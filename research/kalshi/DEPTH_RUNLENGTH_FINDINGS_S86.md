# DEPTH / RUN-LENGTH — the MBP-10 book read on the NYMEX canary (S86)

`event_move_baseline.py --depth` on the **MBP-10** depth tape (Databento `mbp-10`, trade events carrying
their concurrent 10-level book; `databento_backfill.py --schema mbp-10` -> `data/nymex_mbp10/`). Same 24
EIA-release windows as S85 (12 NG Thu + 12 CL Wed, Apr-Jul 2026, +/-40min around 14:30 UTC). The trade
price path is byte-identical to the S85 `trades` tape (so the magnitude/duration result reproduces); the
book rides along. **Leakage PASS 12/12 both contracts** — including the new pre-event book-imbalance
feature (`imb_R`, gated with bid_dep/ask_dep as the corrupt-the-future channels).

## The question (Greg, S86 #1)

Does a thinning book / one-sided imbalance predict a **LONGER run** (the dipole *exhaustion* read on the
canary)? Two mechanisms, opposite predictions:
- **Continuation/momentum:** a book leaning INTO the move (supportive) = fuel = the move RUNS longer.
- **Exhaustion (the dipole collapse-toward-balance):** an over-extended one-sided push = the leader is
  spent = REVERSAL = shorter run.

Features, measured R -> the **initial push** (fast-window peak, NOT the 30-min global peak that book
recovery would dominate): `aligned_imb_push` = book imbalance x move-direction at the push (>0 = book
supports the move); `exhaustion` = aligned_imb_R - aligned_imb_push (>0 = support collapsed); `far_thinning`
= consumed-side depth eaten. Tested against `sustain_s` (run length) and `retention` (run vs blip).

## The headline: per-cell, NG and CL carry opposite-signed correlations (Apr-Jul window only)

| contract | aligned_imb_push vs sustain | exhaustion vs retention | long-run push-book | short-run push-book |
|----------|----------------------------|-------------------------|--------------------|---------------------|
| **NG** (KXNATGASD) | **-0.17** | **-0.40** | balanced (0.02) | one-sided (0.12) |
| **CL** (KXWTI)     | **+0.52** | +0.32 | one-sided (0.12) | anti (-0.09) |

(Spearman rank-sign, n=12 each. `far_thinning` NG -0.43 / CL +0.13 — same-signed split, but it is
CONFOUNDED, see caveat; lean on `aligned_imb_push`.)

## Read (per-cell, log only — no mechanism claimed)

- **NG:** in this window, a more one-sided book at the initial push co-occurs with a SHORTER run
  (aligned_imb_push vs sustain -0.17; exhaustion vs retention -0.40; long-run aligned_imb_push 0.02 vs
  short-run 0.12). Observed correlation, sign as logged — not a claim about why.
- **CL:** opposite sign — a more one-sided book at the push co-occurs with a LONGER run (aligned_imb_push
  vs sustain +0.52, the largest |rho| here; long-run push-book 0.12 vs short-run -0.09).
- **The two contracts carry opposite-signed correlations.** Logged per-cell and kept per-cell; no single
  cross-contract rule is asserted. Whether this is a stable per-contract property or an artifact of this
  window is exactly what more data decides (see caveats).
- **Pre-event `imb_R`:** book imbalance AT the release leans the eventual move 0.58 (NG) / 0.33 (CL) of
  the time — near/below coin-flip at n=12. Logged; not used as a direction predictor here.

## Honest caveats (provisional — do not generalize)

1. **Prior conditions / event-stacking (load-bearing, Greg).** Events are not independent — each release
   lands on a market state carrying prior events' lasting effects, and the book behavior stacks on that
   running condition. These per-window correlations are UNCONDITIONED; building the running event-state
   context (see EVENT_SURPRISE_FINDINGS_S86.md Next) is what conditions them.
2. **Time-of-year confound.** These 24 windows are Apr-Jul 2026 only — one seasonal slice (NG
   injection/power-burn, CL summer draws). The book-behavior correlations may be season-specific; NONE of
   this generalizes to other months on this data. A full-year pull spanning all seasons is required before
   any per-contract property is asserted.
3. **n=12 per contract, release windows only.** Spearman |0.17-0.52|; none is individually significant at
   n=12 (CL +0.52 ~ p0.08). The signs are internally consistent (the median-split and the rank-correlation
   agree within each contract), but this is a LOG of an observed correlation, not a validated edge. The
   full-year MBP-10 pull (~52 releases/contract + the daily settle tape) is what confirms/refutes it.
4. **`far_thinning` is confounded** by the release-instant liquidity vacuum: at 14:30 UTC quotes get pulled,
   so the book at R is unusually thin and "thins" negatively (thickens) into the push as depth returns —
   strongest on NG (thin p50 -0.50) which is the thinnest/fastest book. It carries the same NG/CL sign but
   do not lean on its magnitude. `aligned_imb_push` (a normalized ratio at the push) is the clean feature.
5. **These are descriptive** except `imb_R`. `aligned_imb_push` is measured AT the initial push (observable
   seconds in, not a pre-move predictor of the full move); in this window it correlates with the remaining
   run, so it is a CANDIDATE hold-time signal for the lag join (S86 #3) to test, not an established one.
6. Futures book != Kalshi book. This is the canary's own microstructure; the Kalshi echo is measured next.

## Data / repro

- Depth tape: `data/nymex_mbp10/{NG,CL}_2026MMDD.jsonl` (24 windows, ~28MB raw; trade+book rows,
  `src=databento_mbp10`). Baselines: `data/event_move_{NG,CL}_depth.json`. Cost: ~$0.42 of the $125 credit
  for all 24 MBP-10 windows (NG ~$0.02, CL ~$0.045 each). Raw re-downloadable free within 30d.
- Tools: `databento_backfill.py --schema mbp-10` (`_write_mbp10_df`), `event_move_baseline.py --depth`
  (`load_tape_depth` / `depth_features` / `_depth_summary`). `--selftest` PASS (depth math + depth leakage).

## Next

1. **Full-year MBP-10 pull** (~$130, NG+CL, all seasons) to take n from 12 -> ~52/contract and test whether
   the logged per-contract correlations are stable or a seasonal artifact (gate on `metadata.get_cost`,
   watch disk). Deferred in Plan A until the lag join proves the Kalshi echo pays.
2. **Surprise-cell split** (S86 #2, done): does the book correlation differ by beat/miss x big/small?
   See EVENT_SURPRISE_FINDINGS_S86.md.
3. **Lag join** (S86 #3): feed `aligned_imb_push` as a candidate hold-time signal into the Kalshi echo
   net-of-fee measurement, per cell.
</invoke>
