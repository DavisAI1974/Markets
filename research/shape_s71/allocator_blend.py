"""S77: shared-$5k allocator blend — the HONEST bank $/hr (not the per-cell sum, which fantasises full $5k
in every cell at once). Deploy ONE $5k across all cells greedily by $/hr rate, each capped at its realistic
fill capacity (avg_depl$ from fill_occupancy). Reports bank $/hr + the % of the $5k that lands in small caps.

Inputs: r2_<coin>.txt (per-cell both-maker / maker+taker $/hr x0.9) + fillocc.txt (small-cap avg_depl$).
Majors: no rebate, low both-maker $/hr; given a generous capacity so they compete only on rate (they lose).

    python3 allocator_blend.py
"""
import re

CAP = 5000.0
MAJORS = {"btc", "eth", "sol", "xrp", "doge"}
ALL = "btc eth sol xrp doge aave ada avax bch bnb hype link ltc near sui tao ton xlm xmr xpl zec".split()


def load_dph(coin):
    try:
        t = open(f"/tmp/kbook/r2_{coin}.txt").read()
    except FileNotFoundError:
        return None
    bm = re.search(r"both-maker\s+-?\d+\s+\d+\s+[\d.]+\s+[\d.]+\s+[\-\d.]+\s+[\-\d.]+\s+([\-\d.]+)", t)
    mt = re.search(r"maker\+taker\s+-?\d+\s+\d+\s+[\d.]+\s+[\d.]+\s+[\-\d.]+\s+[\-\d.]+\s+([\-\d.]+)", t)
    if not bm:
        return None
    return float(bm.group(1)), (float(mt.group(1)) if mt else float("nan"))


def load_cap():
    """avg_depl$ per small cap from fillocc.txt; majors get a large cap (they lose on rate anyway)."""
    cap = {}
    for ln in open("/tmp/kbook/fillocc.txt"):
        m = re.match(r"\s*([A-Z]+)\s+[\d.]+\s+[\d,]+\s+[\d,]+\s+([\d,]+)\s+\d+", ln)
        if m:
            cap[m.group(1).lower()] = float(m.group(2).replace(",", ""))
    for c in MAJORS:
        cap.setdefault(c, CAP)   # majors: ample capacity, compete on rate only
    return cap


def blend(scenario_idx):
    cap = load_cap()
    cells = []
    for c in ALL:
        d = load_dph(c)
        if d is None:
            continue
        dph = d[scenario_idx]
        cells.append((c, dph, cap.get(c, CAP)))
    cells.sort(key=lambda x: -x[1])          # greedy by $/hr rate (highest first)
    remaining = CAP; bank = 0.0; small_cap = 0.0; funded = []
    for c, dph, cp in cells:
        if remaining <= 0:
            break
        take = min(cp, remaining)
        earn = take / CAP * dph              # dph was computed at full $5k -> scale by deployed fraction
        bank += earn; remaining -= take
        if c not in MAJORS:
            small_cap += take
        funded.append((c, take, dph, earn))
    return bank, small_cap, funded


print("=== SHARED-$5k ALLOCATOR BLEND (per-cell horizon + rebate, x0.90 fill) ===\n")
for idx, name in ((0, "BOTH-MAKER  (exit rests as maker/rebate — the CEILING)"),
                  (1, "MAKER+TAKER (exit crosses — the FLOOR)")):
    bank, small_cap, funded = blend(idx)
    print(f"[{name}]")
    print(f"  bank $/hr on $5k = {bank:+.1f}   ({bank/CAP*100:+.2f}%/hr)   | small caps = ${small_cap:,.0f} of $5k ({small_cap/CAP*100:.0f}%)")
    print(f"  {'cell':>6}{'deployed$':>11}{'cell$/hr@5k':>12}{'earns$/hr':>11}")
    for c, take, dph, earn in funded:
        print(f"  {c.upper():>6}{take:>11,.0f}{dph:>12.1f}{earn:>11.2f}")
    print()
