# Drop-in for the next chat - Frankie/BOSS, after 2026-09-17 third session (Claude Code, OPUS)

Paste to Claude Code. Repository `DavisAI1974/Markets`. Run `using-agent-skills` first, then `shipping-and-launch`.

```
git fetch origin claude/first-run-using-agent-skills-bd52fj
git checkout -B claude/first-run-using-agent-skills-bd52fj origin/claude/first-run-using-agent-skills-bd52fj
git log --oneline -1          # expect the 'docs: session close' commit; last CODE commit is 1d07b0c
```
Read, in order: `CLAUDE.md` (top block), `research/kalshi/frankie_boss/CLAUDE_HANDOFF_20260918.md` (the LAST FOUR
sections are this session; the final one is the close), then `CLAUDE_HANDOFF_20260917.md` only for a reconciliation
question.

Container setup (nothing survives): `pip install torch --index-url https://download.pytorch.org/whl/cpu` and
`pip install cffi "databento-dbn==0.62.0"` (boto3, zstandard present). Keys: Greg drops the AWS pair into
`~/.config/markets/env` (chmod 600) when an AWS action is needed; run AWS commands with the proxy placeholders unset
(`env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN python3 ...`).

## State in one paragraph

Last code commit `1d07b0c` (the docs commit sits on top). Family GREEN (1018 passed, 1 skipped, nothing deselected). **The ingestion standard is now
`journal_stack_execution.TARGET_BOXES = 1189`** (Greg: the gold standard for every day we ingest going forward); the
partition length derives from it, so the Sunday's 114,054 entries give 96/box = exactly 1,189 boxes, where the old
hardcoded 16 gave 7,129. **This moves the compact journal's bytes and sha256** - the first run's `19603159...` no
longer reproduces and a Sunday re-run is a full new baseline (new compact journal, new prefixes directory, new run
id; the retained 19 prefixes are bound to the OLD compact sha and will be refused, correctly). The two host scripts
`deploy/aws/host/day_schedule_prefixes.ps1` and `day_cycles.ps1` are BUILT but NEVER EXECUTED; the day and the host
roots reach them as `ssm_run_ps1.py --set` assignments. `day_pipeline.reconcile_ingest()` now refuses an ingest
receipt whose record count is not the day's staged count. Native host `i-0e90ee6110ef609aa` r7i.8xlarge, STOPPED.
Launch is HOLD. Receiver `2ebb8ce8` is a sibling checkout, not merged.

## FIRST BUSINESS - a decision Greg owes, before any work

**`a9ab5ec4` on `codex/journal-reduction-stack-20260915` is mine and unrequested.** A dispatched journal run was
cancelled 90 s in, and the publish step is `if: always()`, so it committed
`outputs/frankie-boss/20260915/reduction-stack/runs/35178520927/` - one part of eight, and a
`verification-failure.json`, under the archiver's fixed message "preserve complete journal stack result". **Ask Greg:
revert it or leave it for Codex.** Do not touch that branch otherwise. Structural point for Codex either way: ANY
cancelled or failed journal run writes such a directory there.

## Then: one family run before anything else

`PYTHONPATH=.:research/kalshi/frankie_boss:research/kalshi/frankie_boss/tests python -m pytest -q
research/kalshi/frankie_boss/tests/test_granite*.py .../test_sunday*.py .../test_run_actual*.py
.../test_frankie_controller.py .../test_actual_host*.py` -> expect 1018 passed, 1 skipped. If `T_CTX` surfaces, dig
into the number; else leave it (Greg's call, still pending his row count).

## ARE WE READY TO LAUNCH SUNDAY? No. Two hard blockers, neither weekday-specific

1. **The Pod credential cannot reach stage 5.** `run_actual_sunday` takes it on stdin; an SSM-sent script has no
   stdin. Spec prerequisite 6, never built. This is the highest-value buildable item and Claude offered to take it:
   read it once from an SSM parameter into the process, never a file.
2. **The fresh run configuration cannot be validly authored.** `launch_pins.validate` refuses the historical
   `UNPROVEN` literal for a new run, so `principal_admission.sealed_proof` needs a real
   `FRANKIE_SEALED_ABSENCE_PROOF_V1` path - and nothing produces that file. `native_sealed_absence` is not in this
   tree; it is receiver-side on `2ebb8ce8` and BOSS only verifies. **Receiver work, Greg/Codex.**

Then Greg's own: the fresh `actual-host-configuration.json` (reviewed BOSS tip, receiver commit from
`launch_pins.NEXT_RUN`, a new completion ref, host paths, new `run_id`/`run_directory`, and a `prefixes_directory`
that is FRESH, not the retained one), and `host_variables` in `operations/day_pipeline.configuration.json`
(`HOST_TOOLS_ROOT` / `HOST_PYTHON` / `HOST_RUN_ROOT` are placeholders; both scripts refuse on them).

## Open, in priority order

1. The `a9ab5ec4` decision above.
2. The Pod credential over an SSM parameter (unblocks stage 5).
3. The receiver's sealed-absence proof producer (unblocks the configuration).
4. **Per-record ingest cost is unprofiled and it is the scale problem.** Measured from the first run's receipt:
   37.3 ms of CPU per record, 97% worker dedication, so it is compute and not transfer. One weekday is 20.7 CPU-h,
   four weeks is 352.7 CPU-h (4.9 days on a 4-vCPU runner, 11.4 h on the 32-vCPU host). Six-fold fewer partitions
   removes per-partition overhead but the per-entry work (canonical re-serialisation, per-entry sha256, gzip level 6)
   has NOT been profiled and cannot be here - the bundle is 11.7 GB behind S3. **The next measured run gives the new
   per-record number; if it has not moved, that profile is the job.**
5. The journal job is **pinned to one snapshot request** (`.github/frankie-parallel-source-request.json`, the first
   run's bundle) and takes no day; its publication path is hard-coded `20260915`. Harmless for Sunday - the pinned
   bundle IS the Sunday - and wrong for any other day. `reconcile_ingest()` now refuses the mismatch rather than
   filing it, but only Greg can parameterize the workflow.
6. Reaching 1,189 boxes on a BIG day needs the block format changed (`MAX_ROWS` 256, `MAX_BYTES` 32 MiB; a weekday
   would need 3,355 entries and ~350 MB per box). Not done, deliberately. A weekday clamps to 256/box today.
7. `ng_exhaustion_step1_receipt_count_20260823.yml` fires on every push to this branch and has failed 677 times.
   Noise; delete or restrict its paths when Greg says.

## Do not

Dispatch any workflow, or edit one, without Greg's explicit go - **and a go to "run Sunday" is not a go to change a
workflow; that is this session's nonconformance.** Run Frankie, Granite, the Pod or EC2 without his go. Touch
`codex/journal-reduction-stack-20260915`. Point the prefix builder at the retained prefixes directory. Rebuild the
prefix/reducer machinery (the packing is the ONE declared exception and it is already made). Reintroduce the retired
Granite smoke context. Quote token projections at 4,096 rows. Average anything. Skip or deselect a test to get green.

## Standing orders (Greg)

Nothing local: git and S3. Per-event, never average. Shrinking the packet is a top job. 8 native threads, fixed.
Memory A is VALID; no validation day exists or is required. Keys do not rotate during the walk. Ingestion stays the
journal-stack job already on git - **no second ingestion path and no Databento call** (the days are in S3 under
`nymex/ng_mbo_5y_v0`, put there by `ng_historical_mbo_5y_to_s3_20260820.yml`, the only workflow holding the API key;
`stage_block_sources` decodes bytes already fetched, so nothing in the chain bills the vendor).
