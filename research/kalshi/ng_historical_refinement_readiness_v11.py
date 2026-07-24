#!/usr/bin/env python3
"""Canonical v11 readiness with exact G16 causal provenance authorization.

V10 proves that G16 replay bytes came from the verified broad-corpus partition
and that replay-state cutoffs stayed inside exact common L1/MBO event windows.
V11 binds that proof into the G15-counterfactual causal authorization itself,
so the outcome-blind curve path cannot consume a separately valid posterior
that bypassed the exact source/window wall.
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
import ng_historical_refinement_readiness_v10 as v10

SCHEMA = "ng_historical_refinement_readiness.v11"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V10_OVERALL_STATUS = v10._overall_status

_G16_EXACT_COUNTERFACTUAL_CAUSAL = StageSpec(
    "g16_exact_counterfactual_causal_authorization",
    "g16_exact_counterfactual_causal_authorization.json",
    "ng_g16_exact_counterfactual_causal_authorization.v1",
    "fingerprint",
    frozenset(
        {
            "G16_EXACT_COUNTERFACTUAL_CAUSAL_AUTHORIZED",
            "G16_EXACT_COUNTERFACTUAL_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g16_exact_counterfactual_causal_authorization",
    ("validate_authorization",),
    "Bind verified G16 replay bytes and exact state windows into the pre-cutoff G15-counterfactual causal posterior before any refined curve may be built.",
    required_fields=(
        "exact_partition_replay_authorization_fingerprint",
        "counterfactual_causal_authorization_fingerprint",
        "exact_partition_gate_fingerprint",
        "prepared_replay_gate_fingerprint",
        "manifest_fingerprint",
        "prepared_corpus_fingerprint",
        "replay_fingerprint",
        "blind_prior_fingerprint",
        "source_binding_fingerprint",
        "window_contract_fingerprint",
        "prepared_causal_authorization_fingerprint",
        "counterfactual_lineage_gate_fingerprint",
        "candidate_count",
        "all_g16_replay_sources_bound_to_exact_partition",
        "all_g16_state_spans_inside_exact_common_windows",
    ),
    pre_outcome=True,
)

_V10_KEYS = [spec.key for spec in v10.STAGES]
_CAUSAL_INDEX = _V10_KEYS.index("g16_counterfactual_causal_authorization") + 1
STAGES: tuple[StageSpec, ...] = (
    *v10.STAGES[:_CAUSAL_INDEX],
    _G16_EXACT_COUNTERFACTUAL_CAUSAL,
    *v10.STAGES[_CAUSAL_INDEX:],
)

LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "g16_exact_partition_replay_authorization",
        "fingerprint",
        "g16_exact_counterfactual_causal_authorization",
        "exact_partition_replay_authorization_fingerprint",
    ),
    (
        "g16_counterfactual_causal_authorization",
        "fingerprint",
        "g16_exact_counterfactual_causal_authorization",
        "counterfactual_causal_authorization_fingerprint",
    ),
    (
        "g16_exact_partition_replay_authorization",
        "exact_partition_gate_fingerprint",
        "g16_exact_counterfactual_causal_authorization",
        "exact_partition_gate_fingerprint",
    ),
    (
        "g16_exact_partition_replay_authorization",
        "source_binding_fingerprint",
        "g16_exact_counterfactual_causal_authorization",
        "source_binding_fingerprint",
    ),
    (
        "g16_exact_partition_replay_authorization",
        "window_contract_fingerprint",
        "g16_exact_counterfactual_causal_authorization",
        "window_contract_fingerprint",
    ),
    (
        "g16_counterfactual_causal_authorization",
        "prepared_causal_authorization_fingerprint",
        "g16_exact_counterfactual_causal_authorization",
        "prepared_causal_authorization_fingerprint",
    ),
    (
        "g16_counterfactual_causal_authorization",
        "counterfactual_lineage_gate_fingerprint",
        "g16_exact_counterfactual_causal_authorization",
        "counterfactual_lineage_gate_fingerprint",
    ),
    (
        "g16_counterfactual_causal_authorization",
        "candidate_count",
        "g16_exact_counterfactual_causal_authorization",
        "candidate_count",
    ),
    *v10.LINK_RULES,
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V11"
    if (
        "g16_exact_counterfactual_causal_authorization" in ready_keys
        and "g16_prepared_curve_authorization" not in ready_keys
    ):
        return "G16_EXACT_COUNTERFACTUAL_CAUSAL_AUTHORIZED_CURVE_INCOMPLETE"
    if (
        "g16_counterfactual_causal_authorization" in ready_keys
        and "g16_exact_counterfactual_causal_authorization" not in ready_keys
    ):
        return "G16_COUNTERFACTUAL_CAUSAL_COMPLETE_EXACT_CORPUS_BINDING_INCOMPLETE"
    return _V10_OVERALL_STATUS(
        [
            key
            for key in ready_keys
            if key != "g16_exact_counterfactual_causal_authorization"
        ]
    )


@contextmanager
def _v10_contract() -> Iterator[None]:
    saved = (v10.SCHEMA, v10.STAGES, v10.LINK_RULES, v10._overall_status)
    v10.SCHEMA = SCHEMA
    v10.STAGES = STAGES
    v10.LINK_RULES = LINK_RULES
    v10._overall_status = _overall_status
    try:
        yield
    finally:
        v10.SCHEMA, v10.STAGES, v10.LINK_RULES, v10._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]]
    | None = None,
) -> dict[str, Any]:
    with _v10_contract():
        report = v10.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    exact_causal_ready = "g16_exact_counterfactual_causal_authorization" in ready
    report["g16_causal_authority_bound_to_exact_replay_bytes"] = exact_causal_ready
    report["g16_causal_authority_bound_to_exact_event_windows"] = exact_causal_ready
    report["note"] = (
        "Readiness v11 requires the G16 pre-cutoff posterior to carry both the "
        "verified exact replay-byte/event-window proof and the locked G15 "
        "counterfactual lesson lineage before any outcome-blind curve adapter runs."
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
            "readiness v11 report schema or fingerprint mismatch"
        )
    with _v10_contract():
        v10.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    exact_causal_ready = "g16_exact_counterfactual_causal_authorization" in ready
    for field in (
        "g16_causal_authority_bound_to_exact_replay_bytes",
        "g16_causal_authority_bound_to_exact_event_windows",
    ):
        if value.get(field) is not exact_causal_ready:
            raise HistoricalRefinementReadinessError(
                f"readiness v11 {field} summary mismatch"
            )
    if "g16_prepared_curve_authorization" in ready and not exact_causal_ready:
        raise HistoricalRefinementReadinessError(
            "G16 prepared curve authorization may not bypass exact causal provenance"
        )
    if "g16_counterfactual_curve_authorization" in ready and not exact_causal_ready:
        raise HistoricalRefinementReadinessError(
            "G16 counterfactual curve authorization may not bypass exact causal provenance"
        )
    rows = {str(row.get("key")): row for row in value.get("stages") or []}
    if exact_causal_ready:
        row = rows.get("g16_exact_counterfactual_causal_authorization") or {}
        if row.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
            raise HistoricalRefinementReadinessError(
                "exact causal provenance summary claims readiness while stage is not ready"
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
                f"readiness v11 must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementReadinessError(
            "one signal authority was not preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementReadinessError("blind forecasts were not preserved")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementReadinessError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementReadinessError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v10._linked_fixture_chain()
    exact = values["g16_exact_partition_replay_authorization"]
    causal = values["g16_counterfactual_causal_authorization"]
    authorization: dict[str, Any] = {
        "schema": _G16_EXACT_COUNTERFACTUAL_CAUSAL.schema,
        "status": "G16_EXACT_COUNTERFACTUAL_CAUSAL_AUTHORIZED",
        "exact_partition_replay_authorization_fingerprint": exact["fingerprint"],
        "counterfactual_causal_authorization_fingerprint": causal["fingerprint"],
        "exact_partition_gate_fingerprint": exact["exact_partition_gate_fingerprint"],
        "prepared_replay_gate_fingerprint": exact["prepared_replay_gate_fingerprint"],
        "manifest_fingerprint": exact["manifest_fingerprint"],
        "prepared_corpus_fingerprint": exact["prepared_corpus_fingerprint"],
        "replay_fingerprint": exact["replay_fingerprint"],
        "blind_prior_fingerprint": exact["blind_prior_fingerprint"],
        "source_binding_fingerprint": exact["source_binding_fingerprint"],
        "window_contract_fingerprint": exact["window_contract_fingerprint"],
        "prepared_causal_authorization_fingerprint": causal[
            "prepared_causal_authorization_fingerprint"
        ],
        "counterfactual_lineage_gate_fingerprint": causal[
            "counterfactual_lineage_gate_fingerprint"
        ],
        "candidate_count": causal["candidate_count"],
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
    }
    authorization["fingerprint"] = _fingerprint(authorization)
    values["g16_exact_counterfactual_causal_authorization"] = authorization
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
            == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V11"
        )
        assert complete["g16_causal_authority_bound_to_exact_replay_bytes"] is True
        assert complete["g16_causal_authority_bound_to_exact_event_windows"] is True

        (root / _G16_EXACT_COUNTERFACTUAL_CAUSAL.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert (
            blocked["first_blocking_stage"]
            == "g16_exact_counterfactual_causal_authorization"
        )
        curve = next(
            row
            for row in blocked["stages"]
            if row["key"] == "g16_prepared_curve_authorization"
        )
        assert curve["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v11] selftest PASS")
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
        description="Build exact G16 causal-provenance v11 NG readiness"
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
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("all_ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
