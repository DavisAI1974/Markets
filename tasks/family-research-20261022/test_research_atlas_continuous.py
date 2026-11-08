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


def test_retained_evidence_has_all_cases_and_causal_coordinates():
    f = pd.read_csv(OUT / 'observations.csv.gz')
    e = pd.read_csv(OUT / 'onsets.csv.gz')
    links = pd.read_csv(OUT / 'birth-links.csv.gz')
    summary = pd.read_csv(OUT / 'outcome-summary.csv')
    assert len(f) == 82800
    assert e.quote_known_by_ns.lt(e.decision_ns).all()
    assert e.input_available.all()
    assert not any('birth' in c or 'future' in c for c in e.columns)
    assert links.groupby('hypothesis').candidate_id.nunique().eq(863).all()
    assert links.loc[links.signals_in_prior60.gt(0), 'last_lead_s'].between(1, 60).all()
    assert (summary.up + summary.down + summary.flat == summary.available).all()
    assert (summary.flow_weaker + summary.flow_stronger + summary.flow_same == summary.flow_comparable).all()
    np.testing.assert_allclose(e.loc[e.operator_defined, 'ratio'], e.loc[e.operator_defined, 'imb_level'])


def test_paper_register_keeps_every_arm_and_undefined_prebirth_contrast():
    register = json.loads((OUT / 'paper-hypotheses.json').read_text())
    assert all(r['paper_disposition'] == 'retain_for_more_days' for r in register)
    arms = [r for r in register if r['kind'] == 'recognition_model_arm']
    assert len(arms) == 11
    assert any(r['hypothesis_id'] == 'NG-STACK-v1:full' for r in arms)
    contrasts = [r for r in register if r['kind'] == 'retrospective_prebirth_contrast']
    assert len(contrasts) == 88
    original = pd.read_csv(OUT.parent / 'prebirth-summary.csv')
    undefined = original[original.defined_pairs.eq(0)]
    assert len(undefined) > 0
    identifiers = {r['hypothesis_id'] for r in contrasts}
    assert all(f'NG-PREBIRTH-v1:{r.population}:{r.lead_s}:{r.feature}' in identifiers
               for r in undefined.itertuples())
    queue = pd.read_csv(OUT / 'paper-date-queue.csv')
    assert queue.groupby('hypothesis_id').size().eq(5).all()
    assert len(queue) == len(register) * 5
    assert queue.simulator_status.eq('not_configured_or_executed').all()
