"""One render per Native dipole candidate covering its whole life: its own path from 60 s before birth through exhaustion, with no averaging and no controls drawn.
Usage: OD_SESS=<session> python3 -I x12_instance_renders.py <outdir> [first_n last_n]
Reads WORK/<SESS>/x13_life_paths.npz (per-candidate book/flow paths, boundary k = -60 .. +1260 s), the candidate inputs, the detector ledger and the 20 s flow series.
Window per candidate: k = -60 .. max(160, later of first sign flip and first empty window + 60) s, capped at +1260 s (a note appears in the title when the cap is reached).
Lifecycle markers drawn on every panel (all measured from the same series):
  run onset   first second of the unbroken stretch of 20 s ratio = +1 in the birth direction that contains the birth second (may lie before the birth)
  birth       the birth second (yellow band)
  recognition the next completed-group close after the available second (red dotted)
  run end     first second at or after the birth where the ratio in the birth direction is below 1 (dashed green)
  first flip  first second at or after the birth where the ratio is on the opposite side of zero (dashed purple)
  first empty first second at or after the birth where the 20 s window holds no classified lots (dashed grey)
  weakening   the saved weakening transitions for the candidate (small triangles on the ratio panel, with the saved reason)
  other births  every other candidate birth inside the window (thin black ticks on the ratio panel; up = buy, down = sell)
Panels: 1 oriented midpoint and spread, 2 touch sizes, 3 aggressor lots with/against, 4 target-side book activity, 5 own-side book activity, 6 the 20 s ratio times polarity.
Writes one PNG per candidate and crossday/detector/instance_life_markers_<SESS>.csv (one row per candidate)."""
import os, sys, gzip, json
sys.path.insert(0, '.')
from odcfg import *
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from x11_det_emu import load
OUTD = sys.argv[1]; os.makedirs(OUTD, exist_ok=True)
LO = int(sys.argv[2]) if len(sys.argv) > 3 else 0; HI = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
rows = [json.loads(l) for l in gzip.open(CAND, 'rt')]
Z = np.load(f'{CW}/x13_life_paths.npz'); KS = Z['ks']; ROW = Z['row']; POL = Z['pol']
cov = pd.read_csv(f'{TABD}/t6_cohort_coverage.csv', dtype={'tape': str}).set_index('row')
S, top, ops = load(SESS); X = S.set_index('second'); R = X.ratio
led = pd.read_csv(f'{HERE}/crossday/detector/ledger_saturated_seconds_{SESS}.csv').set_index('second')
wk = pd.read_csv(os.path.join(os.path.dirname(EVENTS), 'dipole-weakening-path.csv.gz'))
allb = np.sort(np.array([int(r['birth_second']) for r in rows if r.get('birth_second') is not None])); allpol = {int(r['birth_second']): int((r.get('recorded_operands') or {}).get('polarity', 0)) for r in rows if r.get('birth_second') is not None}
CLS = ['add_touch', 'add_near', 'add_far', 'fill', 'rm_fill', 'rm_cx_touch', 'rm_cx_near', 'rm_cx_far']
COL = {'add_touch': '#1f77b4', 'add_near': '#6baed6', 'add_far': '#c6dbef', 'fill': '#d62728', 'rm_fill': '#ff9896', 'rm_cx_touch': '#8c564b', 'rm_cx_near': '#c49c94', 'rm_cx_far': '#e0cfc9'}
sec = R.index.to_numpy(); rv = R.to_numpy(float); six = {int(s): i for i, s in enumerate(sec)}
def first_after(cond, i0):
    w = np.where(cond[i0:])[0]; return int(w[0]) if len(w) else None
marks = []
for n in range(len(ROW)):
    r = rows[int(ROW[n])]; cid = r['candidate_id']; bs = int(r['birth_second']); av = int(r['available_second']); pol = int(POL[n]); i0 = six.get(bs)
    lag_rec = (int(cov.loc[ROW[n], 'rec_ns']) - int(cov.loc[ROW[n], 'pre_ns'])) / 1e9
    sg = rv * pol
    onset = None; run_end = flip = empty = None
    if i0 is not None and np.isfinite(sg[i0]):
        j = i0
        while j > 0 and np.isclose(sg[j - 1], 1.0): j -= 1
        onset = int(sec[j] - bs) if np.isclose(sg[i0], 1.0) else None
        run_end = first_after(~(sg >= 1 - 1e-12), i0); flip = first_after(sg < 0, i0); empty = first_after(~np.isfinite(sg), i0)
    life = [v for v in (flip, empty) if v is not None]; endk = max(life) if life else 1200
    hi = int(min(1260, max(160, endk + 60))); capped = (endk + 60 > 1260)
    m = len(marks); marks.append(dict(day=SESS, n=n + 1, candidate_id=cid, birth_second=bs, polarity=pol, run_onset_rel_s=onset, run_end_after_birth_s=run_end, first_flip_after_birth_s=flip, first_empty_after_birth_s=empty,
                                      recognition_after_cutoff_s=round(lag_rec, 3), available_minus_birth_s=av - bs, window_end_s=hi, window_capped=capped))
    if not (LO <= n < HI): continue
    L = int((KS <= hi).sum()); ks = KS[:L]; xb = ks[:-1] + 0.5; g = lambda v: Z[v][n][:L]; gb = lambda v: Z[v][n][:L - 1]
    fig, ax = plt.subplots(6, 1, figsize=(12, 13), sharex=True, gridspec_kw=dict(height_ratios=[1.3, 1, 1, 1.2, 1.2, 1.1]))
    ax[0].step(ks, g('mid_o'), where='post', color='#222', lw=1.2, label='midpoint, oriented (ticks)'); ax[0].plot(ks, g('spr'), color='#999', lw=0.9, label='spread (ticks)'); ax[0].axhline(0, color='#bbb', lw=0.6); ax[0].legend(loc='upper left', fontsize=7, ncol=2)
    ax[1].step(ks, g('tgt_sz'), where='post', color='#d62728', label='target-side touch size'); ax[1].step(ks, g('own_sz'), where='post', color='#1f77b4', label='own-side touch size'); ax[1].legend(loc='upper left', fontsize=7, ncol=2)
    ax[2].bar(xb, np.nan_to_num(gb('with_lots')), width=1, color='#2ca02c', label='aggressor lots with birth direction'); ax[2].bar(xb, -np.nan_to_num(gb('against_lots')), width=1, color='#e377c2', label='against'); ax[2].legend(loc='upper left', fontsize=7, ncol=2)
    for a, side in ((ax[3], 'tgt'), (ax[4], 'own')):
        up = np.zeros(len(xb)); dn = np.zeros(len(xb))
        for c in CLS:
            v = np.nan_to_num(gb(f'{side}_{c}'))
            if c.startswith('add'): a.bar(xb, v, bottom=up, width=1, color=COL[c], label=c); up += v
            else: a.bar(xb, -v, bottom=dn, width=1, color=COL[c], label=c); dn -= v
        a.set_ylabel(f'{side} side, lots', fontsize=8)
    ax[3].legend(loc='upper left', fontsize=6, ncol=4)
    w = X.loc[bs + ks[0]: bs + ks[-1]]; xs = w.index.to_numpy() - bs
    ax[5].step(xs, w.ratio.to_numpy() * pol, where='post', color='#444', lw=1.1); ax[5].set_ylim(-1.1, 1.1); ax[5].axhline(0, color='#bbb', lw=0.6)
    o = ops[ops.candidate_id == cid]; base = float(o.baseline.iloc[0]) if len(o) else np.nan
    ax[5].axhline(base, color='#ff7f0e', lw=0.8, ls='--'); ax[5].set_ylabel('20 s ratio x polarity', fontsize=8)
    wp = wk[wk.candidate_id == cid]
    for _, q in wp.iterrows():
        if ks[0] <= q.second - bs <= ks[-1]: ax[5].plot(q.second - bs, -1.0, marker='v', color='#9467bd', ms=5)
    for bb in allb:
        if bb != bs and ks[0] <= bb - bs <= ks[-1]: ax[5].plot([bb - bs] * 2, [1.02, 1.1] if allpol.get(int(bb), 1) > 0 else [-1.1, -1.02], color='k', lw=0.7)
    disp = led.loc[bs, 'disposition'] if bs in led.index else 'not a saturated second in the ledger'
    for a in ax:
        a.axvspan(0, 1, color='#ffd54f', alpha=0.35, lw=0); a.axvline(lag_rec, color='#d62728', lw=1.1, ls=':'); a.grid(alpha=0.2); a.tick_params(labelsize=8)
        if onset is not None: a.axvline(onset, color='#2ca02c', lw=0.8, ls='-')
        if run_end is not None: a.axvline(run_end, color='#2ca02c', lw=1.0, ls='--')
        if flip is not None: a.axvline(flip, color='#9467bd', lw=1.0, ls='--')
        if empty is not None: a.axvline(empty, color='#7f7f7f', lw=1.0, ls='--')
    ax[0].set_ylabel('ticks', fontsize=8); ax[1].set_ylabel('lots', fontsize=8); ax[2].set_ylabel('lots / s', fontsize=8)
    ax[5].set_xlabel('seconds from the birth-second boundary.  yellow = birth second; red dotted = recognition; green solid = run onset; green dashed = run end;\npurple dashed = first flip; grey dashed = first empty window; v = saved weakening transition; black ticks = other births', fontsize=7)
    ts = pd.Timestamp(bs, unit='s', tz='UTC').strftime('%Y-%m-%d %H:%M:%S'); f = lambda v: 'none' if v is None else f'{v:+d} s'
    fig.suptitle(f'{SESS}  candidate {n + 1} of {len(ROW)}  {cid}  birth {ts} UTC  {"BUY" if pol > 0 else "SELL"}\nrun onset {f(onset)}  run end {f(run_end)}  first flip {f(flip)}  first empty window {f(empty)}  recognition {lag_rec:.1f} s after cutoff  baseline {base:.3f}  detector ledger: {disp}  window to +{hi} s{" (capped; life continues)" if capped else ""}', fontsize=8.5, y=0.995)
    fig.tight_layout(rect=(0, 0.01, 1, 0.965)); fn = f'{SESS}_{n + 1:04d}_{cid}.png'; fig.savefig(f'{OUTD}/{fn}', dpi=85); plt.close(fig); marks[m]['file'] = fn
    if n % 100 == 0: print(SESS, n, flush=True)
if LO == 0 and HI >= 10**9: pd.DataFrame(marks).to_csv(f'{HERE}/crossday/detector/instance_life_markers_{SESS}.csv', index=False)
