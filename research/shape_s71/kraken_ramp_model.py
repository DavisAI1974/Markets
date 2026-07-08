"""S77: Kraken ramp cost vs EDGE PER TRADE. Greg's question: can we ramp to the $10M tier for < $5k in fees
if we keep trade legs LONGER (bigger edge/trade) and target ~$15M volume for the month?

Key facts:
- Fees are charged on VOLUME, not trade count. To qualify you must trade ~$10M (declining maker tiers
  25bp -> 0). Beyond $10M cumulative you're AT the tier -> the rest of the month is 0% maker (free).
- So targeting $15M = ~$10M at declining fees + $5M free, and you EARN edge on all $15M.
- Longer legs (wide-trail ride) => higher gross bps/trade => higher edge per unit volume => offsets the fee.
  Thin churn (~0.5bps) bleeds; a wide-trail ride (~7bps, the paper's config) can break even or profit.

Net month = edge(volume) - maker_fee_ramp - taker_runaways. We sweep gross bps/trade.

    python3 kraken_ramp_model.py
"""
TARGET_VOL = 15e6            # monthly volume target (>$10M to clear the tier with margin)
TIER_VOL = 10e6             # cumulative volume to reach 0% maker
TAKER_BP_AT_TIER = 10.0     # Kraken standard taker ~10bp (exits that cross)
RUNAWAY_FRAC = 0.07         # ~7% of exits fail the patient maker-exit and cross

# Kraken standard MAKER tiers: (cumulative-volume cap, maker bps)
MAKER_TIERS = [(10_000,25),(50_000,20),(100_000,14),(250_000,12),(500_000,10),
               (1_000_000,8),(2_500_000,6),(5_000_000,4),(10_000_000,2)]


def ramp_maker_fee(vol):
    """Integral of the declining maker fee over `vol` of cumulative volume (0% past $10M)."""
    fee = 0.0; prev = 0
    for cap, bp in MAKER_TIERS:
        if vol <= prev:
            break
        seg = min(vol, cap) - prev
        fee += seg * (bp / 1e4)
        prev = cap
    # anything above $10M is at 0% maker
    return fee


def net_month(gross_bps_per_trade):
    # edge per unit VOLUME = gross_bps on notional S, but a round-trip trades 2S of volume -> /2
    edge = TARGET_VOL * (gross_bps_per_trade / 2) / 1e4
    maker_fee = ramp_maker_fee(TIER_VOL)                          # only the first $10M is charged
    taker = RUNAWAY_FRAC * (TARGET_VOL / 2) * (TAKER_BP_AT_TIER / 1e4)  # runaway exits (exit = half the volume)
    return edge, maker_fee, taker, edge - maker_fee - taker


print(f"KRAKEN RAMP — target ${TARGET_VOL/1e6:.0f}M/mo volume, tier at ${TIER_VOL/1e6:.0f}M\n")
print(f"  maker fees on the first $10M (declining 25->0bp): ${ramp_maker_fee(TIER_VOL):,.0f}")
print(f"  (volume past $10M is at 0% maker — free)\n")
print(f"{'gross bps/trade':>16}{'edge':>10}{'maker fee':>11}{'taker':>9}{'NET month':>11}{'ramp<$5k?':>11}")
for g in (0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 7.4):
    edge, mk, tk, net = net_month(g)
    tag = "YES" if -net < 5000 else "no"
    tag = "PROFIT" if net > 0 else tag
    print(f"{g:>15.1f}{edge:>10,.0f}{mk:>11,.0f}{tk:>9,.0f}{net:>11,.0f}{tag:>11}")

# breakeven edge
lo, hi = 0.0, 20.0
for _ in range(40):
    mid = (lo + hi) / 2
    if net_month(mid)[3] < 0: lo = mid
    else: hi = mid
print(f"""
BREAKEVEN: ~{hi:.2f} gross bps/trade makes the whole month net-zero (fees fully covered by edge).
- Below that the ramp is a (shrinking) cost; above it, the ramp PAYS YOU while you qualify.
- The thin churny book-swing (~0.5bps) bleeds ~-$4k (my earlier number, confirmed).
- The wide-trail LONGER-LEG ride (paper's +7.4 gross bps) is comfortably PROFITABLE through the ramp.
- So YES — keeping legs longer (higher bps/trade) is exactly what gets Kraken under $5k / to break-even.

CAVEATS: +7.4 bps is ONE window, n=100, BTC/Coinbase — unvalidated on Kraken across $15M of real volume.
If the live edge is ~2-3 bps, the ramp still costs ~$1-3k (under $5k, but a cost). Longer legs also need
BIGGER size/trade to hit $15M with fewer trades -> use the DEEP books (BTC) where size fills cleanly.
""")
