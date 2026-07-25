from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection
import ng_corpus_s3_materialization_attestation as attestation


def _authority() -> dict[str, object]:
    return attestation._authority_fields()


def _source(
    data: Path,
    *,
    source_id: str,
    lane: str,
    day: str = "20260315",
    definition_path: bool = False,
) -> dict[str, object]:
    path = data / f"{source_id}.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    definition = inspection.definition_observation(
        dataset=coverage.DATASET,
        publisher_id=1,
        instrument_id=1008,
        raw_symbol="NGJ26",
        definition_date=day,
        definition_start_s=0.0,
        definition_end_s=2.0,
        observed_from=f"s3-test:{source_id}",
        observed_at="2026-07-24T00:00:00Z",
        source_sha256=sha,
        source_size_bytes=len(raw),
    )
    source: dict[str, object] = {
        "source_id": source_id,
        "day": day,
        "lane": lane,
        "materialized_path": str(path),
        "s3_object": {
            "bucket": "historical-ng",
            "key": f"dbn/{source_id}.jsonl",
            "version_id": f"version-{source_id}",
            "etag": f'"etag-{source_id}"',
            "last_modified": "2026-07-24T00:00:00Z",
            "size_bytes": len(raw),
            "checksum_sha256": sha,
            "checksum_source": "upload-manifest",
        },
    }
    if definition_path:
        doc = data.parent / f"{source_id}.definition.json"
        text = json.dumps(definition, sort_keys=True) + "\n"
        doc.write_text(text, encoding="utf-8")
        source["definition_path"] = doc.name
        source["definition_sha256"] = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()
    else:
        source["definition"] = definition
    return source


def _spec(
    tmp_path: Path, *, definition_path: bool = False
) -> dict[str, object]:
    data = tmp_path / "data"
    data.mkdir()
    l1 = _source(
        data,
        source_id="l1",
        lane="l1_trades",
        definition_path=definition_path,
    )
    mbo = _source(
        data,
        source_id="mbo",
        lane="mbo",
        definition_path=definition_path,
    )
    return {
        "schema": attestation.SPEC_SCHEMA,
        "allowed_roots": [str(data)],
        "inventory_observed_at": "2026-07-24T00:00:00Z",
        "corpora": [
            {
                "corpus_id": coverage.L1_CORPUS_ID,
                "lane": "l1_trades",
                "publisher_id": 1,
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": [l1],
            },
            {
                "corpus_id": coverage.MBO_CORPUS_ID,
                "lane": "mbo",
                "publisher_id": 1,
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": [mbo],
            },
        ],
        **_authority(),
    }


def _reprint(receipt: dict[str, object]) -> None:
    receipt.pop("receipt_fingerprint", None)
    receipt["receipt_fingerprint"] = attestation._fp(receipt)


def test_attests_remote_objects_and_compiles_ready_plan(
    tmp_path: Path,
) -> None:
    inventory_spec, plan, receipt = attestation.build_attested_plan(
        _spec(tmp_path), spec_dir=tmp_path
    )
    assert receipt["status"] == attestation.READY_STATUS
    assert receipt["blockers"] == []
    assert plan["plan_fingerprint"] == receipt["plan_fingerprint"]
    assert inventory_spec["schema"] == "ng_corpus_inventory_spec.v1"
    assert len(receipt["materialization_evidence"]) == 2
    assert all(
        row["remote_bytes_match_materialized"] is True
        for row in receipt["materialization_evidence"]
    )
    attestation.validate_receipt(receipt)


def test_versioned_location_and_definition_document_are_attested(
    tmp_path: Path,
) -> None:
    _, _, receipt = attestation.build_attested_plan(
        _spec(tmp_path, definition_path=True), spec_dir=tmp_path
    )
    rows = receipt["materialization_evidence"]
    assert all("?versionId=" in row["location"] for row in rows)
    assert len(receipt["definition_documents"]) == 2
    attestation.validate_receipt(receipt)


def test_rejects_remote_checksum_mismatch(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    spec["corpora"][0]["sources"][0]["s3_object"][
        "checksum_sha256"
    ] = "0" * 64
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="SHA-256 does not match",
    ):
        attestation.build_attested_plan(spec, spec_dir=tmp_path)


def test_rejects_remote_size_mismatch(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    spec["corpora"][0]["sources"][0]["s3_object"]["size_bytes"] = 999
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="size does not match",
    ):
        attestation.build_attested_plan(spec, spec_dir=tmp_path)


def test_rejects_materialized_path_outside_allowed_root(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}\n", encoding="utf-8")
    source = spec["corpora"][0]["sources"][0]
    source["materialized_path"] = str(outside)
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="escapes every allowed_root",
    ):
        attestation.build_attested_plan(spec, spec_dir=tmp_path)


def test_rejects_missing_strong_remote_checksum(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    spec["corpora"][0]["sources"][0]["s3_object"].pop(
        "checksum_sha256"
    )
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="64-character hexadecimal SHA-256",
    ):
        attestation.build_attested_plan(spec, spec_dir=tmp_path)


def test_rejects_definition_bytes_not_bound_to_materialization(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    definition = copy.deepcopy(
        spec["corpora"][0]["sources"][0]["definition"]
    )
    definition["source_sha256"] = "1" * 64
    definition.pop("definition_fingerprint")
    definition["definition_fingerprint"] = inspection._fp(definition)
    spec["corpora"][0]["sources"][0]["definition"] = definition
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="definition source_sha256",
    ):
        attestation.build_attested_plan(spec, spec_dir=tmp_path)


def test_rejects_duplicate_exact_s3_object_identity(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    first = spec["corpora"][0]["sources"][0]["s3_object"]
    second = spec["corpora"][1]["sources"][0]
    second["s3_object"] = copy.deepcopy(first)
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="duplicate exact S3 object identity",
    ):
        attestation.build_attested_plan(spec, spec_dir=tmp_path)


def test_requires_explicit_lane_instead_of_key_inference(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    spec["corpora"][0]["sources"][0].pop("lane")
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="explicit lane",
    ):
        attestation.build_attested_plan(spec, spec_dir=tmp_path)


def test_revalidation_detects_materialized_byte_change(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    _, _, receipt = attestation.build_attested_plan(spec, spec_dir=tmp_path)
    path = Path(
        spec["corpora"][0]["sources"][0]["materialized_path"]
    )
    path.write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="size does not match|SHA-256 does not match",
    ):
        attestation.validate_receipt(receipt)


def test_refingerprinted_evidence_substitution_fails_reconstruction(
    tmp_path: Path,
) -> None:
    _, _, receipt = attestation.build_attested_plan(
        _spec(tmp_path), spec_dir=tmp_path
    )
    tampered = copy.deepcopy(receipt)
    tampered["materialization_evidence"][0]["remote_object"][
        "key"
    ] = "other"
    tampered["materialization_evidence_fingerprint"] = attestation._fp(
        tampered["materialization_evidence"]
    )
    _reprint(tampered)
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="materialization evidence mismatch",
    ):
        attestation.validate_receipt(tampered)


def test_authority_escalation_fails_after_refingerprinting(
    tmp_path: Path,
) -> None:
    _, _, receipt = attestation.build_attested_plan(
        _spec(tmp_path), spec_dir=tmp_path
    )
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    _reprint(tampered)
    with pytest.raises(
        attestation.CorpusS3MaterializationError,
        match="options_lane_started",
    ):
        attestation.validate_receipt(tampered)


def test_deterministic_build_and_source_immutability(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path, definition_path=True)
    before = copy.deepcopy(spec)
    first = attestation.build_attested_plan(spec, spec_dir=tmp_path)
    second = attestation.build_attested_plan(spec, spec_dir=tmp_path)
    assert spec == before
    assert first == second
