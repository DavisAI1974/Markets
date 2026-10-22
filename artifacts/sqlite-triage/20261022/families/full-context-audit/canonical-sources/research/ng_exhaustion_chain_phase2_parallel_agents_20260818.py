#!/usr/bin/env python3
# 20260818 durable matrix trigger: analysis semantics unchanged.
from __future__ import annotations
import argparse,gzip,json,math
from collections import Counter,defaultdict
from pathlib import Path
S='collapsed_same_flow_reload';O='collapsed_opposite_flow_reversal';P='persistent_exhaustion';X='collapsed_sparse_indeterminate';C={S:'S',O:'O',P:'P',X:'X'}

def fin(v):
 try:return math.isfinite(float(v))
 except:return False

def linload(*paths):
 d={}
 for p in paths:
  with gzip.open(p,'rt') as f:
   for z in f:
    r=json.loads(z);d[(r['week_sunday'],int(r['origin_sequence_index']))]=(int(r['all_model_consecutive_positive_depth']),r.get('consensus_elapsed_seconds'))
 return d

def rows(path):
 w=[]
 with gzip.open(path,'rt') as f:
  for z in f:
   r=json.loads(z);ep=r['dynamic_endpoint'];hs=(r.get('outcome',{}).get('post_endpoint_price') or {}).get('horizons',{})
   def h(k,m='signed_displacement_ticks'):
    x=hs.get(str(k),{});v=x.get(m);return None if x.get('censored',False) or not fin(v) else float(v)
   w.append((r['week_sunday'],int(r['sequence_index']),int(r['t0_idx']),r['seed_state'],int(r['polarity']),ep.get('causal_confirmation_idx'),ep.get('structural_onset_idx'),bool(r.get('link',{}).get('next_starts_before_endpoint_confirmation')),all(h(k,m)!=None for m in ('signed_displacement_ticks','mfe_ticks','mae_ticks') for k in (5,10,20,30,60)),h(5),h(60)))
 return w

def group(rs):
 out=defaultdict(list)
 for r in rs:out[r[0]].append(r)
 return out

def token(seq):return ''.join(C[x[3]] for x in seq)+'|'+''.join('S' if seq[i][4]==seq[i-1][4] else 'F' for i in range(1,len(seq)))
def valid(r):return r[5]!=None and r[6]!=None and not r[7] and int(r[5])<=int(r[6])+5 and r[9]!=None and r[10]!=None
def hav(ps,cur):return all(x[8] and x[5]!=None and int(x[5])+60<=cur[2] for x in ps)
def block(w,weeks):
 if w=='20260329':return 'held'
 i=weeks.index(w)
 return 'train' if i<18 else 'era13' if i<36 else 'era45' if i<48 else 'conf'
def dump(name,obj):Path(name).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')

def pairings(by,lin,weeks):
 out={m:defaultdict(lambda:{'n':Counter(),'weeks':defaultdict(set),'contexts':defaultdict(set)}) for m in (2,3)}
 for w,rs in by.items():
  b=block(w,weeks)
  for i in range(len(rs)):
   d,_=lin.get((w,i),(0,None))
   if d<2 or i+d>=len(rs):continue
   full=token(rs[i:i+d+1])
   for m in (2,3):
    seen=set()
    for j in range(i,i+d+2-m):
     k=token(rs[j:j+m]
     )
     if k in seen:continue
     seen.add(k);z=out[m][k];z['n'][b]+=1;z['weeks'][b].add(w);z['contexts'][b].add(full)
 ans={}
 for m,D in out.items():
  a=[]
  for k,z in D.items():
   pre=sum(z['n'][b] for b in ('era13','era45','conf'))
   if pre<3:continue
   a.append({'module':k,'preheld_n':pre,'blocks':{b:{'n':z['n'][b],'weeks':len(z['weeks'][b]),'contexts':len(z['contexts'][b])} for b in ('era13','era45','conf','held')}})
  a.sort(key=lambda x:(sum(x['blocks'][b]['weeks'] for b in ('era13','era45','conf')),x['preheld_n']),reverse=True);ans[str(m)]=a[:50]
 return ans

def extension(by,lin,weeks):
 D=defaultdict(lambda:{'e':Counter(),'x':Counter()});totE=Counter();totX=Counter()
 for w,rs in by.items():
  b=block(w,weeks)
  if b=='train':continue
  for i in range(len(rs)-1):
   d,_=lin.get((w,i),(0,None))
   if d<1:continue
   k=token(rs[i:i+2]);D[k]['e'][b]+=1;totE[b]+=1
   if d>=2:D[k]['x'][b]+=1;totX[b]+=1
 a=[]
 for k,z in D.items():
  cells={}
  for b in ('era13','era45','conf','held'):
   e=z['e'][b];x=z['x'][b];r=x/e if e else None;base=totX[b]/totE[b] if totE[b] else None;lift=r/base if r!=None and base else None
   cells[b]={'eligible':e,'extended':x,'rate':r,'baseline':base,'lift':lift}
  if sum(cells[b]['eligible'] for b in ('era13','era45','conf'))>=30:a.append({'module':k,'blocks':cells})
 a.sort(key=lambda x:sum(x['blocks'][b]['eligible'] for b in ('era13','era45','conf')),reverse=True)
 return a[:80]

def timing(lin):
 import numpy as np
 from sklearn.mixture import GaussianMixture
 ans={}
 for d,k in ((2,3),(3,2)):
  pre=[e for (w,_),(dd,e) in lin.items() if w!='20260329' and dd==d and e];held=[e for (w,_),(dd,e) in lin.items() if w=='20260329' and dd==d and e]
  Xv=np.log(np.array(pre,float)).reshape(-1,1);g=GaussianMixture(n_components=k,random_state=20260818,n_init=20).fit(Xv);order=np.argsort(g.means_.ravel());mp={int(raw):i for i,raw in enumerate(order)}
  pc=Counter(mp[int(x)] for x in g.predict(Xv));hc=Counter(mp[int(x)] for x in g.predict(np.log(np.array(held,float)).reshape(-1,1))) if held else Counter()
  ans[f'D{d}']={'components':k,'bic':g.bic(Xv),'centers_seconds':np.exp(g.means_.ravel()[order]).tolist(),'preheld_counts':dict(pc),'held_counts':dict(hc),'preheld_n':len(pre),'held_n':len(held)}
 return ans

def investigator(by,weeks):
 D={k:defaultdict(lambda:defaultdict(list)) for k in (1,2,3,4)}
 for w,rs in by.items():
  b=block(w,weeks)
  if b=='train':continue
  for i,cur in enumerate(rs):
   if not valid(cur):continue
   ret=cur[10]-cur[9]
   for k in (1,2,3,4):
    if i<k or not hav(rs[i-k:i],cur):continue
    st=''.join(C[x[3]] for x in rs[i-k:i]);rel='SAME' if cur[4]==rs[i-1][4] else 'FLIP';D[k][f'{st}->{rel}'][b].append(ret)
 out={}
 for k,Q in D.items():
  a=[]
  for pat,z in Q.items():
   cells={b:{'n':len(z[b]),'mean':sum(z[b])/len(z[b]) if z[b] else None} for b in ('era13','era45','conf','held')}
   if cells['era13']['n']>=20 and cells['era45']['n']>=12 and cells['conf']['n']>=6:a.append({'pattern':pat,'blocks':cells,'policy':'FLAG_AND_DECOMPOSE_NOT_AUTO_KILL'})
  a.sort(key=lambda x:min(x['blocks'][b]['n'] for b in ('era13','era45','conf')),reverse=True);out[str(k)]=a
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['pairings','extension','timing','investigator'],required=True);p.add_argument('--base',required=True);p.add_argument('--held',required=True);p.add_argument('--base-lineage',required=True);p.add_argument('--held-lineage',required=True);p.add_argument('--summary',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 weeks=json.load(open(a.summary))['weeks'];lin=linload(a.base_lineage,a.held_lineage)
 if a.mode=='timing':res=timing(lin)
 else:
  by=group(rows(a.base)+rows(a.held));res={'pairings':pairings,'extension':extension,'investigator':investigator}[a.mode](by,lin,weeks) if a.mode!='investigator' else investigator(by,weeks)
 dump(a.out,{'status':'PARALLEL_RECURRENCE_AGENT_COMPLETE','mode':a.mode,'result':res,'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False}})
if __name__=='__main__':main()
