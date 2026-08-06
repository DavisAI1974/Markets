# S113 TASK 3 - TEST GREG'S HYDRO CARRY - does TVA's curtailed state predict SOCO/SCEG/DUK? If it does, TVA's FORWARD water becomes a forward signal for three BAs that publish none

Self-contained: everything you need is in this file. Registry item A-20.

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

We need the SOURCES for a hydro study, not the study. Specifically, and per item:

1. **USGS gauges.** Site IDs and the exact API call for real-time and daily-value streamflow and gage height on: the Tennessee basin around TVA's Blue Ridge, Nottely and Chatuge; the Toccoa and the Etowah (they drain opposite sides of the Tennessee Valley Divide); the Coosa/Oostanaula at Rome; the upper Chattahoochee; the Savannah headwaters (Tugaloo/Tallulah/Chattooga); the Catawba; the Saluda and Broad. Tell us which have long continuous records and which do not.
2. **TVA.** Does TVA publish observed elevation, predicted elevation and planned generation releases in any MACHINE-READABLE form, or is the Lake Levels site and app the only route? Note that tva.com returns HTTP 403 to automated fetches. TVA is a federal corporate agency and instrumentality of the United States, so if there is no feed, say what the FOIA route looks like and roughly what it costs in time.
3. **USACE.** Which district water-management pages publish daily reservoir elevation, discharge and SPILL for the reservoirs above, and in what format.
4. **Pumped storage per balancing authority.** Nameplate MW of pumped storage vs conventional hydro for TVA, SOCO, DUK, CPLE and SCEG. We need this to compute a dilution factor, because EIA-930 folds pumped storage into the WAT fuel code wherever a BA cannot separate it - and pumped storage follows price, not water. Also: does Rocky Mountain (Oglethorpe 75%, Georgia Power 25%) report inside the SOCO balancing authority? EIA-930 reports by balancing authority, not by ownership.
5. **FERC licence articles.** For Duke Energy Carolinas (Catawba-Wateree, Keowee-Toxaway), Duke Energy Progress, Georgia Power (Wallace Dam is P-2413), Alabama Power (Coosa, Tallapoosa) and Dominion Energy South Carolina (Saluda): the docket numbers, and what the licence actually specifies - target elevation by date, minimum flows, drought contingency plan. This is the part we think nobody has looked at: a licensee's reservoir future is partly a LEGAL CONSTRAINT, dated and binding, whereas TVA's is discretionary.

---

## THE REGISTRY ENTRY, VERBATIM

> THE PRIZE IS HORIZON. TVA is a federal instrumentality and the only one of the four that publishes FORWARD water - predicted elevation and planned generation releases per dam (A-18). SOCO, SCEG and Duke publish nothing comparable forward. So if TVA's curtailed state co-occurs with theirs, TVA's forward reservoir guide becomes a FORWARD hydro signal for three BAs in the highest-gas-share region in the country. That is the whole reason to run the test.
> >
> > NO NEW FEED REQUIRED. Serving WAT (A-16) is two lines and back-fills to 2019-01-01, so the test runs on seven years of daily per-BA hydro we have already paid for, spanning droughts and wet years. Adding the BAs (A-18) is a list edit. This item is analysis, not ingest.
> >
> > THE FORM IS ALREADY RIGHT: Greg stated it as a STATE claim - 'when TVA is curtailed so are those others' - not a level correlation. That is the only form that survives the inverted U (D23/D28), because the same low hydro reading comes from flood spill and from drought drawdown while both produce curtailment. Define the curtailed state per BA off its own distribution; measure P(other curtailed | TVA curtailed) against the base rate; per season, per BA, never pooled.
> >
> > THE CONFOUNDER TO CONTROL FOR, and it is large enough to invert the answer: EIA-930 folds pumped storage into WAT wherever a BA cannot separate it, and pumped storage does not enter a water-curtailed state - it follows price and load shape. Duke's Bad Creek (1,065 MW + a 335 MW uprate) plus Jocassee (710 MW) is about 2,200 MW, comparable to Southern Company's ENTIRE hydro fleet of 2,730 MW across 34 facilities; SCEG's Fairfield is 587 MW against a small conventional fleet; TVA's Raccoon Mountain about 1,700 MW against a large one. So WAT is water-driven in TVA and SOCO and price-driven in DUK and probably SCEG. Expect DILUTION that differs per BA, which is exactly how a coefficient fitted on one BA fails silently on another. Also check whether Rocky Mountain (1,095 MW, Oglethorpe 75%) lands in SOCO's WAT - EIA-930 reports by balancing authority, not by ownership.
> >
> > USE USGS AS THE INDEPENDENT DRIVER. Basin streamflow anomaly from the USGS Water Data APIs is machine-readable, national, and upstream of every utility's operating decision, so it separates 'the water was short' from 'the operator chose to run less'. That is also what distinguishes the inverted U's two tails, which hydro output alone cannot do.
> >
> > SECOND MECHANISM FOUND WHILE CHECKING THE 2007-08 INSTANCE, worth instrumenting in the same pass: in that drought Lake Norman sat less than a foot above the licence minimum for Duke's McGuire NUCLEAR plant. A deep enough water anomaly takes down a stack LEVEL as well as a forcing - hydro and nuclear both, both filling with gas. Links to A-17.
> >
> > SCOPE THE ANSWER PER D31: a failure to clear the base rate refutes the carry FOR THAT CELL AND INSTRUMENT, never 'Southeast hydro does not co-move'.
> >
> > TEST IT DIRECTIONALLY, NOT SYMMETRICALLY - added S112 on Greg's operator testimony that TVA 'just do what they want and the others downstream just have to deal with it'. The structural fact under that is verified and it changes the test: FERC does not regulate federal agency dams, so TVA operates under the TVA Act by its own decision, while Alabama Power, Georgia Power, Duke and Dominion/SCEG all run FERC-licensed projects with guide curves, minimum flows and drought plans written into the licence articles. One party has discretion; four have paperwork.
> >
> > CONSEQUENCE FOR THE MEASUREMENT: shared rainfall predicts SYMMETRIC co-movement with no lead. Discretion-versus-licence predicts an ASYMMETRIC lead-lag - TVA to the others strong, the others to TVA weak. RUN BOTH DIRECTIONS. If they come back equally strong it is common weather, TVA does not lead, and its forward data buys no horizon - which is the honest negative result and is worth as much as the positive. This is the sharpest falsifier the item has and it costs nothing extra.
> >
> > AND CHECK THE OTHER FORWARD ROUTE WHILE HERE, because it inverts the premise: the FERC licence articles are themselves forward and BINDING - target elevations by date, minimum flows, drought contingency plans, filed publicly. Where TVA's future needs a forecast to be trusted, a licensee's future is partly a legal constraint. Never looked at. Georgia Power's Wallace Dam is FERC P-2413; Catawba-Wateree and Rocky Mountain have public relicensing dockets.
> >
> > 'DOWNSTREAM' IS MOSTLY NOT LITERAL - do not build on the word. Different basins, different oceans. The three real channels are: north Georgia, where TVA's Nottely/Chatuge/Blue Ridge reservoirs physically sit in Georgia; the regulatory speed asymmetry above; and the commercial one, which for a gas desk is probably the largest - TVA short on hydro buys and burns into the same regional market, so the shock arrives as tightness whoever's river it was. That third channel is directly measurable the moment A-18 lands: TVA's own gas_mwh IS the transmission channel.
> >
> > RUN IT AT EVENT SCALE, NOT JUST SEASONALLY - the single most important amendment to this item, added S112 on Greg's divide point. VERIFIED GEOGRAPHY: TVA's Blue Ridge and Nottely reservoirs and part of Chatuge are physically IN north Georgia (11,000+ acres, ~250 miles of shoreline). Nottely is in Union County, Chatuge in Towns County - and the Chattahoochee rises near the Union/Towns county line. The Etowah drains the SOUTH side of the Tennessee Valley Divide while the Toccoa (TVA's Blue Ridge) drains the NORTH side, the Etowah running to the Oostanaula at Rome and into the Coosa - Alabama Power's Weiss, Neely Henry, Logan Martin. So one storm total over Fannin/Union/Towns/Lumpkin/Rabun loads TVA on one side and SOCO on the other FROM THE SAME EVENT. Same on the NC escarpment (Transylvania, Jackson, Macon, Clay, Cherokee) against the Savannah and Broad/Saluda headwaters.
> >
> > WHY THAT CHANGES THE TEST: a shared CLIMATE driver co-moves on drought timescales - months - which is nearly useless at a day-ahead-to-two-week horizon. A shared STORM driver co-moves on EVENT timescales, which IS our horizon. Driver variable is therefore basin precipitation and streamflow on the DIVIDE COUNTIES from USGS gauges, free and machine-readable, not a regional drought index. SHARPER FALSIFIER: if co-movement appears only seasonally and vanishes at event scale, the same-rain mechanism is not what drives it and the carry buys no tradeable horizon however good the seasonal number looks.
> >
> > AND IT UPGRADES TVA FROM CORRELATE TO INSTRUMENT. Its north Georgia dams are storage and flood-control structures - Nottely exists to regulate flow at Hiwassee - so they capture the event and hold it, and TVA publishes observed elevation, predicted elevation and planned releases. The same storm's loading of the Chattahoochee, Etowah and Savannah has far less public forward reporting. TVA's published reservoir response is a PUBLISHED GAUGE OF A STORM THAT ALSO LOADED THREE OTHER SYSTEMS - stronger than a fitted percentage.

