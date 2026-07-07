# NEXT-WINDOW PERSISTENCE WATCH — slight-edge trade-prediction candidates (S71, 2026-07-07)

> Greg (S71): "log next window — I'll say more about that later." This is the durable log so the
> slight-edge thread is NOT dropped again. **Greg has more to add here.**

## Why this exists
The S36 dipole/fingerprint re-eval on the **42h Kraken book** (`scripts/_info_dipole_kraken_eval.py` →
`_info_dipole_kraken_eval_results.json`) came back mostly flat (conviction ladder ~48% across all flow-states),
BUT a few cells showed a small positive **directional-prediction** lift. On ONE 42h window these are **within
noise** — pooled `imb_flow` was 51.2% over n=1990 (~1σ above coin-flip; need ~52.2% for 2σ), and the per-cell
positives are offset by equal-magnitude negatives elsewhere (classic noise-slicing). The SAME signed-flow
signal was already debunked on TAPE as a Simpson's-paradox / trend artifact (`DEPLOY_VALIDATED=False`). So the
prior is low — but a *real* small per-cell edge is worth deploying (Greg's "even a small edge is huge",
`deploy-signal-per-cell-not-universal`), and the only honest way to tell real-from-noise is **cross-window
persistence**, not more slicing of this one window.

## The candidates to watch (from the 42h Kraken-book eval)
| cell | feature / signal | lift on the 42h window | n |
|---|---|---|---|
| **btc_kraken_sell** | `imb_flow` (directional acc) | **+4** over base | 316 |
| **xrp_kraken_buy** | `imb_level` (directional acc) | **+3.1** (56.0 vs 52.8 base) | 159 |
| **doge_kraken_sell** | `divergence()` FLOW net-of-cost | both walk-forward halves + (**+0.66 / +2.98** @0bp); also `imb_level` +2.4 | 82 |

(Full per-cell table in `_info_dipole_kraken_eval_results.json` → `B_feature_lift` and `A_per_cell`.)

## The test (do this when a SECOND independent Kraken-book window exists)
1. Re-run `scripts/_info_dipole_kraken_eval.py` on a **different / later** Kraken-book window (more accrued book,
   or a non-overlapping slice) — same live path, strictly pre-entry, book not tape.
2. A candidate is **REAL** only if its lift **repeats** (same sign, similar magnitude) on **2+ independent
   windows**. One window cannot distinguish a true 3–4% edge from a lucky draw at these n's.
3. Deploy **per cell** only on cross-window survivors (net-of-cost @0bp maker, beats a shift-null). If a
   candidate doesn't repeat, drop it cleanly as noise — an honest null is a fine outcome.

## Status
- Prior: LOW (within-noise on 1 window; tape version debunked). Kept anyway per the small-edge / per-cell rule.
- Blocked on: a second Kraken-book window (books accruing; the 16-candidate collector also needs Greg's manual
  "Run workflow" trigger — token 403s).
- **Greg to add more direction here (S71).**
