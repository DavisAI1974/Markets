"""
forecast_harness.py — turn-key helpers for the self-growing forecaster LOOP (S92 build).

Makes the loop one-command per step so S93 just runs it. NO agent reasoning here — this is the deterministic
scaffolding the agent uses: compute the decision-time state for a group, render guess-vs-actual overlays, and
load/merge the brain. The BLIND FORECAST itself (applying judgment from the brain) is the agent's job; this
harness holds the state it forecasts from and the render it's scored by.

Commands:
  decision-state --days D1,D2,...            -> print + write the decision-time state JSON for a group (blind-safe:
                                                weekday + storage surprise + curve regime ONLY; no tape/leg data)
  overlay --forecasts F.json --out P.png     -> render guess (dashed) vs actual (solid) per day, 1 panel/day, ET
  brain-show                                 -> summarize the current ng_brain.json (plays + status)
  --selftest
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MULT = 10000.0   # $/MMBtu move = cum_move_usd / MULT (NG contract 10,000 MMBtu)


def decision_state(days: list[str]) -> dict:
    """Blind-safe decision-time state for each day: weekday + that week's EIA storage surprise + curve regime.
    NO tape, NO legs, NO outcome — exactly what a forecaster knows at the open."""
    import forward_curve as fc
    surp = json.load(open(os.path.join(HERE, "..", "..", "data", "eia_surprise.json"))).get("KXNATGASD", {}) \
        if os.path.exists(os.path.join(HERE, "..", "..", "data", "eia_surprise.json")) else \
        (json.load(open("data/eia_surprise.json")).get("KXNATGASD", {}) if os.path.exists("data/eia_surprise.json") else {})
    cv = fc.load("NG")
    out = {}
    for d in days:
        iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        dow = DOW[datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday()]
        past = sorted(ri for ri in surp if ri <= iso)
        sv = surp[past[-1]]["surprise"] if past else None
        cr = fc.curve_asof(cv, iso)
        out[d] = {"dow": dow, "stor_surprise": round(sv, 1) if sv is not None else None,
                  "stor_surprise_sign": ("above" if sv > 0 else "below") if sv is not None else None,
                  "curve_regime": cr[1]["regime"] if cr else "unknown"}
    return out


def render_overlay(forecasts: dict, out_png: str, source: str = "s3") -> str:
    """Guess (dashed) vs actual (solid), one panel per day, price y / time x (ET). Anchors each guessed
    cumulative-move curve at the day's real OPEN. forecasts = {day: {dow, archetype, curve:[[et_hr, cum_usd],..]}}."""
    import numpy as np, pandas as pd
    import event_move_baseline as emb
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt, matplotlib.dates as mdates
    days = list(forecasts.keys())
    ncol = 3; nrow = (len(days) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(17, 4 * nrow)); axes = np.array(axes).reshape(-1)
    for i, day in enumerate(days):
        ax = axes[i]
        try:
            d = emb.load_cont_day("NG", day, source=source, trades_only=True)
            ts = np.asarray(d["ts"], float); px = np.asarray(d["price"], float)
            idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York")
            ax.plot(idx, px, color="#1f6feb", lw=0.7, label="actual")
            o = float(px[0]); t0 = idx[0]; cur = forecasts[day]["curve"]
            gx = [t0 + pd.Timedelta(hours=2 * k) for k in range(len(cur))]
            gy = [o + float(c) / MULT for _, c in cur]
            ax.plot(gx, gy, color="#e8710a", lw=2.0, ls="--", label="guess")
            ax.set_title(f"{forecasts[day].get('dow','')} {day[4:6]}-{day[6:]}  {o:.3f}->{px[-1]:.3f}  "
                         f"[{forecasts[day].get('archetype','')}]", fontsize=9)
            ax.yaxis.tick_right(); ax.tick_params(labelsize=7)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H", tz=idx.tz)); ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
            ax.grid(True, color="#eee", lw=0.6); ax.set_axisbelow(True)
            for sp in ("top", "left"): ax.spines[sp].set_visible(False)
            if i == 0: ax.legend(fontsize=7)
        except Exception as e:
            ax.text(0.5, 0.5, f"{day}\n{str(e)[:60]}", ha="center", va="center", transform=ax.transAxes, fontsize=8)
    for j in range(len(days), len(axes)): axes[j].axis("off")
    fig.suptitle("NG BLIND forecast (dashed) vs ACTUAL (solid) — each day independent, no pooling",
                 fontsize=12, fontweight="bold", y=0.998)
    plt.tight_layout(rect=[0, 0, 1, 0.985]); plt.savefig(out_png, dpi=115, bbox_inches="tight")
    return out_png


def brain_show(path: str = BRAIN) -> None:
    b = json.load(open(path))
    print(f"ng_brain {b['meta']['version']} — {len(b['plays'])} plays:")
    for p in b["plays"]:
        print(f"  [{p['status']:<20}] {p['id']:<28} target={p['target']:<9} conf={p.get('confidence')}")
    print("open_frontier:")
    for o in b["open_frontier"]:
        print("  -", o)


def _selftest() -> int:
    ds = decision_state(["20250902"])
    assert ds["20250902"]["dow"] == "Tue" and ds["20250902"]["stor_surprise"] is not None, ds
    brain_show()
    print("[forecast_harness] selftest PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    a1 = sub.add_parser("decision-state"); a1.add_argument("--days", required=True); a1.add_argument("--out")
    a2 = sub.add_parser("overlay"); a2.add_argument("--forecasts", required=True); a2.add_argument("--out", required=True); a2.add_argument("--source", default="s3")
    sub.add_parser("brain-show")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if a.cmd == "decision-state":
        ds = decision_state(a.days.split(","))
        print(json.dumps(ds, indent=1))
        if a.out: json.dump(ds, open(a.out, "w"))
        return 0
    if a.cmd == "overlay":
        p = render_overlay(json.load(open(a.forecasts)), a.out, source=a.source)
        print("wrote", p); return 0
    if a.cmd == "brain-show":
        brain_show(); return 0
    ap.print_help(); return 1


if __name__ == "__main__":
    sys.exit(main())
