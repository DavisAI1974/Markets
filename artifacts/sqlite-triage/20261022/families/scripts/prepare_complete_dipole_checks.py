"""All retained second-set components for source-defined pairwise checks.

The classroom uses float32 component values; also retain raw float64 values so
rounding effects can be measured separately. No data is fitted by this script.
"""
import collections
import hashlib
import json
import math
import os
import pathlib
import sqlite3
import struct


def component_row(raw,names):
    assert set(raw)==set(names)
    values=[];states=[]
    for name in names:
        c=raw[name];v=c['value'];s=c['state']
        assert s in [0,1,2,3] and math.isfinite(v)
        if s!=0:assert v==0, (name,s,v)
        values.append(v);states.append(s)
    return values,states


def validate_wire_components(wanted,names,packed_values,states):
    got=struct.unpack('<'+str(len(names))+'f',packed_values)
    for k,name in enumerate(names):
        # The public ledger spells unavailable values null; tensor/raw storage
        # uses zero plus an independent state. Neither is an observed zero.
        expected=got[k] if states[k]==0 else None
        assert wanted[k]['name']==name and wanted[k]['value']==expected, (k,name,wanted[k],expected)
        assert wanted[k]['state']==['PRESENT','MISSING','INVALID','ABLATED'][states[k]]


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'dipole-audit-v1';out.mkdir(exist_ok=True)
    assert not (out/'components-f32.bin').exists()
    db=sqlite3.connect('file:'+str(base/'alignment.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    names=list(json.loads(db.execute('SELECT raw_components_json FROM second_set_clock ORDER BY input_cursor LIMIT 1').fetchone()[0]))
    assert len(names)==19
    groupmap={r['input_cursor']:r['source_ordinal'] for r in db.execute('SELECT input_cursor,source_ordinal FROM group_event')}
    counts=collections.Counter();reason_counts=collections.Counter();n=0;checks=[]
    f32=out/'components-f32.bin';f64=out/'raw-components-f64.bin';st=out/'states-u8.bin';cl=out/'clocks-i64.bin'
    pointpath='/opt/frankie-box/work/experiment-teacher-rows/20231018/host-dipole-classroom-source.c15.rows.jsonl'
    with f32.open('wb') as a,f64.open('wb') as b,st.open('wb') as c,cl.open('wb') as d,open(pointpath,'rb') as source:
        previous_cursor=-1
        for r in db.execute('SELECT * FROM second_set_clock ORDER BY input_cursor'):
            raw=json.loads(r['raw_components_json']);values,states=component_row(raw,names)
            assert r['input_cursor']>previous_cursor;previous_cursor=r['input_cursor']
            v32=struct.pack('<19f',*values)
            a.write(v32);b.write(struct.pack('<19d',*values));c.write(bytes(states))
            clocks=[r[k] for k in ['input_cursor','instrument_id','event_ns','receive_ns','known_by_ns']]
            clocks += [groupmap.get(r['input_cursor'],-1),r['source_offset']]
            assert all(isinstance(x,int) for x in clocks)
            d.write(struct.pack('<7q',*clocks))
            for name,s in zip(names,states):
                counts[(name,s)]+=1;reason_counts[(name,str(raw[name].get('reason')))]+=1
            if n%25000==0:
                source.seek(r['source_offset']);wire=source.read(r['source_length'])
                assert hashlib.sha256(wire).hexdigest()==r['row_sha256']
                j=json.loads(wire)
                validate_wire_components(j['components'],names,v32,states)
                checks.append(dict(input_cursor=r['input_cursor'],source_offset=r['source_offset'],row_sha256=r['row_sha256']))
            n+=1
            if n%100000==0:print('second-set component rows',n,flush=True)
    report=dict(schema='COMPLETE_SECOND_SET_DIPOLE_AUDIT_INPUT_V1',status='complete',rows=n,names=names,
        values_order='row-major; little-endian',component_state_names=['PRESENT','MISSING','INVALID','ABLATED'],
        clock_names=['input_cursor','instrument_id','event_ns','receive_ns','known_by_ns','group_ordinal_or_minus_one','source_offset'],
        files=[dict(name=p.name,bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()) for p in [f32,f64,st,cl]],
        state_counts={name:{str(s):counts[(name,s)] for s in range(4)} for name in names},
        reason_counts={name:{reason:v for (key,reason),v in reason_counts.items() if key==name} for name in names},
        exact_source_float32_component_checks=checks,
        limits=['These are source-defined descriptive pair checks, not model fits or predictive validation.',
                'Raw reason/incomplete structures remain in the pinned database and full indexed context payloads.'])
    (out/'complete_component_input_receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k in ['status','rows','names','files']}),flush=True)


if __name__=='__main__':main()
