"""Trailing 20 s signed flow lean around each birth, next to the oriented midpoint change, cohort versus matched controls.  Measurements only.
Re-uses x03's construction (setup, Tape.paths, matched control pools and plan) by executing its source, then computes per candidate and per boundary k (-40 .. +60 s from the birth-second boundary):
  lean_k = (with lots - against lots) / (with lots + against lots) over the 20 seconds ending at boundary k (lots in the birth direction minus lots against it); undefined when no lots in the window.
Per boundary: p25 / p50 / p75 of lean across candidates where defined, share defined, share lean = +1, share lean = -1.  Controls: 200 draws (same matching as x03), 2.5 / 50 / 97.5 percent across draws.
Usage: OD_SESS=<session> python3 -I x09_lean_around_birth.py     Writes tables/dipole/<SESS>/x09_lean_cohort.csv, x09_lean_control.csv"""
import os, sys
src = open('x03_birth_paths.py').read().split('\n')
os.environ.setdefault('X03_DRAWS', '200')
exec('\n'.join(src[:94]))            # imports, classes, candidate table, tapes
exec('\n'.join(src[103:137]))        # matched control pools and plan
ND = 200; KS = AXES['birth']; KK = np.arange(-40, 61); IDX = [int(np.where(KS == k)[0][0]) for k in KK]
def lean_stats(P):
    w = np.nancumsum(np.nan_to_num(P['with_lots']), axis=1); a = np.nancumsum(np.nan_to_num(P['against_lots']), axis=1); z = np.zeros((w.shape[0], 1)); w = np.hstack([z, w]); a = np.hstack([z, a])
    # boundary index j has cumulative sum over bins 0..j-1; trailing 20 s ending at boundary j = cum[j] - cum[j-20]
    W_ = np.stack([w[:, j] - w[:, j - 20] for j in IDX], 1); A_ = np.stack([a[:, j] - a[:, j - 20] for j in IDX], 1); T_ = W_ + A_
    lean = np.where(T_ > 0, (W_ - A_) / np.maximum(T_, 1), np.nan); nv = (~np.isnan(lean)).sum(0)
    q = np.nanpercentile(lean, [25, 50, 75], axis=0); return np.vstack([q, nv / lean.shape[0], np.nanmean(lean == 1, 0) * 0 + np.where(nv > 0, np.nansum(lean == 1, 0) / np.maximum(nv, 1), np.nan), np.where(nv > 0, np.nansum(lean == -1, 0) / np.maximum(nv, 1), np.nan)]).T
P = {ax: None for ax in AXES}
parts = []
for d, T in tapes.items():
    s = Fs[Fs.tape == d]; parts.append(T.paths(s.pre_ns.to_numpy(np.int64), s.pol.to_numpy(), KS))
Pc = {v: np.vstack([q[v] for q in parts]) for v in ('with_lots', 'against_lots', 'mid_o')}
coh = lean_stats(Pc); n_c = len(Fs)
dr = np.zeros((ND, len(KK), 6), np.float32)
for j in range(ND):
    parts = []
    for d, T in tapes.items():
        s = Fs[Fs.tape == d]; reg, qi = plan[(d, 'birth')]; anc = np.full(len(s), -1, np.int64)
        for rg in ('1', '2', '3+'):
            pl, ed, idxs = pools[(d, 'birth')][rg]
            for q in range(5):
                m = (reg == rg) & (qi == q)
                if m.any() and len(idxs[q]): anc[m] = pl.cut_ns.to_numpy()[rng.choice(idxs[q], size=int(m.sum()))]
        ok = anc >= 0; parts.append(T.paths(anc[ok], s.pol.to_numpy()[ok], KS))
    dr[j] = lean_stats({v: np.vstack([q[v] for q in parts]) for v in ('with_lots', 'against_lots')})
    if j % 50 == 0: print('draw', j, flush=True)
cols = ['p25', 'p50', 'p75', 'share_defined', 'share_lean_plus1', 'share_lean_minus1']
pd.DataFrame([dict(k=int(k), n=n_c, **{c: float(coh[i, m]) for m, c in enumerate(cols)}) for i, k in enumerate(KK)]).to_csv(f'{TABD}/x09_lean_cohort.csv', index=False)
qs = np.nanpercentile(dr, [2.5, 50, 97.5], axis=0)
pd.DataFrame([dict(k=int(k), **{f'ctl_{c}_{nm}': float(qs[a, i, m]) for m, c in enumerate(cols) for a, nm in enumerate(('lo', 'med', 'hi'))}) for i, k in enumerate(KK)]).to_csv(f'{TABD}/x09_lean_control.csv', index=False)
print('done', n_c)
