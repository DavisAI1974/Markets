# SESSION HANDOFF — S52 (2026-07-03) — fill-model BUG fixed (old mk0 $/hr = artifacts); Greg's ACCUMULATE strategy specced + built + validated in miniature; Bybit venue cells MEASURED (MM program = existence condition; MM3 ≈ +$115/hr/cell @$5k PROVISIONAL); 60-trade render walkthrough

Branch: designated `claude/crypto-liquidity-signals-s52-akae2j` == canonical `5c5vg9` (synced every push).
Read `S52_SIZING_MATRIX.md` (canonical corrected matrix) + `STRATEGY_accumulate_S52.md` (Greg's design
spec) + `KICKOFF_2026-07-04_S53.md`. Renders: `docs/renders/s52/` (60 PNGs + INDEX.txt).
NOTE: the earlier quick-S52 session on `s52-twxv4t` was NOT inherited (Greg: too quick to kill things);
its anti-martingale kill STANDS, its green-add fillability kill is SUPERSEDED (wrong window), its matrix
is SUPERSEDED by this session's corrected model.

## 1. THE FILL-MODEL BUG (Greg's "low $/hr doesn't look right" — answered: they were too HIGH)
`_leg_caps` summed window flow with NO price-eligibility check — it credited winners with flow that
traded AFTER price left our limit (uncatchable without chasing). Fixed in place (`price_eligible=True`
default + `window=` param; `window=None` = rest-until-close). Measured consequences (all 5 Coinbase cells,
`_s52_fill_window_audit.py` + `_s52_tif_sweep.py`):
- Honest resting fills are med 38–134s (not 10s) and 1.8–4.2x bigger — but concentrated on LOSERS
  (SOL med fillable: winners $483 vs losers $6,161; BTC $39 vs $17,060). **A fixed limit gets filled in
  full when wrong, rationed when right** — S45 adverse selection, quantified in dollars at the entry.
- **mk0 is NEGATIVE at every size and every cancel window on every cell** (old +$7–18/hr = the artifact).
- −1bp rebate cells survive: +$14–30/hr Coinbase; and $/hr RISES with resting time under a rebate
  (rest-until-turn = the right policy there; no TIF needed).
- Conviction sizing at deployed size is rebate-contingent (mk0: sized ≤ flat; −1bp: sized ≈/> flat).
  The per-leg forward-ledger sizing lift stands (executor-scale, unaffected).

## 2. GREG'S STRATEGY DISSECTION → `odcore/swing_accum.py` (new sibling executor; one-shot untouched)
Greg laid the design out piece by piece; mapped line-by-line vs `swing_maker.py` (5 deltas: one fill vs
trailing accumulation; all-or-nothing exit vs layered fee-aware unload; no lots; no quick-dump; no turn
filter). Full spec in his words: `STRATEGY_accumulate_S52.md`. Built: two-phase schedule (starter →
CONFIRM → all-in remainder with fee-aware taker completion), trailing-peg unload down the slide + slide-
cross taker rule (X = spread+takerfee), quick-dump on red-before-confirm, symmetric legs, per-lot
accounting, price-eligible + queue-aware fills (`queue_frac`), entry-only gating (`entry_ok`).
Prior DEAD labels verified NOT to apply (S51 scale-in = model-class kill; S47 stops/gates = one-shot-
architecture kills; S47 winners-not-separable-at-entry STANDS and the design routes around it).

## 3. HEAD-TO-HEAD (`scripts/_s52_accum_vs_oneshot.py`): 7 cells × 4 scales × fee tiers × {$1k,$5k}
Scales: detect_flips REV {0.1/0.25/0.5} + causal PRICE-ZIGZAG θ=4×(hs+taker)≈20–24bps (the swing-scale
stream Greg's design needs — micro scales carry only 1–4bps swings at ANY REV: nothing to confirm).
Controls: dipole-gate shuffle + reversed-side + honest-queue bracket. Results
`_s52_accum_vs_oneshot_results.json`; full tables in `S52_SIZING_MATRIX.md`. Verdicts:
- **One-shot + rebate + venue flow = the money path.** Bybit (ONE 5.8h window, PROVISIONAL): standard
  mk+2 CATASTROPHIC (SOL −$157/hr, ETH −$273/hr @$5k) → **the MM program is the existence condition**;
  MM3 −1.25bp: **SOL +$115/hr, ETH +$113/hr @$5k**. SOL first cell (spread 1.24bps + rebate), ETH second
  (0.06bps spread = pure rebate harvesting on a $40M/hr tape). Tape multiple this window 3.3x/6.9x.
- **Accum (Greg's design): validated in miniature** on SOL Coinbase zigzag+dipole (+$1.3–1.6/hr, ~66
  legs, beats shuffle −$3 AND reversed −$3 — first arm in 8 sessions where the gate beats its shuffle
  and reversed loses). Mechanics work as designed: 4:1 W/L notional truncation (winners all-in $5k net
  +$0.76..+$63.73; losers dumped at $1,250 starters ≈ −$1.50), addH ~2.2bps (all-in-on-confirmation
  beat the S40 crescendo), dump discipline visible per trade. Tiny $ → R&D thread, NOT deploy. Bybit
  accum samples unusable (1–2 legs/5.8h at the zigzag scale) — needs accrued windows.
- Ungated accum loses everywhere (turn selection is load-bearing); all-micro-scale accum loses
  everywhere (measured on all 7 cells).

## 4. RENDERS (Greg's walkthrough): `docs/renders/s52/`
60 PNGs, rng seed 52: setA_sol + setA_eth = one-shot on the BYBIT books at MM3 (10W+10L each; POST/FILL/
EXIT marked); setB_sol = ACCUM on SOL Coinbase zigzag+dipole (10W+10L; TURN/STARTER, CONFIRM→all-in,
UNLOAD mk/tk or DUMP marked). INDEX.txt has the per-trade stats.

## 5. Tools added/changed this session (all pushed)
- `scripts/_capacity_model.py`: `_leg_caps` corrected IN PLACE (eligibility default; window param);
  `_capacity_model_results.json` refreshed under the corrected model.
- NEW: `odcore/swing_accum.py`, `scripts/_s52_fill_window_audit.py`, `scripts/_s52_tif_sweep.py`,
  `scripts/_s52_accum_vs_oneshot.py` (has `_price_zigzag` + `_dipole_gate` — import from here),
  `scripts/_s52_render_walkthrough.py`, `STRATEGY_accumulate_S52.md`, result JSONs, `docs/renders/s52/`.
- `paper_trade.py` / `swing_maker.py` / ledger: UNTOUCHED (deployed baseline stands; Job 0 ran +0 new
  trades, ledger 25,845, sized>flat all 5).

## NEXT (S53) — see `KICKOFF_2026-07-04_S53.md`
1. **Greg: send the Bybit MM application** — the measured case now exists (−$157/hr standard vs +$115/hr
   MM3 on their own book). institutional_services@bybit.com (+ Backpack VIP optional).
2. Multi-window Bybit confirm as the 0 */6 cron accrues (venue cells + accum at the zigzag scale with
   usable samples). NEVER tune off the one window.
3. Accum refinement (leakage-gated, controls mandatory): asymmetric confirm/dump bands, lean/dipole
   confirm modes, starter/complete window sensitivity — on the zigzag stream only.
4. Wire venue cells into `_capacity_model.cell_scenarios` (path/scen/taker params) for the canonical
   scenario JSON.
