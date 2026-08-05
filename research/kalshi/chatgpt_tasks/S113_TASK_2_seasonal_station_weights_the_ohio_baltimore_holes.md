# S113 TASK 2 - Seasonal station weights + the Ohio/Baltimore holes

Self-contained: everything you need is in this file. Registry item M-5.

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

We need LNG FEEDGAS nomination sources. Our lng_feedgas_bcfd field is null and 278 days stale, and Gulf-coast feedgas is the most Henry-Hub-coupled demand there is - Sabine Pass and the Cameron/Calcasieu cluster are close to the delivery point itself.

1. What free sources publish pipeline nomination or scheduled-quantity data for the LNG terminals (interstate pipeline Electronic Bulletin Boards / EBBs are the usual route). Name the pipelines serving each major terminal and where their EBB posts scheduled quantities.
2. Format, update cadence, history depth, and whether scraping is required.
3. Which terminals are covered and which are not - per terminal, not pooled.

---

## THE REGISTRY ENTRY, VERBATIM

> Ohio has NO station at all against PJM being the largest gas-burning BA. S111 research adds the mechanism: gas-weighted degree-day weights are HEATING-derived and wrong in summer; the fix is a seasonal switch to power-weighted CDD off EIA-930 BA gas generation we already ingest. THIS IS ALSO THE TEST THAT DECIDES THE BURN GATE REINSTATEMENT (D31) - its kill argument rested on a summer CDD limb measured on a winter-weighted index.

