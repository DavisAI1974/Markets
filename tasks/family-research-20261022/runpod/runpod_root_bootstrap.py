"""Set up pinned imports and same-family shared memory before starting ROOT."""
import runpy
import sys
from multiprocessing import shared_memory
from pathlib import Path
from types import SimpleNamespace

entry = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(entry.parent))
from frankie_box_bedrock import load_producers

load_producers(Path("/opt/frankie-box/producers"))

if sys.version_info < (3, 13):
    import frankie_box_parallel_evidence as evidence

    def encoder_shared_memory(*, track=True, **kwargs):
        # ROOT and its spawned encoder share one resource tracker. On 3.12
        # its registration is a set, and the creating encoder still unlinks.
        return shared_memory.SharedMemory(**kwargs)

    evidence.shared_memory = SimpleNamespace(SharedMemory=encoder_shared_memory)

sys.argv = [str(entry), *sys.argv[2:]]
runpy.run_path(str(entry), run_name="__main__")
