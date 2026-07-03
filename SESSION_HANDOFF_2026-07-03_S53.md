# SESSION HANDOFF — S53 (2026-07-03) — Greg's render walkthrough (Set B) → sandboxed refinements: dump-widening + taker-cap lift SOL 2.2x BUT cross-cell says SOL-ONLY (candidate parked, awaiting time-OOS); B1 harvest rungs DEAD; zoom-out verdict (Greg): START TRADING THE BIGGER TRENDS

Branch: designated `claude/s53-liquidity-walkthrough-oxt1yx` == canonical `5c5vg9` (synced every push;
tip `abf0028`+docs). Read `KICKOFF_2026-07-04_S54.md` next session. Renders: `docs/renders/s53/`
(worst10 / best10+smallwin10 / fullwindow) + the S52 set. All S52 standing corrections carry.

## 1. THE WALKTHROUGH (Greg, Set B = SOL Coinbase accum only — Set A parked)
Loser taxonomy from the S52 random renders: (1) free probes (starter barely fills, dump costs cents);
(2) full-starter dumps ≈−$1.47 each — L2's render shows price RECOVERING post-dump (the false-dump
shape); (3) confirmed-then-wrong (L3/L6). Ranked tails (new render modes `--worst-accum` /
`--small-winners-accum` on `_s52_render_walkthrough.py`, renders in `docs/renders/s53/`):
- **Worst-10 losers: ALL confirmed→ALL-IN @$5k, worst −$12.95 (~26bps), NO dump in the tail** — the
  tail is capped and it is entirely a confirm-quality phenomenon. L01 anatomy: confirm fired at the
  swing's exhaustion valley, $4,611 of $5k completed TAKER, unload taker into the reversal.
- **Best-10 winners: top-3 = +$140.60 of the +$214 winner column** (14 winners total). Best trade
  (+$63.73): instant confirm, 0% taker, 18-min 140bps ride, all-maker unload.
- **Smallest winners = harvest failures at SPIKE TOPS, not small swings** (+$0.27 winner rode 45bps,
  exited mk $0 / tk $5,003 into the crash).
- L1 entry question (Greg "why so late?"): entry lag = θ≈23bps BY CONSTRUCTION (causal zigzag);
  L1's chart shows a double-top that would fake out any tighter θ. Axis-autoscale caveat noted
  (29bps window looks like a mountain) → fullwindow renders carry range/drift in the title.
- **Dipole DIVE chart (Greg's phone image):** the divergence FILTER is wired (the entry gate); the
  DIVE (d lean/dt, pins x=0 on 2000 winners) is NOT wired anywhere — C1 candidate trigger.

## 2. GREG'S RULES SET THIS SESSION (load-bearing)
- **NO GATES.** Gates were removed because we were hardly trading; the objective is $/hr, not win
  rate. Eliminating losers eliminates winners too. Judge every change on net $/hr AND legs/hr.
- D-class ideas EXCLUDED (maybe later): confirm-budget blocker, confirm timeout, stricter confirm
  modes. (A1 diagnostics then showed confirm-budget would have been a dud anyway — corr −0.10.)
- Sandbox everything before committing changes; defaults untouched (all new params opt-in;
  bit-identity canary PASSED: 65 legs / +56.204187 dipole, 326 / −273.547137 ungated).

## 3. DIAGNOSTICS (`scripts/_s53_accum_sandbox.py`, full leg population, SOL window)
- **A3: 61% of dumps are FALSE** (22/36 would have confirmed before the next turn; −$31.14 of the
  −$45.28 dump column). Cross-cell: universal — ETH 78%, BTC 56%, DOGE 75%, XRP 70%.
- **A2: total taker share = the cleanest net separator** (corr −0.31): 0%-taker legs +$12.40 mean /
  71% win; top-quartile taker −$5.68 / 25%.
- **A1: bps-consumed-at-confirm ≈ no relation** (corr −0.10) — kills the confirm-budget idea on data.

## 4. VARIANT SWEEP (SOL, dipole arm, $/hr; controls + Q1 on every row)
Opt-in params added to `odcore/swing_accum.py`: `dump_mult`, `p2_taker_cap`, `harvest_rungs`,
`slide_x_mult`. Results (`_s53_accum_sandbox_results.json`):
- base +1.60 → **dump×3 +2.84** (dump rate 55→25%, win 22→35%) → **+cap0+slideX2 STACK +3.54 (2.2x)**.
- Controls negative under every variant (shuffle −2.2..−3.1, reversed −2.1..−3.3) on SOL.
- **B1 harvest rungs LOSE (−0.26 / +0.21 vs +1.60)** — selling into strength caps exactly the fat
  winners that carry the column. Greg's "eliminating losers eliminates winners" confirmed on the
  EXIT side. DEAD.
- **Q1 (honest queue) ≈ $0 on EVERYTHING** — base and variants. The entire measured edge lives in
  the front-of-queue fill tier. Keeps the whole thread R&D, not deploy.

## 5. CROSS-CELL RERUN (`--cells`, 7 cells; `_s53_accum_crosscell_results.json`) — the verdict
**The candidate does NOT generalize. Mechanism universal, money SOL-only.**
- SOL Coinbase: the only cell with clean structure (gate + / controls − / variants lift).
- ETH Coinbase: base −$1.05, variants don't rescue, **REVERSED CONTROL POSITIVE (+0.53→+1.09)** —
  the S51 disqualifier shape on that cell/window. DOGE: shuffle positive. BTC: 0.7 flips/hr at
  θ=20bps (barely ever swings 20bps — 196h window). XRP: ~flat.
- Bybit cells: 1 leg each — SAME 5.83h window as S52 (cron has not delivered a new window yet);
  still ZERO time-OOS on venue cells.
- **Disposition: dump_mult∈[1.5,3] + p2_taker_cap=0 parked as a SOL-Coinbase-ONLY candidate,
  awaiting time-OOS. NOT a default. Per-cell statement: works on {SOL Coinbase}, not
  {ETH/BTC/DOGE/XRP Coinbase}.** Window-personality caveat: ETH's window is one +413bps grind
  (trend, not oscillation) — which cells "work" may substantially be which windows oscillated.

## 6. ZOOM-OUT (Greg's full-shape request; `_s53_render_fullwindow.py` → docs/renders/s53/fullwindow)
Window ranges vs our trading scale: SOL 630bps range (35h) / ETH 624 (+413 drift, 64h) / BTC 1094
(−766, 196h) / DOGE 681 / XRP 482 — **vs θ≈23bps**. We harvest the smallest tradeable ripple; the
shapes show multi-hour 100–300bps waves where the fee floor would be 2–5% of the swing instead of
~25%. **GREG DECISION: "we definitely need to start trading the bigger trends" → S54 job #1.**

## 7. Files added/changed (all pushed; canonical synced)
- `odcore/swing_accum.py`: opt-in variant params (defaults bit-exact, canary in §2).
- NEW `scripts/_s53_accum_sandbox.py` (diagnostics / --sweep / --cells), NEW
  `scripts/_s53_render_fullwindow.py`, render modes on `_s52_render_walkthrough.py`.
- Results: `_s53_accum_sandbox_results.json`, `_s53_accum_crosscell_results.json`.
- Renders: `docs/renders/s53/{setB_sol_worst10,setB_sol_smallwin10,fullwindow}/`.
- `paper_trade.py` / `swing_maker.py` / deployed baseline: UNTOUCHED.

## NEXT (S54) — see `KICKOFF_2026-07-04_S54.md`
1. **BIG-TRENDS thread (Greg): oracle + strategy at coarse θ (~100bps class)** on the multi-day
   Coinbase books; leakage-gated, controls mandatory.
2. Multi-window Bybit confirm (still zero new windows — check the cron).
3. SOL-only candidate re-run per new window (adopt only on reproduction).
4. C1 dive-timed starter (two triggers: 1-sec price-reversal, dipole DIVE).
5. Greg: Bybit MM application (standing).
