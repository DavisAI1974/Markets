"""Frankie's read of the Monday 20211004 trading day through the digest stack (Greg, 2026-09-23: "Apply the digest
stack to Monday's read"; "just apply the reducers and absolutely nothing else").

The WHOLE trading day, no cutoff and no window: every source record of the recovered Monday journal (Sunday 18:00 ET
to Monday 17:00 ET, both members) goes through the same pinned producers the box session's derive stage runs (the V4
adapter from the producers checkout -> legacy control rows -> SecondBinner on ts_recv -> roll20; price; the F_LAST
book; describe_structure per F_LAST group), and the layers are written as the exact DIGEST_V6 document by
frankie_box_digest_document.write_digest (every table inverse-proven before publication). Read-only against the
sealed container and the recovery; writes one fresh root under /opt/frankie-box/work/monday-read/. No model call.
The bedrock tables need a calculation pin for the trading day; none exists, so they are not rendered (recorded).
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import time

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from frankie_box_prepare_trading_day import (  # noqa: E402
    ORIGINAL_CONTAINER, require_checkout, safe_path, save_new, sync_directory, witness)

RECOVERY = Path('/opt/frankie-box/work/sealed-recovery-35796793428')
PRODUCERS = Path('/opt/frankie-box/producers')
READ_PARENT = Path('/opt/frankie-box/work/monday-read')
TOKENIZER = REPOSITORY / ('research/kalshi/frankie_boss/sunday_20260915_package/C_Codex/2026-09-14/'
                          'if-you-mean-claude-code-a/work/verified-tokenizer/tokenizer.json')


def producer_module(relative, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, PRODUCERS / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def open_view(output):
    """The verified recovered Monday journal, read in place (the recovery is never written)."""
    blocks = REPOSITORY / 'research/kalshi/frankie_boss/blocks'
    descriptor = dict(schema='FRANKIE_VERIFIED_RECOVERED_INGESTION_V1',
        source_manifest=witness(blocks / 'BLOCK_20211004_SOURCE_MANIFEST.json'),
        recovery_receipt=witness(RECOVERY / 'recovery-receipt.json'),
        verification=witness(blocks / 'MONDAY_RECOVERY_VERIFIED_20260922.json'),
        checkpoint=witness(RECOVERY / 'builder-checkpoint.c15.json'), completion=witness(RECOVERY / 'completion.json'))
    save_new(output / 'recovered-ingestion.json', descriptor)
    pin = witness(output / 'recovered-ingestion.json')
    from research.kalshi.frankie_boss.recovered_ingestion import load_recovered_ingestion
    from research.kalshi.frankie_boss.completed_schedule_view import open_completed_schedule_view
    from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
    recovered = load_recovered_ingestion(pin)
    if recovered.container != ORIGINAL_CONTAINER:
        raise ValueError('recovered container differs from the canonical original')
    view = open_completed_schedule_view(recovered.scope, Path(recovered.container['path']),
        recovered.checkpoint_path, descriptor['checkpoint']['sha256'], recovered.receipt['checkpoint_state_hash'],
        recovered.completion, reader_factory=FrankieCompactReader, recovery_descriptor=pin)
    return view, recovered


def derive(view, work, progress=None):
    """The session's legacy derivation (frankie_box_boss_session.Session.derive), on every record of the day."""
    from research.kalshi.frankie_boss.context_session import journal_prefix
    from research.kalshi.frankie_raw_mbo_benchmark import native_roll20
    from research.kalshi.frankie_raw_mbo_benchmark.a_memory_member_first_recalculation_20260828 import (
        describe_structure, book_transition, BOOK_FIELDS)
    import frankie_box_bedrock as B
    V4MboAdapter = producer_module('research/ng_exhaustion_mbo_v4_state_adapter_20260820.py',
                                   'research.ng_exhaustion_mbo_v4_state_adapter_20260820').V4MboAdapter
    adapter = V4MboAdapter()
    binner = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
    rows = work / '.rows'
    prices, frames, structures, failures = [B.RowSpool(rows / (n + '.jsonl'))
                                           for n in ('prices', 'frames', 'structures', 'failures')]
    records = legacy_count = 0
    previous_book = None
    final = view.chain.next_cursor - 1
    source = journal_prefix(view, final)
    if progress is not None:
        source = progress.track(source, view.chain.next_cursor, 'root-legacy-records')
    for index, payload in enumerate(source):
        record = {k: v for k, v in payload['raw_record'].items() if not isinstance(v, (bytes, bytearray))}
        records += 1
        try:
            frame, legacy_rows = adapter.apply(record)
        except Exception as error:
            failures.append(dict(index=index, error=f'{type(error).__name__}: {error}'))
            continue
        for row in legacy_rows:
            legacy_count += 1
            try:
                binner.observe(row)
            except Exception as error:
                failures.append(dict(index=index, legacy=True, error=f'{type(error).__name__}: {error}'))
            if row.get('action') == native_roll20.TRADE_ACTION:
                prices.append(dict(ts_recv=row.get('ts_recv'), ts_event=row.get('ts_event'), price=row.get('price'), size=row.get('size'),
                                   bid_px_00=row.get(native_roll20.BID_TOUCH_FIELD), ask_px_00=row.get(native_roll20.ASK_TOUCH_FIELD)))
        if frame is not None:
            book = frame.get('book') or {}
            try:
                record_book = dict(ts_recv_ns=frame.get('ts_recv_ns'), ts_event_ns=frame.get('ts_event_ns'))
                record_book.update({k: book.get(k) for k in ('best_bid', 'best_ask', 'mid', 'depth_imbalance_n')})
                transition = book_transition(previous_book, book)
                record_book.update(transition['after'])  # exact producer-returned full-depth fields
                record_book['transition'] = transition['sign_signature']
                frames.append(record_book)
            except Exception as error:
                failures.append(dict(index=index, book=True, error=f'{type(error).__name__}: {error}'))
            previous_book = book
            try:
                structures.append(dict(ts_recv_ns=frame.get('ts_recv_ns'), ts_event_ns=frame.get('ts_event_ns'),
                                       **describe_structure(frame.get('raw_actions') or [])))
            except Exception as error:
                failures.append(dict(index=index, structure=True, error=f'{type(error).__name__}: {error}'))
    if progress is not None:
        progress.update('root-legacy-finalize')
    for spool in (prices, frames, structures, failures):
        spool.close()
    buys, sells, first = binner.series()
    roll = native_roll20.roll20(buys, sells)
    producer = {'legacy_price': 'research/ng_exhaustion_mbo_v4_state_adapter_20260820.py (legacy control row projection)',
                'legacy_native_signed_flow': 'research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py SecondBinner (clock ts_recv)',
                'legacy_per_second_roll20': 'research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py roll20 (window 20, clock ts_recv)',
                'legacy_book_imbalance': 'V4MboAdapter F_LAST book snapshot + a_memory_member_first_recalculation_20260828.book_values/book_transition',
                'legacy_structure_observables': 'a_memory_member_first_recalculation_20260828.describe_structure per F_LAST group'}
    # Flow and roll20 as exact files (each value once); the three row layers are their exact spools.
    flow = work / 'per-second.json'
    with flow.open('x') as handle:
        json.dump(dict(first_second=first, buy=buys, sell=sells, summary=binner.summary(),
                       roll20=[None if math.isnan(v) else v for v in roll], fields=list(BOOK_FIELDS)), handle)
    files = {'legacy_price': prices.path, 'legacy_native_signed_flow': flow, 'legacy_per_second_roll20': flow,
             'legacy_book_imbalance': frames.path, 'legacy_structure_observables': structures.path}
    derived = {'legacy_price': len(prices), 'legacy_native_signed_flow': binner.trades_seen,
               'legacy_per_second_roll20': any(not math.isnan(v) for v in roll),
               'legacy_book_imbalance': len(frames), 'legacy_structure_observables': len(structures)}
    layers = {name: dict(status='derived' if derived[name] else 'could_not', producer=producer[name],
                         reason=None if derived[name] else 'nothing in the trading day',
                         **witness(files[name])) for name in producer}
    counts = dict(input_records=records, legacy_rows=legacy_count, adapter_records=adapter.record_count,
                  f_last_groups=adapter.completed_event_group_count, failure_count=len(failures),
                  failures_path=str(failures.path))
    return layers, counts, (prices, frames, structures, roll, first, buys, sells)


def tokens(path):
    """Pinned Granite tokenizer count of the published document, in 1 MiB line-aligned slices (the reading parts are
    line-aligned too); the per-slice counts are written, their sum reported."""
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(TOKENIZER))
    slices, buffer = [], []
    size = 0
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            buffer.append(line)
            size += len(line)
            if size >= 1 << 20:
                slices.append(len(tokenizer.encode(''.join(buffer), add_special_tokens=False).ids))
                buffer, size = [], 0
    if buffer:
        slices.append(len(tokenizer.encode(''.join(buffer), add_special_tokens=False).ids))
    return slices


def read(commit, output_root):
    require_checkout(commit)
    output = safe_path(output_root)
    if output.parent != READ_PARENT or not re.fullmatch('[A-Za-z0-9_-]{1,96}', output.name) or output.exists():
        raise ValueError('fresh named root required under ' + str(READ_PARENT))
    READ_PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    sync_directory(READ_PARENT)
    from frankie_box_progress import Probe
    progress = Probe(output, commit, 'monday-read')
    progress.update('verifying-source')
    started = time.time()
    view, recovered = open_view(output)
    try:
        layers, counts, (prices, frames, structures, roll, first, buys, sells) = derive(view, output, progress)
        chain = dict(count=view.chain.next_cursor, head=view.chain.prefix_hash)
    finally:
        view.journal.close()
    kinds = dict(INPUT=chain['count'], APPLIED=chain['count'])
    receipt = dict(schema='FRANKIE_MONDAY_READ_RECEIPT_V1', trading_day='20211004', commit=commit,
                   rows=dict(path=str(ORIGINAL_CONTAINER['path']), count=2 * chain['count'], kinds=kinds, head=chain['head'],
                             head_is_request_source_hash=False),
                   pin_group='none: the trading day carries no calculation pin; bedrock tables not rendered',
                   layers=layers, **counts)
    import frankie_box_digest_document as D
    progress.update('root-digest')
    proof = D.write_digest(output / 'monday-read-digest.md', receipt, layers, prices, frames, structures,
                           roll, first, buys, sells, bedrock_entries={}, scratch_directory=output / 'digest-scratch')
    progress.update('granite-token-count')
    slices = tokens(output / 'monday-read-digest.md')
    result = dict(receipt, digest=dict(path=proof['path'], bytes=proof['bytes'], sha256=proof['sha256'],
                                       tables=proof['tables'], verified=proof['verified']),
                  tokens=dict(tokenizer=witness(TOKENIZER), slice_bytes=1 << 20, slices=slices, total=sum(slices)),
                  seconds=round(time.time() - started, 1), model_calls=0, source_writes=0)
    save_new(output / 'monday-read-receipt.json', result)
    progress.update('monday-read', state='complete', failed=counts['failure_count'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output-root', required=True)
    a = parser.parse_args()
    result = read(a.commit, a.output_root)
    result['layers'] = {k: dict(status=v['status'], bytes=v['bytes']) for k, v in result['layers'].items()}
    result['tokens'].pop('slices')
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
