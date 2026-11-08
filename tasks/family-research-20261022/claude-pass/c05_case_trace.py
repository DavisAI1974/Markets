"""Windowed order-level summary around a first-observed family start (as-of cutoff semantics for pre windows)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '.')
from c04_order_features import enrich, Windows
R0 = pd.read_parquet('/home/claude/work/recon_20231018.parquet'); R, C = enrich(R0); W = Windows(R, C)
IDX = pd.read_csv('/home/claude/ng-wt/artifacts/sqlite-triage/20261022/families/instance-market-review-20261023/chronological-instance-index.csv')
S = 10**9
def trace(inst, edges):
    st = int(IDX[IDX.instance == inst].start_recv_ns.iloc[0]); rows = []
    T = lambda x: st - 1 if x == 0 else st + int(x * S)   # x = 0 is the strict pre-event cutoff (excludes the family group)
    for a, b in zip(edges[:-1], edges[1:]):
        # window (st+a, st+b]; uses records whose group closed by st+b  (post windows are outcome-side)
        hi, e = W.sums(T(b), 0)
        s_hi, e1 = W.sums(T(b), T(b) - T(a))
        s_hi['win'] = f'[{a:+},{b:+}]s'
        eb = e; bb = R.bb_a.iloc[eb] / 1000; ba = R.ba_a.iloc[eb] / 1000
        s_hi.update(bid=bb, ask=ba, bid_sz=int(R.bsz_a.iloc[eb]), bid_n=int(R.bn_a.iloc[eb]), ask_sz=int(R.asz_a.iloc[eb]), ask_n=int(R.an_a.iloc[eb]))
        rows.append(s_hi)
    return pd.DataFrame(rows).set_index('win')
if __name__ == '__main__':
    edges = [-60, -20, -5, -1, 0, 1, 5, 20, 60]
    show = ['trade_sellagg','trade_buyagg','fill_b','fill_a','rm_fill_b','rm_fill_a','rm_cx_touch_b','rm_cx_touch_a','add_touch_b','add_touch_a','add_near_b','add_near_a','bid','ask','bid_sz','bid_n','ask_sz','ask_n']
    for inst in (375, 391):
        print('INSTANCE', inst); print(trace(inst, edges)[show].T.to_string())
