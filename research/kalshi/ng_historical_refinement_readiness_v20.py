#!/usr/bin/env python3
"""Canonical readiness v20 requiring exact S3-to-local materialization attestation.

V19 proves that target shards are uniquely descended from definition-bound broad
sources and deterministically re-derived before basis regeneration. V20 closes the
remaining front-door gap: the broad inspection plan must first be regenerated from
an explicit versioned/checksummed S3 inventory whose materialized local bytes match
both the declared remote object and the observed definition record.
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
import ng_historical_refinement_readiness_v19 as v19

SCHEMA = "ng_historical_refinement_readiness.v20"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V19_OVERALL_STATUS = v19._overall_status

_S3_MATERIALIZATION = StageSpec(
    "corpus_s3_materialization",
    "ng_corpus_s3_materialization_attestation.json",
    "ng_corpus_s3_materialization_attestation.v1",
    "receipt_fingerprint",
    frozenset({"S3_MATERIALIZATION_ATTESTED_READY_FOR_BYTE_INSPECTION"}),
    "ng_corpus_s3_materialization_attestation",
    ("validate_receipt",),
    "Attest exact versioned/checksummed S3 objects to local source bytes and observed definitions before broad byte inspection.",
    required_fields=(
        "source_spec_fingerprint",
        "canonical_inventory_spec_fingerprint",
        "materialization_evidence_fingerprint",
        "plan_fingerprint",
        "inventory_compiler_receipt_fingerprint",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (_S3_MATERIALIZATION, *v19.STAGES)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "corpus_s3_materialization",
        "plan_fingerprint",
        "corpus_definition_byte_binding",
        "plan_fingerprint",
    ),
    (
        "corpus_s3_materialization",
        "inventory_compiler_receipt_fingerprint",
        "corpus_definition_byte_binding",
        "inventory_compiler_receipt_fingerprint",
    ),
    *v19.LINK_RULES,
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V20"
    if "corpus_s3_materialization" in ready_keys and "corpus_coverage" not in ready_keys:
        return "S3_MATERIALIZATION_ATTESTED_BROAD_BYTE_INSPECTION_INCOMPLETE"
    if "corpus_s3_materialization" not in ready_keys:
        return "S3_MATERIALIZATION_ATTESTATION_INCOMPLETE"
    return _V19_OVERALL_STATUS(
        [key for key in ready_keys if key != "corpus_s3_materialization"]
    )


@contextmanager
def _v19_contract() -> Iterator[None]:
    saved = (v19.SCHEMA, v19.STAGES, v19.LINK_RULES, v19._overall_status)
    v19.SCHEMA = SCHEMA
    v19.STAGES = STAGES
    v19.LINK_RULES = LINK_RULES
    v19._overall_status = _overall_status
    try:
        yield
    finally:
        v19.SCHEMA, v19.STAGES, v19.LINK_RULES, v19._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v19_contract():
        report = v19.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    materialized = "corpus_s3_materialization" in ready
    inspected = "corpus_coverage" in ready
    definition_bound = "corpus_definition_byte_binding" in ready
    report["s3_materialization_attested"] = materialized
    report["s3_materialization_required_before_broad_inspection"] = True
    report["remote_inventory_may_not_be_inferred"] = True
    report["broad_inspection_bound_to_s3_materialization"] = inspected
    report["definition_binding_bound_to_s3_materialization"] = definition_bound
    report["note"] = (
        "Readiness v20 requires an explicit versioned/checksummed S3 inventory and "
        "attested local materialization before broad byte inspection. The same compiled "
        "inspection plan and inventory receipt must flow into definition-byte binding, "
        "target derivation, G15 replay, and the pre-cutoff G16 chain."
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
            "readiness v20 report schema or fingerprint mismatch"
        )
    with _v19_contract():
        v19.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    materialized = "corpus_s3_materialization" in ready
    inspected = "corpus_coverage" in ready
    definition_bound = "corpus_definition_byte_binding" in ready
    expected = {
        "s3_materialization_attested": materialized,
        "s3_materialization_required_before_broad_inspection": True,
        "remote_inventory_may_not_be_inferred": True,
        "broad_inspection_bound_to_s3_materialization": inspected,
        "definition_binding_bound_to_s3_materialization": definition_bound,
    }
    for field, item in expected.items():
        if value.get(field) is not item:
            raise HistoricalRefinementReadinessError(
                f"readiness v20 {field} summary mismatch"
            )
    if (inspected or definition_bound) and not materialized:
        raise HistoricalRefinementReadinessError(
            "broad inspection or definition binding may not bypass S3 materialization"
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
                f"readiness v20 must keep {field}=false"
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


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v19._linked_fixture_chain()
    binding = values["corpus_definition_byte_binding"]
    materialization = legacy._fixture_artifact(
        _S3_MATERIALIZATION,
        "S3_MATERIALIZATION_ATTESTED_READY_FOR_BYTE_INSPECTION",
    )
    materialization["plan_fingerprint"] = binding["plan_fingerprint"]
    materialization["inventory_compiler_receipt_fingerprint"] = binding[
        "inventory_compiler_receipt_fingerprint"
    ]
    materialization["blockers"] = []
    materialization["next_action"] = "RUN_BYTE_LEVEL_CORPUS_INSPECTION"
    materialization.pop("receipt_fingerprint", None)
    materialization["receipt_fingerprint"] = _fingerprint(materialization)
    return {"corpus_s3_materialization": materialization, **values}


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["first_blocking_stage"] == "corpus_s3_materialization"
        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V20"
        assert complete["s3_materialization_attested"] is True
        (root / _S3_MATERIALIZATION.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_s3_materialization"
    print("[ng_historical_refinement_readiness_v20] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v20.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
