"""x19: the Tier 1 tables of the four sessions (x18) side by side, cell by cell, with Oct 18 as the reference column.  Usage: python3 -I x19_tier1_crossday.py
Reads tables/<session>/t1_*.csv and writes crossday/t1x_*.csv: one row per (variant, horizon), (flow pattern, depth sign, horizon), (flow, near depth, horizon),
(flow, horizon) oriented to the 5 s flow, (refill set, tercile, horizon), (fill stratum, group, horizon) and (four-arm set, horizon, arm), with each day's counts
and medians beside each other.  Counts stay counts; shares are per day; nothing is averaged across days.  No trade cost anywhere."""
import os, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); DATES = ['20231002', '20231003', '20231017', '20231018']; OUT = f'{HERE}/crossday'; os.makedirs(OUT, exist_ok=True)
def sfx(d): return d[4:]
def tab(d, n): return pd.read_csv(f'{HERE}/tables/{d}/{n}')
rec = []
def side_by_side(name, keys, vals, norm=None):
    T = {}
    for d in DATES:
        t = tab(d, name)
        if norm: t = norm(t)
        T[d] = t.set_index(keys); rec.append(dict(kind='input', date=d, table=name, rows=len(t))); assert T[d].index.is_unique, (name, d)
    idx = sorted(set().union(*[set(T[d].index) for d in DATES]), key=lambda k: tuple(str(v) for v in (k if isinstance(k, tuple) else (k,))))
    R = pd.DataFrame(index=pd.MultiIndex.from_tuples(idx, names=keys) if len(keys) > 1 else pd.Index(idx, name=keys[0]))
    for d in DATES:
        t = T[d].reindex(R.index)
        for v in vals: R[f'{v}_{sfx(d)}'] = t[v].to_numpy()
    R['days_present'] = sum(R[f'{vals[0]}_{sfx(d)}'].notna().astype(int) for d in DATES)
    return R.reset_index()
def add_shares(R, n='n', down='down', up='up'):
    for d in DATES:
        nn = R[f'{n}_{sfx(d)}']; R[f'down_share_{sfx(d)}'] = R[f'{down}_{sfx(d)}'] / nn; R[f'up_share_{sfx(d)}'] = R[f'{up}_{sfx(d)}'] / nn
    M = np.column_stack([R[f'up_share_{sfx(d)}'] - R[f'down_share_{sfx(d)}'] for d in DATES]); pos = (M > 0).sum(1); neg = (M < 0).sum(1)
    R['days_more_up_than_down'] = pos; R['days_more_down_than_up'] = neg; return R
# 1. stack variants (the 'all N' row is renamed to 'all families' so the days align)
def norm_var(t): t = t.copy(); t['variant'] = t.variant.where(~t.variant.str.startswith('all '), 'all families'); return t
V = add_shares(side_by_side('t1_stack_variants.csv', ['variant', 'horizon_s'], ['support', 'n', 'down', 'flat', 'up', 'med'], norm_var))
V.to_csv(f'{OUT}/t1x_stack_variants_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t1x_stack_variants_crossday.csv', rows=len(V)))
# 2. cells: flow pattern x full-depth sign
C = add_shares(side_by_side('t1_cells_flow_pattern_x_depth.csv', ['pattern_60_5_1', 'full_depth_sign', 'horizon_s'], ['cell_n', 'n', 'down', 'flat', 'up', 'med']))
C.to_csv(f'{OUT}/t1x_cells_flow_pattern_x_depth_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t1x_cells_flow_pattern_x_depth_crossday.csv', rows=len(C)))
# 3. corners: flow x near depth
K = add_shares(side_by_side('t1_corners_flow_x_neardepth.csv', ['flow', 'near_depth', 'horizon_s'], ['support', 'n', 'down', 'flat', 'up', 'med']))
K.to_csv(f'{OUT}/t1x_corners_flow_x_neardepth_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t1x_corners_flow_x_neardepth_crossday.csv', rows=len(K)))
# 4. oriented to the 5 s flow
Oo = side_by_side('t1_oriented_to_5s_flow.csv', ['flow', 'horizon_s'], ['n', 'with_5s_flow', 'flat', 'against_5s_flow', 'med_ticks_in_flow_dir'])
for d in DATES: Oo[f'with_share_{sfx(d)}'] = Oo[f'with_5s_flow_{sfx(d)}'] / Oo[f'n_{sfx(d)}']
Oo.to_csv(f'{OUT}/t1x_oriented_to_5s_flow_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t1x_oriented_to_5s_flow_crossday.csv', rows=len(Oo)))
# 5. refill terciles and fill strata
Rt = add_shares(side_by_side('t1_refill_terciles.csv', ['set', 'tercile', 'horizon_s'], ['ratio_lo', 'ratio_hi', 'n', 'down', 'flat', 'up', 'med_ticks', 'med_fill_lots']))
Rt.to_csv(f'{OUT}/t1x_refill_terciles_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t1x_refill_terciles_crossday.csv', rows=len(Rt)))
Rs = add_shares(side_by_side('t1_refill_by_fill_stratum.csv', ['fill_stratum', 'group', 'horizon_s'], ['n', 'down', 'flat', 'up', 'med']))
Rs.to_csv(f'{OUT}/t1x_refill_by_fill_stratum_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t1x_refill_by_fill_stratum_crossday.csv', rows=len(Rs)))
Sp = side_by_side('t1_refill_spearman.csv', ['set', 'horizon_s'], ['spearman', 'n']); Sp.to_csv(f'{OUT}/t1x_refill_spearman_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t1x_refill_spearman_crossday.csv', rows=len(Sp)))
# 6. four arms (set labels carry each day's counts; normalised to the set type)
def norm_set(t): t = t.copy(); t['set'] = np.where(t.set.str.startswith('T1b'), 'T1b in-member (book: root + order-level)', 'T1 all (book: root fields)'); return t
F = side_by_side('t1_fourarm_summary.csv', ['set', 'horizon_s', 'arm'], ['rows', 'n_test', 'mse_vs_zero', 'mae_vs_zero', 'sign_share', 'sign_n', 'null_q05', 'null_med', 'frac_null_le_obs', 'sign_null_med', 'sign_frac_null_ge_obs'], norm_set)
M = np.column_stack([F[f'mse_vs_zero_{sfx(d)}'] < 1 for d in DATES]); F['days_mse_below_zero_benchmark'] = M.sum(1)
M2 = np.column_stack([F[f'sign_share_{sfx(d)}'] > 0.5 for d in DATES]); F['days_sign_share_above_half'] = M2.sum(1)
F.to_csv(f'{OUT}/t1x_fourarm_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t1x_fourarm_crossday.csv', rows=len(F)))
# 7. receipts and depth side by side
rows = []
for d in DATES:
    r = json.load(open(f'{HERE}/tables/{d}/t1_receipt.json'))
    rows.append(dict(date=d, families_in_index=r['families'], families_used=r['families_used'], excluded=r['excluded_no_earlier_group']['count'], in_member=r['in_member'], reconcile_buy_60s=r['reconcile_buy_60s'], reconcile_sell_60s=r['reconcile_sell_60s'], of_in_member=r['of_in_member'],
                     groups=r['groups']['total'], first_group_utc=r['groups']['first_recv_utc'][:19], last_group_utc=r['groups']['last_recv_utc'][:19], censored_300s=r['censored_per_horizon']['300'], censored_600s=r['censored_per_horizon']['600'],
                     full_depth_imb_min=r['depth']['full_imbalance']['min'], full_depth_imb_q25=r['depth']['full_imbalance']['q25'], full_depth_imb_med=r['depth']['full_imbalance']['med'], full_depth_imb_q75=r['depth']['full_imbalance']['q75'], full_depth_imb_max=r['depth']['full_imbalance']['max'],
                     full_ratio_med=r['depth']['full_ratio_med'], near_neg=r['depth']['near_neg'], near_pos=r['depth']['near_pos'], near_zero=r['depth']['near_zero'], corr_full_near=r['depth']['corr_full_near'],
                     refill_in_member=r['refill']['in_member'], sell_hit_with_bid_fills=r['refill']['sell_hit_with_bid_fills'], buy_lift_with_ask_fills=r['refill']['buy_lift_with_ask_fills']))
pd.DataFrame(rows).to_csv(f'{OUT}/t1x_receipts.csv', index=False); rec.append(dict(kind='output', date='all', table='t1x_receipts.csv', rows=4))
pd.DataFrame(rec).to_csv(f'{OUT}/t1x_receipt.csv', index=False); print(pd.DataFrame(rec).to_string(index=False))
