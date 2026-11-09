"""x14: the Tier 2 tables of the four UTC members (Oct 2, 3, 17, 18) side by side, pair by pair and cell by cell, with Oct 18 as the reference column.
Usage: python3 -I x14_tier2_crossday.py
Reads only the committed tables/<date>/t2_*.csv written by c14, c15, c16, c17 and c18 (the same code on every day).  Nothing is recomputed from the grids
and nothing is averaged across days: every row of the outputs is one pair, one cell, one lead-lag pair or one selection step, with the four days' values
beside each other and counts of how many days share a sign.  Days are column labels only.  No trade cost anywhere.
Outputs (crossday/):
  t2x_coupling_crossday.csv        one row per (condition x, outcome y) present on all four days: rho, n, chunk agreement and the per-day shifted-Y line per day,
                                   days sharing the majority sign, other days sharing Oct 18's sign, smallest and median |rho|, range, outcome family, condition group
  t2x_coupling_summary.csv         counts of pairs by days-same-sign and by days-beyond-line (one row; no reference distribution: c14 does not save its draws)
  t2x_leadlag_crossday.csv         one row per (A, B): peak lag and peak rho per day, rho at lags 0, +1, -1, +5 per day, exceeds-band flag per day, agreement counts
  t2x_state_cells_crossday.csv     one row per (cell, horizon) present on any day: net share, support, z, chunk agreement, median ticks per day; days present; agreement
  t2x_pair_couplings_crossday.csv  one row per (x1, x2, y) that enters any day's top 400 by |interaction partial|: interaction per day where listed, its rank, top-60
                                   membership and the flip flag where listed; days listed; agreement among the days that list it
  t2x_forward_stack_paths.csv      one row per (outcome, step): the feature added and the out-of-fold correlation and gain on each day
  t2x_forward_stack_features.csv   one row per (outcome, feature) selected on any day: the step at which each day selected it (blank = not selected), days selected
  t2x_coupling_shifted_reference.csv  (when OD_WORK holds the x16 draws) the same agreement counts for 20 shifted-Y draws, combined day by day
  t2x_pair_couplings_full_crossday.csv, _summary.csv  (when crossday/pairs_full/ holds the x17 tables) every (x1, x2, y) on all four days
  t2x_receipt.csv                  rows read per table per day and rows written per output"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); DATES = ['20231002', '20231003', '20231017', '20231018']; REF = '20231018'
OUT = f'{HERE}/crossday'; os.makedirs(OUT, exist_ok=True)
def tab(d, name): return f'{HERE}/tables/{d}/{name}'
def sfx(d): return d[4:]
FAM = {'signed move': ['dm_1', 'dm_5', 'dm_20', 'dm_60'], 'magnitude': ['am_5', 'am_20'], 'quote response': ['dbid_5', 'dask_5', 'dspr_5'],
       'flow persistence': ['F_net_5', 'F_net_20'], 'book response': ['F_sup_b_5', 'F_sup_a_5', 'F_cx_b_5', 'F_cx_a_5', 'F_add_b_5', 'F_add_a_5']}
fam_of = {y: f for f, ys in FAM.items() for y in ys}
def xgroup(x):
    p = x.split('_')[0]
    if p in ('buy', 'sell', 'net', 'imb', 'ntr'): return 'flow'
    if p in ('addT', 'addN', 'addF', 'cxT', 'cxN', 'cxF', 'rmF', 'fill', 'modT', 'refill', 'sup', 'supdiff', 'cxshare'): return 'book behaviour by side'
    if x in ('spr', 'bsz', 'asz', 'bn', 'an', 'bsz_per_ord', 'asz_per_ord', 'tch_imb', 'tchn_imb', 'age_s', 'qage_s'): return 'touch state'
    if x in ('nb5', 'nb10', 'na5', 'na10', 'near5_imb', 'near10_imb'): return 'near depth'
    if p == 'prior': return 'prior displacement'
    if p == 'qchg': return 'quote changes'
    return 'other'
rec = []
def read(d, name):
    t = pd.read_csv(tab(d, name)); rec.append(dict(kind='input', date=d, table=name, rows=len(t))); return t
def sign_counts(M):
    """M: rows x days matrix of signed values (NaN allowed).  Returns days with a value, days sharing the majority sign, the majority sign, and days agreeing with the last column."""
    pos = (M > 0).sum(1); neg = (M < 0).sum(1); present = np.isfinite(M).sum(1)
    maj = np.where(pos >= neg, '+', '-'); same = np.maximum(pos, neg)
    ref = M[:, -1]; agree_ref = np.array([int(np.sum(np.sign(M[i, :-1][np.isfinite(M[i, :-1])]) == np.sign(ref[i]))) if np.isfinite(ref[i]) and ref[i] != 0 else -1 for i in range(M.shape[0])])
    return present, same, maj, agree_ref

# ---- 1. condition / outcome couplings (c14)
C = {d: read(d, 't2_coupling_conditions.csv') for d in DATES}
keys = None
for d in DATES:
    k = set(zip(C[d].x, C[d].y)); keys = k if keys is None else keys & k
all_keys = set().union(*[set(zip(C[d].x, C[d].y)) for d in DATES])
P = pd.DataFrame(sorted(keys), columns=['x', 'y'])
for d in DATES:
    t = C[d].set_index(['x', 'y']).loc[list(zip(P.x, P.y))]
    P[f'rho_{sfx(d)}'] = t.rho.to_numpy(); P[f'n_{sfx(d)}'] = t.n.to_numpy().astype(int)
    P[f'chunks_agree_{sfx(d)}'] = t.same_sign_chunks.astype(int).astype(str).to_numpy() + '/' + t.chunks.astype(int).astype(str).to_numpy()
    P[f'beyond_line_{sfx(d)}'] = t.exceeds_null95.astype(bool).to_numpy()
R = P[[f'rho_{sfx(d)}' for d in DATES]].to_numpy()
present, same, maj, agree_ref = sign_counts(R)
P['days_beyond_line'] = P[[f'beyond_line_{sfx(d)}' for d in DATES]].sum(axis=1).astype(int)
P['days_same_sign'] = same; P['majority_sign'] = maj; P['other_days_with_oct18_sign'] = agree_ref
P['min_abs_rho'] = np.abs(R).min(1); P['median_rho'] = np.median(R, 1); P['range_rho'] = R.max(1) - R.min(1)
P['abs_rho_1018'] = np.abs(P['rho_1018']); P['family'] = P.y.map(fam_of); P['x_group'] = P.x.map(xgroup)
P = P.sort_values(['days_same_sign', 'min_abs_rho'], ascending=[False, False]).reset_index(drop=True)
P.to_csv(f'{OUT}/t2x_coupling_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_coupling_crossday.csv', rows=len(P)))
S = dict(pairs_on_all_four_days=len(P), pairs_on_any_day=len(all_keys), pairs_not_on_all_days=len(all_keys) - len(P))
for k in (1, 2, 3, 4): S[f'pairs_same_sign_{k}_of_4'] = int((P.days_same_sign == k).sum())
for k in range(5): S[f'pairs_beyond_line_{k}_days'] = int((P.days_beyond_line == k).sum())
for k in range(4): S[f'pairs_oct18_sign_shared_by_{k}_other_days'] = int((P.other_days_with_oct18_sign == k).sum())
q = P[P.days_same_sign == 4].min_abs_rho
S.update(same4_minabs_p50=q.quantile(.5), same4_minabs_p90=q.quantile(.9), same4_minabs_p99=q.quantile(.99), same4_minabs_max=q.max(),
         same4_and_beyond_line_all4=int(((P.days_same_sign == 4) & (P.days_beyond_line == 4)).sum()), reference_distribution='none: c14 does not save shifted-Y draws; per-day lines only')
pd.DataFrame([S]).to_csv(f'{OUT}/t2x_coupling_summary.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_coupling_summary.csv', rows=1))
# per family and per condition group: counts, not means
G = P.groupby(['family', 'x_group']).agg(pairs=('x', 'size'), same_sign_4_of_4=('days_same_sign', lambda s: int((s == 4).sum())), same_sign_3_of_4=('days_same_sign', lambda s: int((s == 3).sum())),
                                        beyond_line_4_days=('days_beyond_line', lambda s: int((s == 4).sum())), beyond_line_0_days=('days_beyond_line', lambda s: int((s == 0).sum()))).reset_index()
G.to_csv(f'{OUT}/t2x_coupling_by_family_group.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_coupling_by_family_group.csv', rows=len(G)))

# ---- 2. lead-lag (c16)
L = {d: read(d, 't2_leadlag_matrix.csv') for d in DATES}
pairs = sorted(set(zip(L[REF].A, L[REF].B)))
Q = pd.DataFrame(pairs, columns=['A', 'B'])
for d in DATES:
    t = L[d].set_index(['A', 'B']).loc[pairs]
    for c in ('peak_lag_s', 'peak_rho', 'rho_lag0', 'rho_lag1', 'rho_lag_m1', 'rho_lag5'): Q[f'{c}_{sfx(d)}'] = t[c].to_numpy()
    Q[f'exceeds_band_{sfx(d)}'] = t.exceeds.astype(bool).to_numpy()
for c in ('rho_lag0', 'rho_lag1', 'rho_lag_m1', 'peak_rho'):
    M = Q[[f'{c}_{sfx(d)}' for d in DATES]].to_numpy(); _, same, maj, agree_ref = sign_counts(M)
    Q[f'days_same_sign_{c}'] = same; Q[f'majority_sign_{c}'] = maj; Q[f'min_abs_{c}'] = np.abs(M).min(1)
PL = Q[[f'peak_lag_s_{sfx(d)}' for d in DATES]].to_numpy()
Q['days_peak_lag_equal_oct18'] = (PL[:, :-1] == PL[:, [-1]]).sum(1)
Q['peak_lag_min'] = PL.min(1); Q['peak_lag_max'] = PL.max(1)
Q['days_exceeds_band'] = Q[[f'exceeds_band_{sfx(d)}' for d in DATES]].sum(axis=1).astype(int)
Q['self_pair'] = Q.A == Q.B
Q = Q.sort_values(['self_pair', 'days_same_sign_rho_lag0', 'min_abs_rho_lag0'], ascending=[True, False, False]).reset_index(drop=True)
Q.to_csv(f'{OUT}/t2x_leadlag_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_leadlag_crossday.csv', rows=len(Q)))

# ---- 3. one-second state cells (c17)
ST = {d: read(d, 't2_state_cells.csv') for d in DATES}
cells = sorted(set().union(*[set(zip(ST[d].cell, ST[d].horizon)) for d in DATES]), key=lambda k: (k[1], k[0]))
W = pd.DataFrame(cells, columns=['cell', 'horizon'])
for d in DATES:
    t = ST[d].set_index(['cell', 'horizon']).reindex(cells)
    W[f'net_{sfx(d)}'] = t.net_share.to_numpy(); W[f'support_{sfx(d)}'] = t.support.to_numpy()
    W[f'up_{sfx(d)}'] = t.up.to_numpy(); W[f'flat_{sfx(d)}'] = t.flat.to_numpy(); W[f'down_{sfx(d)}'] = t.down.to_numpy()
    W[f'z_{sfx(d)}'] = t.z.to_numpy(); W[f'median_ticks_{sfx(d)}'] = t.median_ticks.to_numpy()
    ca = t.same_sign_chunks.astype('Int64').astype(str) + '/' + t.chunks.astype('Int64').astype(str)
    W[f'chunks_agree_{sfx(d)}'] = np.where(t.support.notna(), ca, '')
M = W[[f'net_{sfx(d)}' for d in DATES]].to_numpy(); present, same, maj, agree_ref = sign_counts(M)
W['days_present'] = present; W['days_same_sign'] = same; W['majority_sign'] = maj; W['other_days_with_oct18_sign'] = agree_ref
W['min_abs_net'] = np.nanmin(np.abs(M), axis=1); W['max_abs_net'] = np.nanmax(np.abs(M), axis=1)
W[['mid_move', 'imbalance', 'flow_side']] = W.cell.str.split('|', expand=True)
W = W.sort_values(['horizon', 'days_same_sign', 'min_abs_net'], ascending=[True, False, False]).reset_index(drop=True)
W.to_csv(f'{OUT}/t2x_state_cells_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_state_cells_crossday.csv', rows=len(W)))

# ---- 4. pair couplings (c15): the top-400 tables are the only committed rows, so presence is itself a measurement
PC = {d: read(d, 't2_pair_couplings_top400.csv') for d in DATES}; PC60 = {d: read(d, 't2_pair_couplings_top60.csv') for d in DATES}
trip = sorted(set().union(*[set(zip(PC[d].x1, PC[d].x2, PC[d].y)) for d in DATES]))
V = pd.DataFrame(trip, columns=['x1', 'x2', 'y'])
for d in DATES:
    t = PC[d].copy(); t['rank'] = np.arange(1, len(t) + 1); t = t.set_index(['x1', 'x2', 'y']).reindex(trip)
    V[f'int_rho_{sfx(d)}'] = t.int_rho.to_numpy(); V[f'rank_top400_{sfx(d)}'] = t['rank'].to_numpy()
    s = PC60[d].set_index(['x1', 'x2', 'y']).reindex(trip)
    V[f'in_top60_{sfx(d)}'] = s.int_rho.notna().to_numpy(); V[f'flips_{sfx(d)}'] = s.flips.to_numpy(); V[f'chunks_agree_top60_{sfx(d)}'] = np.where(s.int_rho.notna(), s.same_sign.astype('Int64').astype(str) + '/' + s.chunks.astype('Int64').astype(str), '')
    V[f'x1_effect_x2_low_{sfx(d)}'] = s.x1_effect_when_x2_low.to_numpy(); V[f'x1_effect_x2_high_{sfx(d)}'] = s.x1_effect_when_x2_high.to_numpy()
M = V[[f'int_rho_{sfx(d)}' for d in DATES]].to_numpy(); present, same, maj, agree_ref = sign_counts(M)
V['days_in_top400'] = present; V['days_in_top60'] = V[[f'in_top60_{sfx(d)}' for d in DATES]].sum(axis=1).astype(int)
V['days_same_sign_where_listed'] = same; V['majority_sign'] = maj; V['min_abs_int_rho_where_listed'] = np.nanmin(np.abs(M), axis=1)
V['family'] = V.y.map(fam_of)
V = V.sort_values(['days_in_top400', 'days_in_top60', 'min_abs_int_rho_where_listed'], ascending=[False, False, False]).reset_index(drop=True)
V.to_csv(f'{OUT}/t2x_pair_couplings_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_pair_couplings_crossday.csv', rows=len(V)))

# ---- 5. forward-selection stack (c18)
FS = {d: read(d, 't2_forward_stack.csv') for d in DATES}
outs = sorted(set().union(*[set(FS[d].outcome) for d in DATES])); rows = []
for o in outs:
    kmax = max(int(FS[d][FS[d].outcome == o].step.max()) if (FS[d].outcome == o).any() else 0 for d in DATES)
    for k in range(1, kmax + 1):
        r = dict(outcome=o, step=k)
        for d in DATES:
            t = FS[d][(FS[d].outcome == o) & (FS[d].step == k)]
            r[f'added_{sfx(d)}'] = t.added.iloc[0] if len(t) else ''; r[f'oof_corr_{sfx(d)}'] = t.oof_corr.iloc[0] if len(t) else np.nan; r[f'gain_{sfx(d)}'] = t.gain.iloc[0] if len(t) else np.nan
        rows.append(r)
FP = pd.DataFrame(rows); FP.to_csv(f'{OUT}/t2x_forward_stack_paths.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_forward_stack_paths.csv', rows=len(FP)))
rows = []
for o in outs:
    feats = sorted(set().union(*[set(FS[d][FS[d].outcome == o].added) for d in DATES]))
    for f in feats:
        r = dict(outcome=o, feature=f, family=fam_of.get(o, ''), x_group=xgroup(f))
        for d in DATES:
            t = FS[d][(FS[d].outcome == o) & (FS[d].added == f)]
            r[f'step_{sfx(d)}'] = int(t.step.iloc[0]) if len(t) else np.nan; r[f'gain_{sfx(d)}'] = t.gain.iloc[0] if len(t) else np.nan
        r['days_selected'] = int(sum(np.isfinite(r[f'step_{sfx(d)}']) for d in DATES)); r['selected_oct18'] = bool(np.isfinite(r['step_1018']))
        rows.append(r)
FF = pd.DataFrame(rows).sort_values(['outcome', 'days_selected', 'step_1018'], ascending=[True, False, True]).reset_index(drop=True)
FF.to_csv(f'{OUT}/t2x_forward_stack_features.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_forward_stack_features.csv', rows=len(FF)))
rows = []
for o in outs:
    r = dict(outcome=o, family=fam_of.get(o, ''))
    for d in DATES:
        t = FS[d][FS[d].outcome == o].sort_values('step')
        r[f'steps_{sfx(d)}'] = int(len(t)); r[f'first_feature_{sfx(d)}'] = t.added.iloc[0] if len(t) else ''; r[f'oof_corr_step1_{sfx(d)}'] = t.oof_corr.iloc[0] if len(t) else np.nan; r[f'oof_corr_final_{sfx(d)}'] = t.oof_corr.iloc[-1] if len(t) else np.nan
    sel = [set(FS[d][FS[d].outcome == o].added) for d in DATES]; r['features_on_all_four_days'] = ' '.join(sorted(set.intersection(*sel))) if all(sel) else ''
    r['features_on_three_or_more_days'] = ' '.join(sorted(f for f in set().union(*sel) if sum(f in s for s in sel) >= 3))
    r['same_first_feature_as_oct18_days'] = int(sum(r[f'first_feature_{sfx(d)}'] == r['first_feature_1018'] for d in DATES[:-1])) if r['first_feature_1018'] else 0
    rows.append(r)
FO = pd.DataFrame(rows); FO.to_csv(f'{OUT}/t2x_forward_stack_outcomes.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_forward_stack_outcomes.csv', rows=len(FO)))


# ---- 6. shifted-Y reference for the coupling agreement counts (x16 draws, when present): draw s combines the s-th shifted matrix of each day exactly as the observed ones are combined
WORK = os.environ.get('OD_WORK', '')
NZ = {d: f'{WORK}/t2_nullrho_{d}.npz' for d in DATES}
if WORK and all(os.path.exists(p) for p in NZ.values()):
    Z = {d: np.load(NZ[d]) for d in DATES}
    for d in DATES:
        ix = {(a, b): (i, j) for i, a in enumerate(Z[d]['x']) for j, b in enumerate(Z[d]['y'])}
        obs = np.array([Z[d]['observed'][ix[(x, y)]] for x, y in zip(P.x, P.y)]); assert np.nanmax(np.abs(obs - P[f'rho_{sfx(d)}'].to_numpy())) < 1e-9, d
        Z[d] = dict(null=np.array([[m[ix[(x, y)]] for x, y in zip(P.x, P.y)] for m in Z[d]['null']]), line=float(Z[d]['line']))
    nd = []
    for s in range(Z[DATES[0]]['null'].shape[0]):
        Rn = np.column_stack([Z[d]['null'][s] for d in DATES]); pn = (Rn > 0).sum(1); nn = (Rn < 0).sum(1); same = np.maximum(pn, nn)
        beyond = np.column_stack([np.abs(Z[d]['null'][s]) > Z[d]['line'] for d in DATES]).sum(1)
        ref = Rn[:, -1]; agree = (np.sign(Rn[:, :-1]) == np.sign(ref)[:, None]).sum(1)
        row = dict(draw=s, pairs=len(P))
        for k in (2, 3, 4): row[f'same_sign_{k}_of_4'] = int((same == k).sum())
        for k in range(5): row[f'beyond_line_{k}_days'] = int((beyond == k).sum())
        for k in range(4): row[f'oct18_sign_shared_by_{k}_other_days'] = int((agree == k).sum())
        q = np.abs(Rn).min(1)[same == 4]; row.update(same4_minabs_p50=np.quantile(q, .5) if len(q) else np.nan, same4_minabs_p90=np.quantile(q, .9) if len(q) else np.nan, same4_minabs_max=q.max() if len(q) else np.nan)
        nd.append(row)
    ND = pd.DataFrame(nd); ND.to_csv(f'{OUT}/t2x_coupling_shifted_reference.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_coupling_shifted_reference.csv', rows=len(ND)))
    S['reference_distribution'] = f'{len(ND)} shifted-Y draws per day (x16, seed 11, same transform as c14), combined day by day: t2x_coupling_shifted_reference.csv'
    for c in [c for c in ND.columns if c not in ('draw', 'pairs')]: S[f'ref_{c}_mean'] = ND[c].mean(); S[f'ref_{c}_min'] = ND[c].min(); S[f'ref_{c}_max'] = ND[c].max()
    pd.DataFrame([S]).to_csv(f'{OUT}/t2x_coupling_summary.csv', index=False)

# ---- 7. full pair-coupling family on all four days (x17 output, when present): every (x1, x2, y), not only each day's top 400
PF = {d: f'{OUT}/pairs_full/t2_pair_couplings_full_{d}.csv' for d in DATES}
if all(os.path.exists(p) for p in PF.values()):
    F = {d: pd.read_csv(PF[d]) for d in DATES}
    for d in DATES: rec.append(dict(kind='input', date=d, table=f'pairs_full/t2_pair_couplings_full_{d}.csv', rows=len(F[d])))
    keys = set.intersection(*[set(zip(F[d].x1, F[d].x2, F[d].y)) for d in DATES]); anyk = set.union(*[set(zip(F[d].x1, F[d].x2, F[d].y)) for d in DATES])
    U = pd.DataFrame(sorted(keys), columns=['x1', 'x2', 'y'])
    for d in DATES:
        t = F[d].set_index(['x1', 'x2', 'y']).loc[list(zip(U.x1, U.x2, U.y))]
        U[f'int_rho_{sfx(d)}'] = t.int_rho.to_numpy(); U[f'n_{sfx(d)}'] = t.n.to_numpy().astype(int)
        U[f'chunks_agree_{sfx(d)}'] = t.same_sign_chunks.astype(int).astype(str).to_numpy() + '/' + t.chunks.astype(int).astype(str).to_numpy(); U[f'beyond_line_{sfx(d)}'] = t.exceeds_line.astype(bool).to_numpy()
    M = U[[f'int_rho_{sfx(d)}' for d in DATES]].to_numpy(); present, same, maj, agree_ref = sign_counts(M)
    U['days_beyond_line'] = U[[f'beyond_line_{sfx(d)}' for d in DATES]].sum(axis=1).astype(int); U['days_same_sign'] = same; U['majority_sign'] = maj; U['other_days_with_oct18_sign'] = agree_ref
    U['min_abs_int_rho'] = np.abs(M).min(1); U['median_int_rho'] = np.median(M, 1); U['range_int_rho'] = M.max(1) - M.min(1); U['family'] = U.y.map(fam_of).fillna('support difference')
    U = U.sort_values(['days_same_sign', 'min_abs_int_rho'], ascending=[False, False]).reset_index(drop=True)
    U.to_csv(f'{OUT}/t2x_pair_couplings_full_crossday.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_pair_couplings_full_crossday.csv', rows=len(U)))
    S2 = dict(triplets_on_all_four_days=len(U), triplets_on_any_day=len(anyk))
    for k in (1, 2, 3, 4): S2[f'same_sign_{k}_of_4'] = int((U.days_same_sign == k).sum())
    for k in range(5): S2[f'beyond_line_{k}_days'] = int((U.days_beyond_line == k).sum())
    for d in DATES: S2[f'line_{sfx(d)}'] = float(F[d].line.iloc[0]); S2[f'beyond_line_{sfx(d)}'] = int(F[d].exceeds_line.sum())
    q = U[U.days_same_sign == 4].min_abs_int_rho; S2.update(same4_minabs_p50=q.quantile(.5), same4_minabs_p90=q.quantile(.9), same4_minabs_max=q.max(), same4_and_beyond_line_all4=int(((U.days_same_sign == 4) & (U.days_beyond_line == 4)).sum()))
    pd.DataFrame([S2]).to_csv(f'{OUT}/t2x_pair_couplings_full_summary.csv', index=False); rec.append(dict(kind='output', date='all', table='t2x_pair_couplings_full_summary.csv', rows=1))

RC = pd.DataFrame(rec); RC.to_csv(f'{OUT}/t2x_receipt.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)
print(RC.to_string(index=False)); print(); print(pd.DataFrame([S]).T.to_string(header=False))
