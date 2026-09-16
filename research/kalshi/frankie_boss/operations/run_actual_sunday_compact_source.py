"""Sunday host whose source verification is answered by the compact journal, not the raw 11.7 GB one.

The lawful host (run_actual_sunday.py, untouched) touches the raw journals in exactly two methods:
source_lineage() hashes the 4.4 GB lineage parent and reads both raw journals' tails/anchors, and
prefix() reads one row digest from the raw origin per cycle. This module builds a SUBCLASS of the
lawful ActualHost, over whichever checkout the caller imported it from, that answers both from
compact_source.CompactSource: the sealed container is pinned to the host configuration's
compact_journal witness (sha256, bytes) and to the ingestion completion (count, head), and each
answer decodes one verified block. Every other check of the two methods is kept verbatim;
tests/test_run_actual_sunday_compact_source.py holds prefix() to the lawful text modulo the anchor.

    python run_actual_sunday_compact_source.py --configuration host.json --verify-source-only --run-directory <scratch>
        source() + prefix() for all 19 cycles, no model, no training; writes compact-source-verification.json
    python run_actual_sunday_compact_source.py --configuration host.json
        the lawful main() with this host class substituted (everything else identical)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time


def _load_compact_source(tools_root=None):
    try:
        from research.kalshi.frankie_boss import compact_source
        return compact_source
    except ImportError:
        pass
    candidates = [Path(__file__).resolve().parent.parent / 'compact_source.py']
    if tools_root is not None:
        candidates.insert(0, Path(tools_root) / 'research' / 'kalshi' / 'frankie_boss' / 'compact_source.py')
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location('compact_source', str(path))
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            return module
    raise ImportError('compact_source.py not found')


def host_class(actual, tools_root=None):
    """Subclass actual.ActualHost (the caller's checkout) with compact-source verification."""
    compact_source = _load_compact_source(tools_root)
    Path = actual.Path; json = actual.json

    class CompactSourceHost(actual.ActualHost):
        def compact_source(self):
            if getattr(self, '_compact', None) is None:
                witness = self.host['compact_journal']
                completion = self.full_source_completion
                self._compact = compact_source.CompactSource(witness['path'], expected_sha256=witness['sha256'],
                    expected_bytes=witness.get('bytes'), expected_count=completion['journal_count'],
                    expected_head_hash=completion['journal_hash'])
            return self._compact

        def source_lineage(self, source, ingestion):
            lineage = actual.verified_json(self.host['source_lineage'])
            compact = self.compact_source()
            origins, receipt = compact_source.verify_lineage_from_compact(
                lineage, ingestion, compact, final_source_path=source / 'source.sqlite')
            self.source_origins.update(origins)
            self.source_origins[str(Path(compact.path).resolve())] = compact.count
            self.save('verified-source-lineage.c15.json', dict(witness=self.host['source_lineage'], lineage=lineage))
            self.save('verified-compact-source.c15.json', receipt)

        # The lawful prefix() verbatim, except that the snapshot's anchor digest is read from the
        # compact source instead of the raw origin journal (see the drift-guard test).
        def prefix(self,binding,cycle_directory):
            self.close_cache()
            # Prefix files are created and pinned by the external source host before
            # any paid lease. The first observation of its witness is retained here.
            witness_path=Path(self.host['prefixes_directory'])/f"prefix-{binding['cycle_index']:02d}-witness.json"
            value=json.loads(witness_path.read_bytes())
            if set(value)!={'snapshot','receipt'}:raise ValueError('explicit prefix file witnesses required')
            self.api.driver._save(cycle_directory/'host-prefix.c15.json',dict(witness_path=str(witness_path.resolve()),
                witness_sha256=actual.sha(witness_path),files=value))
            snapshot=actual.verified(value['snapshot']);receipt=actual.verified_json(value['receipt'])
            origin=Path(receipt['original_journal']).resolve()
            if receipt.get('schema') in ('C15_JOURNAL_PREFIX_SNAPSHOT_V1','C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1'):
                if (receipt['snapshot_sha256']!=value['snapshot']['sha256'] or
                    receipt['through_cursor']!=binding['through_cursor']):
                    raise ValueError('new snapshot bytes/cursor differ from actual witness')
                # Preserve the copier's original receipt. Derive the two scope fields
                # in a new, separately saved outer lineage record from final source.
                outer=dict(schema='FRANKIE_SOURCE_LINKED_PREFIX_V1',snapshot_receipt=receipt,
                    snapshot_receipt_sha256=value['receipt']['sha256'],
                    ingestion_receipt_sha256=self.ingestion_receipt_sha256,
                    source_completion_sha256=self.completion_sha256,
                    source_scope_hash=self.scope.genesis_hash(),source_records_expected=self.full_source_completion['record_count'])
                self.api.driver._save(cycle_directory/'host-prefix-source-lineage.c15.json',outer)
                receipt=dict(receipt,source_scope_hash=outer['source_scope_hash'],source_records_expected=outer['source_records_expected'])
            if (str(origin) not in self.source_origins or receipt['journal_count']>self.source_origins[str(origin)] or
                Path(receipt['snapshot_journal']).resolve()!=snapshot.resolve() or
                receipt['source_scope_hash']!=self.scope.genesis_hash() or
                receipt['records_in_prefix']!=binding['through_cursor']+1 or
                receipt['source_prefix_hash']!=binding['source_hash'] or
                receipt['as_of']!=binding['as_of'] or receipt['source_as_of']!=binding['source_as_of'] or
                receipt['source_records_expected']!=57027):
                raise ValueError('actual prefix snapshot differs from full source and authored cutoff')
            if self.compact_source().digest_at(receipt['journal_count']-1)!=receipt['journal_head_hash']:
                raise ValueError('snapshot head differs from compact source prefix')
            if receipt['journal_count']!=2*receipt['records_in_prefix']:
                raise ValueError('prefix record denominator differs')
            reader = self.api.VerifiedJournalReader
            reader_options = {}
            if receipt.get('schema') == 'C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1':
                reader = self.api.FrankieCompactReader
                reader_options = dict(workers=self.host.get('data_workers', 1),
                    emit=None if self.probe is None else self.probe.data)
            journal=reader(snapshot,expected_count=receipt['journal_count'],
                expected_head_hash=receipt['journal_head_hash'],**reader_options)
            old=self.builder
            self.builder=self.api.OnlinePrefix(self.scope,journal,self.api.PrefixCursor(receipt['records_in_prefix'],receipt['source_prefix_hash']))
            self.source_checkpoint=dict(count=receipt['journal_count'],head_hash=receipt['journal_head_hash'])
            self.source_journal_path=str(snapshot.resolve())
            if self.context is not None:self.context.builder=self.builder
            if old is not None:old.journal.close()

        def close(self):
            try:
                super().close()
            finally:
                if getattr(self, '_compact', None) is not None:
                    self._compact.close(); self._compact = None

    return CompactSourceHost


def _lawful(repository):
    repository = Path(repository).resolve()
    if str(repository) not in sys.path:
        sys.path.insert(0, str(repository))
    from research.kalshi.frankie_boss.operations import run_actual_sunday as actual
    return actual


def verify_source_only(configuration, run_directory, tools_root=None):
    """source() and prefix() for every scheduled cycle with no model, no training and no service."""
    run_directory = Path(run_directory).resolve()
    name = run_directory.name.lower()
    if 'scratch' not in name and 'verify' not in name:
        raise SystemExit('verify-only run directory must be explicitly disposable (scratch/verify in its name)')
    actual = _lawful(configuration['host_runtime']['repository'])
    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle
    scratch = json.loads(json.dumps(configuration)); scratch['run_directory'] = str(run_directory)
    started = time.perf_counter()
    host = host_class(actual, tools_root)(scratch)
    try:
        host.source()
        source_seconds = time.perf_counter() - started
        schedule = json.loads(actual.verified(configuration['host_runtime']['schedule']).read_bytes())
        steps = schedule['steps'] if isinstance(schedule, dict) else schedule
        cycles = []
        for index, step in enumerate(steps):
            binding = bind_cycle(configuration['contract']['path'], configuration['contract']['sha256'], index, step)
            cycle_directory = run_directory / f'cycle-{index:02d}'; cycle_directory.mkdir(parents=True, exist_ok=True)
            before = host.compact_source().decoded_blocks; t0 = time.perf_counter()
            host.prefix(binding, cycle_directory)
            cycles.append(dict(cycle_index=index, through_cursor=binding['through_cursor'],
                               source_checkpoint=dict(host.source_checkpoint), snapshot=host.source_journal_path,
                               compact_blocks_decoded=host.compact_source().decoded_blocks - before,
                               seconds=round(time.perf_counter() - t0, 3)))
            print(json.dumps(cycles[-1]), flush=True)
        receipt = dict(schema='FRANKIE_COMPACT_SOURCE_VERIFICATION_V1', run_directory=str(run_directory),
                       source_seconds=round(source_seconds, 3), total_seconds=round(time.perf_counter() - started, 3),
                       compact=host.compact_source().receipt(), source_origins=host.source_origins, cycles=cycles,
                       lineage=host.load('verified-compact-source.c15.json'),
                       model_forward_performed=False, training_updates_performed=False)
        (run_directory / 'compact-source-verification.json').write_bytes(json.dumps(receipt, indent=1, sort_keys=True, default=str).encode())
        print(json.dumps(dict(status='compact_source_verified', cycles=len(cycles), source_seconds=receipt['source_seconds'],
                              total_seconds=receipt['total_seconds'], blocks_decoded=host.compact_source().decoded_blocks)), flush=True)
        return 0
    finally:
        host.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--verify-source-only', action='store_true')
    parser.add_argument('--run-directory', help='disposable directory for --verify-source-only')
    parser.add_argument('--tools-root', help='checkout holding compact_source.py when the lawful tree predates it')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    configuration = json.loads(Path(args.configuration).read_bytes())
    if args.verify_source_only:
        if not args.run_directory:
            raise SystemExit('--run-directory required with --verify-source-only')
        return verify_source_only(configuration, args.run_directory, args.tools_root)
    actual = _lawful(configuration['host_runtime']['repository'])
    actual.ActualHost = host_class(actual, args.tools_root)   # the lawful main() then runs unchanged
    sys.argv = [sys.argv[0], '--configuration', args.configuration] + (['--prepare-only'] if args.prepare_only else [])
    return actual.main()


if __name__ == '__main__':
    raise SystemExit(main())
