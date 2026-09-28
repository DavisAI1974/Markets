"""The pinned producers for the digest tests, loaded as the session loads them (frankie_box_bedrock.load_producers:
markets first, then the checkout at the pin). The digest sources prepare layers through frankie_box_projection, whose
import chain reaches the producers' native_row_sink, so a test process needs the checkout on its path as the box's
session process has it. The checkout is deploy/aws/box/producers_checkout.sh's worktree (or FRANKIE_BOX_PRODUCERS)."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BOX = ROOT / 'deploy/aws/box'


def load():
    if str(BOX) not in sys.path:
        sys.path.insert(0, str(BOX))
    import frankie_box_bedrock
    path = frankie_box_bedrock.default_producers()
    if not path.is_dir():
        raise RuntimeError(f'the pinned producers checkout is missing at {path}: run deploy/aws/box/producers_checkout.sh')
    frankie_box_bedrock.producers_commit(path)
    return frankie_box_bedrock.load_producers(path)


def env():
    """The environment of a fresh test subprocess: markets, then the pinned checkout, on its import path."""
    path = load()
    tests = str(Path(__file__).resolve().parent)
    return dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(path), tests] + [p for p in [os.environ.get('PYTHONPATH')] if p]))


class InProcessWorkers:
    """frankie_box_projection.Workers' interface run in this process, in order: the projection pool requires the box's
    sixteen designated physical cores (it pins fourteen helpers to cpus 2-15), which a CI runner or a dev container does
    not have. The functions submitted are the same; only where they run differs."""

    def __init__(self, configuration=None):
        import frankie_box_projection
        frankie_box_projection._STATE = configuration

    def ordered(self, function, items):
        for item in items:
            yield function(item)

    def receipt(self):
        return dict(in_process=True, reason='fewer than the sixteen designated physical cores on this test host')

    def close(self):
        pass


def sixteen_cores():
    try:
        return len({((root / 'physical_package_id').read_text(), (root / 'core_id').read_text())
                    for root in (Path('/sys/devices/system/cpu') / ('cpu%d' % cpu) / 'topology' for cpu in range(16))}) == 16
    except OSError:
        return False


def prepare_test_host():
    """The pinned producers loaded; on a host without the box's sixteen cores, the projection pool in process (see
    InProcessWorkers); and a 1 GiB disk reserve for the parallel table writer (the box keeps 32 GiB; a test scratch
    filesystem is smaller than that), set through the writer's FRANKIE_DIGEST_DISK_RESERVE setting."""
    os.environ.setdefault('FRANKIE_DIGEST_DISK_RESERVE', str(1 << 30))
    load()
    if not sixteen_cores():
        import frankie_box_projection
        frankie_box_projection.Workers = InProcessWorkers
