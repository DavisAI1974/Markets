"""Known-observation histories, preserving vintage, ambiguity and missingness.

Absolute clocks and semantic scope IDs are provenance. A later matrix consumer
must derive ages at its own exact cutoff and complete the source-unit mapping.
"""
import collections
import csv
import gzip
import itertools
import json
import math
import os
import pathlib
import sqlite3


def observation_rank(point,published,event,position,available=None):
    if point.startswith('curve.'):
        if published is None:raise ValueError('ambiguous curve arrival clock')
        # Exchange-event time and per-event occurrence position do not order
        # different events that share a receive timestamp. Keep the whole tied
        # arrival group; only a known primary source ordinal can order it.
        return published,0,0
    vintage=event if event is not None else available
    if vintage is None:raise ValueError('ambiguous observation vintage')
    return vintage,published if published is not None else -1,0


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


class ScopeHistory:
    def __init__(self):
        self.observations=0;self.stats={};self.category_stats={};self.top={};self.first_known=None;self.last_known=None

    def add(self,row):
        self.observations+=1;known=row['effective_ns']
        self.first_known=known if self.first_known is None else min(self.first_known,known)
        self.last_known=known if self.last_known is None else max(self.last_known,known)
        rank=tuple(row['rank'])
        if rank in self.top:self.top[rank].append(row)
        elif len(self.top)<2 or rank>min(self.top):self.top[rank]=[row]
        if len(self.top)>2:del self.top[min(self.top)]
        for field,value in row['numeric'].items():
            s=self.stats.setdefault(field,dict(emissions=0,count=0,mean=0.0,m2=0.0,minimum=None,maximum=None,alternative_minimum=None,alternative_maximum=None,states=collections.Counter(),last_present_rank=None,last_present=[]))
            s['emissions']+=1;s['states'][row['states'][field]]+=1
            alternatives=row['alternatives'].get(field,{}).get('finite_values',[])
            if alternatives:
                s['alternative_minimum']=min(alternatives) if s['alternative_minimum'] is None else min(s['alternative_minimum'],min(alternatives))
                s['alternative_maximum']=max(alternatives) if s['alternative_maximum'] is None else max(s['alternative_maximum'],max(alternatives))
            if value is None:continue
            assert math.isfinite(value)
            s['count']+=1;delta=value-s['mean'];s['mean']+=delta/s['count'];s['m2']+=delta*(value-s['mean'])
            s['minimum']=value if s['minimum'] is None else min(s['minimum'],value)
            s['maximum']=value if s['maximum'] is None else max(s['maximum'],value)
            previous=s['last_present_rank']
            reading=(value,known,row['event_ns'],row.get('primary_source_ordinal'))
            if previous is None or rank>previous:s['last_present_rank']=rank;s['last_present']=[reading]
            elif rank==previous:s['last_present'].append(reading)
        for field,value in row['categories'].items():
            self.category_stats.setdefault(field,collections.Counter())[canonical(value)]+=1

    @staticmethod
    def ordered_selection(rows):
        if len(rows)>1 and all(r.get('primary_source_ordinal') is not None for r in rows):
            return [max(rows,key=lambda r:r['primary_source_ordinal'])]
        return rows

    @staticmethod
    def reading(rows,field):
        values={(r['numeric'].get(field),r['states'].get(field,'SOURCE_FIELD_ABSENT_NO_FILL')) for r in rows}
        if len(values)==1:return next(iter(values))
        return None,'TIED_OBSERVATION_VINTAGE_CONFLICT'

    def snapshot(self):
        numbers={'history.observations':self.observations};categories={};clocks=dict(first_known_ns=self.first_known,last_known_ns=self.last_known)
        ranked=sorted(self.top,reverse=True)
        current=self.ordered_selection(self.top[ranked[0]])
        previous=self.ordered_selection(self.top[ranked[1]]) if len(ranked)>1 else []
        for label,rows in [('current',current),('previous',previous)]:
            clocks[label+'.known_by_ns']=max(r['effective_ns'] for r in rows) if rows else None
            events={r['event_ns'] for r in rows};clocks[label+'.event_ns']=next(iter(events)) if len(events)==1 else None
        for field,s in sorted(self.stats.items()):
            value,state=self.reading(current,field);pv,ps=self.reading(previous,field) if previous else (None,'NO_PRIOR_OBSERVATION')
            numbers['current.'+field]=value;categories['current.'+field+'.state']=state
            numbers['previous.'+field]=pv;categories['previous.'+field+'.state']=ps
            numbers['change.'+field+'.latest_minus_previous']=value-pv if value is not None and pv is not None else None
            prefix='history.'+field+'.';count=s['count']
            numbers.update({prefix+'present_count':count,prefix+'unavailable_emitted_count':s['emissions']-count,
                prefix+'absent_field_count':self.observations-s['emissions'],prefix+'minimum':s['minimum'],prefix+'maximum':s['maximum'],
                prefix+'alternative_minimum':s['alternative_minimum'],prefix+'alternative_maximum':s['alternative_maximum'],
                prefix+'mean':s['mean'] if count else None,prefix+'population_std':math.sqrt(max(0.0,s['m2']/count)) if count else None})
            for reason,n in sorted(s['states'].items()):numbers[prefix+'state_count.'+reason]=n
            present=s['last_present']
            if len(present)>1 and all(v[3] is not None for v in present):present=[max(present,key=lambda v:v[3])]
            values={v[0] for v in present}
            numbers[prefix+'last_present']=next(iter(values)) if len(values)==1 else None
            categories[prefix+'last_present_state']='PRESENT' if len(values)==1 else 'NO_PRESENT_OBSERVATION' if not values else 'TIED_OBSERVATION_VINTAGE_CONFLICT'
            clocks[prefix+'last_present_known_by_ns']=max(v[1] for v in present) if present else None
            for label,rows in [('current',current),('previous',previous)]:
                alternatives=[]
                for r in rows:alternatives.extend(r['alternatives'].get(field,{}).get('finite_values',[]))
                numbers[label+'.'+field+'.alternative_minimum']=min(alternatives) if alternatives else None
                numbers[label+'.'+field+'.alternative_maximum']=max(alternatives) if alternatives else None
                numbers[label+'.'+field+'.distinct_finite_alternatives']=len(set(alternatives))
        category_fields=set().union(*(r['categories'] for r in current))
        for field in sorted(category_fields):
            values={canonical(r['categories'].get(field,{'state':'SOURCE_FIELD_ABSENT_NO_FILL'})) for r in current}
            categories['current.category.'+field]=json.loads(next(iter(values))) if len(values)==1 else dict(state='TIED_OBSERVATION_VINTAGE_CONFLICT',alternatives=[json.loads(v) for v in sorted(values)])
        for field,frequencies in sorted(self.category_stats.items()):
            numbers['history.category.'+field+'.absent_field_count']=self.observations-sum(frequencies.values())
            for value,count in sorted(frequencies.items()):numbers['history.category.'+field+'.value='+value+'.count']=count
        return dict(numeric=numbers,categories=categories,clock_provenance=clocks,
                    current_observation_ids=[r['observation_id'] for r in current],previous_observation_ids=[r['observation_id'] for r in previous])


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    receipt=json.loads((base/'external-asof-v4/observation_resolution_receipt.json').read_text())
    assert receipt['counts']['resolution_events']==receipt['counts']['observations'],'History update/removal math must be implemented before consuming revised observation events'
    minimum=receipt['context_cutoff_min_ns'];maximum=receipt['context_cutoff_max_ns']
    folder=base/'external-scope-history-v4';folder.mkdir(exist_ok=True)
    target=folder/'scope_feature_timeline.jsonl.gz';assert not target.exists()
    db=sqlite3.connect('file:'+str(base/'external-asof-v4/resolved_observation_events.sqlite')+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA cache_size=-1000000')
    source=sqlite3.connect('file:'+str(base/'external-history-v4/scoped_history.sqlite')+'?mode=ro',uri=True)
    scopes={r[0]:dict(point=r[1],scope=json.loads(r[2])) for r in source.execute('SELECT * FROM scope')}
    links=sqlite3.connect('file:'+str(base/'external-history-v4/occurrence_links.sqlite')+'?mode=ro',uri=True)
    primary_order={(r[0],r[1]):r[2] for r in links.execute("SELECT observation_id,normalized_sha256,max(source_ordinal) FROM occurrence WHERE source_id='pinned-current-db' GROUP BY observation_id,normalized_sha256")}
    histories={};counts=collections.Counter();registry={};snapshot_written=False
    def emit(handle,scope,stamp,basis):
        value=histories[scope].snapshot();spec=scopes[scope]
        for field in value['numeric']:registry[(scope,field)]=('numeric','count' if field.endswith(('_count','.count','observations')) or '.state_count.' in field else 'MEASUREMENT_UNIT_REQUIRES_SEMANTIC_MAPPING')
        for field in value['categories']:registry[(scope,field)]=('categorical','category')
        for field in value['clock_provenance']:registry[(scope,field)]=('clock_provenance','integer_ns_NOT_DIRECT_PREDICTOR')
        handle.write(canonical(dict(scope_id=scope,point=spec['point'],effective_ns=stamp,basis=basis,**value))+'\n');counts['timeline_rows']+=1
    query='SELECT * FROM observation_event ORDER BY effective_ns,point_name,scope_id,observation_id'
    with gzip.open(target,'wt',compresslevel=1) as output:
        for stamp,group in itertools.groupby(db.execute(query),lambda r:r['effective_ns']):
            if stamp>minimum and not snapshot_written:
                for scope in sorted(histories):emit(output,scope,minimum,'INITIAL_EXACT_ASOF_SNAPSHOT')
                snapshot_written=True
            changed=set()
            for row in group:
                assert stamp<=maximum
                value=json.loads(row['resolution_json']);scope=row['scope_id'];point=row['point_name']
                rank=observation_rank(point,row['source_published_ns'],row['event_ns'],row['same_stamp_position'],stamp)
                if value['selected_primary_sha256'] is None and value['clock_states']['event']=='VARIANT_CLOCK_CONFLICT':
                    raise ValueError(('unranked vintage conflict requires additional scope treatment',scope,row['observation_id']))
                value.update(observation_id=row['observation_id'],rank=rank,effective_ns=stamp,event_ns=row['event_ns'],source_published_ns=row['source_published_ns'],
                    primary_source_ordinal=primary_order.get((row['observation_id'],value['selected_primary_sha256'])))
                histories.setdefault(scope,ScopeHistory()).add(value);changed.add(scope);counts['consumed_observations']+=1
                counts['consumed_numeric_emissions']+=len(value['numeric']);counts['consumed_category_emissions']+=len(value['categories'])
                if counts['consumed_observations']%250000==0:print('Consumed historical observations',counts['consumed_observations'],flush=True)
            if stamp>minimum:
                for scope in sorted(changed):emit(output,scope,stamp,'KNOWN_SOURCE_OBSERVATION_ARRIVAL')
        if not snapshot_written:
            for scope in sorted(histories):emit(output,scope,minimum,'INITIAL_EXACT_ASOF_SNAPSHOT')
    assert counts['consumed_observations']==receipt['counts']['observations']
    with (folder/'scope_feature_registry.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['scope_id','point','scope_json','feature','kind','unit_state','consumer'])
        for (scope,field),(kind,unit) in sorted(registry.items()):w.writerow([scope,scopes[scope]['point'],canonical(scopes[scope]['scope']),field,kind,unit,'scope_feature_timeline; matrix consumer remains outstanding'])
    report=dict(schema='EXTERNAL_SCOPED_HISTORY_FEATURE_TIMELINE_V1',status='complete',coverage_gate='NOT_PASSED',counts=dict(counts),
        consumed_scopes=len(histories),registered_features=len(registry),context_cutoff_min_ns=minimum,context_cutoff_max_ns=maximum,
        rules=['Every resolved known observation contributes once, in exact availability order, to its own dimensional scope.',
          'Latest and previous observations use semantic vintage; a late older observation cannot overwrite a newer vintage.',
          'All known present values contribute to count/min/max/mean/population variance; unavailable and absent fields remain distinct.',
          'Current source missingness is never replaced by the separately labelled last-present measurement.',
          'Equal unranked vintages remain explicit conflicts; no hash is used as a numerical predictor or a tie-breaking winner.',
          'Coincident curve arrivals use known primary source order when every tied occurrence has that order; otherwise their order is unresolved. Event timestamps do not fabricate receive order.',
          'Absolute clocks remain provenance; derive ages at the exact consuming context cutoff.'],
        limitations=['These are overlapping historical observations and summaries, not new independently aligned market days.',
          'History aggregation requires one event per observation in this dataset; the builder refuses revised-event datasets until removal/update math is implemented.',
          'Units, context-level consumption, full knowledge/99-plane gate, matrix verification and all model reruns remain incomplete.'])
    (folder/'scope_history_receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
