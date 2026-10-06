"""The ROOT worker on a Pod (or on a worker box): runs one day's ROOT with the committed box script, exactly as the
orchestrator's root stage does, then ships the ROOT directory back and cleans up (SPEC-pod-day-runner.md).

Greg, 2026-09-29: "A100s immediately after to start running ROOT; when that day is done, clean up after the day by deleting
garbage and moving data to the big box to be read by other processes"; "The pod stays and brings the next people in".

Modes (python pod_agent.py <mode>; the Pod runs `serve`, a worker box is driven over SSM by frankie_box_pod_root.sh):
  serve     HTTP on :8081 behind the Runpod proxy, bearer POD_TOKEN: GET /status, POST /job, POST /clean, POST /reupload.
  work      (worker box) the job JSON from MAP_URL's "job" entry, started detached like POST /job.
  jobs      print every job's state.        clean / reupload   JOB=<id> (reupload: MAP_URL's "out" entry).
  job       internal: run one accepted job (a detached process, so a job outlives the HTTP server).

One job = one day, written as a job directory /opt/frankie-box/pod-agent/jobs/<ATTEMPT>/ (job.json with the presigned URLs,
mode 600, never served; state.json; agent.log; root.log):
  1 setup    the ROOT's commit as a clean worktree /opt/frankie-box/code/<commit>-pod-1/markets (the ROOT script refuses
             anything else) and the pinned producers checkout /opt/frankie-box/producers (lineage 2ebb8ce8, the ten
             producer files checked by sha256 as frankie_box_stage_producers.sh pins them);
  2 inputs   the day's sealed-ingest files placed at the SAME absolute paths as on the main box (so every path the ROOT
             records is the box's), each file's bytes and sha256 checked; THE DAY-FILE GATE: day-external.json must be
             there with its receipt and equal sha256, or the job stops before any calculation;
  3 root     deploy/aws/box/frankie_box_experiment_root.sh with the orchestrator's variables (INGESTION_RECEIPT(+_SHA256),
             DAY, DAY_ROLE, OUTPUT_ROOT=/opt/frankie-box/work/experiment-roots/<ATTEMPT>, DATA_WORKERS, DIGEST,
             FROZEN_SURVIVORS), pinned to the job's CPUs (affinity only): one day per Pod gets every CPU (Greg,
             2026-09-29), DATA_WORKERS a cap like Monday's 48, so the reader runs on all CPUs but the first;
  4 scratch  the day's ingest copy deleted (the box holds the originals); never the ROOT;
  5 ship     the ROOT directory whole + the Pod's evidence (job without URLs, root.log, host facts, receipts the ROOT
             wrote under /opt/frankie-box/receipts) as one zstd tar stream in 4 GiB chunks to presigned PUTs, then the
             manifest (every file's bytes + sha256). The box imports and verifies every file (frankie_box_pod_root.sh
             ACTION=import); only after that does the runner call clean, which deletes the ROOT from the Pod.
Nothing here holds an AWS or Runpod credential. No model call, no GPU use (the ROOT is CPU code).
"""
import contextlib
import fcntl
import hashlib
import hmac
import http.server
import json
import os
import re
import resource
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pod_transfer as T  # noqa: E402

PROTOCOL = '1'
ROOT = Path('/opt/frankie-box')
AGENT = ROOT / 'pod-agent'
JOBS = AGENT / 'jobs'
WORK = ROOT / 'work'
ROOTS = WORK / 'experiment-roots'
REPO = 'https://github.com/DavisAI1974/Markets.git'
JOB_SCHEMA = 'FRANKIE_POD_ROOT_JOB_V1'
ACTIVE = ('accepted', 'setup', 'inputs', 'root', 'finish', 'coordinate', 'scratch', 'ship')
CLEANABLE = ('uploaded', 'failed_setup', 'failed_inputs', 'failed_gate', 'failed_ship', 'interrupted', 'refused')
PRODUCERS_BRANCH = 'ccode/frankie-receiver-feed-20260916'
PRODUCERS_COMMIT = '2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134'
# the ten producer files at 2ebb8ce8, bytes and sha256 as frankie_box_stage_producers.sh pins them
PRODUCER_PINS = {
    'research/kalshi/frankie_raw_mbo_benchmark/a_memory_member_first_recalculation_20260828.py': (41528, '04194df484a69bb8d91a296e67145d34ada1a24ed1cf2aa1b4529565808369bb'),
    'research/kalshi/frankie_raw_mbo_benchmark/native_book_regime.py': (13097, 'aea1396df7cd838184de07fa029b4b2bf6d1e9434732b73f908538b4b7a62ab4'),
    'research/kalshi/frankie_raw_mbo_benchmark/native_clocks.py': (32462, 'f333efc43345eaecef375ed3b2cb8e19c5f8d4414a47b24e93bfef58b6e99f05'),
    'research/kalshi/frankie_raw_mbo_benchmark/native_flow_substrate.py': (29393, 'c904119f8e826e92578039182303425e0b6a0060f320c28955ebe85d8ecd8be0'),
    'research/kalshi/frankie_raw_mbo_benchmark/native_full_capture_adapter.py': (32392, 'd45febff374323d0ef1713078ac68775bad69d3f372f5d595503479ac52b59a4'),
    'research/kalshi/frankie_raw_mbo_benchmark/native_recognition.py': (12706, '0b279fda54cedcd3c812580da181356814afe4a35dffc52379d64814a716ac7c'),
    'research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py': (85491, '67996f3e1da9f6584bcca888eefe015c3b31508b9451335a76e2f49bfd7a8762'),
    'research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py': (12887, '8e0a8dd6111cf65dfd87ac153f72824c75fe372da55f24a7ea0c278517d58179'),
    'research/ng_exhaustion_mbo_v4_state_adapter_20260820.py': (41368, '4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce'),
    'research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json': (37242, '7ee754f1f9b080cdc5b7b68cf75829897d6216a1fadbb4b8a5ecd7b4f2133e06'),
}
GATE_ROLES = ('receipt', 'completion', 'journal', 'day_file', 'day_file_receipt')


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def log(job_dir, text):
    line = '%s %s\n' % (now(), text)
    with open(Path(job_dir) / 'agent.log', 'a', encoding='utf-8') as f:
        f.write(line)
    print(line, end='', flush=True)


def write_json(path, doc, mode=0o644):
    path = Path(path)
    tmp = path.with_name(path.name + '.pending')
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, mode)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(json.dumps(doc, indent=1, sort_keys=True, default=str) + '\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def save_path(job_id):
    return JOBS / job_id / 'save-request.json'


def request_save(job_id):
    """Request an orderly save; never kill a calculation or release its retained day."""
    path = save_path(job_id)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, 'w') as handle:
        handle.write(json.dumps(dict(job_id=job_id, requested=now())) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def check_save():
    path = os.environ.get('FRANKIE_LANE_STOP_FILE')
    if path and Path(path).exists():
        raise SystemExit(75)


def stop_job(job_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,96}', job_id):
        raise ValueError('invalid retained job identity')
    with lane_lock():
        job = read_json(JOBS / job_id / 'job.json')
        if job.get('workflow') != 'root-to-finish':
            raise ValueError('save applies only to the retained Linux AWS day')
        state = state_of(job_id) or {}
        if state.get('state') == 'day_complete':
            return 'already complete'
        request_save(job_id)
        return 'save requested; current calculation retains its full state before stopping'


@contextlib.contextmanager
def lane_lock():
    """Serialize Linux acceptance and resume, including the launcher handoff."""
    AGENT.mkdir(parents=True, exist_ok=True)
    with open(AGENT / 'lane.lock', 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def read_json(path):
    return json.loads(Path(path).read_bytes())


def state_of(job_id):
    try:
        return read_json(JOBS / job_id / 'state.json')
    except (OSError, ValueError):
        return None


def set_state(job_id, state, **fields):
    s = state_of(job_id) or dict(job_id=job_id)
    s.update(fields, state=state, updated=now())
    s.setdefault('history', []).append(dict(state=state, at=s['updated'], detail=fields.get('detail')))
    write_json(JOBS / job_id / 'state.json', s)
    return s


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def job_alive(job_id, s):
    """The job's own pid (state.json) or the pid its launcher recorded (the window before the job writes its state)."""
    lock = JOBS / job_id / 'run.lock'
    if lock.exists():
        with open(lock, 'a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(handle, fcntl.LOCK_UN)
    candidates = [s.get('pid')]
    try:
        candidates.append((JOBS / job_id / 'launcher.pid').read_text().strip())
    except OSError:
        pass
    for pid in candidates:
        if not alive(pid):
            continue
        try:
            args = Path('/proc/%s/cmdline' % int(pid)).read_bytes().split(b'\0')
            if any(Path(os.fsdecode(a)).name == 'pod_agent.py' for a in args) and \
                    [b'job', job_id.encode()] == args[-3:-1]:
                return True
        except (OSError, ValueError):
            pass
    return False


def git(*args, cwd=None, check=True):
    r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True,
                       env=dict(os.environ, GIT_TERMINAL_PROMPT='0', HOME=os.environ.get('HOME', '/root')))
    if check and r.returncode:
        raise RuntimeError('git %s: %s' % (' '.join(args), r.stderr.strip()[-400:]))
    return r.stdout.strip()


# ------------------------------------------------------------------------------------------------------- setup

def ensure_code(commit):
    """The ROOT's commit as a clean worktree under /opt/frankie-box/code (the ROOT script requires that prefix, a clean
    checkout and HEAD == MARKETS_SHA)."""
    code = ROOT / 'code' / ('%s-pod-1' % commit) / 'markets'
    base = ROOT / 'markets'
    if not (code / '.git').exists():
        if not (base / '.git').exists():
            raise RuntimeError('no %s (the setup script clones it)' % base)
        git('-C', str(base), 'fetch', '-q', '--depth', '1', 'origin', '--', commit)
        code.parent.mkdir(parents=True, exist_ok=True)
        git('-C', str(base), 'worktree', 'add', '-q', '--detach', str(code), commit)
    if git('-C', str(code), 'rev-parse', 'HEAD') != commit:
        raise RuntimeError('%s is not at %s' % (code, commit))
    if git('-C', str(code), 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError('%s is not clean' % code)
    return code


def ensure_producers():
    """The pinned producers checkout the ROOT loads the V4 adapter from (frankie_box_boss_session.PRODUCERS)."""
    base = ROOT / 'producers'
    if not (base / '.git').exists():
        git('clone', '-q', '--depth', '1', '--branch', PRODUCERS_BRANCH, REPO, str(base))
    if git('-C', str(base), 'rev-parse', 'HEAD') != PRODUCERS_COMMIT:
        git('-C', str(base), 'fetch', '-q', '--depth', '1', 'origin', PRODUCERS_COMMIT)
        git('-C', str(base), 'checkout', '-q', '--detach', PRODUCERS_COMMIT)
    rows, bad = [], []
    for rel, (size, sha) in PRODUCER_PINS.items():
        p = base / rel
        got = (p.stat().st_size, T.sha256_file(p)) if p.is_file() else (None, None)
        rows.append(dict(path=rel, bytes=got[0], sha256=got[1], pinned=got == (size, sha)))
        if got != (size, sha):
            bad.append(rel)
    if bad:
        raise RuntimeError('producer files differ from the pins: %s' % bad)
    return dict(commit=PRODUCERS_COMMIT, files=len(rows))


def host_facts():
    facts = dict(host=os.uname().nodename, cpus=os.cpu_count(), affinity=len(os.sched_getaffinity(0)), usable=len(usable_cpus()),
                 python=sys.version.split()[0], pod_id=os.environ.get('RUNPOD_POD_ID'))
    try:
        facts['cpu_max'] = Path('/sys/fs/cgroup/cpu.max').read_text().strip()
    except OSError:
        pass
    try:
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        facts['mem_total_kb'] = int(mem['MemTotal'].split()[0])
        facts['mem_available_kb'] = int(mem['MemAvailable'].split()[0])
    except (OSError, KeyError, ValueError):
        pass
    try:
        facts['os'] = dict(l.split('=', 1) for l in Path('/etc/os-release').read_text().splitlines() if '=' in l).get('PRETTY_NAME')
    except OSError:
        pass
    usage = shutil.disk_usage(ROOT if ROOT.exists() else '/')
    facts.update(disk_total=usage.total, disk_free=usage.free)
    return facts


def freeze_check(code):
    """The venv's pip freeze against the box's 75 pins (deploy/aws/box/frankie_box_venv_requirements.txt)."""
    req = code / 'deploy' / 'aws' / 'box' / 'frankie_box_venv_requirements.txt'
    if not req.is_file():
        return dict(checked=False, reason='no requirements file at this commit')
    want = sorted(l.strip() for l in req.read_text().splitlines() if l.strip() and not l.startswith('#'))
    r = subprocess.run([str(ROOT / 'venv' / 'bin' / 'python'), '-m', 'pip', 'freeze', '--disable-pip-version-check'],
                       capture_output=True, text=True)
    have = sorted(l.strip() for l in r.stdout.splitlines() if l.strip())
    return dict(checked=True, pins=len(want), missing=sorted(set(want) - set(have)), extra=sorted(set(have) - set(want)))


# -------------------------------------------------------------------------------------------------------- jobs

def validate(job):
    if job.get('workflow') != 'root-to-finish' or os.environ.get('RUNPOD_POD_ID'):
        raise ValueError('Pods and legacy ROOT shipping are retired; use the held Linux AWS CPU day workflow')
    if job.get('schema') != JOB_SCHEMA:
        raise ValueError('schema %s required' % JOB_SCHEMA)
    name, day, run = job.get('name', ''), job.get('day', ''), job.get('run', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,96}', name) or not name.startswith('%s-%s-a' % (run, day)):
        raise ValueError('name <run>-<day>-a<N> required')
    if not re.fullmatch(r'[0-9]{8}', day) or job.get('role') not in ('discovery', 'confirmation') \
            or job.get('digest') not in ('on', 'off') or not re.fullmatch(r'[0-9a-f]{40}', job.get('commit', '')):
        raise ValueError('day, role, digest and a full commit required')
    if not (isinstance(job.get('data_workers'), int) and 1 <= job['data_workers'] <= 63):
        raise ValueError('data_workers 1..63 required')
    ingest = Path(job.get('ingest_dir', ''))
    if ingest.parent != WORK or not re.fullmatch(r'ingest-[A-Za-z0-9_.-]+', ingest.name):
        raise ValueError('ingest_dir /opt/frankie-box/work/ingest-* required')
    roles = set()
    for f in job.get('inputs') or []:
        p = Path(f['path'])
        if '..' in p.parts or not p.is_absolute():
            raise ValueError('input path %s refused' % p)
        if f['role'] == 'frozen_survivors':
            if ROOT not in p.parents:
                raise ValueError('frozen survivors outside /opt/frankie-box refused')
        elif p.parent != ingest:
            raise ValueError('%s is not in the ingest directory' % p)
        if not f.get('parts') or sum(x['bytes'] for x in f['parts']) != f['bytes'] or not re.fullmatch('[0-9a-f]{64}', f['sha256']):
            raise ValueError('%s: parts, bytes and sha256 required' % p)
        roles.add(f['role'])
    missing = [r for r in GATE_ROLES if r not in roles]
    if missing:
        raise ValueError('the day-file gate: inputs %s missing (a day goes to a Pod only with its day file attached)' % missing)
    if job['role'] == 'confirmation' and 'frozen_survivors' not in roles:
        raise ValueError('a confirmation day needs the frozen survivor list')
    out = job.get('out') or {}
    if job.get('workflow') == 'root-to-finish':
        if not job.get('plan') or not job.get('mailbox') or job['data_workers'] != 15:
            raise ValueError('held Linux day requires plan, mailbox and exactly 15 workers')
        if job.get('where') != 'worker:i-0d17573dbce871520' or slots() != 1 or len(usable_cpus()) != 16:
            raise ValueError('held workflow requires the single 16-CPU Linux AWS lane')
        return
    if not out.get('chunk_urls') or not out.get('manifest_url'):
        raise ValueError('out.chunk_urls and out.manifest_url required')


def slots():
    return max(1, int(os.environ.get('POD_SLOTS') or 1))


def usable_cpus():
    """The CPUs this container may use: its affinity set, cut to the cgroup CPU quota when one is set (a container can
    see every host CPU in its affinity yet be limited to its vCPUs by cpu.max)."""
    cpus = sorted(os.sched_getaffinity(0))
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()[:2]
        if quota != 'max':
            cpus = cpus[:max(1, -(-int(quota) // int(period)))]
    except (OSError, ValueError):
        pass
    return cpus


def slot_cpus(slot):
    """Greg, 2026-09-29: one day per Pod, the day's ROOT gets ALL the Pod's CPUs (POD_SLOTS=1, the default); with more
    slots each gets an equal share."""
    cpus = usable_cpus()
    per = len(cpus) // slots()
    return cpus[slot * per:(slot + 1) * per]


def accept(job):
    """Validate, give the job a free slot, write its directory; (job_id, None) or (None, why)."""
    try:
        validate(job)
    except (ValueError, KeyError, TypeError) as e:
        return None, 'refused: %s' % e
    JOBS.mkdir(parents=True, exist_ok=True)
    job_id = job['name']
    if (JOBS / job_id).exists():
        return None, 'refused: job %s exists' % job_id
    busy = {}
    for d in JOBS.iterdir():
        if not d.is_dir() or d.name.startswith('.'):
            continue
        s = state_of(d.name)
        if read_json(d / 'job.json').get('workflow') == 'root-to-finish' and (s or {}).get('state') != 'day_complete':
            return None, 'refused: held Linux day %s must finish/resume on this lane first' % d.name
        if s and s.get('state') in ACTIVE and job_alive(d.name, s):
            busy[s.get('slot')] = s
            if s.get('day') == job['day']:
                return None, 'refused: a job for day %s runs (%s)' % (job['day'], d.name)
    free = [k for k in range(slots()) if k not in busy]
    if not free:
        return None, 'refused: no free slot (%d busy)' % len(busy)
    cpus = slot_cpus(free[0])
    # DATA_WORKERS is a cap, as on Monday's ROOT (48): the journal reader takes its workers from the process's CPU set
    # minus the first (frankie_journal_reader.worker_budget), so the ROOT pinned to N CPUs runs min(cap, N-1) readers
    d = JOBS / ('.accept-' + job_id)
    d.mkdir(exist_ok=True)
    write_json(d / 'job.json', job, mode=0o600)
    stamp = now()
    write_json(d / 'state.json', dict(job_id=job_id, state='accepted', day=job['day'], run=job['run'],
               slot=free[0], cpus=cpus, detail=None, updated=stamp,
               history=[dict(state='accepted', at=stamp, detail=None)],
               reader_workers=min(job['data_workers'], max(1, len(cpus) - 1))))
    os.rename(d, JOBS / job_id)
    directory = os.open(JOBS, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return job_id, None


def launch(job_id):
    d = JOBS / job_id
    out = open(d / 'agent.log', 'a')
    proc = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), 'job', job_id], stdout=out,
                            stderr=subprocess.STDOUT, start_new_session=True, cwd=str(d))
    (d / 'launcher.pid').write_text(str(proc.pid))       # never state.json: the job itself writes that
    return proc.pid


def renew_job(job_id, update, resume=False):
    """Refresh transport only; the job's day, source hashes, commit and lane stay fixed."""
    with lane_lock():
        d = JOBS / job_id
        job = read_json(d / 'job.json')
        if job.get('workflow') != 'root-to-finish':
            raise ValueError('renew/resume applies only to the Linux held-day workflow')
        if 'inputs' in update:
            old = job['inputs']
            new = update['inputs']
            def identity(inputs):
                return [dict(f, parts=[{k: v for k, v in p.items() if k != 'url'} for p in f['parts']])
                        for f in inputs]
            if identity(old) != identity(new):
                raise ValueError('renewal changed input identity; retained job not overwritten')
            job['inputs'] = new
            write_json(d / 'job.json', job, mode=0o600)
        write_json(d / 'mailbox.json', update['mailbox'], mode=0o600)
        if not resume:
            return None
        state = state_of(job_id) or {}
        if job_alive(job_id, state) or state.get('state') == 'day_complete':
            raise ValueError('a live/completed day cannot be resumed')
        for other in listing():
            if other['job_id'] != job_id and (other.get('pid_alive') or
                    (other.get('workflow') == 'root-to-finish' and other.get('state') != 'day_complete')):
                raise ValueError('another retained day owns this Linux lane')
        validate(job)
        save_path(job_id).unlink(missing_ok=True)
        return launch(job_id)


def public(job):
    """The job without its presigned URLs (the evidence copy that travels to the box)."""
    j = json.loads(json.dumps(job))
    for f in j.get('inputs') or []:
        for p in f.get('parts') or []:
            p.pop('url', None)
    j.pop('mailbox', None)
    j['out'] = dict(chunks=len((j.get('out') or {}).get('chunk_urls') or []))
    return j


def fetch_inputs(job_id, job):
    """Place every input at its box path; returns the list of paths this job created (only those are deleted later)."""
    d = JOBS / job_id
    created = []
    ingest = Path(job['ingest_dir'])
    if ingest.exists():
        log(d, 'the ingest directory %s exists: every file must already hold the expected bytes (never overwritten)' % ingest)
    else:
        ingest.mkdir(parents=True)
        created.append(str(ingest))
        set_state(job_id, 'inputs', created=created)
    for f in job['inputs']:
        check_save()
        p = Path(f['path'])
        if p.exists():
            if p.stat().st_size != f['bytes'] or T.sha256_file(p) != f['sha256']:
                raise ValueError('%s exists here with other bytes (never overwritten)' % p)
            log(d, 'input present: %s' % p)
            continue
        if not p.parent.exists():
            p.parent.mkdir(parents=True)
            created.append(str(p.parent))
        if str(p.parent) not in created:
            created.append(str(p))
        set_state(job_id, 'inputs', created=created)
        started = time.time()
        n, digest = T.get_parts_to_file(f['parts'], p)
        if n != f['bytes'] or digest != f['sha256']:
            raise ValueError('%s: %d bytes sha256 %s, expected %d %s' % (p, n, digest, f['bytes'], f['sha256']))
        log(d, 'input %s: %d bytes in %.0f s, sha256 ok' % (p.name, n, time.time() - started))
    return created


def gate(job):
    """The day file beside the sealed ingest with its receipt, sha256 equal (frankie_box_experiment.attached_day_file)."""
    ingest = Path(job['ingest_dir'])
    path, receipt = ingest / 'day-external.json', ingest / 'day-external-receipt.json'
    if not path.is_file() or not receipt.is_file():
        return 'no day file beside the sealed ingest'
    want = read_json(receipt).get('sha256')
    have = T.sha256_file(path)
    if read_json(path).get('day', read_json(path).get('trading_day')) != job['day']:
        return 'the attached 13-point file belongs to a different trading day'
    if have != want or (job.get('day_external_sha256') and have != job['day_external_sha256']):
        return 'day-external.json sha256 %s, its receipt %s, the box %s' % (have, want, job.get('day_external_sha256'))
    receipt_path = Path(job['ingestion_receipt'])
    if T.sha256_file(receipt_path) != job['ingestion_receipt_sha256']:
        return 'the ingestion receipt differs from its sha256'
    return None


def remove(paths):
    """Delete what this job created (never anything it found); a file's download leftovers (.part, .piece-*,
    .assembling) go with it."""
    freed = 0
    for p in sorted(paths, key=len, reverse=True):
        p = Path(p)
        if p.parent.is_dir():
            for extra in p.parent.glob(p.name + '.*'):
                if extra.is_file() and (extra.name.endswith(('.part', '.assembling')) or '.piece-' in extra.name):
                    freed += extra.stat().st_size
                    extra.unlink()
        if p.is_dir():
            freed += sum(x.stat().st_size for x in p.rglob('*') if x.is_file())
            shutil.rmtree(p)
        elif p.exists():
            freed += p.stat().st_size
            p.unlink()
    return freed


def ship(job_id, job):
    """Pack the ROOT directory and the Pod's evidence, upload the chunks, then the manifest."""
    d = JOBS / job_id
    s = state_of(job_id)
    if job.get('workflow') == 'root-to-finish':
        raise ValueError('Linux day evidence remains on its assigned box; never shipped')
    output = ROOTS / job['name']
    evidence = d / 'pod'
    if evidence.exists():
        shutil.rmtree(evidence)
    evidence.mkdir()
    write_json(evidence / 'job.json', public(job))
    for name in ('root.log', 'agent.log', 'setup.json'):
        if (d / name).is_file():
            shutil.copy2(d / name, evidence / name)
    receipts = ROOT / 'receipts'
    started = s.get('started_epoch') or 0
    new = [p for p in receipts.glob('*') if p.is_file() and p.stat().st_mtime >= started] if receipts.is_dir() else []
    if new:
        (evidence / 'receipts').mkdir()
        for p in new:
            shutil.copy2(p, evidence / 'receipts' / p.name)
    urls = job['out']['chunk_urls']

    def upload(index, path):
        if index >= len(urls):
            raise IOError('the stream needs more than the %d chunk slots given' % len(urls))
        t0 = time.time()
        digest = T.put_range(urls[index], path)
        log(d, 'chunk %d: %d bytes in %.0f s' % (index, os.stat(path).st_size, time.time() - t0))
        return digest

    writer = T.ChunkWriter(d / 'chunks', upload, int(job['out'].get('chunk_bytes') or T.CHUNK_BYTES))
    trees = [('pod', evidence)] + ([('root/' + job['name'], output)] if output.is_dir() else [])
    files, dirs = T.pack(trees, writer)
    s = state_of(job_id)
    manifest = dict(schema=T.TRANSFER_SCHEMA, name=job['name'], run=job['run'], day=job['day'], commit=job['commit'],
                    root_exit=s.get('root_exit'), root_seconds=s.get('root_seconds'), root_status=s.get('root_status'),
                    root_max_rss_kb=s.get('root_max_rss_kb'), host=s.get('host'), inputs_deleted=s.get('inputs_deleted'),
                    files=files, dirs=dirs, chunks=writer.chunks, packed_at=now())
    T.put_bytes(job['out']['manifest_url'], T.canonical(manifest).encode())
    return manifest


def run_job(job_id):
    # The lock also covers a launcher interrupted before launcher.pid was saved.
    with open(JOBS / job_id / 'run.lock', 'a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 1
        if (state_of(job_id) or {}).get('state') == 'day_complete':
            return 0
        job = read_json(JOBS / job_id / 'job.json')
        if job.get('workflow') == 'root-to-finish':
            os.environ['FRANKIE_LANE_STOP_FILE'] = str(save_path(job_id))
            for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                signal.signal(sig, lambda *_: request_save(job_id))
        try:
            check_save()
            return _run_job(job_id)
        except SystemExit as error:
            if error.code != 75:
                raise
            set_state(job_id, 'saved', detail='orderly save complete; original day, inputs and lane retained')
            return 75


def _run_job(job_id):
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)        # the server ignores SIGCHLD; a job must see its ROOT's exit code
    d = JOBS / job_id
    job = read_json(d / 'job.json')
    s = set_state(job_id, 'setup', pid=os.getpid(), started_epoch=time.time(), host=host_facts())
    created = []
    try:
        code = ensure_code(job['commit'])
        check_save()
        producers = ensure_producers()
        check_save()
        write_json(d / 'setup.json', dict(code=str(code), commit=job['commit'], producers=producers,
                                          freeze=freeze_check(code), host=host_facts()))
    except Exception as e:  # noqa: BLE001
        set_state(job_id, 'failed_setup', detail='%s: %s' % (type(e).__name__, e))
        return 1
    set_state(job_id, 'inputs')
    try:
        created = fetch_inputs(job_id, job)
        check_save()
        why = gate(job)
        if why:
            freed = 0 if job.get('workflow') == 'root-to-finish' else remove(created)
            set_state(job_id, 'failed_gate', detail=why, inputs_deleted=freed)
            return 1
    except Exception as e:  # noqa: BLE001
        freed = 0 if job.get('workflow') == 'root-to-finish' else remove(created)
        set_state(job_id, 'failed_inputs', detail='%s: %s' % (type(e).__name__, e), inputs_deleted=freed)
        return 1
    if job.get('workflow') == 'root-to-finish':
        # Retained Linux days use the common runner and never enter the legacy ship/clean path.
        try:
            return run_full_day(job_id, job, code)
        except (Exception, SystemExit) as error:
            if isinstance(error, SystemExit) and error.code == 75:
                raise
            set_state(job_id, 'failed_finish', detail='%s: %s; same-box claim retained for resume' % (
                type(error).__name__, error))
            return 1
    output = ROOTS / job['name']
    if output.exists():
        freed = remove(created)
        set_state(job_id, 'refused', detail='%s exists on this machine' % output, inputs_deleted=freed)
        return 1
    ROOTS.mkdir(parents=True, exist_ok=True)
    set_state(job_id, 'root', output_created=True, detail='starting the ROOT')   # from here the output is this job's
    env = dict(os.environ, MARKETS_SHA=job['commit'], CODE_ROOT=str(code), INGESTION_RECEIPT=job['ingestion_receipt'],
               INGESTION_RECEIPT_SHA256=job['ingestion_receipt_sha256'], DAY=job['day'], DAY_ROLE=job['role'],
               OUTPUT_ROOT=str(output), DATA_WORKERS=str(job['data_workers']), DIGEST=job['digest'],
               HOME=os.environ.get('HOME', '/root'))
    env.pop('POD_TOKEN', None)
    if job.get('frozen_survivors'):
        env['FROZEN_SURVIVORS'] = job['frozen_survivors']
    cpus = state_of(job_id)['cpus']
    set_state(job_id, 'root', detail='cpus %s' % cpus)
    started = time.time()
    with open(d / 'root.log', 'ab') as out:
        proc = subprocess.Popen(['bash', str(code / 'deploy' / 'aws' / 'box' / 'frankie_box_experiment_root.sh')], env=env,
                                stdout=out, stderr=subprocess.STDOUT, preexec_fn=lambda: os.sched_setaffinity(0, cpus))
        code_exit = proc.wait()
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    status = None
    if (output / 'calculations-receipt.json').is_file():
        status = read_json(output / 'calculations-receipt.json').get('status')
    set_state(job_id, 'scratch', root_exit=code_exit, root_seconds=round(time.time() - started, 1), root_status=status,
              root_max_rss_kb=rss)
    freed = remove(created)
    set_state(job_id, 'ship', inputs_deleted=freed, detail='the day\'s ingest copy deleted (%d bytes)' % freed)
    try:
        manifest = ship(job_id, job)
    except Exception as e:  # noqa: BLE001
        set_state(job_id, 'failed_ship', detail='%s: %s (the ROOT stays here; POST /reupload with fresh slots)' % (type(e).__name__, e))
        return 1
    set_state(job_id, 'uploaded', chunks=len(manifest['chunks']), files=len(manifest['files']),
              bytes=sum(f['bytes'] for f in manifest['files']), compressed=sum(c['bytes'] for c in manifest['chunks']),
              detail='waiting for the box import; clean after it verifies')
    return 0


def run_full_day(job_id, job, code):
    """Linux worker: common Run/queue day runner, one CPU-ledger booking through the last applicable stage."""
    import argparse
    sys.path.insert(0, str(code / 'deploy/aws/box'))
    import frankie_box_experiment as X
    import frankie_box_frankie_queue as Q
    import frankie_box_lane_state as LS
    import frankie_box_cores as C
    d = JOBS / job_id
    mailbox = d / 'mailbox.json'
    if not mailbox.exists():
        write_json(mailbox, job['mailbox'], mode=0o600)
    os.environ.update(FRANKIE_LANE_MAILBOX=str(mailbox), FRANKIE_LANE_OWNER=job['where'],
                      FRANKIE_LANE_RUN=job['run'], FRANKIE_LANE_DAY=job['day'],
                      FRANKIE_LANE_ATTEMPT=job_id)
    # Requests use the job state so the existing controller sees and services them.
    raw_request = LS.request
    def request(op, **payload):
        set_state(job_id, 'coordinate', detail=op)
        try:
            return raw_request(op, **(dict(run=job['run'], where=job['where'], day=job['day'], attempt=job_id) | payload))
        finally:
            set_state(job_id, 'finish', detail='continuing on the held day lane')
    LS.request = request
    recovered = LS.recover_request()
    if recovered and recovered['op'] == 'day_done' and recovered['result'].get('done'):
        set_state(job_id, 'day_complete', detail='recovered central completion; local artifacts retained')
        return 0
    lease = LS.request('day_resume')
    if lease.get('done'):
        set_state(job_id, 'day_complete', detail='central completion confirmed; local artifacts retained')
        return 0
    plan = job['plan']
    plan_path = X.RUNS / job['run'] / 'plan.json'
    if plan_path.exists() and json.loads(plan_path.read_bytes()) != plan:
        raise ValueError('different retained plan; not overwritten')
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(plan_path, plan)
    e = next(e for e in plan['days'] if e['day'] == job['day'])
    retained_cpus = (state_of(job_id) or {}).get('cpus')
    if not retained_cpus or len(retained_cpus) != 16:
        raise ValueError('retained 16-CPU lane identity is missing')
    entry = dict(run=job['run'], day=job['day'], settings=job['settings'], plan_sha256=X.plan_digest(plan),
                 cpus=retained_cpus)
    booking, reason = Q._book_slot(entry, 'remote-day', job['commit'])
    if booking is None:
        set_state(job_id, 'failed_finish', detail='CPU ledger: ' + str(reason))
        return 1
    set_state(job_id, 'finish', slot_booking=booking, cpus=C.held_booking(booking)[0]['cpus'])
    try:
        check_save()
        os.sched_setaffinity(0, retained_cpus)
        run = X.Run(argparse.Namespace(**dict(Q.SETTINGS, **job['settings'])), plan, code, job['commit'],
                    log=lambda message: log(d, message))
        run.slot_booking = booking
        for stage in ('fetch', 'ingest', 'external', 'root'):
            r = run.guarded(stage, e)
            if not r or r['status'] not in X.FINISHED:
                raise RuntimeError('%s: %s' % (stage, r))
        ok, facts = Q._finish_day(run, e, code, job['commit'], run.log)
        if not ok:
            raise RuntimeError('day finish: %s' % facts)
        root = run.receipt('root', job['day'])
        run.check_save()
        LS.boundary(job['day'], 'complete', brain=plan.get('brain') or X.BRAIN)
        receipts = sorted(run.dir.glob('days/%s/*.json' % job['day']))
        teacher_receipt = run.receipt_path('teacher', 'day-' + job['day'])
        if teacher_receipt.is_file():
            receipts.append(teacher_receipt)
        batch = run.batch_of(job['day'])
        if batch and batch.startswith('discovery-'):
            lessons_receipt = run.receipt_path('lessons', batch)
            if lessons_receipt.is_file():
                receipts.append(lessons_receipt)
        LS.request('day_done', calculations=root['calculations'], receipt_sha256=root['receipt_sha256'],
                   receipts=[LS.pack_file(p) for p in receipts])
        set_state(job_id, 'day_complete', calculations=root['calculations'], facts=facts,
                  detail='complete on original Linux box; ROOT and journal retained here')
        return 0
    except (Exception, SystemExit) as error:
        if isinstance(error, SystemExit) and error.code == 75:
            raise
        set_state(job_id, 'failed_finish', detail='%s: %s; same-box claim retained for resume' % (type(error).__name__, error))
        return 1
    finally:
        Q._release_slot(booking, 'remote day complete or stopped with retained receipts')


def reupload(job_id, out):
    s = state_of(job_id)
    if not s or s.get('state') not in ('failed_ship', 'interrupted', 'uploaded'):
        return 'refused: state %s' % (s and s.get('state'))
    d = JOBS / job_id
    job = read_json(d / 'job.json')
    job['out'] = out
    write_json(d / 'job.json', job, mode=0o600)
    set_state(job_id, 'ship', detail='reupload')
    try:
        manifest = ship(job_id, job)
    except Exception as e:  # noqa: BLE001
        set_state(job_id, 'failed_ship', detail='%s: %s' % (type(e).__name__, e))
        return 'failed: %s' % e
    set_state(job_id, 'uploaded', chunks=len(manifest['chunks']), files=len(manifest['files']),
              bytes=sum(f['bytes'] for f in manifest['files']), compressed=sum(c['bytes'] for c in manifest['chunks']))
    return 'uploaded'


def clean(job_id, verified):
    if read_json(JOBS / job_id / 'job.json').get('workflow') == 'root-to-finish':
        return 'refused: Linux day evidence stays on its assigned box'

    """After the box verified its import (or a failed job): the ROOT, the chunks and the evidence copy removed from this
    machine; the job's state and logs stay (small), its presigned URLs are dropped."""
    s = state_of(job_id)
    if not s or s.get('state') not in CLEANABLE:
        return 'refused: state %s' % (s and s.get('state'))
    if s.get('state') == 'uploaded' and not verified:
        return 'refused: an uploaded ROOT is removed only after the box import verified it (give verified)'
    d = JOBS / job_id
    job = read_json(d / 'job.json')
    mine = [str(ROOTS / job['name'])] if s.get('output_created') and (ROOTS / job['name']).exists() else []
    if s.get('state') == 'interrupted' and s.get('inputs_deleted') is None:
        # an interrupted job never reached its own scratch step: its inputs go now, unless another job of the day runs
        others = [x for x in (JOBS.iterdir() if JOBS.is_dir() else ()) if x.name != job_id
                  and (state_of(x.name) or {}).get('day') == s.get('day')
                  and (state_of(x.name) or {}).get('state') in ACTIVE]
        if not others:
            mine += [p for p in (s.get('created') or []) if Path(p).exists()]
    freed = remove(mine)
    freed += remove([str(p) for p in (d / 'chunks', d / 'pod') if p.exists()])
    write_json(d / 'job.json', public(job))
    set_state(job_id, 'cleaned', freed=freed, verified=verified, detail='removed from this machine after the move')
    return 'cleaned %d bytes' % freed


def listing():
    out = []
    for d in sorted(JOBS.iterdir()) if JOBS.is_dir() else ():
        if not d.is_dir() or d.name.startswith('.'):
            continue
        s = state_of(d.name) or {}
        pending = d / 'rpc-pending.json'
        rpc = read_json(pending) if pending.is_file() else {}
        if rpc.get('waiting') and rpc.get('uploaded', True) and job_alive(d.name, s):
            s = dict(s, state='coordinate')
        out.append({k: s.get(k) for k in ('job_id', 'day', 'run', 'state', 'updated', 'detail', 'slot', 'root_exit',
                                          'root_seconds', 'root_status', 'root_max_rss_kb', 'inputs_deleted', 'chunks',
                                          'bytes', 'compressed', 'freed', 'calculations', 'slot_booking')}
                   | dict(pid_alive=job_alive(d.name, s), save_requested=save_path(d.name).exists(),
                          workflow=read_json(d / 'job.json').get('workflow')))
    return out


def mark_interrupted():
    for d in JOBS.iterdir() if JOBS.is_dir() else ():
        if not d.is_dir() or d.name.startswith('.'):
            continue
        s = state_of(d.name)
        if s and s.get('state') in ACTIVE and not job_alive(d.name, s):
            set_state(d.name, 'interrupted', detail='the job process was gone at agent start (stage %s)' % s.get('state'))


# -------------------------------------------------------------------------------------------------------- HTTP

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'frankie-pod-root/' + PROTOCOL

    def _auth(self):
        token = os.environ.get('POD_TOKEN', '')
        got = self.headers.get('Authorization', '')
        if not token or not hmac.compare_digest(got.encode(), ('Bearer ' + token).encode()):
            self._send(401, dict(error='unauthorized'))
            return False
        return True

    def _send(self, code, doc):
        body = json.dumps(doc, sort_keys=True, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n)) if n else {}

    def log_message(self, fmt, *args):       # no URLs or tokens in any log
        pass

    def do_GET(self):
        if not self._auth():
            return
        if self.path.split('?')[0] == '/status':
            return self._send(200, dict(protocol=PROTOCOL, slots=slots(), host=host_facts(), jobs=listing(), at=now(),
                                        setup=read_json(AGENT / 'bootstrap.json') if (AGENT / 'bootstrap.json').is_file() else None))
        self._send(404, dict(error='unknown path'))

    def do_POST(self):
        if not self._auth():
            return
        path = self.path.split('?')[0]
        try:
            body = self._body()
        except ValueError:
            return self._send(400, dict(error='JSON body required'))
        if path == '/job':
            with lane_lock():
                job_id, why = accept(body)
                if job_id is None:
                    return self._send(409, dict(error=why))
                return self._send(200, dict(job_id=job_id, pid=launch(job_id), state=state_of(job_id)))
        if path == '/clean':
            return self._send(200, dict(result=clean(body.get('job_id', ''), body.get('verified'))))
        if path == '/reupload':
            job_id = body.get('job_id', '')
            s = state_of(job_id)
            if not s:
                return self._send(404, dict(error='no job'))
            pid = os.fork()
            if pid == 0:                                  # the upload runs in its own process; the server answers now
                os.setsid()
                try:
                    reupload(job_id, body.get('out') or {})
                finally:
                    os._exit(0)
            return self._send(200, dict(result='reupload started', pid=pid))
        self._send(404, dict(error='unknown path'))


def serve(port):
    AGENT.mkdir(parents=True, exist_ok=True)
    JOBS.mkdir(parents=True, exist_ok=True)
    mark_interrupted()
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)       # detached jobs and uploads are reaped automatically
    print('%s pod agent protocol %s on :%d, %d slot(s)' % (now(), PROTOCOL, port, slots()), flush=True)
    http.server.HTTPServer(('0.0.0.0', port), Handler).serve_forever()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'serve':
        serve(int(os.environ.get('POD_PORT') or 8081))
    elif mode == 'job':
        sys.exit(run_job(sys.argv[2]))
    elif mode == 'jobs':
        print('POD_ROOT_RESULT ' + json.dumps(dict(action='jobs', jobs=listing(), host=host_facts()), sort_keys=True, default=str))
    elif mode == 'work':
        JOBS.mkdir(parents=True, exist_ok=True)
        m = json.loads(T.get_bytes(os.environ['MAP_URL']))
        job = json.loads(T.get_bytes(m['job']['url']))
        with lane_lock():
            mark_interrupted()
            job_id, why = accept(job)
            if job_id is None:
                print('POD_ROOT_RESULT ' + json.dumps(dict(action='work', accepted=False, error=why)))
                sys.exit(3)
            print('POD_ROOT_RESULT ' + json.dumps(dict(action='work', accepted=True, job_id=job_id, pid=launch(job_id))))
    elif mode == 'clean':
        print('POD_ROOT_RESULT ' + json.dumps(dict(action='clean', result=clean(os.environ['JOB'], os.environ.get('VERIFIED')))))
    elif mode == 'reupload':
        m = json.loads(T.get_bytes(os.environ['MAP_URL']))
        print('POD_ROOT_RESULT ' + json.dumps(dict(action='reupload', result=reupload(os.environ['JOB'], m['out']))))
    elif mode in ('renew', 'resume'):
        job_id = os.environ['JOB']
        m = json.loads(T.get_bytes(os.environ['MAP_URL']))
        pid = renew_job(job_id, m, resume=mode == 'resume')
        print('POD_ROOT_RESULT ' + json.dumps(dict(action=mode, job_id=job_id, renewed=True, pid=pid)))
    elif mode == 'stop':
        print('POD_ROOT_RESULT ' + json.dumps(dict(action=mode, job_id=os.environ['JOB'],
                                                  result=stop_job(os.environ['JOB']))))
    else:
        raise SystemExit('mode serve | work | job <id> | jobs | clean | reupload | renew | resume | stop')


if __name__ == '__main__':
    main()
