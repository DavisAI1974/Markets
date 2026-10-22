"""Source-defined episode/path checks and exact emission/cursor availability.

Reference math: native_dipole.py and native_recognition.py at canonical 2ebb8ce8.
Execution checkout identity is recorded separately; this does not execute it.
"""
import bisect
import collections
import csv
import gzip
import hashlib
import json
import os
import pathlib
import sqlite3


def stage_bin(index):
    assert type(index) is int and index>=0
    if index==0:return 0,0
    low=1<<(index.bit_length()-1)
    return low,2*low-1


def lawful(row,cutoff,cursor_cap,instrument):
    return row['known_by_ns']<=cutoff and row['input_cursor']<=cursor_cap and row['instrument_id']==instrument


def check_path(path,emission):
    stages=path['stages'];assert stages and path['stage_count']==len(stages)
    previous=None;reversals=[];zero=0
    for index,s in enumerate(stages):
        assert s['stage_index']==index and s['runway_id']==path['runway_id']
        assert s['orientation']==path['orientation'] and s['recv_ns']<=emission
        if index:assert s['recv_ns']>=stages[index-1]['recv_ns']
        flow=s['signed_flow'];direction='LONG' if flow>0 else 'SHORT' if flow<0 else 'NO_DIRECTION'
        assert s['direction']==direction and s['magnitude']==abs(flow)
        total=s['bid_depth']+s['ask_depth']
        assert s['normalized_imbalance']==((s['bid_depth']-s['ask_depth'])/total if total else None)
        low,high=stage_bin(index)
        assert (s['stage_bin'],s['stage_bin_first_index'],s['stage_bin_last_index'])==(f'STAGE_{low}_{high}',low,high)
        if flow==0:zero+=1;continue
        if previous is not None and previous!=direction:
            reversals.append(dict(stage_index=index,recv_ns=s['recv_ns'],from_direction=previous,to_direction=direction))
        previous=direction
    assert path['orientation'] in ['SAME','FLIP']
    assert path['sign_reversals']==reversals and path['sign_reversal_count']==len(reversals)
    assert path['persisted']==(not reversals)
    assert path['inflection_recv_ns']==(reversals[0]['recv_ns'] if reversals else None)
    assert path['price_coupling_raw']==stages[-1]['price_raw']-stages[0]['price_raw']
    return dict(stage_count=len(stages),zero_flow_stages=zero,nonzero_flow_stages=len(stages)-zero,
                sign_reversals=len(reversals),price_coupling_raw=path['price_coupling_raw'],
                duration_ns=stages[-1]['recv_ns']-stages[0]['recv_ns'])


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'episode-path-audit-v1';out.mkdir(exist_ok=True)
    target=out/'lifecycle_asof.sqlite';assert not target.exists()
    db=sqlite3.connect(target)
    db.executescript('''CREATE TABLE record(record_sha256 TEXT PRIMARY KEY,section TEXT,known_by_ns INTEGER,
        input_cursor INTEGER,instrument_id INTEGER,source_file TEXT,source_line INTEGER,row_json TEXT);
        CREATE TABLE context(sample_id TEXT,lag_s INTEGER,family_id TEXT,instrument_id INTEGER,cutoff_ns INTEGER,cursor_cap INTEGER,
        PRIMARY KEY(sample_id,lag_s));''')
    rows_by_section=collections.defaultdict(list);episodes=collections.defaultdict(list);counts=collections.Counter();seen=set()
    source_files=[base/'enriched-v2/lifecycle_original_rows.jsonl.gz',base/'full-context-audit/supplemental_lifecycle_payloads.jsonl.gz']
    full_rows=[];lineages=[];detectors=[]
    for source in source_files:
        with gzip.open(source,'rt') as f:
            for line_number,line in enumerate(f):
                wrapper=json.loads(line);row=wrapper['row']
                text=json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)
                digest=hashlib.sha256(text.encode()).hexdigest()
                if digest in seen:continue
                seen.add(digest);em=row['frankie_emission'];section=row['emitting_section']
                known=max(em['ts_recv_ns'],row.get('emitted_at_recv_ns') or 0)
                linked=dict(known_by_ns=known,input_cursor=em['input_cursor'],instrument_id=em['instrument_id'])
                db.execute('INSERT INTO record VALUES (?,?,?,?,?,?,?,?)',
                    (digest,section,known,em['input_cursor'],em['instrument_id'],str(source),line_number,text))
                rows_by_section[(section,em['instrument_id'])].append((known,em['input_cursor']))
                counts[section]+=1
                if section=='episode':episodes[row['candidate_id']].append((row,linked,digest))
                if section=='lineage':
                    entered=row['entered_recv_ns'];exited=row.get('exited_recv_ns')
                    assert entered<=known and (exited is None or entered<=exited<=known)
                    assert row.get('stage_duration_ns')==(None if exited is None else exited-entered)
                    lineages.append((row,linked,digest))
                if section=='detector_coverage':detectors.append((row,linked,digest))
    flags=[];checks=[];stage_total=0
    for candidate,records in sorted(episodes.items()):
        short=[r for r in records if 'recognition_outcome' in r[0]]
        full=[r for r in records if 'recognition' in r[0]]
        assert len(short)==len(full)==1,(candidate,len(short),len(full))
        summary,opening,opening_sha=short[0];row,emission,closing_sha=full[0]
        r=row['recognition'];c=row['candidate'];path=row.get('dipole')
        assert candidate==c['candidate_id']==r['candidate_id']
        birth=c['event_second']*10**9;available=c['available_second']*10**9
        assert summary['birth_recv_ns']==r['birth_recv_ns']==birth
        assert c['detection_lag_seconds']==c['available_second']-c['event_second']
        assert summary['recognition_outcome']==r['outcome']
        recognized=r['recognized_recv_ns'];lead=None if recognized is None else birth-recognized
        assert r['lead_ns']==lead
        if recognized is not None:
            assert r['outcome']==('PRIOR' if recognized<birth else 'T0' if recognized==birth else 'H+N')
            assert recognized<=opening['known_by_ns']<=emission['known_by_ns']
        if r['recognized_recv_ns_basis']=='AVAILABLE_SECOND_BIN':assert recognized==available
        assert summary['recognized_recv_ns']==recognized
        assert r['failed_state_count']==len(r['failed_states'])
        assert row['orientation']==summary['orientation']
        if path is None:
            assert row['dipole_path_withheld'] and row['orientation']=='NO_PREDECESSOR' and row['stage_count']==0
            result=dict(stage_count=0,zero_flow_stages=0,nonzero_flow_stages=0,sign_reversals=None,price_coupling_raw=None,duration_ns=None)
        else:
            result=check_path(path,emission['known_by_ns']);assert row['stage_count']==result['stage_count']
            stage_total+=result['stage_count']
        checks.append(dict(candidate_id=candidate,family_id=r['family_id'],continuity_segment=c['continuity_segment'],
            orientation=row['orientation'],terminal_phase=row['terminal_phase'],recognition_outcome=r['outcome'],
            birth_ns=birth,recognition_ns=recognized,recognition_basis=r['recognized_recv_ns_basis'],source_lead_ns=lead,
            opening_emission_ns=opening['known_by_ns'],complete_path_emission_ns=emission['known_by_ns'],
            actual_opening_emission_delay_ns=opening['known_by_ns']-birth,
            failed_states=r['failed_state_count'],opening_sha256=opening_sha,complete_sha256=closing_sha,**result))
        if path is not None and path['stages'][0]['recv_ns']<available:
            flags.append(dict(kind='stage_zero_event_stamp_precedes_candidate_availability',candidate_id=candidate,
                source_answer=path['stages'][0]['recv_ns'],availability_answer=available,research_status='open',
                question='Stage zero is stamped at candidate event birth by the adapter; verify which book/flow instant its caller supplied. Never treat it as a pre-availability predictor.'))
    for row,linked,digest in detectors:
        counters=row['detector_counters']
        parts=['seconds_in_warmup','seconds_without_finite_flow','rejected_zero_magnitude','rejected_below_threshold',
               'rejected_not_local_max','rejected_in_refractory','rejected_in_refractory_at_release','suppressed_by_prominence',
               'candidates_emitted','candidates_pending_in_window']
        assert counters['seconds_judged']==sum(counters.get(k,0) for k in parts)
        assert row['partition_identity_holds'] and row['reconciled_with_detector']
    samples={r['sample_id']:r for r in csv.DictReader((base/'joint-inputs-v3/model_sample_master.csv').open())}
    contexts=list(csv.DictReader((base/'descriptive-v1/group_context_receipts.csv').open()))
    indices={}
    for key,values in rows_by_section.items():
        ordered=sorted(values);times=[r[0] for r in ordered];cursors=[r[1] for r in ordered]
        assert all(a<=b for a,b in zip(cursors,cursors[1:])),key
        indices[key]=(times,cursors)
    alignment=[]
    for context in contexts:
        sample=samples[context['sample_id']];cutoff=int(context['cutoff_ns']);cap=int(sample['cursor_cap']);instrument=int(sample['instrument_id'])
        db.execute('INSERT INTO context VALUES (?,?,?,?,?,?)',(context['sample_id'],int(context['lag_s']),sample['family_id'],instrument,cutoff,cap))
        for (section,inst),(times,cursors) in indices.items():
            if inst!=instrument:continue
            eligible=min(bisect.bisect_right(times,cutoff),bisect.bisect_right(cursors,cap))
            alignment.append(dict(sample_id=context['sample_id'],lag_s=context['lag_s'],family_id=sample['family_id'],
                instrument_id=instrument,cutoff_ns=cutoff,cursor_cap=cap,section=section,eligible_emitted_records=eligible,
                source_records=len(times),disposition='emission_and_cursor_guard; full rows retained in SQL view'))
    db.executescript('''CREATE INDEX record_guard ON record(instrument_id,known_by_ns,input_cursor,section);
        CREATE VIEW lawful_context_records AS SELECT c.sample_id,c.lag_s,c.family_id,c.cutoff_ns,c.cursor_cap,r.*
          FROM context c JOIN record r ON r.instrument_id=c.instrument_id AND r.known_by_ns<=c.cutoff_ns AND r.input_cursor<=c.cursor_cap;''')
    db.commit();db.close()
    def write(name,rows):
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['status']);w.writeheader();w.writerows(rows)
    write('complete_episode_path_checks.csv',checks);write('lifecycle_context_availability.csv',alignment)
    write('episode_path_research_registry.csv',flags)
    report=dict(schema='COMPLETE_EPISODE_PATH_AND_EMISSION_AUDIT_V1',status='complete',coverage_gate='NOT_PASSED',
        source_records_by_section=dict(counts),episode_records=counts['episode'],distinct_candidates=len(episodes),
        complete_paths=sum(r['stage_count']>0 for r in checks),withheld_no_predecessor=sum(r['stage_count']==0 for r in checks),
        path_stages=stage_total,context_rows=len(contexts),families=len({r['family_id'] for r in alignment}),
        detector_partition_checks=len(detectors),open_research_flags=len(flags),
        limitations=['1726 episode records represent opening and complete records for 863 candidates, not 1726 independent candidates.',
          'Path checks reproduce declared arithmetic; stage-zero book/flow sourcing is separately flagged, not assumed contemporaneous at birth.',
          'Every complete path is available only at its actual full-row emission. STREAM_END/SEGMENT_CLOSE facts are never moved earlier.',
          'Stage-index octaves do not establish event-phase labels; event phases and model-input roles still require consumer accounting.',
          'No v4 matrix or model fit is asserted.'])
    (out/'episode_path_check_receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
