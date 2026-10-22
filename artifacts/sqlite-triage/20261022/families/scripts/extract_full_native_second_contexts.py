"""Materialize audited native/FIFO/second-set additions; no model fit or gate pass."""
import collections
import csv
import gzip
import hashlib
import itertools
import json
import os
import pathlib
from full_context_measurements import native_measurements,second_measurements


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    audit=base/'full-context-audit';out=base/'joint-inputs-v4';out.mkdir(exist_ok=True)
    dst=out/'native_second_full_context_values.jsonl.gz';assert not dst.exists()
    registry={};finite=collections.Counter();null=collections.Counter();vocab=collections.defaultdict(set);n=0;cells=0
    with gzip.open(audit/'indexed-payloads/native.member.jsonl.gz','rt') as nf, \
         gzip.open(audit/'indexed-payloads/second_set.jsonl.gz','rt') as sf, \
         gzip.open(dst,'wt',compresslevel=1) as output:
        for nw,sw in itertools.zip_longest(nf,sf):
            assert nw is not None and sw is not None
            native,second=json.loads(nw),json.loads(sw);a,b=native['row'],second['row']
            assert a['frankie_emission']['input_cursor']==b['key']['input_cursor']
            assert a['frankie_emission']['ts_recv_ns']==b['clocks']['clock_event_known_by']
            measured=[native_measurements(a),second_measurements(b,a)]
            numbers={};categories={}
            for m in measured:
                assert not set(numbers).intersection(m.numeric)
                numbers.update(m.numeric);categories.update(m.categories)
                for key,unit in m.units.items():
                    spec=(unit,m.source_paths[key],'numeric' if key in m.numeric else 'categorical')
                    if key in registry:assert registry[key]==spec,(key,registry[key],spec)
                    else:registry[key]=spec
            for key,value in numbers.items():(null if value is None else finite)[key]+=1
            for key,value in categories.items():vocab[key].add(value)
            output.write(json.dumps(dict(source_ordinal=native['source_ordinal'],input_cursor=b['key']['input_cursor'],
                known_by_ns=b['clocks']['clock_event_known_by'],instrument_id=b['key']['instrument_id'],
                native_row_sha256=native['row_sha256'],second_row_sha256=second['row_sha256'],numeric=numbers,categories=categories),separators=(',',':'),allow_nan=False)+'\n')
            n+=1;cells+=len(numbers)
            if n%1000==0:print('Full native/FIFO/second-set extraction',n,flush=True)
    assert n==6265
    with (out/'native_second_full_feature_registry.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['feature','unit','source_path','kind','finite_unique_records','null_unique_records','observed_categories'])
        for name,(unit,path,kind) in sorted(registry.items()):w.writerow([name,unit,path,kind,finite[name],null[name],len(vocab[name]) if kind=='categorical' else 0])
    (out/'native_second_category_vocabulary.json').write_text(json.dumps({k:sorted(v) for k,v in sorted(vocab.items()) if v},indent=2)+'\n')
    report=dict(schema='FULL_NATIVE_SECOND_CONTEXT_EXTRACTION_V1',status='complete',coverage_gate='NOT_PASSED',
        unique_records=n,numeric_cells=cells,numeric_feature_identities=sum(v[2]=='numeric' for v in registry.values()),
        categorical_fields=sum(v[2]=='categorical' for v in registry.values()),categorical_levels=sum(map(len,vocab.values())),
        complete_native_second_depth_reconciliation='all selected records passed',
        saved_bytes=dst.stat().st_size,saved_sha256=hashlib.file_digest(dst.open('rb'),'sha256').hexdigest(),
        remaining=['Complete external-history variant/availability resolution and full dimensional features.',
                   'Complete supplemental lifecycle and knowledge/plane coverage accounting.',
                   'Build and verify the expanded frozen matrix and structured consumer receipts before all-model rerun.'],
        limitations=['Queue positions and ranks are state coordinates; changes do not imply the same order or price level identity.',
                     'Categorical vocabularies retain all observed labels; fit preprocessing must remain training-only.',
                     'Source IDs, absolute clocks, future/identity buckets and narratives remain in structured raw evidence, not numerical predictors.'])
    (out/'native_second_full_extraction_receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
