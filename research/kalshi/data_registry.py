#!/usr/bin/env python3
"""
data_registry.py - THE MASTER LIST OF EVERY DATA POINT WE HAVE. (Registry A-22.)

THE ASK (Greg, S112), verbatim: "list aaaaaallllll of our data points that we have available, no
matter how big or small and no matter if we are currently using all of them. There should be a
master list because we are collecting a lot and we've already left out some of literally our most
important ones on multiple runs."

HE IS DESCRIBING A MEASURED FAILURE, NOT A WORRY. Four instances, every one paid for:
  - 0629, the desk's cleanest documented miss: `wind_mwh` was SERVED IN EVERY SLICE and read by
    nobody. gw_cdd rose exactly as forecast and gas burn FELL 4.2 Bcf/d because wind rose 62%.
  - `coal_mwh` and `nuclear_mwh`: served across US48 and six BAs, referenced by ZERO plays.
  - EIA-930's hydro (`WAT`): FETCHED since 2019 and dropped at a five-element serving list, so the
    stack's third forcing has never reached a specialist (A-16).
  - `gw_precip`: computed, gas-weighted, emitted daily, named once in the brain in a field list.
And two where a correct value was destroyed rather than merely ignored: S107's `big_print_b_share`
(size-weighted computed, then omitted from the emit list, the count-based one shadowing it under the
same name) and S109's `session_b_share` (the one b_share field missing from `_tape_enrich`'s copy
list). A hand-maintained list of fields is where correct data goes to die quietly.

WHY A REGISTRY FIXES IT AND A REMINDER DOES NOT. Every one of these is invisible to `state_health`,
which asks "is the block present, numeric, in range, self-consistent" - and all of them ARE. The
question none of our gates asked is the only one that catches this class: DOES ANYTHING READ IT.
That is computable, so it becomes a report instead of a memory.

WHAT COUNTS AS A DATA POINT HERE: every leaf served into the decision state - numeric, string and
boolean alike. Greg said "no matter how big or small", and a regime LABEL or a boolean flag is a
data point even though `brain_conditions.vocabulary()` deliberately excludes it (a condition is a
bar on a quantity, so that tool wants numerics only). This is the wider list on purpose.

READER COUNTING - the method, stated because it bounds the claim. A field is "read" if its name
occurs anywhere in ng_brain.json: a play condition, a mechanism, an instance, a doctrine line. That
OVER-counts (a mention in prose is not a consumer) and cannot under-count. So a ZERO here is hard
evidence of no reader; a small non-zero is a prompt to look, never a clean bill.

USAGE
    python data_registry.py build            # dry run - what the master list would contain
    python data_registry.py build --write    # store/data_points.json + DATA_POINTS.md
    python data_registry.py unread           # THE MONEY VIEW: served, and nothing reads it
    python data_registry.py selftest
"""

import argparse
import json
import os
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
STATE_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
STORE = os.path.join(HERE, "store", "data_points.json")
RENDER = os.path.join(ROOT, "DATA_POINTS.md")

OPEN_ITEMS = os.path.join(HERE, "OPEN_ITEMS.json")

# THE FOUR TIERS. Greg, S112: "no matter if we are currently using all of them... even the stuff we
# haven't started collecting yet but are going to." A list of only what we serve would have shown
# 0629's wind_mwh as present and healthy; a list of only what we HOLD would still have missed hydro.
TIERS = OrderedDict([
    ("SERVED", "reaches a specialist in the decision state"),
    ("HELD_NOT_SERVED", "we already have it and it is dropped before serving - the 0629 class"),
    ("PLANNED", "committed to in the work registry, not yet collected"),
    ("IDENTIFIED", "named as available by research, no registry item yet - the weakest tier, and "
                   "the one where a good source gets forgotten"),
])

# Blocks that the blind DELIBERATELY sees frozen at the anchor vintage. Read from the harness rather
# than asserted, so a change there cannot leave this list quietly wrong.
PRICE_DERIVED_BLOCKS = ("contract_structure", "squeeze_watch", "vol_regime", "cash_basis",
                        "options_surface")

# Block -> upstream provider and cadence. The FEED MODULE is derived from the tree, not listed here;
# what a machine cannot derive is who publishes it and how often, which is what this supplies.
BLOCK_SOURCE = {
    "weather": ("NWS/IEM ASOS observations", "daily, T+1"),
    "weather_forecast": ("NWS MOS (GFS/NAM/MEX) via the IEM archive", "per model cycle"),
    "weather_forecast_cycle": ("MOS cycle timing - which run was available at decision time",
                               "per cycle"),
    "freeze_risk": ("station-level freeze-off proxy off the same ASOS obs", "daily"),
    "solar": ("solar geometry + EIA-930 solar generation", "daily"),
    "grid_stack": ("EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel",
                   "daily, wall = period+2"),
    "nuclear_outages": ("NRC daily reactor status", "daily, age 1d"),
    "storage": ("EIA weekly working gas in storage", "weekly Thu 10:30 ET"),
    "storage_regional": ("EIA regional + salt/non-salt storage", "weekly"),
    "storage_vintage": ("EIA storage as-of each vintage - the revision process", "weekly"),
    "storage_consensus": ("street consensus for the storage print", "weekly, pre-print"),
    "stor_surprise": ("actual minus consensus", "weekly"),
    "steo_vintage": ("EIA STEO monthly archived workbooks - the complete balance as-of release",
                     "monthly, 1-34d stale"),
    "ngwu_balance": ("EIA Natural Gas Weekly Update. LIVE RISK: final edition was the week ending "
                     "2026-01-21", "weekly - DISCONTINUED"),
    "cash_basis": ("Henry Hub cash vs front-futures settle", "weekly batches"),
    "cot": ("CFTC Commitments of Traders, futures and ICE HH", "weekly Fri, suspended in shutdowns"),
    "contract_structure": ("CME definitions + forward curve, calendar-front pair", "daily"),
    "options_surface": ("NG options settle IV surface, ON/LNE roots", "daily settle"),
    "vol_regime": ("realized vol regime derived from the tape", "daily"),
    "squeeze_watch": ("expiry/OI/positioning conjunction detector", "daily"),
    "tape_conditions": ("Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED",
                        "per session"),
    "flow_calendar": ("exchange + index calendar: roll, BCOM, expiry, holidays", "static rules"),
    "model_disagreement": ("cross-model spread between MOS families", "per cycle"),
    "model_cycles_et": ("model run times in ET", "static"),
    "curve_regime": ("backwardation/contango label off the forward curve", "daily"),
    "holiday": ("CME holiday table - HARDCODED, ends 2027-02-15 (A-14)", "static, 194d runway"),
    "dow": ("day of week", "derived"),
    "firehose_present": ("whether the MBO firehose reached this day", "per day"),
    "frozen_structure_stale": ("staleness flag on the one-shot mask", "per day"),
    "note": ("free-text annotation, not a quantity", "-"),
}

# IDENTIFIED but not committed - named as available and free by our own research, with no registry
# item. The weakest tier by construction, and therefore the one this file exists to stop losing.
IDENTIFIED_NOT_COMMITTED = [
    {"field": "ECMWF ensemble members (all 51)", "source": "ECMWF open data, CC-BY since 2025-10-01",
     "why": "dispersion is the part of the forecast that survives past the 5-7 day horizon where "
            "directional level forecasting dies (S111 horizon briefing)"},
    {"field": "GEFS ensemble members", "source": "NOAA NOMADS/AWS open data, free",
     "why": "same as above, and it is the American counterpart we can cross-check against"},
    {"field": "ERCOT NP3-233-CD planned outages", "source": "ERCOT MIS, free",
     "why": "168-hour hourly forward outage postings - forward-dated supply (A-17's pair)"},
    {"field": "PJM frcstd_gen_outages", "source": "PJM Data Miner 2, free",
     "why": "90-day forward generation outage forecast in the largest gas-burning BA"},
    {"field": "FERC hydro licence articles: guide curves, minimum flows, drought plans",
     "source": "FERC eLibrary, free (Wallace Dam is P-2413; Catawba-Wateree and Rocky Mountain "
               "have public relicensing dockets)",
     "why": "a licensee's reservoir future is partly a LEGAL CONSTRAINT, dated and binding - "
            "arguably more forecastable than TVA's discretion (A-20)"},
    {"field": "USACE district water-management daily reservoir and spill data",
     "source": "USACE water control pages, free",
     "why": "the agency that orders the gates open; the flood-spill tail of the inverted U"},
    {"field": "utility IRP weather-normalization station lists",
     "source": "state PUC dockets (NCUC E-100, SC PSC), free",
     "why": "an expert candidate station set per service territory, with a 30-year normal "
            "recomputed annually (A-19)"},
    {"field": "EIA-930 day-ahead demand forecast for BAs we do not yet serve",
     "source": "EIA-930, already-pulled route",
     "why": "the only free forward load number in the non-ISO Southeast; per-BA coverage must be "
            "checked rather than assumed"},
    {"field": "Kalshi expiration_value (the settle print)", "source": "Kalshi public API, free",
     "why": "verified S99 as the settle print itself - ground truth for scoring the product we "
            "actually trade"},
]

# Fields we demonstrably PULL and then DROP before serving. Each carries the citation that proves
# it, because an unproven claim here would be worse than an absent one - it would look like coverage.
PULLED_NOT_SERVED = [
    {"field": "grid_stack gen_mwh['WAT'] (hydro, per BA)",
     "source": "EIA-930 daily-fuel-type-data",
     "proof": "grid_stack.py sets no fueltype facet, so every fuel EIA reports is stored under "
              "gen_mwh[fueltype]; _ba_read (grid_stack.py:180-181) hand-picks NG/SUN/WND/COL/NUC. "
              "The 6.7-7.6% of US48 generation that the five named fields leave unaccounted IS "
              "these dropped fuels - total_gen_mwh sums all of them.",
     "held_since": "2019-01-01", "item": "A-16"},
    {"field": "grid_stack gen_mwh['OIL'] and ['OTH'] (per BA)",
     "source": "EIA-930 daily-fuel-type-data",
     "proof": "same serving list as WAT above", "held_since": "2019-01-01", "item": "A-16"},
    {"field": "grid_stack demand/gen for TVA, CPLE, CPLW, DUK, FPL, SCEG",
     "source": "EIA-930 - every BA is a reportable respondent",
     "proof": "grid_stack.RESPONDENTS is a 7-element list: US48, ERCO, CISO, MISO, PJM, SWPP, SOCO. "
              "The Southeast is the largest summer-burn region and we carry one of its six BAs.",
     "held_since": "not pulled - a list edit away", "item": "A-18"},
    {"field": "nws_hourly raw observations (every field, every ob)",
     "source": "NWS/IEM ASOS via nws_temp_feed --ingest-hourly",
     "proof": "ingested to nws_hourly/ by design (S90, 'the daily degree-day store was the same "
              "reduction mistake'), but degree_days() still takes a DAILY MEAN, so the diurnal "
              "peak that actually sets AC load is collapsed before it is served.",
     "held_since": "S90", "item": "A-21"},
    {"field": "dew point / wet bulb / relative humidity",
     "source": "present in the raw ASOS obs we already ingest",
     "proof": "dewpoint, wet_bulb and humidity occur ZERO times in ng_brain.json. Southern cooling "
              "load answers to wet bulb, so a rainy day cancels less than dry bulb implies.",
     "held_since": "S90 (raw)", "item": "A-21"},
]

# Named ABSENT - not held anywhere, so no amount of serving discipline reaches them. Listed because
# a master list that only covers what we have cannot show what is missing, and the missing ones are
# what Greg is actually guarding against.
KNOWN_ABSENT = [
    {"field": "forward wind / solar generation forecast", "item": "G-4",
     "why": "net load is uncomputable FORWARD without it; only realized wind_mwh/solar_mwh exist"},
    {"field": "forward nuclear planned-outage schedule", "item": "A-17",
     "why": "the most schedulable event in the power system, posted 12-18 months ahead, and we "
            "read only realized nuclear_outages.*"},
    {"field": "river stage / reservoir elevation / spill", "item": "A-16 + A-18",
     "why": "without it hydro output cannot carry a sign - flood spill and drought drawdown give "
            "the same low reading (the inverted U)"},
    {"field": "coal headroom: EIA-860M additions/retirements, ISO outage aggregates", "item": "M-6",
     "why": "the retirement calendar is forward-dated, which survives past the weather horizon"},
    {"field": "LNG feedgas (lng_feedgas_bcfd)", "item": "M-5",
     "why": "null and 278 days stale. Gulf-coast feedgas is the most HH-COUPLED demand there is "
            "(D35), so this hole is larger than its size suggests"},
    {"field": "chain state served to the blind (cum_from_anchor, chain age)", "item": "A-11",
     "why": "unblocks nine plays; four of eight curation batches hit it independently"},
    {"field": "zero-change and seasonal-normal baselines", "item": "A-1",
     "why": "no error number is readable without a named benchmark (S111)"},
]


DATA_WORDS = ("feed", "ingest", "serve", "serving", "pull", "publish", "published", "collect",
              "eia", "usgs", "usace", "nrc", "ferc", "noaa", "ecmwf", "api", "forecast", "schedule",
              "station", "data", "series", "field")


def planned_from_registry():
    """PLANNED data harvested from OPEN_ITEMS.json rather than hand-listed, so registering an item
    puts its data on this list automatically and cannot be forgotten separately.

    Deliberately OVER-INCLUSIVE: an item is data-acquisition if its text uses any acquisition word.
    Omission is the failure mode this file exists to end, so a few analysis items appearing here
    costs nothing while a missing feed costs a run."""
    try:
        with open(OPEN_ITEMS, encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for it in reg.get("items", []):
        if it.get("status") not in ("OPEN", "IN_PROGRESS"):
            continue
        text = (it.get("title", "") + " " + it.get("why", "")).lower()
        hits = sorted({w for w in DATA_WORDS if w in text})
        if not hits:
            continue
        out.append(OrderedDict([
            ("item", it["id"]), ("status", it.get("status")), ("size", it.get("size")),
            ("title", it.get("title", "")),
            ("blocked_by", it.get("blocked_by")),
            ("acquisition_terms", hits[:6]),
        ]))
    return out


def _leaf_kind(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    return None


def _walk(obj, prefix, out):
    """Every leaf, including strings and booleans. Wider than brain_conditions.vocabulary() on
    purpose - that one wants quantities a bar can be written on; this one wants everything we hold."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue                      # _mask_note and friends are annotations
            _walk(v, "%s.%s" % (prefix, k) if prefix else str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:4]):
            _walk(v, "%s[%d]" % (prefix, i), out)
    else:
        kind = _leaf_kind(obj)
        if kind:
            rec = out.setdefault(prefix, {"kind": kind, "n": 0, "n_null": 0})
            rec["n"] += 1
        elif obj is None:
            rec = out.setdefault(prefix, {"kind": "null-only", "n": 0, "n_null": 0})
            rec["n_null"] += 1


def state_files():
    if not os.path.isdir(STATE_DIR):
        return []
    return sorted(os.path.join(STATE_DIR, f) for f in os.listdir(STATE_DIR)
                  if f.startswith("grp") and f.endswith("_state.json"))


def _gnum(path):
    b = os.path.basename(path)
    return b[3:b.index("_state")]


def survey():
    """Every served leaf, the groups carrying it, and how often it is populated."""
    fields = OrderedDict()
    for sf in state_files():
        g = _gnum(sf)
        try:
            with open(sf, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            continue
        days = st.get("days") or st
        if not isinstance(days, dict):
            continue
        for day in days.values():
            if not isinstance(day, dict):
                continue
            out = {}
            _walk(day, "", out)
            for path, rec in out.items():
                e = fields.setdefault(path, {"kind": rec["kind"], "groups": set(),
                                             "days_present": 0, "days_null": 0})
                e["groups"].add(g)
                e["days_present"] += rec["n"]
                e["days_null"] += rec["n_null"]
                if e["kind"] == "null-only" and rec["kind"] != "null-only":
                    e["kind"] = rec["kind"]
    return fields


def defects_by_quantity():
    """Attach every known defect to the quantities it damaged, so a field's history travels with it.
    A field that was silently wrong for five groups is not the same field as one that never was."""
    try:
        sys.path.insert(0, HERE)
        import defect_timeline
        out = {}
        for d in defect_timeline.DEFECTS:
            for q in d.get("quantities", []):
                out.setdefault(q, []).append(OrderedDict([
                    ("id", d["id"]), ("found", d["found"]), ("repair", d["repair"]),
                    ("groups", d.get("groups", [])), ("what", d["what"])]))
        return out
    except Exception:
        return {}


def readers(fields):
    """How many times the brain names each field. OVER-counts by construction (prose mentions
    count), so a zero is hard and a small number is only a prompt to look."""
    with open(BRAIN, encoding="utf-8") as f:
        text = f.read()
    out = {}
    for path in fields:
        leaf = path.split(".")[-1].split("[")[0]
        out[path] = text.count(leaf) if len(leaf) > 3 else 0
    return out


def build():
    fields = survey()
    rd = readers(fields)
    rows = []
    for path, e in fields.items():
        rows.append(OrderedDict([
            ("path", path), ("kind", e["kind"]),
            ("groups", sorted(e["groups"], key=lambda x: int(x) if x.isdigit() else 99)),
            ("days_populated", e["days_present"]), ("days_null", e["days_null"]),
            ("brain_mentions", rd[path]),
            ("read", "NOT READ" if rd[path] == 0 else "READ"),
            ("status", "SERVED_UNREAD" if rd[path] == 0 else "SERVED"),
        ]))
    rows.sort(key=lambda r: (r["brain_mentions"] != 0, r["path"]))
    dfx = defects_by_quantity()
    for r in rows:
        blk = r["path"].split(".")[0].split("[")[0]
        src, cadence = BLOCK_SOURCE.get(blk, ("(source not yet declared - declare it)", "-"))
        r["block"] = blk
        r["upstream_source"] = src
        r["cadence"] = cadence
        r["blind_sees"] = ("FROZEN at anchor vintage (price-derived)" if blk in PRICE_DERIVED_BLOCKS
                           else "NEVER MASKED" if blk == "tape_conditions" else "live")
        hits = dfx.get(blk, []) + dfx.get(r["path"].split(".")[-1].split("[")[0], [])
        seen, uniq = set(), []
        for h in hits:
            if h["id"] not in seen:
                seen.add(h["id"]); uniq.append(h)
        r["known_defects"] = uniq
    return OrderedDict([
        ("note", "THE MASTER DATA-POINT LIST. Greg, S112: 'list aaaaaallllll of our data points... "
                 "no matter if we are currently using all of them... we've already left out some of "
                 "literally our most important ones on multiple runs.' Generated - never hand-kept, "
                 "because a hand-kept field list is precisely what failed (0629's wind_mwh, coal_mwh, "
                 "nuclear_mwh, hydro, gw_precip). READER COUNT OVER-COUNTS by design: any occurrence "
                 "of the leaf name in ng_brain.json counts, so a ZERO is hard evidence of no reader "
                 "and a small non-zero is only a prompt to look."),
        ("generated_by", "research/kalshi/data_registry.py build --write"),
        ("state_source", os.path.relpath(STATE_DIR, ROOT)),
        ("n_served", len(rows)),
        ("n_served_unread", sum(1 for r in rows if r["status"] == "SERVED_UNREAD")),
        ("served", rows),
        ("tiers", TIERS),
        ("blocks", OrderedDict((b, OrderedDict([("upstream_source", BLOCK_SOURCE.get(b, ("(not declared)", "-"))[0]),
                                                ("cadence", BLOCK_SOURCE.get(b, ("-", "-"))[1]),
                                                ("blind_sees", "FROZEN at anchor vintage (price-derived)"
                                                 if b in PRICE_DERIVED_BLOCKS else
                                                 "NEVER MASKED" if b == "tape_conditions" else "live"),
                                                ("n_fields", sum(1 for p in fields
                                                                 if p.split(".")[0].split("[")[0] == b)),
                                                ("n_not_read", sum(1 for r in rows
                                                                   if r["block"] == b and r["read"] == "NOT READ"))]))
                               for b in sorted({p.split(".")[0].split("[")[0] for p in fields}))),
        ("pulled_not_served", PULLED_NOT_SERVED),
        ("planned_from_registry", planned_from_registry()),
        ("identified_not_committed", IDENTIFIED_NOT_COMMITTED),
        ("known_absent", KNOWN_ABSENT),
    ])


def render(store):
    L = ["# DATA POINTS - the master list", "",
         "Generated by `python research/kalshi/data_registry.py build --write`. Do not hand-edit:",
         "a hand-kept field list is exactly what failed (0629's `wind_mwh` served in every slice and",
         "read by nobody; `coal_mwh` and `nuclear_mwh` with zero readers; hydro fetched since 2019",
         "and dropped at a five-element serving list; `gw_precip` computed daily and named once).", "",
         "**Reader count over-counts by construction** - any occurrence of the leaf name anywhere in",
         "`ng_brain.json` counts, including prose. So a **zero is hard evidence of no reader**, and a",
         "small non-zero is a prompt to look, never a clean bill.", "",
         "| | count |", "|---|---|",
         "| served data points | %d |" % store["n_served"],
         "| **served and READ BY NOTHING** | **%d** |" % store["n_served_unread"],
         "| HELD but not served | %d |" % len(store["pulled_not_served"]),
         "| PLANNED (from the work registry) | %d |" % len(store["planned_from_registry"]),
         "| IDENTIFIED, not committed | %d |" % len(store["identified_not_committed"]),
         "| named ABSENT | %d |" % len(store["known_absent"]),
         "| source blocks | %d |" % len(store["blocks"]), "",
         "## SERVED AND READ BY NOTHING", "",
         "The 0629 class. Present, numeric, correct, in every slice - and no consumer.", "",
         "| path | kind | groups | days populated |", "|---|---|---|---|"]
    for r in store["served"]:
        if r["status"] != "SERVED_UNREAD":
            continue
        L.append("| `%s` | %s | %s | %d |"
                 % (r["path"], r["kind"], ",".join(r["groups"]) or "-", r["days_populated"]))
    L += ["", "## PULLED BUT NOT SERVED", "",
          "Held or one list-edit away, and never reaching a specialist. Each carries its proof.", "",
          "| field | source | held since | item |", "|---|---|---|---|"]
    for p in store["pulled_not_served"]:
        L.append("| %s | %s | %s | %s |" % (p["field"], p["source"], p["held_since"], p["item"]))
    L += ["", "## NAMED ABSENT", "",
          "Not held anywhere, so no serving discipline reaches them. A master list of what we have",
          "cannot show what is missing, and the missing ones are what this registry guards against.", "",
          "| field | why it matters | item |", "|---|---|---|"]
    for k in store["known_absent"]:
        L.append("| %s | %s | %s |" % (k["field"], k["why"], k["item"]))
    L += ["", "## PLANNED - committed in the work registry, not yet collected", "",
          "Harvested from `OPEN_ITEMS.json`, never hand-listed: registering an item puts its data",
          "here automatically. Deliberately over-inclusive - omission is the failure mode.", "",
          "| item | size | status | title |", "|---|---|---|---|"]
    for p in store["planned_from_registry"]:
        L.append("| %s | %s | %s | %s |" % (p["item"], p["size"] or "-", p["status"], p["title"]))
    L += ["", "## IDENTIFIED - free and available, no registry item yet", "",
          "The weakest tier by construction, and the one this file exists to stop losing.", "",
          "| field | source | why it matters |", "|---|---|---|"]
    for k in store["identified_not_committed"]:
        L.append("| %s | %s | %s |" % (k["field"], k["source"], k["why"]))
    L += ["", "## THE BLOCKS - where every served field comes from", "",
          "Sorted by UNREAD COUNT, because that is where a triage starts. A high unread count in a",
          "high-cardinality block (`model_disagreement` is a per-station x per-model cross-product)",
          "is very different from an unread count in a small block where every field was meant to",
          "be consumed - `grid_stack` and `weather` are the ones to look at first.", "",
          "| block | fields | NOT READ | upstream source | cadence | what the blind sees |",
          "|---|---|---|---|---|---|"]
    for b, m in sorted(store["blocks"].items(), key=lambda kv: -kv[1]["n_not_read"]):
        L.append("| `%s` | %d | **%d** | %s | %s | %s |"
                 % (b, m["n_fields"], m["n_not_read"], m["upstream_source"], m["cadence"],
                    m["blind_sees"]))
    L += ["", "## EVERY SERVED DATA POINT", "",
          "`defects` names any known defect that damaged this field - a field that was silently",
          "wrong for five groups is not the same field as one that never was.", "",
          "| path | READ? | kind | block | groups | days populated | brain mentions | blind sees | defects |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in store["served"]:
        L.append("| `%s` | **%s** | %s | %s | %s | %d | %d | %s | %s |"
                 % (r["path"], r["read"], r["kind"], r["block"], ",".join(r["groups"]) or "-",
                    r["days_populated"], r["brain_mentions"], r["blind_sees"],
                    ", ".join(d["id"] for d in r["known_defects"]) or "-"))
    return "\n".join(L) + "\n"


def cmd_build(a):
    st = build()
    print("blocks                          : %d" % len(st["blocks"]))
    print("SERVED data points              : %d" % st["n_served"])
    print("  ...and READ BY NOTHING        : %d" % st["n_served_unread"])
    print("HELD but not served             : %d" % len(st["pulled_not_served"]))
    print("PLANNED (from the work registry): %d" % len(st["planned_from_registry"]))
    print("IDENTIFIED, not committed       : %d" % len(st["identified_not_committed"]))
    print("named ABSENT                    : %d" % len(st["known_absent"]))
    if not st["n_served"]:
        print("\nNO STATE FILES FOUND under %s - refusing to write an empty master list."
              % os.path.relpath(STATE_DIR, ROOT))
        return 1
    if not a.write:
        print("\ndry run - nothing written. Re-run with --write.")
        return 0
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1, ensure_ascii=False)
    with open(RENDER, "w", encoding="utf-8") as f:
        f.write(render(st))
    print("\nwrote %s and %s" % (os.path.relpath(STORE, ROOT), os.path.relpath(RENDER, ROOT)))
    return 0


def cmd_unread(a):
    st = build()
    un = [r for r in st["served"] if r["status"] == "SERVED_UNREAD"]
    print("SERVED AND READ BY NOTHING - %d of %d served data points\n" % (len(un), st["n_served"]))
    for r in un:
        print("  %-8s %-52s %-7s g%s"
              % (r["read"], r["path"][:52], r["kind"], ",".join(r["groups"])))
    print("\nPULLED BUT NOT SERVED - %d" % len(st["pulled_not_served"]))
    for p in st["pulled_not_served"]:
        print("  %-58s [%s]" % (p["field"][:58], p["item"]))
    return 0


def cmd_selftest(a):
    res = []

    def check(n, ok):
        res.append(ok)
        print("  %-4s | %s" % ("PASS" if ok else "FAIL", n))

    out = {}
    _walk({"a": {"b": 1.5, "c": "label", "d": True, "e": None, "_note": "skip"}}, "", out)
    check("walks numbers, strings and booleans alike",
          {k: v["kind"] for k, v in out.items()} ==
          {"a.b": "number", "a.c": "string", "a.d": "bool", "a.e": "null-only"})
    check("underscore annotations are not data points", "a._note" not in out)
    check("a bool is not counted as a number", out["a.d"]["kind"] == "bool")
    st = build()
    check("the survey finds a real served field set", st["n_served"] > 200)
    check("reader counting marks at least one field unread", st["n_served_unread"] > 0)
    known = [r for r in st["served"] if r["path"].endswith("coal_mwh")]
    check("the known instances are in the list (coal_mwh present)", len(known) > 0)
    check("every row carries an explicit READ / NOT READ label",
          all(r["read"] in ("READ", "NOT READ") for r in st["served"]))
    check("the label agrees with the mention count",
          all((r["read"] == "NOT READ") == (r["brain_mentions"] == 0) for r in st["served"]))
    check("every block reports how many of its fields are unread",
          all("n_not_read" in m for m in st["blocks"].values()))
    check("render mentions the unread count",
          "served and READ BY NOTHING" in render(st))
    empty = dict(st, n_served=0, served=[])
    check("an empty survey renders without crashing", isinstance(render(empty), str))
    print("\n  %d/%d passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build"); p.add_argument("--write", action="store_true")
    sub.add_parser("unread")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"build": cmd_build, "unread": cmd_unread, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
