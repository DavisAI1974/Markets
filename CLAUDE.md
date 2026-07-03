# CLAUDE.md — DavisAI Master Context (Updated 2026-07-03 Session 59 — READ `S59_NOTES.md` + `SESSION_HANDOFF_2026-07-03_S59.md` + `KICKOFF_2026-07-04_S60.md`, not this whole file)

## ⛔ STANDING BAN (S57, 2026-07-03, Greg): BYBIT — NEVER USE FOR ANYTHING
Bybit is permanently off-limits for this project: the venue is US-INELIGIBLE (Bybit's own
restricted-jurisdictions policy names the United States; the restriction applies at the UBO
level for entities per their Business-KYC FAQ; no US-facing intermediary offers its books —
post-Falcon-Labs CFTC enforcement). ALL bybit code, data, cells, collectors, and ledgers were
STRUCK in S57. Never collect its data, never run its tape, never cite its cells or fee tiers,
never propose it as a venue or benchmark. Primary-source record: `S57_VENUE_FINDINGS.md`.
Two leftover data branches (data/{sol,eth}-bybit-book) await Greg's UI deletion.


## S57 UPDATE (2026-07-03) — the ELIGIBILITY RESET: Bybit STRUCK (permanent ban, block above) + MEXC DEAD; mk0 exposed as an unreached tier -> REAL FEE MODELS standing (cb_entry 40/60 / cb_early 10/20 / cb_real 8/18 / cb_scale 3/10 / cb_top 0/6 ceiling); FINE BAND measured DEAD at every reachable tier; STAGED-COMMIT SIZING validated (Greg's design; ALL-IN = $5k); MID BAND = the only way (Greg) -> S58 = the 3-PIECE PLAN (read `SESSION_HANDOFF_2026-07-03_S57.md` + `KICKOFF_2026-07-04_S58.md`)
- **ELIGIBILITY (the session's axis):** Bybit US-ineligible at every door (direct: US on their own restricted list; entity: UBO-nationality test; intermediary: none US-facing post-Falcon-Labs) -> ALL bybit code/data/cells STRUCK; MEXC dead 5 ways (API maker +6bp overrides marketing 0%; ToS bans HFT/API algo; unlicensed everywhere; freeze-profitable-traders pattern verified; volume non-organic). Citable record `S57_VENUE_FINDINGS.md`. NEW STANDING RULE: verify venue eligibility (jurisdiction + fee reality, primary sources) BEFORE any venue work.
- **FEE REALITY:** mk0/tk5 (every Coinbase paper number since S47) = an UNREACHED tier (verified schedule: 40/60 entry .. 0 maker only at $250M+/30d; the real $500k/mo upgrade program matches proportionally to ~3-8bp for 60 days — cannot deliver mk0; no lawful rebate anywhere; onshore CFTC perps ~2bp/side or $0.15/contract, no rebates). FINE BAND at $5k all-in: NEGATIVE at every reachable tier (sol -124..-2,381/hr, eth -284..-4,143), positive only at the 0/6 ceiling — toll:edge 8:1; structurally dead on lawful venues.
- **THE BLEED MAP (measured):** fine = fee toll x cadence (61 legs/hr x 16bp vs +1.9bp/leg real edge); mid-band-as-naively-built = THETA-GIVEBACK at entry (enter after coarse confirm = theta late: SOL -31bp/leg GROSS, REVERSED positive = the S54 signature; ETH theta80 +21bp/leg gross w/ REVERSED negative, n=22 one window = the shape to chase). NOT bleeding: execution (taker 0-1%), fine direction, the confirm-add mechanism.
- **STAGED-COMMIT SIZING (Greg's S52 accumulate per-leg) VALIDATED:** starter every leg -> ALL-IN ($5k IS the cap, no $10k) on confirmation; adds MAKER-POSTED (taker adds fatal). Confirmation adds beat random 10-14 sigma on two venues' tape; add earns +1.4-2.0bp net AFTER the signal; win 69%->91-95% once confirmed; 16% confirm <1s. ACROSS trades: NO signal (P(w|prev w)==P(w|prev L) all 5 cells) — the probe lives INSIDE the trade. Confirm threshold MUST SCALE WITH THE BAND (+2bp confirms ~everything at coarse).
- **THE LAG CUTS (Greg's dipole-dive recall — S55 R5/R8, the fix for the mid-band bleed):** entry theta-confirm 151bp/54min -> fine 25bp reversal confirm 26bp/1min (dive lifts P(real) 0.36->0.48; R4 `continue`/rc~0 veto = the false-fire filter); exit lean-collapse at ~28bp giveback (`lean_exit` wired S55, never aimed). ~250bp/leg recoverable; S55 prize table theta100 +106..122bp/leg. S56's ARM-family kill was RBATE-REGIME-graded (ARM0's volume paycheck) — re-testing at mid-band ARMs under real fees w/ R4 veto is the changed question, not relitigation.
- **Also:** freight-train veto: anatomy real (signed fade corr -0.31; unsigned first pass = tool error), gate unprofitable (no subgroup sums negative) -> DEAD as a gate, content lives in the size axis. Probe-across-trades dead (anti-martingale re-confirmed). Baseline ledger 26,784 healthy (mk0 record basis — see fee reality).
- **DEAD (S57):** bybit-anything (banned); MEXC; mk0 as a headline basis; fine band on lawful venues; freight-train entry veto; probe-then-commit ACROSS trades; taker adds at tight confirms; +2bp as a coarse-scale confirm.
- **NEXT (S58): the 3-PIECE PLAN, one piece at a time (Greg):** (1) ENTRY — armed mid-band extension + dipole-dive/25bp fine confirm + R4 veto, anchored at the fine flip nearest the PIVOT, vs theta-confirm baseline, all fee models, multi-window (Binance-spot 30d bins research tape + Coinbase books), full controls; (2) EXIT — aim `lean_exit` (R8) at coarse; (3) STAGED ALL-IN on the confirmed rides. Background: Kraken Pro US spot tier verification; Greg: UI-delete the 2 bybit data branches.

## S56 UPDATE (2026-07-03) — JOB 1 run as a live walkthrough loop (worst-10/smallest-10 renders every round — Greg's standing rule) → EVERY armed/coarse-confirm variant KILLED by its own gate → THE MODEL = the DEPLOYED fine zigzag at NATURAL CADENCE (ARM0) on Bybit @ MM3: FULL S54 GATE PASS all 5 coins (z 6.8–14.4, 20/20 coin-weeks, reversed below the shuffle floor) → PROMOTED to platform SANDBOX cells → queue-honest capacity MEASURED (read `SESSION_HANDOFF_2026-07-03_S56.md` + `KICKOFF_2026-07-05_S57.md`)
- **The autopsy (each variant killed by a measured mechanism):** v1 arming IDLES (98% of the month stranded in a stale leg, max 289h; loss NOT bounded — max adverse 1,905bp; 3.9 legs/day vs oracle 28–60; cadence, not fees, kept $/hr down). v2 (extreme-anchored + trailing fallback) fixes cadence (129/day) but the bare 25bp first-dip confirm = mid-trend COIN FLIP (47% win, gross −3bp; executor verified bit-exact vs hand P&L; toy path proved sides correct; "swapped losers" = drift + trough-selling fallbacks, not a bug). v2+R4 dipole veto lifts gross but ARM40's gate pass = KNIFE-EDGE (ARM30/35/45 response curve dead — sweep the knob before promoting a grid point). v3-ARM (deployed flip detector enter/exit + ARM chop filter): ARM filter family fails as a family.
- **ARM0 = THE MODEL (Greg called it all session):** deployed lean-flip enter/exit at natural cadence (~127k legs/30d/coin): z = 9.0/11.3/13.0/14.4/6.8 (sol/eth/btc/doge/xrp) vs joint price+flow shuffle, 20/20 coin-weeks positive, reversed BELOW the floor all 5.
- **THE SHUFFLE FLOOR (load-bearing):** at rebate fees a structure-free tape still earns ~$90–106/hr/coin (volume paycheck — reversed/coin-flips collect it too). Fair zero = the floor; the DIRECTION PREMIUM above it = +$7–17/hr/coin. Never cite floor $/hr as edge.
- **FEE SCORING STANDARD (Greg):** 10%-taker blend on bins (measured taker: Coinbase ledger 0–5%, Bybit books 0.0–0.1% at grace300): taker11 / std_bl +4.70 / mm3_bl −1.15 rt/leg; TRUE fees on books. Keep taker fees out of design — the fee floor is what kept every engine idle.
- **PROMOTION:** `odcore/platform.py` — `venue` = first-class CellConfig dimension; NEW `SANDBOX` registry = sol/eth bybit @ true MM3 (−1.25/5.5, grace 300; gate record in the registry comment). `paper_trade.py` runs SANDBOX cells every run → `paper_ledger_sandbox.jsonl` (seeded 3,735 legs @ 0% taker; bybit book cron IS accruing — 12.6h now, no longer the 5.83h single window). Baseline canary bit-identical (+0, 25,845).
- **QUEUE-HONEST CAPACITY (`_s56_bybit_capacity.py`):** $5k flat, 12.6h books: sol_bybit +$3.05 (v2) … +$37.19 (v1) /hr; eth +$12.22…+$46.73; net/leg +4.25/+2.89bp, taker ~0%. Binding constraint = FILL SIZE (median fillable $137–169/leg), not the edge. **std +2bp NEGATIVE on real books both fill models → Bybit MM application (Greg) = the existence condition.**
- **Walkthrough tails:** worst-10 = FADE-THE-FREIGHT-TRAIN (counter-entries into violent moves; dipole class `continue` rc=0.00 on 10/10 — our own descriptor flags them) → freight-train veto = S57 SANDBOX VARIANT, NO-GATES judged. Smallest winners = seconds-long noise round trips (rebate-only economics).
- **DEAD (S56):** v1 arming; bare price-dip confirm; trading fallback (risk control must FLAT, not flip); ARM chop-filter family; fee re-pricing as cadence rescue; rebate-floor $/hr as edge.
- **NEXT (S57):** (1) Greg: MM application; (2) accrue sandbox + re-run capacity on grown books; extend bybit book collectors to doge/xrp/btc; (3) freight-train veto sandbox variant; (4) Binance spot R4 second-venue check (JOB 2, never run); (5) BTC Coinbase collector 155h gap (JOB 3, still broken).

## S55 UPDATE (2026-07-03) — the LEG WALKTHROUGH session (15 tested rounds, Greg's markups = the spec pipeline) → THE ONE VERSION (`odcore/platform.py`: paper=live=research, canaried bit-identical) → both lag halves MEASURED (entry 151→26bp R5; exit flow-collapse @~28bp R8 "inverted graph") → the MIDDLE BAND priced (Greg's pencil scale theta60-100: theta-confirm loses −25..−40bp/leg on EVERY coin = why his drawn trades are unharvested; at measured fine-confirm costs +$2,900-3,700/day 5-coin @$5k PROJECTION) → ARMING RULE v1 first pass POSITIVE 20/20 cells on 30d deep tape, reversed negative — NOT adopted, S56 JOB 1 = the full gate (read `SESSION_HANDOFF_2026-07-03_S55.md` + `S55_WALKTHROUGH_NOTES.md`)
- **THE ONE VERSION (Greg: "compile 1 version — live, paper, all sizes"):** `odcore/platform.py` = the single decision layer; `run_cell` (deployed cells, S47 sizing ALWAYS on), `run_stream` (ANY flip stream through the same executor/sizing/descriptors — research never forks mechanics again), `DEPLOYED` registry; `paper_trade.py` -> thin harness (CLI/ledger/GHA unchanged). Canaries: +0 trades, ledger 25,845 intact, shakeout bit-identical; S49 leakage gate PASS all 5.
- **Executor additions (opt-in, defaults bit-identical):** `lean_exit` (R8 dipole collapse exit — INERT at fine scale, the flip detector already IS that exit; value at coarse), `fill_mode="taker"` (equivalence-PROVEN: zz150+bigline through the executor == S54 leg tables exactly), `exit_gate` (structure-says-out/FLAT third state), dipole entry gate fed (`--dipole-entry`), R1 dipole descriptors on every ledger row. ⚠ FOUND: S46 doc/code mismatch — non-actionable flips HOLD (never flattened); docstring corrected, exit_gate is the explicit flatten.
- **Walkthrough verdicts:** losers NOT side-flipped (fakeout confirm-lag anatomy; flip test loses more); Greg's pencil = oracle theta60 (11 legs/100min, zz150 took 3, LAW: capture = swing − 2θ − fees); descriptor SCALE-LOCAL (zz150 reversal-class +30.2/leg 4/5 coins z=1.8; zz100 INVERTED; coarse depth->|move| sign-inconsistent); two-scale v0/v1 DEAD (re-entry churn); cadence decomposition: fine zigzag vs bigline capture IDENTICAL (36%), gap = pure cadence (153 vs 0.4 legs/hr), coarse's lever = SIZE; bigline platform rerun: Bybit gate reproduces S54 exactly, Coinbase maker-mechanics ~2x the parked number (SOL +4.81 … DOGE +5.71 $/hr, one window).
- **ARMING RULE v1 (`_s55_armed_zigzag_probe.py`):** two-stage confirm zigzag — extension >= ARM arms DURING the ride (costless at the turn), first 25bp fine reversal confirms AT the turn (~25bp instead of theta). First causal pass: positive ALL 20 coin×ARM cells, REVERSED negative every row, net/leg = the lag projection (ARM150 +100..+121bp). NOT adopted: n thin outside SOL, entries fire on the first post-arm dip (R4 dipole class = the veto to test), S54 full gate not run.
- **PACE RULE (Greg, standing):** one round = one defined test, run, read, THEN next. **NEXT (S56):** (1) full gate on the arming rule (shuffle+reversed+per-week x5, dipole-gated variant, maker tiers) -> promote to odcore on PASS; (2) Binance-spot descriptor check; (3) BTC book collector + Bybit book cron (both still broken); (4) Greg: Bybit MM application.

## S54 UPDATE (2026-07-03) — Greg's BIG LINE (trendline ride/break) built through 5 live chart-markup spec rounds → +$1-4/hr on 4/5 Coinbase one-window books → the S54 DATA UNLOCK (Bybit/Binance bulk trade dumps → 30d x 5-coin 1-sec bins in ~40min, in-container) → the deep-history gate FAILS it (all 5 coins, all 20 coin-weeks ~= shuffle); coarse dipole bell DEAD-as-built (measured: retrace-confirm on smoothed lean fires with 72-89% of the leg GONE — late, not wrong); GREG DIRECTIVE: TWO-SCALE ZIGZAG = S55 (read `SESSION_HANDOFF_2026-07-03_S54.md` + `KICKOFF_2026-07-04_S55.md`)
- **The build (new files only; zigzag/one-shot/accum untouched):** `odcore/swing_bigline.py` (aligned HH+HL/LL+LH entries, continuous-adaptive theta = 0.25 x trailing 4h range, ratcheting redraw, leakage PASS), probes `_s54_bigline_probe.py` / `_s54_flip_threshold.py` / `_s54_backfill_sweep.py`, renders `_s54_render_bigline.py`, NEW `backfill_binance_spot.py`. Greg steered by drawing on renders — the markup→mechanic loop IS the spec pipeline (alignment, scale-down-in-chop, bounce-back confirm, cadence gist, maker posture "jump in front with an offer they can't refuse").
- **Oracle at coarse theta (books):** SOL theta100 ~20 sw/day med 175bp = $1,822/day @$5k — the pool is deep, fees 2-6% of swing. Greg's coin criteria = NEW ALGEBRA: $/hr = opportunity (waves/day x size) x CAPTURE fraction; his pencil over 15h SOL ≈ +1,400bp vs engine +37bp.
- **The gate that matters (NEVER tune off one window, proven same-day):** the 4/5-coin Coinbase result did NOT reproduce on 30d x 5 Bybit bins — adaptive big line negative every coin, every week, ~= its shuffle. PARKED (not dead — Greg: "nothing is dead; it's up to us to figure out how to draw straight lines between 2 points"); Coinbase-cell verdict awaits Coinbase history (REST-grind only, no bulk dumps).
- **Bell post-mortem (the WHY, measured):** coarse lean flips (10min-2h windows) = P(real)~0.50 at every cadence on thousands of events BECAUSE the confirm lags the true turn by 2h+ (72-89% of leg elapsed). Fine lean (60s) pins turns to seconds but rings 83/hr. x_PL bounce never rescued any scale (k=0 beat k>0 at coarse).
- **Scaled-up zigzag baseline (30d bins): the giveback ledger** — theta150 SOL gross/leg +10.7 vs oracle +$45/hr: the coarse flip PICKS real legs but pays ~2xtheta giveback (~300bp) per ~310bp swing. Fine execution pays ~50bp. **GREG: "we have a good enter and exit strategy with zig zag. we just have to scale it up and eliminate the chop in between" → S55 JOB 1 = two-scale machine (fine flips execute, coarse structure selects, chop veto ablated under NO-GATES scoring).**
- **Infra:** BTC Coinbase book = 155h gap of 196h (collector broken — fix before ANY BTC-cell claim; Greg's fun guess on record: BTC wins on bigger climbs/slides); Bybit book cron still the one 5.83h window; bins are re-pullable (commands in kickoff), /tmp dies with the container.

## S53 UPDATE (2026-07-03) — Greg's Set B walkthrough → sandboxed refinements: dump-widening+taker-cap lift SOL 2.2x but CROSS-CELL = SOL-ONLY (candidate parked awaiting time-OOS); B1 harvest rungs DEAD; ⚠ Q1 honest-queue ≈ $0 on every config; GREG DECISION: trade the BIGGER TRENDS (read `SESSION_HANDOFF_2026-07-03_S53.md` + `KICKOFF_2026-07-04_S54.md`)
- **GREG RULES (load-bearing): NO GATES** — judge every change on net $/hr AND legs/hr; eliminating losers eliminates winners too; sandbox before committing changes (all S53 executor params opt-in, defaults bit-reproduce S52, canary PASS). D-class excluded (confirm-budget/timeout/stricter-confirm — "we'll see about the d's later maybe"); A1 then showed confirm-budget was a dud anyway (corr −0.10).
- **Walkthrough anatomy (renders docs/renders/s53/):** worst-10 losers ALL confirmed@$5k, capped −$12.95, ZERO dumps in the tail — the tail is a confirm-quality phenomenon (late confirm at exhaustion + taker-heavy completion). Smallest winners = harvest failures at SPIKE tops (+$0.27 off a 45bps ride, mk$0/tk$5,003 exit), NOT small swings. Top-3 winners carry $140.60 of the $214 winner column. Entry lag = θ≈23bps by construction (L1's double-top shows tighter θ gets faked out). Dipole DIVE (Greg's chart): filter wired as gate; DIVE timing wired NOWHERE → C1 candidate.
- **Diagnostics (`_s53_accum_sandbox.py`): A3 61% of dumps FALSE** (would have confirmed; −$31 of the −$45 dump column; universal 56–78% across all 5 Coinbase cells); **A2 taker share = cleanest separator** (corr −0.31; 0%-taker +$12.40/71% win vs top-quartile −$5.68/25%).
- **Sweep (SOL, controls+Q1 every row): base +$1.60/hr → dump×3 + p2_taker_cap 0 + slideX2 STACK +$3.54/hr (2.2x)**, controls negative throughout. **B1 harvest-into-strength rungs LOSE** (−$0.26 — caps the fat winners; Greg's rule measured on the exit side) → DEAD. **⚠ Q1 honest-queue ≈ $0 on EVERYTHING** — the accum edge lives entirely in the front-of-queue tier; the R&D-not-deploy label stays.
- **Cross-cell (`--cells`, 7 cells): candidate does NOT generalize — mechanism universal, money SOL-only.** ETH Coinbase REVERSED control POSITIVE (+1.09 at d3.0 — S51 disqualifier shape on that cell/window; its window = one +413bps grind, trend not oscillation); DOGE shuffle positive; BTC 0.7 flips/hr at θ=20bps. **Disposition: dump_mult∈[1.5,3]+cap0 = SOL-Coinbase-ONLY candidate awaiting time-OOS; defaults untouched.** Bybit still the SAME single 5.83h window (cron delivered nothing new — check it S54).
- **ZOOM-OUT (Greg's full-shape request; `_s53_render_fullwindow.py`):** window ranges 482–1094bps vs our θ≈23bps ripple — multi-hour 100–300bps waves where the fee floor is 2–5% of the swing (vs ~25%). **GREG: "we definitely need to start trading the bigger trends" → S54 JOB 1** (oracle at coarse θ first, then leakage-gated causal probe, controls mandatory, multi-day books).
- **NEXT (S54):** (1) big-trends oracle+probe; (2) Bybit multi-window confirm (diagnose the cron); (3) SOL candidate re-run on new windows; (4) C1 dive-timed starter (attacks Q1); (5) Greg: MM application. Files: `_s53_accum_sandbox.py`, `_s53_render_fullwindow.py`, swing_accum opt-in params, ranked-tail render modes.

## S52 UPDATE (2026-07-03) — fill-model BUG fixed (ALL pre-S52 matrices superseded — old mk0 $/hr were ARTIFACTS); Greg's ACCUMULATE strategy specced+built+validated in miniature; Bybit venue cells MEASURED: MM program = the EXISTENCE condition (read `SESSION_HANDOFF_2026-07-03_S52.md` + `S52_SIZING_MATRIX.md`)
- **THE BUG (Greg: "the low $/hr numbers don't look right" — they were too HIGH):** `_leg_caps` had no price-eligibility — it credited flow that traded after price left our limit. Fixed IN PLACE (default `price_eligible=True`). Corrected: honest resting fills are 1.8–4.2x bigger but concentrate on LOSERS (SOL med fillable $483 winners vs $6,161 losers — a fixed limit fills fully when wrong, gets rationed when right = S45 adverse selection in dollars). **mk0 = measured-DEAD at size on every cell, every cancel window** (old +$7–18/hr = artifact); −1bp Coinbase cells survive (+$14–30/hr); $/hr RISES with resting time under a rebate (rest-until-turn correct there). Deployed-size conviction sizing is rebate-contingent; per-leg forward-ledger lift stands.
- **BYBIT VENUE CELLS (one 5.83h window each, PROVISIONAL):** standard mk+2 CATASTROPHIC (SOL −$157/hr, ETH −$273/hr @$5k) → **the MM program is the existence condition, not an optimization**; MM3 −1.25bp: **SOL +$115/hr, ETH +$113/hr @$5k, ~10x the mk0 case**. SOL = first cell (spread 1.24bps + rebate), ETH = second (0.06bps spread = pure rebate harvest, $40M/hr tape). Tape multiple this window 3.3x/6.9x vs Coinbase. **Greg action: SEND the MM application — the measured case exists now.**
- **GREG'S ACCUMULATE STRATEGY (dissected piece by piece → `odcore/swing_accum.py`, sibling executor; spec in his words = `STRATEGY_accumulate_S52.md`):** dipole-selected REAL turns; starter small while unsure; ALL-IN remainder on confirmation ("as much trading done as quickly as possible on confirmed winners"); layered fee-aware unload (trailing best offer down the slide, slide-cross taker rule); quick cheap dump on failed calls (small by construction). Head-to-head (7 cells × 4 turn scales × tiers, shuffle+reversed+honest-queue controls): **loses on ALL micro scales** (1–4bps swings = nothing to confirm — measured) but **on the zigzag swing-scale stream (θ≈4×(hs+tk)) + dipole gate it VALIDATES in miniature on SOL Coinbase: +$1.3–1.6/hr, beats shuffle (−$3) AND reversed (−$3)** — first arm in 8 sessions where the gate beats its shuffle and reversed loses. Mechanics per design: 4:1 W/L notional truncation, addH 2.2bps (all-in-on-confirm beat the S40 crescendo). Tiny $ → R&D thread, NOT deploy. **S51 "scale-in falsified" + "front-of-queue sims" DEAD labels re-attach to the MODEL CLASS, not this design.** 60-trade render walkthrough: `docs/renders/s52/`.
- **twxv4t (quick-S52 session) disposition:** anti-martingale kill STANDS; green-add fillability kill SUPERSEDED (wrong window); its matrix SUPERSEDED.
- **NEXT (S53):** (1) Greg: Bybit MM application; (2) multi-window venue confirm (cron accrues 4/day); (3) accum refinement (asymmetric bands, lean/dipole confirm modes — zigzag stream only, controls mandatory); (4) wire venue cells into `_capacity_model.cell_scenarios`. DEAD adds: mk0 anywhere; the old no-eligibility fill model; accum on micro streams; TIF-as-mk0-rescue.

## S51 UPDATE (2026-07-02) — rebate lever MEASURED (super-linear); Bybit picked + venue-book crons LIVE; v2 queue-honest fill; scale-in probed (one-shot executor VALIDATED); ⚠ "$/hr" is a MATRIX, never one number (read `SESSION_HANDOFF_2026-07-02_S51.md` + `S51_REBATE_FINDINGS.md`)
- **⚠ STANDING CORRECTION (Greg): never cite a single "$X/hr ceiling."** Every $/hr = one cell of {venue, maker fee, FLAT|SIZED, v1|v2 fill, window}. Same SOL legs: mk0·flat·v1 +$18/hr … −1bp +$71 (3.9x, SUPER-linear — the rebate flips losing legs positive) … −2bp+wider +$142 (v1); v2 queue-honest mk0 **−$7** → −1bp +$20; all PRE-Bybit (10x tape). **S52 JOB 1 (Greg): the sizing-on-winners accounting is NOT final in these numbers — make it airtight first** (forward ledger says sized>flat OOS on all 5: sol +16% … doge +47%).
- **Venue (Greg's TOTAL-$/hr frame — maximize OUR $/hr, rebate size and venue volume are only inputs):** primary-source verified — **Bybit MM Incentive Program = the reachable rebate** (−0.1…−1.25 bps; qualifies on maker SHARE ≥0.03% = an email application, NOT a volume wall). Tape (venues' own APIs): SOL Bybit ~$47M/hr vs Coinbase ~$4.7M (10x), ETH ~$111M vs ~$10.7M; Backpack ~$1M; Bitfinex zero-fee ~$0.05M = flow-dead (best per-trade, worst per-hour). **Bybit standard maker +2bps = our edge NEGATIVE → the MM program is the VIABILITY gate there; past it the 10x tape is the money.** Greg action: send the application.
- **Job 3 LIVE:** `bybit_book_collector.py` (same row schema — pipeline reads venue books unchanged; smoke-tested live, SOLUSDT spread 1.24 bps) + `bybit_book_collectors_durable.yml` on the DEFAULT branch (cron 0 */6, SOL+ETH → `data/{sol,eth}-bybit-book`). The venue-cell measurement = S52 Job 2.
- **v2 QUEUE-HONEST fill (in `_capacity_model.py`):** v1 front-of-queue / v2 back-of-queue (minus best-level size ahead) = the truth bracket. **v2 mk0: 4/5 cells' ceilings NEGATIVE (Coinbase-without-rebate does not print worst-case); −1bp flips every cell positive; deep books win under queue-honesty — ETH overtakes SOL (44% vs 20% legs fillable).**
- **Scale-in / one-legged (Greg's picture):** the deployed executor IS his design (verified: 0 overlapping legs/5,376; off-side never shown; entry 0.69 bps from turn; 99.8% maker closes). Scale-in variants FALSIFIED: losers soak ~2x the opposing flow of winners (S45 adverse selection re-confirmed); mark-to-close scale-in $ = fiction (inventory 4–20x exit flow); the netting sim's REVERSED control beats conviction at mk0 → front-of-queue sims reward volume not signal. Re-test only on the venue book + queue model.
- **Size cap FALSIFIED on the forward ledger** (25,845 trades, mk0 AND +1bp, matched-capital): net rises monotonically to the existing `hi_clip=4.0` — tightening loses money. No change.
- **Pipeline 4x, bit-identical:** `load_book` 1.9x (prefix sums K<8, np.sum kept at K=10, captures spread) + single-parse reuse (`build_channels(raw=)`/`median_spread_bps(raw=)`). Old-vs-new: 7,241 trades, 0 differing fields; 142.7s→39.5s/cell. Money-neutral by construction.
- **NEXT (S52):** (1) sizing-on-winners accounting (Greg Job 1); (2) Bybit venue-cell measurement on the accruing books; (3) MM application (Greg). DEAD adds: cap-tightening; mark-to-close scale-in; front-of-queue sims as validators.

## S50 UPDATE (2026-07-01) — DOLLAR-capacity model: the edge is THIN → the deploy lever is a REBATE VENUE, focus SOL (read `S50_CAPACITY_FINDINGS.md`, `KICKOFF_2026-07-02_S51.md`)
- **Resumed S49 after a container restart — verified nothing lost.** S49's 2nd-window gate (PASSES all 5 cells OOS; conviction sizing wired leakage-clean into `odcore.swing_maker.size_legs`) was committed at `a0be673`; re-ran the mandatory leakage gate end-to-end → **OVERALL PASS** (clmx + size axes, all 5 cells). The gate that blocked the thread since S46 is DONE.
- **Built the DOLLAR-capacity model (`scripts/_capacity_model.py`):** real legs from the deployable pipeline, fill bounded by ACTUAL opposing flow per leg. **Greg caught a coding issue (confirmed):** summing flow over the WHOLE hold made SOL's uncapped ceiling spuriously −$204/hr (losing legs flood the fill side for the whole leg); a fixed per-turn position fills NEAR THE TURN and holds → bounding to a 1s entry window (`FILL_W=10`) flips it to **+$19/hr** (corr(cap,net) −0.123→−0.025 = small residual adverse tilt only). **Corrected (mk0, flat, conservative 1s window): SOL +$19/hr, DOGE +$9, XRP +$6, ETH ~$0, BTC −$5.** SOL leads but absolute $ are SMALL.
- **WHY small + what scales it (Greg "$19/hr seems low"):** (1) **conviction sizing is only ~+25%**, not a multiplier — `corr(size,net)=+0.03`, winners NOT separable from losers at entry (S47 DEAD), so sizing loads *big moves* (half wrong-tail); (2) **$/hr = edge(bps) × passively-fillable notional, and 1.75 bps is THIN** ($100/hr on SOL needs ~$570k/hr passive fills ≈ 11% of one-sided volume). **THE LEVER = a maker REBATE (as bps): a −1 bp rebate adds ~+2 bps/round-trip → ~doubles net/leg → ~doubles $/hr**, same fills, and stacks with a wider-spread venue book.
- **"Same volume to make the same money?" NO** — volume/depth is uneven and doesn't track edge (SOL standout; DOGE 2nd-best net/leg but ~10× less volume; ETH/BTC deep but near-zero spread = thin timing edge). **"Other venues?" UNTESTED** — every book is Coinbase; code is venue-agnostic but edge must be re-measured per venue-cell.
- **DECISIONS (Greg S50):** Coinbase zero-maker tier ($250M+/30d) not realistically reachable → **pivot to a REBATE VENUE** (market-maker-agreement path); **focus SOL initially** (data-confirmed best cell).
- **NEXT (S51):** (1) quantify the rebate scenario (capacity at maker −1/−2 bps — sizes the venue decision); (2) pick 1–2 rebate venues, VERIFY terms from primary sources, collect their SOL book, re-measure spread+fill (per-cell); (3) v2 walk-the-book/mark-to-fill model; (4) wire per-leg size cap + `size_legs`. DEAD: timing retiming, wrong-tail entry-gates, expecting sizing > +25% garnish.

## S49 UPDATE (2026-06-30) — the 2nd-WINDOW GATE PASSES: maker-at-the-turn + cover-grace + two-factor sizing REPRODUCES out-of-sample on all 5 cells; conviction sizing wired into the executor (leakage PASS) (read `S49_SECOND_WINDOW_FINDINGS.md`)
- **THE GATE THE THREAD WAS BLOCKED ON SINCE S46 IS CLEARED.** The book cron rolled the alt branches forward to **06-30 17:01Z** — the alt book now spans **29.2h** (was the single 11.7h S46/S47 window) and the `paper_trade.yml` cron has been auto-accruing the forward ledger. Ran `scripts/paper_trade.py` → +3463 trades (ledger **22,702**). `scripts/_s49_window_confirm.py` segments the deduped ledger at the end of the original window (06-29 23:29Z): W1=in-sample, **W2=fresh/OOS** with FIXED params.
- **REPRODUCES on all 5 cells (W1 net/leg → W2 net/leg OOS):** sol +1.94→**+1.59**, doge +1.42→**+1.28**, xrp +1.33→**+1.02**, eth +0.69→**+0.46**, btc +0.55→**+0.34**. All three S47/S48 claims hold OOS: (1) **net-of-fee positive on every cell** (sign + ranking preserved); (2) **cover-grace holds taker% near 0** (doge 7%, rest 0–1%) — the S48 fix is structural, doge stays profitable; (3) **two-factor sizing adds positive lift on all 5** (+0.15..+0.82/leg, biggest on doge). W2 sits modestly below W1 (real regime softening, not collapse).
- **CONVICTION SIZING WIRED (leakage PASS first, mandatory).** `scripts/_s49_conviction_leakage.py` → `assert_no_leakage` PASS on BOTH axes (clmx_60 quality + size_score) on all 5 cells. Then extracted the two-factor sizing from `paper_trade.py` into **`odcore/swing_maker.size_legs(legs, quality, size_axis, *, alpha, roll)`** + a `SwingLeg.size` field — ONE leakage-clean implementation shared by the script and the per-cell emit path; **bit-identical** to the prior inline pass (max |Δ|=0.0). `paper_trade.py` now calls it.
- **HONESTY:** fill model still optimistic (same both windows → relative reproduction is fair, absolute bps an upper bound); the edge is THIN and **requires maker fee ≤ 0** (a +1 bp maker fee is fatal at 2–4 bps mean swing); two windows is two, not many — but the forward ledger now auto-accrues so the OOS record keeps growing.
- **JOB #2 ANSWERED (the binding deploy gate):** Coinbase Advanced maker fee floor is **0.00% (ZERO), NEVER negative** — reached only at the TOP tier ($250M+/30d) or the fee-upgrade program (≥$500K/mo proof → as low as 0.0% maker); retail tiers are 0.25–0.60% = 25–60 bps (10–30× the 2–4 bps swing → fatal). **No maker REBATE exists on Coinbase**, so S47's rebate column (rescues XRP/ETH) needs a DIFFERENT venue. Deployable scenario = **mk0/tk5 (zero maker)**, which cover-grace clears on all 5 cells OOS — but mk0 on Coinbase requires the top VIP/upgrade tier. **Greg decision:** deploy is gated on EITHER (a) Coinbase zero-maker tier, OR (b) a rebate-paying venue (then the rebate column returns).
- **NEXT (S50):** (1) **pick the deploy venue path** (Coinbase zero-maker tier vs a rebate venue) — the binding gate; (2) wire `size_legs` into the per-cell **emit path** (a sizing analogue of `odcore/quiet_registry.py`: per-cell alpha/roll + deploy flag) once a maker≤0 venue is secured; (3) keep watching the auto-accruing ledger (3rd/4th window). DEAD: timing retiming, wrong-tail entry-gates, spread/dive as timing.

## S48 UPDATE (2026-06-30) — job #2 DONE: COVER-GRACE cuts the taker rate to ~0% and lifts net-of-fee on ALL 5 cells (DOGE flips losing→profitable on execution alone). 2nd-window gate still open (read `S48_TAKER_CUT_FINDINGS.md` + `KICKOFF_2026-07-01_S48_UNBLOCK_CHECKLIST.md`)
- **Harness landed STALE** (S37-era s48 branch); ff-merged the designated branch up to the S47 tip `e4a5f51` (clean, 84 commits, 0 lost) — `paper_trade.py`/`swing_maker.py`/`flip_detector.py` + S47/S48 docs now present.
- **Job #0 (paper run):** +0 new trades — the alt book branches have NOT rolled past S46/S47's one 11.7h window (06-29 11:49→23:29). Collection cron is ALIVE (a scheduled `book_collectors_durable` run is in_progress; pushes only at the end of its 5h50m run) — a fresh window is coming, just lagged. **So the 2nd-window gate (THE gate before sizing for real) stays OPEN; everything below is one window.**
- **Job #2 (cut the taker rate) — DONE, the durable result.** The forced-taker flatten (cover quote doesn't fill before the next turn → cross spread + pay taker) was the cost sink: doge 36%, xrp 12%, sol 8%, eth 7%, btc 4%. FIX = **COVER-GRACE** (`simulate_swing_maker(cover_grace=cells)`, opt-in, `0`==prior bit-identical): rest the maker cover up to `grace` cells past the turn, take the first opposing trade as a MAKER (earn the half-spread) before resorting to taker; cover-only (no late entry), inventory capped, intervening flips skipped (`hold_until`). Faithful to the existing fill model. **Per cell, net-of-fee mk0/tk5, flat sizing:** sol +3053→**+3795** (tk8→0%), **doge −510→+1011 (LOSING→PROFITABLE, tk36→2%)**, xrp +1208→**+2371**, eth +654→**+1324**, btc +2434→**+3689**; win% up on all 5; mean hold barely moves (inventory contained). Monotone in grace, saturates ~G=300 (30s); doge wants 600. Per-cell GRACE map wired into `paper_trade.py`; ledger RE-SEEDED under the grace executor (old G=0 seed was the same one window).
- **Honesty:** the win is mostly STRUCTURAL (swing the half-spread from paid→earned + save taker per converted leg) so more robust than a signal edge, but the fill model is optimistic (same as production) and the falling-knife downside is window-dependent — the **2nd window must confirm** (esp. doge G=600 in a trendier regime). This is EXECUTION mechanics, not a sizing/signal claim, so it's safe under "never tune off one window."
- **Greg actions to unblock (checklist doc):** (1) let the in-progress book cron finish / Run-workflow for a fresh window (my token = 403 on GHA dispatch); (2) place `paper_trade.yml` on the DEFAULT branch so the forward ledger auto-accrues; (3) connect Render/AWS for off-git storage (the durable fix; Render MCP still 400/unauthed).
- **NEXT (S48 cont. / S49):** 2nd-window confirm (THE gate) → confirm maker fee ≤0 venue → then wire conviction→SIZE (`assert_no_leakage` first) into `simulate_swing_maker` + per-cell emit. DEAD (don't re-chase): timing retiming, wrong-tail entry-gates, spread/dive as timing, stacking net-screened levers onto climax.

## S47 UPDATE (2026-06-30) — entry-timing & wrong-tail-GATING are DEAD; the edge is two-factor conviction SIZING (climax × size-axis); net-of-fee survives on SOL/BTC only with maker fee ≤ 0 (read `SESSION_HANDOFF_2026-06-30_S47.md` + `S47_SIZING_FINDINGS.md`)
- **The kickoff's two "remaining edges" both DIED on examination; the real edge came from Greg's live steers (size-don't-gate; spread/DEPTH as levers).** All PROVISIONAL on ONE 11.7h window (== S46's; the rolling alt book hadn't advanced — reproduces S46 byte-identical), per-cell, vs a random-tilt control. DO NOT size until a 2nd window.
- **Entry timing (job #2) — DEAD.** Built `odcore/flip_detector.retime_flips` (causal early-arm + price-reversal; leakage PASS; OFF by default; `eps→inf`==`detect_flips`). Entries already near-optimal: peak-before lag ~2 bps, median off-top ≈ half-spread, price flat at the turn (1–2 bps over 1–2s = S40 symmetry). The "6–10 bps off the top" was a ±300-window artifact (neighbouring swings). Lagging tail = irreducible causal limit.
- **Wrong-tail GATING (job #4) — DEAD 3 ways.** The losing ~26% are NOT separable at entry (every causal feature ~0.53 AUC; only look-ahead distinguishes them — they're bigger swings that happened to continue). Dipole-exhaustion gate (anti-predictive), climax-volume gate (removes winners, total halved), adverse-excursion STOP (cuts winners that reverse) — **all LOSE total net.** Gating subtracts; **sizing adds** (Greg). Wrong-tail is IRREDUCIBLE.
- **TWO-FACTOR conviction SIZING = THE EDGE.** Keep every trade; SIZE up the high-conviction turns. Two axes (per-cell corr screen): **SIZE axis** (predicts |move|, sign-consistent on ALL 5 cells): vol_60, volat_120, runup, **dive_depth=|lean@pivot| (Greg's S40 depth→size, reproduced STRONGER)**, clmx_60. **QUALITY axis** (predicts win/lose): **only clmx_60**. The other levers' sign-"inconsistency" is a TARGET artifact (consistent on SIZE, not NET). **E[net]=P(reversal)·E[|move|] → size by rank(clmx)·rank(size-axis):** matched-capital total-net lift vs random **SOL +3.6σ, DOGE +3.2σ (size axis activates it), BTC +2.2σ; XRP/ETH null.**
- **Job #5 net-of-cost — RAZOR-THIN + FEE-CRITICAL.** Mean swing 2–4 bps → **even a 1 bp maker fee is fatal** (all cells negative at mk1/tk5). REQUIRES **maker fee ≤ 0.** At realistic mk0/tk5: **SURVIVES on SOL (+1.68) & BTC (+0.47)** (sizing improves net-of-fee); **DOGE dies** (47% forced taker exits = execution, not signal); XRP marginal, ETH negative; a maker REBATE rescues XRP/ETH. **Deployable net-of-fee: SOL/BTC with maker≤0.**
- **PAPER TRADING set up + seeded (Greg: "bring them all into paper trades").** `scripts/paper_trade.py` runs the causal executor + two-factor sizing (CAUSAL rolling normalization) on ALL 5 cells, net-of-fee, appending to `paper_ledger.jsonl` deduped by (cell,ts) so runs ACCRUE A FORWARD record (the real multi-window test). Seed (mk0/tk5, flat→sized): sol +3053→+4314, btc +2434→+3618, xrp +1208→+1662, eth +654→+1153, **doge −510→+16 (sizing rescues it)** — causal sizing lifts net-of-fee on ALL 5 cells. `.github/workflows/paper_trade.yml` = cron, auto-fires only once on the DEFAULT branch (Greg; token can't dispatch GHA); else run per session.
- **NEXT (S48, `KICKOFF_2026-07-01_S48.md`):** (0) **run `paper_trade.py` each session + read the accruing ledger** (the forward test); (1) **2nd-window confirmation** (THE gate — re-fetch once the rolling book advances; does the SOL/BTC lift + fee-survival reproduce? don't size until yes); (2) **cut the taker rate** (the doge lesson — forced taker flattens are the cost sink); (3) causal-rolling-normalize the conviction + `assert_no_leakage` + **wire conviction→SIZE into `simulate_swing_maker`** (the job-#3 scale-in) + per-cell emit; (4) confirm maker≤0/rebate is real. DEAD, don't re-chase: timing retiming, wrong-tail entry-gates, spread/dive as TIMING, stacking net-screened levers (dilutes). Books load GZIPPED (no `gunzip`); `pip install matplotlib`, `MPLBACKEND=Agg`.

## S46 UPDATE (2026-06-30) — WIRED maker-at-the-turn to Greg's full spec; leakage PASS; all 5 cells net+; wrong-tail gate marginal (read `SESSION_HANDOFF_2026-06-30_S46.md`, `KICKOFF_2026-07-01_S47.md`)
- **Built `odcore/swing_maker.py` (the S46 job).** One-sided maker-at-the-turn executor, corrected LIVE by Greg (3 screenshots from the S45 chat): post ONLY the conviction side (best BID valley + all the way UP = long; best OFFER peak + all the way DOWN = short; at the peak the offer fill sells the long AND goes short); **"have the BEST bid/offer" = FRONT OF QUEUE** (price improvement, fill on the first real opposing trade) — load-bearing (joining the deep SOL book fills <10% and bleeds to taker; at the front it's a MAKER); **NO time/climax windows** ("the time windows are irrelevant" — the quote rests the whole leg, capped at the next turn); **taker is the LAST option** (only when no opposing trade before the next turn). Direction = the validated CAUSAL flip detector (S40 W=60/REV=0.10 scaled to W=600 on 100ms); QuietFloor confirms the shock.
- **Leakage PASS** (`assert_no_leakage` on the flip signal, 0 fails). **Walk-through (`_render_trades.py … swingwalk`): the same 10 S45 floor trades — loser #1 BID −9.98 → SHORT +12.66 (maker); every old BID-into-a-peak loser inverts; the +15.16 peak → SHORT +18.46.** **Per-cell (gross/leg, all net+, PROVISIONAL one 11.7h window):** sol +2.19 (90% maker, win 74%), doge +1.12, xrp +1.01, eth +0.40, btc(control, 0.0008 half-sp) +0.60 on pure SWING capture. net/leg tracks half-spread (edge ≈ spread capture) except btc (timing carries).
- **Wrong-tail exhaustion gate (`entry_gate` via `info_dipole.divergence`) built + A/B'd → MARGINAL** on this window (SOL net/leg +2.19→+1.99, win 74→71%, taker 81→52, big-swings 5→8) — the dipole divergence doesn't cleanly isolate the ~36% no-reversal tail here. KEPT OFF by default; revisit as data accrues.
- **CAVEATS:** front-of-queue assumes best-price priority + credits the full half-spread; mean swing ~2–4 bps (most below the 20bps fee floor); ALL numbers ONE window — do NOT size. **NEXT (S47): confirm on a 2nd window FIRST**, then scale-in modeling, climax-volume wrong-tail gate, true net-of-fee. Tools: `odcore/swing_maker.py`, `_render_trades.py` (`swing`/`swingwalk`/`exhaustion_gate`).

## S45 UPDATE (2026-06-30) — decisive maker test on the multi-coin book; fill autopsy pins the bleed on adverse selection; flip filter was wired backwards; THE STRATEGY = maker-at-the-turn / asymmetric conviction quoting (read `SESSION_HANDOFF_2026-06-30_S45.md` + `STRATEGY_maker_at_the_turn_S45.md`; S46 = wire it)
- **THE DECISIVE TEST RAN (NEXT #2).** Alt books accrued (cron pushed `data/{eth,sol,doge,xrp}-book` ~23:30 UTC 2026-06-29, ~11.7h/420k rows each; btc 46.7h control). `_maker_deploy_map.py` on all 5 cells. **btc-locked operator (K=10) does NOT transfer** — all alts `rebate` (sol −0.45, doge −0.65, xrp −0.45). NOT a kill: per Greg, the btc operator failing IS the per-cell signal to find each coin's own operator.
- **PER-CELL OPERATOR = the fix (`_gate_param_sweep.py` per coin): the thin alt books carry their depth-imbalance signal at TOP-OF-BOOK (K=1), not the deep K=10 btc wants.** Re-ran with per-cell K (`PER_CELL_K` in `_maker_deploy_map.py`): direction hit jumped (sol 62→81%, xrp 61→79%), side-filter edge turned positive (sol fav−anti −0.02→+0.20, doge −0.05→+0.42), and **DOGE flipped NET+ before rebate (+0.037)** — existence proof a wide-spread cell clears with its OWN operator. sol/xrp/eth improved but stay just negative (within a maker rebate). **PROVISIONAL: one 11.7h window, small fill counts (doge 55) — do NOT size off it.**
- **FILL AUTOPSY (`_dissect_fills.py`, Greg's "dissect the firing trades").** `gross/fill = half_spread + drift`; `drift = d_wait(post→fill) + d_hold`. SOL: half_sp +0.67, mean drift −0.97 (d_wait −0.93 dominates) → gross −0.30; mid moves AGAINST us 58.6% of fills. **ROOT CAUSE = adverse selection in the QUEUE WAIT:** a passive quote fills only when flow is against it (a bid fills because sellers press → mid dropping while you queue). The gate fires on an imbalance SHOCK = a turn OR a falling knife, indistinguishably. Renders (`_render_trades.py`, swing-diagram style, PNGs gitignored): all losers are "Buy long" posted into a downtrend; the +15 bps winner is "Sell short" at a peak that rolls over.
- **ARE WE USING THE DIPOLE FLIP DETECTOR? NO.** The maker path imports only `quiet_floor.gated_signal`; the validated S36 FLIP detector (`odcore/flip_detector.py` / `odcore/info_dipole.py` divergence+exhaustion, 64% reversal) is NOT wired in (`incremental.py` only mentions it in a comment). Wired a first floor+flip combiner (`_maker_flip_floor.py`) but it made things WORSE.
- **THE FLIP WAS WIRED BACKWARDS (Greg: "it's how we code it"; `_flip_debug.py`).** Gating on `opposing` (book AGAINST the move = the S36 reversal condition) bled (sol −0.86) — for a passive maker that means posting into the flush. Splitting gated test fills by condition: `confirming` (book WITH the move) gross **+0.745** vs `opposing` −0.863, consistent on all 4 cells; `confirm+exhaust` +0.91 → sol/doge/xrp NET+ (eth can't, 0.03 bps spread). The S36 detector predicts REVERSALS (a TAKER concept); a hold=1 maker wants CONTINUATION. Direction stays `sign(imb)` (follow ≫ fade, all cells); only the flip POLARITY flipped.
- **THE REAL FIX = MAKER-AT-THE-TURN / asymmetric conviction quoting (Greg, S45; spec `STRATEGY_maker_at_the_turn_S45.md`).** A symmetric two-sided passive maker is at the counterparty's mercy (the adversely-selected victim). Be a maker ONLY at the turns, ONE-SIDED: at a PEAK (flip=top) post the best OFFER + pull the bid → euphoric BUYERS lift it → you're SHORT the top (maker, +spread); ride down keeping the best offer, bid PULLED (no knife-catching); at the VALLEY (flip=bottom) post the best BID + pull the offer → capitulation SELLERS hit it → you cover the bottom (maker). BOTH legs maker, spread captured both turns, never cross it (taker only as fallback). The aggressor (S40 climax ~2x vol AT the turn) is the adversely-selected victim on BOTH ends. Loser #1 proves it: at that peak we posted a BID (−9.98); maker-at-the-turn posts the OFFER → short the top → cover the valley ≈ +16. NOT YET WIRED — it is a different execution model (position state machine + one-sided quoting + hold-to-next-turn); the hold=1 confirm/opposing numbers do NOT apply to it. This is the S46 build.
- **TOOLS (S45):** `_dissect_fills.py` (per-fill autopsy), `_render_trades.py` (swing renders, +confirm/opposing modes), `_render_one.py` (single-loser blow-up + signal-value explanation), `_maker_flip_floor.py` (opposing — flip to CONFIRMING), `_flip_debug.py` (per-condition autopsy), `_hold_sweep.py`. Renders committed in `docs/renders/`. All PROVISIONAL on one 11.7h window (tiny fill counts).
- **BRANCHES:** harness landed on stale S37 + collector commits on `s45-y2ni2m`; merged canonical `5c5vg9` in; pushed S45 work to `s45-y2ni2m` AND fast-forwarded `5c5vg9` + `-kb2i5c` to the same tip (all three unified/synced).

## S44 UPDATE (2026-06-29) — multi-venue/multi-coin book collectors built (NEXT #1) + QuietFloor gate wired into the live book dipole (NEXT #4) (read `SESSION_HANDOFF_2026-06-29_S44.md`)
- **BRANCH/HYGIENE:** harness again landed on the stale S37 branch (`claude/crypto-liquidity-signals-5c5vg9-kb2i5c` at `7256abd`); fast-forwarded it to the canonical S43 tip `30d2425`. Dev/push on BOTH `-kb2i5c` (harness-designated) and `claude/crypto-liquidity-signals-5c5vg9` (canonical, per the drop-in). Greg's S44 call: "do multi coin then wire quiet floor."
- **NEXT #1 (THE bottleneck) — multi-venue/multi-coin BOOK collectors built.** The book existed for btc_coinbase only and the maker model is SPREAD-STARVED there (1-tick book). Built `coinbase_book_collector.py` (symbol-parameterized generalization of `coinbase_btcusd_book_collector.py`, same WS protocol + row schema) and a unified matrix workflow `book_collectors_durable.yml` (btc/eth/sol/doge/xrp → Coinbase, per-coin `data/<coin>-book`, gz anti-clobber guardrail). SUPERSEDES `book_collector_btc.yml` (deleted — pointed at a dead branch + would double-push `data/btc-book`). **Live smoke-test: SOL-USD half-spread ≈ 0.69 bps vs BTC's 0.0008 bps (~860× wider)** — confirms the alts are exactly the wider-spread cells NEXT #2's maker test needs (half-spread 2–5 bps ≫ ~0.5 bps adverse selection). **STILL NEEDS GREG'S MANUAL GHA TRIGGER** (token 403s on workflow_dispatch): Actions → "Book Collectors (BTC/ETH/SOL/DOGE/XRP, durable)" → Run workflow on `5c5vg9`. Data accrual is the only remaining gate on NEXT #2/#3.
- **NEXT #4 — QuietFloor gate WIRED into the live dipole (per cell, leakage-safe, hot-path-ready).** New `IncrementalQuietGate` (causal O(1)/tick port of `QuietFloor`) + `RollingFlow.gated_signal()` hook (`odcore/incremental.py`); `dipole_gated` generator registered in `odcore/generators.py`; per-cell driver `_wire_quiet_gate_book.py`; canary `_canary_quiet_gate.py`. **CANARY FINDING (load-bearing):** on TRADE-flow ofi the floor degenerates (quiet cells have zero flow → phi≈0 → near no-op); the relaxation edge lives in the resting-size **book DEPTH imbalance** (phi_q≈0.95 between trades), so the gate is wired on the depth channel. **On btc_coinbase book (1.68M cells, 46.7h): raw level fires 100% of cells → gated fires 6.9% (stands aside 93% — stops churning through trends); gate opens 2.54× more on shock vs quiet cells; OOS next-cell direction hit 69.8%→70.9% retained; IncrementalQuietGate bit-faithful to batch on all 1.68M cells.** Deploy form = gate (WHEN) + level sign (DIRECTION); per-cell, ready for the multi-venue book the new collectors feed. Result `_wire_quiet_gate_book_results.json`.
- **DISCIPLINE:** OD-BOOK `.ttest_committed.json` sentinel untouched (KILL still frozen). Existing `_canary_incremental.py` still PASS (RollingFlow gate is opt-in, backward-compatible). NEXT: Greg triggers the book matrix; then re-run `_maker_fill_model.py` + `_wire_quiet_gate_book.py` PER CELL on the wider-spread alts (the decisive deploy test).


## S43 UPDATE (2026-06-29) — OD-BOOK gated T_test = KILL (fee-floor, not signal) + maker-fill/queue model built (read `SESSION_HANDOFF_2026-06-29_S43_ODBOOK.md`, `KICKOFF_2026-06-29_S44.md`)
- **BRANCH/HYGIENE:** harness landed on the STALE S37 branch `2txotq` (the recurring wrong-branch landing) — switched to the canonical S43 tip `claude/crypto-liquidity-signals-5c5vg9` and dev/push there; `crypto-backfill-validation-31tubb` fast-forwarded to match (`46f09ea`). Book data on `data/btc-book` kept accruing via the GHA: **46.7h → 1.68M cells** by session end (still btc_coinbase ONLY — single cell, so everything stays CHARACTERIZATION). Re-extract: `git show <ref>:btc_coinbase_book.jsonl.gz | gunzip > /tmp/od_book.jsonl.gz`.
- **OD-BOOK gated T_test RAN ONCE (NEXT #5; `research/od_book/run_experiment.py --commit-ttest`, sentinel frozen) → VERDICT KILL.** On the multi-day book (1.26M states @ run time, 45-dim x(t), 100ms): **leg 1 PASS** (OD DMD r43 BEATS the VAR(3)/ridge champion on mid-price R² at all 3 horizons OOS — the strong linear model overfit val and went negative on test; the rank-truncated operator generalized), **leg 3 PASS** (operator stable, top-k spectral drift 0.040 ≪ 0.15), **leg 2 FAIL** (turn-net-of-22bps both −39.6 bps). Miss any leg → KILL. This is anticipated **KILL-mode #2** (prettier forecast, no edge after fees), NOT mode #1. **Salvage:** DMD operator wins mid_price (all horizons) + spread (h10) and is stable → reusable as a feature/gate; the validated dipole *detector* stands; **threads 2/3 NOT built.** Result `research/od_book/od_book_result.json`, sentinel `.ttest_committed.json`.
- **LEG-2 POST-MORTEM (Greg: "not going to kill it yet, dive into why"; `_leg2_diagnosis.py`):** leg 2 fails ENTIRELY on the taker fee floor, NOT for lack of signal. Predicted forward moves are **~0.11–0.16 bps at p99 (h=1)** vs a **22 bps** round-trip taker fee (~140× gap). gross PnL is **positive** (+0.14 bps/flip champion, +0.30 challenger) but 15k–33k flips × 22 bps swamps it; the tuned db=5 → 2 flips → −39.6 (reproduces the gate). **No taker deadband works** (raising it just stops trading). **Execution counterfactual: fee=0 → net=gross +~4600 bps over 18.7h, both models positive**; challenger (DMD) is ~half as churny as VAR (15k vs 33k flips, 2× gross/flip) — an OPTIMISTIC upper bound (no adverse selection/queue), so it motivates the maker model, not a deploy number. **Fixed a real bug in `metrics.label_turns`** (direction=0 fired both branches → always 0 turns; now independent hi/lo → 12 swings ≥22 bps over 18.7h, median 49 bps, matching S42). Diagnostic-only field; gate leg 2 scores swing PnL, so the frozen verdict is unaffected.
- **NEXT #3 BUILT — maker-fill/queue model (`odcore/maker_book.py` portable + `_maker_fill_model.py`):** honest queue (join the BACK of the displayed best-level queue; fill only when cumulative OPPOSING taker volume in a 1s window clears it) + adverse selection (limit price fixed at post, mark-to-mid at fill+hold). QuietFloor fit on train quiet cells; arms on held-out 40%. btc_coinbase half-spread **0.0008 bps** (1-tick book). Findings: unconditional making **bleeds ~0.5–0.8 bps/fill to adverse selection**; the signal IS a real adverse-selection filter but **weak** (`fav − anti = +0.068 bps/fill`); the **QuietFloor gate is the best lever — cuts ~30% of the per-fill loss** (−0.64 → −0.44 @hold5; −0.32 @hold1, shortest hold best). **No standalone net edge before rebate** (breakeven ≈ −0.32 bps/leg; Coinbase doesn't pay it). **The binding constraint is the ABSENT SPREAD, not the signal** — a 1-tick book gives ~0 half-spread capture; on a wider-spread cell half-spread (2–5 bps) ≫ adverse selection (0.5 bps) and the gated signal-as-filter should clear. The model is the deploy tool; it needs cells where the spread pays.
- **NET READING:** the book's tradeable content is a MAKER/quoting signal below the taker fee floor (confirms S42). The taker dynamics-recoverer is KILLED; the maker thread is **NOT falsified** — it is spread-starved on btc_coinbase and awaits multi-venue/multi-coin book.
- **NEXT (S44):** (1) **multi-venue/multi-coin book = THE bottleneck** — Greg's manual GHA run of `book_collector_btc.yml` + clone the collector to other venues/coins; (2) **re-run `_maker_fill_model.py` PER CELL once wider-spread book exists** — the decisive deploy test (half-spread should dominate adverse selection there); (3) re-run `_liquidity_dive.py` + fit `QuietFloor` per cell; (4) wire the QuietFloor gate into the live dipole (gate=when, level=direction).

## S42 UPDATE (2026-06-23) — LIQUIDITY DIVE: book imbalance is a real OOS next-move predictor + the QUIET FLOOR gate (read `SESSION_HANDOFF_2026-06-23_S42.md`, `KICKOFF_2026-06-23_S43.md`)
- **BRANCH:** `claude/crypto-liquidity-signals-5c5vg9` (S37 HEAD was a clean ancestor of S41's `crypto-backfill-validation-31tubb`, so fast-forwarded all S38–S41 work on with no divergence, then this session on top). Book file extracted to `/tmp/book.jsonl.gz` (gitignored): btc_coinbase, **420,215 records, 100ms, 11.67h** (bigger than the 5.83h S41 quoted), 3 gaps >1s. Single cell only -> everything is CHARACTERIZATION, NOT deploy-grade.
- **THE LIQUIDITY EDGE S41 MISSED (`_liquidity_dive.py`):** S41 found flow↔price NULL but used `abs_return` (magnitude) and never tested liquidity *dynamics*. Adding the SIGNED return + dynamics surfaces it: **`depth_imb` (book-depth imbalance, top-K=5) predicts the SIGNED next move — OOS_r +0.164 next-cell, circular-shift null_z +60, 63.1% directional hit** on a 40% held-out test; decays with horizon (62%@0.5s … 55%@5s). Two-sided xcorr: imbalance **LEADS price +0.1s** (lead side > lag side) = genuinely predictive, the canonical top-of-book-imbalance next-tick signal recovered OOS. **PART A (agnostic 5-step coupler, 10 slices): depth_imb~signed_ret survives the tautology null in 7/10 slices, LEADS +0.08s — a stable property, NOT S41's single-window fluke.** Flow→price stays weak (≤4/10, low z). `d_total_depth` (symmetric withdrawal) is NULL for direction — content is in the IMBALANCE; one-sided depth (`d_bid_depth`+/`d_ask_depth`−) are symmetric echoes.
- **NET-OF-COST (honest):** moves are sub-bp where the hit-rate is high (0.06 bps next-cell @63%; ~1.3 bps @5s @55%) << Coinbase ~50–80 bps round-trip. So this is a **MAKER/quoting signal** (which side to post, when to pull), NOT a taker strategy — real OOS edge, below the active fee floor. Reconciles S41 (flow↔price NULL holds for *magnitude*; directional coupling lives in imbalance vs *signed* return).
- **QUIET FLOOR GATE (Greg's directive on Chat's OD run; `_quiet_floor.py` + `odcore/quiet_floor.py`):** Chat found book imbalance obeys a clean AR(1) RELAXATION, quiet/still between trades. Reproduced: **φ_quiet=0.944** (Chat 0.947), quiet OOS-R2 0.76 > trade 0.62. Use it as a FLOOR so the dipole stops firing while trend-following. Floor `floor_hat=φ_q·imb(t-1)+c_q`; innovation `innov=imb-floor_hat` absorbs the between-trade relaxation (std 0.15 quiet vs 0.22 trade; raw level 0.38 in both). **Direction lives in the LEVEL** (innovation alone dilutes hit 61.6→57.4%), so **use the floor as a GATE**: fire only when `|innov|>k·σ` (a shock breaks the floor). At k=1.5σ the gate opens **7% on quiet cells vs 16% on trade cells (2.3×)** — silent between trades, fires on shocks — and gated direction keeps **62% hit** (k=2σ sharpens to 62.7%). Raw level holds "on" ~15% of all cells continuously (the churn). **Between-trade firing cut, direction kept.** `odcore/quiet_floor.py` = portable, leakage-safe `QuietFloor` (fits φ_q + gate σ on TRAIN quiet cells only), causal `floor_hat/innovation/gate/gated_signal`; fit one per cell.
- **NEXT (S43):** (1) **more book data = the bottleneck** — `book_collector_btc.yml` GHA needs Greg's manual run; add venues/coins; (2) re-run `_liquidity_dive.py` + fit `QuietFloor` PER CELL once multi-cell book exists; (3) maker-fill/queue model to monetize the sub-bp predictor net-of-rebate; (4) wire the QuietFloor gate into the live dipole (gate=when, level=direction); (5) OD-BOOK T_test when book is multi-day.

## S41 UPDATE (2026-06-22) — book-layer (liquidity+flow+price) lead/lag + 5-step coupler runs on the btc_coinbase book (read `SESSION_HANDOFF_2026-06-22_S41.md`, `KICKOFF_2026-06-23_S42.md`)
- **DATA:** `data/btc-book` -> `btc_coinbase_book.jsonl.gz`, 209,998 records, 100ms, 5.83h, 0 gaps >1s; per record `ts, mid, spread, bids[[offset,size]×10], asks[[offset,size]×10], buy, sell, n_trades` (liquidity + flow + price on one grid). Chat external run saved at `research/od_book/chat_runs/OD_book_run_1.docx`. BUILD_PLAN S37–S40 folded in (commit 0c2f511).
- **Lead/lag on the book (`_birth_probe.py`, cross-corr ±5s + event-aligned at 168 onsets):** LIQ→FLOW peak r≈+0.14 at +0.7..0.9s (K=1..10); LIQ→PXV r≈+0.12 at +0.1s; FLOW→PXV r=+0.106 at 0.0s. Event-aligned means: LIQ(K5) pre-onset +0.170/post +0.029; FLOW pre +0.072/post +0.246.
- **Full 5-step coupler rolling (`_rolling_coupler.py`, `trade_coupling_vector`, win 5min/step 30s, 690 windows; a=signed depth-imbalance K5, b=price return):** leadlag>0 (a leads b) 75.5%, <0 2.8%, =0 21.7%, mean +0.07s. corr(leadlag, quiet_frac)=+0.058, vol=−0.043, relax_r2=+0.002.
- **OD coupling discriminator on book pairs (`_od_book_run.py`, windowed_operator_matrix + analyze_coupling + PySR):** structured=False on all 4 pairs. buy/sell eq_entropy_frac 0.660 / mi_frac 0.012; bid/ask mi_frac 0.9997 mi_slope_r2 0.011; bid/buy mi_frac 0.999 mi_slope_r2 0.038; buy/absret eq_entropy 0.812. PySR: H_a^2→square(H_a) (degenerate, H_a in features); MI no functional family (flow MI~(H_a·H_b)³ loss 0.795 vs const 1.023; liquidity MI~0.548 const; flow-price MI~0).
- **Dipole trend-following (`_dipole_trend_follow.py`, position=sign of trailing-300s lean, hysteresis, fee 10bps):** gross negative all thr — btc_bybit_perp gross −398..−1479 (buy-hold +148), eth_bybit_perp gross −610..−1929 (buy-hold +111).
- **buy/sell mirror (`_diag_flip_states.py` reproduced):** leave-one-out 63.5% (n=1400); margin vs flow-strength corr +0.019..−0.043.
- **Agnostic 5-step scan (`_coupling_scan.py`, no imposed direction):** score_pair (5 steps + circular-shift tautology null) over 15 book-channel pairs; results in `_coupling_scan_results.json`.
- **Chat run (`research/od_book/chat_runs/OD_book_run_1.docx`):** linear AR(1) X[t+1]=φX[t]+c, OLS, 60/40 OOS, rolling 3000/300. imb(t+1)~imb φ=0.936 OOS R²=0.865 half-life 1.05s; ret(t+1)~{imb,top_imb,ofi,ret} R²=0.044; quiet (n_trades=0) φ 0.947 R² 0.904 vs trade φ 0.883 R² 0.726; imb→fwd price R² 0.024..0.035; loudness(1−R²) vs realized vol cross-corr 0.51..0.83; operator-stress→fwd-vol | current-vol-removed corr −0.002; loudness-vs-vol local lead/lag operator leads 18.9% / lags 58.9%.
- **METHOD NOTE (Greg, S41):** run the agnostic 5-step coupler and read what it couples; do not impose a direction. When the 5-step coupler is used, all 5 steps run in order (`coupling_scanner.score_pair` / `dipole_trade.trade_coupling_vector`).

## S40 UPDATE (2026-06-22) — AWS done + 14-cell 1-sec coeff basis + per-cell fingerprint + the ANATOMY OF A TURN + the honest edge map (read `SESSION_HANDOFF_2026-06-22_S40.md`, `KICKOFF_2026-06-23_S41.md`)
- **AWS package finished + RUN.** Bedrock IDs in `DEPLOY_AWS §4` (Opus 4.7 GA/Mythos; Bedrock=agent only, FNO=SageMaker GPU, signal core=model-free); `_run_alt_coeffs --save-embeds` persists prefill_embeds (FNO X's); venue-agnostic discovery + `aws/LIGHTSAIL_SETUP.md`. **Greg ran it on Lightsail -> 14-cell 1-sec deterministic coeff basis committed** (bybit x5 coins + kraken x{btc,eth}; coinbase=REST dud). TASK 2 (BTC/ETH 1-sec) DONE.
- **Per-cell DISTINCTIVE fingerprint predictor** (`odcore/fingerprint_predictor.py`): coeff "merge" SOLVED — deterministic decoder = L2norm(mean of magnitude embeds) -> **~91% of every coeff is one shared shape**; distinctiveness = the **centered ~9% residual** ("distinct before" = unique vectors, not separated cosine). **BUY/SELL = perfect mirror (-1.000)** in the residual; whitened/centered STACK beats every single tool. Motivates the FNO upgrade.
- **ANATOMY OF A TURN** (`_turn_*`, `_render_turn`, `_dipole_price_overlay`): capitulation **CLIMAX** at the turn (~2x volume + peak flow in dying dir, then flips); coeff **flips through the turn** (confirms, no lead); **QUADRATIC** (vertex=turn; sharpness != quality); **acceleration LEADS ~3s** (only leading signal, weak); **94-99.6% SYMMETRIC** (mirror=no edge) -> edge is the **ODD remainder, in FLOW (5.7%) not price (0.4%)**; dipole<->price **coupled +0.26 but COINCIDENT**.
- **Causal flip detector** (`odcore/flip_detector.py`, leakage PASS) + harness: **TIMING works (1-4 bps to turn) but net-of-cost LOSES** (over-fires the breakeven middle, gross ~0.2 bps << fees). **dive STEEPNESS gate EXHAUSTED** (-0.13 winners = survivorship -> +0.004 full pop; per-cell ~0).
- **GREG'S CLARIFICATION (load-bearing): the cut is BIG vs SMALL price CHANGE (|swing|), NOT win/lose.** That corrected cut surfaced the **first real swing-size signal: lean DEPTH at the pivot predicts big moves in ALL 4 cells** (corr +0.045..+0.067, full population) — deeper dipole dive -> bigger swing. Weak but consistent + on the right target. (dive steepness=noise; DEPTH=signal.)
- **THREE LESSONS:** (1) never pool sign-blind (buy/sell mirror -> directional signal cancels to ~0 = the anti-symmetry fingerprint; sign-align always); (2) **cut by big-vs-small |move|**, not the ~breakeven middle, not win/lose; (3) winner-only = survivorship -> need the NEGATIVES (dud/small-move turns).
- **NEXT (S41):** predict **|move| (big vs small) per cell via the dipole STATE (lean DEPTH + divergence/exhaustion, NOT dive-steepness)** + coeff fingerprint, on the big-vs-small cut; **loser coeffs** (greenlit, = the separate win/lose question); the swing-size **gate** + **FNO** GPU training; OD-BOOK T_test when book multi-day; **cross-domain falsification** (same turn operator on World Cup momentum around the cooling break — frame, test, don't declare).

## S39 UPDATE (2026-06-22) — coeff-engine UNBLOCK (deterministic tier, in-container) + 1-second standard + free-historical backfill + multi-regime KILL + 600 alt coeffs (read `SESSION_HANDOFF_2026-06-22_S39.md`, `KICKOFF_2026-06-23_S40.md`)
- **THE UNBLOCK (load-bearing):** the production 128-dim `operator_coefficients` (the BTC/ETH fingerprints) are **unit-L2 + all non-negative** = the **DETERMINISTIC decoder tier** (`OperatorDecoder.prefill`=mean of spectral-magnitude embeds, `refine`=L2-normalize), NOT a trained FNO (the manifest's FNO+Bayesian is aspirational). That pipeline is **vendored in markets** (`odcore/od_refrag_adapter.py`; `markets_adapter.py` is the same port w/ `np.fft.rfft`), so **coeff discovery runs IN-CONTAINER — no `E:\refrag`, no torch, no FNO checkpoint.** cs100_v2 config verbatim: 30-min pre-entry window → 1-sec mid → log-returns → `SpectralChunker(192,16)` → `SpectralChunkEncoder(d_enc=128)` → `OperatorQuery.from_spectral_target([0.1,0.25],1.0)` → top_k=8 / expand_budget=4 → `prefill`+`refine(8)` ⇒ 128-dim unit-L2. Reproduced by **signature** (dim/L2/sign/shape); NOT exact-vector (no 05-18 bars) — encoder-summary/expansion variant is the comparability knob. `np.fft.rfft` (vs the pure-Python O(n²) DFT) → full alt cap-100 discovery = **35 s**. `_run_alt_coeffs.py`.
- **1-SECOND IS THE STANDARD (Greg):** minute-bar aggregation smooths away the sub-minute flow that carries the timing edge (S36b). All alt work is 1-sec-native (labeler, oracle exit, micros, coeff pipeline). **OPEN: re-discover BTC/ETH coeffs on 1-sec** for consistency (cheap in-container now).
- **Free-historical backfill** (`backfill_bybit.py` NEW + binance_vision/coinbase/kraken; `backfill_oneshot.yml` 5-coin gzip matrix). Integrity-verified: timestamps integer-second NO shift (overlap test 0.008 bps), taker buy/sell semantics consistent. `realbins/` = 9 cells (5 bybit_perp 21d contiguous + 2 kraken + 2 coinbase gappy).
- **Multi-regime gated-swing KILL (S38):** re-ran `_info_dipole_gated_swing.py` (leakage PASS 9/9) on the multi-regime set — **only 2/9 clear net>0 at maker (both thin); 7/9 stand aside incl. all 5 bybit_perp. The S37 single-window map (+466/+392/+670) was OVERFIT. No capital on this evidence.**
- **Alt winner-labels + coeffs:** 1-sec oracle winners (buy 360/sell 60 min, net 10bps) for 6 sol/doge/xrp bybit_perp cells (~2500-2800 each); **600 coeffs, 100/cell, all source_ids unique, intra-cell cosine ~0.91 (distinct).** **source_id COLLISION FIXED** (S35 class — embed decision_ts; the S38-note "XRP-sell=195" was the STALE collision, real=2564). `_build_alt_winner_labels.py`, `_run_alt_coeffs.py`, `_alt_labels/coeffs/alt_coeff_index.json.gz`.
- **AWS:** no creds/CLI/boto3 in container (endpoints reachable). Greg's call = run heavy jobs on AWS; **Bedrock** is the AWS-native path (Claude Code via Bedrock + Knowledge Bases on S3/RDS) for the agent + GPU **FNO training** (the production-tier upgrade). `aws/` dir created; package is the S40 first task.
- **NEXT (S40):** (1) **build the AWS package** (Dockerfile + S3 discovery runner + Batch/EC2 launch + SageMaker GPU FNO-training path); (2) re-discover BTC/ETH coeffs on 1-sec; (3) wire the per-cell distinctive fingerprint predictor off the coeffs (the S35 goal); (4) pin the exact-comparability knob if cross-cell coeff compare needed. Default-branch sync NOT done (kept to assigned dev branch).


## S58 UPDATE (2026-07-03) — THE ENTRY PIECE: 6 rounds, per-coin verdicts, ETH dropped, KRAKEN kr_mk0 verified (read `S58_ENTRY_NOTES.md` — the round-by-round record — + `SESSION_HANDOFF_2026-07-03_S58.md`)
- **Entry-only discipline (Greg):** 6 rounds moved the mid-band entry from -17..-23 to -1.4..-4 $/hr cb_real (positive gross everywhere, first positive weeks). Entry-alone cannot cross real fees — it hands the per-leg budget to Piece 2 (exit, PARKED until Greg opens it).
- **Five-verdict board:** SOL lead (Coinbase = NAIVE th100); BTC conditional (th80 stack, collector now FIXED + accruing); DOGE remapped (climax-Q4+exhaustion th100 — only flow map to survive its books check); XRP naive-only (stack lift = pooled-window artifact; death-combo anti-print: opposing+climax w/o exhausting = -31..-53bp/leg 4x-replicated); **ETH DROPPED** (books promise = 2 legs of one tape; re-entry test named).
- **MASTER LAW (unanimous, r3 controls + 5 agents): price mechanics port across venues; FLOW READS DON'T.** Nothing flow-based deploys without per-venue books validation. Winners are INVISIBLE to all 6 causal flow reads -> the S35 dual-print fingerprint wire-in (match-winner MINUS match-loser, micros-first) is the winner-side path (spec + preconditions in notes).
- **KRAKEN PRO US SPOT: 0.00% maker at $10M/30d VERIFIED** (primary sources; no application; our cadence clears it; climb $3,905 once; ⚠ schedule changes Jul 9). kr_mk0=0/10 makes the S57 "ceiling-only" column REACHABLE -> **fine band research-REOPENED, Kraken-gated** (4 conditions; fine cadence sustains the tier for all cells). Kraken vol = 35-42% of Coinbase (live). NEXT: kraken book collector (gates everything Kraken).
- Infra: rotation guardrail on all book collectors (S37 cap-stall pre-empted); BTC book workflow repaired (45c145b on crons branch). Round-5 falsification: bounce-fallback rejected; the S56 trough-sell narrative was fine-scale-local. S58 mistakes ledger in the notes file — read before building.

## S59 UPDATE (2026-07-03) — ENTRY PIECE **DONE** (DoD promotion committed) + kr_mk0 re-price + the KRAKEN DATA MACHINE (read `S59_NOTES.md` + `SESSION_HANDOFF_2026-07-03_S59.md`)
- **ENTRY DONE (Greg's call):** `odcore/entry_coinbase.py` (VENUE IN FILE TITLES from now on — Greg) = the round-6 armed mid-band machine promoted verbatim (v2 arming, c-scaled confirm, mode-0 fallback fix, baseline fallback, data-blind pred socket) + `COINBASE_MIDBAND` registry (sol mb100/xrp mb80/doge mb100 naive-k0 ACTIVE, btc mb80 gated on books, eth absent) + truncation-invariance leakage gate; wired into paper_trade as SANDBOX cells through run_stream. CANARY 3/3: bit-identical port on 5 tapes, leakage PASS, baseline DEPLOYED bit-identical (26,784 rows, +0 live). Sandbox forward record accruing via the paper cron (sol_mb100 +418 net bps first window). **PIECE 2 (EXIT) IS OPEN** — R8 lean-collapse first.
- **kr_mk0 RE-PRICE (Pass A paper == Pass B machine):** every surviving member-map config flips POSITIVE at Kraken 0bp maker (~+$6/hr best-per-coin at $5k) — the "entry can't cross fees" ceiling was a COINBASE-FEE statement. XRP asterisk: its th80 books-derived shape is negative on bins even at 0 fee. TWO UNKNOWNS remain (Greg): the Kraken TAPE (thinner volume) and Kraken FILLS — fees are solved.
- **KRAKEN DATA MACHINE both halves live:** `kraken_book_collectors_durable.yml` ALL 5 COINS (6h cron on default branch, rotation+anti-clobber; data/<coin>-kraken-book) = the FILLS truth. `backfill_kraken_trades.py` (REST Trades -> 1-sec bins, paced/resumable, REST pairs XBTUSD/XDGUSD) = the TAPE truth, 30d x 5 pulled. **S60 #1 = machines on the Kraken tape at kr_mk0 per cell.**
- **Fingerprint micros-tier dual-print = CLEAN NULL** (AUC ~0.5, direction-unstable, leakage PASS): winners invisible to the causal descriptor space CONFIRMED at feature level -> the 5th member narrows to the S35 ENCODER tier (onset canary + Greg's E: drive win/lose archives = the gates). No iteration off one window.
- Hygiene: S59 designated branch was AGAIN cut from the default/crons parent — reconcile to canonical `5c5vg9` FIRST every session. Jul-9 Kraken schedule re-confirm queued post-facto; Greg's CFM tier tab read still open; FINE-GRAIN untouched (it returns later).

## S37 UPDATE (2026-06-22) — the S36b data bottleneck DIAGNOSED + FIXED; collection expanded to 5 coins x 3 venues; NEXT #2 gated-swing challenger built (read `SESSION_HANDOFF_2026-06-22_S37.md`; branch = canonical `claude/divergence-exhaustion-backtest-wj65sm`, now == repo default)
- **THE UNBLOCK:** the whole S36b "can't validate on ONE window" bottleneck had a concrete cause — **the durable collectors stalled ~06-14/06-19 because `btc_coinbase_bins.json` hit 103 MB > GitHub's 100 MiB/file push cap** (collect OK, push rejected). FIXED by storing bins **gzipped** on the data branch (104->16 MB; gunzip on restore, gzip on push, gz-aware guardrail; `btc/eth_collectors_durable.yml`). ~6-week runway; off-git storage (S3/Render) is the durable answer (blocked on cloud auth).
- **5 coins x 3 venues now durable in git:** added SOL/DOGE/XRP via generic symbol-parameterized collectors (`coinbase_collector.py`/`kraken_collector.py`/`bybit_perp_collector.py`, exact BTC/ETH bin schema) + matrix workflow `alt_collectors_durable.yml` (per-coin `data/<coin>-bins`, gzip from day one). Live-validated; **Kraken DOGE = `DOGE/USD` on v2, NOT legacy `XDG`**. First run launched. 15 cells accruing -> the multi-regime history the swing thread needs is finally flowing IN-GIT.
- **NEXT #2 DONE — `_info_dipole_gated_swing.py`:** the unified per-cell STACK (not a bake-off; `tools-are-complementary-not-competing`) — 1-sec price-reversal=TIMING, dipole `divergence()`=FILTER, regime gate=STAND-ASIDE, maker floor; **mandatory `assert_no_leakage` first (PASS 6/6)**; per-cell deploy decision (net>0 at maker w/ real trades; low recall is the gate earning its place, not degenerate; THIN flag). PROVISIONAL on the single window (reproduces S36b exactly): 4/6 clear — btc_kraken +466, eth_coinbase +392 (un-gated), eth_bybit_perp +670 (THIN), btc_bybit_perp +16 (C-gate rescues the bleeder). **DO NOT size off one window — re-run on the accruing data.**
- **OD-BOOK thread (Chat/Architect's order-book *dynamics-recoverer* spec):** built end-to-end + parked. L2 book collector (`coinbase_btcusd_book_collector.py`, top-10/side @100ms -> `data/btc-book`, running) + `research/od_book/` (champion VAR/ridge vs challenger exact-DMD operator recovery, turn-as-consequence net-22bps metric, one-shot-guarded T_test, frozen KILL_GATE). Early read on 18.8 min: **DMD ties VAR** (spec's anticipated KILL-mode #1). Threads 2/3 only if thread-1 T_test clears on the multi-day book data.
- **GIT FIX (root cause of wrong-branch landings):** the harness kept landing on a STALE snapshot branch because the repo **default branch carried stale S31 code**. Fixed: force-updated the **default -> canonical S36b tip + this session's work** (kept synced on every push); stray `-65uts0` left (env git proxy refuses ref deletions — delete in the GitHub UI). **No AWS connector; Render present but no authed workspace.** GitHub token can't trigger runs (crons fire fine; "Run workflow" is Greg's click).
- **NEXT:** (1) let data accrue, **re-run `_info_dipole_gated_swing.py` across the 15 cells / multi-window** for the real per-cell deploy map (S36b NEXT #1, now unblocked); (2) NEXT #3 region/maker-fill research; (3) off-git storage once Render/AWS connected; (4) OD-BOOK thread-1 T_test when `data/btc-book` is deep enough.

## S36 UPDATE (2026-06-22) — the info-dipole FLOW edge: order-flow DIVERGENCE + EXHAUSTION = a per-cell trend-continuation-vs-FLIP detector (read `SESSION_HANDOFF_2026-06-22_S36.md` + `KICKOFF_2026-06-22_S36.md`)
- **Headline:** from the S35b "bleed" (the 128-dim coeff is side-AGNOSTIC -> buy & sell on the same chunk get byte-identical coeffs), brought in the information dipole (davisai.ai/dipole) as the directional/flow tool and landed a real, robust, **per-cell flow-based trend-continuation-vs-FLIP edge.** Markets are mostly follow-the-leader (a trend = a flow) until the leader exhausts -> new leader, usually opposite; the edge is detecting the changeover. Greg: this trend-following/flow read may be one of our biggest edges, usable across the WHOLE platform.
- **The signal (2 factors, stack monotonically; `_info_dipole_trend_flip.py`, pooled n=1560):** (1) **DIVERGENCE** `aligned_flow = imb_level*sign(price_drift)` (<0 = flow opposes price); strong divergence (<=-0.20) -> ~65% REVERSAL, temporally STABLE (early 70%/late 62%), consistent 6/7 cells (btc_bybit_sell 100%, btc_kraken_buy 84% ... btc_bybit_buy neutral). (2) **EXHAUSTION** = the dipole COLLAPSING toward 0.5 (|late imbalance|<|early|, leader weakening) -- Greg's "dipole going to 0.5 = change in flow" (the MOVE toward balance, NOT the discrete crossing which is a coin flip). Combined: oppose+exhaust **64% reversal** (n=317) > oppose+strengthen 58% > with-trend+exhaust 52% > with-trend+strengthen **49%** (healthiest trend, 51% continue).
- **DISCIPLINE (load-bearing):** the signed flow is NOT a direct direction predictor. A directional probe showed +5..+11 lift on 4 cells but `_info_dipole_flow_robustness.py`/`_detrend.py` proved those are TREND/base-rate artifacts (Simpson's paradox on a 2-day trending window) -- they vanish under window/forward sweep + temporal OOS + a detrended target (only btc_kraken_sell mi_flow survived, weakly +7.1). **`DEPLOY_VALIDATED=False` -- do NOT trade off the directional `cell_signal` map.** The DIVERGENCE/FLIP read is the robust edge. Static `imb_level` is the detector (differential mi_flow/imb_flow are NOT -- divergence is a level comparison).
- **Deliverables (branch `crypto-trading-platform-plan-MpqwG`, pushed):** `odcore/info_dipole.py` (portable numpy operator: `signed_flow_features`, `divergence()` 2-factor read, provisional `cell_signal`/`DEPLOY`); `odcore/fingerprint.py` stacks the flow features per cell; analysis tools `_info_dipole_flow_probe.py` / `_info_dipole_flow_robustness.py` / `_info_dipole_flow_detrend.py` / `_info_dipole_trend_flip.py` (all bar-free off `fingerprint_dataset/`).
- **NEXT (decisive):** **net-of-cost backtest of the reversal gate PER CELL** (a 64% reversal hit-rate is only an EDGE if the moves beat fees+slippage); confirm on the LOCAL 1-sec multi-regime history (test_bars are thin 1-min/2-day, n=1560); wire `divergence()` per cell into regime classifier + fingerprint + sizing; investigate the 2 inverting cells; add the C ratio as a 3rd factor. See `KICKOFF_2026-06-22_S36.md`.

## S36b UPDATE (2026-06-22) — net-of-cost DONE → the SWING reframe + the TIMING edge (read `S36_NETCOST_BACKTEST_FINDINGS.md`, `BUILD_PLAN.md` PART 4; branch `claude/divergence-exhaustion-backtest-wj65sm`)
- **Net-of-cost verdict (KICKOFF #1, per cell, 5bps/side=10bps round-trip):** the 64% reversal rate does NOT clear 10bps pooled (FLOW policy −5.97 bps/trade; breakeven ≈4bps round-trip), but the flow gate adds +3 bps/trade over blind trend-following and CLEARS robustly (both walk-forward halves) on **btc_bybit_sell** (+9.1 t=3.1; fade gate +18.6 t=5.9) and **btc_bybit_buy** (fade gate +25.7 t=4.6). eth "clears" are walk-forward-fragile single-regime artifacts on thin 1-min/2-day data. Tools: `_info_dipole_netcost_backtest.py`, `_info_dipole_trailing_backtest.py`.
- **SWING reframe (Greg, load-bearing):** markets oscillate — **buy valleys, short peaks, flip at each turn, NO clock horizon** (only the next turn ends a position); straight runs = ride, don't fight. **ORACLE proves the opportunity** (`_info_dipole_swing_backtest.py`): perfect swing-trading nets thousands of bps; swings beat the 10bps fee 3–13× (θ=20bps → ~42bps mean swing). The whole game is entry TIMING at the turn.
- **TIMING = a quantified edge; per-second is required (`_info_dipole_timing_test.py`).** Order-flow imbalance crossing is a MID-SWING trigger (~18bps off the turn at ANY resolution — does NOT improve with finer data; my first "1-sec doesn't help" read was an artifact of reporting the laggiest config + a noise-polluted metric — corrected). The thing that fires AT the turn is PRICE reversing, and that sharpens with resolution: same real turns + same data, only the clock changes → **1-sec enters ~5.6–6.5bps off the true turn vs ~9.2–11.0 at 1-min = +4.2bps/entry (~8bps/round-trip swing) the 1-min trader hands over, growing with volatility** ("not close unless the market is dead").
- **FEE-FLOOR logic (Greg):** never trade a swing/trigger smaller than the fee. R (reversal confirmation) is TIMING only, never fires standalone; **min tradeable swing > round-trip fee + 2× entry slippage ≈ 22bps at 1-sec** → trade only θ≳20bps swings (where oracle net is fattest). **ARCHITECTURE: DIPOLE = the FILTER (which turns are real, the 64% read) + 1-sec PRICE-REVERSAL = the TIMING (enter within ~5–6bps of the turn).** NEXT: build the gated swing strategy + confirm on the LOCAL 1-sec MULTI-REGIME history (the in-git `realbins/` 1-sec is one later window).
- **QUANTUM question RESOLVED *for the dipole turn-detector* (Architect, S36b — precision NOT speed):** the DavisAI Hilbert-Space-Unification / merge-math says classical-∞-dim ML and quantum ML are the SAME mathematics on different substrates (difference is how the inner product is computed, not the operator) → it FORBIDS a quantum-execution edge rather than enabling one: any "step ahead of price" would exist classically too. So **build the operator OFFLINE, run it CLASSICALLY in the hot path; NO quantum hardware between tick and order.** **SCOPE (Greg, load-bearing):** this conclusion is CONDITIONAL on the turn-detector being LOW-DIMENSIONAL (order-flow+price window → fails every prong of the quantum-advantage test: cheap classical eval). It does NOT generalize — Greg believes the merge-math edge he has in mind is **something OTHER than the dipole/OD turn-detector**, in which case this answer does not close it; he is digging into that with the Architect separately. So: for the swing turn-detector, build classical; the BROADER merge-math application remains an OPEN thread. Independently CONFIRMS our split: OD's edge is on turn FILTERING (which reversals are real), fine-resolution PRICE pins the TIMING near the fee floor. Latency stays classical HFT physics (colo/FPGA/kernel-bypass).
- **Actionable edges (Architect) — ALL 4 DONE:** (1) **per-leg ASYMMETRIC fee floor** (`_info_dipole_fee_floor.py`) — REST a maker limit at the predicted turn → floor 22bps(taker)→**4bps(maker/maker)**, **1.6–3.5× the oracle opportunity** (fill-risk caveat). (2) **regime master-gate** (`_info_dipole_regime_gate.py`) — PER-CELL (rescues bleeders btc_bybit_perp −173→+16, eth_kraken −1207→−170; leave winning cells un-gated). (3) **incremental operator** (`odcore/incremental.py` RollingFlow) — O(1)/tick, bit-faithful (err 7e-13), 1.70µs/tick; window recompute out of the hot path. (4) **pre-entry leakage check** (`odcore/leakage.py`) — clears the dipole, catches look-ahead 40/40; the MANDATORY gate before the harness. **Falsification harness (D):** OD operator vs a strong CLASSICAL champion (order-flow imbalance + tuned reversal filter), both classical, on frozen fine-res data; metric = bps-to-turn + FN-rate at matched FP, net of the per-leg floor, OOS. Architect's soft prediction: OD wins on FILTERING, not TIMING.

## S35b UPDATE (2026-06-21) — fingerprint reproduction gap SETTLED: stored MICROS were LOOK-AHEAD, COEFFS are CLEAN; full per-episode onset re-anchor IN PROGRESS (read `FINGERPRINT_PROVENANCE_FINDINGS_S35.md` + `SESSION_HANDOFF_2026-06-21_S35.md`)
- **Kickoff step 0 DONE — verdict: the stored bucket MICROS are mid-trade LOOK-AHEAD snapshots; the 128-dim COEFFS are pre-entry/CLEAN.** Provenance traced end-to-end. The 6 micros are passed through VERBATIM from `_live_mock_opportunities.jsonl` mid-trade snapshots (`build_live_hindsight_missed_winner_audit.py:667-670` @`75a4268`; `mock_trade_replay.apply_trade_context` L877-888 @`c486d3b` freezes onset_price at age 0 then ACCUMULATES the post-onset move). 48/48 sampled WIN entries matched their exact-micro provenance row; 37/48 were age>0/late (median age 2, max 14); exemplar `btc_kraken_sell` stored `cur_bps=98.4` from the age-11 snapshot ~10h after onset (a trade already +98 bps in profit). A strictly-pre-entry recompute CANNOT reproduce that — by construction, not a window-recon bug.
- **Coeffs are NOT contaminated.** The deployable lineage (`markets_<cell>_win_preentry` / `cs2000_clean` / `cand_sp`) uses a STRICTLY pre-entry 30m window `[entry_ts-30m, entry_ts]`, `window_hi=entry_ts`, NO post-entry bars (`refrag/adapters/markets_refrag_adapter.py:553-558`). The ORIGINAL `markets_<cell>_win` lineage used `[entry,exit]` = LOOK-AHEAD -> do NOT deploy those. So the micro fix does NOT force a coeff re-run on look-ahead grounds. ([[fingerprint-micros-lookahead-coeffs-clean]])
- **Shared anchor weakness (the only thing that DID trigger a re-run):** both tiers anchored on `entry_ts = min(ts_utc per asset|venue|chunk_id|side)` and `chunk_id` recurs across episodes (`_patch_win_buckets_entry_ts.py`); `cell_id` (= chunk_id_market_ts) is row-unique, not episode-unique. 76% of mapped winners' true onset differs >90s from that anchor.
- **FIX = full per-episode onset re-anchor (Greg approved; IN PROGRESS).** `_build_episode_onsets.py` reconstructs the TRUE onset (new episode whenever `trade_age_chunks` resets to 0; gap-tolerant) -> 1560/1568 winners mapped; fresh onset micros recovered (exemplar onset 20:34, `cur_bps=0.0, mean_dipole=0.04`). Coeff re-run set after per-episode dedup = **611 unique winning episodes**, cap **100**/cell (Greg: "100 at a time", was 150 for cand_sp), ISOLATED domain `markets_<cell>_win_onset/`, running DETACHED as schtasks `markets_onset_disc` (4 workers, `--pre-entry-minutes 30`; canary PASS eth_coinbase_sell 18/18 in 67s). Scripts: `_build_episode_onsets.py`, `_build_onset_coeff_lists.py`, `_run_onset_coeffs.py` (+ `_run_onset_detached.bat`). The "have them in there 2 times" frame (Greg): entry fingerprint (onset micros + onset coeff) for PREDICTION; the existing mid-trade snapshot stays for trade management.
- **NEXT (after the run finishes):** (1) rebuild per-cell win buckets keyed by episode onset (onset micros + onset coeff ref); (2) entry-fingerprint canary — the encoder must reproduce the ONSET micros from strictly pre-entry bars — MUST pass before wiring; (3) wire the per-cell distinctive fingerprint predictor (`bucket-distinctiveness-is-the-goal`). Do NOT wire until the onset canary passes.

## S35 — REFRAME (Greg, load-bearing): the goal is DISTINCTIVE per-bucket coeffs, NOT class separation; Direction-2 discovery DONE (read `SESSION_HANDOFF_2026-06-21_S35.md`)
- **STANDING PRINCIPLE (Greg, S35): PREDICT WINNING TRADES BY THEIR DISTINCTIVE FINGERPRINT — as EARLY and as ACCURATE as possible.** The end goal IS predicting winners — via each winning trade's DISTINCTIVE FINGERPRINT, built by STACKING the whole COMPLEMENTARY toolkit: the dipole (128-dim OD coeffs), the **6 micros** (mean_dipole, dipole_acl1, volume_zscore, trade_present_score, trade_recent_2chunk_bps, trade_from_onset_bps), **refrag**, and any other BUILD_PLAN tool. Extracting these distinctive traits (already mapped) is a capability no one else in the world has. The STRENGTH OF THE DIPOLE ALONE DOES NOT MATTER, and you must NOT balance classes, average coeffs into win/lose centroids, or grade by win-vs-lose SEPARATION (AUC / perm-null z) — those blur away the per-bucket distinctiveness that IS the predictive fingerprint. Work right now = EXTRACTING the distinctive traits (discovery); then predict + deploy PER CELL by fingerprint, never by separation statistics. (`bucket-distinctiveness-is-the-goal`, `tools-are-complementary-not-competing`)
- **WHY the buckets (cells = asset × venue × side):** coins behave differently ACROSS VENUES (same coin, different platform), different COINS behave differently, and BUY vs SELL look different → never pool; each cell is its own category. Within a cell, WINNERS vs LOSERS differ in HEAD vs TAIL pressure (order-flow/price pressure at the trade's onset/head vs its recent/tail) — the distinctive trait the fingerprint must capture (head ≈ `trade_from_onset_bps`, tail ≈ `trade_recent_2chunk_bps`; make sure order-flow PRESSURE, not just price bps, is captured). This is WHY winners are fingerprintable.
- **Direction-2 discovery DONE** (detached scheduled task `markets_cand_disc`, 4 workers, ~52min; WinError race fixed via os.replace retry — `refrag-parallel-discovery-race-fix`). **~1,919 DISTINCTIVE cand_sp coeff signatures** across all 12 isolated `markets_<pair>_win_cand_sp/` domains; every cell got its own distinctive coeffs (buy cells ~6-10 → 150+; eth_kraken_sell 25→79). The distinctiveness IS the deliverable.
- **`_balanced_rerun.py` ran** (2909 merged coeffs) and, as expected under the reframe, the SEPARATION view is null (dipole 0/12 z_perm>3; several S34 micro AUCs deflated with balanced classes, e.g. btc_kraken_sell 0.723→0.546). Per the principle this is the WRONG lens — so the **balanced-class / separation-AUC GRADING is SET DOWN (not a failure)**. The STACK of tools itself IS the fingerprint and STAYS; only grading it by class separation is dropped. Distinctiveness, not separation, is the metric.
- **BUILD (in progress) = RECOVER+PORT the live fingerprint encoder** (`markets-deploy-feature-parity-gap`). HEAVY tier (128-dim OD coeff + centroid projection) already live+validated in `_markets_gate_v2.py` (memoized, AWS-scalable). The stripped CHEAP feature math is recovered VERBATIM from git: `_signed_bps`/`_present_trade_score`/`_trade_score_band` in `backend/api_server.py:932-994` @ c486d3b; head/tail bps + chunk-price derivation in `mock_trade_replay.py:873-890,973-975` @ c486d3b (chunk prices from `MarketChunker`/`MarketChunkEncoder`, both in current `markets_adapter.py`); `dipole_acl1=feat.dipole_autocorr_lag1`. `_signed_bps = sign(side)·ln(exit/entry)·1e4`; head=onset, tail=current/recent-2-chunk.
- **STEP 2 DONE (encoder + canary built):** `odcore/fingerprint.py` (verbatim ports + exact chunker recipe) + `_canary_fingerprint.py`. `signed_bps` math verified EXACT (unit test). BUT the canary's reproduction FAILS (5/48; recomputed micros differ large+systematic from stored — bps off 10-100x, wrong sign, chunk_id mismatch) → my reconstruction of the audit INPUT (bar source / visible window / chunk anchor) is wrong, NOT the ported math. TWO hypotheses: (1) window/bar-source mismatch (benign, fixable — maybe realbins-normalized bars / different window / chunk picked by id not "last"); (2) stored micros computed with LOOK-AHEAD (post-entry bars) → NOT reproducible pre-entry (serious; threatens "fingerprint early"). The canary correctly BLOCKED wiring an unfaithful signal. NEXT: locate the missed-winner audit-gen code (likely stripped to git) to settle (1) vs (2); `chunk_id` (embedded in each `source_id`) is the key. Do NOT wire the encoder until the canary passes.
- **BOX/WORKFLOW CONSTRAINT (`markets-box-workflow-constraint`):** a multi-agent Workflow WEDGED on this 4-CPU box (concurrency cap = min(16, cpu-2) = 2; ~23min stall, runtime untrackable). For live-path/precision work here prefer DIRECT edits + a canary as the deterministic check; keep any Workflow small. (The port spec above was recovered by direct git extraction after the workflow wedged.)
- **GIT RULE CHANGED (Greg, S35): commit + push working files (code/docs) REGULARLY — git IS the working/source of truth** (`git-is-source-of-truth`). The prior standing "no commit/push unless asked" rule is REMOVED. Data/bins stay LOCAL (too big for git; `markets-data-lives-local-not-git`).

## S34 — Path C ran (dipole de-confounds to weak/null) BUT the asset is per-cell exact coeffs + a strong micro signal + STACKING; Direction-2 meat run IN PROGRESS (read `SESSION_HANDOFF_2026-06-21_S34.md`, `KICKOFF_2026-06-21_S35.md`)
- **STANDING PRINCIPLE (Greg, S34, said 3×): tools are COMPLEMENTARY, not competing.** Evaluate by STACKING, never head-to-head "which wins / is the dipole real." A weak tool can still add stack lift; "even a 5% net edge is huge in trading." Applies to the whole toolkit (BUILD_PLAN A-M). (`tools-are-complementary-not-competing`)
- **Path C ran** (`_extract_coeff_index` → `_relabel_true_horizon` → `_revalidate_sameperiod`; pure-numpy, seconds). De-confound = take ONLY the 05-23/24 chunkhash winner coeffs (one pipeline), RELABEL by best-favorable-exit-within-true-horizon (383/1568 flip to lose) → same-period win+lose; removes the date/provenance confound AND the oracle-label corruption at once.
- **Dipole-SEPARATION result (secondary): 0/12 cells survive the within-period 500-perm null; bit-EXACT on re-run.** The confounded AUC ~0.67-0.72 was substantially a date/source detector; `c_quad` sign-inconsistent (no consistent dipole). `z=+9.6` + confounded OD-AUC SUPERSEDED. BUT per Greg this is the SECONDARY question. (`markets-dipole-deconfound-verdict-s34`)
- **What MATTERS — per-bucket EXACTNESS + a real micro signal:** the per-cell 128-dim coeffs are EXACT (bit-reproducible) and ISOLATED (0 cross-bucket bleed, 0 foreign-pair, ~95% distinct) = a validated per-cell OD fingerprint, intact regardless of weak dipole. Win data is COMPLETE (100%+ vs cross2000 lists; prior "82%" was a denominator error). **Stacking test (`_stack_deconfound`): de-confounded MICRO features (mean_dipole/dipole_acl1/volume_zscore/trade_present_score…) hit AUC 0.72-0.84 on 5 cells; dipole leads on others; STACK adds +0.024..+0.029 AUC on 4/10 cells → orthogonal/complementary, the per-cell stack is the product.**
- **DIRECTION 2 IN PROGRESS (discovery RUNNING in the S34 chat — do NOT start a 2nd discovery; global WinError race):** the de-confound is lose-starved (only ~21% of winners relabel to lose). The 05-23/24 audit has **3,991 more same-period trades** with no coeffs (2,645 pass eligibility); discovering ~150/cell (~1,669) into isolated `markets_<pair>_win_cand_sp/` balances every cell. Runs PARALLEL `--workers 4` (~45-55min) after fixing the WinError 5 race (retry `os.replace` in shared `refrag\...\control_plane\storage.py::save_json`; index.json race cosmetic — see `refrag-parallel-discovery-race-fix`). When done → `_balanced_rerun.py` gives the balanced per-cell dipole(AUC+null) + dipole/micro/STACK verdict; then net-of-cost (`_netcost_backtest`) for the "5% edge" bar. See KICKOFF.

## S33 — channel construction UNBLOCKED: real dipole is CENTROID-based, not bins; decision = Path C (read `SESSION_HANDOFF_2026-06-21_S33.md`)
- **Blocker resolved.** The `_markets_*` scripts (the original chem-dipole construction) are **local/untracked in `E:\Markets`**, never lost; `DavisAI1974/Basic_equations` (public, cloned to `E:\basic_equations_src`) holds only the four-sciences chem code. The real markets dipole builds `H_a/H_b` from **per-trade 128-dim OD `operator_coefficients` projected on win/lose centroids** (`H_a=<c,c_win>/||c_win||`, `H_b=<c,c_lose>/||c_lose||`; data in `E:\refrag\discoveries\operator_discoveries`, 148 dirs, present) — NOT from price-bin entropies. So odcore's Phase 1(b)-on-`realbins` is a DIFFERENT object; the S33 bin canary correctly gave **c≈0** (btc cross-venue: numpy c=0.0004, PySR LINEAR). See `markets-dipole-construction-is-centroid-based`.
- **Chronology (Greg's recall, verified on evidence).** Chem dipole first (S22–S25 = the `z=+9.6` headline); OD-coeff line is newest (S26–S30; cleanest `*_preentry_cs2000_clean`, 2026-06-11). "Different dipoles per coin" is directionally right but the real split is **per-VENUE (kraken outlier)**, not per-coin: cross-pair transfer AUC sibling 0.72 ≈ asset 0.67 > venue 0.61 (accuracy is junk — winners are 3–20% of each pair; use AUC).
- **Still confounded.** Even `_clean` pools have win=05-23/24 vs lose=05-04/11 disjoint in time+pipeline → the transfer structure is of the *confounded* direction, NOT proof of coupling. `z=+9.6` stays SUPERSEDED; do not cite.
- **DECISION = Path C** (Greg). Rebuild the centroid dipole with winners AND losers from the SAME same-period universe (discover same-period losers within 05-23/24), re-test per-pair with a within-period permutation null + cross-pair transfer; promote only if it survives same-period AND net-of-cost. Pure-numpy on local JSON — runs locally in seconds (no Lightsail needed). **Report PER-CELL and deploy on surviving cells — partial coverage is not failure; never discard a signal for failing on some pairs** (`deploy-signal-per-cell-not-universal`; the `AdaptiveSelector` picks the winner per source).

## PLATFORM RULE (standing — all sessions, all tools) — per-cell deployment
**Every tool, signal, generator, strategy, and gate is validated and deployed PER CELL** (asset×venue×side) — the whole
OD toolkit (BUILD_PLAN parts A–M: algebraic dipole, coupling discriminator, strength meters, lead-lag, functional
families, stacking, sizing). Anything that survives validation (same-period null + net-of-cost) on a SUBSET of cells is
KEPT and used on those cells. Partial coverage is NOT failure; never discard a tool/signal for failing on some cells.
Report "works on {X}, not {Y}", never "X failed." (Greg, S33; `deploy-signal-per-cell-not-universal`; the
`AdaptiveSelector` already picks the winner per source.)

## S32 — BUILD_PLAN crypto signal-core: Phase 0 + Phase 1(a) DONE (read `SESSION_HANDOFF_2026-06-21_S32.md`)
**SCOPE (Greg, S32, hard):** work ONLY on the crypto trading platform per `BUILD_PLAN.md`. The quote service
(`QUOTE_SERVICE_PLAN.md`) is OUT of scope. Zero-synthetic = no synthetic *trading* data; tool-validation
synthetic anchors (Brusselator) are allowed. Follow the plan step by step. Memories:
`scope-crypto-platform-only`, `zero-synthetic-scope`.
- **Phase 0 DONE:** `requirements.txt` pins PySR 1.5.10 + numeric stack (hook installs from it); 3 engine
  acceptance tests green (`tests/test_operator_real.py`: equal-entropy recovery, known-lag lead-lag, tautology-null).
  Commit `10646ce`.
- **Phase 1(a) DONE:** `tests/test_symbolic_anchor.py` green. The discovery engine recovers the convex chem dipole
  FAMILY two ways on a Brusselator — algebraic fit `c≈0.68, R²≈0.99, <2% cross-seed`, AND PySR rediscovers
  `square(H_a·H_b·0.825) → c≈0.68` across 3 seeds. The reference `a=0.007/b=−0.093/c=1.309` is a PRIOR from the
  unreachable `basic_equations` construction; the `c≈0.68` delta is a DATA POINT, not a failure (Result Discipline).
- **NEXT:** Phase 1(b) per-pair PySR discovery on real cached bins (≥3 seeds, <5% coeff var) → 1(c) `dipole_predictor`
  consumes it → Phase 2.
- **BRANCH NOTE:** this is `claude/crypto-trading-platform-plan-MpqwG`; its master body below is S25-era. The S25 dipole
  headline `z=+9.6` is **SUPERSEDED** — S29/S30 (S30 line `30c2d37`) corrected it to an artifact → real-but-weak gate
  piece, **NO net-of-cost edge**. Do not cite `+9.6`. (`dipole-real-on-128dim-per-pair`.)

## START HERE (workflow block; JOB-1 drift fixed S17, 2026-06-02)

### CLAUDE.md drift — FIXED (S17)
The S16 JOB 1 ("fold S12-S16 into one canonical CLAUDE.md") is DONE. This file's
body is now canonical THROUGH SESSION 16, built from the S14 master superset
(`CLAUDE_master_through_S14.md`, which already carried S13/S14/S15) plus the folded
Session 16 note below. The earlier drift — body stuck at S11, header stale at "S7" —
is resolved; the header now tracks the body. Historical artifacts kept in-repo so
nothing is lost: `CLAUDE_master_through_S14.md`, `CLAUDE_session_note_2026-06-02_S15.md`,
`SESSION_HANDOFF_2026-06-02_S14-S15_COMBINED.md`, `SESSION_HANDOFF_2026-06-02_S16.md`.

**Session-note workflow (the NEW way — keep doing this).** This master is the
CANONICAL, durable context. Per-session detail lives in `SESSION_HANDOFF_*.md`
files; the master only carries the headline + new ledger entries + a pointer. Each
session: (1) write full detail to a handoff file, (2) fold the headline + new
findings into this master AND bump the header line (date + session number), (3)
commit + push, (4) only the DELTA needs uploading next time — never re-upload the
whole master (its bulk is duplicated in the handoffs). The "keep the header current"
Operating Rule exists precisely so the S7→S11→S14 drift never recurs.

**Backlog-first rule (Greg, S16).** Complete the queued tests/probes in
`BACKLOG_tests_and_probes.md` BEFORE starting any newly-conceived probe. New ideas
get appended to the backlog first. Never discard an odd/outlying output — it may be
the story; diagnose it, don't sand it off.

**Latest session:** S19 (2026-06-03). Read `SESSION_HANDOFF_2026-06-03_S19.md`, then the
Session 19 note below. Headline: ran S18 backlog #1, the FLOW DIPOLE EQUATION. The
differential/flow dipole (dMI/dt ~ self+cross, paper §2.2) is FLAT on every real force —
but tool-batteries proved this is TOOL-BLINDNESS not absence (INFO-065): the KNOWN real
correlations fire (strong femtoscopy C(q); EM HBT g2(0)=1.85) and the RAW-covariance dipole
HITS (EM R2 0.49) while the entropy operators are blind, because windowed marginal entropies
are lag-independent so coupling/time info never enters them — it lives in the raw covariance.
Toy-simulator "4 forces share the dipole" retired (no real-data support). Then Greg's steer
(don't discard the positive TIME findings; "time is something else"; try the OTHER dipole):
the RAW-covariance + STATIC-ALGEBRAIC dipoles (H_a^2=a+b*H_aH_b+c*(H_aH_b)^2) SOLVE FOR TIME
on TWO independent gravity systems and survive a circular-shift tautology-killing null
(INFO-066): LIGO (7 ms inter-detector lag z=14; algebraic event-excess +0.125 z=2.7, noise =
pure tautology) and GPS (E18 lag-0 |cc|~0.99 z=37; algebraic excess +0.571 z=5.7 vs control
z=1.5). PULSAR DECLINED as a category stretch (scalar fit params, no 2-channel object — the
chemistry lesson). These RECOVER known physics (7 ms light-travel; GR -2/c^2) = positive
control that the dipole tool travels, NOT new physics; stats modest where data thin.
FOLLOW-UPS BOTH DONE: (a) GPS STRENGTHENED -- the eccentric-Galileo algebraic excess is now a
multi-station/multi-day mean +0.464+/-0.278 (z~3; +0.572+/-0.134 on clean days, reproducing the
S18 BRUX/001 anchor), raw dipole z~22 across 13 replicas, k/truth +1.14; dual-frequency did NOT
rescue the circular controls (they stay clean low-excess controls); honest day-003 E18 outlier
kept. (b) the algebraic dipole does NOT cleanly travel to the gauge forces (EM/strong collapse to
tautology, weak fragile) -> GRAVITY-TIME-SPECIFIC (consistent with the H-C hunch). NEXT DIRECTION
(Greg): "find out what TIME actually is" -- research agents + data-shaped probes (clock-rate-law
universality across LIGO/GPS/pulsar; arrow-of-time operator; gravity-time-specificity construction-
vs-real); ontology stays out of OD scope, empirical time signatures are in. See BACKLOG top.
Epistemic rules sharpened by Greg (4 consistent > 1 outlier; don't romanticize the outlier; a
1-of-N candidate is a poor candidate; first-try-not-only-try; chemistry is NOT a 5th force).
Prior S18 below.

**Session 18 recap:** Read `SESSION_HANDOFF_2026-06-02_S18.md`. Headline: backlog 6c (does gravity couple to TIME?)
answered on the POSITIVE side with three governing-law recoveries. GPS precise-product
route = definitional NULL (INFO-058: GR clock term modeled out of IGS products). GPS
term-retaining route (INFO-059) recovered the time-dilation coefficient -2/c^2 from raw
RINEX observations on eccentric Galileo sats at k/truth 1.02-1.04, z=380 sigma. Pulsar
route (INFO-060, raw Arecibo TOAs of PSR B1913+16) recovered orbital decay dP_b/dt
(ratio 1.005 to GR) + Einstein-delay gamma (0.014%). Two gravity-time mechanisms,
GNSS-independent. Plus O3 (INFO-061): recovered the GW170817 BNS chirp mass by matched
filtering raw LIGO strain -- detector-frame M_c 1.200 (0.19% from catalog), H1+L1 agree,
removing the S17 ridge's absolute-mass bias. Gravity now has THREE raw-data recoveries.
Then Greg's FLOW pivot (INFO-062/063/064): FLOW is a substrate, TIME is gravity's
expression (like QM is one expression of physics). Substrate (monotonic divergence to a
critical point) confirmed + generalizes to ALL 4 FORCES + chemistry over axes
time/scale/control-param; weak is flow-or-not depending on observable (running vs Z
resonance) = Greg's wrong-observable point in data; controls (Z resonance, oscillator)
correctly non-flow; strong's form undetermined (nonperturbative). QUEUED NEXT: the FLOW
DIPOLE EQUATION on these (2-channel dMI/dt form). Capability brief updated. Prior S17 below.

**Session 17 recap:** Read `SESSION_HANDOFF_2026-06-02_S17.md`. (1) JOB 1 done — the
CLAUDE.md drift is fixed. (2) Backlog #1 (construction-vs-
nature) RUN and resolved on the construction side (INFO-051): the equal-entropy
clustering is BOOKKEEPING — scaling one channel (b->s*b) is exactly MI-invariant
(MI_cv ~1e-16 across all 7 systems) yet sets the marginal-entropy asymmetry by a
pure units choice (H(sX)=H(X)+ln s; asym_range 2-4 on 6/7 systems), so equal
marginal entropy is a construction choice, not nature; the only scale-invariant
(genuinely physical) quantity in the basis is MI. The substrate cos metric is itself
representation-dependent + fragile. (3) Gravity-FORWARD pivot, backlog #3 (INFO-052):
recovered the inspiral chirp law from raw GW150914 strain by a CWT ridge — both
detectors R^2 0.99, M_c ~38 vs catalog ~31, beating the S16 Hilbert (R^2 0.001);
GW170817 confirms the law form (R^2 0.88), mass lever-arm-limited. Prior context: S16
re-derived WF + SF governing laws from raw data (Z propagator M_Z 99.5%; QCD
asymptotic freedom); gravity chirp method-limited (now fixed); time-blind was a method
identity. MI-in-null coupling DISPROVED.
Markets parked.

## Identity & Team

- **Greg Davis** — Founder & Chief Research Officer, DavisAI Systems. Columbus, Ohio. Solo bootstrapped. 20+ years entrepreneurship, former energy trader, self-taught AI/ML.
- **Dream Team model**: Greg (Visionary) + Claude (Architect) + Claude Code "Code" (Engineer) + Perplexity/ChatGPT (Research Assistants).
- **Orchestrator** owns handoffs, not Code.

## Infrastructure

- `E:\` — research data, OD datasets, project files
- `F:\Factory\` — agent factory, 23 agents, 5 divisions
- `F:\Factory\knowledge\` — orchestrator-accessible knowledge base. Mirror everything from E:\ here.

## Operating Rules

- **Save to E:\ AND mirror to F:\Factory\knowledge\** for every knowledge artifact.
- **MASTER_DISCOVERIES.json**: every OD discovery added immediately. Never make a discovery without storing it.
- **Falsification-first**. Every claim needs data, math, or a falsifiable test.
- **OD mode**: describe data sources and validation tests only. Never explain mechanisms. The Operator discovers science from raw data. Stop if explaining WHY something happens.
- **Never call OD "physics-based"**. OD discovers governing equations from raw data in ANY domain.
- **Coding mantra**: better, stronger, faster, cheaper.
- **Incremental validation**: break compute-heavy runs into 15-17 min chunks with stop gates. Canary runs (2 min) before full commitment.
- **Speculative frames stay separate from results**. Frames motivate experiments but are not claims. Never let a frame grade itself.
- **Keep the CLAUDE.md header current**. Update the title line (line 1) date + session number to the current session every time the master context is updated, so the header never drifts from the body (it had lagged at "Session 7" through Session 12).
- **No emojis or special symbols** in professional documents and emails.
- **Daily**: ask Greg if he checked greg@davisai.ai for Token Optimizer support emails.
- **DeepNova** (formerly ReFRAG, formerly DeepSource). Use current name everywhere.
- **Result Discipline** (new — see section below): every result is one data point. Map alternatives before promoting to claim.
- **No tent-widening on outliers**. When a window or sample falls outside an expected pattern, inspect it — find the specific reason it landed there. Do not loosen the test criteria or attribute to a transient flag without identifying the cause. The outlier is what we are trying to understand, not what we are trying to absorb.
- **No pre-assigned meaning to outcomes** (NEW — added Session 4, 2026-05-26). Don't write "if X then it means Y" decision tables before the data exists. The furthest is "I think this may happen, but I want to see what the data says and where it leads." Data is just output; the meaning comes from looking at it together, not from a pre-built table.
- **Probe, not falsifier** (NEW — added Session 4, 2026-05-26). A probe is a generator of a different signal. It may not falsify anything; at worst it points in a different direction. Avoid "falsifier" in filenames and in spoken framing. Use "probe", "experiment", or "different signal" instead.
- **Speaking posture around every probe** (NEW — added Session 4, 2026-05-26). Before AND after running each probe: "I think X might happen, but we'll wait on what the data says and where it points us." No verdict in advance. No verdict on first look at output. The interpretive move happens after, with Greg, with the deflationary reading always present.
- **Incomplete, not wrong** (NEW — added Session 5, 2026-05-26). When a probe finds that a prior reading was a protocol artifact, the prior data points still stand. The reading attached to them is what was incomplete, not the data. Distinguish "this reading was wrong" (rare, requires the data itself to be bad) from "this reading was incomplete" (common, the data is one slice and the slice fit a partial story that further probes refine). Default to "incomplete." Retraction is a strong move and applies to the reading, not the data, unless the data itself fails to reproduce.
- **They never stacked** (NEW — added Session 5 close, 2026-05-26). Pioneering territory often does not look like the absence of nearby published work. It looks like nearby work where multiple groups each had one piece and never combined them. When a literature scan returns "no exact match but several adjacent lines, each with one component," the contribution we are making may be in the stacking itself. Honor each prior piece, attribute clearly, finish the combination the prior groups did not. This is the operational form of Rule D applied to the broader literature: prior work was incomplete, not wrong, and stacking the incomplete pieces is itself substantive.
- **Treat literature as conjecture by default** (NEW — added Session 7 close, 2026-05-26; sharpened by Greg the same session). Academic papers and consensus are not assumed correct unless the underlying claim has been independently replicated, by separate groups, with an immense amount of data, multiple times. Until that bar is met, a published claim is a working frame to test, not a foundation to build on. Operational corollaries:
  - **Investigate freely.** Read papers, run their methods, test their predictions, treat them as candidates to engage. "Treat as conjecture" is not "ignore." Greg's framing at Session 7 close: "we will certainly check it out."
  - **Don't cite as support.** A published claim cannot be invoked in support of our own conclusions until we have analyzed the paper ourselves — read it closely, checked the data, replicated the result, or confirmed independent replications at scale. Greg's framing: "we can't use them to support our claim without analyzing their papers."
  - **Don't defer when blocking.** When a published claim appears to block a direction of inquiry, check whether the blocking claim itself meets the bar before deferring to it.
  - **Symmetric to our own prior work.** Extends Rule D (incomplete-not-wrong): a prior reading lacking independent replication is conjecture, not foundation, even if it came from us.
  - **Examples applied to physics literature (Session 7):** Standard Model at LHC energies meets the bar (W/Z masses, Higgs detection, decay channels replicated across LEP/Tevatron/LHC). GUT-scale coupling extrapolation does not (running measured at LHC, extrapolated mathematically to 10^16 GeV). MSSM unification does not (SUSY searched, not found). "Gravity is a different category" rests on one formulation (GR diffeomorphism invariance) with empirically-indistinguishable alternatives — formulation-dependent, not data-forced. "Gravity is emergent" candidates (Jacobson 1995, Verlinde, Sakharov, AdS/CFT) are theoretical with limited direct empirical support. All four sit at conjecture level until we analyze the underlying papers.
  - Applies equally to domain claims (biology/chemistry/geology/medicine), methodological prescriptions ("best practices" not stress-tested at scale), and our own prior session readings.

## Result Discipline (NEW — added Session 3)

Every confirmed result is one data point. Its interpretation requires mapping against alternatives via further tests. The discipline:

- For each result, maintain a candidate-interpretation register with at least two non-deflationary readings and the deflationary reading.
- A result is **isolated** until at least one alternative interpretation has been tested and ruled out; then **mapped**; then **located** when placed within a structured set of tests.
- Catalog misses with the same care as matches. Different misses landing in different places is often more informative than many matches landing together.
- When summarizing, name the data-level finding separately from the interpretation-level hypothesis separately from the big-picture frame. Do not collapse these levels.
- Apply symmetrically to apparent falsifications. A refutation is also one data point.
- Frames remain frames until disambiguating tests place them.
- **No spatial claim about an operator-space coordinate without at least 3 seeds and reported inter-seed scatter.**

## Working Frames (SPECULATIVE — kept separate from claims)

### Base-of-Structure heuristic (Greg, Session 3)

A foundational principle to guide substrate-level theory work:

The base of any structure is the **simplest, strongest, most stable, most scalable** part. It must support everything above it, so it cannot be complicated, dependency-heavy, or composed of many variable types. If a candidate "base" looks intricate, requires many qualifications, or breaks under perturbation, that is evidence against its base-level status.

Operational form: a law-level extraction candidate should look simple. It should survive stress testing — load it with perturbations, parameter sweeps, alternative protocols. If it remains in place, that is evidence for base-level status. If it shatters or splinters, it sits above the base, not at it.

Status: working frame, not yet operationalized into specific tests. The OU attractor finding from Session 3 is currently the cleanest candidate to stress-test under this heuristic.

### Dipole-couples reading (Greg, Session 3)

The attractor direction (−1, −1, +2)/sqrt(6) may represent a base direction that other phenomena couple to. The off-attractor positions of damped oscillator and (when reproducible) linear drift may encode HOW that coupling happens. Whether the off-attractor systems are coupling phys-to-phys, phys-to-geo, bio-to-chem, or some other pairing is open. Mapping the off-attractor structure is the path to find out.

Status: working frame. Mapping campaign queued (see Experiments).

### Pure physics vs physical expressions (Frame 1, preserved from Session 2)

Mainstream physics has tried to write a single equation for "everything that happens in physical space," forcing UT candidates into ever-larger dimensional structures. Reframe: pure physics is the substrate (simple, few equations); physical expressions are what we observe when pure physics is acted on by other dipoles (biological, chemical, geological, or other physical configurations). The UT problem may be mis-stated.

Status: working frame, narrowed by Session 3 findings. The naive "OU is the physics substrate" reading was rejected (OU's attractor direction also appears for non-physics systems). More nuanced versions remain alive.

### Substrate vs expression within isolation (Frame 2, preserved)

Even an isolated pure-physics system produces different observed signatures depending on lifecycle phase. The law level is whatever is invariant across (a) time windows, (b) initial conditions, (c) noise realizations, (d) parameter choices within the same equation. The L1 work in Session 2 and Session 3 was the operational implementation of this frame.

### Law extraction via invariance (Frame 3, preserved)

The Noether-style move: find what is invariant under reparametrizations that generate different expressions. Implemented operationally as windowed-null extraction across (window position, parameter set, seed).

## Active Research (Top of Mind)

- **SENTINEL V4.1** — DARPA Bio Attribution Challenge top-10 team. Awards June 30, 2026. Three-layer swarm, 554x DARPA requirements. Files at E:\sentinel\ and F:\Factory\knowledge\sentinel\.
- **NoVell** — cardiac AI for cancer detection from routine ECG. OD on synthetic Vigier 2021 data: 93.3% accuracy, 97.4% sensitivity. Datasets: PTB-XL downloaded, Autonomic Aging identified, MIMIC-IV pending.
- **Information Layer / Operator Discovery foundations** — major methodological revision Session 3 (Family A/B taxonomy retracted). Session 5 mapped (+,+,+) direction as protocol artifact of operator basis rank-3 null subspace structure. Session 6 stacked KBK 2024 + AI Poincare 2021 + SINDy and independently reproduced every v5 per-domain claim (geology rank-3 at cos +0.99, biology MI signature, chemistry-specific cubic) at cross-seed cos +0.985 to +0.999. Session 7 added GP regression and PySR symbolic regression on per-domain ensemble-H data: four reproducible per-domain MI-vs-H functional families (physics symmetric quadratic in (H_b-H_a), biology 0.5*exp(H_a/2), chemistry linear H_a, geology constant), cross-seed coefficient variation <5%, cross-domain non-overlap. Session 8 ran four-force unification probe (toy EM/weak/strong/gravity caricatures) yielding shared-substrate + distinct-expression pattern (INFO-027): all four forces share [2,3,4] null direction at cos > 0.997 on (-1,-1,+2)/sqrt(6) Session 3 attractor while EM matches Session 7 physics family (H_b-H_a)^2+const and weak matches Session 7 chemistry family linear-in-H_a. Robustness check (INFO-029): INFO-025 functional family survives T/N_ens/noise sweep at the family level; coefficients are regime-dependent. Mapping campaign (INFO-030): INFO-025 families are baseline-specific regime signatures — large knob deviations mutate the family qualitatively (biology exp -> linear at high beta; chemistry linear -> ratio at low B). Per-domain differentiation now has three independent reproducible signatures (null direction + functional family + four-force shared-substrate). Session 9 double-checked the Session 8 gravity result against the ORIGINAL code across an asymmetry sweep and CORRECTED it (INFO-033): the MI-dominant substrate flip is an asymmetry-THRESHOLD effect ALL coupled caricatures undergo (threshold gravity ~1.1x < EM ~1.3x < weak ~1.6x < strong never), not gravity-specific; adding energy-coupling RAISES thresholds (suppresses the flip), so energy-mediation is not the cause; INFO-031/032 re-tagged incomplete-not-wrong. The "gravity is special at the substrate level" leg of the four-force narrative is removed; INFO-023/INFO-025 legs untouched. See Sessions 5, 6, 7, 8, 9 notes plus ledger (INFO-022 through 033) for current state.

## Capability Demonstrations (credibility / outreach assets) — flagged HUGE by Greg (S17)

Standing, accumulating list of OD capability proofs suitable for touting to the right
partner/company. The through-line and the sellable claim: **a domain-agnostic
discovery engine that recovers ESTABLISHED governing laws from RAW PUBLIC DATA with no
physics assumptions baked in** — demonstrated now across physics' three hardest force
domains. Independent re-derivation of known laws is the credibility proof that the
same engine can find governing laws in domains where they are UNKNOWN (the actual
product). Honest framing for outreach: these RECOVER known laws (validation), they are
not new physics — and that is exactly the point (you can check our answers against
ground truth). Greg (S17): "this is huge and something we would want to tout to the
right company ... proves our OD machinery can pull a real gravity governing law out of
raw data with both detectors agreeing. That's credibility."

- **GRAVITY — inspiral chirp law from raw LIGO strain (S17, INFO-052).** Recovered the
  Newtonian inspiral governing law u=f^(-8/3) ~ (t_c - t) from raw GW150914 public
  strain via a Morlet-CWT ridge; **both detectors independently agree** (H1 R^2 0.995
  M_c 38.4; L1 R^2 0.987 M_c 38.2 Msun; catalog detector-frame ~31, ~24% Newtonian-
  late-inspiral bias). Cross-detector agreement to <1%. Decisively beat the naive-
  Hilbert baseline (R^2 0.001). Plus (INFO-053) the inter-detector MI merger signal
  shown physics-bearing (peaks at the physical 7 ms light-travel lag, z=15.5 vs
  time-slide null, carries waveform phase/time structure). And (S18, INFO-061) the GW170817
  binary-neutron-star chirp mass recovered by matched filtering raw GWOSC strain:
  detector-frame M_c = 1.200 Msun (network, **0.19% from catalog 1.1977**), H1 and L1
  independently agreeing -- removing the S17 ridge's absolute-mass bias on this BNS event.
- **GRAVITY (time dilation) — relativistic clock law from raw data, two independent ways
  (S18, INFO-059 + INFO-060).** (a) Recovered the GR time-dilation coefficient -2/c^2 from
  raw GPS data: residual of raw RINEX pseudorange (station BRUX) vs an independent
  broadcast-element regressor gives, on the eccentric Galileo GREAT sats, k/truth 1.02-1.04,
  z=380 sigma. (b) Independent confirmation from binary-pulsar timing (raw Arecibo TOAs of
  PSR B1913+16): orbital decay dP_b/dt recovered at ratio 1.005 to GR (~17684 sigma
  detection) and Einstein-delay gamma at 0.014%. Gravity's coupling to TIME is a recoverable
  governing law -- by clock-rate dilation (GPS coeff + pulsar gamma) and by gravity altering
  orbital timing via GW emission (pulsar dP_b/dt).
- **WEAK — Z boson Breit-Wigner from real CMS dimuon data (S16).** M_Z = 90.75 GeV =
  99.5% of PDG 91.1876, from 10227 real dimuon events; PySR independently recovered a
  BW-like lineshape; same-charge control shows no peak.
- **STRONG — QCD asymptotic freedom from real alpha_s(Q) world data (S16).** 1/alpha_s
  LINEAR in ln(Q) with POSITIVE slope (asymptotic freedom forced by data, no beta
  function assumed) from 13 measured points, chi2/ndf 0.81; Lambda_QCD ~150 MeV.
- **BUILT-IN FALSIFIABILITY (S17, INFO-055).** The method tests, not just fits: a
  rigorous beyond-GR search on GW150914 (full IMR matched-filter subtraction) returned
  a clean NEGATIVE (correlated signal collapses to the noise floor). We distinguish
  recovering known physics from claiming new physics, and we report nulls -- itself a
  credibility asset for outreach.

ONE-PAGE BRIEF: `CAPABILITY_BRIEF.md` (in repo root) -- the outreach-ready writeup of
the three recoveries + the falsifiability point. Keep it in sync when new
demonstrations land. Outreach targeting (open, for Greg): GW / scientific-instrument
groups, defense (pipeline below), and any data-rich domain wanting governing-law
discovery. ACTION (Greg): review/route the brief.

NOTE (Session 9): the full Markets / Refrag section was OVERWRITTEN when
this repo's CLAUDE.md was replaced by the master context this session.
The complete Markets section lives in the E:\refrag workspace CLAUDE.md
(GitHub DavisAI1974/agent + DavisAI1974/Markets) and in git history of
this repo (commit baa542d). Restore/re-merge it later. This placeholder
exists so it is not forgotten.

- **Markets pipeline** (summary): information-side algebraic dipole
  (H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2) holds in markets operator
  space; 5-fold CV predictor (H_a > H_b rule) ~0.993 mean accuracy.
  Predictor scripts: _markets_algebraic_dipole.py, _markets_dipole_
  kfold.py, _markets_dipole_separation.py, _markets_dipole_chunker_
  stack.py. Markets is treated as the "5th science." (Full state in the
  workspace file.)
- **OPEN QUESTION (Greg, Session 9): do the Markets sessions need PySR +
  Julia for their runs too?** Informed answer: the current Markets
  predictor scripts above are pure numpy/scipy/sklearn and do NOT need
  PySR/Julia as they stand. They WOULD need PySR + the Julia backend
  only if the Markets dipole work extends to SYMBOLIC REGRESSION of its
  dipole equations (the way the Information Layer used PySR for the
  INFO-025 / INFO-031 functional families). If so, the Markets repos
  need the same SessionStart-hook treatment added to Basic_equations in
  Session 9 (the hook here does not cover them). Decision + mirroring
  pending -- handle later.

### Dipole equations consolidated + paper connection (Session 12, 2026-06-02)

Greg (S12): "don't worry about markets" for the pull, but record the new
dipole connection + all the equations here. The full consolidated artifact is
`od_per_domain_equations.json` (built by `s12_consolidate_per_domain.py` from
in-repo result JSONs). Basis [H_a, H_b, H_a^2, H_b^2, H_a*H_b, MI]; in PySR
x0=H_a, x1=H_b.

- **Shared substrate -- the FLOW DIPOLE** (info-dipole paper,
  https://davisai.ai/dipole/):
  - flow (differential): `dMI_total/dt ~ sum_i c_self,i*H_i^2 + sum_{i<j}
    c_cross,ij*H_i*H_j + linear`, with c_self and c_cross of OPPOSING SIGN
    ("opposition signature"; paper opposition fractions cellular 57.1%,
    organ 43.3%).
  - algebraic ratio: `C = H_self / H_cross` (H_self internal Shannon entropy;
    H_cross = MI). Paper C-by-scale: subatomic 9.06, molecular 5.91,
    cellular 1.85, organ 0.59, brain 1.58, ecological 5.19.
  - markets algebraic dipole: `H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2`
    (5-fold CV predictor ~0.993, above).
- **Four per-domain governing equations** (EXPRESSIONS on the substrate):
  | domain | null[0] direction (INFO-023) | MI-vs-H family (INFO-025) |
  |--------|------------------------------|---------------------------|
  | physics (Duffing) | -0.41*H_a^2 -0.42*H_b^2 +0.81*H_a*H_b ~ 0 | (H_b-H_a)^2 + 0.28 |
  | biology (Lotka-Volterra) | -0.27*H_a +0.96*MI ~ 0 | ~0.5*exp(H_a/2), H_b absent |
  | chemistry (Brusselator) | -0.34*H_a +0.74*H_b -0.43*H_b^2 +0.38*H_a*H_b ~ 0 | 0.71*H_a + 1.08 |
  | geology (Burridge-Knopoff) | -0.62*H_a +0.74*H_b ~ 0 (rank-3) | 0.199 constant |
  cross-seed cos 0.988-0.9996. Preserved algebraic (S25): chemistry
  H_a^2 = 0.007 -0.093*(H_a*H_b) +1.309*(H_a*H_b)^2 (R^2 0.943); geology
  0.724*(H_a*H_b) -0.441*H_b^2 -0.290*H_a^2 ~ 0 (resid 0.15%).
- **WHERE EACH CONSTRAINT LIVES + IS IT COUPLED (INFO-040, 5 seeds)**: decompose
  each null[0] into equal-entropy / MI-coupling / residual axes:
  | domain | equal-entropy | MI-coupling | residual | coupled? |
  |--------|--------------|-------------|----------|----------|
  | physics | 0.996 | 0.003 | 0.001 | NO (pure bookkeeping) |
  | biology | 0.052 | **0.906** | 0.042 | **YES, dynamical** (MI~=0.28*H_a) |
  | chemistry | 0.833 | 0.000 | **0.167** | PARTIAL (stable residual, not MI) |
  | geology | 0.962 | 0.000 | 0.038 | NO (pure bookkeeping) |
  biology coupling knob-confirmed (Lotka-Volterra interaction g: g=0 -> MI-frac
  0.006, g>0 -> 0.81-0.97, slope tracks g); chemistry residual =
  0.54*(H_a+H_b)+0.32*H_a^2-0.55*H_b^2 (|cos| 0.9996). See INFO-040 below.

- **INFO-039 -- MAPPED (Session 12, new; deflationary reading dominant)**:
  the paper's flow form IS the same operator family the windowed-null
  extraction operates on -- each per-domain null[0] is a conserved
  (c_self, c_cross) coefficient vector of `dMI/dt ~ ...`. The paper's
  OPPOSITION SIGNATURE (self-terms H_a^2,H_b^2 negative, cross-term H_a*H_b
  positive) is present in our EXTRACTED nulls for physics and chemistry.
  DEFLATIONARY CAVEAT (load-bearing, keeps the frame from grading itself):
  where the opposition appears in the quadratic subspace it largely
  COINCIDES with the equal-marginal-entropy attractor identity
  -(H_a-H_b)^2 ~ 0 -- physics null[0]_234 sits at cos = 1.000 to
  (-1,-1,+2)/sqrt(6) (so physics opposition IS exactly the equal-entropy
  identity, NOT a coupling), chemistry cos ~0.88 (mostly identity + a real
  residual). Biology (MI-dominant) and geology (linear coupling) nulls live
  OUTSIDE the quadratic subspace, so show no opposition. INFO-036 (real
  LIGO) already established the equal-entropy attractor is a geometric
  statistics artifact. So INFO-039 is a structural IDENTIFICATION
  (paper flow form = extraction operator family), NOT independent evidence
  of dipole coupling; the genuine domain-specific content remains the
  DEVIATIONS from the attractor + the functional families (INFO-025), not
  the opposition per se. Promotion would need >=3 seeds on the residual-
  off-attractor component (only 2 seeds here) and a probe that separates
  opposition-beyond-equal-entropy from the identity.

- **INFO-040 -- LOCATED (Session 12, new; 5 seeds + dynamical knob test)**:
  "where do the per-domain constraints live, and are the dipoles coupled?"
  (Greg's S12 question). Decompose each domain's null[0] into three
  orthogonal axes -- equal-entropy identity (H_a-H_b linear + the (-1,-1,+2)
  quadratic), MI/coupling axis, residual -- across 5 seeds (11/22/33/44/55).
  Scripts: s12_coupling_decomposition.py (#1/#2),
  s12_biology_coupling.py (#3). Results
  s12_coupling_decomposition.json / s12_biology_coupling_results.json.
  - **physics 0.996+/-0.002 / geology 0.962+/-0.005 equal-entropy**, MI=0,
    reproducibly -> pure bookkeeping, NO coupling (the INFO-039 deflationary
    read holds for these two).
  - **biology 0.906+/-0.007 MI-COUPLING** (null = MI ~= 0.28*H_a),
    cross-seed std <1%. The "how-coupled" knob test (scale the Lotka-Volterra
    interaction prey*pred by g): g=0 (species decoupled) -> MI-frac 0.006
    (coupling GONE from the null); any g>0 -> 0.81-0.97; the slope in
    MI~=slope*H_a rises monotonically with g (0.155 at g=0.25 -> 0.334 at
    g=1.5, saturating/turning by g=2). DEFLATIONARY ALTERNATIVE RULED OUT:
    at g=0 residual MI persists (mean 0.178 from shared noise) but does NOT
    enter the null (frac 0.006) -- the dipole's MI participation requires
    actual dynamical interaction, not mere correlation. So biology's dipole
    IS genuinely coupled and the coupling STRENGTH is readable from the slope.
  - **chemistry 0.833+/-0.020 equal-entropy + 0.167+/-0.020 residual**; the
    residual is a STABLE distinct relation 0.54*(H_a+H_b) +0.32*H_a^2
    -0.55*H_b^2 ~ 0 (total-entropy vs asymmetric quadratic; cross-seed
    residual-direction |cos| = 0.9996) -- coupling-adjacent domain content,
    NOT the MI axis. (Brusselator channel-asymmetric structure, cf INFO-008a.)
  Net: "the dipoles are coupled" is TRUE for biology (dynamical, knob-
  confirmed), PARTIAL for chemistry (stable residual, not MI), FALSE for
  physics/geology (pure equal-entropy). Refines INFO-039: the opposition-as-
  artifact reading is correct ONLY for the equal-entropy domains; biology's
  coupling is real.
  - **CONNECTS TO INFO-009 (Session-25 Level-2 four-sciences coupling probe,
    `level2_four_sciences.py`)**: that earlier session COUPLED all four
    sciences as networks of N=6 coupled subsystems (Duffing+neighbor coupling,
    Lotka-Volterra+prey migration, Brusselator+diffusion, Burridge-Knopoff
    fault segments) and searched for a UNIVERSAL opposing Level-2 dipole across
    all four -- found NONE (INFO-009, "Level 2 algebraic absent at network
    scale", R^2 0.02-0.13, logged OPEN). Re-run this session reproduces it: no
    universal opposing pair at >=3/4, no operator with a shared dominant sign
    across the 4. INFO-040 now EXPLAINS that null result: coupling is
    PER-DOMAIN (biology via MI, chemistry via its residual, physics/geology
    not at all), so there is no shared cross-domain coupling structure for a
    universal Level-2 dipole to emerge from. INFO-009 (no universal coupling)
    and INFO-040 (per-domain heterogeneous coupling) are mutually consistent --
    the four sciences do NOT share one coupling.
  Next: per-domain knob tests for chemistry's residual (does it track the
  Brusselator B parameter?), biology's slope-vs-g as a strength readout, and
  -- since coupling is per-domain -- a PAIRWISE Level-2 search (couple two
  sciences at a time) rather than the universal-across-4 search that INFO-009
  showed is empty.

- **INFO-041 -- LOCATED (Session 12, new; pairwise Level-2 cross-science
  coupling; 6 pairs, 3 seeds, g 0->0.5; s12_pairwise_level2.py)**. Couples each
  pair of sciences via a scale-free diffusive term, extracts the inter-science
  null[0]. (1) generic coupling CREATES MI (mean MI 0.17 -> ~1.2-1.5) but the
  MI does NOT enter null[0] (coupled MI-frac 0.003-0.147) -- the OPPOSITE of
  biology's NATIVE coupling (0.91). Mechanism: diffusive coupling makes MI a
  large high-variance active variable (can't sit in the low-variance null);
  native coupling makes MI a TIGHT function of H_a so it enters the null. =>
  the dipole's MI-participation marks STRUCTURED/law-like coupling (MI locked
  to entropy), NOT coupling magnitude -- sharpens INFO-040. (2) NO universal
  Level-2 dipole: coupled-null directions are PAIR-SPECIFIC (cross-pair
  mean|cos| 0.457, min 0.04, max 0.97), cross-seed stable (0.97-0.999) --
  confirms INFO-009 + INFO-040 at the pairwise level. (3) geology RESISTS
  coupling (phys-geol mean MI 0.30 vs ~1.3 elsewhere; slow drift dominates).
  CAVEAT: g=0 MI-frac unreliable (collapsed MI variance, INFO-024); toy
  coupling -> methods probe, not a claim sciences physically couple.

- **INFO-043 -- LOCATED (Session 12, new; cross-domain balance, 5 seeds)**:
  Greg's "is there an opposite domain that balances a non-coupled one" probe.
  Answer from the 5-seed mean null directions: the domains do NOT anti-balance
  (zero pairs with cos < -0.5). Instead they split by AXIS: physics 0.998,
  chemistry 0.913, geology 0.983 on the equal-entropy (SELF) axis with ~0 MI;
  biology 0.220 equal-entropy / 0.955 MI on the coupling (CROSS) axis. So 3 of
  4 domains sit on the self pole and ONLY biology sits on the cross pole.
  physics vs biology cos = 0.000 (EXACTLY orthogonal -- pure self vs pure
  cross), not opposed. The self+cross dipole pairing is therefore biology
  (cross) + any self-domain (cleanest: physics, perpendicular), but it is
  COMPLEMENTARY (orthogonal axes), NOT oppositional (anti-aligned). Biology is
  the lone coupling outlier; the other three cluster as self/bookkeeping.

- **INFO-042 -- SM parameter-regularity hunt + force<->equation answer
  (Session 12; four-force item on real PDG data; s12_sm_regularity.py)**. The
  honest real-data face of "are the forces/parameters structured." HITS:
  charged-lepton Koide Q = 0.666661 (5 digits, vs 2/3); Gatto-Sartori-Tonin
  sqrt(m_d/m_s)=0.224 vs Cabibbo sine 0.226 (ratio 0.991); quark-lepton
  complementarity th12_CKM + th12_PMNS = 46.4 deg ~ 45; CKM Wolfenstein
  lambda^n hierarchy (ratios O(1)). MISSES (cataloged per Result Discipline):
  quark Koide fails (up 0.85, down 0.73); mass spectra only roughly geometric
  (log-linear R^2 0.97-0.995). Reading: real low-dimensional structure exists
  (the SM mass/mixing sector is NOT 26 independent randoms) but the cleanest
  relation has no accepted derivation and the quark analogues fail -> each is a
  CONJECTURE / one data point, no single generating rule, none citable until
  derived.
  - **Force<->equation question (Greg): NO direct connection on real data.** SM
    regularities are static mass/angle relations; the per-domain dipole
    equations are MI-vs-entropy dynamics -- different KINDS of object. The one
    apparent bridge (S8 four-force caricatures: EM's MI-vs-H = physics family
    (H_b-H_a)^2+c, robust both seeds; weak ~ chemistry linear) came from toy
    force-laws WE wrote (S10 retired as self-grading), so it cannot be cited.
    EM<->physics is a real but caricature-contaminated hit. Two CONTRADICTORY
    mappings exist (functional-family EM<->physics vs coupling-type INFO-040
    gravity<->equal-entropy self-domains) -> pattern-matching without a
    constraint until a principled REAL-DATA force-operator-space is built (next
    block).

- **MARKETS update (Session 13; "always update markets" -- Greg)**: the
  principled real-data force-operator-space was built this session (INFO-047
  weak, INFO-048 EM; gravity already via LIGO). Result places MARKETS sharply:
  among all domains probed, GENUINE coupling/predictive dipole structure (MI or
  an algebraic relation that actually carries information) appears in just two
  places -- simulated BIOLOGY (MI enters the null, INFO-040) and MARKETS (the
  algebraic dipole H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2 with the ~0.993 5-fold
  CV predictor). The GAUGE FORCES (weak, EM) and physics/geology are SELF-POLE
  (MI stays out of the null; equal-entropy is pure channel symmetry). So markets
  is NOT a self-pole/bookkeeping domain -- its dipole carries real predictive
  content, putting it (with biology) on the COUPLING side, distinct from the
  forces. The caricature force<->per-domain-equation hits (EM<->physics,
  weak<->chemistry) did NOT survive real data, so the markets algebraic dipole
  remains the strongest non-biology coupling signal we have. STILL PENDING (no
  list_repos/add_repo in scope, GitHub locked to basic_equations): pull the
  actual Markets dipole JSONs from the Markets repo via a tooled session; the
  markets algebraic dipole FORM + this placement are recorded here meanwhile.

- **MARKETS update (Session 14; STRONG force added + RE-RUN-WHEN-MODELS-IMPROVE
  flag from Greg)**: strong is now self-pole too (INFO-050) -> 4/4 real gauge
  forces on the self-pole; the coupling side still holds exactly two members,
  simulated BIOLOGY (MI-in-null, knob-confirmed) and MARKETS (the predictive
  algebraic dipole). Strong did not move markets' placement. **ACTION FLAGGED BY
  GREG (re-validation, not yet run): RE-RUN THE WHOLE MI/COUPLING DISCRIMINATOR
  ONCE WE HAVE BETTER MODELS.** The coupling-vs-self-pole split (biology+markets
  carry MI/predictive structure; the 4 forces + physics/geology do not) currently
  rests on (a) the SIMULATED domain dynamics (Duffing/Lotka-Volterra/Brusselator/
  Burridge-Knopoff -- toy ODEs, INFO-023/040) and (b) the markets predictor at
  ~0.993 5-fold CV. As the per-domain models get more realistic / higher-fidelity
  (better simulators, more channels, real biology/market data instead of toy ODEs)
  the discriminator must be re-run end-to-end to confirm: does MI STILL enter the
  null only for biology+markets, and do the 4 real forces STILL stay self-pole?
  This is the load-bearing claim of the whole force<->equation arc, so it should be
  the first thing re-checked whenever the models are upgraded -- a result that
  could move (per Rule D, the current reading is one slice, not a settled fact).
  Specifically re-confirm: INFO-040 biology MI~=0.28*H_a + g-knob slope; markets
  H_a^2=a+b(H_aH_b)+c(H_aH_b)^2 predictor; and the self-pole nulls of weak/EM/
  strong/gravity (INFO-047/048/049/050) under any improved real-data construction.
  ALSO (Greg S14): the "how are the forces derived" 3-piece program (see the
  "Queued thread (Session 14)" subsection below) TRANSFERS to markets one-to-one
  -- re-derive the markets dipole equation from raw data (Piece 1), find where its
  coefficients come from (Piece 2), test markets<->biology unification (Piece 3).
  Run the markets pieces in lockstep with the force pieces, same PySR-from-raw-
  data machinery.

### Next direction queued -- principled force-operator-space (Session 12 close)

Greg wants to dive into this. The force<->equation question (INFO-042 (b))
is currently UNTESTABLE on real data because forces and per-domain equations
are different KINDS of object (static mass/angle relations vs MI-vs-entropy
dynamics) and the only bridge (S8 four-force caricatures) is self-grading.
THREAD (speculative, not a claim): build a principled REAL-DATA force-operator-
space so the comparison is data-driven, not caricature.
  - gravity already HAS a real operator-space object (LIGO strain ->
    H_a/H_b/MI, INFO-036/038). The gap is the GAUGE forces.
  - candidate construction: put each gauge force into the per-domain 6-op basis
    from ACTUAL measurement distributions -- e.g. collider event /
    cross-section / decay-rate distributions at varying energy as the two
    channels + their MI -- rather than the deterministic running curve (which
    is a single line, not a 2-channel stochastic object). The measurement
    ensemble (or the spread across observables fixing each coupling) supplies
    the channels.
  - decision gate FIRST (Result Discipline): is there a real dataset that gives
    a force a 2-channel entropy object without us inventing the coupling? If
    not, the force<->equation question stays a live frame, not a probe. Map
    that before building anything.
  - this is the honest path to test whether EM really resembles the physics
    equation (vs being a caricature artifact) and whether the coupling-type
    mapping (gravity <-> equal-entropy/self domains) survives real data.

### Queued thread (Session 14, Greg) -- "what ARE the 4 forces, and where/how derived?"

Greg's S14 question after the 4/4 self-pole result. HONEST BOUNDARY FIRST
(OD-mode + no-mechanism rule + "no dataset contains the origin"): "what a force
ACTUALLY IS" (ontology / why it exists / its mechanism) is NOT a data question --
OD extracts governing equations from raw data, it does not produce ontology or
mechanism, and no dataset contains a force's origin. That part stays a frame,
permanently, unless reframed into something falsifiable. So we do NOT chase
"what it is." BUT "where/how derived" decomposes into THREE data-shaped,
falsifiable pieces, each with a clear data requirement:

  - **PIECE 1 -- re-derive each force's GOVERNING EQUATION from raw data without
    assuming it** (the OD mantra applied to a force; the most OD-faithful piece).
    - gravity/EM HAVE classical force laws -> recoverable by symbolic regression
      from trajectory/field data (precedent: Lemos-Cranmer 2022 rediscovered
      Newton's law + planetary masses from real ephemerides; Schmidt-Lipson
      Hamiltonians). NEED: raw two-body trajectory data (ephemerides / binary-
      pulsar timing / LIGO inspiral phase->separation(t)) for gravity; charged-
      particle tracks in a known field for EM.
    - weak/strong have NO classical force law -- the "equation" is the QFT
      amplitude / propagator / running coupling. Data-shaped analogue = recover
      the ENERGY-DEPENDENCE / resonance shape from measured distributions. NEED:
      data we ALREADY HAVE -- weak: the Z Breit-Wigner propagator (M_Z, Gamma_Z)
      from the dimuon mass spectrum (data/forces/Zmumu.csv); strong: alpha_s(Q)
      running / the femtoscopy source radius R from C(q) (data/strong/).
  - **PIECE 2 -- where the COUPLING STRENGTHS come from** (the parameter-origin
    piece). The SM takes ~26 couplings as free inputs; "where they come from" =
    is there a PREDICTIVE relation among them (predicts a held-out parameter and
    survives)? INFO-042 found real structure (Koide 5-digit, Cabibbo) but NOTHING
    predictive/derived. NEED: the PDG precision parameter set (have it) + an OD
    search for a held-out-predictive relation. High-risk (likely no clean rule --
    itself a result).
  - **PIECE 3 -- are the 4 actually ONE thing (unification)** -- the Track B
    inverse problem (INFO-037), partly built: extract the new-physics FOOTPRINT
    (Delta-b_i, onset scale mu_NP) required to close the running-coupling triangle.
    Mechanism-agnostic, falsifiable. Two-loop already shrank the triangle 3.5x
    with no new physics; FOOTPRINT recoverable, IDENTITY never.

  MOST TRACTABLE "one part" with data IN HAND = Piece 1 for a force we already
  have: recover the Z propagator (weak) from Zmumu.csv, and/or the gravitational
  chirp law from the cached LIGO inspiral. Decision gate (Result Discipline): map
  these alternatives before building; do the cheapest defensible one as a down
  payment. NOTE the scope honesty -- recovering the Z Breit-Wigner is "deriving
  the weak neutral-current's data-level propagator shape from raw data," NOT
  deriving the weak force's mechanism or what it "is."

  **GREG'S S14 DECISION (plan for S15, new session)**: do ALL THREE pieces,
  EASIEST ONE FIRST. Order = (1) Piece 1 weak Z-propagator from Zmumu.csv
  (cheapest, data in hand, pure-fit + PySR symbolic recover of the Breit-Wigner);
  (2) Piece 1 gravity chirp law from the cached LIGO inspiral (data/ligo_M/ +
  GWOSC strain -> f(t) -> df/dt ~ f^(11/3)); (3) Piece 3 unification footprint
  (extend Track B / INFO-037, s12_track_b_inverse.py). Piece 2 (predictive
  coupling relation on PDG) folds in alongside (3). To be run in a FRESH session
  off the v15 kickoff -- this session (S14) recorded the roadmap + did the strong
  build; it did not run a derivation piece.

  **TRANSFERS TO MARKETS (Greg, S14: "a lot of it transfers")**: the Piece-1
  method -- re-derive a domain's GOVERNING EQUATION from raw data by symbolic
  regression WITHOUT assuming it -- is EXACTLY how the markets algebraic dipole
  (H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2) was found, and markets sits on the
  same COUPLING side as biology (INFO-050 frame). So the 3-piece program applies
  to markets one-to-one: Piece 1 = re-derive the markets dipole equation from raw
  market data (already have the form; re-run as models improve, see the Markets
  re-run flag); Piece 2 = where the dipole COEFFICIENTS (a,b,c) come from / a
  predictive relation among them that survives held-out data; Piece 3 = whether
  markets unifies with the other coupling-side domain (biology) under one
  relation. Run the markets pieces in lockstep with the force pieces (same
  symbolic-regression-from-raw-data machinery, PySR).

## Information Layer — Current State (2026-05-25 Session 3)

### What's confirmed at data level

- **OU windowed-null direction** in the {H_a, H_b, H_a^2, H_b^2, H_a*H_b, MI} basis at window=40s, three (gamma, sigma) pairs, three seeds: cleanly extracts to (−1, −1, +2)/sqrt(6) in the (H_a^2, H_b^2, H_a*H_b) subspace. Cos to pure symmetric direction: 0.9994 to 0.9997. Antisymmetric energy fraction: 0.0005 to 0.0012. Fully reproducible.

- **Attractor membership**: the same direction is reached by 8 wildly heterogeneous systems at cos >= 0.99. Members include OU (Gaussian SDE), AR(1) with Laplace innovations (non-Gaussian SDE), GARCH(1,1) (heteroskedastic), Student-t white noise (heavy-tailed IID), logistic map at r=3.9 (deterministic chaos), IID uniform (pure noise), periodic sine + small noise (engineered), and Brownian motion without restoring force (non-stationary diffusion).

- **Off-attractor systems (Session 3 cross-system test)**:
  - **Damped oscillator** (zeta=0.1, omega=2): cos-to-attractor stable across seeds at 0.69–0.74. But the per-seed off-direction varies within a region (inter-seed cosine 0.83–0.99). Reproducibly off the attractor by a consistent amount; exact direction wobbles.
  - **Linear drift** (v=1): cos-to-attractor varies 0.42–0.83 across seeds. Inter-seed cosine ranges −0.28 to +0.93 — different seeds gave nulls pointing nearly opposite directions. Not reproducible at N_REAL=30 in this basis.

- **Drift source diagnostic**: antisymmetric energy fraction on the algebraic basis scales as 1/N_eff where N_eff = window_length / tau_correlation. Confirmed by 15x reduction in anti_frac when window quadruples. Rejected for KDE-specific bias (analytic Gaussian estimator also shows the noise). Domain-general diagnostic.

### What's NOT confirmed (open questions)

- What property defines membership in the attractor. Candidate readings (all currently live): "stationarity at window scale" (Brownian breaks this reading by sitting on the attractor despite non-stationarity), "smooth-observation regime," "rate-of-change/window ratio below some threshold," "physics-related" (rejected — non-physics systems are also on the attractor).
- Whether damped oscillator's off-attractor region is a single point with noise, a small manifold with sub-clusters, or a noisy patch. Untested at higher seed counts.
- Whether linear drift's non-reproducibility is structural (basis cannot capture this system) or sample-noise-driven (more N_REAL would restore reproducibility). Untested.
- Whether varying physics knobs (zeta, omega for damped osc; v for linear drift; etc.) moves the off-attractor positions in interpretable ways.
- Whether other domains (Geo, Bio, Chem) have their own native operator bases that would yield law-level signatures appropriate to those domains. Per Greg's call Session 3, each domain is its own substrate inquiry. Geo lives in 3D, not 1D scalar channels; expecting the current basis to extract Geo's law would be a category error.

### Ledger entries (with discipline-status tags)

**INFO-008 — RETRACTED**: The "Family A cluster" claim (cos 0.97–0.99 among Phys/Geo/OU) is retracted. The cluster was measured under window=20s with finite-sample noise of order 0.05 in coefficient std; Geo data was 1D-projected before extraction, making any comparison to OU's native 1D null structurally meaningless; and at window=40s the OU direction is shared by 8 heterogeneous systems including non-physics ones. The cluster as a domain-level taxonomy does not survive.

**INFO-008a, 008b, 008c, 010, 011 — DEMOTED**: All depend on INFO-008. The "two-family structure" interpretation downgrades to "interesting geometric clustering under a specific protocol; interpretation unmapped." Pending re-evaluation in domain-native bases.

**INFO-012 — ISOLATED FINDING (data confirmed, interpretation rejected)**: Windowed-null extraction on OU at T=100, window=40s, three (gamma, sigma) pairs, three seeds yields V_1 = (−1, −1, +2)/sqrt(6) in (H_a^2, H_b^2, H_a*H_b) with cos >= 0.9994. Initially interpreted as "OU law-level direction"; this interpretation rejected by INFO-014. Data finding stands; physics-interpretation does not.

**INFO-013 — CONFIRMED, REINTERPRETED**: The original T=30 reference's asymmetric coefficients (+0.45, +0.38, −0.80) were finite-window expression-level noise on the symmetric direction. Decays as 1/window-length. Confirmed across multiple tests.

**INFO-014 — ISOLATED FINDING (data confirmed, interpretation open)**: The direction (−1, −1, +2)/sqrt(6) is a strong attractor across 8 heterogeneous systems including non-physics (GARCH, IID uniform, sine wave, deterministic chaos). Working frame: the basis discriminates clearly between "on-attractor" and "off-attractor" behavior, but what property defines attractor membership is not yet identified. Three candidate readings still live (see "Open questions" above).

**INFO-015 — ISOLATED FINDING (Session 3)**: Damped oscillator at zeta=0.1, omega=2 sits reproducibly off-attractor with cos-to-attractor 0.69–0.74 across 3 seeds. The exact off-direction varies within a region (inter-seed cosine 0.83–0.99). Suggests an off-attractor manifold with structure, not a single point. Mapping queued.

**INFO-016 — NULL FINDING / OPEN (Session 3)**: Linear drift at v=1 does not yield reproducible operator-space coordinates at N_REAL=30 in this basis. Inter-seed cosine ranges −0.28 to +0.93. Disambiguation queued: N_REAL sweep at 50, 100, 200, 500 to distinguish (a) basis is structurally blind to this system from (b) sample noise that more realizations would resolve.

**INFO-017 — METHODOLOGICAL (Session 3)**: Drift source diagnostic — antisymmetric energy fraction on the algebraic basis {(H_a − H_b)/sqrt(2), (H_a^2 − H_b^2)/sqrt(2)} flags finite-effective-sample-size noise. Scales as 1/N_eff, amplified by reduced channel correlation. Portable domain-general diagnostic for any extraction in this operator basis.

**INFO-022 — LOCATED FINDING (Session 5 structural; promoted Session 6)**: Rank-3 null subspace in the 6-op basis [H_a, H_b, H_a^2, H_b^2, H_a*H_b, MI] under H_a~H_b~const regime. From three first-order algebraic relations on centered columns. Confirmed by FOUR independent diagnostics in Session 6: KBK rank-gap (with rank-3-strong-plus-1-weak refinement), AI Poincare local-PCA intrinsic dim, AI Poincare two-NN, Levina-Bickel MLE. Robust across 3 estimator families (Vasicek, KDE, kNN/KSG), 5 dt values across 20x range in samples-per-window, 3 seeds. The rank-3 reading is now strong. The MAGNITUDE of the smallest eigenvalues remains procedure-dependent (see INFO-024).

**INFO-023 — LOCATED FINDING (Session 6, new)**: Per-domain ensemble-H + KBK+AI Poincare+SINDy stack produces reproducible domain-specific null directions across 4 simulated domains (physics Duffing, biology Lotka-Volterra, chemistry Brusselator, geology Burridge-Knopoff). Cross-seed cos +0.985 to +0.999 within domain; cross-domain cos mostly < 0.5. The (+1,+1,+2)/sqrt(6) protocol artifact does NOT dominate per-domain (max cos +0.32, min -0.28 across 4 domains x 2 seeds). Independent reproduction of every v5 per-domain claim: geology rank-3 relation at cos +0.99 to v5 (INFO-008b); biology MI ~ poly(H_a) with H_b coefficient 0.003-0.017 (INFO-008c); chemistry-specific cubic content via SINDy deg-3 that is not a Taylor remnant (INFO-008a). Methodology is the stack of KBK 2024 + AI Poincare 2021 + SINDy with extended library, none of which had been combined for windowed/ensemble-H of coupled species before per v5 literature scan ("they never stacked" rule).

**INFO-024 — METHODOLOGICAL (Session 6)**: Eigenvalue floor of operator covariance is min(structural_noise_from_dynamics, estimator_noise_from_procedure). Different procedures have different floors. OU single-trajectory windowed-H pins at ~1e-3 to 5e-5 regardless of sigma, window, dt, or estimator family. Per-domain ensemble-H reaches 2e-7 for geology at N_ens=600; plausibly reaches machine epsilon at larger N_ens via the 1/sqrt(N_ens) noise-reduction scaling. Resolves the v5 machine-epsilon eigenvalue anomaly as procedure-dependent: the rank claim (3 algebraic relations) is robust across procedures; only the eigenvalue magnitude depends on procedure. Practical consequence: state which floor regime you are in before interpreting eigenvalue magnitudes; to drive a floor down, increase ensemble size or use a lower-noise estimator rather than tightening source noise.

**INFO-025 — LOCATED FINDING (Session 7, new)**: Four reproducible per-domain MI-vs-H functional families surfaced by PySR (Brunton/Cao/Liu/Tegmark/Cranmer family symbolic regression) with extended operator set {+, -, *, /, square, cube, exp, log, sqrt} on per-domain ensemble-H data. Cross-seed coefficient reproduction <5% within domain across seeds 11 and 22 (N_ens=600, T=30, dt=0.02): physics Duffing MI = (H_b - H_a)^2 + 0.275-0.280 at complexity 6 (symmetric quadratic in *difference*); biology Lotka-Volterra MI = (0.50 ± 0.02) * exp(H_a / 2) at complexity 5 (exponential in H_a, H_b absent); chemistry Brusselator MI = (0.73 ± 0.02) * H_a + 1.075 ± 0.005 at complexity 5 (linear in H_a); geology Burridge-Knopoff MI = 0.199 constant with loss flat across complexity 1-9 (decoupled). Cross-domain non-overlap; families do not reduce to each other. Polynomial-only methods (v5 SINDy deg-3 library) could not surface these families by construction. v5's biology "polynomial(H_a)" reading is incomplete-not-wrong (Rule D): operator content correct (H_a present, H_b absent); functional family is exponential, not polynomial. Together with INFO-023 (per-domain null direction), this gives two independent reproducible per-domain signatures supporting the "per-domain expression of substrate" frame.

**INFO-026 — METHODOLOGICAL (Session 7, new)**: For regression on time-series ensemble-H data, block-CV (contiguous time blocks) is catastrophically negative across non-stationary domains (physics, biology, geology block-CV ranges -0.5 to -80) due to system passage through qualitatively different dynamical regimes across the trajectory. Chemistry Brusselator is the only stationary domain among the 4 simulators (block-CV positive at +0.4 to +0.8). Random-CV (shuffled k-fold) overestimates true OOS for correlated time series but isolates functional-form fit from the stationarity confound. Use both readings; the gap between them is itself a domain signature for stationarity. Substantive finding within: GP joint(H_a, H_b) on biology reaches random-CV R^2 = 0.97-0.98 vs poly3 joint at 0.81-0.86. The +0.12 gap is real nonlinear cross-coupling beyond polynomial reach. For physics, chemistry, geology, polynomial joint matches GP joint within 0.05.

### Experiments queued (priority order)

1. **N_REAL sweep on linear drift** (50, 100, 200, 500). Disambiguates INFO-016: structural blindness vs sample noise. Cheapest decisive test. **Run first.**

2. **Multi-seed damped oscillator mapping**. 10+ seeds at zeta=0.1, omega=2 to characterize the off-attractor region. Then parameter sweeps: zeta in {0.05, 0.1, 0.2, 0.5}, omega in {1, 2, 5}, varied independently. Tests whether the off-direction encodes damping rate, frequency, or something structural.

3. **Cluster the misses by structure**. Around damped oscillator: exponentially-modulated noise, decaying-amplitude OU, chirped signals. Around linear drift (if reproducibility resolves): exponential growth, polynomial drift, Brownian+drift. Tests whether off-attractor positions cluster by type of departure.

4. **Boundary mapping**. Slowly varying OU parameters; sinusoidally forced OU at varying frequencies. Find where systems leave the attractor and along which coordinate.

5. **Stress-test the attractor (base-of-structure heuristic test)**. Subject OU and other attractor members to extreme conditions: very high sigma, very low gamma (under-damped), multiplicative noise, nonlinear drift. Does the attractor finding survive? Per Greg's heuristic, a true base should remain stable under stress.

6. **Domain-native operator bases**. For non-OU domains (Geo 3D, Bio multi-variable, Chem multi-species), construct operator libraries that match the native dimensionality. Stay in scope of the relevant domain. Each extraction is its own inquiry.

### Files produced this session (2026-05-25 Session 3)

Need to be saved to E:\information_layer\ AND mirrored to F:\Factory\knowledge\information_layer\:

- `L1_windowed_null_OU.py` — main L1 extraction script
- `L1_rank_extraction.py` — top-k singular subspace analysis of pooled nulls
- `L1_drift_source.py` — drift source diagnostic with sweep modes
- `cross_system_test.py` — alpha/beta/gamma cross-system battery
- `L1_results_FULL.json` — full L1 run output
- `L1_rank_extraction.json` — rank extraction output
- `L1_rerun_w40.json` — window=40 confirming run
- (cross_system_test.json was not generated because sweeps were run in chunks; per-cell numbers are in SESSION_HANDOFF_2026-05-25_v3.md)

## Architecture (current)

- **DeepNova**: 92 passing tests, 22 manifests, persistent evidence graphs, PPO retrieval policy learner. F:\Factory\.
- **VOXA**: voice interface layer. Cloud-hosted TTS MCP server.
- **Agent Factory**: 23 agents, 5 divisions, F:\Factory\.
- **Token Optimizer**: deployed at optimizer.davisai.ai, Stripe live.
- **OD provisional patents**: 3 filed March 24, 2026 (Blind Lindblad/QORA; Hilbert Unification; Decoherence Suppression).

## Defense Pipeline (status as of last update)

- DARPA Bio Attribution (confirmed top-10), CyPhER Forge (abstracts in), TTO BAA (April 17 exec summary), DIU PRISM (submitted), CIA (KV3UCQ1A submitted), IQT (submitted), MDA MAA, AFWERX.
- **Steve "Bucky" Butow** (DIU Space Portfolio): personal email contact, capability email sent.
- **Carl Saab** (Cleveland Clinic): OD outreach engaged, doing his own research. Highest-probability PhysioNet reference.
- **Roland Rott** (GE HealthCare Imaging): connected, MRI proof-of-concept brief (BioForge) delivered.
- SAM.gov UEI: CQ56XYFZL4E6, ref INC-GSAFSD20794734. CAGE pending.

## Standing Decisions

- LlamaIndex: declined (duplicates DeepNova).
- Robyn: declined (web is not bottleneck).
- Nous Atropos: worth evaluating for DeepNova policy learner.
- Hermes 4 14B: recommended for local reasoning on data-sensitive use cases (SENTINEL).
- HomeLift: dormant. Both Neo4j instances safe to cancel.

## Session Handoff Pointer

For the latest (Session 18) session, read `SESSION_HANDOFF_2026-06-02_S18.md`, then the
Session 18 note below. Headline: backlog 6c (does gravity couple to TIME?) answered
DECISIVELY on the positive side with THREE governing-law recoveries. The precise-product
GPS route was a definitional NULL (INFO-058: the GR clock term -2(r.v)/c^2 is modeled out
of IGS/CODE products). The TERM-RETAINING GPS route (INFO-059) then recovered the
time-dilation coefficient -2/c^2 from raw RINEX observations on the eccentric Galileo GREAT
sats at k/truth 1.02-1.04, z=380 sigma (cross-source, non-circular). And the INDEPENDENT
pulsar route (INFO-060) recovered, from raw Arecibo TOAs of PSR B1913+16, both the orbital
decay dP_b/dt (ratio 1.005 to GR, ~17684 sigma detection) and the Einstein-delay gamma
(0.014% from published). Two gravity-time mechanisms (clock-rate dilation + GW-emission
orbital decay), GNSS-convention-independent. Capability brief updated (gravity now has a
time-dilation recovery alongside the inspiral chirp). Plus O3 (INFO-061): GW170817 BNS
chirp mass recovered by pycbc matched-filter -- detector-frame M_c 1.200 (0.19% from
catalog), H1+L1 independently agree -- removing the S17 ridge's absolute-mass bias.
Earlier-probe context below.

For the (Session 17) session, read `SESSION_HANDOFF_2026-06-02_S17.md`, then
the Session 17 note below. Headline: JOB 1 (CLAUDE.md drift) FIXED — this file is now
canonical through S17. Backlog #1 (construction-vs-nature, INFO-051) RESOLVED — the
equal-entropy clustering is bookkeeping (scaling a channel is exactly MI-invariant yet
sets the marginal-entropy asymmetry by a units choice; MI is the only scale-invariant
quantity in the basis). Then the deliberate pivot off coordinate-auditing onto
gravity-FORWARD ground: backlog #3 (INFO-052) recovered the gravity inspiral chirp law
from raw GW150914 strain by a CWT ridge — both detectors agree at R^2 0.99, M_c ~38 vs
catalog ~31 — decisively beating the S16 Hilbert (R^2 0.001); GW170817 confirms the
law form (R^2 0.88) with a lever-arm-limited mass. This is a KNOWN law recovered
(method validation), NOT a new law. Then ("MI next") INFO-053 characterized the
surviving physical signal: inter-detector MI at the merger is PHYSICS-BEARING — peaks
at the physical 7 ms lag, z=15.5 vs a time-slide null, and its excess is entirely
waveform phase/time structure (not loudness). O1 (INFO-054, beyond-chirp): subtracting
the recovered Newtonian inspiral cuts inter-detector MI ~2x but a significant residual
remains at the physical lag -- INCONCLUSIVE for beyond-GR (residual most plausibly
un-modeled GR). O1-real (INFO-055): the rigorous beyond-GR test -- pycbc IMRPhenomD
matched-filter subtraction -- gives a clean NEGATIVE: removing the full GR waveform
collapses the physical-lag MI to the null (0.54 z=18 -> 0.23 == null), so the MI merger
signal is FULLY GR -- no beyond-GR structure on this axis. CORRECTION (Rule D, Greg
caught S17): this does NOT close O2 (gravity-couples-to-time) -- that coupling is
INTRINSIC to GR, so "it's all GR" is consistent with the hunch, not against it; O2 is a
framework/representation question (express gravity's GR-real time coupling as a flow
dipole; does it distinguish gravity from gauge forces -- H-C) and stays OPEN. Gravity
footholds scaffold (F1-F3 confirmed / C1-C3 cleared / O1 resolved NEGATIVE for
beyond-GR / O2 PARTIALLY answered INFO-056 / O3 open) in the S17 handoff: NO new gravity
LAW found -- the surviving physical signal is fully standard GR; the OD method is
validated (recovers known laws); a beyond-GR new-law search needs a different observable
or many events. O2/6c (INFO-056): flow is NOT unique to gravity (strong runs too) --
simple hunch refuted; "gravity flows in TIME specifically" stays open but construction-
confounded (a real test needs clock/time-dilation data).

For the (Session 16) session, read `SESSION_HANDOFF_2026-06-02_S16.md`
first, then `BACKLOG_tests_and_probes.md` (the queue + the standing backlog-first
rule), then the Session 16 note below. Headline: WEAK and STRONG governing laws
re-derived from raw data (Z Breit-Wigner M_Z = 90.75 GeV = 99.5% of PDG from real
CMS dimuon; QCD asymptotic freedom recovered from 13 measured alpha_s(Q) points,
positive 1/alpha_s-vs-lnQ slope, no beta function assumed); gravity chirp law NOT
cleanly recovered on either GW150914 or GW170817 (method-limited — naive whitened-
Hilbert instantaneous frequency too noisy; needs Q-transform/matched-filter,
backlog #3) and recorded as an honest non-result; "time-blind" RESOLVED as a method
identity (pooled column-covariance extraction is row-permutation-invariant BY
CONSTRUCTION) while the TIME-RESOLVED null carries strong time structure (merger
block distinct); H-D trajectory pinned (substrate->DEPART-at-merger->return-to-
NOISE, with "substrate" = the detector-noise reference, so H-D stays a FRAME). Data
note: everything measured clusters on the equal-entropy substrate and the ONLY
departures are gravity-associated; open question (backlog #1) is whether that
clustering is nature or construction (equal-marginal-entropy bookkeeping). MI-in-
null coupling DISPROVED (Greg, S16) — do not build on it. Markets parked. The S13/
S14/S15 detail is in the notes below and their handoffs.

For the (Session 15) gravity/flow-dipole/time/black-hole exploration, see the
Session 15 note below + `SESSION_HANDOFF_2026-06-02_S14-S15_COMBINED.md` /
`CLAUDE_session_note_2026-06-02_S15.md`.

For the (Session 14) session, see the Session 14 note below (INFO-050).
Headline: the STRONG force real-data operator object was built (ATLAS DAOD_HION14
Pb-Pb two-pion femtoscopy, read with pure-Python uproot -- no CMSSW/VM -- after
the CMS RECO path was rejected as uproot-unreadable), completing a clean 4/4: all
four real gauge forces (gravity/weak/EM/strong) sit on the equal-entropy
SELF-POLE with MI NOT in the null. The genuine BE correlation is confirmed
present (C(q<0.1)~1.10) yet stays out of the null even in the low-q femtoscopy
window. MI-in-null coupling remains ONLY in simulated biology. NO synthesis
across construction types (strong compared within-type to weak). Then read the
Session 13 note (INFO-044 through INFO-049). Headline of the two cheap
coupling/LIGO follow-ups: chemistry's
residual tracks the Brusselator B knob in the oscillatory regime (INFO-044, the
chemistry analogue of biology's MI-slope-vs-g); the MI-driven LIGO merger
departure GENERALIZES across all 12 events (INFO-045, S11 GW150914 thread
confirmed 10-11/11) while the full noise/event reversal does not; and nothing in
MI sits before/after the merger -- the genuine before/after structural difference
is non-stationary detector noise, not source inspiral/ringdown (INFO-046). The
Session 13 HEADLINE (gate PASSED, two real builds done, strong deferred):
principled force-operator-space. Real gauge-force objects built for WEAK (CMS
Z->mumu, INFO-047) and EM (HBT, INFO-048 + g2(0) closure INFO-049); gravity
already via LIGO. All sit on the equal-entropy SELF-POLE with MI active (out of
the null) -- the gauge forces look like physics/geology, NOT the coupling pole;
the caricature EM<->physics / weak<->chemistry hits do NOT reproduce on real
data. Biology remains the ONLY genuine MI-in-null coupling. Open: strong force
(heavy), Markets-repo JSON pull (no list_repos in scope).

For the (Session 12) session, read
`SESSION_HANDOFF_2026-06-02_v12_results.md` (in repo root) first, then the
Session 12 note below (INFO-039 + the Track A 12-event null + Track B inverse
problem). Headline: Track B new-physics inverse problem built on the PDG
couplings (two-loop running alone shrinks the unification triangle 3.5x with
no new physics; required Delta-b footprint surface = differences only, never
identity; gravity needs a power-law->log form change); the four per-domain
governing equations consolidated into `od_per_domain_equations.json` from
in-repo result JSONs; and the info-dipole paper (davisai.ai/dipole) connected
to the extraction machinery (INFO-039, MAPPED, deflationary): the paper's flow
form `dMI/dt ~ sum c_self*H_i^2 + sum c_cross*H_i*H_j` IS the operator family
our windowed-null extraction operates on, but its opposition signature in the
quadratic subspace coincides with the equal-entropy attractor identity
(physics cos 1.000) -- a structural identification, NOT new coupling evidence.
Track A full 12-event LIGO null run executed (resume-safe after a GW170817
crash); markets pull dropped per Greg.

For the (Session 11) session, read
`SESSION_HANDOFF_2026-06-02_v11_results.md` (in repo root) first, then the
Session 11 note below (INFO-038). Headline: per-event LIGO readout on 3
events (GW150914/170104/151226) run SEPARATELY with no pooling -- per-event
entropy asymmetry |H_a-H_b| varies (0.62/0.74/1.61) and inversely tracks
how hard noise sits on the equal-entropy attractor, confirming INFO-036's
equal-entropy reading at the per-event level (INFO-038, isolated). Full
12-event batch + per-event off-source null distribution BUILT
(s11_ligo_batch.py), not yet run. OD inputs consolidated onto main
(four-force + per-domain JSONs + stores); medical stores left on their own
branch; main synced to continuity so the SessionStart hook runs every
session. Open: pull dipole JSONs from the Markets repo + list the flow
dipole equation separately (Greg's call). Track B (new-physics inverse
problem) framed, not yet built.

For the (Session 10) FIRST REAL-DATA session, read
`SESSION_HANDOFF_2026-06-02_v10_results.md` (in repo root) first, then
the Session 10 note above (INFO-034 through 037). Headline: caricature
work retired by Greg's call ("no point fine-tuning fake data"); two
four-force real-data sets run -- LIGO GW150914 (method detects the
merger via inter-detector MI; the (-1,-1,+2)/sqrt6 attractor confirmed
on real data as an equal-marginal-entropy artifact, not coupling) and
PDG coupling unification (three gauge forces share the running substrate
form with per-force expression slopes, but NO single SM unification
point -- a triangle spanning ~1e4 in energy; gravity power-law, outside
the form). Plus two method-hardening items on the toy systems before the
pivot: INFO-034 (flip is estimator-robust under KSG) and INFO-035
(substrate invariance is MIXED -- holds biology/geology, regime-bounded
physics, fails chemistry).

For the Session 9 double-check + correction of the Session 8 gravity
result, read `SESSION_HANDOFF_2026-06-02_v9_results.md`, then the Session
9 note above (INFO-033). For the Session 8 record (four-force probe,
INFO-027 through 032), read `SESSION_HANDOFF_2026-05-26_v8.md`.

For Session 7 context (GP regression + PySR symbolic regression on
per-domain ensemble-H data, four reproducible per-domain MI-vs-H
functional families), read `SESSION_HANDOFF_2026-05-26_v7.md`. It contains Session 7's two experiments
(GP regression with poly1-3 baseline and in-sample / block-CV /
random-CV evaluation; PySR symbolic regression with extended
operator set on per-domain ensemble-H data). Headline: four
reproducible per-domain MI-vs-H functional families (physics =
(H_b - H_a)^2 + const, biology = 0.5*exp(H_a/2), chemistry =
linear in H_a, geology = constant) with cross-seed coefficient
variation <5%, cross-domain non-overlap. v5 biology reading
incomplete-not-wrong (Rule D): operator content right, functional
family was wrong. Per-domain differentiation now has TWO
independent reproducible signatures (null direction from Session 6
INFO-023 + functional family from Session 7 INFO-025). New ledger
entries INFO-025 (located) and INFO-026 (methodological).

For Session 6 context, read `SESSION_HANDOFF_2026-05-26_v6.md`.
It contains Session 6's six experiments (KBK pipeline, AI Poincare
rank check, estimator-family sweep, window-size scan, SINDy with
extended library, per-domain stack on 4 domains, sigma scan) and
their joint reading. Headline: v5 INFO-022 rank-3 claim
independently confirmed by FOUR diagnostics; per-domain ensemble-H
stack reproduces every v5 per-domain claim (geology rank-3
cos +0.99, biology MI signature with H_b absent, chemistry
chemistry-specific cubic, physics Taylor identity) with cross-
seed cos +0.985 to +0.999; v5 machine-epsilon eigenvalue
magnitude is procedure-dependent (estimator-noise vs structural-
noise; per-domain ensemble-H reaches 1e-7, OU windowed-H pins
at ~1e-3).

For Session 5 context (three-thread probe results, operator-noise
bypass, projection-rule sweep, high-seed scrambled, literature
scan), read `SESSION_HANDOFF_2026-05-26_v5.md`. It contains Session 5's three-thread probe results
(operator-noise bypass, projection-rule sweep, high-seed scrambled) and
their joint reading — the (+1,+1,+2)/sqrt(6) direction is a protocol
artifact of the operator basis having a 3D null subspace under the
H_a ~ H_b ~ constant regime, not a property of input systems. INFO-014,
INFO-018, INFO-019 are retracted at interpretation level; data stands
(Rule D — incomplete not wrong). The per-domain algebraic equations from
earlier sessions (chemistry quadratic, geology rank-3, biology MI) are
NOT affected by Session 5 and remain on the table. New structural
finding: INFO-022 (rank-3 null subspace from first-order algebraic
relations in the operator basis).

The v4 handoff (`SESSION_HANDOFF_2026-05-26_v4.md`) contains the Session
4 raw data that Session 5 read. The Session 3 v3 handoff is at
`E:\information_layer\SESSION_HANDOFF_2026-05-25_v3.md` (Greg's local).
The early-Session-3 handoff in repo (`SESSION_HANDOFF_2026-05-25.md`)
contains the per-domain algebraic equation coefficients that are
preserved through Session 5.

## Note (Session 25 update — 2026-06-08) — MARKETS: PySR/Julia toolchain FIXED; dipole VALIDATED real on the 128-dim per-pair basis

S25 cleared the S24 blocker and executed kickoff §0–§2 on the RIGHT basis. Full detail:
`SESSION_HANDOFF_2026-06-08_S25.md`; next steps `KICKOFF_2026-06-09_S26.md`; standalone note
`CLAUDE_session_note_2026-06-08_S25.md`.

- **Toolchain FIXED (durable).** The S24 "PySR hangs" was juliapkg's first-run Julia download stalling on the
  flaky `julialang-s3` mirror (resets even curl). Pre-placed Julia 1.11.9 + set env `PYTHON_JULIAPKG_EXE`;
  `import pysr` (1.5.10) + a real fit now work (~12s cached). [[pysr-julia-local-toolchain]]
- **Dipole is REAL on the 128-dim per-pair basis.** Ran the verbatim originals (`_markets_algebraic_dipole.py`,
  `_markets_dipole_kfold.py`) on real `result.operator_coefficients` (128-dim) from
  `E:\refrag\discoveries\operator_discoveries\`: the algebraic surface reproduces per pair (R²_quad up to 0.975,
  convex +γ) while POOLED collapses to 0.49. Honest validation on PRE-ENTRY (no look-ahead) coefficients
  (`_preentry_cs100`, 100/100): classifier acc 0.947 AND a label-permutation null at chance (0.50) →
  **real-vs-null z = +9.6 across all 12/12 pairs**. Genuine predictive signal, not a D≫N geometric artifact.
  [[dipole-real-on-128dim-per-pair]]
- **Why S24 collapsed (Greg, confirmed):** the earlier run **mashed all sources together instead of analyzing
  them separately** — pooling forces the degenerate Hb=−Ha tautology. KEEP PAIRS SEPARATE; never pool across
  pairs. (The S24 15-dim hand-built c_i + per-feature standardizer was also off-BUILD_PLAN.)
- **PySR discovery (kickoff §2 — discover, don't hardcode):** PySR reproducibly discovers a convex dipole
  surface per pair (5/12 identical form across 3 seeds), and the crypto data prefers a **cubic** over the
  hardcoded quadratic ("data picks the form").
- **Correct construction already in repo:** `odcore/dipole_predictor.py`
  (`build_centroids`/`project`/`algebraic_dipole_over_trades`) is the verbatim 128-dim port; the fix is a
  DATA-PATH change — feed raw 128-dim coeffs per pair, NOT the 15-dim `dipole_trade.py` vector.
- **Still owed (Result Discipline):** walk-forward / non-random split (the discovery JSONs lack trade
  timestamps), net-of-cost PnL, and the LARGER trade-set run — the 15-source 16–30 day (~16k-trade) set,
  attached from an E-drive folder (Greg) — all S26.

Prior S24 below.

## Note (Session 24 update — 2026-06-08) — MARKETS: dipole gate FAILS at full scale; root cause = off-BUILD_PLAN basis; reoriented

S24 ran the S24-kickoff #1 (the 15-source chem-dipole validation) to completion, read the numbers, and
reoriented the whole thread back onto `BUILD_PLAN.md` (the WRITTEN-IN-STONE OD / PySR-Julia rebuild plan,
commit `da9dc63` on this branch). Follow it to a T; any deviation cleared with Greg first.

**Result (full scale):** POOLED 16,003 trades (13.1% win). The in-sample control + embargoed walk-forward
gate FAIL in all three modes — `none`/`pool` degenerate to the `H_a==-H_b` tautology (r2=1, c=0), `scale`
is linear (c=-0.0006, r2_lin=0.998); WF net -15 to -26, hit <=40%, z<=0.5. The reference convex
c=1.309/R^2=0.943 reproduced in NO mode. No net-of-cost edge; the gate correctly rejects.

**Root cause (diagnosed, sources kept SEPARATE per Greg):** the collapse is a property of the 15-dim
hand-built c_i, not of the validation. It is collinear (participation-ratio eff-rank 7.82/15) and
non-discriminative (best feature Cohen d=0.19; multivariate AUC 0.574 random / 0.513 time-ordered = no OOS
signal). Per source, NO source reproduces convex c>0.

**The reorientation:** against `BUILD_PLAN.md` the S22-S24 dipole port deviated three ways — (1) WRONG
BASIS: a 15-dim hand-built coupling vector instead of the plan's ORIGINAL 128-dim `operator_coefficients`;
(2) HARDCODED a fixed quadratic instead of PySR-DISCOVERING the form; (3) POOLED all sources instead of
per-pair. The S20 blocker is now partly resolved — the originals (`_markets_algebraic_dipole.py` etc.) are
ON DISK at `E:\Markets`; reading the core confirms H_a/H_b are centroid projections of RAW 128-dim
`operator_coefficients` per pair (read from `E:\refrag\discoveries\operator_discoveries\`). The richer
labeled set `_full_pipeline_winners_preentry_cs100_v2\summary.json` (1,054 x ~128-dim) is the "where it
worked" reproduction target. Tier-3 originals (s12/s13/od_per_domain) still missing.

**Toolchain:** PySR 1.5.10 installed but NOT loading (import hangs on Julia precompile; `julia` not on
PATH). S25's FIRST action is to make the SessionStart PySR/Julia bootstrap actually load before any
discovery.

**Plan hygiene:** `MARKETS_OFFENSIVE_LAYER_PLAN.md` is a SEPARATE older defensive plan, NOT this; identify
the plan by the PySR/Julia/5-step test. Memory: [[markets-canonical-plan]], [[follow-canonical-plan-rule]].
Full detail `SESSION_HANDOFF_2026-06-08_S24.md`; next steps `KICKOFF_2026-06-09_S25.md`.

## Note (Session 23 update — 2026-06-08) — MARKETS: dipole trade runner built; data scaled to a current month + git unstuck

S23 built the runner that earns the chem-dipole validation and fixed the data pipeline it runs on.

**Built (`scripts/od_trade_dipole_run.py`, commits `26be859`/`b97d377`):** replays the
adaptive_backtester generators (ALL generators incl. the dipole one — Greg's Option-2 call) on
minute bars to get labeled win/lose trades; slices each trade's pre-entry orderflow window from
the 1s BinSeries; builds the 15-dim c_i (`dipole_trade.trade_coupling_vector`); runs the
in-sample positive control + embargoed walk-forward gate (`odcore/validation.py`), printing
three standardization modes (none/scale/pool). It is **resumable** — each source checkpoints to
`realbins/_dipole_cache/`, so a killed run resumes; `--eval-only` gives an instant readout.

**Data unblock:** the git `data/btc-bins`/`data/eth-bins` branches had stalled at 2026-05-17
(~10 days). The collectors kept writing locally to `E:\Markets\live_data_history\<date>\<src>_bins.jsonl`
(~2026-02-23 -> today, 5 assets x 3 venues). `scripts/build_realbins.py` merges that daily JSONL
into the merged `realbins/<src>_bins.json` both loaders consume unchanged; rebuilt 30 days x 15
sources. Pushed **gzipped** 30-day bins back to git (`aa4736d`/`977f979`; under GitHub's 100-MiB
cap) and `session_start.sh` now gunzips — so future hooks materialize current data.

**Unresolved finding (S24 to confirm at scale):** on a small/imbalanced smoke sample the
in-sample dipole did NOT reproduce the reference convex `c=1.309, R^2=0.943` — the quadratic
collapses to `c~=0` in all three modes (pool-mode mean-centering forces antiparallel centroids
=> `H_a==-H_b`, a tautology and a **latent issue in the ported core**; none/scale stay linear).
Likely cause: the 15-dim c_i is too thin/collinear. STRONG LEAD: the local folder
`_full_pipeline_winners_preentry_cs100_v2` (2026-05-28) may already hold a richer ~100-dim
labeled trade set.

**Honest status:** no net-of-cost edge demonstrated; the gate (`odcore/validation.py`) is
unchanged and unmet. The full 15-source validation numbers are still pending (run is long +
resumable; relaunched at session end) — that is S24's first action. Hygiene fixed so S24 starts
fast: `safe.directory '*'` is global (no more "dubious ownership"); onboarding docs live IN GIT
(never re-upload/paste); the data branches are current. See `SESSION_HANDOFF_2026-06-08_S23.md`
+ `KICKOFF_2026-06-08_S24.md`; memory `markets-data-lives-local-not-git`.

## Note (Session 22 update — 2026-06-07) — MARKETS: chem-dipole construction resolved + core ported

> ALREADY FOLDED IN — do not re-upload/re-apply. This S22 delta is merged into this master
> in-repo. Per the START-HERE workflow rule (lines 14-21): never re-upload the whole master and
> never re-paste an already-folded session note. Next session: read the handoff + kickoff, then
> fold only the NEW (S23+) delta and bump the header line.

Branch `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets). No PR. All Operating
Rules + Result Discipline in force. Zero synthetic. Full detail: `SESSION_HANDOFF_2026-06-07_S22.md`;
next steps: `KICKOFF_2026-06-07_S23.md`.

Headline: resolved S22 priority #1 (the chem dipole). The originals were NOT in `Basic_equations`
(Greg checked) and NOT in Markets git history (all 15 refs searched); the verbatim original is a
LOCAL untracked file at `E:\Markets\_markets_algebraic_dipole.py`. It defines H_a/H_b as NORMALIZED
PROJECTIONS of a per-trade operator-coefficient vector onto in-sample win/lose centroids
(H_a=<c,c_win>/||c_win||, H_b=<c,c_lose>/||c_lose||; fit H_a^2=a+b*(H_a*H_b)+c*(H_a*H_b)^2) -- NOT
windowed Vasicek entropy of buy/sell volume. That mismatch is the entire c~=0 collapse (near-
symmetric buy/sell entropies -> H_a~=H_b -> collinear regressor -> gamma unidentified; epistemic
rule #4 confirmed: tool-wrong, not signal-absent). The two other "missing" files
(s12_coupling_decomposition / s13_chemistry_residual) are already covered by `odcore/null_extract.py`
(the 5-step coupling model), so only `dipole_predictor.py` was wrong.

Pushed (commit `d129c19`): `odcore/dipole_predictor.py` rewritten to the verbatim construction
(build_centroids / project / algebraic_dipole_over_trades; legacy window fit kept for
coupling_scanner); `odcore/dipole_trade.py` NEW wires it onto the current 5-step model -- per-trade
c_i = 15-feature coupling vector (Greg-approved decision #1), per-feature standardized, centroid-
projected; portable (channel arrays + labels as args). NOT validated: reproducing R^2 is structural,
not an edge; the predictor must clear `odcore/validation.py` (S20/S21: unblocked OD loses net-of-cost).
NOT done (S23 #1): the runner that pulls labeled trades + pre-entry channels, fits with WALK-FORWARD
centroids, and validates.

Environment: `E:\Markets\.claude` is HARD-LOCKED (exFAT open handle) -- in-place checkout impossible;
worked entirely from git refs and committed via git plumbing (temp index, no checkout). Avoid
`Remove-Item` while cwd is `E:\Markets`. Prior S21 below.

## Note (Session 21 update — 2026-06-05) — MARKETS: OD layer wired through the platform

> ALREADY FOLDED IN — do not re-upload/re-apply. This S21 delta is merged into this master
> in-repo. Per the START-HERE workflow rule (lines 14-21): never re-upload the whole master and
> never re-paste an already-folded session note. Next session: read the handoff + kickoff, then
> fold only the NEW (S22+) delta and bump the header line.

Branch `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets). No PR. All Operating
Rules + Result Discipline in force. Zero synthetic. Full detail: `SESSION_HANDOFF_2026-06-05_S21.md`;
next steps: `KICKOFF_2026-06-05_S22.md`.

Headline: continued the S20 OD signal-core rebuild by PLUMBING the OD machinery through the
running platform (the unblocked Section-2 build; the chem-dipole port stayed BLOCKED on
`Basic_equations`, files incoming from Greg). Built `backend/odcore_store.CouplingStore` (loads
realbins, computes the OD layer, cached + refreshed off the polling loop on a thread, ~84s,
self-gated, lock-guarded) + 5 authed endpoints (`/api/coupling_matrix`, `/api/leadlag/{asset}`,
`/api/dipole_signals`, `/api/strength/{asset}/{venue}`, `/api/decoupling`). New frontend
"Coupling" tab (CouplingMatrix / LeadLag / StrengthOverTime / DecouplingFeed). Executor: wired the
OD generators into the adaptive_backtester pool, OD-native sizing (opt-in) and a circuit-breaker
gate. Housekeeping: consolidated 5 duplicate minute-bar loaders into
`markets_adapter.load_minute_bars` (kept odcore import-free of the platform shell so it stays
portable to Basic_equations); defaulted `MARKETS_WATCH_DEMO_MODE` off.

HONEST STATUS UNCHANGED (Result Discipline): re-ran the promotion gate on real BTC
(`scripts/od_backtest.py`, 15,396 minute bars, buy-hold -4.52%) — every unblocked OD signal still
LOSES net-of-cost (dipole_direction WF -11.8% taut z 1.2; ofi_momentum -177.9%; ofi_fade -188.2%;
momentum5 -91.8%). So the OD layer is DIAGNOSTIC/shadow, NOT the live signal source — the regime
classifier remains the source. Greg's S21 question "what to make OD the source": EARN it (clear
the `odcore/validation.py` gate: net>0 after fees+slip, beat baselines under walk-forward,
tautology z>>2-3) THEN WIRE it (flow od_* fields through /api/signals -> OD-native sizing; switch
the emit decision to the OD generator; then unwire PELT). The two edge candidates remain the real
chem dipole (#1, blocked) and cheaper execution (maker-rebate/tick data; cross-venue reversion is
real at taut z 3.0-3.6 but cost-bound). Prior S20 below.

## Note (Session 20 update — 2026-06-03) — MARKETS: OD signal-core rebuild on real data

> ALREADY FOLDED IN — do not re-upload/re-apply. This S20 delta is merged into this master
> in-repo. Per the START-HERE workflow rule (lines 14-21): never re-upload the whole master
> and never re-paste an already-folded session note. Next session: read the handoff + kickoff,
> then fold only the NEW (S21+) delta and bump the header line.

Branch `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets). No PR. All
Operating Rules + Result Discipline in force. Zero synthetic data (Greg). Full detail:
`SESSION_HANDOFF_2026-06-03_S20.md`; next steps: `KICKOFF_2026-06-03_S21.md`; decisions +
open questions: `BUILD_QUESTIONS.md`.

Headline: built a new `odcore/` package bringing the REAL OD machinery into the Markets repo
(which previously had only a crude order-flow-imbalance dipole). The full pipeline runs
end-to-end on REAL collector bins (BTC/ETH x Coinbase/Kraken/Bybit, ~10.7 days of 1s bins on
the data/* branches), and PySR symbolic regression (Julia backend, 1.5.10) DISCOVERS equations
from real market data (recovered `MI ~= -0.028*H_a*exp(H_b)+0.023` on real BTC order-flow).
Modules: operators (windowed basis), null_extract (coupling discriminator + INFO-040/041
guards + biology MI-slope / chemistry residual-fraction strength meters), leadlag (S19 raw
cross-cov-over-lag right tool), dipole_predictor (algebraic chem dipole), symbolic (PySR),
coupling_scanner (tautology-killing circular-shift null + decoupling events), channels, io,
validation (walk-forward + real costs + tautology null), sizing (OD-native, NOT Kelly),
stacking, generators. SessionStart hook added (PySR/Julia + real-bins bootstrap).

REAL findings (Result Discipline): equal-entropy attractor reproduces on real data (quad
|cos| 0.9996); cross-venue coupling Coinbase<>Bybit-perp lag-0 cc=0.656 z=580 (venues
synchronous at 1s; sub-second leads need tick data); 145 real decoupling events. HONEST NULL:
the signals buildable from the UNBLOCKED pieces have NO net-of-cost edge (all lose to 3bps
costs; tautology-z ~1); cross-venue reversion is STATISTICALLY REAL (tautology z=3.0-3.6 at
10s) but per-trade edge < cost. The chem QUADRATIC dipole does NOT reproduce on the
reconstructed channels (real buy/sell entropies near-symmetric -> trivial identity, c~=0);
tried 5 channels x 3 timescales x 3 conditionings. BLOCKER: the exact construction lives in
`DavisAI1974/Basic_equations` (`_markets_algebraic_dipole.py` etc.), which is ACCESS-DENIED
this session (scope locked to davisai1974/markets). ACTION (Greg): add `Basic_equations` to
session scope so the originals port verbatim. Nothing fabricated; nulls reported. Prior S19
below.

## Note (Session 19 update — 2026-06-03) — FLOW DIPOLE EQUATION: wrong tool, and the OTHER dipole solves for time

Branch `claude/kickoff-claude-handoff-0vfgz` (main untouched; no PR). All Operating Rules in
force; no new Rule. Continuity restored at session open (branch was cut stale at S12; fast-
forwarded onto the S18 work branch). Full detail: `SESSION_HANDOFF_2026-06-03_S19.md`. Ran S18
backlog #1 (the flow dipole equation), then followed Greg's live steers.

Confirmed paper flow form (davisai.ai/dipole §2.2 verbatim): dMI/dt ~ sum c_self,i*H_i^2 +
sum c_cross,ij*H_i*H_j + linear; ratio C = H_self/H_cross; opposition = self vs cross opposite sign.

EPISTEMIC RULES sharpened by Greg this session (carry forward; not new Operating Rules, they
refine Result Discipline): (1) don't be determinative about one test; (2) 4 consistent tests
are a STRONGER signal than 1 outlier — they are NOT equal; do not romanticize the outlier
(inspect it, no tent-widening); (3) a candidate that shows in only 1 of N systems is, by that
inconsistency, a POOR candidate (Base-of-Structure); (4) first-try-not-only-try — a uniform low
result is as much evidence the TOOL is wrong as that structure is absent; (5) chemistry is NOT
a 5th force — the four forces are gravity/EM/weak/strong; sciences/domains are a separate inquiry.

- **INFO-065 — LOCATED (Session 19, new; real data, multi-force)**: the differential/FLOW
  entropy dipole (dMI/dt ~ ...) does NOT carry the forces' real 2-channel structure, and the
  S18 toy result was an artifact. (a) Real-data flow dipole is FLAT: gravity LIGO H1/L1 R2 0.022
  ~= shuffle-null; weak CMS dimuon R2 0.044 ~= null. (b) Toy-simulator 4-domain/Brusselator
  flow-dipole RETIRED (Greg: untrustworthy; no real-data support) — its "shared opposition" did
  not survive real data. (c) TOOL-BATTERIES (6-7 tools/force, each with a known-correlation
  diagnostic) show the flatness is TOOL-BLINDNESS, not absence: STRONG — only the KNOWN
  femtoscopy C(q) hit (ratio 0.80 vs event-mixed), all entropy/dipole/symbolic/direct tools
  blind; EM — known g2(0)=1.85 HBT bunching fires AND the RAW-count covariance dipole HITS
  (R2 0.49 vs null 0.21) + direct coupling (Pearson 0.142 ~250σ), but entropy->MI->dMI/dt tools
  blind (R2 0.11-0.13 ~= null). MECHANISM: windowed marginal entropies H_a,H_b are ~independent
  of the inter-channel time lag, so coupling/time info never enters the entropy operators — it
  lives in the RAW covariance. Scripts: probe_flow_dipole_{gravity,weak,strong_battery,em_battery}.py.
  Caveats: strong data is dimuon/quarkonium (no dijet CSV); EM "uncorrelated" control also
  bunches (within-script time-shift/shuffle nulls are load-bearing).

- **INFO-066 — LOCATED (Session 19, new; the OTHER dipole solves for TIME; 2 gravity systems +
  tautology null; pulsar declined)**: following Greg ("don't discard the positive time findings;
  time is something else; try the other dipole"), two non-flow dipole forms — RAW cross-covariance
  (over lag) and STATIC ALGEBRAIC H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2 — recover the gravity-time
  coupling where the flow dipole was blind (precedent: static_dipole_test.py — DNA differential R2=0
  but algebraic alive). GRAVITY (LIGO H1/L1): raw dipole SOLVES FOR TIME = inter-detector light-
  travel lag 7.32 ms (|phys| ~6.9), z=14.2, while the entropy-MI dipole on the same data is lag-FLAT
  (blind); algebraic dipole R2 0.93 vs flow's 0.022. TAUTOLOGY-KILLING NULL (circular-shift of H_b —
  preserves H_b smoothness + shared-H_a factor, kills only the instantaneous pairing): EVENT excess
  +0.125 over null, z=2.7, p=0.000, corr(Ha,Hb)+0.73 = genuine common-GW-signal coupling; NOISE
  excess ~0, z=-0.7, corr -0.06 = PURE shared-H_a tautology. GPS (decision-gate PASS — genuine
  2-channel: A = cleaned RINEX pseudorange relativistic residual, B = independent broadcast-element
  geometry driver e*sqrt(a)*sinE, NOT the S18 regression relabeled): raw dipole E18 lag-0 |cc|~0.99
  z=37, E14 z=22, near-circular control fails; algebraic + shift null E18 R2 0.989 excess +0.571
  z=5.7 corr 0.97 vs control excess +0.374 z=1.5 corr 0.17. PULSAR DECLINED — category stretch (the
  chemistry lesson): PSR B1913+16 dP_b/dt + gamma are SCALAR params of a global PINT fit, no
  co-sampled 2nd physical channel, secular parabola not instantaneous A<->B; clean negative, no
  fabrication. READING: the flow dipole was the WRONG TOOL (discards the raw covariance where
  time/coupling live); the positive time findings stand, measured with the right dipole. BRAKES
  (load-bearing): these RECOVER known physics (7 ms light-travel; GR -2/c^2) = positive control that
  the tool TRAVELS, NOT new physics; stats modest where data thin (GPS 1 station/1 day/~10 windows);
  whether the algebraic dipole is a universal law vs a positive-control recovery is NOT settled.
  Scripts: probe_time_dipole_gravity.py, probe_time_dipole_gravity_null.py, probe_time_dipole_gpspulsar.py.
  FOLLOW-UPS: (b) DONE -- the algebraic dipole does NOT cleanly travel to the gauge forces
  (probe_time_dipole_forces.py): EM/strong excess collapse to tautology (z 1.4-2.0, EM
  'uncorrelated' control even shows a LARGER excess -- contaminated), weak borderline-fragile
  (z=2.5, 52 bins, no usable control); the raw-cross-cov-over-lag form DOES fire on EM (z=420
  lag-0 = known HBT bunching) but applies only to time-series channels. So the algebraic dipole's
  genuine excess is confined to the 2 gravity-TIME systems (LIGO event, GPS eccentric) -> reads
  GRAVITY-TIME-SPECIFIC, consistent with the H-C hunch (gravity is the force that touches time),
  with brakes: weak fragile, thin samples, recoveries-of-known-physics. (a) STRENGTHEN GPS
  (multi-station/dual-frequency, probe_time_dipole_gps_strengthen.py) -- DONE: eccentric-Galileo
  algebraic excess +0.464+/-0.278 (z~3) across 12 sat-replicas / 2 stations / 2-3 days (+0.572+/-
  0.134 on clean days = S18 anchor reproduced), raw dipole |cc0| 0.787 z~22 across 13 replicas,
  k/truth +1.14; dual-frequency did NOT rescue the 17-33m circular-sat controls (stay clean
  low-excess controls); honest day-003 E18 degradation kept (real station-day condition, not a
  frequency artifact). So the GPS gravity-time dipole holds as an aggregate, not a one-day fluke. NEXT DIRECTION (Greg, S19): "what is TIME" -- research agents +
  data-shaped probes (clock-rate-law universality across LIGO/GPS/pulsar; arrow-of-time operator;
  why gravity-time-specific = construction vs real). See BACKLOG top section; ontology stays out
  of scope (no-mechanism rule), empirical time signatures are in scope.

## Note (Session 18 update — 2026-06-02) — gravity-couples-to-time (backlog 6c), 3 recoveries

Branch `claude/kickoff-handoff-sequence-4jk6N` (main untouched; no PR). All Operating
Rules in force; no new Rule. Session opened with file-continuity housekeeping: folded the
S12-S17 deltas into this canonical CLAUDE.md and brought the full S17 work branch
(`claude/claude-md-problem-nM8Hm`) onto this branch (all probe scripts + artifacts), then
ran backlog 6c. Greg steered: 6c first, then O3; for 6c, run the GPS positive recovery and
the pulsar route IN PARALLEL.

- **6c question**: does gravity couple to TIME in a recoverable governing law (the H-C
  hunch; INFO-056 showed force-coupling data is construction-confounded, so the clean test
  is clock/time-dilation data). Answer: YES, three independent recoveries.
- **INFO-058 (GPS precise-product NULL)**: the GR clock term -2(r.v)/c^2 is modeled out of
  IGS/CODE precise products -> definitional null (recovered k 0.4% of truth; residual 0.10
  ns vs predicted 24-385 ns across 57 GPS+Galileo sats). Clean null, clear reason, kept as
  data. Motivated the term-retaining route.
- **INFO-059 (GPS POSITIVE)**: from raw RINEX C1 pseudorange (station BRUX) - geometry -
  precise SP3 clock - receiver clock, the relativistic modulation survives in the residual;
  fit vs an INDEPENDENT broadcast-element e*sqrt(a)*sin(E) regressor (cross-source, non-
  circular) recovers -2/c^2 on the eccentric Galileo GREAT sats at k/truth 1.038 (E18) /
  1.019 (E14), z=380 sigma, R^2 0.98-0.99. Dead routes mapped (precise-product + broadcast-
  differencing, term in neither). LOCATED -- clean on 2 sats, one station/day; replicate
  before promotion.
- **INFO-060 (PULSAR, independent)**: raw Arecibo TOAs of PSR B1913+16 (Weisberg & Huang
  2016) + PINT metrology + WLS recovery: orbital decay dP_b/dt = -2.4151e-12 (ratio 1.005 to
  GR; ~0.5% = galactic-accel term; ~17684 sigma detection) and Einstein-delay gamma 4.30737
  ms (0.014% from published). Two gravity-time mechanisms (clock-rate dilation + GW-emission
  orbital decay). Formal errors optimistic (not all JUMPs/terms fit) -> sigma_from_GR an
  artifact, point estimates robust; published values conjecture-to-check. Fixed an exp2 1e12
  units-reporting bug (PINT PBDOT.value already s/s).
- **Capability brief**: updated -- gravity now has a time-dilation recovery (GPS coeff +
  pulsar gamma + pulsar dP_b/dt) alongside the inspiral chirp.
- **O3 (GW170817 BNS chirp mass via pycbc matched-filter, INFO-061)**: DONE. Recovered
  detector-frame M_c 1.200 Msun (network, 0.19% from catalog 1.1977); H1 1.200 / L1 1.195
  independently agree; net SNR 14.8; L1 null 9.7 sigma. Removes the S17 CWT-ridge absolute-
  mass bias (form right at R^2 0.88, mass was 15.7). Env: pycbc 2.11.0 (--ignore-installed
  cryptography) silently shadows scipy with a broken 1.16.3 -> force-reinstall --no-deps
  scipy; use pycbc TimeSeries.gate() not a hand-rolled taper.
- **FLOW = substrate, TIME = one expression (Greg's pivot; INFO-062/063/064)**: tested
  Greg's frame "flow has many expressions, time is one (like QM is one expression of
  physics)". SUBSTRATE (monotonic divergence to a critical point) CONFIRMED + GENERALIZES:
  5 flows across ALL 4 FORCES + chemistry -- gravity (TIME), strong (scale), EM (scale, opp
  sign), weak alpha_2 (scale), Brusselator->Hopf (control-parameter, new domain). Controls
  (weak Z resonance, driven oscillator) correctly PEAK = non-flows -> flow is a real
  restriction. WEAK is both flow (running) and non-flow (Z resonance) -> "non-flow" was an
  OBSERVABLE CHOICE (Greg's wrong-observable point, in data). EXPRESSION: axis distinct
  (time/scale/mass/control-param); FORM distinct where measurable (gravity 3/8 vs Brusselator
  1.0), UNDETERMINED for strong (nonperturbative critical region freezes, INFO-064). Axis
  UNIFICATION still not data-forced. Greg's epistemic rule applied: a non-conforming system
  is one data point / possibly wrong observable, NOT a falsification (e.g. GW170817 miss).
- **FIRST THING NEXT CHAT (Greg): the FLOW DIPOLE EQUATION on these flows, started with a
  HARD NOVELTY SCAN.** REALITY CHECK (frames don't grade themselves): the S18 flow result is
  mostly RE-DESCRIPTION of known physics -- the gauge forces' flow IS the RG / running
  couplings (asymptotic freedom + Wilson RG are Nobel-level), gravity's chirp is GR, the
  cross-axis unification is NOT data-forced, and "flow to a critical point" also caught a
  chemistry bifurcation (general universality). So "new 4-forces law nobody found" is NOT
  established. STEP 0 = literature/novelty scan (RG flow, universality, asymptotic safety,
  EFT, info/flow dipole) BEFORE any novelty claim. STEP 1 = the probe: a flow DIPOLE needs 2
  coupled channels in the paper's form dMI/dt ~ sum c_self*H_i^2 + sum c_cross*H_i*H_j +
  linear (opposition signature). Channels: gravity = H1/L1 (inter-detector MI, INFO-053);
  chemistry Brusselator = native 2 species x,y (START HERE); strong/EM/weak = two observables.
  DECISIVE TEST: do the flows share the SAME quantitative equation form (only coefficients
  differing)? yes -> real structural claim; no -> "flow" is a useful description, not a law.
  Connect to the info-dipole paper + Markets flow dipole. Full plan in BACKLOG top section.
- **Env notes (do not persist across containers)**: pulsar route needed `pip install
  pint-pulsar pdfminer.six`, `pip install --force-reinstall cffi` (broken container
  cryptography binding), and a certifi CA-bundle patch for PINT clock downloads. numpy 2.4
  removed ndarray.ptp() -> use np.ptp(). Raw GPS/pulsar/ligo_bulk downloads gitignored.

## Note (Session 17 update — 2026-06-02) — CLAUDE.md drift fix + construction-vs-nature probe

Branch `claude/claude-md-problem-nM8Hm` (main untouched; no PR). All Operating Rules
in force. Two items: JOB 1 (the CLAUDE.md drift) then backlog #1 (construction-vs-
nature). Full detail in `SESSION_HANDOFF_2026-06-02_S17.md`.

- **JOB 1 — CLAUDE.md drift FIXED.** The repo body was canonical only through S11
  (header stale at "S7"); the true master was S14 with S15/S16 in handoffs; this
  branch was cut from `main` at the S12 kickoff so it lacked all S13-S16 work.
  Fast-forwarded this branch to the S16 work branch (`claude/claude-md-strategy-pwfZr`),
  verified `CLAUDE_master_through_S14.md` (which already carried S13/S14/S15) is a
  STRICT SUPERSET of the S11 body (all 44 ledger entries preserved, no sections
  dropped), then rebuilt this file from it + folded S16 + S17 notes + re-attached the
  START-HERE block + fixed the header. This file is now canonical through S17.
  Historical artifacts kept in-repo. The "keep the header current" rule prevents
  recurrence.

- **INFO-051 -- LOCATED FINDING (Session 17, new; 4 sim generators x 5 seeds + 3
  real LIGO segments)**: the equal-entropy clustering ("everything falls on the
  (1,1,2)/sqrt6 substrate") is BOOKKEEPING, not nature. Probe
  (`probe_construction_vs_nature.py`): scale ONE channel, b -> s*b, which is (a)
  EXACTLY MI-invariant (adaptive histogram bins => MI(a,s*b)=MI(a,b); MI_cv ~1e-16
  across all 7 systems) and (b) a pure UNITS choice (H(s*b)=H(b)+ln s). DATA: (1) MI
  is machine-precision scale-invariant for every system -- the genuine coupling is
  representation-independent; (2) marginal-entropy asymmetry mean|H_a-H_b| is set by
  the units choice, asym_range 2.1-3.8 on 6/7 systems, tracking |H_a-H_b0-ln s|
  (monotone ~ln s for symmetric sims; V-shape for LIGO with min where ln s matches
  the baseline gap); (3) the substrate cos metric (project_234) is NOT scale-
  invariant (cos112_std 0.07-0.27) and is fragile/segment-specific -- independent
  noise segments V1/V2 do NOT reproduce s10's GW150914-noise cos 0.984 (sit at
  0.12/0.38), and that 0.984 is itself a small quadratic residual of a near-constant-
  entropy whitened segment (the null is dominated by the LINEAR H_a,H_b terms).
  INTERPRETATION (deflationary, supported): systems sit on the substrate because we
  build/normalize channels to comparable scales (sims: equal noise amplitude; LIGO:
  whitening to unit variance); a physics-preserving units change dissolves the
  clustering with MI untouched. The only scale-invariant (genuinely physical)
  quantity in the basis is MI. RESOLVES the S16 backlog-#1 open question on the
  construction side; consistent with INFO-036 (attractor = equal-marginal-entropy
  identity) and INFO-038 (asymmetry moves objects off -- because asymmetry is a units
  knob). DISTINCT REGIME kept as data (not predetermined bad -- Greg, S17):
  logistic_chaos (the lone small asym_range, 0.23) ANTI-SYNCHRONIZES (corr -0.995) --
  the two channels become near-perfect mirror images -- and in that LOCKED regime the
  units-knob barely moves the asymmetry (ln s shift +0.076 vs +2.303 expected),
  unlike every independent system. Two things are jointly true and both are data: the
  windowed Vasicek estimator hits its limit on a near-deterministic signal (entropy
  ~ -620), AND strongly-coupled/locked channels genuinely respond differently to
  rescaling. A "what happens at near-perfect coupling" case worth its own look (e.g.
  a different estimator), NOT garbage to drop. CAVEAT: the quadratic-null cos metric
  is estimator-noise-sensitive (INFO-024); do not over-read individual cos values.
  No new Operating Rule.

- **INFO-052 -- LOCATED FINDING (Session 17, new; gravity-FORWARD; 2 real events, 2
  detectors)**: the gravity inspiral chirp LAW is recovered from raw strain by a
  time-frequency RIDGE -- the pivot from PROBE 1's deflationary edge result onto the
  scale-invariant content, the gravity analogue of the S16 WF/SF Piece-1 wins. Probe
  (`probe_gravity_chirp_ridge.py`): own FFT-based Morlet CWT (scipy 1.17 removed cwt)
  -> scalogram; ridge tracked BACKWARD from the merger column with a continuity
  constraint; fit u=f^(-8/3) vs t (Newtonian inspiral => u linear in t, slope ->
  chirp mass). DATA: GW150914 (BBH) CLEAN on BOTH detectors -- H1 R^2 0.995 M_c 38.40
  Msun (f 34->155 Hz, t_c 16.424 s); L1 R^2 0.987 M_c 38.18 Msun (t_c 16.419 s); true
  merger 16.40 s; catalog detector-frame M_c ~31 so ~24% high (expected Newtonian-on-
  late-inspiral bias) and the two detectors agree to <1%. DECISIVELY beats S16
  (whitened-Hilbert R^2 0.001 -> ridge R^2 0.99), confirming backlog #3's diagnosis
  that the method, not the event, was the S16 limiter. GW170817 (BNS): the f^(-8/3)
  LAW FORM fits a second, physically-distinct system (R^2 0.879, merger from metadata
  15.43 s) but absolute M_c is biased (15.67 vs ~1.20) -- the visible H1 arc is a
  narrow low-frequency band (51->76 Hz, short lever arm); honest partial, kept as data
  (form generalizes, absolute mass data/method-limited in a 32 s H1 segment).
  INTERPRETATION: a positive gravity governing-law recovery on the scale-invariant
  content (not the bookkeeping substrate). No new Operating Rule.

- **INFO-053 -- LOCATED FINDING (Session 17, new; "MI next" -- Greg; GW150914 H1/L1)**:
  the inter-detector MI merger signal is PHYSICS-BEARING, not loudness bookkeeping --
  characterizing the one scale-invariant operator left after INFO-051. Probe
  (`probe_mi_merger_axis.py`), 4 tests, same hist-MI estimator (MI is invariant under
  L1's inversion, so only the lag matters): (T1) MI(t) peaks at the merger 0.455 vs
  baseline 0.205 (reproduces INFO-036); (T2, decisive) merger MI peaks at lag
  +7.0 ms = the PHYSICAL H1-L1 light-travel delay, off-merger noise window FLAT -- a
  loudness coincidence is lag-independent, so MI tracks the gravitational GEOMETRY;
  (T3) merger MI is z=15.5 above a 10-lag time-slide null; (T4) phase-scrambling L1
  (keep amplitude spectrum, destroy waveform phase) collapses MI to 0.240 ~= null
  0.225 ~= baseline 0.205, so the ENTIRE MI excess is carried by waveform PHASE/TIME
  structure, not amplitude. INTERPRETATION: MI is genuine common gravitational
  information carrying the waveform's time structure -- validates MI as the physical
  footing (consistent with INFO-051). NOT new physics (LIGO uses inter-detector
  consistency + the 7 ms delay routinely); the contribution is that our MI operator
  captures it and is time-structure-bearing. FRAME CONTACT (ungraded): MI -- the
  surviving physical quantity -- carries the gravitational TIME structure, the
  empirical contact point for the gravity-couples-to-time hunch; stays a frame until a
  probe separates "MI tracks the GR chirp's time structure" from "MI carries
  time-coupling beyond GR" (open thread O1/O2). No new Operating Rule. See the gravity
  footholds scaffold in `SESSION_HANDOFF_2026-06-02_S17.md` (F1-F3 confirmed, C1-C3
  cleared, O1-O3 open).

- **INFO-054 -- METHODOLOGICAL / INCONCLUSIVE (Session 17, new; O1; GW150914)**: does
  the inter-detector MI carry structure BEYOND the recovered chirp -- the only road to
  a NEW gravity law. HONEST SCOPE: a rigorous beyond-GR test needs IMR matched-filter
  templates (pycbc/lalsuite, not in our self-contained stack); this tests "beyond the
  recovered INSPIRAL law INFO-052." Probe (`probe_mi_beyond_chirp.py`): fit + subtract
  the Newtonian chirp model from each detector over the late inspiral, recompute
  inter-detector MI of the residual vs a time-slide null. RESULT: the crude Newtonian
  model removed only 51%/38% of window variance; MI at the physical +7.5 ms lag goes
  FULL 0.624 (z=10.0) -> RESIDUAL 0.325 (z=8.7) -- a ~1.9x cut but a SIGNIFICANT
  residual remains at the correct lag. READING: INCONCLUSIVE for beyond-GR, NOT a
  new-law signal -- the residual is most plausibly un-modeled GR (merger + ringdown +
  higher PN, all omitted by the Newtonian-inspiral-only model). DECISIVE
  methodological output: separating "beyond GR" from "un-modeled GR" REQUIRES IMR
  templates to remove the FULL GR waveform; the method (residual inter-detector MI vs
  time-slide null) is established and the requirement is pinned. No new law. Scaffold:
  O1 -> attempted/inconclusive, needs IMR templates (new backlog item). No new
  Operating Rule.

- **INFO-055 -- LOCATED, NEGATIVE (Session 17, new; O1-real, beyond-GR; GW150914)**:
  the inter-detector MI merger signal is FULLY accounted for by the GR waveform -- no
  detectable structure beyond GR. The rigorous test INFO-054 required: pycbc 2.11.0
  installed, IMRPhenomD (m1=36,m2=29) whitened per-detector, fine time-shift +
  2-quadrature lstsq fit to the whitened GW150914 data, subtract the max-likelihood GR
  waveform, recompute residual inter-detector MI vs time-slide null
  (`probe_mi_beyond_GR_imr.py`). RESULT: template removed 67.7%/53.3% of merger-window
  variance; MI at the physical +7 ms lag FULL 0.536 (z=18.0) -> RESIDUAL 0.226 == null
  0.209; residual peak 0.263 drifts off to -18.5 ms (search edge) at z=2.9 (consistent
  with null). READING: removing the GR waveform collapses the physical-lag MI to
  chance => MI = the GR waveform, NO beyond-GR common structure on this axis for
  GW150914. A real, valuable NEGATIVE (falsification-first): built the rigorous
  new-physics test, answer is "it's GR." CAVEATS: single event; template masses fixed
  (subtraction removed ~55-68% of variance, leftover is uncorrelated detector noise
  that carries no inter-detector MI -- which is why residual MI -> null).
  CORRECTION (Rule D -- Greg caught S17): this does NOT close O2 (the gravity-couples-
  to-time hunch). O2 was never a beyond-GR question -- gravity/time coupling is
  INTRINSIC to GR (the chirp IS time-evolution; time dilation; proper time). INFO-053's
  "MI carries time structure" being GR's time structure is CONSISTENT with the
  flow/time hunch, not evidence against it. INFO-055 closes ONLY "beyond-GR structure
  on the MI axis"; the earlier "also closes O2" was incomplete-not-wrong. O2 is a
  FRAMEWORK/REPRESENTATION question -- can OD express gravity's GR-real time coupling as
  a flow/time dipole term, and does that term distinguish gravity from the gauge forces
  (H-C: only gravity touches time)? -- and remains OPEN. Scaffold: O1 RESOLVED NEGATIVE
  (beyond-GR only); no new gravity LAW found this session; the surviving physical signal
  is fully standard GR. No new Operating Rule.

- **INFO-056 -- FRAME EXPLORATION / DATA FINDING (Session 17, new; O2-reframed/6c; Greg
  "follow this thread")**: flow is NOT unique to gravity. Honesty flag carried: "only
  gravity has time structure" risks construction bookkeeping (gravity is our only
  time-series observable), and the H-C core (gravity dilates clocks) is time-dilation,
  untouched by force-coupling data. Fair test (`probe_flow_operator.py`): one flow
  operator |Spearman(characteristic, axis)| on the three recovered governing relations.
  RESULT: GRAVITY chirp f(t) |rho|=1.000 (axis TIME) = FLOW; STRONG alpha_s(lnQ)
  |rho|=1.000 (axis ENERGY SCALE) = FLOW; WEAK Breit-Wigner |rho|=0.55 (resonance,
  peak 90.5 GeV) = no flow. READING: the SIMPLE hunch "only gravity flows" is REFUTED at
  data level -- the strong force runs exactly as monotonically (RG flow). Surviving
  narrower form: gravity's flow AXIS is TIME, strong's is ENERGY SCALE -- but that is
  construction-confounded (strong also flows in time during the interaction; we measure
  it vs scale) and NOT decided by this data. CAVEATS: 3 forces only (no EM/HBT); the
  time-dilation claim untouched. The frame did NOT grade itself -- the data pushed back.
  Scaffold: O2 PARTIALLY ANSWERED (simple form refuted; time-specific form open +
  construction-confounded; a real test needs clock/time-dilation data, not force
  objects). No new Operating Rule.

- **INFO-057 -- FRAME EXPLORATION / DATA FINDING (Session 17, new; Greg "time correlates
  the 4 forces"; 3-force)**: all three forces organize around a CRITICAL/SINGULAR POINT,
  recovered from raw data (`probe_force_critical_points.py`): gravity t_c=16.42 s (axis
  TIME; chirp f~(t_c-t)^p, p=-0.331 vs GR -0.375, R2=0.965); strong Lambda_QCD=150 MeV
  (axis ENERGY SCALE; 1/alpha_s linear in lnQ, R2=0.982); weak M_Z=90.86 GeV Gamma=4.08
  (axis MASS; Breit-Wigner pole, R2=0.986). READING: the correlating thread the data
  supports is the SINGULAR-POINT structure, NOT time per se -- time is gravity's instance;
  the parameter differs (time/scale/mass). Greg's "time correlates the forces" is REFINED
  to "critical-point structure correlates the forces." DEFLATIONARY (load-bearing):
  unifying time<->scale<->mass is NOT data-forced (construction-confounded); KNOWN physics
  (Landau/Z/merger poles) through the frame, not new physics. Frame aside (ungraded):
  energy-scale, mass, and time are physically interrelated (E-t; mass=energy; RG
  "time"=log-scale). CAVEATS: 3 forces (no EM/HBT). No new Operating Rule.

- **INFO-058 -- LOCATED / METHODOLOGICAL (Session 18, new; backlog 6c, GPS precise-product
  route; 57 sats)**: the GR relativistic clock term dt_rel = -2(r.v)/c^2 = -2(r*rdot)/c^2
  is MODELED OUT of IGS/CODE precise clock products, so recovering it from the cleaned
  product is a definitional NULL. `probe_gravity_time_dilation.py` on CODE SP3 (GPS+Galileo,
  5-min orbit+clock, 2023-001): joint per-sat fit clock=poly3(t)+k*(r*rdot) gives recovered
  k = 0.4% of GR truth -2/c^2; median residual 0.10 ns vs orbit-predicted term 24-385 ns
  (eccentric Galileo GREAT E14/E18 ~275-385 ns). NOT buried in noise (a cubic cannot absorb
  ~2 cycles/day; 0.05 ns << 275 ns). Clean null with a clear reason; kept as data
  (don't-predetermine). Motivated the term-retaining route INFO-059.

- **INFO-059 -- LOCATED, REAL DATA (Session 18, new; backlog 6c POSITIVE; 1 station/1 day)**:
  POSITIVE recovery of the GR time-dilation coefficient -2/c^2 from RAW GPS data via a
  term-RETAINING route (`probe_6c_gps_positive.py`, helper `_route2_obs.py`). Raw RINEX C1
  pseudorange (IGS station BRUX) - geometry - precise SP3 clock (term removed) - receiver
  clock (from near-circular sats) leaves the relativistic modulation in the residual; fit
  against the e*sqrt(a)*sin(E) regressor computed INDEPENDENTLY from broadcast Keplerian
  elements (cross-source, non-circular). RESULT on eccentric Galileo GREAT sats (e~0.162,
  ~275 ns / ~200 m signal): E18 k/truth +1.038 R^2 0.978 corr -0.987 z=380 sigma vs scramble
  null; E14 k/truth +1.019 R^2 0.995 corr -0.997. Two dead routes mapped as data: precise-
  product NULL (INFO-058) and broadcast-differencing NULL (term is in NEITHER precise SP3
  clock nor broadcast polynomial -- they agree to ~3 ns while the term is ~760 ns ptp).
  CAVEATS: clean only on the 2 eccentric Galileo sats (single-freq C1 ionosphere swamps the
  17-33 m signal on circular GPS, diagnosed not absorbed); one station/one day -> LOCATED,
  replicate across stations/days before promotion. The gravity-couples-to-time governing-law
  recovery (clock-rate dilation), positive counterpart to INFO-058's definitional null.

- **INFO-060 -- LOCATED, REAL DATA (Session 18, new; backlog 6c pulsar route)**: two
  gravity-couples-to-time governing relations recovered from RAW Arecibo TOAs of PSR
  B1913+16 (Hulse-Taylor; 9261 TOAs 1981-2012, Weisberg & Huang 2016, Zenodo 54764), GNSS-
  convention-INDEPENDENT (`probe_pulsar_time.py`; PINT does standard clock/barycenter/DM/
  Keplerian reductions with NO dP_b/dt or gamma assumption; relativistic params recovered by
  WLS). (a) Orbital decay: Delta-chi2(PBDOT=0 vs free)=3.13e8 (~17684 sigma detection);
  recovered dP_b/dt = -2.4151e-12 vs GR -2.40263e-12 (ratio 1.005; the ~0.5% is the known
  galactic-acceleration term). (b) Einstein delay gamma = 4.30737e-3 s vs published
  4.30675e-3 (ratio 1.00014, 0.014%) -- the most direct "gravity slows the clock" parameter
  (grav redshift + 2nd-order Doppler). Two mechanisms: gravity altering orbital timing (GW
  emission) + clock rate. CAVEATS (Rule D, honest): PINT does the metrology (not from
  scratch); not all JUMPs/high-order spin/Shapiro/red-noise terms fit, so postfit wRMS ~27 us
  (paper 16.3) and FORMAL ERRORS ARE OPTIMISTIC -- the large sigma_from_GR (91.6) is an
  artifact; the POINT ESTIMATES (ratios 1.005, 1.0001) are the robust result. Published GR
  values treated as conjecture-to-check, not cited as support. Earlier exp2 carried a 1e12
  units-reporting bug (PINT PBDOT.value is already s/s) -- fixed; root cause verified.

- **INFO-061 -- LOCATED, REAL DATA (Session 18, new; backlog O3)**: recovered the GW170817
  binary-neutron-star chirp mass from raw LIGO strain by matched filtering
  (`probe_o3_gw170817_chirpmass.py`). Fetched GWOSC GWTC-1 GW170817 4096s/4096Hz H1+L1
  (data/ligo_bulk/, gitignored; the repo 32 s file was too narrow-band for the BNS lever
  arm); TaylorF2 chirp-mass template bank + Welch-PSD whitening + matched filter, L1 glitch
  (t_merger -1.05 s) gated with pycbc .gate(), peak complex-SNR within +/-0.1 s of merger GPS.
  RESULT: detector-frame M_c = 1.200 Msun (network), 0.19% from catalog 1.1977; H1 1.200
  (SNR 11.1, peak +0.014 s) and L1 1.195 (SNR 9.8, peak -0.008 s) INDEPENDENTLY agree; net
  SNR 14.8 sharply peaked (drops to ~7.5 by +/-0.015 Msun). Null: L1 on 9.8 vs off-source
  9.7 sigma (clean); H1 5.6 sigma (noisier H1-band off-source tail -- the same H1 ugliness
  that defeated the S17 ridge -- but the on-source peak lands at the right M_c AND time).
  This REMOVES the S17 CWT-ridge absolute-mass bias (which got the inspiral LAW FORM
  u=f^-8/3 linear at R^2 0.88 but M_c 15.7): matched filtering recovers M_c to 0.19%.
  CAVEATS (limit SNR, NOT M_c): TaylorF2 inspiral-only, no spin, q=1, f_final 1024 Hz,
  single PSD -> net SNR 14.8 << catalog ~32; inspiral phasing still fixes M_c. Source-frame
  ~1.187 reached after z~0.0099 correction (not applied). Catalog = comparison target only,
  not cited as support. Gravity now has THREE raw-data recoveries (chirp INFO-052, time
  dilation INFO-059/060, BNS chirp mass INFO-061).

- **INFO-062 -- LOCATED (Session 18, new; O2/flow reframe; data in hand)**: Greg's frame
  "FLOW is a substrate, each domain EXPRESSES it along its own axis; TIME is gravity's
  expression (like QM is one expression of physics)" tested as substrate-vs-expression
  (`probe_flow_substrate_expression.py`). SUBSTRATE (flow = a characteristic running
  monotonically and DIVERGING toward a critical point): gravity chirp |rho|=1.000 + strong
  alpha_s |rho|=1.000 both flow; WEAK (Z, a genuine critical point at M_Z) does NOT --
  |rho|=0.054, peaks = resonance. The control BEATS the deflationary "monotonic=trivial"
  reading (a real critical point is not automatically a flow). Critical point is REAL:
  gravity power-law R^2 scan locks to the true t_c (16.4236->16.4234, 0.2 ms); gravity
  exponent q=0.393 vs GR 3/8. EXPRESSION: AXIS clearly distinct (time/scale/mass); FUNCTIONAL
  FORM undetermined here (strong fits power ~ log far from Lambda). Frame SUPPORTED at
  substrate+axis, OPEN at form; axis UNIFICATION not data-forced (construction-confounded).

- **INFO-063 -- LOCATED (Session 18, new; flow battery; widen + control + ALL 4 FORCES)**:
  `probe_flow_battery.py`. WIDEN: the flow substrate GENERALIZES beyond the original two
  forces and beyond time/scale -- 5 flows: gravity GW150914 (time), strong (scale), EM
  alpha_em running (scale, OPPOSITE sign -> Landau pole), weak SU(2) alpha_2 running (scale),
  and chemistry Brusselator->Hopf CRITICAL SLOWING (CONTROL-PARAMETER axis, new domain;
  q=1.000 R^2=1.000, textbook mean-field exponent). ALL 4 FORCES flow under the right
  observable (Greg's "all 4 forces" catch). DEEPEN CONTROL: weak Z resonance (|rho|0.054)
  and a driven oscillator (|rho|0.559) both PEAK -> non-flows; the flow restriction is real.
  KEY (Greg's wrong-observable point, in data): WEAK appears as BOTH a flow (alpha_2 running)
  and a non-flow (Z resonance) -- so "weak=non-flow" was an OBSERVABLE CHOICE, not a property.
  FORM distinct where measurable near-critical: gravity q~3/8 vs Brusselator q=1.0. MISS kept
  as data (Greg's rule, NOT falsification): GW170817 H1 ridge (|rho|0.883) = wrong observable
  (narrow-band H1; BNS SNR in L1; why O3 used matched-filter). Provenance honest: EM alpha_em
  measured running (comparison-only); weak alpha_2 SM-running-from-measured-anchor (labeled).

- **INFO-064 -- LOCATED / UNDETERMINED (Session 18, new; strong flow FORM; agent)**:
  `probe_flow_form_strong.py`. Resolve whether the strong flow's divergence FORM (power vs
  log) is distinguishable by getting alpha_s(Q) near its critical point. ANSWER: NO, and for
  a real reason -- the region where the forms separate (Q->Lambda) is NONPERTURBATIVE/
  inaccessible: quark-hadron duality breaks below ~0.84 GeV, and in schemes where the
  coupling IS measured below 1 GeV it FREEZES to a finite alpha_s(0)~0.76 rather than
  diverging, so the perturbative MSbar Landau-pole "divergence" is a SCHEME ARTIFACT, not a
  measurable feature. Pushing to Q/Lambda~5.6: |dR^2|<0.02 (indistinguishable); combined
  |dR^2|=0.016. Legitimate UNDETERMINED (NOT a falsification; the frame holds at substrate+
  axis). Provenance: FAR 13 PDG points (measured); NEAR set RGE-from-measured-anchor (best
  case, labeled); WALL IR-freezing values scheme-dependent (compared, not cited as support).

## Note (Session 16 update — 2026-06-02) — gravity / 4-force + CLAUDE workflow

Branch `claude/claude-md-strategy-pwfZr` (main untouched; no PR). All Operating
Rules in force. Scope: gravity (S15 thread) + four forces (S14 thread). Greg's
standing calls this session: (a) the MI-in-null coupling discriminator is DISPROVED
— do not build on it; (b) ignore Markets for now; (c) no data discarded, odd outputs
are kept and diagnosed; (d) treat all literature as conjecture. Full detail +
result JSONs in `SESSION_HANDOFF_2026-06-02_S16.md`; queue in
`BACKLOG_tests_and_probes.md` (standing rule: clear backlog before new probes).

What ran (all committed + pushed):

- **Time-blind RECHECK** (`recheck_time_blind.py`) — resolved the INFO-S15a vs
  INFO-046 apparent contradiction on GW150914. SENSE 1 (within-window row shuffle):
  cos = 1.00000000, covariance drift 9e-14 => row-order invariance is a MATHEMATICAL
  IDENTITY of the column-covariance extraction, NOT data time-blindness. SENSE 2
  (28-block null trajectory): the null DIRECTION moves strongly in time (consecutive
  |cos| 0.07-0.99), the merger block is distinct, merger quad-null sits on equal-
  entropy at 0.958 vs noise 0.372. Restatement: "level null is time-blind" must be
  read as "the pooled extraction is row-permutation-invariant by construction"; the
  TIME-RESOLVED null carries strong time structure.

- **H-D trajectory PINNED** (`gravity_HD_trajectory.py`) — stable pooled-noise
  reference + K=40-row window fixes the resolution wall. Clean substrate -> DEPART ->
  return: |cos(window-null, noise-null)| 0.82 pre / 0.28 AT MERGER / 0.89 post.
  DEFLATIONARY (load-bearing): the pre/post "substrate" IS the detector-noise
  reference, so "return" = return-to-NOISE (INFO-046 gate), not ringdown. The
  DEPARTURE at merger is the real signal. H-D ("structure zeroed to substrate") stays
  a FRAME, ungraded. (Superseded the K=16 `gravity_null_trajectory.py`, estimator-
  noise-dominated away from the merger — kept on record.)

- **Gravity chirp Piece-1** (`gravity_chirp_law.py`) — NOT cleanly recovered, and
  recorded as such (no manufactured hit). Five robust extractions on GW150914 (n
  wandered 0.18->0.58->2.0->5.0, R^2 <= 0.46) AND on GW170817 (fetched from GWOSC;
  long BNS inspiral tracked f 30->320 Hz over 6s/18k samples, yet f^-8/3 linearity
  R^2 0.001). BOTH events fail => the limiter is the METHOD (per-sample whitened-
  Hilbert instantaneous frequency too noisy to track the monotone chirp), NOT the
  event. RULE D correction: the earlier "wrong event, use GW170817" diagnosis was
  INCOMPLETE. Clean recovery needs a Q-transform / matched-filter (backlog #3).
  Qualitative chirp present on both events.

- **WF Piece-1** (`s16_weak_zpropagator.py`) — CLEAN. Z Breit-Wigner recovered from
  10227 real CMS dimuon events: M_Z = 90.75 GeV = 99.5% of PDG 91.1876 (chi2/ndf
  3.3-4.2); Gamma_Z over-wide (43-53%) consistent with detector mass-resolution
  broadening (honest instrumental effect). PySR independently recovered a BW-like
  rational lineshape. Same-charge control: no peak. (Lit: SymbolFit used this exact
  data but modeled background; we recovered the resonance.)

- **SF Piece-1** (`s16_strong_running.py`) — CLEAN. QCD running recovered from 13
  real measured alpha_s(Q) world-data points (1.78 GeV-1 TeV), no beta function
  assumed: 1/alpha_s LINEAR in ln(Q), slope +1.31 (POSITIVE => asymptotic freedom
  FORCED by data), b0 8.25, n_f eff ~4.1, Lambda_QCD ~150 MeV, chi2/ndf 0.81. PySR
  recovered the affine 1.24*lnQ+2.57 form. Femtoscopy-R path deferred (backlog #7).

- **PROBE 1** (`probe1_gate_check.py`, `probe1_rate_dynamics_sim.py`) — gravity
  rate-dynamics gate: the merger window has only ~8 independent samples, so lagged
  dynamics can't be fit on real gravity (deferred, backlog #6). Sim half: dMI/dt
  carries lagged memory in chemistry (dR2 0.17) > physics (0.12) > biology (0.05),
  NULL in geology (random-CV dR2 negative; INFO-025 constant-MI). Data level only.

Literature scan (2 agents; "they never stacked"; all gravity-time refs at conjecture
level): Rovelli-Smerlak (temperature as speed of time / Tolman-Ehrenfest);
Castro Ruiz-Brukner (gravity entangles quantum clocks, PNAS); Smith-Ahmadi
(arXiv:2304.01263); de Freitas 2024 (arXiv:2412.12211, Tsallis entropy of real
GW150914 strain, single-detector, no MI); Lemos-Cranmer 2022 (Newton from
ephemerides via PySR); Moynihan 2026 (arXiv:2602.15169, SR rediscovers
gravity=gauge^2 double-copy, theory only). NEGATIVE findings (= our unstacked
lanes): nobody re-derived all four force laws from raw data in one SR framework;
nobody recovered the GW chirp law from real strain by SR; nobody recovered the Z
Breit-Wigner from real dimuon by SR; "only gravity dilates clocks => gravity is the
unique time-coupled force" is unwritten as a formal claim; inter-detector MI as a
physics probe (vs glitch-vetoing) is untouched. CAUTION absorbed: MSSM two-loop
shrinks the unification triangle — our one-loop "no single unification (~1e4)" must
be mapped before being leaned on.

Operator hunch this session (logged, NOT graded — frame): algebra sharpening (Greg)
— only a like term cancels a like term, so if time zeroes at the horizon, the
canceling term must itself be a TIME term inside the gravity equation => gravity must
CONTAIN a time/flow term (H-A/H-B). Coherent; ungraded. Anchor to re-verify: horizon
time-freeze is the EXTERNAL/observer-frame statement.

Data-level analysis "they all fall into that area": everything measured sits ON the
equal-entropy region — 8 toy systems (>=0.99), 4 sim flow axes (0.94-0.99), 4 real
gauge forces (~1.0), LIGO noise (0.98), LIGO merger no-MI view (0.96). The ONLY
departures: LIGO merger in the full 6-op basis (0.23-0.28, MI spike) and gravity's
flow axis (0.61-0.78, loosely pinned). Both departures are GRAVITY-associated.
READING (direction-shift, frame): the universal clustering is the signal — that
region is the universal SUBSTRATE/base (Base-of-Structure; existence pole), the
gravity-associated departures are where structure leaves the base. DEFLATIONARY CRUX
(= backlog #1): the clustering is partly forced by building symmetric equal-marginal-
entropy channels (INFO-038: asymmetry moves objects off). Open question that decides
nature-vs-bookkeeping: is equal-marginal-entropy a forced property of physical
2-channel observables, or our construction choice?

Settled this session (do NOT relitigate): MI-in-null coupling discriminator DISPROVED
(Greg); equal-entropy attractor = equal-marginal-entropy geometric identity (S5+S10),
the OPEN question is construction-vs-nature (backlog #1) not whether the identity
holds; time-blind RESOLVED (method identity, not data); WF + SF Piece-1 DONE. No new
Operating Rule this session. Branch pushed; main untouched; no PR.

## Note (Session 15 — 2026-06-02) — Gravity / Flow-Dipole / Time / Black-Hole exploration

Single-session CLAUDE note, in master format, ready to merge. Branch
`claude/file-upload-session-context-pOsLp`; main untouched; no PR. Opened by
installing the Session 14 master `CLAUDE.md` + v14 handoff + v15 kickoff into
memory, then a free-form exploration. Findings below are stated at DATA level only
(operator's request: no frame-grading this session — fresh eyes to judge). All
Operating Rules in force.

### Operator hunches raised (conjectures, recorded WITHOUT evaluation)
- **H-A** gravity = mixture of "pure physics" + "flow" dipole; affects time/flow.
- **H-B** the flow dipole expresses itself AS time.
- **H-C** EM/strong/weak don't directly affect time, only gravity does ("something
  in the gravity equation cancels the time equation out").
- **H-D** a black hole turning objects into info = zeroing the dipole equations back
  to the bare substrate/dipole level (no-hair analogue: settled BH = mass/charge/
  spin only).
- **H-E** if flow = equal-entropy substrate, that's why nothing (phys/bio/chem/geo)
  exists in a black hole.
- **H-F** (clarified, one consistent model) existence gradient: high cos→substrate
  (~0.9) = exists; distance away (gravity ~0.6) = toward non-existence; substrate =
  existence pole, distance = the gradient.
- **H-G** (newest, unprobed) the SCATTER in per-event gravity coordinates may itself
  carry structure.
Anchored physics (re-verify, treat as conjecture): gravitational time dilation is
measured/replicated (GPS, optical clocks, Pound-Rebka); static EM/strong/weak
potentials don't directly dilate a clock; other forces touch time only via energy
sourcing gravity.

### Probes run + data-level findings (no interpretation)
- **INFO-S15a (P1, `time_flow_probe.py`)** — sim physics+biology, 3 seeds. Level
  null is exactly time-ORDER invariant (cos 1.000000; partly definitional, row
  covariance). With rate ops [dH/dt, dMI/dt] added, null weight is 99.2–99.7% on
  LEVELS, 0.3–0.8% on RATES. Constraint is a static level relation.
- **INFO-S15b (P2, `grav_time_retaining.py`)** — real LIGO, 3 events (GW150914
  cleanly aligned). Order-shuffle cos 1.000000 all events (time-blind on real data).
  GW150914: MI peaks AT merger (16.41 s, kurtosis 18.25); dMI/dt peaks 16.47 s; |MI
  coef in null| 0.001 (self-pole). Reproduces INFO-036/045.
- **INFO-S15c (P3, `flow_dipole_axis.py`)** — FIRST measurement of the flow-dipole
  axis (d(MI)/dt regressed on levels). Opposition signature present fraction 1.0 all
  4 sim domains; flow axis cos→equal-entropy substrate 0.943–0.995; flow R^2 weak
  0.003–0.13. Biology flow axis (0.969→substrate) ≠ its coupling axis (0.588→MI).
  Gravity whole-segment: R^2 0.024, cos→substrate 0.608. Measures by regression what
  INFO-039 identified structurally (opposition ≈ equal-entropy identity).
- **INFO-S15d (P4, `grav_flow_reproduce.py`)** — gravity full/event/noise +
  bootstrap. GW150914 event window R^2 0.438, cos→substrate 0.668 (noise 0.780);
  bootstrap [0.31, 0.95] (loose); off-axis component also in noise. Other 2 events
  alignment failed.
- **INFO-S15e (P5, `grav_flow_crossevent.py`)** — fixed alignment on known merger,
  3 events. Event-window cos→substrate 0.781 / 0.639 / 0.994; GW150914 event ≈ its
  noise (0.781 vs 0.792); cross-event axes scatter (GW150914–GW170104 |cos| 0.106).
  Off-substrate flow axis does NOT reproduce across events; consistent with INFO-038/
  046 detector-state. Per-event scatter unexplained (H-G).

Method-sensitivity audit (GW150914 flow cos→substrate): 0.608 (whole seg, R^2 0.024)
→ 0.668 (event, peak-MI, R^2 0.44) → 0.781 (event, known merger, R^2 0.46; = noise).
Value not yet pinned; cross-event reproduction not established (1 clean event; other
two weak detections, MI_event/noise ≈1.07–1.08).

### Fits vs does-not-fit preexisting data
FITS: level-null time-blindness; flow axis ≈ equal-entropy substrate + opposition =
identity (measures INFO-039); gravity self-pole + MI-peaks-at-merger (INFO-036/045);
off-substrate value present in noise + event-varying (INFO-038/046).
NEW/does-not-fit a prior frame: biology flow axis ≠ coupling axis (new distinction);
gravity event-window off-substrate displacement loosely determined, = noise on clean
event, non-reproducing across events; per-event coordinate scatter unexplained.

### Queued probes (PROBE 1 first)
1. **(FIRST) dMI/dt rate-DYNAMICS** — test lagged/temporal rate structure the
   time-blind level null discards; gravity vs sim within-construction. Gate: is
   event-window sampling enough for a rate-dynamics fit?
2. **Construction-type control** — measure a non-gravity REAL detector-pair object
   (EM/HBT, INFO-048) identically; on-substrate (~0.9) or off (~0.6–0.8)? Needs HBT.
3. **Louder-event reproduction** — GW170814/GW190521 (4096 s hdf5 archives,
   ~134 MB, sliceable); re-run P5 for ≥3 clean events.
4. **Biology JOINT time-shuffle** — same permutation both channels; MI≈0.28*H_a
   survives (instantaneous, H-B unsupported) or dies (temporal, H-B supported)?
5. **Inspiral→merger→ringdown trajectory** — cos-to-attractor(t) shape
   substrate→off→substrate (H-D)? Gate: INFO-046 post-merger is detector-noise at
   125 ms/35–350 Hz; needs finer/lower band.
6. **Scattered-coordinates structure (H-G)** — does per-event spread track SNR/mass/
   noise-state/alignment-lag? Needs ≥ several clean events (depends on #3).
7. **INFO-039 promotion** — dMI/dt as target, ≥3 seeds on off-attractor residual;
   separate opposition-beyond-equal-entropy from the identity.
8. **Gravity vs gauge forces within-construction** — once weak/EM/strong real
   objects on a branch, P3-method flow axis each; compare gravity directly (H-A/H-C).

### Files (branch `claude/file-upload-session-context-pOsLp`)
Scripts: time_flow_probe.py, grav_time_retaining.py, flow_dipole_axis.py,
grav_flow_reproduce.py, grav_flow_crossevent.py. Results: matching *_results.json
(+ time_flow_probe_canary.json). Data: data/ligo/ (H1/L1 GW150914 + GW170104 +
GW151226, 32 s/4096 Hz hdf5). Env: h5py pip-installed for the LIGO probes (add to
requirements.txt if persisting). Companion docs: SESSION_HANDOFF_2026-06-02_FULL.md,
SESSION_HANDOFF_2026-06-02_gravity_flow_time_EXPLORATORY.md.

## Note (Session 13 update — 2026-06-02)

Session 13 opened on the v13 kickoff (CLAUDE.md updated through S12 + the v12
handoff). Greg: do all three queued items, the two cheap ones first, then the
headline. Branch: work on the session-start branch
`claude/file-upload-memory-LKCoB` (main synced; the v12 scripts/result JSONs
were pulled onto it from `claude/file-attachment-hold-DjGSW` so the runs had
their inputs). h5py was missing on this branch and added to requirements.txt.
No PR. All six Operating Rules in force; the header-currency rule (added this
session) is why the title line now reads Session 13.

- **INFO-044 -- LOCATED (Session 13, new; chemistry residual knob test, 3 seeds
  + B sweep across the Hopf bifurcation; s13_chemistry_residual.py)**. The
  chemistry analogue of biology's MI-slope-vs-g (INFO-040). Sweep the Brusselator
  B (baseline 3.0; Hopf B_crit=1+A^2=2). In the OSCILLATORY regime (B>=3) the
  null[0] residual FRACTION rises monotonically (B=3 -> 0.169, B=3.5 -> 0.342,
  B=4 -> 0.400, scatter <=0.02) while the residual DIRECTION stays pinned to the
  INFO-040 baseline relation +0.54 H_a +0.54 H_b +0.32 H_a^2 -0.55 H_b^2 ~ 0
  (|cos| 0.97-0.99, cross-seed 0.999+). So chemistry's coupling-strength readout
  lives in the residual FRACTION of a FIXED non-MI relation, not in the MI axis
  (contrast biology, whose readout is the MI-slope). At the Hopf threshold B=2
  the structure flips qualitatively (residual -> 0.96, eqEntropy collapses,
  direction rotates, |cos|->base 0.64) -- a critical point inspected on its own
  terms (no tent-widening). Below threshold B=1.5 (fixed-point regime) the
  residual is small (0.07) and direction-UNSTABLE cross-seed (0.715), noise-
  limited. Net: chemistry's "partial residual coupling" (INFO-040) is genuinely
  knob-responsive in the oscillatory regime -- refines INFO-040; the per-domain
  heterogeneous-coupling reading strengthens (biology MI-coupled, chemistry
  residual-coupled, both knob-confirmed; physics/geology pure equal-entropy).

- **INFO-045 -- LOCATED (Session 13, new; LIGO no-MI decomposition across the
  full 12 events; s13_ligo_nomi_batch.py)**. Re-ran the S11 GW150914 no-MI
  decomposition (6-op vs 5-op-no-MI attractor cos, event vs noise windows) per
  event across all 12 (11 scored; GW170608 skipped, missing L1). ROBUST /
  GENERALIZES: the EVENT (merger) window leaves the 6-op equal-entropy attractor
  in 11/11 (cos6 < 0.55, mostly < 0.35), and REMOVING MI restores it (event
  cosNoMI > 0.65 in 10/11; GW170809 the lone exception) -- the MI-driven merger
  departure (the strong half of the S11 GW150914 thread) is universal. Does NOT
  generalize: the full noise-OFF/event-ON REVERSAL holds only 6/11, because the
  NOISE-side no-MI position is event-dependent. The 3 events whose 6-op NOISE
  also leaves the attractor (GW170729/170823/190521) are exactly the high
  |H_a-H_b| events -- confirms INFO-038's inverse asymmetry<->noise-cos relation
  at the per-event no-MI level. Resolves the S11 open thread: the event-side
  MI-driven departure generalizes; the noise-side reversal was an event-specific
  detector-noise configuration.

- **INFO-046 -- LOCATED (Session 13, new; peri-event before/after trajectory;
  s13_ligo_trajectory.py; per-event operator matrices cached to data/ligo_M/)**.
  Greg's question: does anything right before/after the merger tell us something?
  Time-resolved zones (pre_far/pre_near/merger/post_near/post_far) of MI,
  |H_a-H_b|, and attractor cos around each merger, 11 events, no pooling. (a) MI:
  the coherent inter-detector MI excess is a SPIKE CONFINED to the merger window
  (+/-0.125s; loud-event merger MI/far 1.18-1.76x), with pre_near/post_near back
  to ~1.0x noise -- NO inspiral precursor, NO ringdown tail. Pre-registered guess
  that the long-inspiral BNS GW170817 would show a sustained pre-merger MI ramp
  was NOT borne out (GW170817 peak only 1.05x far) -- the method keys on peak
  coalescence strain, not the inspiral (caveat: 0.125s windows, 35-350Hz band; a
  finer/lower-band probe could in principle chase the BNS inspiral, this one
  cannot). (b) the no-MI attractor structure IS strongly time-asymmetric pre vs
  post (|delta cos| up to 0.66) BUT the sign is event-specific (6 pre-dominant,
  4 post-dominant, 1 symmetric) and it lives in the off-merger NOISE windows ->
  DEFLATIONARY (load-bearing): non-stationary detector noise floor across the 32s
  segment (single-PSD whitening leaves local drift; the INFO-038 detector-state
  fingerprint), NOT an astrophysical inspiral/ringdown asymmetry. So "before
  differs from after" reports the instrument's noise state on either side of the
  trigger, not source physics.

### Session 13 HEADLINE -- principled force-operator-space (the force<->equation dive)

The S12 decision gate (is there a REAL dataset giving a gauge force a 2-channel
entropy/MI object WITHOUT inventing the coupling?) was answered by a 3-agent
open-data scan: PASS for 3 of 4 forces. Gravity already has LIGO (INFO-036/038,
cached data/ligo_M/). Weak: CMS Open Data dimuon (Z->mu+mu-, record 545
Zmumu_Run2011A, per-event 2-lepton kinematics, ~MB CSV; the Z propagator makes
the di-muon correlation intrinsic). EM: Zenodo 5113016 HBT raw two-channel
photon timetags (Bose bunching intrinsic; same DETECTOR-PAIR construction type
as LIGO). Strong: ALICE/CMS heavy-ion femtoscopy event-level data exists but is
TB-scale + ROOT/VM -- DEFERRED by Greg ("do everything but the big heavy
build"). STRUCTURAL CAVEAT (a finding itself): the four objects are TWO
construction types -- detector-pair time series (gravity + EM) vs particle-pair
event ensembles binned by energy (weak + strong) -- so clean tests are
WITHIN-type. Greg's rule this session: do NOT synthesize across objects (that
isn't real data); each is its own real-data probe.

- **INFO-047 -- LOCATED, REAL DATA (Session 13, new; WEAK force; CMS Z->mu+mu-,
  10227 events; s13_force_dimuon.py + s13_force_dimuon_observables.py)**. First
  real gauge-force operator object. Channels = mu+ / mu- (by charge, physical &
  symmetric, NOT arbitrary leading/subleading); energy axis = dimuon invariant
  mass M, equal-count bins -> a trajectory; same 6-op extract_v1 as
  per_domain_kbk. Finding: the weak object sits on the equal-MARGINAL-entropy
  self-pole (H_a~=H_b, charge-symmetric) and MI does NOT enter the null
  (MI-coupling 0.000) -- like physics/geology (INFO-040), NOT the coupling pole
  (biology). ROBUST across observables: pt, E, signed pz, signed eta, and
  Collins-Soper cos(theta*) ALL give |H_a-H_b| small and MI-in-null 0.000,
  including the parity-carrying observables (A_FB is a small correlation-with-
  boost effect, not a marginal-entropy difference; even cos(theta*) with the two
  muons near-perfectly anti-correlated MI=2.6 keeps MI OUT of the null -- the
  INFO-041 high-variance-active-variable mechanism). Robustness via 5 observables
  agreeing is the real-data analogue of the >=3-seed rule. CONSEQUENCE: the
  caricature "weak ~ chemistry linear-in-H_a" hit (S8, self-grading toy) does NOT
  reproduce on real data.

- **INFO-048 -- LOCATED, REAL DATA (Session 13, new; EM force; HBT, Zenodo
  5113016; s13_force_hbt.py)**. First real EM force object, SAME construction
  type as LIGO (two detectors, windowed count-rate entropy + MI). Two sources:
  split-thermal (detectors ch11/ch15, ASYMMETRIC rates 139k/77k per s) and an
  uncorrelated control (ch15/ch16, symmetric). Findings: (a) MI does NOT enter
  the null for EM either (max 0.031) -- so gravity-noise, weak, AND EM all keep
  MI an ACTIVE variable, never a low-variance null constraint; the ONLY object
  where MI ENTERS the null remains simulated biology (genuine dynamical coupling,
  INFO-040). (b) equal-entropy attractor membership tracks the marginal-entropy
  SYMMETRY of the two channels, not the force: the asymmetric split detector
  (H_a != H_b) sits OFF (eqEnt 0.29-0.52), the symmetric pair sits closer
  (eqEnt 0.57-0.61). This CONFIRMS INFO-036's "attractor = equal-marginal-entropy
  geometry" on a THIRD construction. CAVEAT (RESOLVED by INFO-049, Rule D): the
  "20-100us = slow drift not g2" caveat was INCOMPLETE. Direct g2(tau) shows the
  coherence half-width is ~2us, so 20-100us sits just ABOVE coherence and DID
  capture the bunching (its slow tail), not pure drift. The self-pole / MI-active
  conclusion stands and is strengthened by INFO-049.

- **INFO-049 -- LOCATED, REAL DATA (Session 13, new; EM g2(0) coincidence object;
  s13_force_hbt_g2.py)**. Closes the INFO-048 gap. (a) Direct g2(tau) (binned
  cross-correlation): g2(0)=1.83 (split), 1.92 (uncorr); coherence half-width
  ~2us; decays to g2=1.00 by +-400us -> HBT Bose bunching CONFIRMED real (the EM
  quantum signature, intrinsic). (b) Rebuilt the operator object across bin
  scales spanning the coherence: WELL-SAMPLED (dt=50us, counts ~7-18) reproduces
  INFO-048 -- MI substantial (0.12-0.45, tracking g2-1) and OUT of the null,
  self-pole; SPARSE coherence-scale (dt=1-2us, mean count <1) shows a spurious
  "+1.00*MI ~ 0" MI-dominant null. (c) DEFLATIONARY (load-bearing, no tent-
  widening -- inspected the outlier): the coherence-scale MI-in-null is an
  ESTIMATOR-FLOOR ARTIFACT (INFO-024 on real data) -- at mean count <1 the MI
  estimate collapses to a near-zero near-constant floor (MI std 0.0004 vs H_a std
  0.114, ~300x smaller), so MI trivially becomes the lowest-variance null. It is
  NOT biology-like coupling (biology's null is MI~=0.28*H_a, MI tied to H; here
  it is MI~=const, and only in the sparse regime). CONCLUSION: the genuine HBT
  bunching does NOT enter the null as a coupling; properly sampled, EM is self-
  pole with MI active. Reinforces INFO-047/048 and confirms INFO-024's procedure/
  sampling-dependent MI floor on real EM data. Biology remains the ONLY genuine
  MI-in-null coupling across all objects, simulated or real.

- **Session 13 force-operator-space FRAME (held as frame, not claim; no
  synthesis per Greg)**: across two real gauge-force builds (weak, EM) plus
  gravity, the forces look like the SELF-POLE / bookkeeping domains
  (physics/geology) -- MI stays out of the null, equal-entropy membership is pure
  channel symmetry. The caricature-era EM<->physics and weak<->chemistry hits do
  NOT reproduce on real data. "MI-in-the-null = law-like coupling" appears so far
  ONLY in simulated biology, in NO real force object yet measured (the EM
  g2(0)-coincidence object, INFO-049, confirmed this: genuine HBT bunching stays
  out of the null; the sparse-bin MI-in-null was an INFO-024 estimator artifact).
  Open within-type extension: the strong force (heavy, deferred) -- CLOSED in
  Session 14 (INFO-050): strong is also self-pole; 4/4 real gauge forces now
  measured.

## Note (Session 14 update — 2026-06-02)

Session 14 opened on the v14 kickoff (CLAUDE.md updated through S13/INFO-049).
Greg's pick: "let's do the big one next" -- the STRONG force real-data operator
object, the last within-type force and the 4-for-4 test of the self-pole frame.
Branch: work on the session-start branch `claude/upload-to-memory-1g6eY` (the
three master files -- CLAUDE.md S13, v13 handoff, v14 kickoff -- were uploaded to
memory at session start; the master context was then pulled into context). main
not synced this session (the S13 force scripts live on
`claude/file-upload-memory-LKCoB`, not main; this branch carries the S14 work).
No PR. All Operating Rules in force incl. header-currency + Greg's no-synthesis
directive. Header bumped to Session 14.

- **Decision gate (Result Discipline; mapped before committing TB/compute)**.
  The kickoff's cheap first step ("test uproot on ONE file before any TB
  download") drove the whole gate. Findings:
  - **Network**: this session's egress proxy CANNOT reach `eospublic.cern.ch`
    (the EOS host for ALL CMS/ATLAS open-data files) -- HTTPS 503 (proxy fails to
    verify CERN's TLS cert chain, "self signed certificate in chain"), xrootd:1094
    times out (port blocked). This DIFFERS from S13, where eospublic worked --
    an environment-level network-policy difference. **Workaround found (reusable):**
    `https://opendata.cern.ch/eos/opendata/<path>` streams the same files (200,
    supports HTTP range requests), so uproot partial remote reads work through it.
  - **CMS HI RECO REJECTED** (records 14010 HICorePhysics / 14011 / 14014; 19.3 TB,
    ~2.5-3.9 GB/file). uproot opens the file, reads the Events tree (2380 branches),
    sees the HI track collections (hiSelectedTracks, hiGlobalPrimTracks) with
    momentum_.fCoordinates.fX/fY/fZ leaves -- BUT returns 0-length for EVERY track
    member (momentum, chi2_, ndof_, charge_) while `.present`=True: a systematic
    failure to reconstruct the vector<reco::Track> member-wise counts (top branch =
    AsGroup with UnknownInterpretation EDProduct). CMS RECO tracks need CMSSW (the
    heavy VM path). Not empty events -- confirmed via .present + mid-file sampling.
  - **ATLAS DAOD_HION14 PASSED** (record 80036 child of 80035, 2015 Pb-Pb "Open
    Data for Research", 1913 files / 4.4 TB, CC0, /eos/opendata/atlas/rucio/
    data15_hi/). ATLAS's own usage note: "can be used ... using uproot". Confirmed:
    uproot reads CollectionTree; InDetTrackParticlesAuxDyn.{phi,theta,qOverP,...}
    are flat readable arrays; a real central PbPb event read in 0.3s gave 3644
    tracks with realistic pt (0.5-2.8 GeV) and eta (+-2.3). NO VM. pt=sin(theta)/
    |qOverP|, eta=-ln tan(theta/2), p=1/|qOverP|.

- **INFO-050 -- LOCATED, REAL DATA (Session 14, new; STRONG force; ATLAS
  DAOD_HION14 Pb-Pb, 1500 events / 5 files; s14_force_strong.py +
  s14_strong_lowq_becheck.py)**. The 4th and last within-type gauge-force object,
  built the SAME way as WEAK (s13_force_dimuon): particle-pair event ensemble
  binned by an energy axis. Construction: CHANNELS = the two identical same-charge
  hadrons of a pair, assigned A/B AT RANDOM (symmetric labeling -- identical bosons
  have no distinguishing charge, the strong analogue of weak's mu+/mu- symmetry),
  observable = hadron pT (eta as robustness); ENERGY AXIS = pair relative momentum
  q_inv (the femtoscopy scale, Bose-Einstein peak at q->0), equal-count bins; per
  q-bin the 6-op [H_a,H_b,H_a^2,H_b^2,H_a*H_b,MI] -> extract_v1 null. The
  inter-hadron BE correlation of identical pions is the intrinsic strong signal,
  not invented. FINDING: strong sits on the equal-entropy SELF-POLE -- MI does NOT
  enter the null (MI-coupling = 0.000) and equal-entropy ~ 1.000, ROBUST across
  charge (++ / --) x observable (pT / eta) x 3 random-A/B seeds (the real-data
  analogue of the >=3-seed rule). Two no-tent-widening robustness checks
  (s14_strong_lowq_becheck): (1) the BE correlation is CONFIRMED PRESENT --
  C(q)=same-event/mixed-event for same-charge pairs rises at low q, C(q<0.1)~1.10
  (lowest bins 1.19-1.23) -- so MI-not-in-null is not the absence of a signal
  (INFO-049 lesson); (2) restricting to the low-q femtoscopy window q<0.4 GeV
  (down to q~0.075, where BE peaks) the self-pole SURVIVES -- MI-coupling still
  0.000 across all configs/seeds. The genuine BE coupling creates MI but it stays
  an ACTIVE high-variance variable, never a low-variance null constraint -- exactly
  like EM/HBT (same Bose-statistics physics; INFO-048/049) and consistent with
  INFO-041 (generic coupling makes MI without it entering the null). CAVEATS
  (honest, not tent-widening): track cap MAX_TRK=150/event (central events have
  thousands -- a compute bound; no Coulomb/purity correction, so the BE
  enhancement is modest); 1500 events of 4.4 TB available (small subset, but the
  null result is stable across files/seeds/observables/q-windows); one construction
  (femtoscopy pair-ensemble).

- **Session 14 force-frame (held as frame, no synthesis per Greg)**: with the
  strong force added, **4/4 real gauge forces -- gravity (LIGO, INFO-036/038),
  weak (CMS Z->mumu, INFO-047), EM (HBT+g2, INFO-048/049), strong (ATLAS
  femtoscopy, INFO-050)** -- all sit on the equal-entropy self-pole; MI is active
  but NEVER a null constraint for any real force. The gauge forces look like the
  bookkeeping domains (physics/geology), NOT the coupling pole. "MI-in-the-null =
  law-like coupling" remains confined to simulated biology (knob-confirmed,
  INFO-040) and -- via its predictive algebraic dipole -- markets. The clean 4/4
  statement the v14 kickoff named as the goal is achieved. Strong did NOT produce
  the "most interesting outcome" (MI entering the null); it confirmed the
  self-pole. NO synthesis across construction types -- strong was compared
  within-type to weak (both particle-pair event ensembles binned by an energy
  axis); gravity/EM are the other (detector-pair time-series) type.

- **Environment**: added uproot/awkward/aiohttp/requests (+ h5py) to
  requirements.txt for reproducibility (the SessionStart hook installs the numeric
  stack + PySR/Julia; these are the new heavy-ion deps). xrootd client + the
  opendata.cern.ch HTTP-streaming bypass are the access path; raw ATLAS files in
  data/strong/ are gitignored (re-fetchable). Note for next session: if eospublic
  is needed directly, this session's network policy blocks it -- use the
  opendata.cern.ch/eos/opendata/<path> streaming bypass, or a session whose policy
  trusts the CERN CA.

- **Open / next**: (a) **NEXT SESSION (Greg S14 decision): the "how are the 4
  forces derived" 3-piece program -- do ALL THREE, EASIEST FIRST.** Order: (1) weak
  Z-propagator from Zmumu.csv, (2) gravity chirp from cached LIGO inspiral, (3)
  unification footprint (extend Track B). Piece 2 (PDG coupling relation) folds
  into (3). RUN THE MARKETS ANALOGUE IN LOCKSTEP (the method transfers -- see the
  queued-thread subsection in the Markets section). Full plan in
  NEW_SESSION_KICKOFF_v15.md. (b) the four real force objects are all built --
  the data-collection phase is complete; remaining force interpretation is WITHIN
  type only (Greg's no-synthesis rule). (c) Markets dipole JSON pull still dropped
  per Greg; keep the Markets section in lockstep. (d) Strong follow-ups if wanted:
  more files/centrality binning, Coulomb-corrected C(q), opposite-charge control
  -- none change the self-pole null (the load-bearing result).

## Note (Session 12 update — 2026-06-02)

Session 12 continued the v12 kickoff. Branch given at session start
(`claude/file-attachment-hold-DjGSW`); main kept synced; the kickoff's stale
`gravity-substrate-config-51cfp` reference disregarded per Greg. Greg enabled
out-of-order/efficiency. Three of the v12 first-three actions delivered; the
Markets pull was dropped by Greg's call.

- **Track B -- new-physics inverse problem (built, INFO-037 extended)**:
  `s12_track_b_inverse.py` -> `s12_track_b_inverse_results.json`. Reproduces
  the INFO-037 one-loop triangle exactly (crossings 1.03e13 / 2.43e14 /
  9.71e16 GeV, spread 9419x). New: (b) TWO-LOOP running alone shrinks the
  triangle to 2678x (factor 3.5) with NO new physics -- part of the apparent
  gap is a one-loop artifact, ~2700x remains; (inversion) the required
  Delta-b FOOTPRINT surface over (mu_NP, M_GUT) is exactly determined for
  the differences only -- 3 unknown shifts, 2 difference constraints, free
  spectrum scale, so FOOTPRINT recoverable, IDENTITY never (mapped MSSM as
  one uncited point on the surface, sitting near the 1 TeV / 2e16 GeV point);
  gravity needs b_G ~ 2.9e33 (power-law->log form change), confirming it is
  outside the gauge family. Alternatives (a) no-closure [deflationary],
  (b) two-loop, (c) extrapolation-is-conjecture mapped FIRST per Result
  Discipline. The leading deflationary read (nothing forces a single point)
  is unrefuted.

- **Four per-domain equations consolidated**: `s12_consolidate_per_domain.py`
  -> `od_per_domain_equations.json`, built from in-repo result JSONs
  (per_domain_kbk seeds 11/22 for null directions INFO-023; pysr_symbolic_
  per_domain for functional families INFO-025), confirmed by Greg's 6 chat
  screenshots. All equations are listed in the Markets section above.

- **INFO-039 -- MAPPED (deflationary reading dominant)**: info-dipole paper
  (davisai.ai/dipole) connected to the extraction machinery. Its flow form
  `dMI/dt ~ sum c_self*H_i^2 + sum c_cross*H_i*H_j + linear` (opposition
  signature: c_self, c_cross opposing sign) IS the operator family the
  windowed-null extraction operates on; each per-domain null[0] is a
  conserved (c_self, c_cross) vector of it. The opposition signature appears
  in our extracted physics + chemistry nulls -- BUT where it appears in the
  quadratic subspace it largely COINCIDES with the equal-marginal-entropy
  attractor identity -(H_a-H_b)^2 ~ 0 (physics null[0]_234 cos=1.000 to
  (-1,-1,+2)/sqrt6; chemistry ~0.88). Since INFO-036 (real LIGO) already
  showed that attractor is a geometric statistics artifact, INFO-039 is a
  structural IDENTIFICATION (paper = extraction operator family), NOT
  independent coupling evidence. Genuine domain content stays in the
  deviations + functional families (INFO-025). Full detail in the Markets
  section. Promotion needs >=3 seeds on the off-attractor residual + a probe
  separating opposition-beyond-equal-entropy from the identity.

- **Track A -- full 12-event LIGO null, COMPLETE** (`s11_ligo_batch.py`,
  hardened to incremental-save + resume-safe this session; the first run had
  stopped on GW170817 after 7 events and -- saving only at the end -- lost the
  JSON, so it now persists after every event + gc's; GW170817 completed fine
  on the resume-safe re-run, so that stop was transient). 11 events scored
  (GW170608 skipped: no 4096s L1 file), each run SEPARATELY, N_null=100
  off-source per event, no pooling -> `s11_ligo_batch_results.json`:
  | event | \|H_a-H_b\| | noise cos | peak-MI | p | det |
  |-------|-----------|-----------|---------|---|-----|
  | GW150914 | 0.14 | 0.997 | 0.658 | 0.000 | YES |
  | GW151012 | 1.98 | 0.568 | 0.325 | 0.980 | . |
  | GW151226 | 2.38 | 0.795 | 0.333 | 1.000 | . |
  | GW170104 | 0.14 | 0.924 | 0.435 | 0.000 | YES |
  | GW170729 | 2.06 | 0.200 | 0.380 | 0.000 | YES |
  | GW170809 | 1.08 | 0.849 | 0.407 | 0.000 | YES |
  | GW170814 | 0.38 | 0.949 | 0.364 | 0.094 | ~ |
  | GW170817 (BNS) | 1.41 | 0.564 | 0.335 | 0.760 | . |
  | GW170818 | 0.44 | 0.948 | 0.351 | 0.320 | . |
  | GW170823 | 2.22 | 0.136 | 0.380 | 0.030 | YES |
  | GW190521 | 1.33 | 0.039 | 0.376 | 0.050 | ~ |
  Two data-level readings, both CONFIRMED at batch scale (promote INFO-038
  from isolated/3-event to MAPPED/11-event-with-null): (1) the off-source
  NULL gives real p-values -- 5/11 clear p<0.05 (+2 marginal); misses are the
  two quiet O1 events, the BNS (long low-freq inspiral, different morphology),
  and GW170818. Detection tracks event loudness/morphology, NOT entropy
  asymmetry (GW170729/170823 detect at the HIGHEST asym). (2) INFO-038's
  inverse |H_a-H_b| <-> noise-cos relation holds across the batch:
  corr(asym, noise-cos) = -0.667. (3) The entropy-asymmetry axis and the MI
  axis are ORTHOGONAL (confirms the S11 first-run decomposition): the
  attractor is equal-entropy bookkeeping; detection rides the separate MI
  axis. Open INFO-038 no-MI-basis reversal thread: not yet re-checked across
  the full 12.

- **INFO-040 -- per-domain coupling probe (Greg's "find how the dipoles are
  coupled")**: 5-seed null decomposition + biology dynamical-knob test.
  Headline: biology's dipole is GENUINELY COUPLED (null = MI~=0.28*H_a,
  0.906+/-0.007 MI-fraction; g=0 knob kills it, g>0 restores it, slope tracks
  coupling strength, shared-noise artifact ruled out); chemistry has a stable
  total-entropy-vs-asymmetric-quadratic residual; physics/geology pure
  equal-entropy. Refines INFO-039. Full entry in the Markets dipole subsection
  above. Scripts s12_coupling_decomposition.py + s12_biology_coupling.py.

- **INFO-041 -- pairwise Level-2 cross-science coupling** (Markets dipole
  subsection): generic coupling creates MI but it does NOT enter the null
  (coupled MI-frac 0.003-0.147) unlike biology's native 0.91 -> the dipole's
  MI-participation marks STRUCTURED (entropy-locked) coupling, not magnitude;
  coupled-null directions are pair-specific (mean|cos| 0.46) -> NO universal
  Level-2 dipole. s12_pairwise_level2.py.

- **INFO-042 -- SM parameter-regularity hunt (four-force item, real PDG data)**:
  s12_sm_regularity.py / s12_sm_regularity_results.json. The honest real-data
  face of "are the forces/parameters structured." HITS: charged-lepton Koide
  Q=0.666661 (5 digits); Gatto-Sartori-Tonin sqrt(m_d/m_s)=0.224 vs Cabibbo
  sine 0.226 (ratio 0.991); quark-lepton complementarity th12_CKM+th12_PMNS
  =46.4deg ~ 45; CKM Wolfenstein lambda^n hierarchy (ratios O(1)). MISSES
  (cataloged per Result Discipline): quark Koide fails (up 0.85, down 0.73);
  mass spectra only roughly geometric (log-linear R^2 0.97-0.995, not exact).
  Reading: real low-dimensional structure exists (the SM mass/mixing sector is
  NOT 26 independent randoms) but the cleanest relation has no accepted
  derivation and the quark analogues fail -> each is a CONJECTURE / one data
  point, no single generating rule, none citable as support until derived.
  - **Answers Greg's force<->equation question (b)**: NO direct connection. SM
    regularities are mass/angle relations among static parameters; the per-
    domain equations are MI-vs-entropy relations of 2-channel dynamics --
    different KIND of object. The one apparent bridge (Session-8 four-force
    caricatures: EM's MI-vs-H = physics family (H_b-H_a)^2+c, weak ~ chemistry
    linear, both robust-ish) was from toy force-laws WE wrote (S10 retired as
    self-grading), so it cannot be cited. EM<->physics is a real but
    caricature-contaminated hit; on REAL data there is no commensurable bridge.
    Two contradictory mappings exist (functional-family: EM<->physics, vs
    coupling-type INFO-040: gravity<->equal-entropy domains) -> pattern-matching
    without constraint until a principled real-data force-operator-space is
    built.

- **INFO-043 -- cross-domain balance (Greg's "opposite domain that balances a
  non-coupled one")**: domains do NOT anti-balance; they split by axis -- 3 of
  4 (physics/chemistry/geology) on the equal-entropy SELF pole, only biology on
  the MI CROSS pole. physics vs biology cos=0.000 (orthogonal, pure self vs
  pure cross), complementary not oppositional. Full entry in Markets subsection.

- **Next direction queued (Greg wants to dive in): principled force-operator-
  space** so the force<->equation question becomes real-data-testable instead
  of caricature-bound. Gravity already has a real operator object (LIGO); the
  gap is the gauge forces. Decision gate first: is there a real dataset giving
  a force a 2-channel entropy object without inventing the coupling? See the
  "Next direction queued" block in the Markets dipole subsection.

- All six Operating Rules in force; no new Rule. Branch
  `claude/file-attachment-hold-DjGSW`, main synced, pushed. No PR.

## Note (Session 11 update — 2026-06-02)

Session 11 opened on the Session 10 four-force real-data results. Greg
directed: do Track A (LIGO generalization) and Track B (new-physics
inverse problem + SM-parameter-regularity hunt) in parallel; run LIGO
events SEPARATELY with no merge/average; consolidate OD inputs; update
docs; prepare for a fresh session. Branch: work on
`claude/gravity-substrate-config-51cfp`, **main fast-forwarded to it** so
the SessionStart hook + all data run every session. Harness-designated
`claude/awaiting-files-TgxVq` not used (continuity precedent); Greg's
branch-specifying file had not arrived by session end.

- **Four-force framing answers (no compute, recorded for Track B)**: set 2
  (PDG) CONSUMES the Standard Model (beta functions + gauge group are
  inputs) so it cannot derive the forces or their origins; set 1 (LIGO) is
  a method/measurement result. Neither reaches "origins" -- a why/mechanism
  question outside OD mode, and no dataset contains the origin. The honest
  OD-shaped target is the INVERSE PROBLEM: extract the Delta-b_i +
  onset-scale mu_NP that would close the triangle (mechanism-agnostic,
  falsifiable), AFTER mapping alternatives (a) nothing forces single
  unification [leading deflationary read], (b) two-loop + thresholds may
  shrink the triangle (Session 10 used one-loop), (c) the extrapolation
  itself is conjecture. We can recover new physics's required FOOTPRINT,
  never its IDENTITY (3 couplings don't invert to a unique spectrum).
  Gravity is its own extraction (power-law would need to become log to
  join the gauge family). This is Track B, framed not built.

- **INFO-038 -- ISOLATED FINDING (Session 11, new; 3 events, NO null yet,
  NOT averaged)**: per-event LIGO readout (s11_ligo_perevent.py) on
  GW150914, GW170104, GW151226 run separately. Per-event windowed entropy
  asymmetry |H_a-H_b| varies materially (0.62 / 0.74 / 1.61) and INVERSELY
  tracks how strongly noise-only windows sit on the (-1,-1,+2) equal-
  entropy attractor (GW150914 asym 0.62 -> cos 0.980; GW151226 asym 1.61 ->
  cos 0.816). Internally consistent with INFO-036: the attractor IS the
  equal-marginal-entropy identity H_a~=H_b, so unequal per-channel entropy
  sits further off it even in pure detector noise. The entropy reading
  EXPLAINS the cos reading. The asymmetry is a per-event detector-state
  signature (epoch-specific H1-vs-L1 noise floor/PSD surviving whitening),
  NOT astrophysics. MI-peak-at-merger detection is loudness-dependent
  (lands at merger for GW150914 + GW170104; misses quiet long-inspiral
  GW151226). All event/noise MI ratios modest (1.06-1.19x) and MEANINGLESS
  without the null distribution. Full 12-event batch + per-event off-source
  null built (s11_ligo_batch.py), not yet run. Do not pool: the per-event
  spread is the signal.
  - **First-run decomposition (s11_first_run_entropy.py; GW150914, 1
    event)**: re-read the FIRST real-data run in this frame and asked what
    breaks the attractor at the merger. Answer: MI, NOT the marginal
    entropies. Event-window asymmetry |H_a-H_b| barely moves (-0.016) while
    MI spikes (per-window ~0.24 baseline -> 0.66 at the merger). Removing
    MI from the basis RESTORES the event attractor (event cos 0.231 ->
    0.959 in the 5-op basis; +0.728). So two ORTHOGONAL axes: (1) the
    entropy-asymmetry axis = the across-event noise-floor fingerprint
    (INFO-038 main), (2) the MI axis = the within-event merger signature,
    independent of marginal entropy. Strengthens the deflationary reading:
    the (-1,-1,+2) attractor is equal-marginal-entropy bookkeeping while
    the GW detection rides the orthogonal MI axis -- they do not interfere.
    Open thread (1 event, not over-read): in the no-MI basis NOISE sits OFF
    the attractor (0.301) and EVENT sits ON it (0.959) -- a reversal to
    check across the 12-event batch.

- **OD consolidation (Greg: update OD with latest dipole + 4-force JSONs)**:
  brought Session 6/7/8 four-force + per-domain result JSONs and OD stores
  (store/four_force_caricature, store/simulator_4domain) onto continuity
  (additive) and synced main. Four-force JSONs verified identical across
  O6ahb/iZvY4. Decisions: **dipole** -> pull from the Markets repo if the
  info lives there + list the flow dipole equation separately (Greg; ACTION
  next session via list_repos/add_repo on DavisAI1974/Markets); **medical
  OD stores** (cardiac/cerebro) -> stay on their own branch, NOT main.

- All Operating Rules from Sessions 4-7 in force. No new Rule this session.
  Branch state: work on `claude/gravity-substrate-config-51cfp`, main
  synced, pushed. No PR.

## Note (Session 10 update — 2026-06-02, FIRST REAL DATA)

Session 10 started from `claude/gravity-substrate-config-51cfp` (per the
v10 kickoff; the SessionStart hook + Session 9 work live there, main
untouched). Arc: two method-hardening probes on the toy systems, then
Greg called the pivot to REAL DATA, and two four-force real-data sets
ran. All six Operating Rules held; no new Rule.

- **Greg's pivot decision**: when it surfaced that the gravity/weak force
  laws in `gravity_glance.py` / `four_force_probe.py` are OUR OWN toy
  caricatures (not OD discoveries, not literature force laws -- gravity
  is a softened E_total*dx/(dx^2+eps) term, "weak" is a Gaussian
  exp(-M*dx^2) not a real Yukawa exp(-Mr)/r), Greg cut the caricature
  work: "no point fine-tuning fake data ... if replacing would just be
  more work on fake data, skip that too." So items 2 (strong exp seed-
  rate) and 3 (coupling-strength dial) and any caricature replacement
  were SKIPPED. Pivot straight to real data, four-force-related only.
  Operating-rule consequence reinforced: a frame must never grade itself
  -- caricature results describe only the equations we wrote.

- **INFO-034 -- METHODOLOGICAL (Session 10; item 4; 3 seeds)**: the
  INFO-033 MI-dominant flip is ESTIMATOR-ROBUST. Swapping the histogram
  MI for a Kraskov-Stoegbauer-Grassberger kNN estimator (estimator 1) on
  the same operator matrix reproduces follow-up A exactly on histogram
  (gravity 0.8/0.9 raw 0.906/std 0.644; 0.8/1.0 0.990/0.665) and the KSG
  estimator AGREES on the standardized structural core near threshold
  (gravity 0.8/0.9 std 0.644; EM 1.0/1.3 std 0.435; EM 1.0/1.5 0.597),
  on raw values, on strong-never-flips, and on the threshold ordering.
  Sharpens the deflationary reading: the structural core is a modest
  ~0.6-0.7 band NEAR the flip threshold; at extreme asymmetry (gravity
  0.8/1.2) both estimators fall below 0.5 while raw rides ~0.99 on a
  collapsing MI variance (procedure inflation). The flip is not a
  histogram artifact. (Script s10_third_estimator.py.)

- **INFO-035 -- LOCATED (Session 10; item 1; 3 seeds, seed-stability
  0.95-1.00)**: substrate-vs-expression invariance across the Session 8
  mapping-campaign knob sweep is MIXED -- partial support for the
  Base-of-Structure spine, with two clear exceptions. Biology (beta
  0.3-0.8): substrate |cos| 0.978-0.986, stable rank 1, while expression
  mutates exp->linear -> clean support. Geology (drift 0.02-0.08):
  |cos| 0.981-1.000, stable rank 3 (expression also robust; weaker
  test). Physics (K 0.05-0.5): invariant baseline->high (0.995) but
  BREAKS at weak coupling K=0.05 (rank 1->4, |cos| 0.69) -- regime-
  bounded. Chemistry (B 2-4): substrate NOT invariant, |cos| 0.045
  between B=3 and B=4, rank swings 4->1->5 -- prediction FAILS; B=2 sits
  at the Brusselator Hopf threshold (B_crit=1+A^2=2), flagged for
  inspection, not absorbed. Net: "substrate = simple invariant base"
  holds in 2/4 domains, regime-bounded in 1, fails in 1. Spine partially
  supported, not confirmed. (Script s10_substrate_invariance.py.)

- **INFO-036 -- LOCATED, REAL DATA (Session 10; item 5 set 1; one event,
  one 32s segment)**: the windowed-H/MI/operator stack, UNCHANGED from
  the toy systems, applied to real LIGO GW150914 H1/L1 strain (GWOSC
  public, 4096Hz, bandpass 35-350Hz + ASD whiten, 2s edge crop, 125ms
  windows). Two findings. (a) METHOD WORKS: inter-detector windowed MI
  PEAKS EXACTLY at the merger (t=16.41s vs 16.4s; MI 0.530 vs noise
  baseline 0.247, 2.1x). (b) PRE-REGISTERED PREDICTION OVERTURNED, frame
  refined: I predicted the (-1,-1,+2)/sqrt6 channel-substrate would
  appear IN the event; instead noise-only windows sit ON it (|cos|=0.984)
  and event windows LEAVE it (|cos|=0.242). The attractor IS the
  equal-marginal-entropy identity H_a~=H_b, not coupling: whitened
  detector noise has equal per-channel entropy -> lands on it trivially;
  the chirp changes one detector's entropy -> breaks it, while MI (a
  separate operator) spikes on the common signal. Real data confirms the
  Session 5 reading -- the attractor is an equal-statistics geometric
  fact, not a substrate signature. Caveat: noise-on-attractor is partly
  a whitening consequence (which is the point); needs more events.
  (Script s10_ligo_extract.py; data/ligo/.)

- **INFO-037 -- LOCATED, REAL DATA (Session 10; item 5 set 2; special
  build)**: four-force unification from MEASURED couplings, mapped onto
  the surviving frame (substrate = shared linear-in-ln(Q) running form;
  expression = per-force slope b_i). Anchored on solid PDG M_Z couplings
  (alpha_em^-1=127.951, sin^2thetaW=0.23122, alpha_s=0.1180 ->
  alpha_1,2,3^-1(M_Z) = 59.02/29.59/8.48). (a) The shared running FORM is
  CONFIRMED in real data: SM one-loop alpha_s(Q) matches measured
  determinations within <1sigma from 31 GeV to 1 TeV (low-Q pulls are the
  known one-loop limitation). (b) NO single SM unification: pairwise
  crossings at 1.0e13, 2.4e14, 9.7e16 GeV -- a triangle spanning ~9400x.
  (c) MSSM near-point ~2.1e16 GeV (spread 1.1x) but rests on unobserved
  SUSY -> tagged conjecture, not cited as support. (d) Gravity:
  alpha_G(E)=(E/M_Pl)^2 is power-law, not linear-in-ln(Q) -- different
  substrate form, outside the gauge family. Verdict: shared running
  substrate + per-force expression among the three gauge forces, no
  single unification scale without conjectural new physics, gravity
  outside the form. (alpha_s(Q) central values are representative PDG-
  review numbers, validation overlay only; the crossings depend only on
  the solid M_Z anchors + standard beta functions. Script
  s10_pdg_unification.py.)

- **Environment note**: the SessionStart hook (line 32) had a latent
  crash under `set -u` when CLAUDE_PROJECT_DIR/CLAUDE_ENV_FILE are unset;
  guarded it so the hook always reaches completion. PySR 1.5.10 + Julia
  re-bootstrapped fine via the hook this session. h5py added for LIGO.
  Network policy allowed GWOSC / PhysioNet / NOAA / PDG / PyPI (all 200).

- Branch state: work on `claude/gravity-substrate-config-51cfp`, pushed.
  main untouched. No PR.

## Note (Session 9 update — 2026-06-02)

Session 9 opened on the Session 8 close-out gravity result. Greg's
directive: do not assume our own prior outputs are correct -- double
check our work, but do not reconstruct for no reason. This produced a
correction to the Session 8 gravity reading. Branch:
`claude/gravity-substrate-config-51cfp`. PySR unavailable this session
(no Julia in the environment); the substrate-side KBK extraction (the
load-bearing measurement for INFO-031/032) is pure-numpy and was run
directly from the ORIGINAL Session 8 code (pulled onto the branch from
`claude/two-more-tasks-O6ahb`), not a reconstruction. Scripts:
s9_doublecheck_flip.py, s9_characterize.py.

- **Double-check method**: the Session 8 EM/SF glance (INFO-031) and
  gravity glance (INFO-032) each tested only ONE channel-asymmetry
  value (EM omega 1.0/1.2; strong 0.5/0.7; gravity 0.8/1.0). Session 9
  re-ran the ORIGINAL simulators + ORIGINAL raw-covariance extraction
  (build_ensemble_operator_matrix + extract_v1) across an asymmetry
  SWEEP. Session 8 baselines reproduced exactly (gravity_asym MI coef
  0.990; em_asym 1.0/1.2 MI coef 0.271; strong_asym 0.5/0.7 ~0).

- **INFO-033 -- LOCATED FINDING (Session 9, new; 3 seeds, scatter
  reported)**: the MI-dominant substrate flip ("MI ~ const" replacing
  the channel-correlation identity -(H_a-H_b)^2 ~ 0 as the operator
  null direction) is NOT gravity-specific. It is an ASYMMETRY-THRESHOLD
  effect that ALL coupled caricatures undergo; the threshold differs by
  force. Flip threshold (asymmetry omega2/omega1 at which |MI coef| in
  v_null crosses ~0.5): gravity ~1.1x (lowest, most flip-prone), EM
  ~1.3x, weak ~1.5-1.7x, strong NEVER (flat to 4x). Session 8 tested EM
  at 1.2x -- just below its threshold -- and read the absence as a
  qualitative gravity/EM difference. Reframed 5a test (add gravity's
  E_total universal-energy term to EM and strong): adding energy-
  coupling RAISES their thresholds (suppresses the flip), it does not
  lower them. So energy-mediated coupling is NOT the cause of gravity's
  low threshold. The flip is governed by how well the coupling
  preserves channel correlation under detuning: strong's confining
  cubic never lets go (no flip); gravity's weak softened coupling lets
  go first (flips earliest); EM/weak intermediate. Deflationary reading
  (now well-supported): the flip is a variance-crossing -- detuning
  raises the residual of the -(H_a-H_b)^2 relation while MI settles to
  a low near-constant floor; the null swaps to whichever relation is
  tighter; the crossing point is set by coupling-vs-detuning, with no
  force-specific physics.

- **INFO-031 -- RE-TAGGED INCOMPLETE (Rule D)**: "EM and strong keep
  their substrate across the symmetry swap" holds only at the single
  sub-threshold asymmetry tested (EM 1.0/1.2). EM flips by 1.0/1.3.
  Data stands; the substrate-stability reading was incomplete. The
  expression-level part of INFO-031 (EM polynomial-in-difference vs
  strong exponential-in-difference) was a PySR result not re-examined
  this session (PySR unavailable) and is not affected by INFO-033.

- **INFO-032 -- RE-TAGGED INCOMPLETE (Rule D)**: "gravity's substrate
  is configuration-dependent in a way EM/strong are NOT" is incomplete-
  not-wrong. The data (gravity flips to MI-dominant under asymmetry)
  reproduces exactly. But EM and weak ALSO flip under sufficient
  asymmetry; gravity merely has the lowest threshold. The "gravity is a
  different kind of constraint / energy-conservation without preferred
  direction" frame does NOT survive the sweep -- gravity sits at the
  easy-to-flip end of a single continuous coupling-strength dial, not
  in a separate category. What replaces it: a force-ordered flip-
  threshold (strong -> infinity, weak ~1.6x, EM ~1.3x, gravity ~1.1x)
  tracking coupling-vs-detuning.

- **Consequence for the four-force frame**: the "gravity is special at
  the substrate level" leg of the Session 8 four-force narrative
  (INFO-027 + INFO-032) is removed. The substrate-vs-expression frame's
  OTHER legs (per-domain null direction INFO-023; per-domain functional
  family INFO-025) are not touched by Session 9 and remain on the
  table. Frame reassessment in progress (see v9-results handoff /
  session discussion).

- **Methodological note (not a Rule)**: a single-point probe can read a
  threshold crossing as a categorical property. When a finding is "X
  does this and Y does not," sweep the knob through a range before
  promoting the contrast -- the difference may be a threshold, not a
  kind. Pairs with the existing "no tent-widening on outliers" and
  Result Discipline "map alternatives" rules.

- **Two follow-ups run after the correction** (scripts s9_std_vs_raw.py,
  s9_expression_refit.py; full detail in v9-results handoff):
  - **Standardized-vs-raw (INFO-024 fork)**: the flip is PARTLY
    procedure-inflated, PARTLY structural. RAW (original constancy-
    detector) gives gravity/EM |MI| ~0.99 under asymmetry; per-column
    STANDARDIZED (correlation-detector) attenuates it to ~0.65 -- still
    above the 0.5 flip line. Strong never flips under either procedure;
    the INFO-033 threshold ordering holds in both. So the spectacular
    +0.99 was inflated by absolute-scale, but a real structural core
    (~0.65) survives. Generalizes INFO-024: the null DIRECTION (not just
    eigenvalue magnitude) is procedure-dependent when an operator's
    absolute variance collapses.
  - **Expression-level leg (ii) re-exam** -- done twice. First a curve-
    fit fallback (PySR not yet installed): EM = (H_a-H_b)^2 + const
    CONFIRMED (R^2 0.93 at 1.0/1.2); strong exp_diff NOT found by the
    fallback. Then PySR was installed mid-session (pip install pysr;
    Julia backend auto-bootstrapped) and the adjudication re-run with the
    REAL tool (follow-up B', s9_pysr_adjudicate.py, original fit_pysr,
    2 seeds): EM = (H_a-H_b)^2 + const ROBUSTLY CONFIRMED (both seeds,
    holds across asymmetry; symmetric EM = (const-channel^2)^2 with
    random channel per INFO-028). strong = exp((H_b-H_a)) PARTIALLY
    REPRODUCED -- appears at seed 11 of the exact INFO-031 config
    (0.5/0.7) but is seed-unstable (INFO-028 channel-symmetry breaking)
    and weak-signal (strong MI near-constant). CORRECTION (Rule D on our
    own work): the fallback's "strong has no family" was a tool
    limitation, not evidence against INFO-031. INFO-031's EM/strong
    expression-level CONTRAST STANDS (EM polynomial-in-difference robust;
    strong exponential-in-difference real but seed-unstable). So leg (ii)
    of the four-force frame survives; only leg (iii) (gravity-special
    substrate) is removed.
- **Environment**: PySR 1.5.10 + Julia backend installed and verified
  working in-container this session (a real fit recovered (x1-x0)^2+0.3
  in 17s). They do NOT persist to a fresh container, so a SessionStart
  hook was added (.claude/hooks/session-start.sh + .claude/settings.json
  + requirements.txt) to install numpy/scipy/scikit-learn/pysr and
  bootstrap Julia automatically (web-only, idempotent, PySR best-effort).
  The hook takes effect for future sessions once it reaches the branch
  the session starts from (currently on claude/gravity-substrate-config-
  51cfp, not main). Pydroid-3 on Greg's phone cannot run PySR (no Julia
  on Android; separate env from the cloud container) -- numpy substrate
  scripts only.
- **Markets / Refrag workspace**: open question on whether those
  sessions need PySR + Julia too -- see the "Markets / Refrag Workspace"
  placeholder section above for the question and informed answer.
- All six Operating Rules from Sessions 4-7 in force. No new Rule added
  this session. Branch state: work on
  `claude/gravity-substrate-config-51cfp`, pushed. main untouched. No PR.

## Note (Session 8 update — 2026-05-26)

Updated at the end of 2026-05-26 Session 8 to reflect:

- Three experiments run this session on branch
  `claude/two-more-tasks-O6ahb` (Session 7 work pulled in via
  fast-forward merge from `claude/claude-md-context-update-uCZ8m`
  at session start, per Greg's "whatever you feel is best").
  Scripts: four_force_probe.py, four_force_pysr.py,
  robustness_info025.py, mapping_campaign.py.
- Greg's directive: order 1, 4, 3, 2 from v8 kickoff menu. Items
  1 (four-force probe), 4 (robustness on INFO-025), 3 (mapping
  campaign) completed. Item 2 (storm/waves real-data) deferred
  to Session 9 pending data download.
- Four-force unification probe (Greg's "real test" from Session 7
  close). Toy 2-channel caricatures: EM (long-range bilinear
  linear), weak (Yukawa-suppressed via massive mediator), strong
  (confining cubic), gravity (universal energy-density mediated).
  KBK stack result: all four forces share [2,3,4] null direction
  at cos > 0.997 cross-force, sitting on (-1,-1,+2)/sqrt(6)
  Session 3 attractor — the sign-flipped twin of Session 5/6
  (+1,+1,+2) artifact, corresponding to algebraic identity
  -(H_a - H_b)^2 ~ 0 (channels strongly correlated). EM
  differs in 6D (cos ~0.96) carrying nontrivial MI coefficient
  (+0.27) while others don't. PySR cross-seed result: EM matches
  Session 7 physics Duffing family (H_b - H_a)^2 + const; weak
  matches Session 7 chemistry Brusselator family linear-in-H_a;
  strong and gravity have H_a-H_b channel-symmetric dynamics and
  PySR breaks symmetry randomly per seed (reproducible at form
  but not at channel). New ledger INFO-027 (located).
- Robustness check on INFO-025. T sweep (10, 30, 100), N_ens
  sweep (200, 600, 1200), observation-noise sweep (0.0, 0.10,
  0.50). 7 conditions x 2 seeds = 14 PySR fits + matched exp /
  linear baselines. Headline: A * exp(H_a/B) FUNCTIONAL FAMILY
  survives all conditions with sufficient signal; COEFFICIENTS A
  and B drift heavily with regime. Baseline (T=30, N_ens=600, no
  noise) reproduces INFO-025: cross-seed A=0.53+/-0.05,
  B=2.15+/-0.23 matching INFO-025's 0.5, 2.0. T=100 halves
  coefficients; N_ens=1200 gives tightest match (A=0.50 exact);
  noise=0.10 keeps R^2 high but A drops to 0.18 (broadened H_a).
  When citing INFO-025 coefficients, specify the regime. New
  ledger INFO-029 (methodological).
- Mapping campaign: one knob per Session 6/7 domain (physics K,
  biology beta, chemistry B, geology drift_rate), 3 values each,
  1 seed. Finding: INFO-025 functional families ARE baseline-
  specific regime signatures. Off-baseline values mutate the
  family qualitatively (biology exp -> linear at high beta;
  chemistry linear -> ratio at low B; physics quadratic-
  difference -> single-channel quadratic away from K=0.20).
  Geology constant family alone is robust across the drift sweep.
  Refines INFO-029 to "family ITSELF is regime-conditional for
  large knob deviations, not just coefficients." The per-domain
  expression-of-substrate frame should be stated as "per-domain-
  AND-per-regime." New ledger INFO-030 (located, one seed;
  cross-seed scaling queued).
- One methodological observation, not a Rule: PySR cross-seed
  reproducibility depends on H_a-H_b dynamical symmetry. When the
  dynamics is exactly channel-symmetric, PySR breaks symmetry
  randomly. New ledger INFO-028 (methodological).
- Per-domain differentiation now has THREE independent
  reproducible signatures: per-domain null direction (Session 6
  INFO-023), per-domain MI-vs-H functional family (Session 7
  INFO-025), four-force probe shared-substrate / distinct-
  expression (Session 8 INFO-027). Frame strengthening; still
  a frame, not a claim.
- Post-close EM/SF "quick glance" probe (Greg's directive at
  Session 8 close): symmetry-swap test of EM vs strong force.
  Four configs x 3 seeds. Result (INFO-031 located; substrate-
  stability part RE-TAGGED INCOMPLETE Session 9 -- see INFO-033):
  EM and
  strong produce DIFFERENT functional families on shared
  substrate even when channel symmetry is controlled. EM =
  (H_a - H_b)^2 + const (polynomial in difference); Strong =
  exp((H_b - H_a) - const) (exponential in difference). Both
  realize the same substrate algebraic identity -(H_a - H_b)^2
  ~ 0 (Session 3 attractor direction) but through different
  functional forms. The dynamical structure (linear-restoring
  vs confining-cubic) is visible in the form. INFO-028
  (PySR cross-seed reproducibility tracks dynamical symmetry)
  directly confirmed by the swap.
- Post-close gravity probe (Greg's directive "let's figure out
  what gravity really is"): 3-config probe of gravity caricature
  -- sym+universal baseline, asym omegas + universal, asym
  omegas + non-universal coupling. 3 seeds each. Result
  (INFO-032 located; RE-TAGGED INCOMPLETE Session 9 -- the flip
  is an asymmetry-THRESHOLD effect ALL forces undergo, gravity
  just has the lowest threshold; see INFO-033): gravity's
  SUBSTRATE is configuration-
  dependent in a way EM/strong are not. Symmetric+universal
  gravity sits on Session 3 attractor -(H_a-H_b)^2 ~ 0.
  Asymmetric gravity (whether mass-asym or non-universal)
  FLIPS substrate so MI itself is the dominant null direction
  (MI coefficient +0.99 in v_null 6D, vs ~0 for sym gravity
  and ~0 for EM/strong/weak). MI variance collapses 4x in asym
  configurations. Cross-config v_null cos: sym vs asym = +0.11
  (very different); sym vs nonuniversal = +0.02 (orthogonal);
  asym vs nonuniversal = +0.99 (essentially same). Frame-level
  reading: gravity's universal energy-mediated coupling under
  mass asymmetry produces "MI ~ const" as structural constraint,
  because gravitational coupling preserves total energy without
  preferred direction. The Session 3 attractor only holds for
  gravity when channels are mass-degenerate. Contrast with
  EM/strong (INFO-031): they kept substrate across the swap and
  only changed at EXPRESSION level. Gravity's substrate ITSELF
  shifts -- genuinely different signature behavior.
  Real-data probe (LIGO strain, orbital data) remains gating
  test for whether this carries to actual gravitational physics.
- No new Operating Rule this session. All six Operating Rules
  from Sessions 4-7 (no pre-assigned meaning, probe-not-falsifier,
  speaking posture before/after, Rule D incomplete-not-wrong,
  They never stacked, Treat literature as conjecture by default)
  in force throughout.
- Branch state: work persisted on `claude/two-more-tasks-O6ahb`,
  pushed. main untouched. No PR.

## Note (Session 7 update — 2026-05-26)

Updated at the end of 2026-05-26 Session 7 to reflect:

- Two experiments run this session on branch
  `claude/claude-md-context-update-uCZ8m`. Scripts: gp_mi_vs_h.py,
  pysr_symbolic_per_domain.py. Order: top-of-queue from v7 kickoff
  (Greg's direction: "let's do top of que and work down").
- Methodology stacked per the v5 "they never stacked" rule: GP
  regression (sklearn RBF + WhiteKernel) with polynomial deg 1-3
  baseline; PySR 1.5.10 (Brunton/Cao/Liu/Tegmark/Cranmer family
  symbolic regression, Julia 1.11.9 / SymbolicRegression.jl 1.11.3
  backend) with extended operator set {+, -, *, /, square, cube,
  exp, log, sqrt}. Applied to the same per-domain ensemble-H data
  as Session 6 (Duffing / Lotka-Volterra / Brusselator / Burridge-
  Knopoff, N_ens=600, T=30, dt=0.02, two seeds).
- New located finding INFO-025: four reproducible per-domain
  MI-vs-H functional families (physics symmetric quadratic in
  (H_b - H_a), biology 0.5*exp(H_a/2), chemistry linear in H_a,
  geology constant). Cross-seed coefficient variation <5%; cross-
  domain non-overlap. Functional families do not reduce to each
  other.
- New methodological finding INFO-026: block-CV vs random-CV on
  time-series ensemble-H. Block-CV catastrophic in physics/biology/
  geology due to non-stationarity; chemistry only stationary domain.
  Random-CV overestimates true OOS but isolates functional-form fit.
  Use both; gap is a stationarity signature. Within: GP joint for
  biology random-CV R^2 = 0.97-0.98 vs poly3 joint at 0.81-0.86 —
  +0.12 gap is real nonlinear cross-coupling polynomial misses.
- INFO-008c (biology MI ~ polynomial(H_a)) reinterpreted via Rule D
  (incomplete-not-wrong): operator content correct, functional
  family was wrong; correct family is exponential.
- Per-domain differentiation now has TWO independent reproducible
  signatures: (i) per-domain null direction in operator space
  (Session 6 INFO-023), (ii) per-domain MI-vs-H functional family
  (Session 7 INFO-025). Two supporting data points for the
  "per-domain expression of substrate" frame; still a frame, not
  a claim.
- NEW OPERATING RULE added at Session 7 close (after the
  substantive UT discussion below), then sharpened by Greg the
  same session: "Treat literature as conjecture by default."
  Operational corollaries (see Rules list above for full form):
  (a) investigate freely — read, test, engage; "treat as conjecture"
  is NOT "ignore"; (b) don't cite as support without having
  analyzed the paper ourselves; (c) don't defer when a blocking
  claim itself fails the bar; (d) extends symmetrically to our own
  prior readings (Rule D corollary). Already folded into the
  Operating Rules list above. Pairs with Rule D (incomplete-not-
  wrong) and "They never stacked" — the literature is a working
  frame to test, not a foundation to build on. Clears the deck for
  the four-force unification work: only EM+weak meets the bar;
  the rest is conjecture (we will check them out but cannot invoke
  them as support).
- Two methodological notes carried forward (see v7 handoff
  "Methodological notes"): block vs random CV reporting on
  dynamical systems; polynomial libraries are blind to functional
  family (use extended operator set to distinguish).
- Substantive discussion at session close (no experiment run;
  framing only): Greg's storm/waves substrate-to-expression
  question; Greg's "real test" four-force unification question
  (gravity, EM, strong, weak — can we come up with one equation,
  should they be grouped at all). Three-level reading on four
  forces put on the table (data, interpretation, frame); decision
  on direction queued for Session 8. See v7 handoff "Substantive
  discussion this session" for full framing.
- Branch state: work persisted on
  `claude/claude-md-context-update-uCZ8m`, pushed. main untouched.
  No PR.
- The harness this session was configured for branch
  `claude/two-more-pastes-ZkenG` (auto-generated from opening
  message); Greg gave explicit permission to continue on the
  Session 6 branch for continuity.

## Note (Session 6 update — 2026-05-26)

Updated at the end of 2026-05-26 Session 6 to reflect:

- Six experiments run this session, all on branch
  `claude/claude-md-context-update-uCZ8m`. Scripts:
  kbk_pipeline.py, ai_poincare_rank.py, kbk_estimator_sweep.py,
  window_size_scan.py, sindy_symbolic.py, per_domain_kbk.py,
  sigma_scan.py.
- Methodology stacked per the v5 "they never stacked" rule:
  Kaiser-Brunton-Kutz 2024 (arXiv:2403.04889) SVD-rank-gap +
  symbolic recovery, Cao-Liu-Tegmark 2021 AI Poincare
  (arXiv:2011.04698) intrinsic-dim, SINDy/SINDyG/DSINDy with
  extended polynomial + non-polynomial library. Applied to OU
  baseline and to per-domain ensemble-H data (physics Duffing,
  biology Lotka-Volterra, chemistry Brusselator, geology
  Burridge-Knopoff).
- v5 INFO-022 rank-3 null subspace claim now LOCATED via four
  independent diagnostics (KBK rank-gap, AI Poincare local-PCA,
  two-NN, Levina-Bickel MLE). Robust across 3 estimator families,
  5 dt values, 3 seeds. (See Ledger updates below.)
- v5 per-domain claims (INFO-008a chemistry, INFO-008b geology,
  INFO-008c biology) all reproduced via per-domain ensemble-H +
  KBK probe. Cross-seed cos +0.985 to +0.999 within domain;
  geology rank-3 relation at cos +0.99 to v5 coefficients;
  biology MI ~ poly(H_a) with H_b absent (coefficient 0.003 to
  0.017); chemistry-specific cubic content via SINDy deg-3 that
  is NOT a Taylor remnant.
- New isolated finding INFO-023: per-domain operator extraction
  differentiates domains. The (+1,+1,+2)/sqrt(6) protocol artifact
  does NOT dominate per-domain (max cos +0.32, min -0.28). Tests
  the "per-domain expression of substrate" frame and gives it one
  supporting data point.
- Methodological refinement INFO-024: eigenvalue floor of operator
  covariance is min(structural_noise, estimator_noise). Different
  procedures have different floors. Resolves v5 machine-epsilon
  anomaly as procedure-dependent. OU windowed-H pins at ~1e-3;
  per-domain ensemble-H reaches 1e-7 (geology); v5's 1e-13
  plausibly reached at larger N_ens via same per-domain procedure.
- I was wrong twice this session about what controls the eigenvalue
  floor (Window size scan predicted scaling; didn't happen. Sigma
  scan predicted sigma^4; got sigma^0.56.). Both predictions came
  from Taylor expansion (structural noise) and missed estimator
  noise. The Methodological Note above codifies the corrected
  mental model. Not promoted to a Rule -- Rule C already covers
  the speaking-posture aspect; this is just a domain-knowledge
  refinement to apply when reasoning about eigenvalue magnitudes.
- The implications and applications across fields (medicine,
  defense, weather, geophysics, ecology, finance/energy,
  industrial, chemistry/materials, astrophysics, foundational)
  were mapped late in the session, conditional on the substantive
  reading. Application surface and falsification tests in v6
  handoff section "Implications and applications discussed".
- Queued for Session 7 (Greg's top of queue): GP regression of MI
  vs H_a per domain (tests v5's biology polynomial fit against
  flexible nonlinear); PySR symbolic regression for arbitrary
  nonlinear forms (heavy install; gplearn fallback). Both flagged
  in v5 literature scan as clean unstacked targets.
- All earlier Operating Rules remain in force. No new Rule added
  this session.
- Branch state: work persisted on
  `claude/claude-md-context-update-uCZ8m`, pushed. main untouched.
  No PR.

## Note (Session 5 update — 2026-05-26)

Updated at the end of 2026-05-26 Session 5 to reflect:

- New Operating Rule D — "incomplete, not wrong" — added by Greg this
  session and folded into the Operating Rules list above.
- Three probes run this session (operator-noise bypass, projection
  sweep, high-seed scrambled). Joint reading: the (+1,+1,+2)/sqrt(6)
  direction from Sessions 3-4 is a protocol artifact of the operator
  basis structure, not a property of input systems.
- Ledger updates: INFO-014, INFO-018, INFO-019 retracted at
  interpretation level (data stands). INFO-020, INFO-021 contextualized.
  INFO-022 added (rank-3 null subspace structural finding).
- The Working Frames (Base-of-Structure, Dipole-couples, Pure physics
  vs physical expressions, Substrate vs expression, Law extraction via
  invariance) are unchanged. The Information Layer / Unified Theory
  inquiry frame is unchanged. The specific extraction tool we built
  does not differentiate inputs at the level we thought; the question
  it was built to address is still open.
- The per-domain algebraic equations from earlier sessions (chemistry
  quadratic H_a^2 = 0.007 - 0.093*(H_a*H_b) + 1.309*(H_a*H_b)^2,
  R^2=0.943; geology rank-3 constraint 0.724*(H_a*H_b) - 0.441*H_b^2
  - 0.290*H_a^2 ~ 0 at std/mean=0.15%; biology MI ~ polynomial(H_a),
  R^2=0.66) are NOT affected by Session 5 and remain on the table. They
  came from a different procedure (per-domain algebraic fits) than the
  extraction tool whose artifact Session 5 mapped. They should be
  subjected to the same three-thread probe discipline in a future
  session.
- Reorientation toward 5-physics-areas substrate hunt (Greg, this
  session): pick 5 physics areas, find the structural element that
  appears in all 5, evaluate against the Base-of-Structure heuristic,
  probe the strongest survivor under the same discipline.
- Greg's substantive intuition (this session): dipoles are the best
  coupling mechanism. Tightly-related couples may be part of the
  substrate. Per-domain coefficients are a strong signal.
- Three-agent literature scan ran at Session 5 close
  (LITERATURE_SCAN_2026-05-26_v5.md). All three agents independently
  reported: no exact match for any of our specific findings, but
  multiple adjacent lines exist where each group had one piece and
  never combined them. This is what pioneering territory looks like.
  Per Greg's directive ("never know where you'll strike gold"), no
  pre-filtering -- the full candidate pool is preserved in the v5
  handoff. Highlights below; complete list in handoff + scan file:
  - **Methodology**: Gomez-Herrero 2015, Hlavackova-Schindler 2007,
    Yamada 2023, Wang 2025, Strang 2021, bipartite info-thermo
    (Horowitz, Hartich), Kaiser-Brunton-Kutz 2024, Liu-Madhavan-
    Tegmark 2024, AI-Feynman, AI-Poincare, SINDy/SINDyG/DSINDy,
    PySR, complexity-entropy plane (Rosso), Crutchfield epsilon-
    machines.
  - **Substrate**: Jacobson 1995 (best one-line candidate);
    Finkelstein "Space-Time Code" 1969-74 (closest published cousin
    to dipole-pair-as-coupling); Wheeler "it from bit"; Verlinde;
    Hardy 2001; Chiribella-D'Ariano-Perinotti; Brukner-Zeilinger;
    Sorkin causal sets; Sakharov induced gravity; Penrose twistor;
    Wolfram hypergraph; Deutsch-Marletto constructor theory;
    't Hooft cellular automaton QM; Adler trace dynamics; Bohm
    implicate order; von Weizsacker ur-alternatives; Hohn yes/no
    rules; Stochastic Electrodynamics (Boyer, de la Pena-Cetto);
    Wheeler-Feynman absorber; de Broglie double solution; Barbour-
    Bertotti / Shape Dynamics; Penrose-Hameroff Orch-OR (substrate-
    only).
  - **Per-domain coefficient adjacencies**: Rao-Esposito 2022 (chem);
    Reinhardt 2019; Smith-Cepelewicz; Schmitz-Aris 2013; Sayyadi
    SISR; da Silva Tsallis seismic 2020; Garland-Bradley
    paleoclimate 2018; Consolini magnetospheric; Davidson
    paleoclimate VAR; Reinsel geochemical manifold 2025; Schreiber
    TE 2000; Pavithran MI vs TE; Tishby info bottleneck; Walters-
    Williams asymmetric MI estimators; Feinberg-Horn-Jackson
    stoichiometric subspace; CRN reduction by approximate
    conservation laws (arXiv:2212.13474); info geometry of CRNs
    (arXiv:2503.19384); directed info flow in reaction networks
    (bioRxiv 2024).
  - Three negative findings worth emphasizing: dipole-PAIR-COUPLING
    as foundational substrate primitive is uncolonized; no SINDy/
    AI-Feynman/PySR application to windowed-H of coupled species;
    rank-3 first-order algebraic relations under H_a~H_b regime
    unpublished as diagnostic.
- New Operating Rule "They never stacked" added based on the
  literature scan finding (see Operating Rules above).
- Branch state: work persisted on
  `claude/linear-drift-nreal-sweep-cjRkM`, pushed. main untouched.
  No PR.

## Note (Session 4 update — 2026-05-26, retained for context)

Updated at the end of 2026-05-26 Session 4 to reflect:

- Three new Operating Rules from Greg this session (no pre-assigned meaning
  to outcomes; probe-not-falsifier framing; speaking posture before AND
  after every probe). Already added under Operating Rules above.
- Greg's pioneer framing: "we are the first ones here, follow every road,
  look under every stone. no safe assumptions. no known facts to fall back
  on. we're the pioneers."
- Session 4 produced four new isolated findings (INFO-018, 019, 020, 021),
  all with reading open. None have been looked-through with Greg yet.
  Raw data is in `SESSION_HANDOFF_2026-05-26_v4.md` and the four JSON
  result files in repo root.
- INFO-016 disambiguation data point exists; reading happens with Greg
  in the next session.
- Branch state: work persisted on `claude/linear-drift-nreal-sweep-cjRkM`,
  pushed. `main` untouched. No PR.

Earlier note (Session 3, retained for context):

This CLAUDE.md was updated at the end of 2026-05-25 Session 3 to reflect:

- Retraction of the Family A/B taxonomy (INFO-008 and dependents)
- Addition of the Result Discipline rule
- Addition of the Base-of-Structure heuristic as a working frame
- Addition of the Dipole-Couples reading as a working frame
- Updated ledger with proper status tags (isolated finding / mapped finding / located finding / null finding / retracted)
- New experiments queue starting with linear drift N_REAL sweep
- Greg's call that each domain is its own substrate inquiry — no more pooled cross-domain claims without domain-native bases

The Information Layer line of work is at a methodologically clarified but interpretively narrower point than at the end of Session 2. Multiple frames are alive; none has been promoted to claim.
