"""Trading-day declarations and exact schedule identities; no inferred modelling values."""
from datetime import datetime
import hashlib
import json
import re
from pathlib import Path

SCHEMA = 'BOSS_TRADING_DAY_CAUSAL_CYCLE_SCHEDULE_V1'
WHOLE_DAY_SCHEMA = 'BOSS_WHOLE_DAY_NEXT_SESSION_SCHEDULE_V1'
LAUNCH_SCHEMA = 'FRANKIE_TRADING_DAY_LAUNCH_V1'
LAUNCH_FIELDS = ('model_context_rows', 'cutoff_rule', 'cutoffs', 'ingestion_receipt',
                 'mapping', 'source_contract', 'publish_route')
BASE = ('schema', 'cutoff_file_sha256', 'mapping_index_sha256', 'steps',
        'terminal_delivery', 'first_observed_trade_candidate', 'anchor_authorship',
        'model_context_rows', 'source_dates_required', 'feedback_lag')
IDENTITY = ('trading_day', 'source_manifest_hash', 'source_partitions',
            'source_record_count', 'journal_count', 'journal_hash', 'journal_sha256',
            'step_count', 'cutoff_rule')
STEP = ('group_index', 'groups_delivered', 'through_cursor', 'records_delivered',
        'as_of', 'source_as_of', 'source_hash')
TERMINAL = ('groups_delivered', 'records_delivered', 'through_cursor',
            'as_of', 'source_as_of', 'source_hash')


def missing_launch_fields(value):
    missing = []
    def walk(v, name):
        if v is None or v == '':
            missing.append(name)
        elif isinstance(v, dict):
            for key, child in v.items():
                walk(child, name + '.' + key)
    for name in LAUNCH_FIELDS:
        walk(value.get(name), name)
    return missing


def require_launch_fields(value):
    if value.get('schema') != LAUNCH_SCHEMA:
        raise ValueError('trading-day launch declaration schema required')
    missing = missing_launch_fields(value)
    if missing:
        raise ValueError('missing launch values: ' + ', '.join(missing))
    _positive(value['model_context_rows'], 'model_context_rows')
    if not isinstance(value['cutoff_rule'], str) or not value['cutoff_rule'].strip():
        raise ValueError('cutoff_rule must be explicitly authored')
    return value


def _positive(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(name + ' must be an explicitly declared integer')
    return value


def _hash(value, name):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError(name + ' must be a full sha256')
    return value


def counts(schedule):
    return schedule['terminal_delivery']['records_delivered'], len(schedule['steps'])


def _prefix(row, keys, name):
    if type(row) is not dict or set(row) != set(keys):
        raise ValueError(name + ' fields differ')
    for key in set(keys) - {'source_hash'}:
        _positive(row[key], name + '.' + key, minimum=0 if key in ('through_cursor', 'group_index') else 1)
    _hash(row['source_hash'], name + '.source_hash')
    if row['records_delivered'] != row['through_cursor'] + 1:
        raise ValueError(name + ' record denominator differs')
    if 'group_index' in row and row['groups_delivered'] != row['group_index'] + 1:
        raise ValueError(name + ' group denominator differs')



WHOLE_DAY_IDENTITY = ('trading_day', 'source_manifest_hash', 'source_partitions',
                      'source_record_count', 'journal_count', 'journal_hash', 'journal_sha256')
WHOLE_DAY_FIELDS = (*WHOLE_DAY_IDENTITY, 'schema', 'mapping_index_sha256', 'steps',
                    'terminal_delivery', 'model_context_rows', 'source_dates_required',
                    'feedback_lag', 'context_selection', 'forecast_target', 'step_count')


def _day(value):
    if not isinstance(value, str) or re.fullmatch('20[0-9]{6}', value) is None:
        raise ValueError('trading_day must be YYYYMMDD')
    return datetime.strptime(value, '%Y%m%d').date()


def _validate_whole_day(body):
    """A terminal source delivery is not a same-day feedback boundary."""
    if set(body) != set(WHOLE_DAY_FIELDS):
        raise ValueError('whole-day schedule fields differ')
    for name in ('model_context_rows', 'source_record_count', 'journal_count',
                 'step_count', 'source_dates_required'):
        _positive(body[name], name)
    for name in ('source_manifest_hash', 'journal_hash', 'journal_sha256', 'mapping_index_sha256'):
        _hash(body[name], name)
    day = _day(body['trading_day'])
    members = body['source_partitions']
    if (type(members) is not list or not members
            or any(type(m) is not str or not m for m in members)
            or len(set(members)) != len(members) or len(members) != body['source_dates_required']):
        raise ValueError('complete ordered source partitions required')
    if (body['journal_count'] != 2 * body['source_record_count']
            or body['model_context_rows'] != body['source_record_count']
            or body['context_selection'] != 'all_source_records'):
        raise ValueError('whole-day source and context must include every record')
    terminal = body['terminal_delivery']
    _prefix(terminal, TERMINAL, 'terminal_delivery')
    if (terminal['records_delivered'] != body['source_record_count']
            or terminal['groups_delivered'] > terminal['records_delivered']
            or terminal['source_as_of'] > terminal['as_of']):
        raise ValueError('whole-day terminal coverage or causal clocks differ')
    expected_step = dict(terminal, group_index=terminal['groups_delivered'] - 1,
                         feedback_available_through=None)
    if (body['step_count'] != 1 or type(body['steps']) is not list
            or body['steps'] != [expected_step]):
        raise ValueError('whole-day delivery requires one complete terminal step and pending feedback')
    if body['feedback_lag'] != 'verified target-day outcomes pending':
        raise ValueError('target-day outcome feedback must remain explicitly pending')
    target = body['forecast_target']
    if type(target) is not dict or set(target) != {'trading_day', 'open_ns', 'close_ns', 'calendar_hash'}:
        raise ValueError('explicit next-session forecast target required')
    _hash(target['calendar_hash'], 'forecast_target.calendar_hash')
    _positive(target['open_ns'], 'forecast_target.open_ns')
    _positive(target['close_ns'], 'forecast_target.close_ns')
    if (_day(target['trading_day']) <= day
            or not terminal['as_of'] < target['open_ns'] < target['close_ns']):
        raise ValueError('forecast target must be a future unopened trading session')
    return body


def build_whole_day_schedule(builder, mapping_index, *, expected_index_sha256,
                            source_identity, forecast_target):
    """Read a verified sealed source once, retaining every record and no future labels.

    The caller supplies the independently verified source view and source identity.
    This reads existing evidence, never ingests, computes a market result or writes
    the source. The target/calendar are explicit, not inferred from a cutoff.
    """
    if type(source_identity) is not dict or set(source_identity) != set(WHOLE_DAY_IDENTITY):
        raise ValueError('complete independently verified source identity required')
    _hash(expected_index_sha256, 'mapping_index_sha256')
    total = _positive(source_identity['source_record_count'], 'source_record_count')
    if (builder.chain.next_cursor != total
            or builder.journal.count != source_identity['journal_count']
            or builder.journal.head_hash != source_identity['journal_hash']):
        raise ValueError('verified journal differs from declared source identity')
    digest, cursor, groups = hashlib.sha256(), 0, 0
    with Path(mapping_index).open('rb') as stream:
        for line in stream:
            digest.update(line)
            row = json.loads(line)
            start, end = row.get('cursor_start'), row.get('cursor_end')
            if (type(start) is not int or type(end) is not int
                    or start != cursor or end < start or end >= total):
                raise ValueError('mapping cursor coverage differs')
            cursor, groups = end + 1, groups + 1
    if digest.hexdigest() != expected_index_sha256 or cursor != total or not groups:
        raise ValueError('full mapping identity or coverage differs')
    count = closed_groups = as_of = source_as_of = 0
    terminal = None
    for entry in builder.journal.entries():
        if entry['kind'] == 'INPUT':
            continue
        if entry['kind'] != 'APPLIED':
            raise ValueError('failed or unknown sealed source entry')
        row = entry['payload']
        if type(row.get('cursor')) is not int or row['cursor'] != count:
            raise ValueError('applied source cursor continuity differs')
        record = row['raw_record']
        as_of = max(as_of, record['ts_recv'])
        source_as_of = max(source_as_of, record['ts_event'])
        closed_groups += bool(record['flags'] & 128)
        count += 1
        terminal = row
    if (count != total or closed_groups != groups or terminal is None
            or terminal.get('receipt') is None or not terminal['raw_record']['flags'] & 128
            or terminal['terminal_prefix_hash'] != builder.chain.prefix_hash):
        raise ValueError('sealed source terminal or complete group coverage differs')
    delivery = dict(groups_delivered=groups, records_delivered=count, through_cursor=count - 1,
                    as_of=as_of, source_as_of=source_as_of, source_hash=builder.chain.prefix_hash)
    return seal(dict(source_identity, schema=WHOLE_DAY_SCHEMA,
        mapping_index_sha256=expected_index_sha256,
        steps=[dict(delivery, group_index=groups - 1, feedback_available_through=None)],
        terminal_delivery=delivery, model_context_rows=count,
        source_dates_required=len(source_identity['source_partitions']),
        context_selection='all_source_records', feedback_lag='verified target-day outcomes pending',
        forecast_target=dict(forecast_target), step_count=1))


def validate_body(body):
    if type(body) is dict and body.get('schema') == WHOLE_DAY_SCHEMA:
        return _validate_whole_day(body)
    if type(body) is not dict or set(body) != set(BASE + IDENTITY):
        raise ValueError('trading-day schedule fields differ')
    if body['schema'] != SCHEMA:
        raise ValueError('trading-day schedule schema required')
    for name in ('model_context_rows', 'source_record_count', 'journal_count', 'step_count', 'source_dates_required'):
        _positive(body[name], name)
    for name in ('source_manifest_hash', 'journal_hash', 'journal_sha256', 'cutoff_file_sha256', 'mapping_index_sha256'):
        _hash(body[name], name)
    if not isinstance(body['trading_day'], str) or re.fullmatch('20[0-9]{6}', body['trading_day']) is None:
        raise ValueError('trading_day must be YYYYMMDD')
    if not isinstance(body['cutoff_rule'], str) or not body['cutoff_rule'].strip():
        raise ValueError('cutoff_rule must be explicitly authored')
    members = body['source_partitions']
    if (type(members) is not list or not members or any(not isinstance(m, str) or not m for m in members)
            or len(set(members)) != len(members) or len(members) != body['source_dates_required']):
        raise ValueError('source_partitions differ from declared source_dates_required')
    if body['journal_count'] != 2 * body['source_record_count']:
        raise ValueError('journal record denominator differs')
    terminal = body['terminal_delivery']
    _prefix(terminal, TERMINAL, 'terminal_delivery')
    if terminal['records_delivered'] != body['source_record_count']:
        raise ValueError('terminal record count differs from measured source')
    steps = body['steps']
    if type(steps) is not list or len(steps) != body['step_count']:
        raise ValueError('step_count differs from authored roster')
    previous = None
    for index, step in enumerate(steps):
        if type(step) is not dict or set(step) != set(STEP) | {'feedback_available_through'}:
            raise ValueError('step fields differ')
        current = {k: step[k] for k in STEP}
        _prefix(current, STEP, 'steps.' + str(index))
        if previous and any(current[k] <= previous[k] for k in ('through_cursor', 'as_of', 'group_index')):
            raise ValueError('schedule cutoffs must be strictly increasing')
        if current['source_as_of'] > terminal['source_as_of'] or current['groups_delivered'] >= terminal['groups_delivered']:
            raise ValueError('cutoff must precede terminal source')
        later = ({k: steps[index + 1][k] for k in STEP} if index + 1 < len(steps) else terminal)
        if step['feedback_available_through'] != later:
            raise ValueError('feedback boundary differs from next declared cutoff')
        if later['as_of'] <= current['as_of'] or later['through_cursor'] <= current['through_cursor']:
            raise ValueError('strictly later feedback availability required')
        previous = current
    if body['feedback_lag'] != 'next retained cutoff':
        raise ValueError('feedback_lag differs')
    trade = body['first_observed_trade_candidate']
    if trade is not None:
        required = {'cursor', 'ts_event_ns', 'ts_recv_ns', 'price_raw', 'evidence_hash', 'source_prefix_hash'}
        if type(trade) is not dict or set(trade) != required:
            raise ValueError('first_observed_trade_candidate fields differ')
        for key in ('evidence_hash', 'source_prefix_hash'):
            _hash(trade[key], 'first_observed_trade_candidate.' + key)
        for key in required - {'evidence_hash', 'source_prefix_hash'}:
            _positive(trade[key], 'first_observed_trade_candidate.' + key, minimum=0 if key == 'cursor' else 1)
        if trade['cursor'] >= body['source_record_count']:
            raise ValueError('first trade is outside the source')
    return body


def seal(body):
    validate_body(body)
    raw = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
    return dict(body, schedule_sha256=hashlib.sha256(raw).hexdigest())


def verify(value, *, expected_digest):
    if type(value) is not dict or 'schedule_sha256' not in value:
        raise ValueError('completed trading-day schedule required')
    body = {k: v for k, v in value.items() if k != 'schedule_sha256'}
    checked = seal(body)
    if checked['schedule_sha256'] != expected_digest or checked != value:
        raise ValueError('completed trading-day schedule identity differs')
    return checked
