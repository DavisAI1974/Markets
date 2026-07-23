from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import ng_corpus_definition_probe_gate as gate
import ng_corpus_materialization as materialization
import ng_definition_observation as definitions


class FakeS3:
    def __init__(self, objects: dict[tuple[str, str], bytes]):
        self.objects = objects

    def download_file(self, bucket: str, key: str, target: str) -> None:
        Path(target).write_bytes(self.objects[(bucket, key)])


class FakeLister:
    def __init__(self, key: str, size: int):
        self.key = key
        self.size = size

    def list_objects_v2(self, **_kwargs):
        return {
            "Contents": [{"Key": self.key, "Size": self.size, "ETag": "etag"}],
            "IsTruncated": False,
        }


def _trade_bytes(*, instrument_id: int = 1008, raw_symbol: str = "NGJ26") -> bytes:
    rows = [
        {
            "event_type": "trade",
            "source_schema": "trades",
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": instrument_id,
            "raw_symbol": raw_symbol,
            "ts_event_s": 1773579600.0,
            "sequence": 1,
        },
        {
            "event_type": "trade",
            "source_schema": "trades",
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": instrument_id,
            "raw_symbol": raw_symbol,
            "ts_event_s": 1773579700.0,
            "sequence": 2,
        },
    ]
    return ("\n".join(json.dumps(row) for row in rows) + "\n").encode()


def _definition_row(
    *,
    instrument_id: int = 1008,
    raw_symbol: str = "NGJ26",
    start: float = 1773500000.0,
    end: float = 1773700000.0,
    event: float | None = None,
) -> dict:
    return {
        "event_type": "definition",
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": instrument_id,
        "raw_symbol": raw_symbol,
        "ts_event_s": start if event is None else event,
        "activation": start,
        "expiration": end,
    }


def _catalog(tmp_path: Path, rows: list[dict] | None = None) -> tuple[dict, Path]:
    path = tmp_path / "definitions.jsonl"
    rows = rows or [_definition_row()]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    symbols = sorted({row["raw_symbol"] for row in rows})
    return (
        definitions.build_catalog(
            [path],
            observed_at="2026-07-22T00:00:00Z",
            raw_symbols=symbols,
        ),
        path,
    )


def _quarantine(tmp_path: Path, data: bytes | None = None):
    data = data or _trade_bytes()
    bucket, key = "history", "opaque/object-0001.jsonl"
    snapshot = materialization.snapshot_s3(
        FakeLister(key, len(data)),
        bucket=bucket,
        prefixes=["opaque/"],
        observed_at="2026-07-22T00:00:00Z",
    )
    object_id = snapshot["objects"][0]["object_id"]
    receipt = gate.quarantine_download(
        FakeS3({(bucket, key): data}),
        snapshot=snapshot,
        object_ids=[object_id],
        output_root=tmp_path / "quarantine",
        confirm_download=True,
        max_total_bytes=len(data),
    )
    return snapshot, receipt, object_id, data


def _bundle(tmp_path: Path, *, rows: list[dict] | None = None, data: bytes | None = None):
    snapshot, quarantine, object_id, payload = _quarantine(tmp_path, data)
    catalog, definition_path = _catalog(tmp_path, rows)
    gated, probed, bindings = gate.probe_with_catalog(
        snapshot=snapshot,
        quarantine=quarantine,
        definition_catalog=catalog,
    )
    return snapshot, quarantine, catalog, gated, probed, bindings, object_id, payload, definition_path


def _refingerprint_catalog(value: dict) -> dict:
    value.pop("catalog_fingerprint", None)
    value["catalog_fingerprint"] = definitions._fp(value)
    return value


def _refingerprint_bindings(value: dict) -> dict:
    for row in value["bindings"]:
        row.pop("binding_fingerprint", None)
        row["binding_fingerprint"] = gate._fp(row)
    value.pop("binding_manifest_fingerprint", None)
    value["binding_manifest_fingerprint"] = gate._fp(value)
    return value


def test_gate_binds_probe_to_verified_definition_catalog(tmp_path):
    snapshot, quarantine, catalog, gated, probed, bindings, *_ = _bundle(tmp_path)
    assert gated["status"] == gate.STATUS
    assert gated["definition_catalog_fingerprint"] == catalog["catalog_fingerprint"]
    assert gated["definition_source_fingerprints"] == catalog["source_fingerprints"]
    assert gated["definition_source_files_verified"] is True
    assert gated["probe_status_counts"]["UNIQUE_DEFINITION_MATCH"] == 1
    assert probed["objects"][0]["status"] == "UNIQUE_DEFINITION_MATCH"
    assert bindings["bindings"][0]["review_status"] == "REVIEW_REQUIRED"
    gate.validate_gate(
        gated,
        snapshot=snapshot,
        quarantine=quarantine,
        definition_catalog=catalog,
        probe=probed,
        proposed_bindings=bindings,
    )


def test_raw_definition_list_is_rejected(tmp_path):
    snapshot, quarantine, *_ = _quarantine(tmp_path)
    catalog, _ = _catalog(tmp_path)
    with pytest.raises(gate.CorpusQuarantineError, match="raw definition list"):
        gate.probe_with_catalog(
            snapshot=snapshot,
            quarantine=quarantine,
            definition_catalog=catalog["definitions"],
        )


def test_refingerprinted_catalog_tampering_is_rejected(tmp_path):
    snapshot, quarantine, *_ = _quarantine(tmp_path)
    catalog, _ = _catalog(tmp_path)
    changed = copy.deepcopy(catalog)
    changed["source_fingerprints"] = ["0" * 64]
    _refingerprint_catalog(changed)
    with pytest.raises(gate.CorpusQuarantineError, match="source fingerprint list mismatch"):
        gate.probe_with_catalog(
            snapshot=snapshot,
            quarantine=quarantine,
            definition_catalog=changed,
        )


def test_definition_source_file_tampering_is_rejected(tmp_path):
    snapshot, quarantine, *_ = _quarantine(tmp_path)
    catalog, definition_path = _catalog(tmp_path)
    definition_path.write_text(definition_path.read_text() + "{}\n", encoding="utf-8")
    with pytest.raises(gate.CorpusQuarantineError, match="source verification failed"):
        gate.probe_with_catalog(
            snapshot=snapshot,
            quarantine=quarantine,
            definition_catalog=catalog,
        )


def test_probe_nested_tampering_is_rejected(tmp_path):
    snapshot, quarantine, catalog, gated, probed, bindings, *_ = _bundle(tmp_path)
    changed = copy.deepcopy(probed)
    changed["objects"][0]["status"] = "NO_DEFINITION_MATCH"
    changed.pop("probe_fingerprint")
    changed["probe_fingerprint"] = gate._fp(changed)
    with pytest.raises(gate.CorpusQuarantineError, match="object fingerprint mismatch"):
        gate.validate_gate(
            gated,
            snapshot=snapshot,
            quarantine=quarantine,
            definition_catalog=catalog,
            probe=changed,
            proposed_bindings=bindings,
        )


def test_binding_cannot_substitute_another_catalog_definition(tmp_path):
    rows = [
        _definition_row(),
        _definition_row(
            instrument_id=996,
            raw_symbol="NGK26",
            start=1773400000.0,
            end=1773800000.0,
        ),
    ]
    snapshot, quarantine, catalog, gated, probed, bindings, object_id, *_ = _bundle(tmp_path, rows=rows)
    changed = copy.deepcopy(bindings)
    row = next(row for row in changed["bindings"] if row["object_id"] == object_id)
    row["definition"] = next(row for row in catalog["definitions"] if row["raw_symbol"] == "NGK26")
    _refingerprint_bindings(changed)
    changed_gate = copy.deepcopy(gated)
    changed_gate["proposed_binding_manifest_fingerprint"] = changed["binding_manifest_fingerprint"]
    changed_gate.pop("gate_fingerprint")
    changed_gate["gate_fingerprint"] = gate._fp(changed_gate)
    with pytest.raises(gate.CorpusQuarantineError, match="differs from catalog evidence"):
        gate.validate_gate(
            changed_gate,
            snapshot=snapshot,
            quarantine=quarantine,
            definition_catalog=catalog,
            probe=probed,
            proposed_bindings=changed,
        )


def test_ambiguous_definition_periods_remain_unassigned(tmp_path):
    rows = [
        _definition_row(start=1773400000.0, end=1773800000.0),
        _definition_row(start=1773450000.0, end=1773750000.0, event=1773450001.0),
    ]
    _, _, _, gated, probed, bindings, object_id, *_ = _bundle(tmp_path, rows=rows)
    evidence = probed["objects"][0]
    binding = next(row for row in bindings["bindings"] if row["object_id"] == object_id)
    assert evidence["status"] == "AMBIGUOUS_DEFINITION_MATCH"
    assert evidence["unique_definition"] is None
    assert binding["definition"] is None
    assert gated["probe_status_counts"]["AMBIGUOUS_DEFINITION_MATCH"] == 1


def test_no_definition_match_remains_unassigned(tmp_path):
    data = _trade_bytes(instrument_id=1008, raw_symbol="NGJ26")
    rows = [_definition_row(instrument_id=996, raw_symbol="NGK26")]
    _, _, _, gated, probed, bindings, object_id, *_ = _bundle(tmp_path, rows=rows, data=data)
    binding = next(row for row in bindings["bindings"] if row["object_id"] == object_id)
    assert probed["objects"][0]["status"] == "NO_DEFINITION_MATCH"
    assert binding["definition"] is None
    assert gated["probe_status_counts"]["NO_DEFINITION_MATCH"] == 1


def test_quarantine_and_definition_sources_are_immutable(tmp_path):
    snapshot, quarantine, catalog, *_rest, payload, definition_path = _bundle(tmp_path)
    quarantine_path = Path(quarantine["objects"][0]["quarantine_path"])
    before_definition = definition_path.read_bytes()
    assert quarantine_path.read_bytes() == payload
    gate.probe_with_catalog(
        snapshot=snapshot,
        quarantine=quarantine,
        definition_catalog=catalog,
    )
    assert quarantine_path.read_bytes() == payload
    assert definition_path.read_bytes() == before_definition


def test_gate_link_tampering_is_rejected_even_after_refingerprinting(tmp_path):
    snapshot, quarantine, catalog, gated, probed, bindings, *_ = _bundle(tmp_path)
    changed = copy.deepcopy(gated)
    changed["definition_fingerprints"] = []
    changed.pop("gate_fingerprint")
    changed["gate_fingerprint"] = gate._fp(changed)
    with pytest.raises(gate.CorpusQuarantineError, match="definition_fingerprints mismatch"):
        gate.validate_gate(
            changed,
            snapshot=snapshot,
            quarantine=quarantine,
            definition_catalog=catalog,
            probe=probed,
            proposed_bindings=bindings,
        )


def test_gate_status_count_tampering_is_rejected(tmp_path):
    snapshot, quarantine, catalog, gated, probed, bindings, *_ = _bundle(tmp_path)
    changed = copy.deepcopy(gated)
    changed["probe_status_counts"]["UNIQUE_DEFINITION_MATCH"] = 0
    changed.pop("gate_fingerprint")
    changed["gate_fingerprint"] = gate._fp(changed)
    with pytest.raises(gate.CorpusQuarantineError, match="status counts mismatch"):
        gate.validate_gate(
            changed,
            snapshot=snapshot,
            quarantine=quarantine,
            definition_catalog=catalog,
            probe=probed,
            proposed_bindings=bindings,
        )


def test_gate_is_deterministic(tmp_path):
    snapshot, quarantine, catalog, first, first_probe, first_bindings, *_ = _bundle(tmp_path)
    second, second_probe, second_bindings = gate.probe_with_catalog(
        snapshot=snapshot,
        quarantine=quarantine,
        definition_catalog=catalog,
    )
    assert second == first
    assert second_probe == first_probe
    assert second_bindings == first_bindings


def test_catalog_provenance_is_exposed_without_auto_approval(tmp_path):
    _, _, catalog, gated, _, bindings, *_ = _bundle(tmp_path)
    assert gated["definition_catalog_observed_at"] == catalog["observed_at"]
    assert gated["raw_definition_list_permitted"] is False
    assert gated["automatic_approval_permitted"] is False
    assert gated["session_day_assignment_status"] == "REVIEW_REQUIRED"
    assert all(row["review_status"] != "APPROVED" for row in bindings["bindings"])


def test_authority_contract_remains_disabled(tmp_path):
    _, _, _, gated, probed, _, *_ = _bundle(tmp_path)
    for artifact in (gated, probed):
        assert artifact["actual_outcomes_used"] is False
        assert artifact["may_change_blind_forecast"] is False
        assert artifact["may_change_posterior"] is False
        assert artifact["may_update_ng_brain"] is False
        assert artifact["execution_authority"] is False
        assert artifact["cme_event_contracts_mode"] == "SHADOW"
        assert artifact["brokerage_contract"] == "tastytrade_not_ibkr"
        assert artifact["options_lane_started"] is False
