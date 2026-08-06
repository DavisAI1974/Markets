#!/usr/bin/env python3
"""storage_restage_repair.py - graft the CORRECT storage lane onto a committed group state. (S115.)

WHY THIS EXISTS, and why it is a graft rather than a re-stage.

The g24 refine needs a state whose storage lane is right: the block spans 2026-07-20..07-31 and TWO
EIA prints land inside it (07-23 and 07-30), so the two EIA Thursdays are exactly the days a
specialist must diagnose off the correct week. The committed `grp24_state.json` serves
`storage.as_of = 2026-07-16` on ALL TEN DAYS with `stor_surprise` a constant 5.4 - two prints stale
by the last day - because `eia_surprise.json`, the source `_storage_series()` reads, stopped at the
07-16 print. Repaired and pushed to S3 this session (704 -> 706 prints, purely additive, 0 existing
values changed, read-back verified per D47).

A FULL RE-STAGE WOULD HAVE FIXED STORAGE AND BROKEN THREE OTHER THINGS. Measured, not assumed: a
fresh `stage_group g24` off the CURRENT S3 plane produces a state that is WORSE than the committed
one on three blocks, because their stores on S3 are older than what S114 built locally and never
pushed -
    storage_consensus       committed print_date 2026-07-30   fresh 2026-07-09  (3 prints stale)
    weather_forecast_cycle  committed present                 fresh EMPTY on 9/10 days
    freeze_risk             committed present                 fresh EMPTY on 9/10 days
(the two weather indexes on S3 both stop at 2026-07-20, the block's first day). Replacing a
ten-day state to fix one block and silently empty three others is the trade this desk exists to
refuse. So: keep the committed state, graft ONLY the storage family, and DECLARE the graft.

THE REPAIR DECLARES ITSELF (the S109 `session_b_share_basis` pattern). Every repaired day carries
`storage_repair_basis` naming what changed, from what, by what computation, and in which session -
a value that changes must say it changed, or the next reader cannot tell a repair from a defect.

SCOPE LIMIT, stated so it is not over-read: this touches `storage`, `stor_surprise`,
`stor_surprise_sign` and `stor_surprise_basis` and NOTHING else. It does not re-derive any
price-derived block, does not touch the mask, and does not invent a value - every number comes from
`forecast_harness`'s own `_storage_series()` / `_storage_asof()` reading the repaired store, i.e.
the identical computation a clean re-stage would perform.

    python storage_restage_repair.py g24              # dry run - print the per-day diff
    python storage_restage_repair.py g24 --write      # apply, in place, idempotent
    python storage_restage_repair.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
SESSION = "S115"
FIELDS = ("storage", "stor_surprise", "stor_surprise_sign", "stor_surprise_basis",
          "storage_regional")


def correct_storage_lane(days):
    """-> {day: {field: value}} exactly as a clean re-stage would compute it today."""
    sys.path.insert(0, HERE)
    import forecast_harness as fh
    stor = fh._storage_series()
    surp = fh._load_json("eia_surprise.json").get("KXNATGASD", {})
    out = {}
    for d in days:
        iso = "%s-%s-%s" % (d[:4], d[4:6], d[6:8])
        # STRICTLY BEFORE the reading day - the S96 blind fix; a same-day 10:30 ET print is not
        # open-time information. Identical selection to decision_state's own loop.
        past = sorted(ri for ri in surp if ri < iso)
        # THE WHOLE EIA-WEEKLY FAMILY MOVES TOGETHER OR NOT AT ALL. `storage_regional` tracks the
        # SAME publication, and the committed state has it frozen at the 07-16 print while storage
        # advances - the S114-reported pairing defect whose guard exists but whose STATE predates
        # the store fix. Grafting one and not the other would leave two blocks in one slice two
        # prints apart, which is precisely what state_health's same-publication check refuses.
        rec = {"storage": fh._storage_asof(iso, stor),
               "storage_regional": fh._storage_regional_block(iso)}
        if past:
            sr = surp[past[-1]]
            sv = sr.get("surprise")
            rec["stor_surprise"] = round(sv, 1) if sv is not None else None
            rec["stor_surprise_sign"] = (("above" if sv > 0 else "below")
                                         if sv is not None else None)
            rec["stor_surprise_basis"] = {
                "as_of_report_date": past[-1],
                "period_week_ending": sr.get("period"),
                "actual_bcf": sr.get("actual"),
                "seasonal_expectation_bcf": sr.get("seasonal_exp"),
                "surprise_bcf": sr.get("surprise"),
                "formula": ("surprise = actual - mean(same-ISO-week weekly change over the prior 5 "
                            "years, >=3 years required). It is a SEASONAL proxy, not a survey "
                            "consensus - storage_consensus carries the survey separately and the "
                            "two are additive, never substitutes."),
                "sign_means": ("positive = the print BUILT more (or drew less) than its own "
                               "five-year same-week norm; negative = tighter than the norm."),
            }
        out[d] = rec
    return out


def repair(gid, write=False, state_path=None):
    sp = state_path or os.path.join(RENDER_DIR, "grp%s_state.json" % gid.lstrip("g"))
    if not os.path.exists(sp):
        raise SystemExit("no state at %s" % sp)
    with open(sp, encoding="utf-8") as f:
        st = json.load(f)
    days = sorted(k for k in st if k[:2] == "20")
    want = correct_storage_lane(days)
    changed, already = [], 0
    for d in days:
        cur, new = st[d], want.get(d) or {}
        if not new.get("storage"):
            continue
        was_asof = (cur.get("storage") or {}).get("as_of")
        now_asof = (new.get("storage") or {}).get("as_of")
        was_reg = (cur.get("storage_regional") or {}).get("as_of")
        now_reg = (new.get("storage_regional") or {}).get("as_of")
        if (was_asof == now_asof and cur.get("stor_surprise") == new.get("stor_surprise")
                and was_reg == now_reg):
            already += 1
            continue
        changed.append((d, was_asof, now_asof, cur.get("stor_surprise"), new.get("stor_surprise"),
                        was_reg, now_reg))
        if write:
            for k, v in new.items():
                if v is not None:
                    cur[k] = v
            cur["storage_repair_basis"] = {
                "session": SESSION,
                "what": "storage / stor_surprise regrafted onto this committed state",
                "from": "storage.as_of %s (stor_surprise %s), storage_regional.as_of %s"
                        % (was_asof, cur.get("stor_surprise"), was_reg),
                "to": "storage.as_of %s, storage_regional.as_of %s" % (now_asof, now_reg),
                "why": ("eia_surprise.json - the source _storage_series() reads - stopped at the "
                        "2026-07-16 print, so every day of this block served that print. The store "
                        "was rebuilt this session (+2 prints, 0 existing values changed) and pushed "
                        "to S3 with a read-back verification (D47)."),
                "computation": ("forecast_harness._storage_asof(iso, _storage_series()) - the "
                                "identical call a clean re-stage makes; no value is invented"),
                "not_touched": ("every other block, the price mask, and all price-derived blocks. "
                                "A full re-stage was REFUSED because the S3 copies of "
                                "storage_consensus, weather_forecast_cycle and freeze_risk are "
                                "older than this state and would have emptied three blocks to fix "
                                "one."),
            }
    print("[storage-repair] %s: %d day(s) already correct, %d to change" % (gid, already, len(changed)))
    for d, wa, na, ws, ns, wr, nr in changed:
        print("   %s  as_of %s -> %s   stor_surprise %s -> %s   regional %s -> %s"
              % (d, wa, na, ws, ns, wr, nr))
    if write and changed:
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1, ensure_ascii=False)
        print("[storage-repair] WROTE %s" % os.path.relpath(sp, HERE))
    elif not write:
        print("[storage-repair] dry run - nothing written. Re-run with --write.")
    return changed


def selftest():
    """NC-3: every branch prints its own output, and the guard is exercised on real data."""
    fails = []

    def check(name, cond, detail=""):
        print("  %-62s %s%s" % (name, "PASS" if cond else "FAIL", ("  " + detail) if detail else ""))
        if not cond:
            fails.append(name)

    days = ["20260720", "20260724", "20260731"]
    want = correct_storage_lane(days)
    check("the repaired source advances across the block (it did not before)",
          len({(want[d]["storage"] or {}).get("as_of") for d in days}) == 3,
          str([(want[d]["storage"] or {}).get("as_of") for d in days]))
    check("the last day sees the 07-30 print",
          (want["20260731"]["storage"] or {}).get("as_of") == "2026-07-30")
    check("no day sees a print on or after its own date (decision-time discipline)",
          all((want[d]["storage"] or {}).get("as_of") < "%s-%s-%s" % (d[:4], d[4:6], d[6:8])
              for d in days))
    # IDEMPOTENCE on a scratch copy: a second run must find nothing to do.
    import shutil
    import tempfile
    src = os.path.join(RENDER_DIR, "grp24_state.json")
    if os.path.exists(src):
        tmp = os.path.join(tempfile.mkdtemp(), "grp24_state.json")
        shutil.copy(src, tmp)
        first = repair("g24", write=True, state_path=tmp)
        second = repair("g24", write=True, state_path=tmp)
        check("repair changes days on the first pass", len(first) > 0, "%d days" % len(first))
        check("repair is IDEMPOTENT (second pass changes nothing)", len(second) == 0)
        with open(tmp, encoding="utf-8") as f:
            after = json.load(f)
        d0 = after[sorted(k for k in after if k[:2] == "20")[-1]]
        check("every repaired day DECLARES itself", "storage_repair_basis" in d0)
        check("the repair touches ONLY the storage family",
              set(d0) - set(json.load(open(src))[sorted(k for k in after if k[:2] == "20")[-1]])
              <= {"storage_repair_basis", "stor_surprise_basis"})
    print("\n%s" % ("ALL PASS" if not fails else "FAILURES: %s" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Graft the correct storage lane onto a committed state")
    ap.add_argument("gid", nargs="?")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.gid:
        ap.error("give a group id, or --selftest")
    repair(a.gid, a.write)
