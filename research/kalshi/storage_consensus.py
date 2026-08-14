"""
storage_consensus.py -- weekly EIA natural gas storage analyst consensus as a decision-state input.

The store carries archived and forward point-in-time survey evidence.  The serving rule is stricter
than the storage record itself: an UPCOMING print may expose only consensus evidence that was actually
captured before the decision-day open.  A later capture can prove history after the fact, but it cannot
travel backward into an earlier blind slice.

Decision-time convention matches the walk's weekday-open state: 08:00 America/New_York on D.
For next_print, estimates/capture metadata at or after that cutoff are withheld.  Missing stays None;
there is no interpolation, seasonal stand-in, or synthetic earlier vintage.  last_print is strictly
before D and may carry realized actual/surprise fields.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
_STORE_DIRS = [os.path.join(_HERE, "..", "..", "data", "storage_consensus"),
               os.path.join("data", "storage_consensus")]
STORE_NAME = "storage_consensus.json"
_SURPRISE_PATHS = [os.path.join(_HERE, "..", "..", "data", "eia_surprise.json"),
                   os.path.join("data", "eia_surprise.json")]
_ET = ZoneInfo("America/New_York")
_DECISION_OPEN_HOUR_ET = 8

SCHEDULE_EXCEPTIONS = {
    "2025-11-14": ("Fri", "10:30"),
    "2025-11-26": ("Wed", "12:00"),
    "2025-12-29": ("Mon", "12:00"),
    "2025-12-31": ("Wed", "12:00"),
}

_CACHE = {"store": None, "surprise": None}


def _find_store():
    for d in _STORE_DIRS:
        p = os.path.join(d, STORE_NAME)
        if os.path.exists(p):
            return p
    return None


def _load_store():
    if _CACHE["store"] is None:
        p = _find_store()
        if p is None:
            return None
        with open(p) as f:
            _CACHE["store"] = json.load(f)
    return _CACHE["store"]


def _load_surprise_actuals():
    if _CACHE["surprise"] is None:
        for p in _SURPRISE_PATHS:
            if os.path.exists(p):
                with open(p) as f:
                    ng = json.load(f).get("KXNATGASD", {})
                _CACHE["surprise"] = {k: v.get("actual") for k, v in ng.items()}
                break
        else:
            _CACHE["surprise"] = {}
    return _CACHE["surprise"]


def _as_date(d):
    if isinstance(d, dt.datetime):
        return d.date()
    if isinstance(d, dt.date):
        return d
    return dt.date.fromisoformat(str(d)[:10])


def _snapshot_utc(value):
    """Parse the store's ISO/compact/date-only provenance stamps as aware UTC datetimes."""
    if not value:
        return None
    s = str(value).strip()
    try:
        if len(s) == 14 and s.isdigit():
            return dt.datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)
        if "T" not in s:
            return dt.datetime.fromisoformat(s + "T00:00:00+00:00")
        parsed = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _decision_cutoff_utc(D: dt.date) -> dt.datetime:
    local = dt.datetime.combine(D, dt.time(_DECISION_OPEN_HOUR_ET, 0), tzinfo=_ET)
    return local.astimezone(dt.timezone.utc)


def _visible_snapshot(value, D: dt.date) -> bool:
    snap = _snapshot_utc(value)
    return snap is not None and snap < _decision_cutoff_utc(D)


_CONSENSUS_KEYS = [
    "for_report_date", "print_date", "print_dow", "print_time_et", "print_datetime_utc",
    "print_schedule_note", "consensus_chg_bcf", "source", "consensus_pre_print_bcf",
    "consensus_pre_print_snapshot_utc", "n_estimates", "range_low_bcf", "range_high_bcf",
    "house_disagreement_bcf",
]
_STATIC_NEXT_KEYS = [
    "for_report_date", "print_date", "print_dow", "print_time_et", "print_datetime_utc",
    "print_schedule_note",
]


def _clean_estimate(e):
    return {k: v for k, v in e.items() if k != "actual_on_page_bcf"}


def _next_print_view(rec, D):
    """Upcoming-print view using only evidence actually visible by the decision-day open."""
    out = {k: rec.get(k) for k in _STATIC_NEXT_KEYS}
    out["days_to_print"] = (dt.date.fromisoformat(rec["print_date"]) - D).days

    legal_est = []
    for e in rec.get("estimates", []):
        if e.get("pre_print") is True and _visible_snapshot(e.get("snapshot_utc"), D):
            legal_est.append(_clean_estimate(e))

    pre_val = rec.get("consensus_pre_print_bcf")
    pre_ts = rec.get("consensus_pre_print_snapshot_utc")
    legal_pre = pre_val if pre_val is not None and _visible_snapshot(pre_ts, D) else None

    headline = rec.get("consensus_chg_bcf")
    chosen = None
    chosen_source = None
    chosen_ts = None

    # Preserve the archived primary headline only when a decision-time-visible source supports it.
    if headline is not None:
        for e in legal_est:
            v = e.get("value_bcf")
            if isinstance(v, (int, float)) and abs(float(v) - float(headline)) < 1e-9:
                chosen = float(headline)
                chosen_source = rec.get("source") or e.get("source")
                chosen_ts = e.get("snapshot_utc")
                break
        if chosen is None and legal_pre is not None and abs(float(legal_pre) - float(headline)) < 1e-9:
            chosen = float(headline)
            chosen_source = rec.get("source")
            chosen_ts = pre_ts

    # If the final headline is not yet evidenced at the cutoff, a strictly pre-print captured value
    # may still be served.  It is carried as that captured value, never silently promoted to a later one.
    if chosen is None and legal_pre is not None:
        chosen = float(legal_pre)
        chosen_ts = pre_ts
        for e in legal_est:
            v = e.get("value_bcf")
            if isinstance(v, (int, float)) and abs(float(v) - chosen) < 1e-9:
                chosen_source = e.get("source")
                chosen_ts = e.get("snapshot_utc") or chosen_ts
                break
        chosen_source = chosen_source or "strictly_pre_print_snapshot"

    # A single visible source is usable even if the store's later frozen headline came from another
    # house.  With multiple conflicting visible sources and no primary/pre-print pin, remain unknown.
    if chosen is None and len(legal_est) == 1 and isinstance(legal_est[0].get("value_bcf"), (int, float)):
        chosen = float(legal_est[0]["value_bcf"])
        chosen_source = legal_est[0].get("source")
        chosen_ts = legal_est[0].get("snapshot_utc")

    vals = [float(e["value_bcf"]) for e in legal_est if isinstance(e.get("value_bcf"), (int, float))]
    out["consensus_chg_bcf"] = chosen
    out["source"] = chosen_source
    out["final_capture_is_post_print"] = False if chosen is not None else None
    out["consensus_pre_print_bcf"] = chosen
    out["consensus_pre_print_snapshot_utc"] = chosen_ts
    out["n_estimates"] = len(vals) if vals else None
    out["range_low_bcf"] = None
    out["range_high_bcf"] = None
    out["house_disagreement_bcf"] = (round(max(vals) - min(vals), 3) if len(vals) >= 2 else None)
    out["estimates"] = legal_est

    for k in out:
        assert not any(s in k for s in ("actual", "surprise", "vintage")), \
            f"blind wall: forbidden key {k} in next_print view"
    cutoff = _decision_cutoff_utc(D)
    if out.get("consensus_pre_print_snapshot_utc"):
        snap = _snapshot_utc(out["consensus_pre_print_snapshot_utc"])
        assert snap is not None and snap < cutoff, \
            f"blind wall: next_print snapshot {snap} not before decision cutoff {cutoff}"
    for e in legal_est:
        assert "actual_on_page_bcf" not in e, "blind wall: page actual leaked into next_print"
        snap = _snapshot_utc(e.get("snapshot_utc"))
        assert snap is not None and snap < cutoff, \
            f"blind wall: estimate snapshot {snap} not before decision cutoff {cutoff}"
    return out


def _last_print_view(rec, D, actuals):
    out = {k: rec.get(k) for k in _CONSENSUS_KEYS}
    out["days_since_print"] = (D - dt.date.fromisoformat(rec["print_date"])).days
    cur = actuals.get(rec["nominal_release_date"])
    if cur is None:
        cur = rec.get("actual_current_vintage_bcf")
    printed = rec.get("actual_as_printed_bcf")
    cons = rec.get("consensus_chg_bcf")
    out["actual_current_vintage_bcf"] = cur
    out["actual_as_printed_bcf"] = printed
    out["actual_as_printed_source"] = rec.get("actual_as_printed_source")
    out["vintage_diff_bcf"] = (round(printed - cur, 3)
                               if (printed is not None and cur is not None) else None)
    out["surprise_vs_consensus_bcf"] = (round(cur - cons, 3)
                                        if (cur is not None and cons is not None) else None)
    out["surprise_as_printed_vs_consensus_bcf"] = (round(printed - cons, 3)
                                                   if (printed is not None and cons is not None)
                                                   else None)
    out["estimates"] = rec.get("estimates", [])
    return out


def storage_consensus_asof(date) -> dict | None:
    store = _load_store()
    if not store or not store.get("reports"):
        return None
    D = _as_date(date)
    reports = store["reports"]
    last = None
    nxt = None
    for rec in reports:
        pd_ = dt.date.fromisoformat(rec["print_date"])
        if pd_ < D:
            last = rec
        elif nxt is None:
            nxt = rec
            break
    if last is None and nxt is None:
        return None
    if last is not None:
        assert dt.date.fromisoformat(last["print_date"]) < D, "blind wall: last_print not strictly before D"
    if nxt is not None:
        assert dt.date.fromisoformat(nxt["print_date"]) >= D, "blind wall: next_print before D"
    actuals = _load_surprise_actuals()
    return {
        "as_of": D.isoformat(),
        "next_print": _next_print_view(nxt, D) if nxt is not None else None,
        "last_print": _last_print_view(last, D, actuals) if last is not None else None,
        "source": "storage_consensus_v1",
    }


def selftest() -> bool:
    ok = True
    violations = 0
    store = _load_store()
    if not store:
        print("SELFTEST FAIL: store not found (data/storage_consensus/storage_consensus.json)")
        return False
    reports = store["reports"]

    prev = None
    for rec in reports:
        pd_ = dt.date.fromisoformat(rec["print_date"])
        if prev is not None and not pd_ > prev:
            print(f"  FAIL: print dates not strictly ascending at {rec['print_date']}"); ok = False
        prev = pd_
        nom = dt.date.fromisoformat(rec["nominal_release_date"])
        if nom.weekday() != 3:
            print(f"  FAIL: nominal_release_date not a Thursday: {nom}"); ok = False
        if (nom - dt.timedelta(days=6)).isoformat() != rec["for_report_date"]:
            print(f"  FAIL: for_report_date misaligned at {rec['print_date']}"); ok = False
        exp = SCHEDULE_EXCEPTIONS.get(rec["print_date"])
        if exp is not None:
            if (rec["print_dow"], rec["print_time_et"]) != exp:
                print(f"  FAIL: schedule exception mismatch at {rec['print_date']}"); ok = False
        elif rec["print_dow"] != "Thu" or rec["print_time_et"] != "10:30":
            print(f"  FAIL: non-exception print not Thu 10:30: {rec['print_date']}"); ok = False
        if rec["consensus_chg_bcf"] == 0.0 and not rec.get("estimates"):
            print(f"  FAIL: zero-with-no-source at {rec['print_date']} (placeholder?)"); ok = False

        put = _snapshot_utc(rec.get("print_datetime_utc"))
        for e in rec.get("estimates", []):
            if e.get("pre_print") is True:
                snap = _snapshot_utc(e.get("snapshot_utc"))
                if snap is None:
                    print(f"  FAIL: unparseable snapshot_utc {e.get('snapshot_utc')!r} at {rec['print_date']}")
                    ok = False
                elif put is not None and snap >= put:
                    violations += 1
                    print(f"  VIOLATION: pre_print row captured at/after print {rec['print_date']} "
                          f"({e.get('source')} {e.get('snapshot_utc')})")

    # Sweep through the whole stored period, including the newly recovered forward rows.
    d0 = dt.date(2025, 8, 15)
    d1 = max(dt.date.fromisoformat(r["print_date"]) for r in reports) + dt.timedelta(days=1)
    d = d0
    while d <= d1:
        st = storage_consensus_asof(d)
        if st is not None:
            np_, lp = st["next_print"], st["last_print"]
            if np_ is not None:
                if dt.date.fromisoformat(np_["print_date"]) < d:
                    violations += 1; print(f"  VIOLATION: next_print before D at {d}")
                bad = [k for k in np_ if any(s in k for s in ("actual", "surprise", "vintage"))]
                if bad:
                    violations += 1; print(f"  VIOLATION: actual-shaped keys {bad} in next_print at {d}")
                cutoff = _decision_cutoff_utc(d)
                ts = np_.get("consensus_pre_print_snapshot_utc")
                if ts:
                    snap = _snapshot_utc(ts)
                    if snap is None or snap >= cutoff:
                        violations += 1
                        print(f"  VIOLATION: next_print snapshot {ts} reaches {d} cutoff {cutoff}")
                for e in np_.get("estimates", []):
                    if "actual_on_page_bcf" in e:
                        violations += 1; print(f"  VIOLATION: page actual in next_print estimate at {d}")
                    snap = _snapshot_utc(e.get("snapshot_utc"))
                    if snap is None or snap >= cutoff:
                        violations += 1
                        print(f"  VIOLATION: estimate snapshot {e.get('snapshot_utc')} reaches {d} cutoff {cutoff}")
            if lp is not None and dt.date.fromisoformat(lp["print_date"]) >= d:
                violations += 1; print(f"  VIOLATION: last_print not strictly before D at {d}")
        d += dt.timedelta(days=1)

    st = storage_consensus_asof("2026-01-29")
    if st is None or st["next_print"] is None or st["next_print"]["print_date"] != "2026-01-29":
        print("  FAIL: print-day open must identify its own print as next_print"); ok = False
    if st and st["last_print"] and st["last_print"]["print_date"] != "2026-01-22":
        print("  FAIL: last_print on 2026-01-29 should be 2026-01-22"); ok = False
    st2 = storage_consensus_asof("2025-12-30")
    if not st2 or not st2["last_print"] or st2["last_print"]["print_date"] != "2025-12-29" \
            or not st2["next_print"] or st2["next_print"]["print_date"] != "2025-12-31":
        print("  FAIL: double-print week (Dec 29 / Dec 31) mechanics wrong"); ok = False

    n_pre = sum(1 for r in reports if r.get("consensus_pre_print_bcf") is not None)
    print(f"  store: {len(reports)} reports, consensus {sum(1 for r in reports if r['consensus_chg_bcf'] is not None)}"
          f"/{len(reports)}, strictly-pre-print value {n_pre}/{len(reports)}")
    print(f"  decision cutoff: {_DECISION_OPEN_HOUR_ET:02d}:00 ET; blind-wall violations: {violations}")
    ok = ok and violations == 0
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


def audit():
    store = _load_store()
    if not store:
        print("no store"); return
    print(f"{'print_date':<12}{'dow':<5}{'et':<7}{'report_wk':<12}{'consensus':>10}{'pre_print':>10}"
          f"{'printed':>9}{'cur_vint':>9}  houses / gaps")
    for rec in store["reports"]:
        houses = sorted({e["source"].split(" ")[0] for e in rec.get("estimates", [])
                         if e.get("value_bcf") is not None})
        gaps = []
        if rec["consensus_chg_bcf"] is None:
            gaps.append("NO CONSENSUS OBTAINED")
        if rec["consensus_pre_print_bcf"] is None:
            gaps.append("no strictly-pre-print capture")
        if rec["n_estimates"] is None:
            gaps.append("no n_estimates")
        print(f"{rec['print_date']:<12}{rec['print_dow']:<5}{rec['print_time_et']:<7}"
              f"{rec['for_report_date']:<12}"
              f"{str(rec['consensus_chg_bcf']):>10}{str(rec['consensus_pre_print_bcf']):>10}"
              f"{str(rec['actual_as_printed_bcf']):>9}{str(rec['actual_current_vintage_bcf']):>9}"
              f"  {','.join(houses)}  [{'; '.join(gaps) if gaps else 'ok'}]")


def main():
    ap = argparse.ArgumentParser(description="EIA weekly NG storage analyst consensus (feed D)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--asof", help="print the state visible on a decision day YYYY-MM-DD")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if args.audit:
        audit(); return
    if args.asof:
        print(json.dumps(storage_consensus_asof(args.asof), indent=2)); return
    ap.print_help()


if __name__ == "__main__":
    main()
