import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
d = pd.read_csv('tables/t1_family_master_flags.csv'); S=10**9
m = d[d.candidate_status=='matched'].sort_values('start_recv_ns').copy()
sgn = lambda v: np.where(pd.isna(v),'NA',np.where(v>0,'up',np.where(v<0,'down','flat')))
m['s5']=sgn(m.tk_5s); m['s60']=sgn(m.tk_60s); m['s300']=sgn(m.tk_300s)
m['path']= m.s5+'@5s -> '+m.s60+'@60s -> '+m.s300+'@300s'
# time clustering: new episode when gap to previous matched start > 300 s
gap=(m.start_recv_ns.diff()/S).fillna(1e9); m['episode']=(gap>300).cumsum()
m['gap_prev_s']=gap.round(1)
# how many of ALL 749 families start inside each case's [-120,+600] s window (shared outcome window)
allst=d.start_recv_ns.values
m['families_in_window']=[(int(((allst>=s-120*S)&(allst<=s+600*S)).sum())-1) for s in m.start_recv_ns]
m['other_matched_in_window']=[(int(((m.start_recv_ns.values>=s-120*S)&(m.start_recv_ns.values<=s+600*S)).sum())-1) for s in m.start_recv_ns]
cols=['instance','start_utc','episode','gap_prev_s','ref_mid','spread_ticks','tk_1s','tk_5s','tk_20s','tk_60s','tk_300s','tk_600s','path','families_in_window','other_matched_in_window',
      'root.activity.60.trade_buy_aggressor_qty','root.activity.60.trade_sell_aggressor_qty','root.activity.5.trade_buy_aggressor_qty','root.activity.5.trade_sell_aggressor_qty','root.activity.1.trade_buy_aggressor_qty','root.activity.1.trade_sell_aggressor_qty',
      'root.depth_imbalance_n','touch_imb','ref_bid_sz','ref_ask_sz','in_member','settle_tag']
m[cols].to_csv('tables/t1_matched50_cases.csv',index=False)
print('matched',len(m),'episodes (gap>300s):',m.episode.nunique(),'sizes',m.groupby('episode').size().sort_values(ascending=False).head(8).tolist())
print(m.path.value_counts().to_string())
print('with <=1 other matched in window:', int((m.other_matched_in_window<=1).sum()), '| median other families in window', m.families_in_window.median())
print('settle-tagged matched:',int(m.settle_tag.sum()),'| outside Oct18 member:',int((~m.in_member).sum()))
# order-level pre windows (60 s ending at the strict cutoff): distribution across matched cases that have them
mm=m[m.in_member]
for c in ['ob_trade_sellagg_60s','ob_trade_buyagg_60s','ob_add_touch_b_5s','ob_add_near_b_5s','ob_rm_fill_b_5s','ob_rm_cx_touch_b_5s','ob_rm_cx_near_b_5s','ob_net_bid_5s','ob_net_ask_5s','ob_net_bid_20s','ob_net_ask_20s']:
    print(f'{c:24s} n={mm[c].notna().sum():3d} q25={mm[c].quantile(.25):7.1f} med={mm[c].median():7.1f} q75={mm[c].quantile(.75):7.1f}')
# cases 375 / 391 side by side, key columns
k=m[m.instance.isin([375,391])].set_index('instance')[['start_utc','ref_mid','spread_ticks','tk_1s','tk_5s','tk_20s','tk_60s','tk_120s','tk_300s','tk_600s','episode','gap_prev_s','other_matched_in_window']]
print(k.T.to_string())
