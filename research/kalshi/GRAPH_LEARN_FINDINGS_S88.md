# GRAPH-AND-LEARN FINDINGS — the forecaster's exploratory pass (S88)

The exploratory pass from `FORECAST_AGENT_DIRECTIVE_S88.md` method step 2 (graph the actual NYMEX trade
curves + how the pre-event pieces line up with them, per commodity), run by a bounded subagent on the 24
weekly MBP-10 release windows. This is the empirical basis for the bucket continuation table
(`bucket_continuation.py`). PROVISIONAL, machinery-validation + warm-season read ONLY.

## Corpus + hard caveats (read first)
- 24 weekly MBP-10 release windows: 12 CL (EIA-crude, Wed) + 12 NG (EIA-storage, Thu), Apr-Jul 2026. Each
  event joined to realized NWS gas-weighted temp regime + leakage-safe D-1 forward-curve regime. Baseline
  leakage gate PASS both. n=12/commodity, ONE warm season, ZERO winter analogs.
- **Three axes COLLAPSE in this corpus** (only the year pull fixes them):
  1. Every event is a RELEASE day -> the whole corpus is the single storage/inventory-day cell; weekday-type
     is degenerate here.
  2. Curve-regime label degenerate: CL backwardation 12/12 (Hormuz-tight); NG contango 10/12. Only the
     continuous slope depth varies.
  3. Temp, curve-depth, calendar are COLLINEAR (all the April->July ramp: gw_hdd 9->0, gw_cdd 0->18, CL
     slope1 -5.4->-0.25). Cannot separate at n=12.
- **The only axes ORTHOGONAL to the calendar ramp are surprise sign/magnitude and microstructure
  (imbalance, coiled volume).** Those are where the non-confounded structure lives.

## CL (crude) — release is a WEAK catalyst
- Shape: peak_usd min $410 / p50 $770 / max $2640 (06-17 Hormuz). fast_capture p50 = 0.27, peaked_fast 0/12
  -> confirms S85 "CL slow-bleed." time_to_peak p50 ~1345s. Magnitude is a slow grind or an exogenous
  mid-window jump (Hormuz peak at +1030s, unrelated to the print). EIA-crude print = weak t=0 anchor.
- Pieces (Spearman, n=12): **aligned_imb_push -> sustain_s = +0.52** (reproduces S86; cleanest non-calendar
  signal — book supporting the push = longer run). abs_surprise -> fast_capture = +0.50. imb_R leans the
  move only 0.3 of the time (detector, not direction). Surprise cell near-degenerate: 10/12 miss|small on
  the seasonal proxy (needs REAL consensus).

## NG (natgas) — release IS the catalyst, front-loaded, bimodal on surprise size
- Shape: peak_usd min $290 / p50 $505 / max $900. fast_capture p50 = 0.66, peaked_fast 2/12 -> confirms S85
  "NG front-loads ~66% in 60s." time_to_peak BIMODAL (fast-spike 2-63s vs slow-grind 1462-1781s), p50
  misleading.
- **Headline (orthogonal to calendar): surprise MAGNITUDE selects the shape.** Both fast-peak days are
  beat|big (instant spike then done); abs_surprise -> sustain_s = -0.46, signed_surprise -> fast_capture =
  +0.46. Big surprise -> fast spike / short hold; small-moderate surprise -> slower grind that SUSTAINS (the
  leg worth holding).
- **Coiled pre-release volume -> bigger move**, per-cell Spearman(pre_vol, peak_bps) negative in all 3 NG
  cells (-1.0/-0.5/-0.6); reproduces S86. Pooled washes to -0.09 -> per-cell normalization load-bearing.
- gw_precip/gw_cdd -> sustain_s ~ -0.66/-0.46 (hotter/wetter -> shorter run) — suggestive summer cooling-load
  axis but calendar-confounded at n=12; carry to the year corpus.

## Structure vs too-thin
- CL carries: aligned_imb_push->sustain (+0.52), abs_surprise->fast_capture (+0.50). Else slow-bleed/exogenous.
- NG carries: surprise-magnitude->shape, coiled-volume->magnitude (per-cell).
- Too thin/degenerate: weekday-type, curve-regime label, temp-vs-calendar separation, CL big cells (n<=2),
  NG miss|big (n=1), any 4-way cell.

## Recommendation — the bucket continuation table keys
- **CL (inventory-day cell):** (1) surprise sign x magnitude (degenerate on proxy; needs real consensus) —
  primary tabulated outcome = minute-scale CONTINUATION, not 60s capture (~0.27 flat). (2) **aligned_imb_push
  = the CL hold-length key** (+0.52). (3) geopolitical/vol regime as its OWN cell (Hormuz tail must not pool).
  (4) season/curve-depth placeholder for the year. Tabulate peak_usd dist, fast_capture, retention, sustain_s.
- **NG (storage-day cell):** (1) **surprise-MAGNITUDE {big|small} x sign = the shape/hold-length selector**
  (big->fast-spike+short; small->grind+long). (2) coiled pre-release volume {quiet|active} split at per-cell
  median (quiet->bigger). (3) demand-temp regime + summer precip as CONDITIONING dims, gated, populated by
  the year. (4) book exhaustion as secondary fade flag. Tabulate peak_usd dist, fast_capture (~0.66),
  peaked_fast frac, retention, sustain_s, bimodal time_to_peak.
- **Cross-commodity: never pool** — aligned_imb_push->sustain is CL's key but weak/negative on NG;
  surprise-magnitude->shape is NG's key but CL's surprise cell is degenerate. Discovery per-commodity,
  per-cell. Warm-season only; the real analog library is the continuous-year MBP-10 pull.
