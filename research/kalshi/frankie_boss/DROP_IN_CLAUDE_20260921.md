# Frankie/BOSS drop-in — next chat after 2026-09-20 (launch day)

Read in this order, then act: this file; `CLAUDE.md` (the FRANKIE/BOSS standing rules, first bullet is today's
state); `research/kalshi/frankie_boss/CLAUDE_HANDOFF_20260920.md` (every receipt of the day, in order). Run
`using-agent-skills` and `git-workflow-and-versioning` first; typed atomic commits, why-not-what, change
summaries.

## First decision already made, and the first job

Greg's go stands for exactly one thing: the 20211003 two-cycle run. **Run 35508198333** of
`frankie_journal_stack.yml` on `codex/frankie-launch-two-cycle-20260919` (day 20211003,
`go 0eb2c2acdccc17f8ad2d64d00b74a0c93b477c0418651a7f290d53f19d5710b0`, cycles 2, keep_compute true) ran
at 11:34Z: sources OK, journal skipped (ingest receipt present), checks OK, **host job REFUSED at the
cycles stage** (`stage_refused`, `cycles exited 1`, `FRANKIE_RUN_PROGRESS_V1` phase `data_delivery`, owner
`transport`, `error_type ValueError` 1.44 s in; the message is scrubbed by design; no new receipt
committed; the earlier `03-schedule-prefixes.json` from run 35498663360 stands). The refusal sits in
`run_actual_sunday.py` lines 812-843, after `read_execution_trigger` succeeded (the request-id fix is on
the host). Candidates, in order of likelihood:
1. line 833 `actual open run must follow this admitted live host instance`: the delivered
   `startup-intent.json` carries `local_ready.host_instance_id 6d02c1fcafbd4c7e8aa09245d3f9e3e7` (the 09-19
   admission witness); the host compares it to its own `host-instance.c15.json` in the run directory.
2. line 836 `startup admission differs from the actual prepared request`: `service-pins.admission`
   (observer tokenizer: 92,439 in / 38,633 out / 131,072) must EQUAL the host's `prepared['admission']`.
3. `retained readiness differs from actual admission` (`retained_ready_signal`, an older host-ready record
   for this instance with different fields).
4. line 843 `trusted host service pins differ` (config/identity hash after `verified_service_inputs`).
Diag run 35508442554 already narrowed this (handoff, last section): candidate 2 is OUT (the observer's
admission equals the host's, all five keys); the host witness `6d02c1fc...` and `host-preparation.c15.json`
live under the 09-19 run directory `actual-feedback-run/execution/cycle-00`, while the cycles stage runs
under `RunRoot=C:/Codex/Frankie-BOSS-20260919/days`, `Day=20211003`. **First job: a read-only host probe**
(style: `frankie_host_diag.ps1` section 1d) that prints `actual-host-configuration.json run_directory`, the
`host-instance.c15.json` instance_id in THAT directory, its cycle-00 listing, and the four comparisons
with `repr` plus the real exception text. Do not re-dispatch the pipeline until the refusing check is
named and fixed; every re-dispatch restarts the native host.

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
- Native host `i-0e90ee6110ef609aa`: tools checkout `6b0b37fe`, `boss_commit` recorded, readiness for request
  `frankie-boss-sunday-two-cycle-20260919-cycle-00` delivered, trigger written.
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
