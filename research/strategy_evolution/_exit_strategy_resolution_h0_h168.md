# Exit Strategy Resolution: h0-h168 Winners

Created: 2026-05-18T16:42:54.443329Z

- Winner Rows: 5616
- Entry Strategy Families: 6
- Bucket Count: 72
- Promoted Buckets: 72
- Trial Buckets: 0
- Exit Profiles Considered: 4
- Exit Profile Bucket Candidates: 288
- Promoted Exit Profile Bucket Candidates: 72

## Exit Profiles Considered

| Profile | Label | Family hint | Base TP1 | Base scale | Base trail |
|---|---|---|---:|---:|---:|
| `basis_dislocation_runner_exits_v1` | Basis dislocation partial take-profit with modest runner | `BASIS_DISLOCATION` | 20.00 | 0.50 | 12.00 |
| `gated_profitable_score_news_exits_v1` | Gate profitable score/news exits before full close | `` | 0.00 | 0.00 | 0.00 |
| `liquidity_squeeze_runner_exits_v1` | Liquidity squeeze small lock with loose runner | `LIQUIDITY_SQUEEZE` | 12.00 | 0.33 | 25.00 |
| `mean_reversion_chop_tight_exits_v1` | Mean reversion tighter scale-out and cleanup | `MEAN_REVERSION_CHOP` | 18.00 | 0.50 | 8.00 |

## By Entry Strategy

| Strategy | Winners | Buckets | Promoted | Suggested exit profile | Median winner bps | P75 winner bps | Median cf30 extra bps |
|---|---:|---:|---:|---|---:|---:|---:|
| `VOL_BREAKOUT` | 991 | 12 | 12 | `gated_profitable_score_news_exits_v1` | 11.11 | 22.17 | 13.42 |
| `BASIS_DISLOCATION` | 959 | 12 | 12 | `basis_dislocation_runner_exits_v1` | 12.47 | 23.37 | 14.11 |
| `RELATIVE_STRENGTH` | 949 | 12 | 12 | `gated_profitable_score_news_exits_v1` | 11.42 | 21.97 | 14.36 |
| `MEAN_REVERSION_CHOP` | 922 | 12 | 12 | `mean_reversion_chop_tight_exits_v1` | 10.94 | 20.82 | 15.62 |
| `NEWS_BREAKOUT` | 916 | 12 | 12 | `gated_profitable_score_news_exits_v1` | 11.46 | 21.97 | 13.62 |
| `LIQUIDITY_SQUEEZE` | 879 | 12 | 12 | `liquidity_squeeze_runner_exits_v1` | 10.97 | 22.29 | 16.33 |

## Top Promoted Buckets

| Bucket | Winners | Suggested profile | TP1 | Scale | Trail | Min hold | Max hold | Median winner bps | Median cf30 extra bps |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `BASIS_DISLOCATION|ETH|Kraken|remaining18h` | 166 | `basis_dislocation_runner_exits_v1` | 6.43 | 0.33 | 7.19 | 15 | 60 | 10.72 | 14.38 |
| `RELATIVE_STRENGTH|ETH|Coinbase|remaining18h` | 165 | `gated_profitable_score_news_exits_v1` | 5.93 | 0.33 | 7.66 | 15 | 60 | 9.88 | 15.31 |
| `VOL_BREAKOUT|ETH|Kraken|remaining18h` | 164 | `gated_profitable_score_news_exits_v1` | 6.03 | 0.33 | 5.27 | 15 | 60 | 10.06 | 10.53 |
| `VOL_BREAKOUT|ETH|Coinbase|remaining18h` | 162 | `gated_profitable_score_news_exits_v1` | 5.96 | 0.33 | 6.49 | 15 | 60 | 9.93 | 12.99 |
| `RELATIVE_STRENGTH|ETH|Kraken|remaining18h` | 157 | `gated_profitable_score_news_exits_v1` | 6.04 | 0.33 | 7.86 | 15 | 60 | 10.07 | 15.73 |
| `BASIS_DISLOCATION|ETH|Coinbase|remaining18h` | 155 | `basis_dislocation_runner_exits_v1` | 6.90 | 0.33 | 6.28 | 15 | 60 | 11.50 | 12.55 |
| `MEAN_REVERSION_CHOP|ETH|Coinbase|remaining18h` | 153 | `mean_reversion_chop_tight_exits_v1` | 6.22 | 0.33 | 7.48 | 15 | 60 | 10.37 | 14.96 |
| `LIQUIDITY_SQUEEZE|ETH|Coinbase|remaining18h` | 152 | `liquidity_squeeze_runner_exits_v1` | 6.24 | 0.33 | 7.48 | 15 | 60 | 10.40 | 14.97 |
| `NEWS_BREAKOUT|ETH|Coinbase|remaining18h` | 143 | `gated_profitable_score_news_exits_v1` | 7.44 | 0.33 | 6.28 | 15 | 60 | 12.41 | 12.56 |
| `NEWS_BREAKOUT|ETH|Kraken|remaining18h` | 143 | `gated_profitable_score_news_exits_v1` | 6.86 | 0.33 | 6.83 | 15 | 60 | 11.44 | 13.67 |
| `MEAN_REVERSION_CHOP|ETH|Kraken|remaining18h` | 135 | `mean_reversion_chop_tight_exits_v1` | 6.79 | 0.33 | 6.80 | 15 | 60 | 11.32 | 13.60 |
| `LIQUIDITY_SQUEEZE|ETH|Kraken|remaining18h` | 131 | `liquidity_squeeze_runner_exits_v1` | 6.85 | 0.33 | 6.84 | 15 | 60 | 11.42 | 13.67 |
| `VOL_BREAKOUT|ETH|Coinbase|first6h` | 103 | `gated_profitable_score_news_exits_v1` | 10.07 | 0.33 | 11.14 | 15 | 60 | 16.78 | 22.29 |
| `MEAN_REVERSION_CHOP|ETH|Bybit|remaining18h` | 99 | `mean_reversion_chop_tight_exits_v1` | 6.61 | 0.33 | 6.01 | 15 | 60 | 11.02 | 12.03 |
| `RELATIVE_STRENGTH|ETH|Kraken|first6h` | 98 | `gated_profitable_score_news_exits_v1` | 9.15 | 0.33 | 9.85 | 15 | 60 | 15.25 | 19.70 |
| `RELATIVE_STRENGTH|ETH|Coinbase|first6h` | 98 | `gated_profitable_score_news_exits_v1` | 8.20 | 0.33 | 9.83 | 15 | 60 | 13.67 | 19.66 |
| `BASIS_DISLOCATION|ETH|Kraken|first6h` | 96 | `basis_dislocation_runner_exits_v1` | 10.50 | 0.33 | 11.98 | 15 | 60 | 17.51 | 23.96 |
| `VOL_BREAKOUT|BTC|Coinbase|remaining18h` | 96 | `gated_profitable_score_news_exits_v1` | 5.28 | 0.50 | 5.00 | 15 | 60 | 8.80 | 4.67 |
| `BASIS_DISLOCATION|ETH|Coinbase|first6h` | 95 | `basis_dislocation_runner_exits_v1` | 11.49 | 0.33 | 13.18 | 15 | 60 | 19.14 | 26.37 |
| `MEAN_REVERSION_CHOP|BTC|Kraken|remaining18h` | 95 | `mean_reversion_chop_tight_exits_v1` | 5.00 | 0.33 | 7.50 | 15 | 60 | 8.12 | 15.01 |
| `NEWS_BREAKOUT|BTC|Kraken|remaining18h` | 94 | `gated_profitable_score_news_exits_v1` | 5.00 | 0.33 | 5.73 | 15 | 60 | 8.17 | 11.45 |
| `NEWS_BREAKOUT|BTC|Coinbase|remaining18h` | 93 | `gated_profitable_score_news_exits_v1` | 5.31 | 0.33 | 5.65 | 15 | 60 | 8.85 | 11.30 |
| `BASIS_DISLOCATION|BTC|Coinbase|remaining18h` | 93 | `basis_dislocation_runner_exits_v1` | 5.29 | 0.50 | 5.00 | 15 | 60 | 8.82 | 5.10 |
| `LIQUIDITY_SQUEEZE|BTC|Kraken|remaining18h` | 93 | `liquidity_squeeze_runner_exits_v1` | 5.00 | 0.33 | 7.89 | 15 | 60 | 8.12 | 15.79 |
| `RELATIVE_STRENGTH|BTC|Coinbase|remaining18h` | 90 | `gated_profitable_score_news_exits_v1` | 5.80 | 0.50 | 5.00 | 15 | 60 | 9.66 | 8.63 |
| `LIQUIDITY_SQUEEZE|ETH|Bybit|remaining18h` | 88 | `liquidity_squeeze_runner_exits_v1` | 6.83 | 0.33 | 8.88 | 15 | 60 | 11.39 | 17.76 |
| `VOL_BREAKOUT|ETH|Kraken|first6h` | 86 | `gated_profitable_score_news_exits_v1` | 9.60 | 0.33 | 12.43 | 15 | 60 | 16.01 | 24.86 |
| `VOL_BREAKOUT|BTC|Kraken|remaining18h` | 82 | `gated_profitable_score_news_exits_v1` | 5.00 | 0.33 | 5.59 | 15 | 60 | 7.45 | 11.19 |
| `NEWS_BREAKOUT|ETH|Coinbase|first6h` | 81 | `gated_profitable_score_news_exits_v1` | 8.44 | 0.33 | 11.95 | 15 | 60 | 14.07 | 23.90 |
| `MEAN_REVERSION_CHOP|BTC|Coinbase|remaining18h` | 81 | `mean_reversion_chop_tight_exits_v1` | 5.92 | 0.33 | 7.34 | 15 | 60 | 9.86 | 14.68 |
| `NEWS_BREAKOUT|ETH|Bybit|remaining18h` | 78 | `gated_profitable_score_news_exits_v1` | 7.48 | 0.50 | 5.90 | 15 | 60 | 12.47 | 11.81 |
| `LIQUIDITY_SQUEEZE|BTC|Coinbase|remaining18h` | 78 | `liquidity_squeeze_runner_exits_v1` | 6.02 | 0.33 | 8.84 | 15 | 60 | 10.03 | 17.68 |
| `LIQUIDITY_SQUEEZE|ETH|Kraken|first6h` | 76 | `liquidity_squeeze_runner_exits_v1` | 8.58 | 0.33 | 12.69 | 15 | 60 | 14.30 | 25.39 |
| `MEAN_REVERSION_CHOP|ETH|Kraken|first6h` | 76 | `mean_reversion_chop_tight_exits_v1` | 8.58 | 0.33 | 12.69 | 15 | 60 | 14.30 | 25.39 |
| `BASIS_DISLOCATION|BTC|Kraken|remaining18h` | 76 | `basis_dislocation_runner_exits_v1` | 5.60 | 0.33 | 5.42 | 15 | 60 | 9.33 | 10.84 |
| `RELATIVE_STRENGTH|BTC|Kraken|remaining18h` | 76 | `gated_profitable_score_news_exits_v1` | 5.00 | 0.33 | 5.53 | 15 | 60 | 7.72 | 11.06 |
| `NEWS_BREAKOUT|ETH|Kraken|first6h` | 70 | `gated_profitable_score_news_exits_v1` | 9.18 | 0.33 | 13.46 | 15 | 60 | 15.31 | 26.93 |
| `MEAN_REVERSION_CHOP|ETH|Coinbase|first6h` | 65 | `mean_reversion_chop_tight_exits_v1` | 7.62 | 0.33 | 9.52 | 15 | 60 | 12.71 | 19.05 |
| `MEAN_REVERSION_CHOP|BTC|Bybit|remaining18h` | 65 | `mean_reversion_chop_tight_exits_v1` | 5.13 | 0.33 | 6.61 | 15 | 60 | 8.56 | 13.21 |
| `VOL_BREAKOUT|BTC|Bybit|remaining18h` | 65 | `gated_profitable_score_news_exits_v1` | 5.00 | 0.33 | 7.39 | 15 | 60 | 7.99 | 14.77 |

## Notes

- All 72 buckets met the promoted threshold of at least 5 winners.
- Resolver-only positives were not used for exit params because they lack realized exit/counterfactual rows.
- The live default `exit_params.json` was not overwritten; promoted output is a separate artifact for review or adoption.