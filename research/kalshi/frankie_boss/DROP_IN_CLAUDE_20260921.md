# Frankie/BOSS drop-in — next chat after 2026-09-20 (launch day)

Read in this order, then act: this file; `CLAUDE.md` (the FRANKIE/BOSS standing rules, first bullet is today's
state); `research/kalshi/frankie_boss/CLAUDE_HANDOFF_20260920.md` (every receipt of the day, in order). Run
`using-agent-skills` and `git-workflow-and-versioning` first; typed atomic commits, why-not-what, change
summaries.

## State at 21:30Z: cycle 0 at the designed HOLD, waiting on Root's response reaching the host

**Read first.** Run 35536713271 returned to the HOLD (`actual_frankie_session_pending`, cycles exited 3,
205 s; nothing written over). Root's Frankie session recorded its response on HIS machine, then pushed
the three files (response, host attestation, host session record) to his fork
`rootdavis/Markets`, branch `root/cycle-00-response`, under
`research/kalshi/frankie_boss/runs/20211003/root/`. The session cannot reach a fork (credential scoped
to DavisAI1974/Markets; cross-owner attach refused), so the bridge is a pull request from the fork
into DavisAI1974/Markets: its head is `refs/pull/N/head`, which the recording workflow fetches.

**The next three actions, in order, no code changes:**
1. `frankie_host_record_principal_response.yml` (branch `claude/frankie-launch-verification-lqmv0m`)
   with `source_ref=refs/pull/N/head`, `response_path/attestation_path/record_path` = the three files'
   repo-relative paths on that ref, `cycle_index=00`. It checks the files on GitHub, stages them with
   SigV4 presigned GETs (masked), and the host script verifies sha256/bytes, places the session record at
   `<run_directory>/execution/cycle-00/principal/host-session-record.json`, rewrites a foreign
   `host_record.path` to that host path WITH a receipt (Greg's override, 66b0ab27), runs the recorder from
   the tools checkout, and requires `actual_principal_response_recorded`. Receipt:
   `principal-response-recorded-<stamp>.json` in the day directory. An existing `session-response.json`
   is reported and left alone.
2. ONE dispatch of `frankie_journal_stack.yml` on `codex/frankie-launch-two-cycle-20260919` (day
   20211003, the standing go, cycles 2, keep_compute true, checks_only false): verify -> native learning
   -> readback -> completion -> classroom correction turn (a second HOLD if it needs Root) -> cycle 1's
   readiness (`frankie_deliver_readiness.yml` for `...-cycle-01`, observer bound to cycle 1's request sha).
3. `frankie_host_cycle_report.yml` (cycle 00): the whole report arrives as a workflow artifact and in the
   job log. GLANCE ONLY for anything pertinent to the next cycle (Greg, 20:46Z); deep dives after cycle 1
   is running.

**Greg's standing rules today (all in `CLAUDE_HANDOFF_20260920.md`):** launch-critical = how Frankie runs
or the science, everything else waits; no package code changes until both cycles are done; NO LIMIT
anywhere we put one (the report display is uncut; Frankie's analysis has no cap in the code; the Granite
contract caps are science, queued); the next cycle is the priority once reports exist; Root's response
is ESSENTIAL (the native learner trains on its feedback), so it cannot be skipped.

**Notes queued for after the cycle:** start the remaining (nineteen-cycle) prefixes while the cycle runs
(`day_schedule_prefixes.ps1` with `CycleLimit=19`, respecting the host's CPU-dedication gate); wire a
ROOT PROBE (a heartbeat record Root's session writes to git or S3, printed by the status probe) so
"churning, dead or hung" is answerable; the NWS hourly collector failing on the trunk; the three notes
files for the architect. Skills: `~/.claude/skills/using-agent-skills` and `git-workflow-and-versioning`
exist on disk but are not registered in the session; read their SKILL.md and follow them (change
summaries per commit, assumptions surfaced, typed atomic commits).

**Harness note:** the auto-mode classifier refuses guard-changing diffs ("Security Weaken"); on Greg's
explicit word such commits go through the GitHub API (`push_files`), then the container syncs with
`git checkout -- <files> && git pull --rebase`. Workflow files must also be registered on the trunk
`claude/kalshi-s79-kickoff-ij8t9o` for `workflow_dispatch` to see new inputs.

## State at 15:40Z on launch day: every refusal so far is root-caused and cleared; the pipeline is running

Greg's go stands for exactly one thing: the 20211003 two-cycle run (`frankie_journal_stack.yml` on
`codex/frankie-launch-two-cycle-20260919`, day 20211003, `go 0eb2c2acdccc17f8ad2d64d00b74a0c93b477c0418651a7f290d53f19d5710b0`,
cycles 2, keep_compute true, checks_only false). Greg's priority rule (12:45Z): launch-critical = anything
that changes how Frankie runs or the science; the identity/evidence guards and the tests are provenance
and, when one blocks the launch, it is overridden WITH A RECEIPT (moved, never deleted) and we move on.
Every override today is receipted in the day directory on the host or in S3, and recorded in
`CLAUDE_HANDOFF_20260920.md` in order. The chain, each refusal named by evidence, not guessed:

1. `__init__` `save('host-identity')` refused: the retained run directory was code-bound to `c9a86e74`
   (host-identity, initialization, training checkpoint digest, execution-identity). Superseded by
   `frankie_host_supersede_code_bound_state.ps1` (three runs; the stale execution-identity was the second
   find). Re-run each time the host advances.
2. Line 843 `trusted host service pins differ`: the Windows checkout had `core.autocrlf=true`; every
   `*_parser_code_hash` is sha256 over SOURCE BYTES; the observer is Linux (LF). Fixed by `.gitattributes`
   `-text` on the two roots and `frankie_host_normalize_eol.ps1` (run 35514620722); probe section 6 now shows
   the host identity `1bd1027a...` = pins.
3. A stop with only `error_type`: the runner scrubs exception text by design, and the host runs
   `run_actual_sunday_classroom.main`, not the base main. Both mains now emit `frames` (repo-relative
   file/line/function, never a message): `57366d61`, `34a4feac`. Read them first on any stop.
4. `run_actual_sunday_classroom.py:191 prime_cache -> sunday_execution.py:48 _save`: the 09-17 Dipole
   classroom package in cycle-00 refused on differing bytes. `frankie_host_supersede_classroom_package.ps1`.
5. The two-cycle prefix batch pinned CRLF-era code hashes of four LF-committed sources (all six pins were
   stale): cycle 1 would have refused at `encoding_options`. `frankie_host_rebuild_prefix_batch.ps1`
   rebuilt prefix-01 on the LF checkout (snapshot witness sha UNCHANGED: the data is identical), rewrote
   only the configuration's `prefix_manifest` witness and moved host-identity aside. Done BEFORE the cycles
   dispatch on purpose: a supersede after cycle 0 would move `training.sqlite` and destroy its learning.
6. Line 833 `startup admission differs from the actual prepared request`: the LF host prepares request
   **`a7b72cf9...`** (model_hash, teacher_binding, teacher_hash, input_hash are code-bound and changed with the
   line endings; probe section 7 diffs the receipts); the 11:19Z readiness pinned the CRLF request
   `6cd46f98...`. `a7b72cf9` is the request the observer world always used (archive on the branch). Re-pin:
   `frankie_host_supersede_readiness.ps1` (trigger, readiness dir, host-service moved), observer re-run on
   a7b72cf9 with the host's ready witness (`admitted_at 1789916729.1158657`) and the reviewed runtime
   configuration, Pod restart after the start intent (Pod RUNNING throughout), delivery run 35520040166.
7. The observer first refused at the S3 active-run claim (the cancelled 11:19Z observer still owned the
   Pod; release needs a Pod STOP, which loses the GPU under low stock). `operations/active_run_supersede.py`
   copied the record aside and wrote `phase closed` (run 35519639227).

**Pipeline run 35520104563 dispatched 15:36Z.** Its outcome is the next section of the handoff; if this
file still ends here, read the handoff's last section and `list_workflow_runs` on `frankie_journal_stack.yml`
before anything else. Cycle 0 is the launch; cycle 1 needs no further host action.

Still open on the launch path, in order of consequence: (a) the git receipt
`runs/20211003/03-schedule-prefixes.json` on the launch branch names the superseded manifest sha
(provenance only, not a gate; moving it means pushing to that branch, Greg's word); (b) the
host-identity guard cannot survive a lawful advance or configuration rewrite (task #2, Greg's design call);
(c) the supersede receipts' `bytes`/`mtime` were null in the prefix rebuild's first run (fixed in the script,
sha256 values were right).

## Where everything is

- Branch = `claude/frankie-launch-verification-lqmv0m` (head carries the re-mint, the operator
  workflows and the handoff). The trunk `claude/kalshi-s79-kickoff-ij8t9o` registers the workflows
  (dispatch inputs) and is an OLDER lineage for `frankie_boss`; never run launch code from it.
- The retained Pod is **`8vqdacl5t61rjx`** (US-MO-1, RUNNING, healthy, adopted). Identity lives in
  `granite_retained_identity.py` + `granite_retained_migration_receipt.json` + `granite_retained_host.INFO_SHA256`
  (`6f8efdf9...`); generation `migration-8vqdacl5t61rjx-a004983e93b9`.
- `ycf4v6lmave6xw` is EXITED on a GPU-less host, untouched, still holding the original retained model.
  Its fate (keep as cold spare, or terminate) is Greg's call; `pod_control --action terminate` refuses the
  current retained id only, so re-check `RETAINED_POD` before ever pointing it at anything.
- Native host `i-0e90ee6110ef609aa`: tools checkout `34a4feac` (LF, `.gitattributes -text`), `boss_commit` recorded,
  readiness for request `frankie-boss-sunday-two-cycle-20260919-cycle-00` re-pinned to `a7b72cf9...` and delivered
  (run 35520040166), trigger written. Everything moved aside lives under `C:/Codex/Frankie-BOSS-20260919/superseded/`.
- Observer run 35507527320 is in `hold` (observes until the local stop; never stops the Pod).

## What the day measured (do not relearn)

1. Provider refusal text on record: `"There are not enough free GPUs on the host machine to start this pod."`
   The repo lifecycle discards the body; `pod_control --action start` prints it.
2. Under LOW L40S stock a stopped Pod loses its GPU within minutes (resume refused 5 min after a
   stop-retain). Never stop a prepared Pod; adoption goes RUNNING -> observer `observe_migrated_start` ->
   `restart` after `retained-start-intent.json` exists.
3. `verified_service_inputs` builds `RunpodConfig(POD_ID, ...)` from the checkout, so a re-mint must
   reach the native host (`frankie_host_advance.yml`, target as input, descendant-only).
4. The bootstrap from a fresh volume takes ~9 min in US-MO-1 (17.59 GB at ~47 MB/s); an EUR-IS-2 host
   produced no bootstrap line in 30 min.

## Next ordered work

1. Run 35508198333 receipts (above). Then drop-in items 3-5 of 2026-09-20: sealed-absence receipts for absent
   downstream artifacts; configuration consumes only signed absence proofs; per-record ingest cost measured
   before any scale claim.
2. After the run, two clean commits: `chore:` remove the retired-smoke literals (`TOTAL_SECONDS`, `BASE`,
   `BUNDLE_SHA` in `granite_runpod_cloud.py`; bounded-lease durations in `granite_retained_lifecycle.py`),
   and `refactor:` the remaining hardcoded host paths/instance ids in the ops scripts. Any edit to a roster
   file re-pins the bundle, so keep those two commits off the roster files.
3. Add `tests/test_partition_packing.py` and the stack tests to CI (needs Greg's word).

## Do not do these things

Do not revert a9ab5ec4; do not touch `codex/journal-reduction-stack-20260915`; do not import from
Bento/Databento; do not change the AWS-first credential path; do not create local C:/E: artifacts; do not
treat the go as permission to modify the pipeline workflow; do not invent Claude or Frankie statements; do
not claim STOP/cleanup or any result without its receipt; do not claim all 19 prefixes are built (two are
verified); do not stop, restart or terminate any Pod without Greg's word; do not quote 114,054 or 1,189 as
measured facts (57,027 is the one measurement); keep durable records in git or AWS only.
