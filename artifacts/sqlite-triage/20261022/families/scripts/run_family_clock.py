"""Read the confirmed second set, align the whole retained clock, fit no model.

Full source records are decoded and hashed, then retained by exact byte reference
instead of copying 161 GB. All plane carriers remain in their pinned source files.
"""
import concurrent.futures
import hashlib
import json
import pathlib
import sqlite3
import time
from family_clock_sources import seek_line_start

OUT = pathlib.Path('/tmp/codex-family-starts-20261022')
SOURCE = pathlib.Path('/opt/frankie-box/work/experiment-teacher-rows/20231018/host-dipole-classroom-source.c15.rows.jsonl')
SCHEMA = '''CREATE TABLE IF NOT EXISTS second_set_clock(
 source_offset INTEGER PRIMARY KEY,source_length INTEGER,input_cursor INTEGER,
 journal_ordinal INTEGER,instrument_id INTEGER,event_ns INTEGER,receive_ns INTEGER,
 known_by_ns INTEGER,raw_components_json TEXT,coverage_json TEXT,row_sha256 TEXT,issues_json TEXT)'''


def scan_partition(task):
    number, lower, upper = task
    path = OUT / ('clock-shard-%02d.sqlite' % number)
    if path.exists():
        raise RuntimeError('Preserve existing clock shard instead of overwriting: ' + str(path))
    db = sqlite3.connect(path)
    db.execute(SCHEMA)
    digest = hashlib.sha256()
    count = 0
    batch = []
    with SOURCE.open('rb') as handle:
        begin = seek_line_start(handle, lower)
        while handle.tell() < upper:
            offset = handle.tell()
            raw = handle.readline()
            if not raw:
                break
            digest.update(raw)
            issues = []
            row = json.loads(raw)
            key, clocks = row.get('key', {}), row.get('clocks', {})
            event = clocks.get('clock_event_time', {}).get('ts_event_ns')
            receive = clocks.get('clock_receive_time', {}).get('ts_recv_ns')
            known = clocks.get('clock_event_known_by')
            cursor = key.get('adapter_cursor')
            if cursor != key.get('input_cursor'):
                issues.append('adapter/input cursor difference; record retained')
            if any(type(value) is not int for value in [cursor, event, receive, known]):
                issues.append('one or more exact clocks/cursors absent; record retained')
            batch.append((offset,len(raw),cursor,key.get('input_journal_ordinal'),key.get('instrument_id'),event,receive,known,
                          json.dumps(row.get('raw_components')),json.dumps(row.get('coverage')),hashlib.sha256(raw).hexdigest(),json.dumps(issues)))
            count += 1
            if len(batch) == 1000:
                db.executemany('insert into second_set_clock values (?,?,?,?,?,?,?,?,?,?,?,?)', batch)
                db.commit()
                batch = []
        end = handle.tell()
    if batch:
        db.executemany('insert into second_set_clock values (?,?,?,?,?,?,?,?,?,?,?,?)', batch)
    db.commit()
    db.close()
    return dict(partition=number,path=str(path),begin=begin,end=end,rows=count,sha256=digest.hexdigest())


def main():
    started = time.monotonic()
    report_path = OUT / 'combined-clock-report.json'
    if report_path.exists():
        raise RuntimeError('This combined-clock run already has a report; preserve it')
    price_report = json.loads((OUT / 'price-clock-verification.json').read_text())
    if not price_report['rerun_ready_price_clocks']:
        raise RuntimeError('Price timestamp prerequisite is not verified')
    before = SOURCE.stat()
    with SOURCE.open('rb') as handle:
        header_raw = handle.readline()
        header = json.loads(header_raw)
        data_start = handle.tell()
    db = sqlite3.connect(OUT / 'family-alignment.sqlite')
    db.execute(SCHEMA)
    if db.execute('select count(*) from second_set_clock').fetchone()[0]:
        raise RuntimeError('Existing combined clock must be preserved')
    parts = 24
    boundaries = [data_start + (before.st_size - data_start) * i // parts for i in range(parts + 1)]
    manifest = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:
        for shard in pool.map(scan_partition, [(i,boundaries[i],boundaries[i+1]) for i in range(parts)]):
            manifest.append(shard)
            db.execute('attach database ? as shard', (shard['path'],))
            db.execute('insert into second_set_clock select * from shard.second_set_clock')
            db.commit()
            db.execute('detach database shard')
            print(json.dumps({'stage':'combined_clock_read','partitions_done':len(manifest),'partitions_total':parts,'second_set_rows_read':sum(x['rows'] for x in manifest)}), flush=True)
    after = SOURCE.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino) != (after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('Second-set source changed during clock read')
    if manifest[0]['begin'] != data_start or manifest[-1]['end'] != before.st_size or any(a['end'] != b['begin'] for a,b in zip(manifest,manifest[1:])):
        raise ValueError('Second-set byte partitions do not cover every source record once')
    db.executescript('''CREATE INDEX second_set_cursor ON second_set_clock(input_cursor,instrument_id);
      CREATE INDEX second_set_known ON second_set_clock(known_by_ns,input_cursor);
      CREATE VIEW trade_market_alignment AS SELECT p.*,t.source_offset AS trade_second_set_offset,
        t.source_length AS trade_second_set_length,t.known_by_ns AS trade_known_by_ns,
        t.raw_components_json AS second_set_components_at_trade,t.coverage_json AS trade_coverage,
        (SELECT max(b.source_offset) FROM second_set_clock b WHERE b.source_offset<t.source_offset) AS prior_second_set_offset,
        e.source_offset AS emitted_second_set_offset,e.known_by_ns AS emission_known_by_ns,
        t.event_ns AS second_set_trade_event_ns,t.receive_ns AS second_set_trade_receive_ns
        FROM price_clock p LEFT JOIN second_set_clock t ON t.input_cursor=p.trade_input_cursor AND t.instrument_id=p.instrument_id
        LEFT JOIN second_set_clock e ON e.input_cursor=p.group_close_input_cursor AND e.instrument_id=p.instrument_id;
      CREATE VIEW family_market_alignment AS SELECT f.*,c.source_offset AS second_set_offset,c.source_length AS second_set_length,
        c.known_by_ns,c.raw_components_json,c.coverage_json FROM family_start f
        LEFT JOIN second_set_clock c ON c.input_cursor=f.input_cursor;
      CREATE VIEW group_market_alignment AS SELECT g.*,c.source_offset AS second_set_offset,c.known_by_ns
        FROM group_event g LEFT JOIN second_set_clock c ON c.input_cursor=g.input_cursor AND c.instrument_id=g.instrument_id;
      CREATE VIEW combined_clock_events AS
        SELECT known_by_ns AS available_ns,input_cursor AS source_cursor,'second_set' AS kind,cast(source_offset as text) AS record_key FROM second_set_clock
        UNION ALL SELECT available_ns,group_close_input_cursor,'price',cast(source_ordinal as text) FROM price_clock
        UNION ALL SELECT published_ns,NULL,'external_13',point_name||':'||source_ordinal FROM external_row
        UNION ALL SELECT c.known_by_ns,f.input_cursor,'family_start',f.family_id FROM family_start f
          LEFT JOIN second_set_clock c ON c.input_cursor=f.input_cursor;''')
    counts = {table:db.execute('select count(*) from '+table).fetchone()[0] for table in ['second_set_clock','family_start','group_event','plane_registry','external_point','external_row','price_clock']}
    checks = {
        'second_set_rows_with_clock_issues':db.execute("select count(*) from second_set_clock where issues_json!='[]'").fetchone()[0],
        'duplicate_second_set_cursors':db.execute('select count(*) from (select input_cursor from second_set_clock group by input_cursor having count(*)>1)').fetchone()[0],
        'families_without_second_set_match':db.execute('select count(*) from family_market_alignment where second_set_offset is null').fetchone()[0],
        'groups_without_second_set_match':db.execute('select count(*) from group_market_alignment where second_set_offset is null').fetchone()[0],
        'trades_without_second_set_match':db.execute('select count(*) from trade_market_alignment where trade_second_set_offset is null or emitted_second_set_offset is null').fetchone()[0],
        'trade_clock_differences':db.execute('select count(*) from trade_market_alignment where event_ns!=second_set_trade_event_ns or receive_ns!=second_set_trade_receive_ns').fetchone()[0],
        'group_clock_differences':db.execute('select count(*) from group_event g join second_set_clock c on c.input_cursor=g.input_cursor where g.recv_ns!=c.receive_ns or g.event_ns!=c.event_ns').fetchone()[0],
    }
    # Repair only previously unresolved lookups from the now complete cursor index.
    repaired = 0
    with SOURCE.open('rb') as handle:
        gaps = db.execute("select family_id,point,input_cursor,cutoff_ns from prebirth_context where missing_json!='[]'").fetchall()
        for family,point,cursor,cutoff in gaps:
            refs = db.execute('select source_offset,source_length,known_by_ns from second_set_clock where input_cursor=?',(cursor,)).fetchall()
            if len(refs) != 1:
                continue
            offset,length,known = refs[0]
            handle.seek(offset)
            raw = handle.read(length)
            issues = [] if known<=cutoff else ['selected picture became available after cutoff; not eligible as prebirth evidence']
            db.execute('update prebirth_context set second_set_json=?,known_by_ns=?,missing_json=? where family_id=? and point=?',(raw.decode(),known,json.dumps(issues),family,point))
            repaired += 1
    checks['pre_start_lookups_repaired'] = repaired
    checks['pre_start_contexts_with_remaining_issues'] = db.execute("select count(*) from prebirth_context where missing_json!='[]'").fetchone()[0]
    # Walk every retained clock event; tie ordering is descriptive, not sub-cursor causality.
    event_digest = hashlib.sha256()
    events = 0
    event_counts = {}
    for available,cursor,kind,key in db.execute('select * from combined_clock_events order by available_ns,source_cursor,kind,record_key'):
        event_digest.update(json.dumps([available,cursor,kind,key],separators=(',',':')).encode()+b'\n')
        event_counts[kind] = event_counts.get(kind,0)+1
        events += 1
    binding = json.loads((OUT/'all-input-binding.json').read_text())
    report = dict(schema='FAMILY_COMBINED_CLOCK_RUN_V1',counts=counts,checks=checks,
        external_13_count=len(binding['external_13']['points']),all99_entries=counts['plane_registry'],second_set_confirmed=True,
        price_timestamp_verification=price_report,lookback_seconds=120,prediction_target=None,model_fitted=False,signals_tested=False,
        second_set_source=dict(path=str(SOURCE),bytes=before.st_size,header_sha256=hashlib.sha256(header_raw).hexdigest(),expected_rows=header.get('rows'),partitions=manifest),
        clock_events_walked=events,clock_event_counts=event_counts,clock_event_sha256=event_digest.hexdigest(),
        source_order='original input cursor retained; combined display ordered by availability, cursor and explicit tie keys',
        values='Every second-set record decoded and hashed; complete payloads retained at verified byte references. All 13 source rows and all 99 dispositions retained. Native/ROOT payloads remain in their pinned indexed source files.',
        scope='Combined chronological reconstruction only, through all retained history after starts; no two-minute post-start cutoff. Direction, momentum, exhaustion, prebirth and tradable-signal analysis follow this read.',
        missing_policy='all observations retained with explicit coverage; no family or trade excluded',seconds=round(time.monotonic()-started,2))
    db.execute('insert or replace into metadata values (?,?)',('combined_clock_report',json.dumps(report)))
    db.commit()
    report['sqlite_quick_check'] = db.execute('pragma quick_check').fetchone()[0]
    db.close()
    report_path.write_text(json.dumps(report,indent=2))
    (OUT/'second-set-clock-partitions.json').write_text(json.dumps(report['second_set_source'],indent=2))
    print(json.dumps({key:value for key,value in report.items() if key!='second_set_source'}),flush=True)


if __name__ == '__main__':
    main()

