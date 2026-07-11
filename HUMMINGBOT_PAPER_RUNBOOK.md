# Hummingbot paper-trade runbook — first live look on the real Kraken book (S77)

> Goal: stand up Hummingbot in **paper-trade mode on Kraken** and watch our quotes fill against the **real
> live order book** — no API key, no capital, no risk. This is the "just run it and see what happens" step.
> What we learn: do our resting quotes actually get filled, how often, and do the fills go against us
> (adverse selection). Honest caveat (ChatGPT is right): Hummingbot paper fills are **optimistic** — it fills
> when the market trades to your price but doesn't fully model queue position. So this is a real-data SANITY
> CHECK, not proof of fill economics. NautilusTrader (queue-aware) is the rigorous follow-up.

## 0. What you need
- A machine that **stays on** (your laptop/desktop left running, or a cheap $5/mo VPS). Not this session.
- **Docker** installed (easiest path). Mac/Windows: Docker Desktop. Linux: `apt install docker.io`.
- ~15 minutes.

## 1. Install + launch Hummingbot (Docker)
```bash
mkdir hummingbot && cd hummingbot
docker run -it --name hb \
  -v $(pwd)/conf:/home/hummingbot/conf \
  -v $(pwd)/logs:/home/hummingbot/logs \
  -v $(pwd)/data:/home/hummingbot/data \
  hummingbot/hummingbot:latest
```
First launch: set a password when prompted. You're now at the `>>>` Hummingbot prompt.

## 2. Turn ON paper mode + connect Kraken (no keys needed)
At the `>>>` prompt:
```
config paper_trade_account_balance
```
Set a fake balance, e.g. `USD 5000` and `BTC 0.1` (paper only). Then confirm paper mode is ON:
```
balance paper
```
Paper trade uses Kraken's **real public order book** — no API key required.

## 3. Create the strategy — pure market making (spread capture)
This is the architecture the realistic-fill test pointed to: **quote BOTH sides, earn the spread** (not chase
a directional bet). Run `create` and answer:
```
create
  What is your market making strategy?            -> pure_market_making
  Enter your maker spot connector                 -> kraken_paper_trade
  Enter the trading pair                          -> BTC-USD          (start here; deepest book)
  How far from mid to place the BID (bid_spread)  -> 0.05             (%, = 5 bps)
  How far from mid to place the ASK (ask_spread)  -> 0.05             (%, = 5 bps)
  Order refresh time (seconds)                    -> 30
  Order amount (BTC)                              -> 0.002            (~$130 notional, paper)
  (accept defaults for the rest)
  Save config as                                  -> pmm_btc_paper
```
> Why these: our signal lives at ~60s, so 30s refresh is reasonable; 5bps each side is a real spread to
> capture on BTC; tiny size so fills are realistic. We'll add a **second, wider config on a more volatile
> pair** (e.g. `SOL-USD` or `ETH-USD` at 8-12 bps) once BTC is running, to compare — wide-spread coins are
> where a maker earns the most.

## 4. Run it + watch
```
start
status        # shows your live bid/ask, mid, and active orders on the real book
history       # after it runs a while: fills, P&L, spread captured
```
Leave it running. Come back over hours/days.

## 5. What to actually look at (this is the whole point)
- **Fill rate** — are the resting orders getting hit at all? (The directional backtest showed only ~29-56%
  fill for directional bets; pure MM quotes both sides so it should fill MORE, both sides.)
- **Net P&L trend** — is spread capture > adverse selection? A market maker earns the spread but loses when
  filled right before an adverse move. `history` shows the net.
- **Markout** — after a fill, does the mid move against the fill (adverse) or stay/revert (good)? Watch the
  price right after fills in `status`.
- **Inventory drift** — does it end up one-sided (all long or all short)? That's unmanaged inventory risk,
  and it's the signal's job (later) to skew quotes and prevent it.

## 6. First-run success criteria (honest, low bar)
This first run is NOT trying to prove profit. Success = (a) it runs stably on the real Kraken book, (b) we
see fills on both sides, (c) we get a first read on fill rate + markout. That tells us whether spread-capture
MM is even viable here before we invest in the rigorous NautilusTrader queue test or wire in the signal skew.

## 7. Next after Hummingbot runs
1. Add the wider-spread pair config (SOL/ETH) and compare fill/markout.
2. Wire our book signal as a **quote skew** (Hummingbot supports it via a custom script / the `quote_gate`
   logic) — skew quotes away from the predicted move to cut adverse selection.
3. NautilusTrader queue-aware shadow test for the rigorous fill economics (the real validation gate).

## Troubleshooting
- Kraken pair format is `BTC-USD` (dash) in Hummingbot.
- If `kraken_paper_trade` isn't listed: `exchange list` to see available paper connectors; update the image
  (`docker pull hummingbot/hummingbot:latest`).
- Logs are in `./logs/` on the host (mounted). Send me any errors and I'll debug.
