# Codex drop-in: SQLite schema + triage queries — October 22 2026

**Author of this drop-in:** Claude (S115 session, October 22 2026)  
**Work belongs to:** Greg Davis, DavisAI Markets

**What this asks you to do:** Start the main box (read-only), inspect the two SQLite schemas,
run two queries that skip all the already-classified noise, paste the output. Nothing else.
No compute, no catalog edits, no service start.

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
source_day, source_role, source_dbn_object

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

## 3. Schema first — stop here and paste output before running queries

```bash
CELLS='/opt/frankie-box/work/experiment-search/20231018/cycle-00/discovery.partial/recovery/indexed-v1/cells.sqlite'
TASKS='/opt/frankie-box/work/experiment-search/20231018/cycle-00/discovery.partial/recovery/factored-v2/group-tasks-finite-2-6.sqlite'

sqlite3 -readonly "$CELLS" ".schema"
echo "--- TASKS ---"
sqlite3 -readonly "$TASKS" ".schema"
```

**Paste the full output here. Do not proceed to the queries until the schema is confirmed.**
The table names, column names and join structure below are placeholders.
Fill them in from the actual schema before running anything.

---

## 4. Query A — What field names survive the filter?

Purpose: see what is actually left once the known noise is excluded. Returns one row per
surviving field name and how many distinct selections it has. Should be a short list.

```sql
-- Run against cells.sqlite
-- Replace <selections_table> and <field_name_col> with real names from .schema

SELECT   <field_name_col>        AS field_name,
         COUNT(*)                AS selection_count
FROM     <selections_table>
WHERE    <field_name_col> NOT IN (
    'order_id','order_ids','causing_order_ids','filled_order_ids',
    'cancelled_fill_order_ids','modified_fill_order_ids',
    'same_id_cancel_modify_order_ids','unresolved_fill_order_ids',
    'fill_order_ids','matched_order_ids','unresolved_order_ids',
    'member_id','candidate_id','structure_id','runway_id',
    'attributed_to_episode_ids','node_id','parent_id',
    'cursor','input_cursor','input_index','input_record_indices',
    'input_ordinal','ordinal','group_ordinal','group_index',
    'source_member_index','legacy_row_ordinal',
    'publisher_id','channel_id','session_id','run_id','request_id',
    'hash','sha256','digest',
    'instrument_id','symbol','raw_symbol',
    'source_day','source_role','source_dbn_object'
)
GROUP BY <field_name_col>
ORDER BY selection_count DESC;
```

---

## 5. Query B — How many groups survive, and show the first 20

Purpose: count the groups that have at least one condition outside the set-aside list,
then show the first 20 in full so Greg can read them.

```sql
-- Run against group-tasks-finite-2-6.sqlite joined to cells.sqlite
-- ATTACH cells.sqlite first:
--   ATTACH DATABASE '/path/to/cells.sqlite' AS catalog;
-- Then replace placeholder names from .schema

-- Count of surviving groups
SELECT COUNT(DISTINCT gc.<group_id_col>) AS surviving_groups
FROM   <group_conditions_table>  gc
JOIN   catalog.<selections_table> s  ON gc.<selection_id_col> = s.<selection_id_col>
WHERE  s.<field_name_col> NOT IN (
    'order_id','order_ids','causing_order_ids','filled_order_ids',
    'cancelled_fill_order_ids','modified_fill_order_ids',
    'same_id_cancel_modify_order_ids','unresolved_fill_order_ids',
    'fill_order_ids','matched_order_ids','unresolved_order_ids',
    'member_id','candidate_id','structure_id','runway_id',
    'attributed_to_episode_ids','node_id','parent_id',
    'cursor','input_cursor','input_index','input_record_indices',
    'input_ordinal','ordinal','group_ordinal','group_index',
    'source_member_index','legacy_row_ordinal',
    'publisher_id','channel_id','session_id','run_id','request_id',
    'hash','sha256','digest',
    'instrument_id','symbol','raw_symbol',
    'source_day','source_role','source_dbn_object'
);

-- First 20 surviving groups — all their conditions shown
SELECT   gc.<group_id_col>,
         s.<field_name_col>   AS field,
         s.<field_value_col>  AS value
FROM     <group_conditions_table>  gc
JOIN     catalog.<selections_table> s ON gc.<selection_id_col> = s.<selection_id_col>
WHERE    gc.<group_id_col> IN (
    SELECT DISTINCT gc2.<group_id_col>
    FROM   <group_conditions_table>   gc2
    JOIN   catalog.<selections_table> s2 ON gc2.<selection_id_col> = s2.<selection_id_col>
    WHERE  s2.<field_name_col> NOT IN (
        'order_id','order_ids','causing_order_ids','filled_order_ids',
        'cancelled_fill_order_ids','modified_fill_order_ids',
        'same_id_cancel_modify_order_ids','unresolved_fill_order_ids',
        'fill_order_ids','matched_order_ids','unresolved_order_ids',
        'member_id','candidate_id','structure_id','runway_id',
        'attributed_to_episode_ids','node_id','parent_id',
        'cursor','input_cursor','input_index','input_record_indices',
        'input_ordinal','ordinal','group_ordinal','group_index',
        'source_member_index','legacy_row_ordinal',
        'publisher_id','channel_id','session_id','run_id','request_id',
        'hash','sha256','digest',
        'instrument_id','symbol','raw_symbol',
        'source_day','source_role','source_dbn_object'
    )
    LIMIT 20
)
ORDER BY gc.<group_id_col>, s.<field_name_col>;
```

---

## 6. If conditions are not in a standard join table

If `.schema` shows conditions stored as a JSON column or binary blob (not a normal join table),
stop and paste the schema. Do not attempt to write a Python loop over 1.5M rows without
confirming that approach first. A JSON-column query using SQLite's `json_each()` function
may still be fast; a raw Python deserialization loop may not be.

---

## 7. Stop the box when done

```bash
python3 deploy/aws/ec2_host.py --instance i-035994afa8bdf66a5 --region us-east-1 stop
```

Total expected box time: under 15 minutes if schema shows standard SQL join tables.
If schema shows something unexpected, stop the box after step 3 and report back.
