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

## The headline: it's PER-CELL, and NG and CL point OPPOSITE ways

| contract | aligned_imb_push vs sustain | exhaustion vs retention | long-run push-book | short-run push-book | reads as |
|----------|----------------------------|-------------------------|--------------------|---------------------|----------|
| **NG** (KXNATGASD) | **-0.17** | **-0.40** | balanced (0.02) | one-sided (0.12) | **EXHAUSTION** |
| **CL** (KXWTI)     | **+0.52** | +0.32 | one-sided (0.12) | anti (-0.09) | **CONTINUATION** |

(Spearman rank-sign, n=12 each. `far_thinning` NG -0.43 / CL +0.13 — same split, but it is CONFOUNDED,
see caveat; lean on `aligned_imb_push`.)

## Read (per-cell, both KEPT — different book behavior, same as the magnitude split)

- **NG = the exhaustion reactor.** A one-sidedly-leaning book at the initial push -> a SHORTER run; NG's
  healthiest holds have a MORE BALANCED book at the push (long-run aligned_imb_push 0.02 vs short-run 0.12;
  exhaustion vs retention -0.40). Mechanistically: the natgas release is a fast one-directional burst
  (S85: 60s captures 66%, 06-11 peaked in 1s) and when the book is most one-sided the burst has already
  spent itself -> fade. This is the dipole exhaustion frame (`odcore/info_dipole.py`) showing up on the
  canary: imbalance collapsing toward balance precedes the turn. The tradeable shape for NG is
  **fade the over-extended one-sided push**, not ride it.
- **CL = the trend developer (opposite).** A book leaning INTO the move at the push -> a LONGER run
  (aligned_imb_push vs sustain **+0.52**, the strongest single signal here; long-run push-book 0.12 vs
  short-run -0.09). Crude's move builds slowly over ~20 min (S85: 60s=27%, 06-17 built $2,640 over 17min),
  and a supportive book is the tell that it will keep developing. The tradeable shape for CL is
  **ride the supported trend** (hold longer while the book stays one-sided with the move).
- **This is the per-cell doctrine, not a contradiction.** NG and CL are different cells; a signal that
  works one way on one and the other way on the other is KEPT for each, used per-cell. It also
  independently corroborates the S85 magnitude story (NG front-loaded/fast; CL diffuse/slow) from a
  completely separate quantity (resting-book dynamics, not price).
- **Direction (pre-event `imb_R`) is weak.** Book imbalance AT the release leans the eventual move 0.58
  of the time on NG, 0.33 on CL (i.e. anti on CL) — near/below coin-flip at n=12. The resting book at the
  release instant is NOT a clean pre-event direction predictor; direction still comes from the catalyst +
  the futures lead, per the merged architecture.

## Honest caveats (provisional)

1. **n=12 per contract, release windows only.** Spearman |0.17-0.52|; none is individually significant at
   n=12 (CL +0.52 ~ p0.08). The SIGNS are internally consistent (the median-split and the rank-correlation
   agree within each contract) and the NG/CL split matches the independent magnitude story, but this is a
   HYPOTHESIS-GENERATING read, not a validated edge. The full-year MBP-10 pull (~52 releases/contract +
   the daily settle tape) is what confirms/refutes it per contract.
2. **`far_thinning` is confounded** by the release-instant liquidity vacuum: at 14:30 UTC quotes get pulled,
   so the book at R is unusually thin and "thins" negatively (thickens) into the push as depth returns —
   strongest on NG (thin p50 -0.50) which is the thinnest/fastest book. It carries the same NG/CL sign but
   do not lean on its magnitude. `aligned_imb_push` (a normalized ratio at the push) is the clean feature.
3. **These are descriptive** except `imb_R`. `aligned_imb_push` is measured AT the initial push, so it is
   not a pre-move predictor of the FULL move — but it IS observable early (seconds in) and predicts the
   REMAINING run, so it is usable as a **hold-time signal** on the lagged Kalshi echo (how long to hold),
   which is exactly where the lag join (S86 #3) will consume it.
4. Futures book != Kalshi book. This is the canary's own microstructure; the Kalshi echo is measured next.

## Data / repro

- Depth tape: `data/nymex_mbp10/{NG,CL}_2026MMDD.jsonl` (24 windows, ~28MB raw; trade+book rows,
  `src=databento_mbp10`). Baselines: `data/event_move_{NG,CL}_depth.json`. Cost: ~$0.42 of the $125 credit
  for all 24 MBP-10 windows (NG ~$0.02, CL ~$0.045 each). Raw re-downloadable free within 30d.
- Tools: `databento_backfill.py --schema mbp-10` (`_write_mbp10_df`), `event_move_baseline.py --depth`
  (`load_tape_depth` / `depth_features` / `_depth_summary`). `--selftest` PASS (depth math + depth leakage).

## Next

1. **Full-year MBP-10 pull** (~$130, NG+CL) to take n from 12 -> ~52/contract and settle the NG-exhaust /
   CL-continue split per cell (gate on `metadata.get_cost`, watch disk). Deferred in Plan A until the lag
   join proves the Kalshi echo pays.
2. **Surprise-cell split** (S86 #2): does the NG/CL book behavior differ on beat/miss x big/small? The
   surprise join resolves surprise=unknown.
3. **Lag join** (S86 #3): feed `aligned_imb_push` as the hold-time signal into the Kalshi echo net-of-fee
   measurement — NG fade-the-push vs CL ride-the-trend, realized-EV per contract.
</content>
</invoke>
