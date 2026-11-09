"""M20: the environment BEFORE and AFTER each trade candidate, one row per trade, using today's layers.
(A) Large-move fades (S2, 46/58/57/64): before = native 20 s window state at the move (whole/native-flow-source-clocks), net native flow in the prior
60 s oriented to the move, Native dipole born in the move direction in the prior 60 s, prints in the prior 60 s, pre-move spread, thin-touch episodes
open at the move, hour; after = net native flow in the next 20 and 60 s oriented to the move, a Native birth in the move direction in the next 120 s,
prints in the next 60 s, episodes started in the next 60 s; outcome = full return within 600 s and its time. Per date conditionals.
(B) Dipole rides (S7): before = M17 layer score at k=+5; after = with/against lots and prints in the 60 s after the exhaustion exit (x13)."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
LIFE = EV / "final_markets" / FR / "claude-pass-3day/tables/dipole"
rows = []; summ = {}
for day in DAYS:
    lm = pd.read_csv(OUT / f"m2_large_moves_{day}.csv")
    nf = pq.read_table(WHOLE / f"audit-{day}/native-flow-source-clocks.parquet", columns=["second", "native_buy", "native_sell", "native_ratio", "native_total", "completed_second_known_by_ns"]).to_pandas().set_index("second")
    tr = pq.read_table(EVENTS / f"events-{day}/a-trades.parquet", columns=["receive_ns"]).to_pandas().receive_ns.sort_values().values
    dc = pq.read_table(EVENTS / f"events-{day}/a-dipole-clocks.parquet", columns=["birth_label_ns", "polarity", "recognition_ns", "live_recognition"]).to_pandas()
    ep = pq.read_table(EVENTS / f"events-{day}/b-quote-episodes.parquet", columns=["onset_clocks", "end_clocks", "side"]).to_pandas()
    ep_on = ep.onset_clocks.apply(lambda c: c["known_by_ns"]).values.astype("int64"); ep_end = ep.end_clocks.apply(lambda c: c["known_by_ns"] if c is not None else np.iinfo("int64").max).values.astype("int64")
    def flow(t0s, t1s, d):  # seconds [t0s, t1s) ; oriented net lots to direction d
        s = nf.loc[(nf.index >= t0s) & (nf.index < t1s)]
        return float((s.native_buy.sum() - s.native_sell.sum()) * d), float(s.native_total.sum() if "native_total" in s else (s.native_buy + s.native_sell).sum())
    for _, r in lm.iterrows():
        t = int(r.move_known_by_ns); ts = t // 10**9; d = int(r.direction)
        pre_net, pre_tot = flow(ts - 60, ts, d); post20_net, post20_tot = flow(ts + 1, ts + 21, d); post60_net, post60_tot = flow(ts + 1, ts + 61, d)
        ratio_at = nf.native_ratio.get(ts - 1, np.nan); ratio_or = ratio_at * d if pd.notna(ratio_at) else np.nan
        births = dc[dc.live_recognition == True]
        pre_birth_with = int(((births.birth_label_ns >= t - 60 * 10**9) & (births.birth_label_ns <= t) & (births.polarity == d)).sum()); pre_birth_against = int(((births.birth_label_ns >= t - 60 * 10**9) & (births.birth_label_ns <= t) & (births.polarity == -d)).sum())
        post_birth_with = int(((births.birth_label_ns > t) & (births.birth_label_ns <= t + 120 * 10**9) & (births.polarity == d)).sum()); post_birth_against = int(((births.birth_label_ns > t) & (births.birth_label_ns <= t + 120 * 10**9) & (births.polarity == -d)).sum())
        prints_pre = int(((tr >= t - 60 * 10**9) & (tr < t)).sum()); prints_post = int(((tr > t) & (tr <= t + 60 * 10**9)).sum())
        ep_open = int(((ep_on <= t) & (ep_end > t)).sum()); ep_new = int(((ep_on > t) & (ep_on <= t + 60 * 10**9)).sum())
        rows.append(dict(day=day, event_id=r.event_id, direction=d, returned=pd.notna(r.full_recovery_s), full_recovery_s=r.full_recovery_s, extreme_ticks=r.extreme_first5s_ticks_oriented, pre_spread=r.pre_spread_ticks, hour=pd.Timestamp(t, unit="ns").hour,
                         before_ratio20_oriented=ratio_or, before_net_flow60_oriented=pre_net, before_total_flow60=pre_tot, before_birth_with=pre_birth_with, before_birth_against=pre_birth_against, before_prints60=prints_pre, before_open_thin_episodes=ep_open,
                         after_net_flow20_oriented=post20_net, after_net_flow60_oriented=post60_net, after_total_flow60=post60_tot, after_birth_with120=post_birth_with, after_birth_against120=post_birth_against, after_prints60=prints_post, after_new_thin_episodes60=ep_new))
E = pd.DataFrame(rows); E.to_csv(OUT / "m20_large_move_environment.csv", index=False)
def cell(g): return dict(n=int(len(g)), returned=int(g.returned.sum()), not_returned=int((~g.returned).sum()), ret_p50=float(g.full_recovery_s.median()) if g.returned.any() else None)
for day, g in E.groupby("day"):
    summ[day] = dict(n=len(g),
        before_ratio20=dict(with_move=cell(g[g.before_ratio20_oriented > 0]), against_move=cell(g[g.before_ratio20_oriented < 0]), undefined=cell(g[g.before_ratio20_oriented.isna()])),
        before_net_flow60=dict(with_move=cell(g[g.before_net_flow60_oriented > 0]), against=cell(g[g.before_net_flow60_oriented < 0]), zero=cell(g[g.before_net_flow60_oriented == 0])),
        before_birth=dict(with_move=cell(g[g.before_birth_with > 0]), against=cell(g[(g.before_birth_against > 0) & (g.before_birth_with == 0)]), none=cell(g[(g.before_birth_with == 0) & (g.before_birth_against == 0)])),
        before_prints60=dict(low=cell(g[g.before_prints60 <= g.before_prints60.median()]), high=cell(g[g.before_prints60 > g.before_prints60.median()]), median=float(g.before_prints60.median())),
        before_open_thin_episodes=dict(none=cell(g[g.before_open_thin_episodes == 0]), some=cell(g[g.before_open_thin_episodes > 0])),
        after_net_flow20=dict(with_move=cell(g[g.after_net_flow20_oriented > 0]), against=cell(g[g.after_net_flow20_oriented < 0]), zero=cell(g[g.after_net_flow20_oriented == 0])),
        after_net_flow60=dict(with_move=cell(g[g.after_net_flow60_oriented > 0]), against=cell(g[g.after_net_flow60_oriented < 0]), zero=cell(g[g.after_net_flow60_oriented == 0])),
        after_birth120=dict(with_move=cell(g[g.after_birth_with120 > 0]), against_only=cell(g[(g.after_birth_against120 > 0) & (g.after_birth_with120 == 0)]), none=cell(g[(g.after_birth_with120 == 0) & (g.after_birth_against120 == 0)])),
        after_prints60=dict(low=cell(g[g.after_prints60 <= g.after_prints60.median()]), high=cell(g[g.after_prints60 > g.after_prints60.median()]), median=float(g.after_prints60.median())))
    print(day, "before ratio20:", summ[day]["before_ratio20"]); print("   before net flow60:", summ[day]["before_net_flow60"]); print("   before birth:", summ[day]["before_birth"]); print("   after flow20:", summ[day]["after_net_flow20"], "| after flow60:", summ[day]["after_net_flow60"]); print("   after birth120:", summ[day]["after_birth120"]); print("   prints pre/post:", summ[day]["before_prints60"], summ[day]["after_prints60"])
# (B) dipole rides: environment after the exhaustion exit from x13 arrays
B = {}
for day in DAYS:
    z = np.load(LIFE / f"{day}/instances/x13_life_paths.npz", allow_pickle=True); ks = z["ks"]; i0 = int(np.where(ks == 0)[0][0])
    lc = pd.read_csv(OUT / "m16_lookahead_lifecycle_candidates.csv"); lc = lc[lc.day == int(day)].set_index("row").reindex(z["row"])
    F = pd.read_csv(OUT / "m17_features.csv.gz"); F = F[F.day == int(day)].set_index("row").reindex(z["row"])
    ke = lc.k_exhaustion.values; n = len(ke)
    def win(arr, k, a, b):
        o = np.full(n, np.nan)
        for i, kk in enumerate(k):
            if np.isfinite(kk) and i0 + int(kk) + b < arr.shape[1]: o[i] = np.nansum(arr[i, i0 + int(kk) + a:i0 + int(kk) + b + 1])
        return o
    w60 = win(z["with_lots"], ke, 1, 60); a60 = win(z["against_lots"], ke, 1, 60); t60 = win(z["n_trades"], ke, 1, 60); w_pre = win(z["with_lots"], np.zeros(n), -20, 5); a_pre = win(z["against_lots"], np.zeros(n), -20, 5)
    ride = (lc.m_exh - lc.m5).values; post = (pd.read_json(OUT / "m16_lookahead_lifecycle.json")[day]["after_exhaustion"] if False else None)
    def sc(x): x = x[np.isfinite(x)]; return dict(n=int(x.size), up=int((x > 0).sum()), flat=int((x == 0).sum()), down=int((x < 0).sum()))
    B[day] = dict(n=n, after_exhaustion_60s_against_share_of_lots=dict(p25=float(np.nanpercentile(a60 / np.where(w60 + a60 > 0, w60 + a60, np.nan), 25)), p50=float(np.nanpercentile(a60 / np.where(w60 + a60 > 0, w60 + a60, np.nan), 50)), p75=float(np.nanpercentile(a60 / np.where(w60 + a60 > 0, w60 + a60, np.nan), 75))),
                  after_exhaustion_60s_trades_vs_prebirth_26s=dict(after_p50=float(np.nanmedian(t60)), before_p50=float(np.nanmedian(win(z["n_trades"], np.zeros(n), -20, 5)))),
                  ride_by_after_flow=dict(after_mostly_against=sc(ride[(a60 > w60)]), after_mostly_with=sc(ride[(a60 < w60)])),
                  ride_by_prebirth_total_lots=dict(low=sc(ride[(w_pre + a_pre) <= np.nanmedian(w_pre + a_pre)]), high=sc(ride[(w_pre + a_pre) > np.nanmedian(w_pre + a_pre)])))
    print(day, "S7 after-exit env:", B[day])
json.dump(dict(large_moves=summ, dipole_rides=B), open(OUT / "m20_trade_environment.json", "w"), indent=1)
