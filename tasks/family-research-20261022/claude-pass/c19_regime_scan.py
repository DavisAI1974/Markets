"""c19: conditions-only coupling scan split by spread regime (supersedes the inline split in log section D).
Usage: python3 -I c19_regime_scan.py <date> [nosettle]
Regimes by the spread at the decision cutoff, in ticks (0.001): '1', '2', '3+'.  Nothing is pooled across regimes.  Locked/crossed rows (spread <= 0) and
closed-market rows (c12 flag) are counted and left out.  'nosettle' also leaves out rows tagged by c12 as inside the settlement window (sensitivity run).
Same conditions-only rules as c14:
  X = as-of market conditions (flow, book behaviour by side, touch state, near depth, prior displacement, quote changes, snapshot age and time since the touch moved).
  Not in X or Y: ids, cursors, record indices, timestamps, UTC hour, weekday, any clock label (asserted below).
  Columns are percentile-ranked inside ACTIVITY QUINTILES computed inside the regime (trailing trade count and quote changes, as of the cutoff).
  A condition with fewer than 100 usable rows in the regime has no defined correlation: its pairs are left out and counted (pairs_undefined), never reported as 0.
  Columns constant inside the regime (for example the spread itself in the 1-tick and 2-tick regimes) are dropped for that regime and listed in the receipt.
  Stability: K=12 contiguous chronological chunks of the regime's rows (order only), count of chunks with the same sign (chunks need >= 40 usable rows).
  Reference line: Y cyclically shifted inside the regime's row sequence by >= max(100, N//10) rows, 300 shifts, max |rho| over all pairs -> 95% line (family-wise).
  The first 20 shifted rho matrices are saved so c20 can show what cross-day agreement looks like when Y is unrelated to X.
Overlapping neighbours: naive p-values are not used.  No trade cost anywhere."""
import sys; sys.path.insert(0, '.')   # cwd is this code directory, not a data directory
from odcfg import *
import json
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import rankdata
DATE = date_arg(); NOSETTLE = 'nosettle' in sys.argv[2:]; SUF = '_nosettle' if NOSETTLE else ''
K = 12; MIN_CHUNK = 40; MIN_VALID = 100; NSHIFT = 300; NSAVE = 20
OUT = ('dm_', 'am_', 'dbid_', 'dask_', 'dspr_', 'F_')
NOT_CONDITIONS = {'cut_ns', 'rec_idx', 'block', 'utc_hour', 'settle_tag', 'mid', 'closed'}
Ycols = ['dm_1', 'dm_5', 'dm_20', 'dm_60', 'am_5', 'am_20', 'dbid_5', 'dask_5', 'dspr_5', 'F_net_5', 'F_net_20', 'F_sup_b_5', 'F_sup_a_5', 'F_cx_b_5', 'F_cx_a_5', 'F_add_b_5', 'F_add_a_5']
raw = pd.read_parquet(big(DATE, 'grid')).sort_values('cut_ns').reset_index(drop=True)
Xall = [c for c in raw.columns if c not in NOT_CONDITIONS and not c.startswith(OUT)]
assert not any(k in c for c in Xall for k in ('cut_ns', 'rec_idx', 'hour', 'block', 'order_id', 'cursor')), 'identity or clock column in X'
n_closed = int(raw.closed.sum()); n_settle = int((raw.settle_tag & ~raw.closed).sum()) if NOSETTLE else 0
df = raw[~raw.closed]
if NOSETTLE: df = df[~df.settle_tag]
n_lockcross = int((df.spr <= 0).sum()); df = df[df.spr > 0].reset_index(drop=True)
REG = {'1': df.spr == 1, '2': df.spr == 2, '3+': df.spr >= 3}
rows_out = []; recv = []; qs_all = {}
for reg, m in REG.items():
    s = df[m.to_numpy()].reset_index(drop=True); N = len(s)
    act = s.ntr_60.rank(pct=True) + s.qchg_60.rank(pct=True) + s.ntr_20.rank(pct=True)
    q = pd.qcut(act.rank(method='first'), 5, labels=False).to_numpy()
    Xc = [c for c in Xall if np.nanstd(s[c].to_numpy(float)) > 0]; dropped = [c for c in Xall if c not in Xc]
    Yc = [c for c in Ycols if np.nanstd(s[c].to_numpy(float)) > 0]
    def strat_pct(col):
        a = s[col].to_numpy(float); out = np.full(N, np.nan)
        for k in range(5):
            mk = (q == k) & ~np.isnan(a)
            if mk.sum() > 50: out[mk] = (rankdata(a[mk]) - 0.5) / mk.sum() - 0.5
        return out
    PX = np.column_stack([strat_pct(c) for c in Xc]); PY = np.column_stack([strat_pct(c) for c in Yc])
    chunk = np.minimum((np.arange(N) * K) // N, K - 1)
    valid = ~np.isnan(PX); ZX = np.where(valid, PX, 0.0); sdx = np.sqrt((ZX ** 2).sum(0) / np.maximum(valid.sum(0), 1)) + 1e-12; ZX = ZX / sdx
    sdy = np.nanstd(PY, axis=0) + 1e-12; ZY = np.nan_to_num(PY) / sdy; nv = np.maximum(valid.sum(0), 1)
    C = (ZX.T @ ZY) / nv[:, None]
    nvalid = valid.sum(0); undef = nvalid < MIN_VALID; C[undef, :] = np.nan      # a condition with < MIN_VALID usable rows has no defined correlation (not a measured zero)
    same = np.zeros(C.shape); tot = np.zeros(C.shape)
    for k in range(K):
        mk = chunk == k; nvk = np.maximum(valid[mk].sum(0), 1); Ck = (ZX[mk].T @ ZY[mk]) / nvk[:, None]; ok = valid[mk].sum(0) >= MIN_CHUNK
        same += (np.sign(Ck) == np.sign(C)) & ok[:, None] & ~np.isnan(C); tot += ok[:, None] & ~np.isnan(C)
    rng = np.random.default_rng(11); mx = []; saved = []; lo = max(100, N // 10)
    for i in range(NSHIFT):
        sh = int(rng.integers(lo, N - lo)); Cn = (ZX.T @ np.roll(ZY, sh, axis=0)) / nv[:, None]; Cn[undef, :] = np.nan; mx.append(np.nanmax(np.abs(Cn)))
        if i < NSAVE: saved.append(Cn)
    thr = float(np.quantile(mx, .95))
    for i, xc in enumerate(Xc):
        if undef[i]: continue
        for j, yc in enumerate(Yc):
            rows_out.append(dict(date=DATE, regime=reg, x=xc, y=yc, rho=C[i, j], n=int(nv[i]), chunks=int(tot[i, j]), same_sign_chunks=int(same[i, j]), null95_line=thr, beyond_null95=abs(C[i, j]) > thr))
    np.savez_compressed(f'{WORK}/nullrho_{DATE}_{reg.replace("+", "p")}{SUF}.npz', null=np.array(saved), x=np.array(Xc), y=np.array(Yc), rho=C)
    recv.append(dict(date=DATE, regime=reg, rows=N, features_used=len(Xc), outcomes_used=len(Yc), pairs=len(Xc) * len(Yc), pairs_undefined=int(undef.sum()) * len(Yc), pairs_defined=int((~undef).sum()) * len(Yc), undefined_conditions=';'.join(np.array(Xc)[undef]), dropped_constant=';'.join(dropped), null95_line=thr, min_shift_rows=lo, chunks=K))
    print(DATE, 'regime', reg, 'rows', N, 'pairs', len(Xc) * len(Yc), 'null95 %.4f' % thr, 'defined pairs', int((~undef).sum()) * len(Yc), 'beyond', int(np.nansum(abs(C.ravel()) > thr)), 'dropped constant:', dropped)
M = pd.DataFrame(rows_out); M['abs'] = M.rho.abs(); M = M.sort_values(['regime', 'abs'], ascending=[True, False]).drop(columns='abs')
M.to_csv(tab(DATE, f't3_regime_coupling{SUF}.csv'), index=False)
rc = pd.DataFrame(recv); rc['grid_rows'] = len(raw); rc['closed_market_rows_left_out'] = n_closed; rc['settle_rows_left_out'] = n_settle; rc['locked_crossed_left_out'] = n_lockcross
rc['rows_all_regimes'] = int(rc.rows.sum()); rc.to_csv(tab(DATE, f't3_regime_receipt{SUF}.csv'), index=False)
assert rc.rows.sum() + n_closed + n_settle + n_lockcross == len(raw), 'row reconciliation failed'
print(DATE, 'rows reconcile: grid', len(raw), '= regimes', int(rc.rows.sum()), '+ closed', n_closed, '+ settle', n_settle, '+ locked/crossed', n_lockcross)
