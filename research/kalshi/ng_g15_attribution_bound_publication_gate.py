#!/usr/bin/env python3
"""Recursively bind exact G15 attribution authorization to fixed-outcome publication.

The existing exact-publication gate already validates immutable blind/refined forecast
files, separate outcome scorecards, their comparison, lesson adjudication, and both
canonical renders. This gate closes the remaining cross-stage gap: it proves that the
fixed-outcome publication was opened only after the exact six-factor, outcome-blind
attribution authorization and that the scorecards actually embedded in the binding are
the same separate blind/refined scorecards named by the publication completion.

The gate never changes either forecast or posterior, never updates ``ng_brain.json``,
never reads G16 outcomes, never grants execution authority, and never starts options.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from ng_g15_counterfactual_attribution import FACTORS
from ng_g15_counterfactual_attribution_gate import (
    G15_DATES,
    validate_authorization as validate_attribution_authorization,
)
from ng_g15_exact_publication_gate import (
    _validate_comparison,
    _validate_score,
    validate_completion as validate_publication_completion,
)

SCHEMA = "ng_g15_attribution_bound_publication_gate.v1"
READY = "G15_ATTRIBUTION_BOUND_PUBLICATION_VERIFIED"
READY_WITH_STAND_DOWNS = "G15_ATTRIBUTION_BOUND_PUBLICATION_VERIFIED_WITH_STAND_DOWNS"
AUTH_SCHEMA = "ng_g15_counterfactual_attribution_authorization.v1"
PUBLICATION_SCHEMA = "ng_g15_exact_publication_completion.v1"
SCORE_SCHEMA = "ng_g15_path_score.v1"
COMPARISON_SCHEMA = "ng_g15_path_comparison.v1"
AUTHORITY = "G15_ATTRIBUTION_BOUND_PUBLICATION_AUDIT_ONLY"


class AttributionBoundPublicationError(ValueError):
    """Raised when fixed-outcome G15 publication loses attribution authorization."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AttributionBoundPublicationError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise AttributionBoundPublicationError(f"artifact must be a JSON object: {path}")
    return value


def _controls(value: Mapping[str, Any], *, label: str) -> None:
    false_fields = (
        "actual_g16_outcomes_used",
        "random_shuffle_used",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "g16_outcome_access_authorized",
        "options_lane_started",
    )
    for field in false_fields:
        if field in value and value.get(field) is not False:
            raise AttributionBoundPublicationError(f"{label} must keep {field}=false")
    if value.get("cme_event_contracts_mode", "SHADOW") != "SHADOW":
        raise AttributionBoundPublicationError(
            f"{label} must keep CME event contracts SHADOW"
        )
    if value.get("brokerage_contract", "tastytrade_not_ibkr") != "tastytrade_not_ibkr":
        raise AttributionBoundPublicationError(
            f"{label} must preserve tastytrade rather than IBKR"
        )


def _validate_inputs(
    *,
    attribution_authorization: Mapping[str, Any],
    publication_completion: Mapping[str, Any],
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    auth = copy.deepcopy(dict(attribution_authorization))
    publication = copy.deepcopy(dict(publication_completion))
    blind = copy.deepcopy(dict(blind_score))
    refined = copy.deepcopy(dict(refined_score))
    compared = copy.deepcopy(dict(comparison))

    try:
        validate_attribution_authorization(auth)
        validate_publication_completion(publication)
    except Exception as error:
        raise AttributionBoundPublicationError(str(error)) from error

    if auth.get("schema") != AUTH_SCHEMA:
        raise AttributionBoundPublicationError("unexpected attribution authorization schema")
    if publication.get("schema") != PUBLICATION_SCHEMA:
        raise AttributionBoundPublicationError("unexpected publication completion schema")
    if auth.get("all_six_factors_quantified") is not True:
        raise AttributionBoundPublicationError("all six factors must be authorized before scoring")
    if tuple(auth.get("factors") or ()) != tuple(FACTORS):
        raise AttributionBoundPublicationError("attribution authorization lost canonical factors")
    if auth.get("lesson_proposals_brain_write_forbidden") is not True:
        raise AttributionBoundPublicationError(
            "lesson proposals must remain forbidden from writing ng_brain.json"
        )
    if auth.get("actual_outcomes_used") is not False:
        raise AttributionBoundPublicationError(
            "attribution authorization must remain outcome-blind"
        )
    if publication.get("actual_outcomes_used") is not True:
        raise AttributionBoundPublicationError(
            "publication completion must disclose fixed G15 outcome use"
        )

    lineage = {
        "exact_replay_completion_fingerprint": auth.get(
            "exact_replay_completion_fingerprint"
        ),
        "exact_refinement_authorization_fingerprint": auth.get(
            "refinement_authorization_fingerprint"
        ),
        "refine_stream_fingerprint": auth.get("refine_stream_fingerprint"),
    }
    publication_lineage = {
        "exact_replay_completion_fingerprint": publication.get(
            "exact_replay_completion_fingerprint"
        ),
        "exact_refinement_authorization_fingerprint": publication.get(
            "exact_refinement_authorization_fingerprint"
        ),
        "refine_stream_fingerprint": publication.get("refine_stream_fingerprint"),
    }
    if lineage != publication_lineage:
        raise AttributionBoundPublicationError(
            "publication is not bound to the exact replay/refinement stream authorized for attribution"
        )

    try:
        blind_value = _validate_score(
            blind,
            kind="blind",
            forecast_hash=str(publication.get("blind_forecast_sha256") or ""),
            actual_fingerprint=str(publication.get("actual_artifact_fingerprint") or ""),
        )
        refined_value = _validate_score(
            refined,
            kind="refined",
            forecast_hash=str(publication.get("refined_forecast_sha256") or ""),
            actual_fingerprint=str(publication.get("actual_artifact_fingerprint") or ""),
        )
        comparison_value = _validate_comparison(
            compared,
            blind_score_fp=str(blind_value.get("artifact_fingerprint") or ""),
            refined_score_fp=str(refined_value.get("artifact_fingerprint") or ""),
        )
    except Exception as error:
        raise AttributionBoundPublicationError(str(error)) from error

    expected_fingerprints = {
        "blind_score_fingerprint": blind_value.get("artifact_fingerprint"),
        "refined_score_fingerprint": refined_value.get("artifact_fingerprint"),
        "comparison_fingerprint": comparison_value.get("artifact_fingerprint"),
    }
    for field, expected in expected_fingerprints.items():
        if publication.get(field) != expected:
            raise AttributionBoundPublicationError(
                f"publication completion references a different {field}"
            )
    if blind_value.get("artifact_fingerprint") == refined_value.get("artifact_fingerprint"):
        raise AttributionBoundPublicationError(
            "blind and refined scorecards must remain separate artifacts"
        )
    if blind_value.get("forecast_kind") != "blind" or refined_value.get(
        "forecast_kind"
    ) != "refined":
        raise AttributionBoundPublicationError(
            "blind/refined scorecard identities were collapsed"
        )
    if blind_value.get("actual_artifact_fingerprint") != refined_value.get(
        "actual_artifact_fingerprint"
    ):
        raise AttributionBoundPublicationError(
            "blind and refined scorecards must use the same fixed actual substrate"
        )
    if comparison_value.get("blind_score_fingerprint") == comparison_value.get(
        "refined_score_fingerprint"
    ):
        raise AttributionBoundPublicationError(
            "comparison must retain distinct blind and refined score lineage"
        )
    _controls(auth, label="attribution authorization")
    _controls(publication, label="publication completion")
    _controls(blind_value, label="blind score")
    _controls(refined_value, label="refined score")
    _controls(comparison_value, label="score comparison")
    return auth, publication, blind_value, refined_value, comparison_value


def _build_gate(
    *,
    attribution_authorization: Mapping[str, Any],
    publication_completion: Mapping[str, Any],
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    auth, publication, blind, refined, compared = _validate_inputs(
        attribution_authorization=attribution_authorization,
        publication_completion=publication_completion,
        blind_score=blind_score,
        refined_score=refined_score,
        comparison=comparison,
    )
    stand_down_days = sorted(
        set(str(day) for day in auth.get("stand_down_days") or [])
        | set(str(day) for day in publication.get("stand_down_days") or [])
    )
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": READY_WITH_STAND_DOWNS if stand_down_days else READY,
        "authority": AUTHORITY,
        "attribution_authorization_fingerprint": auth[
            "authorization_fingerprint"
        ],
        "publication_completion_fingerprint": publication[
            "completion_fingerprint"
        ],
        "exact_replay_completion_fingerprint": auth[
            "exact_replay_completion_fingerprint"
        ],
        "exact_refinement_authorization_fingerprint": auth[
            "refinement_authorization_fingerprint"
        ],
        "attribution_fingerprint": auth["attribution_fingerprint"],
        "refine_stream_fingerprint": auth["refine_stream_fingerprint"],
        "blind_forecast_sha256": publication["blind_forecast_sha256"],
        "refined_forecast_sha256": publication["refined_forecast_sha256"],
        "actual_artifact_fingerprint": publication[
            "actual_artifact_fingerprint"
        ],
        "blind_score_fingerprint": blind["artifact_fingerprint"],
        "refined_score_fingerprint": refined["artifact_fingerprint"],
        "comparison_fingerprint": compared["artifact_fingerprint"],
        "n_days": len(G15_DATES),
        "days": list(G15_DATES),
        "factors": list(FACTORS),
        "stand_down_days": stand_down_days,
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
        "attribution_authorization": copy.deepcopy(auth),
        "publication_completion": copy.deepcopy(publication),
        "blind_score": copy.deepcopy(blind),
        "refined_score": copy.deepcopy(refined),
        "comparison": copy.deepcopy(compared),
        "note": (
            "Fixed G15 outcomes were opened only after exact six-factor attribution "
            "authorization. Blind and refined paths were scored as separate immutable "
            "artifacts against one fixed actual substrate; lesson proposals remain "
            "non-writing candidates for pre-cutoff G16 SHADOW adjudication only."
        ),
    }
    result["fingerprint"] = _fingerprint(result)
    return result


def build_gate(
    *,
    attribution_authorization: Mapping[str, Any],
    publication_completion: Mapping[str, Any],
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            attribution_authorization,
            publication_completion,
            blind_score,
            refined_score,
            comparison,
        )
    )
    result = _build_gate(
        attribution_authorization=attribution_authorization,
        publication_completion=publication_completion,
        blind_score=blind_score,
        refined_score=refined_score,
        comparison=comparison,
    )
    if (
        attribution_authorization,
        publication_completion,
        blind_score,
        refined_score,
        comparison,
    ) != originals:
        raise AttributionBoundPublicationError("gate mutated an input artifact")
    validate_gate(result)
    return result


def validate_gate(value: Mapping[str, Any]) -> None:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fingerprint(checked):
        raise AttributionBoundPublicationError("gate schema or fingerprint mismatch")
    if checked.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise AttributionBoundPublicationError("gate is not ready")
    if checked.get("authority") != AUTHORITY:
        raise AttributionBoundPublicationError("gate authority mismatch")
    _controls(checked, label="attribution-bound publication gate")
    for field in (
        "attribution_authorization_bound_to_publication",
        "publication_opened_after_attribution_authorization",
        "separate_blind_refined_scores_verified",
        "score_artifacts_distinct",
        "score_actual_substrate_shared",
        "all_six_factors_authorized_before_scoring",
        "lesson_proposals_brain_write_forbidden",
        "blind_forecasts_immutable",
        "one_signal_authority_preserved",
        "actual_g15_outcomes_used",
    ):
        if checked.get(field) is not True:
            raise AttributionBoundPublicationError(f"mandatory gate field mismatch: {field}")
    if tuple(checked.get("factors") or ()) != tuple(FACTORS):
        raise AttributionBoundPublicationError("gate lost the canonical six-factor set")
    if checked.get("days") != list(G15_DATES) or int(checked.get("n_days") or 0) != len(
        G15_DATES
    ):
        raise AttributionBoundPublicationError("gate lost canonical G15 day coverage")
    if checked.get("blind_score_fingerprint") == checked.get(
        "refined_score_fingerprint"
    ):
        raise AttributionBoundPublicationError("gate collapsed blind/refined score lineage")
    embedded = (
        checked.get("attribution_authorization"),
        checked.get("publication_completion"),
        checked.get("blind_score"),
        checked.get("refined_score"),
        checked.get("comparison"),
    )
    if not all(isinstance(item, Mapping) for item in embedded):
        raise AttributionBoundPublicationError(
            "gate lacks recursively embedded authorization/publication/score evidence"
        )
    rebuilt = _build_gate(
        attribution_authorization=embedded[0],
        publication_completion=embedded[1],
        blind_score=embedded[2],
        refined_score=embedded[3],
        comparison=embedded[4],
    )
    if dict(value) != rebuilt:
        raise AttributionBoundPublicationError(
            "gate differs from deterministic recursive reconstruction"
        )


def _synthetic_fixture(tmp: Path) -> dict[str, Any]:
    import ng_g15_counterfactual_attribution_gate as attribution_gate
    import ng_g15_exact_publication_gate as publication_gate

    fixture = publication_gate._fixture(tmp)
    publication = publication_gate.build_completion(
        authorization=fixture["authorization"],
        blind=fixture["blind"],
        refined=fixture["refined"],
        actual=fixture["actual"],
        blind_score=fixture["blind_score"],
        refined_score=fixture["refined_score"],
        comparison=fixture["comparison"],
        adjudication=fixture["adjudication"],
        blind_rt=fixture["blind_rt"],
        refined_rt=fixture["refined_rt"],
        blind_bytes=fixture["blind_bytes"],
        refined_bytes=fixture["refined_bytes"],
        blind_png=fixture["blind_png"],
        refined_png=fixture["refined_png"],
    )
    refinement = fixture["authorization"]
    authorization = {
        "schema": AUTH_SCHEMA,
        "market": "NG",
        "group": 15,
        "status": attribution_gate.READY,
        "authority": "G15_COUNTERFACTUAL_ATTRIBUTION_AUTHORIZATION_ONLY",
        "exact_replay_completion_fingerprint": refinement[
            "exact_replay_completion_fingerprint"
        ],
        "pipeline_fingerprint": refinement["pipeline_fingerprint"],
        "refinement_authorization_fingerprint": refinement[
            "authorization_fingerprint"
        ],
        "attribution_fingerprint": "a" * 64,
        "replay_fingerprint": refinement["replay_fingerprint"],
        "anchor_fingerprint": refinement["anchor_fingerprint"],
        "refine_stream_fingerprint": refinement["refine_stream_fingerprint"],
        "n_states": len(G15_DATES),
        "n_days": len(G15_DATES),
        "factors": list(FACTORS),
        "factor_summary_fingerprint": "f" * 64,
        "per_day_fingerprint": "d" * 64,
        "rows_fingerprint": "r" * 64,
        "lesson_proposals_fingerprint": "l" * 64,
        "lesson_proposal_count": 1,
        "stand_down_days": [],
        "all_six_factors_quantified": True,
        "lesson_proposals_brain_write_forbidden": True,
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
        "next_permitted_stage": (
            "LOCK_G15_REFINED_FORECAST_AND_SCORE_BLIND_REFINED_SEPARATELY"
        ),
    }
    authorization["authorization_fingerprint"] = _fingerprint(authorization)
    return {
        "attribution_authorization": authorization,
        "publication_completion": publication,
        "blind_score": fixture["blind_score"],
        "refined_score": fixture["refined_score"],
        "comparison": fixture["comparison"],
    }


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        fixture = _synthetic_fixture(Path(directory))
        result = build_gate(**fixture)
        assert result["status"] == READY
        assert result["separate_blind_refined_scores_verified"] is True
        assert result["lesson_proposals_brain_write_forbidden"] is True
        validate_gate(result)

        tampered = copy.deepcopy(result)
        tampered["may_update_ng_brain"] = True
        tampered.pop("fingerprint", None)
        tampered["fingerprint"] = _fingerprint(tampered)
        try:
            validate_gate(tampered)
        except AttributionBoundPublicationError:
            pass
        else:
            raise AssertionError("brain-write escalation was not rejected")
    print("[ng_g15_attribution_bound_publication_gate] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution-authorization", type=Path)
    parser.add_argument("--publication", type=Path)
    parser.add_argument("--blind-score", type=Path)
    parser.add_argument("--refined-score", type=Path)
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    required = (
        args.attribution_authorization,
        args.publication,
        args.blind_score,
        args.refined_score,
        args.comparison,
        args.out,
    )
    if any(value is None for value in required):
        parser.error(
            "--attribution-authorization, --publication, --blind-score, "
            "--refined-score, --comparison, and --out are required"
        )
    result = build_gate(
        attribution_authorization=_load(args.attribution_authorization),
        publication_completion=_load(args.publication),
        blind_score=_load(args.blind_score),
        refined_score=_load(args.refined_score),
        comparison=_load(args.comparison),
    )
    _atomic_json(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "blind_score": result["blind_score_fingerprint"],
                "refined_score": result["refined_score_fingerprint"],
                "fingerprint": result["fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
