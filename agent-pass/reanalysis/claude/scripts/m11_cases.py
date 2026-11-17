"""M11: CASES.csv by declared selection rules (presentation only; populations are unchanged):
R1 first chronological SAME, FLIP, NO_PREDECESSOR archived Native candidate per date (same rule as the Codex pinning packet);
R2 per date, the live candidate whose lifecycle ended earliest relative to recognition and the one with the longest remaining life after recognition;
R3 per date, the live candidate with the largest adverse (against birth direction) 300 s print move after recognition and the largest favourable one;
R4 per date, the large midpoint move with the fastest full recovery, the slowest observed full recovery, and one with no full return within 600 s;
R5 per date, one thin-touch episode that retreated and one that recovered among standing_best_shrank onsets with attacking 1 s flow (first chronological of each);
R6 Ccode population: per date, the first exhaustion-clock event confirmed before the 50 s info horizon and the first with remaining runway > 0 at info50."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
rows = []
def add(**k): rows.append(k)
for day in DAYS:
    tag = TAG[day]
    c = pd.read_csv(OUT / f"m1_candidates_{day}.csv", low_memory=False)
    live = c[c.live_recognition == True].copy()
    srcn = f"markets-data@0487d83:{NATIVE.relative_to(EV / 'native')}/{day}-candidate-operands.csv ; markets-data@9e3365f:whole-lifecycles/audit-{day}/whole-lifecycles.parquet ; Markets@24da878:claude-code/dipole-post-recognition-{tag}-rows.jsonl.gz"
    def native_case(r, rule, rel, unexpl):
        add(case_id=f"{day}:{r.candidate_id}:candidate", rule=rule, day=day, population="archived Native candidates (741/833/741/863)", source=srcn,
            parent_id=r.parent_id, component_refs="birth-context path -60s..recognition (paths.csv.gz); life path (life-paths.csv.gz); whole-lifecycle-points",
            observation_clock_ns=int(r.anchor_label_ns), known_by_clock_ns=int(r.lifecycle_start_known_by_ns) if pd.notna(r.lifecycle_start_known_by_ns) else "",
            recognition_clock_ns=int(r.recognition_ns) if pd.notna(r.recognition_ns) else "", outcome_clock_ns=int(r.lifecycle_end_known_by_ns) if pd.notna(r.lifecycle_end_known_by_ns) else "",
            observed_sequence=f"orientation={r.orientation}; polarity={int(r.polarity)}; flow_state_at_emission={r.flow_state}; recognition_lag_s={r.recognition_lag_s:.3f}; nominal_lag_s={r.nominal_lag_s}; lifecycle_span_s={r.lifecycle_span_s:.0f}; life_end_minus_recognition_s={r.life_end_known_by_minus_recog_s:.1f}; ended_before_recognition={bool(r.ended_before_recognition)}; realised_by_recognition_ticks={r.realised_by_recog_ticks}; cc_move_ticks_60/300={r.cc_move_60}/{r.cc_move_300}; print_move_ticks_60/300/600={r.print_move_60s_ticks}/{r.print_move_300s_ticks}/{r.print_move_600s_ticks}",
            relation_to_interpretation=rel, contrary_or_complementary="", unexplained=unexpl)
    for ori in ["SAME", "FLIP", "NO_PREDECESSOR"]:
        g = c[c.orientation == ori].sort_values("anchor_label_ns")
        if len(g): native_case(g.iloc[0], "R1 first chronological " + ori, "navigation case; shows the whole lifecycle relative to the recognition clock", "whether the predecessor relationship (SAME/FLIP) carries decision content is not established on these four days")
    if len(live):
        r = live.sort_values("life_end_known_by_minus_recog_s").iloc[0]; native_case(r, "R2 lifecycle ended earliest before recognition", "supports the claim that roughly half of operational lifecycles are over before the detector reports; recognition arrives after the one-sided window has already been broken", "why the detector selection window admits births whose flow has already reversed is a detector-design question")
        r = live.sort_values("life_end_known_by_minus_recog_s").iloc[-1]; native_case(r, "R2 longest remaining life after recognition", "the long-life tail exists; at recognition the remaining-life median is ~45-50 s with p90 ~190-260 s", "no decision-time feature in the packet separates this tail from the median case (open question)")
        r = live.sort_values("print_move_300s_ticks").iloc[0]; native_case(r, "R3 largest adverse 300 s print move after recognition", "adverse case for any 'ride the dipole direction after recognition' rule", "")
        r = live.sort_values("print_move_300s_ticks").iloc[-1]; native_case(r, "R3 largest favourable 300 s print move after recognition", "favourable case; the symmetric adverse case exists on every date", "")
    lm = pd.read_csv(OUT / f"m2_large_moves_{day}.csv")
    srcl = f"markets-data@87dc338:combined-events/run-42571551209-1/events-{day}/c-large-quote-events.parquet (+c-prior-signal-to-large-move)"
    def lm_case(r, rule, rel, contra):
        add(case_id=f"{day}:{r.event_id}", rule=rule, day=day, population=f"large midpoint moves >=2 ticks ({len(lm)} this date)", source=srcl, parent_id=r.event_id,
            component_refs="prior/move/extreme/half/full recovery clocks; responses at 1/5/20 s; prior signals", observation_clock_ns=int(r.move_receive_ns), known_by_clock_ns=int(r.move_known_by_ns), recognition_clock_ns="",
            outcome_clock_ns="", observed_sequence=f"direction={r.direction}; jump_ticks={r.jump_ticks_oriented}; extreme_first5s_ticks={r.extreme_first5s_ticks_oriented}; print_count={r.print_count}; pre_spread_ticks={r.pre_spread_ticks}; resp_5s/20s_oriented={r.resp_5s_oriented_ticks}/{r.resp_20s_oriented_ticks}; half_recovery_s={r.half_recovery_s}; full_recovery_s={r.full_recovery_s}; full_not_observed_600s={r.full_not_observed}; prior_signals={r.prior_signals}; prior_agree={r.prior_agree}",
            relation_to_interpretation=rel, contrary_or_complementary=contra, unexplained="first return is not event death; which moves return is not separated by prior-signal agreement, size or print count on these dates")
    if len(lm):
        ok = lm[lm.full_recovery_s.notna()]
        if len(ok): lm_case(ok.sort_values("full_recovery_s").iloc[0], "R4 fastest full recovery", "supports 'price change followed by replenishment/return'", "")
        if len(ok): lm_case(ok.sort_values("full_recovery_s").iloc[-1], "R4 slowest observed full recovery within 600 s", "return can take most of the window", "")
        nf = lm[lm.full_not_observed]
        if len(nf): lm_case(nf.iloc[0], "R4 no full return within 600 s", "contrary case for a fade rule: 11/10/15/15 of 46/58/57/64 moves per date did not return", "contrary")
    ep = pq.read_table(EVENTS / f"events-{day}/b-quote-episodes.parquet", columns=["event_id", "side", "onset_type", "onset_clocks", "end_clocks", "ending", "duration_known_by_ns", "flow1_buy_lots", "flow1_sell_lots", "onset_has_print", "prior_three_close_history"]).to_pandas()
    ep["attack1"] = np.where(ep.side == "B", np.sign(ep.flow1_sell_lots - ep.flow1_buy_lots), np.sign(ep.flow1_buy_lots - ep.flow1_sell_lots))
    sel = ep[(ep.onset_type == "standing_best_shrank") & (ep.attack1 > 0)].copy(); sel["onset_ns"] = sel.onset_clocks.apply(lambda c: c["known_by_ns"]); sel = sel.sort_values("onset_ns")
    for ending in ["retreated", "recovered_same_price"]:
        g = sel[sel.ending == ending]
        if len(g):
            r = g.iloc[0]
            add(case_id=f"{day}:{r.event_id}", rule=f"R5 first chronological standing_best_shrank + attacking 1 s flow, ending={ending}", day=day, population=f"thin-touch quote episodes ({len(ep)} this date)",
                source=f"markets-data@87dc338:combined-events/run-42571551209-1/events-{day}/b-quote-episodes.parquet", parent_id=r.event_id, component_refs="onset group; end group; flow1/5/20/60 at onset",
                observation_clock_ns=int(r.onset_clocks["receive_ns"]), known_by_clock_ns=int(r.onset_clocks["known_by_ns"]), recognition_clock_ns="", outcome_clock_ns=int(r.end_clocks["known_by_ns"]) if r.end_clocks is not None else "",
                observed_sequence=f"side={r.side}; onset_type={r.onset_type}; onset_has_print={r.onset_has_print}; prior_three_close_history={r.prior_three_close_history}; flow1 buy/sell={r.flow1_buy_lots}/{r.flow1_sell_lots}; ending={r.ending}; duration_s={r.duration_known_by_ns/1e9:.6f}",
                relation_to_interpretation="cell with retreat share 0.64-0.70 on all four dates (standing best shrank + attacking fresh flow)", contrary_or_complementary="recovered case is the complementary ~1/3", unexplained="episode durations are milliseconds; whether any participant can act inside them is an execution question, not a market one")
    ex = pd.DataFrame(list(jsonl(CCODE / f"exhaustion-clock-{tag}-events.jsonl.gz"))); ex = ex[ex["mode"] == "day"] if "mode" in ex else ex
    for cond, lab in [(ex.confirmed_before_info50 == True, "R6 first exhaustion confirmed before the 50 s info horizon"), (ex.remaining_runway_at_info50_s > 0, "R6 first with runway remaining at the 50 s info horizon")]:
        g = ex[cond].sort_values("t0")
        if len(g):
            r = g.iloc[0]
            add(case_id=f"{day}:ccode_t0={int(r.t0)}", rule=lab, day=day, population=f"Ccode independent detector population ({len(ex)} this date; not the archived Native set)",
                source=f"Markets@24da878:claude-code/exhaustion-clock-{tag}-events.jsonl.gz", parent_id=f"t0_epoch_s={int(r.t0_epoch_s)}", component_refs="onset/confirm/seed_known/info horizon seconds; aftermath by horizon",
                observation_clock_ns=int(r.t0_epoch_s) * 10**9, known_by_clock_ns=int(r.seed_known_s_epoch_s) * 10**9 if pd.notna(r.seed_known_s_epoch_s) else "", recognition_clock_ns=int(r.t0_epoch_s + 50) * 10**9, outcome_clock_ns=int(r.confirm_epoch_s) * 10**9 if pd.notna(r.confirm_epoch_s) else "",
                observed_sequence=f"polarity={r.polarity}; seed_state={r.seed_state}; runway_s={r.runway_s}; confirm_offset_s={r.confirm_offset_s}; confirmed_before_info50={r.confirmed_before_info50}; remaining_runway_at_info50_s={r.remaining_runway_at_info50_s}; archived_recognition_offset_s={r.archived_recognition_offset_s}; move_t0_to_info50={r.move_t0_to_info50}; move_info50_plus60={r.move_info50_plus60}; aftermath300={json.dumps(r.aftermath.get('300')) if isinstance(r.aftermath, dict) else ''}",
                relation_to_interpretation="P (persistent) seeds never confirm before info50; O/S/X seeds mostly do", contrary_or_complementary="", unexplained="seed-state classes are Ccode definitions; their correspondence to the Native SAME/FLIP labels is not joined")
df = pd.DataFrame(rows); df.to_csv(OUT.parent / "CASES.csv", index=False); print(len(df), df.rule.value_counts().to_dict())
