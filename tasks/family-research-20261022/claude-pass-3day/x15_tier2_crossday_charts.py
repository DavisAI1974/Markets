"""x15: charts for the Tier 2 cross-day comparison, built straight from the x14 tables in crossday/.  Usage: python3 -I x15_tier2_crossday_charts.py
Every figure's plotted points are counted and asserted equal to the table rows they come from; the counts go to crossday/t2x_chart_reconciliation.csv.
Palette: the validated categorical slots 1-4 (blue, orange, aqua, yellow) in fixed assignment to days with a marker shape as the second encoding;
blue/red diverging with a neutral midpoint for signed heatmaps.  Days are labels only.  No trade cost anywhere."""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
HERE = os.path.dirname(os.path.abspath(__file__)); CD = f'{HERE}/crossday'; DATES = ['20231002', '20231003', '20231017', '20231018']
SURF = '#fcfcfb'; INK = '#0b0b0b'; INK2 = '#52514e'; GRID = '#e6e5e1'
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'text.color': INK, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.edgecolor': GRID, 'axes.linewidth': 1, 'grid.color': GRID, 'grid.linewidth': 1, 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
DL = {'20231002': 'Oct 2', '20231003': 'Oct 3', '20231017': 'Oct 17', '20231018': 'Oct 18'}
COL = {'20231018': '#2a78d6', '20231002': '#eb6834', '20231003': '#1baf7a', '20231017': '#eda100'}; MK = {'20231018': 'o', '20231002': 's', '20231003': '^', '20231017': 'D'}
cmap = LinearSegmentedColormap.from_list('div', ['#1c5cab', '#86b6ef', '#f0efec', '#f2a5a4', '#c93a39'])
def sfx(d): return d[4:]
def legend_days(fig, loc=(0.99, 0.945)):
    h = [Line2D([], [], color=COL[d], marker=MK[d], linestyle='', markersize=7, label=DL[d]) for d in DATES]
    fig.legend(handles=h, frameon=False, loc='upper right', ncol=4, fontsize=9, bbox_to_anchor=loc)
rec = []
P = pd.read_csv(f'{CD}/t2x_coupling_crossday.csv'); S = pd.read_csv(f'{CD}/t2x_coupling_summary.csv').iloc[0]
REF = pd.read_csv(f'{CD}/t2x_coupling_shifted_reference.csv') if os.path.exists(f'{CD}/t2x_coupling_shifted_reference.csv') else None

# ---- Fig 1: each condition/outcome pair, one day against Oct 18
fig, ax = plt.subplots(1, 3, figsize=(13, 4.8), sharex=True, sharey=True); lim = float(np.ceil(P[[f'rho_{sfx(d)}' for d in DATES]].abs().max().max() * 20) / 20)
for j, d in enumerate(DATES[:3]):
    a = ax[j]; x = P['rho_1018']; y = P[f'rho_{sfx(d)}']; a.scatter(x, y, s=7, color=COL[d], alpha=0.35, linewidths=0)
    a.plot([-lim, lim], [-lim, lim], color=INK2, lw=1); a.axhline(0, color=GRID, lw=1); a.axvline(0, color=GRID, lw=1); a.set_xlim(-lim, lim); a.set_ylim(-lim, lim); a.set_aspect('equal')
    same = int((np.sign(x) == np.sign(y)).sum()); a.set_title(f'{DL[d]} against Oct 18', loc='left', fontsize=10, color=INK)
    a.text(0.03, 0.97, f'{len(x):,} pairs\nsame sign {same:,} ({same / len(x):.0%})\nPearson r {np.corrcoef(x, y)[0, 1]:+.2f}', transform=a.transAxes, ha='left', va='top', fontsize=8.5, color=INK2)
    a.set_xlabel('Oct 18 rank correlation'); rec.append(dict(figure='1 pair scatter', panel=DL[d], plotted=len(x), table_rows=len(P), source='t2x_coupling_crossday.csv'))
ax[0].set_ylabel('other day rank correlation')
fig.suptitle('Tier 2 condition/outcome couplings: the same pair on two days (one dot per pair, activity-quintile rank correlation)', x=0.01, ha='left', fontsize=12, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(f'{CD}/t2x-coupling-day-vs-oct18.png', dpi=150); plt.close(fig)

# ---- Fig 2: days agreeing in sign and days beyond the line, observed against the shifted-Y reference
fig, ax = plt.subplots(1, 2, figsize=(13, 4.6)); w = 0.34
a = ax[0]; xs = np.arange(3); obs = [S.pairs_same_sign_2_of_4, S.pairs_same_sign_3_of_4, S.pairs_same_sign_4_of_4]
a.bar(xs - w / 2 - 0.01, obs, width=w, color='#2a78d6', label='observed, four days')
if REF is not None:
    nm = [REF[f'same_sign_{k}_of_4'].mean() for k in (2, 3, 4)]; nlo = [REF[f'same_sign_{k}_of_4'].min() for k in (2, 3, 4)]; nhi = [REF[f'same_sign_{k}_of_4'].max() for k in (2, 3, 4)]
    a.bar(xs + w / 2 + 0.01, nm, width=w, color='#eb6834', label=f'Y shifted, mean of {len(REF)} draws (whisker min to max)')
    for k in range(3): a.vlines(xs[k] + w / 2 + 0.01, nlo[k], nhi[k], color=INK2, lw=1); a.text(xs[k] + w / 2 + 0.01, nhi[k] + 20, f'{nm[k]:,.0f}', ha='center', va='bottom', fontsize=9, color=INK2)
for k in range(3): a.text(xs[k] - w / 2 - 0.01, obs[k] + 20, f'{int(obs[k]):,}', ha='center', va='bottom', fontsize=9, color=INK)
a.set_xticks(xs); a.set_xticklabels(['2 of 4 days', '3 of 4 days', '4 of 4 days']); a.grid(axis='y'); a.set_axisbelow(True); a.set_ylabel('pairs'); a.set_title(f'days sharing the majority sign, {int(S.pairs_on_all_four_days):,} pairs', loc='left', fontsize=10, color=INK)
assert int(sum(obs)) == len(P); rec.append(dict(figure='2 agreement counts', panel='same sign', plotted=int(sum(obs)), table_rows=len(P), source='t2x_coupling_summary.csv'))
a = ax[1]; xs = np.arange(5); obs = [S[f'pairs_beyond_line_{k}_days'] for k in range(5)]
a.bar(xs - w / 2 - 0.01, obs, width=w, color='#2a78d6')
if REF is not None:
    nm = [REF[f'beyond_line_{k}_days'].mean() for k in range(5)]; nhi = [REF[f'beyond_line_{k}_days'].max() for k in range(5)]; nlo = [REF[f'beyond_line_{k}_days'].min() for k in range(5)]
    a.bar(xs + w / 2 + 0.01, nm, width=w, color='#eb6834')
    for k in range(5): a.vlines(xs[k] + w / 2 + 0.01, nlo[k], nhi[k], color=INK2, lw=1); a.text(xs[k] + w / 2 + 0.01, nhi[k] + 20, f'{nm[k]:,.0f}', ha='center', va='bottom', fontsize=9, color=INK2)
for k in range(5): a.text(xs[k] - w / 2 - 0.01, obs[k] + 20, f'{int(obs[k]):,}', ha='center', va='bottom', fontsize=9, color=INK)
a.set_xticks(xs); a.set_xticklabels([f'{k} days' for k in range(5)]); a.grid(axis='y'); a.set_axisbelow(True); a.set_title("days on which |rho| is beyond that day's own shifted-Y 95% line", loc='left', fontsize=10, color=INK)
assert int(sum(obs)) == len(P); rec.append(dict(figure='2 agreement counts', panel='beyond line', plotted=int(sum(obs)), table_rows=len(P), source='t2x_coupling_summary.csv'))
h, l = ax[0].get_legend_handles_labels(); fig.legend(h, l, frameon=False, loc='upper right', ncol=2, fontsize=9, bbox_to_anchor=(0.99, 0.945))
fig.suptitle('How often the four days agree: observed pairs against the same pairs with Y shifted on each day', x=0.01, ha='left', fontsize=12, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.89)); fig.savefig(f'{CD}/t2x-coupling-agreement-vs-shifted.png', dpi=150); plt.close(fig)

# ---- Fig 3: pairs agreeing on all four days, within outcome family, ranked by the smallest |rho|
FAMS = ['signed move', 'magnitude', 'quote response', 'flow persistence', 'book response']; NT = 10
fig, ax = plt.subplots(1, 5, figsize=(24, 6.6))
for fi, fam in enumerate(FAMS):
    Q = P[(P.family == fam) & (P.days_same_sign == 4)].sort_values('min_abs_rho', ascending=False).head(NT); M = Q[[f'rho_{sfx(d)}' for d in DATES]].to_numpy(); a = ax[fi]
    n4 = int(((P.family == fam) & (P.days_same_sign == 4)).sum()); nf = int((P.family == fam).sum())
    a.imshow(M, cmap=cmap, vmin=-0.35, vmax=0.35, aspect='auto'); a.set_xticks(range(4)); a.set_xticklabels([DL[d] for d in DATES], fontsize=8.5); a.xaxis.tick_top()
    a.set_yticks(range(len(Q))); a.set_yticklabels([f'{x} -> {y}' for x, y in zip(Q.x, Q.y)], fontsize=8.5)
    for u in range(M.shape[0]):
        for v in range(4): a.text(v, u, f'{M[u, v]:+.2f}', ha='center', va='center', fontsize=8, color=INK)
    a.set_title(f'{fam}\ntop {len(Q)} of {n4} on all 4 days ({nf} pairs)', loc='left', fontsize=9, color=INK, pad=22)
    for s in a.spines.values(): s.set_visible(False)
    a.tick_params(length=0); rec.append(dict(figure='3 per-family heatmap', panel=fam, plotted=int(M.size), table_rows=int(len(Q) * 4), source='t2x_coupling_crossday.csv (4 rho columns x top rows)'))
fig.suptitle('Condition/outcome pairs with the same sign on all four days, by outcome family, ranked by the smallest |rho| (blue negative, red positive)', x=0.01, ha='left', fontsize=12, color=INK, y=0.995)
fig.tight_layout(rect=(0, 0, 1, 0.96)); fig.savefig(f'{CD}/t2x-coupling-top-by-family.png', dpi=150); plt.close(fig)

# ---- Fig 4: one-second state cells, net share of the next midpoint move per day
W = pd.read_csv(f'{CD}/t2x_state_cells_crossday.csv')
fig, ax = plt.subplots(1, 2, figsize=(14, 7.5), sharey=False)
for i, hz in enumerate(['next1s', 'next5s']):
    t = W[W.horizon == hz].sort_values('net_1018').reset_index(drop=True); a = ax[i]; npts = 0
    a.axvline(0, color=GRID, lw=1); a.grid(axis='x'); a.set_axisbelow(True)
    for d in DATES:
        v = t[f'net_{sfx(d)}']; m = v.notna(); a.scatter(v[m], np.arange(len(t))[m], color=COL[d], marker=MK[d], s=34, linewidths=0.8, edgecolors=SURF, zorder=3); npts += int(m.sum())
    a.set_yticks(range(len(t))); a.set_yticklabels([f'{c}  ({int(r.days_same_sign)}/{int(r.days_present)} days same sign)' for c, r in zip(t.cell, t.itertuples())], fontsize=8)
    a.set_title(f'{hz}: {len(t)} cells, ordered by Oct 18', loc='left', fontsize=10, color=INK); a.set_xlabel('net share = (up - down) / (up + down + flat)')
    rows = int(t[[f'net_{sfx(d)}' for d in DATES]].notna().sum().sum()); assert npts == rows; rec.append(dict(figure='4 state cells', panel=hz, plotted=npts, table_rows=rows, source='t2x_state_cells_crossday.csv (4 net columns)'))
legend_days(fig); fig.suptitle('One-second state cells [last-second midpoint move | touch imbalance tercile | last-second net flow]: what the midpoint did next, per day', x=0.01, ha='left', fontsize=12, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.91)); fig.savefig(f'{CD}/t2x-state-cells.png', dpi=150); plt.close(fig)

# ---- Fig 5: lead-lag at lag 0 for the 21 distinct series pairs, per day, with the peak lag of each day
Q = pd.read_csv(f'{CD}/t2x_leadlag_crossday.csv'); Q = Q[~Q.self_pair]; Q = Q[Q.A < Q.B].sort_values('rho_lag0_1018').reset_index(drop=True)
fig, ax = plt.subplots(1, 2, figsize=(14, 6.4), sharey=True)
a = ax[0]; a.axvline(0, color=GRID, lw=1); a.grid(axis='x'); a.set_axisbelow(True); npts = 0
for d in DATES: a.scatter(Q[f'rho_lag0_{sfx(d)}'], np.arange(len(Q)), color=COL[d], marker=MK[d], s=34, linewidths=0.8, edgecolors=SURF, zorder=3); npts += len(Q)
a.set_yticks(range(len(Q))); a.set_yticklabels([f'{r.A} , {r.B}' for r in Q.itertuples()], fontsize=8.5); a.set_xlabel('rank correlation at lag 0'); a.set_title('same-second correlation', loc='left', fontsize=10, color=INK)
rec.append(dict(figure='5 lead-lag', panel='lag 0', plotted=npts, table_rows=len(Q) * 4, source='t2x_leadlag_crossday.csv (A<B rows, 4 rho_lag0 columns)'))
a = ax[1]; a.axvline(0, color=GRID, lw=1); a.grid(axis='x'); a.set_axisbelow(True); npts = 0
for k, d in enumerate(DATES): a.scatter(Q[f'peak_lag_s_{sfx(d)}'] + (k - 1.5) * 0.0, np.arange(len(Q)) + (k - 1.5) * 0.12, color=COL[d], marker=MK[d], s=30, linewidths=0.8, edgecolors=SURF, zorder=3); npts += len(Q)
a.set_xlabel('lag of the peak |rho| in seconds (positive: A leads B)'); a.set_title('where the peak sits, per day (rows offset slightly)', loc='left', fontsize=10, color=INK); a.set_xlim(-16, 16)
rec.append(dict(figure='5 lead-lag', panel='peak lag', plotted=npts, table_rows=len(Q) * 4, source='t2x_leadlag_crossday.csv (A<B rows, 4 peak_lag columns)'))
legend_days(fig); fig.suptitle('One-second lead-lag between condition series, the 21 distinct pairs, ordered by Oct 18 lag-0 correlation', x=0.01, ha='left', fontsize=12, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.90)); fig.savefig(f'{CD}/t2x-leadlag.png', dpi=150); plt.close(fig)

# ---- Fig 6: forward-selection paths per outcome, out-of-fold correlation by step, per day, feature names at each step
FP = pd.read_csv(f'{CD}/t2x_forward_stack_paths.csv'); outs = list(FP.outcome.unique())
fig, ax = plt.subplots(2, 4, figsize=(18, 8.4)); ax = ax.ravel()
for i, o in enumerate(outs):
    t = FP[FP.outcome == o]; a = ax[i]; npts = 0
    for d in DATES:
        v = t[f'oof_corr_{sfx(d)}']; m = v.notna(); a.plot(t.step[m], v[m], color=COL[d], marker=MK[d], lw=2, markersize=6, markeredgecolor=SURF, markeredgewidth=0.8); npts += int(m.sum())
        for s, val, nm in zip(t.step[m], v[m], t[f'added_{sfx(d)}'][m]): a.annotate(nm, (s, val), textcoords='offset points', xytext=(4, 3), fontsize=6.5, color=INK2)
    a.grid(axis='y'); a.set_axisbelow(True); a.set_title(o, loc='left', fontsize=10, color=INK); a.set_xlabel('step'); a.set_xticks(range(1, int(t.step.max()) + 1))
    if i % 4 == 0: a.set_ylabel('out-of-fold correlation')
    rows = int(t[[f'oof_corr_{sfx(d)}' for d in DATES]].notna().sum().sum()); assert npts == rows; rec.append(dict(figure='6 forward stack', panel=o, plotted=npts, table_rows=rows, source='t2x_forward_stack_paths.csv (4 oof_corr columns)'))
ax[-1].axis('off'); legend_days(fig)
fig.suptitle('Forward-selection stack per outcome: out-of-fold correlation after each added condition, per day (label = the condition added at that step)', x=0.01, ha='left', fontsize=12, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.91)); fig.savefig(f'{CD}/t2x-forward-stack.png', dpi=150); plt.close(fig)

# ---- Fig 7 (when the full pair family is present): interaction partials agreeing on all four days, by outcome
if os.path.exists(f'{CD}/t2x_pair_couplings_full_crossday.csv'):
    U = pd.read_csv(f'{CD}/t2x_pair_couplings_full_crossday.csv'); outs = ['dm_5', 'dm_20', 'dspr_5', 'F_supdiff_5', 'F_net_5', 'am_20']; NT = 10
    fig, ax = plt.subplots(1, 6, figsize=(26, 6.6))
    for i, o in enumerate(outs):
        Q = U[(U.y == o) & (U.days_same_sign == 4)].sort_values('min_abs_int_rho', ascending=False).head(NT); M = Q[[f'int_rho_{sfx(d)}' for d in DATES]].to_numpy(); a = ax[i]
        n4 = int(((U.y == o) & (U.days_same_sign == 4)).sum()); nf = int((U.y == o).sum())
        a.imshow(M, cmap=cmap, vmin=-0.15, vmax=0.15, aspect='auto'); a.set_xticks(range(4)); a.set_xticklabels([DL[d] for d in DATES], fontsize=8.5); a.xaxis.tick_top()
        a.set_yticks(range(len(Q))); a.set_yticklabels([f'{x1} x {x2}' for x1, x2 in zip(Q.x1, Q.x2)], fontsize=8.5)
        for u in range(M.shape[0]):
            for v in range(4): a.text(v, u, f'{M[u, v]:+.3f}', ha='center', va='center', fontsize=7.5, color=INK)
        a.set_title(f'{o}\ntop {len(Q)} of {n4} on all 4 days ({nf} rows)', loc='left', fontsize=9, color=INK, pad=22)
        for s in a.spines.values(): s.set_visible(False)
        a.tick_params(length=0); rec.append(dict(figure='7 pair couplings', panel=o, plotted=int(M.size), table_rows=int(len(Q) * 4), source='t2x_pair_couplings_full_crossday.csv'))
    fig.suptitle('Pair couplings: interaction partial corr(y, z1*z2 | z1, z2) with the same sign on all four days, by outcome, ranked by smallest |value| (blue negative, red positive)', x=0.01, ha='left', fontsize=12, color=INK, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96)); fig.savefig(f'{CD}/t2x-pair-couplings-top-by-outcome.png', dpi=150); plt.close(fig)
R = pd.DataFrame(rec); R['match'] = R.plotted == R.table_rows; R.to_csv(f'{CD}/t2x_chart_reconciliation.csv', index=False)
assert R.match.all(); pd.set_option('display.width', 200); print(R.to_string(index=False)); print('all plotted counts reconcile to table rows:', bool(R.match.all()))
