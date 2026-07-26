import copy

import pytest

import ng_corpus_executor_plan_compiler_v28 as compiler


def _fixture():
    attribution_authorization = {"authorization_fingerprint": "auth-fp"}
    attribution = {"fingerprint": "attribution-fp"}
    replay = {"fingerprint": "replay-fp"}
    anchor = {"anchor_fingerprint": "anchor-fp"}
    refine_stream = {"fingerprint": "stream-fp"}
    publication = {"completion_fingerprint": "publication-fp"}
    blind_score = {"artifact_fingerprint": "blind-score-fp"}
    refined_score = {"artifact_fingerprint": "refined-score-fp"}
    comparison = {"artifact_fingerprint": "comparison-fp"}
    bound = {
        "attribution_authorization": copy.deepcopy(attribution_authorization),
        "publication_completion": copy.deepcopy(publication),
        "blind_score": copy.deepcopy(blind_score),
        "refined_score": copy.deepcopy(refined_score),
        "comparison": copy.deepcopy(comparison),
        "publication_completion_fingerprint": "publication-fp",
        "blind_score_fingerprint": "blind-score-fp",
        "refined_score_fingerprint": "refined-score-fp",
        "comparison_fingerprint": "comparison-fp",
        "attribution_fingerprint": "attribution-fp",
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
        "fingerprint": "bound-fp",
    }
    lessons = {
        "source": {
            "comparison_fingerprint": "comparison-fp",
            "counterfactual_fingerprint": "attribution-fp",
        },
        "adjudication": {
            "g16_shadow_registry": {"registry_fingerprint": "registry-fp"}
        },
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
        "fingerprint": "lessons-fp",
    }
    upstream = {
        "g15_counterfactual_attribution_authorization": attribution_authorization,
        "g15_replay": replay,
        "g15_anchor": anchor,
        "g15_refine_stream": refine_stream,
        "g15_counterfactual_attribution": attribution,
    }
    return {
        "upstream_receipt": upstream,
        "publication": publication,
        "bound_publication": bound,
        "blind_score": blind_score,
        "refined_score": refined_score,
        "comparison": comparison,
        "daily_audit": {"audit_fingerprint": "audit-fp"},
        "counterfactual_lessons": lessons,
    }


def test_fixed_g15_outcomes_are_validated_without_pretending_to_be_outcome_blind(monkeypatch):
    monkeypatch.setattr(compiler.publication_gate, "validate_completion", lambda value: None)
    monkeypatch.setattr(compiler.bound_gate, "validate_gate", lambda value: None)
    monkeypatch.setattr(compiler.lesson_gate, "validate_gate", lambda *args, **kwargs: None)
    result = compiler._validate_fixed_outcome_chain(**_fixture())
    assert result["publication_fingerprint"] == "publication-fp"
    assert result["bound_publication_fingerprint"] == "bound-fp"
    assert result["counterfactual_lessons_fingerprint"] == "lessons-fp"
    assert result["g16_registry_fingerprint"] == "registry-fp"


def test_fixed_chain_rejects_substituted_attribution_lineage(monkeypatch):
    monkeypatch.setattr(compiler.publication_gate, "validate_completion", lambda value: None)
    monkeypatch.setattr(compiler.bound_gate, "validate_gate", lambda value: None)
    monkeypatch.setattr(compiler.lesson_gate, "validate_gate", lambda *args, **kwargs: None)
    fixture = _fixture()
    fixture["bound_publication"]["attribution_fingerprint"] = "other-attribution"
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV28Error):
        compiler._validate_fixed_outcome_chain(**fixture)
