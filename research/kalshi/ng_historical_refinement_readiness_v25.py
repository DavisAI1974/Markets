#!/usr/bin/env python3
"""Canonical readiness v25 requiring a complete expected-session-day contract.

V24 proves complete S3 pagination, but its source specification can still carry an
operator-supplied ``expected_days`` list that is shorter than the canonical corpus
window. V25 inserts an independent calendar partition before any S3 call. Every date
in the one-year L1/dense-trades and spring/summer MBO windows must be classified as an
expected session or an evidenced no-session exclusion, and every G15/G16 replay date
must remain expected.
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
import ng_historical_refinement_readiness_v24 as v24

SCHEMA = "ng_historical_refinement_readiness.v25"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V24_OVERALL_STATUS = v24._overall_status

_EXPECTED_DAY_CONTRACT = StageSpec(
    "corpus_expected_day_contract",
    "ng_corpus_expected_day_contract_attestation.json",
    "ng_corpus_expected_day_contract_attestation.v1",
    "receipt_fingerprint",
    frozenset({"CORPUS_EXPECTED_DAY_CONTRACT_READY_FOR_S3_RESOLUTION"}),
    "ng_corpus_expected_day_contract",
    ("validate_receipt",),
    "Attest a complete canonical expected-session-day partition before S3 resolution.",
    required_fields=(
        "source_spec_fingerprint",
        "corpus_calendar_partitions_fingerprint",
        "canonical_windows_fingerprint",
        "g15_target_days_fingerprint",
        "g16_target_days_fingerprint",
        "complete_calendar_partition_attested",
        "expected_days_operator_truncation_rejected",
        "non_saturday_exclusions_require_evidence",
        "target_replay_days_may_not_be_excluded",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (_EXPECTED_DAY_CONTRACT, *v24.STAGES)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "corpus_expected_day_contract",
        "source_spec_fingerprint",
        "corpus_s3_latest_version_resolution",
        "source_spec_fingerprint",
    ),
    *v24.LINK_RULES,
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V25"
    if "corpus_expected_day_contract" not in ready_keys:
        return "CORPUS_EXPECTED_DAY_CONTRACT_INCOMPLETE"
    if (
        "corpus_expected_day_contract" in ready_keys
        and "corpus_s3_latest_version_resolution" not in ready_keys
    ):
        return "EXPECTED_DAY_CONTRACT_COMPLETE_S3_VERSION_RESOLUTION_INCOMPLETE"
    return _V24_OVERALL_STATUS(ready_keys)


@contextmanager
def _v24_contract() -> Iterator[None]:
    saved = (v24.SCHEMA, v24.STAGES, v24.LINK_RULES, v24._overall_status)
    v24.SCHEMA = SCHEMA
    v24.STAGES = STAGES
    v24.LINK_RULES = LINK_RULES
    v24._overall_status = _overall_status
    try:
        yield
    finally:
        v24.SCHEMA, v24.STAGES, v24.LINK_RULES, v24._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v24_contract():
        report = v24.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    contracted = "corpus_expected_day_contract" in ready
    resolved = "corpus_s3_latest_version_resolution" in ready
    report["expected_day_contract_artifact"] = _EXPECTED_DAY_CONTRACT.filename
    report["expected_day_contract_schema"] = _EXPECTED_DAY_CONTRACT.schema
    report["complete_canonical_calendar_partition_attested"] = contracted
    report["operator_shortened_expected_day_lists_rejected"] = True
    report["non_saturday_exclusions_evidence_bound"] = contracted
    report["g15_g16_target_days_must_remain_expected"] = True
    report["s3_resolution_bound_to_expected_day_contract"] = resolved
    report["calendar_contract_required_before_any_s3_inventory_request"] = True
    report["note"] = (
        "Readiness v25 requires a complete canonical day-by-day partition for the "
        "one-year L1/dense-trades and spring/summer MBO windows before paginated S3 "
        "version resolution. Saturdays may be schedule exclusions; any other exclusion "
        "requires evidence, and no G15/G16 target replay day may be excluded."
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
            "readiness v25 report schema or fingerprint mismatch"
        )
    with _v24_contract():
        v24.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    contracted = "corpus_expected_day_contract" in ready
    resolved = "corpus_s3_latest_version_resolution" in ready
    expected = {
        "expected_day_contract_artifact": _EXPECTED_DAY_CONTRACT.filename,
        "expected_day_contract_schema": _EXPECTED_DAY_CONTRACT.schema,
        "complete_canonical_calendar_partition_attested": contracted,
        "operator_shortened_expected_day_lists_rejected": True,
        "non_saturday_exclusions_evidence_bound": contracted,
        "g15_g16_target_days_must_remain_expected": True,
        "s3_resolution_bound_to_expected_day_contract": resolved,
        "calendar_contract_required_before_any_s3_inventory_request": True,
    }
    for field, item in expected.items():
        if value.get(field) != item:
            raise HistoricalRefinementReadinessError(
                f"readiness v25 {field} summary mismatch"
            )
    if resolved and not contracted:
        raise HistoricalRefinementReadinessError(
            "S3 latest-version resolution may not bypass the expected-day contract"
        )
    order = list(value.get("stage_order") or [])
    if order[:3] != [
        "corpus_expected_day_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
    ]:
        raise HistoricalRefinementReadinessError(
            "expected-day contract and paginated S3 stages must remain first"
        )
    if _EXPECTED_DAY_CONTRACT.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "expected-day contract must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v24._linked_fixture_chain()
    resolution = values["corpus_s3_latest_version_resolution"]
    contract = legacy._fixture_artifact(
        _EXPECTED_DAY_CONTRACT,
        "CORPUS_EXPECTED_DAY_CONTRACT_READY_FOR_S3_RESOLUTION",
    )
    contract["source_spec_fingerprint"] = resolution["source_spec_fingerprint"]
    contract["complete_calendar_partition_attested"] = True
    contract["expected_days_operator_truncation_rejected"] = True
    contract["non_saturday_exclusions_require_evidence"] = True
    contract["target_replay_days_may_not_be_excluded"] = True
    contract["identity_from_s3_keys_inferred"] = False
    contract["blockers"] = []
    contract["next_action"] = "RUN_PAGINATED_S3_LATEST_VERSION_RESOLUTION"
    contract.pop("receipt_fingerprint", None)
    contract["receipt_fingerprint"] = _fingerprint(contract)
    return {"corpus_expected_day_contract": contract, **values}


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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V25"
        assert complete["complete_canonical_calendar_partition_attested"] is True
        (root / _EXPECTED_DAY_CONTRACT.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_expected_day_contract"
    print("[ng_historical_refinement_readiness_v25] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v25.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
