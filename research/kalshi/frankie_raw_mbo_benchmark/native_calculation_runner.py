"""Sections 5 and 6: the seven artifact layers and the eight fail-closed gates.

The sixteen calculation modules are each correct on their own. This is what makes them a
run: it emits the layers section 5 requires, and it refuses to promote a result that fails
any gate in section 6.

Section 6's wording is "Reject the calculation rather than partially promote it". A partial
promotion is the dangerous outcome, not the loud failure - a run that emits six good layers
and one broken one looks like a success with a caveat, and the caveat is what gets lost
between here and a conclusion. So `finalize` evaluates every gate, and a single failure
makes the whole result REJECTED with the failures named; there is no partial state.

The last gate is the one that cannot be checked from inside this file, and it is stated
rather than assumed: calculation evidence is not a principal-model execution. This runner
produces evidence. It does not lock, freeze, hand off, or claim that Frankie ran.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_absorption import AbsorptionCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_book_regime import BookRegimeCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import ClockCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_detector_coverage import (
    DetectorCoverageCalculator,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_mirror import MirrorMatcher
from research.kalshi.frankie_raw_mbo_benchmark.native_dipole import DipoleCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_discovery import DiscoveryCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_exhaustion import ExhaustionCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_flow_substrate import (
    FlowSubstrateCalculator,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ladder import LadderCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_key_alias import (
    averaged_companion_layer,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_lineage import LineageCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_mbo_field_census import MboFieldCensus
from research.kalshi.frankie_raw_mbo_benchmark.native_queue import QueueSurvivalCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_recognition import RecognitionCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_recurrence import RecurrenceCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_replenishment import ReplenishmentCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_response import ResponseTableCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_session import AssignmentLedger

SCHEMA = "FRANKIE_NATIVE_RAW_MBO_CALCULATION_RESULT_V1"
CAUSAL_CLOCK = "ts_recv_ns"

ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"

LAYER_IDENTITY = "identity_receipt"
LAYER_MEMBERS = "exact_member_ledger"
LAYER_LIFECYCLE = "exact_lifecycle_and_runway_ledger"
LAYER_INDEXES = "open_world_indexes"
LAYER_AVERAGES = "averaged_companions"
LAYER_RECONCILIATION = "reconciliation_receipt"
LAYER_FINDINGS = "positive_findings_report"
REQUIRED_LAYERS = (
    LAYER_IDENTITY,
    LAYER_MEMBERS,
    LAYER_LIFECYCLE,
    LAYER_INDEXES,
    LAYER_AVERAGES,
    LAYER_RECONCILIATION,
    LAYER_FINDINGS,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_cross_section_agreement import (
    compare as cross_section_compare,
    gate_detail as cross_section_gate_detail,
)

GATE_IDENTITY = "identity"
GATE_COVERAGE = "exact_once_coverage"
GATE_ISOLATION = "arm_isolation_and_sealing"
GATE_CLOCKS = "lawful_clock_order"
GATE_DETERMINISM = "deterministic_identity_and_open_world_retention"
GATE_DENOMINATORS = "denominators_strata_and_censoring"
GATE_EXACT_UNDER_SUMMARY = "exact_members_beneath_every_summary"
GATE_NOT_A_MODEL_RUN = "calculation_evidence_is_not_model_execution"
# The ninth, and the only HORIZONTAL one. The eight above check a section against
# itself, which a one-sided book satisfies perfectly - run 33605852433 passed all eight
# while 4.9 and 4.12 computed one estimand and disagreed structurally about it.
DEFAULT_MIRROR_DISTANCE_BOUND_NS = 60 * 1_000_000_000
"""PROVISIONAL. How far apart two mirrored members may sit and still be one phenomenon.

Declared here rather than buried, because nothing measures it yet. It borrows 4.7's and
4.8's 60-second horizon on the grounds that they ask a comparable question of the same
tape, and that grounding is an analogy, not evidence. The matcher emits a near-miss
distance distribution even when it pairs nothing, so the first run that offers it members
reports what the bound should be - which is the only thing that can settle it.
"""

MIRROR_COORDINATE_NAME = "group_ts_recv_ns"
"""The axis distance is measured on. Lawful at the moment of the offer: no lookahead."""

GATE_CROSS_SECTION = "cross_section_agreement"
REQUIRED_GATES = (
    GATE_IDENTITY,
    GATE_COVERAGE,
    GATE_ISOLATION,
    GATE_CLOCKS,
    GATE_DETERMINISM,
    GATE_DENOMINATORS,
    GATE_EXACT_UNDER_SUMMARY,
    GATE_NOT_A_MODEL_RUN,
    GATE_CROSS_SECTION,
)


class CalculationRunError(ValueError):
    """The calculation run could not be assembled."""


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(frozen=True)
class RunIdentity:
    """Everything section 6's first gate requires be verifiable."""

    run_id: str
    arm: str
    mission_sha256: str
    calculation_contract_sha256: str
    knowledge_manifest_hash: str
    source_manifest_hash: str
    total_mbo_records: int
    code_commit: str

    def __post_init__(self) -> None:
        if self.arm not in ("A_CLEAN", "A_MEMORY"):
            raise CalculationRunError("arm must be A_CLEAN or A_MEMORY")
        for name in (
            "mission_sha256",
            "calculation_contract_sha256",
            "knowledge_manifest_hash",
            "source_manifest_hash",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise CalculationRunError(f"{name} must be a SHA-256")
        if self.total_mbo_records <= 0:
            raise CalculationRunError("total_mbo_records must be positive")

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "arm": self.arm,
            "mission_sha256": self.mission_sha256,
            "calculation_contract_sha256": self.calculation_contract_sha256,
            "knowledge_manifest_hash": self.knowledge_manifest_hash,
            "source_manifest_hash": self.source_manifest_hash,
            "total_mbo_records": self.total_mbo_records,
            "code_commit": self.code_commit,
        }


@dataclass
class GateResult:
    gate: str
    passed: bool
    detail: str
    # Structured evidence behind the verdict, for gates that produce any. A gate that reduces
    # its findings to a prose string hands the reader a sentence to parse instead of rows to
    # query - and a tolerated absence recorded only in prose is one nobody can count later.
    verdicts: tuple[Mapping[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        out = {"gate": self.gate, "passed": self.passed, "detail": self.detail}
        if self.verdicts:
            out["verdicts"] = [dict(v) for v in self.verdicts]
        return out


@dataclass
class CoverageLedger:
    """Exact-once accounting, the second gate's evidence."""

    records_seen: int = 0
    groups_seen: int = 0
    groups_f_last_closed: int = 0
    cursor_discontinuities: int = 0
    fifo_reconstruction_failures: int = 0
    duplicate_group_indices: int = 0
    _seen_indices: set[int] = field(default_factory=set, repr=False)
    _last_cursor: int | None = field(default=None, repr=False)

    def observe_group(self, *, group_index: int, record_count: int, f_last_closed: bool, cursor: int) -> None:
        self.groups_seen += 1
        self.records_seen += record_count
        if f_last_closed:
            self.groups_f_last_closed += 1
        if group_index in self._seen_indices:
            self.duplicate_group_indices += 1
        self._seen_indices.add(group_index)
        if self._last_cursor is not None and cursor < self._last_cursor:
            self.cursor_discontinuities += 1
        self._last_cursor = cursor

    def note_fifo_failure(self) -> None:
        self.fifo_reconstruction_failures += 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "records_seen": self.records_seen,
            "groups_seen": self.groups_seen,
            "groups_f_last_closed": self.groups_f_last_closed,
            "duplicate_group_indices": self.duplicate_group_indices,
            "cursor_discontinuities": self.cursor_discontinuities,
            "fifo_reconstruction_failures": self.fifo_reconstruction_failures,
        }


@dataclass
class IsolationLedger:
    """Third gate: arm isolation, answer-wall sealing, no later evidence."""

    other_arm_reads: int = 0
    sealed_surface_reads: int = 0
    later_evidence_reads: int = 0
    denied_access_attempts: list[dict[str, Any]] = field(default_factory=list)

    def note_denial(self, *, surface: str, reason: str) -> None:
        """A denial is a pass, and is recorded as evidence the wall was tested."""
        self.denied_access_attempts.append({"surface": surface, "reason": reason})

    def note_breach(self, kind: str) -> None:
        if kind == "OTHER_ARM":
            self.other_arm_reads += 1
        elif kind == "SEALED":
            self.sealed_surface_reads += 1
        elif kind == "LATER_EVIDENCE":
            self.later_evidence_reads += 1
        else:
            raise CalculationRunError(f"unknown isolation breach kind: {kind}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "other_arm_reads": self.other_arm_reads,
            "sealed_surface_reads": self.sealed_surface_reads,
            "later_evidence_reads": self.later_evidence_reads,
            "denied_access_attempts": list(self.denied_access_attempts),
        }


def _observation_count(value: Mapping[str, Any]) -> int:
    """How many observations a companion row stands for, whatever measure produced it.

    D60. Three measure kinds emit three different shapes and only DISTRIBUTION carries "n".
    Reading "n" alone silently valued a ratio or a survival row at zero, which understated
    the reconciliation receipt by exactly the measures whose denominators matter most.
    """
    if "n" in value:
        return int(value.get("n") or 0)
    if "total_observations" in value:
        return int(value.get("total_observations") or 0)
    nested = value.get("member_ratio_distribution")
    if isinstance(nested, Mapping):
        return int(nested.get("n") or 0)
    return 0


class NativeCalculationRun:
    """Wires the sixteen sections, emits seven layers, enforces eight gates."""

    def __init__(
        self,
        identity: RunIdentity,
        *,
        replenishment_horizon_ns: int,
        mirror_distance_bound_ns: float = DEFAULT_MIRROR_DISTANCE_BOUND_NS,
        mirror_coordinate_name: str = MIRROR_COORDINATE_NAME,
        response_horizons_ns: Sequence[int],
        response_horizon_version: str,
        response_value_names: Sequence[str],
        discovery: DiscoveryCalculator | None = None,
        exact_cap: int | None = None,
        seed: int = 0,
        session_strata: bool = True,
        sinks: Any = None,
        alias_companion_keys: bool = False,
    ) -> None:
        self.identity = identity
        # Key names are 49.5% of the averaged companions and aliasing removes about a third
        # of what the principal reads (FRANKIE_MEASURED_TOKEN_REDUCTION_20260902.md). OFF by
        # default deliberately: it changes the shape of the artifact every consumer reads,
        # and a rerun meant to be compared against 33605852433 should not carry a second
        # change at the same time. The gates never see it - they run on the unaliased rows
        # `_averaged_companions` returns, and only the serialized layer is aliased.
        self.alias_companion_keys = alias_companion_keys
        self._companions_cache: list[dict[str, Any]] | None = None
        # When present, the exact ledgers are RETAINED ON DISK instead of in RAM. Nothing is
        # dropped - see `native_row_sink`. Absent, behaviour is byte-identical to before, so
        # the two paths can be run against each other and compared.
        self.sinks = sinks
        shared: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            shared["exact_cap"] = exact_cap

        # Section 4.0, Frankie's item (a). The per-second substrate the candidate detector
        # and 4.12 consume was `traversal.legacy_per_second_roll20` - a counters block, not
        # a section: no declaration, no stratum, no denominator and no gate, which is why
        # the 51.6% NO_DIRECTION share had to be reconstructed from counters. The binning
        # clock is the DRIVER's declaration - it owns the binner this section shadows - and
        # the section adopts it before the first row (`declare_clock`), so there is exactly
        # one place the clock is set and no second one to disagree with it.
        self.flow_substrate = FlowSubstrateCalculator(**shared)
        # 4.0b. The selection function that creates the 4.10-4.12/4.16 population was in no
        # section: 91 promoted of 4,462 considered on run 33605852433, and the 4,371 rejected
        # lived in a traversal counter block nothing governed. This accounts for the detector
        # and refuses a rejection it cannot name.
        self.detector_coverage = DetectorCoverageCalculator(**shared)
        # D-4. 4.2 did not run at all, which left `book_full` - 10.13 GB, 93.47% of
        # the exact member ledger - with no consumer anywhere in the artifact.
        self.book_regime = BookRegimeCalculator(**shared)
        # D-16. The coordinate is the group's own receive time, which is lawful at the
        # moment of the offer and needs no lookahead. THE BOUND IS PROVISIONAL AND
        # DECLARED AS SUCH: 60 s matches 4.7's replenishment and 4.8's replacement
        # horizons, but no measurement establishes it for MIRRORS and none can until a
        # run reports a near-miss distance distribution - which is precisely what the
        # matcher now emits even at zero pairs. A provisional bound that produces a
        # diagnosis is strictly better than a matcher nothing calls.
        self.mirror = MirrorMatcher(
            coordinate_name=mirror_coordinate_name,
            distance_bound=mirror_distance_bound_ns,
            **shared,
        )
        self.clocks = ClockCalculator(**shared)
        self.queue = QueueSurvivalCalculator(**shared)
        self.replenishment = ReplenishmentCalculator(horizon_ns=replenishment_horizon_ns, **shared)
        self.absorption = AbsorptionCalculator(**shared)
        self.ladder = LadderCalculator(**shared)
        self.exhaustion = ExhaustionCalculator(**shared)
        self.recognition = RecognitionCalculator(**shared)
        self.dipole = DipoleCalculator(**shared)
        self.lineage = LineageCalculator(**shared)
        self.recurrence = RecurrenceCalculator(**shared)
        self.discovery = discovery
        self.response = ResponseTableCalculator(
            horizons_ns=response_horizons_ns,
            horizon_version=response_horizon_version,
            value_names=response_value_names,
            **shared,
        )

        self.coverage = CoverageLedger()
        self.isolation = IsolationLedger()
        self.sessions = AssignmentLedger()
        self.session_strata = session_strata
        self.member_rows_written = 0
        self.lifecycle_rows_written = 0
        # F-10 / mission 9a. The raw-MBO drop question was unanswerable because nothing
        # measured the retained fields themselves: which are degenerate on this slice, which
        # are always null, which are present. This walks EVERY member row the sink receives
        # and reports per field path. It is a measurement, never a recommendation (D60/D76).
        self.field_census = MboFieldCensus()
        # D60: the two exact-evidence layers of section 5 emitted COUNTS. A count is not a
        # member, and the gate that exists to guarantee exact rows beneath every summary was
        # satisfied by an integer being greater than zero. The rows live here now.
        self.member_rows: list[Mapping[str, Any]] = []
        self.lifecycle_rows: list[Mapping[str, Any]] = []
        self._findings: list[dict[str, Any]] = []
        self._principal: dict[str, Any] | None = None
        self._finalized = False

    # --- section 5 layers ------------------------------------------------

    @property
    def sections(self) -> dict[str, Any]:
        mapping = {
            # Upstream of every other section: the substrate 4.10-4.12 and the candidate
            # lane are computed from. A section absent from THIS map is dark whatever else
            # is true of it (D-4, D-16), so it is registered before it is fed anywhere.
            "4.0": self.flow_substrate,
            # 4.0b sits upstream of every candidate-unit section: it is the accounting for
            # the search that produces their population. Absent from this map it would be
            # D-4 and D-16 again - built, and dark - so it is registered first, and the
            # dark-section regression test enumerates it.
            "4.0b": self.detector_coverage,
            "4.2": self.book_regime,
            # D-16. 4.4 was absent from this map entirely - the numbering jumped 4.2 to
            # 4.5 - so even a working matcher reached neither the averages layer nor the
            # denominators gate. Exactly D-4's shape: built and invisible.
            "4.4": self.mirror,
            "4.5": self.clocks,
            "4.6": self.queue,
            "4.7": self.replenishment,
            "4.8": self.absorption,
            "4.9": self.ladder,
            "4.10": self.exhaustion,
            "4.11": self.recognition,
            "4.12": self.dipole,
            "4.13": self.lineage,
            "4.14": self.recurrence,
            "4.16": self.response,
        }
        if self.discovery is not None:
            mapping["4.15"] = self.discovery
        return mapping

    def note_session_assignment(
        self, *, ts_event_ns: int, continuity_segment: int, session_phase: str
    ) -> None:
        """Report the segment and phase this group was actually keyed on.

        Reported rather than returned, because the point is reconciliation: the ledger
        recomputes both from the group's own event time and the denominators gate fails on
        any disagreement. A traversal that supplies a constant phase is caught here and
        nowhere else - the value is present, typed and plausible at every field-level check.
        """
        self.sessions.observe(
            ts_event_ns=ts_event_ns,
            continuity_segment=continuity_segment,
            session_phase=session_phase,
        )

    def note_member_row(self, count: int = 1, *, row: Mapping[str, Any] | None = None) -> None:
        self.member_rows_written += count
        if row is None:
            return
        self.field_census.observe(row)
        if self.sinks is None:
            self.member_rows.append(row)
        else:
            self.sinks.member.write(row)

    def note_lifecycle_row(self, count: int = 1, *, row: Mapping[str, Any] | None = None) -> None:
        self.lifecycle_rows_written += count
        if row is None:
            return
        if self.sinks is None:
            self.lifecycle_rows.append(row)
        else:
            self.sinks.lifecycle.write(row)

    def add_finding(self, **_kwargs: Any) -> None:
        """Removed. The calculation layer does not author findings.

        On the first run Frankie was never called and the runner stood in for it: this
        method let whatever drove the traversal write the positive findings report, and the
        artifact finalized looking complete. The calculation layer produces EVIDENCE. The
        findings are Frankie's output, read from a committed artifact an agent session
        emitted against that evidence.
        """
        raise CalculationRunError(
            "the calculation layer does not author findings; findings come from a committed "
            "principal artifact via attach_principal_findings"
        )

    def attach_principal_findings(
        self, *, execution: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]
    ) -> None:
        """Ingest the findings a principal emitted, with the attribution that proves it ran.

        Proof is the file contract rather than a provider receipt: Sol runs as an agent
        session over committed files exactly as the blind and refine group runs did, so
        there is no provider, model id or token usage to reconcile. What there IS: a named
        principal, a committed artifact at a known path, and that artifact's hash. Absent
        any of those, this is controller work wearing Frankie's name.
        """
        if self._finalized:
            raise CalculationRunError("this run has already been finalized")
        self._check_principal_attribution(execution)
        admitted = [self._admit_finding(row) for row in findings]
        self._principal = dict(execution)
        self._findings.extend(admitted)

    @staticmethod
    def _check_principal_attribution(execution: Mapping[str, Any]) -> None:
        """The attribution a principal execution must carry, shared by both attach routes."""
        for field_name in ("principal", "artifact_path", "artifact_sha256"):
            value = execution.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise CalculationRunError(
                    f"principal attribution requires {field_name}; without it the findings "
                    "cannot be traced to anything that ran"
                )
        if execution.get("actual_principal_invocation") is not True:
            raise CalculationRunError("actual principal invocation is not proven")
        if execution.get("controller_only") is not False:
            raise CalculationRunError(
                "controller_only work cannot supply findings; that is the runner standing in "
                "for the principal, which is what this gate exists to catch"
            )

    @classmethod
    def attach_principal_findings_to_result(
        cls,
        result: Mapping[str, Any],
        *,
        execution: Mapping[str, Any],
        findings: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """The attach route for a FINISHED result (S121 slice 2, the read-back).

        A run cannot be reconstituted from its `calculation_result.json` - the sixteen
        calculators' state is not serialized - so a principal artifact that arrives after
        `finalize` has no live run to attach to. This applies the SAME attribution and
        admission checks as `attach_principal_findings`, re-evaluates the one gate whose
        verdict depends on attachment, and returns a NEW result: the findings layer filled,
        `completion_status` PRINCIPAL_FINDINGS_ATTACHED, `evidence_result_hash` naming the
        original by the hash the artifact cites, and `result_hash` recomputed over the whole.
        The mapping handed in is not mutated. A result whose hash does not recompute, or that
        already carries principal findings, is refused - a filed record is never replaced.
        """
        if not isinstance(result, Mapping) or result.get("schema") != SCHEMA:
            raise CalculationRunError(
                f"not a {SCHEMA} result; findings attach to a calculation result and nothing else"
            )
        declared = result.get("result_hash")
        recomputed = canonical_hash({k: v for k, v in result.items() if k != "result_hash"})
        if declared != recomputed:
            raise CalculationRunError(
                f"result_hash {declared!r} does not recompute ({recomputed}); a result that does "
                "not hash to itself is tampered or partial and cannot receive findings"
            )
        layer = (result.get("layers") or {}).get(LAYER_FINDINGS) or {}
        if (
            result.get("completion_status") != "EVIDENCE_ONLY"
            or layer.get("principal") is not None
            or layer.get("findings")
        ):
            raise CalculationRunError(
                f"this result already carries principal findings (completion_status "
                f"{result.get('completion_status')!r}); a filed record is never replaced"
            )
        cls._check_principal_attribution(execution)
        admitted = [cls._admit_finding(row) for row in findings]
        principal = dict(execution)

        updated = copy.deepcopy(dict(result))
        updated["layers"][LAYER_FINDINGS] = {
            "findings": admitted,
            "every_finding_carries_a_falsifier": True,
            "authored_by": "PRINCIPAL",
            "principal": principal,
        }
        updated["completion_status"] = "PRINCIPAL_FINDINGS_ATTACHED"
        gate = cls._principal_attribution_gate(admitted, principal).as_dict()
        updated["gates"] = [
            gate if g.get("gate") == GATE_NOT_A_MODEL_RUN else g for g in updated["gates"]
        ]
        updated["failed_gates"] = [g["gate"] for g in updated["gates"] if not g["passed"]]
        updated["verdict"] = REJECTED if updated["failed_gates"] else ACCEPTED
        updated["evidence_result_hash"] = declared
        updated.pop("result_hash")
        updated["result_hash"] = canonical_hash(updated)
        return updated

    @staticmethod
    def _admit_finding(row: Mapping[str, Any]) -> dict[str, Any]:
        """A finding without a falsifier is not admitted, and no status is stamped on it.

        The A-arm review found that falsifier fields were the most valued content in the
        prior run and that a live status could sit above a discharged falsifier. The
        conclusion carried here is that the FALSIFIER is the retirement mechanism, not a
        status word: a status that is the same on every row carries no information and
        invites exactly the mismatch the review found. A finding cannot be recorded without
        the thing that could retire it, and it is not pre-labelled as tentative.
        """
        if not str(row.get("falsifier", "")).strip():
            raise CalculationRunError("a finding requires a falsifier")
        if not row.get("exemplars"):
            raise CalculationRunError("a finding requires at least one exact exemplar")
        return dict(row)

    def _averaged_companions(self) -> list[dict[str, Any]]:
        """Every section's averaged rows, section-labelled.

        Cached from the first call inside `finalize`, which now asks for these six times -
        two reconciliations, the denominators gate, the cross-section gate and the averages
        layer - and rebuilding 16,293 rows each time is work done five times over on a run
        whose whole point is that it is expensive.
        """
        if self._companions_cache is not None:
            return self._companions_cache
        rows: list[dict[str, Any]] = []
        for label, section in self.sections.items():
            if not hasattr(section, "companion_rows"):
                continue
            for row in section.companion_rows():
                rows.append({**row, "section": label})
        # Only cached once the run is sealed. Before that a section can still observe more,
        # and a cache built mid-traversal would freeze a partial population under a name that
        # says otherwise.
        if self._finalized:
            self._companions_cache = rows
        return rows

    def _open_world_indexes(self) -> dict[str, Any]:
        index: dict[str, Any] = {
            "exhaustion_open_world_states": sorted(self.exhaustion.open_world_states),
            "lineage_depth_distribution": self.lineage.depth_distribution(),
            "transition_edges": self.recurrence.graph.rows(),
        }
        if self.discovery is not None:
            index["discovery"] = self.discovery.summary()
            if self.discovery.frozen:
                index["clusters"] = self.discovery.cluster_summary()
            index["unassigned_members"] = list(self.discovery.unassigned)
        return index

    def _reconciliation(self) -> dict[str, Any]:  # noqa: D401 - see _observation_count
        companions = self._averaged_companions()
        # D60: this read `.get("n", 0)` only. `RatioPair.as_dict` and
        # `SurvivalAccumulator.as_dict` carry no "n" key, so every RATIO_PAIR and SURVIVAL
        # measure contributed ZERO to the reconciliation receipt - and that receipt is the
        # evidence for the gate that exact members sit beneath every summary.
        summarized = sum(_observation_count(row["value"]) for row in companions if "value" in row)
        return {
            "averaged_rows": len(companions),
            "summarized_observations": summarized,
            "exact_member_rows": self.member_rows_written,
            "exact_lifecycle_rows": self.lifecycle_rows_written,
            "exact_members_present_beneath_summaries": self.member_rows_written > 0 or not companions,
            "session_assignment": self.sessions.as_dict(),
            "granularity_note": (
                "an averaged row's n counts observations within its own stratum and estimand; "
                "it is not expected to equal the member count, and a valid difference is a "
                "COMPLEMENTARY_SCOPE_DIFFERENCE rather than a discrepancy"
            ),
        }

    # --- section 6 gates -------------------------------------------------

    def _gate_identity(self) -> GateResult:
        try:
            self.identity.as_dict()
        except CalculationRunError as exc:  # pragma: no cover - constructor validates
            return GateResult(GATE_IDENTITY, False, str(exc))
        return GateResult(GATE_IDENTITY, True, "run, arm, mission, contract, knowledge and source identities present")

    def _gate_coverage(self) -> GateResult:
        c = self.coverage
        problems = []
        if c.groups_seen == 0:
            problems.append("no groups observed")
        if c.groups_f_last_closed != c.groups_seen:
            problems.append(f"{c.groups_seen - c.groups_f_last_closed} groups not F_LAST-closed")
        if c.duplicate_group_indices:
            problems.append(f"{c.duplicate_group_indices} duplicate group indices")
        if c.cursor_discontinuities:
            problems.append(f"{c.cursor_discontinuities} cursor discontinuities")
        if c.fifo_reconstruction_failures:
            problems.append(f"{c.fifo_reconstruction_failures} FIFO reconstruction failures")
        if c.records_seen != self.identity.total_mbo_records:
            problems.append(
                f"record coverage {c.records_seen} of {self.identity.total_mbo_records}"
            )
        return GateResult(GATE_COVERAGE, not problems, "; ".join(problems) or "exact-once coverage complete")

    def _gate_isolation(self) -> GateResult:
        i = self.isolation
        problems = []
        if i.other_arm_reads:
            problems.append(f"{i.other_arm_reads} other-arm reads")
        if i.sealed_surface_reads:
            problems.append(f"{i.sealed_surface_reads} sealed-surface reads")
        if i.later_evidence_reads:
            problems.append(f"{i.later_evidence_reads} later-evidence reads")
        detail = "; ".join(problems) or (
            f"no breaches; {len(i.denied_access_attempts)} denial(s) recorded"
        )
        return GateResult(GATE_ISOLATION, not problems, detail)

    def _gate_clocks(self) -> GateResult:
        summary = self.clocks.summary()
        if summary["causal_clock"] != CAUSAL_CLOCK:
            return GateResult(GATE_CLOCKS, False, "clock is not ts_recv_ns")
        if summary["members_seen"] == 0:
            return GateResult(GATE_CLOCKS, False, "no members were measured on the clocks")
        return GateResult(
            GATE_CLOCKS,
            True,
            f"{summary['members_seen']} members on {CAUSAL_CLOCK}; first availability is F_LAST receive time",
        )

    def _gate_determinism(self) -> GateResult:
        problems = []
        if self.queue.identity_violations:
            problems.append(f"{self.queue.identity_violations} FIFO identity violations")
        if self.discovery is not None and not self.discovery.frozen:
            problems.append("discovery is not frozen; cluster identity is not fixed")
        return GateResult(
            GATE_DETERMINISM,
            not problems,
            "; ".join(problems) or "family, lineage and cluster identities are deterministic",
        )

    def _gate_denominators(self) -> GateResult:
        problems = []
        for row in self._averaged_companions():
            declaration = row.get("declaration", {})
            for field_name in ("numerator_formula", "population", "causal_cutoff", "status", "missingness_rule"):
                if not declaration.get(field_name):
                    problems.append(f"{row.get('measure')} missing {field_name}")
                    break
        risk_rows = self.response.at_risk_table()
        if risk_rows and not all(r["denominator_is_horizon_specific"] for r in risk_rows):
            problems.append("a response horizon reused another horizon's denominator")
        if self.session_strata:
            if self.member_rows_written and not self.sessions.observed:
                problems.append(
                    "member rows were written but no session assignment was reported; "
                    "segment and phase are stratum keys and cannot go unreconciled"
                )
            if self.sessions.segment_mismatches:
                problems.append(
                    f"{len(self.sessions.segment_mismatches)} continuity_segment values "
                    "disagree with the exchange session rule"
                )
            if self.sessions.phase_mismatches:
                problems.append(
                    f"{len(self.sessions.phase_mismatches)} session_phase values disagree "
                    "with the exchange session rule; a collapsed phase stratum reads exactly "
                    "like this"
                )
        return GateResult(
            GATE_DENOMINATORS,
            not problems,
            "; ".join(problems[:5]) or "every averaged row declares its numerator, population, cutoff, status and missingness",
        )

    def _ledger_rows(self, rows: list[Mapping[str, Any]], which: str) -> dict[str, Any]:
        if self.sinks is None:
            return {"rows": list(rows), "rows_retention": "INLINE"}
        return {
            "rows_retention": "STREAMED",
            "rows_receipt": getattr(self.sinks, which).receipt(),
        }

    def _gate_exact_under_summary(self) -> GateResult:
        reconciliation = self._reconciliation()
        problems = []
        if not reconciliation["exact_members_present_beneath_summaries"]:
            problems.append("no exact member rows beneath the summaries")
        # THE CHECK THE IN-RAM VERSION NEVER HAD. `exact_members_present_beneath_summaries`
        # reads a COUNTER, so it passed just as happily when the list was empty - present,
        # typed, in range and attesting nothing. Streamed retention is reconciled against
        # the FILE, and a mismatch REJECTS rather than warning.
        if self.sinks is not None:
            for which, counted in (
                ("member", self.member_rows_written),
                ("lifecycle", self.lifecycle_rows_written),
            ):
                sink = getattr(self.sinks, which)
                if sink.rows_written != counted:
                    problems.append(
                        f"{which} retention mismatch: {counted} counted, "
                        f"{sink.rows_written} retained"
                    )
        return GateResult(
            GATE_EXACT_UNDER_SUMMARY,
            not problems,
            "; ".join(problems) or (
                f"{reconciliation['exact_member_rows']} exact member rows beneath "
                f"{reconciliation['averaged_rows']} averaged rows"
            ),
        )

    def _gate_not_a_model_run(self) -> GateResult:
        """A CHECK, not a label. It used to always return True.

        Asserting the distinction in the output is what let the first run pass with the
        runner standing in for Frankie: the statement was true of the calculation layer and
        said nothing about whether a principal had actually produced the findings above it.
        Findings present without principal attribution now REJECT the result.
        """
        return self._principal_attribution_gate(self._findings, self._principal)

    @staticmethod
    def _principal_attribution_gate(
        findings: Sequence[Mapping[str, Any]], principal: Mapping[str, Any] | None
    ) -> GateResult:
        """The one gate whose verdict depends on attachment; shared with the read-back route
        so a result attached after finalize carries the identical wording."""
        if findings and principal is None:
            return GateResult(
                GATE_NOT_A_MODEL_RUN,
                False,
                "findings are present with no principal attribution; the calculation layer "
                "has stood in for the principal, which is not the procedure",
            )
        if principal is None:
            return GateResult(
                GATE_NOT_A_MODEL_RUN,
                True,
                "evidence only; no findings claimed and no principal invocation performed "
                "here",
            )
        return GateResult(
            GATE_NOT_A_MODEL_RUN,
            True,
            f"findings attributed to {principal['principal']} via committed artifact "
            f"{principal['artifact_path']}",
        )

    def _gate_cross_section(self) -> GateResult:
        """Two sections computing one estimand must agree, or neither reading is evidence.

        This is the only gate that reads ACROSS sections. It exists because every vertical
        check the run already performs is satisfied by a section that is internally perfect
        and reading the wrong substrate; the only thing that separates it from a correct one
        is a second computation of the same quantity, which was in the same artifact and was
        never compared to it.
        """
        verdicts = cross_section_compare(self._averaged_companions())
        passed, detail = cross_section_gate_detail(verdicts)
        return GateResult(GATE_CROSS_SECTION, passed, detail, tuple(verdicts))

    def finalize(self) -> dict[str, Any]:
        """Emit all seven layers with a single accept/reject verdict.

        There is no partial promotion: one failed gate rejects the result. A run that emitted
        six sound layers and one broken one would read as a success with a caveat, and the
        caveat is what goes missing between here and a conclusion.
        """
        if self._finalized:
            raise CalculationRunError("this run has already been finalized")
        self._finalized = True

        gates = [
            self._gate_identity(),
            self._gate_coverage(),
            self._gate_isolation(),
            self._gate_clocks(),
            self._gate_determinism(),
            self._gate_denominators(),
            self._gate_exact_under_summary(),
            self._gate_not_a_model_run(),
            self._gate_cross_section(),
        ]
        failures = [g.gate for g in gates if not g.passed]

        layers = {
            LAYER_IDENTITY: {
                **self.identity.as_dict(),
                "schema": SCHEMA,
                "causal_clock": CAUSAL_CLOCK,
                "coverage": self.coverage.as_dict(),
            },
            LAYER_MEMBERS: {
                "exact_member_rows": self.member_rows_written,
                # D60: the rows themselves, not just how many there were. When a sink is in
                # use they are on disk in emission order and this carries the RECEIPT - path,
                # count, sha256, and the count read back off the file - instead of the array.
                # The key is different rather than the value being empty, because a reader
                # finding `rows: []` cannot tell retention-elsewhere from nothing-retained.
                **self._ledger_rows(self.member_rows, "member"),
                # F-10 / mission 9a: the per-field census over every member row above, so
                # the principal can judge the raw MBO from a measurement rather than from
                # counters. `rows_observed` must equal `exact_member_rows`; the emitter checks.
                "field_census": self.field_census.summary(),
                # A member counted but never censused would make the census partial while
                # it reads as complete. Emitted as a fact; the spawn emitter refuses on False.
                "field_census_covers_every_member_row": (
                    self.field_census.rows_observed == self.member_rows_written
                ),
            },
            LAYER_LIFECYCLE: {
                "exact_lifecycle_rows": self.lifecycle_rows_written,
                **self._ledger_rows(self.lifecycle_rows, "lifecycle"),
                # D60: computed inside the denominators gate, checked for one boolean and
                # discarded. It carries every horizon's OWN entered/observed/censored counts
                # per stratum - the horizon-specific denominators section 3 mandates.
                "response_at_risk_table": self.response.at_risk_table(),
                # D60: never called anywhere. Its own docstring says the detected-only figure
                # "appears here as one labelled row beside the missed and censored counts that
                # give it meaning" - and it never appeared.
                "recognition_population_report": self.recognition.population_report(),
                "section_summaries": {
                    label: section.summary()
                    for label, section in self.sections.items()
                    if hasattr(section, "summary")
                },
            },
            LAYER_INDEXES: self._open_world_indexes(),
            LAYER_AVERAGES: averaged_companion_layer(
                self._averaged_companions(), alias_keys=self.alias_companion_keys
            ),
            LAYER_RECONCILIATION: self._reconciliation(),
            LAYER_FINDINGS: {
                "findings": list(self._findings),
                "every_finding_carries_a_falsifier": True,
                "authored_by": "PRINCIPAL" if self._principal else None,
                "principal": dict(self._principal) if self._principal else None,
            },
        }
        missing = [name for name in REQUIRED_LAYERS if name not in layers]
        if missing:
            raise CalculationRunError(f"required layers missing: {missing}")

        result = {
            "schema": SCHEMA,
            "verdict": REJECTED if failures else ACCEPTED,
            "completion_status": (
                "PRINCIPAL_FINDINGS_ATTACHED" if self._principal else "EVIDENCE_ONLY"
            ),
            "failed_gates": failures,
            "gates": [g.as_dict() for g in gates],
            "isolation": self.isolation.as_dict(),
            "layers": layers,
            "partial_promotion_permitted": False,
            "verdict_note": (
                "section 6 requires rejecting the calculation rather than partially promoting "
                "it; a single failed gate rejects the whole result"
            ),
        }
        result["result_hash"] = canonical_hash(result)
        return result
