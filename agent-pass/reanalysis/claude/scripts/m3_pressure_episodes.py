"""M3: Thin-touch (size-one) quote episodes and pressure signals, per date, from combined-events (87dc338):
b-quote-episodes (ending: recovered / retreated / improved; duration known-by), b-signals + b-delayed-outcomes (1/5/30 s hypothetical quote
observations) and cross-study-condition-outcomes. Decision clock = the episode onset group's known-by time; features are strictly prior."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
summ = []; cells = []; dcells = []
def flowsign(b, s):
    return np.sign(b - s)
for day in DAYS:
    ep = pq.read_table(EVENTS / f"events-{day}/b-quote-episodes.parquet").to_pandas()
    ep["duration_s"] = ep.duration_known_by_ns / 1e9
    ep["attack_flow1"] = np.where(ep.side == "B", flowsign(ep.flow1_sell_lots, ep.flow1_buy_lots), flowsign(ep.flow1_buy_lots, ep.flow1_sell_lots))  # +1: fresh flow hits this side
    ep["attack_flow5"] = np.where(ep.side == "B", flowsign(ep.flow5_sell_lots, ep.flow5_buy_lots), flowsign(ep.flow5_buy_lots, ep.flow5_sell_lots))
    ep["attack_flow20"] = np.where(ep.side == "B", flowsign(ep.flow20_sell_lots, ep.flow20_buy_lots), flowsign(ep.flow20_buy_lots, ep.flow20_sell_lots))
    s = dict(day=day, episodes=len(ep), endings=ep.ending.value_counts().to_dict(), end_not_observed=int(ep.end_not_observed.sum()),
             onset_types=ep.onset_type.value_counts().to_dict(), duration_s=qdesc(ep.duration_s),
             duration_s_by_ending={k: qdesc(g.duration_s) for k, g in ep.groupby("ending")})
    summ.append(s); print(json.dumps({k: v for k, v in s.items() if k != "duration_s_by_ending"}))
    for keys, g in ep.groupby(["side", "onset_type", "attack_flow1", "attack_flow20", "all_gap_trend"], dropna=False):
        vc = g.ending.value_counts()
        cells.append(dict(day=day, side=keys[0], onset_type=keys[1], attack_flow1=keys[2], attack_flow20=keys[3], gap_trend=keys[4], n=len(g),
                          retreated=int(vc.get("retreated", 0)), recovered=int(vc.get("recovered_same_price", 0)), improved=int(vc.get("improved", 0)),
                          dur_p50_s=float(g.duration_s.median()), dur_p90_s=float(g.duration_s.quantile(.9))))
    for col in ["attack_flow1", "attack_flow5", "attack_flow20", "all_gap_trend", "onset_type", "onset_has_print", "prior_three_close_history"]:
        for k, g in ep.groupby(col, dropna=False):
            vc = g.ending.value_counts()
            cells.append(dict(day=day, side="both", onset_type=f"{col}={k}", attack_flow1=None, attack_flow20=None, gap_trend=None, n=len(g),
                              retreated=int(vc.get("retreated", 0)), recovered=int(vc.get("recovered_same_price", 0)), improved=int(vc.get("improved", 0)),
                              dur_p50_s=float(g.duration_s.median()), dur_p90_s=float(g.duration_s.quantile(.9))))
    # delayed outcomes: oriented so that + means the midpoint moved AWAY from the signalled side (bid thin -> price down = +)
    do = pq.read_table(EVENTS / f"events-{day}/b-delayed-outcomes.parquet", columns=["event_id", "event_type", "side", "horizon_s", "disposition", "signed_midpoint_change_twice_raw", "spread_crossing_raw"]).to_pandas()
    sig = pq.read_table(EVENTS / f"events-{day}/b-signals.parquet", columns=["event_id", "flow1_buy_lots", "flow1_sell_lots", "flow20_buy_lots", "flow20_sell_lots", "all_gap_trend", "fresh_group_print_count"]).to_pandas()
    do = do.merge(sig, on="event_id", how="left")
    do["oriented_ticks"] = do.signed_midpoint_change_twice_raw / (2 * TICK_RAW) * np.where(do.side == "B", -1, 1)
    do["attack_flow1"] = np.where(do.side == "B", flowsign(do.flow1_sell_lots, do.flow1_buy_lots), flowsign(do.flow1_buy_lots, do.flow1_sell_lots))
    do["attack_flow20"] = np.where(do.side == "B", flowsign(do.flow20_sell_lots, do.flow20_buy_lots), flowsign(do.flow20_buy_lots, do.flow20_sell_lots))
    for keys, g in do.groupby(["event_type", "side", "horizon_s", "attack_flow1", "attack_flow20"], dropna=False):
        obs = g[g.disposition == "observed"] if "observed" in set(g.disposition) else g[g.oriented_ticks.notna()]
        sc = sign_counts(obs.oriented_ticks)
        dcells.append(dict(day=day, event_type=keys[0], side=keys[1], horizon_s=keys[2], attack_flow1=keys[3], attack_flow20=keys[4], n=len(g), observed=sc["n"],
                           away=sc["up"], flat=sc["flat"], toward=sc["down"], p50_ticks=float(obs.oriented_ticks.median()) if sc["n"] else np.nan,
                           spread_cross_pos=int((obs.spread_crossing_raw > 0).sum()), dispositions=json.dumps(g.disposition.value_counts().to_dict())))
pd.DataFrame(cells).to_csv(OUT / "m3_episode_cells.csv", index=False)
pd.DataFrame(dcells).to_csv(OUT / "m3_delayed_outcome_cells.csv", index=False)
json.dump(summ, open(OUT / "m3_summary.json", "w"), indent=1)
