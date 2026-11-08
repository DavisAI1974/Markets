"""Workbook of the Claude-pass tables: regime rows and denominators, cross-day comparison, state cells, lead-lag, dipole cohort, crosswalk.
Values are copied from the committed tables (README sheet names each source); reconciliation and share columns are live formulas.  Usage: python3 -I c26_workbook.py"""
import sys; sys.path.insert(0, '.')
from odcfg import *
import pandas as pd, numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
T = f'{HERE}/tables'; OUT = f'{HERE}/claude-pass-tables-20261108.xlsx'
F = 'Arial'; HF = Font(name=F, bold=True, size=10); BF = Font(name=F, size=10); FILL = PatternFill('solid', start_color='E6E5E1')
wb = Workbook(); wb.remove(wb.active)
def sheet(name, df, note=None, fmt=None, widths=None):
    ws = wb.create_sheet(name); r0 = 1
    if note: ws.cell(1, 1, note).font = Font(name=F, italic=True, size=9); r0 = 3
    for j, c in enumerate(df.columns, 1):
        x = ws.cell(r0, j, c); x.font = HF; x.fill = FILL; x.alignment = Alignment(wrap_text=True, vertical='top')
    for i, row in enumerate(df.itertuples(index=False), r0 + 1):
        for j, v in enumerate(row, 1):
            if isinstance(v, (np.integer,)): v = int(v)
            elif isinstance(v, (np.floating,)): v = None if np.isnan(v) else float(v)
            elif isinstance(v, (np.bool_,)): v = bool(v)
            elif isinstance(v, float) and np.isnan(v): v = None
            x = ws.cell(i, j, v); x.font = BF
            if isinstance(v, float): x.number_format = fmt or '0.000'
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    for j, c in enumerate(df.columns, 1):
        w = max([len(str(c))] + [len(str(v)) for v in df.iloc[:200, j - 1].tolist()]); ws.column_dimensions[get_column_letter(j)].width = min(max(10, w * 0.95), 60)
    ws.row_dimensions[r0].height = 42; return ws, r0
# README
rd = pd.DataFrame([
 ('Regime_rows', 'tables/<date>/t3_regime_receipt.csv', 'Rows per spread regime and day, with closed-market, settle and locked/crossed rows left out. Check columns are formulas.'),
 ('Crossday_summary', 'tables/crossday/t4_crossday_summary.csv', 'Cross-day agreement counts, observed against 20 shifted-outcome draws, per regime.'),
 ('Crossday_pairs', 'tables/crossday/t4_crossday_pairs.csv', 'Every condition/outcome pair defined on all four days, per regime, rho on each day.'),
 ('Top_repeating', 'tables/crossday/t4_crossday_pairs.csv', 'Pairs sharing sign on all four days, 25 largest minimum |rho| per regime, with family label.'),
 ('State_crossday', 'tables/crossday/t4_state_crossday.csv', 'State cells by regime: next-second and next-5-second net direction, support and z per day.'),
 ('LeadLag_crossday', 'tables/crossday/t4_leadlag_crossday.csv', 'Lead-lag rank correlations by regime and lag per day.'),
 ('Dipole_cells', 'tables/dipole/t6_cohort_cells.csv', 'The 852 covered Native candidates by cell; in/against/flat counts. Share and check columns are formulas.'),
 ('Dipole_controls', 'tables/dipole/t6_cohort_controls.csv', 'Cohort shares against 500 matched-control draws.'),
 ('Dipole_vs_Codex', 'tables/dipole/t6_cohort_vs_codex.csv', 'Line-by-line agreement with Codex labels and outcome directions.'),
 ('Dipole_cases', 'tables/dipole/t6_cohort_cases.csv', 'Eight cases with source coordinates; paths in t6_cohort_case_paths.csv.'),
 ('Plane_roles', 'tables/crosswalk/t7_plane_roles.csv', '99 planes: my class from registry fields, Codex class, agreement.'),
 ('Input_crosswalk', 'tables/crosswalk/t7_input_crosswalk.csv', '13 inputs: relationship labels (my reading, proposed) and measured evidence.'),
 ('Input_series', 'tables/crosswalk/t7_input_series_measurements.csv', '93 series on the 749 Oct 18 families.')], columns=['sheet', 'source (committed table)', 'content'])
ws, _ = sheet('README', rd, note='Claude pass, tables as of 2026-11-08. Ids and timestamps are provenance, never conditions. Reported as measured; no thresholds applied.')
# Regime rows
R = pd.concat([pd.read_csv(f'{T}/{d}/t3_regime_receipt.csv') for d in DATES], ignore_index=True)
keep = ['date', 'regime', 'rows', 'pairs', 'pairs_defined', 'pairs_undefined', 'null95_line', 'grid_rows', 'closed_market_rows_left_out', 'settle_rows_left_out', 'locked_crossed_left_out']
ws, r0 = sheet('Regime_rows', R[keep].assign(date=lambda x: x.date.astype(str)), note='Check: per date, sum of regime rows + closed + settle + locked/crossed equals grid rows (column L, 0 expected).')
n = len(R); ws.cell(r0, 12, 'check (0 expected)').font = HF
for i in range(r0 + 1, r0 + 1 + n):
    ws.cell(i, 12, f'=SUMIFS($C${r0+1}:$C${r0+n},$A${r0+1}:$A${r0+n},A{i})+I{i}+J{i}+K{i}-H{i}').font = BF
sheet('Crossday_summary', pd.read_csv(f'{T}/crossday/t4_crossday_summary.csv', dtype={'regime': str}))
P = pd.read_csv(f'{T}/crossday/t4_crossday_pairs.csv', dtype={'regime': str}); sheet('Crossday_pairs', P)
TR = P[P.days_same_sign == 4].sort_values(['regime', 'min_abs_rho'], ascending=[True, False]).groupby('regime').head(25); sheet('Top_repeating', TR)
sheet('State_crossday', pd.read_csv(f'{T}/crossday/t4_state_crossday.csv', dtype={'regime': str})); sheet('LeadLag_crossday', pd.read_csv(f'{T}/crossday/t4_leadlag_crossday.csv', dtype={'regime': str}))
# Dipole
C = pd.read_csv(f'{T}/dipole/t6_cohort_cells.csv'); cols = ['dimension', 'cell', 'n', 'retro_in', 'retro_opp', 'retro_flat'] + [f'fwd{h}_{k}' for h in (1, 5, 20, 60) for k in ('in', 'opp', 'flat')]
ws, r0 = sheet('Dipole_cells', C[cols], note='Counts of oriented midpoint change: in the birth direction / against / flat. Columns after the counts are formulas.')
n = len(C); k0 = len(cols) + 1; ws.cell(r0, k0, 'retro in share').font = HF; ws.cell(r0, k0 + 1, 'retro against share').font = HF; ws.cell(r0, k0 + 2, 'fwd20 in share').font = HF; ws.cell(r0, k0 + 3, 'fwd20 against share').font = HF; ws.cell(r0, k0 + 4, 'row checks (0 expected)').font = HF
L = lambda name: get_column_letter(cols.index(name) + 1)
for i in range(r0 + 1, r0 + 1 + n):
    ws.cell(i, k0, f'={L("retro_in")}{i}/{L("n")}{i}').number_format = '0.000'; ws.cell(i, k0 + 1, f'={L("retro_opp")}{i}/{L("n")}{i}').number_format = '0.000'
    ws.cell(i, k0 + 2, f'={L("fwd20_in")}{i}/{L("n")}{i}').number_format = '0.000'; ws.cell(i, k0 + 3, f'={L("fwd20_opp")}{i}/{L("n")}{i}').number_format = '0.000'
    chk = '+'.join(f'ABS({L(p+"_in")}{i}+{L(p+"_opp")}{i}+{L(p+"_flat")}{i}-{L("n")}{i})' for p in ['retro', 'fwd1', 'fwd5', 'fwd20', 'fwd60'])
    ws.cell(i, k0 + 4, '=' + chk)
    for j in range(k0, k0 + 5): ws.cell(i, j).font = BF
sheet('Dipole_controls', pd.read_csv(f'{T}/dipole/t6_cohort_controls.csv', dtype={'regime_at_cut': str})); sheet('Dipole_vs_Codex', pd.read_csv(f'{T}/dipole/t6_cohort_vs_codex.csv'))
sheet('Dipole_cases', pd.read_csv(f'{T}/dipole/t6_cohort_cases.csv'))
sheet('Plane_roles', pd.read_csv(f'{T}/crosswalk/t7_plane_roles.csv')); sheet('Input_crosswalk', pd.read_csv(f'{T}/crosswalk/t7_input_crosswalk.csv')); sheet('Input_series', pd.read_csv(f'{T}/crosswalk/t7_input_series_measurements.csv'))
wb.save(OUT); print('saved', OUT, [ws.title for ws in wb])
