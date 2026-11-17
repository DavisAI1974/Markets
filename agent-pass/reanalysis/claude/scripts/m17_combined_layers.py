"""M17: many layers together at the look-ahead decision clock (k=+5 s after the birth second). For every covered candidate assemble the layers
knowable by then from Ccode's life paths (x13: spread, target/own touch size and order counts, near-5 depth, prebirth adds/cancels/fills by side,
window lots), the recorded operands (prominence, baseline, competing peaks, observations), path-member regime/activity, UTC hour, orientation,
gap to previous birth, and (constant within a session) the 13 external points. Outcomes: ride to exhaustion sign, exhaustion timing class, 60 s move,
flip timing. Method: per-date tertile cells per layer, two-way cells of consistent layers, and a leave-one-date-out additive sign score
(a layer contributes +1/-1 if its tertile direction is the same on the three training dates), evaluated by counts on the held-out date."""
import pandas as pd, numpy as np, json
from common import *
LIFE = EV / "final_markets" / FR / "claude-pass-3day/tables/dipole"
feats_all = []
for day in DAYS:
    z = np.load(LIFE / f"{day}/instances/x13_life_paths.npz", allow_pickle=True); ks = z["ks"]; i0 = int(np.where(ks == 0)[0][0]); k5 = i0 + 5
    lc = pd.read_csv(OUT / "m16_lookahead_lifecycle_candidates.csv"); lc = lc[lc.day == int(day)].set_index("row")
    x03 = pd.read_csv(LIFE / f"{day}/x03_cohort_mid_o_birth_axis.csv.gz")
    rows = z["row"]
    def pre(arr, a, b): return np.nansum(arr[:, i0 + a:i0 + b + 1], axis=1)  # intervals k in [a,b]
    F = pd.DataFrame(dict(row=rows, pol=z["pol"],
        spr_k5=z["spr"][:, k5], tgt_sz_k5=z["tgt_sz"][:, k5], own_sz_k5=z["own_sz"][:, k5], tgt_n_k5=z["tgt_n"][:, k5], own_n_k5=z["own_n"][:, k5], tgt_near5_k5=z["tgt_near5"][:, k5], own_near5_k5=z["own_near5"][:, k5],
        touch_ratio_k5=(z["own_sz"][:, k5] + 1) / (z["tgt_sz"][:, k5] + 1), near5_ratio_k5=(z["own_near5"][:, k5] + 1) / (z["tgt_near5"][:, k5] + 1),
        with_lots_0_5=pre(z["with_lots"], 0, 5), against_lots_0_5=pre(z["against_lots"], 0, 5), with_lots_m20_m1=pre(z["with_lots"], -20, -1), against_lots_m20_m1=pre(z["against_lots"], -20, -1),
        n_trades_m20_5=pre(z["n_trades"], -20, 5), tgt_add_touch_m20_5=pre(z["tgt_add_touch"], -20, 5), own_add_touch_m20_5=pre(z["own_add_touch"], -20, 5), tgt_fill_m20_5=pre(z["tgt_fill"], -20, 5), own_fill_m20_5=pre(z["own_fill"], -20, 5),
        tgt_rm_cx_touch_m20_5=pre(z["tgt_rm_cx_touch"], -20, 5), own_rm_cx_touch_m20_5=pre(z["own_rm_cx_touch"], -20, 5), tgt_add_near_m20_5=pre(z["tgt_add_near"], -20, 5), own_add_near_m20_5=pre(z["own_add_near"], -20, 5),
        mid_m60_0=z["mid_o"][:, i0] - z["mid_o"][:, i0 - 60], mid_m20_0=z["mid_o"][:, i0] - z["mid_o"][:, i0 - 20], mid_0_5=z["mid_o"][:, k5] - z["mid_o"][:, i0], spr_change_m20_5=z["spr"][:, k5] - z["spr"][:, i0 - 20]))
    F["tgt_add_minus_fill"] = F.tgt_add_touch_m20_5 - F.tgt_fill_m20_5; F["own_add_minus_cx"] = F.own_add_touch_m20_5 - F.own_rm_cx_touch_m20_5
    F = F.merge(x03[["row", "delay_s"]], on="row", how="left")
    ops = pd.read_csv(NATIVE / f"{day}-candidate-operands.csv"); pm = pd.read_csv(NATIVE / f"{day}-path-members.csv"); pm = pm[pm.kind == "candidate"]
    ci = pd.read_csv(LIFE / f"{day}/t6_cohort_features.csv")[["row", "prov_candidate_id"]].rename(columns={"prov_candidate_id": "candidate_id"})
    F = F.merge(ci.drop_duplicates("row"), on="row", how="left"); print(day, "row->candidate_id mapped:", int(F.candidate_id.notna().sum()), "of", len(F))
    if "candidate_id" in F:
        F = F.merge(ops[list(dict.fromkeys(["candidate_id", "orientation", "prominence", "baseline", "competing_peaks" if "competing_peaks" in ops else "observations_behind_threshold", "observations_behind_threshold"]))].drop_duplicates("candidate_id"), on="candidate_id", how="left")
        F = F.merge(pm[["candidate_id", "regime", "activity_bucket", "activity"]], on="candidate_id", how="left")
        lag = pd.read_csv(NATIVE / f"{day}-lag-measurements.csv")[["candidate_id", "competing_peaks", "window_open", "winning_offset_s"]]; F = F.merge(lag, on="candidate_id", how="left", suffixes=("", "_lag"))
        c1 = pd.read_csv(OUT / f"m1_candidates_{day}.csv", low_memory=False)[["candidate_id", "anchor_label_ns", "flow_state"]]; F = F.merge(c1, on="candidate_id", how="left")
        F["hour"] = pd.to_datetime(F.anchor_label_ns, unit="ns").dt.hour
        b = np.sort(F.anchor_label_ns.dropna().values); F["prev_gap_s"] = [(t - b[b < t].max()) / 1e9 if pd.notna(t) and (b < t).any() else np.nan for t in F.anchor_label_ns.values]
    # outcomes from m16
    F = F.merge(lc[["k_exhaustion", "k_flip_majority", "m5", "m_exh", "m_exh_end", "m60", "m300", "m_flipmaj"]], left_on="row", right_index=True, how="left")
    F["ride_exh"] = F.m_exh - F.m5; F["ride_exh_end"] = np.where(F.k_exhaustion <= 5, 0.0, F.m_exh_end - F.m5); F["ride_60"] = F.m60 - F.m5; F["ride_300"] = F.m300 - F.m5; F["exh_class"] = pd.cut(F.k_exhaustion.fillna(9999), [0, 19.5, 60, 1e9], labels=["lt20", "20to60", "gt60"])
    F["day"] = day; feats_all.append(F)
A = pd.concat(feats_all, ignore_index=True); A.to_csv(OUT / "m17_features.csv.gz", index=False)
LAYERS = ["spr_k5", "tgt_sz_k5", "own_sz_k5", "tgt_n_k5", "own_n_k5", "tgt_near5_k5", "own_near5_k5", "touch_ratio_k5", "near5_ratio_k5", "with_lots_0_5", "with_lots_m20_m1", "against_lots_m20_m1", "n_trades_m20_5", "tgt_add_touch_m20_5", "own_add_touch_m20_5", "tgt_fill_m20_5", "own_fill_m20_5", "tgt_rm_cx_touch_m20_5", "own_rm_cx_touch_m20_5", "tgt_add_near_m20_5", "own_add_near_m20_5", "tgt_add_minus_fill", "own_add_minus_cx", "mid_m60_0", "mid_m20_0", "mid_0_5", "spr_change_m20_5", "prominence", "baseline", "observations_behind_threshold", "competing_peaks", "winning_offset_s", "activity", "prev_gap_s", "hour"]
LAYERS = [l for l in LAYERS if l in A.columns]
OUTC = {"ride_exh": "ride k5->exhaustion, midpoint before the opposed print (oriented ticks)", "ride_exh_end": "ride k5->exhaustion, midpoint at the end of the exhaustion second (realistic exit)", "ride_60": "k5->60 s", "ride_300": "k5->300 s"}
def tert(s):
    q = s.rank(pct=True, method="average"); return pd.cut(q, [0, 1/3, 2/3, 1.0001], labels=["low", "mid", "high"], include_lowest=True)
cells = []; sign_table = {}
for out_name in OUTC:
    for L in LAYERS:
        per = {}
        for day in DAYS:
            d = A[(A.day == day) & A[L].notna() & A[out_name].notna()].copy()
            if d[L].nunique() < 3: continue
            d["t"] = tert(d[L])
            for t in ["low", "mid", "high"]:
                g = d[d.t == t]; cells.append(dict(outcome=out_name, layer=L, tertile=t, day=day, n=len(g), up=int((g[out_name] > 0).sum()), flat=int((g[out_name] == 0).sum()), down=int((g[out_name] < 0).sum()), mean=float(g[out_name].mean())))
            hi = d[d.t == "high"][out_name]; lo = d[d.t == "low"][out_name]
            per[day] = np.sign(((hi > 0).mean() - (hi < 0).mean()) - ((lo > 0).mean() - (lo < 0).mean()))
        sign_table[(out_name, L)] = per
C = pd.DataFrame(cells); C.to_csv(OUT / "m17_layer_tertile_cells.csv", index=False)
cons = [(o, L, p) for (o, L), p in sign_table.items() if len(p) == 4 and len(set(p.values())) == 1 and 0 not in p.values()]
print("layers with the same high-vs-low direction on all four dates:")
for o, L, p in cons: print("  ", o, L, list(p.values())[0])
# leave-one-date-out additive sign score for ride_exh and ride_60
score_res = {}
for out_name in ["ride_exh", "ride_exh_end", "ride_60"]:
    res = {}
    for held in DAYS:
        train = [d for d in DAYS if d != held]
        use = [(L, list(sign_table[(out_name, L)].values())[0]) for L in LAYERS if (out_name, L) in sign_table and all(d in sign_table[(out_name, L)] for d in train) and len({sign_table[(out_name, L)][d] for d in train}) == 1 and sign_table[(out_name, L)][train[0]] != 0]
        d = A[(A.day == held) & A[out_name].notna()].copy(); s = np.zeros(len(d))
        for L, sg in use:
            if d[L].notna().sum() < 10: continue
            t = tert(d[L].fillna(d[L].median())); s += sg * ((t == "high").astype(int) - (t == "low").astype(int)).values
        d["score"] = s
        bins = pd.cut(d.score, [-99, -3, -1, 0, 2, 99], labels=["<=-3", "-2..-1", "0", "1..2", ">=3"])
        res[held] = dict(layers_used=len(use), by_score={str(k): dict(n=len(g), up=int((g[out_name] > 0).sum()), flat=int((g[out_name] == 0).sum()), down=int((g[out_name] < 0).sum())) for k, g in d.groupby(bins, observed=True)},
                        top_vs_bottom=dict(top=dict(n=int((d.score >= 3).sum()), up=int(((d.score >= 3) & (d[out_name] > 0)).sum()), down=int(((d.score >= 3) & (d[out_name] < 0)).sum())), bottom=dict(n=int((d.score <= -3).sum()), up=int(((d.score <= -3) & (d[out_name] > 0)).sum()), down=int(((d.score <= -3) & (d[out_name] < 0)).sum()))))
    score_res[out_name] = res
    print(out_name, json.dumps(res))
json.dump(dict(consistent_layers=[dict(outcome=o, layer=L, direction=int(list(p.values())[0])) for o, L, p in cons], leave_one_date_out=score_res, layers=LAYERS), open(OUT / "m17_combined_layers.json", "w"), indent=1)
