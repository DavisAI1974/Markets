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
    PAIR_COUNT,
    TEACHBACK_SCHEMA,
    ClassroomMode,
    audit_teacher_complete,
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
    encoded = [float(value) if state == int(TargetState.PRESENT) else 0.0
               for value, state in zip(values, states)]
    return DipoleTarget(
        spec,
        HEX_A,
        source_prefix,
        now,
        torch.tensor([[encoded]], dtype=torch.float32),
        torch.tensor([[states]], dtype=torch.int8),
        torch.tensor([[now]], dtype=torch.int64),
    )


def _teacher(*, offset=0.0):
    rows = []
    raw_rows = []
    cursors = (2, 4, 6)
    for row_index, cursor in enumerate(cursors):
        states = [int(TargetState.PRESENT)] * len(COLUMNS)
        reasons = [""] * len(COLUMNS)
        if row_index == 0:
            states[1] = int(TargetState.MISSING);reasons[1] = "WINDOW_SHORT"
            states[2] = int(TargetState.INVALID);reasons[2] = "LEVEL_INTEGRITY"
            states[7] = int(TargetState.ABLATED);reasons[7] = "UNBUILT_B2_C1"
        values = [float(index + row_index + offset) for index in range(len(COLUMNS))]
        rows.append(_target(cursor, values, states))
        raw_rows.append(tuple({"value": values[index], "state": states[index], "reason": reasons[index]}
                              for index in range(len(COLUMNS))))
    receipts = tuple({"cursor": cursor, "source_prefix_hash": target.source_prefix_hash,
                      "target_hash": target.target_hash, "normalizer": {"normalizer_id": "test-normalizer"}}
                     for cursor, target in zip(cursors, rows))
    return {
        "targets": tuple(rows),
        "raw": tuple(raw_rows),
        "processed_records": 7,
        "context_cursors": cursors,
        "step_receipts": receipts,
        "attachment_hash": evidence_hash(receipts),
        "candidate_digest": HEX_C,
    }


def _prepared(*, cycle_index=0, previous_snapshot=None, history=(), prior_grade=None, offset=0.0):
    return prepare_cycle(_teacher(offset=offset), request_id=f"run-cycle-{cycle_index:02d}", cycle_index=cycle_index,
        source_hash=HEX_B, as_of=2_000_000 + cycle_index, through_cursor=6,
        previous_snapshot=previous_snapshot, history=history, prior_grade=prior_grade)


def _teachback(pre, key, *, wrong_first=False, future=False, pair_count=PAIR_COUNT):
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
            pair = next(item for item in key["relationship_scan"] if item["left"] == name and item["right"] == other)
            relationships.append({"with": other, "relation": pair["direction_relation"],
                                  "explanation": "I compared the full causal-window directional evidence."})
        components.append({
            "name": name,
            "state_counts": dict(actual["state_counts"]),
            "terminal_state": state,
            "direction": direction,
            "explanation": f"I reviewed every retained state/value for {name}.",
            "why": f"I used the governed role for {name} and separated observation from interpretation.",
            "market_behavior": "I connected the measurement to the order-book behavior it actually measures.",
            "fifo_full_book_order_link": "I stated the FIFO/full-book/order implication only where the curriculum supports it.",
            "evidence": "I used only the causal evidence available at this cutoff and accounted for non-PRESENT states.",
            "uncertainty": "I did not use or claim a later market outcome.",
            "relationships": relationships,
        })
    return {
        "schema": TEACHBACK_SCHEMA,
        "teacher_message_hash": pre["teacher_message_hash"],
        "components": components,
        "cycle_summary": "I reviewed the complete 19-dimensional Dipole surface for this cycle.",
        "correlation_review": "I considered all 171 pairs; descriptive Pearson/direction is not causation or future proof.",
        "relationship_pairs_considered": pair_count,
        "unresolved_questions": [],
        "future_outcome_claimed": future,
    }


def _ack(grade, *, remaining=None, session_id="frankie-session"):
    return {
        "schema": ACK_SCHEMA,
        "post_grade_hash": grade["post_grade_hash"],
        "session_id": session_id,
        "acknowledged": True,
        "resolved_correction_ids": list(grade["correction_ids"]),
        "remaining_disagreements": [] if remaining is None else list(remaining),
        "what_i_will_change": "I will carry every correction forward and continue covering all 19 Dipole dimensions.",
    }


def test_cycle_zero_teaches_every_state_value_dimension_and_pair():
    prepared = _prepared()
    source, key, pre = prepared["source"], prepared["teacher_key"], prepared["pre_message"]
    assert prepared["binding"]["mode"] == ClassroomMode.TEACH.value
    assert source["coverage_count"] == key["coverage_count"] == pre["coverage_count"] == len(COLUMNS)
    assert tuple(item["name"] for item in pre["components"]) == tuple(COLUMNS)
    assert len(source["rows"]) == 3
    assert all(len(row["components"]) == len(COLUMNS) for row in source["rows"])
    assert all("observations" in item for item in pre["components"])
    assert all(len(item["observations"]) == 3 for item in pre["components"])
    assert key["relationship_pairs_scanned"] == pre["relationship_pairs_required"] == PAIR_COUNT
    assert len(pre["relationship_review"]) == PAIR_COUNT
    assert key["dimensions"][1]["state_counts"]["MISSING"] == 1
    assert key["dimensions"][2]["state_counts"]["INVALID"] == 1
    assert key["dimensions"][7]["state_counts"]["ABLATED"] == 1
    assert key["dimensions"][1]["nonpresent_explanations"][0]["reason"] == "WINDOW_SHORT"


def test_cycle_after_zero_requires_immediate_prior_snapshot_and_reviews_change():
    first = _prepared(cycle_index=0)
    with pytest.raises(ValueError, match="preceding classroom source snapshot"):
        _prepared(cycle_index=1)
    second = _prepared(cycle_index=1, previous_snapshot=first["source"], offset=1.0)
    assert all(item["change_from_previous"] is not None for item in second["teacher_key"]["dimensions"])
    assert all(item["previous_cycle"] is not None for item in second["teacher_key"]["dimensions"])


def test_teacher_cardinality_or_column_loss_fails_closed():
    teacher = _teacher();teacher["raw"] = teacher["raw"][:-1]
    with pytest.raises(ValueError, match="cardinality"):
        prepare_cycle(teacher, request_id="run-cycle-00", cycle_index=0,
            source_hash=HEX_B, as_of=2_000_000, through_cursor=6)
    teacher = _teacher();teacher["raw"] = (teacher["raw"][0][:-1],) + teacher["raw"][1:]
    with pytest.raises(ValueError, match="every governed column"):
        prepare_cycle(teacher, request_id="run-cycle-00", cycle_index=0,
            source_hash=HEX_B, as_of=2_000_000, through_cursor=6)


def test_mode_backs_away_only_after_two_mastered_acknowledged_teacher_complete_cycles():
    base = {"schema": COMPLETION_SCHEMA, "mode": ClassroomMode.TEACH.value,
            "mastered": True, "acknowledged": True, "teacher_complete": True}
    assert select_mode(()) == ClassroomMode.TEACH.value
    assert select_mode((base,)) == ClassroomMode.TEACH.value
    assert select_mode((base, dict(base))) == ClassroomMode.GUIDED.value
    failed = dict(base, mastered=False)
    assert select_mode((base, failed)) == ClassroomMode.TEACH.value
    incomplete = dict(base, teacher_complete=False)
    with pytest.raises(ValueError, match="invalid completion"):
        select_mode((incomplete,))


def test_socratic_message_keeps_19_of_19_requirement_but_withholds_answer_key():
    prepared = _prepared();key = prepared["teacher_key"]
    pre = build_pre_message(key, mode=ClassroomMode.SOCRATIC.value)
    assert pre["schema"] == MESSAGE_SCHEMA
    assert pre["coverage_count"] == len(COLUMNS)
    assert pre["relationship_pairs_required"] == PAIR_COUNT
    assert tuple(item["name"] for item in pre["components"]) == tuple(COLUMNS)
    assert pre["relationship_review"] is None
    for item in pre["components"]:
        assert "observations" not in item
        assert "terminal_state" not in item
        assert "terminal_value" not in item
        assert "first_to_last_present_direction" not in item
        assert "required_review" in item


def test_teachback_requires_exact_19_full_pair_scan_and_no_future_claim():
    prepared = _prepared();pre, key = prepared["pre_message"], prepared["teacher_key"]
    value = _teachback(pre, key);value["components"] = value["components"][:-1]
    with pytest.raises(ValueError, match="exactly"):
        validate_teachback(value, pre)
    value = _teachback(pre, key, pair_count=PAIR_COUNT - 1)
    with pytest.raises(ValueError, match="full intra-Dipole relationship surface"):
        validate_teachback(value, pre)
    value = _teachback(pre, key, future=True)
    with pytest.raises(ValueError, match="future outcome"):
        validate_teachback(value, pre)


def test_post_grade_explains_right_wrong_and_emits_correction_ids():
    prepared = _prepared();pre, key = prepared["pre_message"], prepared["teacher_key"]
    correct = validate_teachback(_teachback(pre, key), pre)
    grade = grade_teachback(key, correct)
    assert grade["schema"] == GRADE_SCHEMA
    assert grade["coverage_count"] == len(COLUMNS)
    assert grade["relationship_pairs_checked"] == PAIR_COUNT
    assert grade["mastered"] is True
    assert grade["correction_ids"] == ()
    assert all(item["state_counts_correct"] and item["state_correct"] and item["direction_correct"]
               for item in grade["component_grades"])

    wrong = validate_teachback(_teachback(pre, key, wrong_first=True), pre)
    grade = grade_teachback(key, wrong)
    assert grade["mastered"] is False
    assert grade["component_grades"][0]["direction_correct"] is False
    assert "component:" + COLUMNS[0] in grade["correction_ids"]
    assert grade["component_grades"][0]["explanation"].startswith("Correction:")


def test_same_session_ack_resolves_every_correction_and_unresolved_disagreement_blocks_completion():
    prepared = _prepared();pre, key = prepared["pre_message"], prepared["teacher_key"]
    teachback = validate_teachback(_teachback(pre, key, wrong_first=True), pre)
    grade = grade_teachback(key, teachback)
    ack = validate_acknowledgement(_ack(grade), grade, session_id="frankie-session")
    completion = complete_cycle(binding=prepared["binding"], key=key, pre_message=pre,
        teachback=teachback, grade=grade, acknowledgement=ack)
    assert completion["schema"] == COMPLETION_SCHEMA
    assert completion["teacher_complete"] is True
    assert completion["mastered"] is False
    assert completion["acknowledged"] is True
    assert completion["audit"]["unresolved_disagreements"] == 0

    raw = _ack(grade, remaining=["I still disagree about the first dimension."])
    unresolved = validate_acknowledgement(raw, grade, session_id="frankie-session")
    with pytest.raises(ValueError, match="unresolved Dipole disagreement"):
        complete_cycle(binding=prepared["binding"], key=key, pre_message=pre,
            teachback=teachback, grade=grade, acknowledgement=unresolved)

    bad = _ack(grade, session_id="other-session")
    with pytest.raises(ValueError, match="same Frankie session"):
        validate_acknowledgement(bad, grade, session_id="frankie-session")


def test_teacher_complete_audit_refuses_silent_nonpresent_omission():
    prepared = _prepared();pre, key = prepared["pre_message"], prepared["teacher_key"]
    teachback = validate_teachback(_teachback(pre, key), pre);grade = grade_teachback(key, teachback)
    ack = validate_acknowledgement(_ack(grade), grade, session_id="frankie-session")
    broken = copy.deepcopy(key)
    broken["dimensions"][1]["nonpresent_explanations"] = ()
    with pytest.raises(ValueError, match="silently omitted"):
        audit_teacher_complete(binding=prepared["binding"], key=broken, pre_message=pre,
            teachback=teachback, grade=grade, acknowledgement=ack)
