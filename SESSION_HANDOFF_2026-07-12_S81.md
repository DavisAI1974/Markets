# SESSION HANDOFF — S81 (2026-07-12) — Kalshi: the futures→Kalshi LAG made tradeable-or-not, and the sub-minute pivot to Pyth

Branch **`claude/kalshi-s79-kickoff-ij8t9o`** (= repo DEFAULT; push there). The harness assigned a stale
S70 branch (`claude/kalshi-s81-kickoff-qvtgbg`) — the exact trap the kickoff warned about; switched to s79.
All work committed + pushed: `74bac6d` (lag backtest) → `b44e1be` (economic gate) → `5089e72` (hold tool) →
`956a2ef` (findings) → `17850e9` (Pyth collector + durable workflow) → (this handoff + KALSHI_TRADING.md).

## THE SESSION: turn the S80 measured lag into a MEASURED net-of-toll edge

Greg's steer: "it might be just as simple as taking advantage of the lag." Built
`research/kalshi/lag_exploit_backtest.py` and worked it end to end on the 496k WTI tape (re-pulled; local)
+ CL=F 1-min futures (Yahoo, 7-day window = Jul 6–10). Per-trade, per-cell, leakage-gated, **no averaging**.

### What the lag IS (confirmed) and what it ISN'T (yet)
1. **Mode B (cross-strike, no futures feed): NULL.** Strikes are synchronous with each other (significant
   lead-lag all at lag 0). The lag is futures-vs-Kalshi ONLY — no Kalshi-only free lunch; an external
   futures feed is required.
2. **Mode A (futures→Kalshi): the edge is real but SIZE-vs-FEE bound, and direction is the easy part.**
   - Firing on everything (2,721 fires) = GROSS +1,856¢ but −2,147¢ after taker fees (fees on many tiny
     reprices swamp the capture). Firing-on-everything LOSES.
   - **Direction is predictable and sharpens with move size** — on provably-lagging contracts (leadlag
     z≥3): next-min direction hit-rate `0.55 @ $0.05 → 0.64 @ $0.10 → 0.77 @ $0.40+`. Greg was right:
     direction is easy.
   - **The obstacle is size vs fee, not direction.** Median 1-min reprice ≈ 1.0¢ < ~2.4¢ round-trip taker
     fee. Net-of-fee turns positive only where the move beats the fee: **lagging × ≥$0.40 move = +91¢ over
     26 trades, 0.77 direction.** Real but RARE at 1-min (~26 events/5 days).
   - **Corrected two over-negative reads (mine):** (a) I over-charged the toll (full spread + 2 fees) — fee
     alone is small (0.3–1.75¢/side, lower at extremes) and maker-exit ~halves it; (b) I pooled small moves
     + synchronous contracts, burying the edge. Gross reprice is POSITIVE every one of the 5 days.

### The sub-minute pivot (Greg: "1 minute is an eternity … NYMEX moves a lot in a minute")
- **1-min is coarse on BOTH sides.** Yahoo's 1-min high/low was broken (range < close-move = under-sampled).
  Pyth's real 1-min OHLC: median intra-minute range **11¢** vs 6.4¢ close-to-close (1.6× hidden); **15–23¢
  ranges around the 14:30 EIA release**. The reprice opportunity is much bigger than the 1-min close showed.
- **Historical sub-minute NYMEX EXISTS** — Pyth Benchmarks stores per-second history
  (`benchmarks.pyth.network/v1/updates/price/{ts}?ids={id}`), but it's **aggressively rate-limited** (~2 req/s,
  ~50% success) so a dense window is slow to pull.
- **Direct event-study (10s NYMEX + ms Kalshi tape, Jul 8):** on a +17¢ NYMEX jump (14:27), the liquid
  strike T74.99's FIRST reprice tick came ~7s later (14:27:06.958) and it kept climbing 49→53→55 over ~20s.
  The 1-min "half lag a full minute" was largely **coarse-bar aliasing** — but **7–20s is a HUGE exploitable
  window** (Greg), not "near-synchronous": with a sub-second NYMEX feed you see the move instantly and have
  seconds to hit the stale Kalshi quote before it catches up. This is a **persistent latency edge on every
  meaningful move**, and the LESS-liquid strikes lag EVEN LONGER — this was the fastest/most-liquid strike.
  Time-to-act is NOT the constraint; the remaining question is the reprice SIZE vs the toll on a given move.
  One event so far — the live feed gives the per-contract distribution of the window.

### Pyth feed — BUILT + LIVE (the real instrument)
- `research/kalshi/pyth_collector.py` — stdlib SSE stream of the front-month feeds **WTIQ6 / NGDQ6 / BRENTU6**
  (Pyth is Kalshi's own settlement source). Sub-second ticks → `data/pyth_ticks/` (local); dedup on advancing
  publish-time (skips the weekend frozen price). Verified: connects + parses through the proxy.
- `.github/workflows/pyth_collector_durable.yml` — 6h durable cron mirroring the bins collector → gzip + push
  to `data/pyth-ticks`. **Run #1 live** (`29185118959`); s79 is default so the 6h cron recurs. Ticks accrue
  when energy futures reopen (Sun ~6 PM ET), well before Thu's natgas release.
- **Front-month ROLL DATES (re-point after expiry):** WTIQ6 2026-07-21, NGDQ6 2026-07-29, BRENTU6 2026-07-31.

## Files this session
New: `research/kalshi/lag_exploit_backtest.py`, `research/kalshi/pyth_collector.py`,
`.github/workflows/pyth_collector_durable.yml`, `research/kalshi/LAG_EXPLOIT_FINDINGS_S81.md`,
`KALSHI_TRADING.md` (the file index Greg asked for). Local-only: `data/pyth_ticks/`, `data/kalshi_hist_trades/`.

## NEXT (S82)
1. **Sub-second lag on LIVE ticks** (once `data/pyth-ticks` accrues): per-contract, in seconds — WHICH strikes
   lag, by how many seconds, and does the reprice (whole, captured before decay) clear the toll? Use
   `score_hold` (fire-quick-then-hold) at real resolution. This is the decisive tradeability test.
2. **Thursday 7/16 EIA natgas (14:30 UTC)** — first live release: `release_book_signal.py --test` on the
   accrued book + the busy-day natgas lag on live Pyth ticks. Run `consensus_poll.py` before (forecast) + after.
3. **THE PER-TRADE LEVEL-HIT DATASET (priority-1, NOT yet started)** — the each-trade-individually rebuild on
   the 496k tape: context + outcome per level-hit event, distributions + winner fingerprints, herd/whale
   fingerprint scored not assumed. The continuation predictor.
4. Standing: front-month roll re-point (Jul 21+); paper-loop RSA creds; OD-weather → kalshi_score (Greg's spec).

## RULES (unchanged, load-bearing)
EACH TRADE INDIVIDUALLY, never average; per-cell always; exclude the settle window; catalyst=trigger+coarse
size / book+flow imbalance+exhaustion=direction+magnitude / herd breadth=continuation, whale=scalp-only;
leakage gate before any backtest; zero synthetic; provisional-until-live; weather = Greg's spec, hands off.
