# Kraken Candidate TAPE Screen — fresh 14d tape (S71, 2026-07-07)

> **TAPE SCREEN ONLY** — grades the SIGNAL (edge real + direction), front-of-line, NO book depth. It is
> NOT a deploy decision. The **deploy gate remains the on-book grade** (needs Greg's collector trigger +
> accrual). Firing/registry (`odcore/platform.py::KRAKEN`) is LOCKED — changes only on Greg's explicit
> say-so. Nothing here is seated live. Method: existing `scripts/grade_coin_kraken.py` (S54 gate) via the
> LIVE path (`flip_detector` + `run_stream`, kr_mk0). Tape re-pullable via `backfill_kraken_trades.py`
> (realbins gitignored / data-lives-local).

## Grade table — ranked by $/hr (14d / 336h tape each)
| # | coin | side | rev | $/hr | rev $/hr | null floor | win% | verdict |
|---|------|------|-----|------:|---------:|-----------:|-----:|---------|
| 1 | ton | REV | 0.13 | +31.83 | −26.85 | +5.86 | 100% | **SEAT** ⚠ thin |
| 2 | xpl | FWD | 0.30 | +14.05 | −25.76 | +1.36 | 86% | **SEAT** ⚠ thin |
| 3 | ltc | REV | 0.30 | +3.23 | −2.31 | +2.70 | 86% | **SEAT** |
| 4 | xlm | FWD | 0.30 | +3.12 | −5.01 | +4.28 | 86% | MARGINAL |
| 5 | zec | REV | 0.30 | +2.75 | −8.13 | +5.14 | 71% | MARGINAL |
| 6 | link | FWD | 0.13 | +2.69 | −4.90 | +3.36 | 71% | MARGINAL |
| 7 | avax | FWD | 0.13 | +2.52 | −6.76 | +2.78 | 57% | MARGINAL |
| 8 | ada | FWD | 0.10 | +1.92 | −2.11 | +3.42 | 86% | MARGINAL |
| 9 | bch | FWD | 0.13 | +1.83 | −12.71 | +1.31 | 86% | **SEAT** (thin tape → lower-conf) |
| 10 | aave | REV | 0.20 | +0.99 | −5.12 | +4.65 | 71% | MARGINAL |
| 11 | near | FWD | 0.30 | +0.49 | −7.77 | +3.34 | 57% | MARGINAL |
| 12 | hype | FWD | 0.13 | −0.18 | −1.55 | +3.38 | 43% | REJECT |
| 13 | sui | REV | 0.30 | −1.40 | −3.63 | +2.38 | 43% | REJECT |
| 14 | tao | REV | 0.20 | −1.61 | −4.05 | +4.03 | 57% | REJECT |
| 15 | bnb | REV | 0.30 | −1.70 | −3.05 | +1.15 | 14% | REJECT |
| 16 | xmr | FWD | 0.20 | −2.18 | −2.91 | +3.91 | 14% | REJECT |

## Verdict tally
- **SEAT (4):** ltc, bch, ton⚠, xpl⚠  — **candidates for on-book confirm**, not deployed.
- **MARGINAL (7):** xlm, zec, link, avax, ada, aave, near — hold as possible thin backup capacity.
- **REJECT (5):** hype, sui, tao, bnb, xmr — drop.

## Recommended CellConfigs (tape-screen SEATs — pending on-book grade + Greg's approval)
```python
CellConfig("ltc", venue="kraken", side=-1, rev=0.3,  grace=300, improve=0.5),  # flagship, confirmed 2nd window
CellConfig("bch", venue="kraken", side=+1, rev=0.13, grace=300, improve=0.5),  # new SEAT, thinnest tape (10k bins) -> lower confidence
CellConfig("ton", venue="kraken", side=-1, rev=0.13, grace=300, improve=0.5),  # ⚠ +31.83 is a thin-tape front-of-line artifact — DO NOT size off tape; book-gate first
CellConfig("xpl", venue="kraken", side=+1, rev=0.3,  grace=300, improve=0.5),  # ⚠ same thin-tape caveat
```

## ⚠ TON / XPL caveat (load-bearing)
+31.83 / +14.05 dwarf the liquid majors (~3–5 $/hr) because both are low-liquidity/newer listings (~$1.2M/24h)
and the front-of-line, no-depth screen assumes we capture the full swing at front-of-queue — wildly optimistic
on thin tape. The **timing signal is real** (each clears its own shift-null floor, 100%/86% window consistency),
but the **magnitude collapses under real book depth.** "Signal exists, capacity unknown." Book-gate before any sizing.

## New info vs old (S67) — no flips, strong robustness
All 4 coins S67 had tape-graded reproduced verdict, side AND rev on fresh 14d tape:
ltc SEAT +3.33→+3.23 (side −1 rev 0.30), avax MARGINAL +3.37→+2.52, ada MARGINAL +1.88→+1.92 (below floor),
sui REJECT −2.30→−1.40. **No verdict flipped** — the old grades were robust. The new information is the 12
never-tape-graded coins → 3 new SEATs (bch + thin ton/xpl), the MARGINALs, and 5 clean REJECTs.
**edge ≠ depth:** the deepest-book candidates (hype, xmr) both REJECT (consistent with the S67 SUI finding).

## Next
- Believable new capacity to pursue: **LTC (confirmed) + BCH (thin-tape, lower-conf).** MARGINALs = hold.
- Deploy gate = **on-book grade** → needs Greg's manual "Run workflow" on the candidate book collector (token 403s) + days of accrual.
- Firing/seating changes only on Greg's explicit say-so.
