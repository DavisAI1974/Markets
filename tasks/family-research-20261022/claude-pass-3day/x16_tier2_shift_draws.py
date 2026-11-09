"""x16: the c14 condition/outcome coupling scan with its shifted-Y draws SAVED, so x14 can show what four-day sign agreement looks like when Y is
unrelated to X (the same reference c19/c20 gave the regime comparison).  Usage: OD_WORK=<derived dir> python3 -I x16_tier2_shift_draws.py <date>
Identical transform to c14 (closed rows out, activity-quintile percentile ranks, 24 chunks, Y cyclically shifted by >= 1200 rows, seed 11, 300 shifts):
the observed matrix is written beside the first NSAVE shifted matrices to <WORK>/t2_nullrho_<date>.npz and the observed matrix is checked against the
committed tables/<date>/t2_coupling_conditions.csv (max absolute difference printed).  Nothing in tables/ is written.  No trade cost anywhere."""
import sys; sys.path.insert(0, '.')
from odcfg import *
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import rankdata
DATE = date_arg(); NSAVE = 20
df = pd.read_parquet(big(DATE, 'grid')).sort_values('cut_ns').reset_index(drop=True); df = df[~df.closed].reset_index(drop=True)
OUT = ('dm_', 'am_', 'dbid_', 'dask_', 'dspr_', 'F_'); NOT_CONDITIONS = {'cut_ns', 'rec_idx', 'block', 'utc_hour', 'settle_tag', 'mid', 'closed'}
Xcols = [c for c in df.columns if c not in NOT_CONDITIONS and not c.startswith(OUT)]
Ycols = ['dm_1', 'dm_5', 'dm_20', 'dm_60', 'am_5', 'am_20', 'dbid_5', 'dask_5', 'dspr_5', 'F_net_5', 'F_net_20', 'F_sup_b_5', 'F_sup_a_5', 'F_cx_b_5', 'F_cx_a_5', 'F_add_b_5', 'F_add_a_5']
N = len(df); act = df.ntr_60.rank(pct=True) + df.qchg_60.rank(pct=True) + df.ntr_20.rank(pct=True); q = pd.qcut(act.rank(method='first'), 5, labels=False).to_numpy()
def strat_pct(col):
    a = df[col].to_numpy(float); out = np.full(N, np.nan)
    for k in range(5):
        m = (q == k) & ~np.isnan(a)
        if m.sum() > 50: out[m] = (rankdata(a[m]) - 0.5) / m.sum() - 0.5
    return out
PX = np.column_stack([strat_pct(c) for c in Xcols]); PY = np.column_stack([strat_pct(c) for c in Ycols])
valid = ~np.isnan(PX); ZX = np.where(valid, PX, 0.0); sdx = np.sqrt((ZX ** 2).sum(0) / np.maximum(valid.sum(0), 1)) + 1e-12; ZX = ZX / sdx
sdy = np.nanstd(PY, axis=0) + 1e-12; ZY = np.nan_to_num(PY) / sdy; nv = np.maximum(valid.sum(0), 1)
C = (ZX.T @ ZY) / nv[:, None]
rng = np.random.default_rng(11); mx = []; saved = []
for s in range(300):
    sh = int(rng.integers(1200, N - 1200)); Cn = (ZX.T @ np.roll(ZY, sh, axis=0)) / nv[:, None]; mx.append(np.abs(Cn).max())
    if s < NSAVE: saved.append(Cn)
thr = np.quantile(mx, .95)
T = pd.read_csv(tab(DATE, 't2_coupling_conditions.csv')).set_index(['x', 'y'])
obs = np.array([[T.rho.get((x, y), np.nan) for y in Ycols] for x in Xcols])
print(DATE, 'rows', N, 'features', len(Xcols), 'outcomes', len(Ycols), 'line %.4f' % thr, '| max |rebuilt - committed rho| = %.3g' % np.nanmax(np.abs(C - obs)), '| committed pairs', len(T))
np.savez_compressed(f'{WORK}/t2_nullrho_{DATE}.npz', x=np.array(Xcols), y=np.array(Ycols), observed=C, null=np.array(saved), line=thr, rows=N)
