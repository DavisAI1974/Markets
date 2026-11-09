import sys; sys.path.insert(0,'.')
from x11_det_sim2 import *
OUT='/home/claude/markets/tasks/family-research-20261022/claude-pass-3day/crossday/detector'
import os; os.makedirs(OUT,exist_ok=True)
def run(d, mode='HYB', Rd=5, REF=45, warm=900):
    S,top,ops=load(d); sec=S.second.to_numpy()
    r=series(d,mode,S) if d!='20231018' else series(d,mode,S)
    a,fin,base,prom=prep2(d,r); thr=thr_series(a,fin); n=len(a)
    top=top.dropna(subset=['birth_second']).copy(); top['birth_second']=top.birth_second.astype(int); recset=set(top.birth_second)
    rows=[]; pend=None; relt=None; cid=0; cl_members={}
    def flush(s):
        nonlocal pend
        i,p,c=pend; rows[c['row']]['disposition']='emitted'; rows[c['row']]['emitted_release_second']=int(sec[min(s,n-1)]); rows[c['row']]['emulated_lag']=s-i; pend=None
    for s in range(n):
        i=s-Rd
        if pend is not None and s>=relt: flush(s)
        if i>=warm and i>=0 and np.isfinite(thr[s]) and fin[i] and a[i]>=1e-12 and a[i]>=thr[s]:
            row=dict(day=d,second=int(sec[i]),decision_second=int(sec[s]),ratio=float(r[i]),polarity=int(np.sign(r[i])),baseline=float(base[i]),prominence=float(prom[i]),threshold=float(thr[s]),
                     disposition='',cluster_id=-1,cluster_first_second=-1,emitted_release_second=-1,emulated_lag=-1,in_recorded=int(int(sec[i]) in recset))
            rows.append(row); k=len(rows)-1
            if pend is None:
                cid+=1; row['cluster_id']=cid; row['cluster_first_second']=row['second']; pend=(i,prom[i],dict(row=k,cid=cid,first=row['second'])); relt=s+REF
            else:
                row['cluster_id']=pend[2]['cid']; row['cluster_first_second']=pend[2]['first']
                if prom[i]>pend[1]:
                    rows[pend[2]['row']]['disposition']='replaced_by_higher_prominence'
                    pend=(i,prom[i],dict(row=k,cid=pend[2]['cid'],first=pend[2]['first']))
                else: row['disposition']='lost_to_higher_or_equal_prominence_in_cluster'
    if pend is not None:
        rows[pend[2]['row']]['disposition']='pending_at_series_end'
    L=pd.DataFrame(rows)
    # recorded births with operands, and which the emulation did not produce
    ops2=ops.merge(top[['candidate_id','birth_second','available_second']],on='candidate_id',how='left') if 'available_second' not in ops.columns else ops
    em=set(L[L.disposition=='emitted'].second)
    R=top.copy(); R['emulated_as_birth']=R.birth_second.isin(em).astype(int)
    R['saturated_second_in_ledger']=R.birth_second.isin(set(L.second)).astype(int)
    R=R.merge(L[['second','disposition','cluster_id','cluster_first_second','emitted_release_second','emulated_lag','baseline','prominence']].rename(columns={'second':'birth_second'}),on='birth_second',how='left')
    L.to_csv(f'{OUT}/ledger_saturated_seconds_{d}.csv',index=False); R.to_csv(f'{OUT}/ledger_recorded_births_{d}.csv',index=False)
    return L,R
if __name__=='__main__':
    for d in sys.argv[1:]:
        L,R=run(d); print(d,len(L),'ledger rows;',L.disposition.value_counts().to_dict(),'; recorded',len(R),'emulated as birth',int(R.emulated_as_birth.sum()))
