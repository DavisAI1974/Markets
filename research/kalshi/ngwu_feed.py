"""
ngwu_feed.py - FEED N (family D/supply): the EIA weekly natural gas S/D balance, from the
Natural Gas Weekly Update (NGWU, era 1) and the WNGSR Supplement (era 2). S98 data gate.

WHY THIS EXISTS
---------------
The desk audit's #2 structural gap is the FLOW/BALANCE side - the forecaster has zero visibility of
production, consumption, LNG feedgas or imports. The NGWU is the free weekly version of the balance
object desks anchor on, and the walked winter's freeze-offs and feedgas swings are in its tables.
The feed does not gate, score, or recommend; the agent decides what the numbers mean.

THE MEASURED PUBLICATION REALITY (investigated 2026-07-20 on EIA's own pages - the load-bearing
findings; nothing below is assumed)
------------------------------------------------------------------------------------------------
1. ERA 1 - the NGWU (weekly, normally Thursday; per-issue archive at
   eia.gov/naturalgas/weekly/archivenew_ngwu/YYYY/MM_DD/). Release dates for the store span are
   MEASURED from EIA's archive index (same measurement feed G recorded):
     2025: Aug 28 (w/w seed); Sep 4/11/18/25; Oct 2/9/16/23/30; Nov 6/13/20; Dec 4/11/18;
     2026: Jan 8/15/22.
   HOLIDAY SKIPS: no issue exists for the weeks of Thanksgiving (would-be Nov 27), Christmas
   (would-be Dec 25), or New Year (would-be Jan 1). Each issue covers exactly ONE Thu->Wed report
   week ending release-1, so the report weeks ending 2025-11-26, 2025-12-24 and 2025-12-31 were
   never covered by any issue - a named gap, never bridged.
   The 2026-01-22 issue is the FINAL NGWU (stated on the issue), replaced by the WNGSR Supplement.

2. THE S/D SECTION DIED BEFORE THE NGWU DID. The archived issues are per-issue static snapshots
   (verified: per-issue commented-out holiday notices differ across issues), and in the late-2025
   issues the whole "Supply and Demand" block - the S&P Global Commodity Insights production /
   consumption / LNG-pipeline-receipts estimates - is present only INSIDE HTML COMMENTS (dead
   template carrying one frozen sample week), while prices / storage / rigs / vessels remain live.
   The live->dead boundary is MEASURED per issue by this module's parser (a value is taken ONLY
   from live, uncommented HTML; commented text is never extracted as data). The frozen sample in
   the dead issues is used as a corroboration display for the last live week, never as data.

3. ERA 2 - the WNGSR Supplement (launched Thursday 2026-01-29, "published every Thursday
   afternoon" per its own about page; an Angular app whose per-issue content lives at
   eia.gov/naturalgas/weekly/supplement/archive/YYYY/MM/DD/content/*.html, with release dates in
   content/release_dates.json - MEASURED: every Thursday Jan 29 -> present, no skips, data week
   ending release-1). It does NOT carry the NGWU's S/D balance table. What it carries on the
   balance side: narrative BULLETS with week/week CHANGES (Bcf/d and %) for whichever components
   moved that week (power burn, LNG feedgas demand, dry production, net Canadian imports, total
   supply), attributed inline to LSEG Data - a DIFFERENT source than era 1's S&P Global. Absolute
   Bcf/d LEVELS are generally NOT published. Era-2 rows therefore carry stated deltas (parsed
   conservatively; the full bullet text is retained verbatim per row) and None levels - a named
   partial gap, not an extraction failure.

4. LNG VESSEL DEPARTURES survive both eras (era 1: Bloomberg shipping data in the NGWU LNG
   section; era 2: Vortexa Analytics in the supplement's LNG tab): weekly vessel count +
   LNG-carrying capacity (Bcf). Carried because it is the only LNG series that spans the walked
   winter's S/D-dead stretch.

BLIND WALL
----------
knowable_from = release_date + 1 calendar day (feed G's convention: releases are afternoon,
mid-session, hour not pinned to the minute -> same-day use is not defensible; the day-after rule
is airtight). The trap this kills: the report week ends release-1 (Wednesday), so a naive "week
data joins the day after the week ends" rule would hand Thursday's release out on Thursday
morning, and a naive "data-week + 1" rule would leak a full day earlier still. Values join on
ISSUE PUBLICATION only. Asserted in code on every asof call AND audited store-wide by --selftest.

ATTRIBUTION (carried per row, stated honestly)
----------------------------------------------
Era-1 S/D estimates: S&P Global Commodity Insights (formerly IHS Markit / Platts), republished by
EIA in the NGWU. Era-1 vessels: Bloomberg Finance, L.P. Era-2 balance bullets: LSEG Data where
cited inline. Era-2 vessels: Vortexa Analytics tanker tracker. All were published openly by EIA on
public pages; no redistribution terms are printed on those pages; the third-party attribution is
carried on every row and must travel with the numbers.

ZERO SYNTHETIC. Missing issue / missing series / dead section = None + named. Nothing is bridged
across issue gaps: computed w/w changes exist only when the prior issue's report week ends exactly
7 days earlier AND both levels were published live.

PUBLIC API
----------
  ngwu_asof(date) -> dict | None
      Latest issue with knowable_from <= date, with its balance fields, age_days (vs the report
      week end), issue_age_days (vs the issue date), and latest_sd_levels = the most recent
      knowable issue that still carried LIVE S/D levels (with its own age) - so the agent always
      sees both the freshest issue and the freshest actual balance, each with honest staleness.

CLI
---
  python research/kalshi/ngwu_feed.py --fetch  [--refresh]   # polite pull of raw pages -> data/ngwu/raw/
  python research/kalshi/ngwu_feed.py --build                # parse raw -> data/ngwu/ngwu.json
  python research/kalshi/ngwu_feed.py --selftest
  python research/kalshi/ngwu_feed.py --show 2026-01-30
  python research/kalshi/ngwu_feed.py --table
"""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
import sys
import time
from datetime import date as _date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data", "ngwu")
RAW_DIR = os.path.join(DATA_DIR, "raw")
STORE_PATH = os.path.join(DATA_DIR, "ngwu.json")
CASH_STORE = os.path.join(ROOT, "data", "cash_basis", "hh_cash.json")  # read-only, optional (crosscheck)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-fetch"}

# MEASURED era-1 release dates (EIA archive index eia.gov/naturalgas/weekly/includes/archive.php,
# measured 2026-07-20; identical to feed G's measurement). 2025-08-28 is the w/w seed issue for
# the Sep 4 store start; coverage target proper is Sep 2025 -> the final issue.
ERA1_RELEASES = [
    "2025-08-28",
    "2025-09-04", "2025-09-11", "2025-09-18", "2025-09-25",
    "2025-10-02", "2025-10-09", "2025-10-16", "2025-10-23", "2025-10-30",
    "2025-11-06", "2025-11-13", "2025-11-20",
    "2025-12-04", "2025-12-11", "2025-12-18",
    "2026-01-08", "2026-01-15", "2026-01-22",
]
# Report weeks never covered by ANY era-1 issue (holiday skips; each issue covers exactly one week).
ERA1_SKIPPED_WEEKS_ENDING = ["2025-11-26", "2025-12-24", "2025-12-31"]

ERA1_URL = "https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/{y}/{m}_{d}"
ERA2_BASE = "https://www.eia.gov/naturalgas/weekly/supplement/"
ERA2_ARCH = ERA2_BASE + "archive/{y}/{m}/{d}/content/"
ERA2_FILES = ["bullets_prices_1.html", "bullets_prices_2.html", "bullets_lng_1.html", "source_prices_1.html"]

ATTR_ERA1_SD = "S&P Global Commodity Insights (published by EIA, Natural Gas Weekly Update)"
ATTR_ERA1_VESSELS = "Bloomberg Finance, L.P. shipping data (published by EIA, Natural Gas Weekly Update)"
ATTR_ERA2_SD = "LSEG Data, as cited inline in WNGSR Supplement bullets (published by EIA)"
ATTR_ERA2_VESSELS = "Vortexa Analytics tanker tracker (published by EIA, WNGSR Supplement)"

FIELDS = ["total_supply", "dry_production", "net_canada_imports", "total_consumption",
          "power", "industrial", "rescomm", "mexico_exports", "lng_feedgas"]


def _require(cond, msg):
    if not cond:
        raise AssertionError("ngwu_feed blind-wall/integrity violation: " + msg)


def _d(s):
    if isinstance(s, _date):
        return s
    s = str(s).strip().replace("/", "-")
    if len(s) == 8 and s.isdigit():
        s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return datetime.strptime(s, "%Y-%m-%d").date()


def _iso(d):
    return d.isoformat()


_MON = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"])}


def _long_date(s):
    m = re.search(r"([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if not m or m.group(1) not in _MON:
        return None
    return _date(int(m.group(3)), _MON[m.group(1)], int(m.group(2)))


# ------------------------------------------------------------------ number words (vessel counts)
_ONES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
         "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60}


def _word_num(w):
    w = w.strip().lower()
    if w.isdigit():
        return int(w)
    parts = re.split(r"[-\s]+", w)
    total = 0
    for p in parts:
        if p in _ONES:
            total += _ONES[p]
        elif p in _TENS:
            total += _TENS[p]
        else:
            return None
    return total if total > 0 else None


# ------------------------------------------------------------------ html helpers
def _strip_comments(raw):
    return re.sub(r"<!--.*?-->", " ", raw, flags=re.S)


def _text(fragment):
    t = re.sub(r"<script.*?</script>", " ", fragment, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


_UPW = ("rose", "increased", "grew", "climbed", "expanded", "gained", "higher", "rise",
        "increase", "jump", "up")
_DOWNW = ("fell", "decreased", "declined", "dropped", "lower", "decline", "decrease", "drop",
          "fall", "down")
_FLATP = ("remained essentially unchanged", "essentially unchanged", "remained relatively the same",
          "relatively the same", "remained flat", "stayed flat", "remained unchanged",
          "was unchanged", "unchanged", "flat")


def _sign_of(word):
    w = word.lower()
    if w in _UPW:
        return 1
    if w in _DOWNW:
        return -1
    return None


def _metric_window(text, anchor, all_anchors, cap=460):
    low = text.lower()
    i = low.find(anchor.lower())
    if i < 0:
        return None
    j = len(text)
    for a in all_anchors:
        if a == anchor:
            continue
        k = low.find(a.lower(), i + len(anchor))
        if 0 <= k < j:
            j = k
    return text[i:min(j, i + cap)]


def _parse_metric(win):
    """Parse one era-1 metric window -> dict(level, pct, delta, qualifier, direction)."""
    if win is None:
        return None
    out = {"level_bcfd": None, "wow_stated_pct": None, "wow_stated_bcfd": None,
           "qualifier": None, "direction": None}
    low = win.lower()
    flat = next((f for f in _FLATP if f in low), None)
    vm = re.search(r"\b(rose|increased|grew|climbed|expanded|gained|fell|decreased|declined|dropped)\b", win, re.I)
    sign = None
    if vm:
        sign = _sign_of(vm.group(1))
        out["direction"] = vm.group(1).lower()
    if flat and (vm is None or low.find(flat) < low.find(vm.group(1).lower())):
        out["direction"] = "unchanged"
        out["qualifier"] = flat
        sign = 0
    # pct: first "X%" in window
    pm = re.search(r"(\d+(?:\.\d+)?)\s*%", win)
    if pm and sign is not None and sign != 0:
        out["wow_stated_pct"] = round(sign * float(pm.group(1)), 2)
    elif pm and sign == 0:
        out["wow_stated_pct"] = 0.0
    # delta: "(0.6 Bcf/d)" | "(less than 0.1 Bcf/d)" | "or 0.3 Bcf/d lower than last week"
    #        | "fell 0.3 Bcf/d from last week"
    dm = re.search(r"\((less than |about |approximately )?(\d+(?:\.\d+)?) Bcf/d\)", win)
    if dm:
        if dm.group(1):
            out["qualifier"] = (dm.group(1).strip() + " " + dm.group(2) + " Bcf/d")
        elif sign is not None:
            out["wow_stated_bcfd"] = round((sign if sign != 0 else 0) * float(dm.group(2)), 2)
    else:
        dm2 = re.search(r"or (\d+(?:\.\d+)?) Bcf/d (lower|higher) than last week", win, re.I)
        dm3 = re.search(r"\b(?:rose|fell|increased|decreased|declined|grew|climbed) (?:by )?(\d+(?:\.\d+)?) Bcf/d\b", win, re.I)
        if dm2:
            out["wow_stated_bcfd"] = round((1 if dm2.group(2).lower() == "higher" else -1) * float(dm2.group(1)), 2)
        elif dm3 and sign is not None:
            out["wow_stated_bcfd"] = round(sign * float(dm3.group(1)), 2)
    # level: "to average X Bcf/d" | "averaging X" | "averaged X" | "to X Bcf/d" | "at X Bcf/d"
    lm = (re.search(r"(?:to average|averaging|averaged) (?:about )?(\d+(?:\.\d+)?) Bcf/d", win, re.I)
          or re.search(r"\bto (\d+(?:\.\d+)?) Bcf/d", win)
          or re.search(r"\bat (\d+(?:\.\d+)?) Bcf/d", win))
    if lm:
        out["level_bcfd"] = float(lm.group(1))
    return out


# ------------------------------------------------------------------ era-1 issue parser
E1_ANCHORS = {
    "total_supply": "average total supply of natural gas",
    "dry_production": "Dry natural gas production",
    "net_canada_imports": "net imports from Canada",
    "total_consumption": "Total U.S. consumption of natural gas",
    "power": "power generation",
    "industrial": "industrial sector",
    "rescomm": "residential and commercial",
    "mexico_exports": "exports to Mexico",
    "lng_feedgas": "LNG export facilities",
}


def parse_era1(raw, issue_date):
    """Parse one archived NGWU page. Values ONLY from live (uncommented) HTML."""
    nc = _strip_comments(raw)
    row = {"era": 1, "issue_date": _iso(issue_date),
           "knowable_from": _iso(issue_date + timedelta(days=1)),
           "source_url": ERA1_URL.format(y=issue_date.year, m=f"{issue_date.month:02d}", d=f"{issue_date.day:02d}"),
           "extraction_route": None, "sd_live": False, "fields": {}, "sentences": {}, "notes": []}
    # header: week ending + release date
    hm = re.search(r"for week ending\s+([A-Z][a-z]+ \d{1,2}, \d{4})", nc)
    rm = re.search(r"Release date:\s*</strong>\s*(?:&nbsp;|\s)*([A-Z][a-z]+ \d{1,2}, \d{4})", raw)
    week_end = _long_date(hm.group(1)) if hm else None
    rel_hdr = _long_date(rm.group(1)) if rm else None
    if week_end is None:
        row["notes"].append("header week-ending not found")
        return row
    row["week_ending"] = _iso(week_end)
    row["week_span"] = [_iso(week_end - timedelta(days=6)), _iso(week_end)]
    if week_end.weekday() != 2:
        row["notes"].append(f"week_ending {week_end} is not a Wednesday")
    if rel_hdr and rel_hdr != issue_date:
        row["notes"].append(f"header release date {rel_hdr} != archive-index date {issue_date}")
    if week_end != issue_date - timedelta(days=1):
        row["notes"].append("report week does not end release-1")

    # S/D section: live only if the jm-supply anchor survives comment-stripping
    si = nc.find('id="jm-supply"')
    li_ = nc.find('id="jm-lng"')
    ri = nc.find('id="jm-rigs"')
    sd_text = _text(nc[si:li_]) if (si >= 0 and li_ > si) else None
    lng_text = _text(nc[li_:ri]) if (li_ >= 0 and ri > li_) else None
    row["sd_live"] = bool(sd_text and "Supply:" in sd_text)

    # EIA's own product notice, when carried live (the S/D removal was announced Oct 2, 2025)
    nt = _text(nc)
    nm_ = re.search(r"Note on product page.*?more information\.", nt)
    if nm_ and "currently unavailable" in nm_.group(0):
        row["product_notice"] = nm_.group(0).strip()

    f = {}
    if row["sd_live"]:
        anchors = [a for a in E1_ANCHORS.values() if a.lower() in sd_text.lower()]
        for key, anchor in E1_ANCHORS.items():
            win = _metric_window(sd_text, anchor, anchors)
            f[key] = _parse_metric(win)
        row["sentences"]["supply_demand"] = sd_text
        row["extraction_route"] = "era1_live_html_text"
    else:
        for key in E1_ANCHORS:
            f[key] = None
        row["extraction_route"] = "era1_sd_discontinued"
        row["notes"].append("S/D section not present live on the archived page (commented-out dead template); levels None")

    # LNG section (live even in some dead-S/D issues): pipeline receipts + vessels
    if lng_text:
        row["sentences"]["lng"] = lng_text
        if "LNG export terminals" in lng_text:
            win = _metric_window(lng_text, "LNG export terminals", ["essels departing"])
            m = _parse_metric(win)
            if m and (m["level_bcfd"] is not None or m["wow_stated_bcfd"] is not None):
                f["lng_feedgas_lng_section"] = m
                # if the demand-side display is dead, the LNG section is the (still live) display
                if f.get("lng_feedgas") is None:
                    f["lng_feedgas"] = m
        vm = re.search(r"([A-Za-z][A-Za-z\- ]{0,20}?)\s+(?:LNG\s+)?(?:vessels|tankers)\s+with a combined LNG-carrying capacity of\s+([\d,]+)\s+(?:Bcf|billion cubic feet \(Bcf\)) departed", lng_text)
        if vm:
            n = _word_num(vm.group(1))
            row["lng_vessels_departed"] = n
            row["lng_vessel_capacity_bcf"] = float(vm.group(2).replace(",", ""))
            row["vessels_attribution"] = ATTR_ERA1_VESSELS
    row["fields"] = f
    row["attribution"] = ATTR_ERA1_SD if row["sd_live"] else None
    return row


def stale_template_sample(raw):
    """Extract the frozen S/D sample from the COMMENTED-OUT block of a dead issue (corroboration
    display only - never data)."""
    out = {}
    for cm in re.finditer(r"<!--(.*?)-->", raw, flags=re.S):
        seg = cm.group(1)
        if "Supply:" in seg and "Dry natural gas production" in seg:
            t = _text(seg)
            anchors = [a for a in E1_ANCHORS.values() if a in t]
            for key, anchor in E1_ANCHORS.items():
                m = _parse_metric(_metric_window(t, anchor, anchors))
                if m:
                    out[key] = m
            out["_text"] = t[:1200]
            break
    return out or None


# ------------------------------------------------------------------ era-2 issue parser
# The supplement's balance content is EDITORIAL bullets; wording varies per issue. Patterns below
# were derived from the actual archived issues (2026-01-29 .. 2026-07-16). National scope is
# guarded: sector statements are taken only from sentences that are nationally scoped ("United
# States" / "U.S." / "Total") and not regional (" region" and hub/ISO names rejected). Full bullet
# text is retained verbatim on every row; anything unparsed stays None.
_BCFD = r"(?:Bcf/d|billion cubic feet per day \(Bcf/d\))"
E2_NATIONAL_TOTAL = re.compile(
    r"Total (?:U\.?S\.? )?(?:demand for natural gas|natural gas (?:demand|consumption)|consumption of natural gas)"
    r"(?: in the United States)?,? (increased|decreased|rose|fell|declined|grew|climbed)"
    r"(?: \w+){0,3}? by (\d+(?:\.\d+)?) " + _BCFD, re.I)
E2_FOLLOWS = re.compile(
    r"follow(?:s|ing|ed) a (\d+(?:\.\d+)?) Bcf/d(?: \((\d+(?:\.\d+)?)%\))? "
    r"(rise|increase|decline|decrease|drop|fall)(?: from)? last week", re.I)
E2_SECTOR_DELTA_IN = [
    # "a 1.4 Bcf/d (3%) increase in electric power sector demand"
    ("power", re.compile(r"(\d+(?:\.\d+)?) Bcf/d \((\d+(?:\.\d+)?)%\) (increase|rise|jump|decline|decrease|drop|fall) in (?:electric )?power (?:sector )?(?:demand|burn|consumption)", re.I)),
    ("lng_feedgas", re.compile(r"(\d+(?:\.\d+)?) Bcf/d \((\d+(?:\.\d+)?)%\) (increase|rise|jump|decline|decrease|drop|fall) in LNG feedgas (?:demand|deliveries)", re.I)),
    ("rescomm", re.compile(r"(\d+(?:\.\d+)?) Bcf/d \((\d+(?:\.\d+)?)%\) (?:demand )?(increase|rise|jump|decline|decrease|drop|fall) in (?:the )?residential and commercial sectors?", re.I)),
    # "led by an 11.0 Bcf/d decrease in the residential and commercial sectors"
    ("rescomm", re.compile(r"an? (\d+(?:\.\d+)?) Bcf/d()\s?(increase|rise|jump|decline|decrease|drop|fall) in (?:the )?residential and commercial sectors?", re.I)),
]
E2_SUBJ_PATTERNS = [
    ("total_supply", re.compile(r"Total U\.?S\.? natural gas supply (increased|decreased|rose|fell|declined|grew|climbed) (?:by )?(\d+(?:\.\d+)?) Bcf/d(?: \((\d+(?:\.\d+)?)%\))?", re.I)),
    ("dry_production", re.compile(r"[Dd]ry natural gas production (increased|decreased|rose|fell|declined|grew|climbed) (?:by )?(\d+(?:\.\d+)?) Bcf/d(?: \((\d+(?:\.\d+)?)%\))?", re.I)),
    ("net_canada_imports", re.compile(r"net Canadian imports (increased|decreased|rose|fell|declined|grew|climbed) (?:by )?(\d+(?:\.\d+)?) Bcf/d(?: \((\d+(?:\.\d+)?)%\))?", re.I)),
    ("power", re.compile(r"(?:electric )?power (?:sector |burn )?demand (increased|decreased|rose|fell|declined|grew|climbed) (?:by )?(\d+(?:\.\d+)?) Bcf/d(?: \((\d+(?:\.\d+)?)%\))?", re.I)),
    ("lng_feedgas", re.compile(r"LNG feedgas (?:demand |deliveries )?(increased|decreased|rose|fell|declined|grew|climbed) (?:by )?(\d+(?:\.\d+)?) Bcf/d(?: \((\d+(?:\.\d+)?)%\))?", re.I)),
    # "total U.S. residential and commercial demand fell by 8.3 Bcf/d, or 12.5%"
    ("rescomm", re.compile(r"residential and commercial demand (increased|decreased|rose|fell|declined) by (\d+(?:\.\d+)?) Bcf/d(?:, or (\d+(?:\.\d+)?)%)?", re.I)),
]
# pct-only feedgas ("Total ... feedgas deliveries fell 18% on the week")
E2_FEEDGAS_PCT = re.compile(
    r"(?:Total )?(?:liquefied natural gas \(LNG\) |LNG )feedgas (?:deliveries |demand |flows )?"
    r"(fell|rose|increased|decreased|declined|dropped)(?: by)? (\d+(?:\.\d+)?)%", re.I)
E2_PAIR = re.compile(
    r"dry natural gas production and net Canadian imports (rose|fell|increased|decreased|declined) by "
    r"(\d+(?:\.\d+)?) Bcf/d \((\d+(?:\.\d+)?)%\) and (\d+(?:\.\d+)?) Bcf/d \((\d+(?:\.\d+)?)%\), respectively", re.I)
_E2_REGION_WORDS = (" region", "Northeast", "Midwest", "Western", "Pacific", "Southeast",
                    "South Central", "Mountain", "California", "CAISO", "NYISO", "PJM", "ISO-NE",
                    "Boston", "SoCal", "PG&E", "Algonquin", "Transco", "Waha", "Sumas", "Florida")


def _sentences(text):
    prot = text.replace("U.S.", "U~S~").replace("L.P.", "L~P~")
    parts = re.split(r"(?<=[.!?])\s+", prot)
    return [p.replace("U~S~", "U.S.").replace("L~P~", "L.P.") for p in parts if p.strip()]


def _e2_national(sent):
    if " region" in sent:
        return False
    return ("United States" in sent) or ("U.S." in sent) or sent.strip().startswith("Total")


def _e2_not_regional(sent):
    return not any(w in sent for w in _E2_REGION_WORDS)


def parse_era2(files, issue_date, week_ending):
    row = {"era": 2, "issue_date": _iso(issue_date),
           "knowable_from": _iso(issue_date + timedelta(days=1)),
           "week_ending": _iso(week_ending),
           "week_span": [_iso(week_ending - timedelta(days=6)), _iso(week_ending)],
           "source_url": ERA2_ARCH.format(y=issue_date.year, m=f"{issue_date.month:02d}", d=f"{issue_date.day:02d}").replace("content/", ""),
           "extraction_route": "era2_supplement_bullets", "sd_live": False,
           "fields": {k: None for k in E1_ANCHORS}, "sentences": {}, "notes": [
               "WNGSR Supplement: no S/D balance table; balance info is narrative w/w deltas (LSEG), no absolute levels"],
           }
    text = ""
    for name in ["bullets_prices_1.html", "bullets_prices_2.html"]:
        if name in files:
            text += " " + _text(files[name])
    if not text.strip():
        row["notes"].append("no bullets content recovered")
        return row
    row["sentences"]["bullets"] = text.strip()
    f = row["fields"]

    def _put(key, sign, delta, pct):
        cur = f.get(key)
        ent = cur if isinstance(cur, dict) else {
            "level_bcfd": None, "wow_stated_pct": None, "wow_stated_bcfd": None,
            "qualifier": None, "direction": None}
        if ent.get("wow_stated_bcfd") is None and delta is not None:
            ent["wow_stated_bcfd"] = round(sign * float(delta), 2)
        if ent.get("wow_stated_pct") is None and pct is not None:
            ent["wow_stated_pct"] = round(sign * float(pct), 2)
        ent["direction"] = "up" if sign > 0 else "down"
        f[key] = ent

    sents = _sentences(text)
    prior_quotes = {}

    def _follows(idx, key):
        for s in sents[idx:idx + 2]:
            fm = E2_FOLLOWS.search(s)
            if fm:
                sign = 1 if fm.group(3).lower() in ("rise", "increase") else -1
                prior_quotes[key] = round(sign * float(fm.group(1)), 2)
                return

    pm = E2_PAIR.search(text)
    if pm:
        sign = _sign_of(pm.group(1)) or (1 if pm.group(1).lower() in _UPW else -1)
        _put("dry_production", sign, pm.group(2), pm.group(3))
        _put("net_canada_imports", sign, pm.group(4), pm.group(5))
    for i, s in enumerate(sents):
        m = E2_NATIONAL_TOTAL.search(s)
        if m and _e2_national(s):
            sign = _sign_of(m.group(1))
            if sign:
                _put("total_consumption", sign, m.group(2), None)
                _follows(i, "total_consumption")
        for key, rx in E2_SECTOR_DELTA_IN:
            m = rx.search(s)
            if m and (_e2_national(s) or _e2_not_regional(s)):
                sign = 1 if m.group(3).lower() in ("increase", "rise", "jump") else -1
                _put(key, sign, m.group(1), m.group(2) or None)
                _follows(i, key)
        for key, rx in E2_SUBJ_PATTERNS:
            m = rx.search(s)
            if m and (_e2_national(s) or _e2_not_regional(s)):
                sign = _sign_of(m.group(1))
                if sign:
                    _put(key, sign, m.group(2), m.group(3))
                    _follows(i, key)
        m = E2_FEEDGAS_PCT.search(s)
        if m:
            sign = _sign_of(m.group(1))
            if sign:
                cur = f.get("lng_feedgas")
                ent = cur if isinstance(cur, dict) else {
                    "level_bcfd": None, "wow_stated_pct": None, "wow_stated_bcfd": None,
                    "qualifier": None, "direction": None}
                if ent.get("wow_stated_pct") is None:
                    ent["wow_stated_pct"] = round(sign * float(m.group(2)), 2)
                ent["direction"] = "up" if sign > 0 else "down"
                f["lng_feedgas"] = ent
    if prior_quotes:
        row["prior_week_quotes_bcfd"] = prior_quotes
    # levels, when a bullet states one (rare)
    lm = re.search(r"[Dd]ry natural gas production[^.]{0,120}?averag(?:ed|ing) (\d+(?:\.\d+)?) Bcf/d", text)
    if lm:
        ent = f.get("dry_production") or {"level_bcfd": None, "wow_stated_pct": None,
                                          "wow_stated_bcfd": None, "qualifier": None, "direction": None}
        ent["level_bcfd"] = float(lm.group(1))
        f["dry_production"] = ent

    # vessels (bullets_lng_1)
    if "bullets_lng_1.html" in files:
        lt = _text(files["bullets_lng_1.html"])
        row["sentences"]["lng"] = lt
        cm = (re.search(r"capacity of vessels departing U\.?S\.? ports was ([\d,]+) Bcf", lt)
              or re.search(r"([\d,]+) Bcf of total LNG-carrying capacity departed U\.?S\.? ports", lt))
        nm = re.search(r"\b([A-Za-z][A-Za-z\-]{2,15}|\d{1,3})\s+(?:LNG )?vessels left U\.?S\.? ports", lt)
        if cm:
            row["lng_vessel_capacity_bcf"] = float(cm.group(1).replace(",", ""))
        if nm:
            row["lng_vessels_departed"] = _word_num(nm.group(1))
        if cm or nm:
            row["vessels_attribution"] = ATTR_ERA2_VESSELS
    row["attribution"] = ATTR_ERA2_SD
    return row


# ------------------------------------------------------------------ fetch
def _get(url, dest=None, tries=3):
    import urllib.request
    import urllib.error
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                if dest:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "wb") as fh:
                        fh.write(data)
                return r.status, data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            return e.code, b""
        except Exception:
            time.sleep(3)
    return None, b""


def cmd_fetch(refresh=False):
    os.makedirs(RAW_DIR, exist_ok=True)
    for ds in ERA1_RELEASES:
        d = _d(ds)
        dest = os.path.join(RAW_DIR, f"ngwu_{ds}.html")
        if os.path.exists(dest) and not refresh:
            print("skip", dest)
            continue
        st, _ = _get(ERA1_URL.format(y=d.year, m=f"{d.month:02d}", d=f"{d.day:02d}"), dest)
        print("era1", ds, st)
        time.sleep(1.1)
    # era 2: release dates first, then per-issue content
    st, data = _get(ERA2_BASE + "content/release_dates.json", os.path.join(RAW_DIR, "supp_release_dates.json"))
    print("era2 release_dates.json", st)
    rel = json.loads(data.decode("utf-8"))
    issues = [(p["release-date"], p["data-week-ending"]) for p in rel.get("past-publications", [])]
    cur_rel, cur_wk = _long_date(rel["release-date"]), _long_date(rel["data-week-ending"])
    for ds, wk in issues:
        d = _d(ds)
        for name in ERA2_FILES:
            dest = os.path.join(RAW_DIR, "supp_archive", ds, name)
            if os.path.exists(dest) and not refresh:
                continue
            st, _ = _get(ERA2_ARCH.format(y=d.year, m=f"{d.month:02d}", d=f"{d.day:02d}") + name, dest)
            print("era2", ds, name, st)
            time.sleep(0.9)
    # current issue content (lives at content/, not archive/)
    for name in ERA2_FILES + ["about.html"]:
        dest = os.path.join(RAW_DIR, "supp_" + name)
        if os.path.exists(dest) and not refresh:
            continue
        st, _ = _get(ERA2_BASE + "content/" + name, dest)
        print("era2 current", name, st)
        time.sleep(0.9)
    print("fetch done; current issue:", cur_rel, "week ending", cur_wk)


# ------------------------------------------------------------------ build
def cmd_build():
    issues = []
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # era 1
    dead_samples = {}
    for ds in ERA1_RELEASES:
        p = os.path.join(RAW_DIR, f"ngwu_{ds}.html")
        if not os.path.exists(p):
            issues.append({"era": 1, "issue_date": ds, "unrecovered": True,
                           "notes": [f"raw page not fetched: {p}"]})
            continue
        raw = open(p, encoding="utf-8", errors="replace").read()
        row = parse_era1(raw, _d(ds))
        row["raw_file"] = os.path.basename(p)
        issues.append(row)
        if not row["sd_live"]:
            s = stale_template_sample(raw)
            if s:
                dead_samples[ds] = s
    # era 2 (from measured release_dates.json)
    rel_path = os.path.join(RAW_DIR, "supp_release_dates.json")
    era2_measured = []
    if os.path.exists(rel_path):
        rel = json.loads(open(rel_path, encoding="utf-8").read())
        pubs = sorted([(p["release-date"], p["data-week-ending"]) for p in rel.get("past-publications", [])])
        cur_rel, cur_wk = _long_date(rel["release-date"]), _long_date(rel["data-week-ending"])
        era2_measured = [p[0] for p in pubs] + ([_iso(cur_rel)] if cur_rel else [])
        for ds, wk in pubs:
            d = _d(ds)
            files = {}
            for name in ERA2_FILES:
                fp = os.path.join(RAW_DIR, "supp_archive", ds, name)
                if os.path.exists(fp):
                    files[name] = open(fp, encoding="utf-8", errors="replace").read()
            row = parse_era2(files, d, _d(wk))
            row["raw_file"] = f"supp_archive/{ds}/"
            if not files:
                row["unrecovered"] = True
                row["notes"].append("no archived content files recovered for this issue")
            issues.append(row)
        if cur_rel:
            files = {}
            for name in ERA2_FILES:
                fp = os.path.join(RAW_DIR, "supp_" + name)
                if os.path.exists(fp):
                    files[name] = open(fp, encoding="utf-8", errors="replace").read()
            row = parse_era2(files, cur_rel, cur_wk)
            row["source_url"] = ERA2_BASE
            row["raw_file"] = "supp_bullets_*.html (current issue)"
            issues.append(row)

    issues = [r for r in issues if not r.get("unrecovered")] + [r for r in issues if r.get("unrecovered")]
    issues.sort(key=lambda r: r["issue_date"])

    # computed w/w: only consecutive report weeks (exactly 7 days apart), both levels live
    by_date = [r for r in issues if not r.get("unrecovered")]
    for i, row in enumerate(by_date):
        comp = {}
        prev = by_date[i - 1] if i > 0 else None
        if prev and row.get("week_ending") and prev.get("week_ending") and \
                (_d(row["week_ending"]) - _d(prev["week_ending"])).days == 7:
            for k in E1_ANCHORS:
                a, b = row["fields"].get(k), prev["fields"].get(k)
                if isinstance(a, dict) and isinstance(b, dict) and \
                        a.get("level_bcfd") is not None and b.get("level_bcfd") is not None:
                    comp[k] = round(a["level_bcfd"] - b["level_bcfd"], 2)
                else:
                    comp[k] = None
        else:
            comp = {k: None for k in E1_ANCHORS}
            if prev:
                row.setdefault("notes", []).append(
                    "computed w/w None: prior issue's report week is not 7 days earlier (issue gap - never bridged)")
        row["computed_wow_bcfd"] = comp

    live = [r for r in by_date if r.get("era") == 1 and r.get("sd_live")]
    dead = [r for r in by_date if r.get("era") == 1 and not r.get("sd_live")]
    meta = {
        "built_at": fetched_at,
        "store": "EIA weekly NG S/D balance; era 1 = NGWU (S&P Global estimates), era 2 = WNGSR Supplement (LSEG deltas)",
        "era1_release_dates_measured": ERA1_RELEASES,
        "era1_skipped_report_weeks_ending": ERA1_SKIPPED_WEEKS_ENDING,
        "era1_final_issue": "2026-01-22",
        "era2_launch": "2026-01-29",
        "era2_release_dates_measured": era2_measured,
        "era2_schedule_note": "measured from supplement release_dates.json: every Thursday 2026-01-29 -> present, no skips; data week ends release-1",
        "knowability_rule": "knowable_from = release_date + 1 calendar day (afternoon release, hour not pinned; day-after rule airtight)",
        "sd_last_live_issue": live[-1]["issue_date"] if live else None,
        "sd_first_dead_issue": dead[0]["issue_date"] if dead else None,
        "sd_dead_issues": [r["issue_date"] for r in dead],
        "sd_unavailability_notice": {
            "issues_carrying_it": [r["issue_date"] for r in by_date if r.get("product_notice")],
            "text": next((r["product_notice"] for r in by_date if r.get("product_notice")), None),
            "note": "EIA's own live notice on the first dead issues; dropped from later issues without the section returning",
        },
        "live_page_wayback_check": {
            "snapshot": "web.archive.org/web/20251115185640 of eia.gov/naturalgas/weekly/ (the Nov 13 issue as visitors saw it)",
            "raw_capture": "raw/wayback_live_20251115.html",
            "finding": "live page mid-winter carried NO S/D section ('Supply:' present only inside an HTML comment) and no notice - the balance was not published anywhere on the vehicle",
        } if os.path.exists(os.path.join(RAW_DIR, "wayback_live_20251115.html")) else None,
        "stale_template_samples": dead_samples,
        "attribution": {"era1_sd": ATTR_ERA1_SD, "era1_vessels": ATTR_ERA1_VESSELS,
                        "era2_sd": ATTR_ERA2_SD, "era2_vessels": ATTR_ERA2_VESSELS,
                        "redistribution_note": "all values were published openly by EIA on public pages; no redistribution terms printed there; attribution must travel with the numbers"},
        "named_gaps": [
            "report weeks ending 2025-11-26 / 2025-12-24 / 2025-12-31: no NGWU issue existed (holiday skips) - never bridged",
            "S/D balance levels are absent (None) from every issue after sd_last_live_issue: the S&P Global section is dead template on those archived pages",
            "era 2 (WNGSR Supplement) publishes no absolute balance levels - stated w/w deltas only, source LSEG",
        ],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    store = {"meta": meta, "issues": issues}
    with open(STORE_PATH, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=1)
    print(f"built {STORE_PATH}: {len(issues)} issues "
          f"({sum(1 for r in issues if r.get('era') == 1)} era-1, {sum(1 for r in issues if r.get('era') == 2)} era-2); "
          f"S/D live through {meta['sd_last_live_issue']}, dead from {meta['sd_first_dead_issue']}")
    return store


# ------------------------------------------------------------------ asof
_STORE_CACHE = None


def _load():
    global _STORE_CACHE
    if _STORE_CACHE is None:
        with open(STORE_PATH, encoding="utf-8") as fh:
            _STORE_CACHE = json.load(fh)
    return _STORE_CACHE


def ngwu_asof(date):
    """Latest knowable weekly balance as of `date` (str YYYY-MM-DD or date). None before the
    first knowable issue. Blind wall asserted in-code."""
    d = _d(date)
    store = _load()
    best = None
    for row in store["issues"]:
        if row.get("unrecovered"):
            continue
        if _d(row["knowable_from"]) <= d and (best is None or row["issue_date"] > best["issue_date"]):
            best = row
    if best is None:
        return None
    _require(_d(best["knowable_from"]) <= d,
             f"issue {best['issue_date']} served at {d} before knowable_from {best['knowable_from']}")
    _require(_d(best["issue_date"]) < d, f"issue {best['issue_date']} served same-day/future at {d}")
    week_end = _d(best["week_ending"])
    # latest issue that carried LIVE S/D levels (may be older than `best` in the dead span)
    lvl = None
    for row in store["issues"]:
        if row.get("unrecovered") or not row.get("sd_live"):
            continue
        if _d(row["knowable_from"]) <= d and (lvl is None or row["issue_date"] > lvl["issue_date"]):
            lvl = row
    latest_sd = None
    if lvl is not None:
        _require(_d(lvl["knowable_from"]) <= d,
                 f"sd-level issue {lvl['issue_date']} served at {d} before knowable_from {lvl['knowable_from']}")
        latest_sd = {"issue_date": lvl["issue_date"], "week_ending": lvl["week_ending"],
                     "age_days": (d - _d(lvl["week_ending"])).days,
                     "attribution": lvl.get("attribution")}
        for k in E1_ANCHORS:
            v = lvl["fields"].get(k)
            latest_sd[k + "_bcfd"] = v.get("level_bcfd") if isinstance(v, dict) else None
            latest_sd[k + "_wow_stated_bcfd"] = v.get("wow_stated_bcfd") if isinstance(v, dict) else None
            latest_sd[k + "_wow_stated_pct"] = v.get("wow_stated_pct") if isinstance(v, dict) else None
    out = {
        "asof": _iso(d),
        "issue_date": best["issue_date"],
        "era": best["era"],
        "week_ending": best["week_ending"],
        "week_span": best["week_span"],
        "knowable_from": best["knowable_from"],
        "sd_live": best.get("sd_live", False),
        "age_days": (d - week_end).days,
        "issue_age_days": (d - _d(best["issue_date"])).days,
        "attribution": best.get("attribution"),
        "source_url": best.get("source_url"),
        "lng_vessels_departed": best.get("lng_vessels_departed"),
        "lng_vessel_capacity_bcf": best.get("lng_vessel_capacity_bcf"),
        "vessels_attribution": best.get("vessels_attribution"),
        "latest_sd_levels": latest_sd,
        "note": "; ".join(best.get("notes", [])) or None,
    }
    for k in E1_ANCHORS:
        v = best["fields"].get(k)
        out[k + "_bcfd"] = v.get("level_bcfd") if isinstance(v, dict) else None
        out[k + "_wow_stated_pct"] = v.get("wow_stated_pct") if isinstance(v, dict) else None
        out[k + "_wow_stated_bcfd"] = v.get("wow_stated_bcfd") if isinstance(v, dict) else None
        out[k + "_wow_computed_bcfd"] = (best.get("computed_wow_bcfd") or {}).get(k)
        if isinstance(v, dict) and v.get("qualifier"):
            out[k + "_qualifier"] = v["qualifier"]
    return out


# ------------------------------------------------------------------ selftest
def cmd_selftest():
    store = _load()
    issues = [r for r in store["issues"] if not r.get("unrecovered")]
    fails = []

    # S1 store integrity
    for r in issues:
        _require(_d(r["knowable_from"]) == _d(r["issue_date"]) + timedelta(days=1),
                 f"knowable_from != issue+1 on {r['issue_date']}")
        span = r.get("week_span")
        _require(span and (_d(span[1]) - _d(span[0])).days == 6, f"week span not 7 days on {r['issue_date']}")
        _require(_d(r["week_ending"]).weekday() == 2, f"week_ending not Wednesday on {r['issue_date']}")
    weeks = [r["week_ending"] for r in issues]
    _require(len(weeks) == len(set(weeks)), "duplicate report weeks")
    n1 = sum(1 for r in issues if r["era"] == 1)
    n2 = sum(1 for r in issues if r["era"] == 2)
    live = [r for r in issues if r["era"] == 1 and r.get("sd_live")]
    dead = [r for r in issues if r["era"] == 1 and not r.get("sd_live")]
    print(f"S1 OK: {len(issues)} issues ({n1} era-1: {len(live)} S/D-live + {len(dead)} S/D-dead; {n2} era-2); "
          f"weeks unique; spans Thu->Wed; knowable_from = release+1 everywhere")

    # S2 blind-wall audit: full asof sweep + per-issue same-day refusal
    d0, d1 = _d("2025-08-25"), max(_d(r["knowable_from"]) for r in issues) + timedelta(days=7)
    viol = evals = 0
    d = d0
    while d <= d1:
        out = ngwu_asof(d)   # in-code _require would raise on any violation
        evals += 1
        if out is not None:
            if _d(out["knowable_from"]) > d or _d(out["issue_date"]) >= d:
                viol += 1
            ls = out.get("latest_sd_levels")
            if ls and _d(ls["issue_date"]) >= d:
                viol += 1
        d += timedelta(days=1)
    for r in issues:
        out = ngwu_asof(r["issue_date"])  # release day itself: this issue must NOT be visible
        evals += 1
        if out is not None and out["issue_date"] == r["issue_date"]:
            viol += 1
        out2 = ngwu_asof(r["knowable_from"])  # day after: must be visible (it is the newest)
        evals += 1
        if out2 is None or out2["issue_date"] < r["issue_date"]:
            viol += 1
    print(f"S2 blind-wall audit: {viol} violations over {evals} asof evaluations "
          f"({(d1 - d0).days + 1} daily sweeps + {2 * len(issues)} boundary probes)")
    if viol:
        fails.append("blind wall")

    # S3 cross-checks
    # (a) within-issue dual display of LNG feedgas (demand paragraph vs LNG section)
    na = ok_a = bad_a = 0
    for r in live:
        f1, f2 = r["fields"].get("lng_feedgas"), r["fields"].get("lng_feedgas_lng_section")
        if isinstance(f1, dict) and isinstance(f2, dict) and \
                f1.get("level_bcfd") is not None and f2.get("level_bcfd") is not None:
            if abs(f1["level_bcfd"] - f2["level_bcfd"]) <= 0.051:
                ok_a += 1
            else:
                bad_a += 1
                print(f"   S3a MISMATCH {r['issue_date']}: demand-display {f1['level_bcfd']} vs LNG-display {f2['level_bcfd']}")
        else:
            na += 1
    print(f"S3a feedgas dual-display (same week, two displays on the page): {ok_a} agree, {bad_a} mismatch, {na} not-comparable")
    if bad_a:
        fails.append("S3a")

    # (b) chain check: prior issue level + this issue's stated delta ~= this issue level.
    #     A miss that is INTERNALLY consistent (stated pct * implied prior ~= stated delta) is a
    #     SOURCE prior-week revision (S&P revised last week's estimate between publications) -
    #     named as a vintage finding, not a parse failure. Only internal inconsistency fails.
    ok_b = bad_b = rev_b = 0
    pairs = []
    for i in range(1, len(issues)):
        cur, prev = issues[i], issues[i - 1]
        if not (cur["era"] == 1 and cur.get("sd_live") and prev.get("sd_live")):
            continue
        if (_d(cur["week_ending"]) - _d(prev["week_ending"])).days != 7:
            continue
        for k in ("dry_production", "lng_feedgas"):
            a, b = cur["fields"].get(k), prev["fields"].get(k)
            if isinstance(a, dict) and isinstance(b, dict) and None not in \
                    (a.get("level_bcfd"), b.get("level_bcfd"), a.get("wow_stated_bcfd")):
                err = abs(b["level_bcfd"] + a["wow_stated_bcfd"] - a["level_bcfd"])
                pairs.append((cur["issue_date"], k, err))
                if err <= 0.151:  # both legs printed at 0.1 Bcf/d resolution
                    ok_b += 1
                    continue
                implied_prior = a["level_bcfd"] - a["wow_stated_bcfd"]
                pct = a.get("wow_stated_pct")
                internally_ok = (pct is not None and implied_prior > 0 and
                                 abs(abs(a["wow_stated_bcfd"]) - abs(pct) / 100.0 * implied_prior) <= 0.11)
                if internally_ok:
                    rev_b += 1
                    print(f"   S3b VINTAGE FINDING {cur['issue_date']} {k}: implied prior {implied_prior:.1f} vs "
                          f"as-printed prior {b['level_bcfd']:.1f} - the source revised last week's estimate "
                          f"between publications (internally consistent, parse verified)")
                else:
                    bad_b += 1
                    print(f"   S3b MISMATCH {cur['issue_date']} {k}: prev {b['level_bcfd']} + stated {a['wow_stated_bcfd']} != {a['level_bcfd']} (err {err:.2f}, not internally consistent)")
    print(f"S3b cross-issue chain (issue N-1 level + issue N stated w/w vs issue N level): "
          f"{ok_b} agree, {rev_b} source-revision findings (named), {bad_b} parse mismatches over {len(pairs)} checks")
    if bad_b:
        fails.append("S3b")

    # (c) the frozen sample in the dead issues vs the last live issue (corroboration display)
    samples = store["meta"].get("stale_template_samples") or {}
    last_live = live[-1] if live else None
    if last_live and samples:
        keys_chk = ["dry_production", "lng_feedgas", "industrial"]
        agree = []
        for ds, s in sorted(samples.items()):
            comp = []
            for k in keys_chk:
                lv = (last_live["fields"].get(k) or {}).get("level_bcfd")
                sv = (s.get(k) or {}).get("level_bcfd")
                if lv is not None and sv is not None:
                    comp.append((k, lv, sv, abs(lv - sv) < 0.051))
            allok = comp and all(c[3] for c in comp)
            agree.append((ds, allok, comp))
        n_ok = sum(1 for a in agree if a[1])
        print(f"S3c frozen-sample corroboration: {n_ok}/{len(agree)} dead issues carry a commented sample "
              f"matching the last live issue ({last_live['issue_date']}) on production/feedgas/industrial")
        for ds, allok, comp in agree:
            if not allok:
                print(f"   S3c note {ds}: {comp}")

    # (d) era-2 HH-spot bullet vs feed G's DNAV store. NOT the same assessor: the supplement
    #     quotes Natural Gas Intelligence, DNAV is Refinitiv-sourced - so this validates that our
    #     parse reads real prices (agreement within $0.10 on calm days) while divergences are the
    #     MEASURED NGI-vs-Refinitiv assessor spread, named per day. Only an absurd (> $1) gap
    #     fails, since that would indicate a parse error rather than assessor spread.
    if os.path.exists(CASH_STORE):
        cash = json.load(open(CASH_STORE, encoding="utf-8"))
        spot = {r["gas_day"]: r["spot"] for r in cash.get("rows", []) if r.get("spot") is not None}
        ok_d = spread_d = bad_d = na_d = 0
        for r in issues:
            if r["era"] != 2:
                continue
            t = (r.get("sentences") or {}).get("bullets") or ""
            m = re.search(r"from \$(\d+(?:\.\d+)?)/MMBtu last Wednesday to \$(\d+(?:\.\d+)?)/MMBtu", t)
            if not m:
                na_d += 1
                continue
            wk = _d(r["week_ending"])
            checks = [(_iso(wk - timedelta(days=7)), float(m.group(1))), (_iso(wk), float(m.group(2)))]
            for gd, val in checks:
                if gd in spot:
                    gap = abs(spot[gd] - val)
                    if gap <= 0.101:
                        ok_d += 1
                    elif gap <= 1.0:
                        spread_d += 1
                        print(f"   S3d assessor spread {r['issue_date']}: HH {gd} NGI {val} vs Refinitiv/DNAV {spot[gd]} (gap {gap:.2f})")
                    else:
                        bad_d += 1
                        print(f"   S3d MISMATCH {r['issue_date']}: HH {gd} bullet {val} vs DNAV {spot[gd]} - parse-scale error")
        print(f"S3d era-2 HH bullets vs feed G DNAV store: {ok_d} agree within $0.10, {spread_d} NGI-vs-Refinitiv "
              f"spreads (named), {bad_d} parse-scale errors, {na_d} issues without the phrase")
        if bad_d:
            fails.append("S3d")
    else:
        print("S3d skipped: cash_basis store not present")

    # (e) era-2 chain: issue N's "following a X Bcf/d ..." quote of LAST week vs issue N-1's own
    #     stated delta for the same metric (a second archived page quoting the same week's number)
    ok_e = rev_e = bad_e = 0
    e2 = [r for r in issues if r["era"] == 2]
    for i in range(1, len(e2)):
        cur, prev = e2[i], e2[i - 1]
        if (_d(cur["week_ending"]) - _d(prev["week_ending"])).days != 7:
            continue
        for k, q in (cur.get("prior_week_quotes_bcfd") or {}).items():
            pv = prev["fields"].get(k)
            pd = pv.get("wow_stated_bcfd") if isinstance(pv, dict) else None
            if pd is not None:
                if abs(pd - q) <= 0.051:
                    ok_e += 1
                elif (q == 0 and pd != 0) or (pd != 0 and q != 0 and pd * q > 0 and abs(pd - q) / max(abs(pd), abs(q)) <= 0.15):
                    rev_e += 1
                    print(f"   S3e VINTAGE FINDING {cur['issue_date']} {k}: quotes last week {q}, prior issue "
                          f"stated {pd} - same sign, <=15% apart: source revised the estimate between publications")
                else:
                    bad_e += 1
                    print(f"   S3e MISMATCH {cur['issue_date']} {k}: quotes last week {q}, prior issue stated {pd}")
    print(f"S3e era-2 chain (issue N quoting last week's delta vs issue N-1's own statement): "
          f"{ok_e} agree, {rev_e} source-revision findings (named), {bad_e} mismatch")
    if bad_e:
        fails.append("S3e")

    # S4 era boundaries, factually
    print("S4 era boundaries:")
    meta = store["meta"]
    ll, fd = meta.get("sd_last_live_issue"), meta.get("sd_first_dead_issue")
    if ll and fd:
        a = ngwu_asof(_d(ll) + timedelta(days=1))
        b = ngwu_asof(_d(fd) + timedelta(days=1))
        print(f"   S/D content boundary: asof {_iso(_d(ll) + timedelta(days=1))} -> issue {a['issue_date']} sd_live={a['sd_live']} dry_production={a['dry_production_bcfd']} lng_feedgas={a['lng_feedgas_bcfd']}")
        print(f"                         asof {_iso(_d(fd) + timedelta(days=1))} -> issue {b['issue_date']} sd_live={b['sd_live']} dry_production={b['dry_production_bcfd']} (levels None; latest_sd_levels falls back to {b['latest_sd_levels']['issue_date']} age {b['latest_sd_levels']['age_days']}d)")
    for probe in ["2026-01-23", "2026-01-29", "2026-01-30", "2026-02-06"]:
        o = ngwu_asof(probe)
        if o:
            print(f"   asof {probe}: era {o['era']} issue {o['issue_date']} (week ending {o['week_ending']}, issue_age {o['issue_age_days']}d)")
    # vehicle boundary assertions
    o_pre, o_post = ngwu_asof("2026-01-29"), ngwu_asof("2026-01-30")
    if not (o_pre and o_pre["era"] == 1 and o_pre["issue_date"] == "2026-01-22"):
        fails.append("S4 pre-boundary")
    if not (o_post and o_post["era"] == 2 and o_post["issue_date"] == "2026-01-29"):
        fails.append("S4 post-boundary")

    # S5 missing-is-None demonstrations
    print("S5 missing-is-None:")
    o = ngwu_asof("2026-01-02")
    print(f"   asof 2026-01-02 (inside the year-end publication blackout): issue {o['issue_date']} week ending {o['week_ending']} age {o['age_days']}d; skipped report weeks {meta['era1_skipped_report_weeks_ending']} never appear in any row")
    covered = {r["week_ending"] for r in issues}
    for wk in meta["era1_skipped_report_weeks_ending"]:
        _require(wk not in covered, f"skipped week {wk} unexpectedly covered")
    o = ngwu_asof("2026-02-10")
    _require(o["total_consumption_bcfd"] is None and o["era"] == 2, "era-2 asof should have None levels")
    print(f"   asof 2026-02-10 (era 2): total_consumption_bcfd={o['total_consumption_bcfd']} (None - supplement publishes no levels); stated deltas where published: rescomm={o['rescomm_wow_stated_bcfd']} power={o['power_wow_stated_bcfd']} feedgas={o['lng_feedgas_wow_stated_bcfd']}; latest S/D levels are {o['latest_sd_levels']['issue_date']} (age {o['latest_sd_levels']['age_days']}d)")

    print("SELFTEST", "FAIL: " + ", ".join(fails) if fails else "PASS")
    return 1 if fails else 0


# ------------------------------------------------------------------ display helpers
def cmd_show(date):
    print(json.dumps(ngwu_asof(date), indent=1))


def cmd_table():
    store = _load()
    hdr = f"{'issue':<11}{'wk_end':<11}{'era':<4}{'sd':<5}{'prod':>7}{'cons':>7}{'power':>7}{'ind':>6}{'resc':>6}{'mex':>6}{'canada':>7}{'lng':>6}{'vessels':>8}{'cap':>6}"
    print(hdr)
    for r in store["issues"]:
        if r.get("unrecovered"):
            print(f"{r['issue_date']:<11}  UNRECOVERED: {'; '.join(r.get('notes', []))}")
            continue

        def cell(k, item="level_bcfd"):
            v = r["fields"].get(k)
            x = v.get(item) if isinstance(v, dict) else None
            return "-" if x is None else f"{x:g}"

        def wow(k):
            v = r["fields"].get(k)
            x = v.get("wow_stated_bcfd") if isinstance(v, dict) else None
            return "-" if x is None else f"{x:+g}"
        print(f"{r['issue_date']:<11}{r['week_ending']:<11}{r['era']:<4}{str(r.get('sd_live'))[:1]:<5}"
              f"{cell('dry_production'):>7}{cell('total_consumption'):>7}{cell('power'):>7}{cell('industrial'):>6}"
              f"{cell('rescomm'):>6}{cell('mexico_exports'):>6}{cell('net_canada_imports'):>7}{cell('lng_feedgas'):>6}"
              f"{str(r.get('lng_vessels_departed') or '-'):>8}{str(r.get('lng_vessel_capacity_bcf') or '-'):>6}"
              f"   wow(prod {wow('dry_production')}, cons {wow('total_consumption')}, lng {wow('lng_feedgas')})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show", metavar="DATE")
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()
    if a.fetch:
        cmd_fetch(refresh=a.refresh)
    if a.build:
        cmd_build()
    if a.selftest:
        sys.exit(cmd_selftest())
    if a.show:
        cmd_show(a.show)
    if a.table:
        cmd_table()
    if not any([a.fetch, a.build, a.selftest, a.show, a.table]):
        ap.print_help()


if __name__ == "__main__":
    main()
