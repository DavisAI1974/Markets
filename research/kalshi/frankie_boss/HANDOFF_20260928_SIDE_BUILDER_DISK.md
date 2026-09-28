# HANDOFF 2026-09-28 ~04:35Z: Monday ROOT, side builder filled the disk again

Branch: `claude/agent-skills-kalshi-research-f1hr0c` (tip after this commit). Checklist:
`research/kalshi/frankie_boss/MONDAY_CHECKLIST_20260927.md`. Box `i-035994afa8bdf66a5` (us-east-1).

## Standing rules (Greg)
- Every box action needs Greg's go. Keys are not rotated until the build is done.
- Stage and dispatch the SAME commit, with no push in between.
- Never edit frankie_box_projection.py. Tuesday stays pending.
- No tests or validations: the live run is the validation.
- Save code everywhere (stop/fix/restart keeps all data). Do a read-only single-core CPU scan before each step.
- Cross checklist items off from receipts only. Classroom science changes only if outputs improve.
- **Do not grow the box unless we absolutely have to.**
- Greg's directive for the new session: **run the code-review skill (agent-skills plugin, `code-review-and-quality`) YOURSELF on
  our build code** (the digest/bedrock writer path) before anything else, starting with the question below.

## State
- ROOT (b35e79b7) was PAUSED cleanly at 01:05Z (receipt `pause-for-terminal-digest-62338.json`, checkpoint 2,032,203
  records). sources.sqlite (82 GB) and legacy tables 0-4 were ADOPTED as save points at 01:13Z (run 36364858997).
- The side builder (run 36373163230, code 723e5020, 30 threads on CPUs 1-15 plus siblings, scratch
  `work/derived/.digest-side-work`) is building bedrock table 7 (bedrock.members).
  - Snapshot pass SAVED (`.digest-side-work/table-0007/passes.pkl`, 03:19:53Z to 03:48:42Z).
  - Plan pass crashed at 04:09:32Z: **disk full**. Confirmed by the EC2 console log (run 36377558316,
    `journald: No space left on device` at 04:13Z); there were no OOM lines.
- **SSM cannot run anything** (the agent needs disk). Every SSM script fails in about 10 s with empty output.
  The box is still Online.
- The new read-only console step works whenever SSM does not: script `deploy/aws/box/frankie_box_console.sh`
  (commit 77ee2807).

## THE QUESTION (Greg): how did the plan pass write over 460 GB in about 20 minutes?
**Answered in `REVIEW_20260928_PARALLEL_WRITER_DISK.md`.** From the run logs, the plan pass most likely finished (it
took 18.5 min on the first run), and the COUNT pass filled the disk. The option A boothook must also delete `freq.sqlite`.
The suspect is the plan pass in `deploy/aws/box/frankie_box_digest_parallel.py` (`_plan`, around line 148). For EVERY
row it stores `TS._dump(cells)`: a JSON list with one `(kind, text)` pair for EVERY column in the table-wide
column union, including `?` (absent) and `=` (derived) cells. bedrock.members is wide and sparse, so the stored size is
rows x union-width, many times the 82 GB source.
- 30 helpers writing SQLite with no journal can plausibly sustain about 400 MB/s, which is 460 GB in 20 minutes.
- Verify this by review and by measuring on the box once SSM is back (the size of one part's plans.sqlite against its
  row count and column count).
- Also review `_count` (freq per part), `_final` (final.sqlite, again every row) and the merge for the same pattern.

## WIP fix (NOT applied; a patch only)
`research/kalshi/frankie_boss/wip/parallel_lean_plan_WIP_20260928.patch`:
- Plan and count happen in ONE read, and no plan is stored. Columns that may still be derived or constant in a part are
  held apart, so the counts are exact.
- The final pass re-plans from the seed and writes tab-joined rows.txt directly. The copy step translates tab to space
  when sep is space. This removes final.sqlite and the emit pass.
- STILL TODO:
  - The `write_table_parallel` driver: steps snapshot, plan, merge (add the held counts of kept columns only, and
    number by min(first)), final, copy.
  - Checkpoint V2, adopting the saved V1 snapshot. The legacy 723e5020 parallel.py sha256 is
    `9ffbd7d48289d2fd27d919f6fc8f05620a75f32b2471baa17f8b31f2ba2db864`. Adopt ONLY the 'snapshot' pass, and only when
    `_snapshot`, `_source_rows`, `_fold` and `_readonly` and the DG/TS/S modules are unchanged.
  - The relaunch must use the SAME CPU list (the specs sha depends on 2 x len(cpus) parts).

## Recovery (needs Greg's go; both are box power actions)
- A (no growth, recommended by the rule):
  1. Stop the instance.
  2. Add a guarded one-time cloud-boothook to user-data. Read and keep the existing user-data first, and combine as MIME.
     The boothook deletes ONLY `.../monday-calculations/full-20211004-20260927-r1-48/work/derived/.digest-side-work/table-0007/part-*/plans.sqlite`,
     which is the unsaved plan pass.
  3. Start the instance, wait for SSM Online, then run disk_usage.
- B: grow EBS a little and reboot (cloud-init growpart/resizefs runs on every boot). This is permanent growth, and the
  grow step is hardcoded to 2048.

## After recovery
1. Clean the plans files if they remain.
2. Finish and review the lean writer, stage and dispatch it, and relaunch the side builder on the same CPUs. It resumes
   from the saved snapshot.
3. Restart ROOT with the staged inputs below.
4. Continue downstream: principal inputs, cycle0 config, Granite Pod (Greg's go), launch, principal, record, resume and
   grading, correction, record, resume final grading, retain.

ROOT restart inputs:
- Script: `frankie_box_monday_calculations.sh`
- AUTHORSHIP: `/opt/frankie-box/work/monday-launch/full-20211004-20260923-r4/authorship-receipt.json` (sha ade460de...ec6)
- OUTPUT_ROOT: `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`
- RESUME_CHECKPOINT: `.../work/bedrock/recovery-8c03f629f01747158535f3cfa4f01f2d/checkpoints/checkpoint-000000.json`
- BINDING_SHA256: `99440a65fe5ad6fa93fbeebdfda3391d9dfcbf58abb3251661e6f76adea2d90a`
- DATA_WORKERS: 48

Restage the code if it changes.

## UPDATE 2026-09-28 (later): all review fixes built (Greg: "Do all the fixes and improvements"; ask ladder not intended)
Review: `REVIEW_20260928_PARALLEL_WRITER_DISK.md`. Nothing staged, nothing dispatched, no box action.

What changed (branch `claude/frankie-monday-continuation-qlkvqr`):
- **Ask ladder** (`frankie_box_digest_parallel.MEMBER_LIST_PATHS`): the member column `book_full.ask_levels_full` (the whole
  ask ladder with every FIFO queue, whole on every group row: a missing `[]` in the pinned crosswalk, whose carrier says
  `ask_levels_full[]`) is carried as `book_full.ask_levels_full[]#count`, the way the bid ladder is. The crosswalk, the
  layers, the ledgers and sources.sqlite are untouched. This changes bedrock.members, so its table-7 snapshot is redone
  (~29 min); the saved V1 snapshot cannot be adopted (its columns differ).
- **Lean writer** (`frankie_box_digest_parallel.py`): plan + counts in one read, no stored plans; counts keyed by sha256
  in WITHOUT ROWID tables (no uncompressed key text); the merge numbers digests; the final pass re-plans from the seed
  and writes the row text plus the text of the dictionary entries it numbers first; the copy deletes each part as it
  appends it (peak = table + one part); the inverse proof streams each part; no final.sqlite, no emit pass; the
  snapshot no longer repeats the unfailable spool round trip.
- **Disk guard**: every helper and the copy stop with `DiskReserve` before free space falls under 32 GiB (SSM and
  journald keep working); saved passes stay.
- **Checkpoint V2**: each pass is saved with the hash of the code it and the earlier passes depend on; a rerun keeps
  every pass whose code is unchanged and whose files the next pass needs still exist. A V1 scratch is removed whole
  (this also clears the old plans/freq files once the builder can run).
- **Legacy tables 0-4 stay save points**: `frankie_box_digest_document.legacy_key` keys a legacy table on the code that
  reaches its bytes only (digest_stream, digest_render, per_second_rows); the adopted receipts (keyed on the whole
  code identity) still match. sources.sqlite's key (S functions) is unchanged, so it is reused.
- **Disk rescue** (the corrected option A, a box power action, Greg's go only): dispatch `frankie_box_run.yml` with
  script `deploy/aws/box/frankie_box_disk_rescue.sh` and variables `CONFIRM=GREG_GO_DISK_RESCUE_TABLE_0007`. The
  workflow (EC2 API, no SSM) stops the box, adds the one-time boothook `frankie_box_disk_rescue_boothook.sh` beside
  the existing user-data (kept byte for byte; refused if it cannot be combined or exceeds 16 KB), starts it and waits
  for a fresh SSM ping. The boothook prints every table-0007 part's plans/freq/final sizes and free disk to the console
  (the 461 GB byte split), deletes only those stage files, and marks itself done. `frankie_box_console.sh` also shows
  its lines.

Second review (fresh context), all fixed in the follow-up commit: a Critical crash on 1-row tables (`bedrock.run`), plus
key coverage, a conflict check and disk checks. See section 6 of the review.

Order after Greg's go:
1. Disk rescue (above). Then `frankie_box_disk_usage.sh` (read-only) for free disk.
2. Stage the tip (`frankie_box_stage_code.sh ACTION=stage`), then relaunch the side builder from the SAME commit on the
   same CPUs (`frankie_box_bedrock_side.sh CPUS=1,...,15 SIBLINGS=1`, CODE_ROOT from the staging receipt).
3. Restart ROOT on that same staged commit with the inputs above (legacy tables and sources reused; bedrock tables
   adopted from the side scratch).

## UPDATE 2026-09-28 ~07:45Z: deployed, ROOT re-dispatched, CLM sidecar built
- **Disk rescue ran (Greg's go).** The boothook measured the 461 GB: **plans.sqlite 44.4 GB, freq.sqlite 416.8 GB.** The
  count pass filled the disk, as the review predicted. Those files were deleted; free disk was 461.3 GB afterwards.
- **Lean writer deployed** (staged 60b8b8cd, side builder run 36386769736). All 18 bedrock tables were built and
  inverse-proven in 24.6 min.
  - bedrock.members: 1,535,939 rows, 1.0 GB, 18 min 10 s.
  - Snapshot pass: 4 min 25 s, against 28 min 49 s on the old code.
- **ROOT restart** (run 36389358724, 60b8b8cd) reused every layer and table, then stopped at assembly with `KeyError: 'kinds'`.
  The resume receipt had no journal entry kinds. Fixed in 80f5c2c0. **5fb84365 was staged 07:40:24Z** and ROOT was
  re-dispatched from it with the same inputs.
- **CLM sidecar** (5fb84365; `research/kalshi/frankie_boss/clm_sidecar/README.md`): standalone and not wired in. The box
  extract is queued behind ROOT (STAMP=monday-20260928a). After it finishes, dispatch the Pod step with
  `DATASET_KEY=<manifest key> STAMP=monday-20260928a`.
- **Decisions store drift (existing before this session, not fixed):** `DECISIONS.md` has lines the store lacks (for
  example a second D49 on the CME trading day), so `store.py check --write` would silently drop them.
  - D51 was added to the store, and its rendered line was appended to DECISIONS.md.
  - Reconcile the drift by moving the md-only lines into the store before any `--write`.

## Ideas, not directives (Greg, 2026-09-28)
- If Granite still struggles, consider a System One decision model for its decision calls: TypeSafe **Jev** (closed,
  API), or the open **Stanford/NVIDIA CLM-8B** (Apache-2.0, frozen Qwen3-8B plus trainable heads, so it can be
  customised and pinned).
  - An interpreter would render its typed decisions as text.
  - Granite's prose roles (reading notes, merges, ledgers, narrative) would stay with an LLM.
  - Map of Granite's roles against output types: see this session's analysis. The critic verdict, the classroom
    claims, the dispositions and the accounting status are the bounded decisions.
- The same model class fits the **trade-execution layer**: fire/hold, maker/taker, size bucket, cancel/replace.
- **D51:** a gate is the STARTING role for these, and for the dipole direction map, not the destination. Promotion is
  per cell on forward evidence: gate, then advisor, then decider. It is recorded in CLAUDE.md, BUILD_PLAN.md, the
  decisions store and the signal_retest_registry policy. `odcore/info_dipole.py` is deliberately not edited: its bytes
  are pinned in `DIPOLE_SHARED_CATALOG_20260922.json`, which principal inputs reads.
