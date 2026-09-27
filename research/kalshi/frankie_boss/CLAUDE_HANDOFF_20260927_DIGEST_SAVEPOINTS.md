# CLAUDE HANDOFF 2026-09-27 23:1xZ -- ROOT in the digest on helper-part preparation; save points after every step

Branch: `claude/agent-skills-kalshi-research-f1hr0c` (head c65688d5 + this doc).
Earlier record, same day, read if needed: `CLAUDE_HANDOFF_20260927_HELPER_RESUME.md`.

## What is running

- ROOT run: **36351808435**, dispatched 21:27:41Z from commit **b35e79b7**.
  - CODE_ROOT `/opt/frankie-box/code/b35e79b77b3a06ee82cb526480587a1f32df2485-36351591734-1/markets`
  - pid **62338**, process token stem `099d4eb6-a46d-4b94-a888-f15e55c1ee7e:` (read the full token from a probe)
- Same root, same checkpoint, no rebuild:
  - OUTPUT_ROOT `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`
  - RESUME_CHECKPOINT `.../work/bedrock/recovery-8c03f629f01747158535f3cfa4f01f2d/checkpoints/checkpoint-000000.json`
    (terminal, 2,032,203 MBO records)
  - AUTHORSHIP `/opt/frankie-box/work/monday-launch/full-20211004-20260923-r4/authorship-receipt.json`, sha256
    `ade460dede20a4557b6369ca45f653fdae24a958fd52d1f1e449da53fe8e2ec6`
  - BINDING_SHA256 `99440a65fe5ad6fa93fbeebdfda3391d9dfcbf58abb3251661e6f76adea2d90a`
  - DATA_WORKERS=48, RECONSTRUCT_MISSING=0, timeout 86400
- The digest scratch for this run is `work/derived/.digest-109f959829b14b169fd6b98d69fc3125`.

### Timeline of this run (measured)

- 21:40:45Z digest start. Publication e6ff reused. Prepared layers 0-7 reused from their receipts.
- 21:40:50Z-~22:00Z preparation on 14 helpers:
  - full_bid_ask_depth (89.5 GB compressed) was 79% through at 21:50:32Z, at about 120 MB/s.
  - Helpers ran at about 96% of a core each.
  - Before the fix the rate was 1.4-4.3 MB/s.
- Legacy tables ran concurrently and are done: no table files were open at 23:03Z.
- 23:03Z: the sharded member merge.
  - `calculation-layers/sources.sqlite` was 13.7 GB with its journal open.
  - The coordinator was sleeping and the host at about 13.7 busy cores (helpers).
  - Free disk 574 GB.
- Still to come in ROOT, all unmeasured so far:
  1. The rest of the merge.
  2. The bedrock tables on helpers, one job per table. The **`bedrock.members` table is ONE job on ONE core**;
     Greg expects one core will not cut it.
  3. Document assembly.
  4. `calculations-receipt.json`.

## Save points (c65688d5, NOT in the running ROOT)

Greg: "Put saves in after every process so we don't have to rebuild anything."

- Already in the running code:
  - publication reuse (frankie_box_boss_session._reusable_projection)
  - prepared-layer receipts (`calculation-layers/prepare-NNNNNN/receipt.json`)
- Added in c65688d5:
  - Every digest table writes `table-NNNN.save.json`. Its key is:
    - legacy: name and context
    - bedrock: name, query spec, and the pinned layer sha256s
    - plus the serializer/renderer (digest_stream, digest_render) code hashes.
    The receipt also records rows, path and byte witness. A later digest attempt of the same root reuses a table
    only on an exact key match. Legacy tables are reused only as an unbroken prefix, and the families pass reruns
    when the structures table is reused. Reused bytes are re-hashed while the document is assembled.
  - Every merge shard writes `merge-NN.save.json`, keyed by the pinned layer sha256s and the `_merge_shard` source.
- **Caveat: the running ROOT (b35e79b7) writes neither of the new receipts.** If it is stopped now, a restart on
  c65688d5 reuses the publication and all prepared layers. It redoes the legacy tables (about 33 min, run
  concurrently with the rest), the merge, and any tables written so far. From the first run on c65688d5 onward,
  nothing finished is rebuilt.

## If the members table is too slow (Greg's call)

- It is one `TS.write_table` over every group, on one core. It plans the whole table (column widths/scales), emits,
  then re-reads and verifies it.
- Splitting it across helpers changes the digest's table format (several tables or a chunked table). That is a
  format decision for Greg, and needs the verify path adjusted.
- First measure it: the probe shows `table-NNNN.txt` growing. Only its helper is busy then.

## How to operate (lessons from today, each cost a restart)

1. **Stage and dispatch the SAME commit.** The ROOT wrapper refuses "checkout differs from reviewed commit" if
   anything is pushed between staging (frankie_box_stage_code.sh, ACTION=stage) and the ROOT dispatch. Stage the
   tip, then dispatch from that tip with its CODE_ROOT from the staging receipt.
2. **Never edit `frankie_box_projection.py`.** The retained projection plan pins its bytes (code_sha256
   `2cedd8c9...`). Any edit refuses the root with "retained projection plan differs".
3. **Pause:** `frankie_box_pause_root.sh` with `HANDOFF=terminal-digest`, plus DIRECTORY, CHECKPOINT_DIR,
   EXPECTED_PID, EXPECTED_PROCESS_TOKEN (from a probe) and BINDING_SHA256. Since 87f16198 it finds helpers started
   from any thread.
4. **After a pause**, check for orphans with `frankie_box_read_log.sh MODE=processes`
   (FILE=work/monday-calculations/<root>/progress.json). If any spawn helpers with parent 1 remain, run
   `HANDOFF=reap-orphans EXPECTED_ORPHANS=<pids>` (a7e1b34a). Orphans hold the SSM pipe, so the ROOT GitHub run
   never closes and the serial queue blocks.
5. **Queues:** progress.sh and read_log.sh use box-progress; pause and root_cpu use box-pause; everything else
   (ROOT, staging, inventory) uses box-run. Each group keeps one pending run, and a newer pending run cancels the
   older one.
6. **Probes:**
   - progress.sh RESOURCE_METRICS=1: ROOT's open files and sizes, host CPU ticks (sum over 20 s / 20 / 100 = busy
     cores), free disk.
   - read_log MODE=processes: every helper's CPU seconds, affinity, and read positions of files under the root.
   - read_log with a nonexistent FILE in a directory prints `ls -la` of that directory.

## Commits today on this branch (after 106ca918)

| commit | change |
|---|---|
| 6275f4e4 | the pusher zips any published file of 90 MB or more (Greg's rule); restore reads .gz |
| 5b1eaffd | projection module back to 2d3e6bb bytes; publication reuse moved to the caller |
| 7485d648 | helpers write prepared-layer parts; the coordinator copies them inside SQLite (30-80x on the box) |
| 87f16198 | the pause scans every thread's children |
| 08d2ac40 / 38f8f829 | read-only process listing with read positions |
| a7e1b34a | pause HANDOFF=reap-orphans |
| c65688d5 | table and merge-shard save points |

## Open decisions for Greg

1. `bedrock.members`: keep one core, or split it (a format change). Decide once it is measured.
2. Whether to stop the running ROOT to move onto c65688d5. My recommendation: no, let it finish unless the
   members table measures too slow. Stopping now costs the legacy tables and the merge (see the caveat above).
3. The publication verification slice, Option 3 (receipt-level evidence, unverified hash checks listed), once
   `calculations-receipt.json` exists.

## Order after ROOT (corrected 2026-09-27 23:4xZ; the 12-line list above it dropped steps)

The earlier list said only "principal" and listed "grading" as its own steps. Checked against the scripts on this
branch, the Monday sequence is as below. Nothing was missing from the code; the steps were missing from the plan.

1. `calculations-receipt.json`: read with `frankie_box_read_log.sh MODE=receipt`; keep its sha256. Completed status,
   2,032,203 records, 0 failures.
2. Publication slice, Option 3 (receipt-level evidence, the unverified hash checks listed). No script exists yet.
3. Stage ONE commit (`frankie_box_stage_code.sh ACTION=stage`) after ROOT frees the box-run queue. Every step below is
   dispatched from that same commit (MARKETS_SHA must equal the staged checkout HEAD). The commit must carry the
   calculation pin the request was rendered under, or ACTION=principal refuses (`_pin_matches_request`). The tip carries
   the classroom runtime a80990d (fourteen classroom preparation helpers); its lines are all intact at 1524dfee.
4. `frankie_box_principal_inputs.sh`: fresh OUTPUT_ROOT under work/principal-inputs, CALCULATIONS_RECEIPT and its sha256.
5. `frankie_box_cycle0.sh ACTION=config`: PREPARED = the existing
   /opt/frankie-box/work/trading-day-preparation/full-20211004-20260927-r6-48 (do not reprepare), PRINCIPAL receipt, fresh
   RUN_ID and OUTPUT_ROOT. The config binds the five-lesson Granite priming
   (`blocks/GRANITE_PRIMING_CONFIGURATION_20260922.json`, host_config.py). COMPLETION_REF defaults to
   claude/agent-skills-execution-tzh7sw.
6. `ACTION=launch`: one cycle, pending-return. Exit 3/4 with a WAIT is pending, not failure. The Granite Pod
   (fhiwwlouzyx6l2) must be up. The priming is delivered in this first request; verify the request's knowledge hash and
   the model's acknowledgement from the actual receipts.
7. `ACTION=principal` (CALCULATIONS, REQUEST_DIRECTORY): verify -> reading -> **CLASSROOM** (the Dipole classroom,
   mandatory) -> **TEACH** (exhaustion teach-back, `work/teach/exhaustion-teachback.json`) -> writing
   (frankie_box_boss_session.py `_run`). No output caps.
8. `ACTION=record TURN=initial`: records the response and host attestation; the classroom pre-grade runs here.
9. `ACTION=launch RESUME=1 WAIT_SHA256=<retained WAIT>`: the runner grades the initial response (teachback, post-grade,
   novel findings, novelty investigation) and writes `classroom-correction-request.json`, then waits
   (dipole_classroom_final_review.py, "same Frankie session must consume Dipole classroom correction").
10. `ACTION=correction`: the same BOSS session answers the classroom correction.
11. `ACTION=record TURN=correction`.
12. `ACTION=launch RESUME=1`: the runner validates the correction, writes the acknowledgement, completion, transcript
    and `dipole-classroom-receipt.json` (final grading); the cycle completes.
13. `ACTION=retain`: pushes the response and brain; files of 90 MB or more are gzipped (6275f4e4).

Tuesday stays pending. Every box action needs Greg's go. Keys are not rotated until the build is done.
