"""M16b: exhaustion CONVENTION check (rerun v2). The M16 'ride to exhaustion' used the midpoint at the boundary that STARTS the exhaustion second,
i.e. before the first opposed print is known. A realistic exit can only happen at the END of that second. Compare both conventions, the midpoint
change inside the exhaustion second itself, after-exhaustion and after-flip +60 s from the start vs the end of the marking second, the realistic
exit rule (exhaustion-end or 60 s) and the fixed k5->60 hold. Reads m16_lookahead_lifecycle_candidates.csv and Ccode's x13 life paths."""
import pandas as pd, numpy as np, json
from common import *
LIFE = EV / "final_markets" / FR / "claude-pass-3day/tables/dipole"
out = {}
def sc(a): a = np.asarray(a, float); a = a[np.isfinite(a)]; return dict(n=int(a.size), up=int((a > 0).sum()), flat=int((a == 0).sum()), down=int((a < 0).sum()), p25=float(np.percentile(a, 25)) if a.size else None, p50=float(np.median(a)) if a.size else None, p75=float(np.percentile(a, 75)) if a.size else None)
for day in DAYS:
    z = np.load(LIFE / f"{day}/instances/x13_life_paths.npz", allow_pickle=True); ks = z["ks"]; i0 = int(np.where(ks == 0)[0][0]); mid = z["mid_o"]; n = mid.shape[0]
    lc = pd.read_csv(OUT / "m16_lookahead_lifecycle_candidates.csv"); lc = lc[lc.day == int(day)].set_index("row").reindex(z["row"])
    ke = lc.k_exhaustion.values; kf = lc.k_flip_majority.values; m5 = mid[:, i0 + 5]
    def at(k, off=0):
        return np.array([mid[i, i0 + int(kk) + off] if np.isfinite(kk) and i0 + int(kk) + off < mid.shape[1] else np.nan for i, kk in enumerate(k)])
    ride_A = np.where(ke <= 5, 0.0, at(ke, 0) - m5); ride_B = np.where(ke <= 5, 0.0, at(ke, 1) - m5)
    tick_in_exh_second = at(ke, 1) - at(ke, 0)
    after_B_60 = at(ke, 61) - at(ke, 1); after_A_60 = at(ke, 60) - at(ke, 0)
    flip_B_60 = at(kf, 61) - at(kf, 1); flip_A_60 = at(kf, 60) - at(kf, 0)
    exit_B = np.where(ke <= 5, 0.0, np.where(np.isfinite(ke) & (ke <= 60), at(ke, 1), mid[:, i0 + 60]) - m5)
    out[day] = dict(ride_to_exhaustion_before_opposed_print=sc(ride_A), ride_to_exhaustion_after_opposed_print=sc(ride_B), midpoint_change_inside_exhaustion_second=sc(tick_in_exh_second),
                    after_exhaustion_60s_from_end_of_second=sc(after_B_60), after_exhaustion_60s_from_start_of_second=sc(after_A_60),
                    after_flip_60s_from_end_of_second=sc(flip_B_60), after_flip_60s_from_start_of_second=sc(flip_A_60), exit_rule_realistic=sc(exit_B), k5_to_60_hold=sc(mid[:, i0 + 60] - m5))
    print(day, {k: (v["up"], v["flat"], v["down"]) for k, v in out[day].items()})
json.dump(out, open(OUT / "m16b_exhaustion_convention_check.json", "w"), indent=1)
