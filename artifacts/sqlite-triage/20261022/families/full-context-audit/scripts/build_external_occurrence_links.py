"""Retain simultaneous stream-message multiplicity before revision alignment.

Normalized row content is not an event count. The coarse observation coordinate
in scoped_history.sqlite is deliberately refined for ordered curve messages;
every original source ordinal still has its own provenance row.
"""
import collections
import csv
import json
import os
import pathlib
import sqlite3
from external_variant_resolution import occurrence_identity


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'external-history-v4';target=out/'occurrence_links.sqlite';assert not target.exists()
    source=sqlite3.connect('file:'+str(out/'scoped_history.sqlite')+'?mode=ro',uri=True)
    source.execute('PRAGMA cache_size=-2000000')
    result=sqlite3.connect(target)
    result.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE occurrence(source_id TEXT,point_name TEXT,source_ordinal INTEGER,normalized_sha256 TEXT,
          observation_id TEXT,same_stamp_position INTEGER,available_ns INTEGER,
          PRIMARY KEY(source_id,point_name,source_ordinal));''')
    query='''SELECT p.source_id,p.point_name,p.source_ordinal,p.normalized_sha256,n.scope_id,n.observation_id,
             n.source_published_ns,n.event_ns,n.available_ns
             FROM provenance p JOIN normalized_variant n USING(normalized_sha256)
             ORDER BY p.source_id,p.point_name,p.source_ordinal'''
    previous=None;positions=collections.Counter();counts=collections.Counter();coincident=collections.Counter();total=0
    for source_id,point,ordinal,normalized_sha,scope,coarse,published,event,available in source.execute(query):
        if point.startswith('curve.'):
            clock_group=(source_id,point,published)
            if clock_group!=previous:
                if previous is not None and previous[:2]==clock_group[:2]:assert previous[2]<=published
                positions.clear();previous=clock_group
            key=(scope,event);position=positions[key];positions[key]+=1
            identity=occurrence_identity(point,scope,published,event,position)
            if position:coincident[(source_id,point)]+=1
        else:identity=coarse;position=None
        result.execute('INSERT INTO occurrence VALUES (?,?,?,?,?,?,?)',
            (source_id,point,ordinal,normalized_sha,identity,position,available))
        counts[(source_id,point)]+=1;total+=1
        if total%250000==0:
            result.commit();print('Linked external source occurrences',total,flush=True)
    result.executescript('''CREATE INDEX occurrence_observation ON occurrence(observation_id,available_ns);
        CREATE INDEX occurrence_variant ON occurrence(normalized_sha256,source_id);''')
    result.commit();result.execute('PRAGMA wal_checkpoint(TRUNCATE)');result.close()
    with (out/'coincident_stream_occurrence_counts.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['source_id','point','source_records','additional_same_stamp_messages'])
        for key,count in sorted(counts.items()):w.writerow([*key,count,coincident[key]])
    expected=json.loads((out/'scoped_history_receipt.json').read_text())['source_records'];assert total==expected
    receipt=dict(schema='EXTERNAL_SOURCE_OCCURRENCE_LINKS_V1',status='complete',coverage_gate='NOT_PASSED',source_records=total,
        simultaneous_stream_messages_retained=sum(coincident.values()),
        original_normalized_catalog_changed=False,
        rule='Curve stream coordinate = dimensional scope + original publication ns + event ns + stable same-stamp source position. Other natural observation/vintage keys remain scoped.',
        limitations=['No exchange sequence is fabricated; same-stamp position is the retained source order.',
          'A source version adding/removing messages can change position matching. Conflicting payloads at a matched coordinate must stay explicit.',
          'Normalized variant counts and observation coordinates must never substitute for source-message counts.',
          'As-of revision resolution, full field consumer coverage and the v4 matrix remain incomplete.'])
    (out/'occurrence_links_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
