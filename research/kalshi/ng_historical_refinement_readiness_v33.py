#!/usr/bin/env python3
"""Canonical readiness v33 requiring attribution-bound G15 publication.

Readiness v32 authorizes the exact six-factor G15 attribution before fixed outcomes may
open. V33 additionally requires a recursive post-publication gate proving that the exact
publication completion, separate blind/refined scorecards, and their comparison descend
from that authorization before lesson adjudication or any G16 lineage may proceed.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_historical_refinement_readiness as legacy
import ng_historical_refinement_readiness_v32 as v32

SCHEMA = "ng_historical_refinement_readiness.v33"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V32_OVERALL_STATUS = v32._overall_status

_ATTRIBUTION_BOUND_PUBLICATION = StageSpec(
    "g15_attribution_bound_publication",
    "g15_attribution_bound_publication_gate.json",
    "ng_g15_attribution_bound_publication_gate.v1",
    "fingerprint",
    frozenset(
        {
            "G15_ATTRIBUTION_BOUND_PUBLICATION_VERIFIED",
            "G15_ATTRIBUTION_BOUND_PUBLICATION_VERIFIED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g15_attribution_bound_publication_gate",
    ("validate_gate",),
    (
        "Recursively bind attribution authorization to fixed-outcome G15 publication "
        "and verify separate blind/refined score artifacts before lesson adjudication."
    ),
    required_fields=(
        "attribution_authorization_fingerprint",
        "publication_completion_fingerprint",
        "exact_replay_completion_fingerprint",
        "exact_refinement_authorization_fingerprint",
        "attribution_fingerprint",
        "refine_stream_fingerprint",
        "blind_score_fingerprint",
        "refined_score_fingerprint",
        "comparison_fingerprint",
        "actual_artifact_fingerprint",
        "n_days",
        "factors",
        "attribution_authorization_bound_to_publication",
        "publication_opened_after_attribution_authorization",
        "separate_blind_refined_scores_verified",
        "all_six_factors_authorized_before_scoring",
        "lesson_proposals_brain_write_forbidden",
        "next_permitted_stage",
    ),
    pre_outcome=False,
)

_STAGE_KEYS = [spec.key for spec in v32.STAGES]
_PUBLICATION_INDEX = _STAGE_KEYS.index("g15_publication")
_LESSON_INDEX = _STAGE_KEYS.index("g15_counterfactual_lesson_gate")
_LESSON_FIXED_OUTCOME = replace(v32.STAGES[_LESSON_INDEX], pre_outcome=False)
STAGES = (
    *v32.STAGES[: _PUBLICATION_INDEX + 1],
    _ATTRIBUTION_BOUND_PUBLICATION,
    _LESSON_FIXED_OUTCOME,
    *v32.STAGES[_LESSON_INDEX + 1 :],
)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v32.LINK_RULES,
    (
        "g15_counterfactual_attribution_authorization",
        "authorization_fingerprint",
        "g15_attribution_bound_publication",
        "attribution_authorization_fingerprint",
    ),
    (
        "g15_publication",
        "completion_fingerprint",
        "g15_attribution_bound_publication",
        "publication_completion_fingerprint",
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
    return [key for key in keys if key != "g15_attribution_bound_publication"]


def _overall_status(ready_keys: list[str]) -> str:
    if len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V33"
    if "g15_publication" not in ready_keys:
        return _V32_OVERALL_STATUS(_without_bound_publication(ready_keys))
    if "g15_attribution_bound_publication" not in ready_keys:
        return "G15_PUBLICATION_COMPLETE_ATTRIBUTION_BINDING_INCOMPLETE"
    if "g15_counterfactual_lesson_gate" not in ready_keys:
        return "G15_ATTRIBUTION_BOUND_PUBLICATION_READY_LESSON_ADJUDICATION_INCOMPLETE"
    return _V32_OVERALL_STATUS(_without_bound_publication(ready_keys))


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
    publication = "g15_publication" in ready_set
    bound = "g15_attribution_bound_publication" in ready_set
    lesson = "g15_counterfactual_lesson_gate" in ready_set
    return {
        **v32._summary_fields(_without_bound_publication(ready)),
        "g15_attribution_bound_publication_artifact": (
            _ATTRIBUTION_BOUND_PUBLICATION.filename
        ),
        "g15_attribution_bound_publication_schema": (
            _ATTRIBUTION_BOUND_PUBLICATION.schema
        ),
        "g15_attribution_authorization_bound_to_publication": bound,
        "g15_separate_blind_refined_scores_recursively_verified": bound,
        "g15_score_actual_substrate_shared": bound,
        "g15_lesson_adjudication_blocked_until_publication_binding": True,
        "g15_lesson_adjudication_fixed_outcome_only": True,
        "g15_lesson_adjudication_bound_to_verified_publication": lesson,
        "g15_publication_fixed_outcome_stage_ready": publication,
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
        "Readiness v33 requires a recursive fixed-outcome publication binding after "
        "G15 attribution authorization and publication, but before scored lesson "
        "adjudication. Blind and refined scorecards must remain separate immutable "
        "artifacts on one actual substrate; lesson proposals cannot write ng_brain.json."
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
            "readiness v33 report schema or fingerprint mismatch"
        )
    with _legacy_contract():
        legacy.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError(
            "readiness v33 overall status mismatch"
        )
    for field, expected in _summary_fields(ready).items():
        if value.get(field) != expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v33 {field} summary mismatch"
            )

    ready_set = set(ready)
    publication = "g15_publication" in ready_set
    bound = "g15_attribution_bound_publication" in ready_set
    lesson = "g15_counterfactual_lesson_gate" in ready_set
    if bound and not publication:
        raise HistoricalRefinementReadinessError(
            "attribution-bound publication may not bypass G15 publication"
        )
    if lesson and not bound:
        raise HistoricalRefinementReadinessError(
            "G15 lesson adjudication may not bypass attribution-bound publication"
        )
    order = list(value.get("stage_order") or [])
    publication_index = order.index("g15_publication")
    if order[publication_index : publication_index + 3] != [
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ]:
        raise HistoricalRefinementReadinessError(
            "attribution-bound publication must remain directly between publication and lessons"
        )
    if _ATTRIBUTION_BOUND_PUBLICATION.pre_outcome is not False:
        raise HistoricalRefinementReadinessError(
            "attribution-bound publication must remain behind the G15 outcome boundary"
        )
    lesson_spec = next(spec for spec in STAGES if spec.key == "g15_counterfactual_lesson_gate")
    if lesson_spec.pre_outcome is not False:
        raise HistoricalRefinementReadinessError(
            "G15 scored lesson adjudication must remain behind the fixed-outcome boundary"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v32._linked_fixture_chain()
    authorization = values["g15_counterfactual_attribution_authorization"]
    publication = values["g15_publication"]
    gate = legacy._fixture_artifact(
        _ATTRIBUTION_BOUND_PUBLICATION,
        "G15_ATTRIBUTION_BOUND_PUBLICATION_VERIFIED",
    )
    gate.update(
        {
            "attribution_authorization_fingerprint": authorization[
                "authorization_fingerprint"
            ],
            "publication_completion_fingerprint": publication[
                "completion_fingerprint"
            ],
            "exact_replay_completion_fingerprint": authorization[
                "exact_replay_completion_fingerprint"
            ],
            "exact_refinement_authorization_fingerprint": authorization[
                "refinement_authorization_fingerprint"
            ],
            "attribution_fingerprint": authorization["attribution_fingerprint"],
            "refine_stream_fingerprint": authorization[
                "refine_stream_fingerprint"
            ],
            "blind_forecast_sha256": "b" * 64,
            "refined_forecast_sha256": "r" * 64,
            "actual_artifact_fingerprint": "a" * 64,
            "blind_score_fingerprint": "s" * 64,
            "refined_score_fingerprint": "t" * 64,
            "comparison_fingerprint": "c" * 64,
            "n_days": 12,
            "days": [
                "20260315",
                "20260316",
                "20260317",
                "20260318",
                "20260319",
                "20260320",
                "20260322",
                "20260323",
                "20260324",
                "20260325",
                "20260326",
                "20260327",
            ],
            "factors": [
                "move_onset",
                "signed_flow",
                "divergence_exhaustion",
                "queue_depletion_replenishment",
                "price_efficiency",
                "activity",
            ],
            "stand_down_days": [],
            "attribution_authorization_bound_to_publication": True,
            "publication_opened_after_attribution_authorization": True,
            "separate_blind_refined_scores_verified": True,
            "score_artifacts_distinct": True,
            "score_actual_substrate_shared": True,
            "all_six_factors_authorized_before_scoring": True,
            "lesson_proposals_brain_write_forbidden": True,
            "blind_forecasts_immutable": True,
            "one_signal_authority_preserved": True,
            "actual_g15_outcomes_used": True,
            "actual_g16_outcomes_used": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "may_change_blind_prior": False,
            "may_change_blind_forecast": False,
            "may_change_posterior": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "g16_outcome_access_authorized": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "next_permitted_stage": (
                "ADJUDICATE_LOCKED_G15_COUNTERFACTUAL_LESSONS_FOR_G16_SHADOW"
            ),
        }
    )
    gate.pop("fingerprint", None)
    gate["fingerprint"] = _fingerprint(gate)
    values["g15_attribution_bound_publication"] = gate

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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V33"
        assert complete[
            "g15_separate_blind_refined_scores_recursively_verified"
        ] is True

        (root / _ATTRIBUTION_BOUND_PUBLICATION.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "g15_attribution_bound_publication"
        assert blocked["status"] == (
            "G15_PUBLICATION_COMPLETE_ATTRIBUTION_BINDING_INCOMPLETE"
        )
    print("[ng_historical_refinement_readiness_v33] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v33.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
