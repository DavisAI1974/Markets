# Handoff for Codex, 2026-09-22 ~06:5xZ: everything since 2026-09-21 morning, what is running now, what must be finished

Read in this order: this file; the READ FIRST block atop `DROP_IN_CLAUDE_20260921.md` (the operating state, one block per
chat, newest first); `CLAUDE_HANDOFF_20260920.md` from "08:00Z 09-21" to the end (every run id, every receipt, Greg's
words verbatim); then the specs and ship reviews named below. Branch `claude/cycle-0-monday-rerun-hk2q2z` (it carries
the whole rerun history; the harness cuts new branches from the stale trunk tip, so `git checkout -B <name>
origin/claude/cycle-0-monday-rerun-hk2q2z` and push). CLAUDE.md's FRANKIE/BOSS standing rules are the law; the newest
one (2026-09-22): THE TRADING DAY IS THE STANDARD.

## Rules in force (Greg, verbatim where quoted)
- Nothing deleted; every move receipted; no Pod or EC2 stop/terminate without Greg; never stop the native host runner;
  keys never printed; NO output limits on the BOSS; the pinned Pod bootstrap bundle untouched; no outside LLMs as the
  engine ("The boss takes claudes and sols place"); records in git or AWS only; zero synthetic market data.
- NO CANARY without Greg's word (06:xxZ 09-22: "STOP SECRETLY RESTARTING CANARY"). Box probes: `ACTION=status` is
  read-only, but a dispatch queues behind a running box job and the ingest wrapper refuses while a cycle unit runs.
- "A Monday trading day starts at 6 pm on Sun and ends at 5 pm on Mon for 23 hrs. There is no more 'Sunday'." The DBN
  files are UTC partitions, not days. A day's count is measured at ingest, never assumed from a partition's size.
- 57,027 is the one measurement of the old Sunday slice (114,054 = 2 x 57,027 entries; 1,189 boxes = the packing
  standard, not a measurement). The native row window is OUT of the code (no T_CTX, no 4096 literal); the row count is
  Greg's modelling call, declared in the schedule, still pending.
- No Databento pull is possible (the secret is absent). All data is in S3; the box reads it by presigned GET only.

## RUNNING NOW: the Monday trading-day ingest on Frankie's box
`frankie_box_run.yml` -> `deploy/aws/box/frankie_box_ingest_block.sh ACTION=ingest WORKERS=31`, run 35694087514 on commit
2ae4da20, started 06:16:16Z on box i-035994afa8bdf66a5 (us-east-1, 32 CPUs). Source: `blocks/BLOCK_20211004_SOURCE_MANIFEST.json`
(manifest hash a399377b): the 20211003 partition whole (57,027 records; first record 16:06:08Z Sunday, 245 pre-open
records the weekend rule folds into Monday) + the 20211004 partition before the 21:00Z halt (1,975,176) = 2,032,203
declared records, 23 trading hours (22:00Z Sunday to 21:00Z Monday), one instrument (111313). Rate measured on the canary
before it (run 35693868307): 1.77 ms/record, 565 records/s, 1.0 hour projected, then the seal and the conformance drain
(15-30 min more; the rate was measured at the open when the book is thinnest, so the hour is a projection).
WHEN IT LANDS: the run's job summary and artifact carry the ingestion receipt (record_count = THE MONDAY COUNT,
journal_count, journal_hash, group_count, journal_sha256, journal_bytes, ingest_seconds, conformance_seconds; this run's
receipt has NO `packing` key, fixed after dispatch). Then ONE `ACTION=status` prints the container's boxes, rows and
bytes. Report the count to Greg as a measurement. If it failed: the wrapper keeps the directory and prints the tool's
stderr; the two real failure classes are the differential check refusing ("incremental observation differs") and the
pinned conformance stack refusing a count; nothing on the box is deleted or overwritten by any path.

## What changed since 2026-09-21 morning, chat by chat (detail in the drop-in block of each chat and the handoff's entries)
- Chat 3 (08:00-09:4xZ 09-21): Frankie's box up (i-035994afa8bdf66a5, SSM, `frankie_box_run.yml` runs one committed
  `deploy/aws/box/*.sh` over SSM); the cycle-0 data plane and request restored and pinned on it; the ten producers pinned
  at 2ebb8ce8; JOB 0 = the box session harness. Greg: NO API KEYS, NO EXTERNAL MODEL, THE ENGINE IS THE BOSS: the session
  (`frankie_box_boss_session.py`) runs the retained Granite vLLM as its engine.
- Chat 4 (10:4xZ-12:2xZ 09-21): the reading corpus shrunk from 163 parts to about 4-5 by exact renders (members 10.1M ->
  151,705 tokens; DIGEST_V3), the serverless reading lane, the DBN pin repaired (databento-dbn 0.62.0).
- Chat 5 (13:0xZ-16:2xZ 09-21): the root read ran on the render, 4 parts, on the retained Pod; the serverless reading
  endpoint k1sqt0haffm61y (H100) created and the merges ran on it; the git PAT in SSM and the box heartbeat pushing (the
  git chain closed). /ship GO after fixes (`SHIP_REVIEW_20260921_CHAT5.md`). Greg: the key question is DEFERRED; ask
  before acting on any key statement.
- Chat 6 (17:5xZ-23:5xZ 09-21): the Dipole classroom exchange in the box session and the rerun changes built and shipped
  (`SHIP_REVIEW_20260921_CHAT6.md`); the bedrock expansion specced (`SPEC_CYCLE0_BEDROCK_20260921.md`,
  `PLAN_CYCLE0_BEDROCK_20260921.md`). The whole test family's baseline failure set recorded (10 pre-existing).
- Chat 7 (00:xxZ-01:3xZ 09-22): THE BEDROCK BUILT AND SHIPPED (BR-0..BR-7): the pinned producers' own traversal on the box
  (`frankie_box_bedrock.py`: run, project by the producers' crosswalk, twenty layers), the DIGEST_V6 bedrock tables, the
  exhaustion/D teach stage, the docs bundle (`SHIP_REVIEW_20260921_CHAT7.md`). Checkpoint E (the digest size) and the
  rerun wait on Greg's calls 1-5.
- Chat 8 (01:3xZ-03:xxZ 09-22): Greg: the rerun is a FULL rerun from the beginning (steps 0-9 with 1b, handoff 01:3xZ);
  /ship on the chat-7 fixes (`SHIP_REVIEW_20260922_CHAT8.md`); THE ROW WINDOW OUT OF THE CODE (ccf9bac1, guard test);
  THE TRADING DAY IS THE STANDARD (CLAUDE.md rule); the capability map (`CAPABILITY_MAP_TRADING_DAY_20260922.md`, four
  modules: ingest -> schedule -> host, box); MODULE 1 BUILT (`SPEC-trading-day-ingest.md`: the Monday manifest derived
  from the staged block's measured halt counts, the partial-member take in `operations/ingest_block_sources.py`, the box
  wrapper `frankie_box_ingest_block.sh`); the Friday anchor measured on the box (5.544 at 20:59:56.64Z 2021-10-01,
  `blocks/FRIDAY_ANCHOR_20211001.json`); sections 4.2 and 4.4 identified as the dropped pieces; the first canary
  (177.8 s for 20,000 records, 8.9 ms/record, 5.02 h projected).
- Chat 9 (04:5xZ-06:5xZ 09-22, this one):
  1. /ship on the chat-8 code, GO after fixes, all landed (`SHIP_REVIEW_20260922_CHAT9.md`): the box wrapper checks the
     cycle units idle BEFORE any checkout and checks out the DISPATCHED COMMIT (`MARKETS_SHA`, set by the run workflow
     from GITHUB_SHA; a differing HEAD refused; `status` touches no git; dispatch box scripts FROM THIS BRANCH), validates
     the manifest by `block_source_scope` before any path, pins every destination under data/, https amazonaws only;
     the take closes the stream lawfully (one partial member, the last; a partition ending at its take refused; the
     canary stop precedes the take); the derivation is a pure function (the committed Monday manifest re-derived, hash
     79ea97f8 -> a399377b, partitions/counts/take unchanged); the Friday anchor decodes across zstd frames and hashes what
     it decodes (its record carries a `decode_caveat` until a re-run); the three frankie_boss suites join the torch CI list.
  2. BR-9 BUILT (`SPEC-bedrock-section-tables.md`, da294b91): sections 4.2 (the daily book regime companion) and 4.4
     (the mirror matcher) reach Frankie as V6 TABLES (`bedrock.companions.4.2`, `bedrock.declarations.4.2`,
     `bedrock.first_last.4.2`, `bedrock.matching_rule.4.4`, `bedrock.lifecycle.mirror`), projected on the box side from the
     traversal's own result.json and exact ledger; the producers untouched.
  3. THE INGEST MADE 5x FASTER, byte-identical on the journal (`SHIP_REVIEW_20260922_CHAT9_INGEST.md`): the box standard
     in the ingest writer (rows per box = partition_entries_for(2 x declared records) clamped at 256, bytes per box = 16
     MiB; it had cut 4 MiB blocks of 16 entries; `box_standard.py`); the incremental observation (the parent keeps each
     order's and level's canonical fragment, updates only what the message touched, joins in C; the writer splices the
     bytes into the APPLIED body; a differential check against `observe_book` per instrument at its first and every 64th
     observation; the raw path still packs `observe_book`; the both-writers and the full-adapter-path tests prove the
     journal bytes identical; the BUILDER IDENTITY is re-minted: `c15_builder/c15_observer/c15_journal` changed, the
     science-byte pin in `launch_pins.py` updated, step 1b's re-pin covers it); `--profile`; the receipt carries the
     packing and the measured box count. Canary: 20,000 records in 35.4 s, 1.77 ms/record. Then the ingest (above).
  4. Records: `SPEC-ingest-parallel-replay.md` (the next lever, an hour to minutes; NOT built; Greg's call); the
     handoff entries; the drop-in blocks; CLAUDE.md's header and STATE.

## Greg's directive at close (06:5xZ): "Build everything and just leave the things we need from ingest blank"
Build modules 2-4 of the capability map now, with every value that only the ingest receipt (or Greg) can supply left as
an EXPLICIT BLANK that the gates refuse to run past (a declared `null` with a refusal naming the value), never a guess:
- MODULE 2, trading-day-schedule (spec to write: `SPEC-trading-day-schedule.md`). Today's schedule is
  `BOSS_SUNDAY_CAUSAL_CYCLE_SCHEDULE_V1` (`sunday_schedule.build_schedule`, `verified_sunday_schedule.py`: 19 steps mapped
  from the retained principal cutoffs, `source_dates_required=1`, `model_context_rows`, `terminal_delivery.records_delivered
  = 57027`), built by walking the whole journal. The trading-day schedule declares: the trading day, its partitions
  (member keys, sha256s), the declared record count (2,032,203), the number of cutoffs/steps and their rule (BLANK: Greg's
  modelling call), `model_context_rows` (BLANK: Greg's row count), and the journal-derived fields (cursors, prefix
  hashes, as_of clocks, the container sha256, the head hash) filled from the container after the ingest (BLANK now).
  Every gate that hard-codes the Sunday slice reads the declared value instead; the fourteen sites are listed in
  `CAPABILITY_MAP_TRADING_DAY_20260922.md` ("The Sunday-only assumption is hard-coded in code"): build_remaining_sunday_
  prefixes.py, run_actual_sunday.py, run_actual_sunday_compact_source.py, seal_final_prelaunch_candidate.py,
  run_journal_stack.py, parallel_source/verify_snapshot.py, sunday_execution.py, source_contract_runtime.py,
  day_pipeline.py, verified_sunday_schedule.py, selected_source_scope.py, and the box driver's one-UTC-day source object
  (`frankie_box_bedrock.py` ~132-154). The prefixes are re-seeded under the row count and the binding re-pinned
  (`frankie_host_rebuild_prefix_batch.yml`, the 2026-09-20 precedent).
- MODULE 3, trading-day-host: the host runner's gates read the declared counts; the code pins re-minted (step 1b); the
  request carries the trading-day stream.
- MODULE 4, trading-day-box: the driver's source object per TRADING DAY (not UTC day); the bedrock traversal, the ledgers
  and the V6 digest at 2 million rows (per-layer streaming); the candidate lane fires on the day (its 900 s / 600
  observation warm-up is the pinned producers' DATA warm-up, constructor defaults).
- Then the full rerun order (handoff 01:3xZ 09-22, steps 0-9 with 1b): step 0 done (the response-supersede workflow on
  the trunk, e194892d).
Still Greg's calls: the row count; the cutoff rule; the publish route for the container (presigned PUT via the run
workflow vs S3 rights on the box); the two flagged 4096s (the Pod bundle env GRANITE_MAX_MODEL_LEN, the coach's Bedrock
maxTokens); pre-warm from Friday; chat 7's calls 2-5; the Friday-anchor re-run; the parallel-replay writer.

## Where the machinery is
- Box: `deploy/aws/box/` (the session `frankie_box_boss_session.py`, the bedrock `frankie_box_bedrock.py`, the digest
  `frankie_box_digest_render.py`, the ingest wrapper `frankie_box_ingest_block.sh`, the Friday anchor, the producers
  checkout `producers_checkout.sh` -> the in-repo worktree `.producers-2ebb8ce8`); tests under `tests/test_frankie_box_*`.
- Ingest: `research/kalshi/frankie_boss/operations/ingest_block_sources.py` (the tool), `compact_build_journal.py` (the
  writer), `compact_journal.py` (the pinned codec, unchanged), `c15_builder.py` / `c15_observer.py` / `c15_journal.py` (the
  builder, the incremental observation), `box_standard.py`, `blocks/` (the manifests), `operations/
  derive_trading_day_manifest.py`.
- Host chain: `.github/workflows/frankie_host_*.yml`, `frankie_journal_stack.yml` (the pipeline), the PowerShell host
  scripts under `deploy/aws/host/`.
- Tests: the box codecs CI list (`frankie_box_codecs_ci.yml`, 198 green torch present and hidden) and the torch-equipped
  list in `frankie_journal_stack.yml` (now with the ingest, derivation and row-window suites). Baseline failures in this
  container (pre-existing, not ours): authority_map x3 (a commit absent from the clone), source_recovery x1.
- Container prerequisites: torch cpu, zstandard 0.25.0, databento-dbn 0.62.0 (the resume hook may pull databento 0.86
  and dbn 0.69 over it: reinstall the pin), boto3.
