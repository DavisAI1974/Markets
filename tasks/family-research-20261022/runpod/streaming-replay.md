# Streaming replay handoff

The deployed day runner starts ROOT and Native together after a date has a full
ingest receipt. The overlap setting divides cores between those two producers.
Deferred ingest conformance is a separate mode that can publish a journal seal
before a conformance drain. The active runs use inline conformance.

`committed_ingest.py` proves the input seam for a streaming producer. It reads
the next committed block in journal order using the pinned ROOT checkout's
existing block and envelope verifier. A read can return before the next block
is available. The reader claims completion only when the final journal count
and chain head match the stream it read.

On November 8, 2026, the read-only probe verified three blocks on each live
pod while its date was still ingesting. Each probe read 768 journal entries
including 384 INPUT entries. The test suite compares a growing-stream read
against the original sealed reader, and exercises a broken block chain and a
mismatched seal. Run the tests with the pinned ROOT checkout on `PYTHONPATH`:

```sh
PYTHONPATH=/opt/frankie-box/replay-code/markets python -B test_committed_ingest.py
```

## Producer integration still required

1. Start both producers from the date manifest, approved opening book, and
   producer pins. Feed them the same ordered verified INPUT stream. Pause at
   the committed edge and preserve open-group, FIFO, and lifecycle state
   across blocks. Only finalize once at the actual end of the available span.
2. Bind provisional rows and checkpoints to the pinned source scope and the
   consumed journal chain. The current Native driver stamps input records with
   the final compact-container SHA-256. A streaming contract must explicitly
   bind rows to verifiable source coordinates before that SHA is known and
   reconcile the bindings when the final journal receipt arrives.
3. Publish the usual date handoff only after counts, the terminal chain head,
   journal witness, calculation identities, and conformance reconcile. Reuse
   verified checkpoints on a retry. The rich second set still requires the
   original full-book APPLIED observations and sealed producer handoff.
4. Verify the new route against a bounded sealed replay, including a split
   group, a missing opening span, a reset, and a stopped and resumed consumer.
   Compare scientific values, ordering, clocks, and provenance. Keep the
   October 2 and 17 coverage partial and every date assigned to discovery.

The reader is a verification tool at this revision. The live day runner still
uses its existing ingest and producer receipt gates.
