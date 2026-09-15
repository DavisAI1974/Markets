"""New synthetic transport/verification wiring checks; no production DB access."""
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

import verify_snapshot as runner


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        source = Path(os.environ['FRANKIE_TEST_CODE_SOURCE'])
        code = cls.root / 'code'
        code.mkdir()
        for name in runner.CODE_FILES:
            location = source / name
            if name == runner.ADAPTER:
                location = source.parents[1] / name
            shutil.copyfile(location, code / name)
        cls.modules = runner.load_code(code, cls.root / 'runtime')
        cls.journal = importlib.import_module(runner.PACKAGE + '.c15_journal')
        prefix = importlib.import_module(runner.PACKAGE + '.causal_prefix')
        records = importlib.import_module(runner.PACKAGE + '.causal_prefix_records')
        cls.scope = prefix.SourceScope(prefix.ScopeKind.PROBE_ONLY, '5' * 64,
            (prefix.SourceMember(0, 'synthetic', 'a' * 64, 100, 2),),
            records.SUPPORTED_ADAPTER_REVISION)
        cls.database = cls.root / 'synthetic.sqlite'
        driver = cls.modules.SourceConformanceDriver(cls.scope, cls.database,
            expected_scope_hash=cls.scope.genesis_hash())
        for cursor in range(2):
            row = dict(instrument_id=1, publisher_id=1, channel_id=1, order_id=0,
                action='N', side='N', price=0, size=0, flags=128, sequence=cursor,
                ts_event=cursor * 100 + 1, ts_recv=cursor * 100 + 2, ts_in_delta=1)
            driver.append(row, cursor=cursor, source_member_index=0,
                source_sha256='a' * 64, session_id='synthetic', source_dbn_object='synthetic')
        cls.state = driver._builder.export_state()
        cls.expected = driver.complete()
        driver.close()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_original_restore_and_complete_with_two_progress_passes(self):
        events = []
        before = runner.sha256(self.database)
        completion = runner.verify_state(self.database, self.state, self.scope,
            self.modules, events.append, workers=2)
        self.assertEqual(completion, self.expected)
        self.assertEqual(before, runner.sha256(self.database))
        self.assertEqual([(e['phase'], e['entries']) for e in events if e['status'] == 'pass_complete'],
            [('journal_restore', 4), ('source_conformance', 4)])
        self.assertNotIn('torch', __import__('sys').modules)

    def test_valid_self_hash_cannot_hide_wrong_journal_binding(self):
        state = self.journal.unpack(self.journal.pack(self.state))
        state['journal_hash'] = '0' * 64
        state['state_hash'] = self.journal.evidence_hash({k: v for k, v in state.items() if k != 'state_hash'})
        with self.assertRaises(ValueError):
            runner.verify_state(self.database, state, self.scope, self.modules, lambda _: None)

    def test_modified_code_bytes_rejected_before_import(self):
        bundle = self.root / 'corrupt-bundle'
        bundle.mkdir()
        (bundle / 'sample.py').write_bytes(b'original\r\n')
        material = {'files': {'sample.py': {'bytes': 10, 'sha256': runner.sha256(bundle / 'sample.py')}}}
        (bundle / 'sample.py').write_bytes(b'changed!\r\n')
        with self.assertRaises(ValueError):
            runner.verify_files(bundle, material, ['sample.py'], lambda _: None)

    def test_escaping_manifest_name_rejected(self):
        with self.assertRaises(ValueError):
            runner.verify_files(self.root, {'files': {'../escape': {'bytes': 1, 'sha256': 'a' * 64}}},
                ['../escape'], lambda _: None)

    def corrupted(self, name, sql):
        target = self.root / name
        shutil.copyfile(self.database, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute('DROP TRIGGER forbid_update')
            connection.execute('DROP TRIGGER forbid_delete')
            connection.execute(sql)
            connection.commit()
        finally:
            connection.close()
        return target

    def test_corruption_fixture_closes_its_handle(self):
        path = self.corrupted('fixture-close.sqlite', 'DELETE FROM entries WHERE ordinal=3')
        renamed = path.with_name('fixture-close-renamed.sqlite')
        path.rename(renamed)
        self.assertTrue(renamed.is_file())

    def test_parallel_rejects_noncanonical_body(self):
        path = self.corrupted('noncanonical.sqlite', "UPDATE entries SET body=CAST(' ' || CAST(body AS TEXT) AS BLOB) WHERE ordinal=1")
        with self.assertRaises(ValueError):
            runner.verify_state(path, self.state, self.scope, self.modules, lambda _: None, workers=2)

    def test_parallel_rejects_corrupt_digest(self):
        path = self.corrupted('digest.sqlite', "UPDATE entries SET digest='corrupted' WHERE ordinal=1")
        with self.assertRaises(ValueError):
            runner.verify_state(path, self.state, self.scope, self.modules, lambda _: None, workers=2)

    def test_parallel_rejects_missing_terminal_row(self):
        path = self.corrupted('short.sqlite', 'DELETE FROM entries WHERE ordinal=3')
        with self.assertRaises(ValueError):
            runner.verify_state(path, self.state, self.scope, self.modules, lambda _: None, workers=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
