"""New integration and indexed worker-seam tests for the combined stack."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from test_single_pass_finalization import fixture
from compact_journal import CompactWriter, CompactReader
from compact_conformance_reader import CompactConformanceReader
from single_pass_finalization import finalize_snapshot


class CombinedTests(unittest.TestCase):
    def test_full_conformance_parallel_compact_and_seam_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            source, scope, state, expected, _ = fixture(directory, 12)
            compact = Path(directory)/'compact.sqlite'
            db = sqlite3.connect(source)
            try:
                rows = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
            finally:
                db.close()
            with CompactWriter(compact, block_bytes=12000) as writer:
                for row in rows:
                    writer.add(row)
                writer.seal(expected_count=len(rows), expected_head_hash=state['journal_hash'])
            with CompactReader(compact, expected_count=len(rows), expected_head_hash=state['journal_hash']) as reader:
                self.assertEqual(list(reader.rows()), rows)
            result = finalize_snapshot(compact, scope, state, expected_scope_hash=scope.genesis_hash(),
                expected_state_hash=state['state_hash'],
                expected_physical_sha256=hashlib.sha256(compact.read_bytes()).hexdigest(),
                storage='compact', workers=2)
            self.assertEqual(result.completion, expected)
            self.assertEqual(result.checkpoint, state)
            db = sqlite3.connect(compact)
            db.execute("UPDATE blocks SET previous=? WHERE start=0", ('0'*64,))
            db.commit()
            db.close()
            with CompactConformanceReader(compact, expected_count=len(rows),
                    expected_head_hash=state['journal_hash'], workers=2) as reader:
                with self.assertRaises(ValueError):
                    list(reader.entries())

if __name__ == '__main__':
    unittest.main()
