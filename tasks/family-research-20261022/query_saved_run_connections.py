"""Read the preserved SQLite member in memory; link originals, never refit or impute."""
import collections
import csv
import gzip
import io
import json
from pathlib import Path
import sqlite3
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/sqlite-triage/20261022/families'
TRADE = BASE / 'trade-lifecycle-targeted-v1'
OUT = TRADE / 'completed-run-connections-v1'
ARCHIVE = ROOT / 'artifacts/recovered-c-drive/20261022/git-preserved-local-files-v1/12-full-context-continuation-v1.tar.gz.manifest.json'


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        for line in handle:
            yield json.loads(line)


def write_rows(name, records):
    with (OUT / name).open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as handle:
            for record in records:
                handle.write((json.dumps(record, separators=(',', ':'), allow_nan=False) + '\n').encode())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def open_original_database():
    manifest = json.loads(ARCHIVE.read_text())
    # Already verified Git parts; no loose archive/database restoration or rehash.
    stream = io.BytesIO(b''.join((ROOT / p['file']).read_bytes() for p in manifest['parts']))
    with tarfile.open(fileobj=stream, mode='r|gz') as archive:
        for member in archive:
            if member.name == 'episode-path-audit-v1/lifecycle_asof.sqlite':
                source = sqlite3.connect(':memory:')
                source.deserialize(archive.extractfile(member).read())
                source.execute('PRAGMA query_only=ON')
                source.execute('PRAGMA temp_store=MEMORY')
                return source, member.name, member.size
    raise RuntimeError('Exact saved SQLite member missing')


def navigation_database(trades, cases):
    nav = sqlite3.connect(':memory:')
    nav.execute('PRAGMA temp_store=MEMORY')
    nav.executescript('''
        CREATE TABLE trade(ordinal INTEGER PRIMARY KEY, instrument INTEGER,
                           receive_ns INTEGER, known_by_ns INTEGER, cursor INTEGER, size INTEGER);
        CREATE TABLE case_context(line INTEGER PRIMARY KEY, instance INTEGER, instrument INTEGER,
                                  start_ns INTEGER, cutoff_ns INTEGER, pre_cursor INTEGER);
        CREATE INDEX case_time ON case_context(instrument,start_ns,line);
        CREATE INDEX trade_cursor ON trade(instrument,cursor);
    ''')
    nav.executemany('INSERT INTO trade VALUES(?,?,?,?,?,?)', [
        (int(t['source_ordinal']), int(t['instrument_id']), int(t['receive_ns']),
         int(t['available_ns']), int(t['group_close_input_cursor']), int(t['size'])) for t in trades])
    nav.executemany('INSERT INTO case_context VALUES(?,?,?,?,?,?)', [
        (i, c['instance'], c['instrument_id'], c['start_receive_ns'], c['decision_cutoff_ns'],
         c['pre_input_cursor']) for i, c in enumerate(cases, 1)])
    return nav


def neighboring_cases(nav, instrument, receive_ns):
    # Equal-time contexts stay in the prior-or-equal set; all members remain addressable.
    prior = nav.execute('''SELECT line FROM case_context WHERE instrument=? AND start_ns<=?
                           ORDER BY start_ns DESC,line DESC LIMIT 1''', (instrument, receive_ns)).fetchone()
    later = nav.execute('''SELECT line FROM case_context WHERE instrument=? AND start_ns>?
                           ORDER BY start_ns,line LIMIT 1''', (instrument, receive_ns)).fetchone()
    bounds = nav.execute('SELECT MIN(line),MAX(line) FROM case_context WHERE instrument=?', (instrument,)).fetchone()
    return dict(nearest_prior_or_equal_start_line=None if prior is None else prior[0],
                nearest_later_start_line=None if later is None else later[0],
                all_prior_or_equal_start_line_range=None if prior is None else [bounds[0], prior[0]],
                all_later_start_line_range=None if later is None else [later[0], bounds[1]])


def lineage_connections(source, wanted):
    """Keep node and parent associations separately, including late and censored records."""
    result = collections.defaultdict(list)
    for sha, known, cursor, instrument, raw in source.execute(
            "SELECT record_sha256,known_by_ns,input_cursor,instrument_id,row_json FROM record WHERE section='lineage'"):
        record = json.loads(raw)
        for field in ('node_id', 'parent_id'):
            identity = record.get(field)
            if identity is None or not identity.startswith('ord-'):
                continue
            order_id = int(identity[4:])
            if (instrument, order_id) not in wanted:
                continue
            result[(instrument, order_id)].append(dict(
                original_file='../source-lineage.jsonl.gz', record_sha256=sha,
                known_by_ns=known, input_cursor=cursor, instrument_id=instrument,
                matching_identity_field=field, node_id=record.get('node_id'), parent_id=record.get('parent_id'),
                entered_recv_ns=record.get('entered_recv_ns'), exited_recv_ns=record.get('exited_recv_ns'),
                source_status=record.get('status'), source_side_orientation=record.get('side_orientation'),
                source_role=record.get('role'), source_transition_type=record.get('transition_type')))
    for links in result.values():
        links.sort(key=lambda r: (r['known_by_ns'], r['input_cursor'], r['record_sha256'], r['matching_identity_field']))
    return result


def main():
    OUT.mkdir(exist_ok=True)
    master = json.loads((BASE / 'completed-run-source-list.json').read_text())
    assert len(master['original_99_plane_records']) == 99
    with (BASE / 'price-curve-timestamps.csv').open(newline='') as handle:
        trades = list(csv.DictReader(handle))
    assert len(trades) == 30739
    cases = list(rows(BASE / 'instance-market-review-20261023/individual-instance-records.jsonl.gz'))
    cases.sort(key=lambda c: (c['instrument_id'], c['start_receive_ns'], c['instance']))
    assert len(cases) == 749
    assert len({c['instrument_id'] for c in cases}) == 1  # Range pointers are for this retained instrument.
    nav = navigation_database(trades, cases)
    source, member, member_bytes = open_original_database()
    section_counts = dict(source.execute('SELECT section,COUNT(*) FROM record GROUP BY section'))
    assert sum(section_counts.values()) == 388640
    print('Original SQLite loaded read-only in memory; linking saved contexts.', flush=True)

    context_rows = []
    for line, case in enumerate(cases, 1):
        context_rows.append(dict(
            context_line=line, **{k: case[k] for k in (
                'instance', 'family_id', 'sample_id', 'instrument_id', 'start_receive_ns', 'start_event_ns',
                'decision_cutoff_ns', 'cursor_cap', 'pre_source_ordinal', 'pre_known_by_ns', 'pre_input_cursor',
                'forecast_disposition')},
            original_nested_case=dict(file='../../instance-market-review-20261023/individual-instance-records.jsonl.gz',
                                      line_number=case['instance']),
            readable_case=f'../../instance-market-review-20261023/cases/{case["instance"]:04d}.md',
            original_forecast_rows=len(case['forecasts']),
            interpretation='Original family-context forecasts and outcomes; never a forecast of an unmatched trade'))
    write_rows('all-749-original-model-context-links.jsonl.gz', context_rows)

    removals = list(rows(TRADE / 'each-removal-with-original-order-evidence.jsonl.gz'))
    removal_at = collections.defaultdict(list)
    wanted = set()
    for line, row in enumerate(removals, 1):
        original = row['original_removal_record']
        key = (original['instrument_id'], original['original_record']['order_id'])
        wanted.add(key)
        removal_at[(original['instrument_id'], original['input_cursor'])].append((line, key, row))
    roles = json.loads((TRADE / 'quote-order-gapfill-v1/role-reconciliation-v1/all-32-trade-role-reconciliation.json').read_text())
    bounded_t_ids = {r['trade_ordinal']: (int(r['original_trade']['instrument_id']), r['original_T']['order_id']) for r in roles}
    wanted.update(bounded_t_ids.values())
    links = lineage_connections(source, wanted)
    order_lines = {}
    order_rows = []
    for line, key in enumerate(sorted(wanted), 1):
        order_lines[key] = line
        order_rows.append(dict(order_link_line=line, instrument_id=key[0], order_id=key[1],
                               all_original_lineage_associations=links.get(key, []),
                               interpretation='Constructed lineage association only; not matching execution quantity, exchange priority, order survival or causation',
                               no_match_meaning='No association in this saved selected source; not absence from original market data'))
    write_rows('all-observed-removal-and-bounded-T-order-lineage-links.jsonl.gz', order_rows)

    stats = collections.Counter()
    def trade_rows():
        for i, trade in enumerate(trades):
            assert int(trade['source_ordinal']) == i
            instrument, cursor = int(trade['instrument_id']), int(trade['group_close_input_cursor'])
            removals_here = removal_at.get((instrument, cursor), [])
            order_keys = {key for _, key, _ in removals_here}
            if i in bounded_t_ids:
                order_keys.add(bounded_t_ids[i])
            order_refs = [dict(file='all-observed-removal-and-bounded-T-order-lineage-links.jsonl.gz',
                               line_number=order_lines[key], order_id=key[1],
                               associations_known_after_trade_group=sum(x['known_by_ns'] > int(trade['available_ns']) for x in links.get(key, [])),
                               associations_at_later_cursor=sum(x['input_cursor'] > cursor for x in links.get(key, []))) for key in sorted(order_keys)]
            nearby = neighboring_cases(nav, instrument, int(trade['receive_ns']))
            exact_contexts = [r[0] for r in nav.execute(
                'SELECT line FROM case_context WHERE instrument=? AND pre_cursor=? ORDER BY line', (instrument, cursor))]
            stats['trades'] += 1
            stats['trades_with_same_emission_removals'] += bool(removals_here)
            stats['trades_with_order_lineage_associations'] += any(links.get(k) for k in order_keys)
            stats['trades_with_later_known_lineage_associations'] += any(
                x['known_by_ns'] > int(trade['available_ns']) for k in order_keys for x in links.get(k, []))
            stats['trades_sharing_original_model_pre_group'] += bool(exact_contexts)
            yield dict(trade_ordinal=i, original_trade=trade,
                       exact_clocks={k: int(trade[k]) for k in (
                           'event_ns', 'receive_ns', 'available_ns', 'trade_input_cursor', 'group_close_input_cursor', 'trade_journal_ordinal')},
                       all_run_evidence_index='run-evidence-index.json',
                       original_model_context_index='all-749-original-model-context-links.jsonl.gz',
                       model_context_navigation=nearby, exact_shared_model_pre_group_lines=exact_contexts,
                       model_context_rule='Temporal neighbors and a shared group are context links, not model attribution or per-trade predictions. All earlier and later contexts remain eligible.',
                       same_emission_removal_refs=[dict(file='../each-removal-with-original-order-evidence.jsonl.gz', line_number=line,
                                                        interpretation=row['source_bound_interpretation']) for line, _, row in removals_here],
                       order_lineage_refs=order_refs,
                       bounded_original_T_identity=None if i not in bounded_t_ids else dict(
                           order_id=bounded_t_ids[i][1], original_file='../quote-order-gapfill-v1/role-reconciliation-v1/all-32-trade-role-reconciliation.json',
                           array_ordinal=i - 118),
                       shared_group_limit='A group can contain several prints and removals. Do not allocate a removal or its descendants to an individual execution merely from this join.',
                       quantity_gap_status='UNRESOLVED' if i in (119, 134) else 'NO_NEW_QUANTITY_RESOLUTION_CLAIM',
                       semantic_coverage='NOT_PASSED')
    write_rows('every-trade-completed-run-and-lineage-links.jsonl.gz', trade_rows())

    quantity_counts = collections.Counter()
    def quantity_rows():
        for sha, known, cursor, instrument, raw in source.execute(
                "SELECT record_sha256,known_by_ns,input_cursor,instrument_id,row_json FROM record WHERE section='absorption' ORDER BY instrument_id,input_cursor,record_sha256"):
            record = json.loads(raw)
            matching = nav.execute('SELECT ordinal,size FROM trade WHERE instrument=? AND cursor=? ORDER BY ordinal', (instrument, cursor)).fetchall()
            total = sum(size for _, size in matching)
            comparison = None if not matching else record['traded_quantity'] == total
            quantity_counts['absorption_records'] += 1
            quantity_counts['with_original_tape_prints'] += bool(matching)
            quantity_counts['source_traded_quantity_differs_from_unique_tape_sum'] += comparison is False
            yield dict(original_absorption_ref=dict(file='../source-absorption.jsonl.gz', record_sha256=sha,
                                                    known_by_ns=known, input_cursor=cursor, instrument_id=instrument),
                       original_trade_ordinals=[ordinal for ordinal, _ in matching], original_tape_quantity=None if not matching else total,
                       source_traded_quantity=record['traded_quantity'], source_displayed_depletion=record['displayed_depletion'],
                       source_withdrawn_quantity=record['withdrawn_quantity'], source_side=record['side'],
                       source_disposition=record['disposition'], equality=comparison,
                       interpretation='Different measurement definitions: reference adapter sums F and T; C can be fill cleanup. Equality or difference does not establish missing executions, unique displayed depletion or absorption.')
    write_rows('all-6265-absorption-to-original-tape-links.jsonl.gz', quantity_rows())
    save('sqlite-query-receipt.json', dict(
        status='SAVED_SQLITE_AND_COMPLETED_RUN_CONNECTED_WITH_ORIGINALS_RETAINED',
        source_master='../../completed-run-source-list.json', original_source_master_unchanged=True,
        screenshot_run_checkpoint='682b69b3b992ab1dddfb2165d9d84e5e2b93c237',
        new_deep_inventory_checkpoint='5470b27b5a9219cfe701c1f11375e6e8d301f1a0',
        original_sqlite_member=member, original_sqlite_bytes=member_bytes,
        database_loaded_in_memory=True, database_query_only=True, sqlite_temp_store='MEMORY',
        original_record_sections=section_counts, counts=dict(stats), quantity_definition_checks=dict(quantity_counts),
        original_model_contexts=len(cases), original_case_forecast_rows=sum(len(c['forecasts']) for c in cases),
        order_ids_indexed=len(wanted), order_ids_with_lineage_associations=len(links),
        lineage_associations=sum(len(v) for v in links.values()),
        lineage_node_and_parent_roles_kept_separate=True, original_trade_fields_unchanged=True,
        discarded_trades=0, raw_source_reads=0, source_retrievals=0, aws_operations=0, fits=0,
        janus_hipporag_execution_attribution='UNVERIFIED; screenshot identifies completed family-model run, not a separate execution receipt',
        semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED'))
    source.close()
    nav.close()
    print(json.dumps(dict(trades=stats, quantity_definitions=quantity_counts, order_ids_with_lineage=len(links))), flush=True)


if __name__ == '__main__':
    main()
