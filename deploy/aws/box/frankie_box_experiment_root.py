"""The experiment's ROOT for any ingested day (Greg, 2026-09-29: "we forgot root in the experiment"). Spec:
research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md, step 3.

The Monday ROOT (frankie_box_monday_calculations.py) starts from Monday's launch authorship and its recovered-ingestion
descriptor; neither exists for another day, and the experiment forecasts nothing through the full pipeline, so it needs
no authorship. This ROOT starts from the day's own sealed ingest (BOSS_BLOCK_INGESTION_RECEIPT_V1, written by
frankie_box_ingest_block.sh ACTION=ingest), pins it (receipt sha256 given by the caller; the journal's bytes and sha256
checked against the receipt), builds the SAME whole-day calculation pin (whole_day_pin_document, shared with the Monday
ROOT), and runs the SAME Session.derive with the NATIVE PASS ON for the experiment (Greg reversed the 2026-09-29
no-bedrock decision, 2026-10-07: the 18 native-only registry entries are carried only by the native member/lifecycle
ledgers and must reach Frankie and both teachers): ROOT process 1 (the legacy pass: every INPUT record, the five legacy
layers and the row spools), the existing native traversal and compressed projection with opening state and complete
recovery (processes 2+3; the giant bedrock tables are not rendered), and process 4 (the Markdown digest) when asked.
--bedrock defaults to on; every NEW orchestrator request carries the shared market policy, under which the wrapper
passes --bedrock on. --bedrock off remains only for an older saved legacy plan (kept as saved, never mutated): its pin
rule text and its source binding stay byte-identical so its retained ROOT resumes unchanged.
Nothing is re-ingested: the sealed journal is read in place, read-only. Incomplete data never stops the day: a
partial member (the trading-day cut) is carried, producer failures are listed in the receipt and every other record is
calculated (status calculations_retained_with_failures). A day already calculated declines (duplicate
data). A confirmation day is refused unless the frozen survivor list is given (R15: confirmation days stay untouched).
"""
import argparse
import hashlib
import json
import os
import signal
import time
import uuid
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frankie_box_prepare_trading_day import require_checkout, witness, safe_path  # noqa: E402
from frankie_box_author_monday_launch import fresh, sync_directory  # noqa: E402
from frankie_box_monday_calculations import whole_day_pin_document  # noqa: E402

PARENT = Path('/opt/frankie-box/work/experiment-roots')
INGESTION_SCHEMA = 'BOSS_BLOCK_INGESTION_RECEIPT_V1'
REPOSITORY = Path(__file__).resolve().parents[3]       # this checkout's root (the one that builds the documents)
CHECKOUT_REBIND_SCHEMA = 'FRANKIE_ROOT_CHECKOUT_REBIND_V1'


def _checkout_relative(path):
    """`path` relative to this checkout's root, or None when it is not inside it."""
    try:
        return Path(path).relative_to(REPOSITORY).as_posix()
    except (TypeError, ValueError):
        return None


def content_rebinds(saved, built, where='$'):
    """Identity is content, not location (Greg, 2026-10-07: a saved ROOT resumes from any checkout of the same source).

    Compares a saved ROOT document with the one this checkout builds. Returns [] when they are equal; the list of
    checkout moves when the ONLY differences are file witnesses ({path, bytes, sha256, ...}) whose bytes, sha256 and
    every other key are equal and whose paths name the same file inside a checkout: the current path is
    <this checkout>/<rel> and the saved path is <another absolute prefix>/<rel>. Returns None for any other difference
    (a hash, bytes, schema, data_workers, policy, a key, a value type, a path outside the checkout). Old saved documents
    (absolute paths of the checkout that wrote them) fall under the same rule; nothing saved is rewritten."""
    if isinstance(saved, dict) and isinstance(built, dict):
        if set(saved) != set(built):
            return None
        moves = []
        if ({'path', 'bytes', 'sha256'} <= set(saved) and saved['path'] != built['path']
                and isinstance(saved['path'], str) and isinstance(built['path'], str)):
            rel = _checkout_relative(built['path'])
            if (rel is None or not saved['path'].startswith('/') or not saved['path'].endswith('/' + rel)
                    or len(saved['path']) <= len(rel) + 1):
                return None
            for key in sorted(saved):
                if key != 'path' and content_rebinds(saved[key], built[key], '%s.%s' % (where, key)) != []:
                    return None
            return [dict(at=where, saved_path=saved['path'], current_path=built['path'], relative=rel,
                         saved_checkout=saved['path'][:-len(rel) - 1], current_checkout=str(REPOSITORY),
                         bytes=saved['bytes'], sha256=saved['sha256'])]
        for key in sorted(saved):
            found = content_rebinds(saved[key], built[key], '%s.%s' % (where, key))
            if found is None:
                return None
            moves.extend(found)
        return moves
    if isinstance(saved, list) and isinstance(built, list):
        if len(saved) != len(built):
            return None
        moves = []
        for i, (a, b) in enumerate(zip(saved, built)):
            found = content_rebinds(a, b, '%s[%d]' % (where, i))
            if found is None:
                return None
            moves.extend(found)
        return moves
    # leaves: equal value AND equal JSON type (True never equals 1 here)
    return [] if type(saved) is type(built) and saved == built else None


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(64 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def _save_new_complete(path, value):
    """Publish complete JSON exclusively; an interrupted temporary stays for recovery."""
    path = Path(path)
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    pending = path.with_name(path.name + '.pending-' + uuid.uuid4().hex)
    with pending.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(pending, path)  # atomic, and refuses to replace an existing publication
    sync_directory(path.parent)
    pending.unlink()
    sync_directory(path.parent)


def calculate_day(commit, receipt_path, receipt_sha256, day, day_role, output_root, data_workers=1, digest=False,
                  frozen_survivors=None, resume=False, *, bedrock=True, shared_market_policy=None, bedrock_off_cause=None):
    requested = [False]
    previous_handler = signal.signal(signal.SIGTERM, lambda *_: requested.__setitem__(0, True))
    stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')
    def save_requested():
        return requested[0] or bool(stop_file and Path(stop_file).exists())
    try:
        result = _calculate_day(commit, receipt_path, receipt_sha256, day, day_role, output_root, data_workers,
                                digest, frozen_survivors, resume, save_requested=save_requested, bedrock=bedrock,
                                shared_market_policy=shared_market_policy, bedrock_off_cause=bedrock_off_cause)
        if save_requested():
            from research.kalshi.frankie_boss.parallel_teacher import TeacherSaved
            raise TeacherSaved('ROOT completion published; resume uses the completed receipt')
        return result
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


def _calculate_day(commit, receipt_path, receipt_sha256, day, day_role, output_root, data_workers=1, digest=False,
                   frozen_survivors=None, resume=False, save_requested=None, bedrock=True, shared_market_policy=None,
                   bedrock_off_cause=None):
    require_checkout(commit)
    # Why the native pass is off, stated to Session.derive (second review F5; correction_consumer cceb191 defines the
    # causes): the caller's explicit cause when given; otherwise this ROOT's own request decides it. A request WITHOUT
    # the shared market policy is an older saved legacy plan run with its saved native-off setting (legacy_plan, kept as
    # saved, never mutated); a request WITH the policy defaults the native pass on, so off there was selected by the
    # caller (caller_override, e.g. BEDROCK=off given to the wrapper). This route never turns the pass off after a
    # failure (no native_pass_failed fallback exists here: a failed native pass is the ROOT's own failure). Bedrock on:
    # no cause, derive.json unchanged.
    if bedrock:
        bedrock_off_cause = None
    elif bedrock_off_cause is None:
        bedrock_off_cause = 'legacy_plan' if shared_market_policy is None else 'caller_override'
    if day_role not in ('discovery', 'confirmation'):
        raise ValueError('day role discovery or confirmation required')
    if day_role == 'confirmation' and not (frozen_survivors and Path(frozen_survivors).is_file()):
        raise ValueError('a confirmation day stays untouched until the survivor list is frozen (give it)')
    if shared_market_policy is not None:
        from frankie_box_market_timeline import SCHEMA as timeline_schema, binding as timeline_binding
        if shared_market_policy != timeline_schema:
            raise ValueError('the shared market policy requires its exact version')
        # Greg, 2026-10-07: an absent native layer thins the shared picture; it never blocks the
        # day. Every NEW request runs the native pass (bedrock on); only an older saved legacy plan ran
        # without it, and then the reader lists native.member/native.lifecycle absent.
    receipt_pin = witness(safe_path(receipt_path))
    if receipt_pin['sha256'] != receipt_sha256:
        raise ValueError('ingestion receipt differs from the sha256 given')
    receipt = json.loads(Path(receipt_path).read_bytes())
    if receipt.get('schema') != INGESTION_SCHEMA or receipt.get('writer') != 'compact':
        raise ValueError('a compact BOSS_BLOCK_INGESTION_RECEIPT_V1 is required')
    if receipt.get('trading_day') != day:
        raise ValueError('the ingestion receipt is for trading day %s, not %s' % (receipt.get('trading_day'), day))
    # A partial member is how a trading day is cut from its UTC partitions (the take up to the 17:00 ET halt; the rest
    # is the next day's): it is the whole day, carried and listed in the binding, never a reason to refuse the day.
    partial_members = list(receipt.get('partial_members') or [])
    # A day that opens at the prior day's halt (a tail member) opens with the prior day's closing book, the same one its
    # ingest opened with (Greg, 2026-09-29): read again in place from the prior day's sealed ingest and checked against
    # what this day's ingest recorded; the legacy pass replays the day's records onto it. Absent = listed, never refused.
    tail_members = list(receipt.get('tail_members_ingested') or receipt.get('tail_members') or [])
    directory = Path(receipt_path).parent
    opening_book, opening_state = receipt.get('opening_book'), None
    own = receipt.get('opening_book_file')
    if own:
        # the day's own ingest wrote the book it opened with beside the journal (seeded or warmed from the tail partition):
        # the same bytes, sha256 checked against the receipt; no prior day is needed
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from research.kalshi.frankie_boss.c15_journal import unpack
        raw = (directory / own['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != own['sha256']:
            raise ValueError('the opening book beside the journal differs from its ingestion receipt')
        opening_state = unpack(json.loads(raw))
    elif opening_book and opening_book.get('status') == 'seeded':
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from research.kalshi.frankie_boss import opening_book as opening_books
        opening_state, again = opening_books.load(opening_book['receipt'])
        if any(again[k] != opening_book[k] for k in ('checkpoint_sha256', 'checkpoint_state_hash', 'adapter_state_hash')):
            raise ValueError('the prior day\'s closing book differs from the one this day\'s ingest opened with')
    elif tail_members:
        opening_book = dict(opening_book or {}, status='absent',
                            listed='this day opens at the prior halt and its ingest had no opening book; the legacy pass '
                                   'starts from an empty book')
    journal = directory / receipt['journal_file']
    # Hashed once per ROOT process: the stat-keyed cache (frankie_box_filehash) is the one Session.derive's input
    # reader witnesses the same container with, so the multi-GB journal is read for its sha256 once, not twice. Same
    # bytes, same sha256, same refusal on any difference.
    import frankie_box_filehash
    journal_witness = frankie_box_filehash.witness(journal)
    if journal_witness != dict(bytes=receipt['journal_bytes'], sha256=receipt['journal_sha256']):
        raise ValueError('the sealed journal differs from its ingestion receipt (bytes or sha256)')
    completion_path = directory / 'completion.json'
    completion = json.loads(completion_path.read_bytes())
    for key in ('record_count', 'journal_count', 'journal_hash'):
        if completion.get(key) != receipt.get(key):
            raise ValueError('completion.json %s differs from the ingestion receipt' % key)
    container = dict(path=str(journal), bytes=receipt['journal_bytes'], sha256=receipt['journal_sha256'],
                     count=receipt['journal_count'], head=receipt['journal_hash'])
    # Frankie's 13 historical points attached beside the sealed ingest (FRANKIE_DAY_EXTERNAL_V1, Greg 2026-09-29):
    # read through the same as-of reader as the search/teachers, with every table field counted exactly.
    ext_path, ext_receipt = directory / 'day-external.json', directory / 'day-external-receipt.json'
    if ext_path.is_file() and ext_receipt.is_file():
        want = json.loads(ext_receipt.read_bytes())
        have = _sha256_file(ext_path)
        if have != want.get('sha256'):
            raise ValueError('day-external.json beside the ingest differs from its receipt')
        from research.kalshi.frankie_boss.operations.frankie_day_external import AsOfReader, computation_receipt
        body = json.loads(ext_path.read_bytes())
        external_computation = computation_receipt(AsOfReader(body, body['halt_ns']), day)
        external = dict(status='attached', path=str(ext_path), sha256=have, bytes=ext_path.stat().st_size,
                        receipt=str(ext_receipt), receipt_sha256=_sha256_file(ext_receipt), s3_key=want.get('s3_key'),
                        missing=len(want.get('missing') or []))
    else:
        external = dict(status='absent', expected=str(ext_path), s3_key='frankie/day_external/%s/day-external.json' % day,
                        reason='not attached beside the ingest when the ROOT ran (frankie_box_day_external.sh ACTION=link)')
    manifest = dict(manifest_hash=receipt['manifest_hash'],
                    note='the day manifest by hash; its members are in the ingestion receipt (the bedrock traversal, which '
                         'needs the whole manifest, is off in the experiment)')
    manifest_pin = None
    if bedrock:
        from research.kalshi.frankie_boss.opening_book import _manifest_by_hash
        from research.kalshi.frankie_boss.block_source_scope import block_source_scope
        manifest_path, manifest = _manifest_by_hash(receipt['manifest_hash'])
        scope = block_source_scope(manifest, expected_manifest_hash=receipt['manifest_hash'])
        if (manifest.get('trading_day') != day
                or manifest.get('total_mbo_records') != receipt['record_count']
                or scope.genesis_hash() != completion['scope_hash']
                or [member.mbo_records for member in scope.members] != list(completion['member_counts'])):
            raise ValueError('native calculation manifest differs from the sealed day completion')
        manifest_pin = witness(manifest_path)
    output = safe_path(output_root) if resume else fresh(output_root, PARENT)
    if resume and (output.parent != PARENT or not output.is_dir() or (output / 'calculations-receipt.json').exists()):
        raise ValueError('resume requires this day\'s unfinished retained ROOT directory')
    PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700, exist_ok=resume)
    sync_directory(PARENT)
    rebinds = []
    def save_or_match(path, body):
        """The saved document when this checkout builds the same content (equal, or equal but for the checkout prefix
        of recorded file paths: content_rebinds); it stays the identity, never rewritten. Any other difference refuses
        (retained, never discarded). A fresh ROOT publishes the built document."""
        if resume and path.exists():
            saved = json.loads(path.read_bytes())
            moves = content_rebinds(saved, json.loads(json.dumps(body, sort_keys=True, allow_nan=False)))
            if moves is None:
                raise ValueError('retained ROOT source/pin differs: %s' % path)
            if moves:
                rebinds.append(dict(document=str(path), sha256=_sha256_file(path), moves=moves))
            return saved
        _save_new_complete(path, body)
        return body
    source = dict(trading_day=day, manifest_hash=receipt['manifest_hash'], container=container, completion=completion,
                  source_prefix_hash=receipt['source_prefix_hash'], record_count=receipt['record_count'])
    # the legacy (bedrock off) text below is part of an older saved plan's pinned calculation-pins.json bytes: kept
    # byte-identical so its retained ROOT resumes; every NEW request takes the first text (the native pass ON)
    rule = ('One complete day delivery for the experiment; existing native calculators and exact local evidence; '
            'compressed projections retained, giant bedrock rendering omitted. Source route only; consumer coverage separate.'
            if bedrock else 'One complete day delivery for the experiment; the complete registry; the bedrock groups '
            'are named by the pin but not derived (bedrock off).')
    save_or_match(output / 'calculation-pins.json', whole_day_pin_document(source, rule=rule))
    from frankie_box_boss_session import Session, FRAME_SECTIONS_SCHEMA, NATIVE_RECOVERY_SCHEMA
    binding = dict(schema='FRANKIE_EXPERIMENT_DAY_CALCULATION_SOURCE_V1', source=source, data_workers=data_workers,
                   frame_sections_schema=FRAME_SECTIONS_SCHEMA,
                   authorship=None, authorship_note='the experiment forecasts nothing through the full pipeline; no launch '
                   'authorship is needed', ingestion_receipt=receipt_pin, completion=witness(completion_path),
                   calculation_pins=witness(output / 'calculation-pins.json'), container=container, manifest=manifest,
                   record_count=receipt['record_count'], journal_count=receipt['journal_count'],
                   journal_hash=receipt['journal_hash'], day_role=day_role, partial_members=partial_members,
                   tail_members=tail_members, opening_book=opening_book, external=external)
    if shared_market_policy is not None:
        binding['shared_market_policy'] = timeline_binding()
    if bedrock:
        from frankie_box_native_emission import binding as emission_binding
        binding['native_calculation_policy'] = dict(schema=NATIVE_RECOVERY_SCHEMA,
            producer='existing_pinned_native_traversal', bedrock=True, source_manifest=manifest_pin,
            representation='exact_local_ledgers_and_existing_compressed_projections', digest_bedrock=False,
            emission=emission_binding())
    # on resume the SAVED binding stays the identity (Session reads source-binding.json; every stage identity and the
    # retained derivation compare against it), whatever checkout path this process built
    binding = save_or_match(output / 'source-binding.json', binding)
    if external['status'] == 'attached':
        save_or_match(output / 'external-computation.json', external_computation)
    if rebinds:
        # the move is recorded in the attempt (append-only, one record per resuming process): old/new checkout,
        # this commit, every moved path with its unchanged bytes and sha256; the saved documents are untouched
        records = output / 'checkout-rebinds'
        records.mkdir(mode=0o700, exist_ok=True)
        _save_new_complete(records / ('%d-%s.json' % (time.time_ns(), uuid.uuid4().hex[:8])), dict(
            schema=CHECKOUT_REBIND_SCHEMA, at=time.time(), commit=commit, current_checkout=str(REPOSITORY),
            saved_checkouts=sorted({m['saved_checkout'] for r in rebinds for m in r['moves']}), documents=rebinds,
            rule='the saved documents differ from this checkout\'s only in the checkout prefix of recorded file paths '
                 'whose bytes and sha256 are equal; the saved documents stay the identity'))
    session = Session(output, day, '00', None)
    session.request_sha256 = witness(output / 'source-binding.json')['sha256']
    session.phase('deriving', 'experiment ROOT: sealed day, legacy and native calculations; no giant bedrock digest'
                  if bedrock else 'experiment ROOT: the legacy pass on the sealed day; bedrock off')
    retained = session.work / 'derive.json'
    if resume and retained.is_file():
        # The existing legacy reader/render helpers recover the finished calculation stage without replaying it.
        from frankie_box_monday_calculations import load_retained_layers, write_retained_digest
        result = json.loads(retained.read_bytes())
        if result.get('source_binding') != binding or result.get('pin_identity', {}).get('sha256') != \
                witness(output / 'calculation-pins.json')['sha256']:
            raise ValueError('saved derivation belongs to another source/pin')
        if result.get('producers') != session._producer_witnesses(session._pin()):
            raise ValueError('saved derivation producers changed')
        if result.get('frame_sections_schema') != FRAME_SECTIONS_SCHEMA:
            raise ValueError('saved derivation has another frame projection; retained outputs preserved')
        if bedrock and (result.get('native_recovery_schema') != NATIVE_RECOVERY_SCHEMA
                        or not result.get('bedrock') or result['bedrock'].get('skipped')):
            raise ValueError('saved derivation lacks completed native calculations; retained outputs preserved')
        if bedrock:
            native = result['bedrock']
            if native.get('emission') != binding['native_calculation_policy']['emission']:
                raise ValueError('saved native emission provenance policy differs; retained outputs preserved')
            for item in [native['receipt'], native['result'], *native['ledgers'].values()]:
                if witness(Path(item['path'])) != {k: item[k] for k in ('path', 'bytes', 'sha256')}:
                    raise ValueError('saved native evidence differs: ' + item['path'])
        for item in result['layers'].values():
            if witness(Path(item['path'])) != {k: item[k] for k in ('path', 'bytes', 'sha256')}:
                raise ValueError('saved calculation layer differs: %s' % item['path'])
        _, _, _, prices, frames, structures, failures, layers, _ = load_retained_layers(session, allow_failures=True)
        if len(failures) != result['failure_count']:
            raise ValueError('saved failure spool differs from derivation')
        if digest:
            write_retained_digest(session, result, layers, prices, frames, structures, bedrock=False)
        session.note('resumed from the saved derivation; no legacy calculation replay')
        if hasattr(session, 'native_layer_records'):
            # the per-layer native records of the retained derivation (work/native-layer-records.json, bound to its
            # derive.json bytes; correction_consumer 2026-10-07): written when absent, nothing derived
            session.native_layer_records()
    else:
        result = session.derive(source=SimpleNamespace(container=container), bedrock=bedrock, digest=digest,
                                opening_adapter_state=opening_state, opening_book=opening_book,
                                recovery=True, save_requested=save_requested, retain_frame_sections=True,
                                digest_bedrock=False, bedrock_off_cause=bedrock_off_cause)
    # Greg, 2026-09-29: no data is dropped even when it is not all complete; a calculation that cannot use a record
    # skips over it, the day is not skipped. Producer failures stay in derive.json (and the failures spool) with their
    # record index and error, and are named in the receipt; the day's calculations go on to the next steps.
    failures = result['failure_count']
    calc = dict(schema='FRANKIE_EXPERIMENT_DAY_CALCULATIONS_V1', commit=commit, day=day, day_role=day_role,
                source_binding=witness(output / 'source-binding.json'),
                calculation_pins=witness(output / 'calculation-pins.json'),
                derivation=witness(session.work / 'derive.json'),
                digest=witness(session.work / 'derivation-digest-full.md') if digest else None,
                root_processes=result.get('root_processes'),
                native_calculation_policy=binding.get('native_calculation_policy'),
                frame_sections_schema=result.get('frame_sections_schema'), frame_sections=result.get('frame_sections'),
                not_run=[dict(process=k, reason='not selected by this source-bound ROOT configuration')
                         for k, v in (result.get('root_processes') or {}).items() if v == 'skipped'],
                failure_count=failures, opening_book=opening_book, external=external,
                external_computation=witness(output / 'external-computation.json')
                if external['status'] == 'attached' else None,
                failures_note=(None if not failures else 'records a producer could not use; each listed with its index '
                               'and error in derive.json / work/derived/.rows/failures.jsonl; every other record calculated'),
                model_calls=0, source_replays=0, source_writes=0,
                status='calculations_retained' if not failures else 'calculations_retained_with_failures')
    rebind_dir = output / 'checkout-rebinds'
    if rebind_dir.is_dir():
        # additive: the checkout moves recorded in this attempt (content_rebinds), each pinned
        calc['checkout_rebinds'] = [witness(path) for path in sorted(rebind_dir.glob('*.json'))]
    # How the ROOT used its lane (operator inspection only; never an input to a calculation): the native stage beside
    # the legacy pass (work/native-overlap.json, FRANKIE_ROOT_NATIVE_OVERLAP_V1: child pid, CPUs, seconds, outcome) or
    # the serial order when it is absent (a record of an earlier attempt stays pinned as written). No hash-pass count:
    # the stat-keyed cache does not measure one, and the receipt never reports an unmeasured number.
    overlap_path = session.work / 'native-overlap.json'
    calc['root_execution'] = dict(
        native_overlap=witness(overlap_path) if overlap_path.is_file() else dict(
            status='absent', reason='serial order (FRANKIE_ROOT_NATIVE_OVERLAP=off, native pass off, a resumed '
                                    'completed native stage, or a saved derivation reused)'),
        data_workers=data_workers,
        # additive (session 6, the ROOT AWS treatment audit): stated, not measured. How this ROOT's file hashes were
        # taken and that it moved no bytes over S3 itself (its inputs are the sealed ingest and the attached day file
        # read in place; the day file's fetch and the outputs' archive are other pieces with their own receipts).
        hash_basis='frankie_box_filehash.witness: one streamed sha256 per unchanged file per process (16 MiB reads), '
                   'keyed on path, device, inode, size, mtime_ns, ctime_ns; no stat-only skip across processes '
                   '(Greg\'s open call (c) undecided); the spool witnesses are the reference layers\' single scans',
        s3_transfer='none in this process: the sealed journal, the opening book and day-external.json are read in '
                    'place; the presigned day-external fetch (frankie_box_day_external, shared transport) and the '
                    'archive/offload of the outputs carry their own transport receipts')
    if shared_market_policy is not None:
        # Pin existing spools at publication; a reader must never invent a new
        # source identity by hashing whatever happens to be at an old pathname.
        calc['shared_market_policy'] = binding['shared_market_policy']
        calc['shared_market_sources'] = {}
        for name in ('frames', 'prices', 'structures'):
            spool = session.work / 'derived' / '.rows' / (name + '.jsonl')
            if spool.is_file():
                calc['shared_market_sources'][name] = dict(path=str(spool), **witness(spool))
            else:
                # Listed, never fabricated: the reader presents a thinner picture without this layer.
                calc['shared_market_sources'][name] = dict(status='absent', path=str(spool),
                                                           reason='the legacy pass published no ' + name + ' spool')
    _save_new_complete(output / 'calculations-receipt.json', calc)
    session.phase('derived')
    return calc


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--commit', required=True)
    p.add_argument('--ingestion-receipt', required=True)
    p.add_argument('--ingestion-receipt-sha256', required=True)
    p.add_argument('--day', required=True)
    p.add_argument('--day-role', required=True, choices=('discovery', 'confirmation'))
    p.add_argument('--output-root', required=True)
    p.add_argument('--data-workers', type=int, default=1)
    p.add_argument('--digest', choices=('on', 'off'), default='off', help='on for a classroom-arm day (Frankie reads it)')
    p.add_argument('--frozen-survivors')
    p.add_argument('--resume', action='store_true', help='reuse the source-bound unfinished ROOT directory')
    p.add_argument('--bedrock', choices=('on', 'off'), default='on',
                   help='the native pass (default on: Greg reversed the 2026-09-29 no-bedrock decision); off only for an '
                        'older saved legacy plan; does not establish downstream consumer coverage')
    p.add_argument('--shared-market-policy', choices=('FRANKIE_SHARED_MARKET_TIMELINE_V1',))
    p.add_argument('--bedrock-off-cause', choices=('caller_override', 'legacy_plan'),
                   help='why --bedrock off (recorded on derive.json); default: legacy_plan without the shared market '
                        'policy, caller_override with it; ignored with --bedrock on')
    a = p.parse_args()
    print(json.dumps(calculate_day(a.commit, a.ingestion_receipt, a.ingestion_receipt_sha256, a.day, a.day_role,
                                   a.output_root, a.data_workers, a.digest == 'on', a.frozen_survivors, a.resume,
                                   bedrock=a.bedrock == 'on', shared_market_policy=a.shared_market_policy,
                                   bedrock_off_cause=a.bedrock_off_cause), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
