# SQLite Triage Handoff — 2026-10-22

**Session branch**: `claude/first-run-using-agent-skills-bd52fj`
**Boxes**: ALL THREE STOPPED. Do not restart without Greg's explicit go.
- Main: i-035994afa8bdf66a5
- Helper: i-0d17573dbce871520
- Calculation: i-031eeb577ad72b064

---

## What we did

Read-only triage of the SQLite catalog from a stopped Frankie experiment box.

**Source path (on box, do not touch)**:
```
/opt/frankie-box/work/experiment-search/20231018/cycle-00/discovery.partial/recovery/indexed-v1/cells.sqlite
```

The file is 31 GB. We ran everything as read-only (`mode=ro`, `pragma query_only=on`). No writes, no application changes, no box restarts.

**Triage scripts committed to repo**:
- `artifacts/sqlite-triage/20261022/exports/triage_*.py` — initial field surveys, schema dump, top-100 fields
- `research/kalshi/frankie_boss/conjunction_query_20261022.py` — the main conjunction query sent to Codex via SSM

**All results pushed by Greg (commit `cb3534bf`)**:
- `artifacts/sqlite-triage/20261022/exports/` — schema, field surveys, CSV exports
- `artifacts/sqlite-triage/20261022/queries/conjunction-uncapped-results.json` — 585 KB, the full conjunction output

The conjunction script ran on the box in 159 seconds and produced no minimum-count threshold — every co-occurring (field, value) pair is present in the output, uncapped.

---

## What the conjunction query found

### Schema recap

**`cells.sqlite`** has one primary table: `labels(selection INT, column_name TEXT, value_text TEXT, body BLOB, pin BLOB)`. A `selection` is a row ID grouping all condition labels for one observation. There are no primary keys on `labels`; the only index is `labels_selection ON labels(selection)`.

The conjunction query uses three **handle groups** — fields whose presence defines a class of selection — and then counts every other field/value pair that co-occurs on those same selections.

---

### Handle group 1: `level_event_key`

**277,965 selections** carry `level_event_key` or `level_event_key_at_exit`.

These are the main experiment observations — tracked lifecycle events for order-window families.

**Top findings (from the conjunction output)**:

| leaf_field | value | count | interpretation |
|---|---|---|---|
| family_id | (748 distinct `ow-...` IDs) | varies | Every observation belongs to one family. 748 total distinct families in this experiment. |
| event_type | REQUEUE_PRICE_CHANGED | dominant | Most events are price-change requeue events, not fills or cancels |
| status | CENSORED_SEGMENT_END | high | Many segments end at a censorship boundary (experiment cut-off, not natural termination) |
| action | various cancel/fill/trade codes | — | Standard MBO lifecycle actions |
| timestamps | `2023-10-10`, `2023-10-13T15:30:00-04:00` | — | Observation window is ~Oct 10-13, 2023 |
| instrument / symbol | NGX3, NGZ3 | — | November 2023 and December 2023 NG futures contracts |

**The 748 family IDs** are all `ow-` prefixed opaque identifiers (order-windows or observation-windows). The conjunction output lists each one by co-occurrence count. The top families by appearance count represent the most-observed tracking windows in this experiment run.

---

### Handle group 2: `structural_metadata`

**495 selections** carry `legacy_rows`, `source_missing_fields`, `source_null_fields`, or `continuity_segment`.

These are not market events — they are bookkeeping rows that describe the structure of the data pipeline.

**Two distinct sub-populations**:
1. **~2,581-appearance cluster**: no-trade time bins. These rows record time windows where no trade activity occurred. The high repeat count indicates a regular time-grid structure.
2. **~692-appearance cluster**: book refill rows. These record moments when the order book was rebuilt from scratch (e.g., after a connection reset or session boundary).

These selections are structurally important but carry no direct market signal. They mark the boundaries and gaps in the data stream.

---

### Handle group 3: `book_side_tautology`

**248 selections** carry `side` fields descending from `ask_levels_full` or `bid_levels_full`.

These are energy market context rows that record the full order book state at the time of an observation.

**Top findings**:

| leaf_field | value | count | interpretation |
|---|---|---|---|
| side | M (Market maker) | dominant | Most book-level entries are market-maker posted quotes |
| instrument | NGX3, NGZ3 | — | Same Oct 2023 NG contracts |
| timestamps | same Oct 2023 window | — | Consistent with the level_event_key group |

The `side='M'` dominance is expected in a NG futures order book — the resting limit order book is populated almost entirely by market makers, not aggressive takers. Aggressive/taker flows appear as trades, not book levels.

---

## The 99 planes

"99 planes" = **99 registered Frankie layers** from the A_MEMORY inventory.

Source: `research/kalshi/frankie_boss/handoffs/20260915/FRANKIE_BOSS_NEXT_CHAT_HANDOFF.md`

Breakdown:
- 22 static layers
- 55 causal layers
- 9 sealed layers
- 2 optional shadow layers
- 10 append-only output layers (6 obsolete roles retired from a larger set)
- 98 applicable to A_MEMORY (1 reserved/excluded)

These are the input planes Frankie reads when building its context packet for Granite. They are not files on disk in the traditional sense — they are logical views materialized from the substrate for each inference cycle.

---

## The 13 data files

The exact identity of "13 data files" is **not yet resolved**. Three candidates:

1. **13 variable MBOMsg fields**: From the BOSS handoff — "245 raw actions preserve all 13 variable MBOMsg fields." These are the 13 per-message fields from Databento's MBO schema that vary at runtime (as opposed to static header fields). If this is the right interpretation, the 13 files are not files but fields within each action record.

2. **13 Granite model files**: The Granite 3.3 8B model as loaded has a multi-file checkpoint structure. "13 files" could refer to the model weight shards.

3. **13 experiment input data files**: The experiment at `20231018/cycle-00/` may have been staged from exactly 13 source data files. The `sources/` directory in `artifacts/sqlite-triage/20261022/` may clarify this — not yet fully read.

**Resolution plan**: Read `artifacts/sqlite-triage/20261022/sources/` and cross-reference with the BOSS handoff's data staging records. Also check `research/kalshi/frankie_boss/operations/` for the day_pipeline receipts for the 20231018 run.

---

## What we want to do

### 1. Pin the 13 data files to the Oct 2023 time span

The families span approximately **Oct 10-13, 2023**. The training source is `glbx-mdp3-20211003.mbo.dbn.zst` (Oct 3, 2021 — the Sunday principal run). The experiment observation window is Oct 2023.

We need to:
- Confirm the exact first and last timestamp in the `level_event_key` group (a time-span query on `cells.sqlite`)
- Map those timestamps against the 13 data files / MBOMsg fields to understand what data was being served when these families were being tracked

### 2. Pin the 99 layers to that same window

For each of the 99 registered Frankie layers, determine:
- Which layers were active/serving during Oct 10-13, 2023
- What values those layers held at the specific timestamps of the top families
- Which layers include dipole and exhaustion data (these are causal layers in the 55-causal group)

This means reading the A_MEMORY inventory in detail and cross-referencing layer names against what the conjunction output reveals.

### 3. Dipole and exhaustion data for Oct 2023

The dipole mathematics (divergence, exhaustion) are part of Frankie's causal layers. The relevant question is: what were the actual dipole state values during the Oct 10-13, 2023 window when the 748 families were being tracked?

If the box's SQLite catalog captured these as condition labels, they will appear as co-occurring conditions under the family_id selections in a per-family profile query.

---

## Next plans (specific queries to run)

All queries are **read-only**. All boxes remain **stopped**. These queries need SSM access when Greg authorizes a box restart, or they can be run if the cells.sqlite file is transferred to a local environment.

### Query A: Time span extraction

Get the exact min and max timestamps for the level_event_key group:

```sql
SELECT
  MIN(value_text) AS earliest_ts,
  MAX(value_text) AS latest_ts,
  COUNT(DISTINCT selection) AS selection_count
FROM labels
WHERE selection IN (
  SELECT DISTINCT selection FROM labels
  WHERE keep_field(column_name)
    AND (
      column_name LIKE '%level_event_key%'
      OR column_name LIKE '%level_event_key_at_exit%'
    )
)
AND (column_name LIKE '%ts%' OR column_name LIKE '%time%' OR column_name LIKE '%timestamp%')
```

### Query B: Per-family profile for the top 20 families

For each of the top 20 ow-... family IDs by appearance count, pull every co-occurring condition:

```sql
-- Replace FAMILY_ID_VALUE with each target ow-... string
SELECT
  column_name,
  value_text,
  COUNT(*) AS cnt
FROM labels
WHERE selection IN (
  SELECT DISTINCT selection FROM labels
  WHERE column_name LIKE '%family_id%'
    AND value_text = 'FAMILY_ID_VALUE'
)
GROUP BY column_name, value_text
ORDER BY cnt DESC
LIMIT 500
```

Run this for the top 20 family IDs from the conjunction output. Each profile will show what conditions — including dipole state, exhaustion flags, order book state, and Frankie layer values — co-occurred with that family across all its tracked selections.

### Query C: Dipole and exhaustion layer identification

Search the labels for any field names that match the Frankie dipole/exhaustion layer naming conventions:

```sql
SELECT DISTINCT column_name, value_text
FROM labels
WHERE column_name LIKE '%dipole%'
   OR column_name LIKE '%exhaustion%'
   OR column_name LIKE '%divergence%'
   OR column_name LIKE '%imbalance%'
   OR column_name LIKE '%flow%'
LIMIT 1000
```

This will reveal whether the cells.sqlite catalog captured dipole and exhaustion state as selectable conditions, and if so, what their field paths are.

### Query D: Layer inventory cross-reference

Once we have the full A_MEMORY layer list from the BOSS handoff, build a targeted query that checks for each layer name whether it appears in the labels catalog:

```sql
SELECT
  column_name,
  COUNT(DISTINCT selection) AS selection_count,
  COUNT(*) AS label_count
FROM labels
WHERE column_name LIKE '%LAYER_NAME%'
GROUP BY column_name
ORDER BY label_count DESC
```

Run this for each of the 99 layer names to map which planes are represented in the SQLite triage data.

---

## What we do NOT do

- No box restarts without Greg's explicit go
- No application code changes
- No catalog changes
- No production regrouping or new scientific calculations
- No BuildMap, no duplication of downstream assignments
- No averaging, smoothing, rarity penalties, or arbitrary caps on query results
- No writes to any database — all queries are read-only with `mode=ro` and `pragma query_only=on`
- No arbitrary capping of results — the conjunction query was run uncapped intentionally; keep that discipline on all future queries

---

## Files in play

| File | Purpose | Location |
|---|---|---|
| `cells.sqlite` | 31 GB conditions catalog (on stopped box) | box:/opt/frankie-box/work/experiment-search/20231018/cycle-00/discovery.partial/recovery/indexed-v1/ |
| `conjunction-uncapped-results.json` | Full conjunction output, 585 KB | `artifacts/sqlite-triage/20261022/queries/` |
| `conjunction_query_20261022.py` | The query script (committed) | `research/kalshi/frankie_boss/` |
| `FRANKIE_BOSS_NEXT_CHAT_HANDOFF.md` | 99-layer inventory reference | `research/kalshi/frankie_boss/handoffs/20260915/` |
| This file | Triage handoff | `research/kalshi/frankie_boss/SQLITE_TRIAGE_HANDOFF_20261022.md` |

---

## Open questions

1. **What exactly are the 13 data files?** Candidates: 13 MBOMsg variable fields, 13 Granite weight shards, or 13 experiment input source files. Check `artifacts/sqlite-triage/20261022/sources/` and the 20231018 day pipeline receipts.

2. **What is the exact Oct 2023 time span?** Query A above will answer this.

3. **What dipole and exhaustion values were served during that window?** Query C will reveal whether these layers are present in the catalog. Query B on top families will show what dipole state accompanied high-count families.

4. **Which of the 99 layers are represented in cells.sqlite?** Query D will map this. Not all 99 may appear as selectable conditions — some are output-only or sealed.

5. **What distinguishes high-count families from low-count ones?** Running Query B on both ends of the count distribution (top 10 and bottom 10) will characterize what makes a family appear many times vs few times in the experiment.
