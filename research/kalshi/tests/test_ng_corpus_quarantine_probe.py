from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import ng_corpus_inspection as inspection
import ng_corpus_materialization as materialization
import ng_corpus_quarantine_probe as probe


class FakeS3:
    def __init__(self, objects: dict[tuple[str, str], bytes]):
        self.objects = objects

    def download_file(self, bucket: str, key: str, target: str) -> None:
        Path(target).write_bytes(self.objects[(bucket, key)])


def _bytes(*, instrument_id: int = 1008, raw_symbol: str = "NGJ26", publisher_id: int = 1, backwards: bool = False) -> bytes:
    rows = [
        {
            "event_type": "trade",
            "source_schema": "trades",
            "dataset": "GLBX.MDP3",
            "publisher_id": publisher_id,
            "instrument_id": instrument_id,
            "raw_symbol": raw_symbol,
            "ts_event_s": 1773579600.0,
            "sequence": 1,
        },
        {
            "event_type": "trade",
            "source_schema": "trades",
            "dataset": "GLBX.MDP3",
            "publisher_id": publisher_id,
            "instrument_id": instrument_id,
            "raw_symbol": raw_symbol,
            "ts_event_s": 1773579700.0 if not backwards else 1773579500.0,
            "sequence": 2,
        },
    ]
    return ("\n".join(json.dumps(row) for row in rows) + "\n").encode()


def _snapshot(data: bytes) -> tuple[dict, FakeS3, str]:
    bucket = "history"
    key = "opaque/object-0001.jsonl"
    fake = FakeS3({(bucket, key): data})
    snapshot = materialization.snapshot_s3(
        type("Lister", (), {"list_objects_v2": lambda self, **kwargs: {
            "Contents": [{"Key": key, "Size": len(data), "ETag": "etag"}],
            "IsTruncated": False,
        }})(),
        bucket=bucket,
        prefixes=["opaque/"],
        observed_at="2026-07-22T00:00:00Z",
    )
    return snapshot, fake, snapshot["objects"][0]["object_id"]


def _definition(data: bytes, *, instrument_id: int = 1008, raw_symbol: str = "NGJ26", publisher_id: int = 1, definition_date: str = "20260313") -> dict:
    return inspection.definition_observation(
        dataset="GLBX.MDP3",
        publisher_id=publisher_id,
        instrument_id=instrument_id,
        raw_symbol=raw_symbol,
        definition_date=definition_date,
        definition_start_s=1773500000.0,
        definition_end_s=1773700000.0,
        observed_from="definition.dbn",
        observed_at="2026-07-22T00:00:00Z",
        source_sha256=hashlib.sha256(data).hexdigest(),
        source_size_bytes=len(data),
    )


def _quarantine(tmp_path: Path, data: bytes):
    snapshot, fake, object_id = _snapshot(data)
    receipt = probe.quarantine_download(
        fake,
        snapshot=snapshot,
        object_ids=[object_id],
        output_root=tmp_path / "quarantine",
        confirm_download=True,
        max_total_bytes=len(data),
    )
    return snapshot, receipt, object_id


def _approve(bindings: dict, object_id: str, definition: dict) -> dict:
    approved = copy.deepcopy(bindings)
    row = next(row for row in approved["bindings"] if row["object_id"] == object_id)
    row.update(
        review_status="APPROVED",
        source_id="g15-l1-20260315",
        corpus_id="l1_dense_one_year",
        lane="l1_trades",
        day="20260315",
        definition=definition,
        skip_nonmatching=False,
    )
    row.pop("binding_fingerprint")
    row["binding_fingerprint"] = probe._fp(row)
    approved.pop("binding_manifest_fingerprint")
    approved["binding_manifest_fingerprint"] = probe._fp(approved)
    return approved


def test_quarantine_requires_explicit_confirmation(tmp_path):
    data = _bytes()
    snapshot, fake, object_id = _snapshot(data)
    with pytest.raises(probe.CorpusQuarantineError, match="explicit confirmation"):
        probe.quarantine_download(fake, snapshot=snapshot, object_ids=[object_id], output_root=tmp_path, confirm_download=False, max_total_bytes=len(data))


def test_quarantine_enforces_byte_ceiling(tmp_path):
    data = _bytes()
    snapshot, fake, object_id = _snapshot(data)
    with pytest.raises(probe.CorpusQuarantineError, match="exceeds"):
        probe.quarantine_download(fake, snapshot=snapshot, object_ids=[object_id], output_root=tmp_path, confirm_download=True, max_total_bytes=len(data) - 1)


def test_quarantine_is_identity_neutral_and_hashes_bytes(tmp_path):
    data = _bytes()
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    row = receipt["objects"][0]
    assert row["contract_identity_status"] == "UNOBSERVED"
    assert row["sha256"] == hashlib.sha256(data).hexdigest()
    assert Path(row["quarantine_path"]).read_bytes() == data
    probe.validate_quarantine(receipt, snapshot=snapshot, verify_files=True)


def test_quarantine_tampering_is_detected(tmp_path):
    data = _bytes()
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    Path(receipt["objects"][0]["quarantine_path"]).write_bytes(b"tampered")
    with pytest.raises(probe.CorpusQuarantineError, match="verification failed"):
        probe.validate_quarantine(receipt, snapshot=snapshot, verify_files=True)


def test_probe_builds_unique_definition_review_proposal(tmp_path):
    data = _bytes()
    snapshot, receipt, object_id = _quarantine(tmp_path, data)
    definition = _definition(data)
    result, bindings = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[definition])
    evidence = result["objects"][0]
    binding = next(row for row in bindings["bindings"] if row["object_id"] == object_id)
    assert evidence["status"] == "UNIQUE_DEFINITION_MATCH"
    assert binding["review_status"] == "REVIEW_REQUIRED"
    assert binding["definition"]["raw_symbol"] == "NGJ26"
    assert binding["day"] is None
    assert result["automatic_approval_permitted"] is False


def test_probe_rejects_filename_as_identity(tmp_path):
    data = _bytes(raw_symbol="NGJ26")
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    result, _ = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[_definition(data)])
    assert result["identity_inferred_from_object_name"] is False
    assert result["objects"][0]["identity_inferred_from_object_name"] is False


def test_probe_reports_no_definition_match(tmp_path):
    data = _bytes(instrument_id=1008)
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    result, _ = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[_definition(data, instrument_id=996, raw_symbol="NGK26")])
    assert result["objects"][0]["status"] == "NO_DEFINITION_MATCH"


def test_probe_reports_ambiguous_definition_match(tmp_path):
    data = _bytes()
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    first = _definition(data, definition_date="20260313")
    second = _definition(data, definition_date="20260314")
    result, _ = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[first, second])
    assert result["objects"][0]["status"] == "AMBIGUOUS_DEFINITION_MATCH"


def test_probe_detects_decoded_symbol_contradiction(tmp_path):
    data = _bytes(raw_symbol="NGK26", instrument_id=1008)
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    result, _ = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[_definition(data, instrument_id=1008, raw_symbol="NGJ26")])
    assert result["objects"][0]["status"] == "NO_DEFINITION_MATCH"


def test_probe_rejects_backward_chronology(tmp_path):
    data = _bytes(backwards=True)
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    with pytest.raises(probe.CorpusQuarantineError, match="moved backwards"):
        probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[_definition(data)])


def test_probe_preserves_source_bytes(tmp_path):
    data = _bytes()
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    path = Path(receipt["objects"][0]["quarantine_path"])
    before = path.read_bytes()
    probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[_definition(data)])
    assert path.read_bytes() == before


def test_probe_artifact_tampering_is_detected(tmp_path):
    data = _bytes()
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    result, bindings = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[_definition(data)])
    changed = copy.deepcopy(result)
    changed["objects"][0]["status"] = "NO_DEFINITION_MATCH"
    changed["probe_fingerprint"] = probe._fp({k: v for k, v in changed.items() if k != "probe_fingerprint"})
    with pytest.raises(probe.CorpusQuarantineError, match="object fingerprint mismatch"):
        probe.validate_probe(changed, snapshot=snapshot, quarantine=receipt, proposed_bindings=bindings)


def test_promotion_requires_operator_approval(tmp_path):
    data = _bytes()
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    _, bindings = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[_definition(data)])
    with pytest.raises(Exception, match="unreviewed"):
        probe.promote_quarantine(snapshot=snapshot, bindings=bindings, quarantine=receipt, output_root=tmp_path / "promoted", confirm_promote=True)


def test_promotion_reuses_verified_quarantine_bytes(tmp_path):
    data = _bytes()
    snapshot, receipt, object_id = _quarantine(tmp_path, data)
    definition = _definition(data)
    _, bindings = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[definition])
    approved = _approve(bindings, object_id, definition)
    materialized = probe.promote_quarantine(snapshot=snapshot, bindings=approved, quarantine=receipt, output_root=tmp_path / "promoted", confirm_promote=True)
    assert materialized["schema"] == materialization.MATERIALIZATION_SCHEMA
    assert materialized["approved_object_count"] == 1
    assert Path(materialized["objects"][0]["materialized_path"]).read_bytes() == data
    materialization.validate_materialization(materialized, snapshot=snapshot, bindings=approved, verify_files=True)


def test_promotion_requires_explicit_confirmation(tmp_path):
    data = _bytes()
    snapshot, receipt, object_id = _quarantine(tmp_path, data)
    definition = _definition(data)
    _, bindings = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[definition])
    approved = _approve(bindings, object_id, definition)
    with pytest.raises(probe.CorpusQuarantineError, match="explicit confirmation"):
        probe.promote_quarantine(snapshot=snapshot, bindings=approved, quarantine=receipt, output_root=tmp_path / "promoted", confirm_promote=False)


def test_authority_contract_remains_disabled(tmp_path):
    data = _bytes()
    snapshot, receipt, _ = _quarantine(tmp_path, data)
    result, _ = probe.probe_quarantine(snapshot=snapshot, quarantine=receipt, definitions=[_definition(data)])
    for artifact in (receipt, result):
        assert artifact["actual_outcomes_used"] is False
        assert artifact["may_update_ng_brain"] is False
        assert artifact["execution_authority"] is False
        assert artifact["cme_event_contracts_mode"] == "SHADOW"
        assert artifact["brokerage_contract"] == "tastytrade_not_ibkr"
        assert artifact["options_lane_started"] is False
