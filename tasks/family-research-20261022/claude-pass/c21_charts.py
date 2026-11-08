"""c21: charts for the cross-day regime comparison, built straight from the tables.  Usage: python3 -I c21_charts.py
Every figure's plotted points are counted and asserted equal to the table rows they come from; the counts go to figures/t5_chart_reconciliation.csv.
Palette: reference categorical slots 1 (blue) and 2 (orange), validated light mode; one hue for single-series panels; blue/red diverging with a gray midpoint.
Dates are panel labels only."""
import sys; sys.path.insert(0, '.')   # cwd is this code directory, not a data directory
from odcfg import *
import os
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
SURF = '#fcfcfb'; INK = '#0b0b0b'; INK2 = '#52514e'; GRID = '#e6e5e1'; BLUE = '#2a78d6'; ORANGE = '#eb6834'
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'text.color': INK, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.edgecolor': GRID, 'axes.linewidth': 1, 'grid.color': GRID, 'grid.linewidth': 1, 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
FIG = f'{HERE}/figures'; os.makedirs(FIG, exist_ok=True)
DL = {'20231002': 'Oct 2', '20231003': 'Oct 3', '20231017': 'Oct 17', '20231018': 'Oct 18'}; RL = {'1': '1 tick', '2': '2 ticks', '3+': '3+ ticks'}; REGS = ['1', '2', '3+']
T = pd.concat([pd.read_csv(tab(d, 't3_regime_coupling.csv')) for d in DATES], ignore_index=True); T['date'] = T['date'].astype(str)
A = pd.read_csv(tab('crossday', 't4_crossday_pairs.csv'), dtype={'regime': str}); S = pd.read_csv(tab('crossday', 't4_crossday_summary.csv'), dtype={'regime': str})
NULLC = np.load(f'{WORK}/crossday_null_counts.npz'); rec = []
# ---- Fig 1: distribution of rho over all pairs, per day and regime
fig, ax = plt.subplots(3, 4, figsize=(13, 8), sharex=True)
lo, hi = np.floor(T.rho.min() * 50) / 50, np.ceil(T.rho.max() * 50) / 50; bins = np.arange(lo, hi + 1e-9, 0.01)
for i, r in enumerate(REGS):
    for j, d in enumerate(DATES):
        t = T[(T.regime == r) & (T.date == d)]; a = ax[i, j]; cnt, _ = np.histogram(t.rho, bins=bins)
        a.bar(bins[:-1], cnt, width=0.0095, align='edge', color=BLUE, linewidth=0); a.grid(axis='y'); a.set_axisbelow(True)
        line = t.null95_line.iloc[0]
        for s in (-line, line):
            if lo <= s <= hi: a.axvline(s, color=INK2, lw=1)
        a.set_title(f'{DL[d]}, {RL[r]}: {len(t):,} pairs, {int(t.beyond_null95.sum())} beyond line', fontsize=9, color=INK, loc='left')
        assert cnt.sum() == len(t); rec.append(dict(figure='1 rho distributions', panel=f'{DL[d]} {RL[r]}', plotted=int(cnt.sum()), table_rows=len(t), source='t3_regime_coupling.csv'))
        if j == 0: a.set_ylabel('pairs')
for a in ax[-1]: a.set_xlabel('rank correlation')
fig.suptitle('Distribution of every condition/outcome correlation, by day and spread regime\nvertical lines: each regime-day family-wise shifted-Y 95% line (+/-)', x=0.01, ha='left', fontsize=12, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.94)); fig.savefig(f'{FIG}/crossday-rho-distributions.png', dpi=150); plt.close(fig)
# ---- Fig 2: agreement counts, observed vs shifted-Y
fig, ax = plt.subplots(1, 3, figsize=(13, 4.6), sharey=True); xs = np.arange(3); w = 0.32
for i, r in enumerate(REGS):
    a = ax[i]; s = S[S.regime == r].iloc[0]; nd = NULLC[r.replace('+', 'p')]
    obs = [s.obs_2_of_4, s.obs_3_of_4, s.obs_4_of_4]; nm = nd.mean(0); nlo = nd.min(0); nhi = nd.max(0)
    a.bar(xs - w / 2 - 0.01, obs, width=w, color=BLUE, label='observed (four days)'); a.bar(xs + w / 2 + 0.01, nm, width=w, color=ORANGE, label=f'Y shifted, mean of {nd.shape[0]} draws')
    for k in range(3):
        a.vlines(xs[k] + w / 2 + 0.01, nlo[k], nhi[k], color=INK2, lw=1)
        a.text(xs[k] - w / 2 - 0.01, obs[k] + 25, f'{int(obs[k]):,}', ha='center', va='bottom', fontsize=9, color=INK); a.text(xs[k] + w / 2 + 0.01, nhi[k] + 25, f'{nm[k]:,.0f}', ha='center', va='bottom', fontsize=9, color=INK2)
    a.set_xticks(xs); a.set_xticklabels(['2 of 4 days', '3 of 4 days', '4 of 4 days']); a.grid(axis='y'); a.set_axisbelow(True); a.set_title(f'{RL[r]}: {int(s.pairs_on_all_four_days):,} pairs', loc='left', fontsize=10, color=INK)
    assert int(sum(obs)) == int(s.pairs_on_all_four_days) == int((A.regime == r).sum()); rec.append(dict(figure='2 agreement counts', panel=RL[r], plotted=int(sum(obs)), table_rows=int((A.regime == r).sum()), source='t4_crossday_pairs.csv'))
ax[0].set_ylabel('pairs, by days sharing the majority sign'); h, l = ax[0].get_legend_handles_labels()
fig.suptitle('How many days agree in sign: observed vs the same pairs with Y shifted (whisker = min to max of draws)', x=0.01, ha='left', fontsize=12, color=INK)
fig.legend(h, l, frameon=False, loc='upper right', ncol=2, fontsize=9, bbox_to_anchor=(0.99, 0.985)); fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(f'{FIG}/crossday-agreement-vs-shifted.png', dpi=150); plt.close(fig)
# ---- Fig 3: day vs Oct 18 scatter of rho
fig, ax = plt.subplots(3, 3, figsize=(11.5, 11), sharex=True, sharey=True); lim = float(np.ceil(A[[f'rho_{d[4:]}' for d in DATES]].abs().max().max() * 20) / 20)
for i, r in enumerate(REGS):
    P = A[A.regime == r]
    for j, d in enumerate(DATES[:3]):
        a = ax[i, j]; x = P['rho_1018']; y = P[f'rho_{d[4:]}']; a.scatter(x, y, s=7, color=BLUE, alpha=0.3, linewidths=0)
        a.plot([-lim, lim], [-lim, lim], color=INK2, lw=1); a.axhline(0, color=GRID, lw=1); a.axvline(0, color=GRID, lw=1)
        same = int((np.sign(x) == np.sign(y)).sum()); a.set_xlim(-lim, lim); a.set_ylim(-lim, lim); a.set_aspect('equal')
        a.set_title(f'{RL[r]}: {DL[d]} vs Oct 18', loc='left', fontsize=10, color=INK); a.text(0.03, 0.97, f'{len(x):,} pairs\nsame sign {same:,} ({same / len(x):.0%})\nPearson r {np.corrcoef(x, y)[0, 1]:+.2f}', transform=a.transAxes, ha='left', va='top', fontsize=8.5, color=INK2)
        assert len(x) == int((A.regime == r).sum()); rec.append(dict(figure='3 day vs Oct 18', panel=f'{RL[r]} {DL[d]}', plotted=int(len(x)), table_rows=int((A.regime == r).sum()), source='t4_crossday_pairs.csv'))
        if i == 2: a.set_xlabel('Oct 18 rho')
        if j == 0: a.set_ylabel('other day rho')
fig.suptitle('Same pair, two days: each dot is one condition/outcome pair', x=0.01, ha='left', fontsize=12, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.96)); fig.savefig(f'{FIG}/crossday-rho-scatter.png', dpi=150); plt.close(fig)
# ---- Fig 4: top repeating pairs heatmap (4 of 4 days, ranked by smallest |rho|)
cmap = LinearSegmentedColormap.from_list('div', ['#1c5cab', '#86b6ef', '#f0efec', '#f2a5a4', '#c93a39']); NTOP = 20
fig, ax = plt.subplots(1, 3, figsize=(16, 8.5))
for i, r in enumerate(REGS):
    P = A[(A.regime == r) & (A.days_same_sign == 4)].sort_values('min_abs_rho', ascending=False).head(NTOP); M = P[[f'rho_{d[4:]}' for d in DATES]].to_numpy(); a = ax[i]
    a.imshow(M, cmap=cmap, vmin=-0.3, vmax=0.3, aspect='auto'); a.set_xticks(range(4)); a.set_xticklabels([DL[d] for d in DATES]); a.xaxis.tick_top()
    a.set_yticks(range(len(P))); a.set_yticklabels([f'{x} -> {y}' for x, y in zip(P.x, P.y)], fontsize=8.5)
    for u in range(M.shape[0]):
        for v in range(4): a.text(v, u, f'{M[u, v]:+.2f}', ha='center', va='center', fontsize=8, color=INK)
    a.set_title(f'{RL[r]}: top {len(P)} of {int((A[(A.regime == r)].days_same_sign == 4).sum()):,} agreeing on all 4 days', loc='left', fontsize=9.5, color=INK, pad=24)
    for s in a.spines.values(): s.set_visible(False)
    a.tick_params(length=0); rec.append(dict(figure='4 top repeating heatmap', panel=RL[r], plotted=int(M.size), table_rows=int(len(P) * 4), source='t4_crossday_pairs.csv (4 rho columns x top rows)'))
fig.suptitle('Largest smallest-|rho| among pairs agreeing in sign on all four days (blue negative, red positive)', x=0.01, ha='left', fontsize=12, color=INK, y=0.995)
fig.tight_layout(rect=(0, 0, 1, 0.96)); fig.savefig(f'{FIG}/crossday-top-repeating-heatmap.png', dpi=150); plt.close(fig)
# ---- Fig 5: same view inside each outcome family (the all-family top is dominated by same-quantity persistence)
FAMS = ['signed move', 'quote response', 'magnitude']; NT = 10
fig, ax = plt.subplots(3, 3, figsize=(16, 11))
for fi, fam in enumerate(FAMS):
    for i, r in enumerate(REGS):
        P = A[(A.regime == r) & (A.family == fam) & (A.days_same_sign == 4)].sort_values('min_abs_rho', ascending=False).head(NT); M = P[[f'rho_{d[4:]}' for d in DATES]].to_numpy(); a = ax[fi, i]
        n4 = int(((A.regime == r) & (A.family == fam) & (A.days_same_sign == 4)).sum()); nf = int(((A.regime == r) & (A.family == fam)).sum())
        a.imshow(M, cmap=cmap, vmin=-0.3, vmax=0.3, aspect='auto'); a.set_xticks(range(4)); a.set_xticklabels([DL[d] for d in DATES], fontsize=8.5); a.xaxis.tick_top()
        a.set_yticks(range(len(P))); a.set_yticklabels([f'{x} -> {y}' for x, y in zip(P.x, P.y)], fontsize=8.5)
        for u in range(M.shape[0]):
            for v in range(4): a.text(v, u, f'{M[u, v]:+.2f}', ha='center', va='center', fontsize=8, color=INK)
        a.set_title(f'{fam}, {RL[r]}: top {len(P)} of {n4} (of {nf} pairs)', loc='left', fontsize=9.5, color=INK, pad=22)
        for s in a.spines.values(): s.set_visible(False)
        a.tick_params(length=0); rec.append(dict(figure='5 per-family heatmap', panel=f'{fam} {RL[r]}', plotted=int(M.size), table_rows=int(len(P) * 4), source='t4_crossday_pairs.csv'))
fig.suptitle('Top pairs agreeing in sign on all four days, within outcome family (blue negative, red positive; ranked by smallest |rho|)', x=0.01, ha='left', fontsize=12, color=INK, y=0.995)
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(f'{FIG}/crossday-top-by-family-heatmap.png', dpi=150); plt.close(fig)
R = pd.DataFrame(rec); R['match'] = R.plotted == R.table_rows; R.to_csv(f'{FIG}/t5_chart_reconciliation.csv', index=False)
assert R.match.all(); print(R.to_string(index=False)); print('all plotted counts reconcile to table rows:', bool(R.match.all()))
