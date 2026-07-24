#!/usr/bin/env python3
"""Canonical v5 readiness with mandatory broad-corpus verification before G15.

Readiness v4 correctly locked G15 attribution and forecast bytes before outcomes, but it
still accepted ``G15_G16_EXACT_READY_BROAD_COVERAGE_UNVERIFIED`` as a ready corpus stage.
V5 keeps the exact target-day pipeline while adding an independent, deterministic gate
for the completed one-year L1/dense-trades and spring/summer MBO inventories. Exact
G15 replay cannot advance until that broad scope is verified from byte-inspected objects.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_historical_refinement_readiness as legacy
import ng_historical_refinement_readiness_v4 as v4

SCHEMA = "ng_historical_refinement_readiness.v5"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError

_BROAD_SCOPE = StageSpec(
    "broad_corpus_scope",
    "ng_broad_corpus_scope_gate.json",
    "ng_broad_corpus_scope_gate.v1",
    "fingerprint",
    frozenset({"BROAD_CORPUS_SCOPE_VERIFIED"}),
    "ng_broad_corpus_scope_gate",
    ("validate_gate",),
    "Verify the complete one-year L1/dense-trades and spring/summer MBO inventories before configuring G15 replay.",
    required_fields=(
        "inspection_receipt_fingerprint",
        "catalog_fingerprint",
        "coverage_audit_fingerprint",
        "broad_l1_one_year_verified",
        "broad_mbo_spring_summer_verified",
    ),
    pre_outcome=True,
)

STAGES: tuple[StageSpec, ...] = (
    *v4.STAGES[:3],
    _BROAD_SCOPE,
    *v4.STAGES[3:],
)

LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("corpus_coverage", "fingerprint", "broad_corpus_scope", "coverage_audit_fingerprint"),
    *v4.LINK_RULES,
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V5"
    if "broad_corpus_scope" in ready_keys and "g15_exact_replay" not in ready_keys:
        return "BROAD_CORPUS_VERIFIED_G15_REPLAY_INCOMPLETE"
    return v4._overall_status([key for key in ready_keys if key != "broad_corpus_scope"])


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
        "broad_corpus_verified": "broad_corpus_scope" in ready_keys,
        "exact_replay_intersections_ready": "corpus_coverage" in ready_keys,
        "daily_basis_inventories_ready": "basis_inventory_regeneration" in ready_keys,
        "replay_catalogs_ready": "replay_catalog_export" in ready_keys,
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
            "Readiness v5 makes the independently reconstructed broad-corpus scope gate mandatory after exact "
            "target-day catalog export and before G15 replay. A target-day-only coverage audit cannot advance G15."
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
            "readiness v5 report schema or fingerprint mismatch"
        )
    expected_order = [spec.key for spec in STAGES]
    if value.get("stage_order") != expected_order:
        raise HistoricalRefinementReadinessError("readiness v5 stage order mismatch")
    rows = value.get("stages")
    if not isinstance(rows, list) or [row.get("key") for row in rows] != expected_order:
        raise HistoricalRefinementReadinessError(
            "readiness v5 stage rows are incomplete or reordered"
        )
    ready = [
        row["key"]
        for row in rows
        if row.get("effective_status") in {"READY", "READY_WITH_STAND_DOWNS"}
    ]
    if value.get("ready_stages") != ready or int(value.get("ready_stage_count") or 0) != len(ready):
        raise HistoricalRefinementReadinessError("readiness v5 ready-stage summary mismatch")
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
            "readiness v5 first-blocking-stage mismatch"
        )
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError("readiness v5 overall status mismatch")
    summaries = {
        "broad_corpus_verified": "broad_corpus_scope",
        "g15_counterfactual_scoring_locked_before_actual_open": "g15_counterfactual_scoring_lock",
        "g15_blind_and_refined_scores_separate": "g15_counterfactual_score_gate",
        "g15_counterfactual_scored_publication_complete": "g15_counterfactual_scored_publication",
        "hardened_g16_chain_complete": "g16_counterfactual_publication",
        "g16_counterfactual_curve_locked_before_scoring": "g16_counterfactual_curve_lock",
    }
    for field, key in summaries.items():
        if value.get(field) != (key in ready):
            raise HistoricalRefinementReadinessError(
                f"readiness v5 summary mismatch: {field}"
            )
    if "g15_exact_replay" in ready and "broad_corpus_scope" not in ready:
        raise HistoricalRefinementReadinessError(
            "G15 replay may not be ready before broad corpus scope verification"
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
                f"readiness v5 must keep {field}=false"
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


def _fixture_artifact(spec: StageSpec, status: str) -> dict[str, Any]:
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V5"
        assert complete["broad_corpus_verified"] is True
        (root / _BROAD_SCOPE.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "broad_corpus_scope"
        g15_row = next(row for row in blocked["stages"] if row["key"] == "g15_exact_replay")
        assert g15_row["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v5] selftest PASS")
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
        description="Build canonical broad-corpus-first v5 NG historical refinement readiness"
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
