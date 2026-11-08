"""13-input crosswalk table and chart.  Usage: python3 -I c25b_input_crosswalk.py   (after c25_crosswalk.py)
The relationship labels are my reading of what each input is and where it comes from (one primary, optional secondary); the evidence columns are measured in c25.
A 'closest' registry entry is a proposed analogy taken from external_point_provenance.csv, not a verified mapping; tests of sign, lead/lag, coverage and shared inputs are in the evidence columns.
Lead/lag cannot be tested: every input is declared as-of the family start and most are constant or stepped through the day."""
import sys; sys.path.insert(0, '.')
from odcfg import *
import json, numpy as np, pandas as pd, os
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
ROOT = f'{HERE}/..'; T = f'{HERE}/tables/crosswalk'; FIG = f'{HERE}/figures'
S = pd.read_csv(f'{T}/t7_input_series_measurements.csv'); C = pd.read_csv(f'{ROOT}/flow-book-discovery-v1/all-13-point-coverage.csv'); P = pd.read_csv(f'{ROOT}/../../artifacts/sqlite-triage/20261022/families/descriptive-v1/external_point_provenance.csv')
reg = {}
for _, r in P.iterrows():
    b = json.loads(r.body)
    for p in b['points']: reg.setdefault(p, set()).update(b['registry_entries'])
MY = {  # point: (primary, also, basis)
 1: ('shared input', 'plausible market transmission (positioning)', 'one weekly CFTC report; points 1, 3, 4 are the 1-year percentile, week change and 3-year percentile of the same managed-money net series'),
 2: ('plausible market transmission (weather demand)', 'shared input with 9; forecast counterpart of 10', 'model forecast heating degree days; point 9 is the spread across the same model runs'),
 3: ('shared input', 'plausible market transmission (positioning)', 'week-on-week change of the series behind point 1'),
 4: ('shared input', 'plausible market transmission (positioning)', '3-year percentile of the series behind point 1'),
 5: ('context or interaction (power supply)', 'shared table with 7', 'hourly wind generation, EIA-930 US48 table'),
 6: ('context or interaction (calendar state)', 'clock proxy across days', 'sessions since prompt expiry; a daily count'),
 7: ('plausible market transmission (power-sector gas burn)', 'shared table with 5', 'estimated gas burn rate from the same EIA-930 US48 table'),
 8: ('alternative measurement (positioning on another venue contract)', 'context or interaction', 'ICE Henry Hub LD1 managed-money net percentile; compare with points 1, 3, 4 (NYMEX-code report)'),
 9: ('derived transform (spread across the model runs behind 2)', 'shared input with 2', 'max absolute spread of forecast gw_hdd across models'),
 10: ('alternative measurement (observed weather for the quantity forecast by 2)', 'context or interaction', 'observed daily gw_hdd'),
 11: ('plausible market transmission (inventory)', 'shared input with 12', 'EIA weekly storage level, change and versus 5-year; event-timed, constant between releases'),
 12: ('derived transform (estimate versus actual built on 11)', 'shared input with 11', 'storage estimate against the published actual'),
 13: ('shared input with the traded instrument', 'alternative measurement (price level and term structure)', 'curve legs include the front contract NGX3 that is the traded instrument; shape features are functions of leg prices'),
}
CODEX_SHARED = {1, 2, 3, 4, 5, 7, 9, 13}; MY_SHARED = {1, 2, 3, 4, 5, 7, 9, 11, 12, 13}
rows = []
for _, c in C.iterrows():
    p = int(c.point_id); s = S[S.point.apply(lambda x: p in json.loads(x.replace("'", '"')) if x.startswith('[') else False)]
    v = s[s.distinct > 1]; oc = [c_ for c_ in v.columns if c_.startswith('rho_tk_') or c_.startswith('rho_abs_tk_')]
    rows.append(dict(point=p, name=c['name'], bound_tables=c.bound_tables, series=len(s), series_varying_in_family_order=len(v), max_distinct_values=int(s.distinct.max()), max_changes_in_family_order=int(s.changes_in_family_order.max()),
        my_primary_relationship=MY[p][0], my_secondary_relationship=MY[p][1], my_basis=MY[p][2], codex_relationship=c.relationship, closest_registry_entries='; '.join(sorted(reg.get(p, []))),
        my_shared_source_flag=p in MY_SHARED, codex_shared_source_flag=p in CODEX_SHARED, flags_agree=(p in MY_SHARED) == (p in CODEX_SHARED),
        max_abs_rho_with_family_order=float(v.rho_with_family_order.abs().max()) if len(v) else np.nan, max_abs_rho_with_traded_mid=float(v.rho_with_traded_mid.abs().max()) if len(v) else np.nan,
        max_abs_rho_with_outcomes=float(v[oc].abs().max().max()) if len(v) else np.nan, family_wise_line=float(S.null95_line_family_wise.iloc[0]), testable_within_day='yes' if len(v) else 'no: constant across the 749 families'))
X = pd.DataFrame(rows); X.to_csv(f'{T}/t7_input_crosswalk.csv', index=False); assert len(X) == 13
print(X[['point', 'series', 'series_varying_in_family_order', 'max_distinct_values', 'my_primary_relationship', 'codex_relationship', 'flags_agree', 'max_abs_rho_with_family_order', 'max_abs_rho_with_traded_mid', 'max_abs_rho_with_outcomes']].round(3).to_string())
# ---- chart: heatmap of rank correlations for the series that vary at all
V = S[S.distinct > 1].reset_index(drop=True); cols = ['rho_with_family_order', 'rho_with_traded_mid', 'rho_tk_5s', 'rho_tk_20s', 'rho_tk_60s', 'rho_abs_tk_5s', 'rho_abs_tk_20s', 'rho_abs_tk_60s']
lab = [c.replace('rho_', '').replace('with_', '').replace('family_order', 'family order*').replace('traded_mid', 'traded mid').replace('abs_tk_', '|move| ').replace('tk_', 'signed move ') for c in cols]
SURF = '#fcfcfb'; INK = '#0b0b0b'; INK2 = '#52514e'; BLUE = '#2a78d6'; ORANGE = '#eb6834'
cm = LinearSegmentedColormap.from_list('d', [ORANGE, '#f4f3f0', BLUE]); fig, ax = plt.subplots(figsize=(11, 8.2)); fig.patch.set_facecolor(SURF)
A = V[cols].to_numpy(float); im = ax.imshow(A, cmap=cm, vmin=-1, vmax=1, aspect='auto')
for i in range(A.shape[0]):
    for j in range(A.shape[1]): ax.text(j, i, f'{A[i, j]:.2f}', ha='center', va='center', fontsize=7.5, color=INK)
short = lambda s: s.replace('curve.', '').replace('front_symbol=NGX3|next_symbol=', 'NGX3/').replace('|back_rank=', ' r').replace('eia930.us48|:', 'eia ').replace('mos.gw_by_cycle|model=', 'mos ').replace('|horizon_days=', ' h').replace('|target_day=2023-10-', ' t').replace('mos.disagreement_by_cycle|:max_abs_spread_gw_hdd', 'mos disagreement spread').replace('weather.gw_daily|:gw_hdd', 'observed gw_hdd').replace(':gw_hdd', '')
ax.set_yticks(range(len(V))); ax.set_yticklabels([f'[{p}] ' + short(s) for p, s in zip(V.point.str.strip('[]'), V.series)], fontsize=7.5); ax.set_xticks(range(len(cols))); ax.set_xticklabels(lab, fontsize=8, rotation=20, ha='right')
ax.set_title('Rank correlation of every external series that varies across the 749 Oct 18 families\n* family order is a clock-proxy diagnostic; family-wise shifted-outcome 95%% line for outcome columns: %.2f' % S.null95_line_family_wise.iloc[0], loc='left', fontsize=10, color=INK)
fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02); fig.tight_layout(); fig.savefig(f'{FIG}/crosswalk-input-series-heatmap.png', dpi=150); plt.close(fig)
R = pd.read_csv(f'{FIG}/t5_chart_reconciliation.csv'); R = R[~R.figure.str.startswith('9 ')]
R = pd.concat([R, pd.DataFrame([dict(figure='9 input series heatmap', panel='all varying series x 8 columns', plotted=int(A.size), table_rows=int(len(V) * len(cols)), source='t7_input_series_measurements.csv', match=True)])], ignore_index=True); R.to_csv(f'{FIG}/t5_chart_reconciliation.csv', index=False); print('heatmap cells', A.size)
