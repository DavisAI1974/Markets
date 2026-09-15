"""Run the authorized combined journal conversion on an existing pinned bundle."""
import argparse
from dataclasses import asdict
from functools import partial
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).parent/'parallel_source'))
from verify_snapshot import CODE_FILES, REQUIRED, EXPECTED, load_code, verify_files, write_once, sha256, PACKAGE

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    bundle, output = args.bundle_dir.resolve(), args.output_dir.resolve()
    if output == bundle or output.is_relative_to(bundle) or bundle.is_relative_to(output):
        raise ValueError('separate output required')
    output.mkdir(parents=True, exist_ok=False)
    def emit(value):
        value = dict(value, unix=time.time())
        print(json.dumps(value, sort_keys=True), flush=True)
        with (output/'progress.jsonl').open('a') as stream:
            stream.write(json.dumps(value,sort_keys=True)+'\n')
        (output/'progress.json').write_text(json.dumps(value,sort_keys=True))
    try:
        material = json.loads((bundle/'bundle-manifest.json').read_bytes())
        if not set(REQUIRED).issubset(material['files']):
            raise ValueError('mandatory bundle identities missing')
        # Finalizer verifies the physical source before and after. All remaining
        # inputs are verified here; no redundant full logical pass is started.
        small = dict(material, files={k:v for k,v in material['files'].items() if k!='source.sqlite'})
        verify_files(bundle, small, tuple(k for k in REQUIRED if k!='source.sqlite'), emit)
        checkpoint_raw = (bundle/'checkpoint.json').read_bytes()
        checkpoint_receipt = json.loads((bundle/'checkpoint-receipt.json').read_bytes())
        if hashlib.sha256(checkpoint_raw).hexdigest()!=EXPECTED['sha256'] or any(
                checkpoint_receipt.get(k)!=v for k,v in EXPECTED.items()):
            raise ValueError('independent terminal checkpoint differs')
        load_code(bundle/'code', output/'runtime')
        # Additional verifier modules use exactly the retained producer modules;
        # neither source identity nor adapter calculations are replaced.
        for name in ('c15_builder','c15_journal','c15_registry','causal_prefix_records',
                     'mbo_resume_state','source_conformance'):
            sys.modules[name] = importlib.import_module(PACKAGE+'.'+name)
        journal = sys.modules['c15_journal']
        selected = importlib.import_module(PACKAGE+'.selected_source_scope')
        manifest = json.loads((bundle/'manifest.json').read_bytes())
        scope = selected.source_scope(manifest,expected_manifest_hash=manifest['manifest_hash'])
        state = journal.unpack(json.loads(checkpoint_raw))
        if (scope.genesis_hash()!=EXPECTED['scope_hash'] or state['state_hash']!=EXPECTED['state_hash']
                or state['journal_count']!=EXPECTED['journal_count']
                or state['journal_hash']!=EXPECTED['journal_hash']):
            raise ValueError('terminal bindings differ')
        from single_pass_finalization import finalize_snapshot
        from journal_stack_execution import MigratingConformanceReader, pin_cpu
        available = sorted(os.sched_getaffinity(0))
        if len(available)<2:
            raise ValueError('dedicated parent and worker CPU capacity required')
        parent_cpu, worker_cpus = available[0],available[1:]
        pin_cpu(parent_cpu)
        emit(dict(phase='cpu_dedication',parent_cpu=parent_cpu,worker_cpus=worker_cpus,
                  max_inflight_blocks=2*len(worker_cpus),records=0,entries=0,total=114054,percent=0.0))
        factory = partial(MigratingConformanceReader, output=output/'journal.compact.sqlite',
                          worker_cpus=worker_cpus,emit=emit)
        result = finalize_snapshot(bundle/'source.sqlite',scope,state,
            expected_scope_hash=EXPECTED['scope_hash'],expected_state_hash=EXPECTED['state_hash'],
            expected_physical_sha256=material['files']['source.sqlite']['sha256'],
            reader_factory=factory)
        expected = dict(schema='BOSS_SOURCE_CONFORMANCE_V1',scope_kind=scope.kind.value,
            scope_hash=EXPECTED['scope_hash'],record_count=57027,member_counts=(57027,),
            group_count=43569,source_prefix_hash=EXPECTED['source_prefix_hash'],
            journal_count=EXPECTED['journal_count'],journal_hash=EXPECTED['journal_hash'],
            builder_state_hash=EXPECTED['state_hash'])
        if asdict(result.completion)!=expected or result.checkpoint!=state:
            raise ValueError('final conformance result differs')
        (output/'verified-checkpoint.c15.json').write_bytes(checkpoint_raw)
        receipt=dict(schema='FRANKIE_COMBINED_JOURNAL_EXECUTION_V1',status='verified',
            gate_authority=False,model_calls=0,source_records=57027,journal_entries=114054,
            conformance_passes=1,completion=asdict(result.completion),
            completion_digest=result.completion.digest,checkpoint_sha256=EXPECTED['sha256'],
            source_snapshot_sha256=result.physical_sha256,
            compact_sha256=sha256(output/'journal.compact.sqlite'),
            compact_bytes=(output/'journal.compact.sqlite').stat().st_size,
            parent_cpu=parent_cpu,worker_cpus=worker_cpus,
            parent_cpu_seconds=result.cpu_seconds,worker_cpu_seconds=result.worker_cpu_seconds,
            wall_seconds=result.wall_seconds,code_commit=os.environ.get('GITHUB_SHA'),
            github_run_id=os.environ.get('GITHUB_RUN_ID'),
            model_input_reduction='Sunday host remains configured for stacked_v1; no inference in this job')
        write_once(output/'verification-receipt.json',receipt)
        emit(dict(phase='verified',entries=114054,total=114054,percent=100.0,completion_digest=result.completion.digest))
    except BaseException as error:
        write_once(output/'verification-failure.json',dict(error_type=type(error).__name__,
                   message=str(error),gate_authority=False,unix=time.time()))
        raise

if __name__=='__main__':
    main()
