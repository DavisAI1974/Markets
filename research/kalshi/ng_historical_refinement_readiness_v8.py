#!/usr/bin/env python3
"""Canonical v8 readiness with exact G15 replay-window authorization.

Readiness v7 verifies broad scope, exact cross-lane overlap, and exact same-lane
source partitioning before replay.  V8 additionally requires the completed
G15 replay's full state span for every canonical session to remain inside one
deterministic contiguous common L1/MBO event-time window before refinement.
The lock-first G15 scoring wall and full counterfactual G16 lineage are unchanged.
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
import ng_historical_refinement_readiness_v7 as v7

SCHEMA = "ng_historical_refinement_readiness.v8"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V7_OVERALL_STATUS = v7._overall_status

_G15_REPLAY_WINDOW = StageSpec(
    "g15_exact_replay_window_authorization",
    "g15_exact_replay_window_authorization.json",
    "ng_g15_exact_replay_window_authorization.v1",
    "fingerprint",
    frozenset(
        {
            "EXACT_G15_REPLAY_WINDOWS_AUTHORIZED",
            "EXACT_G15_REPLAY_WINDOWS_AUTHORIZED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g15_exact_replay_window_authorization",
    ("validate_authorization",),
    "Bind every completed G15 replay state span to one exact contiguous common L1/MBO event-time window before refinement.",
    required_fields=(
        "broad_exact_overlap_fingerprint",
        "exact_replay_completion_fingerprint",
        "replay_fingerprint",
        "window_contract_fingerprint",
        "all_replay_state_spans_inside_exact_common_windows",
    ),
    pre_outcome=True,
)

_V7_KEYS = [spec.key for spec in v7.STAGES]
_REPLAY_INDEX = _V7_KEYS.index("g15_exact_replay") + 1
STAGES: tuple[StageSpec, ...] = (
    *v7.STAGES[:_REPLAY_INDEX],
    _G15_REPLAY_WINDOW,
    *v7.STAGES[_REPLAY_INDEX:],
)

LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "broad_corpus_exact_overlap",
        "fingerprint",
        "g15_exact_replay_window_authorization",
        "broad_exact_overlap_fingerprint",
    ),
    (
        "g15_exact_replay",
        "completion_fingerprint",
        "g15_exact_replay_window_authorization",
        "exact_replay_completion_fingerprint",
    ),
    (
        "g15_exact_replay",
        "replay_fingerprint",
        "g15_exact_replay_window_authorization",
        "replay_fingerprint",
    ),
    *v7.LINK_RULES,
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _overall_status(ready_keys: list[str]) -> str:
    if "g16_counterfactual_publication" in ready_keys and len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V8"
    if (
        "g15_exact_replay_window_authorization" in ready_keys
        and "g15_exact_refinement" not in ready_keys
    ):
        return "G15_EXACT_REPLAY_WINDOWS_AUTHORIZED_REFINEMENT_INCOMPLETE"
    if "g15_exact_replay" in ready_keys and "g15_exact_replay_window_authorization" not in ready_keys:
        return "G15_EXACT_REPLAY_COMPLETE_WINDOW_AUTHORIZATION_INCOMPLETE"
    return _V7_OVERALL_STATUS(
        [key for key in ready_keys if key != "g15_exact_replay_window_authorization"]
    )


@contextmanager
def _v7_contract() -> Iterator[None]:
    saved = (v7.SCHEMA, v7.STAGES, v7.LINK_RULES, v7._overall_status)
    v7.SCHEMA = SCHEMA
    v7.STAGES = STAGES
    v7.LINK_RULES = LINK_RULES
    v7._overall_status = _overall_status
    try:
        yield
    finally:
        v7.SCHEMA, v7.STAGES, v7.LINK_RULES, v7._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v7_contract():
        report = v7.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    report["g15_replay_windows_authorized"] = (
        "g15_exact_replay_window_authorization" in ready
    )
    report["note"] = (
        "Readiness v8 requires the completed G15 replay state span for every canonical day "
        "to fit inside one deterministic contiguous exact common L1/MBO event-time window "
        "before outcome-blind refinement."
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
            "readiness v8 report schema or fingerprint mismatch"
        )
    with _v7_contract():
        v7.validate_readiness_report(value)
    ready = list(value.get("ready_stages") or [])
    window_ready = "g15_exact_replay_window_authorization" in ready
    if value.get("g15_replay_windows_authorized") is not window_ready:
        raise HistoricalRefinementReadinessError(
            "readiness v8 replay-window summary mismatch"
        )
    if "g15_exact_refinement" in ready and not window_ready:
        raise HistoricalRefinementReadinessError(
            "G15 refinement may not be ready before exact replay-window authorization"
        )
    rows = {str(row.get("key")): row for row in value.get("stages") or []}
    if window_ready:
        row = rows.get("g15_exact_replay_window_authorization") or {}
        if row.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
            raise HistoricalRefinementReadinessError(
                "replay-window summary claims readiness while stage is not ready"
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
                f"readiness v8 must keep {field}=false"
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


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    with _v7_contract():
        return v7._linked_fixture_chain()


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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V8"
        assert complete["g15_replay_windows_authorized"] is True
        (root / _G15_REPLAY_WINDOW.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "g15_exact_replay_window_authorization"
        refinement = next(
            row for row in blocked["stages"] if row["key"] == "g15_exact_refinement"
        )
        assert refinement["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v8] selftest PASS")
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
        description="Build canonical exact-replay-window-first v8 NG historical readiness"
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
