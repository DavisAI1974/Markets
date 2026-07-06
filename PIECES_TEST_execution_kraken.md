# PIECES_TEST_execution.md — Kraken per-coin execution/strategy coverage audit (S65 agent)

**Mandate (Greg):** "not 100% we haven't missed something." Per-coin coverage + exploratory-test audit of
the execution/strategy toolkit across the 5 Kraken coins, with special focus on the coins WITHOUT a working
solution — XRP (stand-aside) and DOGE (only fade-8h) — and de-fragile-ing SOL (reversed, fragile).

## ⚠ DATA REALITY (binding — read before every number below)
- **NO 30d Kraken edge-bearing TAPE on box.** The tape-based scripts (`_s63_kraken_{zigzag,fade,retime,bail,
  winloss}.py`) read `/tmp/kraken_backfill/*_30d_bins.json` which is **GONE** (ephemeral). Only `realbins/
  {btc,eth}_kraken_bins.json` (~26.7d) survive — SOL/XRP/DOGE have NO tape.
- **What IS on box:** Kraken L2 books `/tmp/kbook/{coin}_book.jsonl` — **~30–42h each, all 5 coins**
  (btc 41.9h, eth 30.0h, sol 41.9h, xrp 30.0h, doge 36.0h). This is **ONE low-edge window** (S64: ETH ideal-fill
  −2.04, BTC −1.11 on it). **Every number below is honest-fill on THIS ONE window → PROVISIONAL. Never size.**
- Consequence: the **full-population 30d tests** (E300 death-classifier per-week-OOS, fade-4–8h with enough
  independent samples, the S63 zigzag gate) are **NOT runnable for SOL/XRP/DOGE on box.** Where I say "UNTESTED
  GAP — needs 30d tape," that is the reason. I ran everything the ~30h book CAN support (executor mechanics +
  direction sign + fill), which is exactly the fill/stack layer the deployed map was still gated on.

---

## 1. COVERAGE MATRIX (rows = pieces, cols = coins)
Legend: ✅tape=validated on 30d tape · 📕book=tested this session on ~30h book · ✱=positive result ·
✗=tried, dead/neg · —=N/A · **GAP**=never tested for that coin.

| Piece | BTC | ETH | SOL | XRP | DOGE |
|---|---|---|---|---|---|
| Flow-lean zigzag FORWARD (W600/REV0.1) | ✅tape KEEP | ✅tape KEEP | ✗tape(anti,z−1.6) / **✱book** | ✗tape(null) / **✱✱book +12.4 ideal** | ~tape(marg) / ✱book |
| Flow-lean zigzag REVERSED | ✗ | ✗ | ✅tape KEEP(fragile) / ✗book | ✗ | ✗ |
| Early-arm entry (retime, eps) | ✅tape(eps5) / ✗book | ✅tape(eps10) / ✗book | ✗tape(−0.68) | ✅tape(eps10,+1.9)/ **✗book(−13!)** | ✗tape(flat)/✗book |
| Deep-bail (price_stop) | ✅tape(−80) | ✅tape(−100) | ✗tape | 📕book(no tail→+0) | 📕book(neutral) |
| Cover-grace (fill fix) | ✅tape / 📕book | ✅tape / 📕book(big lift) | **GAP→📕book ✱(rescues)** | **GAP→📕book ✱✱ (+6 lift)** | **GAP→📕book ✱** |
| Swing-floor (coarser REV) fill knob | 📕 | 📕 | 📕book(helps fill) | 📕book(fill↑ but $↓) | 📕book |
| Fade-N-hour trend (direction) | ~tape(6-8h marg) | ~tape(fragile) | ✅tape(4h,p.018) | ~tape(8h,lumpy) | ✅tape(8h,p.016) KEEP |
| E300 death-selector ON the ride | ✅tape KEEP(+0.20) | ✗tape(−0.41 drop) | ~tape(neutral) | **GAP on Kraken** | **GAP on Kraken** |
| E300 as its own sleeve (family B) | ✅Cbase(+1.29) | ✅Cbase | ✅Cbase(+3.3 w/feat) | **✅Cbase(+2.88!)** | **✅Cbase(+2.02!)** |
| Bigline / coarse-theta ride | GAP | GAP | GAP | **GAP** | **GAP** |
| Accum (starter+all-in-confirm) | ✗(Cbase micro dead) | ✗ | ✅Cbase-SOL(+1.3 R&D) | **GAP** | **GAP** |
| QuietFloor gate (book-depth) | GAP-Kraken | GAP | GAP | **GAP** | **GAP** |
| OD divergence/exhaustion gate | GAP-Kraken | GAP | GAP | **GAP** | **GAP** |
| 128-dim fingerprint (winner-side) | off-box | off-box | off-box | off-box | off-box |

**The most important UNTESTED-GAP cells (highest expected value):**
1. **E300 death-selector on Kraken tape for XRP & DOGE** — on Coinbase/Binance 30d it gave **XRP +2.88, DOGE
   +2.02** (S63 §5), the only rig that lifted XRP/DOGE well over baseline. NEVER run on Kraken's own tape or
   stacked onto the Kraken lean ride. This is the single biggest miss for the two "no-solution" coins.
2. **Cover-grace for XRP/SOL/DOGE** — was a genuine gap (XRP=aside, SOL=reversed) → I tested it (§2, big result).
3. **Bigline / coarse-theta on ALL 5 Kraken coins** — never run on Kraken at all. Greg's "trade the bigger
   trends" tool; the fine zigzag captures only the fine ripple.
4. **QuietFloor / OD-divergence gate on Kraken books** — built, portable, never wired to a Kraken cell.

---

## 2. WHAT I RAN (provisional, ~30h book window, honest queue-fill, $/hr @ $5k, kr_mk0)

### 2a. Direction sign — IDEAL fill (perfect maker at the turns), forward vs reversed
| coin | n_flips | IDEAL fwd | IDEAL rev |
|---|---|---|---|
| btc | 707 | −0.28 | −4.72 |
| eth | 573 | −2.04 | −7.22 |
| sol | 559 | **+1.99** | −1.16 |
| xrp | 460 | **+12.36** | −15.90 |
| doge | 385 | **+1.43** | −8.59 |

**Finding (load-bearing, but window-fragile):** on THIS book window **FORWARD flow-lean zigzag is the correct
sign for ALL 5 coins**, including SOL and XRP. The deployed **SOL=reversed** and **XRP=stand-aside** verdicts
were **30d-TAPE** decisions (SOL fwd z=−1.6; XRP tape null after thin-sample positives dissolved). The book
window and the tape **disagree on direction for SOL/XRP**. Do not overturn the deploy on one window — but this
is exactly a "confirm on a normal-edge multi-day book" flag, not a settled null.

### 2b. THE FILL FIX — cover_grace is decisive (honest queue-fill)
XRP forward, REV=0.1: base grace0 **+7.20** → grace300 **+12.50** → **grace600 +13.46** (fill 46%, takerCl 5%).
Deep-bail adds nothing (no deep tail in XRP's thin swings). **Winner XRP stack = fwd zigzag REV0.1 +
cover_grace600, NO early-arm, NO bail → +13.46 $/hr honest** vs deployed stand-aside (0).

SOL de-fragile (honest): fwd grace0 −4.41 → **fwd grace600 +1.21**; deployed **rev grace600 −6.35** on this
window. The **fill fix (cover_grace) matters more than the direction flip** here; forward+grace is positive
while reversed+grace is negative. SOL's fragility is as much a FILL problem as a direction problem.

DOGE forward honest: **fwd REV0.1 grace300 +2.88** (fill 13%, thin wide-spread book hs=0.43 → low fill is the
DOGE ceiling). Cover_grace cuts takerCl 76%→27% but fill% stays low.

### 2c. Early-arm is window-fragile — it HURT here
Early-arm (`retime_flips`) helped on the 30d tape (XRP +0.96→+2.87 eps10) but **on this book window it
collapsed XRP +7.20 → −6.26** and hurt every coin. Consistent with S64's flag (early-arm hurt BTC on realbins).
**Early-arm's sign is window-dependent — do NOT treat it as a free lift.**

### 2d. Swing-floor (coarser REV) — a fill-vs-edge knob, not a free win
Coarsening REV (0.1→0.5) raises fill% (XRP 59%→86%, SOL 28%→63%) but shrinks the captured edge; XRP net
$/hr FALLS (13.5→~5). On this window REV0.1+grace600 dominates. On a thinner-fill live book the coarser REV
may be needed — keep it as the deploy knob it already is.

**Leakage note (rule-compliant):** no NEW signal was introduced — all stacks use the already-leakage-validated
`detect_flips(lean_series)` detector (S46 `assert_no_leakage` PASS). cover_grace / price_stop / swing-floor are
executor exit/fill mechanics, not predictive signals, so no new leakage surface. Early-arm `retime_flips` is
also causal (leakage PASS, S47).

---

## 3. RANKED SHORTLIST — execution pieces worth a REAL-TAPE run, per coin
Ranked by expected edge × how big the current gap is. Every item's next test = **a normal-edge multi-day
Kraken book / 30d tape** (the box only had one ~30h low-edge window).

1. **XRP — forward flow-lean zigzag + cover_grace600 (NO early-arm, NO bail).** ⭐ biggest miss.
   Book window: **+13.46 $/hr honest** for a coin the map calls stand-aside. Signal alive on the book (ideal
   +12.4), fill leak small, cover_grace is structural (robust, not signal-tuned). NEXT: re-run XRP forward
   zigzag on a full 30d Kraken tape + a normal-edge multi-day book; if the direction sign holds (the tape said
   null once), this is a deployable XRP cell. Why it was missed: XRP was frozen at "stand aside" so cover-grace
   was never tried on it.

2. **E300 death-selector, run on Kraken tape for XRP & DOGE (and as its own sleeve).** ⭐
   Coinbase/Binance 30d: XRP +2.88, DOGE +2.02 — the only rig that lifted both. Never touched Kraken. NEXT:
   pull 30d Kraken tape for xrp/doge → run `_s62_e300_3piece.py` with Kraken bins; also test E300-death-cut
   STACKED on the XRP forward ride. Two shots at a real XRP/DOGE solution in one build.

3. **SOL — forward + cover_grace, re-adjudicated vs reversed on a fresh window.** De-fragile.
   Book window flips SOL to forward-positive (+1.21) and reversed-negative (−6.35). SOL's "reversed & fragile"
   status may be a single-window direction call compounded by an unfixed fill leak. NEXT: forward-vs-reversed
   with cover_grace600 on a 2nd Kraken tape window + the accruing book — settle the direction with the fill fix
   in place before locking reversed.

4. **Bigline / coarse-theta (`swing_bigline.py`) on all 5 Kraken coins.** Never run on Kraken.
   The fine zigzag captures the ripple; Greg's "trade the bigger trends" tool is untested here. NEXT: oracle at
   coarse theta on realbins btc/eth (runnable now) → then 30d tape for the alts. Could give DOGE (wide spread,
   thin fills kill the fine ride) a coarser, fewer-legs, higher-fill alternative — DOGE's fill% ceiling (13%)
   is its real blocker, and coarse-theta directly attacks it.

5. **DOGE — attack the fill ceiling, not the signal.** DOGE forward is right-signed (+1.43 ideal) but
   fill% ~13% (hs=0.43 wide book). NEXT: swing-floor REV≈0.35–0.5 + cover_grace600 on a real DOGE book to raise
   fill%, and/or the coarse-theta bigline (#4). Keep fade-8h as the deployed DOGE direction tool regardless.

6. **QuietFloor / OD-divergence gate on Kraken books (all coins).** Built, portable, never wired to a
   Kraken cell. Cheap add. NEXT: wire `quiet_floor` depth-imbalance gate as an entry filter on the XRP forward
   ride (gate=WHEN, level=DIRECTION) and measure stack lift over #1.

---

## 4. HONEST NULLS / NON-FINDINGS
- **Early-arm is not a free lift on Kraken** — window-dependent sign (helped tape, hurt book). Don't stack blind.
- **Deep-bail added ~nothing on XRP** on this window (no deep loss tail in thin XRP swings). Keep it on BTC/ETH.
- **Reversed SOL underperformed forward** on the book window — but this is ONE window and contradicts the tape;
  it is a flag to re-adjudicate, NOT proof the deploy is wrong.
- **E300 / fade full-population per-week tests are NOT runnable on box** for SOL/XRP/DOGE (no 30d tape). The
  E300-XRP/DOGE promise is a Coinbase/Binance-window result awaiting a Kraken pull — genuinely untested there.
- Everything is honest-fill on ONE ~30h low-edge window. The absolute $/hr is not the tape regime; read the
  MECHANICS (direction sign, fill leak, cover_grace lift), not the levels.

---
## 5. XRP — CORROBORATION of the basket_sim_kraken.py standout (Greg's fresh lead)
Independently reproduced this session: XRP base flow-lean **forward, no early-arm, no bail** on the ~30h book,
honest queue-fill = **+12.50 $/hr** (grace300) / **+13.46** (grace600), fill 46–49%, forced-taker 11%→5%,
win 53% — while ETH/BTC/SOL go negative honest on the same low-edge window. XRP's swings fill far better than
the majors (its fill leak is small: ideal +12.4 → honest +7.2 even at grace0, and cover_grace closes most of
the gap). **This is a genuine per-coin execution solution the S63 "stand aside" (30d-tape z=0.7) missed** —
"stand aside" was a 30d-TAPE direction verdict; the BOOK-FILL picture is materially different and positive.
Provisional (one window). Decisive next test: XRP forward flow-lean zigzag + cover_grace on (a) a full 30d
Kraken tape and (b) a normal-edge multi-day book — if the forward sign holds, deploy an XRP cell. This is
shortlist item #1 above. File kraken-tagged per Greg's naming rule.
