#!/usr/bin/env python3
"""Canonical readiness v30 requiring source-native corpus identity attestation.

Readiness v29 recursively binds runtime-observed S3 inventory to exact materialized
bytes. V30 additionally requires the materialized source bytes themselves to attest
the exact dataset, schema, publisher, instrument, raw symbol mapping, definition
period, and chronological event-time identity before broad corpus inspection.
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
import ng_historical_refinement_readiness_v29 as v29

SCHEMA = "ng_historical_refinement_readiness.v30"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V29_OVERALL_STATUS = v29._overall_status

_SOURCE_IDENTITY = StageSpec(
    "corpus_source_identity_attestation",
    "ng_corpus_source_identity_attestation.json",
    "ng_corpus_source_identity_attestation.v1",
    "fingerprint",
    frozenset({"CORPUS_SOURCE_NATIVE_IDENTITY_ATTESTED"}),
    "ng_corpus_source_identity_attestation",
    ("validate_attestation",),
    (
        "Attest DBN metadata/symbology and record-header identity, or explicit decoded "
        "JSONL identity, before broad byte inspection."
    ),
    required_fields=(
        "materializer_provenance_fingerprint",
        "plan_fingerprint",
        "source_materializations_fingerprint",
        "source_identity_evidence_fingerprint",
        "source_count",
        "all_source_native_identities_attested",
        "dataset_publisher_instrument_symbol_and_period_bound_to_source_bytes",
        "next_action",
    ),
    pre_outcome=True,
)

STAGES = (*v29.STAGES[:6], _SOURCE_IDENTITY, *v29.STAGES[6:])
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v29.LINK_RULES,
    (
        "corpus_s3_materialization_provenance",
        "fingerprint",
        "corpus_source_identity_attestation",
        "materializer_provenance_fingerprint",
    ),
    (
        "corpus_s3_materialization_provenance",
        "plan_fingerprint",
        "corpus_source_identity_attestation",
        "plan_fingerprint",
    ),
    (
        "corpus_s3_materialization_provenance",
        "source_materializations_fingerprint",
        "corpus_source_identity_attestation",
        "source_materializations_fingerprint",
    ),
    (
        "corpus_source_identity_attestation",
        "plan_fingerprint",
        "corpus_definition_byte_binding",
        "plan_fingerprint",
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V30"
    if "corpus_s3_materialization_provenance" not in ready_keys:
        return _V29_OVERALL_STATUS(ready_keys)
    if "corpus_source_identity_attestation" not in ready_keys:
        return "RUNTIME_MATERIALIZATION_PROVENANCE_BOUND_SOURCE_NATIVE_IDENTITY_INCOMPLETE"
    if "corpus_coverage" not in ready_keys:
        return "SOURCE_NATIVE_IDENTITY_ATTESTED_BROAD_BYTE_INSPECTION_INCOMPLETE"
    delegated = [
        key for key in ready_keys if key != "corpus_source_identity_attestation"
    ]
    return _V29_OVERALL_STATUS(delegated)


@contextmanager
def _legacy_contract() -> Iterator[None]:
    saved = (legacy.SCHEMA, legacy.STAGES, legacy.LINK_RULES)
    legacy.SCHEMA = SCHEMA
    legacy.STAGES = STAGES
    legacy.LINK_RULES = LINK_RULES
    try:
        yield
    finally:
        legacy.SCHEMA, legacy.STAGES, legacy.LINK_RULES = saved


def _summary_fields(ready: Sequence[str]) -> dict[str, Any]:
    ready_set = set(ready)
    identity_ready = "corpus_source_identity_attestation" in ready_set
    inspected = "corpus_coverage" in ready_set
    definition_bound = "corpus_definition_byte_binding" in ready_set
    return {
        **v29._summary_fields(
            [key for key in ready if key != "corpus_source_identity_attestation"]
        ),
        "source_identity_attestation_artifact": _SOURCE_IDENTITY.filename,
        "source_identity_attestation_schema": _SOURCE_IDENTITY.schema,
        "dbn_metadata_dataset_and_schema_attested": identity_ready,
        "record_header_publisher_and_instrument_attested": identity_ready,
        "raw_symbol_mapping_interval_attested": identity_ready,
        "definition_period_event_bounds_attested": identity_ready,
        "source_event_chronology_attested": identity_ready,
        "decoded_jsonl_requires_explicit_identity_on_every_matching_row": True,
        "identity_may_not_be_inferred_from_filename_or_s3_key": True,
        "broad_inspection_blocked_until_source_native_identity": True,
        "broad_inspection_bound_to_source_native_identity": inspected,
        "definition_binding_bound_to_source_native_identity": definition_bound,
    }


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[
        str, Callable[[Mapping[str, Any]], Any]
    ]
    | None = None,
) -> dict[str, Any]:
    with _legacy_contract():
        report = legacy.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    report["status"] = _overall_status(ready)
    report.update(_summary_fields(ready))
    report["note"] = (
        "Readiness v30 requires source-native identity evidence after recursive exact "
        "materialization provenance and before broad corpus inspection. DBN dataset/schema "
        "metadata, symbology mapping intervals, record-header publisher/instrument IDs, "
        "definition-period event bounds, and chronological event order must agree with the "
        "explicit observed definitions. Decoded JSONL must carry the exact identity on "
        "every matching row."
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
            "readiness v30 report schema or fingerprint mismatch"
        )
    with _legacy_contract():
        legacy.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError(
            "readiness v30 overall status mismatch"
        )
    for field, expected in _summary_fields(ready).items():
        if value.get(field) != expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v30 {field} summary mismatch"
            )

    ready_set = set(ready)
    provenance = "corpus_s3_materialization_provenance" in ready_set
    identity = "corpus_source_identity_attestation" in ready_set
    inspected = "corpus_coverage" in ready_set
    definition_bound = "corpus_definition_byte_binding" in ready_set
    if identity and not provenance:
        raise HistoricalRefinementReadinessError(
            "source identity attestation may not bypass recursive materializer provenance"
        )
    if inspected and not identity:
        raise HistoricalRefinementReadinessError(
            "broad byte inspection may not bypass source-native identity attestation"
        )
    if definition_bound and not identity:
        raise HistoricalRefinementReadinessError(
            "definition-byte binding may not bypass source-native identity attestation"
        )
    order = list(value.get("stage_order") or [])
    if order[:8] != [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_s3_materialization_provenance",
        "corpus_source_identity_attestation",
        "corpus_coverage",
    ]:
        raise HistoricalRefinementReadinessError(
            "source-native identity must remain between recursive materializer provenance and broad inspection"
        )
    if _SOURCE_IDENTITY.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "source-native identity attestation must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v29._linked_fixture_chain()
    provenance = values["corpus_s3_materialization_provenance"]
    identity = legacy._fixture_artifact(
        _SOURCE_IDENTITY,
        "CORPUS_SOURCE_NATIVE_IDENTITY_ATTESTED",
    )
    identity.update(
        {
            "materializer_provenance_fingerprint": provenance["fingerprint"],
            "plan_fingerprint": provenance["plan_fingerprint"],
            "source_materializations_fingerprint": provenance[
                "source_materializations_fingerprint"
            ],
            "source_identity_evidence_fingerprint": "i" * 64,
            "source_count": provenance["source_count"],
            "all_source_native_identities_attested": True,
            "dataset_publisher_instrument_symbol_and_period_bound_to_source_bytes": True,
            "blockers": [],
            "next_action": "RUN_BYTE_LEVEL_CORPUS_INSPECTION",
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
    )
    identity.pop("fingerprint", None)
    identity["fingerprint"] = _fingerprint(identity)
    values["corpus_source_identity_attestation"] = identity

    definition = values.get("corpus_definition_byte_binding")
    if isinstance(definition, dict):
        definition["plan_fingerprint"] = identity["plan_fingerprint"]
        definition.pop("fingerprint", None)
        definition["fingerprint"] = _fingerprint(definition)
    return values


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["first_blocking_stage"] == "corpus_expected_day_contract"

        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V30"
        assert complete["dbn_metadata_dataset_and_schema_attested"] is True

        (root / _SOURCE_IDENTITY.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_source_identity_attestation"
        assert blocked["broad_corpus_verified"] is False

    print("[ng_historical_refinement_readiness_v30] selftest PASS")
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
        or args.artifact_dir / "ng_historical_refinement_readiness_v30.json"
    )
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
