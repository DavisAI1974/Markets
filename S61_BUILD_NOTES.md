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
