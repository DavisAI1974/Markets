from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection
import ng_corpus_inventory_plan_compiler as compiler


def _authority() -> dict[str, object]:
    return {
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def _definition(
    source_id: str, day: str, path: Path
) -> dict[str, object]:
    raw = path.read_bytes()
    return inspection.definition_observation(
        dataset=coverage.DATASET,
        publisher_id=1,
        instrument_id=1008,
        raw_symbol="NGJ26",
        definition_date=day,
        definition_start_s=0.0,
        definition_end_s=2.0,
        observed_from=f"definition:{source_id}",
        observed_at="2026-07-24T00:00:00Z",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_size_bytes=len(raw),
    )


def _spec(
    tmp_path: Path, *, reference: bool = False
) -> dict[str, object]:
    data = tmp_path / "data"
    data.mkdir()
    sources = {}
    for source_id in ("l1", "mbo"):
        path = data / f"{source_id}.jsonl"
        path.write_text("{}\n", encoding="utf-8")
        definition = _definition(source_id, "20260315", path)
        source = {
            "source_id": source_id,
            "day": "20260315",
            "location": f"s3://bucket/{source_id}",
            "materialized_path": str(path),
        }
        if reference:
            definition_path = tmp_path / f"{source_id}.definition.json"
            raw = json.dumps(definition, sort_keys=True) + "\n"
            definition_path.write_text(raw, encoding="utf-8")
            source["definition_path"] = definition_path.name
            source["definition_sha256"] = hashlib.sha256(
                raw.encode("utf-8")
            ).hexdigest()
        else:
            source["definition"] = definition
        sources[source_id] = source
    return {
        "schema": compiler.SPEC_SCHEMA,
        "allowed_roots": [str(data)],
        "inventory_observed_at": "2026-07-24T00:00:00Z",
        "corpora": [
            {
                "corpus_id": coverage.L1_CORPUS_ID,
                "publisher_id": 1,
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": [sources["l1"]],
            },
            {
                "corpus_id": coverage.MBO_CORPUS_ID,
                "publisher_id": 1,
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": [sources["mbo"]],
            },
        ],
        **_authority(),
    }


def test_compiles_ready_canonical_plan(tmp_path: Path) -> None:
    plan, receipt = compiler.build_compiled_plan(
        _spec(tmp_path), spec_dir=tmp_path
    )
    assert receipt["status"] == compiler.READY_STATUS
    assert receipt["blockers"] == []
    assert plan["plan_fingerprint"] == receipt["plan_fingerprint"]
    assert [row["corpus_id"] for row in plan["corpora"]] == [
        coverage.L1_CORPUS_ID,
        coverage.MBO_CORPUS_ID,
    ]
    compiler.validate_receipt(receipt)


def test_resolves_relative_definition_documents_and_attests_bytes(
    tmp_path: Path,
) -> None:
    _, receipt = compiler.build_compiled_plan(
        _spec(tmp_path, reference=True), spec_dir=tmp_path
    )
    assert len(receipt["definition_documents"]) == 2
    assert all(
        len(row["sha256"]) == 64
        for row in receipt["definition_documents"]
    )
    compiler.validate_receipt(receipt)


def test_rejects_definition_reference_escape(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    source = spec["corpora"][0]["sources"][0]
    source.pop("definition")
    source["definition_path"] = "../outside.json"
    with pytest.raises(
        compiler.CorpusInventoryPlanCompilerError, match="escapes"
    ):
        compiler.build_compiled_plan(spec, spec_dir=tmp_path)


def test_rejects_absolute_definition_reference(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    source = spec["corpora"][0]["sources"][0]
    source.pop("definition")
    source["definition_path"] = str(
        (tmp_path / "outside.json").resolve()
    )
    with pytest.raises(
        compiler.CorpusInventoryPlanCompilerError, match="relative"
    ):
        compiler.build_compiled_plan(spec, spec_dir=tmp_path)


def test_rejects_definition_hash_mismatch(tmp_path: Path) -> None:
    spec = _spec(tmp_path, reference=True)
    spec["corpora"][0]["sources"][0]["definition_sha256"] = "0" * 64
    with pytest.raises(
        compiler.CorpusInventoryPlanCompilerError,
        match="definition_sha256",
    ):
        compiler.build_compiled_plan(spec, spec_dir=tmp_path)


def test_rejects_duplicate_source_id_across_lanes(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    spec["corpora"][1]["sources"][0]["source_id"] = "l1"
    with pytest.raises(
        compiler.CorpusInventoryPlanCompilerError, match="duplicate"
    ):
        compiler.build_compiled_plan(spec, spec_dir=tmp_path)


def test_rejects_definition_publisher_mismatch(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    spec["corpora"][0]["publisher_id"] = 2
    with pytest.raises(
        compiler.CorpusInventoryPlanCompilerError,
        match="publisher mismatch",
    ):
        compiler.build_compiled_plan(spec, spec_dir=tmp_path)


def test_exposes_unmaterialized_and_missing_definition_blockers(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    source = spec["corpora"][0]["sources"][0]
    source["materialized_path"] = None
    source.pop("definition")
    _, receipt = compiler.build_compiled_plan(spec, spec_dir=tmp_path)
    assert receipt["status"] == compiler.BLOCKED_STATUS
    assert (
        f"{coverage.L1_CORPUS_ID}:SOURCE_NOT_MATERIALIZED"
        in receipt["blockers"]
    )
    assert (
        f"{coverage.L1_CORPUS_ID}:SOURCE_DEFINITION_MISSING"
        in receipt["blockers"]
    )


def test_exposes_expected_count_and_day_mismatch(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    spec["corpora"][0]["expected_object_count"] = 2
    spec["corpora"][0]["expected_days"].append("20260316")
    _, receipt = compiler.build_compiled_plan(spec, spec_dir=tmp_path)
    assert (
        f"{coverage.L1_CORPUS_ID}:EXPECTED_OBJECT_COUNT_MISMATCH"
        in receipt["blockers"]
    )
    assert (
        f"{coverage.L1_CORPUS_ID}:EXPECTED_DAY_WITHOUT_SOURCE"
        in receipt["blockers"]
    )


def test_refingerprinted_compiled_plan_substitution_fails_reconstruction(
    tmp_path: Path,
) -> None:
    _, receipt = compiler.build_compiled_plan(
        _spec(tmp_path), spec_dir=tmp_path
    )
    tampered = copy.deepcopy(receipt)
    tampered["compiled_plan"]["corpora"][0]["expected_days"] = [
        "20260316"
    ]
    tampered["compiled_plan"].pop("plan_fingerprint")
    tampered["compiled_plan"]["plan_fingerprint"] = inspection._fp(
        tampered["compiled_plan"]
    )
    tampered["plan_fingerprint"] = tampered["compiled_plan"][
        "plan_fingerprint"
    ]
    tampered.pop("receipt_fingerprint")
    tampered["receipt_fingerprint"] = compiler._fp(tampered)
    with pytest.raises(
        compiler.CorpusInventoryPlanCompilerError,
        match="compiled inspection plan mismatch",
    ):
        compiler.validate_receipt(tampered)


def test_authority_escalation_fails_even_after_refingerprinting(
    tmp_path: Path,
) -> None:
    _, receipt = compiler.build_compiled_plan(
        _spec(tmp_path), spec_dir=tmp_path
    )
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    tampered.pop("receipt_fingerprint")
    tampered["receipt_fingerprint"] = compiler._fp(tampered)
    with pytest.raises(
        compiler.CorpusInventoryPlanCompilerError,
        match="options_lane_started",
    ):
        compiler.validate_receipt(tampered)


def test_deterministic_compilation_and_source_immutability(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path, reference=True)
    before = copy.deepcopy(spec)
    first = compiler.build_compiled_plan(spec, spec_dir=tmp_path)
    second = compiler.build_compiled_plan(spec, spec_dir=tmp_path)
    assert spec == before
    assert first == second
