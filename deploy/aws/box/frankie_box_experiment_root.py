"""The experiment's ROOT for any ingested day (Greg, 2026-09-29: "we forgot root in the experiment"; the bedrock-off
switch). Spec: research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md, step 3.

The Monday ROOT (frankie_box_monday_calculations.py) starts from Monday's launch authorship and its recovered-ingestion
descriptor; neither exists for another day, and the experiment forecasts nothing through the full pipeline, so it needs
no authorship. This ROOT starts from the day's own sealed ingest (BOSS_BLOCK_INGESTION_RECEIPT_V1, written by
frankie_box_ingest_block.sh ACTION=ingest), pins it (receipt sha256 given by the caller; the journal's bytes and sha256
checked against the receipt), builds the SAME whole-day calculation pin (whole_day_pin_document, shared with the Monday
ROOT), and runs the SAME Session.derive with bedrock OFF: ROOT process 1 (the legacy pass: every INPUT record, the five
legacy layers and the row spools) always, process 4 (the Markdown digest) only when asked (classroom-arm days, where
Frankie reads it), processes 2 and 3 (the bedrock traversal and projection) never.
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
                  frozen_survivors=None, resume=False):
    requested = [False]
    previous_handler = signal.signal(signal.SIGTERM, lambda *_: requested.__setitem__(0, True))
    stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')
    def save_requested():
        return requested[0] or bool(stop_file and Path(stop_file).exists())
    try:
        result = _calculate_day(commit, receipt_path, receipt_sha256, day, day_role, output_root, data_workers,
                                digest, frozen_survivors, resume, save_requested=save_requested)
        if save_requested():
            from research.kalshi.frankie_boss.parallel_teacher import TeacherSaved
            raise TeacherSaved('ROOT completion published; resume uses the completed receipt')
        return result
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


def _calculate_day(commit, receipt_path, receipt_sha256, day, day_role, output_root, data_workers=1, digest=False,
                   frozen_survivors=None, resume=False, save_requested=None):
    require_checkout(commit)
    if day_role not in ('discovery', 'confirmation'):
        raise ValueError('day role discovery or confirmation required')
    if day_role == 'confirmation' and not (frozen_survivors and Path(frozen_survivors).is_file()):
        raise ValueError('a confirmation day stays untouched until the survivor list is frozen (give it)')
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
    if journal.stat().st_size != receipt['journal_bytes'] or _sha256_file(journal) != receipt['journal_sha256']:
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
    output = safe_path(output_root) if resume else fresh(output_root, PARENT)
    if resume and (output.parent != PARENT or not output.is_dir() or (output / 'calculations-receipt.json').exists()):
        raise ValueError('resume requires this day\'s unfinished retained ROOT directory')
    PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700, exist_ok=resume)
    sync_directory(PARENT)
    def save_or_match(path, body):
        if resume and path.exists():
            if json.loads(path.read_bytes()) != body:
                raise ValueError('retained ROOT source/pin differs: %s' % path)
        else:
            _save_new_complete(path, body)
    source = dict(trading_day=day, manifest_hash=receipt['manifest_hash'], container=container, completion=completion,
                  source_prefix_hash=receipt['source_prefix_hash'], record_count=receipt['record_count'])
    save_or_match(output / 'calculation-pins.json', whole_day_pin_document(
        source, rule='One complete day delivery for the experiment; the complete registry; the bedrock groups are named '
                     'by the pin but not derived (bedrock off).'))
    from frankie_box_boss_session import Session, FRAME_SECTIONS_SCHEMA
    binding = dict(schema='FRANKIE_EXPERIMENT_DAY_CALCULATION_SOURCE_V1', source=source, data_workers=data_workers,
                   frame_sections_schema=FRAME_SECTIONS_SCHEMA,
                   authorship=None, authorship_note='the experiment forecasts nothing through the full pipeline; no launch '
                   'authorship is needed', ingestion_receipt=receipt_pin, completion=witness(completion_path),
                   calculation_pins=witness(output / 'calculation-pins.json'), container=container, manifest=manifest,
                   record_count=receipt['record_count'], journal_count=receipt['journal_count'],
                   journal_hash=receipt['journal_hash'], day_role=day_role, partial_members=partial_members,
                   tail_members=tail_members, opening_book=opening_book, external=external)
    save_or_match(output / 'source-binding.json', binding)
    if external['status'] == 'attached':
        save_or_match(output / 'external-computation.json', external_computation)
    session = Session(output, day, '00', None)
    session.request_sha256 = witness(output / 'source-binding.json')['sha256']
    session.phase('deriving', 'experiment ROOT: the legacy pass on the sealed day; bedrock off')
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
        for item in result['layers'].values():
            if witness(Path(item['path'])) != {k: item[k] for k in ('path', 'bytes', 'sha256')}:
                raise ValueError('saved calculation layer differs: %s' % item['path'])
        _, _, _, prices, frames, structures, failures, layers, _ = load_retained_layers(session, allow_failures=True)
        if len(failures) != result['failure_count']:
            raise ValueError('saved failure spool differs from derivation')
        if digest:
            write_retained_digest(session, result, layers, prices, frames, structures, bedrock=False)
        session.note('resumed from the saved derivation; no legacy calculation replay')
    else:
        result = session.derive(source=SimpleNamespace(container=container), bedrock=False, digest=digest,
                                opening_adapter_state=opening_state, opening_book=opening_book,
                                recovery=True, save_requested=save_requested, retain_frame_sections=True)
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
                frame_sections_schema=result.get('frame_sections_schema'), frame_sections=result.get('frame_sections'),
                not_run=[dict(process=k, reason='switched off for the experiment (Greg, 2026-09-29)')
                         for k, v in (result.get('root_processes') or {}).items() if v == 'skipped'],
                failure_count=failures, opening_book=opening_book, external=external,
                external_computation=witness(output / 'external-computation.json')
                if external['status'] == 'attached' else None,
                failures_note=(None if not failures else 'records a producer could not use; each listed with its index '
                               'and error in derive.json / work/derived/.rows/failures.jsonl; every other record calculated'),
                model_calls=0, source_replays=0, source_writes=0,
                status='calculations_retained' if not failures else 'calculations_retained_with_failures')
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
    a = p.parse_args()
    print(json.dumps(calculate_day(a.commit, a.ingestion_receipt, a.ingestion_receipt_sha256, a.day, a.day_role,
                                   a.output_root, a.data_workers, a.digest == 'on', a.frozen_survivors, a.resume), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
