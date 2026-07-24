#!/usr/bin/env python3
"""Canonical v13 readiness with exact G16 provenance through lock and publication.

V12 requires the deterministic outcome-blind G16 curve authorization to carry
verified replay bytes, exact common L1/MBO event windows, and locked G15 lesson
lineage.  V13 replaces the legacy lock and scored-publication artifacts with
contracts that preserve that exact proof through the fixed-outcome boundary.
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
import ng_historical_refinement_readiness_v12 as v12

SCHEMA = "ng_historical_refinement_readiness.v13"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V12_OVERALL_STATUS = v12._overall_status

_G16_EXACT_LOCK = StageSpec(
    "g16_counterfactual_curve_lock",
    "g16_exact_counterfactual_curve_lock.json",
    "ng_g16_exact_counterfactual_curve_lock.v1",
    "lock_fingerprint",
    frozenset({"EXACT_G16_CORPUS_COUNTERFACTUAL_CURVE_LOCKED"}),
    None,
    (),
    "Persist the exact refined G16 curve, verified replay-byte/event-window proof, and G15 lesson lineage before opening fixed outcomes.",
    required_fields=(
        "exact_counterfactual_curve_authorization_fingerprint",
        "exact_counterfactual_causal_authorization_fingerprint",
        "counterfactual_curve_authorization_fingerprint",
        "counterfactual_causal_authorization_fingerprint",
        "exact_partition_replay_authorization_fingerprint",
        "source_binding_fingerprint",
        "window_contract_fingerprint",
        "prepared_curve_authorization_fingerprint",
        "prepared_curve_lock_fingerprint",
        "replay_fingerprint",
        "refined_curve_fingerprint",
        "candidate_count",
        "bound_replay_source_count",
        "all_g16_replay_sources_bound_to_exact_partition",
        "all_g16_state_spans_inside_exact_common_windows",
    ),
    pre_outcome=True,
)

_G16_EXACT_PUBLICATION = StageSpec(
    "g16_counterfactual_publication",
    "g16_exact_counterfactual_publication_completion.json",
    "ng_g16_exact_counterfactual_publication_completion.v1",
    "completion_fingerprint",
    frozenset(
        {
            "EXACT_G16_CORPUS_COUNTERFACTUAL_PUBLICATION_COMPLETE",
            "EXACT_G16_CORPUS_COUNTERFACTUAL_PUBLICATION_COMPLETE_WITH_STAND_DOWNS",
        }
    ),
    None,
    (),
    "Score the fixed G16 holdout and render both paths only after exact corpus provenance and G15 lesson lineage are locked.",
    required_fields=(
        "counterfactual_curve_lock_fingerprint",
        "exact_counterfactual_curve_lock_fingerprint",
        "exact_counterfactual_curve_authorization_fingerprint",
        "exact_counterfactual_causal_authorization_fingerprint",
        "counterfactual_curve_authorization_fingerprint",
        "counterfactual_causal_authorization_fingerprint",
        "exact_partition_replay_authorization_fingerprint",
        "source_binding_fingerprint",
        "window_contract_fingerprint",
        "prepared_publication_completion_fingerprint",
        "replay_fingerprint",
        "refined_curve_fingerprint",
        "candidate_count",
        "bound_replay_source_count",
        "all_g16_replay_sources_bound_to_exact_partition",
        "all_g16_state_spans_inside_exact_common_windows",
    ),
    pre_outcome=False,
)


def _replace(spec: StageSpec) -> StageSpec:
    if spec.key == "g16_counterfactual_curve_lock":
        return _G16_EXACT_LOCK
    if spec.key == "g16_counterfactual_publication":
        return _G16_EXACT_PUBLICATION
    return spec


STAGES: tuple[StageSpec, ...] = tuple(_replace(spec) for spec in v12.STAGES)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v12.LINK_RULES,
    (
        "g16_exact_counterfactual_curve_authorization",
        "fingerprint",
        "g16_counterfactual_publication",
        "exact_counterfactual_curve_authorization_fingerprint",
    ),
    (
        "g16_exact_counterfactual_causal_authorization",
        "fingerprint",
        "g16_counterfactual_publication",
        "exact_counterfactual_causal_authorization_fingerprint",
    ),
    (
        "g16_exact_counterfactual_curve_authorization",
        "exact_partition_replay_authorization_fingerprint",
        "g16_counterfactual_publication",
        "exact_partition_replay_authorization_fingerprint",
    ),
    (
        "g16_exact_counterfactual_curve_authorization",
        "source_binding_fingerprint",
        "g16_counterfactual_publication",
        "source_binding_fingerprint",
    ),
    (
        "g16_exact_counterfactual_curve_authorization",
        "window_contract_fingerprint",
        "g16_counterfactual_publication",
        "window_contract_fingerprint",
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
    if "g16_counterfactual_publication" in ready_keys and len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V13"
    if (
        "g16_counterfactual_curve_lock" in ready_keys
        and "g16_counterfactual_publication" not in ready_keys
    ):
        return "G16_EXACT_CORPUS_CURVE_LOCKED_FIXED_SCORING_INCOMPLETE"
    if (
        "g16_exact_counterfactual_curve_authorization" in ready_keys
        and "g16_counterfactual_curve_lock" not in ready_keys
    ):
        return "G16_EXACT_COUNTERFACTUAL_CURVE_AUTHORIZED_EXACT_LOCK_INCOMPLETE"
    return _V12_OVERALL_STATUS(ready_keys)


@contextmanager
def _v12_contract() -> Iterator[None]:
    saved = (v12.SCHEMA, v12.STAGES, v12.LINK_RULES, v12._overall_status)
    v12.SCHEMA = SCHEMA
    v12.STAGES = STAGES
    v12.LINK_RULES = LINK_RULES
    v12._overall_status = _overall_status
    try:
        yield
    finally:
        v12.SCHEMA, v12.STAGES, v12.LINK_RULES, v12._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]]
    | None = None,
) -> dict[str, Any]:
    with _v12_contract():
        report = v12.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    lock_ready = "g16_counterfactual_curve_lock" in ready
    publication_ready = "g16_counterfactual_publication" in ready
    report["g16_exact_corpus_provenance_locked_before_fixed_scoring"] = lock_ready
    report["g16_exact_corpus_provenance_preserved_through_publication"] = (
        publication_ready
    )
    report["g16_counterfactual_lessons_preserved_through_exact_publication"] = (
        publication_ready
    )
    report["note"] = (
        "Readiness v13 requires the pre-scoring G16 curve lock and final scored "
        "publication to preserve the v12 exact replay-byte/event-window proof and "
        "locked G15 counterfactual lesson lineage."
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
            "readiness v13 report schema or fingerprint mismatch"
        )
    with _v12_contract():
        v12.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    lock_ready = "g16_counterfactual_curve_lock" in ready
    publication_ready = "g16_counterfactual_publication" in ready
    summaries = {
        "g16_exact_corpus_provenance_locked_before_fixed_scoring": lock_ready,
        "g16_exact_corpus_provenance_preserved_through_publication": publication_ready,
        "g16_counterfactual_lessons_preserved_through_exact_publication": publication_ready,
    }
    for field, expected in summaries.items():
        if value.get(field) is not expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v13 {field} summary mismatch"
            )
    if lock_ready and "g16_exact_counterfactual_curve_authorization" not in ready:
        raise HistoricalRefinementReadinessError(
            "exact G16 curve lock may not bypass exact curve authorization"
        )
    if publication_ready and not lock_ready:
        raise HistoricalRefinementReadinessError(
            "exact G16 publication may not bypass the exact pre-scoring lock"
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
                f"readiness v13 must keep {field}=false"
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
    values = v12._linked_fixture_chain()
    exact_curve = values["g16_exact_counterfactual_curve_authorization"]
    legacy_lock = copy.deepcopy(values["g16_counterfactual_curve_lock"])
    lock = copy.deepcopy(legacy_lock)
    lock["schema"] = _G16_EXACT_LOCK.schema
    lock["status"] = "EXACT_G16_CORPUS_COUNTERFACTUAL_CURVE_LOCKED"
    lock["exact_counterfactual_curve_authorization_fingerprint"] = exact_curve[
        "fingerprint"
    ]
    lock["exact_counterfactual_causal_authorization_fingerprint"] = exact_curve[
        "exact_counterfactual_causal_authorization_fingerprint"
    ]
    lock["exact_partition_replay_authorization_fingerprint"] = exact_curve[
        "exact_partition_replay_authorization_fingerprint"
    ]
    lock["source_binding_fingerprint"] = exact_curve["source_binding_fingerprint"]
    lock["window_contract_fingerprint"] = exact_curve["window_contract_fingerprint"]
    lock["candidate_count"] = exact_curve["candidate_count"]
    lock["bound_replay_source_count"] = 22
    lock["all_g16_replay_sources_bound_to_exact_partition"] = True
    lock["all_g16_state_spans_inside_exact_common_windows"] = True
    lock.pop("lock_fingerprint", None)
    lock["lock_fingerprint"] = _fingerprint(lock)
    values["g16_counterfactual_curve_lock"] = lock

    legacy_publication = copy.deepcopy(values["g16_counterfactual_publication"])
    publication = copy.deepcopy(legacy_publication)
    publication["schema"] = _G16_EXACT_PUBLICATION.schema
    publication["status"] = "EXACT_G16_CORPUS_COUNTERFACTUAL_PUBLICATION_COMPLETE"
    publication["counterfactual_curve_lock_fingerprint"] = lock["lock_fingerprint"]
    publication["exact_counterfactual_curve_lock_fingerprint"] = lock[
        "lock_fingerprint"
    ]
    publication["exact_counterfactual_curve_authorization_fingerprint"] = exact_curve[
        "fingerprint"
    ]
    publication["exact_counterfactual_causal_authorization_fingerprint"] = exact_curve[
        "exact_counterfactual_causal_authorization_fingerprint"
    ]
    publication["exact_partition_replay_authorization_fingerprint"] = exact_curve[
        "exact_partition_replay_authorization_fingerprint"
    ]
    publication["source_binding_fingerprint"] = exact_curve[
        "source_binding_fingerprint"
    ]
    publication["window_contract_fingerprint"] = exact_curve[
        "window_contract_fingerprint"
    ]
    publication["refined_curve_fingerprint"] = exact_curve[
        "refined_curve_fingerprint"
    ]
    publication["candidate_count"] = exact_curve["candidate_count"]
    publication["bound_replay_source_count"] = 22
    publication["all_g16_replay_sources_bound_to_exact_partition"] = True
    publication["all_g16_state_spans_inside_exact_common_windows"] = True
    publication.pop("completion_fingerprint", None)
    publication["completion_fingerprint"] = _fingerprint(publication)
    values["g16_counterfactual_publication"] = publication
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V13"
        assert complete[
            "g16_exact_corpus_provenance_locked_before_fixed_scoring"
        ] is True
        assert complete[
            "g16_exact_corpus_provenance_preserved_through_publication"
        ] is True

        (root / _G16_EXACT_LOCK.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "g16_counterfactual_curve_lock"
        publication = next(
            row
            for row in blocked["stages"]
            if row["key"] == "g16_counterfactual_publication"
        )
        assert publication["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v13] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v13.json"
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
