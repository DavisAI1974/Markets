from __future__ import annotations

import dataclasses
import pytest

from research.kalshi.ng_exhaustion_v4_pilot_chunk_guardrail import (
    ALLOWED_CLAIM,
    ChunkResult,
    ExactCandidateBinding,
    PilotGuardrailError,
    ResultLaunchAuthorization,
    downstream_handoff,
    make_manifest,
    reconcile_children,
)

H = "1" * 64
C = "2" * 40


def binding() -> ExactCandidateBinding:
    return ExactCandidateBinding(
        candidate_commit=C,
        workflow_sha256=H,
        ruleset_sha256="2" * 64,
        engine_sha256="3" * 64,
        adapter_sha256="4" * 64,
        reconciler_sha256="5" * 64,
        model_sha256="6" * 64,
        source_manifest_sha256="7" * 64,
    )


def manifest():
    return make_manifest(
        pilot_id="pilot-d2-2024",
        d_stage="D2",
        calendar_year=2024,
        start_date="2024-02-01",
        end_date="2024-03-01",
        selection_manifest_sha256="8" * 64,
        membership_manifest_sha256="9" * 64,
        parent_manifest_sha256="a" * 64,
        binding=binding(),
        selection_frozen=True,
        membership_frozen=True,
        release_holdout_consumed=False,
    )


def child(status="COMPLETE", claims=(ALLOWED_CLAIM,)) -> ChunkResult:
    m = manifest()
    return ChunkResult(
        chunk_id="D2-2024-02",
        parent_manifest_hash=m.manifest_hash,
        d_stage=m.d_stage,
        calendar_year=m.calendar_year,
        start_date=m.start_date,
        end_date=m.end_date,
        result_artifact_sha256="b" * 64,
        status=status,
        claims=claims,
    )


def test_manifest_binds_exact_candidate_and_one_d_year():
    m = manifest()
    assert m.d_stage == "D2"
    assert m.calendar_year == 2024
    assert len(m.binding.candidate_commit) == 40
    assert m.release_holdout_consumed is False


def test_cross_year_chunk_rejected():
    with pytest.raises(PilotGuardrailError):
        make_manifest(
            pilot_id="bad",
            d_stage="D1",
            calendar_year=2024,
            start_date="2024-12-20",
            end_date="2025-01-01",
            selection_manifest_sha256="8" * 64,
            membership_manifest_sha256="9" * 64,
            parent_manifest_sha256="a" * 64,
            binding=binding(),
            selection_frozen=True,
            membership_frozen=True,
            release_holdout_consumed=False,
        )


def test_release_holdout_use_rejected():
    with pytest.raises(PilotGuardrailError):
        make_manifest(
            pilot_id="bad",
            d_stage="D0",
            calendar_year=2024,
            start_date="2024-01-01",
            end_date="2024-02-01",
            selection_manifest_sha256="8" * 64,
            membership_manifest_sha256="9" * 64,
            parent_manifest_sha256="a" * 64,
            binding=binding(),
            selection_frozen=True,
            membership_frozen=True,
            release_holdout_consumed=True,
        )


def test_launch_authorization_must_match_exact_candidate_workflow_ruleset_and_manifest():
    m = manifest()
    good = ResultLaunchAuthorization(
        authorization_id="explicit-user-auth",
        candidate_commit=m.binding.candidate_commit,
        workflow_sha256=m.binding.workflow_sha256,
        ruleset_sha256=m.binding.ruleset_sha256,
        pilot_manifest_hash=m.manifest_hash,
        result_bearing_authorized=True,
    )
    assert good.validate_for(m) is good
    with pytest.raises(PilotGuardrailError):
        dataclasses.replace(good, ruleset_sha256="f" * 64).validate_for(m)
    with pytest.raises(PilotGuardrailError):
        dataclasses.replace(good, result_bearing_authorized=False).validate_for(m)


def test_child_must_reconcile_exact_parent_and_membership():
    m = manifest()
    c = child()
    c.validate_against(m)
    with pytest.raises(PilotGuardrailError):
        dataclasses.replace(c, parent_manifest_hash="f" * 64).validate_against(m)
    with pytest.raises(PilotGuardrailError):
        dataclasses.replace(c, d_stage="D3").validate_against(m)


def test_forbidden_scientific_or_trade_claim_rejected():
    m = manifest()
    with pytest.raises(PilotGuardrailError):
        child(claims=("MODEL_SUPERIORITY",)).validate_against(m)
    with pytest.raises(PilotGuardrailError):
        child(claims=("TRADE_EDGE",)).validate_against(m)


def test_completed_chunk_advances_without_aggregate_barrier():
    m = manifest()
    out = downstream_handoff(m, child())
    assert out["status"] == "READY_FOR_DOWNSTREAM"
    assert out["wait_for_other_chunks"] is False
    assert out["claim"] == ALLOWED_CLAIM


def test_blocked_chunk_does_not_block_other_chunks_by_contract():
    m = manifest()
    blocked = child(status="BLOCKED", claims=())
    out = downstream_handoff(m, blocked)
    assert out["status"] == "NOT_READY_FOR_DOWNSTREAM"
    assert out["wait_for_other_chunks"] is False


def test_reconcile_children_recomputes_parent_and_has_no_global_barrier():
    m = manifest()
    c1 = child()
    c2 = dataclasses.replace(child(status="BLOCKED", claims=()), chunk_id="D2-2024-02-b")
    out = reconcile_children(m, [c1, c2])
    assert out["ready_children"] == ["D2-2024-02"]
    assert out["nonready_children"] == ["D2-2024-02-b"]
    assert out["aggregate_barrier_required"] is False
