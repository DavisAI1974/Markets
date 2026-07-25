#!/usr/bin/env python3
"""Canonical readiness v24 requiring paginated checksum-enabled S3 inventory capture.

V23 explicitly paginated latest-version resolution, but the downstream inventory capture
still issued one aggregate ``list-object-versions`` request and stood down when AWS
returned a truncated response. V24 requires the inventory stage itself to preserve and
validate every service page before checksum-enabled heads, materialization, inspection,
G15 replay, or pre-cutoff G16 work.
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
import ng_historical_refinement_readiness_v23 as v23

SCHEMA = "ng_historical_refinement_readiness.v24"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V23_OVERALL_STATUS = v23._overall_status

_PAGINATED_S3_INVENTORY_CAPTURE = StageSpec(
    "corpus_s3_inventory_capture",
    "ng_corpus_s3_paginated_inventory_capture_attestation.json",
    "ng_corpus_s3_paginated_inventory_capture_attestation.v1",
    "receipt_fingerprint",
    frozenset({"S3_PAGINATED_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION"}),
    "ng_corpus_s3_paginated_inventory_capture",
    ("validate_receipt",),
    "Capture exact checksum-enabled S3 inventory from complete service-page evidence.",
    required_fields=(
        "source_spec_fingerprint",
        "captured_pages_fingerprint",
        "pagination_summaries_fingerprint",
        "captured_head_objects_fingerprint",
        "combined_inventory_evidence_fingerprint",
        "legacy_capture_receipt_fingerprint",
        "materialization_spec_fingerprint",
        "complete_pagination_attested",
        "checksum_enabled_heads_attested",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (v23.STAGES[0], _PAGINATED_S3_INVENTORY_CAPTURE, *v23.STAGES[2:])
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "corpus_s3_latest_version_resolution",
        "capture_spec_fingerprint",
        "corpus_s3_inventory_capture",
        "source_spec_fingerprint",
    ),
    *v23.LINK_RULES[1:],
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V24"
    if (
        "corpus_s3_latest_version_resolution" in ready_keys
        and "corpus_s3_inventory_capture" not in ready_keys
    ):
        return "S3_VERSION_PAGINATION_COMPLETE_INVENTORY_PAGINATION_INCOMPLETE"
    if (
        "corpus_s3_inventory_capture" in ready_keys
        and "corpus_s3_materialization" not in ready_keys
    ):
        return "S3_PAGINATED_INVENTORY_CAPTURED_MATERIALIZATION_INCOMPLETE"
    return _V23_OVERALL_STATUS(ready_keys)


@contextmanager
def _v23_contract() -> Iterator[None]:
    saved = (v23.SCHEMA, v23.STAGES, v23.LINK_RULES, v23._overall_status)
    v23.SCHEMA = SCHEMA
    v23.STAGES = STAGES
    v23.LINK_RULES = LINK_RULES
    v23._overall_status = _overall_status
    try:
        yield
    finally:
        v23.SCHEMA, v23.STAGES, v23.LINK_RULES, v23._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[
        str, Callable[[Mapping[str, Any]], Any]
    ]
    | None = None,
) -> dict[str, Any]:
    with _v23_contract():
        report = v23.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    resolved = "corpus_s3_latest_version_resolution" in ready
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    report["paginated_inventory_capture_artifact"] = (
        _PAGINATED_S3_INVENTORY_CAPTURE.filename
    )
    report["paginated_inventory_capture_schema"] = (
        _PAGINATED_S3_INVENTORY_CAPTURE.schema
    )
    report["inventory_service_pagination_attested"] = captured
    report["inventory_page_requests_and_responses_fingerprint_bound"] = captured
    report["checksum_enabled_head_inventory_bound"] = captured
    report["inventory_capture_bound_to_paginated_resolution"] = captured
    report["materialization_bound_to_paginated_inventory_capture"] = materialized
    report["legacy_single_page_inventory_capture_rejected"] = True
    report["inventory_pagination_required_after_resolution"] = resolved
    report["note"] = (
        "Readiness v24 requires complete explicit service pagination both while resolving "
        "latest S3 versions and while checksum-capturing the one-year L1/dense-trades and "
        "spring/summer MBO inventories. A single truncated inventory response may not "
        "authorize materialization, G15 replay, or pre-cutoff G16 work."
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
            "readiness v24 report schema or fingerprint mismatch"
        )
    with _v23_contract():
        v23.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    resolved = "corpus_s3_latest_version_resolution" in ready
    captured = "corpus_s3_inventory_capture" in ready
    materialized = "corpus_s3_materialization" in ready
    expected = {
        "paginated_inventory_capture_artifact": (
            _PAGINATED_S3_INVENTORY_CAPTURE.filename
        ),
        "paginated_inventory_capture_schema": (
            _PAGINATED_S3_INVENTORY_CAPTURE.schema
        ),
        "inventory_service_pagination_attested": captured,
        "inventory_page_requests_and_responses_fingerprint_bound": captured,
        "checksum_enabled_head_inventory_bound": captured,
        "inventory_capture_bound_to_paginated_resolution": captured,
        "materialization_bound_to_paginated_inventory_capture": materialized,
        "legacy_single_page_inventory_capture_rejected": True,
        "inventory_pagination_required_after_resolution": resolved,
    }
    for field, item in expected.items():
        if value.get(field) != item:
            raise HistoricalRefinementReadinessError(
                f"readiness v24 {field} summary mismatch"
            )
    if (captured or materialized) and not resolved:
        raise HistoricalRefinementReadinessError(
            "paginated inventory capture may not bypass latest-version pagination"
        )
    if materialized and not captured:
        raise HistoricalRefinementReadinessError(
            "materialization may not bypass paginated checksum inventory capture"
        )
    if value.get("stage_order", [None, None])[:2] != [
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
    ]:
        raise HistoricalRefinementReadinessError(
            "paginated version resolution and inventory capture must remain first"
        )
    if _PAGINATED_S3_INVENTORY_CAPTURE.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "paginated S3 inventory capture must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v23._linked_fixture_chain()
    values.pop("corpus_s3_inventory_capture", None)
    materialization = values["corpus_s3_materialization"]
    capture = legacy._fixture_artifact(
        _PAGINATED_S3_INVENTORY_CAPTURE,
        "S3_PAGINATED_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION",
    )
    capture["materialization_spec_fingerprint"] = materialization[
        "source_spec_fingerprint"
    ]
    capture["complete_pagination_attested"] = True
    capture["checksum_enabled_heads_attested"] = True
    capture["identity_from_s3_keys_inferred"] = False
    capture["blockers"] = []
    capture["next_action"] = "RUN_S3_MATERIALIZATION_ATTESTATION"
    capture.pop("receipt_fingerprint", None)
    capture["receipt_fingerprint"] = _fingerprint(capture)

    resolution = values["corpus_s3_latest_version_resolution"]
    resolution["capture_spec_fingerprint"] = capture["source_spec_fingerprint"]
    resolution.pop("receipt_fingerprint", None)
    resolution["receipt_fingerprint"] = _fingerprint(resolution)
    return {
        "corpus_s3_latest_version_resolution": resolution,
        "corpus_s3_inventory_capture": capture,
        **{
            key: item
            for key, item in values.items()
            if key != "corpus_s3_latest_version_resolution"
        },
    }


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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V24"
        assert complete["inventory_service_pagination_attested"] is True
        (root / _PAGINATED_S3_INVENTORY_CAPTURE.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_s3_inventory_capture"
    print("[ng_historical_refinement_readiness_v24] selftest PASS")
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
        or args.artifact_dir / "ng_historical_refinement_readiness_v24.json"
    )
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
