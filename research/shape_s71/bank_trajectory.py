"""S77: does the $5k get drawn DOWN during the Kraken ramp? Trace the actual account balance trade-by-trade.
Fees hit the balance on every fill; edge is added on every close. Net per round-trip = edge - entry_fee -
exit_fee. Early ramp = HIGH maker fee (25bp) -> if edge < fee the bank SHRINKS; late ramp = LOW fee (2bp) ->
bank recovers/grows. We walk cumulative volume 0 -> $15M and report the balance path, the LOW point
(max drawdown = how close to zero we get), and the ending balance.

    python3 bank_trajectory.py
"""
START = 5000.0
TARGET_VOL = 15e6
TAKER_BP = 10.0
RUNAWAY = 0.07
MAKER_TIERS = [(10_000,25),(50_000,20),(100_000,14),(250_000,12),(500_000,10),
               (1_000_000,8),(2_500_000,6),(5_000_000,4),(10_000_000,2),(1e18,0)]


def maker_bp(cum_vol):
    for cap, bp in MAKER_TIERS:
        if cum_vol < cap:
            return bp
    return 0.0


def trace(gross_bps):
    bank = START; cum = 0.0; step = 25_000.0     # $25k of volume per step
    low = bank; low_at = 0.0
    while cum < TARGET_VOL:
        dV = min(step, TARGET_VOL - cum)
        mk = maker_bp(cum + dV / 2)
        edge = dV * (gross_bps / 2) / 1e4        # edge per unit volume (round-trip trades 2x notional)
        fee = dV * (mk / 1e4)                     # maker fee on this volume
        taker = RUNAWAY * (dV / 2) * (TAKER_BP / 1e4)
        bank += edge - fee - taker
        cum += dV
        if bank < low:
            low, low_at = bank, cum
    return bank, low, low_at


print(f"BANK TRAJECTORY through a ${TARGET_VOL/1e6:.0f}M Kraken ramp (start ${START:,.0f})\n")
print(f"{'gross bps/trade':>16}{'LOW point':>12}{'(at vol)':>12}{'END balance':>13}{'survives?':>11}")
for g in (0.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.4):
    end, low, low_at = trace(g)
    surv = "YES" if low > 0 else "BUST"
    print(f"{g:>15.1f}{low:>12,.0f}{low_at/1e6:>10.1f}M{end:>13,.0f}{surv:>11}")

print(f"""
READS (answering "are fees bringing the $5k down?"):
- YES — fees come out of the balance on every fill. In the EARLY ramp the maker fee is 25->8bp, well above
  a few-bps edge, so the bank DIPS. As cumulative volume climbs, the fee falls (to 2bp, then 0), and if the
  edge holds the bank RECOVERS and grows. The 'LOW point' is the scariest moment (max drawdown).
- Thin churn (0.5bps): the bank bleeds almost monotonically -> ends near ${trace(0.5)[0]:,.0f}. Dangerous: little
  cushion, and a shrinking bank makes the $15M volume slower to reach (real death-spiral risk).
- Wide-trail longer legs (5-7bps): the bank dips modestly early then climbs back; at 7.4bps it never falls
  far and ends ABOVE $5k. This is why longer legs matter — they keep net-per-trade positive sooner.
- KEY: you must survive the LOW point. Start with the WHOLE $5k as trading capital, ramp on the DEEP book
  (BTC) so fills are clean, and lean on the wide-trail edge so the early-tier dip stays shallow.

CAVEAT: assumes the gross-bps edge holds LIVE across $15M. If it's thin early, the low point is deeper —
validate the wide-trail bps before committing real ramp capital.
""")
