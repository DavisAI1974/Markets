#!/usr/bin/env python3
"""Bind exact G15 counterfactual lesson lineage into G16 causal authorization.

The prepared G16 causal authorization validates the exact 23-source replay and the
pre-cutoff posterior chain. The G15-to-G16 counterfactual lineage gate validates that
G15 publication and the G16 plan use the same deterministic full-minus-neutral lesson
set. This wrapper requires both contracts together so an older adjudication, registry,
or plan cannot enter the prepared G16 posterior path.

The wrapper is outcome-blind for G16. It never changes either blind forecast, never
updates ``knowledge/ng_brain.json``, never grants execution authority, keeps CME event
contracts SHADOW, keeps tastytrade as the brokerage contract, and leaves options work
unstarted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ng_g15_g16_counterfactual_lineage_gate import (
    CounterfactualLineageError,
    READY as LINEAGE_READY,
    READY_WITH_STAND_DOWNS as LINEAGE_STAND_DOWNS,
    SCHEMA as LINEAGE_SCHEMA,
    validate_lineage,
)
from ng_g16_prepared_causal_authorization import (
    G16PreparedCausalAuthorizationError,
    NEXT_STAGE as PREPARED_NEXT_STAGE,
    SCHEMA as PREPARED_SCHEMA,
    STATUS_READY as PREPARED_READY,
    STATUS_STAND_DOWNS as PREPARED_STAND_DOWNS,
    validate_authorization,
)

SCHEMA = "ng_g16_counterfactual_causal_authorization.v1"
AUTHORITY = "EXACT_G15_COUNTERFACTUAL_LINEAGE_TO_G16_PRE_CUTOFF_CAUSAL_ONLY"
STATUS_READY = "G16_COUNTERFACTUAL_CAUSAL_AUTHORIZED"
STATUS_STAND_DOWNS = "G16_COUNTERFACTUAL_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS"
NEXT_STAGE = "OUTCOME_BLIND_G16_CURVE_ADAPTER_WITH_COUNTERFACTUAL_LINEAGE"


class G16CounterfactualCausalAuthorizationError(ValueError):
    """Raised when counterfactual lesson lineage and G16 causal authority diverge."""


def _fp(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _validate_upstream(
    *,
    lineage_gate: Mapping[str, Any],
    counterfactual_gate: Mapping[str, Any],
    g15_publication: Mapping[str, Any],
    g16_plan: Mapping[str, Any],
    g15_replay: Mapping[str, Any],
    g15_anchor: Mapping[str, Any],
    g15_refine_stream: Mapping[str, Any],
    g15_attribution: Mapping[str, Any],
    g15_audit: Mapping[str, Any],
    g15_comparison: Mapping[str, Any],
    g16_blind_forecast: Mapping[str, Any],
    g16_blind_safe_state: Mapping[str, Any],
    prepared_authorization: Mapping[str, Any],
    prepared_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    g16_replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    causal_artifacts: Mapping[str, Any],
) -> None:
    try:
        validate_lineage(
            lineage_gate,
            counterfactual_gate=counterfactual_gate,
            g15_publication=g15_publication,
            g16_plan=g16_plan,
            replay=g15_replay,
            anchor=g15_anchor,
            refine_stream=g15_refine_stream,
            attribution=g15_attribution,
            audit=g15_audit,
            comparison=g15_comparison,
            g16_blind_forecast=g16_blind_forecast,
            g16_blind_safe_state=g16_blind_safe_state,
        )
    except CounterfactualLineageError as error:
        raise G16CounterfactualCausalAuthorizationError(
            f"counterfactual lineage gate invalid: {error}"
        ) from error

    registry_source = counterfactual_gate.get("adjudication") or {}
    try:
        validate_authorization(
            prepared_authorization,
            prepared_gate=prepared_gate,
            prepared_index=prepared_index,
            manifest=manifest,
            replay=g16_replay,
            blind_prior=blind_prior,
            causal_artifacts=causal_artifacts,
            blind_forecast=g16_blind_forecast,
            blind_safe_state=g16_blind_safe_state,
            registry_source=registry_source,
        )
    except G16PreparedCausalAuthorizationError as error:
        raise G16CounterfactualCausalAuthorizationError(
            f"prepared causal authorization invalid: {error}"
        ) from error

    if lineage_gate.get("schema") != LINEAGE_SCHEMA or lineage_gate.get("status") not in {
        LINEAGE_READY,
        LINEAGE_STAND_DOWNS,
    }:
        raise G16CounterfactualCausalAuthorizationError("counterfactual lineage is not ready")
    if prepared_authorization.get("schema") != PREPARED_SCHEMA or prepared_authorization.get(
        "status"
    ) not in {PREPARED_READY, PREPARED_STAND_DOWNS}:
        raise G16CounterfactualCausalAuthorizationError("prepared causal authorization is not ready")
    if prepared_authorization.get("next_permitted_stage") != PREPARED_NEXT_STAGE:
        raise G16CounterfactualCausalAuthorizationError(
            "prepared causal authorization has an unexpected next stage"
        )


def _cross_checks(
    *,
    lineage_gate: Mapping[str, Any],
    prepared_authorization: Mapping[str, Any],
    g16_plan: Mapping[str, Any],
    causal_artifacts: Mapping[str, Any],
) -> tuple[list[str], dict[str, str], list[str]]:
    causal_plan = dict(causal_artifacts.get("plan") or {})
    completion = dict(causal_artifacts.get("completion") or {})
    if causal_plan.get("plan_fingerprint") != g16_plan.get("plan_fingerprint"):
        raise G16CounterfactualCausalAuthorizationError(
            "prepared causal pipeline uses a different G16 plan"
        )

    links = {
        "g16_plan_fingerprint": "plan_fingerprint",
        "g16_registry_fingerprint": "lesson_registry_fingerprint",
        "g15_adjudication_fingerprint": "lesson_adjudication_fingerprint",
        "g16_blind_forecast_fingerprint": "blind_forecast_fingerprint",
        "g16_blind_safe_state_fingerprint": "blind_safe_state_fingerprint",
    }
    for lineage_field, prepared_field in links.items():
        expected = lineage_gate.get(lineage_field)
        if prepared_authorization.get(prepared_field) != expected:
            raise G16CounterfactualCausalAuthorizationError(
                f"prepared causal {prepared_field} bypasses counterfactual lineage"
            )
        if completion.get(prepared_field) != expected:
            raise G16CounterfactualCausalAuthorizationError(
                f"causal completion {prepared_field} bypasses counterfactual lineage"
            )

    candidate_ids = list(lineage_gate.get("candidate_ids") or [])
    if not candidate_ids or candidate_ids != sorted(candidate_ids):
        raise G16CounterfactualCausalAuthorizationError(
            "counterfactual lineage candidate ids must be non-empty and sorted"
        )
    if len(candidate_ids) != len(set(candidate_ids)):
        raise G16CounterfactualCausalAuthorizationError(
            "counterfactual lineage candidate ids must be unique"
        )
    for label, observed in (
        ("G16 plan", list(g16_plan.get("candidate_ids") or [])),
        ("causal plan", list(causal_plan.get("candidate_ids") or [])),
        ("causal completion", list(completion.get("candidate_ids") or [])),
        ("prepared authorization", list(prepared_authorization.get("candidate_ids") or [])),
    ):
        if observed != candidate_ids:
            raise G16CounterfactualCausalAuthorizationError(
                f"{label} candidate set differs from counterfactual lineage"
            )

    evidence = {
        str(key): str(value)
        for key, value in dict(
            lineage_gate.get("candidate_evidence_fingerprints") or {}
        ).items()
    }
    if sorted(evidence) != candidate_ids or any(not value for value in evidence.values()):
        raise G16CounterfactualCausalAuthorizationError(
            "counterfactual candidate evidence map is incomplete"
        )
    for day, row in dict(causal_plan.get("days") or {}).items():
        if dict(row).get("candidate_evidence_fingerprints") != evidence:
            raise G16CounterfactualCausalAuthorizationError(
                f"causal plan {day} candidate evidence differs from counterfactual lineage"
            )

    authorization_stream = dict(causal_artifacts.get("authorization_stream") or {})
    for token in authorization_stream.get("authorizations") or []:
        if list(dict(token).get("authorized_candidate_ids") or []) != candidate_ids:
            raise G16CounterfactualCausalAuthorizationError(
                "authorization token did not request the exact counterfactual candidate set"
            )

    posterior_stream = dict(causal_artifacts.get("posterior_stream") or {})
    used: set[str] = set()
    for output in posterior_stream.get("outputs") or []:
        for row in dict(output).get("attribution") or []:
            identifier = str(dict(row).get("candidate_id") or "")
            if identifier:
                if identifier not in candidate_ids:
                    raise G16CounterfactualCausalAuthorizationError(
                        f"posterior attribution uses unregistered candidate {identifier!r}"
                    )
                used.add(identifier)

    return candidate_ids, evidence, sorted(used)


def _build_authorization(
    *,
    lineage_gate: Mapping[str, Any],
    counterfactual_gate: Mapping[str, Any],
    g15_publication: Mapping[str, Any],
    g16_plan: Mapping[str, Any],
    g15_replay: Mapping[str, Any],
    g15_anchor: Mapping[str, Any],
    g15_refine_stream: Mapping[str, Any],
    g15_attribution: Mapping[str, Any],
    g15_audit: Mapping[str, Any],
    g15_comparison: Mapping[str, Any],
    g16_blind_forecast: Mapping[str, Any],
    g16_blind_safe_state: Mapping[str, Any],
    prepared_authorization: Mapping[str, Any],
    prepared_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    g16_replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    causal_artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            lineage_gate,
            counterfactual_gate,
            g15_publication,
            g16_plan,
            g15_replay,
            g15_anchor,
            g15_refine_stream,
            g15_attribution,
            g15_audit,
            g15_comparison,
            g16_blind_forecast,
            g16_blind_safe_state,
            prepared_authorization,
            prepared_gate,
            prepared_index,
            manifest,
            g16_replay,
            blind_prior,
            causal_artifacts,
        )
    )
    _validate_upstream(
        lineage_gate=lineage_gate,
        counterfactual_gate=counterfactual_gate,
        g15_publication=g15_publication,
        g16_plan=g16_plan,
        g15_replay=g15_replay,
        g15_anchor=g15_anchor,
        g15_refine_stream=g15_refine_stream,
        g15_attribution=g15_attribution,
        g15_audit=g15_audit,
        g15_comparison=g15_comparison,
        g16_blind_forecast=g16_blind_forecast,
        g16_blind_safe_state=g16_blind_safe_state,
        prepared_authorization=prepared_authorization,
        prepared_gate=prepared_gate,
        prepared_index=prepared_index,
        manifest=manifest,
        g16_replay=g16_replay,
        blind_prior=blind_prior,
        causal_artifacts=causal_artifacts,
    )
    candidate_ids, evidence, used_ids = _cross_checks(
        lineage_gate=lineage_gate,
        prepared_authorization=prepared_authorization,
        g16_plan=g16_plan,
        causal_artifacts=causal_artifacts,
    )

    lineage_stand_downs = sorted(
        {str(day) for day in lineage_gate.get("stand_down_days") or []}
    )
    prepared_stand_downs = sorted(
        {str(day) for day in prepared_authorization.get("all_stand_down_days") or []}
    )
    all_stand_downs = sorted(set(lineage_stand_downs) | set(prepared_stand_downs))
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": STATUS_STAND_DOWNS if all_stand_downs else STATUS_READY,
        "authority": AUTHORITY,
        "counterfactual_lineage_gate_fingerprint": lineage_gate.get("fingerprint"),
        "counterfactual_lesson_gate_fingerprint": lineage_gate.get(
            "counterfactual_lesson_gate_fingerprint"
        ),
        "counterfactual_attribution_fingerprint": lineage_gate.get(
            "counterfactual_attribution_fingerprint"
        ),
        "g15_publication_fingerprint": lineage_gate.get("g15_publication_fingerprint"),
        "g15_adjudication_fingerprint": lineage_gate.get(
            "g15_adjudication_fingerprint"
        ),
        "g16_registry_fingerprint": lineage_gate.get("g16_registry_fingerprint"),
        "prepared_causal_authorization_fingerprint": prepared_authorization.get(
            "fingerprint"
        ),
        "prepared_replay_gate_fingerprint": prepared_authorization.get(
            "prepared_replay_gate_fingerprint"
        ),
        "replay_fingerprint": prepared_authorization.get("replay_fingerprint"),
        "manifest_fingerprint": prepared_authorization.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": prepared_authorization.get(
            "prepared_corpus_fingerprint"
        ),
        "blind_prior_fingerprint": prepared_authorization.get(
            "blind_prior_fingerprint"
        ),
        "g16_plan_fingerprint": prepared_authorization.get("plan_fingerprint"),
        "authorization_stream_fingerprint": prepared_authorization.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": prepared_authorization.get(
            "posterior_stream_fingerprint"
        ),
        "g16_blind_forecast_fingerprint": prepared_authorization.get(
            "blind_forecast_fingerprint"
        ),
        "g16_blind_safe_state_fingerprint": prepared_authorization.get(
            "blind_safe_state_fingerprint"
        ),
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_observed_in_posterior_attribution": used_ids,
        "lineage_stand_down_days": lineage_stand_downs,
        "prepared_causal_stand_down_days": prepared_stand_downs,
        "all_stand_down_days": all_stand_downs,
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
        "next_permitted_stage": NEXT_STAGE,
        "note": (
            "The exact prepared G16 posterior chain is bound to the same deterministic "
            "G15 full-minus-neutral counterfactual lessons that were published and "
            "pre-registered before any G16 outcome access."
        ),
    }
    result["fingerprint"] = _fp(result)

    current = (
        lineage_gate,
        counterfactual_gate,
        g15_publication,
        g16_plan,
        g15_replay,
        g15_anchor,
        g15_refine_stream,
        g15_attribution,
        g15_audit,
        g15_comparison,
        g16_blind_forecast,
        g16_blind_safe_state,
        prepared_authorization,
        prepared_gate,
        prepared_index,
        manifest,
        g16_replay,
        blind_prior,
        causal_artifacts,
    )
    if current != originals:
        raise G16CounterfactualCausalAuthorizationError(
            "counterfactual causal authorization mutated a source artifact"
        )
    return result


def build_authorization(**kwargs: Any) -> dict[str, Any]:
    result = _build_authorization(**kwargs)
    validate_authorization_artifact(result, **kwargs)
    return result


def validate_authorization_artifact(
    authorization: Mapping[str, Any], **kwargs: Any
) -> None:
    candidate = copy.deepcopy(dict(authorization))
    observed = candidate.pop("fingerprint", None)
    if observed != _fp(candidate):
        raise G16CounterfactualCausalAuthorizationError("authorization fingerprint mismatch")
    if candidate.get("schema") != SCHEMA or candidate.get("authority") != AUTHORITY:
        raise G16CounterfactualCausalAuthorizationError(
            "authorization schema/authority mismatch"
        )
    if candidate.get("status") not in {STATUS_READY, STATUS_STAND_DOWNS}:
        raise G16CounterfactualCausalAuthorizationError("authorization is not ready")

    false_fields = (
        "actual_g16_outcomes_used",
        "g16_scoring_authorized",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    )
    for field in false_fields:
        if candidate.get(field) is not False:
            raise G16CounterfactualCausalAuthorizationError(
                f"authorization must keep {field}=false"
            )
    if candidate.get("actual_g15_outcomes_used") is not True:
        raise G16CounterfactualCausalAuthorizationError(
            "authorization must disclose G15 outcome use"
        )
    if candidate.get("one_signal_authority_preserved") is not True:
        raise G16CounterfactualCausalAuthorizationError(
            "authorization must preserve one signal authority"
        )
    if candidate.get("blind_forecasts_immutable") is not True:
        raise G16CounterfactualCausalAuthorizationError(
            "authorization must preserve blind forecast immutability"
        )
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise G16CounterfactualCausalAuthorizationError(
            "CME event contracts must remain SHADOW"
        )
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16CounterfactualCausalAuthorizationError(
            "brokerage contract must remain tastytrade_not_ibkr"
        )
    if candidate.get("next_permitted_stage") != NEXT_STAGE:
        raise G16CounterfactualCausalAuthorizationError(
            "authorization has an unexpected next stage"
        )

    rebuilt = _build_authorization(**kwargs)
    rebuilt.pop("fingerprint", None)
    candidate.pop("fingerprint", None)
    if candidate != rebuilt:
        raise G16CounterfactualCausalAuthorizationError(
            "authorization differs from deterministic reconstruction"
        )


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G16CounterfactualCausalAuthorizationError(
            f"expected JSON object: {path}"
        )
    return value


def _pipeline_artifacts(directory: Path) -> dict[str, Any]:
    return {
        "plan": _load(directory / "g16_shadow_plan.json"),
        "authorization_stream": _load(
            directory / "g16_shadow_authorization_stream.json"
        ),
        "posterior_stream": _load(directory / "g16_shadow_posterior_stream.json"),
        "completion": _load(directory / "g16_exact_causal_pipeline.json"),
    }


def _fixture() -> dict[str, Any]:
    import ng_g15_g16_counterfactual_lineage_gate as lineage_module
    from ng_g16_exact_causal_pipeline import _retime_fixture, build_exact_causal_pipeline
    from ng_g16_historical_replay import (
        _fixture_catalog,
        _fixture_inventory,
        build_manifest,
        prepare_corpus,
    )
    from ng_g16_prepared_causal_authorization import build_authorization as build_prepared
    from ng_g16_prepared_replay_gate import run_gate

    lineage_fixture = lineage_module._fixture()
    lineage_gate = lineage_module.build_lineage(
        counterfactual_gate=lineage_fixture["counterfactual_gate"],
        g15_publication=lineage_fixture["publication"],
        g16_plan=lineage_fixture["g16_plan"],
        replay=lineage_fixture["replay"],
        anchor=lineage_fixture["anchor"],
        refine_stream=lineage_fixture["refine_stream"],
        attribution=lineage_fixture["attribution"],
        audit=lineage_fixture["audit"],
        comparison=lineage_fixture["comparison"],
        g16_blind_forecast=lineage_fixture["g16_blind_forecast"],
        g16_blind_safe_state=lineage_fixture["g16_blind_safe_state"],
    )

    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    inventory, definition = _fixture_inventory(root)
    manifest = build_manifest(inventory, _fixture_catalog(inventory, definition))
    prepared_index = prepare_corpus(manifest, root / "prepared")
    blind_prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
    g16_replay, prepared_gate = run_gate(prepared_index, manifest, blind_prior)
    _retime_fixture(g16_replay)
    prepared_gate["replay_fingerprint"] = g16_replay["fingerprint"]
    prepared_gate.pop("fingerprint", None)
    prepared_gate["fingerprint"] = _fp(prepared_gate)

    counterfactual_gate = lineage_fixture["counterfactual_gate"]
    registry_source = counterfactual_gate["adjudication"]
    g16_blind_forecast = lineage_fixture["g16_blind_forecast"]
    g16_blind_safe_state = lineage_fixture["g16_blind_safe_state"]
    causal_artifacts = build_exact_causal_pipeline(
        g16_replay,
        blind_prior,
        g16_blind_forecast,
        g16_blind_safe_state,
        registry_source,
    )
    if (
        causal_artifacts["plan"]["plan_fingerprint"]
        != lineage_fixture["g16_plan"]["plan_fingerprint"]
    ):
        temporary.cleanup()
        raise AssertionError("fixture G16 plans are not deterministic")
    prepared_authorization = build_prepared(
        prepared_gate=prepared_gate,
        prepared_index=prepared_index,
        manifest=manifest,
        replay=g16_replay,
        blind_prior=blind_prior,
        causal_artifacts=causal_artifacts,
        blind_forecast=g16_blind_forecast,
        blind_safe_state=g16_blind_safe_state,
        registry_source=registry_source,
    )
    return {
        "_temporary": temporary,
        "lineage_fixture": lineage_fixture,
        "lineage_gate": lineage_gate,
        "counterfactual_gate": counterfactual_gate,
        "g15_publication": lineage_fixture["publication"],
        "g16_plan": lineage_fixture["g16_plan"],
        "g15_replay": lineage_fixture["replay"],
        "g15_anchor": lineage_fixture["anchor"],
        "g15_refine_stream": lineage_fixture["refine_stream"],
        "g15_attribution": lineage_fixture["attribution"],
        "g15_audit": lineage_fixture["audit"],
        "g15_comparison": lineage_fixture["comparison"],
        "g16_blind_forecast": g16_blind_forecast,
        "g16_blind_safe_state": g16_blind_safe_state,
        "prepared_authorization": prepared_authorization,
        "prepared_gate": prepared_gate,
        "prepared_index": prepared_index,
        "manifest": manifest,
        "g16_replay": g16_replay,
        "blind_prior": blind_prior,
        "causal_artifacts": causal_artifacts,
    }


def _build_from_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    return build_authorization(
        **{key: value for key, value in fixture.items() if not key.startswith("_") and key != "lineage_fixture"}
    )


def selftest() -> int:
    fixture = _fixture()
    try:
        result = _build_from_fixture(fixture)
        assert result["candidate_count"] > 0
        assert result["g16_plan_fingerprint"] == fixture["g16_plan"]["plan_fingerprint"]
        assert result["actual_g16_outcomes_used"] is False
        assert result["may_update_ng_brain"] is False
        assert result["options_lane_started"] is False
    finally:
        fixture["_temporary"].cleanup()
    print("[ng_g16_counterfactual_causal_authorization] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lineage-gate", type=Path)
    parser.add_argument("--counterfactual-gate", type=Path)
    parser.add_argument("--g15-publication", type=Path)
    parser.add_argument("--g16-plan", type=Path)
    parser.add_argument("--g15-replay", type=Path)
    parser.add_argument("--g15-anchor", type=Path)
    parser.add_argument("--g15-refine-stream", type=Path)
    parser.add_argument("--g15-attribution", type=Path)
    parser.add_argument("--g15-audit", type=Path)
    parser.add_argument("--g15-comparison", type=Path)
    parser.add_argument("--g16-blind", type=Path)
    parser.add_argument("--g16-blind-safe-state", type=Path)
    parser.add_argument("--prepared-authorization", type=Path)
    parser.add_argument("--prepared-gate", type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--g16-replay", type=Path)
    parser.add_argument("--blind-prior", type=Path)
    parser.add_argument("--pipeline-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (
        args.lineage_gate,
        args.counterfactual_gate,
        args.g15_publication,
        args.g16_plan,
        args.g15_replay,
        args.g15_anchor,
        args.g15_refine_stream,
        args.g15_attribution,
        args.g15_audit,
        args.g15_comparison,
        args.g16_blind,
        args.g16_blind_safe_state,
        args.prepared_authorization,
        args.prepared_gate,
        args.prepared,
        args.manifest,
        args.g16_replay,
        args.blind_prior,
        args.pipeline_dir,
        args.out,
    )
    if any(value is None for value in required):
        parser.error("all artifact paths and --out are required")

    result = build_authorization(
        lineage_gate=_load(args.lineage_gate),
        counterfactual_gate=_load(args.counterfactual_gate),
        g15_publication=_load(args.g15_publication),
        g16_plan=_load(args.g16_plan),
        g15_replay=_load(args.g15_replay),
        g15_anchor=_load(args.g15_anchor),
        g15_refine_stream=_load(args.g15_refine_stream),
        g15_attribution=_load(args.g15_attribution),
        g15_audit=_load(args.g15_audit),
        g15_comparison=_load(args.g15_comparison),
        g16_blind_forecast=_load(args.g16_blind),
        g16_blind_safe_state=_load(args.g16_blind_safe_state),
        prepared_authorization=_load(args.prepared_authorization),
        prepared_gate=_load(args.prepared_gate),
        prepared_index=_load(args.prepared),
        manifest=_load(args.manifest),
        g16_replay=_load(args.g16_replay),
        blind_prior=_load(args.blind_prior),
        causal_artifacts=_pipeline_artifacts(args.pipeline_dir),
    )
    _atomic(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "candidate_count": result["candidate_count"],
                "fingerprint": result["fingerprint"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
