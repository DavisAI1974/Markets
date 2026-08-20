from __future__ import annotations
import pytest
from research.kalshi.frankie_p0_real_evidence_plan import EvidencePlanError,Partition,RECEIPTS,make_plan,validate_receipt_bundle

H=[c*64 for c in "abcdef1234567890"]

def parts():
    roles=["DEVELOPMENT_SUPPORT","CALIBRATION_FIT","CALIBRATION_EVAL","PROTECTED_RETENTION","PLANTED_NULL_HIDDEN","UNTOUCHED_FORWARD","RELEASE_HOLDOUT"]
    return tuple(Partition(f"p{i}",r,H[i],r=="DEVELOPMENT_SUPPORT") for i,r in enumerate(roles))

def plan():
    return make_plan(candidate_sha256=H[7],baseline_sha256=H[8],runner_sha256=H[9],evaluator_sha256=H[10],evaluator_canary_manifest_sha256=H[11],control_manifest_sha256=H[12],budget_manifest_sha256=H[13],seed_manifest_sha256=H[14],policy_manifest_sha256=H[15],validator_bundle_sha256=H[6],partitions=parts(),disposable_rollback_target_id="sandbox-1",rollback_baseline_sha256=H[5],external_backend_authority_id="backend-auth",evaluator_owner_id="independent-evaluator",mutation_authority_id="sandbox-mutation")

def test_hidden_and_release_partitions_cannot_be_exposed():
    with pytest.raises(EvidencePlanError): Partition("x","RELEASE_HOLDOUT",H[0],True).validate()

def test_plan_is_hash_bound_and_requires_all_partition_roles():
    p=plan(); assert len(p.plan_hash)==64
    with pytest.raises(EvidencePlanError):
        make_plan(candidate_sha256=H[7],baseline_sha256=H[8],runner_sha256=H[9],evaluator_sha256=H[10],evaluator_canary_manifest_sha256=H[11],control_manifest_sha256=H[12],budget_manifest_sha256=H[13],seed_manifest_sha256=H[14],policy_manifest_sha256=H[15],validator_bundle_sha256=H[6],partitions=parts()[:-1],disposable_rollback_target_id="sandbox",rollback_baseline_sha256=H[5],external_backend_authority_id="b",evaluator_owner_id="e",mutation_authority_id="m")

def test_bundle_refuses_synthetic_or_unexecuted_receipts():
    p=plan()
    receipts=[]
    for i,kind in enumerate(RECEIPTS):
        receipts.append({"receipt_type":kind,"plan_hash":p.plan_hash,"candidate_sha256":p.candidate_sha256,"baseline_sha256":p.baseline_sha256,"runner_sha256":p.runner_sha256,"evaluator_sha256":p.evaluator_sha256,"executed":True,"gate_passed":True,"source_validator_receipt_sha256":H[i]})
    assert validate_receipt_bundle(p,receipts)["status"]=="COMPLETE_REAL_EVIDENCE_BUNDLE"
    bad=list(receipts); bad[0]=dict(bad[0],executed=False)
    with pytest.raises(EvidencePlanError): validate_receipt_bundle(p,bad)
