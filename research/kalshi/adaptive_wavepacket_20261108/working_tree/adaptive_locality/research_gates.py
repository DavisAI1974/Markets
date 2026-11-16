"""Explicit unfinished scientific acceptance gates; nothing unverified is lost.

These are *research requirements*, not missing observations, validated laws,
or permission to omit science. They are retained as source-bound statements
with future review permitted, never automatically promoted to VERIFIED.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict

from .core import LocalityError, _digest
from .research_holds import ResearchHoldRegistry


@dataclass(frozen=True)
class ScienceReviewGate:
    gate_id: str
    status: str
    reason: str
    required_evidence: str


UNVERIFIED_GATES: tuple[ScienceReviewGate, ...] = (
    ScienceReviewGate(
        "independent-replication","UNVERIFIED",
        "Synthetic seeds and overlapping time splits are not independent scientific replication.",
        "Different source, sampling regime, calibration and independently fixed holdout."),
    ScienceReviewGate(
        "causal-controls","UNVERIFIED",
        "Predictive associations may reflect common drivers, feedback, multiple testing or regime drift.",
        "Domain-defined causal clocks, confound controls and multiplicity-aware replication."),
    ScienceReviewGate(
        "algebraic-novelty","UNVERIFIED",
        "Equal entropy and constant-donor quadratic curves can be exact algebraic artifacts.",
        "Evidence of incremental out-of-sample target prediction beyond nested linear interaction."),
    ScienceReviewGate(
        "rank-conditioning","UNVERIFIED",
        "Rank and numerical conditioning must be independently examined at multiple precisions.",
        "Condition spectra, perturbation sensitivity and independently verified estimators."),
    ScienceReviewGate(
        "parameter-fisher-information","UNVERIFIED",
        "Frozen-bin Fisher-like roughness is not parameter Fisher information.",
        "Explicit parameter, likelihood and estimator with independent calibration."),
    ScienceReviewGate(
        "physical-neumann-boundary","UNVERIFIED",
        "Operator-space points do not identify a physical continuum domain or normals.",
        "Well-defined domain, normals, PDE operator and consistency/stability analysis."),
    ScienceReviewGate(
        "raw-external-validation","UNVERIFIED",
        "Synthetic RawFrame retention is not real independent source validation.",
        "Complete source-bound original measurements and independent scientific review."),
    ScienceReviewGate(
        "scientific-equivalence","UNVERIFIED",
        "No proof that two different scientific calculations are interchangeable exists.",
        "Separately authorized equivalence proof including direction, causal history and side effects."),
)


def preserve_unverified_gates(registry: ResearchHoldRegistry, *,
                              archive_name: str,
                              gates: tuple[ScienceReviewGate, ...]=UNVERIFIED_GATES) -> dict:
    """Persist EVERY gate and link EACH unverified requirement to a research hold.

    All entries remain in the archive regardless of status. Only explicitly
    UNVERIFIED/INCONCLUSIVE/CONFLICTING/UNDER_REVIEW states are supported;
    there is intentionally no silent auto-acceptance route in this interface.
    The registry labels them RESEARCH_HOLD until a human review is recorded.
    """
    gates=tuple(gates)
    allowed={"UNVERIFIED","INCONCLUSIVE","CONFLICTING","UNDER_REVIEW"}
    if (not archive_name or not gates or
        any(not isinstance(g,ScienceReviewGate) or
            not g.gate_id or not g.reason or not g.required_evidence or
            g.status not in allowed for g in gates) or
        len({g.gate_id for g in gates})!=len(gates)):
        raise LocalityError("all unverified scientific gates require distinct reasons/evidence")
    digest=registry.archive(archive_name,gates)
    case_ids=[]
    for gate in gates:
        case_id=_digest({"archive":digest,"gate":gate.gate_id,
                         "status":gate.status,"reason":gate.reason})
        registry.hold(case_id,archive_name,
                      reason="UNVERIFIED_SCIENTIFIC_GATE:"+gate.gate_id,
                      details={**asdict(gate),"archive_digest":digest,
                               "disposition":"RETAIN_FOR_FURTHER_INSPECTION"})
        case_ids.append(case_id)
    return {"archive_name":archive_name,"archive_digest":digest,
            "retained_gate_count":len(gates),"unverified_case_count":len(case_ids),
            "research_case_ids":tuple(case_ids),"gates_dropped":0,
            "scientific_jobs_eliminated":0}
