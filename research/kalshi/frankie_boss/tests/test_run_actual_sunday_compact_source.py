"""The compact-source host is the lawful host with exactly two raw-journal reads replaced.

Drift guard: the subclass's prefix() must equal the lawful prefix() text after the one anchor
substitution and the module-qualified helper names; if the lawful method changes, this fails and
the subclass must be re-synced by hand. source_lineage() must route through
compact_source.verify_lineage_from_compact and never open a raw SQLite file.
"""
import importlib.util
import inspect
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OPERATIONS = REPO / 'research' / 'kalshi' / 'frankie_boss' / 'operations'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


actual = load('actual_lawful_for_compact_test', OPERATIONS / 'run_actual_sunday.py')
compact = load('run_actual_sunday_compact_source_test', OPERATIONS / 'run_actual_sunday_compact_source.py')

LAWFUL_ANCHOR = """        connection=sqlite3.connect(origin.as_uri()+'?mode=ro',uri=True)
        try:
            row=connection.execute('SELECT digest FROM entries WHERE ordinal=?',(receipt['journal_count']-1,)).fetchone()
            if row is None or row[0]!=receipt['journal_head_hash']:
                raise ValueError('snapshot head differs from original immutable source prefix')
        finally:connection.close()
"""
COMPACT_ANCHOR = """        if self.compact_source().digest_at(receipt['journal_count']-1)!=receipt['journal_head_hash']:
            raise ValueError('snapshot head differs from compact source prefix')
"""


class CompactSourceHostTests(unittest.TestCase):
    def setUp(self):
        self.Host = compact.host_class(actual)

    def test_prefix_is_lawful_text_modulo_anchor(self):
        lawful = textwrap.dedent(inspect.getsource(actual.ActualHost.prefix))
        ours = textwrap.dedent(inspect.getsource(self.Host.prefix))
        lawful_anchor = textwrap.indent(textwrap.dedent(LAWFUL_ANCHOR), '    ')
        compact_anchor = textwrap.indent(textwrap.dedent(COMPACT_ANCHOR), '    ')
        self.assertIn(lawful_anchor, lawful)
        expected = lawful.replace(lawful_anchor, compact_anchor)
        for helper in ('sha(', 'verified(', 'verified_json('):
            expected = expected.replace('=' + helper, '=actual.' + helper).replace(';' + helper, ';actual.' + helper)
        self.assertEqual(ours.strip(), expected.strip())

    def test_source_lineage_routes_through_compact_and_opens_no_sqlite(self):
        source = inspect.getsource(self.Host.source_lineage)
        self.assertIn('verify_lineage_from_compact', source)
        self.assertNotIn('sqlite3', source)
        self.assertIn("verified-source-lineage.c15.json", source)

    def test_subclass_keeps_every_other_lawful_method(self):
        overridden = {'compact_source', 'source_lineage', 'prefix', 'close'}
        for name, member in inspect.getmembers(actual.ActualHost, predicate=inspect.isfunction):
            if name in overridden:
                continue
            self.assertIs(getattr(self.Host, name), member, name)

    def test_harness_exposes_the_switch(self):
        harness = (OPERATIONS / 'benchmark_native_learner_direct.py').read_text(encoding='utf-8')
        self.assertIn('--compact-source-tools', harness)
        self.assertIn('host_class(actual', harness)


if __name__ == '__main__':
    unittest.main()
