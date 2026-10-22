"""Plan immutable pending-only task ownership changes; never move a live/completed fit."""
import copy
import json
import time
from family_save_stop import require,task_key,task_set
from family_reuse_support import task_owner,cohorts_for_worker
from family_guarded_recovery import guarded_source


def reuse_source(original):
    source=guarded_source(original)
    anchor='GIB = 1024**3'
    require(source.count(anchor)==1,'unexpected import anchor')
    source=source.replace(anchor,'from family_reuse_support import cohorts_for_worker,task_owner,validate_preparation,wait_all_shards\n\n'+anchor)
    source=source.replace('assigned_cohorts(', 'cohorts_for_worker(')
    old="    def reconcile(t, info):\n        registered.add(t)"
    require(source.count(old)==1,'unexpected reconciliation anchor')
    source=source.replace(old,"    def reconcile(t, info):\n        validate_preparation(assignment,t,info)\n        registered.add(t)")
    old="                k = (kind,t,model)\n                required.add(k)"
    require(source.count(old)==1,'unexpected mandatory task anchor')
    source=source.replace(old,"                k = (kind,t,model)\n                if task_owner(assignment,k)!=args.worker_id:\n                    continue\n                required.add(k)")
    old='    accumulated_required = own_required'
    require(source.count(old)==1,'unexpected finalization anchor')
    source=source.replace(old,"    checkpoint('waiting_for_all_shards',worker_id='A',global_pca_and_postprocessing_pending=True)\n    wait_all_shards(args.assignment,own_required,run)\n"+old)
    return source


def make_epoch(previous,snapshots,previous_digest,bootstrap=False):
    require(set(snapshots)==set(previous['instances']),'missing owner snapshot')
    required,committed,active,infos={},set(),set(),{}
    for owner,s in snapshots.items():
        keys=task_set(s['required'])
        require(all(task_owner(previous,k)==owner for k in keys),'snapshot contains unowned key')
        done=set(map(task_key,s['committed']))
        require(len(done)==len(s['committed']) and done<=keys,'invalid committed inventory')
        live={(j['kind'],tuple(j['cohort']),j['model']) for j in s['jobs'] if j['kind']!='prepare'}
        require(len(live)==len([j for j in s['jobs'] if j['kind']!='prepare']),'duplicate captured live key')
        require(live<=keys and not live & active,'unregistered/duplicate active task')
        require(not (keys & set().union(*required.values())) if required else True,'duplicate required authority')
        required[owner]=keys;committed.update(done);active.update(live)
        for row in s['preparations']:
            t=tuple(row['cohort'])
            if t in infos:require(infos[t]==row['info'],'training preparation disagreement')
            infos[t]=row['info']
    recipients=[o for o,s in snapshots.items() if not s['jobs'] and not s['unregistered'] and required[o]<=committed]
    if not bootstrap:require(bool(recipients),'no finished box ready for reuse')
    all_required=set().union(*required.values())
    if previous.get('mandatory_jobs'):
        require(all_required==task_set(previous['mandatory_jobs']),'mandatory task universe changed')
    overrides={task_key(row['task']):row['owner'] for row in previous.get('task_delegations',[])}
    transfers=[];retained={o:set(keys) for o,keys in required.items()}
    for recipient in sorted(recipients,key=lambda o:-previous['slots'][o]):
        cap=previous['slots'][recipient] if previous['slots'][recipient]>=96 else 16
        candidates=[(owner,k) for owner in required if owner!=recipient
                    for k in retained[owner]-committed-active if owner not in recipients]
        def priority(item):
            owner,(kind,t,model)=item
            return (t[2]!='4',not(model.startswith('evotrees_') or kind=='neural'),t,model,owner)
        chosen_cohorts=set()
        for owner,k in sorted(candidates,key=priority):
            if cap<=0:break
            t=k[1]
            if t not in chosen_cohorts and len(chosen_cohorts)>=2:continue
            # Every baseline cohort must retain authority on its original shard.
            if sum(x[1]==t for x in retained[owner])<=1:continue
            require(t in infos,'missing delegated training preparation')
            retained[owner].remove(k);overrides[k]=recipient;chosen_cohorts.add(t);cap-=1
            transfers.append(dict(task=[k[0],list(t),k[2]],from_owner=owner,owner=recipient))
    if not bootstrap:require(bool(transfers),'no safely movable pending task')
    plan=copy.deepcopy(previous)
    plan.update(prior_assignment_sha256=previous_digest,reuse_enabled=True,
                mandatory_jobs=[[k,list(t),m] for k,t,m in sorted(all_required)],
                reuse_epoch=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()),
                task_delegations=[dict(task=[k,list(t),m],owner=o) for (k,t,m),o in sorted(overrides.items())],
                delegation_preparations=[dict(cohort=list(t),info=info) for t,info in sorted(infos.items()) if any(k[1]==t for k in overrides)],
                pending_transfers=transfers)
    require(all(task_key(row['task']) not in committed|active for row in transfers),'live/completed task moved')
    return plan
