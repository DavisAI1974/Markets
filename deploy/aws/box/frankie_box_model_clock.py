"""The model-evaluation clock of the experiment: FRANKIE_MODEL_EVALUATION_CLOCK_V1, one append-only record per REAL
model call (Greg, 2026-10-07: fill the clock_model_evaluation entry of the 99 from the experiment's real model calls,
not from new calls inside the native traversal).

Why here and not in the traversal: native_clocks.member_clock_row carries clock_model_evaluation as a declared null
(NO_INVOCATION_AT_THIS_CUTOFF) because the native traversal never calls a model on the experiment path. The real model
evaluations of the experiment are Granite's meeting (voice stage) and Jev, later in the day on the same lane. Each of
those calls is stamped here with the exact market cutoff its input was cut at and the wall clock it ran on.

THE RECORD (contract; the same shape for every piece):
  schema      FRANKIE_MODEL_EVALUATION_CLOCK_V1
  piece       'meeting' | 'jev' | 'jev_sit_in'
  run, day    the owning experiment run id and the trading day (YYYYMMDD); day must equal the file's day
  lane        the lane placement as the caller knows it (host, booking, attempt, cpus...); unknown parts stay null
  call_id     stable per INTENT, never per attempt (meeting: binding sha + item + round; jev: sha256 of the request body)
  model       the runtime pins of the ONE shared Granite runtime (definition, release, pins_sha256, model_identity,
              quantization, config pin, threads, cpus); null only when no runtime was bound (outcome not_called/failed)
  cutoff      the exact market cutoff of the call's input: source_hash, as_of, through_cursor (the original explicit
              source scope) and, where the input carries them, the normalized clocks of that cutoff instant
              (input_cursor, adapter_cursor, ts_recv_ns, ts_event_ns, publication_frontier_ns); or {'listed': reason}
              when the input carries no cutoff; null only for a call that never got an input (not_called/failed)
  wall_start, wall_end   host wall clock (epoch seconds) of the call; wall_end null only for unknown_completion
  outcome     'answered' (reply_sha256 required) | 'refused_over_cap' (input_tokens and cap required, input > cap) |
              'failed' (reason required; sent = True/False/None as the transport knows it) | 'not_called' (reason
              required) | 'unknown_completion' (reason required: a durable pre-send intent with no recorded reply; the
              call is never repeated)
  Every other field the caller gives is kept as given (never dropped). record_call adds exactly two derived fields:
  cutoff_disposition and prior_records_for_call.

Market time vs wall time: the cutoff is the market instant the model evaluated AT; the wall clock is when it ran. The
wall clock never advances the market instant, and nothing after the cutoff is implied to have been seen.

Causality (no same-day circular teaching): these records are written AFTER the day's classroom (the meeting is the
post-class voice stage; Jev files after the classroom package). They never feed that day's classroom. They reach
Frankie only as lawful prior-session carry on later days, and the same day's reports, all-99 coverage and the Jev
comparison. Jev's blind wall is unchanged: nothing here carries a model's reply text, only its sha256.

Missing coverage (Greg, 2026-10-07): a day with no record is 'no model call this day' with the reason, never a zero
and never a fabricated instant; an unreadable line is listed, never dropped or rewritten.

Storage: <run-dir>/days/<day>/model-clock.jsonl, appended under an exclusive lock with fsync. Idempotent per record:
the identical record for the same (piece, call_id) is not appended twice; a DIFFERENT later record for the same call
(for example an interrupted call stamped unknown_completion after an answered stamp whose progress write was lost) is
appended beside the first with prior_records_for_call > 0; readers take the first as primary and list the rest.
Nothing here keys on how many days a run holds.
"""
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path

SCHEMA = 'FRANKIE_MODEL_EVALUATION_CLOCK_V1'
DAY_SCHEMA = 'FRANKIE_MODEL_EVALUATION_CLOCK_DAY_V1'
FILE_NAME = 'model-clock.jsonl'
UNRECORDED_NAME = 'model-clock-unrecorded.jsonl'
PIECES = ('meeting', 'jev', 'jev_sit_in')
OUTCOMES = ('answered', 'refused_over_cap', 'failed', 'not_called', 'unknown_completion')
REQUIRED = ('schema', 'piece', 'run', 'day', 'lane', 'call_id', 'model', 'cutoff', 'wall_start', 'wall_end', 'outcome')
CUTOFF_SCOPE = ('source_hash', 'as_of', 'through_cursor')
CUTOFF_CLOCKS = ('record_count', 'position', 'input_cursor', 'adapter_cursor', 'ts_recv_ns', 'ts_event_ns',
                 'publication_frontier_ns', 'picture_sha256')
DERIVED = ('cutoff_disposition', 'prior_records_for_call')
ENTRY = 'clock_model_evaluation'
STAMPED = 'stamped_from_model_calls'
NO_CALL = 'no_model_call_this_day'
CAUSALITY = ('written after the day\'s classroom by the post-class meeting and Jev; never read by that day\'s classroom; '
             'reaches Frankie only as prior-session carry on later days, and the same day\'s reports, all-99 coverage '
             'and Jev comparison')


def _sync_directory(path):
    try:
        from frankie_box_durable import sync_directory
    except ImportError:      # imported as a repository module (the Jev client): the same durable writer by package path
        from deploy.aws.box.frankie_box_durable import sync_directory
    sync_directory(path)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')


def clock_path(run_dir, day):
    return Path(run_dir) / 'days' / str(day) / FILE_NAME


def cutoff_disposition(cutoff):
    """How exact the cutoff of the call's input is; nothing is filled in."""
    if cutoff is None:
        return 'not_given'
    if 'listed' in cutoff and not any(k in cutoff for k in CUTOFF_SCOPE):
        return 'listed_no_cutoff'
    missing = [k for k in ('as_of', 'through_cursor') if type(cutoff.get(k)) is not int]
    if missing or not isinstance(cutoff.get('source_hash'), str):
        return 'incomplete_scope'
    clocks = [k for k in ('ts_recv_ns', 'ts_event_ns') if type(cutoff.get(k)) is int]
    return 'exact_scope_with_clocks' if clocks else 'exact_scope'


def validate(record, day=None):
    """The record as given, or ValueError naming exactly what is wrong. Never drops a field."""
    if not isinstance(record, dict):
        raise ValueError('model clock record must be an object')
    missing = [k for k in REQUIRED if k not in record]
    if missing:
        raise ValueError('model clock record lacks %s' % ', '.join(missing))
    clashing = [k for k in DERIVED if k in record]
    if clashing:
        raise ValueError('model clock record carries derived fields %s; they are added by record_call' % clashing)
    if record['schema'] != SCHEMA:
        raise ValueError('model clock record is not %s' % SCHEMA)
    if record['piece'] not in PIECES:
        raise ValueError('unknown model clock piece %r (pieces: %s)' % (record['piece'], ', '.join(PIECES)))
    if not isinstance(record['run'], str) or not record['run']:
        raise ValueError('model clock record names no run')
    if not re.fullmatch(r'[0-9]{8}', str(record['day'])):
        raise ValueError('model clock record day %r is not YYYYMMDD' % record['day'])
    if day is not None and str(record['day']) != str(day):
        raise ValueError('model clock record day %s differs from the file day %s' % (record['day'], day))
    if not isinstance(record['call_id'], str) or not record['call_id']:
        raise ValueError('model clock record names no call_id')
    outcome = record['outcome']
    if outcome not in OUTCOMES:
        raise ValueError('unknown model clock outcome %r (outcomes: %s)' % (outcome, ', '.join(OUTCOMES)))
    if record['model'] is not None and not isinstance(record['model'], dict):
        raise ValueError('model must be the runtime pins object or null')
    if record['model'] is None and outcome not in ('not_called', 'failed'):
        raise ValueError('a %s call must name its runtime pins' % outcome)
    cutoff = record['cutoff']
    if cutoff is not None and not isinstance(cutoff, dict):
        raise ValueError('cutoff must be an object or null')
    if cutoff is None and outcome not in ('not_called', 'failed'):
        raise ValueError('a %s call must name the market cutoff of its input (or {"listed": reason})' % outcome)
    if isinstance(cutoff, dict):
        if 'listed' in cutoff and not any(k in cutoff for k in CUTOFF_SCOPE):
            if not isinstance(cutoff['listed'], str) or not cutoff['listed']:
                raise ValueError('a listed cutoff must say why the input carries none')
        elif any(k not in cutoff for k in CUTOFF_SCOPE):
            raise ValueError('cutoff must carry %s (values may be null when the binding lacks them) or {"listed": '
                             'reason}' % ', '.join(CUTOFF_SCOPE))
        for key in ('as_of', 'through_cursor') + CUTOFF_CLOCKS[2:7]:
            value = cutoff.get(key)
            if value is not None and type(value) is not int:
                raise ValueError('cutoff %s must be an integer or null (never a rounded or text clock)' % key)
    if not _number(record['wall_start']):
        raise ValueError('wall_start must be epoch seconds')
    if record['wall_end'] is None:
        if outcome != 'unknown_completion':
            raise ValueError('only an unknown_completion call may lack wall_end')
    elif not _number(record['wall_end']) or record['wall_end'] < record['wall_start']:
        raise ValueError('wall_end must be epoch seconds at or after wall_start')
    if outcome == 'answered':
        if not isinstance(record.get('reply_sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', record['reply_sha256']):
            raise ValueError('an answered call names its reply_sha256')
    elif outcome == 'refused_over_cap':
        tokens, cap = record.get('input_tokens'), record.get('cap')
        if type(tokens) is not int or type(cap) is not int or tokens <= cap:
            raise ValueError('a refused_over_cap call names input_tokens above cap (integers)')
    else:
        if not isinstance(record.get('reason'), str) or not record['reason']:
            raise ValueError('a %s call names its reason' % outcome)
    if 'sent' in record and record['sent'] not in (True, False, None):
        raise ValueError('sent is True, False or None (unknown)')
    _canonical(record)
    return record


def _lines(path):
    """(records, unreadable) of a clock file; a torn or foreign line is listed with its number, never dropped."""
    records, unreadable = [], []
    if not path.is_file():
        return records, unreadable
    for number, line in enumerate(path.read_bytes().split(b'\n'), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError as error:
            unreadable.append(dict(line=number, bytes=len(line), sha256=hashlib.sha256(line).hexdigest(),
                                   reason='not JSON: %s' % error))
            continue
        if not isinstance(value, dict) or value.get('schema') != SCHEMA:
            unreadable.append(dict(line=number, bytes=len(line), sha256=hashlib.sha256(line).hexdigest(),
                                   reason='not a %s record' % SCHEMA))
            continue
        records.append(value)
    return records, unreadable


def record_call(run_dir, day, record):
    """Append one validated record to <run-dir>/days/<day>/model-clock.jsonl and return the stored record.

    Idempotent: the identical record for the same (piece, call_id) already stored is returned without a second append.
    Raises ValueError on a malformed record (the caller lists it beside its output; see record_or_list)."""
    validate(record, day)
    path = clock_path(run_dir, day)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('model clock path traverses a symbolic link')
    created = not path.parent.is_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    if created:
        _sync_directory(path.parent.parent)
    lock_path = path.with_name(FILE_NAME + '.lock')
    with open(lock_path, 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing, _ = _lines(path)
        same = [r for r in existing if r.get('piece') == record['piece'] and r.get('call_id') == record['call_id']]
        body = _canonical(record)
        for stored in same:
            if _canonical({k: v for k, v in stored.items() if k not in DERIVED}) == body:
                return stored
        stored = dict(record, cutoff_disposition=cutoff_disposition(record['cutoff']), prior_records_for_call=len(same))
        data = _canonical(stored) + b'\n'
        new_file = not path.exists()
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            size = os.fstat(descriptor).st_size
            if size:
                with open(path, 'rb') as tail:
                    tail.seek(size - 1)
                    if tail.read(1) != b'\n':
                        data = b'\n' + data      # a torn earlier line stays as it is, on its own line, listed by readers
            written = 0
            while written < len(data):
                written += os.write(descriptor, data[written:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if new_file:
            _sync_directory(path.parent)
        return stored


def record_or_list(run_dir, day, record, fallback_dir):
    """record_call, never raising: the clock is accounting, never the call's outcome. When run_dir is unknown or the
    write fails, the same record is appended to <fallback_dir>/model-clock-unrecorded.jsonl with the reason (the shape
    Jev's caller uses), so nothing is silent. Returns {recorded, path, reason}."""
    reason = None
    if run_dir is not None:
        try:
            stored = record_call(run_dir, day, record)
            return dict(recorded=True, path=str(clock_path(run_dir, day)), call_id=stored['call_id'],
                        outcome=stored['outcome'])
        except Exception as error:  # noqa: BLE001 - listed beside the output, never hidden
            reason = '%s: %s' % (type(error).__name__, str(error)[:300])
    else:
        reason = 'no owning run directory resolved for this output; the record is listed beside it'
    target = Path(fallback_dir) / UNRECORDED_NAME
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(dict(record, unrecorded_reason=reason), sort_keys=True, default=str) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        reason += '; the fallback list could not be written either (%r)' % error
    return dict(recorded=False, path=str(target), call_id=(record or {}).get('call_id'), reason=reason)


def run_dir_of(out_dir, run, day):
    """The owning run directory of a meeting output (<run>/meeting/<day>[/successors/<sha>]), or None."""
    out_dir = Path(out_dir)
    for parent in out_dir.parents:
        if parent.name == str(run):
            parts = out_dir.relative_to(parent).parts
            if parts[:2] == ('meeting', str(day)):
                return parent
    return None


def cutoff_of(shared_market):
    """The cutoff object from an adviser market context or its reference (frankie_box_adviser_market): the original
    explicit scope plus the normalized clocks of the cutoff instant; absent clocks stay null and are named. A legacy
    input without a context gives {'listed': reason}. Nothing is derived from a target or from Frankie's selections."""
    if not isinstance(shared_market, dict) or not isinstance(shared_market.get('scope'), dict):
        return dict(listed='the call\'s input carries no shared market context (legacy exchange); it was not cut at a '
                           'market instant')
    scope, at = shared_market['scope'], shared_market.get('at') or {}
    cutoff = {k: scope.get(k) for k in CUTOFF_SCOPE}
    cutoff.update(record_count=scope.get('record_count'), position=scope.get('position'),
                  input_cursor=at.get('input_cursor') if type(at.get('input_cursor')) is int else None,
                  adapter_cursor=at.get('adapter_cursor') if type(at.get('adapter_cursor')) is int else None,
                  ts_recv_ns=at.get('ts_recv_ns') if type(at.get('ts_recv_ns')) is int else None,
                  ts_event_ns=at.get('ts_event_ns') if type(at.get('ts_event_ns')) is int else None,
                  publication_frontier_ns=(at.get('publication_frontier_ns')
                                           if type(at.get('publication_frontier_ns')) is int else None),
                  picture_sha256=shared_market.get('picture_sha256'))
    cutoff['clocks_unavailable'] = [k for k in ('ts_recv_ns', 'ts_event_ns', 'publication_frontier_ns') if cutoff[k] is None]
    cutoff['basis'] = ('the original explicit source scope of the shared market context the input was cut at; the '
                       'normalized clocks are those of that cutoff instant; an unavailable clock is null and named')
    return cutoff


def read_day(run_dir, day):
    """Everything a report or the all-99 coverage needs about one day's clock: the file pin, the records, per piece
    the calls by outcome (primary record per call), the repeated observations and the unreadable lines."""
    path = clock_path(run_dir, day)
    if not path.is_file():
        return dict(schema=DAY_SCHEMA, day=str(day), path=str(path), exists=False, records=0, calls={}, unreadable=[])
    raw = path.read_bytes()
    records, unreadable = _lines(path)
    primary, repeats = {}, []
    for r in records:
        key = (r.get('piece'), r.get('call_id'))
        if key in primary:
            repeats.append(dict(piece=key[0], call_id=key[1], outcome=r.get('outcome')))
        else:
            primary[key] = r
    calls = {}
    for (piece, _), r in primary.items():
        by = calls.setdefault(piece, {})
        by[r.get('outcome')] = by.get(r.get('outcome'), 0) + 1
    answered = [r for r in primary.values() if r.get('outcome') == 'answered']
    cutoffs = sorted({(r.get('cutoff') or {}).get('through_cursor') for r in answered
                      if type((r.get('cutoff') or {}).get('through_cursor')) is int})
    return dict(schema=DAY_SCHEMA, day=str(day), path=str(path), exists=True, bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(), records=len(records), distinct_calls=len(primary),
                calls=calls, answered_calls=len(answered),
                answered_cutoffs_through_cursor=cutoffs,
                cutoff_dispositions={d: sum(1 for r in primary.values() if r.get('cutoff_disposition') == d)
                                     for d in sorted({r.get('cutoff_disposition') for r in primary.values()}, key=str)},
                wall_first_start=min((r['wall_start'] for r in primary.values() if _number(r.get('wall_start'))), default=None),
                wall_last_end=max((r['wall_end'] for r in primary.values() if _number(r.get('wall_end'))), default=None),
                repeated_observations=repeats, unreadable=unreadable, causality=CAUSALITY)


def coverage_row(run_dir, day):
    """The clock_model_evaluation row of the day's all-99 coverage: STAMPED with the clock file pin when records exist
    (answered calls named apart from refusals and failures), otherwise NO_CALL with the reason. Never a zero clock."""
    summary = read_day(run_dir, day)
    if summary['exists'] and summary['records']:
        return dict(entry=ENTRY, disposition=STAMPED,
                    reason=('%d model call record(s) this day (%s); answered %d' % (
                        summary['distinct_calls'], json.dumps(summary['calls'], sort_keys=True), summary['answered_calls'])),
                    where=dict(path=summary['path'], bytes=summary['bytes'], sha256=summary['sha256']),
                    producer='frankie_box_model_clock.record_call (meeting, jev, jev_sit_in)', causality=CAUSALITY,
                    summary=summary)
    why = ('no clock file: no model call was recorded on this day (meeting and Jev made none, were not dispatched, or '
           'the runtime refused before any record could be written; see their receipts)' if not summary['exists'] else
           'the clock file holds no readable record (%d unreadable line(s) listed)' % len(summary['unreadable']))
    return dict(entry=ENTRY, disposition=NO_CALL, reason=why, where=dict(path=summary['path']),
                producer='frankie_box_model_clock.record_call', causality=CAUSALITY, summary=summary)
