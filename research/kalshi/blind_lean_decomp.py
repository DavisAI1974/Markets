"""Is the blind's error a LEVEL bias (removable by shifting the curve) or SHAPE?

Tests Greg's hypothesis directly: if the blind starts Mondays/Sundays too low and we
just moved the whole curve up, would most of the problem go away?
"""
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_REPO = _os.path.dirname(_os.path.dirname(_HERE))

import json, glob, re, os
import pandas as pd

R = _HERE
FC, RD = f"{R}/forecasts", f"{R}/renders/ng_refine_s95"
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

def load(n):
    p, ap = f"{FC}/grp{n}.json", f"{RD}/g{n}_actual.json"
    if not (os.path.exists(p) and os.path.exists(ap)):
        return None
    b, a = json.load(open(p)), json.load(open(ap))
    am = {d["date"]: d for d in a.get("days", [])}
    out = []
    for d in b.get("days", []):
        dt = str(d.get("date", "")).replace("-", "")
        g = d.get("guess_day_move_usd", d.get("day_move_usd"))
        ac = am.get(dt, {}).get("day_move_usd")
        if isinstance(g, (int, float)) and isinstance(ac, (int, float)):
            dow = _DOW[pd.Timestamp(f"{dt[:4]}-{dt[4:6]}-{dt[6:]}").weekday()]
            out.append((dt, dow, g, ac))
    return out

groups = [n for n in range(15, 24) if load(n)]

print("=" * 100)
print("A. CAN A CONSTANT SHIFT FIX IT?  (k = mean(actual - blind), applied to EVERY day)")
print("=" * 100)
print(f"{'grp':>4} {'sum|err|':>9} {'best k':>8} {'sum|err| after':>15} {'removed':>9} "
      f"{'drift':>8} {'drift after':>12}")
for n in groups:
    rows = load(n)
    errs = [g - a for _, _, g, a in rows]
    k = -sum(errs) / len(errs)                      # the optimal common-mode shift
    before, after = sum(abs(e) for e in errs), sum(abs(e + k) for e in errs)
    drift = sum(errs)
    print(f"{n:>4} {before:>9} {k:>+8.0f} {after:>15.0f} {100*(before-after)/before:>8.0f}% "
          f"{drift:>+8} {drift + k*len(rows):>+12.0f}")

print()
print("=" * 100)
print("B. IS THE BIAS CONCENTRATED ON MONDAY-CLASS DAYS?  (mean signed err = blind - actual)")
print("=" * 100)
print(f"{'grp':>4}   " + "".join(f"{d:>12}" for d in ("Mon", "Tue", "Wed", "Thu", "Fri")))
for n in groups:
    rows = load(n)
    cells = []
    for dow in ("Mon", "Tue", "Wed", "Thu", "Fri"):
        e = [g - a for _, d, g, a in rows if d == dow]
        cells.append(f"{sum(e)/len(e):>+12.0f}" if e else f"{'-':>12}")
    print(f"{n:>4}   " + "".join(cells))

allrows = [(n, *r) for n in groups for r in load(n)]
print()
for dow in ("Mon", "Tue", "Wed", "Thu", "Fri"):
    e = [g - a for _, _, d, g, a in allrows if d == dow]
    if e:
        print(f"  ALL GROUPS {dow}: mean signed err {sum(e)/len(e):>+7.0f}  "
              f"(n={len(e)}, blind too {'HIGH' if sum(e) > 0 else 'LOW'})")

print()
print("=" * 100)
print("C. HOW MUCH OF THE ERROR IS COMMON-MODE AT ALL?")
print("=" * 100)
for n in groups:
    rows = load(n)
    errs = [g - a for _, _, g, a in rows]
    m = sum(errs) / len(errs)
    ss_tot = sum(e * e for e in errs)
    ss_res = sum((e - m) ** 2 for e in errs)
    print(f"  g{n}: mean err {m:>+7.0f} | dispersion around it {(ss_res/len(errs))**0.5:>7.0f} "
          f"| variance explained by a constant: {100*(1-ss_res/ss_tot):>4.0f}%")
