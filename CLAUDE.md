# CLAUDE.md — DavisAI Markets / Kalshi (Updated 2026-07-20, Session 100)

## AWS KEY — READ THIS BEFORE TOUCHING S3 (S100 standing note; cost us an hour on 2026-07-20)

- THE CURRENT KEY (verified live S100): access key ID `AKIAYI6JDCBVLKYQGLMH`, secret begins
  `txRGHd` (40 chars), account `...4170`, bucket `bento-568968024170-us-east-2-*`. The FULL
  secret is NEVER written in this repo (it is/was PUBLIC; AWS kills keys it finds on public
  GitHub). Full pair lives in: `scratchpad/aws.env` on Greg's box (untracked), and in cloud
  sessions `~/.aws/credentials` + `~/.claude/settings.json` env (both outside the repo).
- THE TRAP THAT BURNED S100's OPENER: Claude Code cloud containers inject PLACEHOLDER env vars
  (`AWS_ACCESS_KEY_ID=proxy-injected...`) which OVERRIDE `~/.aws/credentials` in boto3's
  precedence. Symptom: `InvalidClientTokenId` on a known-good key. Fix: run AWS-touching
  commands via `bash -lc` (login shell sources the profile exports of the real pair), or pass
  credentials explicitly; `~/.claude/settings.json` env carries them for future sessions.
- Session ritual: obtain pair -> `~/.aws/credentials` -> STS get-caller-identity via `bash -lc`
  (print pass/fail + account tail ONLY, never the secret) -> proceed. If STS fails on a
  known-good key, suspect the env-var override FIRST, not the key.

**S100 — THE GATE CLOSED + THE LIVE LOOP'S FIRST BREATH (read
`SESSION_HANDOFF_2026-07-20_S100.md` + `KICKOFF_2026-07-21_S101.md` [G12 = S101's opener, FRESH
session per blind-run hygiene]):** live smoke PASSED (GLBX NG **median 7.7ms** via the box;
container can't reach live gateways); Mondays verified 22/22; July 1-18 pulled ($0, in-sub);
**feeds A-ph1 + E BUILT+WIRED** (cycle-level MOS: the 0118 Jan-24 +8.511 add was PRE-REOPEN
available - the weekend-gap blindness closed; basin freeze-offs: Permian+Haynesville sub-20F
from Jan-24 visible 0122); decision_state 23 blocks / 14 audit classes / 0 violations; ICE HH
positioning wired free (LD1 4.72nd pctile echoes NYMEX 2.83rd); **Tier 3 MERGED -> brain s101.2**
(usage doctrine, flip checklist, evidence registry, day-book PRIMARY scoring split, squeeze
doctrine, Greg's SUPERSESSION single-ownership + blind-run hygiene); **feed M DELIVERED**
(76,594-row lag map: ATM response 42%, delays 110-215s median, spreads 15c->4c - **taker does
NOT clear this regime; MAKER-FIRST**; `TWO_COACH_SPEC_S100.md` printed, approval pending);
determinations: FREE-FIRST standing, CL Mondays = free redecode (~Aug 12-14 window), pyth
sunset by Jul 31 (open). Dashboard session live (`DASHBOARD_HANDOFF_S100.md`). AWS key episode
solved permanently (see AWS KEY section above). **G12 IS GO - from a fresh S101.**
**S100.1 (dashboard session, same day): the READ PLANE is BUILT** - branch
`claude/dashboard-wiring-rgvahe`, `dashboard/` (FastAPI + read-only adapters + the v0.1
prototype wired with REAL/AWAITING/SIMULATED truth badges; 21/22 blocks verified on walk days;
executor lane deliberately last). Cruise-able snapshot artifacts (v0.1.1) + build/refresh notes:
the S100.1 addendum at the top of `DASHBOARD_HANDOFF_S100.md`; generator
`dashboard/make_snapshot.py`.

**S99 — FOUR MORE GATE FEEDS IN ONE SESSION + THE MONDAY REPAIR (read
`SESSION_HANDOFF_2026-07-20_S99.md` [SECURITY block FIRST] + `KICKOFF_2026-07-20_S100.md`):**
Item zero HELD (packet presented, recommendation = defer-and-measure + optional quotes; Greg
decides after rest — feed S gated on it). **Feeds T (STEO vintages) / R arm 1 (nuclear outages) /
Q (EIA-930 loads + day-ahead demand forecast + fuel mix) / I phase i (NG options OI pin map —
G13 GATE ITEM CLOSED; ON/LNE roots, "NG.OPT" resolves to nothing) built + WIRED same session:
decision_state 17 -> 21 blocks, audit-joins 12 classes x 101 days, 0 violations throughout.**
Costs measured: gate data ~$5 total (feed I actual $4.67); **Bento LIVE Standard $179/mo
SUBSCRIBED at close (smoke test = S100 opener)**; Pyth Pro declined ($500-10k/mo class).
STRUCTURAL: **the Pyth FREE era ends 2026-07-31** (all API keyed from $500/mo — pyth_collector
WTI/XAU/XAG sunset decision S100; Pyth NGD feeds NEVER published — 3 evidence lines);
**KXNATGASD settlement VERIFIED from spec** (Pyth per-contract NGD 1-min close 17:00 EDT,
underlying rolls forward 5bd before LTD — feed M spec consequence; Kalshi's `expiration_value`
IS the settle print, free); **settle-delta sweep: matched days median 0.1c — exchange-faithful;
all big deltas = roll-window calendar spread**; **THE MONDAY STUB FIND: NG 22 stubs Feb 2-Jun 29
(ALL G12/G13 Mondays — a silent walk blocker) REPAIRED (~$14, S92 script); CL 51 stubs (whole
year) HELD for Greg — free-redecode window closes ~Aug 12-14; July 1-18 NG never pulled.**
ICE HH positioning codes measured in our own CFTC files (023391/023392/0233AG/0233AH — cot
extension queued). SECURITY: the AWS key was photographed into chat — ROTATION = S100 item zero.
G12 still needs feeds A ph1 + E + Tier 3 merges; G13 additionally feed M. START S100 with the
drop-in box.

**S98 — THE DATA GATE LARGELY CLOSED IN ONE SESSION (read `SESSION_HANDOFF_2026-07-20_S98.md` +
`KICKOFF_2026-07-20_S99.md` + `research/kalshi/DATA_GATE_S98.md` [THE build list, feeds A-T]):**
Desk review (20-yr NYMEX/ICE lens) -> Greg: "rewrite our data plan to your specs" -> the gate
reorganized by regime family (DEMAND/POSITIONING/DELIVERY). **TWELVE feeds built/wired;
decision_state 8 -> 17 blocks; audit-joins 0 violations x 8 classes x 101 days all session.**
DECISIONS: **TWO-COACH architecture** (Kalshi initial primary, NYMEX dailies next; one signal core,
ledgers never pooled; build deep, subset down); **the futures->Kalshi LAG = THE STANDING LOOK-AHEAD,
established (S80 15-sig, S81 7-20s, S91 gold/silver), NEVER retest, live telemetry only**;
procurement policy = free-first, verify coverage, pay only MEASURED gaps. **Brain s100.3 MERGED**
(Greg approved): the C2 ratio reformulation REFUTED on comparable data (0120 true 0.714 vs 0107
false 0.718 - identical on every arm); C2 kept + scoped; **the flip confirm completes as C1+C3+C4
on the modern tape class** - forward test rides G12. Tier 1 done (G11 fingerprints on .n.0,
pre-G11 counts reproduced exactly). THREE S97 CONCERNS CLOSED AS MEASURED: vintage look-ahead =
ONE EIA revision event dated AFTER the winter (Mountain reclass ~10 Bcf/wk levels; one mislabeled
print Sep 4); regional store xls-vs-api diff 0/863; C2 resolved. STRUCTURAL DISCOVERIES:
**Kalshi had NO NG daily market in the walked winter** (KXNATGASD born 2026-03-27; Jan-Feb 2026
zero NG markets - the G7-G11 echo replay is impossible, feed M runs on the Mar 30+ life; dailies
skip Fridays; no historical book endpoint exists); the free weekly balance DIED 2025-10-02 (S&P
section removed; vessel line survives); **THE EIA SWEEP FIND: STEO monthly VINTAGES** = the
complete NG balance as-of each release, free, 1-34d stale (the API is current-vintage-only, the
archived workbooks are the source; join on RELEASE dates); the cash HH spot publishes in WEEKLY
BATCHES (naive T+1 would have leaked the Jan blowout a week early; decision-time-legit the +10.77
basis lands ON the 0130 17x day); the two positioning books sat at OPPOSITE extremes entering G11
(futures MM 2.83rd pctile vs options-implied 97.17th - now a wired variable). AWS: all three keys
ROTATED; `platform_sync.py` = the one door; ~15 S3 prefixes manifested; live-loop design =
us-east-1, sub-second suffices, LLM never in the hot path. MOS extended through Feb 27 (the
G12/G13 weather blindness closed; two builder traps documented). **S99 = ITEM ZERO the PAID-DATA
DISCUSSION (packet delivered), then feeds T/A/I/M/Q/R, Tier 3 doctrine proposals, THEN G12
(Feb 1-13) and G13 (Feb 15-27, the SQUEEZE TEST - opex 0224/expiry 0225 inside; requires feed I).**
START A FRESH SESSION with the S99 drop-in box.

**S97 — the walk paused at the hard data gate (read `SESSION_HANDOFF_2026-07-19_S97.md` [GATE section
FIRST] + `KICKOFF_2026-07-19_S98.md`):** G11 (Sun Jan 18 - Fri Jan 30) ran blind on s99.2 -> **6/12, drift
-13,190, the THIRD consecutive block-lean miss** (anchor 2.702 -> 4.416; the bleed reversed into a 63%
rally and the blind held the down-chain). Refine -> **s100.2, 23 plays: 10/12, drift -3,890.** **THE FLIP
RULE IS KEPT** — per-instance: **C1 (band-break) fires 1008/1020/1208/1223/0120 and correctly declines
0107 — five fires, one correct decline, ZERO false positives**; the blind missed because **it never
evaluated 0120, the actual flip day**. **C2 fails on HIGH-ACTIVITY tapes for a SCALE reason** (calibration
15-98 legs on 15-25k trades vs G11's 160-550 on 75-125k, so an absolute <=15%-of-legs bar is mechanically
unreachable) — the ratio reformulation is a FLAGGED BUILD GAP and **blocks G12** (needs G11 fingerprints
on .n.0 first). NEW plays `weekend_gap_delivery` + `mos_first_appearance_vs_revision`. **Brain
architecture (Greg): every play carries `requires`/`scope`/`forward_evidence`; refined rules NEVER
override blind-applicable ones (hindsight-fitted, zero forward evidence — and the blind-vs-refined GAP is
itself the measurement); promotion gated on forward evidence.** MOS forecast temps BUILT + in first use
(91/91 days, blind wall 0/11,648 violations). Net-of-fee replay: **fees are NOT the constraint, DIRECTION
is** (0/51 events had the taker fee flip a sign); G9's +14.4k is SIX named events, the other fourteen sum
-3,220; the block lean and the day-book are TWO DIFFERENT EDGES. Series-construction finding: NG.v.0
whipsawed 1000<->1021 through the G11 expiry week (Feb squeezed 3.0->5.4); G3-G10 are clean; G11 re-pulled
on **NG.n.0**; pass-2 deferred by Greg. **GREG STOPPED THE WALK: no new group runs until EVERY data input
in the handoff's GATE is built and wired.** THREE LANDED in S97 (committed + pushed, none wired yet):
**COT positioning** (`cot_feed.py`; caught a 47-day blind-wall leak — the 2025 shutdown suspended COT
publication Oct 1-Nov 12, so the naive Friday rule would have leaked across G6/G7; 0 violations after
overrides), **EIA regional + SALT/NON-SALT storage** (`storage_regional.py`; salt+nonsalt reconciles on
all 863 records; 0 violations over 6034 days), **contract structure + forward curve**
(`contract_structure.py`, 49 fields, expiries authoritative from definitions). **The last one caught a
flaw in its own spec: the OI-continuous front HIDES the squeeze** (0122 `front_next_spread` 0.093 because
n0 had already rolled) — a CALENDAR-FRONT block keeps the nearest-expiry pair visible, where the real
1.539 sits. **When wiring, expose the calendar-front fields or the feed cannot see what it exists for.**
STILL TO BUILD: MOS cycle timing (Sunday reopen priced by a later cycle than our D-1 feed), vol regime,
G11 fingerprints, C2 ratio reformulation, model disagreement, LNG feedgas, options, cross-market. **How
to build them (Greg): we are NOT testing theses — we put relevant info in front of the agent and IT
decides how to use it. Never gate an input on whether it "worked".** ALL SESSION DATA ON S3 (272 objects
/148MB verified; restore, do not re-pull). NEXT = wire decision_state SERIALLY, finish the gate, then G12
(Feb 1-13), then **G13 (Feb 15-27) = the SQUEEZE TEST** (carries the Feb 25 expiry).

**S96 (read `SESSION_HANDOFF_2026-07-17_S96.md` [session-total block at top] + `KICKOFF_2026-07-17_S97.md`):**
FOUR winter blocks walked, brain s95.2 -> **s99.2 (21 plays)**. PROTOCOL SETTLED (Greg): one-shot block-blind
= the canonical skill test; refine after EVERY group to the ITERATE-TO-TRACKING bar (general rules only, n>=2
spanning groups, never day-tuning); renders PRINTED to Greg before each refine merge; lessons merged BEFORE
the next group; blocks now START SUNDAY (reopen) / END FRIDAY (close). The arc: **G7** (Nov 5-18) blind 3/10
-> refine 9/10 -> s96.2 (giveback_exhaustion_boundary; Thursday side = running swing never print sign).
**G8** (Nov 19 - Dec 2) blind 7/10, lean right -> refine 10/10 -> s97.2 (catalyst_continuity_frontrun; R2
leg-vs-net; winter bands; thin AMPLIFIES delivery). **G9** (Dec 3-31, surplus-collapse December) = block-lean
MISS 1: 13/20 days but the market crested Dec 5 + SOLD THE COLD to -6150 (backwardation; first NEGATIVE roll
-0.504) -> refine 18/20 -> s98.2 (chain_polarity_flip; prints chain-sided at POLARITY 7/7; failed_rally_tell;
crash bands). **G10** (Jan 2-16) = block-lean MISS 2, a FALSE FLIP: 6/11, called a chain-birth off basing but
the down-chain never ended (0109 bullish draw SOLD -2760) -> refine **11/11 / drift +320** -> **s99.2**: the
flip CONFIRM hardened to FOUR mandatory conditions (band-break >=1.5x; old-side continuation-collapse <=15%;
printed-never-front-run; first-print arbiter), TERMINATION != BIRTH (chain birth needs a forward driver), NEW
third chain class **post_parabolic_bleed** (crashes single except into prints, bounces 1-2 days never 3).
Both lean-misses were POLARITY calls — the flip is now the hardest-guarded rule. LIVE-coach cadence (Greg):
rolling week-ahead arc + DAILY re-anchor pass that may OVERRIDE it (every strong rule consumes day-N-1 tape).
DATA next (Greg): forward-curve cache back ($0.07; curve_regime was 'unknown' all S96) + **historical
FORECAST temps via the IEM MOS archive** (forecast-vs-realized DELTA = the driver; back-fill the walked
winter). NEXT = G11 (Sun Jan 18 reopen -> Fri Jan 30; MLK thin; Feb->Mar roll ~Jan 26-27 INSIDE — check
first) blind on s99.2; then the net-of-fee coach replay (the money question). START A FRESH SESSION.

**One-line state:** the futures→Kalshi LAG is the live edge — **NYMEX is the CANARY, Kalshi the delayed
follower.** **git = CODE, S3 = ALL DATA. NEVER pool/average as the final word — each event individually; an
extreme rate is a LEAD, individual numbers pinpoint the WHEN (Greg S92).** **S92 = the NG intraday FORECASTER
program + DIRECTION cracked.** **S93 = the coach agent moved INTO AWS: box `i-08cee...` driveable via SSM,
Bedrock LIVE (us-east-1; opus-4-1/haiku-4-5 via boto3), Claude Code installed — one Claude-Code model-preflight
snag left before the LLM invokes; OpenAI written in as an alternative agent backend. Brain unchanged (s92.1); loop
not yet run on the box. See `SESSION_HANDOFF_2026-07-14_S93.md` + `deploy/aws/COACH_AGENT_SETUP_S93.md`.**
**S94 = PIVOT: run the loop IN THE CLAUDE ENV (the agent's brain = the session model; drop the AWS box/coach
agent), and go CHRONOLOGICAL. Ran Groups 2/3/4/5 (14-cal-day = 10-trading-day CONSECUTIVE blocks) + merged
each BLINDED into the brain -> now **s92.6, 12 plays** (PER-EVENT, NO averaging — Greg's hard rule). The
walk: G3 down (storage surplus called it) -> G4 reversed UP -> G5 a V — so the agent's block-OPEN direction
kept landing CONTRA the market -> NEW play `direction.cross_block_reversion` (n=3: LEAN AGAINST the prior
block, don't extend it). Weekend-gap Monday REVERSALS are huge + under-sized (1020 +$2770 vs guessed $580);
intraday direction still the open problem; fundamentals = slow backdrop not intraday timing. BUILT: running
storage-capacity + weather + weekday-HOLIDAY conditioning in `decision_state`; block-start ACTUAL last-hour
anchor; hr24->hr1 day-into-day reasoning + turn-detector; fast grep+npz scoring; continuous overlay. All 18
corrupt Mondays (Sep29->Jan26) re-pulled clean on S3. READ `research/kalshi/REFINE_DIRECTIVE_S94.md` +
`SESSION_HANDOFF_2026-07-14_S94.md`. NEXT (build left for next session): (1) the CONTINUOUS-CURVE forecast
representation (days still don't flow — schema+render+scorer so the guess is ONE unbroken path from the
anchor); (2) Group-6 (Oct 22->) on s92.6 + per-group blinded merge; (3) the UNBLINDED refine off the
consecutive groups; (4) walk into WINTER.** Built the full-toolbox per-leg characterizer (`month_characterize` now carries
the exhaustion suite + dipole + turning-point fingerprint + surprise/curve) and ran per-event learn/blind/hunt
passes on 12 warm-season NG days: (1) **NG DIRECTION is callable** — `dip_imb_level` (order-flow imbalance)
sorts a leg's side 7%/93%, monotone, **OOS-validated 100% on strong flow (34/34, 3 unseen days)**; a NOWCAST,
ideal for the Kalshi lag. (2) **Magnitude staircase** ($350 crossing = 92% ride, $500 = 100%) + grind-vs-spike;
book/dipole/exhaustion = noise for SHAPE (magnitude confounds). (3) **Turning point = far-side liquidity
RECRUITMENT, not consumption** (held legs grow the far ladder; reversed tops eat it). (4) Built the **coach
"brain"** `research/kalshi/knowledge/ng_brain.json` (versioned plays) + the self-growing loop (load brain ->
forecast blind -> merge -> refine -> converge -> the agent becomes the COACH calling plays). (5) Year-box:
**every Monday was corrupt** (Tue->Tue weeks -> Monday=last-day + `_flush` 'wb' clobber) — root-caused, FIXED
(`_flush` 'ab' append) + DOW-naming + NG Mondays re-downloaded clean; box at ~Oct. (6) NYMEX-forward workflow
rerouted git->S3, NWS-hourly RT collector built (need Greg's 3 GH secrets).
The loop MACHINERY is BUILT + tested (`coach_replay.py` executable playbook, `forecast_harness.py` helpers,
`FORECASTER_RUNBOOK_S93.md` the operating manual). **NEXT (S93) = RUN THE LOOP (brain -> forecast new group blind
-> overlay -> merge -> refine, walk the year); prove the plays net-of-fee (coach replay); the NYMEX-OPTIONS survey
(Greg: the real trading vehicle for our NG-move edge, very soon); characterize NG Mondays; verify box year +
reconcile + final Monday sweep; add GH secrets; rotate keys.**
Detail: `SESSION_HANDOFF_2026-07-14_S92.md`, `KICKOFF_2026-07-15_S93.md`, `research/kalshi/FORECASTER_RUNBOOK_S93.md`.

**READ THIS FIRST, in order — do NOT read this whole file for detail, it points you at the detail:**
1. The latest `SESSION_HANDOFF_*.md` (highest S-number) — the actual current state.
2. The latest `KICKOFF_*.md` — the priorities for this session.
3. `KALSHI_TRADING.md` — the file index: every Kalshi file, what it does, current vs old.
4. Then `git log --oneline -1` — confirm you are NOT on the stale tip (see Branch discipline).

---

## What this project is

DavisAI Markets. The live product is **Kalshi prediction-market trading** (weather / macro / energy /
electricity event contracts). Crypto (the OD "info-dipole" / order-flow toolkit) was the proving ground
and is now history — the session-by-session record + the earlier OD/physics research lives in
`CLAUDE_ARCHIVE_OD.md` (nothing deleted; see Archive pointer). The operator toolkit that came out of it
is LIVE and documented below (see "OD toolkit") — it is the engine the Kalshi lag / signal work runs on,
and we regularly reach back into it for pieces.

Team: **Greg Davis** (founder, sets direction, owns the weather forecaster spec) + Claude (engineer).

---

## The trading rules (load-bearing — Greg, S80-S82)

- **EACH TRADE INDIVIDUALLY, never average.** No pooled hit-rate, no mean signed-bps, no averaged
  coefficient — every aggregate blurs away the per-trade fingerprint that IS the predictive content.
  Characterize the DISTRIBUTION + the per-trade fingerprint; never lead with the mean.
- **Per-cell always, never pool.** Cells = moneyness × side × velocity/lag-class × release (for
  level-hits); regime × city × season × bucket × swing-dir (for weather). A signal that survives on a
  SUBSET of cells is KEPT and used on those cells — partial coverage is not failure. Report "works on
  {X}, not {Y}", never "X failed."
- **The merged signal architecture:** catalyst (release/news) = trigger + coarse size; book imbalance +
  flow + exhaustion = direction + magnitude; herd breadth = continuation, whale = scalp-only.
- **NYMEX is the CANARY; Kalshi is the delayed follower (Greg, S84).** The move happens on NYMEX/ICE
  first and reprices onto Kalshi seconds-to-a-minute later (futures lead, Kalshi never leads). Gather
  NYMEX as the leading signal, measure the lag, fire on Kalshi. Resolution: 1-min is USELESS (NYMEX
  moves fast); 1-sec is the historical floor and STILL undersamples — every 1-sec NYMEX readout is a
  LOWER BOUND, never the full tape. Data reality: Pyth has WTI (historical works) but NO natural gas
  and Brent-historical 404s; NG/Brent need Yahoo/other. See `research/kalshi/NYMEX_CANARY_NOTES_S84.md`.
- **Exclude the settle window** (the daily-settle exclusion / `SETTLE_UTC` guard) from every backtest.
- **Leakage gate before ANY backtest** (`odcore/leakage.py`) — pre-entry context must be invariant to
  future trades. This is mandatory and non-negotiable.
- **Zero synthetic trading data.** Ever.
- **Provisional until live.** A backtest edge is a hypothesis; nothing is "real" until it clears live.
- **Weather = Greg's spec, HANDS OFF.** The forecaster itself is Greg's own work; we only build the
  scoreboard/bridge (`kalshi_score.py`, the `(value,sigma)` bridge) and score PER REGIME vs the baseline.
- **`--events` on `news_coupling_research.py` is a BASENAME** joined onto `--data-dir`, not a path.
- **Keep `KALSHI_TRADING.md` current** — add new files to the top section, move superseded ones down.

---

## Operating discipline (cross-cutting)

- **Falsification-first / Result Discipline.** Every claim needs a falsifiable test. Every result is ONE
  data point — map alternatives (incl. the deflationary reading) before promoting to a claim. Catalog
  MISSES with the same care as hits; a negative that sharpens the program (like the S82 level-hit result)
  is a real deliverable.
- **No tent-widening on outliers.** When something lands outside the pattern, find the specific reason —
  don't loosen the test or wave it off as transient.
- **Incremental validation.** Canary run (short) before any long/compute-heavy run; break long runs into
  chunks with stop gates.
- **git is the source of truth.** Commit + push working code/docs regularly. Large data stays LOCAL /
  gitignored (see Branch & data). Better, stronger, faster, cheaper.
- **No emojis / special symbols** in docs, commits, or anything pushed.

---

## Branch & data discipline (READ — recurring trap)

- **THE DROP-IN BOX'S BRANCH IS ALWAYS THE STARTING POINT (Greg, standing, 2026-07-20 S100).** The
  harness assigns each session its own auto-named branch — that branch is NEVER the work. First
  commands of every session: `git fetch origin <drop-in branch> && git checkout -B <drop-in branch>
  origin/<drop-in branch>`, then confirm the tip message matches the drop-in's stated tip. All
  development and pushes go to the drop-in branch.
- **The empty-checkout trap (observed S100):** when the harness-assigned branch does not exist on the
  remote, the container comes up on an orphan `master` with ZERO commits and an empty tree — every
  file read fails and the session looks broken. The fix is the same fetch + checkout above; nothing
  is lost.
- **The stale-tip trap:** the harness often cuts a fresh session branch from a stale old tip (the known
  bad one is **S70 `3c70ff5`**). ALWAYS run `git log --oneline -1` first. If the tip is old, you are NOT
  on the real work.
- **Canonical trunk = `claude/kalshi-s79-kickoff-ij8t9o`.** The GitHub Actions collectors auto-push data
  commits here, so it is the live rolling branch — develop and push here (pull/rebase first, the
  collectors commit too). Do not strand work on a fresh harness-assigned branch.
- **Durable data accrues on branches, code does not:** `data/kalshi-bins` (live bins + consensus),
  `data/pyth-ticks` (Pyth futures ticks), `data/*-book` / `data/*-bins` (crypto history). Fetch + gunzip
  the relevant branch at session start; VERIFY it actually accrued before trusting it.
- **Local/gitignored data stores:** `data/kalshi_hist_trades/`, `data/pyth_ticks/`, `data/kalshi/`,
  `data/level_hits_*.json`. Too big for git; re-pullable.
- **Workflows (kept, on the trunk):** `.github/workflows/kalshi_collectors_durable.yml` (6h),
  `pyth_collector_durable.yml` (6h). If a run sits `queued` and never executes, it is an account-level
  Actions issue (billing/minutes/runner cap), not the workflow. My token cannot click "Run workflow" —
  Greg dispatches manually.

---

## Where things live (see `KALSHI_TRADING.md` for the full index)

- **`research/kalshi/`** — all Kalshi code: collectors (`kalshi_collector.py`, `kalshi_history.py`,
  `pyth_collector.py`, `consensus_poll.py`), the lag thread (`futures_kalshi_lag.py`,
  `lag_exploit_backtest.py`), the level-hit thread (`level_hit_dataset.py`), release/scoring/weather
  (`release_book_signal.py`, `kalshi_score.py`, `kalshi_weather_forecast.py`), findings `*.md`.
- **`KALSHI_BUILD_SCOPE.md`** — the build scope / thesis.
- **`odcore/`** — the OD toolkit (below).
- **`.claude/skills/`** — session rituals: `kalshi-session-start` (branch/data/accrual checks),
  `kalshi-backtest` (the mandatory evaluation discipline), `kalshi-roll` (Pyth front-month roll).
- Shared: `news_ingest_rss.py`, `news_coupling_research.py`, `regime_classifier.py`.

---

## OD toolkit (live — we reach back into this; provenance in `CLAUDE_ARCHIVE_OD.md`)

The operator tools built in the crypto era (S20–S37) that the Kalshi pipeline runs on, plus the pieces
we periodically pull back out. All portable numpy; validated per-cell.

- **`odcore/leakage.py`** — the MANDATORY pre-backtest leakage gate (catches look-ahead 40/40). Nothing
  gets backtested without passing it.
- **`odcore/leadlag.py`** — raw cross-covariance-over-lag lead-lag + time-slide null (the S19 "right
  tool"; what `futures_kalshi_lag.py` is built on).
- **`odcore/info_dipole.py`** — signed order-flow features + `divergence()`: the 2-factor
  DIVERGENCE (flow opposes price → ~65% reversal) + EXHAUSTION (imbalance collapsing toward 0.5 =
  leader weakening) read. The FILTER in the filter/timing split. Also provisional `cell_signal`/`DEPLOY`
  — **`DEPLOY_VALIDATED=False`, never trade the directional map** (S36 robustness: trend artifacts).
- **`odcore/incremental.py`** — `RollingFlow`, O(1)/tick bit-faithful incremental operator (1.7µs/tick)
  for hot-path use.
- **`odcore/fingerprint.py`** — per-cell fingerprint encoder (verbatim ports of the live micro-feature
  math + chunker recipe; flow features stacked per cell).
- **`odcore/dipole_predictor.py`** — the 128-dim centroid-projection algebraic dipole
  (`build_centroids`/`project`; H_a/H_b = projections on win/lose centroids — centroid-based, NOT bins).
- **`odcore/null_extract.py` / `coupling_scanner.py` / `symbolic.py` (PySR) / `validation.py` /
  `sizing.py` / `stacking.py` / `generators.py`** — coupling discriminator, tautology-killing
  circular-shift null, symbolic regression, the walk-forward net-of-cost promotion gate, OD-native
  sizing, stacking.
- **Crypto data history** (for reaching back): `data/*-bins`, `data/*-book`, `data/*-kraken-book`,
  `data/perp-history` branches — 5 coins × 3 venues 1s bins + L2 books. Collector workflows were
  deleted from the trunk end-S82 (runner hog); the code is recoverable via git history if collection
  ever needs to restart.

The research findings behind these tools are the next section — the dipole research stays LIVE here,
not just in the archive.

---

## Dipole research (standing — the findings, kept live)

The information dipole (davisai.ai/dipole) is our directional/flow tool; Greg: the trend-following /
flow read may be one of our biggest edges, usable across the WHOLE platform — which is why this stays
in the live doc. Full detail: `S36_NETCOST_BACKTEST_FINDINGS.md`, `SESSION_HANDOFF_2026-06-22_S36.md` /
`_S36b` / `_S37`, and `CLAUDE_ARCHIVE_OD.md`.

- **The core read (S36, 2 factors, stack monotonically):** markets are follow-the-leader (a trend = a
  flow) until the leader exhausts → new leader, usually opposite; the edge is detecting the changeover.
  (1) **DIVERGENCE** — `aligned_flow = imb_level × sign(price_drift)`; strong divergence (≤ −0.20) →
  ~65% reversal, temporally stable, consistent 6/7 cells. (2) **EXHAUSTION** — the dipole COLLAPSING
  toward 0.5 (leader weakening; the MOVE toward balance, NOT the discrete crossing, which is a coin
  flip). Combined: oppose+exhaust 64% reversal > oppose+strengthen 58% > with-trend+exhaust 52% >
  with-trend+strengthen 49% (healthiest trend).
- **Discipline (load-bearing):** the signed flow is NOT a direct direction predictor — apparent
  directional lifts were trend/base-rate artifacts (Simpson's on a trending window) and died under
  window/forward sweep + temporal OOS + detrended targets. `DEPLOY_VALIDATED=False`; never trade the
  directional `cell_signal` map. The DIVERGENCE/FLIP read is the robust edge; static `imb_level` is
  the detector (differential flows are not).
- **Net-of-cost (S36b, per cell):** the 64% does NOT clear a 10bps round-trip pooled; the flow gate
  adds ~+3bps/trade over blind trend-following and clears walk-forward-robustly only on specific cells
  (btc_bybit sell/buy). Direction is the easy part — the edge is SIZE-vs-FEE (the same finding Kalshi
  S81/S82 reproduced on a different market).
- **The architecture split:** DIPOLE = the FILTER (which turns are real) + fine-resolution
  PRICE-REVERSAL = the TIMING (1-sec enters ~5–6bps off the true turn vs ~9–11 at 1-min). Fee-floor
  rule: never trade a swing smaller than round-trip fee + 2× entry slippage (taker floor ~22bps;
  resting a maker limit at the predicted turn drops it to ~4bps, with fill-risk). Per-cell regime
  master-gate rescues bleeder cells; leave winning cells un-gated.
- **The gated-swing stack (S37, `_info_dipole_gated_swing.py`):** timing (1-sec price-reversal) +
  filter (dipole divergence) + regime gate + maker floor, leakage-gated (PASS 6/6); PROVISIONAL 4/6
  cells clear on the single window — never size off one window.
- **The centroid-dipole lineage (S33–S35):** the real markets dipole is CENTROID-based, not bins —
  H_a/H_b = projections of a trade's 128-dim OD `operator_coefficients` on win/lose centroids; per-cell
  exact coeffs + the distinctive-fingerprint program (`bucket-distinctiveness-is-the-goal`: predict
  winners by their per-cell fingerprint, never by class-separation statistics).
- **Standing meta-rules:** tools are COMPLEMENTARY, not competing — evaluate by STACKING, never
  head-to-head ("even a 5% net edge is huge"). Per-cell always. On Kalshi today the dipole exhaustion
  read is live inside `release_book_signal.py` (direction = book-imbalance sign, magnitude/fade =
  imbalance + dipole exhaustion) and the level-hit context features.

---

## Current state & priorities

Detail is in the latest handoff + kickoff — this is the pointer, not the record.

Recent arc (compressed; full detail in each `SESSION_HANDOFF_*.md`):
- **S99** — item zero held (determination after rest); feeds T/R/Q/I built+wired (21 blocks, 12
  audit classes, 0 violations); Bento live subscribed; Pyth free era ends Jul 31 (NGD feeds never
  published; NATGAS 24/7 = Pro, declined); KXNATGASD settlement verified from spec (per-contract
  NGD 17:00 close, 5bd-forward roll, expiration_value = the settle print); settle-delta sweep
  exchange-faithful (median 0.1c matched; big deltas = roll-window spread); the Monday stub find
  (NG 22 repaired ~$14; CL 51 held, free-redecode window closes ~Aug 12; Jul 1-18 never pulled);
  ICE HH codes measured; AWS key photographed in chat -> rotation = S100 item zero.
  Detail: `SESSION_HANDOFF_2026-07-20_S99.md`, `KICKOFF_2026-07-20_S100.md`.
- **S98** — the gate largely CLOSED in one session: desk review -> DATA_GATE_S98 (feeds A-T by regime
  family); 12 feeds built/wired, decision_state 17 blocks, audit 0 violations throughout; brain
  s100.3 (C2 refuted on comparable data, confirm = C1+C3+C4 modern-class, forward test rides G12);
  two-coach architecture + the established look-ahead recorded; keys rotated, platform_sync + ~15
  manifested S3 prefixes; three S97 concerns closed as measured; structural finds (no winter Kalshi
  NG market; free weekly balance died 2025-10-02; STEO vintages = the free as-of balance; weekly-batch
  cash publication; futures-vs-options positioning at opposite extremes into G11). S99 = paid-data
  discussion FIRST, then T/A/I/M/Q/R + doctrine, then G12/G13.
  Detail: `SESSION_HANDOFF_2026-07-20_S98.md`, `research/kalshi/DATA_GATE_S98.md`.
- **S97** — G11 blind (6/12, drift -13,190, third straight block-lean miss) -> refine -> **brain s100.2,
  23 plays** (10/12, drift -3,890). The flip rule KEPT with a per-instance read: C1 clean (five fires, one
  correct decline, zero false positives), C2 broken on high-activity tapes by a SCALE artifact — the ratio
  reformulation is a build gap that BLOCKS G12. Plays now carry `requires`/`scope`/`forward_evidence`;
  refined NEVER overrides blind. MOS forecast temps built + first use. Net-of-fee replay: fees are not the
  constraint, DIRECTION is; the block lean and the day-book are two different edges. NG.v.0 whipsaws
  through expiry weeks (G3-G10 clean; G11 re-pulled on NG.n.0; pass-2 deferred). **Greg STOPPED the walk
  at a hard DATA GATE** — no group runs until every input in the S97 handoff is built and wired. Detail:
  `SESSION_HANDOFF_2026-07-19_S97.md`, `KICKOFF_2026-07-19_S98.md`,
  `research/kalshi/PASS2_CONTINUOUS_SERIES_NOTES.md`, `research/kalshi/COACH_REPLAY_S97.md`.
- **S96** — four winter blocks walked (G7-G10), protocol settled (one-shot canonical, refine per group,
  renders printed, Sunday-start blocks), brain s95.2 -> s99.2 (21 plays); two block-lean misses, both
  chain-polarity, which is why the flip confirm was hardened to four conditions.
  Detail: `SESSION_HANDOFF_2026-07-17_S96.md`.
- **S95** — continuous-curve rep + contract-roll adjustment (`roll_adjust.py`; the 0925 "+2760 gap" was the
  Oct->Nov roll, VOID); full G3-5 refine on roll-clean data; G6 first true blind holdout (V; give-back caught,
  recovery missed); brain ONE file, s95.1/s95.2. Detail: `SESSION_HANDOFF_2026-07-15_S95.md`.
- **S93** — the coach agent moved INTO AWS (Greg: the agent must live in his AWS, on the box, not a Claude
  Routine). Cleared the whole access chain (the `Claude` IAM user now has S3+EC2+SSM-full+Bedrock-full + inline
  PassRole; no permissions boundary) and stood the box up as the agent host: instance profile `Ssm` attached ->
  **box `i-08cee...` Online in SSM** (drive via `scratchpad/ssm_run.py`); **Bedrock LIVE in `us-east-1`** (model
  access is per-region — us-east-2 404s; boto3 converse OK for opus-4-1/4-5/4-6 + haiku-4-5); **Node 20 + Claude
  Code 2.1.197 installed on the box**, `/etc/markets/coach.env` wired (Bedrock=us-east-1, S3=us-east-2). ONE SNAG:
  Claude Code 2.1.197's model preflight rejects the Bedrock Opus IDs (boto3 invokes them fine) -> LLM not yet
  invoking. Per Greg, **OpenAI is now an accepted alternative agent backend** (loop is provider-agnostic). Brain
  did NOT advance (s92.1); no group scored/merged. Detail: `SESSION_HANDOFF_2026-07-14_S93.md`,
  `deploy/aws/COACH_AGENT_SETUP_S93.md`, `KICKOFF_2026-07-15_S94.md`.
- **S92** — NG intraday FORECASTER + DIRECTION cracked + the coach BRAIN. Built the full-toolbox per-leg
  characterizer (`month_characterize`: exhaustion suite + dipole + turning-point fingerprint + surprise/curve)
  and ran per-event (NO-pooling) learn/blind/hunt passes on 12 warm-season NG days. (1) **NG DIRECTION callable**
  — `dip_imb_level` order-flow imbalance sorts a leg's side 7%/93%, OOS-validated 100% strong-flow (34/34, 3
  unseen days); a nowcast for the Kalshi lag. (2) **Magnitude staircase** ($350->0.92, $500->1.00) + grind-vs-
  spike; book/dipole/exhaustion NOISE for SHAPE (magnitude confounds). (3) **Turning point = far-side liquidity
  RECRUITMENT, not consumption.** (4) **Coach BRAIN** `knowledge/ng_brain.json` + the self-growing loop (load ->
  forecast blind -> merge -> refine -> converge -> the agent becomes the COACH calling plays). (5) Year-box
  every-Monday-corrupt bug (Tue->Tue weeks + `_flush` 'wb' clobber) root-caused + FIXED ('ab') + DOW-naming + NG
  Mondays re-downloaded clean; box at ~Oct. (6) NYMEX-forward workflow git->S3 + NWS-hourly RT collector (need
  Greg's 3 GH secrets). Detail: `SESSION_HANDOFF_2026-07-14_S92.md`, `KICKOFF_2026-07-15_S93.md`.
- **S91** — YEAR-PULL REBUILT on a durable observable box + GOLD/SILVER depth-add VALIDATED. (1) The S90 box had
  failed (S3 year = corrupt July stubs, blind box); rebuilt: `pull_year --weekly` (per-week Databento jobs +
  marker-resume) + stub-aware resume-skip, on box `i-08cee7171c0a76a04` (200GB) streaming its log to S3 (v1 died
  on an awscli dependency; v2 boto3-only booted clean). (2) Gold/silver LAG confirmed on free Pyth XAU/XAG
  (gold 37/60, silver 26/54 sig, futures-lead, same as WTI/NG; cross-strike is NG-only) — collectors + XAU/XAG
  Pyth feeds wired, HH NGDQ6 feed confirmed correct. (3) Agents: NYMEX-products + Kalshi-ranking (KXGOLDD #1).
  Execution deferred to last (paper-trade Kalshi demo first). Open S92: verify the year landed clean, rotate
  keys, migrate data git→S3, validate the lag net-of-fee at size. Detail: `SESSION_HANDOFF_2026-07-14_S91.md`.
- **S90** — EVERYTHING TO AWS + a critical data-integrity fix. (1) Verifying the first S3 month exposed an
  80% loss: `batch_pull`'s flush gzipped each day BEFORE it was complete, so a later file's boundary rows
  overwrote it (only Fridays/last-day survived) — FIXED (hold latest-2 days unflushed; validated 32.8M/32.8M
  CL-July rows recovered). (2) `pull_year --reuse-done-jobs` + `redecode_job` rebuild corrupt months from
  already-paid Databento jobs FREE. (3) Durable **EC2 box** `i-0017dc36072eaa6c8` (needed EC2FullAccess on
  the `Claude` IAM user; no managed Lightsail-full policy exists) self-configures from S3 + runs the
  recovery+resume. (4) ALL bento data moved git→S3 (`nymex_tape/`+`nymex_mbp10/`); git holds NO bento now.
  (5) S3 tape reader `event_move_baseline.load_cont_day(source="s3")` + raw normalizer (JOB 2 core, wired
  into `month_characterize --source s3`). (6) RAW HOURLY weather ingestion `nws_temp_feed --ingest-hourly`
  → `weather/nws_hourly/` (every field/ob, no roll-up; the daily degree-day store was the same reduction
  mistake). (7) Weather interface spec + trade-distribution math + AWS deploy kit + the daily-cadence trigger
  note. NG dipole quick canary = static-divergence NULL (test exhaustion next). Secrets to ROTATE (Q5).
  Detail: `SESSION_HANDOFF_2026-07-13_S90.md`.
- **S89** — BUILT the durable RAW ingestion + moved the tick corpus to AWS S3. Zero-filter MBP-10 writer
  (removed the last silent row-drop; verified 76 fields/row, all 10 levels). `pull_year_mbp10.py`:
  month-at-a-time batch, gzip-each-day-as-it-lands (`batch_pull(flush_dir=)` bounds local to 1 day),
  `--worktree`/`--scratch`, and **`--dest s3://…` or git**. One-day proof (CL 2026-05-14 = 975k msgs,
  1.3 GB→61 MB gz). Now pulling the full-raw year (CL+NG, 2025-07..2026-07) to bucket
  `bento-568968024170-us-east-2-an` (us-east-2, prefix `nymex/`); split container Jan-Jun 2026 / Greg's
  box Jul-Dec 2025, resumable via bucket list. AWS+Databento keys are session-pasted SECRETS; corpus is
  on S3 now, not git. NEXT = finish/verify + rework scoring to read the raw S3 tape. Detail:
  `SESSION_HANDOFF_2026-07-13_S89.md`, `research/kalshi/AWS_INGEST_SETUP_S89.md`.
- **S83** — meta session: CLAUDE.md audit/split (this lean doc + `CLAUDE_ARCHIVE_OD.md`, dipole
  research + OD toolkit kept live); the three ritual skills (`kalshi-session-start`, `kalshi-backtest`,
  `kalshi-roll`). No research ran; `data/pyth-ticks` still absent at close.
- **S84** — Data reckoning + weather. NYMEX-canary principle set. Found Pyth has NO natgas (bogus `NGDQ6`
  id) → Databento = primary historical (true-tick CL+NG, `databento_backfill.py`). KXNATGASD = daily
  NG-futures market; KXPOWERKWH = monthly macro stat. Weather per-day fingerprint. Killed respawning
  crypto collectors. Detail: `SESSION_HANDOFF_2026-07-15_S84.md`.
- **S86** — Produced the **event-state MODEL** (`EVENT_STATE_DESIGN_S86.md`, Greg's driver model — see
  one-line state) + three leakage-gated builds on the 24 MBP-10 windows (~$0.42), all provisional/n=12/
  Apr-Jul/logged-without-mechanism: (1) MBP-10 depth run-length (push-book one-sidedness vs run length NG
  −0.17 / CL +0.52); (2) EIA seasonal-proxy surprise split (`eia_surprise.py`, 12/12; opposite-signed
  surprise/move NG vs CL); (3) pre-release VOLUME primed/coiled detector (`pre_release_volume`; NG quieter
  pre-release → bigger move, consistent across cells — first build off the model, no external feeds).
  Eyeball-validated (06-17 CL big move = the 2026 Hormuz crisis). NEXT = P3 lag join (needs a Kalshi
  historical pull; gates the $130 full-year MBP-10). Detail: `SESSION_HANDOFF_2026-07-13_S86.md`,
  `DEPTH_RUNLENGTH_FINDINGS_S86.md`, `EVENT_SURPRISE_FINDINGS_S86.md`, `PREVOL_FINDINGS_S86.md`.
- **S85** — Databento LIVE (key set, `pip install databento` 0.81). `event_move_baseline.py` BUILT + run
  on 12 NG + 12 CL real release windows (leakage PASS, `definition`-schema $10/tick): per-contract
  HOLD-TIME map (NG 60s=66% of move front-loaded; CL slower, 60s=27%, longer hold gets the rest — both
  kept, EV-net-of-fee is the gate). Futures move = the ceiling; lag join next. `databento_backfill.py`
  hardened (defs mode + point-in-time tick store, volume roll `.v.0`, retry/backoff). Schema decision =
  MBP-10 (depth, ~$130/yr both, ~$5 over credit; MBO off). Tape persisted on `data/nymex-ticks`
  (session-start restores it). Detail: `SESSION_HANDOFF_2026-07-12_S85.md`, `EVENT_MOVE_FINDINGS_S85.md`.
- **S88** — RAW-INGESTION correction (Greg, load-bearing): historical data is RAW, keep ALL the info; gates
  ONLY on the trade side. Rewrote the MBP-10 writer to keep everything (every message + all 10 levels, zero
  reduction). Built the data feeds `nws_temp_feed.py` (NWS gas-weighted HDD/CDD+precip) + `forward_curve.py`
  (backwardation/contango). Forecaster scoring scaffolding built (`month_characterize`, `bucket_continuation`,
  coin-style `forecaster_month_pass.workflow.js` — ran end-to-end, fixed a date-format leakage bug) but it
  pre-processes on the ingest side → must be reworked to read the RAW tape. NEXT = the durable raw-ingestion
  workflow. Detail: `SESSION_HANDOFF_2026-07-13_S88.md`, `KICKOFF_2026-07-14_S89.md`.
- **S87** — BUILT P3: `lag_join.py` lag-join engine (release + `--intraday`), NYMEX-driven entry/hold/exit,
  trend-hold dollar trailing stop, maker vs taker net-of-fee. PROVISIONAL but pays (CL/NG both positive
  gated; intraday 06-17 trend-hold −115c→+202c maker; leans on maker fill, tiny-n). Designed the intraday
  PATH FORECASTER as a stacked hold-length signal (`FORECAST_AGENT_DESIGN_S87.md` Greg's spec +
  `PATH_FORECAST_RESEARCH_S87.md` cited methods). Databento pull infra (`batch_pull`, `pull_year_mbp10.py`);
  1-yr continuous MBP-10 pull = pay-once to `data/nymex-ticks:nymex_cont/` = the forecaster's analog library
  (2-yr to S3 at go-live). Detail: `SESSION_HANDOFF_2026-07-13_S87.md`.

S86 priorities (see `KICKOFF_2026-07-12_S86.md`): (1) extend writer+baseline to consume MBP-10 DEPTH
(run-length/exhaustion read), then batch the full-year MBP-10 (watch disk); (2) historical surprise join
(EIA actuals + consensus) for the surprise-cell split; (3) the lag join = Kalshi echo net-of-fee vs the
futures move (realized-EV); (4) standing: NGDQ6 fix, weather forecaster scoring, Pyth live lag.

---

## Archive pointer

The full OD / info-dipole crypto research (S20–S37) and the earlier Information-Layer / four-forces /
gravity-time physics research (S3–S25, the INFO-0xx ledger, capability demos) live VERBATIM in
`CLAUDE_ARCHIVE_OD.md`. Nothing was deleted — it was moved out of the always-loaded context because it
is history, not the live Kalshi operating surface. Consult it only if a question reaches back into the
OD toolkit's provenance.

---

## Keeping this file lean (session-note workflow)

This file stays SHORT and CURRENT. Per session: write full detail to a `SESSION_HANDOFF_*.md`, update the
one-line state + header date/session at the top, fold only the new headline into the "Recent arc" list
(drop the oldest if it grows past ~6 entries), keep `KALSHI_TRADING.md` current, commit + push. Do NOT
paste session detail into this file — that is what the handoffs are for. The failure mode this structure
prevents: a bloated master a cheaper model silently half-ignores.
