#!/usr/bin/env python3
"""Recursively bind the immutable G16 curve lock to attribution-scored G15 lessons.

The legacy counterfactual lock proves that exact blind/refined bytes were locked before
G16 outcomes opened.  The attribution-bound curve authorization proves that the same
curve descends from six-factor-authorized, separately scored G15 lessons.  This gate
requires both exact artifacts together before fixed G16 scoring may begin.
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

SCHEMA = "ng_g16_attribution_bound_curve_lock_gate.v1"
BUNDLE_SCHEMA = "ng_g16_attribution_bound_curve_lock_validation_bundle.v1"
AUTHORITY = "G15_ATTRIBUTION_BOUND_LESSONS_TO_IMMUTABLE_G16_CURVE_LOCK_ONLY"
READY = "G16_ATTRIBUTION_BOUND_CURVE_LOCKED"
READY_WITH_STAND_DOWNS = "G16_ATTRIBUTION_BOUND_CURVE_LOCKED_WITH_STAND_DOWNS"
NEXT_STAGE = "FIXED_G16_BLIND_REFINED_SCORING_WITH_ATTRIBUTION_BOUND_LINEAGE"
BOUND_CURVE_SCHEMA = "ng_g16_attribution_bound_curve_authorization_gate.v1"
LEGACY_LOCK_SCHEMA = "ng_g16_counterfactual_curve_lock.v1"


class G16AttributionBoundCurveLockError(ValueError):
    """Raised when the immutable G16 lock diverges from attribution-scored lineage."""


def _fingerprint(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_fp = _fingerprint


def _signed(value: Mapping[str, Any], field: str, label: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    observed = result.pop(field, None)
    if not isinstance(observed, str) or observed != _fingerprint(result):
        raise G16AttributionBoundCurveLockError(f"{label} {field} mismatch")
    result[field] = observed
    return result


def _controls(value: Mapping[str, Any], label: str) -> None:
    for field in (
        "actual_g16_outcomes_used",
        "random_shuffle_used",
        "curve_mutation_authorized",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if field in value and value.get(field) is not False:
            raise G16AttributionBoundCurveLockError(f"{label} must keep {field}=false")
    for field in (
        "actual_g15_outcomes_used",
        "one_signal_authority_preserved",
        "blind_forecasts_immutable",
    ):
        if value.get(field) is not True:
            raise G16AttributionBoundCurveLockError(f"{label} must keep {field}=true")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16AttributionBoundCurveLockError(
            f"{label} must keep CME event contracts SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16AttributionBoundCurveLockError(
            f"{label} must preserve tastytrade rather than IBKR"
        )


def _decode_bytes(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_bytes(item) for item in value]
    if not isinstance(value, Mapping):
        return copy.deepcopy(value)
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key.endswith("_base64"):
            target = key[: -len("_base64")]
            try:
                result[target] = base64.b64decode(str(item).encode("ascii"), validate=True)
            except (ValueError, UnicodeEncodeError, binascii.Error) as error:
                raise G16AttributionBoundCurveLockError(
                    f"invalid base64 validation field {key}"
                ) from error
        else:
            result[str(key)] = _decode_bytes(item)
    return result


def _normalize_bundle(value: Mapping[str, Any]) -> dict[str, Any]:
    bundle = copy.deepcopy(dict(value))
    if bundle.get("schema") != BUNDLE_SCHEMA:
        raise G16AttributionBoundCurveLockError("validation bundle schema mismatch")
    observed = bundle.pop("fingerprint", None)
    if observed != _fingerprint(bundle):
        raise G16AttributionBoundCurveLockError("validation bundle fingerprint mismatch")
    bundle["fingerprint"] = observed
    for field in ("bound_curve_validation", "legacy_lock_validation"):
        if not isinstance(bundle.get(field), Mapping):
            raise G16AttributionBoundCurveLockError(
                f"validation bundle lacks {field} mapping"
            )
    return bundle


def _default_bound_validator(value: Mapping[str, Any], kwargs: Mapping[str, Any]) -> None:
    from ng_g16_attribution_bound_curve_authorization_gate import validate_gate

    validate_gate(value, **dict(kwargs))


def _default_lock_validator(value: Mapping[str, Any], kwargs: Mapping[str, Any]) -> None:
    from ng_g16_counterfactual_publication_gate import validate_curve_lock

    validate_curve_lock(value, **dict(_decode_bytes(kwargs)))


def _candidate_lineage(
    bound: Mapping[str, Any], lock: Mapping[str, Any]
) -> tuple[list[str], dict[str, str], list[str], list[str]]:
    candidate_ids = [str(item) for item in bound.get("candidate_ids") or []]
    if (
        not candidate_ids
        or candidate_ids != sorted(candidate_ids)
        or len(candidate_ids) != len(set(candidate_ids))
    ):
        raise G16AttributionBoundCurveLockError(
            "candidate ids must be non-empty, sorted, and unique"
        )
    if int(bound.get("candidate_count") or 0) != len(candidate_ids):
        raise G16AttributionBoundCurveLockError("candidate_count mismatch")
    if [str(item) for item in lock.get("candidate_ids") or []] != candidate_ids:
        raise G16AttributionBoundCurveLockError(
            "legacy lock candidate registry differs from attribution-bound curve"
        )
    evidence = {
        str(key): str(item)
        for key, item in dict(bound.get("candidate_evidence_fingerprints") or {}).items()
    }
    if sorted(evidence) != candidate_ids or any(not item for item in evidence.values()):
        raise G16AttributionBoundCurveLockError("candidate evidence is incomplete")
    lock_evidence = {
        str(key): str(item)
        for key, item in dict(lock.get("candidate_evidence_fingerprints") or {}).items()
    }
    if lock_evidence != evidence:
        raise G16AttributionBoundCurveLockError(
            "legacy lock candidate evidence differs from attribution-bound curve"
        )
    used = sorted({str(item) for item in bound.get("candidate_ids_used_by_curve") or []})
    if sorted({str(item) for item in lock.get("candidate_ids_used_by_curve") or []}) != used:
        raise G16AttributionBoundCurveLockError(
            "legacy lock curve-used candidates differ from attribution-bound curve"
        )
    if not set(used).issubset(set(candidate_ids)):
        raise G16AttributionBoundCurveLockError("curve-used candidates are unregistered")
    stand_downs = sorted(
        {str(item) for item in bound.get("stand_down_days") or []}
        | {str(item) for item in lock.get("stand_down_days") or []}
    )
    return candidate_ids, evidence, used, stand_downs


def _cross_checks(bound: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    legacy_curve = dict(bound.get("counterfactual_curve_authorization") or {})
    links = {
        "legacy curve authorization": (
            bound.get("counterfactual_curve_authorization_fingerprint"),
            lock.get("counterfactual_curve_authorization_fingerprint"),
        ),
        "legacy causal authorization": (
            legacy_curve.get("counterfactual_causal_authorization_fingerprint"),
            lock.get("counterfactual_causal_authorization_fingerprint"),
        ),
        "prepared curve authorization": (
            bound.get("prepared_curve_authorization_fingerprint"),
            lock.get("prepared_curve_authorization_fingerprint"),
        ),
        "historical replay": (bound.get("replay_fingerprint"), lock.get("replay_fingerprint")),
        "manifest": (bound.get("manifest_fingerprint"), lock.get("manifest_fingerprint")),
        "prepared corpus": (
            bound.get("prepared_corpus_fingerprint"),
            lock.get("prepared_corpus_fingerprint"),
        ),
        "blind prior": (
            bound.get("blind_prior_fingerprint"),
            lock.get("blind_prior_fingerprint"),
        ),
        "G16 plan": (bound.get("g16_plan_fingerprint"), lock.get("plan_fingerprint")),
        "authorization stream": (
            bound.get("authorization_stream_fingerprint"),
            lock.get("authorization_stream_fingerprint"),
        ),
        "posterior stream": (
            bound.get("posterior_stream_fingerprint"),
            lock.get("posterior_stream_fingerprint"),
        ),
        "refined curve": (
            bound.get("refined_curve_fingerprint"),
            lock.get("refined_curve_fingerprint"),
        ),
    }
    for label, values in links.items():
        normalized = [str(item or "") for item in values]
        if any(not item for item in normalized) or len(set(normalized)) != 1:
            raise G16AttributionBoundCurveLockError(f"{label} lineage mismatch")


def _build_gate(
    *,
    attribution_bound_curve_authorization: Mapping[str, Any],
    counterfactual_curve_lock: Mapping[str, Any],
    validation_bundle: Mapping[str, Any],
    bound_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_bound_validator,
    lock_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_lock_validator,
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (attribution_bound_curve_authorization, counterfactual_curve_lock, validation_bundle)
    )
    bundle = _normalize_bundle(validation_bundle)
    try:
        bound_validator(
            attribution_bound_curve_authorization,
            dict(bundle["bound_curve_validation"]),
        )
        lock_validator(
            counterfactual_curve_lock,
            dict(bundle["legacy_lock_validation"]),
        )
    except Exception as error:
        raise G16AttributionBoundCurveLockError(str(error)) from error

    bound = _signed(
        attribution_bound_curve_authorization,
        "fingerprint",
        "attribution-bound curve authorization",
    )
    lock = _signed(counterfactual_curve_lock, "lock_fingerprint", "counterfactual curve lock")
    if bound.get("schema") != BOUND_CURVE_SCHEMA or bound.get("status") not in {
        "G16_ATTRIBUTION_BOUND_CURVE_AUTHORIZED",
        "G16_ATTRIBUTION_BOUND_CURVE_AUTHORIZED_WITH_STAND_DOWNS",
    }:
        raise G16AttributionBoundCurveLockError(
            "attribution-bound curve authorization is not ready"
        )
    if bound.get("next_permitted_stage") != (
        "LOCK_G16_REFINED_CURVE_WITH_ATTRIBUTION_BOUND_LINEAGE_BEFORE_SCORING"
    ):
        raise G16AttributionBoundCurveLockError(
            "attribution-bound curve authorization does not permit locking"
        )
    if lock.get("schema") != LEGACY_LOCK_SCHEMA or lock.get("status") != (
        "EXACT_G16_COUNTERFACTUAL_CURVE_LOCKED"
    ):
        raise G16AttributionBoundCurveLockError("counterfactual curve lock is not ready")
    if lock.get("next_permitted_stage") != (
        "FIXED_G16_BLIND_REFINED_SCORING_WITH_COUNTERFACTUAL_LINEAGE"
    ):
        raise G16AttributionBoundCurveLockError("counterfactual curve lock next stage mismatch")
    _controls(bound, "attribution-bound curve authorization")
    _controls(lock, "counterfactual curve lock")
    for field in (
        "all_six_factors_authorized_before_scoring",
        "separate_blind_refined_scores_verified",
        "scored_lessons_bound_to_attribution_publication",
        "g16_plan_bound_to_validated_g15_lessons",
        "g16_posterior_bound_to_attribution_scored_g15_lessons",
        "g16_curve_bound_to_attribution_scored_g15_lessons",
        "lesson_proposals_brain_write_forbidden",
    ):
        if bound.get(field) is not True:
            raise G16AttributionBoundCurveLockError(
                f"attribution-bound curve authorization lost {field}"
            )
    for field in (
        "fixed_scoring_may_begin",
        "curve_locked_before_fixed_scoring",
        "counterfactual_lineage_locked_before_fixed_scoring",
    ):
        if lock.get(field) is not True:
            raise G16AttributionBoundCurveLockError(f"legacy lock lost {field}")

    _cross_checks(bound, lock)
    candidate_ids, evidence, used, stand_downs = _candidate_lineage(bound, lock)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": READY_WITH_STAND_DOWNS if stand_downs else READY,
        "authority": AUTHORITY,
        "attribution_bound_curve_authorization_fingerprint": bound["fingerprint"],
        "counterfactual_curve_lock_fingerprint": lock["lock_fingerprint"],
        "counterfactual_curve_authorization_fingerprint": bound[
            "counterfactual_curve_authorization_fingerprint"
        ],
        "attribution_bound_causal_authorization_fingerprint": bound[
            "attribution_bound_causal_authorization_fingerprint"
        ],
        "prepared_curve_authorization_fingerprint": bound[
            "prepared_curve_authorization_fingerprint"
        ],
        "prepared_curve_lock_fingerprint": lock["prepared_curve_lock_fingerprint"],
        "validation_bundle_fingerprint": bundle["fingerprint"],
        "attribution_bound_lineage_fingerprint": bound[
            "attribution_bound_lineage_fingerprint"
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
        "prepared_causal_authorization_fingerprint": bound[
            "prepared_causal_authorization_fingerprint"
        ],
        "prepared_replay_gate_fingerprint": bound[
            "prepared_replay_gate_fingerprint"
        ],
        "replay_fingerprint": bound["replay_fingerprint"],
        "manifest_fingerprint": bound["manifest_fingerprint"],
        "prepared_corpus_fingerprint": bound["prepared_corpus_fingerprint"],
        "blind_prior_fingerprint": bound["blind_prior_fingerprint"],
        "authorization_stream_fingerprint": bound[
            "authorization_stream_fingerprint"
        ],
        "posterior_stream_fingerprint": bound["posterior_stream_fingerprint"],
        "g16_blind_forecast_fingerprint": bound[
            "g16_blind_forecast_fingerprint"
        ],
        "refined_curve_fingerprint": bound["refined_curve_fingerprint"],
        "blind_forecast_sha256": lock.get("blind_forecast_sha256"),
        "refined_forecast_sha256": lock.get("refined_forecast_sha256"),
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_used_by_curve": used,
        "stand_down_days": stand_downs,
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
        "next_permitted_stage": NEXT_STAGE,
        "attribution_bound_curve_authorization": copy.deepcopy(bound),
        "counterfactual_curve_lock": copy.deepcopy(lock),
        "validation_bundle": copy.deepcopy(bundle),
        "note": (
            "The exact immutable G16 curve lock is recursively bound to six-factor-"
            "authorized, separately scored G15 lessons before any G16 outcome access."
        ),
    }
    result["fingerprint"] = _fingerprint(result)
    if (
        attribution_bound_curve_authorization,
        counterfactual_curve_lock,
        validation_bundle,
    ) != originals:
        raise G16AttributionBoundCurveLockError("curve-lock gate mutated an input artifact")
    return result


def build_gate(**kwargs: Any) -> dict[str, Any]:
    result = _build_gate(**kwargs)
    validate_gate(
        result,
        bound_validator=kwargs.get("bound_validator", _default_bound_validator),
        lock_validator=kwargs.get("lock_validator", _default_lock_validator),
    )
    return result


def validate_gate(
    value: Mapping[str, Any],
    *,
    bound_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_bound_validator,
    lock_validator: Callable[[Mapping[str, Any], Mapping[str, Any]], None] = _default_lock_validator,
) -> None:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or observed != _fingerprint(candidate):
        raise G16AttributionBoundCurveLockError("gate schema or fingerprint mismatch")
    if candidate.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise G16AttributionBoundCurveLockError("gate is not ready")
    if candidate.get("authority") != AUTHORITY:
        raise G16AttributionBoundCurveLockError("gate authority mismatch")
    _controls(candidate, "attribution-bound curve-lock gate")
    if candidate.get("fixed_scoring_may_begin") is not True:
        raise G16AttributionBoundCurveLockError("fixed scoring may not begin")
    if candidate.get("g16_curve_lock_bound_to_attribution_scored_g15_lessons") is not True:
        raise G16AttributionBoundCurveLockError(
            "G16 curve lock is not bound to attribution-scored G15 lessons"
        )
    if candidate.get("next_permitted_stage") != NEXT_STAGE:
        raise G16AttributionBoundCurveLockError("gate next stage mismatch")
    bound = candidate.get("attribution_bound_curve_authorization")
    lock = candidate.get("counterfactual_curve_lock")
    bundle = candidate.get("validation_bundle")
    if not all(isinstance(item, Mapping) for item in (bound, lock, bundle)):
        raise G16AttributionBoundCurveLockError(
            "gate lacks recursively embedded authorization, lock, or validation evidence"
        )
    rebuilt = _build_gate(
        attribution_bound_curve_authorization=bound,
        counterfactual_curve_lock=lock,
        validation_bundle=bundle,
        bound_validator=bound_validator,
        lock_validator=lock_validator,
    )
    if dict(value) != rebuilt:
        raise G16AttributionBoundCurveLockError(
            "gate differs from deterministic recursive reconstruction"
        )


def _noop(*args: Any, **kwargs: Any) -> None:
    return None


def _synthetic_fixture() -> dict[str, Any]:
    from ng_g16_attribution_bound_curve_authorization_gate import _synthetic_fixture as curve_fixture

    curve_source = curve_fixture()
    bound_curve_validator = curve_source.pop("bound_validator")
    legacy_curve_validator = curve_source.pop("legacy_curve_validator")
    from ng_g16_attribution_bound_curve_authorization_gate import build_gate as build_curve_gate

    bound_curve = build_curve_gate(
        **curve_source,
        bound_validator=bound_curve_validator,
        legacy_curve_validator=legacy_curve_validator,
    )
    legacy_curve = bound_curve["counterfactual_curve_authorization"]
    prepared = bound_curve["prepared_curve_authorization"]
    lock: dict[str, Any] = {
        "schema": LEGACY_LOCK_SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": "EXACT_G16_COUNTERFACTUAL_CURVE_LOCKED",
        "authority": "EXACT_G15_COUNTERFACTUAL_LINEAGE_TO_G16_CURVE_LOCK_BEFORE_FIXED_SCORING",
        "counterfactual_curve_authorization_fingerprint": legacy_curve["fingerprint"],
        "counterfactual_causal_authorization_fingerprint": legacy_curve[
            "counterfactual_causal_authorization_fingerprint"
        ],
        "prepared_curve_authorization_fingerprint": prepared["fingerprint"],
        "prepared_curve_lock_fingerprint": "w" * 64,
        "replay_fingerprint": bound_curve["replay_fingerprint"],
        "manifest_fingerprint": bound_curve["manifest_fingerprint"],
        "prepared_corpus_fingerprint": bound_curve["prepared_corpus_fingerprint"],
        "blind_prior_fingerprint": bound_curve["blind_prior_fingerprint"],
        "plan_fingerprint": bound_curve["g16_plan_fingerprint"],
        "authorization_stream_fingerprint": bound_curve[
            "authorization_stream_fingerprint"
        ],
        "posterior_stream_fingerprint": bound_curve["posterior_stream_fingerprint"],
        "blind_forecast_sha256": "1" * 64,
        "refined_curve_fingerprint": bound_curve["refined_curve_fingerprint"],
        "refined_forecast_sha256": "2" * 64,
        "candidate_ids": copy.deepcopy(bound_curve["candidate_ids"]),
        "candidate_evidence_fingerprints": copy.deepcopy(
            bound_curve["candidate_evidence_fingerprints"]
        ),
        "candidate_ids_used_by_curve": copy.deepcopy(
            bound_curve["candidate_ids_used_by_curve"]
        ),
        "stand_down_days": [],
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "fixed_scoring_may_begin": True,
        "curve_locked_before_fixed_scoring": True,
        "counterfactual_lineage_locked_before_fixed_scoring": True,
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
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "FIXED_G16_BLIND_REFINED_SCORING_WITH_COUNTERFACTUAL_LINEAGE",
    }
    lock["lock_fingerprint"] = _fingerprint(lock)
    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "bound_curve_validation": {},
        "legacy_lock_validation": {},
    }
    bundle["fingerprint"] = _fingerprint(bundle)
    return {
        "attribution_bound_curve_authorization": bound_curve,
        "counterfactual_curve_lock": lock,
        "validation_bundle": bundle,
        "bound_validator": _noop,
        "lock_validator": _noop,
    }


def selftest() -> int:
    fixture = _synthetic_fixture()
    result = build_gate(**fixture)
    assert result["status"] == READY
    assert result["g16_curve_lock_bound_to_attribution_scored_g15_lessons"] is True
    assert result["actual_g16_outcomes_used"] is False
    assert result["may_update_ng_brain"] is False
    validate_gate(result, bound_validator=_noop, lock_validator=_noop)
    print("[ng_g16_attribution_bound_curve_lock_gate] selftest PASS")
    return 0


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G16AttributionBoundCurveLockError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise G16AttributionBoundCurveLockError(f"artifact must be an object: {path}")
    return value


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution-bound-curve", type=Path)
    parser.add_argument("--counterfactual-curve-lock", type=Path)
    parser.add_argument("--validation-bundle", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(
        value is None
        for value in (
            args.attribution_bound_curve,
            args.counterfactual_curve_lock,
            args.validation_bundle,
            args.out,
        )
    ):
        parser.error(
            "--attribution-bound-curve, --counterfactual-curve-lock, "
            "--validation-bundle, and --out are required"
        )
    result = build_gate(
        attribution_bound_curve_authorization=_load(args.attribution_bound_curve),
        counterfactual_curve_lock=_load(args.counterfactual_curve_lock),
        validation_bundle=_load(args.validation_bundle),
    )
    _atomic(args.out, result)
    print(json.dumps({"status": result["status"], "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
