# Frankie — actual wired trading-platform datapoint inventory

Purpose: give Frankie the datapoints/calculations that were actually wired into the Markets trading platform, rather than treating the larger discovered/candidate universe as if it were already live-wired.

Source lineage inspected: `claude/crypto-trading-platform-plan-MpqwG`, especially `markets_adapter.py`, `regime_classifier.py`, `odcore/io.py`, `odcore/channels.py`, `odcore/generators.py`, `backend/odcore_store.py`, and the S21/S35/S36 master context.

## Greg's instruction to Frankie

Use this as the concrete wired sheet. Choose from what is actually available here when you need a platform datapoint/calculation.

**If there is a datapoint/calculation you genuinely want for the prebirth / exhaustion / authority-persistence question and it is NOT on this sheet, do not silently substitute something else. Name the missing datapoint/calculation explicitly, say why you want it, and tell Greg it is missing from the wired sheet.**

The larger discovered/candidate fingerprint universe is not to be mislabeled as live-wired. S35 recorded ~1,919 distinctive `cand_sp` coefficient signatures, but the live fingerprint encoder was still blocked from wiring until its onset/canary reproduced correctly. Treat those as candidate/discovered evidence unless a later lawful source proves a given item is actually wired.

## 1. Wired source universe

The OD backend was wired for six concrete source cells:

- BTC / Coinbase (`btc_coinbase`)
- BTC / Kraken (`btc_kraken`)
- BTC / Bybit-perp (`btc_bybit_perp`)
- ETH / Coinbase (`eth_coinbase`)
- ETH / Kraken (`eth_kraken`)
- ETH / Bybit-perp (`eth_bybit_perp`)

## 2. Raw/per-second collector fields actually consumed

From `odcore/io.py` / `BinSeries`:

- `ts`
- `buy` — taker-buy volume
- `sell` — taker-sell volume
- `mid`
- `volume = buy + sell`
- `spread = ask - bid` when bid/ask are present
- `n_trades`
- derived `log_return`
- derived `abs_return`

Collector input also reads `bid` and `ask` to produce `spread`.

## 3. Minute-bar/regime path fields actually consumed

From `markets_adapter.py` / `MarketBar`:

- `ts`
- `close`
- `open_`
- `high`
- `low`
- `volume`
- `buy_vol`
- `sell_vol`
- derived `mid` (= close)
- derived `ofi = buy_vol - sell_vol`
- derived normalized `dipole = (buy_vol - sell_vol)/(buy_vol + sell_vol)`

## 4. MarketFeatures actually produced by the encoder

Core summary / price-flow / spectral features:

- `ret_mean`
- `ret_std`
- `ret_skew`
- `ret_kurt`
- `autocorr_lag1`
- `mean_dipole`
- `mean_ofi`
- `volume_zscore`
- `realized_vol`
- `range_atr`
- `spectral_energy`
- `spectral_entropy`
- `peak_frequency`
- `spectral_centroid`
- `coefficients` — downsampled FFT-magnitude coefficient block in the encoder embedding

Phase-1.5 / persistence / absorption / timing additions:

- `dipole_autocorr_lag1`
- `dipole_peak_freq`
- `dipole_peak_power`
- `kyle_proxy`
- `hour_utc`
- `day_of_week`
- `is_london_lunch`
- `is_us_lunch`
- `is_us_market_hours`
- `chunk_total_volume`

## 5. Channel factory fields actually exposed to OD

From `odcore/channels.py`:

- `taker_buy`
- `taker_sell`
- `volume`
- `log_return`
- `abs_return`
- `spread`
- `mid`

Pair families actually enumerated:

- orderflow: `taker_buy <> taker_sell` within source
- internal: `abs_return <> volume` within source
- cross-venue: same-asset `log_return <> log_return`
- cross-asset: different-asset `log_return <> log_return`

## 6. Regime-classifier calculations actually wired

Directly consumed by the classifier:

- realized-volatility level and ratio to baseline
- `range_atr` vs baseline
- `kyle_proxy` vs baseline
- chunk-volume ratio vs baseline
- `mean_dipole`
- `dipole_autocorr_lag1`
- `dipole_peak_freq`
- `dipole_peak_power`
- London-lunch flag
- U.S.-lunch flag
- U.S.-market-hours/session phase
- cross-venue regime agreement/disagreement multiplier

Classifier states produced:

- `EQUILIBRIUM_TWO_SIDED`
- `WHALE_UP`
- `WHALE_DOWN`
- `HERD_UP`
- `HERD_DOWN`
- `WASH_PAIRED`
- `DEPLETED`
- `UNKNOWN`

## 7. OD signal generators wired into the platform/backtester pool

Standalone OD harness signals:

- `ofi_momentum`
- `ofi_fade`
- `momentum5`
- `dipole_direction` — rolling buy-side entropy `H_a` vs sell-side entropy `H_b`

Bridge generators appended to the adaptive selector:

- `od_dipole_fade`
- `od_dipole_sustained` — `mean_dipole * (1 + abs(dipole_autocorr_lag1))`

## 8. Coupling / lead-lag / dipole calculations actually wired through the backend API

Coupling matrix output:

- pair identity A/B
- `pair_kind`
- lag-0 absolute cross-correlation `cc0`
- structured-coupling verdict `structured`
- `mi_frac`
- chemistry residual fraction `chem_frac`
- `n_windows`

Lead/lag output:

- pair A/B
- `lag_bars`
- `lag_seconds`
- cross-correlation `cc`
- null-relative `z`
- `leader`

Algebraic dipole output:

- asset
- venue
- coefficient `a`
- coefficient `b`
- quadratic coefficient `c`
- fit `r2`
- current direction from `H_a > H_b`
- `n_windows`

Strength-over-time output:

- timestamp
- `mi_slope`
- `mi_slope_r2`
- `chem_frac`

Decoupling output:

- pair
- timestamp
- current `cc`
- coupling `baseline`
- `severity`

## 9. Important NOT-YET-WIRED distinction

Do not confuse discovered/candidate research assets with the wired sheet above.

The S35 master context records roughly 1,919 distinctive `cand_sp` coefficient signatures across 12 isolated asset x venue x side cells. It also states that the live fingerprint encoder failed its reproduction canary and that wiring was BLOCKED until the onset/canary passed. Therefore those signatures are a discovered/candidate universe, not automatically live-wired datapoints.

S36 likewise records divergence/exhaustion as a strong research edge and says the next step was to wire `divergence()` per cell into the regime classifier + fingerprint + sizing. Unless a later lawful source proves that wiring landed, treat it as research/candidate rather than claiming it was already wired in this inspected platform state.

## Frankie response rule

When choosing datapoints for Greg:

1. Prefer exact identities on this wired sheet when they answer the question.
2. If the point you truly want is absent, write `MISSING_FROM_WIRED_SHEET:` followed by its exact desired identity/definition and causal reason.
3. Do not invent an available path.
4. Do not downgrade to a weaker proxy merely because the desired point is missing.
5. Preserve Greg's no-drop / no-truncation / no-averaging / no-smoothing / no-silent-normalization evidence rules for the Frankie historical work.