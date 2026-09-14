"""What does the BLIND actually see? Audit the price-masked state G21 will be run on."""
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_REPO = _os.path.dirname(_os.path.dirname(_HERE))

import json, sys
sys.path.insert(0, "/home/user/Markets/research/kalshi")

RD = _os.path.join(_HERE, "renders", "ng_refine_s95")
GID = sys.argv[1] if len(sys.argv) > 1 else "grp21"
st = json.load(open(f"{RD}/{GID}_state.json"))
days = {k: v for k, v in st.items() if k.startswith("2026")}

def content(v):
    if v is None:
        return False
    if isinstance(v, dict):
        if v.get("masked_one_shot") is True:
            inner = {k: x for k, x in v.items() if k not in ("masked_one_shot", "vintage_asof")}
            if "value" in inner and len(inner) == 1:
                return inner["value"] is not None
            return any(content(x) for x in inner.values())
        return len(v) > 0 and any(content(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return len(v) > 0
    return True

def masked(v):
    return isinstance(v, dict) and v.get("masked_one_shot") is True

keys = sorted(set().union(*[set(d.keys()) for d in days.values()]))
print(f"{GID}: {len(days)} days, {len(keys)} blocks\n")
print(f"{'block':34} {'days w/ content':>16}  {'masked?':>8}")
print("-" * 64)
live = frozen = empty = 0
for k in keys:
    n = sum(content(days[d].get(k)) for d in days)
    m = sum(masked(days[d].get(k)) for d in days)
    tag = f"{m}/{len(days)}" if m else "-"
    flag = ""
    if n == 0:
        flag = "   <-- EMPTY"; empty += 1
    elif m:
        frozen += 1
    else:
        live += 1
    print(f"{k:34} {n:>10}/{len(days):<5} {tag:>8}{flag}")
print("-" * 64)
print(f"LIVE (unmasked, populated): {live}   FROZEN at anchor vintage: {frozen}   EMPTY: {empty}")

print("\n=== the kitchen sink, block by block (doctrine: only PRICE is masked) ===")
want = {
    "MBO order flow":  ["tape_conditions"],
    "volume":          ["tape_conditions"],
    "L1 book":         ["tape_conditions"],
    "weather":         ["weather", "weather_forecast", "weather_forecast_cycle"],
    "storage":         ["storage", "stor_surprise", "stor_surprise_sign"],
    "positioning/COT": ["cot", "cot_combined"],
    "structure":       ["contract_structure", "curve_regime", "squeeze_watch"],
    "calendar":        ["flow_calendar"],
    "options":         ["options_surface"],
    "vol/magnitude":   ["vol_regime"],
}
d0 = days[sorted(days)[len(days) // 2]]
for label, ks in want.items():
    bits = []
    for k in ks:
        if k not in d0:
            bits.append(f"{k}=ABSENT")
        else:
            n = sum(content(days[d].get(k)) for d in days)
            bits.append(f"{k}={'OK' if n == len(days) else f'{n}/{len(days)}'}"
                        + ("(frozen)" if masked(d0.get(k)) else ""))
    print(f"  {label:18} " + "  ".join(bits))

tc = d0.get("tape_conditions") or {}
print("\n=== tape_conditions fields actually served to the blind (mid-block day) ===")
for k in sorted(tc):
    v = tc[k]
    print(f"    {k:34} {str(v)[:60]}")
