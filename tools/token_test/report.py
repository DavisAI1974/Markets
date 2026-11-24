"""8c. The report: one table with every call by every arm, and two charts.

Input: the per-call lines `replay go` wrote (JSON lines, one per call and arm, in the order sent = the
receipts' order). Output, in a folder the caller names (a markets-data checkout; never inside Markets):
  token-test-table.csv / .jsonl   one row for each call and arm, nothing folded
  token-test-tokens-per-call.png   tokens of each call, one line for each arm
  token-test-tokens-cumulative.png the running sum of each arm's OWN calls through the trade day, in the
                                   receipts' order (the plan asks for it by name; not an average, nothing ranked)
  token-test-report-receipt.json   the row count of the table and the points plotted for each arm, and the check
The row count of the table must equal the number of points plotted for each arm; if not, it raises and writes
NOTHING. With no per-call line there is nothing to plot: it says so and writes nothing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

TOKEN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
COLUMNS = ("arm", "position", "call_id", "conversation_id", "purpose", "model_asked", "model_served", "batch",
           *TOKEN_FIELDS, "total_tokens", "cumulative_tokens", "wall_clock_s", "cost_usd", "stop_reason",
           "output", "granite_output")


class ReportMismatch(RuntimeError):
    pass


def read_lines(paths) -> list[dict]:
    out = []
    for p in ([paths] if isinstance(paths, (str, Path)) else paths):
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def build_rows(lines: list[dict]) -> list[dict]:
    rows, pos, cum = [], {}, {}
    for l in lines:
        a = l["arm"]
        tot = sum(int(l.get(k) or 0) for k in TOKEN_FIELDS)
        pos[a] = pos.get(a, 0) + 1
        cum[a] = cum.get(a, 0) + tot
        rows.append({"arm": a, "position": pos[a], "call_id": l["call_id"], "conversation_id": l.get("conversation_id"),
                     "purpose": l.get("purpose"), "model_asked": l.get("model_asked"), "model_served": l.get("model_served"),
                     "batch": l.get("batch"), **{k: int(l.get(k) or 0) for k in TOKEN_FIELDS},
                     "total_tokens": tot, "cumulative_tokens": cum[a], "wall_clock_s": l.get("wall_clock_s"),
                     "cost_usd": (l.get("cost") or {}).get("total"), "stop_reason": l.get("stop_reason"),
                     "output": l.get("output"), "granite_output": l.get("granite_output")})
    return rows


def _figures(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    arms = sorted({r["arm"] for r in rows})
    figs, plotted = {}, {"per_call": {}, "cumulative": {}}
    for key, field, title in (("per_call", "total_tokens", "Tokens of each call, by arm"),
                              ("cumulative", "cumulative_tokens", "Tokens added up through the trade day, by arm (own calls, receipts' order)")):
        fig, ax = plt.subplots(figsize=(11, 5))
        for a in arms:
            mine = [r for r in rows if r["arm"] == a]
            (line,) = ax.plot([r["position"] for r in mine], [r[field] for r in mine], marker="o", ms=3, label=f"arm {a}")
            plotted[key][a] = len(line.get_xdata())
        ax.set_xlabel("call, in the receipts' order (position among the arm's own calls)")
        ax.set_ylabel("tokens (input + cache write + cache read + output)")
        ax.set_title(title)
        ax.legend()
        figs[key] = fig
    return figs, plotted


def report(lines: list[dict], out_dir) -> dict:
    if not lines:
        return {"written": False, "reason": "no per-call line: nothing to plot, nothing written"}
    rows = build_rows(lines)
    figs, plotted = _figures(rows)
    counts = {a: sum(1 for r in rows if r["arm"] == a) for a in plotted["per_call"]}
    bad = {k: {a: (counts[a], n) for a, n in v.items() if n != counts[a]} for k, v in plotted.items()}
    if any(bad.values()) or sum(counts.values()) != len(rows):
        raise ReportMismatch(f"rows in the table differ from points plotted (rows, points): {bad}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "token-test-table.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with (out / "token-test-table.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    figs["per_call"].savefig(out / "token-test-tokens-per-call.png", dpi=110)
    figs["cumulative"].savefig(out / "token-test-tokens-cumulative.png", dpi=110)
    receipt = {"schema": "markets.token_test.report.v1", "table_rows": len(rows), "rows_per_arm": counts,
               "points_plotted_per_arm": plotted, "rows_equal_points": True,
               "files": {n: hashlib.sha256((out / n).read_bytes()).hexdigest() for n in
                         ("token-test-table.csv", "token-test-table.jsonl", "token-test-tokens-per-call.png",
                          "token-test-tokens-cumulative.png")}}
    (out / "token-test-report-receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
    return dict(receipt, written=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tools.token_test.report")
    ap.add_argument("--lines", nargs="+", required=True, help="per-call JSON lines from `replay go`")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)
    res = report(read_lines(args.lines), args.out_dir)
    print(json.dumps({k: v for k, v in res.items() if k != "files"}, indent=1))
    return 0 if res.get("written") else 1


if __name__ == "__main__":
    sys.exit(main())
