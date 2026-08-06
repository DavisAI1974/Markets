"""Is the BLIND improving group over group? Forward-curve drift is the scoreboard."""
import os, json, glob, re

R = "/home/user/Markets/research/kalshi"
FC, RD = f"{R}/forecasts", f"{R}/renders/ng_refine_s95"

def gnum(p):
    m = re.search(r"grp(\d+)\.json$", p)
    return int(m.group(1)) if m else None

rows = []
for p in sorted(glob.glob(f"{FC}/grp*.json"), key=lambda x: (gnum(x) or 0)):
    n = gnum(p)
    if n is None:
        continue
    ap = f"{RD}/g{n}_actual.json"
    if not os.path.exists(ap):
        continue
    try:
        blind = json.load(open(p)); act = json.load(open(ap))
    except Exception:
        continue
    amap = {d["date"]: d for d in act.get("days", [])}
    pairs = []
    for d in blind.get("days", []):
        dt = str(d.get("date", "")).replace("-", "")
        g = d.get("guess_day_move_usd", d.get("day_move_usd"))
        a = amap.get(dt, {}).get("day_move_usd")
        if isinstance(g, (int, float)) and isinstance(a, (int, float)):
            pairs.append((dt, g, a))
    if not pairs:
        continue
    errs = [abs(g - a) for _, g, a in pairs]
    hits = sum(1 for _, g, a in pairs if (g > 0) == (a > 0))
    bc, ac = sum(g for _, g, _ in pairs), sum(a for _, _, a in pairs)
    rows.append(dict(g=n, n=len(pairs), mae=round(sum(errs) / len(errs)), hits=hits,
                     bcum=bc, acum=ac, drift=bc - ac,
                     anchor=act.get("anchor")))

REGIME = {  # which blind architecture actually produced it
    **{k: "pre-S105 (old 3-angle / contradicted stack)" for k in range(1, 19)},
    19: "S106 one-agent (re-run)", 20: "S106 one-agent",
}

print(f"{'grp':>4} {'n':>3} {'dir':>6} {'mean|err|':>10} {'blind cum':>10} {'actual cum':>11} "
      f"{'DRIFT':>8} {'drift c/MMBtu':>14}  regime")
for r in rows:
    cents = r["drift"] / 10000.0
    print(f"{r['g']:>4} {r['n']:>3} {r['hits']:>3}/{r['n']:<2} {r['mae']:>10} "
          f"{r['bcum']:>+10} {r['acum']:>+11} {r['drift']:>+8} {cents:>13.3f}  "
          f"{REGIME.get(r['g'], '?')}")

mod = [r for r in rows if r["g"] >= 19]
print()
if len(mod) >= 2:
    print("Under the CURRENT one-agent blind regime only:")
    for r in mod:
        print(f"  g{r['g']}: mean|err| {r['mae']}, dir {r['hits']}/{r['n']}, "
              f"forward-curve drift {r['drift']:+} ({r['drift']/10000.0:+.3f}/MMBtu)")
