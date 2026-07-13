# EVENT-STATE / DRIVER-STACK DESIGN — sketch (S86, Greg's model)

STATUS: DESIGN SKETCH for review, not built. Captures the driver model Greg laid out S86 so the event-move
/ lag work reads each release CONDITIONED on prior + anticipated state instead of in isolation. No claims;
this is the schema the full-year data will be tested against.

## The principle (load-bearing, Greg)

Events are NOT independent. Each release/shock lands on a market state carrying prior events' LASTING
EFFECTS, and the reaction STACKS on that state. Traders also price ANTICIPATION — a *forecasted* hurricane
moves crude before landfall, a forecasted cold snap moves gas before the degree-day print — so the state is
FORWARD-looking, not only accumulated-past. A lone actual-vs-consensus surprise is blind to both. That is
why storage-alone ran backwards on the S86 CL check (06-17: $2,640 move on a -3.1 Mbbl small surprise; the
biggest storage surprises made the smallest moves).

## The read: three pillars paint the picture (Greg)

**News (anticipation) + Storage (buffer) + Market capacity (slack)** together = the conditioned read.

1. **NEWS / ANTICIPATION** — forward-looking shocks priced ahead: forecasted hurricanes (NHC cone/outlook),
   weather outlooks, geopolitics. STRICTLY point-in-time / pre-event (leakage: only what was public before
   the event). `news_ingest_rss.py` already tags EIA/Fed/**NHC** feeds — the live spine.
2. **STORAGE** — where the buffer sits: level vs 5-yr normal + the weekly SURPRISE (actual vs consensus /
   seasonal proxy). One piece, not the read (`eia_surprise.py` supplies actual/level; `prev_level` is the
   level hook).
3. **MARKET CAPACITY** — the system's slack / ability to ABSORB a shock; low slack = primed = small shock
   -> big move. Candidate measures (TO CONFIRM the framing):
   - storage as **% of working capacity** (how full/empty vs the max — distinct from vs-normal),
   - **refinery / production utilization + spare capacity** (how much room to respond),
   - **backwardation** (front-vs-deferred calendar spread) = the market's own PRICE-based tightness read
     (the cheap first proxy; Databento deferred contracts).

## Shared drivers, per-market / per-period WEIGHTS (Greg)

One driver schema; each energy market weights the drivers differently and has different peak-effect PERIODS.
The clearest split is inside WEATHER — same driver, opposite mechanism per market:

- **NG weather = TEMPERATURE (degree-days)** -> DEMAND, continuous/seasonal. Peak: winter heating + summer
  power-burn (the double hump). Upstream of the storage number.
- **CL weather = ADVERSE events (hurricanes)** -> SUPPLY disruption (Gulf platforms/refineries offline),
  episodic. Peak: summer (driving demand + hurricane supply risk).

| driver | NG (KXNATGASD) — weight / period / feed | CL (KXWTI) — weight / period / feed |
|--------|------------------------------------------|--------------------------------------|
| Weather | temperature / degree-days; heavy in winter+summer; NOAA/degree-days | adverse weather / hurricanes -> Gulf shut-in; heavy in summer; NHC + shut-in reports |
| Storage | level vs normal + surprise; heaviest driver, withdrawal season; EIA | level vs normal + surprise; weak on the big moves here; EIA |
| Market capacity | storage %-full, pipeline; winter tightness | backwardation, refinery util, spare capacity; summer squeezes; Databento deferreds |
| News/anticipation | cold-snap outlooks; pre-print; RSS/NHC | forecasted hurricanes, geopolitics; pre-event; RSS/NHC |
| Season/demand cycle | double-humped (HDD/CDD discovery) | driving season | 
| The surprise | big builds move it (S86: beat|big fast down) | weak / anti on big moves (S86) |
| Running memory | recent-surprise string + lasting effects | recent-surprise string + lasting effects |

(Weights/periods above are the HYPOTHESIS to test on the full-year data, not established.)

## Data + discipline

- **Point-in-time everything** (leakage gate, mandatory): every state axis at time T uses only info public
  before T. News/forecasts especially — a forecast known after the event leaks the outcome.
- **Historical availability (the sourcing map):**
  - Storage level + surprise: EIA API, deep + free (`eia_surprise.py`). HAVE.
  - Backwardation: Databento deferred contracts, small extra pull. GET (Greg: do it).
  - NHC hurricane anticipation: **NHC keeps dated historical advisory archives** -> reconstructable
    point-in-time for the CL adverse-weather leg. SOURCEABLE.
  - Consensus + general news: RSS is FORWARD-ONLY (same gap as consensus.jsonl) -> accrue forward, or a
    dated news archive for history. GAP to flag.
  - Degree-days: NOAA history, free. HAVE (weather scoreboard).

## How it plugs in

- The event-state becomes the CONDITIONING context for every event. `event_move_baseline` cells gain state
  axes: **capacity-regime x storage-regime x news/anticipation-flag x season** (per market), so the
  surprise->move and depth reads are read CONDITIONED, never pooled across states. The lag join (P3) then
  fires per conditioned cell, and realized-EV is measured per state.
- It is the "running memory": accumulate the state over time (a rolling per-market record) so each new event
  is read in the context the prior events + current forecasts created — the stacking.
- Weather stays Greg's spec (HANDS OFF the forecaster); weather enters here as a DRIVER/conditioning axis
  (degree-days for NG, adverse-weather/NHC for CL), scored through the existing scoreboard, not re-built.

## Open / to confirm before building

1. **"Market capacity" framing** — confirm it = absorptive slack (storage %-full + util/spare + backwardation)
   vs something narrower.
2. **First capacity feed** — backwardation from Databento deferreds is the cheap price-based start; add
   fundamental capacity (%-full, refinery util) after.
3. **Historical news depth** — NHC advisory archive for CL adverse-weather is the high-value, sourceable
   first cut; how far to chase general/geopolitical news history.
4. Sequence vs P3: build the state axes we already HAVE (storage level+surprise, season, degree-days) into
   the conditioning first, then layer capacity + news as feeds land — so P3 can run stacking-aware on the
   axes in hand without waiting for the full set.
