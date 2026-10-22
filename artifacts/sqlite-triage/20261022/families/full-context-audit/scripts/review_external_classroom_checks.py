"""Keep the reproduced external claims and all adverse sensitivities visible."""
import collections
import csv
import hashlib
import json
import os
import pathlib

STEPS = ['same_direction','opposite_direction','left_moved_only','right_moved_only','neither_moved']


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'external-classroom-audit-v1'
    assert not (out/'external_contradiction_review_receipt.json').exists()
    rows=list(csv.DictReader((out/'external_pair_checks.csv').open()))
    lookup={(r['left'],r['right'],r['precision'],r['period'],r['method']):r for r in rows}
    claims=list(csv.DictReader((out/'external_classroom_claim_checks.csv').open()))
    flags=[]
    for claim in claims:
        a,b=claim['left'],claim['right']
        def row(precision='classroom_float32',period='all_retained',method='source_compressed_present'):
            return lookup[(a,b,precision,period,method)]
        source=row();raw=row(precision='raw_native_float64')
        strict=row(method='consecutive_completed_groups_same_instrument')
        quarters=[row(period='elapsed_quarter_'+str(q)) for q in range(1,5)]
        reasons=[]
        if source['endpoint_step_disagreement']=='true':reasons.append('endpoint_vs_step_direction')
        if any(source[k]!=raw[k] for k in STEPS):reasons.append('native_float32_vs_raw_step_counts')
        if source['step_dominance_relation']!=strict['step_dominance_relation']:reasons.append('missing_group_bridge_sensitivity')
        directions={r['step_dominance_relation'] for r in quarters}
        if {'SAME_DIRECTION','OPPOSITE_DIRECTION'}<=directions:reasons.append('chronological_step_direction_reversal')
        if source['endpoint_relation']!=source['both_present_endpoint_relation']:reasons.append('individual_vs_matched_endpoint_support')
        for kind in reasons:
            identity='external-classroom-v1|'+a+'|'+b+'|'+kind
            flags.append(dict(research_id='exdr-'+hashlib.sha256(identity.encode()).hexdigest()[:20],
                finding_id=claim['finding_id'],left=a,right=b,kind=kind,research_status='open',
                answer_1_json=json.dumps(source,sort_keys=True),
                answer_2_json=json.dumps(dict(raw_native_precision=raw,adjacent_groups=strict,quarters=quarters),sort_keys=True),
                scientific_question='Distinguish endpoint versus path, missing-group bridging, chronology, precision and matched support; retain all answers and validate on independent days.'))
    with (out/'external_contradiction_research_registry.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(flags[0]));w.writeheader();w.writerows(flags)
    receipt=dict(schema='EXTERNAL_CLASSROOM_CONTRADICTION_REVIEW_V1',status='complete',coverage_gate='NOT_PASSED',
        claims_checked=len(claims),claims_reproduced=sum(r['status']=='reproduced_descriptive_claim' for r in claims),
        open_flags=len(flags),flag_counts=dict(collections.Counter(r['kind'] for r in flags)),
        interpretation='Counts overlap. Reproduction preserves the hypotheses; it does not establish causal, prospective or tradable effects.',
        limitations=['Pearson floating reduction is not claimed bit-identical to the original OpenBLAS-32 kernel.',
                     'Additional quarter/precision/adjacency checks cover the 441 filed pairs; original definitions cover all 2040 external pairs.',
                     'Expanded historical source alignment, knowledge review, structured checks and v4 inputs remain separate outstanding work.'])
    (out/'external_contradiction_review_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
