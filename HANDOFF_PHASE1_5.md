# Markets / dipole — Phase 1.5 spec: actor-aware regime classifier

**Date**: 2026-05-04
**From**: Architect (Claude) + Code, with Greg's domain calibration
**To**: Code (for implementation when triggered)
**Branch**: `davisai1974/markets @ claude/new-session-o3vnm`
**Status**: GATED on Phase 1 (HANDOFF_TO_CODE.md) producing baseline structure. Do NOT start until Phase 1's 4hr trajectory report exists with at least 8 chunks and gate B passing.

## Scope

Phase 1.5 sits between Phase 1 (dipole trajectory baseline) and Phase 2 (autoresearch). It does NOT replace Phase 1's encoder; it ADDS features on top, then re-runs analysis on the same collected bins so we can compare baseline vs enriched on identical data.

Goal: turn the binary `contamination_flag` into a **6-class regime classifier** that distinguishes actor types, because the product output isn't "is this manipulation" — it's "who's driving this move so I know which playbook to run?"

## Why this phase exists (the framing the canary missed)

Greg's energy-trading calibration:

> Whale moves and herd moves are both **real** price moves, not noise. The right response depends on which is happening. Whale-driven: get out of the way OR piggyback their flow. Herd-driven: fade after overshoot. Wash trades: exclude entirely. Right-but-offside is most dangerous in illiquid crypto, where one or two big players can dictate price regardless of fundamentals — knowing whether you're trading against a whale, a herd, or organic flow is "the holy grail" for crypto retail.

Phase 1 fails to distinguish these. Its `contamination_flag` would mark both panic and wash trading as "exclude" — losing the most informative regime (panic) and treating whale activity as if it didn't matter.

## 6-class regime taxonomy

| Regime | Driver | Playbook |
|---|---|---|
| ORGANIC_TWO_SIDED | balanced flow | sit out / no edge |
| WHALE_UP | one big buyer | piggyback if early, get out of way if late, fade when their inventory is exhausted |
| WHALE_DOWN | one big seller | mirror of WHALE_UP |
| HERD_UP | FOMO / panic buy | follow with tight stops; fade after overshoot |
| HERD_DOWN | panic sell / capitulation | fade after capitulation |
| WASH_PAIRED | self-trades / coordinated wash | exclude — no real price discovery |

## New encoder features (six additions)

All operate within a single `MarketChunk` and are appended to the existing 64D embedding (no removal of existing features — the baseline trajectory must stay comparable).

### F1. Dipole persistence — `dipole_autocorr_lag1`

Lag-1 autocorrelation of bar-level dipole within the chunk.

```
d_t = (buy_vol_t - sell_vol_t) / (buy_vol_t + sell_vol_t + eps)  for each bar t
dipole_autocorr_lag1 = corr(d[:-1], d[1:])
```

High value (> 0.5) = sustained one-side pressure, the WHALE_UP / WHALE_DOWN signature. Low value (~ 0) = independent bar-to-bar flow, the ORGANIC signature.

### F2. Dipole oscillation peak — `dipole_spectral_peak_freq` and `dipole_spectral_peak_power`

FFT of the bar-level dipole series within the chunk. Report the dominant non-DC frequency and its normalized power.

```
mags = |FFT(d - mean(d))|
peak_idx = argmax(mags[1:]) + 1
peak_freq = peak_idx / len(d)
peak_power = mags[peak_idx]^2 / sum(mags^2)
```

High peak power at a non-trivial frequency = the chunk has a periodic flow pattern, the range-trading whale signature.

### F3. Kyle's lambda proxy — `price_impact_per_unit_volume`

Cumulative absolute price move relative to total trade volume within the chunk.

```
total_volume = sum(buy_vol + sell_vol over bars)
price_move = |close[-1] - close[0]| / close[0]
kyle_proxy = price_move / (total_volume + eps)
```

Low value with high volume = absorption (someone soaking, possibly iceberg / whale). High value with low volume = thin book reaction. The whale-absorption signature is uniquely low kyle_proxy.

### F4. Trade-size multimodality — `size_distribution_n_modes`

Within the chunk, collect all individual trade sizes. Run a kernel density estimate (Gaussian KDE, Silverman bandwidth) and count peaks.

```
trade_sizes = [size for trade in chunk_trades]
kde = gaussian_kde(log(trade_sizes), bw_method='silverman')
peaks = local maxima of kde over a uniform grid
n_modes = len(peaks)
```

n_modes >= 2 with a peak at non-typical size = whale chunking signature (their order broken into similar-sized pieces). n_modes = 1 with smooth Pareto tail = organic / herd.

Note: requires per-trade granular data, not just aggregated 1-sec bins. Either retain the raw trade list per chunk during collection, or store a histogram per bin.

### F5. Inter-trade burstiness — `interarrival_burstiness`

Coefficient of variation of inter-trade arrival times. For a Poisson process (independent arrivals), CV = 1. CV > 1 = bursty / clustered (Hawkes self-excitation). CV < 1 = anti-bursty / regular.

```
arrivals = sorted([trade.timestamp for trade in chunk_trades])
deltas = diff(arrivals)
burstiness_cv = std(deltas) / mean(deltas)
```

CV > 1.5 = whale-like clustering. CV ~ 1 = herd-like (independent traders). CV < 0.5 = regular (rare; possibly bot scheduling).

### F6. Cross-venue lead-lag — `cross_venue_dipole_corr_lag`

Requires Kraken collection to be running in parallel and aligned to wall-clock minute (already in plan via `kraken_btcusd_collector.py`).

For each bar, compute `coinbase_dipole_t` and `kraken_dipole_t` aligned by wall-clock minute. Within the chunk, compute Pearson correlation at lags k ∈ {-3, -2, -1, 0, 1, 2, 3}. Report the lag with the maximum |correlation| and the value.

```
lag_correlations = {k: pearson(cb_dipole, kr_dipole.shift(k)) for k in -3..+3}
peak_lag = argmax_k |lag_correlations[k]|
peak_corr = lag_correlations[peak_lag]
```

`peak_lag != 0` with `|peak_corr| > 0.3` = single-venue origin (one venue leads the other). Whale signature on the leading venue. `peak_lag = 0` with `|peak_corr| > 0.5` = multi-venue simultaneity, herd signature.

## Classifier

Rules-based first (interpretable, debuggable). Migrate to DPGMM via `task_meta_learner` once enough labeled chunks accumulate from manual review.

```python
def classify_regime(features) -> RegimeLabel:
    f = features  # encoded MarketChunk

    # WASH_PAIRED first (most disqualifying)
    if (f.dipole_autocorr_lag1 < -0.3
        and f.realized_vol < 0.3 * baseline_rv
        and f.range_atr < 0.3 * baseline_range):
        return WASH_PAIRED

    # WHALE classes (sustained one-side or absorption)
    if f.dipole_autocorr_lag1 > 0.5 and abs(f.mean_dipole) > 0.4:
        return WHALE_UP if f.mean_dipole > 0 else WHALE_DOWN
    if f.kyle_proxy < 0.3 * baseline_kyle and f.volume_zscore > 1.5:
        # absorption: high volume, low price move
        return WHALE_UP if f.mean_dipole > 0 else WHALE_DOWN
    if f.size_distribution_n_modes >= 2 and f.interarrival_burstiness > 1.5:
        return WHALE_UP if f.mean_dipole > 0 else WHALE_DOWN
    if f.cross_venue_peak_lag != 0 and abs(f.cross_venue_peak_corr) > 0.3:
        # single-venue origin, regardless of other features
        return WHALE_UP if f.mean_dipole > 0 else WHALE_DOWN

    # HERD classes
    if f.volume_zscore > 2.0 and f.realized_vol > 2.0 * baseline_rv:
        return HERD_UP if f.mean_dipole > 0 else HERD_DOWN

    return ORGANIC_TWO_SIDED
```

`baseline_rv`, `baseline_range`, `baseline_kyle` are running 24-hour medians per asset/venue, computed offline and refreshed daily. Stored alongside the encoder.

## Phase 1.5 stop gates

For Phase 1.5 to be declared productive:

- **G. Classifier diversity** — On the Phase 1 corpus, the classifier produces ≥ 4 distinct regime classes across chunks (not collapsing to one or two). Distribution shouldn't be uniform either; ORGANIC should be modal (~50–70%) but other classes should be present with non-trivial counts.

- **H. Cross-venue regime agreement** — On wall-clock minutes where both Coinbase and Kraken have non-trivial flow, regime classifications agree on ≥ 60% of minutes. Disagreement isolates true single-venue events (which is what we want WHALE-on-one-venue to look like).

- **I. Per-regime predictive differentiation** — Forward predictive R² (chunk-level dipole vs next-chunk return) differs significantly by regime class. WHALE classes should show stronger directional persistence than ORGANIC; HERD classes should show overshoot-then-revert. If all classes have identical predictive R², the regime decomposition isn't adding value over raw dipole.

G alone = classifier is functional, ship it.
G + H = cross-venue confirmation works as a reliability filter.
G + H + I = regime decomposition adds predictive value beyond raw dipole — this is the holy grail signal.

G failure = classifier rules need recalibration (likely thresholds).
H failure = either Kraken too sparse, or single-venue activity dominates (interesting in itself).
I failure = the regime taxonomy isn't the right cut for this data — fall back to DPGMM auto-discovery.

## Concrete next actions when triggered

1. **Edit `markets_adapter.py`**: add F1–F5 to `MarketChunkEncoder._extract`. Bump `n_summary` accordingly. Keep `d_enc=64` by reducing FFT coefficient block by 6 to make room.
2. **Edit collection scripts** to retain per-trade granular data (sizes, timestamps) per 1-sec bin, since F4 and F5 need it. Currently we aggregate to bin totals only.
3. **New file `cross_venue_aligner.py`**: load both Coinbase and Kraken bins, align by wall-clock minute, output aligned-bar pairs for F6 computation.
4. **New file `regime_classifier.py`**: implement the rule-based classifier above, with thresholds calibrated from a 24-hour offline run as baselines.
5. **New file `phase1_5_run.py`**: re-run Phase 1's analyze() on the same collected Phase 1 bins, but with the enriched encoder. Compare per-chunk regime labels, contamination decisions, and predictive R² baseline-vs-enriched.
6. **Output**: per-chunk JSON with regime label + features; aggregate report on G/H/I gates; trajectory plot colored by regime class.

## Discord signal format (product output preview)

What the closed-group Option E signal feed posts when the classifier fires:

```
[markets-watch] BTC-USD @ 14:32 UTC
WHALE_UP signature on Coinbase, 8 min in
  - dipole_autocorr_lag1 = 0.71 (sustained one-side pressure)
  - kyle_proxy below baseline (absorption pattern)
  - cross-venue: Kraken organic, lag = +2 min (CB leads)
playbook: late-entry NOT recommended; watch for inventory exhaustion
  near $X (round-number magnet); fade-bias if mean reverts to 8min VWAP
confidence: 0.74 (Bayesian posterior, 1000-perm calibrated)
```

This format is meaningfully more useful and meaningfully more sellable than a raw buy/sell signal.

## Open questions for Greg / Desktop before triggering

1. **Per-trade retention overhead**: F4 and F5 need per-trade timestamps + sizes within each chunk. Storage cost: ~10x current bin size. Acceptable? Alternative: pre-aggregate to histogram bins (size deciles, time deciles) at collection time.
2. **Baseline period**: F3 (Kyle's lambda) and the regime thresholds need a baseline period for "normal" values. 24 hours? 7 days? Per-hour-of-day? US-equity-hours-only?
3. **DPGMM migration timing**: at what point do we trust the auto-taxonomy more than the rules? Need ≥ N labeled chunks. Set N = 200, or some other criterion?
4. **Cross-venue with sparse Kraken**: if Kraken stays at ~35× thinner than Coinbase, F6 will be unreliable for many minutes. Fall back to BTC/USDT? Average across all Kraken pairs? Skip F6 when Kraken volume is below threshold?

## Save locations

- `E:\information_layer\markets\HANDOFF_PHASE1_5.md`
- `F:\Factory\knowledge\information_layer\markets\HANDOFF_PHASE1_5.md`
