"""Epoch-scoped pending-task ownership and save-before-reuse coordination."""
import json
import pathlib
import time
from family_save_stop import require,task_key,task_set,durable_json,get_bytes,BUCKET,ACCOUNT,GATE


def task_owner(plan,task):
    key=task_key(task)
    matches=[row['owner'] for row in plan.get('task_delegations',[]) if task_key(row['task'])==key]
    require(len(matches)<=1,'duplicate delegated task')
    baseline=[row['owner'] for row in plan['cohorts'] if tuple(row['cohort'])==key[1]]
    require(len(baseline)==1,'unknown/duplicate task cohort')
    owner=matches[0] if matches else baseline[0]
    require(owner in plan['instances'],'unknown delegated owner')
    return owner


def cohorts_for_worker(all_cohorts,plan,worker):
    baseline=[tuple(row['cohort']) for row in plan['cohorts']]
    require(len(baseline)==len(set(baseline)) and plan.get('coverage_gate')==GATE,'invalid baseline cohort registry')
    if all_cohorts is not None:require(set(baseline)==set(all_cohorts),'frozen cohort registry changed')
    require(worker in plan['instances'],'unknown worker')
    result={tuple(row['cohort']) for row in plan['cohorts'] if row['owner']==worker}
    for row in plan.get('task_delegations',[]):
        require(task_owner(plan,row['task'])==row['owner'],'invalid task delegation')
        if row['owner']==worker:result.add(tuple(row['task'][1]))
    return sorted(result)


def validate_preparation(plan,cohort,info):
    for row in plan.get('delegation_preparations',[]):
        if tuple(row['cohort'])==tuple(cohort):
            require(row['info']==info,'delegated training preparation changed')


def global_ready(plan,digest,rows):
    if set(rows)!=set(plan['instances']):return False
    combined=set()
    for owner,row in rows.items():
        if not row:return False
        require(row.get('status')!='incomplete','mandatory shard failed')
        if row.get('status')!='fits_complete':return False
        require(row.get('worker')==owner and row.get('assignment_sha256')==digest and
                row.get('coverage_gate')==GATE,'wrong completion epoch/owner/gate')
        keys=task_set(row['required_jobs'])
        require(all(task_owner(plan,k)==owner for k in keys),'completion includes unowned task')
        require(not combined & keys,'duplicate global required task')
        combined.update(keys)
    require({t for k,t,m in combined}=={tuple(r['cohort']) for r in plan['cohorts']},
            'global mandatory cohort coverage missing')
    if plan.get('mandatory_jobs'):
        require(combined==task_set(plan['mandatory_jobs']),'global mandatory model coverage missing')
    return True


def reuse_key(digest,name):
    require(len(digest)==64 and all(c in '0123456789abcdef' for c in digest),'invalid reuse epoch')
    return 'host-deliveries/family-research-20261022/reuse/'+digest+'/'+name


def publish(s3,key,value):
    body=(json.dumps(value,sort_keys=True)+'\n').encode()
    s3.put_object(Bucket=BUCKET,Key=key,Body=body,ContentType='application/json',
                  ServerSideEncryption='AES256',ExpectedBucketOwner=ACCOUNT)
    require(get_bytes(s3,key)==body,'reuse control read-back mismatch')


def optional_json(s3,key):
    try:return json.loads(get_bytes(s3,key))
    except s3.exceptions.NoSuchKey:return None


def wait_all_shards(assignment_path,own_required,run):
    from multibox_support import client,assignment_digest,get_json
    plan=json.loads(pathlib.Path(assignment_path).read_text());digest=assignment_digest(assignment_path)
    own=dict(status='fits_complete',worker='A',assignment_sha256=digest,
             required_jobs=own_required,coverage_gate=GATE)
    durable_json(pathlib.Path(run)/'A-fitting-completion.json',own)
    s3=client();publish(s3,reuse_key(digest,'A-fits.json'),own)
    while True:
        rows={'A':own}
        rows.update({owner:get_json(s3,digest,owner+'-status.json') for owner in plan['instances'] if owner!='A'})
        if global_ready(plan,digest,rows):
            proof=dict(status='all_fits_complete',assignment_sha256=digest,coverage_gate=GATE,shards=rows)
            durable_json(pathlib.Path(run)/'all-fitting-completion.json',proof)
            publish(s3,reuse_key(digest,'all-fits-complete.json'),proof)
            return
        time.sleep(15)


def wait_before_stop(s3,config):
    """Keep a verified finished shard available for reassignment until all fits end."""
    if not config.get('reuse_before_stop') or config['owner']=='A':return
    plan=json.loads(pathlib.Path(config['assignment']).read_text())
    ready=dict(status='backup_verified_ready_for_reuse',owner=config['owner'],
               assignment_sha256=config['digest'],receipt_key=config['receipt_key'],coverage_gate=GATE)
    durable_json(pathlib.Path(config['run'])/'hook-status.json',ready)
    publish(s3,reuse_key(config['digest'],config['owner']+'-available.json'),ready)
    while True:
        proof=optional_json(s3,reuse_key(config['digest'],'all-fits-complete.json'))
        if proof is not None:
            require(proof.get('assignment_sha256')==config['digest'] and proof.get('status')=='all_fits_complete'
                    and proof.get('coverage_gate')==GATE,'wrong global completion proof')
            require(global_ready(plan,config['digest'],proof['shards']),'incomplete global stop release')
            return
        time.sleep(15)
