"""Arm the tested callback without editing or restarting numerical execution."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import time
from family_completion_hook import imds_instance, process_token
from family_save_stop import require, durable_json, get_bytes, BUCKET, ACCOUNT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('configs',type=pathlib.Path)
    args = parser.parse_args()
    table = json.loads(args.configs.read_text())
    identity = imds_instance()
    configs = [c for c in table if c['instance'] == identity]
    require(len(configs) == 1, 'unknown instance')
    config = configs[0]
    install = pathlib.Path(__file__).resolve().parent
    base = pathlib.Path(config['base'])
    import sys
    sys.path.insert(0,str(base/'full-context-audit/scripts'))
    from multibox_support import client, assignment_digest
    require(assignment_digest(config['assignment']) == config['digest'], 'assignment changed')
    require(process_token(config['pid']) in (None,config['token']), 'coordinator identity changed')
    run = pathlib.Path(config['run'])
    require(run.is_dir() and run.parent == pathlib.Path(config['out'])/'parallel-63', 'invalid recovery run')
    require(subprocess.run(['/usr/bin/systemctl','is-active','--quiet','family-save-stop.service']).returncode != 0,
            'completion callback already active; refuse duplicate')
    numerical_hashes = {n:hashlib.sha256((base/'full-context-audit/scripts'/n).read_bytes()).hexdigest()
                        for n in ('resume_multibox_candidate.py','multibox_support.py')}
    config['numerical_helper_sha256'] = numerical_hashes
    durable_json(install/'config.json',config)
    durable_json(run/'save-stop-config.json',config)
    sources = run/'save-stop-source'; sources.mkdir(exist_ok=True)
    hashes = {}
    for name in ('family_save_stop.py','family_completion_hook.py','family_final_backup.py',
                 'test_family_save_stop.py','test_family_completion.py','install_family_completion_hook.py'):
        shutil.copy2(install/name,sources/name)
        hashes[name] = hashlib.sha256((install/name).read_bytes()).hexdigest()
    reuse_source=install/'family_reuse_support.py'
    if reuse_source.is_file():
        shutil.copy2(reuse_source,sources/reuse_source.name)
        hashes[reuse_source.name]=hashlib.sha256(reuse_source.read_bytes()).hexdigest()
    attestation = dict(status='installed_tested_ready_to_arm',config=config,source_sha256=hashes,
                       numerical_source_sha256=numerical_hashes,shutdown_mocked_in_tests=True)
    body = durable_json(run/'save-stop-installation.json',attestation)
    s3 = client(); key = config['prefix']+config['owner']+'-installation.json'
    s3.put_object(Bucket=BUCKET,Key=key,Body=body,ContentType='application/json',
                  ServerSideEncryption='AES256',ExpectedBucketOwner=ACCOUNT)
    require(get_bytes(s3,key) == body, 'installation receipt read-back mismatch')
    unit = '\n'.join(['[Unit]','Description=Family candidate verified save before stop',
        'After=network-online.target','Wants=network-online.target','[Service]','Type=simple',
        'User=root','WorkingDirectory='+str(install),
        'ExecStart=/usr/bin/python3 '+str(install/'family_completion_hook.py')+' --config '+str(install/'config.json'),
        'Restart=no','Nice=10','IOSchedulingClass=idle','TimeoutStopSec=30',''])
    pathlib.Path('/etc/systemd/system/family-save-stop.service').write_text(unit)
    subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True)
    # Deliberately not enabled on reboot: a recovery must reconcile work and rearm
    # against the replacement coordinator, rather than use stale process identities.
    subprocess.run(['/usr/bin/systemctl','start','family-save-stop.service'],check=True)
    print(json.dumps(attestation),flush=True)


if __name__ == '__main__':
    main()
