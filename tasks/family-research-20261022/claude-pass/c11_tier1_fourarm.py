import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd, warnings, json; warnings.filterwarnings('ignore')
from fourarm import four_arms
S = 10**9
d = pd.read_csv('tables/t1_family_master_flags.csv'); d = d.copy()
for w in (5, 60): d[f'lev{w}'] = np.log1p(d[f'root.activity.{w}.event_count'])
for w in (5, 60): d[f'lcx{w}'] = np.log1p(d[f'root.activity.{w}.top_level_cancel_qty_derived'])
for w in (5, 60): d[f'lq{w}'] = np.log1p(d[f'root.activity.{w}.trade_buy_aggressor_qty'] + d[f'root.activity.{w}.trade_sell_aggressor_qty'])
imb = lambda w: d[f'root.activity.{w}.trade_aggressor_imbalance']
d['ix_f5_dn'] = imb(5) * d['root.depth_imbalance_n']; d['ix_f60_dn'] = imb(60) * d['root.depth_imbalance_n']; d['ix_f1_touch'] = imb(1) * d['touch_imb']
for w in (1, 5, 20):
    d[f'ob_netdiff_{w}s'] = d[f'ob_net_bid_{w}s'] - d[f'ob_net_ask_{w}s']
d['bid_ratio_1s'] = np.where(d.ob_fill_b_1s > 0, np.log1p(d.ob_add_touch_b_1s + d.ob_add_near_b_1s) - np.log1p(d.ob_fill_b_1s), np.nan)
d['ask_ratio_1s'] = np.where(d.ob_fill_a_1s > 0, np.log1p(d.ob_add_touch_a_1s + d.ob_add_near_a_1s) - np.log1p(d.ob_fill_a_1s), np.nan)
d['start_ns'] = d.start_recv_ns
base = ['spread_ticks', 'lev5', 'lev60', 'prior_tk_5s', 'prior_tk_20s', 'prior_tk_60s', 'quote_changes_5s', 'quote_changes_20s', 'quote_changes_60s']
flow = [f'root.activity.{w}.trade_aggressor_imbalance' for w in (1, 5, 20, 60, 300)] + ['lq5', 'lq60']
book = ['root.depth_imbalance_full', 'root.depth_imbalance_n', 'touch_imb', 'touch_n_imb', 'lcx5', 'lcx60']
book_ob = book + ['ob_netdiff_1s', 'ob_netdiff_5s', 'ob_netdiff_20s', 'bid_ratio_1s', 'ask_ratio_1s']
ix = ['ix_f5_dn', 'ix_f60_dn', 'ix_f1_touch']
NN = 100; allrows = []; blocks = []
for label, sub, bk in (('T1 all 749 families (book: root fields)', d, book), ('T1b 694 in-member families (book: root + order-level)', d[d.in_member], book_ob)):
    for h in (1, 5, 20, 60, 300):
        x = sub.copy(); x['end_ns'] = x.start_ns + h * S
        out, pb, nulls, n = four_arms(x, base, flow, bk, f'tk_{h}s', K=5, clip=10, nnull=NN, extra_both=ix)
        out['null_q05'] = [nulls[a].quantile(.05) for a in out.index]; out['null_med'] = [nulls[a].median() for a in out.index]
        out['frac_null_le_obs'] = [(nulls[a] <= out.loc[a, 'mse_vs_zero']).mean() for a in out.index]
        out['sign_null_med'] = [nulls.attrs['sign'][a].median() for a in out.index]; out['sign_frac_null_ge_obs'] = [(nulls.attrs['sign'][a] >= out.loc[a, 'sign_share']).mean() for a in out.index]
        out.insert(0, 'horizon_s', h); out.insert(0, 'set', label); out.insert(2, 'rows', n); allrows.append(out.reset_index().rename(columns={'index': 'arm'}))
        for a, r in pb.items(): r = r.copy(); r.insert(0, 'arm', a); r.insert(0, 'horizon_s', h); r.insert(0, 'set', label); blocks.append(r)
R = pd.concat(allrows); R.to_csv('tables/t1_fourarm_summary.csv', index=False); pd.concat(blocks).to_csv('tables/t1_fourarm_by_block.csv', index=False)
pd.set_option('display.width', 250)
print(R[['set', 'horizon_s', 'arm', 'rows', 'n_test', 'mse_vs_zero', 'mae_vs_zero', 'sign_agree', 'sign_n', 'null_q05', 'null_med', 'frac_null_le_obs', 'sign_share', 'sign_null_med', 'sign_frac_null_ge_obs']].round(3).to_string(index=False))
