#!/usr/bin/env python3
"""Canonical readiness v26 requiring product-specific corpus finalization lags.

V25 proves every canonical date is classified, but an inventory snapshot taken before a
corpus window ended—or before the publisher/product finalization lag elapsed—could still
be labeled complete. V26 inserts a deterministic finalization contract between the
expected-day contract and paginated S3 resolution.
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
import ng_historical_refinement_readiness_v25 as v25

SCHEMA = "ng_historical_refinement_readiness.v26"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V25_OVERALL_STATUS = v25._overall_status

_INVENTORY_FINALIZATION_CONTRACT = StageSpec(
    "corpus_inventory_finalization_contract",
    "ng_corpus_inventory_finalization_contract.json",
    "ng_corpus_inventory_finalization_contract.v1",
    "receipt_fingerprint",
    frozenset({"CORPUS_INVENTORY_FINALIZATION_READY_FOR_S3_RESOLUTION"}),
    "ng_corpus_inventory_finalization_contract",
    ("validate_receipt",),
    "Attest inventory snapshots after each canonical corpus end and product-specific finalization lag.",
    required_fields=(
        "source_spec_fingerprint",
        "global_inventory_observed_at_utc",
        "corpus_finalization_summaries_fingerprint",
        "canonical_windows_fingerprint",
        "product_specific_lags_required",
        "lag_policies_evidence_fingerprinted",
        "inventory_must_follow_corpus_end_and_product_lag",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (
    v25.STAGES[0],
    _INVENTORY_FINALIZATION_CONTRACT,
    *v25.STAGES[1:],
)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "corpus_expected_day_contract",
        "source_spec_fingerprint",
        "corpus_inventory_finalization_contract",
        "source_spec_fingerprint",
    ),
    (
        "corpus_inventory_finalization_contract",
        "source_spec_fingerprint",
        "corpus_s3_latest_version_resolution",
        "source_spec_fingerprint",
    ),
    *v25.LINK_RULES[1:],
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V26"
    if "corpus_expected_day_contract" not in ready_keys:
        return "CORPUS_EXPECTED_DAY_CONTRACT_INCOMPLETE"
    if "corpus_inventory_finalization_contract" not in ready_keys:
        return "CORPUS_INVENTORY_FINALIZATION_CONTRACT_INCOMPLETE"
    if "corpus_s3_latest_version_resolution" not in ready_keys:
        return "INVENTORY_FINALIZATION_COMPLETE_S3_VERSION_RESOLUTION_INCOMPLETE"
    return _V25_OVERALL_STATUS(ready_keys)


@contextmanager
def _v25_contract() -> Iterator[None]:
    saved = (v25.SCHEMA, v25.STAGES, v25.LINK_RULES, v25._overall_status)
    v25.SCHEMA = SCHEMA
    v25.STAGES = STAGES
    v25.LINK_RULES = LINK_RULES
    v25._overall_status = _overall_status
    try:
        yield
    finally:
        v25.SCHEMA, v25.STAGES, v25.LINK_RULES, v25._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v25_contract():
        report = v25.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    finalized = "corpus_inventory_finalization_contract" in ready
    resolved = "corpus_s3_latest_version_resolution" in ready
    report["inventory_finalization_contract_artifact"] = _INVENTORY_FINALIZATION_CONTRACT.filename
    report["inventory_finalization_contract_schema"] = _INVENTORY_FINALIZATION_CONTRACT.schema
    report["product_specific_finalization_lags_attested"] = finalized
    report["inventory_observation_after_corpus_end_attested"] = finalized
    report["lag_policy_evidence_fingerprints_bound"] = finalized
    report["s3_resolution_bound_to_finalized_inventory_snapshot"] = resolved
    report["expected_day_contract_bound_to_finalization_contract"] = finalized
    report["finalization_contract_required_before_any_s3_request"] = True
    report["note"] = (
        "Readiness v26 requires every corpus inventory observation to occur after the "
        "canonical period end and its explicit evidence-fingerprinted product lag. The "
        "same source specification must pass the expected-day contract, finalization "
        "contract, and paginated S3 resolution before materialization or replay."
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
        raise HistoricalRefinementReadinessError("readiness v26 report schema or fingerprint mismatch")
    with _v25_contract():
        v25.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    expected_days = "corpus_expected_day_contract" in ready
    finalized = "corpus_inventory_finalization_contract" in ready
    resolved = "corpus_s3_latest_version_resolution" in ready
    expected = {
        "inventory_finalization_contract_artifact": _INVENTORY_FINALIZATION_CONTRACT.filename,
        "inventory_finalization_contract_schema": _INVENTORY_FINALIZATION_CONTRACT.schema,
        "product_specific_finalization_lags_attested": finalized,
        "inventory_observation_after_corpus_end_attested": finalized,
        "lag_policy_evidence_fingerprints_bound": finalized,
        "s3_resolution_bound_to_finalized_inventory_snapshot": resolved,
        "expected_day_contract_bound_to_finalization_contract": finalized,
        "finalization_contract_required_before_any_s3_request": True,
    }
    for field, item in expected.items():
        if value.get(field) != item:
            raise HistoricalRefinementReadinessError(f"readiness v26 {field} summary mismatch")
    if finalized and not expected_days:
        raise HistoricalRefinementReadinessError(
            "inventory finalization may not bypass the expected-day contract"
        )
    if resolved and not finalized:
        raise HistoricalRefinementReadinessError(
            "S3 latest-version resolution may not bypass inventory finalization"
        )
    order = list(value.get("stage_order") or [])
    if order[:4] != [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
    ]:
        raise HistoricalRefinementReadinessError(
            "expected-day, inventory-finalization, and paginated S3 stages must remain first"
        )
    if _INVENTORY_FINALIZATION_CONTRACT.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "inventory finalization contract must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v25._linked_fixture_chain()
    resolution = values["corpus_s3_latest_version_resolution"]
    finalization = legacy._fixture_artifact(
        _INVENTORY_FINALIZATION_CONTRACT,
        "CORPUS_INVENTORY_FINALIZATION_READY_FOR_S3_RESOLUTION",
    )
    finalization["source_spec_fingerprint"] = resolution["source_spec_fingerprint"]
    finalization["product_specific_lags_required"] = True
    finalization["lag_policies_evidence_fingerprinted"] = True
    finalization["inventory_must_follow_corpus_end_and_product_lag"] = True
    finalization["blockers"] = []
    finalization["next_action"] = "RUN_PAGINATED_S3_LATEST_VERSION_RESOLUTION"
    finalization.pop("receipt_fingerprint", None)
    finalization["receipt_fingerprint"] = _fingerprint(finalization)
    return {
        "corpus_expected_day_contract": values["corpus_expected_day_contract"],
        "corpus_inventory_finalization_contract": finalization,
        **{key: item for key, item in values.items() if key != "corpus_expected_day_contract"},
    }


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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V26"
        assert complete["product_specific_finalization_lags_attested"] is True
        (root / _INVENTORY_FINALIZATION_CONTRACT.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_inventory_finalization_contract"
    print("[ng_historical_refinement_readiness_v26] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v26.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
