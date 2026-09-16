"""Launch a NEW Sunday run on a declared persistent EC2 native host.

This wrapper preserves the lawful Sunday host and compact-reader lineage. It only:
- requires a new run directory/run id;
- applies and records the declared numeric/toolchain policy before model creation;
- enables safe native-step substage/resource diagnostics.

It does not migrate or resume the failed cycle-00 training checkpoint.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from research.kalshi.frankie_boss.native_runtime_policy import apply_native_runtime_policy


def _write_new(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    with Path(path).open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--configuration', required=True)
    args, _ = parser.parse_known_args()
    configuration = json.loads(Path(args.configuration).read_bytes())
    if configuration.get('schema') != 'FRANKIE_BOSS_ACTUAL_HOST_CONFIGURATION_V1':
        raise ValueError('actual Sunday host configuration required')
    if configuration.get('model_calls_performed') is not False or configuration.get('training_updates_performed') is not False:
        raise ValueError('new benchmark configuration must declare no prior calls or training updates')
    run_directory = Path(configuration['run_directory'])
    if run_directory.exists():
        raise FileExistsError('NEW Sunday rerun requires a nonexistent run_directory')
    identity = apply_native_runtime_policy(configuration)
    run_directory.mkdir(parents=True, exist_ok=False)
    _write_new(run_directory/'native-host-runtime.json', identity)

    # Import only after the numeric runtime policy is fixed. The production host
    # still enforces its exact checked-out boss_commit and all existing receipts.
    from research.kalshi.frankie_boss.operations import run_actual_sunday as actual

    class EC2ActualHost(actual.ActualHost):
        def runtime(self, binding, cycle_directory, retained_plan):
            runtime = super().runtime(binding, cycle_directory, retained_plan)
            if self.probe is not None:
                runtime.learning_event = lambda value: self.probe.call('training_event', value)
            return runtime

    actual.ActualHost = EC2ActualHost
    return actual.main()


if __name__ == '__main__':
    raise SystemExit(main())
