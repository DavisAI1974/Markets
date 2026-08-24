#!/usr/bin/env python3
"""Continuous V4 replay-envelope to protected Frankie causal-second stream.

The builder is an additive consumer of ``replay_dbn_files`` callbacks.  It does
not alter MBO replay, adapter state, the established roll20 implementation, V4
mechanics, or any lock policy.  Rows freeze at the end of each receive-time
second, retain every non-snapshot MBO action, and expose snapshot/bootstrap use
only through explicit suppression and data-quality receipts.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from ng_exhaustion_live_clock import AggressorRoll20Feed

from research.kalshi.ng_exhaustion_frankie_causal_data_plane_20260824 import (
    GENESIS,
    AtRiskOpportunity,
    CausalDataPlaneError,
    CausalDataPlaneRow,
    ChainExtensionState,
    ClockVector,
    GeometrySecond,
    OpportunityKind,
    ProtectedCausalPrefix,
    ProspectiveDiscoveryMark,
    SemanticCrosswalkReceipt,
    derive_geometry_second,
    make_data_plane_row,
    make_protected_prefix,
    open_at_risk_opportunity,
    seal_prospective_mark,
)


SCHEMA_VERSION = "NG_EXHAUSTION_FRANKIE_CONTINUOUS_STREAM_V1"
MARKER_REVISION = "FRANKIE_PROTECTED_ROLL20_WEAKENING_V1"
VALID_ACTIONS = frozenset("ACMRTFN")
NANOSECONDS = 1_000_000_000


class ContinuousStreamError(CausalDataPlaneError):
    pass


def _id(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ContinuousStreamError(f"{field} must be non-empty")
    return text


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ContinuousStreamError(f"{field} must be lowercase SHA-256")
    return text


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ContinuousStreamError(f"{field} must be finite")
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContinuousStreamError(f"{field} must be finite") from exc
    if not math.isfinite(out):
        raise ContinuousStreamError(f"{field} must be finite")
    return out


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, list):
        return [_thaw(item) for item in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        _thaw(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class OpportunityTransition:
    """A predecessor-known opportunity state change, with no target identity."""

    effective_second: int
    opportunity_id: str
    predecessor_ids: tuple[str, ...]
    ancestry_ids: tuple[str, ...]
    predecessor_states: tuple[str, ...]
    ancestry_gap_seconds: tuple[float, ...]
    predecessor_known_by: float
    reveal_not_before: float
    kind: OpportunityKind
    chain_state: ChainExtensionState

    def validate(self) -> "OpportunityTransition":
        second = int(self.effective_second)
        _id(self.opportunity_id, "opportunity_id")
        if not self.predecessor_ids or any(not str(item).strip() for item in self.predecessor_ids):
            raise ContinuousStreamError("transition requires known predecessors")
        if not self.ancestry_ids or any(not str(item).strip() for item in self.ancestry_ids):
            raise ContinuousStreamError("transition requires ordered ancestry")
        if any(state not in {"P", "O", "S", "X"} for state in self.predecessor_states):
            raise ContinuousStreamError("transition predecessor states must be P/O/S/X")
        if any(_finite(value, "ancestry_gap_seconds") < 0 for value in self.ancestry_gap_seconds):
            raise ContinuousStreamError("transition ancestry gaps cannot be negative")
        known = _finite(self.predecessor_known_by, "predecessor_known_by")
        reveal = _finite(self.reveal_not_before, "reveal_not_before")
        if known > second + 1.0:
            raise ContinuousStreamError("transition cannot precede predecessor known-by")
        if reveal <= second + 1.0:
            raise ContinuousStreamError("transition reveal wall must follow its first causal row")
        allowed = {
            OpportunityKind.AT_RISK: {
                ChainExtensionState.UNRESOLVED,
                ChainExtensionState.EXTENDING,
            },
            OpportunityKind.STOPPED_CHAIN_CONTROL: {ChainExtensionState.STOPPED},
            OpportunityKind.NEGATIVE_CONTROL: {ChainExtensionState.NO_CHAIN},
        }
        if self.chain_state not in allowed[self.kind]:
            raise ContinuousStreamError("transition kind/state mismatch")
        return self


@dataclass(frozen=True)
class ActionEvidence:
    action: str
    side: str
    order_id: int
    price: float | None
    size: float
    ts_event: float
    ts_recv: float
    source_object_id: str
    source_object_sha256: str


@dataclass(frozen=True)
class LegacySecond:
    price: float | None
    native_signed_flow: float
    roll20: float | None
    book_imbalance: float | None


@dataclass(frozen=True)
class DataQualitySecond:
    state_status: str
    price_status: str
    roll20_status: str
    integrity_status: str
    integrity: Mapping[str, Any]
    event_groups: int
    snapshot_groups_suppressed: int
    missing_legacy_trade_rows: int
    state_age_seconds: float | None


def _quality_payload(quality: DataQualitySecond) -> dict[str, Any]:
    return {
        "state_status": quality.state_status,
        "price_status": quality.price_status,
        "roll20_status": quality.roll20_status,
        "integrity_status": quality.integrity_status,
        "integrity": _thaw(quality.integrity),
        "event_groups": quality.event_groups,
        "snapshot_groups_suppressed": quality.snapshot_groups_suppressed,
        "missing_legacy_trade_rows": quality.missing_legacy_trade_rows,
        "state_age_seconds": quality.state_age_seconds,
    }


@dataclass(frozen=True)
class ContinuousCausalSecond:
    schema_version: str
    source_second: int
    source_object_id: str
    source_object_sha256: str
    legacy: LegacySecond
    actions: tuple[ActionEvidence, ...]
    v4_native: Mapping[str, Any]
    quality: DataQualitySecond
    data_plane_row: CausalDataPlaneRow
    prefix: ProtectedCausalPrefix
    mark: ProspectiveDiscoveryMark | None
    prior_stream_hash: str
    stream_hash: str

    def core(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_second": self.source_second,
            "source_object_id": self.source_object_id,
            "source_object_sha256": self.source_object_sha256,
            "legacy": asdict(self.legacy),
            "actions": [asdict(item) for item in self.actions],
            "v4_native": _thaw(self.v4_native),
            "quality": _quality_payload(self.quality),
            "data_plane_row_hash": self.data_plane_row.row_hash,
            "protected_prefix_hash": self.prefix.prefix_hash,
            "mark_hash": None if self.mark is None else self.mark.mark_hash,
            "prior_stream_hash": self.prior_stream_hash,
        }

    def validate(self) -> "ContinuousCausalSecond":
        if self.schema_version != SCHEMA_VERSION:
            raise ContinuousStreamError("continuous-second schema mismatch")
        _id(self.source_object_id, "source_object_id")
        _sha(self.source_object_sha256, "source_object_sha256")
        _sha(self.prior_stream_hash, "prior_stream_hash")
        self.data_plane_row.validate()
        self.prefix.validate()
        if self.source_object_id != self.data_plane_row.source_object_id:
            raise ContinuousStreamError("continuous-second source identity mismatch")
        if self.prefix.state_prefix_hash != self.data_plane_row.row_hash:
            raise ContinuousStreamError("protected prefix is not bound to data-plane row")
        if self.mark is not None:
            self.mark.validate()
            if self.mark.state_prefix_hash != self.prefix.state_prefix_hash:
                raise ContinuousStreamError("prospective mark attempted prefix substitution")
        if self.stream_hash != _stable_hash(self.core()):
            raise ContinuousStreamError("continuous-second hash mismatch")
        return self


class ProtectedProspectiveWeakeningMarker:
    """Marks the first backward-known weakening after a same-sign magnitude build.

    The rule has no elapsed-time threshold, target-relative coordinate, outcome,
    label, or hardcoded event clock.  Equal magnitudes neither build nor weaken.
    """

    detector_revision = MARKER_REVISION

    def __init__(self, *, detector_source_sha256: str) -> None:
        self.detector_source_sha256 = _sha(
            detector_source_sha256, "detector_source_sha256"
        )
        self._sign: int | None = None
        self._last_magnitude: float | None = None
        self._build_observed = False
        self._marked_prefix_hashes: set[str] = set()
        self._marked_candidate_ids: set[str] = set()

    def observe(
        self, *, prefix: ProtectedCausalPrefix, geometry: GeometrySecond
    ) -> ProspectiveDiscoveryMark | None:
        prefix.validate()
        geometry.validate()
        if prefix.geometry_hash != geometry.geometry_hash:
            raise ContinuousStreamError("prospective marker geometry/prefix mismatch")
        if prefix.prefix_hash in self._marked_prefix_hashes:
            return None
        value = geometry.roll20
        if value is None or abs(value) <= 1e-15:
            self._sign = None
            self._last_magnitude = None
            self._build_observed = False
            return None
        sign = 1 if value > 0 else -1
        magnitude = abs(value)
        if self._sign != sign or self._last_magnitude is None:
            self._sign = sign
            self._last_magnitude = magnitude
            self._build_observed = False
            return None
        if magnitude > self._last_magnitude:
            self._build_observed = True
        weakening = self._build_observed and magnitude < self._last_magnitude
        self._last_magnitude = magnitude
        if not weakening:
            return None
        candidate_id = f"roll20-weakening:{prefix.prefix_hash[:20]}"
        if candidate_id in self._marked_candidate_ids:
            return None
        mark = seal_prospective_mark(
            prefix=prefix,
            candidate_id=candidate_id,
            detector_revision=self.detector_revision,
            detector_source_sha256=self.detector_source_sha256,
            detector_marked_at=prefix.evaluated_at,
            event_known_by=prefix.evaluated_at,
        )
        self._marked_prefix_hashes.add(prefix.prefix_hash)
        self._marked_candidate_ids.add(candidate_id)
        self._build_observed = False
        return mark


@dataclass
class _SecondBucket:
    actions: list[ActionEvidence]
    event_groups: int = 0
    snapshot_groups: int = 0
    missing_legacy_trade_rows: int = 0
    last_event_at: float | None = None
    last_received_at: float | None = None
    trade_price: float | None = None


class ContinuousV4CausalStreamBuilder:
    """Stateful ``replay_dbn_files`` callback consumer and second-row emitter."""

    def __init__(
        self,
        *,
        run_id: str,
        target_start_second: int,
        target_end_second: int,
        source_manifest_sha256: str,
        crosswalk: SemanticCrosswalkReceipt,
        opportunity_transitions: Sequence[OpportunityTransition],
        marker: ProtectedProspectiveWeakeningMarker | None = None,
    ) -> None:
        self.run_id = _id(run_id, "run_id")
        self.target_start_second = int(target_start_second)
        self.target_end_second = int(target_end_second)
        if self.target_end_second <= self.target_start_second:
            raise ContinuousStreamError("target interval must be non-empty")
        self.source_manifest_sha256 = _sha(
            source_manifest_sha256, "source_manifest_sha256"
        )
        self.crosswalk = crosswalk.validate()
        if self.crosswalk.source_manifest_sha256 != self.source_manifest_sha256:
            raise ContinuousStreamError("crosswalk/source-manifest mismatch")
        transitions = tuple(opportunity_transitions)
        if not transitions:
            raise ContinuousStreamError("at least one opportunity transition is required")
        for item in transitions:
            item.validate()
        ordered = tuple(sorted(transitions, key=lambda item: item.effective_second))
        seconds = tuple(item.effective_second for item in ordered)
        if len(seconds) != len(set(seconds)):
            raise ContinuousStreamError("duplicate opportunity transition second")
        if ordered[0].effective_second > self.target_start_second:
            raise ContinuousStreamError("opportunity state must exist at target start")
        self.transitions = ordered
        self.marker = marker
        self.feed = AggressorRoll20Feed(retain_seconds=600)
        self._buckets: dict[int, _SecondBucket] = {}
        self._next_emit_second = self.target_start_second
        self._last_group_second: int | None = None
        self._last_event_at: float | None = None
        self._last_received_at: float | None = None
        self._latest_source_object: str | None = None
        self._latest_source_sha256: str | None = None
        self._latest_v4_native: Mapping[str, Any] | None = None
        self._latest_native_received_at: float | None = None
        self._latest_price: float | None = None
        self._latest_book_imbalance: float | None = None
        self._prior_geometry: GeometrySecond | None = None
        self._prior_row_hash = GENESIS
        self._prior_stream_hash = GENESIS
        self._finished = False
        self._bootstrap_groups = 0
        self._snapshot_groups = 0
        self._quiet_rows = 0
        self._degraded_rows = 0
        self._marker_count = 0
        self._rows_emitted = 0
        self._action_counts: Counter[str] = Counter()

    @staticmethod
    def _materialize_full_state(envelope: Mapping[str, Any]) -> Mapping[str, Any]:
        state = envelope.get("full_state")
        if isinstance(state, Mapping):
            return state
        checkpoint = getattr(state, "checkpoint", None)
        if callable(checkpoint):
            result = checkpoint()
            if isinstance(result, Mapping):
                return result
        raise ContinuousStreamError("V4 envelope does not expose materializable full state")

    @staticmethod
    def _source_identity(
        frame: Mapping[str, Any], prior_object: str | None, prior_sha: str | None
    ) -> tuple[str, str]:
        for raw in frame.get("raw_actions") or ():
            if not isinstance(raw, Mapping):
                continue
            obj = str(raw.get("source_dbn_object") or "").strip()
            digest = str(raw.get("source_dbn_sha256") or "").strip().lower()
            if obj and len(digest) == 64:
                return obj, _sha(digest, "source_dbn_sha256")
        if prior_object is not None and prior_sha is not None:
            return prior_object, prior_sha
        raise ContinuousStreamError("source object identity absent from first V4 group")

    @staticmethod
    def _legacy_book_imbalance(rows: Sequence[Mapping[str, Any]]) -> float | None:
        for row in reversed(rows):
            bid = sum(float(row.get(f"bid_sz_{i:02d}", 0) or 0) for i in range(10))
            ask = sum(float(row.get(f"ask_sz_{i:02d}", 0) or 0) for i in range(10))
            if bid + ask > 0:
                return (bid - ask) / (bid + ask)
        return None

    def _transition_at(self, second: int) -> OpportunityTransition:
        eligible = [item for item in self.transitions if item.effective_second <= second]
        if not eligible:
            raise ContinuousStreamError("no lawful opportunity state for causal second")
        return eligible[-1]

    def _ingest_group(
        self, second: int, envelope: Mapping[str, Any], legacy_rows: Sequence[Mapping[str, Any]]
    ) -> None:
        frame = envelope.get("compact_event_frame")
        if not isinstance(frame, Mapping):
            raise ContinuousStreamError("V4 envelope missing compact_event_frame")
        if envelope.get("causal_availability_clock") != "ts_recv_ns":
            raise ContinuousStreamError("V4 envelope availability must be ts_recv_ns")
        if frame.get("event_group_complete_f_last") is not True:
            raise ContinuousStreamError("partial MBO event group cannot enter causal stream")
        state = self._materialize_full_state(envelope)
        source_object, source_sha = self._source_identity(
            frame, self._latest_source_object, self._latest_source_sha256
        )
        event_at = _finite(envelope.get("ts_event_ns"), "ts_event_ns") / NANOSECONDS
        received_at = _finite(envelope.get("ts_recv_ns"), "ts_recv_ns") / NANOSECONDS
        if int(received_at) != second:
            raise ContinuousStreamError("group receive second mismatch")
        self._last_event_at = event_at
        self._last_received_at = received_at
        self._latest_source_object = source_object
        self._latest_source_sha256 = source_sha
        self._latest_native_received_at = received_at
        self._latest_v4_native = _freeze(
            {
                "instrument_id": envelope.get("instrument_id"),
                "raw_symbol": envelope.get("raw_symbol"),
                "book": state.get("book") or frame.get("book") or {},
                "activity": state.get("activity") or frame.get("activity") or {},
                "integrity": state.get("integrity") or frame.get("integrity") or {},
                "full_depth_exposed": bool(envelope.get("full_depth_exposed")),
                "fifo_order_state_exposed": bool(envelope.get("fifo_order_state_exposed")),
                "full_state_mode": envelope.get("full_state_mode"),
            }
        )

        in_target = self.target_start_second <= second < self.target_end_second
        if not in_target:
            self._bootstrap_groups += int(second < self.target_start_second)
        bucket = self._buckets.setdefault(second, _SecondBucket(actions=[])) if in_target else None
        if bucket is not None:
            bucket.event_groups += 1
            bucket.last_event_at = event_at
            bucket.last_received_at = received_at

        snapshot_only = frame.get("snapshot_bootstrap_only") is True
        if snapshot_only:
            self._snapshot_groups += int(in_target)
            if bucket is not None:
                bucket.snapshot_groups += 1

        non_snapshot_trade_actions = 0
        for raw in frame.get("raw_actions") or ():
            if not isinstance(raw, Mapping):
                raise ContinuousStreamError("raw MBO action must be a mapping")
            if bool(raw.get("is_snapshot")):
                continue
            action = str(raw.get("action") or "")
            if action not in VALID_ACTIONS:
                raise ContinuousStreamError(f"unsupported MBO action {action!r}")
            if action == "T":
                non_snapshot_trade_actions += 1
            if bucket is None:
                continue
            evidence = ActionEvidence(
                action=action,
                side=str(raw.get("side") or "N"),
                order_id=int(raw.get("order_id") or 0),
                price=None if raw.get("price") is None else _finite(raw.get("price"), "price"),
                size=_finite(raw.get("size", 0), "size"),
                ts_event=_finite(raw.get("ts_event_ns"), "action.ts_event_ns") / NANOSECONDS,
                ts_recv=_finite(raw.get("ts_recv_ns"), "action.ts_recv_ns") / NANOSECONDS,
                source_object_id=source_object,
                source_object_sha256=source_sha,
            )
            bucket.actions.append(evidence)
            self._action_counts[action] += 1

        legacy_trade_rows = 0
        lawful_legacy_rows = () if snapshot_only else legacy_rows
        for row in lawful_legacy_rows:
            if not isinstance(row, Mapping) or str(row.get("action") or "") != "T":
                continue
            row_second = int(_finite(row.get("ts_recv"), "legacy.ts_recv"))
            if row_second != second:
                raise ContinuousStreamError("legacy trade row receive second mismatch")
            event_second = int(_finite(row.get("ts_event"), "legacy.ts_event"))
            if event_second > row_second:
                raise ContinuousStreamError("legacy trade event second cannot follow receive second")
            price = _finite(row.get("price"), "legacy.price")
            size = _finite(row.get("size"), "legacy.size")
            self.feed.ingest_trade(
                event_second,
                price=price,
                size=size,
                bid_px=_finite(row.get("bid_px_00"), "legacy.bid_px_00"),
                ask_px=_finite(row.get("ask_px_00"), "legacy.ask_px_00"),
            )
            self._latest_price = price
            legacy_trade_rows += 1
            if bucket is not None:
                bucket.trade_price = price
        if bucket is not None and non_snapshot_trade_actions > legacy_trade_rows:
            bucket.missing_legacy_trade_rows += non_snapshot_trade_actions - legacy_trade_rows

        legacy_imbalance = self._legacy_book_imbalance(lawful_legacy_rows)
        if legacy_imbalance is None:
            book = frame.get("book") or {}
            if isinstance(book, Mapping) and book.get("depth_imbalance_n") is not None:
                legacy_imbalance = _finite(
                    book.get("depth_imbalance_n"), "book.depth_imbalance_n"
                )
        if legacy_imbalance is not None:
            self._latest_book_imbalance = legacy_imbalance

    def consume_group(
        self, envelope: Mapping[str, Any], legacy_rows: Sequence[Mapping[str, Any]]
    ) -> tuple[ContinuousCausalSecond, ...]:
        if self._finished:
            raise ContinuousStreamError("cannot consume after finish")
        received_ns = int(_finite(envelope.get("ts_recv_ns"), "ts_recv_ns"))
        second = received_ns // NANOSECONDS
        if self._last_group_second is not None and second < self._last_group_second:
            raise ContinuousStreamError("V4 groups must arrive in nondecreasing receive seconds")
        emitted = self._emit_before(second)
        if second < self.target_end_second:
            self._ingest_group(second, envelope, legacy_rows)
        self._last_group_second = second
        return emitted

    def _emit_before(self, second: int) -> tuple[ContinuousCausalSecond, ...]:
        out: list[ContinuousCausalSecond] = []
        stop = min(int(second), self.target_end_second)
        while self._next_emit_second < stop:
            out.append(self._emit_second(self._next_emit_second))
            self._next_emit_second += 1
        return tuple(out)

    def _emit_second(self, source_second: int) -> ContinuousCausalSecond:
        if self._latest_source_object is None or self._latest_source_sha256 is None:
            raise ContinuousStreamError("cannot emit before source/bootstrap state exists")
        bucket = self._buckets.pop(source_second, None)
        actions = () if bucket is None else tuple(bucket.actions)
        event_groups = 0 if bucket is None else bucket.event_groups
        snapshots = 0 if bucket is None else bucket.snapshot_groups
        missing_legacy = 0 if bucket is None else bucket.missing_legacy_trade_rows
        active_groups = event_groups - snapshots
        cutoff = float(source_second + 1)
        event_at = (
            bucket.last_event_at
            if bucket is not None and bucket.last_event_at is not None
            else self._last_event_at if self._last_event_at is not None else cutoff
        )
        received_at = (
            bucket.last_received_at
            if bucket is not None and bucket.last_received_at is not None
            else self._last_received_at if self._last_received_at is not None else cutoff
        )
        if event_at > cutoff or received_at > cutoff:
            raise ContinuousStreamError("source clocks cross causal second cutoff")

        buy_20 = sum(self.feed.buy.get(sec, 0.0) for sec in range(source_second - 19, source_second + 1))
        sell_20 = sum(self.feed.sell.get(sec, 0.0) for sec in range(source_second - 19, source_second + 1))
        transition = self._transition_at(source_second)
        unresolved_age = (
            cutoff - transition.predecessor_known_by
            if transition.chain_state
            in {ChainExtensionState.UNRESOLVED, ChainExtensionState.EXTENDING}
            else None
        )
        geometry = derive_geometry_second(
            causal_second=cutoff,
            feature_available_at=cutoff,
            price=self._latest_price,
            buy_aggressor_qty_20s=buy_20,
            sell_aggressor_qty_20s=sell_20,
            book_imbalance_top10=self._latest_book_imbalance,
            predecessor_states=transition.predecessor_states,
            ancestry_gap_seconds=transition.ancestry_gap_seconds,
            unresolved_age_seconds=unresolved_age,
            prior=self._prior_geometry,
        )
        opportunity: AtRiskOpportunity = open_at_risk_opportunity(
            opportunity_id=transition.opportunity_id,
            run_id=self.run_id,
            predecessor_ids=transition.predecessor_ids,
            ancestry_ids=transition.ancestry_ids,
            predecessor_known_by=transition.predecessor_known_by,
            evaluated_at=cutoff,
            reveal_not_before=transition.reveal_not_before,
            kind=transition.kind,
            chain_state=transition.chain_state,
            state_prefix_hash=self._prior_row_hash,
            source_manifest_sha256=self.source_manifest_sha256,
        )
        clocks = ClockVector(
            event_at=event_at,
            received_at=received_at,
            event_known_by=cutoff,
            feature_available_at=cutoff,
            evaluated_at=cutoff,
            lock_at=None,
        ).validate()
        row = make_data_plane_row(
            run_id=self.run_id,
            source_object_id=self._latest_source_object,
            source_manifest_sha256=self.source_manifest_sha256,
            crosswalk_receipt_hash=self.crosswalk.receipt_hash,
            clocks=clocks,
            geometry=geometry,
            opportunity=opportunity,
            prior_row_hash=self._prior_row_hash,
        )
        prefix = make_protected_prefix(row=row, crosswalk=self.crosswalk)
        mark = None if self.marker is None else self.marker.observe(prefix=prefix, geometry=geometry)

        current_buy = self.feed.buy.get(source_second, 0.0)
        current_sell = self.feed.sell.get(source_second, 0.0)
        legacy = LegacySecond(
            price=self._latest_price,
            native_signed_flow=current_buy - current_sell,
            roll20=self.feed.raw_value_at(source_second),
            book_imbalance=self._latest_book_imbalance,
        )
        if geometry.roll20 != legacy.roll20:
            raise ContinuousStreamError("AggressorRoll20Feed/geometry semantic mismatch")

        if active_groups > 0:
            state_status = "OBSERVED"
        elif snapshots > 0:
            state_status = "SNAPSHOT_ONLY_SUPPRESSED"
        elif self._latest_v4_native is not None:
            state_status = "QUIET_CARRY"
            self._quiet_rows += 1
        else:
            state_status = "MISSING"
        if bucket is not None and bucket.trade_price is not None:
            price_status = "OBSERVED_TRADE"
        elif self._latest_price is not None:
            price_status = "CAUSAL_CARRY"
        else:
            price_status = "MISSING"
        if legacy.roll20 is None:
            roll_status = "SPARSE_NO_CLASSIFIED_VOLUME"
        elif current_buy + current_sell > 0:
            roll_status = "OBSERVED"
        else:
            roll_status = "CAUSAL_ROLLING_CARRY"
        native = self._latest_v4_native or MappingProxyType({})
        integrity = native.get("integrity", {}) if isinstance(native, Mapping) else {}
        degraded = any(bool(value) for value in integrity.values()) if isinstance(integrity, Mapping) else True
        integrity_status = "DEGRADED" if degraded else "PASS"
        self._degraded_rows += int(degraded)
        state_age = (
            None
            if self._latest_native_received_at is None
            else max(0.0, cutoff - self._latest_native_received_at)
        )
        quality = DataQualitySecond(
            state_status=state_status,
            price_status=price_status,
            roll20_status=roll_status,
            integrity_status=integrity_status,
            integrity=_freeze(integrity),
            event_groups=event_groups,
            snapshot_groups_suppressed=snapshots,
            missing_legacy_trade_rows=missing_legacy,
            state_age_seconds=state_age,
        )
        core = {
            "schema_version": SCHEMA_VERSION,
            "source_second": source_second,
            "source_object_id": self._latest_source_object,
            "source_object_sha256": self._latest_source_sha256,
            "legacy": asdict(legacy),
            "actions": [asdict(item) for item in actions],
            "v4_native": _thaw(native),
            "quality": _quality_payload(quality),
            "data_plane_row_hash": row.row_hash,
            "protected_prefix_hash": prefix.prefix_hash,
            "mark_hash": None if mark is None else mark.mark_hash,
            "prior_stream_hash": self._prior_stream_hash,
        }
        result = ContinuousCausalSecond(
            schema_version=SCHEMA_VERSION,
            source_second=source_second,
            source_object_id=self._latest_source_object,
            source_object_sha256=self._latest_source_sha256,
            legacy=legacy,
            actions=actions,
            v4_native=native,
            quality=quality,
            data_plane_row=row,
            prefix=prefix,
            mark=mark,
            prior_stream_hash=self._prior_stream_hash,
            stream_hash=_stable_hash(core),
        ).validate()
        self._prior_geometry = geometry
        self._prior_row_hash = row.row_hash
        self._prior_stream_hash = result.stream_hash
        self._rows_emitted += 1
        self._marker_count += int(mark is not None)
        return result

    def finish(self) -> tuple[ContinuousCausalSecond, ...]:
        if self._finished:
            return ()
        out = self._emit_before(self.target_end_second)
        self._finished = True
        return out

    def diagnostics(self) -> dict[str, Any]:
        """Stable structured signals for replay progress and suppression auditing."""
        return {
            "event": "frankie_continuous_stream_status",
            "run_id": self.run_id,
            "rows_emitted": self._rows_emitted,
            "next_source_second": self._next_emit_second,
            "bootstrap_groups_consumed": self._bootstrap_groups,
            "snapshot_groups_suppressed": self._snapshot_groups,
            "quiet_carry_rows": self._quiet_rows,
            "degraded_integrity_rows": self._degraded_rows,
            "prospective_marks": self._marker_count,
            "action_counts": dict(sorted(self._action_counts.items())),
            "last_row_hash": self._prior_row_hash,
            "last_stream_hash": self._prior_stream_hash,
            "reset_count": 0,
        }


def make_replay_group_callback(
    builder: ContinuousV4CausalStreamBuilder,
    on_second: Callable[[ContinuousCausalSecond], None],
) -> Callable[[Mapping[str, Any], Sequence[Mapping[str, Any]]], int]:
    """Return the exact two-argument callback accepted by ``replay_dbn_files``."""

    def on_group(
        envelope: Mapping[str, Any], legacy_rows: Sequence[Mapping[str, Any]]
    ) -> int:
        emitted = builder.consume_group(envelope, legacy_rows)
        for row in emitted:
            on_second(row)
        return len(emitted)

    return on_group


def replay_dbn_files_to_causal_seconds(
    paths: list[str],
    *,
    builder: ContinuousV4CausalStreamBuilder,
    on_second: Callable[[ContinuousCausalSecond], None],
) -> dict[str, Any]:
    """Execute established full-state replay through the protected second stream."""
    from ng_exhaustion_mbo_v4_full_state_replay_20260820 import replay_dbn_files

    callback = make_replay_group_callback(builder, on_second)
    replay_receipt = replay_dbn_files(paths, callback, materialize_full_state=True)
    for row in builder.finish():
        on_second(row)
    return {
        "schema": SCHEMA_VERSION,
        "replay": replay_receipt,
        "stream": builder.diagnostics(),
    }
