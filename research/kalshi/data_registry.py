#!/usr/bin/env python3
"""Canonical DavisAI Markets data-point registry (S123 reconciliation).

The S112-S114 generator was valuable but mixed three different questions:
  * what is served in the decision state;
  * whether the legacy ng_brain names a leaf;
  * what an old OPEN_ITEMS snapshot still called missing.

By S122 those were no longer equivalent.  The current accepted measurement is
1,914 served leaf fields across 44 decision-state blocks, with 1,222 leaves not
named by the legacy brain.  "Unread" is diagnostic only: it is NOT a Frankie
access-control list.  Frankie must receive every possessed, causal-by-cutoff,
non-future-contaminated field.  The future/realized target curve remains masked.

This generator therefore:
  * surveys the current committed decision-state files exactly as before;
  * keeps legacy brain mention counts as a diagnostic column;
  * consumes the S122 progress lock when interpreting OPEN_ITEMS;
  * removes hard-coded gap claims already disproved by current code (hydro,
    forward wind/solar, baselines, GEFS density);
  * refuses --write if the local survey would regress the accepted 1,914/44
    surface, or if it has advanced beyond the lock and the lock has not first
    been deliberately updated.

USAGE
    python data_registry.py build
    python data_registry.py build --write
    python data_registry.py unread
    python data_registry.py selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BRAIN = HERE / "knowledge" / "ng_brain.json"
STATE_DIR = HERE / "renders" / "ng_refine_s95"
STORE = HERE / "store" / "data_points.json"
RENDER = ROOT / "DATA_POINTS.md"
OPEN_ITEMS = HERE / "OPEN_ITEMS.json"
LOCK_PATH = HERE / "frankie_progress_lock_s122.json"

PRICE_DERIVED_BLOCKS = {
    "contract_structure", "squeeze_watch", "vol_regime", "cash_basis", "options_surface"
}

BLOCK_SOURCE = {
    "weather": ("NWS/IEM ASOS observations", "daily, T+1"),
    "weather_forecast": ("NWS MOS / forecast guidance", "per model cycle"),
    "weather_forecast_cycle": ("forecast-cycle availability clock", "per cycle"),
    "weather_forcing_forecast": ("GEFS 31-member gas-weighted forcing + forward wind/solar", "per cycle"),
    "freeze_risk": ("station-level freeze-off proxy", "daily"),
    "solar": ("solar geometry + EIA-930 solar generation", "daily"),
    "grid_stack": ("EIA-930 BA operations: demand, forecast, interchange, generation by fuel", "daily / period+2"),
    "nuclear_outages": ("NRC daily reactor status", "daily"),
    "storage": ("EIA weekly working gas", "weekly"),
    "storage_regional": ("EIA regional + salt/non-salt storage", "weekly"),
    "storage_vintage": ("EIA storage vintage history", "weekly"),
    "storage_consensus": ("pre-print storage consensus", "weekly"),
    "stor_surprise": ("storage actual minus consensus", "weekly"),
    "steo_vintage": ("EIA STEO archived vintages", "monthly"),
    "ngwu_balance": ("legacy EIA NGWU balance family", "discontinued / historical"),
    "cash_basis": ("Henry Hub cash vs front settle", "daily/weekly batches"),
    "cot": ("CFTC COT / ICE HH", "weekly"),
    "contract_structure": ("CME definitions + forward curve", "daily"),
    "options_surface": ("NG options settle IV surface", "daily settle"),
    "vol_regime": ("realized-vol descriptors", "daily"),
    "squeeze_watch": ("expiry/OI/positioning conjunction", "daily"),
    "tape_conditions": ("Databento NYMEX tape prior-session state", "per session"),
    "flow_calendar": ("exchange/index calendar", "static rules"),
    "model_disagreement": ("cross-model weather disagreement", "per cycle"),
}

# Reconciled tiers.  These lists describe current truth, not the S113 state.
HELD_NOT_SERVED = []

# Served additively at provider prefix time rather than baked into the stale
# per-day render survey. Every row is filtered by observation receipt clock.
RUNTIME_ADDITIVE_SERVED = [
    {
        "field": "nws_hourly raw observations",
        "source": "NWS/IEM ASOS via nws_temp_feed --ingest-hourly",
        "item": "A-21",
        "why": "served losslessly as weather_observation_hourly at each causal prefix; full-day realized rollups remain quarantined",
    },
    {
        "field": "ASOS dew point / humidity / apparent-temperature family",
        "source": "raw ASOS observations",
        "item": "A-21",
        "why": "served losslessly inside timestamped weather_observation_hourly raw quantitative values",
    },
]

IDENTIFIED_NOT_COMMITTED = [
    {
        "field": "ECMWF ENS 51-member immutable cycle archive / cross-model density",
        "source": "ECMWF Open Data",
        "why": "research delivered; GEFS 31-member density is already served, so this is the narrower ECMWF archival/cross-check lane",
    },
    {
        "field": "ERCOT/PJM/MISO/SPP public aggregate forward outage products",
        "source": "ISO public products",
        "why": "public aggregate forward capacity information is buildable; do not infer a confidential unit-level nuclear calendar",
    },
    {
        "field": "FERC hydro licence guide curves / minimum flows / drought plans",
        "source": "FERC eLibrary",
        "why": "dated physical constraints can distinguish hydro states beyond already-served WAT generation",
    },
    {
        "field": "USACE/USGS/TVA reservoir, streamflow and spill state",
        "source": "USACE/USGS/TVA public operational data",
        "why": "distinguishes drought drawdown from flood/spill; hydro WAT serving itself is already DONE",
    },
]

KNOWN_ABSENT = [
    {
        "field": "Southeast BA expansion: TVA, CPLE, CPLW, DUK, FPL, SCEG/current successor code",
        "item": "A-18",
        "why": "current grid_stack.RESPONDENTS still contains US48/ERCO/CISO/MISO/PJM/SWPP/SOCO only; verify exact current EIA respondent codes before editing",
    },
    {
        "field": "LNG terminal-boundary feedgas nomination ingest with parser health states",
        "item": "G-7",
        "why": "source research is delivered, but production EBB adapter/point-in-time ingest is not proven in current code",
    },
    {
        "field": "coal structural headroom / EIA-860M additions-retirements + aggregate outage capacity",
        "item": "M-6",
        "why": "forward structural absorber/headroom remains unproved as a served family",
    },
    {
        "field": "chain state served in the canonical decision state (cum_from_anchor / chain age)",
        "item": "A-11",
        "why": "must be verified against current code/state; do not confuse historical handoff chain fields with canonical per-day serving",
    },
    {
        "field": "river/reservoir/spill state beyond served hydro generation",
        "item": "A-20",
        "why": "hydro generation is served; water-state mechanism is a separate richer physical input",
    },
    {
        "field": "exact public unit-level forward nuclear refuelling calendar",
        "item": "A-17",
        "why": "measured public-data gap; use supported aggregate ISO/commission lanes rather than inventing unit dates",
    },
]

TIERS = OrderedDict([
    ("SERVED", "leaf reaches the decision state"),
    ("HELD_NOT_SERVED", "upstream data is held but not yet a canonical served family"),
    ("PLANNED", "effective current work item may add/repair data; historical OPEN alone is not sufficient"),
    ("IDENTIFIED", "researched source or narrower lane not yet proven as a served current family"),
])

DATA_WORDS = (
    "feed", "ingest", "serve", "serving", "pull", "publish", "collect", "eia", "usgs", "usace",
    "nrc", "ferc", "noaa", "ecmwf", "api", "forecast", "schedule", "station", "data", "series", "field"
)


def _lock() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def _effective_item_state(item_id: str, raw_status: str) -> tuple[str, str]:
    """Small local reader of the progress lock; no circular dependency on the checker."""
    lk = _lock()
    tables = (
        ("fully_done", "DONE"),
        ("implemented_do_not_rebuild_evidence_pending", "IMPLEMENTED_EVIDENCE_PENDING"),
        ("partial_not_rebuild", "PARTIAL"),
        ("must_verify_current_code_before_calling_open", "VERIFY_CURRENT_CODE"),
        ("genuine_or_measured_open_after_reconciliation", "OPEN_RECONCILED"),
    )
    for key, state in tables:
        if item_id in lk.get(key, {}):
            return state, lk[key][item_id]
    return raw_status or "UNCLASSIFIED", "no S122/S123 override"


def planned_from_registry() -> list[OrderedDict]:
    try:
        reg = json.loads(OPEN_ITEMS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for it in reg.get("items", []):
        raw = str(it.get("status", ""))
        if raw not in {"OPEN", "IN_PROGRESS"}:
            continue
        iid = str(it.get("id", ""))
        eff, why = _effective_item_state(iid, raw)
        # Implemented mechanisms and completed work are not future data acquisitions.
        if eff in {"DONE", "IMPLEMENTED_EVIDENCE_PENDING"}:
            continue
        text = (str(it.get("title", "")) + " " + str(it.get("why", ""))).lower()
        hits = sorted({w for w in DATA_WORDS if w in text})
        if not hits:
            continue
        out.append(OrderedDict([
            ("item", iid),
            ("historical_status", raw),
            ("effective_status", eff),
            ("size", it.get("size")),
            ("title", it.get("title", "")),
            ("blocked_by", it.get("blocked_by")),
            ("effective_reason", why),
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
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            _walk(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, list):
        # Preserve the historical registry convention so counts remain comparable.
        for i, v in enumerate(obj[:4]):
            _walk(v, f"{prefix}[{i}]", out)
    else:
        kind = _leaf_kind(obj)
        if kind:
            rec = out.setdefault(prefix, {"kind": kind, "n": 0, "n_null": 0})
            rec["n"] += 1
        elif obj is None:
            rec = out.setdefault(prefix, {"kind": "null-only", "n": 0, "n_null": 0})
            rec["n_null"] += 1


def state_files():
    if not STATE_DIR.is_dir():
        return []
    return sorted(p for p in STATE_DIR.iterdir() if p.name.startswith("grp") and p.name.endswith("_state.json"))


def _gnum(path: Path) -> str:
    return path.name[3:path.name.index("_state")]


def survey():
    fields = OrderedDict()
    for sf in state_files():
        g = _gnum(sf)
        try:
            st = json.loads(sf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        days = st.get("days") or st
        if not isinstance(days, dict):
            continue
        for day in days.values():
            if not isinstance(day, dict):
                continue
            found = {}
            _walk(day, "", found)
            for path, rec in found.items():
                e = fields.setdefault(path, {
                    "kind": rec["kind"], "groups": set(), "days_present": 0, "days_null": 0
                })
                e["groups"].add(g)
                e["days_present"] += rec["n"]
                e["days_null"] += rec["n_null"]
                if e["kind"] == "null-only" and rec["kind"] != "null-only":
                    e["kind"] = rec["kind"]
    return fields


def readers(fields):
    text = BRAIN.read_text(encoding="utf-8")
    out = {}
    for path in fields:
        leaf = path.split(".")[-1].split("[")[0]
        out[path] = text.count(leaf) if len(leaf) > 3 else 0
    return out


def defects_by_quantity():
    try:
        sys.path.insert(0, str(HERE))
        import defect_timeline
        out = {}
        for d in defect_timeline.DEFECTS:
            for q in d.get("quantities", []):
                out.setdefault(q, []).append({
                    "id": d["id"], "found": d["found"], "repair": d["repair"],
                    "groups": d.get("groups", []), "what": d["what"],
                })
        return out
    except Exception:
        return {}


def build():
    fields = survey()
    rd = readers(fields)
    dfx = defects_by_quantity()
    rows = []
    for path, e in fields.items():
        block = path.split(".")[0].split("[")[0]
        src, cadence = BLOCK_SOURCE.get(block, ("source declared by owning feed", "feed-specific"))
        hits = dfx.get(block, []) + dfx.get(path.split(".")[-1].split("[")[0], [])
        seen, defects = set(), []
        for h in hits:
            if h["id"] not in seen:
                seen.add(h["id"])
                defects.append(h)
        mentions = rd[path]
        rows.append(OrderedDict([
            ("path", path), ("kind", e["kind"]),
            ("groups", sorted(e["groups"], key=lambda x: int(x) if x.isdigit() else 999)),
            ("days_populated", e["days_present"]), ("days_null", e["days_null"]),
            ("legacy_brain_mentions", mentions),
            ("legacy_read", "NOT READ" if mentions == 0 else "READ"),
            ("status", "SERVED_LEGACY_UNREAD" if mentions == 0 else "SERVED"),
            ("block", block), ("upstream_source", src), ("cadence", cadence),
            ("blind_sees", "FROZEN at anchor vintage (price-derived)" if block in PRICE_DERIVED_BLOCKS
             else "NEVER MASKED" if block == "tape_conditions" else "live/causal policy applies"),
            ("frankie_access", "TARGET_CELL_MANIFEST_DECIDES"),
            ("known_defects", defects),
        ]))
    rows.sort(key=lambda r: (r["legacy_brain_mentions"] != 0, r["path"]))
    blocks = OrderedDict()
    for block in sorted({r["block"] for r in rows}):
        src, cadence = BLOCK_SOURCE.get(block, ("source declared by owning feed", "feed-specific"))
        blocks[block] = OrderedDict([
            ("upstream_source", src), ("cadence", cadence),
            ("blind_sees", "FROZEN at anchor vintage (price-derived)" if block in PRICE_DERIVED_BLOCKS
             else "NEVER MASKED" if block == "tape_conditions" else "live/causal policy applies"),
            ("n_fields", sum(1 for r in rows if r["block"] == block)),
            ("n_legacy_unread", sum(1 for r in rows if r["block"] == block and r["legacy_brain_mentions"] == 0)),
        ])
    lk = _lock()
    accepted = lk["measurement"]
    observed = {"served": len(rows), "decision_state_blocks": len(blocks),
                "served_unread": sum(1 for r in rows if r["legacy_brain_mentions"] == 0)}
    if observed["served"] < accepted["served"] or observed["decision_state_blocks"] < accepted["decision_state_blocks"]:
        measurement_status = "REGRESSED_LOCAL_SURVEY_DO_NOT_WRITE"
    elif observed["served"] > accepted["served"] or observed["decision_state_blocks"] > accepted["decision_state_blocks"]:
        measurement_status = "ADVANCED_SURVEY_UPDATE_LOCK_BEFORE_WRITE"
    else:
        measurement_status = "CURRENT_ACCEPTED_SURVEY"
    return OrderedDict([
        ("note", "Canonical S123 data registry. Legacy brain readership is diagnostic only and never controls Frankie access."),
        ("generated_by", "research/kalshi/data_registry.py build --write"),
        ("state_source", os.path.relpath(STATE_DIR, ROOT)),
        ("measurement_status", measurement_status),
        ("accepted_measurement", accepted),
        ("n_served", observed["served"]),
        ("n_served_unread", observed["served_unread"]),
        ("n_blocks", observed["decision_state_blocks"]),
        ("reader_semantics", "legacy ng_brain name/mention diagnostic; zero does not mean unavailable to Frankie"),
        ("frankie_access_rule", lk["rules"]["frankie_access_rule"]),
        ("served", rows), ("blocks", blocks), ("tiers", TIERS),
        ("held_not_served", HELD_NOT_SERVED),
        ("planned_from_registry", planned_from_registry()),
        ("identified_not_committed", IDENTIFIED_NOT_COMMITTED),
        ("known_absent", KNOWN_ABSENT),
    ])


def render(store):
    lines = [
        "# DATA POINTS - canonical S123 master list", "",
        "Generated by `python research/kalshi/data_registry.py build --write`. Do not hand-edit.", "",
        f"**Accepted current surface:** {store['accepted_measurement']['served']} served leaves / "
        f"{store['accepted_measurement']['decision_state_blocks']} blocks / "
        f"{store['accepted_measurement']['served_unread']} legacy-brain unread.",
        f"**Observed by this generator:** {store['n_served']} / {store['n_blocks']} / {store['n_served_unread']}.",
        f"**Measurement status:** `{store['measurement_status']}`.", "",
        "`legacy unread` means the old `ng_brain.json` does not name the leaf. It does **not** mean Frankie cannot see it.",
        "Frankie access is decided field-by-field by the causal target-cell manifest; future/realized target price remains masked.", "",
        "| tier | count |", "|---|---:|",
        f"| served leaves | {store['n_served']} |",
        f"| legacy-brain unread | {store['n_served_unread']} |",
        f"| held upstream but not canonical-served | {len(store['held_not_served'])} |",
        f"| effective planned/data-related items | {len(store['planned_from_registry'])} |",
        f"| identified narrower lanes | {len(store['identified_not_committed'])} |",
        f"| named absent/measured gaps | {len(store['known_absent'])} |",
        f"| source blocks | {store['n_blocks']} |", "",
        "## NAMED ABSENT / MEASURED GAPS", "",
        "| field | item | why |", "|---|---|---|",
    ]
    for item in store["known_absent"]:
        lines.append(f"| {item['field']} | {item['item']} | {item['why']} |")
    lines += ["", "## HELD UPSTREAM, NOT CANONICAL-SERVED", "", "| field | item | why |", "|---|---|---|"]
    for item in store["held_not_served"]:
        lines.append(f"| {item['field']} | {item['item']} | {item['why']} |")
    lines += ["", "## BLOCKS", "", "| block | leaves | legacy unread | source | blind/causal treatment |",
              "|---|---:|---:|---|---|"]
    for name, meta in sorted(store["blocks"].items(), key=lambda kv: -kv[1]["n_legacy_unread"]):
        lines.append(f"| `{name}` | {meta['n_fields']} | {meta['n_legacy_unread']} | {meta['upstream_source']} | {meta['blind_sees']} |")
    lines += ["", "## EVERY SERVED LEAF", "", "| path | legacy read? | kind | block | days populated | days null | Frankie access |",
              "|---|---|---|---|---:|---:|---|"]
    for row in store["served"]:
        lines.append(f"| `{row['path']}` | **{row['legacy_read']}** | {row['kind']} | {row['block']} | "
                     f"{row['days_populated']} | {row['days_null']} | {row['frankie_access']} |")
    return "\n".join(lines) + "\n"


def _write_guard(store):
    status = store["measurement_status"]
    if status == "REGRESSED_LOCAL_SURVEY_DO_NOT_WRITE":
        raise RuntimeError(
            f"REFUSING TO REGRESS canonical registry: observed {store['n_served']}/{store['n_blocks']} "
            f"below accepted {store['accepted_measurement']['served']}/{store['accepted_measurement']['decision_state_blocks']}"
        )
    if status == "ADVANCED_SURVEY_UPDATE_LOCK_BEFORE_WRITE":
        raise RuntimeError(
            "A newer surface is present. Update frankie_progress_lock_s122.json deliberately before writing; "
            "never advance the canonical count silently."
        )


def cmd_build(args):
    store = build()
    print(f"blocks                          : {store['n_blocks']}")
    print(f"SERVED data points              : {store['n_served']}")
    print(f"  ...legacy brain READS NOTHING : {store['n_served_unread']}")
    print(f"measurement status              : {store['measurement_status']}")
    print(f"HELD upstream/not served        : {len(store['held_not_served'])}")
    print(f"effective PLANNED data items    : {len(store['planned_from_registry'])}")
    print(f"named absent/measured gaps      : {len(store['known_absent'])}")
    if args.write:
        _write_guard(store)
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(store, indent=1) + "\n", encoding="utf-8")
        RENDER.write_text(render(store), encoding="utf-8")
        print(f"WROTE {STORE.relative_to(ROOT)} and {RENDER.relative_to(ROOT)}")
    return 0


def cmd_unread(_args):
    store = build()
    print(f"{store['n_served_unread']} legacy-brain unread leaves (diagnostic only; Frankie access is independent)")
    for row in store["served"]:
        if row["legacy_brain_mentions"] == 0:
            print(row["path"])
    return 0


def cmd_selftest(_args):
    failures = []
    def check(name, cond):
        print(("PASS" if cond else "FAIL") + "  " + name)
        if not cond:
            failures.append(name)

    out = {}
    _walk({"a": {"b": 1, "c": None, "d": True}}, "", out)
    check("walk preserves numeric leaf", out["a.b"]["kind"] == "number")
    check("walk preserves null-only leaf", out["a.c"]["kind"] == "null-only")
    check("bool is not collapsed into number", out["a.d"]["kind"] == "bool")
    store = build()
    check("real served field set exists", store["n_served"] > 200)
    check("legacy unread remains diagnostic", store["n_served_unread"] > 0)
    check("every served row has Frankie manifest disposition", all(r["frankie_access"] == "TARGET_CELL_MANIFEST_DECIDES" for r in store["served"]))
    absent = {x["field"] for x in store["known_absent"]}
    check("forward wind/solar is no longer falsely absent", not any("forward wind / solar generation forecast" in x for x in absent))
    check("zero-change baselines are no longer falsely absent", not any("zero-change" in x for x in absent))
    check("hydro WAT is no longer falsely held-not-served", not any("WAT" in x["field"] for x in store["held_not_served"]))
    check("GEFS is no longer falsely identified-not-committed", not any(x["field"].startswith("GEFS") for x in store["identified_not_committed"]))
    planned_ids = {x["item"] for x in store["planned_from_registry"]}
    check("implemented A-67 harness is not re-planned as data work", "A-67" not in planned_ids)
    check("implemented A-69 harness is not re-planned as data work", "A-69" not in planned_ids)
    print(f"\n{12-len(failures)}/12 passed")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--write", action="store_true")
    sub.add_parser("unread")
    sub.add_parser("selftest")
    args = parser.parse_args()
    return {"build": cmd_build, "unread": cmd_unread, "selftest": cmd_selftest}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
