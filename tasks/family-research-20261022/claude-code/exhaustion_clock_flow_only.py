"""Frozen exhaustion detector and its three clocks on per-second flow alone (no prices), for the dates whose
standalone exports have not landed. Input: the per-second classified buy/sell table captured from the box
(flow-book-discovery-v1/date-tables/<date>/legacy_native_signed_flow.json.gz). Same constants as the
October 18 pass: ROLL 20, day 85th percentile, 5 s local max, 45 s refractory by prominence, PERSIST 3
endpoint, seed state from the first zero within +60 and the late pressure over t0+41..t0+60. Reports event
counts, the saturation of the threshold, runway and confirmation offsets, and how many exhaustions are over
before the two information horizons. Price outcomes wait for each date's print export."""

import gzip
import json
import sys
from collections import Counter
from math import floor
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402

HERE = Path(__file__).resolve().parent


def run(date):
    path = HERE.parent / "flow-book-discovery-v1" / "date-tables" / date / "legacy_native_signed_flow.json.gz"
    table = json.load(gzip.open(path, "rt"))
    rows = table["per_second"]
    first = rows[0]["second"]
    n = rows[-1]["second"] - first + 1
    buy, sell = [0.0] * n, [0.0] * n
    for r in rows:
        buy[r["second"] - first] = r["buy"]; sell[r["second"] - first] = r["sell"]
    cb, cs = [0.0] * (n + 1), [0.0] * (n + 1)
    for i in range(n):
        cb[i + 1] = cb[i] + buy[i]; cs[i + 1] = cs[i] + sell[i]
    roll = [X.NAN] * n
    for i in range(n):
        lo = max(0, i - X.ROLL + 1)
        b, s = cb[i + 1] - cb[lo], cs[i + 1] - cs[lo]
        if b + s > 0:
            roll[i] = (b - s) / (b + s)
    traded = [i for i in range(n) if buy[i] + sell[i] > 0]
    stream = dict(roll=roll, buy=buy, sell=sell, cb=cb, cs=cs, first_trade=traded[0], last_trade=traded[-1])
    picked, n_cand, thr = X.detect(stream, "day")
    finite = [abs(v) for v in roll if X.fin(v)]
    sat = sum(1 for v in finite if v >= 1 - 1e-12) / len(finite)
    out = []
    for t0, mag, prom in picked:
        pol = X.sgn(roll[t0])
        if not pol:
            continue
        raw_arc = [pol * roll[t0 + d] if X.fin(roll[t0 + d]) else X.NAN for d in range(-X.PRE, X.POST + 1)]
        arc = X.fill_curve(raw_arc)
        pre_def = arc is not None
        if arc is None:
            arc = X.fill_curve([0.0] + raw_arc[1:])
        post = arc[X.PRE:]
        zero_s = X.first_zero(post)
        late_imb, late_vol = X.window_imb(cb, cs, t0 + 60, 20)
        lp = None if late_imb is None else pol * late_imb
        seed = "P" if zero_s is None else "X" if (lp is None or abs(lp) < 1e-12) else ("S" if lp > 0 else "O")
        onset, confirm = X.endpoint(roll, t0, pol, stream["last_trade"])
        dip, vol = X.window_imb(cb, cs, t0, 300)
        out.append(dict(t0=t0, second=first + t0, polarity=pol, seed=seed, pre_arc_defined=pre_def, runway=None if onset is None else onset - t0,
                        confirm=None if confirm is None else confirm - t0, dip300=dip, dip300_vol=vol, burst_vol=X.window_imb(cb, cs, t0, 20)[1]))
    conf = [e["confirm"] for e in out if e["confirm"] is not None]
    rw = [e["runway"] for e in out if e["runway"] is not None]
    summary = dict(
        date=date, seconds=n, first_second=first, trades_seen=table["summary"]["trades_seen"], day_threshold_85pct=thr,
        share_of_finite_roll_seconds_saturated=round(sat, 4), events=len(out), candidates=n_cand,
        polarity=Counter(e["polarity"] for e in out), seed_states=Counter(e["seed"] for e in out), pre_arc_defined=sum(1 for e in out if e["pre_arc_defined"]),
        censored=sum(1 for e in out if e["confirm"] is None),
        runway_s=dict(q25=X.quantile(rw, .25), median=median(rw), q75=X.quantile(rw, .75), max=max(rw)) if rw else None,
        confirm_offset_s=dict(q25=X.quantile(conf, .25), median=median(conf), q75=X.quantile(conf, .75), max=max(conf)) if conf else None,
        confirmed_before_info5=sum(1 for c in conf if c <= 5), confirmed_before_info50=sum(1 for c in conf if c <= 50), confirmed_before_seed_known=sum(1 for c in conf if c <= 61),
        runway_by_seed={st: median([e["runway"] for e in out if e["seed"] == st and e["runway"] is not None] or [None]) for st in "POSX"},
        burst_volume_20s=dict(one_lot=sum(1 for e in out if e["burst_vol"] == 1), two_to_five=sum(1 for e in out if 2 <= e["burst_vol"] <= 5), over_five=sum(1 for e in out if e["burst_vol"] > 5)),
        dip300_sign_vs_polarity=Counter("same" if e["dip300"] is not None and X.sgn(e["dip300"]) == e["polarity"] else "opposite" if e["dip300"] is not None and X.sgn(e["dip300"]) == -e["polarity"] else "zero_or_undefined" for e in out),
        inter_event_gap_s=dict(median=median([out[i]["t0"] - out[i - 1]["t0"] for i in range(1, len(out))]), under_60=sum(1 for i in range(1, len(out)) if out[i]["t0"] - out[i - 1]["t0"] < 60)),
        note="Flow only; no price outcomes until the date's print export lands. Partial-span dates begin at the UTC midnight snapshot.",
    )
    (HERE / f"exhaustion-clock-{date}-flow-only.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"exhaustion-clock-{date}-flow-only-events.jsonl.gz", "wt") as f:
        for e in out:
            f.write(json.dumps(e) + "\n")
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    for date in sys.argv[1:] or ("20231002", "20231017"):
        run(date)
