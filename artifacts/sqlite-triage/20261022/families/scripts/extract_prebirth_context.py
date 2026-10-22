import pathlib,json,sqlite3,array,hashlib,sys,concurrent.futures,time
from family_clock_sources import find_second_set
OUT=pathlib.Path('/tmp/codex-family-starts-20261022')
binding=json.loads((OUT/'all-input-binding.json').read_bytes())
db=sqlite3.connect(OUT/'family-alignment.sqlite')
db.executescript("""CREATE INDEX IF NOT EXISTS group_cursor ON group_event(input_cursor);
CREATE TABLE IF NOT EXISTS prebirth_context(family_id TEXT, point TEXT, cutoff_ns INTEGER, input_cursor INTEGER, source_ordinal INTEGER, record_recv_ns INTEGER, known_by_ns INTEGER, root_frame_packed_json TEXT, native_member_json TEXT, second_set_json TEXT, missing_json TEXT, PRIMARY KEY(family_id,point));""")
jobs=[]
for family,start,window,cursor in db.execute('select family_id,start_recv_ns,window_start_ns,input_cursor from family_start'):
    for point,cutoff in [('window_open',window),('before_start',start-1)]:
        row=db.execute('select source_ordinal,input_cursor,recv_ns from group_event indexed by group_cursor where input_cursor<? and recv_ns<=? order by input_cursor desc limit 1',(cursor,cutoff)).fetchone()
        jobs.append((family,point,cutoff,row))
db.commit()
offsets={}
for name in ['root.frames','native.member']:
    pin=binding['source_identity']['sources'][name];idx=binding['source_indexes'][pin['path']]
    with open(idx['path'],'rb') as f:h=json.loads(f.readline());raw=f.read()
    if hashlib.sha256(raw).hexdigest()!=h['sha256']:raise ValueError('offset digest mismatch')
    a=array.array('Q');a.frombytes(raw)
    if h['byteorder']!=sys.byteorder:a.byteswap()
    offsets[name]=a
teacher=pathlib.Path('/opt/frankie-box/work/experiment-teacher-rows/20231018/host-dipole-classroom-source.c15.rows.jsonl')
def teacher_row(cursor):
    found=find_second_set(teacher,cursor)
    return found[2] if found else None
def extract(job):
    family,point,cutoff,row=job;missing=[]
    if row is None:return (family,point,cutoff,None,None,None,None,None,None,None,json.dumps(['no prior group; family retained']))
    ordinal,cursor,recv=row;records={}
    for name in ['root.frames','native.member']:
        a=offsets[name];pin=binding['source_identity']['sources'][name]
        with open(pin['path'],'rb') as f:f.seek(a[ordinal]);raw=f.read(a[ordinal+1]-a[ordinal])
        records[name]=raw.decode()
    frame=dict(json.loads(records['root.frames'])[1]);member=json.loads(records['native.member'])
    if frame['input_cursor'][1]!=cursor:missing.append('frame cursor mismatch; retain explicitly')
    if member.get('frankie_emission',{}).get('input_cursor')!=cursor:missing.append('member cursor mismatch; retain explicitly')
    second=teacher_row(cursor);known=None
    if second is None:missing.append('second-set row absent at selected cursor; retain family')
    else:
        known=second['clocks']['clock_event_known_by']
        if known>cutoff:missing.append('selected picture became available after cutoff; not eligible as prebirth evidence')
    return (family,point,cutoff,cursor,ordinal,recv,known,records['root.frames'],records['native.member'],json.dumps(second),json.dumps(missing))
count=0;with_gaps=0;start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for result in pool.map(extract,jobs):
        db.execute('insert or replace into prebirth_context values (?,?,?,?,?,?,?,?,?,?,?)',result)
        count+=1;with_gaps+=bool(json.loads(result[-1]))
        if count%100==0:
            db.commit();print(json.dumps({'stage':'two_minute_prebirth_context','done':count,'total':len(jobs),'contexts_with_listed_gaps':with_gaps}),flush=True)
db.commit()
report={'schema':'FAMILY_PREBIRTH_CONTEXT_REPORT_V1','family_count':749,'contexts':count,'contexts_with_listed_gaps':with_gaps,'lookback_seconds':120,'all99_entries':db.execute('select count(*) from plane_registry').fetchone()[0],'external_13_points':len(binding['external_13']['points']),'second_set_included':True,'seconds':round(time.monotonic()-start,2),'signals_tested':False,'scope':'actual full native member, full ROOT frame and second-set rows at window opening and strictly before family first observation; all interval group/price/external rows remain queryable; no claim that two snapshots exhaust all dynamic patterns'}
assert count==1498
(OUT/'prebirth-context-report.json').write_text(json.dumps(report,indent=2))
db.execute('insert or replace into metadata values (?,?)',('prebirth_context_report',json.dumps(report)));db.commit();db.close()
print(json.dumps(report),flush=True)


