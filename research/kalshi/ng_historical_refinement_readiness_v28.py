#!/usr/bin/env python3
"""Canonical readiness v28 requiring operational exact-version S3 materialization.

V27 binds product finalization deadlines to the actual paginated checksum inventory
capture, but its materialization stage only attests local files that already exist.
V28 requires an operational materializer that downloads every missing or mismatched
object with the exact S3 version ID, verifies size and SHA-256 before atomic replacement,
and then emits the existing deterministic inspection plan and materialization receipt.
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
import ng_historical_refinement_readiness_v27 as v27

SCHEMA = "ng_historical_refinement_readiness.v28"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V27_OVERALL_STATUS = v27._overall_status

_EXACT_S3_MATERIALIZATION = StageSpec(
    "corpus_s3_materialization",
    "ng_corpus_s3_exact_materializer_receipt.json",
    "ng_corpus_s3_exact_materializer_receipt.v1",
    "receipt_fingerprint",
    frozenset({"S3_EXACT_VERSION_MATERIALIZATION_READY_FOR_BYTE_INSPECTION"}),
    "ng_corpus_s3_exact_materializer",
    ("validate_receipt",),
    "Download or reuse exact versioned/checksummed S3 corpus bytes atomically before broad byte inspection.",
    required_fields=(
        "runtime_inventory_capture_fingerprint",
        "source_spec_fingerprint",
        "source_materializations_fingerprint",
        "source_count",
        "exact_version_get_object_required",
        "checksum_mode_enabled",
        "atomic_local_replacement_required",
        "downstream_materialization_receipt_fingerprint",
        "canonical_inventory_spec_fingerprint",
        "materialization_evidence_fingerprint",
        "plan_fingerprint",
        "inventory_compiler_receipt_fingerprint",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (*v27.STAGES[:4], _EXACT_S3_MATERIALIZATION, *v27.STAGES[5:])
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v27.LINK_RULES[:5],
    (
        "corpus_s3_inventory_capture",
        "receipt_fingerprint",
        "corpus_s3_materialization",
        "runtime_inventory_capture_fingerprint",
    ),
    *v27.LINK_RULES[5:],
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V28"
    if "corpus_s3_inventory_capture" not in ready_keys:
        return _V27_OVERALL_STATUS(ready_keys)
    if "corpus_s3_materialization" not in ready_keys:
        return "RUNTIME_OBSERVED_S3_CAPTURE_COMPLETE_EXACT_MATERIALIZATION_INCOMPLETE"
    if "corpus_coverage" not in ready_keys:
        return "EXACT_S3_MATERIALIZATION_COMPLETE_BROAD_BYTE_INSPECTION_INCOMPLETE"
    return _V27_OVERALL_STATUS(ready_keys)


@contextmanager
def _v27_contract() -> Iterator[None]:
    saved = (v27.SCHEMA, v27.STAGES, v27.LINK_RULES, v27._overall_status)
    v27.SCHEMA = SCHEMA
    v27.STAGES = STAGES
    v27.LINK_RULES = LINK_RULES
    v27._overall_status = _overall_status
    try:
        yield
    finally:
        v27.SCHEMA, v27.STAGES, v27.LINK_RULES, v27._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v27_contract():
        report = v27.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    inspected = "corpus_coverage" in ready
    report["exact_s3_materializer_artifact"] = _EXACT_S3_MATERIALIZATION.filename
    report["exact_s3_materializer_schema"] = _EXACT_S3_MATERIALIZATION.schema
    report["runtime_capture_bound_to_exact_materializer"] = materialized
    report["exact_version_get_object_materialization_attested"] = materialized
    report["checksum_verified_before_atomic_replace"] = materialized
    report["verified_existing_local_bytes_may_be_reused"] = materialized
    report["broad_inspection_bound_to_exact_materialization"] = inspected
    report["exact_materialization_required_after_runtime_inventory"] = True
    report["note"] = (
        "Readiness v28 requires the runtime-observed inventory's exact materialization "
        "specification to be made operational. Missing or mismatched local objects are "
        "retrieved with exact version IDs and checksum mode, verified before atomic "
        "replacement, and then passed through the existing deterministic inspection-plan "
        "and definition-byte chain."
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
            "readiness v28 report schema or fingerprint mismatch"
        )
    with _v27_contract():
        v27.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    inspected = "corpus_coverage" in ready
    expected = {
        "exact_s3_materializer_artifact": _EXACT_S3_MATERIALIZATION.filename,
        "exact_s3_materializer_schema": _EXACT_S3_MATERIALIZATION.schema,
        "runtime_capture_bound_to_exact_materializer": materialized,
        "exact_version_get_object_materialization_attested": materialized,
        "checksum_verified_before_atomic_replace": materialized,
        "verified_existing_local_bytes_may_be_reused": materialized,
        "broad_inspection_bound_to_exact_materialization": inspected,
        "exact_materialization_required_after_runtime_inventory": True,
    }
    for field, item in expected.items():
        if value.get(field) != item:
            raise HistoricalRefinementReadinessError(
                f"readiness v28 {field} summary mismatch"
            )

    if materialized and not captured:
        raise HistoricalRefinementReadinessError(
            "exact S3 materialization may not bypass runtime-observed inventory capture"
        )
    if inspected and not materialized:
        raise HistoricalRefinementReadinessError(
            "broad byte inspection may not bypass exact S3 materialization"
        )
    order = list(value.get("stage_order") or [])
    if order[:6] != [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_coverage",
    ]:
        raise HistoricalRefinementReadinessError(
            "exact S3 materialization must remain between runtime inventory and broad inspection"
        )
    if _EXACT_S3_MATERIALIZATION.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "exact S3 materialization must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v27._linked_fixture_chain()
    old = values["corpus_s3_materialization"]
    runtime = values["corpus_s3_inventory_capture"]
    exact = legacy._fixture_artifact(
        _EXACT_S3_MATERIALIZATION,
        "S3_EXACT_VERSION_MATERIALIZATION_READY_FOR_BYTE_INSPECTION",
    )
    exact.update(
        {
            "runtime_inventory_capture_fingerprint": runtime["receipt_fingerprint"],
            "source_spec_fingerprint": old["source_spec_fingerprint"],
            "source_materializations_fingerprint": "s" * 64,
            "source_count": 2,
            "exact_version_get_object_required": True,
            "checksum_mode_enabled": True,
            "atomic_local_replacement_required": True,
            "downstream_materialization_receipt_fingerprint": "m" * 64,
            "canonical_inventory_spec_fingerprint": old[
                "canonical_inventory_spec_fingerprint"
            ],
            "materialization_evidence_fingerprint": old[
                "materialization_evidence_fingerprint"
            ],
            "plan_fingerprint": old["plan_fingerprint"],
            "inventory_compiler_receipt_fingerprint": old[
                "inventory_compiler_receipt_fingerprint"
            ],
            "blockers": [],
            "next_action": "RUN_BYTE_LEVEL_CORPUS_INSPECTION",
        }
    )
    exact.pop("receipt_fingerprint", None)
    exact["receipt_fingerprint"] = _fingerprint(exact)
    values["corpus_s3_materialization"] = exact
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V28"
        assert complete["exact_version_get_object_materialization_attested"] is True

        (root / _EXACT_S3_MATERIALIZATION.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_s3_materialization"

    print("[ng_historical_refinement_readiness_v28] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v28.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
