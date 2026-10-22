import pathlib,json,os,signal,time,subprocess,hashlib,ast,runpy,fcntl,sys,csv
B=pathlib.Path('/opt/frankie-box/work/family-research-20261022');O=B/'joint-models-v4-candidate-20261022';R=O/'parallel-63'
source=(B/'full-context-audit/scripts/resume_dual_box_candidate.py').read_text()
target=B/'full-context-audit/scripts/resume_dual_box_candidate.py'
sys.path.insert(0,str(target.parent))
from retained_result_assignment import assignment_preserving_prior_results
ast.parse(source)
assert hashlib.sha256(source.encode()).hexdigest()=='4755e5ad5f3653ab2759e353fc168d80c3483826df4de2602dddb5d35c7b5ff9'
if target.exists() and target.read_text()!=source: raise RuntimeError('different actual-memory source already exists; refuse overwrite')
target.write_text(source)
mod=runpy.run_path(str(target),run_name='admission_preflight')
G=1024**3
assert mod['Budget'](1500*G,64*G,33*G,96).admits(400*G,[400*G]*95,100*G)
assert not mod['Budget'](1500*G,64*G,33*G,96).admits(0,[0]*96,100*G)
oldpid=4409; proc=pathlib.Path('/proc')
def identity(pid):
    p=proc/str(pid);cmd=(p/'cmdline').read_bytes().split(b'\0');st=(p/'stat').read_text().split(') ',1)[1].split()
    return p,cmd,st
p,oldcmd,oldstat=identity(oldpid)
assert b'--execute' in oldcmd and any(a.endswith(b'/resume_actual_memory_candidate.py') for a in oldcmd)
oldtoken=oldstat[19]
stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
manifest_path=R/('dual-box-A-adoption-'+stamp+'.json')
receipt_path=R/('dual-box-A-handoff-'+stamp+'.json')
oldmanifest=json.loads((R/'actual-memory-adoption-20261022T182637Z.json').read_text())
oldcpus={j['folder']:j['cpu'] for j in oldmanifest['jobs']}
paused=False;terminated=False
try:
    os.kill(oldpid,signal.SIGSTOP);paused=True
    stop_deadline=time.monotonic()+5
    while identity(oldpid)[2][0]!='T' and time.monotonic()<stop_deadline:time.sleep(.02)
    assert identity(oldpid)[2][0]=='T'
    wrappers={};numerical={}
    for path in proc.iterdir():
        if not path.name.isdigit(): continue
        try:
            pid=int(path.name);pp,cmd,st=identity(pid)
            if not cmd or not cmd[0]: continue
            exe=pathlib.Path(cmd[0].decode()).name
            if exe!='julia' and not (exe.startswith('python') and b'--child-report' in cmd): continue
            env=dict(v.split(b'=',1) for v in (pp/'environ').read_bytes().split(b'\0') if b'=' in v)
            if env.get(b'FAMILY_RESEARCH_DIR',b'').decode()!=str(B):continue
            if exe=='julia':
                numerical[pid]=dict(parent=int(st[1]),token=st[19],cpu=sorted(os.sched_getaffinity(pid)),command=[c.decode() for c in cmd if c])
            else: wrappers[pid]=(cmd,st,env)
        except (OSError,ValueError,ProcessLookupError):continue
    jobs=[]
    for pid,(cmd,st,env) in wrappers.items():
        folder=env.get(b'JOINT_MODEL_OUT',b'').decode()
        cache=env.get(b'COHORT_CACHE',b'').decode()
        if not folder.startswith(str(R)+'/'): raise RuntimeError('foreign output folder')
        cohort=env.get(b'MODEL_COHORT',b'').decode().split('|')
        if len(cohort)!=3:raise RuntimeError('unknown cohort')
        model=env.get(b'MODEL_NAME',b'').decode()
        kind='prepare' if env.get(b'PREP_ONLY')==b'1' else ('neural' if any(b'run_neural_task.jl' in c for c in cmd) else 'core')
        if kind!='prepare' and pathlib.Path(folder).parent!=R/'jobs':raise RuntimeError('fit folder outside jobs')
        child=[(n,v) for n,v in numerical.items() if v['parent']==pid]
        if len(child)>1:raise RuntimeError('multiple Julia children')
        affinity=child[0][1]['cpu'] if child else sorted(os.sched_getaffinity(pid))
        if len(affinity)==1:cpu=affinity[0]
        elif folder in oldcpus:cpu=oldcpus[folder]
        else:raise RuntimeError('unresolved worker affinity')
        report=cmd[cmd.index(b'--child-report')+1].decode()
        jobs.append(dict(pid=pid,token=st[19],report=report,request=0,folder=folder,cache=cache,kind=kind,cohort=cohort,model=model,cpu=cpu,command=[c.decode() for c in cmd if c],numerical_children=[n for n,v in child]))
    parents={j['pid'] for j in jobs}
    if any(v['parent'] not in parents for v in numerical.values()):raise RuntimeError('numerical worker without adoption wrapper')
    keys=[(j['kind'],tuple(j['cohort']),j['model']) for j in jobs]
    if len(set(keys))!=len(keys):raise RuntimeError('duplicate task identity')
    cpus=[j['cpu'] for j in jobs]
    if len(set(cpus))!=len(cpus):raise RuntimeError('duplicate CPU lease')
    previous=R/'memory-recovery-20261022T182638Z-b253c45d/recovery-plan.json'
    previous_state=json.loads(previous.read_text())
    serial_metrics=[]
    for prefix in ['model','neural']:
        p=R/'serial-prefix'/(prefix+'_metrics.csv')
        if p.exists():
            with p.open(newline='') as f:serial_metrics.extend(csv.DictReader(f))
    assignment=assignment_preserving_prior_results(previous_state,
        {'A':'i-035994afa8bdf66a5','B':'i-087f8d3247ae847a9'},jobs,serial_metrics)
    assignment['created_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    assignment['outcome_sha256']='6a0613a357675ba60c7d4e946592b2aa69ea0e09dd488cd0ecfa4d54ba445608'
    assignment['numerical_source_sha256']={n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in ['run_core_task.jl','run_neural_task.jl','model_rules.jl','shared.jl','parallel_artifact_helpers.jl']}
    assignment_path=R/('dual-box-ownership-'+stamp+'.json')
    with assignment_path.open('x') as f:json.dump(assignment,f,indent=2)
    assignment_sha=hashlib.sha256(assignment_path.read_bytes()).hexdigest()
    manifest=dict(old_coordinator_pid=oldpid,old_coordinator_token=oldtoken,jobs=jobs,numerical_before=numerical,previous_state=previous_state,admission_policy='no per-job estimates; actual MemAvailable > 64 GiB; ceiling 96')
    with manifest_path.open('x') as f:json.dump(manifest,f,indent=2)
    for pid,v in numerical.items():
        try:
            if identity(pid)[2][19]!=v['token']:raise RuntimeError('worker PID reused')
        except FileNotFoundError:pass
    assert identity(oldpid)[2][19]==oldtoken
    os.kill(oldpid,signal.SIGKILL);terminated=True
    deadline=time.monotonic()+10
    while (proc/str(oldpid)).exists() and time.monotonic()<deadline:time.sleep(.1)
    if (proc/str(oldpid)).exists():raise RuntimeError('old coordinator not reaped; do not launch another')
    with (R/'recovery-executor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.flock(lock,fcntl.LOCK_UN)
    logpath=O/'parallel-dual-A.log'
    with logpath.open('a') as log:
        new=subprocess.Popen(['python3',str(target),'--execute','--max-workers','96','--adopt-manifest',str(manifest_path),'--assignment',str(assignment_path),'--worker-id','A'],env=dict(os.environ,FAMILY_BOX_INSTANCE_ID='i-035994afa8bdf66a5',FAMILY_COORDINATOR_LOG=str(logpath)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    receipt=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),new_coordinator_pid=new.pid,old_coordinator_pid=oldpid,manifest=str(manifest_path),old_committed=len(previous_state.get('committed_jobs',[])),adopted_jobs=len(jobs),numerical_workers_before=len(numerical),source_sha256=hashlib.sha256(source.encode()).hexdigest(),log=str(logpath),admission_policy=manifest['admission_policy'],no_numerical_fit_restarted=True,coverage_gate='NOT_PASSED',assignment_path=str(assignment_path),assignment_sha256=assignment_sha,cohorts_by_owner={owner:sum(r['owner']==owner for r in assignment['cohorts']) for owner in ['A','B']})
    with receipt_path.open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(dict(receipt_path=str(receipt_path),ownership=assignment,**receipt)))
except BaseException:
    if paused and not terminated:os.kill(oldpid,signal.SIGCONT)
    raise

