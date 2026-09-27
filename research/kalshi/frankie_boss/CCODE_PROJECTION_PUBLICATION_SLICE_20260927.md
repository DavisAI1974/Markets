# CCode Projection Publication Slice — 2026-09-27

This slice begins only after the existing same-root ROOT resume has stopped and a real `calculations-receipt.json` exists. A live PID, a 100% counter, or completed range workers is not sufficient.

## Preconditions

Require the actual read-only receipt for:

- Calculation root: `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`
- Runtime: corrected immutable `2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a`
- `calculations-receipt.json` with `status: calculations_retained`
- Receipt byte count and SHA256, with readback equal to the parsed JSON
- Calculation process inactive and no second ROOT run active
- `model_calls: 0`, `source_replays: 0`, and `source_writes: 0`

If any precondition is missing, preserve the evidence and stop. Do not resume ROOT, rebuild records, replay ingestion, or create a new calculation root.

## Read-only verification sequence

1. Read the calculations receipt through the existing `frankie_box_read_log.sh` receipt route:
   `FILE=work/monday-calculations/full-20211004-20260927-r1-48/calculations-receipt.json MODE=receipt`.
2. Read the retained projection summary exactly once:
   `FILE=work/monday-calculations/full-20211004-20260927-r1-48/work/derived/.projection-v2 MODE=projection`.
3. Verify that the projection plan SHA256 is the retained plan `3ef241ac435253142680040976ab6f548b3119b1d73f26e6ca95bb9f78cb73b2`.
4. Verify both `member` and `lifecycle` coverage receipts and range receipts:
   - every range is receipt-backed and `readback_verified=true`;
   - source identities match the sealed ledger pins in the plan;
   - the ordered byte frontiers have no gap or overlap;
   - summed range bytes/rows equal the source ledger byte/row pins;
   - all `.blocks` archive sizes and SHA256 values match their receipts.
   Out-of-order worker completion is not the ordered frontier; use the recorded progress/coverage values.
5. Verify publication from the paths and witnesses recorded by the calculations receipt:
   - the published gzip layer files exist under the retained `.projection-v2/published-*` directory;
   - each file's byte count and SHA256 match its publication entry;
   - the publication receipt exists, is readback-verified, and carries the same plan hash;
   - partial or failed publication attempts remain preserved and are not promoted as canonical.
6. Verify the digest files pinned by the receipt:
   - `work/derivation-digest-full.md`
   - `work/digest-proof.json`
   Their byte counts and SHA256 values must match `digest` and `digest_proof` in `calculations-receipt.json`. Confirm the proof's table inverse/readback checks and the exact producer/crosswalk identities recorded there. Do not regenerate or re-encode the digest.
7. Record available filesystem bytes after verification. The projection reserve remains at least 20 GiB; do not delete anything to improve it.

## Acceptance

Accept this slice only when the calculations receipt, projection plan, complete ordered ranges, publication receipt/layers, digest, and digest proof all agree by hash and identity. Report the actual workflow/SSM IDs, receipt paths, SHA256 values, plan hash, range counts/bytes/rows, published layer bytes, digest bytes, proof bytes, and free space.

## Hard stop

Stop immediately after this verification report. Do not dispatch downstream staging, principal, classroom, grading, correction, retention, Tuesday, learning outcomes, or any new observer in this slice. Do not rerun publication, duplicate staging, clean up additional files, change the runtime, add tests/canaries/validators, or alter orchestration. Any mismatch or missing receipt is a genuine blocker: preserve the output and report the exact path/hash that failed.