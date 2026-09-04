# SESSION HANDOFF 2026-09-04 S127 - FRANKIE RAN, AND HE OVERTURNED FOUR OF HIS OWN LESSONS

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. 2,701 tests / 6,474 subtests, exit 0.
D61 adapter hash unchanged (`4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce`).

## 0. THE STATE IN ONE PARAGRAPH

**Frankie ran, for the first time on this lineage, and filed.** He consumed all 43,569 groups
through `CausalGroupStream`, computed every one of the eighteen contract sections himself at
twenty turns, wrote a 30-of-30 output bundle that validates, and filed **18 findings, F-45
through F-62**, artifact sha256 `086e5339dad64d6326e51a143b3c7351efe28825cfa1809575fdf302a1d7080e`.
**He also traversed the raw DBN himself** and his independent order-book reconstruction agrees
with the delivered one on every aggregate at every group. **F-20 PASS.** The A-memory carry
fired automatically on the push and refused for the documented reason - Oct 1 is not run yet.
**One real defect blocks the read-back and it is not his: the box's `calculation_result.json`
does not hash to itself.** S125 section 2 and DROP_IN_S126 item zero are WRONG and are
superseded here: Sunday delivered, and every ledger verified against the box's own digests.

## 1. ITEM ZERO IS CLOSED - SUNDAY DELIVERED

The S125 handoff and the S126 drop-in both assert that run 33746436209 uploaded nothing. That
is false. The delivery manifest (workflow run 33828017377) reconciles exactly:

    exact_member_rows.jsonl      10,756,276,521 bytes  sha256 f73e9537...
    exact_lifecycle_rows.jsonl      300,309,453 bytes
    legacy_observable_rows.jsonl     29,329,182 bytes
    prefix .../a-memory/full/7d0068d8ae720772415bf84c8c0689e84408d642/33746436209-1

All three fetched and **VERIFIED** against the box's own `PLAIN_SIZES` and `PLAIN_SHA256SUMS`;
delivery receipt `3420045aecc9c225ce77bf47a184cc2b262685177998f51ff94585b0b3149d1b`. No role
permission was ever needed - presigned PUTs worked. **Do not re-run the Sunday traversal.**

## 2. WHAT FRANKIE DID, AND HOW IT WAS RUN

He was spawned as an agent session over committed files (D70, no API) against the emitted
prompt `data/sunday_spawn_prompt.md`, 158,950 bytes - the first live measurement of an emitted
prompt (D60 size watch; the prior 128,418 was a build-time fixture). He wrote his own
instruments: `frankie_own_pass_20211003.py`, `_finalize_`, `_findings_`, `_artifact_`, and
`frankie_own_raw_traversal_20211003.py`. He imports only the shared plumbing - the bundle
format, `CausalGroupStream`, the registry - and **none of the coordinator's calculation code**.

- 43,569 of 43,569 groups, 57,027 records, `complete = true`.
- 395,447 lifecycle rows read and 395,447 attached; 22,380 legacy rows; nothing withheld.
- 20 turns: the 19 staged cutoffs plus the stream-end cutoff, where close-occasion rows first
  become lawfully knowable. That twentieth turn is the LAWFUL way to consume them, not a
  workaround: a STREAM_END row delivered inside an earlier group would assert at that clock
  that nothing followed, which is the future.
- Bundle receipt `ac42944ad51bd00213b42e7274f17db5c1526c5b8c68fe608b0a2e52ff8d0074`, 30 of 30
  required ledgers. Stream receipt `21a57f04090da622dd7ed7fa253b105f87c7749bf7aa7f3d89ed356ab3f19c72`.
- **F-20 PASS**, from his own stream receipt: `withheld_no_own_clock` 0 and
  `withheld_close_occasion` 0, against 43,569 and 65,960 before the wiring.

**Four traversals, and he accounted for each without being asked twice.** First died at turn 11
on a None-key JSON defect; second hit the same class in the side-file dumps after all 20 turns
had landed; third landed but was refused by the D83 timing rule on five of his own key names -
he scanned the whole bundle for every offender before re-running, so it was one re-run rather
than five. He also rewrote the `knowledge_verification` ledger after landing because two of his
verdicts were wrong; 29 of 30 chains are byte-identical and the rewrite is declared in the bundle.

## 3. THE RECONCILIATION - THIS IS WHAT MAKES THE REST TRUSTABLE

D100 made the ruling conditional: Sunday stands as long as everything else works, and his own
recomputation against the runner's is the test. It passes.

- His per-second aggressor substrate agrees with the delivered one on **17,991 of 17,991
  seconds, 0 disagreements**.
- His own detector promoted 91 candidates and **91 of 91** match a delivered candidate on the
  same event second.
- **He traversed the raw source himself** (`data/sunday_source/glbx-mdp3-20211003.mbo.dbn.zst`,
  973,355 bytes, sha256 verified against the launch workflow's pinned witness, 57,027 records
  decoded). Grouping on the venue's own last-message flag gives 43,569 F_LAST groups - the same
  count - and replaying every message into full depth with per-level FIFO queues reproduces the
  delivered `book_full`'s best price, full depth, order count and level count on BOTH sides at
  **all 43,569 groups, zero disagreements on all eight comparisons**.
- **The one difference is his, and he says so (F-61).** 118 of 87,138 touch-queue comparisons
  hold the same orders in a different order, every one originating at a TFM group: a trade
  partially fills a resting order and the venue restates the residual with a MODIFY. His rule
  treated that as priority-losing and re-queued it; the delivered book keeps it in place, which
  is correct exchange behaviour - a residual restatement is not a new order. He then scopes the
  consequence to his own 4.6 volume-ahead numbers at those levels.

## 4. THE FINDINGS - 18, AND FOUR OF THEM OVERTURN SERVED MEMORY

Verdicts on the 93 served lessons: **24 VERIFIED, 8 REFUTED, 61 NOT_TESTED_ON_THIS_SLICE**.
All 90 brain plays are NOT_TESTED - they key on forecaster-harness channels this stream does
not carry, which is a scoping fact, not a doubt.

The refutations that matter, each with his own numbers:

- **F-46 - the touch is NOT static.** Measured on the full book rather than the group-local
  ladder delta: **6,079 touch migrations**, against the 8 that the old F-32 reported.
- **F-49 - exhaustion runways DO complete.** Old F-08 recorded 91 opened, 0 completed, 91
  censored. Fed an actual completion rule, the 91 resolve as 35 COMPLETED_DECAY, 22
  COMPLETED_BY_OPPOSITE_CANDIDATE, 33 EXTENDED_BY_SUCCESSOR, 1 censored.
- **F-58 - chains run to D9**, not the flat D0/D1 of old F-18, once succession is defined on
  the exhaustion candidate rather than on order-id.
- **F-59 - delivered pressure is the MAJORITY** among groups that actually traded, 993 against
  261, not the 99:1 rarity of old F-30, which pooled single-action groups into the denominator.
- **F-62 - the TFMN lifecycle shape the mission names is PRESENT**, 12 groups with exemplars,
  where memory records it absent.

Also: **F-50**, a lawful pre-birth signal exists on this unit and is weak - both halves
measured, against old F-11's "structurally unreachable"; **F-51**, the nineteen decision points
were placed by a group count and not by anything the market did; **F-52**, two of the runner's
own row families exist at no decision point of this run.

## 5. 9a - KEEP EVERYTHING

**661 classifications** over every censused field and all 55 registry layers: 181 LOAD_BEARING,
311 REDUNDANT, 92 DEGENERATE_ON_THIS_SLICE, 73 RETAINED_UNREAD, 4 CANNOT_JUDGE. **Zero
elimination recommendations.** `book_full` with its per-level FIFO queues is the most
load-bearing block on the surface: queue survival, birth position, replenishment episodes,
ladder topology and every state frame rest on it, and the top-N projection is not a substitute
because the touch moves between levels the projection does not carry. He recommends keeping the
genuinely redundant material too, because it is small and lets a reader check. **Five fields are
named defective AS CARRIED and recommended for repair, not removal** (F-53).

## 6. THE ONE REAL DEFECT - THE RESULT DOES NOT HASH TO ITSELF

`read-back` refuses, and the refusal is correct:

    calculation result declares result_hash c406eee730401de1... and recomputes to 41d980e10e9efc1a...

Ruled out, each by execution: the file is **byte-identical to what the box wrote**
(sha256 `91e47d0d...` matches `PLAIN_SHA256SUMS`), so it is not delivery corruption; all three
`canonical_hash` implementations in the package agree on `41d980e1`, so it is not a hashing
mismatch; the launcher at the run's own commit `7d0068d` is identical to HEAD, so it is not
version skew; the body round-trips identically through `canonical_bytes`, so it is not a
serialization artifact; and no variant - omitting either hash, both, an empty-string
placeholder, renaming - reproduces the declared value.

**This is the F-feed-6 shape S122 recorded as fixed** ("every launcher-written result declared a
`result_hash` that did not recompute and `read_back` refused all of them - invisible because the
tests build results through the launcher's runner, never the launcher"). The fix did not hold
for this run. **It blocks attaching his findings to the runner's result. It does not invalidate
his artifact**, which validates on its own and against the delivery, knowledge and output
receipts.

## 7. WHAT LANDED IN CODE

- **F-20 is wired into the stream receipt** (`bcf554d`). `stream_receipt()` carries
  `falsifier_f20` with the verdict, both totals, both by-section maps and the pre-wiring
  numbers, under the receipt hash. Zero counters on a ledger nobody supplied read
  `NO_LIFECYCLE_LEDGER`, and on a stream cut short `INCOMPLETE_STREAM` - a measure handed
  nothing must not look like a measure that found nothing. Verified RED first. The separate
  stream-receipt workflow stays as the S3-only fallback and should read this block rather than
  recompute the rule (O1).
- **The knowledge is READ, not merely delivered** (`f0e8d91`). The pass loads every delivered
  artifact, verifies each against its receipted sha256 and byte count, and refuses the run on a
  mismatch ("does not run knowledge-blind"). The brain is parsed in full. Retrieval receipts and
  `knowledge_use` are written from what actually loaded. The emitter CLI now BUILDS the
  knowledge delivery when none is passed - `build_knowledge_delivery` had no production caller
  for four sessions.
- **The middle verdict is no longer UNVERIFIED.** Per S124 - NEW marks recency, not doubt - the
  per-day lesson verdict is `VERIFIED / NOT_TESTED_ON_THIS_SLICE / REFUTED`.
- **`frankie_raw_source_delivery_20260904.yml`** presigns the raw DBN sources against pinned
  size and sha256 witnesses, so the principal can traverse from the beginning.
- **D100** recorded: Sunday is not re-run for the STREAM_END cadence; it is reported.

## 8. OPEN, IN PRIORITY ORDER

1. **The result self-hash defect** (section 6). Until it is fixed no daily artifact can attach
   to its run's result, so it blocks the weekdays as well as Sunday.
2. **Oct 1 must run before Sunday's findings can carry.** `build_finding_memory` refuses a later
   day while an earlier roster artifact is absent. Working as designed; do not relax it.
3. **The invocation cadence is a group count, not an event** (F-51). The launcher installs
   `_GroupCadence`, a pure count - `cadence = records * 0.8 / TARGET_SPAWNS`, which is 2,281 on
   Sunday and produced 19 evenly spaced cutoffs. The driver's `CandidateEventCadence`, which
   fires on a recognition or a 4.16 change point and whose docstring says "there is no clock in
   here to schedule on", is built and **not used by the launch path**. 91 candidates were
   promoted and none caused a decision point.
4. **STREAM_END emission cadence** (D100, F-52). 65,962 of 395,447 lifecycle rows are emitted at
   stream end and 65,220 of those are just lineage and mirror, so 4.13 and 4.4 exist at no
   decision point. Fix before the weekdays, never by re-running Sunday.
5. **Five fields defective as carried** (F-53) - repair, not removal.
6. **`periodic_checkpointer` does not fit a from-raw traversal.** Frankie's answer:
   `export_adapter_state` refuses anything that is not a `V4MboAdapter`, and conforming his
   reconstruction to the hash-locked adapter's state schema would couple the two
   reconstructions he built to be independent. Save points for the from-raw run need a
   different mechanism.
7. Nova `plan_retrieval` (D67) - never wired; deliberately not touched mid-run, since editing
   the emitter would break the prompt binding the run was spawned under.
8. O1, O4 and the reviewer's Gap A/B corpus additions, all still open from S126.

## 9. THE FROZEN RUN

`research/kalshi/frankie_raw_mbo_benchmark/principal_runs/frankie-a-memory-rt-33746436209-1/`
carries 49 files, 13,717,276 bytes, hashed in `FROZEN_MANIFEST.json`: the artifact, the rendered
report, the 30-ledger bundle and its receipt, the stream receipt, his five instrument files, the
prompt, the knowledge bundle and its two receipts, the delivery receipt, the cutoffs, his raw
traversal reconciliation and his cadence and stream-end measurements. Mission section 9: freeze
RT before the one-way handoff. It is evidence and is never rewritten; a later day appends its
own directory beside it.
