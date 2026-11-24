"""8c. The report: one table with every call by every arm, and two charts.

Input: the per-call lines `replay go` wrote (JSON lines, one per call and arm; the head line carrying Greg's words
is skipped). Output, in a folder the caller names (a markets-data checkout; never inside Markets):
  token-test-table.csv / .jsonl   one row for each call and arm, nothing folded
  token-test-tokens-per-call.png   tokens of each call, one line for each arm
  token-test-tokens-cumulative.png the running sum over the trade day's calls of each arm's OWN calls, in the
                                   receipts' order (the plan asks for it by name; not an average, nothing ranked)
  token-test-report-receipt.json   for each arm: rows, points plotted, rows with no figure, and the check

A figure Granite's record or a replayed call does not carry is NOT RECORDED (null): an empty cell in the table, no
point in the charts, never 0. A row HAS A FIGURE when its input_tokens and output_tokens are both recorded; its
total_tokens adds the recorded figures of the four and `figures_not_recorded` names any that are not. A row with no
figure has an empty total and an empty cumulative cell and the running sum passes over it. The report states how
many rows have no figure for each arm.

The x axis of both charts is the Granite call: its place in the receipts' order (`granite_position` on the line),
so the same call sits at the same place for every arm even when arm E sets calls apart. A line without that field
(a Granite record read straight from the receipts) takes the place of its call id's first appearance in the lines.
The reconciliation, for each arm and each chart: rows = points plotted + rows with no figure. If not, it raises
and writes NOTHING. With no per-call line there is nothing to plot: it says so and writes nothing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

TOKEN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
COLUMNS = ("arm", "granite_position", "position", "call_id", "conversation_id", "purpose", "model_asked", "model_served",
           "batch", *TOKEN_FIELDS, "figures_not_recorded", "total_tokens", "cumulative_tokens", "wall_clock_s",
           "cost_usd", "stop_reason", "result_type", "output", "granite_output")


class ReportMismatch(RuntimeError):
    pass


def read_lines(paths) -> list[dict]:
    out = []
    for p in ([paths] if isinstance(paths, (str, Path)) else paths):
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                l = json.loads(line)
                if l.get("record") != "head":
                    out.append(l)
    return out


def _figure(l, k):
    v = l.get(k)
    return None if v is None else int(v)


def has_figure(l: dict) -> bool:
    return _figure(l, "input_tokens") is not None and _figure(l, "output_tokens") is not None


def running_sums(lines: list[dict]) -> dict:
    """The running sum over the trade day's calls, last value, for each token figure and the cost; and how many
    calls have no figure. A call that does not carry a figure adds nothing to that figure's sum (None when no call
    carries it). Nothing else is summed."""
    last = {k: None for k in (*TOKEN_FIELDS, "cost_usd")}
    for l in lines:
        for k in TOKEN_FIELDS:
            v = _figure(l, k)
            if v is not None:
                last[k] = (last[k] or 0) + v
        c = (l.get("cost") or {}).get("total")
        if c is not None:
            last["cost_usd"] = (last["cost_usd"] or 0.0) + float(c)
    return {"calls": len(lines), "calls_with_no_figure": sum(1 for l in lines if not has_figure(l)), "last": last}


def build_rows(lines: list[dict]) -> list[dict]:
    first_seen: dict = {}
    for l in lines:
        first_seen.setdefault(l["call_id"], len(first_seen) + 1)
    rows, pos, cum = [], {}, {}
    for l in lines:
        a = l["arm"]
        pos[a] = pos.get(a, 0) + 1
        fig = {k: _figure(l, k) for k in TOKEN_FIELDS}
        ok = has_figure(l)
        tot = sum(v for v in fig.values() if v is not None) if ok else None
        if ok:
            cum[a] = cum.get(a, 0) + tot
        rows.append({"arm": a, "granite_position": l.get("granite_position") or first_seen[l["call_id"]],
                     "position": pos[a], "call_id": l["call_id"], "conversation_id": l.get("conversation_id"),
                     "purpose": l.get("purpose"), "model_asked": l.get("model_asked"), "model_served": l.get("model_served"),
                     "batch": l.get("batch"), **fig, "figures_not_recorded": [k for k, v in fig.items() if v is None],
                     "total_tokens": tot, "cumulative_tokens": cum.get(a) if ok else None,
                     "wall_clock_s": l.get("wall_clock_s"),
                     "cost_usd": (l.get("cost") or {}).get("total"), "stop_reason": l.get("stop_reason"),
                     "result_type": l.get("result_type"),
                     "output": l.get("output"), "granite_output": l.get("granite_output")})
    return rows


def _figures(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    arms = sorted({r["arm"] for r in rows})
    figs, plotted = {}, {"per_call": {}, "cumulative": {}}
    for key, field, title in (("per_call", "total_tokens", "Tokens of each call, by arm"),
                              ("cumulative", "cumulative_tokens", "Running sum over the trade day's calls, by arm (own calls, receipts' order)")):
        fig, ax = plt.subplots(figsize=(11, 5))
        for a in arms:
            mine = [r for r in rows if r["arm"] == a and r[field] is not None]
            (line,) = ax.plot([r["granite_position"] for r in mine], [r[field] for r in mine], marker="o", ms=3,
                              label=f"arm {a}")
            plotted[key][a] = len(line.get_xdata())
        ax.set_xlabel("Granite call (its place in the receipts' order)")
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
    no_fig = {a: sum(1 for r in rows if r["arm"] == a and r["total_tokens"] is None) for a in counts}
    bad = {k: {a: (counts[a], n, no_fig[a]) for a, n in v.items() if n + no_fig[a] != counts[a]}
           for k, v in plotted.items()}
    if any(bad.values()) or sum(counts.values()) != len(rows):
        raise ReportMismatch(f"rows differ from points plotted + rows with no figure (rows, points, no figure): {bad}")
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
               "points_plotted_per_arm": plotted, "rows_with_no_figure_per_arm": no_fig,
               "reconciliation": "rows = points plotted + rows with no figure, for each arm and each chart",
               "rows_equal_points_plus_no_figure": True,
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
