"""Author whole Monday inputs and a preopen Tuesday forecast from sealed evidence.

Reads both Monday source members through the recovered journal. No intraday
cutoff, source replay, model call, prefix copy, or historical Memory A input.
The terminal Monday trade is a certified prior reference, not an official settle.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from frankie_box_prepare_trading_day import (  # noqa: E402
    ORIGINAL_CONTAINER, OUTPUT_PARENT, read_pin, require_checkout, safe_path, save_new, sync_directory, witness)

RECOVERY = Path('/opt/frankie-box/work/sealed-recovery-35796793428')
AUTHOR_PARENT = Path('/opt/frankie-box/work/monday-launch')
INSTRUMENT = 111313
OPEN_NS = 1633298400000000000    # 2021-10-03T22:00:00Z, the declared CME trading-day open
CLOSE_NS = 1633381200000000000   # 2021-10-04T21:00:00Z, the declared halt
PRICE_SCALE = 10**9
SENTINEL = 2**63 - 1
TARGET_OPEN_NS = 1633384800000000000  # 2021-10-04T22:00Z
TARGET_CLOSE_NS = 1633467600000000000  # 2021-10-05T21:00Z


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def price(raw):
    return float(Decimal(raw) / PRICE_SCALE)


def fresh(path, parent):
    path = safe_path(path)
    if path.parent != parent or not re.fullmatch('[A-Za-z0-9_-]{1,96}', path.name) or path.exists():
        raise ValueError('fresh named root required under ' + str(parent))
    return path


def query_offsets(seed, cycle_index):
    times = sorted({int(digest({'seed': seed, 'cycle_index': cycle_index, 'ordinal': j}), 16)
                    % (TARGET_CLOSE_NS - TARGET_OPEN_NS) + 1 for j in range(8)})
    return times


def measure(view, completion, progress=None):
    """Read complete source coverage and certify the last available Monday trade."""
    from research.kalshi.frankie_boss.context_session import journal_prefix
    final = view.chain.next_cursor - 1
    lines, group_start, member = [], None, None
    as_of = source_as_of = records = entity_rows = other_rows = 0
    entity = prior_close = None

    def close(end):
        nonlocal group_start
        lines.append(canonical(dict(cursor_start=group_start, cursor_end=end)) + b'\n')
        group_start = None

    rows = journal_prefix(view, final)
    if progress is not None:
        rows = progress.track(rows, completion['record_count'], 'full-monday-source-binding')
    for row in rows:
        cursor, record, normal = row['cursor'], row['raw_record'], row['normalized']
        if cursor != records:
            raise ValueError('Monday source cursor continuity differs')
        records += 1
        if member is not None and row['source_member_index'] != member and group_start is not None:
            close(cursor - 1)
        member = row['source_member_index']
        if group_start is None:
            group_start = cursor
        as_of = max(as_of, normal['ts_recv_ns'])
        source_as_of = max(source_as_of, normal['ts_event_ns'])
        key = (record['publisher_id'], record['instrument_id'])
        if record['instrument_id'] == INSTRUMENT and entity is None:
            entity = key
        if key == entity:
            entity_rows += 1
        else:
            other_rows += 1
        if (key == entity and record.get('action') == 'T'
                and type(record.get('price')) is int and 0 < record['price'] < SENTINEL
                and OPEN_NS <= normal['ts_event_ns'] < CLOSE_NS):
            mark = dict(event_ns=normal['ts_event_ns'], receive_ns=normal['ts_recv_ns'],
                        price=price(record['price']),
                        evidence_hash=hashlib.sha256(record['dbn_wire_bytes']).hexdigest())
            if prior_close is None or mark['event_ns'] >= prior_close['event_ns']:
                prior_close = mark
        if record['flags'] & 128:
            close(cursor)
    if group_start is not None:
        close(final)
    if (records != completion['record_count'] or len(lines) != completion['group_count']
            or prior_close is None or entity is None):
        raise ValueError('complete Monday source, mapping and certified prior reference required')
    terminal = dict(through_cursor=final, as_of=as_of, source_as_of=source_as_of,
                    group_index=len(lines) - 1, groups=len(lines), source_hash=view.chain.prefix_hash,
                    entity_rows=entity_rows, other_entity_rows=other_rows)
    return lines, entity, prior_close, terminal


def author(commit, output_root, preparation_root):
    require_checkout(commit)
    output = fresh(output_root, AUTHOR_PARENT)
    preparation = fresh(preparation_root, OUTPUT_PARENT)
    blocks = REPOSITORY/'research/kalshi/frankie_boss/blocks'
    manifest_pin = witness(blocks/'BLOCK_20211004_SOURCE_MANIFEST.json')
    sunday = read_pin(witness(REPOSITORY/'research/kalshi/frankie_boss/sunday_20260915_package/FB/'
                                         'principal-source-contract/source-contract.json'))
    AUTHOR_PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    sync_directory(AUTHOR_PARENT)
    from frankie_box_progress import Probe
    progress = Probe(output, commit, 'monday-authorship')
    progress.update('opening-sealed-source')

    # The verified recovered-ingestion descriptor over the retained recovery, read in place.
    descriptor = dict(schema='FRANKIE_VERIFIED_RECOVERED_INGESTION_V1', source_manifest=manifest_pin,
        recovery_receipt=witness(RECOVERY/'recovery-receipt.json'),
        verification=witness(blocks/'MONDAY_RECOVERY_VERIFIED_20260922.json'),
        checkpoint=witness(RECOVERY/'builder-checkpoint.c15.json'), completion=witness(RECOVERY/'completion.json'))
    save_new(output/'recovered-ingestion.json', descriptor)
    descriptor_pin = witness(output/'recovered-ingestion.json')
    from research.kalshi.frankie_boss.recovered_ingestion import load_recovered_ingestion
    from research.kalshi.frankie_boss.completed_schedule_view import open_completed_schedule_view
    from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
    recovered = load_recovered_ingestion(descriptor_pin)
    if recovered.container != ORIGINAL_CONTAINER:
        raise ValueError('recovered container differs from the canonical original')
    view = open_completed_schedule_view(recovered.scope, Path(recovered.container['path']),
        recovered.checkpoint_path, descriptor['checkpoint']['sha256'], recovered.receipt['checkpoint_state_hash'],
        recovered.completion, reader_factory=FrankieCompactReader, recovery_descriptor=descriptor_pin)
    try:
        lines, entity, prior_close, terminal = measure(view, recovered.completion, progress)
    finally:
        view.journal.close()

    with (output/'mapping.jsonl').open('xb') as stream:
        stream.writelines(lines)
    mapping_pin = witness(output/'mapping.jsonl')
    convention = dict(sunday['convention'], id='NG_111313_CME_TRADING_DAY_20211005_V1',
        close_rule='Declared CME trading-day halt 2021-10-05T21:00:00Z; verified outcomes pending.',
        opening_rule='Preopen forecast: Tuesday opening and path observations are not yet available.',
        prior_reference_rule='Last event-time Monday MBO trade before the 21:00Z halt; not official settlement.')
    calendar = dict(id='CME_TRADING_DAY_20211005_V1', is_exchange_session_calendar=False,
        session_policy='cme_trading_day', trading_day='20211005',
        open_ns=TARGET_OPEN_NS, close_ns=TARGET_CLOSE_NS)
    target = dict(trading_day='20211005', open_ns=TARGET_OPEN_NS, close_ns=TARGET_CLOSE_NS,
                  calendar_hash=digest(calendar))
    if not terminal['as_of'] < TARGET_OPEN_NS:
        raise ValueError('Monday source availability must precede the target open')
    count = recovered.completion['record_count']
    timing = dict(sunday['timing_policy'], max_interior=count)
    query = sunday['query_policy']
    session = dict(instrument='NG.v.0/instrument_id=%d' % INSTRUMENT, session_id='NG_%d_CME_20211005' % INSTRUMENT,
        open_ns=TARGET_OPEN_NS, close_ns=TARGET_CLOSE_NS,
        event_cutoff_ns=terminal['source_as_of'], receive_cutoff_ns=terminal['as_of'],
        usd_per_price_unit=1.0, tick_size=convention['tick_size'], convention_hash=digest(convention),
        calendar_hash=digest(calendar), source_hash=None,
        knot_policy=dict(quantum_ns=1, max_interior=timing['max_interior']),
        prior_close=prior_close, opening=None, known_marks=[])
    cycle = dict(cycle_index=0, historical_group_index=terminal['group_index'],
        source_prefix=dict(source_cursor=terminal['through_cursor'], receive_cutoff_ns=terminal['as_of'],
                           event_cutoff_ns=terminal['source_as_of'], source_records=count,
                           group_index=terminal['group_index']),
        learning_cutoff_ns=None, learning_through_source_cursor=None,
        path_query_offsets_ns=query_offsets(query['seed'], 0),
        native_context=dict(configured_capacity=count, entity_rows_in_prefix=terminal['entity_rows'],
                            other_entity_rows_in_prefix=terminal['other_entity_rows']),
        forecast_session=session)
    contract = dict(schema='FRANKIE_TRADING_DAY_SOURCE_CONTRACT_V1', trading_day='20211004',
        forecast_mode='whole_day_next_session', forecast_target=target,
        source_manifest_hash=recovered.manifest['manifest_hash'], cycle_count=1, cycles=[cycle],
        convention=convention, convention_hash=digest(convention), calendar=calendar, calendar_hash=digest(calendar),
        timing_policy=timing, timing_policy_hash=digest(timing), query_policy=query, query_policy_hash=digest(query),
        principal_authorship=dict(role='operator-authored source binding', authorized_by='Greg, 2026-09-23',
            policies='Existing development units, timing and seeded queries; whole Monday source, preopen Tuesday target.',
            prior_reference='certified terminal Monday trade; no target-day observations', commit=commit))
    save_new(output/'source-contract.json', contract)
    contract_pin = witness(output/'source-contract.json')

    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle
    bound = bind_cycle(contract_pin['path'], contract_pin['sha256'], 0, terminal)

    launch = json.loads((blocks/'MONDAY_20211004_LAUNCH.json').read_bytes())
    launch.pop('cutoffs', None)
    launch.pop('cutoff_rule', None)
    launch.update(source_manifest=dict(manifest_pin, manifest_hash=recovered.manifest['manifest_hash']),
        forecast_mode='whole_day_next_session', forecast_target=target, model_context_rows=count,
        ingestion_receipt=descriptor_pin, mapping=mapping_pin, source_contract=contract_pin,
        publish_route='box-local retained preparation artifacts',
        _note='Whole Monday source; one terminal delivery; Tuesday outcomes explicitly pending.')
    save_new(output/'launch.json', launch)
    configuration = dict(trading_day_launch=witness(output/'launch.json'), source_manifest=manifest_pin,
        schedule_directory=str(preparation/'schedule'),
        host_runtime=dict(source_entity=list(entity), prefixes_directory=str(preparation/'prefixes'), data_workers=1))
    save_new(output/'configuration.json', configuration)
    result = dict(schema='FRANKIE_MONDAY_LAUNCH_AUTHORSHIP_V1', commit=commit, output_root=str(output),
        preparation_root=str(preparation), configuration=witness(output/'configuration.json'),
        launch=witness(output/'launch.json'), entity=list(entity), terminal=terminal,
        forecast_target=target, prior_close=prior_close, mapping=mapping_pin,
        path_query_offsets_ns=cycle['path_query_offsets_ns'], bound_sessions_hash=bound['expected_sessions_hash'],
        model_calls=0, source_replays=0, source_writes=0)
    save_new(output/'authorship-receipt.json', result)
    progress.checkpoint('saved', 'authorship-receipt.json')
    if read_pin(witness(output/'authorship-receipt.json')) != result:
        raise ValueError('authorship receipt readback differs')
    progress.checkpoint('read_verified', 'authorship-receipt.json')
    progress.update('monday-authorship', count, count, state='complete')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--preparation-root', required=True)
    args = parser.parse_args()
    print(json.dumps(author(args.commit, args.output_root, args.preparation_root), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
