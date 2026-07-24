from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v2 as executor
import ng_historical_refinement_preflight_v2 as module
import ng_historical_refinement_readiness_v4 as readiness


def _make_workspace(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    root = tmp_path / "repo"
    work = root / "research" / "kalshi"
    artifacts = work / "renders" / "ng_refine_s95"
    artifacts.mkdir(parents=True)
    for relative in ("forecasts/grp15.json", "forecasts/grp16.json", "knowledge/ng_brain.json"):
        path = work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    return root, work, executor.build_plan(artifacts, work)


class GateBuilder:
    def __init__(self, root: Path, *, status: str = "ALIGNED", head: str = "1" * 40) -> None:
        self.root = root
        self.status = status
        self.head = head
        self.calls = 0

    def __call__(self, repository_path: Path, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        status = self.status
        blockers = [] if status != "BLOCKED" else ["DIRTY_SOURCE"]
        gate = {
            "schema": branch_alignment.SCHEMA,
            "market": "NG",
            "status": status,
            "observed_at": "2026-07-24T04:00:00Z",
            "repository_root": str(self.root),
            "expected_repository": branch_alignment.DEFAULT_REPOSITORY,
            "observed_remote_repository": branch_alignment.DEFAULT_REPOSITORY,
            "remote": branch_alignment.DEFAULT_REMOTE,
            "remote_url": "git@github.com:DavisAI1974/Markets.git",
            "expected_branch": branch_alignment.DEFAULT_BRANCH,
            "observed_branch": branch_alignment.DEFAULT_BRANCH,
            "detached_head": False,
            "head_sha": self.head,
            "remote_ref": f"refs/remotes/origin/{branch_alignment.DEFAULT_BRANCH}",
            "remote_ref_available": True,
            "remote_sha": self.head,
            "ahead_by": 0,
            "behind_by": 0,
            "require_remote_match": True,
            "allow_local_ahead": False,
            "allowed_dirty_prefixes": [],
            "allowed_dirty_entries": [],
            "blocked_dirty_entries": [] if status != "BLOCKED" else ["research/kalshi/source.py"],
            "blockers": blockers,
            "stand_downs": [],
            "remote_fetch_performed": False,
            "remote_presence_inferred": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_change_posterior": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "next_permitted_stage": "REPAIR_BRANCH_OR_WORKTREE" if status == "BLOCKED" else "HISTORICAL_REFINEMENT_EXECUTOR_PREFLIGHT",
        }
        gate["fingerprint"] = branch_alignment._fingerprint(gate)
        return gate


def _run(tmp_path: Path, *, gate_builder: GateBuilder | None = None, runner=None):
    root, work, plan = _make_workspace(tmp_path)
    builder = gate_builder or GateBuilder(root)
    result = module.execute_preflight(
        plan,
        root / "ledger.json",
        dry_run=True,
        gate_builder=builder,
        executor_runner=runner or (lambda *a, **k: {"status": "CONFIGURATION_REQUIRED", "stage": "corpus_coverage"}),
    )
    return root, work, plan, result


def _refingerprint(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    result.pop("fingerprint", None)
    result["fingerprint"] = module.legacy._fingerprint(result)
    return result


def test_valid_receipt_embeds_exact_v4_plan(tmp_path: Path) -> None:
    _, _, plan, result = _run(tmp_path)
    module.validate_receipt(result)
    assert result["readiness_contract"] == readiness.SCHEMA
    assert result["execution_plan_snapshot"] == plan
    assert [row["key"] for row in result["readiness_stage_contract"]] == [spec.key for spec in readiness.STAGES]
    assert "g15_counterfactual_scoring_lock" in module.STAGE_ORDER
    assert "g15_counterfactual_score_gate" in module.STAGE_ORDER
    assert "g15_counterfactual_scored_publication" in module.STAGE_ORDER


def test_legacy_plan_is_rejected_before_executor_call(tmp_path: Path) -> None:
    root, work, _ = _make_workspace(tmp_path)
    plan = legacy_executor.build_plan(work / "renders" / "ng_refine_s95", work)
    called = False

    def runner(*args: Any, **kwargs: Any):
        nonlocal called
        called = True
        return {"status": "CONFIGURATION_REQUIRED"}

    with pytest.raises(Exception):
        module.execute_preflight(plan, root / "ledger.json", gate_builder=GateBuilder(root), executor_runner=runner)
    assert called is False


def test_blocked_alignment_never_calls_executor(tmp_path: Path) -> None:
    root, work, plan = _make_workspace(tmp_path)
    called = False

    def runner(*args: Any, **kwargs: Any):
        nonlocal called
        called = True
        return {"status": "CONFIGURATION_REQUIRED"}

    result = module.execute_preflight(
        plan,
        root / "ledger.json",
        gate_builder=GateBuilder(root, status="BLOCKED"),
        executor_runner=runner,
    )
    module.validate_receipt(result)
    assert result["status"] == "BRANCH_ALIGNMENT_BLOCKED"
    assert called is False


def test_legacy_v1_receipt_is_rejected(tmp_path: Path) -> None:
    _, _, _, result = _run(tmp_path)
    legacy_receipt = module._base_receipt(result)
    with pytest.raises(module.HistoricalRefinementPreflightV2Error):
        module.validate_receipt(legacy_receipt)


def test_refingerprinted_plan_without_scoring_lock_is_rejected(tmp_path: Path) -> None:
    _, _, _, result = _run(tmp_path)
    tampered = copy.deepcopy(result)
    plan = tampered["execution_plan_snapshot"]
    plan["stages"] = [row for row in plan["stages"] if row["key"] != "g15_counterfactual_scoring_lock"]
    plan.pop("fingerprint")
    plan["fingerprint"] = module.legacy._fingerprint(plan)
    tampered["plan_fingerprint"] = plan["fingerprint"]
    tampered = _refingerprint(tampered)
    with pytest.raises(Exception):
        module.validate_receipt(tampered)


def test_refingerprinted_stage_contract_substitution_is_rejected(tmp_path: Path) -> None:
    _, _, _, result = _run(tmp_path)
    tampered = copy.deepcopy(result)
    tampered["readiness_stage_contract"] = tampered["readiness_stage_contract"][:-1]
    tampered["readiness_stage_contract_fingerprint"] = module.legacy._fingerprint(tampered["readiness_stage_contract"])
    tampered = _refingerprint(tampered)
    with pytest.raises(module.HistoricalRefinementPreflightV2Error):
        module.validate_receipt(tampered)


def test_refingerprinted_legacy_receipt_tampering_is_rejected(tmp_path: Path) -> None:
    _, _, _, result = _run(tmp_path)
    tampered = copy.deepcopy(result)
    tampered["alignment_before"]["head_sha"] = "2" * 40
    tampered = _refingerprint(tampered)
    with pytest.raises(Exception):
        module.validate_receipt(tampered)


def test_executor_stage_must_belong_to_v4(tmp_path: Path) -> None:
    with pytest.raises(module.HistoricalRefinementPreflightV2Error):
        _run(
            tmp_path,
            runner=lambda *a, **k: {"status": "CONFIGURATION_REQUIRED", "stage": "legacy_only_stage"},
        )


def test_authority_escalation_is_rejected_after_refingerprint(tmp_path: Path) -> None:
    _, _, _, result = _run(tmp_path)
    for field, value in (
        ("random_shuffle_used", True),
        ("may_update_ng_brain", True),
        ("execution_authority", True),
        ("options_lane_started", True),
        ("cme_event_contracts_mode", "LIVE"),
        ("brokerage_contract", "ibkr"),
    ):
        tampered = copy.deepcopy(result)
        tampered[field] = value
        tampered = _refingerprint(tampered)
        with pytest.raises(Exception):
            module.validate_receipt(tampered)


def test_inputs_are_immutable(tmp_path: Path) -> None:
    root, work, plan = _make_workspace(tmp_path)
    before = json.dumps(plan, sort_keys=True)
    module.execute_preflight(
        plan,
        root / "ledger.json",
        dry_run=True,
        gate_builder=GateBuilder(root),
        executor_runner=lambda *a, **k: {"status": "CONFIGURATION_REQUIRED", "stage": "corpus_coverage"},
    )
    assert json.dumps(plan, sort_keys=True) == before


def test_deterministic_contract_fields(tmp_path: Path) -> None:
    _, _, _, first = _run(tmp_path / "one")
    _, _, _, second = _run(tmp_path / "two")
    assert first["readiness_stage_contract"] == second["readiness_stage_contract"]
    assert first["readiness_stage_contract_fingerprint"] == second["readiness_stage_contract_fingerprint"]
    assert first["executor_contract"] == second["executor_contract"]


def test_fixed_outcome_flag_is_preserved_without_weakening_contract(tmp_path: Path) -> None:
    root, work, plan = _make_workspace(tmp_path)
    result = module.execute_preflight(
        plan,
        root / "ledger.json",
        allow_fixed_outcomes=True,
        dry_run=True,
        gate_builder=GateBuilder(root),
        executor_runner=lambda *a, **k: {"status": "DRY_RUN", "stage": "g15_counterfactual_score_gate"},
    )
    module.validate_receipt(result)
    assert result["fixed_outcomes_explicitly_allowed"] is True
    assert result["lock_first_g15_scoring_required"] is True
    assert result["counterfactual_g16_lineage_required"] is True
