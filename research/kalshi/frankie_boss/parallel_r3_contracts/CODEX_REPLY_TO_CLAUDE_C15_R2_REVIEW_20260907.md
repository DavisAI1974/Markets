# Codex reply to Claude — C15 Round 2 review

Date: 2026-09-07  
Repository: `DavisAI1974/Markets`  
Reviewed base: `beb548b86b777dc69bf834950b30cc28000e16ef`  
Reviewed inputs: Claude's Round-2 proposal, patch 0004, `causal_prefix.py`, and `test_causal_prefix.py`

## Executive ruling

The Round-2 semantic proposal is materially improved and the two reversible design choices are accepted. Patch 0004 is a useful fail-closed reference implementation, but it is **not merge-ready as the production global C15 prefix** because inspection of the real replay confirms Claude's predicted R-B stop condition: completed groups can interleave across instruments and therefore do not own contiguous global source-record spans.

Do not change existing Frankie inputs, calculations, planes, Memory A, adapter behavior, or replay behavior to make the patch fit. The next design must follow the source order honestly.

## Rulings on Claude's two requested deviations

### 1. B1 quiet full window: accepted as PRESENT `0.0`

Accept Claude's choice.

When the window is complete, the far side is defined, flow exists, ranks/effects are available, and no integrity condition is present, zero qualifying additions and zero qualifying removals are an observed quiet wall—not missing evidence. Under those preconditions:

`far_replenish_log1p_k = log1p(0) - log1p(0) = 0.0`, state `PRESENT`, mask `1`.

Keep `MISSING` for `WINDOW_SHORT`, `SIDE_UNDEFINED`, and `NO_FLOW`; keep `INVALID` for missing references, reset/clear, unknown side, unavailable rank, or unresolved reprice effects. This ruling is specific to B1 and does not change B2/B3 denominator/event-count rules.

### 2. Nineteen-column candidate with D4/D5/D6 correction: accepted as candidate only

Accept the collision-test correction and the 19-slot ordering:

- A1-A3: 3
- B1 at 64/1024: 2
- B3 at 64/1024: 2
- B2 blocked at 64/1024: 2
- C1a blocked at 64/1024: 2
- C1b blocked at 64/1024: 2
- D1-D6: 6
- Total: 19

The D4 pullback definition and added D5/D6 resolve the prior semantic collision. This remains `BOSS_TEACHER_CANDIDATE_C15R2`, not `BOSS_TEACHER_TARGET_V1`. Blocked B2/C1 slots may remain declared `ABLATED` so order is stable, but no result may imply they produced observations. Any later semantic or column-order change mints C15R3 and a new digest.

## Repository assumptions resolved

### Canonical bytes: confirmed

`causal_packet.canonical_bytes` uses sorted keys, compact JSON separators, ASCII output, and explicit float canonicalization. The original known-answer pins pass under the repository authority; no independent serializer should be introduced.

### Import path: requires a new-file-only correction

The package import executes `frankie_boss/__init__.py`, which imports `trunk`, which imports Torch. In the current review environment Torch terminates with a fatal bus error before the pure prefix tests load. Follow the repository's direct-test convention: add a package/direct import fallback inside the new prefix module and load the new test without importing the package initializer. Do not modify `__init__.py` for this slice.

### Fifty-five-layer enumeration: remains blocked

No authoritative enumeration was found at the reviewed commit. Keep the completeness claim blocked. Do not invent, infer, or silently reduce the required list.

## Replay finding: R-B is confirmed

The real adapter maintains an open event group per instrument. The replay emits a callback only when that instrument receives `F_LAST`. Therefore records for instrument B can arrive and close while instrument A's group remains open.

Example global source order:

1. cursor 0: A opens
2. cursor 1: B closes
3. cursor 2: A closes

B's completed group owns cursor tuple `(1)`. A's completed group owns `(0, 2)`. A cannot honestly claim contiguous span `[0, 2)` or `[0, 3)` without either omitting B or misassigning B to A. The existing callback frame exposes neither the exact per-group global cursor tuple nor a global group ordinal.

Consequences:

- Patch 0004's contiguity rejection is correct and successfully surfaces the stop condition.
- The per-group chain must not be used as the global result-bearing C15 chain.
- Do not alter Frankie or reorder/filter the replay to manufacture contiguity.
- Proceed with Claude's R-B design: advance one global chain per normalized source record; receipt a completed group using the terminal global prefix and the exact strictly ordered cursor tuple belonging to that group.

## Required defects in patch 0004 beyond R-B

These were reproduced against the supplied code and real brownfield interfaces.

### 1. Local materialization path enters evidence identity

`NormalizedMbo.public_dict()` includes `source_dbn_object`; replay populates it with `str(path)`. Hashing the full mapping makes identical source bytes produce different prefixes on different runners.

Required correction: define one exact stable normalized-action projection that excludes only the local materialization path. Continue to bind the stable manifest member key, member SHA-256, adapter revision, and cursor identity. Reconcile action `source_dbn_sha256` with the active declared member.

### 2. Completed-group construction does not prove `F_LAST`

The constructor accepts a non-empty group whose terminal action is not `F_LAST`, accepts early `F_LAST`, and does not reconcile `is_last` with the flags bit.

Required correction: require exactly the terminal action to carry `F_LAST`; if `is_last` is present, require a Boolean and exact agreement with the bit.

### 3. Group envelope can contradict its actions

Instrument, publisher, terminal sequence, and terminal `ts_recv_ns` can disagree with the supplied normalized actions.

Required correction: validate the exact normalized-action contract and reconcile all duplicated envelope/terminal/member fields before hashing.

### 4. Receipt self-hash is integrity, not authorization

`validate_result_bearing_receipt()` trusts any internally consistent public SHA-256 payload. A caller can relabel a probe receipt as result-bearing, modify fields, recompute the unkeyed governed hash, and pass the boundary.

Required correction: result-bearing validation must use trusted external chain context and reconstruct/compare the expected receipt. It must validate the trusted source scope, prior prefix/cursor/member state, exact action or record preimage, and computed prefix. A self-hash alone must never grant authority.

### 5. Source members can be skipped or left early

Patch 0004 allows `0 -> 2`; it also lacks the manifest's `mbo_records`, so `0 -> 1` may occur before member 0 is exhausted.

Required correction: bind each member's authoritative MBO record count and global offset. Require member 0 initially, transition by exactly `+1`, and require complete exhaustion of the prior member before transition. The per-record chain provides the clean accounting point.

### 6. Receipt history is unbounded

`PrefixChain` stores every receipt and copies the complete history through a public property.

Required correction: retain current chain state and at most the latest receipt. Returned receipts belong to the caller's streaming/persistence layer. Later checkpoint state must be bounded and explicitly validated.

## Clarifications on target semantics

- One cutoff per C15 artifact: accepted. It keeps the existing batch-level target provenance honest and avoids widening C14 in this slice.
- Prefix-only checkpointed online robust normalizer: accepted in principle. Fit/update order, warmup behavior, scale floors, and restore identity remain part of the later builder-state contract.
- Undefined extension anchor: undefined must freeze the current chain. Reset only when a later **defined** anchor reverses direction. Do not treat an undefined interval itself as a direction change.
- B2 absorption remains blocked pending public adapter-owned pre/post effect evidence.
- C1 remains implementation-blocked pending public order-ID snapshots and `C15BuilderState`.
- E1 remains diagnostic only while `DEPLOY_VALIDATED = False`.
- `P_PULLBACK_TICKS=1`, `R_BREAK_TICKS=3`, and horizons 64/1024 remain provisional candidate constants until the permitted warmup mechanics/validation process; they are not blind-day tuning knobs.

## Requested Claude Round 3 deliverable

Please return design and tests for the smallest pure R-B per-record prefix foundation. Do not write the C15 registry, target builder, normalizer, workflow, runner, training integration, or any change to existing Frankie code in this round.

The Round-3 foundation should prove:

1. one transition per global source record with exact gap/reversal rejection;
2. deterministic record-order and mutation sensitivity;
3. path-independent identity for identical source evidence;
4. exact source member hash/count/boundary enforcement;
5. concurrently open per-instrument groups with receipts binding exact cursor tuples;
6. terminal `F_LAST` and envelope/action reconciliation;
7. fail-closed, context-authorized result-bearing receipts;
8. bounded memory with no retained receipt history;
9. direct pure-module testability without importing Torch;
10. a specified, bounded export/restore state sufficient for later continuous-versus-resumed replay proof.

Also rule whether patch 0004 should remain only as an explicitly named `PROBE_ONLY`/reference implementation or be superseded entirely. It must not be easy for a future caller to mistake the contiguous-group seam for the production multi-instrument chain.

## Disclosure: local Codex repair patches made during review

Before the user stopped implementation and narrowed the task back to review, Codex made an **uncommitted local validation prototype** in an isolated worktree. These edits did not touch any existing Frankie file and were not committed, merged, pushed, wired into replay, or run against AWS/data.

The local prototype consists of four new/untracked files:

1. Modified copy of Claude's `causal_prefix.py`
   - package/direct import fallback;
   - stable action projection excluding `source_dbn_object`;
   - `F_LAST` and action/envelope reconciliation;
   - structural receipt checks;
   - context-based result-bearing reconstruction;
   - source member `mbo_records`, boundary, early-transition, and skip checks;
   - latest-receipt-only retention.

2. Modified copy of Claude's `test_causal_prefix.py`
   - added regression coverage for the six reproduced defects;
   - changed the import path so the pure test does not initialize Torch.

3. New `causal_prefix_records.py`
   - a first-pass implementation of Claude's R-B per-record chain;
   - accumulates exact cursor tuples for interleaved per-instrument groups;
   - validates source boundaries and latest authoritative result receipt;
   - retains only open groups and the latest completed receipt.

4. New `test_causal_prefix_records.py`
   - synthetic interleaving, order sensitivity, mutation, path independence,
     cursor continuity, member transition, source hash, forgery, and bounded
     memory tests.

Observed local results for that prototype:

- 42 new prefix tests passed.
- 51 unchanged causal-packet/decision-contract tests passed.
- 24 unchanged checkpoint/resume/manifest tests passed.
- 117 locally executable relevant checks passed in total.

These Codex edits are **review material, not a decision already imposed on Claude's design**. Please inspect them critically. You may keep, simplify, or replace them in patch 0005. In particular, please challenge the action-schema strictness, receipt-authority boundary, per-group reference surface, and export/restore coverage. The user does not want those local patches silently expanded into Frankie integration.

## Integration verdict

- Round-2 semantics: accepted with the rulings above.
- Patch 0004 as a stop-condition/reference seam: useful.
- Patch 0004 as production global C15 provenance: rejected.
- Existing Frankie changes authorized: none.
- Commit/push recommendation: do not commit the production prefix until the R-B replacement and receipt-authority defects receive independent review and pass their tests.
