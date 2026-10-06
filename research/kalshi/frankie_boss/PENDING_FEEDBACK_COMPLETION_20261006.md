# Pending target feedback completion — source connection

Built from branch checkpoint `3fa9f5927a51cddb5f9789f69523ff0e25cd04a7` on 2026-10-06.
SOURCE-BUILT / RUNTIME-UNVERIFIED. No training, data/scientific execution, test suite or E2E was run.
This reconnects an existing native forecast to its later outcomes. It does not activate native training in the
code-only 30-day experiment or settle the remaining BOSS objective/model-lineage decisions.

## Connected path

1. The existing host recorder opens the original source contract, schedule, request plan, concrete principal
   adapter and retained coordinator. It verifies the original pending response and its classroom completion.
2. A separate immutable outcome request binds the original request, controller result, export, input/source,
   full target/session roster, principal response and pending evidence. Only the later learning cutoff advances.
   The original feedback contract remains unchanged inside the request.
3. The authorized host supplies actual observed feedback and an independently hashed session attestation/record.
   `PendingTargetFeedbackAdapter` reuses the existing host-attestation checks and the learner's exact pure label
   checks, including evidence hashes, causal availability, ordered session roster and STOP-after-close rule.
   A later session may have its own session ID, but must retain the original independently attested host authority.
4. `SundayExecution.complete_pending_cycle` checks the retained plan/source/classroom identities and original
   learning objective, then calls `CycleCoordinator.complete_pending`. The dedicated host runtime restores the
   existing model database and witnesses. No new checkpoint is created when state is absent.
5. The coordinator authenticates the outcome, retains separate continuation/output stages and uses the original
   `BossTrainingCheckpoint.apply_completed -> NativeForecastLearner.step` callback. The first update requires the
   exact original pending model predecessor. Retry after a committed update reuses the existing receipt.
6. The original classroom lessons and later outcome lessons both reach the normal lessons/completion path.
   Completed knowledge uses the separately bound later cutoff, with continuation provenance in its hashes.

Normal `run_cycle` still returns a pending cycle. Completion is an explicit separate action: a usual resume must
not accidentally train because a new file appeared. No controller/critic factory or new classroom session is called
by completion. The existing native learner still performs its normal context/teacher preparation inside its update;
this patch does not establish reuse of a retained native preparation cache.

## Host operations, not executed here

Use the actual retained configuration, original cycle index and lawful outcome cutoff. The configuration and all
supplied files require their real independent hashes. These examples are interfaces, not executable authorization.

Prepare the outcome request without constructing native model state:

```sh
python -m research.kalshi.frankie_boss.operations.record_actual_frankie_response \
  --configuration CONFIG --configuration-sha256 CONFIG_SHA \
  --cycle-index INDEX --turn outcome --learning-cutoff-ns CUTOFF_NS --prepare-outcome
```

The result names the exact `request.c15.json` and continuation hash. The host must obtain real evidence and a
response to that request; this helper does not generate labels, invoke an agent or manufacture an attestation.

Record that independently attested response:

```sh
python -m research.kalshi.frankie_boss.operations.record_actual_frankie_response \
  --configuration CONFIG --configuration-sha256 CONFIG_SHA \
  --cycle-index INDEX --turn outcome --learning-cutoff-ns CUTOFF_NS \
  --response RESPONSE --response-sha256 RESPONSE_SHA \
  --host-attestation ATTESTATION --host-attestation-sha256 ATTESTATION_SHA
```

Only after explicit compute authorization, the existing retained EC2 host wrapper can complete one pending cycle:

```sh
python -m research.kalshi.frankie_boss.operations.run_actual_sunday_ec2 \
  --configuration CONFIG --ec2-resume \
  --complete-pending-cycle INDEX --learning-cutoff-ns CUTOFF_NS
```

Preserve any already-declared compact-source-tools option and host numeric policy. Completion requires a retained
outcome response before loading native state, and reports only `pending_cycle_completed`, never an all-days result.
It refuses combination with ordinary cycle-range, prepare-only or pending-return execution scopes.

## Recovery and limitations

- Original binding, pending envelope, forecast, source and initial classroom records are not rewritten.
- Missing or invalid outcome evidence leaves the cycle pending. No replacement labels or weights are synthesized.
- A callback that produces no eligible loss under the original objective refuses before checkpoint insertion.
  The existing checkpoint recovery rule requires close/restore after callback failure. An already attested response
  remains immutable; replacement needs explicit recovery/revision, not silent overwriting.
- Adding this source changes the existing code identity. Old-code pending runs need an explicit reviewed migration
  or supersession before this revision can execute against their state. No old identity guard was bypassed.
- The experiment's native objective plus BOSS auxiliary TeacherHead combination/weight is still unselected.
  The existing timing objective is preserved; the old five-arm harness's 0.1 default was not imported.
- The single-source advancing cursor is unchanged. It is not a global three-lane optimizer sequence. Model ownership,
  update order and stale-input recovery still require the native integration decision.
- Actual matching later target outcomes and current compatible retained model state are still required. This
  connection does not prove trained weights, neural live recognition or completed 99-layer model consumption.

## Retained evidence investigation

The historical restoration inventory names:

- `s3://bento-568968024170-us-east-2-an/frankie/sunday_20260915_restore/UPLOAD_MANIFEST.json`
- `s3://bento-568968024170-us-east-2-an/frankie/sunday_20260915_restore/FB/actual-feedback-run/training.sqlite`
- Database size 107,556,864 bytes; SHA256 `696cee058d911dae6733496f91b2a8a83a1cdd89fb3158238ea0287222df5e6e`.

The committed witness for that database is sequence zero, not evidence of a trained successor. After AWS was
reconnected, read-only STS, S3 GetObject (manifest) and HeadObject (database) calls succeeded. The live object
ContentLength and stored metadata SHA256 match the manifest above; LastModified is 2026-09-16T06:18:59Z.
This is metadata agreement, not a fresh content hash or database inspection. Both owning EC2 instances were
confirmed stopped by DescribeInstances. No host-local disk was inspected and no instance was started.
A broad S3 listing returned 1,000 items; it does not establish an exhaustive checkpoint search. Do not infer
absence of later state from this historical inventory or partial listing.

Historical Sunday feedback does exist: the committed September 15 `cycles.sqlite` and actual response carry 29 timing
labels for `frankie-boss-own-source-sunday-20260915-cycle-00`, session `NG_111313_OWN_SOURCE_20211003`, but no retained
training/completion stage in that database. The independent host record hash is
`e9f6d65683d5d3cd0b3274209c601a746cca3cae14690b8f3a95bf2f81b0ce59`.
These labels cannot substitute for the Monday forecast's `NG_111313_CME_20211005` target outcomes.

## Checks

Source/interface review, independent agent review, in-memory Python syntax compilation, YAML parsing, shell syntax
and whitespace checks only. No extra tests, model calls, scientific runs, AWS start/dispatch or dependency install.
AWS reconnection was verified by successful read-only calls. Memory MCP remains blocked as documented in the main handoff.
