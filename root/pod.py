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
          models                                 the chain link models for this trade day (pins its own helpers)
"""
from __future__ import annotations

import functools
import hmac
import http.server
import os
import re
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
LIBRARIES = ['databento==0.90.0', 'pyarrow==26.0.1', 'numpy==2.5.5']
MODEL_LIBRARIES = ['scikit-learn==1.9.1', 'scipy==1.18.1']   # installed only when the models are asked for
CALCULATIONS = ('refills', 'sweeps', 'chain_peaks', 'quote_peaks', 'outside_changes', 'together')   # what a pod
#                                                      may be asked to run
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
    sh('git', '-C', str(DATA), 'sparse-checkout', 'set', TAPE, log='setup.log')
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
        if job == 'models':
            sh(sys.executable, '-m', 'pip', 'install', '-q', *MODEL_LIBRARIES, log='runs.log')
            started = [('chain_models', None, subprocess.Popen(
                [sys.executable, '-m', 'root.chain_models', day, '--out', str(OUT)], cwd=CODE, env=environment,
                stdout=open(OUT / 'chain_models.log', 'w'), stderr=subprocess.STDOUT))]
        else:                                          # every calculation its own helper, started together,
            started = []                               # each pinned to its own CPU
            for k, name in enumerate(job.split(':')[1].split(',')):
                cpu = cpus[k % len(cpus)]
                started.append((name, cpu, subprocess.Popen(
                    [sys.executable, '-m', 'root.run', 'calc', name, day, '--rows', str(ROWS), '--out', str(OUT)],
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
    if job == 'models':
        return True
    kind, _, names = job.partition(':')
    return kind == 'calc' and bool(names) and all(name in CALCULATIONS for name in names.split(','))


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
