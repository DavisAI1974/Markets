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

## SUMMARY — ALL 9 on 28d tape, RANKED BY PREMIUM-OVER-FLOOR (the honest structural edge)

**Load-bearing lens (applied uniformly, majors + candidates):** raw best $/hr includes the circular-shift
NULL FLOOR (structure-free churn the front-of-line fill model over-credits at ~0 Kraken half-spread). The
deployable structural edge is **PREMIUM = best − floor.** A coin with best $/hr >> 0 but best ≈ floor is
churn, not edge. Judged this way the roster reorders: only **BTC, ADA, ETH, LTC** carry real structural edge;
the 3 incumbents **SOL/XRP/DOGE fall BELOW their own floor on 28d**, as do candidates AVAX/SUI.

| coin | best $/hr | null floor | **PREMIUM** | recency | verdict (premium lens) |
|------|-----------|-----------|-------------|---------|------------------------|
| **btc** | +10.27 | +6.74 | **+3.53** | robust | **SEAT** (real edge) |
| **ada** ⭐new | +11.24 | +8.05 | **+3.20** | robust | **SEAT** — strongest new major, ~ties BTC |
| **eth** | +10.47 | +7.69 | **+2.78** | robust | **SEAT** (real edge) |
| **ltc** ⭐new | +2.97 | +1.87 | **+1.10** | robust | **SEAT** — modest, confirms S67 |
| avax new | +7.88 | +7.81 | +0.07 | FRAGILE | CHURN — big raw $/hr is all floor; not a seat |
| doge | +5.13 | +5.25 | −0.12 | FRAGILE | below floor — churn |
| xrp | +1.47 | +1.86 | −0.40 | FRAGILE | below floor (best side = REVERSED rev0.20) |
| sui new | +1.20 | +2.02 | −0.82 | robust | REJECT — confirms S67 |
| sol | +1.08 | +2.69 | −1.61 | robust | below floor — deployed FWD loses −1.96; reversed still under floor |

**Best-config per coin (proposed CellConfig knobs; NOT applied to live registry — review + longer window first):**
- btc `side+1 rev0.08 eps3 bail100 grace300 K10` · eth `side+1 rev0.08 eps5 bail150 grace600`
- **ada `side+1 rev0.08 eps10 grace600`** · **ltc `side-1 rev0.30 grace600`**
- avax `side+1 rev0.13 eps20 grace600` · doge `side+1 rev0.10 eps15 bail100 grace600`
- xrp `side-1 rev0.20 grace600` · sui `side-1 rev0.40 grace600` · sol `side-1 rev0.40`

**Recency (last ~9d vs full 28d):** btc/eth/ada/ltc/sui/sol configs are recency-ROBUST (agree). avax/doge/xrp
DIVERGE (recent 2nd-half goes negative) — extra fragility on exactly the coins already at/below floor.

**⇒ On 28d structural edge the real seat list is BTC · ADA · ETH · LTC.** SOL/XRP/DOGE/AVAX/SUI stay seated
(never dropped, Greg's rule) but the greedy allocator won't fund them — negative/zero premium. ADA is the
headline: a new major with premium ≈ BTC, better than every current incumbent except BTC/ETH.
⚠ One 28d window, front-of-line fill, structure-grade not sizing-grade; premium cancels fill-optimism but
absolute $/hr are an upper bound. Confirm on a 2nd window before any live-registry change.

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
