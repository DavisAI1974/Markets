"""run_g14_rt_s102.py - build the G14 ACTUALS (rt.json) + continuous render on the DECIDED basis.

BASIS (Greg, S102, recorded verbatim): the CALENDAR-FRONT 1008/NGJ26 (April) continuation - "for
kalshi, the one that settles closest to its close": KXNATGASD settles on the front-month NGD close
and its underlying does not roll until 5bd before LTD, so through Mar 13 the Kalshi underlying IS
NGJ26. Confirmed by the S102 roll-check subagent: NGJ26 (expiry 2026-03-27, from the definitions
raw) is the calendar front the entire window, 2-3x May's trade count every session, NO roll
inside Mar 1-13.

FILE SELECTION (the subagent's load-bearing correction): both local stores are literal
continuation pulls and the OI ranks flipped between 0302 and 0303 (May OI overtook April
216,396 vs 216,338 at the 0302 settle). The 1008 series is therefore:
  n0 store: 20260227 (anchor), 20260301, 20260302
  n1 store: 20260303 .. 20260313 (and 20260315)
Every file is single-instrument; this script HARD-ASSERTS instrument_id == 1008 on every day so a
store mix-up cannot silently splice May onto the walk.

ROLL: none in-window (same instrument across every seam). The rolls list stays empty by
construction; any non-1008 id aborts.

Output: renders/ng_refine_s95/g14_rt.json (continuous_score.py schema) + g14_blind.png
(intraday continuous actual vs the blind guess line, the g13 style).
"""
import gzip, json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
N0_DIR = os.path.join(REPO, "data", "nymex_cont_n0")
N1_DIR = os.path.join(REPO, "data", "nymex_cont_n1")
OUT = os.path.join(HERE, "renders", "ng_refine_s95")
MULT = 10000.0
ET = "America/New_York"
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

WALK_INSTRUMENT = 1008                      # NGJ26 April - asserted on every file
ANCHOR = "20260227"
DAYS = ["20260301", "20260302", "20260303", "20260304", "20260305", "20260306",
        "20260308", "20260309", "20260310", "20260311", "20260312", "20260313"]
# store per day (subagent instrument table, verified):
STORE = {ANCHOR: N0_DIR, "20260301": N0_DIR, "20260302": N0_DIR}
for _d in DAYS[2:]:
    STORE[_d] = N1_DIR


def load_day(day):
    """(ts_sec, px, iid_first, iid_last) trade prints of the UTC-day file, ts-sorted."""
    p = os.path.join(STORE[day], f"NG_{day}.jsonl.gz")
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
    bad = {i for i in iids if i != WALK_INSTRUMENT}
    assert not bad, f"{day}: non-1008 instrument ids {bad} in {p} - store selection is wrong, ABORT"
    return ts, px, (iids[0] if iids else None), (iids[-1] if iids else None)


def main():
    os.makedirs(OUT, exist_ok=True)
    a_ts, a_px, a_iid, _ = load_day(ANCHOR)
    a_et = pd.to_datetime(a_ts, unit="s", utc=True).tz_convert(ET)
    anchor_close = float(a_px[-1])
    last_hr = a_px[a_et >= a_et[-1] - pd.Timedelta(hours=1)]
    a_dir = "up" if len(last_hr) > 1 and last_hr[-1] > last_hr[0] else "down"

    guess = json.load(open(os.path.join(HERE, "forecasts", "grp14.json")))
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
            off = round(o - prev_close, 3)
            rolls.append({"date": d, "offset": off,
                          "note": f"instrument {prev_iid} -> {iid_first}; UNEXPECTED on the 1008 basis"})
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
                     "group": 14, "open": round(o, 3), "close": round(c, 3),
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

    out = {"market": "NG", "tag": "g14",
           "price_basis": ("CALENDAR-FRONT 1008/NGJ26 continuation (Greg S102: 'for kalshi, the one "
                           "that settles closest to its close' - Kalshi underlying = front month "
                           "through Mar 13). Files: n0 store 0227-0302, n1 store 0303-0313 per the "
                           "S102 roll-check subagent (OI-rank flip 0302->0303). No roll in-window; "
                           "instrument 1008 hard-asserted every file."),
           "anchor": {"date": ANCHOR, "price": round(anchor_close, 3), "last_hour_dir": a_dir},
           "seams": [], "n_days": len(recs), "rolls": rolls, "days": recs}
    rt_path = os.path.join(OUT, "g14_rt.json")
    json.dump(out, open(rt_path, "w"), indent=1)
    print(f"[g14_rt] wrote {rt_path}: {len(recs)} days, rolls={rolls}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(16, 5.5))
    adt = pd.to_datetime(np.asarray(cont_t), unit="s", utc=True).tz_convert(ET)
    ax.plot(adt, cont_p, color="#1f6feb", lw=0.9, label="actual (1008/NGJ26 calendar front)")
    if gx:
        gdt = pd.to_datetime(np.asarray(gx), unit="s", utc=True).tz_convert(ET)
        ax.plot(gdt, gy, color="#e8710a", lw=1.5, ls="--", label="blind guess (followed)")
    ax.axhline(anchor_close, color="#999", lw=0.6, ls=":")
    ax.set_title(f"NG G14 blind (one-shot, brain {guess.get('brain_version')}) vs actual - Sun 2026-03-01 .. Fri 2026-03-13  "
                 f"anchor {anchor_close:.3f} ({a_dir})  basis 1008/NGJ26 calendar front  DST Mar 8", fontsize=10, fontweight="bold")
    ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=7)
    plt.tight_layout()
    png = os.path.join(OUT, "g14_blind.png")
    plt.savefig(png, dpi=120, bbox_inches="tight")
    print(f"[g14_rt] wrote {png}")


if __name__ == "__main__":
    main()
