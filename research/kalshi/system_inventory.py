#!/usr/bin/env python3
"""Durable DavisAI Markets / Frankie system inventory.

This exists because A-22 solved the field-list problem but not the historical-system problem:
DATA_POINTS can go stale relative to OPEN_ITEMS, and OPEN_ITEMS is an action registry rather than a
complete map of what was built.  This renderer never drops DONE/SUPERSEDED work and never treats an
old data-point snapshot as current truth.

Authoritative inputs, in order:
  1. OPEN_ITEMS.json: every registered item, INCLUDING DONE/SUPERSEDED/BLOCKED.
  2. data_registry.py + store/data_points.json: data-family/field registry when regenerated.
  3. Current repo assets: spawn, brain/schema/view, Frankie adapters, forecast/data machinery.
  4. Historical handoffs/research are provenance, not status authority.

The report is intentionally generated.  Do not hand-edit MARKETS_SYSTEM_INVENTORY.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OPEN_ITEMS = os.path.join(HERE, "OPEN_ITEMS.json")
DATA_POINTS = os.path.join(HERE, "store", "data_points.json")
RENDER = os.path.join(ROOT, "MARKETS_SYSTEM_INVENTORY.md")

# These are system seams, not a hand-maintained data-point list.  Field/data coverage comes from
# data_registry.py.  The paths are included so a future takeover knows WHERE each system lives.
SYSTEM_ASSETS = [
    ("forecast orchestration", "research/kalshi/spawn.py", "PROTECTED legacy/generated-spawn seam; read, never casually edit"),
    ("brain", "research/kalshi/knowledge/ng_brain.json", "canonical NG/Frankie knowledge store"),
    ("brain schema", "research/kalshi/brain_schema.py", "schema/status validation"),
    ("brain serving", "research/kalshi/brain_view.py", "role-scoped/full-brain serving machinery"),
    ("data registry", "research/kalshi/data_registry.py", "A-22 generator for served/held/planned/identified fields"),
    ("data registry store", "research/kalshi/store/data_points.json", "generated data-point machine store"),
    ("work registry", "research/kalshi/OPEN_ITEMS.json", "append/update status authority; includes closed work"),
    ("work registry render", "OPEN_ITEMS.md", "generated action-board view, NOT system history"),
    ("Frankie build contract", "research/kalshi/FRANKIE_BUILD_BRIEF_S115.md", "original Frankie design contract"),
    ("Frankie implementation", "research/kalshi/FRANKIE_S115_IMPLEMENTATION.md", "implementation record"),
    ("Frankie coordination ledger", "research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md", "append-only C2C ledger"),
    ("Frankie current offline task", "research/kalshi/C2C_019_RESTORE_KITCHEN_SINK_BLIND_CURVE.md", "kitchen-sink/curve restoration"),
]

# High-level families are anchors for the human report only.  The generator proves whether each is
# represented by registry items and/or current source; it does NOT declare a family complete from
# this list.  New fields still come from data_registry, not from this list.
FAMILY_ANCHORS = {
    "market microstructure / Databento": ["Databento", "MBO", "MBP", "tape", "order-flow", "dipole"],
    "weather / ensembles": ["weather", "GEFS", "ECMWF", "MOS", "CDD", "HDD", "wind speed", "freeze"],
    "storage / EIA gas balance": ["storage", "EIA implied", "consensus", "salt", "NGWU", "STEO"],
    "power / generator stack": ["thermal stack", "grid_stack", "coal", "nuclear", "hydro", "battery", "heat rate", "EIA-930"],
    "forward renewables / net load": ["wind + solar", "wind / solar", "NET LOAD", "renewable"],
    "LNG / pipelines": ["LNG", "feedgas", "pipeline", "maintenance"],
    "positioning / COT": ["COT", "positioning"],
    "options / volatility": ["options", "put-call", "vol", "straddle", "IV"],
    "basis / curve / contract": ["basis", "contract", "term structure", "curve", "expiry"],
    "calendar / event state": ["calendar", "holiday", "roll", "EIA print"],
    "analog / library / regime": ["library", "analog", "regime", "retrieval"],
    "Frankie brain / schema / retention": ["brain", "Frankie", "lens", "retention", "schema"],
    "forecast scoring / validation": ["score", "baseline", "validator", "curve", "NO CALL"],
    "storage infrastructure / S3 / restore": ["S3", "restore", "store parity", "data plane"],
    "model / generator infrastructure": ["Bedrock", "model", "backend", "generator"],
}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _item_text(item):
    return " ".join(str(item.get(k, "")) for k in ("id", "title", "why", "source", "resolution_S114", "closed"))


def _family_items(items, needles):
    out = []
    for it in items:
        txt = _item_text(it).lower()
        if any(n.lower() in txt for n in needles):
            out.append(it)
    return out


def _data_status_counts():
    if not os.path.exists(DATA_POINTS):
        return None, "MISSING - regenerate with `python data_registry.py build --write` on the real data plane"
    try:
        d = _load(DATA_POINTS)
    except Exception as exc:
        return None, "UNREADABLE: %s" % exc
    # tolerate old/new store shapes: count tier/status wherever present.
    rows = d.get("points") or d.get("data_points") or d.get("rows") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    counts = Counter(str(r.get("tier") or r.get("status") or "UNKNOWN") for r in rows if isinstance(r, dict))
    return counts, "present sha256=%s" % _sha(DATA_POINTS)


def render():
    reg = _load(OPEN_ITEMS)
    items = reg.get("items") or []
    status_counts = Counter(str(i.get("status", "UNKNOWN")) for i in items)
    data_counts, data_note = _data_status_counts()

    lines = []
    lines += [
        "# MARKETS SYSTEM INVENTORY - CANONICAL GENERATED MAP",
        "",
        "> **DO NOT HAND-EDIT THIS FILE.** Generate it with `python research/kalshi/system_inventory.py --write`.",
        "> `OPEN_ITEMS.md` is the action queue. This document is the system/history map and deliberately retains DONE and SUPERSEDED work.",
        "",
        "## Non-negotiable Frankie data rule",
        "",
        "For a blind historical forecast at cutoff T, if DavisAI possesses information that was causally available by T, Frankie may access it. The only deliberate target mask is the future/realized PRICE CURVE and future-derived information. Reader count is diagnostic, not an entitlement filter: a field with no old brain reader is still available to Frankie.",
        "",
        "## Source hierarchy",
        "",
        "1. Current code + generated machine registries are status truth.",
        "2. `OPEN_ITEMS.json` is read with **all statuses**, never open-only.",
        "3. `data_registry.py` / `store/data_points.json` supply field-level truth and must be regenerated on the real data plane before a canary.",
        "4. Historical handoffs, old spawn files and chat records are provenance and discovery sources; they cannot override newer machine evidence.",
        "5. A contradiction is printed and resolved; it is never silently averaged or guessed.",
        "",
        "## Work-registry history",
        "",
        "Registry session: `%s`. Total registered items: **%d**." % (reg.get("current_session", "?"), len(items)),
        "",
        "| status | count |",
        "|---|---:|",
    ]
    for st in sorted(status_counts):
        lines.append("| %s | %d |" % (st, status_counts[st]))

    lines += ["", "### DONE / SUPERSEDED / BLOCKED history", "",
              "These are retained here specifically so completed work is never rediscovered as missing.", ""]
    for it in items:
        if it.get("status") in {"DONE", "SUPERSEDED", "BLOCKED"}:
            resolution = it.get("resolution_S114") or it.get("closed") or it.get("why") or ""
            resolution = " ".join(str(resolution).split())
            if len(resolution) > 360:
                resolution = resolution[:357] + "..."
            lines.append("- **%s [%s] - %s.** %s" % (it.get("id", "?"), it.get("status"), it.get("title", ""), resolution))

    lines += ["", "## Data registry state", "", "`store/data_points.json`: **%s**." % data_note]
    if data_counts:
        lines += ["", "| data-point tier/status | count |", "|---|---:|"]
        for k in sorted(data_counts):
            lines.append("| %s | %d |" % (k, data_counts[k]))
    lines += ["", "**Freshness gate:** a canary is not kitchen-sink-ready merely because an old `DATA_POINTS.md` exists. Regenerate the registry, then reconcile it against current DONE/OPEN status. Known historical contradiction: A-16 hydro and A-1 baselines became DONE after older registry text still described them as missing/unserved."]

    lines += ["", "## System assets", "", "| subsystem | path | role | present | sha256 |", "|---|---|---|---|---|"]
    for name, rel, role in SYSTEM_ASSETS:
        p = os.path.join(ROOT, rel)
        present = os.path.exists(p)
        digest = _sha(p)[:16] if present and os.path.isfile(p) else "-"
        lines.append("| %s | `%s` | %s | %s | `%s` |" % (name, rel, role, "yes" if present else "NO", digest))

    lines += ["", "## Data / capability families", "",
              "Each section below is generated by searching the **entire** registered history (including closed work). It is a discovery index, not a completeness verdict. Field-level completeness comes from the regenerated data-point registry plus the C2C-019 causal-access audit.", ""]
    for family, needles in FAMILY_ANCHORS.items():
        hits = _family_items(items, needles)
        c = Counter(str(x.get("status", "UNKNOWN")) for x in hits)
        lines.append("### %s" % family)
        lines.append("")
        lines.append("Registry coverage: **%d items** (%s)." % (len(hits), ", ".join("%s=%d" % kv for kv in sorted(c.items())) if c else "none"))
        lines.append("")
        for it in hits:
            lines.append("- `%s` **%s** - %s" % (it.get("id", "?"), it.get("status", "?"), it.get("title", "")))
        lines.append("")

    lines += [
        "## Pre-canary kitchen-sink gate",
        "",
        "A historical canary is READY only when all of these are true:",
        "",
        "- current data registry regenerated on the real data plane;",
        "- every possessed + causal-by-cutoff family is either directly present or accessibly referenced for Frankie;",
        "- all 90 brain plays and the canonical schema are available;",
        "- no fixed output clock, averaging, smoothing or harness-authored interpolation is imposed;",
        "- target/future realized curve and future-derived values remain behind the A-82 wall;",
        "- any unavailable family has a concrete provenance-backed reason, never silent omission;",
        "- `research/kalshi/spawn.py` remains protected unless a separately approved migration explicitly changes it.",
        "",
        "## AWS / terminal-only residue",
        "",
        "Facts that require credentials or the live AWS/local data plane belong here as explicit UNKNOWNs until a terminal operator proves them (current S3 object counts/bytes, materialized historical vintages, runtime-only stores, credentials-bound endpoints). Claude is used only for this residue; the repo/history reconciliation is owned here.",
        "",
    ]
    return "\n".join(lines) + "\n"


def selftest():
    reg = _load(OPEN_ITEMS)
    items = reg.get("items") or []
    assert items, "OPEN_ITEMS has no items"
    assert any(i.get("status") == "DONE" for i in items), "DONE history missing"
    out = render()
    assert "DONE / SUPERSEDED / BLOCKED history" in out
    # Regression for the exact mistake that triggered this build: do not produce an open-only map.
    for i in items:
        if i.get("status") in {"DONE", "SUPERSEDED", "BLOCKED"}:
            assert str(i.get("id")) in out, "closed item silently dropped: %s" % i.get("id")
    # Protected spawn is inventoried, never rewritten by this script.
    assert "research/kalshi/spawn.py" in out
    print("system_inventory selftest PASS: %d items, statuses=%s" % (len(items), dict(Counter(i.get("status", "UNKNOWN") for i in items))))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = render()
    if a.write:
        with open(RENDER, "w", encoding="utf-8") as f:
            f.write(out)
        print("wrote", os.path.relpath(RENDER, ROOT))
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
