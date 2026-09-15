# Sunday actual host: final launch review

All nineteen prefixes completed. Final manifest SHA256: `44992e75ab0c821aac87559d4713bc84dd2f72424e2d904ebe81039def1ce416`. Prefix archives and manifest are published; runtime copies remain on E.

## Actual launch findings and recovery

The first host attempt stopped before inference because an older closed source had a zero-byte WAL and a shared-memory sidecar. Exclusive file handles and the original database SHA256/tail were checked. Both sidecars were preserved in E recovery archives; no source records were changed.

The next attempt exposed a retained teacher binding mismatch. The native model and normalizer matched, but two teacher source files had newline-only changes introduced by checkout. Their original physical bytes were restored from the frozen checkout. Both normalized sources match the pinned Git blobs; git diff remains clean. The teacher binding now exactly matches the retained preparation: `17b047724ecdc66ec6ad6992113f5a38b09bf554874948b83730ab55cdc1d3ec`.

The failed pre-inference attempt, including its untrained initial checkpoint, was preserved at `E:/Codex/Frankie-BOSS-20260915/actual-feedback-run-pre-inference-byte-mismatch`. No critic request was dispatched and no learning occurred.

## Sealed candidate and scoped approval

Existing receipt-only sealer succeeded. Candidate SHA256: `83bd809390498e98b9feb0484e5bf20e8801762585f4ee6d03bafc77971e1db8`, under `sunday-launch-20260915/final-seal-restored-teacher`. Root accepts this candidate for actual local preparation and admission based on the completed source/prefix evidence, prior independent host/transport/compact reviews, and exact restored teacher binding. This record does not certify inference, feedback, or learning outcomes.

No passing test suites were repeated. No prefix or reducer was rebuilt. Runtime commit remains `9a8f3f46abaa3d840b07b685010108e0c551b174`; final-v4 bootstrap is unchanged.

## Current ownership

Actual host PID63112, unified exec session48894, stdin echo disabled. Logs: `actual-host-resume02.stdout.log` and `actual-host-resume02.stderr.log`. Existing final configuration and intended actual-feedback-run directory are in use. Do not create a second host.

The host passed inventory and entered retained preparation recovery. Actual inference has not begun. Before retained Pod start, apply final-v4 package, context131072, jobs_v1 and lifetime `none`; validate exact actual admission and fresh readiness. The stopped Pod still had its historical environment at the last read. Do not confuse desired policy with applied provider state.

Meaningful probe progress never authorizes an elapsed cutoff. Preserve same-job recovery, error reporting, printed Frankie analysis and training checkpoints through all19 cycles.
