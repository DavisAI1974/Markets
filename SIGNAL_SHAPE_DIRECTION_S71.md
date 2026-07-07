# DIRECTION: the SHAPE of the signal, not its numeric value (Greg, S71 — 2026-07-07)

> ⛔ **CORRECTION (Greg, S72) — NO AVERAGING. INDIVIDUAL TRADE SHAPES ONLY.** The signal is the shape of
> EACH INDIVIDUAL trade's onset→exhaustion arc, read live on that one trade. It is NOT a mean/pooled/event-study
> arc, and it is NOT graded on one. The mean "quad_means" arcs (all coins, doge-separate, etc.) were only ever a
> PICTURE of the archetype — they are not the signal. Averaging destroys the per-trade shape and washes out the
> edge, which is exactly why pooled scalars looked "flat/noisy" — that flatness is the averaging error, NOT
> evidence against the signal. The per-trade differences may be MODEST IN SIZE but they are DISTINCT ON EACH
> TRADE, and a small-but-consistent per-trade difference is a real edge. Clear all averaging framing from any
> shape discussion. (Validation classifies EACH trade on its OWN shape and tallies the per-trade decisions —
> that is counting decisions, not averaging curves.)
>
> ⛔⛔ S73 SHARPENING (Greg) — THIS APPLIES TO THE GATE TOO. Do NOT average the archetypes into the gate. The 4
> archetypes (short/long x winner/loser) are FOUR SEPARATE SETS OF INDIVIDUAL CURVES. A centroid/mean gate is
> averaging and FAILS: when the arcs saturate the winner-mean ~= loser-mean, so a nearest-centroid gate cannot
> separate (proven on SOL, S73). Match each forming trade to the EXACT individual curve shapes (nearest actual
> curves / per-trade template), keep all 4 buckets distinct, output trade / don't-trade. No averaging anywhere.
>
> ⛔⛔ S73 — WHERE WINNER/LOSER DON'T OVERLAP (Greg, VERY IMPORTANT). Winner/loser shapes OVERLAP in ABSOLUTE
> level (a blunt threshold over-skips). They SEPARATE — do NOT overlap — in TWO scale-free signatures that hold
> in BOTH categories: (1) RELATIVE ENERGY — the winner ALWAYS has more energy than its PAIRED loser (short-win >
> short-lose, long-win > long-lose; the within-pair rule never flips); (2) LINEAR vs NON-LINEAR ascent — winner
> non-linear/hockey-stick, loser linear (measure via linear-fit R²/convexity, NOT the saturating blade slope).
> Gate on these non-overlap signatures, per coin x per cell (universal shapes, cell-specific numbers), no volume/
> price. This is the S73 finding / S74 build. See STRATEGY_INVENTORY LIVE block + SESSION_HANDOFF_2026-07-07_S73.

> Greg's note (verbatim intent): "we need to look at the SHAPE of things. How much does the exhaustion
> number change from second to second — not just an average over a couple of weeks. Find exhaustion in
> previous trades and MAP THE CURVE of it. Not the numeric value but how quickly up and down our number
> goes. I guarantee there's a curve to it, and it probably follows a SIMILAR shape for different times but
> the SAME conditions — even if the numbers aren't the same each time." **This is more in-depth; Greg to
> expand.**

> ⭐ **S72 RESULT (2026-07-07):** the ENTRY CURVE-SHAPE edge STANDS (the pre-onset ascent SHAPE separates winners
> from losers per trade on all 5 cells) and is THE prize. ⛔ #0e: the edge is the CURVE SHAPE read per trade — NOT a
> snapshot AUC; the ~0.60–0.70 OOS logistic score was only a rough shape-carries-info check, never the signal/metric. The EXIT/turn read via 20s trade-flow exhaustion is a NULL on the sparse Kraken
> book (peak-to-valley test: no leading/specific exhaustion tell at the price turns; ROOT CAUSE = trade sparsity
> saturates `rolling_imb(20s)`; the 4 swing groups don't separate — opposite of the entry archetypes). The exit
> is winner-optimization only (not survival), so the current running exit stays as the fine default; deep-bail
> demoted (entry gate skips the losers). To pursue the exit read: denser/aggregated tape or a book-depth proxy.
> See `research/exit_s72/PEAK_VALLEY_FINDINGS_S72.md` + `SESSION_HANDOFF_2026-07-07_S72.md`.

## The core reframe
We've been reading exhaustion (and the flow signals) as a **level / average scalar** — e.g. exhaustion =
`|late-half imbalance| < |early-half imbalance|`, reversal rate ~48% pooled over the window. That **collapses
the dynamics to one number and averages it.** Greg: the signal is in the **SHAPE** — the second-by-second
*trajectory* of exhaustion approaching the turn: how fast it rises/falls (velocity), its curvature/morphology.
And it is **scale-invariant** — the same curve shape recurs under the same conditions even when absolute levels
differ, so we match by **curve, not value.**

## Why this likely explains the FLAT result
The S36 dipole re-eval on the 42h Kraken book gave a **flat conviction ladder (~48% across all flow-states)**
and `imb_flow` pooled 51.2% (~1σ = noise). Prime suspect: **we measured the wrong object.** Exhaustion was
crushed into a 2-point flag (early vs late half) and the outcome averaged — that discards the curve where the
predictive information may live. A signal can be **invisible in its average and sharp in its shape.** Two
reversals with the same predictive shape but different levels both read as "48%."

This is the **OD / flow thesis applied to our own signal**: don't read the value, recover the *governing curve*
— its velocity (dExhaustion/dt), acceleration into the turn, morphology — and match by shape. The info-dipole is
already a flow operator (dMI/dt, `odcore/info_dipole.py`); this pushes it to the **full trajectory**, not a
2-point difference.

## The concrete test (per cell; result-discipline, don't assume the curve — find it)
1. **Extract second-by-second trajectories.** For past legs (reversals vs continuations), pull the per-second
   exhaustion/imbalance series over the pre-entry window approaching each turn (the book carries per-sec buy/sell
   + mid; `run_kraken_cell` gives the legs/turns; strictly pre-entry, no leakage).
2. **Align at the turn** (t=0 at the pivot/onset) and OVERLAY the curves.
3. **Do reversals share a shape distinct from continuations?** Look for a characteristic morphology (e.g.
   imbalance decaying at an *accelerating* rate into the turn vs a flat/late collapse).
4. **Characterize with LEVEL-INVARIANT shape features:** normalized slope, curvature, time-to-collapse, the
   derivative (velocity/acceleration) profile, peak-to-turn timing — features of the *curve*, not the level.
5. **Test whether the SHAPE features predict where the SCALAR was flat** (per-cell, net-of-cost, shift-null,
   cross-window persistence). If shape clusters by regime → Greg's "same shape, same conditions, different
   numbers." If it doesn't beat the scalar, that's an honest null.

## Connections
- **The fingerprint thesis** (`bucket-distinctiveness-is-the-goal`): the distinctive per-cell fingerprint may
  live in the signal's DYNAMICS/shape, not its static value — this is the same idea sharpened.
- **The AWS continuous re-tuner** (Greg, S71): a shape/curve library is exactly what a regime-adaptive tuner
  would match live — "what curve are we on right now" → which config fits current conditions.
- **Timing/swing thread** (S36b): the swing edge is real (oracle); the trigger is late. A shape-of-exhaustion
  read could arm the tight price-reversal trigger EARLIER by recognizing the reversal *curve* before the level
  crosses a threshold.

## THE WHOLE BALLGAME — the complete decision surface (Greg, S71)
"Not only churn, but enter/exit times, good/bad trades — and factored against DIRECTION, that's the whole
ballgame." The complete strategy is a small set of decisions, and **they all read off the SAME real-time arc:**
- **DIRECTION** (the axis) = sign of the flow — the dipole as trend-follower (which way).
- **ENTRY timing** = the ignition / rising limb (onset; the false-start-then-launch precursor).
- **EXIT timing** = the exhaustion / collapse limb (flow returning to balance).
- **GOOD/BAD trade (selection)** = does the arc SHAPE predict a fee-clearing move (the quality gate).
- **CHURN** = falls out — take every arc that predicts profit, as often as they come (fee-floor-bounded).
Everything is **conditioned on direction**: entry/exit/quality read differently for a long vs a short. THE
UNIFICATION: dipole (direction/trend), arc (exhaustion/exit), price-reversal (timing), capacity (sizing) are
NOT separate tools — they are all reads off ONE object, the live curve. One curve, every decision. That is
what makes the continuous re-tuner tractable (tune thresholds on one object, not five). Sequence: confirm the
ENTRY+QUALITY+CHURN legs (running now), then add EXIT-timing (read the collapse limb live vs fixed
horizon/deep-bail) and full direction-conditioning. One at a time.

## Status
- Idea logged; **Greg to expand ("more in-depth").** Not yet run. Prime candidate to explain the flat scalar
  ladder and to feed the shape-matching the continuous re-tuner would use.
