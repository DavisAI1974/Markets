"""Every data JSON of one day and cycle, from the ROOT, CONFIG and CYCLE processes, for the experiment's teachers.

The processes, in run order: INGEST, AUTHORSHIP, ROOT (calculations), CONFIG (trading-day preparation, principal
inputs, host configuration), CYCLE (one run directory).
Greg, 2026-09-29: "we forgot root in the experiment"; "fix gaps"; and the rule for both teachers (the BOSS teacher and
the scientific teacher, the experiment's search): they read every bit of Frankie's ingest data except the files he
generates himself to reason toward forecasts, so nothing is built a second or third time. Spec:
research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md and SPEC-scientific-teacher.md ("Data access").

Nothing is recomputed or copied: every included file is HARD-LINKED (no second write, no extra disk; the link survives
any later cleanup of the run directory) under /opt/frankie-box/work/experiment-data/<day>/cycle-<NN>/<stage>/<relative
path>, with its bytes and sha256 in MANIFEST.json. Every catalogued pattern lands in exactly one list:
  files     included (data, or a receipt that tells where the data came from);
  excluded  present on disk but kept from the teachers, each with its reason:
              FRANKIE_REASONING  his own notes, analysis, response, ledgers, classroom answers, priming, brain (R09);
              GRADED             grades and the graded answer key (R09/R10: the teachers never see graded outcomes);
              BEDROCK            native artifacts outside the selected completed scientific evidence set;
              MIXED              files carrying data and Frankie's reasoning together; a filter is Greg's call;
              OTHER_MODEL        model output that is not Frankie's (the Granite critic, its self-assessment, the BOSS
                                 forecast journals); where it falls under the rule is Greg's call;
  missing   a catalogued pattern that matched nothing (e.g. a config or cycle stage that never got that far), listed,
            never filled in;
  unclaimed every other file under a given directory that no pattern claims (native pickles, SQLite state, walk
            caches, Markdown, other cycles' files), listed with its bytes so nothing goes unaccounted; not linked.
A day and cycle is exported once: an existing MANIFEST declines the run with the reason (duplicate data). Exactly one
run directory per day and cycle is taken (the caller names it); runs are never merged.
"""
import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

SCHEMA = 'FRANKIE_EXPERIMENT_DATA_V1'
ROOT = Path('/opt/frankie-box/work/experiment-data')

INCLUDE, FRANKIE_REASONING, GRADED, BEDROCK, MIXED, OTHER_MODEL = (
    'INCLUDE', 'FRANKIE_REASONING', 'GRADED', 'BEDROCK', 'MIXED', 'OTHER_MODEL')

# (stage, glob relative to that stage's directory, disposition, what it is). Order matters: the first pattern that
# claims a file decides it, so the specific exclusions come before the broad inclusions.
CATALOG = (
    # INGEST: the gold-standard ingest (/opt/frankie-box/work/ingest-<day>-.../), read in place, never rebuilt
    ('ingest', '**/journal.compact.sqlite', INCLUDE, 'the sealed compact journal (every event, every book level); linked, never rewritten'),
    ('ingest', '**/ingestion-receipt.json', INCLUDE, 'the ingestion receipt: record and journal counts, journal sha256, packing'),
    ('ingest', '**/completion.json', INCLUDE, 'the ingest completion: record_count, journal_count, journal_hash, groups'),
    ('ingest', '**/builder-checkpoint.c15.json', INCLUDE, 'the builder state at completion'),
    ('ingest', '**/day-external.json', INCLUDE, "Frankie's 13 historical points of the day (FRANKIE_DAY_EXTERNAL_V1), "
     'attached beside the sealed ingest; read through its as-of reader'),
    ('ingest', '**/day-external-receipt.json', INCLUDE, 'the day file receipt: sha256, S3 day key, inputs, missing list'),
    ('ingest', '**/*.json', INCLUDE, 'ingest receipts (canary, proofs, manifests)'),
    # AUTHORSHIP: the Monday launch authorship the ROOT requires (/opt/frankie-box/work/monday-launch/<r>/)
    ('authorship', '**/*.json', INCLUDE, 'the launch authorship receipt and its companions'),
    # ROOT: the calculations root (/opt/frankie-box/work/monday-calculations/<root>/)
    ('root', 'work/derived/.projection-v2/**/*', BEDROCK, 'unselected projected aliases, ranges and publication receipts'),
    ('root', 'work/bedrock/**/*', BEDROCK, 'unselected native generations, checkpoint state and staging'),
    ('root', 'work/derived/bedrock_section_*', BEDROCK, 'bedrock sections 4.2 / 4.4'),
    ('root', 'work/classroom/**/*', FRANKIE_REASONING, "Frankie's classroom answers and ledgers (R09)"),
    ('root', 'work/teach/**/*', FRANKIE_REASONING, "Frankie's priming (R09)"),
    ('root', 'work/boss-jobs/**/*', FRANKIE_REASONING, "the principal's model calls (R09)"),
    ('root', 'work/reading*.json', FRANKIE_REASONING, "Frankie's reading corpus and plan (R09)"),
    ('root', 'work/knowledge-base-*.json', FRANKIE_REASONING, "the pin of Frankie's brain (R09)"),
    ('root', 'work/writing.json', FRANKIE_REASONING, "Frankie's writing stage (R09)"),
    ('root', 'work/granite-self-assessment.json', OTHER_MODEL, "Granite's self-assessment as the critic"),
    ('root', 'work/comparison.json', MIXED, 'derived layers beside the frozen brain (brain = Frankie)'),
    ('root', 'out/**/*', FRANKIE_REASONING, "Frankie's response, analysis, attestations (R09)"),
    ('root', 'work/derive.json', INCLUDE, 'the derivation receipt: every layer, status, producer, sha256, row counts'),
    ('root', 'work/native-layer-records.json', INCLUDE, 'one record per native registry layer: crosswalk id, group, status, '
     'reason and projection pin (FRANKIE_ROOT_NATIVE_LAYER_RECORDS_V1), bound to derive.json\'s bytes'),
    ('root', 'work/derived/legacy_*.json', INCLUDE, 'the five legacy layers: price, signed flow, roll20, book frames, structure'),
    ('root', 'work/derived/.rows/*.jsonl', INCLUDE, 'the ROOT row spools: every INPUT record, prices, book frames, structures, failures'),
    ('root', 'work/labels.json', INCLUDE, 'timing labels computed by code'),
    ('root', 'work/digest-proof.json', INCLUDE, 'exact table proofs for the digest'),
    ('root', 'work/derive-only-measurement.json', INCLUDE, 'digest size'),
    ('root', 'work/verify.json', INCLUDE, 'the session verification receipt'),
    ('root', 'calculation-pins.json', INCLUDE, 'the whole-day calculation pin'),
    ('root', 'source-binding.json', INCLUDE, 'the sealed journal the calculations read'),
    ('root', 'calculations-receipt.json', INCLUDE, 'the calculations receipt'),
    ('root', 'external-computation.json', INCLUDE, 'exact row/field consumption of the date-bound external file'),
    ('root', 'progress.json', INCLUDE, 'progress probe'),
    ('root', 'checkpoints.json', INCLUDE, 'progress checkpoints'),
    # CONFIG: the trading-day preparation, the principal inputs, the host configuration
    ('preparation', 'schedule/schedule.json', INCLUDE, 'the day schedule: cutoffs, steps, sessions per cycle, from the journal'),
    ('preparation', 'schedule/receipt.json', INCLUDE, 'the schedule receipt'),
    ('preparation', 'prefixes/*.json', INCLUDE, 'the prefix bindings and witnesses'),
    ('preparation', '*.json', INCLUDE, 'preparation configuration, intent and receipts'),
    ('principal_inputs', 'knowledge-base-receipt.json', FRANKIE_REASONING, "the pin of Frankie's brain (R09)"),
    ('principal_inputs', 'principal-inputs-receipt.json', MIXED, "calculation result together with the shared knowledge (Frankie's brain)"),
    ('principal_inputs', 'retained-witnesses.json', INCLUDE, 'the retained historical contract sections'),
    ('host_config', 'actual-host-configuration.json', INCLUDE, 'the whole host run configuration'),
    # TEACHER: the experiment's teacher-only step (1 day in 5, batched per day; /opt/frankie-box/work/experiment-teacher-rows/<day>/)
    ('teacher', 'host-dipole-classroom-source*.json', INCLUDE, "the teacher's Dipole measurements from the teacher-only step"),
    ('teacher', '*.json', INCLUDE, 'the teacher-only step receipt'),
    # CYCLE: one run directory (/opt/frankie-box/work/runs/<run_id>/), this cycle's execution/cycle-<NN>/
    ('run', 'execution/cycle-{cycle}/host-dipole-classroom-teacher-key*', GRADED, 'the graded answer key (R10)'),
    ('run', 'execution/cycle-{cycle}/classroom-audit/*post-grade*', GRADED, 'the classroom grade (R10)'),
    ('run', 'execution/cycle-{cycle}/classroom-audit/**/*', FRANKIE_REASONING, "Frankie's teach-back, novelty, acknowledgement (R09)"),
    ('run', 'execution/cycle-{cycle}/principal/session-response.json', FRANKIE_REASONING, "Frankie's reply (R09)"),
    ('run', 'execution/cycle-{cycle}/principal/classroom-correction-response.json', FRANKIE_REASONING, "Frankie's correction reply (R09)"),
    ('run', 'execution/cycle-{cycle}/principal/session-request.json', MIXED, "the request: the classroom package together with Frankie's knowledge base"),
    ('run', 'execution/cycle-{cycle}/principal/classroom-correction-request.json', INCLUDE, "the teacher's correction request"),
    ('run', 'execution/cycle-{cycle}/principal/**/*', INCLUDE, 'principal adapter receipts and witnesses'),
    ('run', 'execution/cycle-{cycle}/critic-spool/**/*', OTHER_MODEL, 'the Granite critic request and answer'),
    ('run', 'execution/cycle-{cycle}/actual-critic-request.json', OTHER_MODEL, 'the Granite critic request'),
    ('run', 'execution/cycle-{cycle}/host-dipole-classroom-source*', INCLUDE, "the teacher's Dipole measurements (JournalTeacherR3), lossless"),
    ('run', 'execution/cycle-{cycle}/host-dipole-classroom-pre-message*', INCLUDE, "the teacher's message into the classroom"),
    ('run', 'execution/cycle-{cycle}/**/*.json', INCLUDE, 'cycle receipts, request plan, waits, journal pins, feedback'),
    ('run', 'execution/cycle-{cycle}/**/*.jsonl', INCLUDE, 'cycle event logs'),
    ('run', 'handoff-*/**/*', OTHER_MODEL, "the BOSS controller and native journals and forecast records (the native system's own forecasts)"),
    ('run', 'host-progress/**/*', INCLUDE, 'run progress and native training events'),
    ('run', 'execution/*.json', INCLUDE, 'execution identity'),
    ('run', '*.json', INCLUDE, 'run-level host receipts'),
)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(64 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def _pin(path):
    """(bytes, sha256, seconds) of one linked file; a worker-pool job (one file per worker, largest first)."""
    path = Path(path)
    started = time.time()
    size, digest = path.stat().st_size, _sha256(path)
    return size, digest, round(time.time() - started, 3)


def _pin_all(paths, workers):
    """Pin every linked file. The export's wall time is the hashing (the sealed journal alone is ~23.7 GB, the
    V2 frame spool several GB); files are independent, so the held lane's workers hash them side by side, the
    largest first so one long file does not trail a drained pool. The identities are the same bytes and the same
    sha256 whatever the worker count: a speed-up never changes a pin. Effect unmeasured here; bounded above by
    the largest single file (serial inside one file) and by the volume's read throughput (the work directory is
    EBS: the hash is I/O-bound there, so the per-file seconds recorded below show whether the disk or the CPU
    was the wall). Recorded in MANIFEST.hashing for the one-day canary."""
    paths = sorted(paths, key=lambda p: Path(p).stat().st_size, reverse=True)
    started = time.time()
    if workers <= 1 or len(paths) <= 1:
        measured = {str(p): _pin(p) for p in paths}
        mode = 'serial'
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=min(workers, len(paths))) as pool:
            measured = dict(zip((str(p) for p in paths), pool.map(_pin, paths)))
        mode = 'process_pool'
    pins = {path: (size, digest) for path, (size, digest, _) in measured.items()}
    slowest = sorted(((seconds, size, path) for path, (size, _, seconds) in measured.items()), reverse=True)[:5]
    wall = round(time.time() - started, 3)
    total_bytes = sum(size for size, _ in pins.values())
    return pins, dict(mode=mode, workers=min(workers, len(paths)) if mode == 'process_pool' else 1,
                      files=len(paths), bytes=total_bytes, seconds=wall,
                      bytes_per_second=round(total_bytes / wall) if wall > 0 else None,
                      largest_file_bytes=max((size for size, _ in pins.values()), default=0),
                      slowest_files=[dict(seconds=s, bytes=b, path=p) for s, b, p in slowest],
                      basis='one file per worker, largest first; identities invariant; measure on the one-day canary; '
                            'bytes_per_second against the volume throughput says whether the disk was the wall')


def plan(day, cycle, dirs):
    """(files, excluded, missing, notes) for one day and cycle: every catalogued file decided by the first pattern that
    claims it; a directory not given is listed, never guessed."""
    claimed, files, excluded, missing, notes = set(), [], [], [], []
    native_entries = None
    if dirs.get('root') and Path(dirs['root']).is_dir():
        from frankie_box_experiment_native import selected_files
        files.extend(selected_files(dirs['root'], day))
        native_entries = _native_entry_files(Path(dirs['root']), files, missing)
        claimed.update(Path(item['source']).resolve() for item in files)
    for stage, pattern, disposition, what in CATALOG:
        base = dirs.get(stage)
        glob = pattern.format(cycle=cycle)
        if base is None:
            missing.append(dict(stage=stage, pattern=glob, what=what, reason='no %s directory given' % stage))
            continue
        base = Path(base)
        if not base.is_dir():
            missing.append(dict(stage=stage, pattern=glob, what=what, reason='%s directory %s absent' % (stage, base)))
            continue
        matched = [p for p in sorted(base.glob(glob)) if p.is_file() and not p.is_symlink()]
        fresh = [p for p in matched if p.resolve() not in claimed]
        if not matched:
            missing.append(dict(stage=stage, pattern=glob, what=what,
                                reason='nothing on disk (the stage may not have got this far)'))
            continue
        for p in fresh:
            claimed.add(p.resolve())
            item = dict(stage=stage, path=str(p.relative_to(base)), source=str(p), pattern=glob, what=what)
            if disposition == INCLUDE:
                files.append(item)
            else:
                excluded.append(dict(item, reason=disposition, bytes=p.stat().st_size))
    unclaimed = []
    for stage, base in dirs.items():
        if base and Path(base).is_dir():
            for p in sorted(Path(base).rglob('*')):
                if p.is_file() and not p.is_symlink() and p.resolve() not in claimed:
                    unclaimed.append(dict(stage=stage, path=str(p.relative_to(base)), bytes=p.stat().st_size))
    notes.append(dict(unclaimed=unclaimed))
    notes.append(dict(native_entries=native_entries))
    return files, excluded, missing, notes


def _native_entry_files(root, files, missing):
    """The 18 native-only registry entries (Greg, 2026-10-07: they reach Frankie and both teachers) in this export:
    per entry its carriers (the ROOT projection plan's producers' crosswalk when selected, else the retained crosswalk
    text), the exact ledgers that carry its rows (linked by selected_files; the search places them on the F_LAST axis at
    their exact emission cursor), the ROOT's own record of the projected layer (derive.json layers[<entry>]) and that
    projected layer file, linked here with its derive.json pin (the same ledger rows as the producers projected them;
    the search reads the ledgers once, so the projection is availability for the teachers, never a second observation).
    Nothing produced is listed missing with the ROOT's reason; nothing is recomputed."""
    import frankie_box_all99_coverage as ALL99
    from frankie_box_experiment_native import PROJECTION_PLAN, entry_carriers
    roles = {f.get('native_role'): f for f in files if f.get('native_role')}
    derive_path = root / 'work' / 'derive.json'
    derive = json.loads(derive_path.read_bytes()) if derive_path.is_file() else {}
    layers = derive.get('layers') or {}
    plan_item = roles.get(PROJECTION_PLAN)
    carriers = entry_carriers(json.loads(Path(plan_item['source']).read_bytes())) if plan_item else None
    out = {}
    for name in ALL99.NATIVE_ENTRIES:
        spec = (carriers or {}).get(name) or dict(ALL99.NATIVE_SERIES[name], source='retained crosswalk carrier text (NATIVE_SERIES)')
        layer = layers.get(name) if isinstance(layers.get(name), dict) else {}
        projected = None
        path = Path(layer['path']) if isinstance(layer.get('path'), str) else None
        if path is not None and layer.get('bedrock') and path.is_absolute() and path.is_file() and not path.is_symlink():
            try:
                relative = path.relative_to(root)
            except ValueError:
                relative = None
            if relative is not None and type(layer.get('bytes')) is int and layer.get('sha256'):
                files.append(dict(stage='root', path=str(relative), source=str(path), pattern='derive.json layers[%s]' % name,
                                  what='the projected bedrock layer %s (the exact ledger rows as the producers\' crosswalk '
                                       'projects them); availability for the teachers, not a second observation' % name,
                                  native_entry=name, expected=dict(bytes=layer['bytes'], sha256=layer['sha256']),
                                  expected_from='derive.json layers[%s]' % name))
                projected = str(relative)
        if projected is None:
            missing.append(dict(stage='root', pattern='derive.json layers[%s]' % name, what='projected bedrock layer %s' % name,
                                reason=('no completed native calculation selected in this ROOT' if not roles else
                                        'derive.json records no projected file for this layer: status %s (%s)'
                                        % (layer.get('status'), layer.get('reason')))))
        out[name] = dict(member=list(spec.get('member') or ()), sections=list(spec.get('sections') or ()),
                         carrier_source=spec.get('source'),
                         ledgers=[r for r in ('exact_member_rows.jsonl', 'exact_lifecycle_rows.jsonl') if r in roles],
                         root_status=layer.get('status'), root_reason=layer.get('reason'), root_count=layer.get('count'),
                         projected_file=projected)
    return dict(entries=out, rule='the search reads the exact native ledgers once (exact emission cursor on the F_LAST axis); '
                                  'the projected layer files are the same rows, linked for availability; nothing averaged')


def workflow_report(day, cycle, dirs, files, excluded, missing, unclaimed, external, hashing, *, status):
    """The piece's inputs / use / outputs record for the one-day review (Greg, 2026-10-07): what the export received
    (every directory it was given, every file it linked with path/bytes/sha256 and source binding), how it used it
    (the first-pattern catalog decision per file: linked, excluded with its reason, missing, unclaimed; nothing
    recomputed, nothing copied) and what it produced (the manifest, the counts, the external attachment state). A link
    is availability for the teachers, never proof that a teacher consumed the file. Schema shared with the adviser
    pieces so one reporter projects it (frankie_box_workflow_inspection.workflow_report_block)."""
    by_stage = {}
    for item in files:
        by_stage.setdefault(item['stage'], dict(files=0, bytes=0))
        by_stage[item['stage']]['files'] += 1
        by_stage[item['stage']]['bytes'] += item.get('bytes') or 0
    return dict(schema='FRANKIE_PIECE_WORKFLOW_REPORT_V1', piece='data',
                inputs=dict(day=str(day), cycle=str(cycle),
                            directories={k: (str(v) if v else None) for k, v in dirs.items()},
                            directories_absent=[m for m in missing if m['reason'].startswith('no ') or 'absent' in m['reason']],
                            received_files=[dict(stage=f['stage'], path=f['path'], source=f['source'], bytes=f.get('bytes'),
                                                 sha256=f.get('sha256'), what=f['what'],
                                                 source_binding=f.get('pattern'),
                                                 native_role=f.get('native_role')) for f in files],
                            external_day_file=external, shared_market_picture=None, shared_market_dispositions=None),
                use=dict(decision_rule='the first catalog pattern that claims a file decides it (CATALOG order); '
                                       'selected native evidence is claimed first by selected_files',
                         linked_by_stage=by_stage,
                         excluded=[dict(stage=e['stage'], path=e['path'], reason=e['reason'], bytes=e['bytes'], what=e['what'])
                                   for e in excluded],
                         missing=missing, unclaimed=unclaimed,
                         withheld_roles=dict(FRANKIE_REASONING='R09', GRADED='R10', BEDROCK='unselected native state',
                                             MIXED="Greg's call", OTHER_MODEL="Greg's call"),
                         computation='none: hard links only; bytes and sha256 measured on the linked inode',
                         hashing=hashing,
                         producer_pins_checked=hashing.get('producer_pins_checked'),
                         dipole_rows=('teacher directory given; its rows are linked' if dirs.get('teacher')
                                      else 'no teacher directory given: the day is exported without the teacher-only '
                                           'Dipole rows (listed missing; a launch run may still carry them)')),
                outputs=dict(status=status, manifest='MANIFEST.json beside the links',
                             counts=dict(files=len(files), bytes=sum(f.get('bytes') or 0 for f in files),
                                         excluded=len(excluded), missing=len(missing), unclaimed=len(unclaimed)),
                             external=external, model_calls=0, waits=[],
                             refusals='an existing MANIFEST declines a second export; a failed hard link refuses the '
                                      'whole export (a copy would be a second build), nothing partial is published'),
                rule='recorded inputs, use and outputs of this piece for the one-day review; availability is not proof '
                     'of consumption; missing evidence means unknown, never zero')


def export(day, cycle, dirs, root=ROOT, workers=1):
    target = Path(root) / str(day) / f'cycle-{cycle}'
    if (target / 'MANIFEST.json').exists():
        raise SystemExit('%s already exported (%s): the same day and cycle is not exported twice (duplicate data declines '
                         'the run); move it aside with a receipt to redo it' % (target, target / 'MANIFEST.json'))
    files, excluded, missing, notes = plan(day, cycle, dirs)
    staging = target.parent / (target.name + '.partial')
    if staging.exists():
        shutil.rmtree(staging)
    for item in files:
        destination = staging / item['stage'] / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(item['source'], destination)
            item['linked'] = True
        except OSError as error:
            raise SystemExit('cannot hard-link %s (%s): a copy would be a second build of the data; nothing written'
                             % (item['source'], error))
        item['destination'] = str(destination)
    # Producer pins (Greg, 2026-10-07: integrity stays a separate visible failure): the sealed journal's bytes and
    # sha256 are pinned in its ingestion receipt; the selected native artifacts carry their derivation pins. The
    # export still measures every linked inode itself; a measurement that differs from the producer's pin is
    # corruption of the source, raised with both named, never re-pinned quietly as the new identity.
    receipts = [f for f in files if f['stage'] == 'ingest' and Path(f['path']).name == 'ingestion-receipt.json']
    if len(receipts) == 1:
        rc = json.loads(Path(receipts[0]['source']).read_bytes())
        # the receipt names its journal relative to its own directory (the teacher opens receipt.parent / journal_file)
        journal_path = (str(Path(receipts[0]['path']).parent / rc['journal_file'])
                        if isinstance(rc.get('journal_file'), str) else None)
        for item in files:
            if (item['stage'] == 'ingest' and journal_path is not None and item['path'] == journal_path
                    and type(rc.get('journal_bytes')) is int and rc.get('journal_sha256')):
                item['expected'] = dict(bytes=rc['journal_bytes'], sha256=rc['journal_sha256'])
                item['expected_from'] = 'ingestion-receipt.json (BOSS_BLOCK_INGESTION_RECEIPT_V1 journal pin)'
    pins, hashing = _pin_all([item['destination'] for item in files], workers)
    for item in files:
        item['bytes'], item['sha256'] = pins[item.pop('destination')]
        if item.get('expected') and item['expected'] != {k: item[k] for k in ('bytes', 'sha256')}:
            raise ValueError('linked artifact differs from its producer pin (%s): %s measured %s, pinned %s'
                             % (item.get('expected_from', 'native derivation'), item['source'],
                                {k: item[k] for k in ('bytes', 'sha256')}, item['expected']))
    hashing['producer_pins_checked'] = [dict(path=f['path'], stage=f['stage'], pinned_by=f.get('expected_from', 'native derivation'))
                                        for f in files if f.get('expected')]
    ext = [f for f in files if f['stage'] == 'ingest' and Path(f['path']).name == 'day-external.json']
    external = (dict(status='attached', path='ingest/' + ext[0]['path'], sha256=ext[0]['sha256'], bytes=ext[0]['bytes'])
                if len(ext) == 1 else
                dict(status='absent' if not ext else 'more than one (listed in files)',
                     s3_key='frankie/day_external/%s/day-external.json' % day))
    if len(ext) == 1:
        # Frankie's points tied to the 99 (2026-10-07): the registry entries each point of the day file declares it feeds
        # (frankie_box_all99_coverage.external_point_entries); the search places each point at its publication stamp
        import frankie_box_all99_coverage as ALL99
        points = (json.loads(Path(ext[0]['source']).read_bytes()).get('points') or {})
        external['registry_entries'], external['registry_entry_findings'] = {}, []
        for point, table in sorted(points.items()):
            mapped = ALL99.external_point_mapping(table)
            external['registry_entries'][point] = dict(entries=mapped['entries'], mapping=mapped['mapping'],
                                                       mapping_reason=mapped['mapping_reason'],
                                                       event_time_basis=mapped['event_time_basis'], note=mapped['note'])
            external['registry_entry_findings'].extend(dict(f, point=point) for f in mapped['findings'])
    manifest = dict(schema=SCHEMA, day=str(day), cycle=str(cycle), at=time.time(), external=external,
                    directories={k: (str(v) if v else None) for k, v in dirs.items()},
                    files=files, excluded=excluded, missing=missing, unclaimed=notes[0]['unclaimed'],
                    native_entries=notes[1]['native_entries'],
                    counts=dict(files=len(files), bytes=sum(f['bytes'] for f in files), excluded=len(excluded),
                                missing=len(missing), unclaimed=len(notes[0]['unclaimed']),
                                unclaimed_bytes=sum(u['bytes'] for u in notes[0]['unclaimed'])),
                    rule=('both teachers read every data file of the day except the files Frankie generates himself to '
                          'reason toward forecasts (R09), grades (R10), mixed files and other models\' output; '
                          'selected complete native ledgers and section products are shared, checkpoint/staging state '
                          'and duplicate projected aliases remain excluded; hard links only, nothing recomputed; '
                          'availability is not proof of teacher consumption'),
                    hashing=hashing)
    manifest['workflow_report'] = workflow_report(day, cycle, dirs, files, excluded, missing, notes[0]['unclaimed'],
                                                  external, hashing, status='exported')
    staging.mkdir(parents=True, exist_ok=True)
    (staging / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(staging, target)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--day', required=True)
    p.add_argument('--cycle', required=True)
    p.add_argument('--ingest', help='the ingest directory: /opt/frankie-box/work/ingest-<day>-...')
    p.add_argument('--authorship', help='the launch authorship directory: /opt/frankie-box/work/monday-launch/<r>')
    p.add_argument('--calculations', required=True, help='the ROOT: /opt/frankie-box/work/monday-calculations/<root>')
    p.add_argument('--preparation', help='/opt/frankie-box/work/trading-day-preparation/<r>')
    p.add_argument('--principal-inputs', help='/opt/frankie-box/work/principal-inputs/<r>')
    p.add_argument('--host-config', help='/opt/frankie-box/work/monday-run-config/<r>')
    p.add_argument('--run', help='ONE run directory: /opt/frankie-box/work/runs/<run_id>')
    p.add_argument('--teacher', help='the teacher-only step directory of the day: /opt/frankie-box/work/experiment-teacher-rows/<day>')
    p.add_argument('--plan-only', action='store_true', help='print what would be linked, excluded and missing; write nothing')
    p.add_argument('--workers', type=int, default=1,
                   help='processes hashing the linked files side by side (the held lane gives 15); identities unchanged')
    a = p.parse_args()
    if a.workers < 1:
        raise SystemExit('--workers must be a positive integer')
    if not (len(a.day) == 8 and a.day.isdigit() and a.cycle.isdigit()):
        raise SystemExit('--day YYYYMMDD and --cycle NN required')
    dirs = dict(ingest=a.ingest, authorship=a.authorship, root=a.calculations, preparation=a.preparation, principal_inputs=a.principal_inputs,
                host_config=a.host_config, run=a.run, teacher=a.teacher)
    for name, value in dirs.items():
        if value and not str(Path(value).resolve()).startswith('/opt/frankie-box/'):
            raise SystemExit('%s must be under /opt/frankie-box' % name)
    if a.plan_only:
        files, excluded, missing, notes = plan(a.day, a.cycle, dirs)
        print(json.dumps(dict(files=[(f['stage'], f['path']) for f in files],
                              excluded=[(e['stage'], e['path'], e['reason']) for e in excluded],
                              missing=[(m['stage'], m['pattern'], m['reason']) for m in missing],
                              unclaimed=[(u['stage'], u['path'], u['bytes']) for u in notes[0]['unclaimed']]), indent=1))
        return
    m = export(a.day, a.cycle, dirs, workers=a.workers)
    print(json.dumps(dict(target=str(ROOT / a.day / ('cycle-' + a.cycle)), counts=m['counts'], hashing=m['hashing'],
                          excluded=[(e['stage'], e['path'], e['reason']) for e in m['excluded']],
                          missing=[(x['stage'], x['pattern'], x['reason']) for x in m['missing']],
                          unclaimed=[(u['stage'], u['path'], u['bytes']) for u in m['unclaimed']]), indent=1))


if __name__ == '__main__':
    main()
