# S60 EXIT NOTES — Piece 2 round-by-round record (2026-07-03/04)

The durable log of the EXIT piece (Piece 2). Same discipline as S58_ENTRY_NOTES.md: one round =
one defined test; update this file EVERY round; read the mistakes ledger before building; the
agent fleet runs per AGENT_PLAYBOOK_PIECES.md (exit translation).

GREG'S S60 CALLS AT OPEN: (1) he did NOT click Run workflow on the Kraken book collectors —
first cron tick is 00:00Z Jul 4 (workflow landed on default 22:01Z Jul 3; 0 runs at check);
(2) FULL FLEET on exit round 1; (3) nothing changes priorities — sequencing = Code's call
(kickoff order kept: Kraken backfill launched first, exit fleet runs while it pulls);
(4) **ZIGZAG EXIT = the starting place** (flip-at-next-confirm is the round-1 anchor every
candidate is measured against); (5) **DON'T FORGET THE DIPOLE DIVE that cuts down on exit
lag** — the S55-R9 exhaustion wrinkle (negative coarse-top depth corr) / S45 can't-refuse
fillability peak: opposing flow DIVING in at the forming top fires before the price confirm.
Wired into the dump as first-class trigger columns: armed-dive r8 configs (collapse to
-0.20/-0.30) + pure-dive dv20/dv30/dv40 (first sl <= -d, no arm) + slmin/t_slmin anatomy.

SCORING FRAME (inherited): always-in-market mid-band flip machine (`odcore/entry_coinbase.py`
armed_midband_flips, registry shapes, NAIVE k0, entry held FIXED), mid fills at confirms, $5k
flat, fee columns cb_entry 40 / cb_early 10 / cb_real 8 / cb_scale 3 / kr_mk0 0 (maker-both-
sides; kr taker 10 where taker legs appear). Tapes: 30d x 4-coin Binance spot bins (instrument)
+ Coinbase books (deploy venue; thin — shape only). ETH stays dropped. Controls: reversed,
shuffle, per-week, truncation-invariance leakage.

BASELINE EXIT = flip-at-next-confirm (the promoted machine's own exit; leg = confirm k ->
confirm k+1). CANDIDATE 1 = R8 lean-collapse (`swing_maker` lean_exit=(arm_hi, exit_lo),
with-ride lean armed at arm_hi, closed at collapse to exit_lo; measured basis S55 R8: 765
zz150 exits, ~28bp giveback vs 151bp theta-exit — SCALE-LOCALITY: zz150 numbers do NOT
pre-authorize theta 80/100; that is this round's question).

PER-LEG BUDGET INHERITED (S59): surviving entry configs gross +5.6..+9.3 bp/leg vs 16bp RT
cb_real (deficit -1.4..-4 $/hr); paper-positive at kr_mk0. The exit's job: cut giveback
without killing the winners' tails.

## MISTAKES CAUGHT (append-only; S58 ledger items 1-4 carry — tuple order, mode-0 deadlock,
## thin books, pkill)

(none yet this session)

## ROUND 1a — THE EXIT DUMP + GIVEBACK ANATOMY (dump built, agents pending)

`scripts/_s60_piece2_exitdump.py` — one row per leg of the PROMOTED machine (naive k0, both
thetas, registry flagged), bins (30d) + books, leakage-gated. Registry-cell anatomy:

| cell            |    n | gr/leg |  peak | gvbk | med_gb |  adv | frac_pk | r8(0.10,0) trig/gx |
|-----------------|-----:|-------:|------:|-----:|-------:|-----:|--------:|-------------------:|
| sol_bins_th100  | 1000 |  +2.19 |  67.6 | 65.4 |   52.1 | 42.1 |    0.55 |        0.57 / +3.6 |
| sol_books_th100 |   56 | +22.11 |  85.0 | 62.9 |   51.2 | 43.1 |    0.57 |        1.00 / +3.2 |
| btc_bins_th80   |  700 |  -2.97 |  50.1 | 53.0 |   41.4 | 33.2 |    0.53 |        0.64 / -0.1 |
| btc_books_th80  |   22 | -28.49 |  46.2 | 74.7 |   40.7 | 54.4 |    0.46 |        1.00 / -1.3 |
| doge_bins_th100 |  728 |  +0.84 |  66.4 | 65.5 |   52.0 | 42.3 |    0.54 |        0.65 / +1.6 |
| doge_books_th100|   40 |  +9.29 |  74.7 | 65.4 |   51.6 | 37.9 |    0.49 |        0.97 / +3.5 |
| xrp_bins_th80   | 1090 |  -1.25 |  51.2 | 52.4 |   41.5 | 34.0 |    0.54 |        0.58 / +4.8 |
| xrp_books_th80  |   32 |  +4.14 |  53.6 | 49.5 |   40.8 | 28.6 |    0.60 |        0.97 / -0.3 |

FIRST OBSERVATIONS (leg-slice; machines decide, per playbook rule 1):
1. **The giveback prize is UNIFORM and big:** mean 50-65bp/leg, median ~41-52, at gross +2..+22
   — every cell hands back far more than it keeps. frac_peak ~0.5 = legs ride ~half their
   duration PAST the peak. Sanity: sol_books gross +22.1 reproduces the S59 record exactly.
2. **The naive zz150 R8 config does NOT port to mid-band (scale-locality confirmed):** at
   (arm 0.10, collapse 0.0) on BOOKS it fires on ~100% of legs and exits near-zero gross
   (sol +3.2 vs zigzag +22.1). On BINS it fires 57-65% at exit-now gross ≈ or slightly above
   zigzag on the triggered subset (xrp +4.8 vs -1.25 pooled; NOT same-leg-matched yet).
3. **LEAN-WINDOW WALL-CLOCK CONFOUND (flag for all agents):** WFLIP=600 CELLS = 60s on books
   (0.1s grid) but 600s on bins (1s grid). The books trigger-rate-1.00 vs bins ~0.6 gap is
   partly THIS, not just venue. Bins rows carry slmax60 (60s wall-clock) for the cross-check;
   any deploy read must be defined in WALL-CLOCK terms per venue.

## ROUND 1b — WHERE THE BLEED IS (renders + same-leg trigger match; Greg's question)

Renders: `docs/renders/s60/exit_bleed_<coin>_<venue>.png` (10 worst-giveback legs per registry
cell, price + with-ride-lean strip, R8/dive trigger marks). Tool: `scripts/_s60_exit_renders.py`.

**THE BLEED IS TWO POPULATIONS, not one:**
1. **WRONG-SIDE legs** (= the entire worst-10 giveback board on every cell, both venues):
   entry fires, tiny favorable blip (peak +0..+42bp inside the first ~0-6 min), then under
   water the whole ride to the opposite θ-arm close at ~-θ (gross -64..-115bp). Their
   "giveback" IS the bounded-loss design, not a squandered peak. In the renders the DIVE
   (purple) fires within the first minutes on most of these legs — as a STOP it saves
   60-100bp/leg here.
2. **RIGHT-SIDE legs**: median giveback prints c·θ EXACTLY on all 8 registry cells (40.7-41.5
   at th80, 51.2-52.1 at th100) = the close-side confirm lag — the structural toll of the
   zigzag exit. Mean sits 10-25bp above median = the slow-confirm tail.

**TRIGGER VERDICT (same-leg matched, registry cells):** R8(0.10,0) and dive(-0.30) as PEAK
harvesters FAIL — they fire 61-97% PRE-peak, and their triggered subset has HIGHER zigzag
gross than pooled (sol bins +9.4 vs +2.2) = they select the healthy rides and cut them.
Δ(all-legs): sol -3.3/-18.9(books), doge -3.1/-6.3, xrp -0.8/-4.3 — NEGATIVE. The one
positive: btc +1.3 bins / **+27.2 books** — because btc books legs are mostly wrong-side, so
any early exit beats the -θ death (the STOP role, accidentally demonstrated).
BINS/BOOKS trigger-rate gap (57-65% vs ~100%) is partly the lean wall-clock confound
(600 cells = 600s bins / 60s books) — deploy reads must be wall-clock-defined.

**ROUND 2 SHAPE THIS IMPLIES (split the role, graded per cell):**
(a) close-side trailing retrace tighter than c·θ (price-only, portable — an ASYMMETRIC
    zigzag: entry confirm c=0.5, exit retrace c_x<0.5) → targets the c·θ lag;
(b) the DIVE as an UNDERWATER-ONLY stop (fires only when the leg never armed with-ride /
    sits below entry) → targets wrong-side legs without touching winners.
Both are MACHINE tests (composition changes: extra legs/fees for (a), flat-until-confirm
for (b)) vs the zigzag baseline, all fee columns. Leg-slice numbers above are hypotheses.

## ROUND 1c — THE SIGN-SWAP TESTS (Greg: "the signs are swapped" / "firing in the correct
## spot but the opposite trade") — 5 exit families, leg-slice, bins (books lean saturated)

Greg's reads tested directly. Δa = all-legs delta vs the zigzag exit, bp/leg, registry cells:

| family (exit read)                  | sol   | btc   | doge  | xrp   |
|-------------------------------------|-------|-------|-------|-------|
| R8 collapse (0.10,0)                | -3.3  | +1.3  | -3.1  | -0.8  |
| dive dv30 (opposing -0.30)          | -1.2  | +0.6  | -1.3  | +0.1  |
| dive-as-FLIP corrector (underwater) | -1.6  | +0.4  | +1.9* | -1.1  |
| climax first-cross (sl>=0.3/0.4/0.5)| -1.7  | +1.7  | -1.9  | -0.6  |
| lean-trailing vertex (A,R grid)     | -2.3  | +2.2  | -3.5  | -0.6  |
| PRICE trailing-retrace (X=15-35bp)  | -1.6  | +3.1  | +0.5  | +1.3  |
(* doge dive-flip positive at dv20 only; dv30 negative — fragile)

FINDINGS:
1. **The flow-climax moment IS the right spot (Greg confirmed): exiting at fav@slmax = +18
   to +25bp/leg over zigzag on ALL 4 coins.** But it is hindsight — every causal detector
   tried (first-cross, collapse, trailing-on-lean) fires on earlier lesser climaxes and
   loses on 3/4 coins. The winner's FINAL climax is not causally distinguishable from
   mid-ride climaxes by the lean alone = the entry-side "winners invisible to causal flow
   reads" convergence, now confirmed on the exit side. The +18-25 ceiling is the S35
   fingerprint-tier target, not a threshold-knob target.
2. **BTC is a flow-exit coin: EVERY family is positive on btc_bins** (+0.4..+3.1) — same
   coin whose entry side rewarded flow reads (opposing-mandatory th80). DEFLATIONARY READ
   (must be split by the agents): btc baseline is the worst (-2.97 gr/leg) — on a
   negative-EV cell ANY earlier exit trivially helps; is the lift timing skill or just
   exposure-shrink? Test: does the lift survive on btc's POSITIVE weeks / on the tail
   window where btc k0 turned positive?
3. **The dive-as-flip corrector (blanket, underwater-conditioned) does NOT pay pooled** —
   the machine's entries are dip entries, so early opposing dives are ENTRY NOISE on
   healthy legs; the old side recovers more often than it continues down (flip_gain
   negative on most cells). It pays only where wrong-side legs dominate (btc books +5.1
   dv30). The discriminator wrong-side-vs-entry-noise = an agent question (depth, age,
   never-armed, graded).
4. **SOL: NOTHING beats its zigzag exit** (all families negative) — the lead cell's exit
   is already near-optimal among lean/price threshold reads; its prize sits only in the
   hindsight ceiling. Protect it: any deployed exit read must be per-cell OFF for sol
   until something clears controls.
5. XRP mild positive on PRICE trailing only (+0.5..+1.3) — consistent with its "price
   mechanics only" entry verdict.

## JOB 1 — THE KRAKEN TAPE VERDICT: **THE GROSS EXISTS ON KRAKEN'S OWN PRICES** ✅

`scripts/_s60_kraken_tape_machines.py` — promoted machine (naive k0, venue law: no flow maps)
on the 30d Kraken trade-history bins, all 5 coins x both thetas, leakage gate PASS all tapes.

| cell (REG=registry)   | legs/h | gr/leg | kr_mk0 $/hr | wk+ | tape gap% |
|-----------------------|-------:|-------:|------------:|----:|----------:|
| sol_kraken_mb100  REG |   1.27 |  +4.93 |   **+3.14** | 5/5 |      87.7 |
| doge_kraken_mb100 REG |   0.84 |  +5.01 |   **+2.11** | 3/5 |      96.9 |
| xrp_kraken_mb80   REG |   1.39 |  +0.88 |       +0.61 | 4/5 |      86.7 |
| btc_kraken_mb80   REG |   0.87 |  +0.29 |       +0.12 | 3/5 |      75.6 |
| eth_kraken_mb100      |   0.88 |  +3.90 |   **+1.72** | 3/5 |      86.8 |
| (doge mb80 non-reg    |   1.24 |  +3.15 |       +1.95 | 4/5 |     96.9) |

- Best-per-coin sum ~**+$7.7/hr** @$5k flat on Kraken's OWN tape — confirms and slightly
  exceeds the S59 Binance-instrument estimate (+$6). SOL 5/5 positive weeks.
- **ETH LIVES ON KRAKEN** (+1.72 mb100): per-cell law vindicated — the Coinbase drop never
  pre-judged eth_kraken. New candidate cell.
- **XRP asterisk softens:** mildly POSITIVE on Kraken's own tape (+0.61, 4/5 wk) — the S59
  "negative on bins at 0 fee" was the Binance instrument; Kraken's own prices disagree.
- **STALE-FILL HONESTY CHECK PASS:** median fill-delay 0s (confirms only fire on traded
  seconds by construction); next-trade fill re-score identical to the cent. The 76-97%
  gap% is idle seconds, not stale decisions.
- **TIER LADDER IS LOAD-BEARING:** at kr_mk2 most cells go negative — the $10M/30d 0bp
  tier is the whole game (known; the paper cadence clears it only while running).
- STILL UNKNOWN (b): do maker quotes FILL at Kraken volume? Books accruing (first cron
  tick due 00:00Z; 0 runs at 00:19 check — GitHub cron delay is normal, re-check).

## ROUND 2 — PER-COIN EXIT AGENT VERDICTS (falsification duty enforced)

**BTC — NOTHING EARNED; round-1 "flow-exit coin" is DEAD (exposure-shrink, not timing).**
Killed 4 ways: (1) winner/loser decomposition — every family's lift = loser-truncation that
DAMAGES winners (R8: losers +22.1, winners **-19.5**; fires 88% pre-peak on winners, captures
median 10% of the peak); (2) regime split — all lifts flip NEGATIVE where baseline is
positive (wk3, day>=20 tail, th100 tail) + mechanical-shrink accounting closes the books
(expected +2.4 from exposure cut alone ~= +3.2 observed); (3) blind time-exit control —
exit @75% of dur (+4.79) BEATS the best causal config (+1.68): "a read that loses to a
kitchen timer is not a read"; (4) top-3-excluded kills the dive family (+0.56 -> +0.21);
books +27.2 was ONE -494bp leg (+4.8 without it, n=21). Side-asymmetric too (all lift on
side +1; side -1 negative). VERDICT: keep zigzag exit; anti-print carried — never wire
R8/dive on btc as harvest reads; bnc25 fallback candidate unaffected (fallback legs
untouched by every trigger; theta-deaths are 98% confirm-kind).
Giveback fingerprint: runners and diers BOTH print the c*theta=40 toll exactly (med 40.9 vs
41.0) — the dier's peak (44bp) barely clears the toll, the runner's (109bp) outruns it;
entry-time features IDENTICAL (S58 "winners invisible" law confirmed exit-side on btc).
Wrong-side discriminator: none with lead time (depth>30bp = 83% death but the info arrives
after the money is gone; the 10-30bp decision band is a coin flip).

## SESSION LOG (append per round)
- 22:3x Z: branch reconciled (S60 designated branch was cut from default/crons AGAIN — third
  session running; reset --hard to canonical 396d534, pushed).
- 22:4x Z: Kraken 30d backfill x5 launched sequential (/tmp/kraken_backfill, SOLUSD first).
  Binance 30d bins x5 launched parallel (/tmp/binance_bins). Coinbase books x5 restored from
  data branches (btc 47MB / doge 23MB / eth 53MB / sol 51MB / xrp 36MB).
- 22:5x Z: scrap-heap miners A (S38-S52 handoffs + strategy docs) + B (S53-S59 + code sweep)
  launched in parallel, exit charter per playbook.
- Kraken book collectors: 0 runs (expected — cron ticks 00/06/12/18Z; landed 22:01Z).
