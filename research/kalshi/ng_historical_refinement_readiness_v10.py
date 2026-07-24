#!/usr/bin/env python3
"""Canonical v10 readiness with exact G16 partition/replay-window authorization.

V9 binds every G15 replay lane to the verified broad-corpus source partition.
V10 extends that same byte and event-time wall to G16 before the pre-cutoff
causal posterior may run.  Every one of the 22 NGK26 replay lanes must be the
exact unique broad-partition source, and every emitted feature-state cutoff must
remain inside its exact common L1/MBO event-time window.
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
import ng_historical_refinement_readiness_v9 as v9

SCHEMA = "ng_historical_refinement_readiness.v10"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V9_OVERALL_STATUS = v9._overall_status

_G16_PARTITION_REPLAY = StageSpec(
    "g16_exact_partition_replay_authorization",
    "g16_exact_partition_replay_authorization.json",
    "ng_g16_exact_partition_replay_authorization.v1",
    "fingerprint",
    frozenset(
        {
            "EXACT_G16_PARTITION_REPLAY_WINDOWS_AUTHORIZED",
            "EXACT_G16_PARTITION_REPLAY_WINDOWS_AUTHORIZED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g16_exact_partition_replay_authorization",
    ("validate_authorization",),
    "Bind all 22 G16 replay lanes and every replay-state cutoff to the verified broad-corpus exact partition and common L1/MBO event windows before pre-cutoff causal refinement.",
    required_fields=(
        "exact_partition_gate_fingerprint",
        "prepared_replay_gate_fingerprint",
        "manifest_fingerprint",
        "prepared_corpus_fingerprint",
        "replay_fingerprint",
        "blind_prior_fingerprint",
        "source_binding_fingerprint",
        "window_contract_fingerprint",
        "all_g16_replay_sources_bound_to_exact_partition",
        "all_g16_state_spans_inside_exact_common_windows",
        "bound_replay_source_count",
    ),
    pre_outcome=True,
)

_V9_KEYS = [spec.key for spec in v9.STAGES]
_PREPARED_REPLAY_INDEX = _V9_KEYS.index("g16_prepared_replay") + 1
STAGES: tuple[StageSpec, ...] = (
    *v9.STAGES[:_PREPARED_REPLAY_INDEX],
    _G16_PARTITION_REPLAY,
    *v9.STAGES[_PREPARED_REPLAY_INDEX:],
)

LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "broad_corpus_exact_partition",
        "fingerprint",
        "g16_exact_partition_replay_authorization",
        "exact_partition_gate_fingerprint",
    ),
    (
        "g16_prepared_replay",
        "fingerprint",
        "g16_exact_partition_replay_authorization",
        "prepared_replay_gate_fingerprint",
    ),
    (
        "g16_prepared_replay",
        "manifest_fingerprint",
        "g16_exact_partition_replay_authorization",
        "manifest_fingerprint",
    ),
    (
        "g16_prepared_replay",
        "prepared_corpus_fingerprint",
        "g16_exact_partition_replay_authorization",
        "prepared_corpus_fingerprint",
    ),
    (
        "g16_prepared_replay",
        "replay_fingerprint",
        "g16_exact_partition_replay_authorization",
        "replay_fingerprint",
    ),
    (
        "g16_prepared_replay",
        "blind_prior_fingerprint",
        "g16_exact_partition_replay_authorization",
        "blind_prior_fingerprint",
    ),
    *v9.LINK_RULES,
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
    if "g16_counterfactual_publication" in ready_keys and len(ready_keys) == len(
        STAGES
    ):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V10"
    if (
        "g16_exact_partition_replay_authorization" in ready_keys
        and "g16_exact_causal" not in ready_keys
    ):
        return "G16_EXACT_PARTITION_REPLAY_WINDOWS_AUTHORIZED_CAUSAL_INCOMPLETE"
    if (
        "g16_prepared_replay" in ready_keys
        and "g16_exact_partition_replay_authorization" not in ready_keys
    ):
        return "G16_PREPARED_REPLAY_COMPLETE_PARTITION_WINDOW_BINDING_INCOMPLETE"
    return _V9_OVERALL_STATUS(
        [
            key
            for key in ready_keys
            if key != "g16_exact_partition_replay_authorization"
        ]
    )


@contextmanager
def _v9_contract() -> Iterator[None]:
    saved = (v9.SCHEMA, v9.STAGES, v9.LINK_RULES, v9._overall_status)
    v9.SCHEMA = SCHEMA
    v9.STAGES = STAGES
    v9.LINK_RULES = LINK_RULES
    v9._overall_status = _overall_status
    try:
        yield
    finally:
        v9.SCHEMA, v9.STAGES, v9.LINK_RULES, v9._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]]
    | None = None,
) -> dict[str, Any]:
    with _v9_contract():
        report = v9.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    report["g16_replay_sources_bound_to_exact_partition"] = (
        "g16_exact_partition_replay_authorization" in ready
    )
    report["g16_replay_state_windows_authorized"] = (
        "g16_exact_partition_replay_authorization" in ready
    )
    report["note"] = (
        "Readiness v10 requires every G16 replay lane to match one exact source "
        "from the verified broad-corpus partition and every emitted state cutoff "
        "to remain inside the exact common L1/MBO event-time window before the "
        "pre-cutoff causal posterior may run."
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
            "readiness v10 report schema or fingerprint mismatch"
        )
    with _v9_contract():
        v9.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    g16_binding_ready = "g16_exact_partition_replay_authorization" in ready
    for field in (
        "g16_replay_sources_bound_to_exact_partition",
        "g16_replay_state_windows_authorized",
    ):
        if value.get(field) is not g16_binding_ready:
            raise HistoricalRefinementReadinessError(
                f"readiness v10 {field} summary mismatch"
            )
    if "g16_exact_causal" in ready and not g16_binding_ready:
        raise HistoricalRefinementReadinessError(
            "G16 causal refinement may not precede exact partition/replay-window authorization"
        )
    if "g16_prepared_causal_authorization" in ready and not g16_binding_ready:
        raise HistoricalRefinementReadinessError(
            "G16 prepared causal authorization may not bypass exact partition/replay-window authorization"
        )

    rows = {str(row.get("key")): row for row in value.get("stages") or []}
    if g16_binding_ready:
        row = rows.get("g16_exact_partition_replay_authorization") or {}
        if row.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
            raise HistoricalRefinementReadinessError(
                "G16 partition/replay-window summary claims readiness while stage is not ready"
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
                f"readiness v10 must keep {field}=false"
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
    values = v9._linked_fixture_chain()
    partition = values["broad_corpus_exact_partition"]
    prepared = values["g16_prepared_replay"]
    authorization: dict[str, Any] = {
        "schema": _G16_PARTITION_REPLAY.schema,
        "status": "EXACT_G16_PARTITION_REPLAY_WINDOWS_AUTHORIZED",
        "exact_partition_gate_fingerprint": partition["fingerprint"],
        "prepared_replay_gate_fingerprint": prepared["fingerprint"],
        "manifest_fingerprint": prepared["manifest_fingerprint"],
        "prepared_corpus_fingerprint": prepared["prepared_corpus_fingerprint"],
        "replay_fingerprint": prepared["replay_fingerprint"],
        "blind_prior_fingerprint": prepared["blind_prior_fingerprint"],
        "source_binding_fingerprint": "fixture-source-binding",
        "window_contract_fingerprint": "fixture-window-contract",
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
        "bound_replay_source_count": 22,
    }
    authorization["fingerprint"] = _fingerprint(authorization)
    values["g16_exact_partition_replay_authorization"] = authorization
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
        assert (
            complete["status"]
            == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V10"
        )
        assert complete["g16_replay_sources_bound_to_exact_partition"] is True
        assert complete["g16_replay_state_windows_authorized"] is True

        (root / _G16_PARTITION_REPLAY.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert (
            blocked["first_blocking_stage"]
            == "g16_exact_partition_replay_authorization"
        )
        causal = next(
            row for row in blocked["stages"] if row["key"] == "g16_exact_causal"
        )
        assert causal["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v10] selftest PASS")
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
        description="Build exact G16 partition/replay-window v10 NG readiness"
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
