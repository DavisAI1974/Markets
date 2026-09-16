#!/usr/bin/env python3
"""Build the canonical blind forecaster state from the existing decision_state path.

This is a read-side gate, not a parallel signal. It calls forecast_harness.decision_state,
then removes any datum that fails the strict blind-wall audit. Raw stores and historical
ingestion are never modified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import blind_state_audit as bsa
import forecast_harness as fh


def build(days: list[str], mask_after: str | None, issue_time_et: str) -> tuple[dict, dict]:
    raw = fh.decision_state(days, mask_after=mask_after)
    clean, report = bsa.sanitize_state(raw, issue_time_et=issue_time_et)
    return clean, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a strict blind-safe NG decision state")
    parser.add_argument("--days", required=True, help="comma-separated YYYYMMDD sessions")
    parser.add_argument("--mask-after", required=True, help="YYYYMMDD block anchor")
    parser.add_argument("--out", required=True)
    parser.add_argument("--audit-out")
    parser.add_argument("--issue-time-et", default="08:00")
    parser.add_argument(
        "--allow-sanitized",
        action="store_true",
        help="write sanitized state even when leakage was removed; without this flag any violation blocks output",
    )
    args = parser.parse_args()

    clean, report = build(args.days.split(","), args.mask_after, args.issue_time_et)
    if args.audit_out:
        Path(args.audit_out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["passed"] and not args.allow_sanitized:
        print(json.dumps(report, indent=2))
        print("[build_blind_state] BLOCKED: audit violations exist; review before issuing a blind forecast")
        return 1
    Path(args.out).write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    print(
        f"[build_blind_state] wrote {args.out}; days={report['n_days']} "
        f"removed={report['n_violations']} warnings={report['n_warnings']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
