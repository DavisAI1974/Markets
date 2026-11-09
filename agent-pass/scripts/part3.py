"""Part 3 M1/M2. SPECULATIVE operational event definitions; every event retained."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':8})

def run(day):
    G=groups(day);R=raw(day);C,_=candidates(day)
    M=pd.read_csv(ROOT/f'tables/{day}-path-members.csv',dtype={'anchor_ns':'int64','recognition_ns':'Int64'})
    t=G.receive_ns.to_numpy();cursor=G.cursor.to_numpy();n=len(G);events=[];streams={}
    gi=np.searchsorted(cursor,R.cursor.to_numpy(),side='left');action_matrix={}
    for action in ['A','C','F','M','T']:
      for side in ['B','A']:
        mask=((R.action==action)&(R.side==side)).to_numpy();v=np.bincount(gi[mask],weights=R.loc[mask,'size'],minlength=n);key=f'{action}_{side}';action_matrix[key]=v
        ii=np.flatnonzero(v>0);streams[key]=(t[ii],cursor[ii],v[ii])
    for name,cols in [('quote_relocation',['bid_raw','ask_raw']),('touch_size_change',['bid_size','ask_size'])]:
        values=G[cols].to_numpy();change=np.r_[False,np.any(np.diff(values,axis=0)!=0,axis=1)]&G.good.to_numpy()&np.r_[False,G.good.to_numpy()[:-1]]&np.isfinite(values).all(axis=1)&np.r_[False,np.isfinite(values[:-1]).all(axis=1)]
        indices=np.flatnonzero(change)
        for i in indices:
            events.append(dict(definition=name,receive_ns=int(t[i]),cursor=int(cursor[i]),group=int(G.group.iloc[i]),bid_raw=G.bid_raw.iloc[i],ask_raw=G.ask_raw.iloc[i],bid_size=G.bid_size.iloc[i],ask_size=G.ask_size.iloc[i],buy_lots=action_matrix['T_B'][i],sell_lots=action_matrix['T_A'][i],raw_record_index=None,side=None))
    for key,col in [('bid_quote','bid_raw'),('ask_quote','ask_raw'),('bid_touch_size','bid_size'),('ask_touch_size','ask_size')]:
        v=G[col].to_numpy();ok=np.r_[False,(np.diff(v)!=0)&np.isfinite(v[1:])&np.isfinite(v[:-1])]&G.good.to_numpy();ii=np.flatnonzero(ok);streams[key]=(t[ii],cursor[ii],np.ones(len(ii)))
    trades=R[R.action=='T'];prev=None
    for r in trades.itertuples():
        if r.side not in ('B','A'):prev=None;continue
        if prev!=r.side:
            index=int(np.searchsorted(cursor,r.cursor,side='left'))
            events.append(dict(definition='wire_aggressor_run_start',receive_ns=int(t[index]),cursor=int(r.cursor),group=int(G.group.iloc[index]),bid_raw=None,ask_raw=None,bid_size=None,ask_size=None,buy_lots=int(r.size) if r.side=='B' else 0,sell_lots=int(r.size) if r.side=='A' else 0,raw_record_index=int(r.record_index),side=r.side,raw_receive_ns=int(r.receive_ns),tape_day=r.tape_day))
        prev=r.side
    E=pd.DataFrame(events)
    E['raw_receive_ns']=pd.array([e.get('raw_receive_ns') for e in events],dtype='Int64')
    E=E.sort_values(['receive_ns','cursor','definition']);E['event_second']=E.receive_ns//S
    save(E,f'{day}-detector-free-events.csv.gz')
    case_records=[];case_index=[]
    birth_seconds=set(C.birth_second)
    for definition,e in E.groupby('definition'):
        for label,mask in [('in_birth_second',e.event_second.isin(birth_seconds)),('outside_birth_seconds',~e.event_second.isin(birth_seconds))]:
            if not mask.any():continue
            chosen=e[mask].iloc[0];g=G[G.group==chosen.group].iloc[0]
            raw_case=R[(R.cursor>=g.first_cursor)&(R.cursor<=g.cursor)].copy()
            raw_case['definition']=definition;raw_case['comparison']=label;case_records.append(raw_case)
            case_index.append(dict(definition=definition,comparison=label,group=int(g.group),first_cursor=int(g.first_cursor),close_cursor=int(g.cursor),raw_records=len(raw_case),receive_ns=str(int(g.receive_ns))))
    save(pd.concat(case_records,ignore_index=True),f'{day}-detector-free-case-records.csv.gz');save(pd.DataFrame(case_index),f'{day}-detector-free-cases.csv')
    # Exact-second intersection, not an arbitrary tolerance window.
    overlap=[];near=[]
    for definition,e in E.groupby('definition'):
        es=e.event_second.to_numpy();unique=np.unique(es);births=C.birth_second.to_numpy();matched=np.isin(births,unique)
        named=np.isin(es,births)
        overlap.append(dict(day=day,definition=definition,events=len(e),unique_event_seconds=len(unique),births=len(C),birth_seconds_with_event=int(matched.sum()),birth_seconds_without_event=int((~matched).sum()),events_in_birth_seconds=int(named.sum()),events_outside_birth_seconds=int((~named).sum())))
        et=e.receive_ns.to_numpy()
        for r in C.itertuples():
            b=int(r.birth_second)*S;j=np.searchsorted(et,b,'left');prior=(b-int(et[j-1]))/S if j else np.nan;after=(int(et[j])-b)/S if j<len(et) else np.nan
            near.append(dict(day=day,candidate_id=r.candidate_id,orientation=r.orientation,definition=definition,exact_second=bool(r.birth_second in unique),seconds_since_previous=prior,seconds_until_next=after,first_after_birth_receive_ns=str(et[j]) if j<len(et) else None,recognition_advantage_s=(int(r.recognition_ns)-int(et[j]))/S if j<len(et) and pd.notna(r.recognition_ns) else np.nan))
    O=pd.DataFrame(overlap);N=pd.DataFrame(near);save(O,f'{day}-moonshot-summary.csv');save(N,f'{day}-detector-free-nearest.csv')
    # M2: every first within-lag observable event, and all event quantities by side.
    foot=[];ordered=[]
    for m in M.itertuples():
        start=int(m.anchor_ns);end=start+int(round(m.lag_s*S));row=dict(day=day,candidate_id=m.candidate_id,kind=m.kind,orientation=m.orientation,lag_s=m.lag_s)
        for name,(st,sc,qty) in streams.items():
            a=np.searchsorted(st,start,'left');b=np.searchsorted(st,end,'right');has=b>a
            first=(int(st[a])-start)/S if has else np.nan
            row[name+'_first_s']=first;row[name+'_groups']=b-a;row[name+'_lots_or_changes']=float(qty[a:b].sum())
            ordered.append(dict(day=day,candidate_id=m.candidate_id,kind=m.kind,orientation=m.orientation,event=name,first_s=first,first_cursor=int(sc[a]) if has else None,first_ns=str(int(st[a])) if has else None,groups=b-a,lots_or_changes=float(qty[a:b].sum()),disposition='observed_within_lag' if has else 'absent_within_lag'))
        # Compare order of first cross-side and trade/book footprints; ties remain simultaneous groups.
        for relation,left,right in [('bid_vs_ask_quote','bid_quote','ask_quote'),('buy_vs_sell','T_B','T_A'),('bid_add_vs_bid_cancel','A_B','C_B'),('ask_add_vs_ask_cancel','A_A','C_A'),('buy_vs_ask_quote','T_B','ask_quote'),('sell_vs_bid_quote','T_A','bid_quote')]:
            x,y=row[left+'_first_s'],row[right+'_first_s'];row[relation]=('both_absent' if np.isnan(x) and np.isnan(y) else 'left_absent' if np.isnan(x) else 'right_absent' if np.isnan(y) else 'same_group_time' if x==y else 'left_first' if x<y else 'right_first')
        foot.append(row)
    P=pd.DataFrame(foot);A=pd.DataFrame(ordered);save(P,f'{day}-lag-footprints.csv');save(A,f'{day}-first-footprint-events.csv')
    rel=['bid_vs_ask_quote','buy_vs_sell','bid_add_vs_bid_cancel','ask_add_vs_ask_cancel','buy_vs_ask_quote','sell_vs_bid_quote']
    ordercounts=[]
    for col in rel:
        z=P.groupby(['kind','orientation',col],dropna=False).size().reset_index(name='paths');z['relation']=col;z=z.rename(columns={col:'ordering'});ordercounts.append(z)
    save(pd.concat(ordercounts,ignore_index=True),f'{day}-cross-side-ordering.csv')
    recon=[]
    for ori in C.orientation.unique():
        full,fa=plt.subplots(7,2,figsize=(13,20))
        for ax,event in zip(fa.flat,streams):
            for kind,color in [('candidate','#285f9c'),('control1','#ca6c2e'),('control2','#477b48')]:
                q=A[(A.orientation==ori)&(A.kind==kind)&(A.event==event)];ok=q.first_s.notna();v=np.sort(q.loc[ok,'first_s'])
                ax.scatter(np.arange(len(v)),v,s=4,label=f'{kind}: {len(q)}/{len(v)}/{len(q)-len(v)}',color=color)
                recon.append(dict(figure=f'{day}-all-footprints-{ori}.png',panel=event+' '+kind,rows_in=len(q),points_plotted=len(v),rows_excluded=len(q)-len(v),reason='absent within lag; no invented event time'))
            ax.set_title(event+' first observed seconds from birth');ax.legend(title='in / plotted / absent',fontsize=6,title_fontsize=6)
        full.suptitle(f'SPECULATIVE M2: {day} {ori}; every side and event type');full.tight_layout();full.savefig(ROOT/'figures'/f'{day}-all-footprints-{ori}.png',dpi=140);plt.close(full)
        fig,axes=plt.subplots(2,3,figsize=(14,8))
        for ax,definition in zip(axes[0],O.definition):
            q=N[(N.orientation==ori)&(N.definition==definition)];v=q.recognition_advantage_s;ok=v.notna();arr=np.sort(v[ok]);ax.scatter(np.arange(len(arr)),arr,s=4);ax.axhline(0,lw=.5,color='gray');ax.set_title(f'{definition}\nin {len(q)}; plotted {len(arr)}; undefined {len(q)-len(arr)}');ax.set_ylabel('recognition minus first structural event, seconds')
            recon.append(dict(figure=f'{day}-moonshots-{ori}.png',panel=definition,rows_in=len(q),points_plotted=len(arr),rows_excluded=len(q)-len(arr),reason='finalization-only or no later event'))
        for ax,event in zip(axes[1],['bid_quote','T_B','T_A']):
            for kind,color in [('candidate','#285f9c'),('control1','#ca6c2e'),('control2','#477b48')]:
                q=A[(A.orientation==ori)&(A.kind==kind)&(A.event==event)];ok=q.first_s.notna();v=np.sort(q.loc[ok,'first_s']);ax.scatter(np.arange(len(v)),v,s=4,label=f'{kind} {len(q)}/{len(v)}/{len(q)-len(v)}',color=color)
                recon.append(dict(figure=f'{day}-moonshots-{ori}.png',panel=event+' '+kind,rows_in=len(q),points_plotted=len(v),rows_excluded=len(q)-len(v),reason='absent during birth-to-recognition interval'))
            ax.set_title(event+' first time from birth');ax.legend(title='in / plotted / absent',fontsize=6,title_fontsize=6)
        fig.suptitle(f'SPECULATIVE definitions: {day} {ori}; all observations, no forecast rule');fig.tight_layout();fig.savefig(ROOT/'figures'/f'{day}-moonshots-{ori}.png',dpi=140);plt.close(fig)
    save(pd.DataFrame(recon),f'{day}-part3-figure-reconciliation.csv')
    print(day,'detector-free events',len(E),'footprint paths',len(P),'first-event rows',len(A),flush=True)
if __name__=='__main__':
 import sys;run(sys.argv[1])
