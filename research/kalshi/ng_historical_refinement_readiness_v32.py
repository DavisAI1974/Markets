#!/usr/bin/env python3
"""Canonical readiness v32 requiring exact G15 attribution authorization.

Readiness v31 verifies the exact normalized inputs that enter G15 causal replay. V32
additionally requires the deterministic six-factor counterfactual attribution to be
recursively authorized against exact replay and exact refinement before any G15
publication/scoring stage may open fixed outcomes.
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
import ng_historical_refinement_readiness_v31 as v31

SCHEMA = "ng_historical_refinement_readiness.v32"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V31_OVERALL_STATUS = v31._overall_status

_ATTRIBUTION_AUTHORIZATION = StageSpec(
    "g15_counterfactual_attribution_authorization",
    "g15_counterfactual_attribution_authorization.json",
    "ng_g15_counterfactual_attribution_authorization.v1",
    "authorization_fingerprint",
    frozenset(
        {
            "G15_COUNTERFACTUAL_ATTRIBUTION_AUTHORIZED",
            "G15_COUNTERFACTUAL_ATTRIBUTION_AUTHORIZED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g15_counterfactual_attribution_gate",
    ("validate_authorization",),
    (
        "Recursively bind exact G15 replay, deterministic refinement, and all six "
        "outcome-blind factor effects before locking/scoring the refined forecast."
    ),
    required_fields=(
        "exact_replay_completion_fingerprint",
        "pipeline_fingerprint",
        "refinement_authorization_fingerprint",
        "attribution_fingerprint",
        "replay_fingerprint",
        "anchor_fingerprint",
        "refine_stream_fingerprint",
        "n_states",
        "n_days",
        "factors",
        "factor_summary_fingerprint",
        "per_day_fingerprint",
        "rows_fingerprint",
        "lesson_proposals_fingerprint",
        "all_six_factors_quantified",
        "lesson_proposals_brain_write_forbidden",
        "next_permitted_stage",
    ),
    pre_outcome=True,
)

_STAGE_KEYS = [spec.key for spec in v31.STAGES]
_ATTRIBUTION_INDEX = _STAGE_KEYS.index("g15_counterfactual_attribution")
STAGES = (
    *v31.STAGES[: _ATTRIBUTION_INDEX + 1],
    _ATTRIBUTION_AUTHORIZATION,
    *v31.STAGES[_ATTRIBUTION_INDEX + 1 :],
)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v31.LINK_RULES,
    (
        "g15_exact_replay",
        "completion_fingerprint",
        "g15_counterfactual_attribution_authorization",
        "exact_replay_completion_fingerprint",
    ),
    (
        "g15_exact_refinement",
        "pipeline_fingerprint",
        "g15_counterfactual_attribution_authorization",
        "pipeline_fingerprint",
    ),
    (
        "g15_exact_refinement",
        "authorization_fingerprint",
        "g15_counterfactual_attribution_authorization",
        "refinement_authorization_fingerprint",
    ),
    (
        "g15_counterfactual_attribution",
        "fingerprint",
        "g15_counterfactual_attribution_authorization",
        "attribution_fingerprint",
    ),
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _without_authorization(keys: Sequence[str]) -> list[str]:
    return [key for key in keys if key != "g15_counterfactual_attribution_authorization"]


def _overall_status(ready_keys: list[str]) -> str:
    if len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V32"
    if "g15_counterfactual_attribution" not in ready_keys:
        return _V31_OVERALL_STATUS(_without_authorization(ready_keys))
    if "g15_counterfactual_attribution_authorization" not in ready_keys:
        return "G15_COUNTERFACTUAL_ATTRIBUTION_READY_AUTHORIZATION_INCOMPLETE"
    if "g15_publication" not in ready_keys:
        return "G15_COUNTERFACTUAL_ATTRIBUTION_AUTHORIZED_PUBLICATION_INCOMPLETE"
    return _V31_OVERALL_STATUS(_without_authorization(ready_keys))


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
    authorized = "g15_counterfactual_attribution_authorization" in ready_set
    publication = "g15_publication" in ready_set
    return {
        **v31._summary_fields(_without_authorization(ready)),
        "g15_counterfactual_attribution_authorization_artifact": _ATTRIBUTION_AUTHORIZATION.filename,
        "g15_counterfactual_attribution_authorization_schema": _ATTRIBUTION_AUTHORIZATION.schema,
        "g15_exact_replay_recursively_bound_to_attribution": authorized,
        "g15_exact_refinement_recursively_bound_to_attribution": authorized,
        "g15_all_six_factors_authorized_before_scoring": authorized,
        "g15_lesson_proposals_brain_write_forbidden": True,
        "g15_publication_blocked_until_attribution_authorized": True,
        "g15_publication_bound_to_attribution_authorization": publication,
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
        "Readiness v32 requires the exact replay/refinement/attribution authorization "
        "immediately after six-factor G15 attribution and before fixed-outcome publication. "
        "Every causal state must quantify onset, signed flow, divergence/exhaustion, queue "
        "depletion/replenishment, price efficiency, and activity. Lesson proposals remain "
        "non-writing candidates and cannot update ng_brain.json."
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
            "readiness v32 report schema or fingerprint mismatch"
        )
    with _legacy_contract():
        legacy.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError("readiness v32 overall status mismatch")
    for field, expected in _summary_fields(ready).items():
        if value.get(field) != expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v32 {field} summary mismatch"
            )

    ready_set = set(ready)
    attribution = "g15_counterfactual_attribution" in ready_set
    authorization = "g15_counterfactual_attribution_authorization" in ready_set
    publication = "g15_publication" in ready_set
    if authorization and not attribution:
        raise HistoricalRefinementReadinessError(
            "G15 attribution authorization may not bypass six-factor attribution"
        )
    if publication and not authorization:
        raise HistoricalRefinementReadinessError(
            "G15 publication may not bypass exact attribution authorization"
        )
    order = list(value.get("stage_order") or [])
    attribution_index = order.index("g15_counterfactual_attribution")
    if order[attribution_index : attribution_index + 3] != [
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
        "g15_publication",
    ]:
        raise HistoricalRefinementReadinessError(
            "attribution authorization must remain directly between G15 attribution and publication"
        )
    if _ATTRIBUTION_AUTHORIZATION.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "G15 attribution authorization must remain pre-outcome"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v31._linked_fixture_chain()
    replay = values["g15_exact_replay"]
    refinement = values["g15_exact_refinement"]
    attribution = values["g15_counterfactual_attribution"]

    if not refinement.get("pipeline_fingerprint"):
        refinement["pipeline_fingerprint"] = "p" * 64
        refinement.pop("authorization_fingerprint", None)
        refinement["authorization_fingerprint"] = _fingerprint(refinement)

    authorization = legacy._fixture_artifact(
        _ATTRIBUTION_AUTHORIZATION,
        "G15_COUNTERFACTUAL_ATTRIBUTION_AUTHORIZED",
    )
    authorization.update(
        {
            "exact_replay_completion_fingerprint": replay["completion_fingerprint"],
            "pipeline_fingerprint": refinement["pipeline_fingerprint"],
            "refinement_authorization_fingerprint": refinement[
                "authorization_fingerprint"
            ],
            "attribution_fingerprint": attribution["fingerprint"],
            "replay_fingerprint": refinement.get("replay_fingerprint", "r" * 64),
            "anchor_fingerprint": refinement.get("anchor_fingerprint", "a" * 64),
            "refine_stream_fingerprint": refinement.get(
                "refine_stream_fingerprint", "s" * 64
            ),
            "n_states": 12,
            "n_days": 12,
            "factors": [
                "move_onset",
                "signed_flow",
                "divergence_exhaustion",
                "queue_depletion_replenishment",
                "price_efficiency",
                "activity",
            ],
            "factor_summary_fingerprint": "f" * 64,
            "per_day_fingerprint": "d" * 64,
            "rows_fingerprint": "w" * 64,
            "lesson_proposals_fingerprint": "l" * 64,
            "lesson_proposal_count": 1,
            "all_six_factors_quantified": True,
            "lesson_proposals_brain_write_forbidden": True,
            "blockers": [],
            "next_permitted_stage": (
                "LOCK_G15_REFINED_FORECAST_AND_SCORE_BLIND_REFINED_SEPARATELY"
            ),
            "actual_outcomes_used": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_change_blind_forecast": False,
            "may_change_blind_prior": False,
            "may_change_posterior": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "g16_authorized": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
        }
    )
    authorization.pop("authorization_fingerprint", None)
    authorization["authorization_fingerprint"] = _fingerprint(authorization)
    values["g15_counterfactual_attribution_authorization"] = authorization

    incoming: dict[str, list[tuple[str, str, str]]] = {}
    for source_key, source_path, target_key, target_path in LINK_RULES:
        incoming.setdefault(target_key, []).append((source_key, source_path, target_path))
    for spec in STAGES:
        artifact = values[spec.key]
        for source_key, source_path, target_path in incoming.get(spec.key, []):
            legacy._path_set(
                artifact,
                target_path,
                legacy._path_get(values[source_key], source_path),
            )
        artifact.pop(spec.fingerprint_field, None)
        artifact[spec.fingerprint_field] = _fingerprint(artifact)
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V32"
        assert complete["g15_all_six_factors_authorized_before_scoring"] is True

        (root / _ATTRIBUTION_AUTHORIZATION.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert (
            blocked["first_blocking_stage"]
            == "g15_counterfactual_attribution_authorization"
        )
        assert blocked["g15_publication_bound_to_attribution_authorization"] is False

    print("[ng_historical_refinement_readiness_v32] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v32.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
