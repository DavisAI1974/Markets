"""Source-rule phase reconstruction, separately labelled from stored stage fields."""
import collections
import csv
import gzip
import json
import os
import pathlib
import sqlite3


def phases(stages,candidate_polarity,persist_seconds=3):
    if persist_seconds<1:raise ValueError('positive persistence required')
    current='BIRTH';persistent=False;opposite=0;out=[]
    for index,stage in enumerate(stages):
        if index:
            flow=stage['signed_flow'];polarity=1 if flow>0 else -1 if flow<0 else 0
            opposed=polarity!=0 and polarity!=candidate_polarity
            opposite=opposite+1 if opposed else 0
            if not opposed and not persistent:current='PERSISTENCE';persistent=True
            if opposite>=persist_seconds:current='REVERSAL'
        out.append(current)
        if current=='REVERSAL' and index!=len(stages)-1:raise ValueError('stages continue after source reversal')
    return out


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'dipole-event-phase-audit-v1';out.mkdir(exist_ok=True)
    target=out/'reconstructed_stage_phases.csv.gz';assert not target.exists()
    db=sqlite3.connect('file:'+str(base/'episode-path-audit-v1/lifecycle_asof.sqlite')+'?mode=ro',uri=True)
    counts=collections.Counter();strata=collections.Counter();termini=collections.Counter()
    fields=['candidate_id','family_id','continuity_segment','session_phase','orientation','stage_index','stage_bin',
        'reconstructed_event_phase','stage_bin_ns','full_row_known_by_ns','full_row_input_cursor','full_row_sha256','phase_basis']
    with gzip.open(target,'wt',newline='',compresslevel=1) as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for sha,known,cursor,text in db.execute("SELECT record_sha256,known_by_ns,input_cursor,row_json FROM record WHERE section='episode'"):
            row=json.loads(text)
            if not row.get('dipole'):continue
            c=row['candidate'];p=row['dipole'];r=row['recognition'];stages=p['stages'];labels=phases(stages,c['polarity'])
            terminal=row['terminal_phase'];termini[terminal]+=1
            if terminal=='REVERSAL':assert labels[-1]=='REVERSAL'
            elif terminal=='CENSORED_AT_OBSERVATION_END':assert labels[-1]!='REVERSAL'
            else:raise ValueError(('unreviewed terminal phase',terminal))
            for s,label in zip(stages,labels):
                assert known>=s['recv_ns']
                counts[label]+=1;strata[(p['orientation'],r['session_phase'],label,s['stage_bin'])]+=1
                writer.writerow(dict(candidate_id=c['candidate_id'],family_id=r['family_id'],continuity_segment=c['continuity_segment'],
                    session_phase=r['session_phase'],orientation=p['orientation'],stage_index=s['stage_index'],stage_bin=s['stage_bin'],
                    reconstructed_event_phase=label,stage_bin_ns=s['recv_ns'],full_row_known_by_ns=known,full_row_input_cursor=cursor,
                    full_row_sha256=sha,phase_basis='CANONICAL_CALLER_RECONSTRUCTION_NOT_STORED_STAGE_FIELD'))
    with (out/'phase_stage_bin_counts.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['orientation','session_phase','event_phase','stage_bin','stages'])
        for key,count in sorted(strata.items()):w.writerow([*key,count])
    receipt=dict(schema='DIPOLE_EVENT_PHASE_RECONSTRUCTION_V1',status='complete',coverage_gate='NOT_PASSED',
        phase_counts=dict(counts),terminal_path_counts=dict(termini),paths=sum(termini.values()),stages=sum(counts.values()),
        basis='Canonical native_candidate_adapter at 2ebb8ce8: decide phase before observing stage; persistence threshold three opposite completed seconds.',
        assumptions=['Polarity sign agrees with the absolute classified buy-minus-sell lots, as the source roll20 denominator is nonnegative; no-volume has zero signed lots and no direction.',
          'The canonical persistence default is three; separate execution-parameter byte identity remains an open provenance check.'],
        rules=['Stage zero is BIRTH. A non-opposed completed second starts PERSISTENCE once. The third consecutive opposed completed second is REVERSAL and terminates.',
          'Censoring is a terminal observation boundary, not a fabricated reversal stage.',
          'Actual full-row emission/cursor availability is retained on every reconstructed stage. No terminal phase is backfilled to earlier stages.',
          'Event phase stays separate from orientation, session phase and octave stage-index bin.'],
        limitations=['Reconstructed labels are explicitly distinguished from directly stored stage fields.',
          'These are retrospective path diagnostics available only with their retained source rows, not newly emitted real-time signals.',
          'Family, orientation and phase strata are retained; no pooled across-phase causal effect or tradable signal is asserted.'])
    (out/'event_phase_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
