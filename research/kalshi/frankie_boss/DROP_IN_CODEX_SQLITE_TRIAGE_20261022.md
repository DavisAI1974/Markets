# Codex drop-in: SQLite schema + triage queries — October 22 2026

**Author of this drop-in:** Claude (S115 session, October 22 2026)  
**Work belongs to:** Greg Davis, DavisAI Markets  

**What this asks you to do:** Start the main box (read-only), inspect the two SQLite schemas,
run three queries, paste the output. Nothing else. No compute, no catalog edits, no service start.

---

## 1. Credentials

Credentials come from `~/.config/markets/env` (Greg drops these per session):

```bash
source ~/.config/markets/env
# Verify live — print only the account tail, never the secret
python3 -c "import boto3, os; s=boto3.client('sts',region_name='us-east-1'); print(s.get_caller_identity()['Account'][-4:])"
# Expected: 4170
```

---

## 2. Start main box only

Main box is i-035994afa8bdf66a5, us-east-1. Do NOT start helper (i-0d17573dbce871520)
or calculation (i-031eeb577ad72b064).

```bash
cd /home/user/Markets
python3 deploy/aws/ec2_host.py --instance i-035994afa8bdf66a5 --region us-east-1 start
# Waits until SSM is Online — print confirms state=running + SSM Online
```

---

## 3. Run the schema inspection via SSM

Send two sqlite3 .schema commands. The script below uses boto3 AWS-RunShellScript directly
(no existing Linux SSM runner exists; this is a one-off inline).

```python
import boto3, time, sys

INSTANCE = 'i-035994afa8bdf66a5'
REGION   = 'us-east-1'
CELLS    = '/opt/frankie-box/work/experiment-search/20231018/cycle-00/discovery.partial/recovery/indexed-v1/cells.sqlite'
TASKS    = '/opt/frankie-box/work/experiment-search/20231018/cycle-00/discovery.partial/recovery/factored-v2/group-tasks-finite-2-6.sqlite'

script = f"""
sqlite3 "{CELLS}" ".schema"
echo "---TASKS---"
sqlite3 "{TASKS}" ".schema"
"""

ssm = boto3.client('ssm', region_name=REGION)
resp = ssm.send_command(
    InstanceIds=[INSTANCE],
    DocumentName='AWS-RunShellScript',
    Parameters={'commands': [script]},
)
cmd_id = resp['Command']['CommandId']
time.sleep(5)
for _ in range(30):
    out = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE)
    if out['Status'] in ('Success', 'Failed', 'TimedOut'):
        print(out['StandardOutputContent'])
        print(out['StandardErrorContent'])
        sys.exit(0 if out['Status'] == 'Success' else 1)
    time.sleep(5)
```

**Paste the full .schema output here before writing any queries.** Table and column names are
unknown until we see it. The queries below use placeholder names — fill in the real ones.

---

## 4. Three queries (fill in real table/column names from step 3)

Save as a script, run via the same SSM pattern above.

```sql
-- QUERY 1: Count selections per field name (substitute real table name)
-- Purpose: shows how many distinct (field, value) pairs exist per field category
SELECT field_name, COUNT(*) AS selection_count
FROM   <selections_table>
GROUP  BY field_name
ORDER  BY selection_count DESC;

-- QUERY 2: Triage count — all-set-aside groups vs. groups with any real condition
-- Purpose: the single number that tells us how much survives
-- Set-aside field names (extend this list from the schema if other ID fields appear):
-- order_id, order_ids, causing_order_ids, filled_order_ids, cancelled_fill_order_ids,
-- modified_fill_order_ids, same_id_cancel_modify_order_ids, unresolved_fill_order_ids,
-- fill_order_ids, matched_order_ids, unresolved_order_ids, member_id, candidate_id,
-- structure_id, runway_id, attributed_to_episode_ids, node_id, parent_id,
-- cursor, input_cursor, input_index, input_record_indices, input_ordinal, ordinal,
-- group_ordinal, group_index, source_member_index, legacy_row_ordinal,
-- publisher_id, channel_id, session_id, run_id, request_id,
-- hash, sha256, digest,
-- instrument_id, symbol, raw_symbol,
-- source_day, source_role, source_dbn_object
WITH classified AS (
    SELECT  gc.<group_id_col>,
            CASE WHEN s.<field_name_col> IN (
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
            ) THEN 'aside' ELSE 'keep' END AS cls
    FROM   <group_conditions_table> gc
    JOIN   <selections_table>       s  ON gc.<selection_id_col> = s.<selection_id_col>
)
SELECT
    SUM(CASE WHEN max_cls = 'keep'  THEN 1 ELSE 0 END) AS groups_with_real_condition,
    SUM(CASE WHEN max_cls = 'aside' THEN 1 ELSE 0 END) AS all_conditions_set_aside,
    COUNT(*) AS total_groups
FROM (
    SELECT <group_id_col>, MAX(cls) AS max_cls   -- 'keep' > 'aside' alphabetically
    FROM   classified
    GROUP  BY <group_id_col>
);

-- QUERY 3: First 20 groups with at least one real (non-set-aside) condition
-- Purpose: first sample for Greg to read and judge
SELECT  gc.<group_id_col>,
        s.<field_name_col>,
        s.<field_value_col>,
        l.<label_text_col>   -- path / human-readable description if a labels table exists
FROM    <group_conditions_table> gc
JOIN    <selections_table>       s  ON gc.<selection_id_col> = s.<selection_id_col>
LEFT JOIN <labels_table>         l  ON l.<selection_id_col>  = s.<selection_id_col>
WHERE   gc.<group_id_col> IN (
    SELECT DISTINCT gc2.<group_id_col>
    FROM   <group_conditions_table> gc2
    JOIN   <selections_table>       s2 ON gc2.<selection_id_col> = s2.<selection_id_col>
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

## 5. Stop the box when done

```bash
python3 deploy/aws/ec2_host.py --instance i-035994afa8bdf66a5 --region us-east-1 stop
```

---

## Notes for Codex

- Do not start the helper or calculation box.
- Do not start any Frankie service or cycle.
- Do not edit any catalog or SQLite file — open sqlite3 in read-only mode (`sqlite3 -readonly`).
- The two query files are read-only targets: cells.sqlite and group-tasks-finite-2-6.sqlite.
- Paste the raw .schema output and raw query results back into the living plan
  (`research/kalshi/frankie_boss/FRANKIE_GROUPING_LIVING_PLAN_20261022.md`) before writing
  anything interpretive.
- If the schema shows the group-conditions join differently than expected (e.g. conditions are
  stored as a JSON column rather than a separate join table), paste the schema and stop — do not
  guess at a query rewrite.
