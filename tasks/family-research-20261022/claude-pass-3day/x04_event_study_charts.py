"""Charts and cross-day tables for the second-by-second birth-aligned study (x03).  Reads only the committed x03 tables.
Every plotted line is recorded (figure, day, axis, variable, statistic, k, plotted y) and compared after saving with the values re-read from the CSV files; counts go to es_chart_reconciliation.csv.
Output: crossday/es-*.png, crossday/es_chart_reconciliation.csv, crossday/es_selected_seconds.csv"""
import sys; sys.path.insert(0, '.')
import os, numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
H = os.path.dirname(os.path.abspath(__file__)); DAYS = ['20231002', '20231003', '20231017', '20231018']; OUT = f'{H}/crossday'; os.makedirs(OUT, exist_ok=True)
LAB = {'20231002': 'Oct 2', '20231003': 'Oct 3', '20231017': 'Oct 17', '20231018': 'Oct 18'}
BLUE, ORANGE, INK, GRID, BAND = '#2b6cb0', '#c05621', '#1a202c', '#e2e8f0', '#a0aec0'
plt.rcParams.update({'font.size': 8, 'axes.edgecolor': '#718096', 'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': INK, 'axes.titlesize': 9, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': .6, 'axes.axisbelow': True, 'legend.frameon': False, 'legend.fontsize': 7})
C = {d: pd.read_csv(f'{H}/tables/dipole/{d}/x03_cohort_stats.csv.gz') for d in DAYS}; T = {d: pd.read_csv(f'{H}/tables/dipole/{d}/x03_control_stats.csv.gz') for d in DAYS}
REC = []     # plotted records

def line(ax, fig, d, axis, var, stat, kind='cohort', **kw):
    """plot one series from the tables; record exactly what was plotted"""
    if kind == 'cohort':
        s = C[d][(C[d].axis == axis) & (C[d]['var'] == var)].sort_values('k'); x, y = s.k.to_numpy(), s[stat].to_numpy()
        ax.plot(x, y, **kw)
    else:   # control band: stat like 'share_pos' -> lo/med/hi
        s = T[d][(T[d].axis == axis) & (T[d]['var'] == var)].sort_values('k'); x = s.k.to_numpy()
        lo, md, hi = s[f'ctl_{stat}_lo'].to_numpy(), s[f'ctl_{stat}_med'].to_numpy(), s[f'ctl_{stat}_hi'].to_numpy()
        ax.fill_between(x, lo, hi, color=kw.get('color', BAND), alpha=kw.get('alpha', .35), lw=0, step=kw.get('step')); ax.plot(x, md, color=kw.get('color', BAND), lw=.8, alpha=.9)
        for nm, yy in (('lo', lo), ('med', md), ('hi', hi)): REC.append(dict(fig=fig, day=d, axis=axis, var=var, stat=f'ctl_{stat}_{nm}', n_plotted=len(x), plotted=yy.copy(), k=x.copy()))
        return
    REC.append(dict(fig=fig, day=d, axis=axis, var=var, stat=stat, n_plotted=len(x), plotted=np.asarray(y, float).copy(), k=x.copy()))

def grid4(nrows, title, sub=None, w=13.5, h=2.35):
    f, A = plt.subplots(nrows, 4, figsize=(w, h * nrows + .9), squeeze=False, sharex='row')
    f.suptitle(title, fontsize=10, x=.01, ha='left', y=.995);
    for j, d in enumerate(DAYS): A[0, j].set_title(f'{LAB[d]}  (n={int(C[d][(C[d].axis == "birth") & (C[d]["var"] == "mid_o") & (C[d].k == 0)].n_valid.iloc[0])})', loc='left')
    return f, A

def save(f, name): f.tight_layout(rect=(0, 0, 1, .975)); f.savefig(f'{OUT}/{name}', dpi=130); plt.close(f)

# ---------------------------------------------------------------- ES1 heatmaps of every candidate path, sorted by recognition delay
M = {}
for d in DAYS: M[d] = pd.read_csv(f'{H}/tables/dipole/{d}/x03_cohort_mid_o_birth_axis.csv.gz').sort_values('delay_s').reset_index(drop=True)
f, A = plt.subplots(1, 4, figsize=(14, 5.6), sharey=False); f.suptitle('Every candidate, birth-aligned: oriented midpoint change from the birth-second start (ticks of 0.001), candidates sorted by recognition delay', fontsize=10, x=.01, ha='left')
hm = []
for j, d in enumerate(DAYS):
    X = M[d]; kc = [c for c in X.columns if c.startswith('k')]; Z = X[kc].to_numpy(float); ks = np.array([int(c[1:]) for c in kc])
    im = A[j].imshow(Z, aspect='auto', cmap='RdBu_r', norm=TwoSlopeNorm(0, -4, 4), extent=(ks[0] - .5, ks[-1] + .5, len(Z) - .5, -.5), interpolation='nearest')
    A[j].plot(X.delay_s.to_numpy(), np.arange(len(Z)), color='k', lw=.9, drawstyle='steps-post'); A[j].axvline(0, color='k', lw=.5, ls=':')
    A[j].set_title(f'{LAB[d]}  rows={len(Z)}', loc='left'); A[j].set_xlabel('seconds from birth-second start (k)'); A[j].grid(False)
    hm.append(dict(fig='ES1', day=d, rows_in_table=len(X), rows_plotted=len(Z), cells=int(Z.size), cells_nan=int(np.isnan(Z).sum()), cells_below_minus4=int((Z < -4).sum()), cells_above_plus4=int((Z > 4).sum()), cells_zero=int((Z == 0).sum())))
A[0].set_ylabel('candidate (sorted by recognition delay; black line = recognition second)')
f.colorbar(im, ax=A, orientation='horizontal', fraction=.035, pad=.09, label='oriented midpoint change (ticks); colour scale clipped at +-4, counts of clipped cells in es_chart_reconciliation.csv')
f.savefig(f'{OUT}/es-heatmap-oriented-mid-paths.png', dpi=130, bbox_inches='tight'); plt.close(f)

# ---------------------------------------------------------------- ES2 shares of candidates with oriented change >0 / <0 versus control bands
for axis, ks_lab, nm in (('birth', 'seconds from birth-second start (k)', 'es-share-moved-birth-axis.png'), ('rec', 'seconds from recognition (k)', 'es-share-moved-recognition-axis.png')):
    f, A = grid4(2, f'Share of candidates whose midpoint is above / below its anchor-boundary level, oriented by birth direction ({axis} axis). Bands: 2.5 to 97.5 percent of 500 matched-control draws')
    for j, d in enumerate(DAYS):
        for r, (stat, col, ttl) in enumerate((('share_pos', BLUE, 'oriented change > 0 (birth direction)'), ('share_neg', ORANGE, 'oriented change < 0 (against birth direction)'))):
            a = A[r, j]; line(a, f'ES2{axis}', d, axis, 'mid_o', stat, 'ctl', color=BAND); line(a, f'ES2{axis}', d, axis, 'mid_o', stat, color=col, lw=1.3); a.axvline(0, color='k', lw=.5, ls=':')
            if j == 0: a.set_ylabel(ttl, fontsize=7)
            a.set_xlabel(ks_lab if r == 1 else '')
    save(f, nm)

# ---------------------------------------------------------------- ES3 percentile fan of oriented change
for axis, nm in (('birth', 'es-percentiles-moved-birth-axis.png'), ('rec', 'es-percentiles-moved-recognition-axis.png')):
    f, A = grid4(1, f'Oriented midpoint change: p5, p25, p50, p75, p95 across candidates ({axis} axis), with matched-control band for p5 and p95 (2.5 to 97.5 percent of draws)', h=3.6)
    for j, d in enumerate(DAYS):
        a = A[0, j]; line(a, f'ES3{axis}', d, axis, 'mid_o', 'p5', 'ctl', color=BAND); line(a, f'ES3{axis}', d, axis, 'mid_o', 'p95', 'ctl', color=BAND)
        for st, lw, cl in (('p5', .9, '#2c5282'), ('p25', .9, '#4299e1'), ('p50', 1.2, INK), ('p75', .9, '#4299e1'), ('p95', .9, '#2c5282')): line(a, f'ES3{axis}', d, axis, 'mid_o', st, color=cl, lw=lw, label=st)
        a.axvline(0, color='k', lw=.5, ls=':'); a.set_xlabel('seconds from ' + ('birth-second start' if axis == 'birth' else 'recognition') + ' (k)')
        if j == 0: a.set_ylabel('ticks'); a.legend(ncol=5, loc='upper left')
    save(f, nm)

# ---------------------------------------------------------------- ES4 first-move timing (birth axis)
FM = {d: pd.read_csv(f'{H}/tables/dipole/{d}/x03_first_move_birth_axis.csv') for d in DAYS}
f, A = grid4(2, 'Seconds from the birth-second start boundary to the first non-zero oriented midpoint change (counts of candidates; bands: matched controls, 2.5 to 97.5 percent). Last bar = no change within +160 s', h=2.7)
for j, d in enumerate(DAYS):
    X = FM[d]; x = np.arange(len(X)); xl = np.where(X.boundary_k == 999, 161, X.boundary_k)
    for r, (nm, col, ttl) in enumerate((('oriented_positive', BLUE, 'first move in the birth direction'), ('oriented_negative', ORANGE, 'first move against the birth direction'))):
        a = A[r, j]; a.bar(xl, X[f'cohort_{nm}'], color=col, width=1.0); a.fill_between(xl, X[f'ctl_{nm}_lo'], X[f'ctl_{nm}_hi'], color=BAND, alpha=.55, lw=0, step='mid'); a.plot(xl, X[f'ctl_{nm}_med'], color=INK, lw=.6, drawstyle='steps-mid')
        a.set_xlabel('boundary k of first change (161 = none within +160 s)' if r == 1 else '');
        if j == 0: a.set_ylabel(ttl, fontsize=7)
        REC.append(dict(fig='ES4', day=d, axis='birth', var=nm, stat='cohort_count', n_plotted=len(X), plotted=X[f'cohort_{nm}'].to_numpy(float).copy(), k=xl.copy()))
save(f, 'es-first-move-timing-birth-axis.png')

# ---------------------------------------------------------------- ES5 touch state (target side = the side the birth direction trades against)
for axis in ('birth', 'rec'):
    f, A = grid4(3, f'Displayed touch size in lots ({axis} axis): target side (side the birth direction trades against) and own side; p25 / p50 / p75 of candidates, matched-control p50 band (2.5 to 97.5 percent of draws)', h=2.6)
    for r, (var, ttl) in enumerate((('tgt_sz', 'target-side touch size (lots)'), ('own_sz', 'own-side touch size (lots)'), ('spr', 'spread (ticks)'))):
        for j, d in enumerate(DAYS):
            a = A[r, j]; line(a, f'ES5{axis}', d, axis, var, 'p50', 'ctl', color=BAND)
            for st, lw, cl in (('p25', .8, '#4299e1'), ('p50', 1.3, INK), ('p75', .8, '#4299e1')): line(a, f'ES5{axis}', d, axis, var, st, color=cl, lw=lw)
            a.axvline(0, color='k', lw=.5, ls=':'); a.set_xlabel('seconds from ' + ('birth-second start' if axis == 'birth' else 'recognition') + ' (k)' if r == 2 else '')
            if j == 0: a.set_ylabel(ttl, fontsize=7)
    save(f, f'es-touch-state-{axis}-axis.png')

# ---------------------------------------------------------------- ES6 aggressor lots with / against (per second)
for axis in ('birth', 'rec'):
    f, A = grid4(3, f'Aggressor lots per second in the birth direction (with) and the opposite direction (against), {axis} axis. Bands: matched controls, 2.5 to 97.5 percent of 500 draws', h=2.6)
    for j, d in enumerate(DAYS):
        for r, (stat, ttl) in enumerate((('share_pos', 'share of candidates with any lots in the second'), ('p75', 'p75 of lots in the second'), ('p95', 'p95 of lots in the second'))):
            a = A[r, j]
            for var, col in (('with_lots', BLUE), ('against_lots', ORANGE)):
                line(a, f'ES6{axis}', d, axis, var, stat, 'ctl', color=col, alpha=.18); line(a, f'ES6{axis}', d, axis, var, stat, color=col, lw=1.1, label=var.replace('_lots', ''))
            a.axvline(0, color='k', lw=.5, ls=':'); a.set_xlabel('second k (interval k to k+1)' if r == 2 else '')
            if j == 0: a.set_ylabel(ttl, fontsize=7);
            if j == 0 and r == 0: a.legend(loc='upper left')
    save(f, f'es-aggressor-lots-{axis}-axis.png')

# ---------------------------------------------------------------- ES7 book activity by side (share of candidates with any in the second), birth axis
VARS = [('tgt_fill', 'target side: fills'), ('tgt_add_touch', 'target side: adds at touch'), ('tgt_rm_cx_touch', 'target side: unlinked cancels at touch'), ('own_fill', 'own side: fills'), ('own_add_touch', 'own side: adds at touch'), ('own_rm_cx_touch', 'own side: unlinked cancels at touch')]
for axis in ('birth', 'rec'):
    f, A = grid4(len(VARS), f'Share of candidates with any book activity in the second, by side and class ({axis} axis). Bands: matched controls, 2.5 to 97.5 percent of draws', h=1.9)
    for r, (var, ttl) in enumerate(VARS):
        for j, d in enumerate(DAYS):
            a = A[r, j]; line(a, f'ES7{axis}', d, axis, var, 'share_pos', 'ctl', color=BAND); line(a, f'ES7{axis}', d, axis, var, 'share_pos', color=BLUE if var.startswith('tgt') else ORANGE, lw=1.1); a.axvline(0, color='k', lw=.5, ls=':')
            if j == 0: a.set_ylabel(ttl, fontsize=6.5)
            a.set_xlabel('second k' if r == len(VARS) - 1 else '')
    save(f, f'es-book-activity-{axis}-axis.png')

# ---------------------------------------------------------------- reconcile: plotted arrays versus table rows re-read from the CSV files
rows = []
CC = {d: pd.read_csv(f'{H}/tables/dipole/{d}/x03_cohort_stats.csv.gz').set_index(['axis', 'var', 'k']) for d in DAYS}; TT = {d: pd.read_csv(f'{H}/tables/dipole/{d}/x03_control_stats.csv.gz').set_index(['axis', 'var', 'k']) for d in DAYS}
for r in REC:
    d, axis, var, stat, k = r['day'], r['axis'], r['var'], r['stat'], r['k']
    if r['fig'] == 'ES4':
        X = pd.read_csv(f'{H}/tables/dipole/{d}/x03_first_move_birth_axis.csv'); ref = X[f'cohort_{var}'].to_numpy(float)
    elif stat.startswith('ctl_'): ref = TT[d].loc[[(axis, var, int(kk)) for kk in k], stat].to_numpy(float)
    else: ref = CC[d].loc[[(axis, var, int(kk)) for kk in k], stat].to_numpy(float)
    p = r['plotted']; same = np.isclose(np.nan_to_num(p, nan=-9e9), np.nan_to_num(ref, nan=-9e9)).sum()
    rows.append(dict(fig=r['fig'], day=d, axis=axis, var=var, stat=stat, points_plotted=len(p), table_rows=len(ref), points_equal_table=int(same), nan_points=int(np.isnan(p).sum())))
R = pd.DataFrame(rows).groupby(['fig', 'day', 'axis', 'var', 'stat'], as_index=False).sum(numeric_only=True)
R.to_csv(f'{OUT}/es_chart_reconciliation.csv', index=False)
pd.DataFrame(hm).to_csv(f'{OUT}/es_heatmap_reconciliation.csv', index=False)
print('series', len(R), 'all points equal table:', bool((R.points_plotted == R.points_equal_table).all()), 'table rows == points:', bool((R.points_plotted == R.table_rows).all()), 'points', int(R.points_plotted.sum()))
print(pd.DataFrame(hm).to_string())

# ---------------------------------------------------------------- selected seconds, all days side by side
sel = []
for axis, ks in (('birth', [-60, -30, -10, -5, -2, -1, 1, 2, 3, 5, 10, 20, 30, 40, 50, 60, 80, 100, 160]), ('rec', [-60, -40, -20, -10, -5, -1, 1, 5, 20, 60])):
    for d in DAYS:
        for k in ks:
            a = CC[d].loc[(axis, 'mid_o', k)]; b = TT[d].loc[(axis, 'mid_o', k)]
            sel.append(dict(axis=axis, day=LAB[d], k=k, n=int(a.n_valid), share_pos=a.share_pos, share_neg=a.share_neg, share_zero=1 - a.share_pos - a.share_neg, ctl_pos_lo=b.ctl_share_pos_lo, ctl_pos_med=b.ctl_share_pos_med, ctl_pos_hi=b.ctl_share_pos_hi, ctl_neg_lo=b.ctl_share_neg_lo, ctl_neg_med=b.ctl_share_neg_med, ctl_neg_hi=b.ctl_share_neg_hi, p5=a.p5, p25=a.p25, p50=a.p50, p75=a.p75, p95=a.p95))
pd.DataFrame(sel).to_csv(f'{OUT}/es_selected_seconds.csv', index=False)
