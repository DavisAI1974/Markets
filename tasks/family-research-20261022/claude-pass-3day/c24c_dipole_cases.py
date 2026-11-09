"""Dipole cohort, step 3: cases with source coordinates.  Eight cases: the four narrated in the log (re-traced independently on my reconstruction) and four chosen by a fixed rule
from cohort cells (typical = the member whose oriented move magnitude is the lower median of its cell, ties to the earliest).  Nothing here is chosen for its outcome beyond the cell.
Source coordinates: tape day label and record index range in my reconstruction of that tape, receive times, and Codex's cursors (provenance only).
Outputs: tables/dipole/t6_cohort_cases.csv, t6_cohort_case_paths.csv"""
import sys; sys.path.insert(0, '.')
from odcfg import *
import gzip, json, numpy as np, pandas as pd
S = 10**9
rows = [json.loads(l) for l in gzip.open(CAND, 'rt')]
F = pd.read_csv(f'{TABD}/t6_cohort_features.csv', dtype={'tape': str})
def typical(g, col):
    if not len(g): return None
    g = g.assign(_a=g[col].abs()).sort_values(['_a', 'prov_birth_second']); return g.iloc[(len(g) - 1) // 2]
sel = []
for tag in (('1697581215', '1697583021', '1697625921', '1697607905') if SESS == '20231018' else ()):   # the four narrated log cases exist for Oct 18 only
    r = F[F.prov_birth_second == int(tag)]; assert len(r) == 1, tag; sel.append(('log case', r.iloc[0]))
_t = typical(F[(F.codex_flow_state == 'opposite_direction_at_emission') & (F.retro_cat == 'in')], 'retro_o')
if _t is not None: sel.append(('cell: opposite recent flow, midpoint moved in birth direction', _t))
_t = typical(F[(F.codex_flow_state == 'same_direction_at_emission') & (F.retro_cat == 'opp')], 'retro_o')
if _t is not None: sel.append(('cell: same-direction recent flow, midpoint moved against birth direction', _t))
_t = typical(F[(F.depth_mine == 'aligned') & (F.retro_cat == 'opp')], 'retro_o')
if _t is not None: sel.append(('cell: prebirth depth aligned, midpoint moved against birth direction', _t))
_t = typical(F[(F.retro_cat == 'in') & (F.fwd_20_cat == 'opp')], 'fwd_20_o')
if _t is not None: sel.append(('cell: midpoint moved in birth direction by recognition, then opposite by +20 s', _t))
case_rows = []; path_rows = []
R0 = {}; G = {}
for k, (why, r) in enumerate(sel, 1):
    d = r.tape
    if d not in R0:
        R0[d] = pd.read_parquet(recon(d)); R0[d]['t'] = pd.DatetimeIndex(R0[d].ts_recv).as_unit('ns').asi8; z = np.load(groups(d)); G[d] = {x: z[x] for x in z.files}
    R, g = R0[d], G[d]; cj = rows[int(r.row)]
    pre = int(r.prov_birth_second) * S - 1; rec = int(r.prov_recognition_ns); end = rec + 60 * S
    i_pre = np.searchsorted(g['recv_ns'], pre, side='right') - 1; i_rec = np.searchsorted(g['recv_ns'], rec, side='right') - 1
    assert g['recv_ns'][i_rec] == rec
    a0 = int(g['rec_idx'][i_pre]); a1 = int(g['rec_idx'][i_rec]); a2 = int(g['rec_idx'][np.searchsorted(g['recv_ns'], end, side='right') - 1])
    tr = R[(R.action == 'T') & (R.t > g['recv_ns'][i_pre]) & (R.t <= rec)]
    lots_b = int(tr.loc[tr.side == 'B', 'size'].sum()); lots_s = int(tr.loc[tr.side == 'A', 'size'].sum())
    case_rows.append(dict(case=k, why=why, tape_day=d, tape_label='NG_v0_mbo_' + d + '.dbn.zst', birth_polarity=int(r.polarity), regime_pre=r.pre_regime, recognition_delay_s=round(r.delay_s, 3),
        record_index_last_group_before_birth=a0, record_index_recognition=a1, record_index_rec_plus60=a2, codex_prebirth_close_cursor=(cj.get('prebirth_quote') or {}).get('close_cursor'), codex_recognition_cursor=cj['recognition_cursor'],
        pre_bid=g['bid_px'][i_pre] / 1e6, pre_ask=g['ask_px'][i_pre] / 1e6, pre_bid_lots=int(g['bid_sz'][i_pre]), pre_ask_lots=int(g['ask_sz'][i_pre]),
        rec_bid=g['bid_px'][i_rec] / 1e6, rec_ask=g['ask_px'][i_rec] / 1e6, rec_bid_lots=int(g['bid_sz'][i_rec]), rec_ask_lots=int(g['ask_sz'][i_rec]),
        retro_ticks_oriented=r.retro_o, fwd1=r.fwd_1_o, fwd5=r.fwd_5_o, fwd20=r.fwd_20_o, fwd60=r.fwd_60_o, trades_between_buy_agg_lots=lots_b, trades_between_sell_agg_lots=lots_s,
        flow_20_at_prebirth_net=r.pre_net_20, flow_20_at_recognition_buy=r.rec_buy_20, flow_20_at_recognition_sell=r.rec_sell_20, codex_flow_state=r.codex_flow_state, depth_vs_birth=r.depth_mine))
    # path: quote changes from the last group before birth to rec+60 s, trades in the same span (rel. seconds are from the birth second start)
    gi = np.arange(i_pre, np.searchsorted(g['recv_ns'], end, side='right')); b = g['bid_px'][gi]; a = g['ask_px'][gi]
    ch = np.concatenate([[True], (np.diff(b) != 0) | (np.diff(a) != 0) | (np.diff(g['bid_sz'][gi]) != 0) | (np.diff(g['ask_sz'][gi]) != 0)])
    for j in gi[ch]:
        path_rows.append(dict(case=k, t_rel_s=(g['recv_ns'][j] - int(r.prov_birth_second) * S) / S, kind='group close', record_index=int(g['rec_idx'][j]), bid=g['bid_px'][j] / 1e6, ask=g['ask_px'][j] / 1e6,
                              bid_lots=int(g['bid_sz'][j]), ask_lots=int(g['ask_sz'][j]), lots='', side=''))
    trw = R[(R.action == 'T') & (R.t > g['recv_ns'][i_pre]) & (R.t <= end)]
    for ix, t in trw.iterrows():
        path_rows.append(dict(case=k, t_rel_s=(t.t - int(r.prov_birth_second) * S) / S, kind='trade', record_index=int(ix), bid='', ask='', bid_lots='', ask_lots='', lots=int(t['size']), side=t.side))
CS = pd.DataFrame(case_rows); PA = pd.DataFrame(path_rows).sort_values(['case', 't_rel_s'])
CS.to_csv(f'{TABD}/t6_cohort_cases.csv', index=False); PA.to_csv(f'{TABD}/t6_cohort_case_paths.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 50)
print(CS.drop(columns=['tape_label']).T.to_string()); print(PA.groupby(['case', 'kind']).size().unstack())
