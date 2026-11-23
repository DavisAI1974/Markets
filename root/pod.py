"""ROOT part 2 on a pod: one trade day per pod (Greg, 2026-11-16: the step runs go on pods, all four trade days at
the same time, with the helpers pinned to CPUs "so it isn't just one running by itself").

The pod fetches the code, the raw tape and its trade day's stored rows from the two PUBLIC repositories. No key is
on the pod and the pod writes nothing to git. It serves its output folder; the session fetches every file,
compares it with the fingerprint in its receipt (`root/pod_fetch.py`) and stores it.

What is different from the first launcher (`pod_run.sh`, which this replaces):
- The file server starts FIRST, before anything is installed or fetched, so a failed set-up can still be read.
- Every run names the code commit it runs. The pod checks that commit out first, so a corrected part can be run
  again on the same pod without starting a new one, and the receipt's commit is the one that ran.
- A run is asked for over the pod's own address (`/run?...`), with the word given to the pod when it was made, so
  no command has to be sent through Runpod once the pod is up.

    python3 pod.py <trade day YYYYMMDD> <Markets branch> [<commit> <job>]
    job:  calc:<calculation>,<calculation>,...   each its own helper, started together, each pinned to its own CPU
          ways                                   the chain links in six ways, peak by peak (root/chain_ways.py)
          legs                                   the trade legs of 6 pm to 8 pm on Oct 2 and Oct 17 (root/trade_legs.py)
          crypto_ng_tick                         the crypto and ng exhaustion calculation at the tick (the data run)
          moment:<received ns>                   one trade's own exhaustion graph, printed from the stored line of the
                                                 crypto_ng_tick data run (as steps and as a smooth curve, drawing
                                                 only): the program's trade under way at that moment
          trade:<number>                         the same for a trade of the program named by its number
          tape:<position on tape>                the same for one trade on the tape
          stretch:<from ns>-<to ns>              the 20-second line over one stretch of the trade day
          leg_renders                            one picture for every trade leg of the trade day: its price, the
                                                 crypto dipole line and the crypto exhaustion line on one clock
          leg_renders:<from ns>-<to ns>          the same for the trade legs whose first trade is inside the stretch
          rebuild                                the rows built again with the outside tables as they stand, then
                                                 flow_peak and outside_changes beside them (the changed pieces);
                                                 the unchanged calculations are not run again (Greg: no tests except
                                                 on changed pieces)
"""
from __future__ import annotations

import functools
import hmac
import http.server
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

PORT = 8000                                            # the port the pod serves its output folder on
WORK = Path('/root/work')
OUT, CODE, DATA, ROWS = WORK / 'out', WORK / 'code', WORK / 'data', WORK / 'rows'
GITHUB = 'https://github.com/DavisAI1974'
DATA_BRANCH, TAPE = 'ccr-349e2ffe-07p8od', 'data/nymex_mbo/ng_v0_oct2023'
OUTSIDE = 'data/outside/ng_oct2023/made'               # the made outside tables the rows pin (section G)
KEPT_BESIDE = ('calc-peak_story-', 'calc-quote_runs-')   # unchanged outputs outside_changes' check reads beside
#                                                          the rows
REBUILT = ('flow_peak', 'outside_changes')             # the calculations that changed (Greg: no tests except on
#                                                        changed pieces): the peaks without their ranked column, and
#                                                        the outside changes beside the rebuilt rows
LIBRARIES = ['databento==0.90.0', 'pyarrow==26.0.1', 'numpy==2.5.5', 'matplotlib', 'scipy']   # matplotlib for the
#                                                        renders, scipy for the smooth trade price curve
CALCULATIONS = ('refills', 'sweeps', 'chain_peaks', 'quote_peaks', 'outside_changes', 'together', 'leg_peaks',
                'resting', 'turn_peaks', 'move_steps')   # what a pod
#                                                      may be asked to run
MODEL_JOBS = {'ways': 'chain_ways'}                   # runs that rebuild their peak lines and pin their own helpers
ROW_JOBS = {'legs': 'trade_legs',                      # whole-trade-day programs that read the stored rows
            'dipole': 'dipole_peaks', 'renders': 'dipole_renders',
            'crypto_ng_tick': 'crypto_ng_tick',        # the crypto and ng exhaustion calculation at the tick:
#                                                        every trade at its own nanosecond (Greg, 2026-11-18)
            'leg_renders': 'leg_renders'}              # one picture for every trade leg (Greg, 2026-11-23)
#                                                        (a calc job may name them beside its
#                                                        calculations, so
#                                                        everything starts together, each on its own CPU)
PRINT_ONE = re.compile(r'(moment|trade|tape|stretch):([0-9]+(?:-[0-9]+)?)')   # print one graph from the stored line
LEGS_IN = re.compile(r'leg_renders:([0-9]+-[0-9]+)')   # the trade leg pictures of one stretch only (a first look)
COMMIT = re.compile(r'[0-9a-f]{40}')
ONE_THREAD = {name: '1' for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')}
ACCEPTED, REFUSED, BUSY = 202, 403, 409
busy = threading.Lock()


def say(line: str):
    with open(OUT / 'STATUS', 'a') as status:
        status.write(line + '\n')


def sh(*command, log: str, cwd=None):
    with open(OUT / log, 'a') as out:
        out.write('$ ' + ' '.join(command) + '\n')
        out.flush()
        subprocess.run(command, stdout=out, stderr=subprocess.STDOUT, cwd=cwd, check=True)


def set_up(day: str):
    """The libraries, the raw tape, and this trade day's stored rows."""
    sh(sys.executable, '-m', 'pip', 'install', '-q', *LIBRARIES, log='setup.log')
    sh('git', 'clone', '-q', '--depth', '1', '--filter=blob:none', '--sparse', '--branch', DATA_BRANCH,
       f'{GITHUB}/markets-data', str(DATA), log='setup.log')
    sh('git', '-C', str(DATA), 'sparse-checkout', 'set', TAPE, OUTSIDE, log='setup.log')
    sh('git', 'clone', '-q', '--depth', '1', '--single-branch', '--branch', f'root-rows-{day}',
       f'{GITHUB}/markets-data', str(ROWS), log='setup.log')
    (OUT / 'ROWS_COMMIT').write_text(subprocess.run(['git', '-C', str(ROWS), 'rev-parse', 'HEAD'],
                                                    capture_output=True, text=True, check=True).stdout)
    say('set up')


def run(day: str, commit: str, job: str):
    """One run at one named commit. Holds `busy` for as long as it lasts."""
    try:
        sh('git', '-C', str(CODE), 'fetch', '-q', '--depth', '1', 'origin', commit, log='runs.log')
        sh('git', '-C', str(CODE), 'checkout', '-q', commit, log='runs.log')
        (OUT / 'CODE_COMMIT').write_text(commit + '\n')
        environment = dict(os.environ, MARKETS_DATA=str(DATA), **ONE_THREAD)
        cpus = sorted(os.sched_getaffinity(0))
        if job in MODEL_JOBS:
            module = MODEL_JOBS[job]
            started = [(module, None, subprocess.Popen(
                [sys.executable, '-m', f'root.{module}', day, '--out', str(OUT)], cwd=CODE, env=environment,
                stdout=open(OUT / f'{module}.log', 'w'), stderr=subprocess.STDOUT))]
        elif job == 'rebuild':
            sh(sys.executable, '-m', 'root.run', 'build', day, '--tape', str(DATA / TAPE), '--out', str(OUT),
               '--outside', str(DATA / OUTSIDE), cwd=CODE, log='build.log')
            say(f'build passed at {commit}')
            for kept in sorted(ROWS.iterdir()):
                if kept.name.startswith(KEPT_BESIDE):
                    shutil.copy2(kept, OUT / kept.name)
            for name in REBUILT:                       # the changed pieces, in order: each reads the one before
                done = subprocess.run(
                    [sys.executable, '-m', 'root.run', 'calc', name, day, '--rows', str(OUT), '--out', str(OUT)],
                    cwd=CODE, env=environment, stdout=open(OUT / f'{name}.log', 'w'), stderr=subprocess.STDOUT,
                    preexec_fn=functools.partial(os.sched_setaffinity, 0, {cpus[0]}))
                say(f'{name} {"passed" if done.returncode == 0 else "FAILED"} on CPU {cpus[0]} at {commit}')
                if done.returncode:
                    break
            started = []
        elif PRINT_ONE.fullmatch(job):
            how, which = PRINT_ONE.fullmatch(job).groups()
            started = [('crypto_ng_tick_print', cpus[0], subprocess.Popen(
                [sys.executable, '-m', 'root.crypto_ng_tick', day, '--rows', str(ROWS), '--out', str(OUT),
                 f'--{how}', which], cwd=CODE, env=environment, stdout=open(OUT / 'crypto_ng_tick_print.log', 'w'),
                stderr=subprocess.STDOUT, preexec_fn=functools.partial(os.sched_setaffinity, 0, {cpus[0]})))]
        elif LEGS_IN.fullmatch(job):
            started = [('leg_renders', cpus[0], subprocess.Popen(
                [sys.executable, '-m', 'root.leg_renders', day, '--rows', str(ROWS), '--out', str(OUT), '--stretch',
                 LEGS_IN.fullmatch(job).group(1)], cwd=CODE, env=environment,
                stdout=open(OUT / 'leg_renders.log', 'w'), stderr=subprocess.STDOUT,
                preexec_fn=functools.partial(os.sched_setaffinity, 0, {cpus[0]})))]
        elif job in ROW_JOBS:
            module = ROW_JOBS[job]
            started = [(module, cpus[0], subprocess.Popen(
                [sys.executable, '-m', f'root.{module}', day, '--rows', str(ROWS), '--out', str(OUT)], cwd=CODE,
                env=environment, stdout=open(OUT / f'{module}.log', 'w'), stderr=subprocess.STDOUT,
                preexec_fn=functools.partial(os.sched_setaffinity, 0, {cpus[0]})))]
        else:                                          # every calculation its own helper, started together,
            started = []                               # each pinned to its own CPU
            for k, name in enumerate(job.split(':')[1].split(',')):
                cpu = cpus[k % len(cpus)]
                module = ROW_JOBS.get(name)
                command = ([sys.executable, '-m', 'root.run', 'calc', name] if module is None else
                           [sys.executable, '-m', f'root.{module}'])
                name = module or name
                started.append((name, cpu, subprocess.Popen(
                    command + [day, '--rows', str(ROWS), '--out', str(OUT)],
                    cwd=CODE, env=environment, stdout=open(OUT / f'{name}.log', 'w'), stderr=subprocess.STDOUT,
                    preexec_fn=functools.partial(os.sched_setaffinity, 0, {cpu}))))
        for name, cpu, process in started:
            where = 'on its own pinned helpers' if cpu is None else f'on CPU {cpu}'
            say(f'{name} {"passed" if process.wait() == 0 else "FAILED"} {where} at {commit}')
    except Exception as reason:
        say(f'FAILED before the run: {reason}')
    finally:
        say(f'finished {job} at {commit}')
        busy.release()


def allowed(job: str) -> bool:
    if (job in MODEL_JOBS or job in ROW_JOBS or job == 'rebuild' or PRINT_ONE.fullmatch(job)
            or LEGS_IN.fullmatch(job)):
        return True
    kind, _, names = job.partition(':')
    return kind == 'calc' and bool(names) and all(name in CALCULATIONS or name in ROW_JOBS
                                                  for name in names.split(','))


class Handler(http.server.SimpleHTTPRequestHandler):
    day = word = None

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != '/run':
            return super().do_GET()
        asked = {key: values[0] for key, values in urllib.parse.parse_qs(url.query).items()}
        commit, job = asked.get('commit', ''), asked.get('job', '')
        if not (self.word and hmac.compare_digest(asked.get('word', ''), self.word)
                and COMMIT.fullmatch(commit) and allowed(job)):
            return self.answer(REFUSED, 'refused')
        if not busy.acquire(blocking=False):
            return self.answer(BUSY, 'a run or the set-up is still going')
        threading.Thread(target=run, args=(self.day, commit, job)).start()
        self.answer(ACCEPTED, f'started {job} at {commit}')

    def answer(self, code: int, text: str):
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write((text + '\n').encode())


def main():
    day, branch, first = sys.argv[1], sys.argv[2], sys.argv[3:]
    OUT.mkdir(parents=True, exist_ok=True)
    Handler.day, Handler.word = day, os.environ.get('POD_WORD')
    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), functools.partial(Handler, directory=str(OUT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    say(f'serving; trade day {day}, branch {branch}')
    busy.acquire()
    try:
        set_up(day)
    except Exception as reason:
        say(f'FAILED in the set-up: {reason}')
        busy.release()
    else:
        if first and COMMIT.fullmatch(first[0]) and allowed(first[1]):
            run(day, first[0], first[1])
        else:
            busy.release()
    threading.Event().wait()                           # keep serving until the pod is deleted


if __name__ == '__main__':
    main()
