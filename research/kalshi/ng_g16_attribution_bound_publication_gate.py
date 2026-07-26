#!/usr/bin/env python3
"""Bind attribution-scored G15 lineage through fixed G16 scoring and publication.

The attribution-bound G16 curve-lock gate proves the immutable blind/refined curve
was locked before G16 outcomes opened and descends from six-factor-authorized,
separately scored G15 lessons. The existing counterfactual publication proves fixed
G16 outcomes were scored chronologically against that legacy lock. This gate requires
both exact artifacts plus the distinct G16 blind score, refined score, and comparison
before the scored publication may be accepted.

Nothing here may rewrite a blind forecast, posterior, lesson registry, or
``ng_brain.json``. Random shuffling remains forbidden, CME event contracts remain
SHADOW, tastytrade remains the brokerage contract, and the options lane remains
unstarted.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA = "ng_g16_attribution_bound_publication_gate.v1"
BUNDLE_SCHEMA = "ng_g16_attribution_bound_publication_validation_bundle.v1"
AUTHORITY = "G15_ATTRIBUTION_BOUND_LESSONS_THROUGH_FIXED_G16_SCORED_PUBLICATION_ONLY"
READY = "G16_ATTRIBUTION_BOUND_PUBLICATION_COMPLETE"
READY_WITH_STAND_DOWNS = "G16_ATTRIBUTION_BOUND_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"
NEXT_STAGE = "REVIEW_G16_FIXED_OUTCOME_PUBLICATION_WITHOUT_BRAIN_WRITE"
BOUND_LOCK_SCHEMA = "ng_g16_attribution_bound_curve_lock_gate.v1"
PUBLICATION_SCHEMA = "ng_g16_counterfactual_publication_completion.v1"
SCORE_SCHEMA = "ng_g16_path_score.v1"
COMPARISON_SCHEMA = "ng_g16_path_comparison.v1"


class G16AttributionBoundPublicationError(ValueError):
    """Raised when fixed G16 scoring diverges from the attribution-bound curve lock."""


def _fingerprint(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_fp = _fingerprint


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G16AttributionBoundPublicationError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise G16AttributionBoundPublicationError(f"JSON artifact must be an object: {path}")
    return value


def _signed(value: Mapping[str, Any], field: str, label: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    observed = result.pop(field, None)
    if not isinstance(observed, str) or observed != _fingerprint(result):
        raise G16AttributionBoundPublicationError(f"{label} {field} mismatch")
    result[field] = observed
    return result


def _decode_bytes(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_bytes(item) for item in value]
    if not isinstance(value, Mapping):
        return copy.deepcopy(value)
    result: dict[str, Any] = {}
    for key, item in value.items():
        if str(key).endswith("_base64"):
            target = str(key)[: -len("_base64")]
            try:
                result[target] = base64.b64decode(str(item).encode("ascii"), validate=True)
            except (ValueError, UnicodeEncodeError, binascii.Error) as error:
                raise G16AttributionBoundPublicationError(
                    f"invalid base64 validation field {key}"
                ) from error
        else:
            result[str(key)] = _decode_bytes(item)
    return result


def _normalize_bundle(value: Mapping[str, Any]) -> dict[str, Any]:
    bundle = copy.deepcopy(dict(value))
    if bundle.get("schema") != BUNDLE_SCHEMA:
        raise G16AttributionBoundPublicationError("validation bundle schema mismatch")
    observed = bundle.pop("fingerprint", None)
    if observed != _fingerprint(bundle):
        raise G16AttributionBoundPublicationError("validation bundle fingerprint mismatch")
    bundle["fingerprint"] = observed
    for field in ("bound_lock_validation", "publication_validation"):
        if not isinstance(bundle.get(field), Mapping):
            raise G16AttributionBoundPublicationError(f"validation bundle lacks {field} mapping")
    return bundle


def _default_bound_lock_validator(value: Mapping[str, Any], kwargs: Mapping[str, Any]) -> None:
    from ng_g16_attribution_bound_curve_lock_gate import validate_gate

    if kwargs:
        raise G16AttributionBoundPublicationError(
            "attribution-bound curve-lock validation does not accept external kwargs"
        )
    validate_gate(value)


def _default_publication_validator(value: Mapping[str, Any], kwargs: Mapping[str, Any]) -> None:
    from ng_g16_counterfactual_publication_gate import validate_completion

    validate_completion(value, **dict(_decode_bytes(kwargs)))


def _default_score_validator(value: Mapping[str, Any]) -> None:
    from ng_g16_path_score import validate_scorecard

    validate_scorecard(value)


def _default_comparison_validator(value: Mapping[str, Any]) -> None:
    from ng_g16_path_score import validate_comparison

    validate_comparison(value)


def _controls(value: Mapping[str, Any], *, label: str, outcomes_used: bool) -> None:
    if value.get("actual_g16_outcomes_used") is not outcomes_used:
        raise G16AttributionBoundPublicationError(
            f"{label} actual_g16_outcomes_used must be {outcomes_used}"
        )
    for field in (
        "random_shuffle_used",
        "may_change_any_blind_prior",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
        "options_implementation_authorized",
    ):
        if field in value and value.get(field) is not False:
            raise G16AttributionBoundPublicationError(f"{label} must keep {field}=false")
    for field in ("actual_g15_outcomes_used", "one_signal_authority_preserved", "blind_forecasts_immutable"):
        if value.get(field) is not True:
            raise G16AttributionBoundPublicationError(f"{label} must keep {field}=true")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16AttributionBoundPublicationError(f"{label} must keep CME event contracts SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16AttributionBoundPublicationError(f"{label} must preserve tastytrade rather than IBKR")


def _validate_score(
    score: Mapping[str, Any],
    *,
    role: str,
    publication: Mapping[str, Any],
    validator: Callable[[Mapping[str, Any]], None],
) -> dict[str, Any]:
    try:
        validator(score)
    except Exception as error:
        raise G16AttributionBoundPublicationError(f"{role} score invalid: {error}") from error
    checked = _signed(score, "score_fingerprint", f"{role} score")
    if checked.get("schema") != SCORE_SCHEMA or checked.get("role") != role:
        raise G16AttributionBoundPublicationError(f"{role} score schema/role mismatch")
    expected_forecast = publication.get(f"{role}_forecast_sha256")
    if checked.get("forecast_sha256") != expected_forecast:
        raise G16AttributionBoundPublicationError(f"{role} score references another forecast")
    if checked.get("actual_sha256") != publication.get("actual_sha256"):
        raise G16AttributionBoundPublicationError(f"{role} score references another actual substrate")
    if checked.get("score_fingerprint") != publication.get(f"{role}_score_fingerprint"):
        raise G16AttributionBoundPublicationError(f"publication references another {role} score")
    return checked


def _validate_comparison(
    comparison: Mapping[str, Any],
    *,
    publication: Mapping[str, Any],
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
    validator: Callable[[Mapping[str, Any]], None],
) -> dict[str, Any]:
    try:
        validator(comparison)
    except Exception as error:
        raise G16AttributionBoundPublicationError(f"comparison invalid: {error}") from error
    checked = _signed(comparison, "comparison_fingerprint", "G16 comparison")
    if checked.get("schema") != COMPARISON_SCHEMA:
        raise G16AttributionBoundPublicationError("G16 comparison schema mismatch")
    if checked.get("actual_sha256") != publication.get("actual_sha256"):
        raise G16AttributionBoundPublicationError("comparison references another actual substrate")
    if checked.get("blind_score_fingerprint") != blind_score.get("score_fingerprint"):
        raise G16AttributionBoundPublicationError("comparison references another blind score")
    if checked.get("refined_score_fingerprint") != refined_score.get("score_fingerprint"):
        raise G16AttributionBoundPublicationError("comparison references another refined score")
    if checked.get("comparison_fingerprint") != publication.get("comparison_fingerprint"):
        raise G16AttributionBoundPublicationError("publication references another comparison")
    return checked


def _cross_checks(bound: Mapping[str, Any], publication: Mapping[str, Any]) -> None:
    links = {
        "legacy curve lock": (
            bound.get("counterfactual_curve_lock_fingerprint"),
            publication.get("counterfactual_curve_lock_fingerprint"),
        ),
        "legacy curve authorization": (
            bound.get("counterfactual_curve_authorization_fingerprint"),
            publication.get("counterfactual_curve_authorization_fingerprint"),
        ),
        "prepared curve authorization": (
            bound.get("prepared_curve_authorization_fingerprint"),
            publication.get("prepared_curve_authorization_fingerprint"),
        ),
        "prepared curve lock": (
            bound.get("prepared_curve_lock_fingerprint"),
            publication.get("prepared_curve_lock_fingerprint"),
        ),
        "historical replay": (bound.get("replay_fingerprint"), publication.get("replay_fingerprint")),
        "manifest": (bound.get("manifest_fingerprint"), publication.get("manifest_fingerprint")),
        "prepared corpus": (
            bound.get("prepared_corpus_fingerprint"),
            publication.get("prepared_corpus_fingerprint"),
        ),
        "blind prior": (
            bound.get("blind_prior_fingerprint"),
            publication.get("blind_prior_fingerprint"),
        ),
        "G16 plan": (bound.get("g16_plan_fingerprint"), publication.get("plan_fingerprint")),
        "authorization stream": (
            bound.get("authorization_stream_fingerprint"),
            publication.get("authorization_stream_fingerprint"),
        ),
        "posterior stream": (
            bound.get("posterior_stream_fingerprint"),
            publication.get("posterior_stream_fingerprint"),
        ),
        "refined curve": (
            bound.get("refined_curve_fingerprint"),
            publication.get("refined_curve_fingerprint"),
        ),
        "blind forecast bytes": (
            bound.get("blind_forecast_sha256"),
            publication.get("blind_forecast_sha256"),
        ),
        "refined forecast bytes": (
            bound.get("refined_forecast_sha256"),
            publication.get("refined_forecast_sha256"),
        ),
        "G15 publication": (
            bound.get("publication_completion_fingerprint"),
            publication.get("g15_publication_fingerprint"),
        ),
        "G15 adjudication": (
            bound.get("g15_adjudication_fingerprint"),
            publication.get("g15_adjudication_fingerprint"),
        ),
        "G16 registry": (
            bound.get("g16_registry_fingerprint"),
            publication.get("g16_registry_fingerprint"),
        ),
    }
    for label, values in links.items():
        normalized = [str(item or "") for item in values]
        if any(not item for item in normalized) or len(set(normalized)) != 1:
            raise G16AttributionBoundPublicationError(f"{label} lineage mismatch")

    for field in ("candidate_ids", "candidate_ids_used_by_curve"):
        if list(bound.get(field) or []) != list(publication.get(field) or []):
            raise G16AttributionBoundPublicationError(f"{field} lineage mismatch")
    if dict(bound.get("candidate_evidence_fingerprints") or {}) != dict(
        publication.get("candidate_evidence_fingerprints") or {}
    ):
        raise G16AttributionBoundPublicationError("candidate evidence lineage mismatch")


def _build_gate(
    *,
    attribution_bound_curve_lock: Mapping[str, Any],
    counterfactual_publication: Mapping[str, Any],
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
    comparison: Mapping[str, Any],
    validation_bundle: Mapping[str, Any],
    bound_lock_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_bound_lock_validator,
    publication_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_publication_validator,
    score_validator: Callable[[Mapping[str, Any]], None] = _default_score_validator,
    comparison_validator: Callable[[Mapping[str, Any]], None] = _default_comparison_validator,
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            attribution_bound_curve_lock,
            counterfactual_publication,
            blind_score,
            refined_score,
            comparison,
            validation_bundle,
        )
    )
    bundle = _normalize_bundle(validation_bundle)
    try:
        bound_lock_validator(
            attribution_bound_curve_lock,
            dict(bundle["bound_lock_validation"]),
        )
        publication_validator(
            counterfactual_publication,
            dict(bundle["publication_validation"]),
        )
    except Exception as error:
        raise G16AttributionBoundPublicationError(str(error)) from error

    bound = _signed(attribution_bound_curve_lock, "fingerprint", "attribution-bound curve lock")
    publication = _signed(
        counterfactual_publication,
        "completion_fingerprint",
        "counterfactual publication",
    )
    if bound.get("schema") != BOUND_LOCK_SCHEMA or bound.get("status") not in {
        "G16_ATTRIBUTION_BOUND_CURVE_LOCKED",
        "G16_ATTRIBUTION_BOUND_CURVE_LOCKED_WITH_STAND_DOWNS",
    }:
        raise G16AttributionBoundPublicationError("attribution-bound curve lock is not ready")
    if bound.get("next_permitted_stage") != (
        "FIXED_G16_BLIND_REFINED_SCORING_WITH_ATTRIBUTION_BOUND_LINEAGE"
    ):
        raise G16AttributionBoundPublicationError("attribution-bound curve lock next stage mismatch")
    if publication.get("schema") != PUBLICATION_SCHEMA or publication.get("status") not in {
        "EXACT_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE",
        "EXACT_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_WITH_STAND_DOWNS",
    }:
        raise G16AttributionBoundPublicationError("counterfactual publication is not complete")

    _controls(bound, label="attribution-bound curve lock", outcomes_used=False)
    _controls(publication, label="counterfactual publication", outcomes_used=True)
    for field in (
        "all_six_factors_authorized_before_scoring",
        "separate_blind_refined_scores_verified",
        "scored_lessons_bound_to_attribution_publication",
        "g16_plan_bound_to_validated_g15_lessons",
        "g16_posterior_bound_to_attribution_scored_g15_lessons",
        "g16_curve_bound_to_attribution_scored_g15_lessons",
        "g16_curve_lock_bound_to_attribution_scored_g15_lessons",
        "lesson_proposals_brain_write_forbidden",
    ):
        if bound.get(field) is not True:
            raise G16AttributionBoundPublicationError(f"attribution-bound lock lost {field}")
    for field in (
        "counterfactual_lineage_preserved_through_fixed_scoring",
        "curve_locked_before_fixed_scoring",
        "outcome_scoring_complete",
        "chronological_validation_complete",
        "continuous_rt_renders_complete",
        "g16_consumed_as_forward_holdout",
    ):
        if publication.get(field) is not True:
            raise G16AttributionBoundPublicationError(f"counterfactual publication lost {field}")

    _cross_checks(bound, publication)
    blind = _validate_score(
        blind_score,
        role="blind",
        publication=publication,
        validator=score_validator,
    )
    refined = _validate_score(
        refined_score,
        role="refined",
        publication=publication,
        validator=score_validator,
    )
    if blind["score_fingerprint"] == refined["score_fingerprint"]:
        raise G16AttributionBoundPublicationError("blind and refined score artifacts collapsed")
    compared = _validate_comparison(
        comparison,
        publication=publication,
        blind_score=blind,
        refined_score=refined,
        validator=comparison_validator,
    )

    stand_downs = sorted(
        {str(day) for day in bound.get("stand_down_days") or []}
        | {str(day) for day in publication.get("stand_down_days") or []}
    )
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": READY_WITH_STAND_DOWNS if stand_downs else READY,
        "authority": AUTHORITY,
        "attribution_bound_curve_lock_fingerprint": bound["fingerprint"],
        "counterfactual_publication_fingerprint": publication["completion_fingerprint"],
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
        "blind_score_fingerprint": blind["score_fingerprint"],
        "refined_score_fingerprint": refined["score_fingerprint"],
        "comparison_fingerprint": compared["comparison_fingerprint"],
        "chronological_validation_fingerprint": publication[
            "chronological_validation_fingerprint"
        ],
        "candidate_count": bound["candidate_count"],
        "candidate_ids": copy.deepcopy(list(bound.get("candidate_ids") or [])),
        "candidate_evidence_fingerprints": copy.deepcopy(
            dict(bound.get("candidate_evidence_fingerprints") or {})
        ),
        "candidate_ids_used_by_curve": copy.deepcopy(
            list(bound.get("candidate_ids_used_by_curve") or [])
        ),
        "stand_down_days": stand_downs,
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
        "may_change_any_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "options_implementation_authorized": False,
        "next_permitted_stage": NEXT_STAGE,
        "attribution_bound_curve_lock": copy.deepcopy(bound),
        "counterfactual_publication": copy.deepcopy(publication),
        "blind_score": copy.deepcopy(blind),
        "refined_score": copy.deepcopy(refined),
        "comparison": copy.deepcopy(compared),
        "validation_bundle": copy.deepcopy(bundle),
        "note": (
            "The fixed G16 blind/refined scores and chronological publication are "
            "recursively bound to the immutable attribution-scored G15 lesson lineage."
        ),
    }
    result["fingerprint"] = _fingerprint(result)
    current = (
        attribution_bound_curve_lock,
        counterfactual_publication,
        blind_score,
        refined_score,
        comparison,
        validation_bundle,
    )
    if current != originals:
        raise G16AttributionBoundPublicationError("publication gate mutated an input artifact")
    return result


def build_gate(**kwargs: Any) -> dict[str, Any]:
    result = _build_gate(**kwargs)
    validate_gate(
        result,
        bound_lock_validator=kwargs.get("bound_lock_validator", _default_bound_lock_validator),
        publication_validator=kwargs.get("publication_validator", _default_publication_validator),
        score_validator=kwargs.get("score_validator", _default_score_validator),
        comparison_validator=kwargs.get("comparison_validator", _default_comparison_validator),
    )
    return result


def validate_gate(
    value: Mapping[str, Any],
    *,
    bound_lock_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_bound_lock_validator,
    publication_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_publication_validator,
    score_validator: Callable[[Mapping[str, Any]], None] = _default_score_validator,
    comparison_validator: Callable[[Mapping[str, Any]], None] = _default_comparison_validator,
) -> None:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or observed != _fingerprint(candidate):
        raise G16AttributionBoundPublicationError("gate schema or fingerprint mismatch")
    if candidate.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise G16AttributionBoundPublicationError("gate is not ready")
    if candidate.get("authority") != AUTHORITY:
        raise G16AttributionBoundPublicationError("gate authority mismatch")
    _controls(candidate, label="attribution-bound publication gate", outcomes_used=True)
    for field in (
        "all_six_factors_authorized_before_g16_scoring",
        "separate_g15_blind_refined_scores_verified",
        "separate_g16_blind_refined_scores_verified",
        "g16_publication_bound_to_attribution_scored_g15_lessons",
        "g16_curve_locked_before_fixed_scoring",
        "g16_chronological_forward_holdout_scored",
        "lesson_proposals_brain_write_forbidden",
        "outcome_scoring_complete",
    ):
        if candidate.get(field) is not True:
            raise G16AttributionBoundPublicationError(f"gate lost {field}")
    if candidate.get("next_permitted_stage") != NEXT_STAGE:
        raise G16AttributionBoundPublicationError("gate next stage mismatch")
    embedded = (
        candidate.get("attribution_bound_curve_lock"),
        candidate.get("counterfactual_publication"),
        candidate.get("blind_score"),
        candidate.get("refined_score"),
        candidate.get("comparison"),
        candidate.get("validation_bundle"),
    )
    if not all(isinstance(item, Mapping) for item in embedded):
        raise G16AttributionBoundPublicationError("gate lacks recursively embedded scoring lineage")
    rebuilt = _build_gate(
        attribution_bound_curve_lock=embedded[0],
        counterfactual_publication=embedded[1],
        blind_score=embedded[2],
        refined_score=embedded[3],
        comparison=embedded[4],
        validation_bundle=embedded[5],
        bound_lock_validator=bound_lock_validator,
        publication_validator=publication_validator,
        score_validator=score_validator,
        comparison_validator=comparison_validator,
    )
    if dict(value) != rebuilt:
        raise G16AttributionBoundPublicationError(
            "gate differs from deterministic recursive reconstruction"
        )


def _noop(*args: Any, **kwargs: Any) -> None:
    return None


def _synthetic_fixture() -> dict[str, Any]:
    common = {
        "counterfactual_curve_lock_fingerprint": "a" * 64,
        "counterfactual_curve_authorization_fingerprint": "b" * 64,
        "attribution_bound_causal_authorization_fingerprint": "c" * 64,
        "prepared_curve_authorization_fingerprint": "d" * 64,
        "prepared_curve_lock_fingerprint": "e" * 64,
        "replay_fingerprint": "f" * 64,
        "manifest_fingerprint": "1" * 64,
        "prepared_corpus_fingerprint": "2" * 64,
        "blind_prior_fingerprint": "3" * 64,
        "authorization_stream_fingerprint": "4" * 64,
        "posterior_stream_fingerprint": "5" * 64,
        "refined_curve_fingerprint": "6" * 64,
        "blind_forecast_sha256": "7" * 64,
        "refined_forecast_sha256": "8" * 64,
        "g15_adjudication_fingerprint": "9" * 64,
        "g16_registry_fingerprint": "0" * 64,
    }
    bound: dict[str, Any] = {
        "schema": BOUND_LOCK_SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": "G16_ATTRIBUTION_BOUND_CURVE_LOCKED",
        "authority": "G15_ATTRIBUTION_BOUND_LESSONS_TO_IMMUTABLE_G16_CURVE_LOCK_ONLY",
        **common,
        "attribution_bound_curve_authorization_fingerprint": "a1" * 32,
        "attribution_bound_lineage_fingerprint": "a2" * 32,
        "attribution_bound_publication_fingerprint": "a3" * 32,
        "attribution_authorization_fingerprint": "a4" * 32,
        "publication_completion_fingerprint": "a5" * 32,
        "counterfactual_attribution_fingerprint": "a6" * 32,
        "counterfactual_lesson_gate_fingerprint": "a7" * 32,
        "legacy_lineage_fingerprint": "a8" * 32,
        "blind_score_fingerprint": "a9" * 32,
        "refined_score_fingerprint": "aa" * 32,
        "comparison_fingerprint": "ab" * 32,
        "g16_plan_fingerprint": "ac" * 32,
        "prepared_causal_authorization_fingerprint": "ad" * 32,
        "prepared_replay_gate_fingerprint": "ae" * 32,
        "g16_blind_forecast_fingerprint": "af" * 32,
        "candidate_count": 1,
        "candidate_ids": ["lesson-1"],
        "candidate_evidence_fingerprints": {"lesson-1": "be" * 32},
        "candidate_ids_used_by_curve": ["lesson-1"],
        "stand_down_days": [],
        "all_six_factors_authorized_before_scoring": True,
        "separate_blind_refined_scores_verified": True,
        "scored_lessons_bound_to_attribution_publication": True,
        "g16_plan_bound_to_validated_g15_lessons": True,
        "g16_posterior_bound_to_attribution_scored_g15_lessons": True,
        "g16_curve_bound_to_attribution_scored_g15_lessons": True,
        "g16_curve_lock_bound_to_attribution_scored_g15_lessons": True,
        "lesson_proposals_brain_write_forbidden": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "fixed_scoring_may_begin": True,
        "curve_locked_before_fixed_scoring": True,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "curve_mutation_authorized": False,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "g16_outcome_access_authorized": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "FIXED_G16_BLIND_REFINED_SCORING_WITH_ATTRIBUTION_BOUND_LINEAGE",
    }
    bound["fingerprint"] = _fingerprint(bound)

    actual_sha = "ca" * 32
    publication: dict[str, Any] = {
        "schema": PUBLICATION_SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": "EXACT_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE",
        "authority": "EXACT_G15_COUNTERFACTUAL_LINEAGE_THROUGH_G16_SCORED_PUBLICATION_ONLY",
        **{key: value for key, value in common.items() if key != "attribution_bound_causal_authorization_fingerprint"},
        "counterfactual_causal_authorization_fingerprint": common[
            "attribution_bound_causal_authorization_fingerprint"
        ],
        "plan_fingerprint": bound["g16_plan_fingerprint"],
        "g15_publication_fingerprint": bound["publication_completion_fingerprint"],
        "candidate_ids": ["lesson-1"],
        "candidate_evidence_fingerprints": {"lesson-1": "be" * 32},
        "candidate_ids_used_by_curve": ["lesson-1"],
        "actual_sha256": actual_sha,
        "blind_score_fingerprint": "11" * 32,
        "refined_score_fingerprint": "22" * 32,
        "comparison_fingerprint": "33" * 32,
        "chronological_validation_fingerprint": "44" * 32,
        "stand_down_days": [],
        "counterfactual_lineage_preserved_through_fixed_scoring": True,
        "curve_locked_before_fixed_scoring": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": True,
        "outcome_scoring_complete": True,
        "chronological_validation_complete": True,
        "continuous_rt_renders_complete": True,
        "g16_consumed_as_forward_holdout": True,
        "g16_reusable_as_untouched_holdout": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_any_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "options_implementation_authorized": False,
    }
    publication["completion_fingerprint"] = _fingerprint(publication)

    blind_score = {
        "schema": SCORE_SCHEMA,
        "role": "blind",
        "forecast_sha256": publication["blind_forecast_sha256"],
        "actual_sha256": actual_sha,
    }
    blind_score["score_fingerprint"] = _fingerprint(blind_score)
    refined_score = {
        "schema": SCORE_SCHEMA,
        "role": "refined",
        "forecast_sha256": publication["refined_forecast_sha256"],
        "actual_sha256": actual_sha,
    }
    refined_score["score_fingerprint"] = _fingerprint(refined_score)
    publication.pop("completion_fingerprint")
    publication["blind_score_fingerprint"] = blind_score["score_fingerprint"]
    publication["refined_score_fingerprint"] = refined_score["score_fingerprint"]
    comparison = {
        "schema": COMPARISON_SCHEMA,
        "actual_sha256": actual_sha,
        "blind_score_fingerprint": blind_score["score_fingerprint"],
        "refined_score_fingerprint": refined_score["score_fingerprint"],
    }
    comparison["comparison_fingerprint"] = _fingerprint(comparison)
    publication["comparison_fingerprint"] = comparison["comparison_fingerprint"]
    publication["completion_fingerprint"] = _fingerprint(publication)

    bundle = {
        "schema": BUNDLE_SCHEMA,
        "bound_lock_validation": {},
        "publication_validation": {},
    }
    bundle["fingerprint"] = _fingerprint(bundle)
    return {
        "attribution_bound_curve_lock": bound,
        "counterfactual_publication": publication,
        "blind_score": blind_score,
        "refined_score": refined_score,
        "comparison": comparison,
        "validation_bundle": bundle,
        "bound_lock_validator": _noop,
        "publication_validator": _noop,
        "score_validator": _noop,
        "comparison_validator": _noop,
    }


def _selftest() -> None:
    fixture = _synthetic_fixture()
    gate = build_gate(**fixture)
    validators = {
        key: fixture[key]
        for key in (
            "bound_lock_validator",
            "publication_validator",
            "score_validator",
            "comparison_validator",
        )
    }
    validate_gate(gate, **validators)
    again = build_gate(**fixture)
    assert gate == again
    bad = copy.deepcopy(gate)
    bad["may_update_ng_brain"] = True
    bad.pop("fingerprint")
    bad["fingerprint"] = _fingerprint(bad)
    try:
        validate_gate(bad, **validators)
    except G16AttributionBoundPublicationError:
        pass
    else:
        raise AssertionError("brain-write escalation was accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bound-lock", type=Path)
    parser.add_argument("--publication", type=Path)
    parser.add_argument("--blind-score", type=Path)
    parser.add_argument("--refined-score", type=Path)
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--validation-bundle", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        print(json.dumps({"status": "SELFTEST_PASS", "schema": SCHEMA}, sort_keys=True))
        return 0
    required = (
        args.bound_lock,
        args.publication,
        args.blind_score,
        args.refined_score,
        args.comparison,
        args.validation_bundle,
        args.out,
    )
    if any(path is None for path in required):
        parser.error(
            "--bound-lock, --publication, --blind-score, --refined-score, --comparison, "
            "--validation-bundle, and --out are required"
        )
    gate = build_gate(
        attribution_bound_curve_lock=_load(args.bound_lock),
        counterfactual_publication=_load(args.publication),
        blind_score=_load(args.blind_score),
        refined_score=_load(args.refined_score),
        comparison=_load(args.comparison),
        validation_bundle=_load(args.validation_bundle),
    )
    _atomic(args.out, gate)
    print(json.dumps({"status": gate["status"], "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
