"""Stream the original teacher equations over the archived October 2 MBO scope."""

import argparse
from collections import Counter
from dataclasses import asdict, fields
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import time

import pyarrow.parquet as pq

from research.kalshi.frankie_boss import teacher_changes
from research.kalshi.frankie_boss.c15_normalizer_r3 import IdentityNormalizerR3
from research.kalshi.frankie_boss.c15_observer import observe_book, order_rank
from research.kalshi.frankie_boss.c15_teacher_r3 import CONTROL_COLUMNS, JournalTeacherR3, _paired_raw
from research.kalshi.frankie_boss.four_day_pins.recover_book_layers import (
    D, TRADE_REV, TRADE_ROOT, Shards, dump, fetch, READS,
)
from research.kalshi.frankie_boss.mbo_resume_state import export_adapter_state, restore_adapter_state
from research.kalshi.frankie_boss.parallel_teacher import _load_raw_state, _save_raw_state
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import InstrumentBook, NormalizedMbo, V4MboAdapter


DAY = '20231002'
REVISION = '7eebebadef89c4281cdb25c236ac39f5da814839'
SOURCE = f'tasks/family-research-20261022/frankie-four-day-pins/book-recovery-42617700678-1/{DAY}'
MANIFEST_SHA256 = '9af6f09cf333cd60250aadda29947b43165173c6ad82fc6434592f79207df9cb'
INSTRUMENT = 150611
MESSAGE_FIELDS = tuple(field.name for field in fields(NormalizedMbo))


def evidence(entries, samples, metrics, book, prefix, *, limit=None):
    offset = 0
    for entry in entries:
        if offset + entry['rows'] <= metrics['rows']:
            offset += entry['rows']
            continue
        data = fetch(D, REVISION, SOURCE + '/' + entry['path'])
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError(f"Input shard differs from pinned manifest: {entry['path']}")
        count = 0
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            for line in stream:
                ordinal = offset + count
                count += 1
                cursor = metrics['rows']
                if ordinal < cursor:
                    continue
                if limit is not None and cursor >= limit:
                    return
                row = json.loads(line)
                normalized = row['original_message']
                msg = NormalizedMbo(**{key: normalized[key] for key in MESSAGE_FIELDS})
                if (row['source_stream_ordinal'] != cursor or row['adapter_input_cursor'] != cursor
                        or msg.instrument_id != INSTRUMENT or msg.public_dict() != normalized):
                    raise ValueError(f'Message identity mismatch at cursor {cursor}')
                prior_order = book.orders.get(msg.order_id)
                before = None if prior_order is None else asdict(prior_order)
                rank_before = order_rank(book, prior_order)
                effect, frame, _ = book.apply(msg)
                current_order = book.orders.get(msg.order_id)
                after = None if current_order is None else asdict(current_order)
                if asdict(effect) != row['original_effect'] or after != row['resting_order_after']:
                    raise ValueError(f'Replay differs from the saved event at cursor {cursor}')
                closed = frame is not None
                if closed != msg.is_last:
                    raise ValueError(f'Group boundary mismatch at cursor {cursor}')
                if cursor in samples:
                    saved = samples[cursor]
                    full = book.book_snapshot(msg.ts_recv_ns, depth_levels=10,
                                              include_full_depth=True, include_order_ids=True)
                    if full != saved['book_full'] or msg.ts_recv_ns != saved['known_by_ns']:
                        raise ValueError(f'Full book/FIFO sample mismatch at cursor {cursor}')
                    metrics['book_samples'] += 1
                group = metrics['groups'] if closed else None
                metrics['groups'] += closed
                metrics['rows'] += 1
                prefix = hashlib.sha256(prefix + line).digest()
                # The teacher only uses receipt presence to identify a completed group.
                # This is a reconstructed input, with a new hash chain over the pinned
                # message bytes. It does not claim the original journal's receipt hashes.
                yield dict(cursor=cursor, source_member_index=0, session_id=DAY,
                           normalized=normalized, effect=asdict(effect),
                           order_before=before, order_after=after, rank_before=rank_before,
                           rank_after=order_rank(book, current_order),
                           receipt=None if group is None else {'reconstructed_group_ordinal': group},
                           observation=observe_book(book) if closed else None,
                           terminal_prefix_hash=prefix.hex())
        if count != entry['rows']:
            raise ValueError(f"Wrong row count in {entry['path']}: {count}")
        offset += count


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def restore_checkpoint(directory, expected_sha256, root, identity, messages):
    path = Path(directory) / 'CHECKPOINT.bin'
    if file_hash(path) != expected_sha256:
        raise ValueError('Checkpoint differs from the trusted artifact digest')
    saved = _load_raw_state(path)
    if saved['identity'] != identity:
        raise ValueError('Checkpoint belongs to a different source or calculator revision')
    for index, entry in enumerate(saved['files']):
        expected_name = f'second-set-{index:04d}.jsonl.gz'
        if entry['path'] != expected_name:
            raise ValueError('Checkpoint shard names are out of order')
        source = path.parent / expected_name
        if source.stat().st_size != entry['bytes'] or file_hash(source) != entry['sha256']:
            raise ValueError(f'Checkpoint output shard differs: {expected_name}')
        shutil.copyfile(source, root / expected_name)
    messages.files = saved['files']
    messages.rows = sum(entry['rows'] for entry in messages.files)
    messages.part = len(messages.files)
    cursor = saved['metrics']['rows']
    continuation = saved['continuation']
    adapter = restore_adapter_state(saved['adapter'])
    if (cursor != messages.rows or cursor != adapter.record_count
            or cursor != continuation['control']['processed']
            or cursor != continuation['raw']['next_cursor']):
        raise ValueError('Checkpoint book, outputs and calculation state have different cursors')
    return saved, adapter.books[INSTRUMENT]


def main(output, limit=None, max_seconds=None, resume_from=None, resume_sha256=None):
    start = time.monotonic()
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    manifest_bytes = fetch(D, REVISION, SOURCE + '/MANIFEST.json')
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Book recovery manifest differs from its pin')
    entries = [row for row in json.loads(manifest_bytes)['files'] if row['path'].startswith('native-messages-')]
    source_receipt = json.loads(fetch(D, REVISION, SOURCE + '/RECOVERY_RECEIPT.json'))
    original = source_receipt['original_replay_receipt']
    samples = {row['source_stream_ordinal']: row for row in
               json.loads(fetch(D, REVISION, SOURCE + '/REVIEW_SAMPLES.json'))}
    trades = pq.read_table(io.BytesIO(fetch(D, TRADE_REV, f'{TRADE_ROOT}/events-{DAY}/a-trades.parquet'))).to_pylist()
    trade_inputs = {row['trade_input_cursor']: row for row in trades}
    if len(trade_inputs) != len(trades) or len(trades) != original['trades']:
        raise ValueError('Trade inventory differs from the recovery receipt')

    teacher = JournalTeacherR3({INSTRUMENT: 1_000_000}, normalizer=IdentityNormalizerR3((INSTRUMENT,)))
    teacher_changes.install_binding()
    code = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    identity = dict(day=DAY, source=MANIFEST_SHA256, calculator_commit=code, teacher_binding=teacher.binding)
    states = [Counter() for _ in CONTROL_COLUMNS]
    metrics = Counter()
    book = InstrumentBook(INSTRUMENT)
    prefix = bytes.fromhex(MANIFEST_SHA256)
    messages = Shards(root, 'second-set', 25_000)
    continuation = {} if max_seconds is not None or resume_from is not None else None
    last_group = None
    if resume_from is not None:
        saved, book = restore_checkpoint(resume_from, resume_sha256, root, identity, messages)
        states, metrics, continuation = saved['states'], saved['metrics'], saved['continuation']
        prefix = bytes.fromhex(saved['prefix'])
        last_group = metrics['rows'] - 1
        READS.extend(saved['reads'])
    first_cursor = metrics['rows']
    replay_started = time.monotonic()
    stop_at = None if max_seconds is None else start + max_seconds
    checkpoint_prefix = None
    teacher_changes.apply()
    try:
        pending_trades = []
        for event, control, raw in _paired_raw(teacher.control, teacher.raw_teacher,
                                               evidence(entries, samples, metrics, book, prefix, limit=limit),
                                               as_of=original['last_ts_recv_ns'],
                                               source_manifest_hash=MANIFEST_SHA256,
                                               continuation=continuation):
            cursor = event['cursor']
            normalized = event['normalized']
            columns = control[:7] + raw['columns'] + control[13:]
            if len(columns) != len(CONTROL_COLUMNS):
                raise ValueError(f'Column count mismatch at cursor {cursor}')
            for counts, column in zip(states, columns):
                counts[column['state']] += 1
            group = event['receipt']
            if normalized['action'] == 'T':
                trade = trade_inputs[cursor]
                fields_to_check = {'event_ns': 'ts_event_ns', 'receive_ns': 'ts_recv_ns',
                                   'instrument_id': 'instrument_id', 'order_id': 'order_id',
                                   'price_raw': 'price_raw', 'size': 'size',
                                   'aggressor_side': 'side', 'sequence': 'sequence'}
                if any(trade[left] != normalized[right] for left, right in fields_to_check.items()):
                    raise ValueError(f'Trade fields differ at cursor {cursor}')
                pending_trades.append(trade)
                metrics['trades'] += 1
            if group is not None:
                for trade in pending_trades:
                    if (trade['group_close_input_cursor'] != cursor
                            or trade['available_ns'] != normalized['ts_recv_ns']):
                        raise ValueError(f'Trade group close mismatch at cursor {cursor}')
                metrics['closed_trades'] += len(pending_trades)
            messages.write(dict(input_cursor=cursor, event_ns=normalized['ts_event_ns'],
                                receive_ns=normalized['ts_recv_ns'], known_by_ns=normalized['ts_recv_ns'],
                                group_ordinal=None if group is None else group['reconstructed_group_ordinal'],
                                prior_group_cursor=last_group,
                                closed_trade_cursors=[trade['trade_input_cursor'] for trade in pending_trades]
                                if group is not None else [], columns=columns))
            if group is not None:
                last_group = cursor
                pending_trades.clear()
                if stop_at is not None and time.monotonic() >= stop_at and metrics['rows'] < original['records']:
                    checkpoint_prefix = event['terminal_prefix_hash']
                    break
            segment_rows = cursor + 1 - first_cursor
            if segment_rows == 2_000 or segment_rows % 25_000 == 0:
                elapsed = time.monotonic() - replay_started
                rate = segment_rows / elapsed
                eta = (original['records'] - cursor - 1) / rate
                print(f'{DAY}: {cursor + 1:,}/{original["records"]:,} messages, {rate:.1f}/s, '
                      f'estimated {eta / 3600:.2f}h remaining', flush=True)
    finally:
        teacher_changes.restore()
        messages.close()

    complete = limit is None and checkpoint_prefix is None
    if complete and (metrics['rows'], metrics['groups'], metrics['trades'],
                          metrics['closed_trades'], metrics['book_samples']) != (
                              original['records'], original['completed_groups'], len(trades),
                              len(trades), len(samples)):
        raise ValueError(f'Full archived scope did not reconcile: {metrics}')
    checkpoint_sha256 = None
    if checkpoint_prefix is not None:
        adapter = V4MboAdapter()
        adapter.books[INSTRUMENT] = book
        adapter.record_count = metrics['rows']
        adapter.completed_event_group_count = metrics['groups']
        checkpoint_path = root / 'CHECKPOINT.bin'
        _save_raw_state(checkpoint_path, dict(
            identity=identity, adapter=export_adapter_state(adapter), continuation=continuation,
            prefix=checkpoint_prefix, states=states, metrics=metrics, files=messages.files, reads=READS))
        checkpoint_sha256 = file_hash(checkpoint_path)
        print(f'Saved at message {metrics["rows"]:,}. Resume at cursor {metrics["rows"]}. '
              f'Checkpoint SHA-256 {checkpoint_sha256}', flush=True)
    dump(root / 'MANIFEST.json', dict(columns=CONTROL_COLUMNS, files=messages.files))
    dump(root / 'SOURCE_PINS.json', READS)
    dump(root / 'RECOVERY_RECEIPT.json', dict(
        schema='FRANKIE_SECOND_SET_REPLAY_V1', day=DAY, complete_second_set_replay=complete,
        checkpoint_sha256=checkpoint_sha256,
        scope=original['scope'], expected_trades=len(trades), recovered_trades=metrics['trades'],
        metrics=dict(metrics), state_counts=dict(zip(CONTROL_COLUMNS, states)),
        source_manifest_sha256=MANIFEST_SHA256, source_revision=REVISION,
        calculator_commit=code,
        teacher_changes_sha256=teacher_changes.CHANGES_SHA256, teacher_binding=teacher.binding,
        output_kind='recomputed raw components with original teacher equations',
        complete_all_layers=False, wall_seconds=round(time.monotonic() - start, 2)))
    print(f'{DAY}: {dict(metrics)}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--limit', type=int, help='Bounded replay check, ineligible for publication')
    parser.add_argument('--max-seconds', type=float, help='Save at the next closed group after this wall time')
    parser.add_argument('--resume-from', help='Local directory of a trusted checkpoint artifact')
    parser.add_argument('--resume-sha256', help='Checkpoint SHA-256 from the trusted runner log')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    if args.max_seconds is not None and args.max_seconds <= 0:
        parser.error('--max-seconds must be positive')
    if bool(args.resume_from) != bool(args.resume_sha256):
        parser.error('resume requires both the artifact directory and its trusted SHA-256')
    main(args.output, args.limit, args.max_seconds, args.resume_from, args.resume_sha256)
