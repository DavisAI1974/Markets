# Frankie/BOSS drop-in — next chat after 2026-09-20 (launch day)

Read in this order, then act: this file; `CLAUDE.md` (the FRANKIE/BOSS standing rules, first bullet is today's
state); `research/kalshi/frankie_boss/CLAUDE_HANDOFF_20260920.md` (every receipt of the day, in order). Run
`using-agent-skills` and `git-workflow-and-versioning` first; typed atomic commits, why-not-what, change
summaries.

## First decision already made, and the state of the refusal

Greg's go stands for exactly one thing: the 20211003 two-cycle run. **Run 35508198333** of
`frankie_journal_stack.yml` on `codex/frankie-launch-two-cycle-20260919` (day 20211003,
`go 0eb2c2acdccc17f8ad2d64d00b74a0c93b477c0418651a7f290d53f19d5710b0`, cycles 2, keep_compute true) ran
at 11:34Z: sources OK, journal skipped (ingest receipt present), checks OK, **host job REFUSED at the
cycles stage**.

**That refusal is now ROOT-CAUSED** by three read-only probe runs (35510320789, 35510506738,
35510597019; `frankie_host_cycle_binding_probe.yml`). Full receipts in
`CLAUDE_HANDOFF_20260920.md`, last section. The short version, and the corrections this file owes:

- The run-directory hypothesis in the earlier version of this drop-in was WRONG. `run_directory` is
  the retained `actual-feedback-run`, not the day directory, and `cycle-00` holds the preparation and
  the witness where the runner looks.
- `run_actual_sunday.py` 812-843 is RULED OUT. The failing progress line is the initial `RunProbe`
  state (`full_run_progress.py` 64), so `runtime()` was never entered. All four comparisons there
  pass anyway, line 837 included.
- There is NO traceback in `day-cycles.log`; it is 959 bytes and the runner catches the ValueError.
- **The refusing check is `ActualHost.__init__`'s last statement**,
  `save('host-identity.c15.json', ...)` -> `sunday_execution._save` line 45 ->
  `ValueError('retained Sunday execution evidence changed')`. Stored `boss_commit c9a86e74` vs live
  `6b0b37fe`, 6 code entries added and 8 changed.
- **Every artifact in the run directory is from 2026-09-17, 05:20-05:28Z.** The last successful
  `__init__` there was at `c9a86e74`. The witness earlier called the "09-19 admission witness" is a
  09-17 artifact; the 09-19 run never completed `__init__` either. Yesterday's advance neither caused
  this nor fixed it.

**The first job is not another probe: it is Greg's call between two paths**, because the identity
guard (a retained run continues only under the exact configuration and code that started it) and the
advance to `6b0b37fe` (so `verified_service_inputs` aims at the re-minted Pod `8vqdacl5t61rjx`) cannot
both hold in this run directory. Rolling back to `c9a86e74` clears the guard but re-aims inference at
the Pod that commit pins. A new run directory and `run_id` at `6b0b37fe` proceeds, at the cost of
redoing the 09-17 preparation and re-delivering readiness (the trigger is bound to request
`frankie-boss-sunday-two-cycle-20260919-cycle-00`). Before committing to that second path, MEASURE
whether a re-prepared request is byte-identical: `run_actual_sunday.py` changed between `c9a86e74` and
`6b0b37fe`, and `service-pins.admission` must still equal the new `prepared['admission']` or the run
refuses at line 836 instead. Do not assume it. Do not change the guard without Greg's word, and do not
re-dispatch the pipeline until the path is chosen.

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
