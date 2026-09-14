#!/usr/bin/env python3
"""
coal_prices.py - accrue the EIA weekly coal basin spot prices. (Registry G-11.)

WHY THIS IS THE ONE ITEM THAT CANNOT WAIT. EIA says it on its own page, verbatim: "Because the
historical spot price data are proprietary, they cannot be released by EIA; see S&P Global." The
free endpoint carries a ROLLING FIVE-WEEK WINDOW - measured S112: 07/03/26 through 07/31/26, five
dated rows and nothing older. So every week nobody runs this, one week falls off the back and is
gone for good. It is not that the history is expensive; it is that it is not for sale to us.

WHY WE WANT IT. Coal is the third absorber in Greg's own burn-stack model - weather-driven load,
minus wind and solar, minus what coal and nuclear absorb - and it is the one we have NOTHING on
(registry M-6). The asymmetry that makes it matter: coal plants are retired or retiring, so cheap
gas can still take coal's share but expensive gas can no longer reliably hand it back. Published
bands put gas competitive with PRB below about $3.00/MMBtu.

WHAT THIS IS AND IS NOT. The series is PROMPT-QUARTER delivery, quoted by S&P Global and republished
by EIA with permission - not a spot cash print, and it is sticky: all five weeks in the first pull
read identically (CAPP 82, NAPP 70, ILB 55.5, PRB 14.65, Uinta 25.3). Treat it as a slow structural
level, never as a weekly signal, and never lead with a week-over-week change that is mostly zero.

WHERE IT LIVES. In git, deliberately, against D34's "S3 = data" default: this is five numbers a week,
a RECORD rather than a data store, and it must survive a session boundary with no keys. Moving it to
S3 later loses nothing; not capturing it this week loses that week forever.

USAGE
    python coal_prices.py fetch            # dry run - what would be added
    python coal_prices.py fetch --write    # accrue
    python coal_prices.py show
    python coal_prices.py selftest
"""

import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STORE = os.path.join(HERE, "data_records")
OUT = os.path.join(STORE, "coal_basin_prices.json")
URL = "https://www.eia.gov/coal/markets/coal_markets_json.php"

# EIA's own key is misspelled ILLIOIS_BASIN. Preserved on read, normalised on write - renaming it
# in our store while quietly matching on the typo is how a feed breaks silently the day they fix it.
FIELDS = [("CENTRAL_APP", "central_appalachia"),
          ("NORTHERN_APP", "northern_appalachia"),
          ("ILLIOIS_BASIN", "illinois_basin"),
          ("POWDER_RIVER_BASIN", "powder_river_basin"),
          ("UINTA_BASIN", "uinta_basin")]


def _iso(mmddyy):
    """07/31/26 -> 2026-07-31."""
    m, d, y = mmddyy.split("/")
    return "20%s-%s-%s" % (y, m, d)


def fetch_raw(timeout=30):
    req = urllib.request.Request(URL, headers={"User-Agent": "DavisAI-Markets/coal_prices"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def parse(raw):
    rows = raw["data"][0]["snl_dpst"]
    out = {}
    for r in rows:
        wk = str(r.get("WEEK_ENDING_DATE", ""))
        if "/" not in wk:                     # the 'change' row is not an observation
            continue
        rec = {"week_ending": _iso(wk), "units": "usd_per_short_ton",
               "basis": "prompt_quarter_delivery", "source": "EIA Coal Markets (S&P Global, "
                                                            "republished with permission)"}
        for src, dst in FIELDS:
            if src not in r:
                raise SystemExit("EIA changed a field name: %r missing. STOP - a renamed field "
                                 "read as absent is how a feed goes silently dead." % src)
            rec[dst] = r[src]
        out[rec["week_ending"]] = rec
    if not out:
        raise SystemExit("no dated rows parsed - refusing to write an empty accrual")
    return out


def load():
    if not os.path.exists(OUT):
        return {"note": ("EIA WEEKLY COAL BASIN SPOT PRICES - an ACCRUAL. The free endpoint carries "
                         "a rolling FIVE-WEEK window and EIA states the historical series is "
                         "proprietary and cannot be released, so any week not captured while it is "
                         "in the window is lost permanently. Prompt-quarter delivery, USD per short "
                         "ton, S&P Global via EIA with permission. Sticky by nature - never lead "
                         "with a week-over-week change."),
                "source_url": URL, "weeks": {}}
    with open(OUT, encoding="utf-8") as f:
        return json.load(f)


def cmd_fetch(a):
    store = load()
    got = parse(fetch_raw())
    new, conflict = [], []
    for wk, rec in sorted(got.items()):
        old = store["weeks"].get(wk)
        if old is None:
            new.append(wk)
        else:
            diff = [k for _, k in FIELDS if old.get(k) != rec.get(k)]
            if diff:
                # a revision is real news, not a silent overwrite
                conflict.append((wk, diff))
    print("endpoint returned %d weeks: %s .. %s"
          % (len(got), min(got), max(got)))
    print("  already held : %d" % (len(got) - len(new)))
    print("  NEW          : %d  %s" % (len(new), ", ".join(new) if new else ""))
    if conflict:
        print("  REVISED by EIA (values changed for a week we already hold):")
        for wk, diff in conflict:
            print("     %s  fields: %s" % (wk, ", ".join(diff)))
    if not a.write:
        print("\ndry run - nothing written. Re-run with --write.")
        return 0
    for wk, rec in got.items():
        if wk in store["weeks"] and not any(w == wk for w, _ in conflict):
            continue
        rec["first_seen_utc_date"] = a.today or "unrecorded"
        store["weeks"][wk] = rec
    store["n_weeks"] = len(store["weeks"])
    os.makedirs(STORE, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=1, ensure_ascii=False, sort_keys=False)
    print("\naccrued -> %s  (%d weeks held)" % (os.path.relpath(OUT, ROOT), len(store["weeks"])))
    return 0


def cmd_show(a):
    store = load()
    wks = store.get("weeks", {})
    if not wks:
        print("nothing accrued yet - run fetch --write")
        return 1
    print("%d weeks held, %s .. %s  (USD/short ton, prompt-quarter)"
          % (len(wks), min(wks), max(wks)))
    print("\n  week        CAPP   NAPP    ILB    PRB  Uinta")
    for wk in sorted(wks):
        r = wks[wk]
        print("  %s  %5s  %5s  %5s  %5s  %5s"
              % (wk, r.get("central_appalachia"), r.get("northern_appalachia"),
                 r.get("illinois_basin"), r.get("powder_river_basin"), r.get("uinta_basin")))
    return 0


def cmd_selftest(a):
    res = []

    def check(n, ok):
        res.append(ok)
        print("  %-4s | %s" % ("PASS" if ok else "FAIL", n))

    check("date parse 07/31/26 -> 2026-07-31", _iso("07/31/26") == "2026-07-31")
    sample = {"data": [{"snl_dpst": [
        {"WEEK_ENDING_DATE": "change", "CENTRAL_APP": 0, "NORTHERN_APP": 0,
         "ILLIOIS_BASIN": 0, "POWDER_RIVER_BASIN": 0, "UINTA_BASIN": 0},
        {"WEEK_ENDING_DATE": "07/31/26", "CENTRAL_APP": 82, "NORTHERN_APP": 70,
         "ILLIOIS_BASIN": 55.5, "POWDER_RIVER_BASIN": 14.65, "UINTA_BASIN": 25.3}]}]}
    p = parse(sample)
    check("the 'change' row is not parsed as an observation", len(p) == 1)
    check("EIA's ILLIOIS_BASIN typo maps to illinois_basin",
          p["2026-07-31"]["illinois_basin"] == 55.5)
    bad = json.loads(json.dumps(sample))
    bad["data"][0]["snl_dpst"][1].pop("ILLIOIS_BASIN")
    try:
        parse(bad)
        check("a RENAMED/REMOVED field STOPS rather than reading as absent", False)
    except SystemExit:
        check("a RENAMED/REMOVED field STOPS rather than reading as absent", True)
    empty = {"data": [{"snl_dpst": [{"WEEK_ENDING_DATE": "change", "CENTRAL_APP": 0,
                                     "NORTHERN_APP": 0, "ILLIOIS_BASIN": 0,
                                     "POWDER_RIVER_BASIN": 0, "UINTA_BASIN": 0}]}]}
    try:
        parse(empty)
        check("an all-undated payload refuses to write an empty accrual", False)
    except SystemExit:
        check("an all-undated payload refuses to write an empty accrual", True)
    print("\n  %d/%d passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch"); p.add_argument("--write", action="store_true")
    p.add_argument("--today", help="ISO date to stamp first_seen with")
    sub.add_parser("show")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if not hasattr(a, "today"):
        a.today = None
    return {"fetch": cmd_fetch, "show": cmd_show, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
