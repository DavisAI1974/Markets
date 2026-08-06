# S113 TASK 4 - TRIAGE THE 1,129 UNREAD DATA POINTS - find the ones that should be read and are not

Self-contained: everything you need is in this file. Registry item A-23.

## THE CONTEXT YOU NEED (and only what you need)

We forecast **natural gas** - the Henry Hub price curve - and trade it on Kalshi and NYMEX. One
number is the product: total US gas demand, or more precisely **demand that Henry Hub can see**.

Two things that shape every answer you give us:

**Henry Hub is not a national index.** It is one physical delivery point near Erath, Louisiana, on
Sabine Pipe Line, with roughly nine interstate and three-to-four intrastate interconnects, where the
NYMEX contract is physically deliverable. Every other region prices at a basis differential. So New
England demand can spike Algonquin with little effect at Henry, while Gulf-coast LNG feedgas is the
most tightly coupled demand there is.

**Gas burn is the RESIDUAL of the power stack.** Load, minus wind, minus solar, minus hydro, minus
what nuclear and coal are running. Nuclear and coal are LEVELS that move on outage and retirement
timescales. Wind, solar and hydro are FORCINGS - they are on or off according to weather and water,
not according to load. Gas is the only term that regulates. So anything that removes a forcing
without warning lands on gas, and the clearest instance we have measured: on one day our cooling
forecast was exactly right and gas burn still FELL 4.2 Bcf/d, because wind rose 62%.

We work at a **day-ahead to roughly two-week horizon**. Directional level forecasting on price dies
at 5-7 days; what survives past it is dispersion, the forward calendar, and the revision process. So
anything DATED AND FORWARD - a posted outage schedule, a retirement date, a reservoir operating
guide - is worth more to us than a better nowcast.


## WHAT YOU ALREADY DID FOR US, AND WHAT BECAME OF IT

Read this before starting. You have worked for this desk before and we do not want a
question answered twice.

| our item | what you already delivered |
|---|---|
| A-19 | S112 TASK 4 covered the gas-weighted degree-day CONSTRUCTION and a summer weight replacement. DELIVERED. That is adjacent to this item but NOT the same ask - T4 was about how the index is built and weighted for summer; A-19 is about WHICH STATIONS and which BAs. Narrow the new ask accordingly rather than re-running T4. |
| A-5 | S112 TASK 5 (North American weather regime label). DELIVERED, with Greg, not in the repo. |
| G-4 | S112 TASK 2 (ECMWF ENS + GEFS ensemble MEMBER retrieval) and TASK 3 (ISO day-ahead and 7-day wind, solar and load forecasts). Both DELIVERED. Answers are with Greg and are NOT in the repo - they must be brought in and wired before this item can move. |
| G-5 | S112 TASK 1 (the dipole direction result). DELIVERED, with Greg, not in the repo. |
| M-5 | S112 TASK 6 (LNG feedgas nomination sources). DELIVERED. Answer is with Greg, not in the repo. |

**Where those answers live: with Greg, not in our repository.** They have not been
wired in yet. If a task below touches one of those areas, it says so in the task and asks
only for the part you have not already covered.

## THE RULES ON WHAT YOU SEND BACK

These are not style preferences. Each one is a failure this desk has already paid for.

1. **CITE EVERY CLAIM WITH A FOLLOWABLE LINK.** A source we cannot open is a source we cannot use.
   Prefer the primary publisher (the agency, the exchange, the commission docket) over a summary.
2. **NEVER INVENT A NUMBER, AN ENDPOINT, OR A FIELD NAME.** If you cannot verify it, write "not
   verified" and say what you would need. A plausible-looking endpoint that 404s costs us a session;
   an honest gap costs a sentence. This is the single most important rule here.
3. **SAY WHAT IS FREE AND WHAT IS NOT**, with the specific licence or terms where you can find them.
   Our standing policy is free-first: we pay only for measured gaps.
4. **DISTINGUISH "PUBLISHED" FROM "AVAILABLE OVER AN API."** A federal agency posting a web page is
   published; that is not the same as machine-readable, and conflating them is how a build estimate
   goes wrong by a week. Say which one you found, and if it is scrape-only, say so plainly.
5. **REPORT COVERAGE PER UNIT, NEVER POOLED.** "EIA reports this for every balancing authority" is
   the kind of claim that is true in general and false for the three we need. Check per unit or say
   you did not.
6. **DO NOT FIT ANYTHING.** No thresholds, no weights, no coefficients, no "typically around X".
   We fit against our own measured states or not at all - a number tuned without them is
   hindsight-fitted with zero forward evidence and we would have to discard it.
7. **NO EMOJIS OR SPECIAL SYMBOLS** anywhere in what you return - it goes straight into a repo.
8. **ONE TASK PER CONVERSATION.** The tasks below are independent on purpose.


---

## WHAT WE NEED FROM YOU

This one needs a file we will send with the brief: DATA_POINTS.md, the master list of every data point we hold. 1,129 of 1,717 served fields are read by NOTHING, and we want to know which of them SHOULD be read.

Give a verdict per field, and use exactly these four:
  - SHOULD-BE-READ - and name the mechanism it belongs to and why
  - SUMMARY-ONLY - the block needs a served aggregate, not per-cell reads
  - CORRECTLY-UNREAD - with the reason
  - UNUSABLE-IN-BLIND - it is a price-derived block the blind sees frozen at anchor vintage

Work block by block, worst-unread first; the file ranks them for you. Two things to keep in mind. A large unread count in a HIGH-CARDINALITY block is expected and mostly benign - model_disagreement is a per-station by per-model cross-product and nobody was ever going to write a condition on each cell, so the right question there is whether the right SUMMARY is being served. An unread field in a SMALL block is a much stronger signal, because it was almost certainly built to be consumed. Do NOT propose thresholds or weights - only what should be read and why.

---

## THE REGISTRY ENTRY, VERBATIM

> THE HAYSTACK IS NOW VISIBLE AND SORTED. `DATA_POINTS.md` ranks blocks by unread count, which is where a triage starts, and the ranking immediately separates two very different kinds of unread.
> >
> > HIGH-CARDINALITY BLOCKS where a large unread count is EXPECTED and mostly benign: model_disagreement 357 of 431 unread (a per-station x per-model cross-product - nobody was ever going to write a condition on each cell), freeze_risk 148 of 157, solar 68 of 86. The right question there is not 'read all of them' but 'is the right SUMMARY of this block being served'.
> >
> > SMALL AND MID BLOCKS WHERE UNREAD IS A REAL SIGNAL, and these are where to look first: grid_stack (the stack itself - coal_mwh and nuclear_mwh have zero readers, A-15), weather (six fields, the dominant driver), storage/stor_surprise, nuclear_outages, flow_calendar. A field in a small block was almost certainly built to be consumed.
> >
> > TWO SPECIFIC LEADS ALREADY VISIBLE: ngwu_balance is 70 of 83 unread AND its source is DISCONTINUED (final edition week ending 2026-01-21), so the triage must decide whether to mine what we have before it ages out or drop the block. And three price-derived blocks carry large unread counts (options_surface 49, contract_structure 39, vol_regime 28) where the blind sees them FROZEN at the anchor vintage - so an unread field there may be unread because it is unusable in the blind, which is a different verdict from 'nobody thought of it'.
> >
> > GOOD DELEGATION CANDIDATE (Greg named it): the artifact is self-contained, the judgment is per-field, and the work parallelises cleanly by block. Verdict per field should be one of: SHOULD-BE-READ (with the play or condition it belongs in), SUMMARY-ONLY (the block needs a served aggregate, not per-cell reads), CORRECTLY-UNREAD (with the reason), or UNUSABLE-IN-BLIND.

