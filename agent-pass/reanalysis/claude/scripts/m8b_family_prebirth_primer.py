"""M8b: Family replication (markets-data 7b50d63): four-arm ridge arms (direction agreements), prebirth matched contrasts by feature/lead,
primer spread-event responses (aggression-to-rest cases), equal-control-weight sensitivity. Reads existing measured tables only."""
import pandas as pd, numpy as np, json
from common import *
out = {}
arm = []; pre = []; prim = []; sens = []; coh = []
for day in DAYS:
    F = FAMILY / f"family-{day}"
    a = pd.read_csv(F / "flow-book-discovery-v1/arm-metrics.csv"); a["day"] = day; arm.append(a)
    p = pd.read_csv(F / "research-atlas-v2/prebirth-summary.csv"); p["day"] = day; pre.append(p)
    q = pd.read_csv(F / "research-atlas-v2/primer-spread-event-summary.csv"); q["day"] = day; prim.append(q)
    s = pd.read_csv(F / "research-atlas-v2/primer-prebirth-sensitivity.csv"); s["day"] = day; sens.append(s)
    c = pd.read_csv(F / "flow-book-discovery-v1/cohort-outcomes.csv"); c["day"] = day; coh.append(c)
arm = pd.concat(arm); pre = pd.concat(pre); prim = pd.concat(prim); sens = pd.concat(sens); coh = pd.concat(coh)
arm["dir_share"] = arm.direction_agreements / arm.n_test
ag = arm[arm.target == "signed"].groupby(["day", "horizon_s", "arm"]).agg(n_test=("n_test", "sum"), dir_agree=("direction_agreements", "sum"), mae=("mae", "mean")).reset_index()
ag["dir_share"] = (ag.dir_agree / ag.n_test).round(3)
ag.to_csv(OUT / "m8b_fourarm_direction.csv", index=False)
pv = ag.pivot_table(index=["horizon_s", "arm"], columns="day", values="dir_share"); print(pv.round(3).to_string())
pre.to_csv(OUT / "m8b_prebirth_summary_alldays.csv", index=False)
agg = pre[pre.quarter.astype(str).isin(["all", "0", "nan"]) | True].groupby(["day", "feature", "lead_s"]).agg(pairs=("matched_pairs", "sum"), defined=("defined_pairs", "sum"), greater=("greater", "sum"), equal=("equal", "sum"), less=("less", "sum")).reset_index()
agg.to_csv(OUT / "m8b_prebirth_feature_lead.csv", index=False)
print(agg.pivot_table(index=["feature", "lead_s"], columns="day", values=["greater", "less"]).to_string()[:6000])
prim.to_csv(OUT / "m8b_primer_spread_events.csv", index=False)
pp = prim.groupby(["day", "regime", "touch_sign", "horizon"]).agg(n=("n", "sum"), up=("up", "sum"), down=("down", "sum"), flat=("flat", "sum")).reset_index()
print(pp[pp.horizon.isin(["1s", "5s", "20s"])].to_string()[:5000])
sens.to_csv(OUT / "m8b_primer_sensitivity.csv", index=False); print(sens.to_string()[:4000])
coh.to_csv(OUT / "m8b_cohort_outcomes.csv", index=False)
