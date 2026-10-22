"""One-time capture/adoption for the authorized four-box expansion; never kills Julia."""
import pathlib,os,sys,json,signal,time,hashlib,subprocess,fcntl,urllib.request,collections
import boto3

B=pathlib.Path('/opt/frankie-box/work/family-research-20261022')
O=B/'joint-models-v4-candidate-20261022';R=O/'parallel-63'
PREFIX='host-deliveries/family-research-20261022/four-box-expansion-20261022/'
BUCKET='frankie-granite42-568968024170-us-east-1';ACCOUNT='568968024170'
CONFIG={'i-035994afa8bdf66a5':('A',5454,'memory-recovery-20261022T190800Z-7cf0ea3a'),
        'i-087f8d3247ae847a9':('B',3861,'memory-recovery-20261022T194644Z-f4082e1d'),
        'i-031eeb577ad72b064':('C',None,None),'i-0d17573dbce871520':('D',None,None)}

def instance_id():
    token=urllib.request.urlopen(urllib.request.Request('http://169.254.169.254/latest/api/token',
        data=b'',method='PUT',headers={'X-aws-ec2-metadata-token-ttl-seconds':'60'}),timeout=5).read().decode()
    return urllib.request.urlopen(urllib.request.Request('http://169.254.169.254/latest/meta-data/instance-id',
        headers={'X-aws-ec2-metadata-token':token}),timeout=5).read().decode()

def identity(pid):
    p=pathlib.Path('/proc',str(pid))
    return p,(p/'cmdline').read_bytes().split(b'\0'),(p/'stat').read_text().split(') ',1)[1].split()

def put(name,value):
    boto3.client('s3',region_name='us-east-1').put_object(Bucket=BUCKET,Key=PREFIX+name,
        Body=json.dumps(value).encode(),ServerSideEncryption='AES256',ExpectedBucketOwner=ACCOUNT)

def capture(instance,owner,oldpid,oldrun):
    _,oldcmd,oldst=identity(oldpid)
    assert b'--execute' in oldcmd and any(b'resume_dual_box_candidate' in c for c in oldcmd)
    token=oldst[19];paused=False
    try:
        os.kill(oldpid,signal.SIGSTOP);paused=True
        deadline=time.monotonic()+5
        while identity(oldpid)[2][0]!='T' and time.monotonic()<deadline:time.sleep(.02)
        assert identity(oldpid)[2][0]=='T'
        oldmanifest=json.loads(pathlib.Path(oldcmd[oldcmd.index(b'--adopt-manifest')+1].decode()).read_text())
        fallback={j['folder']:j['cpu'] for j in oldmanifest['jobs']}
        wrappers={};numerical={}
        for p in pathlib.Path('/proc').iterdir():
            if not p.name.isdigit():continue
            try:
                pid=int(p.name);p,cmd,st=identity(pid)
                if not cmd or not cmd[0]:continue
                exe=pathlib.Path(cmd[0].decode()).name
                if exe!='julia' and not (exe.startswith('python') and b'--child-report' in cmd):continue
                env=dict(v.split(b'=',1) for v in (p/'environ').read_bytes().split(b'\0') if b'=' in v)
                if env.get(b'FAMILY_RESEARCH_DIR',b'').decode()!=str(B):continue
                if exe=='julia':
                    numerical[pid]=dict(parent=int(st[1]),token=st[19],cpu=sorted(os.sched_getaffinity(pid)))
                else:wrappers[pid]=(cmd,st,env)
            except (OSError,ValueError,ProcessLookupError):continue
        jobs=[]
        for pid,(cmd,st,env) in wrappers.items():
            folder=env[b'JOINT_MODEL_OUT'].decode();cache=env[b'COHORT_CACHE'].decode()
            cohort=env[b'MODEL_COHORT'].decode().split('|');model=env.get(b'MODEL_NAME',b'').decode()
            kind='prepare' if env.get(b'PREP_ONLY')==b'1' else ('neural' if any(b'run_neural_task.jl' in c for c in cmd) else 'core')
            assert len(cohort)==3 and folder.startswith(str(R)+'/')
            assert kind=='prepare' or pathlib.Path(folder).parent==R/'jobs'
            child=[(n,v) for n,v in numerical.items() if v['parent']==pid]
            assert len(child)<=1
            affinity=child[0][1]['cpu'] if child else sorted(os.sched_getaffinity(pid))
            cpu=affinity[0] if len(affinity)==1 else fallback[folder]
            report=cmd[cmd.index(b'--child-report')+1].decode()
            jobs.append(dict(pid=pid,token=st[19],report=report,request=0,folder=folder,cache=cache,
                kind=kind,cohort=cohort,model=model,cpu=cpu,command=[c.decode() for c in cmd if c],
                numerical_children=[n for n,v in child]))
        parents={j['pid'] for j in jobs}
        assert all(v['parent'] in parents for v in numerical.values())
        assert len({(j['kind'],tuple(j['cohort']),j['model']) for j in jobs})==len(jobs)
        assert len({j['cpu'] for j in jobs})==len(jobs)
        state=json.loads((R/oldrun/'recovery-plan.json').read_text())
        from multibox_support import prepared_cache_index
        declared={tuple(t) for k,t,m in state['required_jobs']}|{tuple(t) for t in state['unregistered_cohorts']}
        value=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),owner=owner,instance=instance,
            old_coordinator_pid=oldpid,old_coordinator_token=token,jobs=jobs,numerical_before=numerical,
            previous_state=state,previous_run=oldrun,prepared_caches=prepared_cache_index(R,declared),
            admission_policy='actual RAM only; unlimited caps')
        path=R/('four-box-'+owner+'-capture-20261022.json')
        assert not path.exists()
        path.write_text(json.dumps(value,indent=2))
        put(owner+'-capture.json',value)
        print(json.dumps(dict(owner=owner,capture=str(path),workers=len(numerical),adopted=len(jobs),
            committed=len(state['committed_jobs']),registered=len(state['required_jobs']),
            unknown=len(state['unregistered_cohorts']),coordinator_paused=True)))
    except BaseException:
        if paused:os.kill(oldpid,signal.SIGCONT)
        raise

def launch(instance,owner,oldpid):
    assignment=R/'four-box-ownership-20261022.json'
    plan=json.loads(assignment.read_text())
    assert plan['instances'][owner]==instance
    owned={tuple(r['cohort']) for r in plan['cohorts'] if r['owner']==owner}
    target=B/'full-context-audit/scripts/resume_multibox_candidate.py'
    command=['python3',str(target),'--execute','--max-workers',str(plan['slots'][owner]),
             '--assignment',str(assignment),'--worker-id',owner]
    if oldpid:
        path=R/('four-box-'+owner+'-capture-20261022.json')
        value=json.loads(path.read_text())
        assert all(tuple(j['cohort']) in owned for j in value['jobs'])
        _,_,st=identity(oldpid)
        assert st[19]==value['old_coordinator_token'] and st[0]=='T'
        for pid,v in value['numerical_before'].items():
            try:assert identity(int(pid))[2][19]==v['token']
            except FileNotFoundError:pass
        os.kill(oldpid,signal.SIGKILL)
        deadline=time.monotonic()+10
        while pathlib.Path('/proc',str(oldpid)).exists() and time.monotonic()<deadline:time.sleep(.1)
        assert not pathlib.Path('/proc',str(oldpid)).exists()
        command+=['--adopt-manifest',str(path)]
    with (R/'recovery-executor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_UN)
    log=O/('parallel-four-'+owner+'.log')
    with log.open('a') as f:
        child=subprocess.Popen(command,env=dict(os.environ,FAMILY_BOX_INSTANCE_ID=instance,
            FAMILY_COORDINATOR_LOG=str(log)),stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    value=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),worker=owner,
        instance=instance,new_coordinator_pid=child.pid,old_coordinator_pid=oldpid,
        owned_cohorts=len(owned),max_workers=plan['slots'][owner],assignment=str(assignment),
        assignment_sha256=hashlib.sha256(assignment.read_bytes()).hexdigest(),log=str(log),
        no_numerical_fit_stopped_or_restarted=True,coverage_gate='NOT_PASSED')
    (R/('four-box-'+owner+'-launch-receipt.json')).write_text(json.dumps(value,indent=2))
    print(json.dumps(value))

if __name__=='__main__':
    instance=instance_id();owner,oldpid,oldrun=CONFIG[instance]
    if sys.argv[1]=='capture':
        assert owner in ['A','B'];capture(instance,owner,oldpid,oldrun)
    elif sys.argv[1]=='launch':launch(instance,owner,oldpid)
    else:raise ValueError('capture or launch required')

