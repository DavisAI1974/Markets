"""
_regenerate_audit_summary.py (S31 DATAFIX) — regenerate the hindsight-audit aggregate
summary (.json + .md) from the CORRECTED rows CSV, so the summaries stop reporting the
clamped-oracle numbers.

The original summary generator is not in the repo, so the aggregation rules were recovered
from the original CSV + original .json and are proven by `--validate` (recompute from the
ORIGINAL CSV must reproduce the original .json's oracle-dependent fields exactly).

Oracle-INDEPENDENT fields (actual closed trades, run config) are CARRIED OVER verbatim
from the original .json — they do not change under the oracle fix and the global
`closed_actual_realized_pnl_usd` is sourced from the trade log (not fully in the CSV):
  inputs.*, pnl.closed_actual_realized_pnl_usd, pace.closed_actual_weekly_pace_usd,
  by_pattern_family[].promotion_state (original promotion logic; rule not in repo).
Oracle-DEPENDENT fields are recomputed from the supplied CSV.

Recovered rules (all validated):
  - oracle winner row  = is_oracle_winner_after_fees == True
  - miss_type          = winner&opened -> exit_missed_or_fee_leak; winner&skipped -> missed_entry; else not_a_hindsight_winner
  - captured_net_win   = opened & winner & actual_realized > 0
  - opened_pending     = opened & actual_trade_status != 'closed'
  - by_* tables        = over WINNER rows only; per group: rows, unique(distinct unique_key),
                         missed_entry_rows, opened_rows(decision==opened),
                         oracle_net_pnl_usd (sum), actual_realized_pnl_usd (sum),
                         oracle_incremental = oracle_net - actual; context/trait capped top 25 by pnl.

Usage:
  python _regenerate_audit_summary.py --validate   # prove rules reproduce original .json
  python _regenerate_audit_summary.py              # write .corrected.json + .corrected.md
"""
from __future__ import annotations
import csv, json, os, sys
from collections import defaultdict

D = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "research", "strategy_evolution", "live_mock_replay")
ORIG_JSON = os.path.join(D, "live_hindsight_missed_winner_audit.json")
ORIG_CSV = os.path.join(D, "live_hindsight_missed_winner_audit_rows.csv")
CORR_CSV = os.path.join(D, "live_hindsight_missed_winner_audit_rows.corrected.csv")
OUT_JSON = os.path.join(D, "live_hindsight_missed_winner_audit.corrected.json")
OUT_MD = os.path.join(D, "live_hindsight_missed_winner_audit.corrected.md")


def F(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def load(csv_path):
    return list(csv.DictReader(open(csv_path, newline="")))


def by_key(win, key, limit=None, extra_map=None, extra_name=None):
    g = defaultdict(list)
    for r in win:
        k = r.get(key, "")
        g[k].append(r)
    out = []
    for k, rs in g.items():
        onet = sum(F(r["oracle_net_pnl_usd"]) for r in rs)
        act = sum(F(r["actual_realized_pnl_usd"]) for r in rs)
        d = {
            key: k,
            "rows": len(rs),
            "unique": len({r["unique_key"] for r in rs}),
            "missed_entry_rows": sum(1 for r in rs if r["miss_type"] == "missed_entry"),
            "opened_rows": sum(1 for r in rs if r["decision"] == "opened"),
            "oracle_net_pnl_usd": round(onet, 6),
            "actual_realized_pnl_usd": round(act, 6),
            "oracle_incremental_vs_actual_usd": round(onet - act, 6),
        }
        if extra_map is not None:
            d[extra_name] = extra_map.get(k)
        out.append(d)
    out.sort(key=lambda x: x["oracle_net_pnl_usd"], reverse=True)
    return out[:limit] if limit else out


def compute(rows, carry):
    """Compute the full summary dict from rows; carry = original .json for carry-over fields."""
    win = [r for r in rows if r["is_oracle_winner_after_fees"] == "True"]
    opened = [r for r in rows if r["decision"] == "opened"]
    missed = [r for r in rows if r["miss_type"] == "missed_entry"]
    opened_win = [r for r in opened if r["is_oracle_winner_after_fees"] == "True"]
    ts = [F(r["ts_utc"]) for r in rows]
    elapsed = (max(ts) - min(ts)) / 86400 if ts else 0.0

    closed_actual = carry["pnl"]["closed_actual_realized_pnl_usd"]  # oracle-independent carry-over
    owin_net = round(sum(F(r["oracle_net_pnl_usd"]) for r in win), 8)
    missed_net = round(sum(F(r["oracle_net_pnl_usd"]) for r in missed), 8)
    openedwin_net = round(sum(F(r["oracle_net_pnl_usd"]) for r in opened_win), 8)
    incr = round(owin_net - closed_actual, 8)

    counts = {
        "opportunity_rows": len(rows),
        "audited_rows": len(rows),
        "pending_or_unmatched_rows": carry["counts"]["pending_or_unmatched_rows"],
        "oracle_winner_rows_after_fees": len(win),
        "oracle_winner_unique_after_fees": len({r["unique_key"] for r in win}),
        "missed_entry_rows": len(missed),
        "missed_entry_unique": len({r["unique_key"] for r in missed}),
        "opened_oracle_winner_rows": len(opened_win),
        "captured_net_win_rows": sum(1 for r in opened_win if F(r["actual_realized_pnl_usd"]) > 0),
        "exit_missed_or_fee_leak_rows": sum(1 for r in rows if r["miss_type"] == "exit_missed_or_fee_leak"),
        "opened_pending_rows": sum(1 for r in opened if r["actual_trade_status"] != "closed"),
    }
    pnl = {
        "closed_actual_realized_pnl_usd": closed_actual,
        "oracle_winner_net_pnl_usd": owin_net,
        "missed_entry_oracle_net_pnl_usd": missed_net,
        "opened_oracle_winner_net_pnl_usd": openedwin_net,
        "oracle_incremental_vs_closed_actual_usd": incr,
    }
    wk = lambda v: round(v / elapsed * 7, 2) if elapsed else 0.0
    pace = {
        "audited_elapsed_days": round(elapsed, 6),
        "closed_actual_weekly_pace_usd": carry["pace"]["closed_actual_weekly_pace_usd"],
        "oracle_winner_weekly_pace_usd": wk(owin_net),
        "missed_entry_oracle_weekly_pace_usd": wk(missed_net),
    }
    fam_prom = {e["pattern_family"]: e.get("promotion_state") for e in carry["by_pattern_family"]}
    by_miss = defaultdict(int)
    for r in rows:
        if r["miss_type"] in ("missed_entry", "exit_missed_or_fee_leak"):
            by_miss[r["miss_type"]] += 1
    return {
        "schema": "live_hindsight_missed_winner_audit_v1_corrected",
        "corrected_from": "live_hindsight_missed_winner_audit_rows.corrected.csv",
        "note": ("oracle-dependent fields recomputed from the corrected (per-row ts_utc, true-horizon) "
                 "rows; oracle-independent fields (closed actual PnL/pace, inputs, pattern_family "
                 "promotion_state) carried over from the original 05-28 summary. "
                 "captured_net_win_rows is a SUBSET of opened oracle winners (those whose actual trade "
                 "ended positive), not a separate partition; exit_missed_or_fee_leak_rows counts ALL "
                 "opened oracle winners (the recovered miss_type rule; original had 0 captured so the two "
                 "coincided). 'true' exit leaks = exit_missed_or_fee_leak - captured_net_win. See "
                 "HINDSIGHT_AUDIT_ORACLE_FIX_2026-06-21.md."),
        "created_from_original": carry.get("created_at"),
        "inputs": carry["inputs"],
        "counts": counts, "pnl": pnl, "pace": pace,
        "by_miss_type": dict(by_miss),
        "by_blocker": by_key(win, "blocker_reason"),
        "by_context": by_key(win, "context_key", limit=25),
        "by_trait": by_key(win, "trait_key", limit=25),
        "by_move_shape": by_key(win, "move_shape_category"),
        "by_pattern_family": by_key(win, "pattern_family", extra_map=fam_prom, extra_name="promotion_state"),
        "by_strategy": by_key(win, "strategy_id"),
    }


def validate():
    carry = json.load(open(ORIG_JSON))
    got = compute(load(ORIG_CSV), carry)
    fails = []

    def chk(path, a, b, tol=0.01):
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            if abs(a - b) > tol:
                fails.append(f"{path}: got {a} != orig {b}")
        elif a != b:
            fails.append(f"{path}: got {a!r} != orig {b!r}")

    for k, v in got["counts"].items():
        chk("counts." + k, v, carry["counts"][k])
    for k, v in got["pnl"].items():
        chk("pnl." + k, v, carry["pnl"][k], tol=0.05)
    for k in ("audited_elapsed_days", "oracle_winner_weekly_pace_usd", "missed_entry_oracle_weekly_pace_usd"):
        chk("pace." + k, got["pace"][k], carry["pace"][k], tol=1.0)
    for sec, key in (("by_blocker", "blocker_reason"), ("by_move_shape", "move_shape_category"),
                     ("by_pattern_family", "pattern_family"), ("by_strategy", "strategy_id"),
                     ("by_context", "context_key"), ("by_trait", "trait_key")):
        go = {e[key]: e for e in got[sec]}
        oo = {e[key]: e for e in carry[sec]}
        if set(go) != set(oo):
            fails.append(f"{sec}: key set differs (got {len(go)} vs orig {len(oo)}); "
                         f"only_got={list(set(go)-set(oo))[:3]} only_orig={list(set(oo)-set(go))[:3]}")
        for k in set(go) & set(oo):
            for f in ("rows", "unique", "missed_entry_rows", "opened_rows"):
                chk(f"{sec}[{k}].{f}", go[k][f], oo[k][f])
            for f in ("oracle_net_pnl_usd", "actual_realized_pnl_usd", "oracle_incremental_vs_actual_usd"):
                chk(f"{sec}[{k}].{f}", go[k][f], oo[k][f], tol=0.05)

    if fails:
        print(f"VALIDATION FAILED ({len(fails)} mismatches):")
        for f in fails[:40]:
            print("  ", f)
        return 1
    print("VALIDATION PASSED — recompute reproduces the original .json oracle-dependent fields exactly.")
    return 0


def render_md(s):
    L = []
    a = L.append
    a("# Live Hindsight Missed Winner Audit (CORRECTED)\n")
    a(f"Regenerated from `{s['corrected_from']}` (oracle fix 2026-06-21). "
      f"Oracle-independent fields carried from the original 05-28 run.\n")
    c, p, pc = s["counts"], s["pnl"], s["pace"]
    a("## Counts\n")
    a(f"- Audited opportunity rows: {c['audited_rows']}")
    a(f"- Oracle winner rows after fees: {c['oracle_winner_rows_after_fees']}")
    a(f"- Missed entry rows: {c['missed_entry_rows']}")
    a(f"- Opened oracle winner rows: {c['opened_oracle_winner_rows']}")
    a(f"- Captured net win rows: {c['captured_net_win_rows']} (subset of opened oracle winners whose actual trade ended positive)")
    a(f"- Exit missed / fee leak rows: {c['exit_missed_or_fee_leak_rows']} (all opened oracle winners; 'true' leaks = {c['exit_missed_or_fee_leak_rows'] - c['captured_net_win_rows']})")
    a(f"- Opened pending rows: {c['opened_pending_rows']}\n")
    a("## PnL Ceiling\n")
    a(f"- Closed actual realized PnL: ${p['closed_actual_realized_pnl_usd']:.8f}")
    a(f"- Oracle winner net PnL: ${p['oracle_winner_net_pnl_usd']:.8f}")
    a(f"- Missed entry oracle net PnL: ${p['missed_entry_oracle_net_pnl_usd']:.8f}")
    a(f"- Opened oracle winner net PnL: ${p['opened_oracle_winner_net_pnl_usd']:.8f}")
    a(f"- Oracle incremental vs closed actual: ${p['oracle_incremental_vs_closed_actual_usd']:.8f}\n")
    a("## Pace\n")
    a(f"- Audited elapsed days: {pc['audited_elapsed_days']:.6f}")
    a(f"- Closed actual weekly pace: ${pc['closed_actual_weekly_pace_usd']:.2f}")
    a(f"- Oracle winner weekly pace: ${pc['oracle_winner_weekly_pace_usd']:.2f}")
    a(f"- Missed entry oracle weekly pace: ${pc['missed_entry_oracle_weekly_pace_usd']:.2f}\n")
    a("## Miss Types\n")
    for k, v in s["by_miss_type"].items():
        a(f"- `{k}`: {v}")
    a("")

    def tbl(title, sec, keyname, label, extra=None):
        a(f"## {title}\n")
        hdr = f"| {label} |" + (" State |" if extra else "") + " Rows | Missed entries | Oracle PnL | Incremental |"
        sep = "|---|" + ("---|" if extra else "") + "---:|---:|---:|---:|"
        a(hdr)
        a(sep)
        for e in sec:
            st = f" `{e.get(extra)}` |" if extra else ""
            a(f"| `{e[keyname]}` |{st} {e['rows']} | {e['missed_entry_rows']} | "
              f"${e['oracle_net_pnl_usd']:.6f} | ${e['oracle_incremental_vs_actual_usd']:.6f} |")
        a("")

    tbl("Top Blockers", s["by_blocker"], "blocker_reason", "Blocker")
    tbl("Top Contexts", s["by_context"], "context_key", "Context")
    tbl("Oracle Pattern Families", s["by_pattern_family"], "pattern_family", "Family", extra="promotion_state")
    tbl("Oracle Move Shapes", s["by_move_shape"], "move_shape_category", "Move shape")
    return "\n".join(L) + "\n"


def main():
    if "--validate" in sys.argv:
        return validate()
    carry = json.load(open(ORIG_JSON))
    rc = validate()
    if rc != 0:
        print("Refusing to write corrected summary: validation failed.")
        return rc
    s = compute(load(CORR_CSV), carry)
    json.dump(s, open(OUT_JSON, "w"), indent=2)
    open(OUT_MD, "w").write(render_md(s))
    print(f"\nwrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    print(f"oracle winners: {s['counts']['oracle_winner_rows_after_fees']} "
          f"(was {carry['counts']['oracle_winner_rows_after_fees']})   "
          f"oracle winner net PnL: ${s['pnl']['oracle_winner_net_pnl_usd']:.2f} "
          f"(was ${carry['pnl']['oracle_winner_net_pnl_usd']:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
