"""Bounded dedicated CPU workers; full row proof, small conformance-only IPC.

This specialized reader serves source conformance and metadata-only source
binding/scheduling. General evidence and model consumers must use CompactReader,
which returns the complete original envelope.
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


def _read_conformance_block(path, index):
    start, length, previous, head = index
    entries, actual_head, cpu = _verify_partition(path, start, previous)
    if len(entries) != length or actual_head != head:
        raise ValueError('conformance partition identity differs')
    return entries, cpu


try:
    from .frankie_journal_reader import FrankieCompactReader
except ImportError:
    from frankie_journal_reader import FrankieCompactReader


class CompactConformanceReader(FrankieCompactReader):
    """The shared verified seams, affinity and progress; only IPC is projected.

    _verify_partition still validates every canonical body and logical hash before
    projecting. This class must never serve model context or general evidence.
    """
    block_task = staticmethod(_read_conformance_block)
    progress_phase = 'compact_conformance_read'

    def __init__(self, path, *, expected_count, expected_head_hash, workers=1, emit=None):
        super().__init__(path, expected_count=expected_count, expected_head_hash=expected_head_hash,
                         workers=workers, emit=emit)
        self.workers = len(self.worker_cpus)
