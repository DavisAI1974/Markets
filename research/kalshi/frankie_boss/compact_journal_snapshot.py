"""Reuse verified compact blocks for exact, physically bounded Sunday prefixes.

Whole blocks are copied unchanged; only a block crossing the causal cutoff is
decoded and re-encoded. Each resulting prefix is verified against the original
journal anchor with the full-evidence reader and original INPUT/APPLIED checks.
"""
import hashlib
import os
from pathlib import Path
import sqlite3
import uuid

try:
    from . import journal_prefix_snapshot as original
    from .compact_journal import CompactReader, CompactWriter, decode_block, encode_block
    from .frankie_journal_reader import FrankieCompactReader
    from .verified_journal_reader import GENESIS_HASH, VerifiedJournalReader
except ImportError:
    import journal_prefix_snapshot as original
    from compact_journal import CompactReader, CompactWriter, decode_block, encode_block
    from frankie_journal_reader import FrankieCompactReader
    from verified_journal_reader import GENESIS_HASH, VerifiedJournalReader

SCHEMA = 'C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1'


def snapshot_compact_prefix(source_path, destination_path, *, compact_path,
        compact_sha256, parent_count, parent_head_hash, through_cursor,
        parent_sha256=None, page_rows=64, workers=1, emit=None):
    if type(through_cursor) is not int or not 0 <= through_cursor < parent_count//2:
        raise ValueError('explicit causal cutoff required')
    source, destination, compact = map(lambda p: Path(p).resolve(),
                                      (source_path, destination_path, compact_path))
    if destination in (source, compact) or destination.exists():
        raise ValueError('fresh distinct prefix destination required')
    if original._sidecars(source) or original._sidecars(compact):
        raise ValueError('closed parent journals required')
    if original.file_sha256(compact) != compact_sha256:
        raise ValueError('compact physical pin differs')
    if parent_sha256 is not None and original.file_sha256(source) != parent_sha256:
        raise ValueError('original physical pin differs')
    before, compact_before = source.stat(), compact.stat()
    count = 2*(through_cursor+1)
    with VerifiedJournalReader(source, expected_count=parent_count,
                               expected_head_hash=parent_head_hash):
        pass
    db = sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)
    try:
        anchor = db.execute('SELECT digest FROM entries WHERE ordinal=?',(count-1,)).fetchone()
    finally:
        db.close()
    if anchor is None:
        raise ValueError('original causal anchor missing')
    expected_head = anchor[0]
    staging = destination.with_name(destination.name+'.partial-'+uuid.uuid4().hex)
    copied, head = 0, GENESIS_HASH
    try:
        with CompactReader(compact, expected_count=parent_count,
                           expected_head_hash=parent_head_hash) as parent:
            with CompactWriter(staging) as writer:
                for start, length, blob, digest, previous, terminal in parent.db.execute(
                        'SELECT start,count,body,sha256,previous,head FROM blocks WHERE start<? ORDER BY start',
                        (count,)):
                    if start != copied or previous != head or hashlib.sha256(blob).hexdigest() != digest:
                        raise ValueError('compact prefix block seam differs')
                    if start+length > count:
                        rows = decode_block(blob)[:count-start]
                        blob, length, terminal = encode_block(rows), len(rows), rows[-1][3]
                        digest = hashlib.sha256(blob).hexdigest()
                    with writer.db:
                        writer.db.execute('INSERT INTO blocks VALUES (?,?,?,?,?,?)',
                                          (start,length,blob,digest,previous,terminal))
                    copied, head = copied+length, terminal
                writer.count, writer.head_hash = copied, head
                writer.seal(expected_count=count, expected_head_hash=expected_head)
            parent._check_seal()
        with FrankieCompactReader(staging, expected_count=count,
                expected_head_hash=expected_head, workers=workers, emit=emit) as reader:
            summary = original._verify_pairs(reader.entries(), through_cursor)
        after, compact_after = source.stat(), compact.stat()
        if ((before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns)
                or (compact_before.st_size,compact_before.st_mtime_ns) !=
                   (compact_after.st_size,compact_after.st_mtime_ns)
                or original._sidecars(source) or original._sidecars(compact)):
            raise ValueError('parent changed during compact prefix creation')
        if destination.exists():
            raise ValueError('prefix destination appeared during creation')
        os.rename(staging, destination)
    except BaseException as exc:
        exc.add_note('partial compact prefix retained: '+str(staging))
        raise
    return dict(schema=SCHEMA, evidence_class=original.EVIDENCE_CLASS,
        original_journal=str(source), snapshot_journal=str(destination),
        parent=dict(count=parent_count,head_hash=parent_head_hash,sha256=parent_sha256),
        compact_parent=dict(path=str(compact),sha256=compact_sha256,
                            bytes=compact_before.st_size),
        through_cursor=through_cursor, records_in_prefix=through_cursor+1,
        journal_count=count,journal_head_hash=expected_head,
        snapshot_sha256=original.file_sha256(destination),**summary,
        provenance=dict(method='EXACT_COMPACT_BLOCK_REUSE',workers=workers,
                        verified_by='frankie_journal_reader.FrankieCompactReader'),
        full_source_complete=False,model_forward_performed=False)
