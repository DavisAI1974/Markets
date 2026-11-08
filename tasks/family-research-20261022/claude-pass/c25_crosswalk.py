"""Crosswalk of the 99 planes and the 13 external inputs, Claude pass.  Usage: python3 -I c25_crosswalk.py
Part A (99 planes): my own classification from the registry's own fields (group, role, class, disposition), written BEFORE comparing with Codex's classes, then compared line by line.
Part B (13 inputs): per series measured on the 749 first-observed families of the Oct 18 member: coverage, distinct values, changes in family order, value against the family's traded mid (shared
  instrument overlap), clock-proxy diagnostic (rank correlation with family start order; a diagnostic, never a feature), and the rank correlation with the saved strict-pre outcomes
  (signed and absolute ticks at 5/20/60 s).  Stability: 6 contiguous chunks in family order.  Reference line: outcomes cyclically shifted in family order (300 shifts, max |rho| over all
  series x outcomes, 95%), descriptive only.  Only Oct 18 has bound external data, so nothing can be compared across days here.
Part C: shared-source checks between inputs (rank correlation between series of different points on the same families).
Ids and timestamps are used to join and to order families, never as features."""
import sys; sys.path.insert(0, '.')
from odcfg import *
import json, numpy as np, pandas as pd
from scipy.stats import rankdata, spearmanr
ROOT = f'{HERE}/..'; ART = f'{ROOT}/../../artifacts/sqlite-triage/20261022/families'; OUT = f'{HERE}/tables/crosswalk'; import os; os.makedirs(OUT, exist_ok=True)
# ------------------------------------------------------------------ Part A
pr = pd.read_csv(f'{ART}/descriptive-v1/plane_registry.csv'); B = pd.DataFrame([json.loads(x) for x in pr.body]); B['ordinal'] = pr.ordinal.to_numpy()
MARKET_G = {'full_book_fifo_queue', 'microstructure_mechanics', 'order_lifecycle'}; DERIVED_G = {'derived_geometry', 'legacy_observable_crosswalk', 'prebirth_opportunity', 'frozen_learned_structure'}
LIVE = {'exposed', 'arrived', 'thin', 'completed_only'}
def mine(r):
    if r['group'] == 'causal_clocks' or r['role'] == 'clock': return 'availability_or_provenance', 'a clock or availability entry: places observations in time, carries no market state'
    if r['role'] == 'sealed_answer': return 'outcome_or_selection_boundary', 'sealed answer or target timing: the thing predicted or the boundary of selection'
    if r['group'] in MARKET_G and r['class'] in LIVE: return 'market_mechanism_or_state', 'book, queue or order-lifecycle state or mechanism that reached the picture'
    if r['group'] == 'canonical_raw_dbn_mbo' and r['class'] in LIVE: return 'market_mechanism_or_state', 'raw exchange record that reached the picture'
    if r['group'] in DERIVED_G and r['class'] in LIVE | {'disabled', 'retired'}: return 'derived_transform_or_lifecycle_context', 'computed from raw records or learned structure; shares the raw inputs it was computed from'
    if r['class'] == 'withheld' and r['group'].startswith('current_brain'): return 'outcome_or_selection_boundary', 'withheld by role: part of what is hidden from the reader'
    return 'control_runtime_or_unresolved_context', 'control, runtime, output or entry not read by this piece; relationship to market state unresolved'
mm = B.apply(mine, axis=1, result_type='expand'); B['my_class'] = mm[0]; B['my_basis'] = mm[1]
R = pd.read_csv(f'{ROOT}/flow-book-discovery-v1/all-99-relationship-roles.csv'); X = B.merge(R[['entry_id', 'relationship_class']], left_on='entry', right_on='entry_id', how='left').drop(columns=['entry_id', 'consumer', 'reason'])
X = X.rename(columns={'relationship_class': 'codex_class'}); X['agree'] = X.my_class == X.codex_class; assert len(X) == 99 and X.codex_class.notna().all()
X[['ordinal', 'entry', 'group', 'role', 'class', 'disposition', 'my_class', 'codex_class', 'agree', 'my_basis']].to_csv(f'{OUT}/t7_plane_roles.csv', index=False)
ct = pd.crosstab(X.my_class, X.codex_class); ct.to_csv(f'{OUT}/t7_plane_class_crosstab.csv')
print('planes', len(X), 'agree', int(X.agree.sum())); print(ct.to_string()); print(X[~X.agree][['entry', 'group', 'role', 'class', 'my_class', 'codex_class']].to_string())
# ------------------------------------------------------------------ Part B
m = pd.read_csv(f'{HERE}/tables/t1_family_master.csv').sort_values('start_recv_ns').reset_index(drop=True)
E = pd.read_csv(f'{ROOT}/flow-book-discovery-v1/external-operands.csv.gz')
pts = E.groupby('feature').points.first(); W = E.pivot_table(index='instance', columns='feature', values='value', aggfunc='first')
W = W.reindex(m.instance.to_numpy()); N = len(m)
outs = {f'tk_{h}s': m[f'tk_{h}s'].to_numpy(float) for h in (5, 20, 60)}; outs.update({f'abs_tk_{h}s': np.abs(m[f'tk_{h}s'].to_numpy(float)) for h in (5, 20, 60)})
def rk(a):
    o = np.full(len(a), np.nan); k = ~np.isnan(a); o[k] = (rankdata(a[k]) - 0.5) / k.sum() - 0.5; return o
def rho(a, b):
    k = ~np.isnan(a) & ~np.isnan(b)
    if k.sum() < 30: return np.nan, int(k.sum())
    ra, rb = rankdata(a[k]), rankdata(b[k]); ra -= ra.mean(); rb -= rb.mean(); d = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return (float((ra * rb).sum() / d) if d > 0 else np.nan), int(k.sum())
order_rank = np.arange(N, dtype=float); mid = m['root.mid'].to_numpy(float); rows = []
for f in W.columns:
    v = W[f].to_numpy(float); k = ~np.isnan(v); nd = int(len(np.unique(v[k]))) if k.any() else 0
    ch = int((np.diff(v[k]) != 0).sum()) if k.sum() > 1 else 0
    r = dict(point=pts[f], series=f.replace('external:', ''), present=int(k.sum()), distinct=nd, changes_in_family_order=ch)
    if nd > 1:
        r['rho_with_family_order'], _ = rho(v, order_rank); r['rho_with_traded_mid'], _ = rho(v, mid)
        for on, y in outs.items():
            c, n_ = rho(v, y); r[f'rho_{on}'] = c; r[f'n_{on}'] = n_
            ch6 = np.minimum((np.arange(N) * 6) // N, 5); same = 0; tot = 0
            for q in range(6):
                mk = ch6 == q; ck, nk = rho(np.where(mk, v, np.nan), np.where(mk, y, np.nan))
                if nk >= 30 and not np.isnan(ck) and not np.isnan(c): tot += 1; same += int(np.sign(ck) == np.sign(c))
            r[f'chunks_same_sign_{on}'] = f'{same}/{tot}'
    rows.append(r)
S = pd.DataFrame(rows)
var = S[S.distinct > 1].series.tolist(); rng = np.random.default_rng(5); mx = []; lo = max(30, N // 10)
Vcols = {s: W['external:' + s].to_numpy(float) for s in var}
for i in range(300):
    sh = int(rng.integers(lo, N - lo)); mm_ = 0.0
    for s in var:
        for on, y in outs.items():
            c, _ = rho(Vcols[s], np.roll(y, sh)); mm_ = max(mm_, abs(c) if not np.isnan(c) else 0)
    mx.append(mm_)
line = float(np.quantile(mx, .95)); S['null95_line_family_wise'] = line; S.to_csv(f'{OUT}/t7_input_series_measurements.csv', index=False)
print('series', len(S), 'variable', len(var), 'null95 %.3f' % line)
# ------------------------------------------------------------------ Part C: shared-source checks across points
def first_var(point_pat, contains=None):
    c = S[(S.point.str.contains(point_pat, regex=False)) & (S.distinct > 1)]
    if contains: c = c[c.series.str.contains(contains)]
    return c.series.tolist()
pairs = []
for a, b, why in (('[5, 7]', '[5, 7]', 'same eia930.us48 table: wind_mwh vs est_gas_burn_bcfd_rate'), ('[2]', '[9]', 'forecast gw_hdd vs disagreement summary derived from the same model runs'), ('[2]', '[10]', 'forecast vs observed gw_hdd (same quantity, two measurements)')):
    sa = first_var(a); sb = first_var(b)
    for x in sa:
        for y in sb:
            if x == y: continue
            c, n_ = rho(Vcols[x], Vcols[y]); pairs.append(dict(check=why, series_a=x, series_b=y, rho=c, n=n_))
Pc = pd.DataFrame(pairs); Pc.to_csv(f'{OUT}/t7_shared_source_checks.csv', index=False); print(Pc.to_string() if len(Pc) < 40 else Pc.describe())
