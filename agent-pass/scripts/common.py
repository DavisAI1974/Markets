"""Pinned-source readers. Only agent-pass is writable; caches are reproducible."""
from pathlib import Path
import subprocess, gzip, json, hashlib, io
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
BASE='tasks/family-research-20261022/'
REV='a1c4d6f32a03a21795f411e509f7fc77d479b3bb'
TAPE='1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202'
S=10**9
for d in ('cache','tables','figures'): (ROOT/d).mkdir(exist_ok=True)
def blob(path, rev=REV):
    key=hashlib.sha256((rev+':'+path).encode()).hexdigest()
    f=ROOT/'cache'/key
    if not f.exists(): f.write_bytes(subprocess.check_output(['git','show',rev+':'+path]))
    b=f.read_bytes()
    entry=dict(revision=rev,path=path,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
    m=ROOT/'source-manifest.json'; entries=json.loads(m.read_text()) if m.exists() else []
    if entry not in entries: entries.append(entry); m.write_text(json.dumps(entries,indent=2)+'\n')
    return b

def records(path,rev=REV):
    b=blob(path,rev)
    if path.endswith('.gz'): b=gzip.decompress(b)
    return [json.loads(x) for x in b.splitlines()]
def csv(path,rev=REV):
    b=blob(path,rev)
    return pd.read_csv(io.BytesIO(gzip.decompress(b) if path.endswith('.gz') else b))
def save(df,name):
    f=ROOT/'tables'/name
    df.to_csv(f,index=False,**({'compression':{'method':'gzip','mtime':0}} if name.endswith('.gz') else {}))

def candidates(day):
    p=BASE+('october18-candidate-inputs.jsonl.gz' if day=='20231018' else f'replay-comparison/{day}/candidate-inputs.jsonl.gz')
    rs=records(p); out=[]; prev=None
    covered=csv(BASE+'claude-pass/tables/dipole/t6_cohort_coverage.csv') if day=='20231018' else None
    for i,r in enumerate(rs):
        op=r['recorded_operands']; birth=r.get('birth_second',r.get('original_episode',{}).get('birth_recv_ns',0)//S)
        pol=op.get('polarity',0)
        ori=r.get('recognition_orientation','NO_PREDECESSOR' if prev is None else 'SAME' if pol==prev else 'FLIP')
        out.append(dict(day=day,candidate_id=r['candidate_id'],birth_second=birth,recognition_ns=r.get('recognition_receive_ns'),available_second=r.get('available_second'),polarity=pol,orientation=ori,original_coverage=(str(covered.iloc[i].tape) if covered is not None else 'archived'),flow_state=r.get('birth_to_emission_flow_state'),quote_move=r.get('quote_move_relative_to_birth_polarity'),**{k:v for k,v in op.items() if k in ['baseline','threshold','prominence','magnitude','observations_behind_threshold','searched_span_seconds','window_truncated']}))
        prev=pol
    frame=pd.DataFrame(out)
    frame['recognition_ns']=pd.array([r['recognition_ns'] for r in out],dtype='Int64')
    return frame,rs

def groups(day):
    f=ROOT/'cache'/f'groups-{day}.parquet'
    if f.exists():return pd.read_parquet(f)
    if day=='20231018':
        p='research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz'; rev='b5f28bd57de5ed4ff889335edb9a33216b67eb6a'
    else:p=BASE+f'replay-artifacts/{day}/standalone-inputs/groups.jsonl.gz';rev='2f12d6d47'
    rs=records(p,rev); out=[]
    for g in rs:
        b,a=g['bid'],g['ask']
        out.append((g['receive_ns'],g['close_cursor'],g['first_cursor'],g['group_ordinal'],b[0] if b else np.nan,a[0] if a else np.nan,b[1] if b else np.nan,a[1] if a else np.nan,g['print_count'],not any(g[k] for k in ['snapshot_member','reset_member','bad_receive_clock_member'])))
    G=pd.DataFrame(out,columns=['receive_ns','cursor','first_cursor','group','bid_raw','ask_raw','bid_size','ask_size','prints','good'])
    assert np.all(np.diff(G.receive_ns)>=0) and np.all(np.diff(G.cursor)>0)
    G.to_parquet(f);return G

def raw(day):
    import databento as db
    f=ROOT/'cache'/f'raw-{day}.parquet'
    if f.exists():return pd.read_parquet(f)
    sources=[(day,0)] if day in ('20231002','20231017') else [(str(int(day)-1),-808453 if day=='20231003' else -841601),(day,4889 if day=='20231003' else 17375)]
    G=groups(day); parts=[]
    for d,offset in sources:
        b=blob(f'data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{d}.dbn.zst',TAPE)
        df=db.DBNStore.from_bytes(b).to_df(price_type='fixed',pretty_ts=False,map_symbols=False).reset_index()
        df['record_index']=np.arange(len(df));df['cursor']=df.record_index+offset;df['tape_day']=d
        df=df[(df.cursor>=0)&(df.cursor<=G.cursor.iloc[-1])].copy()
        df['receive_ns']=df.ts_recv.astype('int64')
        parts.append(df[['receive_ns','cursor','record_index','tape_day','action','side','price','size','order_id','flags']])
    R=pd.concat(parts,ignore_index=True)
    check=R.set_index('cursor').loc[G.cursor]
    assert np.array_equal(check.receive_ns,G.receive_ns) and np.all(check['flags'].astype(int)&128)
    R.to_parquet(f);return R

def flow(day):
    return csv(BASE+('research-atlas-v2/' if day=='20231018' else f'replay-comparison/{day}/research-atlas-v2/')+'dipole-completed-group-flow.csv.gz')
