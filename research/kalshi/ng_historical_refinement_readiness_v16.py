#!/usr/bin/env python3
"""Canonical readiness v16 with separate broad and target-slice inspection lanes.

Readiness v15 binds the completed one-year L1/dense-trades and spring/summer MBO
inspection bytes to observed definitions. The exact G15/G16 inventory path also
needs a second, distinct inspection receipt for the deterministic target-day
shards. V16 makes that separation explicit so a target-only receipt cannot prove
broad scope and a broad-corpus receipt cannot silently substitute for the daily
basis input.
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
import ng_historical_refinement_readiness_v15 as v15

SCHEMA = "ng_historical_refinement_readiness.v16"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V15_OVERALL_STATUS = v15._overall_status

_TARGET_SLICE_COVERAGE = StageSpec(
    "target_slice_coverage",
    "ng_target_slice_inspection_receipt.json",
    "ng_corpus_inspection_receipt.v1",
    "receipt_fingerprint",
    frozenset({"INSPECTION_COMPLETE"}),
    "ng_corpus_inspection",
    ("validate_receipt",),
    "Inspect the immutable target-day L1/MBO shards separately from the broad corpus before regenerating daily basis inventories.",
    required_fields=(
        "plan_fingerprint",
        "catalog_fingerprint",
        "audit_fingerprint",
        "present_count",
    ),
    pre_outcome=True,
)


def _insert_target_slice_coverage() -> tuple[StageSpec, ...]:
    stages: list[StageSpec] = []
    for spec in v15.STAGES:
        stages.append(spec)
        if spec.key == "corpus_definition_byte_binding":
            stages.append(_TARGET_SLICE_COVERAGE)
    return tuple(stages)


STAGES = _insert_target_slice_coverage()
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v15.LINK_RULES,
    (
        "target_slice_coverage",
        "receipt_fingerprint",
        "basis_inventory_regeneration",
        "inspection_receipt_fingerprint",
    ),
    (
        "target_slice_coverage",
        "plan_fingerprint",
        "basis_inventory_regeneration",
        "inspection_plan_fingerprint",
    ),
    (
        "target_slice_coverage",
        "catalog_fingerprint",
        "basis_inventory_regeneration",
        "coverage_catalog_fingerprint",
    ),
    (
        "target_slice_coverage",
        "audit_fingerprint",
        "basis_inventory_regeneration",
        "coverage_audit_fingerprint",
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V16"
    if (
        "target_slice_coverage" in ready_keys
        and "basis_inventory_regeneration" not in ready_keys
    ):
        return "TARGET_SLICE_BYTES_INSPECTED_BASIS_REGENERATION_INCOMPLETE"
    if (
        "corpus_definition_byte_binding" in ready_keys
        and "target_slice_coverage" not in ready_keys
    ):
        return "BROAD_CORPUS_DEFINITION_BYTES_BOUND_TARGET_SLICE_INSPECTION_INCOMPLETE"
    return _V15_OVERALL_STATUS(
        [key for key in ready_keys if key != "target_slice_coverage"]
    )


@contextmanager
def _v15_contract() -> Iterator[None]:
    saved = (v15.SCHEMA, v15.STAGES, v15.LINK_RULES, v15._overall_status)
    v15.SCHEMA = SCHEMA
    v15.STAGES = STAGES
    v15.LINK_RULES = LINK_RULES
    v15._overall_status = _overall_status
    try:
        yield
    finally:
        v15.SCHEMA, v15.STAGES, v15.LINK_RULES, v15._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]]
    | None = None,
) -> dict[str, Any]:
    with _v15_contract():
        report = v15.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    broad_bound = "corpus_definition_byte_binding" in ready
    target_inspected = "target_slice_coverage" in ready
    basis_ready = "basis_inventory_regeneration" in ready
    report["broad_corpus_definition_bytes_bound"] = broad_bound
    report["target_slice_bytes_inspected_before_basis_regeneration"] = (
        target_inspected
    )
    report["broad_and_target_inspection_paths_separated"] = True
    report["target_slice_receipt_cannot_satisfy_broad_scope"] = True
    report["broad_receipt_cannot_satisfy_basis_regeneration"] = True
    report["basis_regeneration_bound_to_target_slice_receipt"] = basis_ready
    report["note"] = (
        "Readiness v16 uses two independent inspection receipts: the broad inventory "
        "receipt is definition-byte-bound and feeds broad scope/alignment, while the "
        "target-slice receipt alone feeds exact daily basis regeneration and replay export."
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
            "readiness v16 report schema or fingerprint mismatch"
        )
    with _v15_contract():
        v15.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    broad_bound = "corpus_definition_byte_binding" in ready
    target_inspected = "target_slice_coverage" in ready
    basis_ready = "basis_inventory_regeneration" in ready
    expected = {
        "broad_corpus_definition_bytes_bound": broad_bound,
        "target_slice_bytes_inspected_before_basis_regeneration": target_inspected,
        "broad_and_target_inspection_paths_separated": True,
        "target_slice_receipt_cannot_satisfy_broad_scope": True,
        "broad_receipt_cannot_satisfy_basis_regeneration": True,
        "basis_regeneration_bound_to_target_slice_receipt": basis_ready,
    }
    for field, item in expected.items():
        if value.get(field) is not item:
            raise HistoricalRefinementReadinessError(
                f"readiness v16 {field} summary mismatch"
            )
    if target_inspected and not broad_bound:
        raise HistoricalRefinementReadinessError(
            "target-slice inspection may not bypass broad definition-byte binding"
        )
    if basis_ready and not target_inspected:
        raise HistoricalRefinementReadinessError(
            "basis regeneration may not bypass target-slice inspection"
        )

    for field in (
        "remote_presence_inferred",
        "actual_outcome_paths_loaded",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise HistoricalRefinementReadinessError(
                f"readiness v16 must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementReadinessError(
            "one signal authority was not preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementReadinessError(
            "blind forecasts were not preserved"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementReadinessError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementReadinessError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _target_slice_fixture(
    basis: Mapping[str, Any],
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": "ng_corpus_inspection_receipt.v1",
        "status": "INSPECTION_COMPLETE",
        "plan_fingerprint": basis["inspection_plan_fingerprint"],
        "catalog_fingerprint": basis["coverage_catalog_fingerprint"],
        "audit_fingerprint": basis["coverage_audit_fingerprint"],
        "source_statuses": {},
        "source_inspection_fingerprints": {},
        "present_count": int(basis.get("selected_daily_source_count") or 48),
        "missing_count": 0,
        "corrupt_count": 0,
        "unknown_count": 0,
        "identity_inferred_from_filename": False,
        "remote_presence_inferred": False,
        "catalog": {},
        "audit": {},
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    value["receipt_fingerprint"] = _fingerprint(value)
    return value


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v15._linked_fixture_chain()
    basis = copy.deepcopy(values["basis_inventory_regeneration"])
    target = _target_slice_fixture(basis)
    basis["inspection_receipt_fingerprint"] = target["receipt_fingerprint"]
    basis["inspection_plan_fingerprint"] = target["plan_fingerprint"]
    basis["coverage_catalog_fingerprint"] = target["catalog_fingerprint"]
    basis["coverage_audit_fingerprint"] = target["audit_fingerprint"]
    basis.pop("fingerprint", None)
    basis["fingerprint"] = _fingerprint(basis)
    values["target_slice_coverage"] = target
    values["basis_inventory_regeneration"] = basis
    return values


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["first_blocking_stage"] == "corpus_coverage"

        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V16"
        assert complete["target_slice_bytes_inspected_before_basis_regeneration"] is True

        (root / _TARGET_SLICE_COVERAGE.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "target_slice_coverage"
        basis = next(
            row
            for row in blocked["stages"]
            if row["key"] == "basis_inventory_regeneration"
        )
        assert basis["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v16] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path("renders/ng_refine_s95")
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = build_readiness_report(args.artifact_dir)
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v16.json"
    _atomic_json(output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "first_blocking_stage": report["first_blocking_stage"],
                "ready_stage_count": len(report["ready_stages"]),
                "total_stage_count": len(STAGES),
                "out": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
