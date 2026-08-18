#!/usr/bin/env python3
from __future__ import annotations
import argparse, gzip, json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

S='collapsed_same_flow_reload'; O='collapsed_opposite_flow_reversal'; P='persistent_exhaustion'; X='collapsed_sparse_indeterminate'
CODE={S:'S',O:'O',P:'P',X:'X'}
BLOCKS=('train','era13','era45','conf','held')
OOT=('era13','era45','conf')
PAIR_SEEDS=('PP|S','PO|S','OO|F','OP|F','XP|F','SS|S','PP|F','XP|S')
TRIPLET_SEEDS=('PPP|SS','PPX|SS','OOO|FF','PPS|SS','POP|SF')
CONTEXT_SEEDS=('OOSS->FLIP','SOOS->SAME','OOO->SAME','XSX->FLIP','OSP->SAME','OSP->FLIP','PSOS->FLIP','SXOO->FLIP','O->FLIP','P->FLIP','OOO->FLIP','POX->SAME')
D2_CENTERS=(126.24642964393674,215.19172722847608,797.9643944343011)
D3_CENTERS=(210.5092412831738,609.3386806098245)

def finite(v):
    try: return math.isfinite(float(v))
    except Exception: return False

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def quantile(xs,q):
    if not xs: return None
    ys=sorted(float(x) for x in xs); pos=(len(ys)-1)*q; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return ys[lo]
    return ys[lo]*(hi-pos)+ys[hi]*(pos-lo)

def binom_upper(k,n):
    if n<=0:return None
    return sum(math.comb(n,j) for j in range(k,n+1))/(2**n)

def bh_q(items):
    vals=[(k,float(p)) for k,p in items if p is not None]
    vals.sort(key=lambda x:x[1]); m=len(vals); out={}; nxt=1.0
    for rank in range(m,0,-1):
        k,p=vals[rank-1]; q=min(nxt,p*m/rank,1.0); out[k]=q; nxt=q
    return out

def block_for(w,weeks):
    if w=='20260329':return 'held'
    i=weeks.index(w)
    if i<18:return 'train'
    if i<36:return 'era13'
    if i<48:return 'era45'
    return 'conf'

def load_lineage(*paths):
    d={}
    for path in paths:
        with gzip.open(path,'rt') as f:
            for line in f:
                r=json.loads(line)
                d[(r['week_sunday'],int(r['origin_sequence_index']))]={'depth':int(r.get('all_model_consecutive_positive_depth',0)),'elapsed':r.get('consensus_elapsed_seconds')}
    return d

def load_events(*paths):
    by=defaultdict(list)
    for path in paths:
        with gzip.open(path,'rt') as f:
            for line in f:
                r=json.loads(line); ep=r['dynamic_endpoint']; hs=(r.get('outcome',{}).get('post_endpoint_price') or {}).get('horizons',{})
                H={}
                for k in (5,10,20,30,60):
                    z=hs.get(str(k),{}); row={}
                    for m in ('signed_displacement_ticks','mfe_ticks','mae_ticks'):
                        v=z.get(m); row[m]=None if z.get('censored',False) or not finite(v) else float(v)
                    H[k]=row
                full=all(H[k][m] is not None for k in (5,10,20,30,60) for m in ('signed_displacement_ticks','mfe_ticks','mae_ticks'))
                e={'week':r['week_sunday'],'seq':int(r['sequence_index']),'t0':int(r['t0_idx']),'state':r['seed_state'],'code':CODE[r['seed_state']],
                   'pol':int(r['polarity']),'confirm':ep.get('causal_confirmation_idx'),'onset':ep.get('structural_onset_idx'),
                   'overlap':bool((r.get('link') or {}).get('next_starts_before_endpoint_confirmation')),'H':H,'full':full}
                by[e['week']].append(e)
    for w in by: by[w].sort(key=lambda e:e['seq'])
    return dict(by)

def valid(e):
    return e['confirm'] is not None and e['onset'] is not None and not e['overlap'] and int(e['confirm'])<=int(e['onset'])+5 and e['H'][5]['signed_displacement_ticks'] is not None and e['H'][60]['signed_displacement_ticks'] is not None

def pred_available(e,cur):
    return e['full'] and e['confirm'] is not None and int(e['confirm'])+60<=cur['t0']

def causal_slice(rs,start,end):
    cur=rs[end]
    return start>=0 and all(pred_available(rs[j],cur) for j in range(start,end))

def module_token(es):
    return ''.join(e['code'] for e in es)+'|'+''.join('S' if es[i]['pol']==es[i-1]['pol'] else 'F' for i in range(1,len(es)))

def context_token(rs,i,k):
    if i<k:return None
    return ''.join(rs[j]['code'] for j in range(i-k,i))+'->'+('SAME' if rs[i]['pol']==rs[i-1]['pol'] else 'FLIP')

def live_return(e,h=60):
    a=e['H'][5]['signed_displacement_ticks']; b=e['H'][h]['signed_displacement_ticks']
    return None if a is None or b is None else b-a

def occurrence_records(by,weeks,lineage):
    modules=defaultdict(list); contexts=defaultdict(list); universes=defaultdict(lambda:defaultdict(list))
    for w,rs in by.items():
        b=block_for(w,weeks)
        for i,cur in enumerate(rs):
            if not valid(cur):continue
            r60=live_return(cur,60)
            for depth in range(0,4):
                if i>=depth and causal_slice(rs,i-depth,i):universes[('ctx',depth)][w].append(r60)
            for m in (2,3,4):
                s=i-m+1
                if s<0 or not causal_slice(rs,s,i):continue
                tok=module_token(rs[s:i+1]); lin=lineage.get((w,cur['seq']),{'depth':0,'elapsed':None}); nxt=rs[i+1] if i+1<len(rs) else None
                rec={'kind':'module','pattern':tok,'m':m,'week':w,'block':b,'seq':cur['seq'],'ret60':r60,
                     'path':{str(h):live_return(cur,h) for h in (10,20,30,60)},'current_code':cur['code'],'current_pol':cur['pol'],
                     'module_elapsed_t0':cur['t0']-rs[s]['t0'],'future_depth':int(lin.get('depth') or 0),'future_elapsed':lin.get('elapsed'),
                     'availability_slack':int(cur['onset'])+5-int(cur['confirm']),
                     'pred_slack_min':min([cur['t0']-(int(rs[j]['confirm'])+60) for j in range(s,i)] or [None])}
                rec['next']={'code':nxt['code'],'rel':'S' if nxt['pol']==cur['pol'] else 'F','t0_lag':nxt['t0']-cur['t0']} if nxt is not None else None
                rec['older_code']=rs[s-1]['code'] if s>0 and pred_available(rs[s-1],cur) else None
                modules[tok].append(rec); universes[('module',m-1)][w].append(r60)
            for k in (1,2,3,4):
                s=i-k
                if s<0 or not causal_slice(rs,s,i):continue
                tok=context_token(rs,i,k); lin=lineage.get((w,cur['seq']),{'depth':0,'elapsed':None})
                rec={'kind':'context','pattern':tok,'k':k,'week':w,'block':b,'seq':cur['seq'],'ret60':r60,
                     'path':{str(h):live_return(cur,h) for h in (10,20,30,60)},'current_code':cur['code'],'current_pol':cur['pol'],
                     'context_elapsed_t0':cur['t0']-rs[s]['t0'],'future_depth':int(lin.get('depth') or 0),'future_elapsed':lin.get('elapsed'),
                     'availability_slack':int(cur['onset'])+5-int(cur['confirm']),
                     'pred_slack_min':min(cur['t0']-(int(rs[j]['confirm'])+60) for j in range(s,i)),
                     'older_code':rs[s-1]['code'] if s>0 and pred_available(rs[s-1],cur) else None}
                contexts[tok].append(rec)
    return modules,contexts,universes

def train_orientation(recs):
    xs=[r['ret60'] for r in recs if r['block']=='train']; m=mean(xs)
    if m is None or abs(m)<1e-12:return None
    return 1 if m>0 else -1

def baseline_means(universes,kind,depth): return {w:mean(xs) for w,xs in universes[(kind,depth)].items()}

def score_pattern(recs,orientation,baseline):
    cells={}; week_delta={}
    for b in BLOCKS:
        R=[r for r in recs if r['block']==b]; vals=[orientation*r['ret60'] for r in R]; deltas=[]; bywk=defaultdict(list)
        for r in R:
            base=baseline.get(r['week'])
            if base is not None:
                d=orientation*(r['ret60']-base); deltas.append(d); bywk[r['week']].append(d)
        cells[b]={'n':len(vals),'mean_oriented_ticks':mean(vals),'median_oriented_ticks':median(vals),
                  'positive_rate':sum(v>0 for v in vals)/len(vals) if vals else None,'week_demeaned_mean_ticks':mean(deltas),'weeks':len(bywk)}
        for w,xs in bywk.items():week_delta[w]=mean(xs)
    oot_w=[v for w,v in week_delta.items() if any(r['week']==w and r['block'] in OOT for r in recs)]
    p=binom_upper(sum(v>0 for v in oot_w),len(oot_w)) if oot_w else None
    return cells,p,week_delta

def family(rec):
    m=rec.get('m'); x=rec.get('module_elapsed_t0')
    if x is None or x<=0:return None
    centers=D2_CENTERS if m==3 else D3_CENTERS if m==4 else None
    if not centers:return None
    j=min(range(len(centers)),key=lambda z:abs(math.log(x)-math.log(centers[z])))
    return ('short','middle','long')[j] if len(centers)==3 else ('short','long')[j]

def seeded_patterns(modules,contexts):
    out=[]
    for p in PAIR_SEEDS+TRIPLET_SEEDS:
        if p in modules:out.append(('module',p,modules[p]))
    for p in CONTEXT_SEEDS:
        if p in contexts:out.append(('context',p,contexts[p]))
    return out

def lane_continuation(modules,contexts,universes):
    ans=[]
    for kind,p,recs in seeded_patterns(modules,contexts):
        ori=train_orientation(recs)
        if ori is None:continue
        depth=(recs[0].get('m',1)-1) if kind=='module' else recs[0].get('k',0); base=baseline_means(universes,'module' if kind=='module' else 'ctx',depth)
        cells,pv,_=score_pattern(recs,ori,base); blocks={}
        for b in BLOCKS:
            R=[r for r in recs if r['block']==b]; nxt=Counter((r['next']['code']+r['next']['rel']) for r in R if r.get('next')) if kind=='module' else Counter()
            blocks[b]={'n':len(R),'extend_d1_rate':sum(r['future_depth']>=1 for r in R)/len(R) if R else None,
                       'extend_d2_rate':sum(r['future_depth']>=2 for r in R)/len(R) if R else None,
                       'extend_d3_rate':sum(r['future_depth']>=3 for r in R)/len(R) if R else None,
                       'median_future_elapsed':median([r['future_elapsed'] for r in R if finite(r['future_elapsed'])]),'top_next':nxt.most_common(8)}
        ans.append({'kind':kind,'pattern':p,'orientation':'WITH_CURRENT' if ori==1 else 'AGAINST_CURRENT','outcome_blocks':cells,'oot_week_sign_p':pv,'continuation_blocks':blocks})
    return ans

def lane_chainmap(modules):
    out=[]
    for p in sorted(set(PAIR_SEEDS+TRIPLET_SEEDS)):
        recs=modules.get(p,[])
        if not recs:continue
        B={}
        for b in BLOCKS:
            R=[r for r in recs if r['block']==b]; nxt=Counter(); terminal=0
            for r in R:
                if r['future_depth']<=0:terminal+=1
                if r.get('next') and r['future_depth']>=1:nxt[r['next']['code']+'|'+r['next']['rel']]+=1
            B[b]={'n':len(R),'strict_terminal_rate':terminal/len(R) if R else None,'strict_successors':nxt.most_common(12)}
        out.append({'pattern':p,'blocks':B})
    return out

def lane_timing(modules):
    out=[]
    for p,recs in modules.items():
        m=recs[0]['m'] if recs else None
        if m not in (3,4):continue
        fam=defaultdict(lambda:defaultdict(list))
        for r in recs:
            f=family(r)
            if f:fam[r['block']][f].append(r)
        if sum(len(fam[b][f]) for b in OOT for f in fam[b])<20:continue
        cells={}
        for b in BLOCKS:
            cells[b]={}
            for f,R in fam[b].items():cells[b][f]={'n':len(R),'mean_signed_ret60':mean([r['ret60'] for r in R]),'extend_d1_rate':sum(r['future_depth']>=1 for r in R)/len(R) if R else None}
        out.append({'pattern':p,'m':m,'assignment':'nearest_frozen_log_center_characterization_only','cells':cells})
    out.sort(key=lambda z:sum(v['n'] for b in OOT for v in z['cells'][b].values()),reverse=True)
    return out[:100]

def lane_decompose(modules,contexts,universes):
    out=[]
    for kind,p,recs in seeded_patterns(modules,contexts):
        ori=train_orientation(recs)
        if ori is None:continue
        depth=(recs[0].get('m',1)-1) if kind=='module' else recs[0].get('k',0); base=baseline_means(universes,'module' if kind=='module' else 'ctx',depth)
        cells,pv,_=score_pattern(recs,ori,base); sign_change=any((cells[b]['mean_oriented_ticks'] is not None and cells[b]['mean_oriented_ticks']<0) for b in OOT+('held',))
        loss=[r for r in recs if ori*r['ret60']<0]; win=[r for r in recs if ori*r['ret60']>=0]; older={}
        for code in ('S','O','P','X',None):
            W=[r for r in win if r.get('older_code')==code]; L=[r for r in loss if r.get('older_code')==code]
            if W or L:older[str(code)]={'true_n':len(W),'false_n':len(L),'true_mean':mean([ori*r['ret60'] for r in W]),'false_mean':mean([ori*r['ret60'] for r in L])}
        tf=defaultdict(lambda:{'true':0,'false':0,'rets':[]})
        for r in recs:
            f=family(r) if kind=='module' else None; key=f or 'unclassified'; tf[key]['true' if ori*r['ret60']>=0 else 'false']+=1; tf[key]['rets'].append(ori*r['ret60'])
        timing={k:{'true_n':v['true'],'false_n':v['false'],'mean':mean(v['rets'])} for k,v in tf.items()}
        out.append({'kind':kind,'pattern':p,'orientation':'WITH_CURRENT' if ori==1 else 'AGAINST_CURRENT','sign_change_present':sign_change,'oot_week_sign_p':pv,
                    'blocks':cells,'older_ancestry_split':older,'timing_split':timing,'policy':'FLAG_AND_DECOMPOSE_NOT_AUTO_KILL'})
    return out

def lane_systematic(modules,contexts,universes):
    cand=[]
    for kind,D in (('module',modules),('context',contexts)):
        for p,recs in D.items():
            train=[r for r in recs if r['block']=='train']; complexity=(recs[0].get('m') or recs[0].get('k')+1); floor={2:30,3:20,4:12,5:8}.get(complexity,12)
            if len(train)<floor:continue
            ori=train_orientation(recs)
            if ori is None:continue
            depth=(recs[0].get('m',1)-1) if kind=='module' else recs[0].get('k',0); base=baseline_means(universes,'module' if kind=='module' else 'ctx',depth)
            cells,pv,_=score_pattern(recs,ori,base); minreq={'era13':max(6,floor//2),'era45':max(4,floor//3),'conf':max(2,floor//6)}
            eligible=all(cells[b]['n']>=minreq[b] for b in OOT); stable=eligible and all((cells[b]['mean_oriented_ticks'] or -999)>0 and (cells[b]['week_demeaned_mean_ticks'] or -999)>0 for b in OOT)
            cand.append({'kind':kind,'pattern':p,'complexity':complexity,'orientation':'WITH_CURRENT' if ori==1 else 'AGAINST_CURRENT','train_n':len(train),
                         'eligible':eligible,'stable_preheld_oot':stable,'oot_week_sign_p':pv,'blocks':cells})
    q=bh_q([(f"{c['kind']}:{c['pattern']}",c['oot_week_sign_p']) for c in cand if c['eligible']])
    for c in cand:c['oot_week_sign_q_bh']=q.get(f"{c['kind']}:{c['pattern']}")
    cand.sort(key=lambda c:(c['stable_preheld_oot'], -(c['oot_week_sign_q_bh'] if c['oot_week_sign_q_bh'] is not None else 1), sum(c['blocks'][b]['n'] for b in OOT)),reverse=True)
    return {'candidate_count':len(cand),'stable_count':sum(c['stable_preheld_oot'] for c in cand),'candidates':cand[:250],
            'selection_boundary':'pattern support and orientation fixed from first 18 train weeks; later blocks used for validation. Prior Phase-2 surfacing still makes named patterns historically contaminated, so fresh prospective evidence remains required for promotion.'}

def lane_execution(modules,contexts,universes):
    out=[]
    for kind,p,recs in seeded_patterns(modules,contexts):
        ori=train_orientation(recs)
        if ori is None:continue
        depth=(recs[0].get('m',1)-1) if kind=='module' else recs[0].get('k',0); base=baseline_means(universes,'module' if kind=='module' else 'ctx',depth)
        cells,pv,_=score_pattern(recs,ori,base); path={}
        for b in BLOCKS:
            R=[r for r in recs if r['block']==b]
            path[b]={'n':len(R),'mean_oriented_by_horizon':{str(h):mean([ori*r['path'][str(h)] for r in R if r['path'][str(h)] is not None]) for h in (10,20,30,60)},
                     'cost_stress_mean_h60':{str(cost):mean([ori*r['ret60']-cost for r in R]) for cost in (0.5,1.0,2.0)}}
        out.append({'kind':kind,'pattern':p,'orientation':'WITH_CURRENT' if ori==1 else 'AGAINST_CURRENT',
                    'causal_trigger':'all predecessor h=60 information available before current t0; current frozen detector identity confirmed no later than structural onset+5',
                    'entry_reference':'current structural endpoint+5','exit_reference':'current structural endpoint+60','management_optimization_performed':False,
                    'oot_week_sign_p':pv,'blocks':cells,'path_and_cost_stress':path,'status':'HISTORICAL_STRATEGY_CANDIDATE_REQUIRES_FRESH_PROSPECTIVE_BEFORE_FREEZE'})
    return out

def lane_redteam(modules,contexts,universes):
    out=[]
    for kind,p,recs in seeded_patterns(modules,contexts):
        ori=train_orientation(recs)
        if ori is None:continue
        depth=(recs[0].get('m',1)-1) if kind=='module' else recs[0].get('k',0); base=baseline_means(universes,'module' if kind=='module' else 'ctx',depth)
        cells,pv,week_delta=score_pattern(recs,ori,base); ootweeks={w:v for w,v in week_delta.items() if any(r['week']==w and r['block'] in OOT for r in recs)}
        allR=[r for r in recs if r['block'] in OOT]; bywk=defaultdict(list)
        for r in allR:bywk[r['week']].append(ori*r['ret60'])
        loo=[]
        for w in bywk:
            xs=[x for ww,v in bywk.items() if ww!=w for x in v]
            if xs:loo.append(mean(xs))
        total_abs=sum(abs(sum(v)) for v in bywk.values()); max_share=max([abs(sum(v))/total_abs for v in bywk.values()],default=None) if total_abs else None
        out.append({'kind':kind,'pattern':p,'orientation':'WITH_CURRENT' if ori==1 else 'AGAINST_CURRENT','oot_week_sign_p':pv,
                    'min_oot_block_mean':min([cells[b]['mean_oriented_ticks'] for b in OOT if cells[b]['mean_oriented_ticks'] is not None],default=None),
                    'leave_one_week_out_min_mean':min(loo) if loo else None,'max_abs_week_contribution_share':max_share,
                    'positive_oot_week_fraction':sum(v>0 for v in ootweeks.values())/len(ootweeks) if ootweeks else None,
                    'held_mean':cells['held']['mean_oriented_ticks'],'policy':'FAILURES_PRESERVED_FLAG_AND_DECOMPOSE'})
    return out

def lane_causality(modules,contexts):
    out=[]
    for kind,p,recs in seeded_patterns(modules,contexts):
        sl=[r['availability_slack'] for r in recs if r['availability_slack'] is not None]; ps=[r['pred_slack_min'] for r in recs if r['pred_slack_min'] is not None]
        out.append({'kind':kind,'pattern':p,'n':len(recs),
                    'current_identity_entry_slack_seconds':{'min':min(sl) if sl else None,'median':median(sl),'p25':quantile(sl,.25),'p75':quantile(sl,.75)},
                    'predecessor_h60_availability_before_current_t0_seconds':{'min':min(ps) if ps else None,'median':median(ps),'p25':quantile(ps,.25),'p75':quantile(ps,.75)},
                    'causal_contract_passed_all_occurrences':all((r['availability_slack'] is not None and r['availability_slack']>=0 and r['pred_slack_min'] is not None and r['pred_slack_min']>=0) for r in recs)})
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',required=True,choices=['continuation','chainmap','timing','decompose','systematic','execution','redteam','causality'])
    ap.add_argument('--base',required=True);ap.add_argument('--held',required=True);ap.add_argument('--base-lineage',required=True);ap.add_argument('--held-lineage',required=True);ap.add_argument('--summary',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args(); weeks=json.load(open(a.summary))['weeks']; lineage=load_lineage(a.base_lineage,a.held_lineage); by=load_events(a.base,a.held)
    modules,contexts,universes=occurrence_records(by,weeks,lineage)
    funcs={'continuation':lane_continuation,'chainmap':lane_chainmap,'timing':lane_timing,'decompose':lane_decompose,'systematic':lane_systematic,'execution':lane_execution,'redteam':lane_redteam,'causality':lane_causality}
    if a.mode in ('continuation','decompose','systematic','execution','redteam'):res=funcs[a.mode](modules,contexts,universes)
    elif a.mode=='causality':res=funcs[a.mode](modules,contexts)
    else:res=funcs[a.mode](modules)
    out={'status':'POST_PHASE2_PARALLEL_AGENT_COMPLETE','mode':a.mode,'source_policy':'FROZEN_55W_CHARACTERIZATION_INPUTS_NO_RETUNE','result':res,
         'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False},
         'promotion_performed':False}
    Path(a.out).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
