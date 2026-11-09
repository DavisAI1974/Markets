import numpy as np
import pandas as pd
import json
from research_atlas_continuous import flow_features, predicates, associate_births, book_context, OUT


def tape(buy, sell):
    return pd.DataFrame(dict(second=np.arange(len(buy)) + 1000,
                             buy=buy, sell=sell, unknown=np.zeros(len(buy))))


def test_future_changes_cannot_change_earlier_features():
    rng = np.random.default_rng(6)
    d = tape(rng.integers(0, 4, 90), rng.integers(0, 4, 90))
    expected = flow_features(d.iloc[:55])
    d.loc[55:, ['buy', 'sell']] = 10000
    pd.testing.assert_frame_equal(expected, flow_features(d).iloc[:55])


def test_expiry_weakening_is_not_fresh_opposition():
    b, s = np.zeros(45), np.zeros(45)
    b[1], b[5], s[6] = 9, 2, 1
    f = flow_features(tape(b, s))
    p = predicates(f)
    assert p['step_weakening'][21] and p['expiry_only_weakening'][21]
    assert not p['fresh_opposed_weakening'][21]
    assert f.loc[21, 'expired_buy'] == 9
    assert f.loc[21, 'decision_ns'] == 1022_000_000_000


def test_empty_is_not_balanced_and_gaps_require_new_history():
    d = tape(np.zeros(65), np.zeros(65))
    d.loc[35:, 'second'] += 4
    f = flow_features(d)
    assert f.ratio.isna().all()
    assert not f.loc[35:54, 'flow_available'].any()
    assert f.loc[55, 'flow_available']
    assert not predicates(f)['half_weakening'].any()


def test_birth_join_is_strict_and_keeps_unmatched_cases():
    events = pd.DataFrame(dict(hypothesis=['x'] * 3,
                               decision_ns=[90_000_000_000, 100_000_000_000, 120_000_000_000]))
    births = pd.DataFrame(dict(candidate_id=['a', 'b', 'c'], birth_second=[100, 101, 200]))
    result = associate_births(events, births, ['x'])
    assert len(result) == 3
    assert result.loc[0, 'signals_in_prior60'] == 1
    assert result.loc[0, 'last_lead_s'] == 10
    assert result.loc[1, 'signals_in_prior60'] == 2
    assert result.loc[2, 'signals_in_prior60'] == 0
    assert np.isnan(result.loc[2, 'last_lead_s'])


def test_quote_at_cutoff_is_not_available_and_reset_blocks_history():
    d = flow_features(tape(np.ones(50), np.ones(50)))
    a = np.array([[999*10**9, 0, 201, 100, 101, 1, 2, 1, 0],
                  [1025*10**9, 1, 203, 101, 102, 2, 1, 1, 0],
                  [1030*10**9, 2, 203, 101, 102, 2, 1, 0, 1],
                  [1031*10**9, 3, 203, 101, 102, 2, 1, 1, 1]])
    f = book_context(d, a)
    assert f.loc[24, 'source_cursor'] == 0
    assert f.loc[25, 'source_cursor'] == 1
    assert not f.loc[30:, 'input_available'].any()



def test_finalization_only_keeps_birth_without_inventing_recognition():
    from finish_four_day_extensions import birth_rows
    c = [{"candidate_id":"final","recognition_group":None,
          "original_episode":{"birth_recv_ns":1696366763000000000}}]
    assert birth_rows(c) == [{"candidate_id":"final","birth_second":1696366763}]
    assert c[0]["recognition_group"] is None
