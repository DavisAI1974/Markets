"""Recover previous attached external files via exact manifest paths and hashes.

Keep original database unchanged. The separate history catalog retains every
source variant; this stage does not resolve contradictory revisions or make
them model-ready. The current pinned database is the primary reference.
"""
import collections
import hashlib
import json
import os
import pathlib
import sqlite3


def canonical(row):
    return json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)


def table_rows(point):
    original=point['columns'];cols=[];seen=set()
    for i,name in enumerate(original):
        # Older tables sometimes repeat a source column beside the wrapper's
        # publication/event column. Keep both positions, never dict-overwrite.
        unique=name if name not in seen else name+'__source_column_'+str(i)
        assert unique not in seen
        cols.append(unique);seen.add(unique)
    for ordinal,values in enumerate(point['rows']):
        assert len(values)==len(cols)
        row=dict(zip(cols,values))
        assert isinstance(row['published_ns'],int)
        assert row.get('event_time_ns') is None or isinstance(row['event_time_ns'],int)
        yield ordinal,row


def choose_manifested_file(manifest,attachment):
    candidates=[pathlib.Path(manifest['path']).parent/attachment['name']]
    candidates.extend(map(pathlib.Path,attachment.get('ingest_copies',[])))
    if attachment.get('run_copy'):candidates.append(pathlib.Path(attachment['run_copy']))
    attempts=[]
    for p in candidates:
        if not p.is_file():
            attempts.append(dict(path=str(p),status='not_a_file'));continue
        data=p.read_bytes();digest=hashlib.sha256(data).hexdigest()
        if len(data)==attachment['bytes'] and digest==attachment['sha256']:
            return p,data,attempts
        attempts.append(dict(path=str(p),status='different_version',bytes=len(data),sha256=digest))
    return None,None,attempts


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    audit=base/'full-context-audit';dst=audit/'external_history.sqlite'
    assert not dst.exists(),'history catalog is immutable'
    out=sqlite3.connect(dst)
    out.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE source_file(source_id TEXT PRIMARY KEY,day TEXT,path TEXT,sha256 TEXT,bytes INTEGER,role TEXT,metadata_json TEXT);
        CREATE TABLE variant(point_name TEXT, row_sha256 TEXT,row_json TEXT,published_ns INTEGER,event_time_ns INTEGER,PRIMARY KEY(point_name,row_sha256));
        CREATE TABLE provenance(source_id TEXT,point_name TEXT,source_ordinal INTEGER,row_sha256 TEXT,PRIMARY KEY(source_id,point_name,source_ordinal));
        CREATE INDEX variant_time ON variant(point_name,published_ns);
        CREATE INDEX provenance_variant ON provenance(point_name,row_sha256);''')
    original=sqlite3.connect('file:'+str(base/'alignment.sqlite')+'?mode=ro',uri=True);original.row_factory=sqlite3.Row
    out.execute('INSERT INTO source_file VALUES (?,?,?,?,?,?,?)',('pinned-current-db','20231018',str(base/'alignment.sqlite'),None,None,'primary_pinned_reference','{}'))
    counts=collections.Counter();new_counts=collections.Counter();files=[];duplicate_headers=[]
    def add(source,table,ordinal,row):
        text=canonical(row);h=hashlib.sha256(text.encode()).hexdigest()
        out.execute('INSERT OR IGNORE INTO variant VALUES (?,?,?,?,?)',(table,h,text,row['published_ns'],row.get('event_time_ns')))
        fresh=out.execute('SELECT changes()').fetchone()[0]
        out.execute('INSERT INTO provenance VALUES (?,?,?,?)',(source,table,ordinal,h))
        counts[(source,table)]+=1
        if fresh and source!='pinned-current-db':new_counts[table]+=1
    for r in original.execute('SELECT * FROM external_row ORDER BY point_name,source_ordinal'):
        add('pinned-current-db',r['point_name'],r['source_ordinal'],json.loads(r['row_json']))
    out.commit()
    manifests=json.loads((audit/'brain_manifest_inventory.json').read_text());seen=set()
    for m in manifests:
        day=m.get('day')
        if not isinstance(day,str) or day>'20231018':continue
        if 'retained-' in m['path'] or 'cycle' in m['path']:continue
        for att in m.get('attachments',[]):
            if att.get('name')!='day-external.json' or att['sha256'] in seen:continue
            seen.add(att['sha256'])
            p,data,attempts=choose_manifested_file(m,att)
            receipt=dict(manifest=m['path'],day=day,declared_sha256=att['sha256'],attempts=attempts)
            if p is None:
                receipt.update(status='exact_manifested_version_unavailable');files.append(receipt);continue
            j=json.loads(data);assert j['schema']=='FRANKIE_DAY_EXTERNAL_V1' and str(j['trading_day'])==day
            identity='manifest:'+att['sha256']
            metadata={k:v for k,v in j.items() if k!='points'}
            metadata['point_metadata']={k:{a:v for a,v in pt.items() if a!='rows'} for k,pt in j['points'].items()}
            out.execute('INSERT INTO source_file VALUES (?,?,?,?,?,?,?)',(identity,day,str(p),att['sha256'],len(data),'prior_or_alternate_day_file',canonical(metadata)))
            n=0
            for name,point in j['points'].items():
                if len(point['columns'])!=len(set(point['columns'])):
                    duplicate_headers.append(dict(source=identity,day=day,table=name,columns=point['columns'],rows=len(point['rows']),
                        resolution='retain_each_position; repeated names suffixed with __source_column_<zero-based-index>; semantic availability mapping pending'))
                for ordinal,row in table_rows(point):
                    assert row['published_ns']<int(j['halt_ns']), (day,name,ordinal)
                    add(identity,name,ordinal,row);n+=1
            out.commit();receipt.update(status='complete_manifest_hash_verified',path=str(p),rows=n,bytes=len(data))
            files.append(receipt);print('External attachment recovered',day,n,len(data),flush=True)
    out.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    report=dict(schema='MANIFESTED_EXTERNAL_HISTORY_RECOVERY_V1',status='complete',coverage_gate='NOT_PASSED',
        catalog=str(dst),files=files,source_record_rows=sum(counts.values()),unique_variant_rows=out.execute('SELECT count(*) FROM variant').fetchone()[0],
        newly_recovered_row_variants_by_table=dict(new_counts),
        duplicate_source_headers=duplicate_headers,
        limits=['These historical external files do not add independently aligned MBO market days.',
                'Variants and revisions are retained separately; no contradictory value is silently chosen or averaged.',
                'New rows have not yet been as-of aligned or consumed by any model.',
                'Publication stamps are source-declared historical availability, not proof of a contemporaneous live capture.'])
    out.close()
    (audit/'external_history_recovery.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'}),flush=True)


if __name__=='__main__':main()
