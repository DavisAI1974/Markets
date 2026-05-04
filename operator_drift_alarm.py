"""
operator_drift_alarm.py — detect day-over-day operator coefficient drift.

The cyber-DARPA precedent: the recovered operator's coefficients drift
characteristically before / during regime changes. Watching that drift
gives early warning that a previously-working strategy is degrading.

This tool compares two operator_registry.json snapshots and flags:
  - sources where the preferred operator changed (regime fundamentally shifted)
  - sources where rolling Sharpe dropped > THRESHOLD (alpha decay starting)
  - sources where n_trades didn't grow (data acquisition stalled)

Usage:
  # Snapshot daily
  cp operator_registry.json snapshots/registry_$(date +%Y%m%d).json

  # Compare yesterday vs today
  python operator_drift_alarm.py \\
      --baseline snapshots/registry_20260503.json \\
      --current operator_registry.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass


@dataclass
class DriftSignal:
    asset: str
    venue: str
    severity: str   # "info" | "warning" | "critical"
    kind: str
    message: str
    delta: dict


def compare_registries(baseline_path: str, current_path: str,
                        sharpe_drop_threshold: float = 0.3,
                        sharpe_drop_critical: float = 0.6) -> list[DriftSignal]:
    with open(baseline_path) as f:
        b = json.load(f)
    with open(current_path) as f:
        c = json.load(f)

    signals: list[DriftSignal] = []
    all_keys = set(b.keys()) | set(c.keys())
    for key in sorted(all_keys):
        if "." not in key:
            continue
        asset, venue = key.split(".", 1)
        b_entry = b.get(key)
        c_entry = c.get(key)

        if b_entry is None and c_entry is not None:
            signals.append(DriftSignal(asset, venue, "info", "new_source",
                f"Source {key} appeared in current registry (n_trades={c_entry.get('n_trades', 0)})",
                {"baseline": None, "current": c_entry}))
            continue
        if c_entry is None and b_entry is not None:
            signals.append(DriftSignal(asset, venue, "warning", "source_disappeared",
                f"Source {key} present in baseline but missing from current; data acquisition halted?",
                {"baseline": b_entry, "current": None}))
            continue

        b_pref = b_entry.get("preferred")
        c_pref = c_entry.get("preferred")
        b_sharpe = float(b_entry.get("rolling_sharpe", 0.0))
        c_sharpe = float(c_entry.get("rolling_sharpe", 0.0))
        b_n = int(b_entry.get("n_trades", 0))
        c_n = int(c_entry.get("n_trades", 0))

        # 1. Preferred operator changed
        if b_pref != c_pref:
            severity = "warning" if (b_pref and c_pref) else "info"
            signals.append(DriftSignal(asset, venue, severity, "preferred_changed",
                f"Preferred operator changed: {b_pref} -> {c_pref}. "
                f"Possible regime shift or convergence to new winner.",
                {"baseline_preferred": b_pref, "current_preferred": c_pref,
                 "baseline_sharpe": b_sharpe, "current_sharpe": c_sharpe}))

        # 2. Sharpe dropped meaningfully
        sharpe_delta = c_sharpe - b_sharpe
        if sharpe_delta <= -sharpe_drop_critical and b_sharpe > 0:
            signals.append(DriftSignal(asset, venue, "critical", "sharpe_collapse",
                f"Rolling Sharpe collapsed: {b_sharpe:+.2f} -> {c_sharpe:+.2f} "
                f"(delta {sharpe_delta:+.2f}). Strategy may be dying; investigate.",
                {"baseline_sharpe": b_sharpe, "current_sharpe": c_sharpe, "delta": sharpe_delta}))
        elif sharpe_delta <= -sharpe_drop_threshold and b_sharpe > 0:
            signals.append(DriftSignal(asset, venue, "warning", "sharpe_drop",
                f"Rolling Sharpe dropped: {b_sharpe:+.2f} -> {c_sharpe:+.2f} "
                f"(delta {sharpe_delta:+.2f}). Watch closely.",
                {"baseline_sharpe": b_sharpe, "current_sharpe": c_sharpe, "delta": sharpe_delta}))

        # 3. Trade count didn't grow
        if c_n <= b_n and b_n > 0:
            signals.append(DriftSignal(asset, venue, "warning", "data_stalled",
                f"n_trades didn't grow: {b_n} -> {c_n}. Collection or "
                f"adaptive-backtester run may have stalled.",
                {"baseline_n": b_n, "current_n": c_n}))
    return signals


def format_report(signals: list[DriftSignal]) -> str:
    if not signals:
        return "✓ No drift signals detected. All sources stable."
    lines = [f"=== {len(signals)} drift signal(s) ==="]
    by_severity = {"critical": [], "warning": [], "info": []}
    for s in signals:
        by_severity.setdefault(s.severity, []).append(s)
    for sev in ("critical", "warning", "info"):
        for s in by_severity.get(sev, []):
            icon = {"critical": "🔴", "warning": "🟡", "info": "ℹ️ "}.get(s.severity, "  ")
            lines.append(f"{icon} [{s.severity.upper():<8}] {s.asset}-{s.venue} {s.kind}")
            lines.append(f"      {s.message}")
            if s.delta:
                lines.append(f"      delta: {json.dumps(s.delta, default=str)}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True, help="path to baseline operator_registry.json")
    p.add_argument("--current", required=True, help="path to current operator_registry.json")
    p.add_argument("--report-path", default=None, help="save signals as JSON")
    p.add_argument("--sharpe-warn", type=float, default=0.3)
    p.add_argument("--sharpe-critical", type=float, default=0.6)
    args = p.parse_args()

    signals = compare_registries(args.baseline, args.current,
                                   sharpe_drop_threshold=args.sharpe_warn,
                                   sharpe_drop_critical=args.sharpe_critical)
    print(format_report(signals))

    if args.report_path:
        with open(args.report_path, "w") as f:
            json.dump([s.__dict__ for s in signals], f, indent=2)
        print(f"\nSaved: {args.report_path}")

    if any(s.severity == "critical" for s in signals):
        sys.exit(2)
    if any(s.severity == "warning" for s in signals):
        sys.exit(1)


if __name__ == "__main__":
    main()
