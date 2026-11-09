"""Second-by-second birth-aligned paths for the archived Native dipole candidates, with matched controls.
Usage: OD_SESS=<session> python3 -I x03_birth_paths.py

Anchors and axes
  birth axis       anchor = pre cutoff (the nanosecond before the birth second starts).  Boundaries b_k = anchor + k s, k = -60 .. +160.
                   Second k is the interval (b_k, b_k+1]; second 0 is the birth second.
  recognition axis anchor = recognition receive time.  Boundaries k = -100 .. +60.
State at a boundary = the book after the last COMPLETED GROUP closed by that boundary (same as every other script in this folder).
Per-second flow/book sums = records of the groups closed in (b_k, b_k+1], so consecutive seconds partition the records with no gaps or overlaps.
Orientation: p = birth polarity (+1 buy, -1 sell).  'tgt' side = the side the birth direction would trade against (ask for p=+1, bid for p=-1); 'own' = the other side.
  mid_o      = p * (mid_k - mid at the anchor), ticks of 0.001
  with/against lots = aggressor lots in the birth direction / opposite
  book classes at tgt/own: adds at touch / near (1-4 ticks) / far (5+), fills, fill-linked removals, unlinked cancels at touch / near / far, touch modifies (same classes as c12)
Controls: for each candidate, one anchor per draw from a pool of the same tape, same spread regime and same activity quintile (ntr_60, qchg_60, ntr_20 percentile sum),
  carrying the candidate's polarity.  Birth axis: 3 s grid anchors; recognition axis: random group-close anchors.  500 draws.
Outputs: tables/dipole/<SESS>/x03_*.csv(.gz); full cohort matrices in WORK/<SESS>/x03_cohort_*.npz; draw statistics in WORK/<SESS>/x03_draws_*.npz."""
import sys; sys.path.insert(0, '.')
from odcfg import *
import gzip, json, time, numpy as np, pandas as pd
from c04_order_features import enrich, Windows
S = 10**9; NDRAW = int(os.environ.get('X03_DRAWS', 500))
AXES = {'birth': np.arange(-60, 161), 'rec': np.arange(-100, 61)}
PCT = [5, 25, 50, 75, 95]
CLS = ['add_touch', 'add_near', 'add_far', 'fill', 'rm_fill', 'rm_cx_touch', 'rm_cx_near', 'rm_cx_far', 'mod_touch']
STATE_VARS = ['mid_o', 'spr', 'tgt_sz', 'own_sz', 'tgt_n', 'own_n', 'tgt_near5', 'own_near5']
BIN_VARS = ['with_lots', 'against_lots', 'n_trades'] + [f'{s}_{c}' for s in ('tgt', 'own') for c in CLS]

rows = [json.loads(l) for l in gzip.open(CAND, 'rt')]
F = pd.read_csv(f'{TABD}/t6_cohort_features.csv', dtype={'tape': str}); cov = pd.read_csv(f'{TABD}/t6_cohort_coverage.csv', dtype={'tape': str}).set_index('row')
F['pre_ns'] = cov.loc[F.row, 'pre_ns'].to_numpy(); F['rec_ns'] = cov.loc[F.row, 'rec_ns'].to_numpy()
F['pol'] = [int(rows[k]['recorded_operands']['polarity']) for k in F.row]
F['pre_regime'] = np.where(F.pre_spr <= 0, 'lockcross', np.where(F.pre_spr == 1, '1', np.where(F.pre_spr == 2, '2', '3+')))
F['rec_regime'] = np.where(F.rec_spr <= 0, 'lockcross', np.where(F.rec_spr == 1, '1', np.where(F.rec_spr == 2, '2', '3+')))

class Tape:
    def __init__(self, d):
        t0 = time.time(); self.d = d; R, C = enrich(pd.read_parquet(recon(d))); self.W = Windows(R, C)
        self.bb = R.bb_a.to_numpy().astype(np.int64); self.ba = R.ba_a.to_numpy().astype(np.int64)
        self.bsz = R.bsz_a.to_numpy().astype(np.float32); self.asz = R.asz_a.to_numpy().astype(np.float32)
        self.bn = R.bn_a.to_numpy().astype(np.float32); self.an = R.an_a.to_numpy().astype(np.float32)
        self.nb5 = R.near_bid5.to_numpy().astype(np.float32); self.na5 = R.near_ask5.to_numpy().astype(np.float32)
        self.ci = {c: i for i, c in enumerate(self.W.cols)}; self.last_end = int(self.W.last_ts[-1])
        print(d, 'loaded', len(R), 'records', round(time.time() - t0, 1), 's', flush=True)
    def paths(self, anchor, pol, ks):
        """anchor (n,) ns; pol (n,) +-1; returns dict var -> (n, K) state or (n, K-1) bins as float32; NaN where the boundary is past the last completed group"""
        n = len(anchor); K = len(ks); B = anchor[:, None] + ks[None, :] * S
        j = np.searchsorted(self.W.last_ts, B.ravel(), side='right') - 1
        E = np.where(j >= 0, self.W.last_idx[np.maximum(j, 0)], -1).reshape(n, K); bad = (B > self.last_end) | (E < 0); Ec = np.maximum(E, 0)
        p = pol[:, None]; buy = p > 0; out = {}
        mid = (self.bb[Ec] + self.ba[Ec]) / 2.0; k0 = int(np.where(ks == 0)[0][0])
        out['mid_o'] = (p * (mid - mid[:, [k0]])).astype(np.float32); out['spr'] = (self.ba[Ec] - self.bb[Ec]).astype(np.float32)
        out['tgt_sz'] = np.where(buy, self.asz[Ec], self.bsz[Ec]); out['own_sz'] = np.where(buy, self.bsz[Ec], self.asz[Ec])
        out['tgt_n'] = np.where(buy, self.an[Ec], self.bn[Ec]); out['own_n'] = np.where(buy, self.bn[Ec], self.an[Ec])
        out['tgt_near5'] = np.where(buy, self.na5[Ec], self.nb5[Ec]); out['own_near5'] = np.where(buy, self.nb5[Ec], self.na5[Ec])
        for v in STATE_VARS: out[v] = np.where(bad, np.nan, out[v]).astype(np.float32)
        def seg(col):
            c = self.W.cum[self.ci[col]][E + 1]; return np.diff(c, axis=1).astype(np.float32)
        badb = bad[:, 1:] | bad[:, :-1]
        out['with_lots'] = np.where(buy[:, :1], seg('trade_buyagg'), seg('trade_sellagg')); out['against_lots'] = np.where(buy[:, :1], seg('trade_sellagg'), seg('trade_buyagg')); out['n_trades'] = seg('n_trade')
        for c in CLS:
            a, b = seg(f'{c}_a'), seg(f'{c}_b'); out[f'tgt_{c}'] = np.where(buy[:, :1], a, b); out[f'own_{c}'] = np.where(buy[:, :1], b, a)
        for v in BIN_VARS: out[v] = np.where(badb, np.nan, out[v]).astype(np.float32)
        return out

def stats(P):
    """P: var -> (n, K).  Returns var -> (K, 8): p5 p25 p50 p75 p95, share>0, share<0, n_valid"""
    o = {}
    for v, a in P.items():
        ok = ~np.isnan(a); nv = ok.sum(0); q = np.nanpercentile(a, PCT, axis=0) if nv.max() > 0 else np.full((5, a.shape[1]), np.nan)
        pos = np.where(nv > 0, np.nansum(a > 0, 0) / np.maximum(nv, 1), np.nan); neg = np.where(nv > 0, np.nansum(a < 0, 0) / np.maximum(nv, 1), np.nan)
        o[v] = np.vstack([q, pos, neg, nv]).T.astype(np.float32)
    return o

def first_move(mid_o, ks):
    """for each candidate/anchor: seconds after the anchor of the first boundary with mid_o != 0 (k>=1), sign; counted into bins k=1..max, plus 'none' as last bin"""
    k0 = int(np.where(ks == 0)[0][0]); m = mid_o[:, k0 + 1:]; nz = (m != 0) & ~np.isnan(m); has = nz.any(1); first = np.where(has, nz.argmax(1), -1)
    sg = np.where(has, np.sign(m[np.arange(len(m)), np.maximum(first, 0)]), 0); return first, sg

def fm_hist(first, sg):
    """(2, 161): row 0 = first move oriented positive, row 1 = oriented negative, columns = boundary k=1..160 (index 0..159); index 160 = never moved (counted in row 0)"""
    h = np.zeros((2, 161), np.int64)
    for si, sv in enumerate((1, -1)):
        m = (sg == sv) & (first >= 0); h[si, :160] = np.bincount(np.minimum(first[m], 159), minlength=160)[:160]
    h[0, 160] = int((first < 0).sum()); return h

def act_pct(pool, x):
    s = np.zeros(len(x))
    for col in ('ntr_60', 'qchg_60', 'ntr_20'):
        ref = np.sort(pool[col].to_numpy(float)); v = x[col].to_numpy(float); s += (np.searchsorted(ref, v, side='left') + np.searchsorted(ref, v, side='right')) / 2 / len(ref)
    return s

tapes = {d: Tape(d) for d in TAPES if (F.tape == d).any()}
Fs = pd.concat([F[F.tape == d] for d in tapes], ignore_index=True)   # candidate order = tape order
N = len(Fs); print('candidates', N, flush=True)
# ------------------------------------------------------------------ cohort
cohort = {}
for ax, ks in AXES.items():
    anchor_col = 'pre_ns' if ax == 'birth' else 'rec_ns'; parts = []
    for d, T in tapes.items():
        s = Fs[Fs.tape == d]; parts.append(T.paths(s[anchor_col].to_numpy(np.int64), s.pol.to_numpy(), ks))
    cohort[ax] = {v: np.vstack([q[v] for q in parts]) for v in parts[0]}
    np.savez_compressed(f'{CW}/x03_cohort_{ax}.npz', ks=ks, row=Fs.row.to_numpy(), pol=Fs.pol.to_numpy(), **cohort[ax])
cst = {ax: stats(cohort[ax]) for ax in AXES}
# ------------------------------------------------------------------ matched control pools
pools = {}
for d, T in tapes.items():
    z = np.load(groups(d)); r = z['recv_ns']
    for ax, src in (('birth', big(d, 'grid')), ('rec', f'{WORK}/gc_grid_{d}.parquet')):
        G = pd.read_parquet(src, columns=['cut_ns', 'spr', 'ntr_60', 'qchg_60', 'ntr_20', 'closed'])
        lo = r[0] + 600 * S + (60 if ax == 'birth' else 100) * S; hi = r[-1] - 160 * S
        G = G[(~G.closed) & (G.spr > 0) & (G.cut_ns >= lo) & (G.cut_ns <= hi)].reset_index(drop=True)
        reg = np.where(G.spr == 1, '1', np.where(G.spr == 2, '2', '3+')); pp = {}
        for rg in ('1', '2', '3+'):
            pl = G[reg == rg].reset_index(drop=True); a = act_pct(pl, pl); ed = np.quantile(a, [.2, .4, .6, .8]); qq = np.searchsorted(ed, a, side='right')
            pp[rg] = (pl, ed, [np.where(qq == i)[0] for i in range(5)])
        pools[(d, ax)] = pp
        print(d, ax, 'pool', len(G), flush=True)
rng = np.random.default_rng(11)
draw = {ax: {v: np.zeros((NDRAW, len(AXES[ax]) - (0 if v in STATE_VARS else 1), 8), np.float32) for v in STATE_VARS + BIN_VARS} for ax in AXES}
fm = {ax: np.zeros((NDRAW, 2, 161), np.int32) for ax in AXES}
t0 = time.time()
# precompute for each tape/axis the candidate pool index lists
plan = {}
for d, T in tapes.items():
    s = Fs[Fs.tape == d]
    for ax in AXES:
        pre = 'pre' if ax == 'birth' else 'rec'; reg = s[f'{pre}_regime'].to_numpy()
        cx = pd.DataFrame({'ntr_60': s[f'{pre}_ntr_60'].to_numpy(), 'qchg_60': s[f'{pre}_qchg_60'].to_numpy(), 'ntr_20': s[f'{pre}_ntr_20'].to_numpy()})
        # vectorised quintiles per regime
        qi = np.full(len(s), -1)
        for rg in ('1', '2', '3+'):
            m = reg == rg
            if m.any():
                pl, ed, idxs = pools[(d, ax)][rg]; qi[m] = np.searchsorted(ed, act_pct(pl, cx[m]), side='right')
        plan[(d, ax)] = (reg, qi)
ncov = {k: int(((v[0] != 'lockcross') & (v[1] >= 0)).sum()) for k, v in plan.items()}
print('candidates with a control pool:', ncov, flush=True)
for j in range(NDRAW):
    for ax, ks in AXES.items():
        parts = []
        for d, T in tapes.items():
            s = Fs[Fs.tape == d]; reg, qi = plan[(d, ax)]; anc = np.full(len(s), -1, np.int64)
            for rg in ('1', '2', '3+'):
                pl, ed, idxs = pools[(d, ax)][rg]
                for q in range(5):
                    m = (reg == rg) & (qi == q)
                    if m.any() and len(idxs[q]): anc[m] = pl.cut_ns.to_numpy()[rng.choice(idxs[q], size=int(m.sum()))]
            ok = anc >= 0; P = T.paths(anc[ok], s.pol.to_numpy()[ok], ks); parts.append(P)
        Pc = {v: np.vstack([q[v] for q in parts]) for v in parts[0]}
        st = stats(Pc)
        for v in st: draw[ax][v][j] = st[v]
        first, sg = first_move(Pc['mid_o'], ks)
        fm[ax][j] = fm_hist(first, sg)
    if j % 25 == 0: print('draw', j, round(time.time() - t0, 1), 's', flush=True)
np.savez_compressed(f'{CW}/x03_draws.npz', **{f'{ax}__{v}': draw[ax][v] for ax in AXES for v in draw[ax]}, **{f'fm__{ax}': fm[ax] for ax in AXES})
# ------------------------------------------------------------------ tables
cols = ['p5', 'p25', 'p50', 'p75', 'p95', 'share_pos', 'share_neg', 'n_valid']
recs = []; ctl = []
for ax, ks in AXES.items():
    for v in STATE_VARS + BIN_VARS:
        kk = ks if v in STATE_VARS else ks[:-1]
        a = cst[ax][v]
        for i, k in enumerate(kk): recs.append(dict(axis=ax, var=v, k=int(k), **{c: float(a[i, m]) for m, c in enumerate(cols)}))
        dq = draw[ax][v]; qs = np.nanpercentile(dq, [2.5, 50, 97.5], axis=0)     # across draws: (3, K, 8)
        for i, k in enumerate(kk):
            row = dict(axis=ax, var=v, k=int(k))
            for m, c in enumerate(cols[:7]): row.update({f'ctl_{c}_lo': float(qs[0, i, m]), f'ctl_{c}_med': float(qs[1, i, m]), f'ctl_{c}_hi': float(qs[2, i, m])})
            ctl.append(row)
pd.DataFrame(recs).to_csv(f'{TABD}/x03_cohort_stats.csv.gz', index=False); pd.DataFrame(ctl).to_csv(f'{TABD}/x03_control_stats.csv.gz', index=False)
# per-candidate oriented midpoint paths (full distribution), birth axis
mo = cohort['birth']['mid_o']; ks = AXES['birth']
W = pd.DataFrame(mo, columns=[f'k{int(k)}' for k in ks]); W.insert(0, 'delay_s', ((Fs.rec_ns - Fs.pre_ns - 1) / S).to_numpy()); W.insert(0, 'polarity', Fs.pol.to_numpy()); W.insert(0, 'row', Fs.row.to_numpy())
W.to_csv(f'{TABD}/x03_cohort_mid_o_birth_axis.csv.gz', index=False)
first, sg = first_move(mo, ks); hc = fm_hist(first, sg); dm = fm['birth']
q = np.percentile(dm, [2.5, 50, 97.5], axis=0)     # (3, 2, 161)
fmc = pd.DataFrame({'boundary_k': list(range(1, 161)) + [999]})   # 999 = never moved within +160 s
for si, nm in enumerate(('oriented_positive', 'oriented_negative')):
    fmc[f'cohort_{nm}'] = hc[si]
    for qi, qn in enumerate(('lo', 'med', 'hi')): fmc[f'ctl_{nm}_{qn}'] = q[qi, si]
fmc.to_csv(f'{TABD}/x03_first_move_birth_axis.csv', index=False)
json.dump(dict(session=SESS, candidates=N, draws=NDRAW, tapes=list(tapes), axes={k: [int(v[0]), int(v[-1])] for k, v in AXES.items()}, with_control_pool={f'{a}_{b}': v for (a, b), v in ncov.items()}), open(f'{TABD}/x03_receipt.json', 'w'), indent=1)
print('done', round(time.time() - t0, 1), 's')
