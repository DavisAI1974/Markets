"""Audit cached lifecycle scope/age and freeze all inputs before Julia starts."""
import collections
import csv
import gzip
import hashlib
import json
import os
import pathlib
import statistics
from enrichment_rules import flatten

BASE=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
OUT=BASE/'enriched-v2'
contexts=list(csv.DictReader((BASE/'descriptive-v1/group_context_receipts.csv').open()))
life={}
with gzip.open(OUT/'lifecycle_original_rows.jsonl.gz','rt') as f:
    for line in f:
        r=json.loads(line);life[r['source_ordinal']]=r['row']
links=collections.defaultdict(list)
for r in csv.DictReader((OUT/'lifecycle_context_links.csv').open()):
    links[(r['sample_id'],int(r['lag_s']))].append(r)
safe={'queue','replenishment','absorption','ladder','flow_substrate','recurrence','mirror'}
tmp=OUT/'enriched_context_measurements.final.csv'
dest=OUT/'enriched_context_measurements.csv'
life_n=total=0
feature_names=set()
quality=[]
with dest.open() as source,tmp.open('w',newline='') as target:
    reader=csv.DictReader(source);writer=csv.DictWriter(target,fieldnames=reader.fieldnames);writer.writeheader()
    for row in reader:
        if not row['feature'].startswith('lifecycle.'):
            writer.writerow(row);total+=1;feature_names.add(row['feature'])
    for c in contexts:
        values=collections.defaultdict(list);ages=collections.defaultdict(list);counts=collections.Counter()
        for link in links[(c['sample_id'],int(c['lag_s']))]:
            if link['eligible']!='1':continue
            r=life[int(link['lifecycle_ordinal'])];sec=r['emitting_section']
            # Retain all categorical/provenance fields, including nested queue bases,
            # but never convert them or recognition/response labels into predictors.
            def walk(x,path=''):
                if isinstance(x,dict):
                    for k,v in x.items():yield from walk(v,path+'.'+k if path else k)
                elif isinstance(x,list):
                    for i,v in enumerate(x):yield from walk(v,path+f'[{i}]')
                elif isinstance(x,(str,bool)) or x is None:yield path,x
            for path,value in walk(r):
                if any(k in path for k in ['basis','reason','censor','resolved','status','continuity','policy','clock','availability','attribution','disposition','outcome','label','phase','scope','defined']):
                    quality.append(dict(sample_id=c['sample_id'],lag_s=c['lag_s'],section=sec,
                                        lifecycle_ordinal=link['lifecycle_ordinal'],path=path,value=json.dumps(value)))
            if sec not in safe:continue
            counts[sec]+=1
            dims=[sec,str(r.get('side','UNSPECIFIED'))]
            for key in ['queue_scope','ladder_scope','observation','horizon_ns','window_seconds']:
                if key in r and not isinstance(r[key],(dict,list)):
                    dims.append(key+'='+str(r[key]))
            scope='.'.join(dims)
            age=(int(c['cutoff_ns'])-int(link['own_known_by_ns']))/1e9
            if sec=='flow_substrate' and isinstance(r.get('second'),int):
                age=max(age,(int(c['cutoff_ns'])-(r['second']+1)*10**9)/1e9)
            for name,value in flatten(r):
                feature=f'lifecycle.{scope}.{name}.mean'
                values[feature].append(value);ages[feature].append(age)
        for sec in sorted(safe):
            feature=f'lifecycle.{sec}.emission_count';values[feature]=[counts[sec]];ages[feature]=[float(c['age_s'])]
        for feature,v in values.items():
            writer.writerow(dict(sample_id=c['sample_id'],lag_s=c['lag_s'],feature=feature,
                                 value=statistics.mean(v),age_s=max(ages[feature]),source_ordinal=c['source_ordinal'],
                                 observed_n=len(v),reason='known_emission_scope_mean;age=max_publication_or_flow_bin_age'))
            life_n+=1;total+=1
            feature_names.add(feature)
os.replace(tmp,dest)
with gzip.open(OUT/'lifecycle_complete_quality.csv.gz','wt',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['sample_id','lag_s','section','lifecycle_ordinal','path','value']);w.writeheader();w.writerows(quality)
ready=json.loads((OUT/'all_additions_ready.json').read_text())
ready.update(numeric_rows=total,features=len(feature_names),final_lifecycle_numeric_rows=life_n,complete_lifecycle_quality_rows=len(quality),
             lifecycle_dimensions='section, side, queue/ladder scope, observation type, horizon_ns, window_seconds; no pooling across these dimensions',
             lifecycle_age_policy='Publication ages retained in links; numerical age conservatively includes flow-bin observation age; no early availability inferred from an old event timestamp')
files=['enriched_context_measurements.csv','quote_windows.csv','remaining_gaps.csv','enrichment_receipt.json','lifecycle_context_links.csv','lifecycle_original_rows.jsonl.gz','external_extended_asof.jsonl.gz','native_quality_contexts.jsonl.gz']
ready['frozen_input_hashes']={name:hashlib.file_digest((OUT/name).open('rb'),'sha256').hexdigest() for name in files}
(OUT/'all_additions_ready.json').write_text(json.dumps(ready,indent=2)+'\n')
print(json.dumps({k:v for k,v in ready.items() if k!='frozen_input_hashes'}),flush=True)
