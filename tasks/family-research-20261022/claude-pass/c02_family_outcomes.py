"""Midpoint outcomes at fixed horizons for all 749 first-observed families.
Reference = last completed group known by the strict pre-event cutoff.
Later = last completed group known by start_recv_ns + h.  Raw price change, ticks (0.001), signed pct.
Censoring: horizon end beyond last group receive time -> missing (kept as NaN, counted)."""
import sys, numpy as np, pandas as pd
G = np.load(sys.argv[1]); idx = pd.read_csv(sys.argv[2]); out = sys.argv[3]
recv = G['recv_ns']; mid = (G['bid_px'] + G['ask_px']) / 2e9
spr = (G['ask_px'] - G['bid_px']) / 1e9
H = [1, 5, 20, 60, 120, 300, 600]
rows = []
for _, r in idx.iterrows():
    cut = int(r['cutoff_ns']); st = int(r['start_recv_ns'])
    i0 = np.searchsorted(recv, cut, side='right') - 1   # last group known by cutoff
    row = dict(instance=int(r['instance']), family_id=r['family_id'], start_recv_ns=st,
               ref_group=int(G['ord'][i0]), ref_recv_ns=int(recv[i0]), ref_mid=mid[i0], ref_spread=spr[i0],
               ref_bid_sz=int(G['bid_sz'][i0]), ref_ask_sz=int(G['ask_sz'][i0]),
               ref_bid_n=int(G['bid_n'][i0]), ref_ask_n=int(G['ask_n'][i0]))
    for h in H:
        end = st + h * 10**9
        if end > recv[-1]:
            row[f'chg_{h}s'] = np.nan; row[f'grp_{h}s'] = -1; continue
        j = np.searchsorted(recv, end, side='right') - 1
        row[f'chg_{h}s'] = mid[j] - mid[i0]; row[f'grp_{h}s'] = int(G['ord'][j])
    rows.append(row)
df = pd.DataFrame(rows); df.to_csv(out, index=False)
print(df.shape, 'censored per horizon:', {h: int(df[f"chg_{h}s"].isna().sum()) for h in H})
for k in (375, 391):
    print(df[df.instance == k][['instance','ref_mid','ref_spread'] + [f'chg_{h}s' for h in H]].round(4).to_string(index=False))
