#!/usr/bin/env python3
"""Canonical v12 readiness with exact corpus provenance bound into the G16 curve.

V11 joins verified replay bytes and common L1/MBO event windows to the locked
G15 counterfactual causal posterior. V12 requires the deterministic G16 curve
authorization itself to carry that exact causal proof before the refined curve
may be locked or any fixed G16 outcome substrate may be opened.
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
import ng_historical_refinement_readiness_v11 as v11

SCHEMA = "ng_historical_refinement_readiness.v12"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V11_OVERALL_STATUS = v11._overall_status

_G16_EXACT_COUNTERFACTUAL_CURVE = StageSpec(
    "g16_exact_counterfactual_curve_authorization",
    "g16_exact_counterfactual_curve_authorization.json",
    "ng_g16_exact_counterfactual_curve_authorization.v1",
    "fingerprint",
    frozenset(
        {
            "G16_EXACT_COUNTERFACTUAL_CURVE_AUTHORIZED",
            "G16_EXACT_COUNTERFACTUAL_CURVE_AUTHORIZED_WITH_STAND_DOWNS",
        }
    ),
    None,
    (),
    "Bind the deterministic outcome-blind G16 refined curve directly to verified replay bytes, exact common L1/MBO event windows, and locked G15 counterfactual lesson lineage before the pre-scoring lock.",
    required_fields=(
        "exact_counterfactual_causal_authorization_fingerprint",
        "counterfactual_curve_authorization_fingerprint",
        "exact_partition_replay_authorization_fingerprint",
        "counterfactual_causal_authorization_fingerprint",
        "exact_partition_gate_fingerprint",
        "source_binding_fingerprint",
        "window_contract_fingerprint",
        "prepared_curve_authorization_fingerprint",
        "prepared_causal_authorization_fingerprint",
        "replay_fingerprint",
        "refined_curve_fingerprint",
        "candidate_count",
        "bound_replay_source_count",
        "all_g16_replay_sources_bound_to_exact_partition",
        "all_g16_state_spans_inside_exact_common_windows",
    ),
    pre_outcome=True,
)

_V11_KEYS = [spec.key for spec in v11.STAGES]
_CURVE_INDEX = _V11_KEYS.index("g16_counterfactual_curve_authorization") + 1
STAGES: tuple[StageSpec, ...] = (
    *v11.STAGES[:_CURVE_INDEX],
    _G16_EXACT_COUNTERFACTUAL_CURVE,
    *v11.STAGES[_CURVE_INDEX:],
)

LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "g16_exact_counterfactual_causal_authorization",
        "fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "exact_counterfactual_causal_authorization_fingerprint",
    ),
    (
        "g16_counterfactual_curve_authorization",
        "fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "counterfactual_curve_authorization_fingerprint",
    ),
    (
        "g16_exact_counterfactual_causal_authorization",
        "exact_partition_replay_authorization_fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "exact_partition_replay_authorization_fingerprint",
    ),
    (
        "g16_exact_counterfactual_causal_authorization",
        "counterfactual_causal_authorization_fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "counterfactual_causal_authorization_fingerprint",
    ),
    (
        "g16_exact_counterfactual_causal_authorization",
        "exact_partition_gate_fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "exact_partition_gate_fingerprint",
    ),
    (
        "g16_exact_counterfactual_causal_authorization",
        "source_binding_fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "source_binding_fingerprint",
    ),
    (
        "g16_exact_counterfactual_causal_authorization",
        "window_contract_fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "window_contract_fingerprint",
    ),
    (
        "g16_counterfactual_curve_authorization",
        "prepared_curve_authorization_fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "prepared_curve_authorization_fingerprint",
    ),
    (
        "g16_counterfactual_curve_authorization",
        "prepared_causal_authorization_fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "prepared_causal_authorization_fingerprint",
    ),
    (
        "g16_counterfactual_curve_authorization",
        "replay_fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "replay_fingerprint",
    ),
    (
        "g16_counterfactual_curve_authorization",
        "refined_curve_fingerprint",
        "g16_exact_counterfactual_curve_authorization",
        "refined_curve_fingerprint",
    ),
    (
        "g16_exact_counterfactual_curve_authorization",
        "fingerprint",
        "g16_counterfactual_curve_lock",
        "exact_counterfactual_curve_authorization_fingerprint",
    ),
    *v11.LINK_RULES,
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V12"
    if (
        "g16_exact_counterfactual_curve_authorization" in ready_keys
        and "g16_counterfactual_curve_lock" not in ready_keys
    ):
        return "G16_EXACT_COUNTERFACTUAL_CURVE_AUTHORIZED_LOCK_INCOMPLETE"
    if (
        "g16_counterfactual_curve_authorization" in ready_keys
        and "g16_exact_counterfactual_curve_authorization" not in ready_keys
    ):
        return "G16_COUNTERFACTUAL_CURVE_COMPLETE_EXACT_CORPUS_BINDING_INCOMPLETE"
    return _V11_OVERALL_STATUS(
        [
            key
            for key in ready_keys
            if key != "g16_exact_counterfactual_curve_authorization"
        ]
    )


@contextmanager
def _v11_contract() -> Iterator[None]:
    saved = (v11.SCHEMA, v11.STAGES, v11.LINK_RULES, v11._overall_status)
    v11.SCHEMA = SCHEMA
    v11.STAGES = STAGES
    v11.LINK_RULES = LINK_RULES
    v11._overall_status = _overall_status
    try:
        yield
    finally:
        v11.SCHEMA, v11.STAGES, v11.LINK_RULES, v11._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]]
    | None = None,
) -> dict[str, Any]:
    with _v11_contract():
        report = v11.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    exact_curve_ready = "g16_exact_counterfactual_curve_authorization" in ready
    report["g16_curve_authority_bound_to_exact_replay_bytes"] = exact_curve_ready
    report["g16_curve_authority_bound_to_exact_event_windows"] = exact_curve_ready
    report["g16_curve_authority_bound_to_counterfactual_lessons"] = exact_curve_ready
    report["note"] = (
        "Readiness v12 requires the deterministic outcome-blind G16 curve itself "
        "to carry the verified replay-byte and exact common-window proof together "
        "with locked G15 counterfactual lesson lineage before the curve lock."
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
            "readiness v12 report schema or fingerprint mismatch"
        )
    with _v11_contract():
        v11.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    exact_curve_ready = "g16_exact_counterfactual_curve_authorization" in ready
    for field in (
        "g16_curve_authority_bound_to_exact_replay_bytes",
        "g16_curve_authority_bound_to_exact_event_windows",
        "g16_curve_authority_bound_to_counterfactual_lessons",
    ):
        if value.get(field) is not exact_curve_ready:
            raise HistoricalRefinementReadinessError(
                f"readiness v12 {field} summary mismatch"
            )
    if "g16_counterfactual_curve_lock" in ready and not exact_curve_ready:
        raise HistoricalRefinementReadinessError(
            "G16 curve lock may not bypass exact curve authorization"
        )
    if "g16_counterfactual_publication" in ready and not exact_curve_ready:
        raise HistoricalRefinementReadinessError(
            "G16 publication may not bypass exact curve authorization"
        )

    rows = {str(row.get("key")): row for row in value.get("stages") or []}
    if exact_curve_ready:
        row = rows.get("g16_exact_counterfactual_curve_authorization") or {}
        if row.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
            raise HistoricalRefinementReadinessError(
                "exact curve summary claims readiness while stage is not ready"
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
                f"readiness v12 must keep {field}=false"
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
    values = v11._linked_fixture_chain()
    exact = values["g16_exact_counterfactual_causal_authorization"]
    curve = values["g16_counterfactual_curve_authorization"]
    exact_curve: dict[str, Any] = {
        "schema": _G16_EXACT_COUNTERFACTUAL_CURVE.schema,
        "status": "G16_EXACT_COUNTERFACTUAL_CURVE_AUTHORIZED",
        "exact_counterfactual_causal_authorization_fingerprint": exact["fingerprint"],
        "counterfactual_curve_authorization_fingerprint": curve["fingerprint"],
        "exact_partition_replay_authorization_fingerprint": exact[
            "exact_partition_replay_authorization_fingerprint"
        ],
        "counterfactual_causal_authorization_fingerprint": exact[
            "counterfactual_causal_authorization_fingerprint"
        ],
        "exact_partition_gate_fingerprint": exact[
            "exact_partition_gate_fingerprint"
        ],
        "source_binding_fingerprint": exact["source_binding_fingerprint"],
        "window_contract_fingerprint": exact["window_contract_fingerprint"],
        "prepared_curve_authorization_fingerprint": curve[
            "prepared_curve_authorization_fingerprint"
        ],
        "prepared_causal_authorization_fingerprint": curve[
            "prepared_causal_authorization_fingerprint"
        ],
        "replay_fingerprint": curve["replay_fingerprint"],
        "refined_curve_fingerprint": curve["refined_curve_fingerprint"],
        "candidate_count": curve["candidate_count"],
        "bound_replay_source_count": 22,
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
    }
    exact_curve["fingerprint"] = _fingerprint(exact_curve)
    values["g16_exact_counterfactual_curve_authorization"] = exact_curve

    lock = values.get("g16_counterfactual_curve_lock")
    if isinstance(lock, dict):
        lock["exact_counterfactual_curve_authorization_fingerprint"] = exact_curve[
            "fingerprint"
        ]
        fingerprint_field = next(
            spec.fingerprint_field
            for spec in STAGES
            if spec.key == "g16_counterfactual_curve_lock"
        )
        lock.pop(fingerprint_field, None)
        lock[fingerprint_field] = _fingerprint(lock)
        publication = values.get("g16_counterfactual_publication")
        if isinstance(publication, dict):
            publication["counterfactual_curve_lock_fingerprint"] = lock[
                fingerprint_field
            ]
            publication_field = next(
                spec.fingerprint_field
                for spec in STAGES
                if spec.key == "g16_counterfactual_publication"
            )
            publication.pop(publication_field, None)
            publication[publication_field] = _fingerprint(publication)
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
            == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V12"
        )
        assert complete["g16_curve_authority_bound_to_exact_replay_bytes"] is True
        assert complete["g16_curve_authority_bound_to_exact_event_windows"] is True
        assert complete["g16_curve_authority_bound_to_counterfactual_lessons"] is True

        (root / _G16_EXACT_COUNTERFACTUAL_CURVE.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert (
            blocked["first_blocking_stage"]
            == "g16_exact_counterfactual_curve_authorization"
        )
        lock = next(
            row for row in blocked["stages"] if row["key"] == "g16_counterfactual_curve_lock"
        )
        assert lock["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v12] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("renders/ng_refine_s95"),
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = build_readiness_report(args.artifact_dir)
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v12.json"
    _atomic_json(output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "first_blocking_stage": report["first_blocking_stage"],
                "ready_stage_count": len(report["ready_stages"]),
                "total_stage_count": len(STAGES),
                "out": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
