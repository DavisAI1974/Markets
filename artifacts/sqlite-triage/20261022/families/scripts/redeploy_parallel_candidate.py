"""63-slot same-instance executor; shared immutable matrices and prepared folds.

Only scheduling, storage, views and BLAS worker counts change. No instance
lifecycle operation, agent, monitor, target/split/hyperparameter change.
"""
import concurrent.futures
import csv
import hashlib
import json
import os
import pathlib
import queue
import shutil
import signal
import subprocess
import threading
import time


def rows(path):
    if not path.exists():return []
    with path.open() as f:return list(csv.DictReader(f))


def once(text,old,new):
    assert text.count(old)==1,(old,text.count(old))
    return text.replace(old,new)


def main():
    b=pathlib.Path('/opt/frankie-box/work/family-research-20261022')
    out=b/'joint-models-v4-candidate-20261022';root=out/'parallel-63';root.mkdir(exist_ok=False)
    jobs=root/'jobs';jobs.mkdir();cache=root/'cache';cache.mkdir();shared=root/'shared';shared.mkdir()
    scripts=out/'scripts';julia=str(b/'julia-runtime/julia-1.13.2/bin/julia')
    for name in ['pool_cache_guard.py','parallel_artifact_helpers.jl']:
        shutil.copyfile(pathlib.Path(__file__).parent/name,root/name)
    helper=r'''using Mmap
const PARROOT=joinpath(ENV["JOINT_PARALLEL_ROOT"])
function mapped(path,dims)
    open(path,"r") do io
        Mmap.mmap(io,Matrix{Float64},Tuple(Int.(dims));grow=false,shared=true)
    end
end
function load_shared_packet()
    m=deserialize(joinpath(PARROOT,"shared/meta.jls"))
    (x=mapped(joinpath(PARROOT,"shared/raw.bin"),m.dims),names=m.names,samples=m.samples)
end
function save_prepared(prep,a,b)
    d=ENV["COHORT_CACHE"];mkpath(d)
    for (name,x) in [("a",a),("b",b)]
        open(joinpath(d,name*".bin"),"w") do io;write(io,x);end
    end
    serialize(joinpath(d,"prep.jls"),(prep=prep,adims=size(a),bdims=size(b)))
    groups=sort(unique(layergroup.(replace.(prep.names,r"^delta[0-9]+\."=>""))))
    open(joinpath(d,"ready.json"),"w") do io
        JSON3.write(io,Dict("groups"=>groups,"a_dims"=>size(a),"b_dims"=>size(b)))
    end
end
function load_prepared()
    d=ENV["COHORT_CACHE"];p=deserialize(joinpath(d,"prep.jls"))
    p.prep,mapped(joinpath(d,"a.bin"),p.adims),mapped(joinpath(d,"b.bin"),p.bdims)
end
'''
    helper+='\ninclude("parallel_artifact_helpers.jl")\n'
    (root/'shared.jl').write_text(helper)
    shutil.copyfile(scripts/'model_rules.jl',root/'model_rules.jl')
    export=r'''using Serialization,JSON3,DataFrames
b=ENV["FAMILY_RESEARCH_DIR"];d=joinpath(ENV["JOINT_PARALLEL_ROOT"],"shared")
p=deserialize(joinpath(b,"joint-inputs-v4-candidate-20261022/model_matrix.jls"))
open(joinpath(d,"raw.bin"),"w") do io;write(io,p.x);end
serialize(joinpath(d,"meta.jls"),(names=p.names,samples=p.samples,dims=size(p.x)))
println(JSON3.write(Dict("status"=>"shared_matrix_ready","dimensions"=>size(p.x),"bytes"=>sizeof(p.x))));flush(stdout)
'''
    (root/'export_shared.jl').write_text(export)
    src=(scripts/'run_joint_models.jl').read_text();neural=(scripts/'run_neural_models.jl').read_text()
    originals={'core':hashlib.sha256(src.encode()).hexdigest(),'neural':hashlib.sha256(neural.encode()).hexdigest()}
    for kind,text in [('core',src),('neural',neural)]:
        text=once(text,'BLAS.set_num_threads(8)','BLAS.set_num_threads(1)\ninclude("shared.jl")')
        text=once(text,'deserialize(joinpath(OUT,"model_matrix.jls"))','load_shared_packet()')
        at='        begin_ns,end_ns=bounds[fold],bounds[fold+1]'
        text=once(text,at,'        selected=get(ENV,"MODEL_COHORT","")\n        selected!="$(outcome)|$(h)|$(fold)" && continue\n'+at)
        if kind=='core':
            text=once(text,'function runmodels()',
              'get(ENV,"PREP_ONLY","0")=="1" && run(`python3 $(joinpath(PARROOT,"pool_cache_guard.py"))`)\nfunction runmodels()')
            at='        prep=fitprep(x[tr,use],names[use]);a=applyprep(prep,x[tr,use]);b=applyprep(prep,x[te,use])'
            repl='''        if get(ENV,"PREP_ONLY","0")=="1"
            prep=fitprep(view(x,tr,use),names[use]);a=applyprep(prep,view(x,tr,use));b=applyprep(prep,view(x,te,use))
            save_prepared(prep,a,b);return
        end
        prep,a,b=load_prepared()'''
            text=once(text,at,repl)
            text=once(text,'        for modelname in models','        for modelname in models\n            modelname!=ENV["MODEL_NAME"] && continue')
            text=once(text,'                aa,bb=a[:,cols],b[:,cols]','                aa,bb=view(a,:,cols),view(b,:,cols)')
            at='    # Unsupervised structure is fitted on the earliest quarter without outcomes.'
            text=once(text,at,'    get(ENV,"PCA_ONLY","0")!="1" && return\n    pm,pp,ps=publish_parallel_outputs(OUT,PARROOT)\n    append!(metrics,pm);append!(predictions,pp);append!(splits,ps)\n'+at)
            text=once(text,'        serialize(joinpath(OUT,stem*"-preprocessing.jls"),',
              '        save_cohort_preprocessing(joinpath(OUT,stem*"-preprocessing.jls"),')
            # PCA runs once after merging, using exactly the same matrix/cohort.
            text=text.replace('prep=fitprep(x[train,:],names);z=applyprep(prep,x)','prep=fitprep(view(x,train,:),names);z=applyprep(prep,x)')
        else:
            text=once(text,'        p=(prep=fitprep(x[tr,use],packet.names[use]),raw_columns=use,train_sample_ids=samples.sample_id[tr],test_sample_ids=samples.sample_id[te])',
                '        prep,a64,b64=load_prepared()\n        p=(prep=prep,raw_columns=use,train_sample_ids=samples.sample_id[tr],test_sample_ids=samples.sample_id[te])')
            text=once(text,'        a=Float32.(applyprep(p.prep,x[tr,p.raw_columns]));b=Float32.(applyprep(p.prep,x[te,p.raw_columns]))','        a=Float32.(a64);b=Float32.(b64)')
            text=once(text,'        for (modelname,arch) in configs','        for (modelname,arch) in configs\n            modelname!=ENV["MODEL_NAME"] && continue')
        (root/('run_'+kind+'_task.jl')).write_text(text)
    # One readiness pass: source anchors above, shape-preserving shared export,
    # and one completed prepared cohort before broad dispatch.
    env=dict(os.environ,FAMILY_RESEARCH_DIR=str(b),JOINT_PARALLEL_ROOT=str(root),JULIA_DEPOT_PATH=str(b/'julia-depot'),
      JULIA_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    with (root/'export.log').open('w') as log:
        subprocess.run([julia,'--startup-file=no','--project='+str(b/'julia-model-env'),str(root/'export_shared.jl')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    # Stop only the exact old launcher/fit commands, preserving committed and
    # partial output files. Instance state and unrelated work are untouched.
    ids=[15137,15275,15276];commands={}
    for pid in ids:
        p=pathlib.Path('/proc')/str(pid)/'cmdline'
        if not p.exists():continue
        cmd=p.read_bytes().replace(b'\0',b' ').decode();assert str(out) in cmd,(pid,cmd);commands[pid]=cmd
        os.kill(pid,signal.SIGSTOP)
    prefix=root/'serial-prefix';prefix.mkdir()
    for p in out.iterdir():
        if p.is_file() and not p.is_symlink() and p.suffix in ['.csv','.jls','.log','.txt']:
            shutil.copy2(p,prefix/p.name)
    completed_neural={(r['outcome'],r['horizon_s'],r['fold'],r['model']) for r in rows(prefix/'neural_metrics.csv')}
    completed_core={(r['outcome'],r['horizon_s'],r['fold'],r['model']) for r in rows(prefix/'model_metrics.csv')}
    for pid in commands:
        os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT)
    print('Preserved serial results; redeploying 63-slot executor',flush=True)
    tasks=sorted({(r['outcome'],r['horizon_s'],str(f)) for r in rows(out/'model_outcomes.csv') for f in [2,3,4]})
    ready=queue.Queue();result_lock=threading.Lock();results=[];failures=[];all_jobs=[]
    def stem(t):return t[0].replace('_','-')+'-h'+t[1]+'-fold'+t[2]
    def prep(t):
        d=cache/stem(t);d.mkdir();e=dict(env,JOINT_MODEL_OUT=str(d),COHORT_CACHE=str(d),MODEL_COHORT='|'.join(t),PREP_ONLY='1',MODEL_NAME='')
        (d/'model_outcomes.csv').symlink_to(out/'model_outcomes.csv')
        with (d/'prepare.log').open('w') as log:
            p=subprocess.run([julia,'--startup-file=no','--project='+str(b/'julia-model-env'),str(root/'run_core_task.jl')],env=e,stdout=log,stderr=subprocess.STDOUT)
        if p.returncode or not (d/'ready.json').exists():
            with result_lock:failures.append(dict(stage='prepare',cohort=t,returncode=p.returncode))
            return
        groups=json.loads((d/'ready.json').read_text())['groups'];binary=t[0]=='first_observed_family_within_h'
        models=['training_frequency','ridge100','evotrees_depth3','evotrees_depth5'] if binary else ['zero_change','training_mean','ridge100','evotrees_depth3','evotrees_depth5','evotrees_mae','evotrees_q10','evotrees_q90']
        models+=['dropgroup:'+g for g in groups]+([] if binary else ['drop_history'])
        for kind,names,done in [('core',models,completed_core),('neural',['neural_tree','residual_mlp','tabm_ensemble'],completed_neural)]:
            for name in names:
                item=(kind,t,name,d)
                if (*t,name) not in done:
                    with result_lock:all_jobs.append(dict(kind=kind,cohort=t,model=name))
                    ready.put(item)
        print(json.dumps(dict(prepared=t,groups=len(groups))),flush=True)
    def fit(item):
        kind,t,name,d=item;jobid=stem(t)+'--'+kind+'--'+hashlib.sha256(name.encode()).hexdigest()[:12]
        dest=jobs/jobid;dest.mkdir();(dest/'model_outcomes.csv').symlink_to(out/'model_outcomes.csv')
        e=dict(env,JOINT_MODEL_OUT=str(dest),COHORT_CACHE=str(d),MODEL_COHORT='|'.join(t),MODEL_NAME=name,PREP_ONLY='0')
        project=b/('julia-model-env' if kind=='core' else 'julia-neural-env')
        with (dest/'run.log').open('w') as log:
            p=subprocess.run([julia,'--startup-file=no','--project='+str(project),str(root/('run_'+kind+'_task.jl'))],env=e,stdout=log,stderr=subprocess.STDOUT)
        receipt=dict(kind=kind,cohort=t,model=name,returncode=p.returncode,output=str(dest))
        metrics=rows(dest/('model_metrics.csv' if kind=='core' else 'neural_metrics.csv'))
        errors=rows(dest/('model_errors.csv' if kind=='core' else 'neural_errors.csv'))
        receipt.update(metric_rows=len(metrics),error_rows=len(errors))
        if p.returncode or len(metrics)!=1 or errors:
            with result_lock:failures.append(receipt)
        else:
            with result_lock:results.append(receipt)
        (dest/'job_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
    plan=dict(status='running',workers=63,preparation_workers=4,fit_workers_during_preparation=59,fit_workers_after_preparation=63,
      cpu_affinity=len(os.sched_getaffinity(0)),single_cpu_threads_per_worker=True,shared_raw_matrix=str(shared/'raw.bin'),
      prepared_folds='memory-mapped once per cohort; no per-worker full matrix deserialization',original_source_sha256=originals,
      completed_serial_core=len(completed_core),completed_serial_neural=len(completed_neural),cohorts=len(tasks),coverage_gate='NOT_PASSED',
      changes='Scheduler, read-only memory maps, allocation-saving views, BLAS threads 8 to 1. Thread reduction may change floating-point last bits; algorithms/hyperparameters/splits/targets unchanged.')
    (root/'parallel_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    # 4 preparation jobs + 59 fits = 63 active compute slots. Prepared models
    # begin immediately; after preparation all 63 slots fit models.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pp,concurrent.futures.ThreadPoolExecutor(max_workers=63) as fp:
        pf=[pp.submit(prep,t) for t in tasks];active=set()
        while True:
            preparing=any(not f.done() for f in pf);limit=59 if preparing else 63
            while len(active)<limit:
                try:item=ready.get_nowait()
                except queue.Empty:break
                active.add(fp.submit(fit,item))
            if not preparing and ready.empty() and not active:break
            if active:
                done,_=concurrent.futures.wait(active,timeout=1,return_when=concurrent.futures.FIRST_COMPLETED)
                for f in done:f.result()
                active-=done
            else:time.sleep(0.2)
        for f in pf:f.result()
    def merge(name,kind):
        merged=rows(prefix/(name+'.csv'))
        for r in results:
            if r['kind']==kind:merged.extend(rows(pathlib.Path(r['output'])/(name+'.csv')))
        if not merged:return
        keys=['sample_id','outcome','horizon_s','fold','model'] if 'predictions' in name else ['outcome','horizon_s','fold','model'] if 'metrics' in name else ['outcome','horizon_s','fold']
        unique={tuple(r[k] for k in keys):r for r in merged}
        assert len(unique)==len(merged),(name,'duplicate result keys')
        p=out/(name+'.csv.parallel-complete')
        with p.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(merged[0]));w.writeheader();w.writerows(merged)
        os.replace(p,out/(name+'.csv'))
    for name in ['model_metrics','model_predictions']:merge(name,'core')
    for name in ['neural_metrics','neural_predictions']:merge(name,'neural')
    # Original column/target metadata plus per-job fitted states stay in place;
    # no enormous redundant state copies are made during aggregation.
    plan.update(status='fits_complete' if not failures else 'fits_with_failures',completed_jobs=len(results),failures=failures,scheduled_jobs=len(all_jobs))
    (root/'parallel_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    if failures:raise RuntimeError(f'{len(failures)} preparation/model failures; all evidence retained')
    # PCA and downstream analyses are single tasks after the parallel refits.
    e=dict(env,JOINT_MODEL_OUT=str(out),MODEL_COHORT='',MODEL_NAME='',PREP_ONLY='0',PCA_ONLY='1')
    with (root/'pca.log').open('w') as log:
        subprocess.run([julia,'--startup-file=no','--project='+str(b/'julia-model-env'),str(root/'run_core_task.jl')],env=e,stdout=log,stderr=subprocess.STDOUT,check=True)
    for name in ['summarize_joint_models.jl','analyze_joint_interactions.jl','analyze_observed_price_paths.jl']:
        with (root/(name+'.log')).open('w') as log:
            subprocess.run([julia,'--startup-file=no','--project='+str(b/'julia-model-env'),str(scripts/name)],env=e,stdout=log,stderr=subprocess.STDOUT,check=True)
    plan['status']='complete_candidate';(root/'parallel_plan.json').write_text(json.dumps(plan,indent=2)+'\n')


if __name__=='__main__':main()
