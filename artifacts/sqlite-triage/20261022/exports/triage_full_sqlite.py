import sqlite3,json,hashlib,pickle,io,re,time,collections,functools
base='/opt/frankie-box/work/experiment-search/20231018/cycle-00/discovery.partial/recovery/'
c=sqlite3.connect('file:'+base+'indexed-v1/cells.sqlite?mode=ro',uri=True)
c.execute('pragma query_only=on')
excluded=set('order_id order_ids causing_order_ids filled_order_ids cancelled_fill_order_ids modified_fill_order_ids same_id_cancel_modify_order_ids unresolved_fill_order_ids fill_order_ids matched_order_ids unresolved_order_ids member_id candidate_id structure_id runway_id attributed_to_episode_ids node_id parent_id cursor input_cursor input_index input_record_indices input_ordinal ordinal group_ordinal group_index source_member_index legacy_row_ordinal publisher_id channel_id session_id run_id request_id hash sha256 digest instrument_id symbol raw_symbol source_day source_role source_dbn_object trading_day trading_weekday whole-day'.split())
@functools.lru_cache(None)
def leaf(col): return re.sub(r'\[[^]]*\]','',col.rsplit('.',1)[-1])
@functools.lru_cache(None)
def keep(col):
 f=leaf(col)
 return f not in excluded and not f.endswith(('_hash','_sha256'))
c.create_function('keep_field',1,keep,deterministic=True)
start=time.monotonic()
fields=list(c.execute('select column_name,count(distinct selection),count(*) from labels where keep_field(column_name) group by column_name order by 2 desc,1'))
print('PROGRESS field counts complete',len(fields),flush=True)
surviving=set()
normalized=collections.Counter()
for sid,col in c.execute('select selection,column_name from labels where keep_field(column_name)'):
 surviving.add(sid)
 normalized[leaf(col)]+=1
print('PROGRESS label scan complete',len(surviving),flush=True)
t=sqlite3.connect('file:'+base+'factored-v2/group-tasks-finite-2-6.sqlite?mode=ro',uri=True)
t.execute('pragma query_only=on')
class Primitive(pickle.Unpickler):
 def find_class(self,module,name): raise ValueError('nonprimitive pickle')
hist=collections.Counter();first=[];n=0
for ordinal,body,pin in t.execute('select ordinal,body,pin from tasks order by ordinal'):
 if hashlib.sha256(body).digest()!=pin: raise ValueError('task pin mismatch')
 saved,value=Primitive(io.BytesIO(body)).load()
 if saved!=ordinal or not isinstance(value,tuple) or len(value)!=2 or value[1] is not None: raise ValueError('unexpected task format')
 sid=value[0]
 n+=1
 if sid in surviving:
  hist['surviving_tasks']+=1
  if len(first)<20:
   labels=[dict(field=col,value=val,survives=bool(keep(col))) for col,val in c.execute('select column_name,value_text from labels where selection=? order by column_name,value_text',(sid,))]
   first.append(dict(task_ordinal=ordinal,selection_id=sid,labels=labels))
report=dict(task_count=n,surviving_tasks=hist['surviving_tasks'],surviving_catalog_selections=len(surviving),surviving_full_field_names=len(fields),field_counts=[dict(field=f,distinct_selections=s,label_count=l) for f,s,l in fields],normalized_label_counts=normalized.most_common(),first_20_tasks=first,seconds=round(time.monotonic()-start,2),interpretation='Task rows reference unique observation masks; labels on one selection are aliases, not proof of an explicit AND hypothesis.',extra_calendar_exclusions=['trading_day','trading_weekday'],excluded=sorted(excluded))
report['run_utc']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
path='/tmp/codex-sqlite-triage-full-20261022.json'
with open(path,'w') as f: json.dump(report,f,indent=2)
print('SUMMARY',json.dumps({k:v for k,v in report.items() if k not in ['field_counts','first_20_tasks','excluded','normalized_label_counts']}),flush=True)
import gzip,base64
print('EXPORT_BASE64',base64.b64encode(gzip.compress(json.dumps(report).encode())).decode(),flush=True)

