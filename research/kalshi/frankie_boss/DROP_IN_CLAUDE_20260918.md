# Drop-in for the next chat - Frankie/BOSS, after 2026-09-17 (Claude Code, OPUS is fine for this chat)

Paste to Claude Code. Repository `DavisAI1974/Markets`. Run `using-agent-skills` first, then `shipping-and-launch`.

```
git fetch origin claude/first-run-using-agent-skills-bd52fj
git checkout -B claude/first-run-using-agent-skills-bd52fj origin/claude/first-run-using-agent-skills-bd52fj
git log --oneline -1
```
Read, in order: `CLAUDE.md` (top block), `research/kalshi/frankie_boss/CLAUDE_HANDOFF_20260918.md` (whole file; the last
section is the latest), then `CLAUDE_HANDOFF_20260917.md` only if a reconciliation question comes up.

Container setup (nothing survives): `pip install torch --index-url https://download.pytorch.org/whl/cpu` and
`pip install cffi "databento-dbn==0.62.0"` (boto3, zstandard are present). Keys: Greg drops the AWS pair into
`~/.config/markets/env` (chmod 600) when an AWS action is needed; run AWS commands with the proxy placeholders unset
(`env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN python3 ...`).

## State in one paragraph

Integrated tree (recovery + classroom + review) with the Granite smoke context retired (131,072 only) and the Granite
test family GREEN (1018/1019 passed, nothing deselected). Audit findings 3 and 6 CLOSED; 4, 5, 2+7, 8 landed on the BOSS
side (explicit `principal_admission` per run; classroom-composed compact-source dispatch; `launch_pins.py`; clean
receiver-checkout refusal; BOSS Memory A witness). Memory A is VALID (Greg). The beginning-to-end chain is BUILT: the
started workflow `frankie_journal_stack.yml` now runs sources -> journal (gold standard, unchanged) -> host stages, driven
by `operations/day_pipeline.py` with git receipts, resume, HOLD before cycles without a go, and a measured CPU-dedication
gate. Native host `i-0e90ee6110ef609aa` is RESIZED to r7i.8xlarge (32 vCPU), stopped. Launch is HOLD. Receiver `2ebb8ce8`
is a sibling checkout, not merged. 32 = the Pod's CPUs (Granite), 48 = the reader's worker cap, 8 = native threads.

## First business (bare-minimum tests: one run per slice, one family run at the start)

1. ONE family run: `PYTHONPATH=.:research/kalshi/frankie_boss:research/kalshi/frankie_boss/tests python -m pytest -q
   research/kalshi/frankie_boss/tests/test_granite*.py .../test_sunday*.py .../test_run_actual*.py
   .../test_frankie_controller.py .../test_actual_host*.py`. If item `T_CTX` surfaces here, dig into the number; else leave it.
2. The two host scripts the pipeline configuration names: `deploy/aws/host/day_schedule_prefixes.ps1` (wraps
   `build_remaining_sunday_prefixes.py --configuration`) and `deploy/aws/host/day_cycles.ps1` (wraps
   `run_actual_sunday_compact_source.py --configuration`, classroom-composed). Each ends with ONE line
   `PIPELINE_RECEIPT {json}` carrying the fields in `day_pipeline.GATES` (`prefix_count`, `prefixes_sha256`;
   `cycles_completed`, `cycles_total`). Windows host, PowerShell, `ssm_run_ps1.py`.
3. The fresh configuration: copy `sunday_20260915_package/FB/sunday-launch-20260915/actual-host-final-configuration.json`
   and change ONLY `host_runtime.boss_commit` (reviewed tip), `receiver_commit` (full sha in `launch_pins.NEXT_RUN`),
   `host_runtime.completion_workflow_ref` (Greg's new ref), `host_runtime.native_threads: 8`,
   `host_runtime.science_byte_exceptions` (from `launch_pins`), `principal_admission` (artifact + outputs dir + sealed
   proof path; the historical NOT_PRESENTED/UNPROVEN literals only under a retained prompt), host-side paths (no `E:`),
   a NEW `run_directory`/`run_id`. `launch_pins.validate(config, boss_commit=<tip>)` must pass with zero problems.
4. Seal (`seal_final_prelaunch_candidate.py`), then `run_actual_sunday_compact_source.py --verify-source-only` on a
   scratch directory (no model), then the tailored pre-launch checklist in the handoff.
5. Dispatch is Greg's go: Actions -> "Frankie day pipeline (beginning to end; ...)" -> Run workflow on this branch;
   inputs day, go (the day's source manifest hash; empty = data plane only, HOLD before cycles), until, ingest_on
   (runner default), runner (label; default the first run's 4-vCPU runner). Even without go, stage 2 starts the EC2
   host (3.60/h) and the host job runs prefixes; `until: stage-sources` keeps it to S3 only.

## Still open after that (receiver side / Greg)

Receiver produces the sealed-absence proof file (`native_sealed_absence.prove_sealed_absent` has no producer);
receiver binds the BOSS Memory A witness into the knowledge receipt's proof layer; Pod credential via SSM parameter on
stdin (spec prerequisite 6); Pod idle cost (~1.19/h, ~28.60/day while RUNNING between days; the chain never stops the
Pod, only the ownership protocol does); token shrinks 3.1-3.4 (need a served-Granite check: HOLD); CPU items.

## Standing orders (Greg)

- The Granite smoke context is RETIRED; never reintroduce it. 114,054 is an entry count, not tokens.
- The first run's prefixes/reducer stack are the gold standard; change dates only, never rebuild.
- 8 native threads, fixed. Per-event, never average. Shrinking the packet is a top job.
- Memory A is VALID. No validation day exists or is required.
- No Frankie/Granite/Pod/EC2/result-bearing action, no workflow dispatch, without Greg's explicit go. Nothing local: git and S3.
- Keys do not rotate during the walk.
