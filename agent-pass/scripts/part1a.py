"""Part 1A. Per-path unscaled observations, complete heat strips, matched controls."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import argparse
plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False})
FIELDS=['bid','ask','bid_size','ask_size']+[a+'_'+s for a in ['add','cancel','fill','modify','trade'] for s in ['B','A']]+['ratio']

def prepare(day):
    G=groups(day); R=raw(day); F=flow(day)
    flow_index=F.set_index('second')
    gr=G.receive_ns.to_numpy(); rt=R.receive_ns.to_numpy()
    # Action volumes use containing completed group, avoiding half-applied groups.
    gi=np.searchsorted(G.cursor.to_numpy(),R.cursor.to_numpy(),side='left')
    R['group_ns']=gr[gi]
    streams={}
    for name,act in [('add','A'),('cancel','C'),('fill','F'),('modify','M'),('trade','T')]:
        for side in ['B','A']:
            m=(R.action==act)&(R.side==side)
            streams[name+'_'+side]=(R.loc[m,'group_ns'].to_numpy(),np.r_[0,np.cumsum(R.loc[m,'size'].to_numpy(dtype=np.int64))])
    def sample(cuts,lo=None):
        ix=np.searchsorted(gr,cuts,side='right')-1
        assert np.all(ix>=0)
        out=G.iloc[ix][['cursor','good','bid_raw','ask_raw','bid_size','ask_size']].reset_index(drop=True)
        out['bid']=out.pop('bid_raw')/S;out['ask']=out.pop('ask_raw')/S
        out['quote_age_s']=(cuts-gr[ix])/S
        for k,(t,cum) in streams.items():
            lower=cuts-S if lo is None else lo
            out[k]=cum[np.searchsorted(t,cuts,side='right')]-cum[np.searchsorted(t,lower,side='right')]
        sec=cuts//S-1 # only fully closed seconds, no future within-second information
        fi=flow_index.reindex(sec)
        out['ratio']=fi.ratio.to_numpy();out['classified_lots_20']=fi.total.to_numpy()
        return out
    return G,R,F,sample

def run(day):
    C,source=candidates(day);G,R,F,sample=prepare(day)
    gr=G.receive_ns.to_numpy(); start=(gr[0]//S+61)*S;end=(gr[-1]//S-200)*S
    grid=np.arange(start,end,S,dtype=np.int64)-1
    P=sample(grid);P['anchor_ns']=grid+1
    t=G.receive_ns.to_numpy();cum=np.r_[0,np.cumsum(G.prints.to_numpy())]
    def activity(cuts):return cum[np.searchsorted(t,cuts,side='right')]-cum[np.searchsorted(t,cuts-60*S,side='right')]
    P['activity']=activity(grid)
    P['regime']=np.round((P.ask-P.bid)*1000).astype('Int64')
    P=P[P.good & (P.regime>0) & (P.quote_age_s<60)].copy()
    P['regime']=P.regime.clip(upper=3)
    # No sampled control anchor in a candidate's requested event window.
    blocked=np.zeros(len(P),bool)
    for r in C.itertuples():
        if pd.notna(r.recognition_ns):blocked|=(P.anchor_ns.to_numpy()>=r.birth_second*S-60*S)&(P.anchor_ns.to_numpy()<=r.recognition_ns)
    P['blocked']=blocked
    P['activity_bucket']=-1;edges={}
    for reg,x in P.groupby('regime'):
        edges[reg]=np.quantile(x.activity,[.2,.4,.6,.8]);P.loc[x.index,'activity_bucket']=np.searchsorted(edges[reg],x.activity,side='right')
    paths=[];meta=[];rng=np.random.default_rng(1401);reasons=[]
    for i,c in C.iterrows():
        if pd.isna(c.recognition_ns):reasons.append(dict(candidate_id=c.candidate_id,reason='finalization_only_no_live_recognition'));continue
        birth=int(c.birth_second)*S;rec=int(c.recognition_ns);lag=(rec-birth)/S
        if birth-61*S<gr[0] or rec>gr[-1]:reasons.append(dict(candidate_id=c.candidate_id,reason='source_boundary'));continue
        pre=sample(np.array([birth-1])).iloc[0]
        reg=min(3,round((pre.ask-pre.bid)*1000));act=activity(np.array([birth-1]))[0]
        bucket=np.searchsorted(edges.get(reg,[]),act,side='right')
        pool=P[(P.regime==reg)&(P.activity_bucket==bucket)&(~P.blocked)]
        anchors=[('candidate',birth)]
        if len(pool):
            picks=rng.choice(pool.anchor_ns.to_numpy(),size=2,replace=len(pool)<2)
            anchors += [(f'control{k+1}',int(v)) for k,v in enumerate(picks)]
        else:reasons.append(dict(candidate_id=c.candidate_id,reason='no_matching_control_pool'))
        for kind,anchor in anchors:
            offsets=np.r_[np.arange(-60,int(np.floor(lag))+1,dtype=np.int64)*S,int(rec-birth)]
            offsets=np.unique(offsets);cuts=anchor+offsets
            # t=0 denotes strict prebirth, the exact recognition endpoint is retained.
            cuts[offsets<=0]-=1
            x=sample(cuts,lo=np.r_[cuts[0]-S,cuts[:-1]])
            x['candidate_id']=c.candidate_id;x['kind']=kind;x['relative_s']=offsets/S;x['cut_ns']=cuts
            x['orientation']=c.orientation;x['original_coverage']=c.original_coverage
            paths.append(x)
            m=c.to_dict();m.update(kind=kind,anchor_ns=anchor,lag_s=lag,regime=reg,activity_bucket=bucket,activity=act,control_pool_n=len(pool),path_rows=len(x))
            m['mid_change_ticks']=((x.bid.iloc[-1]+x.ask.iloc[-1])-(pre.bid+pre.ask))*500 if kind=='candidate' else ((x.bid.iloc[-1]+x.ask.iloc[-1])-(x.loc[x.relative_s==0,'bid'].iloc[0]+x.loc[x.relative_s==0,'ask'].iloc[0]))*500
            m['move_orientation']='in' if m['mid_change_ticks']*c.polarity>1e-8 else 'against' if m['mid_change_ticks']*c.polarity < -1e-8 else 'flat'
            meta.append(m)
    X=pd.concat(paths,ignore_index=True);M=pd.DataFrame(meta)
    save(C,f'{day}-candidate-operands.csv');save(M,f'{day}-path-members.csv');save(X,f'{day}-paths.csv.gz');save(pd.DataFrame(reasons,columns=['candidate_id','reason']),f'{day}-path-dispositions.csv')
    # Exact per-row matrix; no interpolation/rescaling/row averaging. Final fractional endpoint separately plotted.
    reconc=[]
    for kind in M.kind.unique():
      for ori in C.orientation.unique():
        q=X[(X.kind==kind)&(X.orientation==ori)]
        if day=='20231018': q=q[q.original_coverage!='none']
        if not len(q):continue
        for panel,fields in [('quotes',FIELDS[:4]),('actions',FIELDS[4:14]),('flow',['ratio'])]:
            fig,axes=plt.subplots(len(fields),1,figsize=(12, max(3,2.5*len(fields))),squeeze=False)
            for ax,col in zip(axes.flat,fields):
                integral=q[np.isclose(q.relative_s%1,0,atol=1e-9)]
                mat=integral.pivot(index='candidate_id',columns='relative_s',values=col)
                expected=len(q); plotted=int(np.isfinite(mat.to_numpy()).sum());fraction=q[~q.index.isin(integral.index)]
                missing=int(q[col].isna().sum());endpoints=int(fraction[col].notna().sum())
                assert expected==plotted+endpoints+missing
                im=ax.imshow(mat.to_numpy(),aspect='auto',interpolation='nearest',extent=[mat.columns.min()-.5,mat.columns.max()+.5,len(mat),0],cmap='coolwarm' if col=='ratio' else 'viridis')
                ax.axvline(0,color='white',lw=.5);ax.set_ylabel('candidate row');ax.set_title(f'{col}: rows in {expected}; heat cells {plotted}; exact endpoints {endpoints}; undefined {missing}',loc='left');fig.colorbar(im,ax=ax,pad=.01)
                reconc.append(dict(figure=f'{day}-{kind}-{ori}-{panel}.png',panel=col,rows_in=expected,points_plotted=plotted,endpoint_points_in_companion=endpoints,rows_excluded=missing,reason='undefined classified ratio or missing quote',candidate_rows=len(mat)))
            axes[-1,0].set_xlabel('seconds from birth; white is unobserved/after recognition')
            fig.suptitle(f'{day} {kind} {ori}: raw levels and lots; 852 subset on Oct 18',fontsize=10);fig.tight_layout();fig.savefig(ROOT/'figures'/f'{day}-{kind}-{ori}-{panel}.png',dpi=130);plt.close(fig)
        frac=q[~np.isclose(q.relative_s%1,0,atol=1e-9)]
        fig,axes=plt.subplots(5,3,figsize=(13,12))
        for ax,col in zip(axes.flat,FIELDS):
            ok=frac[col].notna();ax.scatter(np.arange(len(frac))[ok],frac.loc[ok,col],s=3);ax.set_title(f'{col}: in {len(frac)}, points {ok.sum()}, undefined {(~ok).sum()}')
            reconc.append(dict(figure=f'{day}-{kind}-{ori}-endpoints.png',panel=col,rows_in=len(frac),points_plotted=int(ok.sum()),endpoint_points_in_companion=0,rows_excluded=int((~ok).sum()),reason='undefined classified ratio or missing quote',candidate_rows=len(frac)))
        fig.tight_layout();fig.savefig(ROOT/'figures'/f'{day}-{kind}-{ori}-endpoints.png',dpi=110);plt.close(fig)
    save(pd.DataFrame(reconc),f'{day}-figure-reconciliation.csv')
    # One raw-record trace per SAME/FLIP x observed alternative quote direction, for candidate and both paired controls.
    cases=[];traces=[]
    for (ori,move),sub in M[M.kind=='candidate'].groupby(['orientation','move_orientation']):
        chosen=sub.sort_values('birth_second').iloc[0];ident=chosen.candidate_id
        for m in M[M.candidate_id==ident].itertuples():
            cut0=int(m.anchor_ns-60*S);cut1=int(m.anchor_ns+round(m.lag_s*S))
            z=R[(R.receive_ns>=cut0)&(R.receive_ns<=cut1)].copy();z['case_id']=ident;z['case_kind']=m.kind;traces.append(z)
            cases.append(dict(candidate_id=ident,kind=m.kind,orientation=ori,move=move,records=len(z),first_cursor=z.cursor.iloc[0] if len(z) else None,last_cursor=z.cursor.iloc[-1] if len(z) else None))
    save(pd.DataFrame(cases),f'{day}-cases.csv');save(pd.concat(traces),f'{day}-case-raw-records.csv.gz')
    receipt=dict(day=day,candidates=len(C),live=int(C.recognition_ns.notna().sum()),path_candidates=int((M.kind=='candidate').sum()),path_rows=len(X),groups=len(G),raw_records=len(R),matched_controls=int((M.kind!='candidate').sum()),distinct_control_anchors=int(M[M.kind!='candidate'].anchor_ns.nunique()),original_coverage=C.original_coverage.value_counts().to_dict(),figures=len(set(r['figure'] for r in reconc)))
    (ROOT/f'{day}-part1a-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
if __name__=='__main__':run(argparse.ArgumentParser().parse_known_args()[1][0])
