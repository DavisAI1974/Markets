"""M1: Native dipole candidates at the actual recognition clock: what was known, what remained.
Inputs (frozen): whole-lifecycles.parquet (9e3365f), native candidate-operands / lag-measurements / life-measurements /
paths.csv.gz (0487d83), Ccode dipole-post-recognition rows (Markets 24da878), combined-events a-trades (87dc338).
Every row is one candidate; counts are per date; nothing pooled across dates."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *

rows = []
cells_out = []
for day in DAYS:
    tag = TAG[day]
    wl = pq.read_table(WHOLE / f"audit-{day}/whole-lifecycles.parquet").to_pandas()
    cand = wl[wl.kind == "candidate"].copy()
    ops = pd.read_csv(NATIVE / f"{day}-candidate-operands.csv")
    lag = pd.read_csv(NATIVE / f"{day}-lag-measurements.csv")[["candidate_id", "nominal_lag_s", "recognition_lag_s", "dispatch_lag_s", "competing_peaks", "winning_offset_s"]]
    life = pd.read_csv(NATIVE / f"{day}-life-measurements.csv")
    life = life[life.kind == "candidate"][["candidate_id", "anchor_ratio", "life_seconds", "disposition", "first_undefined_after_anchor_s", "magnitude_increases", "magnitude_decreases", "max_net_change"]]
    post = pd.DataFrame(list(jsonl(CCODE / f"dipole-post-recognition-{tag}-rows.jsonl.gz")))
    mt = pd.DataFrame(post["move_ticks_after_recognition"].tolist()).add_prefix("cc_move_")
    post = pd.concat([post.drop(columns=["move_ticks_after_recognition"]), mt], axis=1)
    post = post.rename(columns={"realised_by_recognition_ticks_in_birth_direction": "realised_by_recog_ticks"})
    df = cand.merge(ops[["candidate_id", "flow_state", "quote_move", "baseline", "prominence", "observations_behind_threshold"]], on="candidate_id", how="left")
    df = df.merge(lag, on="candidate_id", how="left").merge(life, on="candidate_id", how="left")
    df = df.merge(post[["candidate_id", "prebirth_depth_state", "quote_move_by_recognition", "realised_by_recog_ticks", "recognition_touch_relation", "birth_classified_lots", "last_window_classified_lots"] + list(mt.columns)], on="candidate_id", how="left")
    # price path from prints (receive clock), oriented by polarity, in ticks
    tr = pq.read_table(EVENTS / f"events-{day}/a-trades.parquet", columns=["receive_ns", "price_raw"]).to_pandas().sort_values("receive_ns")
    rn = tr.receive_ns.values; pr = tr.price_raw.values
    def last_print(t):
        i = np.searchsorted(rn, t, side="right") - 1
        return pr[i] if i >= 0 else np.nan
    rec = df.recognition_ns.values.astype("float")
    df["print_at_recog"] = [last_print(int(t)) if np.isfinite(t) else np.nan for t in rec]
    for h in [5, 20, 60, 300, 600]:
        df[f"print_move_{h}s_ticks"] = [((last_print(int(t) + h * 10**9) - p) / TICK_RAW) * pol if np.isfinite(t) and np.isfinite(p) else np.nan
                                        for t, p, pol in zip(rec, df.print_at_recog.values, df.polarity.values)]
    # remaining life at recognition (known-by clocks): the operational endpoint is the third opposite second (research convention)
    df["life_end_known_by_minus_recog_s"] = (df.lifecycle_end_known_by_ns - df.recognition_ns) / 1e9
    df["ended_before_recognition"] = df.life_end_known_by_minus_recog_s <= 0
    df["lifecycle_span_s"] = (df.lifecycle_end_label_ns - df.anchor_label_ns) / 1e9
    df["day"] = day
    df.to_csv(OUT / f"m1_candidates_{day}.csv", index=False)
    live = df[df.live_recognition == True]
    r = dict(day=day, candidates=len(df), live_recognition=int(df.live_recognition.fillna(False).sum()),
             finalization_only=int((df.live_recognition != True).sum()),
             endpoint_opposite_hold3=int((df.endpoint_definition == "opposite_hold3").sum()),
             endpoint_censored=int((df.endpoint_definition != "opposite_hold3").sum()),
             ended_before_recognition=int(live.ended_before_recognition.sum()),
             share_ended_before_recognition=round(float(live.ended_before_recognition.mean()), 3),
             life_span_s=qdesc(df.lifecycle_span_s), remaining_after_recog_s=qdesc(live.life_end_known_by_minus_recog_s[live.life_end_known_by_minus_recog_s > 0]),
             recognition_lag_s=qdesc(live.recognition_lag_s), realised_by_recog_ticks=sign_counts(live.realised_by_recog_ticks),
             print_move_60s=sign_counts(live.print_move_60s_ticks), cc_move_60=sign_counts(live.cc_move_60), cc_move_300=sign_counts(live.cc_move_300),
             print_move_300s=sign_counts(live.print_move_300s_ticks), print_move_600s=sign_counts(live.print_move_600s_ticks),
             agree_sign_cc_vs_print_60=int(((np.sign(live.cc_move_60) == np.sign(live.print_move_60s_ticks)) & live.cc_move_60.notna() & live.print_move_60s_ticks.notna()).sum()))
    rows.append(r)
    # decision-time cells: orientation x quote_move_by_recognition x flow_state x ended_before_recognition
    for keys, g in live.groupby(["orientation", "quote_move_by_recognition", "flow_state", "ended_before_recognition"], dropna=False):
        rec_ = dict(day=day, orientation=keys[0], quote_move_by_recognition=keys[1], flow_state=keys[2], ended_before_recognition=keys[3], n=len(g))
        for h in [5, 20, 60, 300]:
            sc = sign_counts(g[f"cc_move_{h}"]); rec_.update({f"cc{h}_up": sc["up"], f"cc{h}_flat": sc["flat"], f"cc{h}_down": sc["down"]})
            sp = sign_counts(g[f"print_move_{h}s_ticks"]); rec_.update({f"pr{h}_up": sp["up"], f"pr{h}_flat": sp["flat"], f"pr{h}_down": sp["down"]})
        rec_["remaining_life_p50_s"] = float(g.life_end_known_by_minus_recog_s.clip(lower=0).median())
        cells_out.append(rec_)
    # simple 2-way cells too
    for col in ["orientation", "quote_move_by_recognition", "flow_state", "prebirth_depth_state", "recognition_touch_relation", "ended_before_recognition"]:
        for k, g in live.groupby(col, dropna=False):
            rec_ = dict(day=day, cell_var=col, cell=str(k), n=len(g))
            for h in [5, 20, 60, 300]:
                sc = sign_counts(g[f"cc_move_{h}"]); rec_.update({f"cc{h}_up": sc["up"], f"cc{h}_flat": sc["flat"], f"cc{h}_down": sc["down"]})
            for h in [60, 300, 600]:
                sp = sign_counts(g[f"print_move_{h}s_ticks"]); rec_.update({f"pr{h}_up": sp["up"], f"pr{h}_flat": sp["flat"], f"pr{h}_down": sp["down"]})
            rec_["remaining_life_p50_s"] = float(g.life_end_known_by_minus_recog_s.clip(lower=0).median())
            rec_["share_ended_before_recog"] = round(float(g.ended_before_recognition.mean()), 3)
            cells_out.append(rec_)
pd.DataFrame(cells_out).to_csv(OUT / "m1_decision_cells.csv", index=False)
json.dump(rows, open(OUT / "m1_summary.json", "w"), indent=1)
for r in rows:
    print(json.dumps(r))
