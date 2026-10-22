"""Check whether activity-since changes compare the same source anchor."""
import collections
import csv
import gzip
import json
import os
import pathlib
from summarize_layer_review import write


def main():
    b=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=b/'joint-inputs-v3'
    with gzip.open(b/'enriched-v2/native_quality_contexts.jsonl.gz','rt') as f:
        quality={r['source_ordinal']:r['quality'] for r in map(json.loads,f)}
    with (b/'descriptive-v1/group_context_receipts.csv').open() as f:
        contexts={(r['sample_id'],int(r['lag_s'])):r for r in csv.DictReader(f)}
    with (b/'joint-inputs-v2/model_sample_master.csv').open() as f:samples=list(csv.DictReader(f))
    rows=[]
    for s in samples:
        if s['phase'] not in ['before_start','near_before','near_after']:continue
        c=contexts[(s['sample_id'],0)]
        historical_sid=s['sample_id'].split(':')[0]+':onset' if s['phase']=='before_start' else s['sample_id']
        for lag in [120,300,600]:
            a=contexts[(historical_sid,lag)]
            qa,qc=quality[int(a['source_ordinal'])],quality[int(c['source_ordinal'])]
            for anchor in ['last_book_reset','last_f_last_same_side','last_touch_change','last_trade','session_open']:
                ha,ca=qa['activity_anchor_quality'][anchor],qc['activity_anchor_quality'][anchor]
                signature=lambda x:tuple(x.get(k) for k in ['anchor_basis','anchor_event_ns','anchor_recv_ns','anchor_sequence'])
                changed=signature(ha)!=signature(ca)
                valid_event=ha.get('anchor_event_ns') is not None and ca.get('anchor_event_ns') is not None
                valid_recv=ha.get('anchor_recv_ns') is not None and ca.get('anchor_recv_ns') is not None
                rows.append(dict(sample_id=s['sample_id'],family_id=s['family_id'],phase=s['phase'],lag_s=lag,anchor=anchor,
                    historical_ordinal=a['source_ordinal'],current_ordinal=c['source_ordinal'],
                    historical_known_by_ns=a['known_by_ns'],current_known_by_ns=c['known_by_ns'],
                    historical_age_s=a['age_s'],current_age_s=c['age_s'],anchor_changed=changed,
                    both_event_anchors_available=valid_event,both_receive_anchors_available=valid_recv,
                    continuity_segment_changed=qa.get('continuity_segment')!=qc.get('continuity_segment'),
                    historical_basis=ha.get('anchor_basis'),current_basis=ca.get('anchor_basis'),
                    disposition='different_anchors;delta_not_a_cumulative_flow_increment' if changed else
                        'same_anchor_with_source_measurement_missingness' if not(valid_event and valid_recv) else 'same_observed_anchor'))
    write(out/'counter_anchor_context_audit.csv',rows)
    groups=collections.defaultdict(list)
    for r in rows:groups[(r['phase'],r['lag_s'],r['anchor'])].append(r)
    summary=[]
    for key,rs in sorted(groups.items()):
        summary.append(dict(phase=key[0],lag_s=key[1],anchor=key[2],master_n=len(rs),
            changed_anchor_n=sum(r['anchor_changed'] for r in rs),
            event_anchor_unavailable_n=sum(not r['both_event_anchors_available'] for r in rs),
            receive_anchor_unavailable_n=sum(not r['both_receive_anchors_available'] for r in rs),
            continuity_segment_changed_n=sum(r['continuity_segment_changed'] for r in rs)))
    write(out/'counter_anchor_summary.csv',summary)
    result={'rows':len(rows),'changed_anchor_rows':sum(r['anchor_changed'] for r in rows),
        'continuity_segment_changed_rows':sum(r['continuity_segment_changed'] for r in rows),
        'meaning':'Raw differences remain valid differences of named source state; a counter delta across different anchors is not net order flow or a rate. Source anchors and dispositions stay provenance; no anchor repair or future backfill.',
        'by_anchor':{a:{'n':len(rs),'changed':sum(r['anchor_changed'] for r in rs)} for a,rs in
            ((a,[r for r in rows if r['anchor']==a]) for a in sorted({r['anchor'] for r in rows}))}}
    (out/'counter_anchor_receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
