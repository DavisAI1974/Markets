from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

import ng_corpus_s3_exact_materializer as materializer
import ng_historical_refinement_executor_v24 as executor
import ng_historical_refinement_readiness_v28 as readiness


def _spec(root: Path, *, payload: bytes = b"exact-bytes\n") -> dict[str, Any]:
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "schema": materializer.materialization.SPEC_SCHEMA,
        "allowed_roots": [str(root)],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "corpora": [
            {
                "corpus_id": "l1",
                "lane": "l1_trades",
                "sources": [
                    {
                        "source_id": "l1-20260315",
                        "materialized_path": str(root / "l1.jsonl"),
                        "s3_object": {
                            "bucket": "bucket",
                            "key": "ng/l1.jsonl",
                            "version_id": "v-exact",
                            "size_bytes": len(payload),
                            "checksum_sha256": digest,
                        },
                    }
                ],
            }
        ],
        **materializer._authority_fields(),
    }


def _runtime() -> dict[str, Any]:
    return {"source_spec": {**materializer._authority_fields()}}


def _runner(payload: bytes, calls: list[list[str]], *, version: str = "v-exact"):
    def run(argv: Sequence[str]) -> Mapping[str, Any]:
        values = list(argv)
        calls.append(values)
        Path(values[-1]).write_bytes(payload)
        return {
            "VersionId": version,
            "ContentLength": len(payload),
            "ChecksumSHA256": base64.b64encode(
                hashlib.sha256(payload).digest()
            ).decode("ascii"),
        }

    return run


def test_downloads_exact_version_with_checksum_and_atomic_replace(tmp_path: Path) -> None:
    payload = b"exact-bytes\n"
    calls: list[list[str]] = []
    evidence, blockers = materializer.materialize_source_bytes(
        _spec(tmp_path, payload=payload),
        spec_dir=tmp_path,
        runtime_receipt=_runtime(),
        runner=_runner(payload, calls),
    )
    assert blockers == []
    assert len(calls) == 1
    command = calls[0]
    assert command[command.index("--version-id") + 1] == "v-exact"
    assert command[command.index("--checksum-mode") + 1] == "ENABLED"
    assert evidence[0]["action"] == "DOWNLOADED_EXACT_S3_VERSION"
    assert evidence[0]["atomic_replace_performed"] is True
    assert (tmp_path / "l1.jsonl").read_bytes() == payload


def test_reuses_already_verified_local_bytes(tmp_path: Path) -> None:
    payload = b"exact-bytes\n"
    (tmp_path / "l1.jsonl").write_bytes(payload)
    calls: list[list[str]] = []
    evidence, blockers = materializer.materialize_source_bytes(
        _spec(tmp_path, payload=payload),
        spec_dir=tmp_path,
        runtime_receipt=_runtime(),
        runner=_runner(payload, calls),
    )
    assert blockers == []
    assert calls == []
    assert evidence[0]["action"] == "REUSED_VERIFIED_LOCAL_BYTES"
    assert evidence[0]["preexisting_bytes_verified"] is True


def test_mismatched_download_never_replaces_target(tmp_path: Path) -> None:
    expected = b"expected\n"
    bad = b"wrong-data\n"
    calls: list[list[str]] = []
    evidence, blockers = materializer.materialize_source_bytes(
        _spec(tmp_path, payload=expected),
        spec_dir=tmp_path,
        runtime_receipt=_runtime(),
        runner=_runner(bad, calls),
    )
    assert any("DOWNLOADED_SHA256_MISMATCH" in blocker for blocker in blockers)
    assert not (tmp_path / "l1.jsonl").exists()
    assert evidence[0]["atomic_replace_performed"] is False


def test_wrong_get_object_version_is_visible_blocker(tmp_path: Path) -> None:
    payload = b"exact-bytes\n"
    calls: list[list[str]] = []
    evidence, blockers = materializer.materialize_source_bytes(
        _spec(tmp_path, payload=payload),
        spec_dir=tmp_path,
        runtime_receipt=_runtime(),
        runner=_runner(payload, calls, version="other-version"),
    )
    assert any("GET_OBJECT_VERSION_ID_MISMATCH" in blocker for blocker in blockers)
    assert not (tmp_path / "l1.jsonl").exists()
    assert evidence[0]["exact_version_and_checksum_verified"] is False


def test_force_download_replaces_verified_target(tmp_path: Path) -> None:
    payload = b"exact-bytes\n"
    (tmp_path / "l1.jsonl").write_bytes(payload)
    calls: list[list[str]] = []
    evidence, blockers = materializer.materialize_source_bytes(
        _spec(tmp_path, payload=payload),
        spec_dir=tmp_path,
        runtime_receipt=_runtime(),
        runner=_runner(payload, calls),
        force_download=True,
    )
    assert blockers == []
    assert len(calls) == 1
    assert evidence[0]["atomic_replace_performed"] is True


def test_materialized_path_escape_fails_closed(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    spec["corpora"][0]["sources"][0]["materialized_path"] = str(
        tmp_path.parent / "escape.jsonl"
    )
    with pytest.raises(materializer.CorpusS3ExactMaterializerError):
        materializer.materialize_source_bytes(
            spec,
            spec_dir=tmp_path,
            runtime_receipt=_runtime(),
            runner=lambda argv: {},
        )


def test_authority_escalation_is_rejected(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    spec["options_lane_started"] = True
    with pytest.raises(materializer.CorpusS3ExactMaterializerError):
        materializer.materialize_source_bytes(
            spec,
            spec_dir=tmp_path,
            runtime_receipt=_runtime(),
            runner=lambda argv: {},
        )


def test_readiness_v28_replaces_legacy_materialization_stage() -> None:
    keys = [stage.key for stage in readiness.STAGES]
    assert keys[:6] == [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_coverage",
    ]
    assert readiness.STAGES[4].filename == "ng_corpus_s3_exact_materializer_receipt.json"
    assert readiness.STAGES[4].schema == materializer.SCHEMA
    assert any(
        rule
        == (
            "corpus_s3_inventory_capture",
            "receipt_fingerprint",
            "corpus_s3_materialization",
            "runtime_inventory_capture_fingerprint",
        )
        for rule in readiness.LINK_RULES
    )


def test_readiness_blocks_when_exact_materialization_is_missing(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES[:4]:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "corpus_s3_materialization"
    assert report["status"] == (
        "RUNTIME_OBSERVED_S3_CAPTURE_COMPLETE_EXACT_MATERIALIZATION_INCOMPLETE"
    )


def test_executor_v24_uses_exact_materializer_entrypoint() -> None:
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_materialization"] == (
        "python",
        "ng_corpus_s3_exact_materializer.py",
        "materialize",
    )
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    stage = next(
        item for item in plan["stages"] if item["key"] == "corpus_s3_materialization"
    )
    assert stage["expected_output"] == "ng_corpus_s3_exact_materializer_receipt.json"
    executor.validate_plan(plan)


def test_permanent_authority_contract_is_preserved() -> None:
    authority = materializer._authority_fields()
    assert authority["random_shuffle_used"] is False
    assert authority["blind_forecasts_immutable"] is True
    assert authority["may_update_ng_brain"] is False
    assert authority["execution_authority"] is False
    assert authority["cme_event_contracts_mode"] == "SHADOW"
    assert authority["brokerage_contract"] == "tastytrade_not_ibkr"
    assert authority["options_lane_started"] is False
