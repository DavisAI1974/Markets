"""The stack test: the activity and persistence read (timing and size) crossed with direction sources.

The frozen exhaustion state and the pre-birth activity read say WHEN the price will travel and HOW FAR
(section 13), not which way. This script asks whether any direction source available at the same knowable
anchor (t0+60) supplies the missing half, per cell, and whether the two halves stack: is the direction call
better, or the called move larger, in the cells where the activity read says a large move is coming?

Direction sources (every operand ends at or before the anchor; leakage by construction impossible):
  pol        the burst's own polarity (section 11: contemporaneous only)
  next       the state's forecast of the NEXT burst's polarity: same side after a persistent state or P seed,
             opposite after fast-collapse or O seed (other_things_oct18: persistent flips 33%, fast 56%)
  dip300     sign of the 300 s flow imbalance at the anchor (the S92 price-leg nowcast operand); 'strong'
             variant keeps only the top tercile of |imbalance| on this day (threshold stated, not the S92 one)
  book10     sign of the 10-level resting-book imbalance at the anchor
  touch      sign of best-bid size minus best-ask size at the anchor
  recruit    pol times sign(toward-side depth change minus away-side depth change over t0..+60): the S92
             turning-point read (held legs grow the far ladder) applied to the burst's own leg
  mom300     sign of the price change over the 300 s before the anchor
Targets: sign of the net price change anchor -> +300 and +600; direction of the first 3-tick excursion from
the anchor; the realised next-burst polarity (for 'next' only).
Cells: A state x pre-event volume tercile; hour class (release hour 14:00-15:00 UTC kept apart); and
two-source agreement cells. Counts with / flat / against and the median move in the called direction, in
ticks. No pooling as the final word; the per-cell table is the deliverable. No trade cost.
"""

import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402

HORIZONS = (300, 600)


def val(series, t):
    return series[t] if 0 <= t < len(series) and X.fin(series[t]) else None


def first_dir(price, a, k, last):
    p0 = val(price, a)
    if p0 is None:
        return None
    for t in range(a + 1, last + 1):
        v = price[t]
        if X.fin(v) and abs(v - p0) >= k * X.TICK - 1e-9:
            return 1 if v > p0 else -1
    return None


def tri(calls, moves):
    """calls: +-1 direction calls; moves: signed tick changes. Returns with/flat/against and median called move."""
    w = f = ag = 0
    called = []
    for c, m in zip(calls, moves):
        if c is None or m is None or c == 0:
            continue
        cm = c * m
        called.append(cm)
        if cm > 0:
            w += 1
        elif cm == 0:
            f += 1
        else:
            ag += 1
    n = w + f + ag
    return dict(n=n, with_=w, flat=f, against=ag, hit_share_nonflat=round(w / (w + ag), 3) if w + ag else None,
                median_called_move=median(called) if called else None)


def main():
    stream = X.replay_cached()
    last = min(stream["last_trade"], 86399)
    price, book, cb, cs = stream["price"], stream["book"], stream["cb"], stream["cs"]
    bdep, adep, btch, atch = stream["bid_depth"], stream["ask_depth"], stream["bid_touch"], stream["ask_touch"]
    cls = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / f"frozen-a-classifier-{X.TAG}-events.jsonl.gz", "rt"))}
    ev = [json.loads(l) for l in gzip.open(HERE / f"exhaustion-clock-{X.TAG}-events.jsonl.gz", "rt")]
    ev = sorted((r for r in ev if r["mode"] == "day"), key=lambda r: r["t0"])
    recs = []
    for i, r in enumerate(ev):
        t0, pol = r["t0"], r["polarity"]
        a = t0 + 60
        if a > last:
            continue
        st, seed = cls[t0]["a_state"], r["seed_state"]
        rec = dict(t0=t0, polarity=pol, seed=seed, a_state=st, hour_utc=((t0 + X.DAY0) % 86400) // 3600,
                   pre300_volume=(cb[t0 + 1] - cb[max(0, t0 - 299)]) + (cs[t0 + 1] - cs[max(0, t0 - 299)]))
        imb, vol = X.window_imb(cb, cs, a, 300)
        rec["dip300_imb"], rec["dip300_vol"] = imb, vol
        src = {"pol": pol, "next_state": pol if st == "A-persistent" else -pol, "next_seed": pol if seed == "P" else -pol if seed == "O" else None,
               "dip300": None if imb is None else X.sgn(imb), "book10": None if val(book, a) is None else X.sgn(val(book, a)),
               "touch": None if val(btch, a) is None or val(atch, a) is None else X.sgn(val(btch, a) - val(atch, a))}
        toward, away = (adep, bdep) if pol > 0 else (bdep, adep)
        if None not in (val(toward, t0), val(toward, a), val(away, t0), val(away, a)):
            src["recruit"] = pol * X.sgn((val(toward, a) - val(toward, t0)) - (val(away, a) - val(away, t0)))
        p_a, p_pre = val(price, a), val(price, max(0, a - 300))
        src["mom300"] = None if p_a is None or p_pre is None else X.sgn(p_a - p_pre)
        rec["sources"] = src
        tg = {}
        for h in HORIZONS:
            ph = val(price, a + h) if a + h <= last else None
            tg[f"net{h}"] = None if ph is None or p_a is None else round((ph - p_a) / X.TICK)
        tg["first3"] = first_dir(price, a, 3, last)
        tg["next_pol"] = ev[i + 1]["polarity"] if i + 1 < len(ev) else None
        rec["targets"] = tg
        recs.append(rec)
    vols = sorted(r["pre300_volume"] for r in recs)
    cuts = (X.quantile(vols, 1 / 3), X.quantile(vols, 2 / 3))
    absimb = sorted(abs(r["dip300_imb"]) for r in recs if r["dip300_imb"] is not None)
    strong_cut = X.quantile(absimb, 2 / 3)
    for r in recs:
        r["vol_tercile"] = "low" if r["pre300_volume"] <= cuts[0] else "mid" if r["pre300_volume"] <= cuts[1] else "high"
        r["hour_class"] = "release_14_15" if r["hour_utc"] == 14 else "us_day_13_20" if 13 <= r["hour_utc"] <= 20 else "overnight"
        r["sources"]["dip300_strong"] = r["sources"]["dip300"] if (r["dip300_imb"] is not None and abs(r["dip300_imb"]) >= strong_cut) else None
    source_names = ["pol", "next_state", "next_seed", "dip300", "dip300_strong", "book10", "touch", "recruit", "mom300"]
    out = dict(events=len(recs), vol_cuts=cuts, strong_abs_imb_cut=strong_cut, horizons=HORIZONS)

    def table(sub):
        t = {}
        for s in source_names:
            calls = [r["sources"].get(s) for r in sub]
            t[s] = {f"net{h}": tri(calls, [r["targets"][f"net{h}"] for r in sub]) for h in HORIZONS}
            t[s]["first3"] = tri(calls, [r["targets"]["first3"] for r in sub])
            if s.startswith("next"):
                t[s]["realised_next_polarity"] = tri(calls, [r["targets"]["next_pol"] for r in sub])
        return t

    out["all_events"] = table(recs)
    out["by_a_state"] = {g: table([r for r in recs if r["a_state"] == g]) for g in ("A-fast-collapse", "A-persistent")}
    out["by_vol_tercile"] = {g: table([r for r in recs if r["vol_tercile"] == g]) for g in ("low", "mid", "high")}
    out["by_state_x_tercile"] = {f"{st}|{tc}": table([r for r in recs if r["a_state"] == st and r["vol_tercile"] == tc]) for st in ("A-fast-collapse", "A-persistent") for tc in ("low", "mid", "high")}
    out["by_hour_class"] = {g: table([r for r in recs if r["hour_class"] == g]) for g in ("overnight", "us_day_13_20", "release_14_15")}
    # two-source agreement: every pair, all events and the high-activity cell
    pairs = {}
    for i, s1 in enumerate(source_names):
        for s2 in source_names[i + 1:]:
            for label, sub in (("all", recs), ("high_vol", [r for r in recs if r["vol_tercile"] == "high"]), ("fast_high", [r for r in recs if r["vol_tercile"] == "high" and r["a_state"] == "A-fast-collapse"])):
                agree = [r for r in sub if r["sources"].get(s1) is not None and r["sources"].get(s1) == r["sources"].get(s2)]
                calls = [r["sources"][s1] for r in agree]
                pairs[f"{s1}&{s2}|{label}"] = {f"net{h}": tri(calls, [r["targets"][f"net{h}"] for r in agree]) for h in HORIZONS}
                pairs[f"{s1}&{s2}|{label}"]["first3"] = tri(calls, [r["targets"]["first3"] for r in agree])
    out["two_source_agreement"] = pairs
    # size of the move regardless of direction, by cell (what the activity half contributes)
    out["abs_move_by_cell"] = {f"{st}|{tc}": {f"net{h}": X.quantile([abs(r["targets"][f"net{h}"]) for r in recs if r["a_state"] == st and r["vol_tercile"] == tc and r["targets"][f"net{h}"] is not None], .5) for h in HORIZONS}
                               for st in ("A-fast-collapse", "A-persistent") for tc in ("low", "mid", "high")}
    out["note"] = ("All source operands end at or before the anchor t0+60. 'next_state'/'next_seed' are forecasts of the next burst's polarity "
                   "from the current state; their realised_next_polarity row is the check. 'dip300_strong' threshold is this day's top tercile of |imbalance|, "
                   "not the S92 strong-flow definition. Hit shares are over non-flat outcomes; median_called_move is the signed move in the called direction.")
    (HERE / f"stack-direction-sources-{X.TAG}-summary.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"stack-direction-sources-{X.TAG}-events.jsonl.gz", "wt") as f:
        for r in recs:
            f.write(json.dumps(r, default=str) + "\n")

    def show(title, t):
        print(f"\n== {title}")
        for s, row in t.items():
            parts = []
            for k, v in row.items():
                parts.append(f"{k}: {v['with_']}/{v['flat']}/{v['against']} hit {v['hit_share_nonflat']} med {v['median_called_move']}")
            print(f"  {s:14s} " + " | ".join(parts))
    show("all events", out["all_events"])
    for g, t in out["by_a_state"].items():
        show(g, t)
    for g, t in out["by_vol_tercile"].items():
        show(f"vol {g}", t)
    for g, t in out["by_state_x_tercile"].items():
        show(g, t)
    for g, t in out["by_hour_class"].items():
        show(g, t)
    print("\n== abs move medians by cell", json.dumps(out["abs_move_by_cell"]))
    print("\n== two-source agreement, net300 hit >= 0.58 or <= 0.42 with n >= 30")
    for k, v in pairs.items():
        r3 = v["net300"]
        if r3["n"] >= 30 and r3["hit_share_nonflat"] is not None and (r3["hit_share_nonflat"] >= 0.58 or r3["hit_share_nonflat"] <= 0.42):
            print(f"  {k:34s} net300 {r3['with_']}/{r3['flat']}/{r3['against']} hit {r3['hit_share_nonflat']} med {r3['median_called_move']} | net600 hit {v['net600']['hit_share_nonflat']} | first3 hit {v['first3']['hit_share_nonflat']}")


if __name__ == "__main__":
    main()
