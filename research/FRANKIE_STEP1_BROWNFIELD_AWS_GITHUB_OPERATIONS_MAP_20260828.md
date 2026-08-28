# Frankie + Step-1 Brownfield AWS/GitHub Operations Map — 2026-08-28

## Purpose

This is the authoritative brownfield operations map for the Markets/Frankie NG exhaustion program’s Step-1 and Frankie launch paths as of 2026-08-28.

It exists because multiple days were lost to stale workflows, launcher mistakes, synchronous-control-plane timeouts, insufficient memory, missing progress visibility, non-resumable long stages, and repeated rediscovery of which files were actually authoritative.

This document is an operations/control-plane contract. It does **not** change the scientific definitions, event logic, MBO resolution, causal rules, retained cases/chains, Frankie brain, or model behavior.

## Agent Skills brownfield path is now the governing engineering posture

Agent Skills 0.6.7 from `addyosmani/agent-skills` is explicitly invoked for this program.

Brownfield means incremental and verification-first:

1. inspect current repo/runtime truth before modification;
2. preserve load-bearing behavior even when it looks awkward;
3. characterize/test before refactoring an existing scientific or launcher path;
4. make the smallest reversible change;
5. verify with evidence before the next change;
6. ratchet safeguards forward so solved failure classes do not return;
7. deprecate obsolete launch paths rather than casually reusing them.

The following skills remain directly applicable:

- `using-agent-skills`
- `context-engineering`
- `debugging-and-error-recovery`
- `incremental-implementation`
- `test-driven-development`
- `git-workflow-and-versioning`
- `observability-and-instrumentation`
- `deprecation-and-migration`

### Brownfield hard rule

No broad refactor of the scientific wrapper, Frankie runtime, or launch machinery merely to make the code cleaner. Characterization coverage comes first. Existing oddities are presumed potentially load-bearing until disproven.

---

# 1. Global launch architecture

## GitHub is the control plane, not the compute plane

Long Step-1 or Frankie compute must not live directly inside a GitHub-hosted runner and must not depend on a single synchronous SSM command remaining open for the duration of the computation.

The preferred architecture is:

1. GitHub checks out an exact source commit.
2. GitHub performs local syntax/tests/preflight.
3. GitHub authenticates to AWS.
4. GitHub verifies exact EC2/EBS/input identities.
5. GitHub stages an exact source/runtime package or exact worker script.
6. GitHub uses SSM only to start a **detached systemd unit** on EC2.
7. EC2 performs the long compute.
8. EC2 writes local progress/checkpoints and final artifacts.
9. EC2 publishes terminal status/results to S3.
10. GitHub monitors S3/receipt state and verifies hashes.
11. `COMPLETE` is declared only after terminal receipt and artifact identity verification.

## Proven AWS control-plane identity

Current Step-1/Frankie AWS resources:

- region: `us-east-2`
- EC2 instance: `i-08cee7171c0a76a04`
- preserved EBS volume: `vol-05a0b1e56f8c16478`
- S3 bucket: `bento-568968024170-us-east-2-an`

Do not silently substitute a different instance, volume, region, or bucket.

## Git launch discipline

Every one-shot launch should be bound to:

- exact branch;
- exact source commit;
- exact workflow path or explicit `workflow_dispatch` approval;
- exact approval token/launch-control object;
- exact input hashes;
- one atomic launcher commit when a commit-triggered one-shot is used.

Before any write, re-read the remote branch tip. Do not overwrite work from another chat/agent. Do not force-push.

---

# 2. Step-1 — scientific path and preserved identities

## Current corrected two-day full-MBO scientific wrapper

Authoritative science wrapper:

`research/ng_exhaustion_mbo_2day_full_mbo_step1_20260825.py`

This is the corrected two-day full-MBO Step-1 implementation. It preserves the scientific program and reuses the already reconstructed native-seconds stream while replaying the remaining full raw-MBO proposal/evidence stages.

Do not create reduced-MBO, summary, pilot, structural-only, capped-family, capped-proposal, or otherwise scientifically reduced variants merely to make the run easier.

## Preserved native-seconds identity

Path:

`/mnt/markets/ng_exhaustion_two_day_full_mbo_step1_20260825/32819740234-1/results/V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz`

SHA-256:

`899cca3c03d0cd66ba97bbd798b6d000bc3cb12c34d165a6def50b9c6f091b77`

Expected rows: `90,763`.

This is a high-value checkpoint and must not be rebuilt unless its identity check fails.

## Source run root

`/mnt/markets/ng_exhaustion_two_day_full_mbo_step1_20260825/33054308590-1`

Expected raw MBO files:

- `glbx-mdp3-20211001.mbo.dbn.zst`
- `glbx-mdp3-20211003.mbo.dbn.zst`
- `glbx-mdp3-20211004.mbo.dbn.zst`
- `glbx-mdp3-20211005.mbo.dbn.zst`

Baseline archive SHA-256:

`27cacc62681bc482e89eefcc3746f5d71958beab4e25816054e0c388a0346b33`

Candidate/base SHA used by the recovery venv:

`0d318335825b4a0e19a5a2881522f3da0374788e`

---

# 3. Step-1 — proven current worker/launcher path

## Standalone worker

Authoritative current recovery worker:

`research/ng_exhaustion_step1_oom_continue_worker_20260827.sh`

What it does correctly:

- runs the unchanged corrected full-MBO wrapper;
- uses the four verified raw-MBO files;
- reuses the hash-bound native-seconds stream;
- records `/usr/bin/time -v` resource data;
- writes run log/resource data into results at completion;
- generates a deterministic result-file manifest with SHA-256 values;
- creates `results.tar.gz`;
- uploads the result tar through a presigned S3 PUT;
- always attempts to write/upload `WORKER_STATUS.json` on exit;
- terminal status contains success/failure, exit code, tar SHA-256, and result-manifest SHA-256 when available.

This separation of worker logic from YAML is a successful brownfield correction. Keep it. Shell code that can be syntax-checked independently should not be re-embedded into giant YAML/Python f-strings.

## Proven host-resize workflow

Proven resize workflow:

`.github/workflows/ng_exhaustion_step1_v6_resize_r6i_2xlarge_simple_20260828.yml`

Successful resize commit:

`beee3f48906cdaae8f9c097b51b780f660005e6e`

Successful run:

`33139051598`

The workflow verified preservation of EBS volume `vol-05a0b1e56f8c16478` while resizing the same EC2 instance to `r6i.2xlarge`.

## Current V6 launcher

Current proven recovery launcher:

`.github/workflows/ng_exhaustion_step1_v6_64g_continue_20260828.yml`

Launch commit:

`e720d645156feaebc207a84df73c125bdceaa1df`

Active run at documentation time:

- run: `33139463724`
- job: `98746824307`
- systemd unit: `ng-exhaustion-step1-oom-v6-33139463724-1`
- continuation root: `/mnt/markets/ng_exhaustion_two_day_full_mbo_step1_20260825/oom_continue/33139463724-1`
- S3 result prefix: `nymex/ng_mbo_5y_v0/step1_census/two_day_full_mbo_corrected/continuations/33139463724-1`

The launcher correctly:

- requires `r6i.2xlarge`;
- requires the preserved EBS volume;
- validates worker shell syntax and wrapper Python syntax;
- validates native-seconds identity;
- validates required raw inputs;
- starts the worker detached with systemd;
- monitors the terminal S3 receipt;
- requires success status, exit code 0, result-tar hash, result-manifest hash, and result-object existence before `STEP1_V6_RECEIPT=PASS`.

### Important: current V6 is a recovery artifact, not the final future template unchanged

The active V6 run was launched with a 7-CPU cap (`taskset -c 0-6` and thread limits of 7). **Do not change the active process.**

Future Step-1 long-run launchers must carry the revised policy below.

---

# 4. Step-1 — standing AWS resource policy for future runs

## Host size

For Step-1 runs, retain:

- instance class: `r6i.2xlarge`
- physical memory: approximately 64 GiB
- host vCPUs: 8

Do not downsize Step-1 back to the prior 32-GiB configuration without a new measured justification.

## Compute CPU cap

Future Step-1 compute default:

- host: 8 vCPUs
- scientific compute: **6 CPUs maximum**
- leave 2 vCPUs uncommitted

The reason is primarily **memory pressure**, not because the OS/control plane requires two CPUs. The current 7-CPU V6 run demonstrated extreme RAM/swap pressure. Reducing concurrent worker/thread pressure is the conservative default.

All relevant runtime thread controls should agree with the 6-CPU cap, including where applicable:

- `taskset`
- `OMP_NUM_THREADS`
- `OMP_THREAD_LIMIT`
- `OPENBLAS_NUM_THREADS`
- `MKL_NUM_THREADS`
- `NUMEXPR_NUM_THREADS`
- `NUMEXPR_MAX_THREADS`
- `BLIS_NUM_THREADS`
- `LOKY_MAX_CPU_COUNT`

Do not set one to 6 and leave hidden thread pools at 7/8.

## Swap policy

The original 16-GiB swap file:

`/mnt/markets/.ng_step1_swap_20260827`

During V6 it became essentially 100% utilized. A guarded sidecar successfully added another 16 GiB:

`/mnt/markets/.ng_step1_swap_extra_20260828`

Future Step-1 long launches must preflight **approximately 32 GiB total active swap headroom** on this host unless a deliberately larger-memory host is approved.

Swap is an operational OOM guard, not a substitute for checkpointing or adequate RAM.

The extra-swap sidecar pattern was proven on temporary branch:

`chatgpt/frankie-october-aws-readonly-20260824-progress-probe-temp`

Workflow:

`.github/workflows/ng_exhaustion_step1_v6_add_swap_headroom_20260828.yml`

Commit:

`f6e808879e434cdd03d40e2e189a89247340775b`

Do not blindly rerun that exact emergency workflow for a future unit; instead incorporate its guarded preflight behavior into the future canonical Step-1 launcher.

---

# 5. Mandatory checkpoint/resume policy for all long compute

This is now a standing rule for Step-1, V4, Frankie support compute, and any other long-running compute.

**No long run may be launched without restart-safe checkpoints at intervals.**

The existence of `.partial` files or copied input artifacts does not count as a checkpoint unless restart from that state has been explicitly implemented and tested.

## Minimum checkpoint contract

Every checkpoint must bind at least:

- schema/version;
- exact source commit / wrapper hash;
- exact input file hashes and window identity;
- current deterministic stage;
- deterministic cursor/shard/file/row/event position needed to resume;
- completed output identities/manifests;
- any model/scorer/RNG state needed for exact continuation, if applicable;
- checkpoint creation timestamp;
- checkpoint hash/receipt;
- explicit `COMPLETE` marker written **last** after checkpoint contents are durable.

Checkpoint writes should use temp-file + atomic rename or equivalent fail-closed publication.

## Cadence

For a long loop, the launch contract must define a checkpoint cadence before compute starts.

Default lost-work target: **no more than about 15 minutes of compute** where practical. If the natural deterministic unit is a shard/file/stage boundary, checkpoint on that boundary provided the maximum replay cost is explicitly bounded and accepted before launch.

## Resume test gate

Before a new long-run path is considered production-ready:

1. run a bounded characterization case;
2. interrupt it after at least one checkpoint;
3. resume from the checkpoint;
4. verify final artifacts/hashes against an uninterrupted control run where deterministic equivalence is expected.

No “checkpoint support” claim without an actual interruption/resume test.

## Current Step-1 limitation

The current corrected wrapper is **not** fully restart-safe through every long stage. V6 preserves important upstream state, but a failure during the large evidence/self-fit phase can still cost substantial work.

Therefore **do not launch another comparable long Step-1 run after V6 until checkpoint/resume support is added around the long stages and characterized without altering scientific definitions.**

The preferred brownfield implementation is to wrap/extract deterministic stage boundaries and persist resumable state rather than rewrite the science wholesale.

---

# 6. Mandatory progress/observability policy

A progress probe is part of the run design from now on, not an optional debugging add-on.

## Proven read-only sidecar pattern

Temporary branch:

`chatgpt/frankie-october-aws-readonly-20260824-progress-probe-temp`

Workflow:

`.github/workflows/ng_exhaustion_step1_v6_progress_probe_20260828.yml`

Latest probe commit used to re-run it:

`ce8e7211a860539f80623962d9b963dda0940725`

Successful progress run:

`33153412972`

The probe is read-only against the scientific worker and reports:

- systemd active/substate/main PID;
- current memory;
- CPU use;
- RAM and swap totals/usage;
- current result filenames/sizes/mtimes;
- run-log metadata/tail;
- Python process RSS/peak/threads/I/O;
- currently open raw-MBO file descriptor and byte position when in raw replay;
- worker terminal-status JSON if present.

Future long-run launchers should provide equivalent observability directly or via a reusable read-only sidecar.

## Percentage reporting

Percentage is an estimate unless the stage has a deterministic count/byte denominator. Report:

- exact stage;
- exact denominator-based progress when available;
- overall estimated percentage separately;
- memory/swap risk separately.

Never pretend elapsed wall time alone is a percentage.

---

# 7. Current V6 live snapshot at documentation time

Read-only probe timestamp:

`2026-08-28T07:57:41Z`

At that snapshot:

- systemd unit: active/running;
- raw-MBO replay: complete;
- `UNCAPPED_MBO_PROPOSALS.jsonl.gz`: complete;
- family discovery: complete;
- event/evidence replay: complete;
- `V4_NATIVE_FULL_MBO_EVENT_EVIDENCE.jsonl.gz`: complete at ~3.0 GB compressed;
- events, causal cutoff bindings, lineage inputs: complete;
- MBO-to-old-baselines match graph: complete;
- sparse lineage: complete;
- current stage: writing `V4_NATIVE_FULL_MBO_SELF_FIT_GAINS.jsonl.gz.partial`;
- overall estimate: approximately 96%, +/- 1–2%;
- physical RAM used: approximately 64.3 GB;
- total swap: approximately 32 GiB;
- swap used: approximately 20.0 GB;
- swap free: approximately 14.4 GB.

This is a snapshot, not a terminal receipt. The run is not `COMPLETE` until the V6 terminal receipt is published and verified.

---

# 8. Step-1 workflow classification: use vs reference vs do-not-reuse

## USE / current proven path

- `research/ng_exhaustion_mbo_2day_full_mbo_step1_20260825.py` — current corrected science wrapper.
- `research/ng_exhaustion_step1_oom_continue_worker_20260827.sh` — current standalone worker/finalization pattern.
- `.github/workflows/ng_exhaustion_step1_v6_resize_r6i_2xlarge_simple_20260828.yml` — proven same-instance/same-EBS resize path.
- `.github/workflows/ng_exhaustion_step1_v6_64g_continue_20260828.yml` — proven current V6 recovery launch architecture; future launches must update CPU/checkpoint/swap policies rather than reuse unchanged.

## REFERENCE / diagnostics and history

- `.github/workflows/ng_exhaustion_two_day_full_mbo_step1_20260825.yml` — original corrected science-bearing launch reference; not the preferred long-run operational architecture.
- `.github/workflows/ng_exhaustion_full_mbo_checkpoint_inspect_20260827.yml` — historical inspection reference.
- `.github/workflows/ng_exhaustion_step1_timeout_inspect_20260827.yml` — failure-diagnosis reference.
- `.github/workflows/ng_exhaustion_step1_v4_resource_envelope_inspect_20260827.yml` and RAM candidate workflows — resource diagnosis only.
- temporary progress-probe and extra-swap workflows — proven sidecar patterns; bind to new unit/root before reuse.

## DO NOT USE AS THE NEXT STEP-1 LAUNCHER

The following families are historical recovery attempts and should not be selected merely because their names look close:

- `ng_exhaustion_step1_oom_continue_20260827.yml`
- `ng_exhaustion_step1_oom_continue_v2_20260827.yml`
- `ng_exhaustion_step1_oom_continue_v3_20260827.yml`
- `ng_exhaustion_step1_oom_continue_v4_20260827.yml`
- `ng_exhaustion_step1_oom_continue_v5_20260827.yml`
- `ng_exhaustion_step1_oom_continue_v5_retry_20260827.yml`
- obsolete resize candidates/diagnostic probes from the V3–V5 recovery chain.

Also ignore unrelated failures from:

`.github/workflows/ng_exhaustion_step1_receipt_count_20260823.yml`

That workflow is not the authority for the active V6 recovery.

---

# 9. Frankie — proven runtime/launch architecture and current experiment boundary

Frankie remains separate from Step-1. Completing Step-1 does not authorize launching either Frankie.

The user will provide the final launch directive from the separate Frankie experiment chat. Follow that directive when it arrives.

## Proven full-stack AWS runtime architecture reference

Workflow:

`.github/workflows/ng_exhaustion_frankie_fullstack_october_20260824.yml`

This is useful as an architectural reference because it implements important controls such as:

- exact source checkout;
- focused runtime tests;
- hash-locked/offline runtime packaging;
- artifact boundary before AWS credentials;
- exact package hashing;
- AWS S3 publication;
- isolated EC2/systemd execution;
- evidence gates.

It is **not** permission to relaunch the old full-October program or old scientific surface for the new two-day MBO experiment.

## Proven two-Frankie packet/coordination reference

Workflow:

`.github/workflows/ng_exhaustion_two_frankies_prior_surface_blind_2day_20260825.yml`

Supporting files named by that workflow include:

- `research/kalshi/ng_exhaustion_two_frankies_workmode_packet_2day_20260825.py`
- `research/kalshi/ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825.py`
- `research/kalshi/FRANKIE_PRIOR_SURFACE_OCT45_CAPABILITY_OVERLAY_20260825.json`
- `research/kalshi/agents/frankie_prior_surface_oct45_realtime_20260825.md`
- `research/kalshi/agents/frankie_prior_surface_oct45_forecaster_20260825.md`
- `research/kalshi/NG_EXHAUSTION_PRIOR_SURFACE_OCT45_TWO_FRANKIES_LAUNCH_20260825.json`

This is useful as a **launch-control/packet-sealing pattern only**.

### Critical warning

That workflow explicitly labels its evidence surface:

`PRIOR_REDUCED_NON_FULL_MBO_SURFACE`

Therefore it is **not the scientific input path for the upcoming full-MBO two-day experiment**. Do not accidentally reuse that reduced prior surface just because it is already a two-day/two-Frankie workflow.

The new experiment must bind to the completed corrected full-MBO Step-1 artifacts and the exact directive supplied by the user.

---

# 10. Upcoming two-run Frankie MBO experiment — sealed-blind contract

The planned experiment is:

1. Run the Frankies on the same two-day full-MBO data in the first condition.
2. Preserve/freeze the first-run predictions and runtime artifacts.
3. **Do not reveal the answers after the first run.**
4. Do not run reveal/score/postreveal workflows between the two prediction runs.
5. Run the same two days again on the same MBO data under the second condition, with BOSS driving Frankie as specified by the upcoming directive.
6. Keep answer-bearing/outcome/reveal artifacts sealed until the second run’s predictions are locked.
7. Only then compare condition 1 versus condition 2 and, when explicitly authorized, reveal/score against truth.

## Between-run contamination controls

After first-run prediction lock, do not expose to Frankie/BOSS before second-run prediction lock:

- answer labels;
- outcome truth;
- reveal packets;
- scorecards;
- post-event comparison artifacts;
- first-run correctness judgments;
- any generated lesson that encodes the answers.

First-run output itself may be preserved for later comparison, but it must not become an answer-bearing teaching signal for the second run unless the experiment directive explicitly says so.

## Old reveal workflows are forbidden between the two runs

Do not invoke old reveal/score paths such as:

- `.github/workflows/ng_frankie_blind_reveal_score_20260816.yml`
- `.github/workflows/ng_frankie_blind_postreveal_20260816.yml`
- other reveal/family-reveal workflows

until both MBO experiment prediction runs are complete and reveal is explicitly authorized.

---

# 11. Pre-launch checklist — every future Step-1 long run

A future Step-1 launch is blocked unless all are true:

- exact science wrapper and commit identified;
- characterization/regression tests pass;
- exact raw input identities verified;
- preserved upstream checkpoints verified;
- `r6i.2xlarge` / 64 GiB / 8-vCPU host verified;
- same expected EBS volume verified;
- compute CPU cap = 6;
- thread-pool caps = 6 consistently;
- approximately 32 GiB swap active and verified;
- sufficient EBS free space verified;
- restart-safe checkpoint implementation present for every long stage;
- checkpoint interruption/resume test passes;
- progress/health observability available before launch;
- detached systemd execution used;
- terminal status receipt path defined;
- result object/hash verification defined;
- no Frankie/model launch is bundled into Step-1 completion.

If any item fails, stop at the failed gate. Do not “try it and see” with an hours-long compute.

---

# 12. Pre-launch checklist — upcoming Frankie MBO experiment

Blocked unless all are true:

- user’s experiment directive has been pasted and read;
- corrected full-MBO Step-1 has a verified terminal success receipt;
- exact Step-1 artifact hashes are frozen;
- both Frankie conditions use the same intended two-day MBO evidence identity;
- first condition and BOSS condition are explicitly distinguished only by the experiment directive;
- first-run output destination is immutable/sealed;
- reveal/answer paths are disabled between runs;
- first-run prediction-lock receipt is defined;
- second-run prediction-lock receipt is defined;
- comparison does not run until both prediction locks exist;
- no old reduced/non-full-MBO packet is substituted.

---

# 13. Failure-response rule

For any future failure:

1. preserve the failed root/artifacts/logs first;
2. classify whether failure is scientific assertion, input identity, AWS control plane, systemd/process, disk, RAM/OOM, swap, timeout, packaging/upload, or receipt verification;
3. collect read-only evidence;
4. change one failure class at a time;
5. do not change scientific definitions to fix infrastructure;
6. resume from the last verified restart-safe checkpoint;
7. never restart from raw merely because it is simpler for the operator.

The OOM recovery chain from Aug. 27–28 is the example of why this matters.

---

# 14. Deprecation policy

The repo contains many historically useful one-shot workflows. Their existence is not evidence that they remain valid launchers.

Going forward, every handoff/operations map must classify relevant launch files as:

- `CANONICAL/USE`
- `REFERENCE/DIAGNOSTIC`
- `DEPRECATED/DO NOT LAUNCH`

A new launcher superseding an old one must update this map or its successor in the same change series.

Do not delete historical workflows merely to reduce clutter until their forensic value has been considered. Brownfield deprecation first; removal later.

---

# 15. Current branch and authoritative reading order

Repository:

`DavisAI1974/Markets`

Authoritative working branch:

`chatgpt/frankie-october-aws-readonly-20260824`

Branch tip immediately before this documentation change:

`e720d645156feaebc207a84df73c125bdceaa1df`

Read in this order for continuation:

1. `research/FRANKIE_STEP1_BROWNFIELD_AWS_GITHUB_OPERATIONS_MAP_20260828.md` — this document.
2. `research/FRANKIE_FULL_MBO_STEP1_OOM_RECOVERY_HANDOFF_20260827.md` — detailed failure/recovery lineage and preserved identities.
3. `research/ng_exhaustion_mbo_2day_full_mbo_step1_20260825.py` — current corrected Step-1 science wrapper.
4. `research/ng_exhaustion_step1_oom_continue_worker_20260827.sh` — current worker/finalization mechanism.
5. `.github/workflows/ng_exhaustion_step1_v6_64g_continue_20260828.yml` — active V6 recovery launcher; inspect, do not re-trigger.
6. user-supplied Frankie experiment directive when provided — it governs the next Frankie launch.

---

# 16. Standing hard boundaries

- Do not launch Frankie until the user supplies the experiment directive.
- Do not reveal answers after the first Frankie MBO experiment run.
- Do not score/reveal between the two Frankie experiment runs.
- Do not silently substitute reduced/non-full-MBO data for full MBO.
- Do not change Step-1 science to make compute fit infrastructure.
- Do not drop events/chains/cases because findings are inconvenient.
- Do not treat non-confirming empirical evidence as a failed/dropped chain.
- Do not run future long compute without restart-safe interval checkpoints.
- Do not run future Step-1 on less than the standing 64-GiB/8-vCPU host configuration without explicit reconsideration.
- Default Step-1 scientific compute cap is 6 CPUs.
- Maintain approximately 32 GiB active swap safety margin on this host for long Step-1 runs.
- Keep a progress/health probe available from launch.
- Verify exact receipt/artifact hashes before declaring completion.
- `COMPLETE` is always the last publication step.
