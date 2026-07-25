#!/usr/bin/env python3
"""Canonical readiness v22 requiring exact latest-version resolution before S3 capture.

V21 requires a complete versioned/checksummed S3 inventory capture. V22 closes the
remaining circular operator seam: exact latest version IDs are resolved from complete
``list-object-versions`` evidence for explicitly identified object keys before the
capture stage performs checksum-enabled ``head-object`` calls.
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
import ng_historical_refinement_readiness_v21 as v21

SCHEMA = "ng_historical_refinement_readiness.v22"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V21_OVERALL_STATUS = v21._overall_status

_S3_LATEST_VERSION_RESOLUTION = StageSpec(
    "corpus_s3_latest_version_resolution",
    "ng_corpus_s3_latest_version_resolution_attestation.json",
    "ng_corpus_s3_latest_version_resolution_attestation.v1",
    "receipt_fingerprint",
    frozenset({"S3_LATEST_VERSIONS_RESOLVED_READY_FOR_CAPTURE"}),
    "ng_corpus_s3_latest_version_resolution",
    ("validate_receipt",),
    "Resolve exact latest S3 version IDs for explicitly identified corpus object keys before inventory capture.",
    required_fields=(
        "source_spec_fingerprint",
        "captured_list_evidence_fingerprint",
        "normalized_list_evidence_fingerprint",
        "resolutions_fingerprint",
        "capture_spec_fingerprint",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (_S3_LATEST_VERSION_RESOLUTION, *v21.STAGES)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "corpus_s3_latest_version_resolution",
        "capture_spec_fingerprint",
        "corpus_s3_inventory_capture",
        "source_spec_fingerprint",
    ),
    *v21.LINK_RULES,
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V22"
    if (
        "corpus_s3_latest_version_resolution" in ready_keys
        and "corpus_s3_inventory_capture" not in ready_keys
    ):
        return "S3_LATEST_VERSIONS_RESOLVED_CAPTURE_INCOMPLETE"
    if "corpus_s3_latest_version_resolution" not in ready_keys:
        return "S3_LATEST_VERSION_RESOLUTION_INCOMPLETE"
    return _V21_OVERALL_STATUS(
        [
            key
            for key in ready_keys
            if key != "corpus_s3_latest_version_resolution"
        ]
    )


@contextmanager
def _v21_contract() -> Iterator[None]:
    saved = (v21.SCHEMA, v21.STAGES, v21.LINK_RULES, v21._overall_status)
    v21.SCHEMA = SCHEMA
    v21.STAGES = STAGES
    v21.LINK_RULES = LINK_RULES
    v21._overall_status = _overall_status
    try:
        yield
    finally:
        v21.SCHEMA, v21.STAGES, v21.LINK_RULES, v21._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[
        str, Callable[[Mapping[str, Any]], Any]
    ]
    | None = None,
) -> dict[str, Any]:
    with _v21_contract():
        report = v21.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    resolved = "corpus_s3_latest_version_resolution" in ready
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    report["s3_latest_versions_resolved"] = resolved
    report["latest_version_resolution_required_before_capture"] = True
    report["version_ids_may_not_be_operator_guessed"] = True
    report["identity_may_not_be_inferred_from_s3_keys"] = True
    report["inventory_capture_bound_to_resolved_versions"] = captured
    report["materialization_bound_to_resolved_versions"] = materialized
    report["note"] = (
        "Readiness v22 requires complete list-object-versions evidence to resolve "
        "the exact latest version ID for every explicitly identified L1 and MBO "
        "object before checksum-enabled inventory capture, materialization, G15 "
        "replay, or pre-cutoff G16 work."
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
            "readiness v22 report schema or fingerprint mismatch"
        )
    with _v21_contract():
        v21.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    resolved = "corpus_s3_latest_version_resolution" in ready
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    expected = {
        "s3_latest_versions_resolved": resolved,
        "latest_version_resolution_required_before_capture": True,
        "version_ids_may_not_be_operator_guessed": True,
        "identity_may_not_be_inferred_from_s3_keys": True,
        "inventory_capture_bound_to_resolved_versions": captured,
        "materialization_bound_to_resolved_versions": materialized,
    }
    for field, item in expected.items():
        if value.get(field) is not item:
            raise HistoricalRefinementReadinessError(
                f"readiness v22 {field} summary mismatch"
            )
    if (captured or materialized) and not resolved:
        raise HistoricalRefinementReadinessError(
            "inventory capture or materialization may not bypass exact latest-version resolution"
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
                f"readiness v22 must keep {field}=false"
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
    values = v21._linked_fixture_chain()
    capture = values["corpus_s3_inventory_capture"]
    resolution = legacy._fixture_artifact(
        _S3_LATEST_VERSION_RESOLUTION,
        "S3_LATEST_VERSIONS_RESOLVED_READY_FOR_CAPTURE",
    )
    resolution["capture_spec_fingerprint"] = capture["source_spec_fingerprint"]
    resolution["blockers"] = []
    resolution["identity_from_s3_keys_inferred"] = False
    resolution["next_action"] = "RUN_EXACT_S3_INVENTORY_CAPTURE"
    resolution.pop("receipt_fingerprint", None)
    resolution["receipt_fingerprint"] = _fingerprint(resolution)
    return {"corpus_s3_latest_version_resolution": resolution, **values}


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["first_blocking_stage"] == "corpus_s3_latest_version_resolution"
        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V22"
        assert complete["s3_latest_versions_resolved"] is True
        (root / _S3_LATEST_VERSION_RESOLUTION.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_s3_latest_version_resolution"
    print("[ng_historical_refinement_readiness_v22] selftest PASS")
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
        or args.artifact_dir / "ng_historical_refinement_readiness_v22.json"
    )
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
