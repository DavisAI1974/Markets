#!/usr/bin/env python3
"""Canonical readiness v35 binding attribution-scored G15 lessons into G16 causal output.

Readiness v34 requires the G16 plan and candidate registry to descend from exact
six-factor-authorized G15 publication and separate blind/refined scoring before any
G16 corpus work starts. V35 additionally requires the completed pre-cutoff G16 causal
posterior authorization to remain recursively bound to that same attribution-scored
lineage before any refined-curve authorization may proceed.
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
import ng_historical_refinement_readiness_v34 as v34

SCHEMA = "ng_historical_refinement_readiness.v35"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V34_OVERALL_STATUS = v34._overall_status

_ATTRIBUTION_BOUND_CAUSAL = StageSpec(
    "g16_attribution_bound_causal_authorization",
    "g16_attribution_bound_causal_authorization.json",
    "ng_g16_attribution_bound_causal_authorization_gate.v1",
    "fingerprint",
    frozenset(
        {
            "G16_ATTRIBUTION_BOUND_CAUSAL_AUTHORIZED",
            "G16_ATTRIBUTION_BOUND_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g16_attribution_bound_causal_authorization_gate",
    ("validate_gate",),
    (
        "Recursively bind the exact pre-cutoff G16 posterior to the attribution-scored "
        "G15 lesson lineage before any G16 refined-curve authorization."
    ),
    required_fields=(
        "attribution_bound_lineage_fingerprint",
        "legacy_counterfactual_causal_authorization_fingerprint",
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
        "posterior_stream_fingerprint",
        "candidate_count",
        "candidate_ids",
        "g16_posterior_bound_to_attribution_scored_g15_lessons",
        "lesson_proposals_brain_write_forbidden",
        "next_permitted_stage",
    ),
    pre_outcome=False,
)

_STAGE_KEYS = [spec.key for spec in v34.STAGES]
_LEGACY_CAUSAL_INDEX = _STAGE_KEYS.index("g16_counterfactual_causal_authorization")
_PREPARED_CURVE_INDEX = _STAGE_KEYS.index("g16_prepared_curve_authorization")
if _PREPARED_CURVE_INDEX != _LEGACY_CAUSAL_INDEX + 1:
    raise HistoricalRefinementReadinessError(
        "readiness v34 G16 causal authorization must directly precede prepared curve authorization"
    )
_LEGACY_CAUSAL_FIXED_G15_OUTCOME = replace(
    v34.STAGES[_LEGACY_CAUSAL_INDEX], pre_outcome=False
)
STAGES = (
    *v34.STAGES[:_LEGACY_CAUSAL_INDEX],
    _LEGACY_CAUSAL_FIXED_G15_OUTCOME,
    _ATTRIBUTION_BOUND_CAUSAL,
    *v34.STAGES[_LEGACY_CAUSAL_INDEX + 1 :],
)
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v34.LINK_RULES,
    (
        "g15_g16_attribution_bound_lineage",
        "fingerprint",
        "g16_attribution_bound_causal_authorization",
        "attribution_bound_lineage_fingerprint",
    ),
    (
        "g16_counterfactual_causal_authorization",
        "fingerprint",
        "g16_attribution_bound_causal_authorization",
        "legacy_counterfactual_causal_authorization_fingerprint",
    ),
    (
        "g15_g16_attribution_bound_lineage",
        "attribution_bound_publication_fingerprint",
        "g16_attribution_bound_causal_authorization",
        "attribution_bound_publication_fingerprint",
    ),
    (
        "g15_g16_attribution_bound_lineage",
        "attribution_authorization_fingerprint",
        "g16_attribution_bound_causal_authorization",
        "attribution_authorization_fingerprint",
    ),
    (
        "g15_g16_attribution_bound_lineage",
        "blind_score_fingerprint",
        "g16_attribution_bound_causal_authorization",
        "blind_score_fingerprint",
    ),
    (
        "g15_g16_attribution_bound_lineage",
        "refined_score_fingerprint",
        "g16_attribution_bound_causal_authorization",
        "refined_score_fingerprint",
    ),
    (
        "g15_g16_attribution_bound_lineage",
        "comparison_fingerprint",
        "g16_attribution_bound_causal_authorization",
        "comparison_fingerprint",
    ),
    (
        "g15_g16_attribution_bound_lineage",
        "candidate_count",
        "g16_attribution_bound_causal_authorization",
        "candidate_count",
    ),
    (
        "g15_g16_attribution_bound_lineage",
        "candidate_ids",
        "g16_attribution_bound_causal_authorization",
        "candidate_ids",
    ),
    (
        "g16_prepared_causal_authorization",
        "fingerprint",
        "g16_attribution_bound_causal_authorization",
        "prepared_causal_authorization_fingerprint",
    ),
    (
        "g16_prepared_replay",
        "fingerprint",
        "g16_attribution_bound_causal_authorization",
        "prepared_replay_gate_fingerprint",
    ),
    (
        "g16_historical_replay",
        "fingerprint",
        "g16_attribution_bound_causal_authorization",
        "replay_fingerprint",
    ),
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _without_bound_causal(keys: Sequence[str]) -> list[str]:
    return [key for key in keys if key != "g16_attribution_bound_causal_authorization"]


def _overall_status(ready_keys: list[str]) -> str:
    if len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V35"
    if "g16_counterfactual_causal_authorization" not in ready_keys:
        return _V34_OVERALL_STATUS(_without_bound_causal(ready_keys))
    if "g16_attribution_bound_causal_authorization" not in ready_keys:
        return "G16_LEGACY_CAUSAL_READY_ATTRIBUTION_BOUND_CAUSAL_INCOMPLETE"
    if "g16_prepared_curve_authorization" not in ready_keys:
        return "G16_ATTRIBUTION_BOUND_CAUSAL_READY_PREPARED_CURVE_INCOMPLETE"
    return _V34_OVERALL_STATUS(_without_bound_causal(ready_keys))


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
    legacy_causal = "g16_counterfactual_causal_authorization" in ready_set
    bound_causal = "g16_attribution_bound_causal_authorization" in ready_set
    prepared_curve = "g16_prepared_curve_authorization" in ready_set
    return {
        **v34._summary_fields(_without_bound_causal(ready)),
        "g16_attribution_bound_causal_artifact": _ATTRIBUTION_BOUND_CAUSAL.filename,
        "g16_attribution_bound_causal_schema": _ATTRIBUTION_BOUND_CAUSAL.schema,
        "g16_legacy_counterfactual_causal_fixed_g15_outcome_only": True,
        "g16_posterior_bound_to_attribution_scored_g15_lessons": bound_causal,
        "g16_outcomes_unavailable_during_causal_authorization": True,
        "g16_curve_blocked_until_attribution_bound_causal": True,
        "g16_prepared_curve_opened_after_attribution_bound_causal": prepared_curve,
        "g16_legacy_counterfactual_causal_ready": legacy_causal,
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
        "Readiness v35 requires the exact pre-cutoff G16 posterior authorization to be "
        "recursively rebound to attribution-scored G15 lesson lineage before any G16 "
        "curve stage. Fixed G15 outcomes are disclosed; G16 outcomes, scoring, posterior "
        "mutation, ng_brain.json writes, execution, and options remain forbidden."
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
            "readiness v35 report schema or fingerprint mismatch"
        )
    with _legacy_contract():
        legacy.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError(
            "readiness v35 overall status mismatch"
        )
    for field, expected in _summary_fields(ready).items():
        if value.get(field) != expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v35 {field} summary mismatch"
            )

    ready_set = set(ready)
    legacy_causal = "g16_counterfactual_causal_authorization" in ready_set
    bound_causal = "g16_attribution_bound_causal_authorization" in ready_set
    prepared_curve = "g16_prepared_curve_authorization" in ready_set
    if bound_causal and not legacy_causal:
        raise HistoricalRefinementReadinessError(
            "attribution-bound G16 causal authorization may not bypass legacy causal authorization"
        )
    if prepared_curve and not bound_causal:
        raise HistoricalRefinementReadinessError(
            "G16 prepared curve may not bypass attribution-bound causal authorization"
        )

    order = list(value.get("stage_order") or [])
    causal_index = order.index("g16_counterfactual_causal_authorization")
    if order[causal_index : causal_index + 3] != [
        "g16_counterfactual_causal_authorization",
        "g16_attribution_bound_causal_authorization",
        "g16_prepared_curve_authorization",
    ]:
        raise HistoricalRefinementReadinessError(
            "attribution-bound causal authorization must remain between legacy causal and prepared curve"
        )
    legacy_spec = next(
        spec for spec in STAGES if spec.key == "g16_counterfactual_causal_authorization"
    )
    if legacy_spec.pre_outcome is not False:
        raise HistoricalRefinementReadinessError(
            "legacy G16 causal authorization must disclose fixed G15 outcome use"
        )
    if _ATTRIBUTION_BOUND_CAUSAL.pre_outcome is not False:
        raise HistoricalRefinementReadinessError(
            "attribution-bound G16 causal authorization must remain behind fixed G15 outcomes"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v34._linked_fixture_chain()
    bound = values["g15_g16_attribution_bound_lineage"]
    legacy_causal = values["g16_counterfactual_causal_authorization"]
    prepared = values["g16_prepared_causal_authorization"]
    prepared_replay = values["g16_prepared_replay"]
    replay = values["g16_historical_replay"]

    gate = legacy._fixture_artifact(
        _ATTRIBUTION_BOUND_CAUSAL,
        "G16_ATTRIBUTION_BOUND_CAUSAL_AUTHORIZED",
    )
    gate.update(
        {
            "attribution_bound_lineage_fingerprint": bound["fingerprint"],
            "legacy_counterfactual_causal_authorization_fingerprint": legacy_causal[
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
            "prepared_causal_authorization_fingerprint": prepared["fingerprint"],
            "prepared_replay_gate_fingerprint": prepared_replay["fingerprint"],
            "replay_fingerprint": replay["fingerprint"],
            "manifest_fingerprint": legacy_causal.get("manifest_fingerprint", "m" * 64),
            "prepared_corpus_fingerprint": legacy_causal.get(
                "prepared_corpus_fingerprint", "p" * 64
            ),
            "blind_prior_fingerprint": legacy_causal.get(
                "blind_prior_fingerprint", "b" * 64
            ),
            "authorization_stream_fingerprint": legacy_causal.get(
                "authorization_stream_fingerprint", "a" * 64
            ),
            "posterior_stream_fingerprint": legacy_causal.get(
                "posterior_stream_fingerprint", "o" * 64
            ),
            "candidate_count": bound["candidate_count"],
            "candidate_ids": copy.deepcopy(bound["candidate_ids"]),
            "candidate_evidence_fingerprints": copy.deepcopy(
                bound.get("candidate_evidence_fingerprints") or {}
            ),
            "stand_down_days": [],
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
            "next_permitted_stage": (
                "OUTCOME_BLIND_G16_CURVE_ADAPTER_WITH_ATTRIBUTION_BOUND_LINEAGE"
            ),
        }
    )
    gate.pop("fingerprint", None)
    gate["fingerprint"] = _fingerprint(gate)
    values["g16_attribution_bound_causal_authorization"] = gate

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

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        values = _linked_fixture_chain()
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        report = build_readiness_report(root, validator_overrides=overrides)
        assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V35"
        assert report["g16_posterior_bound_to_attribution_scored_g15_lessons"] is True
        assert report["g16_outcomes_unavailable_during_causal_authorization"] is True
    print("[ng_historical_refinement_readiness_v35] selftest PASS")
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
