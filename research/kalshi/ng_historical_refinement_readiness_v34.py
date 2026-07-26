#!/usr/bin/env python3
"""Canonical readiness v34 binding attribution-scored G15 lessons to G16.

Readiness v33 recursively binds the six-factor G15 attribution authorization to fixed-
outcome publication and separate blind/refined scorecards before lesson adjudication.
V34 additionally requires the scored lesson registry and pre-cutoff G16 SHADOW plan to
remain recursively bound to that exact attribution/publication lineage before any G16
corpus, replay, posterior, curve, scoring, or publication stage may proceed.
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
import ng_historical_refinement_readiness_v33 as v33

SCHEMA = "ng_historical_refinement_readiness.v34"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V33_OVERALL_STATUS = v33._overall_status

_ATTRIBUTION_BOUND_G16_LINEAGE = StageSpec(
    "g15_g16_attribution_bound_lineage",
    "g15_g16_attribution_bound_lineage_gate.json",
    "ng_g15_g16_attribution_bound_lineage_gate.v1",
    "fingerprint",
    frozenset(
        {
            "G15_ATTRIBUTION_BOUND_LESSONS_G16_LINEAGE_AUTHORIZED",
            "G15_ATTRIBUTION_BOUND_LESSONS_G16_LINEAGE_AUTHORIZED_WITH_STAND_DOWNS",
        }
    ),
    None,
    (),
    (
        "Recursively bind six-factor-authorized G15 publication, separate path scores, "
        "scored lesson adjudication, the G16 candidate registry, and the pre-cutoff G16 "
        "SHADOW plan before verifying or replaying the G16 corpus."
    ),
    required_fields=(
        "attribution_bound_publication_fingerprint",
        "attribution_authorization_fingerprint",
        "publication_completion_fingerprint",
        "counterfactual_attribution_fingerprint",
        "counterfactual_lesson_gate_fingerprint",
        "legacy_lineage_fingerprint",
        "blind_score_fingerprint",
        "refined_score_fingerprint",
        "comparison_fingerprint",
        "g15_adjudication_fingerprint",
        "g16_registry_fingerprint",
        "g16_plan_fingerprint",
        "candidate_count",
        "candidate_ids",
        "all_six_factors_authorized_before_scoring",
        "separate_blind_refined_scores_verified",
        "scored_lessons_bound_to_attribution_publication",
        "g16_plan_bound_to_validated_g15_lessons",
        "lesson_proposals_brain_write_forbidden",
        "next_permitted_stage",
    ),
    pre_outcome=False,
)

_STAGE_KEYS = [spec.key for spec in v33.STAGES]
_LEGACY_LINEAGE_INDEX = _STAGE_KEYS.index("g15_g16_counterfactual_lineage")
_G16_BASIS_INDEX = _STAGE_KEYS.index("g16_corpus_basis")
if _G16_BASIS_INDEX != _LEGACY_LINEAGE_INDEX + 1:
    raise HistoricalRefinementReadinessError(
        "readiness v33 G15-G16 lineage must directly precede G16 corpus basis"
    )
_LEGACY_LINEAGE_FIXED_OUTCOME = replace(
    v33.STAGES[_LEGACY_LINEAGE_INDEX], pre_outcome=False
)
STAGES = (
    *v33.STAGES[:_LEGACY_LINEAGE_INDEX],
    _LEGACY_LINEAGE_FIXED_OUTCOME,
    _ATTRIBUTION_BOUND_G16_LINEAGE,
    *v33.STAGES[_LEGACY_LINEAGE_INDEX + 1 :],
)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v33.LINK_RULES,
    (
        "g15_attribution_bound_publication",
        "fingerprint",
        "g15_g16_attribution_bound_lineage",
        "attribution_bound_publication_fingerprint",
    ),
    (
        "g15_counterfactual_attribution_authorization",
        "authorization_fingerprint",
        "g15_g16_attribution_bound_lineage",
        "attribution_authorization_fingerprint",
    ),
    (
        "g15_publication",
        "completion_fingerprint",
        "g15_g16_attribution_bound_lineage",
        "publication_completion_fingerprint",
    ),
    (
        "g15_counterfactual_attribution",
        "fingerprint",
        "g15_g16_attribution_bound_lineage",
        "counterfactual_attribution_fingerprint",
    ),
    (
        "g15_counterfactual_lesson_gate",
        "fingerprint",
        "g15_g16_attribution_bound_lineage",
        "counterfactual_lesson_gate_fingerprint",
    ),
    (
        "g15_g16_counterfactual_lineage",
        "fingerprint",
        "g15_g16_attribution_bound_lineage",
        "legacy_lineage_fingerprint",
    ),
    (
        "g15_attribution_bound_publication",
        "blind_score_fingerprint",
        "g15_g16_attribution_bound_lineage",
        "blind_score_fingerprint",
    ),
    (
        "g15_attribution_bound_publication",
        "refined_score_fingerprint",
        "g15_g16_attribution_bound_lineage",
        "refined_score_fingerprint",
    ),
    (
        "g15_attribution_bound_publication",
        "comparison_fingerprint",
        "g15_g16_attribution_bound_lineage",
        "comparison_fingerprint",
    ),
    (
        "g15_g16_counterfactual_lineage",
        "g15_adjudication_fingerprint",
        "g15_g16_attribution_bound_lineage",
        "g15_adjudication_fingerprint",
    ),
    (
        "g15_g16_counterfactual_lineage",
        "g16_registry_fingerprint",
        "g15_g16_attribution_bound_lineage",
        "g16_registry_fingerprint",
    ),
    (
        "g15_g16_counterfactual_lineage",
        "g16_plan_fingerprint",
        "g15_g16_attribution_bound_lineage",
        "g16_plan_fingerprint",
    ),
    (
        "g15_g16_counterfactual_lineage",
        "candidate_count",
        "g15_g16_attribution_bound_lineage",
        "candidate_count",
    ),
    (
        "g15_g16_counterfactual_lineage",
        "candidate_ids",
        "g15_g16_attribution_bound_lineage",
        "candidate_ids",
    ),
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _without_attribution_bound_lineage(keys: Sequence[str]) -> list[str]:
    return [key for key in keys if key != "g15_g16_attribution_bound_lineage"]


def _overall_status(ready_keys: list[str]) -> str:
    if len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V34"
    if "g15_g16_counterfactual_lineage" not in ready_keys:
        return _V33_OVERALL_STATUS(_without_attribution_bound_lineage(ready_keys))
    if "g15_g16_attribution_bound_lineage" not in ready_keys:
        return "G15_G16_LEGACY_LINEAGE_READY_ATTRIBUTION_BOUND_LINEAGE_INCOMPLETE"
    if "g16_corpus_basis" not in ready_keys:
        return "G15_ATTRIBUTION_BOUND_LESSONS_G16_LINEAGE_READY_CORPUS_BASIS_INCOMPLETE"
    return _V33_OVERALL_STATUS(_without_attribution_bound_lineage(ready_keys))


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
    legacy_lineage = "g15_g16_counterfactual_lineage" in ready_set
    bound_lineage = "g15_g16_attribution_bound_lineage" in ready_set
    corpus_basis = "g16_corpus_basis" in ready_set
    return {
        **v33._summary_fields(_without_attribution_bound_lineage(ready)),
        "g15_g16_attribution_bound_lineage_artifact": (
            _ATTRIBUTION_BOUND_G16_LINEAGE.filename
        ),
        "g15_g16_attribution_bound_lineage_schema": (
            _ATTRIBUTION_BOUND_G16_LINEAGE.schema
        ),
        "g15_g16_legacy_lineage_fixed_outcome_only": True,
        "g15_scored_lessons_recursively_bound_to_g16_plan": bound_lineage,
        "g16_plan_bound_to_attribution_scored_g15_lessons": bound_lineage,
        "g16_outcomes_unavailable_during_lesson_lineage": True,
        "g16_corpus_basis_blocked_until_attribution_bound_lineage": True,
        "g16_corpus_basis_opened_after_attribution_bound_lineage": corpus_basis,
        "g15_g16_legacy_lineage_ready": legacy_lineage,
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
        "Readiness v34 requires the fixed-outcome G15 lesson gate and legacy G15-G16 "
        "lineage to be recursively rebound to the exact six-factor authorization, "
        "attribution-bound publication, separate blind/refined scores, G16 registry, "
        "and pre-cutoff G16 SHADOW plan before G16 corpus verification or replay. G16 "
        "outcomes remain unavailable and ng_brain.json writes remain forbidden."
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
            "readiness v34 report schema or fingerprint mismatch"
        )
    with _legacy_contract():
        legacy.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError(
            "readiness v34 overall status mismatch"
        )
    for field, expected in _summary_fields(ready).items():
        if value.get(field) != expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v34 {field} summary mismatch"
            )

    ready_set = set(ready)
    legacy_lineage = "g15_g16_counterfactual_lineage" in ready_set
    bound_lineage = "g15_g16_attribution_bound_lineage" in ready_set
    corpus_basis = "g16_corpus_basis" in ready_set
    if bound_lineage and not legacy_lineage:
        raise HistoricalRefinementReadinessError(
            "attribution-bound G15-G16 lineage may not bypass legacy lineage"
        )
    if corpus_basis and not bound_lineage:
        raise HistoricalRefinementReadinessError(
            "G16 corpus basis may not bypass attribution-bound G15 lesson lineage"
        )

    order = list(value.get("stage_order") or [])
    lineage_index = order.index("g15_g16_counterfactual_lineage")
    if order[lineage_index : lineage_index + 3] != [
        "g15_g16_counterfactual_lineage",
        "g15_g16_attribution_bound_lineage",
        "g16_corpus_basis",
    ]:
        raise HistoricalRefinementReadinessError(
            "attribution-bound G15-G16 lineage must remain between legacy lineage and G16 corpus basis"
        )

    legacy_spec = next(
        spec for spec in STAGES if spec.key == "g15_g16_counterfactual_lineage"
    )
    if legacy_spec.pre_outcome is not False:
        raise HistoricalRefinementReadinessError(
            "legacy G15-G16 scored lineage must remain behind the fixed G15 outcome boundary"
        )
    if _ATTRIBUTION_BOUND_G16_LINEAGE.pre_outcome is not False:
        raise HistoricalRefinementReadinessError(
            "attribution-bound G15-G16 lineage must remain behind the fixed G15 outcome boundary"
        )
    basis_spec = next(spec for spec in STAGES if spec.key == "g16_corpus_basis")
    if basis_spec.pre_outcome is not True:
        raise HistoricalRefinementReadinessError(
            "G16 corpus-basis verification itself must remain outcome-blind"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v33._linked_fixture_chain()
    bound = values["g15_attribution_bound_publication"]
    authorization = values["g15_counterfactual_attribution_authorization"]
    publication = values["g15_publication"]
    attribution = values["g15_counterfactual_attribution"]
    lesson = values["g15_counterfactual_lesson_gate"]
    lineage = values["g15_g16_counterfactual_lineage"]

    candidate_ids = list(lineage.get("candidate_ids") or ["g15_counterfactual.activity"])
    lineage.setdefault("candidate_count", len(candidate_ids))
    lineage.setdefault("candidate_ids", candidate_ids)
    lineage.setdefault("g15_adjudication_fingerprint", "j" * 64)
    lineage.setdefault("g16_registry_fingerprint", "g" * 64)
    lineage.setdefault("g16_plan_fingerprint", "q" * 64)
    lineage.pop("fingerprint", None)
    lineage["fingerprint"] = _fingerprint(lineage)

    gate = legacy._fixture_artifact(
        _ATTRIBUTION_BOUND_G16_LINEAGE,
        "G15_ATTRIBUTION_BOUND_LESSONS_G16_LINEAGE_AUTHORIZED",
    )
    gate.update(
        {
            "attribution_bound_publication_fingerprint": bound["fingerprint"],
            "attribution_authorization_fingerprint": authorization[
                "authorization_fingerprint"
            ],
            "publication_completion_fingerprint": publication[
                "completion_fingerprint"
            ],
            "counterfactual_attribution_fingerprint": attribution["fingerprint"],
            "counterfactual_lesson_gate_fingerprint": lesson["fingerprint"],
            "legacy_lineage_fingerprint": lineage["fingerprint"],
            "blind_score_fingerprint": bound["blind_score_fingerprint"],
            "refined_score_fingerprint": bound["refined_score_fingerprint"],
            "comparison_fingerprint": bound["comparison_fingerprint"],
            "g15_adjudication_fingerprint": lineage[
                "g15_adjudication_fingerprint"
            ],
            "g16_registry_fingerprint": lineage["g16_registry_fingerprint"],
            "g16_plan_fingerprint": lineage["g16_plan_fingerprint"],
            "candidate_count": lineage["candidate_count"],
            "candidate_ids": copy.deepcopy(lineage["candidate_ids"]),
            "candidate_evidence_fingerprints": copy.deepcopy(
                lineage.get("candidate_evidence_fingerprints") or {}
            ),
            "stand_down_days": [],
            "all_six_factors_authorized_before_scoring": True,
            "separate_blind_refined_scores_verified": True,
            "scored_lessons_bound_to_attribution_publication": True,
            "g16_plan_bound_to_validated_g15_lessons": True,
            "lesson_proposals_brain_write_forbidden": True,
            "actual_g15_outcomes_used": True,
            "actual_g16_outcomes_used": False,
            "g16_scoring_authorized": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_change_g16_blind_prior": False,
            "may_change_posterior": False,
            "may_select_lessons_from_g16_outcomes": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "g16_outcome_access_authorized": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "next_permitted_stage": (
                "VERIFY_G16_MATCHED_CORPUS_AND_RUN_PRE_CUTOFF_CAUSAL_REPLAY"
            ),
        }
    )
    gate.pop("fingerprint", None)
    gate["fingerprint"] = _fingerprint(gate)
    values["g15_g16_attribution_bound_lineage"] = gate

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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V34"
        assert complete["g15_scored_lessons_recursively_bound_to_g16_plan"] is True
        assert complete["g16_outcomes_unavailable_during_lesson_lineage"] is True

        (root / _ATTRIBUTION_BOUND_G16_LINEAGE.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "g15_g16_attribution_bound_lineage"
        assert blocked["status"] == (
            "G15_G16_LEGACY_LINEAGE_READY_ATTRIBUTION_BOUND_LINEAGE_INCOMPLETE"
        )
    print("[ng_historical_refinement_readiness_v34] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v34.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
