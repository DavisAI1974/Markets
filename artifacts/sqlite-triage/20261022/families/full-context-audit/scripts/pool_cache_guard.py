"""Bound the live prepared-fold cache; discard only reproducible dense caches.

Called by preparation jobs, not a monitor. Model outputs, raw inputs, source
evidence, metadata and failed-job records are never removed.
"""
import csv
import fcntl
import hashlib
import json
import os
import pathlib
import time


def rows(path):
    if not path.exists():return []
    with path.open() as f:return list(csv.DictReader(f))


def expected_jobs(root,folder):
    ready=folder/'ready.json'
    if not ready.exists():return None
    info=json.loads(ready.read_text());name=folder.name
    binary=name.startswith('first-observed-family-within-h-')
    core=['training_frequency','ridge100','evotrees_depth3','evotrees_depth5'] if binary else ['zero_change','training_mean','ridge100','evotrees_depth3','evotrees_depth5','evotrees_mae','evotrees_q10','evotrees_q90']
    core+=['dropgroup:'+g for g in info['groups']]+([] if binary else ['drop_history'])
    prior={}
    for kind,file in [('core','model_metrics.csv'),('neural','neural_metrics.csv')]:
        prior[kind]={(r['outcome'].replace('_','-')+'-h'+r['horizon_s']+'-fold'+r['fold'],r['model']) for r in rows(root/'serial-prefix'/file)}
    jobs=[]
    for kind,models in [('core',core),('neural',['neural_tree','residual_mlp','tabm_ensemble'])]:
        for model in models:
            if (name,model) in prior[kind]:continue
            jobs.append(root/'jobs'/(name+'--'+kind+'--'+hashlib.sha256(model.encode()).hexdigest()[:12])/'job_receipt.json')
    return jobs


def main():
    root=pathlib.Path(os.environ['JOINT_PARALLEL_ROOT']).resolve();folder=pathlib.Path(os.environ['COHORT_CACHE']).resolve()
    assert folder.parent==root/'cache'
    lock=root/'cache-admission.lock'
    while True:
        with lock.open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            active=[]
            for d in (root/'cache').iterdir():
                if not d.is_dir():continue
                dense=any((d/n).exists() for n in ['a.bin','b.bin'])
                admitted=(d/'admitted.json').exists()
                if not dense and not admitted:continue
                expected=expected_jobs(root,d)
                complete=expected is not None and all(p.exists() for p in expected)
                if complete:
                    for name in ['a.bin','b.bin','admitted.json']:
                        p=(d/name).resolve();assert p.parent==d.resolve() and d.resolve().parent==root/'cache'
                        if p.exists():p.unlink()
                    (d/'dense_cache_released.json').write_text(json.dumps(dict(reason='all assigned model jobs finished; immutable raw matrix and prep metadata retained',model_jobs=len(expected)))+'\n')
                else:active.append(d)
            stat=os.statvfs(root);free=stat.f_bavail*stat.f_frsize
            if (folder in active or len(active)<6) and free>=100*1024**3:
                (folder/'admitted.json').write_text(json.dumps(dict(cohort=folder.name,free_disk_bytes=free,active_cohorts=len(active)))+'\n')
                return
        time.sleep(2)


if __name__=='__main__':main()
