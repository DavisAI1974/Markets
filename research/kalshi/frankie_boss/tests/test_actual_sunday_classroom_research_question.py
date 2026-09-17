from research.kalshi.frankie_boss import frankie_principal_adapter
from research.kalshi.frankie_boss.operations import run_actual_sunday_classroom as classroom


def test_greg_question_keeps_prebirth_and_frankie_selected_top_five():
    question = classroom.GREG_PREBIRTH_AUTHORITY_TOP5_QUESTION
    assert classroom.GREG_PREBIRTH_AUTHORITY_TOP5_MARKER in question
    assert "prebirth" in question
    assert "authority persists, collapses, or transfers" in question
    assert "choose exactly five" in question
    assert "Choose the five yourself" in question
    assert "1,900+" in question
    assert "BLOCKED" in question
    assert "instead of guessing or inventing five" in question
    assert "no-drop/no-truncation/no-averaging/no-smoothing/no-normalization" in question
    assert "Do not change existing Frankie calculations or planes" in question


def test_research_question_installation_is_idempotent(monkeypatch):
    baseline = "BASE_RUN_ANALYSIS_INSTRUCTION"
    monkeypatch.setattr(frankie_principal_adapter, "RUN_ANALYSIS_INSTRUCTION", baseline)

    classroom._install_greg_research_question()
    first = frankie_principal_adapter.RUN_ANALYSIS_INSTRUCTION
    classroom._install_greg_research_question()
    second = frankie_principal_adapter.RUN_ANALYSIS_INSTRUCTION

    assert first == second
    assert first.startswith(baseline)
    assert first.count(classroom.GREG_PREBIRTH_AUTHORITY_TOP5_MARKER) == 1
