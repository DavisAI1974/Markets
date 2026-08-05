# S113 TASK 1 - NUCLEAR PLANNED-OUTAGE SCHEDULE (forward) - agreed TWICE across sessions and never tracked until S112

Self-contained: everything you need is in this file. Registry item A-17.

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

We need the FORWARD nuclear outage schedule sources, with endpoints.

1. NRC daily reactor status: the exact data URL, format, history depth, and whether power level per unit is in it.
2. Where licensees file or post REFUELLING OUTAGE SCHEDULES far enough ahead to be forward information - this is the point of the task. Nuclear refuelling is planned 12-18 months out and clustered in spring and autumn, which makes it the most schedulable event in the power system, and we currently read it only after the fact.
3. ISO forward outage postings: ERCOT NP3-233-CD (168-hour hourly) and PJM frcstd_gen_outages (90 days) - exact endpoints, auth requirements, formats. Whether MISO, SPP, CAISO and the Southeast have equivalents, and if the Southeast does not, say so, because that is where our gap is.
4. Anything equivalent for COAL retirements and additions (EIA-860M) - a retirement is a forward-dated calendar, which is the class we most want.

---

## THE REGISTRY ENTRY, VERBATIM

> WHAT WE HAVE vs WHAT WAS ASKED FOR. Served today: nuclear_outages.{capacity_out_mw, capacity_out_gw, pct_of_fleet_out, chg_1d_mw, chg_7d_mw, age_days} - all REALIZED or current, age 1 day, built as feed R arm 1 at S99. Served nowhere: any FORWARD planned-outage schedule. There is no planned start or end date in any block.
> >
> > WHY THIS ONE STINGS: nuclear refuelling is the MOST SCHEDULABLE EVENT IN THE POWER SYSTEM - planned 12-18 months ahead, publicly posted, clustered in spring and autumn. It is the one supply-side quantity genuinely knowable in advance, and it belongs to the class the horizon research says survives past the 5-7 day weather boundary: the forward calendar, dated by construction, with no horizon limit. We are reading the single most forecastable input backwards.
> >
> > THE TRACKING FAILURE, stated plainly because it is the more important half. This was agreed in conversation at least twice and NEVER BECAME A REGISTRY LINE. Searched S112: 'nuclear' appears in the registry only inside M-6's title (an item about COAL) and in a research briefing's Tier 3 (an item about NON-nuclear thermal). It had no id, no status, and no place on the andon board, so nothing could report it overdue and it surfaced only because Greg remembered.
> >
> > THE MECHANISM GAP IT EXPOSES - D30 one level down: OPEN_ITEMS.json enforces tracking at the ITEM level, but a commitment living inside another item's PROSE is invisible to the count. plant_status can say '40 open items'; it cannot say 'and one thing agreed twice that belongs to no item'. The registry catches items that were entered. It cannot catch a decision that was never entered, and that is exactly what happened here. THE DISCIPLINE THAT WAS MISSING: a thing agreed in conversation becomes a registry line IN THAT SESSION, before the session ends - not when someone remembers.
> >
> > SOURCES, all free: NRC publishes daily reactor status (power level per unit, so an outage is visible as it happens) and licensees file refuelling schedules; ISO planned-outage postings carry forward dates - ERCOT NP3-233-CD is 168-hour hourly, PJM frcstd_gen_outages runs 90 days. Pair with A-15: nuclear_mwh is already served and read by ZERO plays, so a forward schedule with no consumer would repeat the same failure in a new field.

