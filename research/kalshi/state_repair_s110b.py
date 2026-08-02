#!/usr/bin/env python3
"""state_repair_s110b.py - A11.1: the CDD-LADDER ARTIFACT repair (S110 merge addendum; Greg's go
"run with your plan for proposals and fixes for platform").

THE NONCONFORMANCE (D11 class, third instance this session): S109 P4 recorded the CDD ladder +
seam_delta_warning as SERVED. The harness code landed (forecast_harness.py lines ~137-166, ~557-577)
but the committed grp22/grp23 states were never rebuilt - fwd7_gw_cdd_span, horizons' CDD, run_delta
CDD, ladder_basis_note, sunday_reopen CDD/seam warning all ABSENT from both. B-0629 declared it
mid-refine; verified by grep on both states.

THE REPAIR, honest about what is provable cold:
1. weather_forecast GRAFT (true cold recompute): the mos_asof store on disk carries forecast_gw_cdd
   per horizon and d_gw_cdd per run_delta row for every G22/G23 asof day. Graft them via the SAME
   assembly the harness now performs, with two IDENTITY PROOFS per day before writing anything:
   (a) the state's served D0 forecast_gw_cdd must equal the store's (same-vintage proof);
   (b) fwd7_gw_hdd_span recomputed from the store's horizons must equal the store's own span
       (arithmetic proof) - then and only then fwd7_gw_cdd_span is derived by the SAME arithmetic
       (the store's own top-level CDD span is null in this vintage), flagged with its basis.
2. weather_forecast_cycle DECLARATION (no cold source): mos_cycle_feed's store is absent, so
   sunday_reopen's gw_cdd_d0/d_gw_cdd CANNOT be recomputed and are NOT fabricated. Grafted instead:
   the static seam_delta_warning doctrine text + a cdd_basis note directing the reader to the
   weather_forecast CDD LEVELS (difference the levels across the seam - the rule B-0629 executed by
   hand to get the sign pre-tape).

Dry-run default; --write applies; --include-g22 adds g22 (HOLD until refine r2 completes - r2
agents read grp22_state.json live). Idempotent (keys on ladder_basis_note / seam_delta_warning).
Confined diff walked and asserted. Rollback = git checkout.
"""
from __future__ import annotations

import argparse
import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RD = os.path.join(HERE, "renders", "ng_refine_s95")
MOS = os.path.join(HERE, "..", "..", "weather", "mos_asof", "mos_asof_index.json")

LADDER_NOTE = (
    "S109: forecast_gw_cdd / d_gw_cdd are served ALONGSIDE the HDD ladder, never replacing it. "
    "In a summer block CDD is the demand signal and HDD is inert - a play stating an ABSOLUTE "
    "HDD bar (divergence_resolution 16.4, shoulder_weather_band_void 13.5) is UNEVALUABLE in "
    "summer, not satisfied and not refuted. Treat an unreachable HDD bar as UNKNOWN; do not let "
    "it default the selector to a direction.")
GRAFT_BASIS = (
    "S110 REPAIR (A11.1): the S109 ladder assembly landed in harness code but this staged state "
    "was never rebuilt (no data plane at S109 close). CDD horizon/run-delta fields grafted from "
    "the mos_asof store via the same assembly, after two per-day identity proofs (served D0 CDD == "
    "store D0 CDD; HDD span arithmetic reproduces the store's own). fwd7_gw_cdd_span is DERIVED "
    "from the store's horizons by that proven arithmetic (the store's own CDD span is null in this "
    "vintage). A restage off the raw feeds overwrites this graft.")
SEAM_WARN = ("run deltas baseline run-over-run, NOT session-over-session. Across a weekend/holiday "
             "seam use the LEVEL difference (gw_cdd_d0 here vs the prior session's), never these deltas.")
CYCLE_BASIS = (
    "S110 REPAIR (A11.1, declared-not-fabricated): the cycle store is absent cold, so gw_cdd_d0 / "
    "d_gw_cdd cannot be recomputed here and are NOT served. For the weekend-add CDD read, difference "
    "the LEVELS in weather_forecast (forecast_gw_cdd D0 and horizons) against the prior session's - "
    "the seam rule, executed by hand successfully on G22 0629. A restage with the cycle store "
    "overwrites this note with the real fields.")


def span(hs, key):
    vals = [h.get(key) for h in hs if isinstance(h.get(key), (int, float))]
    return round(max(vals) - min(vals), 3) if len(vals) >= 2 else None


def graft(state: dict, mos: dict, gid: str) -> list[str]:
    log = []
    for d in sorted(k for k in state if k[:1].isdigit()):
        iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        wf = state[d].get("weather_forecast")
        r = mos.get(iso)
        if not isinstance(wf, dict) or not r:
            log.append(f"{gid} {d}: weather_forecast or store row missing - SKIP (declared)")
            continue
        if wf.get("ladder_basis_note"):
            log.append(f"{gid} {d}: already grafted - skip")
            continue
        # identity proof (a): same vintage
        a, b = wf.get("forecast_gw_cdd"), r.get("forecast_gw_cdd")
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) < 1e-6):
            raise SystemExit(f"IDENTITY FAIL {gid} {d}: state D0 CDD {a} != store {b} - vintages differ; ABORT")
        # identity proof (b): span arithmetic reproduces the store's own HDD span
        hs = r.get("horizons") or []
        hdd_span = span(hs, "forecast_gw_hdd")
        store_hdd_span = r.get("fwd7_gw_hdd_span")
        if isinstance(store_hdd_span, (int, float)) and (hdd_span is None or abs(hdd_span - store_hdd_span) > 0.02):
            raise SystemExit(f"SPAN ARITHMETIC FAIL {gid} {d}: derived HDD span {hdd_span} != store {store_hdd_span}; ABORT")
        # graft: horizons CDD + run_delta CDD, mirroring the harness assembly exactly
        by_t = {h.get("target_date"): h for h in hs}
        n_h = n_rd = 0
        for h in wf.get("horizons") or []:
            src = by_t.get(h.get("target_date"))
            if src and "forecast_gw_cdd" in src and "forecast_gw_cdd" not in h:
                h["forecast_gw_cdd"] = src["forecast_gw_cdd"]
                n_h += 1
        rd_by_t = {x.get("target_date"): x for x in r.get("run_delta") or []}
        for x in wf.get("run_delta") or []:
            src = rd_by_t.get(x.get("target_date"))
            if src and "d_gw_cdd" in src and "d_gw_cdd" not in x:
                x["d_gw_cdd"] = src["d_gw_cdd"]
                n_rd += 1
        wf["fwd7_gw_cdd_span"] = span(hs, "forecast_gw_cdd")
        wf["fwd7_gw_cdd_span_basis"] = "derived from store horizons at repair (store CDD span null this vintage); HDD-twin arithmetic proven"
        wf["ladder_basis_note"] = LADDER_NOTE
        wf["ladder_graft_basis"] = GRAFT_BASIS
        # cycle block: declare, never fabricate
        wc = state[d].get("weather_forecast_cycle")
        tag = ""
        if isinstance(wc, dict):
            for limb_name in ("sunday_reopen", "weekday_open"):
                limb = wc.get(limb_name)
                if isinstance(limb, dict) and not limb.get("seam_delta_warning"):
                    limb["seam_delta_warning"] = SEAM_WARN
                    limb["cdd_basis"] = CYCLE_BASIS
                    tag += f"+{limb_name}"
        log.append(f"{gid} {d}: grafted {n_h} horizon CDD + {n_rd} run-delta CDD, span {wf['fwd7_gw_cdd_span']} {tag}")
    return log


def leaves(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, f"{p}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, f"{p}[{i}]")
    else:
        yield p, o


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--include-g22", action="store_true",
                    help="HOLD until refine r2 completes - r2 agents read grp22_state.json live")
    a = ap.parse_args()
    mos = json.load(open(MOS, encoding="utf-8"))
    gids = ["g23"] + (["g22"] if a.include_g22 else [])
    for gid in gids:
        path = os.path.join(RD, f"grp{gid[1:]}_state.json")
        before = json.load(open(path, encoding="utf-8"))
        after = copy.deepcopy(before)
        for line in graft(after, mos, gid):
            print(" ", line)
        la, lb = dict(leaves(before)), dict(leaves(after))
        changed = [k for k in la.keys() & lb.keys() if la[k] != lb[k]]
        added = sorted(lb.keys() - la.keys())
        removed = sorted(la.keys() - lb.keys())
        stray = [k for k in changed + added + removed
                 if "/weather_forecast" not in k]
        print(f"  {gid}: {len(changed)} changed, {len(added)} added, {len(removed)} removed")
        if stray or removed or changed:
            for s_ in (stray or removed or changed)[:8]:
                print("   UNEXPECTED:", s_)
            raise SystemExit("CONFINEMENT FAILED - graft must be purely ADDITIVE under weather_forecast*; nothing written")
        if a.write:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(after, fh)
            print(f"  [write] {path}")
    if not a.write:
        print("DRY RUN - nothing written. --write to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
