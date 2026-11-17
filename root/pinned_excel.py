"""ROOT: the pinned dipoles and the exhaustion peak pages as one Excel file.

    python3 -m root.pinned_excel <out.xlsx> <folder holding rows-<trade day>/> <peak research folder>

Write the stored pinned-dipole tables and the index of the exhaustion peak pages as one Excel file (a sheet per
trade day for each), every row linked to its picture on GitHub, and read the values back."""
import datetime as dt, sys
from pathlib import Path
import pyarrow.parquet as pq
from openpyxl import Workbook, load_workbook
from zoneinfo import ZoneInfo
out, ROWS, R = Path(sys.argv[1]), sys.argv[2], sys.argv[3]   # the workbook; the folder holding rows-<trade day>/; the peak research folder
E = ZoneInfo('America/New_York')
LINK = 'https://github.com/DavisAI1974/markets-data/blob/root-rows-{day}/renders/{name}'
days = ['20231002', '20231003', '20231017', '20231018']
eastern = lambda ns: dt.datetime.fromtimestamp(ns // 10**9, tz=dt.timezone.utc).astimezone(E).strftime('%Y-%m-%d %H:%M:%S')
wb = Workbook(); wb.remove(wb.active)
first = wb.create_sheet('READ ME')
for line in ['Native\'s dipoles pinned to their birth seconds on OUR tape, and every exhaustion peak with the page it is drawn on.',
             'Sheets named "dipoles <trade day>": one row per dipole. Sheets named "peaks <trade day>": one row per exhaustion peak (the 20-second peaks).',
             'Tap the name in the picture column to open that picture on GitHub (the renders folder of that trade day\'s root-rows branch).',
             'Written from renders/dipoles-pinned-<trade day>.parquet and renders/exhaustion-sheets-index-<trade day>.parquet (the exact record). Nothing is averaged.',
             'born_eastern and high_eastern are added here for reading; every other column is the stored value.',
             'Times ending _ns are written as text (19 digits; Excel would round them as numbers). Empty cells are empty: never zero.',
             'Excel keeps a decimal to about 15 digits, so a decimal here can differ from the stored value in its last digit. The stored files are the exact record.',
             'A trade day runs 6 pm Eastern the evening before to 5 pm Eastern on the named date.',
             'These pictures use the 20-second flow. Greg, 2026-11-17: the 20-second flow is kept, and a line made at the tick is added beside it; the next pictures are three separate graphs (price, dipole, exhaustion).']:
    first.append([line])
kept = {}
for d in days:
    label = f'{d[:4]}-{d[4:6]}-{d[6:]}'
    t = pq.read_table(f'{ROWS}/rows-{d}/renders/dipoles-pinned-{d}.parquet'); names = t.column_names
    sheet = wb.create_sheet(f'dipoles {label}'); sheet.append(['born_eastern'] + names)
    rows = t.to_pylist(); kept['dipoles', d] = (names, rows, None)
    at = names.index('render') + 2
    for k, r in enumerate(rows, start=2):
        sheet.append([eastern(r['native_birth_ns'])] + [str(r[n]) if n.endswith('_ns') and r[n] is not None else r[n] for n in names])
        sheet.cell(row=k, column=at).hyperlink = LINK.format(day=d, name=r['render'])
    when = {p['peak_high_position']: p['peak_high_received_time_ns'] for p in pq.read_table(f'{R}/peaks-by-place-in-the-move-{d}.parquet', columns=['peak_kind', 'peak_high_position', 'peak_high_received_time_ns']).to_pylist() if p['peak_kind'] == '20-second flow'}
    t = pq.read_table(f'{ROWS}/rows-{d}/renders/exhaustion-sheets-index-{d}.parquet'); names = t.column_names
    sheet = wb.create_sheet(f'peaks {label}'); sheet.append(['high_eastern'] + names)
    rows = t.to_pylist(); kept['peaks', d] = (names, rows, when)
    at = names.index('sheet') + 2
    for k, r in enumerate(rows, start=2):
        sheet.append([eastern(when[r['peak_high_position']])] + [r[n] for n in names])
        sheet.cell(row=k, column=at).hyperlink = LINK.format(day=d, name=r['sheet'])
wb.save(out)
back = load_workbook(out, read_only=True)
for (kind, d), (names, rows, _) in kept.items():
    it = back[f'{kind} {d[:4]}-{d[4:6]}-{d[6:]}'].iter_rows(values_only=True); next(it)
    n = 0
    for want, got in zip(rows, it):
        got = tuple(got) + (None,) * (len(names) + 1 - len(got))
        for name, cell in zip(names, got[1:]):
            v = want[name]
            if isinstance(v, float) and isinstance(cell, (int, float)):      # Excel keeps a decimal to about 15 digits
                assert abs(v - cell) <= 1e-12 * max(1.0, abs(v)), (kind, d, n, name, v, cell)
            else:
                assert (str(v) if name.endswith('_ns') and v is not None else v) == cell, (kind, d, n, name, v, cell)
        n += 1
    assert n == len(rows), (kind, d, n, len(rows))
    print(kind, d, 'rows', n, 'read back equal')
print('bytes', out.stat().st_size)
