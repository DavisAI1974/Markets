"""M16: the dipole lifecycle at the LOOK-AHEAD clock. CONVENTION NOTE (rerun v2): m_exh is the midpoint at the boundary that STARTS the exhaustion second (before the opposed print is known); m_exh_end is the midpoint at the boundary that ENDS it (the realistic exit). Both are reported; the headline uses m_exh_end.
 The saturated 20 s window is knowable the second it completes; the Native detector reports it
~50 s later. Using Ccode's per-candidate life paths (Markets@3d0b06a claude-pass-3day/tables/dipole/<day>/instances/x13_life_paths.npz: oriented
midpoint mid_o and with/against lots per second, k=-60..+1260 from the pre-birth cutoff), rebuild the oriented 20 s window per candidate and mark,
at completed-second clocks: drive (window fully one-sided), exhaustion onset (first fresh against lot), window empty, flip (window majority / fully
opposite), operational end (third consecutive opposite second). Measure oriented price from early decision clocks (k=+1, +5) to each mark and horizon,
and compare with the Native recognition clock (delay_s). Per date; controls from x03_control_stats where available."""
import pandas as pd, numpy as np, json
from common import *
LIFE = EV / "final_markets" / FR / "claude-pass-3day/tables/dipole"
out = {}; percand = []
def sc(a):
    a = a[np.isfinite(a)]; return dict(n=int(a.size), up=int((a > 0).sum()), flat=int((a == 0).sum()), down=int((a < 0).sum()), p25=float(np.percentile(a, 25)) if a.size else None, p50=float(np.median(a)) if a.size else None, p75=float(np.percentile(a, 75)) if a.size else None)
for day in DAYS:
    z = np.load(LIFE / f"{day}/instances/x13_life_paths.npz", allow_pickle=True)
    ks = z["ks"]; mid = z["mid_o"]; w = z["with_lots"]; a = z["against_lots"]; n = mid.shape[0]
    x03 = pd.read_csv(LIFE / f"{day}/x03_cohort_mid_o_birth_axis.csv.gz")[["row", "delay_s"]]
    delay = x03.set_index("row").delay_s.reindex(z["row"]).values
    i0 = int(np.where(ks == 0)[0][0])  # boundary k=0 = pre-birth cutoff; interval j covers (k_j, k_{j+1}]
    # rolling 20-interval sums ending at interval j (intervals j-19..j); interval i0 is the birth second
    cw = np.cumsum(np.concatenate([np.zeros((n, 1)), np.nan_to_num(w)], axis=1), axis=1); ca = np.cumsum(np.concatenate([np.zeros((n, 1)), np.nan_to_num(a)], axis=1), axis=1)
    def roll(c, j): return c[:, j + 1] - c[:, max(0, j - 19)]
    J = range(i0, w.shape[1])
    rw = np.stack([roll(cw, j) for j in J], axis=1); ra = np.stack([roll(ca, j) for j in J], axis=1)
    tot = rw + ra; ratio = np.where(tot > 0, (rw - ra) / np.where(tot > 0, tot, 1), np.nan)   # oriented: +1 fully with the birth direction
    fresh_against = np.nan_to_num(a[:, i0:]) > 0
    rec = {}
    def first_k(cond):  # cond shape (n, len(J)) over k = 0..; return k (seconds after birth second start) of first True, else nan
        idx = np.argmax(cond, axis=1).astype(float); has = cond.any(axis=1); idx[~has] = np.nan; return idx
    k_exh = first_k(fresh_against[:, 1:]) + 1                      # first fresh opposed lot after the birth second
    k_empty = first_k((tot[:, 1:] == 0)) + 1                        # window empty
    k_flipmaj = first_k((ratio[:, 1:] < 0)) + 1                     # window majority opposite
    k_flipfull = first_k((ratio[:, 1:] <= -1 + 1e-12) & (tot[:, 1:] > 0)) + 1  # window fully opposite
    opp = (ratio < 0); o3 = opp[:, 2:] & opp[:, 1:-1] & opp[:, :-2]; k_end = first_k(o3[:, :]) + 2   # third consecutive opposite second
    mid_k = lambda k: np.array([mid[i, i0 + int(kk)] if np.isfinite(kk) and i0 + int(kk) < mid.shape[1] else np.nan for i, kk in enumerate(k)])
    m0 = mid[:, i0]; m1 = mid[:, i0 + 1]; m5 = mid[:, i0 + 5]
    def at(k): return mid[:, i0 + k] if i0 + k < mid.shape[1] else np.full(n, np.nan)
    mrec = np.array([mid[i, i0 + int(np.ceil(d))] if np.isfinite(d) and i0 + int(np.ceil(d)) < mid.shape[1] else np.nan for i, d in enumerate(delay)])
    df = pd.DataFrame(dict(day=day, row=z["row"], pol=z["pol"], delay_s=delay, k_exhaustion=k_exh, k_empty=k_empty, k_flip_majority=k_flipmaj, k_flip_full=k_flipfull, k_end_opp3=k_end,
                           m0=m0, m1=m1, m5=m5, m_rec=mrec, m_exh=mid_k(k_exh), m_exh_end=mid_k(k_exh + 1), m_flipmaj=mid_k(k_flipmaj), m_flipfull=mid_k(k_flipfull), m_end=mid_k(k_end), m20=at(20), m60=at(60), m160=at(160), m300=at(300), m600=at(600)))
    percand.append(df)
    r = dict(day=day, candidates=n,
             knowable_marks_s=dict(exhaustion_onset=sc(df.k_exhaustion.values), window_empty=sc(df.k_empty.values), flip_majority=sc(df.k_flip_majority.values), flip_full=sc(df.k_flip_full.values), end_opp3=sc(df.k_end_opp3.values), native_recognition=sc(df.delay_s.values)),
             share_with_mark=dict(exhaustion=float(np.isfinite(k_exh).mean()), empty=float(np.isfinite(k_empty).mean()), flip_majority=float(np.isfinite(k_flipmaj).mean()), flip_full=float(np.isfinite(k_flipfull).mean()), end=float(np.isfinite(k_end).mean())),
             exhaustion_before_recognition=int(np.nansum(k_exh < delay)), flip_before_recognition=int(np.nansum(k_flipmaj < delay)), end_before_recognition=int(np.nansum(k_end < delay)),
             ride_from_k5=dict(to_exhaustion=sc(np.where(df.k_exhaustion.values <= 5, 0.0, (df.m_exh - df.m5).values)), to_exhaustion_end_of_second=sc(np.where(df.k_exhaustion.values <= 5, 0.0, (df.m_exh_end - df.m5).values)), inside_exhaustion_second=sc((df.m_exh_end - df.m_exh).values), to_flip_majority=sc((df.m_flipmaj - df.m5).values), to_end=sc((df.m_end - df.m5).values), to_recognition=sc((df.m_rec - df.m5).values), to_20=sc((df.m20 - df.m5).values), to_60=sc((df.m60 - df.m5).values), to_160=sc((df.m160 - df.m5).values), to_300=sc((df.m300 - df.m5).values), to_600=sc((df.m600 - df.m5).values)),
             ride_from_k1=dict(to_exhaustion=sc((df.m_exh - df.m1).values), to_60=sc((df.m60 - df.m1).values), to_300=sc((df.m300 - df.m1).values)),
             ride_from_k0=dict(to_60=sc((df.m60 - df.m0).values), to_160=sc((df.m160 - df.m0).values)),
             from_recognition=dict(to_60_after=sc((np.array([mid[i, i0 + int(np.ceil(d)) + 60] if np.isfinite(d) and i0 + int(np.ceil(d)) + 60 < mid.shape[1] else np.nan for i, d in enumerate(delay)]) - mrec)), to_300_after=sc((np.array([mid[i, i0 + int(np.ceil(d)) + 300] if np.isfinite(d) and i0 + int(np.ceil(d)) + 300 < mid.shape[1] else np.nan for i, d in enumerate(delay)]) - mrec))),
             after_exhaustion=dict(to_60=sc((np.array([mid[i, i0 + int(k) + 60] if np.isfinite(k) and i0 + int(k) + 60 < mid.shape[1] else np.nan for i, k in enumerate(k_exh)]) - df.m_exh.values)), to_300=sc((np.array([mid[i, i0 + int(k) + 300] if np.isfinite(k) and i0 + int(k) + 300 < mid.shape[1] else np.nan for i, k in enumerate(k_exh)]) - df.m_exh.values))),
             after_flip_majority_oriented_to_birth=dict(to_60=sc((np.array([mid[i, i0 + int(k) + 60] if np.isfinite(k) and i0 + int(k) + 60 < mid.shape[1] else np.nan for i, k in enumerate(k_flipmaj)]) - df.m_flipmaj.values)), to_300=sc((np.array([mid[i, i0 + int(k) + 300] if np.isfinite(k) and i0 + int(k) + 300 < mid.shape[1] else np.nan for i, k in enumerate(k_flipmaj)]) - df.m_flipmaj.values))),
             exit_rule_vs_fixed=dict(k5_to_exhaustion_or_60=sc(np.where(np.isfinite(k_exh) & (k_exh <= 5), 0.0, np.where(np.isfinite(k_exh) & (k_exh <= 60), df.m_exh.values, df.m60.values) - m5)), k5_to_exhaustion_end_or_60=sc(np.where(np.isfinite(k_exh) & (k_exh <= 5), 0.0, np.where(np.isfinite(k_exh) & (k_exh <= 60), df.m_exh_end.values, df.m60.values) - m5)), k5_to_flip_or_300=sc(np.where(np.isfinite(k_flipmaj) & (k_flipmaj <= 300), df.m_flipmaj.values, df.m300.values) - m5)))
    out[day] = r
    print(day, "marks(s) p50:", {k: v["p50"] for k, v in r["knowable_marks_s"].items()}, "| exh<rec", r["exhaustion_before_recognition"], "flip<rec", r["flip_before_recognition"], "end<rec", r["end_before_recognition"])
    print("   ride k5->exh", {k: r["ride_from_k5"]["to_exhaustion"][k] for k in ("n", "up", "flat", "down", "p50")}, "| k5->60", {k: r["ride_from_k5"]["to_60"][k] for k in ("up", "flat", "down", "p50")}, "| k5->300", {k: r["ride_from_k5"]["to_300"][k] for k in ("up", "flat", "down", "p50")}, "| k5->rec", {k: r["ride_from_k5"]["to_recognition"][k] for k in ("up", "flat", "down", "p50")})
    print("   from recognition +60", {k: r["from_recognition"]["to_60_after"][k] for k in ("up", "flat", "down")}, "| after exhaustion +60", {k: r["after_exhaustion"]["to_60"][k] for k in ("up", "flat", "down")}, "| after flip(maj) +60 (oriented to birth dir)", {k: r["after_flip_majority_oriented_to_birth"]["to_60"][k] for k in ("up", "flat", "down")})
    print("   exit rule k5->exh|60", {k: r["exit_rule_vs_fixed"]["k5_to_exhaustion_or_60"][k] for k in ("up", "flat", "down", "p50")}, "| k5->flip|300", {k: r["exit_rule_vs_fixed"]["k5_to_flip_or_300"][k] for k in ("up", "flat", "down", "p50")})
pd.concat(percand).to_csv(OUT / "m16_lookahead_lifecycle_candidates.csv", index=False)
json.dump(out, open(OUT / "m16_lookahead_lifecycle.json", "w"), indent=1)
