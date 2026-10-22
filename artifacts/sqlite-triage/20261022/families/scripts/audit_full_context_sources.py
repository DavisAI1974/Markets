"""Inventory complete indexed context payloads, retaining ordered raw evidence.

No fitted-model coverage credit is inferred from reading or retaining a source.
No broad recovery scan, new restoration, source rewriting or future backfill.
"""
import collections
import csv
import gzip
import hashlib
import json
import math
import os
import pathlib
import sqlite3
import struct
from family_clock_sources import unpack


def leaves(obj, path=''):
    """Wildcard list paths for schema inventory; full values stay in raw payloads."""
    if isinstance(obj, dict):
        if not obj:
            yield path, obj
        for key, value in obj.items():
            yield from leaves(value, path+'.'+str(key) if path else str(key))
    elif isinstance(obj, list):
        if not obj:
            yield path, obj
        for value in obj:
            yield from leaves(value, path+'[]')
    else:
        yield path, obj


class Inventory:
    def __init__(self):
        self.rows = {}
        self.sources = collections.Counter()

    def add(self, source, obj):
        self.sources[source] += 1
        for path, value in leaves(obj):
            key = (source, path)
            if key not in self.rows:
                self.rows[key] = dict(types=collections.Counter(), records=0, observations=0,
                                      finite=0, minimum=None, maximum=None)
            r = self.rows[key]
            r['types'][type(value).__name__] += 1
            r['observations'] += 1
            if isinstance(value, (float,int)) and not isinstance(value,bool) and math.isfinite(value):
                r['finite'] += 1
                r['minimum'] = value if r['minimum'] is None else min(r['minimum'],value)
                r['maximum'] = value if r['maximum'] is None else max(r['maximum'],value)

    def write(self, path):
        fields = ['source','field_path','source_record_count','observations','type_counts_json',
                  'finite_numeric_observations','minimum','maximum','model_consumption_status']
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for (source,p),r in sorted(self.rows.items()):
                w.writerow(dict(source=source,field_path=p,source_record_count=self.sources[source],
                    observations=r['observations'],type_counts_json=json.dumps(r['types'],sort_keys=True),
                    finite_numeric_observations=r['finite'],minimum=r['minimum'],maximum=r['maximum'],
                    model_consumption_status='pending_explicit_semantic_mapping'))


class Indexed:
    def __init__(self,pin):
        self.pin=pin
        self.fd=os.open(pin['path'],os.O_RDONLY);self.ix=os.open(pin['offset_index'],os.O_RDONLY)
        with open(pin['offset_index'],'rb') as f:
            header=json.loads(f.readline());self.head=f.tell()
        assert header['byteorder']=='little'

    def read(self,ordinal):
        pair=os.pread(self.ix,16,self.head+8*ordinal)
        assert len(pair)==16
        lo,hi=struct.unpack('<QQ',pair)
        raw=os.pread(self.fd,hi-lo,lo);assert len(raw)==hi-lo
        return raw,lo

    def close(self):
        os.close(self.fd);os.close(self.ix)


def validate_context(context,sample,known,cursor,instrument):
    assert known==int(context['known_by_ns'])
    assert cursor==int(context['input_cursor'])
    assert known<=int(context['cutoff_ns'])
    assert cursor<=int(sample['cursor_cap'])
    assert instrument==int(sample['instrument_id'])


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'full-context-audit';out.mkdir(exist_ok=True)
    payload=out/'indexed-payloads';payload.mkdir(exist_ok=True)
    assert not (out/'field_inventory_receipt.json').exists(), 'completed audit is immutable'
    db=sqlite3.connect('file:'+str(base/'alignment.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    pins={r['name']:dict(r) for r in db.execute('SELECT * FROM source_registry')}
    samples={r['sample_id']:r for r in csv.DictReader((base/'joint-inputs-v3/model_sample_master.csv').open())}
    contexts=list(csv.DictReader((base/'descriptive-v1/group_context_receipts.csv').open()))
    byordinal=collections.defaultdict(list)
    for c in contexts:byordinal[int(c['source_ordinal'])].append(c)
    inventory=Inventory();receipts=[];byte_counts=collections.Counter()
    for name in ['native.member','root.frames','root.structures']:
        ix=Indexed(pins[name]);dst=payload/(name+'.jsonl.gz')
        assert not dst.exists(), str(dst)
        with gzip.open(dst,'wt',compresslevel=1) as output:
            for n,(ordinal,cs) in enumerate(sorted(byordinal.items()),1):
                raw,offset=ix.read(ordinal);obj=json.loads(raw)
                if name.startswith('root.'):obj=unpack(obj)
                if name=='native.member':
                    em=obj['frankie_emission']
                    for c in cs:validate_context(c,samples[c['sample_id']],int(em['ts_recv_ns']),int(em['input_cursor']),int(obj['instrument_id']))
                inventory.add(name,obj);byte_counts[name]+=len(raw)
                row=dict(source=name,source_ordinal=ordinal,source_offset=offset,source_length=len(raw),
                         row_sha256=hashlib.sha256(raw).hexdigest(),context_count=len(cs))
                output.write(json.dumps(dict(**row,row=obj),separators=(',',':'))+'\n');receipts.append(row)
                if n%1000==0:print(name,n,len(byordinal),flush=True)
        ix.close()
    offsets=sorted({int(c['source_offset']) for c in contexts})
    path='/opt/frankie-box/work/experiment-teacher-rows/20231018/host-dipole-classroom-source.c15.rows.jsonl'
    with open(path,'rb') as f,gzip.open(payload/'second_set.jsonl.gz','wt',compresslevel=1) as output:
        for n,offset in enumerate(offsets,1):
            r=dict(db.execute('SELECT * FROM second_set_clock WHERE source_offset=?',(offset,)).fetchone())
            f.seek(offset);raw=f.read(r['source_length'])
            assert len(raw)==r['source_length'] and hashlib.sha256(raw).hexdigest()==r['row_sha256']
            obj=json.loads(raw)
            assert obj['key']['input_cursor']==r['input_cursor']
            assert obj['clocks']['clock_event_known_by']==r['known_by_ns']
            inventory.add('second_set',obj);byte_counts['second_set']+=len(raw)
            row=dict(source='second_set',source_offset=offset,source_length=len(raw),row_sha256=r['row_sha256'],
                     input_cursor=r['input_cursor'],known_by_ns=r['known_by_ns'],instrument_id=r['instrument_id'])
            output.write(json.dumps(dict(**row,row=obj),separators=(',',':'))+'\n');receipts.append(row)
            if n%1000==0:print('second_set',n,len(offsets),flush=True)
    with gzip.open(base/'enriched-v2/lifecycle_original_rows.jsonl.gz','rt') as f:
        for line in f:
            j=json.loads(line);inventory.add('lifecycle.'+str(j['row'].get('emitting_section')),j['row'])
    for r in db.execute('SELECT * FROM external_row ORDER BY point_name,source_ordinal'):
        inventory.add('external.'+r['point_name'],json.loads(r['row_json']))
    inventory.write(out/'complete_field_inventory.csv')
    with gzip.open(out/'indexed_source_receipts.jsonl.gz','wt',compresslevel=1) as f:
        for r in receipts:f.write(json.dumps(r,separators=(',',':'))+'\n')
    report=dict(schema='FULL_CONTEXT_FIELD_INVENTORY_V1',status='complete',coverage_gate='NOT_PASSED',
        scope='All complete payload fields at the existing 10486 selected contexts, all cached linked lifecycle rows, and every retained external row; not a whole-raw-ledger schema census.',
        source_records=dict(inventory.sources),field_paths=len(inventory.rows),selected_contexts=len(contexts),
        unique_native_ordinals=len(byordinal),source_bytes_read=dict(byte_counts),pins=pins,
        remaining=['Map every inventoried field to a semantic consumer, provenance role or documented unavailable/excluded state.',
                   'Apply actual knowledge definitions/claims with source-bound scientific checks.',
                   'Complete numerical and structured extraction, then verify runtime coverage before v4 fits.'])
    (out/'field_inventory_receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
