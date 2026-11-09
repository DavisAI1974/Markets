"""M2: Large quote moves (>= 2 ticks midpoint jump) and recovery, per date, from combined-events c-large-quote-events (87dc338)
and c-prior-signal-to-large-move. Endpoint: first half/full return to the pre-move quote within 600 s (source definition); first return is not event death."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
allrows = []; summ = []
for day in DAYS:
    t = pq.read_table(EVENTS / f"events-{day}/c-large-quote-events.parquet").to_pandas()
    pri = pq.read_table(EVENTS / f"events-{day}/c-prior-signal-to-large-move.parquet").to_pandas()
    agg = pri.groupby("later_event_id").agg(prior_signals=("earlier_event_id", "count"), prior_agree=("earlier_signal_direction_agrees", "sum"),
                                            prior_lag_min_s=("lag_known_by_ns", lambda s: s.min() / 1e9)).reset_index().rename(columns={"later_event_id": "event_id"})
    t = t.merge(agg, on="event_id", how="left")
    recs = []
    for _, r in t.iterrows():
        resp = {int(x["horizon_s"]): x for x in (list(r.responses) if r.responses is not None else [])}
        pre_mid2 = r.prior_clocks["bid_raw"] + r.prior_clocks["ask_raw"]; mv_mid2 = r.move_clocks["bid_raw"] + r.move_clocks["ask_raw"]
        d = dict(day=day, event_id=r.event_id, direction=int(r.direction), move_half_ticks=int(r.move_half_ticks), print_count=int(r.print_count),
                 first_disjoint_20s=bool(r.first_disjoint_20s), move_known_by_ns=int(r.move_clocks["known_by_ns"]), move_receive_ns=int(r.move_clocks["receive_ns"]),
                 pre_spread_ticks=(r.prior_clocks["ask_raw"] - r.prior_clocks["bid_raw"]) / TICK_RAW, move_spread_ticks=(r.move_clocks["ask_raw"] - r.move_clocks["bid_raw"]) / TICK_RAW,
                 jump_ticks_oriented=(mv_mid2 - pre_mid2) / (2 * TICK_RAW) * r.direction,
                 extreme_first5s_ticks_oriented=(r.extreme_midpoint_twice_raw - pre_mid2) / (2 * TICK_RAW) * r.direction if pd.notna(r.extreme_midpoint_twice_raw) else np.nan,
                 half_recovery_s=r.half_recovery_elapsed_ns / 1e9 if pd.notna(r.half_recovery_elapsed_ns) and r.half_recovery_elapsed_ns >= 0 else np.nan,
                 full_recovery_s=r.full_recovery_elapsed_ns / 1e9 if pd.notna(r.full_recovery_elapsed_ns) and r.full_recovery_elapsed_ns >= 0 else np.nan,
                 half_not_observed=bool(r.half_not_observed), full_not_observed=bool(r.full_not_observed), recovery_window_complete=bool(r.recovery_window_complete),
                 prior_signals=int(r.prior_signals) if pd.notna(r.prior_signals) else 0, prior_agree=int(r.prior_agree) if pd.notna(r.prior_agree) else 0,
                 prior_lag_min_s=r.prior_lag_min_s)
        for h in [1, 5, 20]:
            x = resp.get(h)
            d[f"resp_{h}s_oriented_ticks"] = (x["signed_change_twice_raw"] / (2 * TICK_RAW)) * r.direction if x and x["available"] else np.nan
            d[f"resp_{h}s_full_retrace"] = bool(x["full_retrace"]) if x and x["available"] else None
        recs.append(d)
    df = pd.DataFrame(recs); df.to_csv(OUT / f"m2_large_moves_{day}.csv", index=False); allrows.append(df)
    s = dict(day=day, large_moves=len(df), up=int((df.direction > 0).sum()), down=int((df.direction < 0).sum()),
             jump_ticks=qdesc(df.jump_ticks_oriented), extreme5s_ticks=qdesc(df.extreme_first5s_ticks_oriented),
             full_recovered=int(df.full_recovery_s.notna().sum()), half_recovered=int(df.half_recovery_s.notna().sum()),
             full_not_observed_within_600s=int(df.full_not_observed.sum()), window_incomplete=int((~df.recovery_window_complete).sum()),
             full_recovery_s=qdesc(df.full_recovery_s), half_recovery_s=qdesc(df.half_recovery_s),
             resp5_continuation=int((df.resp_5s_oriented_ticks > 0).sum()), resp5_flat=int((df.resp_5s_oriented_ticks == 0).sum()), resp5_reversal=int((df.resp_5s_oriented_ticks < 0).sum()),
             resp20_continuation=int((df.resp_20s_oriented_ticks > 0).sum()), resp20_flat=int((df.resp_20s_oriented_ticks == 0).sum()), resp20_reversal=int((df.resp_20s_oriented_ticks < 0).sum()),
             with_prior_signal=int((df.prior_signals > 0).sum()),
             full_rec_given_prior_agree_majority=int(df[(df.prior_signals > 0) & (df.prior_agree * 2 > df.prior_signals)].full_recovery_s.notna().sum()),
             n_prior_agree_majority=int(((df.prior_signals > 0) & (df.prior_agree * 2 > df.prior_signals)).sum()),
             full_rec_given_prior_disagree_majority=int(df[(df.prior_signals > 0) & (df.prior_agree * 2 <= df.prior_signals)].full_recovery_s.notna().sum()),
             n_prior_disagree_majority=int(((df.prior_signals > 0) & (df.prior_agree * 2 <= df.prior_signals)).sum()),
             full_rec_by_size={str(k): [int(g.full_recovery_s.notna().sum()), len(g)] for k, g in df.groupby(df.move_half_ticks.clip(upper=8))},
             full_rec_by_printcount={str(k): [int(g.full_recovery_s.notna().sum()), len(g)] for k, g in df.groupby(pd.cut(df.print_count, [-1, 0, 2, 5, 10**6], labels=["0", "1-2", "3-5", "6+"]))},
             full_rec_by_first_disjoint={str(k): [int(g.full_recovery_s.notna().sum()), len(g)] for k, g in df.groupby("first_disjoint_20s")})
    summ.append(s); print(json.dumps(s))
json.dump(summ, open(OUT / "m2_summary.json", "w"), indent=1)
pd.concat(allrows).to_csv(OUT / "m2_large_moves_all.csv", index=False)
