import sqlite3,json,re,time,collections,functools,gzip,base64,datetime
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
# Pass 1 — collect selection IDs belonging to each handle group
handle_sids={'level_event_key':set(),'structural_metadata':set(),'book_side_tautology':set()}
BOOK_SIDE_PARENTS=('ask_levels_full','bid_levels_full')
for sid,col in c.execute('select selection,column_name from labels where keep_field(column_name)'):
 l=leaf(col)
 if l in ('level_event_key','level_event_key_at_exit'):
  handle_sids['level_event_key'].add(sid)
 if l in ('legacy_rows','source_missing_fields','source_null_fields','continuity_segment'):
  handle_sids['structural_metadata'].add(sid)
 if l=='side' and any(p in col for p in BOOK_SIDE_PARENTS):
  handle_sids['book_side_tautology'].add(sid)
print('PROGRESS pass1 done',{h:len(s) for h,s in handle_sids.items()},flush=True)
# Build reverse index sid -> [handles] for fast pass-2 lookup
sid_to_handles=collections.defaultdict(list)
for h,sids in handle_sids.items():
 for sid in sids:
  sid_to_handles[sid].append(h)
print('PROGRESS reverse index built unique_sids=',len(sid_to_handles),flush=True)
# Pass 2 — co-occurring kept conditions, handle leaf fields excluded from their own group output
HANDLE_EXCLUDE={
 'level_event_key':frozenset(['level_event_key','level_event_key_at_exit']),
 'structural_metadata':frozenset(['legacy_rows','source_missing_fields','source_null_fields','continuity_segment']),
 'book_side_tautology':frozenset(['side']),
}
cooccur={h:collections.Counter() for h in handle_sids}
for sid,col,val in c.execute('select selection,column_name,value_text from labels where keep_field(column_name)'):
 hs=sid_to_handles.get(sid)
 if hs:
  l=leaf(col)
  for h in hs:
   if l not in HANDLE_EXCLUDE[h]:
    cooccur[h][(l,val)]+=1
print('PROGRESS pass2 done',flush=True)
report={
 'run_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'seconds':round(time.monotonic()-start,2),
 'handle_selection_counts':{h:len(s) for h,s in handle_sids.items()},
 'interpretation':'For each handle group, co-occurring kept conditions on the same selections. Handle leaf fields are excluded from their own group output. Count = label occurrences (may exceed unique selections when a kept field appears multiple times per observation, e.g. N book levels).',
 'conjunction_results':{
  h:[{'leaf_field':f,'value':v,'count':n} for (f,v),n in ctr.most_common(1000)]
  for h,ctr in cooccur.items()
 }
}
path='/tmp/codex-sqlite-conjunction-20261022.json'
with open(path,'w') as f: json.dump(report,f,indent=2)
print('SUMMARY',json.dumps({k:v for k,v in report.items() if k!='conjunction_results'}),flush=True)
print('EXPORT_BASE64',base64.b64encode(gzip.compress(json.dumps(report).encode())).decode(),flush=True)
