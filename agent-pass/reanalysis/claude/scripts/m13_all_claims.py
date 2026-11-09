"""M13: every measured relationship becomes a CLAIMS.csv row (brief: retain every considered relationship regardless of strength).
Appends generated rows after the hand-written ones; per-date numbers kept as strings, never pooled."""
import pandas as pd, numpy as np, json, csv
from common import *
H = ["claim_id","direction","question","interpretation","observed_correspondence","applicability_conditions","contrary_or_absent_correspondence","unresolved_aspects","source_references","date_population","numerator_denominator","decision_clock","endpoint","measured_lead_time","limitations"]
rows = []
def fmt(d): return "; ".join(f"{k}: {v}" for k, v in d.items())
def interp(ups, downs):
    s = [(u > d) - (u < d) for u, d in zip(ups, downs) if (u + d) > 0]
    if not s: return "no observations"
    if all(x > 0 for x in s): return "same sign on all dates with observations (positive)"
    if all(x < 0 for x in s): return "same sign on all dates with observations (negative)"
    return "mixed sign across dates (retained as condition-dependent or null)"
def add(cid, direction, q, it, obs, cond="", contra="", unres="", src="", pop="per date", clock="", end="", lead="n/a", lim=""):
    rows.append([cid, direction, q, it, obs, cond, contra, unres, src, pop, "see counts", clock, end, lead, lim])
# M16 look-ahead lifecycle
m16 = json.load(open(OUT / "m16_lookahead_lifecycle.json"))
for key, q, clock, end in [("ride_from_k5", "Oriented midpoint from decision clock k=+5 s to each knowable mark / horizon", "birth second +5 s (window saturation knowable; local max confirmed)", "mark or horizon"), ("ride_from_k1", "Oriented midpoint from k=+1 s", "birth second +1 s", "mark/horizon"), ("ride_from_k0", "Oriented midpoint from the pre-birth boundary", "k=0", "horizon"), ("from_recognition", "Oriented midpoint after Native recognition", "recognition", "+60/+300 s"), ("after_exhaustion", "Oriented midpoint after the first fresh opposed lot (exhaustion onset)", "exhaustion onset completed second", "+60/+300 s"), ("after_flip_majority_oriented_to_birth", "Oriented midpoint (to birth direction) after the window turns majority-opposite", "flip completed second", "+60/+300 s"), ("exit_rule_vs_fixed", "Ride from k=+5 with exit at exhaustion onset (else 60 s) or at flip (else 300 s)", "k=+5 s", "exit mark")]:
    for sub in m16[DAYS[0]][key]:
        conv = (" | CONVENTION: midpoint at the START of the marking second (before the opposed print is known); the realizable END-of-second variant is the M16B row and the *_end_of_second key, symmetric on all four dates" if ((key in ("ride_from_k5", "ride_from_k1") and sub == "to_exhaustion") or key in ("after_exhaustion", "after_flip_majority_oriented_to_birth") or (key == "exit_rule_vs_fixed" and sub == "k5_to_exhaustion_or_60")) else "")
        add(f"LA-{key}-{sub}", "look-ahead dipole lifecycle", f"{q}: {sub}", interp([m16[d][key][sub]["up"] for d in DAYS], [m16[d][key][sub]["down"] for d in DAYS]) + conv, fmt({d: json.dumps({k: m16[d][key][sub][k] for k in ("n", "up", "flat", "down", "p25", "p50", "p75")}) for d in DAYS}), "covered Native candidates 741/824/740/852 (recorded births = competition winners)", "", "earliest-knowable population includes qualifying peaks that did not win the 45 s competition (not measured here)", "tables/m16_lookahead_lifecycle.json; Markets@3d0b06a x13_life_paths.npz", clock=clock, end=end, lim="midpoint ticks, gross")
for sub in m16[DAYS[0]]["knowable_marks_s"]:
    add(f"LA-marks-{sub}", "look-ahead dipole lifecycle (clocks)", f"Seconds from birth second to {sub}", "retained", fmt({d: json.dumps({k: m16[d]["knowable_marks_s"][sub][k] for k in ("n", "p25", "p50", "p75")}) for d in DAYS}), src="tables/m16_lookahead_lifecycle.json", clock="completed second", end=sub)
add("LA-marks-before-recognition", "look-ahead dipole lifecycle (clocks)", "Exhaustion onset / flip / operational end knowable before Native recognition", "same on all dates", fmt({d: f"exhaustion {m16[d]['exhaustion_before_recognition']}, flip {m16[d]['flip_before_recognition']}, end {m16[d]['end_before_recognition']} of {m16[d]['candidates']}" for d in DAYS}), src="tables/m16_lookahead_lifecycle.json", clock="completed second vs recognition_receive_ns", end="n/a")
# M1 cells
c = pd.read_csv(OUT / "m1_decision_cells.csv"); two = c[c.cell_var.notna()]
for (cv, cell), g in two.groupby(["cell_var", "cell"]):
    for h in [5, 20, 60, 300]:
        add(f"M1C-{cv}-{cell}-{h}s", "dipole at Native recognition", f"Oriented midpoint {h} s after recognition, cell {cv}={cell}", interp([int(r[f"cc{h}_up"]) for _, r in g.iterrows()], [int(r[f"cc{h}_down"]) for _, r in g.iterrows()]), fmt({r.day: f"up/flat/down {int(r[f'cc{h}_up'])}/{int(r[f'cc{h}_flat'])}/{int(r[f'cc{h}_down'])} of {int(r.n)}; ended_before {r.share_ended_before_recog}" for _, r in g.iterrows()}), src="tables/m1_decision_cells.csv", clock="recognition_receive_ns", end=f"{h} s", lim="Oct 18-only fields undefined elsewhere")
dep = json.load(open(OUT / "m14_dependence.json"))
for key in dep[DAYS[0]]:
    add(f"M14-{key}", "dependence / robustness", key.replace("_", " "), "retained as measured", fmt({d: json.dumps(dep[d].get(key)) for d in DAYS}), src="tables/m14_dependence.json", clock="as underlying claim", end="as underlying claim", lim="small cells retained, not interpreted")
m2 = json.load(open(OUT / "m2_summary.json"))
for key in ["full_rec_by_size", "full_rec_by_printcount", "full_rec_by_first_disjoint"]:
    add(f"M2C-{key}", "price->price (large move)", f"Large-move full return within 600 s by {key.replace('full_rec_by_', '')}", "retained; no cell separates return on all dates", fmt({d["day"]: json.dumps(d[key]) for d in m2}), src="tables/m2_summary.json", clock="move known_by", end="full return 600 s")
add("M2C-prior_agreement", "behavior->price (large move)", "Large-move full return by majority agreement of prior pressure signals", "no separation", fmt({d["day"]: f"agree {d['full_rec_given_prior_agree_majority']}/{d['n_prior_agree_majority']}, disagree {d['full_rec_given_prior_disagree_majority']}/{d['n_prior_disagree_majority']}" for d in m2}), src="tables/m2_summary.json", clock="move known_by", end="full return 600 s")
e = pd.read_csv(OUT / "m3_episode_cells.csv")
g3 = e[e.side != "both"].groupby(["day", "side", "onset_type", "attack_flow1", "attack_flow20"]).agg(n=("n", "sum"), retreated=("retreated", "sum"), recovered=("recovered", "sum"), improved=("improved", "sum")).reset_index()
for (side, ot, f1, f20), g in g3.groupby(["side", "onset_type", "attack_flow1", "attack_flow20"]):
    add(f"M3C-{side}-{ot}-f1{int(f1)}-f20{int(f20)}", "behavior->price (thin touch)", f"Thin-touch ending: side {side}, onset {ot}, attack flow1={int(f1)}, flow20={int(f20)}", "retained", fmt({r.day: f"retreated/recovered/improved {int(r.retreated)}/{int(r.recovered)}/{int(r.improved)} of {int(r.n)}" for _, r in g.iterrows()}), src="tables/m3_episode_cells.csv", clock="onset known_by", end="episode ending", lim="ms durations")
for ot, g in e[e.side == "both"].groupby("onset_type"):
    add(f"M3C-both-{ot}", "behavior->price (thin touch)", f"Thin-touch ending by {ot}", "retained", fmt({r.day: f"retreated {int(r.retreated)} of {int(r.n)}" for _, r in g.iterrows()}), src="tables/m3_episode_cells.csv", clock="onset known_by", end="episode ending")
d3 = pd.read_csv(OUT / "m3_delayed_outcome_cells.csv")
agg = d3.groupby(["day", "event_type", "side", "horizon_s", "attack_flow1"]).agg(observed=("observed", "sum"), away=("away", "sum"), flat=("flat", "sum"), toward=("toward", "sum")).reset_index()
for (et, side, h, f1), g in agg.groupby(["event_type", "side", "horizon_s", "attack_flow1"]):
    add(f"M3D-{et}-{side}-{h}s-f1{int(f1)}", "behavior->price (pressure signal)", f"{h} s midpoint after {et} side {side} attack flow1={int(f1)} (+ = through the signalled side)", "retained; sign convention pending (C9)", fmt({r.day: f"through/flat/against {int(r.away)}/{int(r.flat)}/{int(r.toward)} of {int(r.observed)}" for _, r in g.iterrows()}), unres="CONFLICTS C9", src="tables/m3_delayed_outcome_cells.csv", clock="signal known_by + 1 ms", end=f"{h} s")
m4 = pd.read_csv(OUT / "m4_tier1_cells.csv")
for (cv, cell, h), g in m4[m4.horizon_s.notna()].groupby(["cell_var", "cell", "horizon_s"]):
    add(f"M4C-{cv}-{cell}-{int(h)}s", "families", f"{cv} ({cell}) at {int(h)} s", interp([int(r['continue_']) for _, r in g.iterrows()], [int(r.reverse) for _, r in g.iterrows()]), fmt({r.day: f"continue/flat/reverse {int(r['continue_'])}/{int(r.flat)}/{int(r.reverse)} of {int(r.n)}" for _, r in g.iterrows()}), src="tables/m4_tier1_cells.csv", clock="cutoff", end=f"{int(h)} s")
for (cv, cell), g in m4[m4.horizon_s.isna()].groupby(["cell_var", "cell"]):
    add(f"M4C-{cv}-{cell}", "families", f"Flow 60/5/1 x full-depth cell {cell} at 5/60/300 s", interp([int(r.up_60) for _, r in g.iterrows()], [int(r.down_60) for _, r in g.iterrows()]), fmt({r.day: f"5s {int(r.up_5)}/{int(r.flat_5)}/{int(r.down_5)}; 60s {int(r.up_60)}/{int(r.flat_60)}/{int(r.down_60)}; 300s {int(r.up_300)}/{int(r.flat_300)}/{int(r.down_300)} of {int(r.n)}" for _, r in g.iterrows()}), src="tables/m4_tier1_cells.csv", clock="cutoff", end="5/60/300 s")
cp = pd.read_csv(SUITE / "crossday/t2x_coupling_crossday.csv")
for _, r in cp.iterrows():
    add(f"T2-{r.x}->{r.y}", "grid coupling (" + ("price->behavior" if str(r.x).startswith(("qchg", "prior")) else "behavior->price") + ")", f"Spearman {r.x} -> {r.y}", f"same sign {int(r.days_same_sign)}/4 days; beyond line {int(r.days_beyond_line)} days; {r.family}", f"rho Oct2/3/17/18 = {r.rho_1002:.3f}/{r.rho_1003:.3f}/{r.rho_1017:.3f}/{r.rho_1018:.3f}", src="Markets@3d0b06a crossday/t2x_coupling_crossday.csv", clock="3 s grid", end=str(r.y), lim="Ccode measurement reused")
for _, r in pd.read_csv(SUITE / "crossday/t2x_state_cells_crossday.csv").iterrows():
    add(f"T2S-{r.cell}-{r.horizon}", "state cell", f"{r.cell} at {r.horizon}", f"same sign {int(r.days_same_sign)}/4", f"net Oct2/3/17/18 = {r.net_1002:.3f}/{r.net_1003:.3f}/{r.net_1017:.3f}/{r.net_1018:.3f}; support {int(r.support_1002)}/{int(r.support_1003)}/{int(r.support_1017)}/{int(r.support_1018)}", src="Markets@3d0b06a crossday/t2x_state_cells_crossday.csv", clock="1 s", end=str(r.horizon))
for _, r in pd.read_csv(SUITE / "crossday/t2x_leadlag_crossday.csv").iterrows():
    add(f"T2L-{r.A}-{r.B}", "lead/lag", f"{r.A} vs {r.B}", f"lag-0 same sign {int(r.days_same_sign_rho_lag0)}/4; beyond band {int(r.days_exceeds_band)} days; peak lag {r.peak_lag_min}..{r.peak_lag_max} s", f"rho lag0 = {r.rho_lag0_1002:.3f}/{r.rho_lag0_1003:.3f}/{r.rho_lag0_1017:.3f}/{r.rho_lag0_1018:.3f}", src="Markets@3d0b06a crossday/t2x_leadlag_crossday.csv", clock="1 s", end="lag", lead=f"peak lag {r.peak_lag_min}..{r.peak_lag_max} s")
for _, r in pd.read_csv(SUITE / "crossday/t2x_forward_stack_outcomes.csv").iterrows():
    add(f"T2F-{r.iloc[0]}", "model comparison", f"Forward stack outcome {r.iloc[0]}", "retained", "; ".join(f"{k}={v}" for k, v in r.items()), src="Markets@3d0b06a crossday/t2x_forward_stack_outcomes.csv", clock="3 s grid")
cs = pd.read_csv(CONT / "four-day-continuous-summary.csv")
for hyp, g in cs.groupby("hypothesis"):
    add(f"M6G-{hyp}", "early warning", f"Onset {hyp}: onset->birth rate, coverage, lead", "retained", fmt({r.day: f"onsets {r.onsets}, with next birth {r.onsets_with_next_birth}, births covered {r.births_with_prior_onset}/{r.retained_births}, median last lead {r.median_last_lead_s} s" for _, r in g.iterrows()}), src="markets-data@71240aa four-day-continuous-summary.csv", clock="onset completed second", end="next birth", lead="median last lead")
os_ = pd.read_csv(OUT / "m6_precursor_outcome_summary.csv")
for (hyp, h), g in os_.groupby(["hypothesis", "horizon_s"]):
    add(f"M6O-{hyp}-{int(h)}s", "after onset", f"Price after onset {hyp} at {int(h)} s", interp([int(r.follows) for _, r in g.iterrows()], [int(r.opposes) for _, r in g.iterrows()]), fmt({r.day: f"up/down/flat {int(r.up)}/{int(r.down)}/{int(r.flat)}; follows/opposes {int(r.follows)}/{int(r.opposes)}; flow weaker/stronger/same {int(r.flow_weaker)}/{int(r.flow_stronger)}/{int(r.flow_same)}; median |ticks| {r.median_abs_ticks}" for _, r in g.iterrows()}), src="markets-data@71240aa outcome-summary.csv", clock="onset", end=f"{int(h)} s")
m7 = pd.read_csv(OUT / "m7_ccode_cells.csv")
for (cv, cell), g in m7.groupby(["cell_var", "cell"]):
    add(f"M7C-{cv}-{cell}", "Ccode population", f"{cv}={cell}", "retained", fmt({r.day: json.dumps({k: v for k, v in r.drop(["day", "cell_var", "cell"]).items() if not (isinstance(v, float) and pd.isna(v))}) for _, r in g.iterrows()}), unres="population not joined to Native", src="tables/m7_ccode_cells.csv", clock="t0 / t0+50 / seed known")
m8 = json.load(open(OUT / "m8_summary.json"))
for kind in ["candidate", "control1", "control2"]:
    for k in ["mid_next_5", "mid_next_20", "mid_next_20_given_more_adds_toward_2_5", "mid_next_20_given_more_adds_away_2_5", "mid_next_20_given_fills_toward_2_5", "mid_next_20_given_no_fills_toward_2_5", "mid_next_20_given_prior5_same_dir", "mid_next_20_given_prior5_opposite", "mid_next_20_given_prior5_flat"]:
        add(f"M8G-{kind}-{k}", "price->behavior->price (overlapping)", f"{k} ({kind})", "retained; see non-overlap rows", fmt({d["day"]: json.dumps(d[kind][k]) for d in m8}), src="tables/m8_summary.json", clock="second of change", end="5/20 s")
    for tag in ["s0", "s1", "s2_5", "s6_20"]:
        for act in ["add", "cancel", "fill", "trade", "modify"]:
            add(f"M8R-{kind}-{tag}-{act}", "price->behavior (response)", f"{act} toward vs away in {tag} ({kind})", "retained", fmt({d["day"]: json.dumps(d[kind][f"{tag}_{act}"]) for d in m8}), src="tables/m8_summary.json", clock="second of change", end=tag, lim="s0 mechanical")
m8n = json.load(open(OUT / "m8_feedback_nonoverlap.json")); m8s = json.load(open(OUT / "m8_feedback_s1_nonoverlap.json"))
for kind in ["candidate", "control1", "control2"]:
    for k, v in m8n[DAYS[0]][kind].items():
        if isinstance(v, dict): add(f"M8N-{kind}-{k}", "price->behavior->price (non-overlap +5..+20)", f"{k} ({kind})", interp([m8n[d][kind][k]["up"] for d in DAYS], [m8n[d][kind][k]["down"] for d in DAYS]), fmt({d: json.dumps(m8n[d][kind][k]) for d in DAYS}), src="tables/m8_feedback_nonoverlap.json", clock="+5 s", end="+20 s")
    for k in m8s[DAYS[0]][kind]:
        add(f"M8S-{kind}-{k}", "price->behavior->price (non-overlap +1..+20)", f"{k} ({kind})", interp([m8s[d][kind][k]["up"] for d in DAYS], [m8s[d][kind][k]["down"] for d in DAYS]), fmt({d: json.dumps(m8s[d][kind][k]) for d in DAYS}), src="tables/m8_feedback_s1_nonoverlap.json", clock="+1 s", end="+20 s")
pre = pd.read_csv(OUT / "m8b_prebirth_feature_lead.csv")
for (f, l), g in pre.groupby(["feature", "lead_s"]):
    add(f"M8B-prebirth-{f}-{int(l)}s", "family prebirth", f"Paired contrast of {f} at lead {int(l)} s", interp([int(r.greater) for _, r in g.iterrows()], [int(r.less) for _, r in g.iterrows()]), fmt({r.day: f"greater/equal/less {int(r.greater)}/{int(r.equal)}/{int(r.less)} of {int(r.defined)}" for _, r in g.iterrows()}), unres="C7", src="markets-data@7b50d63 prebirth-summary.csv", clock=f"start - {int(l)} s", end="paired contrast", lead=f"{int(l)} s")
pr = pd.read_csv(OUT / "m8b_primer_spread_events.csv")
for (reg, ts, h), g in pr.groupby(["regime", "touch_sign", "horizon"]):
    gg = g.groupby("day").agg(n=("n", "sum"), up=("up", "sum"), down=("down", "sum"), flat=("flat", "sum")).reset_index()
    add(f"M8B-primer-{reg}-{ts}-{h}", "primer", f"Next price after rest: {reg}, {ts}, {h}", interp([int(r.up) for _, r in gg.iterrows()], [int(r.down) for _, r in gg.iterrows()]), fmt({r.day: f"up/down/flat {int(r.up)}/{int(r.down)}/{int(r.flat)} of {int(r.n)}" for _, r in gg.iterrows()}), src="markets-data@7b50d63 primer-spread-event-summary.csv", clock="rest", end=str(h))
for (h, arm), g in pd.read_csv(OUT / "m8b_fourarm_direction.csv").groupby(["horizon_s", "arm"]):
    add(f"M8B-fourarm-{arm}-{int(h)}s", "model comparison", f"Ridge arm {arm} direction agreement at {int(h)} s", "retained", fmt({r.day: f"{int(r.dir_agree)}/{int(r.n_test)} = {r.dir_share}" for _, r in g.iterrows()}), src="markets-data@7b50d63 arm-metrics.csv", clock="cutoff", end=f"{int(h)} s")
for (h, coh), g in pd.read_csv(OUT / "m8b_cohort_outcomes.csv").groupby(["horizon_s", "cohort"]):
    add(f"M8B-cohort-{coh}-{int(h)}s", "family cohorts", f"Cohort {coh} at {int(h)} s", "retained", fmt({r.day: f"down/flat/up {int(r.down)}/{int(r.flat)}/{int(r.up)} of {int(r.n)}; median {r['median']}" for _, r in g.iterrows()}), src="markets-data@7b50d63 cohort-outcomes.csv", clock="cutoff", end=f"{int(h)} s")
m12 = json.load(open(OUT / "m12_dipole_exit.json")); fx = json.load(open(OUT / "m12_large_move_fixed_decision.json"))
for k in m12[DAYS[0]]["A_large_moves"]:
    add(f"M12A-{k}", "exit (survivorship-biased)", f"Large-move return when {k}", "retained with bias stated", fmt({d: json.dumps(m12[d]["A_large_moves"][k]) for d in DAYS}), unres="survivorship", src="tables/m12_dipole_exit.json", clock="any time before return", end="full return 600 s")
for T in ["decision_at_30s", "decision_at_60s", "decision_at_120s"]:
    for k, v in fx[DAYS[0]][T].items():
        if isinstance(v, dict): add(f"M12F-{T}-{k}", "exit (fixed decision)", f"Large-move return given {k} at {T}", "retained", fmt({d: json.dumps(fx[d][T][k]) for d in DAYS}), unres="small cells", src="tables/m12_large_move_fixed_decision.json", clock=T, end="full return 600 s")
for fs_ in m12[DAYS[0]]["B_hold_after_recognition_by_flow_state"]:
    add(f"M12B-{fs_}", "exit (hold vs exit at recognition)", f"Later move for a birth-direction position, flow state {fs_}", "retained", fmt({d: json.dumps(m12[d]["B_hold_after_recognition_by_flow_state"].get(fs_)) for d in DAYS}), src="tables/m12_dipole_exit.json", clock="recognition", end="60/300 s")

# M17 combined layers, M18 cross-layer joins, M19 external, M20 trade environment
m17 = json.load(open(OUT / "m17_combined_layers.json")); cells17 = pd.read_csv(OUT / "m17_layer_tertile_cells.csv")
cons = {(c["outcome"], c["layer"]): c["direction"] for c in m17["consistent_layers"]}
for (o, L), g in cells17.groupby(["outcome", "layer"]):
    parts = {}
    for d in DAYS:
        h = g[(g.tertile == "high") & (g.day == int(d))]; l = g[(g.tertile == "low") & (g.day == int(d))]
        if len(h) and len(l): parts[d] = f"high up/flat/down {int(h.up.iloc[0])}/{int(h.flat.iloc[0])}/{int(h.down.iloc[0])} n{int(h.n.iloc[0])} | low {int(l.up.iloc[0])}/{int(l.flat.iloc[0])}/{int(l.down.iloc[0])} n{int(l.n.iloc[0])}"
    add(f"M17-{o}-{L}", "combined layers at look-ahead clock (k=+5)", f"{L} tertiles vs {o}", (f"same high-vs-low direction on all four dates ({cons[(o, L)]:+d})" if (o, L) in cons else "not consistent across dates (retained)"), fmt(parts), "covered candidates", "", "", "tables/m17_layer_tertile_cells.csv", clock="k=+5 s", end=o)
for o, res in m17["leave_one_date_out"].items():
    add(f"M17-score-{o}", "combined layers (leave-one-date-out additive score)", f"Additive sign score of layers consistent on the three other dates vs {o}, held-out date", ("midpoint BEFORE the opposed print: top vs bottom separates on every held-out date, but this convention is not a realistic exit (M16b)" if o == "ride_exh" else ("realistic exit (end of exhaustion second): top leans up, bottom leans down on 3 of 4 dates; Oct 3 does not separate" if o == "ride_exh_end" else "weaker; retained")), fmt({d: json.dumps(res[d]["top_vs_bottom"]) + f" layers_used={res[d]['layers_used']}" for d in DAYS}), src="tables/m17_combined_layers.json", clock="k=+5 s", end=o, lim="rank-tertile score, not a fitted model")
m18 = json.load(open(OUT / "m18_cross_layer_joins.json"))
for key in ["by_dipole_state", "by_dipole_direction", "by_dipole_direction_recent", "by_fresh_flow_label", "by_touch_label", "by_gap_trend", "by_family_occurrence", "three_way_onset_flow_dipole"]:
    add(f"M18-{key}", "cross-layer join (thin touch x dipole x flow x family)", f"Size-one episode retreat share {key.replace('_', ' ')}", ("dipole state does not change thin-touch fate; fresh flow does" if "dipole" in key else "retained"), fmt({d: json.dumps(m18[d][key]) for d in DAYS}), src="tables/m18_cross_layer_joins.json", clock="onset known_by", end="episode ending")
m19 = json.load(open(OUT / "m19_external_summary.json"))
add("M19-external-within-session", "external context layers", "Do any of the 48 external series change within a session?", "see tables/m19_external_values_by_session.csv (daily/weekly cadence; context per day)", json.dumps(m19), src="tables/m19_external_values_by_session.csv", clock="publication known-by", end="n/a", lim="four sessions = four observations of each point")
m20 = json.load(open(OUT / "m20_trade_environment.json"))
for key in ["before_ratio20", "before_net_flow60", "before_birth", "before_prints60", "before_open_thin_episodes", "after_net_flow20", "after_net_flow60", "after_birth120", "after_prints60"]:
    add(f"M20-fade-{key}", "trade environment before/after (large-move fade)", f"Full return of the fade by {key.replace('_', ' ')}", ("post-move native flow continuing WITH the move marks failures on 3 of 4 dates" if key.startswith("after_net") else ("busy tape before the move: fast return on all 4 dates" if key == "before_prints60" else "retained")), fmt({d: json.dumps(m20["large_moves"][d][key]) for d in DAYS}), src="tables/m20_large_move_environment.csv", clock="move known_by (+20/+60 s for after)", end="full return 600 s")
for key in ["ride_by_prebirth_total_lots", "ride_by_after_flow", "ride_end_by_prebirth_total_lots", "ride_end_by_after_flow", "after_exhaustion_60s_against_share_of_lots", "after_exhaustion_60s_trades_vs_prebirth_26s"]:
    add(f"M20-ride-{key}", "trade environment before/after (dipole ride)", f"Dipole ride {key.replace('_', ' ')}", ("midpoint BEFORE the opposed print (superseded convention, M16b): quiet births appear to drive further on all four dates" if key == "ride_by_prebirth_total_lots" else ("realistic exit: quiet births MOVE more in both directions (fewer flat), no direction lean" if key == "ride_end_by_prebirth_total_lots" else "retained")), fmt({d: json.dumps(m20["dipole_rides"][d][key]) for d in DAYS}), src="tables/m20_trade_environment.json", clock="k=+5 s / exhaustion exit", end="ride to exhaustion")


# M23 raw MBO layers at the look-ahead clock and around large moves; M24 flip/successor and earliest-knowable population
try:
    m23 = json.load(open(OUT / "m23_raw_mbo_joins.json")); c23 = pd.read_csv(OUT / "m23_raw_layer_tertile_cells.csv")
    cons23 = {(c["outcome"], c["layer"]): c["direction"] for c in m23["consistent_raw_layers"]}
    for (o, L), g in c23.groupby(["outcome", "layer"]):
        parts = {}
        for d in DAYS:
            h = g[(g.tertile == "high") & (g.day == int(d))]; l = g[(g.tertile == "low") & (g.day == int(d))]
            if len(h) and len(l): parts[d] = f"high up/flat/down {int(h.up.iloc[0])}/{int(h.flat.iloc[0])}/{int(h.down.iloc[0])} n{int(h.n.iloc[0])} | low {int(l.up.iloc[0])}/{int(l.flat.iloc[0])}/{int(l.down.iloc[0])} n{int(l.n.iloc[0])}"
        add(f"M23-{o}-{L}", "raw MBO queue layer at look-ahead clock (k=+5)", f"{L} tertiles vs {o}", (f"same high-vs-low direction on all four dates ({cons23[(o, L)]:+d})" if (o, L) in cons23 else "not consistent across dates (retained)"), fmt(parts), "covered candidates", "", "", "tables/m23_raw_layer_tertile_cells.csv; markets-data@c01caaf raw MBO tapes", clock="k=+5 s (second-end book state) / -20..+5 sums", end=o)
    for o, res in m23["leave_one_date_out"].items():
        add(f"M23-score-{o}", "all layers together (derived + raw MBO), leave-one-date-out", f"Additive sign score over all consistent layers vs {o}, held-out date", "retained", fmt({d: json.dumps(res[d]) for d in DAYS}), src="tables/m23_raw_mbo_joins.json", clock="k=+5 s", end=o)
    e23 = json.load(open(OUT / "m23_large_move_raw_env.json"))
    for col in sorted({k for d in DAYS for k in e23.get(d, {})}):
        add(f"M23-fade-{col}", "raw MBO environment around large moves", f"Large-move full return by {col} (above vs at/below the date median)", "retained", fmt({d: json.dumps(e23[d][col]) for d in DAYS if col in e23.get(d, {})}), src="tables/m23_large_move_raw_env.csv", clock="second before the move / +1..+20 s", end="full return 600 s")
except FileNotFoundError:
    pass
try:
    m24 = json.load(open(OUT / "m24_flip_successor_and_peaks.json"))
    for k, v in m24.get("per_date", {}).get(DAYS[0], {}).items():
        add(f"M24-{k}", "look-ahead lifecycle (flip/successor; earliest-knowable population)", k.replace("_", " "), "retained", fmt({d: json.dumps(m24["per_date"][d].get(k)) for d in DAYS}), src="tables/m24_flip_successor_and_peaks.json", clock="completed second", end="see key")
except FileNotFoundError:
    pass
try:
    m16b = json.load(open(OUT / "m16b_exhaustion_convention_check.json"))
    NOTE16 = {"ride_to_exhaustion_before_opposed_print": "midpoint at the START of the exhaustion second (before the opposed print is known): up-leaning on all four dates; NOT a realistic exit",
              "ride_to_exhaustion_after_opposed_print": "midpoint at the END of the exhaustion second (realistic exit): symmetric on all four dates",
              "midpoint_change_inside_exhaustion_second": "the exhaustion second itself moves AGAINST the birth direction on all four dates (the opposed print takes the tick)",
              "after_exhaustion_60s_from_end_of_second": "symmetric on all four dates", "after_exhaustion_60s_from_start_of_second": "down-leaning on all four dates, but this includes the exhaustion second's own tick",
              "after_flip_60s_from_end_of_second": "symmetric on all four dates", "after_flip_60s_from_start_of_second": "down-leaning on all four dates, but this includes the flip second's own tick",
              "exit_rule_realistic": "exhaustion-end or 60 s: symmetric on all four dates", "k5_to_60_hold": "symmetric on all four dates"}
    for k in m16b[DAYS[0]]:
        add(f"M16B-{k}", "exhaustion CONVENTION check (look-ahead ride)", k.replace("_", " "), NOTE16.get(k, "retained"), fmt({d: json.dumps(m16b[d][k]) for d in DAYS}), src="tables/m16b_exhaustion_convention_check.json", clock="k=+5 s entry; mark second start vs end", end="see key", lim="oriented midpoint ticks from Ccode x13 life paths; four dates")
except FileNotFoundError:
    pass

with open(OUT.parent / "CLAIMS.csv") as fh: existing = list(csv.reader(fh))
PFX = ("LA-", "M16B-", "M23-", "M24-", "M17-", "M18-", "M19-", "M20-", "M1C-", "M14-", "M2C-", "M3C-", "M3D-", "M4C-", "T2-", "T2S-", "T2L-", "T2F-", "M6G-", "M6O-", "M7C-", "M8G-", "M8R-", "M8N-", "M8S-", "M8B-", "M12A-", "M12F-", "M12B-")
hand = [r for r in existing[1:] if r and not r[0].startswith(PFX)]
with open(OUT.parent / "CLAIMS.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(H); w.writerows(hand); w.writerows(rows)
print("hand-written", len(hand), "generated", len(rows), "total", len(hand) + len(rows))
