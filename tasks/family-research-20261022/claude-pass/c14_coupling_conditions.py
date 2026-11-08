"""Market-condition couplings only.
X = as-of market conditions: flow (known-side lots, imbalance, trade count), book behaviour by side (adds/removals/fills/cancels/modifies, support, refill, cancel share),
touch state (spread, sizes, order counts, size per order, imbalances), near depth, prior displacement, quote-change counts.
NOT in X or Y: order/trade IDs, cursors, record indices, timestamps, UTC hour, weekday, any clock label.
Normalisation by a market condition: rows are put in ACTIVITY QUINTILES (composite of trade count and quote changes over 60 s, as of the cutoff) and every column is percentile-ranked inside its quintile.
Time is used only for ordering: 24 contiguous chronological chunks (equal row counts) test whether a sign repeats; the shift-null moves Y cyclically by >=1200 rows against X.
Neighbouring decisions overlap, so naive p-values are not used."""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import rankdata
df = pd.read_parquet('tables/t2_grid.parquet').sort_values('cut_ns').reset_index(drop=True)
OUT = ('dm_', 'am_', 'dbid_', 'dask_', 'dspr_', 'F_')
NOT_CONDITIONS = {'cut_ns', 'rec_idx', 'block', 'utc_hour', 'settle_tag', 'mid'}
Xcols = [c for c in df.columns if c not in NOT_CONDITIONS and not c.startswith(OUT)]
Ycols = ['dm_1', 'dm_5', 'dm_20', 'dm_60', 'am_5', 'am_20', 'dbid_5', 'dask_5', 'dspr_5', 'F_net_5', 'F_net_20', 'F_sup_b_5', 'F_sup_a_5', 'F_cx_b_5', 'F_cx_a_5', 'F_add_b_5', 'F_add_a_5']
assert not any(k in c for c in Xcols for k in ('cut_ns', 'rec_idx', 'hour', 'block', 'order_id', 'cursor')), 'identity or clock column in X'
N = len(df)
act = df.ntr_60.rank(pct=True) + df.qchg_60.rank(pct=True) + df.ntr_20.rank(pct=True)
q = pd.qcut(act.rank(method='first'), 5, labels=False).to_numpy()
def strat_pct(col):
    a = df[col].to_numpy(float); out = np.full(N, np.nan)
    for k in range(5):
        m = (q == k) & ~np.isnan(a)
        if m.sum() > 50: out[m] = (rankdata(a[m]) - 0.5) / m.sum() - 0.5
    return out
PX = np.column_stack([strat_pct(c) for c in Xcols]); PY = np.column_stack([strat_pct(c) for c in Ycols])
chunk = np.minimum((np.arange(N) * 24) // N, 23)
valid = ~np.isnan(PX); ZX = np.where(valid, PX, 0.0); sdx = np.sqrt((ZX ** 2).sum(0) / np.maximum(valid.sum(0), 1)) + 1e-12; ZX = ZX / sdx
sdy = np.nanstd(PY, axis=0) + 1e-12; ZY = np.nan_to_num(PY) / sdy
nv = np.maximum(valid.sum(0), 1)
C = (ZX.T @ ZY) / nv[:, None]                                    # rho of within-quintile percentile ranks
same = np.zeros(C.shape); tot = np.zeros(C.shape)
for k in range(24):
    m = chunk == k; nvk = np.maximum(valid[m].sum(0), 1); Ck = (ZX[m].T @ ZY[m]) / nvk[:, None]; ok = valid[m].sum(0) >= 150
    same += (np.sign(Ck) == np.sign(C)) & ok[:, None]; tot += ok[:, None]
rng = np.random.default_rng(11); mx = []
for _ in range(300):
    sh = int(rng.integers(1200, N - 1200)); Cn = (ZX.T @ np.roll(ZY, sh, axis=0)) / nv[:, None]; mx.append(np.abs(Cn).max())
thr = np.quantile(mx, .95); print('rows', N, 'features', len(Xcols), 'outcomes', len(Ycols), '| family-wise null max|rho| 95%%: %.4f' % thr)
rows = [dict(x=Xcols[i], y=Ycols[j], rho=C[i, j], n=int(nv[i]), chunks=int(tot[i, j]), same_sign_chunks=int(same[i, j]), exceeds_null95=abs(C[i, j]) > thr) for i in range(len(Xcols)) for j in range(len(Ycols))]
M = pd.DataFrame(rows); M['abs'] = M.rho.abs(); M = M.sort_values('abs', ascending=False); M.to_csv('tables/t2_coupling_conditions.csv', index=False)
print('pairs', len(M), 'exceeding null', int(M.exceeds_null95.sum()))
pd.set_option('display.width', 200)
for fam, ys in (('SIGNED MOVE', ['dm_1', 'dm_5', 'dm_20', 'dm_60']), ('QUOTE RESPONSE', ['dbid_5', 'dask_5', 'dspr_5']), ('FLOW PERSISTENCE', ['F_net_5', 'F_net_20']), ('BOOK RESPONSE', ['F_sup_b_5', 'F_sup_a_5', 'F_cx_b_5', 'F_cx_a_5', 'F_add_b_5', 'F_add_a_5']), ('MAGNITUDE', ['am_5', 'am_20'])):
    s = M[M.y.isin(ys)].head(12); print('\n==', fam); print(s[['x', 'y', 'rho', 'chunks', 'same_sign_chunks', 'exceeds_null95']].round(3).to_string(index=False))
