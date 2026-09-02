# DROP-IN S121 — FRANKIE GETS EVERYTHING, AS IT ARRIVES, AND DOES THE CALCS HIMSELF

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`, tip is the last commit of S120 (check
`git log --oneline -1`; it must say "Salvaged draft" or later). **1,483 tests green.** Read
`SESSION_HANDOFF_2026-09-02_S120.md` sections 7 and 8, then `FRANKIE_WIRING_TODO_S120.md`,
before anything else.

## ITEM ZERO — GREG'S RULINGS. THESE ARE THE SPEC. DO NOT RE-DERIVE FROM ANY OLDER DOCUMENT.

1. **Frankie is supposed to be doing the calcs.** The runner did them on one data run that was
   wrong in the first place. Mission section 5 is rewritten; the runner captures, retains and
   proves; its `calculation_result.json` is NOT his evidence.
2. **He gets every record of every field for the day being run**, Sunday for Sunday, Monday for
   Monday, and so on. Delivered **exactly as it comes in RT**: F_LAST-closed groups in
   `ts_recv_ns` order, visible only once their F_LAST is received, never ahead.
3. **The proposal lineage goes in whole.** Disregard its "do not promote / research memory /
   proposal-only" language; every lesson carries VERIFIED / UNVERIFIED / REFUTED; Frankie
   verifies against the stream; only the refuted comes out.
4. **No historical number is a spec.** Not 99, not 16, not 10, not 18,837. Derive counts from
   the current contract and registry at validation time. **No floor below the full count**:
   "if it's supposed to have 30, the floor is 28. 10 is how 20 get silently dropped."
5. **No hardcoded windows or horizons.** Clock values, run times, prebirths and H times are
   derived from what actually happens, on the multiple clocks that were built for it.
6. **A helper is a tool invocation** inside REAL_TIME_FRANKIE or FORECASTER_FRANKIE with
   selectable persona options. Never a parallel lane (D63/D64).
7. **Nothing is dropped without discussion (D60)**; keep-everything is a first-class answer (D76).

## ITEM ONE — THE HARDCODED WINDOWS AND THE MISSING CLOCKS (a D60 discussion with Greg, first)

Still in the path, measured: `ACTIVITY_WINDOWS_S = (1, 5, 20, 60, 300)` in the hash-locked V4
adapter feeding `activity` / `activity_full` on every member row; 4.11's H ladder; 4.16's
fixed horizon version. The registry's seven causal clocks (event, receive, event_known_by,
feature availability, prospective discovery/confirmation, model evaluation, lock time) have
no producer mapping; the row carries `clocks` with five fields. **Discuss with Greg what
replaces the fixed windows and how each of the seven clocks is produced, then build.** The
adapter is hash-locked; restore by wrapping, never editing (D61).

## ITEM TWO — RUN THE THREE PERSONAS (Greg: "salvage it and we'll run them in new session")

Their specs are in handoff section 8.3, verbatim enough to respawn. Use the test-engineer
persona, `isolation: worktree`, one per item, disjoint files, never push from a worktree.
- Knowledge delivery (to-do items 3-5): rebind the knowledge layers to the KEEP files of
  `NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md` (sections C, D, E, F, the brain),
  render the knowledge block, receipt, NOT_READ refused, every excluded path listed with why.
- The 99-layer crosswalk (items 6, 9): producers with file:line, NO_PRODUCER_FOUND allowed,
  pre-call status COMPUTED, sealed-proof helper, the seven clocks mapped or NO_PRODUCER_FOUND,
  every hardcoded window flagged.
- Output ledgers (item 8): the FULL derived set, chain-hashed append-only, per contract section
  read from the contract's headings, 9a classification, knowledge verification, state movie
  with book and FIFO per cutoff, timings on the clocks. A salvaged, unverified, pre-correction
  draft exists: `native_principal_outputs_draft_20260902.py` (raw material only).
Then, as the single writer: wire the emitter to the knowledge block and the sealed proof, the
staging gate to the output validator, the spawn gate on every applicable input receipt (item 7),
register F-21.. and D82 (item 10), merge, run the suite, push.

## STATE, VERIFIED BY EXECUTION

- **The raw-MBO stream delivery is BUILT and MERGED** (`80f8b33`): `native_causal_stream.py`
  (one group at a time, byte-identical, no peeking, per-group receipts through the registry's
  own validator, which had no caller before), `fetch_frankie_ledgers.py` (gz length vs S3, plain
  bytes vs the box's `wc -c`, sha256 vs `PLAIN_SHA256SUMS`), the delivery workflow
  `frankie_ledger_delivery_20260902.yml` (presigns seven days, publishes a manifest artifact;
  pinned to run 33630348943 by default), the emitter requiring a delivery receipt and naming
  the ledgers as THE evidence, staging refusing NOT_READ on a delivered ledger.
- **The first delivery row exists.** Workflow run 33666109982 published the manifest; the
  session fetched Sunday's three ledgers, all VERIFIED (member 10,630,127,166 bytes), receipt
  `d973b025...`. The manifest's links expire 2026-09-09T18:15Z; re-dispatch the workflow for a
  fresh one. Fetch: download the artifact zip, then
  `python3 -m research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers fetch --manifest <dir>/delivery_manifest.json --out-dir <dir>/delivered --receipt <dir>/RECEIPT.json`
  (about 12.6 GB on disk; the container has ~26 GB).
- **FIFO and the book are in every row** (`book_full` levels carry `fifo_queue` with order_id,
  priority_recv_ns, priority_sequence, size, volume_ahead; plus `book`, `book_regime`,
  `activity`, `activity_full`, `structure`, `clocks`, `integrity`); 48 top-level fields.
- **Of the 99 registry layers, 78 are inputs to him, 75 apply to A-clean, 2 reach him today.**
  The 21 non-inputs: 9 sealed (correctly sealed on Sunday), 2 shadow, 10 that are HIS outputs.
  91 of 99 bind their evidence hash to the feed-inventory document; the pre-call gate stamps
  status off the policy. The canonical list is the feed inventory + the source-file inventory
  (149 paths, A-M); registry never bound to the second.
- Earlier this session, also merged: sections 4.0 and 4.0b, the field census, mission 9a, the
  evidence-read gate, the report render, F-16/F-17/F-18 joins.
- Canary 33659412614 on the merged calc code was left running and never checked; the Sunday
  full run was NOT dispatched (Greg stopped it). D68's stop-for-the-reveal still stands.

## STANDING RULES THAT BIT THIS SESSION

- A gate that reads status off a policy is not a gate. A delivery is proven by a row from a
  real run naming the layer, the carrier and the receipt hash. "Done" is that row.
- An interrupt stops background personas and their uncommitted worktrees are lost. Personas
  commit at every slice. Nothing is reported done without its commit sha.
- The mission and the registry said one thing, the spawn did another, and no gate between
  them measured anything. Wire the document to the gate, or the document is prose.
