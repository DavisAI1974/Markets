"""The compact journal as the authoritative source for host verification.

The lawful host asks the raw 11.7 GB journal and its 4.4 GB lineage parent for two things only:
the digest of one row at a given ordinal (prefix anchors, rehydration boundaries, parent tails)
and a physical hash of the parent file. Both journals are exact-order encodings of the same rows,
and the compact container (compact_journal.py, 570 MB) already carries every row body, every row
digest, per-block SHA-256 pins, a previous/head chain across blocks and a seal (count, head) that
must equal the ingestion completion. So a compact container that is physically pinned (file sha256
from the host configuration) and logically pinned (seal == completion) answers the ordinal question
by decoding ONE block, verified on access, and the raw journals never need to be on the host.

No scientific value is computed here. Nothing is written. The prefix journals the model actually
reads are untouched: they are still opened by the same readers the lawful host uses.
"""
import bisect
import hashlib
import json
import sqlite3
from pathlib import Path

try:
    from research.kalshi.frankie_boss.compact_journal import FORMAT, decode_block, verified_partition
    from research.kalshi.frankie_boss.verified_journal_reader import GENESIS_HASH
except ImportError:
    from compact_journal import FORMAT, decode_block, verified_partition
    from verified_journal_reader import GENESIS_HASH

SCHEMA = 'FRANKIE_COMPACT_SOURCE_V1'
LINEAGE_SCHEMA = 'FRANKIE_COMPACT_SOURCE_LINEAGE_V1'
_HEX = frozenset('0123456789abcdef')


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecars(path):
    return [str(path) + suffix for suffix in ('-wal', '-shm', '-journal') if Path(str(path) + suffix).exists()]


def _hex64(value, name):
    if type(value) is not str or len(value) != 64 or not _HEX.issuperset(value):
        raise ValueError(f'{name} must be a sha256 hex digest')
    return value


class CompactSource:
    """A sealed compact container, pinned physically and logically, answering row digests by ordinal."""

    def __init__(self, path, *, expected_sha256, expected_count, expected_head_hash, expected_bytes=None):
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError('compact source container missing')
        if _sidecars(self.path):
            raise ValueError('closed compact source container required')
        if type(expected_count) is not int or expected_count < 1:
            raise ValueError('independently supplied compact count required')
        _hex64(expected_sha256, 'compact physical pin'); _hex64(expected_head_hash, 'compact head hash')
        self.bytes = self.path.stat().st_size
        if expected_bytes is not None and self.bytes != expected_bytes:
            raise ValueError('compact source size differs from its witness')
        self.sha256 = file_sha256(self.path)
        if self.sha256 != expected_sha256:
            raise ValueError('compact source physical pin differs')
        self.db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            if self.db.execute('SELECT format,count,head FROM seal').fetchall() != [(FORMAT, expected_count, expected_head_hash)]:
                raise ValueError('compact source seal differs from the completed ingestion')
            blocks = self.db.execute('SELECT start,count,sha256,previous,head FROM blocks ORDER BY start').fetchall()
            expected_start, previous = 0, GENESIS_HASH
            for start, count, digest, before, head in blocks:
                if (start != expected_start or type(count) is not int or count < 1 or before != previous
                        or len(digest) != 64 or len(head) != 64):
                    raise ValueError('compact source block table is not one unbroken chain')
                expected_start, previous = start + count, head
            if (expected_start, previous) != (expected_count, expected_head_hash):
                raise ValueError('compact source block table does not reach its seal')
        except BaseException:
            self.db.close()
            raise
        self.blocks = blocks
        self.starts = [block[0] for block in blocks]
        self.count, self.head_hash = expected_count, expected_head_hash
        self.decoded_blocks = 0
        table = json.dumps(blocks, separators=(',', ':')).encode()
        self.block_table_sha256 = hashlib.sha256(table).hexdigest()

    def _block(self, index):
        start, count, digest, previous, head = self.blocks[index]
        row = self.db.execute('SELECT body FROM blocks WHERE start=?', (start,)).fetchone()
        if row is None or hashlib.sha256(row[0]).hexdigest() != digest:
            raise ValueError('compact source block identity differs')
        rows = decode_block(row[0])
        if len(rows) != count or [r[0] for r in rows] != list(range(start, start + count)) or rows[-1][3] != head:
            raise ValueError('compact source block coverage differs')
        for _ in verified_partition(rows, start, previous):
            pass
        self.decoded_blocks += 1
        return rows

    def rows(self, first, last):
        """Verified (ordinal, kind, body, digest) rows for ordinals first..last inclusive."""
        if type(first) is not int or type(last) is not int or not 0 <= first <= last < self.count:
            raise ValueError('ordinal range outside the sealed compact source')
        index = bisect.bisect_right(self.starts, first) - 1
        out = []
        while index < len(self.blocks) and self.blocks[index][0] <= last:
            out.extend(r for r in self._block(index) if first <= r[0] <= last)
            index += 1
        if [r[0] for r in out] != list(range(first, last + 1)):
            raise ValueError('compact source rows do not cover the requested ordinals')
        return out

    def digest_at(self, ordinal):
        return self.rows(ordinal, ordinal)[0][3]

    def receipt(self):
        return dict(schema=SCHEMA, path=str(self.path.resolve()), sha256=self.sha256, bytes=self.bytes,
                    count=self.count, head_hash=self.head_hash, blocks=len(self.blocks),
                    block_table_sha256=self.block_table_sha256, format=FORMAT,
                    model_forward_performed=False)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _verified_json(witness):
    path = Path(witness['path'])
    if file_sha256(path) != witness['sha256'] or ('bytes' in witness and path.stat().st_size != witness['bytes']):
        raise ValueError('host file differs from independently supplied witness')
    return json.loads(path.read_bytes())


def verify_lineage_from_compact(lineage, ingestion, compact, *, final_source_path):
    """The lawful closed-lineage checks with the compact container standing in for the raw journals.

    Every check of run_actual_sunday.ActualHost.source_lineage is kept except the two that open a
    raw SQLite file: the parent's stored tail and the child's rehydration anchor are read from the
    compact container instead, which holds the same rows because every link rehydrated with
    existing_entries_rewritten == 0. The parent's PHYSICAL pin is verified when the file is present
    and reported ABSENT_NOT_VERIFIED when it is not; nothing on the host reads that file.
    Returns (source_origins, receipt).
    """
    final = Path(final_source_path).resolve()
    if (lineage.get('schema') != 'FRANKIE_CLOSED_SOURCE_LINEAGE_V1'
            or Path(lineage['final_source_path']).resolve() != final or not lineage['links']):
        raise ValueError('explicit closed source lineage required')
    child, seen, origins, links = final, set(), {}, []
    for index, link in enumerate(lineage['links']):
        witness = link['recovery_receipt']; recovery = _verified_json(witness); parent = link['closed_parent']
        path = Path(parent['path']).resolve()
        if (str(path) in seen or path == child or Path(recovery['recovered_path']).resolve() != child
                or Path(recovery['parent_path']).resolve() != path or recovery['existing_entries_rewritten'] != 0
                or any(parent[k] != recovery['parent'][k] for k in ('sha256', 'count', 'head_hash'))
                or (index == 0 and witness['sha256'] != ingestion['recovery_receipt_sha256'])):
            raise ValueError('closed lineage differs from actual recovery receipts')
        if type(parent['count']) is not int or not 0 < parent['count'] <= compact.count:
            raise ValueError('closed lineage parent lies outside the compact source')
        if compact.digest_at(parent['count'] - 1) != parent['head_hash']:
            raise ValueError('closed lineage parent tail differs from the compact source')
        if compact.digest_at(recovery['journal_count'] - 1) != recovery['journal_hash']:
            raise ValueError('child no longer contains its verified rehydration boundary')
        physical = 'ABSENT_NOT_VERIFIED'
        if path.is_file():
            if _sidecars(path):
                raise ValueError('lineage parent must be closed before verification')
            if file_sha256(path) != parent['sha256']:
                raise ValueError('retained parent source differs from verified recovery lineage')
            physical = 'VERIFIED'
        origins[str(path)] = parent['count'] // 2 * 2
        links.append(dict(parent_path=str(path), count=parent['count'], head_hash=parent['head_hash'],
                          parent_physical_pin=physical, recovery_receipt_sha256=witness['sha256']))
        seen.add(str(path)); child = path
    receipt = dict(schema=LINEAGE_SCHEMA, compact=compact.receipt(), final_source_path=str(final),
                   links=links, raw_journals_opened=0)
    return origins, receipt
