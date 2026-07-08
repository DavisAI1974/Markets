"""S77: compounding model for the $5k bank, capped at $15k (Greg). Compound the strategy's hourly return
until the bank hits $15k, then STOP compounding (withdraw everything above $15k as profit). The $15k cap is
the practical capacity ceiling — thin books can't absorb an ever-growing bank.

The backtest blend is ~+0.55%/hr on $5k (Kraken corrected, provisional: one ~5h window, mid-price, overfit
risk). Real trading delivers a FRACTION of a mid-price backtest (spread, adverse selection, competition), so
we model a RANGE of haircuts. Crypto is 24/7 + automated, and the $/hr is already wall-clock (occupancy in
the denominator), so ACTIVE_H defaults to 24 but is a knob.

    python3 compound_model.py
"""
START, CAP = 5000.0, 15000.0
ACTIVE_H = 24.0            # hours/day the bot is live (24 = always-on automated)
BACKTEST_RATE = 0.0055    # +0.55%/hr on deployed capital (the corrected Kraken blend)

SCENARIOS = [
    ("optimistic  (backtest holds, 1.0x)", 1.00),
    ("base        (1/2 of backtest)",       0.50),
    ("conservative(1/3 of backtest)",       0.33),
    ("pessimistic (1/5 of backtest)",       0.20),
    ("marginal    (1/10 of backtest)",      0.10),
]


def sim(rate_hr):
    """Compound hour by hour to CAP, then steady-state. Returns (days_to_cap, daily_at_cap, month1_profit)."""
    bank = START; hrs = 0; capped_at = None
    # grow to cap
    while bank < CAP and hrs < 24 * 365:
        bank *= (1 + rate_hr)
        hrs += 1
        if bank >= CAP:
            bank = CAP; capped_at = hrs; break
    days_to_cap = (capped_at / ACTIVE_H) if capped_at else None
    # daily profit once capped (withdraw the hourly earnings on $15k)
    daily_at_cap = CAP * ((1 + rate_hr) ** ACTIVE_H - 1)
    # 30-day cumulative profit (growth phase compounds; capped phase withdraws)
    bank = START; profit = 0.0
    for h in range(int(30 * ACTIVE_H)):
        earn = bank * rate_hr
        if bank >= CAP:
            profit += earn                      # withdraw (bank stays at cap)
        else:
            bank = min(bank + earn, CAP)         # reinvest until cap
    month1 = (bank - START) + profit             # growth in bank + withdrawn profit
    return days_to_cap, daily_at_cap, month1


print(f"COMPOUNDING MODEL — ${START:,.0f} -> cap ${CAP:,.0f}, {ACTIVE_H:.0f}h/day, backtest {BACKTEST_RATE*100:.2f}%/hr\n")
print(f"{'scenario':<38}{'%/hr':>7}{'%/day':>8}{'days->$15k':>11}{'$/day@cap':>11}{'month-1 $':>11}")
for name, mult in SCENARIOS:
    r = BACKTEST_RATE * mult
    daily_pct = ((1 + r) ** ACTIVE_H - 1) * 100
    d2cap, daily, m1 = sim(r)
    d2cap_s = f"{d2cap:.1f}" if d2cap else ">1yr"
    print(f"{name:<38}{r*100:>6.3f}%{daily_pct:>7.1f}%{d2cap_s:>11}{daily:>11,.0f}{m1:>11,.0f}")

print("""
READS:
- % / hr is on DEPLOYED capital; %/day compounds it over the active hours.
- 'days->$15k' = compounding growth phase; '$/day@cap' = steady profit once at the $15k ceiling.
- 'month-1 $' = total profit in the first 30 days (growth in bank + withdrawals after the cap).

CAVEATS (load-bearing):
- The backtest 0.55%/hr is PROVISIONAL: one ~5h recent window, MID-PRICE P&L, overfit risk, and it
  assumes 0% maker + a patient maker-exit that fills. Even the 'optimistic' row is an UPPER bound.
- Real desks rarely keep >1/3 of a mid-price backtest edge -> the 'conservative'/'pessimistic' rows
  are the honest planning numbers. Validate LIVE (paper loop, ~$0) before trusting any row.
- The $15k cap exists BECAUSE the edge doesn't scale past thin-book capacity; beyond $15k you need
  more venues/cells or a different game (perps, data product), not more capital in these books.
""")
