"""Complementary causal indicator layers on the retained dipole cohort."""
import numpy as np
import pandas as pd
from flow_book_discovery import HERE, REV, GROUPS, NS, rows
from research_atlas import OUT, group_matrix, save, dump

LAYERS={
    'context':['prior_ticks20','range_ticks20','spread_ticks'],
    'dipole':['imb_level','imb_flow','ent_dipole','mi_flow','log_signed_C','strength_change',
              'early_empty','late_empty'],
    'fresh':['fresh_imb5','log_fresh_lots5','log_unknown_lots5'],
    'book':['touch_imb','touch_count_imb','log_touch_lots','log_touch_orders'],
    'display':['bid_add5','bid_remove5','ask_add5','ask_remove5','quote_price_changes5'],
}
ARMS={'baseline':[],**{f'plus_{k}':[k] for k in LAYERS if k!='context'},
      'dipole_book':['dipole','book'],'full':['dipole','fresh','book','display'],
      **{f'without_{k}':[v for v in LAYERS if v not in ('context',k)] for k in LAYERS if k!='context'}}


def same_price_changes(a):
    x=np.zeros((len(a),5),dtype=np.int64)
    for i in range(1,len(a)):
        p,c=a[i-1],a[i]
        if not (p[7] and c[7] and p[8]==c[8]):continue
        for price,size,offset in ((3,5,0),(4,6,2)):
            if p[price]==c[price]:
                delta=c[size]-p[size]
                x[i,offset]=max(0,delta);x[i,offset+1]=max(0,-delta)
            else:x[i,4]+=1
    return x


def ridge_predict(train,y,test):
    # Every column receives a missingness indicator, even when only test is missing.
    valid=np.isfinite(train)
    mean=np.divide(np.where(valid,train,0).sum(axis=0),valid.sum(axis=0),
                   out=np.zeros(train.shape[1]),where=valid.sum(axis=0)>0)
    a=np.where(valid,train,mean);b=np.where(np.isfinite(test),test,mean)
    a=np.c_[a,~valid];b=np.c_[b,~np.isfinite(test)]
    m=a.mean(axis=0);s=a.std(axis=0);s[s==0]=1
    a=(a-m)/s;b=(b-m)/s;ym=y.mean()
    coef=np.linalg.solve(a.T@a+10*np.eye(a.shape[1]),a.T@(y-ym))
    return ym+b@coef


def ratio(b,s):return (b-s)/(b+s) if b+s else np.nan


def build_features():
    groups=rows(GROUPS);a=group_matrix(groups)
    changes=np.vstack([np.zeros(5,dtype=np.int64),np.cumsum(same_price_changes(a),axis=0)])
    candidates=rows('tasks/family-research-20261022/october18-candidate-inputs.jsonl.gz')
    flow=pd.read_csv(OUT/'dipole-completed-group-flow.csv.gz').set_index('second')
    operator=pd.read_csv(OUT/'dipole-operator-observations.csv.gz',dtype={'decision_ns':str})
    operator=operator[operator.stage.eq('recognition')].set_index('candidate_id')
    records=[]
    for c in candidates:
        ident=c['candidate_id'];j=c['recognition_group'];t=c['recognition_receive_ns']
        k=int(np.searchsorted(a[:,0],t-20*NS,side='right'))-1
        k5=int(np.searchsorted(a[:,0],t-5*NS,side='right'))-1
        end=c['last_closed_second'];op=operator.loc[ident]
        kflow=int(np.searchsorted(a[:,0],(end-19)*NS,side='left'))-1
        valid=min(k,kflow)>=0 and a[k,7] and a[kflow,7] and a[j,7] and a[k,8]==a[kflow,8]==a[j,8]
        r=dict(candidate_id=ident,decision_ns=str(t),source_group=j,source_cursor=int(a[j,1]),
               quote_known_by_ns=str(int(a[j,0])),flow_closed_by_ns=str((end+1)*NS),
               source_start_group=min(k,kflow),input_disposition='available' if valid else 'boundary')
        if valid:
            assert int(a[j,0])==t and (end+1)*NS<=t
            b,s=groups[j]['bid'],groups[j]['ask']
            prior=flow.loc[end-19:end];early=prior.iloc[:10];late=prior.iloc[10:]
            fresh=prior.iloc[-5:]
            eb,es=early.buy.sum(),early.sell.sum();lb,ls=late.buy.sum(),late.sell.sum()
            delta=abs(ratio(lb,ls))-abs(ratio(eb,es))
            d=changes[j+1]-changes[k5+1]
            r.update(prior_ticks20=(a[j,2]-a[k,2])/2e6,
                     range_ticks20=(a[k:j+1,2].max()-a[k:j+1,2].min())/2e6,
                     spread_ticks=(a[j,4]-a[j,3])/1e6,touch_imb=ratio(b[1],s[1]),
                     touch_count_imb=ratio(b[2],s[2]),log_touch_lots=np.log1p(b[1]+s[1]),
                     log_touch_orders=np.log1p(b[2]+s[2]),bid_lots=b[1],ask_lots=s[1],
                     bid_orders=b[2],ask_orders=s[2],early_buy=eb,early_sell=es,late_buy=lb,late_sell=ls,
                     strength_change=delta,early_empty=int(eb+es==0),late_empty=int(lb+ls==0),
                     fresh_buy5=fresh.buy.sum(),fresh_sell5=fresh.sell.sum(),
                     fresh_imb5=ratio(fresh.buy.sum(),fresh.sell.sum()),
                     log_fresh_lots5=np.log1p(fresh.buy.sum()+fresh.sell.sum()),
                     log_unknown_lots5=np.log1p(fresh.unknown.sum()),
                     log_signed_C=np.sign(op.C_signed)*np.log1p(abs(op.C_signed)),
                     **{name:op[name] for name in ('imb_level','imb_flow','ent_dipole','mi_flow')},
                     **dict(zip(LAYERS['display'],map(int,d))))
            r['dipole_state']='both_empty' if eb+es+lb+ls==0 else 'one_half_empty' if not np.isfinite(delta) else 'weakening' if delta<0 else 'strengthening' if delta>0 else 'steady'
            r['book_vs_flow']='undefined_flow' if not np.isfinite(op.imb_level) else 'balanced' if op.imb_level*r['touch_imb']==0 else 'aligned' if op.imb_level*r['touch_imb']>0 else 'opposed'
            r['price_vs_flow']='undefined_flow' if not np.isfinite(op.imb_level) else 'flat_or_balanced' if op.imb_level*r['prior_ticks20']==0 else 'aligned' if op.imb_level*r['prior_ticks20']>0 else 'opposed'
            fj=int(np.searchsorted(a[:,0],t+20*NS,side='right'))-1
            future_valid=t+20*NS<=a[-1,0] and a[fj,7] and a[fj,8]==a[j,8]
            r['future_flow20']=flow.ratio.get((t+20*NS)//NS-1,np.nan) if future_valid else np.nan
            r['flow_strength_change20']=abs(r['future_flow20'])-abs(op.imb_level)
            r['future_target_ns']=str(t+20*NS)
            r['future_flow_bin_closed_by_ns']=str(((t+20*NS)//NS)*NS)
            r['future_disposition']='boundary' if not future_valid else 'no_classified_lots' if not np.isfinite(r['future_flow20']) else 'available'
        records.append(r)
    f=pd.DataFrame(records)
    # Future observations are isolated from predictor output.
    future_columns=['future_flow20','flow_strength_change20','future_target_ns','future_flow_bin_closed_by_ns','future_disposition']
    future=f[['candidate_id',*future_columns]].copy()
    save('stack-flow-outcomes.csv',future)
    f=f.drop(columns=future_columns)
    save('stack-features.csv.gz',f)
    return f,future


def fit_stacks(f,future):
    price=pd.read_csv(HERE/'flow-book-discovery-v1/dipole-after-recognition.csv.gz')
    targets=[]
    for h in (5,20,60):
        p=price[price.horizon_s.eq(h)&price.disposition.eq('available')]
        for target,values in [('midpoint_ticks',p.change/.001),('absolute_ticks',p.change.abs()/.001)]:
            targets.append((target,h,pd.DataFrame(dict(candidate_id=p.candidate_id,y=values))))
    targets.append(('flow_strength_change',20,future[['candidate_id','flow_strength_change20']].rename(columns={'flow_strength_change20':'y'}).dropna()))
    predictions,splits=[],[]
    for target,h,ys in targets:
        x=f[f.input_disposition.eq('available')].merge(ys,on='candidate_id',validate='one_to_one')
        x['time']=x.decision_ns.map(int);x=x.sort_values('time').reset_index(drop=True)
        times=x.time.to_numpy(dtype=np.int64);y=x.y.to_numpy();n=len(x)
        edges=[int(n*q) for q in (.4,.6,.8)]+[n]
        for fold,(lo,hi) in enumerate(zip(edges[:-1],edges[1:])):
            train=np.flatnonzero(times+(h+600)*NS<times[lo]);test=np.arange(lo,hi)
            if len(train)<30:raise ValueError('insufficient training support')
            splits.append(dict(target=target,horizon_s=h,fold=fold,train=len(train),test=len(test),
                               test_start_ns=str(times[lo]),last_train_target_ns=str(times[train[-1]]+h*NS),embargo_s=600))
            for arm,layers in ARMS.items():
                cols=[col for layer in ['context',*layers] for col in LAYERS[layer]]
                matrix=x[cols].to_numpy(dtype=float)
                prediction=ridge_predict(matrix[train],y[train],matrix[test])
                for idx,p in zip(test,prediction):
                    predictions.append(dict(target=target,horizon_s=h,fold=fold,arm=arm,
                        candidate_id=x.iloc[idx].candidate_id,decision_ns=str(times[idx]),target_ns=str(times[idx]+h*NS),
                        actual=y[idx],prediction=p,squared_error=(p-y[idx])**2,absolute_error=abs(p-y[idx]),
                        train_mean=y[train].mean()))
    p=pd.DataFrame(predictions);save('stack-predictions.csv.gz',p);save('stack-splits.csv',splits)
    metrics=[]
    for keys,g in p.groupby(['target','horizon_s','arm']):
        for fold in [-1,0,1,2]:
            v=g if fold==-1 else g[g.fold.eq(fold)]
            end=-1;clusters=0
            for r in v.sort_values('decision_ns').itertuples():
                if int(r.decision_ns)>end:clusters+=1
                end=max(end,int(r.target_ns))
            metrics.append(dict(zip(['target','horizon_s','arm'],keys),fold=fold,n=len(v),
                                interval_clusters=clusters,mse=v.squared_error.mean(),mae=v.absolute_error.mean(),
                                null_mse=((v.actual-v.train_mean)**2).mean()))
    m=pd.DataFrame(metrics)
    baseline=m[m.arm.eq('baseline')][['target','horizon_s','fold','mse']].rename(columns={'mse':'baseline_mse'})
    m=m.merge(baseline,on=['target','horizon_s','fold'],validate='many_to_one')
    m['mse_ratio_to_baseline']=m.mse/m.baseline_mse
    save('stack-metrics.csv',m)
    deltas=[]
    for keys,g in m.groupby(['target','horizon_s','fold']):
        table=g.set_index('arm')
        for layer in ('dipole','fresh','book','display'):
            without=table.loc['without_'+layer,'mse'];full=table.loc['full','mse']
            deltas.append(dict(zip(['target','horizon_s','fold'],keys),layer=layer,
                              improvement_from_adding_layer=without-full,
                              fraction_of_without_mse=(without-full)/without if without else np.nan))
    save('stack-layer-contributions.csv',deltas)
    return price,m


def conditional_tables(f,future,price):
    joined=f.merge(price[price.horizon_s.isin([5,20,60])],on='candidate_id',validate='one_to_many')
    joined=joined.merge(future,on='candidate_id',validate='many_to_one')
    records=[]
    for keys,g in joined.groupby(['dipole_state','book_vs_flow','horizon_s'],dropna=False):
        v=g[g.disposition.eq('available')]
        direction=v.change*np.sign(v.imb_level)
        records.append(dict(zip(['dipole_state','book_vs_flow','horizon_s'],keys),n=len(g),available=len(v),
            up=int((v.change>0).sum()),down=int((v.change<0).sum()),flat=int((v.change==0).sum()),
            follows_current_flow=int((direction>0).sum()),opposes_current_flow=int((direction<0).sum()),
            current_flow_undefined=int(v.imb_level.isna().sum()),current_flow_balanced=int(v.imb_level.eq(0).sum()),
            median_abs_ticks=v.change.abs().median()/.001,
            future_flow_defined=int(g.future_flow20.notna().sum()),
            future_flow_weaker=int((g.flow_strength_change20<0).sum()),
            future_flow_stronger=int((g.flow_strength_change20>0).sum()),
            future_flow_same_strength=int(g.flow_strength_change20.eq(0).sum())))
    save('stack-conditional-states.csv',records)
    cols=[c for layer in LAYERS.values() for c in layer]
    corr=f[cols].corr(method='spearman',min_periods=30)
    records=[]
    for i,left in enumerate(cols):
        for right in cols[i+1:]:
            records.append(dict(left=left,right=right,defined_pairs=int(f[[left,right]].notna().all(axis=1).sum()),rho=corr.loc[left,right]))
    save('stack-feature-redundancy.csv',records)
    examples=f.sort_values('decision_ns').groupby(['dipole_state','book_vs_flow'],dropna=False).head(1)
    save('stack-state-examples.csv',examples.merge(price[price.horizon_s.eq(20)],on='candidate_id'))


def main():
    f,future=build_features();price,metrics=fit_stacks(f,future);conditional_tables(f,future,price)
    dump('stack-method.json',dict(source_revision=REV,source_groups=GROUPS,layers=LAYERS,arms=ARMS,
         targets=['midpoint ticks and absolute ticks at 5/20/60 seconds','absolute flow-strength change at 20 seconds, both ratios defined'],
         trials=dict(arms=len(ARMS),target_horizon_pairs=7,chronological_folds=3),
         fit='Ridge alpha 10; train-only mean imputation, missingness flags and scaling. Expanding 40/60/80 percent cuts; label purge plus 600-second embargo. Same eligible rows in every arm within target/fold; no search for hyperparameters.',
         interpretation='Compare added layers and full-stack ablations; complementary stories do not automatically imply additional predictive value.',
         limits=['One selected October 18 discovery cohort; other three days pending comparable final inputs.',
                 'Repeated/overlapping observations; interval clusters reported, no iid significance or calibrated probabilities.',
                 'Same-price displayed additions/removals are aggregate changes, not proven same-order replenishment or executed absorption.',
                 'Fresh and dipole features share trade observations; redundancy correlations and ablations retain this.',
                 'Flow-strength target excludes undefined endpoint/start ratios; report empty flow separately.',
                 'No future family, birth polarity, final duration, identity, timestamp or source cursor is a predictor.',
                 'Price response is a separate target; no universal law or execution rule is admitted.']))
    print(metrics[metrics.fold.eq(-1)].pivot(index=['target','horizon_s'],columns='arm',values='mse_ratio_to_baseline').round(3).to_string())


if __name__=='__main__':main()
