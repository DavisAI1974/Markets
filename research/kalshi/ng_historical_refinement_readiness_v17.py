#!/usr/bin/env python3
"""Canonical readiness v17 with target-shard to broad-source lineage binding.

V16 separates broad-corpus inspection from target-slice inspection. V17 additionally
requires every selected target-day shard to resolve to exactly one definition-byte-
bound broad source before daily basis regeneration. This prevents an independently
valid but unrelated target slice set from entering G15/G16 replay.
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
import ng_historical_refinement_readiness_v16 as v16

SCHEMA = "ng_historical_refinement_readiness.v17"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V16_OVERALL_STATUS = v16._overall_status

_TARGET_BROAD_LINEAGE = StageSpec(
    "target_slice_broad_lineage",
    "ng_target_slice_broad_lineage_gate.json",
    "ng_target_slice_broad_lineage_gate.v1",
    "fingerprint",
    frozenset({"TARGET_SLICE_BROAD_LINEAGE_READY"}),
    "ng_target_slice_broad_lineage_gate",
    ("validate_gate",),
    "Bind each selected and inspected target-day shard to exactly one verified broad-corpus source before basis regeneration.",
    required_fields=(
        "broad_definition_byte_binding_fingerprint",
        "broad_inventory_compiler_receipt_fingerprint",
        "broad_inspection_receipt_fingerprint",
        "broad_binding_set_fingerprint",
        "target_slice_bundle_fingerprint",
        "target_inspection_plan_fingerprint",
        "target_inspection_receipt_fingerprint",
        "target_catalog_fingerprint",
        "target_audit_fingerprint",
        "selected_target_source_count",
        "expected_target_source_count",
        "unique_lineage_count",
        "lineage_set_fingerprint",
    ),
    pre_outcome=True,
)


def _insert_target_broad_lineage() -> tuple[StageSpec, ...]:
    stages: list[StageSpec] = []
    for spec in v16.STAGES:
        stages.append(spec)
        if spec.key == "target_slice_coverage":
            stages.append(_TARGET_BROAD_LINEAGE)
    return tuple(stages)


STAGES = _insert_target_broad_lineage()
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v16.LINK_RULES,
    (
        "corpus_definition_byte_binding",
        "fingerprint",
        "target_slice_broad_lineage",
        "broad_definition_byte_binding_fingerprint",
    ),
    (
        "target_slice_coverage",
        "receipt_fingerprint",
        "target_slice_broad_lineage",
        "target_inspection_receipt_fingerprint",
    ),
    (
        "target_slice_coverage",
        "plan_fingerprint",
        "target_slice_broad_lineage",
        "target_inspection_plan_fingerprint",
    ),
    (
        "target_slice_coverage",
        "catalog_fingerprint",
        "target_slice_broad_lineage",
        "target_catalog_fingerprint",
    ),
    (
        "target_slice_coverage",
        "audit_fingerprint",
        "target_slice_broad_lineage",
        "target_audit_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "target_slice_bundle_fingerprint",
        "basis_inventory_regeneration",
        "slice_bundle_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "target_inspection_receipt_fingerprint",
        "basis_inventory_regeneration",
        "inspection_receipt_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "target_inspection_plan_fingerprint",
        "basis_inventory_regeneration",
        "inspection_plan_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "target_catalog_fingerprint",
        "basis_inventory_regeneration",
        "coverage_catalog_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "target_audit_fingerprint",
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V17"
    if (
        "target_slice_broad_lineage" in ready_keys
        and "basis_inventory_regeneration" not in ready_keys
    ):
        return "TARGET_SLICE_BROAD_LINEAGE_READY_BASIS_REGENERATION_INCOMPLETE"
    if (
        "target_slice_coverage" in ready_keys
        and "target_slice_broad_lineage" not in ready_keys
    ):
        return "TARGET_SLICE_INSPECTION_COMPLETE_BROAD_LINEAGE_INCOMPLETE"
    return _V16_OVERALL_STATUS(
        [key for key in ready_keys if key != "target_slice_broad_lineage"]
    )


@contextmanager
def _v16_contract() -> Iterator[None]:
    saved = (v16.SCHEMA, v16.STAGES, v16.LINK_RULES, v16._overall_status)
    v16.SCHEMA = SCHEMA
    v16.STAGES = STAGES
    v16.LINK_RULES = LINK_RULES
    v16._overall_status = _overall_status
    try:
        yield
    finally:
        v16.SCHEMA, v16.STAGES, v16.LINK_RULES, v16._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]]
    | None = None,
) -> dict[str, Any]:
    with _v16_contract():
        report = v16.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    target_inspected = "target_slice_coverage" in ready
    lineage_ready = "target_slice_broad_lineage" in ready
    basis_ready = "basis_inventory_regeneration" in ready
    report["target_slice_broad_lineage_verified"] = lineage_ready
    report["target_slice_lineage_required_before_basis_regeneration"] = True
    report["unrelated_target_slice_route_rejected"] = True
    report["basis_regeneration_bound_to_broad_lineage"] = basis_ready
    report["target_slice_inspection_alone_cannot_authorize_basis"] = True
    report["note"] = (
        "Readiness v17 requires the independently inspected target shards to map "
        "uniquely back to definition-byte-bound broad sources before exact daily "
        "basis regeneration, G15 replay, or pre-cutoff G16 work may advance."
    )
    if lineage_ready and not target_inspected:
        raise HistoricalRefinementReadinessError(
            "target broad lineage may not bypass target-slice inspection"
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
            "readiness v17 report schema or fingerprint mismatch"
        )
    with _v16_contract():
        v16.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    target_inspected = "target_slice_coverage" in ready
    lineage_ready = "target_slice_broad_lineage" in ready
    basis_ready = "basis_inventory_regeneration" in ready
    expected = {
        "target_slice_broad_lineage_verified": lineage_ready,
        "target_slice_lineage_required_before_basis_regeneration": True,
        "unrelated_target_slice_route_rejected": True,
        "basis_regeneration_bound_to_broad_lineage": basis_ready,
        "target_slice_inspection_alone_cannot_authorize_basis": True,
    }
    for field, item in expected.items():
        if value.get(field) is not item:
            raise HistoricalRefinementReadinessError(
                f"readiness v17 {field} summary mismatch"
            )
    if lineage_ready and not target_inspected:
        raise HistoricalRefinementReadinessError(
            "target broad lineage may not bypass target-slice inspection"
        )
    if basis_ready and not lineage_ready:
        raise HistoricalRefinementReadinessError(
            "basis regeneration may not bypass target-to-broad lineage"
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
                f"readiness v17 must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementReadinessError(
            "one signal authority was not preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementReadinessError("blind forecasts were not preserved")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementReadinessError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementReadinessError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _lineage_fixture(values: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    broad = values["corpus_definition_byte_binding"]
    target = values["target_slice_coverage"]
    basis = values["basis_inventory_regeneration"]
    value: dict[str, Any] = {
        "schema": "ng_target_slice_broad_lineage_gate.v1",
        "status": "TARGET_SLICE_BROAD_LINEAGE_READY",
        "broad_definition_byte_binding_fingerprint": broad["fingerprint"],
        "broad_inventory_compiler_receipt_fingerprint": broad[
            "inventory_compiler_receipt_fingerprint"
        ],
        "broad_inspection_receipt_fingerprint": broad[
            "inspection_receipt_fingerprint"
        ],
        "broad_binding_set_fingerprint": broad["binding_set_fingerprint"],
        "target_slice_bundle_fingerprint": basis["slice_bundle_fingerprint"],
        "target_inspection_plan_fingerprint": target["plan_fingerprint"],
        "target_inspection_receipt_fingerprint": target["receipt_fingerprint"],
        "target_catalog_fingerprint": target["catalog_fingerprint"],
        "target_audit_fingerprint": target["audit_fingerprint"],
        "selected_target_source_count": int(
            basis.get("selected_daily_source_count") or 48
        ),
        "expected_target_source_count": int(
            basis.get("expected_daily_source_count") or 48
        ),
        "unique_lineage_count": int(
            basis.get("selected_daily_source_count") or 48
        ),
        "broad_source_ids_used": ["broad-l1", "broad-mbo"],
        "lineage_rows": [],
        "lineage_set_fingerprint": "lineage-set",
        "blockers": [],
        "stand_down_required": False,
        "next_action": "REGENERATE_G15_G16_BASIS_FROM_LINEAGE_BOUND_TARGET_SHARDS",
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
    value["fingerprint"] = _fingerprint(value)
    return value


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v16._linked_fixture_chain()
    values["target_slice_broad_lineage"] = _lineage_fixture(values)
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V17"
        assert complete["target_slice_broad_lineage_verified"] is True

        (root / _TARGET_BROAD_LINEAGE.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "target_slice_broad_lineage"
        basis = next(
            row
            for row in blocked["stages"]
            if row["key"] == "basis_inventory_regeneration"
        )
        assert basis["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v17] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v17.json"
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
