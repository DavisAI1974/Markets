"""Recover original trade nanoseconds. This does not run family analysis."""
import bisect
import concurrent.futures
import csv
import gzip
import hashlib
import json
import math
import pathlib
import sqlite3
import sys
import time

OUT = pathlib.Path('/tmp/codex-family-starts-20261022')
JOURNAL = '/opt/frankie-box/work/ingest-20231018-gh-36571235912-1/journal.compact.sqlite'
# Read the plain INPUT scalar fields without importing model dependencies.
# Unused byte payloads remain encoded in the untouched journal source.
from family_clock_sources import unpack


def read_block(task):
    start, wanted = task
    journal = sqlite3.connect('file:' + JOURNAL + '?mode=ro', uri=True)
    body, digest = journal.execute('select body,sha256 from blocks where start=?', (start,)).fetchone()
    journal.close()
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('Original journal block digest changed at ' + str(start))
    decoded = json.loads(gzip.decompress(body))
    if decoded[0] != 'C15_EXACT_ORDER_BLOCK_GZIP_V1':
        raise ValueError('Unknown journal block encoding')
    found = {}
    for encoded in decoded[2]:
        ordinal, kind = encoded[:2]
        if ordinal not in wanted:
            continue
        entry = unpack(encoded[2])
        payload = entry['payload']
        if kind != 'INPUT' or payload.get('cursor') != wanted[ordinal]:
            raise ValueError('Original journal ordinal/cursor mismatch')
        found[wanted[ordinal]] = (ordinal, payload['record'], encoded[4], start, digest)
    return found


def main():
    begun = time.monotonic()
    db = sqlite3.connect(OUT / 'family-alignment.sqlite')
    prices = [(ordinal, unpack_json(row)) for ordinal, row in db.execute('select source_ordinal,row_json from price_row order by source_ordinal')]
    journal = sqlite3.connect('file:' + JOURNAL + '?mode=ro', uri=True)
    blocks = journal.execute('select start,count from blocks order by start').fetchall()
    seal = journal.execute('select * from seal').fetchall()
    journal.close()
    starts = [row[0] for row in blocks]
    tasks = {}
    for _, row in prices:
        cursor = row['provenance']['input_index']
        ordinal = cursor * 2
        block = bisect.bisect_right(starts, ordinal) - 1
        if block < 0 or ordinal >= blocks[block][0] + blocks[block][1]:
            raise ValueError('Trade ordinal is outside original journal block coverage')
        tasks.setdefault(starts[block], {})[ordinal] = cursor
    exact = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:
        for number, found in enumerate(pool.map(read_block, sorted(tasks.items()), chunksize=4), 1):
            exact.update(found)
            if number % 500 == 0:
                print(json.dumps({'stage': 'price_timestamp_verification_only', 'blocks_read': number, 'blocks_needed': len(tasks), 'trade_inputs_found': len(exact)}), flush=True)
    db.execute('''CREATE TABLE IF NOT EXISTS price_clock(
        source_ordinal INTEGER PRIMARY KEY, trade_input_cursor INTEGER,
        trade_journal_ordinal INTEGER, group_close_input_cursor INTEGER,
        instrument_id INTEGER, event_ns INTEGER, receive_ns INTEGER,
        available_ns INTEGER, price REAL, price_raw INTEGER, size INTEGER,
        entry_hash TEXT, block_start INTEGER, block_sha256 TEXT,
        issues_json TEXT, timestamp_basis TEXT)''')
    result_rows = []
    for ordinal, row in prices:
        provenance = row['provenance']
        cursor = provenance['input_index']
        close = provenance['group_close_input_index']
        instrument = provenance['instrument_id']
        found = exact.get(cursor)
        issues = []
        journal_ordinal = event = receive = raw_price = size = entry_hash = block_start = block_hash = None
        if found is None:
            issues.append('original trade input not located; row retained')
        else:
            journal_ordinal, record, entry_hash, block_start, block_hash = found
            event, receive, raw_price, size = (record.get(k) for k in ['ts_event', 'ts_recv', 'price', 'size'])
            if record.get('action') != 'T':
                issues.append('source input action differs from trade')
            if record.get('instrument_id') != instrument:
                issues.append('source input instrument differs')
            if not math.isclose(row['price'], raw_price / 1_000_000_000, rel_tol=0, abs_tol=1e-12):
                issues.append('source input price differs')
            if row['size'] != size:
                issues.append('source input size differs')
            for name, stamp in [('ts_recv', receive), ('ts_event', event)]:
                if abs(row[name] - stamp / 1_000_000_000) > 0.000001:
                    issues.append('legacy floating-point ' + name + ' differs by more than one microsecond')
        available = db.execute('select recv_ns from group_event where input_cursor=? and instrument_id=?', (close, instrument)).fetchall()
        if len(available) != 1:
            issues.append('group close availability not uniquely located; row retained')
            available_ns = None
        else:
            available_ns = available[0][0]
        result_rows.append((ordinal, cursor, journal_ordinal, close, instrument, event, receive, available_ns, row['price'], raw_price, size, entry_hash, block_start, block_hash, json.dumps(issues), 'original journal integer nanoseconds; availability at emitted group close'))
    db.executemany('insert or replace into price_clock values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', result_rows)
    db.execute('''UPDATE price_row SET recv_ns=(select receive_ns from price_clock c where c.source_ordinal=price_row.source_ordinal),
        event_ns=(select event_ns from price_clock c where c.source_ordinal=price_row.source_ordinal),
        input_cursor=(select group_close_input_cursor from price_clock c where c.source_ordinal=price_row.source_ordinal)''')
    db.executescript('''CREATE INDEX IF NOT EXISTS price_available ON price_clock(available_ns,group_close_input_cursor);
        DROP VIEW IF EXISTS prebirth_prices;
        CREATE VIEW prebirth_prices AS SELECT f.family_id AS target_family_id,f.start_recv_ns,p.*,c.available_ns,
            c.trade_input_cursor,c.group_close_input_cursor FROM family_start f JOIN price_clock c
            ON c.available_ns>=f.window_start_ns AND c.available_ns<f.start_recv_ns
            AND c.group_close_input_cursor<f.input_cursor JOIN price_row p ON p.source_ordinal=c.source_ordinal;''')
    columns = [column[1] for column in db.execute('pragma table_info(price_clock)')]
    with (OUT / 'price-curve-timestamps.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(result_rows)
    counts = db.execute("select count(*),sum(event_ns is not null and receive_ns is not null),sum(available_ns is not null),sum(issues_json!='[]') from price_clock").fetchone()
    report = dict(schema='FAMILY_PRICE_CLOCK_VERIFICATION_V1', price_rows=counts[0], exact_trade_event_and_receive_rows=counts[1], group_close_availability_rows=counts[2], rows_with_issues=counts[3],
        journal_path=JOURNAL, journal_seal=seal, journal_blocks_read=len(tasks), source_blocks_digest_verified=True,
        timestamp_basis='original journal integer nanoseconds, never rounded float seconds',
        source_joins='price provenance input_index -> individually verified original INPUT ordinal/cursor; group_close_input_index plus instrument -> exact group availability',
        missing_policy='retain every price row and family; list source discrepancies',
        scope='price timestamp recovery and source verification only; no family rerun, model, target or signal analysis',
        rerun_ready_price_clocks=counts[0]==counts[1]==counts[2] and counts[3]==0,
        seconds=round(time.monotonic()-begun,2))
    db.execute('insert or replace into metadata values (?,?)', ('price_clock_verification', json.dumps(report)))
    db.commit()
    report['sqlite_quick_check'] = db.execute('pragma quick_check').fetchone()[0]
    db.close()
    (OUT / 'price-clock-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


def unpack_json(raw):
    # The first working export had already decoded containers but retained
    # float64 markers. Decode only those scalars and preserve the original row.
    def convert(value):
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        if isinstance(value, list) and value and value[0] == 'float64':
            return unpack(value)
        if isinstance(value, list):
            return [convert(item) for item in value]
        return value
    return convert(json.loads(raw))


if __name__ == '__main__':
    main()
