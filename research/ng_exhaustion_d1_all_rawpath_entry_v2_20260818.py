#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
from datetime import datetime

import ng_exhaustion_d1_all_rawpath_entry_20260818 as base


def load_week_prices_precise(raw_paths, week):
    """Preserve sub-second trade order for causal first-fill/last-exit pricing."""
    sun = base.parse_week(week)
    pts = []
    for p in raw_paths:
        d = base.day_from_name(p)
        di = (datetime.strptime(d, "%Y%m%d") - sun).days
        if di < 0 or di > 5:
            continue
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line)
                if r.get("action") != "T":
                    continue
                px = float(r.get("price", 0) or 0)
                if px <= 0:
                    continue
                ts = r.get("ts_event", r.get("ts"))
                if ts is None:
                    continue
                try:
                    raw_ts = float(ts)
                    sec = raw_ts % 86400.0
                except Exception:
                    continue
                pts.append((di * 86400.0 + sec, px))
    # Python sort is stable: equal timestamps preserve source tape order; never sort by price.
    pts.sort(key=lambda z: z[0])
    return pts


base.load_week_prices = load_week_prices_precise


if __name__ == "__main__":
    base.main()
