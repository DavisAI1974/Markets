"""The drain profiler reads a journal read-only, counts every row, and refuses a wrong receipt."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from test_single_pass_finalization import fixture
from compact_journal import CompactWriter

TOOL = Path(__file__).resolve().parent.parent / 'operations' / 'profile_journal_drain.py'


class ProfileDrainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path, _, _, _, _ = fixture(self.temp.name, 6)
        with sqlite3.connect(self.path) as db:
            self.rows = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
        db.close()
        self.count, self.head = len(self.rows), self.rows[-1][3]

    def run_tool(self, journal, receipt, *extra):
        receipt_path = Path(self.temp.name) / 'receipt.json'
        receipt_path.write_text(json.dumps(receipt))
        report = Path(self.temp.name) / 'report.json'
        proc = subprocess.run([sys.executable, str(TOOL), '--journal', str(journal), '--receipt', str(receipt_path),
                               '--report', str(report), *extra], capture_output=True, text=True)
        return proc, (json.loads(report.read_text()) if report.exists() else None)

    def test_raw_drain_counts_every_row(self):
        before = self.path.read_bytes()
        proc, report = self.run_tool(self.path, dict(schema='C15_JOURNAL_PREFIX_SNAPSHOT_V1',
                                                     journal_count=self.count, journal_head_hash=self.head))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report['runs'][0]['rows'], self.count)
        self.assertEqual(report['runs'][0]['applied_records'], self.count // 2)
        self.assertTrue(report['runs'][0]['complete'])
        self.assertEqual(self.path.read_bytes(), before)

    def test_compact_drain_single_and_workers(self):
        compact = Path(self.temp.name) / 'compact.sqlite'
        with CompactWriter(compact, block_bytes=4096) as writer:
            for row in self.rows:
                writer.add(row)
            writer.seal(expected_count=self.count, expected_head_hash=self.head)
        proc, report = self.run_tool(compact, dict(schema='C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1',
                                                   journal_count=self.count, journal_head_hash=self.head),
                                     '--workers', '2')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual([run['rows'] for run in report['runs']], [self.count, self.count])

    def test_wrong_receipt_refused(self):
        proc, report = self.run_tool(self.path, dict(schema='C15_JOURNAL_PREFIX_SNAPSHOT_V1',
                                                     journal_count=self.count, journal_head_hash='0' * 64))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIsNone(report)


if __name__ == '__main__':
    unittest.main()
