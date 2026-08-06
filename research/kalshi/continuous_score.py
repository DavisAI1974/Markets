"""continuous_score.py — score a blind forecast (grpN.json) against the continuous actual (gN_rt.json),
per-event, and render the honest "if you followed it" overlay: the guess assembled as ONE flowing curve
from the block anchor (each day's open = prior day's GUESSED close + guessed gap), diverging from the
actual as it errs. S95 (Greg: the continuous-curve representation).

  python continuous_score.py --guess forecasts/grp6.json --actual renders/ng_refine_s95/g6_rt.json --tag g6

Writes renders/ng_refine_s95/<tag>_score.json (per-day, PER-EVENT, no averages) + <tag>_overlay.png.
"""
import argparse, json, os
import numpy as np, pandas as pd
MULT = 10000.0
OUT = os.path.join("renders", "ng_refine_s95")


def score(guess_path, actual_path, tag):
    g = json.load(open(guess_path)); a = json.load(open(actual_path))
    anchor = a["anchor"]["price"]
    actual_by_date = {d["date"]: d for d in a["days"]}
    rolls = a.get("rolls", [])                           # RT is REAL (has roll jumps); shift guess to follow it
    def _cum_roll(date):                                 # $ roll offset up to & incl. this date -> guess-to-real
        return sum(r["offset"] for r in rolls if r["date"] <= date) * MULT
    rows, running_guess = [], 0.0                       # running_guess = ROLL-FREE guessed close cum ($)
    for gd in g["days"]:
        date = gd["date"]
        ad = actual_by_date.get(date)
        g_gap = gd.get("overnight_gap_usd", 0)
        g_net = gd.get("guessed_net_usd", gd.get("guess_curve", [[0,0]])[-1][1])
        g_open_cum = running_guess + g_gap
        g_close_cum = g_open_cum + g_net
        running_guess = g_close_cum                      # keep the guess roll-free internally
        roll = _cum_roll(date)                            # add to put the guess on the REAL RT scale
        if ad is None:
            rows.append({"date": date, "dow": gd.get("dow"), "note": "no actual", "guess_net_usd": g_net})
            continue
        a_gap, a_net = ad["overnight_gap_usd"], ad["net_usd"]
        a_close_cum = ad["cum_from_anchor_close_usd"]
        rows.append({
            "date": date, "dow": gd.get("dow"), "archetype": gd.get("archetype"),
            "guess_gap_usd": g_gap, "actual_gap_usd": a_gap,
            "guess_net_usd": g_net, "actual_net_usd": a_net,
            "net_dir_ok": bool((g_net > 0) == (a_net > 0)) if g_net and a_net else None,
            "gap_dir_ok": bool((g_gap > 0) == (a_gap > 0)) if g_gap and a_gap else None,
            "guess_day_move_usd": g_gap + g_net, "actual_day_move_usd": a_gap + a_net,
            "guess_close_cum": round(g_close_cum),                         # roll-free (forecast)
            "actual_close_cum": a_close_cum,                                # REAL (has roll)
            "actual_close_cum_adj": round(a_close_cum - roll),             # roll-adjusted for skill comparison
            "drift_usd": round(g_close_cum - (a_close_cum - roll)),         # skill gap, roll removed from both
        })
    out = {"tag": tag, "anchor": a["anchor"], "brain_version": g.get("brain_version"),
           "note": "PER-EVENT scorecard. drift_usd = continuous guessed-close cum minus actual cum (the "
                   "'if you followed it' gap). NO averages/pooled rates - each day is its own descriptor.",
           "days": rows}
    json.dump(out, open(os.path.join(OUT, f"{tag}_score.json"), "w"), indent=1)

    # overlay: continuous actual (solid) vs continuous guess (dashed), daily close-cum as price
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    dts = [pd.Timestamp(f"{r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]}") for r in rows if "actual_close_cum_adj" in r]
    a_price = [anchor + r["actual_close_cum_adj"] / MULT for r in rows if "actual_close_cum_adj" in r]   # roll-adjusted
    g_price = [anchor + r["guess_close_cum"] / MULT for r in rows if "actual_close_cum_adj" in r]
    a_dt0 = pd.Timestamp(f"{anchor and a['anchor']['date'][:4]}-{a['anchor']['date'][4:6]}-{a['anchor']['date'][6:]}")
    fig, ax = plt.subplots(figsize=(15, 5))
    ax.plot([a_dt0] + dts, [anchor] + a_price, color="#1f6feb", lw=1.6, marker="o", ms=3, label="actual (roll-adj)")
    ax.plot([a_dt0] + dts, [anchor] + g_price, color="#e8710a", lw=1.8, ls="--", marker="s", ms=3, label="blind guess (followed)")
    ax.axhline(anchor, color="#999", lw=0.6, ls=":")
    nroll = len(a.get("rolls", []))
    ax.set_title(f"NG {tag} blind guess vs actual — SKILL VIEW (roll-adjusted{', '+str(nroll)+' roll' if nroll else ''}) "
                 f"from anchor {a['anchor']['date']} {anchor:.3f} ({a['anchor']['last_hour_dir']})  brain {g.get('brain_version')}",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=7)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, f"{tag}_overlay.png"), dpi=120, bbox_inches="tight")

    # console verdict (per-event, no averages)
    print(f"[continuous_score] {tag}  brain {g.get('brain_version')}  anchor {a['anchor']['date']} {anchor:.3f} ({a['anchor']['last_hour_dir']})")
    print(f"  {'date':9s} {'dow':4s} {'g_net':>7s} {'a_net':>7s} dir  {'g_move':>7s} {'a_move':>7s}  {'drift':>7s}")
    for r in rows:
        if "actual_net_usd" not in r: continue
        dk = "OK " if r["net_dir_ok"] else "MISS"
        print(f"  {r['date']} {r['dow']:4s} {r['guess_net_usd']:+7d} {r['actual_net_usd']:+7d} {dk} "
              f"{r['guess_day_move_usd']:+7d} {r['actual_day_move_usd']:+7d}  {r['drift_usd']:+7d}")
    fin = [r for r in rows if "actual_close_cum" in r][-1]
    print(f"  block: guess close-cum {fin['guess_close_cum']:+d} vs actual {fin['actual_close_cum']:+d}  "
          f"(final drift {fin['drift_usd']:+d})  -> price guess {anchor+fin['guess_close_cum']/MULT:.3f} vs actual {anchor+fin['actual_close_cum']/MULT:.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--guess", required=True); ap.add_argument("--actual", required=True); ap.add_argument("--tag", default="g6")
    a = ap.parse_args()
    score(a.guess, a.actual, a.tag)
