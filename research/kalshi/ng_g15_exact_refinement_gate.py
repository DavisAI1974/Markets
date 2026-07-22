#!/usr/bin/env python3
"""Authorize downstream G15 refinement only from an exact-basis causal replay.

This contract closes a provenance gap between ``ng_g15_exact_replay_completion``
and ``ng_g15_pipeline``. A pipeline bundle is accepted only when its replay,
anchor, blind prior, prepared corpus, exact manifest, feature states, posterior
outputs, daily audit, and lesson proposals all remain fingerprint-linked to the
exact replay completion artifact.

The gate is outcome-blind. It cannot mutate the blind forecast or prior, update
``ng_brain.json``, authorize G16, or grant execution authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "ng_g15_exact_refinement_authorization.v1"
COMPLETION_SCHEMA = "ng_g15_exact_replay_completion.v1"
PIPELINE_SCHEMA = "ng_g15_pipeline.v1"
REFINE_STREAM_SCHEMA = "ng_rt_refine_stream.v1"
AUDIT_SCHEMA = "ng_g15_daily_refine_audit.v1"
LESSON_SCHEMA = "ng_g15_lesson_proposals.v1"
READY = "EXACT_G15_REFINEMENT_READY"
READY_WITH_STAND_DOWNS = "EXACT_G15_REFINEMENT_READY_WITH_STAND_DOWNS"
EXACT_REPLAY_READY = {
    "EXACT_CAUSAL_REPLAY_READY",
    "EXACT_CAUSAL_REPLAY_READY_WITH_STAND_DOWNS",
}
G15_DATES = (
    "20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
    "20260322", "20260323", "20260324", "20260325", "20260326", "20260327",
)


class ExactRefinementAuthorizationError(ValueError):
    """Raised when a pipeline cannot be tied to the exact-basis replay."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _verify_embedded_fingerprint(value: Mapping[str, Any], field: str, *, label: str) -> None:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not observed or observed != _fingerprint(payload):
        raise ExactRefinementAuthorizationError(f"{label} fingerprint mismatch")


def _validate_completion(completion: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(completion))
    _verify_embedded_fingerprint(value, "completion_fingerprint", label="completion")
    if value.get("schema") != COMPLETION_SCHEMA:
        raise ExactRefinementAuthorizationError("unexpected exact replay completion schema")
    if value.get("status") not in EXACT_REPLAY_READY:
        raise ExactRefinementAuthorizationError("exact replay completion is not ready")
    if value.get("basis_status") != "MATCHED_L1_MBO_READY":
        raise ExactRefinementAuthorizationError("completion is not exact matched L1+MBO basis")
    if value.get("g15_shadow_refinement_authorized") is not True:
        raise ExactRefinementAuthorizationError("completion does not authorize G15 SHADOW refinement")
    if value.get("g16_authorized") is not False:
        raise ExactRefinementAuthorizationError("completion cannot authorize G16")
    for field in (
        "execution_authority", "actual_outcomes_used", "may_change_blind_prior",
        "may_change_blind_forecast", "may_change_posterior", "may_update_ng_brain",
    ):
        if value.get(field) is not False:
            raise ExactRefinementAuthorizationError(f"completion must keep {field}=false")
    days = [str(row.get("date") or "") for row in value.get("days") or []]
    if days != list(G15_DATES):
        raise ExactRefinementAuthorizationError("completion lost canonical G15 order")
    if int(value.get("prepared_source_count") or 0) != 26:
        raise ExactRefinementAuthorizationError("completion must reference all 26 prepared sources")
    if int(value.get("emitted_feature_states") or 0) <= 0:
        raise ExactRefinementAuthorizationError("completion emitted no causal feature states")
    return value


def _validate_pipeline_fingerprint(pipeline: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(pipeline))
    _verify_embedded_fingerprint(value, "pipeline_fingerprint", label="pipeline")
    if value.get("schema") != PIPELINE_SCHEMA:
        raise ExactRefinementAuthorizationError("unexpected G15 pipeline schema")
    if value.get("market") != "NG" or int(value.get("group") or 0) != 15:
        raise ExactRefinementAuthorizationError("pipeline must describe G15 NG")
    if value.get("authority") != "HISTORICAL_REFINE_PIPELINE_ONLY":
        raise ExactRefinementAuthorizationError("pipeline authority is invalid")
    if value.get("execution_authority") is not False:
        raise ExactRefinementAuthorizationError("pipeline cannot grant execution authority")
    expected_gates = {
        "actual_outcome_scoring_complete": False,
        "refined_curve_complete": False,
        "continuous_rt_renders_complete": False,
        "g16_authorized": False,
    }
    if dict(value.get("gates") or {}) != expected_gates:
        raise ExactRefinementAuthorizationError("pipeline prematurely claims a downstream gate")
    return value


def _validate_blind(pipeline: Mapping[str, Any], blind_forecast_bytes: bytes | None) -> str:
    blind = dict(pipeline.get("blind_forecast") or {})
    if blind.get("byte_identical") is not True:
        raise ExactRefinementAuthorizationError("pipeline did not preserve the blind forecast")
    before = str(blind.get("sha256_before") or "")
    after = str(blind.get("sha256_after") or "")
    if not before or before != after:
        raise ExactRefinementAuthorizationError("blind forecast before/after hash differs")
    if blind_forecast_bytes is not None and before != _sha256_bytes(blind_forecast_bytes):
        raise ExactRefinementAuthorizationError("pipeline references a different blind forecast file")
    return before


def _completion_state_fingerprints(completion: Mapping[str, Any]) -> Counter[str]:
    values = [
        str(fingerprint)
        for day in completion.get("days") or []
        for fingerprint in day.get("state_fingerprints") or []
    ]
    if not values or any(not value for value in values):
        raise ExactRefinementAuthorizationError("completion lacks feature-state fingerprints")
    if len(values) != int(completion.get("emitted_feature_states") or 0):
        raise ExactRefinementAuthorizationError("completion feature-state count mismatch")
    return Counter(values)


def _validate_replay_link(completion: Mapping[str, Any], replay: Mapping[str, Any]) -> None:
    if _fingerprint(replay) != completion.get("replay_fingerprint"):
        raise ExactRefinementAuthorizationError("pipeline replay differs from exact replay completion")
    if replay.get("prepared_corpus_fingerprint") != completion.get("prepared_corpus_fingerprint"):
        raise ExactRefinementAuthorizationError("pipeline replay uses a different prepared corpus")
    if replay.get("prepared_manifest_fingerprint") != completion.get("manifest_fingerprint"):
        raise ExactRefinementAuthorizationError("pipeline replay uses a different exact manifest")
    if replay.get("blind_prior_fingerprint") != completion.get("blind_prior_fingerprint"):
        raise ExactRefinementAuthorizationError("pipeline replay uses a different blind prior")
    if int(replay.get("prepared_source_count") or 0) != 26:
        raise ExactRefinementAuthorizationError("pipeline replay did not consume all 26 sources")
    if replay.get("duplicate_records"):
        raise ExactRefinementAuthorizationError("pipeline replay contains duplicate records")
    if int(replay.get("completed_mbo_event_boundaries") or 0) != int(
        completion.get("completed_mbo_event_boundaries") or 0
    ):
        raise ExactRefinementAuthorizationError("pipeline replay boundary count differs from completion")


def _validate_refine_stream(completion: Mapping[str, Any], stream: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(stream))
    if value.get("schema") != REFINE_STREAM_SCHEMA:
        raise ExactRefinementAuthorizationError("unexpected refine stream schema")
    if value.get("authority") != "REFINE_POSTERIOR_STREAM_ONLY":
        raise ExactRefinementAuthorizationError("refine stream authority is invalid")
    if value.get("execution_authority") is not False:
        raise ExactRefinementAuthorizationError("refine stream cannot grant execution authority")
    if value.get("anchor_fingerprint") != completion.get("anchor_fingerprint"):
        raise ExactRefinementAuthorizationError("refine stream uses a different Friday anchor")
    outputs = [copy.deepcopy(dict(row)) for row in value.get("outputs") or []]
    if int(value.get("n_outputs") or 0) != len(outputs):
        raise ExactRefinementAuthorizationError("refine stream n_outputs mismatch")
    if len(outputs) != int(completion.get("emitted_feature_states") or 0):
        raise ExactRefinementAuthorizationError("refine output count differs from exact feature-state count")
    observed: Counter[str] = Counter()
    dates: set[str] = set()
    previous: tuple[float, int] | None = None
    for output in outputs:
        if output.get("schema") != "ng_rt_refine_output.v1":
            raise ExactRefinementAuthorizationError("unexpected refine output schema")
        payload = copy.deepcopy(output)
        output_fp = payload.pop("output_fingerprint", None)
        if not output_fp or output_fp != _fingerprint(payload):
            raise ExactRefinementAuthorizationError("refine output fingerprint mismatch")
        if output.get("authority") != "REFINE_POSTERIOR_ONLY" or output.get("execution_authority") is not False:
            raise ExactRefinementAuthorizationError("refine output authority is invalid")
        if output.get("anchor_fingerprint") != completion.get("anchor_fingerprint"):
            raise ExactRefinementAuthorizationError("refine output uses a different Friday anchor")
        if output.get("blind_prior_fingerprint") != completion.get("blind_prior_fingerprint"):
            raise ExactRefinementAuthorizationError("refine output uses a different blind prior")
        feature_fp = str(output.get("feature_fingerprint") or "")
        if not feature_fp:
            raise ExactRefinementAuthorizationError("refine output lacks feature fingerprint")
        observed[feature_fp] += 1
        day = str(output.get("session_day") or "")
        if day not in G15_DATES:
            raise ExactRefinementAuthorizationError(f"refine output carries non-G15 day: {day!r}")
        dates.add(day)
        order = (float(output.get("as_of_event_s")), int(output.get("sequence") or 0))
        if previous is not None and order < previous:
            raise ExactRefinementAuthorizationError("refine stream moved backwards")
        previous = order
        if output.get("status") == "STAND_DOWN" and dict(output.get("posterior") or {}) != dict(
            output.get("blind_prior") or {}
        ):
            raise ExactRefinementAuthorizationError("stand-down output changed the blind prior")
    if dates != set(G15_DATES):
        missing = sorted(set(G15_DATES) - dates)
        raise ExactRefinementAuthorizationError("refine stream missing G15 days: " + ", ".join(missing))
    if observed != _completion_state_fingerprints(completion):
        raise ExactRefinementAuthorizationError("refine outputs do not map one-to-one to exact feature states")
    return value


def _validate_audit(completion: Mapping[str, Any], audit: Mapping[str, Any], blind_hash: str) -> None:
    value = copy.deepcopy(dict(audit))
    _verify_embedded_fingerprint(value, "audit_fingerprint", label="daily audit")
    if value.get("schema") != AUDIT_SCHEMA or value.get("authority") != "REFINE_AUDIT_ONLY":
        raise ExactRefinementAuthorizationError("daily audit authority is invalid")
    if value.get("execution_authority") is not False:
        raise ExactRefinementAuthorizationError("daily audit cannot grant execution authority")
    if value.get("blind_forecast_sha256") != blind_hash:
        raise ExactRefinementAuthorizationError("daily audit references a different blind forecast")
    if value.get("anchor_fingerprint") != completion.get("anchor_fingerprint"):
        raise ExactRefinementAuthorizationError("daily audit references a different anchor")
    days = [str(row.get("date") or "") for row in value.get("days") or []]
    if int(value.get("n_days") or 0) != len(G15_DATES) or days != list(G15_DATES):
        raise ExactRefinementAuthorizationError("daily audit lost canonical G15 coverage")
    if any(row.get("outcome_scored") is not False for row in value.get("days") or []):
        raise ExactRefinementAuthorizationError("causal daily audit cannot contain outcome scoring")


def _validate_lessons(audit: Mapping[str, Any], lessons: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(lessons))
    _verify_embedded_fingerprint(value, "proposal_fingerprint", label="lesson proposals")
    if value.get("schema") != LESSON_SCHEMA or value.get("authority") != "LESSON_PROPOSAL_ONLY":
        raise ExactRefinementAuthorizationError("lesson proposal authority is invalid")
    if value.get("execution_authority") is not False or value.get("may_update_ng_brain") is not False:
        raise ExactRefinementAuthorizationError("lesson proposals cannot update the brain or execute")
    if value.get("source_audit_fingerprint") != audit.get("audit_fingerprint"):
        raise ExactRefinementAuthorizationError("lesson proposals reference a different daily audit")
    for proposal in value.get("proposals") or []:
        if proposal.get("status") != "UNSCORED_CANDIDATE":
            raise ExactRefinementAuthorizationError("pre-outcome lesson must remain UNSCORED_CANDIDATE")
        if proposal.get("may_update_ng_brain") is not False:
            raise ExactRefinementAuthorizationError("proposal may not update ng_brain.json")


def build_authorization(*, completion: dict[str, Any], pipeline: dict[str, Any], blind_forecast_bytes: bytes | None = None) -> dict[str, Any]:
    """Bind an outcome-blind refinement pipeline to the exact replay completion."""
    originals = copy.deepcopy((completion, pipeline))
    completion_value = _validate_completion(completion)
    pipeline_value = _validate_pipeline_fingerprint(pipeline)
    blind_hash = _validate_blind(pipeline_value, blind_forecast_bytes)
    anchor = dict(pipeline_value.get("anchor") or {})
    if anchor.get("anchor_fingerprint") != completion_value.get("anchor_fingerprint"):
        raise ExactRefinementAuthorizationError("pipeline uses a different Friday anchor")
    replay = dict(pipeline_value.get("replay") or {})
    _validate_replay_link(completion_value, replay)
    stream = _validate_refine_stream(completion_value, dict(pipeline_value.get("refine_stream") or {}))
    audit = dict(pipeline_value.get("daily_audit") or {})
    _validate_audit(completion_value, audit, blind_hash)
    lessons = dict(pipeline_value.get("lesson_proposals") or {})
    _validate_lessons(audit, lessons)

    stand_down_days = [row["date"] for row in completion_value.get("days") or [] if row.get("stand_down_reasons")]
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": READY_WITH_STAND_DOWNS if stand_down_days else READY,
        "authority": "EXACT_G15_REFINEMENT_AUTHORIZATION_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": False,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "g16_authorized": False,
        "exact_replay_completion_fingerprint": completion_value["completion_fingerprint"],
        "pipeline_fingerprint": pipeline_value["pipeline_fingerprint"],
        "replay_fingerprint": completion_value["replay_fingerprint"],
        "manifest_fingerprint": completion_value["manifest_fingerprint"],
        "prepared_corpus_fingerprint": completion_value["prepared_corpus_fingerprint"],
        "anchor_fingerprint": completion_value["anchor_fingerprint"],
        "blind_prior_fingerprint": completion_value["blind_prior_fingerprint"],
        "blind_forecast_sha256": blind_hash,
        "refine_stream_fingerprint": _fingerprint(stream),
        "daily_audit_fingerprint": audit["audit_fingerprint"],
        "lesson_proposal_fingerprint": lessons["proposal_fingerprint"],
        "emitted_feature_states": completion_value["emitted_feature_states"],
        "posterior_outputs": stream["n_outputs"],
        "days": list(G15_DATES),
        "stand_down_days": stand_down_days,
        "authorized_next_stages": [
            "ng_g15_curve_adapter.build_refined_forecast",
            "continuous_rt.py blind and refined renders",
            "ng_g15_path_score after the refined forecast is locked",
            "ng_g15_lesson_adjudication after outcome scoring",
        ],
        "note": (
            "The causal G15 posterior is fingerprint-linked to exact matched L1+MBO replay. "
            "Outcome scoring and G16 remain unauthorized until downstream artifacts are locked."
        ),
    }
    result["authorization_fingerprint"] = _fingerprint(result)
    if (completion, pipeline) != originals:
        raise ExactRefinementAuthorizationError("authorization validation mutated source artifacts")
    return result


def validate_authorization(authorization: dict[str, Any], *, completion: dict[str, Any] | None = None, pipeline: dict[str, Any] | None = None, blind_forecast_bytes: bytes | None = None) -> None:
    value = copy.deepcopy(authorization)
    _verify_embedded_fingerprint(value, "authorization_fingerprint", label="authorization")
    if value.get("schema") != SCHEMA or value.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise ExactRefinementAuthorizationError("unexpected or non-ready authorization")
    for field in (
        "execution_authority", "actual_outcomes_used", "may_change_blind_prior",
        "may_change_blind_forecast", "may_change_posterior", "may_update_ng_brain", "g16_authorized",
    ):
        if value.get(field) is not False:
            raise ExactRefinementAuthorizationError(f"authorization must keep {field}=false")
    if value.get("days") != list(G15_DATES):
        raise ExactRefinementAuthorizationError("authorization lost canonical G15 dates")
    if completion is not None and value.get("exact_replay_completion_fingerprint") != completion.get("completion_fingerprint"):
        raise ExactRefinementAuthorizationError("authorization references a different completion")
    if pipeline is not None and value.get("pipeline_fingerprint") != pipeline.get("pipeline_fingerprint"):
        raise ExactRefinementAuthorizationError("authorization references a different pipeline")
    if blind_forecast_bytes is not None and value.get("blind_forecast_sha256") != _sha256_bytes(blind_forecast_bytes):
        raise ExactRefinementAuthorizationError("authorization references a different blind forecast")


def _fixture() -> tuple[dict[str, Any], dict[str, Any], bytes]:
    prior_fp = "prior-fp"
    feature_fps = [f"feature-{index:02d}" for index in range(len(G15_DATES))]
    replay = {
        "prepared_corpus_fingerprint": "prepared-fp",
        "prepared_manifest_fingerprint": "manifest-fp",
        "blind_prior_fingerprint": prior_fp,
        "prepared_source_count": 26,
        "completed_mbo_event_boundaries": len(feature_fps),
        "duplicate_records": [],
    }
    completion = {
        "schema": COMPLETION_SCHEMA,
        "status": "EXACT_CAUSAL_REPLAY_READY",
        "basis_status": "MATCHED_L1_MBO_READY",
        "g15_shadow_refinement_authorized": True,
        "g16_authorized": False,
        "execution_authority": False,
        "actual_outcomes_used": False,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "prepared_source_count": 26,
        "emitted_feature_states": len(feature_fps),
        "completed_mbo_event_boundaries": len(feature_fps),
        "replay_fingerprint": _fingerprint(replay),
        "manifest_fingerprint": "manifest-fp",
        "prepared_corpus_fingerprint": "prepared-fp",
        "anchor_fingerprint": "anchor-fp",
        "blind_prior_fingerprint": prior_fp,
        "days": [
            {"date": day, "state_fingerprints": [feature_fps[index]], "stand_down_reasons": {}}
            for index, day in enumerate(G15_DATES)
        ],
    }
    completion["completion_fingerprint"] = _fingerprint(completion)
    blind_bytes = b'{"group":15,"days":[]}\n'
    blind_hash = _sha256_bytes(blind_bytes)
    outputs = []
    for index, day in enumerate(G15_DATES):
        output = {
            "schema": "ng_rt_refine_output.v1",
            "authority": "REFINE_POSTERIOR_ONLY",
            "execution_authority": False,
            "session_day": day,
            "sequence": index + 1,
            "as_of_event_s": float(index + 1),
            "anchor_fingerprint": "anchor-fp",
            "blind_prior_fingerprint": prior_fp,
            "feature_fingerprint": feature_fps[index],
            "blind_prior": {"up": 0.4, "flat": 0.2, "down": 0.4},
            "posterior": {"up": 0.5, "flat": 0.2, "down": 0.3},
            "status": "UPDATED",
        }
        output["output_fingerprint"] = _fingerprint(output)
        outputs.append(output)
    stream = {
        "schema": REFINE_STREAM_SCHEMA,
        "authority": "REFINE_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "anchor_fingerprint": "anchor-fp",
        "n_outputs": len(outputs),
        "outputs": outputs,
    }
    audit = {
        "schema": AUDIT_SCHEMA,
        "authority": "REFINE_AUDIT_ONLY",
        "execution_authority": False,
        "blind_forecast_sha256": blind_hash,
        "anchor_fingerprint": "anchor-fp",
        "n_days": len(G15_DATES),
        "days": [{"date": day, "outcome_scored": False} for day in G15_DATES],
    }
    audit["audit_fingerprint"] = _fingerprint(audit)
    lessons = {
        "schema": LESSON_SCHEMA,
        "authority": "LESSON_PROPOSAL_ONLY",
        "execution_authority": False,
        "may_update_ng_brain": False,
        "source_audit_fingerprint": audit["audit_fingerprint"],
        "proposals": [{"id": "g15_mbo.signed_flow", "status": "UNSCORED_CANDIDATE", "may_update_ng_brain": False}],
    }
    lessons["proposal_fingerprint"] = _fingerprint(lessons)
    pipeline = {
        "schema": PIPELINE_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "HISTORICAL_REFINE_PIPELINE_ONLY",
        "execution_authority": False,
        "blind_forecast": {"sha256_before": blind_hash, "sha256_after": blind_hash, "byte_identical": True},
        "anchor": {"anchor_fingerprint": "anchor-fp"},
        "replay": replay,
        "refine_stream": stream,
        "daily_audit": audit,
        "lesson_proposals": lessons,
        "gates": {
            "actual_outcome_scoring_complete": False,
            "refined_curve_complete": False,
            "continuous_rt_renders_complete": False,
            "g16_authorized": False,
        },
    }
    pipeline["pipeline_fingerprint"] = _fingerprint(pipeline)
    return completion, pipeline, blind_bytes


def selftest() -> int:
    completion, pipeline, blind_bytes = _fixture()
    result = build_authorization(completion=completion, pipeline=pipeline, blind_forecast_bytes=blind_bytes)
    assert result["status"] == READY
    assert result["posterior_outputs"] == len(G15_DATES)
    assert result["g16_authorized"] is False
    validate_authorization(result, completion=completion, pipeline=pipeline, blind_forecast_bytes=blind_bytes)
    print("[ng_g15_exact_refinement_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind G15 refinement to exact matched L1+MBO replay")
    parser.add_argument("--completion", type=Path)
    parser.add_argument("--pipeline", type=Path)
    parser.add_argument("--blind-forecast", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(value is None for value in (args.completion, args.pipeline, args.blind_forecast, args.out)):
        parser.error("--completion, --pipeline, --blind-forecast, and --out are required")
    result = build_authorization(
        completion=json.loads(args.completion.read_text(encoding="utf-8")),
        pipeline=json.loads(args.pipeline.read_text(encoding="utf-8")),
        blind_forecast_bytes=args.blind_forecast.read_bytes(),
    )
    validate_authorization(result)
    _atomic_json(args.out, result)
    print(json.dumps({
        "status": result["status"], "days": len(result["days"]),
        "posterior_outputs": result["posterior_outputs"],
        "stand_down_days": result["stand_down_days"],
        "fingerprint": result["authorization_fingerprint"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
