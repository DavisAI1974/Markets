"""x17: the c15 pair-coupling scan with EVERY (x1, x2, y) row kept, so the four days can be compared on the whole family rather than on each day's top 400.
Usage: OD_WORK=<derived dir> python3 -I x17_pair_couplings_full.py <date>
Identical to c15 in transform (closed rows out, activity-quintile percentile ranks), pair list, outcome list, interaction partial rho = corr(y, z1*z2 | z1, z2),
24-chunk same-sign count (chunks with > 300 usable rows), and the family-wise shifted-y line (seed 5, 40 shifts, every third pair, 95 percent), here applied
to every row.  Output: crossday/pairs_full/t2_pair_couplings_full_<date>.csv.  Nothing in tables/ is written.  No trade cost anywhere."""
import sys, os; sys.path.insert(0, '.')
from odcfg import *
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import rankdata
DATE = date_arg(); OUTD = f'{HERE}/crossday/pairs_full'; os.makedirs(OUTD, exist_ok=True)
df = pd.read_parquet(big(DATE, 'grid')).sort_values('cut_ns').reset_index(drop=True); df = df[~df.closed].reset_index(drop=True); N = len(df)
df['F_supdiff_5'] = df.F_sup_b_5 - df.F_sup_a_5
X = ['imb_1', 'imb_5', 'imb_20', 'imb_60', 'net_5', 'net_20', 'tch_imb', 'tchn_imb', 'spr', 'bsz', 'asz', 'bn', 'an', 'bsz_per_ord', 'asz_per_ord', 'near5_imb', 'near10_imb',
     'supdiff_5', 'supdiff_20', 'sup_b_5', 'sup_a_5', 'refill_b_5', 'refill_a_5', 'refill_b_20', 'refill_a_20', 'cxshare_b_20', 'cxshare_a_20', 'modT_b_20', 'modT_a_20', 'addT_b_5', 'addT_a_5',
     'cxT_b_5', 'cxT_a_5', 'rmF_b_5', 'rmF_a_5', 'fill_b_5', 'fill_a_5', 'prior_5', 'prior_20', 'prior_60', 'qchg_5', 'qchg_60', 'ntr_60']
Y = ['dm_5', 'dm_20', 'dspr_5', 'F_supdiff_5', 'F_net_5', 'am_20']
act = df.ntr_60.rank(pct=True) + df.qchg_60.rank(pct=True) + df.ntr_20.rank(pct=True); q = pd.qcut(act.rank(method='first'), 5, labels=False).to_numpy()
def sp(col):
    a = df[col].to_numpy(float); out = np.full(N, np.nan)
    for k in range(5):
        m = (q == k) & ~np.isnan(a)
        if m.sum() > 50: out[m] = (rankdata(a[m]) - 0.5) / m.sum() - 0.5
    return out
Z = {c: sp(c) for c in X}; YY = {c: sp(c) for c in Y}; chunk = np.minimum((np.arange(N) * 24) // N, 23)
def partial_int(z1, z2, y, m):
    a, b, yy = z1[m], z2[m], y[m]; p = a * b; A = np.column_stack([np.ones(m.sum()), a, b])
    rp = p - A @ np.linalg.lstsq(A, p, rcond=None)[0]; ry = yy - A @ np.linalg.lstsq(A, yy, rcond=None)[0]
    d = np.sqrt((rp ** 2).sum() * (ry ** 2).sum()); return (rp * ry).sum() / d if d > 0 else np.nan
pairs = [(X[i], X[j]) for i in range(len(X)) for j in range(i + 1, len(X))]; rows = []; skipped = 0
for (c1, c2) in pairs:
    m0 = ~np.isnan(Z[c1]) & ~np.isnan(Z[c2])
    if m0.sum() < 3000: skipped += 1; continue
    for yc in Y:
        m = m0 & ~np.isnan(YY[yc]); r = partial_int(Z[c1], Z[c2], YY[yc], m)
        ch = []
        for k in range(24):
            mk = m & (chunk == k)
            if mk.sum() > 300: ch.append(partial_int(Z[c1], Z[c2], YY[yc], mk))
        ch = np.array(ch); same = int((np.sign(ch) == np.sign(r)).sum()) if len(ch) else 0
        rows.append(dict(x1=c1, x2=c2, y=yc, int_rho=r, n=int(m.sum()), chunks=len(ch), same_sign_chunks=same))
M = pd.DataFrame(rows); print(DATE, 'pair-outcome rows', len(M), 'pairs skipped (<3000 usable rows)', skipped)
rng = np.random.default_rng(5); mx = []
for _ in range(40):
    sh = int(rng.integers(1200, N - 1200)); best = 0
    for (c1, c2) in pairs[::3]:
        m0 = ~np.isnan(Z[c1]) & ~np.isnan(Z[c2])
        if m0.sum() < 3000: continue
        for yc in Y:
            ys = np.roll(YY[yc], sh); m = m0 & ~np.isnan(ys); r = partial_int(Z[c1], Z[c2], ys, m); best = max(best, abs(r) if not np.isnan(r) else 0)
    mx.append(best)
thr = np.quantile(mx, .95); M['exceeds_line'] = M.int_rho.abs() > thr; M['line'] = thr; M['abs'] = M.int_rho.abs(); M = M.sort_values('abs', ascending=False)
M.to_csv(f'{OUTD}/t2_pair_couplings_full_{DATE}.csv', index=False); print(DATE, 'line %.4f' % thr, 'rows beyond line', int(M.exceeds_line.sum()))
top = pd.read_csv(tab(DATE, 't2_pair_couplings_top400.csv')); j = top.merge(M, on=['x1', 'x2', 'y'], suffixes=('_c15', ''))
print(DATE, 'top-400 check: rows matched', len(j), 'of', len(top), '| max |int_rho diff| %.3g' % (j.int_rho_c15 - j.int_rho).abs().max())
