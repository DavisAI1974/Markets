"""Dipole cohort charts, built from the tables.  Every plotted count is asserted equal to its table row and appended to figures/t5_chart_reconciliation.csv.
Blue = in the birth direction, orange = against it, gray = flat/zero.  Usage: python3 -I c24d_dipole_charts.py"""
import sys; sys.path.insert(0, '.')
from odcfg import *
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
SURF = '#fcfcfb'; INK = '#0b0b0b'; INK2 = '#52514e'; GRID = '#e6e5e1'; BLUE = '#2a78d6'; ORANGE = '#eb6834'; GRAY = '#b9b8b3'
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'text.color': INK, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.edgecolor': GRID, 'axes.linewidth': 1, 'grid.color': GRID, 'grid.linewidth': 1, 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
FIG = f'{HERE}/figures/{SESS}'; os.makedirs(FIG, exist_ok=True); T = TABD; rec = []
CT = pd.read_csv(f'{T}/t6_cohort_controls.csv', dtype={'regime_at_cut': str}); CE = pd.read_csv(f'{T}/t6_cohort_cells.csv'); SG = pd.read_csv(f'{T}/t6_cohort_signed_conditions.csv')
DS = np.load(f'{CW}/cohort_draw_stats.npz')
# ---- Fig 1: cohort against matched controls
meas = ['birth-to-recognition', '+1s from recognition', '+5s from recognition', '+20s from recognition', '+60s from recognition']
fig, ax = plt.subplots(1, 5, figsize=(15, 3.9), sharey=False)
for a, m in zip(ax, meas):
    row = CT[(CT.measure == m) & (CT.regime_at_cut == 'all')].iloc[0]; ds = DS[f'{m}|all']; assert ds.shape[0] == int(row.draws)
    lo = min(ds[:, 0].min(), ds[:, 1].min(), row.cohort_in, row.cohort_opp) - 0.01; hi = max(ds[:, 0].max(), ds[:, 1].max(), row.cohort_in, row.cohort_opp) + 0.01; bins = np.linspace(lo, hi, 31)
    c1, _ = np.histogram(ds[:, 0], bins=bins); c2, _ = np.histogram(ds[:, 1], bins=bins); w = bins[1] - bins[0]
    a.bar(bins[:-1], c1, width=w * 0.95, align='edge', color=BLUE, alpha=0.75, linewidth=0, label='controls: in birth direction'); a.bar(bins[:-1], c2, width=w * 0.95, align='edge', color=ORANGE, alpha=0.75, linewidth=0, label='controls: against')
    a.axvline(row.cohort_in, color=BLUE, lw=2); a.axvline(row.cohort_opp, color=ORANGE, lw=2, ls='--'); a.grid(axis='y'); a.set_axisbelow(True)
    a.set_title(f'{m}\ncohort in {row.cohort_in:.3f}, against {row.cohort_opp:.3f}, n {int(row.cohort_n)}', fontsize=9, color=INK, loc='left'); a.set_xlabel('share of candidates'); assert c1.sum() == len(ds) and c2.sum() == len(ds)
    rec.append(dict(figure='6 cohort vs controls', panel=m, plotted=int(c1.sum() + c2.sum()), table_rows=2 * int(row.draws), source='t6_cohort_controls.csv + cohort_draw_stats.npz', match=True))
ax[0].set_ylabel('control draws (of 500)'); h, l = ax[0].get_legend_handles_labels()
fig.legend(h, l + ['cohort: in (solid line)', 'cohort: against (dashed line)'][:0], loc='lower center', ncol=2, frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
fig.suptitle('The 852 covered candidates against 500 draws of matched controls (same tape, spread regime and activity quintile)\nlines: cohort shares; bars: distribution of the same share over control draws', x=0.01, ha='left', fontsize=11, color=INK)
fig.tight_layout(rect=(0, 0.05, 1, 0.9)); fig.savefig(f'{FIG}/dipole-cohort-vs-controls.png', dpi=150); plt.close(fig)
# ---- Fig 2: cells, retro and +20 s
order = [('spread regime at prebirth cutoff', ['1', '2', '3+']), ('orientation to previous candidate (SAME/FLIP)', ['SAME', 'FLIP']), ('Codex flow state at recognition', ['same_direction_at_emission', 'opposite_direction_at_emission', 'balanced_at_emission', 'undefined_at_emission']),
         ('prebirth displayed depth vs birth direction (mine)', ['aligned', 'opposed', 'equal']), ('recognition delay', ['fastest third', 'middle third', 'slowest third']), ('birth direction', ['buy birth', 'sell birth'])]
lab = {'same_direction_at_emission': 'recent flow same', 'opposite_direction_at_emission': 'recent flow opposite', 'balanced_at_emission': 'recent flow balanced', 'undefined_at_emission': 'no classified flow'}
items = [(d, c) for d, cs in order for c in cs if len(CE[(CE.dimension == d) & (CE.cell == c)])]; fig, ax = plt.subplots(1, 3, figsize=(15, 6.2), sharey=True); y = np.arange(len(items))[::-1]
for a, (nm, ttl) in zip(ax, (('retro', 'birth to recognition'), ('fwd5', '+5 s after recognition'), ('fwd20', '+20 s after recognition'))):
    for yy, (d, c) in zip(y, items):
        r = CE[(CE.dimension == d) & (CE.cell == c)].iloc[0]; n = int(r.n); vals = [int(r[f'{nm}_in']), int(r[f'{nm}_opp']), int(r[f'{nm}_flat'])]; assert sum(vals) == n
        left = 0
        for v, col in zip(vals, (BLUE, ORANGE, GRAY)):
            a.barh(yy, v / n, left=left / n if False else left, height=0.72, color=col, linewidth=0); left += v / n
        a.text(1.01, yy, f'{vals[0]}/{vals[1]}/{vals[2]}', va='center', fontsize=8, color=INK2)
        rec.append(dict(figure='7 cohort cells', panel=f'{ttl} | {d} | {c}', plotted=sum(vals), table_rows=n, source='t6_cohort_cells.csv', match=True))
    a.set_xlim(0, 1.0); a.set_title(ttl + '   (in / against / flat counts)', fontsize=9, color=INK, loc='left'); a.set_xlabel('share of cell'); a.grid(axis='x'); a.set_axisbelow(True)
ax[0].set_yticks(y)
def nice(d, c):
    if d.startswith('spread'): return f'spread {c} tick' + ('' if c == '1' else 's')
    if d.startswith('prebirth depth'): return f'prebirth depth {c}'
    if d.startswith('orientation'): return f'{c} as previous candidate' if c == 'SAME' else 'FLIP from previous candidate'
    return lab.get(c, c)
ax[0].set_yticklabels([f"{nice(d, c)}  (n {int(CE[(CE.dimension == d) & (CE.cell == c)].iloc[0].n)})" for d, c in items], fontsize=8.5)
for yy, (d, c) in zip(y, items):
    if c == order[[o[0] for o in order].index(d)][1][0]: ax[0].text(-0.62, yy + 0.62, d, fontsize=8, color=INK, ha='left', transform=ax[0].get_yaxis_transform(), fontweight='bold') if False else None
fig.suptitle('Oriented midpoint move by cell: blue in the birth direction, orange against, gray flat. Order of cells: spread regime, SAME/FLIP, flow state at recognition, prebirth depth, recognition delay, birth direction', x=0.01, ha='left', fontsize=10, color=INK)
fig.tight_layout(rect=(0, 0, 0.99, 0.94)); fig.savefig(f'{FIG}/dipole-cohort-cells.png', dpi=150); plt.close(fig)
# ---- Fig 3: signed prebirth conditions, cohort counts against the symmetric-pool expectation
fig, ax = plt.subplots(1, len(SG), figsize=(15, 3.6), sharey=False)
for a, (_, r) in zip(ax, SG.iterrows()):
    n = int(r.defined_n); co = [r.cohort_toward_birth, r.cohort_against_birth, r.cohort_zero]; ex = [r.expected_toward, r.expected_against, r.expected_zero]; assert sum(co) == n
    xs = np.arange(3); a.bar(xs - 0.2, np.array(co) / n, width=0.38, color=BLUE, linewidth=0, label='cohort'); a.bar(xs + 0.2, np.array(ex) / n, width=0.38, color=GRAY, linewidth=0, label='same-regime grid, symmetrised')
    a.set_xticks(xs); a.set_xticklabels(['toward\nbirth', 'against\nbirth', 'zero'], fontsize=8); a.set_title(f'{r.condition}\nn {n}', fontsize=9, color=INK, loc='left'); a.grid(axis='y'); a.set_axisbelow(True)
    rec.append(dict(figure='8 signed prebirth conditions', panel=r.condition, plotted=int(sum(co)), table_rows=n, source='t6_cohort_signed_conditions.csv', match=True))
ax[0].set_ylabel('share of defined candidates'); h, l = ax[0].get_legend_handles_labels(); fig.legend(h, l, loc='lower center', ncol=2, frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.01))
fig.suptitle('Prebirth condition sign relative to the later birth direction (retrospective: the direction is only known at recognition)', x=0.01, ha='left', fontsize=11, color=INK)
fig.tight_layout(rect=(0, 0.07, 1, 0.88)); fig.savefig(f'{FIG}/dipole-cohort-signed-conditions.png', dpi=150); plt.close(fig)
R = (pd.read_csv(f'{FIG}/t5_chart_reconciliation.csv') if os.path.exists(f'{FIG}/t5_chart_reconciliation.csv') else pd.DataFrame(columns=['figure', 'panel', 'plotted', 'table_rows', 'source', 'match'])); R = R[~R.figure.str.startswith(('6 ', '7 ', '8 '))]
pd.concat([R, pd.DataFrame(rec)], ignore_index=True).to_csv(f'{FIG}/t5_chart_reconciliation.csv', index=False); print('figures written', len(rec), 'reconciliation rows added')
