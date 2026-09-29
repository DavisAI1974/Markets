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
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frankie_box_prepare_trading_day import require_checkout, save_new, witness, safe_path  # noqa: E402
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


def calculate_day(commit, receipt_path, receipt_sha256, day, day_role, output_root, data_workers=1, digest=False,
                  frozen_survivors=None):
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
    manifest = dict(manifest_hash=receipt['manifest_hash'],
                    note='the day manifest by hash; its members are in the ingestion receipt (the bedrock traversal, which '
                         'needs the whole manifest, is off in the experiment)')
    output = fresh(output_root, PARENT)
    PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    sync_directory(PARENT)
    source = dict(trading_day=day, manifest_hash=receipt['manifest_hash'], container=container, completion=completion,
                  source_prefix_hash=receipt['source_prefix_hash'], record_count=receipt['record_count'])
    save_new(output / 'calculation-pins.json', whole_day_pin_document(
        source, rule='One complete day delivery for the experiment; the complete registry; the bedrock groups are named '
                     'by the pin but not derived (bedrock off).'))
    binding = dict(schema='FRANKIE_EXPERIMENT_DAY_CALCULATION_SOURCE_V1', source=source, data_workers=data_workers,
                   authorship=None, authorship_note='the experiment forecasts nothing through the full pipeline; no launch '
                   'authorship is needed', ingestion_receipt=receipt_pin, completion=witness(completion_path),
                   calculation_pins=witness(output / 'calculation-pins.json'), container=container, manifest=manifest,
                   record_count=receipt['record_count'], journal_count=receipt['journal_count'],
                   journal_hash=receipt['journal_hash'], day_role=day_role, partial_members=partial_members,
                   tail_members=tail_members, opening_book=opening_book)
    save_new(output / 'source-binding.json', binding)
    from frankie_box_boss_session import Session
    session = Session(output, day, '00', None)
    session.request_sha256 = witness(output / 'source-binding.json')['sha256']
    session.phase('deriving', 'experiment ROOT: the legacy pass on the sealed day; bedrock off')
    result = session.derive(source=SimpleNamespace(container=container), bedrock=False, digest=digest,
                            opening_adapter_state=opening_state, opening_book=opening_book)
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
                not_run=[dict(process=k, reason='switched off for the experiment (Greg, 2026-09-29)')
                         for k, v in (result.get('root_processes') or {}).items() if v == 'skipped'],
                failure_count=failures, opening_book=opening_book,
                failures_note=(None if not failures else 'records a producer could not use; each listed with its index '
                               'and error in derive.json / work/derived/.rows/failures.jsonl; every other record calculated'),
                model_calls=0, source_replays=0, source_writes=0,
                status='calculations_retained' if not failures else 'calculations_retained_with_failures')
    save_new(output / 'calculations-receipt.json', calc)
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
    a = p.parse_args()
    print(json.dumps(calculate_day(a.commit, a.ingestion_receipt, a.ingestion_receipt_sha256, a.day, a.day_role,
                                   a.output_root, a.data_workers, a.digest == 'on', a.frozen_survivors), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
