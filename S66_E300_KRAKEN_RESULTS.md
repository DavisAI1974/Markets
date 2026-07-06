# S66 — E300 death-selector: Binance preview vs Kraken deploy-grade (2026-07-06)

Driver: `scripts/_s66_e300_run.py {binance|kraken|kraken5}` — drives `scripts/_s62_e300_3piece.py`
UNMODIFIED (sim=live rule). CAP=$5k, fee=0 (Greg handles fees; flip/flatten = taker cross via FC=22bp),
E=300s, per-week walk-forward. base = bare flow-lean; 3piece = + E300 death-cut (HOLD/FLATTEN/FLIP).

## Binance-vision 30d (signal proxy — majors only; NOT deploy-grade)
| coin | legs | AUC | base $/hr | 3piece | Δ | per-week Δ |
|---|---|---|---|---|---|---|
| DOGE | 512 | 0.685 | +0.63 | +1.32 | +0.69 | −0.4 +0.2 +1.6 +1.5 +0.7 |
| XRP  | 785 | 0.768 | +1.10 | +3.08 | +1.98 | +5.0 +1.3 +0.9 −0.1 +6.1 |

## Kraken 30d tape (DEPLOY-GRADE, all 5 majors)
| coin | legs | AUC | base $/hr | 3piece | Δ (E300 adds) | per-week Δ |
|---|---|---|---|---|---|---|
| ETH  | 517 | 0.709 | +2.20 | +2.88 | +0.69 | +0.4 −0.5 +2.3 +0.8 |
| BTC  | 288 | 0.643 | +0.85 | +1.79 | **+0.94** | +1.2 +2.2 +0.9  (3/3 wk+) |
| SOL  | 641 | 0.687 | +3.86 | +4.04 | +0.18 | +1.0 −1.1 −0.9 +1.9 |
| XRP  | 692 | 0.718 | +1.64 | +2.91 | **+1.27** | +3.1 +0.2 +1.4 +0.9  (4/4 wk+) |
| DOGE | 407 | 0.680 | +2.59 |  | +0.41 | +1.0 −1.3 −0.1 +2.5 |

## Reads
- **Death-selector signal is REAL and venue-robust:** AUC 0.64–0.72 on all 5 Kraken cells; DOGE/XRP AUC
  transferred from Binance within ~0.05 (0.685→0.680, 0.768→0.718). ⇒ **Binance is a valid SIGNAL proxy for
  majors** (prices arb'd, lag-0 synchrony) but NOT the deploy $/hr (Kraken base higher, Δ smaller) — grade on Kraken.
- **E300-on-the-ride is PER-COIN (confirms S64):** all Δ positive but **BTC (+0.94, 3/3 wk) and XRP (+1.27, 4/4
  wk) are the robust cells**; ETH/SOL/DOGE each carry a soft/negative week (SOL weakest — its bare-lean base is
  already the fattest, +3.86). Keep E300 on BTC/XRP; treat ETH/SOL/DOGE E300-on-ride as fragile (per-coin law).
- **E300 ALSO stands as its own uncorrelated SLEEVE** (Family B) — the death-cut earns independent of the ride.
- ⚠ fee=0 here (Greg handles fees); base $/hr is at kr_mk0 assumption. 4 per-week buckets on ~30d Kraken tape
  (Binance had 5). One 30d window — the S54 full gate (shuffle + reversed + deeper per-week) still owed on Kraken.
- Small-cap E300 (~116 THIN-OK band) pending the `data/kraken-smallcap-tape` 120d pull.
