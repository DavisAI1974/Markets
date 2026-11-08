"""All-pairs rank-correlation scan: as-of features (X) against outcomes (Y) on the Tier 2 grid.
Rank correlation = Pearson on global ranks over rows where X is defined (Y is dense).  Stability = same-sign share across UTC-hour blocks with >=200 usable rows.
Null = cyclic shift of Y by >=1200 rows (1 hour), 200 shifts, max |rho| over ALL pairs per shift (family-wise) -> null_max95.
Neighbouring decisions overlap in time (3 s grid, outcome windows up to 60 s), so the p-values of a naive test are far too optimistic; the shift null and block signs are the evidence used."""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import rankdata
df = pd.read_parquet('tables/t2_grid.parquet')
Ycols = ['dm_1', 'dm_5', 'dm_20', 'dm_60', 'am_1', 'am_5', 'am_20', 'am_60', 'dbid_5', 'dask_5', 'dspr_5', 'F_net_5', 'F_ntr_5', 'F_sup_b_5', 'F_sup_a_5', 'F_cx_b_5', 'F_cx_a_5', 'F_add_b_5', 'F_add_a_5', 'F_net_20', 'F_ntr_20']
drop = set(['cut_ns', 'rec_idx', 'block', 'utc_hour', 'settle_tag', 'mid']) | set(Ycols) | {c for c in df.columns if c.startswith(('dm_', 'am_', 'dbid_', 'dask_', 'dspr_', 'F_'))}
Xcols = [c for c in df.columns if c not in drop]
print('features', len(Xcols), 'outcomes', len(Ycols), 'pairs', len(Xcols) * len(Ycols))
def grank(a):
    out = np.full(len(a), np.nan); m = ~np.isnan(a); out[m] = rankdata(a[m]); return out
RX = np.column_stack([grank(df[c].to_numpy(float)) for c in Xcols]); RY = np.column_stack([grank(df[c].to_numpy(float)) for c in Ycols])
blocks = df.block.to_numpy()
def corr_cols(rx, ry):
    m = ~np.isnan(rx) & ~np.isnan(ry)
    if m.sum() < 200 or np.nanstd(rx[m]) == 0 or np.nanstd(ry[m]) == 0: return np.nan, int(m.sum())
    return np.corrcoef(rx[m], ry[m])[0, 1], int(m.sum())
rows = []
for i, xc in enumerate(Xcols):
    for j, yc in enumerate(Ycols):
        r, n = corr_cols(RX[:, i], RY[:, j])
        if np.isnan(r): continue
        br = []
        for b in np.unique(blocks):
            mb = blocks == b; rb, nb = corr_cols(RX[mb, i], RY[mb, j])
            if nb >= 200 and not np.isnan(rb): br.append(rb)
        br = np.array(br); same = int((np.sign(br) == np.sign(r)).sum()) if len(br) else 0
        rows.append(dict(x=xc, y=yc, rho=r, n=n, blocks=len(br), same_sign_blocks=same, med_block_rho=np.median(br) if len(br) else np.nan))
M = pd.DataFrame(rows)
# null: approximate rho by standardized ranks with NaN->0 for X
ZX = (RX - np.nanmean(RX, axis=0)) / np.nanstd(RX, axis=0); valid = ~np.isnan(ZX); ZX = np.where(valid, ZX, 0.0); nv = valid.sum(axis=0)
ZY = (RY - np.nanmean(RY, axis=0)) / np.nanstd(RY, axis=0)
rng = np.random.default_rng(1); N = len(df); mx = []; allnull = []
for _ in range(200):
    sh = int(rng.integers(1200, N - 1200)); Yr = np.roll(ZY, sh, axis=0); A = (ZX.T @ Yr) / nv[:, None]; mx.append(np.abs(A).max()); allnull.append(np.abs(A).ravel())
mx = np.array(mx); allnull = np.concatenate(allnull)
M['null_max95'] = np.quantile(mx, .95); M['null_pair99'] = np.quantile(allnull, .99)
M['exceeds_familywise'] = M.rho.abs() > M.null_max95
M['abs_rho'] = M.rho.abs(); M = M.sort_values('abs_rho', ascending=False)
M.to_csv('tables/t2_coupling_scan.csv', index=False)
print('family-wise null max|rho| 95%%: %.4f ; 99%% of all null pairs: %.4f' % (np.quantile(mx, .95), np.quantile(allnull, .99)))
print('pairs exceeding family-wise null:', int(M.exceeds_familywise.sum()), 'of', len(M))
pd.set_option('display.width', 220)
print(M.head(45)[['x', 'y', 'rho', 'n', 'blocks', 'same_sign_blocks', 'med_block_rho']].round(3).to_string(index=False))
