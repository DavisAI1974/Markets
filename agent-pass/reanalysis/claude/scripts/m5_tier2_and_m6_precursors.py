"""M5: Tier 2 cross-day tables (Ccode suite, Markets 3d0b06a): extract the relationships that hold on all four days, by family, with min |rho| and
beyond-line days; state cells; lead-lag. M6: continuous precursor onsets (markets-data 71240aa): onset -> next birth rate, births covered, lead times."""
import pandas as pd, numpy as np, json
from common import *
out = {}
c = pd.read_csv(SUITE / "crossday/t2x_coupling_crossday.csv")
out["couplings_total"] = len(c)
fam = {}
for f, g in c.groupby("family"):
    fam[f] = dict(pairs=len(g), same_sign_4of4=int((g.days_same_sign == 4).sum()), beyond_line_4days=int((g.days_beyond_line == 4).sum()), beyond_line_0days=int((g.days_beyond_line == 0).sum()),
                  top_4of4_by_min_abs_rho=g[g.days_same_sign == 4].sort_values("min_abs_rho", ascending=False).head(8)[["x", "y", "rho_1002", "rho_1003", "rho_1017", "rho_1018", "days_beyond_line"]].round(3).to_dict("records"))
out["coupling_families"] = fam
# price -> later behavior couplings: x = prior price/quote change conditions (prior_*, qchg_*, am?), y = later book/flow (F_add, F_cx, F_sup, F_net)
px = c[c.x.str.match(r"^(prior_\d+|qchg_\d+|dm_prior|ret_\d+|mom_\d+)") & c.y.str.match(r"^(F_|am_|dspr)")]
out["price_to_behavior_couplings"] = px.sort_values("min_abs_rho", ascending=False)[["x", "y", "rho_1002", "rho_1003", "rho_1017", "rho_1018", "days_same_sign", "days_beyond_line"]].round(3).head(40).to_dict("records")
out["x_groups"] = c.x_group.value_counts().to_dict(); out["x_list"] = sorted(c.x.unique().tolist()); out["y_list"] = sorted(c.y.unique().tolist())
sc = pd.read_csv(SUITE / "crossday/t2x_state_cells_crossday.csv")
out["state_cells_all_same_sign"] = sc[sc.days_same_sign == 4][["cell", "horizon", "net_1002", "net_1003", "net_1017", "net_1018", "support_1018", "min_abs_net"]].round(3).to_dict("records")
out["state_cells_not_same_sign"] = sc[sc.days_same_sign < 4][["cell", "horizon", "net_1002", "net_1003", "net_1017", "net_1018", "days_same_sign"]].round(3).to_dict("records")
ll = pd.read_csv(SUITE / "crossday/t2x_leadlag_crossday.csv")
out["leadlag_all_days_beyond_band"] = ll[ll.days_exceeds_band == 4][["A", "B", "rho_lag0_1002", "rho_lag0_1003", "rho_lag0_1017", "rho_lag0_1018", "rho_lag1_1018", "rho_lag_m1_1018", "peak_lag_min", "peak_lag_max"]].round(3).to_dict("records")
fs = pd.read_csv(SUITE / "crossday/t2x_forward_stack_outcomes.csv"); out["forward_stack_outcomes"] = fs.round(3).to_dict("records")
# M6 precursors
cs = pd.read_csv(CONT / "four-day-continuous-summary.csv")
cs["onset_to_birth_rate"] = (cs.onsets_with_next_birth / cs.onsets).round(3)
cs["birth_coverage"] = (cs.births_with_prior_onset / cs.retained_births).round(3)
out["precursors"] = cs[["day", "hypothesis", "onsets", "onsets_with_next_birth", "onset_to_birth_rate", "retained_births", "births_with_prior_onset", "birth_coverage", "median_last_lead_s", "median_quote_age_s"]].to_dict("records")
pre = []
for day in DAYS:
    osum = pd.read_csv(CONT / f"{day}/research-atlas-v2/continuous-prebirth-v1/outcome-summary.csv")
    osum["day"] = day; pre.append(osum)
osum = pd.concat(pre); osum.to_csv(OUT / "m6_precursor_outcome_summary.csv", index=False)
out["precursor_outcome_summary_columns"] = list(osum.columns); out["precursor_outcome_summary_head"] = osum.head(12).round(3).to_dict("records")
json.dump(out, open(OUT / "m5_m6_summary.json", "w"), indent=1, default=str)
print(json.dumps({k: out[k] for k in ("couplings_total", "x_groups")})); print("families:", {k: {kk: v[kk] for kk in ("pairs", "same_sign_4of4", "beyond_line_4days")} for k, v in fam.items()})
print("price->behavior couplings:", len(px)); print(pd.DataFrame(out["price_to_behavior_couplings"]).head(15).to_string())
print(cs[["day", "hypothesis", "onsets", "onset_to_birth_rate", "birth_coverage", "median_last_lead_s"]].to_string())
print(osum.head(8).to_string())
