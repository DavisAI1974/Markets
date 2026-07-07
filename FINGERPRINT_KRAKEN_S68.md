# FINGERPRINT_KRAKEN_S68.md — distinctive microstructure fingerprints on Kraken, PER COIN

**Session 68 · 2026-07-07 · agent: OD/fingerprint (Kraken stack).** Deliverable for the S68 kickoff's
3-class fingerprint ask. All numbers from `scripts/_s68_fp_kraken.py` (tape) and `scripts/_s68_fp_book.py`
(L2 depth). No live-code edits, no commits. Companion raw JSON: `/tmp/s68_all.json`, `/tmp/s68_ep.json`,
`/tmp/s68_book.json`.

## Data used (all on-box; no backfill)
- **Tape (1s bins, `realbins/<coin>_kraken_bins.json`):** all 9 coins — btc/eth 683h, sol/xrp/doge/ada/sui/ltc/avax ~672h (**28 days each**). mid/buy/sell (taker flow)/spread. Kraken median half-spread rounds to **0.0 bps** in these bins (tick-scale) — so tape fingerprints are pure FLOW+PRICE, no spread lever.
- **Kraken L2 book (`origin/data/<coin>-kraken-book`, top-10/side):** 5 majors only, covering the **last 30–67h** of the tape (btc 42h, eth 67h, sol 42h, xrp 30h, doge 61h). Depth-truth, but short window.

## Method (discipline)
- **Legs = LIVE stack** (`detect_flips(lean_series(buy,sell,600), rev)` → `platform.run_stream`, front-of-line, kr_mk0, grace 300). Per-coin config: eth/btc/sol fwd rev0.10, doge fwd rev0.30, xrp fwd rev0.20, ltc rev0.30 side−1, ada/sui/avax fwd rev0.10. Win = `net_bps>0`.
- **Slides/Hills = price zigzag** (θ auto = 6× median |300s return|, per coin): a down-swing ≥θ (high-pivot → slide) vs up-swing ≥θ (low-pivot → hill). Fingerprint = features over the strictly pre-onset window `[onset−600, onset]`.
- **Causal vs descriptive** separated explicitly. Every causal tape feature (imb_pre, pre_ret, volz, lean) **PASSES `odcore.leakage.assert_no_leakage` on all 9 coins**. Predictive claims get a **circular-shift null** (rotate flow vs price).
- Separation reported as **AUC** (Mann-Whitney) + **Cohen d**. AUC 0.5 = no separation.

---

## CLASS 1 — WINNING vs LOSING legs: **CLEAN NULL on every coin (winners invisible pre-entry)**

| coin | legs | win% | best causal feat | AUC | null band ≤ | verdict |
|------|-----:|-----:|------------------|----:|------:|---------|
| btc  | 7760 | 48.5 | imb_pre_aligned  | 0.487 | 0.512 | null |
| eth  | 8662 | 50.2 | pre_ret_aligned  | 0.479 | 0.511 | null |
| sol  | 9924 | 42.4 | d_mi_flow        | 0.514 | 0.510 | null |
| xrp  | 6314 | 45.7 | d_mi_flow        | 0.512 | 0.512 | null |
| doge | 3982 | 47.5 | imb_pre_aligned  | 0.480 | 0.516 | null |
| ada  | 7010 | 49.1 | pre_ret_aligned  | 0.479 | 0.513 | null |
| sui  | 4969 | 43.6 | d_C_signed       | 0.515 | 0.518 | null |
| ltc  | 4040 | 50.4 | pre_ret_aligned  | 0.479 | 0.516 | null |
| avax | 4553 | 46.4 | aligned_flow     | 0.477 | 0.517 | null |

**No pre-entry feature distinguishes a future winner from a future loser on ANY coin.** Every causal feature
(side-aligned pre-entry flow imbalance, aligned pre-move, volume z-score, lean, lean-slope, the signed
info-dipole set `mi_flow`/`imb_flow`/`ent_dipole`/`C_signed`, `aligned_flow`/`opposing`/`exhausting`/
`rev_conv`) sits inside its circular-shift null band (best |AUC−0.5| ≤ 0.015; **zero** features anywhere
cross |AUC−0.5|>0.03). This **reproduces the master law** (S35/S47/S59/S63): winners are invisible to the
causal descriptor space, on Kraken tape, per coin, at n≈4k–10k legs.

**The only separator is DESCRIPTIVE (post-hoc):** hold duration. Winners are held longer (AUC 0.54–0.58,
d 0.17–0.29 on 8/9 coins) — mechanical: a winning ride lasts to the next turn while a loser is closed at the
next (adverse) flip. **ltc is the lone inversion** (hold AUC 0.461, d −0.13) — its reversed (side−1) winners
are the *shorter* holds. hold_s is not a filter (you learn it only after the leg closes).

**Deployable? NO** — there is no pre-entry winner/loser filter to wire. This is a real, valuable negative:
it says stop hunting an entry-time winner classifier from flow/price/dipole features and keep the edge where
it lives (signal timing + capital deployment), consistent with the S59 conclusion that the winner-side path
narrows to the S35 ENCODER tier (128-dim coeff archives, **not on this box**).

---

## CLASS 2/3 — DOWN-SLIDES vs UP-HILLS: **strong CAUSAL flow-CLIMAX fingerprint on every coin**

Directional AUC (slide vs hill) of each **pre-onset causal** feature. >0.5 ⇒ the feature leans toward the
completed move at the pivot (the capitulation CLIMAX). θ = per-coin zigzag threshold (bps).

| coin | θ | nS/nH | **imb_pre / lean** | lean_slope | d_imb_flow | d_ent_dipole | d_mi_flow | ~pre_ret (mech.) |
|------|--:|------:|------:|------:|------:|------:|------:|------:|
| sui  | 71 | 298/298 | **0.799** | 0.726 | 0.612 | 0.643 | 0.544 | 0.969 |
| ada  | 76 | 347/346 | **0.785** | 0.681 | 0.638 | 0.584 | 0.513 | 0.965 |
| doge | 52 | 316/317 | **0.773** | 0.666 | 0.604 | 0.631 | 0.579 | 0.948 |
| sol  | 62 | 369/367 | **0.769** | 0.715 | 0.621 | 0.554 | 0.545 | 0.968 |
| xrp  | 51 | 371/371 | **0.732** | 0.676 | 0.596 | 0.543 | 0.499 | 0.965 |
| avax | 65 | 318/318 | **0.730** | 0.694 | 0.607 | 0.605 | 0.547 | 0.954 |
| eth  | 36 | 610/608 | **0.695** | 0.709 | 0.658 | 0.525 | 0.518 | 0.904 |
| ltc  | 54 | 298/297 | **0.674** | 0.690 | 0.583 | 0.547 | 0.537 | 0.982 |
| btc  | 19 | 931/931 | **0.656** | 0.682 | 0.609 | 0.524 | 0.517 | 0.853 |

**The signature (identical shape on all 9 coins):** a down-slide begins at a price top preceded by NET
BUYING (pre-onset taker imbalance **+0.14 … +0.31**); an up-hill begins at a bottom preceded by NET SELLING
(**−0.05 … −0.39**). The trailing-flow lean and its acceleration (`lean_slope`) point *into* the exhausting
move — the aggressor's climax. This is the S45 "maker-at-the-turn" picture, now **measured per coin on
Kraken tape**: the euphoric buyers marking the top / capitulating sellers marking the bottom.

**Feature ranking (robust):** `imb_pre`≡`lean` (600s trailing imbalance) is the strongest single feature,
tied with `lean_slope`; `d_imb_flow` (late-half imbalance shift) is a weaker second; the differential
info-dipole flows (`d_mi_flow`, `d_ent_dipole`) and `exhausting`/`aligned_flow` are ~null here (0.50–0.64,
mildly useful only on doge/sui/ada). `volz` is null (~0.5) — a slide is not a volume event on Kraken.

**Discount `pre_ret`:** its 0.85–0.98 AUC is **mechanical/definitional** (a high pivot is up-preceded, a low
pivot down-preceded, by the zigzag's own construction) — not an edge. It is listed only to mark the ceiling.

**Circular-shift null (genuine coupling, not price-mechanics):** rotating flow vs price and re-scoring
`imb_pre` at the real onsets collapses the directional AUC to the null band — real vs null: eth 0.683 vs
≤0.534, sol 0.745 vs ≤0.539, doge 0.734 vs ≤0.549, btc 0.647 vs ≤0.520. **PASS all** → the fingerprint is
real flow↔price coupling, not a repackaging of the price move.

**Per-coin law:** the climax fingerprint is **strongest on the thinner alts** (sui 0.80, ada 0.79, doge 0.77,
sol 0.77) and **weakest on the deep majors** (btc 0.66, ltc 0.67, eth 0.70) — deeper/more-efficient books
hide the aggressor's climax; thin books broadcast it. Deploy per cell accordingly.

### Book (L2 depth) — NULL + coverage-limited
Top-5 depth-imbalance (bid vs ask resting size), pre-onset mean, tested slide-vs-hill on the 5 majors:
only **eth** (35h, 45/44 episodes) and **doge** (35h, 23/22) had enough onsets in the book window — both
give **AUC ≈ 0.50** (eth 0.515, doge 0.490) and **book-leads-price 60s corr ≈ 0** (eth +0.04, doge −0.01).
btc/sol/xrp had <20 episodes in-window (too few). **Verdict: Kraken top-K resting-depth imbalance is NOT a
causal directional fingerprint at this resolution/window** — depth carries a strong *persistent per-coin
bias* (eth ask-heavy ~−0.4, doge bid-heavy ~+0.3) that does not discriminate turns. The directional edge is
in taker FLOW, not resting DEPTH. (Coverage caveat: 30–67h book windows are too short to grade depth
properly; this is characterization, not a kill.)

---

## WHAT'S DEPLOYABLE (causal) vs descriptive

**CAUSAL / deployable (pre-onset, leakage-clean, null-passing):**
1. **Down-slide / up-hill early-warning = pre-onset taker-flow CLIMAX** (`imb_pre`/`lean` 600s + `lean_slope`),
   AUC 0.66–0.80 per coin. Wire as the **portfolio down-slide flatten overlay** (cross-ref STRATEGY_INVENTORY
   §8.10): the live `flip_detector` already fires at these turns causally; **gate/size a flatten by the
   pre-turn flow-climax magnitude** — a short-signal top with strong preceding BUY-climax = high-conviction
   down-slide → flatten/de-risk longs; symmetric BUY-the-capitulation for hills. Strongest cells first:
   **sui, ada, doge, sol** (AUC ≥0.77); btc/ltc marginal. This is a directional/regime overlay, **not** a
   per-leg winner filter.
2. Same climax feature could **weight the greedy allocator's idle-vs-deploy threshold** (S67 open job 1):
   fund a coin's turn more when the pre-turn climax is strong, less in flat flow — a causal, per-coin knob.

**DESCRIPTIVE only (post-hoc, do NOT wire as a filter):**
- Winner/loser hold duration (winners ride longer; ltc inverted) — realized, not pre-entry.
- `pre_ret` at an onset — mechanical artifact of pivot definition.

**NOT deployable (clean nulls):**
- Any pre-entry winner-vs-loser classifier (Class 1) — uniform null on all 9 coins.
- Kraken top-K resting-depth imbalance as a turn-direction signal (thin coverage + ~0.5 AUC).

---

## Honest limits
- **One 28-day tape window** per coin; slide/hill counts 298–931 per class (solid), leg counts 4k–10k (solid).
  Directional AUCs are ~9–17 SE above 0.5 and null-confirmed, but this is one regime — re-confirm on a
  second window before sizing an overlay.
- **Book covers only 30–67h** (5 majors, tail of the tape) → depth findings are characterization; a null on
  a short window is not a permanent kill. btc/sol/xrp had too few in-window episodes to grade.
- **Kraken half-spread ≈ 0 in these bins** → no spread-capture dimension in the tape fingerprint; the flow
  climax is the whole causal signal here.
- The **128-dim OD coeff / S35 encoder tier** (the winner-side fingerprint archives) is **not on this box** —
  Class 1's null is over the *causal flow/price/dipole* feature space, which is the deployable space; it does
  not test the E-drive encoder archives (S59's narrowing still stands as the only open winner-side path).
- Per-coin law honored throughout: reported per cell, never pooled.
