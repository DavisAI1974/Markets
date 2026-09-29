# HANDOFF 2026-09-29 (Code session): the experiment built out; Monday r10 parked; everything stopped

Branch `claude/frankie-monday-cycle-0-urozez`. Every push `[skip ci]`. Nothing was run on the box except read-only
probes, one code staging and one config write (below). py_compile python3.12 and bash -n only; no tests.
Previous handoff: `HANDOFF_20260929_PRINCIPAL_CODE.md`. Drop-in: `DROP_IN_20260929_EXPERIMENT.md`.

## State of the machines (checked at close)
- Frankie's box `i-035994afa8bdf66a5` (us-east-1): STOPPED (was running idle). Native host `i-0e90ee6110ef609aa`
  (us-east-2, Windows): STOPPED (was running since Sep 20). Year-pull box `i-08cee7171c0a76a04`: stopped. All 6 Pods
  EXITED. No serverless file on the box. Stops through the new `frankie_box_control.yml action=stop` (aa221de1).
- On the box (disk, retained): staged checkout `/opt/frankie-box/code/7f8deb0d...-36521357469-1/markets` (now stale:
  restage before any cycle0 dispatch); r10 config `work/monday-run-config/full-20211004-20260928-r10/
  actual-host-configuration.json` (written; the cancel arrived after it finished; inert, not launched).
- Monday r10: PARKED by Greg ("not worrying about finalizing Monday run"). Do not resume it unless he asks.
- Two collector workflows (Kalshi, Pyth durable) still run on their schedule; Greg was told, left alone.

## Jev's reports (read-only, turn by turn)
No report was ever written: `clm-sidecar/monday-20260928-jev1/` holds code, `sit-in/config.json` and 58 feed bundles,
all identical (phase `derived`, "render-only done: DIGEST_V9", no classroom item, no answer, probe frozen at 13:22Z).
Three relay starts (idx resets at 0000/0020/0027). The r9 principal never passed derive, so Jev had nothing to discuss.

## Greg's decisions this session (in order)
1. Classroom and Granite are settled and the code is done: Granite = the B2 critic only (+ one self-assessment); the
   classroom is Frankie's code. Do not re-ask.
2. The experiment is CPU only; classroom-arm days run no launch, no Granite, no Pod (only Jev's own Pod).
3. JEV IS IN as the blind outside student (spec section "Jev"): Qwen3-8B, own Pod, classroom-arm days only, never
   sees Frankie's answers before filing, files claims the search tests, keeps his seat by counts. His outputs AND the
   teacher's lessons go into his brain; never Frankie's answers.
4. Frankie's outputs and his lessons from the teacher go into his brain too.
5. Brain: Sunday and Monday cycles separate (day-keyed); a cycle reads every entry written so far except its own
   day+cycle ("his reasoning part had later data; he just can't have the actual run data ahead of time").
6. Teachers read every bit of Frankie's ingest data and every calculation layer directly, except the files Frankie
   generates to reason toward forecasts (R09); nothing built a second or third time.
7. No bedrock in the experiment. ROOT runs four processes; the experiment skips 2 and 3 (traversal, projection) and 4
   (digest) except on classroom-arm days.
8. "We forgot root in the experiment": ROOT is step 3.
9. DuckDB was added to the environment (container 1.5.6 cannot load extensions; use 1.5.5 + PyPI extension wheels).
10. The teacher's Dipole rows: 1 day in 5, batched; each day its own walk; days in parallel (Claude's comments folded
    into the spec).
11. End-of-build: inspect ALL code for run-time changes made to relaunch or do truncated runs (runbook section 6).
12. Keys do not rotate; never re-raise.
13. ChatGPT builds new pieces in parallel: `CHATGPT_BRIEF_EXPERIMENT_20260929.md` (orchestrator, historical Dipole
    claims from the earlier exhaustive search, transforms). New files only, own branches; Claude merges.
    SUPERSEDED the same day: "I'm going to have you do chatgpts part" - Claude built all three (below).
14. NO DATA IS DROPPED, even when incomplete: a calculation skips over the missing piece and lists it; never skip the
    day or the run for it (section below).

## Built this session (commit, what)
| Commit | What |
|---|---|
| aa221de1 | box control: `action=stop` |
| 67f9347c, 50207d59 | experiment spec + runbook: tied teachers, Granite out, classroom arm CPU only |
| 60790f53, eaa2004a | Jev: role in spec; `sit_in.py` rewritten (claims filed + pinned before Frankie is read), relay `ACTION=material\|frankie`, `launch.py --jev`, `frankie_box_jev_pod.sh` + workflow step |
| ade99ab4 | Jev's brain on S3 `clm-sidecar/jev-brain/` (entries + lessons) |
| 8dc172c1 | brain: R10 host grade out of Frankie's reading; `unavailable` lists; calcs-only entry + `frankie_box_brain_calcs.sh` |
| 7b45cdac | brain day-keyed; every entry read except own day+cycle; snapshot includes day-keyed entries |
| f97ad3e0, 5628555e | `frankie_box_experiment_data.py/.sh`: every root/config/cycle/ingest/authorship file of a day, linked or excluded with reason, missing, unclaimed; bedrock section leak fixed |
| d1a3abe3 | ROOT `bedrock`/`digest` switches |
| fb8fe3db, 3dd32b9d, 15b8f3a6 | search: DuckDB ASOF series, REAL leakage gate, sign-step couplings + chance check; sources: frames, structures, trades, per-second flow/roll20, per-group event counts, the teacher's Dipole |
| 9bc3e6fb, 01b7605d | scientific teacher's turn (claims -> counts per day -> lessons); Frankie's lessons as brain entry `<day>-lessons` |
| 8342839a, cf308f79, 8c295d29 | experiment ROOT for any ingested day (no authorship); shared pin builder; a broken wrapper pushed then fixed |
| e7c13e04 | day data + search take the teacher-only step's Dipole rows |
| c9b53360 | ChatGPT brief |

Nonconformance, mine: 8342839a pushed `frankie_box_experiment_root.sh` with an apostrophe inside `${VAR:?...}` (bash
syntax error) and, because that check failed mid-chain, two edits were silently missing from the commit. Fixed in
cf308f79 / 8c295d29; every script touched today passes bash -n. Run each check on its own before committing.
Also caught before commit: a leakage gate that could never fail (it only read rows up to i); replaced by the gate on
the real ASOF alignment.

## Later the same day: ChatGPT's three pieces, built by Claude (Greg: "I'm going to have you do chatgpts part")
| Commit | What |
|---|---|
| e7ae50ab | C: `frankie_box_experiment_transforms.py` (sign_of_step, run_length, magnitude_class, level_crossing, acceleration; causal, running LOWER medians, no caps) wired into the search (x under T vs y under T, and vs y's sign_of_step; rows name x_transform / y_transform; `TRANSFORMS=`); the scientific teacher marks only rows on the claim's own transform pair (`counts_only` otherwise) |
| e2d6bf36 | B: `frankie_box_historical_claims.py` + committed `knowledge/HISTORICAL_CLAIMS_V1-9b2ca9849e4f.json`: 127 catalog sources read at their revisions (sha256 checked; 0 unreadable), 4,806 candidate statements enumerated mechanically, 10 testable claims (H01-H10) from a declared crosswalk whose verbatim anchors are verified in the source bytes, 4,799 listed not_testable with reasons; the teacher takes `HISTORICAL_CLAIMS=`, lists a claim's condition as untested, writes HISTORICAL_LESSONS_V1 (into nobody's brain) |
| 2ccbea3a | A: `frankie_box_experiment.py` + `.sh` (plan / start / status; see the runbook section 5); `box-experiment-*` lock for it and the future teacher step |

Honest limits of these pieces:
- B's crosswalk is thin: 10 claims out of 4,806 candidates. Everything else is listed "no crosswalk entry: not put in
  testable form here", which is not a judgment that it cannot be tested. The crosswalk is a table in the code (authored
  by Claude from reading the sources; Greg may amend); widening it is open work. It was built in the container because
  the box's staged checkout has no git history (8 sources exist only at their catalog revision).
- Every day needs a committed per-day manifest to be ingested; today only 20211003 and 20211004 have one, and
  Tue/Wed cannot be derived alone (`derive_trading_day_manifest.py` refuses a tail day). Since 91cac9ea such a day
  WAITS (listed) instead of refusing the run. How midweek days get their manifests is open (section below).
- A calls the teacher-only step as `frankie_box_experiment_teacher.sh DAYS=<list> INGESTION_RECEIPTS=<list>`; until it is
  built, batches record `not_built`.
- The transforms multiply the search's pairs (up to 9 transform pairs per ordered series pair); no wall time is measured.

## Greg's rule, restated 2026-09-29 (after the three pieces): NO DATA IS DROPPED, EVEN WHEN IT IS NOT ALL COMPLETE
"We might not be able to include it in a calc if it's missing important data, but then we'll just skip over [it]
instead of skipping [the day]." Applied in 91cac9ea:
- `frankie_box_experiment_root.py` REFUSED any ingest with partial members. Every trading-day ingest has one (Monday's
  20211004 partition is taken up to the 17:00 ET halt; the rest is Tuesday's), so it would have refused Monday itself.
  Now the partial members are carried and listed in the source binding.
- The same ROOT refused to declare the day when a producer failed on some records. Now it writes
  `calculations_retained_with_failures` with the failure count (each failure is in derive.json and the failures spool
  with its record index and error); every other record is calculated and the day goes on.
- The orchestrator no longer refuses the whole plan for one day's gap: a day with no manifest stays in and its steps
  WAIT (listed); a day with no Dipole rows is exported and searched without them (listed missing, `dipole_missing` in
  the receipt); a teacher batch runs for the days that have an ingest while the others wait. Only rule breaks refuse the
  plan (a day listed twice, a malformed day); a day of another class, outside the assigned Octobers, or an unfrozen
  confirmation day is LEFT OUT of that run with its reasons (walls, not data gaps). WITHOUT_DIPOLE is gone.
- Still stopping, on purpose (listed): duplicates (two sealed ingests / two ROOTs of a day, a day searched twice), the
  leakage gate (a source that fails is not placed, listed), a day with no book frames (the search has no axis).

## The midweek manifest question (DECIDED later the same day: tail take + the prior day's closing book; built, see below)
A trading day opens 18:00 ET the day before, so Tuesday 20211005 = the TAIL of the 20211004 UTC partition (after the
21:00Z halt) + the HEAD of the 20211005 partition (up to its halt). `derive_trading_day_manifest.py` refuses a tail
take ("ingest that day from the whole block"), and `ingest_block_sources.py` can only stop early in a partition
(partial members), not start late. So only Monday-type days (whose prior partition is a Sunday) can be ingested alone.
Options: (a) teach the derivation + ingest tool a TAIL take (start at the halt boundary; the staged block manifest
already measured the before/after-halt counts per partition); (b) ingest the Mon-Wed block whole and have ROOT split
it by trading day. (a) keeps one journal per day, which is what every experiment step expects. Nothing drops either way.

## Later still: Tuesday and Wednesday built (Greg: "We will be running Tuesdays and Wednesdays for a while";
"build the remaining missing hrs for Tuesday so we can combine with what we already have for Tue to get a complete tue
book"; then "Go, build the three pieces and if possible ingest wed separately"). Built, NOT run:
- Manifests `blocks/BLOCK_20211005_SOURCE_MANIFEST.json` (2,104,864 records: the 19,182 after the 21:00Z halt of the
  20211004 partition + 2,085,682 before the halt of 20211005; hash 4bb86f47) and `BLOCK_20211006_SOURCE_MANIFEST.json`
  (2,304,995: 26,248 + 2,278,747; hash 67c3d701). `derive_trading_day_manifest.py` now writes a TAIL member
  (`tail_members`: skip = the prior day's pre-halt records, take = the post-halt records; only as the first member).
  Monday's manifest re-derives byte for byte (the key is written only when a day has a tail).
- The book at the halt: Monday's ingest never took Tuesday's first 2 hours, and a book starting empty at the halt would
  miss every order resting across it. `opening_book.py` reads the PRIOR day's closing book from its sealed ingest's
  `builder-checkpoint.c15.json` in place (sha256 against the receipt, state hash against the receipt and its own body)
  for both receipt kinds: a normal ingest (Tuesday for Wednesday) and Monday's recovery receipt
  (`blocks/MONDAY_RECOVERY_RECEIPT_20260922.json`, checkpoint 0262b0e9 beside the Monday container). Restored with
  `mbo_resume_state.restore_adapter_state` (exact round trip), counters zeroed: the day's counts are its own, the book
  is real. Nothing re-ingested, nothing copied.
- `ingest_block_sources.py --opening-receipt`: decodes and skips the tail partition's prior-day records (never appended
  or counted), verifies the cut on both sides (last skipped record = the prior day's session, first taken = this day's)
  and that the opening book ends exactly at that cut (same partition, its take = this skip, same session), seeds the
  builder's adapter before the first record. The conformance drain replays the prefix chain only, never the book.
  Receipt: `tail_members_ingested`, `opening_book` (descriptor; `absent` and listed when no receipt is given).
- ROOT: `Session.derive(opening_adapter_state=, opening_book=)`; `frankie_box_experiment_root.py` reads the ingest
  receipt's `opening_book`, loads the same checkpoint again and checks it equals what the ingest opened with, then the
  legacy pass replays the day onto it (derive.json carries `opening_book`).
- `frankie_box_ingest_block.sh`: `OPENING_RECEIPT` (the first day's prior receipt: `$ROOT/work/ingest-*/ingestion-
  receipt.json` or Monday's committed recovery receipt path), and `MANIFEST` may be a comma list for fetch/ingest: each
  day its own journal, each after the first opening with the book the one before closed with; a failed day stops the
  list (the next waits on its book). Fetch hard-links a partition already verified under another block (Tuesday's
  20211004 is in Monday's block), downloading only what is missing.
- Orchestrator: a day with a tail member records `opens_after` (the prior day) and its ingest WAITS on that day's sealed
  ingest (Monday = the committed recovery receipt); plan override `opening_receipt`.
- Not yet: the teacher-only step (not built) must seed the same book for a midweek day's walk; the Monday checkpoint's
  presence at `/opt/frankie-box/work/ingest-20211004-ingest-1790057801/builder-checkpoint.c15.json` is read from the
  recovery receipt, not probed (the box is stopped); a missing file fails the ingest at its start, before any record.

Tonight's dispatch (each on Greg's go; box `i-035994afa8bdf66a5` stopped): start the box; restage the tip; fetch with
presigns for glbx-mdp3-20211004/05/06 (`ACTION=fetch MANIFEST=<Tue>,<Wed>`); then ONE ingest dispatch through
`frankie_box_run.yml` (timeout ~4 h: about 1.1 h per day at Monday's 1.77 ms/record plus each day's conformance drain):
`ACTION=ingest MANIFEST=research/kalshi/frankie_boss/blocks/BLOCK_20211005_SOURCE_MANIFEST.json,research/kalshi/
frankie_boss/blocks/BLOCK_20211006_SOURCE_MANIFEST.json OPENING_RECEIPT=research/kalshi/frankie_boss/blocks/
MONDAY_RECOVERY_RECEIPT_20260922.json`, with the progress probe on it. Then each day's ROOT (`frankie_box_experiment_root.sh`,
DIGEST off unless it is a classroom-arm day).

## RUNNING (Greg's "Go for all", 2026-09-29 ~09:00Z)
- Box `i-035994afa8bdf66a5` STARTED (control run 36546524863, SSM Online 09:03Z). Now billing.
- Fetch (run 36546879068): 20211004 hard-linked from Monday's block, 20211005 and 20211006 downloaded, sha256 + size
  verified; receipts `/opt/frankie-box/receipts/ingest-fetch-20211005-1790672762.json`, `-20211006-1790672765.json`.
- Ingest try 1 (run 36547021157, 66f50851) stopped before any record: Monday's checkpoint is beside its recovery receipt
  in `/opt/frankie-box/work/sealed-recovery-35796793428/`, not beside the container. Fixed in 25b30d9c; its work dir
  `work/ingest-20211005-ingest-1790672828` holds no receipt (kept, not a sealed ingest).
- Ingest Tue then Wed (run 36547330372, 25b30d9c, timeout 86400, OPENING_RECEIPT = Monday's on-box recovery receipt):
  RUNNING, `work/ingest-20211005-ingest-1790673001`, about 2 ms/record at 09:13Z (70,000 of 2,104,864 in 170 s).
  Wednesday follows in the same dispatch from Tuesday's closing book. Probes: `frankie_box_read_log.sh MODE=tail
  FILE=work/ingest-20211005-ingest-1790673001/progress.jsonl`, `MODE=processes FILE=work`.
- Staging for the ROOT: restage the tip before each ROOT dispatch (docs pushes move the tip).
- Read-only audit of the Tuesday path (two agents): no run-time relaunch or truncation leftover, no check against
  Monday's sizes. Fixed in 25b30d9c: ROOT reader passed over an INPUT without an MBO record unlisted and then refused the
  day (now listed, a failure of the day); search cells with < 2 steps now listed; search leakage print key; a day export
  is reused only from this run's ROOT; ACTION=ingest requires MANIFEST. Left as is (listed): cycle '00' literals (the
  whole-day pin admits cycle 0 only), Monday wording in ROOT messages, OBSERVATION_CHECK_EVERY = 64 (the incremental
  observation's differential check), the ingest's CYCLE units check; the 09-23 perf rewrites of the adapter, observer
  and builder run for the first time on Tuesday (the differential check refuses on drift). The producers
  `native_roll20.py` and `a_memory_member_first_recalculation_20260828.py` live in the box's pinned producers checkout
  and were not audited here.

## No Monday dependency (Greg, 2026-09-29: "We can't do that dependency for later weeks because we will just be
running tue and weds for a while")
A day with a tail member no longer needs the prior day's ingest. Without OPENING_RECEIPT the ingest WARMS its own book:
the tail partition's prior-day records are applied to the book only (never journaled, never counted), from the
partition's first record, which is Databento's 00:00Z book snapshot (checked by its F_SNAPSHOT flag and listed in the
receipt; a partition without one is listed, not refused), up to the halt. Either way (warmed or seeded from a prior
receipt) the ingest writes the opening book beside the journal (`opening-book.c15.json`, sha256 + adapter state hash in
the receipt's `opening_book_file`), and the day's ROOT opens from those bytes, with no prior day needed. The orchestrator
uses a prior day's sealed ingest when one exists and otherwise lets the day warm (no wait). Tonight's running ingest
(25b30d9c) predates this: Tuesday is seeded from Monday's recovery checkpoint, Wednesday from Tuesday's, and their ROOTs
open from those prior receipts (still supported). Days are now independent, so later Tue/Wed ingests can run as
separate dispatches.

## Speed items 1-5 + resume (Greg: "Do 1-5 now. We are supposed to have save code so we can pick up where we left
off"; "We can break my gold standard"), built 959c5e12, review fixes c887bf9a, NOT run except as noted
1. Days side by side: a git worktree per dispatched commit (`/opt/frankie-box/ingest-code/<sha>`, under a lock; the
   shared checkout is never moved), `DAYS_AT_ONCE`, an own concurrency group per ingest dispatch, a per-dispatch presign
   map; the orchestrator ingests `--parallel-days` at once, each day warming its own opening book.
2. `operations/parallel_ingest.py` (SPEC-ingest-parallel-replay): pass 1 state only (chain + book; exact state saved
   every 20,000 records at a group-closed point, the adapter PICKLED so key order is kept), pass 2 workers replay each
   segment through `C15BuilderNoObservation` into spools (placeholder previous_hash) and must end on pass 1's state,
   pass 3 patches the hash and cuts boxes exactly as append(). Saved passes: `RESUME_DIR` / `--resume` continues a day.
   Observation 'none' only.
3. `VERIFY=deferred`: seal + completion from the builder state (complete()'s count refusals kept);
   `ACTION=conform DIRECTORY=<ingest dir>` runs the drain later -> conformance.json.
4. `OBSERVATION=none`: no full-book copy at a group close (`c15_builder_none.py` subclass; c15_builder.py keeps its
   pinned bytes and identity); `observation_replay.py` rebuilds it for the teacher.
5. `fast_mbo_decode.py`: batch decode, every per-record check kept.
Wrapper defaults stay Frankie's (sequential, full, inline). Orchestrator defaults: parallel, none, deferred.
Open: the disk gate does not reserve for spools x parallel days; `status` reads the shared checkout's manifests.
First real use tonight: Wednesday (run 36551601815, c887bf9a): SEQUENTIAL, OBSERVATION=full (classroom days need the
teacher's observations), VERIFY=deferred, warm start, fast decode, WORKERS=16, beside Tuesday; out
`work/ingest-20211006-ingest-1790675371`. The chained Tue,Wed run 36547330372 must be CANCELLED once Tuesday's
ingestion-receipt.json exists (else it starts a second Wednesday: duplicate data).

## Classroom arm revised (Greg, 2026-09-29): discovery days 1 and 2 of every five on, 3-5 off (orchestrator
`--classroom-arm-cycle 2/5`); Tue 20211005 and Wed 20211006 are days 1 and 2. Their ROOTs run DIGEST=off tonight (the
experiment's classroom arm is not wired yet); the digest is a later step when it is.

## Next (in order)
0. DONE: the midweek manifests (built, 66f50851 / 25b30d9c). Ingest running; then each day's ROOT on the go given.
1. The teacher-only batch step `frankie_box_experiment_teacher.py/.sh` (DAYS=<list>; each day its own fresh walk of
   JournalTeacherR3 on its sealed journal, in parallel; writes `DIPOLE_CLASSROOM_SOURCE_V1` to
   `/opt/frankie-box/work/experiment-teacher-rows/<day>/host-dipole-classroom-source.c15.json`; skips days a launch
   already covered). The standalone call chain is mapped in `TEACHER_ONLY_CALL_MAP_20260929.md` (call sequence
   with real names, pinned files, CPU/taskset, the walk-cache trap, the unsettled items). Build from it. The
   orchestrator already calls it as `frankie_box_experiment_teacher.sh DAYS=<comma list> INGESTION_RECEIPTS=<comma
   list, same order>` (box-experiment lock added); a day it cannot finish is listed and goes on without rows.
1b. BOTH TEACHERS HAVE ALL THE DIPOLE DATA (Greg, 2026-09-29: "the boss teacher will still absolutely have all dipole
   data available just not fresh calcs on it every day. I guess that applies to both teachers"). Fresh Dipole calcs
   run 1 day in 5 (batched per day); what the teachers READ is everything that exists. Built: the scientific teacher
   tests on every discovery day whose Dipole rows exist. NOT built: on a classroom-arm day the BOSS teacher's classroom
   material (and Jev's material) must also carry every earlier discovery day's Dipole rows (launch sources +
   experiment-teacher-rows, read in place, each labelled with its day, never merged across days) and the historical
   Dipole catalog (knowledge/DIPOLE_SHARED_CATALOG_20260922.json) whole. Nothing recomputed; never Frankie's answers.
2. ChatGPT's pieces are DONE (built by Claude). Open from them: widen the historical crosswalk (10 of 4,806 candidates
   are testable claims today); measure the transforms' cost on the first search.
3. On Greg's go when the box is up, in order: restage the tip; `frankie_box_venv_duckdb.sh ACTION=check` then
   `install`; `frankie_box_brain_calcs.sh ACTION=show` (read-only); `frankie_box_experiment.sh ACTION=plan` for Monday
   (read-only; a PLAN file naming Monday's sealed ingest, its ROOT `monday-calculations/full-20211004-20260927-r1-48`
   and its r9 run directory, since those already exist and are never rebuilt); then the Monday day data and search
   (through the orchestrator `STAGES=data,search,lessons` or the step scripts); probes on every long step.
4. Open for Greg (listed in the runbook section 6): the MIXED files (session-request, comparison, principal-inputs
   receipt) - filter the data part through?; the BOSS forecast journals (`handoff-*`) - Frankie's decision process or
   data?; the Granite critic files; the canary-vs-no-canary question for the disk measurement; to reach r10 the
   principal inputs would need re-pinning to see the Monday brain entry.
5. At the end: the whole-code inspection for run-time relaunch/truncation leftovers.

## Tools this session
codebase-memory-mcp is installed and connected; the index is built with the CLI
(`~/.local/bin/codebase-memory-mcp cli index_repository '{"repo_path":"/home/user/Markets","mode":"moderate"}'`,
82 s) because the MCP call times out at 60 s and kills the worker. The ADR store (`manage_adr`) holds the settled
decisions but lives in the container; git is the durable copy. DuckDB in the container: use a venv with duckdb 1.5.5 +
`duckdb-extension-{json,parquet,sqlite-scanner,httpfs}==1.5.5`, installed from their bundled files.
