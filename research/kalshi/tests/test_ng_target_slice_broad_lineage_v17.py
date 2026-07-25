from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v13 as compiler
import ng_historical_refinement_executor_v14 as executor
import ng_historical_refinement_preflight_v14 as preflight
import ng_historical_refinement_readiness_v17 as readiness
import ng_target_slice_broad_lineage_gate as lineage


def _definition(*, lane: str, suffix: str = "") -> dict[str, object]:
    return {
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": 996,
        "raw_symbol": "NGK26",
        "definition_date": "20260330",
        "definition_start_s": 0.0,
        "definition_end_s": 100.0,
        "source_sha256": ("a" if lane == "l1_trades" else "b") * 64,
        "source_size_bytes": 100 if lane == "l1_trades" else 200,
        "definition_fingerprint": f"definition-{lane}{suffix}",
    }


def _gate_inputs(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(lineage.slicer, "_target_days", lambda: ("20260330",))
    monkeypatch.setattr(
        lineage.inspection,
        "validate_definition",
        lambda value: copy.deepcopy(dict(value)),
    )
    monkeypatch.setattr(lineage.broad_binding, "validate_gate", lambda value: copy.deepcopy(dict(value)))
    monkeypatch.setattr(lineage.basis, "_validate_slice_envelope", lambda value: copy.deepcopy(dict(value)))
    monkeypatch.setattr(lineage.inspection, "validate_receipt", lambda value: copy.deepcopy(dict(value)))
    monkeypatch.setattr(lineage.basis, "_validate_entry_against_candidate", lambda *args, **kwargs: None)

    candidates: dict[tuple[str, str], dict[str, object]] = {}
    entries: dict[str, dict[str, object]] = {}
    broad_sources: list[dict[str, object]] = []
    bindings: list[dict[str, object]] = []
    for lane in ("l1_trades", "mbo"):
        definition = _definition(lane=lane)
        source_id = f"broad-{lane}"
        location = f"s3://markets/{lane}.dbn.zst"
        target_id = f"target-{lane}"
        broad_sources.append(
            {
                "source_id": source_id,
                "lane": lane,
                "location": location,
                "definition": copy.deepcopy(definition),
            }
        )
        bindings.append(
            {
                "source_id": source_id,
                "binding_fingerprint": f"binding-{lane}",
                "byte_identity_matches_definition": True,
                "blockers": [],
            }
        )
        candidates[("20260330", lane)] = {
            "day": "20260330",
            "lane": lane,
            "target": "G16",
            "candidate_id": f"candidate-{lane}",
            "candidate_fingerprint": f"candidate-fingerprint-{lane}",
            "normalized_source_id": target_id,
            "object_id": f"object-{lane}",
            "source_location": location,
            "definition": copy.deepcopy(definition),
            "definition_fingerprint": definition["definition_fingerprint"],
        }
        entries[target_id] = {
            "source_id": target_id,
            "inspection_fingerprint": f"inspection-{lane}",
            "sha256": ("c" if lane == "l1_trades" else "d") * 64,
            "size_bytes": 50,
            "event_start_s": 10.0,
            "event_end_s": 20.0,
        }

    monkeypatch.setattr(lineage.basis, "_selected_candidates", lambda value: copy.deepcopy(candidates))
    monkeypatch.setattr(lineage.basis, "_catalog_entries", lambda value: copy.deepcopy(entries))

    broad = {
        "schema": lineage.broad_binding.SCHEMA,
        "status": lineage.broad_binding.READY_STATUS,
        "fingerprint": "broad-gate-fingerprint",
        "inventory_compiler_receipt_fingerprint": "inventory-receipt",
        "inspection_receipt_fingerprint": "broad-inspection-receipt",
        "binding_set_fingerprint": "broad-binding-set",
        "inventory_compiler_receipt": {
            "compiled_plan": {
                "corpora": [
                    {
                        "corpus_id": "broad",
                        "lane": "mixed",
                        "sources": broad_sources,
                    }
                ]
            }
        },
        "bindings": bindings,
    }
    slices = {
        "slice_bundle_fingerprint": "slice-bundle",
        "inspection_plan_fingerprint": "target-plan",
    }
    receipt = {
        "receipt_fingerprint": "target-receipt",
        "plan_fingerprint": "target-plan",
        "catalog_fingerprint": "target-catalog",
        "audit_fingerprint": "target-audit",
        "catalog": {},
    }
    return broad, slices, receipt, candidates, entries


def test_exact_target_lineage_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    broad, slices, receipt, _, _ = _gate_inputs(monkeypatch)
    result = lineage.build_gate(broad, slices, receipt)
    assert result["status"] == lineage.READY_STATUS
    assert result["selected_target_source_count"] == 2
    assert result["unique_lineage_count"] == 2
    assert result["stand_down_required"] is False
    assert [row["lane"] for row in result["lineage_rows"]] == ["l1_trades", "mbo"]


def test_unrelated_target_source_stands_down(monkeypatch: pytest.MonkeyPatch) -> None:
    broad, slices, receipt, candidates, _ = _gate_inputs(monkeypatch)
    candidates[("20260330", "mbo")]["source_location"] = "s3://other/unrelated.dbn.zst"
    result = lineage.build_gate(broad, slices, receipt)
    assert result["status"] == lineage.BLOCKED_STATUS
    assert result["stand_down_required"] is True
    assert any("NO_EXACT_BROAD_SOURCE_LINEAGE" in item for item in result["blockers"])


def test_ambiguous_parent_source_stands_down(monkeypatch: pytest.MonkeyPatch) -> None:
    broad, slices, receipt, _, _ = _gate_inputs(monkeypatch)
    duplicate = copy.deepcopy(broad["inventory_compiler_receipt"]["compiled_plan"]["corpora"][0]["sources"][0])
    duplicate["source_id"] = "broad-l1-duplicate"
    broad["inventory_compiler_receipt"]["compiled_plan"]["corpora"][0]["sources"].append(duplicate)
    broad["bindings"].append(
        {
            "source_id": "broad-l1-duplicate",
            "binding_fingerprint": "binding-l1-duplicate",
            "byte_identity_matches_definition": True,
            "blockers": [],
        }
    )
    result = lineage.build_gate(broad, slices, receipt)
    assert result["status"] == lineage.BLOCKED_STATUS
    assert any("AMBIGUOUS_BROAD_SOURCE_LINEAGE" in item for item in result["blockers"])


def test_refingerprinted_nested_tamper_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    broad, slices, receipt, _, _ = _gate_inputs(monkeypatch)
    result = lineage.build_gate(broad, slices, receipt)
    result["lineage_rows"][0]["lineage_unique"] = False
    result["fingerprint"] = lineage._fp({key: value for key, value in result.items() if key != "fingerprint"})
    with pytest.raises(lineage.TargetSliceBroadLineageError, match="deterministic reconstruction"):
        lineage.validate_gate(result)


def test_authority_escalation_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    broad, slices, receipt, _, _ = _gate_inputs(monkeypatch)
    result = lineage.build_gate(broad, slices, receipt)
    result["options_lane_started"] = True
    result["fingerprint"] = lineage._fp({key: value for key, value in result.items() if key != "fingerprint"})
    with pytest.raises(lineage.TargetSliceBroadLineageError, match="options_lane_started"):
        lineage.validate_gate(result)


def test_gate_is_deterministic_and_inputs_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    broad, slices, receipt, _, _ = _gate_inputs(monkeypatch)
    before = copy.deepcopy((broad, slices, receipt))
    first = lineage.build_gate(broad, slices, receipt)
    second = lineage.build_gate(broad, slices, receipt)
    assert first == second
    assert (broad, slices, receipt) == before


def _write_chain(root: Path, values: dict[str, dict[str, object]]) -> None:
    for spec in readiness.STAGES:
        (root / spec.filename).write_text(
            json.dumps(values[spec.key], sort_keys=True) + "\n",
            encoding="utf-8",
        )


def test_readiness_v17_requires_lineage_before_basis(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    _write_chain(tmp_path, values)
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    complete = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V17"
    assert complete["target_slice_broad_lineage_verified"] is True

    (tmp_path / readiness._TARGET_BROAD_LINEAGE.filename).unlink()
    blocked = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert blocked["first_blocking_stage"] == "target_slice_broad_lineage"
    basis_row = next(row for row in blocked["stages"] if row["key"] == "basis_inventory_regeneration")
    assert basis_row["effective_status"] == "BLOCKED_BY_UPSTREAM"


def test_readiness_rejects_refingerprinted_summary_tamper(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    _write_chain(tmp_path, values)
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    report["unrelated_target_slice_route_rejected"] = False
    report["fingerprint"] = readiness._fingerprint({key: value for key, value in report.items() if key != "fingerprint"})
    with pytest.raises(readiness.HistoricalRefinementReadinessError, match="summary mismatch"):
        readiness.validate_readiness_report(report)


def test_executor_and_plan_contract_include_lineage_stage() -> None:
    keys = [spec.key for spec in readiness.STAGES]
    assert keys.index("corpus_definition_byte_binding") < keys.index("target_slice_coverage")
    assert keys.index("target_slice_coverage") < keys.index("target_slice_broad_lineage")
    assert keys.index("target_slice_broad_lineage") < keys.index("basis_inventory_regeneration")
    assert executor.SUGGESTED_ENTRYPOINTS["target_slice_broad_lineage"] == (
        "python",
        "ng_target_slice_broad_lineage_gate.py",
        "build",
    )
    assert compiler.CONFIGURED_STAGES[:5] == (
        "corpus_coverage",
        "corpus_definition_byte_binding",
        "target_slice_coverage",
        "target_slice_broad_lineage",
        "basis_inventory_regeneration",
    )


def test_preflight_rejects_plan_without_lineage_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    preflight._check_plan(plan)
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [row for row in tampered["stages"] if row["key"] != "target_slice_broad_lineage"]
    tampered["fingerprint"] = fingerprinting._fp({key: value for key, value in tampered.items() if key != "fingerprint"})
    with pytest.raises(preflight.HistoricalRefinementPreflightV14Error, match="stage order"):
        preflight._check_plan(tampered)


def test_permanent_authority_controls() -> None:
    values = readiness._linked_fixture_chain()
    lineage_fixture = values["target_slice_broad_lineage"]
    assert lineage_fixture["actual_outcomes_used"] is False
    assert lineage_fixture["random_shuffle_used"] is False
    assert lineage_fixture["blind_forecasts_immutable"] is True
    assert lineage_fixture["may_update_ng_brain"] is False
    assert lineage_fixture["execution_authority"] is False
    assert lineage_fixture["cme_event_contracts_mode"] == "SHADOW"
    assert lineage_fixture["brokerage_contract"] == "tastytrade_not_ibkr"
    assert lineage_fixture["options_lane_started"] is False
