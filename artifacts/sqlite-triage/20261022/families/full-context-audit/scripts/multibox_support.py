"""Disjoint cohort ownership and one-time receipt/state transfer for four boxes."""
import collections
import hashlib
import json
import os
import pathlib
import posixpath
import shutil
import tarfile
import time
import uuid

BUCKET = 'frankie-granite42-568968024170-us-east-1'
PREFIX = 'host-deliveries/family-research-20261022/dual-box/'
ACCOUNT = '568968024170'
GIB = 1024**3

def expand_assignment(previous, states, active, extra_instances, slots):
    """Move only untouched cohorts; capacity weights guide placement, never admission."""
    old={tuple(r['cohort']):r['owner'] for r in previous['cohorts']}
    if len(old)!=63 or len(previous['cohorts'])!=63 or set(states)!={'A','B'}:
        raise ValueError('invalid previous ownership')
    instances=dict(previous['instances'],**extra_instances)
    if set(instances)!={'A','B','C','D'} or set(slots)!=set(instances):
        raise ValueError('exactly four instance identities and slot counts required')
    pinned=set();counts=collections.Counter();done=collections.Counter()
    for owner,s in states.items():
        registered={tuple(t) for k,t,m in s['required_jobs']}
        unknown={tuple(t) for t in s['unregistered_cohorts']}
        owned={t for t,o in old.items() if o==owner}
        if registered & unknown or registered | unknown != owned:
            raise ValueError('source state must cover its exact existing ownership')
        live={tuple(j['cohort']) for j in active[owner]}
        if not live<=owned:raise ValueError('live work on wrong owner')
        pinned.update(registered|live)
        counts.update(tuple(t) for k,t,m in s['required_jobs'])
        done.update(tuple(t) for k,t,m in s['committed_jobs'])
        if not set(map(task_key,s['committed_jobs']))<=set(map(task_key,s['required_jobs'])):
            raise ValueError('committed task absent from mandatory registry')
    weights={'2':.19,'3':.20,'4':1.0}
    def task_count(t):return 29 if t[0]=='first_observed_family_within_h' else 34
    owners={t:old[t] for t in pinned};load={o:0. for o in instances}
    for t in pinned:load[old[t]]+=max(0,counts[t]-done[t] if t in counts else task_count(t))*weights[t[2]]
    for t in sorted(set(old)-pinned,key=lambda t:(-weights[t[2]],t)):
        owner=min(load,key=lambda o:(load[o]/slots[o],o))
        owners[t]=owner;load[owner]+=task_count(t)*weights[t[2]]
    if set(owners.values())!=set(instances):
        raise ValueError('insufficient untouched work for every added box')
    return dict(version=2,instances=instances,slots=slots,coverage_gate='NOT_PASSED',
        run_id=uuid.uuid4().hex,forecast_load=load,
        balancing_forecasts_do_not_limit_admission=True,
        prior_assignment_sha256=previous.get('assignment_sha256'),
        pinned_existing_cohorts=[list(t) for t in sorted(pinned)],
        cohorts=[dict(cohort=list(t),owner=owners[t]) for t in sorted(owners)])

def prepared_cache_index(root, cohorts):
    root=pathlib.Path(root)
    parents=[root/'cache']
    for run in root.glob('memory-recovery-*'):
        parents.extend(run.glob('rebuilt-cache-*'))
    result=[]
    for t in cohorts:
        name=t[0].replace('_','-')+'-h'+t[1]+'-fold'+t[2]
        candidates=[p/name for p in parents if (p/name/'ready.json').is_file()]
        if candidates:
            def priority(p):
                return (all((p/n).is_file() for n in ['a.bin','b.bin']),
                        (p/'ready.json').stat().st_mtime_ns)
            result.append(dict(cohort=list(t),cache=str(max(candidates,key=priority))))
    return result

def require_dispatch_ready(path, worker):
    digest=assignment_digest(path);s3=client()
    for owner in (['A'] if worker=='B' else ['A','B']):
        r=get_json(s3,digest,owner+'-ready.json')
        if not r or r.get('assignment_sha256')!=digest:
            raise RuntimeError(owner+' restricted dispatch must be ready before '+worker)

def task_key(row):
    kind, cohort, model = row
    return kind, tuple(cohort), model

def make_assignment(state, instances):
    required = state['required_jobs']
    registered = {tuple(t) for k,t,m in required}
    unknown = {tuple(t) for t in state['unregistered_cohorts']}
    if registered & unknown or len(registered | unknown) != 63:
        raise ValueError('expected complete disjoint 63-cohort registry')
    pinned = {tuple(t) for t in state.get('pinned_cohorts',[])}
    if not pinned <= registered | unknown:
        raise ValueError('pinned cohort outside frozen registry')
    fixed = registered | pinned
    unknown -= pinned
    done = collections.Counter(tuple(t) for k,t,m in state['committed_jobs'])
    counts = collections.Counter(tuple(t) for k,t,m in required)
    weights = {'2':.19,'3':.20,'4':1.0}
    owners = {t:'A' for t in fixed}
    load = dict(A=sum(((counts[t]-done[t]) if t in registered else 34)*weights[t[2]] for t in fixed), B=0.)
    for t in sorted(unknown, key=lambda t:(-weights[t[2]],t)):
        owner = min(load, key=lambda k:(load[k],k))
        owners[t] = owner
        load[owner] += (30 if t[0]=='first_observed_family_within_h' else 34)*weights[t[2]]
    return dict(version=1, instances=instances, coverage_gate='NOT_PASSED',
        run_id=uuid.uuid4().hex, forecast_load=load,
        balancing_forecasts_do_not_limit_admission=True,
        cohorts=[dict(cohort=list(t),owner=owners[t]) for t in sorted(owners)])

def assigned_cohorts(cohorts, assignment, worker):
    rows = assignment['cohorts']
    pairs = [(tuple(r['cohort']),r['owner']) for r in rows]
    if len(pairs)!=63 or len({t for t,o in pairs})!=63 or set(t for t,o in pairs)!=set(cohorts):
        raise ValueError('ownership does not cover exactly the frozen cohorts')
    if set(assignment['instances']) != {'A','B','C','D'} or any(o not in assignment['instances'] for t,o in pairs) or worker not in assignment['instances']:
        raise ValueError('unknown owner')
    if assignment.get('coverage_gate')!='NOT_PASSED':
        raise ValueError('semantic gate cannot be promoted')
    result = [t for t,o in pairs if o==worker]
    if not result or len(result)==63:
        raise ValueError('both boxes must own work')
    return sorted(result)

def reconcile_keys(left, right, required):
    a,b,expected = [set(map(task_key,x)) for x in [left,right,required]]
    if len(a)!=len(left) or len(b)!=len(right) or len(expected)!=len(required) or a & b or a | b != expected:
        raise ValueError('overlap or incomplete mandatory task union')

def validate_members(members):
    for member in members:
        name = member.name
        path = pathlib.PurePosixPath(name)
        top = path.parts[0] if path.parts else ''
        if path.is_absolute() or '..' in path.parts or not (
                top in ['jobs','cache','attempts'] or top.startswith('memory-recovery-')):
            raise ValueError('unsafe artifact path: '+name)
        if not (member.isfile() or member.isdir() or member.issym()):
            raise ValueError('unsupported artifact type')
        if member.issym():
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name),member.linkname))
            if member.linkname.startswith('/') or target=='..' or target.startswith('../'):
                raise ValueError('artifact link escapes shard')

def assignment_digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def client():
    import boto3
    from botocore.config import Config
    return boto3.client('s3',region_name='us-east-1',
        config=Config(connect_timeout=10,read_timeout=120,retries={'max_attempts':5}))

def object_key(digest, name):
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('invalid assignment digest')
    return PREFIX+digest+'/'+name

def put_json(s3,digest,name,value):
    s3.put_object(Bucket=BUCKET,Key=object_key(digest,name),
        Body=json.dumps(value).encode(),ContentType='application/json',
        ServerSideEncryption='AES256',ExpectedBucketOwner=ACCOUNT)

def get_json(s3,digest,name):
    try:
        r=s3.get_object(Bucket=BUCKET,Key=object_key(digest,name),ExpectedBucketOwner=ACCOUNT)
        if r['ContentLength']>20*1024**2:
            raise ValueError('oversized completion receipt')
        return json.loads(r['Body'].read())
    except s3.exceptions.NoSuchKey:
        return None

def announce_ready(path,worker,instance):
    digest=assignment_digest(path)
    put_json(client(),digest,worker+'-ready.json',dict(assignment_sha256=digest,
        worker=worker,instance=instance,pid=os.getpid(),coverage_gate='NOT_PASSED'))

def require_a_ready(path):
    digest=assignment_digest(path)
    r=get_json(client(),digest,'A-ready.json')
    if not r or r.get('assignment_sha256')!=digest:
        raise RuntimeError('A restricted dispatch must be ready before B starts')

def pack_results(root,locations,archive):
    root=pathlib.Path(root).resolve()
    members={}
    def add(path):
        path=pathlib.Path(path)
        rel=path.relative_to(root).as_posix()
        if rel in members or path.name in ['a.bin','b.bin','model_outcomes.csv']:
            return
        if path.is_symlink():
            target=path.resolve(strict=True)
            target.relative_to(root)
            add(target)
        members[rel]=path
    for folder in locations.values():
        folder=pathlib.Path(folder)
        if folder.parent!=root/'jobs':
            raise ValueError('B result outside fresh jobs')
        for p in folder.iterdir():
            if p.is_file() or p.is_symlink():
                add(p)
    attempts=root/'attempts'
    if attempts.exists():
        for p in attempts.rglob('*'):
            if p.is_file() or p.is_symlink():
                add(p)
    # B starts with a fresh output root; these are only this shard's recovery metadata.
    for run in root.glob('memory-recovery-*'):
        for p in run.rglob('*'):
            if p.is_file() or p.is_symlink():add(p)
    raw_bytes=0
    with tarfile.open(archive,'w:gz',compresslevel=1,dereference=False) as tar:
        for name,path in members.items():
            info=tar.gettarinfo(str(path),arcname=name)
            if info.issym():
                info.linkname=os.path.relpath(path.resolve(),path.parent).replace(os.sep,'/')
            validate_members([info])
            if info.isfile():
                raw_bytes+=info.size
                with path.open('rb') as f:tar.addfile(info,f)
            else:tar.addfile(info)
    return raw_bytes

def sha_file(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()

def publish_shard(root,locations,required,cohorts,assignment_path,worker):
    from boto3.s3.transfer import TransferConfig
    root=pathlib.Path(root);digest=assignment_digest(assignment_path)
    archive=root/('box-'+worker+'-results-'+digest[:12]+'.tar.gz')
    raw_bytes=pack_results(root,locations,archive)
    s3=client()
    s3.upload_file(str(archive),BUCKET,object_key(digest,worker+'-results.tar.gz'),
        ExtraArgs={'ServerSideEncryption':'AES256','ExpectedBucketOwner':ACCOUNT},
        Config=TransferConfig(max_concurrency=4,multipart_chunksize=64*1024**2))
    receipt=dict(status='fits_complete',worker=worker,assignment_sha256=digest,
        archive_sha256=sha_file(archive),archive_bytes=archive.stat().st_size,
        artifact_bytes=raw_bytes,cohorts=[list(t) for t in cohorts],
        required_jobs=[[k,list(t),m] for k,t,m in sorted(required)],
        locations=[dict(task=[k,list(t),m],folder=str(pathlib.Path(folder).relative_to(root)))
            for (k,t,m),folder in sorted(locations.items())],coverage_gate='NOT_PASSED')
    put_json(s3,digest,worker+'-status.json',receipt)
    (root/('box-'+worker+'-transfer-receipt.json')).write_text(json.dumps(receipt,indent=2))
    return receipt

def publish_failure(assignment_path,worker,error):
    if worker!='A':
        put_json(client(),assignment_digest(assignment_path),worker+'-status.json',
            dict(status='incomplete',error=str(error),coverage_gate='NOT_PASSED'))

class HashReader:
    def __init__(self,body):
        self.body=body
        self.hash=hashlib.sha256()
    def read(self,n=-1):
        data=self.body.read(n)
        self.hash.update(data)
        return data

def receive_shard(base,root,assignment_path,worker):
    digest=assignment_digest(assignment_path);s3=client()
    # This is a dependency wait inside the numerical coordinator, not a monitor.
    while True:
        receipt=get_json(s3,digest,worker+'-status.json')
        if receipt is not None:break
        time.sleep(60)
    if receipt.get('status')!='fits_complete' or receipt.get('assignment_sha256')!=digest:
        raise RuntimeError('B mandatory work incomplete: '+str(receipt))
    candidates=[pathlib.Path(root)]
    archived=pathlib.Path('/opt/frankie-box/archive')
    if archived.is_dir():candidates.append(archived/'family-research-20261022')
    for p in candidates:p.mkdir(exist_ok=True,parents=True)
    storage=max(candidates,key=lambda p:shutil.disk_usage(p).free)
    if shutil.disk_usage(storage).free<receipt['artifact_bytes']+64*GIB:
        raise RuntimeError('required B result import needs more disk; work retained')
    destination=storage/('remote-'+worker+'-'+digest[:12])
    if destination.exists():
        raise RuntimeError('B import destination already exists; preserve for explicit recovery')
    staging=destination.with_name(destination.name+'.partial')
    staging.mkdir()
    reader=HashReader(s3.get_object(Bucket=BUCKET,Key=object_key(digest,worker+'-results.tar.gz'),
                                   ExpectedBucketOwner=ACCOUNT)['Body'])
    with tarfile.open(fileobj=reader,mode='r|gz') as tar:
        for member in tar:
            validate_members([member])
            tar.extract(member,path=staging,filter='data')
    while reader.read(8*1024**2):pass
    if reader.hash.hexdigest()!=receipt['archive_sha256']:
        raise RuntimeError('B archive hash disagreement; partial import retained')
    staging.rename(destination)
    imported={}
    for row in receipt['locations']:
        folder=destination/row['folder']
        if pathlib.Path(row['folder']).parent!=pathlib.Path('jobs'):
            raise ValueError('invalid B job location')
        local=pathlib.Path(root)/'jobs'/folder.name
        if local.exists() or local.is_symlink():
            raise RuntimeError('B job already exists on A; refuse overwrite')
        local.symlink_to(folder,target_is_directory=True)
        imported[task_key(row['task'])]=folder
    (pathlib.Path(root)/('box-'+worker+'-import-receipt.json')).write_text(json.dumps(receipt,indent=2))
    return imported,receipt

