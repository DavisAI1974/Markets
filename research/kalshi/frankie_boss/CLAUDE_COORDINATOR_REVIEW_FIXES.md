# Claude: coordinator recovery and training checkpoint fixes

Date: 2026-09-15. Bounded slice assigned by Codex after the Claude review
(CLAUDE_REVIEW_FRANKIE_BOSS_INTEGRATION_20260915: H1, M5, L1, L3).
Base: `codex/full-frankie-boss-connection-20260915` @ ae0102d8c28ed0589c86bb6f733e13b3914dea01.
Branch: `claude/coordinator-recovery-fixes-20260915`. Worktree: E:\Markets-coord. Local commit only, not pushed.

Ownership honoured: only `feedback_cycle.py`, `boss_training_checkpoint.py`, the two new test files and this
note changed. The adapter, runtime, lifecycle, source recovery and their tests are untouched. The chronology
guard and the completed-replay-before-factories lookup are byte-for-byte where they were.

## Changes

### H1 - coordinator recovery gap (`feedback_cycle.py`)

The coordinator saves `principal_intent` before the adapter writes its durable `session-request.json`. On
resume the old branch could only call `recover`, and a `None` result raised `AmbiguousPrincipalCall` forever,
even when nothing was ever dispatched.

New behaviour on the `intent is not None` branch:

- `recover` raising the adapter's `PrincipalNotDispatched` (no durable request exists) is the only signal
  on which the coordinator calls `execute`. It is resolved lazily by name from
  `frankie_principal_adapter` (`_not_dispatched_signals()`); the coordinator never defines it and no adapter
  code was changed here. Until Codex exports the class, the tuple is empty, nothing is caught, and an intent
  without output stays ambiguous exactly as before.
- `PrincipalPending` (durable request, no response) is not caught and propagates. No resubmission.
- Any other exception from `recover` propagates. A `None` result after actual dispatch still raises
  `AmbiguousPrincipalCall`. Safety is never inferred from a generic failure or a missing response.

### M5 - feedback roster (`feedback_cycle.py`)

Before `_save(request_id, 'feedback', ...)` and therefore before `checkpoint.apply_completed`, the verified
feedback's `sessions` must be a tuple whose `session_id`s equal, in order, the requested
`learning_kwargs['sessions']` `(name, session)` roster (`_requested_session_ids`). A mismatch raises
`ValueError('principal feedback session roster differs ...')`. The retained `principal_output` stays for
diagnosis; no feedback row, no training row, checkpoint `_failed` stays False, weights unchanged, and a
corrected `verify` completes the same request without re-executing the principal.

### L1 - export identity (`feedback_cycle.py`)

A caller-supplied `export_kwargs['request_id']` that differs from the cycle request raises
`ValueError('export request identity differs from cycle request')` before export, prepare, intent or
principal dispatch. An equal ID is accepted; an absent ID is filled as before.

### L3 - checkpoint identities (`boss_training_checkpoint.py`)

Admitted identities are held privately (`self._identities = dict(identities)`, detached from the supplied
mapping) and exposed by an `identities` property returning a fresh plain `dict` on every access. Mutating the
supplied dict after construction or the returned dict never changes the admitted mapping. `MappingProxyType`
was deliberately not exposed: `_tree` in `encode_state` accepts `dict` only, so a proxy in the envelope would
fail exact-type serialization. The envelope, the on-open identity comparison and the coordinator's
`training_identities` binding all read the private copy; the persisted encoding is unchanged in shape.

## New test evidence (run once, after the fixes; baseline run before the fixes recorded below)

`PYTHONPATH=".;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests"`, pytest 7.4.3, Python 3.13.7.

`tests/test_claude_cycle_review_fixes.py` (6) + `tests/test_claude_checkpoint_identity.py` (1): **7 passed**.

| test | seam | baseline (ae0102d8) | after |
|---|---|---|---|
| intent_without_durable_request_dispatches_exactly_once_on_recovery | H1 not-dispatched -> one execute | FAIL (AmbiguousPrincipalCall) | PASS |
| pending_outbox_propagates_without_redispatch | H1 PrincipalPending propagates, no execute | PASS (guard) | PASS |
| generic_recovery_failure_never_infers_safety_to_dispatch | H1 generic error propagates, no execute | PASS (guard) | PASS |
| feedback_roster_mismatch_rejected_before_save_and_training | M5 reject, checkpoint usable, weights untouched | FAIL | PASS |
| feedback_roster_order_must_match_requested_sessions | M5 order | FAIL | PASS |
| conflicting_export_request_id_is_rejected_not_overwritten | L1 | FAIL | PASS |
| identities_detached_from_supplied_and_returned_mappings | L3 | FAIL | PASS |

Existing tests that exercise the two changed modules, run once as regression on the changed code:
`test_feedback_cycle.py`, `test_cycle_chronology.py`, `test_boss_training_checkpoint.py`: **20 passed**.
No other suite was rerun; no smoke runs; no cloud, Pod, model, principal, replay, broker or Memory A action.

## Limitations (unresolved, reported not hidden)

1. **H1 is verified against a local double.** The adapter at ae0102d8 exports `PrincipalPending` only. The
   not-dispatched test installs `LocalNotDispatched` under the agreed name `PrincipalNotDispatched` on the
   adapter module via monkeypatch when the real attribute is absent, and binds to the real class automatically
   once it exists. The integrated seam (real `recover` raising it when `session-request.json` is missing, and
   the adapter's own `execute`/`verify` paths under the new contract) is Codex's to verify when the two changes
   meet. Until then the coordinator's behaviour on that branch is unchanged from baseline by construction.
2. **Checkpoint code hash is part of the binding.** `_layout()` pins `runtime.code` to the bytes of
   `boss_training_checkpoint.py`, so any retained training checkpoint database created under the previous file
   will refuse to open with 'training checkpoint identity or chain differs'. That is the module's existing
   design, not a new rule; it applies to any edit of the file. No retained checkpoint exists in this worktree.
3. `_requested_session_ids` reads `session_id` off the second element of each `(name, session)` pair and
   requires that exact shape; the learner's `_validate` reads the same shape.

## Blob hashes (git, LF; the checkout is CRLF)

- feedback_cycle.py 594e2477b2cc5e8fab87ddf97962c91c13c52616
- boss_training_checkpoint.py b8c5b2585d693b0d310c05e70a86c2b5dd2cc956
- tests/test_claude_cycle_review_fixes.py 07987601853fe74f523f473c8321c8b994c1c508
- tests/test_claude_checkpoint_identity.py 0bcafc8becd5856cad7ec4405b0e6da7fce881b2
