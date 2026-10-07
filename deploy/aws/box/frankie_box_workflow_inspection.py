"""Opt-in, stdout-only one-day inspection of retained workflow metadata.

Run manually on the owning lane after/between authorized workflow pieces. This module
imports no project code, launches nothing and supplies no knowledge. By default it writes
nothing; with --write it also writes one markdown file per canonical piece under
<run-dir>/days/<day>/inspection/ plus index.md (Greg, 2026-10-07: after the one-day test
every piece reports what it received, how it used it and what it produced). Those files
are temporary operator review only, never knowledge, evidence or a gate.
It reports recorded processing evidence, never infers consumption from availability.
Large journals, model state, row spools and scientific result parts are not opened.
Use --artifact PIECE=PATH for additional exact JSON metadata or an existing report;
operator-supplied artifacts are labelled unverified references, not adopted evidence.
Step receipts carry an `inspection` object (inputs / use / outputs) where their caller records it (the ROOT, teacher
and Jev callers of frankie_box_experiment.py, Step 8; the school and reports steps, and the successor operation's
state for the owner school recovery, whose chain the school/corrections pieces follow by recorded pins, bounded
depth, the school file itself never opened); the preflight piece projects the owner-local lane records
(the queue's owner binding, save marker and class acknowledgment, the Linux lane controller's last status) by their
known paths, recorded scope only. The teacher receipt, the data export MANIFEST and the search MANIFEST carry their
own FRANKIE_PIECE_WORKFLOW_REPORT_V1 (workflow_report), projected whole. The search also writes workflow-report.json
beside its MANIFEST (FRANKIE_SEARCH_WORKFLOW_REPORT_FILE_V1: the same report with every long list named by its count
and exact MANIFEST location), read here so the search piece reports even when its MANIFEST exceeds the ceiling.
"""
import argparse
import hashlib
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
    ('candidates', 'Cross-day candidate / survivor update', ('survivors',)),
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
shared_market_context shared_market_context_listed shared_market adviser_market_reader workflow_report
claims_seal scientific_result deliveries client_receipt pending unparsed jev_withheld teacher_rows
teacher_rows_listed lessons exchange_hash refused_to_run inputs
received phase_timings timings read pinned
axis discovery fft_cache hashing exact_membership equation_not_run findings
school school_sha256 school_status school_listed index row number_assigned_now built_from revision supersedes
classroom_copy classroom_copy_listed exchange_sha256 meeting_sha256 meeting_status problems
successor correction corrections reused_by_child school_recovery dependents native_results native_intent
acknowledgments learner_consumption selected_knowledge checked_overlay_sha256 visible_evidence_sha256
all_knowledge_consumed native_learning_performed forecast_replaced pending_feedback_preserved
original_request_sha256 original_response_sha256 host_attestation_sha256 request_sha256 response_sha256 session_id
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
input_verification producer_pins_checked slowest_files bytes_per_second dipole_missing dipole exported_from this_root
walk_seconds
all99 all99_coverage all99_boundary all99_coverage_files evidence_read missing_listed withheld_listed candidates_by_status
same_pair_candidates native_pass native_entries native_carriers opening_state layer_entries survivors boundary_day
batch_days shared_runtime superseded_jev_runtime route_integrity shared_field
exhaustion_d native_only_ingestion model_clock use_counts registry_entries registry_mapping registry_entry_findings
confirmation_clock external_points
root_execution native_overlap timing parse
cpu_placement pool_recovery
workflow_report_file leakage_failed source_passes native_selection_check journal_witness
'''.split())
WORKFLOW_REPORT_SCHEMA = 'FRANKIE_PIECE_WORKFLOW_REPORT_V1'   # the pieces' own inputs / use / outputs record
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

# Received / used / produced (Greg, 2026-10-07): every piece's report says what it received,
# how it used it and what it produced. These are projections of recorded fields only; a
# field under "used" is the producer's own recorded disposition, never an inference here.
RECEIVED = set('''ingestion_receipt source_binding calculation_pins derivation container journal sources external
identity calculations as_of through_cursor record_count journal_count journal_hash journal_file journal_bytes
journal_sha256 manifest_sha256 data_manifest_sha256 shared_market_identity shared_market_policy learner_binding
day_external day_role partial_members tail_members opening_book input_sources claim_inputs claim_inputs_sha256
searches searched_days requested_search_days frozen_survivors entity binding source commit plan_sha256
teacher_rows shared_market_external teacher_shared_market_arithmetic learner_reading carried_from_previous
school_knowledge stage_knowledge classroom_rules experiment_directive received
school school_sha256 built_from exchange_sha256 meeting_sha256 original_request_sha256 original_response_sha256
checked_overlay_sha256 visible_evidence_sha256 selected_knowledge
'''.split())
USED = set('''coverage completeness arithmetic equation shared_market_arithmetic shared_market_use root_processes not_run
layers dispositions frame_dispositions pairing exclusions leakage lags transforms cells_not_counted not_searched
missing excluded withheld listed reason caveat rule interpretation limitation view absent_layers unclosed_instruments
closed_source_without_root_frame unplaceable_input_clocks completed_sources stopped
shared_market anchor_pictures source_status_counts applied_to phase_timings timings read
axis exact_membership fft_cache hashing equation_not_run input_verification producer_pins_checked walk_seconds
school_listed problems number_assigned_now meeting_status school_status
rows_missing rows_refused rows_waiting external_waiting refused_days root_waiting dipole_missing retries waited_seconds
all99 all99_coverage all99_boundary evidence_read missing_listed withheld_listed candidates_by_status same_pair_candidates
native_pass native_entries native_carriers opening_state layer_entries shared_runtime
cpu_pinning
cpu_placement pool_recovery source_passes native_selection_check journal_witness leakage_failed
'''.split())
PRODUCED = set('''outputs rows entity_rows rows_file attachment_file failure_count status shared_market_sources
presented_inputs external_publications integrity_failure placed_series placed_cells couplings series cells planes
results reports brain_entry brain_entries external_section external_computation frame_sections files
mode components observations pairs novel_findings novel_finding_ids dropped_findings correction_ids
teacher_complete completion_hash external_novel_finding_ids jev_material saved_phases stop_requested
discovery findings unclaimed survivors all99_coverage_files
report_number revision supersedes classroom_copy index row file sha256 bytes learner_consumption
all_knowledge_consumed native_learning_performed forecast_replaced pending_feedback_preserved
workflow_report_file
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
    workflow_report_block(body, path.name)
    nested_workflow_reports(body, path.name)
    return body


def nested_workflow_reports(body, label):
    """A piece whose own record sits inside a retained envelope: the correction consumer's
    FRANKIE_ORIGINAL_SESSION_KNOWLEDGE_REPRODUCTION_V1 travels as learner_consumption inside the follow-up
    receipt/response (the dependents' native-results file carries that receipt whole). Known field names, one
    level each, never a scan; the flags beside it are projected as recorded; the reproduction body stays at source."""
    for field in ('receipt', 'response', 'learner_consumption'):
        inner = body.get(field)
        if not isinstance(inner, dict):
            continue
        if field == 'learner_consumption':
            json_block(dict(learner_consumption={k: inner.get(k) for k in (
                'schema', 'original_request_sha256', 'original_response_sha256', 'checked_overlay_sha256',
                'visible_evidence_sha256', 'scope', 'native_learning_performed', 'independent_scientific_verification',
                'all_knowledge_consumed', 'pending_feedback_preserved')},
                selected_knowledge=[{k: d.get(k) for k in ('path', 'bytes', 'sha256')}
                                    for d in inner.get('selected_knowledge') or [] if isinstance(d, dict)],
                disposition='the analytical consumer\'s record; a reproduction is not native learning, a forecast '
                            'rerun or scientific confirmation'))
            workflow_report_block(inner, label + ' > learner_consumption')
        else:
            nested_workflow_reports(inner, label + ' > ' + field)


def workflow_report_block(body, label):
    """The piece's own FRANKIE_PIECE_WORKFLOW_REPORT_V1 (exchange, Granite meeting, Jev CPU, Jev sit-in; since
    2026-10-07 also the BOSS teacher receipt, the data export MANIFEST and the search MANIFEST): the
    inputs it received (the cutoff picture's source, as_of/through_cursor, hash, bytes), how it used them
    (which picture values reached which prompt or record, what a role or the privacy wall withheld, every
    missing/stale/unavailable disposition, caps that refused) and what it produced (seals, inputs with pins,
    model calls made or refused, waits). Projected whole from the receipt; prompt bodies are never in it and
    a picture appears only as its exact reference."""
    report = body.get('workflow_report')
    if not isinstance(report, dict):
        return
    emit('#### ' + label + ': the piece\'s own inputs / use / outputs record\n')
    if report.get('schema') != WORKFLOW_REPORT_SCHEMA:
        json_block(dict(workflow_report=report, disposition='unknown workflow report schema; shown as recorded'))
        return
    for section in ('inputs', 'use', 'outputs'):
        emit('##### ' + section + ' (' + str(report.get('piece')) + ')\n')
        json_block(report.get(section))
    json_block(dict(rule=report.get('rule'),
                    disposition='temporary operator review; a recorded prompt delivery is not proof of consumption, '
                                'learning or that a model experienced every historical picture'))


def classroom_projection(receipt, path):
    """The classroom's shared-picture inputs / use / outputs, from its own receipt.json only.

    What the classroom received from the shared source (identity, exhaustion, layers), how each
    component used it (which anchor pictures entered which answer field; which anchors, inputs,
    layers were partial/missing/unavailable; which legacy aggregates stayed completed-only and
    why), and what it produced (answers, claims, corrections, a refusal, saved operations).
    Recorded dispositions only; nothing here is inferred, filled in, knowledge or a gate.
    """
    if receipt.get('schema') != 'FRANKIE_EXPERIMENT_CLASSROOM_RECEIPT_V2' or path.name != 'receipt.json':
        return
    shared = receipt.get('shared_market') or {}
    coverage = shared.get('coverage') or {}
    use = receipt.get('shared_market_use') or {}
    learner = receipt.get('learner_reading') or {}
    emit('#### classroom shared picture: inputs / use / outputs (recorded in receipt.json; not computation proof)\n')
    json_block(dict(
        status=receipt.get('status'), mode=receipt.get('mode'),
        inputs=dict(
            # every input the classroom recorded receiving, with path/bytes/sha256 and the whole-day binding
            # (FRANKIE_CLASSROOM_RECEIVED_V1; None on a receipt written before the field existed)
            received=receipt.get('received'),
            shared_source_identity=shared.get('identity'),
            shared_source_read=dict(source_exhausted=coverage.get('source_exhausted'),
                                    core_report_complete=coverage.get('core_report_complete'),
                                    journal=coverage.get('journal'), layers_present=sorted(coverage.get('layers') or {}),
                                    layers_not_in_read=coverage.get('layers_not_in_read'),
                                    core_absent_layers=coverage.get('core_absent_layers'),
                                    core_coverage=coverage.get('core_coverage'), external=coverage.get('external'),
                                    source_status_counts=shared.get('source_status_counts')),
            anchor_pictures=shared.get('anchor_pictures'),
            shared_market_external=receipt.get('shared_market_external'),
            teacher_shared_market_arithmetic=receipt.get('teacher_shared_market_arithmetic'),
            learner_reading=dict(ingestion_receipt=learner.get('ingestion_receipt'), coverage=learner.get('coverage'),
                                 shared_market_arithmetic=learner.get('shared_market_arithmetic')),
            external_day_file=(receipt.get('external') or {}).get('day_file')),
        use=dict(entered=use.get('entered'), arithmetic=use.get('arithmetic'), components=use.get('components'),
                 partial_missing_stale=use.get('partial_missing_stale'), completed_only=use.get('completed_only'),
                 knowledge_applied_to=(receipt.get('stage_knowledge') or {}).get('applied_to'),
                 # where the time went: the classroom's own full ordered pass (pictures seen, when the last
                 # anchor was retained, the tail after it) and seconds per saved operation; diagnostic only
                 shared_read_timing=(use.get('received') or {}).get('read'),
                 phase_timings=receipt.get('phase_timings'),
                 # the six native entries' arithmetic on the same pass (18 of 18; the receipt's compact view, its whole
                 # result pinned in native-entry-arithmetic.json): status, reason, per entry its use / form / series /
                 # pairs / unavailable carriers, the file pin and the timings, as recorded
                 native_entries=_native_entries_projection(receipt.get('native_entries')),
                 # the cutoff limits the classroom received (env or defaults, each with its source)
                 native_cutoff=(receipt.get('received') or {}).get('native_cutoff'),
                 limit=use.get('limit') or shared.get('limit')),
        outputs=dict(
            # every file the classroom produced, with its pin, and the brain entry's manifest entries
            # (FRANKIE_CLASSROOM_OUTPUTS_V1; None on a receipt written before the field existed)
            pinned=receipt.get('outputs'),
            components=receipt.get('components'), observations=receipt.get('observations'), pairs=receipt.get('pairs'),
            novel_finding_ids=receipt.get('novel_finding_ids'), dropped_findings=receipt.get('dropped_findings'),
            correction_ids=receipt.get('correction_ids'), teacher_complete=receipt.get('teacher_complete'),
            completion_hash=receipt.get('completion_hash'),
            external={k: (receipt.get('external') or {}).get(k) for k in (
                'correction_ids', 'mastered', 'teacher_complete', 'completion_hash', 'series_absent',
                'missing_not_assigned', 'deferred')},
            external_novel_finding_ids=receipt.get('external_novel_finding_ids'),
            brain_entry=receipt.get('brain_entry'), jev_material=receipt.get('jev_material'),
            refusal=(dict(reason=receipt.get('reason'), listed=receipt.get('listed'))
                     if receipt.get('status') == 'refused' else None),
            failure=(dict(reason=receipt.get('reason'), error_type=receipt.get('error_type'), listed=receipt.get('listed'),
                          saved_phases=receipt.get('saved_phases'), stage_reached=receipt.get('stage_reached'),
                          exit_code=receipt.get('exit_code'), phase_progress=_phase_progress(path))
                     if receipt.get('status') == 'failed' else None),
            waits='phase-progress.json (saved_phases, stop_requested) shows a saved or waiting classroom; '
                  'status complete means every operation finished on this lane'),
        disposition='temporary operator review; a listed anchor, input or layer disposition is what the classroom '
                    'recorded for a thinner instant, not a verdict on the day; nothing here is knowledge or a gate'))
    all99_section(receipt.get('all99_coverage'), 'classroom all-99 coverage (receipt.json all99_coverage)')


NATIVE_ENTRY_KEYS = ('use', 'form', 'reason', 'own_series', 'thin_series', 'series_names', 'relations', 'pearson_reported',
                     'pairs', 'unavailable', 'carriers', 'disposition', 'not_computed', 'rows_covered')


def _native_entries_projection(native):
    """The classroom receipt's native_entries (frankie_box_classroom_code.native_entries_compact) as recorded: status,
    reason, per entry NATIVE_ENTRY_KEYS, the file pin and every recorded timing (a key naming seconds); None = the receipt
    carries no such section (written before it existed): unknown, never zero."""
    if not isinstance(native, dict):
        return None
    entries = native.get('entries') if isinstance(native.get('entries'), dict) else {}
    return dict(schema=native.get('schema'), status=native.get('status'), reason=native.get('reason'),
                file=native.get('file'),
                # the cutoff (None = no limit reached) and the limits it ran under (frankie_box_classroom_code)
                cutoff=native.get('cutoff'), cutoff_limits=native.get('cutoff_limits'),
                entries={name: {k: item.get(k) for k in NATIVE_ENTRY_KEYS if k in item}
                         for name, item in sorted(entries.items()) if isinstance(item, dict)},
                series_kinds=native.get('series_kinds'), read=native.get('read'),
                timings={k: v for k, v in native.items() if 'seconds' in k or k in ('timings', 'phase_timings')},
                other_fields_retained_at_source=sorted(k for k in native if k not in (
                    'schema', 'status', 'reason', 'file', 'entries', 'series_kinds', 'read', 'timings', 'phase_timings',
                    'cutoff', 'cutoff_limits')
                    and 'seconds' not in k))


def _phase_progress(receipt_path):
    """phase-progress.json beside a classroom receipt: its saved phases and last event, as recorded; absent = unknown."""
    path = receipt_path.with_name('phase-progress.json')
    try:
        body, pin = read_object(path)
    except (OSError, ValueError) as error:
        return dict(path=str(path), unavailable=str(error))
    return dict(source_read=pin, saved_phases=body.get('saved_phases'), last_event=body.get('last_event'),
                stop_requested=body.get('stop_requested'), saved_at=body.get('saved_at'))


def all99_section(block, label):
    """A piece's all-99 list as its own section: the piece's own counts, and the shared field
    (FRANKIE_ALL99_COVERAGE_V1; the block itself or its nested shared_field) with its counts in the one vocabulary, its
    integrity findings and every entry row (entry, role, word, the piece's word, reason, consumer). Recorded only."""
    if not isinstance(block, dict):
        return
    shared = block if block.get('schema') == 'FRANKIE_ALL99_COVERAGE_V1' else block.get('shared_field')
    emit('#### ' + label + '\n')
    json_block(dict(piece_schema=block.get('schema'), piece_counts=block.get('counts'), piece_by_role=block.get('by_role'),
                    use_counts=block.get('use_counts'), native_only_ingestion=block.get('native_only_ingestion'),
                    route_integrity=block.get('route_integrity'), requests=block.get('requests'),
                    shared_counts=(shared or {}).get('counts'), shared_by_role=(shared or {}).get('by_role'),
                    integrity=(shared or {}).get('integrity'), integrity_ok=(shared or {}).get('integrity_ok'),
                    listed=(shared or {}).get('listed'), registry=(shared or {}).get('registry'),
                    absent=block.get('absent'), thin=block.get('thin'),
                    disposition='what this piece recorded; an arrival is not proof that an equation used the entry; '
                                'absent/thin keeps the day; integrity is listed apart'))
    rows = (shared or {}).get('entries') or []
    if rows:
        emit('| entry | role | disposition | piece word | use | reason | consumer | day-file points |\n'
             '|---|---|---|---|---|---|---|---|')
        for e in rows:
            if isinstance(e, dict):
                emit('| %s | %s | %s | %s | %s | %s | %s | %s |' % tuple(str(e.get(k)).replace('|', '/').replace('\n', ' ') for k in (
                    'entry', 'role', 'disposition', 'piece_disposition', 'use', 'reason', 'consumer', 'external_points')))
        emit('')


def candidates_projection(receipt, path):
    """The survivor/candidate update receipt (FRANKIE_SURVIVOR_UPDATE_RECEIPT_V1): the survivors document pin, the
    counts by status, the per-day all-99 coverage files (pins only, never opened here) and the boundary."""
    if receipt.get('schema') != 'FRANKIE_SURVIVOR_UPDATE_RECEIPT_V1':
        return
    report = receipt.get('workflow_report') or {}
    emit('#### candidates: survivor update (recorded in %s; candidates are not acceptance)\n' % path.name)
    json_block(dict(status=receipt.get('status'), boundary_day=receipt.get('boundary_day'), batch_days=receipt.get('batch_days'),
                    survivors=receipt.get('survivors'), reused=receipt.get('reused'), counts=receipt.get('counts'),
                    candidates_by_status=(report.get('outputs') or {}).get('candidates_by_status'),
                    all99_coverage_files=(report.get('outputs') or {}).get('all99_coverage_files'),
                    all99_boundary=(report.get('use') or {}).get('all99_boundary'),
                    listed=receipt.get('listed'), integrity_failures=receipt.get('integrity_failures'),
                    late_knowledge=receipt.get('late_knowledge'), publication=receipt.get('publication'),
                    disposition='temporary operator review; the pinned coverage files are not opened here'))


def keep_running_projection(run_dir):
    """<run>/keep-running.json (FRANKIE_KEEP_RUNNING_V1): every KeepRunning tag event of this run as recorded (a JSON
    list), under the metadata ceiling; absent = no event recorded, never 'kept running'."""
    path = run_dir / 'keep-running.json'
    emit('### KeepRunning tag events (FRANKIE_KEEP_RUNNING_V1; recorded scope only)\n')
    try:
        size = path.stat().st_size
        if size > METADATA_BYTE_LIMIT:
            raise ValueError('not-inspected-too-large: %d bytes' % size)
        raw = path.read_bytes()
        events = json.loads(raw)
    except (OSError, ValueError) as error:
        json_block(dict(path=str(path), unavailable=str(error)))
        return
    json_block(dict(source_read=dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
                    events=events if isinstance(events, list) else None,
                    malformed=None if isinstance(events, list) else 'expected a JSON list of events',
                    disposition='a tag request is not proof the box stayed up or stopped; the idle guard decides on its own'))


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


def lane_records(run_dir, run, day):
    """The owner-local lane records of one run/day: the queue's two line entries (projected to the day), both line
    workers' last status (their scope), the day-bound save marker and its class acknowledgment, the run's Linux lane
    controller status and latest outcome, and the day's persisted PREVIOUS selection. Known paths only; nothing scanned."""
    emit('### Lane ownership, scope, save and resume (owner-local records; recorded scope only)\n')
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
        value = record.get(field)
        # a receipt is a path, or a pin {path, bytes, sha256} (the survivors step records its child's receipt pin)
        path = absolute(value.get('path') if isinstance(value, dict) else value)
        if path:
            out.append(path)
    root = absolute(record.get('calculations'))
    if root and piece == 'root':
        out += [root / 'calculations-receipt.json', root / 'source-binding.json',
                root / 'work/derive.json', root / 'external-computation.json',
                root / 'work/native-layer-records.json',      # per native layer status (second review F4)
                root / 'work/native-overlap.json']            # ROOT process 2 beside process 1: child, CPUs, seconds, outcome
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
    if piece == 'school':
        # The school step's record names the school file (never opened here: it inlines the day's lessons, exchange
        # and meeting); its small index (the indexed original) or successor receipt (a checked successor) is the
        # contract. The reports step writes its receipt beside its index, <reports-dir>/receipts/<run>/<day>.json
        # (its workflow_report: what the reports received, carried, withheld and produced); the index keeps every build.
        school_file = absolute(record.get('file')) if record.get('stage') == 'school' else None
        if school_file is None and isinstance(record.get('school'), dict):
            school_file = absolute(record['school'].get('file'))
        if school_file:
            out.append(school_file.with_name('receipt.json') if 'successors' in school_file.parts
                       else school_file.with_name('index.json'))
        reports = [absolute(r.get('file')) for r in record.get('reports') or [] if isinstance(r, dict)]
        reports = [r for r in reports if r]
        if reports and record.get('run') and record.get('_inspection_day'):
            out.append(reports[0].parent / 'receipts' / str(record['run']) / (str(record['_inspection_day']) + '.json'))
            out.append(reports[0].parent / 'index.json')
    classroom = absolute(record.get('classroom'))
    if classroom and piece == 'classroom':
        out += [classroom / name for name in ('receipt.json', 'learner-knowledge.json',
                'completion.json', 'external-completion.json', 'phase-progress.json')]
    for item in record.get('days') or []:
        if isinstance(item, dict) and item.get('day') == record.get('_inspection_day'):
            rows = absolute(item.get('rows'))
            if rows:
                # The teacher-only step: its receipt.json (FRANKIE_EXPERIMENT_TEACHER_ROWS_V1 with the piece's
                # workflow report), the measured knowledge the Run filed beside it (teacher-knowledge.json) and
                # the BOSS teacher's external-section receipt. Rows, attachment and walk state are never opened.
                out += [rows / 'receipt.json', rows / 'teacher-knowledge.json',
                        rows / 'external-section' / 'receipt.json']
    if target and piece == 'search':
        # The search's own findings record (its brain source) and the symbolic discovery index
        # beside its MANIFEST; coupling parts and equation parts are never opened here.
        out += [target / 'knowledge-findings.json', target / 'discovery' / 'INDEX.json',
                # the search's own one-day review file (FRANKIE_SEARCH_WORKFLOW_REPORT_FILE_V1): its workflow report with
                # long lists named by count and exact MANIFEST location, readable when the MANIFEST outgrows the ceiling
                target / 'workflow-report.json']
    entries = [record.get('brain_entry'), record.get('teacher_brain_entry')]
    if isinstance(record.get('brain_entries'), dict):
        entries += list(record['brain_entries'].values())
    for publication in entries:
        if isinstance(publication, dict):
            # The immediate brain commit of this piece: its MANIFEST only (pins of what was filed).
            entry = absolute(publication.get('path')) or absolute(publication.get('entry'))
            if entry:
                out.append(entry if entry.suffix == '.json' else entry / 'MANIFEST.json')
    for field in ('exchange', 'frankie_view', 'meeting'):
        path = absolute(record.get(field))
        if path:
            out.append(path.parent / 'receipt.json')
    if piece == 'jev':
        # The Jev CPU piece: its receipt.json (JEV_CPU_RECEIPT_V1 with the piece's workflow report),
        # owner.json (identity, the shared market context pin) and the sit-in client receipt beside it.
        # Material, claims, transcript and the retained picture itself are never opened here.
        for field in ('jev', 'jev_receipt', 'jev_output', 'output'):
            path = absolute(record.get(field))
            if path:
                base = path.parent if path.suffix == '.json' else path
                out += [base / 'receipt.json', base / 'owner.json', base / 'client-receipt.json']
        # the immutable JEV_CPU_REQUEST_V1 (pins of the classroom producer receipt, the search manifest and the
        # runtime) and the helper's bound status beside the receipt (Step 8 caller records)
        for field in ('request', 'status_file'):
            path = absolute(record.get(field))
            if path:
                out.append(path)
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
                    or args.day in (body.get('batch_days') or []) or body.get('boundary_day') == args.day
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
        if piece == 'preflight':
            lane_records(args.run_dir, plan['run'], args.day)
            keep_running_projection(args.run_dir)
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
            if isinstance(body.get('all99'), dict):
                # the ROOT step's per-day production/admission list (FRANKIE_ALL99_ADMISSION_V1) as its own section
                all99_section(body['all99'], '%s step all-99 (%s all99)' % (piece, path.name))
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
                    retained = metadata(artifact, 'Retained producer/consumer metadata (recorded scope only)')
                    if piece == 'classroom' and isinstance(retained, dict):
                        classroom_projection(retained, artifact)
                    if piece == 'candidates' and isinstance(retained, dict):
                        candidates_projection(retained, artifact)
                    if isinstance(retained, dict) and piece not in ('classroom',):
                        # every other piece's own all-99 list (teacher receipt, search MANIFEST, core read, ROOT step)
                        for key in ('all99_coverage', 'all99'):
                            if isinstance(retained.get(key), dict) and (retained[key].get('schema') or '').startswith('FRANKIE_ALL99'):
                                all99_section(retained[key], '%s all-99 (%s %s)' % (piece, artifact.name, key))
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
