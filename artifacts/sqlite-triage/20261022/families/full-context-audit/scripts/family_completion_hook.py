"""One finite exit callback for one exact running family coordinator."""
import argparse
import hashlib
import json
import os
import pathlib
import select
import shutil
import subprocess
import sys
import time
import urllib.request
from family_save_stop import (require, validate_shard, verify_remote, get_bytes,
                              durable_json, record_and_stop, task_set, BUCKET, ACCOUNT, GATE)


def read_json(path):
    return json.loads(pathlib.Path(path).read_text())


def process_token(pid):
    try:
        return pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]
    except FileNotFoundError:
        return None


def imds_instance():
    # Fixed local IMDS endpoint, no proxy or user-controlled URL.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request('http://169.254.169.254/latest/api/token',method='PUT',
                                headers={'X-aws-ec2-metadata-token-ttl-seconds':'60'})
    with opener.open(req,timeout=5) as r:
        token = r.read().decode()
    req = urllib.request.Request('http://169.254.169.254/latest/meta-data/instance-id',
                                headers={'X-aws-ec2-metadata-token':token})
    with opener.open(req,timeout=5) as r:
        return r.read().decode()


def wait_exact_exit(config):
    pid = int(config['pid'])
    token = process_token(pid)
    if token is None:
        return  # Completed between installation and service startup; proofs still mandatory.
    require(token == config['token'], 'coordinator PID identity changed')
    fd = os.pidfd_open(pid)
    try:
        # Reject PID reuse between identity check and pidfd_open.
        require(process_token(pid) in (None,config['token']), 'coordinator identity race')
        durable_json(pathlib.Path(config['run'])/'hook-status.json',
                     dict(status='waiting_for_exit',pid=pid,token=token,owner=config.get('owner')))
        poll = select.poll(); poll.register(fd,select.POLLIN)
        poll.poll()  # Kernel exit notification; no process/status polling loop.
    finally:
        os.close(fd)


def ensure_idle(base):
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        try:
            args = [s.decode(errors='replace') for s in (p/'cmdline').read_bytes().split(b'\0') if s]
            cmd = ' '.join(args)
            exe = (p/'exe').resolve().name
            python_worker = exe.startswith('python') and len(args) > 1 and (
                '--child-report' in args or
                (pathlib.Path(args[1]).name.startswith('resume_') and '--execute' in args))
            require(not (str(base) in cmd and (exe == 'julia' or python_worker)),
                    'live numerical process remains: '+p.name)
        except (FileNotFoundError,ProcessLookupError):
            pass


def verify_shards(s3, config, plan, owners):
    from multibox_support import object_key
    transfers, verified = {}, []
    root = pathlib.Path(config['out'])/'parallel-63'
    for owner in owners:
        key = object_key(config['digest'],owner+'-status.json')
        receipt = json.loads(get_bytes(s3,key))
        cfg = dict(config,owner=owner,instance=plan['instances'][owner])
        if config['owner'] == owner:
            state = read_json(pathlib.Path(config['run'])/'recovery-plan.json')
            require(read_json(root/('box-'+owner+'-transfer-receipt.json')) == receipt and
                    read_json(pathlib.Path(config['run'])/'shard-completion.json') == receipt,
                    'local/remote completion receipt mismatch')
            require(state.get('assignment_sha256') == config['digest'] and state.get('worker_id') == owner,
                    'state ownership mismatch')
            require(state.get('unregistered_cohorts') == [] and not state.get('deferred_memory_jobs') and
                    state.get('all_declared_tasks_mandatory') is True, 'mandatory work remains unregistered/deferred')
            from multibox_support import prepared_cache_index
            from resume_multibox_candidate import expected_models
            owned = [tuple(r['cohort']) for r in plan['cohorts'] if r['owner'] == owner]
            caches = prepared_cache_index(root,owned)
            require({tuple(r['cohort']) for r in caches} == set(owned), 'missing training preparation')
            expected = set()
            for row in caches:
                t = tuple(row['cohort'])
                info = read_json(pathlib.Path(row['cache'])/'ready.json')
                for kind,models in zip(('core','neural'),expected_models(t,info['groups'])):
                    expected.update((kind,t,m) for m in models)
            require(task_set(state['required_jobs']) == expected, 'training-derived mandatory tasks mismatch')
        else:
            # A already validated and imported these artifacts in its sole finalizer.
            state = dict(status='shard_fits_complete',coverage_gate=GATE,
                         required_jobs=receipt['required_jobs'],committed_jobs=receipt['required_jobs'])
        validate_shard(cfg,plan,state,receipt)
        verified.append(verify_remote(s3,object_key(config['digest'],owner+'-results.tar.gz'),
                                      receipt['archive_sha256'],receipt['archive_bytes']))
        transfers[owner] = receipt
    return transfers,verified


def save_final(s3,config,plan):
    from boto3.s3.transfer import TransferConfig
    from family_final_backup import validate_final, pack_final
    from multibox_support import sha_file
    transfers, verified = verify_shards(s3,config,plan,['B','C','D'])
    state = read_json(pathlib.Path(config['run'])/'recovery-plan.json')
    coverage,remote_roots = validate_final(config,plan,state,transfers)
    candidates = [pathlib.Path(config['base'])/'save-stop-archives-20261022']
    if pathlib.Path('/opt/frankie-box/archive').is_dir():
        candidates.append(pathlib.Path('/opt/frankie-box/archive/family-save-stop-20261022'))
    for p in candidates:
        p.mkdir(exist_ok=True,parents=True)
    storage = max(candidates,key=lambda p:shutil.disk_usage(p).free)
    # Keep each backup attempt; a failed partial is never mistaken for verification.
    name = 'A-final-'+str(time.time_ns())
    archive = storage/(name+'.tar.gz')
    manifest = pack_final(config['out'],archive,remote_roots)
    key = config['prefix']+name+'.tar.gz'
    sha = sha_file(archive); length = archive.stat().st_size
    s3.upload_file(str(archive),BUCKET,key,
                  ExtraArgs={'ServerSideEncryption':'AES256','ExpectedBucketOwner':ACCOUNT},
                  Config=TransferConfig(max_concurrency=4,multipart_chunksize=64*1024**2))
    verified.append(verify_remote(s3,key,sha,length))
    return dict(backup_verified=True,owner='A',coverage=coverage,archives=verified,
                collection=manifest,shard_receipts=transfers,
                local_archive=str(archive),coverage_gate=GATE)


def run(config, shutdown=None):
    import fcntl
    from multibox_support import assignment_digest, client
    runpath = pathlib.Path(config['run'])
    with (runpath/'save-stop.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(imds_instance() == config['instance'], 'IMDS instance mismatch')
        require(config['shutdown_behavior_verified'] == 'stop', 'stop behavior not verified')
        for name,expected in config.get('numerical_helper_sha256',{}).items():
            require(hashlib.sha256((pathlib.Path(config['base'])/'full-context-audit/scripts'/name).read_bytes()).hexdigest()
                    == expected, 'numerical helper changed')
        require(assignment_digest(config['assignment']) == config['digest'], 'assignment changed')
        plan = read_json(config['assignment'])
        require(plan['instances'][config['owner']] == config['instance'], 'owner changed')
        token = process_token(config['pid'])
        if token is not None:
            cmd = pathlib.Path('/proc',str(config['pid']),'cmdline').read_bytes().split(b'\0')
            require(str(pathlib.Path(config['base'])/'full-context-audit/scripts/resume_multibox_candidate.py').encode() in cmd
                    and b'--execute' in cmd and cmd[cmd.index(b'--worker-id')+1].decode() == config['owner'],
                    'unexpected coordinator command')
        wait_exact_exit(config)
        ensure_idle(config['base'])
        s3 = client()
        durable_json(runpath/'hook-status.json',dict(status='validating_and_backing_up',owner=config['owner']))
        if config['owner'] == 'A':
            proof = save_final(s3,config,plan)
        else:
            transfers,verified = verify_shards(s3,config,plan,[config['owner']])
            proof = dict(backup_verified=True,owner=config['owner'],archives=verified,
                         shard_receipts=transfers,coverage_gate=GATE)
        proof.update(instance=config['instance'],assignment_sha256=config['digest'],
                     coordinator_pid=config['pid'],coordinator_start_token=config['token'],
                     verified_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                     shutdown='systemctl poweroff; EC2 instance-initiated behavior stop; retain EBS')
        def stop():
            # Fresh quiescence/identity check immediately before OS shutdown.
            ensure_idle(config['base'])
            require(imds_instance() == config['instance'], 'instance changed before stop')
            durable_json(runpath/'hook-status.json',dict(status='backup_verified_stop_requested',owner=config['owner']))
            os.sync()
            if shutdown is not None:
                shutdown()
            else:
                subprocess.run(['/usr/bin/systemctl','poweroff'],check=True)
        record_and_stop(s3,config,proof,stop)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=pathlib.Path,required=True)
    args = parser.parse_args()
    config = read_json(args.config)
    sys.path.insert(0,str(pathlib.Path(config['base'])/'full-context-audit/scripts'))
    try:
        run(config)
    except BaseException as error:
        # Never stop on failure. Preserve a compact failure both locally and remotely.
        failure = dict(status='save_stop_failed_retained',error=repr(error),owner=config['owner'],
                       instance=config['instance'],coverage_gate=GATE)
        body = durable_json(pathlib.Path(config['run'])/'hook-status.json',failure)
        try:
            from multibox_support import client
            client().put_object(Bucket=BUCKET,Key=config['prefix']+config['owner']+'-failure.json',
                                Body=body,ServerSideEncryption='AES256',ExpectedBucketOwner=ACCOUNT)
        except Exception as upload_error:
            print('Failure retained locally; remote receipt failed: '+repr(upload_error),flush=True)
        raise


if __name__ == '__main__':
    main()
