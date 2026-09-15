"""New integration check for one-pass conversion and explicit CPU affinity."""
from functools import partial
from pathlib import Path
import os
import sys
import tempfile
HERE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(HERE),str(HERE/'tests'),str(HERE.parents[2])]
from test_single_pass_finalization import fixture
from journal_stack_execution import MigratingConformanceReader
from single_pass_finalization import finalize_snapshot
from compact_journal import CompactReader

def main():
    available=sorted(os.sched_getaffinity(0))
    if len(available)<2:
        raise ValueError('worker CPU required')
    with tempfile.TemporaryDirectory() as directory:
        source,scope,state,expected,physical=fixture(directory,20)
        target=Path(directory)/'compact.sqlite'
        progress=[]
        factory=partial(MigratingConformanceReader,output=target,
                        worker_cpus=available[1:3],emit=progress.append)
        result=finalize_snapshot(source,scope,state,expected_scope_hash=scope.genesis_hash(),
            expected_state_hash=state['state_hash'],expected_physical_sha256=physical,
            reader_factory=factory)
        assert result.completion==expected and result.checkpoint==state
        assert progress[-1]['entries']==40
        assert result.worker_cpu_seconds>0
        with CompactReader(target,expected_count=40,expected_head_hash=state['journal_hash']) as reader:
            assert len(list(reader.entries()))==40
    print('New one-pass conversion, exact conformance and CPU affinity integration passed.')

if __name__=='__main__':
    main()
