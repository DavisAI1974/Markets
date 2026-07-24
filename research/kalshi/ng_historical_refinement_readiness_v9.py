#!/usr/bin/env python3
"""Canonical v9 readiness with exact partition-to-replay byte authorization.

V8 requires every completed replay-state span to remain inside one contiguous
common L1/MBO event-time window.  V9 additionally proves that all 24 G15
manifest lanes consumed by that replay are the exact unique sources authorized
by the broad-corpus same-lane partition gate.
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
import ng_historical_refinement_readiness_v8 as v8

SCHEMA = "ng_historical_refinement_readiness.v9"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V8_OVERALL_STATUS = v8._overall_status

_G15_PARTITION_REPLAY = StageSpec(
    "g15_exact_partition_replay_authorization",
    "g15_exact_partition_replay_authorization.json",
    "ng_g15_exact_partition_replay_authorization.v1",
    "fingerprint",
    frozenset(
        {
            "EXACT_G15_PARTITION_REPLAY_AUTHORIZED",
            "EXACT_G15_PARTITION_REPLAY_AUTHORIZED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g15_exact_partition_replay_authorization",
    ("validate_authorization",),
    "Bind every G15 replay-manifest lane to exactly one source from the verified broad-corpus exact partition before replay-window authorization.",
    required_fields=(
        "exact_partition_gate_fingerprint",
        "exact_replay_completion_fingerprint",
        "replay_fingerprint",
        "bridge_fingerprint",
        "all_g15_replay_sources_bound_to_exact_partition",
        "bound_replay_source_count",
    ),
    pre_outcome=True,
)

_V8_KEYS = [spec.key for spec in v8.STAGES]
_REPLAY_INDEX = _V8_KEYS.index("g15_exact_replay") + 1
STAGES: tuple[StageSpec, ...] = (
    *v8.STAGES[:_REPLAY_INDEX],
    _G15_PARTITION_REPLAY,
    *v8.STAGES[_REPLAY_INDEX:],
)

LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "broad_corpus_exact_partition",
        "fingerprint",
        "g15_exact_partition_replay_authorization",
        "exact_partition_gate_fingerprint",
    ),
    (
        "g15_exact_replay",
        "completion_fingerprint",
        "g15_exact_partition_replay_authorization",
        "exact_replay_completion_fingerprint",
    ),
    (
        "g15_exact_replay",
        "replay_fingerprint",
        "g15_exact_partition_replay_authorization",
        "replay_fingerprint",
    ),
    *v8.LINK_RULES,
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
    if "g16_counterfactual_publication" in ready_keys and len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V9"
    if (
        "g15_exact_partition_replay_authorization" in ready_keys
        and "g15_exact_replay_window_authorization" not in ready_keys
    ):
        return "G15_EXACT_PARTITION_REPLAY_AUTHORIZED_WINDOW_AUTHORIZATION_INCOMPLETE"
    if (
        "g15_exact_replay" in ready_keys
        and "g15_exact_partition_replay_authorization" not in ready_keys
    ):
        return "G15_EXACT_REPLAY_COMPLETE_PARTITION_BINDING_INCOMPLETE"
    return _V8_OVERALL_STATUS(
        [
            key
            for key in ready_keys
            if key != "g15_exact_partition_replay_authorization"
        ]
    )


@contextmanager
def _v8_contract() -> Iterator[None]:
    saved = (v8.SCHEMA, v8.STAGES, v8.LINK_RULES, v8._overall_status)
    v8.SCHEMA = SCHEMA
    v8.STAGES = STAGES
    v8.LINK_RULES = LINK_RULES
    v8._overall_status = _overall_status
    try:
        yield
    finally:
        v8.SCHEMA, v8.STAGES, v8.LINK_RULES, v8._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v8_contract():
        report = v8.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    report["g15_replay_sources_bound_to_exact_partition"] = (
        "g15_exact_partition_replay_authorization" in ready
    )
    report["note"] = (
        "Readiness v9 requires all 24 G15 replay-manifest lanes to match exactly one "
        "source from the verified same-lane broad-corpus partition before replay-window "
        "authorization and outcome-blind refinement."
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
            "readiness v9 report schema or fingerprint mismatch"
        )
    with _v8_contract():
        v8.validate_readiness_report(value)
    ready = list(value.get("ready_stages") or [])
    partition_replay_ready = "g15_exact_partition_replay_authorization" in ready
    if (
        value.get("g15_replay_sources_bound_to_exact_partition")
        is not partition_replay_ready
    ):
        raise HistoricalRefinementReadinessError(
            "readiness v9 partition-replay summary mismatch"
        )
    if "g15_exact_replay_window_authorization" in ready and not partition_replay_ready:
        raise HistoricalRefinementReadinessError(
            "replay-window authorization may not precede exact partition-to-replay binding"
        )
    if "g15_exact_refinement" in ready and not partition_replay_ready:
        raise HistoricalRefinementReadinessError(
            "G15 refinement may not precede exact partition-to-replay binding"
        )
    rows = {str(row.get("key")): row for row in value.get("stages") or []}
    if partition_replay_ready:
        row = rows.get("g15_exact_partition_replay_authorization") or {}
        if row.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
            raise HistoricalRefinementReadinessError(
                "partition-replay summary claims readiness while stage is not ready"
            )
        artifact = copy.deepcopy(dict(row.get("artifact") or {}))
        if artifact.get("bound_replay_source_count") != 24:
            raise HistoricalRefinementReadinessError(
                "partition-replay authorization must bind exactly 24 lanes"
            )
        if artifact.get("all_g15_replay_sources_bound_to_exact_partition") is not True:
            raise HistoricalRefinementReadinessError(
                "partition-replay authorization did not bind every G15 lane"
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
                f"readiness v9 must keep {field}=false"
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
    values = v8._linked_fixture_chain()
    source_partition = values["broad_corpus_exact_partition"]
    source_replay = values["g15_exact_replay"]
    authorization: dict[str, Any] = {
        "schema": _G15_PARTITION_REPLAY.schema,
        "status": "EXACT_G15_PARTITION_REPLAY_AUTHORIZED",
        "exact_partition_gate_fingerprint": source_partition["fingerprint"],
        "exact_replay_completion_fingerprint": source_replay[
            "completion_fingerprint"
        ],
        "replay_fingerprint": source_replay["replay_fingerprint"],
        "bridge_fingerprint": "fixture-bridge",
        "all_g15_replay_sources_bound_to_exact_partition": True,
        "bound_replay_source_count": 24,
    }
    authorization["fingerprint"] = _fingerprint(authorization)
    values["g15_exact_partition_replay_authorization"] = authorization
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V9"
        assert complete["g15_replay_sources_bound_to_exact_partition"] is True

        (root / _G15_PARTITION_REPLAY.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == (
            "g15_exact_partition_replay_authorization"
        )
        window = next(
            row
            for row in blocked["stages"]
            if row["key"] == "g15_exact_replay_window_authorization"
        )
        assert window["effective_status"] == "BLOCKED_BY_UPSTREAM"
        refinement = next(
            row
            for row in blocked["stages"]
            if row["key"] == "g15_exact_refinement"
        )
        assert refinement["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v9] selftest PASS")
    return 0


def _parse_stage_paths(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    allowed = {spec.key for spec in STAGES}
    for raw in values:
        if "=" not in raw:
            raise HistoricalRefinementReadinessError(
                "--stage-path requires KEY=PATH"
            )
        key, path = raw.split("=", 1)
        if key not in allowed or not path:
            raise HistoricalRefinementReadinessError(
                f"invalid stage path override: {raw!r}"
            )
        result[key] = Path(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build exact-partition-bound v9 NG historical readiness"
    )
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path("renders/ng_refine_s95")
    )
    parser.add_argument(
        "--stage-path", action="append", default=[], metavar="KEY=PATH"
    )
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
