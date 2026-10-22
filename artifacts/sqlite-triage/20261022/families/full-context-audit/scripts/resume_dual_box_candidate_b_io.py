"""Resume the existing candidate using actual available RAM and physical CPU slots.

Default: plan only. --execute runs missing jobs; never builds raw inputs.
Only the stopped candidate is supported. No instance lifecycle calls or monitors.
"""
import argparse
import csv
import dataclasses
import hashlib
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import time
import uuid
from dual_box_support import (assigned_cohorts, assignment_digest, announce_ready,
    require_a_ready, publish_b, receive_b, reconcile_keys, publish_failure)

GIB = 1024**3
BASE = pathlib.Path('/opt/frankie-box/work/family-research-20261022')
NEURAL = ['neural_tree', 'residual_mlp', 'tabm_ensemble']


def readrows(path):
    if not path.exists():
        return []
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def savejson(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temp, path)


def key(row):
    return tuple(str(row[k]) for k in ['outcome', 'horizon_s', 'fold', 'model'])


def stem(t):
    return t[0].replace('_', '-') + '-h' + t[1] + '-fold' + t[2]


def job_id(t, kind, model):
    return stem(t) + '--' + kind + '--' + hashlib.sha256(model.encode()).hexdigest()[:12]


def expected_models(t, groups):
    binary = t[0] == 'first_observed_family_within_h'
    core = (['training_frequency', 'ridge100', 'evotrees_depth3', 'evotrees_depth5']
        if binary else ['zero_change', 'training_mean', 'ridge100',
            'evotrees_depth3', 'evotrees_depth5', 'evotrees_mae',
            'evotrees_q10', 'evotrees_q90'])
    return (core + ['dropgroup:' + g for g in groups]
        + ([] if binary else ['drop_history']), NEURAL[:])


def committed(folder, kind, t, model, serial=False):
    """Recover coherent output even if shutdown preceded the coordinator receipt."""
    try:
        receipt = folder / 'job_receipt.json'
        if receipt.exists() and json.loads(receipt.read_text()).get('returncode') != 0:
            return False
        prefix = 'model' if kind == 'core' else 'neural'
        wanted = tuple(t) + (model,)
        metrics = readrows(folder / (prefix + '_metrics.csv'))
        if not serial and len(metrics) != 1:
            return False
        matched = [r for r in metrics if key(r) == wanted]
        if len(matched) != 1:
            return False
        for row in readrows(folder / (prefix + '_errors.csv')):
            if not serial or not all(k in row for k in ['outcome','horizon_s','fold','model']) or key(row) == wanted:
                return False
        pred = [r for r in readrows(folder / (prefix + '_predictions.csv'))
            if key(r) == wanted]
        if len(pred) != int(matched[0]['test_n']) or not pred:
            return False
        if len({r['sample_id'] for r in pred}) != len(pred):
            return False
        if not all(math.isfinite(float(r[k])) for r in pred for k in ['prediction','observed']):
            return False
        # Only these branches serialize fitted weights in the existing model code.
        binary_constant = (t[0] == 'first_observed_family_within_h'
            and float(matched[0].get('train_label_mean', '-1')) in [0., 1.])
        weights = (kind == 'neural' and
            not matched[0].get('disposition','').startswith('constant_training_target'))
        weights |= kind == 'core' and model.startswith('evotrees_') and not binary_constant
        if weights and not (folder / (stem(t) + '-' + model + '.jls')).is_file():
            return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def preserve_attempt(root, folder, attempt):
    root, folder = root.resolve(), folder.resolve()
    if folder.parent != root / 'jobs':
        raise ValueError('refuse to move outside candidate jobs')
    receipt = folder / 'job_receipt.json'
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved.get('returncode') == 0 and saved.get('metric_rows') == 1 and saved.get('error_rows') == 0:
            raise ValueError('successful receipt requires manual reconciliation, never overwrite')
    dest = root / 'attempts' / attempt / folder.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise ValueError('attempt already exists')
    folder.rename(dest)
    return dest


@dataclasses.dataclass
class Budget:
    total: int
    reserve: int
    shared: int
    slots: int = 63

    @property
    def capacity(self):
        return self.total - self.reserve - self.shared

    def admits(self, request, active, available):
        # Legacy request values are retained in old receipts, never used for admission.
        return len(active) < self.slots and available > self.reserve


def reservation(kind, info, model=None):
    # No per-job estimates: admission uses live MemAvailable and the host floor.
    return 0


def scope_command(command, memory, unit, cpu=None):
    # Per-job memory is unlimited by explicit user instruction. Admission keeps
    # host headroom using measured demand; it does not kill a growing fit.
    prefix = ['taskset', '--cpu-list', str(cpu)] if cpu is not None else []
    return prefix + ['systemd-run', '--scope', '--quiet', '--unit=' + unit,
        '--property=MemoryMax=infinity', '--property=MemoryHigh=infinity',
        '--property=MemorySwapMax=infinity', '--'] + command


def physical_cpu_pool():
    groups = {}
    for cpu in sorted(os.sched_getaffinity(0)):
        folder = pathlib.Path('/sys/devices/system/cpu') / ('cpu'+str(cpu)) / 'topology'
        k = (int((folder/'physical_package_id').read_text()),
             int((folder/'core_id').read_text()))
        groups.setdefault(k, []).append(cpu)
    # Spread first across sockets, then through physical cores; avoid SMT siblings.
    return [v[0] for k,v in sorted(groups.items(),key=lambda kv:(kv[0][1],kv[0][0]))]


def claim_cpu(pool, leased):
    return next(cpu for cpu in pool if cpu not in leased)


class AdoptedProcess:
    """Wait for an existing numerical wrapper without restarting or reparenting it."""
    def __init__(self, pid, token, report, proc_root=pathlib.Path('/proc')):
        self.pid, self.token = int(pid), str(token)
        self.report, self.proc_root = pathlib.Path(report), proc_root

    def poll(self):
        try:
            fields = (self.proc_root/str(self.pid)/'stat').read_text().split()
            if fields[21] == self.token and fields[2] != 'Z':
                return None
        except (FileNotFoundError,ProcessLookupError):
            pass
        if self.report.exists():
            rc = json.loads(self.report.read_text())['returncode']
            return rc if rc >= 0 else 128-rc
        return 125  # Missing completion report remains an explicit failure.

    def wait(self):
        while True:
            rc = self.poll()
            if rc is not None:
                return rc
            time.sleep(1)


def memory():
    values = {s.split(':')[0]: int(s.split()[1]) * 1024 for s in
        pathlib.Path('/proc/meminfo').read_text().splitlines()
        if s.startswith(('MemTotal:', 'MemAvailable:'))}
    return values['MemTotal'], values['MemAvailable']


def retry_memory(previous, capacity):
    """No permanent skip: escalate deferred jobs, up to a safe isolated host limit."""
    if previous >= capacity:
        raise RuntimeError('required job exhausted safe host RAM; larger host required')
    return min(capacity, max(previous + 16 * GIB, (previous * 3 + 1) // 2))


def child_report(command, report):
    cgroup = next(s.split(':', 2)[2] for s in
        pathlib.Path('/proc/self/cgroup').read_text().splitlines()
        if s.startswith('0::'))
    folder = pathlib.Path('/sys/fs/cgroup') / cgroup.lstrip('/')
    def events():
        return {k: int(v) for k, v in
            (s.split() for s in (folder / 'memory.events').read_text().splitlines())}
    before = events()
    maximum = (folder / 'memory.max').read_text().strip()
    p = subprocess.run(command)
    savejson(pathlib.Path(report), dict(returncode=p.returncode,
        events_before=before, events_after=events(),
        peak_bytes=int((folder / 'memory.peak').read_text()) if (folder / 'memory.peak').exists() else None,
        memory_max_bytes=None if maximum=='max' else int(maximum)))
    return p.returncode if p.returncode >= 0 else 128 - p.returncode


def is_julia_worker(executable, command, root):
    return (pathlib.Path(executable).name == 'julia' and str(root) in command
        and any(n in command for n in ['run_core_task.jl','run_neural_task.jl']))


def assert_idle(root, adopted=None):
    adopted = adopted or {}
    import fcntl
    lock = (root / 'recovery-executor.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        try:
            cmd = (p / 'cmdline').read_bytes().replace(b'\0', b' ').decode()
            if (is_julia_worker((p/'exe').resolve(),cmd,root)
                    or ('redeploy_parallel_candidate.py' in cmd and 'python' in cmd)):
                parent = int((p/'stat').read_text().split()[3])
                allowed = next((j for j in adopted.values() if j['pid']==parent), None)
                if allowed is None or AdoptedProcess(parent,allowed['token'],allowed['report']).poll() is not None:
                    raise RuntimeError('unregistered candidate worker: ' + p.name)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return lock


def prepare_adapters(root, adapters):
    adapters.mkdir()
    marker = 'get(ENV,"PREP_ONLY","0")=="1" && run(`python3 $(joinpath(PARROOT,"pool_cache_guard.py"))`)'
    hashes = {}
    for name in ['shared.jl','model_rules.jl','parallel_artifact_helpers.jl',
            'run_core_task.jl','run_neural_task.jl']:
        text = (root / name).read_text()
        hashes[name] = hashlib.sha256(text.encode()).hexdigest()
        if name == 'run_core_task.jl':
            if text.count(marker) != 1:
                raise RuntimeError('unrecognized storage admission anchor')
            # This executor owns cache admission; old six-cache guard can deadlock recovery.
            text = text.replace(marker, '# Cache admission is owned by memory recovery executor.')
        (adapters / name).write_text(text)
    savejson(adapters / 'source-provenance.json', dict(original_sha256=hashes,
        changes='only bypass legacy cache admission; numerical Julia code unchanged',
        coverage_gate='NOT_PASSED'))


def release_dense(folder):
    # Remove reproducible matrices only; keep prep, provenance, logs, and fitted links.
    for name in ['a.bin', 'b.bin', 'admitted.json']:
        p = folder / name
        if p.is_symlink():
            raise RuntimeError('unexpected dense-cache symlink')
        p.unlink(missing_ok=True)


def finalize(out, root, locations, run, launch_sync):
    for kind, prefix in [('core','model'), ('neural','neural')]:
        for suffix in ['metrics','predictions']:
            name = prefix + '_' + suffix + '.csv'
            temp = out / (name + '.recovery-complete')
            header = None
            with temp.open('w', newline='') as dest:
                for (k, t, model), folder in sorted(locations.items()):
                    if k != kind:
                        continue
                    with (folder / name).open(newline='') as src:
                        reader = csv.DictReader(src)
                        if header is None:
                            header = reader.fieldnames
                            writer = csv.DictWriter(dest, fieldnames=header)
                            writer.writeheader()
                        if reader.fieldnames != header:
                            raise RuntimeError('incompatible output schema: ' + name)
                        for row in reader:
                            if key(row) == t + (model,):
                                writer.writerow(row)
            if header is None:
                raise RuntimeError('empty publication: ' + name)
            if (out / name).exists():
                shutil.copy2(out / name, run / ('before-' + name))
            os.replace(temp, out / name)
    launch_sync('pca', out, None, None, 0, dict(PCA_ONLY='1'))
    for name in ['summarize_joint_models.jl','analyze_joint_interactions.jl',
            'analyze_observed_price_paths.jl']:
        launch_sync('postprocess', out, None, None, 0, {}, out / 'scripts' / name)
    plan = json.loads((root / 'parallel_plan.json').read_text())
    savejson(run / 'previous-parallel-plan.json', plan)
    plan.update(status='complete_candidate', coverage_gate='NOT_PASSED',
        recovery=str(run), failures_preserved_under=str(root / 'attempts'),
        recovered_committed_jobs=len(locations))
    savejson(root / 'parallel_plan.json', plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=pathlib.Path, default=BASE)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--max-workers', type=int, default=96)
    parser.add_argument('--adopt-manifest', type=pathlib.Path)
    parser.add_argument('--assignment', type=pathlib.Path, required=True)
    parser.add_argument('--worker-id', choices=['A','B'], required=True)
    args = parser.parse_args()
    if args.max_workers < 1:
        parser.error('--max-workers must be positive')
    b = args.base.resolve()
    out = b / 'joint-models-v4-candidate-20261022'
    root = out / 'parallel-63'
    cohorts = sorted({(r['outcome'], r['horizon_s'], str(f))
        for r in readrows(out / 'model_outcomes.csv') for f in [2,3,4]})
    if len(cohorts) != 63:
        raise RuntimeError('expected the frozen 63 cohorts')
    all_cohorts = cohorts[:]
    assignment = json.loads(args.assignment.read_text())
    cohorts = assigned_cohorts(all_cohorts,assignment,args.worker_id)
    instance = os.environ.get('FAMILY_BOX_INSTANCE_ID')
    if instance != assignment['instances'][args.worker_id]:
        raise RuntimeError('ownership is pinned to a different instance')
    snapshot = []
    for t in cohorts:
        ready = root / 'cache' / stem(t) / 'ready.json'
        snapshot.append(dict(cohort=t, prepared=ready.exists()))
    if not args.execute:
        print(json.dumps(dict(status='plan_only', cohorts=snapshot,
            max_workers=args.max_workers, memory_reserve_gib=64,
            coverage_gate='NOT_PASSED')))
        return

    if args.worker_id=='B':
        require_a_ready(args.assignment)
    adopted = {}
    if args.adopt_manifest:
        manifest = json.loads(args.adopt_manifest.read_text())
        if pathlib.Path('/proc',str(manifest['old_coordinator_pid'])).exists():
            raise RuntimeError('old coordinator must exit before adopting its workers')
        for job in manifest['jobs']:
            if tuple(job['cohort']) not in set(cohorts):
                raise RuntimeError('cannot move an active cohort to another owner')
            k = (job['kind'],tuple(job['cohort']),job['model'])
            if k in adopted:
                raise RuntimeError('duplicate adoption key')
            folder = pathlib.Path(job['folder']).resolve()
            if folder.parent != root/'jobs' and job['kind']!='prepare':
                raise RuntimeError('adopted output outside candidate jobs')
            adopted[k] = job
    lock = assert_idle(root,adopted)  # No concurrent coordinator or unregistered worker.
    announce_ready(args.assignment,args.worker_id,instance)
    cpu_pool = physical_cpu_pool()
    leased_cpus = set()
    args.max_workers = min(args.max_workers,len(cpu_pool))
    if not shutil.which('systemd-run') or not pathlib.Path('/sys/fs/cgroup/cgroup.controllers').exists():
        raise RuntimeError('cgroup-v2/systemd-run required; refuse unbounded execution')
    runid = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + uuid.uuid4().hex[:8]
    run = root / ('memory-recovery-' + runid)
    run.mkdir()
    savejson(run/'ownership.json',assignment)
    shutil.copy2(pathlib.Path(__file__),run/'coordinator-source.py')
    shutil.copy2(pathlib.Path(__file__).with_name('dual_box_support.py'),run/'dual_box_support.py')
    adapters = run / 'adapters'
    prepare_adapters(root, adapters)
    total, _ = memory()
    budget = Budget(total, 64*GIB, (root / 'shared/raw.bin').stat().st_size, args.max_workers)
    julia = str(b / 'julia-runtime/julia-1.13.2/bin/julia')
    env = dict(os.environ, FAMILY_RESEARCH_DIR=str(b), JOINT_PARALLEL_ROOT=str(root),
        JULIA_DEPOT_PATH=str(b / 'julia-depot'), JULIA_NUM_THREADS='1',
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    locations, deferred, required = {}, [], set()
    savejson(run / 'recovery-plan.json', dict(status='running', coverage_gate='NOT_PASSED',
        memory=dataclasses.asdict(budget), no_input_rebuild=True, no_successful_refits=True))

    def launch(kind, folder, t, model, request, extra=None, script=None, cache_folder=None):
        folder.mkdir(exist_ok=True, parents=True)
        if t and not (folder / 'model_outcomes.csv').exists():
            (folder / 'model_outcomes.csv').symlink_to(out / 'model_outcomes.csv')
        e = dict(env, JOINT_MODEL_OUT=str(folder), MODEL_COHORT='|'.join(t or ()),
            MODEL_NAME=model or '', PREP_ONLY='1' if kind=='prepare' else '0',
            COHORT_CACHE=str(cache_folder or cache))
        e.update(extra or {})
        if script is None:
            script = adapters / ('run_neural_task.jl' if kind=='neural' else 'run_core_task.jl')
        project = b / ('julia-neural-env' if kind=='neural' else 'julia-model-env')
        report = folder / ('memory-report-' + runid + '.json')
        cmd = [julia, '--startup-file=no', '--project='+str(project), str(script)]
        wrapped = [sys.executable, str(pathlib.Path(__file__).resolve()),
            '--child-report', str(report), '--'] + cmd
        unit = 'family-recovery-' + uuid.uuid4().hex
        logpath = folder / ('run.log' if kind in ['core','neural'] else kind+'-'+runid+'.log')
        log = logpath.open('w')
        cpu = claim_cpu(cpu_pool,leased_cpus)
        process = subprocess.Popen(scope_command(wrapped, request, unit, cpu), env=e,
            stdout=log, stderr=subprocess.STDOUT)
        leased_cpus.add(cpu)
        return dict(process=process, log=log, folder=folder, kind=kind, cohort=t,
            model=model, request=request, report=report, cpu=cpu)

    def finish(job):
        rc = job['process'].wait()
        if job['log'] is not None:
            job['log'].close()
        leased_cpus.discard(job['cpu'])
        report = json.loads(job['report'].read_text()) if job['report'].exists() else {}
        is_oom = report.get('events_after',{}).get('oom_kill',0) > report.get('events_before',{}).get('oom_kill',0)
        if job['kind'] in ['core','neural']:
            prefix = 'model' if job['kind']=='core' else 'neural'
            receipt = dict(kind=job['kind'], cohort=job['cohort'], model=job['model'],
                returncode=rc, metric_rows=len(readrows(job['folder'] / (prefix+'_metrics.csv'))),
                error_rows=len(readrows(job['folder'] / (prefix+'_errors.csv'))),
                output=str(job['folder']), memory_reservation_bytes=job['request'],
                memory_report=report, recovery_run=runid)
            savejson(job['folder'] / 'job_receipt.json', receipt)
            good = committed(job['folder'],job['kind'],job['cohort'],job['model'])
        else:
            good = rc == 0
        return good, is_oom, rc

    def sync(kind, folder, t, model, request, extra=None, script=None):
        if not budget.admits(request, [], memory()[1]):
            raise RuntimeError('insufficient safe free RAM for isolated ' + kind)
        job = launch(kind,folder,t,model,request,extra,script)
        good, oom, rc = finish(job)
        if not good:
            raise RuntimeError(str((kind,t,model,'memory_limited' if oom else 'execution_failure',rc)))

    cache = root / 'cache' / stem(cohorts[0])
    # Verify the unlimited job scope once before importing model data.
    probe = [sys.executable, '-c',
        "import pathlib; c=next(s.split(':',2)[2] for s in pathlib.Path('/proc/self/cgroup').read_text().splitlines() if s.startswith('0::')); assert (pathlib.Path('/sys/fs/cgroup')/c.lstrip('/')/'memory.max').read_text().strip()==str(2*1024**3)"]
    probe[2] = probe[2].replace("==str(2*1024**3)","=='max'")
    subprocess.run(scope_command(probe, 2*GIB, 'family-probe-'+uuid.uuid4().hex, cpu_pool[0]), check=True)

    # Reconcile each declared result once, then schedule across cohorts globally.
    # These queues are numerical execution, not a monitor or a new automation.
    infos, missing, registered = {}, {}, set()

    def reconcile(t, info):
        registered.add(t)
        tasks = []
        for kind, models in zip(['core','neural'], expected_models(t,info['groups'])):
            for model in models:
                k = (kind,t,model)
                required.add(k)
                folder = root/'jobs'/job_id(t,kind,model)
                serial = root/'serial-prefix'
                if k in adopted:
                    tasks.append((kind,model,int(adopted[k]['request'])))
                    continue
                if committed(folder,kind,t,model):
                    locations[k] = folder
                    if not (folder/'job_receipt.json').exists():
                        savejson(folder/'artifact_recovery_receipt.json',
                            dict(status='coherent_committed_artifacts',
                                original_process_returncode=None, recovery_run=runid))
                elif committed(serial,kind,t,model,serial=True):
                    locations[k] = serial
                else:
                    tasks.append((kind,model,reservation(kind,info,model)))
        return tasks

    def checkpoint(status, **extra):
        savejson(run/'recovery-plan.json', dict(status=status,
            coverage_gate='NOT_PASSED', memory=dataclasses.asdict(budget),
            required_jobs=[[k,list(t),m] for k,t,m in sorted(required)],
            committed_jobs=[[k,list(t),m] for k,t,m in sorted(locations)],
            unregistered_cohorts=[list(t) for t in cohorts if t not in registered],
            all_declared_tasks_mandatory=True, per_job_memory_caps='unlimited',
            admission_policy='actual MemAvailable above host floor; no job estimates',
            cpu_placement='one worker per physical core, sockets interleaved',
            **extra))

    adopted_caches = {tuple(j['cohort']):pathlib.Path(j['cache']) for j in adopted.values()}
    for t in cohorts:
        original = adopted_caches.get(t,root/'cache'/stem(t))
        if (original/'ready.json').exists():
            infos[t] = json.loads((original/'ready.json').read_text())
            missing[t] = reconcile(t,infos[t])
        else:
            missing[t] = None
    checkpoint('reconciled',worker_id=args.worker_id,
        assignment_sha256=assignment_digest(args.assignment))

    def parallel_phase(work, phase):
        """Parallel prepares and fits, bounded by slots, RAM and dense cache space."""
        nonlocal cache
        prepare_queue, pending, active, resident, cache_by, remaining = [], [], [], set(), {}, {}
        next_deferred, failures = [], []
        last_dispatch = 0.0

        def clear_cache(t):
            folder = cache_by[t]
            release_dense(folder)
            original = root/'cache'/stem(t)
            if folder != original:
                release_dense(original)
            resident.discard(t)

        def enqueue(t, tasks, folder):
            cache_by[t] = folder
            remaining[t] = len(tasks)
            for kind,model,amount in tasks:
                k = (kind,t,model)
                if k in adopted:
                    old = adopted.pop(k)
                    cpu = int(old['cpu'])
                    if cpu in leased_cpus:
                        raise RuntimeError('duplicate adopted CPU placement')
                    leased_cpus.add(cpu)
                    active.append(dict(process=AdoptedProcess(old['pid'],old['token'],old['report']),
                        log=None, folder=pathlib.Path(old['folder']),kind=kind,cohort=t,
                        model=model,request=int(old['request']),report=pathlib.Path(old['report']),
                        cpu=cpu, adopted=True))
                else:
                    pending.append((kind,t,model,amount))
            if tasks:
                resident.add(t)
                # An adopted worker may still own a preprocessing lock.
                if not any(j.get('adopted') and j['cohort']==t and j['process'].poll() is None for j in active):
                    for stale in folder.glob('*.lock'):
                        dest = root/'attempts'/runid/('locks-'+str(phase))/stem(t)/stale.name
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        stale.rename(dest)
            else:
                clear_cache(t)

        for t,tasks in work.items():
            original = adopted_caches.get(t,root/'cache'/stem(t))
            prepkey = ('prepare',t,'')
            if prepkey in adopted:
                old = adopted.pop(prepkey)
                cpu = int(old['cpu'])
                if cpu in leased_cpus:
                    raise RuntimeError('duplicate adopted preparation CPU')
                leased_cpus.add(cpu)
                cache_by[t] = pathlib.Path(old['cache'])
                active.append(dict(process=AdoptedProcess(old['pid'],old['token'],old['report']),
                    log=None,folder=pathlib.Path(old['folder']),kind='prepare',cohort=t,model='',
                    request=int(old['request']),report=pathlib.Path(old['report']),cpu=cpu,
                    adopted=True,pending_after_prepare=tasks))
                continue
            if tasks == []:
                release_dense(original)
                continue
            info = infos.get(t)
            valid = phase == 0 and info is not None and all(
                (original/n).is_file() and (original/n).stat().st_size == math.prod(info[k])*8
                for n,k in [('a.bin','a_dims'),('b.bin','b_dims')])
            if valid:
                enqueue(t,tasks,original)
            else:
                # Only reproducible caches are released; all fitted and failed states remain.
                release_dense(original)
                folder = run/('rebuilt-cache-'+str(phase))/stem(t)
                folder.mkdir(parents=True)
                cache_by[t] = folder
                prepare_queue.append((t,tasks))
        try:
            while prepare_queue or pending or active:
                changed = False
                requests = [j['request'] for j in active]
                preparing = [j for j in active if j['kind']=='prepare']
                # Preparation and fits share slots; admission uses actual RAM only.
                while (prepare_queue and len(preparing)<4
                        and len(resident)+len(preparing)<6
                        and shutil.disk_usage(root).free >= (100+32*len(preparing))*GIB
                        and budget.admits(0,requests,memory()[1])):
                    t,tasks = prepare_queue.pop(0)
                    job = launch('prepare',cache_by[t],t,None,0,
                        cache_folder=cache_by[t])
                    job['pending_after_prepare'] = tasks
                    active.append(job)
                    preparing.append(job)
                    requests.append(job['request'])
                    changed = True
                # Multiple cohorts share this pool. There is no per-cohort barrier.
                for item in pending[:]:
                    # Cold-start pacing lets the live RAM guard observe allocations.
                    if args.worker_id=='B' and time.monotonic()-last_dispatch < 3:
                        break
                    kind,t,model,amount = item
                    if not budget.admits(amount,requests,memory()[1]):
                        continue
                    folder = root/'jobs'/job_id(t,kind,model)
                    if folder.exists():
                        preserve_attempt(root,folder,runid+'-phase-'+str(phase))
                    active.append(launch(kind,folder,t,model,amount,cache_folder=cache_by[t]))
                    last_dispatch = time.monotonic()
                    requests.append(amount)
                    pending.remove(item)
                    changed = True
                for job in active[:]:
                    if job['process'].poll() is None:
                        continue
                    good,oom,rc = finish(job)
                    active.remove(job)
                    t = job['cohort']
                    if job['kind']=='prepare':
                        if not good:
                            # Preparation is mandatory too; increase its cap on next explicit recovery.
                            failures.append(('prepare',t,None,rc,oom))
                            continue
                        info = json.loads((cache_by[t]/'ready.json').read_text())
                        if t in infos and info != infos[t]:
                            raise RuntimeError('regenerated preparation shape/group disagreement')
                        infos[t] = info
                        tasks = job['pending_after_prepare']
                        if tasks is None:
                            tasks = reconcile(t,info)
                        enqueue(t,tasks,cache_by[t])
                    else:
                        remaining[t] -= 1
                        if good:
                            locations[(job['kind'],t,job['model'])] = job['folder']
                        elif oom:
                            next_deferred.append((job['kind'],t,job['model'],job['request']))
                        else:
                            failures.append((job['kind'],t,job['model'],rc,False))
                        if remaining[t] == 0:
                            clear_cache(t)
                        print(json.dumps(dict(kind=job['kind'],cohort=t,model=job['model'],
                            committed=good,memory_deferred=oom,returncode=rc)),flush=True)
                    changed = True
                if failures:
                    raise RuntimeError('required tasks failed; pending work retained: '+str(failures))
                if not active and (pending or prepare_queue) and not changed:
                    raise RuntimeError('required tasks need more safe RAM/disk; no task skipped')
                if changed:
                    checkpoint('running',phase=phase,active_jobs=len(active),
                        queued_jobs=len(pending),queued_preparations=len(prepare_queue),
                        deferred_memory_jobs=next_deferred)
                if active:
                    time.sleep(1)
        except BaseException as error:
            # Let already running numerical jobs finish and record them before exiting.
            for job in active:
                good,oom,rc = finish(job)
                if job['kind'] in ['core','neural'] and good:
                    locations[(job['kind'],job['cohort'],job['model'])] = job['folder']
            checkpoint('incomplete',phase=phase,error=str(error),
                deferred_memory_jobs=next_deferred,all_pending_work_retained=True)
            raise
        return next_deferred

    deferred = parallel_phase(missing,0)
    phase = 0
    while deferred:
        phase += 1
        retry_work = {}
        for kind,t,model,amount in deferred:
            # Escalation ends in an explicit larger-host requirement, never a skip.
            try:
                larger = retry_memory(amount,budget.capacity)
            except RuntimeError as error:
                checkpoint('incomplete',error=str(error),deferred_memory_jobs=deferred)
                raise
            retry_work.setdefault(t,[]).append((kind,model,larger))
        deferred = parallel_phase(retry_work,phase)
    if registered != set(cohorts) or set(locations) != required:
        checkpoint('incomplete',error='mandatory task coverage incomplete')
        raise RuntimeError('mandatory task coverage incomplete; publication refused')
    own_required = [[k,list(t),m] for k,t,m in sorted(required)]
    checkpoint('shard_fits_complete',worker_id=args.worker_id,
        assignment_sha256=assignment_digest(args.assignment),
        global_pca_and_postprocessing_pending=True)
    if args.worker_id=='B':
        logpath = os.environ.get('FAMILY_COORDINATOR_LOG')
        if logpath and pathlib.Path(logpath).is_file():
            shutil.copy2(logpath,run/'coordinator.log')
        transfer = publish_b(root,locations,required,cohorts,args.assignment)
        savejson(run/'shard-completion.json',transfer)
        print(json.dumps(dict(status='shard_fits_complete',worker='B',
            coverage_gate='NOT_PASSED',committed_jobs=len(locations))),flush=True)
        return
    checkpoint('waiting_for_B',worker_id='A',global_pca_and_postprocessing_pending=True)
    imported,transfer = receive_b(b,root,args.assignment)
    expected_b = set(assigned_cohorts(all_cohorts,assignment,'B'))
    if set(map(tuple,transfer['cohorts'])) != expected_b:
        raise RuntimeError('B cohort ownership mismatch')
    b_required = transfer['required_jobs']
    if {tuple(t) for k,t,m in b_required} != expected_b:
        raise RuntimeError('B mandatory cohort enumeration incomplete')
    required.update((k,tuple(t),m) for k,t,m in b_required)
    all_required = [[k,list(t),m] for k,t,m in sorted(required)]
    reconcile_keys(own_required,b_required,all_required)
    if set(imported) != {(k,tuple(t),m) for k,t,m in b_required}:
        raise RuntimeError('B required/committed task mismatch')
    for (kind,t,model),folder in imported.items():
        if not committed(folder,kind,t,model):
            raise RuntimeError('imported B artifacts are not coherent: '+str((kind,t,model)))
    locations.update(imported)
    if set(locations) != required or {t for k,t,m in required} != set(all_cohorts):
        raise RuntimeError('global mandatory task coverage incomplete')
    checkpoint('global_fits_complete',global_cohorts=len(all_cohorts),
        global_pca_and_postprocessing_pending=True)
    cache = root/'cache'/stem(cohorts[0])
    finalize(out,root,locations,run,sync)
    savejson(run/'recovery-plan.json',dict(status='complete_candidate',
        coverage_gate='NOT_PASSED',committed_jobs=len(locations),
        memory=dataclasses.asdict(budget),deferred_memory_jobs=len(deferred)))
    print(json.dumps(dict(status='complete_candidate',run=str(run),
        coverage_gate='NOT_PASSED',committed_jobs=len(locations))))


if __name__ == '__main__':
    if len(sys.argv) >= 5 and sys.argv[1] == '--child-report' and sys.argv[3] == '--':
        sys.exit(child_report(sys.argv[4:],sys.argv[2]))
    try:
        main()
    except BaseException as error:
        if '--assignment' in sys.argv and '--worker-id' in sys.argv:
            try:
                publish_failure(sys.argv[sys.argv.index('--assignment')+1],
                    sys.argv[sys.argv.index('--worker-id')+1],error)
            except Exception as transfer_error:
                print('Failure receipt remains local: '+str(transfer_error),flush=True)
        raise
