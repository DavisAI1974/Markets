"""ROOT: Native's dipole beside the peaks (Step 2, piece D), on one trade day.

Laid out for Greg and approved (markets-data `STEP2_PLAN.md`, piece D, 2026-11-16; his go 2026-11-17). Native's own
stored record of each dipole is used as it is and marked as Native's: it is not a ROOT calculation, and nothing of
Native is worked out again here. Greg, ninth session: the stored record is valid and is placed as it is; on trade
days Oct 2 and Oct 17 it starts at 8 pm Eastern (00:00 UTC) and is marked so; the 6 pm to 8 pm part is added beside
it when it has been made.

What Native's record holds for each dipole (its `episode` lines, two per dipole, kept here word for word in
`native-episodes-<trade day>.jsonl.gz`):
- a line written when the dipole was recognized: the second of its birth, the second it was recognized, how the
  recognition came out;
- a closing line written later: its terminal phase and stage count, with Native's line for the candidate (its
  polarity, the sign of the signed flow, and its magnitude).
Each line carries the received time at which Native wrote it. That is when it could first be known, so each line is
placed at the first tick received at or after that time, with Native's own times beside it. A birth is in the past
when it becomes known: it is on the recognized line, never on an earlier row.

What is written, each line at the tick it could first be known:
- recognized, and closed: the dipole, Native's times and words, how many dipoles are known and not closed on each
  polarity once this tick is done, and the peaks in play (the buy peak and the sell peak most lately known, where
  each story stands, the rise under way), as `quote_peaks` writes them;
- peak known (every 20-second peak, at the tick it became known): the same counts, and the dipole most lately
  recognized that is not closed (its polarity, the time since its birth and since it was recognized).
And beside every row: how many dipoles are known and not closed on each polarity. Empty before Native's record
starts on that trade day; never zero where it is not known.

Claude's calls in the build, stated to Greg (his to correct):
- "Alive" is read as known and not closed: from the tick a dipole was recognized to the tick of its closing line.
  A dipole born and not yet recognized cannot be known at that tick, so it is not counted there.
- Native's candidate number ties its two lines together. It is a label and never an input.
- A line Native wrote outside the trade day (6 pm to 5 pm Eastern) is not placed; it is listed in the receipt.
- Native's record is built on its own fixed windows (TO REVISIT, in every handoff). Nothing is added to them here.
The rows are read through `tape.rows_for_calculations()`; Native's record is fetched file by file from its pinned
commit and each file is compared with the fingerprint in the record's own manifest.

    python3 -m root.dipole_peaks 20231002 --rows <stored rows folder> --out <folder>
"""
from __future__ import annotations

import argparse
import bisect
import concurrent.futures
import gzip
import hashlib
import io
import itertools
import json
import time
import urllib.request
from pathlib import Path

from root import checks, store, tape
from root import trade_legs as TL
from root.calcs import flow_peak, in_play
from root.calendar import parse_trade_day, trade_day_bounds

FOLDER = 'tasks/family-research-20261022/frankie-four-day-pins/native-lifecycle-42621496819-1/{day}'
SHARDED = {          # trade day -> (the commit of its markets-data record branch, the fingerprint of its MANIFEST.json)
    '20231002': ('5305008bb48160cd29d9e14887989e375449e4bb',
                 '4e001a5d59d748642bd78d2d40a6be6e3715103d4d73be339b630a69286d92a1'),
    '20231003': ('146592a9cfb8834c2880cca2275fb0f36e36899f',
                 'ee56a574a9ac3f4b8c38e1efa535dc6b49768b78c3885cabdc40141bf6101df6'),
    '20231017': ('792ae74514012748f33bb680aa3a1b03e0439c0a',
                 '2060825c84e58ce531141bdccf68a484cf447b0f7e7a21223c160dda21c436d9'),
}
ONE_FILE = {         # trade day Oct 18: an older run, kept as one file of episode lines in Markets
    '20231018': ('Markets', '3d0b06aa29781d5e39cc3eb45c6d09e174f195a2',
                 'artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/source-episode.jsonl.gz',
                 '1d39d9d89c7bed68bceafb0f0c3f554fa8503cbeee232f0797ccc07b9a3011f5'),
}
EPISODE = 'episode'
FETCHERS, TRIES = 8, 5
RECOGNIZED, CLOSED, PEAK_KNOWN = 'recognized', 'closed', 'peak known'
PLUS, MINUS = 1, -1
READS = list(in_play.READS)
RECEIVED = READS.index('received_time_ns')

ROW_COLUMNS = [
    ('native_dipoles_known_plus', 'Native\'s dipoles of polarity +1 (net buying) that are known and not closed '
     'once this tick is done. Empty before Native\'s record starts on this trade day.'),
    ('native_dipoles_known_minus', 'The same for polarity -1 (net selling).'),
    ('native_dipoles_known_no_polarity', 'The same for dipoles whose polarity Native\'s record does not give.'),
    ('dipole_peak_facts_known', 'How many lines about a dipole or a peak became known at this tick (they are in '
     'the facts file).'),
]
ROW_NAMES = [name for name, _ in ROW_COLUMNS]
FACT_COLUMNS = [
    ('known_position', 'The tick at which this line became known: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('fact', 'Recognized or closed (a line of Native\'s record placed on the tape), or peak known.'),
    ('dipole', 'Native\'s candidate number. A label only. On peak known: the dipole most lately recognized that '
     'is not closed; empty when there is none.'),
    ('native_polarity', 'Native\'s polarity for the dipole: +1 or -1, the sign of the signed flow.'),
    ('native_magnitude', 'Native\'s magnitude for the dipole.'),
    ('native_birth_ns', 'Native\'s time for the dipole\'s birth (the start of its second).'),
    ('native_recognized_ns', 'Native\'s time for its recognition (the start of its second).'),
    ('native_line_written_ns', 'The received time at which Native wrote this line. On peak known: empty.'),
    ('native_detection_lag_seconds', 'Native\'s detection lag, in seconds.'),
    ('native_orientation', 'Native\'s orientation, in its own words.'),
    ('native_recognition_outcome', 'Native\'s recognition outcome, in its own words.'),
    ('native_terminal_phase', 'On closed: Native\'s terminal phase, in its own words.'),
    ('native_stage_count', 'On closed: Native\'s stage count.'),
    ('since_birth_ns', 'From Native\'s birth time to this tick.'),
    ('since_recognized_line_ns', 'On closed and on peak known: from the tick the dipole\'s recognized line was '
     'placed to this tick.'),
    ('dipoles_known_plus', 'Dipoles of polarity +1 known and not closed once this tick is done.'),
    ('dipoles_known_minus', 'The same for polarity -1.'),
    ('dipoles_known_no_polarity', 'The same for dipoles whose polarity the record does not give.'),
    ('peak_high_position', 'On peak known: the tick of the peak\'s high. A label only.'),
    ('peak_side', 'On peak known: buy or sell.'),
] + in_play.PEAK_COLUMNS
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
OWN = len(FACT_COLUMNS) - len(in_play.PEAK_COLUMNS)


def get(repo: str, commit: str, path: str, sha256: str, size: int = None) -> bytes:
    """One pinned file, tried again a few times; refused unless it is the file its fingerprint names."""
    for attempt in range(TRIES):
        try:
            ask = urllib.request.Request(TL.RAW.format(repo=repo, commit=commit, path=path),
                                         headers={'User-Agent': TL.AGENT})
            with urllib.request.urlopen(ask, timeout=300) as answer:
                raw = answer.read()
            break
        except OSError:
            if attempt + 1 == TRIES:
                raise
            time.sleep(2 ** attempt)
    checks.need(hashlib.sha256(raw).hexdigest() == sha256 and (size is None or len(raw) == size),
                f'{path}: not the file pinned')
    return raw


def native_episodes(day: str) -> tuple:
    """Native's episode lines for one trade day, word for word and in the record's order, with where they came
    from. Trade days Oct 2, 3 and 17: every part of the stored lifecycle record is read (each compared with the
    record's manifest) and its episode lines kept. Trade day Oct 18: the one stored file of episode lines."""
    if day in ONE_FILE:
        repo, commit, path, sha256 = ONE_FILE[day]
        raw = get(repo, commit, path, sha256)
        lines = [json.dumps(json.loads(line)['original_record'], sort_keys=True)
                 for line in gzip.decompress(raw).decode().splitlines() if line]
        return lines, dict(repository=f'DavisAI1974/{repo}', commit=commit, file=path, sha256=sha256,
                           lines_in_file=len(lines), note='an older run than the other three trade days; each '
                           'line is the `original_record` of the stored line')
    commit, manifest_sha = SHARDED[day]
    folder = FOLDER.format(day=day)
    manifest = json.loads(get('markets-data', commit, f'{folder}/MANIFEST.json', manifest_sha))
    parts = [f for f in manifest['files'] if f['path'].endswith('.jsonl.gz')]

    def kept(part) -> list:
        raw = get('markets-data', commit, f'{folder}/{part["path"]}', part['sha256'], part['bytes'])
        text = gzip.decompress(raw).decode().splitlines()
        checks.need(len(text) == part['rows'], f'{part["path"]}: {len(text)} lines, the manifest says {part["rows"]}')
        return [line for line in text if '"episode"' in line and json.loads(line).get('emitting_section') == EPISODE]
    with concurrent.futures.ThreadPoolExecutor(FETCHERS) as pool:
        lines = [line for some in pool.map(kept, parts) for line in some]
    return lines, dict(repository='DavisAI1974/markets-data', commit=commit, folder=folder,
                       manifest_sha256=manifest_sha, parts_read=len(parts),
                       lines_read=sum(part['rows'] for part in parts), megabytes_read=round(
                           sum(part['bytes'] for part in parts) / 2 ** 20, 1))


def dipoles(lines: list) -> list:
    """One entry per line of Native's record, in the order Native wrote them: (written ns, kind, the dipole)."""
    by_id, out = {}, []
    for line in lines:
        row = json.loads(line)
        d = by_id.setdefault(row['candidate_id'], dict(id=row['candidate_id'], polarity=None, magnitude=None))
        if 'birth_recv_ns' in row:
            d.update(birth=row['birth_recv_ns'], recognized=row['recognized_recv_ns'],
                     lag=row.get('detection_lag_seconds'), orientation=row.get('orientation'),
                     outcome=row.get('recognition_outcome'))
            out.append((row['emitted_at_recv_ns'], RECOGNIZED, d))
        else:
            d.update(phase=row.get('terminal_phase'), stages=row.get('stage_count'))
            out.append((row['emitted_at_recv_ns'], CLOSED, d))
        candidate = row.get('candidate') or {}
        if candidate.get('polarity') is not None:      # Native's own line for the candidate, carried on its
            d.update(polarity=candidate['polarity'], magnitude=candidate.get('magnitude'))   # closing line
    for d in by_id.values():
        checks.need('birth' in d, f'{d["id"]}: a closing line with no recognized line')
    # Native wrote some closing lines at the same instant as the recognized line: the recognized line goes first
    return sorted(out, key=lambda entry: (entry[0], entry[1] != RECOGNIZED))


def follow(ticks, events: list, opens: int, halts: int, record_starts: int) -> tuple:
    """One trade day, forward only: (the row values per tick as (position, values), the lines, the lines of
    Native's record that are not placed). `events` is the output of `dipoles()`."""
    state, rows, lines, not_placed = in_play.InPlay(), [], [], []
    inside = [e for e in events if opens <= e[0] < halts]
    not_placed += [dict(dipole=e[2]['id'], line=e[1], native_line_written_ns=e[0],
                        why='written outside the trade day') for e in events if not opens <= e[0] < halts]
    known, placed_at, latest, k = {PLUS: 0, MINUS: 0, None: 0}, {}, [], 0
    seen = dict.fromkeys(in_play.SIDES)

    def line(position, received, kind, d, written=None, peak=None) -> tuple:
        row = dict.fromkeys(FACT_NAMES[:OWN])
        row.update(known_position=position, known_received_time_ns=received, fact=kind,
                   dipoles_known_plus=known[PLUS], dipoles_known_minus=known[MINUS],
                   dipoles_known_no_polarity=known[None])
        if d is not None:
            row.update(dipole=d['id'], native_polarity=d['polarity'], native_magnitude=d['magnitude'],
                       native_birth_ns=d['birth'], native_recognized_ns=d['recognized'],
                       native_line_written_ns=written, native_detection_lag_seconds=d['lag'],
                       native_orientation=d['orientation'], native_recognition_outcome=d['outcome'],
                       since_birth_ns=received - d['birth'])
            if kind != RECOGNIZED:
                row.update(since_recognized_line_ns=received - placed_at[d['id']])
            if kind == CLOSED:
                row.update(native_terminal_phase=d.get('phase'), native_stage_count=d.get('stages'))
        if peak is not None:
            row.update(peak_high_position=peak.high, peak_side=peak.side)
        return tuple(row[name] for name in FACT_NAMES[:OWN]) + state.peaks_now(received)
    for position, row in ticks:
        received = row[RECEIVED]
        state.tick(position, *row)
        new = []
        while k < len(inside) and inside[k][0] <= received:
            written, kind, d = inside[k]
            k += 1
            polarity = d['polarity'] if d['polarity'] in (PLUS, MINUS) else None
            if kind == RECOGNIZED:
                known[polarity] += 1
                placed_at[d['id']] = received
                latest.append(d)
            elif d['id'] not in placed_at:             # its recognized line was written outside the trade day
                not_placed.append(dict(dipole=d['id'], line=kind, native_line_written_ns=written,
                                       why='its recognized line was written outside the trade day'))
                continue
            else:
                known[polarity] -= 1
                latest.remove(d)
            new.append(line(position, received, kind, d, written))
        for side in in_play.SIDES:
            peak = state.last.get(side)
            if peak is not seen[side]:
                seen[side] = peak
                new.append(line(position, received, PEAK_KNOWN, latest[-1] if latest else None, peak=peak))
        lines += new
        rows.append((position, (None, None, None) if received < record_starts else
                     (known[PLUS], known[MINUS], known[None]), len(new)))
    not_placed += [dict(dipole=e[2]['id'], line=e[1], native_line_written_ns=e[0],
                        why='written after the last tick given') for e in inside[k:]]
    return rows, lines, not_placed


def recount(rows_folder: Path, trade_day, events: list, opens: int, halts: int, record_starts: int) -> tuple:
    """The second method: the tick of each of Native's lines found by where its written time falls along the
    whole column of received times; the counts by adding up along the sorted lines; the peaks in play from the
    stored outputs of pieces 1 and 2 as whole tables."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    files = tape.stored_row_files(rows_folder, trade_day)
    table = pa.concat_tables([pq.read_table(f, columns=['position_on_tape', 'row_label', 'trade_day',
                                                        'received_time_ns']) for f in files])
    text = lambda name: np.array(table.column(name).to_pylist(), dtype=object)
    d = np.flatnonzero((text('row_label') == checks.TRADE_DAY) & (text('trade_day') == trade_day.isoformat()))
    peaks_at, _, position, r = checks._in_play_as_stored(rows_folder, trade_day, table, d)
    stored_peaks = checks._peaks_as_stored(rows_folder, trade_day, position)
    moments = []                                       # (row, order within the row, kind, dipole or peak, written)
    for n, (written, kind, dip) in enumerate(e for e in events if opens <= e[0] < halts):
        row = int(np.searchsorted(r, written, side='left'))
        if row < len(r):
            moments.append((row, 0, n, kind, dip, written))
    sides = {name: k for k, name in enumerate(in_play.SIDES)}
    moments += [(p['known'], 1, sides[p['side']], PEAK_KNOWN, p, None) for p in stored_peaks]
    moments.sort(key=lambda m: m[:3])
    known, placed, latest, lines = {PLUS: 0, MINUS: 0, None: 0}, {}, [], []
    per_row, alive = {}, []
    for row, _, _, kind, what, written in moments:
        received = int(r[row])
        dip = what if kind != PEAK_KNOWN else (latest[-1] if latest else None)
        if kind == CLOSED and dip['id'] not in placed:
            continue
        if kind != PEAK_KNOWN:
            polarity = dip['polarity'] if dip['polarity'] in (PLUS, MINUS) else None
            known[polarity] += 1 if kind == RECOGNIZED else -1
            if kind == RECOGNIZED:
                placed[dip['id']] = received
                latest.append(dip)
            else:
                latest.remove(dip)
        own = dict.fromkeys(FACT_NAMES[:OWN])
        own.update(known_position=int(position[row]), known_received_time_ns=received, fact=kind,
                   dipoles_known_plus=known[PLUS], dipoles_known_minus=known[MINUS],
                   dipoles_known_no_polarity=known[None])
        if dip is not None:
            own.update(dipole=dip['id'], native_polarity=dip['polarity'], native_magnitude=dip['magnitude'],
                       native_birth_ns=dip['birth'], native_recognized_ns=dip['recognized'],
                       native_line_written_ns=written, native_detection_lag_seconds=dip['lag'],
                       native_orientation=dip['orientation'], native_recognition_outcome=dip['outcome'],
                       since_birth_ns=received - dip['birth'])
            if kind != RECOGNIZED:
                own.update(since_recognized_line_ns=received - placed[dip['id']])
            if kind == CLOSED:
                own.update(native_terminal_phase=dip.get('phase'), native_stage_count=dip.get('stages'))
        if kind == PEAK_KNOWN:
            own.update(peak_high_position=what['high'], peak_side=what['side'])
        lines.append(tuple(own[name] for name in FACT_NAMES[:OWN]) + peaks_at(row))
        per_row[row] = per_row.get(row, 0) + 1
        alive.append((row, (known[PLUS], known[MINUS], known[None])))
    at = [row for row, _ in alive]
    values = []
    for row in range(len(d)):
        j = bisect.bisect_right(at, row) - 1
        now = (0, 0, 0) if j < 0 else alive[j][1]
        values.append((int(position[row]), (None, None, None) if r[row] < record_starts else now,
                       per_row.get(row, 0)))
    return values, lines


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    opens, halts = trade_day_bounds(trade_day)
    record_starts = TL.OLD_START_NS.get(day, opens)
    kept, source = native_episodes(day)
    events = dipoles(kept)
    ticks = lambda: tape.rows_for_calculations(rows_folder, trade_day, READS)
    rows, lines, not_placed = follow(ticks(), events, opens, halts, record_starts)
    again_rows, again_lines = recount(rows_folder, trade_day, events, opens, halts, record_starts)
    for a, b in zip(lines, again_lines):
        checks.need(a == b, f'a line differs from the recount: {dict(zip(FACT_NAMES, a))} against '
                            f'{dict(zip(FACT_NAMES, b))}')
    checks.need(len(lines) == len(again_lines), f'{len(lines)} lines, {len(again_lines)} in the recount')
    checks.need(rows == again_rows, 'the counts beside the rows differ from the recount')
    waiting = [n for n, entry in enumerate(lines) if entry[2] == RECOGNIZED]
    cut = None
    if waiting:                                        # playback: cut one tick before a recognized line, when the
        middle = lines[waiting[len(waiting) // checks.HALVE]][0]      # dipole is born and cannot yet be known
        cut = [position for position, _, _ in rows].index(middle)
        cut_rows, cut_lines, _ = follow(itertools.islice(ticks(), cut), events, opens, halts, record_starts)
        checks.need(cut_rows == rows[:cut] and cut_lines == [entry for entry in lines if entry[0] < middle],
                    'playback cut one tick before a recognized line: a value or a line up to the cut differs')

    def write(name: str, names: list, columns: list, text: set = frozenset()) -> dict:
        pq.write_table(pa.Table.from_arrays([pa.array(c, type=pa.string() if n in text else None)
                                             for n, c in zip(names, columns)], names=names),
                       out / name, compression='zstd', compression_level=store.ZSTD_LEVEL)
        raw = (out / name).read_bytes()
        return dict(file=name, rows=len(columns[0]) if columns else 0, bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest())
    files, at = [], 0
    for part, row_file in enumerate(tape.stored_row_files(rows_folder, trade_day)):
        positions = pq.read_table(row_file, columns=['position_on_tape']).column('position_on_tape').to_pylist()
        columns = [[] for _ in range(len(ROW_NAMES) + 1)]
        for position in positions:
            values = (None,) * len(ROW_NAMES)
            if at < len(rows) and rows[at][0] == position:
                values, at = rows[at][1] + (rows[at][2],), at + 1
            for column, value in zip(columns, (position,) + values):
                column.append(value)
        files.append(dict(write(f'dipole-peaks-{day}-part{part:03d}.parquet', ['position_on_tape'] + ROW_NAMES,
                                columns), beside=row_file.name))
    checks.need(at == len(rows), f'{len(rows) - at} ticks of the trade day have no stored row')
    text = {'fact', 'dipole', 'native_orientation', 'native_recognition_outcome', 'native_terminal_phase',
            'peak_side'} | in_play.PEAK_TEXT
    files.append(write(f'dipole-peaks-facts-{day}.parquet', FACT_NAMES,
                       [list(c) for c in zip(*lines)] if lines else [[] for _ in FACT_NAMES], text))
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb', mtime=0) as packed:
        packed.write(('\n'.join(kept) + '\n').encode())
    (out / f'native-episodes-{day}.jsonl.gz').write_bytes(buffer.getvalue())
    files.append(dict(file=f'native-episodes-{day}.jsonl.gz', rows=len(kept), bytes=len(buffer.getvalue()),
                      sha256=hashlib.sha256(buffer.getvalue()).hexdigest()))
    kinds = [entry[2] for entry in lines]
    receipt = dict(
        what='Native\'s dipole beside the peaks: Native\'s stored record placed on the tape, each line at the tick '
             'it could first be known. Native\'s record is Native\'s; nothing of it is worked out again here',
        laid_out_and_approved='markets-data STEP2_PLAN.md, piece D (Greg, 2026-11-16; his go 2026-11-17)',
        trade_day=trade_day.isoformat(), native_record=source,
        native_record_starts='6 pm Eastern, the open of the trade day' if day not in TL.OLD_START_NS else
        '8 pm Eastern (00:00 UTC): the first two hours of the trade day are not in Native\'s stored record; the '
        'counts beside the rows are empty until then',
        to_revisit='Native\'s record is built on its own fixed windows (a 20-second roll, a level set from 85 in '
                   '100 seconds, 60-second horizons)',
        columns=[dict(column=c, what=w) for c, w in ROW_COLUMNS],
        fact_columns=[dict(column=c, what=w) for c, w in FACT_COLUMNS],
        counts=dict(native_episode_lines=len(kept), dipoles=len({e[2]['id'] for e in events}),
                    lines=len(lines), recognized=kinds.count(RECOGNIZED), closed=kinds.count(CLOSED),
                    peak_known=kinds.count(PEAK_KNOWN),
                    peak_known_with_a_dipole_known_and_not_closed=sum(
                        1 for entry in lines if entry[2] == PEAK_KNOWN and entry[3] is not None),
                    dipoles_with_no_polarity_in_the_record=sum(
                        1 for d in {e[2]['id']: e[2] for e in events}.values() if d['polarity'] not in (PLUS, MINUS)),
                    native_lines_not_placed=len(not_placed)),
        native_lines_not_placed=not_placed,
        checks=dict(passed=True, lines_compared=len(lines), rows_compared=len(rows),
                    playback=None if cut is None else dict(cut_at='one tick before the middle recognized line',
                                                           ticks_given=cut, same_as_full_run=True),
                    method='the tick of every line of Native\'s record found again along the whole column of '
                           'received times; the counts added up along the sorted lines; the peaks in play from '
                           'the stored outputs of pieces 1 and 2 as whole tables'),
        empty_cells='stored as empty (null): never 0, never blank text', files=files,
        seconds=round(time.monotonic() - started, 1))
    (out / f'DIPOLE-PEAKS-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='Native\'s dipole beside the peaks')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
