"""Read full ROOT contexts, prove aliases, and recover order-update ages by ID."""
import collections
import csv
import gzip
import hashlib
import itertools
import json
import os
import pathlib
from full_context_measurements import Measurements,number


def root_measurements(frame,structure,native):
    out=Measurements();checks=collections.Counter()
    known=frame['ts_recv_ns']
    assert known==native['frankie_emission']['ts_recv_ns']
    assert frame['input_cursor']==native['frankie_emission']['input_cursor']
    orders={r['order_id']:r for r in frame['observation']['orders']}
    assert len(orders)==len(frame['observation']['orders'])
    visited=set()
    for side,label in [('bid','B'),('ask','A')]:
        levels=frame['book'][side+'_levels_full']
        other=native['book_full'][side+'_levels_full']
        assert levels==other,('full_ROOT_native_level_alias',side)
        observation=frame['observation']['levels'][label]
        assert len(observation)==len(levels)
        for rank,(level,index) in enumerate(zip(levels,observation),1):
            assert index['price_raw']==level['price_raw']
            assert index['order_ids']==[o['order_id'] for o in level['fifo_queue']]
            checks['full_depth_level_aliases']+=1
            for position,queued in enumerate(level['fifo_queue'],1):
                oid=queued['order_id'];assert oid not in visited;visited.add(oid)
                order=orders[oid]
                assert order['price_raw']==level['price_raw'] and order['side']==label
                for field in ['size','priority_recv_ns','priority_sequence']:assert order[field]==queued[field],field
                checks['order_identity_matches']+=1
                update=order['last_update_recv_ns'];valid=type(update) is int and update<=known
                checks['future_last_update_clocks']+=type(update) is int and update>known
                prefix=f'root_full.book.{side}.rank{rank}.fifo_position{position}'
                out.add(prefix+'.last_update_age_ns',known-update if valid else None,'nanoseconds_age',
                        'observation.orders[].last_update_recv_ns linked by order_id to book FIFO position')
                out.category(prefix+'.last_update_clock_state','PRESENT' if valid else 'INVALID_OR_FUTURE_SOURCE_CLOCK',
                             'observation.orders[].last_update_recv_ns')
    assert visited==set(orders)
    # Reconcile raw DBN/native messages before treating their market fields as aliases.
    records=frame['input_records'];raw=native['raw_actions'];inner=frame['native_frame']['raw_actions']
    assert len(records)==len(raw)==len(inner)
    for slot,(record,action,adapter) in enumerate(zip(records,raw,inner),1):
        for key in ['action','side','size','order_id','instrument_id','publisher_id','channel_id','sequence','flags']:
            assert record[key]==action[key]==adapter[key],('ROOT_message_alias',key)
        for source,key in [('price','price_raw'),('ts_event','ts_event_ns'),('ts_recv','ts_recv_ns'),('ts_in_delta','ts_in_delta_ns')]:
            assert record[source]==action[key]==adapter[key],('ROOT_clock_price_alias',key)
        checks['ordered_raw_message_aliases']+=1
        out.category(f'root_full.raw_message.slot{slot}.rtype',record.get('rtype'),'input_records[].rtype')
    out.counts(frame.get('activity',{}),'root_full.activity','activity')
    for key in ['transition']:
        if key in frame:out.category('root_full.'+key,frame[key],key)
    for key in ['action_string','side_string','terminal_action','terminal_side']:
        if key in structure:out.category('root_full.structure.'+key,structure[key],key)
    for key in ['component_count','distinct_order_id_count','distinct_price_count']:
        if key in structure:out.add('root_full.structure.'+key,structure[key],'count',key)
    for key in ['action_counts','side_counts','fill_disposition_signature']:
        out.counts(structure.get(key,{}),'root_full.structure.'+key,key)
    for key in ['price_raw_min','price_raw_max','price_raw_span']:
        if key in structure:
            value=structure[key]
            out.add('root_full.structure.'+key.removesuffix('_raw').replace('_raw_','_'),value/1e9 if number(value) else None,
                    'price_units',key)
    for key,value in structure.get('mirror',{}).items():
        if key!='mirror_pair_key':out.category('root_full.structure.mirror.'+key,value,'mirror.'+key)
    if 'fill_disposition' in structure:
        fill=structure['fill_disposition']
        if 'class' in fill:out.category('root_full.structure.fill_disposition.class',fill['class'],'fill_disposition.class')
        if 'signature' in fill:
            assert fill['signature']==structure['fill_disposition_signature']
            checks['fill_signature_aliases']+=1
    return out,dict(checks)


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'joint-inputs-v4';audit=base/'full-context-audit/indexed-payloads'
    target=out/'root_full_context_values.jsonl.gz';assert not target.exists()
    registry={};finite=collections.Counter();nulls=collections.Counter();vocabulary=collections.defaultdict(set)
    totals=collections.Counter();rows=0
    with gzip.open(audit/'root.frames.jsonl.gz','rt') as rf,gzip.open(audit/'root.structures.jsonl.gz','rt') as sf, \
         gzip.open(audit/'native.member.jsonl.gz','rt') as nf,gzip.open(target,'wt',compresslevel=1) as output:
        for root_line,structure_line,native_line in itertools.zip_longest(rf,sf,nf):
            assert root_line is not None and structure_line is not None and native_line is not None
            rw,sw,nw=map(json.loads,[root_line,structure_line,native_line])
            assert rw['source_ordinal']==sw['source_ordinal']==nw['source_ordinal']
            m,checks=root_measurements(rw['row'],sw['row'],nw['row']);totals.update(checks)
            for name,unit in m.units.items():
                spec=(unit,m.source_paths[name],'numeric' if name in m.numeric else 'categorical')
                if name in registry:assert registry[name]==spec
                else:registry[name]=spec
            for name,value in m.numeric.items():(nulls if value is None else finite)[name]+=1
            for name,value in m.categories.items():vocabulary[name].add(value)
            output.write(json.dumps(dict(source_ordinal=rw['source_ordinal'],input_cursor=rw['row']['input_cursor'],
                known_by_ns=rw['row']['ts_recv_ns'],root_row_sha256=rw['row_sha256'],structure_row_sha256=sw['row_sha256'],
                numeric=m.numeric,categories=m.categories,checks=checks),separators=(',',':'),allow_nan=False)+'\n')
            rows+=1
            if rows%1000==0:print('Full ROOT identity-linked contexts',rows,flush=True)
    assert rows==6265
    with (out/'root_full_feature_registry.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['feature','unit','source_path','kind','finite_unique_records','null_unique_records','observed_categories'])
        for name,(unit,path,kind) in sorted(registry.items()):w.writerow([name,unit,path,kind,finite[name],nulls[name],len(vocabulary.get(name,()))])
    (out/'root_full_category_vocabulary.json').write_text(json.dumps({k:sorted(v) for k,v in sorted(vocabulary.items())},indent=2)+'\n')
    report=dict(schema='ROOT_FULL_CONTEXT_EXTRACTION_V1',status='complete',coverage_gate='NOT_PASSED',unique_records=rows,
        identity_and_alias_checks=dict(totals),numeric_fields=sum(r[2]=='numeric' for r in registry.values()),
        categorical_fields=sum(r[2]=='categorical' for r in registry.values()),
        saved_bytes=target.stat().st_size,saved_sha256=hashlib.file_digest(target.open('rb'),'sha256').hexdigest(),
        limitations=['Identity checks reconcile each complete snapshot; they do not establish unobserved between-context survival or true order birth.',
                     'Clock-invalid update ages remain unavailable with an independent state; no negative age or zero fill is invented.',
                     'Full books, raw message clocks/IDs/wire bytes and discovery/family linkage remain in indexed source provenance.',
                     'Registry aliases and existing v3 numeric values still require frozen-matrix value/unit reconciliation. No model fit is asserted.'])
    (out/'root_full_extraction_receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
