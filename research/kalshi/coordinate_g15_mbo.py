"""coordinate_g15_mbo.py - COORDINATOR for the G15 MBO 5-specialist refine (S103).
Assembles the 5 specialist posteriors into grp15_mbo_refined.json (each day OWNED by its day-class
specialist - SELECT, never average). Builds the two-leg actual curve from the MBO trades (NGJ26 0313-0319,
NGK26 0320-0327, 0320 seam never-traded), renders blind + refined vs actual, scores blind vs refined.
Does NOT edit the immutable blind (forecasts/grp15.json)."""
import os, json, glob
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import databento as db

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "renders", "ng_refine_s95")
MBO_DIR = os.path.join(HERE, "..", "..", "data", "ng_mbo"); ET = "America/New_York"; MULT = 10000.0
ANCHOR = 3.132
DAYS = ["20260315","20260316","20260317","20260318","20260319","20260320","20260322","20260323","20260324","20260325","20260326","20260327"]
SEAM = "20260320"
OWNER = {"20260315":"A","20260322":"A","20260316":"B","20260323":"B","20260317":"C","20260318":"C","20260324":"C","20260325":"C","20260319":"D","20260326":"D","20260320":"E","20260327":"E"}
_DOW = ("Mon","Tue","Wed","Thu","Fri","Sat","Sun")


def _dir(side):
    v = getattr(side, "value", side)
    return 1 if str(v) in ("B", "Bid") else (-1 if str(v) in ("A", "Ask") else 0)


def load_trades(day):
    store = db.DBNStore.from_file(os.path.join(MBO_DIR, f"NG_{day}.dbn.zst"))
    rows = []
    for r in store:
        if type(r).__name__ != "MBOMsg":
            continue
        av = getattr(r.action, "value", r.action)
        if not (str(av) == "T"):
            continue
        p = r.price
        if p in (None, 9223372036854775807, -9223372036854775808):
            continue
        rows.append((int(r.ts_event) / 1e9, p / 1e9))
    rows.sort()
    return np.array([x[0] for x in rows]), np.array([x[1] for x in rows])


def specialist_posteriors():
    """date -> {net, curve, dir, conf, owner, verdict, selection}."""
    out = {}
    for f in glob.glob(os.path.join(HERE, "forecasts", "grp15_mbo_specialist_*.json")):
        x = os.path.basename(f).split("_")[-1].split(".")[0]
        d = json.load(open(f))
        entries = d if isinstance(d, list) else (d.get("days") if isinstance(d, dict) and isinstance(d.get("days"), list) else list(d.values()))
        for e in entries:
            if not isinstance(e, dict) or "date" not in e:
                continue
            dt = e["date"].replace("-", "")
            if OWNER.get(dt) != x:
                continue
            net = e.get("expected_magnitude_usd")
            if isinstance(net, str):
                try: net = int(net)
                except: net = None
            out[dt] = {"net": net, "curve": e.get("path_p50_curve"), "owner": x,
                       "conf": e.get("confidence"), "verdict": (e.get("mbo_verdict") or "")[:400],
                       "selection": (e.get("selection_reason") or "")[:300],
                       "dir": e.get("posterior_direction_by_horizon")}
    return out


def build_actual():
    """Per-day actual from MBO trades; continuous cum-$ from anchor, 0320 seam removed (never-traded)."""
    recs, cont_t, cont_p, cum_seam = [], [], [], 0.0
    prev_close = ANCHOR
    for d in DAYS:
        ts, px = load_trades(d)
        if px.size == 0:
            continue
        et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
        o, c = float(px[0]), float(px[-1])
        if d == SEAM:
            cum_seam += round(o - prev_close, 3)                       # April->May offset, never traded
        gap = 0 if d == SEAM else round((o - prev_close) * MULT)
        net = round((c - o) * MULT)
        recs.append({"date": d, "dow": _DOW[pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}").weekday()],
                     "open": round(o, 3), "close": round(c, 3), "net_usd": net, "gap_usd": gap,
                     "cum_from_anchor_usd": round((c - ANCHOR - cum_seam) * MULT)})
        idx = np.linspace(0, len(px) - 1, min(len(px), 400)).astype(int)
        cont_t.extend(ts[idx].tolist()); cont_p.extend((px[idx] - cum_seam).tolist())
        prev_close = c
    return recs, cont_t, cont_p, cum_seam


def guess_line(days_by_date, cont_anchor=ANCHOR):
    """cumulative guess price line from per-day gap+net (blind or refined)."""
    xs, ys, run = [], [], 0.0
    for d in DAYS:
        e = days_by_date.get(d)
        if not e:
            continue
        gap = e.get("gap", 0) or 0
        net = e.get("net", 0) or 0
        run += gap
        ys.append(cont_anchor + run / MULT); xs.append(d + "_o")
        run += net
        ys.append(cont_anchor + run / MULT); xs.append(d + "_c")
    return xs, ys


def main():
    posts = specialist_posteriors()
    actual, cont_t, cont_p, seam = build_actual()
    act_by = {r["date"]: r for r in actual}
    # blind day-moves from grp15.json
    blind = json.load(open(os.path.join(HERE, "forecasts", "grp15.json")))
    bl_by = {x["date"].replace("-", ""): x for x in blind["days"]}

    # ASSEMBLE grp15_mbo_refined.json (posterior update, per-day owned by specialist)
    refined_days = []
    for d in DAYS:
        p = posts.get(d, {})
        b = bl_by.get(d, {})
        refined_days.append({"date": d, "owner_specialist": OWNER[d],
                             "blind_net_usd": b.get("guessed_net_usd"),
                             "refined_net_usd": p.get("net"), "refined_path_p50": p.get("curve"),
                             "posterior_direction_by_horizon": p.get("dir"), "confidence": p.get("conf"),
                             "selection_reason": p.get("selection"), "mbo_verdict": p.get("verdict"),
                             "execution_authority": False})
    refined = {"group": 15, "tag": "g15_mbo", "kind": "5_specialist_posterior_refine", "brain_version": "s102.3+mbo",
               "anchor": {"date": "20260313", "price": ANCHOR, "contract": "NGJ26", "last_hour_dir": "down"},
               "price_basis": "two-leg Kalshi underlying NGJ26(1008)->NGK26(996), 0320 seam never-traded",
               "method": "5 day-class specialists (A weekend/B Monday/C core/D Thu-EIA/E Fri-expiry) -> coordinator SELECTS owner per day, NO averaging; posterior update of the immutable blind",
               "seam_offset": round(seam, 4), "days": refined_days}
    json.dump(refined, open(os.path.join(HERE, "forecasts", "grp15_mbo_refined.json"), "w"), indent=1)

    # DAY-MOVES (from prior close). blind = its own gap+net; refined = specialist day-move (already gap+net);
    # actual = its own gap+net. NEVER mix the actual gap into the refined (that double-counts on Sundays).
    def blind_dm(d): return (bl_by[d].get("overnight_gap_usd", 0) or 0) + (bl_by[d].get("guessed_net_usd", 0) or 0)
    def refined_dm(d): return posts[d]["net"] if posts.get(d, {}).get("net") is not None else blind_dm(d)
    def actual_dm(d): return act_by[d]["net_usd"] + act_by[d]["gap_usd"]

    # SCORE blind vs refined (day-move vs actual)
    score = []
    for d in DAYS:
        if d not in act_by: continue
        a = actual_dm(d); bnet = blind_dm(d); rnet = refined_dm(d)
        score.append({"date": d, "owner": OWNER[d], "actual_day_move": a,
                      "blind_day_move": bnet, "blind_err": bnet - a,
                      "refined_day_move": rnet, "refined_err": rnet - a,
                      "dir_blind_ok": (bnet > 0) == (a > 0) or abs(a) < 50,
                      "dir_refined_ok": (rnet > 0) == (a > 0) or abs(a) < 50})
    json.dump({"days": score,
               "blind_dir": sum(s["dir_blind_ok"] for s in score), "refined_dir": sum(s["dir_refined_ok"] for s in score),
               "n": len(score),
               "blind_mean_abs_err": round(np.mean([abs(s["blind_err"]) for s in score])),
               "refined_mean_abs_err": round(np.mean([abs(s["refined_err"]) for s in score]))},
              open(os.path.join(OUT, "g15_mbo_comparison.json"), "w"), indent=1)

    # RENDER blind + refined - FORM-FITTING the intraday p50 path (not straight open->close segments).
    adt = pd.to_datetime(np.asarray(cont_t), unit="s", utc=True).tz_convert(ET)
    spans = {d: load_trades(d) for d in DAYS if d in act_by}

    def _span_et(d):
        ts, _ = spans[d]
        return pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)

    def _curve_pts(curve):
        """normalize a [[et_hour, cum_from_open_usd], ...] path curve to (hpos, cum) arrays.
        hpos = hours since the 18:00 ET reopen (wraps 0..~23), so the shape lands at the right x."""
        if not isinstance(curve, list) or not curve:
            return None
        hh, cc = [], []
        for pt in curve:
            if not (isinstance(pt, (list, tuple)) and len(pt) >= 2):
                continue
            hh.append((float(pt[0]) - 18.0) % 24.0); cc.append(float(pt[1]))
        if len(hh) < 2:
            return None
        return np.asarray(hh), np.asarray(cc)

    def path_xy(d, curve, open_y, net_target=None):
        """map a day's p50 path onto its actual trade-time span; optionally SCALE the shape so its
        close lands exactly on net_target (magnitude from the scored day-move, shape from the forecast).
        net_target=None draws the forecast's OWN magnitude (used for the re-anchored-to-actual line)."""
        pts = _curve_pts(curve)
        et = _span_et(d)
        t0, t1 = et[0], et[-1]
        if pts is None:
            return [t0, t1], [open_y, open_y + ((net_target or 0) / MULT)]
        hpos, cum = pts
        rng = hpos.max() - hpos.min()
        frac = (hpos - hpos.min()) / rng if rng > 1e-6 else np.linspace(0, 1, len(hpos))
        factor = 1.0
        if net_target is not None and abs(cum[-1]) > 1e-6:
            factor = net_target / cum[-1]
        xs = [t0 + f * (t1 - t0) for f in frac]
        ys = [open_y + (c * factor) / MULT for c in cum]
        return xs, ys

    for tag, dmfn, curvefn, gapfn, netfn, color, label in [
        ("blind", blind_dm, lambda d: bl_by[d].get("guess_curve"),
         lambda d: bl_by[d].get("overnight_gap_usd", 0) or 0,
         lambda d: bl_by[d].get("guessed_net_usd", 0) or 0, "#e8710a", "blind (grp15)"),
        ("refined", refined_dm, lambda d: posts.get(d, {}).get("curve") or bl_by[d].get("guess_curve"),
         lambda d: 0, lambda d: refined_dm(d), "#2ea043", "refined (5-specialist MBO)")]:
        fig, ax = plt.subplots(figsize=(16, 5.5))
        ax.plot(adt, cont_p, color="#1f6feb", lw=0.7, label="actual (two-leg NGJ26->NGK26, MBO trades)")
        # (1) continuous FORM-FIT guess: compound from the running anchor cum, shape from the p50 path,
        #     close scaled to the scored day-move.
        gx, gy = [], []
        run = 0.0
        for d in DAYS:
            if d not in act_by: continue
            gap = gapfn(d); net = netfn(d)
            open_y = ANCHOR + (run + gap) / MULT
            xs, ys = path_xy(d, curvefn(d), open_y, net_target=net)
            gx.extend(xs); gy.extend(ys)
            run += dmfn(d)
        ax.plot(gx, gy, color=color, lw=1.5, label=f"{label} - form-fit p50 path (compound)")
        # (2) SAME guess RE-ANCHORED to the actual open each day (Greg: "if it started off on the price").
        #     Direction/shape skill without the compounding level drift; own magnitude, unscaled.
        for d in DAYS:
            if d not in act_by: continue
            xs, ys = path_xy(d, curvefn(d), act_by[d]["open"], net_target=None)
            ax.plot(xs, ys, color=color, lw=1.1, ls=(0, (2, 2)), alpha=0.55,
                    label="re-anchored to actual open (shape only)" if d == DAYS[0] else None)
        sd = pd.Timestamp(f"{SEAM[:4]}-{SEAM[4:6]}-{SEAM[6:]}", tz=ET)
        ax.axvline(sd, color="#999", lw=0.8, ls=":"); ax.text(sd, ax.get_ylim()[0], f" roll seam {seam:+.3f} (never traded)", fontsize=7, color="#666", va="bottom")
        ax.axhline(ANCHOR, color="#999", lw=0.6, ls=":"); ax.text(adt[0], ANCHOR, " anchor 3.132 (NGJ26)", fontsize=8, color="#666", va="bottom")
        ax.set_title(f"NG G15 MBO {label} vs actual - Sun 2026-03-15 .. Fri 2026-03-27  (two-leg basis, 5-specialist posterior refine)", fontsize=10, fontweight="bold")
        ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=7); plt.tight_layout()
        plt.savefig(os.path.join(OUT, f"g15_mbo_{tag}_continuous.png"), dpi=120, bbox_inches="tight")
        print(f"wrote g15_mbo_{tag}_continuous.png")

    cmp = json.load(open(os.path.join(OUT, "g15_mbo_comparison.json")))
    print(f"\nSCORE: blind dir {cmp['blind_dir']}/{cmp['n']} (mean abs err {cmp['blind_mean_abs_err']}) | refined dir {cmp['refined_dir']}/{cmp['n']} (mean abs err {cmp['refined_mean_abs_err']})")
    print(f"{'day':9} own {'actual':>7} {'blind':>7} {'b_err':>6} {'refined':>7} {'r_err':>6}")
    for s in score:
        print(f"{s['date']} {s['owner']}   {s['actual_day_move']:+7} {s['blind_day_move']:+7} {s['blind_err']:+6} {s['refined_day_move']:+7} {s['refined_err']:+6}")


if __name__ == "__main__":
    main()
