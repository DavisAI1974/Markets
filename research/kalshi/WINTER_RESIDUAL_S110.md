# WINTER_RESIDUAL_S110 — gas_call_residual in COLD, the regime the claim lives in

S110 step 5. Closes the P0.8 gap (S109_MERGE_PROPOSAL_G22.md): the S109 residual test covered only
WARM blocks (g20-g23, mean gw_hdd 0.12-0.72) and the verdict was UNTESTED IN ITS CLAIMED REGIME
(Greg S109: "Residual is only going to drive it in cold or getting cold times"). This run puts the
seven walked-winter blocks G7-G13 under the same instrument.

Runner: `gas_call_residual.py --winter-store` (additive mode; the default warm path is untouched).

## What was run, and the honesty constraints

- **Grid**: harvested DIRECTLY from the feed Q store `data/grid_stack/grid_stack.json.gz`
  (2019-01-01..2026-07-20 — all winter days present). The winter states grp7..grp13 predate feed Q
  and carry no grid_stack blocks, which is why the default state-harvest path can never see winter.
  Field mapping and the burn estimate reuse `grid_stack._ba_read` verbatim — identical to the
  staged blocks by construction. Residual = demand − solar − wind − nuclear (US48), same definition
  and units (kMWh) as the warm run.
- **RETRIEVAL-VINTAGE CAVEAT (the headline constraint)**: the store is a snapshot retrieved
  2026-07-20. This run is therefore the **MECHANISM (contemporaneous) view ONLY** — it tests
  whether the subtractor is real, and is NOT a forecast. The `a_res(+2d)` column applies the feed's
  wall (period = latest ≤ X−2 calendar days, mirroring `grid_stack_asof`) as a labeled
  APPROXIMATION of decision-time alignment: the alignment is wall-correct, the vintage is not (EIA
  revises early prints at the margin). A true decision-time verdict needs restaged states.
- **Day-moves**: from the SCORED blind files `renders/ng_refine_s95/g{7..13}_score.json`, field
  `actual_day_move_usd` (gap-inclusive). The task sheet's nominal source (`forecasts/grp{7..13}.json`)
  predates that field, and `group_config.GROUPS` no longer carries the winter groups — the score
  files are the operative source. g11_score.json is the older format; its day move is derived as
  `gap_actual + net_actual`, an identity verified exact on g7/g9/g12 before use.
- **Weather**: realized gw_hdd/gw_cdd from `weather/nws_temp/gw_degree_days.json` — complete on all
  seven windows. No historical forecast degree-days exist in this path, so the approx-DT column is
  residual-only.
- Join coverage was full: every differenced session pair joined (n = block days − 1).

These are proper COLD cells: block mean gw_hdd 13.6 / 18.4 / 24.3 / 20.6 / 34.6 / 25.5 / 20.1
(g7..g13) vs 0.12-0.72 across the entire warm test.

## Per-block cells — MECHANISM (contemporaneous) view

Sign = fraction of days where the differenced quantity and the day move share sign. Never pooled.

| grp | n | mean hdd | dd sign | res sign | corr dd | corr res | power |
|---|---|---|---|---|---|---|---|
| g7  | 9  | 13.6 | 3/9   | 5/9  | -0.300 | -0.009 | n<10, corr not a result |
| g8  | 9  | 18.4 | 7/9   | 2/9  | +0.397 | +0.086 | n<10, corr not a result |
| g9  | 19 | 24.3 | 11/19 | 8/19 | -0.090 | -0.125 | |
| g10 | 10 | 20.6 | 5/10  | 6/10 | +0.013 | +0.210 | |
| g11 | 11 | 34.6 | 9/11  | 8/11 | +0.079 | +0.087 | |
| g12 | 11 | 25.5 | 7/11  | 8/11 | +0.302 | +0.194 | |
| g13 | 11 | 20.1 | 6/11  | 6/11 | +0.205 | -0.444 | |

Approx decision-time residual (+2d wall, retrieval vintage — labeled approximate): sign 6/9, 5/9,
8/19, 6/10, 4/11, 4/11, 6/11; corr +0.549, +0.274, -0.075, -0.222, -0.178, -0.371, +0.317. Sign-split
and sign-unstable across cells — no decision-time usability shown, and the vintage caveat means this
column cannot decide that question anyway.

## Per-block cells — CUMULATIVE (slope-horizon) view

The claim as Greg stated it is a slope claim ("gentle changes over time"), so the block-arc view is
the horizon where it must show up. Burn = est_gas_burn_bcfd (gas MWh x 7,900 Btu/kWh / 1.035e9,
the feed's stated method).

| grp | days | dd first→last | cum move | resid first→last (kMWh) | burn f→l (Bcf/d) | aligned? |
|---|---|---|---|---|---|---|
| g7  | 10 | 8.9 → 17.5 (+8.6)   | -580   | 6,153 → 6,844 (+691)    | 28.4 → 31.8 (+3.4) | no |
| g8  | 10 | 16.4 → 27.8 (+11.4) | +4,510 | 7,567 → 9,031 (+1,463)  | 36.5 → 42.5 (+6.0) | YES |
| g9  | 20 | 26.9 → 27.4 (+0.5)  | -6,950 | 8,429 → 8,198 (-231)    | 39.8 → 37.7 (-2.1) | sign yes, magnitude no |
| g10 | 11 | 26.7 → 26.5 (-0.2)  | -5,370 | 7,730 → 7,832 (+102)    | 32.5 → 33.4 (+0.9) | no (flat resid, big move) |
| g11 | 12 | 31.2 → 36.9 (+5.8)  | +17,140 | 7,948 → 9,710 (+1,761) | 34.1 → 40.7 (+6.6) | YES (the squeeze) |
| g12 | 12 | 35.3 → 21.1 (-14.2) | -13,320 | 9,782 → 7,535 (-2,247) | 43.0 → 33.3 (-9.7) | YES (the release) |
| g13 | 12 | 18.5 → 16.6 (-1.9)  | -2,270 | 6,649 → 6,551 (-98)     | 29.7 → 30.1 (+0.4) | sign yes (tiny slope) |

Warm comparison at the same horizon (S109 default mode): g20 +589 kMWh / +1,860; g21 -434 / -220;
g22 +1,307 / +470; g23 +864 / -3,290. The one warm block with a cold-sized residual slope (g22,
+1,307) produced only +470; g23's +864 came with -3,290 against it.

Sanity anchor: the g11 burn ramp reproduces the S98 freeze-sweep numbers (28.3 → 41.1 Bcf/d era;
here 34.1 → 40.7 first→last with the 41.1-class peak mid-block), so the join reads the same store
the sweep did.

## Verdict, shaped as P0.8's options

**At DAY horizon: outcome (b) — inert in cold too.** Per-day residual sign agreement sits at or
near chance in five of seven cells (5/9, 6/10, 6/11, 8/19-below, 2/9-below), weakly positive only in
g11 and g12 (8/11 each, corr +0.087/+0.194 — weak). Correlations are small and sign-unstable
(-0.444 to +0.210). The residual does not sort single-day moves in cold any better than it did in
warm. The g9 cell is below chance (8/19) — residual-up days were price-DOWN days in the
surplus-collapse December, i.e. positioning overrode the call, the same story S96 recorded as
"sold the cold."

**At SLOPE horizon: the claim lives — outcome (a), scoped.** Every cold block with a large residual
slope (|Δ| ≥ ~1,400 kMWh: g8 +1,463, g11 +1,761, g12 -2,247 — 3/3) delivered a four-figure
same-signed cumulative move (+4,510, +17,140, -13,320), including both of the winter's biggest
arcs (the g11 squeeze and the g12 release). The comparable warm slope (g22 +1,307) was absorbed
(+470). That is the regime asymmetry Greg's claim asserts: in cold the system has no slack, so a
large multi-day call change transmits to price; in warm it is absorbed. The converse also holds
honestly: flat-residual cold blocks still moved four figures (g9 -6,950, g10 -5,370) on
positioning, not the call — the residual is a driver among drivers, never the sole driver, and it
contributes a lean, not a day timer.

**Increment over raw degree-days is thin: one cell.** dd slope is sign-aligned in the same three
big blocks (+11.4, +5.8, -14.2), so the subtractor's added value at slope horizon shows up only in
g9 (dd flat +0.5 while residual -231 agreed with the -6,950 sell) plus the unit coherence of the
burn estimate (Bcf/d, the desk quantity). g7 is a counterexample against both (dd +8.6 and residual
+691, price -580).

**Strict label per the power discipline: (c) applies to every per-day correlation** (n=9-19 per
cell, two cells under n=10) **and to the slope read as a coefficient** (n=7 blocks, and only 3
large-slope instances). Nothing here supports a coefficient. What the cells DO support, stated as
sign evidence: per-day inert in cold (b); slope-horizon transmission present in cold and absent in
warm at matched slope size, 3/3 vs 0/1 (a, scoped to slope horizon).

**Consequence for the play (matches P0.8 item 4 and the S110 merge's residual-tilt handoff):** if
a residual play is ever written, scope it to cold / turning-cold, at BLOCK-LEAN (multi-day slope)
horizon only, never as a day-move caller; the warm null and the cold per-day null are both forward
evidence to carry with it, and the decision-time arm is still OPEN until winter states are restaged
with proper knowable_from walls (this run's store reads are retrieval-vintage, mechanism-view only).
