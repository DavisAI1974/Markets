#!/usr/bin/env python3
"""Frankie coordinator integration for the bounded post-evidence metacognitive loop.

This is Frankie's own non-specialist/coordinator layer. It reuses the S138
metacognitive contract and specialist reconciliation machinery but adds the
system-level reconciliation that compares Frankie's own validated self-audit
with validated A-E specialist audits.

Scientific boundary:
- post-evidence only;
- no first-lock/blind/evidence rewrite;
- no case or chain dropping;
- no specialist role rewrite;
- no automatic apply or brain promotion;
- revisions are next-run-only proposals.
"""
from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from frankie_meta_loop_s138 import (
    META_QUESTIONS,
    REVISION_SCOPE,
    SPECIALISTS,
    VERSION as META_VERSION,
    MetaLoopError,
    artifact_hash,
    build_meta_contract,
    reconcile_specialist_meta_audits,
    validate_meta_audit,
)

VERSION = "s138.frankie-coordinator-meta-loop.1"


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MetaLoopError(f"{name} must be a mapping")
    return value


def _sequence(name: str, value: Any) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise MetaLoopError(f"{name} must be a sequence")
    return value


def build_frankie_meta_contract(
    *,
    subject: str,
    hypothesis: Mapping[str, Any],
    first_lock: Mapping[str, Any],
    evidence: Mapping[str, Any],
    result: Mapping[str, Any],
    path_trace: Mapping[str, Any],
) -> dict[str, Any]:
    """Build Frankie's own immutable post-evidence audit contract."""
    contract = build_meta_contract(
        subject=subject,
        hypothesis=hypothesis,
        first_lock=first_lock,
        evidence=evidence,
        result=result,
        path_trace=path_trace,
        specialist=None,
    )
    contract = copy.deepcopy(contract)
    contract["coordinator"] = "Frankie"
    contract["coordinator_meta_version"] = VERSION
    contract["role"] = "FRANKIE_NON_SPECIALIST_COORDINATOR"
    contract["activation"] = "POST_EVIDENCE_ONLY"
    contract["scientific_boundaries"]["coordinator_can_override_specialist_evidence"] = False
    contract["scientific_boundaries"]["coordinator_can_majority_vote_truth"] = False
    contract["scientific_boundaries"]["coordinator_can_rewrite_own_first_lock"] = False
    contract["contract_sha256"] = artifact_hash({k: v for k, v in contract.items() if k != "contract_sha256"})
    return contract


def validate_frankie_meta_audit(
    contract: Mapping[str, Any], audit: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate Frankie's own self-audit against its immutable bindings."""
    contract = _mapping("contract", contract)
    if contract.get("specialist") is not None:
        raise MetaLoopError("Frankie coordinator audit cannot use a specialist contract")
    if contract.get("coordinator") != "Frankie":
        raise MetaLoopError("Frankie coordinator contract missing coordinator identity")
    if contract.get("coordinator_meta_version") != VERSION:
        raise MetaLoopError("unsupported Frankie coordinator meta-loop version")

    # The base validator expects the S138 version but otherwise validates the
    # same immutable artifact bindings and next-run-only boundary.
    base_contract = copy.deepcopy(dict(contract))
    base_contract.pop("coordinator", None)
    base_contract.pop("coordinator_meta_version", None)
    base_contract.pop("role", None)
    base_contract["version"] = META_VERSION
    base_contract["contract_sha256"] = artifact_hash(
        {k: v for k, v in base_contract.items() if k != "contract_sha256"}
    )

    validated = validate_meta_audit(base_contract, audit)
    validated = copy.deepcopy(validated)
    validated["coordinator"] = "Frankie"
    validated["role"] = "FRANKIE_NON_SPECIALIST_COORDINATOR"
    validated["coordinator_meta_version"] = VERSION
    validated["automatic_apply_performed"] = False
    validated["promotion_performed"] = False
    validated["first_lock_rewritten"] = False
    validated["case_or_chain_dropped"] = False
    validated["meta_audit_sha256"] = artifact_hash(
        {k: v for k, v in validated.items() if k != "meta_audit_sha256"}
    )
    return validated


def reconcile_frankie_meta_system(
    *,
    frankie_audit: Mapping[str, Any],
    specialist_audits: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Reconcile Frankie's self-audit with A-E without voting or erasing evidence."""
    frankie_audit = _mapping("frankie_audit", frankie_audit)
    if frankie_audit.get("status") != "VALIDATED_META_AUDIT":
        raise MetaLoopError("Frankie system reconciliation requires a validated Frankie audit")
    if frankie_audit.get("coordinator") != "Frankie":
        raise MetaLoopError("Frankie audit lacks coordinator identity")
    if frankie_audit.get("specialist") is not None:
        raise MetaLoopError("Frankie coordinator audit cannot be a specialist audit")

    specialist_audits = tuple(_sequence("specialist_audits", specialist_audits))
    specialist_summary = None
    if specialist_audits:
        specialist_summary = reconcile_specialist_meta_audits(specialist_audits)

    assumptions = Counter(str(x).strip() for x in frankie_audit.get("assumptions", ()) if str(x).strip())
    missing = {str(x).strip() for x in frankie_audit.get("missing_evidence", ()) if str(x).strip()}
    specialist_stances: dict[str, dict[str, str]] = {}
    shared_with_frankie: list[dict[str, Any]] = []

    if specialist_summary:
        for row in specialist_summary.get("shared_assumptions", ()):
            text = str(row.get("assumption", "")).strip()
            if text:
                assumptions[text] += int(row.get("specialist_count", 0))
        missing.update(str(x).strip() for x in specialist_summary.get("missing_evidence_union", ()) if str(x).strip())
        specialist_stances = copy.deepcopy(specialist_summary.get("claim_disagreements", {}))

    frankie_claims = {str(k): str(v) for k, v in dict(frankie_audit.get("claim_stances", {})).items()}
    for claim, by_spec in specialist_stances.items():
        fstance = frankie_claims.get(claim)
        if fstance is None:
            continue
        all_stances = {fstance, *by_spec.values()}
        if len(all_stances) > 1:
            shared_with_frankie.append(
                {
                    "claim": claim,
                    "frankie": fstance,
                    "specialists": dict(sorted(by_spec.items())),
                    "status": "UNRESOLVED_DISAGREEMENT",
                }
            )

    system = {
        "version": VERSION,
        "status": "FRANKIE_META_SYSTEM_RECONCILIATION_COMPLETE",
        "frankie_audit_sha256": frankie_audit.get("meta_audit_sha256"),
        "specialist_reconciliation_sha256": (
            specialist_summary.get("reconciliation_sha256") if specialist_summary else None
        ),
        "specialists_present": specialist_summary.get("specialists", []) if specialist_summary else [],
        "frankie_specialist_disagreements": shared_with_frankie,
        "shared_assumptions": [
            {"assumption": text, "participant_count": count}
            for text, count in sorted(assumptions.items())
            if count >= 2
        ],
        "missing_evidence_union": sorted(missing),
        "frankie_next_discriminating_test": frankie_audit.get("next_discriminating_test"),
        "frankie_revision_proposal": copy.deepcopy(frankie_audit.get("revision_proposal")),
        "meta_questions": list(META_QUESTIONS),
        "revision_scope": REVISION_SCOPE,
        "scientific_boundaries": {
            "first_lock_rewrite_allowed": False,
            "blind_or_evidence_mutation_allowed": False,
            "case_or_chain_drop_allowed": False,
            "majority_vote_resolution_allowed": False,
            "specialist_evidence_override_allowed": False,
            "automatic_apply_allowed": False,
            "automatic_brain_promotion_allowed": False,
            "next_run_revision_only": True,
        },
    }
    system["system_reconciliation_sha256"] = artifact_hash(system)
    return system


def selftest() -> None:
    z = "0" * 64
    contract = build_frankie_meta_contract(
        subject="demo",
        hypothesis={"claim": "candidate continuation"},
        first_lock={"lock": "frozen", "sha": z},
        evidence={"observation": "mixed"},
        result={"outcome": "inconclusive"},
        path_trace={"steps": ["hypothesis", "lock", "reveal"]},
    )
    audit = {
        "produced_vs_found": "mixed",
        "path_soundness": "bounded",
        "contradictions": ["counterexample"],
        "measurement_vs_market": "measurement may explain part of the difference",
        "alternative_mechanisms": ["liquidity refill"],
        "missing_evidence": ["predecessor lifecycle"],
        "assumptions": ["book coverage is representative"],
        "claim_stances": {"continuation": "UNRESOLVED"},
        "case_disposition": "UNRESOLVED",
        "confidence_delta": -0.1,
        "next_discriminating_test": "replay with explicit predecessor lifecycle",
        "revision_proposal": {"scope": "NEXT_RUN_ONLY", "actions": ["add_control"]},
    }
    validated = validate_frankie_meta_audit(contract, audit)
    system = reconcile_frankie_meta_system(frankie_audit=validated, specialist_audits=[])
    assert system["status"] == "FRANKIE_META_SYSTEM_RECONCILIATION_COMPLETE"
    assert system["scientific_boundaries"]["automatic_brain_promotion_allowed"] is False


if __name__ == "__main__":
    selftest()
    print("FRANKIE COORDINATOR META LOOP SELFTEST PASS")
