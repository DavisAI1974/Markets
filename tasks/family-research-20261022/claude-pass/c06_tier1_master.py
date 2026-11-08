"""Tier 1: the 749 first-observed families on one table.
Features are as of the strict pre-event cutoff.  Outcome = signed midpoint change (price units and ticks of 0.001)
from the last group known at the cutoff to the last group known at start+h (see c02).  Missing stays missing.
Order-level windows (adds, fills, cancels) come from the reconstructed MBO member and exist only for families
starting inside the Oct 18 UTC member (start >= 2023-10-18 00:00 UTC); earlier ones are explicit NaN."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, '.')
from c04_order_features import enrich, Windows
ROOT = '/home/claude/ng-wt/artifacts/sqlite-triage/20261022/families/instance-market-review-20261023/'
A = pd.read_csv(ROOT + 'candidate-flow-transition-audit.csv')
O = pd.read_csv('/home/claude/work/family_outcomes.csv')
G = np.load('/home/claude/work/groups.npz')
R0 = pd.read_parquet('/home/claude/work/recon_20231018.parquet'); R, C = enrich(R0); W = Windows(R, C)
MEMBER_START = int(R.ts.iloc[0])
S = 10**9; TICK = 0.001
recv = G['recv_ns']; mid = (G['bid_px'] + G['ask_px']) / 2e9
bidp = G['bid_px'] / 1e9; askp = G['ask_px'] / 1e9
df = A.merge(O.drop(columns=['family_id', 'start_recv_ns']), on='instance')
df['chg_ticks'] = None
for h in (1, 5, 20, 60, 120, 300, 600):
    df[f'tk_{h}s'] = df[f'chg_{h}s'] / TICK
# prior displacement and quote activity from groups, as of cutoff
def prior(row, w):
    cut = int(row['cutoff_ns']); i0 = np.searchsorted(recv, cut, side='right') - 1
    j = np.searchsorted(recv, cut - w * S, side='right') - 1
    if j < 0: return np.nan, np.nan, np.nan
    seg = slice(j, i0 + 1)
    qchg = int(((np.diff(bidp[seg]) != 0) | (np.diff(askp[seg]) != 0)).sum())
    return (mid[i0] - mid[j]) / TICK, qchg, len(range(j, i0 + 1)) - 1
for w in (5, 20, 60):
    v = df.apply(lambda r: prior(r, w), axis=1, result_type='expand')
    df[f'prior_tk_{w}s'] = v[0]; df[f'quote_changes_{w}s'] = v[1]; df[f'groups_{w}s'] = v[2]
# touch-size features at the reference group (as of cutoff)
df['touch_imb'] = (df.ref_bid_sz - df.ref_ask_sz) / (df.ref_bid_sz + df.ref_ask_sz)
df['touch_n_imb'] = (df.ref_bid_n - df.ref_ask_n) / (df.ref_bid_n + df.ref_ask_n)
df['spread_ticks'] = np.round(df.ref_spread / TICK).astype(int)
# order-level windows (as-of cutoff = start - 1 ns), only inside the Oct 18 UTC member
cols = ['trade_sellagg','trade_buyagg','fill_b','fill_a','rm_fill_b','rm_fill_a','rm_cx_touch_b','rm_cx_touch_a','rm_cx_near_b','rm_cx_near_a',
        'add_touch_b','add_touch_a','add_near_b','add_near_a','mod_touch_b','mod_touch_a','n_add_touch_b','n_add_touch_a']
for w in (1, 5, 20, 60):
    vals = []
    for _, r in df.iterrows():
        st = int(r['start_recv_ns'])
        if st - w * S < MEMBER_START: vals.append([np.nan] * len(cols)); continue
        s, _e = W.sums(st - 1, w * S); vals.append([s[c] for c in cols])
    X = pd.DataFrame(vals, columns=[f'ob_{c}_{w}s' for c in cols], index=df.index)
    df = pd.concat([df, X], axis=1)
df['in_member'] = df.start_recv_ns >= MEMBER_START + 60 * S
# derived: net displayed support per side (adds minus removals), as-of
for w in (1, 5, 20, 60):
    df[f'ob_net_bid_{w}s'] = df[f'ob_add_touch_b_{w}s'] + df[f'ob_add_near_b_{w}s'] - df[f'ob_rm_fill_b_{w}s'] - df[f'ob_rm_cx_touch_b_{w}s'] - df[f'ob_rm_cx_near_b_{w}s']
    df[f'ob_net_ask_{w}s'] = df[f'ob_add_touch_a_{w}s'] + df[f'ob_add_near_a_{w}s'] - df[f'ob_rm_fill_a_{w}s'] - df[f'ob_rm_cx_touch_a_{w}s'] - df[f'ob_rm_cx_near_a_{w}s']
# NYMEX settle-window tag (18:30 UTC +-5 min) as context, not an exclusion
t = pd.to_datetime(df.start_recv_ns, unit='ns', utc=True)
df['utc_hour'] = t.dt.hour + t.dt.minute / 60
df['settle_tag'] = ((df.utc_hour >= 18 + 25/60) & (df.utc_hour <= 18 + 35/60))
df.to_csv('tables/t1_family_master.csv', index=False)
print(df.shape, 'in_member', int(df.in_member.sum()), 'settle_tag', int(df.settle_tag.sum()))
# order-level reconciliation to retained root.activity operands (60 s, buy/sell aggressor lots)
m = df[df.in_member]
okb = (m['ob_trade_buyagg_60s'] == m['root.activity.60.trade_buy_aggressor_qty']); oks = (m['ob_trade_sellagg_60s'] == m['root.activity.60.trade_sell_aggressor_qty'])
print('aggressor lots 60s equal to retained operands: buy', int(okb.sum()), 'sell', int(oks.sum()), 'of', len(m))
bad = m[~(okb & oks)][['instance','ob_trade_buyagg_60s','root.activity.60.trade_buy_aggressor_qty','ob_trade_sellagg_60s','root.activity.60.trade_sell_aggressor_qty']].head(8)
print(bad.to_string(index=False))
json.dump(dict(rows=len(df), in_member=int(df.in_member.sum()), reconcile_buy=int(okb.sum()), reconcile_sell=int(oks.sum()), of=len(m)), open('tables/t1_family_master_receipt.json', 'w'))
