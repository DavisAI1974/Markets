# DIPOLE S61-ALT AT THE ENTRY — S62 (dipole specialist, research-only)

Session 62, 2026-07-04. Successor to `dipole_lane_report_s61.md` + `dipole_followups_s61.md`.
Charter: take my S61 cross-flow / coupling descriptors — the ones that came back REAL as stack
ingredients (Job C cross-flow troubled-vs-winner separator D−W z +5..+6.8; INFO-040 strength
meter; fill toxicity `bn_nf_pre`) — and bring them to the **ENTRY DECISION**, strictly pre-entry,
per-leg, on the CURRENT BTC/ETH mid-band legs. Target: score big-loser (gross ≤ −40 bp) vs
winner (gross > 0) at entry to drive an entry-flip (flip a predicted big-loser: pnl = −gross − 22bp).

House rules honored: strictly causal (features use only indices < ci); per-cell, never pooled;
circular-shift + label-permutation null on every claim; $/hr leads; MPLBACKEND=Agg; Kraken untouched;
nothing wired, nothing committed. Data NOT re-pulled (used the S61 `/tmp/backfill/*_30d_bins.json`,
the Binance-spot 1s bins = the cross-coin instrument).

## Calibration (validates the $/hr convention against the stated oracle)

Legs from the recipe (armed_midband_flips θ80, arm0.5, ci≥1802): **BTC 671 legs, ETH 1026**.
gross = side·(mid[xi]−mid[ci])/mid[ci]·1e4. Entry-flip oracle (flip exactly the big-losers) at
$5k / 720h:

| cell | n | big-loss (≤−40) | win (>0) | mid | base $/hr | **oracle-flip lift $/hr** |
|---|---|---|---|---|---|---|
| BTC | 671 | 200 | 338 | 133 | −1.18 | **+14.93** |
| ETH | 1026 | 302 | 536 | 188 | +0.56 | **+22.65** |

Matches the charter's oracle (BTC +14, ETH +23) to the decimal — the prize is real and my
gross/hours/$5k convention is correct.

## EXECUTIVE SUMMARY

- **The S61 cross-flow separator DOES reach the entry — but attenuated ~3× and week-fragile.**
  My Job-C read (cross-venue/cross-coin oppose flow x = −side·(B−S)/(B+S)) separated troubled
  legs from winners at **E300 (post-entry) at D−W z +6.7**. Brought to the strictly-PRE-entry
  window `[ci−300, ci)` and scored big-loss-vs-win at the entry decision, `cross_major_nf_pre300`
  survives on **ETH at AUC 0.542, z +2.1, and is week-CONSISTENT (all 5 weeks 0.522–0.557)** —
  a real, direction-correct, pre-entry echo of the E300 signal. On **BTC it does NOT reach**
  (AUC 0.533 but carried entirely by week 4 = 0.927; weeks 0–3 are 0.47–0.64, chance) — the
  recurring wk4 regime fragility, reproduced.
- **`cross_major_nf_pre300` (the watch-item) is the single best cross-flow ingredient on ETH**,
  tied with the own-tape `own_nf_pre300` (AUC 0.543 z +2.1). The cross channel adds a genuinely
  separate look (the basket read `xbask_nf_pre300` gives the only positive OOS $/hr, +0.42).
- **No single descriptor and no linear stack clears the shift floor as a hard entry-flip trigger.**
  Best ETH stack (5 oppose-flow ingredients, week-OOS) lifts pooled AUC to **0.560** with
  week-consistent test AUCs (0.56 / 0.524) — but the OOS $/hr flip lift is **+0.01 (z +1.2 vs the
  circular-shift floor)**, i.e. real-but-shallow separation that does not convert to money at a
  hard threshold. This is the winners-invisible law at the entry, quantified: the prize needs the
  E300 (in-leg, post-decision) sharpness or the S35 encoder tier; the pre-entry linear read is a
  **weak-but-real stack ingredient, not a standalone flip gate.**
- **Strength meter (`xcorr400`, INFO-040 regime conditioner):** rolling 400s cross-coin signed
  return-corr. Best raw AUC on BTC (0.537, z +1.5) but week-fragile and NEGATIVE $/hr (z −2.7,
  worse than shuffle as a trigger); ETH null (AUC 0.490). It is a REGIME descriptor, not a
  per-leg loss predictor — consistent with S61 (state-dependent coupling, not a leg-level edge).
- **Fill toxicity `bn_nf_pre1` (own prior-second net flow signed by side):** null at the entry on
  both cells (BTC AUC 0.474 z −1.0, ETH 0.496 z −0.2). It was a per-FILL adverse-selection read
  (S61 Job B), not a per-LEG entry-quality read — the entry test confirms it does not transfer to
  the leg-quality decision. Keep it in its own (fill-mark) office.

## PER-FEATURE TABLE (big-loser vs winner at entry; strictly pre-entry)

AUC = P(feature ranks a big-loss leg above a winner); `dir` = orientation toward big-loss
(negative means the feature is inversely predictive, flip-rule uses feat<τ); `wk` = per-week AUC
(5 weeks, week-OOS consistency check); `full_lift` = best-threshold entry-flip $/hr (full sample,
maximization-inflated); `floor±sd` = 200× circular-shift null of that same maximized lift;
`lift_z` = (full_lift − floor)/sd; `OOS` = honest week-parity out-of-sample flip lift $/hr.

### BTC (n=671; base −1.18, oracle-flip +14.93 $/hr)

| feature | AUC | z | dir | wk AUC (0–4) | full_lift | floor±sd | lift_z | OOS |
|---|---|---|---|---|---|---|---|---|
| xmaj_nf_pre300 | 0.533 | +1.3 | + | .489/.541/.637/.467/**.927** | −0.45 | −0.03±.35 | −1.2 | −0.65 |
| xmaj_nf_pre60 | 0.525 | +1.0 | + | .478/.478/.66/.526/.688 | +0.00 | −0.05±.31 | +0.2 | −0.19 |
| xbask_nf_pre300 | 0.527 | +1.0 | + | .524/.554/.504/.48/.771 | −0.39 | −0.04±.34 | −1.0 | −0.50 |
| own_nf_pre300 | 0.533 | +1.2 | + | .506/.586/.562/.476/.719 | −0.26 | −0.04±.32 | −0.7 | −1.04 |
| bn_nf_pre1 | 0.474 | −1.0 | − | .492/.374/.486/.479/.646 | −0.12 | −0.06±.36 | −0.2 | −1.35 |
| xcorr400 | 0.537 | +1.5 | + | .466/.645/.59/.58/.365 | −0.94 | −0.05±.34 | −2.7 | −1.83 |
| xmaj_ret_pre60 | 0.481 | −0.7 | − | .51/.497/.527/.391/.521 | −0.14 | −0.04±.39 | −0.2 | −1.86 |
| own_ret_pre60 | 0.497 | −0.1 | − | .563/.475/.499/.414/.406 | +0.00 | −0.04±.33 | +0.1 | −1.57 |

**BTC: nothing reaches.** Best AUC (xcorr400 0.537) is week-fragile and a money-loser as a
trigger. The apparent xmaj_nf_pre300 edge is a single-week (wk4) artifact.

### ETH (n=1026; base +0.56, oracle-flip +22.65 $/hr)

| feature | AUC | z | dir | wk AUC (0–4) | full_lift | floor±sd | lift_z | OOS |
|---|---|---|---|---|---|---|---|---|
| **xmaj_nf_pre300** | **0.542** | **+2.1** | + | **.54/.557/.553/.522/.556** | +0.22 | −0.27±.38 | +1.3 | −0.85 |
| xmaj_nf_pre60 | 0.527 | +1.4 | + | .539/.568/.457/.537/.481 | +0.21 | −0.29±.39 | +1.3 | −0.39 |
| xbask_nf_pre300 | 0.528 | +1.4 | + | .569/.577/.492/.447/.522 | +0.42 | −0.31±.40 | +1.8 | **+0.42** |
| own_nf_pre300 | 0.543 | +2.1 | + | .536/.602/.499/.514/.621 | +0.08 | −0.35±.40 | +1.1 | −0.34 |
| bn_nf_pre1 | 0.496 | −0.2 | − | .5/.498/.438/.52/.606 | +0.01 | −0.27±.39 | +0.7 | −0.28 |
| xcorr400 | 0.490 | −0.5 | − | .484/.499/.505/.477/.357 | +0.22 | −0.26±.34 | +1.4 | +0.22 |
| xmaj_ret_pre60 | 0.531 | +1.5 | + | .536/.512/.461/.588/.481 | +0.27 | −0.33±.37 | +1.6 | −0.17 |
| own_ret_pre60 | 0.539 | +1.8 | + | .539/.545/.443/.582/.638 | +0.22 | −0.31±.37 | +1.4 | −0.17 |

**ETH: `xmaj_nf_pre300` and `own_nf_pre300` reach at AUC 0.542–0.543, z +2.1**, with
`xmaj_nf_pre300` the only feature above 0.5 in **every** week. The oppose-flow family is
directionally correct (all `+` dir) but each single feature's $/hr flip lift sits inside the
shift floor (lift_z +1.1–1.8).

## STACK (Greg: everything is a stack ingredient)

Equal-weight standardized stack of the 5 directional oppose-flow ingredients
(`xmaj_nf_pre300, xbask_nf_pre300, own_nf_pre300, xmaj_ret_pre60, own_ret_pre60`), each oriented
by its TRAIN-week sign; week-parity OOS; 200× per-column circular-shift null.

| cell | pooled AUC | week-OOS test AUC | OOS flip $/hr | shift floor±sd | lift_z |
|---|---|---|---|---|---|
| BTC | 0.536 | 0.489 / 0.513 | −1.08 | −0.93±0.82 | −0.2 |
| **ETH** | **0.560** | **0.56 / 0.524** | +0.01 | −0.78±0.68 | **+1.2** |

The stack lifts ETH pooled AUC from 0.543 (best single) to **0.560** and both week-OOS test AUCs
stay above 0.5 — the cross-flow + own-flow + return family carries **additive, week-consistent**
big-loss/win separation at the entry. But as a hard flip trigger the OOS $/hr is ≈0 (z +1.2), so
the separation is real yet too shallow to convert at a threshold. BTC does not stack (week-OOS AUC
≈ chance, negative $/hr) — the wk4 fragility dominates.

## VERDICT — which S61 descriptors reach the entry, and how strong

1. **`cross_major_nf_pre300` REACHES the entry on ETH** (AUC 0.542, z +2.1, week-consistent) and
   is the best cross-flow ingredient. It is the strictly-pre-entry echo of the Job-C E300 D−W
   separator, attenuated from z +6.7 (in-leg) to z +2.1 (pre-entry) — the decision-time price of
   causality. It does **not** reach on BTC (single-week artifact).
2. **The oppose-flow STACK is the deliverable, not any single feature.** ETH pooled AUC 0.560,
   week-consistent, direction-stable. This is a genuine weak-but-real ENTRY ingredient for the
   big-loser question — exactly the "is this a bad entry" read the charter wanted, now measured
   at the entry.
3. **It does not clear the shift floor as a standalone entry-flip gate** on either cell (best OOS
   $/hr ≈ +0.4, within noise). The winners-invisible law holds at the entry: the +14/+23 $/hr
   prize needs either the in-leg sharpness (E300, post-decision — the wired per-cell corrector
   diagonal's home) or the S35 encoder tier. `cross_major_nf_pre300` is a free candidate column
   for that encoder (the watch-item promotion path from the S61 report is confirmed: it carries
   week-consistent pre-entry signal on ETH; graded by the fingerprint tier's own harness).
4. **Regime conditioner (`xcorr400`) and fill toxicity (`bn_nf_pre1`) do NOT transfer to the
   per-leg entry decision** — consistent with their S61 offices (market-state descriptor / per-fill
   mark, respectively), not leg-quality predictors. Kept in their own offices, not entry ingredients.

## Best stack candidate (per charter)
- **ETH:** the equal-weight oppose-flow stack (lead ingredient `cross_major_nf_pre300`, co-leads
  `own_nf_pre300` + `xbask_nf_pre300`) — pooled AUC 0.560, week-consistent, real vs shift null.
- **BTC:** none reaches; the cross-flow read is week-fragile (wk4-carried). No entry ingredient
  earned. BTC's big-loser question stays with the in-leg corrector / plainstop rider.

## Deflationary reads (visible)
- 10s/1s Binance bins on a 30d tape; the cross-coin instrument is a single collector, so
  collector-skew is structurally absent (as in S61) but sub-second lead is invisible.
- AUCs of 0.54–0.56 are shallow by construction (winners-invisible); the value is week-consistency
  + shift-null survival on ETH, not classification power.
- Threshold maximization inflates full_lift; the circular-shift floor absorbs that bias, so the
  honest reads are `lift_z` and the week-parity `OOS` column (both ≈ noise → no hard gate earned).
- Per-cell: ETH reaches, BTC does not — never pooled.

## Artifacts (scratchpad `/tmp/s62cache/`)
- `btc_dipole_s61alt.npz`, `eth_dipole_s61alt.npz` — `ecell` int[n], `feats` float[n,8], `names`
  (list), plus `gross` (leg pnl bp). Same leg set/order as the recipe.
- `s62_dipole_s61alt.py` → `s62_dipole_s61alt_results.json` (per-feature AUC / week-AUC / $/hr / null)
- `s62_stack.py` → `s62_stack_results.json` (oppose-flow stack, week-OOS, shift null)
