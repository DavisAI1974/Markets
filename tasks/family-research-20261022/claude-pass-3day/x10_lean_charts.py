"""Chart for x09: trailing 20 s signed flow lean and the oriented midpoint change around the birth, four days, cohort versus matched controls (200 draws for lean; 500 for midpoint).
Every plotted array is compared after saving with the table re-read from disk; counts go to crossday/es_lean_reconciliation.csv."""
import os, numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
H = os.path.dirname(os.path.abspath(__file__)); OUT = f'{H}/crossday'; DAYS = ['20231002', '20231003', '20231017', '20231018']; LAB = dict(zip(DAYS, ['Oct 2', 'Oct 3', 'Oct 17', 'Oct 18']))
OR, BK, GR, BL = '#c05621', '#1a202c', '#a0aec0', '#2b6cb0'
plt.rcParams.update({'font.size': 8, 'axes.grid': True, 'grid.color': '#e2e8f0', 'grid.linewidth': .6, 'axes.axisbelow': True, 'legend.frameon': False, 'legend.fontsize': 7})
def load(d):
    L = pd.read_csv(f'{H}/tables/dipole/{d}/x09_lean_cohort.csv').set_index('k'); LC = pd.read_csv(f'{H}/tables/dipole/{d}/x09_lean_control.csv').set_index('k')
    M = pd.read_csv(f'{H}/tables/dipole/{d}/x03_cohort_stats.csv.gz'); M = M[(M.axis == 'birth') & (M['var'] == 'mid_o')].set_index('k')
    MC = pd.read_csv(f'{H}/tables/dipole/{d}/x03_control_stats.csv.gz'); MC = MC[(MC.axis == 'birth') & (MC['var'] == 'mid_o')].set_index('k'); return dict(lean=L, lean_ctl=LC, mid=M, mid_ctl=MC)
T = {d: load(d) for d in DAYS}; REC = []
def put(ax, d, kind, col, ks, **kw):
    df = T[d][kind].loc[ks]; y = df[col].to_numpy(float); ax.plot(ks, y, **kw); REC.append((d, kind, col, list(ks), y.copy()))
def band(ax, d, kind, base, ks):
    df = T[d][kind].loc[ks]; ax.fill_between(ks, df[base + '_lo'], df[base + '_hi'], color=GR, alpha=.4, lw=0); ax.plot(ks, df[base + '_med'], color=GR, lw=.8)
    for nm in ('lo', 'med', 'hi'): REC.append((d, kind, f'{base}_{nm}', list(ks), df[f'{base}_{nm}'].to_numpy(float).copy()))
KL = np.arange(-40, 61); f, A = plt.subplots(3, 4, figsize=(14, 8.4), sharex=True)
for j, d in enumerate(DAYS):
    n = int(T[d]['lean'].n.iloc[0]); A[0, j].set_title(f'{LAB[d]}  (n={n})', loc='left')
    a = A[0, j]; band(a, d, 'lean_ctl', 'ctl_p50', KL); a.fill_between(KL, T[d]['lean'].loc[KL, 'p25'], T[d]['lean'].loc[KL, 'p75'], color=OR, alpha=.22, lw=0)
    put(a, d, 'lean', 'p25', KL, color=OR, lw=.7); put(a, d, 'lean', 'p75', KL, color=OR, lw=.7); put(a, d, 'lean', 'p50', KL, color=OR, lw=1.5)
    a = A[1, j]; band(a, d, 'lean_ctl', 'ctl_share_lean_plus1', KL); band(a, d, 'lean_ctl', 'ctl_share_lean_minus1', KL)
    put(a, d, 'lean', 'share_lean_plus1', KL, color=OR, lw=1.4, label='share with lean = +1 (all lots in the birth direction)'); put(a, d, 'lean', 'share_lean_minus1', KL, color=BL, lw=1.4, label='share with lean = -1'); put(a, d, 'lean', 'share_defined', KL, color=BK, lw=.9, ls='--', label='share with any lots in the window')
    a = A[2, j]; band(a, d, 'mid_ctl', 'ctl_p5', KL); band(a, d, 'mid_ctl', 'ctl_p95', KL)
    for st, lw, col in (('p5', .8, '#2c5282'), ('p25', .8, '#4299e1'), ('p50', 1.4, BK), ('p75', .8, '#4299e1'), ('p95', .8, '#2c5282')): put(a, d, 'mid', st, KL, color=col, lw=lw, label=st)
    for r in range(3): A[r, j].axvline(0, color='k', lw=.6, ls=':'); A[r, j].axvline(-20, color='#718096', lw=.5, ls=':')
    A[2, j].set_xlabel('seconds from birth-second boundary (k)')
A[0, 0].set_ylabel('trailing 20 s lean: (lots with - lots against) / total\np25, p50, p75 across candidates where defined'); A[1, 0].set_ylabel('share of candidates'); A[2, 0].set_ylabel('oriented midpoint change (ticks)'); A[1, 0].legend(loc='center left'); A[2, 0].legend(ncol=5, loc='upper left')
f.suptitle('Flow lean and midpoint around the birth, four days. Grey: matched controls (2.5 to 97.5 percent of draws). Dotted lines: k = 0 and k = -20', x=.01, ha='left', fontsize=10)
f.tight_layout(rect=(0, 0, 1, .96)); f.savefig(f'{OUT}/es-lean-and-price-around-birth.png', dpi=130); plt.close(f)
rows = []
for d, kind, col, ks, y in REC:
    ref = T[d][kind].loc[ks, col].to_numpy(float); rows.append(dict(day=d, table=kind, column=col, points_plotted=len(y), table_rows=len(ref), points_equal_table=int(np.isclose(np.nan_to_num(y, nan=-9e9), np.nan_to_num(ref, nan=-9e9)).sum()), nan_points=int(np.isnan(y).sum())))
R = pd.DataFrame(rows); R.to_csv(f'{OUT}/es_lean_reconciliation.csv', index=False); print('series', len(R), 'points', int(R.points_plotted.sum()), 'all equal:', bool((R.points_plotted == R.points_equal_table).all()), 'nan points:', int(R.nan_points.sum()))
