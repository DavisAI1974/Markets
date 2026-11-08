"""Lead-lag between market-condition series at 1-second resolution (Oct 18 UTC member).
Series per second s (records assigned by receive second; seconds are an ordering index only, no calendar feature):
 flow   = known-wire-side buy lots - sell lots
 supB   = adds at/near the bid touch - removals (fill-linked + unlinked) near the bid touch
 supA   = same for the ask
 dmid   = change in midpoint (ticks) over the second (last completed group at the end of the second vs the previous second)
 dspr   = change in spread (ticks)
 churn  = total adds + removals near the touch, both sides
 timb   = touch size imbalance at the end of the second
Each series is percentile-ranked inside ACTIVITY QUINTILES (trade lots over the trailing 60 s) so quiet and busy stretches are comparable.
cross-correlation at lags -15..+15 s : corr(A[t], B[t+lag]); lag>0 means A leads B.  Null: cyclic shift of B by >=600 s, 300 shifts -> 99.9% band of |rho|."""
import sys; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from scipy.stats import rankdata
from c04_order_features import enrich
R0 = pd.read_parquet('/home/claude/work/recon_20231018.parquet'); R, C = enrich(R0)
G = np.load('/home/claude/work/groups.npz'); recv = G['recv_ns']; mid = (G['bid_px'] + G['ask_px']) / 2e9; spr = (G['ask_px'] - G['bid_px']) / 1e9
S = 10**9; t0 = int(R.ts.iloc[0]); sec = ((R.ts.to_numpy() - t0) // S).astype(int); T = int(sec.max()) + 1
def bc(w): return np.bincount(sec, weights=w, minlength=T)
flow = bc((C.trade_buyagg - C.trade_sellagg).to_numpy(float))
supB = bc((C.add_touch_b + C.add_near_b - C.rm_fill_b - C.rm_cx_touch_b - C.rm_cx_near_b).to_numpy(float))
supA = bc((C.add_touch_a + C.add_near_a - C.rm_fill_a - C.rm_cx_touch_a - C.rm_cx_near_a).to_numpy(float))
churn = bc((C.add_touch_b + C.add_near_b + C.add_touch_a + C.add_near_a + C.rm_fill_b + C.rm_fill_a + C.rm_cx_touch_b + C.rm_cx_touch_a + C.rm_cx_near_b + C.rm_cx_near_a).to_numpy(float))
tot = bc((C.trade_buyagg + C.trade_sellagg).to_numpy(float))
ends = t0 + (np.arange(T) + 1) * S; gi = np.clip(np.searchsorted(recv, ends, side='right') - 1, 0, len(recv) - 1)
m_end = mid[gi]; s_end = spr[gi]; dmid = np.diff(m_end, prepend=m_end[0]) / 0.001; dspr = np.diff(s_end, prepend=s_end[0]) / 0.001
bsz = G['bid_sz'][gi].astype(float); asz = G['ask_sz'][gi].astype(float); timb = (bsz - asz) / (bsz + asz)
live = np.convolve(tot, np.ones(60), 'full')[:T]           # trailing 60 s trade lots (market condition)
valid = np.arange(T) >= 600
q = pd.qcut(pd.Series(live).rank(method='first'), 5, labels=False).to_numpy()
def sp(a):
    out = np.zeros(T)
    for k in range(5):
        m = (q == k) & valid
        if m.sum() > 50: out[m] = (rankdata(a[m]) - 0.5) / m.sum() - 0.5
    return out
series = dict(flow=sp(flow), supB=sp(supB), supA=sp(supA), dmid=sp(dmid), dspr=sp(dspr), churn=sp(churn), timb=sp(timb))
names = list(series); lags = list(range(-15, 16))
def xc(a, b, lag):
    if lag >= 0: x, y = a[:T - lag], b[lag:]; v = valid[:T - lag] & valid[lag:]
    else: x, y = a[-lag:], b[:T + lag]; v = valid[-lag:] & valid[:T + lag]
    x, y = x[v], y[v]; return np.corrcoef(x, y)[0, 1]
rng = np.random.default_rng(3); null = []
for _ in range(300):
    sh = int(rng.integers(600, T - 600)); a, b = rng.choice(names, 2, replace=False); null.append(max(abs(xc(series[a], np.roll(series[b], sh), l)) for l in (-5, 0, 5)))
band = np.quantile(null, .999); print('seconds', T, 'usable', int(valid.sum()), 'null 99.9%% band |rho| ~ %.4f' % band)
rows = []
for a in names:
    for b in names:
        cc = np.array([xc(series[a], series[b], l) for l in lags]); k = int(np.argmax(np.abs(cc)))
        rows.append(dict(A=a, B=b, peak_lag_s=lags[k], peak_rho=cc[k], rho_lag0=cc[lags.index(0)], rho_lag1=cc[lags.index(1)], rho_lag_m1=cc[lags.index(-1)], rho_lag5=cc[lags.index(5)], exceeds=abs(cc[k]) > band))
L = pd.DataFrame(rows); L.to_csv('tables/t2_leadlag_matrix.csv', index=False)
pd.set_option('display.width', 200); print(L[(L.A != L.B)].sort_values('peak_rho', key=abs, ascending=False).head(30).round(3).to_string(index=False))
# --- persist the per-second series; ts_ns and rec_idx are provenance coordinates only (never used in the math)
sec_end_idx = np.searchsorted(R.ts.to_numpy(), ends, side='right') - 1
pd.DataFrame(dict(sec=np.arange(T), end_ns=ends, last_rec_idx=sec_end_idx, flow=flow, supB=supB, supA=supA, churn=churn, tot=tot, dmid=dmid, dspr=dspr, spread_ticks=s_end / 0.001,
                  bsz=bsz, asz=asz, timb=timb, live60=live, mid=m_end, valid=valid)).to_parquet('tables/t2_seconds.parquet')
a = series['dmid']; print('autocorr of activity-normalised dmid at lag1: %.3f' % xc(a, a, 1))
