from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_g15_attribution_bound_publication_gate as gate
import ng_g15_exact_publication_gate as publication


def _fixture(tmp_path: Path) -> dict:
    return gate._synthetic_fixture(tmp_path)


def test_builds_recursive_attribution_bound_publication(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    result = gate.build_gate(**inputs)
    gate.validate_gate(result)
    assert result["status"] == gate.READY
    assert result["attribution_authorization_bound_to_publication"] is True
    assert result["separate_blind_refined_scores_verified"] is True
    assert result["blind_score_fingerprint"] != result["refined_score_fingerprint"]
    assert result["actual_g16_outcomes_used"] is False
    assert result["may_update_ng_brain"] is False


def test_rejects_publication_from_different_refinement_authorization(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    tampered = copy.deepcopy(inputs["publication_completion"])
    tampered["exact_refinement_authorization_fingerprint"] = "x" * 64
    tampered.pop("completion_fingerprint", None)
    tampered["completion_fingerprint"] = publication._fingerprint(tampered)
    inputs["publication_completion"] = tampered
    with pytest.raises(gate.AttributionBoundPublicationError):
        gate.build_gate(**inputs)


def test_rejects_collapsed_blind_refined_score_artifacts(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    inputs["refined_score"] = copy.deepcopy(inputs["blind_score"])
    with pytest.raises(gate.AttributionBoundPublicationError):
        gate.build_gate(**inputs)


def test_rejects_publication_score_fingerprint_substitution(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    tampered = copy.deepcopy(inputs["publication_completion"])
    tampered["blind_score_fingerprint"] = "z" * 64
    tampered.pop("completion_fingerprint", None)
    tampered["completion_fingerprint"] = publication._fingerprint(tampered)
    inputs["publication_completion"] = tampered
    with pytest.raises(gate.AttributionBoundPublicationError):
        gate.build_gate(**inputs)


def test_rejects_refingerprinted_score_brain_write_escalation(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    tampered = copy.deepcopy(inputs["blind_score"])
    tampered["may_update_ng_brain"] = True
    tampered.pop("artifact_fingerprint", None)
    tampered["artifact_fingerprint"] = publication._fingerprint(tampered)
    inputs["blind_score"] = tampered
    with pytest.raises(gate.AttributionBoundPublicationError):
        gate.build_gate(**inputs)


def test_rejects_nested_tampering_even_with_outer_refingerprint(tmp_path: Path) -> None:
    result = gate.build_gate(**_fixture(tmp_path))
    tampered = copy.deepcopy(result)
    tampered["comparison"]["execution_authority"] = True
    tampered["comparison"].pop("artifact_fingerprint", None)
    tampered["comparison"]["artifact_fingerprint"] = publication._fingerprint(
        tampered["comparison"]
    )
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = gate._fingerprint(tampered)
    with pytest.raises(gate.AttributionBoundPublicationError):
        gate.validate_gate(tampered)


def test_build_does_not_mutate_inputs(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    original = copy.deepcopy(inputs)
    gate.build_gate(**inputs)
    assert inputs == original
