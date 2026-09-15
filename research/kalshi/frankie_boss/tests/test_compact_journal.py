"""Exact storage, corruption, truncation and incomplete-publication boundaries."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from test_single_pass_finalization import fixture
from compact_journal import encode_block, decode_block, CompactWriter, CompactReader


class CompactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path, _, self.state, _, _ = fixture(self.temp.name, 5)
        with sqlite3.connect(self.path) as db:
            self.rows = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
        db.close()

    def test_exact_rows_and_faster_reader(self):
        encoded = encode_block(self.rows)
        self.assertEqual(decode_block(encoded), self.rows)
        path = Path(self.temp.name)/'compact.sqlite'
        with CompactWriter(path, block_bytes=10000) as writer:
            for row in self.rows:
                writer.add(row)
            writer.seal(expected_count=len(self.rows), expected_head_hash=self.rows[-1][3])
        with CompactReader(path, expected_count=len(self.rows), expected_head_hash=self.rows[-1][3]) as reader:
            self.assertEqual(list(reader.rows()), self.rows)
            self.assertEqual(len(list(reader.entries())), len(self.rows))

    def test_corrupt_and_truncated_blocks(self):
        encoded = encode_block(self.rows)
        for corrupted in (encoded[:-1], encoded + b'extra', encoded[:20]+b'bad'+encoded[23:]):
            with self.subTest(length=len(corrupted)), self.assertRaises(ValueError):
                decode_block(corrupted)

    def test_unsealed_container_refused(self):
        path = Path(self.temp.name)/'partial.sqlite'
        with CompactWriter(path, block_bytes=10000) as writer:
            writer.add(self.rows[0])
        with self.assertRaisesRegex(ValueError, 'sealed'):
            CompactReader(path, expected_count=1, expected_head_hash=self.rows[0][3])

if __name__ == '__main__':
    unittest.main()
