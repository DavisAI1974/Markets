"""Normalize every saved external source record into explicit dimensional scopes.

The original catalog and raw source rows remain immutable. This component does
not pick a favorable revision, overwrite old features, or approve model fits.
"""
import collections
import csv
import hashlib
import json
import os
import pathlib
import sqlite3
from collect_manifested_external_history import table_rows
from external_history_semantics import normalize


def canon(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    audit=base/'full-context-audit';out=base/'external-history-v4'
    out.mkdir(exist_ok=True);target=out/'scoped_history.sqlite'
    assert not target.exists(),'Normalized catalog is immutable; retain failed versions explicitly'
    db=sqlite3.connect('file:'+str(audit/'external_history.sqlite')+'?mode=ro',uri=True)
    db.execute('PRAGMA cache_size=-2000000')
    original=sqlite3.connect('file:'+str(base/'alignment.sqlite')+'?mode=ro',uri=True)
    added=audit/'historical-source-additions/20231017-day-external-3e4b06be.json'
    recovered=json.loads((added.parent/'20231017-source-recovery.json').read_text())
    assert added.stat().st_size==recovered['bytes']
    assert hashlib.file_digest(added.open('rb'),'sha256').hexdigest()==recovered['sha256']
    extra=json.loads(added.read_text())
    sources={r[0]:dict(source_id=r[0],day=r[1],path=r[2],sha256=r[3],bytes=r[4],role=r[5],metadata=json.loads(r[6]))
             for r in db.execute('SELECT * FROM source_file')}
    sources['pinned-current-db']['metadata']['point_metadata']={n:json.loads(body) for n,body in original.execute('SELECT name,body FROM external_point')}
    extra_id='s3-sha256:'+recovered['sha256']
    sources[extra_id]=dict(source_id=extra_id,day=extra['trading_day'],path=str(added),sha256=recovered['sha256'],
                           bytes=recovered['bytes'],role='newer_prior_day_source_variant',
                           metadata={k:v for k,v in extra.items() if k!='points'})
    sources[extra_id]['metadata']['point_metadata']={n:{k:v for k,v in p.items() if k!='rows'} for n,p in extra['points'].items()}
    # Fail preflight on any unreviewed schema before the full retained-catalog walk.
    preflight=[]
    for source,spec in sources.items():
        for point,meta in spec['metadata'].get('point_metadata',{}).items():
            if source==extra_id:
                candidate=next(table_rows(extra['points'][point]),None)
                row=candidate[1] if candidate else None
            else:
                candidate=db.execute('''SELECT v.row_json FROM provenance p JOIN variant v USING(point_name,row_sha256)
                    WHERE p.source_id=? AND p.point_name=? ORDER BY p.source_ordinal LIMIT 1''',(source,point)).fetchone()
                row=json.loads(candidate[0]) if candidate else None
            if row is not None:
                normalized=normalize(point,row,spec['day'])
                preflight.append(dict(source_id=source,point=point,fields=len(row),clock_rule=normalized['clock_rule']))
    (out/'schema_preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
    result=sqlite3.connect(target)
    result.executescript('''PRAGMA journal_mode=WAL; PRAGMA cache_size=-2000000;
        CREATE TABLE source_file(source_id TEXT PRIMARY KEY,day TEXT,path TEXT,sha256 TEXT,bytes INTEGER,role TEXT,metadata_json TEXT);
        CREATE TABLE scope(scope_id TEXT PRIMARY KEY,point_name TEXT,scope_json TEXT);
        CREATE TABLE normalized_variant(normalized_sha256 TEXT PRIMARY KEY,point_name TEXT,scope_id TEXT,observation_id TEXT,
          observation_json TEXT,available_ns INTEGER,event_ns INTEGER,numeric_json TEXT,states_json TEXT,categories_json TEXT,
          provenance_json TEXT,source_published_ns INTEGER,clock_rule TEXT);
        CREATE TABLE provenance(source_id TEXT,point_name TEXT,source_ordinal INTEGER,raw_row_sha256 TEXT,normalized_sha256 TEXT,
          PRIMARY KEY(source_id,point_name,source_ordinal));''')
    for spec in sources.values():
        result.execute('INSERT INTO source_file VALUES (?,?,?,?,?,?,?)',tuple(spec[k] for k in ['source_id','day','path','sha256','bytes','role'])+(canon(spec['metadata']),))
    counts=collections.Counter();states=collections.Counter();fields=collections.Counter();clocks=collections.Counter();variant_counts=collections.Counter()
    total=0;new_variants=0
    def consume(source,point,ordinal,raw_sha,row):
        nonlocal total,new_variants
        value=normalize(point,row,sources[source]['day'])
        scope_json=canon(value['scope']);scope_id=digest(point+'|'+scope_json)
        obs_json=canon(value['observation']);obs_id=digest(scope_id+'|'+obs_json)
        normalized_sha=digest(canon(value))
        result.execute('INSERT OR IGNORE INTO scope VALUES (?,?,?)',(scope_id,point,scope_json))
        result.execute('INSERT OR IGNORE INTO normalized_variant VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (normalized_sha,point,scope_id,obs_id,obs_json,value['available_ns'],value['event_ns'],canon(value['numeric']),
             canon(value['states']),canon(value['categories']),canon(value['provenance']),value['source_published_ns'],value['clock_rule']))
        fresh=result.execute('SELECT changes()').fetchone()[0]
        new_variants+=fresh
        if fresh:variant_counts[point]+=1
        result.execute('INSERT INTO provenance VALUES (?,?,?,?,?)',(source,point,ordinal,raw_sha,normalized_sha))
        counts[(source,point)]+=1;clocks[(point,value['clock_rule'])]+=1
        for field,role in value['field_roles'].items():fields[(point,field,role)]+=1
        for field,state in value['states'].items():states[(point,field,state)]+=1
        total+=1
        if total%100000==0:
            result.commit();print('Scoped external source records',total,'normalized variants',new_variants,flush=True)
    for source,spec in sources.items():
        if source==extra_id:
            for point,body in extra['points'].items():
                for ordinal,row in table_rows(body):consume(source,point,ordinal,digest(canon(row)),row)
        else:
            query='''SELECT p.point_name,p.source_ordinal,p.row_sha256,v.row_json FROM provenance p
                     JOIN variant v USING(point_name,row_sha256) WHERE p.source_id=? ORDER BY p.point_name,p.source_ordinal'''
            for point,ordinal,raw_sha,text in db.execute(query,(source,)):
                consume(source,point,ordinal,raw_sha,json.loads(text))
        result.commit();print('Finished source',source,spec['day'],flush=True)
    result.executescript('''CREATE INDEX normalized_scope_time ON normalized_variant(scope_id,available_ns);
        CREATE INDEX normalized_observation ON normalized_variant(observation_id,available_ns);
        CREATE INDEX provenance_normalized ON provenance(normalized_sha256,source_id);''')
    result.commit();result.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    with (out/'source_field_dispositions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['point','canonical_source_field','semantic_role','source_record_emissions','consumer','fitted'])
        for (point,field,role),count in sorted(fields.items()):w.writerow([point,field,role,count,'normalized_variant and raw provenance linkage',False])
    with (out/'measurement_state_counts.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['point','measurement','state','source_record_count'])
        for key,count in sorted(states.items()):w.writerow([*key,count])
    with (out/'source_record_counts.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['source_id','point','source_records'])
        for key,count in sorted(counts.items()):w.writerow([*key,count])
    report=dict(schema='SCOPED_EXTERNAL_HISTORY_CATALOG_V1',status='complete',coverage_gate='NOT_PASSED',
        sources=len(sources),source_records=total,normalized_variants=new_variants,scopes=result.execute('SELECT count(*) FROM scope').fetchone()[0],
        variants_by_table=dict(variant_counts),explicit_field_dispositions=len(fields),
        clock_rule_counts=[dict(point=k[0],rule=k[1],source_records=v) for k,v in sorted(clocks.items())],
        original_catalog_changed=False,additional_prior_day_source=recovered,
        rules=['Primary and alternative raw versions remain linked independently by source ordinal and raw SHA256.',
               'Old publication-only rows use the exact saved reader event/14:00 ET placement as an explicit derived availability; original source stamp is retained.',
               'COT wrapper and store publication fields remain distinct; repeated-header positional aliases reconcile to store fields.',
               'MOS source-file horizon is provenance; model/target day/runtime define the forecast. Original horizon is retained.',
               'Undefined statistics quantity and timestamp sentinels, deletions, source M, null and real zero remain distinct.',
               'The catalog normalizes all source rows; source revisions are not selected or averaged here.'],
        external_standard_refs=['https://www.databento.tech/docs/schemas-and-data-formats','https://databento.com/docs/standards-and-conventions'],
        remaining=['As-of context consumption, conflict accounting, field units/ages and a tested v4 matrix remain outstanding.',
                   'This component adds no independently aligned market day or fitted model.'])
    result.close()
    (out/'scoped_history_receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
