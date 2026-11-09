import pandas as pd, numpy as np, gzip, json
R0='/home/claude/markets/tasks/family-research-20261022'
def load(d):
    if d=='20231018': cp=f'{R0}/october18-candidate-inputs.jsonl.gz'; sp=f'{R0}/research-atlas-v2/dipole-completed-group-flow.csv.gz'
    else: cp=f'{R0}/replay-comparison/{d}/candidate-inputs.jsonl.gz'; sp=f'{R0}/replay-comparison/{d}/research-atlas-v2/dipole-completed-group-flow.csv.gz'
    S=pd.read_csv(sp); rows=[json.loads(l) for l in gzip.open(cp,'rt')]
    top=pd.DataFrame([{k:x[k] for k in ('candidate_id','birth_second','available_second') if k in x} for x in rows])
    ops=pd.DataFrame([dict(x['recorded_operands'],candidate_id=x['candidate_id']) for x in rows if 'recorded_operands' in x])
    return S,top,ops
def prep(S, nanzero=False):
    sec=S.second.to_numpy(); f=S.ratio.to_numpy(float); a=np.abs(f); n=len(a)
    base=np.zeros(n)
    for i in range(n):
        w=a[max(0,i-30):max(0,i-9)] if i>=30 else a[0:max(0,i-9)]
        w=w[np.isfinite(w)]
        base[i]=np.median(w) if len(w) else 0.0
    # trailing quantile threshold over finite |f| observations strictly before i
    thr=np.full(n,np.nan); nobs=np.zeros(n,int)
    fin=np.isfinite(a); cs=np.cumsum(fin)
    nobs[1:]=cs[:-1]
    return sec,f,a,base,thr,nobs,fin
