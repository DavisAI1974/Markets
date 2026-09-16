# NG DAILY/WEEKEND PREDICTORS - OUTSIDE-EYES RESEARCH SWEEP (S102, 2026-07-21)

Commissioned by Greg mid-G14: "spin up a nat gas nymex daily research agent to see what the best
predictors for the dailys are, best ways to call the weekends well... this won't override what
we've done but it may see something that we're missing." Full citations were delivered in-session;
this file records the RANKED DELTAS + lore-worth-testing lists for handoff (e.g. to ChatGPT for
build-ranking). Era caveats and free-vs-paid flags preserved.

## Ranked deltas (inputs/mechanics the program does not carry)
1. ECMWF + AIFS ensembles - went FREE 2025 (entire real-time catalogue; 50-member AI ensemble;
   0.1 deg from 2026; AWS open data). Our weather stack is GFS-family MOS only; weekend gap
   stories are literally GFS-vs-ECMWF divergence. Attacks the standing weekend-gap irreducible.
2. CME NG WEEKLY OPTIONS, Friday AND Monday expiries - the market's own weekend-gap variance
   quote (Fri close of a Mon-expiry straddle = implied weekend gap). Derivable from options
   settles ALREADY IN HOUSE.
3. EIA announcement-day return premium (Prokopczuk/Wese Simen/Wichmann, Energy J 2021): >50% of
   annual NG futures return earned on storage Thursdays; pre-release drift concentrates on
   beat-days; survives costs. Scoring prior for the storage-Thursday class - testable on our year.
4. Friday-attention modulation (Gu/Kurov/Stan, JFM 2026): storage-surprise response -74% when the
   report lands Friday (holiday weeks). Plugs into holiday doctrine.
5. LNG feedgas daily nominations from pipeline EBBs - free-derivable incl WEEKENDS (weekend
   terminal trips = recurring Monday-gap cause invisible to weather). Paid shortcut: WoodMac/Criterion.
6. Lower-48 production nowcast from EBB scheduled receipts - free-derivable; the standard
   "record output" bear-day attribution; freeze-off feed covers temps, not realized flow.
7. Day-ahead wind forecasts (ERCOT/MISO) - forecast W-TX wind now >3x gas price as ERCOT DA
   driver (arXiv 2604.14257); burn-side term orthogonal to HDD/CDD; the shoulder family.
8. Reverse weekend effect: NG Fri returns negative / Mon positive (Hoelscher-Mbanga 2018; spot
   1997-2017 - era transfer risk). Check against the walked year.
9. Coal-to-gas switching band (~$2.00-3.75, ~180 MMcf/d per 10c) - mechanistic price shelves.
10. CPC 6-10/8-14 outlooks release 3-4pm ET daily (post-settle, intra-Globex) - a scheduled
    late-afternoon repricing window to score separately.
11. ECMWF weeklies (46-day, Mon+Thu) - scheduled twice-weekly extended-range events.
12. Pre-release order-flow imbalance predicts EIA surprise direction (Rousse-Sevi) - we have the
    tape; test OFI 60-30min pre-print vs surprise sign.
13. Pre-holiday positive drift (cross-commodity, moderate evidence).
14. NG VRP/skew - 6-MONTH horizon signal, LOW daily value (options lane covers the useful parts).

## Lore worth testing (cheap, on data in house)
- Friday-expiry weekly straddle vs realized Sunday gap (weekend variance mispricing).
- NG-specific Monday gap fill rates conditional on gap size x forecast-delta agreement.
- Sunday 18:00-20:00 drift as leading read on the Monday session.
- Weekend cash package pricing vs the futures gap.
- Storage-beat asymmetry (Prokopczuk conditional) on our Thursday cells.
- Saturday ECMWF run delta pins gap SIGN, Sunday runs set SIZE?
- January GSCI/BCOM rebalance week as its own flow event class.
- Re-check all DOW effects post-2015 (published anomalies are pre-shale/pre-LNG era).

## Negative results (save the effort)
- Crowdsourced storage consensus adds nothing beyond professional surveys (Energy J 2020).
- Published daily ML forecasting: no credible net-of-cost daily direction edge.
- TTF/JKM daily transmission weak while the arb is deep ITM (matters via feedgas events, #5).
