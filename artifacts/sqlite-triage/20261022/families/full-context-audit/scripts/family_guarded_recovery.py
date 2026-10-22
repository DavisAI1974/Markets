"""Recover A after a global OOM while adopting every surviving fit unchanged."""
import argparse
import hashlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
from family_save_stop import require, durable_json, get_bytes, BUCKET, ACCOUNT


def guarded_source(source):
    replacements=[
        ("if args.worker_id!='A' and time.monotonic()-last_dispatch < 3:",
         "if time.monotonic()-last_dispatch < 3:"),
        ('Budget(total, 64*GIB','Budget(total, 192*GIB'),
        ('memory_reserve_gib=64','memory_reserve_gib=192')]
    for old,new in replacements:
        require(source.count(old)==1,'unexpected coordinator source; refuse patch')
        source=source.replace(old,new)
    return source


def validate_capture(jobs,owned,numerical):
    keys=[(j['kind'],tuple(j['cohort']),j['model']) for j in jobs]
    require(len(set(keys))==len(keys),'duplicate captured task')
    require(len({j['cpu'] for j in jobs})==len(jobs),'duplicate captured CPU lease')
    require(all(tuple(j['cohort']) in owned for j in jobs),'captured unowned cohort')
    require(all(v['parent'] in {j['pid'] for j in jobs} for v in numerical.values()),
            'unowned live Julia process; retain original coordinator')


def identity(pid):
    p=pathlib.Path('/proc',str(pid))
    return p,(p/'cmdline').read_bytes().split(b'\0'),(p/'stat').read_text().rsplit(')',1)[1].split()


def capture_workers(base,root,owned,oldcmd):
    fallback={}
    if b'--adopt-manifest' in oldcmd:
        old=json.loads(pathlib.Path(oldcmd[oldcmd.index(b'--adopt-manifest')+1].decode()).read_text())
        fallback={j['folder']:j['cpu'] for j in old['jobs']}
    wrappers,numerical={},{}
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            pid=int(p.name);p,cmd,st=identity(pid)
            if not cmd or not cmd[0] or st[0]=='Z':continue
            exe=(p/'exe').resolve().name
            if exe!='julia' and not (exe.startswith('python') and b'--child-report' in cmd):continue
            env=dict(v.split(b'=',1) for v in (p/'environ').read_bytes().split(b'\0') if b'=' in v)
            if env.get(b'FAMILY_RESEARCH_DIR',b'').decode()!=str(base):continue
            if exe=='julia':
                numerical[pid]=dict(parent=int(st[1]),token=st[19],cpu=sorted(os.sched_getaffinity(pid)))
            else:wrappers[pid]=(cmd,st,env)
        except (OSError,ValueError,ProcessLookupError):continue
    jobs=[]
    for pid,(cmd,st,env) in wrappers.items():
        folder=env[b'JOINT_MODEL_OUT'].decode();cache=env[b'COHORT_CACHE'].decode()
        cohort=env[b'MODEL_COHORT'].decode().split('|');model=env.get(b'MODEL_NAME',b'').decode()
        kind='prepare' if env.get(b'PREP_ONLY')==b'1' else (
            'neural' if any(b'run_neural_task.jl' in c for c in cmd) else 'core')
        require(len(cohort)==3 and pathlib.Path(folder).is_relative_to(root) and
                pathlib.Path(cache).is_relative_to(root),'wrapper output/cache outside candidate')
        require(kind=='prepare' or pathlib.Path(folder).parent==root/'jobs','unexpected fit folder')
        children=[(n,v) for n,v in numerical.items() if v['parent']==pid]
        require(len(children)<=1,'unexpected Julia child count')
        affinity=children[0][1]['cpu'] if children else sorted(os.sched_getaffinity(pid))
        cpu=affinity[0] if len(affinity)==1 else fallback[folder]
        jobs.append(dict(pid=pid,token=st[19],report=cmd[cmd.index(b'--child-report')+1].decode(),
            request=0,folder=folder,cache=cache,kind=kind,cohort=cohort,model=model,cpu=cpu,
            command=[c.decode() for c in cmd if c],numerical_children=[n for n,v in children]))
    # Ignore only processes that finished during the capture; no live orphan may vanish.
    live={}
    for pid,value in numerical.items():
        try:
            if identity(pid)[2][19]==value['token']:live[pid]=value
        except FileNotFoundError:pass
    validate_capture(jobs,owned,live)
    return jobs,live


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=pathlib.Path,required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();config=json.loads(args.config.read_text())
    base=pathlib.Path(config['base']);root=pathlib.Path(config['out'])/'parallel-63'
    sys.path.insert(0,str(base/'full-context-audit/scripts'))
    from multibox_support import client,assignment_digest,prepared_cache_index
    from family_completion_hook import imds_instance
    require(config['owner']=='A' and imds_instance()==config['instance'],'wrong instance')
    require(assignment_digest(config['assignment'])==config['digest'],'assignment changed')
    plan=json.loads(pathlib.Path(config['assignment']).read_text())
    owned={tuple(r['cohort']) for r in plan['cohorts'] if r['owner']=='A'}
    target=base/'full-context-audit/scripts/resume_multibox_candidate.py'
    original=target.read_text();source=guarded_source(original)
    _,oldcmd,st=identity(config['pid'])
    require(st[19]==config['token'] and str(target).encode() in oldcmd and b'--execute' in oldcmd,
            'unexpected original coordinator identity')
    if not args.execute:
        print(json.dumps(dict(status='plan_only',max_workers=96,host_floor_gib=192,dispatch_interval_s=3)))
        return
    oldlog=pathlib.Path(config['out'])/'parallel-four-A.log'
    failure_tail=subprocess.check_output(['tail','-n','12',str(oldlog)],text=True)
    require('"returncode": 125' in failure_tail,'expected failure-drain evidence missing')
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    variant=base/('guarded-recovery-A-'+stamp);variant.mkdir()
    (variant/'resume_multibox_candidate.py').write_text(source)
    (variant/'multibox_support.py').write_bytes((target.parent/'multibox_support.py').read_bytes())
    subprocess.run(['systemctl','stop','family-save-stop.service'],check=True)
    paused,retired=False,False
    try:
        require(identity(config['pid'])[2][19]==config['token'],'coordinator changed before pause')
        os.kill(config['pid'],signal.SIGSTOP);paused=True
        deadline=time.monotonic()+5
        while identity(config['pid'])[2][0]!='T' and time.monotonic()<deadline:time.sleep(.02)
        require(identity(config['pid'])[2][0]=='T','coordinator did not pause')
        jobs,numerical=capture_workers(base,root,owned,oldcmd)
        state=json.loads(pathlib.Path(config['state']).read_text())
        value=dict(utc=stamp,owner='A',instance=config['instance'],old_coordinator_pid=config['pid'],
            old_coordinator_token=config['token'],jobs=jobs,numerical_before=numerical,
            previous_state=state,previous_run=config['run'],prepared_caches=prepared_cache_index(root,owned),
            reason='global OOM 2026-10-22T21:12:49Z; original coordinator draining after missing wrapper report125',
            original_source_sha256=hashlib.sha256(original.encode()).hexdigest(),
            guarded_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            max_workers=96,dispatch_interval_s=3,host_floor_gib=192,per_job_memory_caps='unlimited')
        value['failure_log_tail']=failure_tail
        kernel=subprocess.run(['journalctl','-k','--since','2026-10-22 21:00:00 UTC','--no-pager','-o','short-iso'],
                              capture_output=True,text=True)
        value['kernel_oom_evidence']=[line for line in kernel.stdout.splitlines()
            if any(text in line.lower() for text in ('out of memory','killed process','oom-kill'))][-6:]
        manifest=root/('guarded-A-capture-'+stamp+'.json')
        body=durable_json(manifest,value)
        s3=client();key=config['prefix']+'A-recovery-capture-'+stamp+'.json'
        s3.put_object(Bucket=BUCKET,Key=key,Body=body,ServerSideEncryption='AES256',ExpectedBucketOwner=ACCOUNT)
        require(get_bytes(s3,key)==body,'capture read-back mismatch')
        durable_json(pathlib.Path(config['run'])/'hook-status.json',
                     dict(status='disarmed_for_guarded_recovery',manifest=str(manifest),reason=value['reason']))
        require(identity(config['pid'])[2][19]==config['token'],'coordinator changed before retirement')
        os.kill(config['pid'],signal.SIGKILL);retired=True
        deadline=time.monotonic()+10
        while pathlib.Path('/proc',str(config['pid'])).exists() and time.monotonic()<deadline:time.sleep(.05)
        require(not pathlib.Path('/proc',str(config['pid'])).exists(),'old coordinator not reaped')
        import fcntl
        with (root/'recovery-executor.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(lock,fcntl.LOCK_UN)
        log=pathlib.Path(config['out'])/('parallel-A-guarded-'+stamp+'.log')
        command=['python3',str(variant/'resume_multibox_candidate.py'),'--execute','--max-workers','96',
                 '--assignment',config['assignment'],'--worker-id','A','--adopt-manifest',str(manifest)]
        with log.open('a') as f:
            child=subprocess.Popen(command,env=dict(os.environ,FAMILY_BOX_INSTANCE_ID=config['instance'],
                FAMILY_COORDINATOR_LOG=str(log)),stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        token=identity(child.pid)[2][19]
        receipt=dict(status='replacement_started',new_pid=child.pid,new_token=token,old_pid=config['pid'],
                     source=str(variant/'resume_multibox_candidate.py'),log=str(log),manifest=str(manifest),
                     live_wrappers_captured=len(jobs),live_julia_captured=len(numerical),max_workers=96,
                     dispatch_interval_s=3,host_floor_gib=192,per_job_memory_caps='unlimited',
                     original_source_unchanged=target.read_text()==original)
        durable_json(root/('guarded-A-launch-'+stamp+'.json'),receipt)
        print(json.dumps(receipt),flush=True)
    except BaseException:
        if paused and not retired:
            os.kill(config['pid'],signal.SIGCONT)
            subprocess.run(['systemctl','start','family-save-stop.service'],check=True)
        raise


if __name__=='__main__':main()
