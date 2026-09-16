# SESSION HANDOFF - 2026-08-02, S110 (the factory session: G22 refine, G23 blind+refine, TWO merges, the SOP, the dock)

Branch: `claude/kalshi-agents-coordinator-guard-1175nr`. Brain **s103.7 -> s104.0 -> s105.0, 82 plays**.

The longest session of the program. Two full group cycles, two brain merges, the first RETIREMENT in
the system's history, a platform turnaround pass, the paper-trading dock, and - the part that will
matter longest - the plant's operating system: a binding SOP, a decision ledger, an andon board, a QC
checklist, batch records, and reasoning ledgers that are mechanically bound to the decisions they
describe.

## THE HEADLINE NUMBERS

| block | blind | refine r1 | refine r2 |
|---|---|---|---|
| **G22** | 4/10 - sum\|err\| 5,965 - drift -1,815 | **10/10 - 500 - -80** | **10/10 - 330 - +50** |
| **G23** | 5/10 - sum\|err\| 5,920 - drift **+4,900** - survives **83%** | **10/10 - 720** | not run |

**G23's blind is the most one-directional block of the walk** (83% of error survives netting vs
15-45% in every prior block) and **the first to lean UP** (+4,900 against a -3,290 actual cum). That
is not a calibration wobble - it is the S110 merge's centerpiece play pushing the whole panel one way.

## THE RESULT THAT MATTERS MOST: A MERGED PLAY DIED ON ITS OWN FORWARD TEST

`weather.burn_conversion_gate` was merged at the start of the session (brain s104.0) as the G22
proposal's centerpiece, measured at both polarities in one block, with a falsifier written into it:
*"a burn-confirmed CDD add that fails to deliver, in G23+."* G23 was its named forward test. **Four
specialists refuted it independently, on four day-classes, and the author refuted it hardest.**

- **D-0709, the mechanism:** the CDD-add limb is a **CONSTANT** - `d_gw_cdd` at horizon 1 is positive
  **20/20 days across G22+G23**. A limb that never changes sign cannot gate. D then tested and
  **rejected** the obvious repair (the forward integral does not sort direction, ~10/19).
- **E-0710, both polarities, its own play:** re-run against the realized weekend, **both limbs pass**
  and say "flip UP +300..+800" into a **-620** Monday; and the both-ways clause **capped a correct
  DOWN read** to a -150 floor against a **-660** actual. E: *"Not softened - it is my play."*
- **E's mechanism, the session's best sentence:** *the gate reads burn as a numerator with no
  balance-clearing denominator; when the balance loosens at the demand peak, burn confirmation is
  BEARISH information.*
- **C-0715, the cleanest evidence and it is PRE-GRAFT and inside the play's own evidence list:** G22
  0624 and 0625 carry the **identical served burn of 39.3** and delivered **+800 and -60** on
  consecutive sessions. The play cites 0624 and is silent on its twin.

**Retired under a new declared class** (brain s105.0): status `REFUTED_FORWARD_TEST_S110_G23` with
4,225 characters of refuting evidence attached as a new key. The damper limb survives inside the
successor `weather.burn_is_demand_arrival_not_direction`.

**AND THE DISSENT IS RECORDED, because Greg asked for it explicitly.** **C-0707 dissented and was
RIGHT on its point**: read on the gate's own weekday-normalization rule (the blind had confirmed it
off a disqualified holiday-Sunday row) the gate **confirmed and its day delivered +160**. The other
four assembled *"3 clean up-fires, 0 of 3 delivered"* - and **nobody counted 0707**, because per-day
causal isolation means no specialist sees another's instance. **Corrected tally: 1 of 4.** The
retirement stands because it never rested on the tally; the two mechanism arguments survive the
dissent untouched. **Structural lesson merged with it: any tally assembled from independent slices is
systematically incomplete and must be recomputed at the coordinator before merging.**

## THE LIVE STRUCTURAL CLAIM: THE IMPACT-COEFFICIENT COLLAPSE (and it is BLIND-LEGAL)

C-0714 retired the block's first explanation (the GSCI/BCOM roll window) **within the same run**: the
window is a **CONTAINER, NOT A CAUSE**. Mechanism test - if roll supply had been holding price down,
removing it on the last window day would restore impact toward the week-1 median 0.380 (worth
~+$1,400 on that flow); realized **0.053**. *Nothing was released because nothing was held.* A tighter
partition exists on the same data: **0708+0709+0710 = -3,230 = 98% of the block**, the other seven
days **-60 total**.

What replaced it: **`k3` = price change per unit aggressor flow.** After the 0709 liquidity void it
collapses 0.302 -> 0.026 -> 0.018, and week-2 flows of **+3,747 / +6,326 / +1,089 / +1,333** produced
only **+200 / -60 / -20 / +180**. *A void is price discovering where liquidity actually sits; once
found, flow stops moving price.* C-0715 supplies the exact mirror six sessions apart in the same
contract: 0709 = price without flow, 0715 = flow without price - **usd per unit net flow 1.322 vs
0.009, a factor of 147.**

**Corpus-searched (D24): n=6 spanning G20+G23, 5/6 at <= $200 (median 115) against a 30% base rate,
with one counterexample named and not explained away (g20 0605, -1,350).** B-0706 adds an independent
out-of-sample instance in a day-class C never sampled, reached by a **different road** (holiday
thinness, not a void) - and the qualifier that makes it tradeable: **numb compresses the NET 6.5x but
the RANGE only 1.5x. A net-suppressor, not a volatility-suppressor.**

**`k3_prev` is PRE-CUTOFF information - it belongs in the blind's hands.** C's verdict: *"G23's second
week is a magnitude problem misdiagnosed as a direction problem. A better direction rule doesn't fix
that; putting k3_prev in front of the blind does."*

## WHAT ELSE THE REFINE FOUND (all corpus-searched, all in the ledgers)

- **`daytype.eia_print_impulse_arbiter` (D-0716):** on a pre-print UP run >= +300, the **60-second
  impulse** separates continuation from full round-trip **6/6 across five groups** - stable at 30s,
  60s and 120s, **degrading at 300s**, which places the arbiter inside the first two minutes,
  **exactly where the established futures->Kalshi lag says the platform's edge lives.**
- **`tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell` (D-0716):** across **all 70 sessions**,
  same-day buy flow agrees with price **41% -> 29% -> 25% -> 20%** as the threshold rises (monotone;
  8 of 10 extreme days closed down) while the **sell side is flat at 46/43/46/47**, and the **D-1
  version is a coin flip**. It names D's own blind error: it cited 0715's +6,326 - the largest buy
  flow in seven groups - as bullish evidence, reading a same-day bearish tell as a next-day bullish one.
- **`flow.flowless_reprice_is_not_absorption` (E-0710, corrected by E-0717):** 0709's ph2 fell -1,860
  on **-11 net flow across 98,400 lots** - the bid withdrew, nothing was transferred, so the level was
  never tested and got pressed twice more. Separating it from true absorption needs **two axes** (flow
  intensity AND price efficiency): *a withdrawn book continues; an absent book round-trips.*
- **The 0709 decomposition (D-0709):** the print itself was **~5%** of the move (-100 net, reclaimed in
  40 seconds); **59% was pre-print**. An **attribution** error, not a sizing error. A **-1,450-class
  day was derivable**; the last ~600 ran into the **3.00 put wall (42,295 puts)** - readable only
  because the S110 audit fixed `options_surface`'s 10x-off strikes.
- **The cancellation artifact (B-0706):** its blind scored 400 on the day while being wrong on **both**
  components in opposite directions - gap +400 vs **-580** (sign wrong), session +100 vs **+680**.
  **1,560 of component error behind a 400 score: the day number concealed 74% of the failure.** D4
  (never average above and below) applies INSIDE a single day.
- **The chain audit (B-0713):** the walk's cleanest chain execution produced a wrong answer. B's own
  verdict: *"A caveat that does not change the vote is not a caveat"* and *"two verification layers
  delivered a defective instrument with accumulated authority - nobody anywhere asked whether the limbs
  measured the right quantity."* Its rule: executing a handed-down conditional yields a **limb state,
  never a sign**; a declared-weak limb resolves **UNREADABLE, not PASS**; **single ownership does not
  care where the sign came from.**

## THE PLANT (the operating system, all new this session)

- **`agents/RUN_SOP.md` v1.6 - THE SPEC BOOK.** Every station, verbatim spawn templates (AUD-1, BLD-1,
  BLD-2, RFN-1, RFN-2), slots filled by lookup only. **Change control:** nothing runs off-SOP; a gap
  STOPS the line; changes are versioned diffs on Greg's go; deviations are recorded nonconformances.
- **`DECISIONS.md`** - the append-only binding-decision ledger, 27 entries, with the **instance-inline
  rule**: every claim carries its evidence in the same sentence.
- **`plant_status.py`** (andon board) + **`agents/QC_CHECKLIST.md`** (the small-model conformance
  sweep, report-only, 7 items) + **batch records** per group + **inspection certificates**.
- **`decision_trace.py`** - reasoning **bound** to decisions: `decision_id = sha256(group|date|owner|
  number)[:12]`, so an id stops resolving the instant a number changes. `--embed` writes the
  self-contained record (answer beside explanation). **Verified: g22 30 ids, g23 40 ids, 0 unresolved.**
- **Four reasoning ledgers** (G22 blind S109 legacy-declared, G22 refine, G23 blind, G23 refine) -
  every specialist's ACTION beside its REASONING, with corpus state per D24.
- **`PLANT_MAP.md`**, **`KEYS.md`**, `.gitattributes` (the CRLF trap that false-flagged the gold vault).

## THE DOCK (paper trading)

**G0 CLOSED**: `kalshi_auth.py` signs RSA-PSS SHA256; **prod balance read HTTP 200, demo balance read
HTTP 200**. Both key pairs are wired in `scratchpad/kalshi.env` (never in git).
**Built:** `kalshi_paper_ledger.py` (fills/fees/settles on the verified formula, four risk caps, 11/11
selftest **including negative tests that prove each cap fires**), `ng_paper_loop.py` (quotes from the
Kalshi public API - **proven from the session container, no box needed for the paper stage**),
`tropical_feed.py` (the named summer gap, live-smoked), `KALSHI_DOCK_S110.md` (the full endpoint/auth
reference from Greg's doc walk).
**THE ROUTING DECISION:** the margin platform's demo carries 33 perps (WTI yes, **no natural gas**);
the CLASSIC demo carries **KXNATGASD live**. Paper NG runs on the classic demo; the margin/FIX lane is
filed for the live stage.

## OPEN - GREG'S CALLS, IN PRIORITY ORDER

1. **D23 - THE VALUE-REPLACEMENT / SHAPE QUESTION (Greg tomorrow).** *"We can only pay attention to
   SHAPE for forecasting purposes... any time you use it after that, the value has to be replaced."*
   Measured: **24 of 76 plays carried an absolute bar**, and **the plays that failed this session are
   value-keyed ones** (HDD >= 16.4 unreachable; HDD <= 13.5 trivially satisfied; the burn gate's
   CDD-add limb positive 20/20). The disease is sharper than "values do not transfer": **a condition
   that cannot change state carries no information, whatever form it is written in.** Greg also expects
   to **test these changes on a new group.**
2. **D24 - the RETRO-INSTANCE PROGRAM.** A mechanism is n=1 until the corpus is searched; the ledger
   carries the instances WITH context. **Qualified by Greg: past evidence is used WHEN AVAILABLE and a
   finding is NEVER disregarded for lacking it** - three states recorded distinctly (found / searched-
   none / not-searched). Greg's read: **this may be where serious blind improvement comes from**,
   because `k3_prev` and its kin are pre-cutoff and therefore blind-legal.
3. **D25 - THE ORDER OF REASONING (Greg tomorrow).** *"It matters the ORDER of reasoning the agents use.
   There has to be a certain order of steps."* Instance in place: E-0710's top-ranked failure was an
   ordering fault (the burn gate applied as a suppressor BEFORE magnitude was derived); E-0717 is the
   mirror (the stand-down evaluated before the sign was committed, which saved the call).
4. **D26 - the HARNESS SCORING CONVENTION.** The render-day is scored 20:00-to-20:00 against a 17:00
   information clock, so every non-Friday scored day carries the next session's first two hours -
   **exactly 0 on 8/8 Fridays identifies the mechanism**; 32 non-Fridays run 21 neg / 9 pos, median
   -30, sum -1,420; on 0715 it was **-230, the only sign flip in 40 sessions**. Changing it re-defines
   every historical score - Greg's call.
5. **D27 - render continuity: BUILT as announce, not gate.** Root-caused why the lines did not connect
   (path emitted cum-from-prior-close lands one whole gap above the next day; g23 8/10 days, both
   Mondays by exactly +400). SOP v1.6 pins cum-from-OPEN. **No score was affected.** Promoting the
   warning to a hard gate is Greg's call.
6. **Data-plane items:** the **missing MBO book files for g21/g22/g23** (declared by all six
   specialists; the book layer stood down group-wide); **only NGQ26 is staged**, so roll attribution is
   unanswerable without the NGU26 leg; session 0710's tape absent from every slice; `ph_absorb` has no
   magnitude term; no `wind_chg_7d`.
7. **Paper trading G1-G3:** the ledger and loop are built; wiring the coach's daily forecast into
   `paper/forecast_today.json` and standing the collector up as a service are next.

**NONCONFORMANCES RECORDED THIS SESSION (per SOP change control):** NC-1 - a refine directive I wrote
carried a false calendar premise ("first post-roll session"; `flow_calendar` says BCOM day 5 of 5) and
C-0715 caught it. Plus my own D11 violation, caught by the rule itself: I verified the retirement code
**parsed** rather than that it **executed**, and its validation block had silently failed to insert.

**KEYS DO NOT ROTATE DURING THE WALK.**
