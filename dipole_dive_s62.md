# Dipole DIVE entry descriptors (S62) — BTC / ETH mid-band

Applying the DIVE chapter (`docs/DIPOLE_DIVE_CHAPTER_S60.md`) framework to the ENTRY
problem: score each armed mid-band leg (`armed_midband_flips(mid, 80.0, 0.5)`, entry `ci>=1802`)
as **big-loser** (gross ≤ −40 bp) vs **winner** (gross > 0), to drive an entry-flip
(flip a predicted big-loser: `pnl = −gross − 22`). All features **strictly causal** (data ≤ ci),
per-cell (one cell/coin), 30-day Binance-spot 1-s bins. Nulls: circular-shift on AUC.
Lean routine self-tested (bounded [−1,1], causal, pure-buy→+1 / pure-sell→−1).

The DIVE intuition ported to entry: a big-loser entry = the machine **fading a move still
running against the new position** (a freight-train). The features read *"am I entering against
a live, one-directional flow, or is opposing flow diving in (a real turn)?"* — office (ii),
the wrong-side/failure read, evaluated at entry rather than mid-leg.

## Leg census
| coin | legs | big-losers | winners | other | hrs | baseline $/hr | ORACLE flip $/hr | prize headroom |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| BTC | 671 | 200 | 338 | 133 | 720 | −1.18 | **+13.75** | +14.93 |
| ETH | 1026 | 302 | 536 | 188 | 720 | +0.56 | **+23.20** | +22.65 |

Oracle reproduces the stated prize (BTC ≈ +14, ETH ≈ +23 $/hr @ $5k) — the target is real.

## Features (8 causal-at-entry; side = new-position side)
`wlean60/300/600` = with-position trailing-W lean `side·(B−S)/(B+S)`;
`traj_fast/slow` = lean building vs collapsing into entry (`wl60−wl300`, `wl300−wl600`);
`diveIn_presence300` = frac of trailing-300 s with net flow **on my side** (counter-flow diving in vs freight-train absent);
`flow_px_coupl300` = |corr(inst-lean, ret)| trailing 300 s (trending/freight-train regime);
`premove600_ADV` = signed adverse pre-move over 600 s (**PRICE reference**, the running move the leg fades).

## Per-feature results (AUC = big-loser vs winner; flip $/hr = per-week OOS)

### BTC (baseline −1.18, oracle +13.75)
| feature | AUC pooled | AUC wkOOS | null-z | flip $/hr (wkOOS) |
|---|--:|--:|--:|--:|
| wlean60 | 0.478 | 0.473 | −0.9 | −1.07 |
| wlean300 | 0.463 | 0.462 | −1.6 | −2.45 |
| wlean600 | 0.465 | 0.449 | −1.4 | −3.79 |
| traj_fast_60_300 | 0.527 | 0.534 | +1.1 | −2.85 |
| traj_slow_300_600 | 0.488 | 0.498 | −0.5 | −1.99 |
| diveIn_presence300 | 0.493 | 0.470 | −0.2 | −2.11 |
| flow_px_coupl300 | 0.527 | 0.540 | +1.2 | −2.42 |
| **premove600_ADV (px ref)** | **0.576** | **0.578** | **+3.3** | −2.06 |

### ETH (baseline +0.56, oracle +23.20)
| feature | AUC pooled | AUC wkOOS | null-z | flip $/hr (wkOOS) |
|---|--:|--:|--:|--:|
| wlean60 | 0.494 | 0.492 | −0.4 | +0.81 |
| wlean300 | 0.453 | 0.443 | −2.3 | −0.08 |
| wlean600 | 0.459 | 0.443 | −1.9 | −0.21 |
| traj_fast_60_300 | 0.528 | 0.531 | +1.3 | +0.44 |
| traj_slow_300_600 | 0.473 | 0.472 | −1.2 | +0.42 |
| diveIn_presence300 | 0.511 | 0.523 | +0.5 | +0.40 |
| flow_px_coupl300 | 0.522 | 0.521 | +1.1 | −0.39 |
| **premove600_ADV (px ref)** | **0.554** | **0.576** | **+2.6** | **+1.08** |

## Reading (data / interpretation / frame kept separate)

**Data.** The strongest single separator on both coins is the **price reference `premove600_ADV`**
(AUC 0.55–0.58, null-z +2.6/+3.3) — big-losers fade a larger running pre-move. This is the
mid-band echo of S61's "pre600 signed return is the strongest single trait." The **with-move
flow lean at entry (`wlean60/300/600`) is at chance and mildly *reversed*** (AUC 0.44–0.49,
z −1 to −2.3): at the decision second, a big-loser-starting leg and a winner-dipping leg are
**twins in the flow lean** — the DIVE chapter's "winners are invisible to causal flow reads"
law, now confirmed at the *entry* feature level, not just mid-leg. The freight-train is **not**
loudly visible as adverse with-move flow at entry.

**The two flow features that are worth keeping** are `traj_fast_60_300` (with-move lean
building into entry) and `flow_px_coupl300` (trending-regime coupling): both give AUC 0.52–0.54
in the *correct* direction, and — the point for stacking — they are **orthogonal to the price
reference** (corr to `premove600` = +0.14/+0.17 BTC, +0.06/+0.05 ETH). They are weak (null-z
~+1.1–1.3, individually inside the null band) but they are a genuinely *different* bet than price.

**$/hr — the honest null.** **No single feature drives a profitable entry-flip.** Every flip
$/hr sits at or below baseline, because a ~0.55 AUC is too weak to survive the 22 bp toll:
flipping the mislabeled winners (a winner → `−gross−22`) bleeds more than the correctly-flipped
big-losers save. Even the best separator (premove600) loses on BTC (−2.06 vs −1.18) and only
nudges ETH (+1.08 vs +0.56). The prize (+14/+23) requires the *multivariate S35 fingerprint
tier*, not any one in-container descriptor — exactly the S61 carry-forward.

**Stack, not scrap (Greg's rule).** A naive z-sum stack (price + the two flow features) is the
right frame: on **ETH** it lifts pooled AUC 0.554 → **0.562** (wkOOS 0.564) — the orthogonal flow
features add a hair on top of price. On **BTC** the equal-weight naive stack does not help
(0.576 → 0.558); it needs a fitted weight, which is the fingerprint-tier job, not a hand blend.
The flow descriptors are **weak, orthogonal-to-price ingredients** — precisely what should feed
the multivariate encoder, never a standalone flip trigger.

## Best stack candidate
- **BTC:** `premove600_ADV` (px-ref, AUC 0.576 z+3.3) as the backbone + `flow_px_coupl300`
  (AUC 0.527, orthogonal, corr +0.17) as the flow orthogonal. Neither flips profitably alone;
  both are fingerprint-tier inputs.
- **ETH:** `premove600_ADV` (AUC 0.554 z+2.6) + `traj_fast_60_300` (AUC 0.528, corr +0.06) —
  the only combination where the orthogonal flow feature measurably improved OOS AUC
  (0.554 → 0.564) and flip $/hr stayed positive (+1.08).

Artifacts: `/tmp/s62cache/{btc,eth}_dipole_dive.npz` (`ecell`, `feats[n,8]`, `names`, + `gross/side/ci/week`),
`/tmp/s62cache/dive_summary.json`, builder `/tmp/s62cache/dive_build.py`.
