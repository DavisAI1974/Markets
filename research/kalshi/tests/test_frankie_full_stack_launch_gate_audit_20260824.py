from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from research.kalshi.frankie_full_stack_launch_gate_audit_20260824 import (
    LaunchAuditInput,
    LaunchGateError,
    audit_launch_gates,
    require_launch_ready,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import LedgerKind


H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64


def passing_input() -> LaunchAuditInput:
    authority_classes = [
        "BINDING_CURRENT",
        "CURRENT_BRAIN",
        "FROZEN_LEARNED_KNOWLEDGE",
        "EXTRA_AGENT_CARRYFORWARD",
        "PROVISIONAL_SHADOW",
        "ARCHIVE_NOT_SERVABLE",
        "SEALED_TARGET_ANSWER",
    ]
    knowledge_catalog = {
        "manifest_hash": H1,
        "coverage_percent": 100,
        "authority_classes": authority_classes,
        "sources": [
            {
                "path": f"source-{index}.md",
                "sha256": H2,
                "bytes": 10 + index,
                "authority_class": authority,
                "access_policy": "SERVABLE" if "NOT_SERVABLE" not in authority else "DENIED",
            }
            for index, authority in enumerate(authority_classes)
        ],
        "s135": {
            "stack_version": "s135.current-frankie.2",
            "brain_version": "s105.9",
            "canonical_plays_total": 90,
            "full_plays_served": 90,
            "play_body_hashes": {f"play-{index:02d}": H3 for index in range(90)},
        },
        "frozen_corpus": {
            "manifest_hash": H2,
            "status": "FROZEN",
            "week_count": 55,
            "retrievable": True,
            "families": [
                "D_STRUCTURES",
                "DIPOLES",
                "CHAINS_AND_EXTENSIONS",
                "PHASE_1",
                "PHASE_2",
                "STOPPED_AND_NEGATIVE_CASES",
            ],
        },
        "access_controls": {
            "forbidden_v3": {
                "mechanically_denied": True,
                "denial_receipt_hash": H3,
                "denied_categories": [
                    "V3_TARGET_POINT_ESTIMATES",
                    "D1_EXTRATREES",
                    "EXACT_HISTORICAL_CLOCKS",
                    "FIXED_HORIZON_TRADE_FINDINGS",
                ],
            },
            "answer_wall": {
                "state": "SEALED",
                "pre_freeze_access": "DENIED",
                "step1_served": False,
                "denial_receipt_hash": H1,
            },
        },
    }
    ledger_metadata = {
        "chain_validated": True,
        "append_only": True,
        "durable_fsync": True,
        "exclusive_create": True,
        "latest_record_hash": H1,
        "record_counts": {kind.value: 1 for kind in LedgerKind},
        "retained_case_counts": {
            "weak": 2,
            "negative": 2,
            "sparse": 1,
            "ambiguous": 1,
            "contradictory": 2,
            "inconclusive": 3,
        },
    }
    helper_binding = {
        "causal_prefix_hash": H1,
        "state_prefix_hash": H2,
        "knowledge_manifest_hash": H3,
    }
    runtime_metadata = {
        "repository_safety_inventory": {
            "completed": True,
            "branch": "chatgpt/ng-exhaustion-october-sharded-20260824",
            "commit": "a" * 40,
            "worktrees_checked": True,
            "uncommitted_artifacts_preserved": True,
            "receipt_hash": H1,
        },
        "crosswalk": {
            "coverage_percent": 100,
            "coverage_receipt_hash": H2,
            "target_identities_injected": False,
            "mapped_observables": [
                "LEGACY_PRICE",
                "LEGACY_NATIVE_SIGNED_FLOW",
                "ROLL20",
                "LEGACY_BOOK_IMBALANCE",
                "PREDECESSOR_FAMILY_CHAIN",
            ],
        },
        "stream": {
            "mode": "CONTINUOUS",
            "started": True,
            "predecessor_bootstrap_verified": True,
            "complete_order_lifecycle": True,
            "artificial_resets": False,
            "message_types": ["A", "C", "M", "R", "T", "F", "N"],
            "receipt_hash": H3,
        },
        "helpers": [
            {
                "role": role,
                "active": True,
                "model": "gpt-5.6-sol",
                **helper_binding,
            }
            for role in ("recurrence", "extension", "timing", "context")
        ],
        "synthesis_authority": {
            "synthesis_owner": "FRANKIE",
            "probability_owner": "FRANKIE",
            "primary_lock_owner": "FRANKIE",
            "voting": False,
            "averaging": False,
            "automatic_consensus": False,
            "helper_lock_ids": [],
        },
        "provider_invocations": [
            {
                "task": task,
                "transport": "OPENAI_RESPONSES_API",
                "accepted": True,
                "requested_model": "gpt-5.6-sol",
                "resolved_model": "gpt-5.6-sol",
                "provider_response_id": f"resp-{index}",
                "request_hash": H1,
                "response_hash": H2,
            }
            for index, task in enumerate(
                (
                    "helper:recurrence",
                    "helper:extension",
                    "helper:timing",
                    "helper:context",
                    "frankie:synthesis",
                ),
                start=1,
            )
        ],
        "service_isolation": {
            "isolated": True,
            "service_id": "markets-frankie-october-full-stack-20260824",
            "target_start": "2021-10-01T00:00:00Z",
            "target_end": "2021-11-01T00:00:00Z",
            "permanent_services_untouched": True,
            "stop_command": "sudo systemctl stop markets-frankie-october-full-stack-20260824",
            "rollback_command": "disable the isolated unit and preserve its ledger",
        },
        "observability": {
            "live_logs": True,
            "run_url": "https://github.com/DavisAI1974/Markets/actions/runs/123456",
            "progress_event_names": [
                "FRANKIE_REPLAY_PROGRESS",
                "FRANKIE_PROVIDER_CALL_STARTED",
                "FRANKIE_PROVIDER_RESPONSE_ACCEPTED",
                "FRANKIE_PERSISTENCE_APPENDED",
                "FRANKIE_OCTOBER_PROGRESS",
                "FRANKIE_RUNTIME_ERROR",
            ],
        },
    }
    return LaunchAuditInput(knowledge_catalog, ledger_metadata, runtime_metadata)


def test_complete_report_passes_exactly_15_structured_gates_without_predictive_claims():
    report = audit_launch_gates(passing_input())
    assert report.status == "LAUNCH_GATES_PASSED"
    assert [gate.gate_id for gate in report.gates] == [f"G{index:02d}" for index in range(1, 16)]
    assert all(gate.passed and gate.evidence for gate in report.gates)
    assert report.passed_count == 15
    assert report.failed_gate_ids == ()
    assert report.predictive_success_claimed is False
    assert "not evidence of predictive success" in report.scientific_disclaimer.lower()
    assert len(report.report_hash) == 64
    require_launch_ready(report)


def _g01(inp):
    inp.runtime_metadata["repository_safety_inventory"]["completed"] = False


def _g02(inp):
    inp.knowledge_catalog["coverage_percent"] = 99


def _g03(inp):
    inp.knowledge_catalog["s135"]["full_plays_served"] = 89


def _g04(inp):
    inp.knowledge_catalog["frozen_corpus"]["retrievable"] = False


def _g05(inp):
    inp.knowledge_catalog["access_controls"]["forbidden_v3"]["mechanically_denied"] = False


def _g06(inp):
    inp.knowledge_catalog["access_controls"]["answer_wall"]["step1_served"] = True


def _g07(inp):
    inp.runtime_metadata["crosswalk"]["coverage_percent"] = 98


def _g08(inp):
    inp.runtime_metadata["stream"]["artificial_resets"] = True


def _g09(inp):
    inp.runtime_metadata["helpers"][3]["state_prefix_hash"] = H1


def _g10(inp):
    inp.runtime_metadata["synthesis_authority"]["primary_lock_owner"] = "HELPER:timing"


def _g11(inp):
    inp.runtime_metadata["provider_invocations"][4]["resolved_model"] = "gpt-5.6"


def _g12(inp):
    inp.ledger_metadata["record_counts"][LedgerKind.NO_LOCK.value] = 0


def _g13(inp):
    inp.ledger_metadata["retained_case_counts"]["weak"] = 0


def _g14(inp):
    inp.runtime_metadata["service_isolation"]["stop_command"] = ""


def _g15(inp):
    inp.runtime_metadata["observability"]["run_url"] = ""


@pytest.mark.parametrize(
    "gate_id,mutator",
    [(f"G{index:02d}", mutator) for index, mutator in enumerate(
        (_g01, _g02, _g03, _g04, _g05, _g06, _g07, _g08, _g09, _g10, _g11, _g12, _g13, _g14, _g15),
        start=1,
    )],
)
def test_each_minimum_gate_fails_closed_with_structured_evidence(gate_id, mutator):
    inp = copy.deepcopy(passing_input())
    mutator(inp)
    report = audit_launch_gates(inp)
    failed = {gate.gate_id: gate for gate in report.gates if not gate.passed}
    assert gate_id in failed
    assert failed[gate_id].evidence
    assert report.status == "LAUNCH_GATES_FAILED"
    assert report.predictive_success_claimed is False
    with pytest.raises(LaunchGateError, match=gate_id):
        require_launch_ready(report)


def test_report_hash_is_deterministic_and_does_not_alias_mutable_inputs():
    inp = passing_input()
    report = audit_launch_gates(inp)
    again = audit_launch_gates(copy.deepcopy(inp))
    assert report == again

    inp.runtime_metadata["observability"]["run_url"] = "mutated-after-audit"
    assert report.gates[-1].passed is True
    assert report.report_hash == again.report_hash

    with pytest.raises(LaunchGateError, match="REPORT_HASH"):
        require_launch_ready(replace(report, report_hash=H1))
