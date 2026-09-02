# SESSION HANDOFF — S120, 2026-09-02

**Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. 1162 -> 1227 tests. Decisions 77 -> 80.**
**Sunday RERAN on the corrected code and is CONFIRMED. The D68 report is NOT delivered.**

---

## 0. READ THIS FIRST: THE HALF OF D68 THAT WAS NEVER ASKED FOR

D68 ordered, verbatim: *"a full indepth report from Frankie. **on the calcs, on the full raw
mbo, all of it.**"* Frankie delivered the calcs. He opened his report by refusing the other
half — *"Retention is not the question and this document does not re-open it"* — and he was
right to, because he was never asked and could not have answered.

**Measured, not inferred:**

- The spawn prompt contains the words `raw mbo`, `retention`, `drop`, `discard`, `field`,
  `book_full` and `keep` **zero times**.
- Mission **section 9** — what the spawn binds him to — lists nine required outputs. None is
  the raw MBO or what can be dropped.
- He could not have answered anyway. In his own artifact: *"The exact member ledger is
  10,616,914,801 bytes over 43,569 rows... **None of these are in the 34 MB result JSON I
  received**, so every exact-member claim in this artifact rests on the runner's counters."*

**So the raw-MBO question was never asked and the raw MBO was never delivered.** Greg has
asked for this repeatedly and it has been reported back to him as a calculation answer every
time, including twice by me this session.

**THE CALCS ARE NOT THE QUESTION AND HAVE NOT BEEN FOR SOME TIME (Greg, this session):**
*"you keep reporting about the calcs and I've said over and over he are keep them all. they
aren't the issue."* D76 already settled it and the measurement agrees — all sixteen are 1.78%
of the bytes. **Stop re-deriving the calc answer. The open question is the raw MBO.**

---

## 1. THREE INSTANCES OF ONE SHAPE, FOUND IN ONE SESSION

Every one is a settlement that reached a report or a decision ledger and never reached the
document that governs the next run.

**(a) D68's raw-MBO half.** Above. Recorded in DECISIONS.md, absent from the mission.

**(b) Two of Frankie's three proposed new calculations were never built**, and the reason is
mechanical rather than a judgement call: **not one recommendation from his report was ever
registered in `OPEN_ITEMS.json`** - the store holds 188 items, its `current_session` was
stale at S117, and searches for detector-coverage, section 9a, raw MBO, non-replacement,
replaced_quantity, F-17 and 'Average decision' all return zero. A recommendation living in
prose has nothing counting it. (My first version of this sentence said the store held ZERO
entries. It holds 188; I read a render-extract count as the store count. Corrected.) Only (c), the cross-section agreement
gate, shipped — because it was also his single highest-value recommendation and got restated
in the defect register, which IS numbered and IS worked. The two that did not:

- **A per-second flow and quote substrate as its own section.**
  `legacy_per_second_roll20` — 22,380 rows, 2,028 trades, 474 buy / 488 sell seconds — is the
  substrate the candidate detector and ALL of 4.12 run on, and it is not one of the sixteen:
  no declaration, no stratum, no averaged companion, no acceptance gate.
- **A detector-coverage and rejection-accounting section.** The selection function that
  CREATES the population for 4.10/4.11/4.12/4.16 is outside the contract. It searched 6,592 of
  17,991 seconds (36.6%), considered 4,462, promoted **91 (2.04%)**, rejected 4,371 across five
  named reasons. **4.11's `detection_share = 1.0` is unfalsifiable precisely because the
  rejected 4,371 sit outside the contract that governs the population.**

This is D36 recurring. S112 found 12 of 13 build suggestions had no registry item and made
that a rule; the rule did not survive contact with a report that was not a numbered register.

**(c) The non-replacement rule is written and unenforced.** Greg asked for a rule that
averages never replace the exact run. **It already exists, verbatim,** in the contract
preamble: *"Exact evidence is never discarded or replaced by an average."* 4.16 restates it.
**The rule is honoured in STORAGE and broken in DELIVERY** — the exact ledgers are written,
retained, counted and witnessed, and then stay on the box while the principal receives the
result JSON. For the only consumer that matters, the average did replace the exact.

The one check guarding it reads a counter:

```
"exact_members_present_beneath_summaries": self.member_rows_written > 0 or not companions
```

The code's own comment beside it already says what is wrong with that shape — *"reads a
COUNTER... present, typed, in range and attesting nothing."* `> 0` proves rows were written
somewhere. It cannot prove anyone read one. Outcome, from Frankie: **16,293 averaged rows
read, zero member rows read.**

**Adding the rule again would change nothing. It needs a gate at the delivery boundary** —
either the exact rows reach the principal, or the run states in words that they did not and
which claims therefore rest on counters.

---

## 2. THE AVERAGED VIEW IS AUTHORIZED ALMOST EVERYWHERE AND HAS EARNED ITS KEEP ONCE

Greg: *"we stated for the 16 calcs that we would look at any value that running the same focus
averaged too... and he settled that long ago by only saying one or two would be run both
ways!!!! that should have been in the calc descriptions!"*

Measured against the contract's own per-section `Average decision` lines:

| decision | sections |
|---|---|
| **no** | 4.1 |
| conditional | 4.3 (conditionally), 4.4 (when matched support exists), 4.6 (limited), 4.15 (only after discovery is frozen) |
| **unqualified yes** | 4.2, 4.5, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12, 4.13, 4.14, 4.16 |

**Thirteen of sixteen authorize it. The dual view paid off once**, and Frankie is the one who
measured that, in 4.7: *"its coequal ratio pair **earned its keep exactly once in the whole
artifact**, detecting that replenishment is size-dependent behind the touch (mean-of-ratios
14.86 vs ratio-of-sums 9.65) and size-invariant at it (44.01 vs 42.63)."*

The run emitted **16,293 averaged rows across 11 sections** on that authorization. The
contract is hash-bound into run identity, so it is the one document where a settlement like
this actually binds — and it is where the settlement is not.

---

## 3. WHAT DID GET DONE, AND IT IS ALL VERIFIED

**Item one of the drop-in, closed with a finding.** The S119 canary (run 33615934710) was
green — but it ran on `53c4943`, the commit **before all eleven defect-fix commits**. It
validated the corrected MISSION, not the corrected CODE. The drop-in's wording was precise;
the rerun was still outstanding.

**Sunday reran on the corrected code and is CONFIRMED** — run 33630348943, `mode=full` on the
box, one roster object, both reducers on.

| | |
|---|---:|
| records / groups | **57,027 / 43,569** — identical to the pre-fix run |
| total ledger bytes | **10,924,504,920** |
| bytes per record | **191,567 (187.1 KiB)** |

Every ledger's sink count matches the box's independent `wc -c`, delta **+0** on all three.
**The 14.0 GB projection was 28% high** — and that is NOT a reduction: the 246 KiB constant
came from a 50,001-record canary over the roster's opening and this is a complete session.
They measure different things. It means the disk precheck is conservative, which is the safe
direction to be wrong in.

Run 33628487030 (flags off, same commit) isolates the regression check: the change-point
commit does not disturb the default path.

**The token reducer is applied (D78)** and measured on the real run by decoding its own rows:
17,914,881 unaliased against 12,365,788 written, **5,549,093 saved = 31.0%**, 55 names, about
1.39M tokens. The S119 hand estimate said 33.8% and ~1.69M. **The rate was close; the total
was high because rows fell 16,293 -> 13,136**, which is D-12 binning the stage index into
closed octaves — a real effect of the fixes.

**4.16's event-driven half has a caller for the first time (D80): 88,071 change points,
`FED_BY_THE_TRAVERSAL`**, from 91 tracks. The size question it raised is answered by
measurement: the whole lifecycle ledger carrying them is 265 MB, **2.4%** of the run, against
`exact_member_ledger` at 97.3%.

**D79 is Greg's and it overruled me.** Sunday runs in the configuration the remaining days
will use, not the one easiest to compare. Holding it byte-comparable to 33605852433 would have
measured a setup nobody will run again. What made it affordable is that the two reducers land
in different layers and cannot confound.

**Three defects found by hitting them, each the branch's recurring shape:**
1. `emit_frankie_spawn` read the rows directly; on an aliased layer that lookup succeeds,
   returns the right count, and reports **every row under `None`**. Reproduced before fixing.
2. The size table went only to a step summary, which cannot be read back through the API —
   the same fix its own witness already had, left undone for the table beside it.
3. The report could not say whether a section was FED, only what it cost. The cheapest thing
   to drop is always the thing that produced nothing.

---

## 4. TWO OF MY OWN NUMBERS WERE WRONG AND GREG CAUGHT BOTH

**The ingestion gate is 99 entries with `hard_minimum_concrete_layer_count: 90`, not 78.** I
summed only the three `*_REQUIRED` policies (19 + 4 + 55) and called that "the gate". The other
21 are gated under different policies — `SEALED_FOR_A_SCOPE` 9, `PROVISIONAL_SHADOW` 2,
`APPEND_ONLY_OUTPUT` 10. **Nothing was changed; I quoted the wrong number.**

**"Skeleton" is not a designed thing.** It appears in exactly two live places — the token
reduction doc and one line of the spawn prompt — has no definition anywhere, and means "the
result JSON minus `layers.averaged_companions.rows`". It leaked from the token measurement
into the prompt and I used it as if it were part of the architecture.

---

## 5. WHERE FRANKIE'S ACTUAL OUTPUTS ARE, BECAUSE THEY WERE NEVER SURFACED

Greg: *"he's supposed to come back with lots of outputs from the calcs... i have yet to see
anything about any d's or families or exhaustion info, prebirth, etc."*

**They exist and I reported only the assessment document.** `frankie_principal_findings.json`
carries **44 findings**, each with claim, evidence, falsifier and confidence basis. Examples
of what was sitting there unreported:

- **F-18 chain depth.** Of 21,651 lineage nodes, **21,344 (98.58%) are D0 roots and 307
  (1.42%) are D1**. Observed max depth 1. D2+ are ABSENT, not suppressed — no maximum depth is
  imposed. 48 TERMINATED, 21,603 CENSORED_STREAM_END.
- **F-19 interstage delay is strictly bimodal by transition type.** 243 of 249 ADD-transition
  descendants have interstage delay of **exactly 0 ns** — the child enters in the same event
  group. TRADE-transition descendants are separated by real time (side A n=27 p50 14.7 us, p90
  4.08 s, max 15.60 s). *An order-ID lineage step that is an add is a bookkeeping successor; a
  step that is a trade is a causal one.*
- **F-11 prebirth is unreachable by construction** and `detection_share = 1.0` is a tautology.
  All 91 candidates are H+N; PRIOR = T0 = MISSED = CENSORED = 0.
- **F-12 recognition delay is second-quantized and hits a hard ceiling** — 6 s to exactly 50 s
  with nothing beyond; 24 members sit in all-at-ceiling strata; population mean 42.6 s is
  pulled to the cap by construction.
- **F-08** 91 runways opened, 0 completed, 91 censored; the two open-world states are
  **perfectly side-locked** (59 side-A / 0 B, and 0 A / 50 B), so the discovered state is a
  re-encoding of side, not an independent axis.
- **F-09** every REVERSAL duration shares the nanosecond remainder **372,071,705** — they all
  end at one wall-clock instant, the observation-window end. The "median reversal of 1,717 s"
  is the position of the stream end.
- **F-05 the family crosswalk**: elementary add A = 16,199 groups, cancel C = 15,136, modify
  M = 3,896, AN = 3,727, CN = 2,182, MN = 794; trade-bearing seeds two orders of magnitude
  rarer (TFCN 812, TFC 162, TFM 139, TFFCCN 32). **The lifecycle the mission names as worth
  recognising, AN -> TFMN -> TFCN, is not observable — no TFMN family appears at all.**
- **F-21/F-22** 51.6% of dipole stages have NO_DIRECTION; normalized imbalance sits near 0.06
  while signed flow swings +1.29 to -10.60 — decoupled, and a positive finding, not a null.

---

## 6. STATE AT CLOSE

Tip `7638659`. **1227 tests green.** All store gates green including `index_py` and `docs`.
Working tree clean, nothing unpushed. Decisions **D78, D79, D80** added via the store and
rendered, never edited in the render.

Nothing was built for section 4.0, the detector-coverage section, or the raw-MBO census. A
census test file was started and removed; **no code for it exists and none is claimed.**

---

## 7. S120 CONTINUED — THE QUESTION WAS ADDED, THEN THE CHANGES THE HANDOFF CALLED FOR WERE MADE

Greg: *"add the question and then mame those changes before we do a final correct run"*, then
*"do your plan"*, *"and use a persona to help you"*. Section 6 above said nothing was built for
4.0, 4.0b or the census. That is no longer true. Everything below is committed, pushed,
tested and gate-checked; nothing below is claimed from reading.

### 7.1 What was built, in the order it landed

- **The raw-MBO question is in the mission and the spawn refuses a mission that omits it**
  (`34a0c16`). Mission section 9a; `emit_frankie_spawn` halts on a mission without the
  `### 9a. The raw MBO` marker; the prompt renders what he is and is NOT given per ledger.
- **The report is a render of the findings** (`60750c9`, F-19 DONE).
- **F-10..F-19 registered** in `research/kalshi/OPEN_ITEMS.json` (`46a41c5`), correcting the
  "ZERO entries" line above: the real registry held 188 items and none were Frankie's.
- **F-17 relabel** (`a3dc360`): `replaced_quantity` is `neighborhood_arrival_quantity`, D-3's
  pattern, arithmetic pinned byte-identical.
- **F-16 as a PARALLEL view** (`91f888c`): birth stays the primary stratum; an exit-keyed
  survival sits beside it. The first attempt restamped and broke S119's pinned test.
- **F-18 join 5** (`bfa1c8b`): one `level_event_key` on the 4.6 terminal and the 4.7 episode.
- **Section 4.0** (persona, worktree, `4096fcb`, merged `decd5ab`): the per-second flow and
  quote substrate the candidate detector and 4.12 always ran on and nothing declared. One
  exact row per COMPLETED second, six own-second classes so an unclassifiable second is a
  CLASS never a gap, INCOMPLETE at boundaries outside every denominator, reconciled against
  the traversal's own binner and refusing on disagreement, phase from the second's own
  instant (D75's shape refused). FIRST in the section map. 25 calculator tests + 8 driver
  tests + the dark-section regression.
- **Section 4.0b** (persona, worktree, `202b210`, merged `ed5e782`): detector coverage and
  rejection accounting. Every judged second ends in exactly one NAMED outcome or a residual
  REFUSES; reconciles key-for-key against the detector at every segment close; every
  detector parameter rides on every row. It found a REAL uncounted exit
  (`rejected_in_refractory_at_release`: counters summed 289 against 290 judged seconds).
  Detector emissions proven identical 80/80 against the pristine module. New measure kind
  `COUNT_PARTITION` (no arithmetic mean formed over counts).
- **The field census** (`0fe66c8`, `69c7fc3`): `MboFieldCensus` walks EVERY member row the
  sink receives and reports per field path - observations, rows-with-field, nulls, distinct
  (capped 64), types, range, DEGENERATE, ALWAYS_NULL. **List positions collapse to `[]`**:
  the first version indexed every ladder level, so a census keyed by position would have
  grown with book depth (a 300-level `bid_levels_full` would be 300 x 6 paths) instead of
  with the schema. Emitted as `layers.exact_member_ledger.field_census` with
  `field_census_covers_every_member_row`; the emitter renders the degenerate and always-null
  fields under 9a and HALTS on a result whose census is absent or partial. **It is a
  measurement and its own `basis` says keep-everything is a first-class answer.** Greg
  asked whether this changes the science or averages anything: it does not - read-only on
  its input (a test proves a row is byte-identical after observation), the exact ledgers
  keep every position, and no mean is formed anywhere in it.
- **The report states what the principal read** (`b5e239e`): per-ledger `evidence_read` in
  words, so a claim resting on counters is distinguishable from one resting on rows. F-14
  DONE on that plus the gate; F-11, F-12, F-17 DONE; F-10 IN_PROGRESS (closes on the
  corrected run's artifact); F-18 join 7 closed with 4.0b.

### 7.2 Greg's question: do the new things need wiring into the token reducers?

**No, and it was verified by execution, not by reading.** `build_alias_table` builds its
table from a key census of whatever rows every registered section emits, and the runner
gathers companions by iterating `self.sections` - so a section in the map is aliased
automatically. Run with aliasing ON on the driver fixture: 4.0's nine rows came out with 0
readable raw and 9 after decoding, legend 44 names. 4.0b registers the same way. The
change-point reducer is 4.16-only by design. The census sits OUTSIDE the aliased layer and
is kept small by construction (~80 KB for 256 paths on the fixture; it grows with the
schema, not the book) so it needs no reducer.

### 7.3 Merging two personas that added into the same slots

Both worktree branches were cut from `34a0c16` and each added its section in the same
places - the runner's constructor and section map, the driver's two finalize loops, the
dark-section tuple, the contract before 4.1, the index. Every conflict resolved by keeping
BOTH in order (4.0 then 4.0b); the driver's segment-close and stream-end paths carry 4.0b's
close call before the loop that now includes `flow_substrate`. The knowledge manifest was
stale twice (each persona pinned the contract at its own base) and re-pinned twice by
`refresh_native_frankie_knowledge.py --write`. Suite 1227 -> **1406**, store gates and
docs green, manifest CURRENT. D77 held: neither persona touched git state outside its
worktree.

### 7.4 The final correct run

Canary first, per the standing incremental-validation rule, because the calculation code
changed: run **33659412614** on `69c7fc3`, Sunday slice, `alias_companion_keys=true`,
`emit_change_points=true`. Then the Sunday full run on the same configuration (D79), then
the spawn against its artifact with the 9a question - the spawn now REQUIRES the mission
with 9a, a census covering every member row, and an artifact carrying `evidence_read`.
The mechanism for getting a result into a session is validated: the size-report workflow
publishes `calculation_result.json` as a small artifact (1.3 MB zip for Sunday's 24.8 MB
result) and `download_workflow_run_artifact` yields a signed URL that curl fetches.
Run ids and verdicts for the full run and the spawn are in `DROP_IN_S121.md` STATE.

---

## 8. THE CLOSE: GREG STOPPED IT, AND WHAT HE FOUND IS THE RECORD

Greg, at the end of this session, in order:

- *"Frankie is supposed to be doing the calcs. we just had the runner doing it one one data run
  that we had done wrong in the first place."*
- *"he gets every record of every field for Sunday, the date and time we are running. and
  Monday will get the same thing for Monday and so on."*
- *"this has to exactly mimic how it's going to come in rt."*
- On the proposal lineage: *"disregard anything in the proposal doc that says we shouldn't use
  it. that was not the intent. we need to verify it's good info but if it holds up, it goes in.
  if there's stuff that doesn't, those pieces don't go in."*
- On counts: *"don't take any historical number like that as a valid number that we should
  follow"*; *"not 10 as the floor. if it's supposed to have 30, the floor is 28. 10 is how 20
  get silently dropped."*
- On windows and clocks: *"we aren't using these hardcoded values anymore over
  1/5/20/60/300-seconds ... all of the clock values and run times, prebirths, h times are
  derived by what actually happens. that's why we built multiple clocks! and i didn't see
  those listed."*
- *"the helper agent is one that rt and forecaster can call as part of their tools and there
  are different options for personas."*

### 8.1 What was measured, and it is why he stopped

- **Mission section 5 said "the runner calculates; you interpret"** since the Aug 28 packet.
  Section 3 of the same mission says "receive and study the complete lawful envelope" at every
  group. Every session built to section 5. Section 5 is now rewritten (`80f8b33`).
- **Of the 99 registry layers, 78 are inputs to the principal, 75 apply to A-clean, and 2
  reached him** (mission, contract). The 21 that are not inputs: 9 sealed (the answer wall,
  correctly sealed on Sunday), 2 shadow (D5), 10 that are HIS outputs.
- **91 of 99 layers bind their evidence hash to one markdown document**
  (`NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md`); the pre-call gate stamps status
  off the POLICY (`build_pre_call_receipt`). It proved the document was unchanged and nothing
  about ingestion or delivery.
- **`validate_causal_group_delivery_receipt` had no caller anywhere.** Now called per group.
- **The canonical input list exists**: the feed inventory (15 feeds) and its companion
  `NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md` (149 paths, A-M). The registry
  never bound to the second. Sections A (Sol-era handoff), B and H (older runtime code), L, M
  are old; C, D, E, F are the knowledge. Feed section 10 was already rewritten for D64.
- **FIFO and the book ARE captured**: every level of `book_full` carries `fifo_queue`
  (order_id, priority_recv_ns, priority_sequence, size, volume_ahead) plus front/queue-age
  fields; verified on group 0 of the delivered Sunday ledger. They were never delivered.
- **Hardcoded windows and horizons still in the path**: `ACTIVITY_WINDOWS_S = (1,5,20,60,300)`
  in the hash-locked V4 adapter (`activity`, `activity_full`), the 4.11 H ladder, 4.16's fixed
  horizon version. Greg: derived from what happens, on the clocks. **A D60 discussion, ITEM ONE
  of the next chat, not a silent change.**
- The registry's seven causal clocks (event, receive, event_known_by, feature availability,
  prospective discovery/confirmation, model evaluation, lock time) have no producer mapping;
  the row carries `clocks` with five fields. The crosswalk (item 6) must map each or say
  NO_PRODUCER_FOUND.

### 8.2 What landed (merged, pushed)

`80f8b33` persona A: `native_causal_stream.py` (RT-faithful group stream, byte-identical
rows, no peeking, per-group receipts through the registry's validator), `fetch_frankie_ledgers.py`
(gz length vs S3, plain bytes vs the box's `wc -c`, sha256 vs `PLAIN_SHA256SUMS`),
`.github/workflows/frankie_ledger_delivery_20260902.yml` (presigns, publishes a manifest),
emitter requires a delivery receipt and names the ledgers as THE evidence, staging refuses
NOT_READ on a delivered ledger, mission 2 and 5 rewritten, D81, F-10/F-20. `9395dc9` fixed
its first fire (a quoting bug). **The first delivery row exists**: run 33666109982 published
the manifest; the session fetched all three Sunday ledgers, all VERIFIED, receipt
`d973b025...`, member ledger 10,630,127,166 bytes. **1,483 tests green.**

### 8.3 What was in flight and was stopped

Three personas (knowledge delivery items 3-5; the 99-layer crosswalk item 6 and sealed proof
item 9; the output ledgers item 8) were stopped by Greg's interrupts twice and committed
nothing. Their specs are the to-do file's items with these bindings, to respawn verbatim:
- knowledge: rebind the 15 knowledge layers from the inventory document to the KEEP files of
  the source-file inventory (sections C, D, E, F; the brain), deliver the proposal lineage whole
  with per-lesson VERIFIED / UNVERIFIED / REFUTED, no "do not promote" language, a
  `FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1`, NOT_READ refused; list every excluded path with why.
- crosswalk: `LAYER_PRODUCERS` for all 99 with file:line citations, NO_PRODUCER_FOUND allowed,
  `crosswalk_against_result`, pre-call status COMPUTED not stamped, sealed-proof helper, the
  table run on the Sunday result; each of the seven clocks mapped or NO_PRODUCER_FOUND; every
  hardcoded window/horizon flagged.
- outputs: append-only chain-hashed ledgers = registry outputs + one per contract section
  (read from the contract's `### 4.x` headings, 18 today) + 9a classification + knowledge
  verification; the FULL count required, no floor; state movie carries book and FIFO state and
  delta per cutoff; timing derived on the clocks, never a fixed ladder; helper invocations
  recordable (persona, question, answer hash).

### 8.4 Not done

Items 3-10 and 12 of `FRANKIE_WIRING_TODO_S120.md`; the spawn; the reveal; Monday.
