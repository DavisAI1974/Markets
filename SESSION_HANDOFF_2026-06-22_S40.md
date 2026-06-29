# SESSION HANDOFF — S40 (2026-06-22) — AWS package + 14-cell 1-sec coeff basis + the per-cell fingerprint + the full ANATOMY OF A TURN (and an honest map of where the edge is / isn't)

Branch `claude/crypto-backfill-validation-31tubb` (all PUSHED). Continues S39. Memories: crypto only; zero
synthetic; per-cell deploy; never flatten/average/smooth (bucket+trade distinctiveness is the goal);
git is source of truth; commit+push regularly; never tune off one window; falsification-first.

## DONE THIS SESSION
### TASK 1 — AWS package (finished + exercised live)
- `aws/DEPLOY_AWS.md` §4: concrete Bedrock model IDs (Opus 4.7 GA / Mythos preview / 4.8-when-GA), scope
  pinned (Bedrock = agent/LLM layer only; FNO training = SageMaker/EC2 GPU; signal core = model-free).
- **prefill_embeds persisted** (`_run_alt_coeffs.py --save-embeds` -> `alt_train_pairs.json.gz`, gitignored,
  S3-bound) = the FNO training X's. `aws/train_fno/train_fno.py` loader unblocked (reads --train-pairs).
- **Venue-agnostic discovery**: `_run_alt_coeffs.parse_cell` + `run_discovery_s3 VENUES` -> one job does all
  15 cells (coin x venue). `aws/LIGHTSAIL_SETUP.md` = from-zero beginner runbook (Greg has a Lightsail acct).
- **Lightsail run executed by Greg** (browser SSH, token-clone, backfill, label, discover, push) ->
  **14-cell 1-sec deterministic coeff basis committed** (`alt_coeff_index.json.gz`, 1400 coeffs):
  bybit_perp x{btc,eth,sol,doge,xrp} (10) + kraken x{btc,eth} (4). **coinbase = dud** (REST walk-back limit,
  ~86 bins). This is TASK 2 (BTC/ETH on 1-sec) done. backfill: bybit clean 21d; kraken decent; coinbase no.

### TASK 3 — per-cell DISTINCTIVE fingerprint predictor (`odcore/fingerprint_predictor.py`, `_build_fingerprint_predictor.py`)
- Per-cell winner signature = stack(128-dim coeff + 6 micros + 5 flow), never pooled/separation-graded.
- **The coeff "merge" DIAGNOSED** (`_diag_coeff_merge.py`): the deterministic decoder = L2norm(mean of
  magnitude embeds) -> **~91% of every coeff is one shared common shape**; the distinctive part is the ~9%
  residual. "distinct before" = unique vectors, NOT separated cosine (that's why cross-cell centroids ~0.998).
  Fix: predictor CENTERS coeffs (subtract global mean) -> cells separate (0.998 -> -0.105).
- **BUY/SELL are perfect mirrors** in the residual (centroid cosine **-1.000**); whitened/centered STACK
  beats every single tool on leave-one-out cell-ID (coeff=coin/venue, micros=side). This ALSO motivates the
  FNO upgrade (a trained decoder should make coeffs that don't collapse onto one shared shape).

## THE BIG THREAD — full ANATOMY OF A TURN (Greg-driven, all tools committed)
Reverse-engineered the turn second-by-second on the 1-sec bins (BTC/ETH bybit local, turn-aligned). Layers:
- **33% = reversals/flips** (won against the prior move), localized to the recent foreground (~last 10 min).
- **At the turn = a capitulation CLIMAX** (`_render_turn.py`, `_turn_*`): ~2x volume + peak flow strength in
  the DYING direction, then the imbalance flips. NOT quiet exhaustion-to-zero.
- **The coeff/operator FLIPS through the turn** (`_turn_coeff_trajectory.py`): buy/sell-axis projection
  negative before -> crosses 0 AT the turn -> positive after. CONFIRMS at the turn, does NOT lead.
- **The turn is a QUADRATIC** (`_turn_quadratic.py`): vertex = the turn; **sharpness does NOT predict
  quality** (gentle turns pay ~76 bps vs sharp ~58; corr -0.09).
- **Acceleration LEADS** (`_turn_accel.py`): deceleration of the lean begins ~3s BEFORE the rate-zero turn =
  the only LEADING signal (everything else is coincident). Small (~3s), trailing-60s/smoothed, noise-sensitive.
- **SYMMETRY** (`_turn_symmetry.py`, Greg's eye): the turn is **94-99.6% a perfect mirror** (= time-reversible
  = NO edge). The edge is the small ODD/asymmetric remainder, and it lives in the **FLOW (5.7%), not price
  (0.4%)**. Price near a turn is a symmetric trap; flow carries the prediction. (The odd part == the
  leading rate/accel asymmetry, two lenses on one edge.)
- **Dipole<->price COUPLING** (`_dipole_price_overlay.py`): corr(dipole dive rate, price rate) = **+0.26 but
  COINCIDENT** (peaks at lag 0). Coupled, no lead -> dipole = confirmation/filter, price = timing.

## THE DETECTOR + the honest net-of-cost verdict
- `odcore/flip_detector.py` (causal, **leakage PASS**) + `_flip_backtest.py`: trailing-W flow lean ZigZag,
  flip when the lean retraces past `reversal` (the "did the defense fail" gate). **Net-of-cost: LOSES
  everywhere** (gross ~0.2 bps/swing << fees; fires 24k-100k times = over-trades the breakeven middle).
  TIMING is excellent (1-4 bps to turn); FILTERING is the missing half.
- **dive STEEPNESS gate is EXHAUSTED** (`_dd_vs_price.py`, `_flip_gate_test.py`, `_flip_gate_split.py`): harder
  dive does NOT predict bigger swing. -0.13 on winners was SURVIVORSHIP -> +0.004 full pop; per-cell ~0 (NOT
  Simpson's); mixed sign on the corrected cut. Set steepness down.

## GREG'S CLARIFICATION (S40 close) — the cut is BIG vs SMALL price CHANGE (swing magnitude), NOT win/lose
Greg corrected himself: when he said "big winners vs losers" he meant **big vs small price MOVES** (|swing|),
not P&L sign. That is the correct gate target (which turns precede a tradeable move vs a dud), and it pulled
a real signal out of the noise that the win/lose and steepness cuts missed:
- **lean DEPTH -> move SIZE** (the inline corrected-cut run): big-move turns (top 25% |swing|) have a
  **DEEPER lean at the pivot in ALL 4 cells** (diff +0.020..+0.078; corr(depth,|move|) +0.045..+0.067).
  Weak (~0.05-0.07) BUT **consistent in sign across every cell, on the full population, on the right target.**
  Deeper dipole dive -> bigger swing. **This is the first real swing-size gate INPUT** (steepness is noise; DEPTH is the signal).
- So the gate target for S41 is **predict |move| (big vs small), per cell, via the dipole STATE/DEPTH** (and
  divergence/exhaustion, the coeff fingerprint) — measured on big-|move| vs small-|move|, not win/lose.

## LOAD-BEARING METHODOLOGY LESSONS (carry forward)
1. **Never pool sign-blind**: buy/sell are mirrors (raw lean@turn buy -0.43 / sell +0.43 -> pooled ~0). A
   pooled directional signal -> ~0 is the FINGERPRINT of the anti-symmetry, not its absence. Always sign-align.
2. **Cut by BIG vs SMALL price CHANGE** (Greg's clarification), not the ~breakeven middle and not win/lose:
   the population is ~breakeven (~43% win-rate, winners bigger than losers), so any feature averaged over it
   -> ~0. Predict swing MAGNITUDE; the big-vs-small cut is where lean-depth showed up.
3. **Winner-only = survivorship**: every winner already swings ~40 bps; you cannot learn "which turns are
   big" without the NEGATIVES (dud/small-move turns). This blocked every gate test.

## NEXT (priority for S41)
1. **Real-turn / win-lose LABELS** (the unblock): define swing-turns vs dud-turns and big-winner vs big-loser
   per cell, then test BETTER features through the TAILS method (per cell, sign-aligned): the dipole STATE
   (divergence/exhaustion, the 64% read — NOT dive), the coeff fingerprint, volume-climax. This is also the
   win/lose half of Greg's "buy/sell AND win/lose" bar.
2. **Loser coeffs** (greenlit S40): discover loser-onset coeffs so win-vs-lose is testable (the missing half).
3. **The swing-size GATE** off whatever separates the tails (timing is solved by the detector; need the filter).
4. **FNO decoder training** on AWS GPU (prefill_embeds ready; the merge finding motivates it).
5. OD-BOOK committed T_test once `data/btc-book` is multi-day (S40 exploratory panel = KILL-lean; lstsq fix in).
6. **Cross-domain falsification (Greg, serious):** run the SAME turn operator (lean -> even/odd -> odd leads)
   on a NON-market contested flow (World Cup momentum / win-probability around the cooling break; the break =
   an exogenous intervention). 3-4 unrelated domains with the same even-mirror+odd-edge = a real "law". Frame,
   not claim; test it, don't declare it.

## TOOLS ADDED THIS SESSION
`odcore/fingerprint_predictor.py`, `odcore/flip_detector.py`; `_build_fingerprint_predictor.py`,
`_diag_coeff_merge.py`, `_diag_flip_states.py`, `_preentry_flow_scan.py`, `_turn_coeff_trajectory.py`,
`_render_turn.py`, `_turn_quadratic.py`, `_turn_accel.py`, `_turn_symmetry.py`, `_dipole_price_overlay.py`,
`_dd_vs_price.py`, `_flip_backtest.py`, `_flip_gate_test.py`, `_flip_gate_split.py`; aws/ finished;
`_run_alt_coeffs.py --save-embeds`. Renders gitignored (*.png).
