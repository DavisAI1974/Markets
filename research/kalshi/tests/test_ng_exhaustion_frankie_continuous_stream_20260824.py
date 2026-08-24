from __future__ import annotations

import pytest

from research.kalshi.ng_exhaustion_frankie_causal_data_plane_20260824 import (
    ChainExtensionState,
    OpportunityKind,
    default_legacy_v4_mappings,
    seal_semantic_crosswalk,
    validate_continuous_data_plane,
)
from research.kalshi.ng_exhaustion_frankie_continuous_stream_20260824 import (
    ContinuousV4CausalStreamBuilder,
    OpportunityTransition,
    ProtectedProspectiveWeakeningMarker,
    make_replay_group_callback,
)

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def crosswalk():
    return seal_semantic_crosswalk(
        mappings=default_legacy_v4_mappings(),
        source_manifest_sha256=A,
        adapter_revision="NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823",
        transform_sha256=B,
    )


def transition(
    effective_second: int,
    *,
    opportunity_id: str = "opp-risk",
    kind: OpportunityKind = OpportunityKind.AT_RISK,
    state: ChainExtensionState = ChainExtensionState.UNRESOLVED,
) -> OpportunityTransition:
    return OpportunityTransition(
        effective_second=effective_second,
        opportunity_id=opportunity_id,
        predecessor_ids=("pred-1", "pred-2"),
        ancestry_ids=("root-1", "pred-1", "pred-2"),
        predecessor_states=("P", "O"),
        ancestry_gap_seconds=(8.0,),
        predecessor_known_by=float(effective_second - 10),
        reveal_not_before=float(effective_second + 100),
        kind=kind,
        chain_state=state,
    )


def raw_action(
    action: str,
    second: int,
    *,
    source: str,
    price: float | None = None,
    size: float = 1.0,
    snapshot: bool = False,
    order_id: int = 1,
) -> dict:
    return {
        "action": action,
        "side": "B" if action == "T" else "N",
        "price": price,
        "size": size,
        "order_id": order_id,
        "ts_event_ns": second * 1_000_000_000 + 100_000_000,
        "ts_recv_ns": second * 1_000_000_000 + 200_000_000,
        "is_snapshot": snapshot,
        "source_dbn_object": source,
        "source_dbn_sha256": C,
    }


def fake_group(
    second: int,
    *,
    source: str = "s3://canonical/object-1.dbn.zst",
    actions: tuple[dict, ...] | None = None,
    trades: tuple[tuple[float, float], ...] = (),
    snapshot: bool = False,
    book_imbalance: float = 0.25,
    integrity: dict | None = None,
    event_second: int | None = None,
) -> tuple[dict, list[dict]]:
    event_second = second if event_second is None else int(event_second)
    if actions is None:
        actions = tuple(
            raw_action(
                "T",
                event_second,
                source=source,
                price=price,
                size=size,
                snapshot=snapshot,
                order_id=index + 1,
            )
            for index, (price, size) in enumerate(trades)
        )
        if not actions:
            actions = (raw_action("N", second, source=source, snapshot=snapshot),)

    bid_depth = 125
    ask_depth = 75
    book = {
        "best_bid": 100.0,
        "best_ask": 101.0,
        "spread": 1.0,
        "mid": 100.5,
        "bid_depth_n": bid_depth,
        "ask_depth_n": ask_depth,
        "depth_imbalance_n": book_imbalance,
        "bid_depth_full": 250,
        "ask_depth_full": 150,
        "depth_imbalance_full": 0.25,
        "bid_price_level_count_full": 2,
        "ask_price_level_count_full": 2,
        "bid_order_count_full": 3,
        "ask_order_count_full": 2,
        "bid_levels_full": [
            {
                "price": 100.0,
                "size": 125,
                "order_count": 2,
                "fifo_queue": [
                    {"order_id": 10, "size": 75, "volume_ahead": 0},
                    {"order_id": 11, "size": 50, "volume_ahead": 75},
                ],
            }
        ],
        "ask_levels_full": [
            {
                "price": 101.0,
                "size": 75,
                "order_count": 1,
                "fifo_queue": [{"order_id": 20, "size": 75, "volume_ahead": 0}],
            }
        ],
    }
    frame = {
        "schema": "NG_MBO_V4_NATIVE_EVENT_FRAME_V1",
        "adapter_revision": "NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823",
        "instrument_id": 123,
        "raw_symbol": "NGX1",
        "ts_event_ns": event_second * 1_000_000_000 + 100_000_000,
        "ts_recv_ns": second * 1_000_000_000 + 200_000_000,
        "causal_availability_clock": "ts_recv_ns",
        "event_group_complete_f_last": True,
        "snapshot_bootstrap_only": snapshot,
        "raw_actions": list(actions),
        "book": {key: value for key, value in book.items() if not key.endswith("_full")},
        "activity": {},
        "integrity": dict(integrity or {}),
        "fifo_priority_reconstructed": True,
    }
    envelope = {
        "schema": "NG_MBO_V4_FULL_STATE_ENVELOPE_V1",
        "revision": "NG_EXHAUSTION_MBO_V4_FULL_STATE_REPLAY_V1_20260820",
        "instrument_id": 123,
        "raw_symbol": "NGX1",
        "ts_event_ns": frame["ts_event_ns"],
        "ts_recv_ns": frame["ts_recv_ns"],
        "causal_availability_clock": "ts_recv_ns",
        "compact_event_frame": frame,
        "full_state": {
            "schema": "NG_MBO_V4_CHECKPOINT_STATE_V1",
            "instrument_id": 123,
            "raw_symbol": "NGX1",
            "ts_recv_ns": frame["ts_recv_ns"],
            "book": book,
            "activity": {},
            "integrity": dict(integrity or {}),
        },
        "full_state_mode": "MATERIALIZED_FULL_DEPTH_FIFO_CHECKPOINT",
        "full_state_materialized": True,
        "full_depth_exposed": True,
        "fifo_order_state_exposed": True,
    }
    legacy = []
    for price, size in trades:
        legacy.append(
            {
                "census_view": "LEGACY_CONTROL",
                "ts_event": event_second + 0.1,
                "ts_recv": second + 0.2,
                "action": "T",
                "side": "B" if price > 100.5 else "A",
                "price": price,
                "size": size,
                "bid_px_00": 100.0,
                "ask_px_00": 101.0,
                "bid_sz_00": 125,
                "ask_sz_00": 75,
                "projection_at_f_last": True,
            }
        )
    return envelope, legacy


def builder(
    start: int,
    end: int,
    *,
    transitions: tuple[OpportunityTransition, ...] | None = None,
    marker: ProtectedProspectiveWeakeningMarker | None = None,
) -> ContinuousV4CausalStreamBuilder:
    return ContinuousV4CausalStreamBuilder(
        run_id="october-blind",
        target_start_second=start,
        target_end_second=end,
        source_manifest_sha256=A,
        crosswalk=crosswalk(),
        opportunity_transitions=transitions or (transition(start),),
        marker=marker,
    )


def test_callback_suppresses_bootstrap_and_snapshot_but_retains_all_live_actions() -> None:
    stream = builder(100, 102)
    emitted = []
    callback = make_replay_group_callback(stream, emitted.append)

    env, legacy = fake_group(99, trades=((101.0, 5.0),))
    assert callback(env, legacy) == 0

    env, legacy = fake_group(100, trades=((101.0, 99.0),), snapshot=True)
    assert callback(env, legacy) == 0

    all_actions = tuple(
        raw_action(action, 100, source="s3://canonical/object-1.dbn.zst", price=100.0 if action == "T" else None, size=2.0, order_id=index)
        for index, action in enumerate("ACMRTFN", start=1)
    )
    env, legacy = fake_group(100, actions=all_actions, trades=((100.0, 2.0),))
    assert callback(env, legacy) == 0

    env, legacy = fake_group(101)
    assert callback(env, legacy) == 1
    emitted.extend(stream.finish())

    first = emitted[0]
    assert first.source_second == 100
    assert tuple(item.action for item in first.actions) == tuple("ACMRTFN")
    assert first.quality.snapshot_groups_suppressed == 1
    assert first.legacy.price == 100.0
    assert first.legacy.native_signed_flow == -2.0
    assert first.legacy.roll20 == pytest.approx((5.0 - 2.0) / (5.0 + 2.0))
    assert first.legacy.book_imbalance == 0.25
    assert first.v4_native["book"]["bid_levels_full"][0]["fifo_queue"][1]["volume_ahead"] == 75
    assert first.prefix.state_prefix_hash == first.data_plane_row.row_hash

    diag = stream.diagnostics()
    assert diag["bootstrap_groups_consumed"] == 1
    assert diag["snapshot_groups_suppressed"] == 1
    assert diag["action_counts"] == {
        **{action: 1 for action in "ACMRTF"},
        "N": 2,
    }


def test_one_row_per_second_and_quiet_seconds_carry_explicit_sparse_state() -> None:
    stream = builder(100, 104)
    env, legacy = fake_group(100, trades=((101.0, 6.0), (100.0, 4.0)), book_imbalance=0.40)
    assert stream.consume_group(env, legacy) == ()
    env, legacy = fake_group(103, book_imbalance=-0.20)
    rows = list(stream.consume_group(env, legacy))
    rows.extend(stream.finish())

    assert [row.source_second for row in rows] == [100, 101, 102, 103]
    assert [row.data_plane_row.geometry.causal_second for row in rows] == [101.0, 102.0, 103.0, 104.0]
    assert validate_continuous_data_plane(tuple(row.data_plane_row for row in rows)) == rows[-1].data_plane_row.row_hash

    assert rows[0].legacy.roll20 == pytest.approx(0.20)
    for quiet in rows[1:3]:
        assert quiet.quality.state_status == "QUIET_CARRY"
        assert quiet.quality.price_status == "CAUSAL_CARRY"
        assert quiet.legacy.price == 100.0
        assert quiet.legacy.roll20 == pytest.approx(0.20)
        assert quiet.actions == ()
    assert rows[1].quality.roll20_status == "CAUSAL_ROLLING_CARRY"


def test_exact_roll20_buckets_by_event_second_without_receive_time_backfill() -> None:
    stream = builder(120, 121)
    env, legacy = fake_group(120, event_second=100, trades=((101.0, 5.0),))
    stream.consume_group(env, legacy)
    row = stream.finish()[0]

    assert row.legacy.price == 101.0
    assert row.legacy.native_signed_flow == 0.0
    assert row.legacy.roll20 is None
    assert row.quality.roll20_status == "SPARSE_NO_CLASSIFIED_VOLUME"


def test_backward_only_marker_emits_once_per_distinct_weakening_episode() -> None:
    marker = ProtectedProspectiveWeakeningMarker(detector_source_sha256=D)
    stream = builder(100, 105, marker=marker)

    rows = []
    for second, trades in (
        (100, ((101.0, 6.0), (100.0, 4.0))),
        (101, ((101.0, 4.0),)),
        (102, ((100.0, 4.0),)),
        (103, ((101.0, 10.0),)),
        (104, ((100.0, 10.0),)),
    ):
        env, legacy = fake_group(second, trades=trades)
        rows.extend(stream.consume_group(env, legacy))
    rows.extend(stream.finish())

    marks = [(row.source_second, row.mark) for row in rows if row.mark is not None]
    assert [second for second, _mark in marks] == [102, 104]
    first_mark = marks[0][1]
    second_mark = marks[1][1]
    assert first_mark.detector_revision == "FRANKIE_PROTECTED_ROLL20_WEAKENING_V1"
    assert first_mark.detector_marked_at == first_mark.event_known_by == 103.0
    assert second_mark.detector_marked_at == second_mark.event_known_by == 105.0
    assert first_mark.state_prefix_hash == rows[2].prefix.state_prefix_hash
    assert second_mark.state_prefix_hash == rows[4].prefix.state_prefix_hash
    assert first_mark.mark_hash != second_mark.mark_hash
    assert marker.observe(
        prefix=rows[4].prefix, geometry=rows[4].data_plane_row.geometry
    ) is None
    for forbidden in ("target_event_id", "canonical_t0", "label", "population", "outcome"):
        assert not hasattr(first_mark, forbidden)
        assert not hasattr(second_mark, forbidden)
        assert not hasattr(rows[2].prefix, forbidden)


def test_opportunity_schedule_emits_at_risk_stopped_and_negative_controls() -> None:
    transitions = (
        transition(100),
        transition(
            101,
            opportunity_id="opp-stopped",
            kind=OpportunityKind.STOPPED_CHAIN_CONTROL,
            state=ChainExtensionState.STOPPED,
        ),
        transition(
            102,
            opportunity_id="opp-negative",
            kind=OpportunityKind.NEGATIVE_CONTROL,
            state=ChainExtensionState.NO_CHAIN,
        ),
    )
    stream = builder(100, 103, transitions=transitions)
    rows = []
    for second in range(100, 103):
        env, legacy = fake_group(second)
        rows.extend(stream.consume_group(env, legacy))
    rows.extend(stream.finish())

    assert [row.data_plane_row.opportunity.kind for row in rows] == [
        OpportunityKind.AT_RISK,
        OpportunityKind.STOPPED_CHAIN_CONTROL,
        OpportunityKind.NEGATIVE_CONTROL,
    ]
    assert [row.data_plane_row.opportunity.chain_state for row in rows] == [
        ChainExtensionState.UNRESOLVED,
        ChainExtensionState.STOPPED,
        ChainExtensionState.NO_CHAIN,
    ]


def test_source_object_and_day_boundaries_do_not_reset_the_hash_or_roll20_state() -> None:
    stream = builder(86_399, 86_402)
    env, legacy = fake_group(86_399, source="s3://canonical/day-1.dbn.zst", trades=((101.0, 5.0),))
    stream.consume_group(env, legacy)
    env, legacy = fake_group(86_400, source="s3://canonical/day-2.dbn.zst", trades=((100.0, 5.0),))
    rows = list(stream.consume_group(env, legacy))
    env, legacy = fake_group(86_401, source="s3://canonical/day-2.dbn.zst")
    rows.extend(stream.consume_group(env, legacy))
    rows.extend(stream.finish())

    assert [row.source_object_id for row in rows] == [
        "s3://canonical/day-1.dbn.zst",
        "s3://canonical/day-2.dbn.zst",
        "s3://canonical/day-2.dbn.zst",
    ]
    assert rows[1].legacy.roll20 == 0.0
    assert rows[1].data_plane_row.prior_row_hash == rows[0].data_plane_row.row_hash
    assert rows[1].prior_stream_hash == rows[0].stream_hash
    assert stream.diagnostics()["reset_count"] == 0
