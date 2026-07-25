#!/usr/bin/env python3
"""Canonical readiness v27 binding finalization deadlines to actual S3 capture time.

V26 proves an operator-declared inventory observation occurs after each product-specific
finalization lag. V27 replaces the standalone paginated inventory artifact with a
runtime-observed wrapper: the actual checksum-enabled paginated capture must start after
those deadlines, and declared observation timestamps must remain close to the measured
capture interval.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_historical_refinement_readiness as legacy
import ng_historical_refinement_readiness_v26 as v26

SCHEMA = "ng_historical_refinement_readiness.v27"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V26_OVERALL_STATUS = v26._overall_status

_RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE = StageSpec(
    "corpus_s3_inventory_capture",
    "ng_corpus_s3_runtime_observed_inventory_capture_attestation.json",
    "ng_corpus_s3_runtime_observed_inventory_capture_attestation.v1",
    "receipt_fingerprint",
    frozenset({"S3_RUNTIME_OBSERVED_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION"}),
    "ng_corpus_s3_runtime_observed_inventory_capture",
    ("validate_receipt",),
    "Bind complete checksum-enabled paginated S3 inventory to actual runtime observation timestamps and product finalization deadlines.",
    required_fields=(
        "source_spec_fingerprint",
        "finalization_contract_fingerprint",
        "paginated_inventory_receipt_fingerprint",
        "materialization_spec_fingerprint",
        "capture_started_at_utc",
        "capture_completed_at_utc",
        "runtime_finalization_checks_fingerprint",
        "declared_observation_checks_fingerprint",
        "actual_runtime_capture_bound_to_product_lags",
        "declared_observations_bound_to_runtime_interval",
        "complete_pagination_attested",
        "checksum_enabled_heads_attested",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (
    v26.STAGES[0],
    v26.STAGES[1],
    v26.STAGES[2],
    _RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE,
    *v26.STAGES[4:],
)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    v26.LINK_RULES[0],
    v26.LINK_RULES[1],
    (
        "corpus_s3_latest_version_resolution",
        "capture_spec_fingerprint",
        "corpus_s3_inventory_capture",
        "source_spec_fingerprint",
    ),
    (
        "corpus_inventory_finalization_contract",
        "receipt_fingerprint",
        "corpus_s3_inventory_capture",
        "finalization_contract_fingerprint",
    ),
    (
        "corpus_s3_inventory_capture",
        "materialization_spec_fingerprint",
        "corpus_s3_materialization",
        "source_spec_fingerprint",
    ),
    *v26.LINK_RULES[4:],
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _overall_status(ready_keys: list[str]) -> str:
    if len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V27"
    if "corpus_expected_day_contract" not in ready_keys:
        return "CORPUS_EXPECTED_DAY_CONTRACT_INCOMPLETE"
    if "corpus_inventory_finalization_contract" not in ready_keys:
        return "CORPUS_INVENTORY_FINALIZATION_CONTRACT_INCOMPLETE"
    if "corpus_s3_latest_version_resolution" not in ready_keys:
        return "INVENTORY_FINALIZATION_COMPLETE_S3_VERSION_RESOLUTION_INCOMPLETE"
    if "corpus_s3_inventory_capture" not in ready_keys:
        return "S3_VERSION_RESOLUTION_COMPLETE_RUNTIME_OBSERVED_CAPTURE_INCOMPLETE"
    if "corpus_s3_materialization" not in ready_keys:
        return "RUNTIME_OBSERVED_S3_CAPTURE_COMPLETE_MATERIALIZATION_INCOMPLETE"
    return _V26_OVERALL_STATUS(ready_keys)


@contextmanager
def _v26_contract() -> Iterator[None]:
    saved = (v26.SCHEMA, v26.STAGES, v26.LINK_RULES, v26._overall_status)
    v26.SCHEMA = SCHEMA
    v26.STAGES = STAGES
    v26.LINK_RULES = LINK_RULES
    v26._overall_status = _overall_status
    try:
        yield
    finally:
        v26.SCHEMA, v26.STAGES, v26.LINK_RULES, v26._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v26_contract():
        report = v26.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    runtime_capture = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    report["runtime_observed_inventory_artifact"] = (
        _RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE.filename
    )
    report["runtime_observed_inventory_schema"] = (
        _RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE.schema
    )
    report["actual_runtime_capture_bound_to_product_lags"] = runtime_capture
    report["declared_inventory_observations_bound_to_runtime_interval"] = runtime_capture
    report["paginated_checksum_inventory_embedded_and_validated"] = runtime_capture
    report["materialization_bound_to_runtime_observed_capture"] = materialized
    report["runtime_observation_required_before_materialization"] = True
    report["note"] = (
        "Readiness v27 requires the actual checksum-enabled paginated S3 capture to "
        "begin after every evidence-fingerprinted product finalization deadline. "
        "Declared inventory observations must remain within the allowed skew of the "
        "measured capture interval, and the resulting materialization specification "
        "must come from that runtime-observed capture."
    )
    report.pop("fingerprint", None)
    report["fingerprint"] = _fingerprint(report)
    validate_readiness_report(report)
    return report


def validate_readiness_report(report: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(report))
    observed = value.get("fingerprint")
    payload = copy.deepcopy(value)
    payload.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != _fingerprint(payload):
        raise HistoricalRefinementReadinessError(
            "readiness v27 report schema or fingerprint mismatch"
        )
    with _v26_contract():
        v26.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    runtime_capture = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    expected = {
        "runtime_observed_inventory_artifact": _RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE.filename,
        "runtime_observed_inventory_schema": _RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE.schema,
        "actual_runtime_capture_bound_to_product_lags": runtime_capture,
        "declared_inventory_observations_bound_to_runtime_interval": runtime_capture,
        "paginated_checksum_inventory_embedded_and_validated": runtime_capture,
        "materialization_bound_to_runtime_observed_capture": materialized,
        "runtime_observation_required_before_materialization": True,
    }
    for field, item in expected.items():
        if value.get(field) != item:
            raise HistoricalRefinementReadinessError(
                f"readiness v27 {field} summary mismatch"
            )

    ready_set = set(ready)
    if runtime_capture and "corpus_inventory_finalization_contract" not in ready_set:
        raise HistoricalRefinementReadinessError(
            "runtime-observed inventory capture may not bypass finalization"
        )
    if materialized and not runtime_capture:
        raise HistoricalRefinementReadinessError(
            "materialization may not bypass runtime-observed inventory capture"
        )
    order = list(value.get("stage_order") or [])
    if order[:5] != [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
    ]:
        raise HistoricalRefinementReadinessError(
            "runtime-observed inventory capture must remain between S3 resolution and materialization"
        )
    if _RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "runtime-observed inventory capture must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v26._linked_fixture_chain()
    resolution = values["corpus_s3_latest_version_resolution"]
    finalization = values["corpus_inventory_finalization_contract"]
    materialization = values["corpus_s3_materialization"]
    runtime = legacy._fixture_artifact(
        _RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE,
        "S3_RUNTIME_OBSERVED_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION",
    )
    runtime.update(
        {
            "source_spec_fingerprint": resolution["capture_spec_fingerprint"],
            "finalization_contract_fingerprint": finalization["receipt_fingerprint"],
            "paginated_inventory_receipt_fingerprint": "p" * 64,
            "materialization_spec_fingerprint": materialization[
                "source_spec_fingerprint"
            ],
            "capture_started_at_utc": "2026-07-25T00:00:00Z",
            "capture_completed_at_utc": "2026-07-25T00:00:02Z",
            "runtime_finalization_checks_fingerprint": "r" * 64,
            "declared_observation_checks_fingerprint": "d" * 64,
            "actual_runtime_capture_bound_to_product_lags": True,
            "declared_observations_bound_to_runtime_interval": True,
            "complete_pagination_attested": True,
            "checksum_enabled_heads_attested": True,
            "blockers": [],
            "next_action": "RUN_S3_MATERIALIZATION_ATTESTATION",
        }
    )
    runtime.pop("receipt_fingerprint", None)
    runtime["receipt_fingerprint"] = _fingerprint(runtime)
    values["corpus_s3_inventory_capture"] = runtime
    return values


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["first_blocking_stage"] == "corpus_expected_day_contract"

        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V27"
        assert complete["actual_runtime_capture_bound_to_product_lags"] is True

        (root / _RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_s3_inventory_capture"

    print("[ng_historical_refinement_readiness_v27] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("renders/ng_refine_s95"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = build_readiness_report(args.artifact_dir)
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v27.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
