from __future__ import annotations

from pathlib import Path

from research.kalshi.frankie_role_context_profiles_20260824 import (
    ActivationState,
    FrankieRole,
    build_role_context_payload,
    load_canonical_role_profiles,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_native_role_budgets_match_the_two_frankie_context_requests():
    profiles = load_canonical_role_profiles(REPO_ROOT)

    rt = profiles.roles[FrankieRole.REAL_TIME]
    assert rt.budget.direct_min_tokens == 32_000
    assert rt.budget.direct_target_tokens == 48_000
    assert rt.budget.tool_expanded_max_tokens == 96_000
    assert rt.budget.soft_ceiling_tokens == 96_000

    forecaster = profiles.roles[FrankieRole.FORECASTER]
    assert forecaster.budget.direct_min_tokens == 80_000
    assert forecaster.budget.direct_target_tokens == 120_000
    assert forecaster.budget.tool_expanded_max_tokens == 150_000
    assert forecaster.budget.soft_ceiling_tokens == 150_000

    assert profiles.native_context_only is True
    assert profiles.nova_token_optimization is False

    for profile in profiles.roles.values():
        assert set(profile.direct_token_plan) == set(profile.direct_surface_ids)
        assert sum(profile.direct_token_plan.values()) == profile.budget.direct_target_tokens
        assert profile.direct_token_plan["step1_structural_census_methodology"] == 18_000


def test_each_role_classifies_the_complete_uniform_superset_without_default_dormancy():
    profiles = load_canonical_role_profiles(REPO_ROOT)
    registered = set(profiles.surface_registry)

    for profile in profiles.roles.values():
        assert set(profile.activation) == registered
        assert set(profile.direct_surface_ids)
        assert set(profile.tool_accessible_surface_ids)
        assert profile.dormant_surface_ids == ()
        assert all(
            state in {ActivationState.DIRECT, ActivationState.TOOL_ACCESSIBLE}
            for state in profile.activation.values()
        )


def test_role_profiles_are_distinct_content_addressed_views_of_one_build():
    profiles = load_canonical_role_profiles(REPO_ROOT)
    rt = profiles.roles[FrankieRole.REAL_TIME]
    forecaster = profiles.roles[FrankieRole.FORECASTER]

    assert rt.profile_hash != forecaster.profile_hash
    assert len(rt.profile_hash) == 64
    assert len(forecaster.profile_hash) == 64
    assert len(profiles.aggregate_hash) == 64
    assert profiles.uniform_superset_build is True
    assert rt.activation["current_causal_operating_state"] is ActivationState.DIRECT
    assert forecaster.activation["frozen_rt_state"] is ActivationState.DIRECT
    assert (
        forecaster.activation["current_causal_operating_state"]
        is ActivationState.TOOL_ACCESSIBLE
    )


def test_complete_step1_method_is_direct_for_both_roles_and_separate_from_results():
    profiles = load_canonical_role_profiles(REPO_ROOT)

    assert "step1_structural_census_methodology" in profiles.surface_registry
    assert "step1_revealed_retrospective_evidence" in profiles.surface_registry
    for profile in profiles.roles.values():
        assert (
            profile.activation["step1_structural_census_methodology"]
            is ActivationState.DIRECT
        )


def test_step1_method_full_bytes_and_exact_sources_are_inside_both_role_builds():
    builds = {
        role: build_role_context_payload(REPO_ROOT, role)
        for role in FrankieRole
    }
    surface_id = "step1_structural_census_methodology"
    rt_surface = builds[FrankieRole.REAL_TIME]["direct_static_surfaces"][surface_id]
    fc_surface = builds[FrankieRole.FORECASTER]["direct_static_surfaces"][surface_id]

    assert rt_surface == fc_surface
    assert rt_surface["bundle_schema"] == "STEP1_METHOD_V1_20260824"
    assert len(rt_surface["direct_sources"]) == 9
    assert len(rt_surface["tool_reference_sources"]) == 8
    assert all(item["content"] for item in rt_surface["direct_sources"])
    assert all(item["byte_length"] == len(item["content"].encode()) for item in rt_surface["direct_sources"])
    assert all(len(item["sha256"]) == 64 for item in rt_surface["direct_sources"])
    assert all("content" not in item for item in rt_surface["tool_reference_sources"])
    assert builds[FrankieRole.REAL_TIME]["role_build_hash"] != builds[FrankieRole.FORECASTER]["role_build_hash"]
    assert (
        builds[FrankieRole.REAL_TIME]["uniform_superset_build_hash"]
        == builds[FrankieRole.FORECASTER]["uniform_superset_build_hash"]
    )
    for build in builds.values():
        reconciliation = build["capability_reconciliation"]
        assert reconciliation["bigsuite"]["leaf_count"] == 1940
        assert reconciliation["bigsuite"]["block_count"] == 46
        assert reconciliation["bigsuite"]["unregistered_leaf_count"] == 0
        assert reconciliation["bigsuite"]["silently_omitted_leaf_count"] == 0
        assert reconciliation["executable_tools"]["tool_count"] > 0
        assert reconciliation["executable_tools"]["unregistered_tool_count"] == 0
        assert reconciliation["executable_tools"]["silently_omitted_tool_count"] == 0


def test_forecaster_has_direct_day_specific_context_without_specialist_dependency():
    profiles = load_canonical_role_profiles(REPO_ROOT)
    forecaster = profiles.roles[FrankieRole.FORECASTER]

    assert profiles.collaboration_contract["forecaster_consumes_frozen_rt_state"] is True
    assert profiles.collaboration_contract["forecaster_consumes_specialist_packets"] is False
    assert profiles.collaboration_contract["rt_helper_packets_are_forecaster_inputs"] is False
    assert profiles.collaboration_contract["legacy_spawn_py_mutated"] is False
    assert (
        profiles.collaboration_contract["legacy_day_specialists_policy"]
        == "NO_ACTIVE_CALLS_PRESERVED_INSTALLED_TOOL_ACCESSIBLE"
    )
    assert (
        profiles.collaboration_contract["rt_helper_scouts_policy"]
        == "ONE_OPTIONAL_RT_EVIDENCE_SCOUT_NOT_AUTO_CALLED"
    )
    assert (
        profiles.collaboration_contract["forecaster_day_specific_surface"]
        == "day_specific_forecast_context"
    )
    assert (
        forecaster.activation["day_specific_forecast_context"]
        is ActivationState.DIRECT
    )
    assert (
        profiles.roles[FrankieRole.REAL_TIME].activation["rt_on_demand_evidence_scout"]
        is ActivationState.TOOL_ACCESSIBLE
    )
