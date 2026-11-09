"""M18: cross-layer joins on the combined-events links (87dc338): each pressure signal (thin touch etc.) carries the structural family at that group,
the latest recognized dipole (age, direction), fresh wire flow vs the signal, displayed touch vs the signal and the prior print-gap trend.
Question: does the state of the other layers change what the thin level does? Episode ending joined on event_id. Per date."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
out = {}; cells = []
for day in DAYS:
    L = pq.read_table(EVENTS / f"events-{day}/cross-study-event-links.parquet", columns=["event_id", "event_type", "side", "latest_recognized_dipole_id", "dipole_recognition_age_ns", "dipole_selection", "fresh_wire_flow_vs_signal", "displayed_touch_vs_signal", "prior_print_gap_trend", "fresh_buy_lots", "fresh_sell_lots", "rolling20_buy_lots", "rolling20_sell_lots", "current_group_no_print", "structural_family_at_group", "observed_family_occurrence_number"]).to_pandas()
    E = pq.read_table(EVENTS / f"events-{day}/b-quote-episodes.parquet", columns=["event_id", "ending", "onset_type"]).to_pandas()
    dc = pq.read_table(EVENTS / f"events-{day}/a-dipole-clocks.parquet", columns=["candidate_id", "polarity", "lifetime_end_label_ns", "recognition_ns"]).to_pandas()
    S = L[L.event_type == "size_one"].merge(E, on="event_id", how="inner")
    S = S.merge(dc.rename(columns={"candidate_id": "latest_recognized_dipole_id", "polarity": "dip_pol"}), on="latest_recognized_dipole_id", how="left")
    S["dip_age_s"] = S.dipole_recognition_age_ns / 1e9
    # dipole direction relative to the thin side: a +1 dipole (buying) attacks a thin ask (side A)
    S["dip_attacks_side"] = np.where(S.dip_pol.isna(), "none", np.where(((S.dip_pol == 1) & (S.side == "A")) | ((S.dip_pol == -1) & (S.side == "B")), "attacks", "defends"))
    S["dip_state"] = np.where(S.dip_pol.isna(), "no_dipole", np.where(S.dip_age_s <= 60, "recognized<=60s", np.where(S.dip_age_s <= 300, "60-300s", ">300s")))
    S["dip_alive"] = np.where(S.dip_pol.isna(), "none", np.where(S.lifetime_end_label_ns > (S.recognition_ns + S.dipole_recognition_age_ns), "alive", "ended"))
    S["family_occ"] = pd.cut(S.observed_family_occurrence_number.fillna(0), [-1, 0, 1, 5, 1e9], labels=["none", "first", "2-5", ">5"])
    rs = lambda g: dict(n=len(g), retreated=int((g.ending == "retreated").sum()), share=round(float((g.ending == "retreated").mean()), 3) if len(g) else None)
    o = dict(day=day, size_one_signals=len(S),
             by_dipole_state=dict({k: rs(g) for k, g in S.groupby("dip_state")}),
             by_dipole_direction=dict({k: rs(g) for k, g in S.groupby("dip_attacks_side")}),
             by_dipole_direction_recent=dict({k: rs(g) for k, g in S[S.dip_state == "recognized<=60s"].groupby("dip_attacks_side")}),
             by_dipole_alive_direction=dict({f"{a}|{b}": rs(g) for (a, b), g in S.groupby(["dip_alive", "dip_attacks_side"])}),
             by_fresh_flow_label=dict({k: rs(g) for k, g in S.groupby("fresh_wire_flow_vs_signal")}),
             by_touch_label=dict({k: rs(g) for k, g in S.groupby("displayed_touch_vs_signal")}),
             by_gap_trend=dict({k: rs(g) for k, g in S.groupby("prior_print_gap_trend")}),
             by_family_occurrence=dict({str(k): rs(g) for k, g in S.groupby("family_occ", observed=True)}),
             three_way_flow_touch_dipole=dict({f"{a}|{b}|{c}": rs(g) for (a, b, c), g in S.groupby(["fresh_wire_flow_vs_signal", "displayed_touch_vs_signal", "dip_attacks_side"]) if len(g) >= 100}),
             three_way_onset_flow_dipole=dict({f"{a}|{b}|{c}": rs(g) for (a, b, c), g in S.groupby(["onset_type", "fresh_wire_flow_vs_signal", "dip_attacks_side"]) if len(g) >= 100}))
    out[day] = o
    print(day, "dipole state:", o["by_dipole_state"]); print("   dipole direction:", o["by_dipole_direction"], "| recent:", o["by_dipole_direction_recent"]); print("   flow label:", o["by_fresh_flow_label"]); print("   touch label:", o["by_touch_label"]); print("   family occ:", o["by_family_occurrence"])
    print("   onset x flow x dipole:", {k: (v["n"], v["share"]) for k, v in o["three_way_onset_flow_dipole"].items()})
json.dump(out, open(OUT / "m18_cross_layer_joins.json", "w"), indent=1)
