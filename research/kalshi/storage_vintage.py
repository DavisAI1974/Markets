"""
storage_vintage.py — AS-FIRST-PRINTED vs CURRENT-VINTAGE EIA weekly storage (DATA_GATE_S98 feed K).

WHY. The blind wall governs WHEN a storage report becomes visible, not WHICH VINTAGE. Our storage
stores (national data/eia_surprise.json lineage and regional data/storage_regional/) carry EIA's
LATEST REVISED estimates, so the walk's agent may have seen numbers nobody had at the time. This
module exposes, per report week, BOTH the number the market saw at the print (as-first-printed,
recovered from Wayback captures of EIA's own report page) and the number today's series carries —
so a decision-state consumer can see exactly what was knowable then vs what the modern series says.
This is the S97 handoff's #1 concern; it fails silently, which is why the store names every
difference individually.

THE VINTAGE MECHANISM (EIA's own policy, ir.eia.gov/ngs/revisions.html): revisions are DISSEMINATED
only when net reported changes are >= 4 Bcf at a regional level or for the Lower 48; out-of-cycle
releases only at >= 10 Bcf. Sub-4-Bcf respondent corrections therefore reach the current series
WITHOUT any published notice — the mechanism behind the observed 1-3 Bcf as-printed-vs-current
differences. EIA publishes NO vintage archive and NO history of past revisions, and EIA API v2's
natural-gas/stor/wkly route has no vintage facility (facets: duoarea/product/process/series —
current vintage only; verified 2026-07-20). The Wayback captures of the report page are therefore
the authoritative as-printed record.

SOURCES (all recorded per record in the store):
  as-printed   : earliest in-window Wayback capture of ir.eia.gov/ngs/ngs.html (the page states its
                 own "Released:" datetime; values verbatim from the printed table incl. the five
                 regions and the salt/nonsalt split). From 2026-01-06 the page moved behind
                 ir.eia.gov/secure/ngs/ngs.html signed URLs; route recorded per record.
  corroboration: Wayback captures of ir.eia.gov/ngs/wngsr.json (EIA machine summary, carries EIA's
                 own revision_flag per value) where one landed inside the print window.
  current      : data/storage_regional/storage_regional.json + data/eia_surprise.json (read-only).

ZERO SYNTHETIC DATA. A week or field with no in-window archive capture is None and NAMED in
`unrecoverable_fields` — never inferred from neighbors, never assumed equal to current.

ADDITIVE. This module writes/reads its own store (data/storage_vintage/storage_vintage.json) and
edits nothing else. The revised values in the existing stores STAY; this exposes both vintages.

BLIND WALL. Identical day-level rule to storage_regional_asof: for a decision on day D only prints
whose release date is STRICTLY BEFORE D are visible (a Thursday print is not visible on that
Thursday). The store additionally carries the print datetime (page-stated, ET and UTC) and the
audit verifies every as-printed evidence capture falls INSIDE its print window
[print datetime, next print datetime) — evidence captured before the print would be impossible,
evidence captured after the next print would be a later vintage. `--selftest` reports violation
counts (0 required) and checks the known Sep 4 2025 +10 Bcf case against feed D.

PUBLIC INTERFACE (the orchestrator wires this; feed builders never touch forecast_harness.py):

    storage_vintage_asof(date) -> dict | None

        date : str "YYYY-MM-DD" | datetime.date — the DECISION day D.
        returns None if no print is visible strictly before D, else:
        {
          "as_of":  "YYYY-MM-DD",          # print date of the most recent VISIBLE report
          "period": "YYYY-MM-DD",          # week-ending Friday it covers
          "print_datetime_utc": str|None,
          "age_days": int,                 # D - print date (staleness; store ends Mar 5 2026 print)
          "as_printed_recovered": bool,    # False => every *_as_printed field is None, named below
          "national_level_as_printed": num|None, "national_chg_as_printed": num|None,
          "national_level_current":   num|None, "national_chg_current":   num|None,
          "vintage_delta_level": num|None,  # as_printed - current (None where either side missing)
          "vintage_delta_chg":   num|None,
          "regions": { <east|midwest|mountain|pacific|south_central|south_central_salt|
                        south_central_nonsalt|l48>: {
                "level_as_printed": num|None, "chg_as_printed": num|None,
                "level_current":   num|None, "chg_current":   num|None,
                "level_delta":     num|None, "chg_delta":     num|None } | None },
          "unrecoverable_fields": [str, ...],
          "eia_revision_flags_at_print": dict|None,   # EIA's own R flags printed that day
          "notices_at_print": [str, ...],             # notice text on the printed page
          "evidence_url": str|None, "route": str|None,
          "source": "WAYBACK_WNGSR_AS_PRINTED + EIA_CURRENT_STORES"
        }

USAGE
    python research/kalshi/storage_vintage.py --selftest
    python research/kalshi/storage_vintage.py --diff            # per-week vintage diff table
    python research/kalshi/storage_vintage.py --audit           # store audit (violation counts)
    python research/kalshi/storage_vintage.py --asof 2026-01-30
(The store is built by the feed-K build script from cached Wayback captures; this module performs
no network I/O.)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

REGION_KEYS = ["east", "midwest", "mountain", "pacific", "south_central",
               "south_central_salt", "south_central_nonsalt", "l48"]

_HERE = os.path.dirname(os.path.abspath(__file__))
_STORE_DIRS = [os.path.join(_HERE, "..", "..", "data", "storage_vintage"),
               os.path.join("data", "storage_vintage")]
STORE_NAME = "storage_vintage.json"

_CACHE = {"path": None, "store": None}


def _find_store():
    for d in _STORE_DIRS:
        p = os.path.abspath(os.path.join(d, STORE_NAME))
        if os.path.exists(p):
            return p
    return None


def _load():
    p = _find_store()
    if p is None:
        return None
    if _CACHE["path"] == p and _CACHE["store"] is not None:
        return _CACHE["store"]
    with open(p, encoding="utf-8") as f:
        _CACHE["store"] = json.load(f)
    _CACHE["path"] = p
    return _CACHE["store"]


def _to_date(d):
    if isinstance(d, dt.datetime):
        return d.date()
    if isinstance(d, dt.date):
        return d
    return dt.date.fromisoformat(str(d)[:10])


def _num_or_none(x):
    return x if isinstance(x, (int, float)) else None


def storage_vintage_asof(date):
    """Most recent print STRICTLY BEFORE `date`, both vintages exposed. None if nothing visible."""
    store = _load()
    if not store:
        return None
    D = _to_date(date)
    reports = store.get("reports", {})
    best = None
    for pk, rec in reports.items():
        pd = rec.get("print_date")
        if pd is None:
            continue
        pdd = dt.date.fromisoformat(pd)
        if pdd < D and (best is None or pdd > best[0]):
            best = (pdd, rec)
    if best is None:
        return None
    pdd, rec = best
    # blind wall assertion — a print on/after D must never be returned
    assert pdd < D, f"blind wall violated: print {pdd} returned for decision day {D}"

    ap = rec.get("as_printed") or {}
    cv = rec.get("current_vintage") or {}
    dl = rec.get("deltas") or {}
    out = {
        "as_of": rec.get("print_date"),
        "period": rec.get("period"),
        "print_datetime_utc": rec.get("print_datetime_utc"),
        "age_days": (D - pdd).days,
        "as_printed_recovered": rec.get("as_printed") is not None,
        "national_level_as_printed": _num_or_none(ap.get("national_level")),
        "national_chg_as_printed": _num_or_none(ap.get("national_chg")),
        "national_level_current": _num_or_none(cv.get("national_level")),
        "national_chg_current": _num_or_none(cv.get("national_chg")),
        "vintage_delta_level": _num_or_none(dl.get("national_level")),
        "vintage_delta_chg": _num_or_none(dl.get("national_chg")),
        "regions": {},
        "unrecoverable_fields": list(rec.get("unrecoverable_fields") or []),
        "eia_revision_flags_at_print": rec.get("eia_flags_at_print"),
        "notices_at_print": list(rec.get("notices") or []),
        "evidence_url": (rec.get("evidence") or {}).get("url"),
        "route": (rec.get("evidence") or {}).get("route"),
        "source": "WAYBACK_WNGSR_AS_PRINTED + EIA_CURRENT_STORES",
    }
    ap_r = ap.get("regions") or {}
    cv_r = cv.get("regions") or {}
    dl_r = dl.get("regions") or {}
    for k in REGION_KEYS:
        a, c, d_ = ap_r.get(k), cv_r.get(k), dl_r.get(k)
        if a is None and c is None:
            out["regions"][k] = None
            continue
        out["regions"][k] = {
            "level_as_printed": _num_or_none((a or {}).get("level")),
            "chg_as_printed": _num_or_none((a or {}).get("chg")),
            "level_current": _num_or_none((c or {}).get("level")),
            "chg_current": _num_or_none((c or {}).get("chg")),
            "level_delta": _num_or_none((d_ or {}).get("level")),
            "chg_delta": _num_or_none((d_ or {}).get("chg")),
        }
    return out


# --------------------------------------------------------------------------------- audits


def _parse_utc(s):
    if not s:
        return None
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


# Publish jitter tolerance: the 2025-12-18 print was captured at 15:29:58Z, 2 seconds before the
# official 15:30:00 stamp - EIA's page goes live seconds around the official time. A capture inside
# this tolerance carries the NEW report (verified: it shows the 12-12 week), so it is EIA posting
# early, not a wall violation. Anything earlier than the tolerance is a real violation.
PUBLISH_JITTER_S = 120


def audit(verbose=True):
    """Store audit. Returns dict of violation counts (all must be 0) + named findings."""
    store = _load()
    if not store:
        print("NO STORE — build it first")
        return None
    reports = store["reports"]
    pks = sorted(reports)
    v = {"evidence_before_print": 0, "evidence_after_next_print": 0,
         "salt_nonsalt_mismatch": 0, "current_store_disagreement": 0,
         "feed_d_print_date_mismatch": 0}
    named = []
    jitter_named = []
    for i, pk in enumerate(pks):
        rec = reports[pk]
        ev = rec.get("evidence")
        if ev and rec.get("print_datetime_utc"):
            cap = _parse_utc(ev["snapshot_ts_utc"])
            pr = _parse_utc(rec["print_datetime_utc"])
            if cap < pr:
                early_s = (pr - cap).total_seconds()
                if early_s <= PUBLISH_JITTER_S:
                    jitter_named.append(f"{pk}: capture {early_s:.0f}s before the official stamp "
                                        f"(EIA publish jitter, content is the new report)")
                else:
                    v["evidence_before_print"] += 1
                    named.append(f"{pk}: capture {cap} BEFORE print {pr}")
            # next print
            if i + 1 < len(pks):
                nrec = reports[pks[i + 1]]
                npr = _parse_utc(nrec.get("print_datetime_utc") or "")
                if npr and cap >= npr:
                    v["evidence_after_next_print"] += 1
                    named.append(f"{pk}: capture {cap} at/after next print {npr}")
        ap = rec.get("as_printed")
        if ap:
            sc = (ap["regions"].get("south_central") or {}).get("level")
            sa = (ap["regions"].get("south_central_salt") or {}).get("level")
            ns = (ap["regions"].get("south_central_nonsalt") or {}).get("level")
            if None not in (sc, sa, ns) and sa + ns != sc:
                # The printed page rounds each row independently (its own footer: "Totals may not
                # equal sum of components because of independent rounding") - +-1 Bcf is EIA's
                # printed data verbatim, named as a note; beyond 1 Bcf is a recovery violation.
                if abs(sa + ns - sc) > 1:
                    v["salt_nonsalt_mismatch"] += 1
                    named.append(f"{pk}: printed salt {sa} + nonsalt {ns} != SC {sc}")
                else:
                    jitter_named.append(f"{pk}: printed salt {sa} + nonsalt {ns} = {sa+ns} vs SC {sc} "
                                        f"(EIA independent rounding, verbatim)")
        cv = rec.get("current_vintage") or {}
        if (cv.get("sources") or {}).get("NOTE_store_disagreement"):
            v["current_store_disagreement"] += 1
            named.append(f"{pk}: {cv['sources']['NOTE_store_disagreement']}")
        fd = rec.get("feed_d")
        if fd and fd.get("print_date") and rec.get("print_date") and fd["print_date"] != rec["print_date"]:
            v["feed_d_print_date_mismatch"] += 1
            named.append(f"{pk}: page print {rec['print_date']} vs feed D {fd['print_date']}")
    if verbose:
        print("STORE AUDIT (violation counts, 0 required):")
        for k, n in v.items():
            print(f"  {k}: {n}")
        for n in named:
            print("   ", n)
        for n in jitter_named:
            print("    note:", n)
        unrec = [pk for pk in pks if reports[pk].get("as_printed") is None]
        print(f"  unrecoverable weeks ({len(unrec)}):", ", ".join(unrec) or "none")
    return v


def diff_table():
    store = _load()
    reports = store["reports"]
    print("period      print       chg asP/cur (d) | lvl asP/cur (d) | differing regions (level d / chg d)")
    for pk in sorted(reports):
        r = reports[pk]
        ap, cv, dl = r.get("as_printed"), r.get("current_vintage") or {}, r.get("deltas") or {}
        if ap is None:
            print(f"{pk}  {r.get('print_date') or '?':10}  UNRECOVERABLE")
            continue
        parts = []
        for k in REGION_KEYS:
            d_ = (dl.get("regions") or {}).get(k)
            if d_ and ((d_["level"] not in (None, 0)) or (d_["chg"] not in (None, 0))):
                parts.append(f"{k}:{d_['level']}/{d_['chg']}")
        mark = " <-- DIFFERS" if (dl.get("national_chg") not in (None, 0)
                                  or dl.get("national_level") not in (None, 0) or parts) else ""
        print(f"{pk}  {r['print_date']:10}  {ap['national_chg']!s:>5}/{cv.get('national_chg')!s:>5} "
              f"({dl.get('national_chg')!s:>4}) | {ap['national_level']!s:>5}/{cv.get('national_level')!s:>5} "
              f"({dl.get('national_level')!s:>4}) | {'; '.join(parts) or '-'}{mark}")


def selftest():
    ok = True
    store = _load()
    if not store:
        print("FAIL: store missing")
        return 1
    v = audit(verbose=False)
    bad = {k: n for k, n in v.items() if n}
    if bad:
        print(f"  FAIL store audit violations: {bad}")
        ok = False
    else:
        print("  ok  store audit: 0 violations on all five checks")

    # known-week check (feed D's Sep 4 2025 case): printed +55, current +45, delta +10
    r = store["reports"].get("2025-08-29")
    if not r or not r.get("as_printed"):
        print("  FAIL known week 2025-08-29 missing/unrecovered")
        ok = False
    else:
        a = r["as_printed"]["national_chg"]
        c = (r.get("current_vintage") or {}).get("national_chg")
        d_ = (r.get("deltas") or {}).get("national_chg")
        if a == 55 and c == 45 and d_ == 10:
            print("  ok  known week 2025-08-29: as-printed +55 vs current +45 (delta +10, matches feed D)")
        else:
            print(f"  FAIL known week 2025-08-29: as-printed {a} current {c} delta {d_} (expected 55/45/10)")
            ok = False

    # blind-wall daily sweep
    viol = 0
    D = dt.date(2025, 7, 1)
    while D <= dt.date(2026, 3, 20):
        try:
            got = storage_vintage_asof(D)
        except AssertionError:
            viol += 1
            got = None
        if got is not None:
            if dt.date.fromisoformat(got["as_of"]) >= D:
                viol += 1
        D += dt.timedelta(days=1)
    if viol:
        print(f"  FAIL blind-wall sweep: {viol} violations")
        ok = False
    else:
        print("  ok  blind-wall daily sweep 2025-07-01..2026-03-20: 0 violations")

    # asof exposes both vintages on a G11 day
    got = storage_vintage_asof("2026-01-30")
    if got and got["as_of"] == "2026-01-29" and got["as_printed_recovered"] \
            and got["national_chg_as_printed"] is not None and got["national_chg_current"] is not None:
        print(f"  ok  asof 2026-01-30 -> print 2026-01-29 (as-printed {got['national_chg_as_printed']} "
              f"vs current {got['national_chg_current']})")
    else:
        print(f"  FAIL asof 2026-01-30: {None if got is None else got.get('as_of')}")
        ok = False

    # pre-store date -> None
    if storage_vintage_asof("2025-07-01") is None:
        print("  ok  asof before first print -> None")
    else:
        print("  FAIL asof 2025-07-01 should be None")
        ok = False

    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="As-printed vs current-vintage EIA weekly storage (feed K)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--asof", type=str, default=None)
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    if args.audit:
        audit()
        return
    if args.diff:
        diff_table()
        return
    if args.asof:
        print(json.dumps(storage_vintage_asof(args.asof), indent=1))
        return
    ap.print_help()


if __name__ == "__main__":
    main()
