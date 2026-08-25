"""
Decision contract: typed heads -> calibration -> constrained decode -> validation.

This is the M -> V -> J segment. It is deliberately framework-agnostic:
heads hand over plain numbers, so this layer is fully testable before the
trunk exists and cannot be broken by a torch upgrade.

The design resolves the branch that was unspecified in the architecture
diagram -- what the validator does on contract failure.

    REJECT  -> emit a typed abstention. Never raise into the caller,
               never emit a partial decision.
    REPAIR  -> permitted only via pure, total, declared repair functions.
               A repair that is not declared in the schema cannot run.
    RETRY   -> forbidden. There is nothing to retry: decode is a
               projection of typed head outputs, not sampling, so a
               second attempt on identical inputs is identical by
               construction. A retry that could differ would mean a
               hidden nondeterminism source, and that is a bug to find,
               not a condition to paper over.

Determinism is structural rather than promised. Because the heads are
typed, decoding is projection, not generation: there is no sampler, no
temperature, no token loop. Given (head outputs, calibrator version,
schema version) the emitted JSON is a pure function.

Abstention is a first-class output, not an error path. Every abstention
carries a machine-readable reason and the same stamp a decision would
carry, so the evidence graph sees refusals and emissions on equal
footing. A system that logs only its answers cannot be audited on the
questions it declined.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Protocol, Sequence

__all__ = [
    "FieldKind",
    "FieldSpec",
    "DecisionSchema",
    "HeadOutput",
    "Calibrator",
    "IdentityCalibrator",
    "Decision",
    "Abstention",
    "ContractViolation",
    "DecisionEngine",
    "ShadowDiff",
    "shadow_compare",
]

CONTRACT_VERSION = "decision_contract/1"


class FieldKind(str, Enum):
    PROBABILITY = "probability"  # [0, 1]
    MAGNITUDE = "magnitude"      # real, optionally bounded
    REGIME = "regime"            # categorical, closed set
    CONTRADICTION = "contradiction"  # [0, 1], high = heads disagree
    EVIDENCE = "evidence"        # pointers into the packet
    UNCERTAINTY = "uncertainty"  # [0, inf)


class AbstainReason(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    HIGH_CONTRADICTION = "high_contradiction"
    DEGRADED_PACKET = "degraded_packet"
    CONTRACT_VIOLATION = "contract_violation"
    UNRESOLVED_EVIDENCE = "unresolved_evidence"


class ContractViolation(Exception):
    """Internal signal. Never escapes the engine -- becomes an abstention."""

    def __init__(self, field_name: str, detail: str):
        self.field_name = field_name
        self.detail = detail
        super().__init__(f"{field_name}: {detail}")


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

RepairFn = Callable[[Any], Any]


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """One field of the output contract.

    repair, if given, must be pure and total: same input -> same output,
    never raises, defined on every value the head can emit. It runs
    BEFORE validation. If validation still fails afterwards, the decision
    abstains -- repair gets exactly one shot and cannot loop.
    """

    name: str
    kind: FieldKind
    required: bool = True
    choices: tuple[str, ...] = ()
    lo: float | None = None
    hi: float | None = None
    repair: RepairFn | None = None

    def __post_init__(self) -> None:
        if self.kind is FieldKind.REGIME and not self.choices:
            raise ValueError(f"{self.name}: regime field needs a closed choice set")
        if self.kind is FieldKind.PROBABILITY and (self.lo, self.hi) != (None, None):
            raise ValueError(f"{self.name}: probability bounds are fixed at [0,1]")

    def bounds(self) -> tuple[float | None, float | None]:
        if self.kind in (FieldKind.PROBABILITY, FieldKind.CONTRADICTION):
            return 0.0, 1.0
        if self.kind is FieldKind.UNCERTAINTY:
            return 0.0, self.hi
        return self.lo, self.hi

    def validate(self, value: Any) -> Any:
        if self.kind is FieldKind.REGIME:
            if not isinstance(value, str):
                raise ContractViolation(self.name, f"regime must be str, got {type(value).__name__}")
            if value not in self.choices:
                raise ContractViolation(self.name, f"{value!r} outside closed set {self.choices}")
            return value

        if self.kind is FieldKind.EVIDENCE:
            if not isinstance(value, (list, tuple)) or not all(
                isinstance(v, str) for v in value
            ):
                raise ContractViolation(self.name, "evidence must be a list of str keys")
            return list(value)

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ContractViolation(self.name, f"expected number, got {type(value).__name__}")
        v = float(value)
        if v != v:  # NaN
            raise ContractViolation(self.name, "NaN is not a decision")
        if v in (float("inf"), float("-inf")):
            raise ContractViolation(self.name, "infinite value")
        lo, hi = self.bounds()
        if lo is not None and v < lo:
            raise ContractViolation(self.name, f"{v} below lower bound {lo}")
        if hi is not None and v > hi:
            raise ContractViolation(self.name, f"{v} above upper bound {hi}")
        return v


@dataclass(frozen=True, slots=True)
class DecisionSchema:
    """The exact output contract. Must match Frankie's expected shape.

    version is stamped into every emission. Change the contract, bump the
    version, or shadow diffs against Frankie become meaningless.
    """

    version: str
    fields: tuple[FieldSpec, ...]

    def by_name(self) -> dict[str, FieldSpec]:
        return {f.name: f for f in self.fields}

    def field_of_kind(self, kind: FieldKind) -> FieldSpec | None:
        for f in self.fields:
            if f.kind is kind:
                return f
        return None


# --------------------------------------------------------------------------
# Heads and calibration
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HeadOutput:
    """Raw typed-head output. Plain numbers -- no tensors cross this line."""

    values: Mapping[str, Any]
    packet_hash: str
    model_version: str


class Calibrator(Protocol):
    """Maps raw head outputs to calibrated ones, and sets abstention gates.

    version MUST be stamped into the packet (see PacketStamp.calibrator_version).
    An adaptive calibrator outside the signed registry is a live mutable
    input to the decision; if it is unversioned, calibrator drift and model
    drift are indistinguishable in the audit.
    """

    version: str

    def calibrate(self, values: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def min_confidence(self) -> float: ...

    def max_contradiction(self) -> float: ...


@dataclass(frozen=True, slots=True)
class IdentityCalibrator:
    """Baseline. Emits inputs unchanged with fixed gates."""

    version: str = "identity/1"
    confidence_floor: float = 0.55
    contradiction_ceiling: float = 0.35

    def calibrate(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(values)

    def min_confidence(self) -> float:
        return self.confidence_floor

    def max_contradiction(self) -> float:
        return self.contradiction_ceiling


# --------------------------------------------------------------------------
# Emissions
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Decision:
    payload: Mapping[str, Any]
    packet_hash: str
    model_version: str
    calibrator_version: str
    schema_version: str
    repaired_fields: tuple[str, ...] = ()
    contract_version: str = CONTRACT_VERSION

    @property
    def abstained(self) -> bool:
        return False

    def to_json(self) -> str:
        return json.dumps(
            {
                "abstained": False,
                "payload": dict(sorted(self.payload.items())),
                "stamp": {
                    "packet_hash": self.packet_hash,
                    "model_version": self.model_version,
                    "calibrator_version": self.calibrator_version,
                    "schema_version": self.schema_version,
                    "contract_version": self.contract_version,
                },
                "repaired_fields": list(self.repaired_fields),
            },
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class Abstention:
    reason: AbstainReason
    detail: str
    packet_hash: str
    model_version: str
    calibrator_version: str
    schema_version: str
    contract_version: str = CONTRACT_VERSION

    @property
    def abstained(self) -> bool:
        return True

    def to_json(self) -> str:
        return json.dumps(
            {
                "abstained": True,
                "reason": self.reason.value,
                "detail": self.detail,
                "stamp": {
                    "packet_hash": self.packet_hash,
                    "model_version": self.model_version,
                    "calibrator_version": self.calibrator_version,
                    "schema_version": self.schema_version,
                    "contract_version": self.contract_version,
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        )


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------


class DecisionEngine:
    """Deterministic projection from head outputs to strict JSON.

    Never raises on bad head output. A malformed head produces a stamped
    abstention, because an exception at this boundary means the caller
    decides what to do with a half-formed decision, and that decision
    belongs here.
    """

    def __init__(
        self,
        schema: DecisionSchema,
        calibrator: Calibrator,
        require_evidence_in_packet: bool = True,
    ):
        self.schema = schema
        self.calibrator = calibrator
        self.require_evidence_in_packet = require_evidence_in_packet

    def _abstain(
        self, reason: AbstainReason, detail: str, head: HeadOutput
    ) -> Abstention:
        return Abstention(
            reason=reason,
            detail=detail,
            packet_hash=head.packet_hash,
            model_version=head.model_version,
            calibrator_version=self.calibrator.version,
            schema_version=self.schema.version,
        )

    def decide(
        self,
        head: HeadOutput,
        packet_keys: Sequence[str] = (),
        packet_degraded: Sequence[str] = (),
    ) -> Decision | Abstention:
        if packet_degraded:
            return self._abstain(
                AbstainReason.DEGRADED_PACKET, "; ".join(packet_degraded), head
            )

        raw = self.calibrator.calibrate(head.values)
        specs = self.schema.by_name()
        payload: dict[str, Any] = {}
        repaired: list[str] = []

        for name, spec in specs.items():
            if name not in raw:
                if spec.required:
                    return self._abstain(
                        AbstainReason.CONTRACT_VIOLATION,
                        f"{name}: required field absent from head output",
                        head,
                    )
                continue

            value = raw[name]
            try:
                payload[name] = spec.validate(value)
            except ContractViolation as first:
                if spec.repair is None:
                    return self._abstain(
                        AbstainReason.CONTRACT_VIOLATION, str(first), head
                    )
                # Repair gets exactly one attempt. No loop, no retry.
                repair_fn = spec.repair
                if not callable(repair_fn):
                    # Explicit guard. Previously this path abstained only
                    # because calling None raised TypeError into the
                    # catch-all below -- correct behaviour by accident.
                    return self._abstain(
                        AbstainReason.CONTRACT_VIOLATION,
                        f"{name}: repair is not callable ({type(repair_fn).__name__})",
                        head,
                    )
                try:
                    fixed = repair_fn(value)
                    payload[name] = spec.validate(fixed)
                    repaired.append(name)
                except ContractViolation as second:
                    return self._abstain(
                        AbstainReason.CONTRACT_VIOLATION,
                        f"repair failed: {second}",
                        head,
                    )
                except Exception as exc:  # repair was not total
                    return self._abstain(
                        AbstainReason.CONTRACT_VIOLATION,
                        f"{name}: repair function raised {type(exc).__name__}",
                        head,
                    )

        unknown = set(raw) - set(specs)
        if unknown:
            return self._abstain(
                AbstainReason.CONTRACT_VIOLATION,
                f"head emitted fields outside contract: {sorted(unknown)}",
                head,
            )

        # Evidence pointers must resolve into the packet that produced this
        # decision. An unresolvable pointer means the audit trail is broken,
        # which is worse than no decision.
        ev_spec = self.schema.field_of_kind(FieldKind.EVIDENCE)
        if ev_spec is not None and self.require_evidence_in_packet:
            pointers = payload.get(ev_spec.name, [])
            dangling = [p for p in pointers if p not in set(packet_keys)]
            if dangling:
                return self._abstain(
                    AbstainReason.UNRESOLVED_EVIDENCE,
                    f"pointers absent from packet: {sorted(dangling)}",
                    head,
                )

        # Gates last: a decision must be well-formed before it is judged
        # confident, otherwise a malformed field can pass by being loud.
        contra = self.schema.field_of_kind(FieldKind.CONTRADICTION)
        if contra is not None and contra.name in payload:
            if payload[contra.name] > self.calibrator.max_contradiction():
                return self._abstain(
                    AbstainReason.HIGH_CONTRADICTION,
                    f"{contra.name}={payload[contra.name]} > "
                    f"{self.calibrator.max_contradiction()}",
                    head,
                )

        prob = self.schema.field_of_kind(FieldKind.PROBABILITY)
        if prob is not None and prob.name in payload:
            conf = abs(payload[prob.name] - 0.5) * 2.0
            if conf < self.calibrator.min_confidence():
                return self._abstain(
                    AbstainReason.LOW_CONFIDENCE,
                    f"confidence {conf:.4f} < {self.calibrator.min_confidence()}",
                    head,
                )

        return Decision(
            payload=payload,
            packet_hash=head.packet_hash,
            model_version=head.model_version,
            calibrator_version=self.calibrator.version,
            schema_version=self.schema.version,
            repaired_fields=tuple(sorted(repaired)),
        )


# --------------------------------------------------------------------------
# Shadow harness
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShadowDiff:
    """One packet's worth of new-path vs Frankie comparison."""

    packet_hash: str
    agreed: bool
    new_abstained: bool
    frankie_abstained: bool
    field_deltas: Mapping[str, float] = field(default_factory=dict)
    mismatched: tuple[str, ...] = ()
    note: str = ""


def shadow_compare(
    emitted: Decision | Abstention,
    frankie: Mapping[str, Any] | None,
    schema: DecisionSchema,
    tol: float = 1e-9,
) -> ShadowDiff:
    """Compare an emission against live Frankie output.

    frankie=None means Frankie itself declined to act.

    Abstention asymmetry is reported, never scored as agreement. The new
    path abstaining where Frankie acted is a different failure from the
    reverse, and collapsing them into one number hides which way the
    system is wrong.
    """
    new_abst = emitted.abstained
    frankie_abst = frankie is None

    if new_abst or frankie_abst:
        return ShadowDiff(
            packet_hash=emitted.packet_hash,
            agreed=(new_abst and frankie_abst),
            new_abstained=new_abst,
            frankie_abstained=frankie_abst,
            note=(
                "both abstained"
                if new_abst and frankie_abst
                else "new path abstained, Frankie acted"
                if new_abst
                else "Frankie abstained, new path acted"
            ),
        )

    assert isinstance(emitted, Decision) and frankie is not None
    deltas: dict[str, float] = {}
    mismatched: list[str] = []

    for spec in schema.fields:
        if spec.name not in emitted.payload or spec.name not in frankie:
            mismatched.append(spec.name)
            continue
        a, b = emitted.payload[spec.name], frankie[spec.name]
        if spec.kind in (FieldKind.REGIME, FieldKind.EVIDENCE):
            if a != b:
                mismatched.append(spec.name)
        else:
            d = abs(float(a) - float(b))
            deltas[spec.name] = d
            if d > tol:
                mismatched.append(spec.name)

    return ShadowDiff(
        packet_hash=emitted.packet_hash,
        agreed=not mismatched,
        new_abstained=False,
        frankie_abstained=False,
        field_deltas=deltas,
        mismatched=tuple(sorted(mismatched)),
    )
