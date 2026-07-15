"""extract_guesses.py — the per-day guess-vs-actual scorecard for G3/4/5 survived in the brain's
magnitude.warm_season_scale_candidate evidence ('0908 +$1260 vs -$450' = MMDD ACTUAL vs GUESS). Extract it
to a clean {date: {actual_usd, guess_usd}} json so the refine agent has a rigorous guess reference to lay
against the continuous RT curve. (The full guess CURVES were lost to scratchpad; these dominant-move
scalars + direction are the faithful surviving record.) S95."""
import json, re, os

BRAIN = "knowledge/ng_brain.json"
OUT = os.path.join("renders", "ng_refine_s95", "guesses.json")
_RE = re.compile(r"(\d{4})\s+([+-]?)\$([\d,]+)\s+vs\s+([+-]?)\$([\d,]+)")


def _num(sign, digits):
    return (-1 if sign == "-" else 1) * int(digits.replace(",", ""))


if __name__ == "__main__":
    b = json.load(open(BRAIN))
    ev = next(p for p in b["plays"] if p["id"] == "magnitude.warm_season_scale_candidate")["evidence"]
    out = {}
    for key in ("under_forecast_days_g3", "under_forecast_days_g4", "under_forecast_days_g5"):
        grp = {"g3": 3, "g4": 4, "g5": 5}[key[-2:]]
        for mmdd, sa, da, sg, dg in _RE.findall(ev.get(key, "")):
            out[f"2025{mmdd}"] = {"group": grp, "actual_usd": _num(sa, da), "guess_usd": _num(sg, dg)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"note": "per-day dominant-move scorecard (ACTUAL vs GUESS $), from brain evidence. "
                       "Full guess curves were lost; these scalars + sign are the surviving guess reference. "
                       "PER-EVENT, no averages.", "days": out}, open(OUT, "w"), indent=1)
    print(f"[extract_guesses] {len(out)} days -> {OUT}")
    for d, v in sorted(out.items()):
        print(f"  {d} g{v['group']}: actual {v['actual_usd']:+d} vs guess {v['guess_usd']:+d}"
              f"  {'MISS-SIDE' if (v['actual_usd']>0)!=(v['guess_usd']>0) else 'side-ok'}")
