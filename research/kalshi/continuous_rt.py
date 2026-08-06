"""continuous_rt.py — the CONTINUOUS actual (RT) curve for the chronological walk (S95, Greg).

Builds ONE unbroken actual price/cum-$ path across a set of consecutive groups, anchored at the actual
hr24 (last hour) of the day BEFORE the first group day, days flowing hr24->hr1 (real overnight/weekend
gaps preserved). This is the refine substrate: the historic curve the agent's guess is scored against,
and the shape where the cross-block reversion is visible.

Emits (committed, persisted):
  renders/ng_refine_s95/<tag>_continuous.png    -> one unbroken actual line, block seams marked
  renders/ng_refine_s95/<tag>_rt.json           -> numeric substrate for the (text) refine agent:
      anchor {date, price, last_hour_dir}
      days[]  per day: {date, dow, group, open, close, net_usd, overnight_gap_usd,
                        cum_from_anchor_close_usd, curve_2h:[[et_hr, cum_from_open_usd],...]}
      NO pooling / no averages -- every day stands alone.

Usage:  python continuous_rt.py --anchor 20250905 --start 20250908 --end 20251021 \
                --seams 20250925,20251008 --tag g3g4g5
"""
import argparse, json, os
import numpy as np, pandas as pd
import boto3
import fast_tape, event_move_baseline as emb, roll_adjust

MULT = 10000.0                      # $ = price_move * MULT  (NG 10,000 MMBtu), matches forecast_harness
OUT = os.path.join("renders", "ng_refine_s95")
ET = "America/New_York"
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _avail_days(start, end):
    s3 = boto3.client("s3")
    pfx = f"{emb.S3_PREFIX + '/' if emb.S3_PREFIX else ''}nymex_cont/"
    days = set()
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=emb.S3_BUCKET, Prefix=pfx + "NG_"):
        for o in pg.get("Contents", []):
            d = o["Key"].split("/")[-1].replace("NG_", "").split(".")[0].split("_")[0]
            if len(d) == 8 and start <= d <= end:
                days.add(d)
    return sorted(days)


def _group_of(d, seams):
    """seams = sorted list of group-start dates; group index by which seam window d falls in."""
    g = 0
    for s in seams:
        if d >= s:
            g += 1
    return g


def build(anchor, start, end, seams, tag, guess_path=None):
    os.makedirs(OUT, exist_ok=True)
    days = _avail_days(start, end)
    # ROLL BACK-ADJUSTMENT: back-adjust the whole window (anchor + days) so contract rolls don't inject
    # fake steps; intraday moves preserved, roll-boundary overnight gaps -> ~real-overnight only (S95).
    offs, rolls = roll_adjust.roll_offsets("NG", [anchor] + days)   # DETECT rolls; RT stays REAL, scorer adjusts

    # anchor day (REAL prices)
    a_ts, a_px = fast_tape.fast_load_day("NG", anchor)
    a_et = pd.to_datetime(a_ts, unit="s", utc=True).tz_convert(ET)
    anchor_close = float(a_px[-1])
    last_hr = a_px[a_et >= a_et[-1] - pd.Timedelta(hours=1)]
    a_dir = "up" if len(last_hr) > 1 and last_hr[-1] > last_hr[0] else "down"

    group_starts = sorted(seams)                          # e.g. [g4_start, g5_start]; g3 is before the first
    gd_by_date = {gg["date"]: gg for gg in json.load(open(guess_path))["days"]} if guess_path else {}
    grun = 0.0; gx, gy = [], []                            # roll-free guess running cum ($); plotted guess line
    recs, prev_close, cont_ts, cont_px = [], anchor_close, [], []
    for d in days:
        ts, px = fast_tape.fast_load_day("NG", d)
        if len(px) == 0:
            continue
        et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
        o, c = float(px[0]), float(px[-1])
        gap = round((o - prev_close) * MULT)              # overnight/weekend gap from prior day's close
        net = round((c - o) * MULT)                        # day's net move
        # 2-hourly cum-from-open curve on the ET grid 20,22,0,2,...,18,20
        curve = []
        grid = list(range(20, 24, 2)) + list(range(0, 21, 2))
        hours = et.hour.values + et.minute.values / 60.0
        # map each grid mark to the last trade at/just before that ET hour within this session
        for k, h in enumerate(grid):
            # cumulative at the last trade whose ET <= the running 2h step from session start
            step_time = et[0] + pd.Timedelta(hours=2 * k)
            m = et <= step_time
            cum = round((float(px[m][-1]) - o) * MULT) if m.any() else 0
            curve.append([h, cum])
        recs.append({"date": d, "dow": _DOW[pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}").weekday()],
                     "group": 3 + _group_of(d, group_starts),
                     "open": round(o, 3), "close": round(c, 3), "net_usd": net,
                     "overnight_gap_usd": gap,
                     "cum_from_anchor_close_usd": round((c - anchor_close) * MULT),
                     "curve_2h": curve})
        # continuous overlay series (downsample to ~2min for the png)
        idxds = np.linspace(0, len(px) - 1, min(len(px), 400)).astype(int)
        cont_ts.extend(ts[idxds].tolist()); cont_px.extend(px[idxds].tolist())
        # forecast line: place the guess 2h curve on this day's real ET span, roll-shifted to the REAL scale
        if d in gd_by_date:
            gd = gd_by_date[d]
            gopen = grun + gd.get("overnight_gap_usd", 0)
            rp = offs.get(d, 0.0)                          # roll offset -> real price scale
            gc = gd.get("guess_curve", [[20, 0]])
            for k, (hr, cum) in enumerate(gc):
                gt = ts[0] + (ts[-1] - ts[0]) * (k / max(len(gc) - 1, 1))
                gx.append(gt); gy.append(anchor_close + (gopen + cum) / MULT + rp)
            grun = gopen + gd.get("guessed_net_usd", gc[-1][1])
        prev_close = c

    out = {"market": "NG", "tag": tag,
           "anchor": {"date": anchor, "price": round(anchor_close, 3), "last_hour_dir": a_dir},
           "seams": seams, "n_days": len(recs), "rolls": rolls, "roll_adjusted": False,
           "note": "continuous actual (RT) = REAL traded prices (NOT roll-adjusted; Greg: RT line = real "
                   "values). Contract rolls are listed in 'rolls'; the scorer/forecast side adjusts for them, "
                   "not the RT line. cum_from_anchor is real. PER-EVENT, no averages.",
           "days": recs}
    jpath = os.path.join(OUT, f"{tag}_rt.json")
    json.dump(out, open(jpath, "w"), indent=1)

    # render — REAL traded prices; break the line across weekend/overnight gaps (no diagonal bridges); mark rolls
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.dates as mdates
    cts = np.array(cont_ts, float); cpx = np.array(cont_px, float)
    ts_plot, px_plot = [], []
    for i in range(len(cts)):
        ts_plot.append(cts[i]); px_plot.append(cpx[i])
        if i < len(cts) - 1 and cts[i + 1] - cts[i] > 3 * 3600:   # >3h gap = closed market -> break the line
            ts_plot.append(cts[i] + 1.0); px_plot.append(np.nan)
    cont_et = pd.to_datetime(np.array(ts_plot), unit="s", utc=True).tz_convert(ET)
    px_plot = np.array(px_plot, float)
    fig, ax = plt.subplots(figsize=(18, 5))
    ax.plot(cont_et, px_plot, color="#1f6feb", lw=0.8, label="actual (real RT)")
    ax.axhline(anchor_close, color="#999", lw=0.6, ls=":")
    if gx:                                                       # forecast line over the real RT (roll-shifted)
        gxa = np.array(gx, float); gya = np.array(gy, float)
        gts, gps = [], []
        for i in range(len(gxa)):                                # break across overnight/weekend gaps too
            gts.append(gxa[i]); gps.append(gya[i])
            if i < len(gxa) - 1 and gxa[i + 1] - gxa[i] > 3 * 3600:
                gts.append(gxa[i] + 1.0); gps.append(np.nan)
        gx_et = pd.to_datetime(np.array(gts, float), unit="s", utc=True).tz_convert(ET)
        ax.plot(gx_et, gps, color="#e8710a", lw=1.8, ls="--", label="forecast (guess)")
        ax.legend(fontsize=8, loc="lower right")
    ymax = float(np.nanmax(px_plot))
    for s in seams:                                              # group boundaries (multi-group only)
        st = pd.Timestamp(f"{s[:4]}-{s[4:6]}-{s[6:]}", tz=ET)
        ax.axvline(st, color="#e8710a", lw=1.0, ls="--")
        ax.text(st, ymax, f" G{4 + seams.index(s)}", color="#e8710a", fontsize=9, va="top")
    if seams:
        ax.text(cont_et[0], ymax, " G3", color="#e8710a", fontsize=9, va="top")
    for r in rolls:                                              # contract rolls = real-value jumps, marked
        rd = pd.Timestamp(f"{r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]}", tz=ET)
        ax.axvline(rd, color="#c0392b", lw=1.0, ls="-.")
        ax.text(rd, ymax, f" roll {r['from_iid']}->{r['to_iid']} ({r['offset']:+.2f})",
                color="#c0392b", fontsize=7, va="top")
    ax.set_title(f"NG continuous ACTUAL (RT, real prices) {tag}: {recs[0]['date']}..{recs[-1]['date']}  "
                 f"anchor {anchor} {anchor_close:.3f} ({a_dir})  [rolls marked, NOT adjusted]",
                 fontsize=11, fontweight="bold")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d", tz=ET))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2)); ax.tick_params(labelsize=7)
    ax.grid(True, color="#eee", lw=0.6); ax.set_axisbelow(True)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    ppath = os.path.join(OUT, f"{tag}_continuous.png")
    plt.tight_layout(); plt.savefig(ppath, dpi=120, bbox_inches="tight")
    print(f"[continuous_rt] {len(recs)} days -> {jpath} + {ppath}")
    print(f"  anchor {anchor} close={anchor_close:.3f} ({a_dir}); "
          f"block net: {recs[0]['open']:.3f} -> {recs[-1]['close']:.3f}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", required=True); ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True); ap.add_argument("--seams", default="")
    ap.add_argument("--tag", default="rt"); ap.add_argument("--guess", default=None)
    a = ap.parse_args()
    seams = [s for s in a.seams.split(",") if s]
    build(a.anchor, a.start, a.end, seams, a.tag, guess_path=a.guess)
