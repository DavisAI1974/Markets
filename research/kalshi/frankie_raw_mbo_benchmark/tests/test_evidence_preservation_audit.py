"""Regressions from the pre-comparison evidence-preservation audit."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_row_sink import RowSink, RowSinkError
from research.kalshi.frankie_raw_mbo_benchmark.native_full_capture_adapter import FullCaptureAdapter
from research.kalshi.frankie_raw_mbo_benchmark.native_a_arm_launch import NATIVE_RECORD_FIELDS
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_full_capture_adapter import rec


class PreservationAuditTests(unittest.TestCase):
    def test_existing_ledger_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ledger.jsonl'
            before = b'{"prior_evidence":1}\n'
            path.write_bytes(before)
            with self.assertRaises((RowSinkError, FileExistsError)):
                RowSink(path, ledger='test')
            self.assertEqual(path.read_bytes(), before)

    def test_equal_length_equal_count_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ledger.jsonl'
            sink = RowSink(path, ledger='test')
            sink.write({'id': 1, 'value': 11})
            sink.close()
            path.write_bytes(path.read_bytes().replace(b'11', b'99'))
            with self.assertRaises(RowSinkError):
                sink.reconcile(1)

    def test_reconciliation_binds_actual_file_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ledger.jsonl'
            sink = RowSink(path, ledger='test')
            sink.write({'id': 2**63 + 1, 'value': -0.0})
            receipt = sink.reconcile(1)
            self.assertEqual(receipt['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(receipt['bytes'], len(path.read_bytes()))

    def test_raw_native_record_retains_rtype_and_unknown_fields(self):
        raw = rec(seq=1, order_id=11)
        raw.update(rtype=160, extension={'id': 2**63 + 1, 'value': -0.0})
        frame, _ = FullCaptureAdapter().apply(raw)
        self.assertEqual(frame['raw_actions'][0]['source_record'], raw)
        raw['extension']['id'] = 0
        self.assertEqual(frame['raw_actions'][0]['source_record']['extension']['id'], 2**63 + 1)
        self.assertIn('rtype', NATIVE_RECORD_FIELDS)

    def test_missing_null_and_zero_remain_distinct_in_source_record(self):
        rows = []
        for kind in ('missing', 'null', 'zero'):
            raw = rec(seq=1, order_id=12)
            if kind == 'missing':
                del raw['ts_in_delta']
            else:
                raw['ts_in_delta'] = None if kind == 'null' else 0
            frame, _ = FullCaptureAdapter().apply(raw)
            rows.append(frame['raw_actions'][0])
        self.assertNotIn('ts_in_delta', rows[0]['source_record'])
        self.assertIsNone(rows[1]['source_record']['ts_in_delta'])
        self.assertEqual(rows[2]['source_record']['ts_in_delta'], 0)
        self.assertIn('ts_in_delta', rows[0]['source_missing_fields'])
        self.assertIn('ts_in_delta', rows[1]['source_null_fields'])
        self.assertNotIn('ts_in_delta', rows[2]['source_missing_fields'])

    def test_non_json_exact_extensions_refuse_before_book_mutation(self):
        for extension in ((1, 2), {1: 'numeric key'}, b'raw', float('nan')):
            with self.subTest(extension=repr(extension)):
                raw = rec(seq=1, order_id=13)
                raw['extension'] = extension
                adapter = FullCaptureAdapter()
                with self.assertRaises((TypeError, ValueError)):
                    adapter.apply(raw)
                self.assertEqual(adapter.record_count, 0)
                self.assertFalse(adapter.books)


if __name__ == '__main__':
    unittest.main()
