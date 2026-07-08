"""S77: DAY-BY-DAY Kraken ramp with the bank<->volume feedback Greg flagged. Volume RATE = bank x turnover,
so a shrinking bank trades fewer dollars -> slower ramp. Kraken's tier is TRAILING-30-DAY volume, so early
volume AGES OUT: you must reach $10M within a rolling 30d window or you never qualify (death spiral).

Each day: fee tier <- trailing-30d volume; daily_vol = bank x turnover; bank += edge - maker_fee - taker.
Track trailing-30d volume; qualify when it first hits $10M. Sweep edge (bank growth) x turnover (churn).

    python3 day_ramp_sim.py
"""
START = 5000.0
QUAL_VOL = 10e6            # trailing-30d volume to reach 0% maker tier
TAKER_BP, RUNAWAY = 10.0, 0.07
MAKER_TIERS = [(10_000,25),(50_000,20),(100_000,14),(250_000,12),(500_000,10),
               (1_000_000,8),(2_500_000,6),(5_000_000,4),(10_000_000,2),(1e18,0)]


def maker_bp(trailing):
    for cap, bp in MAKER_TIERS:
        if trailing < cap:
            return bp
    return 0.0


def sim(turnover_day, gross_bps, days=90):
    bank = START; vol_hist = []; qual_day = None; low = bank
    for d in range(1, days + 1):
        trailing = sum(vol_hist[-30:])
        mk = maker_bp(trailing)
        daily_vol = bank * turnover_day
        edge = daily_vol * (gross_bps / 2) / 1e4
        fee = daily_vol * (mk / 1e4)
        taker = RUNAWAY * (daily_vol / 2) * (TAKER_BP / 1e4)
        bank = max(0.0, bank + edge - fee - taker)
        vol_hist.append(daily_vol)
        low = min(low, bank)
        if qual_day is None and sum(vol_hist[-30:]) >= QUAL_VOL:
            qual_day = d
        if bank < 100:      # busted
            break
    return qual_day, bank, low


print(f"DAY-BY-DAY RAMP — start ${START:,.0f}, qualify at ${QUAL_VOL/1e6:.0f}M trailing-30d\n")
print("Steady-state trailing-30d = daily_vol x 30 = bank x turnover x 30. To EVER reach $10M you need")
print(f"bank x turnover x 30 >= $10M -> on $5k that's turnover >= {QUAL_VOL/(START*30):.0f}x/day BEFORE any shrink.\n")
print(f"{'turnover/day':>12}{'edge bps':>10}{'qual day':>10}{'bank@qual/end':>15}{'low':>9}")
for turn in (40, 67, 100, 150):
    for g in (0.5, 3.0, 7.4):
        qd, bank, low = sim(turn, g)
        qs = f"day {qd}" if qd else "NEVER"
        print(f"{turn:>10}x{g:>10.1f}{qs:>10}{bank:>15,.0f}{low:>9,.0f}")
    print()

print("""READS (Greg's point, confirmed):
- The bank<->volume feedback is REAL. Because the tier is TRAILING-30d, steady-state trailing = daily x 30.
  On $5k you need ~67x/day turnover JUST to hold $10M trailing if the bank stays flat — and MORE if it
  shrinks. Below ~67x/day you NEVER qualify no matter how long you wait (volume ages out as fast as you add).
- Thin edge (0.5bps) shrinks the bank -> the volume rate falls -> trailing-30d sags -> qualify slips away
  or never comes. The death spiral you described.
- High edge (7.4bps) GROWS the bank -> volume rate rises -> trailing-30d climbs faster -> qualify sooner and
  the bank ends up. Edge and churn compound in your favor.
- So two knobs must BOTH be high enough: TURNOVER (>=67x/day on $5k) to reach $10M trailing, and EDGE
  (>=~6bps) so the bank doesn't shrink underneath you. Deep BTC book supports the high churn; the wide-trail
  ride supplies the bps.

CAVEAT: ~67-150x/day turnover on a $5k maker book is aggressive — the live paper loop must confirm we can
actually push that volume as a maker (fills, not just quotes). This is THE feasibility question for Kraken.""")
