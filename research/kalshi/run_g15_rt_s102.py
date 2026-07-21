"""run_g15_rt_s102.py - G15 ACTUALS + render on the KALSHI-UNDERLYING basis (Greg's rule).

S103: parametrized (backward-compatible; no args = the original blind render byte-for-byte).
  --guess FILE:label:color[,FILE:label:color]  overlay 1-2 guess lines (default forecasts/grp15.json)
  --out NAME.png    output filename (default g15_blind.png)
  --title TAG       title tag (default "BLIND"); the actual + rt.json are guess-independent.

BASIS: the Kalshi underlying. APRIL/NGJ26 (instrument 1008) through Thu 2026-03-19; MAY/NGK26
(instrument 996) from Fri 2026-03-20 (KXNATGASD underlying rolls 5 business days before the
Mar 27 LTD). The 0319->0320 seam is a REAL instrument change (April->May), MARKED NEVER TRADED:
overnight forecast ~0, seam offset MEASURED (new first trade minus old last trade) and the scorer
roll-adjusts. Per-day nets are roll-clean regardless.

FILE SELECTION (roll-check subagent S102 + box pull):
  0315: data/nymex_cont_n1 (April 1008, the only local 0315 April file)
  0316-0319: data/nymex_cont_ngj26 (box NGJ26 top-up - April fell to n.2 in n0/n1 after 0315)
  0320-0327: data/nymex_cont_n0 (May 996)
Instrument asserted per leg so a mis-file cannot splice the wrong contract.
"""
import argparse, gzip, json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "renders", "ng_refine_s95")
MULT = 10000.0
ET = "America/New_York"
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

ANCHOR = "20260313"                       # Fri, April 1008, from n1 store
ANCHOR_DIR = os.path.join(REPO, "data", "nymex_cont_n1")
APRIL, MAY = 1008, 996
# (day, dir, expected_instrument)
LEGS = [("20260315", os.path.join(REPO, "data", "nymex_cont_n1"), APRIL)]
for d in ["20260316", "20260317", "20260318", "20260319"]:
    LEGS.append((d, os.path.join(REPO, "data", "nymex_cont_ngj26"), APRIL))
for d in ["20260320", "20260322", "20260323", "20260324", "20260325", "20260326", "20260327"]:
    LEGS.append((d, os.path.join(REPO, "data", "nymex_cont_n0"), MAY))
SEAM_DAY = "20260320"                      # April->May, marked never traded


def load(path, day, want_iid):
    p = os.path.join(path, f"NG_{day}.jsonl.gz")
    ts, px, iids = [], [], []
    with gzip.open(p, "rt") as fh:
        for line in fh:
            if '"action": "T"' not in line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("action") != "T" or r.get("price") is None:
                continue
            ts.append(float(r["ts"])); px.append(float(r["price"])); iids.append(r.get("instrument_id"))
    o = np.argsort(ts, kind="stable")
    ts = np.asarray(ts, float)[o]; px = np.asarray(px, float)[o]
    iids = [iids[i] for i in o]
    if ts.size and ts[0] > 1e15:
        ts = ts / 1e9
    bad = {i for i in iids if i != want_iid}
    assert not bad, f"{day}: expected {want_iid}, saw {bad} in {p}"
    return ts, px


def _guess_line(gpath, day_spans, anchor_close):
    """Replay a guess file into a plotted (gx, gy) line on the real per-day ET spans."""
    gd_by = {g["date"].replace("-", ""): g for g in json.load(open(gpath))["days"]}
    gx, gy, grun = [], [], 0.0
    for d, (ts0, ts1) in day_spans:
        if d not in gd_by:
            continue
        gg = gd_by[d]
        gopen = grun + gg.get("overnight_gap_usd", 0)
        gc = gg.get("guess_curve", [[20, 0]])
        for k, (hr, cg) in enumerate(gc):
            gt = ts0 + (ts1 - ts0) * (k / max(len(gc) - 1, 1))
            gx.append(gt); gy.append(anchor_close + (gopen + cg) / MULT)
        grun = gopen + gg.get("guessed_net_usd", gc[-1][1])
    return gx, gy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guess", default="forecasts/grp15.json:blind guess (followed):#e8710a",
                    help="comma-sep FILE:label:color list (1-2 guesses)")
    ap.add_argument("--out", default="g15_blind.png")
    ap.add_argument("--title", default="BLIND")
    a = ap.parse_args()
    guesses = []
    for spec in a.guess.split(","):
        parts = spec.split(":")
        path = parts[0] if os.path.isabs(parts[0]) else os.path.join(HERE, parts[0])
        label = parts[1] if len(parts) > 1 else "guess"
        color = parts[2] if len(parts) > 2 else "#e8710a"
        guesses.append((path, label, color))

    os.makedirs(OUT, exist_ok=True)
    a_ts, a_px = load(ANCHOR_DIR, ANCHOR, APRIL)
    a_et = pd.to_datetime(a_ts, unit="s", utc=True).tz_convert(ET)
    anchor_close = float(a_px[-1])
    last_hr = a_px[a_et >= a_et[-1] - pd.Timedelta(hours=1)]
    a_dir = "up" if len(last_hr) > 1 and last_hr[-1] > last_hr[0] else "down"

    rolls, recs, cont_t, cont_p, day_spans = [], [], [], [], []
    cum_roll = 0.0
    prev_close = anchor_close
    for d, path, iid in LEGS:
        ts, px = load(path, d, iid)
        if px.size == 0:
            continue
        et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
        o, c = float(px[0]), float(px[-1])
        if d == SEAM_DAY:
            off = round(o - prev_close, 3)
            rolls.append({"date": d, "offset": off,
                          "note": f"April({APRIL})->May({MAY}) seam; marked never traded; scorer roll-adjusts"})
            cum_roll += off
        gap = round((o - prev_close) * MULT) if d != SEAM_DAY else 0
        net = round((c - o) * MULT)
        grid = list(range(20, 24, 2)) + list(range(0, 21, 2))
        curve = []
        for k, h in enumerate(grid):
            m = et <= et[0] + pd.Timedelta(hours=2 * k)
            curve.append([h, round((float(px[m][-1]) - o) * MULT) if m.any() else 0])
        recs.append({"date": d, "dow": _DOW[pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}").weekday()],
                     "group": 15, "instrument": iid, "open": round(o, 3), "close": round(c, 3),
                     "net_usd": net, "overnight_gap_usd": gap,
                     "cum_from_anchor_close_usd": round((c - anchor_close - cum_roll) * MULT),
                     "curve_2h": curve})
        idx = np.linspace(0, len(px) - 1, min(len(px), 400)).astype(int)
        cont_t.extend(ts[idx].tolist()); cont_p.extend((px[idx] - cum_roll).tolist())
        day_spans.append((d, (ts[0], ts[-1])))
        prev_close = c

    out = {"market": "NG", "tag": "g15",
           "price_basis": ("Kalshi underlying: April/NGJ26(1008) through 2026-03-19, May/NGK26(996) "
                           "from 2026-03-20 (5bd-before-LTD roll). 0319->0320 seam marked never traded, "
                           "scorer roll-adjusts. Greg S102 Kalshi-settlement-proximity rule."),
           "anchor": {"date": ANCHOR, "price": round(anchor_close, 3), "last_hour_dir": a_dir},
           "n_days": len(recs), "rolls": rolls, "days": recs}
    json.dump(out, open(os.path.join(OUT, "g15_rt.json"), "w"), indent=1)
    print(f"[g15_rt] {len(recs)} days, rolls={rolls}, anchor {anchor_close:.3f} ({a_dir})")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(16, 5.5))
    adt = pd.to_datetime(np.asarray(cont_t), unit="s", utc=True).tz_convert(ET)
    ax.plot(adt, cont_p, color="#1f6feb", lw=0.9, label="actual (Kalshi underlying, roll-adjusted)")
    for gpath, glabel, gcolor in guesses:
        gx, gy = _guess_line(gpath, day_spans, anchor_close)
        if gx:
            gdt = pd.to_datetime(np.asarray(gx), unit="s", utc=True).tz_convert(ET)
            ax.plot(gdt, gy, color=gcolor, lw=1.6, ls="--", label=glabel)
    for r in rolls:
        rd = pd.Timestamp(f"{r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]}", tz=ET)
        ax.axvline(rd, color="#999", lw=0.8, ls=":")
        ax.text(rd, ax.get_ylim()[0], f" seam {r['offset']:+.3f}", fontsize=7, color="#666", va="bottom")
    ax.axhline(anchor_close, color="#999", lw=0.6, ls=":")
    ax.set_title(f"NG G15 {a.title} vs actual - Sun 2026-03-15 .. Fri 2026-03-27  "
                 f"anchor {anchor_close:.3f} ({a_dir})  Kalshi underlying April->May 0320", fontsize=10, fontweight="bold")
    ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=7)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, a.out), dpi=120, bbox_inches="tight")
    print(f"[g15_rt] wrote {a.out}")


if __name__ == "__main__":
    main()
