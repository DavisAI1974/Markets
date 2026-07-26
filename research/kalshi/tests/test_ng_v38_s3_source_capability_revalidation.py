from __future__ import annotations

import base64
import copy
import inspect
import json
from pathlib import Path

import pytest

import ng_historical_refinement_preflight_v37 as preflight
import ng_v38_s3_source_capability_revalidation_gate as gate

ACCOUNT = "123456789012"
REGION = "us-east-1"


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    aws_path = tmp_path / "aws"
    aws_path.write_bytes(b"aws-cli")
    plan = {"fingerprint": "plan-fp"}
    arm = {"fingerprint": "arm-fp"}
    aws_receipt = {
        "fingerprint": "aws-fp",
        "expected_account_id": ACCOUNT,
        "expected_region": REGION,
        "selected_profile": "markets-corpus",
        "effective_region": REGION,
        "external_runtime_revalidation_receipt": {
            "runtime_executables": {"aws": {"path": str(aws_path)}}
        },
    }
    monkeypatch.setattr(
        gate.aws_gate,
        "validate_gate",
        lambda value, **kwargs: copy.deepcopy(dict(value)),
    )
    source_spec = {
        "schema": gate.resolution.SPEC_SCHEMA,
        "aws_profile": "markets-corpus",
        "aws_region": REGION,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "corpora": [],
        **gate.resolution._authority_fields(),
    }
    for corpus_id, expected in gate.coverage.EXPECTED_WINDOWS.items():
        source_id = f"{corpus_id}-source"
        source_spec["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "publisher_id": 1,
                "bucket": f"markets-{corpus_id}",
                "prefix": f"ng/{corpus_id}/",
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": [
                    {
                        "source_id": source_id,
                        "day": "20260315",
                        "lane": expected["lane"],
                        "key": f"ng/{corpus_id}/source.dbn",
                        "materialized_path": f"data/{source_id}.dbn",
                        "definition": {"placeholder": True},
                    }
                ],
            }
        )
    state = {
        "bucket_region": REGION,
        "versioning": "Enabled",
        "checksum": base64.b64encode(b"1" * 32).decode("ascii"),
        "deny_operation": None,
        "version_id": "v1",
    }

    def runner(argv, timeout):
        parts = list(argv)
        operation = next(
            name
            for name in (
                "get-bucket-location",
                "get-bucket-versioning",
                "list-object-versions",
                "head-object",
            )
            if name in parts
        )
        if state["deny_operation"] == operation:
            return {
                "returncode": 255,
                "stdout": "",
                "stderr": "An error occurred (AccessDenied) when calling the operation",
            }
        if operation == "get-bucket-location":
            response = {
                "LocationConstraint": (
                    None if state["bucket_region"] == "us-east-1" else state["bucket_region"]
                )
            }
        elif operation == "get-bucket-versioning":
            response = {"Status": state["versioning"]}
        elif operation == "list-object-versions":
            response = {
                "Name": parts[parts.index("--bucket") + 1],
                "Prefix": parts[parts.index("--prefix") + 1],
                "Versions": [],
                "IsTruncated": True,
            }
        else:
            response = {
                "ContentLength": 128,
                "VersionId": state["version_id"],
                "LastModified": "2026-07-25T00:00:00Z",
                "ChecksumSHA256": state["checksum"],
                "Metadata": {},
            }
        return {"returncode": 0, "stdout": json.dumps(response), "stderr": ""}

    return plan, arm, aws_receipt, source_spec, runner, state


def _build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    plan, arm, aws_receipt, source_spec, runner, state = _fixture(tmp_path, monkeypatch)
    receipt = gate.build_gate(
        plan,
        arm,
        aws_receipt,
        source_spec,
        tmp_path,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        command_runner=runner,
    )
    return plan, arm, aws_receipt, source_spec, runner, state, receipt


def _build_with_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    **changes,
):
    plan, arm, aws_receipt, source_spec, runner, state = _fixture(tmp_path, monkeypatch)
    state.update(changes)
    receipt = gate.build_gate(
        plan,
        arm,
        aws_receipt,
        source_spec,
        tmp_path,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        command_runner=runner,
    )
    return receipt


def test_ready_gate_binds_buckets_prefixes_versioning_and_checksum_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, _, source_spec, runner, _, receipt = _build(tmp_path, monkeypatch)
    assert receipt["status"] == gate.READY
    assert receipt["required_bucket_locations_verified"] is True
    assert receipt["required_bucket_versioning_enabled_verified"] is True
    assert receipt["required_prefix_list_object_versions_access_verified"] is True
    assert receipt["checksum_enabled_head_object_access_verified"] is True
    assert receipt["corpus_completeness_claimed"] is False
    assert receipt["all_declared_objects_verified"] is False
    assert len(receipt["corpus_capability_summaries"]) == len(
        gate.coverage.EXPECTED_WINDOWS
    )
    assert all(
        row["checksum_probe_head"]["checksum_sha256"] == "31" * 32
        for row in receipt["corpus_capability_summaries"]
    )
    gate.validate_gate(
        receipt,
        plan=plan,
        arm_receipt=arm,
        source_spec=source_spec,
        repository_root=tmp_path,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        command_runner=runner,
        verify_runtime=False,
    )


@pytest.mark.parametrize(
    ("changes", "blocker"),
    [
        ({"bucket_region": "us-west-2"}, "BUCKET_REGION_MISMATCH"),
        ({"versioning": "Suspended"}, "BUCKET_VERSIONING_NOT_ENABLED"),
        ({"deny_operation": "list-object-versions"}, "LIST_OBJECT_VERSIONS_ACCESSDENIED"),
        ({"checksum": ""}, "S3_SHA256_MISSING"),
    ],
)
def test_capability_failures_are_visible_blockers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
    blocker: str,
) -> None:
    receipt = _build_with_state(tmp_path, monkeypatch, **changes)
    assert receipt["status"] == gate.BLOCKED
    assert any(blocker in value for value in receipt["blockers"])


def test_source_spec_profile_substitution_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, aws_receipt, source_spec, runner, _ = _fixture(tmp_path, monkeypatch)
    source_spec["aws_profile"] = "other"
    with pytest.raises(
        gate.V38S3SourceCapabilityRevalidationError,
        match="profile differs",
    ):
        gate.build_gate(
            plan,
            arm,
            aws_receipt,
            source_spec,
            tmp_path,
            expected_account_id=ACCOUNT,
            expected_region=REGION,
            command_runner=runner,
        )


def test_nested_refingerprinted_tampering_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, _, source_spec, runner, _, receipt = _build(tmp_path, monkeypatch)
    receipt["corpus_capability_summaries"][0]["declared_source_count"] = 999
    receipt.pop("fingerprint")
    receipt["fingerprint"] = gate._fp(receipt)
    with pytest.raises(
        gate.V38S3SourceCapabilityRevalidationError,
        match="evidence fingerprint mismatch|deterministic evidence rebuild",
    ):
        gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm,
            source_spec=source_spec,
            repository_root=tmp_path,
            expected_account_id=ACCOUNT,
            expected_region=REGION,
            command_runner=runner,
            verify_runtime=False,
        )


def test_preflight_revalidates_s3_capabilities_at_executor_delegation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    plan = {"fingerprint": "plan-fp"}
    arm = {"fingerprint": "arm-fp"}
    aws_receipt = {"fingerprint": "aws-fp"}
    s3_receipt = {
        "fingerprint": "s3-fp",
        "aws_execution_context_revalidation_receipt": aws_receipt,
    }
    source_spec = {"schema": "source-spec"}

    def validate_s3(*args, **kwargs):
        order.append("s3")
        return copy.deepcopy(s3_receipt)

    def fake_prior(*args, **kwargs):
        order.append("prior-preflight")
        kwargs["executor_runner"](plan, Path("ledger.json"))
        return {"fingerprint": "prior-preflight-fp"}

    def fake_executor(*args, **kwargs):
        order.append("executor")
        return {"status": "DRY_RUN"}

    monkeypatch.setattr(preflight, "_validated_s3_gate", validate_s3)
    monkeypatch.setattr(preflight.prior, "execute_preflight", fake_prior)
    monkeypatch.setattr(preflight, "_finalize", lambda *args, **kwargs: {"ok": True})
    result = preflight.execute_preflight(
        plan,
        arm,
        aws_receipt,
        s3_receipt,
        source_spec,
        tmp_path,
        Path("ledger.json"),
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        executor_runner=fake_executor,
    )
    assert result == {"ok": True}
    assert order == ["s3", "prior-preflight", "s3", "executor"]


def test_preflight_receipt_requires_s3_capability_boundary_fields() -> None:
    receipt = {"schema": preflight.SCHEMA}
    receipt["fingerprint"] = preflight.legacy_readiness._fingerprint(receipt)
    with pytest.raises(
        preflight.HistoricalRefinementPreflightV37Error,
        match="required_bucket_locations_verified",
    ):
        preflight.validate_receipt(receipt, verify_runtime=False)


def test_permanent_authority_wall_is_explicit() -> None:
    text = inspect.getsource(gate) + inspect.getsource(preflight)
    assert '"cme_event_contracts_mode": "SHADOW"' in text
    assert '"brokerage_contract": "tastytrade_not_ibkr"' in text
    assert '"options_lane_started": False' in text
    assert '"may_update_ng_brain": False' in text
    assert '"random_shuffle_used": False' in text
    assert '"corpus_completeness_claimed": False' in text
    assert "runtime_s3_source_capability_revalidation_at_executor_delegation" in text
