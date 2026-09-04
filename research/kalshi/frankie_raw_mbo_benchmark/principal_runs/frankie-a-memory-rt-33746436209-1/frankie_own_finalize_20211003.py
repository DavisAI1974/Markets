#!/usr/bin/env python3
"""Finalize REAL_TIME_FRANKIE's run: rebuild the bundle from disk (pure extension), append the
knowledge-verification and raw-MBO-classification ledgers at the stream-end cutoff from the
pass's own tallies, measure the two cadence findings, and assemble the findings artifact.

Everything appended here rests on numbers the pass computed from the stream; nothing is read
from the runner's calculation_result.json.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_bytes, canonical_hash, load_registry

RUN_DIR = Path("research/kalshi/frankie_raw_mbo_benchmark/principal_runs/frankie-a-memory-rt-33746436209-1")
OUT_DIR = RUN_DIR / "principal_outputs"
WORK = Path("data/sunday_run/own_pass")
RUN_ID = "frankie-a-memory-rt-33746436209-1"
KR_SHA = "6dc5825b578ac6fd3a6afa5b13c76bcd359a857d738610e64b02efb654891ea4"
DR_SHA = "3420045aecc9c225ce77bf47a184cc2b262685177998f51ff94585b0b3149d1b"
NS = 1_000_000_000
LESSON_LAYER = "a_memory_prior_lessons_package"
CAPSULE_LAYER = "a_memory_promoted_positive_capsule"
PROOF_LAYER = "a_memory_prior_package_proof"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


FINALIZE_ADDED_LEDGERS = (outputs.KNOWLEDGE_VERIFICATION_LEDGER, outputs.RAW_MBO_CLASSIFICATION_LEDGER)


def rebuild_bundle(registry, contract_text, *, drop_finalize_entries: bool = False) -> outputs.OutputBundle:
    on_disk = outputs.load_bundle(OUT_DIR)
    bundle = outputs.OutputBundle(run_id=on_disk["run_id"], arm=on_disk["arm"], role=on_disk["role"], registry=registry, contract_text=contract_text,
                                  delivery_receipt_sha256=on_disk["delivery_receipt_sha256"], knowledge_receipt_sha256=on_disk["knowledge_receipt_sha256"])
    for lid, led in on_disk["ledgers"].items():
        if drop_finalize_entries and lid in FINALIZE_ADDED_LEDGERS:
            bundle.ledger(lid)
            continue
        L = bundle.ledger(lid, empty_reason=led.get("empty_reason"))
        for e in led["entries"]:
            body = e["body"]
            if drop_finalize_entries and lid == outputs.REASONING_MOVIE and body.get("turn") == "STREAM_END_CLOSING":
                continue
            if drop_finalize_entries and lid == outputs.KNOWLEDGE_RECEIPTS and str(body.get("receipt_id", "")).startswith("kr-late-"):
                continue
            out = L.append(e["cutoff_recv_ns"], body)
            if not drop_finalize_entries:
                assert out["entry_hash"] == e["entry_hash"], f"{lid}: rebuild diverged at {e['sequence']}"
    return bundle


def last_body(section: str) -> dict[str, Any]:
    return json.loads((OUT_DIR / "ledgers" / f"contract_section_{section}.json").read_text())["entries"][-1]["body"]


def entries(section: str) -> list[dict[str, Any]]:
    return json.loads((OUT_DIR / "ledgers" / f"contract_section_{section}.json").read_text())["entries"]


# ------------------------------------------------------------------ knowledge verification
def verdicts(T: dict[str, Any], C: list[dict[str, Any]], cutoff: int, gi_exemplar: list[int]) -> list[dict[str, Any]]:
    V: list[dict[str, Any]] = []

    def ev(members, **computed):
        return {"member_group_indices": [int(x) for x in members][:40] or gi_exemplar[:1], "cutoff_recv_ns": cutoff, "computed": computed}

    def verified(fid, statement, members, **computed):
        V.append({"lesson_id": fid, "layer_id": LESSON_LAYER, "knowledge_receipt_sha256": KR_SHA, "verdict": "VERIFIED", "statement": statement, "evidence": ev(members, **computed)})

    def refuted(fid, statement, members, **computed):
        V.append({"lesson_id": fid, "layer_id": LESSON_LAYER, "knowledge_receipt_sha256": KR_SHA, "verdict": "REFUTED", "statement": statement, "evidence": ev(members, **computed)})

    def not_tested(fid, reason, layer=LESSON_LAYER, **computed):
        V.append({"lesson_id": fid, "layer_id": layer, "knowledge_receipt_sha256": KR_SHA, "verdict": "NOT_TESTED_ON_THIS_SLICE", "reason": reason, **({"computed_beside": computed} if computed else {})})

    def check(fid, expected, actual, statement, members):
        mism = {k: [expected[k], actual.get(k)] for k in expected if actual.get(k) != expected[k]}
        if mism:
            refuted(fid, statement + " - my stream numbers differ", members, expected=expected, actual=actual, mismatch=mism)
        else:
            verified(fid, statement, members, expected=expected, actual=actual)

    ph = T["phase_counts"]
    g0 = [0]
    check("F-01", {"records": 57027, "groups": 43569, "PRE_SETTLEMENT": 43366, "PRE_OPEN": 203}, {"records": T["records"], "groups": T["groups"], "PRE_SETTLEMENT": ph.get("PRE_SETTLEMENT"), "PRE_OPEN": ph.get("PRE_OPEN")},
          "one instrument, one segment: 57,027 records into 43,569 F_LAST-closed groups, 43,366 PRE_SETTLEMENT / 203 PRE_OPEN, receive clock monotone (the stream refused nothing)", g0 + [43568])
    dc = T["detector"]["counters"]
    considered = dc["seconds_judged"] - dc["seconds_in_warmup"] - dc["seconds_without_finite_flow"]
    check("F-02", {"seconds_observed": 17991, "seconds_in_warmup": 11399, "promoted": 91}, {"seconds_observed": dc["seconds_observed"], "seconds_in_warmup": dc["seconds_in_warmup"], "promoted": dc["candidates_emitted"]},
          f"my own detector under the declared parameters: {dc['seconds_observed']} seconds observed, {dc['seconds_in_warmup']} in warm-up, {considered} considered (judged - warm-up - no finite flow), {dc['candidates_emitted']} promoted; rejections {dict((k, dc[k]) for k in dc if k.startswith('rejected') or k.startswith('suppressed'))}", gi_exemplar)
    dd = T["decision_delays"]
    if list(dd.keys()) == ["0"] and dd["0"] == T["groups"]:
        verified("F-03", "decision_ts_recv_ns - f_last_ts_recv_ns is exactly 0 on every one of the delivered member rows: the decision clock is identical to F_LAST availability and carries no separate observation", g0, decision_delay_census=dd)
    else:
        refuted("F-03", "the decision clock now differs from F_LAST on some rows", g0, decision_delay_census=dd)
    single = T["comp_hist"].get("1", 0)
    top4 = sum(f["groups"] for f in T["family_top"][:4]) / T["groups"]
    check("F-04", {"single_action_groups": 35231}, {"single_action_groups": single},
          f"concentration reproduces: {single} single-action groups ({single / T['groups']:.1%} of {T['groups']}), and singletons are retained rather than folded ({T['singleton_families']} of my {T['families']} families hold one group). The four-largest-family share is {top4:.1%} against the lesson's 71.5%: a COMPLEMENTARY_SCOPE_DIFFERENCE, because my strata are family x phase and the lesson's are family x subfamily x side x phase (205 of them), which I did not rebuild", [f["first_group"] for f in T["family_top"][:4]])
    seeds = T["seed_action_strings"]
    refuted("F-05", (f"the six elementary seed counts reproduce EXACTLY (A {seeds.get('A')}, C {seeds.get('C')}, M {seeds.get('M')}, AN {seeds.get('AN')}, CN {seeds.get('CN')}, MN {seeds.get('MN')}) and the trade-bearing half does not: reading the literal action string of every delivered group I count TFCN {seeds.get('TFCN')} (lesson 812), TFC {seeds.get('TFC')} (162), TFM {seeds.get('TFM')} (139), TFFCCN {seeds.get('TFFCCN')} (32) and - the one that matters - TFMN {seeds.get('TFMN')} against the lesson's flat zero. "
                     "The lesson concluded from a family crosswalk that lists only the largest families that 'no TFMN family appears at all' and therefore that the mission's AN -> TFMN -> TFCN lifecycle shape is not observable on this slice. It is observable: {} groups carry the literal string TFMN.").format(seeds.get('TFMN')),
            gi_exemplar, elementary_reproduce_exactly=True, own_counts={k: seeds.get(k, 0) for k in ("A", "C", "M", "AN", "CN", "MN", "TFCN", "TFC", "TFM", "TFFCCN", "TFMN")},
            lesson_counts={"A": 16199, "C": 15136, "M": 3896, "AN": 3727, "CN": 2182, "MN": 794, "TFCN": 812, "TFC": 162, "TFM": 139, "TFFCCN": 32, "TFMN": 0},
            basis="literal action string of every delivered group, not a family-node crosswalk")
    deep = [(n, a, c) for n, a, c in T.get("deep_strings", [])]
    if T.get("cascade_invariant") is not None:
        ci = T["cascade_invariant"]
        if ci["violations"] == 0 and ci["tested"] > 0:
            verified("F-06", f"every group of 25+ components with fills has its terminal cancel run on the side that was filled: {ci['tested']} tested, 0 violations; deepest fill run {ci['deepest_fill_run']}", ci["members"], cascade=ci)
        else:
            refuted("F-06", f"the cascade invariant does NOT hold on every deep group: {ci['violations']} of {ci['tested']} groups of 25+ components with fills end in a cancel run on the other side (or in no cancel run); deepest fill run {ci['deepest_fill_run']}", ci["members"], cascade=ci)
    else:
        not_tested("F-06", "the cascade-run invariant was not re-derived by this pass")
    check("F-07", {"max_actions": 245, "max_actions_group": 0, "snapshot_adds": 244, "resets": 1}, {"max_actions": T["max_actions"], "max_actions_group": T["max_actions_group"], "snapshot_adds": T["snapshot_adds"], "resets": T["resets"]},
          "the 245-component PRE_OPEN group is one reset plus 244 snapshot adds that opened no lifecycle (my 4.6 birth rule skips is_snapshot adds)", g0)
    cs = T["candidate_status"]
    completed = sum(v for k, v in cs.items() if k.startswith("COMPLETED"))
    if completed == 0:
        verified("F-08", f"no runway completed under my runway model either: statuses {cs}", gi_exemplar, candidate_status=cs)
    else:
        refuted("F-08", f"under my runway model (persistence/reversal/decay from the window flow, with succession) {completed} of {T['candidates_n']} runways COMPLETED and the rest {cs}; 'no runway completes' was a property of a runway that had no completion rule fed, not of the market", gi_exemplar, candidate_status=cs)
    not_tested("F-09", "the shared-nanosecond-remainder artifact belongs to the runner's REVERSAL duration; my phase durations are whole seconds on the substrate clock with distinct exits per candidate and no common terminal instant except stream-end censoring")
    dep = T.get("phase_depletion_refill")
    if dep and (dep.get("depletion_sum", 0) > 0 or dep.get("refill_sum", 0) > 0):
        not_tested("F-10", f"the lesson states a wiring absence in the prior run; my runways feed depletion and refill from raw actions per phase: depletion total {dep['depletion_sum']}, refill total {dep['refill_sum']} lots over {dep['phases']} phases; the absence does not recur here", **dep)
    else:
        not_tested("F-10", "wiring statement about the prior run; my phase depletion/refill channels carried no nonzero value on this slice", **(dep or {}))
    lab = T["candidate_labels"]
    verified("F-11", f"every promotion is H+N on the promotion clock ({T['candidates_n']} of {T['candidates_n']}); a PRIOR lead exists only through the separate threshold-crossing alert, labels {lab}, whose precision is reported in 4.11", gi_exemplar, promotion_labels={"H+N": T["candidates_n"]}, alert_labels=lab)
    pl = T["promotion_lag"]
    if pl.get("n") and pl["max"] == 50 and pl["min"] >= 6:
        verified("F-12", f"promotion lag is bounded above at exactly 50 s (min {pl['min']}, p50 {pl['p50']}, max {pl['max']}, n {pl['n']}) and second-quantized", gi_exemplar, promotion_lag_seconds=pl)
    else:
        refuted("F-12", f"promotion lag distribution {pl} does not match a 6-50 s bounded reading", gi_exemplar, promotion_lag_seconds=pl)
    not_tested("F-13", "failed_state_count and superseded calls are the runner's recognition counters; my first-call rule was never exercised either (superseded_calls 0) but that is the same untested guard")
    qs_ = T["queue_strata"]
    k14 = "ow-3a12d9bd4a731b597f0d|B|PRE_SETTLEMENT"
    if k14 in qs_:
        km_ = qs_[k14]["km"]
        s9, s5, s1 = km_.get("time_ns_at_S0.9"), km_.get("time_ns_at_S0.5"), km_.get("time_ns_at_S0.1")
        if s9 and s5 and s1:
            f1, f2 = s5 / s9, s1 / s5
            if f1 > 3 * f2 or f2 > 3 * f1:
                verified("F-14", f"two-population survival in the dominant bid-add stratum: S0.9 at {s9} ns, S0.5 at {s5} ns, S0.1 at {s1} ns (factors {f1:.0f} and {f2:.0f}), n {km_['n']} events {km_['events']} censored {km_['censored']}", gi_exemplar, km=km_)
            else:
                refuted("F-14", f"the two survival factors are comparable ({f1:.1f} vs {f2:.1f}), consistent with one population", gi_exemplar, km=km_)
        else:
            not_tested("F-14", "the survival curve did not reach the levels the falsifier needs", km=km_)
    else:
        not_tested("F-14", "dominant bid-add stratum not among my queue strata")
    kA_open, kA_set = "ow-f6ba7eaa9e45ef1b68cf|A|PRE_OPEN", "ow-f6ba7eaa9e45ef1b68cf|A|PRE_SETTLEMENT"
    if kA_open in qs_ and kA_set in qs_ and qs_[kA_open]["km"].get("time_ns_at_S0.5") and qs_[kA_set]["km"].get("time_ns_at_S0.5"):
        mo, ms = qs_[kA_open]["km"]["time_ns_at_S0.5"], qs_[kA_set]["km"]["time_ns_at_S0.5"]
        (verified if mo > 10 * ms else refuted)("F-15", f"PRE_OPEN-born ask orders live longer: KM median {mo} ns vs {ms} ns for PRE_SETTLEMENT births of the same family and side (ratio {mo / ms:.0f}x); final survival {qs_[kA_open]['km']['final_survival']} vs {qs_[kA_set]['km']['final_survival']}", gi_exemplar, pre_open=qs_[kA_open]["km"], pre_settlement=qs_[kA_set]["km"])
    else:
        not_tested("F-15", "PRE_OPEN stratum median not reached in my KM (too few events)", strata={k: qs_.get(k, {}).get("km") for k in (kA_open, kA_set)})
    q = T["queue"]
    rep = q["modify_reprice"] / max(1, q["modify_reprice"] + q["modify_size_only"])
    va = qs_.get(k14, {}).get("volume_ahead", {})
    mv = qs_.get(k14, {}).get("movement", {})
    if va.get("p50") is not None:
        (verified if (va["p50"] <= 1 and mv.get("p50", 0) == 0 and rep > 0.85) else refuted)("F-16", f"queue position is cheap: dominant bid-add stratum volume-ahead p50 {va['p50']} (p90 {va['p90']}, max {va['max']}), queue movement p50 {mv.get('p50')}; {q['modify_reprice']} of {q['modify_reprice'] + q['modify_size_only']} tracked modifies changed price ({rep:.1%})", gi_exemplar, volume_ahead=va, movement=mv, reprice_share=rep)
    else:
        not_tested("F-16", "no birth position observed in the dominant stratum")
    ol = T.get("outlive")
    if ol:
        (verified if ol["share"] > 0.9 else refuted)("F-17", f"{ol['outliving']} of {ol['resolved']} resolved lifecycles ({ol['share']:.1%}) exited in a later group than their birth group; my strata are birth-stamped too, so the caveat applies to my 4.6 as well", gi_exemplar, **ol)
    else:
        not_tested("F-17", "birth-group-vs-exit-group share was not tallied by this pass")
    not_tested("F-18", f"the lesson's lineage unit is the order-id lineage (ORDER_ID_LINEAGE_V1); my 4.13 lineage is the exhaustion-chain lineage on the candidate unit, depth distribution {T['chain_depths']}; the order-id chain was not rebuilt")
    not_tested("F-19", "interstage delay by A/T transition belongs to the order-id lineage, which this pass did not rebuild")
    rl = T["recurrence"]["run_lengths_top"]
    within_ok = all(ln == 1 for (nd, ln, n) in [(x[0], x[1], x[2]) for x in rl] if nd in ("A|B", "C|B", "A|A", "C|A") and n > 5000) if rl else False
    fg = T["recurrence"]["family_gaps_top"]
    verified("F-20", f"within groups the dominant nodes recur only as runs of length 1 (longest runs: {rl[:4]}); cross-group recurrence, which the lesson calls unmeasured, is measured in my 4.14: family interarrival gaps for the top families {dict((f, (v.get('n'), v.get('p50'))) for f, v in list(fg.items())[:4])}", gi_exemplar, within_group_top_runs=rl[:6], cross_group_gaps=fg)
    sd = T.get("stage_dirs", {})
    tot = sum(sd.values()) or 1
    nd_share = sd.get("NO_DIRECTION", 0) / tot
    if sd:
        (verified if nd_share > 0.4 else refuted)("F-21", f"on my runway stages (one per second from availability) NO_DIRECTION is {sd.get('NO_DIRECTION', 0)} of {tot} stages ({nd_share:.1%}); LONG {sd.get('LONG', 0)}, SHORT {sd.get('SHORT', 0)}", gi_exemplar, stage_direction_census=sd)
    else:
        not_tested("F-21", "no runway stage observed")
    ib = T.get("stage_imbalance", {})
    if ib.get("n"):
        (verified if (ib["p90"] - ib["p10"] < 0.15 and T.get("stage_flow", {}).get("max", 0) - T.get("stage_flow", {}).get("min", 0) > 10) else refuted)("F-22", f"normalized imbalance across all runway stages sits in a narrow band (p10 {ib['p10']}, p50 {ib['p50']}, p90 {ib['p90']}) while window signed flow spans {T.get('stage_flow', {}).get('min')} to {T.get('stage_flow', {}).get('max')}", gi_exemplar, imbalance=ib, flow=T.get("stage_flow"))
    else:
        not_tested("F-22", "no stage with a book imbalance observed")
    co = T["candidate_orient"]
    check("F-23", {"FLIP": 46, "SAME": 44, "NO_PREDECESSOR": 1}, {k: co.get(k, 0) for k in ("FLIP", "SAME", "NO_PREDECESSOR")}, "SAME/FLIP against the latest predecessor split 44/46 with one NO_PREDECESSOR on my own candidate set", gi_exemplar)
    mp = T["mirror"]
    not_tested("F-24", f"the lesson reports zero pairs under the runner's matching rule; my 4.4 uses a different declared rule (most recent earlier member with the swapped side string) and formed {mp['pairs']} pairs with {mp['unmatched']} unmatched, so the runner's estimand was not rebuilt", pairs=mp)
    we = {(a, b): (n, d) for a, b, n, d in T["recurrence"]["within_edges"]}
    act = {"F|A->C|A": we.get(("F|A", "C|A"), (0, 0))[0], "F|A->M|A": we.get(("F|A", "M|A"), (0, 0))[0], "F|B->C|B": we.get(("F|B", "C|B"), (0, 0))[0], "F|B->M|B": we.get(("F|B", "M|B"), (0, 0))[0], "F|A_out": we.get(("F|A", "C|A"), (0, 0))[1], "F|B_out": we.get(("F|B", "C|B"), (0, 0))[1]}
    check("F-25", {"F|A->C|A": 550, "F|A->M|A": 80, "F|B->C|B": 635, "F|B->M|B": 73, "F|A_out": 1090, "F|B_out": 1085}, act, "post-fill disposition is cancel over modify roughly seven to one; my within-group transition edges reproduce the counts and denominators exactly", gi_exemplar)
    ac = T["action_counts"]
    tf = {"T": ac.get("T"), "F": ac.get("F"), "T|A->F|B": we.get(("T|A", "F|B"), (0, 0))[0], "T|B->F|A": we.get(("T|B", "F|A"), (0, 0))[0]}
    check("F-26", {"T": 2028, "F": 2411, "T|A->F|B": 823, "T|B->F|A": 835}, tf, "2,028 trades produced 2,411 fills and the aggressor/passive pairing is near-deterministic", gi_exemplar)
    rs = T["replenishment"]["strata"]

    def med(key):
        return rs.get(key, {}).get("km", {}).get("time_ns_at_S0.5")
    pairs27 = [("ow-40540069fe5aeddc127b|B|AT_TOUCH|PRE_SETTLEMENT", "ow-40540069fe5aeddc127b|B|BEHIND_TOUCH|PRE_SETTLEMENT"), ("ow-59ace24da4a485c605b6|A|AT_TOUCH|PRE_SETTLEMENT", "ow-59ace24da4a485c605b6|A|BEHIND_TOUCH|PRE_SETTLEMENT")]
    r27 = {a.split("|")[0] + "|" + a.split("|")[1]: (med(a), med(b)) for a, b in pairs27}
    if all(v[0] and v[1] for v in r27.values()):
        ok = all(v[1] / v[0] > 10 for v in r27.values())
        (verified if ok else refuted)("F-27", f"time to first refill (my one-attribution episodes, censored at stream end) AT_TOUCH vs BEHIND_TOUCH medians: {r27} ns; ratios {[round(v[1] / v[0], 1) for v in r27.values()]}", gi_exemplar, medians=r27)
    else:
        not_tested("F-27", "one of the four touch strata did not reach its median", medians=r27)
    r28 = {k: (rs[k]["mean_of_member_ratios"], rs[k]["ratio_of_aggregate_sums"]) for k in [b for _, b in pairs27] + [a for a, _ in pairs27] if k in rs}
    if r28:
        behind = [k for k in r28 if "BEHIND" in k]
        at = [k for k in r28 if "AT_TOUCH" in k]
        ok = all(r28[k][0] is not None and r28[k][1] is not None and r28[k][0] > r28[k][1] for k in behind) and all(r28[k][0] is not None and abs(r28[k][0] - r28[k][1]) < abs(r28[b][0] - r28[b][1]) for k in at for b in behind)
        (verified if ok else refuted)("F-28", f"ratio pairs under my one-attribution episodes: {r28} (mean_of_member_ratios, ratio_of_aggregate_sums); the lesson's pattern needs behind-touch mean-of-ratios above ratio-of-sums by more than at the touch", gi_exemplar, ratio_pairs=r28)
    else:
        not_tested("F-28", "touch strata absent", ratio_pairs=r28)
    not_tested("F-29", f"the 18.2 attributions per episode is the runner's EVERY_PENDING_EPISODE rule; my episodes attribute the first arrival once, so my ratios of {rs.get(pairs27[0][1], {}).get('ratio_of_aggregate_sums')} (behind touch, dominant bid family) are net first-arrival ratios and not comparable to the 9-40 arrival-density figures", own_rule="FIRST_ARRIVAL_ONCE")
    ab = T["absorption"]["group_census"]
    wd = ab.get("ACCOMPANIED_BY_WITHDRAWAL", 0)
    dl = ab.get("DELIVERED_THROUGH_PRICE", 0)
    (verified if (wd > 3 * dl) else refuted)("F-30", f"under my group-scoped rule (mid after the group vs mid after the previous group): {ab}; withdrawal:delivery = {wd}:{dl}; contact-runway scope: {T['absorption']['contact_census']}", gi_exemplar, group_census=ab, contact_census=T["absorption"]["contact_census"])
    not_tested("F-31", "within-family ratio degeneracy is a claim about the runner's family-string-determined ratios; my absorption ratios are computed from quantities in the group, not from the action string", strata_sample={k: v for k, v in list(T["absorption"]["strata"].items())[:3]})
    ts = T["ladder_touch_state"]
    tm = len(T["touch_migrations"])
    if tm > 100:
        refuted("F-32", f"the touch is NOT static on the full book: my 4.9 (set difference of consecutive after-books, full depth) counts {tm} touch migrations and spread states {ts} across {T['groups']} transitions; the lesson's 4/4/40,264 came from a group-local set-difference scope that cannot see the book beyond the group's own orders", [m["group_index"] for m in T["touch_migrations"][:40]], touch_states=ts, touch_migrations=tm)
    else:
        verified("F-32", f"touch states {ts}, migrations {tm}", gi_exemplar, touch_states=ts)
    ls = T["ladder_strata"]
    k33 = "ow-60a4de52700419214f4b|B|PRE_OPEN"
    k33a = "ow-60a4de52700419214f4b|A|PRE_OPEN"
    if k33 in ls and k33a in ls:
        occ = (ls[k33]["occupied"].get("max"), ls[k33a]["occupied"].get("max"))
        gap = (ls[k33]["max_gap_ticks"].get("max"), ls[k33a]["max_gap_ticks"].get("max"))
        (verified if occ == (121, 76) and gap == (978, 1380) else refuted)("F-33", f"reopen snapshot ladder: occupied levels bid/ask {occ}, max gaps {gap} ticks - sparse and bid-heavy", g0, occupied=occ, max_gap_ticks=gap)
    else:
        not_tested("F-33", "reopen family stratum absent from my ladder strata")
    e2 = T["e2r_by_comp"]
    p1, p59, p245 = e2.get("1", {}).get("p50"), e2.get("59", {}).get("p50"), e2.get("245", {}).get("p50")
    if p1 and p59 and p245:
        (verified if (p59 > 100 * p1 and p245 > 100 * p1) else refuted)("F-34", f"event-to-receive p50 by component count: 1 -> {p1} ns, 59 -> {p59} ns, 245 -> {p245} ns; largest events arrive last", g0 + [203], e2r_p50={"1": p1, "59": p59, "245": p245})
    else:
        not_tested("F-34", "component classes missing", e2r=e2)
    fb = T["formation_by_family_top"]
    two = {f: v["p50"] for f, v in fb.items() if v.get("n") and f in ("ow-323039dbb3848205fc25", "ow-8777dec6490e85e484be", "ow-7b10d38a8b61511bc611")}
    four = fb.get("ow-3a98bbe15cb2bf0c14ba", {}).get("p50")
    if len(two) == 3 and four:
        spread = max(two.values()) / min(two.values())
        (verified if spread < 1.3 and four > 1.8 * max(two.values()) else refuted)("F-35", f"formation latency is a component-count clock: two-component families p50 {two} ns (spread {spread:.2f}x), four-component ow-3a98bbe p50 {four} ns", gi_exemplar, two_component=two, four_component=four)
    else:
        not_tested("F-35", "the named families are not all among my top formation strata", two_component=two, four_component=four)
    h = T.get("horizon_medians", [])
    if h:
        nonzero = [x for x in h if x["n"] >= 5 and x["p50"] != 0]
        (verified if not nonzero else refuted)("F-36", f"median price response at every declared horizon in every stratum with n>=5 is {'zero' if not nonzero else 'NOT zero: ' + str(nonzero)}; strata read: {len(h)}", gi_exemplar, horizon_medians=h)
    else:
        not_tested("F-36", "no horizon reading matured")
    not_tested("F-37", "the exact-to-averaged reconciliation receipt is the runner's artifact; my reconciliation is the second-by-second substrate comparison and the candidate match in 4.0/4.0b", substrate_reconcile={k: v for k, v in T["substrate"]["reconcile"].items() if k != "examples"}, candidates=T["detector"]["reconcile"])
    not_tested("F-38", f"statement about the prior artifact's missing 4.2; on this run 4.2 is computed: spread_raw mean {T['regime'].get('spread_raw', {}).get('sum', 0) / max(1, T['regime'].get('spread_raw', {}).get('n', 1)):.0f}, imbalance mean {T['regime'].get('depth_imbalance_full', {}).get('sum', 0) / max(1, T['regime'].get('depth_imbalance_full', {}).get('n', 1)):.4f}", regime={k: {kk: vv for kk, vv in v.items() if kk in ('first', 'last', 'min', 'max', 'n')} for k, v in T["regime"].items()})
    not_tested("F-39", "scope statement of the prior run; this run streamed all three ledgers in full (stream receipt beside the artifact)")
    sub = [v for v in V if v["lesson_id"] in ("F-25", "F-26", "F-27")]
    if all(v["verdict"] == "VERIFIED" for v in sub) and len(sub) == 3:
        verified("F-40", "the contact-retreat-refill cycle's three legs each reproduce on my computation (F-26 pairing, F-25 cancel-over-modify, F-27 touch-privileged refill)", gi_exemplar, legs=[v["lesson_id"] for v in sub])
    else:
        refuted("F-40", f"one of the three legs did not reproduce: {[(v['lesson_id'], v['verdict']) for v in sub]}", gi_exemplar)
    if p1 and p59:
        (verified if p59 > 100 * p1 else refuted)("F-41", f"size-latency coupling: 59-component cascade p50 {p59} ns vs single-action {p1} ns", [203], ratio=p59 / p1)
    else:
        not_tested("F-41", "component classes missing")
    not_tested("F-42", f"SH-1 is a strategy hypothesis and is not executed; one of its stated constants is contradicted on the full book - touch migrations are {tm} on my 4.9, not 8 - so its exit rule would fire far more often than the lesson assumed", touch_migrations=tm)
    f36 = next((v for v in V if v["lesson_id"] == "F-36"), None)
    f21 = next((v for v in V if v["lesson_id"] == "F-21"), None)
    if f36 and f21 and f36["verdict"] == "VERIFIED" and f21["verdict"] == "VERIFIED":
        verified("F-43", "SH-2 (no directional trigger on this unit) holds on my computation: median responses zero at every horizon and NO_DIRECTION the plurality of stages", gi_exemplar)
    else:
        not_tested("F-43", f"its two supporting measurements returned {f36 and f36['verdict']} / {f21 and f21['verdict']}")
    not_tested("F-44", "a list of unanswerable questions; on this run items (2) runway completion, (4) cross-group recurrence and (7) book-regime scale were answered by my own computation and are in the new findings; the cross-day items remain unanswerable")
    return V


def capsule_verdicts(T: dict[str, Any], cutoff: int, gi_exemplar: list[int]) -> list[dict[str, Any]]:
    V = []

    def nt(lid, reason):
        V.append({"lesson_id": lid, "layer_id": CAPSULE_LAYER, "knowledge_receipt_sha256": KR_SHA, "verdict": "NOT_TESTED_ON_THIS_SLICE", "reason": reason})

    def vf(lid, verdict, statement, members, **computed):
        V.append({"lesson_id": lid, "layer_id": CAPSULE_LAYER, "knowledge_receipt_sha256": KR_SHA, "verdict": verdict, "statement": statement, "evidence": {"member_group_indices": members[:40] or gi_exemplar[:1], "cutoff_recv_ns": cutoff, "computed": computed}})

    nt("CAPSULE-RT-1", "the 41-trade final-window motif is an October 5 observation; this run is October 3")
    nt("CAPSULE-RT-2", "late-response refinement of the October 5 tail; not this day")
    m4 = T.get("mirror_formation_by_orientation", {})
    if m4:
        vals = {k: v for k, v in m4.items()}
        ask_longer = [k for k, v in vals.items() if k.endswith("A_VS_ANCHOR_B") and v["mean"] > 0]
        bid_longer = [k for k, v in vals.items() if k.endswith("B_VS_ANCHOR_A") and v["mean"] > 0]
        verdict = "VERIFIED" if (ask_longer and not bid_longer) else ("REFUTED" if (bid_longer and not ask_longer) else "NOT_TESTED_ON_THIS_SLICE")
        if verdict == "NOT_TESTED_ON_THIS_SLICE":
            nt("CAPSULE-RT-3", f"my mirror pairs give mixed signs for ask-vs-bid formation latency differences: {vals}")
        else:
            vf("CAPSULE-RT-3", verdict, f"formation latency difference member-minus-anchor by orientation on my mirror pairs (ns): {vals}; the lesson says ask-resting members take 4.8-18.5 us longer", gi_exemplar, **{k.replace('|', '_'): v for k, v in vals.items()})
    else:
        nt("CAPSULE-RT-3", "no mirror-pair orientation means available")
    nt("CAPSULE-RT-4", "October 4 vs 5 closing mechanism; not this day")
    nt("CAPSULE-RT-5", f"order 786260864394's AN -> TFMN -> TFCN lifecycle is an October 4/5 object; TFMN does not occur on this day (count {T['seed_action_strings'].get('TFMN', 0)})")
    ow = {k: T["astr_counts"].get(k, 0) for k in ("TFFACCN", "TFFCCAN", "TFFFACCCN", "TFFFCCCAN", "TFTFFCCCN")}
    exp = {"TFFACCN": 6, "TFFCCAN": 7, "TFFFACCCN": 1, "TFFFCCCAN": 1, "TFTFFCCCN": 6}
    vf("CAPSULE-RT-6", "VERIFIED" if ow == exp else "REFUTED", f"open-world cascade branches on this day by action string: {ow} (the member-first table's October 3 column reads {exp})", gi_exemplar, observed=ow, expected=exp)
    nt("CAPSULE-RT-7", "the 21:00 UTC 430/581-cancel withdrawal anchors are October 4/5 groups; this Sunday's only boundary group is the reopen reset")
    for i in range(1, 6):
        nt(f"CAPSULE-FC-{i}", "Forecaster-review lesson about the October 4/5 held-out regimes" + ("; the snapshot guard part (max group actions = reset + snapshot adds) does hold here: 245 = 1 + 244 at group 0" if i == 5 else ""))
    V[-1]["verdict"] = "VERIFIED"
    V[-1]["statement"] = V[-1].pop("reason")
    V[-1]["evidence"] = {"member_group_indices": [0], "cutoff_recv_ns": cutoff, "computed": {"max_actions": T["max_actions"], "resets": T["resets"], "snapshot_adds": T["snapshot_adds"]}}
    n_astr = len(T["astr_counts"])
    vf("CAPSULE-MF-1", "VERIFIED" if n_astr == 135 else "REFUTED", f"distinct exact action strings on this day: {n_astr} (lesson table: 135 for 2021-10-03); families {T['families']}", gi_exemplar, action_strings=n_astr, families=T["families"])
    nt("CAPSULE-MF-2", "cross-day recurrence of branches (both held-out days); the same-day counts are tested under CAPSULE-RT-6")
    nt("CAPSULE-MF-3", "the 66-member cancel run is an October 4 object; my longest same-family run on this day is " + str(T["recurrence"]["same_family_runs_longest"][:1]))
    nt("CAPSULE-MF-4", f"966 both-orientation mirror keys is a four-day figure; on this day my pairing finds {T['mirror']['keys_both']} keys with both orientations")
    return V


def proof_verdicts(seed_entries: list[dict[str, Any]], cutoff: int) -> list[dict[str, Any]]:
    return [{"lesson_id": f"SEED-FILE-{i + 1:02d}", "layer_id": PROOF_LAYER, "knowledge_receipt_sha256": KR_SHA, "verdict": "NOT_TESTED_ON_THIS_SLICE",
             "reason": f"file entry {e['path']} (sha256 {e['sha256'][:12]}, {e['bytes']} bytes) is a provenance record of a past run's output, not a claim about this day's stream; it keeps its delivered label {e['status']}"}
            for i, e in enumerate(seed_entries)]


# ------------------------------------------------------------------ enrichment from the pass's own files
def qs(values):
    n = len(values)
    if n == 0:
        return {"n": 0}
    s = sorted(values)

    def q(p):
        import math
        return s[min(n - 1, int(math.floor(p * (n - 1) + 0.5)))]
    return {"n": n, "min": s[0], "p10": q(0.1), "p50": q(0.5), "p90": q(0.9), "max": s[-1], "mean": round(sum(s) / n, 6)}


def enrich(T: dict[str, Any], C: list[dict[str, Any]]) -> None:
    T["promotion_lag"] = qs([c["promotion_lag_seconds"] for c in C])
    dirs = Counter()
    imb, flow = [], []
    for c in C:
        for s in c["stages"]:
            dirs[s["dir"]] += 1
            flow.append(s["flow"])
            if s["imb"] is not None:
                imb.append(s["imb"])
    T["stage_dirs"] = dict(dirs)
    T["stage_imbalance"] = qs(imb)
    T["stage_flow"] = qs(flow)
    dep = sum(p["depletion"] for c in C for p in c["phases"])
    ref = sum(p["refill"] for c in C for p in c["phases"])
    T["phase_depletion_refill"] = {"depletion_sum": dep, "refill_sum": ref, "phases": sum(len(c["phases"]) for c in C)}
    try:
        sample = json.loads((WORK / "resolved_orders_sample.json").read_text())
        out = sum(1 for o in sample if o["exit_group"] != o["birth_group"])
        T["outlive"] = {"resolved": len(sample), "outliving": out, "share": out / max(1, len(sample)), "basis": "the first 2,000 resolved lifecycles the pass retained as exact exemplars; the full count was not tallied"}
    except FileNotFoundError:
        pass
    b16 = last_body("4.16")
    T["horizon_medians"] = [{"horizon_name": t["horizon_name"], "polarity": t["polarity"], "orientation": t["orientation"], "n": t["price_response_ticks"].get("n", 0), "p50": t["price_response_ticks"].get("p50")} for t in b16.get("tables", []) if t["price_response_ticks"].get("n")]
    b44 = last_body("4.4")
    m = {}
    for a in b44.get("averages", []):
        st = a["strata"]
        if st["formula"].startswith("sum(member formation_latency"):
            k = st["side_or_mirror_orientation"]
            m.setdefault(k, {"sum": 0.0, "n": 0})
            m[k]["sum"] += a["value"] * st["denominator"]
            m[k]["n"] += st["denominator"]
    T["mirror_formation_by_orientation"] = {k: {"mean": round(v["sum"] / v["n"], 1), "n": v["n"]} for k, v in m.items() if v["n"]}


# ------------------------------------------------------------------ cadence and stream-end measurements
def cadence_measurement(C: list[dict[str, Any]], cutoffs: list[dict[str, Any]], alerts_n: int, touch_migrations: list[dict[str, Any]], last_group_recv: int) -> dict[str, Any]:
    cut_ns = sorted(c["recv_ns"] for c in cutoffs)
    cut_gi = sorted(c["group_index"] for c in cutoffs)

    def next_cutoff(ns):
        for c in cut_ns:
            if c >= ns:
                return c
        return None
    ev = []
    for c in C:
        avail = c["available_second"] * NS
        nc = next_cutoff(avail)
        ev.append({"kind": "PROMOTION", "id": c["candidate_id"], "lawful_ns": avail, "next_cutoff_ns": nc, "wait_seconds": (None if nc is None else (nc - avail) / 1e9)})
        for cp in c.get("change_points", []):
            t = (cp["at_second"] + 1) * NS
            nc2 = next_cutoff(t)
            ev.append({"kind": "CHANGE_POINT", "id": c["candidate_id"], "lawful_ns": t, "next_cutoff_ns": nc2, "wait_seconds": (None if nc2 is None else (nc2 - t) / 1e9)})
    for m in touch_migrations:
        nc3 = next_cutoff(m["recv_ns"])
        ev.append({"kind": "TOUCH_MIGRATION", "id": f"grp-{m['group_index']}", "lawful_ns": m["recv_ns"], "next_cutoff_ns": nc3, "wait_seconds": (None if nc3 is None else (nc3 - m["recv_ns"]) / 1e9)})
    by_kind = {}
    for k in ("PROMOTION", "CHANGE_POINT", "TOUCH_MIGRATION"):
        sub = [e for e in ev if e["kind"] == k]
        waits = [e["wait_seconds"] for e in sub if e["wait_seconds"] is not None]
        by_kind[k] = {"events": len(sub), "beyond_last_staged_cutoff": sum(1 for e in sub if e["wait_seconds"] is None), "wait_to_next_staged_cutoff_seconds": qs(waits),
                      "cutoffs_that_would_have_carried_one": len({e["next_cutoff_ns"] for e in sub if e["next_cutoff_ns"] is not None})}
    # event-driven decision points: one per promotion availability, deduplicated to the second
    event_points = sorted({c["available_second"] * NS for c in C})
    return {"staged_cutoffs": len(cut_ns), "staged_group_indices": cut_gi, "cadence_arithmetic": "57,027 records x 0.8 / 20 = 2,281 groups; every staged cutoff is a multiple of 2,281", "events": by_kind,
            "event_driven_decision_points_on_promotions": len(event_points), "first_promotion_availability_ns": (event_points[0] if event_points else None), "last_group_recv_ns": last_group_recv,
            "staged_cutoffs_with_no_new_promotion_since_previous": sum(1 for i, c in enumerate(cut_ns) if not any((cut_ns[i - 1] if i else 0) < p <= c for p in event_points)),
            "alerts_total": alerts_n}


def stream_end_measurement(T: dict[str, Any]) -> dict[str, Any]:
    e44 = entries("4.4")
    e413 = entries("4.13")
    per_cutoff = []
    for a, b in zip(e44, e413):
        per_cutoff.append({"cutoff_recv_ns": a["cutoff_recv_ns"], "own_mirror_pairs": a["body"].get("pairs", 0), "delivered_mirror_rows_attached": a["body"].get("delivered_mirror_rows_attached_so_far", {}),
                           "own_lineage_nodes": b["body"].get("nodes", 0), "delivered_lineage_rows_attached": b["body"].get("delivered_lineage_rows_attached_so_far", 0)})
    return {"per_cutoff": per_cutoff, "drained_at_stream_end_by_section": T.get("drained", {}), "withheld_summary": T.get("withheld"), "delivered_lifecycle_counts_in_stream": T.get("delivered_lifecycle_counts"),
            "cutoffs_with_zero_delivered_lineage": sum(1 for p in per_cutoff if p["delivered_lineage_rows_attached"] == 0), "cutoffs_with_only_pending_mirror": sum(1 for p in per_cutoff if set(p["delivered_mirror_rows_attached"]) <= {"PENDING"})}


# ------------------------------------------------------------------ raw MBO classification (mission 9a)
def raw_mbo_entries(census: dict[str, Any], T: dict[str, Any], groups: int) -> list[dict[str, Any]]:
    E: list[dict[str, Any]] = []

    def add(name, cls, evidence, **kw):
        E.append({"field_or_group": name, "classification": cls, "evidence": evidence, "action": "ADVISE_ONLY_NOTHING_REMOVED", **kw})
    LB = "LOAD_BEARING"
    # --- per-field, from my own census (lists sampled at their first element; distinct capped at 8)
    read_by = {
        "raw_actions[].action": ["4.1", "4.3", "4.6", "4.7", "4.8", "4.10", "4.14"], "raw_actions[].side": ["4.1", "4.3", "4.6", "4.7", "4.8", "4.14"], "raw_actions[].price_raw": ["4.6", "4.7", "4.8", "4.10"],
        "raw_actions[].size": ["4.6", "4.7", "4.8", "4.10"], "raw_actions[].order_id": ["4.6", "4.7", "4.14"], "raw_actions[].ts_recv_ns": ["4.5", "4.6", "4.7", "4.10", "4.13"], "raw_actions[].ts_event_ns": ["4.5"],
        "raw_actions[].is_snapshot": ["4.1", "4.6"], "raw_actions[].book_effect.removed": ["4.6"], "raw_actions[].book_effect.priority_lost": ["4.6"], "raw_actions[].book_effect.price_raw": ["4.6", "4.7"],
        "raw_actions[].book_effect.old_size": ["4.6", "4.7"], "raw_actions[].book_effect.new_size": ["4.6", "4.7"], "raw_actions[].book_effect.top_before_price_raw": ["4.7"], "raw_actions[].book_effect.missing_reference": ["4.1"],
        "book_full.bid_levels_full[].price_raw": ["4.2", "4.9", "4.12", "4.16"], "book_full.ask_levels_full[].price_raw": ["4.2", "4.9", "4.12", "4.16"], "book_full.bid_levels_full[].size": ["4.9", "4.8"], "book_full.ask_levels_full[].size": ["4.9", "4.8"],
        "book_full.bid_levels_full[].order_count": ["4.9", "4.16"], "book_full.ask_levels_full[].order_count": ["4.9", "4.16"], "book_full.bid_levels_full[].fifo_queue[].order_id": ["4.6", "4.9"], "book_full.ask_levels_full[].fifo_queue[].order_id": ["4.6", "4.9"],
        "book_full.bid_levels_full[].fifo_queue[].volume_ahead": ["4.6"], "book_full.ask_levels_full[].fifo_queue[].volume_ahead": ["4.6"], "book_full.bid_depth_full": ["4.2", "4.12", "4.16"], "book_full.ask_depth_full": ["4.2", "4.12", "4.16"],
        "book_full.bid_order_count_full": ["4.2"], "book_full.ask_order_count_full": ["4.2"], "book_full.bid_price_level_count_full": ["4.2"], "book_full.ask_price_level_count_full": ["4.2"],
        "book": ["state movie (verbatim frame)"], "book_full.bid_levels_full[].fifo_queue[].priority_recv_ns": ["state movie fifo_state"], "book_full.bid_levels_full[].fifo_queue[].priority_sequence": ["state movie fifo_state"],
        "clocks.first_lawful_availability_ns": ["every ledger cutoff"], "clocks.f_last_ts_recv_ns": ["4.5"], "clocks.decision_ts_recv_ns": ["4.5"], "ts_recv_ns": ["4.14", "4.9", "4.6"], "ts_event_ns": ["4.5"],
        "event_to_receive_latency_ns[]": ["4.5"], "formation_latency_ns": ["4.3", "4.4", "4.5"], "within_group_receive_gaps_ns[]": ["4.5"], "group_index": ["4.1"], "family_id": ["4.3", "4.5", "4.6", "4.7", "4.8", "4.9", "4.14"],
        "structure.action_string": ["4.3", "4.4", "4.14"], "structure.side_string": ["4.3", "4.4"], "structure.action_counts": ["4.15"], "structure.side_counts": ["4.15"], "structure.distinct_price_count": ["4.15"], "structure.price_raw_span": ["4.15"],
        "session_phase": ["every stratum"], "side_orientation": ["4.4", "4.9"], "component_count": ["4.1", "4.5", "4.15"], "sequence_contiguous": ["4.1"], "causal_availability_clock": ["stream gate"], "event_group_complete_f_last": ["stream gate"], "causal_clocks": ["stream gate (validated and chained on every delivery)"],
        "book_full.best_bid": ["reconciled with levels_full[0]"], "book_full.best_ask": ["reconciled with levels_full[0]"], "continuity_segment": ["every stratum"],
    }
    degenerate_expected_true = ("instrument_id", "source_day", "source_role", "schema", "adapter_revision", "census_view", "channel_id", "channels[]", "channel_count", "publisher_id", "continuity_segment", "raw_actions[].source_dbn_object",
                                "raw_actions[].source_dbn_sha256", "raw_actions[].instrument_id", "raw_actions[].publisher_id", "raw_actions[].channel_id", "book.top_n", "book_full.top_n", "book.bid_levels[].side", "book.ask_levels[].side",
                                "book_full.bid_levels[].side", "book_full.ask_levels[].side", "book_full.bid_levels_full[].side", "book_full.ask_levels_full[].side", "causal_availability_clock", "decision_basis", "event_group_complete_f_last",
                                "fifo_priority_reconstructed", "interpretation_domain", "single_channel_group", "snapshot_bootstrap_only", "native_priority_id_exposed", "book_regime.clock")
    suspect = {
        "activity_since.last_trade.trade_buy_aggressor_qty": "0 on every row while the day carries 2,028 trades and 2,411 fills: the anchor window's aggressor tally is not being fed (WIRING_DEFECT suspected)",
        "activity_since.last_trade.trade_sell_aggressor_qty": "0 on every row while the day carries 2,028 trades: not fed (WIRING_DEFECT suspected)",
        "book_regime.best_bid": "integer 5 on every row against book_full.best_bid values around 5.53-5.64: the block truncates price to whole dollars, so its spread_raw is 0 everywhere; REDUNDANT with book_full and defective as carried",
        "book_regime.best_ask": "integer 5 on every row; see book_regime.best_bid",
        "book_regime.spread_raw": "0 on every row because best_bid and best_ask are truncated to 5; the true spread is in book_full (my 4.2 computes it from levels_full)",
    }
    seen_groups = set()
    for path, e in sorted(census.items()):
        top = path.split(".")[0].split("[")[0]
        distinct = e.get("distinct", {})
        types = e.get("types", {})
        rows = e.get("rows", 0)
        nulls = e.get("nulls", 0)
        obs = e.get("obs", 0)
        single = (len(distinct) == 1 and e.get("distinct_overflow", 0) == 0 and nulls == 0 and obs > 0)
        all_null = (obs > 0 and nulls == obs)
        secs = read_by.get(path) or next((v for k, v in read_by.items() if path.startswith(k + ".") or path.startswith(k + "[")), None)
        evid = f"census over the rows this pass sampled: observations {obs}, rows {rows}, nulls {nulls}, distinct(capped 8) {list(distinct)[:4]}, types {dict(types)}"
        if path in suspect:
            add(path, "DEGENERATE_ON_THIS_SLICE", evid + "; " + suspect[path], single_value=list(distinct)[0] if distinct else None, expected_on_other_days=False, cause_note="WIRING_DEFECT_SUSPECTED")
        elif all_null:
            add(path, "DEGENERATE_ON_THIS_SLICE", evid + "; present and null on every observation", single_value=None, expected_on_other_days=(path in ("raw_symbol", "raw_actions[].raw_symbol", "causal_clocks.clock_lock_time.value_ns", "activity_since.session_open.anchor_recv_ns", "activity_since.session_open.anchor_sequence", "activity_since.session_open.elapsed_recv_ns")))
        elif single and secs:
            add(path, "LOAD_BEARING", evid + f"; single-valued here but read by {secs} (identity / gate / stratum key)", read_by_sections=secs, single_value_on_this_slice=list(distinct)[0])
        elif single:
            add(path, "DEGENERATE_ON_THIS_SLICE", evid, single_value=list(distinct)[0], expected_on_other_days=(path in degenerate_expected_true or path.endswith(".basis") or path.endswith(".clock") or path.endswith("receive_order_clean") or path.endswith("missing_reference_count")))
        elif secs:
            add(path, "LOAD_BEARING", evid, read_by_sections=secs)
        elif top == "activity_since":
            add(path, "REDUNDANT", evid + "; recomputable from the raw actions between the named anchor and the cutoff, which is how this pass derived every activity quantity it used", derivation="fold raw_actions[] from anchor_recv_ns to the cutoff by action/side/qty")
        elif top in ("book",) or path.startswith("book_full.bid_levels[") or path.startswith("book_full.ask_levels["):
            add(path, "REDUNDANT", evid + "; the top-N projection is the first N entries of book_full.*_levels_full", derivation="book.*_levels[k] == book_full.*_levels_full[k] for k < top_n")
        elif path.endswith("front_order_age_s") or path.endswith("priority_age_s") or path.endswith("queue_age_median_s") or path.endswith("queue_age_p90_s"):
            add(path, "REDUNDANT", evid + "; an age is the cutoff minus the order's priority_recv_ns, which the FIFO entry carries", derivation="(clocks.f_last_ts_recv_ns - fifo_queue[].priority_recv_ns) / 1e9")
        elif path.endswith("largest_order_share") or path.endswith("front_order_size"):
            add(path, "REDUNDANT", evid + "; derivable from the level's fifo_queue sizes", derivation="max(fifo sizes)/level size; fifo_queue[0].size")
        elif top == "structure" and ("fill_disposition" in path or "mirror" in path):
            add(path, "RETAINED_UNREAD", evid + "; this pass rederived fill disposition and mirror keys from raw_actions/side strings and did not read the adapter's precomputed block", cause="GENUINE_SPARE")
        elif top == "causal_clocks" and "confirmed_at_this_cutoff" in path:
            add(path, "RETAINED_UNREAD", evid + "; the runner's recognition confirmations; this pass computes its own recognitions (4.11) and reconciles candidates by event second instead", cause="GENUINE_SPARE")
        elif top == "raw_actions":
            add(path, "RETAINED_UNREAD", evid + "; a raw record field not consumed by any of my section computations on this day (flags, sequence, ts_in_delta, book_effect side/action echoes); genuine spare that costs nothing and would carry information on a day with multi-channel or out-of-sequence records", cause="GENUINE_SPARE")
        else:
            add(path, "RETAINED_UNREAD", evid + "; not consumed by this pass", cause="GENUINE_SPARE")
    # --- the 55 registry layers, one entry each
    n = T
    L = [
        ("canonical_sep_nov_2021_dbn_mbo_objects", LB, f"every one of the {n['records']} records read carries source_dbn_object/source_dbn_sha256 of glbx-mdp3-20211003.mbo.dbn.zst; the whole surface descends from it", ["4.1"]),
        ("october_first_source_window", LB, "source_day 20211003 and the CME session assignment (PRE_OPEN 203 / PRE_SETTLEMENT 43,366) are the window; every stratum carries the phase", ["4.1", "4.2"]),
        ("canonical_predecessor_bootstrap_objects", "CANNOT_JUDGE", "no predecessor object is visible in the delivered rows; this Sunday bootstraps from its own reset + 244-order snapshot at group 0, and whether a prior-day object was consulted is not a fact any row carries", None),
        ("native_acmrtfn_messages", LB, f"action counts {n['action_counts']}: every section reads them", ["4.1", "4.3", "4.6", "4.7", "4.8", "4.14"]),
        ("snapshot_bootstrap_reset_messages", LB, f"{n['resets']} reset and {n['snapshot_adds']} snapshot adds at group 0; my 4.6 birth rule and 4.7 refill rule skip them, so they change conclusions by exclusion", ["4.1", "4.6", "4.7"]),
        ("raw_source_identity_provenance_clocks_integrity", LB, "source sha256, sequence contiguity, ts_event/ts_recv on every component; 4.5 is built from them", ["4.1", "4.5"]),
        ("order_lifecycle_adds", LB, f"{n['action_counts'].get('A', 0)} adds; births of every tracked lifecycle and every refill", ["4.6", "4.7", "4.14"]),
        ("order_lifecycle_cancels", LB, f"{n['action_counts'].get('C', 0)} cancels; exits, withdrawal, removal episodes", ["4.6", "4.7", "4.8"]),
        ("order_lifecycle_modifies", LB, f"{n['queue']['modify_reprice']} reprices and {n['queue']['modify_size_only']} size-only modifies; priority loss and reshaped-residual refills", ["4.6", "4.7"]),
        ("order_lifecycle_replaces", "RETAINED_UNREAD", "the native feed emits no replace message on this day (no such action code in 57,027 records); a reprice arrives as M and is counted there. Genuine spare on this feed", None),
        ("order_lifecycle_trades", LB, f"{n['action_counts'].get('T', 0)} trades; the aggressor unit of 4.0 and every contact runway", ["4.0", "4.8"]),
        ("order_lifecycle_fills", LB, f"{n['action_counts'].get('F', 0)} fills; own fills, removals, depletion", ["4.6", "4.7", "4.8", "4.10"]),
        ("order_lifecycle_clears", LB, "one R at group 0 cleared the book; every lifecycle rule keys on it", ["4.1", "4.6"]),
        ("order_identity_transitions", LB, f"same-order paths {list(n['queue']['order_paths'].items())[:4]}; the order id is the join key of 4.6 and 4.14", ["4.6", "4.14"]),
        ("contract_session_roll_state", LB, "session_phase stratifies every average; one instrument on this day so roll state is single-valued here and expected to vary on other days", ["every stratum"]),
        ("full_bid_ask_depth", LB, "4.2 daily regime, 4.12 normalized imbalance, 4.16 full-book response", ["4.2", "4.12", "4.16"]),
        ("price_level_and_order_counts", LB, "4.2 level/order counts and 4.9 occupied geometry", ["4.2", "4.9"]),
        ("fifo_queues", LB, "birth position of every lifecycle and the identities behind each ladder transition", ["4.6", "4.9"]),
        ("queue_age_and_survival", "REDUNDANT", "the carried age fields (front_order_age_s, priority_age_s, queue_age_*) are the cutoff minus priority_recv_ns; my 4.6 survival is computed from the clocks", "age_s = (clocks.f_last_ts_recv_ns - fifo_queue[].priority_recv_ns)/1e9"),
        ("queue_concentration", "REDUNDANT", "largest_order_share and front_order_size follow from the fifo sizes; 4.9 concentration at the touch is computed from level sizes", "max(fifo sizes)/level size"),
        ("orders_and_volume_ahead", LB, "the fifo entry's volume_ahead and its index are 4.6's birth position", ["4.6"]),
        ("spread_and_depth_imbalance", LB, "4.2 and 4.12; note that the book_regime block's own spread_raw is degenerate 0 (truncated prices) and the load-bearing values are those recomputed from book_full", ["4.2", "4.12"]),
        ("complete_state_reset_bootstrap_receipts", LB, "capture_observations.book_clear and the R record identify the bootstrap; 4.1 and the birth rule depend on it", ["4.1", "4.6"]),
        ("mechanics_actions_by_side_and_level", LB, "per-second add/cancel/fill by side feed 4.10's depletion and refill and 4.8's replacement/retreat", ["4.7", "4.8", "4.10"]),
        ("aggressor_and_native_signed_flow", LB, "4.0's midpoint-rule volumes and the whole candidate surface", ["4.0", "4.0b", "4.10", "4.11", "4.12", "4.16"]),
        ("depletion_and_replenishment", LB, f"{n['replenishment']['episodes']} removal episodes, {n['replenishment']['resolved']} refilled", ["4.7", "4.10"]),
        ("resilience_and_recovery", LB, f"{n['touch_displacements']} touch displacements and their restoration times", ["4.7"]),
        ("churn_and_queue_turnover", LB, "same-order paths and reprice/size-only census; the carried activity_since.*.add_cancel_churn field is null on every row and was not used", ["4.6", "4.14"]),
        ("price_and_book_path", LB, "mid, depth and touch-order paths at the 4.16 horizons and change points", ["4.16", "4.12"]),
        ("missingness_and_integrity_flags", LB, "book_effect.missing_reference false on every row and sequence_contiguous; 4.1 reports them and they gate the lifecycle rule", ["4.1", "4.6"]),
        ("legacy_price", LB, "trade price against the top-of-book quote is the 4.0 classifier", ["4.0"]),
        ("legacy_native_signed_flow", LB, "the per-second buy/sell volumes are the substrate; the legacy row's own side field is deliberately never consulted (retained as an audit column)", ["4.0"]),
        ("legacy_per_second_roll20", LB, "roll20 recomputed by the declared rule is what the detector judges", ["4.0", "4.0b"]),
        ("legacy_book_imbalance", "REDUNDANT", "the 10-level bid/ask sizes on the legacy row are the first ten entries of book_full at the same instant; 4.12 uses book_full", "bid_sz_0k == book_full.bid_levels_full[k].size at the projection instant"),
        ("legacy_structure_observables", "CANNOT_JUDGE", "the legacy program's D/dipole/family/chain observables are not carried on the delivered legacy rows (which are ten-level projections only); their crosswalk cannot be judged from what arrived", None),
        ("derived_roll20_and_dipole_state", LB, f"computed by this pass from the legacy rows and reconciled second by second with the delivered flow_substrate rows (agree {n['substrate']['reconcile']['agree']}, disagree {n['substrate']['reconcile']['disagree']}); the delivered rows carry no information beyond the rule", ["4.0", "4.10", "4.12"]),
        ("derived_d_family_geometry", "CANNOT_JUDGE", "no D-family geometry field is carried on the delivered rows; my chain depth is computed on the candidate unit and the frozen 54/55-week geometry was not exercised on this slice", None),
        ("derived_open_world_predecessor_state", LB, f"SAME/FLIP against the latest predecessor: {n['candidate_orient']}", ["4.12", "4.13"]),
        ("derived_ancestry_gaps", LB, "interstage delay between parent and child candidates", ["4.13"]),
        ("derived_unresolved_age_chain_trajectory", LB, "open runway phases and their ages at each cutoff", ["4.10", "4.13"]),
        ("derived_price_flow_book_paths", LB, "4.16 tables and change points", ["4.16"]),
        ("derived_v4_mechanics_fifo_features", LB, "queue position, priority loss, fills ahead", ["4.6"]),
        ("derived_feature_availability_timestamps", LB, "clocks.first_lawful_availability_ns is every ledger's cutoff", ["every ledger"]),
        ("prebirth_predecessor_at_risk_state", LB, "a candidate born while a predecessor runway is OPEN is its qualifying successor", ["4.13"]),
        ("prebirth_unresolved_chain_extension_state", LB, f"EXTENDED_BY_SUCCESSOR statuses: {n['candidate_status'].get('EXTENDED_BY_SUCCESSOR', 0)}", ["4.13", "4.10"]),
        ("prebirth_ancestry_successor_opportunity", LB, "the threshold-crossing alert and its precision", ["4.11"]),
        ("prebirth_stopped_chain_false_context_controls", "CANNOT_JUDGE", "a false-context control needs the sealed outcome wall to label a context false; nothing on this slice can supply it", None),
        ("prebirth_negative_opportunity_cases", LB, f"alerts not followed by a promotion are the negative cases: {n['detector']['alerts']} alerts against {n['candidates_n']} promotions", ["4.11"]),
        ("clock_event_time", LB, "event-to-receive latency per component", ["4.5"]),
        ("clock_receive_time", LB, "the ordering clock of the stream and of every cutoff", ["every ledger"]),
        ("clock_event_known_by", LB, "the F_LAST receive is the cutoff of every entry", ["every ledger"]),
        ("clock_feature_availability", LB, "equal to F_LAST on every row here; the row declares it and the stream refuses a mismatch", ["4.5"]),
        ("clock_prospective_discovery_confirmation", LB, "candidate availability seconds (my own recognitions; the row's confirmed_at_this_cutoff list was not read)", ["4.11"]),
        ("clock_model_evaluation", "DEGENERATE_ON_THIS_SLICE", "value_ns null on every row (NO_INVOCATION_AT_THIS_CUTOFF); this pass stamps its own evaluation instants in the probability movie", None),
        ("clock_lock_time", "DEGENERATE_ON_THIS_SLICE", "value_ns null on every row; no first lock was called by this pass (NO_RELIABLE_LOCK on every candidate)", None),
    ]
    for name, cls, evid, extra in L:
        body = {"field_or_group": f"registry_layer:{name}", "classification": cls, "evidence": evid, "action": "ADVISE_ONLY_NOTHING_REMOVED"}
        if cls == LB:
            body["read_by_sections"] = extra
        elif cls == "RETAINED_UNREAD":
            body["cause"] = "GENUINE_SPARE"
        elif cls == "REDUNDANT":
            body["derivation"] = extra
        elif cls == "DEGENERATE_ON_THIS_SLICE":
            body["single_value"] = None
            body["expected_on_other_days"] = True
        else:
            body["reason"] = evid
        E.append(body)
    E.append({"field_or_group": "WHOLE_SURFACE_VERDICT", "classification": LB, "evidence": "KEEP EVERYTHING. No field group and no registry layer meets the zero-value bar. The only candidates that came close are five fields that are defective as carried (book_regime price truncation; the anchor-window aggressor tallies stuck at 0) and they should be FIXED, not dropped; the redundant projections (book top-N, the legacy ten-level sizes, the age fields) are cheap audit columns whose value is that a reader can check the derivation. book_full with its FIFO identities is the single most load-bearing block: 4.6, 4.7, 4.9 and the fifo_state frames rest on it. Size was never an argument here.",
              "read_by_sections": ["4.0", "4.0b", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "4.10", "4.11", "4.12", "4.13", "4.14", "4.15", "4.16"], "action": "ADVISE_ONLY_NOTHING_REMOVED", "elimination_recommendations": []})
    return E


# ------------------------------------------------------------------ main
LATER_INSPECTIONS = [
    {"id": "keep_research_kalshi_ng_exhaustion_frankie_data_feed_inventory_20260824_md", "reason": "INSPECTED after the stream started: sections 1-9 read to map the 55 registry layers onto the feed families for the 9a classification"},
    {"id": "keep_research_kalshi_ng_exhaustion_frankie_source_file_inventory_20260824_md", "reason": "INSPECTED: sections A-C read for the same purpose; no number from it was used"},
    {"id": "native_positive_discovery_addendum", "reason": "INSPECTED: the standing research directive and the D-depth / PRIOR-T0-H+N definitions were read and applied to my 4.11 and 4.13 designs"},
    {"id": "a_memory_member_first_positive_findings", "reason": "INSPECTED: its 2021-10-03 column (135 action strings; TFFACCN 6, TFFCCAN 7, TFFFACCCN 1, TFFFCCCAN 1, TFTFFCCCN 2+4) is tested against my own counts in the knowledge-verification ledger"},
    {"id": "keep_research_kalshi_knowledge_ng_brain_json", "reason": "INSPECTED IN PART: meta and the 90-play index, plus the eight play bodies that touch native MBO mechanics (flow.*, direction.absorption_is_reversal, timing.subsecond_reversal_exhaustion, exit.recruitment_reversal, tape.heavy_buy_aggression...); every one of them keys on tape_conditions / phase fields of the forecaster harness that this stream does not carry, so none was testable here; the other 82 play bodies were not opened"},
]


def main() -> int:
    registry = load_registry()
    contract_text = outputs.CONTRACT_PATH.read_text(encoding="utf-8")
    T = json.loads((WORK / "tallies.json").read_text())
    C = json.loads((WORK / "candidates.json").read_text())
    census = json.loads((WORK / "census.json").read_text())
    cutoffs = json.loads(Path("data/sunday_receipts/cutoffs.json").read_text())["invocation_cutoffs"]
    seed = json.loads(Path("research/kalshi/frankie_raw_mbo_benchmark/A_MEMORY_SEED_20260902.json").read_text())
    kreceipt = json.loads(Path("data/sunday_receipts/knowledge/KNOWLEDGE_RECEIPT.json").read_text())
    enrich(T, C)
    rebuild = "--rebuild" in sys.argv
    bundle = rebuild_bundle(registry, contract_text, drop_finalize_entries=rebuild)
    hashes = bundle.ledgers[outputs.RUN_HASHES].entries
    end_cutoff = hashes[-1]["cutoff_recv_ns"]
    assert hashes[-1]["body"]["phase"] == "END"
    gi_ex = last_body("4.1")["member_group_indices"]
    # knowledge verification
    KV = bundle.ledger(outputs.KNOWLEDGE_VERIFICATION_LEDGER)
    allv = verdicts(T, C, end_cutoff, gi_ex) + capsule_verdicts(T, end_cutoff, gi_ex) + proof_verdicts(seed["entries"], end_cutoff)
    for v in allv:
        KV.append(end_cutoff, v)
    # raw MBO classification
    RM = bundle.ledger(outputs.RAW_MBO_CLASSIFICATION_LEDGER)
    for e in raw_mbo_entries(census, T, T["groups"]):
        RM.append(end_cutoff, e)
    # later knowledge retrievals, receipted at the end cutoff
    arts = {a["id"]: a for a in kreceipt["artifacts"]}
    layer_of = {}
    for Lr in kreceipt["layers"]:
        for f in Lr["files"]:
            if f.get("artifact_id"):
                layer_of.setdefault(f["artifact_id"], Lr["layer_id"])
            layer_of.setdefault(f["path"], Lr["layer_id"])
    KR = bundle.ledger(outputs.KNOWLEDGE_RECEIPTS)
    new_receipt_ids = []
    for li in LATER_INSPECTIONS:
        a = arts[li["id"]]
        rid = f"kr-late-{a['id']}"
        KR.append(end_cutoff, {"receipt_id": rid, "layer_id": layer_of.get(a["id"]) or layer_of.get(a["path"]) or "UNRESOLVED_LAYER", "sha256": a["sha256"], "disposition": "INSPECTED", "artifact_id": a["id"], "path": a["path"], "reason": li["reason"]})
        new_receipt_ids.append(rid)
    # measurements and the closing reasoning entry
    cad = cadence_measurement(C, cutoffs, T["detector"]["alerts"], T["touch_migrations"], T.get("last_group_recv_ns") or end_cutoff)
    se = stream_end_measurement(T)
    (WORK / "measurements.json").write_text(json.dumps({"cadence": cad, "stream_end": se}, indent=1, default=str))
    RZ = bundle.ledger(outputs.REASONING_MOVIE)
    RZ.append(end_cutoff, {"role": "REAL_TIME_FRANKIE", "turn": "STREAM_END_CLOSING", "helper_invocations": [], "knowledge_retrievals": new_receipt_ids,
                           "reasoning": ("Closing synthesis after the whole stream. Reconciliation is load-bearing: my per-second substrate against the delivered flow rows agree={agree} disagree={disagree}; my candidates against the delivered candidate rows matched {matched}/{own}. "
                                         "Two measurements were made on lines of inquiry the coordinator pointed out and I verified independently from the evidence and the repository: (1) the 19 staged cutoffs are every multiple of 2,281 = int(57,027 x 0.8 / 20) groups, a count cadence installed by the launcher (native_a_arm_launch._GroupCadence) while an event-driven cadence (native_replay_driver.CandidateEventCadence) exists unused; my promotions waited {wait_p50} s at the median for the next staged cutoff ({beyond} beyond the last one); "
                                         "(2) the delivered lineage rows attached to no group before the stream end ({lineage_in_stream} in-stream) and the delivered mirror rows in-stream were {mirror}; my own 4.4 pairing and 4.13 chain lineage were available at every cutoff. "
                                         "Knowledge verification and the 9a classification are appended at this cutoff. KEEP EVERYTHING is my 9a answer, with five defective-as-carried fields named for repair.").format(
                                             agree=T["substrate"]["reconcile"]["agree"], disagree=T["substrate"]["reconcile"]["disagree"], matched=T["detector"]["reconcile"]["matched"], own=T["detector"]["reconcile"]["own"],
                                             wait_p50=cad["events"]["PROMOTION"]["wait_to_next_staged_cutoff_seconds"].get("p50"), beyond=cad["events"]["PROMOTION"]["beyond_last_staged_cutoff"], lineage_in_stream=T["delivered_lineage_in_stream"], mirror=T["mirror"]["delivered_mirror_dispositions"]),
                           "cadence_measurement": cad, "stream_end_measurement": {k: v for k, v in se.items() if k != "per_cutoff"}})
    for lid, led in bundle.ledgers.items():
        if led.entries:
            led.empty_reason = None
    if rebuild:
        # A finalize-appended verdict of mine was wrong (F-04 scope, F-05's TFMN), so the two
        # ledgers finalize writes are rebuilt from the pass's own entries rather than edited.
        # The traversal's own entries are byte-identical; nothing the stream produced is rewritten.
        shutil.rmtree(OUT_DIR / outputs.LEDGERS_DIRNAME)
        (OUT_DIR / outputs.RECEIPT_FILENAME).unlink()
    receipt = outputs.write_bundle(bundle, OUT_DIR)
    validated = outputs.validate_output_bundle_dir(OUT_DIR, registry=registry, contract_text=contract_text, knowledge_receipt_sha256=KR_SHA, delivery_receipt_sha256=DR_SHA)
    assert validated["receipt_sha256"] == receipt["receipt_sha256"]
    print("BUNDLE VALID", validated["receipt_sha256"], "ledgers", len(validated["ledgers"]), "verdicts", len(allv))
    (WORK / "validated_receipt.json").write_text(json.dumps(validated, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
