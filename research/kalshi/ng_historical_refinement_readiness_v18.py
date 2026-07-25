#!/usr/bin/env python3
"""Canonical readiness v18 with deterministic target-shard derivation attestation.

V17 proves that each independently inspected target shard has one exact broad-source
ancestor. V18 additionally re-streams that definition-byte-bound parent through the same
historical normalizer used by the target slicer and requires the reconstructed JSONL bytes
to equal the selected target shard before basis regeneration may begin.
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
import ng_historical_refinement_readiness_v17 as v17

SCHEMA = "ng_historical_refinement_readiness.v18"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V17_OVERALL_STATUS = v17._overall_status

_TARGET_SLICE_DERIVATION = StageSpec(
    "target_slice_derivation",
    "ng_target_slice_derivation_gate.json",
    "ng_target_slice_derivation_gate.v1",
    "fingerprint",
    frozenset({"TARGET_SLICE_DERIVATION_ATTESTED"}),
    "ng_target_slice_derivation_gate",
    ("validate_gate",),
    "Re-stream each verified broad source and require deterministic normalized target-shard bytes before basis regeneration.",
    required_fields=(
        "target_slice_broad_lineage_fingerprint",
        "broad_definition_byte_binding_fingerprint",
        "target_slice_bundle_fingerprint",
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
    ),
    pre_outcome=True,
)


def _insert_target_derivation() -> tuple[StageSpec, ...]:
    stages: list[StageSpec] = []
    for spec in v17.STAGES:
        stages.append(spec)
        if spec.key == "target_slice_broad_lineage":
            stages.append(_TARGET_SLICE_DERIVATION)
    return tuple(stages)


STAGES = _insert_target_derivation()

_DIRECT_LINEAGE_TO_BASIS_FIELDS = {
    ("target_slice_bundle_fingerprint", "slice_bundle_fingerprint"),
    ("target_inspection_receipt_fingerprint", "inspection_receipt_fingerprint"),
    ("target_inspection_plan_fingerprint", "inspection_plan_fingerprint"),
    ("target_catalog_fingerprint", "coverage_catalog_fingerprint"),
    ("target_audit_fingerprint", "coverage_audit_fingerprint"),
}
_BASE_RULES = tuple(
    rule
    for rule in v17.LINK_RULES
    if not (
        rule[0] == "target_slice_broad_lineage"
        and rule[2] == "basis_inventory_regeneration"
        and (rule[1], rule[3]) in _DIRECT_LINEAGE_TO_BASIS_FIELDS
    )
)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *_BASE_RULES,
    (
        "target_slice_broad_lineage",
        "fingerprint",
        "target_slice_derivation",
        "target_slice_broad_lineage_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "broad_definition_byte_binding_fingerprint",
        "target_slice_derivation",
        "broad_definition_byte_binding_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "target_slice_bundle_fingerprint",
        "target_slice_derivation",
        "target_slice_bundle_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "target_inspection_receipt_fingerprint",
        "target_slice_derivation",
        "target_inspection_receipt_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "target_catalog_fingerprint",
        "target_slice_derivation",
        "target_catalog_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "target_audit_fingerprint",
        "target_slice_derivation",
        "target_audit_fingerprint",
    ),
    (
        "target_slice_broad_lineage",
        "lineage_set_fingerprint",
        "target_slice_derivation",
        "lineage_set_fingerprint",
    ),
    (
        "target_slice_derivation",
        "target_slice_bundle_fingerprint",
        "basis_inventory_regeneration",
        "slice_bundle_fingerprint",
    ),
    (
        "target_slice_derivation",
        "target_inspection_receipt_fingerprint",
        "basis_inventory_regeneration",
        "inspection_receipt_fingerprint",
    ),
    (
        "target_slice_derivation",
        "target_catalog_fingerprint",
        "basis_inventory_regeneration",
        "coverage_catalog_fingerprint",
    ),
    (
        "target_slice_derivation",
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
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _overall_status(ready_keys: list[str]) -> str:
    if len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V18"
    if (
        "target_slice_derivation" in ready_keys
        and "basis_inventory_regeneration" not in ready_keys
    ):
        return "TARGET_SLICE_DERIVATION_ATTESTED_BASIS_REGENERATION_INCOMPLETE"
    if (
        "target_slice_broad_lineage" in ready_keys
        and "target_slice_derivation" not in ready_keys
    ):
        return "TARGET_SLICE_LINEAGE_READY_DERIVATION_ATTESTATION_INCOMPLETE"
    return _V17_OVERALL_STATUS(
        [key for key in ready_keys if key != "target_slice_derivation"]
    )


@contextmanager
def _v17_contract() -> Iterator[None]:
    saved = (v17.SCHEMA, v17.STAGES, v17.LINK_RULES, v17._overall_status)
    v17.SCHEMA = SCHEMA
    v17.STAGES = STAGES
    v17.LINK_RULES = LINK_RULES
    v17._overall_status = _overall_status
    try:
        yield
    finally:
        v17.SCHEMA, v17.STAGES, v17.LINK_RULES, v17._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v17_contract():
        report = v17.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    lineage_ready = "target_slice_broad_lineage" in ready
    derivation_ready = "target_slice_derivation" in ready
    basis_ready = "basis_inventory_regeneration" in ready
    report["target_slice_derivation_attested"] = derivation_ready
    report["target_slice_derivation_required_before_basis_regeneration"] = True
    report["target_slice_metadata_lineage_alone_cannot_authorize_basis"] = True
    report["basis_regeneration_bound_to_derivation_attestation"] = basis_ready
    report["target_slice_source_files_rederived"] = derivation_ready
    report["note"] = (
        "Readiness v18 requires exact target-to-broad lineage and deterministic "
        "re-derivation of each selected target shard from the definition-byte-bound "
        "parent source before basis regeneration, G15 replay, or pre-cutoff G16 work."
    )
    if derivation_ready and not lineage_ready:
        raise HistoricalRefinementReadinessError(
            "target derivation may not bypass target-to-broad lineage"
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
            "readiness v18 report schema or fingerprint mismatch"
        )
    with _v17_contract():
        v17.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    lineage_ready = "target_slice_broad_lineage" in ready
    derivation_ready = "target_slice_derivation" in ready
    basis_ready = "basis_inventory_regeneration" in ready
    expected = {
        "target_slice_derivation_attested": derivation_ready,
        "target_slice_derivation_required_before_basis_regeneration": True,
        "target_slice_metadata_lineage_alone_cannot_authorize_basis": True,
        "basis_regeneration_bound_to_derivation_attestation": basis_ready,
        "target_slice_source_files_rederived": derivation_ready,
    }
    for field, item in expected.items():
        if value.get(field) is not item:
            raise HistoricalRefinementReadinessError(
                f"readiness v18 {field} summary mismatch"
            )
    if derivation_ready and not lineage_ready:
        raise HistoricalRefinementReadinessError(
            "target derivation may not bypass target-to-broad lineage"
        )
    if basis_ready and not derivation_ready:
        raise HistoricalRefinementReadinessError(
            "basis regeneration may not bypass target-shard derivation attestation"
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
                f"readiness v18 must keep {field}=false"
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
    lineage_value = values["target_slice_broad_lineage"]
    basis_value = values["basis_inventory_regeneration"]
    count = int(basis_value.get("selected_daily_source_count") or 48)
    value: dict[str, Any] = {
        "schema": "ng_target_slice_derivation_gate.v1",
        "status": "TARGET_SLICE_DERIVATION_ATTESTED",
        "target_slice_broad_lineage_fingerprint": lineage_value["fingerprint"],
        "broad_definition_byte_binding_fingerprint": lineage_value[
            "broad_definition_byte_binding_fingerprint"
        ],
        "target_slice_bundle_fingerprint": lineage_value[
            "target_slice_bundle_fingerprint"
        ],
        "target_inspection_receipt_fingerprint": lineage_value[
            "target_inspection_receipt_fingerprint"
        ],
        "target_catalog_fingerprint": lineage_value["target_catalog_fingerprint"],
        "target_audit_fingerprint": lineage_value["target_audit_fingerprint"],
        "lineage_set_fingerprint": lineage_value["lineage_set_fingerprint"],
        "derivation_algorithm": "historical_normalize_v1_canonical_jsonl_sha256",
        "expected_target_source_count": count,
        "derived_target_source_count": count,
        "exact_derivation_count": count,
        "derivation_rows": [],
        "derivation_set_fingerprint": "derivation-set",
        "blockers": [],
        "stand_down_required": False,
        "source_files_verified": True,
        "next_action": "REGENERATE_G15_G16_BASIS_FROM_DERIVATION_ATTESTED_TARGET_SHARDS",
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
    values = v17._linked_fixture_chain()
    values["target_slice_derivation"] = _derivation_fixture(values)
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V18"
        assert complete["target_slice_derivation_attested"] is True

        (root / _TARGET_SLICE_DERIVATION.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "target_slice_derivation"
        assert "basis_inventory_regeneration" not in blocked["ready_stages"]
    print("[ng_historical_refinement_readiness_v18] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v18.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
