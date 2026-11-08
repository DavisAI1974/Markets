"""c22: one-second state cells (c17) and lead-lag (c16) split by spread regime, then compared across the four days.
Usage: python3 -I c22_state_leadlag_regime.py
Per second (from seconds_<date>.parquet, closed-market seconds already invalid): regime = spread in ticks at the end of the second ('1', '2', '3+').
STATE CELLS: [last-second midpoint move: up/down/flat] x [touch size imbalance tercile] x [last-second net aggressor flow: buy/sell/none] -> next 1 s and next 5 s midpoint change.
  Activity quintiles (trailing 60 s trade lots) and imbalance terciles are computed INSIDE the regime.  net share = (up - down) / (up + down + flat).
  Cells need >= 100 seconds.  Reference: outcome vector cyclically shifted inside the regime's second sequence by >= max(100, n//10) rows, 300 shifts -> z.
  Stability: 12 contiguous chronological chunks of the regime's seconds (order only), same-sign count (chunk needs >= 10 seconds in the cell).
  Denominators: usable seconds per regime = seconds in cells at/above the floor + seconds in cells below it (printed in the receipt).
LEAD-LAG: series percentile-ranked inside activity quintiles within the regime; corr(A[t], B[t+lag]) over pairs of seconds that are BOTH valid and BOTH in the regime;
  lag > 0 means A leads B.  Seconds are an ordering index only.  Reference band: B shifted >= 600 s, 300 draws at lags -5, 0, +5, 99.9%.
No calendar feature, no id, no trade cost."""
import sys; sys.path.insert(0, '.')   # cwd is this code directory, not a data directory
from odcfg import *
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import rankdata
REGS = ['1', '2', '3+']; K = 12; MIN_SUP = 100; MIN_CH = 10
PAIRS = [('flow', 'dmid'), ('supB', 'dmid'), ('supA', 'dmid'), ('timb', 'dmid'), ('supB', 'supA'), ('churn', 'timb'), ('flow', 'supB'), ('flow', 'supA'), ('dmid', 'timb')]
LAGS = list(range(-5, 6))
def reg_of(spt):
    r = np.rint(spt); return np.where(r <= 0, '', np.where(r == 1, '1', np.where(r == 2, '2', '3+')))
def cell_stats(y, mask):
    v = y[mask]; up = int((v > 0).sum()); dn = int((v < 0).sum()); fl = int((v == 0).sum()); tot = len(v)
    return up, dn, fl, tot, ((up - dn) / tot if tot else np.nan)
cells_all = []; ll_all = []; rec = []
for d in DATES:
    s = pd.read_parquet(big(d, 'seconds')); T = len(s); rg = reg_of(s.spread_ticks.to_numpy())
    mid = s.mid.to_numpy(); y1 = (np.roll(mid, -1) - mid) / 0.001; y5 = (np.roll(mid, -5) - mid) / 0.001
    for r in REGS:
        ok = (s.valid.to_numpy() & (rg == r) & (np.arange(T) < T - 6) & (s.live60.to_numpy() > 0))
        D = s[ok].copy(); n = len(D); D['y1'] = y1[ok]; D['y5'] = y5[ok]
        D['aq'] = pd.qcut(D.live60.rank(method='first'), 5, labels=False)
        D['tt'] = np.nan
        for k in range(5):
            m = D.aq == k
            if m.sum() >= 3: D.loc[m, 'tt'] = pd.qcut(D.loc[m, 'timb'].rank(method='first'), 3, labels=False)
        D = D[D.tt.notna()].reset_index(drop=True); n = len(D)
        lean = D.tt.map({0: 'ask-heavy', 1: 'mid', 2: 'bid-heavy'}); move = np.where(D.dmid > 0, 'up', np.where(D.dmid < 0, 'down', 'flat')); flow = np.where(D.flow > 0, 'buy', np.where(D.flow < 0, 'sell', 'none'))
        keys = pd.Series(move) + '|' + lean + '|' + pd.Series(flow); chunk = np.minimum((np.arange(n) * K) // n, K - 1)
        rng = np.random.default_rng(2); lo = max(100, n // 10); shifts = [int(rng.integers(lo, n - lo)) for _ in range(300)]
        in_floor = 0
        for key in sorted(keys.unique()):
            m = (keys == key).to_numpy()
            if m.sum() < MIN_SUP: continue
            in_floor += int(m.sum())
            for h, y in (('next1s', D.y1.to_numpy()), ('next5s', D.y5.to_numpy())):
                up, dn, fl, tot, net = cell_stats(y, m); nulls = np.array([cell_stats(np.roll(y, sh), m)[4] for sh in shifts]); z = (net - nulls.mean()) / (nulls.std() + 1e-9)
                sg = [np.sign(a - b) for k in range(K) for (a, b, f, t, nt) in [cell_stats(y, m & (chunk == k))] if (m & (chunk == k)).sum() >= MIN_CH]
                cells_all.append(dict(date=d, regime=r, cell=key, horizon=h, support=int(m.sum()), up=up, flat=fl, down=dn, net_share=net, null_mean=nulls.mean(), z=z, chunks=len(sg), same_sign_chunks=int((np.array(sg) == np.sign(up - dn)).sum()) if sg else 0, median_ticks=float(np.median(y[m]))))
        rec.append(dict(date=d, regime=r, valid_seconds_in_regime=int((s.valid.to_numpy() & (rg == r)).sum()), usable_seconds=n, in_cells_at_or_above_floor=in_floor, in_cells_below_floor=n - in_floor, cells_floor=MIN_SUP))
        # ---- lead-lag inside the regime
        act = pd.qcut(s.live60.rank(method='first'), 5, labels=False).to_numpy(); inreg = s.valid.to_numpy() & (rg == r)
        def sp(a):
            out = np.full(T, np.nan)
            for k in range(5):
                mk = (act == k) & inreg & ~np.isnan(a)
                if mk.sum() > 50: out[mk] = (rankdata(a[mk]) - 0.5) / mk.sum() - 0.5
            return out
        ser = {c: sp(s[c].to_numpy(float)) for c in ('flow', 'supB', 'supA', 'timb', 'dmid', 'churn')}
        def xc(a, b, lag):
            if lag >= 0: x, y = a[:T - lag], b[lag:]
            else: x, y = a[-lag:], b[:T + lag]
            v = ~np.isnan(x) & ~np.isnan(y)
            return (np.corrcoef(x[v], y[v])[0, 1], int(v.sum())) if v.sum() > 100 else (np.nan, int(v.sum()))
        rng2 = np.random.default_rng(3); names = list(ser); null = []
        for _ in range(300):
            sh = int(rng2.integers(600, T - 600)); a, b = rng2.choice(names, 2, replace=False); vals = [xc(ser[a], np.roll(ser[b], sh), l)[0] for l in (-5, 0, 5)]; null.append(np.nanmax(np.abs(vals)))
        band = float(np.nanquantile(null, .999))
        for A_, B_ in PAIRS:
            for l in LAGS:
                rho, nn = xc(ser[A_], ser[B_], l); ll_all.append(dict(date=d, regime=r, A=A_, B=B_, lag=l, rho=rho, pairs_of_seconds=nn, null999_band=band))
    print(d, 'done')
C = pd.DataFrame(cells_all); L = pd.DataFrame(ll_all); RC = pd.DataFrame(rec)
assert (RC.usable_seconds == RC.in_cells_at_or_above_floor + RC.in_cells_below_floor).all()
for d in DATES:
    C[C.date == d].to_csv(tab(d, 't3_state_cells_regime.csv'), index=False); L[L.date == d].to_csv(tab(d, 't3_leadlag_regime.csv'), index=False); RC[RC.date == d].to_csv(tab(d, 't3_state_receipt.csv'), index=False)
# ---- cross-day tables
P = C.pivot_table(index=['regime', 'horizon', 'cell'], columns='date', values='net_share'); Sx = C.pivot_table(index=['regime', 'horizon', 'cell'], columns='date', values='support'); Z = C.pivot_table(index=['regime', 'horizon', 'cell'], columns='date', values='z')
ok = P.dropna().index; X = pd.DataFrame(index=ok)
for d in DATES: X[f'net_{d[4:]}'] = P.loc[ok, d]; X[f'support_{d[4:]}'] = Sx.loc[ok, d].astype(int); X[f'z_{d[4:]}'] = Z.loc[ok, d]
nets = X[[f'net_{d[4:]}' for d in DATES]].to_numpy(); X['days_same_sign'] = np.maximum((nets > 0).sum(1), (nets < 0).sum(1)); X['min_abs_net'] = np.abs(nets).min(1)
X = X.reset_index().sort_values(['regime', 'horizon', 'days_same_sign', 'min_abs_net'], ascending=[True, True, False, False]); X.to_csv(tab('crossday', 't4_state_crossday.csv'), index=False)
Lp = L.pivot_table(index=['regime', 'A', 'B', 'lag'], columns='date', values='rho'); Lp.columns = [f'rho_{c[4:]}' for c in Lp.columns]
Lp['days_same_sign'] = np.maximum((Lp.to_numpy() > 0).sum(1), (Lp.to_numpy() < 0).sum(1)); Lp = Lp.reset_index(); Lp.to_csv(tab('crossday', 't4_leadlag_crossday.csv'), index=False)
RC.to_csv(tab('crossday', 't3_state_receipts_all.csv'), index=False)
pd.set_option('display.width', 220); print(RC.to_string(index=False)); print('state cells in cross-day table:', len(X), '| lead-lag rows:', len(Lp))
