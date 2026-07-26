#!/usr/bin/env python3
"""Canonical readiness v31 requiring prepared normalized replay identity/time attestation.

V30 proves source-native identity in the materialized raw corpus. V31 additionally
verifies the normalized G15 files that actually enter causal replay, including exact
publisher identity, lane type, definition/event periods, chronological source order,
and prepared definitions before trade/MBO use.
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
import ng_historical_refinement_readiness_v30 as v30

SCHEMA = "ng_historical_refinement_readiness.v31"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V30_OVERALL_STATUS = v30._overall_status

_PREPARED_IDENTITY = StageSpec(
    "g15_prepared_normalized_identity",
    "g15_prepared_normalized_identity_guard.json",
    "ng_g15_prepared_normalized_identity_guard.v1",
    "fingerprint",
    frozenset({"G15_PREPARED_NORMALIZED_IDENTITY_AND_TIME_ATTESTED"}),
    "ng_g15_prepared_normalized_identity_guard",
    ("validate_guard",),
    (
        "Verify every prepared G15 normalized row preserves exact dataset/publisher/"
        "instrument/raw-symbol/definition-period identity and chronological event time."
    ),
    required_fields=(
        "bridge_fingerprint",
        "manifest_fingerprint",
        "prepared_corpus_fingerprint",
        "source_evidence_fingerprint",
        "source_count",
        "all_publishers_explicit_and_positive",
        "all_rows_match_exact_manifest_identity",
        "all_events_within_definition_and_lane_periods",
        "all_sources_chronological",
        "definitions_precede_trade_and_mbo_replay",
        "next_action",
    ),
    pre_outcome=True,
)

_STAGE_KEYS = [spec.key for spec in v30.STAGES]
_G15_REPLAY_INDEX = _STAGE_KEYS.index("g15_exact_replay")
STAGES = (
    *v30.STAGES[:_G15_REPLAY_INDEX],
    _PREPARED_IDENTITY,
    *v30.STAGES[_G15_REPLAY_INDEX:],
)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v30.LINK_RULES,
    (
        "replay_catalog_export",
        "g15_bridge_fingerprint",
        "g15_prepared_normalized_identity",
        "bridge_fingerprint",
    ),
    (
        "g15_prepared_normalized_identity",
        "prepared_corpus_fingerprint",
        "g15_exact_replay",
        "prepared_corpus_fingerprint",
    ),
    (
        "g15_prepared_normalized_identity",
        "manifest_fingerprint",
        "g15_exact_replay",
        "manifest_fingerprint",
    ),
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _without_prepared_identity(keys: Sequence[str]) -> list[str]:
    return [key for key in keys if key != "g15_prepared_normalized_identity"]


def _overall_status(ready_keys: list[str]) -> str:
    if len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V31"
    if "replay_catalog_export" not in ready_keys:
        return _V30_OVERALL_STATUS(_without_prepared_identity(ready_keys))
    if "g15_prepared_normalized_identity" not in ready_keys:
        return "EXACT_REPLAY_CATALOG_READY_PREPARED_NORMALIZED_IDENTITY_INCOMPLETE"
    if "g15_exact_replay" not in ready_keys:
        return "PREPARED_NORMALIZED_IDENTITY_ATTESTED_G15_CAUSAL_REPLAY_INCOMPLETE"
    return _V30_OVERALL_STATUS(_without_prepared_identity(ready_keys))


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
    prepared_identity = "g15_prepared_normalized_identity" in ready_set
    replay = "g15_exact_replay" in ready_set
    return {
        **v30._summary_fields(_without_prepared_identity(ready)),
        "g15_prepared_normalized_identity_artifact": _PREPARED_IDENTITY.filename,
        "g15_prepared_normalized_identity_schema": _PREPARED_IDENTITY.schema,
        "prepared_publishers_explicit_and_positive": prepared_identity,
        "prepared_rows_exact_manifest_identity": prepared_identity,
        "prepared_events_within_definition_and_lane_periods": prepared_identity,
        "prepared_sources_chronological": prepared_identity,
        "prepared_definitions_precede_trade_and_mbo": prepared_identity,
        "g15_replay_blocked_until_prepared_normalized_identity": True,
        "g15_replay_bound_to_prepared_normalized_identity": replay,
    }


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
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
        "Readiness v31 requires exact prepared normalized identity and event-time bounds "
        "after replay-catalog export and before G15 causal replay. Missing publisher IDs, "
        "lane/event mismatches, definition-period leakage, chronological reversal, or "
        "missing prepared definitions cause a visible stand-down."
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
            "readiness v31 report schema or fingerprint mismatch"
        )
    with _legacy_contract():
        legacy.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError("readiness v31 overall status mismatch")
    for field, expected in _summary_fields(ready).items():
        if value.get(field) != expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v31 {field} summary mismatch"
            )

    ready_set = set(ready)
    catalog = "replay_catalog_export" in ready_set
    prepared_identity = "g15_prepared_normalized_identity" in ready_set
    replay = "g15_exact_replay" in ready_set
    if prepared_identity and not catalog:
        raise HistoricalRefinementReadinessError(
            "prepared normalized identity may not bypass exact replay-catalog export"
        )
    if replay and not prepared_identity:
        raise HistoricalRefinementReadinessError(
            "G15 replay may not bypass prepared normalized identity/time attestation"
        )
    order = list(value.get("stage_order") or [])
    catalog_index = order.index("replay_catalog_export")
    if order[catalog_index : catalog_index + 3] != [
        "replay_catalog_export",
        "g15_prepared_normalized_identity",
        "g15_exact_replay",
    ]:
        raise HistoricalRefinementReadinessError(
            "prepared normalized identity must remain between replay-catalog export and G15 replay"
        )
    if _PREPARED_IDENTITY.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "prepared normalized identity attestation must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v30._linked_fixture_chain()
    export = values["replay_catalog_export"]
    replay = values["g15_exact_replay"]
    guard = legacy._fixture_artifact(
        _PREPARED_IDENTITY,
        "G15_PREPARED_NORMALIZED_IDENTITY_AND_TIME_ATTESTED",
    )
    guard.update(
        {
            "bridge_fingerprint": export["g15_bridge_fingerprint"],
            "manifest_fingerprint": replay["manifest_fingerprint"],
            "prepared_corpus_fingerprint": replay["prepared_corpus_fingerprint"],
            "source_evidence_fingerprint": "n" * 64,
            "source_count": 26,
            "all_publishers_explicit_and_positive": True,
            "all_rows_match_exact_manifest_identity": True,
            "all_events_within_definition_and_lane_periods": True,
            "all_sources_chronological": True,
            "definitions_precede_trade_and_mbo_replay": True,
            "blockers": [],
            "next_action": "RUN_EXACT_G15_CAUSAL_REPLAY",
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
    guard.pop("fingerprint", None)
    guard["fingerprint"] = _fingerprint(guard)
    values["g15_prepared_normalized_identity"] = guard
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V31"
        assert complete["prepared_rows_exact_manifest_identity"] is True

        (root / _PREPARED_IDENTITY.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "g15_prepared_normalized_identity"
        assert blocked["g15_exact_replay_complete"] is False

    print("[ng_historical_refinement_readiness_v31] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v31.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
