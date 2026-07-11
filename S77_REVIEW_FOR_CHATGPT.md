# S77 REVIEW — DavisAI Markets: strategy economics, findings, and the plan (2026-07-11)

> Self-contained review of the S77 session for an outside reviewer (ChatGPT). Everything below is on branch
> `claude/book-swing-s77-kraken-meomsh` (github.com/DavisAI1974/Markets). All $/hr numbers are PROVISIONAL:
> one recent ~5h–40h window per coin, MID-PRICE P&L (an upper bound), overfit risk from grid selection.
> The whole point of the plan's step 1 is to replace these with realistic fill-aware numbers before any real money.
> **We want a critical, skeptical review — poke holes in the economics, the fee assumptions, and the plan.**

## 1. THE ASSET
A forward-looking order-book signal on crypto spot: the resting L2 book's shape/imbalance leans into a price
turn ~1s BEFORE price moves (standard order-flow imbalance confirms the turn ~18bps late). It is a **fee-floor
edge** — NEGATIVE at taker fees, POSITIVE only at 0% maker or a maker rebate. Deployed per-cell = asset × venue × side.
- **FILTER** = the book pre-fire tell (which turns are real; ~71% hit on BTC at 60s, ~55% ETH). **TIMING** = a
  1-sec price-reversal (enters ~5.6bps off the true turn). Signal "lives" at ~60s, not 15–30s.
- Tools built (all in `research/shape_s71/`, plus `odcore/`): `early_signal.py` (book imbalance → magnitude +
  direction, `fit_direction_sign`), the ride-to-reversal swing, a patient maker-exit, a per-cell horizon fit,
  the OD/dipole layer (coupling, lead-lag, decoupling, regime classifier), and a mostly-built regime-gated
  market-making "quote service" (branch `claude/bold-ptolemy-qwgkcx`, Phase 0–1: `backend/quote_gate.py`).

## 2. KEY EMPIRICAL FINDINGS THIS SESSION
### 2a. The signal is VENUE-SPECIFIC (we have both Coinbase and Kraken L2 books)
Best-venue-per-coin, 0% maker, patient maker-exit, ×0.9 fill haircut, mid-price:
| coin | Kraken 0% $/hr | Coinbase 0% $/hr | best |
|---|---|---|---|
| BTC | **+11.6** | −1.3 | Kraken |
| ETH | +0.6 | **+21.2** | Coinbase |
| XRP | −0.2 | **+30.2** | Coinbase |
| DOGE | −11 | **+29.5** | Coinbase |
| SOL | neg | neg | neither (no directional edge — spread-capture only) |
Picking each coin's best venue roughly TRIPLES the majors' contribution. (Coinbase per the paper: BTC+ETH strong.)

### 2b. Fee classification (corrected mid-session)
- 5 majors (BTC/ETH/SOL/XRP/DOGE) + 16 "large minors" all get **0% maker** at the tier. NO rebate.
- ONLY **HYPE + XPL** (illiquid) get Kraken's **−2bp maker rebate** (Spot Maker Rebate program). The real −2bp
  sleeve is a separate ~116 THIN coins we don't collect books for yet.
- My earlier "+$57/hr on $5k" blend WRONGLY gave all 16 minors the rebate → inflated. **Corrected: +$27.7/hr**
  on $5k (Kraken-only). Venue-per-cell (Coinbase majors) is separate and additive.

### 2c. The patient maker-exit
Greg's idea: on volatile coins, rest the exit as a maker and sit for the oscillation to bring price back →
fill as maker (earn rebate) instead of crossing (taker). Modeled: **92–98% maker fills** by sitting 30–300s.
Turns the taker floor (−$34/hr blend) into the rebate ceiling (+$90/hr). BUT: only suits volatile/wide-spread
coins; on deep tight-spread MAJORS it doesn't apply (price doesn't oscillate back) → majors use a directional
ride with a normal exit, NOT a patient sit.

### 2d. Shape-follow gate on the majors — NULL (rigorous)
Tested whole-curve shape-matching (fire winner-shapes, skip loser-shapes) on BTC/ETH/XRP/DOGE. It does NOT lift
$/hr above ungated — reproduces the SOL "direction wall." Reversing each OOS loser's side flips 94–100% of them
to winners → **win/lose IS direction**, and a winner and its loser-twin share the identical entry shape, so no
entry-shape gate can separate them. Takeaway: **direction comes from the book signal, NOT the shape**; the shape
is a good ENERGY/DURATION descriptor → use it for SIZING, not the fire/skip decision. (`research/shape_s77/`.)

## 3. THE THREE CEILINGS (why $5k trading is capped)
1. **Capital.** Realistic ~$6–9/hr on $5k (after adverse-selection haircut of the mid-price number) = ~$75–110/day
   ≈ $2–3k/month. The % looks huge (~40–90%/mo) but that's a mirage — dollars are tiny because $5k is tiny.
   Public retail MM bots (Hummingbot-class) realistically do 0.5–3%/month; industry MM captures ~1bp per $ of
   matched volume ($8k earned per $8M traded). Our per-volume capture is in that ballpark; the dollar ceiling is
   VOLUME, and volume = capital.
2. **Fee floor.** The edge is 0%-maker-only; deeply negative at taker. Coinbase gives a New-Client Intro Rate =
   **0% maker for 1–2 months, NO volume bar** → the clean entry (no ramp, bank intact). Holding the program past
   intro needs ~0.8% of Coinbase total maker vol ≈ **~$250M/month AMV**, reachable via multipliers (low-liq 30×,
   BTC 10× this month) with only ~$8–25M actual volume.
3. **Thin-book saturation + the Kraken ramp trap.** Compounding a $5k bank caps at ~$15–60k (thin books can't
   absorb more). And reaching Kraken's 0% tier costs ~$4.5–6k in ramp fees on a churny config — MORE than the
   $5k bank. Modeled two ways Greg pushed on:
   - Longer legs (wide-trail ride, ~7bps/trade) make the ramp self-funding (fees are on volume, and volume past
     $10M is free); at ~6bps breakeven, at 7.4bps +$1,120 profit through the ramp.
   - BUT the tier is **trailing-30-day** volume, and volume rate = bank × turnover. On $5k you need **≥67×/day
     turnover just to hold $10M trailing**; thin edge shrinks the bank → volume rate falls → **NEVER qualifies
     (death spiral)**. Only high edge (7.4bps) + high churn (100×/day) qualifies (~day 30). So Kraken-direct is
     fragile for cold-start seed capital; **Coinbase-intro is the clean path.**

## 4. THE ECONOMIC MODEL — how the money is actually made
The signal is worth a fraction of a bp per trade, so you monetize it via VOLUME — yours or others':
1. **Trade it (our capital):** spread + edge − fees ≈ $2–3k/mo on $5k, capped by capital. Its real job is to
   produce the **validated track record** that sells #2 and #3.
2. **MM-as-a-service (token projects' capital) — the real, uncapped business:** a project hires us as designated
   market maker; we get paid FOUR ways per client — a **retainer** (~$3–30k/mo), an **inventory loan** (they lend
   us tokens + stablecoin float to quote with → we deploy THEIR capital, not our $5k → no ceiling), **spread +
   exchange rebates** we keep, and a **call option** on the loaned tokens. 5–10 clients → $30–300k/mo. Needs
   clients (token projects) + track record + the quoting engine (mostly built).
3. **Sell the signal (no capital, no market risk):** license the feed — energy desks $500–$5k/mo per seat
   (Greg's prior career = the sales channel), institutional higher. SEC-clean (newsletter precedent).
- NOTE: the "friends brief" (Option E, retail signal feed) is NOT the quote service. The quote-service notes
  describe our OWN-capital MM engine (no clients, no credit) — great tech but the same capital ceiling. The
  ceiling-breaking move is #2 (clients supply inventory-on-credit) or #3 (subscribers).

## 5. THE PLAN (Greg's order: 1 → 2 → 3)
1. **VALIDATE** — realistic-fill test. Replace mid-price P&L with queue-based maker fills (fill only when price
   trades THROUGH our level; mark against the SUBSEQUENT move) on our Kraken+Coinbase L2 books, per cell, for the
   wide-trail ride + patient exit. Tool: **NautilusTrader** (open-source, models L2 queue fills, Kraken Pro
   connector, same code backtest→live) as primary; Hummingbot `kraken_paper_trade` as a quick live sanity check.
   Output: the two numbers that gate everything — real gross bps/trade and achievable maker turnover.
2. **REVIVE the quote-service engine** (`claude/bold-ptolemy-qwgkcx`, Phase 0–1 built) and plug in this session's
   book signal + venue-per-cell economics into `quote_gate` (book lean = spread-skew/direction bias; decoupling/
   regime = when to pull; shape/energy = sizing).
3. **SCOPE MM-as-a-service** — what a first token-project deal looks like (retainer + token-loan + call-option
   structure), and the BD path (track record + Greg's credibility as the wedge).

## 6. QUESTIONS FOR THE REVIEWER
- Are the fee assumptions right (Coinbase 0% intro no-volume-bar; the ~$250M AMV hold threshold; Kraken −2bp only
  on illiquid pairs; the multipliers changed Feb 1 and Jul 1 2026 — verify)?
- Is the adverse-selection haircut (keep 1/3–1/2 of a mid-price maker edge) reasonable, or too generous?
- Is MM-as-a-service (#2) the right ceiling-breaker for a solo US founder with $5k, or is the signal-license (#3)
  the faster/safer first revenue? What's the realistic first-deal size + timeline?
- Any fatal flaw in the venue-per-cell + Coinbase-intro entry plan?
