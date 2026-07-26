#!/usr/bin/env python3
"""Readiness v38: bind fixed G16 scoring to the attribution-bound immutable curve lock."""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_historical_refinement_readiness as legacy
import ng_historical_refinement_readiness_v37 as v37

SCHEMA = "ng_historical_refinement_readiness.v38"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V37_STATUS = v37._overall_status

_ATTRIBUTION_BOUND_PUBLICATION = StageSpec(
    "g16_attribution_bound_publication",
    "g16_attribution_bound_publication_gate.json",
    "ng_g16_attribution_bound_publication_gate.v1",
    "fingerprint",
    frozenset(
        {
            "G16_ATTRIBUTION_BOUND_PUBLICATION_COMPLETE",
            "G16_ATTRIBUTION_BOUND_PUBLICATION_COMPLETE_WITH_STAND_DOWNS",
        }
    ),
    "ng_g16_attribution_bound_publication_gate",
    ("validate_gate",),
    (
        "Recursively bind the fixed G16 blind/refined scorecards and chronological "
        "publication to the attribution-scored G15 lesson lineage."
    ),
    required_fields=(
        "attribution_bound_curve_lock_fingerprint",
        "counterfactual_publication_fingerprint",
        "counterfactual_curve_lock_fingerprint",
        "attribution_bound_curve_authorization_fingerprint",
        "attribution_bound_causal_authorization_fingerprint",
        "attribution_bound_lineage_fingerprint",
        "attribution_bound_publication_fingerprint",
        "attribution_authorization_fingerprint",
        "counterfactual_attribution_fingerprint",
        "g15_blind_score_fingerprint",
        "g15_refined_score_fingerprint",
        "g15_comparison_fingerprint",
        "g15_adjudication_fingerprint",
        "g16_registry_fingerprint",
        "g16_plan_fingerprint",
        "prepared_causal_authorization_fingerprint",
        "prepared_curve_authorization_fingerprint",
        "prepared_curve_lock_fingerprint",
        "replay_fingerprint",
        "manifest_fingerprint",
        "prepared_corpus_fingerprint",
        "blind_prior_fingerprint",
        "authorization_stream_fingerprint",
        "posterior_stream_fingerprint",
        "refined_curve_fingerprint",
        "blind_forecast_sha256",
        "refined_forecast_sha256",
        "actual_sha256",
        "blind_score_fingerprint",
        "refined_score_fingerprint",
        "comparison_fingerprint",
        "chronological_validation_fingerprint",
        "candidate_count",
        "candidate_ids",
        "candidate_evidence_fingerprints",
        "candidate_ids_used_by_curve",
        "all_six_factors_authorized_before_g16_scoring",
        "separate_g15_blind_refined_scores_verified",
        "separate_g16_blind_refined_scores_verified",
        "g16_publication_bound_to_attribution_scored_g15_lessons",
        "g16_curve_locked_before_fixed_scoring",
        "g16_chronological_forward_holdout_scored",
        "lesson_proposals_brain_write_forbidden",
        "outcome_scoring_complete",
        "next_permitted_stage",
    ),
    pre_outcome=False,
)

_KEYS = [spec.key for spec in v37.STAGES]
_PUBLICATION_INDEX = _KEYS.index("g16_counterfactual_publication")
if _PUBLICATION_INDEX != len(v37.STAGES) - 1:
    raise HistoricalRefinementReadinessError(
        "readiness v37 G16 counterfactual publication must be the final stage"
    )
STAGES = (*v37.STAGES, _ATTRIBUTION_BOUND_PUBLICATION)

LINK_RULES = (
    *v37.LINK_RULES,
    (
        "g16_attribution_bound_curve_lock",
        "fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "attribution_bound_curve_lock_fingerprint",
    ),
    (
        "g16_counterfactual_publication",
        "completion_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "counterfactual_publication_fingerprint",
    ),
    (
        "g16_counterfactual_publication",
        "blind_score_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "blind_score_fingerprint",
    ),
    (
        "g16_counterfactual_publication",
        "refined_score_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "refined_score_fingerprint",
    ),
    (
        "g16_counterfactual_publication",
        "comparison_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "comparison_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_lock",
        "attribution_bound_curve_authorization_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "attribution_bound_curve_authorization_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_lock",
        "attribution_bound_causal_authorization_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "attribution_bound_causal_authorization_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_lock",
        "attribution_bound_lineage_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "attribution_bound_lineage_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_lock",
        "g15_adjudication_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "g15_adjudication_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_lock",
        "g16_registry_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "g16_registry_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_lock",
        "g16_plan_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "g16_plan_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_lock",
        "refined_curve_fingerprint",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
        "refined_curve_fingerprint",
    ),
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _without_bound_publication(keys: Sequence[str]) -> list[str]:
    return [key for key in keys if key != _ATTRIBUTION_BOUND_PUBLICATION.key]


def _overall_status(ready: list[str]) -> str:
    if len(ready) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V38"
    if "g16_counterfactual_publication" not in ready:
        return _V37_STATUS(_without_bound_publication(ready))
    if _ATTRIBUTION_BOUND_PUBLICATION.key not in ready:
        return "G16_COUNTERFACTUAL_PUBLICATION_READY_ATTRIBUTION_BINDING_INCOMPLETE"
    return _V37_STATUS(_without_bound_publication(ready))


@contextmanager
def _contract() -> Iterator[None]:
    saved = (legacy.SCHEMA, legacy.STAGES, legacy.LINK_RULES)
    legacy.SCHEMA, legacy.STAGES, legacy.LINK_RULES = SCHEMA, STAGES, LINK_RULES
    try:
        yield
    finally:
        legacy.SCHEMA, legacy.STAGES, legacy.LINK_RULES = saved


def _summary_fields(ready: Sequence[str]) -> dict[str, Any]:
    ready_set = set(ready)
    return {
        **v37._summary_fields(_without_bound_publication(ready)),
        "g16_attribution_bound_publication_artifact": _ATTRIBUTION_BOUND_PUBLICATION.filename,
        "g16_attribution_bound_publication_schema": _ATTRIBUTION_BOUND_PUBLICATION.schema,
        "g16_scoring_bound_to_attribution_scored_g15_lessons": (
            _ATTRIBUTION_BOUND_PUBLICATION.key in ready_set
        ),
        "g16_blind_refined_scores_remain_separate": True,
        "g16_publication_cannot_rewrite_ng_brain": True,
    }


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _contract():
        report = legacy.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    report["status"] = _overall_status(ready)
    report.update(_summary_fields(ready))
    report["note"] = (
        "Fixed G16 scoring is accepted only after the exact blind/refined scorecards and "
        "chronological publication are recursively bound to the attribution-scored G15 "
        "lesson lineage. Blind forecasts, ng_brain.json, SHADOW mode, tastytrade, and the "
        "no-options boundary remain unchanged."
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
            "readiness v38 schema or fingerprint mismatch"
        )
    with _contract():
        legacy.validate_readiness_report(value)
    ready = list(value.get("ready_stages") or [])
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError("readiness v38 status mismatch")
    for field, expected in _summary_fields(ready).items():
        if value.get(field) != expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v38 {field} mismatch"
            )

    order = list(value.get("stage_order") or [])
    if order[-4:] != [
        "g16_counterfactual_curve_lock",
        "g16_attribution_bound_curve_lock",
        "g16_counterfactual_publication",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
    ]:
        raise HistoricalRefinementReadinessError(
            "attribution-bound publication must directly follow the G16 lock/publication chain"
        )
    by_key = {spec.key: spec for spec in STAGES}
    for key in (
        "g16_attribution_bound_curve_lock",
        "g16_counterfactual_publication",
        _ATTRIBUTION_BOUND_PUBLICATION.key,
    ):
        if by_key[key].pre_outcome is not False:
            raise HistoricalRefinementReadinessError(
                f"{key} must remain behind the fixed G15 outcome boundary"
            )
    ready_set = set(ready)
    if _ATTRIBUTION_BOUND_PUBLICATION.key in ready_set and not {
        "g16_attribution_bound_curve_lock",
        "g16_counterfactual_publication",
    }.issubset(ready_set):
        raise HistoricalRefinementReadinessError(
            "attribution-bound G16 publication bypassed lock or scored publication"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v37._linked_fixture_chain()
    bound = values["g16_attribution_bound_curve_lock"]
    publication = values["g16_counterfactual_publication"]
    gate = legacy._fixture_artifact(
        _ATTRIBUTION_BOUND_PUBLICATION,
        "G16_ATTRIBUTION_BOUND_PUBLICATION_COMPLETE",
    )
    gate.update(
        {
            "attribution_bound_curve_lock_fingerprint": bound["fingerprint"],
            "counterfactual_publication_fingerprint": publication[
                "completion_fingerprint"
            ],
            "counterfactual_curve_lock_fingerprint": bound[
                "counterfactual_curve_lock_fingerprint"
            ],
            "attribution_bound_curve_authorization_fingerprint": bound[
                "attribution_bound_curve_authorization_fingerprint"
            ],
            "attribution_bound_causal_authorization_fingerprint": bound[
                "attribution_bound_causal_authorization_fingerprint"
            ],
            "attribution_bound_lineage_fingerprint": bound[
                "attribution_bound_lineage_fingerprint"
            ],
            "attribution_bound_publication_fingerprint": bound[
                "attribution_bound_publication_fingerprint"
            ],
            "attribution_authorization_fingerprint": bound[
                "attribution_authorization_fingerprint"
            ],
            "counterfactual_attribution_fingerprint": bound[
                "counterfactual_attribution_fingerprint"
            ],
            "g15_blind_score_fingerprint": bound["blind_score_fingerprint"],
            "g15_refined_score_fingerprint": bound["refined_score_fingerprint"],
            "g15_comparison_fingerprint": bound["comparison_fingerprint"],
            "g15_adjudication_fingerprint": bound["g15_adjudication_fingerprint"],
            "g16_registry_fingerprint": bound["g16_registry_fingerprint"],
            "g16_plan_fingerprint": bound["g16_plan_fingerprint"],
            "prepared_causal_authorization_fingerprint": bound[
                "prepared_causal_authorization_fingerprint"
            ],
            "prepared_curve_authorization_fingerprint": bound[
                "prepared_curve_authorization_fingerprint"
            ],
            "prepared_curve_lock_fingerprint": bound["prepared_curve_lock_fingerprint"],
            "replay_fingerprint": bound["replay_fingerprint"],
            "manifest_fingerprint": bound["manifest_fingerprint"],
            "prepared_corpus_fingerprint": bound["prepared_corpus_fingerprint"],
            "blind_prior_fingerprint": bound["blind_prior_fingerprint"],
            "authorization_stream_fingerprint": bound[
                "authorization_stream_fingerprint"
            ],
            "posterior_stream_fingerprint": bound["posterior_stream_fingerprint"],
            "refined_curve_fingerprint": bound["refined_curve_fingerprint"],
            "blind_forecast_sha256": publication["blind_forecast_sha256"],
            "refined_forecast_sha256": publication["refined_forecast_sha256"],
            "actual_sha256": publication["actual_sha256"],
            "blind_score_fingerprint": publication["blind_score_fingerprint"],
            "refined_score_fingerprint": publication["refined_score_fingerprint"],
            "comparison_fingerprint": publication["comparison_fingerprint"],
            "chronological_validation_fingerprint": publication[
                "chronological_validation_fingerprint"
            ],
            "candidate_count": bound["candidate_count"],
            "candidate_ids": copy.deepcopy(bound["candidate_ids"]),
            "candidate_evidence_fingerprints": copy.deepcopy(
                bound["candidate_evidence_fingerprints"]
            ),
            "candidate_ids_used_by_curve": copy.deepcopy(
                bound["candidate_ids_used_by_curve"]
            ),
            "all_six_factors_authorized_before_g16_scoring": True,
            "separate_g15_blind_refined_scores_verified": True,
            "separate_g16_blind_refined_scores_verified": True,
            "g16_publication_bound_to_attribution_scored_g15_lessons": True,
            "g16_curve_locked_before_fixed_scoring": True,
            "g16_chronological_forward_holdout_scored": True,
            "lesson_proposals_brain_write_forbidden": True,
            "actual_g15_outcomes_used": True,
            "actual_g16_outcomes_used": True,
            "outcome_scoring_complete": True,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "next_permitted_stage": (
                "REVIEW_G16_FIXED_OUTCOME_PUBLICATION_WITHOUT_BRAIN_WRITE"
            ),
        }
    )
    gate.pop("fingerprint", None)
    gate["fingerprint"] = _fingerprint(gate)
    values[_ATTRIBUTION_BOUND_PUBLICATION.key] = gate
    return values


def _fixture_validator(value: Mapping[str, Any]) -> None:
    if not value:
        raise HistoricalRefinementReadinessError("fixture artifact missing")


def _selftest() -> None:
    import tempfile

    values = _linked_fixture_chain()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        paths: dict[str, Path] = {}
        validators: dict[str, Callable[[Mapping[str, Any]], Any]] = {}
        for spec in STAGES:
            path = root / spec.filename
            _atomic_json(path, values[spec.key])
            paths[spec.key] = path
            validators[spec.key] = _fixture_validator
        report = build_readiness_report(
            root,
            stage_paths=paths,
            validator_overrides=validators,
        )
        assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V38"
        assert report["g16_scoring_bound_to_attribution_scored_g15_lessons"] is True

        missing = dict(paths)
        missing.pop(_ATTRIBUTION_BOUND_PUBLICATION.key)
        partial = build_readiness_report(
            root,
            stage_paths=missing,
            validator_overrides=validators,
        )
        assert partial["status"] == (
            "G16_COUNTERFACTUAL_PUBLICATION_READY_ATTRIBUTION_BINDING_INCOMPLETE"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        print(json.dumps({"status": "SELFTEST_PASS", "schema": SCHEMA}, sort_keys=True))
        return 0
    report = build_readiness_report(args.artifact_dir)
    if args.out:
        _atomic_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
