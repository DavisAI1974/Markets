#!/usr/bin/env python3
"""Readiness v37: require an attribution-bound immutable G16 curve lock before scoring."""
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
import ng_historical_refinement_readiness_v36 as v36

SCHEMA = "ng_historical_refinement_readiness.v37"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V36_STATUS = v36._overall_status

_ATTRIBUTION_BOUND_LOCK = StageSpec(
    "g16_attribution_bound_curve_lock",
    "g16_attribution_bound_curve_lock.json",
    "ng_g16_attribution_bound_curve_lock_gate.v1",
    "fingerprint",
    frozenset(
        {
            "G16_ATTRIBUTION_BOUND_CURVE_LOCKED",
            "G16_ATTRIBUTION_BOUND_CURVE_LOCKED_WITH_STAND_DOWNS",
        }
    ),
    "ng_g16_attribution_bound_curve_lock_gate",
    ("validate_gate",),
    (
        "Recursively bind the exact immutable G16 curve lock to attribution-scored "
        "G15 lessons before fixed G16 scoring."
    ),
    required_fields=(
        "attribution_bound_curve_authorization_fingerprint",
        "counterfactual_curve_lock_fingerprint",
        "counterfactual_curve_authorization_fingerprint",
        "attribution_bound_causal_authorization_fingerprint",
        "prepared_curve_authorization_fingerprint",
        "prepared_curve_lock_fingerprint",
        "validation_bundle_fingerprint",
        *v36._BOUND_FIELDS,
        "refined_curve_fingerprint",
        "g16_curve_lock_bound_to_attribution_scored_g15_lessons",
        "lesson_proposals_brain_write_forbidden",
        "next_permitted_stage",
    ),
    pre_outcome=False,
)

_KEYS = [spec.key for spec in v36.STAGES]
_LOCK_INDEX = _KEYS.index("g16_counterfactual_curve_lock")
_PUBLICATION_INDEX = _KEYS.index("g16_counterfactual_publication")
if _PUBLICATION_INDEX != _LOCK_INDEX + 1:
    raise HistoricalRefinementReadinessError(
        "readiness v36 curve lock must directly precede G16 publication"
    )
_LEGACY_LOCK = replace(
    v36.STAGES[_LOCK_INDEX],
    required_fields=tuple(
        field
        for field in v36.STAGES[_LOCK_INDEX].required_fields
        if field != "attribution_bound_curve_authorization_fingerprint"
    ),
    pre_outcome=False,
)
STAGES = (
    *v36.STAGES[:_LOCK_INDEX],
    _LEGACY_LOCK,
    _ATTRIBUTION_BOUND_LOCK,
    *v36.STAGES[_LOCK_INDEX + 1 :],
)

_OLD_SYNTHETIC_LINK = (
    "g16_attribution_bound_curve_authorization",
    "fingerprint",
    "g16_counterfactual_curve_lock",
    "attribution_bound_curve_authorization_fingerprint",
)
LINK_RULES = (
    *(rule for rule in v36.LINK_RULES if rule != _OLD_SYNTHETIC_LINK),
    (
        "g16_attribution_bound_curve_authorization",
        "fingerprint",
        _ATTRIBUTION_BOUND_LOCK.key,
        "attribution_bound_curve_authorization_fingerprint",
    ),
    (
        "g16_counterfactual_curve_lock",
        "lock_fingerprint",
        _ATTRIBUTION_BOUND_LOCK.key,
        "counterfactual_curve_lock_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_authorization",
        "counterfactual_curve_authorization_fingerprint",
        _ATTRIBUTION_BOUND_LOCK.key,
        "counterfactual_curve_authorization_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_authorization",
        "attribution_bound_causal_authorization_fingerprint",
        _ATTRIBUTION_BOUND_LOCK.key,
        "attribution_bound_causal_authorization_fingerprint",
    ),
    (
        "g16_attribution_bound_curve_authorization",
        "prepared_curve_authorization_fingerprint",
        _ATTRIBUTION_BOUND_LOCK.key,
        "prepared_curve_authorization_fingerprint",
    ),
    (
        "g16_counterfactual_curve_lock",
        "prepared_curve_lock_fingerprint",
        _ATTRIBUTION_BOUND_LOCK.key,
        "prepared_curve_lock_fingerprint",
    ),
    *(
        (
            "g16_attribution_bound_curve_authorization",
            field,
            _ATTRIBUTION_BOUND_LOCK.key,
            field,
        )
        for field in v36._BOUND_FIELDS
    ),
    (
        "g16_attribution_bound_curve_authorization",
        "refined_curve_fingerprint",
        _ATTRIBUTION_BOUND_LOCK.key,
        "refined_curve_fingerprint",
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


def _without_bound_lock(keys: Sequence[str]) -> list[str]:
    return [key for key in keys if key != _ATTRIBUTION_BOUND_LOCK.key]


def _overall_status(ready: list[str]) -> str:
    if len(ready) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V37"
    if "g16_counterfactual_curve_lock" not in ready:
        return _V36_STATUS(_without_bound_lock(ready))
    if _ATTRIBUTION_BOUND_LOCK.key not in ready:
        return "G16_LEGACY_CURVE_LOCK_READY_ATTRIBUTION_BOUND_LOCK_INCOMPLETE"
    if "g16_counterfactual_publication" not in ready:
        return "G16_ATTRIBUTION_BOUND_CURVE_LOCK_READY_PUBLICATION_INCOMPLETE"
    return _V36_STATUS(_without_bound_lock(ready))


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
        **v36._summary_fields(_without_bound_lock(ready)),
        "g16_attribution_bound_curve_lock_artifact": _ATTRIBUTION_BOUND_LOCK.filename,
        "g16_attribution_bound_curve_lock_schema": _ATTRIBUTION_BOUND_LOCK.schema,
        "g16_legacy_curve_lock_no_longer_requires_unemitted_bound_field": True,
        "g16_curve_lock_bound_to_attribution_scored_g15_lessons": (
            _ATTRIBUTION_BOUND_LOCK.key in ready_set
        ),
        "g16_fixed_scoring_blocked_until_attribution_bound_lock": True,
        "g16_fixed_scoring_opened_after_attribution_bound_lock": (
            "g16_counterfactual_publication" in ready_set
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
        "The legacy curve lock is validated as its actual producer emits it, then a "
        "recursive attribution-bound lock gate must pass before fixed G16 scoring. "
        "Blind forecasts, posterior state, ng_brain.json, SHADOW mode, tastytrade, "
        "and the no-options boundary remain unchanged."
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
            "readiness v37 schema or fingerprint mismatch"
        )
    with _contract():
        legacy.validate_readiness_report(value)
    ready = list(value.get("ready_stages") or [])
    if value.get("status") != _overall_status(ready):
        raise HistoricalRefinementReadinessError("readiness v37 status mismatch")
    for field, expected in _summary_fields(ready).items():
        if value.get(field) != expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v37 {field} mismatch"
            )

    order = list(value.get("stage_order") or [])
    start = order.index("g16_attribution_bound_curve_authorization")
    if order[start : start + 4] != [
        "g16_attribution_bound_curve_authorization",
        "g16_counterfactual_curve_lock",
        _ATTRIBUTION_BOUND_LOCK.key,
        "g16_counterfactual_publication",
    ]:
        raise HistoricalRefinementReadinessError(
            "attribution-bound curve lock must remain between legacy lock and publication"
        )
    by_key = {spec.key: spec for spec in STAGES}
    if "attribution_bound_curve_authorization_fingerprint" in by_key[
        "g16_counterfactual_curve_lock"
    ].required_fields:
        raise HistoricalRefinementReadinessError(
            "legacy lock still requires a field its producer cannot emit"
        )
    for key in (
        "g16_attribution_bound_curve_authorization",
        "g16_counterfactual_curve_lock",
        _ATTRIBUTION_BOUND_LOCK.key,
        "g16_counterfactual_publication",
    ):
        if by_key[key].pre_outcome is not False:
            raise HistoricalRefinementReadinessError(
                f"{key} must disclose fixed G15 outcome use"
            )
    ready_set = set(ready)
    if _ATTRIBUTION_BOUND_LOCK.key in ready_set and not {
        "g16_attribution_bound_curve_authorization",
        "g16_counterfactual_curve_lock",
    }.issubset(ready_set):
        raise HistoricalRefinementReadinessError(
            "attribution-bound lock bypassed curve authorization or legacy lock"
        )
    if (
        "g16_counterfactual_publication" in ready_set
        and _ATTRIBUTION_BOUND_LOCK.key not in ready_set
    ):
        raise HistoricalRefinementReadinessError(
            "G16 publication bypassed attribution-bound curve lock"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v36._linked_fixture_chain()
    legacy_lock = values["g16_counterfactual_curve_lock"]
    legacy_lock.pop("attribution_bound_curve_authorization_fingerprint", None)
    legacy_lock.pop("lock_fingerprint", None)
    legacy_lock["lock_fingerprint"] = _fingerprint(legacy_lock)

    bound = values["g16_attribution_bound_curve_authorization"]
    gate = legacy._fixture_artifact(
        _ATTRIBUTION_BOUND_LOCK,
        "G16_ATTRIBUTION_BOUND_CURVE_LOCKED",
    )
    gate.update(
        {
            "attribution_bound_curve_authorization_fingerprint": bound["fingerprint"],
            "counterfactual_curve_lock_fingerprint": legacy_lock["lock_fingerprint"],
            "counterfactual_curve_authorization_fingerprint": bound[
                "counterfactual_curve_authorization_fingerprint"
            ],
            "attribution_bound_causal_authorization_fingerprint": bound[
                "attribution_bound_causal_authorization_fingerprint"
            ],
            "prepared_curve_authorization_fingerprint": bound[
                "prepared_curve_authorization_fingerprint"
            ],
            "prepared_curve_lock_fingerprint": legacy_lock[
                "prepared_curve_lock_fingerprint"
            ],
            "validation_bundle_fingerprint": "d" * 64,
            **{field: copy.deepcopy(bound[field]) for field in v36._BOUND_FIELDS},
            "refined_curve_fingerprint": bound["refined_curve_fingerprint"],
            "g16_curve_lock_bound_to_attribution_scored_g15_lessons": True,
            "lesson_proposals_brain_write_forbidden": True,
            "actual_g15_outcomes_used": True,
            "actual_g16_outcomes_used": False,
            "fixed_scoring_may_begin": True,
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
                "FIXED_G16_BLIND_REFINED_SCORING_WITH_ATTRIBUTION_BOUND_LINEAGE"
            ),
        }
    )
    gate.pop("fingerprint", None)
    gate["fingerprint"] = _fingerprint(gate)
    values[_ATTRIBUTION_BOUND_LOCK.key] = gate

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
        assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V37"
        assert report["g16_curve_lock_bound_to_attribution_scored_g15_lessons"] is True
        assert report[
            "g16_legacy_curve_lock_no_longer_requires_unemitted_bound_field"
        ] is True
    print("[ng_historical_refinement_readiness_v37] selftest PASS")
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
