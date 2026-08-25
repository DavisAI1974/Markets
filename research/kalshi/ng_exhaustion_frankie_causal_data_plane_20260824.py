#!/usr/bin/env python3
"""Protected continuous causal data-plane contracts for the Frankie V4 bridge.

This additive module binds the established MBO replay/adapter surface to immutable,
per-second bridge records.  It defines no detector, probability, lock, or legacy
science algorithm.  In particular, it contains no Step-1 target identities, labels,
populations, target-relative clocks, or outcome data before a frozen reveal boundary.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping, Protocol, Sequence

from research.kalshi.ng_exhaustion_v4_mechanics import V4ContractError


SCHEMA_VERSION = "NG_EXHAUSTION_FRANKIE_CAUSAL_DATA_PLANE_V1"
GENESIS = "0" * 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_LEGACY_OBSERVABLES = (
    "legacy_price",
    "legacy_native_signed_flow",
    "legacy_roll20",
    "legacy_book_imbalance",
    "predecessor_family_chain",
)

_EXACT_MAPPING_CONTRACT: Mapping[str, tuple[tuple[str, ...], str]] = {
    "legacy_price": (
        ("compact_event_frame.raw_actions[action=T].price",),
        "LAST_ACTUAL_TRADE_PRICE_PER_RECEIVE_SECOND_WITH_CAUSAL_FORWARD_CARRY",
    ),
    "legacy_native_signed_flow": (
        (
            "compact_event_frame.raw_actions[action=T].side",
            "compact_event_frame.raw_actions[action=T].size",
        ),
        "BUY_AGGRESSOR_QTY_MINUS_SELL_AGGRESSOR_QTY",
    ),
    "legacy_roll20": (
        (
            "compact_event_frame.activity.20.trade_buy_aggressor_qty",
            "compact_event_frame.activity.20.trade_sell_aggressor_qty",
            "compact_event_frame.activity.20.trade_aggressor_imbalance",
        ),
        "V4_ACTIVITY_20S_TRADE_AGGRESSOR_IMBALANCE_AS_LEGACY_ROLL20",
    ),
    "legacy_book_imbalance": (
        ("compact_event_frame.book.depth_imbalance_n",),
        "TOP10_BID_MINUS_ASK_SIZE_OVER_TOTAL_SIZE",
    ),
    "predecessor_family_chain": (
        (
            "geometry.predecessor_states",
            "geometry.ancestry_gap_seconds",
            "opportunity.predecessor_ids",
            "opportunity.ancestry_ids",
            "opportunity.chain_state",
        ),
        "LAWFULLY_KNOWN_PREDECESSOR_STATE_AND_ORDERED_ANCESTRY_ONLY",
    ),
}


class CausalDataPlaneError(V4ContractError):
    """Raised when bridge data would violate a causal or identity boundary."""


def _id(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CausalDataPlaneError(f"{field} must be non-empty")
    return text


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise CausalDataPlaneError(f"{field} must be lowercase SHA-256")
    return text


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise CausalDataPlaneError(f"{field} must be finite")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CausalDataPlaneError(f"{field} must be finite") from exc
    if not math.isfinite(result):
        raise CausalDataPlaneError(f"{field} must be finite")
    return result


def _optional_finite(value: Any, field: str) -> float | None:
    return None if value is None else _finite(value, field)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        _jsonable(dict(payload)), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ClockVector:
    """Six non-conflated bridge clocks; equal values are allowed, backdating is not."""

    event_at: float
    received_at: float
    event_known_by: float
    feature_available_at: float
    evaluated_at: float
    lock_at: float | None = None

    def validate(self) -> "ClockVector":
        event = _finite(self.event_at, "event_at")
        received = _finite(self.received_at, "received_at")
        known = _finite(self.event_known_by, "event_known_by")
        feature = _finite(self.feature_available_at, "feature_available_at")
        evaluated = _finite(self.evaluated_at, "evaluated_at")
        if event > known or received > known:
            raise CausalDataPlaneError("event_at/received_at cannot exceed event_known_by")
        if known > feature:
            raise CausalDataPlaneError("feature_available_at cannot precede event_known_by")
        if feature > evaluated:
            raise CausalDataPlaneError("evaluated_at cannot precede feature_available_at")
        if self.lock_at is not None and _finite(self.lock_at, "lock_at") < evaluated:
            raise CausalDataPlaneError("lock_at cannot precede evaluated_at")
        return self


@dataclass(frozen=True)
class SemanticMapping:
    legacy_observable: str
    v4_native_fields: tuple[str, ...]
    derivation: str
    causal_availability_clock: str = "ts_recv_ns"
    requires_complete_event_group: bool = True

    def validate(self) -> "SemanticMapping":
        name = _id(self.legacy_observable, "legacy_observable")
        if name not in _EXACT_MAPPING_CONTRACT:
            raise CausalDataPlaneError(f"unsupported legacy observable {name}")
        fields = tuple(_id(item, "v4_native_field") for item in self.v4_native_fields)
        expected_fields, expected_derivation = _EXACT_MAPPING_CONTRACT[name]
        if fields != expected_fields or self.derivation != expected_derivation:
            raise CausalDataPlaneError(f"legacy/V4 semantic drift for {name}")
        if self.causal_availability_clock != "ts_recv_ns":
            raise CausalDataPlaneError("semantic crosswalk availability must be ts_recv_ns")
        if self.requires_complete_event_group is not True:
            raise CausalDataPlaneError("semantic crosswalk requires complete F_LAST event groups")
        return self


def default_legacy_v4_mappings() -> tuple[SemanticMapping, ...]:
    return tuple(
        SemanticMapping(name, fields, derivation)
        for name, (fields, derivation) in _EXACT_MAPPING_CONTRACT.items()
    )


@dataclass(frozen=True)
class SemanticCrosswalkReceipt:
    schema_version: str
    mappings: tuple[SemanticMapping, ...]
    source_manifest_sha256: str
    adapter_revision: str
    transform_sha256: str
    coverage_numerator: int
    coverage_denominator: int
    coverage_fraction: float
    causal_availability_clock: str
    receipt_hash: str

    def core(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mappings": [asdict(item) for item in self.mappings],
            "source_manifest_sha256": self.source_manifest_sha256,
            "adapter_revision": self.adapter_revision,
            "transform_sha256": self.transform_sha256,
            "coverage_numerator": self.coverage_numerator,
            "coverage_denominator": self.coverage_denominator,
            "coverage_fraction": self.coverage_fraction,
            "causal_availability_clock": self.causal_availability_clock,
        }

    def validate(self) -> "SemanticCrosswalkReceipt":
        if self.schema_version != SCHEMA_VERSION:
            raise CausalDataPlaneError("crosswalk schema version mismatch")
        _sha(self.source_manifest_sha256, "source_manifest_sha256")
        _sha(self.transform_sha256, "transform_sha256")
        _id(self.adapter_revision, "adapter_revision")
        for item in self.mappings:
            item.validate()
        names = tuple(item.legacy_observable for item in self.mappings)
        if len(names) != len(set(names)):
            raise CausalDataPlaneError("duplicate legacy observable in crosswalk")
        required = set(REQUIRED_LEGACY_OBSERVABLES)
        covered = set(names) & required
        if set(names) != required or self.coverage_numerator != len(covered):
            raise CausalDataPlaneError("legacy/V4 crosswalk must provide 100% required coverage")
        if self.coverage_denominator != len(required) or self.coverage_fraction != 1.0:
            raise CausalDataPlaneError("legacy/V4 crosswalk must receipt 100% coverage")
        if self.causal_availability_clock != "ts_recv_ns":
            raise CausalDataPlaneError("crosswalk receipt availability must be ts_recv_ns")
        if self.receipt_hash != _stable_hash(self.core()):
            raise CausalDataPlaneError("crosswalk receipt hash mismatch")
        return self


def seal_semantic_crosswalk(
    *,
    mappings: Sequence[SemanticMapping],
    source_manifest_sha256: str,
    adapter_revision: str,
    transform_sha256: str,
) -> SemanticCrosswalkReceipt:
    frozen = tuple(mappings)
    for item in frozen:
        item.validate()
    required = set(REQUIRED_LEGACY_OBSERVABLES)
    covered = {item.legacy_observable for item in frozen} & required
    core = {
        "schema_version": SCHEMA_VERSION,
        "mappings": [asdict(item) for item in frozen],
        "source_manifest_sha256": _sha(source_manifest_sha256, "source_manifest_sha256"),
        "adapter_revision": _id(adapter_revision, "adapter_revision"),
        "transform_sha256": _sha(transform_sha256, "transform_sha256"),
        "coverage_numerator": len(covered),
        "coverage_denominator": len(required),
        "coverage_fraction": len(covered) / len(required),
        "causal_availability_clock": "ts_recv_ns",
    }
    receipt = SemanticCrosswalkReceipt(
        **{**core, "mappings": frozen}, receipt_hash=_stable_hash(core)
    )
    return receipt.validate()


@dataclass(frozen=True)
class GeometrySecond:
    causal_second: float
    feature_available_at: float
    price: float | None
    buy_aggressor_qty_20s: float
    sell_aggressor_qty_20s: float
    native_signed_flow_20s: float
    roll20: float | None
    book_imbalance_top10: float | None
    price_delta_1s: float | None
    roll20_delta_1s: float | None
    roll20_curvature_1s: float | None
    book_imbalance_delta_1s: float | None
    predecessor_states: tuple[str, ...]
    ancestry_gap_seconds: tuple[float, ...]
    unresolved_age_seconds: float | None
    geometry_hash: str

    def core(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("geometry_hash", None)
        return data

    def validate(self) -> "GeometrySecond":
        second = _finite(self.causal_second, "causal_second")
        available = _finite(self.feature_available_at, "feature_available_at")
        if available > second:
            raise CausalDataPlaneError("feature availability cannot be after its causal second")
        _optional_finite(self.price, "price")
        buy = _finite(self.buy_aggressor_qty_20s, "buy_aggressor_qty_20s")
        sell = _finite(self.sell_aggressor_qty_20s, "sell_aggressor_qty_20s")
        if buy < 0 or sell < 0:
            raise CausalDataPlaneError("aggressor quantities cannot be negative")
        if abs(self.native_signed_flow_20s - (buy - sell)) > 1e-12:
            raise CausalDataPlaneError("native signed-flow derivation mismatch")
        expected_roll = None if buy + sell == 0 else (buy - sell) / (buy + sell)
        if expected_roll is None:
            if self.roll20 is not None:
                raise CausalDataPlaneError("roll20 must be missing when no aggressor volume exists")
        elif self.roll20 is None or abs(_finite(self.roll20, "roll20") - expected_roll) > 1e-12:
            raise CausalDataPlaneError("roll20 derivation mismatch")
        book = _optional_finite(self.book_imbalance_top10, "book_imbalance_top10")
        if book is not None and not -1.0 <= book <= 1.0:
            raise CausalDataPlaneError("book_imbalance_top10 must be within [-1,1]")
        for field in (
            "price_delta_1s",
            "roll20_delta_1s",
            "roll20_curvature_1s",
            "book_imbalance_delta_1s",
        ):
            _optional_finite(getattr(self, field), field)
        if any(state not in {"P", "O", "S", "X"} for state in self.predecessor_states):
            raise CausalDataPlaneError("predecessor states must use only known P/O/S/X values")
        gaps = tuple(_finite(value, "ancestry_gap_seconds") for value in self.ancestry_gap_seconds)
        if any(value < 0 for value in gaps):
            raise CausalDataPlaneError("ancestry gaps cannot be negative")
        age = _optional_finite(self.unresolved_age_seconds, "unresolved_age_seconds")
        if age is not None and age < 0:
            raise CausalDataPlaneError("unresolved age cannot be negative")
        if self.geometry_hash != _stable_hash(self.core()):
            raise CausalDataPlaneError("geometry hash mismatch")
        return self


def derive_geometry_second(
    *,
    causal_second: Any,
    feature_available_at: Any,
    price: Any,
    buy_aggressor_qty_20s: Any,
    sell_aggressor_qty_20s: Any,
    book_imbalance_top10: Any,
    predecessor_states: Sequence[str],
    ancestry_gap_seconds: Sequence[Any],
    unresolved_age_seconds: Any,
    prior: GeometrySecond | None = None,
) -> GeometrySecond:
    second = _finite(causal_second, "causal_second")
    available = _finite(feature_available_at, "feature_available_at")
    if available > second:
        raise CausalDataPlaneError("feature availability cannot be after its causal second")
    price_value = _optional_finite(price, "price")
    buy = _finite(buy_aggressor_qty_20s, "buy_aggressor_qty_20s")
    sell = _finite(sell_aggressor_qty_20s, "sell_aggressor_qty_20s")
    if buy < 0 or sell < 0:
        raise CausalDataPlaneError("aggressor quantities cannot be negative")
    signed = buy - sell
    roll = None if buy + sell == 0 else signed / (buy + sell)
    book = _optional_finite(book_imbalance_top10, "book_imbalance_top10")
    if prior is not None:
        prior.validate()
        if abs(second - prior.causal_second - 1.0) > 1e-9:
            raise CausalDataPlaneError("geometry prior must be the preceding causal second")
    price_delta = None if prior is None or price_value is None or prior.price is None else price_value - prior.price
    roll_delta = None if prior is None or roll is None or prior.roll20 is None else roll - prior.roll20
    curvature = (
        None
        if prior is None or roll_delta is None or prior.roll20_delta_1s is None
        else roll_delta - prior.roll20_delta_1s
    )
    book_delta = (
        None
        if prior is None or book is None or prior.book_imbalance_top10 is None
        else book - prior.book_imbalance_top10
    )
    core = {
        "causal_second": second,
        "feature_available_at": available,
        "price": price_value,
        "buy_aggressor_qty_20s": buy,
        "sell_aggressor_qty_20s": sell,
        "native_signed_flow_20s": signed,
        "roll20": roll,
        "book_imbalance_top10": book,
        "price_delta_1s": price_delta,
        "roll20_delta_1s": roll_delta,
        "roll20_curvature_1s": curvature,
        "book_imbalance_delta_1s": book_delta,
        "predecessor_states": tuple(str(value) for value in predecessor_states),
        "ancestry_gap_seconds": tuple(_finite(value, "ancestry_gap_seconds") for value in ancestry_gap_seconds),
        "unresolved_age_seconds": _optional_finite(unresolved_age_seconds, "unresolved_age_seconds"),
    }
    result = GeometrySecond(**core, geometry_hash=_stable_hash(core))
    return result.validate()


class OpportunityKind(str, Enum):
    AT_RISK = "AT_RISK"
    STOPPED_CHAIN_CONTROL = "STOPPED_CHAIN_CONTROL"
    NEGATIVE_CONTROL = "NEGATIVE_CONTROL"


class ChainExtensionState(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    EXTENDING = "EXTENDING"
    STOPPED = "STOPPED"
    NO_CHAIN = "NO_CHAIN"


@dataclass(frozen=True)
class AtRiskOpportunity:
    opportunity_id: str
    run_id: str
    predecessor_ids: tuple[str, ...]
    ancestry_ids: tuple[str, ...]
    predecessor_known_by: float
    opened_at: float
    evaluated_at: float
    reveal_not_before: float
    kind: OpportunityKind
    chain_state: ChainExtensionState
    state_prefix_hash: str
    source_manifest_sha256: str
    opportunity_hash: str

    def core(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("opportunity_hash", None)
        return data

    def validate(self) -> "AtRiskOpportunity":
        _id(self.opportunity_id, "opportunity_id")
        _id(self.run_id, "run_id")
        if not self.predecessor_ids or any(not str(value).strip() for value in self.predecessor_ids):
            raise CausalDataPlaneError("opportunity requires causally known predecessor identities")
        if not self.ancestry_ids or any(not str(value).strip() for value in self.ancestry_ids):
            raise CausalDataPlaneError("opportunity requires ordered ancestry")
        known = _finite(self.predecessor_known_by, "predecessor_known_by")
        opened = _finite(self.opened_at, "opened_at")
        evaluated = _finite(self.evaluated_at, "evaluated_at")
        reveal = _finite(self.reveal_not_before, "reveal_not_before")
        if opened != known:
            raise CausalDataPlaneError("opportunity must open at predecessor_known_by")
        if not opened <= evaluated < reveal:
            raise CausalDataPlaneError("opportunity evaluation must remain before the reveal boundary")
        allowed = {
            OpportunityKind.AT_RISK: {ChainExtensionState.UNRESOLVED, ChainExtensionState.EXTENDING},
            OpportunityKind.STOPPED_CHAIN_CONTROL: {ChainExtensionState.STOPPED},
            OpportunityKind.NEGATIVE_CONTROL: {ChainExtensionState.NO_CHAIN},
        }
        if self.chain_state not in allowed[self.kind]:
            raise CausalDataPlaneError("opportunity kind/chain-extension state mismatch")
        _sha(self.state_prefix_hash, "state_prefix_hash")
        _sha(self.source_manifest_sha256, "source_manifest_sha256")
        if self.opportunity_hash != _stable_hash(self.core()):
            raise CausalDataPlaneError("opportunity hash mismatch")
        return self


def open_at_risk_opportunity(
    *,
    opportunity_id: str,
    run_id: str,
    predecessor_ids: Sequence[str],
    ancestry_ids: Sequence[str],
    predecessor_known_by: Any,
    evaluated_at: Any,
    reveal_not_before: Any,
    kind: OpportunityKind,
    chain_state: ChainExtensionState,
    state_prefix_hash: str,
    source_manifest_sha256: str,
) -> AtRiskOpportunity:
    known = _finite(predecessor_known_by, "predecessor_known_by")
    core = {
        "opportunity_id": _id(opportunity_id, "opportunity_id"),
        "run_id": _id(run_id, "run_id"),
        "predecessor_ids": tuple(_id(value, "predecessor_id") for value in predecessor_ids),
        "ancestry_ids": tuple(_id(value, "ancestry_id") for value in ancestry_ids),
        "predecessor_known_by": known,
        "opened_at": known,
        "evaluated_at": _finite(evaluated_at, "evaluated_at"),
        "reveal_not_before": _finite(reveal_not_before, "reveal_not_before"),
        "kind": OpportunityKind(kind),
        "chain_state": ChainExtensionState(chain_state),
        "state_prefix_hash": _sha(state_prefix_hash, "state_prefix_hash"),
        "source_manifest_sha256": _sha(source_manifest_sha256, "source_manifest_sha256"),
    }
    item = AtRiskOpportunity(**core, opportunity_hash=_stable_hash(core))
    return item.validate()


@dataclass(frozen=True)
class OutcomeRevealReceipt:
    schema_version: str
    opportunity_hash: str
    outcome: str
    revealed_at: float
    outcome_source_sha256: str
    receipt_hash: str

    def core(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("receipt_hash", None)
        return data

    def validate(self) -> "OutcomeRevealReceipt":
        if self.schema_version != SCHEMA_VERSION:
            raise CausalDataPlaneError("outcome receipt schema mismatch")
        _sha(self.opportunity_hash, "opportunity_hash")
        if self.outcome not in {"CHAIN_EXTENDED", "CHAIN_STOPPED", "NO_EVENT", "CENSORED"}:
            raise CausalDataPlaneError("unsupported revealed outcome")
        _finite(self.revealed_at, "revealed_at")
        _sha(self.outcome_source_sha256, "outcome_source_sha256")
        if self.receipt_hash != _stable_hash(self.core()):
            raise CausalDataPlaneError("outcome receipt hash mismatch")
        return self


def reveal_opportunity_outcome(
    opportunity: AtRiskOpportunity,
    *,
    outcome: str,
    revealed_at: Any,
    outcome_source_sha256: str,
) -> OutcomeRevealReceipt:
    opportunity.validate()
    timestamp = _finite(revealed_at, "revealed_at")
    if timestamp < opportunity.reveal_not_before:
        raise CausalDataPlaneError("outcome cannot cross the frozen reveal boundary early")
    core = {
        "schema_version": SCHEMA_VERSION,
        "opportunity_hash": opportunity.opportunity_hash,
        "outcome": str(outcome),
        "revealed_at": timestamp,
        "outcome_source_sha256": _sha(outcome_source_sha256, "outcome_source_sha256"),
    }
    receipt = OutcomeRevealReceipt(**core, receipt_hash=_stable_hash(core))
    return receipt.validate()


@dataclass(frozen=True)
class CausalDataPlaneRow:
    schema_version: str
    run_id: str
    source_object_id: str
    source_manifest_sha256: str
    crosswalk_receipt_hash: str
    clocks: ClockVector
    geometry: GeometrySecond
    opportunity: AtRiskOpportunity
    prior_row_hash: str
    row_hash: str

    def core(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("row_hash", None)
        return data

    def validate(self) -> "CausalDataPlaneRow":
        if self.schema_version != SCHEMA_VERSION:
            raise CausalDataPlaneError("data-plane schema version mismatch")
        _id(self.run_id, "run_id")
        _id(self.source_object_id, "source_object_id")
        _sha(self.source_manifest_sha256, "source_manifest_sha256")
        _sha(self.crosswalk_receipt_hash, "crosswalk_receipt_hash")
        _sha(self.prior_row_hash, "prior_row_hash")
        self.clocks.validate()
        self.geometry.validate()
        self.opportunity.validate()
        if self.run_id != self.opportunity.run_id:
            raise CausalDataPlaneError("row/opportunity run identity mismatch")
        if self.source_manifest_sha256 != self.opportunity.source_manifest_sha256:
            raise CausalDataPlaneError("row/opportunity source identity mismatch")
        if self.geometry.causal_second != self.clocks.feature_available_at:
            raise CausalDataPlaneError("geometry clock must equal row feature availability")
        if self.geometry.feature_available_at != self.clocks.feature_available_at:
            raise CausalDataPlaneError("geometry availability differs from row clocks")
        if abs(self.opportunity.evaluated_at - self.clocks.evaluated_at) > 1e-9:
            raise CausalDataPlaneError("opportunity/model evaluation clocks differ")
        if self.row_hash != _stable_hash(self.core()):
            raise CausalDataPlaneError("data-plane row hash mismatch")
        return self


def make_data_plane_row(
    *,
    run_id: str,
    source_object_id: str,
    source_manifest_sha256: str,
    crosswalk_receipt_hash: str,
    clocks: ClockVector,
    geometry: GeometrySecond,
    opportunity: AtRiskOpportunity,
    prior_row_hash: str = GENESIS,
) -> CausalDataPlaneRow:
    core = {
        "schema_version": SCHEMA_VERSION,
        "run_id": _id(run_id, "run_id"),
        "source_object_id": _id(source_object_id, "source_object_id"),
        "source_manifest_sha256": _sha(source_manifest_sha256, "source_manifest_sha256"),
        "crosswalk_receipt_hash": _sha(crosswalk_receipt_hash, "crosswalk_receipt_hash"),
        "clocks": clocks,
        "geometry": geometry,
        "opportunity": opportunity,
        "prior_row_hash": _sha(prior_row_hash, "prior_row_hash"),
    }
    row = CausalDataPlaneRow(**core, row_hash=_stable_hash({
        **core,
        "clocks": asdict(clocks),
        "geometry": asdict(geometry),
        "opportunity": asdict(opportunity),
    }))
    return row.validate()


def validate_continuous_data_plane(rows: Sequence[CausalDataPlaneRow]) -> str:
    if not rows:
        raise CausalDataPlaneError("continuous data plane cannot be empty")
    prior_hash = GENESIS
    prior_second: float | None = None
    identity = (rows[0].run_id, rows[0].source_manifest_sha256, rows[0].crosswalk_receipt_hash)
    for row in rows:
        row.validate()
        if (row.run_id, row.source_manifest_sha256, row.crosswalk_receipt_hash) != identity:
            raise CausalDataPlaneError("continuous data-plane identity drift")
        if row.prior_row_hash != prior_hash:
            raise CausalDataPlaneError("continuous data-plane hash chain broken")
        second = row.geometry.causal_second
        if prior_second is not None and abs(second - prior_second - 1.0) > 1e-9:
            raise CausalDataPlaneError("continuous data plane requires one lawful row per second")
        prior_hash = row.row_hash
        prior_second = second
    return prior_hash


@dataclass(frozen=True)
class ProtectedCausalPrefix:
    schema_version: str
    run_id: str
    opportunity_id: str
    opportunity_hash: str
    causal_cutoff: float
    event_known_by: float
    evaluated_at: float
    geometry_hash: str
    state_prefix_hash: str
    crosswalk_receipt_hash: str
    source_manifest_sha256: str
    prefix_hash: str

    def core(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("prefix_hash", None)
        return data

    def validate(self) -> "ProtectedCausalPrefix":
        if self.schema_version != SCHEMA_VERSION:
            raise CausalDataPlaneError("protected-prefix schema mismatch")
        _id(self.run_id, "run_id")
        _id(self.opportunity_id, "opportunity_id")
        for field in (
            "opportunity_hash",
            "geometry_hash",
            "state_prefix_hash",
            "crosswalk_receipt_hash",
            "source_manifest_sha256",
        ):
            _sha(getattr(self, field), field)
        cutoff = _finite(self.causal_cutoff, "causal_cutoff")
        known = _finite(self.event_known_by, "event_known_by")
        evaluated = _finite(self.evaluated_at, "evaluated_at")
        if not known <= cutoff <= evaluated:
            raise CausalDataPlaneError("protected prefix violates causal clock order")
        if self.prefix_hash != _stable_hash(self.core()):
            raise CausalDataPlaneError("protected-prefix hash mismatch")
        return self


def make_protected_prefix(
    *, row: CausalDataPlaneRow, crosswalk: SemanticCrosswalkReceipt
) -> ProtectedCausalPrefix:
    row.validate()
    crosswalk.validate()
    if row.crosswalk_receipt_hash != crosswalk.receipt_hash:
        raise CausalDataPlaneError("protected prefix attempted crosswalk substitution")
    if row.source_manifest_sha256 != crosswalk.source_manifest_sha256:
        raise CausalDataPlaneError("protected prefix attempted source substitution")
    core = {
        "schema_version": SCHEMA_VERSION,
        "run_id": row.run_id,
        "opportunity_id": row.opportunity.opportunity_id,
        "opportunity_hash": row.opportunity.opportunity_hash,
        "causal_cutoff": row.clocks.feature_available_at,
        "event_known_by": row.clocks.event_known_by,
        "evaluated_at": row.clocks.evaluated_at,
        "geometry_hash": row.geometry.geometry_hash,
        "state_prefix_hash": row.row_hash,
        "crosswalk_receipt_hash": crosswalk.receipt_hash,
        "source_manifest_sha256": row.source_manifest_sha256,
    }
    prefix = ProtectedCausalPrefix(**core, prefix_hash=_stable_hash(core))
    return prefix.validate()


@dataclass(frozen=True)
class ProspectiveDiscoveryMark:
    schema_version: str
    candidate_id: str
    detector_revision: str
    detector_source_sha256: str
    state_prefix_hash: str
    protected_prefix_hash: str
    detector_marked_at: float
    event_known_by: float
    mark_mode: str
    mark_hash: str

    def core(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("mark_hash", None)
        return data

    def validate(self) -> "ProspectiveDiscoveryMark":
        if self.schema_version != SCHEMA_VERSION:
            raise CausalDataPlaneError("prospective-mark schema mismatch")
        _id(self.candidate_id, "candidate_id")
        _id(self.detector_revision, "detector_revision")
        _sha(self.detector_source_sha256, "detector_source_sha256")
        _sha(self.state_prefix_hash, "state_prefix_hash")
        _sha(self.protected_prefix_hash, "protected_prefix_hash")
        marked = _finite(self.detector_marked_at, "detector_marked_at")
        known = _finite(self.event_known_by, "event_known_by")
        if known < marked:
            raise CausalDataPlaneError("event_known_by cannot precede detector_marked_at")
        if self.mark_mode != "PROSPECTIVE":
            raise CausalDataPlaneError("protected discovery interface permits PROSPECTIVE marks only")
        if self.mark_hash != _stable_hash(self.core()):
            raise CausalDataPlaneError("prospective-mark hash mismatch")
        return self


class ProspectiveDiscoveryMarker(Protocol):
    """Detector-owned interface; implementations receive no answer or outcome fields."""

    def mark(self, prefix: ProtectedCausalPrefix) -> ProspectiveDiscoveryMark | None: ...


def seal_prospective_mark(
    *,
    prefix: ProtectedCausalPrefix,
    candidate_id: str,
    detector_revision: str,
    detector_source_sha256: str,
    detector_marked_at: Any,
    event_known_by: Any,
) -> ProspectiveDiscoveryMark:
    prefix.validate()
    marked = _finite(detector_marked_at, "detector_marked_at")
    if marked < prefix.evaluated_at:
        raise CausalDataPlaneError("detector_marked_at cannot precede protected-prefix evaluation")
    core = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": _id(candidate_id, "candidate_id"),
        "detector_revision": _id(detector_revision, "detector_revision"),
        "detector_source_sha256": _sha(detector_source_sha256, "detector_source_sha256"),
        "state_prefix_hash": prefix.state_prefix_hash,
        "protected_prefix_hash": prefix.prefix_hash,
        "detector_marked_at": marked,
        "event_known_by": _finite(event_known_by, "event_known_by"),
        "mark_mode": "PROSPECTIVE",
    }
    mark = ProspectiveDiscoveryMark(**core, mark_hash=_stable_hash(core))
    return mark.validate()
