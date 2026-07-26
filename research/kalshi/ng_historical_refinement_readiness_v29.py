#!/usr/bin/env python3
"""Canonical readiness v29 requiring recursive runtime/materializer provenance.

V28 requires exact versioned S3 object materialization before broad byte inspection.
V29 additionally requires a standalone gate that embeds and recursively validates the
complete runtime-observed paginated inventory receipt beside the exact materializer
receipt. This prevents a standalone materializer fingerprint from being detached from
the S3 page/head evidence that selected the exact object versions.
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
import ng_historical_refinement_readiness_v28 as v28

SCHEMA = "ng_historical_refinement_readiness.v29"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V28_OVERALL_STATUS = v28._overall_status

_MATERIALIZER_PROVENANCE = StageSpec(
    "corpus_s3_materialization_provenance",
    "ng_corpus_s3_materializer_provenance_gate.json",
    "ng_corpus_s3_materializer_provenance_gate.v1",
    "fingerprint",
    frozenset({"S3_RUNTIME_INVENTORY_AND_EXACT_MATERIALIZATION_PROVENANCE_BOUND"}),
    "ng_corpus_s3_materializer_provenance_gate",
    ("validate_gate",),
    "Recursively bind exact materialized bytes and inspection-plan lineage to the complete runtime-observed S3 inventory receipt.",
    required_fields=(
        "runtime_capture_receipt_fingerprint",
        "exact_materializer_receipt_fingerprint",
        "runtime_materialization_spec_fingerprint",
        "exact_materialization_spec_fingerprint",
        "exact_materializer_runtime_inventory_capture_fingerprint",
        "source_materializations_fingerprint",
        "source_count",
        "downstream_materialization_receipt_fingerprint",
        "plan_fingerprint",
        "provenance_lineage_fingerprint",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (*v28.STAGES[:5], _MATERIALIZER_PROVENANCE, *v28.STAGES[5:])
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v28.LINK_RULES,
    (
        "corpus_s3_inventory_capture",
        "receipt_fingerprint",
        "corpus_s3_materialization_provenance",
        "runtime_capture_receipt_fingerprint",
    ),
    (
        "corpus_s3_materialization",
        "receipt_fingerprint",
        "corpus_s3_materialization_provenance",
        "exact_materializer_receipt_fingerprint",
    ),
    (
        "corpus_s3_materialization",
        "runtime_inventory_capture_fingerprint",
        "corpus_s3_materialization_provenance",
        "exact_materializer_runtime_inventory_capture_fingerprint",
    ),
    (
        "corpus_s3_materialization",
        "source_materializations_fingerprint",
        "corpus_s3_materialization_provenance",
        "source_materializations_fingerprint",
    ),
    (
        "corpus_s3_materialization",
        "plan_fingerprint",
        "corpus_s3_materialization_provenance",
        "plan_fingerprint",
    ),
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V29"
    if "corpus_s3_materialization" not in ready_keys:
        return _V28_OVERALL_STATUS(ready_keys)
    if "corpus_s3_materialization_provenance" not in ready_keys:
        return "EXACT_S3_MATERIALIZATION_COMPLETE_RUNTIME_PROVENANCE_BINDING_INCOMPLETE"
    if "corpus_coverage" not in ready_keys:
        return "RUNTIME_MATERIALIZATION_PROVENANCE_BOUND_BROAD_BYTE_INSPECTION_INCOMPLETE"
    return _V28_OVERALL_STATUS(ready_keys)


@contextmanager
def _v28_contract() -> Iterator[None]:
    saved = (
        v28.SCHEMA,
        v28.STAGES,
        v28.LINK_RULES,
        v28._overall_status,
        v28.validate_readiness_report,
    )
    v28.SCHEMA = SCHEMA
    v28.STAGES = STAGES
    v28.LINK_RULES = LINK_RULES
    v28._overall_status = _overall_status
    # V28's own validator hard-codes coverage as stage six. V29 inserts the
    # recursive provenance gate at stage six and validates the full report below.
    v28.validate_readiness_report = lambda report: None
    try:
        yield
    finally:
        (
            v28.SCHEMA,
            v28.STAGES,
            v28.LINK_RULES,
            v28._overall_status,
            v28.validate_readiness_report,
        ) = saved


@contextmanager
def _legacy_contract() -> Iterator[None]:
    saved = (legacy.SCHEMA, legacy.STAGES, legacy.LINK_RULES)
    legacy.SCHEMA = SCHEMA
    legacy.STAGES = STAGES
    legacy.LINK_RULES = LINK_RULES
    try:
        yield
    finally:
        legacy.SCHEMA, legacy.STAGES, legacy.LINK_RULES = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v28_contract():
        report = v28.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    provenance = "corpus_s3_materialization_provenance" in ready
    inspected = "corpus_coverage" in ready
    report["materializer_provenance_artifact"] = _MATERIALIZER_PROVENANCE.filename
    report["materializer_provenance_schema"] = _MATERIALIZER_PROVENANCE.schema
    report["runtime_capture_and_exact_materializer_recursively_bound"] = provenance
    report["complete_runtime_inventory_embedded_with_materialized_byte_lineage"] = provenance
    report["broad_inspection_blocked_until_recursive_provenance"] = True
    report["broad_inspection_bound_to_recursive_materializer_provenance"] = inspected
    report["materializer_provenance_required_after_exact_materialization"] = True
    report["note"] = (
        "Readiness v29 requires exact materialization to be followed by a deterministic "
        "provenance gate that embeds and recursively validates the complete runtime-observed "
        "inventory and exact materializer receipts. Broad byte inspection cannot proceed "
        "from a detached materializer fingerprint."
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
            "readiness v29 report schema or fingerprint mismatch"
        )
    with _legacy_contract():
        legacy.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    provenance = "corpus_s3_materialization_provenance" in ready
    inspected = "corpus_coverage" in ready
    materialized = "corpus_s3_materialization" in ready
    expected = {
        "exact_s3_materializer_artifact": v28._EXACT_S3_MATERIALIZATION.filename,
        "exact_s3_materializer_schema": v28._EXACT_S3_MATERIALIZATION.schema,
        "runtime_capture_bound_to_exact_materializer": materialized,
        "exact_version_get_object_materialization_attested": materialized,
        "checksum_verified_before_atomic_replace": materialized,
        "verified_existing_local_bytes_may_be_reused": materialized,
        "broad_inspection_bound_to_exact_materialization": inspected,
        "exact_materialization_required_after_runtime_inventory": True,
        "materializer_provenance_artifact": _MATERIALIZER_PROVENANCE.filename,
        "materializer_provenance_schema": _MATERIALIZER_PROVENANCE.schema,
        "runtime_capture_and_exact_materializer_recursively_bound": provenance,
        "complete_runtime_inventory_embedded_with_materialized_byte_lineage": provenance,
        "broad_inspection_blocked_until_recursive_provenance": True,
        "broad_inspection_bound_to_recursive_materializer_provenance": inspected,
        "materializer_provenance_required_after_exact_materialization": True,
    }
    for field, item in expected.items():
        if value.get(field) != item:
            raise HistoricalRefinementReadinessError(
                f"readiness v29 {field} summary mismatch"
            )

    if provenance and not materialized:
        raise HistoricalRefinementReadinessError(
            "materializer provenance may not bypass exact S3 materialization"
        )
    if inspected and not provenance:
        raise HistoricalRefinementReadinessError(
            "broad byte inspection may not bypass recursive materializer provenance"
        )
    order = list(value.get("stage_order") or [])
    if order[:7] != [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_s3_materialization_provenance",
        "corpus_coverage",
    ]:
        raise HistoricalRefinementReadinessError(
            "recursive materializer provenance must remain between exact materialization and broad inspection"
        )
    if _MATERIALIZER_PROVENANCE.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "materializer provenance must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v28._linked_fixture_chain()
    runtime = values["corpus_s3_inventory_capture"]
    exact = values["corpus_s3_materialization"]
    provenance = legacy._fixture_artifact(
        _MATERIALIZER_PROVENANCE,
        "S3_RUNTIME_INVENTORY_AND_EXACT_MATERIALIZATION_PROVENANCE_BOUND",
    )
    provenance.update(
        {
            "runtime_capture_receipt_fingerprint": runtime["receipt_fingerprint"],
            "exact_materializer_receipt_fingerprint": exact["receipt_fingerprint"],
            "runtime_materialization_spec_fingerprint": exact[
                "source_spec_fingerprint"
            ],
            "exact_materialization_spec_fingerprint": exact[
                "source_spec_fingerprint"
            ],
            "exact_materializer_runtime_inventory_capture_fingerprint": exact[
                "runtime_inventory_capture_fingerprint"
            ],
            "source_materializations_fingerprint": exact[
                "source_materializations_fingerprint"
            ],
            "source_count": exact["source_count"],
            "downstream_materialization_receipt_fingerprint": exact[
                "downstream_materialization_receipt_fingerprint"
            ],
            "plan_fingerprint": exact["plan_fingerprint"],
            "provenance_lineage_fingerprint": "l" * 64,
            "blockers": [],
            "next_action": "RUN_BYTE_LEVEL_CORPUS_INSPECTION",
        }
    )
    provenance.pop("fingerprint", None)
    provenance["fingerprint"] = _fingerprint(provenance)
    values["corpus_s3_materialization_provenance"] = provenance
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V29"
        assert complete[
            "runtime_capture_and_exact_materializer_recursively_bound"
        ] is True

        (root / _MATERIALIZER_PROVENANCE.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_s3_materialization_provenance"
        assert blocked["broad_corpus_verified"] is False

    print("[ng_historical_refinement_readiness_v29] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v29.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
