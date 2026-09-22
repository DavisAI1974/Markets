"""Submit one isolated conformance-only recovery and retain Git/AWS receipts."""
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import time
import zipfile
import boto3

BUCKET='frankie-granite42-568968024170-us-east-1'
INSTANCE='i-035994afa8bdf66a5'

def main():
    run=os.environ['GITHUB_RUN_ID']
    commit=os.environ['GITHUB_SHA']
    prefix='readiness/20260922/sealed-recovery/'+run+'/'
    s3=boto3.client('s3',region_name='us-east-1')
    ssm=boto3.client('ssm',region_name='us-east-1')
    original=ssm.get_command_invocation(CommandId='eea87d2f-a1d7-428e-ab57-3fdab2980eb6',InstanceId=INSTANCE)
    if original['Status']!='Cancelled':
        raise RuntimeError('original ingest status changed')
    boundary=Path('source-boundary.json').read_bytes()
    # The boundary job must finish before this job; verification gate repeats in the remote CLI.
    parsed=json.loads(boundary)
    if parsed.get('verified') is not True:
        raise RuntimeError('source boundary not verified')
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(Path('research').rglob('*.py')):
            if p.is_symlink():
                raise ValueError('symbolic link in code bundle')
            archive.write(p,p.as_posix())
        archive.write('markets_adapter.py','markets_adapter.py')
        for name in ('BLOCK_20211004_SOURCE_MANIFEST.json',):
            p=Path('research/kalshi/frankie_boss/blocks')/name
            archive.write(p,p.as_posix())
        archive.writestr('source-boundary.json',boundary)
    bundle=raw.getvalue()
    sha=hashlib.sha256(bundle).hexdigest()
    preflight=Path('recovery-bundle-preflight').absolute()
    preflight.mkdir(exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        for info in archive.infolist():
            dest=preflight/info.filename
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as stream:stream.write(archive.read(info))
    # Isolated Python path proves the actual shipped archive carries transitive imports.
    script="import sys,runpy;sys.path.insert(0,sys.argv[1]);sys.argv=['sealed_recovery_run','--help'];runpy.run_module('research.kalshi.frankie_boss.sealed_recovery_run',run_name='__main__')"
    subprocess.run([sys.executable,'-I','-c',script,str(preflight)],cwd=preflight,check=True)
    s3.put_object(Bucket=BUCKET,Key=prefix+'code.zip',Body=bundle,IfNoneMatch='*',ServerSideEncryption='AES256')
    get=s3.generate_presigned_url('get_object',Params=dict(Bucket=BUCKET,Key=prefix+'code.zip'),ExpiresIn=21600)
    filenames=('source-boundary.json','builder-checkpoint.c15.json','completion.json','recovery-receipt.json','progress.jsonl')
    uploads={name:s3.generate_presigned_url('put_object',Params=dict(Bucket=BUCKET,Key=prefix+name),ExpiresIn=21600) for name in filenames}
    for url in (get,*uploads.values()):
        print('::add-mask::'+url,flush=True)
    config=dict(run=run,commit=commit,bundle_sha256=sha,bundle_bytes=len(bundle),get=get,uploads=uploads)
    # No shell checkout or installation. Only this new Linux work directory is written.
    bootstrap=Path('deploy/aws/box/frankie_box_recovery_bootstrap.py').read_text()
    script="export PYTHONDONTWRITEBYTECODE=1\n/opt/frankie-box/venv/bin/python - <<'SEALED_RECOVERY_BOOTSTRAP'\nCONFIG="+repr(config)+"\n"+bootstrap+"\nSEALED_RECOVERY_BOOTSTRAP\n"
    response=ssm.send_command(InstanceIds=[INSTANCE],DocumentName='AWS-RunShellScript',
        Parameters={'commands':[script],'executionTimeout':['21600']},TimeoutSeconds=21600,
        Comment='Conformance-only sealed Monday recovery; no source replay; original journal read-only')
    cid=response['Command']['CommandId']
    print('SSM_RECOVERY_COMMAND '+cid,flush=True)
    dispatch=dict(schema='FRANKIE_SEALED_RECOVERY_DISPATCH_V1',run_id=run,code_commit=commit,
        instance_id=INSTANCE,ssm_command_id=cid,bundle_sha256=sha,bundle_bytes=len(bundle),s3_prefix=prefix)
    dispatch_raw=(json.dumps(dispatch,sort_keys=True)+'\n').encode()
    Path('recovery-dispatch.json').write_bytes(dispatch_raw)
    s3.put_object(Bucket=BUCKET,Key=prefix+'dispatch.json',Body=dispatch_raw,IfNoneMatch='*',ServerSideEncryption='AES256')
    print('RECOVERY_DISPATCH '+dispatch_raw.decode(),flush=True)
    last=None
    while True:
        time.sleep(15)
        try:
            result=ssm.get_command_invocation(CommandId=cid,InstanceId=INSTANCE)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        try:
            progress=s3.get_object(Bucket=BUCKET,Key=prefix+'progress.jsonl')['Body'].read().decode()
            final=progress.strip().splitlines()[-1]
            if final!=last:
                print(final,flush=True)
                last=final
        except s3.exceptions.NoSuchKey:
            pass
        if result['Status'] not in ('Pending','InProgress','Delayed'):
            break
    print('SSM recovery status '+result['Status'],flush=True)
    if result['Status']!='Success':
        # Bootstrap/CLI suppress presigned URL errors. Preserve safe traceback from Python logic.
        print(result.get('StandardErrorContent',''),flush=True)
        raise RuntimeError('recovery did not finish; preserve attempt and inspect recorded evidence')
    for name in filenames:
        try:
            body=s3.get_object(Bucket=BUCKET,Key=prefix+name)['Body'].read()
        except s3.exceptions.NoSuchKey:
            if name=='progress.jsonl':
                continue
            raise
        Path(name).write_bytes(body)
    receipt=json.loads(Path('recovery-receipt.json').read_bytes())
    expected=dict(schema='FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1',status='complete',code_commit=commit,
        manifest_hash='a399377b5b005d989daa467048438437c47b8597dc8cfb5861c3706c6f92a355',
        record_count=2032203,journal_count=4064406,
        journal_hash='534f442aa0008032064c540f1c472433cb665a97bfec94399f8137ca103f207c',
        source_boundary_sha256=hashlib.sha256(boundary).hexdigest(),
        source_replays=0,adapter_apply_calls=0,parent_writes=0,original_ingest_status='Cancelled')
    if any(receipt.get(k)!=v for k,v in expected.items()):
        raise RuntimeError('recovered receipt differs from independently dispatched pins')
    container=receipt['container']
    if (container['sha256']!='947949d84732b0d7fa22b2e853ee89fdcfaf995955d9de652b36b344333b9888'
            or container['bytes']!=23687368704
            or container['path']!='/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite'):
        raise RuntimeError('recovered container differs from independent physical witness')
    for key,filename in (('checkpoint','builder-checkpoint.c15.json'),('completion','completion.json')):
        artifact=receipt['artifacts'][key]
        if artifact['file']!=filename:
            raise RuntimeError('unexpected recovery artifact path')
        body=Path(artifact['file']).read_bytes()
        if len(body)!=artifact['bytes'] or hashlib.sha256(body).hexdigest()!=artifact['sha256']:
            raise RuntimeError('published artifact identity differs from receipt')
    if receipt['status']!='complete':
        raise RuntimeError('recovery completion receipt required')
    print('RECOVERY_RECEIPT '+Path('recovery-receipt.json').read_text().replace('\n',''),flush=True)

if __name__=='__main__':
    main()
