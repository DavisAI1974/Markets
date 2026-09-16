#!/usr/bin/env python3
"""state_repair_s110.py - the S110 fix phase for the G23 pre-blind state audit (findings f1/f3/f4/f5).

Adjudication (SOP STEP 2, session authority - all data plumbing, no brain/play semantics touched):

f1 GO  g23 20260717 tape_conditions: the flow/b-family was computed on a degraded cont store carrying
       ~44% of session 20260716's tape while the session counts beside it came from the leg (root
       cause f2). RECOVER what the staged leg-built evidence pack carries (session_signed_flow,
       phase_signed_flow, phase_volume_lots - non-price fields only, copied field-for-field from
       renders/ng_refine_s95/g23_mbo_evidence.json[20260716], which was built FROM the leg at S108
       staging and whose totals reconcile exactly with the state's own leg-sourced volume_lots).
       NULL what no committed artifact carries (phase_n_trades and the entire b_share family incl.
       unsided_volume_frac) - a value measured on the wrong tape must not be served as a measurement
       (the squeeze_watch S109 precedent). Everything declared in flow_family_basis.
f2 GO  code, fixed at source in the same commit (not in this script): forecast_harness sets
       flow_read._ACTIVE_LEGS; flow_read's fallback is loud; tape_reconcile gained the flow-side
       leg check. Live execution verification rides the next staging with a data plane.
f3 GO  g22+g23 vol_regime: the n0 store carries ~a fifth to a quarter of the scored tape in the leg
       era (measured 0.226/0.265 vs pre-June g21 0.978). Values cannot be rebuilt without stores ->
       DECLARE via n0_era_basis; the new state_health guard fires only where the break is UNdeclared.
f4 GO  g23 20260717 storage_consensus: last_print affirmatively misdescribes the 07-09 print as the
       latest while the same day's storage block carries 07-16. No 07-16 consensus snapshot ever
       existed (the survey store died after 07-09) -> last_print = null with last_print_basis.
f5 GO  g22+g23 options_surface: strikes are 10x below the $/MMBtu convention in EVERY group carrying
       the block (g12-g23, standing feed defect; S109 parked it as costing budget-not-signal).
       Rescale x10 in the two LIVE pipeline states + declare strike_units; historical states stay
       byte-untouched as records; the feed-source fix is queued for the next data-plane session.

Discipline: dry-run by default, --write to apply; idempotent (each repair keys on its own basis/units
field); confined diff verified by a full leaf walk (changed/added/removed counted and asserted);
git is the rollback (git checkout -- <file>). Also appends the adjudication block to the audit JSON.
"""
from __future__ import annotations

import argparse
import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RD = os.path.join(HERE, "renders", "ng_refine_s95")
FC = os.path.join(HERE, "forecasts")

G23 = os.path.join(RD, "grp23_state.json")
G22 = os.path.join(RD, "grp22_state.json")
EV23 = os.path.join(RD, "g23_mbo_evidence.json")
AUDIT = os.path.join(FC, "grp23_state_audit.json")

BAD_DAY, BAD_SESS = "20260717", "20260716"
NULL_FIELDS = ("phase_n_trades", "session_b_share", "session_b_share_two_sided", "phase_b_share",
               "phase_b_share_two_sided", "big_print_b_share", "big_print_b_share_two_sided",
               "unsided_volume_frac")

N0_BASIS = ("S110 audit f3: in the leg era (G22+) this n0 family is computed on a degraded continuous "
            "store carrying ~a fifth to a quarter of the scored leg's tape (measured n0_prev_trades vs "
            "leg-reconciled same-session n_trades: g22 0.265, g23 0.226; pre-June g21 reconciles at "
            "0.978). Levels and trends here describe THAT store, not the scored contract's full tape - "
            "treat magnitude-band scalers reading them as era-degraded. Values not rebuildable without "
            "the stores; declared instead (squeeze_watch S109 precedent).")

STRIKE_BASIS = ("S110 audit f5: strikes were served in units exactly 10x below the $/MMBtu convention "
                "of every other price-denominated field (standing feed convention, all groups g12-g23), "
                "undeclared. Rescaled x10 here so distance-from-settle reads against contract_structure "
                "are unit-consistent; strike_units now declared. Feed-source fix queued (needs the "
                "options feed rerun with a data plane). Counts (n_strikes) and ratios untouched.")


def leaves(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, f"{p}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, f"{p}[{i}]")
    else:
        yield p, o


def diff(a, b):
    la, lb = dict(leaves(a)), dict(leaves(b))
    changed = sorted(k for k in la.keys() & lb.keys() if la[k] != lb[k])
    added = sorted(lb.keys() - la.keys())
    removed = sorted(la.keys() - lb.keys())
    return changed, added, removed


def repair_g23(state: dict, ev: dict) -> list[str]:
    log = []
    tc = state[BAD_DAY]["tape_conditions"]
    if tc.get("flow_family_basis"):
        log.append(f"f1: already repaired (flow_family_basis present) - skip")
    else:
        e = ev[BAD_SESS]
        phases = e["phases"]
        pv = [int(p["vol"]) for p in phases]
        pf = [int(p["sflow"]) for p in phases]
        # the evidence must reconcile with the state's own leg-sourced totals before we trust it
        assert sum(pv) == tc["volume_lots"], f"evidence vol {sum(pv)} != leg volume_lots {tc['volume_lots']}"
        assert sum(pf) == int(e["total_sflow"]), f"evidence phases {sum(pf)} != total_sflow {e['total_sflow']}"
        assert str(e.get("contract", "")).startswith("NGQ26"), f"evidence contract {e.get('contract')}"
        old_flow = tc.get("session_signed_flow")
        tc["session_signed_flow"] = int(e["total_sflow"])
        tc["phase_signed_flow"] = pf
        tc["phase_volume_lots"] = pv
        for f in NULL_FIELDS:
            tc[f] = None
        tc["flow_family_basis"] = (
            "S110 audit f1 REPAIR: the flow/b-family here was computed on a degraded cont store "
            "carrying 44-49% of session 20260716's tape (sum(phase_n_trades) 19,722 vs leg 39,965; "
            "sum(phase_volume_lots) 43,910 vs leg 100,272) while the session counts came from the leg "
            "- two tapes under one label (root cause: flow_read's leg context was never set, audit "
            f"f2). RECOVERED from the leg-built staging evidence (non-price fields only): "
            f"session_signed_flow {old_flow} -> {int(e['total_sflow'])}, phase_signed_flow, "
            "phase_volume_lots (sums reconcile exactly with the leg totals beside them). NULLED as "
            "unrecoverable without the leg file: phase_n_trades and the entire b_share family incl. "
            "unsided_volume_frac - the truncated-tape values (b 0.425/b2 0.531/u 0.199, big-print "
            "pair 0.431/0.574 straddling 0.50) are a biased sample and must not be read. A re-stage "
            "off the raw leg overwrites this repair.")
        log.append(f"f1: recovered 3 flow fields from evidence, nulled {len(NULL_FIELDS)} b-family fields")
    sc = state[BAD_DAY]["storage_consensus"]
    if sc.get("last_print_basis"):
        log.append("f4: already repaired (last_print_basis present) - skip")
    elif isinstance(sc.get("last_print"), dict):
        old = sc["last_print"].get("print_date")
        sc["last_print"] = None
        sc["last_print_basis"] = (
            "S110 audit f4 REPAIR: served last_print described the 2026-07-09 print as the latest for "
            "eight days after the survey store died, while this same day's storage block carries the "
            "2026-07-16 print - the one post-print day of week two would have evaluated the WRONG "
            "print's age (8d) and surprise (+12). No pre-print consensus snapshot for the 07-16 print "
            "ever existed, so there is nothing to serve: null, stated. The seasonal channel "
            "(stor_surprise) is unaffected and did update to the 07-16 print.")
        log.append(f"f4: last_print ({old}) -> null with basis")
    return log


def rescale_options(state: dict, gid: str) -> list[str]:
    log, n = [], 0
    for d in sorted(k for k in state if k[:1].isdigit()):
        op = state[d].get("options_surface")
        if not isinstance(op, dict) or op.get("strike_units"):
            continue
        for m in op.get("months") or []:
            if isinstance(m.get("oi_weighted_strike"), (int, float)):
                m["oi_weighted_strike"] = round(m["oi_weighted_strike"] * 10, 4)
                n += 1
            for t in m.get("top5_oi_strikes") or []:
                if isinstance(t.get("strike"), (int, float)):
                    t["strike"] = round(t["strike"] * 10, 4)
                    n += 1
        op["strike_units"] = "usd_per_mmbtu"
        op["strike_rescale_basis"] = STRIKE_BASIS
    if n:
        log.append(f"f5 {gid}: rescaled {n} strike leaves x10 + declared strike_units on all days")
    else:
        log.append(f"f5 {gid}: already rescaled (strike_units present everywhere) - skip")
    return log


def declare_n0(state: dict, gid: str) -> list[str]:
    n = 0
    for d in sorted(k for k in state if k[:1].isdigit()):
        vr = state[d].get("vol_regime")
        if isinstance(vr, dict) and not vr.get("n0_era_basis"):
            vr["n0_era_basis"] = N0_BASIS
            n += 1
    return [f"f3 {gid}: n0_era_basis declared on {n} day(s)" if n else f"f3 {gid}: already declared - skip"]


ADJUDICATION = {
    "session": "S110", "authority": "session (SOP STEP 2 - data plumbing only)",
    "verdicts": {
        "f1": {"go": True, "fix": "state_repair_s110.py R1 (recover from leg-built evidence + null "
                                  "unrecoverables, flow_family_basis)", "guard": "state_health phase-sum "
                                  "reconciliation, HARD", "negative_test": "fires on exactly 2/48 scopes "
                                  "across 17 committed group states (the two defective sums), 0 after repair"},
        "f2": {"go": True, "fix": "at source, same commit: forecast_harness sets flow_read._ACTIVE_LEGS; "
                                  "flow_read fallback loud; tape_reconcile flow-side leg check",
               "note": "live execution verification rides the next data-plane staging"},
        "f3": {"go": True, "fix": "n0_era_basis declared g22+g23 (values not rebuildable cold)",
               "guard": "state_health n0-era reconciliation, HARD when undeclared",
               "negative_test": "pre-June g21 reconciles 0.978 (passes); g22 0.265 / g23 0.226 fire "
                                "until declared; 0 after"},
        "f4": {"go": True, "fix": "state_repair_s110.py R2 (last_print null + basis)",
               "guard": "state_health storage-vs-consensus freshness, HARD",
               "negative_test": "fires on exactly 1/99 day-blocks (g23 20260717), 0 after repair"},
        "f5": {"go": True, "fix": "state_repair_s110.py R3 (x10 + strike_units on the two live states); "
                                  "feed-source fix queued (data plane)",
               "guard": "state_health strike-scale vs calendar_front_settle, HARD when units undeclared",
               "negative_test": "10x present in all 10 groups carrying options (true positives on "
                                "legacy records, left as records); live states pass after rescale"},
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply (default: dry-run, print the plan)")
    a = ap.parse_args()

    ev = json.load(open(EV23, encoding="utf-8"))
    results = {}
    for path, gid, fns in ((G23, "g23", (lambda s: repair_g23(s, ev), lambda s: rescale_options(s, "g23"),
                                          lambda s: declare_n0(s, "g23"))),
                           (G22, "g22", (lambda s: rescale_options(s, "g22"), lambda s: declare_n0(s, "g22")))):
        before = json.load(open(path, encoding="utf-8"))
        after = copy.deepcopy(before)
        log = []
        for fn in fns:
            log += fn(after)
        changed, added, removed = diff(before, after)
        results[gid] = (path, after, log, changed, added, removed)
        print(f"=== {gid} ({os.path.basename(path)})")
        for line in log:
            print(f"  {line}")
        print(f"  leaf diff: {len(changed)} changed, {len(added)} added, {len(removed)} removed")
        # CONFINEMENT: every touched leaf must live under a targeted path
        allowed = ("/tape_conditions/", "/storage_consensus/", "/options_surface/", "/vol_regime/")
        stray = [k for k in changed + added + removed if not any(t in k for t in allowed)]
        if stray:
            for s_ in stray[:10]:
                print(f"  STRAY LEAF (outside repair scope): {s_}")
            raise SystemExit("CONFINEMENT FAILED - repair touched leaves outside its scope; nothing written.")
        # Removals are legitimate ONLY as the structural shadow of a null-with-basis repair: a list or
        # dict set to None drops its element leaves. Every removed leaf must sit under a field this
        # script explicitly nulled; anything else is data loss and fatal.
        null_prefixes = tuple(f"/tape_conditions/{f}[" for f in NULL_FIELDS) + (
            f"/{BAD_DAY}/storage_consensus/last_print/",)
        bad_rm = [k for k in removed
                  if not any(p in k for p in null_prefixes)
                  and not k.startswith(f"/{BAD_DAY}/storage_consensus/last_print/")]
        if bad_rm:
            for s_ in bad_rm[:10]:
                print(f"  UNEXPECTED REMOVAL: {s_}")
            raise SystemExit("CONFINEMENT FAILED - a leaf was removed outside the declared nulls; nothing written.")

    if not a.write:
        print("\nDRY RUN - nothing written. Re-run with --write to apply.")
        return 0

    for gid, (path, after, _log, _c, _a, _r) in results.items():
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(after, fh)
        print(f"[write] {path}")
    audit = json.load(open(AUDIT, encoding="utf-8"))
    audit["adjudication"] = ADJUDICATION
    with open(AUDIT, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, indent=1)
    print(f"[write] adjudication block -> {AUDIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
