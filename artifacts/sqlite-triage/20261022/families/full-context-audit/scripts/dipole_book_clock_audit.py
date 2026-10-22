"""Compare retained stage books, caller-assigned groups and strictly past books.

Only exact selected native offsets are read. Canonical caller definitions are a
reference hypothesis, not an assertion about the separate execution checkout.
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
from audit_full_context_sources import Indexed

NS=10**9
FIELDS=('bid_depth','ask_depth','bid_order_count','ask_order_count','bid_level_count','ask_level_count','price_raw')


def select_books(groups,stage_ns,opening_cursor=None):
    """groups sorted by (receive, cursor, ordinal), within one continuity scope."""
    clocks=[g[0] for g in groups]
    past=bisect.bisect_right(clocks,stage_ns)-1
    if opening_cursor is not None:
        matches=[i for i,g in enumerate(groups) if g[1]==opening_cursor]
        if len(matches)!=1:raise ValueError('opening cursor is not unique in scope')
        producer=matches[0]
    else:
        producer=bisect.bisect_left(clocks,(stage_ns//NS+1)*NS)
        # The stream close advances outstanding seconds with the last book.
        producer=min(producer,len(groups)-1)
    return (groups[past] if past>=0 else None),groups[producer]


def book_values(book):
    source=('bid_depth_full','ask_depth_full','bid_order_count_full','ask_order_count_full',
            'bid_price_level_count_full','ask_price_level_count_full')
    values=[int(book.get(k) or 0) for k in source]
    mid=book.get('mid');values.append(0 if mid is None else int(round(float(mid)*NS)))
    return dict(zip(FIELDS,values))


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'dipole-book-clock-audit-v1';out.mkdir(exist_ok=True)
    db=sqlite3.connect('file:'+str(base/'alignment.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    life=sqlite3.connect('file:'+str(base/'episode-path-audit-v1/lifecycle_asof.sqlite')+'?mode=ro',uri=True)
    rows=[json.loads(t[0]) for t in life.execute("SELECT row_json FROM record WHERE section='episode'")]
    opening={r['candidate_id']:r for r in rows if 'recognition_outcome' in r}
    coverage=[json.loads(t[0]) for t in life.execute("SELECT row_json FROM record WHERE section='detector_coverage'")]
    assert {r['candidate']['continuity_segment'] for r in rows if r.get('dipole')}=={19648}
    boundary=[r for r in coverage if r['continuity_segment']==19647][0]['frankie_emission']['input_cursor']
    # The current group triggers the segment transition before candidate advancement.
    groups=[tuple(r) for r in db.execute('SELECT recv_ns,input_cursor,source_ordinal FROM group_event WHERE instrument_id=150611 AND input_cursor>=? ORDER BY recv_ns,input_cursor,source_ordinal',(boundary,))]
    bycursor={g[1]:i for i,g in enumerate(groups)};clocks=[g[0] for g in groups]
    selected=set();stages=[]
    for row in rows:
        path=row.get('dipole')
        if not path:continue
        for stage in path['stages']:
            stamp=stage['recv_ns'];past_i=bisect.bisect_right(clocks,stamp)-1
            producer_i=bycursor[opening[row['candidate_id']]['frankie_emission']['input_cursor']] if stage['stage_index']==0 else min(bisect.bisect_left(clocks,(stamp//NS+1)*NS),len(groups)-1)
            past=groups[past_i] if past_i>=0 else None;producer=groups[producer_i]
            selected.add(producer[2])
            if past:selected.add(past[2])
            stages.append((row['candidate_id'],row['candidate']['continuity_segment'],stage,past,producer))
    plan=dict(schema='DIPOLE_BOOK_CLOCK_COORDINATE_PLAN_V1',stages=len(stages),selected_native_ordinals=len(selected),
        source_scope=dict(instrument_id=150611,continuity_segment=19648,first_cursor=boundary),
        producer_rule='Stage zero uses opening emission cursor; later stages use first complete group in a later receive second, or last group for stream close.',
        past_rule='Last complete same-instrument, same-continuity-scope group with receive <= stage bin timestamp; no future fill.')
    (out/'coordinate_plan.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan),flush=True)
    if os.environ.get('PLAN_ONLY')=='1':return
    target=out/'native_book_coordinates.jsonl.gz';assert not target.exists()
    books={};cached=0;read_bytes=0
    with gzip.open(base/'full-context-audit/indexed-payloads/native.member.jsonl.gz','rt') as f:
        for line in f:
            w=json.loads(line);ordinal=w['source_ordinal']
            if ordinal in selected:
                books[ordinal]=(book_values(w['row']['book_full']),{k:w[k] for k in ['source_offset','source_length','row_sha256']});cached+=1
    pin=dict(db.execute("SELECT * FROM source_registry WHERE name='native.member'").fetchone());ix=Indexed(pin)
    with gzip.open(target,'wt',compresslevel=1) as f:
        for n,ordinal in enumerate(sorted(selected),1):
            if ordinal not in books:
                raw,offset=ix.read(ordinal);w=json.loads(raw);read_bytes+=len(raw)
                books[ordinal]=(book_values(w['book_full']),dict(source_offset=offset,source_length=len(raw),row_sha256=hashlib.sha256(raw).hexdigest()))
                em=w['frankie_emission'];g=db.execute('SELECT recv_ns,input_cursor,instrument_id FROM group_event WHERE source_ordinal=?',(ordinal,)).fetchone()
                assert (em['ts_recv_ns'],em['input_cursor'],em['instrument_id'])==tuple(g)
            values,provenance=books[ordinal]
            f.write(json.dumps(dict(source_ordinal=ordinal,source_path=pin['path'],**provenance,book=values),separators=(',',':'))+'\n')
            if n%2000==0:print('Selected native stage books',n,len(selected),flush=True)
    ix.close();counts=collections.Counter();couplings=collections.defaultdict(list)
    with gzip.open(out/'stage_book_comparisons.jsonl.gz','wt',compresslevel=1) as f:
        for candidate,segment,stage,past,producer in stages:
            pv=books[producer[2]][0];av=books[past[2]][0] if past else None
            original={k:stage[k] for k in FIELDS};mismatch=[k for k in FIELDS if original[k]!=pv[k]]
            changes=[k for k in FIELDS if av is not None and original[k]!=av[k]]
            counts['stages']+=1;counts['producer_hypothesis_mismatch_stages']+=bool(mismatch)
            counts['producer_after_stage_bin']+=producer[0]>stage['recv_ns'];counts['no_past_book']+=past is None
            counts['source_vs_past_book_changed_stages']+=bool(changes);counts['source_vs_past_mid_changed_stages']+='price_raw' in changes
            if stage['stage_index']==0:counts['stage_zero']+=1
            couplings[candidate].append((stage['stage_index'],original['price_raw'],None if av is None else av['price_raw']))
            f.write(json.dumps(dict(candidate_id=candidate,continuity_segment=segment,stage_index=stage['stage_index'],stage_bin_ns=stage['recv_ns'],
                original_book=original,reference_producer_group=producer,reference_producer_book=pv,producer_mismatch_fields=mismatch,
                lawful_past_group=past,lawful_past_book=av,past_book_age_ns=None if past is None else stage['recv_ns']-past[0],
                changed_fields=changes),separators=(',',':'))+'\n')
    with (out/'coupling_comparisons.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['candidate_id','source_coupling_raw','lawful_past_coupling_raw','state'])
        for candidate,values in sorted(couplings.items()):
            values.sort();source=values[-1][1]-values[0][1]
            lawful=None if values[0][2] is None or values[-1][2] is None else values[-1][2]-values[0][2]
            w.writerow([candidate,source,lawful,'NO_PAST_BOOK' if lawful is None else 'CHANGED' if source!=lawful else 'SAME'])
            counts['coupling_changed_paths']+=lawful is not None and source!=lawful
    receipt=dict(status='complete',coverage_gate='NOT_PASSED',**plan,
        counts=dict(counts),native_cached_coordinates=cached,new_exact_indexed_bytes=read_bytes,
        interpretation='Producer assignment is compared against canonical definition reference and retained payloads. Actual execution checkout identity stays separate. Past-book comparison is a scientific alternative, not a replacement for frozen source evidence.',
        limitations=['A second-bin label is not an exact book observation clock. Completed-second flow is also only available later.',
          'Couplings compare midpoint price units, not executable bid/ask returns, fees or fills.',
          'No continuous FIFO survival, extra market days, v4 matrix or fit is established.'])
    # Keep one schema key after merging the coordinate plan.
    receipt['schema']='DIPOLE_BOOK_CLOCK_AUDIT_V1'
    (out/'book_clock_audit_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
