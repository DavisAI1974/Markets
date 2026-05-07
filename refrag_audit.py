"""
refrag_audit.py — daily / per-cycle self-audit of the playbook registry.

Mirrors the deepnova/refrag pattern (lifecycle tracker + transfer detector
+ falsification prioritizer) natively in this repo. Runs after every
build_playbook_registry.py rebuild (every 6h via cron in LAUNCH_PLAYBOOK
§1.6) and answers:

  - Has any cell's direction call FLIPPED since last cycle?
  - Has any cell's edge STRENGTHENED or DECAYED across recent rebuilds?
  - Has any cell crossed a sample-size MILESTONE?
  - Are there cells we should prioritize gathering more data for
    (FALSIFICATION targets — small n, marginal p, would benefit from
    more chunks)?

Output:
  - Markdown audit report at audit_reports/YYYY-MM-DDTHH.md
  - Optional: POST each event to a backend /api/drift-alert endpoint so
    Discord + PWA surface drift to users in real time

Why this exists:
  > "we don't want to be thinking about shifts in the market dynamics
  > after we see our confidence numbers have dropped noticeably. we want
  > to be on top of this constantly."

The audit makes drift VISIBLE the moment it's detectable in the data,
not after a friend's P&L tells them so.

Usage:
    python refrag_audit.py \\
        --registry-path playbook_registry.json \\
        --audit-events-path audit_events.jsonl \\
        --report-dir audit_reports \\
        [--post-url http://localhost:8000/api/drift-alert] \\
        [--access-token $MARKETS_WATCH_ACCESS_TOKEN]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from urllib import request as urlreq
from urllib.error import URLError, HTTPError


# ---------------------------------------------------------------------------
# Lifecycle classification — used by the report and (optionally) by the
# runtime to decorate playbook text. Mirrors the patterns in
# deepnova/refrag's lifecycle_tracker.py.
# ---------------------------------------------------------------------------


def classify_cell(entry: dict) -> dict:
    """Classify a single (asset, venue, regime) cell into a lifecycle state.
    Returns a dict with keys:
      - status: "stable" | "evolving" | "unstable" | "decaying" | "strengthening" | "exploring" | "insufficient"
      - reasons: list[str] — short justifications
      - falsification_priority: float in [0, 1] — how much would we benefit
        from more data here? (1.0 = highest priority)
    """
    current = entry.get("current") or entry  # tolerate legacy flat shape
    history = entry.get("history") or []
    lifecycle = entry.get("lifecycle") or {}

    direction = current.get("direction") or "insufficient"
    n = current.get("n") or 0
    r = current.get("r")
    p = current.get("p")

    reasons: list[str] = []
    status = "evolving"
    falsification_priority = 0.0

    if direction == "insufficient":
        status = "insufficient"
        reasons.append(f"only {n} chunks observed; need ≥3 for any direction call")
        falsification_priority = 0.95 if n >= 1 else 0.4
        return {"status": status, "reasons": reasons,
                "falsification_priority": round(falsification_priority, 2)}

    if direction == "exploring":
        status = "exploring"
        reasons.append(
            f"weak signal (|r|={abs(r):.2f}, p={p:.2f}); not committing to direction")
        # High priority — we have data but no edge; more data either resolves
        # to a direction or confirms there's nothing here.
        falsification_priority = 0.85 if n < 30 else 0.5
        return {"status": status, "reasons": reasons,
                "falsification_priority": round(falsification_priority, 2)}

    # Direction is "momentum" or "mean_revert" from here.
    n_flips = lifecycle.get("n_direction_flips", 0)
    if n_flips >= 2:
        status = "unstable"
        reasons.append(f"{n_flips} direction flips on this cell — read is unreliable")
        falsification_priority = 0.9
    elif lifecycle.get("last_changed_direction_at"):
        status = "evolving"
        reasons.append("direction call recently changed; watching for stability")
        falsification_priority = 0.7

    decisive = [h for h in history if h.get("r") is not None][-3:]
    if len(decisive) >= 3:
        rs = [abs(h["r"]) for h in decisive]
        if rs[0] > rs[1] > rs[2] and rs[0] - rs[2] > 0.15:
            status = "decaying"
            reasons.append(f"|r| trending down: {rs[0]:.2f} → {rs[1]:.2f} → {rs[2]:.2f}")
            falsification_priority = max(falsification_priority, 0.8)
        elif rs[0] < rs[1] < rs[2] and rs[2] - rs[0] > 0.15:
            status = "strengthening"
            reasons.append(f"|r| trending up: {rs[0]:.2f} → {rs[1]:.2f} → {rs[2]:.2f}")
            falsification_priority = 0.3

    if status == "evolving" and n >= 30 and (p or 1) < 0.05 and n_flips == 0:
        status = "stable"
        reasons.append(f"n={n} with p={p:.3f} and no flips — stable read")
        falsification_priority = 0.1

    if not reasons:
        reasons.append(f"n={n}, r={r:+.2f}, p={p:.3f}")

    # In small-sample state, even decisive cells have falsification value.
    if n < 10 and status not in ("unstable", "decaying"):
        falsification_priority = max(falsification_priority, 0.6)

    return {"status": status, "reasons": reasons,
            "falsification_priority": round(falsification_priority, 2)}


# ---------------------------------------------------------------------------
# Audit pass
# ---------------------------------------------------------------------------


def audit_registry(registry: dict) -> tuple[list[dict], dict]:
    """Walk the registry, classify each cell, return (cell_audits, summary).

    cell_audits is a list of:
      {key, asset, venue, regime, status, reasons, falsification_priority,
       current, lifecycle}
    summary is an aggregate dict for the report header.
    """
    cell_audits: list[dict] = []
    status_counts: dict[str, int] = {}
    flip_count = 0
    decay_count = 0
    strengthen_count = 0

    for key, entry in registry.items():
        cls = classify_cell(entry)
        cell_audits.append({
            "key": key,
            "asset": entry.get("asset"),
            "venue": entry.get("venue"),
            "regime": entry.get("regime"),
            "status": cls["status"],
            "reasons": cls["reasons"],
            "falsification_priority": cls["falsification_priority"],
            "current": entry.get("current") or {},
            "lifecycle": entry.get("lifecycle") or {},
        })
        status_counts[cls["status"]] = status_counts.get(cls["status"], 0) + 1
        if cls["status"] == "unstable":
            flip_count += 1
        if cls["status"] == "decaying":
            decay_count += 1
        if cls["status"] == "strengthening":
            strengthen_count += 1

    summary = {
        "n_cells": len(registry),
        "status_counts": status_counts,
        "n_unstable": flip_count,
        "n_decaying": decay_count,
        "n_strengthening": strengthen_count,
    }
    return cell_audits, summary


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def render_report(cell_audits: list[dict], summary: dict,
                   audit_events_since: list[dict]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = []
    lines.append(f"# Refrag self-audit — {now}")
    lines.append("")
    lines.append(f"Cells tracked: **{summary['n_cells']}**.")
    lines.append("")
    lines.append("## Status counts")
    for status, n in sorted(summary["status_counts"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- **{status}**: {n}")
    lines.append("")

    if audit_events_since:
        lines.append("## Drift events since last audit")
        for ev in audit_events_since:
            t = ev.get("type", "?")
            key = ev.get("key", "?")
            if t == "direction_flip":
                lines.append(f"- ⚠ **FLIP** `{key}`: {ev.get('from')} → {ev.get('to')} "
                             f"(r {ev.get('prev_r')} → {ev.get('cur_r')}, "
                             f"n {ev.get('prev_n')} → {ev.get('cur_n')})")
            elif t == "edge_decay":
                lines.append(f"- ↓ **DECAY** `{key}`: |r| trend {ev.get('abs_r_trend')}")
            elif t == "edge_strengthen":
                lines.append(f"- ↑ **STRENGTHEN** `{key}`: |r| trend {ev.get('abs_r_trend')}")
            elif t == "sample_milestone":
                lines.append(f"- ✓ **MILESTONE** `{key}`: {ev.get('milestone')}")
            else:
                lines.append(f"- · `{t}` `{key}`")
        lines.append("")
    else:
        lines.append("## Drift events since last audit")
        lines.append("_None — no flips, decays, or milestones in this window._")
        lines.append("")

    lines.append("## Per-cell readout")
    by_priority = sorted(cell_audits, key=lambda c: -c["falsification_priority"])
    for c in by_priority:
        cur = c["current"]
        n = cur.get("n", 0)
        r = cur.get("r")
        p_val = cur.get("p")
        d = cur.get("direction", "?")
        emoji = {
            "stable": "✓", "strengthening": "↑", "evolving": "·",
            "exploring": "?", "decaying": "↓", "unstable": "⚠",
            "insufficient": "—",
        }.get(c["status"], " ")
        rstr = f"r={r:+.2f}" if r is not None else "r=—"
        pstr = f"p={p_val:.3f}" if p_val is not None else "p=—"
        lines.append(f"- {emoji} `{c['key']}` "
                     f"[{c['status']}, falsif_priority={c['falsification_priority']:.2f}] "
                     f"n={n}, {rstr}, {pstr}, dir={d}")
        for reason in c["reasons"]:
            lines.append(f"    - {reason}")

    lines.append("")
    lines.append("## Falsification priorities (cells most worth gathering data on)")
    high_priority = [c for c in by_priority if c["falsification_priority"] >= 0.6]
    if not high_priority:
        lines.append("_No cells flagged as high-priority for falsification._")
    else:
        for c in high_priority[:10]:
            lines.append(f"- `{c['key']}` — {c['status']} "
                         f"(priority {c['falsification_priority']:.2f}); "
                         f"{c['reasons'][0] if c['reasons'] else ''}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Optional: POST audit events as drift_alerts to the running backend so
# Discord + PWA pick them up in real time on the SSE stream.
# ---------------------------------------------------------------------------


def post_drift_alerts(events: list[dict], post_url: str,
                       access_token: str | None) -> int:
    """POST each audit event to the backend's /api/drift-alert endpoint.
    Returns count successfully posted."""
    if not events:
        return 0
    posted = 0
    for ev in events:
        body = json.dumps(ev).encode("utf-8")
        req = urlreq.Request(post_url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if access_token:
            req.add_header("Authorization", f"Bearer {access_token}")
        try:
            with urlreq.urlopen(req, timeout=5) as resp:
                if 200 <= resp.status < 300:
                    posted += 1
                else:
                    print(f"[refrag_audit] POST {post_url}: {resp.status}",
                          file=sys.stderr)
        except (URLError, HTTPError) as e:
            print(f"[refrag_audit] POST error: {e}", file=sys.stderr)
    return posted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _consume_audit_events(path: str | None) -> list[dict]:
    """Read all audit events written by build_playbook_registry.py since
    the last audit, then truncate the file. Idempotent — if no file or
    file empty, returns []."""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        events = [json.loads(ln) for ln in lines]
    except Exception as e:
        print(f"[refrag_audit] could not read {path}: {e}", file=sys.stderr)
        return []
    # Truncate so next run only sees fresh events.
    open(path, "w").close()
    return events


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--registry-path", default="playbook_registry.json")
    p.add_argument("--audit-events-path", default="audit_events.jsonl",
                   help="JSONL produced by build_playbook_registry.py "
                        "--audit-events-path. Truncated after each audit.")
    p.add_argument("--report-dir", default="audit_reports")
    p.add_argument("--post-url", default=None,
                   help="if set, POST each drift event to this URL "
                        "(e.g. http://localhost:8000/api/drift-alert)")
    p.add_argument("--access-token", default=os.environ.get("MARKETS_WATCH_ACCESS_TOKEN"),
                   help="bearer token for the POST (defaults to env)")
    args = p.parse_args()

    if not os.path.exists(args.registry_path):
        print(f"[refrag_audit] registry {args.registry_path} missing; "
              f"run build_playbook_registry.py first")
        return 2

    with open(args.registry_path) as f:
        registry = json.load(f)

    cell_audits, summary = audit_registry(registry)
    events_since = _consume_audit_events(args.audit_events_path)
    report = render_report(cell_audits, summary, events_since)

    os.makedirs(args.report_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
    report_path = os.path.join(args.report_dir, f"{stamp}.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"[refrag_audit] report written: {report_path}")
    print(f"[refrag_audit] {summary['n_cells']} cells; "
          f"{summary.get('n_unstable', 0)} unstable, "
          f"{summary.get('n_decaying', 0)} decaying, "
          f"{summary.get('n_strengthening', 0)} strengthening")

    if args.post_url and events_since:
        posted = post_drift_alerts(events_since, args.post_url, args.access_token)
        print(f"[refrag_audit] {posted}/{len(events_since)} drift_alerts posted "
              f"to {args.post_url}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
