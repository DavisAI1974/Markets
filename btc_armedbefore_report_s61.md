# BTC ARMED-BEFORE RECHECK — S61 full kill battery (the S60 casualty's owed numbers)

Agent: BTC armed-before recheck (re-run of the killed S60 agent). Frame: mid-band always-in
flip machine (`odcore/entry_coinbase.py armed_midband_flips`, naive k0, BTC registry theta=80,
c=0.5; th100 carried), mid fills, $5k flat, fee columns per charter. Scoring scripts (scratch
only): `btc_armedbefore_battery.py`, `btc_books_exgap.py`, `btc_detail_pass.py` in this
scratchpad. No platform code touched; nothing committed.

## 0. TAPE PROVENANCE (label every number)
- **Bins (PRIMARY statistical tape):** `/tmp/backfill/BTCUSDT_30d_bins.json`, 30d ending
  2026-07-04 (**one day later than the S60 tape** — S60 th80 had n=700 legs, base −2.97;
  this tape has n=672, base −2.46, th100 n=422 base −0.52). All deltas below are therefore
  a partial OOS re-ask of the S60 verdict, not a byte-identical reproduction. Leakage gate
  (`assert_truncation_invariance`) PASS both thetas.
- **Books:** `/tmp/btc_coinbase_book.jsonl.gz`, 196.3h INCLUDING the 155h collector-gap era.
  Gap leg (gross −494.34, dur 145.1h) excluded from every stat; ex-gap n=21, mean gross
  **−6.31 (se 13.2)** — reproduces the S60 R4 number exactly. Books = rate evidence only.
- Positive-baseline week on this tape = **wk3** both thetas (th80 +3.58, th100 +18.26);
  wk4 is a partial new-suffix week (n=27/23, strongly negative baseline −7.68/−26.66).
- Tail-10d baseline th80 = **+1.90** (healthy-regime bar exists on this tape).

## 1. THE ARMED-BEFORE FULL KILL BATTERY (bins, leg-slice = hypothesis tier)

Arms, machine-faithful triggers re-walked on the tape (not the dump's r8 approximation):
armed_stop = arm sl≥+0.10 earlier, then sl≤−0.30 while fav≤−10bp, 600s-wall lean;
plain40/50 = first fav≤−X; timer75 = blind exit at 75% of median leg duration (23min th80 /
37min th100). d = delta vs zigzag, bp/leg.

### th80 (REGISTRY = the deploy question), n=672, 131 theta-deaths (19.5%), 339 winners
| arm | trig% | dALL | dWIN (kills, cost) | dLOSE (deaths hit) | dTAIL10d | dPOSwk(wk3) | wk+ | dEX3 | dBUY/dSELL |
|-----|------:|-----:|--------------------|--------------------|---------:|------------:|----:|-----:|------------|
| armed_stop | 26.6 | **+0.36** | −9.20 (59, −3118bp) | +10.08 (62/131) | **−0.94** | **−1.95** | 3/5 | +0.06 | +0.90/−0.19 |
| plain40 | 35.4 | **+2.39** | −8.16 (32, −2765bp) | +13.12 (**131/131**) | **+1.77** (base +1.90) | +1.73 | **5/5** | +2.19 | +2.47/+2.30 |
| plain50 | 28.6 | +1.35 | −4.62 (16, −1566bp) | +7.43 (131/131) | +1.82 | **+2.86** | 4/5 | +1.19 | +1.64/+1.07 |
| timer75 | 57.4 | +1.17 | −15.91 (233, −5395bp) | +18.57 (73/131) | **−2.27** | −2.86 | 4/5 | +0.81 | +2.12/+0.23 |

### th100, n=422, 74 deaths (17.5%), 217 winners
| arm | trig% | dALL | dWIN | dTAIL10d | dPOSwk(wk3) | wk+ | dEX3 |
|-----|------:|-----:|-----:|---------:|------------:|----:|-----:|
| armed_stop | 32.7 | **+0.35** | −14.42 (45 kills) | +0.95 | **−3.70** | 3/5 | **−0.22** |
| plain40 | 44.3 | +1.66 | −16.39 | +2.57 | −2.60 | 4/5 | +1.19 |
| plain50 | 35.8 | **+1.84** | −9.62 | **+4.60** | +1.80 | 4/5 | +1.44 |
| timer75 | 59.2 | +2.31 | −16.68 | +1.05 | −5.24 | 4/5 | +1.63 |

### (d) Blind-timer control — the plain stop BEATS the kitchen timer at th80
plain40 +2.39 vs timer75 +1.17 all-legs, and the timer's lift is pure exposure-shrink
(tail −2.27, poswk −2.86, 233 winner-kills vs plain40's 32). Machine confirms: timer30
d+0.39 (shuf −0.33), timer60 d+0.04 vs plain40 d+1.11 (shuf −0.18). **The S60 conclusion
"the btc stop premium is not a timer" HOLDS.** (At th100 timer75 nominally tops dALL +2.31
but with 149 winner-kills, poswk −5.24 — classic shrink; not a read.)

### (g) Armed-before DISCRIMINATOR — stratified permutation (the info-tier claim)
Among underwater dive-triggered legs (sl≤−0.30 while ≥10bp underwater), armed-before
(pre-trigger slmax ≥ +0.10) vs unarmed, save = exit-at-trigger vs zigzag; 2000 perms of the
armed label within depth×age terciles:
- **th80** (n=235: 164 armed / 71 unarmed): death rate armed 0.35 vs unarmed 0.39;
  save armed +2.23 vs unarmed −4.44; **strat-perm z = −1.05** (stat +6.67 vs null
  +13.26±6.27 — BELOW its own stratified floor).
- **th100** (n=171: 128/43): death rate armed **0.27 vs unarmed 0.49 — SIGN-INVERTED**
  (unarmed is the deadlier class on this tape); save armed +0.08 vs unarmed +11.52;
  **z = −1.51.**

**AMENDMENT TO S60:** the S60 partial recheck's "armed-before reproduces on BTC 4/4 cells,
perm z +2.1..+3.0" does NOT survive the one-day tape shift. On the refreshed 30d tape the
discriminator is at/below its stratified permutation floor on both thetas and the death-rate
split inverts at th100. Armed-before on BTC is **tape-fragile information, not structure** —
it should be DEMOTED from the robustness file to "SOL-only until re-shown" (SOL's 12/12
strata + 9/9 depth-age replication was its own evidence; BTC never had that depth).

## 2. MACHINE RE-RUN (verdict tier; composition-faithful, 3-seed shuffle floor, $/hr kr_mk0)

### th80 (registry)
| arm | gr/leg | stop% | kr_mk0 | kr0_tks | cb_real | cb_tks | wk+ | d vs zz | shuf floor |
|-----|-------:|------:|-------:|--------:|--------:|-------:|----:|--------:|-----------:|
| zigzag | −2.46 | 0 | −1.15 | −1.15 | −8.62 | −8.62 | 1/5 | — | — |
| armed_stop | −2.10 | 26.6 | −0.98 | −2.23 | −8.45 | −9.44 | 1/5 | +0.17 | −0.30 |
| **plain40** | **−0.07** | 35.4 | **−0.03** | −1.69 | −7.50 | −8.82 | 2/5 | **+1.11** | **−0.18** |
| plain50 | −1.11 | 28.6 | −0.52 | −1.85 | −7.99 | −9.05 | 2/5 | +0.63 | −0.11 |
| timer30 | −1.62 | 51.0 | −0.76 | −3.14 | −8.22 | −10.13 | 1/5 | +0.39 | −0.33 |
| timer60 | −2.37 | 31.7 | −1.11 | −2.59 | −8.57 | −9.76 | 1/5 | +0.04 | −0.61 |

- **plain40 structure premium ≈ +1.29/hr** (live d+1.11 − shuf −0.18) — reproduces the S60
  R3 finding (d+1.23 vs −0.17) on the shifted tape. plain50 premium +0.74; armed_stop +0.47
  (but leg-slice tail/poswk fail → not deployable); timers lose to plain40 live AND on premium.
- **The cell stays NEGATIVE at every fee column** (best kr_mk0 −0.03 with plain40; cb_real
  −7.50). RIDER ONLY — the stop shrinks the bleed, it does not turn the cell. At full-taker
  stop accounting (kr0_tks/cb_tks) every arm is a net cost vs zigzag — the mean value is
  fee-fragile; the earned value is tail-shape.
- th100 machine: plain50 d+0.54 (shuf +0.37 → premium ~+0.17 ≈ noise), plain40 d+0.49
  (shuf +0.15), armed_stop d+0.10 (shuf −0.13). No th100 arm separates from its floor.

### Tail-shape (the stop's real product, th80): zigzag leg dist min −91 / p1 −82 / p5 −78
→ plain40 min −54 / p1 −49 / p5 −44 (hits all 131/131 deaths mechanically); plain50 min −77
/ p1 −60; **armed_stop min −91 / p1 −81 — the worst legs are UNTOUCHED** (it reaches only
62/131 deaths: the lean never armed or never dove on half the deaths). A protective stop
that misses half the theta-deaths and the single worst leg is not a protective stop.

## 3. VERDICT ON THE S60 PARTIAL CONCLUSION (deliverable 2)

**CONFIRMED:** (a) armed-stop FAILS the strict tail bar at registry th80 — on the refreshed
tape all-legs +0.36, tail −0.94, positive-week −1.95 (S60: tail −0.24, wk3 −0.96; same
shape, same kill). (b) The surviving BTC piece is the DUMB plain price stop — tail-robust
(+1.77 where base +1.90 = NOT exposure-shrink), 5/5 weeks, both sides, ex-top3 +2.19,
beats the blind timer, machine premium +1.29/hr above the shuffle floor, cell stays gated
(rider only). (c) Books ex-gap stays rate-evidence: armed_stop 9/21 trig, +7.65/leg;
plain40 8/21, +5.70; plain50 7/21, +1.95 (S60: +6.03/+2.29 — consistent), n=anecdote.

**AMENDED (two places):**
1. **th100 armed-stop "pass" does NOT reproduce.** S60 filed +2.47 all-legs / tail +0.62 as
   a robustness entry; on the day-shifted tape it prints +0.35 all-legs, poswk −3.70,
   ex-top3 −0.22, machine premium +0.23 vs floor. Together with the discriminator's
   perm-floor failure (§1g), the BTC armed-before entry should move from "robustness file"
   to **"not shown on BTC"** — the cross-coin 8/8-cells claim needs the SOL-style strata
   replication on a second BTC tape before it is citable again.
2. **X=40, not X=50, is the primary surviving arm at th80.** S60's leg-slice salvage named
   X=50; its own R3/R3b machines already preferred plain40 (premium +1.23..+1.30 vs +0.77),
   and this tape agrees on BOTH tiers (leg-slice +2.39 vs +1.35; premium +1.29 vs +0.74;
   wk+ 5/5 vs 4/5; hits 131/131 deaths with min-leg −54). X=50 is the winner-cheaper
   shadow (dWIN −4.62 vs −8.16); run both, X=40 primary.

## 4. TAKER-TERM UPDATE (deliverable 3; cb frame, stop close taker 16 vs maker 8 = +8bp;
## "w/ slip" = +10bp)

| arm (th80) | trig% | dALL bp/leg | breakeven taker share | w/ 2bp slip | full-taker residual |
|------------|------:|------------:|----------------------:|------------:|--------------------:|
| plain40 | 35.4 | +2.39 | **84%** | 67% | **−0.44 bp/leg** |
| plain50 | 28.6 | +1.35 | 59% | 47% | −0.93 |
| armed_stop | 26.6 | +0.36 | 17% | 13% | −1.77 |

**AMENDMENT to the S60 fee fact:** S60's "X=40 self-funding at 100% taker (+0.35 residual,
breakeven 112%)" was tape-specific. On the refreshed tape X=40's breakeven is **84%**
(67% with slip) and the full-taker residual is **−0.44**. Across the two tapes the honest
statement is: **X=40's full-taker mean is ~0 ± 0.4 bp/leg — treat the stop's MEAN as fee-
neutral at best; its entire earned value is TAIL-SHAPE** (caps the −80/−91 theta-deaths at
~−45/−55). No arm is fee-SAFE at full taker on this tape; X=40 remains the most
taker-tolerant by ~1.4x over X=50. This makes the honest fill model (real maker-close
share on stop legs) the single deploy-deciding number: the rider pays iff realized taker
share < ~70-85%.

## 5. BOOKS EX-GAP ANATOMY + THE GAP-LEG COUNTERFACTUAL (ops finding)

Ex-gap n=21 mean −6.31 (se 13.2) — S60 reproduced. New counterfactual on the excluded gap
leg (gross −494.34): **the armed stop would have exited at −10.2bp BEFORE the stall** (its
flow trigger fired early in the leg), while **plain40/plain50 "fire" only AT the −494 jump
itself** — the stalled tape has no cells between −40 and −494, so a TAPE-GRADED price stop
provides ZERO protection against a collector gap. This sharpens the S60 ops bar: the plain
stop MUST be deployed as a **resting exchange-side stop + staleness kill-switch**, not as a
tape-side trigger; and it is n=1 flow-luck, not a rescue of the armed stop (which misses
half the ordinary deaths, §2).

## 6. WIDENED ARCHIVE SWEEP (S38-S60 handoffs + CLAUDE.md), BTC-Coinbase-exit lens

Beyond the two inherited gold lists (not re-surveyed), the sweep surfaced:
1. **BTC is a 1-TICK book on Coinbase (half-spread ~0.0008bp, ~860x tighter than SOL)** —
   S43/S44/S46. A resting BTC cover earns essentially NO half-spread; the BTC exit is a
   TAKER-COST problem, not a spread-capture problem. BUT S46 measured BTC swing-maker at
   97% maker on swing capture — the maker path exists, it just pays no spread. Consequence:
   the stop's realized taker share (the §4 deploy-deciding number) is NOT foredoomed to
   100%; the honest fill model will likely land it well under the 84% breakeven — this is
   the single best reason to build the fill model before writing the stop off at cb fees.
2. **The fine-scale stop kill does NOT bind at mid-band (scale-locality, concrete case):**
   the S47 adverse-excursion stop was killed at fine scale ("cuts winners that reverse"),
   and the S43/S45 maker-exit kills (adverse selection in the ~500ms queue wait, d_wait
   bleed, breakeven −0.32bp/leg) were measured on the 100ms 1-tick queue book — legs there
   lived seconds; mid-band legs live HOURS. Re-asking the stop at mid-band was legitimate,
   and it survived (this battery). Kill provenance: wrong band, wrong fee regime, same role.
3. **BTC swings are THIN at mid-band (0.7 flips/hr at theta=20; ~0.42 gap-free legs/h at
   th80)** — S53/S54. The stop-verdict accrual bar (S60: 261-389 gap-free legs = 4-6 weeks)
   is set by this; nothing in the sweep shortens it. Greg's "BTC wins on bigger
   climbs/slides" stays untestable until books accrue post-collector-fix.
4. **Fee ladder exact (S57/S58):** cb_real 8/18 maker/taker; NO lawful Coinbase rebate;
   cb mk0 unreachable ($250M+/30d); reachable floor = Kraken kr_mk0 at $10M/30d. So the BTC
   Coinbase cell cannot be fee-rescued below ~16bp RT: the stop rider never turns the cell
   there; the cell's real hope stays fee-tier/venue-shaped (Kraken parked per Greg).
5. **Second unwired fill hook: `swing_accum._eligible_fill`** (alongside
   `maker_book._first_fill_index`), and **run_stream's lean is a 60s wall on books** — the
   wall-clock confound is INSIDE the platform; a wired armed/dive read needs a lean_w param.
   (Confirms the code-miner list; no new wire found beyond it.)
6. Stays-dead list re-confirmed for BTC at this band/fee/role: peak harvesters (all
   coins), R8-as-harvester, in-profit dives, dive-as-flip on BTC (dip entries make early
   opposing dives entry noise), kitchen timers (this battery re-proved: timer75 tail −2.27),
   fine-band exit economics wholesale.

## 7. RIDER SPEC (deliverable 4) — `btc_coinbase_mb80_plainstop` sandbox rider

The plain stop SURVIVED the battery (§1-§3); armed_stop and timers did NOT. Spec for the
build session (sandbox only; ACTIVE ≠ capital — the cell is negative at every fee column):

- **Cell/entry:** btc_coinbase mb80 (registry shape, naive k0, c=0.5) — entry machinery
  UNTOUCHED. Rider affects the CLOSE leg only; flat-until-next-confirm after a stop fire
  (no composition interference with the flip stream; fee count unchanged — close moves
  earlier, open stays at the confirm).
- **Trigger (PRIMARY arm, X=40):** first cell with with-ride excursion fav <= −40bp from
  entry fill. Evaluated on the live book stream, wall-clock, venue-native.
- **SHADOW ARMS (logged, not acted):** X=50; armed_stop (arm sl>=+0.10 600s-WALL lean,
  then sl<=−0.30 while fav<=−10 — kept as the falsification shadow + gap-behavior probe,
  NOT for deploy); timer75 (75% of trailing-30d median leg dur) as the standing null column.
- **Shadow columns per leg:** trigger time + fav at trigger for every arm; maker/taker
  close scoring for the stop fill — score the stop close BOTH ways: (a) guaranteed-taker
  (16bp + 2bp slip) and (b) honest fill via `maker_book._first_fill_index` once wired;
  accrue realized taker-share on stop legs (the §4 deploy decider: pays iff share < ~70-85%).
  Also log `lean_close` (free descriptor, already accrues).
- **Accrual bar (from S60 R4, unchanged by this battery):** disaster screen |16bp| ≈ 57
  gap-free legs (~5-6d); stop verdict ≈ 261 legs X=40 / 389 X=50 (~4-6 wks); never expect
  books to certify the mean (that stays the instrument's job — bins premium +1.29/hr is
  the standing evidence).
- **Stand-down rule:** suspend the X=40 arm if (a) per-fire mean delta < −8bp after 20
  fires, or (b) 3 winner-kills (stop fires, leg would have closed >0) before 5 death-saves,
  or (c) realized taker share > 90% over any 30-fire window (fee-unsafe; revert to shadow).
- **OPS BAR (blocking, from §5):** the stop MUST be exchange-side resting (or paired with a
  staleness kill-switch that flattens on collector silence > 5min). A tape-graded stop
  cannot fire across a collector gap — on the S60 gap leg plain40's first triggerable cell
  was the −494 print itself. This bar is BLOCKING for the arm acting on capital; shadow
  accrual can start day one.

## 8. BUILD-QUEUE INPUT (deliverable 5; BTC's perspective, movement-per-line)

1. **HONEST CLOSE-LEG FILL MODEL** (wire `maker_book._first_fill_index` +
   `swing_accum._eligible_fill` into a sandbox scoring arm) — deploy-DECIDING for the BTC
   rider: breakeven taker share 84%/67% (§4) and S46's 97%-maker precedent mean the whole
   X=40 economics question is one measured number away. Highest movement-per-line, both
   miners + this battery agree.
2. **STALENESS KILL-SWITCH / EXCHANGE-SIDE RESTING STOP** (ops, small) — blocks the rider's
   capital activation; the −494 gap leg is the largest single bp item on the whole BTC
   books tape and ONLY this mechanic addresses it (§5 counterfactual).
3. **FEE-AWARE UNLOAD / fee-tier work** — at cb_real the cell is −7.50 $/hr WITH the best
   stop; the 12-16bp RT fee lever dwarfs the +2.4bp stop prize (4/4 coins now print this).
   From BTC's seat this outranks any further exit read.
4. **COVER-GRACE at mid-band** — only pays after #1 (covers currently "always fill");
   knife-catch risk concentrates exactly on stop legs, so grade it as a stop-leg interaction
   arm, wall-clock-defined.
5. **CASCFLIP exit_pred generalization** — DOGE's machine winner; from BTC's perspective
   low priority (BTC cross-poll premium +0.37..+0.80 = noise-tier; dive-as-flip stays dead
   on BTC). Build for DOGE, keep BTC out of the config.
6. (From this battery) **Retire the BTC armed-before robustness entry** — one-line doc
   change in the fingerprint file: BTC 4/4-cells z+2.1..+3.0 did not survive a 1-day tape
   shift (§1g); keep armed-before as SOL-only until re-shown on a second independent BTC
   window.

## APPENDIX — battery scripts + raw outputs
- `btc_armedbefore_battery.py` (leg-slice battery + machine re-run, both thetas)
- `btc_detail_pass.py` (per-week arm deltas, tail-shape dist, breakevens)
- `btc_books_exgap.py` (books ex-gap + gap-leg counterfactual)
All in this scratchpad; regenerable; leakage gate PASS; MPLBACKEND=Agg; nothing committed.
