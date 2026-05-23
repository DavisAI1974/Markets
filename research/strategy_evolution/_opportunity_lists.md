# Opportunity Lists

Created: 2026-05-18T15:24:16.089322Z

- Tradable opportunities: 5622
- Unresolved opportunities: 0
- Resolver tradable opportunities: 6
- Negative evidence memory: `research\strategy_evolution\_negative_evidence_memory.json`
- Opportunity mutation workbench: `research\strategy_evolution\_opportunity_mutation_workbench.json`

## Top Tradable

| # | Context | Strategy | Source | PnL R | PnL USD | Replay hr |
|---:|---|---|---|---:|---:|---:|
| 1 | `BTC|kraken|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `exact_context_resolver` | +28.69 | $+17.21 | 14.07 |
| 2 | `BTC|bybit|sell|first6h` | `MEAN_REVERSION_CHOP` | `exact_context_resolver` | +21.27 | $+12.76 | 2.97 |
| 3 | `BTC|coinbase|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `opportunity_ledger` | +20.28 | $+121.67 | 153.17 |
| 4 | `BTC|coinbase|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +20.12 | $+140.84 | 153.17 |
| 5 | `BTC|bybit|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `opportunity_ledger` | +19.93 | $+119.59 | 153.17 |
| 6 | `ETH|bybit|buy|first6h` | `MEAN_REVERSION_CHOP` | `exact_context_resolver` | +19.83 | $+11.90 | 0.18 |
| 7 | `BTC|bybit|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +19.83 | $+138.79 | 153.17 |
| 8 | `ETH|bybit|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +18.70 | $+130.91 | 153.17 |
| 9 | `ETH|bybit|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `opportunity_ledger` | +18.03 | $+108.17 | 153.17 |
| 10 | `ETH|kraken|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `opportunity_ledger` | +16.94 | $+101.63 | 151.33 |
| 11 | `ETH|kraken|sell|remaining18h` | `MEAN_REVERSION_CHOP` | `opportunity_ledger` | +16.40 | $+98.38 | 151.17 |
| 12 | `ETH|bybit|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +16.28 | $+113.98 | 151.33 |
| 13 | `BTC|bybit|buy|first6h` | `MEAN_REVERSION_CHOP` | `exact_context_resolver` | +15.80 | $+9.48 | 0.10 |
| 14 | `BTC|coinbase|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +15.57 | $+108.97 | 153.17 |
| 15 | `ETH|coinbase|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `opportunity_ledger` | +15.50 | $+92.99 | 44.67 |
| 16 | `BTC|coinbase|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +15.32 | $+107.26 | 153.25 |
| 17 | `BTC|bybit|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +15.28 | $+106.96 | 153.17 |
| 18 | `BTC|bybit|buy|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +15.17 | $+106.21 | 153.25 |
| 19 | `ETH|coinbase|buy|first6h` | `MEAN_REVERSION_CHOP` | `opportunity_ledger` | +14.96 | $+89.73 | 1.17 |
| 20 | `BTC|kraken|buy|remaining18h` | `BASIS_DISLOCATION` | `opportunity_ledger` | +14.80 | $+118.37 | 153.17 |
| 21 | `BTC|kraken|buy|remaining18h` | `VOL_BREAKOUT` | `opportunity_ledger` | +14.80 | $+118.37 | 153.17 |
| 22 | `BTC|bybit|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `exact_context_resolver` | +14.65 | $+8.79 | 6.85 |
| 23 | `ETH|kraken|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +14.52 | $+101.63 | 151.33 |
| 24 | `ETH|kraken|sell|remaining18h` | `LIQUIDITY_SQUEEZE` | `opportunity_ledger` | +14.05 | $+98.38 | 151.17 |
| 25 | `ETH|kraken|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `opportunity_ledger` | +13.76 | $+82.56 | 12.92 |
| 26 | `ETH|coinbase|buy|remaining18h` | `MEAN_REVERSION_CHOP` | `opportunity_ledger` | +13.61 | $+81.69 | 12.92 |
| 27 | `ETH|coinbase|buy|remaining18h` | `BASIS_DISLOCATION` | `opportunity_ledger` | +13.54 | $+108.34 | 153.17 |
| 28 | `ETH|coinbase|buy|remaining18h` | `RELATIVE_STRENGTH` | `opportunity_ledger` | +13.54 | $+108.34 | 153.17 |
| 29 | `ETH|coinbase|buy|remaining18h` | `VOL_BREAKOUT` | `opportunity_ledger` | +13.54 | $+108.34 | 153.17 |
| 30 | `ETH|coinbase|sell|first6h` | `BASIS_DISLOCATION` | `opportunity_ledger` | +13.53 | $+108.23 | 48.17 |

## By Context

| Context | Tradable | Best R | Best strategy | Strategies |
|---|---:|---:|---|---|
| `BTC|bybit|buy|first6h` | 131 | +15.80 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|bybit|buy|remaining18h` | 215 | +19.93 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|bybit|sell|first6h` | 79 | +21.27 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|bybit|sell|remaining18h` | 152 | +9.55 | `LIQUIDITY_SQUEEZE` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|coinbase|buy|first6h` | 103 | +6.89 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|coinbase|buy|remaining18h` | 323 | +20.28 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|coinbase|sell|first6h` | 98 | +10.48 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|coinbase|sell|remaining18h` | 208 | +9.39 | `BASIS_DISLOCATION` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|kraken|buy|first6h` | 168 | +8.41 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|kraken|buy|remaining18h` | 320 | +14.80 | `BASIS_DISLOCATION` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|kraken|sell|first6h` | 98 | +10.43 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `BTC|kraken|sell|remaining18h` | 197 | +28.69 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|bybit|buy|first6h` | 146 | +19.83 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|bybit|buy|remaining18h` | 183 | +18.70 | `LIQUIDITY_SQUEEZE` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|bybit|sell|first6h` | 116 | +8.77 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|bybit|sell|remaining18h` | 256 | +16.28 | `LIQUIDITY_SQUEEZE` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|coinbase|buy|first6h` | 213 | +14.96 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|coinbase|buy|remaining18h` | 424 | +15.50 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|coinbase|sell|first6h` | 288 | +13.53 | `BASIS_DISLOCATION` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|coinbase|sell|remaining18h` | 506 | +13.18 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|kraken|buy|first6h` | 245 | +10.54 | `RELATIVE_STRENGTH` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|kraken|buy|remaining18h` | 402 | +13.76 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|kraken|sell|first6h` | 257 | +13.38 | `BASIS_DISLOCATION` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |
| `ETH|kraken|sell|remaining18h` | 494 | +16.94 | `MEAN_REVERSION_CHOP` | `BASIS_DISLOCATION, LIQUIDITY_SQUEEZE, MEAN_REVERSION_CHOP, NEWS_BREAKOUT, RELATIVE_STRENGTH, VOL_BREAKOUT` |