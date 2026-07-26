#!/usr/bin/env python3
"""Readiness v36: bind attribution-scored G15 lessons into the G16 refined curve."""
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
import ng_historical_refinement_readiness_v35 as v35

SCHEMA = "ng_historical_refinement_readiness.v36"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V35_STATUS = v35._overall_status

_BOUND_FIELDS = (
    "attribution_bound_lineage_fingerprint",
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
    "prepared_causal_authorization_fingerprint",
    "prepared_replay_gate_fingerprint",
    "replay_fingerprint",
    "manifest_fingerprint",
    "prepared_corpus_fingerprint",
    "blind_prior_fingerprint",
    "authorization_stream_fingerprint",
    "posterior_stream_fingerprint",
    "g16_blind_forecast_fingerprint",
    "candidate_count",
    "candidate_ids",
    "candidate_evidence_fingerprints",
)
_ATTRIBUTION_BOUND_CURVE = StageSpec(
    "g16_attribution_bound_curve_authorization",
    "g16_attribution_bound_curve_authorization.json",
    "ng_g16_attribution_bound_curve_authorization_gate.v1",
    "fingerprint",
    frozenset(
        {
            "G16_ATTRIBUTION_BOUND_CURVE_AUTHORIZED",
            "G16_ATTRIBUTION_BOUND_CURVE_AUTHORIZED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g16_attribution_bound_curve_authorization_gate",
    ("validate_gate",),
    "Bind the deterministic G16 curve to attribution-scored G15 lessons before curve lock.",
    required_fields=(
        "attribution_bound_causal_authorization_fingerprint",
        "counterfactual_curve_authorization_fingerprint",
        "prepared_curve_authorization_fingerprint",
        "validation_bundle_fingerprint",
        *_BOUND_FIELDS,
        "refined_curve_fingerprint",
        "g16_curve_bound_to_attribution_scored_g15_lessons",
        "lesson_proposals_brain_write_forbidden",
        "next_permitted_stage",
    ),
    pre_outcome=False,
)

_keys = [spec.key for spec in v35.STAGES]
_curve = _keys.index("g16_counterfactual_curve_authorization")
_lock = _keys.index("g16_counterfactual_curve_lock")
if _lock != _curve + 1:
    raise HistoricalRefinementReadinessError(
        "v35 curve authorization must directly precede curve lock"
    )
_BOUND_LOCK = replace(
    v35.STAGES[_lock],
    required_fields=(
        *v35.STAGES[_lock].required_fields,
        "attribution_bound_curve_authorization_fingerprint",
    ),
    pre_outcome=False,
)
STAGES = (
    *v35.STAGES[:_curve],
    replace(v35.STAGES[_curve], pre_outcome=False),
    _ATTRIBUTION_BOUND_CURVE,
    _BOUND_LOCK,
    *v35.STAGES[_lock + 1 :],
)
LINK_RULES = (
    *v35.LINK_RULES,
    (
        "g16_attribution_bound_causal_authorization",
        "fingerprint",
        _ATTRIBUTION_BOUND_CURVE.key,
        "attribution_bound_causal_authorization_fingerprint",
    ),
    (
        "g16_counterfactual_curve_authorization",
        "fingerprint",
        _ATTRIBUTION_BOUND_CURVE.key,
        "counterfactual_curve_authorization_fingerprint",
    ),
    (
        "g16_prepared_curve_authorization",
        "fingerprint",
        _ATTRIBUTION_BOUND_CURVE.key,
        "prepared_curve_authorization_fingerprint",
    ),
    *(
        (
            "g16_attribution_bound_causal_authorization",
            field,
            _ATTRIBUTION_BOUND_CURVE.key,
            field,
        )
        for field in _BOUND_FIELDS
    ),
    (
        "g16_counterfactual_curve_authorization",
        "refined_curve_fingerprint",
        _ATTRIBUTION_BOUND_CURVE.key,
        "refined_curve_fingerprint",
    ),
    (
        _ATTRIBUTION_BOUND_CURVE.key,
        "fingerprint",
        "g16_counterfactual_curve_lock",
        "attribution_bound_curve_authorization_fingerprint",
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


def _without(keys: Sequence[str]) -> list[str]:
    return [key for key in keys if key != _ATTRIBUTION_BOUND_CURVE.key]


def _overall_status(ready: list[str]) -> str:
    if len(ready) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V36"
    if "g16_counterfactual_curve_authorization" not in ready:
        return _V35_STATUS(_without(ready))
    if _ATTRIBUTION_BOUND_CURVE.key not in ready:
        return "G16_LEGACY_CURVE_READY_ATTRIBUTION_BOUND_CURVE_INCOMPLETE"
    if "g16_counterfactual_curve_lock" not in ready:
        return "G16_ATTRIBUTION_BOUND_CURVE_READY_LOCK_INCOMPLETE"
    return _V35_STATUS(_without(ready))


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
        **v35._summary_fields(_without(ready)),
        "g16_attribution_bound_curve_artifact": _ATTRIBUTION_BOUND_CURVE.filename,
        "g16_attribution_bound_curve_schema": _ATTRIBUTION_BOUND_CURVE.schema,
        "g16_legacy_counterfactual_curve_fixed_g15_outcome_only": True,
        "g16_curve_bound_to_attribution_scored_g15_lessons": (
            _ATTRIBUTION_BOUND_CURVE.key in ready_set
        ),
        "g16_outcomes_unavailable_during_curve_authorization": True,
        "g16_curve_lock_blocked_until_attribution_bound_curve": True,
        "g16_curve_lock_opened_after_attribution_bound_curve": (
            "g16_counterfactual_curve_lock" in ready_set
        ),
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
        "The G16 curve must descend from the exact attribution-scored G15 lesson "
        "lineage. Fixed G15 outcomes are disclosed; G16 outcomes, scoring, "
        "ng_brain.json writes, execution, and options remain forbidden."
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
            "readiness v36 schema or fingerprint mismatch"
        )
    with _contract():
        legacy.validate_readiness_report(value)
    ready = list(value.get("ready_stages") or [])
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError("readiness v36 status mismatch")
    for field, expected in _summary_fields(ready).items():
        if value.get(field) != expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v36 {field} mismatch"
            )

    ready_set = set(ready)
    required = {
        "g16_attribution_bound_causal_authorization",
        "g16_prepared_curve_authorization",
        "g16_counterfactual_curve_authorization",
    }
    if _ATTRIBUTION_BOUND_CURVE.key in ready_set and not required.issubset(ready_set):
        raise HistoricalRefinementReadinessError(
            "attribution-bound curve bypassed causal or curve authorization"
        )
    if (
        "g16_counterfactual_curve_lock" in ready_set
        and _ATTRIBUTION_BOUND_CURVE.key not in ready_set
    ):
        raise HistoricalRefinementReadinessError(
            "curve lock bypassed attribution-bound curve"
        )

    order = list(value.get("stage_order") or [])
    index = order.index("g16_counterfactual_curve_authorization")
    if order[index : index + 3] != [
        "g16_counterfactual_curve_authorization",
        _ATTRIBUTION_BOUND_CURVE.key,
        "g16_counterfactual_curve_lock",
    ]:
        raise HistoricalRefinementReadinessError(
            "attribution-bound curve must remain between legacy curve and lock"
        )
    by_key = {spec.key: spec for spec in STAGES}
    if (
        by_key["g16_counterfactual_curve_authorization"].pre_outcome is not False
        or _ATTRIBUTION_BOUND_CURVE.pre_outcome is not False
        or by_key["g16_counterfactual_curve_lock"].pre_outcome is not False
    ):
        raise HistoricalRefinementReadinessError(
            "curve authorization and lock must disclose fixed G15 outcome use"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v35._linked_fixture_chain()
    bound = values["g16_attribution_bound_causal_authorization"]
    legacy_curve = values["g16_counterfactual_curve_authorization"]
    prepared = values["g16_prepared_curve_authorization"]
    gate = legacy._fixture_artifact(
        _ATTRIBUTION_BOUND_CURVE,
        "G16_ATTRIBUTION_BOUND_CURVE_AUTHORIZED",
    )
    gate.update(
        {
            "attribution_bound_causal_authorization_fingerprint": bound[
                "fingerprint"
            ],
            "counterfactual_curve_authorization_fingerprint": legacy_curve[
                "fingerprint"
            ],
            "prepared_curve_authorization_fingerprint": prepared["fingerprint"],
            "validation_bundle_fingerprint": "w" * 64,
            **{field: copy.deepcopy(bound[field]) for field in _BOUND_FIELDS},
            "refined_curve_fingerprint": legacy_curve[
                "refined_curve_fingerprint"
            ],
            "g16_curve_bound_to_attribution_scored_g15_lessons": True,
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
            "next_permitted_stage": (
                "LOCK_G16_REFINED_CURVE_WITH_ATTRIBUTION_BOUND_LINEAGE_BEFORE_SCORING"
            ),
        }
    )
    gate.pop("fingerprint", None)
    gate["fingerprint"] = _fingerprint(gate)
    values[_ATTRIBUTION_BOUND_CURVE.key] = gate

    incoming: dict[str, list[tuple[str, str, str]]] = {}
    for source, source_path, target, target_path in LINK_RULES:
        incoming.setdefault(target, []).append((source, source_path, target_path))
    for spec in STAGES:
        artifact = values[spec.key]
        for source, source_path, target_path in incoming.get(spec.key, []):
            legacy._path_set(
                artifact,
                target_path,
                legacy._path_get(values[source], source_path),
            )
        artifact.pop(spec.fingerprint_field, None)
        artifact[spec.fingerprint_field] = _fingerprint(artifact)
    return values


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        values = _linked_fixture_chain()
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        report = build_readiness_report(root, validator_overrides=overrides)
        assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V36"
        assert report["g16_curve_bound_to_attribution_scored_g15_lessons"] is True
    print("[ng_historical_refinement_readiness_v36] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.artifact_dir is None or args.out is None:
        parser.error("--artifact-dir and --out are required")
    report = build_readiness_report(args.artifact_dir)
    _atomic_json(args.out, report)
    print(json.dumps({"status": report["status"], "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
