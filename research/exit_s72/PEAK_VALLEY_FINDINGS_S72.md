# PEAK/VALLEY EXHAUSTION FINDINGS (S72) — descriptive, per-cell, per-leg distributions
Segment the tape by the PRICE's own zigzag peaks/valleys; measure with-trade order-flow
imbalance ('exhaustion') AT the price turns. with-flow signed by swing direction.
LEAD test = flow-hump position within the leg (0=start extreme, 1=the turn); <0.5 would
mean flow flattens BEFORE the price turn = LEADS = catchable. 4 groups on the SWINGS:
short/long = swing duration vs median; winner/loser = swing magnitude vs 20bp fee floor.

## VERDICT — NULL: no consistent leading exhaustion tell at the price turns

Across ALL 5 cells (btc/eth/sol/xrp/doge), ALL 3 thetas (10/20/40bps), and ALL 4 groups, the
with-trade order-flow imbalance ('exhaustion') shows NO consistent, LEADING signature at the
price peaks/valleys. The thesis 'exhaustion marks the top/bottom so we can catch it' is NOT
supported at this flow resolution on the Kraken book data.

- LEAD: the flow-hump position within a swing is ~0.5 of the leg everywhere (per-cell medians
  0.40-0.66, pooled ~0.54) = RANDOM. Flow does NOT flatten before the price turn. (An earlier
  raw-argmax metric produced huge fake 'leads' of hundreds-to-thousands of seconds; those were
  artifacts of a saturated signal, corrected here with swing-proportional smoothing.)
- EXHAUSTION: with-flow is weaker in the 2nd half of the swing in only 33-46% of legs (~40%,
  BELOW a coin flip) — if anything the with-flow tends to be STRONGER approaching the turn, the
  opposite of exhaustion. At the turn itself with-flow is still mildly WITH-trend (median
  +0.08..+0.23), and flow has 'turned against' the swing in only ~13-44% of legs.
- 4 GROUPS DO NOT SEPARATE: short/long x winner/loser show statistically indistinguishable
  wf_turn, hump position, and exhaust% (e.g. long-winner vs short-loser within a cell differ by
  noise only). The big fee-CLEARING swings — the ones we want to catch — have no cleaner or more
  leading exhaustion tell than the small sub-fee swings. This is the opposite of how the entry
  archetypes separated.
- ONLY consistent asymmetry: wf_turn is more positive at PEAKS (+0.14..+0.42) than at VALLEYS
  (~0.0..-0.05). That is a Kraken retail BUY-flow baseline bias (buy volume > sell volume on
  average), present at every peak regardless of what price does next — NOT a turn/exhaustion tell.
- ROBUSTNESS across theta: identical null at 10/20/40bps; not a theta artifact.
- Fee-floor winner cut at theta=20: since the zigzag already keeps only swings >= theta, at
  theta=20 essentially every leg is a '>=20bp winner' -> short/long-LOSER groups are empty (n=0);
  the MEDIAN-SIZE winner/loser cut is the informative one and it too shows no separation.

CORRELATION / PRECISION (the decisive two-directional test):
- CORR#1 P(exhaustion SPENT | price turn) = 24-73% across cells/thetas, clustered ~45-60% =
  roughly a COIN FLIP. Turns are NOT reliably marked by a spent/reversed exhaustion state.
- CORR#3 per-leg corr(exhaustion curve, price curve across the swing) = median +0.03..+0.18
  (~+0.1) = near-zero, and the small positive sign means flow runs mildly WITH the price move,
  not the against/rolling-back pattern exhaustion would require.
- CORR#2/#4 flow-flip (60s-imbalance sign flip) as a turn-caller: PRECISION is ~equal to the
  random BASE RATE (lift x1.0-x2.5, absolute precision low: e.g. ~20-49% at +/-60s on the denser
  coins) because flow flips CONSTANTLY — 1300-1800 flips vs only tens-to-hundreds of real turns —
  so it fires everywhere, not specifically at turns. High RECALL (50-86%) is a saturation
  artifact (with that many flips, every turn has one nearby by chance). Median matched LEAD is
  NEGATIVE (-1..-18s) on 4 of 5 cells = the flow flip LAGS or coincides with the price turn, it
  does NOT lead it. => no specific, leading, catch-the-top/bottom signal.
- These four correlation views ALSO fail to separate the 4 swing groups (P(spent|turn) and
  corr are indistinguishable across short/long x winner/loser).

ROOT CAUSE (data reality, diagnosed): Kraken trades are extremely sparse — only ~1.7% (btc) down
to ~0.2% (doge) of 0.1s cells carry a trade — so rolling_imb(20s) saturates to a +/-1 square wave
(btc: 53% of cells |flow|>0.95). The with-trade imbalance simply does not carry a coherent
onset->exhaustion arc over these multi-minute fee-floor price swings.

IMPLICATION: this specific 'book-only 20s order-flow imbalance marks the price turns' tell is not
present in the Kraken book at these resolutions. Catching the exact top/bottom via exhaustion
would need either (a) a denser trade tape (a higher-volume venue/feed or aggregated cross-venue),
or (b) a different exhaustion proxy (book depth/pressure, trade-size decay, or price
microstructure) rather than the sparse 20s trade-imbalance. Plots (per cell, individual swings,
no trade-exit-price) visually confirm the noise: /tmp/kbook/<coin>_peak_valley_groups.png.

## btc_kraken  (1507773 cells, 41.9h)
### theta=10bps — 144 legs (72 up->peak, 72 down->valley); clean-hump legs=114 (79%)
- median swing: dur=695s  size=20.4bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.56  IQR[0.32,0.82]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 39% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.133 (0=balanced, +1=still fully with-trend); returned-fraction median=0.44 (1=fully rolled back); flow-turned-against-swing-at-turn=31%
- CORR #1 P(exhaustion SPENT | price turn)=47% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.13  IQR[+0.01,+0.25] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=6% vs base 6% (lift x1.01); RECALL P(flow-flip|turn)=50%; median lead=-5s (>0=leads); 1791 flow-flips vs 145 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=12% vs base 12% (lift x1.02); RECALL P(flow-flip|turn)=79%; median lead=-13s (>0=leads); 1791 flow-flips vs 145 turns
- asymmetry: up->PEAK hump_pos=0.50 wf_turn=+0.278 exh=40% | down->VALLEY hump_pos=0.56 wf_turn=+0.056 exh=38%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.55/35%  mid=0.61/31%  high=0.50/50%  [low<= 475 < mid <= 1160 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.58/38%  mid=0.56/35%  high=0.52/44%  [low<= 15 < mid <= 26 < high]
### theta=20bps — 46 legs (23 up->peak, 23 down->valley); clean-hump legs=31 (67%)
- median swing: dur=2775s  size=38.2bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.53  IQR[0.27,0.87]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 39% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.232 (0=balanced, +1=still fully with-trend); returned-fraction median=0.36 (1=fully rolled back); flow-turned-against-swing-at-turn=13%
- CORR #1 P(exhaustion SPENT | price turn)=28% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.05  IQR[-0.00,+0.13] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=2% vs base 2% (lift x1.07); RECALL P(flow-flip|turn)=53%; median lead=-6s (>0=leads); 1791 flow-flips vs 47 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=4% vs base 4% (lift x1.03); RECALL P(flow-flip|turn)=83%; median lead=-17s (>0=leads); 1791 flow-flips vs 47 turns
- asymmetry: up->PEAK hump_pos=0.68 wf_turn=+0.283 exh=39% | down->VALLEY hump_pos=0.36 wf_turn=+0.127 exh=39%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.46/47%  mid=0.53/38%  high=0.71/33%  [low<= 1617 < mid <= 3584 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.55/47%  mid=0.43/38%  high=0.68/33%  [low<= 31 < mid <= 44 < high]
### theta=40bps — 17 legs (8 up->peak, 9 down->valley); clean-hump legs=13 (76%)
- median swing: dur=6565s  size=56.2bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.40  IQR[0.21,0.71]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 41% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.170 (0=balanced, +1=still fully with-trend); returned-fraction median=0.42 (1=fully rolled back); flow-turned-against-swing-at-turn=18%
- CORR #1 P(exhaustion SPENT | price turn)=24% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.03  IQR[+0.02,+0.08] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=1% vs base 1% (lift x1.33); RECALL P(flow-flip|turn)=50%; median lead=-2s (>0=leads); 1791 flow-flips vs 18 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=2% vs base 1% (lift x1.21); RECALL P(flow-flip|turn)=83%; median lead=-8s (>0=leads); 1791 flow-flips vs 18 turns
- asymmetry: up->PEAK hump_pos=0.43 wf_turn=+0.229 exh=50% | down->VALLEY hump_pos=0.32 wf_turn=+0.096 exh=33%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.54/33%  mid=0.32/40%  high=0.42/50%  [low<= 3566 < mid <= 7837 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.36/67%  mid=0.68/40%  high=0.42/17%  [low<= 53 < mid <= 75 < high]

### 4-GROUP breakdown (theta=20bps, 46 legs)

**Cut: WINNER = swing >= 20bp fee floor**  (short/long split at median dur 2775s)
- short-winner:
  n=  23 | P(exhaustion SPENT | turn)=43% | exhaustion-at-turn: wf_turn med=+0.225 (0=balance) returned med=0.44 (1=rolled back) flow-turned-against=22% | per-leg corr(flow,price) med=+0.08 | LEAD: flow-hump position med=0.53 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=48% (50=coinflip)
       peak/valley: PEAK(n=11) hump_pos=0.53 wf_turn=+0.283 exh=55% | VALLEY(n=12) hump_pos=0.50 wf_turn=+0.128 exh=42%
- long-winner:
  n=  23 | P(exhaustion SPENT | turn)=13% | exhaustion-at-turn: wf_turn med=+0.238 (0=balance) returned med=0.35 (1=rolled back) flow-turned-against=4% | per-leg corr(flow,price) med=+0.05 | LEAD: flow-hump position med=0.52 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=30% (50=coinflip)
       peak/valley: PEAK(n=12) hump_pos=0.73 wf_turn=+0.305 exh=25% | VALLEY(n=11) hump_pos=0.32 wf_turn=+0.127 exh=36%
- short-loser: n=0 (too few)
- long-loser: n=0 (too few)

**Cut: WINNER = swing >= median size (38bp)**  (short/long split at median dur 2775s)
- short-winner:
  n=   3 | P(exhaustion SPENT | turn)=33% | exhaustion-at-turn: wf_turn med=+0.278 (0=balance) returned med=0.50 (1=rolled back) flow-turned-against=0% | per-leg corr(flow,price) med=+0.05 | LEAD: flow-hump position med=0.64 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=67% (50=coinflip)
- long-winner:
  n=  20 | P(exhaustion SPENT | turn)=15% | exhaustion-at-turn: wf_turn med=+0.217 (0=balance) returned med=0.35 (1=rolled back) flow-turned-against=5% | per-leg corr(flow,price) med=+0.05 | LEAD: flow-hump position med=0.43 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=30% (50=coinflip)
       peak/valley: PEAK(n=11) hump_pos=0.72 wf_turn=+0.275 exh=27% | VALLEY(n=9) hump_pos=0.32 wf_turn=+0.113 exh=33%
- short-loser:
  n=  20 | P(exhaustion SPENT | turn)=45% | exhaustion-at-turn: wf_turn med=+0.204 (0=balance) returned med=0.43 (1=rolled back) flow-turned-against=25% | per-leg corr(flow,price) med=+0.09 | LEAD: flow-hump position med=0.50 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=45% (50=coinflip)
       peak/valley: PEAK(n=9) hump_pos=0.53 wf_turn=+0.376 exh=56% | VALLEY(n=11) hump_pos=0.46 wf_turn=+0.074 exh=36%
- long-loser:
  n=   3 | P(exhaustion SPENT | turn)=0% | exhaustion-at-turn: wf_turn med=+0.342 (0=balance) returned med=0.26 (1=rolled back) flow-turned-against=0% | per-leg corr(flow,price) med=+0.05 | LEAD: flow-hump position med=0.94 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=33% (50=coinflip)

## eth_kraken  (2422476 cells, 67.3h)
### theta=10bps — 465 legs (233 up->peak, 232 down->valley); clean-hump legs=355 (76%)
- median swing: dur=162s  size=18.2bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.55  IQR[0.29,0.81]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 39% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.115 (0=balanced, +1=still fully with-trend); returned-fraction median=0.43 (1=fully rolled back); flow-turned-against-swing-at-turn=36%
- CORR #1 P(exhaustion SPENT | price turn)=54% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.17  IQR[-0.00,+0.41] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=19% vs base 12% (lift x1.63); RECALL P(flow-flip|turn)=56%; median lead=-4s (>0=leads); 1525 flow-flips vs 467 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=31% vs base 23% (lift x1.36); RECALL P(flow-flip|turn)=78%; median lead=-4s (>0=leads); 1525 flow-flips vs 467 turns
- asymmetry: up->PEAK hump_pos=0.53 wf_turn=+0.244 exh=36% | down->VALLEY hump_pos=0.57 wf_turn=+0.017 exh=41%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.59/38%  mid=0.51/35%  high=0.59/43%  [low<= 81 < mid <= 266 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.53/42%  mid=0.59/40%  high=0.56/35%  [low<= 15 < mid <= 23 < high]
### theta=20bps — 139 legs (69 up->peak, 70 down->valley); clean-hump legs=104 (75%)
- median swing: dur=525s  size=36.2bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.63  IQR[0.36,0.87]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 33% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.119 (0=balanced, +1=still fully with-trend); returned-fraction median=0.39 (1=fully rolled back); flow-turned-against-swing-at-turn=33%
- CORR #1 P(exhaustion SPENT | price turn)=43% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.12  IQR[+0.03,+0.29] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=6% vs base 3% (lift x1.68); RECALL P(flow-flip|turn)=56%; median lead=-4s (>0=leads); 1525 flow-flips vs 140 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=11% vs base 7% (lift x1.61); RECALL P(flow-flip|turn)=77%; median lead=-4s (>0=leads); 1525 flow-flips vs 140 turns
- asymmetry: up->PEAK hump_pos=0.61 wf_turn=+0.229 exh=25% | down->VALLEY hump_pos=0.69 wf_turn=+0.054 exh=41%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.69/26%  mid=0.55/32%  high=0.65/41%  [low<= 324 < mid <= 916 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.72/41%  mid=0.63/30%  high=0.61/28%  [low<= 29 < mid <= 46 < high]
### theta=40bps — 37 legs (18 up->peak, 19 down->valley); clean-hump legs=28 (76%)
- median swing: dur=2090s  size=68.8bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.66  IQR[0.28,0.84]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 46% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.110 (0=balanced, +1=still fully with-trend); returned-fraction median=0.45 (1=fully rolled back); flow-turned-against-swing-at-turn=35%
- CORR #1 P(exhaustion SPENT | price turn)=38% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.09  IQR[+0.04,+0.21] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=2% vs base 1% (lift x1.74); RECALL P(flow-flip|turn)=53%; median lead=-5s (>0=leads); 1525 flow-flips vs 38 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=4% vs base 2% (lift x2.09); RECALL P(flow-flip|turn)=82%; median lead=+10s (>0=leads); 1525 flow-flips vs 38 turns
- asymmetry: up->PEAK hump_pos=0.64 wf_turn=+0.139 exh=33% | down->VALLEY hump_pos=0.73 wf_turn=+0.062 exh=58%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.74/33%  mid=0.43/38%  high=0.71/67%  [low<= 1292 < mid <= 3191 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.72/33%  mid=0.69/54%  high=0.43/50%  [low<= 60 < mid <= 85 < high]

### 4-GROUP breakdown (theta=20bps, 139 legs)

**Cut: WINNER = swing >= 20bp fee floor**  (short/long split at median dur 525s)
- short-winner:
  n=  70 | P(exhaustion SPENT | turn)=51% | exhaustion-at-turn: wf_turn med=+0.090 (0=balance) returned med=0.34 (1=rolled back) flow-turned-against=43% | per-leg corr(flow,price) med=+0.20 | LEAD: flow-hump position med=0.63 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=29% (50=coinflip)
       peak/valley: PEAK(n=37) hump_pos=0.63 wf_turn=+0.277 exh=19% | VALLEY(n=33) hump_pos=0.66 wf_turn=-0.046 exh=39%
- long-winner:
  n=  69 | P(exhaustion SPENT | turn)=35% | exhaustion-at-turn: wf_turn med=+0.125 (0=balance) returned med=0.41 (1=rolled back) flow-turned-against=23% | per-leg corr(flow,price) med=+0.10 | LEAD: flow-hump position med=0.61 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=38% (50=coinflip)
       peak/valley: PEAK(n=32) hump_pos=0.51 wf_turn=+0.187 exh=31% | VALLEY(n=37) hump_pos=0.72 wf_turn=+0.110 exh=43%
- short-loser: n=0 (too few)
- long-loser: n=0 (too few)

**Cut: WINNER = swing >= median size (36bp)**  (short/long split at median dur 525s)
- short-winner:
  n=  23 | P(exhaustion SPENT | turn)=43% | exhaustion-at-turn: wf_turn med=+0.262 (0=balance) returned med=0.33 (1=rolled back) flow-turned-against=43% | per-leg corr(flow,price) med=+0.26 | LEAD: flow-hump position med=0.64 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=13% (50=coinflip)
       peak/valley: PEAK(n=13) hump_pos=0.61 wf_turn=+0.368 exh=8% | VALLEY(n=10) hump_pos=0.90 wf_turn=+0.046 exh=20%
- long-winner:
  n=  47 | P(exhaustion SPENT | turn)=38% | exhaustion-at-turn: wf_turn med=+0.123 (0=balance) returned med=0.45 (1=rolled back) flow-turned-against=28% | per-leg corr(flow,price) med=+0.10 | LEAD: flow-hump position med=0.61 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=32% (50=coinflip)
       peak/valley: PEAK(n=24) hump_pos=0.51 wf_turn=+0.187 exh=25% | VALLEY(n=23) hump_pos=0.70 wf_turn=+0.062 exh=39%
- short-loser:
  n=  47 | P(exhaustion SPENT | turn)=55% | exhaustion-at-turn: wf_turn med=+0.068 (0=balance) returned med=0.35 (1=rolled back) flow-turned-against=43% | per-leg corr(flow,price) med=+0.19 | LEAD: flow-hump position med=0.63 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=36% (50=coinflip)
       peak/valley: PEAK(n=24) hump_pos=0.68 wf_turn=+0.249 exh=25% | VALLEY(n=23) hump_pos=0.50 wf_turn=-0.046 exh=48%
- long-loser:
  n=  22 | P(exhaustion SPENT | turn)=27% | exhaustion-at-turn: wf_turn med=+0.159 (0=balance) returned med=0.34 (1=rolled back) flow-turned-against=14% | per-leg corr(flow,price) med=+0.09 | LEAD: flow-hump position med=0.62 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=50% (50=coinflip)
       peak/valley: PEAK(n=8) hump_pos=0.49 wf_turn=+0.161 exh=50% | VALLEY(n=14) hump_pos=0.83 wf_turn=+0.159 exh=50%

## sol_kraken  (2632849 cells, 73.1h)
### theta=10bps — 546 legs (273 up->peak, 273 down->valley); clean-hump legs=431 (79%)
- median swing: dur=154s  size=18.5bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.52  IQR[0.28,0.78]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 40% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.133 (0=balanced, +1=still fully with-trend); returned-fraction median=0.42 (1=fully rolled back); flow-turned-against-swing-at-turn=38%
- CORR #1 P(exhaustion SPENT | price turn)=53% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.17  IQR[-0.03,+0.40] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=23% vs base 12% (lift x1.88); RECALL P(flow-flip|turn)=54%; median lead=-2s (>0=leads); 1591 flow-flips vs 547 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=42% vs base 25% (lift x1.69); RECALL P(flow-flip|turn)=78%; median lead=-2s (>0=leads); 1591 flow-flips vs 547 turns
- asymmetry: up->PEAK hump_pos=0.51 wf_turn=+0.226 exh=37% | down->VALLEY hump_pos=0.53 wf_turn=+0.007 exh=43%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.58/36%  mid=0.49/42%  high=0.52/43%  [low<= 94 < mid <= 256 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.52/38%  mid=0.53/41%  high=0.52/42%  [low<= 15 < mid <= 23 < high]
### theta=20bps — 166 legs (83 up->peak, 83 down->valley); clean-hump legs=130 (78%)
- median swing: dur=500s  size=33.1bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.53  IQR[0.33,0.80]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 43% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.092 (0=balanced, +1=still fully with-trend); returned-fraction median=0.45 (1=fully rolled back); flow-turned-against-swing-at-turn=38%
- CORR #1 P(exhaustion SPENT | price turn)=54% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.11  IQR[-0.01,+0.23] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=8% vs base 4% (lift x2.10); RECALL P(flow-flip|turn)=58%; median lead=-2s (>0=leads); 1591 flow-flips vs 167 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=16% vs base 8% (lift x2.10); RECALL P(flow-flip|turn)=81%; median lead=-2s (>0=leads); 1591 flow-flips vs 167 turns
- asymmetry: up->PEAK hump_pos=0.49 wf_turn=+0.191 exh=45% | down->VALLEY hump_pos=0.55 wf_turn=-0.012 exh=42%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.50/45%  mid=0.51/45%  high=0.64/40%  [low<= 331 < mid <= 836 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.51/44%  mid=0.54/46%  high=0.55/40%  [low<= 29 < mid <= 42 < high]
### theta=40bps — 36 legs (18 up->peak, 18 down->valley); clean-hump legs=27 (75%)
- median swing: dur=2024s  size=67.7bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.46  IQR[0.24,0.70]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 44% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.076 (0=balanced, +1=still fully with-trend); returned-fraction median=0.47 (1=fully rolled back); flow-turned-against-swing-at-turn=44%
- CORR #1 P(exhaustion SPENT | price turn)=53% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.06  IQR[+0.02,+0.15] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=2% vs base 1% (lift x2.46); RECALL P(flow-flip|turn)=65%; median lead=-15s (>0=leads); 1591 flow-flips vs 37 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=4% vs base 2% (lift x2.46); RECALL P(flow-flip|turn)=86%; median lead=-18s (>0=leads); 1591 flow-flips vs 37 turns
- asymmetry: up->PEAK hump_pos=0.41 wf_turn=+0.157 exh=56% | down->VALLEY hump_pos=0.48 wf_turn=-0.042 exh=33%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.38/50%  mid=0.54/42%  high=0.64/42%  [low<= 1602 < mid <= 3086 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.38/58%  mid=0.41/33%  high=0.70/42%  [low<= 55 < mid <= 81 < high]

### 4-GROUP breakdown (theta=20bps, 166 legs)

**Cut: WINNER = swing >= 20bp fee floor**  (short/long split at median dur 500s)
- short-winner:
  n=  83 | P(exhaustion SPENT | turn)=53% | exhaustion-at-turn: wf_turn med=+0.094 (0=balance) returned med=0.45 (1=rolled back) flow-turned-against=39% | per-leg corr(flow,price) med=+0.17 | LEAD: flow-hump position med=0.51 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=47% (50=coinflip)
       peak/valley: PEAK(n=38) hump_pos=0.53 wf_turn=+0.237 exh=45% | VALLEY(n=45) hump_pos=0.50 wf_turn=-0.029 exh=49%
- long-winner:
  n=  83 | P(exhaustion SPENT | turn)=55% | exhaustion-at-turn: wf_turn med=+0.091 (0=balance) returned med=0.46 (1=rolled back) flow-turned-against=37% | per-leg corr(flow,price) med=+0.06 | LEAD: flow-hump position med=0.55 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=40% (50=coinflip)
       peak/valley: PEAK(n=45) hump_pos=0.47 wf_turn=+0.133 exh=44% | VALLEY(n=38) hump_pos=0.61 wf_turn=-0.011 exh=34%
- short-loser: n=0 (too few)
- long-loser: n=0 (too few)

**Cut: WINNER = swing >= median size (33bp)**  (short/long split at median dur 500s)
- short-winner:
  n=  20 | P(exhaustion SPENT | turn)=50% | exhaustion-at-turn: wf_turn med=+0.107 (0=balance) returned med=0.44 (1=rolled back) flow-turned-against=40% | per-leg corr(flow,price) med=+0.18 | LEAD: flow-hump position med=0.52 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=40% (50=coinflip)
       peak/valley: PEAK(n=9) hump_pos=0.60 wf_turn=+0.242 exh=33% | VALLEY(n=11) hump_pos=0.51 wf_turn=-0.112 exh=45%
- long-winner:
  n=  63 | P(exhaustion SPENT | turn)=49% | exhaustion-at-turn: wf_turn med=+0.111 (0=balance) returned med=0.43 (1=rolled back) flow-turned-against=32% | per-leg corr(flow,price) med=+0.06 | LEAD: flow-hump position med=0.55 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=43% (50=coinflip)
       peak/valley: PEAK(n=31) hump_pos=0.44 wf_turn=+0.235 exh=48% | VALLEY(n=32) hump_pos=0.66 wf_turn=+0.007 exh=38%
- short-loser:
  n=  63 | P(exhaustion SPENT | turn)=54% | exhaustion-at-turn: wf_turn med=+0.094 (0=balance) returned med=0.45 (1=rolled back) flow-turned-against=38% | per-leg corr(flow,price) med=+0.15 | LEAD: flow-hump position med=0.49 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=49% (50=coinflip)
       peak/valley: PEAK(n=29) hump_pos=0.51 wf_turn=+0.232 exh=48% | VALLEY(n=34) hump_pos=0.42 wf_turn=-0.005 exh=50%
- long-loser:
  n=  20 | P(exhaustion SPENT | turn)=75% | exhaustion-at-turn: wf_turn med=-0.012 (0=balance) returned med=0.61 (1=rolled back) flow-turned-against=55% | per-leg corr(flow,price) med=+0.07 | LEAD: flow-hump position med=0.55 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=30% (50=coinflip)
       peak/valley: PEAK(n=14) hump_pos=0.59 wf_turn=+0.038 exh=36% | VALLEY(n=6) hump_pos=0.55 wf_turn=-0.032 exh=17%

## xrp_kraken  (2632800 cells, 73.1h)
### theta=10bps — 716 legs (358 up->peak, 358 down->valley); clean-hump legs=539 (75%)
- median swing: dur=102s  size=18.4bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.54  IQR[0.29,0.79]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 41% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.117 (0=balanced, +1=still fully with-trend); returned-fraction median=0.45 (1=fully rolled back); flow-turned-against-swing-at-turn=39%
- CORR #1 P(exhaustion SPENT | price turn)=59% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.18  IQR[-0.08,+0.45] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=28% vs base 16% (lift x1.71); RECALL P(flow-flip|turn)=51%; median lead=-1s (>0=leads); 1476 flow-flips vs 717 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=46% vs base 33% (lift x1.41); RECALL P(flow-flip|turn)=72%; median lead=-2s (>0=leads); 1476 flow-flips vs 717 turns
- asymmetry: up->PEAK hump_pos=0.50 wf_turn=+0.246 exh=40% | down->VALLEY hump_pos=0.59 wf_turn=-0.036 exh=41%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.64/30%  mid=0.44/48%  high=0.54/44%  [low<= 58 < mid <= 176 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.54/40%  mid=0.53/42%  high=0.55/41%  [low<= 15 < mid <= 24 < high]
### theta=20bps — 212 legs (106 up->peak, 106 down->valley); clean-hump legs=166 (78%)
- median swing: dur=375s  size=37.3bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.61  IQR[0.29,0.79]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 37% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.131 (0=balanced, +1=still fully with-trend); returned-fraction median=0.42 (1=fully rolled back); flow-turned-against-swing-at-turn=33%
- CORR #1 P(exhaustion SPENT | price turn)=48% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.13  IQR[-0.01,+0.32] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=10% vs base 5% (lift x2.00); RECALL P(flow-flip|turn)=50%; median lead=-3s (>0=leads); 1476 flow-flips vs 213 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=19% vs base 10% (lift x2.00); RECALL P(flow-flip|turn)=77%; median lead=-5s (>0=leads); 1476 flow-flips vs 213 turns
- asymmetry: up->PEAK hump_pos=0.59 wf_turn=+0.305 exh=38% | down->VALLEY hump_pos=0.61 wf_turn=+0.023 exh=37%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.62/34%  mid=0.63/44%  high=0.58/34%  [low<= 224 < mid <= 624 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.62/35%  mid=0.55/47%  high=0.61/30%  [low<= 30 < mid <= 48 < high]
### theta=40bps — 56 legs (28 up->peak, 28 down->valley); clean-hump legs=43 (77%)
- median swing: dur=1113s  size=80.5bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.55  IQR[0.27,0.75]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 46% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.112 (0=balanced, +1=still fully with-trend); returned-fraction median=0.42 (1=fully rolled back); flow-turned-against-swing-at-turn=32%
- CORR #1 P(exhaustion SPENT | price turn)=46% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.07  IQR[-0.03,+0.19] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=3% vs base 1% (lift x2.35); RECALL P(flow-flip|turn)=51%; median lead=-1s (>0=leads); 1476 flow-flips vs 57 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=6% vs base 3% (lift x2.29); RECALL P(flow-flip|turn)=77%; median lead=-12s (>0=leads); 1476 flow-flips vs 57 turns
- asymmetry: up->PEAK hump_pos=0.55 wf_turn=+0.145 exh=39% | down->VALLEY hump_pos=0.61 wf_turn=+0.050 exh=54%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.66/26%  mid=0.47/50%  high=0.54/63%  [low<= 805 < mid <= 2168 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.65/42%  mid=0.60/39%  high=0.51/58%  [low<= 59 < mid <= 102 < high]

### 4-GROUP breakdown (theta=20bps, 212 legs)

**Cut: WINNER = swing >= 20bp fee floor**  (short/long split at median dur 375s)
- short-winner:
  n= 106 | P(exhaustion SPENT | turn)=49% | exhaustion-at-turn: wf_turn med=+0.144 (0=balance) returned med=0.43 (1=rolled back) flow-turned-against=34% | per-leg corr(flow,price) med=+0.22 | LEAD: flow-hump position med=0.62 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=37% (50=coinflip)
       peak/valley: PEAK(n=52) hump_pos=0.53 wf_turn=+0.356 exh=35% | VALLEY(n=54) hump_pos=0.65 wf_turn=-0.021 exh=39%
- long-winner:
  n= 106 | P(exhaustion SPENT | turn)=46% | exhaustion-at-turn: wf_turn med=+0.123 (0=balance) returned med=0.40 (1=rolled back) flow-turned-against=33% | per-leg corr(flow,price) med=+0.10 | LEAD: flow-hump position med=0.61 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=38% (50=coinflip)
       peak/valley: PEAK(n=54) hump_pos=0.62 wf_turn=+0.199 exh=41% | VALLEY(n=52) hump_pos=0.60 wf_turn=+0.050 exh=35%
- short-loser: n=0 (too few)
- long-loser: n=0 (too few)

**Cut: WINNER = swing >= median size (37bp)**  (short/long split at median dur 375s)
- short-winner:
  n=  33 | P(exhaustion SPENT | turn)=42% | exhaustion-at-turn: wf_turn med=+0.283 (0=balance) returned med=0.42 (1=rolled back) flow-turned-against=27% | per-leg corr(flow,price) med=+0.13 | LEAD: flow-hump position med=0.66 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=27% (50=coinflip)
       peak/valley: PEAK(n=15) hump_pos=0.66 wf_turn=+0.343 exh=20% | VALLEY(n=18) hump_pos=0.68 wf_turn=+0.147 exh=33%
- long-winner:
  n=  73 | P(exhaustion SPENT | turn)=42% | exhaustion-at-turn: wf_turn med=+0.120 (0=balance) returned med=0.39 (1=rolled back) flow-turned-against=33% | per-leg corr(flow,price) med=+0.09 | LEAD: flow-hump position med=0.61 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=38% (50=coinflip)
       peak/valley: PEAK(n=35) hump_pos=0.62 wf_turn=+0.202 exh=43% | VALLEY(n=38) hump_pos=0.61 wf_turn=+0.063 exh=34%
- short-loser:
  n=  73 | P(exhaustion SPENT | turn)=52% | exhaustion-at-turn: wf_turn med=+0.113 (0=balance) returned med=0.43 (1=rolled back) flow-turned-against=37% | per-leg corr(flow,price) med=+0.25 | LEAD: flow-hump position med=0.53 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=41% (50=coinflip)
       peak/valley: PEAK(n=37) hump_pos=0.47 wf_turn=+0.419 exh=41% | VALLEY(n=36) hump_pos=0.63 wf_turn=-0.105 exh=42%
- long-loser:
  n=  33 | P(exhaustion SPENT | turn)=55% | exhaustion-at-turn: wf_turn med=+0.125 (0=balance) returned med=0.43 (1=rolled back) flow-turned-against=33% | per-leg corr(flow,price) med=+0.11 | LEAD: flow-hump position med=0.60 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=36% (50=coinflip)
       peak/valley: PEAK(n=19) hump_pos=0.61 wf_turn=+0.185 exh=37% | VALLEY(n=14) hump_pos=0.53 wf_turn=-0.010 exh=36%

## doge_kraken  (2212102 cells, 61.4h)
### theta=10bps — 746 legs (373 up->peak, 373 down->valley); clean-hump legs=480 (64%)
- median swing: dur=89s  size=18.6bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.45  IQR[0.14,0.75]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 37% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.000 (0=balanced, +1=still fully with-trend); returned-fraction median=0.43 (1=fully rolled back); flow-turned-against-swing-at-turn=30%
- CORR #1 P(exhaustion SPENT | price turn)=73% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.06  IQR[-0.11,+0.40] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=28% vs base 20% (lift x1.39); RECALL P(flow-flip|turn)=53%; median lead=+1s (>0=leads); 1282 flow-flips vs 748 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=49% vs base 41% (lift x1.21); RECALL P(flow-flip|turn)=80%; median lead=+2s (>0=leads); 1282 flow-flips vs 748 turns
- asymmetry: up->PEAK hump_pos=0.46 wf_turn=+0.000 exh=37% | down->VALLEY hump_pos=0.44 wf_turn=+0.000 exh=36%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.48/31%  mid=0.44/36%  high=0.44/42%  [low<= 46 < mid <= 166 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.44/31%  mid=0.40/42%  high=0.51/37%  [low<= 15 < mid <= 23 < high]
### theta=20bps — 217 legs (108 up->peak, 109 down->valley); clean-hump legs=157 (72%)
- median swing: dur=352s  size=35.9bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.54  IQR[0.23,0.79]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 37% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.000 (0=balanced, +1=still fully with-trend); returned-fraction median=0.50 (1=fully rolled back); flow-turned-against-swing-at-turn=31%
- CORR #1 P(exhaustion SPENT | price turn)=62% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.11  IQR[-0.06,+0.24] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=10% vs base 6% (lift x1.66); RECALL P(flow-flip|turn)=50%; median lead=+2s (>0=leads); 1282 flow-flips vs 218 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=20% vs base 12% (lift x1.70); RECALL P(flow-flip|turn)=79%; median lead=+1s (>0=leads); 1282 flow-flips vs 218 turns
- asymmetry: up->PEAK hump_pos=0.57 wf_turn=+0.041 exh=36% | down->VALLEY hump_pos=0.54 wf_turn=+0.000 exh=39%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.48/44%  mid=0.56/34%  high=0.60/33%  [low<= 200 < mid <= 584 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.51/38%  mid=0.52/41%  high=0.65/33%  [low<= 30 < mid <= 43 < high]
### theta=40bps — 56 legs (28 up->peak, 28 down->valley); clean-hump legs=42 (75%)
- median swing: dur=1083s  size=72.9bps
- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): median=0.53  IQR[0.23,0.78]
- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): 46% of legs (50%=coinflip)
- exhaustion AT turn: with-flow median=+0.096 (0=balanced, +1=still fully with-trend); returned-fraction median=0.48 (1=fully rolled back); flow-turned-against-swing-at-turn=21%
- CORR #1 P(exhaustion SPENT | price turn)=55% (spent = returned>=50% OR flow crossed to oppose the swing)
- CORR #3 per-leg corr(exhaustion curve, price curve across swing): median=+0.12  IQR[+0.02,+0.18] (0=uncorrelated)
- CORR #2/#4 flow-flip as turn-caller (+-30s): PRECISION P(turn|flow-flip)=2% vs base 2% (lift x1.56); RECALL P(flow-flip|turn)=42%; median lead=+0s (>0=leads); 1282 flow-flips vs 57 turns
- CORR #2/#4 flow-flip as turn-caller (+-60s): PRECISION P(turn|flow-flip)=6% vs base 3% (lift x1.99); RECALL P(flow-flip|turn)=81%; median lead=-3s (>0=leads); 1282 flow-flips vs 57 turns
- asymmetry: up->PEAK hump_pos=0.64 wf_turn=+0.071 exh=32% | down->VALLEY hump_pos=0.38 wf_turn=+0.150 exh=61%
- duration-invariance:
    duration(s) terciles — flow-hump pos / exhausts%%: low=0.57/47%  mid=0.44/44%  high=0.62/47%  [low<= 560 < mid <= 1906 < high]
- size-invariance:
    size(bps) terciles — flow-hump pos / exhausts%%: low=0.36/58%  mid=0.34/39%  high=0.70/42%  [low<= 56 < mid <= 95 < high]

### 4-GROUP breakdown (theta=20bps, 217 legs)

**Cut: WINNER = swing >= 20bp fee floor**  (short/long split at median dur 352s)
- short-winner:
  n= 109 | P(exhaustion SPENT | turn)=72% | exhaustion-at-turn: wf_turn med=+0.000 (0=balance) returned med=0.53 (1=rolled back) flow-turned-against=38% | per-leg corr(flow,price) med=+0.07 | LEAD: flow-hump position med=0.52 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=40% (50=coinflip)
       peak/valley: PEAK(n=51) hump_pos=0.58 wf_turn=+0.000 exh=37% | VALLEY(n=58) hump_pos=0.52 wf_turn=+0.000 exh=43%
- long-winner:
  n= 108 | P(exhaustion SPENT | turn)=53% | exhaustion-at-turn: wf_turn med=+0.068 (0=balance) returned med=0.47 (1=rolled back) flow-turned-against=24% | per-leg corr(flow,price) med=+0.11 | LEAD: flow-hump position med=0.57 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=34% (50=coinflip)
       peak/valley: PEAK(n=57) hump_pos=0.57 wf_turn=+0.104 exh=35% | VALLEY(n=51) hump_pos=0.56 wf_turn=+0.011 exh=33%
- short-loser: n=0 (too few)
- long-loser: n=0 (too few)

**Cut: WINNER = swing >= median size (36bp)**  (short/long split at median dur 352s)
- short-winner:
  n=  44 | P(exhaustion SPENT | turn)=77% | exhaustion-at-turn: wf_turn med=+0.000 (0=balance) returned med=0.58 (1=rolled back) flow-turned-against=45% | per-leg corr(flow,price) med=+0.04 | LEAD: flow-hump position med=0.56 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=45% (50=coinflip)
       peak/valley: PEAK(n=21) hump_pos=0.60 wf_turn=-0.006 exh=43% | VALLEY(n=23) hump_pos=0.52 wf_turn=+0.000 exh=48%
- long-winner:
  n=  65 | P(exhaustion SPENT | turn)=45% | exhaustion-at-turn: wf_turn med=+0.146 (0=balance) returned med=0.44 (1=rolled back) flow-turned-against=15% | per-leg corr(flow,price) med=+0.14 | LEAD: flow-hump position med=0.59 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=34% (50=coinflip)
       peak/valley: PEAK(n=34) hump_pos=0.64 wf_turn=+0.124 exh=32% | VALLEY(n=31) hump_pos=0.56 wf_turn=+0.153 exh=35%
- short-loser:
  n=  65 | P(exhaustion SPENT | turn)=68% | exhaustion-at-turn: wf_turn med=+0.000 (0=balance) returned med=0.50 (1=rolled back) flow-turned-against=32% | per-leg corr(flow,price) med=+0.14 | LEAD: flow-hump position med=0.51 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=37% (50=coinflip)
       peak/valley: PEAK(n=30) hump_pos=0.51 wf_turn=+0.000 exh=33% | VALLEY(n=35) hump_pos=0.51 wf_turn=+0.000 exh=40%
- long-loser:
  n=  43 | P(exhaustion SPENT | turn)=65% | exhaustion-at-turn: wf_turn med=+0.000 (0=balance) returned med=0.52 (1=rolled back) flow-turned-against=37% | per-leg corr(flow,price) med=+0.06 | LEAD: flow-hump position med=0.51 of leg (0.5=random, <0.5=leads) exhausts(1st>2nd half)=35% (50=coinflip)
       peak/valley: PEAK(n=23) hump_pos=0.51 wf_turn=+0.000 exh=39% | VALLEY(n=20) hump_pos=0.61 wf_turn=+0.000 exh=30%
