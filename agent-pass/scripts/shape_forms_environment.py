"""Pair shape targets with archived book strata, event clocks and both controls."""
from shape_forms import DAYS,DEFS,COLORS,ROOT,S,save,pd,np,plt,count,finish,RECON

import sys
if '--render-only' in sys.argv:
    Q=pd.read_csv(ROOT/'tables/shape_forms-environment-pairs.csv',float_precision='round_trip');D=pd.read_csv(ROOT/'tables/shape_forms-environment-contrasts.csv',float_precision='round_trip')
else:
    P=pd.read_csv(ROOT/'tables/shape_forms-observations.csv',float_precision='round_trip')
    rows=[]
    for day in DAYS:
        C=pd.read_csv(ROOT/f'tables/{day}-candidate-operands.csv',dtype={'recognition_ns':'Int64'}).set_index('candidate_id')
        M=pd.read_csv(ROOT/f'tables/{day}-path-members.csv',dtype={'anchor_ns':'int64'}).set_index(['candidate_id','kind'])
        H=pd.read_csv(ROOT/f'tables/{day}-matching-audit.csv').set_index(['candidate_id','kind'])
        F=pd.read_csv(ROOT/f'tables/{day}-lag-footprints.csv').set_index(['candidate_id','kind'])
        E=pd.read_csv(ROOT/f'tables/{day}-detector-free-events.csv.gz',usecols=['definition','receive_ns'])
        times={d:np.sort(E.loc[E.definition==d,'receive_ns'].to_numpy(dtype=np.int64)) for d in DEFS}
        for p in P[P.day==day].itertuples():
            c=C.loc[p.candidate_id];birth=int(c.birth_second)*S;live=pd.notna(c.recognition_ns)
            for kind in ['candidate','control1','control2']:
                key=(p.candidate_id,kind);member=M.loc[key] if key in M.index else None
                start=birth if kind=='candidate' else int(member.anchor_ns) if member is not None else None
                end=start+int(c.recognition_ns)-birth if start is not None and live else None
                ts=times[p.definition];index=np.searchsorted(ts,start,'left') if start is not None else len(ts)
                event=int(ts[index]) if index<len(ts) else None
                lead_ns=end-event if end is not None and event is not None else None
                row=dict(day=day,candidate_id=p.candidate_id,definition=p.definition,kind=kind,orientation='SAME',candidate_rank=p.rank,candidate_signed_section=p.section,anchor_ns=str(start) if start is not None else None,paired_end_ns=str(end) if end is not None else None,first_event_ns=str(event) if event is not None else None,recognition_minus_event_ns=str(lead_ns) if lead_ns is not None else None,recognition_minus_event_s=lead_ns/S if lead_ns is not None else None,event_wait_s=(event-start)/S if event is not None else None,disposition='available' if lead_ns is not None else 'finalization_only_or_missing_control_or_next_event')
                if member is not None:
                    h=H.loc[key];f=F.loc[key]
                    row.update(actual_spread_bucket=h.actual_regime,actual_activity_bucket=h.actual_activity_bucket,trailing_60s_activity=h.actual_activity,mid_change_ticks=member.mid_change_ticks,polarity=member.polarity)
                    row.update({field:f[field] for field in F.columns if field.endswith('_groups') or field.endswith('_lots_or_changes') or '_vs_' in field})
                rows.append(row)
    Q=pd.DataFrame(rows);save(Q,'shape_forms-environment-pairs.csv')
    contrasts=[]
    for key,g in Q.groupby(['day','definition','candidate_id'],sort=False):
        c=g[g.kind=='candidate'].iloc[0]
        for kind in ['control1','control2']:
            v=g[g.kind==kind].iloc[0]
            contrasts.append(dict(day=key[0],definition=key[1],candidate_id=key[2],control_kind=kind,candidate_rank=c.candidate_rank,candidate_signed_section=c.candidate_signed_section,spread_bucket=c.get('actual_spread_bucket'),activity_bucket=c.get('actual_activity_bucket'),candidate_lead_s=c.recognition_minus_event_s,control_lead_s=v.recognition_minus_event_s,control_minus_candidate_lead_s=v.recognition_minus_event_s-c.recognition_minus_event_s,candidate_quote_change_ticks=c.get('mid_change_ticks'),control_quote_change_ticks=v.get('mid_change_ticks')))
    D=pd.DataFrame(contrasts);save(D,'shape_forms-environment-contrasts.csv')
for definition in DEFS:
    fig,axes=plt.subplots(3,4,figsize=(19,13),sharex=True,sharey=True);name=f'shape_forms-environment-{definition}.png'
    for row,kind in enumerate(['candidate','control1','control2']):
      for col,day in enumerate(DAYS):
        q=Q[(Q.day==day)&(Q.kind==kind)&(Q.definition==definition)];ok=q.recognition_minus_event_s.notna()&q.mid_change_ticks.notna();ax=axes[row,col]
        for spread,color in zip([1,2,3],COLORS):
            z=q[ok&(q.actual_spread_bucket==spread)];ax.scatter(z.recognition_minus_event_s,z.mid_change_ticks,s=10,color=color,label=f'spread {spread}'+('+' if spread==3 else ''))
        ax.axvline(0,color='gray',lw=.5);ax.axhline(0,color='gray',lw=.5);ax.set_title(f'{day} {kind}: {len(q)}/{ok.sum()}/{(~ok).sum()}');ax.set_xlabel('Paired end minus event (s)');ax.set_ylabel('Midquote change (ticks)');ax.legend(fontsize=6)
        count(name,str(day)+' '+kind,len(q),int(ok.sum()),'missing live clock, control anchor, event or book path')
    fig.suptitle(definition+': individual event timing and quote behavior, both matched controls; in/plotted/unavailable');finish(fig,name)
    fig,axes=plt.subplots(2,4,figsize=(19,9),sharex=True,sharey=True);name=f'shape_forms-paired-contrasts-{definition}.png'
    for row,kind in enumerate(['control1','control2']):
      for col,day in enumerate(DAYS):
        q=D[(D.day==day)&(D.control_kind==kind)&(D.definition==definition)];ok=q.control_minus_candidate_lead_s.notna();ax=axes[row,col]
        for bucket,color in zip(sorted(q.activity_bucket.dropna().unique()),plt.cm.viridis(np.linspace(0,1,5))):
            z=q[ok&(q.activity_bucket==bucket)];ax.scatter(z.candidate_rank,z.control_minus_candidate_lead_s,s=8,color=color,label=f'activity {int(bucket)}')
        ax.axhline(0,color='gray',lw=.5);ax.set_title(f'{day} {kind}: {len(q)}/{ok.sum()}/{(~ok).sum()}');ax.set_xlabel('Original candidate rank');ax.set_ylabel('Control lead minus candidate lead (s)');ax.legend(fontsize=6)
        count(name,str(day)+' '+kind,len(q),int(ok.sum()),'missing live clock, control anchor or next event')
    fig.suptitle(definition+': every matched timing contrast by existing activity stratum');finish(fig,name)
save(pd.DataFrame(RECON),'shape_forms-environment-figure-reconciliation.csv')
print('environment rows',len(Q),'paired contrasts',len(D),'reconciled series',len(RECON))
