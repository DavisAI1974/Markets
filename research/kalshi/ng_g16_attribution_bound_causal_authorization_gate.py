#!/usr/bin/env python3
"""Bind attribution-scored G15 lessons into the exact pre-cutoff G16 causal path.

The legacy G16 counterfactual causal authorization recursively validates the prepared
23-source G16 replay and causal posterior, but it predates the attribution-bound G15
lesson-lineage gate. This audit-only wrapper requires both artifacts together and
proves that the exact G16 posterior used the same G15 lesson registry, candidate set,
and SHADOW plan that descend from six-factor-authorized G15 publication and separate
blind/refined scoring.

The gate is fixed-G15-outcome but G16-outcome-blind. It never reads G16 outcomes,
changes either blind forecast, mutates posterior state or ``knowledge/ng_brain.json``,
grants execution authority, or starts the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA = "ng_g16_attribution_bound_causal_authorization_gate.v1"
BUNDLE_SCHEMA = "ng_g16_attribution_bound_causal_validation_bundle.v1"
AUTHORITY = "G15_ATTRIBUTION_BOUND_LESSONS_TO_G16_PRE_CUTOFF_CAUSAL_ONLY"
READY = "G16_ATTRIBUTION_BOUND_CAUSAL_AUTHORIZED"
READY_WITH_STAND_DOWNS = "G16_ATTRIBUTION_BOUND_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS"
NEXT_STAGE = "OUTCOME_BLIND_G16_CURVE_ADAPTER_WITH_ATTRIBUTION_BOUND_LINEAGE"

BOUND_LINEAGE_SCHEMA = "ng_g15_g16_attribution_bound_lineage_gate.v1"
LEGACY_CAUSAL_SCHEMA = "ng_g16_counterfactual_causal_authorization.v1"


class G16AttributionBoundCausalAuthorizationError(ValueError):
    """Raised when attribution-scored G15 lineage and the G16 posterior diverge."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G16AttributionBoundCausalAuthorizationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise G16AttributionBoundCausalAuthorizationError(
            f"artifact must be a JSON object: {path}"
        )
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _verify_fingerprint(
    value: Mapping[str, Any], field: str, *, label: str
) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop(field, None)
    if not isinstance(observed, str) or observed != _fingerprint(candidate):
        raise G16AttributionBoundCausalAuthorizationError(
            f"{label}: {field} mismatch"
        )
    return copy.deepcopy(dict(value))


def _default_validate_bound(
    value: Mapping[str, Any], validation_kwargs: Mapping[str, Any]
) -> None:
    from ng_g15_g16_attribution_bound_lineage_gate import validate_gate

    validate_gate(value, **dict(validation_kwargs))


def _default_validate_legacy(
    value: Mapping[str, Any], validation_kwargs: Mapping[str, Any]
) -> None:
    from ng_g16_counterfactual_causal_authorization import (
        validate_authorization_artifact,
    )

    validate_authorization_artifact(value, **dict(validation_kwargs))


def _controls(value: Mapping[str, Any], *, label: str) -> None:
    false_fields = (
        "actual_g16_outcomes_used",
        "g16_scoring_authorized",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "g16_outcome_access_authorized",
        "options_lane_started",
    )
    for field in false_fields:
        if field in value and value.get(field) is not False:
            raise G16AttributionBoundCausalAuthorizationError(
                f"{label} must keep {field}=false"
            )
    if value.get("actual_g15_outcomes_used") is not True:
        raise G16AttributionBoundCausalAuthorizationError(
            f"{label} must disclose fixed G15 outcome use"
        )
    if value.get("one_signal_authority_preserved") is not True:
        raise G16AttributionBoundCausalAuthorizationError(
            f"{label} must preserve one signal authority"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise G16AttributionBoundCausalAuthorizationError(
            f"{label} must preserve blind forecast immutability"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16AttributionBoundCausalAuthorizationError(
            f"{label} must keep CME event contracts SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16AttributionBoundCausalAuthorizationError(
            f"{label} must preserve tastytrade rather than IBKR"
        )


def _normalize_bundle(value: Mapping[str, Any]) -> dict[str, Any]:
    bundle = copy.deepcopy(dict(value))
    if bundle.get("schema") != BUNDLE_SCHEMA:
        raise G16AttributionBoundCausalAuthorizationError(
            "validation bundle schema mismatch"
        )
    bound_kwargs = bundle.get("bound_lineage_validation")
    legacy_kwargs = bundle.get("legacy_causal_validation")
    if not isinstance(bound_kwargs, Mapping) or not isinstance(legacy_kwargs, Mapping):
        raise G16AttributionBoundCausalAuthorizationError(
            "validation bundle must contain bound and legacy validation mappings"
        )
    bundle_without_fp = copy.deepcopy(bundle)
    observed = bundle_without_fp.pop("fingerprint", None)
    if observed != _fingerprint(bundle_without_fp):
        raise G16AttributionBoundCausalAuthorizationError(
            "validation bundle fingerprint mismatch"
        )
    return bundle


def _cross_checks(
    *,
    bound_lineage: Mapping[str, Any],
    legacy_causal: Mapping[str, Any],
) -> tuple[list[str], dict[str, str], list[str]]:
    equalities: dict[str, tuple[str, ...]] = {
        "legacy G15-G16 lineage": (
            str(bound_lineage.get("legacy_lineage_fingerprint") or ""),
            str(legacy_causal.get("counterfactual_lineage_gate_fingerprint") or ""),
        ),
        "G15 counterfactual attribution": (
            str(bound_lineage.get("counterfactual_attribution_fingerprint") or ""),
            str(legacy_causal.get("counterfactual_attribution_fingerprint") or ""),
        ),
        "G15 counterfactual lesson gate": (
            str(bound_lineage.get("counterfactual_lesson_gate_fingerprint") or ""),
            str(legacy_causal.get("counterfactual_lesson_gate_fingerprint") or ""),
        ),
        "G15 publication": (
            str(bound_lineage.get("publication_completion_fingerprint") or ""),
            str(legacy_causal.get("g15_publication_fingerprint") or ""),
        ),
        "G15 lesson adjudication": (
            str(bound_lineage.get("g15_adjudication_fingerprint") or ""),
            str(legacy_causal.get("g15_adjudication_fingerprint") or ""),
        ),
        "G16 lesson registry": (
            str(bound_lineage.get("g16_registry_fingerprint") or ""),
            str(legacy_causal.get("g16_registry_fingerprint") or ""),
        ),
        "G16 SHADOW plan": (
            str(bound_lineage.get("g16_plan_fingerprint") or ""),
            str(legacy_causal.get("g16_plan_fingerprint") or ""),
        ),
    }
    for label, values in equalities.items():
        if any(not value for value in values) or len(set(values)) != 1:
            raise G16AttributionBoundCausalAuthorizationError(
                f"{label} lineage mismatch"
            )

    bound_ids = [str(value) for value in bound_lineage.get("candidate_ids") or []]
    legacy_ids = [str(value) for value in legacy_causal.get("candidate_ids") or []]
    if not bound_ids or bound_ids != sorted(bound_ids) or len(bound_ids) != len(set(bound_ids)):
        raise G16AttributionBoundCausalAuthorizationError(
            "attribution-bound candidate ids must be non-empty, sorted, and unique"
        )
    if legacy_ids != bound_ids:
        raise G16AttributionBoundCausalAuthorizationError(
            "G16 causal candidate set differs from attribution-bound lineage"
        )
    if int(bound_lineage.get("candidate_count") or 0) != len(bound_ids):
        raise G16AttributionBoundCausalAuthorizationError(
            "attribution-bound candidate_count mismatch"
        )
    if int(legacy_causal.get("candidate_count") or 0) != len(bound_ids):
        raise G16AttributionBoundCausalAuthorizationError(
            "legacy causal candidate_count mismatch"
        )

    bound_evidence = {
        str(key): str(value)
        for key, value in dict(
            bound_lineage.get("candidate_evidence_fingerprints") or {}
        ).items()
    }
    legacy_evidence = {
        str(key): str(value)
        for key, value in dict(
            legacy_causal.get("candidate_evidence_fingerprints") or {}
        ).items()
    }
    if sorted(bound_evidence) != bound_ids or any(
        not value for value in bound_evidence.values()
    ):
        raise G16AttributionBoundCausalAuthorizationError(
            "attribution-bound candidate evidence is incomplete"
        )
    if legacy_evidence != bound_evidence:
        raise G16AttributionBoundCausalAuthorizationError(
            "G16 causal candidate evidence differs from attribution-bound lineage"
        )

    used_ids = [
        str(value)
        for value in legacy_causal.get(
            "candidate_ids_observed_in_posterior_attribution"
        )
        or []
    ]
    if used_ids != sorted(set(used_ids)) or any(
        value not in bound_ids for value in used_ids
    ):
        raise G16AttributionBoundCausalAuthorizationError(
            "posterior attribution contains invalid candidate ids"
        )
    return bound_ids, bound_evidence, used_ids


def _build_gate(
    *,
    attribution_bound_lineage: Mapping[str, Any],
    counterfactual_causal_authorization: Mapping[str, Any],
    validation_bundle: Mapping[str, Any],
    bound_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_validate_bound,
    causal_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_validate_legacy,
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            attribution_bound_lineage,
            counterfactual_causal_authorization,
            validation_bundle,
        )
    )
    bundle = _normalize_bundle(validation_bundle)
    bound_kwargs = dict(bundle["bound_lineage_validation"])
    legacy_kwargs = dict(bundle["legacy_causal_validation"])

    try:
        bound_validator(attribution_bound_lineage, bound_kwargs)
        causal_validator(counterfactual_causal_authorization, legacy_kwargs)
    except Exception as error:
        raise G16AttributionBoundCausalAuthorizationError(str(error)) from error

    bound = _verify_fingerprint(
        attribution_bound_lineage,
        "fingerprint",
        label="attribution-bound G15-G16 lineage",
    )
    legacy = _verify_fingerprint(
        counterfactual_causal_authorization,
        "fingerprint",
        label="legacy G16 counterfactual causal authorization",
    )
    if bound.get("schema") != BOUND_LINEAGE_SCHEMA:
        raise G16AttributionBoundCausalAuthorizationError(
            "attribution-bound lineage schema mismatch"
        )
    if legacy.get("schema") != LEGACY_CAUSAL_SCHEMA:
        raise G16AttributionBoundCausalAuthorizationError(
            "legacy causal authorization schema mismatch"
        )
    if bound.get("status") not in {
        "G15_ATTRIBUTION_BOUND_LESSONS_G16_LINEAGE_AUTHORIZED",
        "G15_ATTRIBUTION_BOUND_LESSONS_G16_LINEAGE_AUTHORIZED_WITH_STAND_DOWNS",
    }:
        raise G16AttributionBoundCausalAuthorizationError(
            "attribution-bound G15-G16 lineage is not ready"
        )
    if legacy.get("status") not in {
        "G16_COUNTERFACTUAL_CAUSAL_AUTHORIZED",
        "G16_COUNTERFACTUAL_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS",
    }:
        raise G16AttributionBoundCausalAuthorizationError(
            "legacy G16 causal authorization is not ready"
        )

    _controls(bound, label="attribution-bound G15-G16 lineage")
    _controls(legacy, label="legacy G16 causal authorization")
    for field in (
        "all_six_factors_authorized_before_scoring",
        "separate_blind_refined_scores_verified",
        "scored_lessons_bound_to_attribution_publication",
        "g16_plan_bound_to_validated_g15_lessons",
        "lesson_proposals_brain_write_forbidden",
    ):
        if bound.get(field) is not True:
            raise G16AttributionBoundCausalAuthorizationError(
                f"attribution-bound lineage lost mandatory field: {field}"
            )

    candidate_ids, evidence, used_ids = _cross_checks(
        bound_lineage=bound, legacy_causal=legacy
    )
    stand_down_days = sorted(
        set(str(day) for day in bound.get("stand_down_days") or [])
        | set(str(day) for day in legacy.get("all_stand_down_days") or [])
    )
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": READY_WITH_STAND_DOWNS if stand_down_days else READY,
        "authority": AUTHORITY,
        "attribution_bound_lineage_fingerprint": bound["fingerprint"],
        "legacy_counterfactual_causal_authorization_fingerprint": legacy[
            "fingerprint"
        ],
        "attribution_bound_publication_fingerprint": bound[
            "attribution_bound_publication_fingerprint"
        ],
        "attribution_authorization_fingerprint": bound[
            "attribution_authorization_fingerprint"
        ],
        "publication_completion_fingerprint": bound[
            "publication_completion_fingerprint"
        ],
        "counterfactual_attribution_fingerprint": bound[
            "counterfactual_attribution_fingerprint"
        ],
        "counterfactual_lesson_gate_fingerprint": bound[
            "counterfactual_lesson_gate_fingerprint"
        ],
        "legacy_lineage_fingerprint": bound["legacy_lineage_fingerprint"],
        "blind_score_fingerprint": bound["blind_score_fingerprint"],
        "refined_score_fingerprint": bound["refined_score_fingerprint"],
        "comparison_fingerprint": bound["comparison_fingerprint"],
        "g15_adjudication_fingerprint": bound["g15_adjudication_fingerprint"],
        "g16_registry_fingerprint": bound["g16_registry_fingerprint"],
        "g16_plan_fingerprint": bound["g16_plan_fingerprint"],
        "prepared_causal_authorization_fingerprint": legacy[
            "prepared_causal_authorization_fingerprint"
        ],
        "prepared_replay_gate_fingerprint": legacy[
            "prepared_replay_gate_fingerprint"
        ],
        "replay_fingerprint": legacy["replay_fingerprint"],
        "manifest_fingerprint": legacy["manifest_fingerprint"],
        "prepared_corpus_fingerprint": legacy["prepared_corpus_fingerprint"],
        "blind_prior_fingerprint": legacy["blind_prior_fingerprint"],
        "authorization_stream_fingerprint": legacy[
            "authorization_stream_fingerprint"
        ],
        "posterior_stream_fingerprint": legacy["posterior_stream_fingerprint"],
        "g16_blind_forecast_fingerprint": legacy[
            "g16_blind_forecast_fingerprint"
        ],
        "g16_blind_safe_state_fingerprint": legacy[
            "g16_blind_safe_state_fingerprint"
        ],
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_observed_in_posterior_attribution": used_ids,
        "stand_down_days": stand_down_days,
        "all_six_factors_authorized_before_scoring": True,
        "separate_blind_refined_scores_verified": True,
        "scored_lessons_bound_to_attribution_publication": True,
        "g16_plan_bound_to_validated_g15_lessons": True,
        "g16_posterior_bound_to_attribution_scored_g15_lessons": True,
        "lesson_proposals_brain_write_forbidden": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
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
        "next_permitted_stage": NEXT_STAGE,
        "attribution_bound_lineage": copy.deepcopy(bound),
        "counterfactual_causal_authorization": copy.deepcopy(legacy),
        "validation_bundle": copy.deepcopy(bundle),
        "note": (
            "The exact pre-cutoff G16 posterior is recursively bound to G15 lessons that "
            "descend from six-factor authorization and separate blind/refined G15 scoring. "
            "G16 outcomes, scoring, execution, options, posterior mutation, and "
            "ng_brain.json writes remain forbidden."
        ),
    }
    result["fingerprint"] = _fingerprint(result)

    if (
        attribution_bound_lineage,
        counterfactual_causal_authorization,
        validation_bundle,
    ) != originals:
        raise G16AttributionBoundCausalAuthorizationError(
            "causal lineage authorization mutated an input artifact"
        )
    return result


def build_gate(**kwargs: Any) -> dict[str, Any]:
    result = _build_gate(**kwargs)
    validate_gate(
        result,
        bound_validator=kwargs.get("bound_validator", _default_validate_bound),
        causal_validator=kwargs.get("causal_validator", _default_validate_legacy),
    )
    return result


def validate_gate(
    value: Mapping[str, Any],
    *,
    bound_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_validate_bound,
    causal_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_validate_legacy,
) -> None:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or observed != _fingerprint(candidate):
        raise G16AttributionBoundCausalAuthorizationError(
            "gate schema or fingerprint mismatch"
        )
    if candidate.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise G16AttributionBoundCausalAuthorizationError("gate is not ready")
    if candidate.get("authority") != AUTHORITY:
        raise G16AttributionBoundCausalAuthorizationError("gate authority mismatch")
    _controls(candidate, label="attribution-bound G16 causal gate")
    if candidate.get("g16_posterior_bound_to_attribution_scored_g15_lessons") is not True:
        raise G16AttributionBoundCausalAuthorizationError(
            "G16 posterior is not bound to attribution-scored G15 lessons"
        )
    if candidate.get("next_permitted_stage") != NEXT_STAGE:
        raise G16AttributionBoundCausalAuthorizationError(
            "gate next stage mismatch"
        )

    bound = candidate.get("attribution_bound_lineage")
    legacy = candidate.get("counterfactual_causal_authorization")
    bundle = candidate.get("validation_bundle")
    if not isinstance(bound, Mapping) or not isinstance(legacy, Mapping) or not isinstance(
        bundle, Mapping
    ):
        raise G16AttributionBoundCausalAuthorizationError(
            "gate lacks recursively embedded lineage, causal, or validation evidence"
        )
    rebuilt = _build_gate(
        attribution_bound_lineage=bound,
        counterfactual_causal_authorization=legacy,
        validation_bundle=bundle,
        bound_validator=bound_validator,
        causal_validator=causal_validator,
    )
    if dict(value) != rebuilt:
        raise G16AttributionBoundCausalAuthorizationError(
            "gate differs from deterministic recursive reconstruction"
        )


def _noop(*args: Any, **kwargs: Any) -> None:
    return None


def _synthetic_fixture() -> dict[str, Any]:
    candidate_ids = ["g15_counterfactual.activity"]
    evidence = {candidate_ids[0]: "e" * 64}
    bound: dict[str, Any] = {
        "schema": BOUND_LINEAGE_SCHEMA,
        "status": "G15_ATTRIBUTION_BOUND_LESSONS_G16_LINEAGE_AUTHORIZED",
        "authority": "G15_ATTRIBUTION_BOUND_LESSONS_TO_G16_PRE_CUTOFF_LINEAGE_ONLY",
        "attribution_bound_publication_fingerprint": "p" * 64,
        "attribution_authorization_fingerprint": "u" * 64,
        "publication_completion_fingerprint": "q" * 64,
        "counterfactual_attribution_fingerprint": "a" * 64,
        "counterfactual_lesson_gate_fingerprint": "l" * 64,
        "legacy_lineage_fingerprint": "x" * 64,
        "blind_score_fingerprint": "b" * 64,
        "refined_score_fingerprint": "r" * 64,
        "comparison_fingerprint": "c" * 64,
        "g15_adjudication_fingerprint": "j" * 64,
        "g16_registry_fingerprint": "g" * 64,
        "g16_plan_fingerprint": "n" * 64,
        "candidate_count": 1,
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
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
    }
    bound["fingerprint"] = _fingerprint(bound)

    legacy: dict[str, Any] = {
        "schema": LEGACY_CAUSAL_SCHEMA,
        "status": "G16_COUNTERFACTUAL_CAUSAL_AUTHORIZED",
        "authority": "EXACT_G15_COUNTERFACTUAL_LINEAGE_TO_G16_PRE_CUTOFF_CAUSAL_ONLY",
        "counterfactual_lineage_gate_fingerprint": bound["legacy_lineage_fingerprint"],
        "counterfactual_lesson_gate_fingerprint": bound[
            "counterfactual_lesson_gate_fingerprint"
        ],
        "counterfactual_attribution_fingerprint": bound[
            "counterfactual_attribution_fingerprint"
        ],
        "g15_publication_fingerprint": bound["publication_completion_fingerprint"],
        "g15_adjudication_fingerprint": bound["g15_adjudication_fingerprint"],
        "g16_registry_fingerprint": bound["g16_registry_fingerprint"],
        "g16_plan_fingerprint": bound["g16_plan_fingerprint"],
        "prepared_causal_authorization_fingerprint": "h" * 64,
        "prepared_replay_gate_fingerprint": "i" * 64,
        "replay_fingerprint": "k" * 64,
        "manifest_fingerprint": "m" * 64,
        "prepared_corpus_fingerprint": "o" * 64,
        "blind_prior_fingerprint": "d" * 64,
        "authorization_stream_fingerprint": "s" * 64,
        "posterior_stream_fingerprint": "t" * 64,
        "g16_blind_forecast_fingerprint": "v" * 64,
        "g16_blind_safe_state_fingerprint": "w" * 64,
        "candidate_count": 1,
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_observed_in_posterior_attribution": candidate_ids,
        "all_stand_down_days": [],
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    legacy["fingerprint"] = _fingerprint(legacy)

    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "bound_lineage_validation": {},
        "legacy_causal_validation": {},
    }
    bundle["fingerprint"] = _fingerprint(bundle)
    return {
        "attribution_bound_lineage": bound,
        "counterfactual_causal_authorization": legacy,
        "validation_bundle": bundle,
        "bound_validator": _noop,
        "causal_validator": _noop,
    }


def selftest() -> int:
    fixture = _synthetic_fixture()
    original = copy.deepcopy(fixture)
    result = build_gate(**fixture)
    assert result["status"] == READY
    assert result["g16_posterior_bound_to_attribution_scored_g15_lessons"] is True
    assert result["actual_g16_outcomes_used"] is False
    assert result["may_update_ng_brain"] is False
    assert result["blind_score_fingerprint"] != result["refined_score_fingerprint"]
    assert fixture == original

    bad = copy.deepcopy(fixture)
    bad["counterfactual_causal_authorization"]["g16_plan_fingerprint"] = "z" * 64
    bad["counterfactual_causal_authorization"].pop("fingerprint", None)
    bad["counterfactual_causal_authorization"]["fingerprint"] = _fingerprint(
        bad["counterfactual_causal_authorization"]
    )
    try:
        build_gate(**bad)
    except G16AttributionBoundCausalAuthorizationError:
        pass
    else:
        raise AssertionError("G16 causal plan substitution was not rejected")
    print("[ng_g16_attribution_bound_causal_authorization_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution-bound-lineage", type=Path)
    parser.add_argument("--counterfactual-causal-authorization", type=Path)
    parser.add_argument("--validation-bundle", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (
        args.attribution_bound_lineage,
        args.counterfactual_causal_authorization,
        args.validation_bundle,
        args.out,
    )
    if any(value is None for value in required):
        parser.error(
            "--attribution-bound-lineage, --counterfactual-causal-authorization, "
            "--validation-bundle, and --out are required"
        )
    result = build_gate(
        attribution_bound_lineage=_load(args.attribution_bound_lineage),
        counterfactual_causal_authorization=_load(
            args.counterfactual_causal_authorization
        ),
        validation_bundle=_load(args.validation_bundle),
    )
    _atomic_json(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "fingerprint": result["fingerprint"],
                "out": str(args.out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
