# S61 BUILD NOTES — Coinbase exit round-by-round record (2026-07-04)

Successor of `S60_EXIT_NOTES.md` per the one-round-one-test discipline. Session order (Greg):
(1) the 2 S60-casualty coin agents FIRST, primary frame = mine the scrap heap (code + archive +
ALL handoffs + CLAUDE docs) for Coinbase-exit gold; (2) then the build queue in order; (3) NO
KRAKEN until the Coinbase exit is done. Dipole research lane runs in parallel (Greg cleared).

## MISTAKES CAUGHT (append-only; S58/S60 ledgers carry)
(none yet this session)

## ROUND 1 — THE TWO RE-RUN VERDICT AGENTS (S60 interrupt casualties, numbers delivered)

Full reports IN-REPO: `sol_exit_report_s61.md`, `btc_armedbefore_report_s61.md`.

**SOL — PROTECT, with numbers.** Zigzag stands; every exit candidate negative/null on the
registry cell (plain40 −21.4 [−64.5,+5.4]; armed uw stop −14.6; cascflip dead on bins −0.54;
c_x retrace = wealth transfer −17..−21.5, winners −65..−73). POWER BAR (the shield): books
th100 n=56 detects only a 54bp/leg effect; plausible +1..+3bp effects need weeks-to-months —
**standing rule: any SOL exit pitch on <150 books legs across <2 weeks is auto-rejected**;
sub-2bp effects are permanently the bins-instrument's job. FILL/FEE: honest net ∈
[+0.94, +6.95] vs the +6.11 record — queue clears median 8.1s vs multi-hour legs; taker risk
is PRICE-ELIGIBILITY not queue depth (worst-case fixed-price cover 10.7% taker, −5.17/leg;
repeg-to-best +0.15). Toll law confirmed (books 50.74 vs c·θ=50), no flag. `lean_close`
win/lose NULL on the forward sandbox ledger (winners-flow-invisible prints on our own record).

**BTC — S60 conclusion CONFIRMED on deploy, AMENDED twice.** Tape note: refreshed 30d bins
end Jul 4 (one day later than S60) → partial OOS re-ask. CONFIRMED: armed_stop fails registry
th80 (tail −0.94 vs base +1.90; positive-week −1.95 = exposure-shrink); plain stop survives
(all-legs +2.39, TAIL +1.77 vs base +1.90 ≠ shrink, 5/5wk, ex-top3, both sides, beats blind
timer, machine premium ≈ +1.29/hr vs shuffle, caps worst leg −91→−54). Cell stays negative
everywhere — RIDER ONLY, cell gated. **AMENDMENT 1: the armed-before discriminator itself
did NOT survive the tape shift on BTC** (perm z −1.05 th80; th100 death-rate split
SIGN-INVERTED) → demote the S60 "8/8 cells cross-coin" claim to **SOL-only until re-shown**.
**AMENDMENT 2: X=40 replaces X=50 as the primary arm at th80** (better on every axis; X=50 =
winner-cheaper shadow). TAKER TERM re-derived: X=40 full-taker mean ~0 ± 0.4bp/leg — the
stop's entire value is TAIL-SHAPE; pays iff realized taker share < ~70–85% → honest fill
model is deploy-deciding. NEW OPS FINDING: on the −494 gap leg a tape-graded price stop gives
ZERO gap protection (first triggerable cell was the −494 print) → ops bar now BLOCKING:
exchange-side resting stop + staleness kill-switch (>5min silence → flatten) before capital.
Rider spec written (report §7): `btc_coinbase_mb80_plainstop`, X=40 primary, X=50 + armed +
timer75 shadows, dual fill scoring, accrual 57-legs disaster screen / 261–389-legs verdict,
stand-down rules.

**CONVERGENCE (both agents, isolated):** (1) honest fill model = build #1 (SOL: certifies the
record; BTC: decides rider fee-safety); (2) FEE TIER outranks all exit code (Greg's 2 clicks);
(3) cover-grace demotes to contingent shadow (repeg covers make grace=0 fine); (4) fee-aware
unload NOT for SOL (re-proves harvest-rungs kill); cascflip stays DOGE-only.

## ROUND 2 — BUILD (a): THE HONEST FILL MODEL — WIRED (opt-in), CANARY PASS, MEASURED

**The wire:** `fill_model="queue"` + `queue_frac` threaded `simulate_swing_maker` →
`run_stream` → `run_midband_cell` (default `"front"` = bit-identical). New
`swing_maker._queue_fill_index`: the `maker_book._first_fill_index` queue-ahead rule
(cumulative opposing taker volume after the post must STRICTLY exceed queue_frac × best-level
size at the post cell) as searchsorted-on-cumsum — exact, no fill_window cap, so mid-band leg
durations are handled. At queue_ahead=0 it reduces exactly to `_next_positive`. Applies to
every maker fill site (opens, lean-exit covers, exit-gate covers, grace covers).

**CANARY (mandatory, PASS):** `scripts/_s61_fill_canary.py` — default-path leg rows
bit-identical pre/post wire on all 4 cells (sol 56 / xrp 32 / doge 40 / btc-forced 22 legs;
baseline JSON snapshot compare). Sandbox/paper defaults untouched.

**MEASUREMENT (books, all 4 registry cells, btc force-active):** under the honest queue model
the fills move but the money does not — queue fills land LATER (sol: 48/56 legs, median
+8.6s, p90 ~40s, max 155s) at the SAME fixed limit price, zero fills slip past their
next-flip cap → **maker_close stays 100%, net/leg unchanged on all 4 cells** (sol +7.467,
xrp −10.907, doge −5.309, btc −44.492 incl. gap leg). Independently matches the SOL agent's
estimate. **HONEST STATEMENT: queue DEPTH is not the binding fill constraint at mid-band;
the remaining honesty gap is PRICE ELIGIBILITY** (only volume printing at/through our level
fills us — `swing_accum._eligible_fill` is the in-repo machinery; the SOL agent's fixed-price
worst case = 10.7% taker, −5.17/leg bound). That is the next increment of build (a) if we
want the lower bound in the executor; the upper bound (repeg-to-best) is current behavior.

## ROUND 3 — DIPOLE RESEARCH LANE (parallel, Greg-cleared; report `dipole_lane_report_s61.md`)
Headline: **every rank-A cross-venue/cross-coin TIMING use collapses to lag-0 synchrony at
1s** — one coherent finding, not four nulls. (1) Binance→Coinbase lead-lag: SYNCHRONY KILL
(13/13 segments, 4 coins, skew bounded <1s); one survivor: Binance net-flow → Coinbase
next-second return, +1s, 13/13 segments, ~0.3–0.5bp = quote-skew tier only. (2) Markout
decile map: KILL (vol double-sort mandatory — linear vol residualization is a NON-control);
but the survivor consumed by the FILL office survives: prior-second Binance net-flow marks
per-fill adverse selection (dec10−dec1 −0.19..−0.30bp, z −2.2..−6.6, vol-tercile-robust).
(3) Cross-coin majors→alts (Greg's add): D6 SIMULTANEITY KILL 6/6 pairs (dive propagation
co-occurs same-second, no major lead → no flatten overlay); M1 UNREADABLE in the return-
entropy basis (estimator floor, caught by the shift control) BUT the INFO-040 strength meter
fires + shift-nulls cleanly on all 6 pairs — cross-coin MI is real and state-dependent;
structured-vs-vol-clustering left OPEN (deflationary read live). Candidate offices filed:
fill-toxicity mark (queue-level test owed), per-cell regime conditioner (descriptor tier).

## STANDING / NEXT
- Committed LOCALLY only — **push waits on Greg's clear** (S60 focus directive).
- Build queue state: (a) DONE (wire + canary + measurement; price-eligibility increment
  named); (b) cover-grace = contingent shadow only (demoted by both agents); (c) fee-aware
  unload = NOT for SOL, unranked elsewhere; (d) doge cascflip = next build item, DOGE-only.
- BTC rider (`btc_coinbase_mb80_plainstop`) speced and ready to wire AFTER the ops-bar
  question (exchange-side stop / staleness kill-switch) is answered — tape-graded stop gives
  zero gap protection.
- Record change owed (BTC Amendment 1): demote the armed-before robustness-file entry to
  SOL-only in the S60 record when next edited.
- FEE TIER: still the biggest lever (Greg's 2 clicks). Kraken stays PARKED.

## ROUND 4 — THE TWO COIN EXIT CHANGES CODED (Greg: "code all of the exit changes")

**The wire:** `exit_spec` = the per-cell exit-corrector socket in `simulate_swing_maker` (the
S60 code-miner's exit_pred generalization of the lean_exit walker) — kinds `price_stop` /
`armed_dive` / `casc_flip`, actions `flat` / `flip`, per-side filter; every exit_spec close
(and a flip's new open) is a TAKER cross (the conservative arm — a protective stop is
structurally taker; the DOGE flip survives stop-as-taker on the record). `lean_w` param on
`run_stream` = the walker's lean window in WALL-CLOCK terms per venue (the S60 R4b 60s-wall
confound fix; 600s = 6000 cells on the 0.1s book grid). Legs carry `stop_exit`; sandbox rows
carry the new column + variant-tagged `mode`.

**Registry:** `COINBASE_MIDBAND_VARIANTS` = exactly the per-cell diagonal —
`doge_coinbase_mb100_cascflip` (S60 R4 spec verbatim: BUY-only, pure dive <=-0.30 on 600s-wall
lean, >=20bp underwater -> FLIP; ~30-fire accrual bar, stand-down rules in the config note) and
`btc_coinbase_mb80_plainstop` (S61 rider: X=40 primary per Amendment 2, flat-until-next-confirm;
ops bar blocks CAPITAL only — S60 R4 said sandbox day one). SOL and XRP get NO variant BY
VERDICT. `paper_trade.py` accrues variants alongside base cells (distinct cell names, same
SANDBOX ledger).

**CANARY:** base-cell rows bit-identical modulo ONE new key (`stop_exit`, all False) —
verified key-stripped bytes equal on 4/4 cells, then rebaselined. PASS.

**FIRST NUMBERS (books, leg-slice tier — the LEDGER decides, these are the wire check):**
- doge cascflip: 7 fires / 40 legs, cell face −5.31 -> **+1.15 net/leg** (direction matches the
  S60 instrument read; n-tiny).
- btc plainstop: 8 fires / 22 legs, −44.49 -> −41.96 (gap leg still in; ex-gap is where the
  stop's tail-shape value lives). Cell stays gated for capital.

**RENDERS (Greg's print order):** `docs/renders/s61/legs_<cell>.png` — 10 biggest losers +
10 smallest winners per cell (4 base + 2 variants), rendered through the NEW executor path
(red X = stop/flip fired). Tool: `scripts/_s61_exit_renders.py`.

**Build-queue state:** (a) DONE, (b) demoted to contingent shadow, (c) rejected for SOL /
unranked elsewhere, (d) DONE (cascflip) + the BTC plainstop rider — all exit changes coded.

## ROUND 5 — GREG'S SIGNS-FLIPPED CATCH ON THE RENDERS (sol; "xrp and doge look the same")

**NOT a sign bug — verified 3 ways:** REVERSED control (all sides flipped) = −36.75 net/leg vs
live +7.47 (a real flip would make reversed win); accounting spot-check on shorts exact;
side labels in the renders correct. What Greg's eye caught is REAL though: on the SOL books
window ALL profit is long-side (B +28.28 vs S −13.35 n=28/28) and 6/10 biggest losers are
confirm-SHORTS entered at 1–17% of the local range — sold the dip bottom, price mean-reverted
(the S60 "right spot, opposite trade" print, per-side).

**DRIFT, not structure (the instrument kills it):** on 30d bins the asymmetry collapses —
sol B +4.41 / S +0.84 (both positive), DOGE INVERTS (bins S +3.66 > B −0.26 vs books S −16.26),
xrp ~0/~0, and every per-half split flips sign. The books per-side splits are ~4-day window
drift; a side-conditioned exit is a regime bet.

**Greg's reframe tested anyway ("don't raise SOL profits — eliminate the huge losses"):**
side-conditioned stop X=40 aimed ONLY at each cell's bleeding side, executor-run on BOTH tapes:
- SOL S-only: books d=−0.88/leg, bins d=−1.31 (side-blind: books −27.11) → even perfectly
  side-targeted, the stop LOSES on both tapes. PROTECT survives its strongest challenger yet.
- DOGE S-only: books +5.53 BUT bins −1.31 (both-sides bins +0.59 ≈ noise) → books drift
  artifact; DOGE's earned loss-killer stays the flow-conditioned cascflip (wired).
- XRP B-only: ~0 both tapes. Nothing.
**BOTTOM LINE:** the −95..−121bp legs are the bounded-loss design (−θ−fees deaths). The
loss-eliminators that survive controls are per-cell and already WIRED (doge cascflip, btc
plainstop rider). For SOL/XRP no causal read clears — winners-invisible law; the named path to
killing SOL's big losers without winner damage is the S35 fingerprint tier (false-confirm
recognition at entry), not exit knobs. The power bar stands guard.

## ROUND 6 — GREG: "switch the positions of the biggest losers" — the ladder quantified

ORACLE (flip the actual 10 biggest losers at entry): ~+38/leg on sol books — the prize exists.
NAKED DEPTH-FLIP (switch at -X underwater, executor price_stop action=flip, both tapes):
KILLED — sol books FLIP@-40 = -63.17/leg (40/56 legs touch -40 but only ~11 die; 29
recoveries become double-losses); bins deltas 0 +/- 1 everywhere; doge/xrp books negative.
Depth alone cannot tell a death from a dip on a dip-entry machine.
FLOW-CONDITIONED FLIP (dive + underwater + side): earns on DOGE only — already wired
(cascflip). RECOGNITION AT ENTRY: winner/loser entry features near-identical on every causal
read (winners-invisible law) -> the oracle prize on SOL is S35 FINGERPRINT-TIER, not exit-knob
tier. Greg's intuition = the cascade-flip family; its deployable instance is per-cell.

## ROUND 7 — GREG'S XRP CATCH: rate-adjusted, XRP is #2 (volume is its argument)

Per-leg tables undersell XRP — it FIRES ~2x the rate on the books window (1.10 legs/hr vs sol
0.56 / doge 0.40 / btc 0.11; caveat: 29.2h window — on 30d bins the gap mostly closes, xrp
1.47 vs sol 1.35). Loss-elimination ORACLE in $/hr @$5k: sol +11.34 (cb_real) / +13.69
(kr_mk0); **xrp +7.06 / +11.48 = #2, ahead of doge (+5.73/+7.49) and btc (+0.79/+1.09)**
despite the worst per-leg print. IMPLICATIONS (no new code earned): (1) XRP = the most
FEE-SENSITIVE cell (2x the fee events) — Greg's fee-tier clicks are worth most there, matching
the R4 diagnosis (−16 fees on +4.1 gross); (2) its oracle stays exit-knob-uncapturable
(rounds 5-6 apply; dv40+uw corrector parked on the 150-leg bar); (3) XRP's cadence is the
strongest argument for the Kraken lane when un-parked (0-maker + feeds the $10M/30d tier).

## ⭐ STANDING METRIC RULE (Greg, S61 — restated hard): PROFIT PER HOUR IS THE SCOREBOARD.
Per-trade averages are diagnostics only. Every result table leads with net $/hr (and legs/hr);
per-leg bp appears in support. (Extends S53 "judge on net $/hr AND legs/hr".) The S61 board in
$/hr (books, $5k, cb_real | kr_mk0 frame): sol +2.11|+6.62; doge_cascflip +0.23|+3.46 (flips
DOGE positive at cb_real this window); doge base −1.07|+2.16; btc_plainstop −2.35|−1.45; btc
base −2.49|−1.60; xrp −5.98|+2.79 — XRP = the biggest available $/hr swing on the board and it
is pure FEE FRAME, no code. BTC's 0.11 legs/hr caps its $/hr relevance = rider-only confirmed
in the right units.

## ROUND 8 — SOL LOSER WALKTHROUGH (Greg: "go through each loser and explain why it fired")

All 10 biggest SOL losers = ONE mechanism, two directions: the machine believes a c*theta=50bp
retrace off an extreme STARTS a new leg; on these 10 the retrace was a PAUSE inside a bigger
move that resumed. Shorts #1,3-7: rallies of +126..+1102bp into the pivot, 50bp pullback ->
SHORT fires = sold the breather in a live rally (best favorable +1..+12bp inside the first
minute — wrong from the first tick). Longs #8-10: mirror (falls of -99..-129bp, 50bp bounce ->
BUY = bought the relief move). #2 = the theta-fallback chase (flipped LONG at the top of a
+92bp run against the prior short). Switched trades would net +63..+89 each — but the SAME
print fires every winner (winners-invisible law at its sharpest).
TWO EX-ANTE DISCRIMINATOR CANDIDATES SURFACED (leg-slice tier, n=10 — hypotheses only):
(1) FREIGHT-TRAIN CONTEXT: loser #1 armed off a +1,102bp run — no winner fires off that
context; a graded don't-fade-a-monster-run read = the S58 ER/chop member re-anchor (was a
non-filter as anchored, queued). (2) The dipole agent's Job C angle (cross-venue flow at these
entries, per-leg — never tested). Both must clear the full battery before being anything.

## ROUND 9 — DIPOLE FOLLOW-UPS DELIVERED (Jobs A/B/C; report `dipole_followups_s61.md`)
**A — coupling decider: DIRECTIONAL, not vol-state — but fully LINEAR.** Vol-matched surrogate
does NOT reproduce (real meanMI 0.130-0.204 vs surr 0.051-0.070; ~60-70% of above-floor MI is
directional); survives WITHIN vol strata 17/18 cells; BUT per-window MI == Gaussian-implied MI
of Pearson rho (excess -0.05, day_t -20..-40 = no beyond-linear content). OFFICE SPEC: the
regime-conditioner descriptor = rolling cross-coin signed CORRELATION (~400s vs BTC), not KSG
MI — same information, ~1/1000 compute. Descriptor tier only. Pair ordering coverage-confounded.
**B — queue-level fill toxicity: NO overlay earned.** Skip-toxic-decile posting $/hr sub-noise
vs 50-shift floor (sol +2.3 vs floor -9.0±9.5); fee wall reproduced at cb_real. Honest fills
attenuate the decile map 25-70% (fill-prob confound real + measured: toxic posts fill
+4.5-9.3pp more, -2s faster); sole marginal survivor sol H10 -0.146bp z-2.0. SPEC: `bn_nf_pre`
= FREE descriptor column on sol/doge sandbox fill rows only (promotion bar: split markout on
the machine's own forward fills); nothing for xrp/btc; no quote consumption.
**C — big losses vs the whole family: NOTHING NEW SURVIVES.** Cross-venue oppose-flow
separates troubled legs from WINNERS (D-W z +5..+6.8) but CANNOT tell a DEATH from a RECOVERY
(D-R |z|<=2 across horizons, ~128 tests = chance); inside-leg D6 coupling null; stacked
flatten graded in $/hr = -0.25..-1.08 on all 4 cells, at/below shuffle floor. Lead time exists
(deaths only -12..-22bp under at +300s) but nothing reads it. ANSWER STANDS: wired corrector
diagonal + fingerprint tier. Watch item (costless): `cross_major_nf_pre300` D-R z~+2.0 pre-entry
on sol/btc — chance-tier, filed as a fingerprint-encoder candidate column.
=> Round-8's open question closes: the cross-venue angle does NOT discriminate death-vs-recovery;
remaining ex-ante candidates = freight-train context grade (ER re-anchor) + the S35 fingerprint.

## ROUND 10 — FLIP-AND-RIDE AT THE DIVERGENCE POINT (Greg: "how far past 50bp do W/L diverge?")
HAZARD CURVE (SOL 30d bins, n=971, P(final loss | leg reached depth -X)): -30 82% / -50 91%
/ -60 93% — winners & losers separate IMMEDIATELY (already-doomed the moment underwater), NO
clean crossover to key a flip on = the entry-timing problem, not an exit-depth one.
WHY FLIP-AND-RIDE CAN'T PAY (the ride-capture column): losses are FRONT-LOADED — by any depth
where you can tell it's a loser, the leg is already near its low, so the reversal gross left to
"ride" is +0..+2bp everywhere (at -50: 91% loss but only 47% keep falling), vs ~32bp round-trip
flip cost. The reversal catches the bounce-UP as often as the continuation. $/hr flip sweep
(bins, action=flip): baseline -19.81; FLIP@-40..-90 all d = -1.06..+0.39 = NOISE. Same wall as
rounds 5/6, now shown GEOMETRIC not a tuning miss. => the switch-the-losers prize is real ONLY
at ENTRY (move still ahead); by any diagnosable depth it's behind you. Routes to the fingerprint
tier (confirmed by dipole Job C: cross-venue flow separates W-from-L loudly, death-from-recovery
not at all). Flip-and-ride door CLOSED with numbers.

## ROUND 10b — FINE HAZARD GRID (Greg: "how many are losers at 45/40/35/30?")
SOL bins n=971, P(loss | reached -X): -30 82% / -35 84% / -40 86% / -45 89% / -50 91%. THE
DIVERGENCE IS SHALLOW (~30, not 60) — but flip still loses at every shallow depth (flip $/hr Δ
-0.17/-1.83/-0.25/-0.26/+0.29 = noise; books -17.77). TWO reasons the 82% doesn't convert:
(1) "loser" ~= small stop-out near -X, NOT a plunge — still-falling% only ~52% at -30 -> nothing
left to ride (front-loaded losses at fine res); (2) the ~18% winners reaching -30 are the FAT
ones (books: 10/34 reaching -30 are winners = the +28/leg longs) — flipping them shorts the
rally = the entire -17.77 $/hr books wipeout. Ride-capture negative/~0 at all shallow depths
(-3.2..-0.9 bins) vs 32bp flip cost. => divergence is in OUTCOME LABEL not FUTURE PATH; prize
stays entry-only (fingerprint tier). Flip-and-ride door stays closed, now at fine resolution.

## ROUND 10c — FLIP SOONER (Greg: "it isn't waiting longer, it's sooner") + does the agent help?
SHALLOW flip sweep (SOL, $/hr Δ vs baseline). BINS n=971: -5 -1.54 / -10 -1.55 / -15 -0.31 /
-20 +1.91 / -25 -0.06 / -30 -0.17 — the -20 flicker fires on 782/971 legs (80%!) = inverting
the machine, not selecting deaths; noise-adjacent; cell still -17.90/hr. BOOKS n=56: EVERY
shallow flip -10..-18 $/hr; -5 fires 55/56 = shorts nearly every fat-winner long into its rally
= wipeout. BOTH JAWS OF THE TRAP NOW MAPPED: sooner=more ride left but a -20 dip hits ~every
leg (can't select), later=selective but plunge already happened (no ride). NO depth is both
selective AND has ride left = the geometry. DOES THE AGENT HELP: Job C tested exactly the
sooner-flip discriminator (cross-venue flow + whole dipole family): separates trouble-from-
WINNERS (z+5-6.8) but CANNOT tell death-from-recovery (|z|<=2 chance). It gives no working
signal but CLOSES THE DOOR WITH PROOF — the "flip this dip now" call isn't in the flow family;
its only glimmer (cross_major_nf_pre300 z~2) is PRE-ENTRY = fingerprint tier, where the move is
still ahead. Flip-and-ride CLOSED both directions; prize is entry-only.
