# S135 / S136 — Sep 22 to Oct 3 Current-Frankie Blind + Refine Analysis

Status: **POST-RUN ANALYSIS / HANDOFF ONLY**.  The S135 blind remains immutable.  The S136 refine is
post-reveal learning evidence, not a score and not a holdout.  This document does **not** edit the
brain, schema, specialist roles, `spawn.py`, datapoint universe, or hydration policy.

Branch: `chatgpt/burn-hh-12m-s125`

Blind window: **2025-09-22 through 2025-10-03**

Blind scorecard: `research/kalshi/date_run_outputs/20250922_20251003/scorecard.json`

Post-reveal current-Frankie refine:
`research/kalshi/date_run_outputs/20250922_20251003/refine_s136_current_frankie.json`

## 1. Integrity / interpretation

This is a **learning replay for current Frankie**, not an attempt to recreate September-era Frankie and
not a grade against a historical model state.

For S136 refine:

- current brain served at full capacity;
- current brain version recorded by the refine prep: `s105.9`;
- all **90 canonical plays** available;
- **no historical-date/window redaction** in the refine view;
- later-learned current-brain evidence remains available;
- S135 blind files are SHA-frozen and were **not rerun**;
- target tapes are intentionally visible only in the post-reveal refine;
- hydration remains `REJECTED_NOT_USED`;
- no new datapoint family was added;
- no fixed forecast clock and no fixed point count were introduced;
- refine representation is **one forecast per session, one event-driven P50 path only**.  P25/P75 are
  not part of S136 refine.

The event points in the S136 refine are descriptions of the **revealed market transitions** that explain
what happened.  They are not a clock to be copied into future forecasts.

## 2. Blind headline — useful only as a diagnostic

The frozen S135 blind had:

- 10 sessions;
- 4 directional CALLs and 6 ABSTAINs;
- CALL direction: 2/4;
- endpoint MAE: $646;
- RMSE: $761.2;
- mean signed error: -$186;
- Oct. 3 session-net forecast was **exact: -$680 vs -$680**.

These numbers are recorded for orientation, but the purpose of this run is learning.  The more useful
question is whether Frankie's *reasoning failures are becoming narrower and more identifiable*.

They are.

## 3. What looks materially better

### 3.1 Completed-session sequencing is becoming useful rather than decorative

The cleanest example is Sep. 26 -> A -> Sep. 29.

E's Friday forecast was wrong (+$380 versus -$430), but A did **not** inherit E's failed forecast label.
After Friday was revealed, A explicitly replaced the forecast carry with the realized Friday exit:
large downside, roughly 44% recovery off the low, strong late recovery, and absorbed late selling.  A
handed B only an UP-small bias to test and left the Sunday gap unsigned.  B then called Monday UP
(+460) and the session finished +950.

That is the intended S135 architecture working:

> forecast can be wrong -> completed session replaces forecast state -> A bridges the realized exit ->
> next owner reasons from the new legal state.

Do not teach "Friday recovery means Monday up."  Preserve the sequencing behavior.

### 3.2 The completed-session giveback/exhaustion owner can work when the state is clean

Oct. 2 -> Oct. 3 is the strongest example.

Oct. 2 had a bullish EIA surprise, a large event rally, then a roughly $1.8k reversal from the high and
a close almost on the downside extreme.  E did not use raw Thursday sell flow as the Friday sign owner.
The **paired completed price/shape rejection** owned DOWN.  Blind Oct. 3 was -$680 and actual session net
was exactly -$680.

This is important because it is the opposite of the earlier S131 authority failure: the fast paired
price/shape discriminator owned sign and slow/raw context stayed subordinate.

### 3.3 Frankie is increasingly willing to preserve a non-directional diagnosis instead of forcing sign

Sep. 24 is a good control.  Frankie saw a completed down impulse followed by a strong turn-up but no
clean durable owner and ABSTAINed.  The revealed session traveled almost the entire range both ways
(-$480 to +$500) and finished only +$50.  The conflict diagnosis was more valuable than forcing a side.

Sep. 30 and Oct. 1 also show improved discipline: Frankie carried a small positive center from the
multi-day UP trajectory but refused to widen a weak boundary condition into a high-authority CALL.
The realized direction was UP on both days, but not forcing a CALL from an ambiguous discriminator is
not itself a failure to be "fixed" by hindsight.

### 3.4 D is separating opening knowledge from event knowledge correctly

On Sep. 25 and Oct. 2, D explicitly said the opening forecast could not know the EIA surprise / first
legal post-print state and that the remaining curve should be re-derived after the event became legal.
That distinction is correct and should survive.

The refine confirms why: both EIA days changed information state materially after the release, and Oct.
2 actually changed sign again after the initial event rally.

Do not teach an open-time EIA sign from either day.

## 4. The remaining blind misses are more localized

### Sep. 22 — B ABSTAIN, 0 vs -$1,210

This was not a fabricated wrong CALL.  B correctly refused to invent the weekend gap/sign because the
historical weekend plane was absent.  The revealed session then produced a failed morning recovery,
accepted downside and late buy aggression that failed to repair price.

**Learning use:** live rejection/delivery mechanism after the market begins trading.

**Do not learn:** Mondays are bearish; zero-gap center means flat; missing weekend data should be
synthetically filled.

### Sep. 23 — C CALL DOWN -$520 vs +$610

This is a genuine CALL miss.  C used the completed Sep. 22 near-low close as the
`direction.giveback_exhaustion_boundary` owner, but its own reasoning admitted the state was borderline:
about 14% recovery from the low versus the play's strongest continuation form below roughly 10%.

The revealed Sep. 23 tape initially tested down, then failed at the low, turned sharply up and closed
near the high.  The problem is not lack of data.  The problem is **how much authority a borderline
boundary state receives before current price confirms continuation**.

Candidate to test, not yet a brain rule:

> A state sitting outside the clean continuation band but short of the clean alternation band should
> not become a high-authority CALL without a second independent owner or live confirmation.

This is calibration/authority, not a new bullish rule.

### Sep. 26 — E CALL UP +$380 vs -$430

This is the second clear CALL miss.  E allowed the prior EIA-born `direction.absorption_is_reversal`
subset to own UP even while acknowledging that the broad population is only about 11/22 and the
narrow EIA subset only 4/6.

The revealed Friday tape gave an early upside attempt, then a hard downside delivery to -$980 before a
large late recovery.

The important lesson is not "fade EIA absorption."  It is that a **small, outcome-credited subset with
weak broad support should not receive too much next-session sign authority without current price
confirmation**.

No new play is justified from this one miss.  The brain already records the weak audit.

### Oct. 1 — C ABSTAIN +$60 vs +$1,170

This is the largest remaining central-path magnitude miss.  It is not a wrong directional CALL.  C
recognized the positive two-session chain but kept authority low because prior close-location again
sat between the strongest continuation and alternation bands.

The revealed session survived a deep intraday reset and then re-accelerated to +$1,590 before closing
+$1,170, even while aggregate signed flow was negative.

Two useful observations:

1. continuous **price acceptance/trajectory** was more informative than raw flow;
2. magnitude can still be badly compressed when sign authority is withheld.

Do not convert this into "three up days continue" or "negative flow is bullish."  Test whether the
existing magnitude path can express a large single forecast even when disposition is low-authority.

## 5. The 10%-35% boundary zone is now visible as a real research question

A repeated pattern in this block is the space between the current brain's clean close-location bands:

- strongest continuation: close very near the directional extreme, roughly <10% recovery;
- cleaner alternation/turn: roughly >=35% recovery with a late counter-tick;
- the middle region is ambiguous.

This run gave different outcomes inside that middle:

- Sep. 23 reversed UP after a borderline continuation CALL;
- Sep. 30 continued UP after Frankie ABSTAINed;
- Oct. 1 continued UP strongly after Frankie ABSTAINed.

That mixed result is useful: **do not simply move the threshold.**  The middle really is a conditional
state.  The research question is what second discriminator resolves it, not which direction to assign
to the middle by default.

## 6. Oct. 2 creates a specific EIA falsifier candidate

The Oct. 2 one-minute revealed representation shows approximately:

- positive pre-print run;
- strong positive move immediately through the 10:30 release;
- event extension to roughly +$1,360;
- subsequent full rejection and -$440 session close.

The current brain's `daytype.eia_print_impulse_arbiter` treats the first legal impulse as an important
post-event instrument.  This day is therefore a **candidate falsifier / horizon test**: an initial
positive impulse did not guarantee the full-session sign.

Do **not** change the play from the one-minute resample alone.  Before any brain edit, verify the exact
canonical first-60-second tick window and the play's stated horizon.  If the exact arbiter would have
owned UP for too long, the correction should be about **impulse authority decay / re-derivation after
rejection**, not about predicting this historical reversal.

## 7. Magnitude: still the largest unresolved skill problem

Frankie is increasingly locating the correct *kind* of day while the central forecast can remain too
small when sign authority is low.

Examples:

- Sep. 22: 0 center vs -$1,210 actual;
- Sep. 25: 0 opening center vs +$740 actual;
- Oct. 1: +$60 center vs +$1,170 actual.

This does not mean "make every forecast bigger."  It means **direction authority and expected travel
must remain separable**.  Frankie should be capable of one large event-driven forecast path with low
sign authority when the market setup supports large travel.

This is especially important now that P25/P75 side paths are being removed from the operational
forecast representation.  The single forecast must still express the meaningful expected path rather
than collapsing toward zero merely because the sign is uncertain.

## 8. What Frankie should NOT learn from this run

Do not add any of these:

- Sep. 22 / Mondays are bearish;
- EIA absorption means next day UP or DOWN;
- a 14%, 17%, 24% close-off-extreme value has a fixed next-day sign;
- three consecutive UP sessions imply another UP session;
- negative signed flow while price rises is automatically bullish next day;
- bullish EIA surprises reverse;
- Friday after EIA rejection is bearish;
- any hard-coded forecast time or point count from the revealed refine curves;
- any fitted endpoint from these ten actuals;
- any hydration/backfilled historical state.

## 9. What looks safe to preserve immediately

Without changing the brain yet, preserve these operating behaviors:

1. **Completed prior-session price/shape can supersede the prior forecast.**
2. **A may replace E's failed forecast carry with the realized Friday exit before Monday B.**
3. **Raw D-1 flow does not get to recreate a missing sign owner.**
4. **Slow balance/calendar context remains range/regime context unless a canonical play grants sign.**
5. **A clean completed rejection/near-extreme state can own next-session continuation.**
6. **Borderline boundary states should remain low-authority until resolved; do not fit the middle.**
7. **EIA is a sequence of information states: opening -> print/impulse -> subsequent acceptance or rejection.**
8. **Refine may see the full realized tape and current full brain; future learning replays must not reduce current Frankie merely because the dates are historical.**

## 10. Bottom line

The encouraging change is **not that the headline score suddenly became great**.  It did not.  The
encouraging change is that the architecture is producing more interpretable behavior:

- fewer cases where slow/raw context silently becomes sign;
- correct replacement of failed forecast state with realized completed-session state;
- a successful Friday->A->Monday handoff;
- an exact Oct. 3 call from a clean paired price/shape owner;
- better willingness to ABSTAIN when the actual discriminator is genuinely ambiguous;
- remaining failures concentrated in identifiable authority-calibration and magnitude problems.

That is progress because the next fixes can be narrow.  **Do not broadly rewrite Frankie and do not add
new datapoints from this run.**  Hold brain changes until the separate post-refine issue Greg wants to
address is resolved, then decide which of the above candidates deserves a controlled change.
