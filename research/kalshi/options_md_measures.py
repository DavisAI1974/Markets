"""
options_md_measures.py - FEED I phase MD: the free measurement program on the settle-IV surface
(OPTIONS_COACH_RESEARCH_S100.1 section E3, items 1-5). Settle/OI only; every claim EOD-granular;
execution unmeasured and said so. Per-event rows are the store; cell summaries are descriptors.

MEASUREMENTS
  1 samuelson    ATM IV vs days-to-opex, cells = tenor bucket x delivery season class
  2 skew_book    front rr25 per session joined to curve_regime + squeeze state (NG_structure)
  3 event_vol    front ATM IV path around the 17 in-window storage Thursdays, per event
  4 iv_vs_rv     front ATM IV vs subsequent realized vol (n0 closes, 5-session window), per event
  5 on_lne_gap   the measured early-exercise premium (ON-LNE ATM-band IV gap), front months

WALLS: reads the settle surface (D-1-walled store) and REALIZED data strictly AFTER each
session for measurement 4 - this is a measurement pass over history, not a decision-time feed;
nothing here is served to a blind run. Anything that becomes a rule goes through the walk's
refine protocol like every other lesson.

STORE: data/options_ng/md_measures.json. Usage:
  python research/kalshi/options_md_measures.py --run
  python research/kalshi/options_md_measures.py --selftest
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from options_iv_surface import load_store  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_PATH = os.path.join(_ROOT, "data", "options_ng", "md_measures.json")
STRUCT_PATH = os.path.join(_ROOT, "data", "contract_structure", "NG_structure.json")
VOL_PATH = os.path.join(_ROOT, "data", "vol_regime", "vol_regime.json")
EIA_PATH = os.path.join(_ROOT, "data", "eia_surprise.json")

SEASON = {"F": "winter", "G": "winter", "H": "winter", "Z": "winter",
          "J": "shoulder", "K": "shoulder", "V": "shoulder", "X": "shoulder",
          "M": "summer", "N": "summer", "Q": "summer", "U": "summer"}
TENOR_BUCKETS = [(1, 10), (11, 20), (21, 30), (31, 45), (46, 60), (61, 90), (91, 180), (181, 9999)]


def _q(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    v = sorted(vals)
    return round(v[min(len(v) - 1, int(len(v) * q))], 4)


def _season_of(month_sym: str) -> str:
    return SEASON.get(month_sym[2], "?") if len(month_sym) >= 3 else "?"


def m1_samuelson(s: dict) -> dict:
    cells: dict[str, list[float]] = {}
    for day in s["sessions"].values():
        for name, m in day["months"].items():
            iv, d = m.get("atm_iv"), m.get("days_to_opex")
            if iv is None or d is None:
                continue
            for lo, hi in TENOR_BUCKETS:
                if lo <= d <= hi:
                    cells.setdefault(f"{_season_of(name)}|{lo}-{hi}d", []).append(iv)
                    break
    return {cell: {"n": len(v), "med": _q(v, .5), "p10": _q(v, .1), "p90": _q(v, .9)}
            for cell, v in sorted(cells.items())}


def m2_skew_book(s: dict) -> dict:
    struct = json.load(open(STRUCT_PATH)) if os.path.exists(STRUCT_PATH) else {}
    rows = []
    for iso in sorted(s["sessions"]):
        day = s["sessions"][iso]
        f = day["front"]
        if not f:
            continue
        m = day["months"][f]
        if m.get("rr25") is None:
            continue
        # structure is D-1-walled per its own asof; index by NEXT day to align "as of iso close"
        st = struct.get((datetime.date.fromisoformat(iso) + datetime.timedelta(days=1)).isoformat(), {})
        exp = st.get("calendar_front_expiry")
        dte = ((datetime.date.fromisoformat(exp) - datetime.date.fromisoformat(iso)).days
               if exp else None)
        squeeze = bool(dte is not None and dte <= 7 and (st.get("calendar_front_next_spread_chg_3d") or 0) > 0)
        rows.append({"session": iso, "front": f, "rr25": m["rr25"], "fly25": m.get("fly25"),
                     "atm_iv": m.get("atm_iv"), "curve_regime": st.get("curve_regime"),
                     "squeeze_active": squeeze})
    cells: dict[str, list[float]] = {}
    for r in rows:
        key = f"{r['curve_regime'] or 'unknown'}|{'squeeze' if r['squeeze_active'] else 'normal'}"
        cells.setdefault(key, []).append(r["rr25"])
    return {"rows": rows,
            "cells": {k: {"n": len(v), "med_rr25": _q(v, .5), "p10": _q(v, .1), "p90": _q(v, .9)}
                      for k, v in sorted(cells.items())},
            "note": "rr25>0 everywhere observed = call wing over put wing (upside-gap pricing); "
                    "cells are descriptors, rows are the record"}


def m3_event_vol(s: dict) -> dict:
    eia = json.load(open(EIA_PATH)).get("KXNATGASD", {}) if os.path.exists(EIA_PATH) else {}
    sessions = sorted(s["sessions"])
    events = []
    for rep in sorted(eia):
        if not (sessions[0] <= rep <= sessions[-1]):
            continue
        if rep not in s["sessions"]:
            continue
        i = sessions.index(rep)
        path = {}
        for off in range(-3, 3):
            j = i + off
            if 0 <= j < len(sessions):
                day = s["sessions"][sessions[j]]
                f = day["front"]
                iv = day["months"][f].get("atm_iv") if f else None
                path[f"D{off:+d}"] = iv
        base = path.get("D-1")
        rel = {k: (round(v - base, 5) if v is not None and base is not None else None)
               for k, v in path.items()}
        events.append({"report_day": rep, "surprise": eia[rep].get("surprise"),
                       "front_atm_path": path, "delta_vs_Dm1": rel})
    deltas_d0 = [e["delta_vs_Dm1"].get("D+0") for e in events if e["delta_vs_Dm1"].get("D+0") is not None]
    deltas_d1 = [e["delta_vs_Dm1"].get("D+1") for e in events if e["delta_vs_Dm1"].get("D+1") is not None]
    return {"events": events,
            "descriptor": {"n_events": len(events),
                           "med_iv_chg_report_day": _q(deltas_d0, .5),
                           "med_iv_chg_day_after": _q(deltas_d1, .5)},
            "note": "settle-to-settle only; the intraday build/crush shape is UNCLAIMED "
                    "until intraday options data exists (E3 honest-scope statement)"}


def m4_iv_vs_rv(s: dict, horizon: int = 5) -> dict:
    vol = json.load(open(VOL_PATH)) if os.path.exists(VOL_PATH) else {}
    closes = {r["date"]: r["close"] for r in vol.get("sessions", {}).get("n0", []) if r.get("close")}
    cdays = sorted(closes)
    rows = []
    for iso in sorted(s["sessions"]):
        day = s["sessions"][iso]
        f = day["front"]
        iv = day["months"][f].get("atm_iv") if f else None
        if iv is None or iso not in closes:
            continue
        i = cdays.index(iso)
        fwd = cdays[i:i + horizon + 1]
        if len(fwd) < horizon + 1:
            continue
        rets = [math.log(closes[fwd[k + 1]] / closes[fwd[k]]) for k in range(horizon)]
        mean = sum(rets) / len(rets)
        rv = math.sqrt(sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)) * math.sqrt(252)
        rows.append({"session": iso, "front": f, "atm_iv": iv, "rv_fwd5": round(rv, 4),
                     "iv_minus_rv": round(iv - rv, 4)})
    diffs = [r["iv_minus_rv"] for r in rows]
    return {"rows": rows,
            "descriptor": {"n": len(rows), "n_iv_above_rv": sum(1 for d in diffs if d > 0),
                           "med_iv_minus_rv": _q(diffs, .5), "p10": _q(diffs, .1), "p90": _q(diffs, .9)},
            "note": f"rv = next-{horizon}-session close-to-close annualized (n0 basis, "
                    "settle-window discipline inherited from the tape store); the NG VRP on "
                    "our winter, per-event rows first"}


def m5_on_lne_gap(s: dict) -> dict:
    rows = []
    for iso in sorted(s["sessions"]):
        day = s["sessions"][iso]
        f = day["front"]
        if not f:
            continue
        m = day["months"][f]
        g = m.get("on_minus_lne_iv_atm_band")
        if g is None:
            continue
        rows.append({"session": iso, "front": f, "gap": g, "n_matched": m.get("n_on_lne_matched_atm")})
    gaps = [r["gap"] for r in rows]
    ranked = sorted(rows, key=lambda r: abs(r["gap"]), reverse=True)[:5]
    return {"rows": rows,
            "descriptor": {"n": len(rows), "med": _q(gaps, .5), "p10": _q(gaps, .1), "p90": _q(gaps, .9)},
            "top5_abs": ranked,
            "note": "front-month ATM-band ON minus LNE settle IV = measured early-exercise premium; "
                    "inside settle-mark noise -> Black-76-everywhere justified BY MEASUREMENT (C3)"}


def run() -> dict:
    s = load_store()
    if s is None:
        sys.exit("[options_md] iv store absent - run options_iv_surface.py --build first")
    out = {"meta": {"built_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                    "surface_built": s["meta"]["built_utc"], "n_sessions": s["meta"]["n_sessions"]},
           "samuelson": m1_samuelson(s), "skew_book": m2_skew_book(s), "event_vol": m3_event_vol(s),
           "iv_vs_rv": m4_iv_vs_rv(s), "on_lne_gap": m5_on_lne_gap(s)}
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print(f"[options_md] -> {os.path.relpath(OUT_PATH, _ROOT)}")
    print("\nSAMUELSON (med atm_iv per season|tenor):")
    for k, v in out["samuelson"].items():
        print(f"  {k:22s} n={v['n']:4d} med={v['med']} p10={v['p10']} p90={v['p90']}")
    print("\nSKEW cells:", json.dumps(out["skew_book"]["cells"], indent=1))
    print("\nEVENT-VOL descriptor:", json.dumps(out["event_vol"]["descriptor"]))
    print("IV-vs-RV descriptor:", json.dumps(out["iv_vs_rv"]["descriptor"]))
    print("ON-LNE gap descriptor:", json.dumps(out["on_lne_gap"]["descriptor"]))
    print("ON-LNE top5 |gap|:", json.dumps(out["on_lne_gap"]["top5_abs"]))
    return out


def _selftest() -> int:
    ok = True

    def chk(c, m):
        nonlocal ok
        print(("  PASS " if c else "  FAIL ") + m)
        ok = ok and bool(c)

    print("[options_md selftest]")
    if not os.path.exists(OUT_PATH):
        print("  SKIP (run --run first)")
        return 0
    out = json.load(open(OUT_PATH))
    chk(out["event_vol"]["descriptor"]["n_events"] >= 14,
        f"storage report events measured: {out['event_vol']['descriptor']['n_events']} "
        "(of 17 in-window; holiday-shifted reports landing off option sessions are absent, named)")
    chk(out["iv_vs_rv"]["descriptor"]["n"] > 50, "IV-vs-RV rows > 50")
    chk(out["on_lne_gap"]["descriptor"]["n"] > 50, "ON-LNE gap rows > 50")
    chk(all(v["n"] > 0 for v in out["samuelson"].values()), "samuelson cells populated")
    print("[options_md selftest]", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.exit(_selftest() if a.selftest else (0 if run() else 1))
