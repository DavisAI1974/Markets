"""Pair couplings among market conditions.  For features z1, z2 (activity-quintile percentile ranks) and outcome y (same transform):
 interaction partial rho = corr(y, z1*z2 | z1, z2)  ; also sign of the z1 effect in the low-z2 vs high-z2 thirds (does z2 flip z1?).
 Stability: sign of the interaction partial across 24 contiguous chronological chunks.  Null: cyclic shift of y (>=1200 rows), 200 shifts, max |interaction| over all pairs and outcomes.
 Provenance columns (cut_ns, rec_idx) are carried in the output of exemplars, never used here."""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import rankdata
df = pd.read_parquet('tables/t2_grid.parquet').sort_values('cut_ns').reset_index(drop=True); N = len(df)
df['F_supdiff_5'] = df.F_sup_b_5 - df.F_sup_a_5
X = ['imb_1', 'imb_5', 'imb_20', 'imb_60', 'net_5', 'net_20', 'tch_imb', 'tchn_imb', 'spr', 'bsz', 'asz', 'bn', 'an', 'bsz_per_ord', 'asz_per_ord', 'near5_imb', 'near10_imb',
     'supdiff_5', 'supdiff_20', 'sup_b_5', 'sup_a_5', 'refill_b_5', 'refill_a_5', 'refill_b_20', 'refill_a_20', 'cxshare_b_20', 'cxshare_a_20', 'modT_b_20', 'modT_a_20', 'addT_b_5', 'addT_a_5',
     'cxT_b_5', 'cxT_a_5', 'rmF_b_5', 'rmF_a_5', 'fill_b_5', 'fill_a_5', 'prior_5', 'prior_20', 'prior_60', 'qchg_5', 'qchg_60', 'ntr_60']
Y = ['dm_5', 'dm_20', 'dspr_5', 'F_supdiff_5', 'F_net_5', 'am_20']
act = df.ntr_60.rank(pct=True) + df.qchg_60.rank(pct=True) + df.ntr_20.rank(pct=True)
q = pd.qcut(act.rank(method='first'), 5, labels=False).to_numpy()
def sp(col):
    a = df[col].to_numpy(float); out = np.full(N, np.nan)
    for k in range(5):
        m = (q == k) & ~np.isnan(a)
        if m.sum() > 50: out[m] = (rankdata(a[m]) - 0.5) / m.sum() - 0.5
    return out
Z = {c: sp(c) for c in X}; YY = {c: sp(c) for c in Y}
chunk = np.minimum((np.arange(N) * 24) // N, 23)
def partial_int(z1, z2, y, m):
    a, b, yy = z1[m], z2[m], y[m]; p = a * b
    A = np.column_stack([np.ones(m.sum()), a, b]); 
    rp = p - A @ np.linalg.lstsq(A, p, rcond=None)[0]; ry = yy - A @ np.linalg.lstsq(A, yy, rcond=None)[0]
    d = np.sqrt((rp ** 2).sum() * (ry ** 2).sum()); return (rp * ry).sum() / d if d > 0 else np.nan
rows = []; pairs = [(X[i], X[j]) for i in range(len(X)) for j in range(i + 1, len(X))]
for (c1, c2) in pairs:
    m0 = ~np.isnan(Z[c1]) & ~np.isnan(Z[c2])
    if m0.sum() < 3000: continue
    for yc in Y:
        m = m0 & ~np.isnan(YY[yc]); r = partial_int(Z[c1], Z[c2], YY[yc], m)
        rows.append((c1, c2, yc, r, int(m.sum())))
M = pd.DataFrame(rows, columns=['x1', 'x2', 'y', 'int_rho', 'n']); print('pair-outcome tests', len(M))
rng = np.random.default_rng(5); mx = []
top = M.reindex(M.int_rho.abs().sort_values(ascending=False).index).head(400)       # null for the full family: recompute max over all pairs for a subset of shifts
for _ in range(40):
    sh = int(rng.integers(1200, N - 1200)); best = 0
    for (c1, c2) in pairs[::3]:
        m0 = ~np.isnan(Z[c1]) & ~np.isnan(Z[c2])
        if m0.sum() < 3000: continue
        for yc in Y:
            ys = np.roll(YY[yc], sh); m = m0 & ~np.isnan(ys); r = partial_int(Z[c1], Z[c2], ys, m); best = max(best, abs(r) if not np.isnan(r) else 0)
    mx.append(best)
thr = np.quantile(mx, .95); print('family-wise null (1/3 of pairs, 40 shifts) max|int_rho| 95%%: %.4f' % thr)
M['abs'] = M.int_rho.abs(); M = M.sort_values('abs', ascending=False)
# stability + sign-flip diagnostics for the top 60
out = []
for _, r in M.head(60).iterrows():
    z1, z2, y = Z[r.x1], Z[r.x2], YY[r.y]; m0 = ~np.isnan(z1) & ~np.isnan(z2) & ~np.isnan(y)
    ch = []
    for k in range(24):
        mk = m0 & (chunk == k)
        if mk.sum() > 300: ch.append(partial_int(z1, z2, y, mk))
    ch = np.array(ch); same = int((np.sign(ch) == np.sign(r.int_rho)).sum())
    lo = m0 & (z2 <= np.nanquantile(z2[m0], 1 / 3)); hi = m0 & (z2 >= np.nanquantile(z2[m0], 2 / 3))
    c_lo = np.corrcoef(z1[lo], y[lo])[0, 1]; c_hi = np.corrcoef(z1[hi], y[hi])[0, 1]
    out.append(dict(x1=r.x1, x2=r.x2, y=r.y, int_rho=r.int_rho, n=r.n, chunks=len(ch), same_sign=same, x1_effect_when_x2_low=c_lo, x1_effect_when_x2_high=c_hi, flips=bool(np.sign(c_lo) != np.sign(c_hi)), exceeds=abs(r.int_rho) > thr))
O = pd.DataFrame(out); O.to_csv('tables/t2_pair_couplings_top60.csv', index=False); M.head(400).to_csv('tables/t2_pair_couplings_top400.csv', index=False)
pd.set_option('display.width', 230); print(O.round(3).to_string(index=False))
