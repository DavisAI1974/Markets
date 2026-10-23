"""Offline instance records and one exact book replay; no fitting or signal selection."""
import csv,gzip,io,json,pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/sqlite-triage/20261022/families'
SRC=BASE/'final-model-analysis-20261023/source'
OUT=BASE/'instance-market-review-20261023'
OUT.mkdir(exist_ok=True)
CASE=375
MODELS=['ridge100','evotrees_depth3','evotrees_depth5','evotrees_mae','neural_tree','residual_mlp','tabm_ensemble','evotrees_q10','evotrees_q90']
LABELS={'ridge100':'Linear ridge','evotrees_depth3':'Shallow trees','evotrees_depth5':'Deeper trees','evotrees_mae':'Median-loss trees','neural_tree':'NeuralTree','residual_mlp':'Residual MLP','tabm_ensemble':'TabM','evotrees_q10':'Lower quantile','evotrees_q90':'Upper quantile'}

def writejson(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def records(frame):return json.loads(frame.to_json(orient='records',double_precision=15))

def timestamp(ns):return pd.Timestamp(int(ns),unit='ns',tz='UTC').isoformat()

def select_rows(path,predicate):
    rows=[]
    for c in pd.read_csv(path,chunksize=100000,dtype=str,keep_default_na=False):
        rows.append(c.loc[predicate(c)].copy())
    return pd.concat(rows,ignore_index=True)

families=pd.read_csv(BASE/'descriptive-v1/family_master.csv').sort_values(['start_recv_ns','input_cursor']).reset_index(drop=True)
assert len(families)==749 and families.family_id.is_unique
families['instance']=np.arange(1,750)
master=pd.read_csv(SRC/'model_sample_master.csv')
pre=master[master.phase=='before_start'].copy()
assert len(pre)==749 and pre.family_id.is_unique
index=families.merge(pre[['sample_id','family_id','cutoff_ns','cursor_cap','chronological_quarter','price','price_age_s','pre120_change','pre_direction']],on='family_id',validate='one_to_one')
assert (index.cutoff_ns==index.start_recv_ns-1).all()
assert (index.cursor_cap==index.input_cursor-1).all()
index['start_utc']=index.start_recv_ns.map(timestamp)

# Preserve raw missing/disposition fields. Whitelist the exported contemporaneous
# measurements rather than admitting later episode outcomes as predictors.
feature_files=['descriptive-v1/features.csv.gz','descriptive-v1/group_measurements.csv.gz','enriched-v2/native_measurements.csv.gz']
feature_frames=[]
for filename in feature_files:
    f=select_rows(BASE/filename,lambda c:c.sample_id.str.endswith(':before_start'))
    f=f[f.feature.str.startswith(('root.','native.','second.','second_group.'))].copy()
    f['measurement_file']=filename
    feature_frames.append(f)
features=pd.concat(feature_frames,ignore_index=True)
assert not features.duplicated(['sample_id','feature','measurement_file']).any()
features.to_csv(OUT/'pre-event-measurements.csv.gz',index=False,compression={'method':'gzip','mtime':0})

chosen=['root.best_bid','root.best_ask','root.mid','root.spread','root.depth_imbalance_n','root.depth_imbalance_full','root.bid_depth_full','root.ask_depth_full']
for h in [1,5,20,60,300]:
    chosen.extend(f'root.activity.{h}.{suffix}' for suffix in ['trade_buy_aggressor_qty','trade_sell_aggressor_qty','trade_aggressor_imbalance','event_count','top_level_cancel_qty_derived'])
wide=features[features.feature.isin(chosen)].copy()
assert not wide.duplicated(['sample_id','feature']).any()
wide['value']=pd.to_numeric(wide.value,errors='coerce')
wide=wide.pivot(index='sample_id',columns='feature',values='value').reset_index()
index=index.merge(wide,on='sample_id',how='left',validate='one_to_one')

ctx=select_rows(BASE/'descriptive-v1/group_context_receipts.csv.gz',lambda c:(c.lag_s=='0')&c.sample_id.str.endswith(':before_start'))
for col in ['cutoff_ns','known_by_ns','input_cursor','source_ordinal']:
    ctx[col]=ctx[col].map(int)
assert len(ctx)==749
joined=ctx.merge(pre[['sample_id','cutoff_ns','cursor_cap']],on='sample_id',suffixes=('_receipt','_master'),validate='one_to_one')
assert (joined.cutoff_ns_receipt==joined.cutoff_ns_master).all()
assert (joined.known_by_ns<=joined.cutoff_ns_master).all()
assert (joined.input_cursor<=joined.cursor_cap).all()
ctx.to_csv(OUT/'pre-event-clock-receipts.csv',index=False)
index=index.merge(ctx[['sample_id','source_ordinal','known_by_ns','input_cursor','age_s']].rename(columns={'source_ordinal':'pre_source_ordinal','input_cursor':'pre_input_cursor','age_s':'pre_book_age_s'}),on='sample_id',validate='one_to_one')

# Every recorded pre-event forecast/refit is retained. No success-based filtering.
predframes=[]
for name,total in [('model_predictions.csv',1181946),('neural_predictions.csv',118203)]:
    n=0
    for c in pd.read_csv(SRC/name,chunksize=100000):
        n+=len(c);predframes.append(c[c.phase=='before_start'].copy())
    assert n==total
pred=pd.concat(predframes,ignore_index=True)
keys=['sample_id','outcome','horizon_s','fold','model']
assert not pred.duplicated(keys).any()
assert pred.groupby(keys[:-1])['observed'].nunique().max()==1
pred=pred.merge(index[['sample_id','instance','cutoff_ns','cursor_cap']],on='sample_id',validate='many_to_one')
pred.sort_values(['instance','outcome','horizon_s','model'],inplace=True)
pred.to_csv(OUT/'all-pre-event-forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0})
counts=pred.groupby('sample_id').size().rename('recorded_forecast_rows')
index=index.merge(counts,on='sample_id',how='left')
index.recorded_forecast_rows=index.recorded_forecast_rows.fillna(0).astype(int)
index['forecast_disposition']=np.where(index.recorded_forecast_rows>0,'recorded_heldout_forecasts','no_saved_heldout_forecasts_for_this_sample')
index['continuous_book_replay']=np.where(index.instance==CASE,'dedicated_minus120_plus600_second_window','no_dedicated_full_window_some_events_overlap_instance375_window')
index.to_csv(OUT/'chronological-instance-index.csv',index=False)

# A hypothesis formed while inspecting375, not a preregistered trading signal.
# The screen uses only recorded pre-event conditions, never future outcomes.
requirements=['root.activity.60.trade_buy_aggressor_qty','root.activity.60.trade_sell_aggressor_qty',
              'root.activity.5.trade_buy_aggressor_qty','root.activity.5.trade_sell_aggressor_qty',
              'root.activity.1.trade_buy_aggressor_qty','root.activity.1.trade_sell_aggressor_qty',
              'root.bid_depth_full','root.ask_depth_full']
known=index[requirements].notna().all(axis=1)
match=(index[requirements[0]]>index[requirements[1]])&(index[requirements[2]]<index[requirements[3]])&(index[requirements[4]]<index[requirements[5]])&(index[requirements[6]]>index[requirements[7]])
candidate=index.copy();candidate['candidate_status']='not_matched'
candidate.loc[~known,'candidate_status']='unknown_missing_measurement'
candidate.loc[known&match,'candidate_status']='matched'
candidate.to_csv(OUT/'candidate-flow-transition-audit.csv',index=False)
matched=candidate[candidate.candidate_status=='matched']
matched.to_csv(OUT/'candidate-flow-transition-instances.csv',index=False)
nextcase=int(matched.loc[matched.instance>CASE,'instance'].iloc[0])
assert nextcase==391
pred[pred.instance==nextcase].to_csv(OUT/'instance-391-all-model-forecasts.csv',index=False)

main=pred[pred.model.isin(MODELS)]
feature_by={sid:records(g) for sid,g in features.groupby('sample_id')}
main_by={sid:records(g.drop(columns=['cutoff_ns','cursor_cap'])) for sid,g in main.groupby('sample_id')}
with gzip.open(OUT/'individual-instance-records.jsonl.gz','wt',encoding='utf-8') as h:
    for r in index.itertuples():
        # Keep nanosecond identifiers as Python integers; pandas JSON float
        # conversion must never be used for these decision clocks.
        card=dict(instance=int(r.instance),family_id=r.family_id,sample_id=r.sample_id,instrument_id=int(r.instrument_id),
                  start_receive_ns=int(r.start_recv_ns),start_event_ns=int(r.start_event_ns),decision_cutoff_ns=int(r.cutoff_ns),cursor_cap=int(r.cursor_cap),
                  start_utc=r.start_utc,pre_source_ordinal=int(r.pre_source_ordinal),pre_known_by_ns=int(r.known_by_ns),pre_input_cursor=int(r.pre_input_cursor),
                  forecast_disposition=r.forecast_disposition,continuous_book_replay=r.continuous_book_replay,
                  measurements=feature_by.get(r.sample_id,[]),forecasts=main_by.get(r.sample_id,[]))
        h.write(json.dumps(card,allow_nan=False)+'\n')
print('All749individual records and exact pre-event clock checks saved',flush=True)

r=index.iloc[CASE-1];fid=r.family_id;sid=r.sample_id;t=int(r.start_recv_ns);cap=int(r.cursor_cap)
q=pd.read_csv(BASE/'timestamped-mbo-window-v1/consecutive_quote_books.csv.gz')
assert len(q)==22194 and q.family_id.eq(fid).all()
assert q.known_by_ns.is_monotonic_increasing
assert q.input_cursor.is_monotonic_increasing
assert (q.known_by_ns==q.receive_ns).all()
before=q[(q.known_by_ns<=t-1)&(q.input_cursor<=cap)].iloc[-1]
assert int(before.source_ordinal)==int(r.pre_source_ordinal)
assert int(before.known_by_ns)==int(r.known_by_ns)
assert abs(before.mid-r['root.mid'])<1e-12

checkpoints=[]
targets=[(-120,'window_start'),(-60,'pre60s'),(-30,'pre30s'),(-5,'pre5s'),(-1,'pre1s'),(-.061,'pre61ms'),(-.005,'pre5ms'),(0,'strict_before'),(0,'event_group'),(.001,'post1ms'),(.05,'post50ms'),(.1,'post100ms'),(.5,'post500ms'),(1,'post1s'),(5,'post5s'),(20,'post20s'),(60,'post60s'),(120,'post120s'),(300,'post300s'),(600,'post600s')]
for sec,label in targets:
    cutoff=t+round(sec*10**9)-(1 if label=='strict_before' else 0)
    cc=cap if label=='strict_before' else int(r.input_cursor) if label=='event_group' else np.iinfo('int64').max
    a=q[(q.known_by_ns<=cutoff)&(q.input_cursor<=cc)]
    if not len(a):checkpoints.append(dict(checkpoint=label,target_relative_s=sec,cutoff_ns=cutoff,disposition='no_preceding_row_inside_saved_window'));continue
    row=a.iloc[-1]
    item={k:int(row[k]) for k in ['source_ordinal','input_cursor','event_ns','receive_ns','known_by_ns']}
    item.update({k:float(row[k]) for k in ['best_bid','best_ask','mid','spread','bid_depth_n','ask_depth_n','bid_depth_full','ask_depth_full']})
    item.update(checkpoint=label,target_relative_s=sec,cutoff_ns=cutoff,relative_observation_s=(int(row.known_by_ns)-t)/1e9,age_s=(cutoff-int(row.known_by_ns))/1e9,mid_change_from_strict_pre=float(row.mid-before.mid),disposition='actual_completed_group_asof_not_interpolated')
    checkpoints.append(item)
checkpoints=pd.DataFrame(checkpoints,dtype=object)
checkpoints.to_csv(OUT/'instance-375-checkpoints.csv',index=False)
# q includes no missing clocks. Validate every saved outcome within this export.
casepred=pred[pred.sample_id==sid]
casepred.to_csv(OUT/'instance-375-all-model-forecasts.csv',index=False)
checkn=0
for h,g in casepred[casepred.outcome=='mid_price_change'].groupby('horizon_s'):
    if h>600:continue
    endpoint=q[q.known_by_ns<=t+int(h)*10**9].iloc[-1]
    assert (t+int(h)*10**9-int(endpoint.known_by_ns))/1e9<=5
    assert np.allclose(g.observed,endpoint.mid-before.mid,rtol=0,atol=1e-12)
    checkn+=1
assert checkn==7
features[features.sample_id==sid].to_csv(OUT/'instance-375-pre-event-measurements.csv',index=False)

# Exact absolute-price ladders at bounded checkpoints. Stream saved compressed
# parts once; never equate a level rank with a surviving order identity.
class Parts(io.RawIOBase):
    def __init__(self,paths):self.paths=iter(paths);self.current=None
    def readable(self):return True
    def readinto(self,b):
        while True:
            if self.current is None:
                try:self.current=next(self.paths).open('rb')
                except StopIteration:return 0
            n=self.current.readinto(b)
            if n:return n
            self.current.close();self.current=None
    def close(self):
        if self.current is not None:self.current.close()
        super().close()

wanted=set(checkpoints.source_ordinal.dropna().astype('int64'))
parts=sorted((BASE/'timestamped-mbo-window-v1').glob('consecutive_bid_ask_levels.csv.gz.part*'))
assert len(parts)==4
level_frames=[];leveln=0
with io.BufferedReader(Parts(parts)) as stream,gzip.GzipFile(fileobj=stream) as gz:
    for c in pd.read_csv(gz,chunksize=200000):
        leveln+=len(c);level_frames.append(c[c.source_ordinal.isin(wanted)].copy())
assert leveln==10267320
levels=pd.concat(level_frames,ignore_index=True)
assert not levels.duplicated(['source_ordinal','side','rank']).any()
for ordinal,g in levels.groupby('source_ordinal'):
    qr=q[q.source_ordinal==ordinal].iloc[0]
    for side,col in [('B','bid_depth_full'),('A','ask_depth_full')]:
        assert g[g.side==side]['size'].sum()==qr[col]
        assert g[(g.side==side)&(g['rank']<=10)]['size'].sum()==qr['bid_depth_n' if side=='B' else 'ask_depth_n']
    assert g[(g.side=='B')&(g['rank']==1)].price.iloc[0]==qr.best_bid
    assert g[(g.side=='A')&(g['rank']==1)].price.iloc[0]==qr.best_ask
levels.to_csv(OUT/'instance-375-checkpoint-ladders.csv.gz',index=False,compression={'method':'gzip','mtime':0})
print('Exact checkpoint ladders reconciled against full bid/ask size and touches',flush=True)

# Contemporary source components and external publications remain separately
# available; no terminal lifecycle knowledge is injected into the decision row.
external=select_rows(BASE/'descriptive-v1/external_asof.csv.gz',lambda c:c.sample_id==sid)
pub=external[external.published_ns!=''].published_ns.map(int)
assert (pub<=t-1).all()
external.to_csv(OUT/'instance-375-external-asof.csv',index=False)
sequence=select_rows(BASE/'descriptive-v1/retained_group_sequence.csv.gz',lambda c:c.family_id==fid)
sequence.to_csv(OUT/'instance-375-family-occurrences.csv',index=False)
assert len(sequence)==int(r.occurrence_count)
firsts=families[(families.instrument_id==r.instrument_id)&families.start_recv_ns.between(t-120*10**9,t+600*10**9)].copy()
firsts['relative_start_s']=(firsts.start_recv_ns-t)/1e9
firsts.to_csv(OUT/'instance-375-neighboring-first-events.csv',index=False)

flow=[]
for h in [1,5,20,60,300]:
    buy=r[f'root.activity.{h}.trade_buy_aggressor_qty'];sell=r[f'root.activity.{h}.trade_sell_aggressor_qty']
    flow.append(dict(window_s=h,buy_aggressor_qty=float(buy),sell_aggressor_qty=float(sell),imbalance=float(r[f'root.activity.{h}.trade_aggressor_imbalance'])))
pd.DataFrame(flow).to_csv(OUT/'instance-375-pre-event-flow.csv',index=False)

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(4,1,figsize=(12,14),constrained_layout=True)
x=(q.known_by_ns-t)/1e9
for ax,lo,hi,title in [(axes[0],-120,600,'Actual observed book path around this one family event'),(axes[1],-1.6,1,'Close-up: price was already falling before the family appeared')]:
    take=x.between(lo,hi)
    ax.plot(x[take],q.loc[take,'best_bid'],lw=.8,label='Bid',drawstyle='steps-post');ax.plot(x[take],q.loc[take,'best_ask'],lw=.8,label='Ask',drawstyle='steps-post')
    ax.plot(x[take],q.loc[take,'mid'],lw=1,color='black',label='Midquote',drawstyle='steps-post')
    ax.axvline(0,color='crimson',ls='--',label='First observed family');ax.set_title(title,loc='left');ax.set_ylabel('Price');ax.set_xlabel('Seconds relative to first observation');ax.grid(alpha=.2);ax.legend(ncol=4,fontsize=8)
ax=axes[2]
near=(q.bid_depth_n-q.ask_depth_n)/(q.bid_depth_n+q.ask_depth_n)
full=(q.bid_depth_full-q.ask_depth_full)/(q.bid_depth_full+q.ask_depth_full)
take=x.between(-5,20)
ax.plot(x[take],near[take],label='Near-depth summary (depth_n)',drawstyle='steps-post');ax.plot(x[take],full[take],label='Full-book imbalance',drawstyle='steps-post')
ax.axhline(0,color='grey',lw=.7);ax.axvline(0,color='crimson',ls='--');ax.set_title('The larger full bid book coexisted with a different local depth balance',loc='left');ax.set_xlabel('Seconds relative to first observation');ax.set_ylabel('(Bid size - ask size) / total');ax.legend(fontsize=9);ax.grid(alpha=.2)
ax=axes[3]
signed=casepred[(casepred.outcome=='mid_price_change')&casepred.model.isin(MODELS[:7])&casepred.horizon_s.le(600)]
for model,g in signed.groupby('model'):
    g=g.sort_values('horizon_s');ax.plot(g.horizon_s,g.prediction,marker='o',ms=3,label=LABELS[model])
truth=signed.groupby('horizon_s')['observed'].first().sort_index();ax.plot(truth.index,truth.values,color='black',ls='--',lw=2,marker='x',label='Actual endpoint change')
ax.axhline(0,color='grey',lw=.7);ax.set_xscale('log');ax.set_xlabel('Forecast horizon in seconds');ax.set_ylabel('Change from strict pre-event mid');ax.set_title('Frozen pre-event forecasts for this instance, not averages',loc='left');ax.legend(ncol=4,fontsize=8);ax.grid(alpha=.2)
fig.suptitle('Instance 375 | '+fid+' | '+timestamp(t)+'\nSteps connect observed completed-group states; no intra-group replay or simulated fills',fontsize=13)
fig.savefig(OUT/'instance-375-market-replay.png',dpi=150);plt.close(fig)

receipt=dict(status='individual_event_review_saved',instances=749,pre_clock_checks=749,instances_with_heldout_forecasts=int((index.recorded_forecast_rows>0).sum()),
             recorded_pre_event_forecasts=len(pred),per_instance_main_and_quantile_rows=len(main),measurement_rows=len(features),
             candidate_screen=dict(formed_during_review_of=375,matched_instances=len(matched),next_chronological_match=nextcase,
                                   use='Case-finding only, not independently validated or selected on future returns',definition='60s buy>sell;5s sell>buy;1s sell>buy;full bid size>full ask size'),
             case=dict(instance=375,family_id=fid,start_receive_ns=t,start_utc=timestamp(t),sample_id=sid,decision_cutoff_ns=t-1,cursor_cap=cap,
                       strict_pre_source_ordinal=int(before.source_ordinal),strict_pre_known_by_ns=int(before.known_by_ns),strict_pre_age_s=(t-1-int(before.known_by_ns))/1e9,
                       observed_book_rows=len(q),level_rows_streamed=leveln,checkpoint_level_rows=len(levels),checkpoint_ladders=len(wanted),
                       matched_forecast_horizons=checkn,recorded_family_occurrences=len(sequence),neighboring_first_events=len(firsts),external_rows=len(external),
                       same_instrument_future_endpoints='Matched saved signed outcomes within1e-12 at1,5,20,60,120,300,600s'),
             selection='Original chronological middle family, chosen before outcomes. All749instance index in chronological order; no outcome filtering.',
             limits=['First-observed structural family, not a filled trade or proven cause.','Only instance375 has a dedicated local consecutive book window; nearby instances can overlap that window with partial coverage.',
                     'Checkpoint ladders summarize observed queue fields; they do not identify individual FIFO order survival.','depth_n matches top10level sums at all18checked checkpoint ladders; producer name retained elsewhere.',
                     'Rolling activity windows overlap. Their counts are not independent evidence.','One day, semantic coverage NOT_PASSED, neural repeatability/domain caveats unchanged.'],
             operations='Read local saved projections only. No AWS call, EC2 start, raw/database rehash, new fit, trade, ensemble or production change.')
writejson('instance-review-receipt.json',receipt)
print(json.dumps(receipt),flush=True)
