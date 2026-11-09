"""x18: the Oct 18 Tier 1 chain (c02 outcomes, c06 family master with order-level windows, c07 cells and stack variants, c08 depth and corners,
c10 refill at the side being hit, c11 four arms) on the ACTUAL first-observed family starts of one session, method unchanged.
Usage: OD_WORK=<derived dir> OD_FAMILY_INDEX=<chronological-instance-index.csv> python3 -I x18_tier1_days.py <session>
Inputs: the family replication run's chronological-instance-index.csv for the date (markets-data 7b50d634, run 42566535537; the same 59 fields as the
October 18 ledger except candidate_status, which is October 18's own 50-case screen), the session's group arrays (the prior evening member from 21:00 UTC
plus the date member, from the rebuilt tapes, c01b) and the date member's reconstructed records (c03) for the order-level windows.
Differences from the originals, all recorded in t1_receipt.json: cutoff_ns = start_recv_ns - 1 ns where the index has no cutoff (the October 18 ledger's
rule); chronological_quarter = rank quartile within the date where absent; the Oct 18-only matched-50 pass (c09) and its named cases are not run;
the four-arm set labels carry the day's own counts.  Outputs: tables/<session>/t1_*.csv.  No trade cost anywhere."""
import sys, os, json, hashlib; sys.path.insert(0, '.'); sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'claude-pass'))
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import spearmanr
from odcfg import *
from c04_order_features import enrich, Windows
from fourarm import four_arms
SESS = sys.argv[1]; assert SESS in SESS_TAPES; PRIOR, DAY = SESS_TAPES[SESS]
IDX = os.environ['OD_FAMILY_INDEX']; TAB = f'{HERE}/tables/{SESS}'; os.makedirs(TAB, exist_ok=True)
S = 10**9; TICK = 0.001; H = [1, 5, 20, 60, 120, 300, 600]
receipt = dict(session=SESS, members=[PRIOR, DAY], family_index=f'tasks/family-research-20261022/family-replication/run-42566535537-1/family-{DAY}/chronological-instance-index.csv', family_index_markets_data_commit='7b50d634', family_index_local_copy=IDX, family_index_sha256=hashlib.sha256(open(IDX, 'rb').read()).hexdigest())
A = pd.read_csv(IDX); receipt['families'] = len(A)
if 'cutoff_ns' not in A: A['cutoff_ns'] = A.start_recv_ns - 1; receipt['cutoff_rule'] = 'start_recv_ns - 1 ns (index has no cutoff_ns)'
else: receipt['cutoff_rule'] = 'index cutoff_ns'; assert (A.start_recv_ns - A.cutoff_ns == 1).all()
if 'chronological_quarter' not in A: A['chronological_quarter'] = pd.qcut(A.start_recv_ns.rank(method='first'), 4, labels=[1, 2, 3, 4]).astype(int); receipt['quarter_rule'] = 'rank quartile within the date'
# ---- session group arrays: prior member from 21:00 UTC (the session open, as the retained export began) + the date member, ord renumbered from 0
day0 = pd.Timestamp(f'{DAY[:4]}-{DAY[4:6]}-{DAY[6:]}', tz='UTC'); open_ns = int((day0 - pd.Timedelta(hours=3)).value)
close_ns = int((day0 + pd.Timedelta(hours=21)).value)   # the session close; the retained exports ended here, so later groups of the UTC member are not session groups
zp = np.load(groups(PRIOR)); zd = np.load(groups(DAY)); keep = zp['recv_ns'] >= open_ns; keepd = zd['recv_ns'] < close_ns
G = {k: np.concatenate([zp[k][keep], zd[k][keepd]]) for k in ('recv_ns', 'bid_px', 'ask_px', 'bid_sz', 'ask_sz', 'bid_n', 'ask_n', 'lockcross')}
G['ord'] = np.arange(len(G['recv_ns'])); assert (np.diff(G['recv_ns']) >= 0).all()
receipt['groups'] = dict(prior_from_21utc=int(keep.sum()), day_to_close=int(keepd.sum()), day_after_close_left_out=int((~keepd).sum()), total=int(len(G['recv_ns'])), first_recv_utc=str(pd.to_datetime(G['recv_ns'][0], unit='ns', utc=True)), last_recv_utc=str(pd.to_datetime(G['recv_ns'][-1], unit='ns', utc=True)))
# one family per date can start at the very first group of the session: it has no earlier group to stand as its reference and is left out, with its id recorded (section 22's rule)
nopre = A.pre_input_cursor.isna() if 'pre_input_cursor' in A else pd.Series(False, index=A.index)   # the index's own marker: no pre-event source group in the retained span (the snapshot-start family)
drop = (A.cutoff_ns < G['recv_ns'][0]) | nopre; noref = A[drop]
receipt['excluded_no_earlier_group'] = dict(count=int(len(noref)), instances=[int(v) for v in noref.instance], family_ids=[str(v) for v in noref.family_id], start_utc=[str(v) for v in noref.start_utc], reason=['cutoff before first session group' if c else 'index has no pre-event source cursor' for c in (noref.cutoff_ns < G['recv_ns'][0])])
A = A[~drop].reset_index(drop=True); receipt['families_used'] = len(A)
recv = G['recv_ns']; mid = (G['bid_px'] + G['ask_px']) / 2e9; spr = (G['ask_px'] - G['bid_px']) / 1e9; bidp = G['bid_px'] / 1e9; askp = G['ask_px'] / 1e9
# ---- c02: outcomes
rows = []
for _, r in A.iterrows():
    cut = int(r['cutoff_ns']); st = int(r['start_recv_ns']); i0 = np.searchsorted(recv, cut, side='right') - 1; assert i0 >= 0
    row = dict(instance=int(r['instance']), ref_group=int(G['ord'][i0]), ref_recv_ns=int(recv[i0]), ref_mid=mid[i0], ref_spread=spr[i0],
               ref_bid_sz=int(G['bid_sz'][i0]), ref_ask_sz=int(G['ask_sz'][i0]), ref_bid_n=int(G['bid_n'][i0]), ref_ask_n=int(G['ask_n'][i0]))
    for h in H:
        end = st + h * S
        if end > recv[-1]: row[f'chg_{h}s'] = np.nan; row[f'grp_{h}s'] = -1; continue
        j = np.searchsorted(recv, end, side='right') - 1; row[f'chg_{h}s'] = mid[j] - mid[i0]; row[f'grp_{h}s'] = int(G['ord'][j])
    rows.append(row)
O = pd.DataFrame(rows); receipt['censored_per_horizon'] = {h: int(O[f'chg_{h}s'].isna().sum()) for h in H}
# ---- c06: family master
R0 = pd.read_parquet(recon(DAY)); R, C = enrich(R0); W = Windows(R, C); MEMBER_START = int(R.ts.iloc[0])
df = A.merge(O, on='instance')
for h in H: df[f'tk_{h}s'] = df[f'chg_{h}s'] / TICK
def prior(row, w):
    cut = int(row['cutoff_ns']); i0 = np.searchsorted(recv, cut, side='right') - 1; j = np.searchsorted(recv, cut - w * S, side='right') - 1
    if j < 0: return np.nan, np.nan, np.nan
    seg = slice(j, i0 + 1); qchg = int(((np.diff(bidp[seg]) != 0) | (np.diff(askp[seg]) != 0)).sum()); return (mid[i0] - mid[j]) / TICK, qchg, len(range(j, i0 + 1)) - 1
for w in (5, 20, 60):
    v = df.apply(lambda r: prior(r, w), axis=1, result_type='expand'); df[f'prior_tk_{w}s'] = v[0]; df[f'quote_changes_{w}s'] = v[1]; df[f'groups_{w}s'] = v[2]
df['touch_imb'] = (df.ref_bid_sz - df.ref_ask_sz) / (df.ref_bid_sz + df.ref_ask_sz); df['touch_n_imb'] = (df.ref_bid_n - df.ref_ask_n) / (df.ref_bid_n + df.ref_ask_n)
df['spread_ticks'] = np.round(df.ref_spread / TICK).astype(int)
cols = ['trade_sellagg','trade_buyagg','fill_b','fill_a','rm_fill_b','rm_fill_a','rm_cx_touch_b','rm_cx_touch_a','rm_cx_near_b','rm_cx_near_a',
        'add_touch_b','add_touch_a','add_near_b','add_near_a','mod_touch_b','mod_touch_a','n_add_touch_b','n_add_touch_a']
for w in (1, 5, 20, 60):
    vals = []
    for _, r in df.iterrows():
        st = int(r['start_recv_ns'])
        if st - w * S < MEMBER_START: vals.append([np.nan] * len(cols)); continue
        s, _e = W.sums(st - 1, w * S); vals.append([s[c] for c in cols])
    df = pd.concat([df, pd.DataFrame(vals, columns=[f'ob_{c}_{w}s' for c in cols], index=df.index)], axis=1)
df['in_member'] = df.start_recv_ns >= MEMBER_START + 60 * S
for w in (1, 5, 20, 60):
    df[f'ob_net_bid_{w}s'] = df[f'ob_add_touch_b_{w}s'] + df[f'ob_add_near_b_{w}s'] - df[f'ob_rm_fill_b_{w}s'] - df[f'ob_rm_cx_touch_b_{w}s'] - df[f'ob_rm_cx_near_b_{w}s']
    df[f'ob_net_ask_{w}s'] = df[f'ob_add_touch_a_{w}s'] + df[f'ob_add_near_a_{w}s'] - df[f'ob_rm_fill_a_{w}s'] - df[f'ob_rm_cx_touch_a_{w}s'] - df[f'ob_rm_cx_near_a_{w}s']
t = pd.to_datetime(df.start_recv_ns, unit='ns', utc=True); df['utc_hour'] = t.dt.hour + t.dt.minute / 60; df['settle_tag'] = ((df.utc_hour >= 18 + 25/60) & (df.utc_hour <= 18 + 35/60))
df.to_csv(f'{TAB}/t1_family_master.csv', index=False)
m = df[df.in_member]; okb = (m['ob_trade_buyagg_60s'] == m['root.activity.60.trade_buy_aggressor_qty']); oks = (m['ob_trade_sellagg_60s'] == m['root.activity.60.trade_sell_aggressor_qty'])
receipt.update(rows=len(df), in_member=int(df.in_member.sum()), settle_tag=int(df.settle_tag.sum()), reconcile_buy_60s=int(okb.sum()), reconcile_sell_60s=int(oks.sum()), of_in_member=len(m), member_start_utc=str(pd.to_datetime(MEMBER_START, unit='ns', utc=True)))
print(SESS, 'families', len(df), 'in_member', int(df.in_member.sum()), '| 60 s aggressor lots equal to retained operands: buy', int(okb.sum()), 'sell', int(oks.sum()), 'of', len(m))
# ---- c07: cells, stack variants, flags
d = df.copy(); sg = lambda x: np.where(pd.isna(x), 'NA', np.where(x > 0, '+', np.where(x < 0, '-', '0')))
d['f60'] = sg(d['root.activity.60.trade_aggressor_imbalance']); d['f5'] = sg(d['root.activity.5.trade_aggressor_imbalance']); d['f1'] = sg(d['root.activity.1.trade_aggressor_imbalance'])
d['dsg'] = sg(d['root.depth_imbalance_full']); d['dsg_n'] = sg(d['root.depth_imbalance_n']); d['pattern'] = d.f60 + '/' + d.f5 + '/' + d.f1
def dist(sub, h):
    x = sub[f'tk_{h}s'].dropna()
    return dict(n=len(x), down=int((x < 0).sum()), flat=int((x == 0).sum()), up=int((x > 0).sum()), q25=x.quantile(.25) if len(x) else np.nan, med=x.median() if len(x) else np.nan, q75=x.quantile(.75) if len(x) else np.nan)
rows = []
for (pat, ds), sub in d.groupby(['pattern', 'dsg']):
    for h in (1, 5, 60, 300): r = dist(sub, h); r.update(pattern_60_5_1=pat, full_depth_sign=ds, horizon_s=h, cell_n=len(sub)); rows.append(r)
pd.DataFrame(rows)[['pattern_60_5_1','full_depth_sign','cell_n','horizon_s','n','down','flat','up','q25','med','q75']].to_csv(f'{TAB}/t1_cells_flow_pattern_x_depth.csv', index=False)
N = len(d)
var = {'original: 60+/5-/1- , bid-heavy full depth': (d.f60=='+')&(d.f5=='-')&(d.f1=='-')&(d.dsg=='+'), 'inverse (all four flipped): 60-/5+/1+ , ask-heavy': (d.f60=='-')&(d.f5=='+')&(d.f1=='+')&(d.dsg=='-'),
       'flow same, depth flipped: 60+/5-/1- , ask-heavy': (d.f60=='+')&(d.f5=='-')&(d.f1=='-')&(d.dsg=='-'), 'flow flipped, depth same: 60-/5+/1+ , bid-heavy': (d.f60=='-')&(d.f5=='+')&(d.f1=='+')&(d.dsg=='+'),
       'flow same, depth missing/zero': (d.f60=='+')&(d.f5=='-')&(d.f1=='-')&(d.dsg=='0'), 'flow of original with any depth sign': (d.f60=='+')&(d.f5=='-')&(d.f1=='-'), 'flow flipped with any depth sign': (d.f60=='-')&(d.f5=='+')&(d.f1=='+'),
       'bid-heavy full depth, any flow': (d.dsg=='+'), 'ask-heavy full depth, any flow': (d.dsg=='-'), f'all {N}': d.instance>0}
rows = []
for name, mk in var.items():
    for h in H: r = dist(d[mk], h); r.update(variant=name, support=int(mk.sum()), horizon_s=h); rows.append(r)
pd.DataFrame(rows)[['variant','support','horizon_s','n','down','flat','up','q25','med','q75']].to_csv(f'{TAB}/t1_stack_variants.csv', index=False)
d.to_csv(f'{TAB}/t1_family_master_flags.csv', index=False)
# ---- c08: depth and corners, orientation to the 5 s flow
x = d['root.depth_imbalance_full']; y = d['root.depth_imbalance_n']
receipt['depth'] = dict(full_imbalance=dict(min=float(x.min()), q25=float(x.quantile(.25)), med=float(x.median()), q75=float(x.quantile(.75)), max=float(x.max())),
                        full_ratio_med=float((d['root.bid_depth_full']/d['root.ask_depth_full']).median()), near_neg=int((y<0).sum()), near_pos=int((y>0).sum()), near_zero=int((y==0).sum()), corr_full_near=float(np.corrcoef(x, y)[0,1]))
HH = [1, 5, 20, 60, 300]
def dist2(sub, h): v = sub[f'tk_{h}s'].dropna(); return dict(n=len(v), down=int((v<0).sum()), flat=int((v==0).sum()), up=int((v>0).sum()), med=v.median() if len(v) else np.nan)
d['flowpat'] = np.where((d.f60=='+')&(d.f5=='-')&(d.f1=='-'), 'orig(60+/5-/1-)', np.where((d.f60=='-')&(d.f5=='+')&(d.f1=='+'), 'flipped(60-/5+/1+)', 'other'))
d['near'] = np.where(d.dsg_n=='+', 'near bid-heavy', np.where(d.dsg_n=='-', 'near ask-heavy', 'near zero'))
rows = []
for (fp, nr), sub in d.groupby(['flowpat', 'near']):
    for h in HH: r = dist2(sub, h); r.update(flow=fp, near_depth=nr, support=len(sub), horizon_s=h); rows.append(r)
pd.DataFrame(rows)[['flow','near_depth','support','horizon_s','n','down','flat','up','med']].to_csv(f'{TAB}/t1_corners_flow_x_neardepth.csv', index=False)
d['dir5'] = np.where(d.f5=='+', 1, np.where(d.f5=='-', -1, 0)); rows = []
for fp in ['orig(60+/5-/1-)', 'flipped(60-/5+/1+)', 'all with signed 5 s flow']:
    sub = d[d.flowpat == fp] if fp != 'all with signed 5 s flow' else d[d.dir5 != 0]
    for h in HH:
        v = (sub[f'tk_{h}s'] * sub.dir5).dropna(); rows.append(dict(flow=fp, horizon_s=h, n=len(v), with_5s_flow=int((v>0).sum()), flat=int((v==0).sum()), against_5s_flow=int((v<0).sum()), med_ticks_in_flow_dir=v.median() if len(v) else np.nan))
pd.DataFrame(rows).to_csv(f'{TAB}/t1_oriented_to_5s_flow.csv', index=False)
# ---- c10: refill at the side being hit (in-member families)
e = d[d.in_member].copy()
e['bid_adds_1s'] = e.ob_add_touch_b_1s + e.ob_add_near_b_1s; e['ask_adds_1s'] = e.ob_add_touch_a_1s + e.ob_add_near_a_1s
e['bid_ratio_1s'] = np.where(e.ob_fill_b_1s > 0, e.bid_adds_1s / e.ob_fill_b_1s, np.nan); e['ask_ratio_1s'] = np.where(e.ob_fill_a_1s > 0, e.ask_adds_1s / e.ob_fill_a_1s, np.nan)
sell = e[(e.ob_trade_sellagg_1s > 0) & (e.ob_fill_b_1s > 0)].copy(); buy = e[(e.ob_trade_buyagg_1s > 0) & (e.ob_fill_a_1s > 0)].copy()
receipt['refill'] = dict(in_member=len(e), sell_hit_with_bid_fills=len(sell), buy_lift_with_ask_fills=len(buy))
def tert(sub, ratio, label, hit_dir):
    sub = sub.copy(); sub['grp'] = pd.qcut(sub[ratio].rank(method='first'), 3, labels=['low', 'mid', 'high']); rows = []
    for g, s_ in sub.groupby('grp'):
        for h in HH:
            v = s_[f'tk_{h}s'].dropna()
            rows.append(dict(set=label, tercile=g, ratio_lo=s_[ratio].min(), ratio_hi=s_[ratio].max(), horizon_s=h, n=len(v), down=int((v<0).sum()), flat=int((v==0).sum()), up=int((v>0).sum()), med_ticks=v.median() if len(v) else np.nan,
                             med_fill_lots=s_['ob_fill_b_1s' if hit_dir=='bid' else 'ob_fill_a_1s'].median()))
    return pd.DataFrame(rows)
T = pd.concat([tert(sell, 'bid_ratio_1s', 'sell-hit last 1s: bid adds / bid fills', 'bid'), tert(buy, 'ask_ratio_1s', 'buy-lift last 1s: ask adds / ask fills', 'ask')]); T.to_csv(f'{TAB}/t1_refill_terciles.csv', index=False)
sp_rows = []
for lab, sub, rr in (('sell-hit', sell, 'bid_ratio_1s'), ('buy-lift', buy, 'ask_ratio_1s')):
    for h in HH:
        xx = sub[[rr, f'tk_{h}s']].dropna(); rho, p = spearmanr(xx[rr], xx[f'tk_{h}s']) if len(xx) > 2 else (np.nan, np.nan); sp_rows.append(dict(set=lab, horizon_s=h, spearman=rho, n=len(xx)))
pd.DataFrame(sp_rows).to_csv(f'{TAB}/t1_refill_spearman.csv', index=False)
sell['fillbin'] = pd.qcut(sell.ob_fill_b_1s.rank(method='first'), 2, labels=['small fills', 'large fills']); rows = []
for fb, s_ in sell.groupby('fillbin'):
    hi = s_.bid_ratio_1s >= s_.bid_ratio_1s.median()
    for h in (1, 5, 300):
        for lab, ss in (('ratio>=median', s_[hi]), ('ratio<median', s_[~hi])):
            v = ss[f'tk_{h}s'].dropna(); rows.append(dict(fill_stratum=fb, group=lab, horizon_s=h, n=len(v), down=int((v<0).sum()), flat=int((v==0).sum()), up=int((v>0).sum()), med=v.median() if len(v) else np.nan))
pd.DataFrame(rows).to_csv(f'{TAB}/t1_refill_by_fill_stratum.csv', index=False)
# ---- c11: four arms
for w in (5, 60): d[f'lev{w}'] = np.log1p(d[f'root.activity.{w}.event_count']); d[f'lcx{w}'] = np.log1p(d[f'root.activity.{w}.top_level_cancel_qty_derived']); d[f'lq{w}'] = np.log1p(d[f'root.activity.{w}.trade_buy_aggressor_qty'] + d[f'root.activity.{w}.trade_sell_aggressor_qty'])
imb = lambda w: d[f'root.activity.{w}.trade_aggressor_imbalance']
d['ix_f5_dn'] = imb(5) * d['root.depth_imbalance_n']; d['ix_f60_dn'] = imb(60) * d['root.depth_imbalance_n']; d['ix_f1_touch'] = imb(1) * d['touch_imb']
for w in (1, 5, 20): d[f'ob_netdiff_{w}s'] = d[f'ob_net_bid_{w}s'] - d[f'ob_net_ask_{w}s']
d['bid_ratio_1s'] = np.where(d.ob_fill_b_1s > 0, np.log1p(d.ob_add_touch_b_1s + d.ob_add_near_b_1s) - np.log1p(d.ob_fill_b_1s), np.nan)
d['ask_ratio_1s'] = np.where(d.ob_fill_a_1s > 0, np.log1p(d.ob_add_touch_a_1s + d.ob_add_near_a_1s) - np.log1p(d.ob_fill_a_1s), np.nan); d['start_ns'] = d.start_recv_ns
base = ['spread_ticks', 'lev5', 'lev60', 'prior_tk_5s', 'prior_tk_20s', 'prior_tk_60s', 'quote_changes_5s', 'quote_changes_20s', 'quote_changes_60s']
flow = [f'root.activity.{w}.trade_aggressor_imbalance' for w in (1, 5, 20, 60, 300)] + ['lq5', 'lq60']
book = ['root.depth_imbalance_full', 'root.depth_imbalance_n', 'touch_imb', 'touch_n_imb', 'lcx5', 'lcx60']; book_ob = book + ['ob_netdiff_1s', 'ob_netdiff_5s', 'ob_netdiff_20s', 'bid_ratio_1s', 'ask_ratio_1s']
ix = ['ix_f5_dn', 'ix_f60_dn', 'ix_f1_touch']; NN = 100; allrows = []; blocks = []; nin = int(d.in_member.sum())
for label, sub, bk in ((f'T1 all {N} families (book: root fields)', d, book), (f'T1b {nin} in-member families (book: root + order-level)', d[d.in_member], book_ob)):
    for h in (1, 5, 20, 60, 300):
        xx = sub.copy(); xx['end_ns'] = xx.start_ns + h * S
        out, pb, nulls, n = four_arms(xx, base, flow, bk, f'tk_{h}s', K=5, clip=10, nnull=NN, extra_both=ix)
        out['null_q05'] = [nulls[a].quantile(.05) for a in out.index]; out['null_med'] = [nulls[a].median() for a in out.index]; out['frac_null_le_obs'] = [(nulls[a] <= out.loc[a, 'mse_vs_zero']).mean() for a in out.index]
        out['sign_null_med'] = [nulls.attrs['sign'][a].median() for a in out.index]; out['sign_frac_null_ge_obs'] = [(nulls.attrs['sign'][a] >= out.loc[a, 'sign_share']).mean() for a in out.index]
        out.insert(0, 'horizon_s', h); out.insert(0, 'set', label); out.insert(2, 'rows', n); allrows.append(out.reset_index().rename(columns={'index': 'arm'}))
        for a, r in pb.items(): r = r.copy(); r.insert(0, 'arm', a); r.insert(0, 'horizon_s', h); r.insert(0, 'set', label); blocks.append(r)
pd.concat(allrows).to_csv(f'{TAB}/t1_fourarm_summary.csv', index=False); pd.concat(blocks).to_csv(f'{TAB}/t1_fourarm_by_block.csv', index=False)
json.dump(receipt, open(f'{TAB}/t1_receipt.json', 'w'), indent=1); print(SESS, 'done:', json.dumps({k: receipt[k] for k in ('families', 'in_member', 'reconcile_buy_60s', 'reconcile_sell_60s', 'of_in_member', 'censored_per_horizon')}))
