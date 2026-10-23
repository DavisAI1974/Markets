"""Read only saved committed metrics; no fitting or test-based model selection."""
import base64,csv,gzip,json,math,pathlib,collections
HERE=pathlib.Path(__file__).parent
bundles=json.loads((HERE/'candidate-metric-readout-20261023.json').read_text())
aux=json.loads((HERE/'candidate-aux-readout-20261023.json').read_text())
rows=[]
for bundle in bundles:
    body=json.loads(gzip.decompress(base64.b64decode(bundle['metrics_gzip_base64'])))
    rows.extend(dict(zip(body['columns'],r),owner=bundle['owner']) for r in body['rows'])
keys=[tuple(r[k] for k in ('outcome','horizon_s','fold','model')) for r in rows]
assert len(keys)==len(set(keys))
bench={(r['outcome'],r['horizon_s'],r['fold']):r for r in aux['benchmarks']}
assert len(bench)==63
for r in rows:
    if r['model'] not in ('zero_change','training_mean','training_frequency'):continue
    b=bench[(r['outcome'],r['horizon_s'],r['fold'])]
    assert int(r['train_n'])==b['train_n'] and int(r['test_n'])==b['test_n']
    expected=b['zero_mae'] if r['model']=='zero_change' else b['mean_mae']
    assert abs(float(r['mae'])-expected)<1e-12,(r,b)
with (HERE/'candidate-main-metrics-20261023.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
groups=collections.defaultdict(list)
for r in rows:groups[(r['outcome'],r['horizon_s'],r['model'])].append(r)
summary=[]
for (outcome,horizon,model),group in sorted(groups.items()):
    item=dict(outcome=outcome,horizon_s=int(horizon),model=model,folds=sorted(r['fold'] for r in group),n=sum(int(r['test_n']) for r in group))
    for metric in ('mae','brier','logloss','direction_accuracy'):
        eligible=[r for r in group if r[metric] and math.isfinite(float(r[metric]))]
        item[metric]=sum(float(r[metric])*int(r['test_n']) for r in eligible)/sum(int(r['test_n']) for r in eligible) if eligible else None
    item['rmse']=math.sqrt(sum(float(r['rmse'])**2*int(r['test_n']) for r in group)/item['n'])
    summary.append(item)
lookup={(r['outcome'],r['horizon_s'],r['model']):r for r in summary}
comparison=[]
for r in summary:
    if r['model'] in ('training_frequency','training_mean','zero_change','evotrees_q10','evotrees_q90') or len(r['folds'])!=3:continue
    baseline='training_frequency' if r['outcome']=='first_observed_family_within_h' else 'zero_change'
    b=lookup.get((r['outcome'],r['horizon_s'],baseline))
    if not b or b['folds']!=r['folds']:continue
    metric='brier' if baseline=='training_frequency' else 'mae'
    if not b[metric]:continue
    full=groups[(r['outcome'],str(r['horizon_s']),r['model'])]
    bases={row['fold']:row for row in groups[(r['outcome'],str(r['horizon_s']),baseline)]}
    comparison.append(dict(outcome=r['outcome'],horizon_s=r['horizon_s'],model=r['model'],metric=metric,
        model_error=r[metric],baseline_error=b[metric],improvement_pct=100*(1-r[metric]/b[metric]),
        fold_wins=sum(float(row[metric])<float(bases[row['fold']][metric]) for row in full),n=r['n']))
    if baseline=='zero_change':
        med=sum(bench[(r['outcome'],str(r['horizon_s']),row['fold'])]['median_mae']*int(row['test_n']) for row in full)/r['n']
        comparison[-1].update(training_median_mae=med,improvement_vs_median_pct=100*(1-r['mae']/med),
            median_fold_wins=sum(float(row['mae'])<bench[(r['outcome'],str(r['horizon_s']),row['fold'])]['median_mae'] for row in full))
all_ablation=[]
for bundle in aux['ablations']:
    body=json.loads(gzip.decompress(base64.b64decode(bundle['data'])))
    all_ablation.extend(dict(zip(body['columns'],r)) for r in body['rows'])
by_ablation=collections.defaultdict(list)
for r in all_ablation:by_ablation[(r['outcome'],r['horizon_s'],r['model'])].append(r)
fulls={(r['outcome'],r['horizon_s'],r['fold']):r for r in rows if r['model']=='evotrees_depth3'}
ablations=[]
for (outcome,h,model),group in sorted(by_ablation.items()):
    assert len(group)==3
    metric='brier' if outcome=='first_observed_family_within_h' else 'mae'
    n=sum(int(r['test_n']) for r in group)
    full=sum(float(fulls[(outcome,h,r['fold'])][metric])*int(r['test_n']) for r in group)/n
    dropped=sum(float(r[metric])*int(r['test_n']) for r in group)/n
    diffs=[float(r[metric])-float(fulls[(outcome,h,r['fold'])][metric]) for r in group]
    ablations.append(dict(outcome=outcome,horizon_s=int(h),group=model[10:],metric=metric,
        removal_error_increase_pct=100*(dropped/full-1),folds_worse_on_removal=sum(d>1e-12 for d in diffs),
        folds_better_on_removal=sum(d< -1e-12 for d in diffs),n=n))
(HERE/'candidate-main-summary-20261023.json').write_text(json.dumps(dict(summary=summary,comparisons=comparison,ablations=ablations,benchmark_checks=63),indent=2)+'\n')
print(json.dumps(dict(rows=len(rows),cohorts=len({k[:3] for k in keys}),models=sorted({r['model'] for r in rows}),
    missing_main_models=[dict(outcome=k[0],horizon=k[1],model=k[2],folds=[r['fold'] for r in v]) for k,v in groups.items() if len(v)!=3])))
for outcome in sorted({r['outcome'] for r in comparison}):
    print('\nOUTCOME',outcome)
    for r in comparison:
        if r['outcome']==outcome and r['model'] in ('evotrees_depth3','drop_history'):
            print(json.dumps(r))
print('\nREMOVAL HURTS ALL THREE FOLDS:')
for r in sorted((r for r in ablations if r['folds_worse_on_removal']==3),key=lambda r:-r['removal_error_increase_pct'])[:20]:print(json.dumps(r))
print('\nREMOVAL HELPS ALL THREE FOLDS:')
for r in sorted((r for r in ablations if r['folds_better_on_removal']==3),key=lambda r:r['removal_error_increase_pct'])[:10]:print(json.dumps(r))
