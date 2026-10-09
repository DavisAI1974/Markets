"""Bounded dedicated CPU workers; full row proof, small conformance-only IPC.

This specialized reader serves source conformance and metadata-only source
binding/scheduling. General evidence and model consumers must use CompactReader,
which returns the complete original envelope.
Workers open their own read-only connections; raw book objects never cross IPC.
"""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path
import sqlite3
import time

try:
    from .c15_journal import SCHEMA
    from .compact_journal import CompactReader, _field, decode_block, verified_rows
    from .verified_journal_reader import GENESIS_HASH, decode_tagged
except ImportError:
    from c15_journal import SCHEMA
    from compact_journal import CompactReader, _field, decode_block, verified_rows
    from verified_journal_reader import GENESIS_HASH, decode_tagged


SOURCE_FIELDS = {
    'INPUT': ('cursor', 'scope_genesis_hash', 'record', 'source_member_index',
              'session_id', 'raw_symbol', 'source_dbn_object'),
    'APPLIED': ('input_ordinal', 'raw_record', 'cursor', 'source_member_index',
                'session_id', 'normalized', 'terminal_prefix_hash', 'record_count',
                'group_count', 'receipt'),
}


def project_entries(envelopes):
    projected = []
    for envelope in envelopes:
        payload = envelope['payload']
        if envelope['kind'] not in SOURCE_FIELDS:
            raise ValueError('failed or unknown source evidence')
        keys = SOURCE_FIELDS[envelope['kind']]
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
    projected = project_entries(verified_partition(rows, start, previous, payload_fields=SOURCE_FIELDS))
    return projected, rows[-1][3], time.process_time()-cpu


def _read_conformance_block(path, index):
    start, length, previous, head = index
    entries, actual_head, cpu = _verify_partition(path, start, previous)
    if len(entries) != length or actual_head != head:
        raise ValueError('conformance partition identity differs')
    return entries, cpu


def _decoded_partition(rows, start, previous, payload_fields):
    """compact_journal.verified_partition's decode with payload_fields (the same envelopes, built by the same steps)
    without re-proving each body: no canonical re-serialization and no second sha256 per row. Used only when the
    whole file's sha256 equals the seal's (proof: by seal claim); decode_block still checks each reconstructed body's
    digest, and the ordinal/kind/schema/previous-hash chain is still compared."""
    count = start
    for ordinal, kind, body, digest in rows:
        tree = json.loads(body)
        if type(tree) is not list or len(tree) != 2 or tree[0] != 'dict':
            raise ValueError('evidence envelope must be a tagged mapping')
        payload = _field(tree, 'payload')
        if type(payload) is not list or len(payload) != 2 or payload[0] != 'dict':
            raise ValueError('evidence payload must be a tagged mapping')
        fields = payload_fields[kind]
        projected = ['dict', [item for item in payload[1] if item[0] in fields]]
        decoded_tree = ['dict', [[key, projected if key == 'payload' else value] for key, value in tree[1]]]
        envelope = decode_tagged(decoded_tree)
        if (type(envelope) is not dict or ordinal != count or envelope.get('ordinal') != ordinal
                or envelope.get('schema') != SCHEMA or envelope.get('kind') != kind
                or envelope.get('previous_hash') != previous):
            raise ValueError('evidence journal continuity differs')
        previous, count = digest, count+1
        yield envelope


def _read_conformance_block_by_seal(path, index):
    """_read_conformance_block when the whole file's sha256 is the seal's: the block's own sha256 and the per-row
    re-proof are not recomputed (the sealed bytes were proven at the seal); the decoded entries are the same."""
    start, length, previous, head = index
    cpu = time.process_time()
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)
    try:
        row = db.execute('SELECT count,body FROM blocks WHERE start=?', (start,)).fetchone()
    finally:
        db.close()
    if row is None:
        raise ValueError('block identity differs')
    rows = decode_block(row[1])
    if len(rows) != row[0] or len(rows) != length or rows[-1][3] != head:
        raise ValueError('conformance partition identity differs')
    entries = project_entries(_decoded_partition(rows, start, previous, SOURCE_FIELDS))
    return entries, time.process_time()-cpu


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

    def __init__(self, path, *, expected_count, expected_head_hash, workers=1, emit=None, proof=True):
        """proof=False only when the caller holds the whole file's sha256 equal to the seal's (by a claim or a whole
        read): blocks are then decoded without the per-block sha256 and the per-row re-proof
        (_read_conformance_block_by_seal); the decoded entries are the same."""
        super().__init__(path, expected_count=expected_count, expected_head_hash=expected_head_hash,
                         workers=workers, emit=emit)
        self.workers = len(self.worker_cpus)
        self.proof = 'full row proof' if proof else 'by seal claim'
        if not proof:
            self.block_task = _read_conformance_block_by_seal
