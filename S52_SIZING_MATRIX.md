# S52 — Canonical $/hr MATRIX with SIZING factored (Greg Job 1)

> **⚠ There is no single "$X/hr ceiling."** Every number below is one CELL of the matrix {venue, maker fee, FLAT|ENTRY-SIZED|winner-sided, v1|v2 fill, window}. Cite the cell, or cite the matrix. All numbers are on **Coinbase** books (pre-Bybit, ~10x tape smaller) over the S51 windows.

This resolves Greg's S51 concern — *"you aren't factoring in the size up on the winners."* The accounting is now airtight: **(1a)** the flow-cap model credits entry-conviction sizing correctly; **(1b)** the two winner-side sizing mechanisms *beyond* entry conviction are **falsified** on the forward ledger + microstructure. So the deployable sizing lever is entry conviction, and the matrix reports it explicitly.

## Job 1a — is `_dollars()`'s `min(size×S, flow)` under-crediting sizing? **No.**

Per cell (mk0, deploy $1k/leg): `corr(size,cap)` is **positive on all 5** — high-conviction legs sit on slightly fatter-flow turns, so the `min()` model *does* capture the fat-leg concentration (it is not thrown away). `corr(size,net)≈+0.03` (entry conviction loads |move|, not wins — S47, re-confirmed). The sizing lift →0 at the flow-capped ceiling is the **physical flow wall** (you cannot fill more than the real opposing $), not a modeling artifact. At deploy $1k the cap already binds 54–87% of legs, so sizing acts on the fat-flow minority — exactly where `corr(size,cap)>0` puts the conviction.

| cell | mean_size | corr(size,net) | corr(size,cap) | corr(cap,net) | cap-binds @$1k | raw lift (uncapped) | $/hr lift @$1k | capital-MATCHED lift |
|------|-----------|----------------|----------------|---------------|----------------|----------------|----------------|----------------------|
| sol | 1.071 | +0.022 | +0.075 | -0.025 | 73% | +16% | +21% | +17% |
| doge | 1.111 | +0.057 | +0.054 | +0.015 | 87% | +47% | +1% | -3% |
| xrp | 1.089 | +0.015 | +0.075 | -0.023 | 76% | +15% | +7% | +2% |
| eth | 1.073 | +0.023 | +0.097 | -0.031 | 54% | +27% | +51% | +44% |
| btc | 1.068 | +0.052 | +0.083 | -0.059 | 69% | +34% | +75% | +67% |

- **raw lift** = the ledger view (sum net×size, no flow bound) = the UPPER bound if flow were unlimited (+16..+47%).
- **$/hr lift @$1k** = flow-bounded, as-deployed (mean_size≈1.07 ⇒ ~7% more notional on conviction).
- **capital-matched lift** = rescaled so sized deploys the SAME total notional as flat = pure allocation skill (SOL +21%→+17%; the ~4pp gap is the small deploy-more effect). ETH/BTC % are on near-zero baselines (±$1–3/hr absolute) — read them as noise, not signal.

## Job 1b — winner-side sizing BEYOND entry conviction: both mechanisms **FALSIFIED**

**(i) Sequence anti-martingale** ("size up after recent winners") needs leg outcomes to PERSIST. They do not — lag-1 net autocorrelation is ~0 on every cell and never significantly positive (ETH is mildly *anti*-persistent, shuffle z=−3.2); prior-k mean predicts next-leg net at corr ≤ |0.035|, E[next|winning]−E[next|losing] ≈ 0 bps. Leg outcomes are essentially independent (the swing regime resets each turn).

| cell | lag-1 net AC | shuffle z | prior-10 corr | E[next\|prior>0]−E[next\|prior<0] |
|------|--------------|-----------|---------------|-----------------------------------|
| sol | -0.013 | -1.0 | +0.002 | +0.18 bps |
| doge | -0.024 | -1.2 | -0.013 | -0.40 bps |
| xrp | +0.010 | +0.6 | +0.035 | +0.02 bps |
| eth | -0.040 | -3.2 | -0.007 | -0.04 bps |
| btc | +0.015 | +1.3 | +0.000 | -0.03 bps |

**(ii) Within-leg green-adds** ("only add when the leg is green") needs GREEN legs to offer opposing maker flow to fill the add. They offer LESS: winners' fillable $ is **0.32–0.65×** losers' on 4/5 cells (only thin/noisy DOGE inverts). The market force-feeds fill to LOSERS (S45/S51 adverse selection), so a green-only add structurally cannot load winners harder than losers — dead on the microstructure, not just this window.

| cell | winner fillable $ (med) | loser fillable $ (med) | win/lose ratio |
|------|-------------------------|------------------------|----------------|
| sol | $146 | $226 | 0.65 |
| doge | $25 | $14 | 1.78 |
| xrp | $104 | $200 | 0.52 |
| eth | $300 | $943 | 0.32 |
| btc | $51 | $156 | 0.33 |

**Verdict:** "size on winners" that survives falsification = **entry-conviction sizing** (already deployed; +8–21% at deploy sizes, correctly credited per 1a). A *realized*-winner add fails because you cannot preferentially fill winners as a maker. This is gated on the Bybit venue book + queue-aware fill (Job 2) where fill share and the reversed-control test can be re-run — not deployable off Coinbase.

## The canonical matrix — $/hr per cell × fee scenario × fill model

`flat` = $1k/leg every leg. `sized` = entry-conviction (`size_legs`, leakage-clean, hi_clip=4.0). `winner-sided` = **n/a (falsified, Job 1b)** ⇒ equals `sized`. v1 = front-of-queue (we improve the book at the turn); v2 = queue-honest (join the back of the best level). Ceiling = all real opposing flow captured (sizing lift = 0 there by the flow wall). Deploy size $1k/leg.

### SOL — 35h, 153 turns/hr, med leg-cap $188, v2 20% legs fillable
| scenario | net/leg | v1 flat | v1 sized | lift | v2 flat | v2 sized | v1 ceil (sized) |
|----------|---------|---------|----------|------|---------|----------|-----------------|
| mk0  ·1.0x | +1.73b | $+7 | $+9 | +21% | $+1 | $+3 | $+18 |
| mk-1 ·1.0x | +3.72b | $+19 | $+21 | +11% | $+4 | $+7 | $+71 |
| mk-2 ·1.0x | +5.72b | $+30 | $+33 | +8% | $+8 | $+11 | $+124 |
| mk-1 ·1.5x | +4.40b | $+23 | $+25 | +10% | $+6 | $+8 | $+89 |
| mk-2 ·1.5x | +6.40b | $+34 | $+37 | +8% | $+9 | $+12 | $+142 |

### DOGE — 41h, 46 turns/hr, med leg-cap $23, v2 32% legs fillable
| scenario | net/leg | v1 flat | v1 sized | lift | v2 flat | v2 sized | v1 ceil (sized) |
|----------|---------|---------|----------|------|---------|----------|-----------------|
| mk0  ·1.0x | +1.28b | $+1 | $+2 | +1% | $+0 | $+0 | $+6 |
| mk-1 ·1.0x | +3.23b | $+3 | $+3 | +1% | $+1 | $+1 | $+11 |
| mk-2 ·1.0x | +5.19b | $+5 | $+5 | +2% | $+2 | $+2 | $+17 |
| mk-1 ·1.5x | +3.90b | $+4 | $+4 | +1% | $+1 | $+2 | $+13 |
| mk-2 ·1.5x | +5.85b | $+6 | $+6 | +2% | $+2 | $+3 | $+19 |

### XRP — 29h, 140 turns/hr, med leg-cap $129, v2 22% legs fillable
| scenario | net/leg | v1 flat | v1 sized | lift | v2 flat | v2 sized | v1 ceil (sized) |
|----------|---------|---------|----------|------|---------|----------|-----------------|
| mk0  ·1.0x | +1.16b | $+4 | $+4 | +7% | $-0 | $+0 | $+6 |
| mk-1 ·1.0x | +3.15b | $+13 | $+13 | +1% | $+3 | $+4 | $+47 |
| mk-2 ·1.0x | +5.15b | $+23 | $+23 | +0% | $+6 | $+7 | $+87 |
| mk-1 ·1.5x | +3.63b | $+15 | $+15 | +1% | $+4 | $+4 | $+56 |
| mk-2 ·1.5x | +5.62b | $+25 | $+25 | +0% | $+7 | $+8 | $+97 |

### ETH — 64h, 104 turns/hr, med leg-cap $533, v2 44% legs fillable
| scenario | net/leg | v1 flat | v1 sized | lift | v2 flat | v2 sized | v1 ceil (sized) |
|----------|---------|---------|----------|------|---------|----------|-----------------|
| mk0  ·1.0x | +0.55b | $+2 | $+3 | +51% | $+0 | $+1 | $+2 |
| mk-1 ·1.0x | +2.55b | $+13 | $+16 | +15% | $+7 | $+9 | $+68 |
| mk-2 ·1.0x | +4.55b | $+25 | $+28 | +12% | $+14 | $+17 | $+134 |
| mk-1 ·1.5x | +2.58b | $+14 | $+16 | +15% | $+7 | $+9 | $+69 |
| mk-2 ·1.5x | +4.58b | $+25 | $+28 | +12% | $+14 | $+17 | $+135 |

### BTC — 196h, 40 turns/hr, med leg-cap $78, v2 22% legs fillable
| scenario | net/leg | v1 flat | v1 sized | lift | v2 flat | v2 sized | v1 ceil (sized) |
|----------|---------|---------|----------|------|---------|----------|-----------------|
| mk0  ·1.0x | +0.52b | $+1 | $+1 | +75% | $+0 | $+0 | $-5 |
| mk-1 ·1.0x | +2.52b | $+3 | $+4 | +22% | $+2 | $+2 | $+31 |
| mk-2 ·1.0x | +4.52b | $+6 | $+7 | +18% | $+3 | $+4 | $+67 |
| mk-1 ·1.5x | +2.52b | $+3 | $+4 | +22% | $+2 | $+2 | $+31 |
| mk-2 ·1.5x | +4.52b | $+6 | $+7 | +18% | $+3 | $+4 | $+67 |

## How to cite this (the standing rule)
- **Never** "$X/hr." Say e.g. *"SOL, Coinbase, mk0, entry-sized, v1, $1k/leg ⇒ +$9/hr; ceiling +$18/hr; at −1bp v1 ceiling +$71/hr."*
- The **sizing contribution** is: +8–21% as-deployed at $1k (mostly SOL/ETH), SHRINKING with the rebate (uniform per-leg add lifts the flat baseline faster), and →0 at the flow ceiling. It is a **capital-constrained-regime lever**, real and kept, NOT an order-of-magnitude multiplier.
- The order-of-magnitude levers remain the **REBATE** (mk0→−1bp ≈ 3.9× on SOL, super-linear) and **venue FLOW** (Bybit ~10× Coinbase tape ⇒ ~10× the ceiling) — the Bybit MM path. Sizing rides on top, it is not the headline.
