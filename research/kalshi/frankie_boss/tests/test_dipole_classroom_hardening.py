import inspect

from research.kalshi.frankie_boss.c15_normalizer import COLUMNS
from research.kalshi.frankie_boss.dipole_classroom import (
    COMPLETION_SCHEMA,
    GRADE_SCHEMA,
    KEY_SCHEMA,
    PAIR_COUNT,
    ClassroomMode,
)
from research.kalshi.frankie_boss.dipole_classroom_hardening import (
    MIN_PEARSON_PRESENT_OVERLAP,
    HardenedDipoleClassroomPrincipalAdapter,
    _harden_teacher_key_correlations,
    build_hardened_correction_request,
    prior_correction_summary,
    select_hardened_mode,
)


def _completion(mode, *, mastered=True, acknowledged=True):
    return {
        "schema": COMPLETION_SCHEMA,
        "mode": mode,
        "mastered": mastered,
        "acknowledged": acknowledged,
        "teacher_complete": True,
    }


def test_hardened_mode_regresses_one_level_after_degradation():
    assert select_hardened_mode(
        (_completion(ClassroomMode.VERIFY.value, mastered=False),)
    ) == ClassroomMode.SOCRATIC.value
    assert select_hardened_mode(
        (_completion(ClassroomMode.SOCRATIC.value, mastered=False),)
    ) == ClassroomMode.GUIDED.value
    assert select_hardened_mode(
        (_completion(ClassroomMode.GUIDED.value, mastered=False),)
    ) == ClassroomMode.TEACH.value
    assert select_hardened_mode(
        (_completion(ClassroomMode.TEACH.value, mastered=False),)
    ) == ClassroomMode.TEACH.value


def test_hardened_mode_still_requires_two_mastered_cycles_to_advance():
    guided = _completion(ClassroomMode.GUIDED.value)
    assert select_hardened_mode((guided,)) == ClassroomMode.GUIDED.value
    assert select_hardened_mode((guided, dict(guided))) == ClassroomMode.SOCRATIC.value


def test_small_n_pearson_is_suppressed_at_declared_eight_point_floor():
    relationships = []
    for index, left in enumerate(COLUMNS):
        for right in COLUMNS[index + 1 :]:
            relationships.append(
                {
                    "left": left,
                    "right": right,
                    "direction_relation": "SAME_DIRECTION",
                    "correlation": {
                        "present_overlap": MIN_PEARSON_PRESENT_OVERLAP - 1,
                        "pearson": 0.999,
                        "reason": None,
                    },
                    "interpretation_limit": "TEST",
                }
            )
    assert len(relationships) == PAIR_COUNT
    key = {
        "schema": KEY_SCHEMA,
        "relationship_pairs_scanned": PAIR_COUNT,
        "relationship_scan": tuple(relationships),
        "teacher_key_hash": "a" * 64,
    }
    hardened = _harden_teacher_key_correlations(key)
    first = hardened["relationship_scan"][0]["correlation"]
    assert first == {
        "present_overlap": MIN_PEARSON_PRESENT_OVERLAP - 1,
        "pearson": None,
        "reason": "FEWER_THAN_EIGHT_OVERLAPPING_PRESENT_VALUES",
    }


def test_prior_cycle_summary_carries_locations_not_answer_key():
    grade = {
        "schema": GRADE_SCHEMA,
        "post_grade_hash": "b" * 64,
        "correction_ids": (
            "observation:far_front_age_log:7",
            "relationship:far_front_age_log:far_queue_age_p90_log",
        ),
        "mastered": False,
        "exhaustive_audit": {"sentinel_answer_key": 912345.678},
    }
    summary = prior_correction_summary(grade)
    rendered = repr(summary)
    assert summary["correction_count"] == 2
    assert "sentinel_answer_key" not in rendered
    assert "912345.678" not in rendered
    assert "exhaustive_audit" not in summary


def test_same_session_correction_contains_only_mistakes_not_full_post_grade():
    left, right = COLUMNS[:2]
    grade = {
        "schema": GRADE_SCHEMA,
        "post_grade_hash": "c" * 64,
        "correction_ids": (
            f"observation:{left}:7",
            f"relationship:{left}:{right}",
        ),
        "mastered": False,
        "component_grades": (),
        "exhaustive_audit": {
            "coverage_proven": True,
            "sentinel_full_key": 812345.678,
            "observation_grades": (
                {
                    "name": left,
                    "expected_count": 1,
                    "claimed_count": 1,
                    "grades": (
                        {
                            "cursor": 7,
                            "state": "PRESENT",
                            "value": 4.25,
                            "correct": False,
                            "explanation": "Expected state PRESENT value 4.25; claim differed.",
                        },
                    ),
                    "extra_cursors": (),
                },
            ),
            "relationship_grades": (
                {
                    "left": left,
                    "right": right,
                    "claimed": "OPPOSITE_DIRECTION",
                    "actual": "SAME_DIRECTION",
                    "correct": False,
                    "correlation": {
                        "present_overlap": 19,
                        "pearson": 0.75,
                        "reason": None,
                    },
                    "developing_structure": None,
                    "explanation": "Exact directional relationship is SAME_DIRECTION.",
                },
            ),
        },
    }
    response = {
        "session_id": "same-session",
        "model_identity_as_reported_by_session": "frankie",
    }
    request = build_hardened_correction_request(
        original_request_sha256="d" * 64,
        response=response,
        grade=grade,
    )
    rendered = repr(request)
    assert "post_grade" not in request
    assert "exhaustive_audit" not in request
    assert "sentinel_full_key" not in rendered
    assert "812345.678" not in rendered
    assert len(request["correction_items"]) == 2
    assert request["correction_items"][0]["actual_value"] == 4.25
    assert request["correction_items"][1]["actual"] == "SAME_DIRECTION"
    assert "correlation" not in request["correction_items"][1]


def test_hardened_principal_prepare_never_writes_teacher_key_into_principal_dir():
    source = inspect.getsource(HardenedDipoleClassroomPrincipalAdapter.prepare)
    assert "dipole-classroom-teacher-key.audit.json" not in source
    assert "FrankiePrincipalAdapter.prepare" in source
