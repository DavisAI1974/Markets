# Spec: ingest-parallel-replay (the next lever after 1.77 ms per record; NOT built; Greg's call)

MEASURED 2026-09-22 on Frankie's box (run 35693868307, 20,000 records, 31 encoders): 1.77 ms per record on the parent,
1.0 hour projected for the Monday trading day 2021-10-04 (2,032,203 records), down from 8.9 ms and 5.02 hours (run
35681037861) after the incremental observation (022053eb) and the box standard in the writer (87b55109). The encoders
(order dedup + gzip on 31 processes) are not the bound; the PARENT's causal sequence is. What the parent still does per
record: decode the wire record (a DBNDecoder per record), pack/dumps/sha256 the INPUT entry (~1 KB), the record prefix
chain hash (~1 KB canonical), the adapter apply, the fragment update, the composed join of the observation (~200 KB) and
its sha256, the pack/dumps of the rest of the APPLIED evidence (frame, legacy rows, effect, receipt), and every 64th
observation the differential check (~8 ms).

## Objective
The Monday day's compact container, byte-identical to the sequential writer's (same rows, same digests, same head hash;
the box layout may differ only as the standard allows), in about 10-15 minutes on the box's 32 CPUs, by moving the
body serialisation off the causal parent while the parent keeps the one thing that is sequential by construction: the
digest chain, one sha256 per entry.

## Design
1. PASS 1, the parent, causal: the record prefix chain (small hashes) and the adapter apply over every record, with a
   CHECKPOINT every K records (K about 20,000): a deep copy of the adapter's book state (orders, levels, activity
   windows, integrity counters, event group, legacy group rows, top-10 cache, last_* fields) and the chain state (prefix
   hash, open groups, per-instrument ordinals). About 0.15 ms per record: 5 minutes for the day.
2. PASS 2, the workers, parallel: worker k restores checkpoint k, replays records [a_k, a_k + K) through its own adapter
   copy and composer, and emits for each record the INPUT body and the APPLIED body with a fixed-width PLACEHOLDER
   where `previous_hash` goes (the envelope frame is `["dict",[["schema",...],["ordinal",...],["previous_hash",["str",
   <64 hex>]],["kind",...],["payload",...]]]`, so the placeholder is 64 bytes at a known offset). The receipts and the
   terminal prefix hash inside the APPLIED payload come from the chain state pass 1 recorded, so they are exact.
3. PASS 3, the parent, sequential: for each entry in order, patch the 64-byte previous_hash into the body, sha256 it
   (about 0.1 ms for 200 KB), hand the row to the encoders. About 7 minutes for the 4,064,406 entries.
4. The seal and the conformance drain as today (the drain reads the container on the workers, the parent replays the
   predicates).

## Proof of identity
- The both-writers test on the fixture stream (raw sequential vs parallel-replay compact) byte for byte.
- On the box, the first run of the parallel writer on the Monday day is compared to the sequential container's head hash
  from the ingest now running (run 35694087514): equal or refused.
- The differential check of the composer stays in the workers (every 64th observation).

## Boundaries
- The pinned adapter is not changed; a checkpoint is a copy of its instance, restored by the same class.
- The compact codec FORMAT is not changed.
- Nothing runs on the box before Greg's word; the sequential writer stays the default.

## Decided / open
- Open: build it (about a day, TDD) or hold at the hour. Greg's call.
