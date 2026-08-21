from __future__ import annotations

import copy
import pytest

from research.kalshi.frankie_meta_loop_s138 import (
    MetaLoopError,
    artifact_hash,
    attach_specialist_meta_sidecar,
    build_meta_contract,
    reconcile_specialist_meta_audits,
    validate_meta_audit,
)


def _contract(spec=None):
    return build_meta_contract(
        subject="ng exhaustion",
        specialist=spec,
        hypothesis={"claim": "continuation"},
        first_lock={"probability": 0.61, "locked": True},
        evidence={"observed": "mixed"},
        result={"pnl": -1.0},
        path_trace={"steps": ["hypothesis", "prediction", "reveal"]},
    )


def _audit(**overrides):
    row = {
        "produced_vs_found": "mixed",
        "path_soundness": "adequate",
        "contradictions": ["one counterexample"],
        "measurement_vs_market": "measurement uncertainty remains",
        "alternative_mechanisms": ["liquidity refill"],
        "missing_evidence": ["predecessor lifecycle"],
        "assumptions": ["clock is causal"],
        "claim_stances": {"continuation": "uncertain"},
        "case_disposition": "UNRESOLVED",
        "confidence_delta": -0.1,
        "next_discriminating_test": "split by predecessor lifecycle",
        "revision_proposal": {"scope": "NEXT_RUN_ONLY", "actions": ["split_hypothesis"]},
    }
    row.update(overrides)
    return row


def test_contract_binds_first_lock_and_forbids_rewrite_drop_promotion():
    c = _contract()
    assert c["activation"] == "POST_EVIDENCE_ONLY"
    assert c["bindings"]["first_lock_sha256"] == artifact_hash({"probability": 0.61, "locked": True})
    b = c["scientific_boundaries"]
    assert b["first_lock_rewrite_allowed"] is False
    assert b["case_or_chain_drop_allowed"] is False
    assert b["automatic_brain_promotion_allowed"] is False
    assert b["negative_inconclusive_sparse_cases_are_evidence"] is True


def test_validated_audit_is_next_run_only_and_preserves_case():
    out = validate_meta_audit(_contract(), _audit())
    assert out["status"] == "VALIDATED_META_AUDIT"
    assert out["case_disposition"] == "UNRESOLVED"
    assert out["first_lock_rewritten"] is False
    assert out["case_or_chain_dropped"] is False
    assert out["promotion_performed"] is False


@pytest.mark.parametrize("action", ["rewrite_first_lock", "drop_case", "drop_chain", "promote_to_brain", "automatic_apply"])
def test_forbidden_hindsight_actions_fail_closed(action):
    audit = _audit(revision_proposal={"scope": "NEXT_RUN_ONLY", "actions": [action]})
    with pytest.raises(MetaLoopError):
        validate_meta_audit(_contract(), audit)


def test_drop_disposition_is_never_valid():
    with pytest.raises(MetaLoopError):
        validate_meta_audit(_contract(), _audit(case_disposition="DROP"))


def test_specialist_sidecar_does_not_rewrite_packet():
    packet = {"causal_slice": {"d": {"x": 1}}, "brain_view_served": {"plays": {"p": {}}}}
    original = copy.deepcopy(packet)
    out = attach_specialist_meta_sidecar(packet, specialist="A")
    assert packet == original
    assert out["causal_slice"] == original["causal_slice"]
    sidecar = out["specialist_meta_loop_contract"]
    assert sidecar["activation"] == "POST_REVEAL_ONLY"
    assert sidecar["specialist_role_rewritten"] is False
    assert sidecar["blind_packet_mutation_allowed"] is False


def test_cross_specialist_reconciliation_surfaces_shared_assumption_and_disagreement():
    ca = _contract("A")
    cb = _contract("B")
    a = validate_meta_audit(ca, _audit())
    b = validate_meta_audit(cb, _audit(claim_stances={"continuation": "unlikely"}))
    out = reconcile_specialist_meta_audits([a, b])
    assert out["status"] == "SPECIALIST_META_RECONCILIATION_COMPLETE"
    assert out["shared_assumptions"] == [{"assumption": "clock is causal", "specialist_count": 2}]
    assert "continuation" in out["claim_disagreements"]
    assert out["consensus_is_truth"] is False
    assert out["majority_vote_resolution_allowed"] is False
    assert out["automatic_brain_promotion_allowed"] is False
