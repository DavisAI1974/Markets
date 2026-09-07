"""Synthetic known-answer proofs for the isolated C15 D-chain contract."""
import dataclasses
import math

import pytest

from c15_dstate import DChain, DObservation, ReceiptDChain
from test_causal_prefix_records import record, scope
from causal_prefix_records import RecordPrefixChain
from causal_prefix import ScopeKind


def obs(i, x, **kwargs):
    args = dict(group_ordinal=i, source_member_index=0, session_id="s1",
                anchor_dir=1, far_best_price_raw=x, book_integrity=True)
    args.update(kwargs)
    return DObservation(**args)


def trace(xs):
    machine = DChain(tick_raw=1)
    return machine, [machine.advance_synthetic(obs(i, x)) for i, x in enumerate(xs)]


def present(output, col, raw):
    value = output.columns[col - 1]
    assert value.state == "PRESENT"
    assert value.reason is None
    assert value.value == pytest.approx(raw)


def missing(output, cols, reason):
    for col in cols:
        value = output.columns[col - 1]
        assert (value.value, value.state, value.reason) == (0.0, "MISSING", reason)


def test_t_a_clean_staircase_known_answers():
    _, out = trace([10, 11, 10, 12, 11, 14, 13])
    assert [o.state.n_ext for o in out] == [0, 0, 0, 1, 1, 2, 2]
    present(out[5], 3, math.log(2))
    present(out[5], 4, math.log(2))
    present(out[5], 5, math.log(3))
    present(out[5], 6, math.log(2))
    present(out[6], 1, math.log(2))
    present(out[6], 2, math.log(3))


def test_t_b_monotone_run_and_break():
    _, out = trace([10, 11, 12, 13, 10])
    for o in out[:4]:
        present(o, 2, 0.0)
        missing(o, range(3, 7), "NO_COMPLETED_STEP")
    assert out[4].state.E == 13
    assert out[4].state.broken and not out[4].state.armed
    missing(out[4], range(3, 7), "CHAIN_BROKEN")


def test_t_c_previous_pullback_separates_morphologies():
    _, shallow = trace([10, 11, 10, 12, 11, 14])
    _, deep = trace([10, 12, 10, 13, 12, 15])
    assert shallow[-1].columns[:5] == deep[-1].columns[:5]
    present(shallow[-1], 6, math.log(2))
    present(deep[-1], 6, math.log(3))


def test_t_d_break_clears_history_and_restart_requires_new_pullback():
    _, out = trace([10, 11, 10, 12, 9, 13, 12, 14])
    assert out[4].state.broken and out[4].state.E == 12
    present(out[4], 1, math.log(2))
    present(out[4], 2, 0.0)
    missing(out[4], range(3, 7), "CHAIN_BROKEN")
    assert out[5].state.n_ext == 0 and not out[5].state.broken
    missing(out[5], range(3, 7), "NO_COMPLETED_STEP")
    present(out[7], 4, math.log(2))
    present(out[7], 5, math.log(3))
    missing(out[7], [3, 6], "NO_COMPLETED_STEP")


def test_break_wins_same_group_arm_and_cannot_rearm_while_broken():
    _, out = trace([10, 7, 8, 10, 6, 11])
    assert all(o.state.broken and not o.state.armed for o in out[1:5])
    assert [o.state.pull_depth for o in out[1:5]] == [3, 3, 3, 4]
    assert [o.state.age for o in out[1:5]] == [1, 2, 3, 4]
    assert out[5].state.n_ext == 0


def test_undefined_anchor_freezes_then_same_direction_resumes():
    m, out = trace([10, 9])
    frozen = m.advance_synthetic(obs(2, None, anchor_dir=None))
    assert frozen.state == out[-1].state
    missing(frozen, range(1, 7), "SIDE_UNDEFINED")
    resumed = m.advance_synthetic(obs(3, 11))
    assert resumed.state.n_ext == 1
    present(resumed, 5, math.log(4))


def test_defined_reversal_after_undefined_resets():
    m, _ = trace([10, 9, 11])
    m.advance_synthetic(obs(3, None, anchor_dir=None))
    reversed_ = m.advance_synthetic(obs(4, 10, anchor_dir=-1))
    assert reversed_.state.anchor_dir == -1
    assert reversed_.state.E == -10 and reversed_.state.n_ext == 0
    missing(reversed_, range(3, 7), "NO_COMPLETED_STEP")


@pytest.mark.parametrize("boundary", [dict(source_member_index=1), dict(session_id="s2")])
def test_source_and_session_boundaries_reset_even_during_undefined(boundary):
    m, _ = trace([10, 9, 11])
    m.advance_synthetic(obs(3, None, anchor_dir=None, **boundary))
    resumed = m.advance_synthetic(obs(4, 12, **boundary))
    assert resumed.state.n_ext == 0 and resumed.state.age == 0


def test_bid_direction_matches_mirrored_ask():
    ask, out = trace([10, 11, 10, 12, 11, 14])
    bid = DChain(tick_raw=1)
    mirrored = [bid.advance_synthetic(obs(i, 100 - x, anchor_dir=-1))
                for i, x in enumerate([10, 11, 10, 12, 11, 14])]
    assert [o.columns for o in out] == [o.columns for o in mirrored]


def test_unarmed_later_extreme_does_not_rewrite_last_completed_duration():
    _, out = trace([10, 9, 11, 12, 13])
    assert [o.state.duration_last for o in out[2:]] == [2, 2, 2]
    assert out[2].columns[4] == out[4].columns[4]


@pytest.mark.parametrize("bad", [dict(book_integrity=False), dict(far_best_price_raw=None)])
def test_invalid_book_freezes_state(bad):
    m, out = trace([10, 9])
    invalid = m.advance_synthetic(obs(2, 12, **bad))
    assert invalid.state == out[-1].state
    assert all((v.value, v.state, v.reason) == (0.0, "INVALID", "BOOK_INTEGRITY")
               for v in invalid.columns)


def test_unknown_tick_never_advances_geometry():
    m = DChain(tick_raw=None)
    out = m.advance_synthetic(obs(0, 10))
    assert out.state.E is None
    assert all(v.state == "INVALID" and v.reason == "TICK_UNKNOWN" for v in out.columns)


def test_suffix_and_output_snapshot_invariance():
    xs = [10, 11, 10, 12, 9, 13, 12, 14]
    _, whole = trace(xs + [100, 0, -50, 101])
    for n in range(1, len(xs) + 1):
        _, prefix = trace(xs[:n])
        assert prefix[-1] == whole[n - 1]
    with pytest.raises(dataclasses.FrozenInstanceError):
        whole[0].state.E = 500


@pytest.mark.parametrize("ordinal", [0, 2, -1, True])
def test_invalid_group_progress_is_rejected_without_mutation(ordinal):
    m, out = trace([10])
    with pytest.raises(ValueError):
        m.advance_synthetic(obs(ordinal, 12))
    assert m.advance_synthetic(obs(1, 9)).state.armed


def test_receipted_consumer_binds_code_config_and_real_prefix_authority():
    chain = RecordPrefixChain(scope())
    machine = ReceiptDChain(chain, instrument_id=1, publisher_id=1,
                            tick_raw=1, builder_code_sha="a" * 40)
    r = chain.advance(record(0))
    output = machine.advance(r, session_id="s", anchor_dir=1,
                             far_best_price_raw=10, book_integrity=True)
    assert output.receipt_hash == r.receipt_hash
    assert output.terminal_prefix_hash == r.terminal_prefix_hash
    assert output.builder_code_sha == "a" * 40
    assert len(output.config_hash) == 64
    with pytest.raises(ValueError):
        machine.advance(r, session_id="s", anchor_dir=1,
                        far_best_price_raw=10, book_integrity=True)


def test_receipted_consumer_rejects_other_instrument_and_stale_receipt():
    chain = RecordPrefixChain(scope())
    machine = ReceiptDChain(chain, instrument_id=1, publisher_id=1,
                            tick_raw=1, builder_code_sha="a" * 40)
    r0 = chain.advance(record(0))
    r1 = chain.advance(record(1, instrument=2))
    args = dict(session_id="s", anchor_dir=1, far_best_price_raw=10, book_integrity=True)
    with pytest.raises(ValueError):
        machine.advance(r1, **args)
    # Another instrument's receipt does not invalidate ours.
    machine.advance(r0, **args)
    chain.advance(record(2))
    with pytest.raises(ValueError):
        machine.advance(r0, **args)


@pytest.mark.parametrize("tick", [0, -1, True, 1.0])
def test_tick_config_rejects_invalid_scalar(tick):
    with pytest.raises(ValueError):
        DChain(tick_raw=tick)


@pytest.mark.parametrize("bad", [dict(anchor_dir=True), dict(anchor_dir=0),
    dict(anchor_dir=1.0), dict(far_best_price_raw=float("nan")),
    dict(far_best_price_raw=10.0), dict(book_integrity=1),
    dict(source_member_index=True), dict(session_id="")])
def test_observation_rejects_malformed_scalars(bad):
    with pytest.raises(ValueError):
        obs(0, 10, **bad)


def test_fractional_tick_thresholds_are_exact_and_registry_tick_is_used():
    machine = DChain(tick_raw=10)
    out = [machine.advance_synthetic(obs(i, x)) for i, x in enumerate([100, 91, 90, 110])]
    assert not out[1].state.armed
    assert out[2].state.armed
    present(out[3], 4, math.log(2))
    assert out[3].state.m_last == 1


def test_duplicate_source_member_regression_rejected_transactionally():
    machine = DChain(tick_raw=1)
    machine.advance_synthetic(obs(0, 10, source_member_index=1))
    with pytest.raises(ValueError):
        machine.advance_synthetic(obs(1, 9, source_member_index=0))
    assert machine.advance_synthetic(obs(1, 9, source_member_index=1)).state.armed


def test_receipted_consumer_refuses_probe_authority():
    chain = RecordPrefixChain(scope(kind=ScopeKind.PROBE_ONLY))
    machine = ReceiptDChain(chain, instrument_id=1, publisher_id=1,
                            tick_raw=1, builder_code_sha="a" * 40)
    receipt = chain.advance(record(0))
    with pytest.raises(ValueError):
        machine.advance(receipt, session_id="s", anchor_dir=1,
                        far_best_price_raw=10, book_integrity=True)


def test_code_tick_and_session_changes_bind_distinct_receipts():
    chain = RecordPrefixChain(scope())
    receipt = chain.advance(record(0))
    outputs = []
    for code, tick, session in [("a", 1, "s"), ("b", 1, "s"),
                                ("a", 2, "s"), ("a", 1, "t")]:
        machine = ReceiptDChain(chain, instrument_id=1, publisher_id=1,
                                tick_raw=tick, builder_code_sha=code * 40)
        outputs.append(machine.advance(receipt, session_id=session, anchor_dir=1,
                                       far_best_price_raw=10, book_integrity=True))
    assert len({o.dstate_receipt_hash for o in outputs}) == 4
    assert outputs[0].config_hash != outputs[2].config_hash
