"""Disposable, non-result-bearing timing of the native cycle-0 step on a CLONED run directory.

What it does: runs the lawful Sunday host (the checkout named by --repository, at the failed
run's own boss_commit) against a scratch clone of the failed run directory. Because the
clone already holds the saved controller, principal_output and feedback stages, the host
skips Granite and the principal entirely and goes straight to the native training step,
which is the only thing this measures. Pure in-memory wrappers around _prepare,
forward_decision, Tensor.backward, Optimizer.step and NativeForecastLearner.step record
substage timestamps, process RSS/peak RSS and the exception TYPE AND MESSAGE (the message is
scratch diagnostics for the operator, never evidence). Nothing on disk in the repository is
modified, so the host's code-hash identity is the lawful one.

What it never does: call Granite or Frankie, read stdin credentials (stdin is /dev/null, so
the first credential request of cycle 1 stops the host), or touch the ORIGINAL run
directory. Verify the original afterwards by hash; the clone is garbage when done.

Thread count: with --keep-checkpoint the clone's seed checkpoint is restored and the thread
count MUST equal the one bound in it (4 for the failed run). With --fresh-checkpoint the
clone's training.sqlite and training-witnesses are removed first, so the host creates a new
seed checkpoint (same seed, same weights) under the requested thread count; that is the
8-vs-16 comparison path on the restored host.

    python benchmark_native_step_disposable.py --repository E:/Codex/.../Markets \
        --configuration <scratch-config.json> --threads 4 --keep-checkpoint --log <scratch>.jsonl
"""
import argparse
import ctypes
import functools
import io
import json
import os
from pathlib import Path
import sys
import threading
import time


def _rss():
    if os.name != 'nt':
        try:
            values = {}
            for line in Path('/proc/self/status').read_text().splitlines():
                key, _, tail = line.partition(':')
                if key in ('VmRSS', 'VmHWM'):
                    values[key] = int(tail.split()[0]) * 1024
            return dict(rss=values.get('VmRSS'), peak_rss=values.get('VmHWM'))
        except OSError:
            return {}

    class Counters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
                    ('PrivateUsage', ctypes.c_size_t)]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    # The pseudo-handle is (HANDLE)-1; left untyped, ctypes truncates it to a 32-bit int and
    # GetProcessMemoryInfo fails silently, which is exactly how runtime_resource_probe lost
    # every process field on Windows. Type both sides.
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return {}
    return dict(rss=int(counters.WorkingSetSize), peak_rss=int(counters.PeakWorkingSetSize),
                private=int(counters.PrivateUsage), peak_pagefile=int(counters.PeakPagefileUsage))


class Log:
    def __init__(self, path):
        self.path = Path(path)
        self.started = time.perf_counter()
        self.lock = threading.Lock()

    def write(self, stage, **values):
        record = dict(stage=stage, t=round(time.perf_counter() - self.started, 3), unix=time.time(), **_rss(), **values)
        with self.lock, self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, default=str) + '\n')
        print('BENCH ' + json.dumps(record, default=str), flush=True)


def _wrap(log, owner, name, stage):
    original = getattr(owner, name)
    import inspect

    if inspect.iscoroutinefunction(original):
        @functools.wraps(original)
        async def wrapped(*args, **kwargs):
            log.write(stage + '_start')
            try:
                result = await original(*args, **kwargs)
            except BaseException as error:
                log.write(stage + '_failed', error_type=type(error).__name__, error_message=str(error)[:500])
                raise
            log.write(stage + '_complete')
            return result
    else:
        @functools.wraps(original)
        def wrapped(*args, **kwargs):
            log.write(stage + '_start')
            try:
                result = original(*args, **kwargs)
            except BaseException as error:
                log.write(stage + '_failed', error_type=type(error).__name__, error_message=str(error)[:500])
                raise
            log.write(stage + '_complete')
            return result
    setattr(owner, name, wrapped)


def _wrap_class(log, owner, prefix, skip=()):
    for name, member in list(vars(owner).items()):
        if callable(member) and not name.startswith('__') and name not in skip:
            _wrap(log, owner, name, prefix + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--threads', type=int, required=True)
    parser.add_argument('--log', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--keep-checkpoint', action='store_true')
    group.add_argument('--fresh-checkpoint', action='store_true')
    parser.add_argument('--sample-seconds', type=float, default=2.0)
    parser.add_argument('--reviewed-repository', default=None,
                        help='checkout of the reviewed recovery branch whose Pod identity and sidecar-tolerant '
                             'lineage verifier are applied IN MEMORY to the scratch modules (benchmark only)')
    args = parser.parse_args()

    repository = Path(args.repository).resolve()
    sys.path.insert(0, str(repository))
    os.chdir(repository)
    configuration = json.loads(Path(args.configuration).read_bytes())
    run_directory = Path(configuration['run_directory'])
    if 'scratchpad' not in run_directory.as_posix() and 'bench' not in run_directory.name:
        raise SystemExit('refusing: run_directory does not look like a disposable clone')
    if args.fresh_checkpoint:
        (run_directory / 'training.sqlite').unlink(missing_ok=True)
        for witness in (run_directory / 'training-witnesses').glob('*'):
            witness.unlink()
    log = Log(args.log)

    import torch
    torch.set_num_threads(args.threads)
    log.write('driver_start', threads=torch.get_num_threads(), interop=torch.get_num_interop_threads(),
              torch=torch.__version__, python=sys.version.split()[0], cpus=os.cpu_count(),
              keep_checkpoint=args.keep_checkpoint, repository=str(repository))

    from research.kalshi.frankie_boss import native_forecast_learning, context_session, b1_reasoner, boss_training_checkpoint
    _wrap(log, native_forecast_learning.NativeForecastLearner, 'step', 'learner_step')
    _wrap(log, context_session.ContextSessionRunner, '_prepare', 'prepare')
    _wrap(log, b1_reasoner.B1Reasoner, 'forward_decision', 'forward')
    _wrap(log, torch.Tensor, 'backward', 'backward')
    _wrap(log, torch.optim.Optimizer, 'step', 'optimizer_step')
    _wrap(log, boss_training_checkpoint.BossTrainingCheckpoint, 'apply_completed', 'apply_completed')

    stop = threading.Event()

    def sampler():
        while not stop.wait(args.sample_seconds):
            log.write('sample')
    threading.Thread(target=sampler, daemon=True).start()

    sys.stdin = io.TextIOWrapper(open(os.devnull, 'rb'))  # no credential can ever be read
    from research.kalshi.frankie_boss.operations import run_actual_sunday as actual
    # The host never prints exception text; for a scratch benchmark we want the innermost
    # failing host method and its message, so wrap every method the host class defines.
    _wrap_class(log, actual.ActualHost, 'host.', skip=('progress', 'save', 'load', 'phase', 'recovery_progress', 'encoding_options'))
    from research.kalshi.frankie_boss import sunday_execution, feedback_cycle, frankie_principal_adapter
    _wrap_class(log, sunday_execution.SundayExecution, 'execution.')
    _wrap_class(log, feedback_cycle.CycleCoordinator, 'coordinator.', skip=('_save', '_load', '_observe'))
    _wrap_class(log, frankie_principal_adapter.FrankiePrincipalAdapter, 'principal.')
    # Scratch diagnostics only: the principal attestation compares an opaque config hash, so log
    # the material it hashes (paths, commits, file hashes; never prompt text or credentials) and the
    # retained hash it is compared against, to pin which field a cloned run directory changes.
    principal_class = frankie_principal_adapter.FrankiePrincipalAdapter
    original_config_hash = principal_class._config_hash
    original_request = principal_class._request

    def logged_config_hash(self):
        material = {'receiver_root': str(self.receiver_root), 'receiver_commit': self.receiver_commit,
                    'python': self.python, 'preparation': {k: str(v) for k, v in self.preparation.items()},
                    'render': {k: str(v) for k, v in self.render.items()},
                    'protected_files': self.protected_files, 'section_evidence': self.section_evidence,
                    'feedback_contract_keys': sorted(self.feedback_contract) if isinstance(self.feedback_contract, dict) else None}
        digest = original_config_hash(self)
        log.write('principal_config_material', config_hash=digest, material=material)
        return digest

    def logged_request(self, request_id, attachment):
        log.write('principal_attachment_config_hash', retained=attachment.get('config_hash'))
        return original_request(self, request_id, attachment)
    principal_class._config_hash = logged_config_hash
    principal_class._request = logged_request
    if args.reviewed_repository:
        # BENCHMARK-ONLY, in memory: apply the two reviewed recovery semantics from the reviewed
        # branch onto the 050c5056 scratch modules without touching that checkout's bytes.
        # 1. The retained Pod identity of the aa12fd09 port (the scratch lineage still pins the
        #    retired Pod, so its own service check can never pass against the real readiness dir).
        # 2. The recovery-only lineage verifier, which differs from the lawful one by exactly the
        #    sidecar liveness predicate (journal_prefix_snapshot._sidecars). Every other check runs
        #    unchanged. Nothing is skipped; the same checks run with the reviewed values.
        import importlib.util
        import re
        reviewed = Path(args.reviewed_repository).resolve() / 'research' / 'kalshi' / 'frankie_boss'
        lifecycle_text = (reviewed / 'granite_retained_lifecycle.py').read_text(encoding='utf-8')
        pod_id = re.search(r"^POD_ID = '([A-Za-z0-9]+)'", lifecycle_text, re.M).group(1)
        from research.kalshi.frankie_boss import granite_retained_lifecycle as lifecycle
        log.write('reviewed_semantics_applied_in_memory', scratch_pod_id=lifecycle.POD_ID, reviewed_pod_id=pod_id)
        lifecycle.POD_ID = pod_id
        # Load the reviewed helper as a submodule of the scratch package so its relative import of
        # journal_prefix_snapshot resolves to the scratch checkout's identical lawful file.
        spec = importlib.util.spec_from_file_location(
            'research.kalshi.frankie_boss.source_lineage_resume_reviewed', reviewed / 'source_lineage_resume.py')
        helper = importlib.util.module_from_spec(spec)
        helper.__package__ = 'research.kalshi.frankie_boss'
        spec.loader.exec_module(helper)

        def source_lineage(self, source, ingestion):
            return helper.verify_closed_source_lineage(self, source, ingestion,
                                                       verified_json=actual.verified_json, verified=actual.verified)
        actual.ActualHost.source_lineage = source_lineage
        _wrap(log, actual.ActualHost, 'source_lineage', 'host.source_lineage_reviewed')
    sys.argv = ['run_actual_sunday', '--configuration', args.configuration]
    try:
        code = actual.main()
    finally:
        stop.set()
        log.write('driver_end')
    log.write('host_exit', code=code)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
