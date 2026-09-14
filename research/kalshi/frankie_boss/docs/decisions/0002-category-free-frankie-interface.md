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

Both standalone entry points default to invoking the exact legacy callback before
native imports or ledger reads. Enabled projection restores the trusted artifact
and regenerates the projection to prevent coherent but fabricated numeric payloads
from borrowing a valid artifact digest. A typed record alone is a validated value,
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

Runtime pinning deliberately rejects incompatible restores. Full journal verification
and repeated artifact reconstruction favor correctness at this software boundary;
throughput is unmeasured. No fitted weights, calibration evidence or B2_GATED
production completion follows from synthetic tests.
