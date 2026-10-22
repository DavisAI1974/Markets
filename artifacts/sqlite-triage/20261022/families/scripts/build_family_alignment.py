import pathlib, json, sqlite3, time, hashlib, array, sys, bisect, concurrent.futures, os
from family_clock_sources import find_second_set

OUT = pathlib.Path('/tmp/codex-family-starts-20261022')
binding = json.loads((OUT/'all-input-binding.json').read_bytes())
families = json.loads((OUT/'family-start-candidates.json').read_bytes())['families']
dbpath = OUT/'family-alignment.sqlite'
if dbpath.exists():
    raise RuntimeError('Analysis database already exists; preserve it instead of overwriting')
db = sqlite3.connect(dbpath)
db.executescript("""
CREATE TABLE metadata(key TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE family_start(family_id TEXT PRIMARY KEY, occurrence_count INTEGER, start_recv_ns INTEGER, start_event_ns INTEGER, window_start_ns INTEGER, input_cursor INTEGER, source_ordinal INTEGER, start_basis TEXT);
CREATE TABLE group_event(source_ordinal INTEGER PRIMARY KEY, family_id TEXT, recv_ns INTEGER, event_ns INTEGER, input_cursor INTEGER, instrument_id INTEGER);
CREATE TABLE source_registry(name TEXT PRIMARY KEY, path TEXT, sha256 TEXT, bytes INTEGER, offset_index TEXT);
CREATE TABLE plane_registry(ordinal INTEGER PRIMARY KEY, entry_id TEXT, body TEXT NOT NULL);
CREATE TABLE external_point(name TEXT PRIMARY KEY, columns_json TEXT, body TEXT);
CREATE TABLE external_row(point_name TEXT, source_ordinal INTEGER, published_ns INTEGER, event_time_ns INTEGER, row_json TEXT, PRIMARY KEY(point_name, source_ordinal));
CREATE TABLE price_row(source_ordinal INTEGER PRIMARY KEY, recv_ns INTEGER, event_ns INTEGER, input_cursor INTEGER, row_json TEXT);
CREATE TABLE anchor_context(family_id TEXT PRIMARY KEY, native_member_json TEXT, root_frame_packed_json TEXT, second_set_json TEXT, differences_json TEXT);
""")
db.execute('INSERT INTO metadata VALUES (?,?)', ('all_input_binding',json.dumps(binding)))
db.execute('INSERT INTO metadata VALUES (?,?)', ('analysis_status',json.dumps({'stage':'aligning','signals_tested':False,'missing_policy':'retain all families, all 99 entries, all 13 points and confirmed second set; explicit missing fields','start_basis':'first observed structural-family instance in retained source order, not an assumed order birth'})))
for f in families:
    x=f['first_in_source']
    db.execute('INSERT INTO family_start VALUES (?,?,?,?,?,?,?,?)',(f['family_id'],f['occurrences'],x['ts_recv_ns'],x['ts_event_ns'],x['ts_recv_ns']-120_000_000_000,x['input_cursor'],x['source_ordinal'],'FIRST_OBSERVED_STRUCTURAL_FAMILY'))
for ordinal,entry in enumerate(binding['all99']['entries']):
    name=entry.get('entry') or entry.get('name') or entry.get('id') or str(ordinal)
    db.execute('INSERT INTO plane_registry VALUES (?,?,?)',(ordinal,name,json.dumps(entry)))
for name,pin in binding['source_identity']['sources'].items():
    idx=binding['source_indexes'][pin['path']]
    db.execute('INSERT INTO source_registry VALUES (?,?,?,?,?)',(name,pin['path'],pin['sha256'],pin['bytes'],idx['path']))
db.commit()

def scalar(d,k):
    v=d.get(k)
    return v[1] if isinstance(v,list) and len(v)>1 else None

def unpack(v):
    if not isinstance(v,list) or not v:return v
    tag=v[0]
    if tag=='dict':return {k:unpack(x) for k,x in v[1]}
    if tag in ('list','tuple','set','frozenset'):return [unpack(x) for x in v[1]]
    if tag=='null':return None
    if len(v)==2 and tag in ('str','int','float','bool'):return v[1]
    return v

sp=binding['source_identity']['sources']['root.structures']
count=0;digest=hashlib.sha256()
with open(sp['path'],'rb') as handle:
    batch=[]
    for ordinal,raw in enumerate(handle):
        digest.update(raw);packed=dict(json.loads(raw)[1]);prov=dict(packed['provenance'][1])
        batch.append((ordinal,scalar(packed,'candidate_family_id'),scalar(packed,'ts_recv_ns'),scalar(packed,'ts_event_ns'),scalar(prov,'input_cursor'),scalar(prov,'instrument_id')))
        if len(batch)==5000:db.executemany('INSERT INTO group_event VALUES (?,?,?,?,?,?)',batch);batch=[]
        count+=1
    if batch:db.executemany('INSERT INTO group_event VALUES (?,?,?,?,?,?)',batch)
if digest.hexdigest()!=sp['sha256']:raise ValueError('Structures source hash differs')
db.commit()
print(json.dumps({'stage':'family_events_indexed','rows':count,'families':len(families)}),flush=True)

ep=binding['source_identity']['external']
raw=pathlib.Path(ep['path']).read_bytes()
if hashlib.sha256(raw).hexdigest()!=ep['sha256']:raise ValueError('13-point source hash differs')
external=json.loads(raw)
external_rows=0
for name,table in external['points'].items():
    cols=table['columns'];stamp=cols.index(table['stamp_column']);event=cols.index('event_time_ns') if 'event_time_ns' in cols else None
    meta={k:v for k,v in table.items() if k!='rows'}
    db.execute('INSERT INTO external_point VALUES (?,?,?)',(name,json.dumps(cols),json.dumps(meta)))
    batch=[]
    for ordinal,row in enumerate(table['rows']):
        batch.append((name,ordinal,row[stamp],row[event] if event is not None else None,json.dumps(dict(zip(cols,row)))))
        if len(batch)==5000:db.executemany('INSERT INTO external_row VALUES (?,?,?,?,?)',batch);batch=[]
        external_rows+=1
    if batch:db.executemany('INSERT INTO external_row VALUES (?,?,?,?,?)',batch)
pp=binding['source_identity']['sources']['root.prices']
digest=hashlib.sha256();price_rows=0
with open(pp['path'],'rb') as handle:
    batch=[]
    for ordinal,raw in enumerate(handle):
        digest.update(raw);row=unpack(json.loads(raw));prov=row.get('provenance') or {}
        batch.append((ordinal,row.get('ts_recv_ns'),row.get('ts_event_ns'),prov.get('input_cursor'),json.dumps(row)))
        if len(batch)==5000:db.executemany('INSERT INTO price_row VALUES (?,?,?,?,?)',batch);batch=[]
        price_rows+=1
    if batch:db.executemany('INSERT INTO price_row VALUES (?,?,?,?,?)',batch)
if digest.hexdigest()!=pp['sha256']:raise ValueError('Price source hash differs')
db.executescript("""
CREATE INDEX group_time ON group_event(recv_ns,input_cursor);
CREATE INDEX external_time ON external_row(published_ns,point_name);
CREATE INDEX price_time ON price_row(recv_ns,input_cursor);
CREATE VIEW prebirth_groups AS SELECT f.family_id AS target_family_id,f.start_recv_ns,g.* FROM family_start f JOIN group_event g ON g.recv_ns>=f.window_start_ns AND g.recv_ns<f.start_recv_ns AND g.input_cursor<f.input_cursor;
CREATE VIEW prebirth_prices AS SELECT f.family_id AS target_family_id,f.start_recv_ns,p.* FROM family_start f JOIN price_row p ON p.recv_ns>=f.window_start_ns AND p.recv_ns<f.start_recv_ns AND (p.input_cursor<f.input_cursor OR p.input_cursor IS NULL);
CREATE VIEW prebirth_external_updates AS SELECT f.family_id,f.start_recv_ns,e.* FROM family_start f JOIN external_row e ON e.published_ns>=f.window_start_ns AND e.published_ns<f.start_recv_ns;
CREATE VIEW external_known_before_start AS SELECT f.family_id,f.start_recv_ns,e.* FROM family_start f JOIN external_row e ON e.published_ns<f.start_recv_ns;
""")
db.commit()
print(json.dumps({'stage':'all_13_points_and_prices_indexed','external_tables':len(external['points']),'external_rows':external_rows,'price_rows':price_rows,'all99_entries':99,'second_set':'source and cursor binding retained; validating actual anchor records next'}),flush=True)

offsets={}
for name in ['native.member','root.frames']:
    pin=binding['source_identity']['sources'][name];idx=binding['source_indexes'][pin['path']]
    with open(idx['path'],'rb') as h:header=json.loads(h.readline());body=h.read()
    if hashlib.sha256(body).hexdigest()!=header['sha256']:raise ValueError('Index changed')
    a=array.array('Q');a.frombytes(body)
    if header['byteorder']!=sys.byteorder:a.byteswap()
    offsets[name]=a

teacher=pathlib.Path('/opt/frankie-box/work/experiment-teacher-rows/20231018/host-dipole-classroom-source.c15.rows.jsonl')
def teacher_row(cursor):
    found=find_second_set(teacher,cursor)
    return found[2] if found else None

def context(f):
    x=f['first_in_source'];ordinal=x['source_ordinal'];records={};differences=[]
    for name in ['native.member','root.frames']:
        a=offsets[name];pin=binding['source_identity']['sources'][name]
        with open(pin['path'],'rb') as h:h.seek(a[ordinal]);raw=h.read(a[ordinal+1]-a[ordinal])
        row=json.loads(raw)
        if name=='native.member':
            if row.get('family_id')!=f['family_id']:differences.append({'source':name,'field':'family_id','actual':row.get('family_id')})
            if (row.get('frankie_emission') or {}).get('input_cursor')!=x['input_cursor']:differences.append({'source':name,'field':'input_cursor'})
        else:
            d=dict(row[1]);
            if scalar(d,'input_cursor')!=x['input_cursor']:differences.append({'source':name,'field':'input_cursor','actual':scalar(d,'input_cursor')})
        records[name]=raw.decode()
    second=teacher_row(x['input_cursor'])
    if second is None:differences.append({'source':'second_set','field':'row','reason':'cursor not found; family retained'})
    elif second['key']['adapter_cursor']!=x['input_cursor']:differences.append({'source':'second_set','field':'adapter_cursor'})
    return (f['family_id'],records['native.member'],records['root.frames'],json.dumps(second),json.dumps(differences))

done=0;different=0
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for row in pool.map(context,families):
        db.execute('INSERT INTO anchor_context VALUES (?,?,?,?,?)',row)
        done+=1;different+=bool(json.loads(row[-1]))
        if done%50==0:
            db.commit();print(json.dumps({'stage':'anchoring_all_inputs','families_done':done,'total':len(families),'families_with_listed_differences':different}),flush=True)
db.commit()
counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['family_start','group_event','plane_registry','external_point','external_row','price_row','anchor_context']}
summary={'schema':'FAMILY_PREBIRTH_ALIGNMENT_REPORT_V1','counts':counts,'families_with_listed_differences':different,'external_13_count':len(binding['external_13']['points']),'second_set_confirmed':True,'lookback_seconds':120,'start_basis':'first observed structural family, recurring instances retained separately','signals_tested':False,'notes':['All source plane identities and dispositions retained, including missing/thin/non-market roles.','SQL views retain original timestamps, cursors and native values. Raw receive-clock views are exploratory; availability clocks in second-set records remain distinct.','Full interval frame/member values remain in pinned source files through ordinal offset references; anchor_context contains all three actual anchor records. No claim that every source byte in every window has been statistically analyzed.']}
assert counts['family_start']==749 and counts['plane_registry']==99 and counts['anchor_context']==749
db.execute('UPDATE metadata SET body=? WHERE key=?',(json.dumps({'stage':'family_anchors_loaded_price_clocks_require_verification','signals_tested':False}), 'analysis_status'))
db.execute('INSERT INTO metadata VALUES (?,?)',('alignment_report',json.dumps(summary)))
db.commit()
check=db.execute('PRAGMA quick_check').fetchone()[0]
summary['sqlite_quick_check']=check
(OUT/'alignment-report.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({'stage':'alignment_complete',**summary}),flush=True)
db.close()


