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

## The midweek manifest question (open, Greg's call)
A trading day opens 18:00 ET the day before, so Tuesday 20211005 = the TAIL of the 20211004 UTC partition (after the
21:00Z halt) + the HEAD of the 20211005 partition (up to its halt). `derive_trading_day_manifest.py` refuses a tail
take ("ingest that day from the whole block"), and `ingest_block_sources.py` can only stop early in a partition
(partial members), not start late. So only Monday-type days (whose prior partition is a Sunday) can be ingested alone.
Options: (a) teach the derivation + ingest tool a TAIL take (start at the halt boundary; the staged block manifest
already measured the before/after-halt counts per partition); (b) ingest the Mon-Wed block whole and have ROOT split
it by trading day. (a) keeps one journal per day, which is what every experiment step expects. Nothing drops either way.

## Next (in order)
0. Greg's call on the midweek manifests (section above); then build it.
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
