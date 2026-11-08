import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from runpod_seal_touch_print import seal


RUNNER = Path(__file__).resolve().parents[3] / 'research/kalshi/adaptive_wavepacket_20261108/markets_bridge/discovery_touch_print.py'


class SealTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source = self.root / 'groups.jsonl.gz'
        self.target = self.root / 'decisions'
        start = 1696204800000000000
        rows = [dict(group_ordinal=i, first_cursor=i, close_cursor=i,
                     event_ns=start+i, receive_ns=start+i, ask=[102, size, 1], bid=[100, 7, 1],
                     snapshot_member=False, reset_member=False, bad_receive_clock_member=False,
                     prints=[dict(source_ordinal=0, trade_input_cursor=i, price_raw=102)] if i == 2 else [])
                for i, size in enumerate((8, 7, 6))]
        with gzip.open(self.source, 'wt') as stream:
            stream.writelines(json.dumps(row)+'\n' for row in rows)
        self.receipt = dict(session='20231002', counts=dict(groups=3, prints=1),
                            groups_file=dict(path=self.source.name, bytes=self.source.stat().st_size,
                                             sha256=hashlib.sha256(self.source.read_bytes()).hexdigest()))
        self.save_receipt()

    def save_receipt(self):
        (self.root / 'receipt.json').write_text(json.dumps(self.receipt))

    def test_real_runner_seals_decisions_and_reuses_without_rewrite(self):
        result = seal('20231002', self.source, self.target, RUNNER)
        output = self.target / 'decisions.jsonl.gz'
        with gzip.open(output, 'rt') as stream:
            rows = [json.loads(line) for line in stream]
        self.assertEqual(len(rows), 3)
        self.assertEqual(result['summary']['scope'], 'partial')
        self.assertEqual(result['decision_rows'], 3)
        self.assertEqual(result['status'], 'touch-print-decisions-sealed')
        stamp = output.stat().st_mtime_ns
        self.assertEqual(seal('20231002', self.source, self.target, RUNNER), result)
        self.assertEqual(output.stat().st_mtime_ns, stamp)

    def test_incomplete_source_never_seals(self):
        self.receipt['counts']['groups'] = 4
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, 'source_groups'):
            seal('20231002', self.source, self.target, RUNNER)
        self.assertFalse(self.target.exists())

    def test_wrong_day_and_missing_seal_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'session'):
            seal('20231003', self.source, self.target, RUNNER)
        (self.root / 'receipt.json').unlink()
        with self.assertRaises(FileNotFoundError):
            seal('20231002', self.source, self.target, RUNNER)
        self.assertFalse(self.target.exists())

    def test_existing_result_missing_decisions_cannot_pass(self):
        seal('20231002', self.source, self.target, RUNNER)
        (self.target / 'decisions.jsonl.gz').unlink()
        with self.assertRaises(FileNotFoundError):
            seal('20231002', self.source, self.target, RUNNER)


if __name__ == '__main__':
    unittest.main()
