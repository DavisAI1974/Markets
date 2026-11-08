"""c20: which couplings repeat across the four days, per spread regime (the day is the unit of independence).
Usage: python3 -I c20_crossday.py [nosettle]
Reads tables/<date>/t3_regime_coupling[_nosettle].csv for the four dates and the saved shifted-Y draws (nullrho_*.npz).
For every (regime, x, y) pair present on all four days it tabulates the four rhos, the number of days sharing the majority sign,
the smallest and median |rho|, how many days lie beyond their own family-wise line, and the chunk agreement per day.
The shifted-Y draws give the reference distribution: for draw s the four days' s-th shifted rho matrices are combined exactly as the observed ones are
(each day is shifted independently).  The comparison is shown as full distributions (counts by number of agreeing days, quantiles of the smallest |rho|),
not as a pass/fail cut.  The date is a column label only.  No trade cost anywhere."""
import sys; sys.path.insert(0, '.')   # cwd is this code directory, not a data directory
from odcfg import *
import numpy as np, pandas as pd
SUF = '_nosettle' if 'nosettle' in sys.argv[1:] else ''
REGS = ['1', '2', '3+']
FAM = {'signed move': ['dm_1', 'dm_5', 'dm_20', 'dm_60'], 'magnitude': ['am_5', 'am_20'], 'quote response': ['dbid_5', 'dask_5', 'dspr_5'],
       'flow persistence': ['F_net_5', 'F_net_20'], 'book response': ['F_sup_b_5', 'F_sup_a_5', 'F_cx_b_5', 'F_cx_a_5', 'F_add_b_5', 'F_add_a_5']}
fam_of = {y: f for f, ys in FAM.items() for y in ys}
T = pd.concat([pd.read_csv(tab(d, f't3_regime_coupling{SUF}.csv')) for d in DATES], ignore_index=True)
pairs_out = []; summ = []; null_dist = {}
for reg in REGS:
    t = T[T.regime == reg]
    piv = {c: t.pivot(index=['x', 'y'], columns='date', values=c) for c in ('rho', 'n', 'chunks', 'same_sign_chunks', 'beyond_null95')}
    ok = piv['rho'].dropna().index                          # pairs defined on all four days
    P = pd.DataFrame(index=ok)
    for d in DATES:
        P[f'rho_{d[4:]}'] = piv['rho'].loc[ok, int(d) if int(d) in piv['rho'].columns else d]
    R = P[[f'rho_{d[4:]}' for d in DATES]].to_numpy()
    for d in DATES:
        P[f'chunks_agree_{d[4:]}'] = piv['same_sign_chunks'].loc[ok, int(d) if int(d) in piv['rho'].columns else d].astype(int).astype(str) + '/' + piv['chunks'].loc[ok, int(d) if int(d) in piv['rho'].columns else d].astype(int).astype(str)
    P['days_beyond_null95'] = piv['beyond_null95'].loc[ok].astype(int).sum(axis=1).to_numpy()
    pos = (R > 0).sum(1); neg = (R < 0).sum(1); P['days_same_sign'] = np.maximum(pos, neg); P['majority_sign'] = np.where(pos >= neg, '+', '-')
    P['min_abs_rho'] = np.abs(R).min(1); P['median_rho'] = np.median(R, 1); P['range_rho'] = R.max(1) - R.min(1)
    P['family'] = [fam_of[y] for y in P.index.get_level_values('y')]
    P = P.reset_index(); P.insert(0, 'regime', reg)
    P = P.sort_values(['days_same_sign', 'min_abs_rho'], ascending=[False, False]); pairs_out.append(P)
    # shifted-Y reference: draw s uses the s-th saved matrix of each day, aligned on the same pairs
    NS = {}
    for d in DATES:
        z = np.load(f'{WORK}/nullrho_{d}_{reg.replace("+", "p")}{SUF}.npz'); xs, ys = list(z['x']), list(z['y']); ix = {(a, b): (i, j) for i, a in enumerate(xs) for j, b in enumerate(ys)}
        NS[d] = np.array([[m[ix[(a, b)]] for (a, b) in ok] for m in z['null']])
    nd = []; nmin = []
    for s in range(NS[DATES[0]].shape[0]):
        Rn = np.column_stack([NS[d][s] for d in DATES]); pn = (Rn > 0).sum(1); nn = (Rn < 0).sum(1); same = np.maximum(pn, nn)
        nd.append([int((same == k).sum()) for k in (2, 3, 4)]); nmin.append(np.quantile(np.abs(Rn).min(1)[same == 4], [.5, .9, .99]) if (same == 4).any() else [np.nan] * 3)
    nd = np.array(nd); nmin = np.array(nmin)
    obs = [int((P.days_same_sign == k).sum()) for k in (2, 3, 4)]
    q4 = P[P.days_same_sign == 4].min_abs_rho
    summ.append(dict(regime=reg, pairs_on_all_four_days=len(P), obs_2_of_4=obs[0], obs_3_of_4=obs[1], obs_4_of_4=obs[2],
                     null_2_of_4_mean=nd[:, 0].mean(), null_3_of_4_mean=nd[:, 1].mean(), null_4_of_4_mean=nd[:, 2].mean(), null_4_of_4_min=nd[:, 2].min(), null_4_of_4_max=nd[:, 2].max(),
                     obs_4of4_minabs_p50=q4.quantile(.5), obs_4of4_minabs_p90=q4.quantile(.9), obs_4of4_minabs_p99=q4.quantile(.99), obs_4of4_minabs_max=q4.max(),
                     null_4of4_minabs_p50_mean=np.nanmean(nmin[:, 0]), null_4of4_minabs_p90_mean=np.nanmean(nmin[:, 1]), null_4of4_minabs_p99_mean=np.nanmean(nmin[:, 2]),
                     obs_days_beyond_null95_all4=int((P.days_beyond_null95 == 4).sum()), obs_days_beyond_null95_ge3=int((P.days_beyond_null95 >= 3).sum()), null_draws=int(nd.shape[0])))
    null_dist[reg] = nd
A = pd.concat(pairs_out, ignore_index=True); A.to_csv(tab('crossday', f't4_crossday_pairs{SUF}.csv'), index=False)
S = pd.DataFrame(summ); S.to_csv(tab('crossday', f't4_crossday_summary{SUF}.csv'), index=False)
np.savez_compressed(f'{WORK}/crossday_null_counts{SUF}.npz', **{k.replace('+', 'p'): v for k, v in null_dist.items()})
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print(S.round(3).T.to_string())
