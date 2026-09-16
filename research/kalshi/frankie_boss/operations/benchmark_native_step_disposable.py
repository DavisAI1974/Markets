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
    for name, member in list(vars(actual.ActualHost).items()):
        if callable(member) and not name.startswith('__'):
            _wrap(log, actual.ActualHost, name, 'host.' + name)
    sys.argv = ['run_actual_sunday', '--configuration', args.configuration]
    try:
        code = actual.main()
    finally:
        stop.set()
        log.write('driver_end', **_rss())
    log.write('host_exit', code=code)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
