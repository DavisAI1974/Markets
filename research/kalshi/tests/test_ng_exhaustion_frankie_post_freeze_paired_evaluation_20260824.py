from __future__ import annotations

from dataclasses import replace

import pytest

from research.kalshi.ng_exhaustion_frankie_post_freeze_paired_evaluation_20260824 import (
    AnswerKind,
    EvaluationPolicy,
    FrozenLaneMovie,
    FrozenLaneObservation,
    LaneId,
    PostRevealMetaLoopMovie,
    PostRevealMetaLoopObservation,
    ReconciliationError,
    ResourceUsage,
    Step1Answer,
    evaluate_frozen_pair,
    freeze_complete_pair,
    reveal_step1_answers,
)


RUN = "october-full-stack"
HEX = "0123456789abcdef"


def usage(multiplier: float = 1.0) -> ResourceUsage:
    return ResourceUsage(
        provider_calls=multiplier,
        input_tokens=100.0 * multiplier,
        output_tokens=20.0 * multiplier,
        provider_cost_usd=0.01 * multiplier,
        retrieval_queries=2.0 * multiplier,
        retrieval_bytes=1_000.0 * multiplier,
        retrieval_cost_usd=0.002 * multiplier,
    )


def observation(
    opportunity_id: str,
    cutoff: float,
    identity_index: int,
    *,
    candidates: tuple[str, ...] = (),
    probability: float | None = None,
    abstained: bool = False,
    first_lock_id: str | None = None,
    row_usage: ResourceUsage | None = None,
    components: dict[str, ResourceUsage] | None = None,
) -> FrozenLaneObservation:
    return FrozenLaneObservation.create(
        opportunity_id=opportunity_id,
        causal_cutoff=cutoff,
        causal_prefix_hash=HEX[identity_index] * 64,
        state_prefix_hash=HEX[identity_index + 1] * 64,
        candidate_ids=candidates,
        target_probability=probability,
        abstained=abstained,
        first_lock_id=first_lock_id,
        usage=row_usage or usage(),
        component_usage=components or {},
    )


PREFIXES = (
    ("d1", 10.0, 1),
    ("d1", 14.0, 2),
    ("d2", 30.0, 3),
    ("d2", 32.0, 4),
    ("false", 40.0, 5),
    ("stopped", 50.0, 6),
    ("negative", 60.0, 7),
)


def control_rows() -> tuple[FrozenLaneObservation, ...]:
    return (
        observation("d1", 10.0, 1, probability=0.4),
        observation("d1", 14.0, 2, candidates=("D1",), probability=0.8, first_lock_id="control-d1"),
        observation("d2", 30.0, 3, probability=0.3),
        observation("d2", 32.0, 4, probability=0.4),
        observation("false", 40.0, 5, candidates=("NOISE",), probability=0.6, first_lock_id="control-false"),
        observation("stopped", 50.0, 6, candidates=("NOISE2",), probability=0.7, first_lock_id="control-stopped"),
        observation("negative", 60.0, 7, probability=0.1),
    )


def combined_rows() -> tuple[FrozenLaneObservation, ...]:
    component_usage = {
        "S137": usage(0.6),
        "HIPPORAG": usage(0.8),
        "V4_ENGINEERING": usage(0.6),
    }
    return (
        observation("d1", 10.0, 1, candidates=("D1",), probability=0.8, first_lock_id="shadow-d1", row_usage=usage(2), components=component_usage),
        observation("d1", 14.0, 2, probability=0.9, row_usage=usage(2), components=component_usage),
        observation("d2", 30.0, 3, probability=0.7, row_usage=usage(2), components=component_usage),
        observation("d2", 32.0, 4, candidates=("D2",), probability=0.9, first_lock_id="shadow-d2", row_usage=usage(2), components=component_usage),
        observation("false", 40.0, 5, abstained=True, row_usage=usage(2), components=component_usage),
        observation("stopped", 50.0, 6, probability=0.1, row_usage=usage(2), components=component_usage),
        observation("negative", 60.0, 7, probability=0.1, row_usage=usage(2), components=component_usage),
    )


def movie(
    lane: LaneId,
    rows: tuple[FrozenLaneObservation, ...],
    *,
    complete: bool = True,
) -> FrozenLaneMovie:
    return FrozenLaneMovie.create(
        run_id=RUN,
        lane=lane,
        rows=rows,
        expected_prefix_count=len(PREFIXES),
        complete=complete,
        frozen_at=100.0,
    )


def answers():
    return (
        Step1Answer("d1", AnswerKind.D_TARGET, 12.0, ("D1",)),
        Step1Answer("d2", AnswerKind.D_TARGET, 31.0, ("D2",)),
        Step1Answer("false", AnswerKind.FALSE_CONTEXT, None, ()),
        Step1Answer("stopped", AnswerKind.STOPPED_CHAIN_CONTROL, None, ()),
        Step1Answer("negative", AnswerKind.NEGATIVE_CONTROL, None, ()),
    )


def frozen_inputs():
    control = movie(LaneId.S135_CONTROL, control_rows())
    combined = movie(LaneId.FULL_PROVISIONAL_COMBINED, combined_rows())
    receipt = freeze_complete_pair(control, combined, completed_at=101.0)
    revealed = reveal_step1_answers(receipt, answers(), revealed_at=102.0)
    return control, combined, receipt, revealed


def test_global_freeze_requires_both_complete_movies_and_identical_prefix_roster() -> None:
    control = movie(LaneId.S135_CONTROL, control_rows(), complete=False)
    combined = movie(LaneId.FULL_PROVISIONAL_COMBINED, combined_rows())
    with pytest.raises(ReconciliationError, match="both lane movies must be complete"):
        freeze_complete_pair(control, combined, completed_at=101.0)

    wrong_rows = list(combined_rows())
    wrong_rows[0] = observation("d1", 10.0, 8, candidates=("D1",), probability=0.8)
    mismatched = movie(LaneId.FULL_PROVISIONAL_COMBINED, tuple(wrong_rows))
    with pytest.raises(ReconciliationError, match="identical prefix roster"):
        freeze_complete_pair(movie(LaneId.S135_CONTROL, control_rows()), mismatched, completed_at=101.0)


def test_step1_answer_wall_requires_global_freeze_and_post_freeze_access_time() -> None:
    control = movie(LaneId.S135_CONTROL, control_rows())
    combined = movie(LaneId.FULL_PROVISIONAL_COMBINED, combined_rows())

    with pytest.raises(ReconciliationError, match="global paired freeze receipt"):
        reveal_step1_answers(None, answers(), revealed_at=102.0)

    receipt = freeze_complete_pair(control, combined, completed_at=101.0)
    with pytest.raises(ReconciliationError, match="after global freeze"):
        reveal_step1_answers(receipt, answers(), revealed_at=100.5)


def test_primary_evaluation_is_control_vs_all_provisional_combined_only() -> None:
    control, combined, receipt, revealed = frozen_inputs()
    report = evaluate_frozen_pair(
        control,
        combined,
        receipt,
        revealed,
        policy=EvaluationPolicy(early_onset_window_seconds=2.0, confidence_z=1.96, calibration_bins=2),
    )

    assert report["comparison"] == {
        "control_lane": "S135_CONTROL",
        "combined_lane": "FULL_PROVISIONAL_COMBINED",
        "primary_test": "S135_CONTROL_VS_FULL_PROVISIONAL_COMBINED",
    }
    control_metrics = report["lanes"]["S135_CONTROL"]
    combined_metrics = report["lanes"]["FULL_PROVISIONAL_COMBINED"]
    assert control_metrics["recognition"]["candidate_matches"] == 1
    assert control_metrics["recognition"]["recall"] == 0.5
    assert control_metrics["recognition"]["precision"] == pytest.approx(1 / 3)
    assert combined_metrics["recognition"]["candidate_matches"] == 2
    assert combined_metrics["recognition"]["recall"] == 1.0
    assert combined_metrics["recognition"]["precision"] == 1.0
    assert control_metrics["timing"]["pre_onset_detections"] == 0
    assert control_metrics["timing"]["early_onset_detections"] == 1
    assert combined_metrics["timing"]["pre_onset_detections"] == 1
    assert combined_metrics["timing"]["early_onset_detections"] == 1
    assert combined_metrics["timing"]["sign_convention"] == "NEGATIVE_IS_LEAD_POSITIVE_IS_LAG"
    assert control_metrics["controls"]["FALSE_CONTEXT"]["detections"] == 1
    assert control_metrics["controls"]["STOPPED_CHAIN_CONTROL"]["detections"] == 1
    assert combined_metrics["controls"]["FALSE_CONTEXT"]["detections"] == 0
    assert combined_metrics["prediction"]["brier_score"] < control_metrics["prediction"]["brier_score"]
    assert combined_metrics["prediction"]["log_loss"] < control_metrics["prediction"]["log_loss"]
    assert combined_metrics["prediction"]["calibration"]["status"] == "DESCRIPTIVE_ONLY"
    assert combined_metrics["coverage"]["prefix_abstentions"] == 1

    deltas = report["paired_deltas"]
    assert deltas["target_detection_rate"]["n_pairs"] == 2
    assert deltas["target_detection_rate"]["estimate_combined_minus_control"] == 0.5
    assert deltas["brier_loss"]["estimate_combined_minus_control"] < 0
    assert deltas["provider_cost_usd"]["n_pairs"] == 5
    assert "standard_error" in deltas["brier_loss"]
    assert deltas["first_detection_seconds_vs_onset"]["n_pairs"] == 1

    attribution = report["component_telemetry"]
    assert set(attribution["FULL_PROVISIONAL_COMBINED"]) == {"S137", "HIPPORAG", "V4_ENGINEERING"}
    assert attribution["interpretation"] == "COST_ATTRIBUTION_ONLY_NOT_COMPONENT_ABLATIONS"
    assert report["promotion_authority"] == "NONE"
    assert report["automatic_promotion"] is False
    assert report["significance_claim"] == "NOT_TESTED"
    assert report["predictive_success_claim"] == "NOT_MADE"


def test_evaluation_rejects_movie_substitution_after_freeze() -> None:
    control, combined, receipt, revealed = frozen_inputs()
    substituted = replace(combined, movie_hash="f" * 64)
    with pytest.raises(ReconciliationError, match="movie hash mismatch"):
        evaluate_frozen_pair(
            control,
            substituted,
            receipt,
            revealed,
            policy=EvaluationPolicy(2.0),
        )

    authority_substitution = replace(combined, can_promote=True)
    with pytest.raises(ReconciliationError, match="movie hash mismatch"):
        evaluate_frozen_pair(
            control,
            authority_substitution,
            receipt,
            revealed,
            policy=EvaluationPolicy(2.0),
        )


def test_post_reveal_meta_loop_is_separate_and_cannot_rewrite_shadow_first_locks() -> None:
    control, combined, receipt, revealed = frozen_inputs()
    lock_by_opportunity = {
        "d1": "shadow-d1",
        "d2": "shadow-d2",
        "false": None,
        "stopped": None,
        "negative": None,
    }
    records = tuple(
        PostRevealMetaLoopObservation.create(
            opportunity_id=answer.opportunity_id,
            executed_at=103.0,
            candidate_ids=answer.candidate_ids,
            target_probability=0.9 if answer.kind is AnswerKind.D_TARGET else 0.1,
            abstained=False,
            observed_frozen_first_lock_id=lock_by_opportunity[answer.opportunity_id],
            rewrites_frozen_first_lock=False,
            usage=usage(0.5),
        )
        for answer in answers()
    )
    meta = PostRevealMetaLoopMovie.create(
        run_id=RUN,
        source_shadow_movie_hash=combined.movie_hash,
        frozen_shadow_first_lock_roster_hash=combined.first_lock_roster_hash,
        observations=records,
        expected_opportunity_count=5,
        complete=True,
    )
    primary_only = evaluate_frozen_pair(
        control, combined, receipt, revealed, policy=EvaluationPolicy(2.0)
    )
    with_meta = evaluate_frozen_pair(
        control,
        combined,
        receipt,
        revealed,
        policy=EvaluationPolicy(2.0),
        meta_loop=meta,
    )

    assert with_meta["paired_deltas"] == primary_only["paired_deltas"]
    assert with_meta["meta_loop"]["authority"] == "POST_REVEAL_DIAGNOSTIC_ONLY"
    assert with_meta["meta_loop"]["predictive_evidence"] is False
    assert with_meta["meta_loop"]["recognition"]["recall"] == 1.0
    assert with_meta["meta_loop"]["source_shadow_movie_hash"] == combined.movie_hash

    bad = replace(records[0], rewrites_frozen_first_lock=True)
    bad_meta = replace(meta, observations=(bad, *records[1:]))
    with pytest.raises(ReconciliationError, match="cannot rewrite"):
        evaluate_frozen_pair(
            control,
            combined,
            receipt,
            revealed,
            policy=EvaluationPolicy(2.0),
            meta_loop=bad_meta,
        )


def test_meta_loop_cannot_run_before_answer_reveal() -> None:
    control, combined, receipt, revealed = frozen_inputs()
    record = PostRevealMetaLoopObservation.create(
        opportunity_id="d1",
        executed_at=101.5,
        candidate_ids=("D1",),
        target_probability=0.9,
        abstained=False,
        observed_frozen_first_lock_id="shadow-d1",
        rewrites_frozen_first_lock=False,
        usage=usage(),
    )
    meta = PostRevealMetaLoopMovie.create(
        run_id=RUN,
        source_shadow_movie_hash=combined.movie_hash,
        frozen_shadow_first_lock_roster_hash=combined.first_lock_roster_hash,
        observations=(record,),
        expected_opportunity_count=1,
        complete=True,
    )
    with pytest.raises(ReconciliationError, match="after Step-1 reveal"):
        evaluate_frozen_pair(
            control,
            combined,
            receipt,
            revealed,
            policy=EvaluationPolicy(2.0),
            meta_loop=meta,
        )
