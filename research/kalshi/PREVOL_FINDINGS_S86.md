# PRE-RELEASE VOLUME SIGNATURE — the primed/coiled detector (S86, first build off the event-state model)

`event_move_baseline.py` now computes a leakage-safe PRE-RELEASE VOLUME read (Greg's "market goes dead
before the print" — a primed/on-edge market coils, volume drying up because nobody wants to get run over on
a bad number). Two features on the existing MBP-10 tape (no new feeds):
- **pre_vol** = traded size in [R-120s, R], and **coiled_ratio** = late-half rate / early-half rate of that
  window (<1 = drying up into the release). STRICTLY pre-event -> leakage-safe -> PREDICTIVE.
- **surge_ratio** = post-release rate (0..+60s) / pre-release rate (explosion vs relief; descriptive).

Leakage gate PASS (pre_vol invariant to post-R sizes, added to the 3 existing gates). `--selftest` PASS
(coiled + surge + leakage). Normalization is PER CELL / PER CONTRACT (Greg's rule: same scaffold, different
variable values per energy type — NG's normal pre_vol ~500-640, CL's ~280-370, never pooled). 24 windows,
surprise-split cells. Provisional (n=12, sub-cells n=3-5).

## The read: the coiled spring is real on NG; weaker on CL (and the weakness fits)

### NG (KXNATGASD) — quieter pre-release -> BIGGER move, consistent across all cells
| cell | n | Spearman pre_vol vs peak_bps | quiet-half peak_bps | active-half peak_bps | surge_ratio p50 |
|------|---|------------------------------|---------------------|----------------------|-----------------|
| miss\|small | 5 | -0.6 | 227 | 160 | 6.5 |
| beat\|big | 3 | -1.0 | 185 | 91 | 6.2 |
| beat\|small | 3 | -0.5 | 145 | 108 | 6.2 |

- In EVERY NG cell the quiet (low pre_vol) half out-moved the active half, and pre_vol vs peak_bps is
  NEGATIVE (coiled hypothesis: a dead pre-release precedes a bigger break). Consistent sign across cells.
- Because pre_vol is strictly pre-event, this is a genuine PREDICTIVE primed-detector, not a descriptive
  outcome — the market telling us it is coiled BEFORE the print.
- surge_ratio ~6x: NG explodes on the release (the spring releasing) — NG is the release-reactive contract.

### CL (KXWTI) — weak/mixed, consistent with CL not trading the EIA number here
| cell | n | Spearman pre_vol vs peak_bps | Spearman coiled_ratio vs peak_bps | surge_ratio p50 |
|------|---|------------------------------|-----------------------------------|-----------------|
| miss\|big | 5 | +0.1 | -0.8 | 3.4 |
| miss\|small | 5 | -0.1 | -0.2 | 2.6 |

- The pre_vol LEVEL is near-zero predictive on CL; only the drying-up RATIO is negative, and only on the
  big-surprise cell. surge ~2.6-3.4x (smaller than NG).
- This tracks the eyeball test + P2: in this window CL was trading the 2026 Strait of Hormuz crisis, not the
  EIA print, so "quiet before the EIA release" is a DILUTED signal for crude — the release was a secondary
  event. The signal being weak precisely where the release is not the main event is itself consistent with
  the model (storage/release is one piece; on CL the latent geopolitical state was the driver).

## Honest caveats (provisional)

1. **n=12, sub-cells n=3-5.** Spearman -1.0 at n=3 is degenerate; treat the NG consistency-of-SIGN across
   cells as the signal, not any single coefficient. The full-year pull settles it.
2. **Pre-window is only 120s** (the pulled window's --pre). A longer pre-window (e.g. 10-15 min) would
   measure the coiling better; worth widening on the full-year pull.
3. Same seasonality / prior-conditions confounds as the rest of S86 (Apr-Jul only). No generalization.
4. This is the FIRST build off the event-state model (EVENT_STATE_DESIGN_S86.md): a market-based primed
   detector that needs NO external feeds. It is a candidate GATE for P3 (fire when coiled + primed) and a
   proxy for the latent state while the macro feeds (backwardation, news) are sourced.

## Data / repro

- `event_move_baseline.py` (`pre_release_volume` / `post_release_volume` / `_prevol_scalar` /
  `_volume_summary`); reads the existing MBP-10 tape. Baselines: `data/event_move_{NG,CL}_depth.json` carry
  the `volume` block. `--selftest` PASS.
- Next: widen the pre-window on the full-year pull; test the coiled detector as a P3 primed-state gate;
  add the post-release surge as the explosion-vs-relief classifier alongside herd-breadth.
