"""
storage_consensus.py -- weekly EIA natural gas storage ANALYST CONSENSUS as a decision-state
INPUT (S98, DATA_GATE_S98 feed D).

WHY. The market prices the weekly EIA storage print against the ANALYST SURVEY CONSENSUS, not
against the 5-yr seasonal norm that `eia_surprise.py` proxies. A -80 Bcf draw is a bearish miss
if consensus was -95 even though it looks bullish vs the 5-yr. Concretely: on 2026-01-29 the
print was 15.2 Bcf below the SEASONAL comparison and the market rallied +1480; against the
surveyed consensus the surprise was much smaller (consensus -232 TE / -237 FF / -238 NGI,
printed -242, i.e. -4..-10 Bcf). Which number the market was actually positioned against was
previously unknowable from our data; this feed supplies it. It is an INPUT for the agent to use
as it sees fit -- NOT a thesis on trial: nothing here gates, scores, or argues for/against
using consensus.

ADDITIVE. New standalone module + store. Touches nothing existing; reads
`data/eia_surprise.json` strictly read-only for the realized-actual join.

STORE. data/storage_consensus/storage_consensus.json, built from ARCHIVED point-in-time
sources (Wayback snapshots of TradingEconomics / investing.com mirrors / ForexFactory pages,
plus named news-wire survey mentions), each row carrying the exact snapshot URL and whether the
capture was strictly pre-print. Sources disagree on some weeks (e.g. 2026-01-22: TE -106 vs
FF -90); disagreeing values are CARRIED SIDE BY SIDE, never averaged. Coverage and gaps are
named per week in research/kalshi/STORAGE_CONSENSUS_NOTES_S98.md.

VINTAGE. `actual_as_printed_bcf` (what the market saw at the print, from the archives; mutually
consistent across TE/investing/FF on every overlap) differs from today's EIA API series on many
weeks (mostly 1-3 Bcf; 2025-09-04 differs by 10). Both are carried; feed K owns the full
vintage audit.

BLIND WALL (exact mechanics). The consensus for an UPCOMING print is public BEFORE the print
(analyst surveys publish Tue/Wed), so on a print-day morning the consensus for that day's print
IS available; the print's ACTUAL value is NOT (it lands at the print datetime: Thursday
10:30 ET normally; four in-window holiday shifts per EIA's published schedule -- Fri 2025-11-14
10:30, Wed 2025-11-26 12:00, Mon 2025-12-29 12:00, Wed 2025-12-31 12:00). For a decision day D:
  - next_print (print_date >= D): consensus fields ONLY. No actual, no surprise. Post-print-
    captured per-source rows have the page-displayed actual STRIPPED so a print's own actual
    can never reach its own morning. `final_capture_is_post_print` flags that our EVIDENCE of
    the final frozen consensus is a post-print snapshot (the number itself was public at the
    print; the strictly-pre-print evidence value sits in `consensus_pre_print_bcf`).
  - last_print (print_date < D): consensus + realized actual (current vintage joined read-only
    from data/eia_surprise.json, as-printed from the archives) + the surprises.
Assertions enforce this on every call, and --selftest audits the whole store plus a daily sweep
of the walked window, printing the violation count (must be 0).

MISSING IS EXPLICIT, NEVER ZERO. None = unknown. No interpolation, no seasonal stand-in, zero
synthetic data. A week with no obtainable value stays None and is named in the notes.

PUBLIC INTERFACE (the orchestrator wires this into decision_state serially, later):

    storage_consensus_asof(date) -> dict | None

        date : str "YYYY-MM-DD" | datetime.date  -- the DECISION day D (open-time semantics,
               date resolution, matching forecast_harness._storage_asof's S96 convention).
        returns None if the store is absent/empty or D precedes all records; else
        {
          "as_of": "YYYY-MM-DD",
          "next_print": {            # the upcoming print at-or-after D; None past the store end
             "for_report_date", "print_date", "print_dow", "print_time_et",
             "print_datetime_utc", "print_schedule_note", "days_to_print",
             "consensus_chg_bcf",              # final frozen house consensus (primary source)
             "source",                         # which house/value the headline number is
             "final_capture_is_post_print",    # True: evidence snapshot is post-print
             "consensus_pre_print_bcf",        # value from a STRICTLY pre-print snapshot | None
             "consensus_pre_print_snapshot_utc",
             "n_estimates", "range_low_bcf", "range_high_bcf",   # None throughout (not carried
                                                                 # by any free archived source)
             "house_disagreement_bcf",         # max-min across houses where >=2 exist
             "estimates": [...]                # per-source rows, actual_on_page stripped
          } | None,
          "last_print": {            # most recent print STRICTLY before D; None before store
             ...same consensus fields..., "days_since_print",
             "actual_current_vintage_bcf",     # from data/eia_surprise.json (read-only join)
             "actual_as_printed_bcf",          # from the archives (what the market saw)
             "actual_as_printed_source",
             "vintage_diff_bcf",
             "surprise_vs_consensus_bcf",              # current-vintage actual - consensus
             "surprise_as_printed_vs_consensus_bcf",   # as-printed actual - consensus
             "estimates": [...]                # per-source rows, intact
          } | None,
          "source": "storage_consensus_v1"
        }
        Sign convention: values are net weekly change in Bcf (negative = withdrawal);
        surprise = actual - consensus, so NEGATIVE surprise = bigger draw than expected
        (tighter than consensus). Same orientation as eia_surprise.py.

USAGE
    python research/kalshi/storage_consensus.py --selftest
    python research/kalshi/storage_consensus.py --audit
    python research/kalshi/storage_consensus.py --asof 2026-01-29
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_STORE_DIRS = [os.path.join(_HERE, "..", "..", "data", "storage_consensus"),
               os.path.join("data", "storage_consensus")]
STORE_NAME = "storage_consensus.json"
_SURPRISE_PATHS = [os.path.join(_HERE, "..", "..", "data", "eia_surprise.json"),
                   os.path.join("data", "eia_surprise.json")]

# The four in-window exceptions to the normal Thursday 10:30 ET rule, verbatim from EIA's
# published schedule (https://ir.eia.gov/ngs/schedule.html, fetched 2026-07-20), keyed by
# actual print date. Used by --selftest to re-assert the store's schedule fields.
SCHEDULE_EXCEPTIONS = {
    "2025-11-14": ("Fri", "10:30"),   # Veterans Day observance
    "2025-11-26": ("Wed", "12:00"),   # Thanksgiving Day
    "2025-12-29": ("Mon", "12:00"),   # Christmas Day (EIA 'Updated')
    "2025-12-31": ("Wed", "12:00"),   # New Year's Day
}

_CACHE = {"store": None, "surprise": None}


# --------------------------------------------------------------------------- loading

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
    """{nominal_release_iso: actual} from data/eia_surprise.json (READ-ONLY), or None."""
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


# --------------------------------------------------------------------------- views

_CONSENSUS_KEYS = [
    "for_report_date", "print_date", "print_dow", "print_time_et", "print_datetime_utc",
    "print_schedule_note", "consensus_chg_bcf", "source", "consensus_pre_print_bcf",
    "consensus_pre_print_snapshot_utc", "n_estimates", "range_low_bcf", "range_high_bcf",
    "house_disagreement_bcf",
]


def _next_print_view(rec, D):
    """Blind-safe view of an upcoming print: consensus only, never its actual."""
    out = {k: rec.get(k) for k in _CONSENSUS_KEYS}
    out["days_to_print"] = (dt.date.fromisoformat(rec["print_date"]) - D).days
    out["final_capture_is_post_print"] = True if rec.get("consensus_chg_bcf") is not None else None
    est = []
    for e in rec.get("estimates", []):
        e2 = {k: v for k, v in e.items() if k != "actual_on_page_bcf"}
        est.append(e2)
    out["estimates"] = est
    # blind-wall assertion: nothing actual/surprise/vintage-shaped may appear here
    for k in out:
        assert not any(s in k for s in ("actual", "surprise", "vintage")), \
            f"blind wall: forbidden key {k} in next_print view"
    for e in est:
        assert "actual_on_page_bcf" not in e, "blind wall: page actual leaked into next_print"
    return out


def _last_print_view(rec, D, actuals):
    out = {k: rec.get(k) for k in _CONSENSUS_KEYS}
    out["days_since_print"] = (D - dt.date.fromisoformat(rec["print_date"])).days
    # realized actual: prefer the live read-only eia_surprise join; fall back to the value
    # baked into the store at build time (same series, same vintage question).
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


# --------------------------------------------------------------------------- public

def storage_consensus_asof(date) -> dict | None:
    """Consensus state visible at open-time of decision day `date`. See module docstring."""
    store = _load_store()
    if not store or not store.get("reports"):
        return None
    D = _as_date(date)
    reports = store["reports"]  # build order is print-date ascending; asserted in selftest
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
    # blind-wall assertions (in addition to the structural ones inside the views)
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


# --------------------------------------------------------------------------- selftest / audit

def selftest() -> bool:
    ok = True
    violations = 0
    store = _load_store()
    if not store:
        print("SELFTEST FAIL: store not found (data/storage_consensus/storage_consensus.json)")
        return False
    reports = store["reports"]

    # 1) store-level structure: ascending prints, week-ending alignment, schedule fields
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
        # missing-is-None sanity: a headline value of exactly 0.0 with no source would be a
        # coerced placeholder (a real 0 consensus would still carry its source row)
        if rec["consensus_chg_bcf"] == 0.0 and not rec.get("estimates"):
            print(f"  FAIL: zero-with-no-source at {rec['print_date']} (placeholder?)"); ok = False

    # 2) source-level pre-print audit: every row flagged pre_print must have been captured
    #    strictly before the print datetime
    for rec in reports:
        put = dt.datetime.fromisoformat(rec["print_datetime_utc"].replace("Z", ""))
        for e in rec.get("estimates", []):
            if e.get("pre_print") is True:
                ts = e.get("snapshot_utc", "")
                try:
                    if "T" in ts:
                        snap = dt.datetime.fromisoformat(ts.replace("Z", ""))
                    elif len(ts) == 14 and ts.isdigit():
                        snap = dt.datetime.strptime(ts, "%Y%m%d%H%M%S")
                    else:  # date-only provenance (news pub date): midnight UTC that day
                        snap = dt.datetime.fromisoformat(ts + "T00:00:00")
                except ValueError:
                    print(f"  FAIL: unparseable snapshot_utc {ts!r} at {rec['print_date']}")
                    ok = False
                    continue
                if snap >= put:
                    violations += 1
                    print(f"  VIOLATION: pre_print row captured at/after print "
                          f"{rec['print_date']} ({e['source']} {ts})")

    # 3) daily blind-wall sweep across the walked window
    d0, d1 = dt.date(2025, 8, 15), dt.date(2026, 3, 15)
    d = d0
    while d <= d1:
        st = storage_consensus_asof(d)  # internal assertions also run here
        if st is not None:
            np_, lp = st["next_print"], st["last_print"]
            if np_ is not None:
                if dt.date.fromisoformat(np_["print_date"]) < d:
                    violations += 1; print(f"  VIOLATION: next_print before D at {d}")
                bad = [k for k in np_ if any(s in k for s in ("actual", "surprise", "vintage"))]
                for e in np_.get("estimates", []):
                    if "actual_on_page_bcf" in e:
                        bad.append("estimates.actual_on_page_bcf")
                if bad:
                    violations += 1; print(f"  VIOLATION: actual-shaped keys {bad} in next_print at {d}")
            if lp is not None and dt.date.fromisoformat(lp["print_date"]) >= d:
                violations += 1; print(f"  VIOLATION: last_print not strictly before D at {d}")
        d += dt.timedelta(days=1)

    # 4) spot semantic checks on known mechanics
    st = storage_consensus_asof("2026-01-29")  # print-day morning
    if st is None or st["next_print"] is None or st["next_print"]["print_date"] != "2026-01-29":
        print("  FAIL: print-day morning must see its own print as next_print"); ok = False
    elif st["next_print"]["consensus_chg_bcf"] is None:
        print("  FAIL: 2026-01-29 morning consensus missing"); ok = False
    if st and st["last_print"] and st["last_print"]["print_date"] != "2026-01-22":
        print("  FAIL: last_print on 2026-01-29 should be 2026-01-22"); ok = False
    st2 = storage_consensus_asof("2025-12-30")  # between the two holiday-shifted prints
    if not st2 or not st2["last_print"] or st2["last_print"]["print_date"] != "2025-12-29" \
            or not st2["next_print"] or st2["next_print"]["print_date"] != "2025-12-31":
        print("  FAIL: double-print week (Dec 29 / Dec 31) mechanics wrong"); ok = False

    n_pre = sum(1 for r in reports if r.get("consensus_pre_print_bcf") is not None)
    print(f"  store: {len(reports)} reports, consensus {sum(1 for r in reports if r['consensus_chg_bcf'] is not None)}"
          f"/{len(reports)}, strictly-pre-print value {n_pre}/{len(reports)}")
    print(f"  blind-wall violations: {violations}")
    ok = ok and violations == 0
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


def audit():
    """Per-week coverage table; gaps named individually (never a percentage)."""
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
