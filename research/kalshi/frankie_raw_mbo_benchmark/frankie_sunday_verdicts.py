"""Per-day verdicts on the 44 served lessons, computed from the principal pass's own tallies.

Each verdict is one of VERIFIED (today's stream reproduced the lesson's numeric core, and the
numbers are written beside it), REFUTED (today's stream contradicts it, numbers beside it), or
NOT_TESTED_ON_THIS_SLICE (the lesson's unit is not one this pass computed, or it is a statement
about a prior artifact rather than the market; the reason says which). S124: a lesson not
exercised is not doubted. Every check here is explicit and named; nothing is inferred from
prose. Reads `tallies.json` and the section ledgers the pass wrote; never the runner's result.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _last(out_dir: Path, section: str) -> dict[str, Any]:
    body = json.loads((out_dir / "ledgers" / f"contract_section_{section}.json").read_text(encoding="utf-8"))
    return body["entries"][-1]["body"]


def _i(x: Any) -> int | None:
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def verdicts(out_dir: Path) -> list[dict[str, Any]]:
    t = json.loads((out_dir / "tallies.json").read_text(encoding="utf-8"))
    s = {k: _last(out_dir, k) for k in ("4.0", "4.1", "4.3", "4.4", "4.8", "4.9", "4.11", "4.12", "4.13", "4.14", "4.7")}
    members_all = "all delivered groups; see the section ledger's member_group_indices"
    V: list[dict[str, Any]] = []

    def verified(fid: str, computed: dict[str, Any], statement: str) -> None:
        V.append({"lesson_id": fid, "verdict": "VERIFIED", "computed": computed, "statement": statement,
                  "member_group_indices": s["4.1"]["member_group_indices"][:1] or [0]})

    def refuted(fid: str, computed: dict[str, Any], statement: str) -> None:
        V.append({"lesson_id": fid, "verdict": "REFUTED", "computed": computed, "statement": statement,
                  "member_group_indices": s["4.1"]["member_group_indices"][:1] or [0]})

    def not_tested(fid: str, reason: str) -> None:
        V.append({"lesson_id": fid, "verdict": "NOT_TESTED_ON_THIS_SLICE", "reason": reason})

    def check(fid: str, expected: dict[str, Any], actual: dict[str, Any], statement: str) -> None:
        mism = {k: (expected[k], actual.get(k)) for k in expected if actual.get(k) != expected[k]}
        if mism:
            refuted(fid, {"expected": expected, "actual": actual, "mismatch": mism}, statement + " - today's numbers differ")
        else:
            verified(fid, {"expected": expected, "actual": actual}, statement)

    ph = t["phase"]
    check("F-01", {"records": 57027, "groups": 43569, "PRE_SETTLEMENT": 43366, "PRE_OPEN": 203, "segments": 1},
          {"records": t["records"], "groups": t["groups"], "PRE_SETTLEMENT": ph.get("PRE_SETTLEMENT"), "PRE_OPEN": ph.get("PRE_OPEN"), "segments": len(t["segments"])},
          "one instrument, one segment, 57,027 records into 43,569 groups, phase split 43,366 / 203")
    det = (t.get("detector_end") or {}).get("detector_counters") or {}
    flat = {str(k): v for k, v in det.items()} if isinstance(det, dict) else {}
    got = {k: _i(flat.get(k)) for k in ("seconds_observed", "seconds_in_warmup", "considered", "promoted")}
    if any(v is None for v in got.values()):
        not_tested("F-02", f"the detector's own counters on the STREAM_END row do not carry the four names this check reads; keys present: {sorted(flat)[:12]}")
    else:
        check("F-02", {"seconds_observed": 17991, "seconds_in_warmup": 11399, "considered": 4462, "promoted": 91}, got,
              "detector searched 36.6% of observed seconds and promoted 91 of 4,462 considered")
    d45 = _last(out_dir, "4.5")["f_last_to_decision_delay_ns"]
    if d45["n"] == 0:
        verified("F-03", {"f_last_to_decision_delay_ns_n": 0, "groups": t["groups"]}, "the decision clock is still unpopulated on every member row")
    else:
        refuted("F-03", {"f_last_to_decision_delay_ns": d45}, "the decision clock now carries observations, so the absence lesson no longer holds")
    not_tested("F-04", "this pass strata are content families (family_id), not the runner's family x subfamily x side x phase strata; the 205-strata count is not computed here")
    top = {row["action_string"]: row["groups"] for row in s["4.3"]["action_strings_top"]}
    check("F-05", {"A": 16199, "C": 15136, "M": 3896, "AN": 3727, "CN": 2182, "MN": 794}, {k: top.get(k) for k in ("A", "C", "M", "AN", "CN", "MN")},
          "the day is elementary queue traffic: the six elementary action strings reproduce exactly")
    not_tested("F-06", "the cascade grammar (alternating trade/fill pairs terminated by a same-side cancel run) is a per-group shape this pass did not classify")
    check("F-07", {"max_actions_per_group": 245, "PRE_OPEN_groups": 203}, {"max_actions_per_group": _last(out_dir, "4.2")["max_actions_per_group"], "PRE_OPEN_groups": ph.get("PRE_OPEN")},
          "the 245-component PRE_OPEN reopen group is present; its snapshot-restatement mechanism was not re-derived here")
    ex = t.get("exhaustion_end") or {}
    check("F-08", {"candidates": 91, "completed": False}, {"candidates": t["candidates"], "completed": bool(ex.get("completed"))},
          "91 candidates promoted and no runway completed; the runway row is censored")
    not_tested("F-09", "the nanosecond-remainder signature of REVERSAL durations lives in the runner's averaged companions, which this pass does not read")
    not_tested("F-10", "phase_depletion / phase_refill are 4.10 averaged-companion channels this pass does not compute")
    rec = t["recognition"]
    only_hn = set(rec) <= {"H+N"} and rec.get("H+N", 0) > 0
    check("F-11", {"only_H+N": True, "episodes": 182}, {"only_H+N": only_hn, "episodes": t["episodes"]},
          "every episode is H+N: PRIOR and T0 are structurally unreachable on the flow-spike unit")
    lag = s["4.11"]["detection_lag_seconds"]
    check("F-12", {"max_seconds": 50.0, "min_at_least_6": True}, {"max_seconds": lag["max"], "min_at_least_6": (lag["min"] or 0) >= 6},
          "recognition delay is bounded above at exactly 50 s")
    not_tested("F-13", "failed_state_count and superseded_call_attempts are runner counters not present on the delivered episode rows")
    for fid in ("F-14", "F-15", "F-16"):
        not_tested(fid, "per-stratum queue survival and queue-position quantiles; this pass computes a pooled Kaplan-Meier only, which cannot confirm or refute a stratum claim")
    check("F-17", {"lifecycles": 20005}, {"lifecycles": t["queue"]["rows"]}, "the queue population is 20,005 lifecycles; the birth-stamp caveat itself is a labelling rule, not a number")
    L = t["lineage"]
    check("F-18", {"nodes": 21651, "D0": 21344, "D1": 307, "TERMINATED": 48, "CENSORED_STREAM_END": 21603},
          {"nodes": L["nodes"], "D0": _i(L["depth"].get("D0")), "D1": _i(L["depth"].get("D1")), "TERMINATED": _i(L["status"].get("TERMINATED")), "CENSORED_STREAM_END": _i(L["status"].get("CENSORED_STREAM_END"))},
          "chain depth is flat: D0 and D1 only, termination rare, censoring the norm")
    not_tested("F-19", "interstage delay by transition type is not on the delivered lineage rows as a separate field this pass read")
    check("F-20", {"gaps": 13458}, {"gaps": s["4.14"]["gaps"]}, "recurrence is a within-group measure: the interarrival population equals the within-group gap population")
    not_tested("F-21", "dipole runway STAGES are a 4.12 averaged-companion unit; this pass reads per-second window direction and per-group book imbalance, different units")
    not_tested("F-22", "normalized imbalance at runway stages is not computed here; the per-group depth imbalance is a different estimand")
    sf = t["candidate_same_flip"]
    check("F-23", {"FLIP": 46, "SAME": 44}, {"FLIP": sf.get("FLIP"), "SAME": sf.get("SAME")}, "SAME and FLIP versus the latest predecessor split 44 / 46")
    mc = t["mirror_close"]
    matched = sum(v for k, v in mc.items() if str(k).upper().startswith("MATCH"))
    check("F-24", {"matched_pairs": 0}, {"matched_pairs": matched}, "mirror pairing produced no pairs; the seed hypothesis remains untested, not refuted")
    not_tested("F-25", "conditional transition edges F|A -> C|A are a 4.14 edge census this pass did not build")
    check("F-26", {"T": 2028, "F": 2411}, {"T": t["actions"].get("T"), "F": t["actions"].get("F")}, "2,028 trades produced 2,411 fills: trades almost never sweep")
    for fid in ("F-27", "F-28"):
        not_tested(fid, "per-family, per-touch-state restoration quantiles; this pass computes pooled replenishment only")
    check("F-29", {"episodes": 24283}, {"episodes": _last(out_dir, "4.7")["episodes_matured"]}, "the replenishment episode population is 24,283; the attribution-multiplicity caveat is a rule of the runner's attribution, restated")
    A = t["absorption"]
    check("F-30", {"INDETERMINATE": 24617, "ACCOMPANIED_BY_WITHDRAWAL": 17327, "ABSORBED_WITHOUT_PRICE_MOVE": 1450, "DELIVERED_THROUGH_PRICE": 175},
          {k: A.get(k) for k in ("INDETERMINATE", "ACCOMPANIED_BY_WITHDRAWAL", "ABSORBED_WITHOUT_PRICE_MOVE", "DELIVERED_THROUGH_PRICE")},
          "delivered pressure is rare and withdrawal is the norm, 99 to 1")
    not_tested("F-31", "within-family ratio degeneracy is a per-family quantile claim; pooled here")
    ts = s["4.9"]["touch_state"]
    check("F-32", {"COMPRESSION": 4, "EXPANSION": 4}, {"COMPRESSION": _i(ts.get("COMPRESSION")), "EXPANSION": _i(ts.get("EXPANSION"))},
          "the touch is static within groups: four compressions and four expansions all day")
    not_tested("F-33", "the reopen ladder's per-side gap quantiles are inside one group's ladder rows and were not separated out here")
    for fid in ("F-34", "F-35", "F-41"):
        not_tested(fid, "latency by component count is a stratified claim; this pass keeps pooled latency quantiles")
    not_tested("F-36", "H+N price response medians live on the runner's response companions, not on the delivered track rows this pass tallied")
    for fid in ("F-37", "F-38", "F-39"):
        not_tested(fid, "a statement about the prior run's artifact and its reader's scope, not a claim about the market on this day")
    for fid in ("F-40", "F-42", "F-43"):
        not_tested(fid, "a hypothesis whose falsifier names a second day; one Sunday cannot test it")
    not_tested("F-44", "a list of what one day cannot answer; it holds by construction on this same day")
    return V


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out-dir", required=True)
    p.add_argument("--write", required=True)
    a = p.parse_args(argv)
    V = verdicts(Path(a.out_dir))
    from collections import Counter
    Path(a.write).write_text(json.dumps({"schema": "FRANKIE_SUNDAY_LESSON_VERDICTS_V1", "verdicts": V}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(Counter(v["verdict"] for v in V), indent=1))
    for v in V:
        if v["verdict"] == "REFUTED":
            print("REFUTED", v["lesson_id"], json.dumps(v["computed"].get("mismatch")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
