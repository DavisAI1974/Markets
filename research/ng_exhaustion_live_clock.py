#!/usr/bin/env python3
"""Causal live-input adapter for the isolated NG exhaustion runway clock.

This is NOT an event detector and does not mutate permanent Frankie.
An upstream causal detector supplies only an exhaustion-event t0. From the live
MBP-10 trade stream this module then:

1. reconstructs the exact 20-second rolling aggressor-volume imbalance used by
   the frozen exhaustion research (trade sign = price vs concurrent top-of-book mid),
2. derives event polarity from raw roll20 at t0,
3. assigns frozen pre-family A/B/C from the oriented t=-60..0 geometry,
4. keeps Family A pending until the legal +60 boundary,
5. feeds the exact oriented t=0..+60 61-sample window into the frozen A post-state
   classifier and deterministic runway clock.

No price path after t0, realized endpoint, ZigZag leg, or model/LLM call is used.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from ng_exhaustion_runway_clock import ExhaustionRunwayClock

EXPECTED_PRE_FAMILY_CLASSIFIER_SHA256 = "583f6a121788b3d962f2ec849a270f96b1786d714ac930d2b0069c6261eda6f7"
FAMILY_FEATURE_COUNT = 78
PRE_SECONDS = 60
POST_SECONDS = 60
ROLL_SECONDS = 20


class LiveClockInputError(RuntimeError):
    pass


class FamilyClassifierIntegrityError(LiveClockInputError):
    pass


def _finite_float(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError, OverflowError) as exc:
        raise LiveClockInputError(f"non-numeric value: {x!r}") from exc
    if not math.isfinite(v):
        raise LiveClockInputError(f"non-finite value: {x!r}")
    return v


def _fill_curve(values: Sequence[float | None]) -> tuple[float, ...]:
    """Match ng_dipole_native_shape_audit.fill_curve exactly.

    Forward-fill internal gaps, then backward-fill leading gaps. At least one
    finite sample must exist. This is used only inside an already-bounded causal
    window; no sample later than the requested window is consulted.
    """
    out: list[float] = []
    for x in values:
        try:
            v = float(x) if x is not None else float("nan")
        except (TypeError, ValueError, OverflowError):
            v = float("nan")
        out.append(v)
    last: float | None = None
    for i, v in enumerate(out):
        if math.isfinite(v):
            last = v
        elif last is not None:
            out[i] = last
    nxt: float | None = None
    for i in range(len(out) - 1, -1, -1):
        if math.isfinite(out[i]):
            nxt = out[i]
        elif nxt is not None:
            out[i] = nxt
    if not out or any(not math.isfinite(v) for v in out):
        raise LiveClockInputError("roll20 curve cannot be filled causally")
    return tuple(out)


def _slope(y: Sequence[float], lo: int, hi: int) -> float:
    vals = [float(v) for v in y[lo:hi]]
    if len(vals) < 2 or max(vals) - min(vals) < 1e-15:
        return 0.0
    n = float(len(vals))
    mx = (n - 1.0) / 2.0
    my = sum(vals) / n
    den = sum((i - mx) ** 2 for i in range(len(vals)))
    return 0.0 if den <= 0 else sum((i - mx) * (v - my) for i, v in enumerate(vals)) / den


def _first_ge(y: Sequence[float], level: float) -> int:
    for i, v in enumerate(y):
        if float(v) >= level:
            return i
    return len(y) - 1


def family_feature(oriented_pre_minus60_to_t0: Sequence[float]) -> tuple[float, ...]:
    """Exact stdlib recovery of ng_exhaustion_family_quantify_v2_20260816.feature."""
    if len(oriented_pre_minus60_to_t0) != 61:
        raise LiveClockInputError(f"pre-family window must contain 61 samples, got {len(oriented_pre_minus60_to_t0)}")
    raw = tuple(_finite_float(x) for x in oriented_pre_minus60_to_t0)
    peak = raw[-1]
    if peak <= 0.0:
        raise LiveClockInputError("oriented t0 roll20 must be positive")
    rel = tuple(v / peak for v in raw)
    base10 = sum(raw[:10]) / 10.0
    excursion = peak - base10
    if abs(excursion) > 1e-9:
        build = tuple((v - base10) / excursion for v in raw)
    else:
        build = tuple(0.0 for _ in raw)

    prominence_base = sorted(abs(v) for v in raw[30:51])
    m = len(prominence_base)
    prom_med = prominence_base[m // 2] if m % 2 else 0.5 * (prominence_base[m // 2 - 1] + prominence_base[m // 2])
    prominence = abs(peak) - prom_med

    c10 = _first_ge(build, .10)
    c25 = _first_ge(build, .25)
    c50 = _first_ge(build, .50)
    c75 = _first_ge(build, .75)
    c90 = _first_ge(build, .90)
    early = _slope(build, 0, 21)
    mid = _slope(build, 20, 41)
    late = _slope(build, 40, 61)
    roughness = sum(abs(build[i + 1] - build[i]) for i in range(60)) / 60.0
    bmean = sum(build) / 61.0
    bstd = math.sqrt(sum((v - bmean) ** 2 for v in build) / 61.0)
    scalar = (
        base10,
        math.log1p(abs(excursion)),
        math.log1p(abs(prominence)),
        (60 - c10) / 60.0,
        (60 - c25) / 60.0,
        (60 - c50) / 60.0,
        (60 - c75) / 60.0,
        (60 - c90) / 60.0,
        max(0, c90 - c10) / 60.0,
        early,
        mid,
        late,
        late - mid,
        mid - early,
        roughness,
        bstd,
    )
    feat = tuple(build[::2]) + tuple(rel[::2]) + scalar
    if len(feat) != FAMILY_FEATURE_COUNT or any(not math.isfinite(v) for v in feat):
        raise LiveClockInputError("pre-family feature contract failed")
    return feat


@dataclass(frozen=True)
class FamilyClassification:
    family: str
    distances: tuple[float, float, float]
    transformed_feature: tuple[float, ...]


@dataclass(frozen=True)
class FrozenPreFamilyClassifier:
    artifact_sha256: str
    center: tuple[float, ...]
    scale: tuple[float, ...]
    centroids: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]

    @classmethod
    def load(cls, path: str | Path) -> "FrozenPreFamilyClassifier":
        raw = Path(path).read_bytes()
        got = sha256(raw).hexdigest()
        if got != EXPECTED_PRE_FAMILY_CLASSIFIER_SHA256:
            raise FamilyClassifierIntegrityError(
                f"pre-family classifier SHA drift: expected {EXPECTED_PRE_FAMILY_CLASSIFIER_SHA256}, got {got}"
            )
        try:
            a = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FamilyClassifierIntegrityError(f"pre-family classifier JSON invalid: {exc}") from exc
        ic = a.get("input_contract", {})
        if ic.get("sample_count") != 61 or ic.get("feature_count") != FAMILY_FEATURE_COUNT:
            raise FamilyClassifierIntegrityError("pre-family input contract drift")
        if ic.get("post_t0_data_used") is not False or ic.get("price_used") is not False or ic.get("outcome_used") is not False:
            raise FamilyClassifierIntegrityError("pre-family classifier causal wall drift")
        sc = a.get("scaler", {})
        if sc.get("type") != "RobustScaler" or sc.get("quantile_range") != [20.0, 80.0]:
            raise FamilyClassifierIntegrityError("pre-family scaler contract drift")
        center = tuple(float(x) for x in sc.get("center", []))
        scale = tuple(float(x) for x in sc.get("scale", []))
        if len(center) != FAMILY_FEATURE_COUNT or len(scale) != FAMILY_FEATURE_COUNT:
            raise FamilyClassifierIntegrityError("pre-family scaler dimension drift")
        if any((not math.isfinite(x)) or x == 0.0 for x in scale):
            raise FamilyClassifierIntegrityError("pre-family scaler contains invalid scale")
        c = a.get("centroids_family_order", {})
        centroids = tuple(tuple(float(x) for x in c.get(name, [])) for name in ("A", "B", "C"))
        if any(len(row) != FAMILY_FEATURE_COUNT for row in centroids):
            raise FamilyClassifierIntegrityError("pre-family centroid dimension drift")
        prov = a.get("provenance", {})
        if prov.get("substantive_population_n") != 3429 or prov.get("recovered_assignment_check", {}).get("mismatches") != 0:
            raise FamilyClassifierIntegrityError("pre-family provenance drift")
        return cls(got, center, scale, (centroids[0], centroids[1], centroids[2]))

    def classify(self, oriented_pre_minus60_to_t0: Sequence[float]) -> FamilyClassification:
        f = family_feature(oriented_pre_minus60_to_t0)
        x = tuple((v - c) / s for v, c, s in zip(f, self.center, self.scale))
        d = tuple(math.dist(x, centroid) for centroid in self.centroids)
        idx = min(range(3), key=lambda i: d[i])
        return FamilyClassification(("A", "B", "C")[idx], (d[0], d[1], d[2]), x)


class AggressorRoll20Feed:
    """Exact second-bucketed live input for the research roll-20 flow series.

    Only MBP-10 trade prints should be ingested. Trade side matches the historical
    loader: price > concurrent mid => buy; price < mid => sell; midpoint/no-book
    prints are ignored for aggressor volume. Seconds must arrive nondecreasing.
    """

    def __init__(self, *, retain_seconds: int = 600):
        if retain_seconds < 180:
            raise ValueError("retain_seconds must be >=180")
        self.retain_seconds = int(retain_seconds)
        self.buy: dict[int, float] = defaultdict(float)
        self.sell: dict[int, float] = defaultdict(float)
        self.last_seen_second: int | None = None
        self.classified_trades = 0
        self.midpoint_skipped = 0
        self.invalid_skipped = 0

    def _advance(self, second: int) -> int:
        sec = int(second)
        if self.last_seen_second is not None and sec < self.last_seen_second:
            raise LiveClockInputError(f"out-of-order trade second: {sec} < {self.last_seen_second}")
        self.last_seen_second = sec if self.last_seen_second is None else max(self.last_seen_second, sec)
        cutoff = sec - self.retain_seconds
        for store in (self.buy, self.sell):
            for k in [k for k in store if k < cutoff]:
                del store[k]
        return sec

    def ingest_volume(self, second: int, *, buy_volume: float = 0.0, sell_volume: float = 0.0) -> None:
        sec = self._advance(second)
        b = _finite_float(buy_volume)
        s = _finite_float(sell_volume)
        if b < 0 or s < 0:
            raise LiveClockInputError("aggressor volume cannot be negative")
        if b:
            self.buy[sec] += b
        if s:
            self.sell[sec] += s

    def ingest_trade(self, second: int, *, price: float, size: float, bid_px: float, ask_px: float) -> str:
        sec = self._advance(second)
        try:
            p = _finite_float(price); q = _finite_float(size); bid = _finite_float(bid_px); ask = _finite_float(ask_px)
        except LiveClockInputError:
            self.invalid_skipped += 1
            return "invalid"
        if not (p > 0 and q > 0 and bid > 0 and ask > 0 and ask >= bid):
            self.invalid_skipped += 1
            return "invalid"
        mid = 0.5 * (bid + ask)
        if p > mid:
            self.buy[sec] += q
            self.classified_trades += 1
            return "buy"
        if p < mid:
            self.sell[sec] += q
            self.classified_trades += 1
            return "sell"
        self.midpoint_skipped += 1
        return "midpoint"

    def raw_value_at(self, second: int) -> float | None:
        sec = int(second)
        lo = sec - ROLL_SECONDS + 1
        b = sum(self.buy.get(s, 0.0) for s in range(lo, sec + 1))
        sv = sum(self.sell.get(s, 0.0) for s in range(lo, sec + 1))
        total = b + sv
        return None if total <= 0 else (b - sv) / total

    def raw_series(self, start_second: int, end_second: int) -> tuple[float | None, ...]:
        if end_second < start_second:
            raise LiveClockInputError("invalid roll20 series bounds")
        return tuple(self.raw_value_at(s) for s in range(int(start_second), int(end_second) + 1))

    def snapshot(self, *, end_second: int | None = None, seconds: int = 180) -> dict[str, Any]:
        end = self.last_seen_second if end_second is None else int(end_second)
        if end is None:
            return {"last_second": None, "roll20_raw": None, "history": [], "classified_trades": 0,
                    "midpoint_skipped": self.midpoint_skipped, "invalid_skipped": self.invalid_skipped}
        start = end - max(1, int(seconds)) + 1
        hist = [[s, self.raw_value_at(s)] for s in range(start, end + 1)]
        return {
            "last_second": end,
            "roll20_raw": self.raw_value_at(end),
            "history": hist,
            "classified_trades": self.classified_trades,
            "midpoint_skipped": self.midpoint_skipped,
            "invalid_skipped": self.invalid_skipped,
        }


@dataclass(frozen=True)
class LiveExhaustionEvent:
    event_id: str
    session_id: str
    t0_second: int
    polarity: int
    family: str
    family_distances: tuple[float, float, float]
    oriented_pre_minus60_to_t0: tuple[float, ...]


class LiveExhaustionRunwayEngine:
    """Compose live roll20 input, frozen pre-family assignment, and V0 runway clock."""

    def __init__(self, *, feed: AggressorRoll20Feed, family_classifier: FrozenPreFamilyClassifier, runway_clock: ExhaustionRunwayClock):
        self.feed = feed
        self.family_classifier = family_classifier
        self.runway_clock = runway_clock
        self.events: dict[str, LiveExhaustionEvent] = {}

    def mark_event(self, *, event_id: str, session_id: str, t0_second: int) -> LiveExhaustionEvent:
        eid = str(event_id)
        if eid in self.events:
            raise LiveClockInputError(f"duplicate event_id: {eid}")
        t0 = int(t0_second)
        if self.feed.last_seen_second is None or self.feed.last_seen_second < t0:
            raise LiveClockInputError("event t0 cannot be ahead of observed live tape")
        raw_pre = _fill_curve(self.feed.raw_series(t0 - PRE_SECONDS, t0))
        raw0 = raw_pre[-1]
        if abs(raw0) <= 1e-12:
            raise LiveClockInputError("event t0 roll20 is zero; polarity unavailable")
        polarity = 1 if raw0 > 0 else -1
        oriented = tuple(polarity * v for v in raw_pre)
        fc = self.family_classifier.classify(oriented)
        event = LiveExhaustionEvent(eid, str(session_id), t0, polarity, fc.family, fc.distances, oriented)
        self.events[eid] = event
        return event

    def update(self, *, event_id: str, now_second: int, microstructure: str = "unavailable", data_flags: Mapping[str, bool] | None = None) -> dict[str, Any]:
        eid = str(event_id)
        if eid not in self.events:
            raise LiveClockInputError(f"unknown event_id: {eid}")
        event = self.events[eid]
        now = int(now_second)
        if now < event.t0_second:
            raise LiveClockInputError("clock update precedes event t0")
        elapsed = float(now - event.t0_second)
        flags = dict(data_flags or {})
        flags.setdefault("event_clock", True)
        flags.setdefault("microstructure", microstructure != "unavailable")
        a_window = None
        if event.family == "A" and elapsed >= POST_SECONDS:
            if self.feed.last_seen_second is None or self.feed.last_seen_second < event.t0_second + POST_SECONDS:
                flags["a_classifier_window"] = False
            else:
                raw_post = _fill_curve(self.feed.raw_series(event.t0_second, event.t0_second + POST_SECONDS))
                a_window = tuple(event.polarity * v for v in raw_post)
                flags["a_classifier_window"] = True
        out = self.runway_clock.update(event_id=event.event_id, session_id=event.session_id, t0=event.t0_second,
                                       family=event.family, elapsed_s=elapsed, a_t0_to_plus60=a_window,
                                       microstructure=microstructure, data_flags=flags)
        out["dipole_polarity"] = event.polarity
        out["pre_family_classifier_sha256"] = self.family_classifier.artifact_sha256
        out["pre_family_distances"] = list(event.family_distances)
        out["live_input_contract"] = "exact_roll20_aggressor_volume_price_vs_concurrent_mid"
        out["future_price_accessed"] = False
        return out
