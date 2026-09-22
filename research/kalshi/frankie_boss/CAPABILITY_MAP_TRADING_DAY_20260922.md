# Capability Map: the cycle-0 rerun on the CME TRADING DAY (2026-09-22)

Greg's word (02:xxZ 09-22, verbatim, in order):
- "It's just one trading day but it starts on Sunday and ends on Monday. We have been breaking up the days incorrectly
  for a while. We need to start following trading days."
- "Rerun starts on Sunday and ends at 5pm Monday for 23 hrs"
- "You aren't pulling from bento are you? If you are stop"
- "All of the data should already be in aws and the 4 days should be ingested already. So take the Monday hrs from the
  ingested block"
- "Override the runner problem on this run"
- Earlier (01:5xZ): "57,027 is the one measurement. Sunday plus Monday to the halt is a new count. This number will go up.
  A trade day runs from the prior day at 6 pm to 5pm on the trade day."

## What is measured (not assumed)
- NO Databento pull is happening or possible from here: the repository secret DATABENTO_API_KEY is ABSENT (measured by the
  01:32Z probe, names only), this container carries no key, the pull-capable workflows are dispatch-only or branch-filtered
  to two old chatgpt branches, and the pipeline installs databento-dbn only to DECODE the .dbn.zst files already in S3.
  Nothing has run on the host, box, Pod or endpoint in this chat.
- The data IS in AWS: `s3://bento-568968024170-us-east-2-an/frankie/block_20211004_20211006/sources/` holds the four
  members (2021-10-03: 57,027 records; 10-04: 1,994,358; 10-05: 2,111,930; 10-06: 2,308,160; 6,471,475 total), pinned by
  `blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json` (manifest hash 75c7134d..., halt hour 21Z, halt boundaries and
  member seams close groups, causal clock ts_recv_ns).
- The block is STAGED, NOT INGESTED on record: the manifest says `ingested: false`; the 2026-09-18 handoff says
  `ingested: false, prefixes_built: false, scheduled: false`; no compact container for the block exists in any record.
  The ingest tool exists (`operations/ingest_block_sources.py`: one continuous stream into the compact container, no 2 TB
  raw journal, `--session-policy cme_trading_day`, 2026-09-16). If a box holds a container the record does not know,
  the box inventory probe will show it (on Greg's go); otherwise the ingest is ONE run of that tool on a box, reading
  S3, not Databento.
- The Sunday hours are already the cycle-0 source (the 20211003 member = the 57,027 measurement, 22:00Z Sunday = 18:00 ET
  open). The Monday hours are the 20211004 member's records BEFORE the 21:00Z halt (17:00 ET); records at or after the halt
  belong to Tuesday's trading day and are excluded. The trading-day count = 57,027 + those Monday records, measured at
  ingest, reported to Greg.
- The Sunday-only assumption is hard-coded in code (a sweep, 2026-09-22): `57027` and `19` steps and "full Sunday source"
  in `build_remaining_sunday_prefixes.py` (lines 221-225, 255, 333, 391-395), `run_actual_sunday.py` (351-353, 452, 581),
  `run_actual_sunday_compact_source.py` (105), `seal_final_prelaunch_candidate.py` (63-64), `run_journal_stack.py`
  (77, 85), `parallel_source/verify_snapshot.py` (26, 224), `sunday_execution.py` (208), `source_contract_runtime.py`
  (21), `day_pipeline.py` (237), `verified_sunday_schedule.py` (12, 29: `source_dates_required`), `selected_source_scope.py`
  (17); the box driver's source object carries ONE UTC day (`journal:<day>:<container>`, `frankie_box_bedrock.py`
  132-154). These are the places where the UTC-day split lives; the trading day replaces the day.

## ASSUMPTIONS I'M MAKING (correct me now or I proceed with these)
1. "Override the runner problem on this run" = the host runner's refusal on the re-pinned code bytes (the binding and the
   19 seeds pin the sha256 of context_session.py and sunday_native_runtime.py): for this rerun the prefix batch is
   RE-PINNED (the 2026-09-20 precedent, `frankie_host_rebuild_prefix_batch.yml`) so the runner accepts the advanced
   checkout. It is NOT a bypass of any data gate (source hashes, schedule digest, journal identity stay enforced).
2. The trading day is 2021-10-04 (trade date), open Sunday 2021-10-03 22:00Z, halt Monday 2021-10-04 21:00Z, 23 hours;
   the `cme_trading_day` session policy already in the ingest tool is the definition, and the halt closes an F_LAST group.
3. The ingest is of the trading day only from the staged block's first two members (Sunday whole; Monday to the halt);
   the two later members stay staged for the next trading days (Tuesday = Monday 22:00Z to Tuesday 21:00Z, and so on).
4. The rerun of cycle 0 = the FIRST cycle of the trading-day schedule, from the Sunday open, on the row window the
   schedule declares (`model_context_rows`, Greg's number; the code carries none). A 23-hour day is many cycles.
5. Everything reads S3; nothing pulls from Databento; the box's role reads nothing in S3 so the sources reach the box
   by presigned map as today.

## The map

| Module id | Responsibility | Depends on |
|---|---|---|
| trading-day-ingest | The staged block's Sunday and Monday members ingested as ONE continuous stream under `cme_trading_day` into a compact container cut at the 21:00Z halt; the count measured and receipted; the container pinned in S3 | - |
| trading-day-schedule | The trading-day schedule (cutoffs over the 23 hours), prefixes (derivable seeds, the declared `model_context_rows`) and binding; the `57027`/`19`/one-date/"full Sunday" gates become the schedule's own declared counts and dates | trading-day-ingest |
| trading-day-host | The host chain minting cycle 0's request on the trading day: the runner's Sunday gates read the declared counts; the code pins re-minted (assumption 1); the request carries the trading-day stream | trading-day-schedule |
| trading-day-box | The box session on a trading-day request: the driver's source object per TRADING DAY (not UTC day); the bedrock traversal, the ledgers and the V6 digest at 2 million rows (per-layer streaming; the candidate lane fires on the day) | trading-day-schedule |

Build order: trading-day-ingest -> trading-day-schedule -> trading-day-host, trading-day-box (in parallel) -> the full
rerun order (handoff 01:3xZ 09-22, steps 0-9, with 1b).

Every module gets its own spec (`SPEC-trading-day-<id>.md`) after Greg reviews this map. No build, no run, no ingest
before his word on the map and the assumptions.
