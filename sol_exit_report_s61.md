# SOL COINBASE EXIT FIX — S61 report (re-run of the killed S60 agent; numbers delivered)

Frame: mid-band always-in flip machine (`odcore/entry_coinbase.armed_midband_flips`, naive k0,
registry theta=100 c=0.5; theta=80 secondary), mid fills at confirms, $5k flat, cb_real
8bp/side maker / 16bp taker. PRIMARY tape = Coinbase books 99.3h (`exit_legs_sol_books.csv`,
n=56 th100 / 95 th80; legs reproduce the dump exactly); SUPPORT = Binance 30d bins
(n=971/1482). All leg-slice numbers are HYPOTHESES per house law; the only machine-tier
verdicts cited are S60's (armed_stop below shuffle floor; R3b diagonal). Scratch scripts:
`s61_sol_dump_analysis.py` (+ `_bins` variant), `s61_sol_honest_fill.py` (this scratchpad).

## VERDICT: PROTECT THE CELL — zigzag stands; no exit read goes on SOL. The honest-fill
## check says the +6.11 net/leg record SURVIVES an honest queue model (repeg bound +6.25,
## fixed-price worst-case bound +0.94). The S61 build should wire the honest-fill
## MEASUREMENT arm and the fee-tier clicks; no timing change, no toll-attacker.

---

## 1. PROTECT-THE-CELL: per-candidate deltas (bp/leg vs zigzag, bootstrap 95% CI)

### Books th100 (REGISTRY, n=56, 0.56 legs/hr) — baseline gross +22.11 [−9.59,+68.10], net@cb_real +6.11, win 55%

| candidate | fires | dAll [CI] | winner/loser dSum | verdict |
|---|---:|---|---|---|
| plain stop X=40 (taker) | 29 | **−21.35 [−64.50,+5.37]** | win −1740 / lose +545 | SHREDS (matches S60 R4d −21.4) |
| plain stop X=50 (taker) | 23 | −2.20 [−11.38,+6.45] | — | null-to-negative |
| armed-dive uw stop a10xm30 uw−10 | 10 | −14.59 [−54.10,+7.89] | win −1052 / lose +235 | DEAD (S60 machine: below own shuffle floor) |
| armed-dive uw stop a10xm20 uw−10 | 12 | −14.95 [−55.16,+8.59] | — | DEAD |
| cascade-flip BUY dv30 uw20 (doge spec) | 3 | +0.57 [−2.36,+3.78] | — | n=3 anecdote; bins n=50 says **−0.54 [−1.42,+0.26]** → DEAD for SOL |
| cascade-flip BUY dv40 uw20 | 6 | −16.46 [−54.83,+4.14] | — | DEAD (books winner-kill −153.7/fire) |
| XRP-style dv40 uw10 stop | 10 | −15.45 [−54.75,+6.29] | — | DEAD (bins −1.46 [−2.84,−0.17], significantly negative) |
| R8 collapse (0.10,0) pooled | 35 | −15.44 [−57.36,+9.73] | — | DEAD (known anti-print; bins −3.57 [−6.82,−0.42]) |
| c_x trailing retrace 0.2/0.3/0.4 (toll attacker, maker at trail level) | all legs | **−17.3 / −18.0 / −21.5** (CI ~[−60,+11]) | winners −65..−73 vs losers +33..+52 | WEALTH TRANSFER — amputates winners on mid-ride retraces; median positive + mean negative = the fat winners carry the cell. DEAD |

th80 secondary: plain40 +1.20 [−4.56,+6.52], plain50 +2.37 [−1.12,+5.39] — CIs straddle 0 and
the bins registry-shape read is null; winner/loser decomposition still transfer-shaped
(plain40: win −560 / lose +674). Nothing certifiable.

### Bins support (30d instrument, registry th100 n=971): every candidate ≤ +0.79 and none
clears its CI (plain50 +0.79 [−1.43,+2.96] is the best print; its winner/loser split is
transfer: win dSum −11.5k / lose +10.4k on plain40). Reproduces the S60 R3b diagonal
(sol = every piece negative-premium). PROTECT is unanimous: books, bins, and the S60
machine+shuffle record all agree.

Cover-grace and climax-posted cover are NOT timing candidates — they live in the fill layer
and are measured in §3 (grace sweep) and bounded by the S45 polarity number (§5-C1).

## 2. POWER BAR (what the current tape can even certify; two-sided α=.05, power .80)

Books th100, n=56: detectable paired-delta = **54.1 bp/leg** (stop-like sd_delta 144.5);
unpaired gross-vs-baseline detectable = 79.3 bp/leg. NOTHING in the +0.5..+3bp class is
testable on the current books tape — any "positive" exit read on 56 legs is noise-chasing by
construction.

Accrual needed (paired test) at SOL books rates (th100 13.5 legs/day, th80 23 legs/day):

| effect | stop-like variance (sd 144.5, th100) | corrector-like variance (sd 27.6, th80) |
|---:|---:|---:|
| +0.5 bp/leg | 656k legs ≈ 48,000 d | 23.9k legs ≈ 1,043 d |
| +1.0 | 164k ≈ 12,100 d | 6.0k ≈ 261 d |
| +2.0 | 41k ≈ 3,000 d | 1.5k ≈ 65 d |
| +3.0 | 18.2k ≈ 1,346 d | 665 ≈ 29 d |
| +5.0 | 6.6k ≈ 485 d | 239 ≈ 10 d |

Bar for the cell: **no exit change is certifiable on SOL Coinbase books in under ~1-2 months
of accrual even at +3-5bp effect sizes with tame variance; sub-2bp effects are permanently
the instrument's job** (bins n=971 already detects 4.2bp; ~4 more months of bins for 2bp).
This is the shield: any future "exit fix" pitched on <150 books legs is auto-rejected.

## 3. FILL/FEE ANGLE (the mining frame's core) — honest fill on the raw books tape

Model = the deliverable spec: resting cover, queue rule ported from
`maker_book._first_fill_index` (fill when cumulative opposing taker volume clears the
best-level size ahead; queue_frac=1.0). Taker conversion when unfilled by the cap. Tape
facts: median half-spread 0.68bp; best-level ~$8.7k vs $5k clip (clip/queue 0.57).

| model (th100 registry) | taker share | close delta bp/leg [CI] | honest net/leg |
|---|---:|---|---:|
| dump convention (mid fill at confirm) | — | 0 | +6.11 |
| V1 price-blind queue (join level, queue must trade through) | **0.0%** (0/56) | +0.84 [+0.76,+0.93] (earn hs) | +6.95 |
| A repeg-to-best (deploy executor behavior; fill at queue-clear time at THEN price) | 0.0% | +0.15 [−1.81,+2.25]; winners +0.90 / losers −0.78; ex-top3 −0.43 | +6.25 |
| B rest-at-confirm-price, price-eligible vol only, taker at next turn | **10.7%** | −5.17 [−10.63,−0.77] | **+0.94** |
| B with grace G=0 (immediate taker) | 100% | −8.84 | −2.74 |
| B G=30s / 60s / 300s / 600s | 48 / 36 / 14 / 13% | −7.77 / −7.02 / −5.90 / −5.90 | −1.66 / −0.91 / +0.21 / +0.21 |

Readings (leg-slice hypotheses; the machine arm decides):
1. **The +6.11 record SURVIVES honest fill.** Honest net/leg is bounded [+0.94, +6.95];
   the realistic deploy model (repeg-to-best, which is what the executor actually does)
   sits at +6.25. The S60 worry "128/128 maker=True by construction hides the fill cost"
   is real as MACHINERY but at mid-band durations the queue genuinely clears: median
   queue-clear 8.1s, p90 40s, vs median leg ~hours. The fine-scale kills (S46 <10% fill /
   89% taker; S51 20% legs fillable) DO NOT transfer to mid-band — band axis, as suspected.
2. **The residual fill risk is PRICE-ELIGIBILITY, not queue depth**: taker share is
   identical at queue_frac 0.5 vs 1.0 (10.7%) — conversions happen when price runs off the
   fixed level before the queue clears, concentrated on LOSERS (16.0% vs winners 6.5% at
   th100) — i.e. the taker cost lands on wrong-side legs closing into the running-away arm.
   A repegging cover erases most of it; that is the executor's current behavior.
3. **Cover-grace at mid-band = contingent, not gold**: with repeg covers taker share is
   already ~0, so grace has nothing to fix (keep grace=0). Grace only matters in the
   fixed-price regime, where G≥300s vs G=0 is worth ~+9bp/leg and saturates at 300s —
   matching the S48 shape. Wire a wall-clock G≈300s arm ONLY if the honest-fill measurement
   arm shows real taker conversions in the forward ledger.
4. **S52 fill-asymmetry at mid-band: direction visible, rationing GONE.** Eligible opposing
   $ in 60s post-close: winners med $12,610 vs losers $17,676 (th100; th80 $9,435 vs
   $25,374; price-blind $49.6k vs $88.9k). Losers still fill easier, but winners' covers see
   ~2.5x the $5k clip in eligible flow — the fine-scale $483-vs-$6,161 rationing is
   fine-scale-only. cb_real 16bp RT is approximately honest for SOL mid-band winners.
5. Free ledger gold (`paper_ledger_sandbox.jsonl`, sol_coinbase_mb100 n=56): maker_close
   56/56 (by construction, confirming the miner); `lean_close` win-vs-lose NULL (means
   −0.302 vs −0.249, Cohen d −0.12, permutation p=0.665) — the with-ride lean at exit
   carries no winner/loser separation: the winners-flow-invisible law prints for free on
   the forward record too.

## 4. TOLL-LAW PRINT (deliverable 4) — CONFIRMED, NO FLAG

Books th100 winners (n=31): median giveback **50.74 vs c*theta=50** (excess-over-toll mean
+1.13, med +0.74, p90 +2.43, max +5.82; ZERO legs under 0.35*theta). th80: med 40.88 vs 40
(excess +1.14/+0.88/p90 +2.52). Bins reproduce S60's quoted numbers exactly (th100 med 51.20,
excess mean +1.77 med +1.20 p90 +3.90 — the "+1.8 mean" S60 cited was the bins print; the
books print is slightly TIGHTER, +1.13). Deaths close AT their lows to the cent
(|gross|−max_adv = +0.00 books, +0.17 bins). The toll is structural and there is nothing for
a detector to harvest — re-confirmed on the current dumps, both venues, both thetas.

## 5. WIDENED SCRAP-HEAP SWEEP (S38–S59 handoffs + CLAUDE.md + session notes) — what the S60 miners missed

New items (all band/role/fee-axis re-asks, none killed at mid-band Coinbase in the exit role):
- **C1 — S45 confirming/opposing per-fill polarity, in dollars** (S45 addendum, SOL K=1):
  fills WITH residual flow +0.745bp, +exhaustion +0.908, AGAINST (into the dive) −0.863
  (n=33-52, fine scale). The measured backbone under "post the cover into the climax" —
  worth ~1.6bp/fill IF it transfers to mid-band. Killed axis: ROLE (entry-gate) + BAND.
  Belongs as a diagnostic COLUMN in the honest-fill arm, not as a wire.
- **C2 — exhaustion read as cover-timing booster** (+22%/fill fine-scale): never asked on
  the exit side at theta=100. Same disposition: measure inside the honest-fill arm.
- **C3 — SOL back-of-queue kills are FINE-SCALE-ONLY**: S46 "<10% fill, 89% taker",
  S51 v2 "20% legs fillable, med cap $0" — §3 shows the mid-band queue clears in ~8s vs
  multi-hour legs; kill does not transfer (band axis). This report is the re-ask.
- **C5 — S55 R8 exit-lean lag (+30-60s post-top collapse window)**: `lean_exit` inert at
  fine scale, never fired at mid-band; but §1's R8/dive rows and S60's machines already
  graded collapse-triggered exits at this band: negative on SOL. Stays dead as timing;
  the residual (fill-moment marking) folds into C1.
- **C6 — swing_accum slide-cross X=(spread+taker) unload trio**: validated only at
  theta~20-24 under a −1bp rebate; at cb_real X moves ~1.9→~9.4bp/side. On SOL the whole
  unload-into-strength family is contraindicated by §1's c_x result (winners −65..−73/leg).
  Do not port to SOL.
- Fee facts re-confirmed: cb ladder 8/16 at $1-15M; CFM 4-7bp RT settling to Coinbase spot
  index; Kraken kr_mk0 (sol_kraken_mb100 +$3.14/hr already earned). **Fee tier remains
  bigger than the entire SOL exit prize** (16bp RT vs a ±1bp exit read).

## 6. BUILD-QUEUE INPUT (deliverable 5) — ranked by movement-per-line, SOL's perspective

1. **(a) HONEST FILL MODEL — YES, wire it as the opt-in measurement arm** (the killed
   agent's `honest_fill_wip.patch` in this scratchpad is a working draft: `fill_model=
   "queue"` through run_midband_cell→swing_maker, default "front" bit-identical). Value:
   converts the program's one UNMEASURED 8-16bp/leg question into a measured ~0-5bp bound;
   my tape numbers predict it will print maker_close ≈ 95-100% and ~unchanged net on SOL —
   i.e. it will CERTIFY the record rather than kill it. Add per-close diagnostics: queue-
   clear time, drift-to-fill, taker-share, and the C1 confirming/opposing polarity column.
   ~30 lines, mostly written.
2. **Fee tier (2 Greg clicks — Coinbase fee-upgrade program + CFM tier tab):** not code,
   but 12-16bp RT of movement vs the ±1bp ceiling of every exit read on SOL. From SOL's
   chair this outranks every exit mechanic including (a).
3. **(b) COVER-GRACE: contingent, default stays grace=0 for SOL.** With repegging covers
   taker share is ~0; wire the wall-clock G=300s arm only as a SHADOW inside (a), promoted
   only if the forward ledger shows real taker conversions (it saturates at G≈300s, +9bp
   only in the fixed-price regime that the executor doesn't run).
4. **(d) doge cascflip variant: fine to build for DOGE, per-cell OFF for SOL** (bins
   −0.54 [−1.42,+0.26] n=50 fires; books +0.57 on 3 fires = anecdote; S60 R3b premium
   −1.59). The variant's underwater gate must ship with the per-cell registry so SOL can
   never inherit it.
5. **(c) swing_accum fee-aware unload: DO NOT wire for SOL** — sell-into-strength caps the
   fat winners that ARE the cell (c_x trail: winners −65..−73bp/leg; harvest-rungs S53 kill
   re-confirmed at this band). If built for another cell, registry-gate it off SOL.
6. NOT on the queue: any SOL exit timing read (stops, dives, collapses, trails) — §1/§2.
   Re-grade bar per §2: ≥150 books legs across ≥2 distinct weeks AND a ≥+3bp face AND the
   machine+shuffle battery; anything less does not even reach the power floor.

## Falsification duty discharged
- Every positive-looking print attacked: cascade-flip books +0.57 → 3 fires, instrument
  n=50 negative → dead. plain50 th80 +2.37 → CI straddles 0, winner/loser transfer-shaped,
  registry-shape null. Honest-fill V1 +0.84 "improvement" → half-spread accounting artifact
  of the mid-fill convention (both sides earn it symmetrically in the flip machine; treat
  as ±0.8 accounting band, not edge). Repeg +0.15 → ex-top3 −0.43, CI [−1.8,+2.3] = null.
- n=tiny caveats: all books cells n=56/95; 99.3h single window; the tape has ffill gap eras
  (queue-clear delays conservatively inflated across gaps).
- Leg-slice vs machine: every number here is leg-slice EXCEPT where S60 machine verdicts
  are cited; the honest-fill machine arm (build #1) is the verdict path.
