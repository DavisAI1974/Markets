"""Trading-day declarations and exact schedule identities; no inferred modelling values."""
import hashlib
import json
import re

SCHEMA = 'BOSS_TRADING_DAY_CAUSAL_CYCLE_SCHEDULE_V1'
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


def validate_body(body):
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
