"""Recover omitted MBO/book/FIFO payloads using the unchanged pinned adapter.

This reruns book reconstruction only. It neither retrains models nor substitutes
book-derived values for unavailable ROOT, DState, or model-output measurements.
"""
import dataclasses
import gzip
import hashlib
import io
import json
import pathlib
import sys
import time
import types
import urllib.request

import pyarrow.parquet as pq

M = 'DavisAI1974/Markets'
D = 'DavisAI1974/markets-data'
REPLAY_REV = 'ef89f83b6298983052f94080be64240d7abc0056'
TRADE_REV = '87dc338f2e74646eb731b3cd6f8968a5a0a653e2'
REPLAY_PATH = 'research/kalshi/adaptive_wavepacket_20261108/markets_bridge/verify_ng_book_replay.py'
TRADE_ROOT = 'tasks/family-research-20261022/combined-events/run-42571551209-1'
READS = []


def fetch(repo, revision, path):
    url = f'https://raw.githubusercontent.com/{repo}/{revision}/{path}'
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    READS.append(dict(repository=repo, revision=revision, path=path,
                      bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    return data


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=1, allow_nan=False)+'\n', encoding='utf-8')


class Shards:
    def __init__(self, root, name, limit):
        self.root, self.name, self.limit = root, name, limit
        self.rows = self.part = 0
        self.stream = None
        self.files = []

    def write(self, row):
        if self.rows % self.limit == 0:
            self.close()
            self.path = self.root / f'{self.name}-{self.part:04d}.jsonl.gz'
            self.stream = gzip.GzipFile(filename=str(self.path), mode='wb', compresslevel=3, mtime=0)
            self.part += 1
            self.part_rows = 0
        self.stream.write((json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n').encode())
        self.part_rows += 1
        self.rows += 1

    def close(self):
        if self.stream is None:
            return
        self.stream.close()
        with self.path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        size = self.path.stat().st_size
        if size >= 95_000_000:
            raise ValueError(f'Git shard exceeds bounded size: {self.path} ({size})')
        self.files.append(dict(path=self.path.name, rows=self.part_rows, bytes=size, sha256=digest))
        self.stream = None


def main(day, destination):
    out = pathlib.Path(destination)
    out.mkdir(parents=True, exist_ok=False)
    source = fetch(M, REPLAY_REV, REPLAY_PATH)
    replay = types.ModuleType('_original_replay')
    sys.modules[replay.__name__] = replay
    exec(compile(source, REPLAY_PATH, 'exec'), replay.__dict__)
    replay.git_blob = lambda pin, path: fetch(M, pin, path)
    # Keep the original tape manifest and byte checks. Only transport changes.
    replay.tape_blob = lambda name: fetch(M, replay.TAPE_PIN, replay.DATA_PATH+'/'+name)
    if day == '20231018':
        archive = out / 'original-book-comparison.jsonl.gz'
        archive.write_bytes(fetch(M, REPLAY_REV, str(replay.ARCHIVE)))
        replay.ARCHIVE = archive
    trade_path = f'{TRADE_ROOT}/events-{day}/a-trades.parquet'
    trades = pq.read_table(io.BytesIO(fetch(D, TRADE_REV, trade_path))).to_pylist()
    expected_counts = {'20231002':37670, '20231003':41410, '20231017':33451, '20231018':30739}
    assert len(trades) == expected_counts[day]
    messages = Shards(out, 'native-messages', 25000)
    snapshots = Shards(out, 'trade-book-fifo', 100)
    original_factory = replay.load_adapter
    next_trade = 0
    raw_count = 0
    samples = []

    def factory():
        adapter = original_factory()
        module = sys.modules[type(adapter).__module__]
        original_apply = module.InstrumentBook.apply

        def observe(book, msg):
            nonlocal next_trade, raw_count
            effect, frame, legacy = original_apply(book, msg)
            stream_ordinal = raw_count
            raw_count += 1
            order = book.orders.get(msg.order_id)
            messages.write(dict(source_stream_ordinal=stream_ordinal,
                                adapter_input_cursor=adapter.record_count,
                                original_message=msg.public_dict(),
                                original_effect=dataclasses.asdict(effect),
                                resting_order_after=None if order is None else dataclasses.asdict(order)))
            if msg.action == 'T' and next_trade < len(trades):
                target = trades[next_trade]
                if msg.ts_recv_ns >= int(trades[0]['receive_ns']):
                    observed = (msg.ts_recv_ns, msg.ts_event_ns, msg.sequence,
                                msg.order_id, msg.price_raw, msg.size, msg.side)
                    expected = tuple(target[k] for k in ('receive_ns','event_ns','sequence',
                                                        'order_id','price_raw','size','aggressor_side'))
                    assert observed == expected, (day, next_trade, observed, expected)
                    assert adapter.record_count == int(target['trade_input_cursor'])
                    full = book.book_snapshot(msg.ts_recv_ns, depth_levels=10,
                                              include_full_depth=True, include_order_ids=True)
                    queue_orders = 0
                    for side in ('bid','ask'):
                        levels = full[side+'_levels_full']
                        assert sum(level['size'] for level in levels) == full[side+'_depth_full']
                        for level in levels:
                            ahead = 0
                            for entry in level['fifo_queue']:
                                assert entry['volume_ahead'] == ahead
                                ahead += entry['size']
                                queue_orders += 1
                            assert ahead == level['size']
                            assert len(level['fifo_queue']) == level['order_count']
                    assert queue_orders == len(book.orders)
                    row = dict(day=day, trade_ordinal=next_trade,
                               source_stream_ordinal=stream_ordinal,
                               original_trade=target, known_by_ns=msg.ts_recv_ns,
                               phase='at_trade_input', book_full=full,
                               activity=book.rolling_activity(msg.ts_recv_ns),
                               integrity=dict(book.integrity),
                               fifo_priority_reconstructed=True,
                               native_priority_id_exposed=False)
                    snapshots.write(row)
                    if next_trade in (0, len(trades)//2, len(trades)-1):
                        samples.append(row)
                    next_trade += 1
                    if next_trade % 5000 == 0:
                        print(day, 'recovered trades', next_trade, flush=True)
            return effect, frame, legacy

        module.InstrumentBook.apply = observe
        return adapter

    replay.load_adapter = factory
    runner = replay.run_partial if day in ('20231002','20231017') else replay.run
    receipt = runner(day)
    assert next_trade == len(trades)
    messages.close()
    snapshots.close()
    dump(out/'REVIEW_SAMPLES.json', samples)
    dump(out/'SOURCE_PINS.json', READS)
    dump(out/'RECOVERY_RECEIPT.json', dict(
        schema='FRANKIE_MBO_BOOK_RECOVERY_V1', day=day,
        expected_trades=len(trades), recovered_trades=next_trade,
        raw_messages_including_opening_warmup=raw_count,
        completed_book_fifo_recovery=True, complete_all_layers=False,
        original_replay_receipt=receipt,
        snapshot_phase='at_trade_input; no later group-close values substituted',
        scope='original archived partial span' if day in ('20231002','20231017') else 'original archived full session',
        limits=['FIFO is reconstructed by the original adapter, not exchange-exposed native priority.',
                'This recovers MBO, book, FIFO and activity only; other missing calculations remain separate.']))
    dump(out/'MANIFEST.json', dict(files=messages.files+snapshots.files))
    print(day, 'BOOK_RECOVERY_VERIFIED', next_trade, 'trades', flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
