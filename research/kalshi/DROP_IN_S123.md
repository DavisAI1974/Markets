# DROP-IN S123 - FINISH THE WIRING, THEN FEED IT

> **AMENDED IN SESSION BY D89 (Greg, 2026-09-03), verbatim:** *"we are not doing canary until all
> of this other stuff is done first."* This file was written to open on a run. **It does not any
> more.** The order is now ITEM TWO and ITEM THREE first, then ITEM ONE. Item zero's diagnosis is
> unchanged and still correct - nothing wired in S121 or S122 has been fed - but the conclusion it
> drew from that diagnosis has been reversed, and the reversal is the sound one: a run dispatched
> over unfinished wiring produces one more set of before-numbers, which is exactly what run
> 33630348943 cost. **A run is worth dispatching once, on finished code.** The outstanding work is
> the Codex packet `CODEX_TASK_S123.md`.

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Check `git log --oneline -1`; the tip must be
the commit carrying `SESSION_HANDOFF_2026-09-03_S122.md` or later. **1,973 tests green.**

Read `SESSION_HANDOFF_2026-09-03_S122.md` section 0, then this file. Nothing else before you start.

---

## ITEM ZERO - THE ONE FACT THAT DECIDES THIS SESSION

**Two full sessions of wiring have landed and not one run has been fed by the wired code.**

S121 wired the causal stream, the crosswalk, the output ledgers and the clocks. S122 wired
per-record `raw_actions` onto the member row, the availability stamp on every lifecycle row,
`activity_since` on event anchors with the fixed windows retired, change points on by default,
the crosswalk computing evidence from what was actually delivered, the A_MEMORY seed, the
knowledge delivery receipt, the sealed-absence proof, the output ledgers' read-back and handoff
trio, and the canonical launch workflow.

**The only feeding that has happened ran the S121 CODE against ledgers written by PRE-CENSUS
code.** Run 33630348943's ledgers predate the field census, `raw_actions`, the stamp and the
retired windows. So every number in `FRANKIE_FEED_RECORD_SUNDAY_33630348943_20260903.md` is a
**before-number**, including F-20's 109,532 withheld lifecycle rows.

**Nothing is blocking the run.** The launch workflow's seal step was executed at the S122 close
and passes: the A_MEMORY seed is merged, the overlay layers bind it, no `external:` identity
remains. Registered **F-31, ESSENTIAL**.

So: the run is the only thing that turns two sessions of wiring from claimed into measured.
**But it is dispatched LAST, not first (D89).** Land item two and item three, then run it once on
finished code and read the result. Nothing is blocking the run when you get there; what is being
avoided is spending it early.

---

## ITEM ONE - THE SUNDAY RE-RUN, IN ORDER (D89: RUN THIS **AFTER** ITEMS TWO AND THREE)

1. **Canary first.** Dispatch `frankie_a_memory_rt_native_launch_20260828.yml` with `mode=canary`.
   The defaults now carry everything (aliasing on, change points on, Sunday `20211003` as the
   only traversed object); a push already runs this, so a dispatch is the deliberate version.
   It exits non-zero on any verdict but ACCEPTED, so it cannot go green over a refused calculation.
2. **Read the canary's own artifact**, not the summary: verdict, failed gates, sections fed,
   and - the new thing - whether the member rows carry `raw_actions` and every lifecycle row
   carries `emitted_at_recv_ns`.
3. **Full roster, Sunday only**, `mode=full`. It runs on the box over SSM, fire-and-return; watch
   it with `frankie_box_monitor_20260829.yml`. **Starting the box is a spend - that is Greg's
   call, not the session's.** The disk precheck computes from the slice's own record count; the
   ledger will be BIGGER than 10.6 GB now that raw actions are carried (F-30 measured the per-row
   cost - read it before sizing).
4. **Deliver it**: re-dispatch `frankie_ledger_delivery_20260902.yml` pinned to the NEW run id
   (its `ROOT_PREFIX` is now the whole benchmark tree, so an a-memory prefix resolves). Download
   the manifest artifact, then `fetch_frankie_ledgers fetch` into gitignored `data/` - never the
   scratchpad (D87). Disk: the session allowance is finite, so delete the plain and gzipped
   ledgers when the measurements are taken, and say how many bytes were freed.
5. **Measure the four falsifiers that a fresh run finally makes answerable:**
   - F-20: `withheld_no_own_clock` and `withheld_close_occasion` read **zero**.
   - F-30: the field census sees the per-record raw action fields.
   - F-26: no fixed-seconds block on the row; `activity_since` present on its anchors.
   - 4.16: change points fed without a flag.
6. **The crosswalk on the new result, with receipts, gate enforced.** This is the number the whole
   two sessions were for. Sunday read **75 of 75 applicable inputs NOT DELIVERED** before any of
   this. Whatever it reads now is the session's headline, good or bad.

---

## ITEM TWO - THE GATE (F-24) - **THIS IS NOW THE OPENER, NOT ITEM ONE**

Written as "once a run exists"; D89 reverses that. It is done FIRST, on the fixture, and the run
then happens over a gated emitter instead of ahead of one.

`gate_applicable_inputs` still has no production caller, and now everything it needs is merged:
the crosswalk computes status from delivered carriers, the sealed-absence proof exists
(`native_sealed_absence.py`, 14 tests), and the knowledge delivery receipt is produced from the
existing pipeline.

1. Call it from `emit_frankie_spawn.emit` after the arm lookup. A refusal is an `EmitError`
   **naming every offender**. Fix the feeding, never the gate.
2. Wire the knowledge read gate. The seam is already named and pinned `None` by a test so wiring
   it flips a test rather than going unnoticed: `native_staging.KNOWLEDGE_USE_GATE` at `:111`,
   called at `:337-345`. Point it at `validate_knowledge_use`.
3. Honest fixtures. The existing ones cannot prove the gate can pass - an empty census, no
   retention receipts, a one-key legacy row, and a gate test that HAND-SETS DELIVERED. **A fixture
   that passes because a status was assigned is worse than no fixture.** Build it from what
   production actually emits, or better, from the new run.

---

## ITEM THREE - THE THINGS THAT MUST NOT ROT (do these in the same session, they are small)

- **F-35, and it is the S112/S114 shape again.** Four committed documents - the two crosswalk
  renders, the FED render and the feed record - assert `raw_actions` absent and the order-lifecycle
  layers `RECEIPTED_CARRIER_ABSENT`. All false of current code. Codex was RIGHT not to rewrite
  them (they are dated records of what an earlier run delivered), but a frozen record that reads
  as live state is how a closed defect gets re-opened as a finding. **Stamp each with a
  superseded-by line naming the commit that changed the behaviour.** Do not rewrite the bodies.
- **F-34.** The seed's package layer and its proof layer bind the SAME file, so the proof is its
  own subject. Measured by executing the seal step. Either bind a real receipt over the seed or
  declare the collapse deliberately.
- **F-36.** The crosswalk's delivered-ledger census is bounded at 1,024 rows / 64 MB. Declared in
  the evidence detail, which is right - but against a 10.6 GB ledger that is a prefix, and a
  gate refusal must say "absent from the scanned prefix", not "absent".

---

## ITEM FOUR - WHAT IS GREG'S, NOT THE SESSION'S

- **The 4.16 horizon ladder (F-32).** D83 says horizons mature on realized responses, never on a
  ladder. But `HORIZON_SETS` is the response table's architecture - fixed horizons, each with its
  own at-risk denominator, written once, refusing a second write, lateness per reading - read live
  by the launcher and the runner. Retiring it is a REDESIGN of section 4.16. Investigated twice,
  deliberately not attempted twice. **Do not start it without a ruling.**
- **PRIOR (F-33).** `precursor_for` has no producer because no precursor signal exists. The
  candidate module says so in its own docstring: a candidate whose birth is its own detection can
  never be recognised before it, so every recognition is honestly `H+N`. Wiring the callback means
  INVENTING a detector. **`prior_reachable: false` is a true statement, not a defect.** It has now
  been proposed as a build item twice and refuted twice from the same paragraph.
- **The box spend** for the full roster, and **F-28** (removing the retired A-clean overlay).

---

## STANDING RULES THAT BIT THIS SESSION

- **Redirect pytest to a file and read its exit code.** Piping to `tail` hid a failure from
  `set -e` and a red commit was pushed with a test count that had not been verified. Same shape as
  the S113 nonconformance: reporting a verification that did not happen.
- **Search before building, and say so when the brief is wrong.** The S122 task packet asserted
  four crosswalk pins should survive; execution proved all twelve should go. The instruction that
  produced that outcome - *when something in this file turns out to be wrong, say so and do not
  silently work around it* - belongs in every future packet.
- **A test that encodes a defect as its specification will preserve the defect.** Three of the
  five held-back tests assert the exact absence that F-30 fixed.
- **D84 paid for itself twice.** Two personas were killed mid-slice by the rate limit; everything
  committed survived and was pushed, including the A_MEMORY seed, which nothing on the development
  branch knew existed until the close.
- **D87.** Scratchpad and `/tmp` are not used at all. Transient files under gitignored `data/`,
  deleted when done.

---

## STATE, VERIFIED BY EXECUTION AT THE CLOSE

- 1,973 tests / 6,387 subtests green; store check 4/4; docs gate pass; D34 grep clean; the
  hash-locked V4 adapter byte-identical; scratchpad empty.
- The seal step passes: 3 files bound, `FRANKIE_A_MEMORY_SEED_PACKAGE_V1`, no `external:` binding.
- Merged this session: item one's two edits, the canonical A_MEMORY launch workflow, the widened
  delivery root, the outputs-staging trio, the feed record, the clocks and windows slices, the
  A_MEMORY seed and knowledge receipt and sealed-absence proof, Codex's four Item-4 tasks, the
  launcher re-hash, and the delivery fetcher's object digest.
- Closed: F-20, F-23, F-27, F-29, F-30. In progress: F-22, F-25, F-26. New: F-31..F-36.
- Not merged, deliberately: `tests/test_native_layer_crosswalk_s122.py` on
  `persona/s121-wire-knowledge-gates` - the spec for the unbuilt slices.
- Keys do not rotate until the build is done; they are GitHub secrets.
