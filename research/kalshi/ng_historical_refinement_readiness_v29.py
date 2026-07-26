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
import ng_historical_refinement_readiness_v25 as v25
import ng_historical_refinement_readiness_v26 as v26
import ng_historical_refinement_readiness_v27 as v27
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
        "canonical_inventory_spec_fingerprint",
        "materialization_evidence_fingerprint",
        "plan_fingerprint",
        "inventory_compiler_receipt_fingerprint",
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
    (
        "corpus_s3_materialization_provenance",
        "plan_fingerprint",
        "corpus_definition_byte_binding",
        "plan_fingerprint",
    ),
    (
        "corpus_s3_materialization_provenance",
        "inventory_compiler_receipt_fingerprint",
        "corpus_definition_byte_binding",
        "inventory_compiler_receipt_fingerprint",
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
    delegated = [
        key
        for key in ready_keys
        if key != "corpus_s3_materialization_provenance"
    ]
    return _V28_OVERALL_STATUS(delegated)


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


def _summary_fields(ready: Sequence[str]) -> dict[str, Any]:
    ready_set = set(ready)
    expected_days = "corpus_expected_day_contract" in ready_set
    finalized = "corpus_inventory_finalization_contract" in ready_set
    resolved = "corpus_s3_latest_version_resolution" in ready_set
    runtime_capture = "corpus_s3_inventory_capture" in ready_set
    materialized = "corpus_s3_materialization" in ready_set
    provenance = "corpus_s3_materialization_provenance" in ready_set
    inspected = "corpus_coverage" in ready_set
    definition_bound = "corpus_definition_byte_binding" in ready_set
    return {
        "expected_day_contract_artifact": v25._EXPECTED_DAY_CONTRACT.filename,
        "expected_day_contract_schema": v25._EXPECTED_DAY_CONTRACT.schema,
        "complete_canonical_calendar_partition_attested": expected_days,
        "operator_shortened_expected_day_lists_rejected": True,
        "non_saturday_exclusions_evidence_bound": expected_days,
        "g15_g16_target_days_must_remain_expected": True,
        "s3_resolution_bound_to_expected_day_contract": resolved,
        "calendar_contract_required_before_any_s3_inventory_request": True,
        "inventory_finalization_contract_artifact": v26._INVENTORY_FINALIZATION_CONTRACT.filename,
        "inventory_finalization_contract_schema": v26._INVENTORY_FINALIZATION_CONTRACT.schema,
        "product_specific_finalization_lags_attested": finalized,
        "inventory_observation_after_corpus_end_attested": finalized,
        "lag_policy_evidence_fingerprints_bound": finalized,
        "s3_resolution_bound_to_finalized_inventory_snapshot": resolved,
        "expected_day_contract_bound_to_finalization_contract": finalized,
        "finalization_contract_required_before_any_s3_request": True,
        "runtime_observed_inventory_artifact": v27._RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE.filename,
        "runtime_observed_inventory_schema": v27._RUNTIME_OBSERVED_S3_INVENTORY_CAPTURE.schema,
        "actual_runtime_capture_bound_to_product_lags": runtime_capture,
        "declared_inventory_observations_bound_to_runtime_interval": runtime_capture,
        "paginated_checksum_inventory_embedded_and_validated": runtime_capture,
        "materialization_bound_to_runtime_observed_capture": materialized,
        "runtime_observation_required_before_materialization": True,
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
        "definition_binding_bound_to_recursive_materializer_provenance": definition_bound,
        "materializer_provenance_required_after_exact_materialization": True,
    }


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    # Build directly against the canonical evaluator. Older wrapper versions hard-code
    # historical prefix lengths, so recursively re-entering them after inserting a new
    # stage can reject a valid newer order before the latest validator runs.
    with _legacy_contract():
        report = legacy.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    report["status"] = _overall_status(ready)
    report.update(_summary_fields(ready))
    report["note"] = (
        "Readiness v29 requires exact materialization to be followed by a deterministic "
        "provenance gate that embeds and recursively validates the complete runtime-observed "
        "inventory and exact materializer receipts. Its plan and inventory-compiler "
        "fingerprints also bind into definition-byte verification before any replay."
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
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError(
            "readiness v29 overall status mismatch"
        )
    for field, item in _summary_fields(ready).items():
        if value.get(field) != item:
            raise HistoricalRefinementReadinessError(
                f"readiness v29 {field} summary mismatch"
            )

    ready_set = set(ready)
    provenance = "corpus_s3_materialization_provenance" in ready_set
    inspected = "corpus_coverage" in ready_set
    materialized = "corpus_s3_materialization" in ready_set
    definition_bound = "corpus_definition_byte_binding" in ready_set
    if provenance and not materialized:
        raise HistoricalRefinementReadinessError(
            "materializer provenance may not bypass exact S3 materialization"
        )
    if inspected and not provenance:
        raise HistoricalRefinementReadinessError(
            "broad byte inspection may not bypass recursive materializer provenance"
        )
    if definition_bound and not provenance:
        raise HistoricalRefinementReadinessError(
            "definition-byte binding may not bypass recursive materializer provenance"
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
            "canonical_inventory_spec_fingerprint": exact[
                "canonical_inventory_spec_fingerprint"
            ],
            "materialization_evidence_fingerprint": exact[
                "materialization_evidence_fingerprint"
            ],
            "plan_fingerprint": exact["plan_fingerprint"],
            "inventory_compiler_receipt_fingerprint": exact[
                "inventory_compiler_receipt_fingerprint"
            ],
            "provenance_lineage_fingerprint": "l" * 64,
            "blockers": [],
            "next_action": "RUN_BYTE_LEVEL_CORPUS_INSPECTION",
            "actual_outcomes_used": False,
            "paid_live_data_assumed": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_change_blind_forecast": False,
            "may_change_posterior": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
        }
    )
    provenance.pop("fingerprint", None)
    provenance["fingerprint"] = _fingerprint(provenance)
    values["corpus_s3_materialization_provenance"] = provenance

    definition = values.get("corpus_definition_byte_binding")
    if isinstance(definition, dict):
        definition["plan_fingerprint"] = provenance["plan_fingerprint"]
        definition["inventory_compiler_receipt_fingerprint"] = provenance[
            "inventory_compiler_receipt_fingerprint"
        ]
        definition.pop("fingerprint", None)
        definition["fingerprint"] = _fingerprint(definition)
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

        final_stage = STAGES[-1]
        (root / final_stage.filename).unlink()
        partial = build_readiness_report(root, validator_overrides=overrides)
        assert partial["status"] != "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V28"
        assert partial["status"] != "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V29"
        _atomic_json(root / final_stage.filename, values[final_stage.key])

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
