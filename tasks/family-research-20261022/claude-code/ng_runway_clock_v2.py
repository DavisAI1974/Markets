"""NG exhaustion runway clock v2: the frozen two-state duration totals with a causal day-speed scale.

Sections 12, 14 and 15 found that the frozen runway clock's two-state ORDERING holds on every session
(16 of 16 across four days) while its ABSOLUTE totals match only on October 18 and run 1.2x to 2.5x long on
the other three. The frozen totals were revealed on four other days, so the missing piece is the speed of
the day in hand. This module keeps the frozen totals untouched and multiplies them by one number: the
session's running price-travel speed, measured causally from the events already seen.

Clock v1 (baseline): remaining_k = max(0, T[state][k] - elapsed), T = the frozen totals.
Clock v2 (day scale): remaining_k = max(0, T[state][k] * s(t) - elapsed), where s(t) is the day's running
    price-travel speed divided by a reference day's running speed AT THE SAME SESSION TIME. The running
    speed at time t is the Kaplan-Meier median of the either-direction 3-tick time over all events born
    before t, censored at t (nothing after 'now' is used). Matching by session time matters: the overnight
    tape travels 4 to 7 times slower than the US day on every session, so an unmatched running ratio
    measures the hour, not the day. Two references: v2a = October 18's curve (the session on which the
    frozen persistent totals already fit; a choice made after seeing October 18 and stated), v2b = the
    median of the other three days' curves (leave-one-day-out, no privileged day). Until 30 events have
    been seen on both curves, s = 1 (v1).
Clock v3 (day scale + event activity, leave-one-day-out): v2a times an activity multiplier m[state][tercile]
    estimated on the other three days as the ratio of the realised with-polarity 3-tick KM median in that
    pre-event volume tercile to the state's overall median, tercile cuts taken from the training days.
    This one is fitted (on other days), the first two are not.

Clock v4 (delivered): v2a times a state-level factor, the median over the OTHER three days of realised / v2a
    predicted (about 1.45 for fast-collapse, 1.1 to 1.2 for persistent); leave-one-day-out, so each day is
    scored with factors it did not contribute to. The per-event scatter around any of these medians is a
    factor of about 3.5 either way, so the delivered clock emits a band: q25 and q75 multipliers of the
    realised remaining time relative to its median, per state, again from the other days. `RunwayClock`
    at the bottom is the live form of v4: feed it events as they are born and resolved, ask it for the
    remaining time to each level with its band.

Scoring at the anchor t0+60, per day, state and scale: realised KM-median remaining among events still
short of the level; median predicted remaining; their ratio (1.0 is calibrated); the share of events
that reach the level within their predicted remaining time (0.5 is a calibrated median clock); and the
per-event median absolute log ratio where the level was reached. No trade cost; nothing refit except
the v3 multipliers, which are always out of day.
"""

import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runway_duration_test_oct18 import FROZEN, SCALES, km_median  # noqa: E402

TAGS = ("oct02", "oct03", "oct17", "oct18")
REFERENCE_TAG = "oct18"
WARMUP_EVENTS = 30
TRAIL_WINDOW = 60
ANCHOR = 60


def load(tag):
    dur = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / f"runway-duration-{tag}-events.jsonl.gz", "rt"))}
    cls = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / f"frozen-a-classifier-{tag}-events.jsonl.gz", "rt"))}
    pre = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / f"beyond-direction-prebirth-{tag}-events.jsonl.gz", "rt"))}
    rows = []
    for t0 in sorted(dur):
        d, c = dur[t0], cls[t0]
        rows.append(dict(t0=t0, state=c["a_state"], polarity=d["polarity"], censor=d["censor_time"], either3=d["price_either_3t"],
                         pre300_volume=pre[t0]["pre300_volume"], **{f"with{k}": d[f"price_with_{k}t"] for k in SCALES}))
    return rows


def running_speed(rows, window=None):
    """Causal KM median of the either-direction 3-tick time over events born before each event (the last `window` of
    them when given), censored at that event's t0."""
    out = []
    for i, r in enumerate(rows):
        now = r["t0"]
        obs, cen = [], []
        prior = rows[:i] if window is None else rows[max(0, i - window):i]
        for p in prior:
            if p["either3"] is not None and p["t0"] + p["either3"] <= now:
                obs.append(p["either3"])
            else:
                cen.append(now - p["t0"])
        out.append(km_median(obs, cen) if i >= WARMUP_EVENTS and (obs or cen) else None)
    return out


def full_day_either3(rows):
    return km_median([r["either3"] for r in rows if r["either3"] is not None], [r["censor"] for r in rows if r["either3"] is None])


def fit_activity_multipliers(train_rows):
    vols = sorted(r["pre300_volume"] for r in train_rows)
    cuts = (vols[len(vols) // 3], vols[2 * len(vols) // 3])
    terc = lambda v: "low" if v <= cuts[0] else "mid" if v <= cuts[1] else "high"
    mult = {}
    for st in FROZEN:
        sub = [r for r in train_rows if r["state"] == st]
        base = km_median([r["with3"] for r in sub if r["with3"] is not None], [r["censor"] for r in sub if r["with3"] is None])
        mult[st] = {}
        for tc in ("low", "mid", "high"):
            s2 = [r for r in sub if terc(r["pre300_volume"]) == tc]
            m = km_median([r["with3"] for r in s2 if r["with3"] is not None], [r["censor"] for r in s2 if r["with3"] is None])
            mult[st][tc] = (m / base) if (m and base) else 1.0
    return cuts, mult


def score(rows, preds, label):
    """preds: list of dict k -> predicted remaining at +60 (None if event unusable)."""
    res = {}
    for st in FROZEN:
        res[st] = {}
        for k in SCALES:
            obs_rem, cen_rem, pred, hits, logerr = [], [], [], [], []
            for r, p in zip(rows, preds):
                if r["state"] != st or p is None or p.get(k) is None:
                    continue
                w = r[f"with{k}"]
                if w is not None and w <= ANCHOR:
                    continue  # already at the level when the clock starts
                rem_pred = p[k]
                pred.append(rem_pred)
                if w is None:
                    cen_rem.append(r["censor"] - ANCHOR)
                    hits.append(0)
                else:
                    obs_rem.append(w - ANCHOR)
                    hits.append(int(w - ANCHOR <= rem_pred))
                    if rem_pred > 0:
                        logerr.append(abs(math.log((w - ANCHOR) / rem_pred)))
            real = km_median(obs_rem, cen_rem) if obs_rem else None
            pm = median(pred) if pred else None
            res[st][str(k)] = dict(n=len(pred), realised_km_remaining=real, predicted_median_remaining=round(pm) if pm is not None else None,
                                   ratio_real_over_pred=round(real / pm, 2) if real and pm else None,
                                   reached_within_prediction=round(sum(hits) / len(hits), 3) if hits else None,
                                   median_abs_log_ratio=round(median(logerr), 3) if logerr else None)
    return res


def curve_at(rows, speeds, t):
    """Running speed of a day at session time t: value at the last event born at or before t (None during warm-up)."""
    v = None
    for r, sp in zip(rows, speeds):
        if r["t0"] > t:
            break
        v = sp
    return v


def main():
    data = {tag: load(tag) for tag in TAGS}
    speeds = {tag: running_speed(rows) for tag, rows in data.items()}
    speeds_w = {tag: running_speed(rows, window=TRAIL_WINDOW) for tag, rows in data.items()}
    day_speed = {tag: full_day_either3(rows) for tag, rows in data.items()}
    out = dict(reference_tag=REFERENCE_TAG, full_day_either3_median_s=day_speed, warmup_events=WARMUP_EVENTS, frozen_totals=FROZEN, clocks={})

    def scale(tag, t, mode):
        sp = speeds_w if mode == "c" else speeds
        own = curve_at(data[tag], sp[tag], t)
        if own is None:
            return 1.0
        if mode in ("a", "c"):
            ref = curve_at(data[REFERENCE_TAG], sp[REFERENCE_TAG], t) if tag != REFERENCE_TAG else own
            return own / ref if ref else 1.0
        others = [curve_at(data[o], speeds[o], t) for o in TAGS if o != tag]
        others = [x for x in others if x]
        return own / median(others) if others else 1.0

    traj = {}
    for tag in TAGS:
        traj[tag] = {f"h{h}": dict(v2a=round(scale(tag, h * 3600, "a"), 2), v2b=round(scale(tag, h * 3600, "b"), 2)) for h in (2, 4, 6, 8, 12, 16, 20)}
    out["day_scale_trajectory"] = traj
    for tag, rows in data.items():
        sa = [scale(tag, r["t0"] + ANCHOR, "a") for r in rows]
        sb = [scale(tag, r["t0"] + ANCHOR, "b") for r in rows]
        sc = [scale(tag, r["t0"] + ANCHOR, "c") for r in rows]
        v1 = [{k: max(0, FROZEN[r["state"]][k] - ANCHOR) for k in SCALES} for r in rows]
        v2a = [{k: max(0, FROZEN[r["state"]][k] * sa[i] - ANCHOR) for k in SCALES} for i, r in enumerate(rows)]
        v2b = [{k: max(0, FROZEN[r["state"]][k] * sb[i] - ANCHOR) for k in SCALES} for i, r in enumerate(rows)]
        v2c = [{k: max(0, FROZEN[r["state"]][k] * sc[i] - ANCHOR) for k in SCALES} for i, r in enumerate(rows)]
        train = [r for t2, rs in data.items() if t2 != tag for r in rs]
        cuts, mult = fit_activity_multipliers(train)
        terc = lambda v: "low" if v <= cuts[0] else "mid" if v <= cuts[1] else "high"
        v3 = [{k: max(0, FROZEN[r["state"]][k] * sa[i] * mult[r["state"]][terc(r["pre300_volume"])] - ANCHOR) for k in SCALES} for i, r in enumerate(rows)]
        out["clocks"][tag] = dict(v1_frozen=score(rows, v1, "v1"), v2a_day_scale_ref_oct18=score(rows, v2a, "v2a"), v2b_day_scale_ref_loo=score(rows, v2b, "v2b"),
                                  v2c_trailing60_ref_oct18=score(rows, v2c, "v2c"), v3_v2a_activity_loo=score(rows, v3, "v3"),
                                  v3_multipliers_from_other_days={st: {tc: round(m, 2) for tc, m in d.items()} for st, d in mult.items()}, v3_cuts=cuts,
                                  median_scale_at_anchor=dict(v2a=round(median(sa), 2), v2b=round(median(sb), 2)))
        with gzip.open(HERE / f"runway-clock-v2-{tag}-events.jsonl.gz", "wt") as f:
            for i, r in enumerate(rows):
                f.write(json.dumps(dict(t0=r["t0"], state=r["state"], scale_v2a=sa[i], scale_v2b=sb[i], activity_tercile_loo=terc(r["pre300_volume"]),
                                        v1=v1[i], v2a=v2a[i], v2b=v2b[i], v3=v3[i], realised_with={k: r[f"with{k}"] for k in SCALES})) + "\n")
    # v4: v2a times a state-level factor = median over the OTHER days' v2a cells (4 scales) of realised / predicted
    for tag, rows in data.items():
        fac = {}
        for st in FROZEN:
            vals = [out["clocks"][o]["v2a_day_scale_ref_oct18"][st][str(k)]["ratio_real_over_pred"] for o in TAGS if o != tag for k in SCALES]
            vals = [v for v in vals if v]
            fac[st] = median(vals) if vals else 1.0
        sa = [scale(tag, r["t0"] + ANCHOR, "a") for r in rows]
        v4 = [{k: max(0, FROZEN[r["state"]][k] * sa[i] * fac[r["state"]] - ANCHOR) for k in SCALES} for i, r in enumerate(rows)]
        out["clocks"][tag]["v4_v2a_state_factor_loo"] = score(rows, v4, "v4")
        out["clocks"][tag]["v4_state_factors_from_other_days"] = {st: round(f, 2) for st, f in fac.items()}
        # band: q25 / q75 of (realised remaining / v4 predicted remaining) on the other days, per state, observed events only
        band = {}
        for st in FROZEN:
            ratios = []
            for o in TAGS:
                if o == tag:
                    continue
                orows = data[o]
                osa = [scale(o, r["t0"] + ANCHOR, "a") for r in orows]
                ofac = {s2: median([x for x in (out["clocks"][o2]["v2a_day_scale_ref_oct18"][s2][str(k)]["ratio_real_over_pred"] for o2 in TAGS if o2 != o for k in SCALES) if x]) for s2 in FROZEN}
                for i, r in enumerate(orows):
                    if r["state"] != st:
                        continue
                    for k in SCALES:
                        w = r[f"with{k}"]
                        pred = FROZEN[st][k] * osa[i] * ofac[st] - ANCHOR
                        if w is not None and w > ANCHOR and pred > 0:
                            ratios.append((w - ANCHOR) / pred)
            ratios.sort()
            band[st] = dict(q25=round(ratios[len(ratios) // 4], 2), q75=round(ratios[3 * len(ratios) // 4], 2), n=len(ratios))
        out["clocks"][tag]["v4_band_from_other_days"] = band
        cov = {}
        for st in FROZEN:
            inside = total = 0
            for i, r in enumerate(rows):
                if r["state"] != st:
                    continue
                for k in SCALES:
                    w = r[f"with{k}"]
                    pred = FROZEN[st][k] * sa[i] * fac[st] - ANCHOR
                    if w is not None and w > ANCHOR and pred > 0:
                        total += 1
                        inside += band[st]["q25"] * pred <= (w - ANCHOR) <= band[st]["q75"] * pred
            cov[st] = dict(observed=total, inside_band_share=round(inside / total, 3) if total else None)
        out["clocks"][tag]["v4_band_coverage_observed_events"] = cov
    # summary across days: median ratio and hit share per clock
    agg = {}
    for v in ("v1_frozen", "v2a_day_scale_ref_oct18", "v2b_day_scale_ref_loo", "v2c_trailing60_ref_oct18", "v3_v2a_activity_loo", "v4_v2a_state_factor_loo"):
        ratios, hits, errs = [], [], []
        for tag in TAGS:
            for st in FROZEN:
                for k in SCALES:
                    c = out["clocks"][tag][v][st][str(k)]
                    if c["ratio_real_over_pred"]:
                        ratios.append(c["ratio_real_over_pred"]); hits.append(c["reached_within_prediction"]); errs.append(c["median_abs_log_ratio"])
        agg[v] = dict(cells=len(ratios), median_ratio=round(median(ratios), 2), ratio_range=(min(ratios), max(ratios)), median_hit_share=round(median(hits), 3),
                      cells_within_20pct=sum(1 for x in ratios if 0.8 <= x <= 1.25), median_abs_log_ratio=round(median(errs), 3))
    out["aggregate"] = agg
    (HERE / "runway-clock-v2-summary.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    print("full-day either-3t medians:", day_speed)
    print("day scale trajectory:", json.dumps(traj))
    for tag in TAGS:
        print(f"\n== {tag}")
        for v in ("v1_frozen", "v2a_day_scale_ref_oct18", "v2b_day_scale_ref_loo", "v2c_trailing60_ref_oct18", "v3_v2a_activity_loo", "v4_v2a_state_factor_loo"):
            print(" ", v)
            for st in FROZEN:
                row = out["clocks"][tag][v][st]
                print(f"    {st:16s}", " | ".join(f"{k}t real {row[str(k)]['realised_km_remaining']} pred {row[str(k)]['predicted_median_remaining']} ratio {row[str(k)]['ratio_real_over_pred']} hit {row[str(k)]['reached_within_prediction']}" for k in SCALES))
        print("  v3 multipliers:", out["clocks"][tag]["v3_multipliers_from_other_days"], "| v4 state factors:", out["clocks"][tag]["v4_state_factors_from_other_days"], "| median scale at anchor:", out["clocks"][tag]["median_scale_at_anchor"])
        print("  v4 band:", out["clocks"][tag]["v4_band_from_other_days"], "| coverage:", out["clocks"][tag]["v4_band_coverage_observed_events"])
    print("\n== aggregate", json.dumps(agg, indent=1))


class RunwayClock:
    """Live form of clock v4. Frozen totals untouched; one day scale, one state factor, one band, all supplied.

    reference_curve: list of (session_second, either3_median) for the reference day (October 18 here), used to
    match session time. state_factor and band come from the other days (see runway-clock-v2-summary.json).
    Feed `birth(t0)` when a frozen-detector event is born, `resolved_either3(t0, seconds)` when its price has
    first moved 3 ticks either way, and query `remaining(state, t0, now)` once the A state is known (t0+60).
    Nothing here uses data after `now`.
    """

    def __init__(self, reference_curve, state_factor, band, warmup=WARMUP_EVENTS):
        self.ref = sorted(reference_curve)
        self.factor, self.band, self.warmup = state_factor, band, warmup
        self.births, self.either3 = [], {}

    def birth(self, t0):
        self.births.append(t0)

    def resolved_either3(self, t0, seconds):
        self.either3[t0] = seconds

    def _own_speed(self, now):
        prior = [t for t in self.births if t < now]
        if len(prior) < self.warmup:
            return None
        obs = [self.either3[t] for t in prior if t in self.either3 and t + self.either3[t] <= now]
        cen = [now - t for t in prior if not (t in self.either3 and t + self.either3[t] <= now)]
        return km_median(obs, cen)

    def _ref_speed(self, now):
        v = None
        for t, m in self.ref:
            if t > now:
                break
            v = m
        return v

    def day_scale(self, now):
        own, ref = self._own_speed(now), self._ref_speed(now)
        return own / ref if own and ref else 1.0

    def remaining(self, state, t0, now):
        elapsed = now - t0
        sc = self.day_scale(now)
        out = {}
        for k in SCALES:
            med = max(0.0, FROZEN[state][k] * sc * self.factor[state] - elapsed)
            out[k] = dict(q25=round(self.band[state]["q25"] * med), median=round(med), q75=round(self.band[state]["q75"] * med))
        return dict(day_scale=round(sc, 3), elapsed=elapsed, remaining_s=out)


if __name__ == "__main__":
    main()
