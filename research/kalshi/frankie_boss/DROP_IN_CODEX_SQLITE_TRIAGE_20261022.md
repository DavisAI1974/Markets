# Codex drop-in: SQLite triage — October 22 2026 (SCHEMA CONFIRMED, TRIAGE RAN)

**Author of this drop-in:** Claude (S115 session, October 22 2026)  
**Work belongs to:** Greg Davis, DavisAI Markets

**STATUS AS OF OCTOBER 22 2026:** Schema confirmed. Triage script ran on the main box.
Full results are in `/tmp/codex-sqlite-triage-20261022.json` on i-035994afa8bdf66a5.
The box is now stopped. When the box is next available, start the retrieval section below.

**What we are actually after — the conjunctions.** A group with two or more surviving
conditions is a conjunctive hypothesis: "find observations where condition A AND condition B
are both true simultaneously." The 18 calculation areas tell us what each field means. They
do not tell us which fields were combined together into a single group definition. That only
exists in the SQLite. Those combinations are the actual hypotheses the experiment search was
testing. Seeing which conjunctions dominate — and whether they cross calculation area
boundaries — is the informative output. The raw count of set-aside groups is secondary.

---

## Already classified — do not query these

We established these field classes on paper. There is no value in scanning them.
Any group whose conditions involve only these fields is set aside. Skip them entirely.

**Order IDs and references:**
order_id, order_ids, causing_order_ids, filled_order_ids, cancelled_fill_order_ids,
modified_fill_order_ids, same_id_cancel_modify_order_ids, unresolved_fill_order_ids,
fill_order_ids, matched_order_ids, unresolved_order_ids

**Other literal identities:**
member_id, candidate_id, structure_id, runway_id, attributed_to_episode_ids,
node_id, parent_id

**Storage positions (slot numbers, ordinals — not market conditions):**
cursor, input_cursor, input_index, input_record_indices, input_ordinal, ordinal,
group_ordinal, group_index, source_member_index, legacy_row_ordinal

**Infrastructure:**
publisher_id, channel_id, session_id, run_id, request_id

**Integrity:**
hash, sha256, digest (and any field ending in _hash or _sha256)

**Pure instrument scope:**
instrument_id, symbol, raw_symbol

**Calendar labels (day-of-week, date, session labels — context only, not market behavior):**
source_day, source_role, source_dbn_object, trading_day, trading_weekday

---

## CONFIRMED SCHEMA (do not re-run .schema — already verified)

**cells.sqlite** — 33,792,499,712 bytes (~31 GB)
- `labels (original PK, key BLOB UNIQUE, selection INT, whole INT, column_name TEXT, value_text TEXT, body BLOB, pin BLOB)`
- `selections (id PK, digest BLOB UNIQUE, size INT, body BLOB, pin BLOB)`
- `metadata (key TEXT PK, value TEXT)`, `ordering (ordinal PK, original UNIQUE)`
- Indexes: `labels_order ON labels(whole,column_name,value_text)`, `labels_selection ON labels(selection)`

**group-tasks-finite-2-6.sqlite** — 110,800,896 bytes (~106 MB)
- `tasks (ordinal PK, body BLOB, pin BLOB)`, `metadata (key TEXT PK, value TEXT)`
- NO join table. NO selection_id column. Conditions are NOT queryable by SQL JOIN.

**Critical discovery:** Each task row is a SHA-256-pinned pickle of `(ordinal, (selection_id, None))`.
The "group" is a single observation mask (selection_id). Its conjunction is all field/value labels
for that selection in cells.sqlite. The original drop-in's SQL JOIN approach was architecturally wrong
and cannot work. Use the Python approach below.

---

## 1. Credentials

```bash
source ~/.config/markets/env
python3 -c "import boto3; s=boto3.client('sts',region_name='us-east-1'); print(s.get_caller_identity()['Account'][-4:])"
# Expected: 4170
```

---

## 2. Start main box only

```bash
cd /home/user/Markets
python3 deploy/aws/ec2_host.py --instance i-035994afa8bdf66a5 --region us-east-1 start
```

Do NOT start i-0d17573dbce871520 (helper) or i-031eeb577ad72b064 (calculation).

---

## 3. Retrieve the triage results (primary action)

The triage script already ran. Results are in `/tmp/codex-sqlite-triage-20261022.json`.
/tmp survives across sessions on this box as long as the instance has not been terminated.
Start with the retrieval. If the file is gone (instance was terminated, not stopped), go to
section 4 to re-run.

```bash
# Verify the file is still there
ls -lh /tmp/codex-sqlite-triage-20261022.json

# Print the summary (excludes the large arrays)
python3 -c "
import json
with open('/tmp/codex-sqlite-triage-20261022.json') as f:
    r = json.load(f)
skip = {'field_counts','first_20_tasks','excluded','normalized_label_counts'}
print(json.dumps({k:v for k,v in r.items() if k not in skip}, indent=2))
"

# Print the top 30 surviving fields by distinct_selections
python3 -c "
import json
with open('/tmp/codex-sqlite-triage-20261022.json') as f:
    r = json.load(f)
for row in r['field_counts'][:30]:
    print(f\"{row['distinct_selections']:>8}  {row['field']}\")
"

# Print the full normalized label counts (leaf field names after stripping array indices)
python3 -c "
import json
with open('/tmp/codex-sqlite-triage-20261022.json') as f:
    r = json.load(f)
for name, count in r['normalized_label_counts']:
    print(f'{count:>10}  {name}')
"

# Print the first 20 surviving tasks in full
python3 -c "
import json
with open('/tmp/codex-sqlite-triage-20261022.json') as f:
    r = json.load(f)
print(json.dumps(r['first_20_tasks'], indent=2))
"
```

Paste all four outputs. Then stop the box.

---

## 4. Re-run triage if /tmp was cleared

Only run this if the JSON file from section 3 is missing.
This script is the exact approach Codex already validated. Runtime: ~2-5 minutes.

```python
# Save as /tmp/triage_rerun.py and run: python3 -I /tmp/triage_rerun.py
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
surviving=set()
normalized=collections.Counter()
for sid,col in c.execute('select selection,column_name from labels where keep_field(column_name)'):
    surviving.add(sid)
    normalized[leaf(col)]+=1
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
path='/tmp/codex-sqlite-triage-20261022.json'
with open(path,'w') as f: json.dump(report,f,indent=2)
print('DONE',path,'task_count',n,'surviving',hist['surviving_tasks'])
```

Note: `trading_day` and `trading_weekday` are added to the exclusion list vs. the original run.
If re-running to compare with the original output, remove them from the excluded set for that run.

---

## 5. What the schema discovery changed

The original drop-in (sections 3-6 below this note) assumed a SQL join table linking tasks to
selections. That assumption was wrong. The actual tasks table stores only:
  `ordinal INTEGER PRIMARY KEY, body BLOB NOT NULL, pin BLOB NOT NULL`

Each body is a SHA-256-pinned pickle of `(ordinal, (selection_id, None))`. There is no
group_id column, no selection_id column, no join table. The correct approach is Python
deserialization, which is what the triage script already does. Do not attempt SQL queries
against tasks to find conjunctions — they will find nothing.

---

## 7. Stop the box when done

```bash
python3 deploy/aws/ec2_host.py --instance i-035994afa8bdf66a5 --region us-east-1 stop
```

Total expected box time: under 15 minutes if schema shows standard SQL join tables.
If schema shows something unexpected, stop the box after step 3 and report back.
