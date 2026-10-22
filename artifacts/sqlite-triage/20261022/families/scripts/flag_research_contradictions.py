"""Keep unresolved within-run scientific conflicts visible, without retuning fits."""
import hashlib
import json
import math
import os
import pathlib
from summarize_layer_review import read, write, group, num, sign


def main():
    b=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    version=os.environ.get('LAYER_REVIEW_VERSION','v3');out=b/('layer-review-'+version);models=b/('joint-models-'+version)
    model_only=os.environ.get('CONTRADICTION_MODEL_ONLY')=='1'
    out.mkdir(exist_ok=True)
    pairs={} if model_only else {r['pair_id']:r for r in read(out/'pair_audit.csv')};flags=[]
    def add(kind, key, one, two, support, source, question):
        identity=json.dumps([version,kind,key],sort_keys=True)
        flags.append(dict(research_id=hashlib.sha256(identity.encode()).hexdigest()[:20],run_version=version,
            conflict_type=kind,comparison_key=json.dumps(key,sort_keys=True),answer_one=str(one),answer_two=str(two),
            support=json.dumps(support,sort_keys=True),evidence_file=source,research_status='open',
            scientific_question=question,disposition='unresolved;descriptive;no_signal_promotion_or_test_based_retuning'))
    for r in ([] if model_only else read(out/'matched_context_contrasts.csv')):
        p=pairs[r['pair_id']];a,c=num(p['contrast']),num(r['contrast_min10'])
        if math.isfinite(a) and math.isfinite(c) and sign(a)*sign(c)<0:
            add('pooled_vs_matched_response_sign',dict(pair_id=r['pair_id'],outcome=r['outcome'],horizon_s=r['horizon_s'],
                fold=r['fold'],model=r['model'],matching=r['matching'],stratum=r['stratum'],feature_a=r['feature_a'],feature_b=r['feature_b']),
                a,c,dict(pooled_corners=p['corner_counts'],matched_corners=r['corner_counts'],stratum_n=r['n'],
                pooled_joint_finite_n=p['joint_finite_n'],pooled_heldout_n=p['heldout_n']),
                'matched_context_contrasts.csv + pair_audit.csv',
                'Does phase, prior direction, intraday chronology, source age, overlap or missingness explain the sign reversal? Same outcome/horizon/model; conditioning differs.')
    for r in ([] if model_only else read(out/'exact_pair_fold_stability.csv')):
        if r['opposite_signs_across_folds']=='True':
            add('exact_pair_response_sign_across_folds',dict(outcome=r['outcome'],horizon_s=r['horizon_s'],model=r['model'],
                feature_a=r['feature_a'],feature_b=r['feature_b']),r['eligible_fold_signs'],'opposite signs',
                dict(eligible_folds=r['eligible_folds'],selected_folds=r['selected_folds']),
                'exact_pair_fold_stability.csv','Does the same pair reverse across chronological heldout periods because of regime, cutpoints, source scope or limited support?')
    for r in ([] if model_only else read(out/'all_ablation_summaries.csv')):
        if int(r['helped_folds']) and int(r['hurt_folds']):
            add('source_block_helped_and_hurt_across_folds',dict(outcome=r['outcome'],horizon_s=r['horizon_s'],source_group=r['source_group']),
                f"helped {r['helped_folds']} folds",f"hurt {r['hurt_folds']} folds",
                dict(heldout_n=r['heldout_n'],fold_deltas=r['fold_deltas'],loss=r['loss']),
                'all_ablation_summaries.csv','Is the source contribution conditional on correlated layers, chronology or changing missingness rather than a stable independent effect?')
    metrics=read(models/'all_model_fold_metrics.csv')
    primary={'evotrees_depth3','evotrees_depth5','evotrees_mae','neural_tree','residual_mlp','tabm_ensemble','ridge100'}
    bases={(r['outcome'],r['horizon_s'],r['fold']):r for r in metrics if r['model'] in ['training_frequency','training_median']}
    for key,rs in sorted(group([r for r in metrics if r['model'] in primary],['outcome','horizon_s','model']).items()):
        field='brier' if key[0]=='first_observed_family_within_h' else 'mae'
        diffs=[num(r[field])-num(bases[(r['outcome'],r['horizon_s'],r['fold'])][field]) for r in rs]
        if any(v< -1e-14 for v in diffs) and any(v>1e-14 for v in diffs):
            add('model_beats_and_loses_to_benchmark_across_folds',dict(outcome=key[0],horizon_s=key[1],model=key[2]),
                'lower heldout loss in some folds','higher heldout loss in other folds',
                dict(loss=field,fold_deltas=diffs,test_n=[r['test_n'] for r in rs]),
                'all_model_fold_metrics.csv','Why does performance reverse across time? Compare target distributions, source availability, outliers and source-group refits; obtain independent days before a signal claim.')
    phases=read(models/'phase_direction_model_diagnostics.csv')
    rows=[r for r in phases if r['outcome']=='mid_price_change' and r['model'] in primary and int(r['heldout_n'])>=10]
    for key,rs in sorted(group(rows,['horizon_s','fold','phase','prior_direction']).items()):
        positive=[r for r in rs if num(r['mean_prediction'])>1e-8];negative=[r for r in rs if num(r['mean_prediction'])< -1e-8]
        if positive and negative:
            add('models_predict_opposite_mean_directions_same_cohort',dict(horizon_s=key[0],fold=key[1],phase=key[2],prior_direction=key[3]),
                {r['model']:num(r['mean_prediction']) for r in positive},
                {r['model']:num(r['mean_prediction']) for r in negative},
                dict(n=rs[0]['heldout_n'],mean_observed=rs[0]['mean_observed']),
                'phase_direction_model_diagnostics.csv','Different architectures answer the same signed-price/cohort question differently. Check calibration, preprocessing, error tails and source dependence; this is not two different buy/ask targets.')
    # Preserve researcher dispositions when the registry is regenerated.
    stem='model_conflict_research' if model_only else 'contradiction_research'
    dest=out/(stem+'_registry.csv')
    if dest.exists():
        old={r['research_id']:r for r in read(dest)}
        for r in flags:
            if r['research_id'] in old:r['research_status']=old[r['research_id']]['research_status']
    write(dest,flags)
    counts={key[0]:len(rs) for key,rs in group(flags,['conflict_type']).items()}
    receipt={'version':version,'review_scope':'model_metrics_and_cohort_direction_only' if model_only else 'full_saved_layer_review','research_flags':len(flags),'by_type':counts,
        'meaning':'Different strata/models/folds can give opposing answers; retained for scientific explanation, not hidden, resolved by cherry-picking or treated as automatic data errors.',
        'scope':'Same target/horizon and explicit context comparison; opposite bid/ask sides or distinct horizons are different questions and are not automatically logical contradictions.',
        'additional_inconclusive_cases':'See pair coverage/missing cells and matched-context support; absence of an eligible contrast is not evidence of no interaction.'}
    (out/(stem+'_receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))


if __name__=='__main__':main()
