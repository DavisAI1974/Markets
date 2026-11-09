"""x20: the frozen receipt of Claude Code's final three-day suite, for the shared reanalysis brief (agent-pass/reanalysis/SHARED_BRIEF.md, item 3 and item 5).
Usage: python3 -I x20_final_suite_receipt.py <Markets three-day worktree> <Markets codex worktree> <markets-data clone> <three-day base> <codex base> <markets-data base>
Writes CCODE_FINAL_SUITE_RECEIPT.json and .md beside this script: every file added or changed since the named base commits in the three repositories, with
measured bytes and sha256 at the named head commits; the per-session run receipts, population and row counts; the clocks each timed file carries; the
Oct 18 reference tables and the replication statement; limitations. Nothing is recomputed from data here; the receipt reads committed files only."""
import sys, os, json, hashlib, subprocess, csv
from pathlib import Path
W3, WC, MD, B3, BC, BM = sys.argv[1:7]; HERE = Path(__file__).resolve().parent
def sh(cmd, cwd): return subprocess.check_output(cmd, cwd=cwd, text=True).strip()
def files_since(repo, base):
    head = sh(["git", "rev-parse", "HEAD"], repo); rows = []
    for line in sh(["git", "diff", "--name-status", f"{base}..HEAD"], repo).splitlines():
        parts = line.split("\t"); status, path = parts[0][0], parts[-1]
        if status == "D": rows.append(dict(path=path, status="deleted", bytes=None, sha256=None)); continue
        b = (Path(repo) / path).read_bytes(); rows.append(dict(path=path, status={"A": "added", "M": "modified", "R": "renamed"}.get(status, status), bytes=len(b), sha256=hashlib.sha256(b).hexdigest()))
    return head, rows
def rd(p): return json.loads(Path(p).read_text())
def csv_rows(p): return sum(1 for _ in open(p)) - 1
h3, f3 = files_since(W3, B3); hc, fc = files_since(WC, BC); hm, fm = files_since(MD, BM)
P3 = Path(W3) / "tasks/family-research-20261022/claude-pass-3day"; PC = Path(WC) / "tasks/family-research-20261022"
S = ["20231002", "20231003", "20231017", "20231018"]
sessions = {}
for d in S:
    r = rd(P3 / f"tables/{d}/t1_receipt.json")
    sessions[d] = dict(members=r["members"], family_index=dict(path=r["family_index"].split("/scratchpad/")[-1] if "scratchpad" in r["family_index"] else r["family_index"], markets_data_commit="7b50d634", sha256=r["family_index_sha256"], run="42566535537"),
                       families_in_index=r["families"], families_used=r["families_used"], excluded=r["excluded_no_earlier_group"], in_member_with_60s_records=r["in_member"], cutoff_rule=r["cutoff_rule"],
                       session_groups=r["groups"], reconcile_60s_aggressor_lots=dict(buy=r["reconcile_buy_60s"], sell=r["reconcile_sell_60s"], of=r["of_in_member"]), censored_outcomes=r["censored_per_horizon"],
                       refill_sets=r["refill"], t1_tables={f: csv_rows(P3 / f"tables/{d}/{f}") for f in sorted(os.listdir(P3 / f"tables/{d}")) if f.startswith("t1_") and f.endswith(".csv")},
                       t2_tables={f: csv_rows(P3 / f"tables/{d}/{f}") for f in sorted(os.listdir(P3 / f"tables/{d}")) if f.startswith("t2_") and f.endswith(".csv")})
crossday = {f: csv_rows(P3 / "crossday" / f) for f in sorted(os.listdir(P3 / "crossday")) if (f.startswith("t2x_") or f.startswith("t1x_")) and f.endswith(".csv")}
pairs_full = {f: csv_rows(P3 / "crossday/pairs_full" / f) for f in sorted(os.listdir(P3 / "crossday/pairs_full"))}
charts = list(csv.DictReader(open(P3 / "crossday/t2x_chart_reconciliation.csv"))); pins = rd(Path(MD) / "tasks/family-research-20261022/claude-code-pins/ninety-nine-pins-tier1-summary.json")
receipt = dict(
    analyst="Claude Code (Ccode)", written="2026-11-09", brief="agent-pass/reanalysis/SHARED_BRIEF.md at da0e2fc27350e791366eafa974e2bdb85e99460b, items 3 and 5",
    repositories=dict(
        three_day_suite=dict(repository="DavisAI1974/Markets", branch="claude/three-day-dipole-20261108", base_commit=B3, head_commit=h3, folder="tasks/family-research-20261022/claude-pass-3day/", files_changed_or_added=f3),
        discovery_record=dict(repository="DavisAI1974/Markets", branch="codex/ng-shadow-discovery-20261108", base_commit=BC, head_commit=hc, files_changed_or_added=fc),
        data=dict(repository="DavisAI1974/markets-data", branch="main", base_commit=BM, head_commit=hm, files_changed_or_added=fm)),
    what_the_suite_is=dict(
        tier2_side_by_side="x14_tier2_crossday.py over the committed tables/<UTC member>/t2_*.csv (c14, c15, c16, c17, c18; same code on the four members); x16_tier2_shift_draws.py saves the c14 shifted-Y draws (seed 11, 20 of 300 shifts) for the day-by-day reference; x17_pair_couplings_full.py keeps every (x1, x2, y) of the c15 family; x15_tier2_crossday_charts.py draws seven figures with every plotted count asserted equal to its table rows. Write-up FINDINGS_TIER2_CROSSDAY_20261109.md.",
        tier1_on_actual_family_starts="x18_tier1_days.py runs the Oct 18 Tier 1 chain (c02 outcomes, c06 family master with order-level windows, c07 cells and stack variants, c08 depth and corners, c10 refill at the side being hit, c11 four arms) unchanged in method on the per-date first-observed family index; x19_tier1_crossday.py puts the four sessions side by side. Write-up FINDINGS_TIER1_CROSSDAY_20261109.md. The Oct 18-only matched-50 pass (c09) is not run.",
        grids="rebuilt in-session from the manifest-pinned tapes (c00 -> c03 -> c01b -> c12, unchanged code); every committed Tier 2 table reproduces (lead-lag, state cells, forward stack byte-identical; coupling rho to 1.1e-16 with identical n, chunks and line flags); the Tier 1 chain on Oct 18 reproduces every committed claude-pass/tables/t1_*.csv value for value."),
    populations_by_session=sessions,
    tier2_inputs=dict(grid_rows_after_closed_market_rows_out={"20231002": 26980, "20231003": 26980, "20231017": 26979, "20231018": 26980}, condition_outcome_pairs=2669, lead_lag_pairs=49, state_cells=42, pair_coupling_rows_full={"20231002": 5406, "20231003": 5418, "20231017": 5166, "20231018": 5166}),
    crossday_tables=crossday, pairs_full_tables=pairs_full, chart_reconciliation=dict(figures=len({c["figure"] for c in charts}), panels=len(charts), all_match=all(c["match"] == "True" for c in charts)),
    oct18_reference=dict(
        original_tier1="claude-pass/tables/t1_*.csv (12 files; 749 families; the matched-50 pass included); reproduced value for value by x18 on the rebuilt grids",
        original_tier2="claude-pass/tables/t2_*.csv and tables/20231018_legacy/ (legacy mode: retained export groups, no closed-market exclusion, age_s and qage_s out of X; 2,635 pairs, 44 cells); the dense run used for the four-day comparison is tables/20231018/t2_*.csv (2,669 pairs, 42 cells); the reason is recorded in FINDINGS_TIER2_CROSSDAY_20261109.md section 1",
        regime_comparison="claude-pass/tables/crossday/t4_*.csv (c19 to c23) already covered the four days and is unchanged",
        dipole_cohort="claude-pass-3day/tables/dipole/<session>/t6_* and FINDINGS_THREE_DAYS_20261108.md (Desktop's pass), unchanged"),
    clocks=dict(
        tier1_family_master=["start_recv_ns (family start receive clock, ns)", "cutoff_ns = start_recv_ns - 1 ns (strict decision boundary; the Oct 18 ledger's own rule, 749 of 749)", "ref_recv_ns (receive clock of the last group known by the cutoff: the reference midpoint and touch)", "start_utc (ISO)", "outcomes at start + h for h in 1, 5, 20, 60, 120, 300, 600 s from the last group known by then; grp_<h>s = -1 and chg NaN where the horizon passes the 21:00 UTC close", "order-level windows end at cutoff (start - 1 ns) over the previous 1, 5, 20, 60 s; NaN where the window begins before the date member"],
        tier1_pin_ledgers="every record carries start, cutoff and reference-group clocks as ns and UTC; pins carry known_by_cutoff_ns, known_by_receive_ns (reference group) or outcome_window_start_plus_<h>s",
        tier2_tables="per UTC member; decisions every 3 s with features as of the cutoff and outcomes after it (c12); one-second series by receive second (c16, c17); closed-market rows and seconds left out (odcfg.closed_mask); the cross-day tables are aggregates with no clock of their own",
        session_scope="session groups = prior member from 21:00 UTC to the date member's 21:00 UTC close; Oct 2 and Oct 17 are partial from the UTC snapshot (their family indexes begin at 00:00 UTC), Oct 3 and Oct 18 full sessions"),
    time_sensitive_new_files=dict(
        per_event_rows=[f"tasks/family-research-20261022/claude-pass-3day/tables/{d}/t1_family_master.csv" for d in S] + [f"tasks/family-research-20261022/claude-pass-3day/tables/{d}/t1_family_master_flags.csv" for d in S],
        pinned_as=[f"tasks/family-research-20261022/claude-code-pins/ninety-nine-pins-tier1-{t}.jsonl.gz" for t in ("oct02", "oct03", "oct17", "oct18")], pin_summary=pins["sessions"], registry_sha256_declared=pins["registry_sha256"],
        aggregates_without_clock="crossday/t2x_*.csv, crossday/t1x_*.csv, crossday/pairs_full/*.csv, tables/<session>/t1_cells*, t1_stack_variants, t1_corners*, t1_oriented*, t1_refill*, t1_fourarm* (summaries over the pinned rows; not pinned)"),
    limitations=[
        "Each day is one session of one instrument; nothing is pooled across days; counts of days are counts.",
        "The Tier 2 cross-day reference distribution is 20 shifted-Y draws per day combined day by day; the regime comparison used the same count.",
        "Pair couplings beyond the line are rare by construction (family-wise line over 40 shifts on every third pair, as c15 defined it).",
        "Tier 1 order-level windows exist only for families inside the date member with a full window; the 60 s aggressor-lot reconciliation to the retained ROOT operands is 744/752, 749/742, 770/774, 654/656 of 781, 796, 809, 694 (the rest differ by the unknown-side lots the retained operands count differently; not examined further).",
        "The session groups come from the rebuilt tapes, not the retained exports; on Oct 18 they reproduce the export-based tables exactly (583,688 groups).",
        "Oct 2 and Oct 17 family indexes begin at the UTC snapshot; the prior evening of those sessions is in the group arrays (from the prefix members) but no family start of theirs falls in it.",
        "No trade cost, fee, slippage or execution assumption anywhere; these are discovery readouts on already-studied days, not out-of-sample validation."],
    not_done_by_direction=["agreement/disagreement pass against the Codex and Desktop passes", "the 99 and 13 crosswalk (Codex reconciles; one copy)", "detector reverse-engineering (Desktop's 3C)", "c13 and c14_deseason variants (superseded by c14 and c19)", "Desktop's 3D issue-13 follow-up (drafted, unposted)"])
(HERE / "CCODE_FINAL_SUITE_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
md = ["# Claude Code final three-day suite: frozen receipt (2026-11-09)", "", f"For `{receipt['brief']}`. Machine-readable twin: `CCODE_FINAL_SUITE_RECEIPT.json` (same folder). Written by `x20_final_suite_receipt.py` from committed files only.", "",
      "## Where", ""]
for k, v in receipt["repositories"].items():
    md.append(f"- **{k}**: `{v['repository']}`, branch `{v['branch']}`, base `{v['base_commit'][:7]}` -> head `{v['head_commit'][:7]}`" + (f", folder `{v['folder']}`" if v.get("folder") else "") + f"; {len(v['files_changed_or_added'])} files changed or added (listed with bytes and sha256 in the JSON).")
md += ["", "## Populations and run receipts", "", "| session | families in index / used / excluded | inside member with 60 s records | session groups (first to last) | censored 300 s / 600 s | 60 s lots equal to retained operands buy / sell / of |", "| --- | --- | --- | --- | --- | --- |"]
for d, s in sessions.items():
    md.append(f"| {d} | {s['families_in_index']} / {s['families_used']} / {s['excluded']['count']} | {s['in_member_with_60s_records']} | {s['session_groups']['total']:,} ({s['session_groups']['first_recv_utc'][:16]} to {s['session_groups']['last_recv_utc'][:16]}) | {s['censored_outcomes']['300']} / {s['censored_outcomes']['600']} | {s['reconcile_60s_aggressor_lots']['buy']} / {s['reconcile_60s_aggressor_lots']['sell']} / {s['reconcile_60s_aggressor_lots']['of']} |")
md += ["", "Tier 2 grid rows after closed-market rows out: 26,980 / 26,980 / 26,979 / 26,980; 2,669 condition/outcome pairs, 49 lead-lag pairs, 42 state cells per member; full pair-coupling rows 5,406 / 5,418 / 5,166 / 5,166.", "",
       f"Chart reconciliation: {receipt['chart_reconciliation']['panels']} panels over {receipt['chart_reconciliation']['figures']} figures, all plotted counts equal to table rows: {receipt['chart_reconciliation']['all_match']}.", "",
       "## Oct 18 reference", ""] + [f"- {v}" for v in receipt["oct18_reference"].values()] + ["", "## Clocks", ""] + [f"- **{k}**: " + ("; ".join(v) if isinstance(v, list) else v) for k, v in receipt["clocks"].items()] + ["", "## Time-sensitive new files (brief item 5)", "",
       "Per-event rows: the eight Tier 1 family masters (one row per family start). Pinned to the 99-layer registry as the four `ninety-nine-pins-tier1-<tag>.jsonl.gz` ledgers in markets-data (" + ", ".join(f"{t}: {v['rows']} rows, {v['pins']} pins" for t, v in pins["sessions"].items()) + f"); declared registry file sha256 `{pins['registry_sha256']}`. Everything else new is an aggregate over those rows or over the Tier 2 grids and carries no clock of its own.", "",
       "## Limitations", ""] + [f"- {l}" for l in receipt["limitations"]] + ["", "## Not done, by direction", ""] + [f"- {l}" for l in receipt["not_done_by_direction"]] + [""]
(HERE / "CCODE_FINAL_SUITE_RECEIPT.md").write_text("\n".join(md)); print("receipt written; files:", {k: len(v["files_changed_or_added"]) for k, v in receipt["repositories"].items()})
