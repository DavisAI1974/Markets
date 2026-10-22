"""Resume only uncommitted core tasks in isolated processes on the same instance.

The executed serial prefix is retained. Numerical model code/configuration stays
unchanged: the adapter only filters tasks, changes output paths and separates PCA.
No agent delegation, instance change, monitor, model selection or hyperparameter change.
"""
import collections
import concurrent.futures
import csv
import hashlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import time


def read(p):
    if not p.exists():return []
    with p.open() as f:return list(csv.DictReader(f))


def write(p,rows):
    assert rows
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def task(r):return (r['outcome'],r['horizon_s'],r['fold'])
def modelkey(r):return task(r)+(r['model'],)
def stem(t):return t[0].replace('_','-')+'-h'+t[1]+'-fold'+t[2]


def main():
    b=pathlib.Path('/opt/frankie-box/work/family-research-20261022');out=b/'joint-models-v3'
    root=out/'core-resume';assert not root.exists(),'refuse a second resume'
    root.mkdir();prefix=root/'committed-serial-prefix';prefix.mkdir()
    src=(out/'scripts/run_joint_models.jl').read_text()
    guard='@assert OUT==joinpath(BASE,"joint-models-v3") "frozen rerun output required"'
    assert src.count(guard)==1
    adapted=src.replace(guard,'@assert OUT==joinpath(BASE,"joint-models-v3") || startswith(OUT,joinpath(BASE,"joint-models-v3","core-resume","jobs")*"/")')
    at='        begin_ns,end_ns=bounds[fold],bounds[fold+1]'
    assert adapted.count(at)==1
    adapted=adapted.replace(at,'        get(ENV,"CORE_PCA_ONLY","0")=="1" && continue\n        selected=get(ENV,"CORE_TASK","")\n        !isempty(selected) && selected!="$(outcome)|$(h)|$(fold)" && continue\n'+at)
    at='    # Unsupervised structure is fitted on the earliest quarter without outcomes.'
    assert adapted.count(at)==1
    adapted=adapted.replace(at,'    if get(ENV,"CORE_TASK","")!=""\n        open(joinpath(OUT,"core_task_receipt.json"),"w") do io;JSON3.write(io,Dict("metric_rows"=>length(metrics),"prediction_rows"=>length(predictions),"error_rows"=>length(errors)));end\n        return\n    end\n    if get(ENV,"CORE_PCA_ONLY","0")=="1"\n        append!(metrics,Tables.rowtable(CSV.read(joinpath(OUT,"model_metrics.csv"),DataFrame)))\n        append!(predictions,Tables.rowtable(CSV.read(joinpath(OUT,"model_predictions.csv"),DataFrame)))\n    end\n'+at)
    # DataFrames exports eachrow, but Tables is transitive, not a direct dependency.
    adapted=adapted.replace('Tables.rowtable(CSV.read(joinpath(OUT,"model_metrics.csv"),DataFrame))','NamedTuple.(eachrow(CSV.read(joinpath(OUT,"model_metrics.csv"),DataFrame)))')
    adapted=adapted.replace('Tables.rowtable(CSV.read(joinpath(OUT,"model_predictions.csv"),DataFrame))','NamedTuple.(eachrow(CSV.read(joinpath(OUT,"model_predictions.csv"),DataFrame)))')
    script=root/'run_core_task.jl';script.write_text(adapted)
    shutil.copyfile(out/'scripts/model_rules.jl',root/'model_rules.jl')
    # Verify the exact target process before pausing it; no unrelated process is signaled.
    pid=int(os.environ['CORE_SERIAL_PID'])
    argv=pathlib.Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode()
    assert str(out/'scripts/run_joint_models.jl') in argv and 'julia' in argv
    os.kill(pid,signal.SIGSTOP)
    try:
        metrics=read(out/'model_metrics.csv');predictions=read(out/'model_predictions.csv');splits=read(out/'chronological_splits.csv')
        assert not read(out/'model_errors.csv')
        old=read(b/'joint-models-v1/model_metrics.csv')
        expected=collections.defaultdict(set)
        for r in old:expected[task(r)].add(r['model'])
        actual=collections.defaultdict(set)
        counts=collections.Counter(modelkey(r) for r in predictions)
        for r in metrics:actual[task(r)].add(r['model'])
        completed={t for t,models in expected.items() if actual[t]==models and all(counts[modelkey(r)]==int(r['test_n']) for r in metrics if task(r)==t)}
        assert completed and len(completed)<len(expected)
        pm=[r for r in metrics if task(r) in completed];pp=[r for r in predictions if task(r) in completed];ps=[r for r in splits if task(r) in completed]
        write(prefix/'model_metrics.csv',pm);write(prefix/'model_predictions.csv',pp);write(prefix/'chronological_splits.csv',ps)
        shutil.copyfile(out/'models.log',prefix/'models.log')
        # Preserve any states emitted by an uncommitted partial task separately.
        uncommitted=root/'uncommitted-serial-states';uncommitted.mkdir()
        for t in expected.keys()-completed:
            for p in out.glob(stem(t)+'-*.jls'):shutil.move(str(p),uncommitted/p.name)
        receipt={'serial_pid':pid,'original_process_command':argv,'completed_serial_tasks':len(completed),
            'preserved_serial_metric_rows':len(pm),'preserved_serial_prediction_rows':len(pp),
            'remaining_tasks':len(expected)-len(completed),'workers':8,'julia_threads_per_process':1,
            'model_code':'identical numerical model code; task/output/PCA adapter only','original_script_sha256':hashlib.sha256(src.encode()).hexdigest(),
            'adapter_script_sha256':hashlib.sha256(adapted.encode()).hexdigest(),
            'remaining_task_ids':[list(t) for t in sorted(expected.keys()-completed)],'neural_results_untouched':True,
            'serial_suite_exit':'intentional SIGTERM after freezing coherent committed task prefix; not a fitted-model execution error'}
        (root/'resume_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    except BaseException:
        os.kill(pid,signal.SIGCONT);raise
    os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT)
    jobs=root/'jobs';jobs.mkdir()
    julia=str(b/'julia-runtime/julia-1.13.2/bin/julia')
    env=dict(os.environ,JULIA_DEPOT_PATH=str(b/'julia-depot'),JULIA_NUM_THREADS='1')
    def run(t):
        d=jobs/stem(t);d.mkdir()
        for n in ['model_matrix.jls','model_outcomes.csv']:(d/n).symlink_to(b/'joint-inputs-v3'/n)
        e=dict(env,JOINT_MODEL_OUT=str(d),CORE_TASK='|'.join(t))
        with (d/'run.log').open('w') as log:
            p=subprocess.run([julia,'--startup-file=no','--project='+str(b/'julia-model-env'),str(script)],env=e,stdout=log,stderr=subprocess.STDOUT)
        assert p.returncode==0,(t,p.returncode)
        r=json.loads((d/'core_task_receipt.json').read_text());assert r['error_rows']==0,(t,r)
        m=read(d/'model_metrics.csv');assert {x['model'] for x in m}==expected[t],(t,len(m),len(expected[t]))
        assert all(task(x)==t for x in m)
        print(json.dumps({'completed_task':t,**r}),flush=True)
        return t,d
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(run,sorted(expected.keys()-completed)))
    merged_metrics=pm[:];merged_predictions=pp[:];merged_splits=ps[:]
    for t,d in sorted(results):
        merged_metrics+=read(d/'model_metrics.csv');merged_predictions+=read(d/'model_predictions.csv');merged_splits+=read(d/'chronological_splits.csv')
        for p in d.glob('*.jls'):
            if p.is_symlink():continue
            dest=out/p.name;assert not dest.exists(),dest;shutil.copyfile(p,dest)
    assert {modelkey(r) for r in merged_metrics}=={modelkey(r) for r in old}
    assert len({modelkey(r) for r in merged_metrics})==len(merged_metrics)
    counts=collections.Counter(modelkey(r) for r in merged_predictions)
    assert all(counts[modelkey(r)]==int(r['test_n']) for r in merged_metrics)
    for name,rows in [('model_metrics',merged_metrics),('model_predictions',merged_predictions),('chronological_splits',merged_splits)]:
        write(out/(name+'.csv.parallel-complete'),rows);os.replace(out/(name+'.csv.parallel-complete'),out/(name+'.csv'))
    e=dict(env,JOINT_MODEL_OUT=str(out),CORE_PCA_ONLY='1',CORE_TASK='')
    with (out/'pca-resumed.log').open('w') as log:
        p=subprocess.run([julia,'--startup-file=no','--project='+str(b/'julia-model-env'),str(script)],env=e,stdout=log,stderr=subprocess.STDOUT)
    assert p.returncode==0,'PCA stage failed; committed fitted models remain saved'
    r=json.loads((out/'model_run_receipt.json').read_text());assert r['metric_rows']==len(old) and r['error_rows']==0
    receipt['status']='core_complete';receipt['final_metric_rows']=len(merged_metrics);receipt['final_prediction_rows']=len(merged_predictions)
    (root/'resume_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
