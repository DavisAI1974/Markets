# FORECAST-AGENT DESIGN — Greg's spec for the path-forecasting agent (S87)

STATUS: DESIGN SPEC (Greg S87) for the NEXT agent/session to build. Captures the job, the structure, and
the self-improving method for turning our pieces into a per-commodity intraday trade-curve forecast. Pairs
with `PATH_FORECAST_RESEARCH_S87.md` (cited methods) and `EVENT_STATE_DESIGN_S86.md` (the pieces/drivers).
The forecast lives on the NYMEX canary; it is a STACKED hold-length / continuation signal, not gospel.

## The job (Greg)
Turn our pieces into a forecast of the intraday TRADE CURVE (the NYMEX path shape), and use RT-vs-forecast
tracking as the hold-length signal (ride the long legs, cut the chop — fees force selectivity, the forecast
is the selector). The agent OWNS figuring out how the pieces combine; it is not handed weights.

## Structure — score SEPARATELY, never pool across type/location (Greg, load-bearing)
1. **Per COMMODITY TYPE.** Each commodity (CL crude, NG gas) scores and forecasts on its OWN — the pieces
   weight differently per type ("same scaffold, different values", S86). NG storage/degree-days heavy; CL
   geopolitics/backwardation heavy; etc.
2. **Per LOCATION / VARIATION, separately.** If we trade different locations or variants of a commodity
   (WTI vs Brent crude; Henry Hub vs other gas hubs; different delivery points), EACH is scored and
   forecasted on its own — do not assume one variant's weights transfer to another.
   - **The lines are HIGHLY CORRELATED -> decompose common factor + basis (Greg S87).** On the NGI chart
     the hub lines track each other tightly: most of the move is a COMMON FACTOR = the Henry Hub / front-
     month LEVEL every hub shares. So (a) our rich NYMEX Henry Hub forecast CARRIES the correlated hubs —
     forecast the shared level ONCE from the rich tape, don't refit each hub from scratch; and (b) the
     tradeable per-location signal is the DIVERGENCE = the BASIS (regional − Henry Hub), which decouples on
     LOCAL drivers (regional weather, pipeline constraints, congestion — "Henry Hub climbs, Northeast
     slides"). Model each location as LEVEL (common, from the rich data) + BASIS (per-location, conditioned
     on local drivers); the correlation is the baseline and the correlation BREAKDOWNS are where the
     per-location edge lives. (Same idea for crude variants: WTI level + the Brent-WTI / grade spread.)

## The pieces and their correlations (Greg — the agent must DISCOVER these)
Our pieces (from the event-state model + microstructure): news (3 tenses), storage level+surprise, forward
CURVE shape/backwardation, weather (degree-days / adverse), geopolitical regime, season, book imbalance,
flow exhaustion, depth run-length, pre-release/coiled volume, herd breadth.
- **Every piece should correlate with SOMETHING** — price change, or direction, or momentum, or
  exhaustion — and a piece may correlate with MULTIPLE of those at once.
- **Pieces may correlate WITH EACH OTHER** (redundancy / interaction) — the agent must find and handle that
  (don't double-count two pieces that are the same signal; find interactions where two pieces together say
  more than either alone).
- **The correlations DIFFER PER COMMODITY** — the same piece can be a strong signal on CL and weak/opposite
  on NG (S86 already saw this: depth run-length NG -0.17 / CL +0.52; surprise/move opposite-signed). So the
  correlation discovery is per-commodity, never pooled.
- **Conditioned on time-of-year, weather, regime** — score the pieces WITHIN season / weather / regime
  cells, because a piece's weight is state-dependent (a low-storage miss matters more into a cold forecast;
  geopolitics matters more in a primed regime). How those conditions build the forecast is the agent's job.

## The method — learn by BLIND forecast -> compare -> rescore -> sharpen (Greg, the core loop)
1. **Get a DIVERSE sample of past days** (calm, trending, whipsaw, release, geopolitical, each season) from
   the continuous NYMEX library (the year/2-year MBP-10 pull).
2. **GRAPH it and LEARN from it** — an exploratory phase: look at the actual trade curves and how the pieces
   lined up with them, per commodity, before modeling. Build intuition/structure first.
3. **BUILD BLIND** — for held-out days, take in ALL our pieces (that day's state) and forecast, WITHOUT
   looking at the outcome, what the trade curve SHOULD look like (shape, legs, hold-length).
4. **COMPARE to the actual curve** — score the blind forecast against what really happened.
5. **RESCORE and SHARPEN** — update the piece weights / correlations / conditioning from the errors, and
   repeat. A self-supervised skill-sharpening loop: the agent gets better at drawing the expected curve as
   it sees more days. (This is walk-forward forecast-skill learning; the blind step is the leakage guard.)

## Discipline (inherited, non-negotiable)
- Leakage-gated (`odcore/leakage.py`): the blind forecast uses ONLY decision-time-available state; normalize
  on decision-time data only (the common silent leak).
- Per-cell distributions, never a pooled mean; net-of-fee at maker AND taker; exclude the settle window.
- Multiple-testing honesty: many pieces x cells -> use PBO/deflated-Sharpe, report specifications tried.
- The forecast is a HOLD-LENGTH / CONTINUATION overlay on catalyst-justified trades; its payoff is measured
  as a net-of-fee EV DELTA vs a fixed-hold baseline, per cell — not claimed as standalone alpha.
- Weather forecaster stays Greg's spec (HANDS OFF); weather enters here only as a conditioning driver.

## Reference / cross-check data (Greg S87 — coarser than our tick data, but tracks the pieces well)
Bring in external daily reference sources as a CROSS-CHECK / validation anchor and (for gas) the
per-LOCATION structure — NOT as the primary tick forecast (they are daily/midday, far coarser than our
MBP-10 tape). Greg: "not as rich as our data but there's pretty good tracking with these pieces."
- **NGI (Natural Gas Intelligence, naturalgasintel.com)** — daily/weekly/monthly gas price INDEXES at
  200+ hubs/locations back to 1988: Henry Hub + regional avgs (Northeast, SoCal Border, S/N LA, Southeast,
  S TX) + named hubs (Chicago Citygate, Houston Ship Channel, PG&E Citygate, Malin). FERC-approved,
  ICE-powered. Historical Download Tool + a **Daily Datafeed API** (paid; sales@naturalgasintel.com).
  This is the reference for the **per-location gas forecasting** (each hub scored separately) AND a coarse
  daily anchor to validate the forecast against.
- **Free coarse refs:** EIA Henry Hub daily (`eia.gov/dnav/ng`), FRED `DHHNGSP`; EIA WTI/Brent for crude.
- DISCIPLINE: reference data is coarser and point-in-time-sensitive — use it for cross-check / validation /
  conditioning and the locational map, never as the tick-level forecast; a published-after-the-fact index
  leaks if used as a same-day feature (leakage-gate it like everything else). The agent should survey for
  the crude-side locational/reference equivalents the same way.

## What it builds on / where it plugs in
- **Analog library / training corpus** = the continuous NYMEX MBP-10 pull (year now, 2-year on AWS later).
  Both the path curves AND the microstructure pieces come off that one feed.
- **The pieces** = `EVENT_STATE_DESIGN_S86.md` (drivers) + the odcore flow/exhaustion tools + the S86 depth/
  surprise/coiled reads + the forward-curve reader (to build).
- **The methods** = `PATH_FORECAST_RESEARCH_S87.md` (bucket-continuation baseline first, then event-time
  anchor + residual-z/shape-corr tracking, GBT continuation classifier, rolling FPCA, HMM chop gate).
- **The application** = the RT-vs-forecast tracking error becomes the hold-length modulator in `lag_join.py`.
- **The workflow** (to build; noted top of `KALSHI_TRADING.md`) = score+load tomorrow's forecast by 5PM the
  day before, recalc in the morning, re-match mid-session if RT stops tracking.
