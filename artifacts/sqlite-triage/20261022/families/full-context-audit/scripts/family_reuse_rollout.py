"""Capture, fence and hand off only dispatchers; existing numerical workers survive."""
import argparse
import base64
import gzip
import hashlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
from family_save_stop import require,durable_json,task_key,task_set
from family_guarded_recovery import identity,capture_workers,validate_coordinator
from family_reuse_epoch import reuse_source,make_epoch
from family_reuse_support import cohorts_for_worker,task_owner,publish,optional_json,reuse_key
from family_completion_hook import process_token,coordinator_source,imds_instance


def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def validate_replacement_exit(config,receipt,state,completion,token):
    require(token in (None,receipt['token']),'replacement coordinator PID reused')
    require(state['status'] not in ('failed','incomplete'),'replacement failed')
    if token is None:
        require(config['owner']!='A' and state['status']=='shard_fits_complete','unexpected replacement exit; retain evidence')
        require(completion and completion['worker']==config['owner'] and
                completion['assignment_sha256']==receipt['digest'] and completion['status']=='fits_complete',
                'exited replacement lacks exact completed shard receipt')


def commit_epoch(config,epoch,hashes,bootstrap=False):
    from multibox_support import client
    from family_save_stop import get_bytes
    require(config['owner']=='A','only A publishes the global ownership commit')
    previous=json.loads(pathlib.Path(config['assignment']).read_text())
    require(set(hashes)==set(previous['instances']),'missing fenced owner')
    s3=client();old=config['digest'];rows={}
    for owner,expected in hashes.items():
        row=json.loads(get_bytes(s3,reuse_key(old,'control/'+epoch+'/'+owner+'-capture.json')))
        # Original capture has integer /proc PIDs as numerical_before mapping keys.
        row['numerical_before']={int(k):v for k,v in row['numerical_before'].items()}
        body=(json.dumps(row,indent=2,sort_keys=True)+'\n').encode()
        require(hashlib.sha256(body).hexdigest()==expected,'exact capture hash mismatch '+owner)
        require(row['epoch']==epoch and row['config']['digest']==old,'wrong capture epoch')
        rows[owner]=row
    plan=make_epoch(previous,rows,old,bootstrap=bootstrap)
    root=pathlib.Path(config['out'])/'parallel-63';path=root/('reuse-ownership-'+epoch+'.json')
    require(not path.exists(),'ownership epoch already exists; inspect its commit before continuing')
    body=durable_json(path,plan);digest=hashlib.sha256(body).hexdigest()
    publish(s3,reuse_key(old,'control/'+epoch+'/assignment.json'),plan)
    original=(pathlib.Path(config['base'])/'full-context-audit/scripts/resume_multibox_candidate.py').read_text()
    proof=dict(status='committed',assignment_sha256=digest,captures=hashes,
        source_sha256=hashlib.sha256(reuse_source(original).encode()).hexdigest(),epoch=epoch)
    publish(s3,reuse_key(old,'control/'+epoch+'/commit.json'),proof)
    durable_json(root/('reuse-commit-'+epoch+'.json'),proof)
    print(json.dumps(dict(commit=proof,path=str(path),pending_transfers=plan['pending_transfers'])),flush=True)


def stage(config,epoch):
    from multibox_support import client
    from family_save_stop import get_bytes
    s3=client();old=config['digest'];root=pathlib.Path(config['out'])/'parallel-63'
    proof=optional_json(s3,reuse_key(old,'control/'+epoch+'/commit.json'))
    require(proof and proof['status']=='committed','epoch not committed')
    plan=json.loads(get_bytes(s3,reuse_key(old,'control/'+epoch+'/assignment.json')))
    path=root/('reuse-ownership-'+epoch+'.json')
    if path.exists():require(sha(path)==proof['assignment_sha256'],'immutable ownership file changed')
    else:durable_json(path,plan)
    require(sha(path)==proof['assignment_sha256'],'assignment read-back mismatch')
    print(json.dumps(dict(path=str(path),digest=proof['assignment_sha256'])),flush=True)


def capture(config,epoch):
    from multibox_support import prepared_cache_index,client
    from resume_multibox_candidate import committed,job_id
    base=pathlib.Path(config['base']);root=pathlib.Path(config['out'])/'parallel-63'
    require(imds_instance()==config['instance'],'wrong instance')
    require(sha(config['assignment'])==config['digest'],'assignment changed')
    plan=json.loads(pathlib.Path(config['assignment']).read_text());owner=config['owner']
    owned=cohorts_for_worker(None,plan,owner)
    state=json.loads(pathlib.Path(config['state']).read_text())
    require(state['status'] not in ('complete_candidate','global_fits_complete'),'finalization already began')
    require(not list(root.glob('box-*-import-receipt.json')),'prior imports prevent ownership handoff')
    alive=process_token(config['pid'])
    oldcmd=[]
    if alive is not None:
        _,oldcmd,st=identity(config['pid'])
        validate_coordinator(config,oldcmd,st[19],sha(coordinator_source(config)))
        require(state['status']!='shard_fits_complete','archive in progress; wait for verified reuse readiness')
    else:
        status=json.loads((pathlib.Path(config['run'])/'hook-status.json').read_text())
        require(status['status']=='backup_verified_ready_for_reuse','finished callback not yet verified/ready')
        require(status['assignment_sha256']==config['digest'],'stale reuse availability')
    subprocess.run(['systemctl','stop','family-save-stop.service'],check=True)
    paused=False
    try:
        if alive is not None:
            require(process_token(config['pid'])==config['token'],'coordinator identity race')
            os.kill(config['pid'],signal.SIGSTOP);paused=True
            deadline=time.monotonic()+5
            while identity(config['pid'])[2][0]!='T' and time.monotonic()<deadline:time.sleep(.02)
            require(identity(config['pid'])[2][0]=='T','dispatcher did not pause')
        jobs,numerical=capture_workers(base,root,set(owned),oldcmd)
        state=json.loads(pathlib.Path(config['state']).read_text())
        require(state['status'] not in ('complete_candidate','global_fits_complete'),'finalization started during fence')
        require(not list(root.glob('box-*-import-receipt.json')),'imports started during fence')
        require(not state.get('unregistered_cohorts'),'not all mandatory tasks registered')
        keys=task_set(state['required_jobs']);done=[]
        for kind,t,model in sorted(keys):
            require(task_owner(plan,(kind,t,model))==owner,'unowned capture key')
            if committed(root/'jobs'/job_id(t,kind,model),kind,t,model) or committed(root/'serial-prefix',kind,t,model,serial=True):
                done.append([kind,list(t),model])
        caches=prepared_cache_index(root,owned)
        infos=[dict(cohort=row['cohort'],info=json.loads((pathlib.Path(row['cache'])/'ready.json').read_text())) for row in caches]
        value=dict(epoch=epoch,owner=owner,config=config,old_coordinator_pid=config['pid'],old_coordinator_token=config['token'],
            old_coordinator_alive=alive is not None,jobs=jobs,numerical_before=numerical,previous_state=state,
            previous_run=config['run'],prepared_caches=caches,required=state['required_jobs'],committed=done,
            preparations=infos,unregistered=state.get('unregistered_cohorts',[]),source_sha256=sha(coordinator_source(config)))
        path=root/('reuse-capture-'+epoch+'-'+owner+'.json');durable_json(path,value)
        publish(client(),reuse_key(config['digest'],'control/'+epoch+'/'+owner+'-capture.json'),value)
        planner=dict(required=value['required'],committed=done,unregistered=value['unregistered'],preparations=infos,
            jobs=[{k:j[k] for k in ('kind','cohort','model')} for j in jobs])
        print(json.dumps(dict(path=str(path),sha256=sha(path),owner=owner,required=len(keys),committed=len(done),live=len(jobs),
            snapshot_gzip_base64=base64.b64encode(gzip.compress(json.dumps(planner).encode())).decode())),flush=True)
    except BaseException:
        if paused:os.kill(config['pid'],signal.SIGCONT)
        subprocess.run(['systemctl','start','family-save-stop.service'],check=True)
        raise


def launch(capture_path,assignment_path):
    from multibox_support import client
    from resume_multibox_candidate import committed,job_id,preserve_attempt
    snap=json.loads(capture_path.read_text());config=snap['config'];epoch=snap['epoch'];owner=config['owner']
    plan=json.loads(assignment_path.read_text());digest=sha(assignment_path)
    base=pathlib.Path(config['base']);root=pathlib.Path(config['out'])/'parallel-63'
    commit=optional_json(client(),reuse_key(config['digest'],'control/'+epoch+'/commit.json'))
    require(commit and commit['assignment_sha256']==digest and commit['captures'][owner]==sha(capture_path),'missing durable all-owner epoch commit')
    require(set(commit['captures'])==set(plan['instances']),'missing owner fence')
    require(plan['prior_assignment_sha256']==config['digest'],'wrong prior epoch')
    pinned=task_set(snap['committed'])|{(j['kind'],tuple(j['cohort']),j['model']) for j in snap['jobs'] if j['kind']!='prepare'}
    require(all(task_owner(plan,k)==owner for k in pinned),'live/completed ownership moved')
    target=base/'full-context-audit/scripts/resume_multibox_candidate.py';original=target.read_text()
    source=reuse_source(original);compile(source,'new coordinator','exec')
    variant=base/('reuse-epoch-'+epoch+'-'+owner);variant.mkdir(exist_ok=False)
    (variant/'resume_multibox_candidate.py').write_text(source)
    for name in ('multibox_support.py','family_save_stop.py','family_reuse_support.py'):
        origin=target.parent/name if name=='multibox_support.py' else pathlib.Path(__file__).parent/name
        shutil.copy2(origin,variant/name)
    require(hashlib.sha256(source.encode()).hexdigest()==commit['source_sha256'],'source not committed')
    if snap['old_coordinator_alive']:
        require(process_token(config['pid'])==config['token'] and identity(config['pid'])[2][0]=='T','old dispatcher fence lost')
        os.kill(config['pid'],signal.SIGKILL)
        deadline=time.monotonic()+10
        while pathlib.Path('/proc',str(config['pid'])).exists() and time.monotonic()<deadline:time.sleep(.05)
        require(not pathlib.Path('/proc',str(config['pid'])).exists(),'old dispatcher not reaped')
    import fcntl
    with (root/'recovery-executor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_UN)
    # A's final import must not collide with a retained partial pending folder.
    # Preserve those failed/unstarted attempts after the new authority is durable.
    for kind,t,model in task_set(snap['required'])-pinned:
        if task_owner(plan,(kind,t,model))==owner:continue
        folder=root/'jobs'/job_id(t,kind,model)
        if folder.exists() or folder.is_symlink():
            require(not committed(folder,kind,t,model),'pending artifact completed after capture; reconcile before transfer')
            preserve_attempt(root,folder,'reuse-'+epoch)
    log=pathlib.Path(config['out'])/('parallel-'+owner+'-reuse-'+epoch+'.log')
    before=[str(p) for p in root.glob('memory-recovery-*')]
    command=['python3',str(variant/'resume_multibox_candidate.py'),'--execute','--max-workers',str(plan['slots'][owner]),
        '--assignment',str(assignment_path),'--worker-id',owner,'--adopt-manifest',str(capture_path)]
    with log.open('a') as f:
        child=subprocess.Popen(command,env=dict(os.environ,FAMILY_BOX_INSTANCE_ID=config['instance'],FAMILY_COORDINATOR_LOG=str(log)),
            stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    receipt=dict(owner=owner,pid=child.pid,token=process_token(child.pid),source=str(variant/'resume_multibox_candidate.py'),
        source_sha256=sha(variant/'resume_multibox_candidate.py'),log=str(log),capture=str(capture_path),assignment=str(assignment_path),
        digest=digest,run_before=before,epoch=epoch)
    path=root/('reuse-launch-'+epoch+'-'+owner+'.json');durable_json(path,receipt)
    print(json.dumps(dict(path=str(path),pid=child.pid,token=receipt['token'],digest=digest)),flush=True)


def arm(launch_path):
    from resume_multibox_candidate import committed
    receipt=json.loads(launch_path.read_text());snap=json.loads(pathlib.Path(receipt['capture']).read_text());config=snap['config']
    root=pathlib.Path(config['out'])/'parallel-63';install=pathlib.Path(__file__).parent
    token=process_token(receipt['pid'])
    require(token in (None,receipt['token']),'replacement coordinator PID reused')
    runs=[p for p in root.glob('memory-recovery-*') if str(p) not in receipt['run_before'] and
          (p/'coordinator-source.py').is_file() and sha(p/'coordinator-source.py')==receipt['source_sha256']]
    require(len(runs)==1,'replacement recovery run not yet unique/ready')
    run=runs[0];state=json.loads((run/'recovery-plan.json').read_text())
    completion=json.loads((run/'shard-completion.json').read_text()) if token is None else None
    validate_replacement_exit(config,receipt,state,completion,token)
    accounted=[]
    for job in snap['jobs']:
        alive=process_token(job['pid'])==job['token']
        good=job['kind']!='prepare' and committed(pathlib.Path(job['folder']),job['kind'],tuple(job['cohort']),job['model'])
        require(alive or good,'captured worker neither alive nor coherent; recover before arming')
        accounted.append(dict(pid=job['pid'],token=job['token'],alive=alive,committed=good))
    for name in ('family_reuse_support.py','family_reuse_epoch.py','family_reuse_rollout.py','test_family_reuse.py','family_guarded_recovery.py'):
        shutil.copy2(install/name,run/name)
    shutil.copy2(receipt['capture'],run/'reuse-capture.json')
    shutil.copy2(launch_path,run/'reuse-launch.json')
    oldlog=pathlib.Path(config.get('coordinator_log',str(pathlib.Path(config['out'])/('parallel-four-'+config['owner']+'.log'))))
    shutil.copy2(oldlog,run/'previous-coordinator.log')
    config.update(pid=receipt['pid'],token=receipt['token'],coordinator_source=receipt['source'],
        coordinator_source_sha256=receipt['source_sha256'],coordinator_log=receipt['log'],run=str(run),state=str(run/'recovery-plan.json'),
        assignment=receipt['assignment'],digest=receipt['digest'],reuse_before_stop=True,
        prefix='host-deliveries/family-research-20261022/save-stop/'+receipt['digest']+'/')
    config['receipt_key']=config['prefix']+config['owner']+'-stop-proof.json'
    table=install/('reuse-config-'+receipt['epoch']+'.json');durable_json(table,[config])
    subprocess.run([sys.executable,str(install/'install_family_completion_hook.py'),str(table)],check=True,stdout=subprocess.DEVNULL)
    durable_json(run/'reuse-adoption-verification.json',dict(status='all_captured_workers_accounted',workers=accounted,config=config))
    print(json.dumps(dict(owner=config['owner'],run=str(run),pid=config['pid'],token=config['token'],accounted=len(accounted),
        required=len(state.get('required_jobs',[])),committed=len(state.get('committed_jobs',[])),status=state['status'])),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['capture','commit','stage','launch','arm','resume'])
    p.add_argument('--epoch');p.add_argument('--config',type=pathlib.Path,default=pathlib.Path(__file__).with_name('config.json'))
    p.add_argument('--capture',type=pathlib.Path);p.add_argument('--assignment',type=pathlib.Path);p.add_argument('--launch',type=pathlib.Path)
    p.add_argument('--captures-json',type=pathlib.Path);p.add_argument('--bootstrap',action='store_true')
    a=p.parse_args();config=json.loads(a.config.read_text());sys.path.insert(0,str(pathlib.Path(config['base'])/'full-context-audit/scripts'))
    if a.mode=='capture':capture(config,a.epoch)
    elif a.mode=='commit':commit_epoch(config,a.epoch,json.loads(a.captures_json.read_text()),a.bootstrap)
    elif a.mode=='stage':stage(config,a.epoch)
    elif a.mode=='launch':launch(a.capture,a.assignment)
    elif a.mode=='arm':arm(a.launch)
    else:
        from multibox_support import client
        s=json.loads(a.capture.read_text());require(optional_json(client(),reuse_key(s['config']['digest'],'control/'+s['epoch']+'/commit.json')) is None,'committed epoch cannot resume old authority')
        if s['old_coordinator_alive']:
            require(process_token(s['old_coordinator_pid'])==s['old_coordinator_token'],'stale coordinator')
            os.kill(s['old_coordinator_pid'],signal.SIGCONT)
        subprocess.run(['systemctl','start','family-save-stop.service'],check=True)


if __name__=='__main__':main()
