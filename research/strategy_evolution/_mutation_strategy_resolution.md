# Mutation Strategy Resolution

Created: 2026-05-18T15:31:47.991570Z

- Mutation candidates: 2936
- Promoted mutation opportunities: 2936
- Unique promoted mutation strategies: 376
- Negative mutation evidence: 0
- Unresolved opportunities: 0

## Top Strategies

| Strategy | Promoted mutations | Best R | Contexts |
|---|---:|---:|---|
| `MEAN_REVERSION_CHOP` | 72 | +37.05 | `BTC|bybit|buy|first6h, BTC|bybit|buy|remaining18h, BTC|bybit|sell|first6h, BTC|bybit|sell|remaining18h, BTC|coinbase|buy|first6h, BTC|coinbase|buy|remaining18h, BTC|coinbase|sell|first6h, BTC|coinbase|sell|remaining18h, BTC|kraken|buy|first6h, BTC|kraken|buy|remaining18h, BTC|kraken|sell|first6h, BTC|kraken|sell|remaining18h, ETH|bybit|buy|first6h, ETH|bybit|buy|remaining18h, ETH|bybit|sell|first6h, ETH|bybit|sell|remaining18h, ETH|coinbase|buy|first6h, ETH|coinbase|buy|remaining18h, ETH|coinbase|sell|first6h, ETH|coinbase|sell|remaining18h, ETH|kraken|buy|first6h, ETH|kraken|buy|remaining18h, ETH|kraken|sell|first6h, ETH|kraken|sell|remaining18h` |
| `LIQUIDITY_SQUEEZE` | 72 | +31.76 | `BTC|bybit|buy|first6h, BTC|bybit|buy|remaining18h, BTC|bybit|sell|first6h, BTC|bybit|sell|remaining18h, BTC|coinbase|buy|first6h, BTC|coinbase|buy|remaining18h, BTC|coinbase|sell|first6h, BTC|coinbase|sell|remaining18h, BTC|kraken|buy|first6h, BTC|kraken|buy|remaining18h, BTC|kraken|sell|first6h, BTC|kraken|sell|remaining18h, ETH|bybit|buy|first6h, ETH|bybit|buy|remaining18h, ETH|bybit|sell|first6h, ETH|bybit|sell|remaining18h, ETH|coinbase|buy|first6h, ETH|coinbase|buy|remaining18h, ETH|coinbase|sell|first6h, ETH|coinbase|sell|remaining18h, ETH|kraken|buy|first6h, ETH|kraken|buy|remaining18h, ETH|kraken|sell|first6h, ETH|kraken|sell|remaining18h` |
| `RELATIVE_STRENGTH` | 72 | +27.79 | `BTC|bybit|buy|first6h, BTC|bybit|buy|remaining18h, BTC|bybit|sell|first6h, BTC|bybit|sell|remaining18h, BTC|coinbase|buy|first6h, BTC|coinbase|buy|remaining18h, BTC|coinbase|sell|first6h, BTC|coinbase|sell|remaining18h, BTC|kraken|buy|first6h, BTC|kraken|buy|remaining18h, BTC|kraken|sell|first6h, BTC|kraken|sell|remaining18h, ETH|bybit|buy|first6h, ETH|bybit|buy|remaining18h, ETH|bybit|sell|first6h, ETH|bybit|sell|remaining18h, ETH|coinbase|buy|first6h, ETH|coinbase|buy|remaining18h, ETH|coinbase|sell|first6h, ETH|coinbase|sell|remaining18h, ETH|kraken|buy|first6h, ETH|kraken|buy|remaining18h, ETH|kraken|sell|first6h, ETH|kraken|sell|remaining18h` |
| `VOL_BREAKOUT` | 71 | +27.79 | `BTC|bybit|buy|first6h, BTC|bybit|buy|remaining18h, BTC|bybit|sell|first6h, BTC|bybit|sell|remaining18h, BTC|coinbase|buy|first6h, BTC|coinbase|buy|remaining18h, BTC|coinbase|sell|first6h, BTC|coinbase|sell|remaining18h, BTC|kraken|buy|first6h, BTC|kraken|buy|remaining18h, BTC|kraken|sell|first6h, BTC|kraken|sell|remaining18h, ETH|bybit|buy|first6h, ETH|bybit|buy|remaining18h, ETH|bybit|sell|first6h, ETH|bybit|sell|remaining18h, ETH|coinbase|buy|first6h, ETH|coinbase|buy|remaining18h, ETH|coinbase|sell|first6h, ETH|coinbase|sell|remaining18h, ETH|kraken|buy|first6h, ETH|kraken|buy|remaining18h, ETH|kraken|sell|first6h, ETH|kraken|sell|remaining18h` |
| `BASIS_DISLOCATION` | 47 | +27.79 | `BTC|bybit|buy|first6h, BTC|bybit|buy|remaining18h, BTC|bybit|sell|first6h, BTC|bybit|sell|remaining18h, BTC|coinbase|buy|first6h, BTC|coinbase|buy|remaining18h, BTC|coinbase|sell|first6h, BTC|coinbase|sell|remaining18h, BTC|kraken|buy|first6h, BTC|kraken|buy|remaining18h, BTC|kraken|sell|first6h, BTC|kraken|sell|remaining18h, ETH|bybit|buy|first6h, ETH|bybit|buy|remaining18h, ETH|bybit|sell|first6h, ETH|bybit|sell|remaining18h, ETH|coinbase|buy|first6h, ETH|coinbase|buy|remaining18h, ETH|coinbase|sell|first6h, ETH|coinbase|sell|remaining18h, ETH|kraken|buy|first6h, ETH|kraken|buy|remaining18h, ETH|kraken|sell|first6h, ETH|kraken|sell|remaining18h` |
| `NEWS_BREAKOUT` | 42 | +22.23 | `BTC|bybit|buy|first6h, BTC|bybit|buy|remaining18h, BTC|bybit|sell|first6h, BTC|bybit|sell|remaining18h, BTC|coinbase|buy|first6h, BTC|coinbase|buy|remaining18h, BTC|coinbase|sell|first6h, BTC|coinbase|sell|remaining18h, BTC|kraken|buy|first6h, BTC|kraken|buy|remaining18h, BTC|kraken|sell|first6h, BTC|kraken|sell|remaining18h, ETH|bybit|buy|first6h, ETH|bybit|buy|remaining18h, ETH|bybit|sell|first6h, ETH|bybit|sell|remaining18h, ETH|coinbase|buy|first6h, ETH|coinbase|buy|remaining18h, ETH|coinbase|sell|first6h, ETH|coinbase|sell|remaining18h, ETH|kraken|buy|first6h, ETH|kraken|buy|remaining18h, ETH|kraken|sell|first6h, ETH|kraken|sell|remaining18h` |

## Top Promoted Mutations

| # | Source context | Candidate context | Strategy | Mutation | PnL R | Entry hr |
|---:|---|---|---|---|---:|---:|
| 1 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +37.05 | 0.23 |
| 2 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +37.05 | 0.23 |
| 3 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +37.05 | 0.23 |
| 4 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +36.41 | 0.23 |
| 5 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +36.41 | 0.23 |
| 6 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +36.41 | 0.23 |
| 7 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +34.64 | 9.33 |
| 8 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +34.64 | 9.33 |
| 9 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +34.64 | 9.33 |
| 10 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `LIQUIDITY_SQUEEZE` | `switch_family_or_delay_entry_until_extension_exhausts` | +31.76 | 0.23 |
| 11 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `LIQUIDITY_SQUEEZE` | `delay_entry_until_score_recovers_or_skip` | +31.76 | 0.23 |
| 12 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `LIQUIDITY_SQUEEZE` | `tighten_context_and_retest` | +31.76 | 0.23 |
| 13 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `LIQUIDITY_SQUEEZE` | `switch_family_or_delay_entry_until_extension_exhausts` | +31.21 | 0.23 |
| 14 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `LIQUIDITY_SQUEEZE` | `delay_entry_until_score_recovers_or_skip` | +31.21 | 0.23 |
| 15 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `LIQUIDITY_SQUEEZE` | `tighten_context_and_retest` | +31.21 | 0.23 |
| 16 | `ETH, ETH` | `ETH|coinbase|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +30.15 | 10.92 |
| 17 | `ETH, ETH` | `ETH|coinbase|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +30.15 | 10.92 |
| 18 | `ETH, ETH` | `ETH|coinbase|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +30.15 | 10.92 |
| 19 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `switch_family_or_delay_entry_until_extension_exhausts` | +29.69 | 9.33 |
| 20 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `delay_entry_until_score_recovers_or_skip` | +29.69 | 9.33 |
| 21 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `tighten_context_and_retest` | +29.69 | 9.33 |
| 22 | `ETH, ETH` | `ETH|kraken|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +29.42 | 10.92 |
| 23 | `ETH, ETH` | `ETH|kraken|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +29.42 | 10.92 |
| 24 | `ETH, ETH` | `ETH|kraken|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +29.42 | 10.92 |
| 25 | `BTC, BTC` | `BTC|kraken|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +28.69 | 20.07 |
| 26 | `BTC, BTC` | `BTC|kraken|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +28.69 | 20.07 |
| 27 | `BTC, BTC` | `BTC|kraken|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +28.69 | 20.07 |
| 28 | `BTC, BTC` | `BTC|coinbase|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +28.68 | 20.05 |
| 29 | `BTC, BTC` | `BTC|coinbase|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +28.68 | 20.05 |
| 30 | `BTC, BTC` | `BTC|coinbase|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +28.68 | 20.05 |
| 31 | `BTC, BTC` | `BTC|bybit|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +28.29 | 8.38 |
| 32 | `BTC, BTC` | `BTC|bybit|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +28.29 | 8.38 |
| 33 | `BTC, BTC` | `BTC|bybit|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +28.29 | 8.38 |
| 34 | `ETH, ETH` | `ETH|coinbase|sell|first6h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +28.24 | 2.08 |
| 35 | `ETH, ETH` | `ETH|coinbase|sell|first6h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +28.24 | 2.08 |
| 36 | `ETH, ETH` | `ETH|coinbase|sell|first6h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +28.24 | 2.08 |
| 37 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `VOL_BREAKOUT` | `flip_side_or_wait_for_flip_confirmation` | +27.79 | 0.23 |
| 38 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `RELATIVE_STRENGTH` | `switch_family_or_delay_entry_until_extension_exhausts` | +27.79 | 0.23 |
| 39 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `BASIS_DISLOCATION` | `delay_entry_until_score_recovers_or_skip` | +27.79 | 0.23 |
| 40 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `VOL_BREAKOUT` | `delay_entry_until_score_recovers_or_skip` | +27.79 | 0.23 |
| 41 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `RELATIVE_STRENGTH` | `delay_entry_until_score_recovers_or_skip` | +27.79 | 0.23 |
| 42 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `RELATIVE_STRENGTH` | `tighten_context_and_retest` | +27.79 | 0.23 |
| 43 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `BASIS_DISLOCATION` | `tighten_context_and_retest` | +27.79 | 0.23 |
| 44 | `ETH, ETH` | `ETH|coinbase|buy|first6h` | `VOL_BREAKOUT` | `tighten_context_and_retest` | +27.79 | 0.23 |
| 45 | `ETH, ETH` | `ETH|kraken|sell|first6h` | `MEAN_REVERSION_CHOP` | `flip_side_or_wait_for_flip_confirmation` | +27.39 | 2.08 |
| 46 | `ETH, ETH` | `ETH|kraken|sell|first6h` | `MEAN_REVERSION_CHOP` | `delay_entry_until_score_recovers_or_skip` | +27.39 | 2.08 |
| 47 | `ETH, ETH` | `ETH|kraken|sell|first6h` | `MEAN_REVERSION_CHOP` | `tighten_context_and_retest` | +27.39 | 2.08 |
| 48 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `VOL_BREAKOUT` | `flip_side_or_wait_for_flip_confirmation` | +27.31 | 0.23 |
| 49 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `RELATIVE_STRENGTH` | `switch_family_or_delay_entry_until_extension_exhausts` | +27.31 | 0.23 |
| 50 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `BASIS_DISLOCATION` | `delay_entry_until_score_recovers_or_skip` | +27.31 | 0.23 |
| 51 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `VOL_BREAKOUT` | `delay_entry_until_score_recovers_or_skip` | +27.31 | 0.23 |
| 52 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `RELATIVE_STRENGTH` | `delay_entry_until_score_recovers_or_skip` | +27.31 | 0.23 |
| 53 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `VOL_BREAKOUT` | `tighten_context_and_retest` | +27.31 | 0.23 |
| 54 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `BASIS_DISLOCATION` | `tighten_context_and_retest` | +27.31 | 0.23 |
| 55 | `ETH, ETH` | `ETH|kraken|buy|first6h` | `RELATIVE_STRENGTH` | `tighten_context_and_retest` | +27.31 | 0.23 |
| 56 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `VOL_BREAKOUT` | `flip_side_or_wait_for_flip_confirmation` | +25.98 | 9.33 |
| 57 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `RELATIVE_STRENGTH` | `switch_family_or_delay_entry_until_extension_exhausts` | +25.98 | 9.33 |
| 58 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `BASIS_DISLOCATION` | `delay_entry_until_score_recovers_or_skip` | +25.98 | 9.33 |
| 59 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `VOL_BREAKOUT` | `delay_entry_until_score_recovers_or_skip` | +25.98 | 9.33 |
| 60 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `RELATIVE_STRENGTH` | `delay_entry_until_score_recovers_or_skip` | +25.98 | 9.33 |
| 61 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `VOL_BREAKOUT` | `tighten_context_and_retest` | +25.98 | 9.33 |
| 62 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `BASIS_DISLOCATION` | `tighten_context_and_retest` | +25.98 | 9.33 |
| 63 | `ETH, ETH` | `ETH|bybit|sell|remaining18h` | `RELATIVE_STRENGTH` | `tighten_context_and_retest` | +25.98 | 9.33 |
| 64 | `ETH, ETH` | `ETH|coinbase|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `switch_family_or_delay_entry_until_extension_exhausts` | +25.85 | 10.92 |
| 65 | `ETH, ETH` | `ETH|coinbase|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `tighten_context_and_retest` | +25.85 | 10.92 |
| 66 | `ETH, ETH` | `ETH|coinbase|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `delay_entry_until_score_recovers_or_skip` | +25.85 | 10.92 |
| 67 | `ETH, ETH` | `ETH|kraken|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `switch_family_or_delay_entry_until_extension_exhausts` | +25.22 | 10.92 |
| 68 | `ETH, ETH` | `ETH|kraken|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `delay_entry_until_score_recovers_or_skip` | +25.22 | 10.92 |
| 69 | `ETH, ETH` | `ETH|kraken|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `tighten_context_and_retest` | +25.22 | 10.92 |
| 70 | `BTC, BTC` | `BTC|kraken|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `switch_family_or_delay_entry_until_extension_exhausts` | +24.59 | 20.07 |
| 71 | `BTC, BTC` | `BTC|kraken|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `delay_entry_until_score_recovers_or_skip` | +24.59 | 20.07 |
| 72 | `BTC, BTC` | `BTC|kraken|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `tighten_context_and_retest` | +24.59 | 20.07 |
| 73 | `BTC, BTC` | `BTC|coinbase|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `switch_family_or_delay_entry_until_extension_exhausts` | +24.58 | 20.05 |
| 74 | `BTC, BTC` | `BTC|coinbase|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `delay_entry_until_score_recovers_or_skip` | +24.58 | 20.05 |
| 75 | `BTC, BTC` | `BTC|coinbase|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `tighten_context_and_retest` | +24.58 | 20.05 |
| 76 | `BTC, BTC` | `BTC|bybit|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `delay_entry_until_score_recovers_or_skip` | +24.25 | 8.38 |
| 77 | `BTC, BTC` | `BTC|bybit|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `switch_family_or_delay_entry_until_extension_exhausts` | +24.25 | 8.38 |
| 78 | `BTC, BTC` | `BTC|bybit|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `tighten_context_and_retest` | +24.25 | 8.38 |
| 79 | `ETH, ETH` | `ETH|coinbase|sell|first6h` | `LIQUIDITY_SQUEEZE` | `switch_family_or_delay_entry_until_extension_exhausts` | +24.21 | 2.08 |
| 80 | `ETH, ETH` | `ETH|coinbase|sell|first6h` | `LIQUIDITY_SQUEEZE` | `tighten_context_and_retest` | +24.21 | 2.08 |