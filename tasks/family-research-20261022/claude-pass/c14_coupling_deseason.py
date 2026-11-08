"""Within-block coupling scan with activity partialled out.
Percentile-rank every column inside each UTC-hour block (removes the session activity cycle).  rho_block = pooled Pearson on those percentile ranks.
rho_part = same after regressing both sides on activity percentiles (ntr_60, qchg_60, ntr_20) — partial rank correlation.
Null = Y cyclically shifted inside each block by >=100 rows (5 min), 300 shifts, max |rho| over all pairs (family-wise).  Stability = same-sign count across blocks."""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import rankdata
df = pd.read_parquet('tables/t2_grid.parquet')
Ycols = ['dm_1', 'dm_5', 'dm_20', 'dm_60', 'am_5', 'am_20', 'dbid_5', 'dask_5', 'dspr_5', 'F_net_5', 'F_net_20', 'F_sup_b_5', 'F_sup_a_5', 'F_cx_b_5', 'F_cx_a_5', 'F_add_b_5', 'F_add_a_5']
outcome_prefix = ('dm_', 'am_', 'dbid_', 'dask_', 'dspr_', 'F_')
Xcols = [c for c in df.columns if c not in ('cut_ns', 'rec_idx', 'block', 'utc_hour', 'settle_tag', 'mid') and not c.startswith(outcome_prefix)]
ACT = ['ntr_60', 'qchg_60', 'ntr_20']
blocks = df.block.to_numpy(); ub = [b for b in np.unique(blocks) if (blocks == b).sum() >= 400]
def block_pct(col):
    a = df[col].to_numpy(float); out = np.full(len(a), np.nan)
    for b in ub:
        m = (blocks == b) & ~np.isnan(a)
        if m.sum() > 50: out[m] = (rankdata(a[m]) - 0.5) / m.sum() - 0.5
    return out
PX = np.column_stack([block_pct(c) for c in Xcols]); PY = np.column_stack([block_pct(c) for c in Ycols]); PA = np.column_stack([block_pct(c) for c in ACT])
inb = np.isin(blocks, ub); PX, PY, PA = PX[inb], PY[inb], PA[inb]; bl = blocks[inb]; N = len(bl); print('rows in usable blocks', N, 'blocks', len(ub))
def resid(P):                                   # regress on activity percentiles (with NaN -> 0 contribution), per column on valid rows
    A = np.column_stack([np.ones(N), np.nan_to_num(PA)]); out = np.full_like(P, np.nan)
    for j in range(P.shape[1]):
        m = ~np.isnan(P[:, j]); beta = np.linalg.lstsq(A[m], P[m, j], rcond=None)[0]; out[m, j] = P[m, j] - A[m] @ beta
    return out
RX, RY = resid(PX), resid(PY)
def pair_corr(P, Q):                            # all pairs, pairwise-complete on X (Y dense)
    out = np.full((P.shape[1], Q.shape[1]), np.nan); nn = np.zeros_like(out)
    for i in range(P.shape[1]):
        m = ~np.isnan(P[:, i]); x = P[m, i]; x = (x - x.mean()) / (x.std() + 1e-12)
        y = Q[m]; y = (y - np.nanmean(y, axis=0)) / (np.nanstd(y, axis=0) + 1e-12); out[i] = np.nan_to_num(x[:, None] * y).sum(0) / m.sum(); nn[i] = m.sum()
    return out, nn
C0, n0 = pair_corr(PX, PY); C1, n1 = pair_corr(RX, RY)
# block stability for the partial version
def block_signs(P, Q, C):
    same = np.zeros(C.shape); tot = np.zeros(C.shape)
    for b in ub:
        mb = bl == b
        if mb.sum() < 200: continue
        cb, nb = pair_corr(P[mb], Q[mb]); ok = ~np.isnan(cb) & (nb >= 150); same += ok & (np.sign(cb) == np.sign(C)); tot += ok
    return same, tot
sm, tt = block_signs(RX, RY, C1)
# family-wise null on the partial version: shift Y inside block
rng = np.random.default_rng(7); mx = []; 
idx_by_b = [np.where(bl == b)[0] for b in ub]
for _ in range(300):
    perm = np.arange(N)
    for ix in idx_by_b:
        k = int(rng.integers(100, max(101, len(ix) - 100))); perm[ix] = np.roll(ix, k)
    cc, _ = pair_corr(RX, RY[perm]); mx.append(np.nanmax(np.abs(cc)))
mx = np.array(mx); thr = np.quantile(mx, .95); print('family-wise null max|rho_part| 95%%: %.4f (median %.4f)' % (thr, np.median(mx)))
rows = []
for i, xc in enumerate(Xcols):
    for j, yc in enumerate(Ycols):
        if np.isnan(C1[i, j]): continue
        rows.append(dict(x=xc, y=yc, rho_block=C0[i, j], rho_part=C1[i, j], n=int(n1[i, j]), blocks=int(tt[i, j]), same_sign=int(sm[i, j]), exceeds_null95=abs(C1[i, j]) > thr))
M = pd.DataFrame(rows); M['abs'] = M.rho_part.abs(); M = M.sort_values('abs', ascending=False); M.to_csv('tables/t2_coupling_partial.csv', index=False)
print('pairs', len(M), 'exceeding family-wise null', int(M.exceeds_null95.sum()))
pd.set_option('display.width', 220)
for fam, ys in (('SIGNED MOVE', ['dm_1', 'dm_5', 'dm_20', 'dm_60']), ('QUOTE RESPONSE', ['dbid_5', 'dask_5', 'dspr_5']), ('FLOW PERSISTENCE', ['F_net_5', 'F_net_20']), ('BOOK RESPONSE', ['F_sup_b_5', 'F_sup_a_5', 'F_cx_b_5', 'F_cx_a_5']), ('MAGNITUDE', ['am_5', 'am_20'])):
    s = M[M.y.isin(ys)].head(14); print('\n==', fam); print(s[['x', 'y', 'rho_block', 'rho_part', 'blocks', 'same_sign', 'exceeds_null95']].round(3).to_string(index=False))
