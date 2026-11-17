"""Patch m13_all_claims.py to add M17-M20 generated claim rows (combined layers, cross-layer joins, external layers, trade environment)."""
import pathlib
p = pathlib.Path(__file__).with_name("m13_all_claims.py"); s = p.read_text()
extra = '''
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
    add(f"M17-score-{o}", "combined layers (leave-one-date-out additive score)", f"Additive sign score of layers consistent on the three other dates vs {o}, held-out date", ("top vs bottom separates on every held-out date" if o == "ride_exh" else "weaker; retained"), fmt({d: json.dumps(res[d]["top_vs_bottom"]) + f" layers_used={res[d]['layers_used']}" for d in DAYS}), src="tables/m17_combined_layers.json", clock="k=+5 s", end=o, lim="rank-tertile score, not a fitted model")
m18 = json.load(open(OUT / "m18_cross_layer_joins.json"))
for key in ["by_dipole_state", "by_dipole_direction", "by_dipole_direction_recent", "by_fresh_flow_label", "by_touch_label", "by_gap_trend", "by_family_occurrence", "three_way_onset_flow_dipole"]:
    add(f"M18-{key}", "cross-layer join (thin touch x dipole x flow x family)", f"Size-one episode retreat share {key.replace('_', ' ')}", ("dipole state does not change thin-touch fate; fresh flow does" if "dipole" in key else "retained"), fmt({d: json.dumps(m18[d][key]) for d in DAYS}), src="tables/m18_cross_layer_joins.json", clock="onset known_by", end="episode ending")
m19 = json.load(open(OUT / "m19_external_summary.json"))
add("M19-external-within-session", "external context layers", "Do any of the 48 external series change within a session?", "see tables/m19_external_values_by_session.csv (daily/weekly cadence; context per day)", json.dumps(m19), src="tables/m19_external_values_by_session.csv", clock="publication known-by", end="n/a", lim="four sessions = four observations of each point")
m20 = json.load(open(OUT / "m20_trade_environment.json"))
for key in ["before_ratio20", "before_net_flow60", "before_birth", "before_prints60", "before_open_thin_episodes", "after_net_flow20", "after_net_flow60", "after_birth120", "after_prints60"]:
    add(f"M20-fade-{key}", "trade environment before/after (large-move fade)", f"Full return of the fade by {key.replace('_', ' ')}", ("post-move native flow continuing WITH the move marks failures on 3 of 4 dates" if key.startswith("after_net") else ("busy tape before the move: fast return on all 4 dates" if key == "before_prints60" else "retained")), fmt({d: json.dumps(m20["large_moves"][d][key]) for d in DAYS}), src="tables/m20_large_move_environment.csv", clock="move known_by (+20/+60 s for after)", end="full return 600 s")
for key in ["ride_by_prebirth_total_lots", "ride_by_after_flow", "after_exhaustion_60s_against_share_of_lots", "after_exhaustion_60s_trades_vs_prebirth_26s"]:
    add(f"M20-ride-{key}", "trade environment before/after (dipole ride)", f"Dipole ride {key.replace('_', ' ')}", ("quiet births (low prebirth lots) drive further on all four dates" if key == "ride_by_prebirth_total_lots" else "retained"), fmt({d: json.dumps(m20["dipole_rides"][d][key]) for d in DAYS}), src="tables/m20_trade_environment.json", clock="k=+5 s / exhaustion exit", end="ride to exhaustion")
'''
marker = 'with open(OUT.parent / "CLAIMS.csv") as fh: existing'
assert marker in s and "M17-" not in s
s = s.replace(marker, extra + "\n" + marker, 1).replace('PFX = ("LA-",', 'PFX = ("LA-", "M17-", "M18-", "M19-", "M20-",')
p.write_text(s); print("patched")
