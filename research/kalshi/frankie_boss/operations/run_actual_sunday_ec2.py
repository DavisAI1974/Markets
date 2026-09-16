"""Launch a NEW Sunday run on a declared persistent EC2 native host.

This wrapper preserves the lawful Sunday host and compact-reader lineage. It only:
- requires a new run directory/run id on first launch;
- applies and records the declared numeric/toolchain policy before model creation;
- permits later prepare/recovery resume only under the exact stable host identity;
- enables safe native-step substage/resource diagnostics;
- uses the existing audited hot-sidecar rule for closed lineage parents so a
  read-only SQLite open cannot make its own next resume fail.

It never adopts the failed cycle-00 run directory or training checkpoint.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

from research.kalshi.frankie_boss.native_runtime_policy import apply_native_runtime_policy


_STABLE_IDENTITY_FIELDS = (
    'schema', 'parent_run_id', 'run_id', 'numeric_identity', 'python', 'python_version',
    'torch', 'numpy', 'torch_intraop_threads', 'torch_interop_threads',
    'deterministic_algorithms', 'platform_system', 'platform_release', 'platform_machine',
    'logical_cpus', 'cpu_model', 'system_memory_total_bytes',
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _stable_identity(value):
    if type(value) is not dict or any(name not in value for name in _STABLE_IDENTITY_FIELDS):
        raise ValueError('native host runtime identity is incomplete')
    return {name: value[name] for name in _STABLE_IDENTITY_FIELDS}


def _write_new(path, value):
    raw = _canonical(value)
    with Path(path).open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--ec2-resume', action='store_true')
    args, _ = parser.parse_known_args()
    configuration = json.loads(Path(args.configuration).read_bytes())
    if configuration.get('schema') != 'FRANKIE_BOSS_ACTUAL_HOST_CONFIGURATION_V1':
        raise ValueError('actual Sunday host configuration required')
    if configuration.get('model_calls_performed') is not False or configuration.get('training_updates_performed') is not False:
        raise ValueError('new benchmark configuration must declare no prior calls or training updates')

    identity = apply_native_runtime_policy(configuration)
    run_directory = Path(configuration['run_directory'])
    identity_path = run_directory/'native-host-runtime.json'
    if run_directory.exists():
        if not args.ec2_resume or not identity_path.is_file():
            raise FileExistsError('existing directory is not an explicitly resumable NEW EC2 run')
        retained = json.loads(identity_path.read_bytes())
        if _canonical(_stable_identity(retained)) != _canonical(_stable_identity(identity)):
            raise RuntimeError('EC2 resume stable host/toolchain identity differs from first launch')
    else:
        if args.ec2_resume:
            raise FileNotFoundError('EC2 resume requested before the NEW run exists')
        run_directory.mkdir(parents=True, exist_ok=False)
        _write_new(identity_path, identity)

    # The production host does not know this wrapper-only switch.
    if args.ec2_resume:
        sys.argv = [argument for argument in sys.argv if argument != '--ec2-resume']

    # Import only after the numeric runtime policy is fixed. The production host
    # still enforces its exact checked-out boss_commit and all existing receipts.
    from research.kalshi.frankie_boss.operations import run_actual_sunday as actual
    from research.kalshi.frankie_boss.journal_prefix_snapshot import _sidecars

    class EC2ActualHost(actual.ActualHost):
        def source_lineage(self, source, ingestion):
            """Lawful lineage verification with the existing hot-sidecar definition."""
            lineage=actual.verified_json(self.host['source_lineage'])
            if (lineage.get('schema')!='FRANKIE_CLOSED_SOURCE_LINEAGE_V1' or
                Path(lineage['final_source_path']).resolve()!=(source/'source.sqlite').resolve() or not lineage['links']):
                raise ValueError('explicit closed source lineage required')
            child=(source/'source.sqlite').resolve();seen=set()
            for index,link in enumerate(lineage['links']):
                witness=link['recovery_receipt'];recovery=actual.verified_json(witness);parent=link['closed_parent']
                path=Path(parent['path']).resolve()
                if (str(path) in seen or path==child or Path(recovery['recovered_path']).resolve()!=child or
                    Path(recovery['parent_path']).resolve()!=path or recovery['existing_entries_rewritten']!=0 or
                    any(parent[k]!=recovery['parent'][k] for k in ('sha256','count','head_hash')) or
                    (index==0 and witness['sha256']!=ingestion['recovery_receipt_sha256'])):
                    raise ValueError('closed lineage differs from actual recovery receipts')
                if _sidecars(path):
                    raise ValueError('lineage parent must be closed before verification')
                actual.verified(parent)
                connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
                try:tail=connection.execute('SELECT ordinal,digest FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()
                finally:connection.close()
                if tail is None or (tail[0]+1,tail[1])!=(parent['count'],parent['head_hash']):
                    raise ValueError('closed lineage parent differs from independently supplied tail')
                connection=sqlite3.connect(child.as_uri()+'?mode=ro',uri=True)
                try:anchor=connection.execute('SELECT digest FROM entries WHERE ordinal=?',(recovery['journal_count']-1,)).fetchone()
                finally:connection.close()
                if anchor is None or anchor[0]!=recovery['journal_hash']:
                    raise ValueError('child no longer contains its verified rehydration boundary')
                self.source_origins[str(path)]=parent['count']//2*2
                seen.add(str(path));child=path
            self.save('verified-source-lineage.c15.json',dict(witness=self.host['source_lineage'],lineage=lineage))

        def runtime(self, binding, cycle_directory, retained_plan):
            runtime = super().runtime(binding, cycle_directory, retained_plan)
            if self.probe is not None:
                runtime.learning_event = lambda value: self.probe.call('training_event', value)
            return runtime

    actual.ActualHost = EC2ActualHost
    return actual.main()


if __name__ == '__main__':
    raise SystemExit(main())
