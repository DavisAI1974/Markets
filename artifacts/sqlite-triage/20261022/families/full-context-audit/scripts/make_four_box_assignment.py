"""Build the immutable expansion only from both paused dispatch snapshots."""
import pathlib,json,hashlib,time,collections
import boto3
from multibox_support import expand_assignment
B=pathlib.Path('/opt/frankie-box/work/family-research-20261022')
R=B/'joint-models-v4-candidate-20261022/parallel-63'
s3=boto3.client('s3',region_name='us-east-1')
bucket='frankie-granite42-568968024170-us-east-1'
prefix='host-deliveries/family-research-20261022/four-box-expansion-20261022/'
captures={}
for owner in ['A','B']:
    r=s3.get_object(Bucket=bucket,Key=prefix+owner+'-capture.json',ExpectedBucketOwner='568968024170')
    assert r['ContentLength']<20*1024**2
    captures[owner]=json.loads(r['Body'].read())
oldpath=R/'dual-box-ownership-20261022T190758Z.json'
old=json.loads(oldpath.read_text())
old['assignment_sha256']=hashlib.sha256(oldpath.read_bytes()).hexdigest()
assert old['assignment_sha256']=='1ff29d49200435fb536638751def689e7f687fa3152a6b243036af820650d131'
plan=expand_assignment(old,{o:c['previous_state'] for o,c in captures.items()},
    {o:c['jobs'] for o,c in captures.items()},
    {'C':'i-031eeb577ad72b064','D':'i-0d17573dbce871520'},
    {'A':96,'B':96,'C':32,'D':32})
plan.update(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
    numerical_source_sha256=old['numerical_source_sha256'],outcome_sha256=old['outcome_sha256'])
path=R/'four-box-ownership-20261022.json'
with path.open('x') as f:json.dump(plan,f,indent=2)
data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
s3.put_object(Bucket=bucket,Key=prefix+'ownership.json',Body=data,
    ServerSideEncryption='AES256',ExpectedBucketOwner='568968024170')
receipt=dict(utc=plan['created_utc'],assignment=str(path),assignment_sha256=digest,
    cohorts_by_owner=dict(collections.Counter(r['owner'] for r in plan['cohorts'])),
    pinned_existing_cohorts=len(plan['pinned_existing_cohorts']),
    source_numerical_workers={o:len(c['numerical_before']) for o,c in captures.items()},
    source_committed={o:len(c['previous_state']['committed_jobs']) for o,c in captures.items()},
    all_active_and_registered_cohorts_preserved=True,coverage_gate='NOT_PASSED')
(R/'four-box-assignment-receipt-20261022.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))

