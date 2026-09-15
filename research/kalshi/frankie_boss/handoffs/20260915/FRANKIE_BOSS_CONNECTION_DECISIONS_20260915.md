# Current status — September 15 handoff

This document retains historical evidence below. The current continuation authority is
[FRANKIE_BOSS_NEXT_CHAT_HANDOFF.md](FRANKIE_BOSS_NEXT_CHAT_HANDOFF.md) and
[HANDOFF_CODE_STATE.json](HANDOFF_CODE_STATE.json).

The accepted Granite startup was run 34928264918. Pod `jvs75m56w8f73q` was confirmed
stopped with `/opt/ml` retained; its last observed status was EXITED. No live compute,
Sunday principal run, or actual BOSS training remains in progress. Preserve the Pod
and verified model files. No new smoke or repeat of passing tests is authorized by
this handoff.

Runpod controller software is connected. Source mapping, supervised native learning
and durable training-state components are saved. Full-source mapping execution,
actual principal delivery/feedback and the durable cycle coordinator remain unfinished.
Do not infer complete system readiness from the component tests. The newer handoff
supersedes older "Pod running", "stop pending", or "no Pod remains" statements below.

---

# Full Frankie and BOSS connection

Status: implementation in progress. No combined Sun session has run.

## Build plan used

Frankie_BOSS_Combined_Build_Round2_20260915.xlsx, in the continuation task's
outputs/combined-build-round2 directory. SHA256:
9a22b8fb79c4920ca8a1d56b19a8adaba67b1d7b5e0ba0ea2d0a98f7bc1f9cac.
Workbook read only; original bytes unchanged.

The Current Snapshot sheet governs later software status; its original eight
sheets retain the design and historical evidence. Later user directions and the
successful Runpod launch supersede the old Sunday hold and hosted-startup failure.

## Decisions carried into the implementation

- Build Plans!D9:J9 and Experiment Arms!B13:J13 select B2_GATED with protected
  Memory A: native B1 reasoning plus required Granite critique. The original A-memory
  label describes the protected no-BOSS control; the combined candidate is B2-memory.
- Components!E24:J29 define native B1 reasoning and a frozen Granite critic.
  BOSS forecasts remain independent. Frankie still performs and files all his own
  market calculations under the preserved principal contract. Auxiliary teacher
  calculations do not replace those findings.
- Components!E7:J7 preserves the exact prior Memory A. Learned results from this
  run are saved separately for subsequent runs; neither BOSS nor Granite rewrites
  the frozen prior. User wants a learning feedback loop, with Frankie helping BOSS.
- Current Snapshot!B12:F15 still lists concrete fitted artifacts, training plan,
  scorer, splits and seeds as pending. The workbook does not supply numeric training
  settings or an implemented online Frankie-to-BOSS learning loop. Existing source
  specifications must supply these details; they must not be represented as already
  configured. A pretrained BOSS is not required to begin user-authorized training.
- Components!E31:J31 requires recorded state and exact restart continuity. A
  diagnostic progress file alone is not a model/optimizer checkpoint.
- Current Snapshot!E9:F10 confirms attributed_input delivery and the remaining
  authentic source/cutoff/population binding. Existing receiver/preparation code is
  reused; timestamps and matching counts cannot substitute for byte evidence.
- The complete current registry has 99 layers, 98 applicable to A_MEMORY, including
  22 static and 55 causal input layers. The user's approximate 100+ is not a new
  count gate. Full MBO, full book and FIFO identity must remain preserved. Future
  answers remain causally sealed and unavailable historical inputs remain explicit.

## Current operational evidence

Granite launch 34928264918 was accepted by the user. The watchdog confirmed Pod
jvs75m56w8f73q stopped with data retained; fresh API status EXITED and 50 GB mount
at /opt/ml confirmed. The 13 verified model files remain on retained storage.

New connection software has been committed and pushed on
codex/full-frankie-boss-connection-20260915 at
ce2411fbf13e9e7ea95a41a3c0a4af401233dc5c. Remote SHA and clean source worktree verified.

- 21 new Runpod transport tests passed.
- 36 new per-request local tokenizer admission tests passed using synthetic loaders.
- 8 new full-controller integration tests passed with real controller/journals and
  synthetic source plus fake HTTP. They verify both context routes, durable native
  and critic receipts, and restart reuse without repeated native work or POST.
- 8 new progress tests passed for stall/repost/recovery, preserved cursor and safe
  errors. Controller phase callbacks are connected. Other full-run owner call sites
  still need operational connection; do not claim all Frankie stages are instrumented.
- Independent review caught a diagnostic-ordering bug. Its one new regression
  failed before the fix and passed afterward: diagnostic failure now occurs before
  recording critic intent, so normal continuation does not invent an unknown call.

These are separate scoped batches. Passing old baselines were not rerun. No model
inference or principal session was sent; the native calculations inside new
integration tests used the explicitly synthetic test fixture.

## Actual Sunday source copy

GitHub Actions run 34931181246 succeeded:
https://github.com/DavisAI1974/Markets/actions/runs/34931181246.
It used the existing AWS GitHub secrets to copy the preserved Sunday source and
verified 973,355 bytes against SHA256
4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88.
The verified local copy is under work/sunday-source. Source framing shows DBN v3,
57,027 MBO records, all type160/56 bytes, publisher1/instrument111313. No rows were
filtered or market calculations repeated. See SUNDAY_SOURCE_COPY.json and
SUNDAY_SOURCE_FRAMING.json for receipts. This establishes source copy/framing,
not the complete causal BOSS-to-Frankie population mapping.

## Still required before calling this the full Sun run

The source/Frankie ledger crosswalk, authentic per-run metadata, actual principal
execution and read-back are not complete. The retained source copy can now be used
to finish these without substituting synthetic data.

The persisted online training/feedback loop is also not implemented by the new
transport or factory. The plan defines roles and staged objectives but explicitly
leaves concrete training settings pending. No trained model, optimizer checkpoint,
or learning progress has been claimed. Frozen Granite critique alone does not
update model weights. The user's training request supersedes a prerequisite for
already-fitted BOSS weights; it does not make an absent training callback executable.
