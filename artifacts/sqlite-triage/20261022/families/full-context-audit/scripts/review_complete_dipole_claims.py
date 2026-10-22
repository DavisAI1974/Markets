"""Check actual Frankie pair claims and retain disagreements as research items."""
import csv
import hashlib
import json
import os
import pathlib
import re

STEPS=['same_direction','opposite_direction','left_moved_only','right_moved_only','neither_moved']


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    audit=base/'dipole-audit-v1';knowledge=base/'full-context-audit/runtime-knowledge'
    rows=list(csv.DictReader((audit/'complete_pair_checks.csv').open()))
    full={(r['left'],r['right'],r['precision'],r['method']):r for r in rows if r['period']=='all_retained'}
    def pair(left,right,precision='classroom_float32',method='source_compressed_present'):
        if (left,right,precision,method) in full:return full[(left,right,precision,method)],False
        return full[(right,left,precision,method)],True
    claims=json.loads((knowledge/'native_classroom_claims.json').read_text());checks=[];flags=[]
    for claim in claims:
        refs=[r for r in claim.get('evidence_refs',[]) if r.get('kind')=='DIPOLE_RELATIONSHIP']
        for ref in refs:
            left,right=ref['left'],ref['right'];r,swap=pair(left,right)
            m=re.search(r'co-movement steps (\{.*\})',ref.get('reasoning',''))
            expected=json.loads(m.group(1)) if m else None
            got={k:int(r[k]) for k in STEPS}
            if swap:got['left_moved_only'],got['right_moved_only']=got['right_moved_only'],got['left_moved_only']
            er=re.search(r'Dipole relation (SAME_DIRECTION|OPPOSITE_DIRECTION|UNRESOLVED)',ref.get('reasoning',''))
            declared=er.group(1) if er else None
            reproduced=expected is not None and expected==got and declared==r['endpoint_relation']
            raw,_=pair(left,right,'raw_float64');strict,_=pair(left,right,method='consecutive_completed_groups_same_instrument')
            checks.append(dict(finding_id=claim['finding_id'],finding_hash=claim.get('finding_hash'),left=left,right=right,
                status='reproduced_descriptive_claim' if reproduced else 'not_fully_reproduced',
                claimed_endpoint_relation=declared,actual_endpoint_relation=r['endpoint_relation'],
                claimed_steps_json=json.dumps(expected,sort_keys=True),actual_steps_json=json.dumps(got,sort_keys=True),
                both_present=int(r['present_overlap']),pearson=r['pearson'],
                missing_group_bridges=int(r['nonconsecutive_group_transitions']),
                strict_same=int(strict['same_direction']),strict_opposite=int(strict['opposite_direction']),
                raw_same=int(raw['same_direction']),raw_opposite=int(raw['opposite_direction']),
                research_status='open',interpretation='Endpoint direction and step dominance answer distinct questions; retain both. No market prediction or causality established.'))
    for (left,right,precision,method),r in full.items():
        if precision!='classroom_float32' or method!='source_compressed_present':continue
        raw,_=pair(left,right,'raw_float64');strict,_=pair(left,right,method='consecutive_completed_groups_same_instrument')
        reasons=[]
        if r['endpoint_step_disagreement']=='true':reasons.append('endpoint_vs_step_direction')
        if any(r[k]!=raw[k] for k in STEPS):reasons.append('float32_vs_raw_step_counts')
        if r['step_dominance_relation']!=strict['step_dominance_relation']:reasons.append('missing_group_bridge_sensitivity')
        qs={q['step_dominance_relation'] for q in rows if q['left']==left and q['right']==right and q['precision']==precision and q['method']==method and q['period']!='all_retained'}
        if 'SAME_DIRECTION' in qs and 'OPPOSITE_DIRECTION' in qs:reasons.append('chronological_step_direction_reversal')
        if r['endpoint_relation']!=r['both_present_endpoint_relation']:reasons.append('individual_vs_matched_endpoint_support')
        for kind in reasons:
            identity='dipole-v1|'+left+'|'+right+'|'+kind
            flags.append(dict(research_id='dr-'+hashlib.sha256(identity.encode()).hexdigest()[:20],kind=kind,left=left,right=right,
                answer_1=json.dumps(r,sort_keys=True),answer_2=json.dumps(dict(raw=raw,consecutive_group_sensitivity=strict,quarter_step_directions=sorted(qs)),sort_keys=True),
                research_status='open',evidence='complete_pair_checks.csv; complete_pair_state_counts.csv',
                scientific_question='Does the difference follow from endpoints versus path, unavailable-state bridging, source float32 quantization, chronology, or a physical mechanism? Resolve with matched scopes and independent days; do not choose a winning answer.'))
    def save(name,rs):
        with (audit/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rs[0]) if rs else ['status']);w.writeheader();w.writerows(rs)
    save('native_classroom_claim_checks.csv',checks);save('dipole_contradiction_research_registry.csv',flags)
    external=json.loads((knowledge/'external_classroom_claims.json').read_text())
    save('external_classroom_claim_dispositions.csv',[dict(finding_id=r['finding_id'],status='pending_full_dimensional_external_reconstruction',research_status='open',premise=r['premise']) for r in external])
    receipt=dict(status='complete_native_pair_claim_review',native_claims=len(claims),checked_native_relationship_refs=len(checks),
        reproduced=sum(r['status']=='reproduced_descriptive_claim' for r in checks),not_fully_reproduced=sum(r['status']!='reproduced_descriptive_claim' for r in checks),
        external_claims_retained=len(external),external_claims_rechecked=0,open_research_flags=len(flags),
        flag_counts={k:sum(r['kind']==k for r in flags) for k in sorted({r['kind'] for r in flags})},
        coverage_gate='NOT_PASSED',limitations=['Claims and flags overlap and are not independent discoveries.','This review does not complete full-99-plane fitted-input coverage.'])
    (audit/'classroom_claim_review_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))


if __name__=='__main__':main()
