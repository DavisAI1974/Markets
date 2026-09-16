import copy

import pytest
import torch

from research.kalshi.frankie_boss.c15_journal import evidence_hash
from research.kalshi.frankie_boss.c15_normalizer import COLUMNS
from research.kalshi.frankie_boss.dipole_classroom import (
    ACK_SCHEMA,
    COMPLETION_SCHEMA,
    GRADE_SCHEMA,
    MESSAGE_SCHEMA,
    TEACHBACK_SCHEMA,
    ClassroomMode,
    build_pre_message,
    complete_cycle,
    grade_teachback,
    prepare_cycle,
    select_mode,
    validate_acknowledgement,
    validate_teachback,
)
from research.kalshi.frankie_boss.dipole_target import DipoleTarget, DipoleTargetSpec, TargetState


HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def _target(cursor, values, states, *, source_prefix=None):
    source_prefix = source_prefix or (f"{cursor + 1:064x}"[-64:])
    spec = DipoleTargetSpec(
        registry_id="boss/teacher/test",
        target_names=tuple(COLUMNS),
        target_units=("z_score",) * len(COLUMNS),
        normalizer_id="test-normalizer",
        builder_code_sha="1" * 40,
    )
    now = 1_000_000 + cursor
    return DipoleTarget(
        spec,
        HEX_A,
        source_prefix,
        now,
        torch.tensor([[values]], dtype=torch.float32),
        torch.tensor([[states]], dtype=torch.int8),
        torch.tensor([[now]], dtype=torch.int64),
    )


def _teacher():
    states = [int(TargetState.PRESENT)] * len(COLUMNS)
    first = _target(2, [float(i) for i in range(len(COLUMNS))], states)
    second = _target(4, [float(i + (1 if i % 2 == 0 else -1)) for i in range(len(COLUMNS))], states)
    targets = (first, second)
    raw = tuple(tuple({"value": 1.0, "state": int(TargetState.PRESENT), "reason": ""} for _ in COLUMNS)
                for _ in targets)
    cursors = (2, 4)
    receipts = tuple({"cursor": cursor, "source_prefix_hash": target.source_prefix_hash,
                      "target_hash": target.target_hash, "normalizer": {"normalizer_id": "test-normalizer"}}
                     for cursor, target in zip(cursors, targets))
    return {
        "targets": targets,
        "raw": raw,
        "processed_records": 5,
        "context_cursors": cursors,
        "step_receipts": receipts,
        "attachment_hash": evidence_hash(receipts),
        "candidate_digest": HEX_C,
    }


def _prepared(*, history=(), prior_grade=None):
    return prepare_cycle(_teacher(), request_id="run-cycle-00", cycle_index=0,
        source_hash=HEX_B, as_of=2_000_000, through_cursor=4,
        history=history, prior_grade=prior_grade)


def _teachback(pre, key, *, wrong_first=False, future=False):
    dimensions = {item["name"]: item for item in key["dimensions"]}
    components = []
    for index, name in enumerate(COLUMNS):
        actual = dimensions[name]
        state = actual["terminal_state"]
        direction = actual["first_to_last_present_direction"]
        if index == 0 and wrong_first:
            direction = "FALL" if direction != "FALL" else "RISE"
        relationships = []
        if index == 0:
            other = COLUMNS[1]
            left, right = COLUMNS[0], COLUMNS[1]
            relation = next(item["relation"] for item in key["directional_relationship_scan"]
                            if item["left"] == left and item["right"] == right)
            relationships.append({"with": other, "relation": relation,
                                  "explanation": "I compared their first-to-last PRESENT directions."})
        components.append({
            "name": name,
            "terminal_state": state,
            "direction": direction,
            "explanation": f"I reviewed {name}.",
            "role_in_cycle": f"{name} contributes one governed part of the Dipole geometry.",
            "evidence": "I used the causal evidence available at this cutoff.",
            "uncertainty": "I do not use later outcomes.",
            "relationships": relationships,
        })
    return {
        "schema": TEACHBACK_SCHEMA,
        "teacher_message_hash": pre["teacher_message_hash"],
        "components": components,
        "cycle_summary": "I reviewed the complete Dipole surface for this cycle.",
        "correlation_review": "Directional relationships are not statistical correlation or causation.",
        "future_outcome_claimed": future,
    }


def test_cycle_zero_teaches_every_dimension_and_retains_every_target_row():
    prepared = _prepared()
    source, key, pre = prepared["source"], prepared["teacher_key"], prepared["pre_message"]
    assert prepared["binding"]["mode"] == ClassroomMode.TEACH.value
    assert source["coverage_count"] == key["coverage_count"] == pre["coverage_count"] == len(COLUMNS)
    assert tuple(item["name"] for item in pre["components"]) == tuple(COLUMNS)
    assert len(source["rows"]) == 2
    assert all(len(row["components"]) == len(COLUMNS) for row in source["rows"])
    assert all("observations" in item for item in pre["components"])
    assert all(len(item["observations"]) == 2 for item in pre["components"])
    assert key["relationship_pairs_scanned"] == len(COLUMNS) * (len(COLUMNS) - 1) // 2


def test_teacher_cardinality_or_column_loss_fails_closed():
    teacher = _teacher()
    teacher["raw"] = teacher["raw"][:-1]
    with pytest.raises(ValueError, match="cardinality"):
        prepare_cycle(teacher, request_id="run-cycle-00", cycle_index=0,
            source_hash=HEX_B, as_of=2_000_000, through_cursor=4)

    teacher = _teacher()
    teacher["raw"] = (teacher["raw"][0][:-1], teacher["raw"][1])
    with pytest.raises(ValueError, match="every governed column"):
        prepare_cycle(teacher, request_id="run-cycle-00", cycle_index=0,
            source_hash=HEX_B, as_of=2_000_000, through_cursor=4)


def test_mode_backs_away_only_after_demonstrated_mastery_and_acknowledgement():
    base = {"schema": COMPLETION_SCHEMA, "mode": ClassroomMode.TEACH.value,
            "mastered": True, "acknowledged": True}
    assert select_mode(()) == ClassroomMode.TEACH.value
    assert select_mode((base,)) == ClassroomMode.TEACH.value
    assert select_mode((base, dict(base))) == ClassroomMode.GUIDED.value
    failed = dict(base, mastered=False)
    assert select_mode((base, failed)) == ClassroomMode.TEACH.value


def test_socratic_message_still_covers_all_dimensions_but_withholds_answer_key():
    prepared = _prepared()
    key = prepared["teacher_key"]
    pre = build_pre_message(key, mode=ClassroomMode.SOCRATIC.value)
    assert pre["schema"] == MESSAGE_SCHEMA
    assert tuple(item["name"] for item in pre["components"]) == tuple(COLUMNS)
    for item in pre["components"]:
        assert "observations" not in item
        assert "terminal_state" not in item
        assert "terminal_value" not in item
        assert "first_to_last_present_direction" not in item
        assert "required_review" in item


def test_teachback_requires_exact_19_of_19_and_refuses_future_outcome_claim():
    prepared = _prepared()
    pre, key = prepared["pre_message"], prepared["teacher_key"]
    value = _teachback(pre, key)
    value["components"] = value["components"][:-1]
    with pytest.raises(ValueError, match="exactly"):
        validate_teachback(value, pre)

    value = _teachback(pre, key, future=True)
    with pytest.raises(ValueError, match="future outcome"):
        validate_teachback(value, pre)


def test_post_grade_explains_factual_right_and_wrong_without_future_outcome():
    prepared = _prepared()
    pre, key = prepared["pre_message"], prepared["teacher_key"]
    correct = validate_teachback(_teachback(pre, key), pre)
    grade = grade_teachback(key, correct)
    assert grade["schema"] == GRADE_SCHEMA
    assert grade["coverage_count"] == len(COLUMNS)
    assert grade["mastered"] is True
    assert all(item["state_correct"] and item["direction_correct"] for item in grade["component_grades"])
    assert "Future outcome correctness remains unknown" in grade["teacher_closing"]

    wrong = validate_teachback(_teachback(pre, key, wrong_first=True), pre)
    grade = grade_teachback(key, wrong)
    assert grade["mastered"] is False
    assert grade["component_grades"][0]["direction_correct"] is False
    assert grade["component_grades"][0]["explanation"].startswith("Correction:")


def test_acknowledgement_must_be_same_frankie_session_then_completion_is_bound():
    prepared = _prepared()
    pre, key = prepared["pre_message"], prepared["teacher_key"]
    teachback = validate_teachback(_teachback(pre, key), pre)
    grade = grade_teachback(key, teachback)
    raw = {"schema": ACK_SCHEMA, "post_grade_hash": grade["post_grade_hash"],
           "session_id": "frankie-session", "acknowledged": True,
           "what_i_will_change": "I will retain the full Dipole coverage and apply the correction next cycle."}
    ack = validate_acknowledgement(raw, grade, session_id="frankie-session")
    completion = complete_cycle(binding=prepared["binding"], grade=grade, acknowledgement=ack)
    assert completion["schema"] == COMPLETION_SCHEMA
    assert completion["mastered"] is True
    assert completion["acknowledged"] is True

    bad = copy.deepcopy(raw);bad["session_id"] = "other-session"
    with pytest.raises(ValueError, match="same Frankie session"):
        validate_acknowledgement(bad, grade, session_id="frankie-session")
