"""
options_surface.py - FEED I phase i (family DEL/P): NG options OI-by-strike pin map + opex clock (S99).

WHY THIS EXISTS
---------------
Options expire the business day BEFORE futures expiry and drive pinning/unpinning and squeeze
mechanics - plausibly part of G11's February (NGG26 settled 7.460 with the walk's 17x residual day
inside opex week). G13 (Feb 15-27) is the designed SQUEEZE TEST and carries opex Feb 24 / futures
expiry Feb 25: running it without the options view repeats the G11 pattern of testing a family the
agent cannot see. Phase i = the pin map: per-strike open interest for the nearest option months,
top-OI walls, P/C totals, opex clock. Phase ii (settle-implied IV/skew) is post-gate.

SUBSTRATE (landed 2026-07-20, $4.67, S3 options_ng/): GLBX.MDP3 definition + statistics for BOTH
NG options roots - ON (American) and LNE (European) - parent-symbology pulls, 2025-11-01 ->
2026-03-01. Measured record facts: strike_price/settlement price at 1e9 fixed point; statistics
stat_type 3 = SETTLEMENT (price), 9 = OPEN INTEREST (quantity), session date in ts_ref (ns);
INT64_MAX/UINT64_MAX are null sentinels; definitions repeat per session (dedupe by instrument_id);
underlying field names the future (e.g. NGQ26). Quality warnings on the pull: 2025-11-28 degraded
(post-Thanksgiving half day), Saturdays missing - both benign, named.

BLIND WALL: CME publishes settlement/OI next-morning - the same rule as the futures OI join
(DATA_GATE feed I spec). asof(iso) therefore serves the latest SESSION STRICTLY BEFORE iso.

ASSETS ARE SPLIT IN THE STORE, COMBINED IN THE READ: ON and LNE are distinct products on the same
future; the pin/wall read sums them per strike, and per-asset totals + per-asset opex dates ride
alongside (they can differ; nothing is averaged away). The read does NOT reach into other modules:
distance-from-settle is left to the agent (contract_structure carries the settle).

STORE: data/options_ng/surface.json.gz. No commits by this module; S3 push is the orchestrator's
step (prefix options_ng/).

USAGE
-----
  python research/kalshi/options_surface.py --build
  python research/kalshi/options_surface.py --selftest
  python research/kalshi/options_surface.py --show 2026-01-27
"""

from __future__ import annotations

import argparse
import datetime
import glob
import gzip
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(_ROOT, "data", "options_ng", "raw")
STORE_PATH = os.path.join(_ROOT, "data", "options_ng", "surface.json.gz")

I64_NULL = 9223372036854775807
U64_NULL = 18446744073709551615
STAT_SETTLEMENT = 3
STAT_OPEN_INTEREST = 9


def _ns_to_date(ns: int) -> str:
    return datetime.datetime.fromtimestamp(ns / 1e9, tz=datetime.timezone.utc).date().isoformat()


def _strike_on_scale(asset: str, k: float) -> float:
    """Root-conditional strike scale (G-14). ON decodes correctly; LNE decodes at 1/10."""
    try:
        from options_iv_surface import LNE_STRIKE_SCALE as _S
    except Exception:
        _S = 10.0            # the measured value; the import is preferred so there is ONE source
    return k * _S if (asset or "").upper().startswith("LNE") else k


def _def_period(path: str) -> str:
    """Pull-window START date ('YYYY-MM-DD') from a raw filename like
    glbx_ng_opt_definition_20251101_20260301.dbn.zst. '' when the name carries no window
    (then the file simply sorts first and acts as the base period)."""
    import re
    m = re.findall(r"(\d{8})", os.path.basename(path))
    return f"{m[0][:4]}-{m[0][4:6]}-{m[0][6:]}" if m else ""


def build() -> dict:
    import databento as db
    # S102 MERGE FIX (measured): CME REUSES instrument_ids across periods - 2 iids in the winter
    # defs (Nov 1 - Mar 1) are REDEFINED as different contracts in the live-era bridge defs
    # (Mar 1 - Jul 20). A single global {iid: def} dict silently mis-decodes the earlier period's
    # statistics under the later definition. Definitions are therefore kept PER PULL PERIOD and a
    # statistics record resolves against the period covering ITS OWN session date.
    periods: list[tuple[str, dict[int, dict]]] = []   # (period_start_iso, {iid: def}) sorted
    # S114: RECURSIVE. The raw tree grew a subdirectory (raw/ext_2026/) when the surface was
    # extended past March 2026, and this non-recursive glob silently stopped seeing it - a rebuild
    # then produced 81 sessions where the store had 180, dropping exactly the Mar-Jul 2026 window
    # the current groups sit in. Same hand-maintained-list failure as A-29/A-16: correct data on
    # disk, never read.
    dpath = sorted(glob.glob(os.path.join(RAW_DIR, "**", "*definition*.dbn.zst"), recursive=True))
    for p in dpath:
        start = _def_period(p)
        defs: dict[int, dict] = {}
        for rec in db.DBNStore.from_file(p):
            cls = str(getattr(rec, "instrument_class", ""))
            if cls not in ("InstrumentClass.CALL", "InstrumentClass.PUT", "C", "P"):
                continue
            _asset = (rec.asset or "").strip()
            defs[rec.instrument_id] = {
                "underlying": (rec.underlying or "").strip(),
                "asset": _asset,
                # S114 (G-14): DECODE THE STRIKE ON THE RIGHT SCALE. Databento's confirmed bug
                # (reported 2024-06-12) decodes an OPTION's strike with the OPTION's display_factor
                # instead of the underlying FUTURE's, so LNE strikes land at 1/10 of $/MMBtu. That
                # was MEASURED and cured in options_iv_surface.py at S100.1 (LNE_STRIKE_SCALE=10,
                # verified per build by matched-pair pricing) and this module - the one that feeds
                # the decision state - never got the fix, which is why state_health rejected a fresh
                # g22 stage on all ten days: "median top-OI strike 0.35 vs calendar_front_settle
                # 3.233 (ratio 0.108)". Import the constant rather than re-declaring it; one store,
                # one number.
                "strike": _strike_on_scale(_asset, rec.strike_price / 1e9),
                "cp": "C" if cls.endswith("CALL") or cls == "C" else "P",
                "opex": _ns_to_date(rec.expiration),
            }
        periods.append((start, defs))
    periods.sort(key=lambda t: t[0])
    n_defs = len({i for _, d in periods for i in d})
    print(f"[options_surface] definitions: {n_defs} option instruments from {len(dpath)} files "
          f"({len(periods)} period(s): {[s or 'base' for s, _ in periods]})")

    def _resolve(iid: int, sess: str) -> dict | None:
        """The def in force for `sess`: the LAST period starting on/before sess that knows the iid;
        falls back to any period that knows it (an iid can outlive its defining period's window)."""
        hit = None
        for start, defs in periods:
            if start <= sess and iid in defs:
                hit = defs[iid]
        if hit is None:
            for _, defs in periods:
                if iid in defs:
                    return defs[iid]
        return hit

    # sessions[date][asset][month][strike] = [call_oi, put_oi, call_settle, put_settle]
    sessions: dict = {}
    n_oi = n_set = 0
    for p in sorted(glob.glob(os.path.join(RAW_DIR, "**", "*statistics*.dbn.zst"), recursive=True)):
        for rec in db.DBNStore.from_file(p):
            st = int(rec.stat_type)
            if st not in (STAT_SETTLEMENT, STAT_OPEN_INTEREST):
                continue
            if rec.ts_ref == U64_NULL:
                continue
            sess = _ns_to_date(rec.ts_ref)
            d = _resolve(rec.instrument_id, sess)
            if d is None:
                continue
            cell = (sessions.setdefault(sess, {}).setdefault(d["asset"], {})
                    .setdefault(d["underlying"], {}).setdefault(f"{d['strike']:.4f}", [None, None, None, None]))
            idx = 0 if d["cp"] == "C" else 1
            if st == STAT_OPEN_INTEREST and rec.quantity != I64_NULL and rec.quantity >= 0:
                cell[idx] = int(rec.quantity); n_oi += 1
            elif st == STAT_SETTLEMENT and rec.price != I64_NULL:
                cell[2 + idx] = rec.price / 1e9; n_set += 1
    opex_by_asset_month: dict = {}
    for _, defs in periods:                     # earliest period first: first-seen opex wins,
        for d in defs.values():                 # matching the original single-pull behaviour
            opex_by_asset_month.setdefault(d["asset"], {}).setdefault(d["underlying"], d["opex"])
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    store = {
        "meta": {
            "built_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            # S102: computed from the decoded sessions (was the hardcoded phase-i pull range;
            # the raw dir now also carries the live-era bridge, Mar 1 - Jul 20 2026)
            "range": (f"{min(sessions)}..{max(sessions)}" if sessions else None),
            "assets": sorted(opex_by_asset_month),
            "n_sessions": len(sessions), "n_oi_points": n_oi, "n_settle_points": n_set,
            "wall": "CME next-morning publication; asof serves latest session STRICTLY before iso",
        },
        "opex": opex_by_asset_month,
        "sessions": sessions,
    }
    with gzip.open(STORE_PATH, "wt", encoding="utf-8") as f:
        json.dump(store, f)
    print(f"[options_surface] store: {len(sessions)} sessions, {n_oi} OI pts, {n_set} settle pts "
          f"-> {os.path.relpath(STORE_PATH, _ROOT)}")
    return store


_CACHE: dict | None = None


def load_store() -> dict | None:
    global _CACHE
    if _CACHE is None and os.path.exists(STORE_PATH):
        with gzip.open(STORE_PATH, "rt", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def _month_view(sess_data: dict, month: str) -> dict | None:
    """Combine ON+LNE per strike for one underlying month; per-asset totals kept."""
    strikes: dict[str, dict] = {}
    per_asset = {}
    for asset, months in sess_data.items():
        md = months.get(month)
        if not md:
            continue
        a_c = a_p = 0
        for k, (c_oi, p_oi, _cs, _ps) in md.items():
            s = strikes.setdefault(k, {"call_oi": 0, "put_oi": 0})
            if c_oi: s["call_oi"] += c_oi; a_c += c_oi
            if p_oi: s["put_oi"] += p_oi; a_p += p_oi
        per_asset[asset] = {"call_oi": a_c, "put_oi": a_p}
    if not strikes:
        return None
    tot_c = sum(s["call_oi"] for s in strikes.values())
    tot_p = sum(s["put_oi"] for s in strikes.values())
    tot = tot_c + tot_p
    ranked = sorted(strikes.items(), key=lambda kv: kv[1]["call_oi"] + kv[1]["put_oi"], reverse=True)
    top5 = [{"strike": float(k), "call_oi": v["call_oi"], "put_oi": v["put_oi"],
             "share_of_month_oi": round((v["call_oi"] + v["put_oi"]) / tot, 4) if tot else None}
            for k, v in ranked[:5]]
    oiw = (sum(float(k) * (v["call_oi"] + v["put_oi"]) for k, v in strikes.items()) / tot) if tot else None
    return {"total_call_oi": tot_c, "total_put_oi": tot_p,
            "put_call_oi_ratio": round(tot_p / tot_c, 3) if tot_c else None,
            "n_strikes": len(strikes), "top5_oi_strikes": top5,
            "oi_weighted_strike": round(oiw, 4) if oiw else None,
            "per_asset_totals": per_asset}


def options_surface_asof(iso: str, root: str = "NG") -> dict | None:
    """Pin map from the latest session STRICTLY BEFORE iso (CME next-morning wall): the two
    nearest option months not yet past opex, each with top-5 OI walls, P/C totals, OI-weighted
    strike, per-asset splits, and the opex clock. None outside coverage."""
    store = load_store()
    if not store:
        return None
    prior = [s for s in store["sessions"] if s < iso]
    if not prior:
        return None
    sess = max(prior)
    sd = store["sessions"][sess]
    # month -> earliest opex across assets (they can differ; earliest governs the pin clock)
    opex_all: dict[str, str] = {}
    for asset, months in store["opex"].items():
        for m, ox in months.items():
            if m.startswith(root) and (m not in opex_all or ox < opex_all[m]):
                opex_all[m] = ox
    live = sorted(((ox, m) for m, ox in opex_all.items() if ox >= iso))
    months_out = []
    for ox, m in live[:2]:
        view = _month_view(sd, m)
        if view is None:
            continue
        per_asset_opex = {a: mm.get(m) for a, mm in store["opex"].items() if m in mm}
        months_out.append({"month": m, "opex_date": ox,
                           "days_to_opex": (datetime.date.fromisoformat(ox) - datetime.date.fromisoformat(iso)).days,
                           "per_asset_opex": per_asset_opex, **view})
    if not months_out:
        return None
    return {"asof_session": sess, "months": months_out,
            # S114 (G-14): a value that was wrong and is now right must SAY so - the
            # session_b_share_basis pattern. Without this, a state built before the fix and one
            # built after are indistinguishable downstream, which is how a 10x scale error survived
            # from S100.1 to S114 in the block that feeds every specialist.
            "strike_units": "usd_per_mmbtu",
            "strike_units_basis": ("LNE strikes are decoded at 1/10 by Databento (confirmed vendor "
                                   "bug, reported 2024-06-12: the OPTION's display_factor is used "
                                   "instead of the underlying FUTURE's) and are multiplied by "
                                   "LNE_STRIKE_SCALE=10 here, imported from options_iv_surface where "
                                   "the scale is verified per build by matched-pair pricing. ON "
                                   "strikes decode correctly and are untouched. States built before "
                                   "S114 carry LNE strikes 10x too small and NO strike_units key."),
            "note": "OI walls = pin/unpin structure; distance-from-settle is the agent's read "
                    "against contract_structure's calendar-front settle; ON+LNE combined per "
                    "strike, per-asset totals and opex kept split; next-morning wall"}


def _t(cond, msg, fails):
    print(("  PASS " if cond else "  FAIL ") + msg)
    return fails + (0 if cond else 1)


def _selftest() -> int:
    print("=== options_surface --selftest ===")
    fails = 0
    store = load_store()
    fails = _t(store is not None, "store present", fails)
    if store is None:
        return 1
    fails = _t(store["meta"]["n_sessions"] >= 75, f"sessions {store['meta']['n_sessions']} (Nov-Feb)", fails)
    fails = _t(set(store["meta"]["assets"]) >= {"ON", "LNE"}, f"both roots present {store['meta']['assets']}", fails)
    # opex anchors vs the flow calendar's verified dates: NGG26 opex 2026-01-27, NGH26 2026-02-24
    on = store["opex"].get("ON", {})
    fails = _t(on.get("NGG26") == "2026-01-27", f"ON NGG26 opex {on.get('NGG26')} (flow-calendar verified 2026-01-27)", fails)
    fails = _t(on.get("NGH26") == "2026-02-24", f"ON NGH26 opex {on.get('NGH26')} (G13 opex 2026-02-24)", fails)
    # the squeeze-eve read: on 2026-01-27 the agent sees the 01-26 session, front month NGG26,
    # 1 day to opex, with a populated pin map
    a = options_surface_asof("2026-01-27")
    fails = _t(a is not None and a["asof_session"] == "2026-01-26", f"asof 2026-01-27 session {a and a['asof_session']}", fails)
    if a:
        m0 = a["months"][0]
        fails = _t(m0["month"] == "NGG26" and m0["days_to_opex"] == 0,
                   f"front option month {m0['month']} days_to_opex {m0['days_to_opex']} (opex day itself)", fails)
        fails = _t(m0["total_call_oi"] > 0 and m0["total_put_oi"] > 0 and len(m0["top5_oi_strikes"]) == 5,
                   f"pin map populated (C {m0['total_call_oi']} / P {m0['total_put_oi']}, top5 present)", fails)
        fails = _t(len(a["months"]) == 2, f"two live months exposed ({[m['month'] for m in a['months']]})", fails)
    # after G-opex the front month rolls to H
    b = options_surface_asof("2026-01-29")
    fails = _t(b is not None and b["months"][0]["month"] == "NGH26",
               f"post-opex front month {b and b['months'][0]['month']} (expect NGH26)", fails)
    # blind wall: session strictly prior on every walked trade day in coverage
    d = datetime.date(2025, 11, 4)
    bad = 0
    while d <= datetime.date(2026, 2, 27):
        if d.weekday() < 5 or d.weekday() == 6:
            r = options_surface_asof(d.isoformat())
            if r is not None and not (r["asof_session"] < d.isoformat()):
                bad += 1
        d += datetime.timedelta(days=1)
    fails = _t(bad == 0, f"blind-wall walk: {bad} violations (expect 0)", fails)
    print(f"=== selftest {'PASS' if fails == 0 else f'FAIL ({fails})'} ===")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="NG options OI pin map, feed I phase i")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show", metavar="DATE")
    a = ap.parse_args()
    if a.build:
        build()
        return 0
    if a.selftest:
        return _selftest()
    if a.show:
        print(json.dumps(options_surface_asof(a.show), indent=1))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
