import pathlib,json,csv,os,time,signal,sys,hashlib
B=pathlib.Path('/opt/frankie-box/work/family-research-20261022');O=B/'joint-models-v4-candidate-20261022';R=O/'parallel-63'
sys.path.insert(0,str(B/'full-context-audit/scripts'))
import resume_dual_box_candidate_b_io as mod
serial=B/'joint-models-v4-candidate-20261022-snapshot-source-184835/parallel-63/serial-prefix'
t=('first_observed_family_within_h','120','4');models=['neural_tree','residual_mlp']
assignment=json.loads((R/'dual-box-ownership-20261022T190758Z.json').read_text())
assert next(r['owner'] for r in assignment['cohorts'] if tuple(r['cohort'])==t)=='B'
def read(path):
    with path.open(newline='') as f:
        r=csv.DictReader(f);return r.fieldnames,list(r)
mh,mr=read(serial/'neural_metrics.csv');ph,pr=read(serial/'neural_predictions.csv')
wanted=lambda r,m:mod.key(r)==t+(m,)
stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
attempt=R/'attempts'/('serial-original-reconciliation-'+stamp)
prepared=[];comparisons=[]
state=json.loads((R/'memory-recovery-20261022T194644Z-f4082e1d/recovery-plan.json').read_text())
committed={(k,tuple(c),m) for k,c,m in state['committed_jobs']}
for model in models:
    folder=R/'jobs'/mod.job_id(t,'neural',model)
    if (folder/'canonical_serial_original_receipt.json').exists():continue
    assert ('neural',t,model) in committed
    assert mod.committed(serial,'neural',t,model,serial=True)
    assert mod.committed(folder,'neural',t,model)
    oldmetrics=[r for r in mr if wanted(r,model)]
    oldpred=[r for r in pr if wanted(r,model)]
    newmh,newmr=read(folder/'neural_metrics.csv');newph,newpr=read(folder/'neural_predictions.csv')
    assert mh==newmh and ph==newph
    assert len(oldmetrics)==len(newmr)==1
    assert all(oldmetrics[0][k]==newmr[0][k] for k in ['train_n','test_n','fitted_columns'])
    oldby={r['sample_id']:r for r in oldpred};newby={r['sample_id']:r for r in newpr}
    assert oldby.keys()==newby.keys()
    assert all(float(oldby[k]['observed'])==float(newby[k]['observed']) for k in oldby)
    comparisons.append(dict(model=model,original_disposition=oldmetrics[0].get('disposition'),
        rerun_disposition=newmr[0].get('disposition'),
        prediction_max_abs_diff=max(abs(float(oldby[k]['prediction'])-float(newby[k]['prediction'])) for k in oldby),
        metrics_differences={k:dict(original=oldmetrics[0][k],rerun=newmr[0][k]) for k in mh if oldmetrics[0][k]!=newmr[0][k]}))
    stage=attempt/'original-ready'/folder.name;stage.mkdir(parents=True)
    for name,header,rows in [('neural_metrics.csv',mh,oldmetrics),('neural_predictions.csv',ph,oldpred)]:
        with (stage/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=header);writer.writeheader();writer.writerows(rows)
    weight=serial/(mod.stem(t)+'-'+model+'.jls')
    if weight.exists():os.link(weight.resolve(),stage/weight.name)
    prep=serial/(mod.stem(t)+'-neural-preprocessing.jls')
    if prep.exists():
        shared=R/'cache'/'preserved-serial-originals'/prep.name
        shared.parent.mkdir(parents=True,exist_ok=True)
        if not shared.exists():os.link(prep.resolve(),shared)
        else:assert os.path.samefile(prep.resolve(),shared)
        (stage/prep.name).symlink_to(shared)
    original_receipt=dict(status='preserved_original_serial_commit',
        original_process_returncode=None,source=str(serial),task=['neural',list(t),model],
        extra_rerun_preserved_under=str(attempt/'repeated-after-prior-commit'/folder.name),
        reason='Serial prefix was omitted from B staging; restore prior completed configuration as authoritative')
    (stage/'artifact_recovery_receipt.json').write_text(json.dumps(original_receipt,indent=2))
    (stage/'canonical_serial_original_receipt.json').write_text(json.dumps(original_receipt,indent=2))
    assert mod.committed(stage,'neural',t,model)
    prepared.append((model,folder,stage))
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        cmd=(p/'cmdline').read_bytes().split(b'\0')
        if not cmd or pathlib.Path(cmd[0].decode()).name!='julia':continue
        env=dict(v.split(b'=',1) for v in (p/'environ').read_bytes().split(b'\0') if b'=' in v)
        assert not (env.get(b'MODEL_COHORT',b'').decode()=='|'.join(t) and env.get(b'MODEL_NAME',b'').decode() in models)
    except OSError:pass
pid=3861;paused=False
try:
    if prepared:
        cmd=(pathlib.Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')
        assert b'--execute' in cmd and any(a.endswith(b'/resume_dual_box_candidate_b_io.py') for a in cmd)
        os.kill(pid,signal.SIGSTOP);paused=True
        deadline=time.monotonic()+5
        while (pathlib.Path('/proc')/str(pid)/'stat').read_text().split(') ',1)[1].split()[0]!='T' and time.monotonic()<deadline:time.sleep(.02)
        assert (pathlib.Path('/proc')/str(pid)/'stat').read_text().split(') ',1)[1].split()[0]=='T'
        for model,folder,stage in prepared:
            backup=attempt/'repeated-after-prior-commit'/folder.name;backup.parent.mkdir(parents=True,exist_ok=True)
            folder.rename(backup);stage.rename(folder)
            assert mod.committed(folder,'neural',t,model)
finally:
    if paused:os.kill(pid,signal.SIGCONT)
v=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),restored_original_keys=[['neural',list(t),m] for m,f,s in prepared],
    comparisons=comparisons,extra_rerun_attempts_retained=str(attempt),no_numerical_job_stopped=True,
    canonical_policy='prior completed serial results are authoritative; both original and repeated evidence retained',
    coverage_gate='NOT_PASSED')
(R/'serial-original-reconciliation-20261022.json').write_text(json.dumps(v,indent=2))
print(json.dumps(v))

