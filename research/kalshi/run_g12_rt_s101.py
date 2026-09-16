"""run_g12_rt_s101.py - build the G12 ACTUALS (rt.json) + continuous render on the walked NG.n.0 basis.

BASIS (recorded, load-bearing): G12 runs on the OI-continuous NG.n.0 tape (data/nymex_cont_n0,
the G11 basis). continuous_rt.py's loader reads the v0 S3 store, so this script mirrors its build
on the local n0 files instead (the run_g11_fingerprints_s98 precedent for basis-specific handling).

ROLL: detected from the per-record instrument_id at the UTC file boundary (1021 -> 996 at
20260213 per the S101 roll-check subagent); offset measured as new-instrument first trade minus
old-instrument last trade across the seam. RT prices stay REAL; the scorer roll-adjusts.

Output: renders/ng_refine_s95/g12_rt.json (continuous_score.py schema) + g12_blind.png
(intraday continuous actual vs the blind guess line, the g11_blind style).
"""
import gzip, json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
N0_DIR = os.path.join(REPO, "data", "nymex_cont_n0")
OUT = os.path.join(HERE, "renders", "ng_refine_s95")
MULT = 10000.0
ET = "America/New_York"
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

ANCHOR = "20260130"
DAYS = ["20260201", "20260202", "20260203", "20260204", "20260205", "20260206",
        "20260208", "20260209", "20260210", "20260211", "20260212", "20260213"]


def load_day(day):
    """(ts_sec, px, iid_first, iid_last) trade prints of the UTC-day file, ts-sorted."""
    p = os.path.join(N0_DIR, f"NG_{day}.jsonl.gz")
    ts, px, iids = [], [], []
    with gzip.open(p, "rt") as fh:
        for line in fh:
            if '"action": "T"' not in line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("action") not in ("T", "Trade", "t"):
                continue
            pr, t = r.get("price"), r.get("ts")
            if pr is None or t is None:
                continue
            ts.append(float(t)); px.append(float(pr)); iids.append(r.get("instrument_id"))
    order = np.argsort(np.asarray(ts), kind="stable")
    ts = np.asarray(ts, float)[order]; px = np.asarray(px, float)[order]
    iids = [iids[i] for i in order]
    if ts.size and ts[0] > 1e15:      # ns -> s
        ts = ts / 1e9
    return ts, px, (iids[0] if iids else None), (iids[-1] if iids else None)


def main():
    os.makedirs(OUT, exist_ok=True)
    a_ts, a_px, a_iid, _ = load_day(ANCHOR)
    a_et = pd.to_datetime(a_ts, unit="s", utc=True).tz_convert(ET)
    anchor_close = float(a_px[-1])
    last_hr = a_px[a_et >= a_et[-1] - pd.Timedelta(hours=1)]
    a_dir = "up" if len(last_hr) > 1 and last_hr[-1] > last_hr[0] else "down"

    guess = json.load(open(os.path.join(HERE, "forecasts", "grp12.json")))
    gd_by_date = {g["date"].replace("-", ""): g for g in guess["days"]}

    rolls, recs = [], []
    prev_close, prev_iid = anchor_close, a_iid
    cont_t, cont_p = [], []
    grun, gx, gy = 0.0, [], []
    cum_roll = 0.0
    for d in DAYS:
        ts, px, iid_first, iid_last = load_day(d)
        if px.size == 0:
            continue
        et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
        o, c = float(px[0]), float(px[-1])
        if iid_first != prev_iid:
            off = round(o - prev_close, 3)   # seam measure: new first trade minus old last trade
            rolls.append({"date": d, "offset": off,
                          "note": f"instrument {prev_iid} -> {iid_first}; seam-measured, includes ~minutes of real overnight"})
            cum_roll += off
        gap = round((o - prev_close) * MULT)
        net = round((c - o) * MULT)
        grid = list(range(20, 24, 2)) + list(range(0, 21, 2))
        curve = []
        for k, h in enumerate(grid):
            step_time = et[0] + pd.Timedelta(hours=2 * k)
            m = et <= step_time
            cum = round((float(px[m][-1]) - o) * MULT) if m.any() else 0
            curve.append([h, cum])
        recs.append({"date": d, "dow": _DOW[pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}").weekday()],
                     "group": 12, "open": round(o, 3), "close": round(c, 3),
                     "net_usd": net, "overnight_gap_usd": gap,
                     "cum_from_anchor_close_usd": round((c - anchor_close) * MULT),
                     "curve_2h": curve})
        idxds = np.linspace(0, len(px) - 1, min(len(px), 400)).astype(int)
        cont_t.extend(ts[idxds].tolist()); cont_p.extend(px[idxds].tolist())
        if d in gd_by_date:
            gd = gd_by_date[d]
            gopen = grun + gd.get("overnight_gap_usd", 0)
            gc = gd.get("guess_curve", [[20, 0]])
            for k, (hr, cumg) in enumerate(gc):
                gt = ts[0] + (ts[-1] - ts[0]) * (k / max(len(gc) - 1, 1))
                gx.append(gt); gy.append(anchor_close + (gopen + cumg) / MULT + cum_roll)
            grun = gopen + gd.get("guessed_net_usd", gc[-1][1])
        prev_close, prev_iid = c, iid_last

    out = {"market": "NG", "tag": "g12",
           "price_basis": "NG.n.0 OI-continuous (local data/nymex_cont_n0)",
           "anchor": {"date": ANCHOR, "price": round(anchor_close, 3), "last_hour_dir": a_dir},
           "seams": [], "n_days": len(recs), "rolls": rolls, "days": recs}
    rt_path = os.path.join(OUT, "g12_rt.json")
    json.dump(out, open(rt_path, "w"), indent=1)
    print(f"[g12_rt] wrote {rt_path}: {len(recs)} days, rolls={rolls}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(16, 5.5))
    adt = pd.to_datetime(np.asarray(cont_t), unit="s", utc=True).tz_convert(ET)
    ax.plot(adt, cont_p, color="#1f6feb", lw=0.9, label="actual (NG.n.0, REAL incl. roll)")
    if gx:
        gdt = pd.to_datetime(np.asarray(gx), unit="s", utc=True).tz_convert(ET)
        ax.plot(gdt, gy, color="#e8710a", lw=1.5, ls="--", label="blind guess (followed, roll-shifted)")
    for r in rolls:
        rd = pd.Timestamp(f"{r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]}", tz=ET)
        ax.axvline(rd, color="#999", lw=0.8, ls=":")
        ax.text(rd, ax.get_ylim()[0], f" roll {r['offset']:+.3f}", fontsize=7, color="#666", va="bottom")
    ax.axhline(anchor_close, color="#999", lw=0.6, ls=":")
    ax.set_title(f"NG G12 blind (one-shot, brain {guess.get('brain_version')}) vs actual - Sun 2026-02-01 .. Fri 2026-02-13  "
                 f"anchor {anchor_close:.3f} ({a_dir})  basis NG.n.0", fontsize=10, fontweight="bold")
    ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=7)
    plt.tight_layout()
    png = os.path.join(OUT, "g12_blind.png")
    plt.savefig(png, dpi=120, bbox_inches="tight")
    print(f"[g12_rt] wrote {png}")


if __name__ == "__main__":
    main()
