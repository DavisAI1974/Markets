"""Author the Monday 20211004 cycle-0 launch bindings from the recovered journal.

Frankie principal authorship (Greg, 2026-09-23). ONE cycle for the whole Monday trading day (Sunday 18:00 ET to
Monday 17:00 ET): the cutoff is the last complete group before 16:00 ET, the final hour to the halt is the learning
feedback, and the model window is the latest 6,500 rows at the cutoff under stacked_v2. One read-only pass over the sealed original
container through the existing verified view; every output is new under one fresh root. No model call,
ingestion, replay, runtime control or source write. The existing preparation operation stays the
authority for the schedule and prefixes; this only writes the launch inputs it requires.
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
MODEL_CONTEXT_ROWS = 6500
CUTOFF_BEFORE_NS = 1633377600000000000   # 2021-10-04T20:00:00Z = 16:00 ET, one hour before the halt
INSTRUMENT = 111313
OPEN_NS = 1633298400000000000    # 2021-10-03T22:00:00Z, the declared CME trading-day open
CLOSE_NS = 1633381200000000000   # 2021-10-04T21:00:00Z, the declared halt
PRICE_SCALE = 10**9
SENTINEL = 2**63 - 1
CUTOFF_RULE = ('One cycle per trading day: cycle 0 cuts at the last complete F_LAST group whose receive clock is '
               'before 2021-10-04T20:00:00Z (16:00 ET, one hour before the halt); availability is the maximum receive '
               'clock of that prefix; the model window is the latest model_context_rows (6500) rows at the cutoff; '
               'the cycle learns through the terminal delivery of the trading day.')


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


def query_offsets(seed, cycle_index, event_cutoff_ns):
    # Sunday's authored query policy verbatim; reproduces its recorded cycle-0 offsets exactly.
    times = sorted({int(digest({'seed': seed, 'cycle_index': cycle_index, 'ordinal': j}), 16)
                    % (CLOSE_NS - event_cutoff_ns) + event_cutoff_ns + 1 for j in range(8)})
    return [t - OPEN_NS for t in times]


def measure(view, completion):
    """One pass: group mapping lines, the cutoff, the opening and marks, and the terminal clocks."""
    from research.kalshi.frankie_boss.context_session import journal_prefix
    final = view.chain.next_cursor - 1
    lines, group_start, member = [], None, None
    as_of = source_as_of = 0
    entity, entity_rows, other_rows = None, 0, 0
    cutoff, opening, marks, pending, last_event = None, None, [], [], None

    def close(end):
        nonlocal group_start
        lines.append(canonical(dict(cursor_start=group_start, cursor_end=end)) + b'\n')
        group_start = None
        for mark in pending:  # availability = max receive clock of the complete containing prefix
            mark['receive_ns'] = as_of
        pending.clear()

    for row in journal_prefix(view, final):
        cursor, record, normal = row['cursor'], row['raw_record'], row['normalized']
        if member is not None and row['source_member_index'] != member and group_start is not None:
            close(cursor - 1)  # member seams close groups
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
        if (normal['ts_recv_ns'] < CUTOFF_BEFORE_NS and record.get('action') == 'T' and record['instrument_id'] == INSTRUMENT
                and type(record.get('price')) is int and 0 < record['price'] < SENTINEL
                and normal['ts_event_ns'] >= OPEN_NS):
            mark = dict(event_ns=normal['ts_event_ns'], receive_ns=None, price=price(record['price']),
                        evidence_hash=hashlib.sha256(record['dbn_wire_bytes']).hexdigest())
            if opening is None:
                opening, last_event = mark, mark['event_ns']
                pending.append(mark)
            elif mark['event_ns'] > last_event:
                marks.append(mark)
                last_event = mark['event_ns']
                pending.append(mark)
        if record['flags'] & 128:
            if normal['ts_recv_ns'] < CUTOFF_BEFORE_NS:   # the latest complete group before the cutoff clock wins
                cutoff = dict(group_index=len(lines), through_cursor=cursor, recv_ns=normal['ts_recv_ns'],
                              as_of=as_of, source_as_of=source_as_of, source_hash=row['terminal_prefix_hash'],
                              entity_rows=entity_rows, other_entity_rows=other_rows)
            close(cursor)
    if group_start is not None:
        close(final)
    if len(lines) != completion['group_count']:
        raise ValueError('mapping groups %d differ from the recovered group count %d'
                         % (len(lines), completion['group_count']))
    if cutoff is None or opening is None:
        raise ValueError('no qualifying cutoff or opening trade in the trading day')
    marks = [m for m in marks if m['event_ns'] <= cutoff['source_as_of'] and m['receive_ns'] is not None
             and m['receive_ns'] <= cutoff['as_of']]
    terminal = dict(through_cursor=final, as_of=as_of, source_as_of=source_as_of,
                    groups=len(lines), source_hash=view.chain.prefix_hash)
    return lines, entity, cutoff, opening, marks, terminal


def author(commit, output_root, preparation_root):
    require_checkout(commit)
    output = fresh(output_root, AUTHOR_PARENT)
    preparation = fresh(preparation_root, OUTPUT_PARENT)
    blocks = REPOSITORY/'research/kalshi/frankie_boss/blocks'
    manifest_pin = witness(blocks/'BLOCK_20211004_SOURCE_MANIFEST.json')
    friday = witness(blocks/'FRIDAY_ANCHOR_VERIFICATION_20260922.json')
    sunday = read_pin(witness(REPOSITORY/'research/kalshi/frankie_boss/sunday_20260915_package/FB/'
                                         'principal-source-contract/source-contract.json'))
    AUTHOR_PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    sync_directory(AUTHOR_PARENT)

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
        lines, entity, cutoff, opening, marks, terminal = measure(view, recovered.completion)
    finally:
        view.journal.close()

    with (output/'mapping.jsonl').open('xb') as stream:
        stream.writelines(lines)
    mapping_pin = witness(output/'mapping.jsonl')
    save_new(output/'cutoffs.json', dict(invocation_cutoffs=[dict(group_index=cutoff['group_index'],
        recv_ns=cutoff['recv_ns'], first_lawful_availability_ns=cutoff['as_of'])]))
    cutoffs_pin = witness(output/'cutoffs.json')

    anchor = read_pin(friday)['anchor_receipt']['anchor']
    prior_close = dict(event_ns=anchor['ts_event'], receive_ns=anchor['ts_recv'],
                       price=price(anchor['price_raw']), evidence_hash=read_pin(friday)['receipt_sha256'])
    if opening['event_ns'] != OPEN_NS or opening['receive_ns'] is None:
        raise ValueError('first eligible trade is not at the declared open; the opening convention needs review')
    convention = dict(sunday['convention'], id='NG_111313_CME_TRADING_DAY_20211004_V1',
        close_rule='Declared CME trading-day halt 2021-10-04T21:00:00Z; the unobserved final tail remains censored.',
        opening_rule='First source-order eligible trade with event timestamp at or after the declared 22:00:00Z open.',
        prior_reference_rule=('Friday 2021-10-01 last MBO trade before the 21:00Z halt for the roster instrument '
                              '(verified Friday anchor receipt); mapped into prior_close, never an official settlement.'))
    calendar = dict(id='CME_TRADING_DAY_20211004_V1', is_exchange_session_calendar=False,
        session_policy='cme_trading_day', trading_day='20211004', open_ns=OPEN_NS, close_ns=CLOSE_NS,
        source_manifest_hash=recovered.manifest['manifest_hash'])
    timing = dict(sunday['timing_policy'], max_interior=recovered.completion['record_count'])
    query = sunday['query_policy']
    session = dict(instrument='NG.v.0/instrument_id=%d' % INSTRUMENT, session_id='NG_%d_CME_20211004' % INSTRUMENT,
        open_ns=OPEN_NS, close_ns=CLOSE_NS, event_cutoff_ns=cutoff['source_as_of'], receive_cutoff_ns=cutoff['as_of'],
        usd_per_price_unit=1.0, tick_size=convention['tick_size'], convention_hash=digest(convention),
        calendar_hash=digest(calendar), source_hash=None,
        knot_policy=dict(quantum_ns=1, max_interior=timing['max_interior']),
        prior_close=prior_close, opening=opening, known_marks=marks)
    cycle = dict(cycle_index=0, historical_group_index=cutoff['group_index'],
        source_prefix=dict(source_cursor=cutoff['through_cursor'], receive_cutoff_ns=cutoff['as_of'],
                           event_cutoff_ns=cutoff['source_as_of'], source_records=cutoff['through_cursor'] + 1,
                           group_index=cutoff['group_index']),
        learning_cutoff_ns=terminal['as_of'], learning_through_source_cursor=terminal['through_cursor'],
        path_query_offsets_ns=query_offsets(query['seed'], 0, cutoff['source_as_of']),
        native_context=dict(configured_capacity=MODEL_CONTEXT_ROWS, entity_rows_in_prefix=cutoff['entity_rows'],
                            other_entity_rows_in_prefix=cutoff['other_entity_rows']),
        forecast_session=session)
    contract = dict(schema='FRANKIE_TRADING_DAY_SOURCE_CONTRACT_V1', trading_day='20211004',
        source_manifest_hash=recovered.manifest['manifest_hash'], cycle_count=1, cycles=[cycle],
        convention=convention, convention_hash=digest(convention), calendar=calendar, calendar_hash=digest(calendar),
        timing_policy=timing, timing_policy_hash=digest(timing), query_policy=query, query_policy_hash=digest(query),
        principal_authorship=dict(role='Frankie principal', authorized_by='Greg, 2026-09-23',
            policies='Sunday 20211003 convention/timing/query policy text reused; Monday calendar, interval, anchors new',
            friday_anchor_verification=friday, commit=commit))
    save_new(output/'source-contract.json', contract)
    contract_pin = witness(output/'source-contract.json')

    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle
    bound = bind_cycle(contract_pin['path'], contract_pin['sha256'], 0, dict(through_cursor=cutoff['through_cursor'],
        as_of=cutoff['as_of'], source_as_of=cutoff['source_as_of'], source_hash=cutoff['source_hash'],
        group_index=cutoff['group_index']))

    launch = json.loads((blocks/'MONDAY_20211004_LAUNCH.json').read_bytes())
    launch.update(source_manifest=dict(manifest_pin, manifest_hash=recovered.manifest['manifest_hash']),
        model_context_rows=MODEL_CONTEXT_ROWS, cutoff_rule=CUTOFF_RULE, cutoffs=cutoffs_pin,
        ingestion_receipt=descriptor_pin, mapping=mapping_pin, source_contract=contract_pin,
        publish_route='presigned PUT through frankie_box_run.yml (frankie_box_prepare_trading_day.sh ACTION=publish)',
        _note='Frankie principal authorship, Greg 2026-09-23; cycle 0 = first window of the day, largest that fits under stacked_v2.')
    save_new(output/'launch.json', launch)
    configuration = dict(trading_day_launch=witness(output/'launch.json'), source_manifest=manifest_pin,
        schedule_directory=str(preparation/'schedule'),
        host_runtime=dict(source_entity=list(entity), prefixes_directory=str(preparation/'prefixes'), data_workers=8))
    save_new(output/'configuration.json', configuration)
    result = dict(schema='FRANKIE_MONDAY_LAUNCH_AUTHORSHIP_V1', commit=commit, output_root=str(output),
        preparation_root=str(preparation), configuration=witness(output/'configuration.json'),
        launch=witness(output/'launch.json'), cutoff=cutoff, entity=list(entity), terminal=terminal,
        opening=opening, prior_close=prior_close, known_marks=len(marks), mapping=mapping_pin,
        path_query_offsets_ns=cycle['path_query_offsets_ns'], bound_sessions_hash=bound['expected_sessions_hash'],
        model_calls=0, source_replays=0, source_writes=0)
    save_new(output/'authorship-receipt.json', result)
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
