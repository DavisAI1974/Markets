# S113 TASK 3 - ISO day-ahead and 7-day wind + solar -> NET LOAD (we serve the LOAD half already; the renewable half is entirely absent)

Self-contained: everything you need is in this file. Registry item G-4.

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

We need FORWARD wind and solar generation forecasts, per balancing authority where possible, with endpoints. Realized wind and solar we already have from EIA-930; without the forward version, net load is uncomputable forward, and net load is what determines gas.

1. ISO day-ahead and 7-day wind and solar forecasts: ERCOT, PJM, MISO, SPP, CAISO, ISO-NE, NYISO - exact endpoints, formats, auth, history depth.
2. The Southeast is not an ISO. Say what forward renewable information exists for SOCO, TVA, DUK, CPLE and SCEG, and if the honest answer is 'almost none publicly', say that - a clear negative is worth as much to us as a source.
3. ECMWF ensemble members went CC-BY on 1 October 2025 and GEFS members are on NOAA open data. For each: how to retrieve MEMBERS (not just the mean), what variables are available, retention, and what a full daily pull would cost in bandwidth and time.

---

## THE REGISTRY ENTRY, VERBATIM

> MEASURED S112 against the served vocabulary, which sharpens this from 'a top gap' to a named half-a-variable: FORWARD load IS served - grid_stack.bas.*.demand_forecast_mwh for all seven BAs, all-modern - and the whole weather_forecast.* family is forward. But wind_mwh and solar_mwh are REALIZED ONLY; there is no forward wind or solar field in any block.
> >
> > So NET LOAD CANNOT BE COMPUTED FORWARD AT ALL - we hold one half of it. Greg, S112: 'wind and solar is just on or off. Not regulating to load there. Solely depended on sun and wind so we have to be tracking those well.' Because nothing in the stack regulates except gas, a renewable miss lands on gas at full size.
> >
> > 0629 is therefore not bad luck but the guaranteed consequence: gw_cdd rose 10.0 -> 14.8 exactly as forecast, burn FELL 4.2 Bcf/d on a 62% wind rise, and no forward instrument existed that could have said so.
> >
> > ALL FREE: ERCOT NP4-742-CD (wind actual+forecast) and NP4-745-CD (solar), SPP Mid-Term Resource Forecast +7d, CAISO OASIS SLD_REN_FCST, PJM Data Miner 2 load_frcstd_7_day plus wind/solar, MISO 168-hour, ISO-NE seven-day. Wrapped by gridstatus. ChatGPT task 3 was commissioned to return the exact endpoints. KNOWN TRAP to carry: behind-the-meter solar is excluded from EIA-930 and is a one-directional growing bias in exactly the daylight hours that matter.

