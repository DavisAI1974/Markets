from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import ng_historical_refinement_readiness_v18 as readiness
import ng_target_slice_derivation_gate as derivation


def _parent_gate() -> dict[str, object]:
    rows = []
    for lane in ("l1_trades", "mbo"):
        rows.append(
            {
                "day": "20260330",
                "lane": lane,
                "lineage_unique": True,
                "target_candidate_fingerprint": f"candidate-fingerprint-{lane}",
                "broad_source_id": f"broad-{lane}",
            }
        )
    return {
        "schema": "ng_target_slice_broad_lineage_gate.v1",
        "status": "TARGET_SLICE_BROAD_LINEAGE_READY",
        "fingerprint": "lineage-fingerprint",
        "broad_definition_byte_binding_fingerprint": "broad-binding-gate",
        "target_slice_bundle_fingerprint": "slice-bundle",
        "target_inspection_receipt_fingerprint": "target-receipt",
        "target_catalog_fingerprint": "target-catalog",
        "target_audit_fingerprint": "target-audit",
        "lineage_set_fingerprint": "lineage-set",
        "expected_target_source_count": 2,
        "lineage_rows": rows,
        "target_slice_bundle": {},
        "target_inspection_receipt": {},
        "broad_definition_byte_binding_gate": {},
    }


def _install_gate_stubs(monkeypatch: pytest.MonkeyPatch, *, mismatch: bool = False) -> None:
    parent = _parent_gate()
    monkeypatch.setattr(
        derivation.lineage,
        "validate_gate",
        lambda value: copy.deepcopy(parent),
    )
    candidates = {
        ("20260330", lane): {
            "day": "20260330",
            "lane": lane,
            "target": "G16",
            "candidate_id": f"candidate-{lane}",
            "candidate_fingerprint": f"candidate-fingerprint-{lane}",
            "normalized_source_id": f"target-{lane}",
        }
        for lane in ("l1_trades", "mbo")
    }
    entries = {
        f"target-{lane}": {
            "inspection_fingerprint": f"inspection-{lane}",
            "sha256": ("a" if lane == "l1_trades" else "b") * 64,
            "size_bytes": 50,
            "record_count": 5,
        }
        for lane in ("l1_trades", "mbo")
    }
    sources = {
        f"broad-{lane}": {
            "source_id": f"broad-{lane}",
            "materialized_path": f"/tmp/{lane}.jsonl",
            "definition": {"definition_fingerprint": f"definition-{lane}"},
            "binding": {
                "binding_fingerprint": f"binding-{lane}",
                "byte_identity_matches_definition": True,
                "blockers": [],
            },
        }
        for lane in ("l1_trades", "mbo")
    }
    monkeypatch.setattr(
        derivation,
        "_target_maps",
        lambda value: (copy.deepcopy(candidates), copy.deepcopy(entries)),
    )
    monkeypatch.setattr(
        derivation,
        "_broad_source_map",
        lambda value: copy.deepcopy(sources),
    )
    monkeypatch.setattr(
        derivation.basis,
        "_validate_entry_against_candidate",
        lambda *args, **kwargs: None,
    )

    def fake_derive(*, source, candidate, target_entry, verify_files):
        lane = candidate["lane"]
        blockers = ["DERIVED_SHA256_MISMATCH"] if mismatch and lane == "mbo" else []
        row = {
            "day": candidate["day"],
            "lane": lane,
            "target": candidate["target"],
            "target_candidate_id": candidate["candidate_id"],
            "target_candidate_fingerprint": candidate["candidate_fingerprint"],
            "target_source_id": candidate["normalized_source_id"],
            "target_inspection_fingerprint": target_entry["inspection_fingerprint"],
            "broad_source_id": source["source_id"],
            "broad_binding_fingerprint": source["binding"]["binding_fingerprint"],
            "broad_materialized_path": source["materialized_path"],
            "definition_fingerprint": source["definition"]["definition_fingerprint"],
            "expected_target_sha256": target_entry["sha256"],
            "expected_target_size_bytes": 50,
            "expected_target_record_count": 5,
            "derived_target_sha256": target_entry["sha256"] if not blockers else "c" * 64,
            "derived_target_size_bytes": 50,
            "derived_target_record_count": 5,
            "parent_source_sha256_before": "p" * 64,
            "parent_source_sha256_after": "p" * 64,
            "parent_source_size_bytes_before": 100,
            "parent_source_size_bytes_after": 100,
            "derivation_algorithm": derivation.ALGORITHM,
            "derivation_exact": not blockers,
            "blockers": blockers,
        }
        row["derivation_fingerprint"] = derivation._fp(row)
        return row

    monkeypatch.setattr(derivation, "_derive_one", fake_derive)


def test_exact_derivation_gate_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_gate_stubs(monkeypatch)
    result = derivation.build_gate(_parent_gate(), verify_files=True)
    assert result["status"] == derivation.READY_STATUS
    assert result["derived_target_source_count"] == 2
    assert result["exact_derivation_count"] == 2
    assert result["source_files_verified"] is True
    assert result["stand_down_required"] is False


def test_content_mismatch_stands_down(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_gate_stubs(monkeypatch, mismatch=True)
    result = derivation.build_gate(_parent_gate(), verify_files=True)
    assert result["status"] == derivation.BLOCKED_STATUS
    assert result["stand_down_required"] is True
    assert any("DERIVED_SHA256_MISMATCH" in item for item in result["blockers"])


def test_lineage_candidate_substitution_stands_down(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_gate_stubs(monkeypatch)
    parent = _parent_gate()
    parent["lineage_rows"][0]["target_candidate_fingerprint"] = "replacement"
    monkeypatch.setattr(derivation.lineage, "validate_gate", lambda value: copy.deepcopy(parent))
    result = derivation.build_gate(parent, verify_files=True)
    assert result["status"] == derivation.BLOCKED_STATUS
    assert any("LINEAGE_CANDIDATE_MISMATCH" in item for item in result["blockers"])


def test_low_level_rederivation_compares_exact_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "parent.jsonl"
    source_path.write_bytes(b"parent-bytes\n")
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    encoded = [b'{"a":1}\n', b'{"a":2}\n']
    target_bytes = b"".join(encoded)
    target_sha = hashlib.sha256(target_bytes).hexdigest()
    monkeypatch.setattr(
        derivation,
        "_normalized_lines",
        lambda **kwargs: iter(encoded),
    )
    source = {
        "source_id": "broad-l1",
        "materialized_path": str(source_path),
        "definition": {
            "definition_fingerprint": "definition",
            "source_sha256": source_sha,
            "source_size_bytes": source_path.stat().st_size,
        },
        "binding": {
            "binding_fingerprint": "binding",
            "byte_identity_matches_definition": True,
            "blockers": [],
        },
    }
    candidate = {
        "day": "20260330",
        "lane": "l1_trades",
        "target": "G16",
        "candidate_id": "candidate",
        "candidate_fingerprint": "candidate-fingerprint",
        "normalized_source_id": "target-l1",
        "sha256": target_sha,
        "size_bytes": len(target_bytes),
        "record_count": 2,
    }
    entry = {
        "inspection_fingerprint": "inspection",
        "sha256": target_sha,
        "size_bytes": len(target_bytes),
        "record_count": 2,
    }
    row = derivation._derive_one(
        source=source,
        candidate=candidate,
        target_entry=entry,
        verify_files=True,
    )
    assert row["derivation_exact"] is True
    assert row["derived_target_sha256"] == target_sha
    assert row["derived_target_record_count"] == 2


def test_refingerprinted_row_tamper_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_gate_stubs(monkeypatch)
    result = derivation.build_gate(_parent_gate(), verify_files=True)
    result["derivation_rows"][0]["derivation_exact"] = False
    result["fingerprint"] = derivation._fp(
        {key: value for key, value in result.items() if key != "fingerprint"}
    )
    with pytest.raises(derivation.TargetSliceDerivationError, match="deterministic reconstruction"):
        derivation.validate_gate(result, verify_files=True)


def test_authority_escalation_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_gate_stubs(monkeypatch)
    result = derivation.build_gate(_parent_gate(), verify_files=True)
    result["options_lane_started"] = True
    result["fingerprint"] = derivation._fp(
        {key: value for key, value in result.items() if key != "fingerprint"}
    )
    with pytest.raises(derivation.TargetSliceDerivationError, match="options_lane_started"):
        derivation.validate_gate(result, verify_files=True)


def test_gate_is_deterministic_and_input_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_gate_stubs(monkeypatch)
    parent = _parent_gate()
    before = copy.deepcopy(parent)
    first = derivation.build_gate(parent, verify_files=True)
    second = derivation.build_gate(parent, verify_files=True)
    assert first == second
    assert parent == before


def _write_chain(root: Path, values: dict[str, dict[str, object]]) -> None:
    for spec in readiness.STAGES:
        (root / spec.filename).write_text(
            json.dumps(values[spec.key], sort_keys=True) + "\n", encoding="utf-8"
        )


def test_readiness_v18_requires_derivation_before_basis(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    _write_chain(tmp_path, values)
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    complete = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V18"
    assert complete["target_slice_derivation_attested"] is True

    (tmp_path / readiness._TARGET_SLICE_DERIVATION.filename).unlink()
    blocked = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert blocked["first_blocking_stage"] == "target_slice_derivation"
    basis_row = next(
        row for row in blocked["stages"] if row["key"] == "basis_inventory_regeneration"
    )
    assert basis_row["effective_status"] == "BLOCKED_BY_UPSTREAM"


def test_readiness_link_chain_routes_derivation_into_basis() -> None:
    keys = [spec.key for spec in readiness.STAGES]
    assert keys.index("target_slice_broad_lineage") < keys.index("target_slice_derivation")
    assert keys.index("target_slice_derivation") < keys.index("basis_inventory_regeneration")
    assert (
        "target_slice_derivation",
        "target_slice_bundle_fingerprint",
        "basis_inventory_regeneration",
        "slice_bundle_fingerprint",
    ) in readiness.LINK_RULES
    assert not any(
        rule[0] == "target_slice_broad_lineage"
        and rule[2] == "basis_inventory_regeneration"
        for rule in readiness.LINK_RULES
    )


def test_permanent_authority_controls() -> None:
    fixture = readiness._linked_fixture_chain()["target_slice_derivation"]
    assert fixture["actual_outcomes_used"] is False
    assert fixture["random_shuffle_used"] is False
    assert fixture["blind_forecasts_immutable"] is True
    assert fixture["may_update_ng_brain"] is False
    assert fixture["execution_authority"] is False
    assert fixture["cme_event_contracts_mode"] == "SHADOW"
    assert fixture["brokerage_contract"] == "tastytrade_not_ibkr"
    assert fixture["options_lane_started"] is False
