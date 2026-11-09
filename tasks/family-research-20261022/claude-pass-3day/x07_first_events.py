"""First-event times after the birth-second start, per candidate, on my reconstructed books (my analog of the 'recognition minus first event' sorted curves; definitions are mine, not the other agent's).
Usage: OD_SESS=<session> python3 -I x07_first_events.py
Anchor = birth-second start boundary (the pre cutoff).  Boundaries b_k = anchor + k s, k = 0 .. 700; state = book after the last completed group closed by b_k.
  aggressor_start   : first second k (interval (b_k, b_k+1]) with aggressor lots in the birth direction            (k of the interval)
  touch_size_change : first boundary k >= 1 at which the bid touch size or the ask touch size differs from its value at b_0
  quote_relocation  : first boundary k >= 1 at which the best bid price or the best ask price differs from its value at b_0
delay_s = recognition receive time minus the anchor.   y = delay_s - k   (positive: event before recognition; negative: event after recognition).
NaN where no event occurs before the last boundary on the tape (reported as unavailable).  Writes tables/dipole/<SESS>/x07_first_events.csv"""
import sys; sys.path.insert(0, '.')
from odcfg import *
import gzip, json, numpy as np, pandas as pd
from c04_order_features import enrich, Windows
S = 10**9; KMAX = 700
rows = [json.loads(l) for l in gzip.open(CAND, 'rt')]
F = pd.read_csv(f'{TABD}/t6_cohort_features.csv', dtype={'tape': str}); cov = pd.read_csv(f'{TABD}/t6_cohort_coverage.csv', dtype={'tape': str}).set_index('row')
F['pre_ns'] = cov.loc[F.row, 'pre_ns'].to_numpy(); F['rec_ns'] = cov.loc[F.row, 'rec_ns'].to_numpy(); F['pol'] = [int(rows[k]['recorded_operands']['polarity']) for k in F.row]
out = []
for d in TAPES:
    s = F[F.tape == d]
    if not len(s): continue
    R, C = enrich(pd.read_parquet(recon(d))); W = Windows(R, C); ci = {c: i for i, c in enumerate(W.cols)}; end = int(W.last_ts[-1])
    bb = R.bb_a.to_numpy().astype(np.int64); ba = R.ba_a.to_numpy().astype(np.int64); bsz = R.bsz_a.to_numpy(); asz = R.asz_a.to_numpy()
    anc = s.pre_ns.to_numpy(np.int64); pol = s.pol.to_numpy(); n = len(s); ks = np.arange(0, KMAX + 1)
    B = anc[:, None] + ks[None, :] * S; j = np.searchsorted(W.last_ts, B.ravel(), side='right') - 1; E = np.where(j >= 0, W.last_idx[np.maximum(j, 0)], 0).reshape(n, len(ks)); past = B > end
    with_ = np.where(pol[:, None] > 0, np.diff(W.cum[ci['trade_buyagg']][E + 1], axis=1), np.diff(W.cum[ci['trade_sellagg']][E + 1], axis=1))
    with_ = np.where(past[:, 1:], 0, with_)
    def first(mask, valid):
        m = mask & valid; has = m.any(1); return np.where(has, m.argmax(1), -1)
    k_agg = first(with_ > 0, ~past[:, 1:])
    valid = ~past[:, 1:]
    k_tch = first((bsz[E][:, 1:] != bsz[E][:, [0]]) | (asz[E][:, 1:] != asz[E][:, [0]]), valid) + 1
    k_qte = first((bb[E][:, 1:] != bb[E][:, [0]]) | (ba[E][:, 1:] != ba[E][:, [0]]), valid) + 1
    k_tch = np.where(k_tch == 0, -1, k_tch); k_qte = np.where(k_qte == 0, -1, k_qte)
    # also the first-event second counted from the end of the horizon covered by the tape
    last_k = np.where(past.any(1), past.argmax(1) - 1, KMAX)
    df = pd.DataFrame(dict(row=s.row.to_numpy(), tape=d, polarity=pol, delay_s=(s.rec_ns.to_numpy() - anc) / S, last_k_on_tape=last_k, k_aggressor_start=k_agg, k_touch_size_change=k_tch, k_quote_relocation=k_qte))
    out.append(df); print(d, n, {c: int((df[c] < 0).sum()) for c in ('k_aggressor_start', 'k_touch_size_change', 'k_quote_relocation')}, 'no event within horizon', flush=True)
pd.concat(out, ignore_index=True).to_csv(f'{TABD}/x07_first_events.csv', index=False)
