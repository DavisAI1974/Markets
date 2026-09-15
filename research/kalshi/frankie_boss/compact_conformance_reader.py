"""Bounded dedicated CPU workers; full row proof, small conformance-only IPC.

This specialized reader is only for SourceConformanceDriver. General evidence
consumers must use CompactReader, which returns the complete original envelope.
Workers open their own read-only connections; raw book objects never cross IPC.
"""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import hashlib
import multiprocessing
from pathlib import Path
import sqlite3
import time

try:
    from .compact_journal import CompactReader, decode_block, verified_rows
    from .verified_journal_reader import GENESIS_HASH
except ImportError:
    from compact_journal import CompactReader, decode_block, verified_rows
    from verified_journal_reader import GENESIS_HASH


def project_entries(envelopes):
    projected = []
    for envelope in envelopes:
        payload = envelope['payload']
        if envelope['kind'] == 'INPUT':
            keys = ('cursor', 'scope_genesis_hash', 'record', 'source_member_index',
                    'session_id', 'raw_symbol', 'source_dbn_object')
        elif envelope['kind'] == 'APPLIED':
            keys = ('input_ordinal', 'raw_record', 'cursor', 'source_member_index',
                    'session_id', 'normalized', 'terminal_prefix_hash', 'record_count',
                    'group_count', 'receipt')
        else:
            raise ValueError('failed or unknown source evidence')
        projected.append(dict(ordinal=envelope['ordinal'], kind=envelope['kind'],
                              payload={key: payload[key] for key in keys}))
    return projected


def _verify_partition(path, start, previous):
    cpu = time.process_time()
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)
    try:
        row = db.execute('SELECT count,body,sha256 FROM blocks WHERE start=?', (start,)).fetchone()
    finally:
        db.close()
    if row is None or hashlib.sha256(row[1]).hexdigest() != row[2]:
        raise ValueError('block identity differs')
    rows = decode_block(row[1])
    if len(rows) != row[0]:
        raise ValueError('block coverage differs')
    # Partition verification uses the same canonical validator and explicit seam.
    try:
        from .compact_journal import verified_partition
    except ImportError:
        from compact_journal import verified_partition
    projected = project_entries(verified_partition(rows, start, previous))
    return projected, rows[-1][3], time.process_time()-cpu


class CompactConformanceReader(CompactReader):
    def __init__(self, path, *, expected_count, expected_head_hash, workers=1):
        if type(workers) is not int or not 1 <= workers <= 64:
            raise ValueError('explicit worker budget must be between 1 and 64')
        self.workers = workers
        self.worker_cpu_seconds = 0.0
        super().__init__(path, expected_count=expected_count, expected_head_hash=expected_head_hash)

    def entries(self):
        # To schedule independent blocks without rereading bodies, the predecessor
        # digest is included in the index and checked against each validated seam.
        index = iter(self.db.execute('SELECT start,count,previous,head FROM blocks ORDER BY start'))
        with ProcessPoolExecutor(max_workers=self.workers,
                mp_context=multiprocessing.get_context('spawn')) as pool:
            pending = deque()
            def submit():
                row = next(index, None)
                if row is None:
                    return False
                start, count, previous, head = row
                pending.append((row, pool.submit(_verify_partition, str(self.path), start, previous)))
                return True
            for _ in range(2*self.workers):
                if not submit():
                    break
            count, previous = 0, GENESIS_HASH
            while pending:
                (start, length, seam, head), future = pending.popleft()
                entries, actual_head, cpu = future.result()
                self.worker_cpu_seconds += cpu
                if (start != count or seam != previous or len(entries) != length
                        or actual_head != head):
                    raise ValueError('partition seam or coverage differs')
                yield from entries
                count, previous = count+length, head
                submit()
            if (count, previous) != (self.count, self.head_hash):
                raise ValueError('partition terminal identity differs')
        self._check_seal()
