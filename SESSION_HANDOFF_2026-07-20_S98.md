# SESSION HANDOFF - S98 (work date 2026-07-20) - the DATA GATE largely CLOSED: desk review -> rewritten gate (A-T), 12 feeds built + wired in one session, brain s100.3, two-coach architecture, AWS consolidation, three S97 concerns closed as MEASURED

Branch: `claude/ng-coach-agent-loop-5ha5bf`, S98 close-out tip (this commit). git = CODE + docs;
S3 = ALL DATA (one bucket, per-prefix manifests, `platform_sync.py list` = the inventory);
`scratchpad/aws.env` = keys (ALL THREE ROTATED this session: AWS pair verified via STS, Databento
verified 29 datasets, REAL EIA key live and verified). Old AWS key deactivation = Greg's console
action, verify done. Future rotations: Greg edits aws.env directly, nothing pastes into chat.

---

## READ ORDER FOR S99

`KICKOFF_2026-07-20_S99.md` -> `research/kalshi/DATA_GATE_S98.md` (THE authoritative build list,
every feed A-T with inline STATUS; gate-closure checklist governs G12/G13) -> the S99 DISCUSSION
PACKET: `research/kalshi/EIA_BALANCE_OPTIONS_S98.md` + `LNG_FEEDGAS_SIZING_S98.md` +
`KALSHI_NG_COVERAGE_S98.md` -> `research/kalshi/knowledge/ng_brain.json` (s100.3).

**ITEM ZERO OF S99 (Greg, load-bearing): the PAID-DATA DISCUSSION happens BEFORE any build.**
The procurement policy (Greg, standing): free-first -> build the free composite -> MEASURE its
coverage per-date with gaps named -> pay ONLY for measured gaps. No subscription on an assumed gap.

---

## SESSION TOTAL

- **The desk review** (20-yr NYMEX/ICE lens): data audit vs institutional desks + usage doctrine +
  ten strategy blindspots. Greg: "rewrite our data plan to your specs" -> `DATA_GATE_S98.md`
  supersedes the S97 gate, organized by regime family (DEMAND / POSITIONING / DELIVERY), feeds A-T,
  explicit gate-closure conditions for G12/G13.
- **Decisions recorded**: TWO-COACH architecture (Kalshi initial primary, NYMEX dailies quickly
  after; one shared signal core, ledgers never pooled; build deep, subset down - never
  shallow-then-retrofit). THE STANDING LOOK-AHEAD = the futures->Kalshi lag (S80 15-sig + S81
  7-20s + S91 gold/silver): ESTABLISHED, never retest, live telemetry only. Modest paid tier on
  the table under the procurement policy. Two-books scoring split effective G12 (day-book primary,
  block lean demoted to regime state).
- **Tier 0 + Tier 1 DONE**: the three S97 feeds wired (calendar-front exposed; the 0122 divergence
  0.093-vs-1.539 asserted in the selftest) + `squeeze_watch` + the information clock. G11
  fingerprints on NG.n.0 (12 sessions, comparability PROVEN by exact reproduction of all five
  recorded instances) -> **the C2 ratio reformulation REFUTED on comparable data** (0120 true
  0.714 vs 0107 false 0.718, near-identical on every arm; the proxy separation was a
  non-comparable-base artifact; 1208 collapsed at 85 legs so the leg-count mechanism dies too).
  C2 KEPT + SCOPED per-instance; the flip confirm completes as C1+C3+C4 on the modern tape class.
  **Brain s100.2 -> s100.3 MERGED on Greg's approval** (backup kept); the rescope's forward test
  rides G12. Record: `C2_RATIO_FINDINGS_S98.md`.
- **TWELVE feeds built and/or wired** (all additive, missing==None never 0, per-feed publication
  mechanics measured, `audit-joins` re-run after every wiring - **0 violations across 8 join
  classes x 101 trade days, all session long**). decision_state: 8 -> **17 blocks**.
- **AWS consolidation (Tier 4, M1-M3 DONE)**: keys rotated; `platform_sync.py` = the one door
  (list/pull/push + manifests + verify); local-only stores pushed; ~15 prefixes manifested. Live
  loop design: us-east-1 co-region, sub-second suffices (the edge's clock is 7-20s), LLM never in
  the hot path, lag telemetry per fire. M4 (collector repoint) + M5 (live box) remain.
- **Three S97 concerns CLOSED AS MEASURED**: #1 revision vintage = ONE EIA event published
  2026-04-23 AFTER the winter (Mountain reclass, levels ~10 Bcf/wk; changes within +-1 except the
  named Sep 4 print +55-vs-+45); #2 regional store = xls-vs-api diff ZERO on all 863 periods;
  #3 C2 = resolved above. #12 curve_regime reads real values.

## THE STRUCTURAL DISCOVERIES (each changes what S99 can honestly claim)

1. **Kalshi had NO NG daily market in the walked winter.** KXNATGASD born 2026-03-27; Jan 1 -
   Feb 27 2026 carried ZERO NG-linked Kalshi markets of any kind. The G7-G11 echo replay is
   STRUCTURALLY IMPOSSIBLE (market-existence gap, not data gap). Feed M runs on the life
   (Mar 30 -> present; store landed, S3 `kalshi/`); dailies SKIP FRIDAYS; **no historical
   orderbook endpoint exists** - candle bid/ask OHLC is the depth ceiling, the live collector's
   10-level books (accruing since 2026-07-12) are the only book source forward.
2. **The free weekly balance died before the winter.** EIA removed the S&P S/D section 2025-10-02;
   era-2 (WNGSR Supplement) carries LSEG narrative deltas only. The vessel line is the one series
   continuous through both eras (squeeze week Jan 28 = winter low 31 vessels/118 Bcf).
3. **THE EIA SWEEP FIND: STEO monthly VINTAGES** - frozen archive workbooks; Table 5a = the
   complete NG balance as-of each monthly release (dry production, PER-BASIN production,
   consumption by sector, trade, inventory), 1-34d stale at decision days, published straight
   through the shutdown. The API is current-vintage-only - the archives are the vintage source.
   JOIN ON RELEASE DATES (workbook Last-Modified leads release 3-6d). All 7 winter vintages parsed.
4. **The cash "daily" spot publishes in WEEKLY BATCHES** with up-to-22-day holiday blackouts - a
   naive T+1 join would have leaked the Jan cash blowout (Jan 23 cash $30.72, basis +25.37) a week
   early. Decision-time-legit, the blowout becomes knowable Jan 30 (+10.77, chg3d +7.29) - ON the
   walk's 17x residual day.
5. **The two positioning books sat at OPPOSITE EXTREMES entering G11**: futures-only MM net at the
   2.83rd 1-yr percentile vs options-implied at the 97.17th. Now a wired state variable.

## WHAT THE 17 decision_state BLOCKS ARE

dow/surprise/curve_regime (legacy) | storage (national) | storage_regional (+salt) |
storage_consensus (per-house survey, the number the market trades) | storage_vintage (as-printed
overlay) | ngwu_balance (free weekly balance, honest staleness + vessel line) | cot (futures +
combined + options-implied) | contract_structure (49 fields, calendar-front) | squeeze_watch |
vol_regime (n0/v0, never mixed) | cash_basis (weekly-batch wall) | flow_calendar (expiry/opex/
bidweek/index-rolls/EIA schedule) | solar (sun clock + day length) | weather (realized proxy) |
weather_forecast (MOS D-1, NOW THROUGH FEB 27 - the G12/G13 blindness gap closed; two builder
traps documented) | model_disagreement (MAV-vs-MET + per-model stability) | holiday (+ the
_information_clock meta key).

## OPEN / CARRIED TO S99

- **Item zero**: the paid-data discussion (packet above). Then builds: T (STEO vintages), A phase 1
  (cycle-level MOS), I (options - REQUIRED for G13), M (lag/fill on the life), Q (EIA-930),
  R (outages - EIA `nuclear-outages` DAILY API route, no NRC scraping), S candidate (as-quoted
  L48), O (news watch, live-forward). Then Tier 3 doctrine proposals (printed -> merged). THEN G12.
- **G12** (Sun Feb 1 - Fri Feb 13): gate-closure checklist in DATA_GATE; roll check via SUBAGENT
  returning date+spread only. **G13** (Feb 15-27) = the squeeze test; carries opex Feb 24 / expiry
  Feb 25 / GSCI roll Feb 6-12 / bidweek Feb 23-27; requires feed I.
- **Ops finding**: subagent completion monitors FIZZLED three times - when an agent goes quiet
  with work-products on disk, verify directly and supersede. Serial wiring stays one hand.
- ICE cheap check: the CFTC disaggregated files may carry ICE Futures US gas contract codes
  (positioning half of the ICE-HH blind spot). Databento carries IFUS/NDEX/IFEU (market half +
  TTF/JKM) - price before pulling; no fundamentals at Databento.
- v0-basis vol backfill (feed B stub) = pass-2-adjacent. Pass 2 + the SECOND refinement round over
  the walked groups (consensus re-characterization, vintage propagation, series re-base) stay
  JOB 4 - do not touch old runs before then (Greg).
- MOS normals mmdd coverage ends ~Jul 20 (fetch-date cap) - extend on a later refresh.
- Feed C's agent left its notes' section 7 pending its fizzled monitor; the orchestrator's direct
  verification (module selftest ALL PASS) supersedes; the notes are otherwise final.

## S3 (RESTORE FROM HERE - `platform_sync.py list` is authoritative)

Bucket `bento-568968024170-us-east-2-an` us-east-2. New/updated prefixes this session (all
manifested + verified): `consensus/`, `storage_vintage/`, `vol_regime/`, `cash_basis/`,
`flow_calendar/`, `solar_calendar/`, `cot_combined/`, `model_disagreement/`, `ngwu/`, `kalshi/`
(178 obj, the family life), `eia/`, `nymex/nymex_curve/`, `weather/nws_temp/`, `weather/mos_asof/`
(101 obj incl. the Feb extension), refreshed `storage_regional/`. Pre-existing unchanged:
`nymex/` tape family, `cot/`, `weather/nws_hourly/`.

## RULES (unchanged)

PER-EVENT, never pool/average as a conclusion; drift is a DESCRIPTOR; general rules only; blind
wall decision-time only (storage strictly-prior, MOS as-of, COT publication-keyed, cash
knowable_from, STEO release-date); one-shot canonical; refine per group, renders PRINTED first;
Sunday-start/Friday-end; refined NEVER overrides blind, promotion on forward evidence; rolls
marked never traded; thin AMPLIFIES delivery DAMPS holds; net-of-fee maker AND taker; git = CODE,
S3 = DATA; NG != WTI; weather forecaster HANDS OFF; provisional-until-live; keys are SECRETS;
no emojis.
