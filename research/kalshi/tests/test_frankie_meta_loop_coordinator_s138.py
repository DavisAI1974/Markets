from __future__ import annotations

import pytest

from research.kalshi.frankie_meta_loop_coordinator_s138 import (
    MetaLoopError,
    build_frankie_meta_contract,
    reconcile_frankie_meta_system,
    validate_frankie_meta_audit,
)
from research.kalshi.frankie_meta_loop_s138 import (
    build_meta_contract,
    validate_meta_audit,
)


def _audit(*, stance: str = "UNRESOLVED", assumption: str = "shared coverage assumption") -> dict:
    return {
        "produced_vs_found": "mixed",
        "path_soundness": "bounded",
        "contradictions": ["counterexample"],
        "measurement_vs_market": "measurement may explain part of the difference",
        "alternative_mechanisms": ["liquidity refill"],
        "missing_evidence": ["predecessor lifecycle"],
        "assumptions": [assumption],
        "claim_stances": {"continuation": stance},
        "case_disposition": "UNRESOLVED",
        "confidence_delta": -0.1,
        "next_discriminating_test": "replay with explicit predecessor lifecycle",
        "revision_proposal": {"scope": "NEXT_RUN_ONLY", "actions": ["add_control"]},
    }


def _frankie_contract() -> dict:
    return build_frankie_meta_contract(
        subject="case-1",
        hypothesis={"claim": "continuation"},
        first_lock={"status": "FROZEN", "hash": "abc"},
        evidence={"observed": "mixed"},
        result={"outcome": "inconclusive"},
        path_trace={"steps": ["hypothesis", "first-lock", "reveal"]},
    )


def _specialist(spec: str, stance: str) -> dict:
    contract = build_meta_contract(
        subject=f"case-1-{spec}",
        hypothesis={"claim": "continuation"},
        first_lock={"status": "FROZEN", "hash": spec},
        evidence={"observed": "mixed"},
        result={"outcome": "inconclusive"},
        path_trace={"steps": ["hypothesis", "first-lock", "reveal"]},
        specialist=spec,
    )
    return validate_meta_audit(contract, _audit(stance=stance))


def test_frankie_contract_is_post_evidence_and_non_mutating():
    c = _frankie_contract()
    assert c["coordinator"] == "Frankie"
    assert c["role"] == "FRANKIE_NON_SPECIALIST_COORDINATOR"
    assert c["activation"] == "POST_EVIDENCE_ONLY"
    b = c["scientific_boundaries"]
    assert b["first_lock_rewrite_allowed"] is False
    assert b["case_or_chain_drop_allowed"] is False
    assert b["automatic_brain_promotion_allowed"] is False
    assert b["coordinator_can_majority_vote_truth"] is False


def test_frankie_audit_validates_next_run_only():
    out = validate_frankie_meta_audit(_frankie_contract(), _audit())
    assert out["status"] == "VALIDATED_META_AUDIT"
    assert out["coordinator"] == "Frankie"
    assert out["first_lock_rewritten"] is False
    assert out["case_or_chain_dropped"] is False
    assert out["automatic_apply_performed"] is False
    assert out["promotion_performed"] is False


def test_hindsight_first_lock_rewrite_is_rejected():
    bad = _audit()
    bad["revision_proposal"] = {
        "scope": "NEXT_RUN_ONLY",
        "actions": ["rewrite_first_lock"],
    }
    with pytest.raises(MetaLoopError):
        validate_frankie_meta_audit(_frankie_contract(), bad)


def test_drop_disposition_is_rejected():
    bad = _audit()
    bad["case_disposition"] = "DROP"
    with pytest.raises(MetaLoopError):
        validate_frankie_meta_audit(_frankie_contract(), bad)


def test_current_run_scope_is_rejected():
    bad = _audit()
    bad["revision_proposal"] = {"scope": "CURRENT_RUN", "actions": ["add_control"]}
    with pytest.raises(MetaLoopError):
        validate_frankie_meta_audit(_frankie_contract(), bad)


def test_system_reconciliation_surfaces_frankie_specialist_disagreement_without_vote():
    frankie = validate_frankie_meta_audit(_frankie_contract(), _audit(stance="WEAKEN"))
    a = _specialist("A", "STRENGTHEN")
    b = _specialist("B", "WEAKEN")
    out = reconcile_frankie_meta_system(frankie_audit=frankie, specialist_audits=[a, b])
    assert out["status"] == "FRANKIE_META_SYSTEM_RECONCILIATION_COMPLETE"
    assert out["specialists_present"] == ["A", "B"]
    assert out["frankie_specialist_disagreements"]
    assert out["scientific_boundaries"]["majority_vote_resolution_allowed"] is False
    assert out["scientific_boundaries"]["specialist_evidence_override_allowed"] is False
    assert out["scientific_boundaries"]["automatic_brain_promotion_allowed"] is False


def test_shared_assumption_is_exposed_not_promoted():
    frankie = validate_frankie_meta_audit(_frankie_contract(), _audit())
    a = _specialist("A", "UNRESOLVED")
    b = _specialist("B", "UNRESOLVED")
    out = reconcile_frankie_meta_system(frankie_audit=frankie, specialist_audits=[a, b])
    assert any(row["assumption"] == "shared coverage assumption" for row in out["shared_assumptions"])
    assert out["scientific_boundaries"]["automatic_apply_allowed"] is False


def test_duplicate_specialist_audit_fails_closed():
    frankie = validate_frankie_meta_audit(_frankie_contract(), _audit())
    a = _specialist("A", "UNRESOLVED")
    with pytest.raises(MetaLoopError):
        reconcile_frankie_meta_system(frankie_audit=frankie, specialist_audits=[a, a])
