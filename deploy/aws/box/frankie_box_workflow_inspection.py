"""Opt-in one-day inspection of retained workflow metadata: stdout, and with --write one markdown file per
canonical piece at <run-dir>/days/<day>/inspection/<piece>.md plus index.md (Greg, 2026-10-07: after the ONE-day
test every workflow piece shows what it received, how it used it and what it produced, before the THREE-day run).

Run manually on the owning lane after/between authorized workflow pieces. This module
imports no project code, launches nothing and supplies no knowledge; without --write it writes nothing, with it
only the inspection files above (temporary operator review, never knowledge, never a gate, never read by a step).
It reports recorded processing evidence, never infers consumption from availability.
Large journals, model state, row spools and scientific result parts are not opened.
Use --artifact PIECE=PATH for additional exact JSON metadata or an existing report;
operator-supplied artifacts are labelled unverified references, not adopted evidence.
Step receipts carry an `inspection` object (inputs / use / outputs) where their caller records it (the ROOT, teacher
and Jev callers of frankie_box_experiment.py, Step 8; the school and reports steps, and the successor operation's
state for the owner school recovery, whose chain the school/corrections pieces follow by recorded pins, bounded
depth, the school file itself never opened); the preflight piece projects the owner-local lane records
(the queue's owner binding, save marker and class acknowledgment, the Linux lane controller's last status) by their
known paths, recorded scope only.
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path

# Owner-local lane records (known metadata contracts of frankie_box_frankie_queue.py, frankie_box_cores.py and
# pod_root/controller.py); read only, projected to the run/day asked for. Absent = reported absent, never zero.
QUEUE_DIR = Path('/opt/frankie-box/work/frankie-queue')
CONTROLLER_DIR = Path('/opt/frankie-box/work/cpu-controller')
LANE_ENTRY_FIELDS = ('seq', 'state', 'reason', 'where', 'owner', 'attempts', 'finish', 'save_request', 'save_ack', 'child',
                     'retained_booking', 'retain_error', 'slot_booking', 'source_owner', 'school_day', 'previous', 'resumes',
                     'owner_history', 'save_requests_stale', 'readiness', 'enqueued_utc', 'done_utc')

# Canonical SECTION 0, including conditional/cross-day work; not the ten-item build list.
PIECES = (
    ('preflight', 'Preflight / resume and lane ownership', ()),
    ('ingest', 'Fetch and sealed ingest', ('fetch', 'ingest')),
    ('external', 'Day file / publication availability', ('external',)),
    ('root', 'ROOT calculations / immediate brain publication', ('root',)),
    ('teacher', 'BOSS teacher / Dipole / external section', ('teacher',)),
    ('classroom', 'Classroom / reader / grade / correction / claims', ('classroom',)),
    ('data', 'Governed data export', ('data',)),
    ('search', 'Causal axis / channels / transforms / cells / chance checks', ('search',)),
    ('carried', 'Carried claims / accumulated scientific checking', ('accumulated_lessons', 'lessons')),
    ('findings', 'Today\'s Frankie claims / scientific checking', ('lessons',)),
    ('candidates', 'Cross-day candidate / survivor update', ()),
    ('meeting', 'Three code seats / bounded Granite discussion', ('exchange', 'voice')),
    ('school', 'End-of-day consolidation / numbered reports', ('school', 'reports')),
    ('jev', 'Blind Jev material / sealed claims / testing / delivery', ('jev',)),
    ('corrections', 'Market-only correction / dependent consumption', ('successors',)),
    ('confirmation', 'Separate confirmation (not selected)', ()),
)
METADATA_BYTE_LIMIT = 8 * 1024 * 1024  # reporting budget only; evidence remains intact
CLASSROOM_ONLY = {'classroom', 'findings', 'meeting', 'school', 'jev'}
# Scalar fields and full disposition/processing tables are projected without sampling.
# Unselected fields are named with the exact source reference, never silently discarded.
FIELDS = set('''schema day trading_day run stage key status reason rule caveat counts scope
source_binding calculation_pins derivation root_processes not_run failure_count failures_note
frame_sections frame_sections_schema native_calculation_policy external external_computation
layers producers processed rows entity_rows as_of through_cursor rows_file attachment_file
external_section learner_binding independent_scientific_verification sources notes leakage lags
series cells transforms couplings cells_not_counted not_searched planes directories files excluded
missing unclaimed withheld sections results inputs reused listed selection_listed school_listed
late_knowledge accumulated_claim_tests completed_native_evidence knowledge_retest scientific_operation
claim_inputs_sha256 claims_sha256 claim_inputs searches origin_rule reports report_number
publication brain_entry brain_entries knowledge_available teacher_knowledge_delivery counts_only
binding record evidence model_calls refused_to_run report receipt receipt_sha256 cpu_booking
owner remote_owner remote_calculations calculations target classroom exchange frankie_view
meeting searched_days requested_search_days calls pending_claims operation decision completion
successor_inputs correction_consumption correction_knowledge record_count journal_count
journal_file journal_bytes journal_sha256 partial_members tail_members opening_book
adapter_records f_last_groups learner_reading applied_to versions school_sources stage_knowledge
review source_review findings_listed independent_observations_added source manifest_sha256
file bytes sha256 input_sources deferred lacking missing_series
days remote_days waiting plan_sha256 role day_role remote_attempt remote_batch_key
remote_source_sha256 attempt commit
inspection owner_binding plan_policy shared_market_policy retained_policy mismatch calculation_roots
refused_days root_waiting external_waiting rows_missing interrupted_attempts exit_code
request request_pins stamp output differs receipt_status status_file deliveries pending unresolved_calls
knowledge_after_delivery claims_seal scientific_result unparsed child child_reason client_receipt
school_sha256 successor correction corrections reused_by_child recovery recovery_intent
row school school_status voice_status stages invalidated_by original_receipt progress acknowledgments acknowledgment
non_blocking meeting_status meeting_sha256 classroom_status exchange_status exchange_sha256 previous_attempts
teacher_rows teacher_rows_listed lessons failure candidate phase original replacement scopes invalidation
original_school dependents school_recovery exchange_publication voice_invalidation school_transition
rows_missing rows_refused rows_waiting retries waited_seconds not_queued finish
trigger directory written pieces_written moved_aside cpus cpus_note seconds pending acknowledged requests standing
route attempts operator_dispatch intent admission returned rebook exchange_sha256 github_run_id github_run_attempt
conclusion concluded predecessor meeting_input workflow archive dispatched admitted_utc recorded_utc
'''.split())
# The successor chain (school and corrections pieces): recorded pins {path, bytes, sha256} followed one by one from the
# step receipt, bounded depth, known field names only (never a directory scan); each file is read under the metadata
# ceiling and projected like any other receipt. A pin that does not resolve is reported unavailable, never invented.
FOLLOW = {
    'meeting': ('intent', 'admission', 'returned'),   # the remote voice route's dispatch intent, admission and return
    'school': ('successor', 'correction', 'corrections'),
    'corrections': ('operation', 'progress', 'recovery_intent', 'acknowledgment', 'failure', 'candidate', 'dependents',
                    'school_recovery', 'exchange_publication', 'voice_invalidation', 'invalidation', 'publication'),
}
FOLLOW_DEPTH = 4   # successors step -> state.json -> ack.json -> dependents.json -> school-recovery.json


def pins(record, fields):
    """Absolute JSON paths of the named pin fields (a pin, or a list of pins), recorded scope only."""
    out = []
    for field in fields:
        value = record.get(field)
        for item in (value if isinstance(value, list) else [value]):
            path = absolute(item.get('path')) if isinstance(item, dict) else None
            if path and path.suffix == '.json':
                out.append(path)
    return out


def json_block(body):
    print('```json\n' + json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + '\n```\n')


def read_object(path):
    size = path.stat().st_size
    if size > METADATA_BYTE_LIMIT:
        raise ValueError('not-inspected-too-large: %d bytes exceeds metadata ceiling %d; '
                         'original retained intact at %s' % (size, METADATA_BYTE_LIMIT, path))
    with path.open('rb') as handle:
        raw = handle.read(METADATA_BYTE_LIMIT + 1)
    if len(raw) > METADATA_BYTE_LIMIT:
        raise ValueError('not-inspected-too-large: grew beyond metadata ceiling %d; '
                         'original retained intact at %s' % (METADATA_BYTE_LIMIT, path))
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError('expected a JSON object')
    return body, dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def metadata(path, label):
    """Report exact metadata; failures stay visible and do not hide other pieces."""
    print('### ' + label + '\n')
    try:
        body, pin = read_object(path)
    except (OSError, ValueError) as error:
        json_block(dict(path=str(path), unavailable=str(error)))
        return
    json_block(dict(source_read=pin, recorded={k: v for k, v in body.items() if k in FIELDS},
                    other_fields_retained_at_source=sorted(set(body) - FIELDS)))
    return body


def absolute(value):
    # The run's records use owner-local absolute paths. Never guess another machine's path.
    return Path(value) if isinstance(value, str) and Path(value).is_absolute() else None


def foreign_owner(record):
    # Imported receipt paths belong to their original machine, even if the same
    # absolute path happens to exist here. Inspect original receipts on that lane.
    return bool(record.get('remote_owner') or record.get('remote_attempt')
                or record.get('remote_calculations')
                or record.get('owner') not in (None, 'main'))


def artifact_paths(record, piece):
    """Only known metadata contracts, never recursive scans or giant evidence reads."""
    if foreign_owner(record):
        return []
    out = []
    for field in ('receipt',):
        path = absolute(record.get(field))
        if path:
            out.append(path)
    root = absolute(record.get('calculations'))
    if root and piece == 'root':
        out += [root / 'calculations-receipt.json', root / 'source-binding.json',
                root / 'work/derive.json', root / 'external-computation.json']
    target = absolute(record.get('target'))
    if target and piece in ('data', 'search'):
        out.append(target / 'MANIFEST.json')
    ingest = absolute(record.get('ingest'))
    if ingest and piece == 'external':
        out.append(ingest / 'day-external-receipt.json')
    publication = record.get('brain_entry')
    source_review = publication.get('source_review') if isinstance(publication, dict) else None
    if piece == 'search' and isinstance(source_review, dict):
        path = absolute(source_review.get('path'))
        if path:
            out.append(path)
    classroom = absolute(record.get('classroom'))
    if classroom and piece == 'classroom':
        out += [classroom / name for name in ('receipt.json', 'learner-knowledge.json',
                'completion.json', 'external-completion.json')]
    for item in record.get('days') or []:
        if isinstance(item, dict) and item.get('day') == record.get('_inspection_day'):
            rows = absolute(item.get('rows'))
            if rows:
                out.append(rows / 'receipt.json')
    for field in ('exchange', 'frankie_view', 'meeting'):
        path = absolute(record.get(field))
        if path:
            out.append(path.parent / 'receipt.json')
    if piece == 'jev':
        # the immutable JEV_CPU_REQUEST_V1 (pins of the classroom producer receipt, the search manifest and the
        # runtime) and the helper's bound status beside the receipt
        for field in ('request', 'status_file'):
            path = absolute(record.get(field))
            if path:
                out.append(path)
    return list(dict.fromkeys(out))


def lane_records(run_dir, run, day):
    """The owner-local lane records of one run/day: the queue's two line entries (projected to the day), both line
    workers' last status (their scope), the day-bound save marker and its class acknowledgment, the run's Linux lane
    controller status and latest outcome, and the day's persisted PREVIOUS selection. Known paths only; nothing scanned."""
    print('### Lane ownership, scope, save and resume (owner-local records; recorded scope only)\n')
    for line in ('root', 'class'):
        path = QUEUE_DIR / ('%s.json' % line)
        try:
            body, pin = read_object(path)
        except (OSError, ValueError) as error:
            json_block(dict(path=str(path), unavailable=str(error)))
            continue
        mine = [x for x in body.get('entries') or [] if isinstance(x, dict) and x.get('run') == run and x.get('day') == day]
        json_block(dict(source_read=pin, line=line, entries=[{k: x.get(k) for k in LANE_ENTRY_FIELDS} for x in mine],
                        absent='no %s-line entry names this run/day' % line if not mine else None))
    for path in (QUEUE_DIR / 'root-worker.json', QUEUE_DIR / 'class-worker.json'):
        metadata(path, 'Line worker last status (its authorized scope)')
    marker = QUEUE_DIR / 'save' / ('%s-%s.save-request.json' % (run, day))
    for path, label in ((marker, 'Day-bound save marker (standing now)'),
                        (Path(str(marker) + '.class-ack.json'), 'Class child acknowledgment (standing now)')):
        if path.is_file():
            metadata(path, label)
        else:
            json_block(dict(path=str(path), absent='not standing now (archived copies, if any, sit beside it as <name>.<label>-<epoch>)'))
    state = CONTROLLER_DIR / run
    metadata(state / 'status.json', 'Linux lane controller last status (lease freshness, scope, outcome, held jobs)')
    outcomes = sorted(state.glob('outcome-*.json')) if state.is_dir() else []
    if outcomes:
        metadata(outcomes[-1], 'Linux lane controller latest outcome (never a day completion)')
    previous = run_dir / 'days' / day / 'previous.json'
    if previous.is_file():
        metadata(previous, 'Persisted PREVIOUS classroom selection (create-only; a retry never repicks)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--day', required=True)
    parser.add_argument('--artifact', action='append', default=[], metavar='PIECE=PATH',
                        help='additional exact metadata/report reference for a canonical piece')
    parser.add_argument('--write', action='store_true',
                        help='also write <run-dir>/days/<day>/inspection/<piece>.md per piece and index.md (temporary '
                             'operator review; not knowledge, not a gate; existing files are replaced)')
    args = parser.parse_args()
    try:
        plan, plan_pin = read_object(args.run_dir / 'plan.json')
    except (OSError, ValueError) as error:
        parser.error(str(error))
    # Same encoding as Run.plan_digest; raw plan-file bytes have a separate pin.
    saved_plan_sha256 = hashlib.sha256(json.dumps(
        plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    entries = [e for e in plan['days'] if str(e['day']) == args.day]
    if len(entries) != 1:
        parser.error('--day must select exactly one entry in the saved plan')
    entry = entries[0]
    extra = {name: [] for name, _, _ in PIECES}
    for item in args.artifact:
        piece, separator, name = item.partition('=')
        if not separator or piece not in extra or not Path(name).is_absolute():
            parser.error('--artifact requires a canonical PIECE and absolute PATH')
        extra[piece].append(Path(name))
    records, errors = [], []
    candidates = sorted((args.run_dir / 'days' / args.day).glob('*.json'))
    candidates += sorted((args.run_dir / 'batches').glob('*/*.json'))
    for path in candidates:
        try:
            body, _ = read_object(path)
        except (OSError, ValueError) as error:
            errors.append(dict(path=str(path), unreadable=str(error)))
            continue
        if body.get('run') != plan['run'] or body.get('schema') != 'FRANKIE_EXPERIMENT_STEP_V1':
            errors.append(dict(path=str(path), excluded='not a step receipt for this saved run'))
            continue
        days = [item.get('day') if isinstance(item, dict) else item for item in body.get('days') or []]
        in_scope = (body.get('key') in (args.day, 'day-' + args.day)
                    or args.day in days or args.day in (body.get('searched_days') or [])
                    or args.day in (body.get('requested_search_days') or []))
        if in_scope:
            records.append((path, body.get('stage')))
        elif path.parent == args.run_dir / 'days' / args.day:
            errors.append(dict(path=str(path), excluded='receipt does not name this day'))
    out_dir = args.run_dir / 'days' / args.day / 'inspection'
    written = []

    def emit(text, name=None):
        """The section to stdout; with --write also to its file (one per piece, index.md for the header)."""
        print(text, end='')
        if args.write and name:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / (name + '.md')).write_text(text, encoding='utf-8')
            written.append(name + '.md')

    header = io.StringIO()
    with contextlib.redirect_stdout(header):
        print('# One-day workflow inspection: ' + args.day + '\n')
        print('Temporary operator review only; not knowledge, scientific evidence, or a completion gate. '
              'All values below are recorded metadata. A file, receipt, source-read count or brain publication '
              'does not prove downstream computation. Missing evidence means unknown, never zero. '
              'No journal, row spool, model state or coupling part is replayed or read. '
              'Cross-day batch records retain their full scope; repeated references are not independent tests.\n')
        json_block(dict(plan=plan_pin, plan_sha256=saved_plan_sha256, selected_day=entry,
                        metadata_byte_ceiling=METADATA_BYTE_LIMIT, unreadable_or_excluded_records=errors))
        if args.write:
            print('Pieces (one file each under %s):\n' % out_dir)
            for piece, title, _ in PIECES:
                print('- [%s](%s.md): %s' % (piece, piece, title))
            print()
    emit(header.getvalue(), 'index' if args.write else None)
    for piece, title, stages in PIECES:
        section = io.StringIO()
        with contextlib.redirect_stdout(section):
            inspect_piece(piece, title, stages, args, plan, entry, records, extra, saved_plan_sha256)
        emit(section.getvalue(), piece)
    if args.write:
        print('\nWritten (temporary operator review, not knowledge): %s under %s' % (', '.join(written), out_dir))


def inspect_piece(piece, title, stages, args, plan, entry, records, extra, saved_plan_sha256):
    """One canonical piece's section (printed; the caller captures it)."""
    print('## ' + piece + ': ' + title + '\n')
    if piece == 'preflight':
        lane_records(args.run_dir, plan['run'], args.day)
    if piece in CLASSROOM_ONLY and not entry.get('classroom_arm'):
        print('Not applicable under the saved non-classroom day plan.\n')
    elif piece == 'confirmation':
        print('Separate design/authorization required; this report activates nothing.\n')
    elif piece == 'candidates':
        print('Cross-day boundary; no per-day survivor completion inferred. Candidate generation, '
              'scientific checking and survivor acceptance must be reviewed separately.\n')
    selected = [p for p, stage in records if stage in stages]
    if not selected:
        print('No day-bound step metadata found for this piece. Actual processing/consumption: unknown.\n')
    seen = set()
    for path in selected:
        body = metadata(path, 'Control receipt (not computation proof)')
        if body is None:
            continue
        matches_plan = body.get('plan_sha256') == saved_plan_sha256
        json_block(dict(step_plan_sha256=body.get('plan_sha256'),
                        saved_plan_sha256=saved_plan_sha256,
                        matches_saved_plan=matches_plan))
        if not matches_plan:
            print('Step plan identity missing/different; its artifact paths are not followed.\n')
            continue
        if foreign_owner(body):
            json_block(dict(disposition='foreign-owner-reference-only; artifact paths not opened on this host',
                            owner=body.get('owner'), remote_owner=body.get('remote_owner'),
                            remote_attempt=body.get('remote_attempt'), attempt=body.get('attempt'),
                            instruction='inspect original retained run receipts on the owning lane'))
            continue
        for artifact in artifact_paths(dict(body, _inspection_day=args.day), piece):
            if artifact not in seen:
                seen.add(artifact)
                metadata(artifact, 'Retained producer/consumer metadata (recorded scope only)')
        # the school / corrections pieces: the checked successor chain by its recorded pins (the school successor
        # receipt and correction records; the successor operation, its state, the recovery intent, the acknowledgment
        # and the dependents receipt), bounded depth, each projected as recorded; the school file itself is never opened
        # (its witness is in the receipt), and a disposition read here is a recorded one, not a consumption proof
        queue = [(p, 1) for p in pins(body, FOLLOW.get(piece, ()))]
        while queue:
            artifact, depth = queue.pop(0)
            if artifact in seen or depth > FOLLOW_DEPTH:
                continue
            seen.add(artifact)
            followed = metadata(artifact, 'Successor chain record (recorded scope only; depth %d)' % depth)
            if followed:
                queue += [(p, depth + 1) for p in pins(followed, FOLLOW.get(piece, ()))]
        # Reuse numbered reports as references: never regenerate, modify or substitute them.
        for report in body.get('reports') or []:
            if isinstance(report, dict):
                json_block(dict(existing_report=report, disposition='reuse this normal report; not regenerated'))
    for path in extra[piece]:
        if path.suffix.lower() == '.json':
            metadata(path, 'Operator-supplied metadata (identity/consumption not independently verified)')
        else:
            json_block(dict(existing_artifact=str(path), exists=path.is_file(),
                            disposition='review original on owning lane; not read or transformed'))
    print('Review: reconcile named inputs with recorded processing/channels/results; inspect full '
          'referenced outputs and every listed exclusion/refusal. Unexpected behavior is an operator '
          'finding; this reporter invents no interpretation. If the actual consumer evidence is absent, '
          'record that gap before claiming this piece consumed its inputs.\n')


if __name__ == '__main__':
    main()
