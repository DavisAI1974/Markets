# Two-Day Step-1 Transfer-Only Recovery Handoff

Date: 2026-08-24  
Branch: `chatgpt/frankie-october-aws-readonly-20260824`  
Protected production branch: `chatgpt/ng-exhaustion-october-sharded-20260824` at `a7611133f64064200de48cd2e7839fcea2510d51` — untouched

## Required first reads

Read and obey these files completely before acting:

1. `research/kalshi/NG_EXHAUSTION_FRANKIE_MONTHLY_RUN_PROCEDURE.md`
2. `research/kalshi/NG_EXHAUSTION_TWO_FRANKIES_FULL_SUITE_HANDOFF_20260824.md`
3. This handoff.

Use the repository's applicable agent skills before changing or dispatching anything. In particular, use context engineering, planning/task breakdown, git workflow/versioning, CI/CD and automation, test-driven development, debugging/error recovery, doubt-driven development, and documentation/ADRs as applicable. Start with a written build/recovery plan and obtain Greg's approval before a new dispatch.

## Binding user intent

- This is collaborative and revealed work. Nobody is trying to trick or hinder either Frankie.
- Never withhold anything a Frankie would lawfully know at that causal time.
- Real-Time Frankie is central causal operating intelligence, not merely an exhaustion detector.
- Forecaster Frankie consumes an immutable Real-Time Frankie state and adds horizon forecasts.
- Preserve one mechanically complete uniform superset build. A capability may be `DIRECT`, `TOOL_ACCESSIBLE`, or `DORMANT`; it is never silently removed.
- Preserve the original 1,940+ BigSuite leaf registry. Role profiles are overlays, not substitute hand-curated inventories.
- Complete Step-1 method knowledge belongs directly inside both Frankie builds. Step-1 result evidence is a separate surface.
- No automatic forecaster specialists. Expose day-specific information directly to Forecaster Frankie.
- Preserve the old specialists as installed/tool-accessible only if retained; do not auto-call them.
- Preserve at most one optional Real-Time evidence scout, callable only when Real-Time Frankie requests it; no automatic helper call.
- History means unlimited lawful recall reach with bounded response size, using sequence/timestamp indexes, authenticated checkpoints, reverse windows, pagination, and immutable evidence pointers.
- Nova token optimization is deferred until after this test.
- Do not call either Frankie/provider yet. Greg wants the two-day Step-1 results inspected first.

## Exact two-day scope

The authorized half-open window is:

```text
[2021-10-04T00:00:00Z, 2021-10-06T00:00:00Z)
```

The user authorized one diagnostic exception: self-fit/self-score on these two days is accepted as if validated. Otherwise the science and outputs must match the 54-week Step-1 method exactly:

- D0 through D5, including D0;
- A/B/C families;
- endpoints and resets;
- lineage and ancestry;
- gains;
- full, sparse, and aggregate outputs;
- legacy-control and V4-native populations;
- dual-census crosswalk and immutable receipt/evidence pointers.

Do not compare these answers to the 54-week structures. The two-day structures are expected to be somewhat different.

## Validated October child reused

- AWS region: `us-east-2`
- Worker instance: `i-08cee7171c0a76a04`
- Bucket: `bento-568968024170-us-east-2-an`
- Frozen candidate: `0d318335825b4a0e19a5a2881522f3da0374788e`
- Worker base: `/mnt/markets/ng_exhaustion_step1_5y_20260822/0d318335825b4a0e19a5a2881522f3da0374788e`
- October segment: `20211001_20211101`
- Validated seconds bytes: `112852940`
- Validated seconds SHA-256: `93654eb5eaf24be6dc6821f422cdd7fc416e12778dcecd6c97150cbc34004f90`
- Validated receipt-file SHA-256: `80b6cf7199805cf40a0b16b139ee1aa8f705b884acf03856640df4054802f7ab`
- Canonical child receipt SHA-256: `4966dac8b25fee7acabf53f880a30155985bd5767ee222381f1188d4eecada3c`
- Adapter SHA-256: `5a18fe96bc5022a619536640a630209df1c85ec7b756f139ee412ef9a8d288db`

Raw October MBO was not replayed.

## Step-1 computation is complete — do not rerun it

GitHub Actions evidence:

- Workflow run: `32782745590`
- Job: `97608112834`
- Launch commit: `870cb379e5aa92a7ddd028a0989152df01dc1843`
- SSM command: `3647c63a-c632-492b-b777-927e727b7e98`
- Worker status: `Success`
- Worker response code: `0`
- `TWO_DAY_STEP1_RECEIPT=PASS`

The real Step-1 computation completed and produced the following receipt-backed results:

```text
TWO_DAY_STEP1_RECEIPT_SHA256=140c6234b8e6f4216416290aa50f4070160e200a3e7025cbca3aa08d0ef42e52
TWO_DAY_EVENT_COUNTS={"legacy": 1577, "native": 1603}
TWO_DAY_FAMILY_COUNTS={"legacy": {"A": 1510, "B": 23, "C": 44}, "native": {"A": 1532, "B": 23, "C": 48}}
TWO_DAY_LEGACY_DEPTHS={"0": 612, "1": 852, "2": 97, "3": 16, "4": 0, "5": 0}
TWO_DAY_NATIVE_DEPTHS={"0": 591, "1": 902, "2": 106, "3": 3, "4": 1, "5": 0}
TWO_DAY_RESULTS_TAR_SHA256=27cacc62681bc482e89eefcc3746f5d71958beab4e25816054e0c388a0346b33
```

The intact result archive remains on the worker:

```text
/mnt/markets/ng_exhaustion_two_day_step1_20260824/32782745590-1/results.tar.gz
```

The complete worker run root is:

```text
/mnt/markets/ng_exhaustion_two_day_step1_20260824/32782745590-1
```

Do not send the compute command again. Do not create a new run root. Do not rerun the adapter. Recovery is transfer-only.

## Why the workflow is red

The science succeeded. The post-compute signed-upload preflight failed after the result tar was created.

Exact observed failure:

```text
aws: [ERROR]: An error occurred (404) when calling the HeadObject operation: Not Found
<Error><Code>TemporaryRedirect</Code>
<Message>Please re-send this request to the specified temporary endpoint. Continue to use the original request endpoint for future requests.</Message>
<Endpoint>bento-568968024170-us-east-2-an.s3.us-east-2.amazonaws.com</Endpoint>
```

Consequences:

- GitHub run `32782745590` concluded `failure` only because transfer/promotion did not complete.
- The Step-1 SSM command itself succeeded.
- `Retrieve and verify the complete result receipt` was skipped.
- No final `COMPLETE.json` marker was published.
- No Frankie/provider call occurred.

## Exact next action: transfer-only recovery

Before dispatching, show Greg the exact transfer-only command/prompt, data exposure, logical-call count, and cost. Obtain approval.

Then:

1. Read-only verify that the worker archive still exists and matches SHA-256 `27cacc62681bc482e89eefcc3746f5d71958beab4e25816054e0c388a0346b33`.
2. Do not recompute if the file exists and matches.
3. Correct the S3 endpoint behavior for the transfer. Use the bucket's explicit `us-east-2` regional endpoint and SigV4/virtual-host addressing for any new presigned PUT, or use another already-authorized transfer path after proving it with a tiny probe.
4. Mint the upload authority only after the archive verification. Keep it short-lived but long enough for SSM dispatch.
5. Send one transfer-only SSM command that uploads the existing archive.
6. Download the archive with the GitHub AWS identity.
7. Verify the tar SHA, Step-1 receipt self-hash, and every receipt-listed artifact's path, byte length, and SHA-256.
8. Require the expected complete output set, including D0–D5, A/B/C, legacy/native populations, full/sparse/aggregate products, crosswalk, source manifest, validation-exception receipt, run log, and resource usage.
9. Publish verified artifacts to the final diagnostic prefix.
10. Publish `COMPLETE.json` last and verify it exists.
11. Report exact run/job/SSM IDs, object count/bytes, final prefix, receipt SHA, tar SHA, event/family counts, and depth histograms.

If the existing worker archive is missing or its hash differs, stop and ask Greg. Do not silently recompute.

## Workflow history and setup failures

Four earlier launches failed before science began:

1. Run `32780100751`, job `97600056041`: worker frozen repo was not a Git repository.
2. Run `32780486848`, job `97601241972`: worker could not read the new diagnostic S3 prefix (`403`).
3. Run `32781542555`, job `97604483321`: long-lived signed URL preflight failed (`403`); SSM was not sent.
4. Run `32781911244`, job `97605618340`: existing launch-prefix staging still failed worker `HeadObject` with `403`; science did not begin.

Run `32782745590` is different: it is the first successful two-day science computation. Preserve it and recover its existing output.

## Focused verification already completed

Local and Actions gates passed before compute:

- Workflow YAML and embedded Bash syntax: pass.
- Literal revision-5 launch contract: pass.
- Compute-before-transfer ordering: pass.
- Verify-before-promote and `COMPLETE.json`-last ordering: pass.
- Secret-value scan: pass.
- Inline adapter size gate: pass.
- Independent launch review: pass after increasing the signed PUT lifetime from 300 to 900 seconds.
- Focused adapter tests: 4/4 pass.
- Frozen detector/feature/lineage/crosswalk parity test: pass.
- Exact half-open-window filter and child validation test: pass.
- Tamper fail-closed test: pass.
- Scored D0–D5 output test: pass.

Do not run broad tests or broad build inspections as part of transfer recovery.

## Current role/context files committed with this handoff

The workspace also contains role-specific context and Step-1-method work. Preserve it, but do not misstate its maturity:

- `research/kalshi/FRANKIE_ROLE_CONTEXT_PROFILES_20260824.json`
- `research/kalshi/frankie_role_context_profiles_20260824.py`
- `research/kalshi/tests/test_frankie_role_context_profiles_20260824.py`
- `research/kalshi/FRANKIE_STEP1_STRUCTURAL_CENSUS_METHOD_V1_20260824.md`
- authority-plane and source-inventory additions that expose the complete Step-1 method separately from results.

These are drafts and are not proof of final runtime wiring. The role-context builder now emits a content-addressed capability-reconciliation receipt that mechanically enumerates the current authoritative BigSuite survey (`1940` leaves across `46` blocks) and every installed non-test Python executable, with zero unregistered or silently omitted items. This closes the draft's immediate inventory gap, but does not itself prove provider/runtime integration. In particular:

- the human-readable activation profile still uses 24 umbrella surfaces; the additive capability-reconciliation receipt carries the one-to-one 1,940-leaf and executable inventory;
- both draft profiles currently have zero `DORMANT` umbrella surfaces;
- role overlays must ultimately classify every authoritative leaf without deleting any leaf;
- runway/dipole/structure capability must be mechanically traceable to the complete registry, not inferred from a hand-curated umbrella list;
- the context builder is not yet proven to be the active provider/runtime path;
- the old four helpers and forecaster specialists are not to be auto-spawned;
- Forecaster's day-specific information must be direct if specialists are inactive;
- one Real-Time evidence scout may remain callable but must not be auto-called;
- Nova token optimization remains deferred.

Focused role/inventory verification completed before commit:

- eight direct pytest-style assertions passed without installing pytest;
- all 20 affected unittest cases passed;
- Python compilation passed;
- the capability receipt reported exactly 1,940 BigSuite leaves, 46 blocks, and zero unregistered/silently omitted leaves or executable tools.

Before further Frankie architecture work, write a build-control document that names the authoritative registry, leaf-count/hash invariant, role-overlay schema, no-drop gate, runtime wiring proof, test matrix, change ledger, stop conditions, and approval points. Use all applicable skills and have independent agents read back the plan before implementation.

## Production and cost boundaries

- Keep `chatgpt/ng-exhaustion-october-sharded-20260824` fixed at `a7611133f64064200de48cd2e7839fcea2510d51`.
- Do not rerun October Step-1.
- Do not rerun this two-day Step-1 computation.
- Do not call Real-Time Frankie, Forecaster Frankie, specialists, helpers, scouts, or another provider until Greg approves the exact preflight, prompts, data exposure, logical-call count, and cost.
- Do not alter production.
- Do not run broad tests.
- Do not compare the two-day structures against the 54-week answer population.

## Drop-in for the next chat

> Take over `DavisAI1974/Markets` on the latest remote head of branch `chatgpt/frankie-october-aws-readonly-20260824`.
>
> Required first reads: read and obey `research/kalshi/NG_EXHAUSTION_FRANKIE_MONTHLY_RUN_PROCEDURE.md`, then read `research/kalshi/NG_EXHAUSTION_TWO_FRANKIES_FULL_SUITE_HANDOFF_20260824.md` completely, then read `research/kalshi/NG_EXHAUSTION_TWO_DAY_STEP1_TRANSFER_HANDOFF_20260824.md` completely. Use the applicable agent skills before acting.
>
> The two-day Step-1 science for `[2021-10-04T00:00:00Z, 2021-10-06T00:00:00Z)` is complete and passed on AWS. Do not rerun it. Run `32782745590`, job `97608112834`, SSM command `3647c63a-c632-492b-b777-927e727b7e98` produced receipt `140c6234b8e6f4216416290aa50f4070160e200a3e7025cbca3aa08d0ef42e52` and archive SHA `27cacc62681bc482e89eefcc3746f5d71958beab4e25816054e0c388a0346b33`. The archive remains at `/mnt/markets/ng_exhaustion_two_day_step1_20260824/32782745590-1/results.tar.gz`.
>
> The workflow is red only because the post-compute signed-upload preflight hit an S3 `TemporaryRedirect`/`HeadObject 404`. Perform transfer-only recovery of that existing archive. First present Greg with the exact transfer-only preflight/command, data exposure, logical-call count, and cost and wait for approval. Use the explicit `us-east-2` bucket endpoint/SigV4 or another proven authorized transfer path. Then verify the tar, receipt self-hash, every receipt-listed artifact, and publish `COMPLETE.json` last. If the worker archive is missing or its hash differs, stop; never silently recompute.
>
> Preserve production at `a7611133f64064200de48cd2e7839fcea2510d51`. Do not call either Frankie/provider yet. After transfer verification, Greg and the new chat will inspect the two-day results first. Preserve the full 1,940+ capability registry; role states are `DIRECT`, `TOOL_ACCESSIBLE`, or `DORMANT`, never dropped. Treat the committed 24-surface role-profile files as drafts, not proof of complete runtime wiring. Before further architecture changes, create and approve a build-control document using all applicable skills.
