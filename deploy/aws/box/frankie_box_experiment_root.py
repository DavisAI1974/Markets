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


def _pinned(path):
    """A receipt pin {path, bytes, sha256} of a file this ROOT wrote or read (session 6, Greg: "we only do 1 pass"):
    the same refusal as frankie_box_prepare_trading_day.witness (safe_path: an absolute, symlink-free regular path), the
    sha256 from frankie_box_filehash's per-process cache, which the durable writer fills from its WRITE stream and the
    reference layers fill from their one spool scan, so derive.json, the layer files and the three shared spools are not
    read again at the receipt (before: a full uncached read of each, the frames spool among them, at every ROOT's end)."""
    path = safe_path(path)
    import frankie_box_filehash
    return dict(path=str(path), **frankie_box_filehash.witness(path))


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(64 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def write_claims_from_derivation(root_dir, *, force=False):
    """<root>/work/file-claims.jsonl (FRANKIE_FILE_CLAIM_V2 rows) for a ROOT reused or resumed on this code whose seal
    wrote no claims (a2's c9bf631 seal): one row per layer file, INPUT spool, reference-layer spool and native ledger /
    result / receipt, from the sha256 and bytes the ROOT itself recorded at its seal (derive.json) plus a fresh stat
    identity and one 64 KiB tail read; never a full read. The parent's rule (Greg's call (c) made exact: claim + stat +
    tail, not stat alone): a consumer (the classroom's brain publication, the data export, this file's resume checks)
    takes a row only while (dev, ino, size, mtime_ns) and the last-64-KiB sha256 still match. Written only when the
    file is absent (force rewrites). Returns a note dict for the receipt; never raises. Callable at the queue's root
    boundary for a REUSED ROOT (Run.root's reused branch is fenced): write_claims_from_derivation(<root>).
    Session 9 (Greg: "fix spool before it starts"; a2's file-claims.jsonl holds 57 V1 rows from an older seal, the
    native ledgers and the layers, NO row for any of the five legacy spools, so the resume counted the 496.7 GB frames
    spool whole): when the file EXISTS, the rows already there are never touched (byte for byte) and a row is ADDED
    for every artifact below that has none yet (the five legacy spools among them, with their sealed count), appended
    atomically; the note says how many rows were added and for which paths (status stays 'present'). The absent-file
    behaviour is unchanged."""
    root = Path(root_dir)
    work, note = root / 'work', dict(schema='FRANKIE_FILE_CLAIM_V2', path=str(root / 'work' / 'file-claims.jsonl'))
    existing, present_rows = None, 0
    try:
        from research.kalshi.frankie_boss.operations.ingest_block_sources import (file_claim, write_file_claims,
                                                                                   FILE_CLAIMS_NAME,
                                                                                   _write_claims_atomic)
        target = work / FILE_CLAIMS_NAME
        note['path'] = str(target)
        if target.is_file() and not force:
            from frankie_box_boss_session import _load_file_claims
            present_rows = sum(1 for _ in target.open('rb'))
            existing = _load_file_claims(work)             # {resolved path: row}; a row there is never rewritten
        result = json.loads((work / 'derive.json').read_bytes())
        receipt_path = root / 'calculations-receipt.json'
        commit = (json.loads(receipt_path.read_bytes()).get('commit') if receipt_path.is_file() else None) \
            or result.get('commit') or 'an earlier checkout'
        by = '%s: receipt/derive.json sha256 (sealed on %s) + stat + tail at %s' % (
            'root resume (row added beside the existing claims)' if existing is not None else 'root reuse',
            commit, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        items = []
        # ROOT-digest role, 2026-10-08 (the live trace on 6076950: 57 rows, none for the 496.7 GB frames spool, so the
        # legacy-stage reuse counted it whole): the five legacy spools from work/legacy-stage.json's artifacts (the
        # bytes + sha256 the seal measured whole) FIRST, each with its sealed count: the artifact's own (this code's
        # seals) or, for an older seal, the one the ROOT's own records hold (_sealed_spool_counts: input_records,
        # failure_count, the layer heads' `count`); the row then carries count + count_basis and a reuse that takes
        # the claim reopens the spool from the count and reads nothing of it
        stage = work / 'legacy-stage.json'
        if stage.is_file():
            from frankie_box_boss_session import _sealed_spool_counts
            saved = json.loads(stage.read_bytes())
            counts = _sealed_spool_counts(saved.get('receipt') or result, work / 'derived')
            for artifact in saved.get('artifacts') or []:
                if not str(artifact.get('path', '')).endswith('.jsonl'):
                    continue
                item = dict(artifact, kind='spool')
                if not isinstance(item.get('count'), int):
                    found = counts.get(str(Path(artifact['path']).resolve()))
                    if found is not None:
                        item.update(count=found['count'], count_basis=found['basis'])
                    else:
                        item.pop('count', None)
                elif not item.get('count_basis'):
                    item['count_basis'] = 'the seal\'s own count of the closed spool (legacy-stage.json)'
                items.append(item)
        for entry in (result.get('layers') or {}).values():
            items.append(entry)
            for spool in (entry.get('spools') or {}).values():        # a reference layer's spools (frames, groups)
                items.append(dict(spool, kind='spool', count_basis='the sealed reference layer\'s spool record')
                             if isinstance(spool.get('count'), int) else spool)
        record_spool = (result.get('rows') or {}).get('record_spool')
        if record_spool:
            items.append(dict(record_spool, kind='spool', count=result['input_records'],
                              count_basis='the sealed receipt\'s input_records')
                         if isinstance(result.get('input_records'), int) else record_spool)
        native = result.get('bedrock') or {}
        items.extend(v for v in (native.get('ledgers') or {}).values())
        for key in ('result', 'receipt'):
            if isinstance(native.get(key), dict):
                items.append(native[key])
        rows, skipped, seen = [], [], set()
        for item in items:
            try:
                path = str(Path(item['path']).resolve())
                if path in seen:
                    continue
                seen.add(path)
                if existing is not None and path in existing:
                    continue                                          # session 9: the row already there stays as it is
                row = file_claim(item['path'], int(item['bytes']), item['sha256'], by)
                if item.get('kind') == 'spool' and isinstance(item.get('count'), int):
                    row['count'] = item['count']                      # additive: the spool's sealed line count
                    row['count_basis'] = item.get('count_basis') or 'the sealed record'
                rows.append(row)
            except (OSError, ValueError, KeyError, TypeError) as error:
                skipped.append(dict(path=item.get('path') if isinstance(item, dict) else None,
                                    reason='%s: %s' % (type(error).__name__, error)))
        if existing is not None:
            # session 9: the existing lines byte for byte, the new rows after them, one atomic rewrite
            out = dict(note, status='present', rows=present_rows + len(rows), added=len(rows),
                       added_paths=[row['path'] for row in rows], claimed_by=by)
            if rows:
                text = target.read_text(encoding='utf-8')
                if text and not text.endswith('\n'):
                    text += '\n'
                _write_claims_atomic(target, (text + ''.join(json.dumps(row, sort_keys=True) + '\n'
                                                             for row in rows)).encode())
            if skipped:
                out['skipped'] = skipped
            return out
        written = write_file_claims(work, rows)
        out = dict(note, status=written.get('status'), rows=len(rows), claimed_by=by)
        if written.get('reason'):
            out['reason'] = written['reason']
        if skipped:
            out['skipped'] = skipped
        return out
    except Exception as error:  # noqa: BLE001 - a claim is a hint for later stages, never the ROOT's outcome
        if existing is not None:                                      # the file is there, its rows untouched
            return dict(note, status='present', rows=present_rows, added=0,
                        reason='no row added: %s: %s' % (type(error).__name__, error))
        return dict(note, status='not_written', reason='%s: %s' % (type(error).__name__, error))


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
    retained_checks = claims_note = spool_checks = None
    if resume and retained.is_file():
        # The existing legacy reader/render helpers recover the finished calculation stage without replaying it.
        from frankie_box_monday_calculations import load_retained_layers, write_retained_digest
        from frankie_box_boss_session import (_artifact_check, _load_file_claims, _reuse_check_mode,
                                              LEGACY_REUSE_CHECK_SETTING, _legacy_spool_artifact,
                                              _reopen_counted_spool, _sealed_spool_counts)
        import frankie_box_bedrock as B
        result = json.loads(retained.read_bytes())
        # session 6, second pass (the relaunch role, live on a2): the native evidence (193.7 GB) and every layer (the
        # 472 GB inline legacy_book_imbalance.json) were read whole here through the uncached witness on every resume,
        # then the layers again inside load_retained_layers. Now: the claims file is written from the ROOT's own sealed
        # sha256/bytes when absent (write_claims_from_derivation), every artifact is taken by its claim while stat and
        # the last 64 KiB hold (else read whole once through the per-process cache; FRANKIE_ROOT_LEGACY_REUSE_CHECK=full
        # restores the reads), the witnesses handed to load_retained_layers; recorded on the receipt.
        claims_note = write_claims_from_derivation(output)
        claims, mode = _load_file_claims(session.work), _reuse_check_mode(LEGACY_REUSE_CHECK_SETTING)
        retained_checks, witnessed = [], {}

        def evidence(item, what):
            path = safe_path(item['path'])                     # the same refusal as the witness before (no symlink)
            seen, basis = _artifact_check(dict(item, path=str(path)), claims, mode, claims_dir=session.work)
            if dict(seen, path=str(path)) != {k: item[k] for k in ('path', 'bytes', 'sha256')}:
                raise ValueError('saved %s differs: %s' % (what, item['path']))
            retained_checks.append(dict(path=str(path), bytes=item['bytes'], basis=basis))
            witnessed[str(path.resolve())] = dict(path=str(path), bytes=item['bytes'], sha256=item['sha256'])
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
                evidence(item, 'native evidence')
        for item in result['layers'].values():
            evidence(item, 'calculation layer')
        # Session 9 (Greg: "fix spool before it starts"): before, load_retained_layers was called without spools=, so
        # each of the five legacy spools was reopened by RowSpool.reopen, which counts EVERY line: a whole read of the
        # 496.7 GB frames spool (~63 min at the box's 131 MB/s) on every resume. Now, as the legacy-stage reuse inside
        # Session.derive already does: each spool artifact sealed in work/legacy-stage.json takes its count from the
        # seal, else its claim row (write_claims_from_derivation above added the rows), else the sealed receipt / layer
        # heads (_sealed_spool_counts), and its witness from the claim while stat + the last 64 KiB hold
        # (_legacy_spool_artifact); the spool is then reopened from the count, first and last lines only
        # (_reopen_counted_spool) and handed to load_retained_layers as spools=. A spool with no count or no holding
        # claim is read whole ONCE there (sha256 + count in one pass, a sealed count it disagrees with refuses); a
        # spool with no sealed artifact at all stays on RowSpool.reopen's whole count. Each case is named on the
        # receipt (spool_reopen), never silent.
        spool_checks, reopened = [], {}
        rows_dir = session.work / 'derived' / '.rows'
        stage = session.work / 'legacy-stage.json'
        saved_stage = json.loads(stage.read_bytes()) if stage.is_file() else {}
        sealed_counts = _sealed_spool_counts(saved_stage.get('receipt') or result, session.work / 'derived')
        for item in saved_stage.get('artifacts') or []:
            if not (str(item.get('path', '')).endswith('.jsonl')
                    or (item.get('kind') == 'spool' and isinstance(item.get('count'), int))):
                continue
            path = Path(item['path'])
            seen, count, how = _legacy_spool_artifact(item, claims, mode, sealed_counts, claims_dir=session.work)
            if seen != {k: item[k] for k in ('bytes', 'sha256')}:
                raise ValueError('retained legacy spool changed: ' + item['path'])
            reopened[str(path.resolve())] = _reopen_counted_spool(B.RowSpool, path, count)
            spool_checks.append(dict(path=str(path), bytes=item['bytes'], count=count, basis=how,
                                     reopened_from='the count: first and last lines read, no other line'))
        for path in [*rows_dir.glob('input-*.jsonl')] + [rows_dir / (n + '.jsonl')
                                                         for n in ('prices', 'frames', 'structures', 'failures')]:
            if str(path.resolve()) not in reopened:
                spool_checks.append(dict(path=str(path), bytes=path.stat().st_size if path.is_file() else None,
                                         count=None, basis='read whole: RowSpool.reopen counts every line (no sealed '
                                         'legacy-stage.json artifact names this spool)',
                                         reopened_from='RowSpool.reopen in load_retained_layers (every line read)'))
        _, _, _, prices, frames, structures, failures, layers, _ = load_retained_layers(
            session, allow_failures=True, spools=reopened, layer_witnesses=witnessed)
        session.note('retained evidence: %d artifacts, %d by their claim, %d read whole; %d spools, %d reopened from '
                     'a sealed count and a holding claim, %d read whole' % (
            len(retained_checks), sum(c['basis'].startswith('the saved claim') for c in retained_checks),
            sum(c['basis'].startswith('read whole') for c in retained_checks), len(spool_checks),
            sum('the saved claim' in c['basis'] for c in spool_checks),
            sum('the saved claim' not in c['basis'] for c in spool_checks)))
        if len(failures) != result['failure_count']:
            raise ValueError('saved failure spool differs from derivation')
        if digest:
            write_retained_digest(session, result, layers, prices, frames, structures, bedrock=False)
        elif (result.get('root_processes') or {}).get('digest') == 'run' \
                and not (session.work / 'derivation-digest-full.md').is_file():
            # session 6: the saved derive.json was written before an interrupted digest (it says 'run'); this ROOT runs
            # with DIGEST=off and no digest file exists, so the receipt below says 'skipped' (derive.json is not rewritten)
            result = dict(result, root_processes=dict(result['root_processes'], digest='skipped'))
            session.note('resumed with DIGEST=off: the saved derivation\'s digest never completed; recorded as skipped')
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
                source_binding=_pinned(output / 'source-binding.json'),
                calculation_pins=_pinned(output / 'calculation-pins.json'),
                derivation=_pinned(session.work / 'derive.json'),
                digest=_pinned(session.work / 'derivation-digest-full.md') if digest else None,
                root_processes=result.get('root_processes'),
                native_calculation_policy=binding.get('native_calculation_policy'),
                frame_sections_schema=result.get('frame_sections_schema'), frame_sections=result.get('frame_sections'),
                not_run=[dict(process=k, reason='not selected by this source-bound ROOT configuration')
                         for k, v in (result.get('root_processes') or {}).items() if v == 'skipped'],
                failure_count=failures, opening_book=opening_book, external=external,
                external_computation=_pinned(output / 'external-computation.json')
                if external['status'] == 'attached' else None,
                # session 6, additive: the resume's evidence checks (claim or read whole) and the claims file note
                retained_evidence_check=(dict(schema='FRANKIE_LEGACY_REUSE_CHECK_V1', artifacts=retained_checks)
                                         if retained_checks is not None else None),
                # session 9, additive: what each of the five legacy spools was reopened from on the resume (a sealed
                # count + a holding claim: first and last lines only; else the one whole pass that counted it)
                spool_reopen=spool_checks,
                file_claims=claims_note if claims_note is not None else result.get('file_claims'),
                failures_note=(None if not failures else 'records a producer could not use; each listed with its index '
                               'and error in derive.json / work/derived/.rows/failures.jsonl; every other record calculated'),
                model_calls=0, source_replays=0, source_writes=0,
                status='calculations_retained' if not failures else 'calculations_retained_with_failures')
    rebind_dir = output / 'checkout-rebinds'
    if rebind_dir.is_dir():
        # additive: the checkout moves recorded in this attempt (content_rebinds), each pinned
        calc['checkout_rebinds'] = [_pinned(path) for path in sorted(rebind_dir.glob('*.json'))]
    # How the ROOT used its lane (operator inspection only; never an input to a calculation): the native stage beside
    # the legacy pass (work/native-overlap.json, FRANKIE_ROOT_NATIVE_OVERLAP_V1: child pid, CPUs, seconds, outcome) or
    # the serial order when it is absent (a record of an earlier attempt stays pinned as written). No hash-pass count:
    # the stat-keyed cache does not measure one, and the receipt never reports an unmeasured number.
    overlap_path = session.work / 'native-overlap.json'
    calc['root_execution'] = dict(
        native_overlap=_pinned(overlap_path) if overlap_path.is_file() else dict(
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
                calc['shared_market_sources'][name] = _pinned(spool)    # (was dict(path=..., **witness()): a duplicate 'path' keyword)
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
