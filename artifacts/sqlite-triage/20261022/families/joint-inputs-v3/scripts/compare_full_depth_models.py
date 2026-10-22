"""Compare every v3 refit with v1 on unchanged heldout cohorts."""
import csv
import json
import math
import os
import pathlib
from summarize_layer_review import read, write, group, num


def main():
    b=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    a=b/'joint-models-v1';z=b/'joint-models-v3';out=b/'layer-review-v3'
    assert json.loads((z/'complete.json').read_text())['all_models_refit']
    old=read(a/'all_model_fold_metrics.csv');new=read(z/'all_model_fold_metrics.csv')
    key=lambda r:(r['outcome'],r['horizon_s'],r['fold'],r['model'])
    am={key(r):r for r in old};zm={key(r):r for r in new}
    assert am.keys()==zm.keys(),(len(am),len(zm))
    changes=[]
    for k,r in sorted(zm.items()):
        prior=am[k];assert r['test_n']==prior['test_n'] and r['train_n']==prior['train_n']
        binary=r['outcome']=='first_observed_family_within_h';metric='brier' if binary else 'mae'
        changes.append(dict(outcome=k[0],horizon_s=k[1],fold=k[2],model=k[3],test_n=int(r['test_n']),
            loss=metric,v1_loss=num(prior[metric]),v3_loss=num(r[metric]),v3_minus_v1=num(r[metric])-num(prior[metric])))
    write(out/'all_v1_v3_fold_changes.csv',changes)
    comparisons=[]
    for k,rs in sorted(group(changes,['outcome','horizon_s','model']).items()):
        n=sum(r['test_n'] for r in rs);aa=sum(r['v1_loss']*r['test_n'] for r in rs)/n;zz=sum(r['v3_loss']*r['test_n'] for r in rs)/n
        baseline='training_frequency' if k[0]=='first_observed_family_within_h' else 'training_median'
        bases=[r for r in new if r['outcome']==k[0] and r['horizon_s']==k[1] and r['model']==baseline]
        metric=rs[0]['loss'];bm=sum(num(r[metric])*int(r['test_n']) for r in bases)/n
        comparisons.append(dict(outcome=k[0],horizon_s=k[1],model=k[2],loss=metric,heldout_n=n,v1_loss=aa,v3_loss=zz,
            relative_v3_reduction_vs_v1=1-zz/aa if aa else '',v3_benchmark=baseline,benchmark_loss=bm,
            v3_reduction_vs_benchmark=1-zz/bm if bm else '',
            folds_v3_better_than_v1=sum(r['v3_minus_v1']< -1e-14 for r in rs),
            folds_v3_better_than_benchmark=sum(num(zm[(k[0],k[1],r['fold'],k[2])][metric])<num(zm[(k[0],k[1],r['fold'],baseline)][metric])-1e-14 for r in rs)))
    write(out/'all_v1_v3_model_comparisons.csv',comparisons)
    # Check heldout sample IDs and observed labels for one canonical model on all 63 tasks.
    cohorts=[]
    for directory in [a,z]:
        rs=read(directory/'model_predictions.csv')
        cohorts.append({(r['sample_id'],r['outcome'],r['horizon_s'],r['fold'],r['observed']) for r in rs if r['model']=='evotrees_depth3'})
        del rs
    assert cohorts[0]==cohorts[1], 'v1/v3 heldout label or sample mismatch'
    crossing=[]
    for k,rs in sorted(group([r for r in new if r['outcome']=='mid_price_change'],['horizon_s','model']).items()):
        n=sum(int(r['spread_threshold_active_n']) for r in rs)
        crossing.append(dict(horizon_s=k[0],model=k[1],active_n=n,
            weighted_mean_quote_crossing_return=sum(num(r['mean_quote_crossing_return'])*int(r['spread_threshold_active_n']) for r in rs if int(r['spread_threshold_active_n']))/n if n else '',
            fold_means='|'.join(r['mean_quote_crossing_return'] for r in rs),
            negative_folds=sum(num(r['mean_quote_crossing_return'])<0 for r in rs),
            limitation='no fees/slippage/latency/queue impact/fill guarantees;overlapping observations'))
    write(out/'all_quote_crossing_summary.csv',crossing)
    primary={'evotrees_depth3','evotrees_depth5','evotrees_mae','neural_tree','residual_mlp','tabm_ensemble'}
    chosen=[r for r in comparisons if r['model'] in primary]
    report={'all_1815_fold_metric_keys_and_cohort_counts_match_v1':True,'all_heldout_sample_ids_and_observed_labels_match_v1':True,
        'metric_rows':len(changes),'comparison_rows':len(comparisons),
        'primary_configuration_horizon_n':len(chosen),'primary_configs_better_than_v1':sum(num(r['relative_v3_reduction_vs_v1'])>0 for r in chosen),
        'primary_configs_worse_than_v1':sum(num(r['relative_v3_reduction_vs_v1'])<0 for r in chosen),
        'primary_configs_better_than_benchmark':sum(num(r['v3_reduction_vs_benchmark'])>0 for r in chosen),
        'selected_reporting_horizons':[r for r in chosen if r['horizon_s'] in ['120','600','3600']],
        'v3_tabm_3600_quote_crossing':[r for r in crossing if r['horizon_s']=='3600' and r['model']=='tabm_ensemble'],
        'claim':'No established tradable signal; exploratory intraday comparison, no independent day or multiple-comparison significance.'}
    (out/'v1_v3_comparison_receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
