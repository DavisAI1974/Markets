"""Dipole cohort, step 2: the 863 archived Native candidates on my reconstructed books, conditions-only, with matched controls.
Usage: python3 -I c24b_dipole_cohort.py   (run c24a_cohort_cuts.py and c12 with OD_CUTS first)

What is measured (all midpoint changes in ticks of 0.001, oriented by the candidate's birth polarity, +1 buy / -1 sell):
  retro   : mid at the recognition close minus mid at the last group closed before the birth second (retrospective, ends when the candidate becomes visible)
  fwd h   : mid at the last group closed by recognition + h seconds minus mid at the recognition close (h = 1, 5, 20, 60).  Recognition clock, not the nominal clock.
  nominal : mid at the last group closed by the nominal emission second start + h minus mid at the last group before that second (shown beside fwd h; it starts before the candidate was recognized).
Conditions at the strict prebirth cutoff (birth second start minus 1 ns) come from the same feature code as the dense grid (c12 with explicit cutoffs).
Ids, birth seconds, cursors and clocks are provenance: they place the cutoff and join to Codex's tables, never enter a statistic.  Polarity is a recognition-time label.
Controls: for every candidate, a row of the same tape (3 s grid for the retrospective move, random group closes for forward moves since a recognition is a group close) in the same spread regime and the same activity quintile (regime-internal, same formula as c19), 500 draws;
the same oriented statistic is computed on each draw.  The full distribution of draws is saved; no cut is applied.
Outputs: tables/dipole/t6_cohort_features.csv, t6_cohort_cells.csv, t6_cohort_controls.csv, t6_cohort_control_draws.npz(workdir), t6_cohort_vs_codex.csv, t6_cohort_rank_hist.csv"""
import sys; sys.path.insert(0, '.')
from odcfg import *
import gzip, json, numpy as np, pandas as pd
S = 10**9; NDRAW = 500; HZ = (1, 5, 20, 60)
rows = [json.loads(l) for l in gzip.open(f'{HERE}/../october18-candidate-inputs.jsonl.gz', 'rt')]
cov = pd.read_csv(f'{HERE}/tables/dipole/t6_cohort_coverage.csv')
A = pd.read_csv(f'{HERE}/../flow-book-discovery-v1/dipole-after-recognition.csv.gz')
EV = pd.read_csv(f'{HERE}/../research-atlas-v2/dipole-weakening-events.csv').set_index('candidate_id')
def half(x): return np.round(np.asarray(x, float) * 2) / 2
def cat(x): x = np.asarray(x, float); return np.where(x > 0, 'in', np.where(x < 0, 'opp', 'flat'))
# ---------------------------------------------------------------- cohort table
feat_keep = ['spr', 'mid', 'bsz', 'asz', 'bn', 'an', 'tch_imb', 'tchn_imb', 'near5_imb', 'near10_imb', 'ntr_1', 'ntr_5', 'ntr_20', 'ntr_60', 'net_1', 'net_5', 'net_20', 'net_60', 'imb_1', 'imb_5', 'imb_20', 'imb_60',
             'supdiff_5', 'supdiff_20', 'supdiff_60', 'sup_b_20', 'sup_a_20', 'prior_1', 'prior_5', 'prior_20', 'prior_60', 'prior_300', 'qchg_5', 'qchg_20', 'qchg_60', 'qchg_300', 'age_s', 'qage_s', 'closed']
parts = []
for d in ('20231017', '20231018'):
    c = cov[cov.tape == d].reset_index(drop=True)
    if not len(c): continue
    P = pd.read_parquet(f'{WORK}/cohort_grid_{d}_pre.parquet'); R = pd.read_parquet(f'{WORK}/cohort_grid_{d}_rec.parquet'); assert len(P) == len(R) == len(c)
    assert (P.cut_ns.to_numpy() == c.pre_ns.to_numpy()).all() and (R.cut_ns.to_numpy() == c.rec_ns.to_numpy()).all()
    z = np.load(groups(d)); gr = z['recv_ns']; gmid = (z['bid_px'] + z['ask_px']) / 2e6          # ticks
    t = pd.DataFrame({'row': c.row, 'tape': d})
    for k in feat_keep: t['pre_' + k] = P[k].to_numpy()
    t['rec_spr'] = R.spr.to_numpy(); t['rec_mid'] = R.mid.to_numpy(); t['rec_ntr_20'] = R.ntr_20.to_numpy(); t['rec_ntr_60'] = R.ntr_60.to_numpy(); t['rec_qchg_60'] = R.qchg_60.to_numpy()
    t['rec_buy_20'] = R.buy_20.to_numpy(); t['rec_sell_20'] = R.sell_20.to_numpy(); t['rec_imb_20'] = R.imb_20.to_numpy(); t['rec_age_s'] = R.age_s.to_numpy()
    for h in HZ: t[f'fwd_{h}'] = half(R[f'dm_{h}'].to_numpy())
    av = np.array([rows[k]['available_second'] * S - 1 for k in c.row])      # nominal emission second start (minus 1 ns): the clock a nominal-bin reading would use
    gi_av = np.searchsorted(gr, av, side='right') - 1
    for h in HZ:
        j = np.minimum(np.searchsorted(gr, av + 1 + h * S, side='right') - 1, len(gr) - 1); t[f'nom_{h}'] = half(gmid[j] - gmid[gi_av])
    t['retro'] = half(R.mid.to_numpy() - P.mid.to_numpy()); parts.append(t)
F = pd.concat(parts, ignore_index=True)
meta = pd.DataFrame([dict(row=k, prov_candidate_id=r['candidate_id'], prov_birth_second=r['birth_second'], prov_recognition_ns=r['recognition_receive_ns'], prov_codex_recognition_cursor=r['recognition_cursor'],
                          polarity=int(r['recorded_operands']['polarity']), orient=r['recognition_orientation'], codex_flow_state=r['birth_to_emission_flow_state'], codex_depth=r['prebirth_displayed_depth_relative_to_birth_flow'],
                          codex_quote_move=r['quote_move_relative_to_birth_polarity'], delay_s=(r['recognition_receive_ns'] - r['birth_second'] * S) / S, emit_delay_s=(r['recognition_receive_ns'] - r['available_second'] * S) / S, avail_minus_birth_s=r['available_second'] - r['birth_second']) for k, r in enumerate(rows)])
F = F.merge(meta, on='row', how='left'); p = F.polarity.to_numpy()
F['pre_regime'] = np.where(F.pre_spr <= 0, 'lockcross', np.where(F.pre_spr == 1, '1', np.where(F.pre_spr == 2, '2', '3+')))
F['rec_regime'] = np.where(F.rec_spr <= 0, 'lockcross', np.where(F.rec_spr == 1, '1', np.where(F.rec_spr == 2, '2', '3+')))
F['retro_o'] = p * F.retro
for h in HZ: F[f'fwd_{h}_o'] = p * F[f'fwd_{h}']; F[f'nom_{h}_o'] = p * F[f'nom_{h}']
d_sz = np.sign(F.pre_bsz - F.pre_asz); F['depth_mine'] = np.where(d_sz == 0, 'equal', np.where(d_sz == p, 'aligned', 'opposed'))
F['delay_bin'] = pd.qcut(F.emit_delay_s.rank(method='first'), 3, labels=['fastest third', 'middle third', 'slowest third'])
F['retro_cat'] = cat(F.retro_o)
for h in HZ: F[f'fwd_{h}_cat'] = cat(F[f'fwd_{h}_o']); F[f'nom_{h}_cat'] = cat(F[f'nom_{h}_o'])
# ---------------------------------------------------------------- agreement with Codex (labels and horizons)
ag = []
cx = {'same': 'in', 'opposite': 'opp', 'flat': 'flat'}
m = pd.crosstab(F.retro_cat, F.codex_quote_move.map(cx))
ag.append(dict(item='birth-to-recognition move direction, mine vs Codex label', covered=len(F), agree=int(sum(m.loc[k, k] for k in m.index if k in m.columns)), disagree=len(F) - int(sum(m.loc[k, k] for k in m.index if k in m.columns))))
dm = {'aligned': 'aligned', 'opposed': 'opposed', 'balanced': 'equal'}
ag.append(dict(item='prebirth displayed depth vs birth direction, mine vs Codex label', covered=len(F), agree=int((F.depth_mine == F.codex_depth.map(dm)).sum()), disagree=int((F.depth_mine != F.codex_depth.map(dm)).sum())))
for h in HZ:
    a = A[A.horizon_s == h].set_index('candidate_id'); a = a.loc[F.prov_candidate_id]; mask = (a.disposition == 'available').to_numpy()
    cc = cat(half(a.change.to_numpy() / 0.001) * F.polarity.to_numpy())
    ag.append(dict(item=f'forward +{h}s from recognition, direction, mine vs Codex (Codex available rows)', covered=int(mask.sum()), agree=int((cc[mask] == F[f'fwd_{h}_cat'].to_numpy()[mask]).sum()), disagree=int((cc[mask] != F[f'fwd_{h}_cat'].to_numpy()[mask]).sum())))
# Codex flow state: mine (wire-side aggressor lots over the trailing 20 s at the recognition close) vs Codex (price-vs-prior-midpoint class, rolling 20 s)
a1 = A[A.horizon_s == 1].set_index('candidate_id').loc[F.prov_candidate_id]; F['codex_roll20'] = a1.recognition_roll20.to_numpy()
mine_sign = np.sign(F.rec_imb_20.fillna(0).to_numpy() * p); codex_sign = np.sign(np.nan_to_num(F.codex_roll20.to_numpy()) * p)
flow_x = pd.crosstab(pd.Series(np.where(mine_sign > 0, 'same as birth', np.where(mine_sign < 0, 'opposite', 'none/balanced')), name='mine: wire-side lots'),
                     pd.Series(np.where(codex_sign > 0, 'same as birth', np.where(codex_sign < 0, 'opposite', 'undefined/balanced')), name='Codex: price-class lots'))
flow_x.to_csv(f'{HERE}/tables/dipole/t6_flow_definition_crosstab.csv')
pd.DataFrame(ag).to_csv(f'{HERE}/tables/dipole/t6_cohort_vs_codex.csv', index=False)
# ---------------------------------------------------------------- matched controls
def act_pct(pool, x):          # activity score: sum of percentile ranks of ntr_60, qchg_60, ntr_20 against the pool distribution of that regime
    s = np.zeros(len(x))
    for col, xc in (('ntr_60', 'ntr_60'), ('qchg_60', 'qchg_60'), ('ntr_20', 'ntr_20')):
        ref = np.sort(pool[col].to_numpy(float)); v = x[xc].to_numpy(float)
        s += (np.searchsorted(ref, v, side='left') + np.searchsorted(ref, v, side='right')) / 2 / len(ref)
    return s
rng = np.random.default_rng(7); draws = {}; ctrl_rows = []
def stat(v):
    return dict(in_share=float(np.mean(v > 0)), opp_share=float(np.mean(v < 0)), flat_share=float(np.mean(v == 0)), mean_ticks=float(np.mean(v)), n=int(len(v)))
for d in ('20231017', '20231018'):
    sub = F[F.tape == d]
    if not len(sub): continue
    z = np.load(groups(d)); gr = z['recv_ns']; gmid = (z['bid_px'] + z['ask_px']) / 2e6
    for kind in ('retro', 'fwd'):
        G = pd.read_parquet(big(d, 'grid') if kind == 'retro' else f'{WORK}/gc_grid_{d}.parquet'); G = G[(~G.closed) & (G.spr > 0)].reset_index(drop=True)   # retro: 3 s grid; fwd: random group closes
        greg = np.where(G.spr == 1, '1', np.where(G.spr == 2, '2', '3+'))
        cutkey = 'pre' if kind == 'retro' else 'rec'
        regs = sub[f'{cutkey}_regime'].to_numpy()
        # cohort covariates at the right cut
        cx_ = pd.DataFrame({'ntr_60': sub[f'{cutkey}_ntr_60'].to_numpy(), 'qchg_60': sub[f'{cutkey}_qchg_60'].to_numpy(), 'ntr_20': sub[f'{cutkey}_ntr_20'].to_numpy()})
        qc = np.full(len(sub), -1)
        pools = {}
        for r in ('1', '2', '3+'):
            pool = G[greg == r].reset_index(drop=True); a_pool = act_pct(pool, pool); edges = np.quantile(a_pool, [.2, .4, .6, .8])
            pq = np.searchsorted(edges, a_pool, side='right'); pools[r] = (pool, pq)
            mk = regs == r
            if mk.any(): qc[mk] = np.searchsorted(edges, act_pct(pool, cx_[mk]), side='right')
        pol = sub.polarity.to_numpy(); delta = (sub.prov_recognition_ns.to_numpy() - (sub.prov_birth_second.to_numpy() * S - 1))
        res = {h: np.full((NDRAW, len(sub)), np.nan) for h in ((0,) if kind == 'retro' else HZ)}
        for r in ('1', '2', '3+'):
            pool, pq = pools[r]
            for q in range(5):
                mem = np.where((regs == r) & (qc == q))[0]; cand = np.where(pq == q)[0]
                if not len(mem) or not len(cand): continue
                pick = cand[rng.integers(0, len(cand), size=(NDRAW, len(mem)))]
                if kind == 'retro':
                    c0 = pool.cut_ns.to_numpy()[pick]; c1 = c0 + delta[mem][None, :]
                    i0 = np.searchsorted(gr, c0, side='right') - 1; i1 = np.minimum(np.searchsorted(gr, c1, side='right') - 1, len(gr) - 1)
                    res[0][:, mem] = pol[mem][None, :] * half(gmid[i1] - gmid[i0])
                else:
                    for h in HZ: res[h][:, mem] = pol[mem][None, :] * half(pool[f'dm_{h}'].to_numpy()[pick])
        for h, M in res.items():
            draws[(d, kind, h)] = M; ok = ~np.isnan(M[0]); assert ok.sum() == len(sub) - int((qc < 0).sum()), (d, kind, h, ok.sum())
cell_rows = []; DS = {}
# ---------------------------------------------------------------- cohort vs controls (whole cohort, and by regime at the matching cut)
def pooled(kind, h, mask_by_tape):
    out = []
    for d in ('20231017', '20231018'):
        k = (d, kind, h)
        if k in draws: sub = F[F.tape == d]; mk = mask_by_tape(sub); out.append(draws[k][:, mk.to_numpy() & ~np.isnan(draws[k][0])])
    return np.concatenate(out, axis=1) if out else np.empty((NDRAW, 0))
for kind, hs in (('retro', (0,)), ('fwd', HZ)):
    cutkey = 'pre' if kind == 'retro' else 'rec'
    for h in hs:
        col = 'retro_o' if kind == 'retro' else f'fwd_{h}_o'
        for reg in ('all', '1', '2', '3+'):
            mk = (lambda s, reg=reg, ck=cutkey: (s[f'{ck}_regime'] != 'lockcross') if reg == 'all' else (s[f'{ck}_regime'] == reg))
            M = pooled(kind, h, mk)
            if M.shape[1] == 0: continue
            coh = F[mk(F)]; v = coh[col].to_numpy(); cs = stat(v)
            ds = np.array([[np.mean(M[i] > 0), np.mean(M[i] < 0), np.mean(M[i] == 0), np.mean(M[i])] for i in range(NDRAW)])
            row = dict(measure='birth-to-recognition' if kind == 'retro' else f'+{h}s from recognition', regime_at_cut=reg, cohort_n=cs['n'], cohort_in=cs['in_share'], cohort_opp=cs['opp_share'], cohort_flat=cs['flat_share'], cohort_mean_ticks=cs['mean_ticks'], draws=NDRAW)
            for j, nm in enumerate(('in', 'opp', 'flat', 'mean_ticks')):
                row[f'ctrl_{nm}_p2.5'] = float(np.quantile(ds[:, j], .025)); row[f'ctrl_{nm}_median'] = float(np.median(ds[:, j])); row[f'ctrl_{nm}_p97.5'] = float(np.quantile(ds[:, j], .975))
                row[f'cohort_{nm}_rank_in_draws'] = float(np.mean(ds[:, j] < (cs[{'in': 'in_share', 'opp': 'opp_share', 'flat': 'flat_share', 'mean_ticks': 'mean_ticks'}[nm]])))
            ctrl_rows.append(row); DS[(row['measure'], reg)] = ds
np.savez_compressed(f'{WORK}/cohort_draw_stats.npz', **{f'{k[0]}|{k[1]}': v for k, v in DS.items()})
CT = pd.DataFrame(ctrl_rows); CT.to_csv(f'{HERE}/tables/dipole/t6_cohort_controls.csv', index=False)
np.savez_compressed(f'{WORK}/cohort_control_draws.npz', **{f'{d}_{k}_{h}': v for (d, k, h), v in draws.items()})
# ---------------------------------------------------------------- cells: counts by dimension (alternatives and inverse paths stay in every denominator)
def cells(dim, col, label):
    for val, g in F.groupby(col, observed=True):
        r = dict(dimension=label, cell=str(val), n=len(g))
        for nm, cc in (('retro', 'retro_cat'),) + tuple((f'fwd{h}', f'fwd_{h}_cat') for h in HZ) + tuple((f'nom{h}', f'nom_{h}_cat') for h in HZ):
            vc = g[cc].value_counts(); r[f'{nm}_in'] = int(vc.get('in', 0)); r[f'{nm}_opp'] = int(vc.get('opp', 0)); r[f'{nm}_flat'] = int(vc.get('flat', 0))
        r['retro_mean_ticks'] = float(g.retro_o.mean())
        for h in HZ: r[f'fwd{h}_mean_ticks'] = float(g[f'fwd_{h}_o'].mean())
        cell_rows.append(r)
F['all'] = 'all covered'; F['regime_pre_label'] = F.pre_regime
cells('all', 'all', 'all covered'); cells('pre', 'regime_pre_label', 'spread regime at prebirth cutoff'); cells('o', 'orient', 'orientation to previous candidate (SAME/FLIP)')
cells('f', 'codex_flow_state', 'Codex flow state at recognition'); cells('d', 'depth_mine', 'prebirth displayed depth vs birth direction (mine)'); cells('dl', 'delay_bin', 'recognition delay')
F['pol_lab'] = np.where(F.polarity > 0, 'buy birth', 'sell birth'); cells('p', 'pol_lab', 'birth direction')
CE = pd.DataFrame(cell_rows); CE.to_csv(f'{HERE}/tables/dipole/t6_cohort_cells.csv', index=False)
# ---------------------------------------------------------------- where does the cohort's prebirth state sit in the same-regime grid distribution
rank_rows = []
sym = {'imb_20': 1, 'imb_60': 1, 'tch_imb': 1, 'near5_imb': 1, 'supdiff_20': 1, 'prior_20': 1, 'prior_60': 1}
plain = ['ntr_20', 'ntr_60', 'qchg_60', 'qchg_300', 'qage_s', 'age_s', 'bn', 'an']
for feat in list(sym) + plain:
    ranks = []
    for d in ('20231017', '20231018'):
        sub = F[(F.tape == d) & (F.pre_regime != 'lockcross')]
        if not len(sub): continue
        G = pd.read_parquet(big(d, 'grid')); G = G[(~G.closed) & (G.spr > 0)]
        greg = np.where(G.spr == 1, '1', np.where(G.spr == 2, '2', '3+'))
        for r in ('1', '2', '3+'):
            pool = G[greg == r][feat].to_numpy(float); pool = pool[~np.isnan(pool)]; mk = sub.pre_regime == r
            if not mk.any() or not len(pool): continue
            x = sub.loc[mk, 'pre_' + feat].to_numpy(float) * (sub.loc[mk, 'polarity'].to_numpy() if feat in sym else 1)
            ref = np.sort(np.concatenate([pool, -pool]) if feat in sym else pool); ok = ~np.isnan(x)
            ranks.append((np.searchsorted(ref, x[ok], side='left') + np.searchsorted(ref, x[ok], side='right')) / 2 / len(ref))
    rk = np.concatenate(ranks); cnt, _ = np.histogram(rk, bins=np.linspace(0, 1, 11))
    rank_rows.append(dict(condition=feat, polarity_signed=feat in sym, n=int(len(rk)), **{f'bin{i}': int(c) for i, c in enumerate(cnt)}))
sg_rows = []
for feat in sym:
    cp = cn = cz = 0; pp = pn = pz = 0.0; ncoh = 0
    for d in ('20231017', '20231018'):
        sub = F[(F.tape == d) & (F.pre_regime != 'lockcross')]
        if not len(sub): continue
        G = pd.read_parquet(big(d, 'grid')); G = G[(~G.closed) & (G.spr > 0)]; greg = np.where(G.spr == 1, '1', np.where(G.spr == 2, '2', '3+'))
        for r in ('1', '2', '3+'):
            pool = G[greg == r][feat].to_numpy(float); pool = pool[~np.isnan(pool)]; mk = sub.pre_regime == r
            if not mk.any() or not len(pool): continue
            x = sub.loc[mk, 'pre_' + feat].to_numpy(float) * sub.loc[mk, 'polarity'].to_numpy(); x = x[~np.isnan(x)]
            cp += int((x > 0).sum()); cn += int((x < 0).sum()); cz += int((x == 0).sum()); ncoh += len(x)
            zf = float(np.mean(pool == 0)); pp += len(x) * (1 - zf) / 2; pn += len(x) * (1 - zf) / 2; pz += len(x) * zf
    sg_rows.append(dict(condition=feat, defined_n=ncoh, cohort_toward_birth=cp, cohort_against_birth=cn, cohort_zero=cz, expected_toward=pp, expected_against=pn, expected_zero=pz))
pd.DataFrame(sg_rows).to_csv(f'{HERE}/tables/dipole/t6_cohort_signed_conditions.csv', index=False)
RH = pd.DataFrame(rank_rows); RH.to_csv(f'{HERE}/tables/dipole/t6_cohort_rank_hist.csv', index=False)
F.drop(columns=['all', 'regime_pre_label', 'pol_lab']).to_csv(f'{HERE}/tables/dipole/t6_cohort_features.csv', index=False)
# ---------------------------------------------------------------- receipts
rec = dict(candidates=len(rows), covered=len(F), uncovered_seam_or_warmup=int((cov.tape == 'none').sum()), tape_17=int((F.tape == '20231017').sum()), tape_18=int((F.tape == '20231018').sum()),
           pre_lockcross=int((F.pre_regime == 'lockcross').sum()), rec_lockcross=int((F.rec_regime == 'lockcross').sum()), pre_regime_counts=F.pre_regime.value_counts().to_dict(), orient=F.orient.value_counts().to_dict(),
           delay_median_s=float(F.delay_s.median()), delay_max_s=float(F.delay_s.max()), draws=NDRAW)
assert rec['covered'] + rec['uncovered_seam_or_warmup'] == rec['candidates']
json.dump(rec, open(f'{HERE}/tables/dipole/t6_cohort_receipt.json', 'w'), indent=1, default=str); print(json.dumps(rec, indent=1, default=str))
print(pd.DataFrame(ag).to_string()); print(flow_x.to_string())
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print(CT[['measure', 'regime_at_cut' if 'regime_at_cut' in CT else 'regime_at_cut', 'cohort_n', 'cohort_in', 'cohort_opp', 'cohort_flat', 'cohort_mean_ticks', 'ctrl_in_p2.5', 'ctrl_in_median', 'ctrl_in_p97.5', 'ctrl_mean_ticks_median']].round(3).to_string())
