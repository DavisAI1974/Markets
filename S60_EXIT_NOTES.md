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

## SESSION LOG (append per round)
- 22:3x Z: branch reconciled (S60 designated branch was cut from default/crons AGAIN — third
  session running; reset --hard to canonical 396d534, pushed).
- 22:4x Z: Kraken 30d backfill x5 launched sequential (/tmp/kraken_backfill, SOLUSD first).
  Binance 30d bins x5 launched parallel (/tmp/binance_bins). Coinbase books x5 restored from
  data branches (btc 47MB / doge 23MB / eth 53MB / sol 51MB / xrp 36MB).
- 22:5x Z: scrap-heap miners A (S38-S52 handoffs + strategy docs) + B (S53-S59 + code sweep)
  launched in parallel, exit charter per playbook.
- Kraken book collectors: 0 runs (expected — cron ticks 00/06/12/18Z; landed 22:01Z).
