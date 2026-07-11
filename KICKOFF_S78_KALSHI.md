# KICKOFF S78 — Kalshi build (drop-in for the new session)

Read this, then `KALSHI_BUILD_SCOPE.md`, then start on Step 1.

## Where we are (end of S77)
The crypto book-swing edge is real but a **fee-floor microstructure signal** capped by capital + a maker-fee
regime we don't control (Hummingbot live check: naive MM ≈ flat). Strategic pivot: **crypto was the proving
ground; Kalshi prediction markets are a better fit** for the stack we already built — news→outcome coupling is
direct/causal on event contracts, it's CFTC-regulated all-50-states with a real API, books are wide-spread /
less-HFT-competed, and Greg's energy/macro/weather domain knowledge is a genuine information edge.

## Branch + docs
- Branch: `claude/book-swing-s77-kraken-meomsh`
- `KALSHI_BUILD_SCOPE.md` — the concrete 4-step plan (this session's deliverable)
- `S77_REVIEW_FOR_CHATGPT.md` — full economics/findings recap
- News pipeline to merge in: `origin/claude/run-pass-14-classifier-nTViL`
  (`news_ingest_rss.py`, `news_coupling_research.py`, `build_news_policy_from_coupling.py`, `NEWS_EVENTS_SCHEMA.md`)

## First actions (in order)
1. `mkdir research/kalshi`; write `kalshi_collector.py` against the public v2 API
   (`https://api.elections.kalshi.com/trade-api/v2`, no auth for market data). Watchlist ~8–15 contracts where
   Greg has edge: EIA petroleum/nat-gas storage, CPI/PCE, FOMC, NFP, NWS temp/hurricane. Same JSONL bin schema
   as the crypto collectors. Run it live a few hours → confirm real depth. **(Cheap gate first.)**
2. Merge the news pipeline files onto this branch.
3. Repoint `news_ingest_rss.py` feeds (EIA/BLS/Fed/NWS/Reuters) + per-contract keyword map. **(Surgical edit.)**
4. Once bins + events accrue: run `news_coupling_research.py` + `early_signal` validation. **(Thesis test.)**

## GREG'S SIDE NOTE TO PICK UP FIRST (S78) — WEATHER via real OD
> "we can probably map the weather better than anyone if we turn the real OD toward it to find the operator."

This is potentially the biggest edge in the whole Kalshi thesis and deserves its own thread, not just a
data-collection footnote. The idea: Kalshi's **weather contracts** (daily high-temp in a city, monthly
temperature, hurricane landfall) are priced by traders running standard NWS/ECMWF forecast models. If the **real
OD engine** (the one that recovered the LIGO inspiral chirp, GPS time-dilation coefficient, QCD running — all
from RAW public data with no physics baked in) is turned on raw weather data to **discover the governing
operator**, we could forecast the settlement variable off a *different, possibly better* model than the crowd —
a genuine edge on the OUTCOME, not the microstructure (so it does NOT get arbed away like a book signal).
- **Data to point OD at:** NOAA/NWS station observations (ASOS/METAR), GHCN-Daily, NOAA GFS/HRRR reanalysis
  grids, buoy + upper-air. All public, all the kind of raw multi-channel time series OD eats.
- **The OD move:** windowed operator extraction on the raw station/grid channels → find the local governing
  operator / lead-lag / regime, the same machinery in `odcore/`. Target: a short-horizon (1–3 day) point or
  distribution forecast for the exact settlement variable a Kalshi contract keys on (e.g. "NYC daily high > 90°F").
- **Validation:** backtest the OD forecast vs (a) the realized settlement and (b) the contract's implied
  probability at the same timestamp — edge = where OD's forecast diverges from the market AND is right.
- **Why us:** OD is domain-agnostic law-discovery from raw data; weather is a data-rich domain with a liquid,
  directly-settleable betting market on the exact variable. That pairing is the whole DavisAI thesis applied to
  a market. Greg wants to bring this up first thing S78.
