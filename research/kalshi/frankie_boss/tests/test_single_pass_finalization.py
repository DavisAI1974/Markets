"""Focused standard-library tests for new finalization boundaries."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from causal_prefix import ScopeKind, SourceMember, SourceScope
from source_conformance import SourceConformanceDriver
from single_pass_finalization import finalize_snapshot
from verified_journal_reader import VerifiedJournalReader


def fixture(directory, count=3):
    scope = SourceScope(kind=ScopeKind.PROBE_ONLY, scope_id='5'*64,
        members=(SourceMember(0, 'synthetic', 'a'*64, 100, count),),
        adapter_revision='NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823')
    path = Path(directory)/'source.sqlite'
    driver = SourceConformanceDriver(scope, path, expected_scope_hash=scope.genesis_hash())
    for i in range(count):
        raw = dict(instrument_id=1, publisher_id=1, channel_id=1, order_id=i+1,
            action='A', side='A', price=101, size=10, flags=128, sequence=i,
            ts_event=i*100+1, ts_recv=i*100+2, ts_in_delta=1)
        driver.append(raw, cursor=i, source_member_index=0, source_sha256='a'*64,
            session_id='s', raw_symbol='NG', source_dbn_object='synthetic')
    expected = driver.complete()
    state = driver._builder.export_state()
    driver.close()
    return path, scope, state, expected, hashlib.sha256(path.read_bytes()).hexdigest()


class FinalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path, self.scope, self.state, self.expected, self.physical = fixture(self.temp.name)

    def run_finalizer(self, **overrides):
        args = dict(expected_scope_hash=self.scope.genesis_hash(),
            expected_state_hash=self.state['state_hash'], expected_physical_sha256=self.physical)
        args.update(overrides)
        return finalize_snapshot(self.path, self.scope, self.state, **args)

    def test_completion_checkpoint_one_traversal(self):
        original = VerifiedJournalReader.entries
        visits = []
        def counted(reader):
            visits.append(1)
            yield from original(reader)
        with patch.object(VerifiedJournalReader, 'entries', counted):
            result = self.run_finalizer()
        self.assertEqual(result.completion, self.expected)
        self.assertEqual(result.checkpoint, self.state)
        self.assertEqual(visits, [1])
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.physical)

    def test_physical_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'physical'):
            self.run_finalizer(expected_physical_sha256='0'*64)

    def test_checkpoint_mismatch(self):
        self.state = copy.deepcopy(self.state)
        self.state['sessions'] = []
        with self.assertRaisesRegex(ValueError, 'checkpoint'):
            self.run_finalizer()

if __name__ == '__main__':
    unittest.main()
