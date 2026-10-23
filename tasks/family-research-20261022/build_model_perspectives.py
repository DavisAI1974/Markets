"""Synthesize complementary model perspectives from the completed candidate only."""
import json,pathlib,re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/sqlite-triage/20261022/families/final-model-analysis-20261023'
SRC=OUT/'source';TABLES=OUT/'tables';FIG=OUT/'figures'
TABLES.mkdir(exist_ok=True);FIG.mkdir(exist_ok=True)
def read(name):return pd.read_csv(SRC/name,keep_default_na=True)
def save(name,frame):frame.to_csv(TABLES/name,index=False)
def records(frame):return json.loads(frame.to_json(orient='records'))
POINT=['ridge100','evotrees_depth3','evotrees_depth5','evotrees_mae','neural_tree','residual_mlp','tabm_ensemble']
metrics=read('all_model_fold_metrics.csv')
key=['outcome','horizon_s','fold','model']
assert len(metrics)==2151 and not metrics.duplicated(key).any()
assert metrics.groupby(key[:-1]).ngroups==63
assert (metrics.groupby(key[:-1]).test_n.nunique()==1).all()
assert int((metrics.model=='training_median').sum())==54
alignment=read('heldout_alignment_audit.csv');assert len(alignment)==63 and alignment.same_heldout_sample_labels.all()
profiles=read('model_comparison_summary.csv')
assert len(profiles)==717 and (profiles.folds==3).all()
extras=[]
for k,g in metrics.groupby(['outcome','horizon_s','model']):
    row=dict(zip(['outcome','horizon_s','model'],k));row['fitted_columns_min']=int(g.fitted_columns.min());row['fitted_columns_max']=int(g.fitted_columns.max())
    for col in ['logloss','direction_accuracy']:
        a=g.dropna(subset=[col]);row['weighted_'+col]=float(np.average(a[col],weights=a.test_n)) if len(a) else np.nan
    row.update(fold_mae_min=float(g.mae.min()),fold_mae_max=float(g.mae.max()))
    extras.append(row)
profiles=profiles.merge(pd.DataFrame(extras),on=['outcome','horizon_s','model'],validate='one_to_one')
save('all_717_model_profiles.csv',profiles)
save('all_2151_fold_metrics.csv',metrics)
print('Final metrics and matching63cohorts checked',flush=True)

# Keep all saved source-block refits. Positive removal delta means that block was
# useful to this specific fitted shallow model, not a causal physical influence.
full=metrics[metrics.model=='evotrees_depth3'].set_index(key[:-1])
abl=[]
for _,r in metrics[metrics.model.str.startswith('dropgroup:') | (metrics.model=='drop_history')].iterrows():
    b=full.loc[(r.outcome,r.horizon_s,r.fold)];measure='brier' if r.outcome=='first_observed_family_within_h' else 'mae'
    abl.append(dict(outcome=r.outcome,horizon_s=int(r.horizon_s),fold=int(r.fold),group=r.model[10:] if r.model.startswith('dropgroup:') else 'ALL_HISTORY',test_n=int(r.test_n),measure=measure,full_error=float(b[measure]),removed_error=float(r[measure]),delta=float(r[measure]-b[measure])))
abl=pd.DataFrame(abl);save('all_1440_removal_fold_effects.csv',abl)
effects=[]
for k,g in abl.groupby(['outcome','horizon_s','group','measure']):
    base=np.average(g.full_error,weights=g.test_n);removed=np.average(g.removed_error,weights=g.test_n)
    effects.append(dict(zip(['outcome','horizon_s','group','measure'],k),full_error=base,removed_error=removed,removal_error_change_pct=100*(removed/base-1),folds_removal_increases_error=int((g.delta>1e-12).sum()),folds_removal_decreases_error=int((g.delta< -1e-12).sum()),flat_folds=int((g.delta.abs()<=1e-12).sum())))
effects=pd.DataFrame(effects);save('all_480_removal_contexts.csv',effects)

# Training structure is a separate lens from held-out effects.
features=read('fitted_split_features.csv')
features['depth_rank']=features.feature.str.extract(r'(?:bid|ask)_levels\.rank(\d+)')[0].astype(float)
features['depth_scope']=np.select([features.depth_rank>10,features.depth_rank.between(1,10)],['beyond_level_10','levels_1_to_10'],default='other_features')
scope=features.groupby(key+['depth_scope'],as_index=False).agg(gain_share=('within_fit_gain_share','sum'),split_count=('split_count','sum'),feature_rows=('feature','size'))
save('tree_depth_scope_by_fit.csv',scope)
gain=features.groupby(key+['source_group'],as_index=False).agg(gain_share=('within_fit_gain_share','sum'),split_count=('split_count','sum'))
save('tree_source_gain_by_fit.csv',gain)
contrasts=read('heldout_joint_response_contrasts.csv')
contrasts['min_corner_n']=contrasts.corner_counts.str.split('|',regex=False).map(lambda x:min(map(int,x)))
eligible=contrasts[contrasts.observed_four_cell_contrast.notna() & (contrasts.min_corner_n>=10)].copy()
save('all_629_interaction_support.csv',contrasts)
save('supported_interactions.csv',eligible.sort_values(['min_corner_n','outcome'],ascending=[False,True]))
pairkeys=['feature_a','feature_b','outcome','horizon_s']
rep=eligible.groupby(pairkeys,as_index=False).agg(folds=('fold','nunique'),models=('model','nunique'),rows=('fold','size')) if len(eligible) else pd.DataFrame()
save('interaction_cross_fold_support.csv',rep)

# Read the already-produced predictions. Neither fits nor original finalizers run.
frames=[]
for filename,expected in [('model_predictions.csv',1181946),('neural_predictions.csv',118203)]:
    n=0
    for chunk in pd.read_csv(SRC/filename,chunksize=100000):
        n+=len(chunk)
        frames.append(chunk[chunk.model.isin(POINT+['evotrees_q10','evotrees_q90','drop_history'])].copy())
    assert n==expected,(filename,n)
pred=pd.concat(frames,ignore_index=True)
pk=['outcome','horizon_s','fold','sample_id']
assert not pred.duplicated(pk+['model']).any()
assert pred.groupby(pk)['observed'].nunique().max()==1
actual=pred.groupby(key).size().rename('prediction_n').reset_index().merge(metrics[key+['test_n']],on=key,validate='one_to_one')
assert (actual.prediction_n==actual.test_n).all()
print('Prediction rows matched declared model samples',flush=True)
point=pred[pred.model.isin(POINT)].copy();point['error']=point.prediction-point.observed;point['abs_error']=point.error.abs()
behavior=point.groupby(['outcome','horizon_s','model'],as_index=False).agg(n=('sample_id','size'),mean_prediction=('prediction','mean'),mean_observed=('observed','mean'),prediction_sd=('prediction','std'),observed_sd=('observed','std'),mae=('abs_error','mean'),negative_forecast_n=('prediction',lambda s:int((s< -1e-12).sum())),positive_forecast_n=('prediction',lambda s:int((s>1e-12).sum())))
save('model_response_profiles.csv',behavior)
save('all_144_point_model_perspectives.csv',behavior.merge(profiles,on=['outcome','horizon_s','model'],validate='one_to_one',suffixes=('','_profile')))
phase=point.groupby(['outcome','horizon_s','fold','model','phase'],as_index=False).agg(n=('sample_id','size'),mean_prediction=('prediction','mean'),mean_observed=('observed','mean'),mae=('abs_error','mean'))
save('phase_model_perspectives.csv',phase)
master=read('model_sample_master.csv')
context=point.merge(master[['sample_id','pre_direction']],on='sample_id',validate='many_to_one')
context=context[context.outcome=='mid_price_change'].copy()
context['observed_up']=context.observed>1e-12
context['observed_down']=context.observed< -1e-12
context['observed_flat']=context.observed.abs()<=1e-12
context['prior_sign']=context.pre_direction.map({'up':1,'down':-1})
context['prior_aligned_observed']=context.prior_sign*context.observed
context['prior_aligned_prediction']=context.prior_sign*context.prediction
context['reversal']=context.prior_aligned_observed< -1e-12
context['continuation']=context.prior_aligned_observed>1e-12
phaseprior=context.groupby(['outcome','horizon_s','fold','model','phase','pre_direction'],as_index=False).agg(n=('sample_id','size'),mean_prediction=('prediction','mean'),mean_observed=('observed','mean'),mae=('abs_error','mean'),observed_up_n=('observed_up','sum'),observed_down_n=('observed_down','sum'),observed_flat_n=('observed_flat','sum'),mean_prior_aligned_observed=('prior_aligned_observed','mean'),mean_prior_aligned_prediction=('prior_aligned_prediction','mean'),reversal_n=('reversal','sum'),continuation_n=('continuation','sum'))
save('signed_phase_and_prior_trade_direction.csv',phaseprior)
obsolete=TABLES/'phase_and_prior_trade_direction.csv'
if obsolete.exists():obsolete.unlink()

# Joint model views: disagreement is retained, not converted into a chosen model
# or an ensemble trading rule. Quantiles are not mixed with point forecasts.
piv=point.pivot(index=pk,columns='model',values='prediction')
truth=point.groupby(pk)['observed'].first();agreement=[];corr=[]
for (outcome,h,fold),g in piv.groupby(level=[0,1,2]):
    g=g.dropna(axis=1,how='all');a=g.to_numpy();y=truth.loc[g.index].to_numpy()
    signs=np.where(a>1e-12,1,np.where(a< -1e-12,-1,0));same=np.all(signs==signs[:,:1],axis=1)
    agreement.append(dict(outcome=outcome,horizon_s=int(h),fold=int(fold),n=len(g),models=g.shape[1],all_models_same_sign_n=int(same.sum()),all_models_same_sign_fraction=float(same.mean()),cross_model_iqr_median=float(np.median(np.quantile(a,.75,axis=1)-np.quantile(a,.25,axis=1))),mean_observed=float(y.mean())))
    cm=g.corr()
    for m in cm.index:
        for n in cm.columns:
            if m<n:corr.append(dict(outcome=outcome,horizon_s=int(h),fold=int(fold),model_a=m,model_b=n,prediction_correlation=cm.loc[m,n]))
agreement=pd.DataFrame(agreement);save('cross_model_agreement.csv',agreement);save('cross_model_prediction_correlations.csv',pd.DataFrame(corr))

binary=point[point.outcome=='first_observed_family_within_h'].copy()
binary['probability_bin']=np.minimum((binary.prediction*10).astype(int),9)
cal=binary.groupby(['horizon_s','fold','model','probability_bin'],as_index=False).agg(n=('observed','size'),mean_probability=('prediction','mean'),observed_frequency=('observed','mean'))
save('occurrence_calibration.csv',cal)

lower=pred[pred.model=='evotrees_q10'].set_index(pk);upper=pred[pred.model=='evotrees_q90'].set_index(pk)
assert lower.index.equals(upper.index) or set(lower.index)==set(upper.index)
tails=lower[['observed','prediction']].rename(columns={'prediction':'lower'}).join(upper[['prediction']].rename(columns={'prediction':'upper'}),validate='one_to_one').reset_index()
tails['covered']=(tails.lower<=tails.observed)&(tails.observed<=tails.upper);tails['crossed']=tails.lower>tails.upper;tails['width']=tails.upper-tails.lower;tails['below']=tails.observed<tails.lower;tails['above']=tails.observed>tails.upper;tails['negative_lower']=tails.lower<0
tail= tails.groupby(['outcome','horizon_s','fold'],as_index=False).agg(n=('observed','size'),coverage=('covered','mean'),crossed_n=('crossed','sum'),mean_width=('width','mean'),below_n=('below','sum'),above_n=('above','sum'),negative_lower_n=('negative_lower','sum'))
assert len(tail)==54;save('quantile_interval_coverage.csv',tail)

signed=point[point.outcome=='mid_price_change'].copy();signed['active']=signed.prediction.abs()>signed.initial_spread
signed['quote_return']=np.where(signed.prediction>0,signed.long_crossing_return,signed.short_crossing_return)
cross=signed[signed.active & signed.quote_return.notna()].groupby(['horizon_s','fold','model'],as_index=False).agg(active_n=('quote_return','size'),mean_quote_crossing_return=('quote_return','mean'),median_quote_crossing_return=('quote_return','median'),positive_n=('quote_return',lambda s:int((s>1e-12).sum())))
save('quote_crossing_context_only.csv',cross)

states=read('market_state_assignments.csv')
sizes=states.groupby(['model','cluster','chronological_quarter','phase'],as_index=False).size()
save('market_state_membership.csv',sizes)
regime=read('market_state_model_diagnostics.csv')
assert len(regime)==2844
reg=[]
for k,g in regime.groupby(['state_model','state','outcome','horizon_s','model']):
    reg.append(dict(zip(['state_model','state','outcome','horizon_s','model'],k),n=int(g.heldout_n.sum()),mean_prediction=float(np.average(g.mean_prediction,weights=g.heldout_n)),mean_observed=float(np.average(g.mean_observed,weights=g.heldout_n)),mae=float(np.average(g.mae,weights=g.heldout_n)),folds=int(g.fold.nunique())))
reg=pd.DataFrame(reg);save('market_state_perspectives.csv',reg)
paths=read('observed_price_paths.csv');paths['no_trade_update']=paths.observed_trade_increment_n==0
pathsummary=paths.groupby('horizon_s',as_index=False).agg(master_rows=('sample_id','size'),available_rows=('observed_trade_range','count'),mean_trade_range=('observed_trade_range','mean'),mean_abs_trade_endpoint=('observed_trade_endpoint_change',lambda x:float(x.abs().mean())),median_path_efficiency=('observed_trade_path_efficiency','median'),no_trade_update_n=('no_trade_update','sum'))
save('observed_path_perspective.csv',pathsummary)

# Views of response, structure and uncertainty. No performance leaderboard.
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
labels={'ridge100':'Linear ridge','evotrees_depth3':'Shallow trees','evotrees_depth5':'Deeper trees','evotrees_mae':'Median-loss trees','neural_tree':'NeuralTree','residual_mlp':'Residual MLP','tabm_ensemble':'TabM'}
colors=dict(zip(POINT,plt.get_cmap('tab10').colors))
fig,axes=plt.subplots(3,1,figsize=(11,12),constrained_layout=True)
for ax,outcome,title in zip(axes,['first_observed_family_within_h','absolute_mid_price_change','mid_price_change'],['Activity: mean family-occurrence probability','Magnitude: mean absolute net midquote move','Direction: mean signed midquote move']):
    sub=behavior[behavior.outcome==outcome]
    for model,g in sub.groupby('model',sort=False):
        g=g.sort_values('horizon_s');ax.plot(g.horizon_s,g.mean_prediction,marker='o',ms=3,label=labels[model],color=colors[model])
    observed=sub.groupby('horizon_s').mean_observed.first().sort_index();ax.plot(observed.index,observed.values,color='black',lw=2,ls='--',label='Observed mean')
    ax.set_xscale('log');ax.set_xlabel('Horizon (seconds, logarithmic scale)');ax.set_title(title,loc='left');ax.grid(alpha=.2)
legend_handles,legend_labels=axes[1].get_legend_handles_labels()
axes[0].legend(legend_handles,legend_labels,ncol=4,fontsize=8,loc='upper left',bbox_to_anchor=(0,1.32));fig.suptitle('Different model perspectives on the same completed expanded-depth candidate',fontsize=14)
fig.savefig(FIG/'model-response-perspectives.png',dpi=160);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
for ax,outcome,title in zip(axes,['absolute_mid_price_change','mid_price_change'],['Magnitude intervals','Signed-move intervals']):
    sub=tail[tail.outcome==outcome]
    for fold,g in sub.groupby('fold'):
        g=g.sort_values('horizon_s');ax.plot(g.horizon_s,g.coverage,marker='o',label='Test fold '+str(fold))
    ax.axhline(.8,color='black',ls='--',label='Nominal 80%');ax.set_xscale('log');ax.set_ylim(0,1);ax.set_title(title,loc='left');ax.set_xlabel('Horizon (seconds)');ax.set_ylabel('Observed interval coverage');ax.grid(alpha=.2)
axes[0].legend(fontsize=8);fig.suptitle('Tail perspective: interval coverage is distinct from point-forecast error');fig.savefig(FIG/'tail-coverage-perspectives.png',dpi=160);plt.close(fig)

summary=dict(status='completed_candidate_perspective_analysis',metrics=2151,mandatory_fits=2097,main_profiles=717,prediction_cohort_checks=63,
    features=len(features),deep_rank_max=int(features.depth_rank.max()),deep_feature_rows=int((features.depth_rank>10).sum()),
    tree_fits_using_deep=int(scope[scope.depth_scope=='beyond_level_10'].groupby(key).ngroups),
    interaction_contrasts=len(contrasts),supported_interactions=len(eligible),unsupported_interactions=len(contrasts)-len(eligible),
    pairs_supported_in_multiple_folds=int((rep.folds>=2).sum()) if len(rep) else 0,
    all_flat_ablation_contexts=int((effects.flat_folds==3).sum()),same_direction_removal_increases=int((effects.folds_removal_increases_error==3).sum()),same_direction_removal_decreases=int((effects.folds_removal_decreases_error==3).sum()),
    negative_magnitude_predictions=records(behavior[behavior.outcome=='absolute_mid_price_change'].groupby('model',as_index=False).agg(n=('n','sum'),negative_forecast_n=('negative_forecast_n','sum'))),
    tail_coverage=records(tail.groupby('outcome',as_index=False).agg(min_fold_coverage=('coverage','min'),max_fold_coverage=('coverage','max'),crossed_n=('crossed_n','sum'))),
    cluster_sizes=records(states.groupby(['model','cluster'],as_index=False).size()),
    source_scope='expanded candidate only, not V1/V3 model rankings',coverage_gate='NOT_PASSED',
    model_policy='Complementary perspectives; no selected winner, ensemble fitting, trading rule or causal conclusion.')
(OUT/'analysis-receipt.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)

# Exhaustive model appendix, with the same display order for every question.
details=['# Recorded perspectives for every point model','',
    'Completed expanded-depth candidate only. All rows pool the three chronological held-out folds by sample count; they are not three independent market days. Price changes are in recorded price units. MAE is mean absolute error, not movement size. Forecast means are descriptive; median-loss trees target a different functional from squared-loss models. No overall rank or ensemble is calculated.','',
    'Every matching fold, refit, benchmark and quantile score is retained in [all 2,151 fold metrics](tables/all_2151_fold_metrics.csv). Invalid negative magnitude predictions are counted without clipping.','']
for model in POINT:
    details.extend(['## '+labels[model],''])
    for outcome,title in [('first_observed_family_within_h','Family occurrence'),('absolute_mid_price_change','Absolute net midquote move'),('mid_price_change','Signed net midquote move')]:
        sub=behavior[(behavior.model==model)&(behavior.outcome==outcome)].sort_values('horizon_s')
        if sub.empty:continue
        details.extend(['### '+title,'','| Horizon (s) | Held-out rows | Observed mean | Forecast mean | MAE | Negative forecasts |','|---:|---:|---:|---:|---:|---:|'])
        for r in sub.itertuples():details.append(f'| {r.horizon_s} | {r.n:,} | {r.mean_observed:.6f} | {r.mean_prediction:.6f} | {r.mae:.6f} | {r.negative_forecast_n:,} |')
        details.append('')
(OUT/'model-by-model-details.md').write_text('\n'.join(details).rstrip()+'\n',encoding='utf-8')
