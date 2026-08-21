# New-chat drop-in — NG Exhaustion V4 five-year AWS census

Take over the Markets/Frankie NG exhaustion program from the current remote branch state.

Repository:
`DavisAI1974/Markets`

Branch:
`chatgpt/ng-exhaustion-entry-timing-revival-20260818`

Five-year AWS source-wiring implementation commit:
`5d49c0a80a58878e4fadef6431b35f6e80c9316d`

The exact pushed branch tip is the commit containing this handoff file; re-verify it remotely before doing any work because another agent may move the branch later.

Read first, in this order:

1. `research/NG_EXHAUSTION_V4_NEW_CHAT_DROPIN_20260820.md`
2. `research/NG_EXHAUSTION_V4_5Y_AWS_SOURCE_READY_20260820.md`
3. `research/ng_exhaustion_mbo_5y_aws_source_20260820.py`
4. `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py`
5. `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`
6. `research/kalshi/NG_MBO_5Y_COMPACT_AUDIT_20260820.json`
7. Current V4 contracts/build-plan files already on the branch, using current branch state as truth over stale handoffs.

## Scientific scope

The objective is to group exhaustion events into chain families and determine the exact architecture and characteristics of the exhaustion events in those families. Do not turn this into a generic prediction/classification exercise. The V3 empirical runs were wrong and are not a basis for the V4 study.

## Exposure rule

The only thing that should not be exposed to the research run is Frankie himself. Do not use Frankie's learned brain/rules/priors/conclusions. Do not mutate Frankie. Otherwise do not artificially withhold relevant exhaustion information; preserve causal/reveal integrity so future information is not leaked backward.

## Five-year source

The native historical MBO corpus is already in AWS/S3:

- region `us-east-2`
- bucket `bento-568968024170-us-east-2-an`
- prefix `nymex/ng_mbo_5y_v0/`
- consolidation key `nymex/ng_mbo_5y_v0/_consolidation/COMPLETE.json`
- durable EC2 documented in repo: `i-08cee7171c0a76a04`
- repo path: `/opt/markets`

## What was completed in the previous chat

- Confirmed the five-year census must read the native AWS/S3 MBO archive, not the old 54/55-week local corpus.
- Confirmed the current archive audit: 61 expected intervals, 61 with jobs, 0 missing, 0 unresolved reservations, 102 native DBN objects, 1,470,112,040 bytes.
- Identified the audit's three exact duplicate intervals and four unexpected partial-August overlaps. Therefore prefix-wide S3 enumeration is forbidden for the census.
- Added `research/ng_exhaustion_mbo_5y_aws_source_20260820.py`: fail-closed canonical object resolution, S3 inventory/staging, and source receipt generation.
- Added `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py`: exposes full reconstructed depth and FIFO order queues at every completed MBO event group to the downstream V4 chain-family engine without changing the validated base adapter.
- Preserved the existing `LEGACY_CONTROL` compatibility surface as a separate view of the same native bytes.
- Added `research/test_ng_exhaustion_mbo_5y_aws_source_20260820.py` and `.github/workflows/ng_exhaustion_v4_5y_aws_source_verify_20260820.yml` for fail-closed source behavior and full-state/FIFO exposure.
- Local syntax compilation passed for the new Python files, and a local source-selection smoke check proved the resolver accepts an explicit canonical list and fails closed when only a generic prefix object list is present.
- The connector used in the prior chat could not observe push-triggered Actions runs, so do not claim the new GitHub workflow is green until its actual run is checked.
- No five-year empirical run was launched.
- No frozen 54/55-week detector/canonical artifacts/runway or Frankie artifacts were modified.

## Important adapter nuance

The base adapter's normal serialized `V4_NATIVE_FULL` event frame is compact: top-10 book levels plus aggregate full-depth fields. Do not feed only that compact file to the scientific engine and assume it is the whole V4 state.

The new full-state replay bridge calls `checkpoint_state(... include_full_depth=True, include_order_ids=True)` at every completed event group and exposes that state directly in-process. The chain-family analysis therefore has the full reconstructed book/FIFO state without requiring gigantic full-book serialization at every tick. Native DBN remains canonical and replayable.

## What needs to happen next

1. Re-verify the remote branch tip and inspect the actual GitHub Actions result for the new five-year source workflow.
2. On `i-08cee7171c0a76a04`, pull the exact branch/tip.
3. Run `python research/ng_exhaustion_mbo_5y_aws_source_20260820.py --inventory-only`.
4. If `_consolidation/COMPLETE.json` does not expose an exact canonical DBN list, stop and build an explicit curated object manifest from consolidation/job provenance. Do not silently list the full prefix because duplicate/overlap objects could contaminate counts.
5. Stage a bounded canonical slice and verify native full-state replay plus source/contract/clock continuity.
6. Verify the `LEGACY_CONTROL` compatibility projection on overlap evidence where available; do not assume equivalence.
7. Connect `replay_dbn_files()` to the V4 chain-family grouping/architecture research engine. The engine should consume full causal state and preserve every exhaustion case.
8. Negative, short-lived, censored, disagreement, no-lock, and sparse cases remain findings. Do not drop chains.
9. Freeze the exact canonical source manifest/candidate/rules before a result-bearing pilot, then launch the full five-year census only with explicit authorization.

Do not redo completed work. The five-year source-wiring implementation commit is `5d49c0a80a58878e4fadef6431b35f6e80c9316d`; use the current remote branch state as truth for anything that landed after it.
