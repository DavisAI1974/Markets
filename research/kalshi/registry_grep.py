#!/usr/bin/env python3
"""registry_grep.py - search the work registry. (S115 close; promoted from a scratchpad one-liner.)

`OPEN_ITEMS.json` is 181 items and `OPEN_ITEMS.md` is 393KB. Both are the wrong shape for the
question that actually gets asked twenty times a session: **has this already been registered, and
under what id?** D30 says a finding with no home in the registry does not exist - which only works
if finding the home is cheap. D36's instance is the cost of it not being: twelve of thirteen S111
build suggestions had no registry item, and nobody noticed because nobody could search.

    python registry_grep.py wind                    # regex over id/title/why/source/what
    python registry_grep.py 'brain|schema' --tier ESSENTIAL
    python registry_grep.py . --status OPEN --size S --sort tier
    python registry_grep.py databento --full        # print the matching item entire

Searches EVERY text field, not just the title - the S115 lesson from `brain_onedoc_fix_s115.py` is
that content hides in the field you did not look at. Case-insensitive by default.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "OPEN_ITEMS.json")

TIER_ORDER = {"ESSENTIAL": 0, "BIGGEST_WIN": 1, "REST": 2, None: 3}
SIZE_ORDER = {"XS": 0, "S": 1, "M": 2, "L": 3, None: 4}


def _blob(it):
    """Every text field, flattened. Nested values are stringified rather than skipped - a match
    inside `external_build` or `falsifier` counts exactly as much as one in the title."""
    parts = []
    for v in it.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, dict)):
            parts.append(json.dumps(v, ensure_ascii=False))
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="search research/kalshi/OPEN_ITEMS.json")
    ap.add_argument("pattern", help="regex; use . to match everything")
    ap.add_argument("--tier", help="ESSENTIAL | BIGGEST_WIN | REST")
    ap.add_argument("--status", help="OPEN | IN_PROGRESS | DONE")
    ap.add_argument("--size", help="XS | S | M | L")
    ap.add_argument("--sort", choices=("id", "tier", "size"), default="tier")
    ap.add_argument("--full", action="store_true", help="print each match's whole entry")
    ap.add_argument("--case", action="store_true", help="case-sensitive")
    a = ap.parse_args()

    with open(REG, encoding="utf-8") as f:
        items = json.load(f)["items"]
    rx = re.compile(a.pattern, 0 if a.case else re.I)

    hits = []
    for it in items:
        if a.tier and (it.get("tier") or "").upper() != a.tier.upper():
            continue
        if a.status and (it.get("status") or "").upper() != a.status.upper():
            continue
        if a.size and (it.get("size") or "").upper() != a.size.upper():
            continue
        if rx.search(_blob(it)):
            hits.append(it)

    key = {"id": lambda i: i.get("id", ""),
           "tier": lambda i: (TIER_ORDER.get(i.get("tier"), 3), i.get("id", "")),
           "size": lambda i: (SIZE_ORDER.get(i.get("size"), 4), i.get("id", ""))}[a.sort]
    hits.sort(key=key)

    for it in hits:
        if a.full:
            print(json.dumps(it, indent=1, ensure_ascii=False))
            print()
            continue
        print("%-7s %-12s %-11s %-2s  %s"
              % (it.get("id", "?"), it.get("tier") or "-", it.get("status") or "-",
                 it.get("size") or "-", (it.get("title") or "")[:98]))
        # WHERE THE MATCH ACTUALLY IS. A hit whose title does not contain the pattern looks like a
        # false positive until you can see the field it matched - and those are the valuable ones,
        # because they are the registrations you would otherwise duplicate.
        if not rx.search(it.get("title", "")):
            for k, v in it.items():
                if k == "title" or not isinstance(v, str):
                    continue
                m = rx.search(v)
                if m:
                    lo, hi = max(0, m.start() - 45), min(len(v), m.end() + 45)
                    print("          ^ %s: ...%s..." % (k, v[lo:hi].replace("\n", " ")))
                    break

    print("\n%d of %d items" % (len(hits), len(items)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
