---
name: frankie-daily-run
description: Operator checklist for the Frankie/BOSS daily run on the Linux box (the "Monday cycle 0" run) - where the state lives, the HOLD/go rule, the stage-config-launch-principal-record-retain sequence through frankie_box_run.yml, how to probe and what receipts to reconcile, and the traps that cost the Sep 23-29 sessions time. Use at the start of any session that will launch, resume, monitor or verify a Frankie day run, before dispatching anything.
---

# Frankie daily run

This is the procedure, not the state. **The current drop-in doc wins over this file** for every
run id, path, sha and count. Values below marked (as of 2026-09-29) are there so you know what to
look for, not to be dispatched blind. If this file and the drop-in disagree, say so to Greg
rather than picking one.

## 0. HOLD is the default

Every box, Pod, Granite or launch action needs **Greg's explicit go, step by step.** A go for
one step is not a go for the next. Read-only probes need no go. Never stop a Pod, never
redispatch a cancelled run, never power-cycle the box without his word.

## 1. Orient (read-only, do this first)

1. Find the run branch - it is NOT this session's auto-named branch and has **no merge base with
   the trunk**. As of 2026-09-29: `claude/frankie-monday-cycle-0-urozez`, tip `27b9c8d9` or later.
   `git fetch origin <branch> && git checkout -B <branch> origin/<branch>`, confirm the tip.
2. Read, in order: `research/kalshi/frankie_boss/SPEC-decouple-granite.md`, the newest
   `research/kalshi/frankie_boss/DROP_IN_*.md` (its WORK INSTRUCTIONS are the live procedure),
   `SPEC-experiment-orchestrator.md`, the newest `HANDOFF_*.md`, and
   `MONDAY_CHECKLIST_20260927.md` (receipt-based checklist). Build plan:
   `research/kalshi/frankie_boss/artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx` (openpyxl;
   sheets Build Plans, Components, Gates) - a Granite role or component not in it is not wired.
3. Treat as HISTORICAL (contradicted by later rules): `CLAUDE_CYCLE0_EXECUTION_HANDOFF_20260923.md`,
   `CODEX_HANDOFF_20260923_*`. `CLEANUP_RUNBOOK.md` is a crypto runbook, unrelated. The
   `day_pipeline.py` / `frankie_journal_stack.yml` / Windows host `i-0e90ee6110ef609aa` chain in
   CLAUDE.md is a different path from the one the Monday run used - do not run it blindly.

## 2. Check what is billing (read-only), report to Greg

- `frankie_pod_control.yml` with `action=list`, plus `/opt/frankie-box/pods.json`
  (4 x A100 SXM 80GB, ~$1.59/h each, as of 2026-09-29).
- `frankie_box_read_log.sh MODE=processes` - what is running on the box.
- `frankie_box_disk_usage.sh` - r10 saves walk blocks and needs >= 30 GB free.
- Never the serverless endpoint; it is removed (min workers 0).

## 3. How every box step is dispatched

One committed script from `deploy/aws/box/`, dispatched via `.github/workflows/frankie_box_run.yml`
(sends it over SSM, sets `MARKETS_SHA` to the dispatched commit). Inputs: `script`, `variables`
(space-separated `NAME=VALUE`, **no quotes, no spaces inside values**), `timeout` (default 1800 -
set it for long stages), `instance`, `region`, `comment`, `presign`, `presign_hours`,
`github_token_to_ssm`. Box: `i-035994afa8bdf66a5`, us-east-1 (as of 2026-09-29).

**Check the `script` field before every dispatch** - a wrong script with a valid ACTION can come
back green (Codex run #105).

## 4. The sequence (each step on Greg's go)

Already done for day 20211004 - do NOT redo: ingest (gold standard), ROOT calculations,
principal inputs, trading-day preparation. The drop-in names their current receipts.

1. **Stage code**: `frankie_box_stage_code.sh ACTION=stage` (runs on its own lock). Record
   `CODE_ROOT=/opt/frankie-box/code/<sha>-<run>-1/markets`. **Push nothing to the run branch
   after staging** - the scripts refuse when the staged checkout differs from `MARKETS_SHA`; if
   you must push, restage.
2. **Config**: `frankie_box_cycle0.sh ACTION=config CODE_ROOT=... RUN_ID=... PREPARED=...
   PRINCIPAL=... OUTPUT_ROOT=...` (values from the drop-in). Do not pass `JOINED` (refused).
   Confirm the written config has `classroom_scientific_dialogue: false` and `boss_commit` equal
   to the staged checkout.
3. **Launch**: `ACTION=launch CODE_ROOT=... CONFIGURATION=<actual-host-configuration.json>`,
   timeout 43200. Ends at a durable WAIT with exit 3/4 and prints `CYCLE0_EXIT n` -
   **exit 3/4 is pending, not failure.**
4. **Principal**: `ACTION=principal CODE_ROOT=... CALCULATIONS=... REQUEST_DIRECTORY=...`,
   timeout 86400.
5. **Record / correction / retain**: `ACTION=record TURN=initial` (needs `CONFIGURATION`,
   `CALCULATIONS`, `TURN`), then correction, then `record TURN=correction`, then `retain`.
   The docs disagree on whether a launch `RESUME=1` sits between these (see section 8) - ask.
   Before `retain`, check its push target: `BASE` defaults to
   `claude/agent-skills-execution-tzh7sw`, outside the run branch.
6. Do NOT dispatch (unwired): the Jev relay, the CLM sidecar, the joined-teacher builder, the
   dipole catalog resend.
7. Update the drop-in + handoff with run ids and probe readings; push with `[skip ci]`.

## 5. Monitoring - a probe on every long run (standing rule)

- `frankie_box_progress.sh CODE_ROOT=... DIRECTORY=<run root>` (add `RESOURCE_METRICS=1`), or
  `frankie_box_read_log.sh MODE=tail FILE=work/runs/<run>/host-progress/progress.json`.
  Probes use the `box-progress` lock and run beside the work.
- Also: `frankie_box_read_log.sh MODE=processes|receipt`, `frankie_box_session_cpu.sh
  MODE=profile|threads` (catch one core carrying the whole step), `frankie_box_disk_usage.sh`,
  `frankie_box_console.sh` when SSM itself is dead.
- Output over ~23k chars arrives paged as "report part i/n" - read every part.
- **A green workflow, an SSM ack or a staged checkout is not proof of execution.** Only a receipt is.

## 6. Done = receipts reconcile

Cross a step off only when its receipt says so. For the day 20211004 base (as of 2026-09-29;
the drop-in/checklist hold current values):
- calculations receipt sha matches the drop-in; 2,032,203 INPUT records, 0 failures;
- 43 of 44 bedrock layers derived (`clock_lock_time` = `NO_PRODUCER_FOUND` by design);
- `model_calls`, `source_writes`, `source_replays` all 0 in calculations and inputs receipts;
- config `boss_commit` = executing checkout;
- run complete = runner reports `requested_cycles_complete` (or `all_scheduled_cycles_complete`)
  with cycles=1, plus `dipole-classroom-receipt.json`.
"Bedrock" here is a calculation layer, not Amazon Bedrock.

## 7. Rules that never bend

- No tests, no CI, no canaries during the run: `py_compile` (python3.12) only, `[skip ci]` on
  **every** push (a digest push once triggered billed CI).
- Cost first: stop what is not needed - on Greg's word.
- Never rebuild or replay the ingest / gold standard. Nothing in the day chain touches
  Databento; only `ng_historical_mbo_5y_to_s3_20260820.yml` holds that key.
- Never edit the pinned files (`frankie_box_projection.py`, `context_session.py`,
  `c15_journal.py`, `c15_teacher_r3.py`): swap, never edit.
- Zero data dropped: no caps, truncation, normalizing or averaging. Duplicate data declines the run.
- Never delete evidence; stop receipts go under `/opt/frankie-box/receipts/`.
- Granite only in C35, C21-C24, C14. Anything else goes into the build plan first.
- Keys are secrets and do not rotate during the build.

## 8. Known traps (each cost a session)

| Trap | Avoid / fix |
|---|---|
| Push after staging -> "staged checkout differs from MARKETS_SHA" | stage last, dispatch from that exact tip |
| Side builder filled the disk (~460 GB), SSM then returns empty after ~10 s | lean writer + 32 GiB `DiskReserve` are in; recovery is `frankie_box_disk_rescue.sh` (an EC2 power action, Greg's go). Do not grow the box unless unavoidable |
| One CPU carrying a whole stage (r4, r6, r7) | single-core scan with `frankie_box_session_cpu.sh` before and during |
| Cancelling a run left its SSM command alive | fixed; still confirm with `MODE=processes` after any cancel |
| Orphan helpers hold the SSM pipe after a pause | `frankie_box_pause_root.sh HANDOFF=reap-orphans` |
| Stop control queued behind a render | `stop_cycle` shares the `box-pause` lock now |
| Journal-stack workflow reduces a PINNED snapshot request for any day | `reconcile_ingest()` stops a wrong day; parameterizing is Greg's call |
| Pod stuck at status None for hours | picker now takes in-stock GPUs only; check `action=list` |
| Runpod HTTP 402 | balance empty - tell Greg |
| Cycle-0 script hard-codes day 20211004 / cycle 00 | "change dates only" is NOT yet possible on this path; a new day needs code first |

## 9. Open and contradictory - ask, do not resolve

- `SPEC-decouple-granite.md` is a draft awaiting Greg's confirmation (is C14 an original role?).
- Post-principal order: drop-in says record -> correction -> record; `MONDAY_CHECKLIST` adds
  launch `RESUME=1 WAIT_SHA256` between them and a final `RESUME=1` before retain.
- Queueing: the drop-in says one pending run per lock; since f5b13a4d each cycle0 dispatch has
  its own concurrency group, so an early principal starts immediately rather than queueing.
- Granite Pod id `fhiwwlouzyx6l2` is still the default in `frankie_pod_control.yml`,
  `frankie_pod_prepare.yml` and `frankie_box_boss_session.py` while later docs use `pods.json`.
- The orchestrator spec still mentions a Granite pass and a canary its own header removed.
