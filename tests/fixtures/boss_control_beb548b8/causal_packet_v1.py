"""
Point-in-time causal packet builder.

The single job of this module is to make the following claim testable:

    Given the same immutable ledger state and the same as_of timestamp,
    the packet is byte-identical, and it contains nothing that was not
    knowable at as_of.

Everything downstream (trunk, heads, calibrator, validator) inherits
whatever this gets wrong, and a leakage bug here backtests beautifully
and dies live. So this is written defensively: the unsafe operation is
the one that raises, not the one that silently succeeds.

Design commitments
------------------
1. BITEMPORAL. Every record carries event_time (when it happened) and
   ingest_time (when this system could first have known it). Filtering
   is on ingest_time. Filtering on event_time is the classic leakage
   bug: a restatement with a past event_time and a future ingest_time
   is invisible to an event_time filter and is pure lookahead.

2. RESTATEMENTS RESOLVE AS-OF. When a logical key has several versions,
   the packet takes the newest version whose ingest_time <= as_of --
   not the newest version, and not the first.

3. INCOMPLETENESS IS RECORDED, NOT FILLED. If a source watermark trails
   as_of, the packet is stamped degraded with the lag. It does not
   silently proceed, and it does not forward-fill across the gap.

4. DERIVED FEATURES ARE WINDOW-SCOPED. Rolling stats, normalizations,
   regime labels and dipole fits are computed inside a CausalWindow
   that can only see the filtered records. There is no path to the
   full series.

5. CANONICAL BYTES. Floats are quantized to a fixed significand before
   hashing so that BLAS/thread nondeterminism cannot change the packet
   hash. The quantization is part of the stamped spec.

6. FULL STAMP. The packet records code_version, feature_spec_version,
   model_version AND calibrator_version. The last one exists because an
   adaptive calibrator outside the signed registry means two identical
   packets can produce different abstention outcomes with no audit
   trail. If calibration is adaptive, its version belongs in the hash.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

__all__ = [
    "Record",
    "Source",
    "Watermark",
    "CausalWindow",
    "FeatureSpec",
    "PacketStamp",
    "CausalPacket",
    "PacketBuilder",
    "LeakageError",
    "IncompletenessPolicy",
    "canonical_bytes",
    "packet_hash",
]

# Significant digits retained before hashing. 12 is comfortably inside
# float64 precision (~15-17 sig digits) while absorbing last-bit drift
# from different BLAS builds, thread counts and reduction orders.
FLOAT_SIGNIFICAND = 12

SCHEMA_VERSION = "causal_packet/1"


class LeakageError(RuntimeError):
    """Raised when an operation would expose data not knowable at as_of."""


# --------------------------------------------------------------------------
# Records and sources
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Record:
    """A single immutable observation.

    key         logical identity. Restatements of the same fact share a key.
    event_time  when the underlying event occurred (epoch nanoseconds).
    ingest_time when this system could first have known it (epoch nanos).
    payload     the data itself. Must be JSON-canonicalizable.
    version     monotone tiebreak when ingest_time collides.
    """

    key: str
    event_time: int
    ingest_time: int
    payload: Mapping[str, Any]
    version: int = 0

    def __post_init__(self) -> None:
        if self.ingest_time < self.event_time:
            # Not fatal in principle (clock skew), but it means the ledger
            # is claiming the system knew something before it happened.
            # Refuse rather than quietly admit a lookahead vector.
            raise LeakageError(
                f"record {self.key!r} has ingest_time {self.ingest_time} "
                f"before event_time {self.event_time}; ledger clock is "
                f"unsound and this record could inject lookahead"
            )


class Source(Protocol):
    """A ledger-backed source of records.

    Implementations wrap the MBO/V4 ledger, the QSV/OD state store, and
    any other evidence feed. The contract is deliberately narrow: return
    every record for the requested entity whose ingest_time is at or
    before as_of, and report a completeness watermark.
    """

    name: str

    def fetch(self, entity: str, as_of: int) -> Sequence[Record]: ...

    def watermark(self, entity: str, as_of: int) -> int:
        """Max event_time for which this source is believed complete."""
        ...


@dataclass(frozen=True, slots=True)
class Watermark:
    source: str
    value: int
    as_of: int

    @property
    def lag_ns(self) -> int:
        return max(0, self.as_of - self.value)


class IncompletenessPolicy:
    """What to do when a source watermark trails as_of."""

    def __init__(self, max_lag_ns: Mapping[str, int], hard_fail: bool = False):
        self.max_lag_ns = dict(max_lag_ns)
        self.hard_fail = hard_fail

    def evaluate(self, watermarks: Sequence[Watermark]) -> list[str]:
        breaches: list[str] = []
        for wm in watermarks:
            limit = self.max_lag_ns.get(wm.source)
            if limit is not None and wm.lag_ns > limit:
                breaches.append(
                    f"{wm.source}: watermark lag {wm.lag_ns}ns exceeds {limit}ns"
                )
        if breaches and self.hard_fail:
            raise LeakageError("; ".join(breaches))
        return breaches


# --------------------------------------------------------------------------
# Causal window
# --------------------------------------------------------------------------


class CausalWindow:
    """The only view of source data a feature function is allowed.

    Holds records already filtered to ingest_time <= as_of with
    restatements resolved. Exposes no way to reach beyond as_of, and
    tracks which sources were actually read so provenance lands in the
    packet rather than being asserted by hand.
    """

    __slots__ = ("_as_of", "_by_source", "_touched")

    def __init__(self, as_of: int, by_source: Mapping[str, Sequence[Record]]):
        self._as_of = as_of
        self._by_source = {k: tuple(v) for k, v in by_source.items()}
        self._touched: set[str] = set()

    @property
    def as_of(self) -> int:
        return self._as_of

    @property
    def touched_sources(self) -> tuple[str, ...]:
        return tuple(sorted(self._touched))

    def records(self, source: str, lookback_ns: int | None = None) -> tuple[Record, ...]:
        if source not in self._by_source:
            raise KeyError(f"source {source!r} not in this packet's sources")
        self._touched.add(source)
        rows = self._by_source[source]
        if lookback_ns is not None:
            floor = self._as_of - lookback_ns
            rows = tuple(r for r in rows if r.event_time >= floor)
        return rows

    def values(
        self, source: str, field_name: str, lookback_ns: int | None = None
    ) -> tuple[float, ...]:
        return tuple(
            float(r.payload[field_name])
            for r in self.records(source, lookback_ns)
            if field_name in r.payload
        )


FeatureFn = Callable[[CausalWindow], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """A named, versioned block of derived features.

    version is part of the packet hash. Change the maths, bump the
    version, or the evidence graph will attribute old outcomes to new
    features.
    """

    name: str
    version: str
    fn: FeatureFn
    required_sources: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# Canonical serialization
# --------------------------------------------------------------------------


def _canon_float(x: float) -> str:
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0.0:
        return "0E+0"  # collapses +0.0 / -0.0
    d = Decimal(repr(float(x)))
    # Round to fixed significant digits, then normalize exponent form so
    # 1.0 and 1.00 cannot produce different bytes.
    exp = d.adjusted()
    quant = Decimal(1).scaleb(exp - (FLOAT_SIGNIFICAND - 1))
    return f"{d.quantize(quant).normalize():E}"


def _canon(obj: Any) -> Any:
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return {"__f__": _canon_float(obj)}
    if isinstance(obj, int):
        return obj
    if isinstance(obj, str) or obj is None:
        return obj
    if isinstance(obj, Mapping):
        return {str(k): _canon(obj[k]) for k in sorted(obj, key=str)}
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    if hasattr(obj, "item") and hasattr(obj, "dtype"):  # numpy scalar
        return _canon(obj.item())
    if hasattr(obj, "tolist"):  # numpy array
        return _canon(obj.tolist())
    raise TypeError(f"non-canonicalizable type in packet: {type(obj)!r}")


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        _canon(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def packet_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


# --------------------------------------------------------------------------
# Packet
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PacketStamp:
    """Everything that can change the emitted decision, versioned.

    calibrator_version is not optional. An adaptive calibrator that sits
    between the frozen model and the validator is a live mutable input
    to the decision; if it is not in the stamp, drift in the calibrator
    and drift in the model are indistinguishable in the audit.
    """

    code_version: str
    feature_spec_versions: Mapping[str, str]
    model_version: str
    calibrator_version: str
    schema_version: str = SCHEMA_VERSION
    float_significand: int = FLOAT_SIGNIFICAND

    def as_dict(self) -> dict[str, Any]:
        return {
            "code_version": self.code_version,
            "feature_spec_versions": dict(self.feature_spec_versions),
            "model_version": self.model_version,
            "calibrator_version": self.calibrator_version,
            "schema_version": self.schema_version,
            "float_significand": self.float_significand,
        }


@dataclass(frozen=True, slots=True)
class CausalPacket:
    entity: str
    as_of: int
    features: Mapping[str, Any]
    watermarks: tuple[Watermark, ...]
    provenance: Mapping[str, tuple[str, ...]]
    stamp: PacketStamp
    degraded: tuple[str, ...] = ()
    record_counts: Mapping[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "as_of": self.as_of,
            "features": dict(self.features),
            "watermarks": [
                {"source": w.source, "value": w.value, "lag_ns": w.lag_ns}
                for w in sorted(self.watermarks, key=lambda w: w.source)
            ],
            "provenance": {k: list(v) for k, v in sorted(self.provenance.items())},
            "record_counts": dict(sorted(self.record_counts.items())),
            "degraded": list(self.degraded),
            "stamp": self.stamp.as_dict(),
        }

    @property
    def hash(self) -> str:
        return packet_hash(self.as_dict())


# --------------------------------------------------------------------------
# Builder
# --------------------------------------------------------------------------


class PacketBuilder:
    def __init__(
        self,
        sources: Sequence[Source],
        specs: Sequence[FeatureSpec],
        policy: IncompletenessPolicy | None = None,
        code_version: str = "dev",
    ):
        self.sources = {s.name: s for s in sources}
        if len(self.sources) != len(sources):
            raise ValueError("duplicate source names")
        self.specs = tuple(specs)
        self.policy = policy or IncompletenessPolicy({})
        self.code_version = code_version

    @staticmethod
    def _resolve(records: Iterable[Record], as_of: int) -> list[Record]:
        """Bitemporal filter + restatement resolution.

        Keeps, per logical key, the newest version whose ingest_time is
        at or before as_of. This is the whole ballgame: a restatement
        ingested after as_of must not be visible, even though its
        event_time is in the past.
        """
        best: dict[str, Record] = {}
        for r in records:
            if r.ingest_time > as_of:
                continue
            prev = best.get(r.key)
            if prev is None or (r.ingest_time, r.version) > (
                prev.ingest_time,
                prev.version,
            ):
                best[r.key] = r
        return sorted(best.values(), key=lambda r: (r.event_time, r.key))

    def build(
        self,
        entity: str,
        as_of: int,
        model_version: str,
        calibrator_version: str,
    ) -> CausalPacket:
        by_source: dict[str, list[Record]] = {}
        watermarks: list[Watermark] = []
        for name, src in self.sources.items():
            raw = src.fetch(entity, as_of)
            # Defense in depth: never trust the adapter's own filtering.
            by_source[name] = self._resolve(raw, as_of)
            watermarks.append(Watermark(name, src.watermark(entity, as_of), as_of))

        degraded = tuple(self.policy.evaluate(watermarks))

        features: dict[str, Any] = {}
        provenance: dict[str, tuple[str, ...]] = {}
        spec_versions: dict[str, str] = {}

        for spec in self.specs:
            missing = [s for s in spec.required_sources if s not in by_source]
            if missing:
                raise KeyError(f"spec {spec.name!r} requires missing sources {missing}")
            window = CausalWindow(as_of, by_source)
            out = spec.fn(window)
            for k, v in out.items():
                qualified = f"{spec.name}.{k}"
                if qualified in features:
                    raise ValueError(f"duplicate feature {qualified!r}")
                features[qualified] = v
            provenance[spec.name] = window.touched_sources
            spec_versions[spec.name] = spec.version

        stamp = PacketStamp(
            code_version=self.code_version,
            feature_spec_versions=spec_versions,
            model_version=model_version,
            calibrator_version=calibrator_version,
        )

        return CausalPacket(
            entity=entity,
            as_of=as_of,
            features=features,
            watermarks=tuple(watermarks),
            provenance=provenance,
            stamp=stamp,
            degraded=degraded,
            record_counts={k: len(v) for k, v in by_source.items()},
        )
