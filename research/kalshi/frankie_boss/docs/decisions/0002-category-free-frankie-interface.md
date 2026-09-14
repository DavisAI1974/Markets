# ADR-0002: Separate category-free Frankie contract

## Status

Accepted by the owner in this build conversation, 2026-09-14, following the explicit
proposal for a separate opt-in twelve-field interface with confidence null.
Software acceptance is distinct from production deployment or empirical acceptance.

## Decision and rationale

Preserve the original BLD-1 validator, projector and low/med/high enum unchanged.
Provide BOSS_FRANKIE_CATEGORY_FREE_V1 through
BOSS_FRANKIE_CATEGORY_FREE_ADAPTER_V1. Retain exactly the same twelve payload names,
with confidence strictly null. Put contract, adapter, artifact and optional
publication identities in a separate transport stamp, not a thirteenth payload field.
The old validator intentionally rejects this new payload.

Ranking and optional internal calibrated probability do not become categorical
confidence or trading authority. Publish the sole valid candidate or the highest
ranked comparable candidate, without an absolute floor. Calibration absence is not
a fatal defect. Existing caller metadata still determines trade disposition/plays.
Following the owner's authorization to apply Claude R5, the defects list is
explicitly fatal-only; non-fatal gaps are recorded in reasoning via
report_nonfatal_gaps. They may accompany a valid CALL. Safety abstention preserves
incoming play history in reasoning while leaving the complete zero safety fields.

Both standalone entry points default to invoking the exact legacy callback before
native imports or ledger reads. Enabled projection reads the trusted stored artifact
without executing its decoder and checks the projection against its stored values.
Independent artifact/publication roots and a deep copy of caller metadata are
captured before the proposal loader runs. A proposal cannot supply its own trust
root or mutate those captured metadata. Transport stamps include a metadata hash
and caller_supplied_unverified origin status; no source authenticity is invented.
A typed record alone is a validated value,
not proof that the verified projection entry point was called.

The enabled consumer reads a retained receipt from a verified single-writer ledger
and checks target, source cutoffs/hash, arm, model/decoder binding and complete
context/recurrence receipt packet linkage. It stamps the
selected publication and performs no B1 forward. Known fatal defects, missing
publications, integrity errors and caught runtime/storage failures produce complete
zero ABSTAIN records with explicit defects. Invalid caller metadata raises rather
than inventing specialist/date context.

## Consequences and limits

Original Frankie/S121/spawn.py, B0/B1, raw evidence, replay and Memory A are untouched.
Production callers must explicitly select the new contract; this build does not
deploy or wire a live service. Single-session S121 representability checks remain:
no implicit cumulative multi-session forecast, unsupported DST crossing or invented
path interpolation. Historical revisions remain readable after later updates.

Runtime pinning deliberately rejects incompatible new queries/reproduction, while
structural historical reads preserve exact V1 bytes and identities across runtime
drift. New native publications attest actual producer reproduction through the
trusted ledger; the stamp says publisher_verified, not reproduced in this runtime.
Legacy receipts without that claim remain unknown.

Standalone category-free accounting is exact: net = gap + terminal. Sessions crossing
the next S121 20:00 boundary fail explicitly; no alternative clock or split is implied.
Valid immediate-STOP two-point native curves remain accepted.

Full journal verification remains in place. Bounded synthetic timing is recorded
separately; production throughput is unmeasured. No fitted weights, calibration evidence or B2_GATED
production completion follows from synthetic tests.
