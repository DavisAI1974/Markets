"""Opt-in, stdout-only one-day inspection of retained workflow metadata.

Run manually on the owning lane after/between authorized workflow pieces. This module
imports no project code, writes nothing, launches nothing and supplies no knowledge.
It reports recorded processing evidence, never infers consumption from availability.
Large journals, model state, row spools and scientific result parts are not opened.
Use --artifact PIECE=PATH for additional exact JSON metadata or an existing report;
operator-supplied artifacts are labelled unverified references, not adopted evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path

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
'''.split())


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
    return list(dict.fromkeys(out))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--day', required=True)
    parser.add_argument('--artifact', action='append', default=[], metavar='PIECE=PATH',
                        help='additional exact metadata/report reference for a canonical piece')
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
    print('# One-day workflow inspection: ' + args.day + '\n')
    print('Temporary operator review only; not knowledge, scientific evidence, or a completion gate. '
          'All values below are recorded metadata. A file, receipt, source-read count or brain publication '
          'does not prove downstream computation. Missing evidence means unknown, never zero. '
          'No journal, row spool, model state or coupling part is replayed or read. '
          'Cross-day batch records retain their full scope; repeated references are not independent tests.\n')
    json_block(dict(plan=plan_pin, plan_sha256=saved_plan_sha256, selected_day=entry,
                    metadata_byte_ceiling=METADATA_BYTE_LIMIT, unreadable_or_excluded_records=errors))
    for piece, title, stages in PIECES:
        print('## ' + piece + ': ' + title + '\n')
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
