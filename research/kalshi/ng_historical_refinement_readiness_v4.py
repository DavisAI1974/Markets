#!/usr/bin/env python3
"""Canonical v4 readiness for the historical-first NG refinement chain.

Readiness v4 closes the G15 scoring bypass left in v3.  The six-factor
counterfactual attribution must be locked before the G15 actual substrate is
opened, blind and refined paths must be scored separately through the guarded
score gate, and the scored publication completion must bind those artifacts
before lesson adjudication or any G16 pre-cutoff work can proceed.

This module is observational only.  It never infers remote object presence,
opens outcome files, mutates blind forecasts or ``ng_brain.json``, grants
execution authority, or starts the options lane.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_historical_refinement_readiness as legacy

SCHEMA = "ng_historical_refinement_readiness.v4"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError


def _legacy_stage(key: str) -> StageSpec:
    for spec in legacy.STAGES:
        if spec.key == key:
            return spec
    raise HistoricalRefinementReadinessError(f"legacy readiness stage missing: {key}")


_G15_LOCK = StageSpec(
    "g15_counterfactual_scoring_lock",
    "g15_counterfactual_scoring_lock.json",
    "ng_g15_counterfactual_scoring_lock.v1",
    "lock_fingerprint",
    frozenset(
        {
            "EXACT_G15_COUNTERFACTUAL_SCORING_LOCKED",
            "EXACT_G15_COUNTERFACTUAL_SCORING_LOCKED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g15_counterfactual_scoring_wall",
    ("validate_lock",),
    "Lock the six-factor attribution and immutable blind/refined bytes before opening G15 actual outcomes.",
    required_fields=(
        "counterfactual_attribution_fingerprint",
        "exact_refinement_authorization_fingerprint",
        "exact_replay_completion_fingerprint",
        "blind_forecast_sha256",
        "refined_forecast_sha256",
        "refined_curve_fingerprint",
    ),
    pre_outcome=True,
)

_G15_SCORE = StageSpec(
    "g15_counterfactual_score_gate",
    "g15_counterfactual_score_gate.json",
    "ng_g15_counterfactual_score_gate.v1",
    "fingerprint",
    frozenset(
        {
            "EXACT_G15_COUNTERFACTUAL_SCORES_COMPLETE",
            "EXACT_G15_COUNTERFACTUAL_SCORES_COMPLETE_WITH_STAND_DOWNS",
        }
    ),
    "ng_g15_counterfactual_score_gate",
    ("validate_receipt",),
    "After lock validation, open the fixed G15 actual substrate and score blind and refined paths separately.",
    required_fields=(
        "counterfactual_scoring_lock_fingerprint",
        "counterfactual_attribution_fingerprint",
        "exact_refinement_authorization_fingerprint",
        "exact_replay_completion_fingerprint",
        "blind_score_fingerprint",
        "refined_score_fingerprint",
        "comparison_fingerprint",
    ),
    pre_outcome=False,
)

_G15_SCORED_PUBLICATION = StageSpec(
    "g15_counterfactual_scored_publication",
    "g15_counterfactual_scored_publication_completion.json",
    "ng_g15_counterfactual_scored_publication_completion.v1",
    "completion_fingerprint",
    frozenset(
        {
            "EXACT_G15_COUNTERFACTUAL_SCORED_PUBLICATION_COMPLETE",
            "EXACT_G15_COUNTERFACTUAL_SCORED_PUBLICATION_COMPLETE_WITH_STAND_DOWNS",
        }
    ),
    "ng_g15_counterfactual_scored_publication_gate",
    ("validate_completion",),
    "Bind the pre-outcome lock, guarded score receipt, separate scores, comparison, and canonical renders before lesson adjudication.",
    required_fields=(
        "counterfactual_scoring_lock_fingerprint",
        "counterfactual_score_gate_fingerprint",
        "counterfactual_attribution_fingerprint",
        "exact_publication_completion_fingerprint",
        "blind_score_fingerprint",
        "refined_score_fingerprint",
        "comparison_fingerprint",
        "lesson_adjudication_fingerprint",
    ),
    pre_outcome=False,
)


# Keep the exact publication stage because the scored-publication gate validates it,
# but it is no longer sufficient on its own.
STAGES: tuple[StageSpec, ...] = (
    _legacy_stage("corpus_coverage"),
    _legacy_stage("basis_inventory_regeneration"),
    _legacy_stage("replay_catalog_export"),
    _legacy_stage("g15_exact_replay"),
    _legacy_stage("g15_exact_refinement"),
    _legacy_stage("g15_counterfactual_attribution"),
    _G15_LOCK,
    _G15_SCORE,
    _legacy_stage("g15_publication"),
    _G15_SCORED_PUBLICATION,
    _legacy_stage("g15_counterfactual_lesson_gate"),
    _legacy_stage("g15_g16_counterfactual_lineage"),
    _legacy_stage("g16_corpus_basis"),
    _legacy_stage("g16_historical_replay"),
    _legacy_stage("g16_prepared_replay"),
    _legacy_stage("g16_exact_causal"),
    _legacy_stage("g16_prepared_causal_authorization"),
    _legacy_stage("g16_counterfactual_causal_authorization"),
    _legacy_stage("g16_prepared_curve_authorization"),
    _legacy_stage("g16_counterfactual_curve_authorization"),
    _legacy_stage("g16_counterfactual_curve_lock"),
    _legacy_stage("g16_counterfactual_publication"),
)

# source stage, source fingerprint path, target stage, target provenance path
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    # New G15 lock-first scoring lineage.
    ("g15_counterfactual_attribution", "fingerprint", "g15_counterfactual_scoring_lock", "counterfactual_attribution_fingerprint"),
    ("g15_exact_refinement", "authorization_fingerprint", "g15_counterfactual_scoring_lock", "exact_refinement_authorization_fingerprint"),
    ("g15_exact_replay", "completion_fingerprint", "g15_counterfactual_scoring_lock", "exact_replay_completion_fingerprint"),
    ("g15_counterfactual_scoring_lock", "lock_fingerprint", "g15_counterfactual_score_gate", "counterfactual_scoring_lock_fingerprint"),
    ("g15_counterfactual_attribution", "fingerprint", "g15_counterfactual_score_gate", "counterfactual_attribution_fingerprint"),
    ("g15_exact_refinement", "authorization_fingerprint", "g15_counterfactual_score_gate", "exact_refinement_authorization_fingerprint"),
    ("g15_exact_replay", "completion_fingerprint", "g15_counterfactual_score_gate", "exact_replay_completion_fingerprint"),
    ("g15_counterfactual_scoring_lock", "lock_fingerprint", "g15_counterfactual_scored_publication", "counterfactual_scoring_lock_fingerprint"),
    ("g15_counterfactual_score_gate", "fingerprint", "g15_counterfactual_scored_publication", "counterfactual_score_gate_fingerprint"),
    ("g15_counterfactual_attribution", "fingerprint", "g15_counterfactual_scored_publication", "counterfactual_attribution_fingerprint"),
    ("g15_publication", "completion_fingerprint", "g15_counterfactual_scored_publication", "exact_publication_completion_fingerprint"),
    ("g15_counterfactual_scored_publication", "lesson_adjudication_fingerprint", "g15_counterfactual_lesson_gate", "source.adjudication_fingerprint"),
    # Preserve all v3 G15-to-G16 and prepared-corpus lineage checks.
    *legacy.LINK_RULES,
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _apply_link_rules(rows: list[dict[str, Any]], values: Mapping[str, Mapping[str, Any]]) -> None:
    row_by_key = {row["key"]: row for row in rows}
    for source_key, source_path, target_key, target_path in LINK_RULES:
        source = values.get(source_key)
        target = values.get(target_key)
        if source is None or target is None:
            continue
        expected = legacy._path_get(source, source_path)
        observed = legacy._path_get(target, target_path)
        if not expected or observed != expected:
            row = row_by_key[target_key]
            row["validation"] = "FAIL"
            row["effective_status"] = "INVALID"
            row["blockers"] = sorted(
                set(row.get("blockers") or [])
                | {f"provenance link mismatch: {target_path} != {source_key}.{source_path}"}
            )


def _overall_status(ready_keys: list[str]) -> str:
    if "g16_counterfactual_publication" in ready_keys and len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V4"
    if "g16_counterfactual_curve_lock" in ready_keys:
        return "G15_LOCK_FIRST_COMPLETE_G16_COUNTERFACTUAL_CURVE_LOCKED_SCORING_INCOMPLETE"
    if "g16_counterfactual_curve_authorization" in ready_keys:
        return "G15_LOCK_FIRST_COMPLETE_G16_COUNTERFACTUAL_CURVE_AUTHORIZED_LOCK_INCOMPLETE"
    if "g16_counterfactual_causal_authorization" in ready_keys:
        return "G15_LOCK_FIRST_COMPLETE_G16_COUNTERFACTUAL_CAUSAL_AUTHORIZED_CURVE_INCOMPLETE"
    if "g15_g16_counterfactual_lineage" in ready_keys:
        return "G15_LOCK_FIRST_LINEAGE_BOUND_G16_REPLAY_INCOMPLETE"
    if "g15_counterfactual_lesson_gate" in ready_keys:
        return "G15_LOCK_FIRST_LESSONS_READY_G16_LINEAGE_INCOMPLETE"
    if "g15_counterfactual_scored_publication" in ready_keys:
        return "G15_COUNTERFACTUAL_SCORED_PUBLICATION_COMPLETE_LESSONS_INCOMPLETE"
    if "g15_publication" in ready_keys:
        return "G15_EXACT_PUBLICATION_COMPLETE_SCORED_PUBLICATION_GATE_INCOMPLETE"
    if "g15_counterfactual_score_gate" in ready_keys:
        return "G15_COUNTERFACTUAL_SCORES_COMPLETE_RENDER_PUBLICATION_INCOMPLETE"
    if "g15_counterfactual_scoring_lock" in ready_keys:
        return "G15_COUNTERFACTUAL_SCORING_LOCKED_FIXED_SCORING_INCOMPLETE"
    if "g15_counterfactual_attribution" in ready_keys:
        return "G15_COUNTERFACTUAL_ATTRIBUTION_READY_PRE_SCORING_LOCK_INCOMPLETE"
    if "g15_exact_refinement" in ready_keys:
        return "G15_EXACT_REFINEMENT_READY_ATTRIBUTION_INCOMPLETE"
    if "g15_exact_replay" in ready_keys:
        return "G15_EXACT_REPLAY_READY_REFINEMENT_INCOMPLETE"
    if "replay_catalog_export" in ready_keys:
        return "EXACT_REPLAY_CATALOG_READY_REPLAY_INCOMPLETE"
    if "corpus_coverage" in ready_keys:
        return "EXACT_INTERSECTIONS_READY_INVENTORY_OR_EXPORT_INCOMPLETE"
    return "BLOCKED_OR_UNVERIFIED"


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    stage_paths = dict(stage_paths or {})
    validator_overrides = dict(validator_overrides or {})
    rows: list[dict[str, Any]] = []
    values: dict[str, dict[str, Any]] = {}
    for spec in STAGES:
        path = stage_paths.get(spec.key, artifact_dir / spec.filename)
        row, value = legacy.evaluate_stage(
            spec, path, validator_override=validator_overrides.get(spec.key)
        )
        rows.append(row)
        if value is not None:
            values[spec.key] = value
    _apply_link_rules(rows, values)

    upstream_ready = True
    for row in rows:
        artifact_ready = row["effective_status"] in {"READY", "READY_WITH_STAND_DOWNS"}
        if artifact_ready and not upstream_ready:
            row["effective_status"] = "BLOCKED_BY_UPSTREAM"
            row["blockers"] = sorted(
                set((row.get("blockers") or []) + ["an earlier stage is not ready"])
            )
        upstream_ready = upstream_ready and artifact_ready

    ready_keys = [
        row["key"]
        for row in rows
        if row["effective_status"] in {"READY", "READY_WITH_STAND_DOWNS"}
    ]
    first_blocking = next(
        (
            row
            for row in rows
            if row["effective_status"] not in {"READY", "READY_WITH_STAND_DOWNS"}
        ),
        None,
    )
    g16_complete = "g16_counterfactual_publication" in ready_keys
    report = {
        "schema": SCHEMA,
        "status": _overall_status(ready_keys),
        "market": "NG",
        "historical_first": True,
        "artifact_dir": str(artifact_dir),
        "stage_order": [spec.key for spec in STAGES],
        "stages": rows,
        "ready_stage_count": len(ready_keys),
        "ready_stages": ready_keys,
        "first_blocking_stage": None if first_blocking is None else first_blocking["key"],
        "next_action": "NONE_CHAIN_COMPLETE" if first_blocking is None else first_blocking["next_action"],
        "broad_corpus_verified": legacy._broad_corpus_verified(values.get("corpus_coverage")),
        "exact_replay_intersections_ready": "corpus_coverage" in ready_keys,
        "daily_basis_inventories_ready": "basis_inventory_regeneration" in ready_keys,
        "g15_counterfactual_attribution_complete": "g15_counterfactual_attribution" in ready_keys,
        "g15_counterfactual_scoring_locked_before_actual_open": "g15_counterfactual_scoring_lock" in ready_keys,
        "g15_blind_and_refined_scores_separate": "g15_counterfactual_score_gate" in ready_keys,
        "g15_exact_publication_complete": "g15_publication" in ready_keys,
        "g15_counterfactual_scored_publication_complete": "g15_counterfactual_scored_publication" in ready_keys,
        "g15_counterfactual_lessons_complete": "g15_counterfactual_lesson_gate" in ready_keys,
        "g15_g16_counterfactual_lineage_complete": "g15_g16_counterfactual_lineage" in ready_keys,
        "g16_prepared_replay_ready": "g16_prepared_replay" in ready_keys,
        "g16_counterfactual_curve_locked_before_scoring": "g16_counterfactual_curve_lock" in ready_keys,
        "g16_exact_publication_complete": g16_complete,
        "hardened_g16_chain_complete": g16_complete,
        "stand_down_days": sorted(
            {day for row in rows for day in row.get("stand_down_days") or []}
        ),
        "remote_presence_inferred": False,
        "actual_outcome_paths_loaded": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "note": (
            "Readiness v4 requires the six-factor G15 attribution lock before actual-file access, "
            "a guarded separate blind/refined score receipt, and a scored-publication completion "
            "before lesson adjudication or G16. The v3 standalone G15 publication route cannot complete this chain."
        ),
    }
    report["fingerprint"] = _fingerprint(report)
    validate_readiness_report(report)
    return report


def validate_readiness_report(report: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(report))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != _fingerprint(value):
        raise HistoricalRefinementReadinessError(
            "readiness v4 report schema or fingerprint mismatch"
        )
    expected_order = [spec.key for spec in STAGES]
    if value.get("stage_order") != expected_order:
        raise HistoricalRefinementReadinessError("readiness v4 stage order mismatch")
    rows = value.get("stages")
    if not isinstance(rows, list) or [row.get("key") for row in rows] != expected_order:
        raise HistoricalRefinementReadinessError(
            "readiness v4 stage rows are incomplete or reordered"
        )
    ready = [
        row["key"]
        for row in rows
        if row.get("effective_status") in {"READY", "READY_WITH_STAND_DOWNS"}
    ]
    if value.get("ready_stages") != ready or int(value.get("ready_stage_count") or 0) != len(ready):
        raise HistoricalRefinementReadinessError("readiness v4 ready-stage summary mismatch")
    first = next(
        (
            row["key"]
            for row in rows
            if row.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}
        ),
        None,
    )
    if value.get("first_blocking_stage") != first:
        raise HistoricalRefinementReadinessError(
            "readiness v4 first-blocking-stage mismatch"
        )
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError("readiness v4 overall status mismatch")
    summaries = {
        "g15_counterfactual_scoring_locked_before_actual_open": "g15_counterfactual_scoring_lock",
        "g15_blind_and_refined_scores_separate": "g15_counterfactual_score_gate",
        "g15_counterfactual_scored_publication_complete": "g15_counterfactual_scored_publication",
        "hardened_g16_chain_complete": "g16_counterfactual_publication",
        "g16_counterfactual_curve_locked_before_scoring": "g16_counterfactual_curve_lock",
    }
    for field, key in summaries.items():
        if value.get(field) != (key in ready):
            raise HistoricalRefinementReadinessError(
                f"readiness v4 summary mismatch: {field}"
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
                f"readiness v4 must keep {field}=false"
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


def _fixture_artifact(spec: StageSpec, status: str, *, stand_down: bool = False) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": spec.schema,
        "status": status,
        "execution_authority": False,
        "may_update_ng_brain": False,
        "random_shuffle_used": False,
        "options_lane_started": False,
        "actual_g16_outcomes_used": False,
    }
    if spec.pre_outcome:
        value["actual_outcomes_used"] = False
    for field in spec.required_fields:
        legacy._path_set(value, field, f"fixture:{spec.key}:{field}")
    if stand_down:
        value["stand_down_days"] = ["20260315"]
    value[spec.fingerprint_field] = _fingerprint(value)
    return value


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = {
        spec.key: _fixture_artifact(spec, sorted(spec.ready_statuses)[0])
        for spec in STAGES
    }
    incoming: dict[str, list[tuple[str, str, str]]] = {}
    for source_key, source_path, target_key, target_path in LINK_RULES:
        incoming.setdefault(target_key, []).append((source_key, source_path, target_path))
    for spec in STAGES:
        value = values[spec.key]
        for source_key, source_path, target_path in incoming.get(spec.key, []):
            legacy._path_set(value, target_path, legacy._path_get(values[source_key], source_path))
        value.pop(spec.fingerprint_field, None)
        value[spec.fingerprint_field] = _fingerprint(value)
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V4"
        assert complete["g15_counterfactual_scoring_locked_before_actual_open"] is True
        assert complete["g15_blind_and_refined_scores_separate"] is True
        assert complete["g15_counterfactual_scored_publication_complete"] is True
    print("[ng_historical_refinement_readiness_v4] selftest PASS")
    return 0


def _parse_stage_paths(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    allowed = {spec.key for spec in STAGES}
    for raw in values:
        if "=" not in raw:
            raise HistoricalRefinementReadinessError("--stage-path requires KEY=PATH")
        key, path = raw.split("=", 1)
        if key not in allowed or not path:
            raise HistoricalRefinementReadinessError(
                f"invalid stage path override: {raw!r}"
            )
        result[key] = Path(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build canonical lock-first v4 NG historical refinement readiness"
    )
    parser.add_argument("--artifact-dir", type=Path, default=Path("renders/ng_refine_s95"))
    parser.add_argument("--stage-path", action="append", default=[], metavar="KEY=PATH")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    report = build_readiness_report(
        args.artifact_dir, stage_paths=_parse_stage_paths(args.stage_path)
    )
    if args.out:
        _atomic_json(args.out, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
