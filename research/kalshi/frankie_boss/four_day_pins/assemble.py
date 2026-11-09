"""Freeze saved four-day evidence and join original trade inputs; no market recomputation.

Run on a GitHub hosted runner. Original sources are immutable, hash checked, and
never silently replaced by another day. Missing runtime outputs remain missing.
"""
import bisect, collections, concurrent.futures, gzip, hashlib, io, json, os, pathlib, time, urllib.request
import pyarrow as pa
import pyarrow.parquet as pq

M = 'DavisAI1974/Markets'
D = 'DavisAI1974/markets-data'
ROOT = 'tasks/family-research-20261022/'
LREV = '2f1c3c72f9e3f15916135bca37ffcad87477e1d6'
LP = ROOT + 'lifecycle-data-links/run-42583801329-1'
EREV = '87dc338f2e74646eb731b3cd6f8968a5a0a653e2'
EP = ROOT + 'combined-events/run-42571551209-1'
GREV = '2fd55ea1276d00530f8cdbd1caf5918910494f19'
GP = ROOT + 'combined-events/run-42569937357-1'
OLD = 'artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/'
READS = []

def fetch(repo, rev, path):
    for attempt in range(5):
        try:
            with urllib.request.urlopen('https://raw.githubusercontent.com/'+repo+'/'+rev+'/'+path, timeout=180) as r:
                return r.read()
        except Exception:
            if attempt == 4: raise
            time.sleep(2 ** attempt)

def checked(repo, rev, path, expected=None):
    b = fetch(repo, rev, path)
    row = dict(repository=repo, revision=rev, path=path, bytes=len(b), sha256=hashlib.sha256(b).hexdigest(),
               git_blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest())
    if expected:
        for k in ('bytes','sha256','git_blob'):
            if expected.get(k) is not None: assert expected[k] == row[k], (path,k,expected[k],row[k])
    READS.append(row)
    return b, row

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')

def compact(value): return json.dumps(value, ensure_ascii=False, separators=(',',':'), allow_nan=False)

def main(config_path, output_path):
    config=json.loads(pathlib.Path(config_path).read_text())
    out=pathlib.Path(output_path); out.mkdir(parents=True,exist_ok=True)
    packet=json.loads(checked(D,config['canonical_revision'],config['canonical_path'])[0])
    groups=packet['active_inputs']
    todo=[]
    for g in groups:
        s=dict(g['canonical']); s.update(bytes=g['bytes'],sha256=g['sha256'],content_id=g['content_id'],aliases=g.get('aliases',[]))
        todo.append(s)
    todo += config['supplements']+config['findings']
    unique={}
    for s in todo:
        key=(s['repository'],s['revision'],s['path'])
        if key not in unique: unique[key]=s
    cache={}; errors=[]; pins=[]
    def verify(s):
        try:
            b,p=checked(s['repository'],s['revision'],s['path'],s)
            p.update(role=s.get('role','frozen_research_input'),content_id=s.get('content_id'),aliases=s.get('aliases',[]),status='BYTES_VERIFIED')
            return p
        except Exception as e: return dict(**s,status='UNAVAILABLE_OR_HASH_FAILED',error=str(e))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for i,p in enumerate(pool.map(verify,unique.values())):
            pins.append(p)
            if p['status']!='BYTES_VERIFIED': errors.append(p)
            if i%100==0: print('verified',i,'of',len(unique),'errors',len(errors),flush=True)
    dump(out/'INPUT_PINS.json',dict(schema='FRANKIE_FOUR_DAY_INPUT_PINS_V1',days=config['days'],sources=pins,
         rule='Exact source bytes pinned. This does not claim every runtime layer was produced.',unavailable=errors))
    verified={(p['repository'],p['revision'],p['path']):p for p in pins if p['status']=='BYTES_VERIFIED'}
    def read(repo,rev,path):
        b,p=checked(repo,rev,path,verified.get((repo,rev,path)))
        return b
    registry=json.loads(read(D,LREV,LP+'/external/canonical-99-registry.json'))
    bindings=json.loads(read(D,LREV,LP+'/external/all-13-input-bindings.json'))['points']
    ext=json.loads(gzip.decompress(read(D,LREV,LP+'/external/original-external-series.json.gz')))
    layers=[]
    for group in registry['groups']:
        for e in group['entries']:
            layers.append(dict(e,number=len(layers)+1,group=group['group_id'],policy=group['policy'],column='L%03d | %s'%(len(layers)+1,e['layer_id'])))
    assert len(layers)==99 and len(bindings)==13
    for p in bindings: layers.append(dict(number=len(layers)+1,layer_id=p['name'],description=p['name'],group='external_13_inputs',policy='PUBLICATION_ASOF',column='X%02d | %s'%(p['point_id'],p['name']),point=p))
    series={s['name']:s for s in ext['series']}
    sortedseries={}
    for name,s in series.items():
        items=sorted(enumerate(s['known']),key=lambda x:(int(x[1]['published_ns']),x[0]))
        sortedseries[name]=([int(r['published_ns']) for _,r in items],items)
    # Full original external histories and legacy knowledge claims are retained.
    (out/'external').mkdir()
    (out/'external'/'original-external-series.json.gz').write_bytes(gzip.compress(compact(ext).encode(),mtime=0))
    dump(out/'external'/'all-13-input-bindings.json',bindings)
    dump(out/'external'/'canonical-99-registry.json',registry)
    knowledge=out/'brain'/'20261109-search'; knowledge.mkdir(parents=True)
    brain_entries=[]; finding_index=[]
    def brain_file(name,b,source,kind):
        (knowledge/name).write_bytes(b)
        brain_entries.append(dict(name=name,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),include=True,source=source,kind=kind))
    for i,s in enumerate(config['findings'],1):
        b=read(s['repository'],s['revision'],s['path']); name='F%02d-'%i+pathlib.PurePosixPath(s['path']).name
        brain_file(name,b,s['repository']+'@'+s['revision']+':'+s['path'],'research findings; source scope and caveats retained')
        finding_index.append(dict(id='F%02d'%i,name=name,source=s,sha256=hashlib.sha256(b).hexdigest()))
    brain_file('retained-external-claims.json', (json.dumps(ext.get('claims',[]),indent=1)+'\n').encode(), LP+'/external/original-external-series.json.gz','original external claims, retained as hypotheses')
    dump(out/'FINDINGS.json',finding_index)
    # Original second-set payloads were absent from the earlier frozen packet.
    second={}
    for line in gzip.decompress(read(M,config['code_revision'],OLD+'every-trade-original-second-set.jsonl.gz')).splitlines():
        r=json.loads(line);second[int(r['trade_ordinal'])]=r
    component_names=sorted({k for r in second.values() for k in (r.get('at_trade_input') or {}).get('numbers',{})})
    for name in component_names:
        layers.append(dict(number=len(layers)+1,layer_id=name,description='Original second-set component '+name,group='second_set_components',policy='SOURCE_STATE_RETAINED',column='S%02d | %s'%(component_names.index(name)+1,name)))
    dump(out/'LAYERS.json',layers)
    native={}
    # All saved full-depth members, not only chunk 001.
    for s in config['supplements']:
        if '/quote-order-gapfill-v1/native.member.chunk' in s['path'] and s['path'].endswith('.jsonl.gz'):
            for ordinal,line in enumerate(gzip.decompress(read(M,s['revision'],s['path'])).splitlines()):
                r=json.loads(line);cl=r.get('clocks',{})
                cursor=cl.get('input_cursor',r.get('input_cursor'))
                if cursor is None:
                    cursor=(r.get('causal_clocks') or {}).get('input_cursor')
                if cursor is not None: native[int(cursor)]=dict(value=r,path=s['path'],ordinal=ordinal)
    static={}
    for layer in layers[:99]:
        if layer['policy'] in ('STATIC_REQUIRED_INPUT','ARM_REQUIRED_INPUT','PROVISIONAL_SHADOW'):
            entries=[p for p in pins if p['path'] in layer.get('source_paths',[]) and p['status']=='BYTES_VERIFIED']
            static[layer['layer_id']]=dict(status='STATIC_KNOWLEDGE_PINNED' if entries else 'MISSING_STATIC_SOURCE',sources=entries)
    # Explicit source-column bindings. These copy observations, not fitted aliases.
    select={
      'full_bid_ask_depth':['bid_full_size','ask_full_size','bid_top10_json','ask_top10_json'],
      'price_level_and_order_counts':['bid_orders','ask_orders','bid_full_orders','ask_full_orders','bid_levels','ask_levels'],
      'price_and_book_path':['bid_price_raw','ask_price_raw','bid_size','ask_size'],
      'spread_and_depth_imbalance':['bid_price_raw','ask_price_raw','bid_size','ask_size','bid_full_size','ask_full_size'],
      'legacy_price':['bid_price_raw','ask_price_raw'],
      'legacy_book_imbalance':['bid_size','ask_size','bid_full_size','ask_full_size'],
      'missingness_and_integrity_flags':['snapshot_member','reset_member','bad_receive_clock_member'],
      'mechanics_actions_by_side_and_level':['bid_old_touch_effect_json','ask_old_touch_effect_json','bid_new_touch_effect_json','ask_new_touch_effect_json'],
      'depletion_and_replenishment':['bid_old_touch_effect_json','ask_old_touch_effect_json'],
      'raw_source_identity_provenance_clocks_integrity':['group_ordinal','first_cursor','close_cursor','known_by_ns'],
    }
    day_stats=[]; samples=[]
    for day in config['days']:
        print('joining original trade inputs',day,flush=True)
        manifest=json.loads(read(D,GREV,GP+'/events-'+day+'/MANIFEST.json'))
        group_rows=[]
        for item in sorted(manifest['files'],key=lambda e:e['path']):
            if item['path'].startswith('groups-') and item['path'].endswith('.parquet'):
                b=checked(D,GREV,GP+'/events-'+day+'/'+item['path'],item)[0]
                group_rows.extend(pq.read_table(io.BytesIO(b)).to_pylist())
        trades=pq.read_table(io.BytesIO(read(D,EREV,EP+'/events-'+day+'/a-trades.parquet'))).to_pylist()
        counts=collections.Counter();batch=[];part=0; daydir=out/day;daydir.mkdir()
        for ordinal,t in enumerate(trades):
            clock=int(t['receive_ns']); gi=int(t['group_ordinal']); pg=t.get('strict_prior_group')
            g=group_rows[gi]; prior=group_rows[int(pg)] if pg is not None and int(pg)>=0 else None
            assert int(g['known_by_ns'])==int(t['available_ns'])
            if prior: assert int(prior['known_by_ns'])<clock and int(prior['close_cursor'])<int(t['trade_input_cursor'])
            vals={k:dict(status='NO_MATCHING_VALUE_IN_RETAINED_INPUT',reason='Layer retained; no value is fabricated') for k in [x['layer_id'] for x in layers]}
            vals.update(static)
            def have(key,value,status='ORIGINAL_VALUES_JOINED'):
                vals[key]=dict(status=status,values=value)
            for key,fields in select.items():
                fields=[f for f in fields if f in g]
                if fields:have(key,dict(before={f:prior.get(f) for f in fields} if prior else None,during={f:g[f] for f in fields},during_known_by_ns=int(g['known_by_ns']),scope='saved aggregate book; top10 is not full FIFO'))
            have('order_lifecycle_trades',t)
            have('clock_event_time',int(t['event_ns']))
            have('clock_receive_time',clock)
            have('clock_event_known_by',int(t['available_ns']))
            have('clock_feature_availability',dict(before=int(prior['known_by_ns']) if prior else None,during=int(g['known_by_ns'])))
            have('aggressor_and_native_signed_flow',{k:t[k] for k in ('aggressor_side','size') if k in t},'ORIGINAL_TRADE_OPERANDS_ONLY')
            for point in bindings:
                selected=[]
                for sb in point['series']:
                    name=sb['series'];times,items=sortedseries[name];idx=bisect.bisect_right(times,clock)-1
                    if idx<0:selected.append(dict(series=name,status='NOT_YET_PUBLISHED',value=None));continue
                    original_idx,row=items[idx];assert int(row['published_ns'])<=clock
                    selected.append(dict(series=name,original_index=original_idx,original=row))
                have(point['name'],dict(asof_receive_ns=clock,series=selected,rule='latest declared publication; original target/state retained'),'ORIGINAL_PUBLICATION_VALUES_JOINED')
            if day=='20231018' and ordinal in second:
                sr=second[ordinal]
                # Refuse a coincidental ordinal join across differing populations.
                assert int(sr['trade_input_cursor'])==int(t['trade_input_cursor'])
                for name in component_names:
                    v={phase:(sr.get(phase) or {}).get('numbers',{}).get(name) for phase in ('previous_input','at_trade_input','at_emission_group_close','last_completed_group_before_trade')}
                    have(name,v,'ORIGINAL_SECOND_SET_WITH_STATES')
                nr=native.get(int(g['close_cursor']))
                if nr:
                    for key,field in [('fifo_queues','book_full'),('full_bid_ask_depth','book_full'),('queue_age_and_survival','book_full'),('queue_concentration','book_full'),('orders_and_volume_ahead','book_full')]:
                        have(key,dict(source=nr['path'],source_row=nr['ordinal'],original=nr['value'].get(field),scope='exact matched saved member; original nested values'))
            row=dict(day=day,trade_ordinal=ordinal,trade_id=day+':trade:'+str(ordinal),trade_cursor=str(t['trade_input_cursor']),event_ns=str(t['event_ns']),receive_ns=str(clock),known_by_ns=str(t['available_ns']),coverage='partial archived' if day in ('20231002','20231017') else 'full archived',source_trade_revision=EREV,source_trade_path=EP+'/events-'+day+'/a-trades.parquet')
            for layer in layers:
                v=vals[layer['layer_id']];row[layer['column']]=compact(v);counts[(layer['column'],v['status'])]+=1
            batch.append(row)
            if ordinal in (0,len(trades)//2,len(trades)-1):samples.append(row)
            if len(batch)==1000 or ordinal==len(trades)-1:
                pq.write_table(pa.Table.from_pylist(batch),daydir/('joined-inputs-%03d.parquet'%part),compression='zstd');batch=[];part+=1
        assert len(trades)=={'20231002':37670,'20231003':41410,'20231017':33451,'20231018':30739}[day]
        ds=dict(day=day,trades=len(trades),groups=len(group_rows),parts=part,layers=[dict(column=col,status=status,rows=count) for (col,status),count in counts.items()])
        dump(daydir/'COVERAGE.json',ds);day_stats.append(ds)
        del group_rows,trades
    dump(out/'REVIEW_SAMPLES.json',samples)
    dump(out/'DAY_COVERAGE.json',day_stats)
    summary=dict(schema='FRANKIE_FOUR_DAY_PIN_AUDIT_V1',days=config['days'],sources=len(pins),verified_sources=sum(p['status']=='BYTES_VERIFIED' for p in pins),failed_sources=errors,
      registry_layers=99,external_inputs=13,external_series=len(series),second_set_components=len(component_names),layer_columns=len(layers),findings_documents=len(finding_index),retained_external_claims=len(ext.get('claims',[])),trades=sum(x['trades'] for x in day_stats),
      complete_all_layers=False,limitations=['Three historical full ROOT archives are not available in the frozen GitHub packet.','Full FIFO saved members are only joined at exact retained matching cursors.','Second-set recovery is available for the retained October 18 population; other dates remain explicitly unavailable.','99 registry entries include static knowledge and runtime outputs, not 99 independent observed market variables.','Some earlier reports overstate completeness; original findings are retained with this correction.','Research findings are discovery knowledge, not independently confirmed trading rules.'])
    dump(out/'SUMMARY.json',summary)
    brain_file('PINNING_SCOPE_AND_LIMITS.json',(json.dumps(summary,indent=1)+'\n').encode(),'this assembly','authoritative completeness correction')
    brain_file('FOUR_DAY_INPUT_BINDING.json',(json.dumps(dict(repository=D,path=output_path,code_revision=os.environ.get('CODE_REV'),inputs_sha256=hashlib.sha256((out/'INPUT_PINS.json').read_bytes()).hexdigest(),layer_columns=len(layers),days=config['days']),indent=1)+'\n').encode(),'this assembly','four-day source and row binding')
    dump(knowledge/'MANIFEST.json',dict(schema='FRANKIE_BOX_BRAIN_ENTRY_V1',cycle='search',day='20261109',entry_kind='research_findings',entries=brain_entries,unavailable=[],knowledge_status='discovery_knowledge_with_explicit_incomplete_input_coverage'))
    dump(out/'READ_VERIFICATION.json',READS)
    files=[]
    for p in sorted(out.rglob('*')):
        if p.is_file():
            b=p.read_bytes();files.append(dict(path=str(p.relative_to(out)).replace('\\','/'),bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    dump(out/'MANIFEST.json',dict(files=files))
    print(json.dumps(summary,indent=1),flush=True)

if __name__=='__main__':
    import sys
    main(sys.argv[1],sys.argv[2])
