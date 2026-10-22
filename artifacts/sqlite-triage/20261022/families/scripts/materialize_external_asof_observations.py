"""Resolve known source versions at their own availability, before scope features.

This is a lossless scientific sidecar to the raw catalogs. It does not select a
scope's latest observation, impute missing measurements, or approve a fit.
"""
import collections
import csv
import itertools
import json
import os
import pathlib
import sqlite3
from external_variant_resolution import resolve


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    folder=base/'external-history-v4';out=base/'external-asof-v4';out.mkdir(exist_ok=True)
    contexts=list(csv.DictReader((base/'descriptive-v1/group_context_receipts.csv').open()))
    minimum=min(int(c['cutoff_ns']) for c in contexts);maximum=max(int(c['cutoff_ns']) for c in contexts)
    target=out/'resolved_observation_events.sqlite';assert not target.exists()
    db=sqlite3.connect('file:'+str(folder/'scoped_history.sqlite')+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA cache_size=-1000000')
    db.execute('ATTACH DATABASE ? AS links',('file:'+str(folder/'occurrence_links.sqlite')+'?mode=ro',))
    result=sqlite3.connect(target)
    result.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE observation_event(observation_id TEXT,scope_id TEXT,point_name TEXT,effective_ns INTEGER,
          event_ns INTEGER,source_published_ns INTEGER,same_stamp_position INTEGER,resolution_json TEXT,
          PRIMARY KEY(observation_id,effective_ns));
        CREATE TABLE observation_audit(observation_id TEXT PRIMARY KEY,scope_id TEXT,point_name TEXT,
          source_records INTEGER,normalized_variants INTEGER,known_variants INTEGER,future_variants INTEGER,
          observation_json TEXT);''')
    query='''SELECT o.observation_id AS occurrence_id,o.same_stamp_position,n.*,
       MAX(CASE WHEN o.source_id='pinned-current-db' THEN o.source_ordinal END) AS primary_ordinal,
       count(*) AS source_records
       FROM links.occurrence o JOIN normalized_variant n USING(normalized_sha256)
       GROUP BY o.observation_id,n.normalized_sha256 ORDER BY o.observation_id,n.available_ns,n.normalized_sha256'''
    counts=collections.Counter();points=collections.defaultdict(collections.Counter)
    for occurrence,group in itertools.groupby(db.execute(query),lambda r:r['occurrence_id']):
        rows=list(group);first=rows[0];variants=[]
        for r in rows:
            v=dict(normalized_sha256=r['normalized_sha256'],available_ns=r['available_ns'],primary_ordinal=r['primary_ordinal'],
                numeric=json.loads(r['numeric_json']),states=json.loads(r['states_json']),categories=json.loads(r['categories_json']))
            variants.append(v)
        known=[v for v in variants if v['available_ns']<=maximum]
        result.execute('INSERT INTO observation_audit VALUES (?,?,?,?,?,?,?,?)',
          (occurrence,first['scope_id'],first['point_name'],sum(r['source_records'] for r in rows),len(rows),len(known),len(rows)-len(known),first['observation_json']))
        counts['observations']+=1;counts['source_records']+=sum(r['source_records'] for r in rows)
        counts['normalized_variants_at_occurrence_coordinates']+=len(rows);counts['future_variants_withheld']+=len(rows)-len(known)
        if not known:counts['entirely_future_observations']+=1;continue
        # Keep one complete initial as-of state, then each distinct subsequent
        # availability. Earlier revisions remain in the immutable linked catalogs.
        initial=[v['available_ns'] for v in known if v['available_ns']<=minimum]
        cutoffs=sorted(({max(initial)} if initial else set())|{v['available_ns'] for v in known if v['available_ns']>minimum})
        for cutoff in cutoffs:
            resolved=resolve(known,cutoff)
            assert resolved and resolved['known_ns']<=cutoff<=maximum
            eligible=[r for r in rows if r['available_ns']<=cutoff]
            selected=[r for r in eligible if r['normalized_sha256']==resolved['selected_primary_sha256']]
            # These clocks are coordinate provenance, not a favorable source selection.
            event_clocks={r['event_ns'] for r in eligible};source_clocks={r['source_published_ns'] for r in eligible}
            event=selected[0]['event_ns'] if selected else next(iter(event_clocks)) if len(event_clocks)==1 else None
            published=selected[0]['source_published_ns'] if selected else next(iter(source_clocks)) if len(source_clocks)==1 else None
            resolved['clock_states']=dict(event='AGREED' if len(event_clocks)==1 else 'VARIANT_CLOCK_CONFLICT',
                source_publication='AGREED' if len(source_clocks)==1 else 'VARIANT_CLOCK_CONFLICT')
            resolved['source_occurrence_coordinate']=occurrence
            result.execute('INSERT INTO observation_event VALUES (?,?,?,?,?,?,?,?)',
                (occurrence,first['scope_id'],first['point_name'],cutoff,event,published,first['same_stamp_position'],
                 json.dumps(resolved,sort_keys=True,separators=(',',':'),allow_nan=False)))
            counts['resolution_events']+=1;points[first['point_name']]['resolution_events']+=1
            conflict=sum(s=='CONFLICTING_SOURCE_VARIANTS' for s in resolved['states'].values())
            counts['unranked_numeric_conflict_cells']+=conflict;points[first['point_name']]['unranked_numeric_conflict_cells']+=conflict
            primary_null=sum(v is None and resolved['selected_primary_sha256'] is not None for v in resolved['numeric'].values())
            counts['primary_unavailable_cells_retained']+=primary_null
        if counts['observations']%100000==0:
            result.commit();print('Resolved scoped observations',counts['observations'],'events',counts['resolution_events'],flush=True)
    expected=json.loads((folder/'occurrence_links_receipt.json').read_text())['source_records'];assert counts['source_records']==expected
    result.executescript('''CREATE INDEX event_scope_time ON observation_event(scope_id,effective_ns);
      CREATE INDEX event_availability ON observation_event(effective_ns,point_name,scope_id);''')
    result.commit();result.execute('PRAGMA wal_checkpoint(TRUNCATE)');result.close()
    report=dict(schema='EXTERNAL_ASOF_OBSERVATION_RESOLUTION_V1',status='complete',coverage_gate='NOT_PASSED',
        context_cutoff_min_ns=minimum,context_cutoff_max_ns=maximum,counts=dict(counts),by_point={k:dict(v) for k,v in sorted(points.items())},
        rules=['Filter by exact integer availability before checking primary-source precedence.',
          'Known primary nulls, missing markers and deletions remain unavailable; no alternative value silently fills them.',
          'Unranked numeric disagreements are unknown with every finite alternative and missingness state retained.',
          'Source-occurrence multiplicity is distinct from normalized content and observation counts.',
          'Initial as-of resolution plus all within-window revision arrivals are retained; raw earlier and later versions remain in the immutable catalogs.'],
        remaining=['Scope-vintage selection, per-context history features, field units and ages, knowledge/99-plane coverage gate, v4 matrix and all fits remain owed.'])
    (out/'observation_resolution_receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
