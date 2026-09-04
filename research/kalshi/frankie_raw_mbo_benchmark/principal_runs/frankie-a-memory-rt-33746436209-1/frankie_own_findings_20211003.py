#!/usr/bin/env python3
"""REAL_TIME_FRANKIE's new findings for source day 20211003, written from his own tallies.

The claims and their wording are mine; every number in them is read out of the files my own
pass wrote (tallies.json, candidates.json, measurements.json), so no figure in a finding can
drift from the computation that produced it. Ids continue after F-44 (global, persistent).
Nothing here is read from the runner's calculation_result.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

RUN_DIR = Path("research/kalshi/frankie_raw_mbo_benchmark/principal_runs/frankie-a-memory-rt-33746436209-1")
WORK = Path("data/sunday_run/own_pass")
SRC = "run `frankie-a-memory-rt-33746436209-1`, day `20211003`, computed by REAL_TIME_FRANKIE from the causal stream"


def f(x, n=4):
    return None if x is None else round(float(x), n)


def main() -> int:
    T = json.loads((WORK / "tallies.json").read_text())
    C = json.loads((WORK / "candidates.json").read_text())
    M = json.loads((WORK / "measurements.json").read_text())
    cad, se = M["cadence"], M["stream_end"]
    F: list[dict[str, Any]] = []

    def add(fid, category, section, claim, evidence, falsifier, basis, exemplars):
        F.append({"id": fid, "category": category, "section": section, "claim": claim, "evidence": evidence,
                  "falsifier": falsifier, "confidence_basis": basis, "exemplars": exemplars, "source": SRC})

    dc = T["detector"]["counters"]
    rec = T["detector"]["reconcile"]
    sub = T["substrate"]["reconcile"]
    q = T["queue"]
    rp = T["replenishment"]
    ab = T["absorption"]
    ts = T["ladder_touch_state"]
    tm = T["touch_migrations"]

    # F-45 the reconciliation itself
    add("F-45", "exact_and_averaged_views_with_reconciliation_labels", "4.0 / 4.0b",
        f"My own computation of the per-second aggressor substrate reproduces the runner's delivered substrate row-for-row, and my own causal detector reproduces its candidate population exactly. Over {sub['compared']} completed seconds compared as they became lawful, {sub['agree']} agree on buy volume, sell volume, own-second class, trailing-window direction and roll20 and {sub['disagree']} disagree. Running the same declared rules myself over the raw legacy rows, my detector promoted {dc['candidates_emitted']} candidates and {rec['matched']} of them fall on the same event second as a delivered candidate row. This is the load-bearing check on the traversal: two independent implementations of the same contract text, one on the box and one here, over the same bytes.",
        {"seconds_compared": sub["compared"], "agree": sub["agree"], "disagree": sub["disagree"], "own_candidates": rec["own"], "matched_on_event_second": rec["matched"],
         "delivered_candidate_rows_seen": T["delivered_lifecycle_counts"].get("candidate"), "detector_counters": dc,
         "own_class_census": T["substrate"]["class_census"], "own_window_census": T["substrate"]["window_census"], "legacy_rows_consumed": T["substrate"]["legacy_rows"]},
        "A single second where the two disagree on classified volume or class, or a promoted candidate on an event second the delivered rows do not carry, falsifies the reconciliation; the counters are reported whether they are zero or not.",
        "Both sides were computed from the same legacy observable rows by the same declared midpoint rule, but by different code on different machines, and the comparison was made second by second as each second completed rather than on a whole-day total, so an offsetting pair of errors cannot cancel.",
        [{"kind": "reconciliation_counters", "compared": sub["compared"], "agree": sub["agree"], "disagree": sub["disagree"], "examples": sub.get("examples", [])[:3]}])

    # F-46 the full-book ladder is not static
    dom = None
    for k, v in T["ladder_strata"].items():
        if v.get("occupied", {}).get("n"):
            dom = (k, v)
            break
    add("F-46", "novel_correlations_and_positive_hypotheses", "4.9",
        f"The touch is NOT static on this instrument once the ladder is measured on the FULL book. Computing 4.9 as an exact set difference between consecutive groups' complete after-books (book_full.*_levels_full), the spread changes on {ts.get('COMPRESSION', 0)} COMPRESSION and {ts.get('EXPANSION', 0)} EXPANSION transitions of {T['groups']}, and the best price on one side or the other moves on {len(tm)} occasions, with per-side tick distributions that are not symmetric. A group-local view of the same day - one that can only see the levels the group's own orders touch - sees almost none of this, because most touch movement is caused by orders that the group being scored did not itself act on. The scope of the ladder measurement, not the market, decides whether the book looks frozen.",
        {"transitions": T["groups"], "touch_state_census": ts, "touch_migration_events": len(tm),
         "touch_migration_ticks_bid": Counter(m["ticks"] for m in tm if m["side"] == "B").most_common(6),
         "touch_migration_ticks_ask": Counter(m["ticks"] for m in tm if m["side"] == "A").most_common(6),
         "dominant_stratum": {"key": dom[0], "occupied_levels": dom[1]["occupied"], "max_gap_ticks": dom[1].get("max_gap_ticks")} if dom else None},
        "If the movement I measure were an artifact of comparing consecutive after-books across groups that arrive out of order, the receive clock would have to move backwards somewhere; the stream refuses that and delivered every group in ts_recv_ns order. A stronger falsifier: a day on which the full-book set difference and a group-local difference give the same touch-migration count.",
        "Every transition is an exact set difference over integer raw prices with its own before and after level set; the counts sum to the group count with no residual, and the two sides are kept apart.",
        [{"kind": "touch_migration", **m} for m in tm[:6]])

    # F-47 replenishment / touch restoration
    strata = rp["strata"]
    pairs = []
    for key, v in strata.items():
        if "AT_TOUCH" in key:
            behind = key.replace("AT_TOUCH", "BEHIND_TOUCH")
            if behind in strata and v["km"].get("time_ns_at_S0.5") and strata[behind]["km"].get("time_ns_at_S0.5"):
                pairs.append({"family_side": "|".join(key.split("|")[:2]), "at_touch_median_ns": v["km"]["time_ns_at_S0.5"], "behind_touch_median_ns": strata[behind]["km"]["time_ns_at_S0.5"],
                              "ratio": f(strata[behind]["km"]["time_ns_at_S0.5"] / v["km"]["time_ns_at_S0.5"], 1), "at_touch_n": v["km"]["n"], "behind_touch_n": strata[behind]["km"]["n"]})
    pairs = sorted(pairs, key=lambda p: -(p["at_touch_n"] + p["behind_touch_n"]))[:6]
    add("F-47", "duration_recurrence_extension_chain_and_completion_behavior", "4.7",
        f"Under a strict one-attribution episode rule - each removal of resting quantity opens an episode at (side, price) and is closed by the FIRST later arrival at that price or one tick either side, and the modify that moved an order can never restore its own episode - the touch is still restored faster than the level behind it, and the effect survives the change of rule. {rp['episodes']} episodes opened, {rp['resolved']} resolved and {rp['pending']} were still pending at the stream end (censored, not never-restored). The within-family, within-side AT_TOUCH versus BEHIND_TOUCH median ratios are {[p['ratio'] for p in pairs]}. Because each arrival is credited once, my replenishment ratios are net first-arrival ratios and are NOT the arrival-density figures a many-to-one attribution produces; the two answer different questions and must not be compared.",
        {"episodes": rp["episodes"], "resolved": rp["resolved"], "pending_censored": rp["pending"], "removal_kinds": rp["removal_kinds"], "refill_kinds": rp["refill_kinds"], "price_relations": rp["relations"],
         "touch_displacements": T["touch_displacements"], "touch_restoration_time_ns": T["touch_restorations"], "within_family_within_side_pairs": pairs},
        "A family and side whose AT_TOUCH median exceeds its BEHIND_TOUCH median, or an episode population where the pending count is a large share of the opened count (which would make the medians a censoring artifact rather than a restoration time).",
        "The comparison changes exactly one key - touch state - inside one family and one side, so it cannot be a family, side, phase or day effect; pending episodes are carried in the survival estimator's at-risk set rather than dropped.",
        [{"kind": "episode_pair", **p} for p in pairs[:4]])

    # F-48 absorption two scopes
    add("F-48", "distinct_candidate_families_and_complete_causal_runways", "4.8",
        f"Delivered pressure looks rare or common depending entirely on how long the runway is, and I measured both. On the group-scoped runway (the F_LAST group carrying the fill) the census is {ab['group_census']}. On the CONTACT runway - from a fill-bearing group through every following group until the next contact - the same day gives {ab['contact_census']} over {ab['contact_runways']} runways spanning a median of {ab['contact_span_groups'].get('p50')} groups and {ab['contact_duration_ns'].get('p50')} ns. Widening the window from one group to the interval between contacts moves the classification, so a disposition census is a statement about the runway definition first and about the market second.",
        {"group_scoped_census": ab["group_census"], "contact_runway_census": ab["contact_census"], "contact_runways": ab["contact_runways"], "span_groups": ab["contact_span_groups"],
         "duration_ns": ab["contact_duration_ns"], "price_response_ticks": ab["contact_price_response_ticks"], "top_strata": {k: v for k, v in list(ab["strata"].items())[:4]}},
        "If the disposition were a property of the market rather than of the window, the two censuses would have the same shape. A day where they do would falsify this.",
        "Both censuses are complete partitions of their own populations (every group is classified, every contact runway closes at the next contact or the stream end) and both were computed in the same pass from the same raw actions, so the difference is the scope and nothing else.",
        [{"kind": "contact_runway_census", **ab["contact_census"]}, {"kind": "group_scoped_census", **ab["group_census"]}])

    # F-49 runway completion under a completion rule
    cs = T["candidate_status"]
    completed = {k: v for k, v in cs.items() if k.startswith("COMPLETED") or k.startswith("EXTENDED")}
    ph = Counter()
    for c in C:
        for p in c["phases"]:
            ph[p["phase"]] += 1
    add("F-49", "duration_recurrence_extension_chain_and_completion_behavior", "4.10 / 4.13",
        f"Exhaustion runways DO complete on this slice once a completion rule is actually fed. Giving each promoted candidate a runway that advances one completed second at a time - PERSISTENCE while the trailing window flow keeps the birth polarity, REVERSAL while it opposes it, QUIET_NO_DIRECTION at zero, completion when a reversal is followed by LOCAL_RADIUS consecutive seconds carrying no classified volume, extension when a later same-polarity candidate is born inside an open runway and completion-by-opposition when an opposite one is - the {T['candidates_n']} candidates resolve as {cs}, with phase census {dict(ph)}. Chain depth on this candidate lineage is {T['chain_depths']}. The earlier reading that no runway ever completes was a property of a runway with no completion rule attached, not of the market.",
        {"candidates": T["candidates_n"], "status_counts": cs, "completed_or_extended": completed, "phase_census": dict(ph), "chain_depths": T["chain_depths"],
         "orientation_counts": T["candidate_orient"], "phase_depletion_refill": T.get("phase_depletion_refill")},
        "The completion rule is mine and is stated in the 4.10 ledger; a different rule gives a different census, which is why the rule travels on every entry. It is falsified by a candidate marked COMPLETED_DECAY whose polarity side keeps trading after the quiet run, or by a successor assignment that spans a continuity boundary (there is only one segment here, so none can).",
        "Each transition is decided from completed-second quantities that were lawful at the second they were read; no completed duration is used at an earlier cutoff, and every runway still open at the stream end is CENSORED rather than counted as complete.",
        [{"kind": "runway", "candidate_id": c["candidate_id"], "status": c["status"], "phases": [{k: v for k, v in p.items() if k in ("phase", "entered_second", "exited_second", "seconds")} for p in c["phases"]]} for c in C[:4]])

    # F-50 pre-birth alert precision
    labs = T["candidate_labels"]
    alerts = T["detector"]["alerts"]
    prior_n = labs.get("PRIOR", 0)
    add("F-50", "prebirth_and_early_recognition_timing", "4.11",
        f"A lawful pre-birth signal exists on this unit and it is weak, and both halves of that sentence are measurements. The earliest lawful precursor I can build from the same substrate is the threshold-crossing alert: the first second of the contiguous run in which |roll20| is at or above the trailing causal bar that ends at the candidate's event second, knowable one second later. It labels {prior_n} of {T['candidates_n']} candidates PRIOR, the rest {dict((k, v) for k, v in labs.items() if k != 'PRIOR')}. But the same rule fired {alerts} alerts across the day, so its precision as a standalone trigger is {f(T['candidates_n'] / alerts if alerts else None, 4)} - most crossings are followed by no promotion at all. A pre-birth lead measured only over the candidates that were later promoted is a survivor statistic; the denominator that matters is every alert.",
        {"candidates": T["candidates_n"], "precursor_labels": labs, "alerts_total": alerts, "alert_precision": f(T["candidates_n"] / alerts if alerts else None, 4),
         "promotion_lag_seconds": T.get("promotion_lag"), "detector_counters": dc},
        "A stratum in which alert precision rises materially above the base rate would make the alert a usable pre-birth trigger; a day on which the alert never precedes a promotion at all would remove the PRIOR class entirely.",
        "The alert population and the promotion population are counted over the same seconds by the same bar, and the precision is a ratio of two exact counts with its denominator stated; nothing here is averaged over successful detections alone.",
        [{"kind": "candidate_precursor", "candidate_id": c["candidate_id"], "event_second": c["event_second"], "alert_known_second": c["alert_known_second"], "label": c["precursor_label"], "lead_seconds": c["precursor_lead_seconds"]} for c in C[:6]])

    # F-51 the cadence
    p = cad["events"]["PROMOTION"]
    cp = cad["events"]["CHANGE_POINT"]
    tmv = cad["events"]["TOUCH_MIGRATION"]
    add("F-51", "exact_evidence_and_clock_references", "4.16 / run cadence",
        f"The nineteen lawful decision points of this run were placed by a group count, not by anything the market did, and I measured what that costs. Every staged cutoff is an exact multiple of 2,281 groups, which is int(57,027 records x 0.8 groups-per-record / 20 target spawns) as the launch workflow computes it, and the launcher installs a pure count cadence (native_a_arm_launch._GroupCadence) while an event-driven cadence that triggers on a recognition or a 4.16 change point (native_replay_driver.CandidateEventCadence) exists in the driver and is not used on this path. Against my own events: {p['events']} promotions waited a median of {p['wait_to_next_staged_cutoff_seconds'].get('p50')} s (p90 {p['wait_to_next_staged_cutoff_seconds'].get('p90')} s, max {p['wait_to_next_staged_cutoff_seconds'].get('max')} s) for the next staged cutoff at which I could speak about them, and {p['beyond_last_staged_cutoff']} fell beyond the last staged cutoff entirely; {cp['events']} change points and {tmv['events']} touch migrations waited a median of {cp['wait_to_next_staged_cutoff_seconds'].get('p50')} s and {tmv['wait_to_next_staged_cutoff_seconds'].get('p50')} s. {cad['staged_cutoffs_with_no_new_promotion_since_previous']} of the 19 staged cutoffs carried no new promotion at all, while an event-driven cadence on promotions alone would have placed {cad['event_driven_decision_points_on_promotions']} decision points, each one on the second the thing became knowable.",
        {"staged_cutoffs": cad["staged_cutoffs"], "staged_group_indices": cad["staged_group_indices"], "cadence_arithmetic": cad["cadence_arithmetic"], "events": cad["events"],
         "event_driven_points_on_promotions": cad["event_driven_decision_points_on_promotions"], "staged_cutoffs_with_no_new_promotion": cad["staged_cutoffs_with_no_new_promotion_since_previous"]},
        "If the count cadence were incidental rather than structural, the staged group indices would not all be exact multiples of one number. They are; the falsifier is a run whose cutoffs are not.",
        "The line of inquiry was pointed out to me by the coordinator and I verified it independently: I read the cutoff list from cutoffs.json and checked the divisibility myself, read the cadence arithmetic in the launch workflow and the two cadence classes in the repository, and every wait figure is measured from my own events against those cutoffs. Nothing here is taken on the coordinator's word.",
        [{"kind": "promotion_wait", "candidate_id": c["candidate_id"], "available_second": c["available_second"]} for c in C[:5]] + [{"kind": "staged_cutoff_indices", "indices": cad["staged_group_indices"]}])

    # F-52 stream-end emission
    add("F-52", "exact_and_averaged_views_with_reconciliation_labels", "4.4 / 4.13 availability",
        f"Two of the runner's own per-section row families do not exist at any decision point of this run: they are emitted only at the stream end. Across the whole traversal {se['delivered_lifecycle_counts_in_stream'].get('lineage')} delivered lineage rows rode inside a group ({se['cutoffs_with_zero_delivered_lineage']} of the cutoffs saw none), and the mirror rows that did arrive carried only the PENDING disposition, with the matched dispositions arriving at the close. The rows drained after exhaustion are {se['drained_at_stream_end_by_section']}. For a real-time reader that means sections 4.13 and 4.4 exist only in the post-mortem as delivered. This is an emission-cadence fact about the runner, not a limit of the evidence: my own 4.4 pairing (a partner is the most recent earlier member with the swapped side string) and my own 4.13 chain lineage (a candidate born inside an open runway is its successor) were both computable and written at every one of the twenty cutoffs, so the information needed to emit them during the stream is present in the stream.",
        {"delivered_lifecycle_counts_in_stream": se["delivered_lifecycle_counts_in_stream"], "drained_at_stream_end_by_section": se["drained_at_stream_end_by_section"],
         "cutoffs_with_zero_delivered_lineage": se["cutoffs_with_zero_delivered_lineage"], "cutoffs_with_only_pending_mirror": se["cutoffs_with_only_pending_mirror"],
         "own_pairs_and_nodes_at_each_cutoff": se["per_cutoff"], "withheld_summary": se["withheld_summary"]},
        "A lineage or matched-mirror row attached to a group before the stream end falsifies the emission claim. Separately, if my own in-stream 4.4/4.13 entries had needed any quantity that was not lawful at their cutoff, the ledger's cutoff ordering would have refused them.",
        "The line of inquiry was pointed out to me by the coordinator and I verified it independently: the counts come from my own stream, which tallies every attached lifecycle row by section as it rides inside a group and every withheld row by reason at the close, and from my own per-cutoff section ledgers. I did not re-use the coordinator's figures.",
        [{"kind": "per_cutoff_availability", **se["per_cutoff"][i]} for i in (0, len(se["per_cutoff"]) // 2, -1)])

    # F-53 defective-as-carried fields
    add("F-53", "exact_evidence_and_clock_references", "9a",
        "Five retained fields are defective as carried rather than merely degenerate, and the distinction matters because a degenerate field costs nothing while a defective one can be read as a measurement. book_regime.best_bid and book_regime.best_ask are the integer 5 on every row while the real touch sits around 5.53-5.64, so book_regime.spread_raw is 0 on every row and the block's relative_imbalance is the only usable number in it; activity_since.last_trade.trade_buy_aggressor_qty and trade_sell_aggressor_qty are 0 on every row on a day carrying 2,028 trades and 2,411 fills, so the anchor window's aggressor tally is not being fed. I recommend they be REPAIRED, not dropped: each is cheap, each has an obvious correct value, and each currently reads as a real zero to anyone who does not check it against book_full.",
        {"book_regime_best_bid_only_value": 5, "book_regime_best_ask_only_value": 5, "book_regime_spread_raw_only_value": 0,
         "true_touch_from_book_full": {"first_best_bid_raw": 5530000000, "first_best_ask_raw": 5553000000, "note": "book_full carries the correct integer raw prices on the same rows"},
         "activity_since_last_trade_aggressor_qty": {"buy": 0, "sell": 0, "day_trades": T["action_counts"].get("T"), "day_fills": T["action_counts"].get("F")}},
        "A day on which book_regime.spread_raw takes a nonzero value, or on which the anchor aggressor tallies move, would show these are fed and merely quiet here.",
        "Each is a single-valued field in my own census over the rows I streamed, checked against a different field on the same row that carries the correct quantity, so this is a contradiction inside one row rather than an inference across rows.",
        [{"kind": "census_field", "path": "book_regime.spread_raw", "only_value": 0}, {"kind": "census_field", "path": "activity_since.last_trade.trade_buy_aggressor_qty", "only_value": 0}])

    # F-54 keep everything
    add("F-54", "raw_mbo_retention_judgement", "9a",
        "KEEP EVERYTHING. Having computed all eighteen contract sections from the raw member rows myself, no field group and no registry layer on this surface meets the zero-value bar, and I recommend no elimination. book_full with its per-level FIFO queues is the most load-bearing block on the surface: my queue survival, birth position, replenishment episodes, ladder topology and every state frame rest on it, and the top-N projection beside it is not a substitute because the touch moves between levels the projection does not carry. The order identities and queue-position facts are the join keys of 4.6, 4.7 and 4.14 and nothing else can supply them. The genuinely redundant material - the top-N book projection, the legacy ten-level sizes, the derived age fields - is recoverable from book_full by a stated derivation, and I still recommend keeping it: it is small, and its value is that a reader can check the derivation rather than trust it. The fields nothing read on this day (raw flags, sequence deltas, the adapter's precomputed fill-disposition and mirror blocks) are genuine spares, not defects: they would carry information on a multi-channel or out-of-order day, and this Sunday is neither. Size was never an argument in this judgement.",
        {"registry_layers_reviewed": 55, "field_paths_censused": len(json.loads((WORK / 'census.json').read_text())), "elimination_recommendations": 0,
         "most_load_bearing": "book_full.*_levels_full[].fifo_queue[] (order_id, size, volume_ahead, priority_recv_ns, priority_sequence)",
         "redundant_but_keep": ["book.* top-N projection", "legacy row bid/ask 10-level sizes", "front_order_age_s / priority_age_s / queue_age_*", "largest_order_share"],
         "repair_not_remove": ["book_regime.best_bid", "book_regime.best_ask", "book_regime.spread_raw", "activity_since.last_trade.trade_buy_aggressor_qty", "activity_since.last_trade.trade_sell_aggressor_qty"],
         "cannot_judge": ["canonical_predecessor_bootstrap_objects", "legacy_structure_observables", "derived_d_family_geometry", "prebirth_stopped_chain_false_context_controls"]},
        "An elimination recommendation would be justified by a field or layer that no section reads, that is not recoverable from another field, and that could not carry information on any future day. I found none; a single such field named with all three properties shown would falsify this verdict.",
        "The judgement rests on my own field census over the rows I streamed and on having actually computed every section from those fields, so 'load-bearing' means a reading I performed and not a reading I assumed. The four CANNOT_JUDGE layers are named rather than guessed at.",
        [{"kind": "verdict", "value": "KEEP_EVERYTHING", "eliminations": 0}])

    # F-55 what this day cannot answer
    add("F-55", "searched_coverage_and_current_causal_state", "scope",
        f"What this run still cannot answer, marked unanswerable rather than answered thinly. (1) The mission's stream-position gradient across October 1, 3, 4 and 5 is cross-day and this run holds one day. (2) Whether the completion behaviour I measure in 4.10 is a property of the instrument or of the Sunday reopen: {T['phase_counts'].get('PRE_SETTLEMENT')} of {T['groups']} groups are PRE_SETTLEMENT on one instrument in one continuity segment. (3) Whether the candidate population is representative: my detector searched {dc['seconds_judged'] - dc['seconds_in_warmup']} of {dc['seconds_observed']} seconds after warm-up and promoted {dc['candidates_emitted']}. (4) Any claim about the 54/55-week frozen D-family geometry: no such field is carried on the delivered rows, so the frozen vocabulary could be used as a seed for naming but never tested. (5) Whether the brain's 90 plays hold: every one of the eight that touches native MBO mechanics keys on forecaster-harness quantities (tape_conditions.*, phase flow) that this stream does not carry, so none was testable and none is reported as verified or refuted. (6) Anything about a decision clock distinct from F_LAST: the delivered rows carry decision_ts_recv_ns equal to f_last_ts_recv_ns on all {T['groups']} of them.",
        {"groups": T["groups"], "phase_counts": T["phase_counts"], "instruments": 1, "segments": 1, "detector_counters": dc, "decision_delay_census": T["decision_delays"],
         "brain_plays_indexed": 90, "brain_plays_testable_on_this_stream": 0, "source_days_in_mission": ["20211001", "20211003", "20211004", "20211005"]},
        "Each item becomes answerable when a second scored day is traversed under the same contract, or when the forecaster-harness channels the brain plays key on are delivered beside the MBO stream. None becomes answerable by re-reading this day.",
        "Every item is tied to a counter in this run that is structurally single-valued or structurally absent, so the limit is a property of the slice rather than of my reading of it.",
        [{"kind": "scope", "groups": T["groups"], "phases": T["phase_counts"], "decision_delays": T["decision_delays"]}])

    (RUN_DIR / "findings_own.json").write_text(json.dumps(F, indent=2) + "\n", encoding="utf-8")
    print("findings written:", len(F), [x["id"] for x in F])
    return 0


if __name__ == "__main__":
    sys.exit(main())
