# TUNING_S68 — per-coin full-stack Kraken tune on the 28-day tape (findings only; live path untouched)

**Method (load-bearing).** Every backtest decision runs through the LIVE executor — `odcore.platform.run_stream`,
driven by `odcore.flip_detector.detect_flips` / `retime_flips` / `lean_series`, exactly as
`scripts/grade_coin_kraken.py::run_side` and `odcore.platform.run_kraken_cell` do. The sweep harness
(`scripts/_s68_tune_kraken.py` + `scripts/_s68_drive.py`) ONLY adds the parameter loop + gating/reporting around
the live calls — no re-implementation of executor / fill / fees / sizing. **Canary PASS:** with all stack knobs off,
`run_cfg` reproduces `grade_coin_kraken.run_side` bit-for-bit across every side×rev on btc and eth.

**Fee frame:** kr_mk0 — maker=0.0, taker=5.0, `fill_model="front"`, `close_improve_bps=0.5`, WFLIP=600, cap=$5000.
`$/hr = res.total_net_bps/1e4 * 5000 / hours`.

**Anti-overfit gate (reuses `grade_coin_kraken` machinery, extended to carry the full stack so the GATED config ==
the RECOMMENDED config):** (a) circular-shift FLOW null floor = `null.mean + 2*std` (15 shifts) — best $/hr must clear
it; (b) per-window sign consistency (NWIN=7) — frac windows positive must be ≥ 0.6; plus a first/second-half read for
fragility. **SEAT** = positive, beats reversed, clears floor, ≥60% windows. **MARGINAL** = positive & beats reversed
but fails floor or window consistency. **REJECT** = otherwise.

**Staging (compute-judicious):** (1) side×coarse-rev at base stack; (2) around the winner add eps → bail → grace, one
axis at a time keeping the best, then a rev-revisit under the chosen stack; (3) gate the final config.
rev grid = [0.08,0.10,0.13,0.16,0.20,0.25,0.30,0.40]; eps ∈ [None,3,5,10,15,20]; bail ∈ [None,60,80,100,150]; grace ∈ [200,300,600].

---

## SUMMARY (updated as tapes backfill; * = 28d tape confirmed)

| coin | current $/hr (28d) | best $/hr | delta | null floor | win% | verdict |
|------|--------------------|-----------|-------|-----------|------|---------|
| btc* | +7.99 | **+10.27** | +2.28 | +6.74 | 86% | **SEAT** |
| eth* | +8.52 | **+10.47** | +1.95 | +7.69 | 100% | **SEAT** |
| sol* | −1.96 | +1.08 | +3.04 | +2.69 | 71% | **MARGINAL** (best is REVERSED; below floor) |
| xrp  | _pending 28d tape_ | | | | | |
| doge | _pending_ | | | | | |
| ada  | _pending_ | | | | | |
| sui  | _pending_ | | | | | |
| ltc  | _pending_ | | | | | |
| avax*| +2.97 | **+7.88** | +4.91 | +7.81 | 100% | **SEAT** (thin floor margin) |

---

## PER-COIN DETAIL

### btc — SEAT (28d)
- **Deployed:** side+1 rev0.10 eps5 bail80 grace300 improve0.5 K=10 → **+7.99 $/hr** on 28d.
- **Best found:** `side+1 rev0.08 eps3 bail100 grace300 improve0.5` → **+10.27 $/hr** (delta **+2.28**).
- Gate: null floor +6.74 (clears), 86% windows positive, halves [+6.93, +13.60] (both positive; 2nd half stronger).
- Direction premium real: wrong side (reversed) best is −2.73.
- Fine churn helps: rev0.08 > 0.10; the tighter early-arm eps=3 (vs deployed 5) + slightly deeper bail=100 (vs 80) is the lift.
- **Proposed:** `CellConfig("btc", venue="kraken", side=+1, rev=0.08, eps=3.0, bail=100.0, grace=300, improve=0.5, K=10)`
- Flags: none major — both halves positive, clears floor comfortably. eps is the S47 early-arm lift and it holds here.

### eth — SEAT (28d)
- **Deployed:** side+1 rev0.10 eps10 bail100 grace300 improve0.5 → **+8.52 $/hr** on 28d.
- **Best found:** `side+1 rev0.08 eps5 bail150 grace600 improve0.5` → **+10.47 $/hr** (delta **+1.95**).
- Gate: null floor +7.69 (clears), **100% windows** positive, halves [+9.86, +11.09] (very stable).
- Direction premium real: wrong side best −0.86.
- **Proposed:** `CellConfig("eth", venue="kraken", side=+1, rev=0.08, eps=5.0, bail=150.0, grace=600, improve=0.5)`
- Flags: cleanest coin — 100% sub-windows positive, tight halves. eps=5 (vs deployed 10), deeper bail=150, longer grace=600.

### sol — MARGINAL / direction re-adjudication (28d)
- **Deployed:** side+1 (FORWARD) rev0.10 base → **−1.96 $/hr on 28d — the deployed forward config LOSES money.**
- **Best found:** `side−1 (REVERSED) rev0.40 base` → **+1.08 $/hr** (delta +3.04 vs deployed).
- Gate: null floor **+2.69 — best does NOT clear it** (+1.08 < +2.69); 71% windows; halves [+0.06, +2.10] (1st half ~flat).
- eps/bail/grace add nothing on sol (base stack is best; eps HURTS — consistent with the S47 note that eps hurts SOL).
- **28d CONTRADICTS the S65 book-provisional forward deploy.** It AGREES with the S63 30d-tape "SOL reversed" reading.
  But even reversed, sol is below its own null floor → **not a real seat; hold / do not run forward.**
- **Proposed (if seated at all, thin backup only):** `CellConfig("sol", venue="kraken", side=-1, rev=0.40, grace=300, improve=0.5)`
  — MARGINAL; recommendation is to **pull sol forward from live capital** and treat reversed as unproven backup.
- Flags: window-fragile (1st half flat), below floor. The edge is not robust; do not size.

### avax — SEAT (28d, thin floor margin)
- **Deployed:** side+1 rev0.13 base → **+2.97 $/hr** on 28d (S67 had graded avax MARGINAL at base).
- **Best found:** `side+1 rev0.13 eps20 grace600 improve0.5` → **+7.88 $/hr** (delta **+4.91** — the full stack tune is the whole lift; eps=20 early-arm + grace=600 more than double base).
- Gate: null floor **+7.81 — best clears it, but only just** (+7.88 vs +7.81, ~+0.07 margin; null mean +5.19 is high, so the flow-lean timing premium over random is small); **100% windows** positive [4.34, 8.89, 13.48, 5.08, 9.98, 13.24, 0.17]; halves [+7.90, +7.86] (very stable across the 28d).
- Direction premium real: wrong side best −6.35. bail adds nothing (None best).
- **Recency (last 9d):** best = `side+1 rev0.10 eps20 grace600` → +8.38 MARGINAL (win 57%, halves [+17.07, −0.31] — the recent window front-loads all the edge into the first half then goes flat/negative). **DIVERGE=True (rev 0.13→0.10).** 28d-best on recent = +7.72 (still strong); recent-best on 28d = +6.56. The divergence is minor (rev only) — deploy the 28d config; the recent flat 2nd-half is a fragility flag to watch but the 28d halves are stable.
- **Proposed:** `CellConfig("avax", venue="kraken", side=+1, rev=0.13, eps=20.0, bail=None, grace=600, improve=0.5)`
- Flags: floor margin thin (+0.07) — the edge is real but small over random-timing; recent 2nd-half went flat. Seat as a lighter allocation than btc/eth.
