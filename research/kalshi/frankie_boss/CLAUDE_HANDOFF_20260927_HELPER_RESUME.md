# CLAUDE HANDOFF 2026-09-27 -- ROOT resumed on the helper-parallel runtime (106ca918)

Branch: `claude/agent-skills-kalshi-research-f1hr0c` (code head 106ca918; this doc lands after it).
Read this first in the next session. Earlier context: `CODEX_HANDOFF_20260927_PROJECTION_RUNTIME.md`,
`CCODE_PROJECTION_PUBLICATION_SLICE_20260927.md`.

## What is running now

- ROOT resume = GitHub run **36346193733** (`frankie_box_run.yml`, script
  `deploy/aws/box/frankie_box_monday_calculations.sh`, dispatched 19:56:51Z on 106ca918, timeout 86400).
- Same root, same checkpoint. No new root, no ledger rebuild (ledger build is frozen).
  - OUTPUT_ROOT `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`
  - RESUME_CHECKPOINT `.../work/bedrock/recovery-8c03f629f01747158535f3cfa4f01f2d/checkpoints/checkpoint-000000.json`
    (terminal, 2,032,203 MBO records)
  - CODE_ROOT `/opt/frankie-box/code/106ca918ca61842b100dd272bd8e0392f8582f35-36344833845-1/markets`
    (from the staging receipt of run 36344833845; pack sha256 `82c8e585...57a0`, 3,686 files)
  - AUTHORSHIP `/opt/frankie-box/work/monday-launch/full-20211004-20260923-r4/authorship-receipt.json`,
    sha256 `ade460de...8e2ec6`; BINDING_SHA256 `99440a65...d90a`; DATA_WORKERS=48; RECONSTRUCT_MISSING=0.

## How it got here (receipts)

- The previous ROOT (run 36339291716, runtime 2d3e6bb, pid 60813) finished publication `published-e6ff4090...`
  and entered the digest, where the legacy tables and the 89.5 GB `full_bid_ask_depth` prep ran on one core.
- Pause run **36344863172**: `HANDOFF=terminal-digest`, receipt
  `.../pause-for-terminal-digest-60813.json` (sha256 `0d3ad440...8f97`). Process and its 14 owned helpers
  exited; terminal verification re-read the chain and full state (`checkpoint_hash c3281f87...becb`,
  driver state `22af7701...f78ee`, 2,032,203 completed); `unsaved_tail_may_require_reconstruction: false`.
- The ROOT run then ended `failure` at 19:35:35Z. That is the expected result of the SIGINT handoff, not a defect.

## What 106ca918 changes (commits e53c38db .. 106ca918)

Digest (ROOT):
- The published projection is reused on rerun: `_reusable_publication` accepts a `published-*/receipt.json`
  with the same plan, layers, fields and sizes, so e6ff is not rebuilt.
- Published layers are prepared per fragment on the 14 helpers (sha256 and row count are checked per
  fragment against the range receipts). The prepared layer is saved with a receipt and reused on rerun.
- The bedrock member merge is sharded 14 ways by group key, and runs on the helpers.
- BedrockSources is built on a thread while the five legacy tables run.

Downstream (fixed before those stages start):
- docs/brain hash ledgers and layers with batched parallel sha256 (no whole-file reads).
- teach streams gzip-json layers.
- Staged reading uses a galloping search.
- Tokens are counted in batches, and the chunk cache is keyed by data hash.

Pause script: `terminal-digest` mode.

## What to check on the startup probe

`frankie_box_progress.sh`, run over `frankie_box_run.yml` (concurrency group box-progress), with:
- `CODE_ROOT=<above>`
- `DIRECTORY=<OUTPUT_ROOT>`
- `RESOURCE_METRICS=1`

Expect to see:
- stage root-digest
- publication e6ff reused (no new `published-*` directory)
- helpers busy on the `full_bid_ask_depth` fragments while the legacy tables run on the coordinator

## Open decisions for Greg

1. **docs/brain push size.** The docs/brain stages copy `derivation-digest-full.md` into git docs. If the
   digest is over 100 MB, that push fails. Decide the route before the principal step.
2. **Publication verification slice.** Greg chose Option 3: accept receipt-level evidence and list the
   unverified hash checks explicitly. Amend and run it once `calculations-receipt.json` exists.
3. The pre-existing red tests are not from this work: stale `request_directory` fixtures and a CI-only
   renderer reference.

## Order after ROOT

1. calculations receipt
2. publication slice (Option 3)
3. principal inputs
4. cycle0 config
5. launch
6. principal
7. record
8. grading
9. correction
10. record
11. final grading
12. retain

Tuesday stays pending.

Every box action still needs Greg's go. Keys are not rotated until the build is done.

## Startup probe (run 36346342291, 19:59:46-20:00:06Z)

- ROOT pid 61435, token `099d4eb6-...:56246455`, state R, coordinator affinity [1], RSS 0.6 GB.
- Stage `root-ledger-verify-member`: sha re-read of the frozen retained ledger
  `recovery-9defa316.../ledgers/exact_member_rows.jsonl` (537,182,189,410 bytes). It had read 78.8 GB at
  about 1.05 GB/s (about 8 min in all). Read-only, no write; the ledger is not rebuilt.
- Free disk 762.7 GB; no swap; memory pressure 0.
- Next check: after the verify, the digest should reuse publication e6ff and put the helpers on
  `full_bid_ask_depth`.

## Resume 36346193733 refused at the projection plan (20:10Z) -- my defect, fixed in 5b1eaffd

- The resume ran the ledger checks, loaded the 8c03 state, reused the 44 retained legacy layers and ran the
  pinned traversal. Then `projection.project` raised `ValueError: retained projection plan differs`
  (frankie_box_projection.py:304). Nothing was written.
- Cause: the projection plan pins `code_sha256 = sha256(frankie_box_projection.py)`. The publication save point
  (3e89b860) had been added to that file, so its bytes changed and the retained plan no longer matched. The
  refusal is correct behaviour.
- Fix 5b1eaffd:
  - frankie_box_projection.py restored to its exact 2d3e6bb bytes (sha256 `2cedd8c9...1ab7d`).
  - The save point moved to `frankie_box_boss_session._reusable_projection`. It rebuilds the plan exactly as
    project() does and requires it to equal the retained plan.json. It reuses a published-*/receipt.json of that
    plan only when every layer file is present at its recorded size; otherwise project() runs.
- Rule for later edits: never edit frankie_box_projection.py while a retained plan is meant to be reused.
- Also in this branch: 6275f4e4. The response pusher zips any published file of 90 MB or more to `<name>.gz`
  before the git push (Greg's rule). restore_from_git reads the .gz form.

## Resume 36347691133 (5b1eaffd): publication reused, preparation too slow; stopped and fixed (20:34-21:11Z)

- The 5b1eaffd resume passed the plan check and reused publication e6ff. The digest started at 20:34:12Z.
- Published layers total 147 GB compressed:
  - full_bid_ask_depth 89.5 GB
  - derived_v4_mechanics_fifo_features 30.4 GB
  - queue_age_and_survival 11.5 GB
  - fifo_queues 11.4 GB
  - the rest under 5 GB
- Measured preparation rate: about 1.4-4.3 MB/s compressed, so 10-29 h for preparation alone. The host showed
  about 2 busy cores, and each helper was about 27% busy.
  - Cause: every decoded row went back to one coordinator thread, which unpickled and inserted it from Python and
    shared the interpreter lock with the legacy tables. This came from my 106ca918 split.
- Fix 7485d648: helpers write their rows, with final ordinals from the range receipts, into part databases. The
  coordinator copies each part with INSERT ... SELECT inside SQLite. rows.sqlite content is identical (old and new
  checked on synthetic fragments), so prepared layers 0-7 (receipts written) stay reusable.
- Greg: "stop and fix root".
  - Pause 36350219973 (terminal-digest) of ROOT 61709: receipt `pause-for-terminal-digest-61709.json`, sha256
    `8e782d87...077f`; state re-verified at 2,032,203 records.
  - That pause missed the helpers: it read only the main thread's /proc children, and the digest helpers are
    started from the bedrock-sources thread.
    - A read-only listing (read_log MODE=processes, 08d2ac40) found 14 orphaned helpers plus the resource tracker
      (parent 1, CPUs 2-15). They were holding the SSM pipe, so the ROOT run stayed open.
    - Fixes:
      - 87f16198: the pause scans every thread's children.
      - a7e1b34a: HANDOFF=reap-orphans terminates exactly the listed PIDs after identity checks.
    - Reap 36350696475: all 15 exited on SIGTERM; receipt `reap-orphans-61709-1790543422.json`.
    - The ROOT run then closed at 21:10:35Z. The box is idle.
- Still single-core in the digest:
  - The 5 legacy tables (about 33 min). They run concurrently with preparation.
  - The one `bedrock.members` table job. Splitting it changes the digest table format, so measure it first.
- Next: stage a7e1b34a and resume the same root from 8c03 ON GREG'S GO. Then probe once: part files flowing, all
  14 helpers busy, the rate, and disk.
