import boto3,json,os,time
from botocore.config import Config
from pathlib import Path
s3=boto3.client('s3',region_name='us-east-1',config=Config(signature_version='s3v4'))
ssm=boto3.client('ssm',region_name='us-east-1')
bucket='frankie-granite42-568968024170-us-east-1'
prefix='readiness/20260922/sealed-recovery/'+os.environ['GITHUB_RUN_ID']+'/'
names=('publication-probe.json','progress.jsonl','source-boundary.json','builder-checkpoint.c15.json',
       'completion.json','publication-receipt.json','recovery-receipt.json')
urls={name:s3.generate_presigned_url('put_object',Params=dict(Bucket=bucket,Key=prefix+name),ExpiresIn=21600) for name in names}
for url in urls.values():
    if 'X-Amz-Algorithm=AWS4-HMAC-SHA256' not in url:raise ValueError('SigV4 publication required')
    print('::add-mask::'+url,flush=True)
config=dict(uploads=urls,commit=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'])
code=Path('deploy/aws/box/frankie_box_publish_recovery.py').read_text()
script="/opt/frankie-box/venv/bin/python - <<'PUBLISH_RETAINED_RECOVERY'\nCONFIG="+repr(config)+"\n"+code+"\nPUBLISH_RETAINED_RECOVERY\n"
cid=ssm.send_command(InstanceIds=['i-035994afa8bdf66a5'],DocumentName='AWS-RunShellScript',
    Parameters={'commands':[script],'executionTimeout':['21600']},TimeoutSeconds=21600,
    Comment='Publish retained recovery artifacts only; no journal scan or replay')['Command']['CommandId']
dispatch=dict(schema='FRANKIE_RECOVERY_PUBLICATION_DISPATCH_V1',ssm_command_id=cid,instance_id='i-035994afa8bdf66a5',
    run_id=os.environ['GITHUB_RUN_ID'],computation_run_id=35796793428,code_commit=os.environ['GITHUB_SHA'],s3_prefix=prefix)
print('PUBLICATION_DISPATCH '+json.dumps(dispatch),flush=True)
s3.put_object(Bucket=bucket,Key=prefix+'dispatch.json',Body=json.dumps(dispatch).encode(),IfNoneMatch='*',ServerSideEncryption='AES256')
last=None
while True:
    time.sleep(15)
    try:r=ssm.get_command_invocation(CommandId=cid,InstanceId=dispatch['instance_id'])
    except ssm.exceptions.InvocationDoesNotExist:continue
    try:
        progress=s3.get_object(Bucket=bucket,Key=prefix+'progress.jsonl')['Body'].read().decode().strip().splitlines()[-1]
        if progress!=last:print(progress,flush=True);last=progress
    except s3.exceptions.NoSuchKey:pass
    if r['Status'] not in ('Pending','InProgress','Delayed'):break
if r['Status']!='Success':
    print(r.get('StandardErrorContent',''),flush=True)
    raise RuntimeError('retained artifact publication failed; no recomputation allowed')
for name in names:
    try:body=s3.get_object(Bucket=bucket,Key=prefix+name)['Body'].read()
    except s3.exceptions.NoSuchKey:
        if name=='progress.jsonl':continue
        raise
    with Path(name).open('xb') as stream:stream.write(body)
print('RECOVERY_RECEIPT '+Path('recovery-receipt.json').read_text().replace('\n',''),flush=True)
print('PUBLICATION_RECEIPT '+Path('publication-receipt.json').read_text(),flush=True)
