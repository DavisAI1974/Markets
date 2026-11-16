"""ROOT part 2: runs one named calculation over one trade day and stores its columns beside the stored rows.

Shape agreed by Greg (SPEC-root.md, "Part 2"): the foundation plus calculations added on top, one at a time, each
named, run tick by tick, pinning its own columns and passing its own checks. A calculation adds columns; it never
adds, removes or changes a row. Its columns are written as their own files, one for each stored rows file and in
the same row order, so nothing already stored is rewritten:
- `calc-<name>-<trade day>-partNNN.parquet`: the position on the tape and the calculation's columns;
- `CALC-<name>-<trade day>.json`: counts, fingerprints of the inputs and outputs, and the result of its checks.
Only the ticks of the trade day itself are calculated on (through `tape.for_calculations()`); the rows of the
5 pm to 6 pm stretches and of the Sunday start-up keep empty cells. Output goes to markets-data, never Markets.

    python3 -m root.run calc flow_peak 20231002 --rows <stored rows folder> --out <folder>
"""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
from pathlib import Path

from root import checks, store, tape
from root.calcs import flow_peak
from root.calendar import label

CALCS = {'flow_peak': flow_peak}
POSITION = 'position_on_tape'


def gated(week, trade_day: dt.date):
    """(position on the tape, record) for every tick of the trade day, through the one gate."""
    base = tape.position_base(week)
    for f_index, r_index, record in tape.for_calculations(week):
        if label(int(record['ts_event']))[1] == trade_day:
            yield base[f_index] + r_index, record


def playback(calc, week, trade_day: dt.date, full: list) -> list:
    """The playback check for a calculation: with the tape cut off at a tick, every value up to that tick is the
    same as in the full run. Cut at the middle tick, and on the high of the middle peak (a high not yet known)."""
    high_at = calc.NAMES.index('peak_high_position')
    highs = [values[high_at] for _, values in full if values[high_at] is not None]
    index = {position: k for k, (position, _) in enumerate(full)}
    cuts = {'the middle tick': len(full) // checks.HALVE}
    if highs:
        cuts['the high of the middle peak'] = index[highs[len(highs) // checks.HALVE]] + 1
    out = []
    for why, cut in cuts.items():
        counts = {}
        again = list(calc.calculate(itertools.islice(gated(week, trade_day), cut), counts))
        checks.need(again == full[:cut], f'playback of the calculation cut at {why}: a value up to the cut differs')
        out.append(dict(cut_at=why, ticks_given=cut, same_as_full_run=True,
                        high_still_standing_at_the_cut=counts['high_still_standing_at_the_last_tick']))
    return out


def run(tape_folder: Path, trade_day: dt.date, rows_folder: Path, out: Path, name: str) -> dict:
    """One calculation on one trade day: its columns beside the stored rows, its receipt, its checks."""
    import time
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    calc = CALCS[name]
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    row_files = sorted(Path(rows_folder).glob(f'rows-{day}-part*.parquet'))
    if not row_files:
        raise FileNotFoundError(f'no stored rows of trade day {trade_day} in {rows_folder}')
    week = tape.read_week(tape_folder, trade_day)
    counts = {}
    full = list(calc.calculate(gated(week, trade_day), counts))
    table_schema = store.schema([POSITION] + calc.NAMES, calc.TEXT, calc.YES_NO, calc.DECIMALS)
    empty = tuple(None for _ in calc.NAMES)
    files, k = [], 0
    for part, row_file in enumerate(row_files):
        positions = pq.read_table(row_file, columns=[POSITION]).column(POSITION).to_pylist()
        columns = [[] for _ in table_schema.names]
        for position in positions:
            if k < len(full) and full[k][0] < position:
                raise checks.CheckFailed(f'the tick at position {full[k][0]} was calculated on and has no stored row')
            values = empty
            if k < len(full) and full[k][0] == position:
                values, k = full[k][1], k + 1
            for column, value in zip(columns, (position,) + values):
                column.append(value)
        file_name = f'calc-{name}-{day}-part{part:03d}.parquet'
        table = pa.Table.from_arrays([pa.array(c, type=t) for c, t in zip(columns, table_schema.types)],
                                     schema=table_schema)
        pq.write_table(table, out / file_name, compression='zstd', compression_level=store.ZSTD_LEVEL,
                       use_dictionary=True, write_statistics=True, version='2.6', data_page_version='2.0')
        raw = (out / file_name).read_bytes()
        files.append(dict(file=file_name, rows=len(positions), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                          beside=row_file.name, beside_sha256=hashlib.sha256(row_file.read_bytes()).hexdigest()))
    checks.need(k == len(full), f'{len(full) - k} calculated ticks have no stored row')
    recount = checks.flow_peak(row_files, [out / f['file'] for f in files], trade_day)
    receipt = dict(
        what=f'ROOT part 2: the calculation {name} on one trade day',
        laid_out_and_approved='markets-data STEP1_STEP2_LAYOUTS.md, piece 1 (Greg, 2026-11-16)',
        trade_day=trade_day.isoformat(),
        inputs=[dict(file=f.name, sha256=f.sha256) for f in week],
        columns=[dict(column=c, what=w) for c, w in calc.COLUMNS],
        ticks_calculated_on=len(full), rows=sum(f['rows'] for f in files), counts=counts, files=files,
        checks=dict(recount=recount, playback=playback(calc, week, trade_day, full)),
        empty_cells='stored as empty (null): never 0, never blank text; a calculation skips them',
        seconds=round(time.monotonic() - started, 1))
    (out / f'CALC-{name}-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt
