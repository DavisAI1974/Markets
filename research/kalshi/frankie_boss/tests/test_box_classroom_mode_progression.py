"""Box curriculum regression: real packages, model claims, and real grading.

Proposed box API additions:
    component_prompt(..., evidence_text=None)
    parse_component(..., mode="TEACH")

The teacher key is used only to construct synthetic model-answer fixtures and
to grade them. It is never passed into a box prompt, parser, or assembler.
"""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from research.kalshi.frankie_boss.c15_normalizer import COLUMNS
from research.kalshi.frankie_boss.dipole_classroom import COMPLETION_SCHEMA
from research.kalshi.frankie_boss.dipole_classroom_integration import (
    prepare_integrated_cycle,
)
from research.kalshi.frankie_boss.dipole_classroom_final_review import (
    apply_relationship_view_crosscheck,
    final_model_visible_classroom,
)
from research.kalshi.frankie_boss.dipole_classroom_session import (
    grade_initial_response,
)
from test_dipole_classroom import _teacher


ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    "box_classroom_progression_under_test",
    ROOT / "deploy/aws/box/frankie_box_classroom.py",
)
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)

CASES = [(0, "TEACH"), (1, "TEACH"), (2, "GUIDED"),
         (4, "SOCRATIC"), (6, "VERIFY")]
EVIDENCE = (
    "CURRENT_REQUEST_EVIDENCE_187\n"
    "Synthetic independently supplied causal input, with native units.\n"
    "This fixture is not a classroom teacher-key serialization.\n"
)
SUMMARY = {
    "cycle_summary": "Model supplied the cycle summary.",
    "correlation_review": "Model separated description from causation.",
    "unresolved_questions": [],
    "novel_findings": [],
}


def package_at(index):
    previous = None
    history = []
    for cycle in range(index + 1):
        package = prepare_integrated_cycle(
            _teacher(offset=float(cycle)),
            request_id=f"progression-cycle-{cycle:02d}",
            cycle_index=cycle,
            cycle_count=8,
            source_hash="b" * 64,
            as_of=2_000_000 + cycle,
            through_cursor=6,
            previous_snapshot=previous,
            history=tuple(history),
        )
        previous = package["source"]
        # Synthetic completed history; production mode selection remains real.
        history.append({
            "schema": COMPLETION_SCHEMA,
            "mode": package["binding"]["mode"],
            "teacher_complete": True,
            "mastered": True,
            "acknowledged": True,
        })
    return package


def public_of(package):
    return json.loads(json.dumps(final_model_visible_classroom(package)))


def answer_objects(package):
    """Synthetic model answers; deliberately not a production teacher shortcut."""
    pairs = {
        (p["left"], p["right"]): p
        for p in package["teacher_key"]["relationship_scan"]
    }
    result = {}
    for index, dimension in enumerate(package["teacher_key"]["dimensions"]):
        name = dimension["name"]
        answer = {
            field: f"MODEL_{field}_{name}"
            for field in C.NARRATIVE
        }
        answer.update({
            "state_counts": dict(dimension["state_counts"]),
            "terminal_state": dimension["terminal_state"],
            "direction": dimension["first_to_last_present_direction"],
            "state_explanations": {
                state: f"MODEL_STATE_{name}_{state}"
                for state in {p["state"] for p in dimension["observations"]}
            },
            "observations": [
                {
                    "cursor": p["cursor"],
                    "state": p["state"],
                    "value": p["value"],
                    "explanation": f"MODEL_OBSERVATION_{name}_{p['cursor']}",
                }
                for p in dimension["observations"]
            ],
            "pairs": [
                {
                    "right": right,
                    "direction_relation": pairs[
                        (name, right)
                    ]["direction_relation"],
                    "correlation_interpretation": f"MODEL_PAIR_{name}_{right}",
                    "developing_structure": None,
                }
                for right in COLUMNS[index + 1:]
            ],
        })
        result[name] = answer
    return result


def parse_answers(public, answers):
    return {
        name: C.parse_component(
            json.dumps(answers[name]),
            C.component(public, name),
            list(COLUMNS[index + 1:]),
            mode=public["pre_message"]["mode"],
        )
        for index, name in enumerate(COLUMNS)
    }


def assemble(public, outputs):
    summary = C.parse_summary(json.dumps(SUMMARY))
    ledgers = C.assemble(public, outputs, summary)["ledgers"]
    C.validate(public, ledgers)
    return ledgers


@pytest.mark.parametrize("index, expected", CASES)
def test_box_accepts_real_production_curriculum_modes(index, expected):
    package = package_at(index)
    public = public_of(package)
    assert package["binding"]["mode"] == expected
    assert C.visible_of({
        "attachment": {"dipole_classroom": public}
    }) == public


@pytest.mark.parametrize("index", [2, 4, 6])
def test_non_teach_prompt_uses_supplied_evidence_without_current_key(index):
    package = package_at(index)
    public = public_of(package)
    before = copy.deepcopy(public)

    assert "teacher_key" not in public
    assert "source" not in public
    assert public["pre_message"]["relationship_review"] is None
    if index >= 4:
        for component in public["pre_message"]["components"]:
            assert "observations" not in component
            assert "terminal_state" not in component
            assert "first_to_last_present_direction" not in component

    text = C.component_prompt(
        public,
        COLUMNS[0],
        cycle=f"{index:02d}",
        request_id=package["binding"]["request_id"],
        evidence_text=EVIDENCE,
    )
    assert EVIDENCE in text
    assert package["binding"]["request_id"] in text
    assert public == before
    assert '"relationship_scan"' not in text
    assert '"teacher_key":' not in text


@pytest.mark.parametrize("index", [4, 6])
@pytest.mark.parametrize("missing", [None, "", " \n"])
def test_independent_mode_refuses_missing_current_evidence(index, missing):
    package = package_at(index)
    with pytest.raises(ValueError, match="evidence"):
        C.component_prompt(
            public_of(package),
            COLUMNS[0],
            cycle=f"{index:02d}",
            request_id=package["binding"]["request_id"],
            evidence_text=missing,
        )


@pytest.mark.parametrize("index, expected", CASES)
def test_each_mode_can_assemble_complete_ledgers_and_pass_real_grader(
    index, expected
):
    package = package_at(index)
    public = public_of(package)
    outputs = parse_answers(public, answer_objects(package))
    ledgers = assemble(public, outputs)

    assert len(ledgers["dipole_teachback"]["components"]) == 19
    assert len(ledgers["dipole_observation_review"]) == 19
    assert sum(
        len(item["observations"])
        for item in ledgers["dipole_observation_review"]
    ) == 19 * 3
    assert len(ledgers["dipole_relationship_scan"]) == 171
    assert (
        ledgers["dipole_teachback"]["teacher_message_hash"]
        == public["pre_message"]["teacher_message_hash"]
    )
    _, grade = grade_initial_response(package, ledgers)
    grade = apply_relationship_view_crosscheck(grade, ledgers)
    assert grade["mastered"] is True
    assert grade["correction_ids"] == ()


@pytest.mark.parametrize("index", [2, 4, 6])
@pytest.mark.parametrize("wrong", ["direction", "relationship"])
def test_withheld_model_claims_survive_assembly_and_are_graded(index, wrong):
    package = package_at(index)
    public = public_of(package)
    answers = answer_objects(package)
    first = answers[COLUMNS[0]]

    if wrong == "direction":
        first["direction"] = (
            "FALL" if first["direction"] != "FALL" else "RISE"
        )
    else:
        original = first["pairs"][0]["direction_relation"]
        first["pairs"][0]["direction_relation"] = (
            "OPPOSITE_DIRECTION"
            if original != "OPPOSITE_DIRECTION"
            else "SAME_DIRECTION"
        )

    outputs = parse_answers(public, answers)
    ledgers = assemble(public, outputs)
    if wrong == "direction":
        assert (
            ledgers["dipole_teachback"]["components"][0]["direction"]
            == first["direction"]
        )
    else:
        assert (
            ledgers["dipole_relationship_scan"][0]["direction_relation"]
            == first["pairs"][0]["direction_relation"]
        )

    _, grade = grade_initial_response(package, ledgers)
    grade = apply_relationship_view_crosscheck(grade, ledgers)
    assert grade["mastered"] is False
    assert grade["correction_ids"]
    if wrong == "direction":
        assert f"component:{COLUMNS[0]}" in grade["correction_ids"]


@pytest.mark.parametrize("index", [4, 6])
def test_independent_observation_claim_is_not_replaced_with_teacher_value(index):
    package = package_at(index)
    public = public_of(package)
    answers = answer_objects(package)
    point = answers[COLUMNS[0]]["observations"][0]
    assert point["state"] == "PRESENT"
    point["value"] += 123.0

    ledgers = assemble(public, parse_answers(public, answers))
    actual = ledgers["dipole_observation_review"][0]["observations"][0]
    assert actual["value"] == point["value"]
    assert actual["explanation"] == point["explanation"]

    _, grade = grade_initial_response(package, ledgers)
    assert grade["mastered"] is False
    assert any(
        item.startswith("observation:")
        for item in grade["correction_ids"]
    )


@pytest.mark.parametrize("index", [2, 4, 6])
def test_non_teach_summary_uses_model_claims_without_teacher_pair_table(index):
    package = package_at(index)
    public = public_of(package)
    answers = answer_objects(package)
    # The fixture's first pair is SAME_DIRECTION. This deliberately differs.
    answers[COLUMNS[0]]["pairs"][0]["direction_relation"] = (
        "OPPOSITE_DIRECTION"
    )
    outputs = parse_answers(public, answers)
    assert public["pre_message"]["relationship_review"] is None

    text = C.summary_prompt(
        public,
        outputs,
        cycle=f"{index:02d}",
        request_id=package["binding"]["request_id"],
    )
    for name in COLUMNS:
        assert outputs[name]["explanation"] in text
    assert "OPPOSITE_DIRECTION" in text
    assert '"teacher_key":' not in text

    parsed = C.parse_summary(json.dumps(SUMMARY))
    assert parsed == SUMMARY
