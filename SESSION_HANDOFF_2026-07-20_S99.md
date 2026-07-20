# SESSION HANDOFF - S99 (work date 2026-07-20) - item zero HELD (determination pending), FOUR feeds built+wired in one session (T/R/Q/I; decision_state 21 blocks), the MONDAY STUB corruption found + NG repaired, Kalshi settlement verified from spec, the Pyth free era ends Jul 31, Bento LIVE subscribed

Branch: `claude/ng-coach-agent-loop-5ha5bf`, S99 close-out tip (this commit). git = CODE + docs;
S3 = ALL DATA (`platform_sync.py list` = inventory). Session commits: 0af2871d (T+R), 60d596fb
(Pyth addendum), 94475640 (settlement verify), f8c40270 (Q), f4f82900 (I + ICE codes + live smoke
script), 75bfd9b9 (settle-delta sweep), + this close-out.

## SECURITY - THE FIRST ITEM OF S100 (pending, Greg deferred in-session: "good for the moment")

The LIVE AWS key pair was photographed into chat this session (the IAM "Retrieve access keys"
screen, secret fully legible; ID verified == aws.env). Policy: treat as COMPROMISED. S100 opens
with Greg's console actions: create a new key -> type it DIRECTLY into `scratchpad/aws.env` (never
chat, never a screenshot) -> deactivate the photographed key -> ALSO verify the old S97-era key is
deactivated (still-unverified from S98). Everything ran fine on the exposed-but-live key
meanwhile; nothing else is blocked.

## READ ORDER FOR S100

`KICKOFF_2026-07-20_S100.md` -> this handoff -> `research/kalshi/DATA_GATE_S98.md` (STATUS lines
updated inline) -> `research/kalshi/knowledge/ng_brain.json` (s100.3 - UNCHANGED this session; no
group ran, no brain merge).

## ITEM ZERO - HELD, DETERMINATION PENDING

The paid-data discussion happened (packet presented, costs measured). Recommendation on the
table: DEFER-and-measure (no subscription meets the policy bar today), optional parallel quote
requests (Criterion / East Daley / PipeRiv demo - Greg's action), DECLINE flagships + NGI-for-
history. Greg: "will make a determination after rest" - PENDING. Feed S (as-quoted L48) stays
HELD on that determination per the gate. Nothing was subscribed on the vendor side; no quotes
fired. THE COST PICTURE (measured): everything the gate requires through G12/G13 = ~$5 Databento
usage (feed I actual: $4.67); live NG at go-live = Databento Standard $179/mo - WHICH GREG
SUBSCRIBED at session end (see Bento live below); vendor balance tier = $600-6,000/yr published
floor (PipeRiv only), rest quote-required.

## SESSION TOTAL

- **FOUR FEEDS BUILT + WIRED + AUDITED** (serial, one hand, selftest-pinned; audit-joins re-run
  after every wiring - 0 violations across 12 join classes x 101 days all session):
  - **T `steo_vintage.py`** (S3 `steo_vintage/`): the 7 frozen STEO vintage workbooks, ALL 37
    Table-5a series kept, MEASURED release-date joins (knowable_from = release+1; Last-Modified
    NEVER used - the named trap), column-origin detected per workbook (202101 vs 202201 - the
    parse trap), revision deltas vs prior vintage ride each read (the freeze re-mark lands
    2026-02-11 as +5.95 Bcf/d Jan consumption / -137 Bcf end-Jan inventory - readable mid-G12).
    Selftest 22/22 incl. all sweep value pins. Scope sep25..mar26; apr26+ needs measured dates.
  - **R `nuclear_outages.py`** (S3 `nuclear_outages/`): EIA daily nuclear capacity-out
    2007->present (7,140 days), wall = period+1 strictly-prior, real gaps stay gaps (chg across a
    gap = None), the freeze window's 1.8 -> 3.2 GW jump (Jan 17-18) visible at D+1. EIA-v2
    serializes numerics as STRINGS - generic trap, coerced at store.
  - **Q `grid_stack.py`** (S3 `grid_stack/`): EIA-930 daily per-BA (US48/ERCO/CISO/MISO/PJM/SWPP/
    SOCO) demand + **the BA's own DAY-AHEAD DEMAND FORECAST (type DF - a quiet find, leading
    info republished free)** + gen by fuel + gas/solar shares + labeled US48 burn estimate
    (sweep's method verbatim). Wall = period+2 (measured worst case), Eastern framing. The
    freeze's power-burn ramp est 28.3 -> 41.1 Bcf/d was decision-time-visible across G11's
    build-up. BUILD BUG CAUGHT BY PINS: a 1000x unit slip in the burn estimate died against the
    sweep-pinned values same-day - the pin architecture doing its job.
  - **I `options_surface.py` phase i** (S3 `options_ng/`): **G13 GATE ITEM 6 CLOSED.** GLBX NG
    options definition+statistics, BOTH roots, $4.67 actual, 81 sessions Oct 31-Feb 27, 715,843
    OI pts / 1,124,806 settle pts. Per read: two nearest live months, top-5 OI walls +
    concentrations, P/C totals, OI-weighted strike, per-asset splits, opex clock. Opex anchors
    REPRODUCE flow_calendar's independently verified dates exactly (NGG26 2026-01-27, NGH26
    2026-02-24). SYMBOLOGY TRAP: CME NG options live under ON/LNE roots - "NG.OPT" resolves to
    NOTHING. PULL TRAP: the 4-month statistics range 504s server-side - monthly chunks pass.
  - decision_state 17 -> **21 blocks**; audit-joins 8 -> 12 classes; harness selftest extended
    per feed. Notes docs: `STEO_VINTAGE_NOTES_S99.md`, `NUCLEAR_OUTAGES_NOTES_S99.md` (carries
    the Pyth findings + settlement verification), `GRID_STACK_NOTES_S99.md`,
    `OPTIONS_SURFACE_NOTES_S99.md`.
- **ICE HH POSITIONING: in files we already hold.** The CFTC disaggregated zips carry ICE Futures
  Energy Div gas markets; codes measured: **023391 NAT GAS ICE LD1, 023392 ICE PEN, 0233AG HENRY
  HUB BASIS, 0233AH HENRY HUB INDEX** (+ regional basis). Additive cot_feed extension QUEUED;
  gate doc feed H updated in place. The ICE market-data half stays a Databento IFUS pricing
  question (deferred with cross-market).
- **THE PYTH RECKONING** (Greg's free-canary hunt; full record in NUCLEAR_OUTAGES_NOTES_S99.md):
  (1) Pyth's Henry Hub NGD contract feeds have NEVER PUBLISHED - three independent evidence
  lines (Hermes epoch-0 on all 7; S84's direct sample; our own collector's 8-day zero-accrual
  while WTI/XAU/XAG accrue fat daily files). S84's verdict stands; S91's "never bogus" verified
  catalog existence + ID mapping only. (2) The explorer's NATGAS row = **Commodities.Index.
  NATGAS/USD, real + live + 24/7, but PYTH PRO** (numeric id 3265; Starter $500/mo crypto-only,
  commodities bundles ~$2,500-10,000/mo) - declined. (3) **THE PYTH FREE ERA ENDS 2026-07-31**
  (pyth.network blog "The Pyth Core Upgrade"): ALL Pyth API access keyed from $500/mo after
  Jul 31; hermes.pyth.network redirects at cutover -> `pyth_collector`'s free WTIQ6/XAU/XAG
  accrual DIES ~Jul 31. S100 decision: sunset the collector (close the corpus cleanly) or
  repoint - with Bento live now subscribed the canary side is covered better anyway.
- **KXNATGASD SETTLEMENT VERIFIED FROM THE CONTRACT SPEC** (closes the gate's feed-M verify item
  early): settlement = the 1-min candle CLOSE at 17:00 EDT of the PYTH PER-CONTRACT NGD feed
  (rules_primary names it; NOT the 24/7 index); the underlying **ROLLS FORWARD 5 BUSINESS DAYS
  before the current contract's last trading day** (observed NGDM6 -> NGDN6 -> NGDQ6) - SPEC
  CONSEQUENCE for feed M: near expiry the daily bracket references MONTH 2 while a squeeze lives
  in the expiring front (the calendar-front lesson on the Kalshi leg). Kalshi consumes the NGD
  feeds on Pyth's PAID side; **Kalshi's own `expiration_value` field IS the settle print** - 61
  settled days already in feed L's store; no Pyth sub needed for outcomes.
- **THE SETTLE-DELTA SWEEP** (Greg's ask; `renders/settle_delta_sweep_s99.json`): Kalshi settle
  vs NYMEX tape at 17:00 EDT across the life - **matched days: median |delta| 0.1c (one tick),
  27/36 within 0.2c - the settle source is exchange-faithful.** Every 13-17c "delta" = the two
  5bd roll windows (Apr 21-23, May 19-21) where the quick pass read the expiring front while
  Kalshi had rolled to month 2 - the CALENDAR SPREAD, not oracle error (June's ~4c pair sits at
  the N/Q boundary consistently). Per-NAMED-contract precise pass on roll-window days = feed M.
- **THE MONDAY STUB FIND (the sweep's bycatch - a silent WALK BLOCKER caught):** `nymex_cont`
  Mondays after Jan 26 are ~450-byte stubs. **NG: 22 stubs Feb 2 -> Jun 29 2026, INCLUDING ALL
  FOUR G12/G13-WINDOW MONDAYS (Feb 2/9/16/23)** - G12/G13 scoring would have silently broken.
  **CL: 51 stubs = the ENTIRE YEAR** (S92's fix re-pulled NG <=Jan 26 only; CL never got one).
  **NG REPAIRED THIS SESSION** via `redownload_mondays.py` (self-discovering - finds Monday
  files <5KB; per-Monday 2-day batch, verify >=1MB/10k rows, upload over stub, ~$0.63/Monday
  ~= $14 total): RESULT: launched as a DETACHED OS process at session close (survives the
  session; log `E:\Markets\scratchpad\monday_repull.log`, driver
  `scratchpad/monday_repull_driver.py`) - all 22 found, first batch submitted, sequential
  Databento batch jobs at hours-scale. The driver is SELF-DISCOVERING + IDEMPOTENT (re-scans S3
  for <5KB Mondays each run): S100 verifies via the log and re-runs the driver if any days
  remain. One duplicate Feb-2 job (~$0.63) exists from the stopped in-session run - harmless.
  **CL HELD FOR GREG (S100):** paid re-pull est $130-165, OR free redecode from the still-alive
  year jobs - ALL done-state, **expirations ~Aug 12-14 = the free window CLOSES then.**
  **July 1-18 NG was never pulled at all** (year-pull boundary) - separate small pull, needed
  for feed M's life coverage.
- **BENTO LIVE: SUBSCRIBED** (Greg, session end - Standard $179/mo on the existing key/account).
  The smoke test (`databento_live_smoke.py`, ready) is SAVED FOR S100 per Greg - first item
  after the key rotation. Live usage beyond base bills per-message; first telemetry days size it.
- **Greg's stream, triaged on the spot:** electricity LOADS -> feed Q (built, incl. DF);
  electricity OPTIONS (literal) -> declined (thin/vendor); his 10 AM memory -> the ISO day-ahead
  market cycle (QUEUED: per-ISO deadline verification before it enters information_clock) + a
  non-Thursday 10:00-10:30 ET tape characterization (QUEUED, live-coach material); NGAS/BitMart
  -> real HH tracker (level matches cash 2.83) but 250bps spread / ~$10 depth / $609k daily vol
  = disqualified as canary ($1 leadlag falsification available on request); "can we pull CME" ->
  historical already ours, live = the sub he then took.

## WHAT THE 21 decision_state BLOCKS ARE

dow/surprise/curve_regime | storage | storage_regional | storage_consensus | storage_vintage |
ngwu_balance | **steo_vintage (NEW)** | cot (futures+combined+options-implied) |
contract_structure | squeeze_watch | vol_regime | cash_basis | flow_calendar | solar |
**nuclear_outages (NEW)** | **grid_stack (NEW)** | **options_surface (NEW)** | weather |
weather_forecast | model_disagreement | holiday (+ _information_clock meta).

## GATE-CLOSURE STATUS (honest, per DATA_GATE_S98's checklist)

G12 still requires: **feed A phase 1** (cycle-level MOS - the highest-value item, unbuilt),
**feed E** (freeze-off basin temps - build with/after A), **Tier 3 items 1-5** (propose -> PRINT
to Greg -> merge), and the run-time roll-check subagent. Everything else on the G12 list is done.
G13 additionally required feed I (**DONE + WIRED this session**) and feed M (unbuilt; its
substrate is now healthier: Mondays repaired, settlement mechanics verified, settle-delta
baseline measured; still needs July tape + the per-contract roll-window pass).

## OPS NOTES

- Greg runs auto-approve: HARD PAUSE after any question to him; short turn-breaks between task
  groups (saved to persistent memory as greg-auto-mode-pacing).
- Background tasks RIDE THROUGH user interrupts (the NG re-pull survived two stops) - stop them
  only via TaskStop, and say plainly what a "canary" is before running one.
- The in-app browser pane WEDGED on a JS SPA again (Pyth Terminal; second instance after S98's
  feed-J timeout) - prefer the underlying APIs; ask Greg to read his own screen when he is
  already on the page.
- The selftest-pin architecture (assert against independently recorded values) caught a real
  1000x unit bug same-day. Missing-is-explicit stayed load-bearing (gap-honesty in feed R).

## S3 (platform_sync list is authoritative)

New prefixes this session (all manifested + verified): `steo_vintage/` (8 obj),
`nuclear_outages/` (1), `grid_stack/` (1), `options_ng/` (6 = raw DBN + surface store).
Updated: `nymex/nymex_cont/` (22 NG Monday files replacing stubs, `_mon` dow-named).
Local git data dirs remain untracked by design (S3 is the data plane).

## RULES (unchanged)

PER-EVENT, never pool/average as a conclusion; drift is a DESCRIPTOR; general rules only; blind
wall decision-time only; one-shot canonical; refine per group, renders PRINTED first; Sunday-
start/Friday-end; refined NEVER overrides blind; rolls marked never traded; thin AMPLIFIES
delivery DAMPS holds; net-of-fee maker AND taker; git = CODE, S3 = DATA; NG != WTI; weather
forecaster HANDS OFF; provisional-until-live; keys are SECRETS (see SECURITY above); no emojis.
