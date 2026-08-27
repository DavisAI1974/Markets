# Frankie Full-MBO Step-1 OOM Recovery Handoff — 2026-08-27

## Scope

Continue only the corrected two-day full-MBO Step-1 program on branch `chatgpt/frankie-october-aws-readonly-20260824`.

Do not rebuild the science, do not broaden scope, do not launch either Frankie, and do not launch any model. Keep all Step-1 findings sealed from both Frankies until the existing reveal boundary says otherwise.

Use the Agent Skills 0.6.7 workflow discipline already invoked in the prior chat, especially:

- `using-agent-skills`
- `debugging-and-error-recovery`
- `incremental-implementation`
- `test-driven-development`
- `git-workflow-and-versioning`

The relevant rule is preserve evidence -> diagnose -> smallest root-cause fix -> verify -> resume.

## Original corrected run

GitHub Actions run: `33054308590`
Job: `98457160703`
Workflow: `.github/workflows/ng_exhaustion_two_day_full_mbo_step1_20260825.yml`
Launch SHA: `10b29a30b23a95d92ea4bdf43331d4e9704275ab`

Key prior commits:

- wrapper fix: `9e68263d…`
- regression test: `5694d534b3ec3304fadeb946a0eb76d5199f4ee1`
- launch: `10b29a30b23a95d92ea4bdf43331d4e9704275ab`
- manual-only restoration: `9ceddb2dfa462d50afa38a721027926ae5eb9ce1`
- monitoring handoff: `a5a955974db45094e8d1e53e068e582f7ff84111`

The original corrected run failed in `Launch exact corrected full-MBO computation`; final receipt verification/publication was skipped.

## Exact failure diagnosis

The failure was not a scientific assertion, data identity error, Python exception, or GitHub timeout.

Read-only post-mortem run: `33075400385`
Inspection commit: `55b8c38a4bfdfae7b3dec9ce0fe75e514097b6d8`

Observed on EC2:

- `/usr/bin/time` reported `Command terminated by signal 9`.
- Wall time before death: `4:31:08`.
- CPU: approximately 99%.
- Maximum resident set size: `15108904 kbytes` (~15.1 GB).
- Swap: `0` during the failed run.
- Kernel journal at 2026-08-27 13:01:34 UTC recorded an OOM kill of the Step-1 Python process.
- Kernel line: `Out of memory: Killed process ... (python) ... anon-rss:15105320kB`.

Therefore the root cause is confirmed kernel OOM.

## Preserved state verified after OOM

Source run root remains present:

`/mnt/markets/ng_exhaustion_two_day_full_mbo_step1_20260825/33054308590-1`

Preserved native seconds remain present and hash-valid:

`/mnt/markets/ng_exhaustion_two_day_full_mbo_step1_20260825/32819740234-1/results/V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz`

SHA-256:

`899cca3c03d0cd66ba97bbd798b6d000bc3cb12c34d165a6def50b9c6f091b77`

Expected rows: `90,763`.

All four raw MBO files remain on the EC2 volume and passed manifest size/hash verification:

- `glbx-mdp3-20211001.mbo.dbn.zst` — 25,628,861 bytes
- `glbx-mdp3-20211003.mbo.dbn.zst` — 973,355 bytes
- `glbx-mdp3-20211004.mbo.dbn.zst` — 34,300,424 bytes
- `glbx-mdp3-20211005.mbo.dbn.zst` — 36,192,430 bytes

The baseline/legacy artifacts also remain present. The failed run's `results/` contained the copied legacy artifacts and the preserved native-seconds output, but the new full-MBO proposal/evidence/event outputs had not yet been emitted when the process was killed.

## Science remains unchanged

The corrected wrapper is still:

`research/ng_exhaustion_mbo_2day_full_mbo_step1_20260825.py`

The two focused regression tests from commit `5694d534…` cover:

1. causal MBO groups spanning receive-second boundaries;
2. preserved native-seconds hash/window identity.

Do not alter event definitions, causal clocks, MBO fields, proposal thresholds, event/family retention, outcome construction, model/scorer definitions, or Frankie inputs merely to reduce runtime/memory.

The existing program reuses the preserved native seconds, then performs the remaining raw-MBO proposal surface replay and the later event-specific causal feature/evidence replay.

## Recovery work already committed

### Timeout/OOM inspection

Commit: `55b8c38a4bfdfae7b3dec9ce0fe75e514097b6d8`

Added a one-shot read-only inspection workflow and established the kernel OOM diagnosis.

### OOM continuation V1

Commit: `394ff681321579c8335174c920489d1336121653`
Run: `33075760613`

This did not reach EC2 mutation or science execution. It failed locally while generating the remote shell because a Bash `finish() {` block was embedded in a Python f-string and caused:

`SyntaxError: f-string: expecting '!', or ':', or '}'`

### Standalone worker

Commit: `abd9f5539df22a57d39929339f1762e7ce1269b5`

Added:

`research/ng_exhaustion_step1_oom_continue_worker_20260827.sh`

Purpose: keep the worker logic separate from the GitHub YAML so shell syntax can be checked independently and the recovery remains atomic/reviewable.

### OOM continuation V2

Commit: `33aaa75c36283f37d735ef062a88a6f8bc727faa`
Run: `33077416669`

GitHub rejected the workflow before creating any jobs because an embedded multiline block escaped YAML indentation. No EC2 continuation was launched by V2.

### OOM continuation V3

Commit: `011725b9b67825fbfbc163e0f2c32f6e11b82806`
Run: `33077574846`
Job: `98535722890`

V3 passed:

- checkout;
- AWS authentication;
- `bash -n` on the standalone worker;
- `python -m py_compile` on the scientific wrapper;
- preserved native-seconds hash check;
- all four raw-MBO manifest size/hash checks.

V3 successfully created and activated a 16-GB swap file:

`/mnt/markets/.ng_step1_swap_20260827`

Observed immediately after activation:

- physical RAM: ~16.55 GB
- available RAM: ~15.68 GB at launch time
- active swap: ~16 GB
- swap used at that moment: 0

This is an operational resource change only. It does not alter the scientific program or inputs.

V3 then invoked:

`systemd-run --unit=ng-exhaustion-step1-oom-v3-33077574846-1 --collect --property=Type=exec /bin/bash <continuation worker>`

The service was created (`Running as unit: ng-exhaustion-step1-oom-v3-33077574846-1.service`) but was no longer active when the launcher checked it three seconds later, causing the SSM wrapper to return response code 3.

The GitHub workflow stopped there. The service journal and continuation worker status have NOT yet been retrieved. That is the exact current blocker.

## Exact next action

Do NOT immediately relaunch another worker.

First perform a read-only inspection of exactly this service and continuation root:

Systemd unit:

`ng-exhaustion-step1-oom-v3-33077574846-1.service`

Continuation root:

`/mnt/markets/ng_exhaustion_two_day_full_mbo_step1_20260825/oom_continue/33077574846-1`

Retrieve, without modifying anything:

1. `systemctl status ng-exhaustion-step1-oom-v3-33077574846-1.service --no-pager -l`
2. `journalctl -u ng-exhaustion-step1-oom-v3-33077574846-1.service -n 200 --no-pager -l`
3. file listing beneath the continuation root;
4. `WORKER_STATUS.json` if present;
5. `run.log` if present;
6. `resource.txt` if present;
7. current `free -b` and `swapon --show` to confirm the 16-GB swap remains active.

Only after the exact early service failure is known should anything be changed.

Likely classes to distinguish include missing exported environment in the transient service, path/permission issues, or an immediate wrapper/input contract failure. Do not guess which one it is.

## Runtime expectation once the worker is genuinely running

The failed scientific worker consumed 4h31m of nearly continuous CPU before reaching ~15.1 GB RSS and being OOM-killed. Because the preserved native seconds avoid rebuilding that stage but the remaining corrected program still does the raw-MBO surface replay and later event-specific evidence replay, budget several hours for a successful run.

Do not promise a precise duration until the new worker has been confirmed active and resource growth can be observed. The prior run demonstrates that more than 4.5 hours is possible.

## Hard boundaries

- Do not launch either Frankie.
- Do not launch any model/provider LLM.
- Keep Step-1 findings sealed from both Frankies.
- Do not rebuild the 90,763-row native-seconds stream.
- Do not redownload/reconstruct data already verified on disk unless an identity check fails.
- Do not change scientific definitions to make the job faster or smaller.
- Do not cap proposal count or family count.
- Do not drop chains/events because a result is inconvenient.
- Do not treat a non-confirming empirical result as a failed chain.
- Diagnose exact infrastructure/runtime failures before changing anything.
- Verify receipt and artifact identities before publishing `COMPLETE`.
- Publish `COMPLETE` last.

## Agent Skills continuation note

Agent Skills release `0.6.7` from `addyosmani/agent-skills` was consulted directly through GitHub. The following relevant skills have been read and should continue to govern this recovery:

- `using-agent-skills`
- `debugging-and-error-recovery`
- `incremental-implementation`
- `test-driven-development`
- `git-workflow-and-versioning`

The rest of the 0.6.7 skill pack can be loaded after the Step-1 worker is genuinely running; do not let skill-pack setup distract from the immediate recovery.
