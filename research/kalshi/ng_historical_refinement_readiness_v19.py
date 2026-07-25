#!/usr/bin/env python3
"""Canonical readiness v19 with plan-bound target-shard derivation.

V18 requires target bytes to be deterministically re-derived from verified broad source
bytes. V19 also binds the exact target inspection plan through that derivation artifact and
into basis regeneration, eliminating a plan-substitution gap.
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
import ng_historical_refinement_readiness_v18 as v18

SCHEMA = "ng_historical_refinement_readiness.v19"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V18_OVERALL_STATUS = v18._overall_status

_TARGET_SLICE_DERIVATION_V2 = StageSpec(
    "target_slice_derivation",
    "ng_target_slice_derivation_gate_v2.json",
    "ng_target_slice_derivation_gate.v2",
    "fingerprint",
    frozenset({"TARGET_SLICE_DERIVATION_ATTESTED_V2"}),
    "ng_target_slice_derivation_gate_v2",
    ("validate_gate",),
    "Re-derive target bytes from broad sources and bind the exact target inspection plan before basis regeneration.",
    required_fields=(
        "target_slice_broad_lineage_fingerprint",
        "broad_definition_byte_binding_fingerprint",
        "target_slice_bundle_fingerprint",
        "target_inspection_plan_fingerprint",
        "target_inspection_receipt_fingerprint",
        "target_catalog_fingerprint",
        "target_audit_fingerprint",
        "lineage_set_fingerprint",
        "derivation_algorithm",
        "expected_target_source_count",
        "derived_target_source_count",
        "exact_derivation_count",
        "derivation_set_fingerprint",
        "source_files_verified",
        "target_plan_bound_to_derivation",
        "basis_may_substitute_target_plan",
    ),
    pre_outcome=True,
)

STAGES = tuple(
    _TARGET_SLICE_DERIVATION_V2 if spec.key == "target_slice_derivation" else spec
    for spec in v18.STAGES
)

LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v18.LINK_RULES,
    (
        "target_slice_broad_lineage",
        "target_inspection_plan_fingerprint",
        "target_slice_derivation",
        "target_inspection_plan_fingerprint",
    ),
    (
        "target_slice_derivation",
        "target_inspection_plan_fingerprint",
        "basis_inventory_regeneration",
        "inspection_plan_fingerprint",
    ),
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _overall_status(ready_keys: list[str]) -> str:
    if len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V19"
    if (
        "target_slice_derivation" in ready_keys
        and "basis_inventory_regeneration" not in ready_keys
    ):
        return "PLAN_BOUND_TARGET_DERIVATION_READY_BASIS_REGENERATION_INCOMPLETE"
    return _V18_OVERALL_STATUS(ready_keys)


@contextmanager
def _v18_contract() -> Iterator[None]:
    saved = (v18.SCHEMA, v18.STAGES, v18.LINK_RULES, v18._overall_status)
    v18.SCHEMA = SCHEMA
    v18.STAGES = STAGES
    v18.LINK_RULES = LINK_RULES
    v18._overall_status = _overall_status
    try:
        yield
    finally:
        v18.SCHEMA, v18.STAGES, v18.LINK_RULES, v18._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v18_contract():
        report = v18.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    derivation_ready = "target_slice_derivation" in ready
    basis_ready = "basis_inventory_regeneration" in ready
    report["target_slice_derivation_plan_bound"] = derivation_ready
    report["target_inspection_plan_required_through_derivation"] = True
    report["basis_target_plan_substitution_rejected"] = True
    report["basis_regeneration_bound_to_plan_attested_derivation"] = basis_ready
    report["note"] = (
        "Readiness v19 requires deterministic target-shard re-derivation and carries "
        "the exact target inspection-plan fingerprint through the attestation into "
        "basis regeneration before G15 replay or pre-cutoff G16 work may advance."
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
            "readiness v19 report schema or fingerprint mismatch"
        )
    with _v18_contract():
        v18.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    derivation_ready = "target_slice_derivation" in ready
    basis_ready = "basis_inventory_regeneration" in ready
    expected = {
        "target_slice_derivation_plan_bound": derivation_ready,
        "target_inspection_plan_required_through_derivation": True,
        "basis_target_plan_substitution_rejected": True,
        "basis_regeneration_bound_to_plan_attested_derivation": basis_ready,
    }
    for field, item in expected.items():
        if value.get(field) is not item:
            raise HistoricalRefinementReadinessError(
                f"readiness v19 {field} summary mismatch"
            )
    if basis_ready and not derivation_ready:
        raise HistoricalRefinementReadinessError(
            "basis regeneration may not bypass plan-bound target derivation"
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
                f"readiness v19 must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementReadinessError("one signal authority was not preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementReadinessError("blind forecasts were not preserved")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementReadinessError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementReadinessError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _derivation_fixture(values: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    base = copy.deepcopy(dict(v18._derivation_fixture(values)))
    base.pop("fingerprint", None)
    lineage = values["target_slice_broad_lineage"]
    base["schema"] = "ng_target_slice_derivation_gate.v2"
    base["status"] = "TARGET_SLICE_DERIVATION_ATTESTED_V2"
    base["target_inspection_plan_fingerprint"] = lineage[
        "target_inspection_plan_fingerprint"
    ]
    base["target_plan_bound_to_derivation"] = True
    base["basis_may_substitute_target_plan"] = False
    base["fingerprint"] = _fingerprint(base)
    return base


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v18._linked_fixture_chain()
    values["target_slice_derivation"] = _derivation_fixture(values)
    return values


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V19"
        assert complete["target_slice_derivation_plan_bound"] is True
        (root / _TARGET_SLICE_DERIVATION_V2.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "target_slice_derivation"
    print("[ng_historical_refinement_readiness_v19] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v19.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
