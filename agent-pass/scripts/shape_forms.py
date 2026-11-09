"""Additive SAME shape descriptions; original ranks/seconds and every residual retained."""
from common import *
from scipy.optimize import linprog
from scipy.sparse import csr_matrix, eye, hstack, vstack
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DAYS=[20231002,20231003,20231017,20231018]
DEFS=['quote_relocation','touch_size_change','wire_aggressor_run_start']
SECTIONS=['full','negative','zero','positive']
FORMS=['line','logarithm','shifted_reciprocal','shifted_exponential']
GRID=[.25,.5,1,2,4,8,16,32,64,128,256,512,1024]
COLORS=['#0072B2','#D55E00','#009E73','#CC79A7']
RECON=[]
plt.rcParams.update({'font.size':8})

def section(q,label):
    y=q.recognition_minus_event_s
    return q if label=='full' else q[y<0] if label=='negative' else q[y==0] if label=='zero' else q[y>0]

def basis(x,form,shift):
    if form=='line':return x
    if form=='logarithm':return np.log(x+shift)
    if form=='shifted_reciprocal':return 1/(x+shift)
    return np.exp(-x/shift)

def count(fig,panel,n,plotted,reason='undefined value',**extra):
    RECON.append(dict(figure=fig,panel=panel,rows_in=n,points_plotted=plotted,rows_excluded=n-plotted,reason=reason,**extra))

def finish(fig,name):
    fig.tight_layout(rect=(0,0,1,.96));fig.savefig(ROOT/'figures'/name,dpi=130);plt.close(fig)

def observations():
    parts=[];sources=[]
    for day in DAYS:
        p=ROOT/f'tables/{day}-detector-free-nearest.csv';n=pd.read_csv(p,dtype={'first_after_birth_receive_ns':'Int64'},float_precision='round_trip')
        n=n[n.orientation=='SAME'].copy()
        for definition in DEFS:
            q=n[n.definition==definition].copy();q=q.sort_values('recognition_advantage_s',kind='stable',na_position='last')
            q['rank']=pd.array(list(range(q.recognition_advantage_s.notna().sum()))+[None]*q.recognition_advantage_s.isna().sum(),dtype='Int64')
            q['recognition_minus_event_s']=q.recognition_advantage_s;q['section']=np.where(q.recognition_advantage_s.isna(),'unavailable',np.where(q.recognition_advantage_s<0,'negative',np.where(q.recognition_advantage_s>0,'positive','zero')))
            q['adjacent_gap_s']=q.recognition_advantage_s.diff();q['gap_change_s']=q.adjacent_gap_s.diff();q['previous_candidate_id']=q.candidate_id.shift(1);q['previous_section']=q.section.shift(1)
            parts.append(q)
        sources.append(dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    P=pd.concat(parts,ignore_index=True);save(P,'shape_forms-observations.csv')
    (ROOT/'tables/shape_forms-source-provenance.json').write_text(json.dumps(sources,indent=2)+'\n')
    for definition in DEFS:
        q=P[P.definition==definition]
        fig,axes=plt.subplots(4,1,figsize=(12,14));name=f'shape_forms-sections-{definition}.png'
        for ax,label in zip(axes,SECTIONS):
            for day,color in zip(DAYS,COLORS):
                z=section(q[q.day==day],label);ok=z.recognition_minus_event_s.notna();ax.plot(z.loc[ok,'rank'],z.loc[ok,'recognition_minus_event_s'],'.-',lw=.7,ms=3,color=color,label=f'{day}: {len(z)}/{ok.sum()}/{(~ok).sum()}');count(name,label+' '+str(day),len(z),int(ok.sum()))
            ax.axhline(0,color='gray',lw=.5);ax.set_title(label+' signed-time section');ax.set_xlabel('Original sorted rank');ax.set_ylabel('Recognition minus event (s)');ax.legend(title='in / plotted / unavailable')
        fig.suptitle(definition+': full observations, no rank reset; negative = event AFTER recognition');finish(fig,name)
        fig,axes=plt.subplots(2,1,figsize=(12,9));name=f'shape_forms-gaps-{definition}.png'
        for ax,field in zip(axes,['adjacent_gap_s','gap_change_s']):
            for day,color in zip(DAYS,COLORS):
                z=q[q.day==day];ok=z[field].notna();ax.scatter(z.loc[ok,'rank'],z.loc[ok,field],s=8,color=color,label=f'{day}: {len(z)}/{ok.sum()}/{(~ok).sum()}');count(name,field+' '+str(day),len(z),int(ok.sum()),'missing predecessor(s) or live clock')
            ax.set_title(field);ax.set_xlabel('Original sorted rank');ax.set_ylabel('Seconds');ax.legend(title='in / plotted / unavailable')
        fig.suptitle(definition+': every adjacent gap and gap change; no marker threshold');finish(fig,name)
    return P

def fit(P):
    models=[];search=[]
    for (day,definition),allq in P.groupby(['day','definition']):
      for label in SECTIONS:
        q=section(allq,label).dropna(subset=['rank','recognition_minus_event_s']);x=q['rank'].to_numpy(dtype=float);y=q.recognition_minus_event_s.to_numpy();n=len(q)
        for form in FORMS:
            common=dict(source_day=day,definition=definition,section=label,form=form,n=n,rank_min=float(x.min()) if n else None,rank_max=float(x.max()) if n else None,constant_response=bool(n and np.ptp(y)==0))
            candidates=[]
            for shift in ([None] if form=='line' else GRID):
                row=dict(**common,shift=shift,a=None,b=None,total_absolute_residual=None,status='fewer_than_two_ranks')
                if n>=2:
                    z=basis(x,form,shift)
                    if np.ptp(z)<1e-12:row['status']='numerically_constant_basis'
                    else:
                        X=csr_matrix(np.column_stack([np.ones(n),z]));I=eye(n,format='csr')
                        result=linprog(np.r_[0,0,np.ones(n)],A_ub=vstack([hstack([X,-I]),hstack([-X,-I])]),b_ub=np.r_[y,-y],bounds=[(None,None),(None,None)]+[(0,None)]*n,method='highs')
                        row['status']='fitted' if result.success else 'solver_unavailable';row['solver_message']=result.message
                        if result.success:
                            a,b=result.x[:2];row.update(a=a,b=b,total_absolute_residual=float(np.abs(a+b*z-y).sum()));candidates.append(row)
                search.append(row)
            if candidates:
                chosen=min(candidates,key=lambda r:r['total_absolute_residual']).copy();chosen['grid_boundary']=bool(form!='line' and chosen['shift'] in (GRID[0],GRID[-1]));chosen.pop('solver_message',None)
            else:chosen=dict(**common,shift=None,a=None,b=None,total_absolute_residual=None,status='no_identifiable_fit',grid_boundary=False)
            chosen['model_id']=f'{day}:{definition}:{label}:{form}';models.append(chosen)
        print('fit',day,definition,label,n,flush=True)
    M=pd.DataFrame(models);save(M,'shape_forms-models.csv');save(pd.DataFrame(search),'shape_forms-fit-grid.csv')
    residual=[]
    for m in M.itertuples():
      target_defs=DEFS if m.definition=='quote_relocation' else [m.definition]
      for target_def in target_defs:
       for day in DAYS:
        q=section(P[(P.day==day)&(P.definition==target_def)],m.section)
        for r in q.itertuples():
            available=pd.notna(r.rank) and m.status=='fitted';prediction=float(m.a+m.b*basis(float(r.rank),m.form,m.shift)) if available else None
            domain='unavailable_fit_or_clock' if not available else 'within_source_rank_domain' if m.rank_min<=r.rank<=m.rank_max else 'out_of_source_rank_domain'
            residual.append(dict(model_id=m.model_id,source_day=m.source_day,target_day=day,source_definition=m.definition,target_definition=target_def,section=m.section,form=m.form,candidate_id=r.candidate_id,rank=r.rank,observed_s=r.recognition_minus_event_s,predicted_s=prediction,residual_s=prediction-r.recognition_minus_event_s if available else None,domain=domain))
    R=pd.DataFrame(residual);save(R,'shape_forms-residuals.csv.gz');return M,R

def render_models(P,M,R):
    for definition in DEFS:
      for label in SECTIONS:
        fig,axes=plt.subplots(5,4,figsize=(20,17),sharey='row');name=f'shape_forms-fits-{definition}-{label}.png'
        for col,day in enumerate(DAYS):
            q=section(P[(P.day==day)&(P.definition==definition)],label);ok=q.recognition_minus_event_s.notna();ax=axes[0,col];ax.scatter(q.loc[ok,'rank'],q.loc[ok,'recognition_minus_event_s'],s=8,color='black',label=f'data {len(q)}/{ok.sum()}/{(~ok).sum()}');count(name,f'{day} data',len(q),int(ok.sum()))
            for row,(form,color) in enumerate(zip(FORMS,COLORS),1):
                z=R[(R.source_day==day)&(R.target_day==day)&(R.source_definition==definition)&(R.target_definition==definition)&(R.section==label)&(R.form==form)];ok=z.residual_s.notna()
                ax.plot(z.loc[ok,'rank'],z.loc[ok,'predicted_s'],lw=.8,color=color,label=f'{form} {len(z)}/{ok.sum()}/{(~ok).sum()}');count(name,f'{day} {form} fit',len(z),int(ok.sum()),'fit or clock unavailable')
                a=axes[row,col];a.scatter(z.loc[ok,'rank'],z.loc[ok,'residual_s'],s=8,color=color);a.axhline(0,color='gray',lw=.5);a.set_title(f'{form}: {len(z)}/{ok.sum()}/{(~ok).sum()}');a.set_ylabel('Predicted - observed (s)');a.set_xlabel('Original rank');count(name,f'{day} {form} residual',len(z),int(ok.sum()),'fit or clock unavailable')
            ax.set_title(str(day));ax.set_ylabel('Recognition minus event (s)');ax.legend(fontsize=6,title='in / plotted / unavailable')
        fig.suptitle(f'SPECULATIVE descriptive fits: {definition}, {label}; all residuals retained');finish(fig,name)
        for form in FORMS:
            z=R[(R.source_definition==definition)&(R.target_definition==definition)&(R.section==label)&(R.form==form)]
            name=f'shape_forms-transfer-{definition}-{label}-{form}.png';render_transfer(z,name,f'{definition} {label} {form}: frozen fit across dates')
    for target,slug in [('wire_aggressor_run_start','run'),('touch_size_change','touch')]:
     for label in SECTIONS:
      for form in FORMS:
        z=R[(R.source_definition=='quote_relocation')&(R.target_definition==target)&(R.section==label)&(R.form==form)]
        name=f'shape_forms-quote-to-{slug}-{label}-{form}.png';render_transfer(z,name,f'Quote fit applied to {target}: {label}, {form}')

def render_transfer(Z,name,title):
    fig,axes=plt.subplots(4,4,figsize=(18,13),sharex=True,sharey=True)
    for row,source in enumerate(DAYS):
      for col,target in enumerate(DAYS):
        q=Z[(Z.source_day==source)&(Z.target_day==target)];ok=q.residual_s.notna();out=q.domain=='out_of_source_rank_domain';ax=axes[row,col]
        for mask,color,label in [(ok&~out,'#0072B2','source rank domain'),(ok&out,'#D55E00','outside source rank domain')]:ax.scatter(q.loc[mask,'rank'],q.loc[mask,'residual_s'],s=7,color=color,label=label)
        ax.axhline(0,color='gray',lw=.5);ax.set_title(f'{source} -> {target}\nin {len(q)}, plotted {ok.sum()}, unavailable {(~ok).sum()}, outside {out.sum()}');ax.set_xlabel('Original target rank');ax.set_ylabel('Predicted - observed (s)');ax.legend(fontsize=5)
        count(name,f'{source} -> {target}',len(q),int(ok.sum()),'fit or clock unavailable; outside-domain predictions retained',out_of_source_rank_domain=int(out.sum()))
    fig.suptitle('SPECULATIVE '+title);finish(fig,name)

if __name__=='__main__':
    import sys
    if '--render-only' in sys.argv:
        P=pd.read_csv(ROOT/'tables/shape_forms-observations.csv',float_precision='round_trip');M=pd.read_csv(ROOT/'tables/shape_forms-models.csv',float_precision='round_trip');R=pd.read_csv(ROOT/'tables/shape_forms-residuals.csv.gz',float_precision='round_trip')
        previous=pd.read_csv(ROOT/'tables/shape_forms-figure-reconciliation.csv');RECON.extend(previous[previous.figure.str.contains('shape_forms-sections-|shape_forms-gaps-')].to_dict('records'))
    else:P=observations();M,R=fit(P)
    render_models(P,M,R)
    save(pd.DataFrame(RECON),'shape_forms-figure-reconciliation.csv')
    print('observations',len(P),'models',len(M),'residual rows',len(R),'reconciled series',len(RECON),flush=True)
