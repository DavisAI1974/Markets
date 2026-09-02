# DROP-IN S121 — Frankie A-arm raw-MBO benchmark

**Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Tip `7638659`, 1227 tests green.**

```bash
git fetch origin chatgpt/frankie-raw-mbo-benchmark-20260828
git checkout -B chatgpt/frankie-raw-mbo-benchmark-20260828 origin/chatgpt/frankie-raw-mbo-benchmark-20260828
git log --oneline -1
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests/ -q   # expect 1227 passed
```

Read `SESSION_HANDOFF_2026-09-02_S120.md` **section 0 first**, then this file.

---

## ITEM ZERO — HOW FRANKIE IS RUN. DO NOT RE-LITIGATE THIS.

Unchanged from S120. The principal is an **AGENT SESSION over committed files**. No API — not
OpenAI, not Anthropic, not Bedrock. Committed staged request -> `emit_frankie_spawn.py` renders
by LOOKUP and HALTS on any slot it cannot resolve -> principal writes a committed artifact ->
`validate_principal_execution` binds the two by hash and refuses identical hashes.
`C2C_014` is SUPERSEDED with its API instruction struck through. **Do not re-derive the
architecture from it.**

---

## ITEM ONE — THE CALCS ARE SETTLED. THE OPEN QUESTION IS THE RAW MBO.

Greg, S120, after it was reported back to him as a calculation answer three times:
*"he's supposed to inform us if any of the mbo info can be dropped. you keep reporting about
the calcs and I've said over and over he are keep them all. they aren't the issue."*

D76 settled the calcs and the measurement agrees — all sixteen are **1.78%** of the bytes.
**Do not re-derive that answer. Do not report a calculation verdict as a retention answer.**

**Why the raw-MBO half has never been delivered, measured rather than guessed:**

1. The spawn prompt contains `raw mbo`, `retention`, `drop`, `discard`, `field`, `book_full`
   and `keep` **zero times**.
2. Mission **section 9** lists nine required outputs. None is the raw MBO or what can be
   dropped.
3. **The raw MBO is not in what Frankie receives.** He gets the ~34 MB result; the
   10,616,914,801-byte member ledger stays on the box. His own words: *"None of these are in
   the 34 MB result JSON I received."*

So it was never asked, and it could not have been answered. Both halves need fixing, and the
delivery half is the harder one.

**Frame it per D76: keep-everything is a first-class outcome.** A question shaped as "what can
we drop" pressures the answer toward a casualty and this programme has already paid for that.

---

## ITEM TWO — TWO OF FRANKIE'S THREE PROPOSED SECTIONS WERE NEVER BUILT

The reason is mechanical: **the `open_items` store holds ZERO entries**, so a recommendation
living in prose has nothing counting it. Only (c) shipped — the cross-section agreement gate —
because it was restated in the numbered defect register, which is worked. This is **D36
recurring**, two sessions after S112 made it a rule.

**Register these before building anything, or the next report's recommendations vanish the
same way.**

- **A per-second flow and quote substrate as its own section.** `legacy_per_second_roll20` —
  22,380 rows, 2,028 trades, 474 buy / 488 sell seconds — is the substrate the candidate
  detector and ALL of 4.12 run on, and it is not one of the sixteen: no declaration, no
  stratum, no averaged companion, **no acceptance gate**.
- **A detector-coverage and rejection-accounting section.** The selection function that
  CREATES the population for 4.10/4.11/4.12/4.16 is outside the contract: trailing causal
  quantile 0.85, 600 minimum observations, 900 s warm-up, 45 s refractory, 5 s local radius.
  It searched 6,592 of 17,991 seconds (36.6%), considered 4,462, promoted **91 (2.04%)**,
  rejected 4,371 across five named reasons. **4.11's `detection_share = 1.0` is unfalsifiable
  precisely because the rejected sit outside the contract.**
- Smaller, also unregistered: **no section owns executions.** Trades appear only as
  by-products across three layers.

---

## ITEM THREE — THE NON-REPLACEMENT RULE IS WRITTEN AND UNENFORCED

Greg asked for a rule that averages never replace the exact run. **It already exists,
verbatim**, in the contract preamble: *"Exact evidence is never discarded or replaced by an
average."*

**Do not add it again.** It is honoured in STORAGE and broken in DELIVERY: the exact ledgers
are written, retained, counted and witnessed, then stay on the box while the principal gets
the result JSON. The one check guarding it reads a counter —
`member_rows_written > 0` — which proves rows were written somewhere and cannot prove anyone
read one. Outcome: **16,293 averaged rows read, zero member rows read.**

**What is needed is a gate at the delivery boundary**: either the exact rows reach the
principal, or the run declares in words that they did not and which claims rest on counters.

---

## ITEM FOUR — THE AVERAGED VIEW IS AUTHORIZED ALMOST EVERYWHERE AND PAID OFF ONCE

The contract's per-section `Average decision` lines: **4.1 no**; conditional on 4.3, 4.4, 4.6,
4.15; **unqualified yes on the other eleven**. The run emitted **16,293 averaged rows across
11 sections** on that authorization.

Frankie measured what the dual view actually earned, in 4.7: *"its coequal ratio pair **earned
its keep exactly once in the whole artifact**"* — mean-of-ratios 14.86 vs ratio-of-sums 9.65
behind the touch, 44.01 vs 42.63 at it.

Greg: *"he settled that long ago by only saying one or two would be run both ways!!!! that
should have been in the calc descriptions!"* **Reconcile each section's `Average decision`
against what the dual view has demonstrably earned, with 4.7 as the one proven case.** The
contract is hash-bound into run identity, so it is the one document where this binds.

---

## STATE, AND WHAT IS ALREADY VERIFIED

**Sunday reran on the corrected code and is CONFIRMED** (run 33630348943, `mode=full`, both
reducers on): **57,027 records / 43,569 groups**, identical to the pre-fix run;
**10,924,504,920 ledger bytes**; **191,567 per record**; sink count matching the box's `wc -c`
with delta **+0** on all three ledgers.

- The 14.0 GB projection was **28% high**. **This is not a reduction** — the 246 KiB constant
  came from a 50,001-record canary over the roster's opening and this is a complete session.
  The precheck is conservative, which is the safe direction.
- **Aliasing measured on the real run: 31.0%**, 5,549,093 bytes, ~1.39M tokens (S119 estimated
  33.8% / 1.69M; the rate was close, the total high because rows fell 16,293 -> 13,136 from
  D-12's octave binning).
- **4.16 fired: 88,071 change points, FED_BY_THE_TRAVERSAL.** The lifecycle ledger carrying
  them is 265 MB, **2.4%** of the run.
- The S119 canary was green but ran on `53c4943`, **before all eleven fix commits** — it
  validated the corrected mission, not the corrected code.

**Decisions 77 -> 80.** D78 (a reducer that changes artifact shape is off by default and the
form is declared either way), D79 (Sunday runs in the configuration the remaining days will
use — Greg's, and it overruled the recommendation), D80 (an event-driven emission is triggered
by an event, never the clock, and a firing test is not optional where the fixture opens zero
tracks).

---

## FRANKIE'S ACTUAL OUTPUTS EXIST AND WERE NEVER SURFACED

`principal_runs/33605852433/frankie_principal_findings.json` carries **44 findings** with
claim, evidence, falsifier and confidence basis — D-depths, families, exhaustion, prebirth,
dipole. S120 reported only the assessment document. **Read the findings file, not just the
assessment.** Section 5 of the handoff lists the headline numbers.

Note the scope: that artifact is from run 33605852433, produced **before** the sixteen fixes.
Seven of its zeros were dead measures. **Frankie has not been spawned against the corrected
Sunday artifact.**

---

## STANDING RULES THAT BIT THIS SESSION

- **D60/D76 — the calcs are kept, all of them.** Stop answering the retention question with a
  calculation verdict.
- **D36 — a recommendation with no registry item does not exist.** Zero `open_items` entries
  is the mechanism, not an oversight.
- **A settlement that reaches a report and not the contract does not bind.** Three instances in
  one session: D68's raw-MBO half, the two unbuilt sections, the non-replacement rule.
- **D77 — parallel agents may never touch git state in a shared worktree.**
- **Verify a number before quoting it.** Two of mine were wrong in S120: the ingestion gate is
  **99 entries / hard minimum 90**, not 78 (I summed only the `*_REQUIRED` policies); and
  "skeleton" is not a designed thing — it is undefined shorthand that leaked from the token
  measurement into the spawn prompt.
