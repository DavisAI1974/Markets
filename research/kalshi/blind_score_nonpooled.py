"""How much of the blind's error does the DRIFT metric cancel away? (S108, Greg's rule)

Forward-curve drift is a SUM OF SIGNED ERRORS, so it nets. A day that is +4,000 and a day that is
-4,000 average to a drift of ZERO on a forecaster that was catastrophically wrong twice. Drift is the
right measure of where the integrated curve ENDS UP; it is NOT a measure of accuracy, and it must never
be reported alone.

Greg's standing rule, applied here: never pool or average as the final word - look at each event
individually. This prints the per-day distribution beside the netted number so the netting is visible.
"""
import os as _os
import json

_HERE = _os.path.dirname(_os.path.abspath(__file__))
FC = _os.path.join(_HERE, "forecasts")
RD = _os.path.join(_HERE, "renders", "ng_refine_s95")


def errs_for(n):
    p, ap = _os.path.join(FC, f"grp{n}.json"), _os.path.join(RD, f"g{n}_actual.json")
    if not (_os.path.exists(p) and _os.path.exists(ap)):
        return None
    b = json.load(open(p))
    a = {d["date"]: d for d in json.load(open(ap))["days"]}
    out = []
    for d in b.get("days", []):
        dt = str(d.get("date", "")).replace("-", "")
        g, act = d.get("guess_day_move_usd"), a.get(dt, {}).get("day_move_usd")
        if isinstance(g, (int, float)) and isinstance(act, (int, float)):
            out.append((dt, g, act, g - act))
    return out


print(f"{'grp':>4} {'sum|err|':>9} {'DRIFT':>8} {'survives':>9} {'>1000':>6} {'>500':>6}   three worst days")
print("-" * 88)
rows = {}
for n in range(15, 24):
    e = errs_for(n)
    if not e:
        continue
    rows[n] = e
    sa = sum(abs(x[3]) for x in e)
    dr = sum(x[3] for x in e)
    worst = sorted(e, key=lambda x: -abs(x[3]))[:3]
    print(f"{n:>4} {sa:>9} {dr:>+8} {100*abs(dr)/sa:>8.0f}% {sum(1 for x in e if abs(x[3])>1000):>6} "
          f"{sum(1 for x in e if abs(x[3])>500):>6}   " + "  ".join(f"{x[0][4:]} {x[3]:+}" for x in worst))

print()
print("'survives' = |drift| as a share of total absolute error. Everything else CANCELLED inside the")
print("netting. A LOW percentage means the drift number is flattering the block, not describing it.")

if 21 in rows and 20 in rows:
    print()
    print("=" * 88)
    print("THE G20 -> G21 COMPARISON, STATED HONESTLY")
    print("=" * 88)
    for n in (20, 21):
        e = rows[n]
        sa, dr = sum(abs(x[3]) for x in e), sum(x[3] for x in e)
        print(f"  g{n}: drift {dr:+6}   sum|err| {sa:6}   per-day |err| "
              f"{sorted((abs(x[3]) for x in e), reverse=True)}")
    d20, d21 = rows[20], rows[21]
    s20, s21 = sum(abs(x[3]) for x in d20), sum(abs(x[3]) for x in d21)
    dr20, dr21 = sum(x[3] for x in d20), sum(x[3] for x in d21)
    print()
    print(f"  drift    {dr20:+} -> {dr21:+}   = a {100*(1-abs(dr21)/abs(dr20)):.0f}% 'improvement'")
    print(f"  sum|err| {s20} -> {s21}   = a {100*(1-s21/s20):.0f}% improvement")
    print()
    print("  The gap between those two numbers IS the cancellation. The drift improvement is mostly")
    print("  errors that stopped agreeing with each other, not errors that got smaller.")
