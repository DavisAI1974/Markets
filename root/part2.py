"""ROOT part 2: runs one named calculation over one trade day and stores its output beside the stored rows.

Shape agreed by Greg (SPEC-root.md, "Part 2"): the foundation plus calculations added on top, one at a time, each
named, run tick by tick, pinning its own output and passing its own checks. A calculation never adds, removes or
changes a row. Its output is written as its own files, so nothing already stored is rewritten:
- `calc-<name>-<trade day>-partNNN.parquet`: the position on the tape and the calculation's columns, one file for
  each stored rows file and in the same row order;
- `calc-<name>-<table>-<trade day>-partNNN.parquet`: a table the calculation keeps beside the rows (for example the
  facts about peaks, each with the tick at which it became known);
- `CALC-<name>-<trade day>.json`: counts, fingerprints of the inputs and outputs, and the result of its checks.
Only the ticks of the trade day itself are calculated on; the rows of the 5 pm to 6 pm stretches and of the Sunday
start-up keep empty cells. A calculation receives its ticks through one of the two gates of `root/tape.py`, which
pass exactly the same ticks: `for_calculations()` gives the raw tape record, `rows_for_calculations()` gives the
stored row (what the tick did to the book is on the row). A calculation that names stored columns in `READS` gets
the rows; the runner then proves, on every run, that the rows gate passed the same positions as the tape gate.
Output goes to markets-data, never Markets.

    python3 -m root.run calc flow_peak 20231002 --rows <stored rows folder> --out <folder>
"""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
from pathlib import Path

from root import checks, store, tape
from root.calcs import book_totals, flow_peak, open_stories, peak_links, peak_story, quote_runs, refills, sweeps
from root.calendar import label

CALCS = {'flow_peak': flow_peak, 'peak_story': peak_story, 'book_totals': book_totals, 'quote_runs': quote_runs,
         'peak_links': peak_links, 'open_stories': open_stories, 'refills': refills, 'sweeps': sweeps}
LAID_OUT = {'flow_peak': 'markets-data STEP1_STEP2_LAYOUTS.md, piece 1 (Greg, 2026-11-16)',
            'peak_story': 'markets-data STEP1_STEP2_LAYOUTS.md, piece 2 as revised (Greg, 2026-11-16)',
            'book_totals': 'markets-data STEP2_PLAN.md, piece C (Greg, 2026-11-16)',
            'quote_runs': 'markets-data STEP2_PLAN.md, piece I, the quote\'s own runs (Greg, 2026-11-16)',
            'peak_links': 'markets-data STEP2_PLAN.md, piece A (Greg, 2026-11-16)',
            'open_stories': 'markets-data STEP2_PLAN.md, piece B (Greg, 2026-11-16)',
            'refills': 'markets-data STEP1_STEP2_LAYOUTS.md, addition L ("Try them all", Greg, 2026-11-16)',
            'sweeps': 'markets-data STEP1_STEP2_LAYOUTS.md, addition M ("Try them all", Greg, 2026-11-16)'}
POSITION = 'position_on_tape'


def gated(week, trade_day: dt.date):
    """(position on the tape, record) for every tick of the trade day, through the one gate."""
    base = tape.position_base(week)
    for f_index, r_index, record in tape.for_calculations(week):
        if label(int(record['ts_event']))[1] == trade_day:
            yield base[f_index] + r_index, record


def stream(calc, week, trade_day: dt.date, rows_folder: Path):
    """The ticks of the trade day as the calculation reads them: the stored rows when it names columns in `READS`,
    the raw tape records otherwise. Either way through a gate of `root/tape.py`."""
    if hasattr(calc, 'READS'):
        return tape.rows_for_calculations(rows_folder, trade_day, calc.READS)
    return gated(week, trade_day)


def same_ticks(week, trade_day: dt.date, full: list) -> dict:
    """The rows gate against the tape gate: the positions calculated on are exactly the trade day's ticks."""
    through_tape = [position for position, _ in gated(week, trade_day)]
    checks.need([position for position, _ in full] == through_tape,
                'the rows gate did not pass exactly the ticks that tape.for_calculations() passes')
    return dict(passed=True, ticks=len(through_tape),
                what='the stored-rows gate passed exactly the positions of tape.for_calculations() for this trade day')


def compute(calc, ticks) -> tuple:
    counts, tables = {}, {}
    return list(calc.calculate(ticks, counts, tables)), counts, tables


def known_by(tables: dict, position) -> dict:
    """The lines of each table that had become known by a tick (a table whose lines carry no tick is left out)."""
    return {name: [line for line in lines if line[0] <= position] for name, lines in tables.items()
            if name in checks.KNOWN_AT_A_TICK}


def playback(name: str, week, trade_day: dt.date, full: list, tables: dict, rows_folder: Path = None) -> list:
    """The playback check for a calculation: with the tape cut off at a tick, every value and every fact known up
    to that tick is the same as in the full run."""
    index = {position: k for k, (position, _) in enumerate(full)}
    cuts = {'the middle tick': len(full) // checks.HALVE}
    cuts.update({why: index[position] + 1 for why, position in checks.playback_cuts(name, full, tables).items()})
    out = []
    for why, cut in cuts.items():
        again, counts, again_tables = compute(CALCS[name], itertools.islice(
            stream(CALCS[name], week, trade_day, rows_folder), cut))
        last = full[cut - 1][0]
        checks.need(again == full[:cut], f'playback of {name} cut at {why}: a value up to the cut differs')
        checks.need(known_by(again_tables, last) == known_by(tables, last),
                    f'playback of {name} cut at {why}: a fact known up to the cut differs')
        out.append(dict(cut_at=why, ticks_given=cut, same_as_full_run=True))
    return out


def write(folder: Path, name: str, table_schema, columns) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_arrays([pa.array(c, type=t) for c, t in zip(columns, table_schema.types)],
                                 schema=table_schema)
    pq.write_table(table, folder / name, compression='zstd', compression_level=store.ZSTD_LEVEL,
                   use_dictionary=True, write_statistics=True, version='2.6', data_page_version='2.0')
    raw = (folder / name).read_bytes()
    return dict(file=name, rows=table.num_rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def run(tape_folder: Path, trade_day: dt.date, rows_folder: Path, out: Path, name: str) -> dict:
    """One calculation on one trade day: its output beside the stored rows, its receipt, its checks."""
    import time
    import pyarrow.parquet as pq
    started = time.monotonic()
    calc = CALCS[name]
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    row_files = tape.stored_row_files(rows_folder, trade_day)
    week = tape.read_week(tape_folder, trade_day)
    full, counts, tables = compute(calc, stream(calc, week, trade_day, rows_folder))
    gate = same_ticks(week, trade_day, full) if hasattr(calc, 'READS') else None
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
        written = write(out, f'calc-{name}-{day}-part{part:03d}.parquet', table_schema, columns)
        files.append(dict(written, beside=row_file.name,
                          beside_sha256=hashlib.sha256(row_file.read_bytes()).hexdigest()))
    checks.need(k == len(full), f'{len(full) - k} calculated ticks have no stored row')
    table_files = {}
    for table, (names, text, yes_no, decimals) in calc.TABLES.items():
        lines, table_files[table] = tables[table], []
        for part, start in enumerate(range(0, max(len(lines), 1), store.ROWS_PER_PART)):
            chunk = lines[start:start + store.ROWS_PER_PART]
            table_files[table].append(write(out, f'calc-{name}-{table}-{day}-part{part:03d}.parquet',
                                            store.schema(names, text, yes_no, decimals),
                                            [list(c) for c in zip(*chunk)] if chunk else [[] for _ in names]))
    recount = checks.CALC_CHECKS[name](row_files, [out / f['file'] for f in files], trade_day,
                                       {t: [out / f['file'] for f in fs] for t, fs in table_files.items()},
                                       Path(rows_folder))
    receipt = dict(
        what=f'ROOT part 2: the calculation {name} on one trade day',
        laid_out_and_approved=LAID_OUT[name], trade_day=trade_day.isoformat(),
        inputs=[dict(file=f.name, sha256=f.sha256) for f in week],
        columns=[dict(column=c, what=w) for c, w in calc.COLUMNS],
        tables={t: dict(columns=calc.TABLES[t][0], lines=sum(f['rows'] for f in fs), files=fs)
                for t, fs in table_files.items()},
        ticks_calculated_on=len(full), rows=sum(f['rows'] for f in files), counts=counts, files=files,
        checks=dict(recount=recount, playback=playback(name, week, trade_day, full, tables, rows_folder),
                    **({'rows_gate': gate} if gate else {})),
        empty_cells='stored as empty (null): never 0, never blank text; a calculation skips them',
        seconds=round(time.monotonic() - started, 1))
    (out / f'CALC-{name}-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt
