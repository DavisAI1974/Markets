import boto3,json,os,time
from pathlib import Path
s=boto3.client('ssm',region_name='us-east-1')
i='i-035994afa8bdf66a5'
prior=s.get_command_invocation(CommandId='eea87d2f-a1d7-428e-ab57-3fdab2980eb6',InstanceId=i)
if prior['Status']!='Cancelled':raise RuntimeError('original ingest status changed')
script="export PYTHONDONTWRITEBYTECODE=1\n/opt/frankie-box/venv/bin/python - <<'RECOVERY_AUDIT_PY'\n"+Path('deploy/aws/box/frankie_box_recovery_audit.py').read_text()+"\nRECOVERY_AUDIT_PY\n"
cid=s.send_command(InstanceIds=[i],DocumentName='AWS-RunShellScript',Parameters={'commands':[script],'executionTimeout':['900']},TimeoutSeconds=950,Comment='Read-only retained Monday journal recovery identity audit')['Command']['CommandId']
print('SSM recovery audit command '+cid,flush=True)
while True:
 time.sleep(5)
 try:r=s.get_command_invocation(CommandId=cid,InstanceId=i)
 except s.exceptions.InvocationDoesNotExist:continue
 if r['Status'] not in ('Pending','InProgress','Delayed'):break
print(r.get('StandardOutputContent',''),flush=True)
print('SSM recovery audit status '+r['Status'],flush=True)
if r['Status']!='Success':raise RuntimeError('audit failed; inspect SSM receipt')
line=next(x for x in r['StandardOutputContent'].splitlines() if x.startswith('RECOVERY_AUDIT '))
raw=line[len('RECOVERY_AUDIT '):].encode()
Path('recovery-input-audit.json').write_bytes(raw+b'\n')
key='readiness/20260922/sealed-recovery/'+os.environ['GITHUB_RUN_ID']+'/input-audit.json'
boto3.client('s3',region_name='us-east-1').put_object(Bucket='frankie-granite42-568968024170-us-east-1',Key=key,Body=raw+b'\n',IfNoneMatch='*',ServerSideEncryption='AES256',ContentType='application/json')
print('AWS receipt '+key)
