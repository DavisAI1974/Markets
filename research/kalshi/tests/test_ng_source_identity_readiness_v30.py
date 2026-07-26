from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ng_corpus_inspection as inspection
import ng_corpus_source_identity_attestation as identity
import ng_historical_refinement_executor_v26 as executor
import ng_historical_refinement_readiness_v30 as readiness


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, *, dbn: bool = False, mutate=None):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    corpora = []
    materializations = []
    for source_id, lane, corpus_id, day in (
        ("l1", "l1_trades", inspection.coverage.L1_CORPUS_ID, "20260313"),
        ("mbo", "mbo", inspection.coverage.MBO_CORPUS_ID, "20260313"),
    ):
        path = data / f"{source_id}{'.dbn' if dbn else '.jsonl'}"
        row = {
            "event_type": "trade" if lane == "l1_trades" else "mbo",
            "dataset": inspection.DATASET,
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "definition_date": "20260313",
            "ts_event_s": 1.0,
            "source_sequence": 1,
            "side": "B",
            "price": 3.0,
            "size": 1,
            "action": "A" if lane == "mbo" else None,
            "order_id": 9,
        }
        if mutate:
            mutate(source_id, lane, row)
        if dbn:
            path.write_bytes(f"fake-{source_id}".encode())
        else:
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        digest = _sha(path)
        definition = inspection.definition_observation(
            dataset=inspection.DATASET,
            publisher_id=1,
            instrument_id=1008,
            raw_symbol="NGJ26",
            definition_date="20260313",
            definition_start_s=0.0,
            definition_end_s=2.0,
            observed_from=f"test:{source_id}",
            observed_at="2026-07-25T00:00:00Z",
            source_sha256=digest,
            source_size_bytes=path.stat().st_size,
        )
        window = inspection.coverage.EXPECTED_WINDOWS[corpus_id]
        corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": lane,
                "declared_window": {
                    "start": window["start"],
                    "end_exclusive": window["end_exclusive"],
                },
                "publisher_id": 1,
                "expected_days": [day],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "inventory_observed_at": "2026-07-25T00:00:00Z",
                "sources": [
                    {
                        "source_id": source_id,
                        "day": day,
                        "lane": lane,
                        "materialized_path": str(path),
                        "location": f"s3://test/{source_id}",
                        "definition": definition,
                    }
                ],
            }
        )
        materializations.append(
            {
                "corpus_id": corpus_id,
                "source_id": source_id,
                "materialized_path": str(path.resolve()),
                "expected_size_bytes": path.stat().st_size,
                "expected_sha256": digest,
            }
        )
    plan = {
        "schema": inspection.PLAN_SCHEMA,
        "market": "NG",
        "dataset": inspection.DATASET,
        "allowed_roots": [str(data.resolve())],
        "corpora": corpora,
        "identity_may_be_inferred_from_filename": False,
        "remote_presence_inferred": False,
        **inspection._base_authority(),
    }
    plan["plan_fingerprint"] = inspection._fp(plan)
    provenance = {
        "schema": identity.materializer_provenance.SCHEMA,
        "status": identity.materializer_provenance.READY_STATUS,
        "fingerprint": "p" * 64,
        "plan_fingerprint": plan["plan_fingerprint"],
        "source_materializations_fingerprint": identity._fp(materializations),
        "exact_materializer_receipt": {"source_materializations": materializations},
        "blockers": [],
        **identity._authority_fields(),
    }
    return plan, provenance


def _build(plan, provenance, *, loader=identity._load_dbn_store):
    return identity.build_attestation(
        provenance,
        plan,
        provenance_validator=lambda value: value,
        store_loader=loader,
    )


class FakeStore:
    def __init__(self, *, dataset: str, schema: str, row: dict, mapping: bool = True):
        self.metadata = SimpleNamespace(dataset=dataset, schema=schema)
        self.symbology = {
            "stype_in": "raw_symbol",
            "stype_out": "instrument_id",
            "mappings": (
                {
                    "NGJ26": [
                        {
                            "start_date": "2026-03-13",
                            "end_date": "2026-03-14",
                            "symbol": "1008",
                        }
                    ]
                }
                if mapping
                else {}
            ),
        }
        self.rows = [row]

    def __iter__(self):
        return iter(self.rows)


def _dbn_loader(plan, *, dataset=inspection.DATASET, mapping=True, event_ts=1.0):
    stores = {}
    for corpus in plan["corpora"]:
        lane = corpus["lane"]
        source = corpus["sources"][0]
        row = {
            "publisher_id": 1,
            "instrument_id": 1008,
            "ts_event": event_ts,
            "source_sequence": 1,
            "side": "B",
            "price": 3.0,
            "size": 1,
            "action": "A" if lane == "mbo" else None,
            "order_id": 9,
        }
        stores[str(Path(source["materialized_path"]).resolve())] = FakeStore(
            dataset=dataset,
            schema="trades" if lane == "l1_trades" else "mbo",
            row=row,
            mapping=mapping,
        )
    return lambda path: stores[str(path.resolve())]


def test_jsonl_exact_identity_ready(tmp_path):
    plan, provenance = _fixture(tmp_path)
    receipt = _build(plan, provenance)
    assert receipt["status"] == identity.READY_STATUS
    assert receipt["all_source_native_identities_attested"] is True


def test_jsonl_missing_raw_symbol_blocks(tmp_path):
    def mutate(source_id, lane, row):
        if source_id == "l1":
            row.pop("raw_symbol")

    plan, provenance = _fixture(tmp_path, mutate=mutate)
    receipt = _build(plan, provenance)
    assert any("JSONL_RAW_SYMBOL_MISSING" in item for item in receipt["blockers"])


def test_publisher_mismatch_blocks(tmp_path):
    def mutate(source_id, lane, row):
        if source_id == "mbo":
            row["publisher_id"] = 2

    plan, provenance = _fixture(tmp_path, mutate=mutate)
    receipt = _build(plan, provenance)
    assert any("RECORD_PUBLISHER_ID_MISMATCH" in item for item in receipt["blockers"])


def test_dbn_metadata_symbology_and_record_headers_ready(tmp_path):
    plan, provenance = _fixture(tmp_path, dbn=True)
    receipt = _build(plan, provenance, loader=_dbn_loader(plan))
    assert receipt["status"] == identity.READY_STATUS


def test_dbn_dataset_or_mapping_mismatch_blocks(tmp_path):
    plan, provenance = _fixture(tmp_path, dbn=True)
    wrong_dataset = _build(
        plan, provenance, loader=_dbn_loader(plan, dataset="OTHER.DATASET")
    )
    assert any("DBN_METADATA_DATASET_MISMATCH" in item for item in wrong_dataset["blockers"])
    missing_mapping = _build(plan, provenance, loader=_dbn_loader(plan, mapping=False))
    assert any("DBN_SYMBOLOGY_MAPPING_MISSING" in item for item in missing_mapping["blockers"])


def test_definition_period_violation_blocks(tmp_path):
    plan, provenance = _fixture(tmp_path, dbn=True)
    receipt = _build(plan, provenance, loader=_dbn_loader(plan, event_ts=3.0))
    assert any("RECORD_EVENT_OUTSIDE_DEFINITION_PERIOD" in item for item in receipt["blockers"])


def test_nested_refingerprint_cannot_manufacture_readiness(tmp_path):
    plan, provenance = _fixture(tmp_path)
    receipt = _build(plan, provenance)
    attacked = copy.deepcopy(receipt)
    attacked["source_identity_evidence"][0]["source_native_identity_attested"] = False
    attacked.pop("fingerprint")
    attacked["fingerprint"] = identity._fp(attacked)
    with pytest.raises(identity.CorpusSourceIdentityError):
        identity.validate_attestation(
            attacked,
            provenance_validator=lambda value: value,
        )


def test_authority_escalation_rejected(tmp_path):
    plan, provenance = _fixture(tmp_path)
    receipt = _build(plan, provenance)
    receipt["options_lane_started"] = True
    receipt.pop("fingerprint")
    receipt["fingerprint"] = identity._fp(receipt)
    with pytest.raises(identity.CorpusSourceIdentityError):
        identity.validate_attestation(
            receipt,
            provenance_validator=lambda value: value,
        )


def test_readiness_and_executor_place_identity_before_coverage():
    keys = [spec.key for spec in readiness.STAGES]
    assert keys[:8] == [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_s3_materialization_provenance",
        "corpus_source_identity_attestation",
        "corpus_coverage",
    ]
    stages = [
        {
            "key": spec.key,
            "expected_output": spec.filename,
            "suggested_entrypoint": list(executor.SUGGESTED_ENTRYPOINTS.get(spec.key, ())),
            "requires_fixed_outcomes": not spec.pre_outcome,
        }
        for spec in readiness.STAGES
    ]
    executor._check_v30_plan_contract({"stages": stages})
    attacked = copy.deepcopy(stages)
    attacked[6]["suggested_entrypoint"] = ["python", "other.py"]
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor._check_v30_plan_contract({"stages": attacked})


def test_permanent_authority_controls():
    authority = identity._authority_fields()
    identity._authority(authority, label="test")
    assert authority["random_shuffle_used"] is False
    assert authority["blind_forecasts_immutable"] is True
    assert authority["may_update_ng_brain"] is False
    assert authority["cme_event_contracts_mode"] == "SHADOW"
    assert authority["brokerage_contract"] == "tastytrade_not_ibkr"
    assert authority["options_lane_started"] is False
