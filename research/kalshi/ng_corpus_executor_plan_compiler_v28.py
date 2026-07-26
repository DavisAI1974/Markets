#!/usr/bin/env python3
"""Compile the durable historical plan through G15 attribution-bound publication v33.

The v32 compiler arms the complete outcome-blind G15 path through exact replay,
refinement, six-factor attribution, and attribution authorization. This v33 compiler
adds canonical command bindings for fixed-outcome publication, recursive attribution-
to-score binding, and scored counterfactual lesson adjudication. Those fixed-outcome
stages remain disabled in the compiled plan and are never armed by the historical
prefix arm. G16 outcomes, execution, options, and ng_brain.json writes remain forbidden.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v27 as v27
import ng_g15_attribution_bound_publication_gate as bound_gate
import ng_g15_counterfactual_lesson_gate as lesson_gate
import ng_g15_exact_publication_gate as publication_gate
import ng_historical_refinement_executor_v29 as executor
import ng_historical_refinement_readiness_v33 as readiness

SCHEMA = "ng_corpus_executor_plan_compiler.v28"
STATUS = "G15_ATTRIBUTION_BOUND_PUBLICATION_EXECUTOR_PLAN_COMPILED"
PRE_OUTCOME_STAGES = tuple(v27.CONFIGURED_STAGES)
CONFIGURED_STAGES = (
    *PRE_OUTCOME_STAGES,
    "g15_publication",
    "g15_attribution_bound_publication",
    "g15_counterfactual_lesson_gate",
)


class CorpusExecutorPlanCompilerV28Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExecutorPlanCompilerV28Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExecutorPlanCompilerV28Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        v27._authority(value, label=label)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV28Error(str(error)) from error


def _validate_fixed_outcome_chain(
    *,
    upstream_receipt: Mapping[str, Any],
    publication: Mapping[str, Any],
    bound_publication: Mapping[str, Any],
    blind_score: Mapping[str, Any],
    refined_score: Mapping[str, Any],
    comparison: Mapping[str, Any],
    daily_audit: Mapping[str, Any],
    counterfactual_lessons: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        publication_gate.validate_completion(publication)
        bound_gate.validate_gate(bound_publication)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV28Error(
            f"G15 publication binding chain is invalid: {error}"
        ) from error

    attribution_authorization = upstream_receipt.get(
        "g15_counterfactual_attribution_authorization"
    )
    replay = upstream_receipt.get("g15_replay")
    anchor = upstream_receipt.get("g15_anchor")
    refine_stream = upstream_receipt.get("g15_refine_stream")
    attribution = upstream_receipt.get("g15_counterfactual_attribution")
    if not all(
        isinstance(item, Mapping)
        for item in (
            attribution_authorization,
            replay,
            anchor,
            refine_stream,
            attribution,
        )
    ):
        raise CorpusExecutorPlanCompilerV28Error(
            "v32 compiler receipt lacks exact G15 attribution provenance"
        )

    embedded = {
        "attribution_authorization": attribution_authorization,
        "publication_completion": publication,
        "blind_score": blind_score,
        "refined_score": refined_score,
        "comparison": comparison,
    }
    for field, expected in embedded.items():
        if bound_publication.get(field) != dict(expected):
            raise CorpusExecutorPlanCompilerV28Error(
                f"attribution-bound publication embeds a different {field}"
            )

    try:
        lesson_gate.validate_gate(
            counterfactual_lessons,
            replay=replay,
            anchor=anchor,
            refine_stream=refine_stream,
            attribution=attribution,
            audit=daily_audit,
            comparison=comparison,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV28Error(
            f"G15 counterfactual lesson adjudication is invalid: {error}"
        ) from error

    required_bound = {
        "attribution_authorization_bound_to_publication": True,
        "publication_opened_after_attribution_authorization": True,
        "separate_blind_refined_scores_verified": True,
        "score_artifacts_distinct": True,
        "score_actual_substrate_shared": True,
        "all_six_factors_authorized_before_scoring": True,
        "lesson_proposals_brain_write_forbidden": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "g16_outcome_access_authorized": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    for field, expected in required_bound.items():
        if bound_publication.get(field) != expected:
            raise CorpusExecutorPlanCompilerV28Error(
                f"attribution-bound publication field mismatch: {field}"
            )

    required_lessons = {
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_select_lessons_from_g15_scores": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "G16_PRE_CUTOFF_SHADOW_REGISTRATION",
    }
    for field, expected in required_lessons.items():
        if counterfactual_lessons.get(field) != expected:
            raise CorpusExecutorPlanCompilerV28Error(
                f"counterfactual lesson field mismatch: {field}"
            )

    if bound_publication.get("publication_completion_fingerprint") != publication.get(
        "completion_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV28Error(
            "bound publication references a different publication completion"
        )
    if bound_publication.get("blind_score_fingerprint") != blind_score.get(
        "artifact_fingerprint"
    ) or bound_publication.get("refined_score_fingerprint") != refined_score.get(
        "artifact_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV28Error(
            "bound publication references different blind/refined scorecards"
        )
    if bound_publication.get("comparison_fingerprint") != comparison.get(
        "artifact_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV28Error(
            "bound publication references a different score comparison"
        )
    lesson_source = dict(counterfactual_lessons.get("source") or {})
    if lesson_source.get("comparison_fingerprint") != comparison.get(
        "artifact_fingerprint"
    ):
        raise CorpusExecutorPlanCompilerV28Error(
            "counterfactual lessons reference a different score comparison"
        )
    if lesson_source.get("counterfactual_fingerprint") != attribution.get("fingerprint"):
        raise CorpusExecutorPlanCompilerV28Error(
            "counterfactual lessons reference a different six-factor attribution"
        )
    if bound_publication.get("attribution_fingerprint") != attribution.get("fingerprint"):
        raise CorpusExecutorPlanCompilerV28Error(
            "bound publication references a different six-factor attribution"
        )

    _authority(bound_publication, label="attribution-bound publication")
    _authority(counterfactual_lessons, label="counterfactual lesson adjudication")
    return {
        "publication": copy.deepcopy(dict(publication)),
        "bound_publication": copy.deepcopy(dict(bound_publication)),
        "blind_score": copy.deepcopy(dict(blind_score)),
        "refined_score": copy.deepcopy(dict(refined_score)),
        "comparison": copy.deepcopy(dict(comparison)),
        "daily_audit": copy.deepcopy(dict(daily_audit)),
        "counterfactual_lessons": copy.deepcopy(dict(counterfactual_lessons)),
        "publication_fingerprint": publication.get("completion_fingerprint"),
        "bound_publication_fingerprint": bound_publication.get("fingerprint"),
        "blind_score_fingerprint": blind_score.get("artifact_fingerprint"),
        "refined_score_fingerprint": refined_score.get("artifact_fingerprint"),
        "comparison_fingerprint": comparison.get("artifact_fingerprint"),
        "daily_audit_fingerprint": daily_audit.get("audit_fingerprint"),
        "counterfactual_lessons_fingerprint": counterfactual_lessons.get("fingerprint"),
        "g16_registry_fingerprint": (
            (counterfactual_lessons.get("adjudication") or {})
            .get("g16_shadow_registry", {})
            .get("registry_fingerprint")
        ),
    }


def _commands(
    *,
    publication_authorization_path: Path,
    blind_forecast_path: Path,
    refined_forecast_path: Path,
    actual_path: Path,
    blind_score_path: Path,
    refined_score_path: Path,
    comparison_path: Path,
    publication_adjudication_path: Path,
    blind_render_rt_path: Path,
    refined_render_rt_path: Path,
    blind_render_png_path: Path,
    refined_render_png_path: Path,
    publication_path: Path,
    attribution_authorization_path: Path,
    bound_publication_path: Path,
    replay_path: Path,
    anchor_path: Path,
    refine_stream_path: Path,
    attribution_path: Path,
    daily_audit_path: Path,
    proposals_out_path: Path,
    counterfactual_adjudication_out_path: Path,
    counterfactual_lessons_path: Path,
    **upstream_kwargs: Any,
) -> dict[str, list[str]]:
    commands = v27._commands(**upstream_kwargs)
    commands["g15_publication"] = [
        "python",
        "ng_g15_exact_publication_gate.py",
        "--authorization",
        str(publication_authorization_path.resolve(strict=False)),
        "--blind",
        str(blind_forecast_path.resolve(strict=False)),
        "--refined",
        str(refined_forecast_path.resolve(strict=False)),
        "--actual",
        str(actual_path.resolve(strict=False)),
        "--blind-score",
        str(blind_score_path.resolve(strict=False)),
        "--refined-score",
        str(refined_score_path.resolve(strict=False)),
        "--comparison",
        str(comparison_path.resolve(strict=False)),
        "--adjudication",
        str(publication_adjudication_path.resolve(strict=False)),
        "--blind-render-rt",
        str(blind_render_rt_path.resolve(strict=False)),
        "--refined-render-rt",
        str(refined_render_rt_path.resolve(strict=False)),
        "--blind-render-png",
        str(blind_render_png_path.resolve(strict=False)),
        "--refined-render-png",
        str(refined_render_png_path.resolve(strict=False)),
        "--out",
        str(publication_path.resolve(strict=False)),
    ]
    commands["g15_attribution_bound_publication"] = [
        "python",
        "ng_g15_attribution_bound_publication_gate.py",
        "--attribution-authorization",
        str(attribution_authorization_path.resolve(strict=False)),
        "--publication",
        str(publication_path.resolve(strict=False)),
        "--blind-score",
        str(blind_score_path.resolve(strict=False)),
        "--refined-score",
        str(refined_score_path.resolve(strict=False)),
        "--comparison",
        str(comparison_path.resolve(strict=False)),
        "--out",
        str(bound_publication_path.resolve(strict=False)),
    ]
    commands["g15_counterfactual_lesson_gate"] = [
        "python",
        "ng_g15_counterfactual_lesson_gate.py",
        "--replay",
        str(replay_path.resolve(strict=False)),
        "--anchor",
        str(anchor_path.resolve(strict=False)),
        "--refine-stream",
        str(refine_stream_path.resolve(strict=False)),
        "--attribution",
        str(attribution_path.resolve(strict=False)),
        "--audit",
        str(daily_audit_path.resolve(strict=False)),
        "--comparison",
        str(comparison_path.resolve(strict=False)),
        "--proposals-out",
        str(proposals_out_path.resolve(strict=False)),
        "--adjudication-out",
        str(counterfactual_adjudication_out_path.resolve(strict=False)),
        "--out",
        str(counterfactual_lessons_path.resolve(strict=False)),
    ]
    return {key: commands[key] for key in CONFIGURED_STAGES}


def _validate_plan(
    plan: Mapping[str, Any], commands: Mapping[str, list[str]], *, compiled: bool
) -> dict[str, Mapping[str, Any]]:
    try:
        executor.validate_plan(plan)
    except Exception as error:
        raise CorpusExecutorPlanCompilerV28Error(str(error)) from error
    rows_list = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows_list]
    expected_order = [spec.key for spec in readiness.STAGES]
    if keys != expected_order:
        raise CorpusExecutorPlanCompilerV28Error(
            "compiled plan does not use the readiness-v33 stage order"
        )
    if list(CONFIGURED_STAGES) != expected_order[: len(CONFIGURED_STAGES)]:
        raise CorpusExecutorPlanCompilerV28Error(
            "configured stages are not the exact readiness-v33 prefix through lessons"
        )
    rows = {str(row.get("key")): row for row in rows_list}
    for key in CONFIGURED_STAGES:
        row = rows.get(key)
        if not isinstance(row, Mapping):
            raise CorpusExecutorPlanCompilerV28Error(f"configured stage missing: {key}")
        if row.get("argv") != commands[key]:
            raise CorpusExecutorPlanCompilerV28Error(f"{key}: command vector mismatch")
        if compiled:
            expected_enabled = key == "corpus_expected_day_contract"
            if row.get("enabled") is not expected_enabled:
                raise CorpusExecutorPlanCompilerV28Error(
                    f"{key}: compiled enablement mismatch"
                )

    for key in PRE_OUTCOME_STAGES:
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise CorpusExecutorPlanCompilerV28Error(f"{key}: must remain pre-outcome")
    for key in (
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ):
        if rows[key].get("requires_fixed_outcomes") is not True:
            raise CorpusExecutorPlanCompilerV28Error(
                f"{key}: must remain behind the fixed-outcome boundary"
            )

    tail = [
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ]
    start = keys.index(tail[0])
    if keys[start : start + len(tail)] != tail:
        raise CorpusExecutorPlanCompilerV28Error(
            "G15 attribution/publication/lesson chronology was changed"
        )
    expected_contracts = {
        "g15_publication": (
            "g15_exact_publication_completion.json",
            ["python", "ng_g15_exact_publication_gate.py"],
        ),
        "g15_attribution_bound_publication": (
            "g15_attribution_bound_publication_gate.json",
            ["python", "ng_g15_attribution_bound_publication_gate.py"],
        ),
    }
    for key, (output, entrypoint) in expected_contracts.items():
        if rows[key].get("expected_output") != output:
            raise CorpusExecutorPlanCompilerV28Error(f"{key}: artifact was substituted")
        if rows[key].get("suggested_entrypoint") != entrypoint:
            raise CorpusExecutorPlanCompilerV28Error(f"{key}: entrypoint was substituted")
    if compiled and plan.get("outcome_paths") != []:
        raise CorpusExecutorPlanCompilerV28Error(
            "compiled plan must not expose fixed G15 outcome paths"
        )
    return rows


def build_compiled_plan(
    *,
    artifact_dir: Path,
    working_directory: Path,
    upstream_build_kwargs: Mapping[str, Path],
    publication_authorization_path: Path,
    blind_forecast_path: Path,
    refined_forecast_path: Path,
    actual_path: Path,
    blind_score_path: Path,
    refined_score_path: Path,
    comparison_path: Path,
    publication_adjudication_path: Path,
    blind_render_rt_path: Path,
    refined_render_rt_path: Path,
    blind_render_png_path: Path,
    refined_render_png_path: Path,
    publication_path: Path,
    attribution_authorization_path: Path,
    bound_publication_path: Path,
    replay_path: Path,
    anchor_path: Path,
    refine_stream_path: Path,
    attribution_path: Path,
    daily_audit_path: Path,
    proposals_out_path: Path,
    counterfactual_adjudication_out_path: Path,
    counterfactual_lessons_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    upstream_plan, upstream_receipt = v27.build_compiled_plan(
        artifact_dir=artifact_dir,
        working_directory=working_directory,
        **dict(upstream_build_kwargs),
    )
    fixed = _validate_fixed_outcome_chain(
        upstream_receipt=upstream_receipt,
        publication=_load(publication_path),
        bound_publication=_load(bound_publication_path),
        blind_score=_load(blind_score_path),
        refined_score=_load(refined_score_path),
        comparison=_load(comparison_path),
        daily_audit=_load(daily_audit_path),
        counterfactual_lessons=_load(counterfactual_lessons_path),
    )
    commands = _commands(
        publication_authorization_path=publication_authorization_path,
        blind_forecast_path=blind_forecast_path,
        refined_forecast_path=refined_forecast_path,
        actual_path=actual_path,
        blind_score_path=blind_score_path,
        refined_score_path=refined_score_path,
        comparison_path=comparison_path,
        publication_adjudication_path=publication_adjudication_path,
        blind_render_rt_path=blind_render_rt_path,
        refined_render_rt_path=refined_render_rt_path,
        blind_render_png_path=blind_render_png_path,
        refined_render_png_path=refined_render_png_path,
        publication_path=publication_path,
        attribution_authorization_path=attribution_authorization_path,
        bound_publication_path=bound_publication_path,
        replay_path=replay_path,
        anchor_path=anchor_path,
        refine_stream_path=refine_stream_path,
        attribution_path=attribution_path,
        daily_audit_path=daily_audit_path,
        proposals_out_path=proposals_out_path,
        counterfactual_adjudication_out_path=counterfactual_adjudication_out_path,
        counterfactual_lessons_path=counterfactual_lessons_path,
        **dict(upstream_build_kwargs),
    )
    plan = executor.build_plan(artifact_dir, working_directory)
    for key in CONFIGURED_STAGES:
        plan = executor.configure_stage(
            plan,
            key,
            commands[key],
            enabled=key == "corpus_expected_day_contract",
        )
    _validate_plan(plan, commands, compiled=True)

    upstream_commands = {
        str(row["key"]): list(row.get("argv") or [])
        for row in upstream_plan.get("stages") or []
        if str(row.get("key")) in v27.CONFIGURED_STAGES
    }
    receipt: dict[str, Any] = {
        **copy.deepcopy(upstream_receipt),
        "schema": SCHEMA,
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan["fingerprint"],
        "commands_fingerprint": fingerprinting._fp(commands),
        "configured_stages": list(CONFIGURED_STAGES),
        "pre_outcome_armed_stages": list(PRE_OUTCOME_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "upstream_v32_compiler_receipt": copy.deepcopy(upstream_receipt),
        "upstream_v32_execution_plan": copy.deepcopy(upstream_plan),
        "upstream_v32_commands": copy.deepcopy(upstream_commands),
        **{
            key: value
            for key, value in fixed.items()
            if key
            not in {
                "publication",
                "bound_publication",
                "blind_score",
                "refined_score",
                "comparison",
                "daily_audit",
                "counterfactual_lessons",
            }
        },
        "g15_publication_completion": fixed["publication"],
        "g15_attribution_bound_publication": fixed["bound_publication"],
        "g15_blind_score": fixed["blind_score"],
        "g15_refined_score": fixed["refined_score"],
        "g15_score_comparison": fixed["comparison"],
        "g15_daily_audit": fixed["daily_audit"],
        "g15_counterfactual_lessons": fixed["counterfactual_lessons"],
        "g15_attribution_authorization_before_publication_required": True,
        "g15_separate_blind_refined_scores_required": True,
        "g15_publication_binding_before_lessons_required": True,
        "g15_lesson_support_locked_before_scoring": True,
        "g15_lessons_cannot_update_ng_brain": True,
        "fixed_outcome_stages_configured_but_disabled": True,
        "g16_outcome_access_forbidden": True,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_V33_PRE_OUTCOME_PREFIX",
    }
    receipt.pop("fingerprint", None)
    receipt["fingerprint"] = fingerprinting._fp(receipt)
    validate_receipt(receipt, plan=plan, commands=commands, verify_files=False)
    return plan, receipt


def validate_receipt(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    commands: Mapping[str, list[str]],
    verify_files: bool = True,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != fingerprinting._fp(checked):
        raise CorpusExecutorPlanCompilerV28Error(
            "compiler v28 receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="compiler v28 receipt")
    _validate_plan(plan, commands, compiled=True)
    expected = {
        "status": STATUS,
        "readiness_contract": readiness.SCHEMA,
        "readiness_stage_contract_fingerprint": fingerprinting._fp(
            [spec.key for spec in readiness.STAGES]
        ),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "commands_fingerprint": fingerprinting._fp(commands),
        "configured_stages": list(CONFIGURED_STAGES),
        "pre_outcome_armed_stages": list(PRE_OUTCOME_STAGES),
        "enabled_stage": "corpus_expected_day_contract",
        "g15_attribution_authorization_before_publication_required": True,
        "g15_separate_blind_refined_scores_required": True,
        "g15_publication_binding_before_lessons_required": True,
        "g15_lesson_support_locked_before_scoring": True,
        "g15_lessons_cannot_update_ng_brain": True,
        "fixed_outcome_stages_configured_but_disabled": True,
        "g16_outcome_access_forbidden": True,
    }
    for field, expected_value in expected.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV28Error(
                f"compiler v28 field mismatch: {field}"
            )

    fixed_names = (
        "g15_publication_completion",
        "g15_attribution_bound_publication",
        "g15_blind_score",
        "g15_refined_score",
        "g15_score_comparison",
        "g15_daily_audit",
        "g15_counterfactual_lessons",
    )
    if not all(isinstance(checked.get(name), Mapping) for name in fixed_names):
        raise CorpusExecutorPlanCompilerV28Error(
            "compiler v28 lacks embedded fixed-outcome G15 provenance"
        )
    upstream_receipt = checked.get("upstream_v32_compiler_receipt")
    upstream_plan = checked.get("upstream_v32_execution_plan")
    upstream_commands = checked.get("upstream_v32_commands")
    if not isinstance(upstream_receipt, Mapping) or not isinstance(
        upstream_plan, Mapping
    ) or not isinstance(upstream_commands, Mapping):
        raise CorpusExecutorPlanCompilerV28Error(
            "compiler v28 lacks embedded v32 compiler provenance"
        )
    try:
        v27.validate_receipt(
            upstream_receipt,
            plan=upstream_plan,
            commands={str(key): list(argv) for key, argv in upstream_commands.items()},
            verify_files=verify_files,
        )
    except Exception as error:
        raise CorpusExecutorPlanCompilerV28Error(
            f"embedded v32 compiler provenance is invalid: {error}"
        ) from error
    fixed = _validate_fixed_outcome_chain(
        upstream_receipt=upstream_receipt,
        publication=checked["g15_publication_completion"],
        bound_publication=checked["g15_attribution_bound_publication"],
        blind_score=checked["g15_blind_score"],
        refined_score=checked["g15_refined_score"],
        comparison=checked["g15_score_comparison"],
        daily_audit=checked["g15_daily_audit"],
        counterfactual_lessons=checked["g15_counterfactual_lessons"],
    )
    fingerprint_fields = {
        "publication_fingerprint": fixed["publication_fingerprint"],
        "bound_publication_fingerprint": fixed["bound_publication_fingerprint"],
        "blind_score_fingerprint": fixed["blind_score_fingerprint"],
        "refined_score_fingerprint": fixed["refined_score_fingerprint"],
        "comparison_fingerprint": fixed["comparison_fingerprint"],
        "daily_audit_fingerprint": fixed["daily_audit_fingerprint"],
        "counterfactual_lessons_fingerprint": fixed[
            "counterfactual_lessons_fingerprint"
        ],
        "g16_registry_fingerprint": fixed["g16_registry_fingerprint"],
    }
    for field, expected_value in fingerprint_fields.items():
        if checked.get(field) != expected_value:
            raise CorpusExecutorPlanCompilerV28Error(
                f"compiler v28 fixed-outcome lineage mismatch: {field}"
            )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    config = _load(args.config)
    try:
        upstream_build_kwargs = {
            key: Path(value) for key, value in config["upstream_build_kwargs"].items()
        }
        fixed_kwargs = {
            key: Path(value)
            for key, value in config.items()
            if key not in {"upstream_build_kwargs", "artifact_dir", "working_directory"}
        }
        plan, receipt = build_compiled_plan(
            artifact_dir=Path(config["artifact_dir"]),
            working_directory=Path(config["working_directory"]),
            upstream_build_kwargs=upstream_build_kwargs,
            **fixed_kwargs,
        )
    except (KeyError, TypeError) as error:
        raise CorpusExecutorPlanCompilerV28Error(
            f"invalid compiler v28 config: {error}"
        ) from error
    _write(args.plan_out, plan)
    _write(args.receipt_out, receipt)
    print(json.dumps({"status": receipt["status"], "plan": str(args.plan_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
