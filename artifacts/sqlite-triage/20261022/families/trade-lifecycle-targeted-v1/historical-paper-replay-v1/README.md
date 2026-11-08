# October 18 historical paper replay

The first replay treats two October 18 liquidity findings as working premises. It asks what would have happened if we had acted on each premise at a quote observable after the signal. The same October 18 window motivated both premises, so this is an in-sample diagnostic. Each signal is a separate hypothetical one-unit scenario. Signals can overlap or point in opposite directions. The ledger preserves all of them and supplies no portfolio return or actual fill claim.

## Research status and simulator tests

Keep the **test result** and **research status** separate. Preserve the exact outcome, test conditions, market and instrument, timing assumptions, original source references, and positive, negative, flat, missing and censored cases. A rule that falls short in a tested setting, has mixed evidence, or cannot be scored remains **`NOT_ENOUGH_INFO`** for broader use. The measured result still stands for that test. Retain the original rule and its full evidence when a later variant is tested.

The size-one onset, continuation after a retreat to the previous second level, and earlier falling-size rules all remain **`NOT_ENOUGH_INFO`** for broader use. Their October 18 results, including adverse spread-crossing outcomes, are preserved below and in the original receipts. Missing source data leaves the October 3 comparison open under the same research status, with no scored result.

Marginal ideas may be tested in a separately labeled forward simulator experiment. Before each test, record the environment and instrument, trigger, size, order type, exit, and what would help distinguish a signal issue from an execution or data issue. Retain simulator fills, partial fills, missed fills and outcomes under those conditions. Link each experiment back to its historical evidence so later work can revisit it.

## Included evidence and decision boundaries

The [source projection](../local-liquidity-v1/README.md) preserves all 30,739 original market trades and identifies every known missing view. The replay population is the 22,194 consecutive observed books for instrument 150611, native groups 229201–251394. It also reads the matching transitions, first-ten source references and all original trade links. The rest of the tape, sparse quotes, and the separate exact-action window for trades 118–149 remain evidence for research. Their gaps prevent them from supplying entries or exits for this replay. The first observed book cannot establish a newly thin episode at the left boundary.

The [master list](../../completed-run-source-list.json), [Frankie ledger](../local-liquidity-v1/frankie-local-liquidity-use.json), and [original actions and contradictions](../quote-order-gapfill-v1/checked-lifecycle-findings.json) govern interpretation. Frankie's distinction between intermediate steps and endpoints motivated retaining the first exit from each thin episode. The provisional book-contrarian play has a specific trigger and unavailable inputs here, so the replay leaves it unscored. Families, dipoles, forecasts, rolling flow, external history and later findings never select or score entries in this pass. Original order actions take precedence when available. The unallocated quantities for trades 119 and 134 remain open.

- **Size-one onset.** At the completed group, the current best has one displayed unit and either the best price changed or the prior size at that same touch differed from one. A thin bid calls short and a thin ask calls long. The separate episode trace keeps the first same-side retreat, improvement, recovery at the original price, or right censor. It records whether that change was already visible by the entry.
- **Retreat to the previous second level.** At the completed group, the old best is absent at its absolute price and the new best is the previous second level on that side. A bid retreat calls short and an ask retreat calls long. This is a continuation test after the retreat was observable. The transition audit also retains retreats that skip levels, improvements, and stable quotes with and without displayed-size changes.

Only the signal group's known-by clock and cursor govern when a call can be issued. Entry is the first subsequent completed book whose known-by clock is at least 1,000,000 ns later. The three separately scored exits use the first later completed book at least 1, 5 or 30 seconds after entry. Each row retains the original book line, group, event, receive, known-by and cursor for the signal, entry and observed exits. Long scenarios cross from ask to bid, short scenarios from bid to ask. Gross differences use integer raw prices and include the quoted spread. Fees, extra slippage, latency beyond the assumed 1 ms, queue priority, fill probability and capital allocation are unmodeled. Entry and exit are censored at the window boundary. There is no carried quote across an unobserved interval. Bid/ask movement is also scored at the midpoint as a separate directional measure.

## What the first pass showed

All 708 improvements left the old best visible at its price. All 706 retreats lost the old best, and 698 landed at the previous second level. The other eight landed deeper in the previous book. This resolves displayed level geometry at the saved closes. The original trades and action links stay attached to each transition so the geometry cannot silently become a fill, cancellation or surviving-order story.

The size-one premise produced 1,012 calls. There were 461 retreats, 548 same-price size recoveries and three improvements as the first episode outcomes. In 298 of the 461 retreat cases, the retreat was observable at or before the assumed entry. At one second the midpoint moved in the called direction 377 times, against it 274 times and stayed flat 361 times. After crossing the observed spread, 39 scenarios were positive, 127 flat and 846 negative before fees. This identifies a concrete timing gap even when the old touch really does disappear.

The continuation premise produced 698 calls. At one second the midpoint agreed 228 times, opposed 245 times and was flat 225 times. After the spread, 27 were positive, 53 flat and 618 negative before fees. All longer horizons, contrary outcomes, and window-censored cases are retained in the individual ledger and receipt. The results leave two separate research questions: what evidence distinguishes an imminent retreat from recovery at the same price, and whether that evidence is available early enough to enter before the quote moves.

## Which size-one onsets preceded a retreat?

The follow-up partitions every saved size-one episode by the side, how the one-unit best appeared, and whether the signal group contains an original T. A standing best must stay at the same absolute price while its displayed size falls to one. A different price becoming best with one unit includes both improving and retreating quotes. The exact old/new prices and sizes stay on the individual row. A T counts only if its original trade link points to the same transition and close cursor and its availability clock is at or before the signal. This is group context. It supplies neither an aggressor classification nor a causal explanation for the missing size.

Each outcome below is **by the first eligible entry / after entry**. The first eligible entry still uses the original 1 ms assumption. There were zero censored episodes in this comparison. These counts describe outcomes in the saved window, with all bid and ask cases separate.

| Side | How best became size one | Recorded T in onset group | Episodes | Retreat | Same-price recovery | Improvement |
|---|---|---|---:|---:|---:|---:|
| Ask | New best price | No | 307 | 62 / 42 | 152 / 49 | 2 / 0 |
| Ask | New best price | Yes | 3 | 0 / 1 | 1 / 1 | 0 / 0 |
| Ask | Standing best shrank | No | 123 | 54 / 26 | 19 / 24 | 0 / 0 |
| Ask | Standing best shrank | Yes | 68 | 46 / 8 | 7 / 6 | 0 / 1 |
| Bid | New best price | No | 283 | 39 / 44 | 135 / 65 | 0 / 0 |
| Bid | New best price | Yes | 10 | 2 / 5 | 1 / 2 | 0 / 0 |
| Bid | Standing best shrank | No | 153 | 53 / 29 | 35 / 36 | 0 / 0 |
| Bid | Standing best shrank | Yes | 65 | 42 / 8 | 9 / 6 | 0 / 0 |

When a standing best shrank in a group with a recorded T, the first outcome was a retreat in **54 of 68 ask episodes** and **50 of 65 bid episodes**. Most of those retreats were visible by entry. Among episodes still open at entry in those cells, the ask had **8 retreats, 6 same-price recoveries and 1 improvement**, and the bid had **8 retreats and 6 same-price recoveries**. Without a recorded T, the after-entry comparison goes opposite ways by side for a standing best: **26 retreats versus 24 recoveries** on the ask, and **29 versus 36** on the bid. A new one-unit best without a recorded T more often recovered at that price than retreated on either side. The two new-best-with-T cells have just 3 and 10 episodes.

The two different outcomes can start with the same visible quotes. Trade **10924** is in group **230690**, where the standing bid at 3.154 falls from two units to one. The bid later recovers at the same price at cursor **299890**, after the entry quote at cursor **299877**. Trade **11048** is in group **232857**, where that same standing bid falls from four units to one. It retreats to 3.153 at cursor **302836**, after the entry quote at cursor **302829**. Both onset groups close at **3.154/3.155**. The full onset records, exact clocks, source links and opposing outcomes are saved on comparison lines **70 and 172**.

This comparison is descriptive and in-sample. It does not add a paper rule or estimate a fill. For October 3, use the prior and current best raw prices and fixed-price quantities from adjacent verified group closes to classify the onset. Use the original same-group T rows and their cursors for the tape flag. A gap or left window edge cannot establish a standing onset. Reuse the same entry clock and end definitions, and report the cells separately. No October 3 episode was scored.

[Every size-one comparison](every-size-one-onset-comparison.jsonl.gz) · [Comparison receipt](size-one-onset-comparison-receipt.json)

## What the standing best was doing before it thinned

The path comparison covers all **409 standing-best shrink onsets**. The 603 onsets at a new best price remain in the previous ledger. For each standing onset, read the three immediately preceding completed groups in order. The three quotes must be consecutive and available by the signal clock and cursor. For a size path comparison, all three must show the same absolute best price as the signal. Three equal sizes are flat. A nonincreasing or nondecreasing path with at least one change is falling or building, respectively. Reversing paths are mixed. A prior price change or short history has its own category. Three group closes can span different amounts of time. Their exact clocks are retained, with no fixed-duration interpretation.

The comparison keeps bids and asks separate, and preserves the original T/no-T distinction at the onset group. The first episode outcome and the first eligible paper quote remain exactly as in the original ledger. A later action or observation cannot qualify an earlier group. This pass measures timing and outcomes within the already observed size-one episodes. It makes no change to simulated entries or exits.

- **Falling path with a recorded T at onset.** The ask retreated in **21 of 24** episodes and the bid in **20 of 23**. In both cells, **19** retreats were already visible by the first eligible entry. After entry there were two ask retreats and one bid retreat. The remaining evidence includes three same-price recoveries on each side, with one bid recovery after entry.
- **Falling path without a recorded T at onset.** After entry, the ask had **nine retreats and eight same-price recoveries**, and the bid also had **nine retreats and eight recoveries**. The earlier outcomes remain in the receipt.
- **Flat path as a counterexample.** With a recorded T at onset, the flat-path bid had **six retreats and four recoveries after entry**, compared with one retreat and one recovery for the falling-path bid. On the ask, the flat path had **three retreats and five recoveries after entry**. These small cells do not establish a side-independent entry rule.

The falling path helps describe a fast retreat in this selected sample. Before the onset, we would have known the three earlier books. We would still be waiting to see whether the next group thinned to one or contained a T. The next forward test would have to start at the earlier book and include **every qualifying falling path, including those that never thinned**. Using only these 409 later-confirmed episodes would select on information unavailable at that earlier entry.

For October 3, apply the same three-close definitions to verified adjacent groups and preserve the original clocks, cursors and T rows. A missing interval prevents a fixed-price history from being classified. No October 3 outcomes are available yet.

[Every standing-best history](every-standing-touch-pre-onset-path.jsonl.gz) · [Pre-onset receipt](standing-touch-pre-onset-receipt.json)


## Earlier falling-size replay without requiring a later size-one event

A candidate qualifies when the last three consecutive observed groups have the same best price on that side, displayed sizes are nonincreasing with at least one decline, and the latest size is still greater than one. Take the first qualifying close of each consecutive run on each side. A failed qualification resets the run. The signal group can contain a T, but neither it nor a later T is required. Bid candidates call short and ask candidates call long. All original tape and source evidence stays linked through group and book line. The input signal is limited to the three completed books, with exact original clocks and cursor.

The existing 1 ms entry and 1-, 5- and 30-second exit conventions apply. The first later arrival at size one at the same best price, a change of best price before size one, or window censoring are recorded for interpretation. They do not select entries. This produces **1,438 bid and 1,412 ask calls**. Only **400 bid** and **444 ask** calls reached one unit before the best price changed. The bid improved first in 728 cases and retreated first in 308, with two censored. The ask improved first in 606 and retreated first in 357, with five censored.

At one second, bid-side midpoint direction agreed in 422 calls, opposed in 450 and was flat in 566. Ask-side midpoint direction agreed in 483, opposed in 397 and was flat in 532. Crossing the observed spread gave **62 positive, 159 flat and 1,217 negative** bid scenarios, and **63 positive, 200 flat and 1,149 negative** ask scenarios, before fees. Every longer horizon and censored outcome is retained in the receipt and individual ledger. The side difference at the midpoint and the many improvements before size one both qualify the premise. The saved window remains in-sample and the scenarios can overlap. These results do not establish fills, an executable rule, or a portfolio return.

[Every early candidate and outcome](every-early-falling-touch-signal.jsonl.gz) · [Replay receipt](early-falling-touch-replay-receipt.json)

## Saved classroom and dipole evidence

Git holds the [69 native classroom claims and review](../../dipole-audit-v1/classroom_claim_review_receipt.json), the [separate reproduction of 441 external claims](../../external-classroom-audit-v1/external_classroom_check_receipt.json), and [all 510 original claims](../all-510-frankie-knowledge-claims.json). Reproduction here checks the stored relationship counts and endpoints. The native review retains 225 overlapping flags, including reversals within the chronology, step-versus-endpoint disagreements, sensitivity to precision and missing-group bridges. The [Frankie ledger](../local-liquidity-v1/frankie-local-liquidity-use.json) preserves claim 0, where far-front age and far-queue age ended in opposite directions despite many more same-direction steps. Claim 2 shows the reverse kind of disagreement for far-front age and replenishment. Those claims inform the choice to retain the three actual size observations and their two steps separately from the later quote or paper outcome. Their far-book quantities supply no direct evidence about a touch order's identity or fill.

The [dipole book-clock audit](../../dipole-book-clock-audit-v1/book_clock_audit_receipt.json) compared **54,042 stages**. In every audited stage the producer's book came after the stage's second-bin label. Substituting the strictly past book changed the book in **45,879 stages** and the midpoint in **8,925**. The original and strictly past versions both stay available. Use the exact observation or full-row availability and source cursor, never the bin label as a decision timestamp. The [phase reconstruction](../../dipole-event-phase-audit-v1/event_phase_receipt.json) keeps terminal reversal separate from birth and persistence. In the [checked trade 143 case](../trade-lifecycle-handoff-20261023.md#checked-lifecycle-findings), the first stored opposition was more than 13 seconds after the bid retreat, and the three opposed rolling-flow seconds contained no fresh recorded trade. The terminal pattern can describe later context without being an early entry signal.

The earlier replay uses these as research context and does not use any dipole label for signal selection or scoring. A separate as-of comparison would need the saved instrument and continuity scope plus an exact available clock and cursor. Keep any unmatched, flat, invalid or contradictory observations. The full original master list remains the controlling evidence inventory. For October 3, reuse the same qualifying paths and entry clock once the verified consecutive books are readable, without borrowing October 18's dipole stages or outcomes.

## Fresh flow and dipole availability at the early signal

This pass keeps all **2,850** earlier falling-size signals in their original order. It tries one deliberately strict match. The flow row must describe the immediately preceding completed receive second and match the instrument, known-by clock and input cursor of the signal's completed group. It must also be resolved, reconcile with the original tape count, and contain usable classified source data. A saved row with different coordinates stays linked as a candidate. Missing or conflicting rows stay visible. This comparison neither carries an older row forward nor borrows a later emission. Fresh midpoint-classified net lots, the fresh original print count, and the separate rolling signed lots remain distinct.

The scope supplied **four usable ask matches and four usable bid matches**. For 1,287 ask and 1,335 bid signals no row for the preceding second is saved. For another 121 ask and 99 bid signals a prior-second row is saved but has no exact-close match. Among the eight usable matches, five show nonzero rolling signed lots without a fresh print and two have fresh net and rolling signs opposed. All eight existing one-second spread-crossing outcomes are negative before fees. The midpoint agrees with one call, opposes one and is flat in six. These are results for the strict matched subset of the existing replay. The subset supplies too little evidence to rank fresh flow or rolling flow as a filter.

No saved full dipole path shares an exact signal-close clock and cursor in this population. That finding addresses same-close emissions only. It leaves earlier correctly timed dipole evidence eligible for future research. A separately scoped comparison can consider it once the original row availability, stage semantics, instrument and continuity are established. Stored terminal labels remain attached to their true availability. Neither unmatched flow nor an unmatched dipole supplies a zero, a fresh directional read, or a decision to retire a hypothesis.

The flow/dipole hypothesis remains **`NOT_ENOUGH_INFO`**. It can be revisited in the historical data or as a separately labeled simulator experiment if the environment supplies comparable book and tape timestamps. Preserve the control cases, including rolling flow with no fresh tape and fresh flow opposing its rolling sign. For October 3, apply the same test only if the verified source or an equivalent reconstruction can supply the original clock, cursor, and flow semantics. No October 3 market record was scored.

[Every signal and its source matches](every-early-signal-flow-and-dipole-availability.jsonl.gz) · [Availability receipt](early-signal-flow-and-dipole-availability-receipt.json)

## October 3

The [October 3 handoff](../other-30-day-local-liquidity-readiness-20261107.md) pins a sealed journal and both original raw members. The [journal receipt](https://github.com/DavisAI1974/Markets/blob/c28a4de13263b6354662cd376fecc7733b47a991/ingest_pointers/20231003-gh-36571235912-1.json) establishes session boundaries and group counts. October 3 has no replay outcomes while the original bytes are unavailable. On recovery, use its consecutive group closes and the same definitions, timing, price convention and censoring, with October 3 source coordinates. Keep its results separate from the October 18 rule-development window. Preserve all raw trade and contradictory action evidence when attributing a mechanism.

[Receipt](receipt.json) · [Every window transition classification](every-saved-window-transition-classification.jsonl.gz) · [Every hypothetical signal and outcome](every-paper-signal-and-outcome.jsonl.gz)

Semantic coverage remains **NOT_PASSED** and MLP reproducibility **UNRESOLVED**. The work used saved Git evidence and placed no broker or exchange orders.
