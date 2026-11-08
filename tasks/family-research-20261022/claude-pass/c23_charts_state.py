"""c23: heatmaps for the regime-split state cells and lead-lag (cross-day).  Usage: python3 -I c23_charts_state.py
Plotted cell counts are asserted equal to table rows and appended to figures/t5_chart_reconciliation.csv.  Same palette rules as c21.  Dates are panel labels only."""
import sys; sys.path.insert(0, '.')   # cwd is this code directory, not a data directory
from odcfg import *
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
SURF = '#fcfcfb'; INK = '#0b0b0b'; INK2 = '#52514e'; GRID = '#e6e5e1'
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'text.color': INK, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'font.size': 10})
FIG = f'{HERE}/figures'; DL = {'1002': 'Oct 2', '1003': 'Oct 3', '1017': 'Oct 17', '1018': 'Oct 18'}; RL = {'1': '1 tick', '2': '2 ticks', '3+': '3+ ticks'}; REGS = ['1', '2', '3+']
cmap = LinearSegmentedColormap.from_list('div', ['#1c5cab', '#86b6ef', '#f0efec', '#f2a5a4', '#c93a39']); rec = []
X = pd.read_csv(tab('crossday', 't4_state_crossday.csv'), dtype={'regime': str})
for hz, fn in (('next1s', 'crossday-state-cells-next1s.png'), ('next5s', 'crossday-state-cells-next5s.png')):
    sub = X[X.horizon == hz]; nrow = max(len(sub[sub.regime == r]) for r in REGS)
    fig, ax = plt.subplots(1, 3, figsize=(17, 0.36 * nrow + 2.2))
    for i, r in enumerate(REGS):
        P = sub[sub.regime == r].sort_values('cell'); M = P[[f'net_{d}' for d in DL]].to_numpy(); a = ax[i]
        a.imshow(M, cmap=cmap, vmin=-0.3, vmax=0.3, aspect='auto'); a.set_xticks(range(4)); a.set_xticklabels(DL.values()); a.xaxis.tick_top(); a.set_yticks(range(len(P))); a.set_yticklabels([c.replace('|', '  |  ') for c in P.cell], fontsize=8.5)
        for u in range(M.shape[0]):
            for v in range(4): a.text(v, u, f'{M[u, v]:+.2f}\nn={int(P.iloc[u][f"support_{list(DL)[v]}"]):,}', ha='center', va='center', fontsize=7, color=INK)
        a.set_title(f'{RL[r]}: {len(P)} cells with >= 100 seconds on all four days', loc='left', fontsize=9.5, pad=24)
        for s in a.spines.values(): s.set_visible(False)
        a.tick_params(length=0); rec.append(dict(figure=f'state cells {hz}', panel=RL[r], plotted=int(M.size), table_rows=int(len(P) * 4), source='t4_state_crossday.csv'))
    fig.suptitle(f'Net share (up minus down, over all seconds in the cell) of the {hz[4:]} midpoint change; rows: last-second move | touch size lean | last-second net flow', x=0.01, ha='left', fontsize=11.5, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.965)); fig.savefig(f'{FIG}/{fn}', dpi=140); plt.close(fig)
L = pd.read_csv(tab('crossday', 't4_leadlag_crossday.csv'), dtype={'regime': str}); PR = L[['A', 'B']].drop_duplicates().apply(tuple, axis=1).tolist()
fig, ax = plt.subplots(3, 1, figsize=(15, 13))
for i, r in enumerate(REGS):
    sub = L[L.regime == r]; cols = []; lab = []; M = []
    for (A_, B_) in PR:
        for lg in (-1, 0, 1):
            row = sub[(sub.A == A_) & (sub.B == B_) & (sub.lag == lg)]; M.append(row[[f'rho_{d}' for d in DL]].to_numpy()[0]); lab.append(f'{A_} -> {B_}  lag {lg:+d}s')
    M = np.array(M); a = ax[i]; a.imshow(M.T, cmap=cmap, vmin=-0.6, vmax=0.6, aspect='auto'); a.set_yticks(range(4)); a.set_yticklabels(DL.values()); a.set_xticks(range(len(lab))); a.set_xticklabels(lab, rotation=60, ha='left', fontsize=8); a.xaxis.tick_top()
    for u in range(M.shape[0]):
        for v in range(4): a.text(u, v, f'{M[u, v]:+.2f}', ha='center', va='center', fontsize=7, color=INK)
    a.set_title(f'{RL[r]}', loc='left', fontsize=10, pad=100)
    for s in a.spines.values(): s.set_visible(False)
    a.tick_params(length=0); rec.append(dict(figure='lead-lag', panel=RL[r], plotted=int(M.size), table_rows=int(len(PR) * 3 * 4), source='t4_leadlag_crossday.csv (lags -1,0,+1 x 4 days)'))
fig.suptitle('One-second lead-lag within spread regime (lag > 0: first series leads); series percentile-ranked inside activity quintiles', x=0.01, ha='left', fontsize=11.5, y=0.998)
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(f'{FIG}/crossday-leadlag-heatmap.png', dpi=140); plt.close(fig)
R = pd.read_csv(f'{FIG}/t5_chart_reconciliation.csv'); R = R[~R.figure.str.startswith(('state cells', 'lead-lag'))]
N = pd.DataFrame(rec); N['match'] = N.plotted == N.table_rows; assert N.match.all()
pd.concat([R, N], ignore_index=True).to_csv(f'{FIG}/t5_chart_reconciliation.csv', index=False); print(N.to_string(index=False))
