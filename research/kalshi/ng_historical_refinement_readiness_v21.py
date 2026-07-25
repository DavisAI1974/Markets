#!/usr/bin/env python3
"""Canonical readiness v21 requiring live S3 inventory capture before materialization.

V20 requires an exact versioned/checksummed S3 materialization attestation. V21
closes the remaining manual front-door gap: the materialization specification must
first be produced from a complete list-object-versions snapshot and checksum-enabled
head-object responses for every explicitly identified corpus source.
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
import ng_historical_refinement_readiness_v20 as v20

SCHEMA = "ng_historical_refinement_readiness.v21"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V20_OVERALL_STATUS = v20._overall_status

_S3_INVENTORY_CAPTURE = StageSpec(
    "corpus_s3_inventory_capture",
    "ng_corpus_s3_inventory_capture_attestation.json",
    "ng_corpus_s3_inventory_capture_attestation.v1",
    "receipt_fingerprint",
    frozenset({"S3_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION"}),
    "ng_corpus_s3_inventory_capture",
    ("validate_receipt",),
    "Capture the exact latest versioned/checksummed S3 object set before local materialization attestation.",
    required_fields=(
        "source_spec_fingerprint",
        "captured_inventory_fingerprint",
        "normalized_inventory_fingerprint",
        "materialization_spec_fingerprint",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (_S3_INVENTORY_CAPTURE, *v20.STAGES)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "corpus_s3_inventory_capture",
        "materialization_spec_fingerprint",
        "corpus_s3_materialization",
        "source_spec_fingerprint",
    ),
    *v20.LINK_RULES,
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V21"
    if (
        "corpus_s3_inventory_capture" in ready_keys
        and "corpus_s3_materialization" not in ready_keys
    ):
        return "S3_INVENTORY_CAPTURED_MATERIALIZATION_INCOMPLETE"
    if "corpus_s3_inventory_capture" not in ready_keys:
        return "S3_INVENTORY_CAPTURE_INCOMPLETE"
    return _V20_OVERALL_STATUS(
        [key for key in ready_keys if key != "corpus_s3_inventory_capture"]
    )


@contextmanager
def _v20_contract() -> Iterator[None]:
    saved = (v20.SCHEMA, v20.STAGES, v20.LINK_RULES, v20._overall_status)
    v20.SCHEMA = SCHEMA
    v20.STAGES = STAGES
    v20.LINK_RULES = LINK_RULES
    v20._overall_status = _overall_status
    try:
        yield
    finally:
        v20.SCHEMA, v20.STAGES, v20.LINK_RULES, v20._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[
        str, Callable[[Mapping[str, Any]], Any]
    ]
    | None = None,
) -> dict[str, Any]:
    with _v20_contract():
        report = v20.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    inspected = "corpus_coverage" in ready
    report["s3_inventory_captured"] = captured
    report["s3_inventory_capture_required_before_materialization"] = True
    report["complete_latest_object_set_required"] = True
    report["checksum_enabled_head_required"] = True
    report["identity_may_not_be_inferred_from_s3_keys"] = True
    report["materialization_bound_to_inventory_capture"] = materialized
    report["broad_inspection_bound_to_captured_inventory"] = inspected
    report["note"] = (
        "Readiness v21 requires a complete list-object-versions capture and "
        "checksum-enabled head-object evidence for explicitly identified L1 and MBO "
        "sources before materialization, inspection, G15 replay, or pre-cutoff G16 work."
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
            "readiness v21 report schema or fingerprint mismatch"
        )
    with _v20_contract():
        v20.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    inspected = "corpus_coverage" in ready
    expected = {
        "s3_inventory_captured": captured,
        "s3_inventory_capture_required_before_materialization": True,
        "complete_latest_object_set_required": True,
        "checksum_enabled_head_required": True,
        "identity_may_not_be_inferred_from_s3_keys": True,
        "materialization_bound_to_inventory_capture": materialized,
        "broad_inspection_bound_to_captured_inventory": inspected,
    }
    for field, item in expected.items():
        if value.get(field) is not item:
            raise HistoricalRefinementReadinessError(
                f"readiness v21 {field} summary mismatch"
            )
    if (materialized or inspected) and not captured:
        raise HistoricalRefinementReadinessError(
            "materialization or inspection may not bypass exact S3 inventory capture"
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
                f"readiness v21 must keep {field}=false"
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


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v20._linked_fixture_chain()
    materialization = values["corpus_s3_materialization"]
    capture = legacy._fixture_artifact(
        _S3_INVENTORY_CAPTURE,
        "S3_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION",
    )
    capture["materialization_spec_fingerprint"] = materialization[
        "source_spec_fingerprint"
    ]
    capture["blockers"] = []
    capture["next_action"] = "RUN_S3_MATERIALIZATION_ATTESTATION"
    capture.pop("receipt_fingerprint", None)
    capture["receipt_fingerprint"] = _fingerprint(capture)
    return {"corpus_s3_inventory_capture": capture, **values}


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["first_blocking_stage"] == "corpus_s3_inventory_capture"
        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert (
            complete["status"]
            == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V21"
        )
        assert complete["s3_inventory_captured"] is True
        (root / _S3_INVENTORY_CAPTURE.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_s3_inventory_capture"
    print("[ng_historical_refinement_readiness_v21] selftest PASS")
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
    output = (
        args.out
        or args.artifact_dir / "ng_historical_refinement_readiness_v21.json"
    )
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
