"""M14: dependence checks the brief asks for: spread, activity/volatility, session phase (UTC hour), direction, event overlap; and robustness of the
S2 fade to neighbouring time limits and decision delays where the packet measures them. Per date. Reads M1/M2/M3/M4 outputs and frozen inputs."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
out = {}
def sc(s): s = s.dropna(); return dict(n=int(len(s)), up=int((s > 0).sum()), flat=int((s == 0).sum()), down=int((s < 0).sum()))
for day in DAYS:
    o = {}
    # --- M1 by regime (spread bucket) x activity bucket, hour
    c = pd.read_csv(OUT / f"m1_candidates_{day}.csv", low_memory=False); c = c[c.live_recognition == True]
    pm = pd.read_csv(NATIVE / f"{day}-path-members.csv"); pm = pm[pm.kind == "candidate"][["candidate_id", "regime", "activity_bucket", "activity", "lag_s"]]
    c = c.merge(pm, on="candidate_id", how="left"); c["hour"] = pd.to_datetime(c.recognition_ns, unit="ns").dt.hour
    o["m1_by_regime"] = {str(k): dict(n=len(g), ended_before=int(g.ended_before_recognition.sum()), rem_p50=float(g.life_end_known_by_minus_recog_s[g.life_end_known_by_minus_recog_s > 0].median()) if (g.life_end_known_by_minus_recog_s > 0).any() else None, cc300=sc(g.cc_move_300), pr300=sc(g.print_move_300s_ticks)) for k, g in c.groupby("regime")}
    o["m1_by_activity_bucket"] = {str(k): dict(n=len(g), ended_before=int(g.ended_before_recognition.sum()), cc300=sc(g.cc_move_300), pr300=sc(g.print_move_300s_ticks)) for k, g in c.groupby("activity_bucket")}
    o["m1_by_hour"] = {str(k): dict(n=len(g), ended_before=int(g.ended_before_recognition.sum()), cc300=sc(g.cc_move_300)) for k, g in c.groupby("hour")}
    o["m1_by_polarity"] = {str(k): dict(n=len(g), ended_before=int(g.ended_before_recognition.sum()), cc300=sc(g.cc_move_300), pr300=sc(g.print_move_300s_ticks)) for k, g in c.groupby("polarity")}
    # event overlap: another candidate born within 60 s before
    b = np.sort(c.anchor_label_ns.values); c["prev_gap_s"] = [(t - b[b < t].max()) / 1e9 if (b < t).any() else np.nan for t in c.anchor_label_ns.values]
    o["m1_by_prev_birth_gap"] = {k: dict(n=len(g), ended_before=int(g.ended_before_recognition.sum()), cc300=sc(g.cc_move_300)) for k, g in c.groupby(pd.cut(c.prev_gap_s, [0, 60, 120, 300, 1e9], labels=["<=60s", "60-120s", "120-300s", ">300s"]), observed=True)}
    # --- M2 large moves: spread, hour, direction, time-limit and delay robustness
    lm = pd.read_csv(OUT / f"m2_large_moves_{day}.csv"); lm["hour"] = pd.to_datetime(lm.move_receive_ns, unit="ns").dt.hour
    def ret(g, T=600): return dict(n=len(g), returned=int((g.full_recovery_s <= T).sum()), half=int((g.half_recovery_s <= T).sum()))
    o["m2_by_pre_spread"] = {str(k): ret(g) for k, g in lm.groupby(lm.pre_spread_ticks.clip(upper=3))}
    o["m2_by_hour_block"] = {k: ret(g) for k, g in lm.groupby(pd.cut(lm.hour, [-1, 5, 11, 14, 17, 23], labels=["00-05", "06-11", "12-14", "15-17", "18-23"]), observed=True)}
    o["m2_by_direction"] = {str(k): ret(g) for k, g in lm.groupby("direction")}
    o["m2_time_limit_robustness"] = {f"T={T}": ret(lm, T) for T in [60, 120, 300, 600]}
    # delay robustness: entering at +20 s instead of +5 s; proxy = returns that occur after 20 s (a fill at +20 s could still capture them) and moves not already returned by 20 s
    o["m2_delay_robustness"] = {f"enter_at_{d}s": dict(open_at_entry=int((lm.full_recovery_s.isna() | (lm.full_recovery_s > d)).sum()), returned_after_entry=int((lm.full_recovery_s > d).sum()), already_returned_before_entry=int((lm.full_recovery_s <= d).sum())) for d in [1, 5, 20, 60]}
    o["m2_by_resp5"] = {k: ret(g) for k, g in lm.groupby(np.sign(lm.resp_5s_oriented_ticks).map({1: "continued_5s", 0: "flat_5s", -1: "reversed_5s"}))}
    o["m2_by_extreme"] = {str(k): ret(g) for k, g in lm.groupby(lm.extreme_first5s_ticks_oriented.clip(upper=6))}
    # --- M3 episodes by hour and spread, flow5/flow20 variants of the retreat cell
    ep = pq.read_table(EVENTS / f"events-{day}/b-quote-episodes.parquet", columns=["side", "onset_type", "onset_clocks", "ending", "flow1_buy_lots", "flow1_sell_lots", "flow5_buy_lots", "flow5_sell_lots", "flow20_buy_lots", "flow20_sell_lots"]).to_pandas()
    ep["hour"] = pd.to_datetime(ep.onset_clocks.apply(lambda x: x["known_by_ns"]), unit="ns").dt.hour
    ep["spread_ticks"] = ep.onset_clocks.apply(lambda x: (x["ask_raw"] - x["bid_raw"]) / TICK_RAW)
    for w in ["1", "5", "20"]:
        ep[f"attack{w}"] = np.where(ep.side == "B", np.sign(ep[f"flow{w}_sell_lots"] - ep[f"flow{w}_buy_lots"]), np.sign(ep[f"flow{w}_buy_lots"] - ep[f"flow{w}_sell_lots"]))
    rs = lambda g: dict(n=len(g), retreated=int((g.ending == "retreated").sum()))
    o["m3_retreat_by_hour_block"] = {k: rs(g) for k, g in ep.groupby(pd.cut(ep.hour, [-1, 5, 11, 14, 17, 23], labels=["00-05", "06-11", "12-14", "15-17", "18-23"]), observed=True)}
    o["m3_retreat_by_spread"] = {str(k): rs(g) for k, g in ep.groupby(ep.spread_ticks.clip(upper=3))}
    o["m3_shrank_attack_variants"] = {f"flow{w}": {str(k): rs(g) for k, g in ep[ep.onset_type == "standing_best_shrank"].groupby(f"attack{w}")} for w in ["1", "5", "20"]}
    o["m3_newbest_attack_variants"] = {f"flow{w}": {str(k): rs(g) for k, g in ep[ep.onset_type == "new_best"].groupby(f"attack{w}")} for w in ["1", "5", "20"]}
    # --- M4 families by hour and spread
    fm = pd.read_csv(SUITE / f"tables/{day}/t1_family_master.csv", low_memory=False)
    fm["flow5"] = np.sign(fm["root.activity.5.trade_buy_aggressor_qty"] - fm["root.activity.5.trade_sell_aggressor_qty"]); fm["tk5"] = fm.chg_5s / 0.001; fm["tk60"] = fm.chg_60s / 0.001
    cont = lambda g: dict(n=int((g.flow5 != 0).sum()), cont5=int(((np.sign(g.tk5) * g.flow5) > 0).sum()), rev5=int(((np.sign(g.tk5) * g.flow5) < 0).sum()), cont60=int(((np.sign(g.tk60) * g.flow5) > 0).sum()), rev60=int(((np.sign(g.tk60) * g.flow5) < 0).sum()))
    o["m4_flow5_cont_by_hour_block"] = {k: cont(g) for k, g in fm.groupby(pd.cut(fm.utc_hour, [-1, 5, 11, 14, 17, 23], labels=["00-05", "06-11", "12-14", "15-17", "18-23"]), observed=True)} if "utc_hour" in fm else None
    o["m4_flow5_cont_by_spread"] = {str(k): cont(g) for k, g in fm.groupby(fm.spread_ticks.clip(upper=3))} if "spread_ticks" in fm else None
    o["m4_outcome_by_hour_block"] = {k: sc(g.tk60) for k, g in fm.groupby(pd.cut(fm.utc_hour, [-1, 5, 11, 14, 17, 23], labels=["00-05", "06-11", "12-14", "15-17", "18-23"]), observed=True)} if "utc_hour" in fm else None
    out[day] = o
    print(day, json.dumps({k: o[k] for k in ["m2_time_limit_robustness", "m2_delay_robustness", "m2_by_pre_spread", "m3_shrank_attack_variants"]}))
json.dump(out, open(OUT / "m14_dependence.json", "w"), indent=1, default=str)
