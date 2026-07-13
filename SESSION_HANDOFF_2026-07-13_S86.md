# SESSION HANDOFF — S86 (work date 2026-07-13) — MBP-10 depth + surprise join + the EVENT-STATE MODEL + pre-release volume

Branch: worked on harness branch `claude/kalshi-s86-kickoff-tpk4e9` (rebased onto the s79 trunk at start;
harness cut it from the stale S70 tip again). **All work pushed to the canonical trunk
`claude/kalshi-s79-kickoff-ij8t9o`** (default; collectors auto-push there; pull before push). Data on the
**`data/nymex-ticks`** branch. Commits: `9d44bfc` (MBP-10 depth) -> `dfe3f60` (surprise join) -> `740daad`
(de-editorialize) -> `a36e5bb`..`0bd6272`..`0ee2e9d`..`338a856`..`e6fc09f` (event-state design, built up
message-by-message with Greg) -> `1ec082e` (pre-release volume). Data branch tip `16c3f05`.

## The headline: this session produced a MODEL, not just features

The big output of S86 is **`research/kalshi/EVENT_STATE_DESIGN_S86.md`** — Greg's driver model for reading an
energy release CONDITIONED on prior + anticipated state, built up over a long back-and-forth. READ IT. Core:
- **Events are not independent** — each release STACKS on prior events' lasting effects AND on anticipation
  (traders price the forecast). A lone actual-vs-consensus surprise is blind to both -> why storage-alone
  ran backwards on the S86 CL check.
- **Three pillars paint the picture:** NEWS (anticipation) + STORAGE (buffer) + MARKET CAPACITY (slack).
- **Storage = the physical CONFIRMATION node** ("brings it home"): the other drivers are LATENT/abstract;
  storage is where the fear becomes physical, the trigger that fires on confluence (tight supply +
  geopolitics + a storage miss = nervous traders).
- **Shared drivers, per-market/per-period WEIGHTS** (Greg's load-bearing rule: "same scaffolding, much
  different variable values" per energy type). Weather splits: **NG = temperature/degree-days (demand,
  continuous)**, **CL = adverse weather/hurricanes (supply, episodic)**. Weather is TWO-DIRECTIONAL — it
  caused the storage number (backward) AND the forward forecast modulates how much it matters (a low-storage
  miss into a mild forecast is muted, into a cold one amplified).
- **News in THREE TENSES** (ex-ante anticipation / concurrent-ongoing incl. the persistent Ukraine+Iran
  geopolitical regime / ex-post aftermath = repair-timeline updates that keep re-pricing forward), and
  **weighted by time-to-impact vs the tenor we trade** — Kalshi settles off PROMPT, so near-term news
  dominates, 3-months-out moves the term curve not us. The curve/backwardation double-duties as a MAP of
  where on the horizon risk is priced.
- **The human/emotion factor** (load-bearing + humility): the amplification is emotional, unquantifiable
  directly -> expect overreaction/noise; but **order flow is its measurable FOOTPRINT** and the **HERD RUN**
  is the emotion becoming visible (herd breadth = continuation, whale = scalp — already in the merged
  architecture). Two layers: event-state = how primed; flow/book = emotion observable.
- **News source (Greg):** NYMEX traders read Bloomberg/ICE, but this is NOT critical — what matters is TIMING
  PARITY, and we trade Kalshi (delayed follower) not NYMEX so we are inside the lag; only the rare
  exclusive-scoop case exposes us.
- **Eyeball-validated:** the biggest summer CL swing (06-17, $2,640 on a trivial -3.1 surprise) landed inside
  the **2026 Strait of Hormuz crisis** (US/Israel-Iran war, ~14M bbl/day off, WTI $88-107) — storage was
  noise, the primed geopolitical state carried it. Textbook fit.

## What was BUILT this session (three code deliverables, all leakage-gated, all provisional n=12)

1. **MBP-10 depth** (`databento_backfill.py --schema mbp-10` -> `_write_mbp10_df` -> `data/nymex_mbp10/`;
   `event_move_baseline.py --depth`). 24 windows re-pulled at MBP-10 (~$0.42). Logged per-cell correlation
   of push-book one-sidedness vs run length: **NG -0.17, CL +0.52** (opposite-signed). `DEPTH_RUNLENGTH_FINDINGS_S86.md`.
2. **Surprise join** (`eia_surprise.py` — EIA seasonal-proxy, DEMO_KEY, 12/12 matched; `event_move_baseline.py
   --surprise-file`). Cells split beat/miss x big/small. Logged: NG beat|big (n=3) all-down + fast; CL
   |surprise| NEGATIVELY related to move size (the $2,640 day was a small surprise). `EVENT_SURPRISE_FINDINGS_S86.md`.
3. **Pre-release volume signature** (`pre_release_volume`/`post_release_volume`/`_volume_summary`) — the
   FIRST build off the event-state model, a leakage-safe primed/coiled detector needing NO external feeds.
   **NG: quieter pre-release precedes a bigger move, consistent sign across all 3 cells (Spearman -0.5..-1.0)**;
   CL weak (consistent with CL trading Hormuz not the EIA print in-window). Per-contract normal (same
   scaffold, different values). `PREVOL_FINDINGS_S86.md`.

All findings LOGGED WITHOUT MECHANISM (Greg: don't overstate; time-of-year + prior conditions confound;
Apr-Jul only; no generalization). `event_move_baseline.py --selftest` PASS (move + depth + volume + leakage).

## P3 — the lag join — SCOPED, feasible, NOT yet built (the next task)

Goal: turn the futures-move CEILING into realized-EV = the KALSHI echo net-of-fee vs the futures move, per
hold-time, per cell. **The blocker found: we have NO Kalshi tape overlapping the Apr-Jul futures windows** —
`data/kalshi/` bins are ONE day (2026-07-12), `data/kalshi-bins` branch has no NG/CL history,
`data/kalshi_hist_trades/` is absent (local). **BUT `kalshi_history.py` CAN pull it from Kalshi's public API**
(`/markets?status=settled` enumerates the strike ladder for a past release; `fetch_trades(ticker,min_ts,max_ts)`
pulls the real signed trades; docstring shows ~46 settled WTI events, e.g. `KXWTI-26MAY06`,
`KXNATGASD-26JUN2517`). So P3 =
1. Pull Kalshi historical trades for the 24 release events (kalshi_history.py) -> the Kalshi echo tape.
2. Join: futures move (have, from `event_move_baseline`) vs Kalshi echo move NET-OF-FEE
   (`round_up(0.07*C*P*(1-P))` per taker leg, at maker AND taker), per hold-time (NG ~60s fast scalp; CL
   longer), per cell. Condition on the surprise cell + the coiled/primed gate.
3. Realized-EV per cell -> the go/no-go for the $130 full-year MBP-10 pull.
Also (kickoff): add the daily 5PM-settle tape (KXNATGASD settles EVERY day), not just release Thursdays.

## OPEN / NEXT (priority order)

1. **P3 lag join** (above) — the decision-critical realized-EV; gates the $130 pull.
2. **Backwardation pull** (Greg greenlit, not done) — Databento deferred contracts -> the tightness/curve
   axis + the where-on-the-horizon map. Small cost.
3. **Event-state feeds** as they land: NHC advisory archive (CL adverse-weather, point-in-time,
   reconstructable), OVX (geopolitical-regime market proxy), forward degree-days (NG storage modulator),
   storage %-of-capacity. Wire the axes we HAVE (storage level+surprise, season, coiled detector) into the
   conditioning first so P3 runs stacking-aware.
4. **Full-year MBP-10 pull** ($130, all seasons) — only AFTER P3 shows the echo pays. Widen the pre-window
   (currently 120s) for a better coiled read.
5. Standing: NGDQ6 fix in `pyth_collector.py`; weather forecaster scoring (Greg's spec, hands-off).

## RULES (unchanged): each trade individually / per-cell / distributions not means; NEVER lead with the
deflationary median or say "X failed"; log correlations WITHOUT mechanism (Greg S86); prior-conditions +
seasonality confound everything (Apr-Jul only, no generalization); exclude the settle window; leakage gate
before any backtest; net-of-fee at maker AND taker; zero synthetic; provisional-until-live; NYMEX=canary,
fire on Kalshi; weather forecaster = Greg's spec HANDS OFF; DATABENTO_API_KEY is a secret (needs `db-`
prefix; re-export per session); keep CLAUDE.md + KALSHI_TRADING.md lean.
