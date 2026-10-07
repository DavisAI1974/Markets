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
shared_market_policy shared_market_sources shared_market_identity shared_market_read shared_market_arithmetic
shared_market_use coverage completeness arithmetic integrity_failure stopped outputs dispositions
frame_dispositions pairing placed_series placed_cells exclusions bedrock input_records data_manifest_sha256
frozen_survivors presented_inputs external_publications completed_sources identity journal equation absent_layers
unclosed_instruments closed_source_without_root_frame unplaceable_input_clocks interpretation limitation view
'''.split())

# Received / used / produced (Greg, 2026-10-07): every piece's report says what it received,
# how it used it and what it produced. These are projections of recorded fields only; a
# field under "used" is the producer's own recorded disposition, never an inference here.
RECEIVED = set('''ingestion_receipt source_binding calculation_pins derivation container journal sources external
identity calculations as_of through_cursor record_count journal_count journal_hash journal_file journal_bytes
journal_sha256 manifest_sha256 data_manifest_sha256 shared_market_identity shared_market_policy learner_binding
day_external day_role partial_members tail_members opening_book input_sources claim_inputs claim_inputs_sha256
searches searched_days requested_search_days frozen_survivors entity binding source commit plan_sha256
'''.split())
USED = set('''coverage completeness arithmetic equation shared_market_arithmetic shared_market_use root_processes not_run
layers dispositions frame_dispositions pairing exclusions leakage lags transforms cells_not_counted not_searched
missing excluded withheld listed reason caveat rule interpretation limitation view absent_layers unclosed_instruments
closed_source_without_root_frame unplaceable_input_clocks completed_sources stopped
'''.split())
PRODUCED = set('''outputs rows entity_rows rows_file attachment_file failure_count status shared_market_sources
presented_inputs external_publications integrity_failure placed_series placed_cells couplings series cells planes
results reports brain_entry brain_entries external_section external_computation frame_sections files
'''.split())

_OUT = []          # the current piece's markdown; stdout when no --write directory is given


def emit(text):
    _OUT.append(text)
    print(text)


def json_block(body):
    emit('```json\n' + json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + '\n```\n')


def received_used_produced(body, label):
    """Three recorded views of one metadata object; nothing sampled, nothing inferred."""
    emit('#### ' + label + ': received / used / produced (recorded fields only)\n')
    json_block(dict(received={k: v for k, v in body.items() if k in RECEIVED},
                    used={k: v for k, v in body.items() if k in USED},
                    produced={k: v for k, v in body.items() if k in PRODUCED},
                    rule='missing evidence reads as unknown, never zero; a recorded output is not proof of downstream use'))
    nested = body.get('shared_market_read')
    if isinstance(nested, dict):
        # The shared market read carries its own inputs (identity pins), use (coverage,
        # arithmetic, dispositions) and outputs (pictures, frontier, integrity failure).
        received_used_produced(nested, label + ' > shared market read')


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
    emit('### ' + label + '\n')
    try:
        body, pin = read_object(path)
    except (OSError, ValueError) as error:
        json_block(dict(path=str(path), unavailable=str(error)))
        return
    json_block(dict(source_read=pin, recorded={k: v for k, v in body.items() if k in FIELDS},
                    other_fields_retained_at_source=sorted(set(body) - FIELDS)))
    received_used_produced(body, path.name)
    return body


def write_piece(directory, piece, text):
    """One markdown file per piece; temporary operator review, never knowledge or a gate."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (piece + '.md')
    pending = path.with_name(path.name + '.pending')
    pending.write_text(text, encoding='utf-8')
    pending.replace(path)
    return path


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
    parser.add_argument('--write', action='store_true',
                        help='also write <run-dir>/days/<day>/inspection/<piece>.md and index.md (Greg, 2026-10-07: '
                             'the one-day test reports; temporary operator review, not knowledge, not a gate)')
    args = parser.parse_args()
    inspection_dir = args.run_dir / 'days' / args.day / 'inspection' if args.write else None
    written = []
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
    header = ('# One-day workflow inspection: ' + args.day + '\n',
              'Temporary operator review only; not knowledge, scientific evidence, or a completion gate. '
              'All values below are recorded metadata. A file, receipt, source-read count or brain publication '
              'does not prove downstream computation. Missing evidence means unknown, never zero. '
              'No journal, row spool, model state or coupling part is replayed or read. '
              'Cross-day batch records retain their full scope; repeated references are not independent tests.\n')
    _OUT.clear()
    for line in header:
        emit(line)
    json_block(dict(plan=plan_pin, plan_sha256=saved_plan_sha256, selected_day=entry,
                    metadata_byte_ceiling=METADATA_BYTE_LIMIT, unreadable_or_excluded_records=errors))
    preamble = '\n'.join(_OUT)
    for piece, title, stages in PIECES:
        _OUT.clear()
        emit('## ' + piece + ': ' + title + '\n')
        if piece in CLASSROOM_ONLY and not entry.get('classroom_arm'):
            emit('Not applicable under the saved non-classroom day plan.\n')
        elif piece == 'confirmation':
            emit('Separate design/authorization required; this report activates nothing.\n')
        elif piece == 'candidates':
            emit('Cross-day boundary; no per-day survivor completion inferred. Candidate generation, '
                 'scientific checking and survivor acceptance must be reviewed separately.\n')
        selected = [p for p, stage in records if stage in stages]
        if not selected:
            emit('No day-bound step metadata found for this piece. Actual processing/consumption: unknown.\n')
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
                emit('Step plan identity missing/different; its artifact paths are not followed.\n')
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
        emit('Review: reconcile named inputs with recorded processing/channels/results; inspect full '
             'referenced outputs and every listed exclusion/refusal. Unexpected behavior is an operator '
             'finding; this reporter invents no interpretation. If the actual consumer evidence is absent, '
             'record that gap before claiming this piece consumed its inputs.\n')
        if inspection_dir is not None:
            written.append((piece, title, write_piece(inspection_dir, piece, preamble + '\n' + '\n'.join(_OUT))))
    if inspection_dir is not None:
        index = [header[0], header[1], 'One file per canonical piece, written from this reporter\'s output after the '
                 'one-day test. Temporary operator review only: not knowledge, not scientific evidence, not a '
                 'completion gate; the brain and the teachers never read these files.\n']
        index += ['- [%s](%s): %s' % (piece, path.name, title) for piece, title, path in written]
        write_piece(inspection_dir, 'index', '\n'.join(index) + '\n')
        print('inspection written: %s (%d pieces + index.md)' % (inspection_dir, len(written)))


if __name__ == '__main__':
    main()
