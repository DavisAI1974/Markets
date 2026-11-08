"""Does the forecast of the NEXT burst's polarity convert into price?

other_things_oct18 found that the frozen state forecasts the polarity of the next frozen-detector event
(same side after a persistent state or a P seed, opposite after fast-collapse or an O seed) at 59 to 68
percent on October 18 and 17 alike, while no source forecasts the price direction from the anchor. Section
11 found that a burst's price move is contemporaneous with the burst. So the open question is whether a
correct forecast of the next burst's side, held from the knowable anchor t0+60, captures the next burst's
own contemporaneous move. For every event whose next event begins after the anchor, this script measures,
oriented by the forecast: the price change from the anchor to the next event's t0 (the wait), from the
next t0 to its confirmation (the next burst's own window), from the anchor to next confirm + 60, and
longer horizons from the anchor (+1800, +3600). Per A state, seed and pre-event volume tercile, with the
realised-polarity hit rate beside each. No trade cost.
"""

import gzip
import json
import sys
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402


def val(series, t):
    return series[t] if 0 <= t < len(series) and X.fin(series[t]) else None


def tri(vals):
    v = [x for x in vals if x is not None]
    return dict(n=len(v), with_=sum(1 for x in v if x > 0), flat=sum(1 for x in v if x == 0), against=sum(1 for x in v if x < 0),
                hit_nonflat=round(sum(1 for x in v if x > 0) / max(1, sum(1 for x in v if x != 0)), 3), median=median(v) if v else None)


def main():
    stream = X.replay_cached()
    last = min(stream["last_trade"], 86399)
    price, cb, cs = stream["price"], stream["cb"], stream["cs"]
    cls = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / f"frozen-a-classifier-{X.TAG}-events.jsonl.gz", "rt"))}
    ev = [json.loads(l) for l in gzip.open(HERE / f"exhaustion-clock-{X.TAG}-events.jsonl.gz", "rt")]
    ev = sorted((r for r in ev if r["mode"] == "day"), key=lambda r: r["t0"])
    recs = []
    for i, r in enumerate(ev[:-1]):
        t0, pol, nx = r["t0"], r["polarity"], ev[i + 1]
        a = t0 + 60
        st, seed = cls[t0]["a_state"], r["seed_state"]
        fc_state = pol if st == "A-persistent" else -pol
        fc_seed = pol if seed == "P" else -pol if seed == "O" else None
        rec = dict(t0=t0, polarity=pol, a_state=st, seed=seed, next_t0=nx["t0"], next_pol=nx["polarity"], next_after_anchor=int(nx["t0"] > a),
                   next_confirm=nx["confirm"], pre300_volume=(cb[t0 + 1] - cb[max(0, t0 - 299)]) + (cs[t0 + 1] - cs[max(0, t0 - 299)]))
        p_a = val(price, a)
        for name, fc in (("state", fc_state), ("seed", fc_seed)):
            if fc is None or p_a is None:
                continue
            rec[f"{name}_forecast"] = fc
            rec[f"{name}_hit"] = int(fc == nx["polarity"])
            segs = {}
            p_n0 = val(price, nx["t0"]); p_nc = val(price, nx["confirm"]) if nx["confirm"] is not None and nx["confirm"] <= last else None
            if p_n0 is not None:
                segs["anchor_to_next_t0"] = fc * (p_n0 - p_a) / X.TICK
            if p_n0 is not None and p_nc is not None:
                segs["next_t0_to_next_confirm"] = fc * (p_nc - p_n0) / X.TICK
            if p_nc is not None and nx["confirm"] + 60 <= last:
                segs["anchor_to_next_confirm_plus60"] = fc * (val(price, nx["confirm"] + 60) - p_a) / X.TICK
            for h in (1800, 3600):
                ph = val(price, a + h) if a + h <= last else None
                if ph is not None:
                    segs[f"anchor_to_plus{h}"] = fc * (ph - p_a) / X.TICK
            for k, v in segs.items():
                rec[f"{name}_{k}"] = round(v)
        recs.append(rec)
    vols = sorted(r["pre300_volume"] for r in recs)
    cuts = (X.quantile(vols, 1 / 3), X.quantile(vols, 2 / 3))
    for r in recs:
        r["vol_tercile"] = "low" if r["pre300_volume"] <= cuts[0] else "mid" if r["pre300_volume"] <= cuts[1] else "high"
    segs = ("anchor_to_next_t0", "next_t0_to_next_confirm", "anchor_to_next_confirm_plus60", "anchor_to_plus1800", "anchor_to_plus3600")
    out = dict(events=len(recs), next_after_anchor=sum(r["next_after_anchor"] for r in recs), vol_cuts=cuts)

    def block(sub, name):
        sub = [r for r in sub if f"{name}_forecast" in r]
        hits = [r[f"{name}_hit"] for r in sub]
        d = dict(n=len(sub), forecast_hit=round(sum(hits) / len(hits), 3) if hits else None)
        for s in segs:
            d[s] = tri([r.get(f"{name}_{s}") for r in sub])
        # the capture conditional on the forecast being right or wrong, for the burst's own window
        for lab, flag in (("right", 1), ("wrong", 0)):
            d[f"next_window_when_forecast_{lab}"] = tri([r.get(f"{name}_next_t0_to_next_confirm") for r in sub if r[f"{name}_hit"] == flag])
        return d

    for name in ("state", "seed"):
        res = {}
        base = [r for r in recs if r["next_after_anchor"]]
        res["all_next_after_anchor"] = block(base, name)
        res["by_a_state"] = {g: block([r for r in base if r["a_state"] == g], name) for g in ("A-fast-collapse", "A-persistent")}
        res["by_seed"] = {g: block([r for r in base if r["seed"] == g], name) for g in "PSOX"}
        res["by_vol_tercile"] = {g: block([r for r in base if r["vol_tercile"] == g], name) for g in ("low", "mid", "high")}
        res["including_next_before_anchor"] = block(recs, name)
        out[f"forecast_{name}"] = res
    out["note"] = ("Forecast 'state': same side as the burst after A-persistent, opposite after A-fast-collapse. Forecast 'seed': same after P, opposite after O, none for S/X. "
                   "Moves are in ticks, oriented by the forecast (positive = price moved the way the forecast said the next burst would push). "
                   "Main rows restrict to next events that begin after the anchor t0+60 so the position could have been taken.")
    (HERE / f"next-burst-forecast-{X.TAG}-summary.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"next-burst-forecast-{X.TAG}-events.jsonl.gz", "wt") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    for name in ("state", "seed"):
        print(f"\n==== forecast by {name}  (events {out['events']}, next after anchor {out['next_after_anchor']})")
        res = out[f"forecast_{name}"]
        def show(label, d):
            print(f"  {label:22s} n {d['n']:4d} hit {d['forecast_hit']}")
            for s in segs + ("next_window_when_forecast_right", "next_window_when_forecast_wrong"):
                t = d[s]
                print(f"      {s:34s} {t['with_']:4d}/{t['flat']:4d}/{t['against']:4d} hit {t['hit_nonflat']} med {t['median']}")
        show("all", res["all_next_after_anchor"])
        for g, d in res["by_a_state"].items():
            show(g, d)
        for g, d in res["by_seed"].items():
            if d["n"]:
                show(f"seed {g}", d)
        for g, d in res["by_vol_tercile"].items():
            show(f"vol {g}", d)


if __name__ == "__main__":
    main()
