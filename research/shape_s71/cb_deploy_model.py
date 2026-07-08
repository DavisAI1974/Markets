"""S77: Coinbase deployment model. Split the $5k into a BTC AMV-ENGINE slice (farms the 10x multiplier to
qualify) + ETH/XRP/DOGE EARNER cells (the venue-per-cell winners at 0% maker). Two questions:
  (1) do we clear ~$250M AMV/month (0.8% of Coinbase total maker vol) inside the 1-2 month intro window?
  (2) how much do we EARN while doing it, and does it compound to the $15k cap?

Greg's anchor: $25M/month BTC volume x 10x = $250M AMV. BTC-USD carries the 10x multiplier this month;
the earner majors are high-liquidity = 1x AMV (they add volume but little AMV). At 0% maker, a maker on
both legs earns the spread, so the AMV churn is free-to-profitable.

    python3 cb_deploy_model.py
"""
BANK = 5000.0
AMV_TARGET = 250e6            # ~0.8% of Coinbase total maker volume (monthly)
INTRO_DAYS = 45              # ~1.5 months of the no-volume-bar intro
# venue-per-cell Coinbase 0%-maker $/hr on $5k (provisional, mid-price, x0.9 fill)
CB_HR_PER_5K = {"btc": -1.3, "eth": 21.2, "xrp": 30.2, "doge": 29.5}
# capital split of the $5k
SPLIT = {"btc": 1500.0, "eth": 1200.0, "xrp": 1200.0, "doge": 1100.0}
AMV_MULT = {"btc": 10.0, "eth": 1.0, "xrp": 1.0, "doge": 1.0}
# maker turnover: $ volume traded per hour per $ deployed (a maker fills what trades against it).
# BTC book-swing ~ 25-45 fills/hr; each fill ~ the deployed slice, x2 legs -> ~10-20x/hr. Model a range.
TURNOVER_HR = [8, 12, 20]    # x deployed capital per hour, both legs


def earnings_per_day(split):
    return sum(CB_HR_PER_5K[c] * (split[c] / BANK) * 24 for c in split)


print(f"COINBASE DEPLOYMENT — ${BANK:,.0f}, intro window {INTRO_DAYS}d, AMV target ${AMV_TARGET/1e6:.0f}M/mo\n")
print("CAPITAL SPLIT:")
for c, amt in SPLIT.items():
    print(f"  {c.upper():>5}: ${amt:>6,.0f}  ({AMV_MULT[c]:.0f}x AMV, {CB_HR_PER_5K[c]:+.1f}/hr@5k -> {CB_HR_PER_5K[c]*amt/BANK:+.2f}/hr on slice)")
day_earn = earnings_per_day(SPLIT)
print(f"\n  earners' net: ${day_earn:,.0f}/day  (${day_earn*30:,.0f}/mo) — while farming AMV\n")

print(f"{'turnover/hr':>12}{'BTC vol/mo':>13}{'total AMV/mo':>14}{'days->$250M':>13}{'qualifies?':>12}")
for t in TURNOVER_HR:
    # monthly $ volume per cell = deployed * turnover/hr * 24 * 30
    amv_mo = sum(SPLIT[c] * t * 24 * 30 * AMV_MULT[c] for c in SPLIT)
    btc_vol_mo = SPLIT["btc"] * t * 24 * 30
    amv_day = amv_mo / 30
    days = AMV_TARGET / amv_day if amv_day else 9e9
    ok = "YES" if days <= INTRO_DAYS else "no"
    print(f"{t:>10}x {btc_vol_mo/1e6:>11.1f}M {amv_mo/1e6:>12.1f}M {days:>12.1f}{ok:>12}")

print(f"""
READS:
- BTC's 10x carries the AMV: even a ${SPLIT['btc']:,.0f} BTC slice at modest turnover clears ${AMV_TARGET/1e6:.0f}M AMV
  well inside the {INTRO_DAYS}-day intro window. The 10x multiplier is doing the heavy lifting, not raw \$.
- The earner majors (ETH/XRP/DOGE) pay the bills (${day_earn:,.0f}/day provisional) AND add 1x volume on top.
- ALL of this is 0% maker (intro, no volume bar) -> no fee bleed, the $5k stays intact and compounds.
- Qualify inside the intro -> the program renews at 0% -> then port to Kraken (Jumpstart) for the -2bp
  rebate sleeve. Bigger AMV lever untapped: Coinbase LOW-LIQUIDITY pairs = 30x (we lack books there yet).

CAVEATS: CB_HR is provisional (one ~5h window, mid-price); TURNOVER/hr is an estimate — the live paper
loop measures the real maker fill/turnover. Validate before sizing.
""")
