#!/usr/bin/env python3
"""Canonical readiness v23 requiring complete S3 service pagination.

V22 resolved exact latest object versions before checksum-enabled inventory capture, but
its resolver accepted one aggregate ``list-object-versions`` response per corpus. V23
replaces that first-stage contract with an explicit service-page attestation: every page
request, continuation marker, and response is fingerprinted; marker cycles, duplicate
rows, out-of-prefix objects, and evidence ending on a truncated page fail closed.
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
import ng_historical_refinement_readiness_v22 as v22

SCHEMA = "ng_historical_refinement_readiness.v23"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V22_OVERALL_STATUS = v22._overall_status

_PAGINATED_S3_LATEST_VERSION_RESOLUTION = StageSpec(
    "corpus_s3_latest_version_resolution",
    "ng_corpus_s3_paginated_latest_version_resolution_attestation.json",
    "ng_corpus_s3_paginated_latest_version_resolution_attestation.v1",
    "receipt_fingerprint",
    frozenset({"S3_PAGINATED_LATEST_VERSIONS_RESOLVED_READY_FOR_CAPTURE"}),
    "ng_corpus_s3_paginated_latest_version_resolution",
    ("validate_receipt",),
    "Resolve exact latest S3 versions from complete, explicitly paginated service-page evidence before inventory capture.",
    required_fields=(
        "source_spec_fingerprint",
        "captured_pages_fingerprint",
        "pagination_summaries_fingerprint",
        "combined_list_evidence_fingerprint",
        "legacy_resolution_receipt_fingerprint",
        "capture_spec_fingerprint",
        "complete_pagination_attested",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (_PAGINATED_S3_LATEST_VERSION_RESOLUTION, *v22.STAGES[1:])
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "corpus_s3_latest_version_resolution",
        "capture_spec_fingerprint",
        "corpus_s3_inventory_capture",
        "source_spec_fingerprint",
    ),
    *v22.LINK_RULES[1:],
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V23"
    if (
        "corpus_s3_latest_version_resolution" in ready_keys
        and "corpus_s3_inventory_capture" not in ready_keys
    ):
        return "S3_COMPLETE_PAGINATION_ATTESTED_CAPTURE_INCOMPLETE"
    if "corpus_s3_latest_version_resolution" not in ready_keys:
        return "S3_COMPLETE_PAGINATION_ATTESTATION_INCOMPLETE"
    return _V22_OVERALL_STATUS(ready_keys)


@contextmanager
def _v22_contract() -> Iterator[None]:
    saved = (v22.SCHEMA, v22.STAGES, v22.LINK_RULES, v22._overall_status)
    v22.SCHEMA = SCHEMA
    v22.STAGES = STAGES
    v22.LINK_RULES = LINK_RULES
    v22._overall_status = _overall_status
    try:
        yield
    finally:
        v22.SCHEMA, v22.STAGES, v22.LINK_RULES, v22._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[
        str, Callable[[Mapping[str, Any]], Any]
    ]
    | None = None,
) -> dict[str, Any]:
    with _v22_contract():
        report = v22.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    paginated = "corpus_s3_latest_version_resolution" in ready
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    report["paginated_resolution_artifact"] = (
        _PAGINATED_S3_LATEST_VERSION_RESOLUTION.filename
    )
    report["paginated_resolution_schema"] = (
        _PAGINATED_S3_LATEST_VERSION_RESOLUTION.schema
    )
    report["s3_complete_pagination_attested"] = paginated
    report["service_page_requests_and_responses_fingerprint_bound"] = paginated
    report["pagination_marker_progression_verified"] = paginated
    report["pagination_cycles_rejected"] = True
    report["truncated_final_page_rejected"] = True
    report["inventory_capture_bound_to_paginated_resolution"] = captured
    report["materialization_bound_to_paginated_resolution"] = materialized
    report["note"] = (
        "Readiness v23 requires complete explicit S3 service pagination for both the "
        "one-year L1/dense-trades corpus and spring/summer MBO corpus before exact "
        "version resolution, checksum-enabled inventory capture, materialization, "
        "G15 replay, or pre-cutoff G16 work."
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
            "readiness v23 report schema or fingerprint mismatch"
        )
    with _v22_contract():
        v22.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    paginated = "corpus_s3_latest_version_resolution" in ready
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    expected = {
        "paginated_resolution_artifact": (
            _PAGINATED_S3_LATEST_VERSION_RESOLUTION.filename
        ),
        "paginated_resolution_schema": (
            _PAGINATED_S3_LATEST_VERSION_RESOLUTION.schema
        ),
        "s3_complete_pagination_attested": paginated,
        "service_page_requests_and_responses_fingerprint_bound": paginated,
        "pagination_marker_progression_verified": paginated,
        "pagination_cycles_rejected": True,
        "truncated_final_page_rejected": True,
        "inventory_capture_bound_to_paginated_resolution": captured,
        "materialization_bound_to_paginated_resolution": materialized,
    }
    for field, item in expected.items():
        if value.get(field) != item:
            raise HistoricalRefinementReadinessError(
                f"readiness v23 {field} summary mismatch"
            )
    if (captured or materialized) and not paginated:
        raise HistoricalRefinementReadinessError(
            "inventory capture or materialization may not bypass complete S3 pagination"
        )
    if value.get("stage_order", [None])[0] != "corpus_s3_latest_version_resolution":
        raise HistoricalRefinementReadinessError(
            "paginated S3 version resolution must remain the first readiness stage"
        )
    if _PAGINATED_S3_LATEST_VERSION_RESOLUTION.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "paginated S3 version resolution must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v22._linked_fixture_chain()
    values.pop("corpus_s3_latest_version_resolution", None)
    capture = values["corpus_s3_inventory_capture"]
    resolution = legacy._fixture_artifact(
        _PAGINATED_S3_LATEST_VERSION_RESOLUTION,
        "S3_PAGINATED_LATEST_VERSIONS_RESOLVED_READY_FOR_CAPTURE",
    )
    resolution["capture_spec_fingerprint"] = capture["source_spec_fingerprint"]
    resolution["complete_pagination_attested"] = True
    resolution["identity_from_s3_keys_inferred"] = False
    resolution["blockers"] = []
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V23"
        assert complete["s3_complete_pagination_attested"] is True
        (root / _PAGINATED_S3_LATEST_VERSION_RESOLUTION.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_s3_latest_version_resolution"
    print("[ng_historical_refinement_readiness_v23] selftest PASS")
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
        or args.artifact_dir / "ng_historical_refinement_readiness_v23.json"
    )
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
