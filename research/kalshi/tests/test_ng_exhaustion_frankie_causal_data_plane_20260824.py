from __future__ import annotations

import dataclasses

import pytest

from research.kalshi.ng_exhaustion_frankie_causal_data_plane_20260824 import (
    GENESIS,
    REQUIRED_LEGACY_OBSERVABLES,
    AtRiskOpportunity,
    CausalDataPlaneError,
    ChainExtensionState,
    ClockVector,
    OpportunityKind,
    ProtectedCausalPrefix,
    ProspectiveDiscoveryMark,
    default_legacy_v4_mappings,
    derive_geometry_second,
    make_data_plane_row,
    make_protected_prefix,
    open_at_risk_opportunity,
    reveal_opportunity_outcome,
    seal_prospective_mark,
    seal_semantic_crosswalk,
    validate_continuous_data_plane,
)

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def clocks(second: float = 100.0, *, lock_at: float | None = None) -> ClockVector:
    return ClockVector(
        event_at=second - 0.30,
        received_at=second - 0.20,
        event_known_by=second - 0.10,
        feature_available_at=second,
        evaluated_at=second + 0.05,
        lock_at=lock_at,
    )


def geometry(second: float = 100.0, *, prior=None):
    return derive_geometry_second(
        causal_second=second,
        feature_available_at=second,
        price=4.125 if prior is None else 4.130,
        buy_aggressor_qty_20s=75,
        sell_aggressor_qty_20s=25,
        book_imbalance_top10=0.20 if prior is None else 0.10,
        predecessor_states=("P", "O", "S", "X"),
        ancestry_gap_seconds=(7.0, 11.0, 13.0),
        unresolved_age_seconds=8.0 if prior is None else 9.0,
        prior=prior,
    )


def opportunity(
    *,
    kind: OpportunityKind = OpportunityKind.AT_RISK,
    state: ChainExtensionState = ChainExtensionState.UNRESOLVED,
    evaluated_at: float = 100.05,
) -> AtRiskOpportunity:
    return open_at_risk_opportunity(
        opportunity_id=f"opp:{kind.value}",
        run_id="october-blind",
        predecessor_ids=("pred-1", "pred-2"),
        ancestry_ids=("root-1", "pred-1", "pred-2"),
        predecessor_known_by=99.9,
        evaluated_at=evaluated_at,
        reveal_not_before=110.0,
        kind=kind,
        chain_state=state,
        state_prefix_hash=A,
        source_manifest_sha256=A,
    )


def test_clock_vector_keeps_six_clocks_distinct_and_fails_closed() -> None:
    vector = clocks(lock_at=100.10).validate()
    assert vector.event_at == 99.70
    assert vector.received_at == 99.80
    assert vector.event_known_by == 99.90
    assert vector.feature_available_at == 100.0
    assert vector.evaluated_at == 100.05
    assert vector.lock_at == 100.10

    with pytest.raises(CausalDataPlaneError, match="feature_available_at"):
        dataclasses.replace(vector, feature_available_at=99.85).validate()
    with pytest.raises(CausalDataPlaneError, match="lock_at"):
        dataclasses.replace(vector, lock_at=100.01).validate()


def test_exact_legacy_v4_crosswalk_has_causal_100_percent_coverage_receipt() -> None:
    mappings = default_legacy_v4_mappings()
    receipt = seal_semantic_crosswalk(
        mappings=mappings,
        source_manifest_sha256=A,
        adapter_revision="NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823",
        transform_sha256=B,
    )

    assert {item.legacy_observable for item in mappings} == set(REQUIRED_LEGACY_OBSERVABLES)
    assert receipt.coverage_numerator == receipt.coverage_denominator == len(REQUIRED_LEGACY_OBSERVABLES)
    assert receipt.coverage_fraction == 1.0
    assert receipt.causal_availability_clock == "ts_recv_ns"
    assert all(item.requires_complete_event_group for item in mappings)
    assert len(receipt.receipt_hash) == 64

    with pytest.raises(CausalDataPlaneError, match="100%"):
        seal_semantic_crosswalk(
            mappings=mappings[:-1],
            source_manifest_sha256=A,
            adapter_revision="NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823",
            transform_sha256=B,
        )


def test_crosswalk_rejects_semantic_or_availability_drift() -> None:
    mappings = list(default_legacy_v4_mappings())
    mappings[0] = dataclasses.replace(mappings[0], causal_availability_clock="ts_event_ns")
    with pytest.raises(CausalDataPlaneError, match="ts_recv_ns"):
        seal_semantic_crosswalk(
            mappings=mappings,
            source_manifest_sha256=A,
            adapter_revision="adapter-v1",
            transform_sha256=B,
        )

    mappings = list(default_legacy_v4_mappings())
    mappings[0] = dataclasses.replace(mappings[0], derivation="RENAMED_BUT_NOT_EQUIVALENT")
    with pytest.raises(CausalDataPlaneError, match="semantic drift"):
        seal_semantic_crosswalk(
            mappings=mappings,
            source_manifest_sha256=A,
            adapter_revision="adapter-v1",
            transform_sha256=B,
        )


def test_per_second_geometry_preserves_legacy_surface_and_derived_paths() -> None:
    first = geometry()
    second = geometry(101.0, prior=first)

    assert first.native_signed_flow_20s == 50
    assert first.roll20 == 0.5
    assert first.predecessor_states == ("P", "O", "S", "X")
    assert second.price_delta_1s == pytest.approx(0.005)
    assert second.roll20_delta_1s == 0.0
    assert second.roll20_curvature_1s is None
    assert second.book_imbalance_delta_1s == pytest.approx(-0.10)
    assert second.unresolved_age_seconds == 9.0

    no_trades = derive_geometry_second(
        causal_second=102.0,
        feature_available_at=102.0,
        price=None,
        buy_aggressor_qty_20s=0,
        sell_aggressor_qty_20s=0,
        book_imbalance_top10=None,
        predecessor_states=(),
        ancestry_gap_seconds=(),
        unresolved_age_seconds=None,
    )
    assert no_trades.roll20 is None
    assert no_trades.price is None


def test_geometry_rejects_future_features_and_unknown_predecessor_states() -> None:
    with pytest.raises(CausalDataPlaneError, match="feature availability"):
        derive_geometry_second(
            causal_second=100.0,
            feature_available_at=100.1,
            price=4.1,
            buy_aggressor_qty_20s=1,
            sell_aggressor_qty_20s=1,
            book_imbalance_top10=0.0,
            predecessor_states=(),
            ancestry_gap_seconds=(),
            unresolved_age_seconds=None,
        )
    with pytest.raises(CausalDataPlaneError, match="P/O/S/X"):
        derive_geometry_second(
            causal_second=100.0,
            feature_available_at=100.0,
            price=4.1,
            buy_aggressor_qty_20s=1,
            sell_aggressor_qty_20s=1,
            book_imbalance_top10=0.0,
            predecessor_states=("D1",),
            ancestry_gap_seconds=(),
            unresolved_age_seconds=None,
        )


def test_continuous_data_plane_is_one_second_hash_chained_without_resets() -> None:
    first_geometry = geometry()
    first = make_data_plane_row(
        run_id="october-blind",
        source_object_id="s3://canonical/part-1.dbn.zst",
        source_manifest_sha256=A,
        crosswalk_receipt_hash=B,
        clocks=clocks(),
        geometry=first_geometry,
        opportunity=opportunity(),
        prior_row_hash=GENESIS,
    )
    second = make_data_plane_row(
        run_id="october-blind",
        source_object_id="s3://canonical/part-1.dbn.zst",
        source_manifest_sha256=A,
        crosswalk_receipt_hash=B,
        clocks=clocks(101.0),
        geometry=geometry(101.0, prior=first_geometry),
        opportunity=opportunity(evaluated_at=101.05),
        prior_row_hash=first.row_hash,
    )

    assert validate_continuous_data_plane((first, second)) == second.row_hash

    gap = make_data_plane_row(
        run_id="october-blind",
        source_object_id="s3://canonical/part-1.dbn.zst",
        source_manifest_sha256=A,
        crosswalk_receipt_hash=B,
        clocks=clocks(102.0),
        geometry=geometry(102.0, prior=second.geometry),
        opportunity=opportunity(evaluated_at=102.05),
        prior_row_hash=first.row_hash,
    )
    with pytest.raises(CausalDataPlaneError, match="one lawful row per second"):
        validate_continuous_data_plane((first, gap))


@pytest.mark.parametrize(
    ("kind", "state"),
    [
        (OpportunityKind.AT_RISK, ChainExtensionState.UNRESOLVED),
        (OpportunityKind.AT_RISK, ChainExtensionState.EXTENDING),
        (OpportunityKind.STOPPED_CHAIN_CONTROL, ChainExtensionState.STOPPED),
        (OpportunityKind.NEGATIVE_CONTROL, ChainExtensionState.NO_CHAIN),
    ],
)
def test_opportunities_are_predecessor_defined_before_any_later_outcome(
    kind: OpportunityKind, state: ChainExtensionState
) -> None:
    item = opportunity(kind=kind, state=state).validate()
    assert item.opened_at == item.predecessor_known_by
    assert item.evaluated_at < item.reveal_not_before
    assert not hasattr(item, "target_event_id")
    assert not hasattr(item, "outcome")


def test_outcome_cannot_be_revealed_until_the_frozen_boundary() -> None:
    item = opportunity()
    with pytest.raises(CausalDataPlaneError, match="reveal boundary"):
        reveal_opportunity_outcome(
            item,
            outcome="CHAIN_EXTENDED",
            revealed_at=109.999,
            outcome_source_sha256=C,
        )
    receipt = reveal_opportunity_outcome(
        item,
        outcome="CHAIN_EXTENDED",
        revealed_at=110.0,
        outcome_source_sha256=C,
    )
    assert receipt.opportunity_hash == item.opportunity_hash
    assert receipt.revealed_at == 110.0
    assert len(receipt.receipt_hash) == 64


def test_protected_prefix_and_mark_bind_only_to_the_lawful_causal_prefix() -> None:
    crosswalk = seal_semantic_crosswalk(
        mappings=default_legacy_v4_mappings(),
        source_manifest_sha256=A,
        adapter_revision="adapter-v1",
        transform_sha256=B,
    )
    row = make_data_plane_row(
        run_id="october-blind",
        source_object_id="s3://canonical/part-1.dbn.zst",
        source_manifest_sha256=A,
        crosswalk_receipt_hash=crosswalk.receipt_hash,
        clocks=clocks(),
        geometry=geometry(),
        opportunity=opportunity(),
    )
    prefix = make_protected_prefix(row=row, crosswalk=crosswalk)

    assert isinstance(prefix, ProtectedCausalPrefix)
    assert prefix.causal_cutoff == row.clocks.feature_available_at
    assert not hasattr(prefix, "canonical_t0")
    assert not hasattr(prefix, "label")
    assert not hasattr(prefix, "population")

    mark = seal_prospective_mark(
        prefix=prefix,
        candidate_id="candidate-1",
        detector_revision="prospective-detector-v1",
        detector_source_sha256=D,
        detector_marked_at=100.06,
        event_known_by=100.06,
    )
    assert isinstance(mark, ProspectiveDiscoveryMark)
    assert mark.mark_mode == "PROSPECTIVE"
    assert mark.state_prefix_hash == prefix.state_prefix_hash

    with pytest.raises(CausalDataPlaneError, match="detector_marked_at"):
        seal_prospective_mark(
            prefix=prefix,
            candidate_id="candidate-1",
            detector_revision="prospective-detector-v1",
            detector_source_sha256=D,
            detector_marked_at=99.99,
            event_known_by=100.06,
        )
