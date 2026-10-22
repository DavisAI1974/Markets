"""Describe every saved pair/ablation; no significance or causal claims."""
import collections
import csv
import gzip
import json
import math
import os
import pathlib
import statistics


def read(path):
    if not path.exists(): path=path.with_suffix(path.suffix+'.gz')
    with (gzip.open(path,'rt',newline='') if path.suffix=='.gz' else path.open(newline='')) as f:
        return list(csv.DictReader(f))


def num(value):
    try: return float(value)
    except (TypeError,ValueError): return math.nan


def write(path, rows):
    if not rows:return
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def group(rows, keys):
    result=collections.defaultdict(list)
    for r in rows: result[tuple(r[k] for k in keys)].append(r)
    return result


def sign(x):return (x>1e-14)-(x< -1e-14)


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    version=os.environ.get('LAYER_REVIEW_VERSION','v3');out=base/('layer-review-'+version)
    models=base/('joint-models-'+version)
    pairs=read(out/'pair_audit.csv');cells=read(out/'response_cells_with_missingness.csv')
    strata=read(out/'matched_context_contrasts.csv')
    eligible=[r for r in pairs if math.isfinite(num(r['contrast']))]
    matching=[]
    bypair={r['pair_id']:r for r in pairs}
    for mode,rs in group(strata,['matching']).items():
        for minimum in [10,5]:
            key='contrast_min'+str(minimum)
            good=[r for r in rs if math.isfinite(num(r[key]))]
            flips=[r for r in good if math.isfinite(num(bypair[r['pair_id']]['contrast'])) and
                   sign(num(r[key]))*sign(num(bypair[r['pair_id']]['contrast']))<0]
            matching.append(dict(matching=mode[0],min_per_corner=minimum,eligible_strata=len(good),
                pairs_with_eligible_stratum=len({r['pair_id'] for r in good}),
                opposite_sign_vs_pooled_strata=len(flips),pairs_with_opposite_sign=len({r['pair_id'] for r in flips})))
    write(out/'matching_summary.csv',matching)
    # Repetition is exact feature-pair identity within a target/horizon/model.
    # Swapping A/B leaves the four-corner contrast unchanged.
    repeated=collections.defaultdict(list)
    for r in pairs:
        key=(r['outcome'],r['horizon_s'],r['model'],*sorted([r['feature_a'],r['feature_b']]))
        repeated[key].append(r)
    stability=[]
    for key,rs in sorted(repeated.items()):
        good=[r for r in rs if math.isfinite(num(r['contrast']))]
        signs={sign(num(r['contrast'])) for r in good}
        stability.append(dict(outcome=key[0],horizon_s=key[1],model=key[2],feature_a=key[3],feature_b=key[4],
            selected_folds=len({r['fold'] for r in rs}),eligible_folds=len({r['fold'] for r in good}),
            eligible_fold_signs='|'.join(f"{r['fold']}:{num(r['contrast']):.10g}" for r in good),
            opposite_signs_across_folds=(-1 in signs and 1 in signs)))
    write(out/'exact_pair_fold_stability.csv',stability)
    coverage=[]
    for key,rs in sorted(group(pairs,['outcome','horizon_s','fold','model']).items()):
        good=[r for r in rs if math.isfinite(num(r['contrast']))]
        coverage.append(dict(zip(['outcome','horizon_s','fold','model'],key),selected_pairs=len(rs),
            eligible_pairs=len(good),pairs_with_missing_raw_values=sum(num(r['joint_finite_n'])<num(r['heldout_n']) for r in rs),
            pairs_abs_train_corr_ge_095=sum(abs(num(r['train_corr']))>=.95 for r in rs),
            pairs_abs_test_corr_ge_095=sum(abs(num(r['test_corr']))>=.95 for r in rs)))
    write(out/'pair_coverage_summary.csv',coverage)
    # All group refits retained. Use Brier for binary occurrence, MAE for price.
    absrows=read(models/'source_group_ablation_comparisons.csv');ablations=[]
    for key,rs in sorted(group(absrows,['outcome','horizon_s','source_group']).items()):
        binary=key[0]=='first_observed_family_within_h'
        full='full_brier' if binary else 'full_model_mae';drop='drop_brier' if binary else 'drop_group_mae'
        n=sum(int(r['test_n']) for r in rs)
        f=sum(num(r[full])*int(r['test_n']) for r in rs)/n
        d=sum(num(r[drop])*int(r['test_n']) for r in rs)/n
        diffs=[num(r[drop])-num(r[full]) for r in rs]
        ablations.append(dict(outcome=key[0],horizon_s=key[1],source_group=key[2],loss='brier' if binary else 'mae',
            heldout_n=n,full_loss=f,drop_loss=d,relative_drop_loss_increase=(d/f-1 if f else ''),
            helped_folds=sum(v>1e-14 for v in diffs),hurt_folds=sum(v< -1e-14 for v in diffs),
            flat_folds=sum(abs(v)<=1e-14 for v in diffs),fold_deltas='|'.join(f'{v:.10g}' for v in diffs)))
    write(out/'all_ablation_summaries.csv',ablations)
    # Conditional path inventory counts are training structure, not independent evidence.
    treepairs=read(models/'fitted_conditional_split_pairs.csv')
    tree_summary=[]
    for key,rs in sorted(group(treepairs,['outcome','horizon_s','fold','model']).items()):
        tree_summary.append(dict(zip(['outcome','horizon_s','fold','model'],key),pairs=len(rs),
            missingness_indicator_pairs=sum('.__missing' in r['feature_a'] or '.__missing' in r['feature_b'] for r in rs),
            history_pairs=sum(r['feature_a'].startswith('delta') or r['feature_b'].startswith('delta') for r in rs),
            reset_or_session_counter_pairs=sum(any(a in r[f] for f in ['feature_a','feature_b'] for a in ['activity_since.last_book_reset.','activity_since.session_open.']) for r in rs)))
    write(out/'conditional_tree_inventory_summary.csv',tree_summary)
    zero_cells=[r for r in cells if int(r['bin_a'])>0 and int(r['bin_b'])>0 and int(r['n'])==0]
    stats={'version':version,'selected_pairs':len(pairs),'eligible_contrasts':len(eligible),
        'eligible_signed_price_contrasts':sum(r['outcome']=='mid_price_change' for r in eligible),
        'ineligible_contrasts':len(pairs)-len(eligible),'nonmissing_empty_response_cells':len(zero_cells),
        'pairs_with_raw_missing_values':sum(int(r['joint_finite_n'])<int(r['heldout_n']) for r in pairs),
        'selected_pairs_with_missing_indicator':sum('.__missing' in r['feature_a'] or '.__missing' in r['feature_b'] for r in pairs),
        'selected_pairs_abs_train_corr_ge095':sum(abs(num(r['train_corr']))>=.95 for r in pairs),
        'selected_pairs_abs_test_corr_ge095':sum(abs(num(r['test_corr']))>=.95 for r in pairs),
        'exact_pairs_selected_in_2plus_folds':sum(r['selected_folds']>=2 for r in stability),
        'exact_pairs_eligible_in_2plus_folds':sum(r['eligible_folds']>=2 for r in stability),
        'exact_pairs_with_opposite_fold_signs':sum(r['opposite_signs_across_folds'] for r in stability),
        'matching':matching,'ablation_groups':len(ablations),'ablation_all_folds_flat':sum(r['flat_folds']==3 for r in ablations),
        'ablation_all_folds_helped':sum(r['helped_folds']==3 for r in ablations),
        'ablation_all_folds_hurt':sum(r['hurt_folds']==3 for r in ablations),
        'conditional_tree_pair_rows':len(treepairs),'limits':'overlapping contexts and one day; posthoc matching; no p-values, causal synergy or executable-edge claim'}
    (out/'summary.json').write_text(json.dumps(stats,indent=2)+'\n')
    print(json.dumps(stats),flush=True)


if __name__=='__main__':main()
