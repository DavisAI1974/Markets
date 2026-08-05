# S113 TASK 4 - THE WEATHER STATION SET IS 16 HAND-SET METROS AND ONE OF THEM COVERS THE ENTIRE SOUTHEAST - and Greg says the metros no longer sit where the load is

Self-contained: everything you need is in this file. Registry item A-19.

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

We need the CANDIDATE STATION SETS that the utilities themselves use, from their public filings - not your opinion on which cities matter.

1. For Duke Energy Carolinas, Duke Energy Progress, Dominion Energy South Carolina, Georgia Power, Alabama Power and TVA: find the load-forecast / weather-normalization methodology in their Integrated Resource Plans or commission filings (NCUC docket E-100, the SC PSC dockets, Georgia PSC, TVA's IRP) and report WHICH WEATHER STATIONS each one weights and how. Duke's IRP states it uses a weighted average of several stations per service territory against a 30-year normal recomputed annually - we want the actual station lists where they are disclosed.
2. Report the EIA-930 balancing-authority boundaries for the Carolinas and the Southeast from EIA's own reference tables - DUK, CPLE, CPLW, SCEG, SC, SOCO, TVA, FPL, FPC, TEC, JEA - so we map stations to RESPONDENTS rather than to company names. We have already made that mistake once in our own registry.
3. Note anything you find about how these utilities handle the fact that Southern load has moved to suburbs and secondary metros - if a filing discusses re-basing station weights, we want it.

---

## THE REGISTRY ENTRY, VERBATIM

> MEASURED against the served set. nws_temp_feed.STATION_WEIGHTS_RAW is 16 stations with hand-set weights, documented in its own header as 'a documented FIRST CUT the agent tunes' (S88). ATL at 0.055 is the ONLY Southeast station in it. Greg's mapping of the five Southeast BAs - SOCO/Atlanta, SCEG/Charleston, TVA/Nashville, FPL/Jacksonville-or-Miami, DUK/Charlotte - resolves to ONE served station for all five, and four of the five have no station at all (CHS, BNA, JAX/MIA, CLT: none served). This is the exact partner defect to A-18: we serve one of five BAs in the highest-gas-share region, and one of five metros.
> >
> > THE SAME FILE ALREADY CARRIES THE KNOWN HOLE ON THE OTHER SIDE: 'the weights are hand-set, unvalidated, and OHIO HAS NO STATION AT ALL against PJM being the largest gas-burning BA' (CLAUDE.md, S109). Greg naming CINCINNATI arrives at that hole from the opposite direction.
> >
> > A BA IS NOT A COMPANY - the CVG nuance, recorded because it changes where the station goes. Greg's 'Duke is Charlotte and Cincinnati' is right about the utility's footprint; EIA-930's DUK respondent is Duke Energy CAROLINAS, while Duke's Ohio/Kentucky utility sits inside PJM. So CVG is a PJM station, not a DUK one - and that is the Ohio hole above. VERIFY the respondent boundaries against EIA's own BA list at build time rather than from the company name; the Carolinas alone split across DUK, CPLE and CPLW.
> >
> > GREG'S MECHANISM FOR WHY ONE METRO IS NOT ENOUGH, and it is a DRIFT not a constant: 'there's been so much growth in the South's suburbs that the major cities aren't really representative of where the majority of their loads are.' The airport ASOS sits at the old core; the residential cooling load that drives Southern summer gas burn has moved to suburbs and exurbs. That makes a hand-set weight a DECAYING quantity - representative when it was set, less so every year, and nothing in the system reports the decay. D23 in a new place: a fixed value standing in for a moving one, and the same shape as the hardcoded holiday table A-14 and plant_calendar were built to end.
> >
> > THE PART THAT MAKES THIS FIXABLE RATHER THAN JUST TRUE - and it has been available since S99 and never used: we now hold each BA's OWN demand AND its OWN day-ahead demand forecast, daily, from EIA-930 (grid_stack.demand_mwh / demand_forecast_mwh). So the station weights no longer have to be argued from population - they can be MEASURED, per BA, by fitting candidate stations' degree-days against that BA's realized demand and keeping what actually explains it. Per-cell, never pooled: a station set that explains ERCO need not explain SOCO.
> >
> > AND IT RE-SCOPES WHAT THE CITY PROXY IS FOR. For a BA we serve, we do not need a city to infer TODAY's load - EIA-930 reports it. The proxy earns its place only FORWARD, where EIA gives one day ahead and the forecast horizon runs further. So: BA demand for the nowcast, stations for the forward driver, weights measured against the BA they claim to represent.
> >
> > DO IT WITH A-18. Adding TVA/DUK/FPL/SCEG to RESPONDENTS without adding BNA/CLT/JAX/CHS gives four BAs whose forward temperature signal is Atlanta; adding the stations without the BAs gives four station series with nothing to validate against.
> >
> > SO IT IS AN AGGREGATE OF SECONDARY CITIES, NOT A METRO (Greg): 'we'd have to aggregate places like Wilmington, NC and cities like that to get a good temp read.' Wilmington is the shape of the problem exactly - coastal NC, inside Duke Energy Progress East (CPLE), not in any metro our 16-station set would ever have reached, and carrying a maritime temperature profile that Charlotte does not.
> >
> > AND THE PHONE CALL IS NOT NEEDED - THEY PUBLISH IT. Greg: 'I used to know people at those places and would be able to ask them but I don't know if they're still there.' The utilities disclose their weather-normalization method in the Integrated Resource Plans they file with the state commissions. Duke Energy's own IRP states it plainly: the load models use a WEIGHTED AVERAGE OF TEMPERATURES FROM SEVERAL WEATHER STATIONS across the service territory, with deliberate inclusion of sites in both states, against a 30-year normal RE-COMPUTED EVERY YEAR. Filed publicly - NCUC docket E-100 for the Carolinas, SC PSC for DEP's South Carolina territory. That is a free, citable, per-utility candidate station list and weighting scheme, and it beats a remembered contact because it is dated and refileable.
> >
> > THE ANNUAL RE-COMPUTE IS THE INDUSTRY ANSWER TO THE DECAY GREG DESCRIBED, and we do not do it. Duke rebases normals yearly; NOAA rolls its 30-year Climate Normals each decade (1991-2020 current). Our weights were set once at S88 and have never been revisited. Whatever station set we land on needs a REBASE CADENCE recorded beside it, or A-19 recurs in three years wearing the same clothes.
> >
> > BUT THEIR LIST IS A PRIOR, NOT THE ANSWER - and this is why the item is tractable without any insider. The utility's set is tuned to ITS retail sales; ours has to explain the BA's gas burn. EIA-930 gives us the BA's own realized demand daily, so any candidate set - theirs, ours, Wilmington-plus-Raleigh-plus-Charlotte - can be scored against the thing it claims to predict. Take the IRP list as the candidate pool because it is free and expert; keep what measures.
> >
> > GREG NAMES THE TWO, AND THEY ARE NOT IN THE BA I LISTED (S112): 'you have to pick up Raleigh and Wilmington in NC because so much of the South's electric load is in the suburbs or smaller metros.' Both sit in CPLE, which A-18 originally omitted - see the correction there. Note what the pair spans: Raleigh is the Triangle, one of the fastest-growing load centres in the country and invisible to any national top-16 metro list; Wilmington is coastal, and a cold-air-damming or coastal-front day can put 15-20F between it and Charlotte. So NC alone needs mountain, Piedmont and coastal-plain stations - one state, three temperature regimes, and our set currently has zero.
> >
> > THE CAROLINAS MINIMUM, per BA: CLT (DUK), RDU and ILM (CPLE), GSO (Piedmont Triad), GSP (upstate SC), CAE (SCEG/Midlands), CHS (SCEG/coastal), AVL (mountains, and the hydro headwaters A-20 cares about). Seven to eight stations for a region the current set covers with none.
> >
> > AND HERE IS THE STRUCTURAL CONSEQUENCE - RE-SIZED HONESTLY FROM M TO L. You cannot APPEND ten Southeast stations to a 16-station national weighted list: renormalise and you dilute every other region, do not renormalise and you double-count the South. THE NATIONAL WEIGHTED-AVERAGE TEMPERATURE IS THE WRONG PRIMITIVE. The primitive should be PER-BA degree days - each BA with its own station set - and the national number becomes a DERIVED roll-up weighted by each BA's MEASURED gas burn. That is only possible now because EIA-930 gives us per-BA gas generation, and it replaces the last hand-set weight in the chain with a measured one. Same move as everywhere else this session: stop hand-maintaining a list that the data can compute.
> >
> > WHY THE SOUTH SPECIFICALLY, and it is not just population growth: the Southeast has the highest heat-pump and electric-resistance heating penetration in the country, concentrated in exactly the detached single-family suburban stock Greg is pointing at. So Southern stations drive BOTH peaks - summer cooling AND winter heating - through the electric meter, where a Northeast station drives the winter peak through the gas meter instead. SCOPING NOTE THAT FOLLOWS: below a heat pump's balance point the resistance strips cut in, so Southern winter electric load is sharply CONVEX in the cold tail, not smooth in HDD. A linear degree-day term will systematically under-call the Southern cold extreme, and the utility fills that jump with gas.
> >
> > ROLL-UP WEIGHT SHARPENED BY D35 (S112): I wrote 'weight the national roll-up by each BA's measured gas burn'. Greg's follow-up - 'what does HH really aggregate, is it a generic national price?' - forces the correction. It is not. Henry Hub is ONE physical point near Erath, Louisiana, on Sabine Pipe Line, and everything else trades at a basis differential. So the target is DEMAND HH CAN SEE, and the weight is burn TIMES HH TRANSMISSION. Measure the transmission by regressing HH day-moves on per-BA burn changes; never assert it from a pipeline map. New England burn can move Algonquin without moving HH; Gulf LNG feedgas is the most coupled demand there is.

