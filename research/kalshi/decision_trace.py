#!/usr/bin/env python3
"""decision_trace.py - BIND the reasoning to the decision it produced (S110, Greg's question:
"are we tying the context to the decision that it made... I don't want a context file out there
that isn't tied to the decision it was used to make").

THE PROBLEM. Reasoning lives in three places with three different bindings:
  1. INSIDE the posterior JSON (evidence_used, stand_down_reasons, magnitude_derivation, ...) -
     bound to the number by construction: same file, same key. Cannot drift.
  2. The LEDGER (*_LEDGER_*.md) - prose, quoting numbers. Bound only by CONVENTION. If a day is
     re-run and its number changes, the ledger still says the old thing, silently. That is a
     context file floating free of its decision.
  3. The BATCH RECORD - stations and versions, but no link to either.

THE BINDING. A DECISION ID = sha256(group|date|owner|number)[:12]. It changes the instant the
number changes, so any artifact quoting a stale number fails to resolve. The trace records, per
decision: the number, the OWNER, the INPUTS that produced it (brain version, state sha, causal-slice
sha), the REASONING (posterior sha + field inventory), and the OUTCOME (actual, err). One row =
one decision with its whole provenance chain.

  build  <gid>    -> forecasts/g<N>_decision_trace.json
  verify <gid>    -> re-derives every id from the live files and cross-checks the ledger's quoted
                     numbers against the trace. A ledger claim whose number no longer matches its
                     day is reported as STALE - the failure this tool exists to make impossible.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.path.join(HERE, "forecasts")
RD = os.path.join(HERE, "renders", "ng_refine_s95")
REASON_FIELDS = ("reasoning", "evidence_used", "evidence_rejected", "stand_down_reasons",
                 "selection_reason", "mbo_verdict", "magnitude_derivation",
                 "proposal_contribution", "refine_targets_addressed", "plays_fired",
                 "plays_stood_down", "handoff_out", "taken_vs_overridden")


def sha(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def decision_id(gid: str, date: str, owner: str, num) -> str:
    return hashlib.sha256(f"{gid}|{date}|{owner}|{num}".encode()).hexdigest()[:12]


def _num(d: dict):
    for k in ("expected_magnitude_usd", "guessed_net_usd"):
        v = d.get(k)
        if isinstance(v, (int, float)):
            return int(v)
    return None


def _reasoning_inventory(d: dict) -> dict:
    return {k: len(json.dumps(d[k])) for k in REASON_FIELDS if k in d and d[k] not in (None, "", [], {})}


def build(gid: str, embed: bool = False) -> dict:
    """embed=True inlines the REASONING TEXT beside each number (Greg, S110: "they should be on the
    same file - you have the answer and then next to it should be the explanation"). The per-day
    posteriors already satisfy that at the decision level (number and reasoning are keys of the same
    object and cannot drift apart). This lifts the same property to the GROUP level: one
    self-contained record where every number carries its own explanation, its inputs, and its
    outcome - no pointer to chase, nothing that can go stale separately."""
    return _build(gid, embed)


def _build(gid: str, embed: bool = False) -> dict:
    n = gid.lstrip("g")
    import sys
    sys.path.insert(0, HERE)
    import group_config as gc
    owner = gc.owner_map(gid)
    brain = json.load(open(os.path.join(HERE, "knowledge", "ng_brain.json"), encoding="utf-8"))
    bver = (brain.get("meta") or {}).get("version", "?")
    actual = {}
    ap = os.path.join(RD, f"{gid}_actual.json")
    if os.path.exists(ap):
        for r in json.load(open(ap, encoding="utf-8")).get("days", []):
            actual[str(r.get("date"))] = r.get("day_move_usd", r.get("actual_day_move_usd"))
    state_sha = sha(os.path.join(RD, f"grp{n}_state.json"))
    rows = []
    for date, own in sorted(owner.items()):
        row = {"date": date, "owner": own, "brain_version_at_trace": bver,
               "inputs": {"state_sha": state_sha,
                          "causal_slice_sha": sha(os.path.join(RD, f"{gid}_causal_slices", f"state_{date}.json")),
                          "anchor_sha": sha(os.path.join(RD, f"{gid}_anchor.json"))},
               "phases": {}, "actual_day_move_usd": actual.get(date)}
        for phase, path in (("blind", os.path.join(FC, f"g{n}_perday", f"grp{n}_{own}_{date}.json")),
                            ("refine_r1", os.path.join(FC, f"g{n}_refine_perday", f"grp{n}_{own}_{date}.json"))):
            if os.path.exists(path):
                d = json.load(open(path, encoding="utf-8"))
                num = _num(d)
                row["phases"][phase] = {
                    "number_usd": num,
                    "decision_id": decision_id(gid, date, own, num),
                    "posterior": os.path.relpath(path, HERE).replace("\\", "/"),
                    "posterior_sha": sha(path),
                    "reasoning_bytes": _reasoning_inventory(d),
                    "reasoning": ({k: d[k] for k in REASON_FIELDS if k in d} if embed else None),
                    "err_vs_actual": (None if (num is None or row["actual_day_move_usd"] is None)
                                      else num - row["actual_day_move_usd"])}
        # round 2 lives in the per-specialist file, keyed by day
        r2 = os.path.join(FC, f"grp{n}_mbo_specialist_{own}_r2.json")
        if os.path.exists(r2):
            for d in json.load(open(r2, encoding="utf-8")).get("days", []):
                if str(d.get("date", "")).replace("-", "") == date:
                    num = _num(d)
                    row["phases"]["refine_r2"] = {
                        "number_usd": num, "decision_id": decision_id(gid, date, own, num),
                        "posterior": os.path.relpath(r2, HERE).replace("\\", "/"),
                        "posterior_sha": sha(r2), "reasoning_bytes": _reasoning_inventory(d),
                        "reasoning": ({k: d[k] for k in REASON_FIELDS if k in d} if embed else None),
                        "err_vs_actual": (None if (num is None or row["actual_day_move_usd"] is None)
                                          else num - row["actual_day_move_usd"])}
        rows.append(row)
    out = {"group": gid, "binding": "decision_id = sha256(group|date|owner|number)[:12] - changes "
                                    "the instant the number changes, so any artifact quoting a stale "
                                    "number fails to resolve against this trace",
           "ledgers": [os.path.basename(p) for p in
                       sorted(glob.glob(os.path.join(HERE, f"*{gid.upper()}*LEDGER*.md")))],
           "days": rows}
    p = os.path.join(FC, f"{gid}_decision_trace{'_full' if embed else ''}.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    return out


def claims_block(gid: str) -> str:
    """The machine-checkable binding a ledger must carry. Generated from the live trace."""
    t = build(gid)
    lines = ["## DECISION CLAIMS (machine-checked - do not hand-edit; regenerate with "
             "`python decision_trace.py claims <gid>`)", "",
             "| date | owner | phase | number | decision_id |", "|---|---|---|---|---|"]
    for r in t["days"]:
        for phase, ph in r["phases"].items():
            # A phase can legitimately carry no number (a bridge, or a posterior whose magnitude
            # field is absent) - record it as UNNUMBERED rather than crashing or silently dropping it.
            num = f"{ph['number_usd']:+d}" if isinstance(ph["number_usd"], int) else "UNNUMBERED"
            lines.append(f"| {r['date']} | {r['owner']} | {phase} | {num} | "
                         f"`{ph['decision_id']}` |")
    return "\n".join(lines) + "\n"


def verify(gid: str) -> int:
    """Verify the LEDGERS' decision claims resolve against the live trace.

    DESIGN NOTE (S110, learned by getting it wrong once): the first version scanned free prose for
    any number near a date and cried STALE on nine legitimate COMPONENT quantities - a +871 signed
    flow, a +1,210 gap, wind +62%. Prose cannot be parsed for intent: a ledger legitimately cites
    measurements that are not day-moves. So the binding is EXPLICIT - each ledger carries a DECISION
    CLAIMS table of decision_ids, and an id either resolves against the trace or it does not. A
    number that changed produces an unresolvable id: unambiguous, no heuristics. A ledger with NO
    claims table is reported as UNBOUND - context floating free of the decision it describes, which
    is the exact failure this tool exists to prevent."""
    t = build(gid)
    live = {ph["decision_id"] for r in t["days"] for ph in r["phases"].values()}
    problems, checked, unbound = [], 0, []
    for lp in t["ledgers"]:
        txt = open(os.path.join(HERE, lp), encoding="utf-8").read()
        ids = re.findall(r"`([0-9a-f]{12})`", txt)
        if not ids:
            # A ledger written before the binding existed may DECLARE itself legacy rather than
            # retrofit ids it never verified against. Declared-legacy is known and quiet; an
            # UNDECLARED ledger with no claims is the live failure.
            unbound.append((lp, "LEGACY-DECLARED" if "LEGACY, UNBOUND" in txt else "UNDECLARED"))
            continue
        for i in ids:
            checked += 1
            if i not in live:
                problems.append(f"{lp}: decision_id {i} does NOT resolve - the number it describes "
                                f"is no longer what the system holds (re-run and regenerate claims)")
    print(f"[decision_trace] {gid}: {len(t['days'])} days, ledgers {t['ledgers'] or 'NONE'}")
    for r in t["days"]:
        ph = {k: v["number_usd"] for k, v in r["phases"].items()}
        rb = sum(sum(v["reasoning_bytes"].values()) for v in r["phases"].values())
        print(f"  {r['date']} {r['owner']}  {ph}  actual {r['actual_day_move_usd']}  "
              f"reasoning {rb:,}B  ids {[v['decision_id'] for v in r['phases'].values()]}")
    print(f"[verify] {checked} decision_ids cross-checked, {len(problems)} UNRESOLVED")
    for p in problems[:15]:
        print("  STALE", p)
    for u in unbound:
        print(f"  UNBOUND {u} - carries no DECISION CLAIMS table; its prose is not tied to any "
              f"decision. Add one with `python decision_trace.py claims {gid}`.")
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["build", "verify", "claims"])
    ap.add_argument("gid")
    ap.add_argument("--embed", action="store_true",
                    help="inline the reasoning text beside every number (self-contained record)")
    a = ap.parse_args()
    if a.cmd == "build":
        t = build(a.gid, a.embed)
        print(f"[decision_trace] wrote forecasts/{a.gid}_decision_trace{'_full' if a.embed else ''}.json - {len(t['days'])} days")
        raise SystemExit(0)
    if a.cmd == "claims":
        print(claims_block(a.gid))
        raise SystemExit(0)
    raise SystemExit(verify(a.gid))
