#!/usr/bin/env python3
from __future__ import annotations
import json, math
from collections import Counter
from pathlib import Path

ROOT=Path('research/generated/ng_exhaustion_postphase2_agents_20260818')

def load(mode):
    p=ROOT/f'NG_EXHAUSTION_POSTPHASE2_{mode.upper()}_AGENT_20260818.json'
    return json.loads(p.read_text())['result']

def bypat(rows): return {(r['kind'],r['pattern']):r for r in rows}
def pos(v): return v is not None and v>0

def main():
    execution=load('execution'); continuation=load('continuation'); decompose=load('decompose'); redteam=load('redteam'); causality=load('causality')
    systematic=load('systematic'); timing=load('timing'); chainmap=load('chainmap')
    E=bypat(execution); C=bypat(continuation); D=bypat(decompose); R=bypat(redteam); K=bypat(causality)
    seeded=[]
    for key,e in E.items():
        blocks=e['blocks']; oot=('era13','era45','conf')
        stable=all(pos(blocks[b]['mean_oriented_ticks']) and pos(blocks[b]['week_demeaned_mean_ticks']) for b in oot)
        cost05=all(pos(e['path_and_cost_stress'][b]['cost_stress_mean_h60']['0.5']) for b in oot)
        cost10=all(pos(e['path_and_cost_stress'][b]['cost_stress_mean_h60']['1.0']) for b in oot)
        rt=R.get(key,{}); causal=K.get(key,{}).get('causal_contract_passed_all_occurrences',False)
        loo=rt.get('leave_one_week_out_min_mean'); loo_pass=pos(loo)
        held=blocks['held']; held_nonneg=held['n']==0 or held['mean_oriented_ticks'] is not None and held['mean_oriented_ticks']>=0
        if not stable: grade='FAIL_HISTORICAL_STABILITY'
        elif not causal: grade='FAIL_CAUSAL_CONTRACT'
        elif not loo_pass: grade='INVESTIGATOR_REDTEAM_FRAGILE'
        elif cost05 and held_nonneg: grade='A_HISTORICAL_CANDIDATE'
        elif held_nonneg: grade='B_HISTORICAL_CANDIDATE_COST_SENSITIVE'
        else: grade='INVESTIGATOR_HELD_SIGN_CHANGE'
        c=C.get(key,{}); d=D.get(key,{})
        seeded.append({
            'kind':key[0],'pattern':key[1],'orientation':e['orientation'],'grade':grade,'stable_preheld_oot':stable,
            'oot_week_sign_p':e['oot_week_sign_p'],'causal_contract_passed':causal,'leave_one_week_out_min_mean':loo,
            'max_abs_week_contribution_share':rt.get('max_abs_week_contribution_share'),'positive_oot_week_fraction':rt.get('positive_oot_week_fraction'),
            'cost_stress_all_oot_positive':{'0.5_tick':cost05,'1.0_tick':cost10},
            'blocks':{b:{'n':blocks[b]['n'],'mean':blocks[b]['mean_oriented_ticks'],'week_delta':blocks[b]['week_demeaned_mean_ticks'],'positive_rate':blocks[b]['positive_rate']} for b in ('train','era13','era45','conf','held')},
            'path_means':{b:e['path_and_cost_stress'][b]['mean_oriented_by_horizon'] for b in oot+('held',)},
            'continuation':c.get('continuation_blocks'),'decomposition_sign_change':d.get('sign_change_present'),'older_ancestry_split':d.get('older_ancestry_split')
        })
    order={'A_HISTORICAL_CANDIDATE':5,'B_HISTORICAL_CANDIDATE_COST_SENSITIVE':4,'INVESTIGATOR_HELD_SIGN_CHANGE':3,'INVESTIGATOR_REDTEAM_FRAGILE':2,'FAIL_CAUSAL_CONTRACT':1,'FAIL_HISTORICAL_STABILITY':0}
    seeded.sort(key=lambda x:(order[x['grade']], -(x['oot_week_sign_p'] if x['oot_week_sign_p'] is not None else 1)),reverse=True)

    scands=systematic['candidates']
    fdr=[c for c in scands if c['stable_preheld_oot'] and c.get('oot_week_sign_q_bh') is not None and c['oot_week_sign_q_bh']<=0.05]
    fdr.sort(key=lambda c:(c['oot_week_sign_q_bh'],-sum(c['blocks'][b]['n'] for b in ('era13','era45','conf'))))
    top=[]
    for c in fdr[:50]:
        top.append({'kind':c['kind'],'pattern':c['pattern'],'orientation':c['orientation'],'q_bh':c['oot_week_sign_q_bh'],'p':c['oot_week_sign_p'],
                    'train_n':c['train_n'],'oot_n':sum(c['blocks'][b]['n'] for b in ('era13','era45','conf')),
                    'means':{b:c['blocks'][b]['mean_oriented_ticks'] for b in ('era13','era45','conf','held')},
                    'week_deltas':{b:c['blocks'][b]['week_demeaned_mean_ticks'] for b in ('era13','era45','conf','held')}})
    sys_summary={'candidate_count':systematic['candidate_count'],'stable_count':systematic['stable_count'],'stable_fdr_q05_count':len(fdr),
                 'fdr_q05_by_kind':dict(Counter(c['kind'] for c in fdr)),'top_fdr_candidates':top,'selection_boundary':systematic['selection_boundary']}

    named={'PPP|SS','PPX|SS','OOO|FF','PPS|SS','POP|SF'}
    trows=[]
    for t in timing:
        support=sum(v['n'] for b in ('era13','era45','conf') for v in t['cells'][b].values())
        if t['pattern'] in named or len(trows)<20:trows.append({'pattern':t['pattern'],'m':t['m'],'oot_support':support,'cells':t['cells']})
    trows.sort(key=lambda x:x['oot_support'],reverse=True)

    out={
      'status':'POST_PHASE2_AGENT_RECONCILIATION_COMPLETE','promotion_performed':False,
      'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False},
      'seeded_candidate_scorecards':seeded,'grade_counts':dict(Counter(x['grade'] for x in seeded)),
      'systematic_atlas':sys_summary,'timing_summary':{'pattern_count':len(timing),'top_or_named':trows[:35]},'chainmap':chainmap,
      'interpretive_boundaries':[
        'named Phase-2 patterns are historically contaminated and cannot be called fresh prospective evidence',
        '0.5/1.0 tick cost stress is sensitivity analysis, not an estimate of actual all-in trading cost',
        'timing-family assignment uses frozen characterization centers and is not a live cutoff',
        'future_depth and successor identity are outcomes for research, never live inputs before causal availability',
        'failed and held-sign-change cases remain investigator evidence under FLAG_AND_DECOMPOSE_NOT_AUTO_KILL'
      ]
    }
    (ROOT/'RECONCILED_SUMMARY.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
