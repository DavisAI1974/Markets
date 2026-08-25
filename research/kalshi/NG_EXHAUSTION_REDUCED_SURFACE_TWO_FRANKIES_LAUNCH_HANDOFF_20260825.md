# Reduced-Surface October 4-5 Two-Frankie Launch Handoff

Status: **LAUNCH IN THE NEW CHAT WHILE FULL-MBO STEP-1 CONTINUES HERE**  
Branch: `chatgpt/frankie-october-aws-readonly-20260824`  
Protected production pin: `a7611133f64064200de48cd2e7839fcea2510d51`

## First action and scope

Use all applicable agent skills before acting, including context engineering,
planning/task breakdown, git workflow/versioning, shipping/launch, and a final
static cross-audit. Use parallel agents for bounded implementation and audit work.

Launch the two Frankies now on the previously validated **reduced/non-full-MBO**
two-day surface. Do not wait for the concurrently running full-MBO Step-1 job.
Do not rerun Step-1, run tests, run a canary, or perform a broad architecture
rebuild. Do not describe this Frankie evidence as full MBO.

Read completely, in this order:

1. `research/kalshi/NG_EXHAUSTION_PRIOR_SURFACE_OCT45_TWO_FRANKIES_BUILD_CONTROL_20260825.md`
2. `research/kalshi/NG_EXHAUSTION_PRIOR_SURFACE_OCT45_SOURCE_20260825.json`
3. `research/kalshi/FRANKIE_PRIOR_SURFACE_OCT45_CAPABILITY_OVERLAY_20260825.json`
4. `research/kalshi/NG_EXHAUSTION_PRIOR_SURFACE_OCT45_TWO_FRANKIES_LAUNCH_20260825.json`
5. `research/kalshi/agents/frankie_prior_surface_oct45_realtime_20260825.md`
6. `research/kalshi/agents/frankie_prior_surface_oct45_forecaster_20260825.md`
7. `research/kalshi/ng_exhaustion_two_frankies_prior_surface_blind_2day_20260825.py`
8. `.github/workflows/ng_exhaustion_two_frankies_prior_surface_blind_2day_20260825.yml`

## Exact evidence surface

Governing label: `PRIOR_REDUCED_NON_FULL_MBO_SURFACE`  
May be described as full MBO: `false`

Source:

`/mnt/markets/ng_exhaustion_step1_5y_20260822/0d318335825b4a0e19a5a2881522f3da0374788e/full/segments/20211001_20211101.seconds.jsonl.gz`

- Bytes: `112852940`
- SHA-256: `93654eb5eaf24be6dc6821f422cdd7fc416e12778dcecd6c97150cbc34004f90`
- Child receipt file SHA-256: `80b6cf7199805cf40a0b16b139ee1aa8f705b884acf03856640df4054802f7ab`
- Child receipt canonical SHA-256: `4966dac8b25fee7acabf53f880a30155985bd5767ee222381f1188d4eecada3c`
- Target window: `[2021-10-04T00:00:00Z, 2021-10-06T00:00:00Z)`
- Included dates: October 4 and October 5, 2021 only

This is the earlier aggregated-seconds surface that did not contain the complete
raw full-MBO order lifecycle. Full order identity, full-depth FIFO, and any other
unretained historical capability must remain `UNAVAILABLE`, `UNKNOWN`, or
`DORMANT`, never false, zero, synthesized, or silently omitted.

## Mission and role sequence

Run exactly two logical `gpt-5.6-sol` role calls in this order:

1. `REAL_TIME_FRANKIE`
2. `FORECASTER_FRANKIE`

Common mission:

> Independently use the causally available prior-surface evidence to detect and
> predict event birth as early as possible; estimate onset/start and run duration;
> identify family, category, depth, severity, and uncertainty; create new
> structures when the evidence does not fit existing ones; and search for
> correlations, interactions, lags, clock relationships, sequence motifs, and
> mechanisms that Step-1 may not have found. Preserve exact ts_event/ts_recv as-of
> reasoning. Prior Step-1 structures may be similar or exact, but matching them is
> neither expected nor required.

Mandatory behavior:

- Both roles calculate runway: elapsed age, predicted remaining runway, total
  duration, end-time range, event/receive as-of clocks, confidence, censoring or
  unknown status, and evidence.
- Open-world outputs are required. New families, categories, mechanisms, depths,
  splits, merges, and nonordinal structures are allowed and receive deterministic
  identities. Old A/B/C or D0-D5 structures are not restrictive.
- Preserve exact clock values. Do not average materially dispersed or multimodal
  clocks. Tight clusters may be reported as observed ranges.
- Real-Time Frankie owns the first lock. Freeze and hash its state before the
  Forecaster call.
- Forecaster receives the immutable RT state plus lawful direct day-specific
  context. It cannot alter or reconstruct a competing RT state.
- Real-Time Frankie has one optional deterministic, read-only local evidence
  scout. It is never auto-called and makes no provider/helper subcall.
- Forecaster has no tools.
- No specialist-model calls, automatic helpers, repair calls, fallback model, or
  alternate provider.

## Blind wall

Do not expose Step-1 answers, result paths, receipts, counts, labels, families,
depth assignments, populations, crosswalks, answer-relative clocks, or the current
full-MBO Step-1 run. Raw source clocks already present in the reduced surface are
lawful. Step-1 answer clocks remain sealed.

Preserve the complete 1,940-leaf/46-block BigSuite registry and all 24 surfaces.
The 24 role profiles are inventory drafts, not proof of provider/runtime wiring.
Runtime receipts must mechanically reconcile every leaf, block, surface, and
installed executable tool with zero silent omissions.

## Bound package hashes

- Frankie workflow: `fef4f6ac2734001d95a7e35f7f13a8609cc431cfddd4f5f92eb4a2fe18924e7e`
- Wrapper: `e8b376d2adecab5979af31f7f684517132411b6eae24a0c157c903059a2ad79b`
- Source control: `7c819aee4f4068be9f13208e7a4dea3b97087e144f05d793d6473da0b2b4eca4`
- Capability overlay: `56b8242d41315f9618fa42553b04fac43a3dae256b4e9ad7029fb70f4bb22b81`
- Build control: `8858cd37bc6f624a0b7b92ac8e2d060eb9a0d7ac79e0d07ef3ac1d2e908825c7`
- Real-Time mission: `c1df14c78cac2e3cf62b05068182dbcb817d01544115eb96e7b6157396308a7a`
- Forecaster mission: `fc7827ac17a3207fa433e4087754d59dc532f7da871e2b7e8e7e473bcceb83c1`
- Launch marker while disabled: `90020f2be1294a9591261aaee5f0b200a52547d73ff37c0e4006e3f9e4b65d8b`
- Runtime lock: `d995333174aa129bc4b9a86a98f10d0c82c45c1fe4d1a40b29c0dbdff6a41de9`

Recompute and verify every hash from the remote branch before launch. Stop on any
drift; never silently substitute a file.

## Calls, tokens, and cost

- Logical role calls: exactly `2`
- Order: RT then Forecaster
- Specialist/provider helper calls: `0`
- RT optional local scout fee: `$0`
- Conservative combined input cap: `246000` tokens
- Conservative combined output cap: `24000` tokens
- Official bound rates as of 2026-08-25: input `$4.00/M`, cached input
  `$0.40/M`, output `$20.00/M`
- Conservative maximum provider cost: `$1.464`
- Hard approved ceiling encoded in the marker: `$1.50`
- Pricing source: `https://developers.openai.com/api/docs/models/gpt-5.6-sol`

Show Greg the exact final preflight once, immediately before launch: surface,
window, source identity, provider-visible data, sealed data, logical/physical call
limits, model, token caps, maximum cost, worker root, S3 prefix, and rollback. Then
obtain explicit launch approval and proceed without a test or canary.

## Feature-branch launch mechanics

The workflow exists only on the feature branch. GitHub will not provide a usable
manual `workflow_dispatch` button for a new workflow absent from the default
branch, and the connected GitHub tool does not expose workflow dispatch. Do not
send Greg through the mobile GitHub UI again. Do not add the workflow to the
default branch or touch protected production.

Use a guarded, approval-bound one-shot push trigger after Greg approves. Preserve
the current authorization guarantees:

1. Re-fetch the remote branch head and treat it as the immutable implementation
   commit.
2. Create an authorization commit that changes only
   `NG_EXHAUSTION_PRIOR_SURFACE_OCT45_TWO_FRANKIES_LAUNCH_20260825.json`: set
   `launch_authorized=true`, bind `authorized_by`, `authorized_at`, and
   `authorization.exact_commit` to the implementation commit.
3. Create a separate launch commit that changes only the run-specific Frankie
   workflow to add the exact feature-branch push trigger and a unique approved
   commit-message marker. Update the workflow's preflight to prove the three
   commits: implementation, marker-only authorization, and workflow-only launch.
   The marker's `exact_commit` must still equal the implementation commit.
4. The wrapper/package receipt must record distinct launch/source,
   authorization, and implementation commits. Do not weaken any hash, answer-wall,
   budget, model, role-order, or receipt gate.
5. After the target Frankie run is registered, restore the Frankie workflow to
   manual-only in a cleanup commit. The live run remains bound to its immutable
   launch commit.

If the three-commit proof cannot be made exact, stop and ask Greg. Do not bypass
the launch marker, edit production, or reuse an unrelated workflow.

## Required artifacts

The run must emit exactly these governed receipts, with `COMPLETE.json` published
last:

1. `PREFLIGHT.json`
2. `SOURCE_VERIFY.json`
3. `SLICE_MANIFEST.json`
4. `ANSWER_WALL.json`
5. `CAPABILITY_RECONCILIATION.json`
6. `RT_CONTEXT_MANIFEST.json`
7. `RT_PROVIDER_RECEIPT.json`
8. `RT_FIRST_LOCK.json`
9. `RT_FROZEN_STATE.json`
10. `ONEWAY_HANDOFF.json`
11. `FORECASTER_CONTEXT_MANIFEST.json`
12. `FORECASTER_PROVIDER_RECEIPT.json`
13. `FORECASTER_FIRST_LOCK.json`
14. `USAGE_COST.json`
15. `ARTIFACT_MANIFEST.json`
16. `COMPLETE.json`

## Concurrent full-MBO Step-1: do not disturb

This chat is monitoring the separate corrected full-MBO Step-1 run:

- Workflow run: `32819740234`
- Job: `97715170837`
- Immutable launch commit: `0cd89889c01cf07f9e84d477dc95b8af9ceec627`
- Status at handoff: `in_progress`
- Current step at handoff: `Launch exact corrected full-MBO computation`
- Raw roster: October 1, 3, 4, and 5, 2021
- Scored window: `[2021-10-04T00:00:00Z, 2021-10-06T00:00:00Z)`
- SSM plugin execution timeout: `18000` seconds
- Provider/Frankie calls: `0`

Do not cancel, rerun, modify, or wait for that job in the Frankie-launch chat. It
continues independently. This chat owns its monitoring and later verified-results
clock audit.

