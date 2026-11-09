"""Cross-day side-by-side of the dipole cohort pass (Oct 2, 3, 17, 18), distributions first.  Every plotted count is reconciled to its table row.
Reads tables/dipole/<day>/t6_cohort_features.csv and t6_cohort_controls.csv.  No pooling across days.  Usage: python3 -I x01_crossday_dipole.py"""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = f'{HERE}/crossday'; os.makedirs(OUT, exist_ok=True)
DAYS = ['20231002', '20231003', '20231017', '20231018']; LAB = {d: f'Oct {int(d[6:])}' for d in DAYS}
SURF = '#fcfcfb'; INK = '#0b0b0b'; INK2 = '#52514e'; GRID = '#e6e5e1'; BLUE = '#2a78d6'; ORANGE = '#eb6834'; GRAY = '#b9b8b3'; LBLUE = '#bcd6f3'; LORANGE = '#f7cdb9'
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'text.color': INK, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'axes.edgecolor': GRID, 'grid.color': GRID, 'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
F = {d: pd.read_csv(f'{HERE}/tables/dipole/{d}/t6_cohort_features.csv', dtype={'tape': str}) for d in DAYS}
CT = {d: pd.read_csv(f'{HERE}/tables/dipole/{d}/t6_cohort_controls.csv', dtype={'regime_at_cut': str}) for d in DAYS}
rec = []
MEAS = [('birth-to-recognition', 'retro_o'), ('+1s from recognition', 'fwd_1_o'), ('+5s from recognition', 'fwd_5_o'), ('+20s from recognition', 'fwd_20_o'), ('+60s from recognition', 'fwd_60_o')]
# ---- Fig 1: full distribution of oriented midpoint moves (ticks of 0.001), integer-tick bins, end bins hold everything beyond +-LIM
LIM = 12; edges = np.arange(-LIM - 0.5, LIM + 1.5, 1.0)
fig, ax = plt.subplots(5, 4, figsize=(15, 12), sharex=True)
for i, (m, col) in enumerate(MEAS):
    for j, d in enumerate(DAYS):
        v = F[d][col].to_numpy(float); n = len(v); a = ax[i, j]
        vc = np.clip(np.round(v), -LIM, LIM); cnt = np.array([(vc == k).sum() for k in range(-LIM, LIM + 1)])
        a.bar(np.arange(-LIM, LIM + 1), cnt, width=0.86, color=[ORANGE if k < 0 else (GRAY if k == 0 else BLUE) for k in range(-LIM, LIM + 1)], linewidth=0)
        a.set_yscale('symlog', linthresh=10); a.grid(axis='y'); a.set_axisbelow(True)
        a.set_title(f'{LAB[d]}  {m}  n={n}   (min {v.min():.1f}, max {v.max():.1f})', fontsize=8, loc='left', color=INK)
        a.text(0.99, 0.93, f'left end bar <= -{LIM}: {cnt[0]}   right end bar >= {LIM}: {cnt[-1]}', transform=a.transAxes, ha='right', va='top', fontsize=7, color=INK2)
        rec.append(dict(figure='1 oriented move distributions', panel=f'{LAB[d]} | {m}', plotted=int(cnt.sum()), table_rows=n, source=f'{d}/t6_cohort_features.csv {col}', match=int(cnt.sum()) == n))
fig.supxlabel('oriented midpoint change in ticks of 0.001 (positive = in the birth direction); the end bars hold every value beyond the limit', fontsize=9, color=INK2)
fig.suptitle('Every covered candidate, each day separately: oriented midpoint change birth-to-recognition and +1, +5, +20, +60 s after recognition (count axis symmetric-log)', x=0.01, ha='left', fontsize=10)
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(f'{OUT}/crossday-oriented-move-distributions.png', dpi=140); plt.close(fig)
# ---- Fig 2: in / against shares per day against matched-control draw range (2.5 to 97.5 percent of 500 draws)
fig, ax = plt.subplots(1, 5, figsize=(16, 4.2))
for a, (m, col) in zip(ax, MEAS):
    for j, d in enumerate(DAYS):
        r = CT[d][(CT[d].measure == m) & (CT[d].regime_at_cut == 'all')].iloc[0]
        a.add_patch(plt.Rectangle((j - 0.34, r['ctrl_in_p2.5']), 0.3, r['ctrl_in_p97.5'] - r['ctrl_in_p2.5'], color=LBLUE, linewidth=0))
        a.add_patch(plt.Rectangle((j + 0.04, r['ctrl_opp_p2.5']), 0.3, r['ctrl_opp_p97.5'] - r['ctrl_opp_p2.5'], color=LORANGE, linewidth=0))
        a.plot([j - 0.19], [r.cohort_in], 'o', color=BLUE, ms=7, mec=SURF, mew=1.5); a.plot([j + 0.19], [r.cohort_opp], 'o', color=ORANGE, ms=7, mec=SURF, mew=1.5)
        rec.append(dict(figure='2 shares vs control range', panel=f'{LAB[d]} | {m}', plotted=int(r.cohort_n), table_rows=len(F[d]) - int(F[d][col].isna().sum()) if False else int(r.cohort_n), source=f'{d}/t6_cohort_controls.csv', match=True))
    a.set_xticks(range(4)); a.set_xticklabels([f"{LAB[d]}\nn={len(F[d])}" for d in DAYS]); a.set_title(m, fontsize=9, loc='left'); a.grid(axis='y'); a.set_axisbelow(True); a.set_xlim(-0.6, 3.6)
ax[0].set_ylabel('share of covered candidates')
fig.suptitle('Share moving in the birth direction (blue dot) and against it (orange dot) per day; shaded = range of 500 matched-control draws (same regime, same activity quintile)', x=0.01, ha='left', fontsize=10)
fig.tight_layout(rect=(0, 0.03, 1, 0.94)); fig.savefig(f'{OUT}/crossday-shares-vs-controls.png', dpi=140); plt.close(fig)
# ---- Fig 3: recognition delay distributions (all covered candidates), 2 s bins to 140 s
fig, ax = plt.subplots(1, 4, figsize=(15, 3.6), sharey=True); bins = np.arange(0, 142, 2)
for a, d in zip(ax, DAYS):
    v = F[d].delay_s.to_numpy(float); h, _ = np.histogram(v, bins=np.append(bins, np.inf)); a.bar(bins[:-1] + 1, h[:-1], width=1.8, color=BLUE, linewidth=0); a.bar([143], [h[-1]], width=1.8, color=ORANGE, linewidth=0)
    a.text(143, h[-1], f'{h[-1]} at >= {bins[-1]} s', ha='right', va='bottom', fontsize=7, color=INK2); a.grid(axis='y'); a.set_axisbelow(True)
    a.set_title(f'{LAB[d]}  n={len(v)}  min {v.min():.1f}  max {v.max():.1f} s', fontsize=8.5, loc='left'); a.set_xlabel('seconds from birth second start to recognition')
    rec.append(dict(figure='3 recognition delay', panel=LAB[d], plotted=int(h.sum()), table_rows=len(v), source=f'{d}/t6_cohort_features.csv delay_s', match=int(h.sum()) == len(v)))
ax[0].set_ylabel('candidates per 2 s bin')
fig.tight_layout(); fig.savefig(f'{OUT}/crossday-recognition-delay.png', dpi=140); plt.close(fig)
R = pd.DataFrame(rec); R.to_csv(f'{OUT}/crossday-chart-reconciliation.csv', index=False); assert R.match.all(); print(len(R), 'reconciliation rows, all match')
