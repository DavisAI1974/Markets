"""CompactSource answers ordinal digests from a pinned, sealed container and refuses every tamper.

Built on a small synthetic journal: raw journal -> CompactWriter (tiny blocks so several exist) ->
CompactSource. Positive: every ordinal's digest and row equals the raw journal's. Negative: wrong
seal, wrong physical pin, wrong size, tampered block body (with and without a matching sha256
column), and a broken block table. Lineage: the lawful link checks pass against the compact rows
with the parent file absent and present, and fail on a wrong tail, a rewritten child or a
first-link witness that does not match the ingestion receipt.
"""
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from test_single_pass_finalization import fixture
from compact_journal import CompactWriter
from compact_source import CompactSource, verify_lineage_from_compact


def _write(path, value):
    raw = json.dumps(value, separators=(',', ':')).encode()
    Path(path).write_bytes(raw)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


class CompactSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw, _, _, _, _ = fixture(self.temp.name, 9)
        with sqlite3.connect(self.raw) as db:
            self.rows = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
        db.close()
        self.count, self.head = len(self.rows), self.rows[-1][3]
        self.compact = Path(self.temp.name) / 'journal.compact.sqlite'
        with CompactWriter(self.compact, block_bytes=3000) as writer:
            for row in self.rows:
                writer.add(row)
            writer.seal(expected_count=self.count, expected_head_hash=self.head)
        self.sha = hashlib.sha256(self.compact.read_bytes()).hexdigest()

    def open(self, path=None, **overrides):
        args = dict(expected_sha256=self.sha, expected_count=self.count, expected_head_hash=self.head)
        args.update(overrides)
        return CompactSource(path or self.compact, **args)

    def test_every_ordinal_matches_raw_and_blocks_are_several(self):
        with self.open() as source:
            self.assertGreater(len(source.blocks), 2)
            for ordinal, kind, body, digest in self.rows:
                self.assertEqual(source.digest_at(ordinal), digest)
            self.assertEqual(source.rows(3, self.count - 2), self.rows[3:self.count - 1])
            receipt = source.receipt()
            self.assertEqual((receipt['count'], receipt['head_hash'], receipt['sha256']), (self.count, self.head, self.sha))
            with self.assertRaises(ValueError):
                source.digest_at(self.count)
        self.assertEqual(self.raw.read_bytes()[:16], b'SQLite format 3\0')

    def test_wrong_pins_refused_before_any_decode(self):
        with self.assertRaisesRegex(ValueError, 'seal'):
            self.open(expected_head_hash='0' * 64)
        with self.assertRaisesRegex(ValueError, 'seal'):
            self.open(expected_count=self.count - 1)
        with self.assertRaisesRegex(ValueError, 'physical'):
            self.open(expected_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'size'):
            self.open(expected_bytes=1)

    def _tampered_copy(self, sql, params):
        copy = Path(self.temp.name) / 'tampered.sqlite'
        shutil.copy(self.compact, copy)
        with sqlite3.connect(copy) as db:
            db.execute(sql, params)
        db.close()
        return copy, hashlib.sha256(copy.read_bytes()).hexdigest()

    def test_tampered_block_refused_on_access_even_with_matching_physical_pin(self):
        with self.open() as source:
            start = source.blocks[1][0]
        db = sqlite3.connect(self.compact)
        try:
            blob = db.execute('SELECT body FROM blocks WHERE start=?', (start,)).fetchone()[0]
        finally:
            db.close()
        bad = blob[:-1] + bytes([blob[-1] ^ 1])
        copy, sha = self._tampered_copy('UPDATE blocks SET body=? WHERE start=?', (bad, start))
        with self.assertRaisesRegex(ValueError, 'physical'):
            self.open(copy)
        with self.open(copy, expected_sha256=sha) as source:
            self.assertEqual(source.digest_at(0), self.rows[0][3])   # an untouched block still answers
            with self.assertRaisesRegex(ValueError, 'block identity'):
                source.digest_at(start)
        copy2, sha2 = self._tampered_copy('UPDATE blocks SET body=?, sha256=? WHERE start=?',
                                          (bad, hashlib.sha256(bad).hexdigest(), start))
        with self.open(copy2, expected_sha256=sha2) as source:
            with self.assertRaises(ValueError):
                source.digest_at(start)

    def test_broken_block_table_refused_at_open(self):
        with self.open() as source:
            start = source.blocks[1][0]
        copy, sha = self._tampered_copy('UPDATE blocks SET previous=? WHERE start=?', ('f' * 64, start))
        with self.assertRaisesRegex(ValueError, 'chain'):
            self.open(copy, expected_sha256=sha)

    def _lineage(self, parent_count, second_count, *, rewritten=0, parent_head=None, parent_file=False):
        base = Path(self.temp.name)
        final = base / 'final' / 'source.sqlite'; final.parent.mkdir(exist_ok=True)
        parent_a = base / 'parent-a' / 'source.sqlite'; parent_a.parent.mkdir(exist_ok=True)
        parent_b = base / 'parent-b' / 'source.sqlite'; parent_b.parent.mkdir(exist_ok=True)
        head_a = parent_head or self.rows[parent_count - 1][3]
        head_b = self.rows[second_count - 1][3]
        sha_a, sha_b = 'a' * 64, 'b' * 64
        if parent_file:
            parent_a.write_bytes(b'parent bytes'); sha_a = hashlib.sha256(b'parent bytes').hexdigest()
        receipt_a = _write(base / 'final' / 'recovery-receipt.json', dict(
            recovered_path=str(final), parent_path=str(parent_a), existing_entries_rewritten=rewritten,
            parent=dict(sha256=sha_a, count=parent_count, head_hash=head_a),
            journal_count=parent_count, journal_hash=head_a))
        receipt_b = _write(base / 'parent-a' / 'recovery-receipt.json', dict(
            recovered_path=str(parent_a), parent_path=str(parent_b), existing_entries_rewritten=0,
            parent=dict(sha256=sha_b, count=second_count, head_hash=head_b),
            journal_count=second_count, journal_hash=head_b))
        lineage = dict(schema='FRANKIE_CLOSED_SOURCE_LINEAGE_V1', final_source_path=str(final), links=[
            dict(closed_parent=dict(path=str(parent_a), sha256=sha_a, count=parent_count, head_hash=head_a), recovery_receipt=receipt_a),
            dict(closed_parent=dict(path=str(parent_b), sha256=sha_b, count=second_count, head_hash=head_b), recovery_receipt=receipt_b)])
        return lineage, dict(recovery_receipt_sha256=receipt_a['sha256']), final

    def test_lineage_verified_from_compact_with_parent_absent_and_present(self):
        for present in (False, True):
            lineage, ingestion, final = self._lineage(12, 6, parent_file=present)
            with self.open() as source:
                origins, receipt = verify_lineage_from_compact(lineage, ingestion, source, final_source_path=final)
            self.assertEqual(sorted(origins.values()), [6, 12])
            self.assertEqual([l['parent_physical_pin'] for l in receipt['links']],
                             ['VERIFIED' if present else 'ABSENT_NOT_VERIFIED', 'ABSENT_NOT_VERIFIED'])
            self.assertEqual(receipt['raw_journals_opened'], 0)
            self.assertEqual(receipt['compact']['sha256'], self.sha)

    def test_lineage_refusals(self):
        with self.open() as source:
            lineage, ingestion, final = self._lineage(12, 6, parent_head='e' * 64)
            with self.assertRaisesRegex(ValueError, 'parent tail'):
                verify_lineage_from_compact(lineage, ingestion, source, final_source_path=final)
            lineage, ingestion, final = self._lineage(12, 6, rewritten=1)
            with self.assertRaisesRegex(ValueError, 'recovery receipts'):
                verify_lineage_from_compact(lineage, ingestion, source, final_source_path=final)
            lineage, ingestion, final = self._lineage(12, 6)
            with self.assertRaisesRegex(ValueError, 'recovery receipts'):
                verify_lineage_from_compact(lineage, dict(recovery_receipt_sha256='0' * 64), source, final_source_path=final)
            lineage, ingestion, final = self._lineage(self.count + 2, 6, parent_head='0' * 64)
            with self.assertRaisesRegex(ValueError, 'outside'):
                verify_lineage_from_compact(lineage, ingestion, source, final_source_path=final)


if __name__ == '__main__':
    unittest.main()
