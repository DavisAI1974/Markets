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

**SOL — zigzag exit CONFIRMED near-optimal for winners + the round's FIND: the ARMED-BEFORE
wrong-side discriminator.**
(1) Winners' excess giveback over the c*theta toll is TINY: mean +1.8 / med +1.3 / p90 +3.9bp,
zero legs under 0.35*theta — ~96% of winner giveback IS the structural toll; there is nothing
for a detector to harvest (why every family failed). The +25.2 ceiling stays S35-tier.
(2) **THE FIND — flow-confirmed failure:** among underwater dive-triggered legs, whether the
with-ride lean had ALREADY ARMED (>=+0.10) earlier splits deaths from recoveries: ARMED =
death 0.63-0.84, save +14..+15bp/leg; unarmed = entry noise, save NEGATIVE -13..-18 (old side
recovers). Sign-consistent 12/12 config strata + 9/9 depth-x-age strata (not an age/depth
proxy); stratified permutation z=+2.39/+3.49. Story fits S58: a dip that GOT its flow and is
still underwater when the opposing dive lands = confirmed failure.
(3) Proposed machine test: UNDERWATER ARMED-DIVE STOP (arm 0.10 / dive -0.30 / uw -10bp /
600s wall-clock), expected +0.6-0.9 gross bp/leg (halves + quartiles stable, trigger ~5%).
**Standing objection (agent's own): a dumb price stop X=40 BEATS it at th80 (+1.11 vs +0.63)
— the machine must run BOTH arms; the lean conditioning hasn't earned its complexity yet.**
(4) Anti-prints: pooled r8/dive/climax/lean-trailing; in-profit dives (dv40 at gx 10-40:
-50.8); unarmed underwater stops. Books shape-consistent (n=4-6, wall-clock caveat).
(5) Flag for dump builder: every sub-toll-giveback leg is a SHORT (longs 100% big-giveback
both thetas) — check confirm/giveback accounting asymmetry (~10-15bp on 8-17% of shorts).

**DOGE — one config earned a machine test: the CASCADE-JOIN FLIP (BUY-only).**
Config: BUY legs only — first PURE dive (lean_600s-wall <= -0.30, NO arm) while leg >= 20bp
underwater -> FLIP to SELL immediately (join the cascade). Leg-slice: **th100 +1.95 (t=+2.36),
th80 +1.05 (t=+2.01, ALL 4 quarters positive), pooled +1.41 over 1,820 legs**; fee-neutral
(moves the transition earlier, same count); fires median 0.37 of leg = ~28min exit-lag cut.
Beat the side-bet null DECISIVELY at th80 (reverse-all-BUY -0.11, unconditioned flip -0.97,
conditioned +1.05 4/4 quarters); top-3-excluded +1.35/+0.74; cross-theta convergent.
Stop-variant (flat not flip) = half the edge (+0.98/+0.52) — machine tests BOTH arms.
- Round-1 dv20 +1.9 RECLASSIFIED ARTIFACT (U=0 side-pooled regime bet; quarters decay).
- **Cascade-mark INVERTED:** deep+early opposing dive marks WINNERS (entry noise absorbed);
  the killing cascade arrives MID-leg. The mark is the CONJUNCTION (dive & >=20 underwater):
  death rate 2x (49-56% vs 24.6% base). BUY dies 28.6% vs SELL ~20% both thetas (S58
  cascade law reproduces exit-side: DOGE dumps cascade, pumps fade).
- **Exhaustion-at-top: NULL on DOGE** — winners' giveback is 51.6-52.0 (= c*theta) across
  ALL clmx/slean grades; the toll is flow-blind. DOGE rewards exit flow ONLY as loser's
  cascade confirmation, never as winner's exhaustion. Winners-invisible law: 3/3 coins now.
- Fallback legs NEVER theta-die (0/409 both thetas) — deaths are confirm-kind (matches btc).
- BOOKS UNRESOLVED: dump's books lean = 60s wall-clock (confound) — **ACTION: re-dump books
  with 600s wall-clock lean (6000 cells) before any books shape-check** (SOL flagged same).
- Deflationary (stands): edge = 27 deaths saved vs 5 winners killed (th100); breakeven ~9-10
  killed winners/39 corrections; if the 30d window is meme-cascade-rich the edge shrinks —
  per-week machine splits + accruing tape are the arbiter.

**CROSS-AGENT CONVERGENCE (playbook rule 5, isolated agents):** SOL and DOGE independently
landed on the same STRUCTURE — opposing dive while underwater = flow-confirmed failure ->
act (SOL: exit flat, armed-before conditioned; DOGE: flip, BUY+depth conditioned). Neither
found a peak harvester; all three coins' winners are flow-invisible post-peak. The exit
edge, where it exists, is a WRONG-SIDE CORRECTOR.

**SOL-agent BTC RECHECK (Greg: "use the good pieces, leave the bad"):**
(1) **The armed-before discriminator REPRODUCES on BTC** — 4/4 cells, perm z +2.1..+3.0,
armed>unarmed in every regime split, real lead time (~15-29min). Cross-coin structural:
8/8 cells (SOL+BTC) with independent nulls. The BTC agent's "no causal discriminator" is
AMENDED: armed-before is one. BUT as a deployable stop at registry th80 it FAILS the strict
tail bar (all-legs -0.24 tail, wk3 -0.96; armed death-precision degrades 0.75->0.47 in the
healthy regime). th100 passes the full battery (+2.47 all-legs, tail +0.62) = robustness
file, not deploy. (2) **The surviving BTC piece is the DUMB one: plain price stop X=50 at
th80** — +2.0..+3.2 all-legs, TAIL-ROBUST (+2.6-2.7 where base is +3.23 = NOT exposure
shrink), 5/5 weeks, both sides, ex-top3, winner-cheap (-4.5). Taker-fee exposure at 29%
trigger rate = the fee-sensitive arm (kr_mk0 unaffected). Blind-timer arm still owed in
the machine. (3) Per-cell law in EXIT space: SOL wants the armed-conditioned stop (plain
stop half-fragile there), BTC wants the plain stop (armed stop tail-fails) — same
information, opposite deploy shapes.

**XRP — NOTHING EARNED (decisive kill of round-1's own lead).** The price-trailing +1.3 =
exposure-shrink artifact: week-corr(baseline health, lift) = **-0.89**; H2 sign-flips; a
brainless fixed-T time-cap reproduces it without price info; 92% of winner legs amputated
pre-peak (wealth transfer, not harvest); th100 no support; **books sign-flip on every X**
(no wall-clock confound on price reads = genuine venue divergence — the S59 bins-divergent
asterisk now covers the EXIT side). Death-combo exit analog (deep dive + never armed =
-30.6/leg, 49% death) is REAL AS A LABEL, sign-stable both halves — but causally
unharvestable (loss front-loaded before the mark confirms). Verdict: zigzag exit stands;
**XRP stays OFF in any pooled exit machine config** (never promote off bins alone on XRP).

## THE ROUND-2 EXIT BOARD (all 4 agents + recheck, falsification enforced)

| coin | exit verdict | machine test owed |
|------|--------------|-------------------|
| SOL  | armed-dive underwater stop (+0.6-0.9 exp.) | vs plain-stop null (X=40/50) — both arms |
| BTC  | plain price stop X=50 th80 (+2.0-3.2, tail-robust) | vs blind 75%-timer + taker-fee arm |
| DOGE | cascade-join FLIP, BUY-only (+1.95/+1.05) | vs flat-stop variant — both arms |
| XRP  | NOTHING — zigzag stands | none (keep OFF) |

**ROUND LAWS (cross-agent convergence, isolated agents):**
1. NO PEAK HARVESTER EXISTS on any coin — winners' post-peak giveback = the c*theta toll,
   flow-blind, printed identically by runners/diers on all 4 coins. The +18-25bp ceiling
   at the true flow-climax is hindsight = S35 fingerprint-tier, not knob-tier.
2. The only exit edge family = the WRONG-SIDE CORRECTOR (Greg's "correct spot, opposite
   trade") — and its deploy shape is PER-CELL (sol conditioned-stop / btc plain-stop /
   doge flip / xrp off).
3. ARMED-BEFORE (flow showed up, still underwater) = real cross-coin information, 8/8
   cells — even where not deployable. Fingerprint-tier input.
4. Theta-deaths are CONFIRM-kind; fallback legs never theta-die (doge 0/409; btc 98%).
5. The bins->books divergence law extends to the EXIT side (xrp sign-flips everywhere).

## ROUND 3 — THE MACHINES (`scripts/_s60_piece2_exit_machines.py`; bins + Kraken-tape race;
## mid fills; fee cols incl. stop-as-taker sensitivity; per-week; 3-seed shuffle floor)

BINANCE BINS (registry cells; d = kr_mk0 $/hr delta vs zigzag; shuf = the arm's delta on
return-permuted tapes — the structure-free floor):
- **SOL: armed_stop d-0.49 (live) vs shuffle +0.54 — BELOW its own floor. DEAD.** plain40/50
  also negative. SOL EXIT VERDICT FINAL: zigzag stands, no exit read, both venues (on the
  Kraken tape armed_stop costs -1.85 and 5/5wk -> 2/5wk). The lead cell stays untouched.
- **DOGE: cascade_flip = the machine winner on the instrument** — kr_mk0 +0.42 -> +2.66
  (d+2.24 vs shuffle +1.14 = **structure premium ~+1.10/hr**), 5/5 weeks, survives
  stop-as-taker (+1.86), beats the flat-stop arm on live AND premium. cb_real still negative
  (-5.42) — this is a KRAKEN/low-fee-frame result.
- BTC: plain40 d+1.23 vs shuffle -0.17 (real premium) BUT the cell stays negative at kr_mk0
  (-0.21 best) — the stop shrinks the bleed, doesn't turn the cell. Rider only; btc gated.
- Timers ~0 (blind-timer null arm properly loses — the btc stop premium is not a timer).

KRAKEN TAPE (cross-venue port test, flagged as such — venue law):
- **DOGE flip adds $/hr on Kraken too (+2.11 -> +3.28, 4/5wk, taker-robust +2.27) BUT its
  live delta (+1.17) does NOT exceed its Kraken shuffle floor (+1.31) — structure premium
  ~0 on Kraken.** The lift there is the mechanical/drift component (shuffle preserves net
  drift; BUY-only bail harvests a down window on any tape). VENUE LAW HOLDS: the flip is
  VALIDATED-ON-INSTRUMENT (Binance premium +1.10), UNVALIDATED on Kraken — needs its own
  per-venue pass as tape accrues. Do NOT deploy on Kraken cells yet.
- BTC plain40 on Kraken: +0.12 -> +1.03, 4/5wk, premium ~+1.1 — real-looking but
  taker-stop kills it (-0.51) and btc stays gated; parked as rider pending fill reality.
- ETH flip: negative (-0.66) — the cascade read is DOGE-specific, per-cell law again.
- SOL/XRP: zigzag only, confirmed.

**PIECE 2 ROUND-3 BOTTOM LINE:** the exit piece's earned content this round = (1) the DOGE
cascade-join flip, instrument-validated at ~+1.1/hr structure premium (deploy-gated on its
own Kraken/books pass); (2) hard NULLS that protect the winners (SOL/XRP untouched; no peak
harvester exists — that prize is S35 fingerprint-tier); (3) the armed-before cross-coin
information (8/8 cells) filed for the fingerprint thread. The zigzag exit remains the
deploy exit everywhere; nothing wires into the platform this round (sandbox rule: a DOGE
flip sandbox cell is the natural next promotion candidate AFTER a books-frame check).

## ROUND 3b — CROSS-POLLINATION MATRIX (Greg: "see if the pieces fit the other coins")

All 6 pieces x all 4 registry cells, Binance bins, prem = liveD - shuffle floor ($/hr kr_mk0):

| piece \ cell    | sol_mb100 | btc_mb80 | doge_mb100 | xrp_mb80 |
|-----------------|----------:|---------:|-----------:|---------:|
| cascade_flip(BUY)|    -1.59 |    +0.37 |  **+0.90** |    +0.33 |
| cascflip_SELL   |     -0.29 |    +0.42 |      -0.74 |    -0.64 |
| cascflip_both   |     -1.88 |    +0.80 |      +0.16 |    -0.31 |
| plain40         |     -1.97 | **+1.30**|      -0.29 |    -1.37 |
| plain50         |     -0.31 |    +0.77 |      +0.16 |    -1.09 |
| armed_stop      |     -0.89 |    +0.38 |      -0.89 |    -0.38 |

**THE ASSIGNMENT MATRIX IS DIAGONAL:** sol = NONE (every piece negative-premium — the lead
cell rejects all exit reads); btc = plain40 only (price-stop coin; cell still negative =
rider); doge = BUY-flip only (its SELL mirror is NEGATIVE -0.74 — the cascade asymmetry is
real and DIRECTIONAL: doge dumps cascade, pumps fade; side-blind dilutes to +0.16); xrp =
none (all noise-or-negative). The pieces do NOT cross-pollinate — per-cell law in its purest
print yet. No new machine candidates from the matrix; the round-3 verdicts stand unchanged.

## VENUE FRAME OF THE EXIT ROUND (Greg's check: "agents were looking for Coinbase exits?")
Honest answer: NO — the exit verdicts are INSTRUMENT-frame (Binance bins); Coinbase books
were shape-checks only (22-56 legs/cell, too thin to grade; S58 convention). The DOGE flip
is a FLOW read -> venue law applies: it does NOT port to the Coinbase deploy without an
accrued-books pass (same bar as the entry flow maps), and at cb_real 8bp the doge cell is
net-negative even with it (-5.42) — its value frame is kr_mk0. Coinbase books shape check
(wall-clock re-dump): flip condition fires 2-3/cell, EVERY fired leg a genuine death
(zigzag -62..-89), deltas +21..+103bp/leg — direction agrees, n=anecdote. Trigger
saturation fixed (100% -> 52-68%). VALIDATION PATHS: Coinbase = books accrual (dumps now
unconfounded); Kraken = books + more tape (shuffle-floor fail stands until then).

## ⭐ FOCUS DIRECTIVE (Greg, S60 mid-session — supersedes the round-3 framing)
**WE ARE FIXING THE COINBASE EXIT STRATEGY. Everything else HALTED** except already-running
background work. The exit fleet re-launched with COINBASE-frame charters: grade ON the
Coinbase books (registry cells, cb_real 8bp frame, the sandbox deploy reality); bins =
secondary support only. **DO NOT PUSH exit-fix work until Greg clears it** (local commits
only). **PARKED FOR LATER (Greg): KRAKEN EXITS** — the whole Kraken exit analysis (incl.
the shuffle-floor question on the DOGE flip, the btc plain40 Kraken premium, and any
eth_kraken exit work) waits until the Coinbase exit is fixed; Kraken books accrual
continues in the background meanwhile.

## ROUND 4 — COINBASE EXIT FIX (books-first, cb_real frame; Greg's focus directive)

**XRP — "the cell's problem is NOT the exit" (decisive decomposition).** The -11.86 net/leg
= **-16.00 fees on +4.14 gross**; winner giveback is -26.7 of which -26.3 is the structural
c*theta toll (excess over toll: +0.70bp med, max +1.23 — the toll law now prints 4/4 coins
BOTH venues). Death-side ceiling: a PERFECT oracle stop on all 11 deaths only lifts net to
+4.3 — the entire theoretical exit prize barely crosses zero at cb_real; realistic reads
get +3..5 -> cell stays -7..-9. **The fix is fee-tier / entry-side / venue-shaped, not
exit-shaped.** Keep zigzag; XRP stays OFF exit configs (round-2 re-confirmed on books).
- Toll law on books: winners' giveback med 40.7 vs c*theta=40 EXACT; deaths close AT their
  lows (adverse == |gross| leg-by-leg, both venues); books deaths discoverable ~12min in
  (vs 2min bins — venue timing divergence, don't build on it yet).
- **Death-combo label DOES NOT EXIST on Coinbase books:** 97% of books legs arm (slmax med
  0.600 vs bins 0.275) — the never-armed state is not something the Coinbase feed produces;
  the label is bins-only as defined. VENUE-RECALIBRATE thresholds before any books use.
- One parked hypothesis: **underwater deep-dive corrector** (dv40 + >=10bp underwater) —
  the cross-coin wrong-side structure appearing on XRP books (th80 +2.80, th100 +10.90,
  beats the plain-stop null which kills winners) — but 4-6 fired legs inside a 41-cell
  search on n=32; NAMED, NOT DECIDABLE. Re-grade bar: **150+ th80 book-legs across >=2
  distinct weeks (~5x current tape)**; and even clearing it (+3/leg) does not rescue
  cb_real economics — corrector rider, not the cell's fix.

**BTC — READINESS VERDICT (Coinbase-frame agent): the -28.49 books gross is 78% ONE
COLLECTOR-GAP ARTIFACT LEG; activate btc_mb80 into SANDBOX with the plain stop attached
DAY ONE as taker-accounted variant arms.**
- Gap anatomy: leg 18 (entry t=45.33h, dur 145.1h, gross -494.34) spans the 155h gap era
  exactly (ends 190.44h = era-B start) — the bounded-loss fallback (~-80) cannot fire on a
  stalled tape. Market-evidence mean = **-6.31 (n=21, se 13.2, 95% CI [-32.7, +20.1])** —
  indistinguishable from bins -2.97, from 0, and from -16. Effective live tape ≈ 51h (era A
  0-45.3h: 19 legs; era B 190.4-196h: 3 legs), not 196h. Normal -80 death instead: mean -9.66.
- Anatomy n=22: wrong-side 8/22 = 36.4%±10.3 (bins 28.7%); right-side n=14 median giveback
  40.22 = c*theta toll EXACT (toll law: btc books consistent with the 4/4-coins print);
  winners 10/22 mean +43.0; only 5/22 clear cb_real 16 RT.
- Stop X leg-slice on books EX-GAP (hypothesis-tier; theta-death saves are mechanical):
  X=40 trig 8/21 (38%) +6.03/leg, 1 winner-kill (-49.7); X=50 trig 7/21 (33%) +2.29/leg.
  Only 1 of 14 right-side legs ever crossed -40 → books adds RATE evidence only. The gap
  leg is NOT creditable to a tape-graded stop (no cells to fire on) — but a LIVE
  exchange-side stop would have fired (the market didn't gap; our collector did). OPS BAR
  FOR ACTIVATION: staleness kill-switch / resting exchange-side stop.
- **Taker term quantified (cb_real, stop leg 16 vs 8):** breakeven taker share X=40 = 112%
  bins / 198% books-ex-gap (fee-safe at 100% taker, +0.35 bins residual); X=50 = 87% / 86%.
  A Coinbase protective stop is structurally TAKER → X=40 is the only self-funding arm at
  full taker; at full taker + 2bp slip both arms ≈ 0 mean — the stop's earned value is
  TAIL-SHAPE (kills -80s), not mean. Run BOTH arms, books decide.
- Accrual bars (gap-free legs, t=2): disaster screen |16bp| ≈ 57 legs (~5-6d @0.42/h);
  stop verdict ≈ 261 (X=40) – 389 (X=50) legs (~4-6 wks); gross-vs-0 at bins scale (3bp,
  sd 60.6) ≈ 1,700 legs (~6 months) — books will NEVER certify the small positive; that
  stays the instrument's job. Sequential naive-first costs 4-6 weeks of calendar for zero
  information (sandbox arms are free; flat-until-confirm, no composition interference).
  ACTIVE ≠ capital: the stop is a rider; the cell is negative at every fee column.
- Claimable at n=22: mechanics grade end-to-end on books; toll prints; headline is
  artifact-dominated; wrong-side rate ~ bins; 1 winner-kill observed. NOT claimable: any
  books gross/net verdict, weekly stability, side/hod splits, books stop-lift magnitude,
  or "books worse than bins."

**DOGE — Coinbase bleed = 43% deaths / 57% structural toll+fees; cascade-join flip spec'd
as the SANDBOX VARIANT (not wired; ledger decides).**
- Books anatomy (n=40 reg + 60 th80): deaths 11/40 @ -87.0 gross = -23.9bp/leg drag (43.1%
  of giveback); winners' excess-over-toll +1.46/+1.05 (no-harvester law on books); deaths
  28/28 confirm-kind; deaths side-BALANCED on books (BUY-only comes from the instrument's
  cascade asymmetry, not death counts).
- Flip on books: 2 registry fires, both genuine deaths (different moves), delta +102/+104
  each; +5.14/leg face [n=2 — bootstrap floor artifact]; th80 semi-independent +1.04 (4
  saves/1 kill). UNDERWATER GATE LOAD-BEARING (uw=0 arm flips a +335 winner for -677).
  dv40 = first books winner-kill (-105). Flat-stop = half the flip (2:1, matches bins).
  SELL-side: books + / bins - on 1,820 legs -> BUY-only stands, SELL shadow-logged.
- **SANDBOX SPEC `doge_coinbase_mb100_cascflip`:** entry identical; BUY only; first
  lean_600s-WALL <= -0.30 (pure dive, no arm) AND leg <= -20bp -> FLIP (fee-neutral).
  Shadow: flat-stop, SELL fires, plain40, taker-fill scoring. Accrual bar ~30 fires
  (~580 th100 legs; 14-34d pooled w/ th80 shadow); stand-down: per-fire mean<0 after 10
  fires OR 3 winner-kills before 3 saves.
- HONEST CEILING: flip does NOT turn the cell at cb_real (books face -6.71 -> -1.56;
  instrument expectation nearer -5). Same conclusion as XRP: the residual gap is
  toll+fee-shaped — asymmetric exit retrace (c_x<c) is the one toll-attacking mechanic
  not yet machine-tested; fee tier is the bigger lever.

## SESSION LOG (append per round)
- Kraken book branches: still 0 at 0x:xx Z (post-00:00Z tick) — cron delay or first-run
  failure; CHECK the Actions tab / re-check next round; Greg's Run-workflow click still
  the fast path.
- 22:3x Z: branch reconciled (S60 designated branch was cut from default/crons AGAIN — third
  session running; reset --hard to canonical 396d534, pushed).
- 22:4x Z: Kraken 30d backfill x5 launched sequential (/tmp/kraken_backfill, SOLUSD first).
  Binance 30d bins x5 launched parallel (/tmp/binance_bins). Coinbase books x5 restored from
  data branches (btc 47MB / doge 23MB / eth 53MB / sol 51MB / xrp 36MB).
- 22:5x Z: scrap-heap miners A (S38-S52 handoffs + strategy docs) + B (S53-S59 + code sweep)
  launched in parallel, exit charter per playbook.
- Kraken book collectors: 0 runs (expected — cron ticks 00/06/12/18Z; landed 22:01Z).
