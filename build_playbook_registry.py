"""
build_playbook_registry.py — compute per-(asset, venue, regime) edge
statistics and dump to a registry JSON the runtime playbook generator
reads.

For each (asset, venue) loaded from bins, runs the Phase 1.5 classifier
and computes, per regime that has any chunks:
  - n            : number of chunks of this regime
  - r            : Pearson r of (chunk mean_dipole_t, next-chunk log_return)
  - r2, p        : R² and p-value
  - direction    : "momentum" if r>+0.3 with p<0.20,
                   "mean_revert" if r<-0.3 with p<0.20,
                   else "exploring"
  - last_updated : ISO timestamp

Writes playbook_registry.json keyed by "<ASSET>/<VENUE>/<REGIME>".
playbook_generator.py reads this at signal-emit time so the actionable
text reflects the current data, not a hand-coded theory.

Usage:
    python build_playbook_registry.py \\
        --asset ETH \\
        --cb-bins eth_coinbase_bins.json \\
        --kr-bins eth_kraken_bins.json \\
        --output-path playbook_registry.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone

import numpy as np

from phase1_5_evaluator import classify_venue, load_bars, _pearsonr_with_p


def _per_regime_edge(chunks: list, results: list, k: int = 1) -> dict:
    """Mirror the gate-I computation: per regime, correlation of mean
    dipole_t with next-chunk log return at lag k."""
    if len(chunks) < k + 2:
        return {}
    mean_dipoles = []
    chunk_returns = []
    for c in chunks:
        bar_dips = [b.dipole for b in c.bars]
        mean_dipoles.append(float(np.mean(bar_dips)) if bar_dips else 0.0)
        if len(c.bars) >= 2:
            r_ret = math.log(max(c.bars[-1].close, 1e-12)
                              / max(c.bars[0].close, 1e-12))
        else:
            r_ret = 0.0
        chunk_returns.append(r_ret)
    md = np.array(mean_dipoles)
    cr = np.array(chunk_returns)
    labels = [r.regime.value for r in results]

    out: dict[str, dict] = {}
    for regime in set(labels):
        idx = [i for i in range(len(chunks) - k) if labels[i] == regime]
        n = len(idx)
        if n < 1:
            continue
        if n < 3:
            out[regime] = {"n": n, "r": None, "r2": None, "p": None,
                            "direction": "insufficient",
                            "note": "n<3; sample too small to claim direction"}
            continue
        x = md[idx]
        y = cr[[i + k for i in idx]]
        r, p, npairs = _pearsonr_with_p(x, y)
        if not (np.isfinite(r) and np.isfinite(p)):
            out[regime] = {"n": npairs, "r": None, "r2": None, "p": None,
                            "direction": "insufficient",
                            "note": "degenerate variance"}
            continue
        # Direction call is INTENTIONALLY permissive: we want the playbook
        # to update each pass and force awareness of how the read evolves.
        # Loosely: |r|>0.3 with p<0.20 is enough to tag momentum or
        # mean_revert; anything else is "exploring". Caller surfaces the
        # n + p so the user sees the small-sample caveat in the text.
        if r > 0.3 and p < 0.20:
            direction = "momentum"
        elif r < -0.3 and p < 0.20:
            direction = "mean_revert"
        else:
            direction = "exploring"
        out[regime] = {
            "n": int(npairs),
            "r": round(float(r), 4),
            "r2": round(float(r * r), 5),
            "p": round(float(p), 4),
            "direction": direction,
        }
    return out


_HISTORY_MAX_LEN = 200            # cap each cell's history; keeps file size bounded
_LIFECYCLE_VERSION = 2            # bump when shape changes; older entries auto-upgrade


def _upgrade_legacy_entry(entry: dict, key: str) -> dict:
    """Convert a flat (pre-v2) registry entry into a history-aware one."""
    if "current" in entry and "history" in entry:
        return entry
    asset, venue, regime = key.split("/", 2)
    flat = {k: v for k, v in entry.items()
              if k in ("n", "r", "r2", "p", "direction", "note", "last_updated")}
    return {
        "asset": asset, "venue": venue, "regime": regime,
        "current": flat,
        "history": [flat] if flat else [],
        "lifecycle": {
            "version": _LIFECYCLE_VERSION,
            "proposed_at": entry.get("last_updated"),
            "last_updated": entry.get("last_updated"),
            "last_changed_direction_at": None,
            "n_direction_flips": 0,
            "n_milestone_upgrades": 0,
            "status": "evolving",
        },
    }


def _direction_flipped(prev_dir: str, cur_dir: str) -> bool:
    """Treat momentum<->mean_revert as a flip; ignore exploring/insufficient
    transitions because those are noise-driven, not real shifts in the edge."""
    decisive = ("momentum", "mean_revert")
    return (prev_dir in decisive
            and cur_dir in decisive
            and prev_dir != cur_dir)


def _milestone_crossed(prev_n: int, cur_n: int) -> str | None:
    for thr in (10, 20, 30, 50, 100):
        if prev_n < thr <= cur_n:
            return f"n>={thr}"
    return None


def build_registry(asset: str, cb_bins_path: str, kr_bins_path: str,
                    existing: dict | None = None,
                    multi_signal_pelt: bool = True
                    ) -> tuple[dict, list[dict]]:
    """Run classify_venue on each venue and compute per-regime edge stats.

    Merges into `existing` registry, preserving each cell's history. Returns
    `(updated_registry, audit_events)` where `audit_events` is a list of dict
    records describing what changed in this rebuild — direction flips,
    milestone crossings, decay onsets. refrag_audit.py + the backend's
    `/api/drift-alert` relay consume these.
    """
    existing = existing or {}
    audit_events: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for venue_short, bins_path in (("CB", cb_bins_path), ("KR", kr_bins_path)):
        if not os.path.exists(bins_path):
            print(f"[registry] skipping {venue_short}: {bins_path} missing")
            continue
        bars = load_bars(bins_path)
        if not bars:
            continue
        chunks, results, _, _ = classify_venue(
            bars, f"{venue_short}-{asset}",
            chunk_max=30, chunk_min=10,
            multi_signal_pelt=multi_signal_pelt,
        )
        per_regime = _per_regime_edge(chunks, results, k=1)
        for regime, stats in per_regime.items():
            key = f"{asset}/{venue_short}/{regime}"
            stats = {**stats, "last_updated": now}

            prior = existing.get(key)
            if prior is not None:
                prior = _upgrade_legacy_entry(prior, key)
            entry = prior or {
                "asset": asset, "venue": venue_short, "regime": regime,
                "current": {}, "history": [],
                "lifecycle": {
                    "version": _LIFECYCLE_VERSION,
                    "proposed_at": now, "last_updated": now,
                    "last_changed_direction_at": None,
                    "n_direction_flips": 0,
                    "n_milestone_upgrades": 0,
                    "status": "evolving",
                },
            }

            prev_current = entry.get("current") or {}
            prev_dir = prev_current.get("direction") or ""
            prev_n = prev_current.get("n") or 0

            entry["current"] = stats
            entry["history"].append(stats)
            if len(entry["history"]) > _HISTORY_MAX_LEN:
                entry["history"] = entry["history"][-_HISTORY_MAX_LEN:]
            lifecycle = entry["lifecycle"]
            lifecycle["last_updated"] = now

            cur_dir = stats.get("direction") or ""
            cur_n = stats.get("n") or 0

            if _direction_flipped(prev_dir, cur_dir):
                lifecycle["last_changed_direction_at"] = now
                lifecycle["n_direction_flips"] = lifecycle.get("n_direction_flips", 0) + 1
                audit_events.append({
                    "type": "direction_flip", "key": key, "ts": now,
                    "from": prev_dir, "to": cur_dir,
                    "prev_r": prev_current.get("r"), "cur_r": stats.get("r"),
                    "prev_n": prev_n, "cur_n": cur_n,
                })
            milestone = _milestone_crossed(prev_n, cur_n)
            if milestone:
                lifecycle["n_milestone_upgrades"] = lifecycle.get("n_milestone_upgrades", 0) + 1
                audit_events.append({
                    "type": "sample_milestone", "key": key, "ts": now,
                    "milestone": milestone,
                    "cur_r": stats.get("r"), "cur_direction": cur_dir,
                })
            # Decay/strengthen detection on |r| trend across last 3 readings
            decisive_history = [h for h in entry["history"]
                                  if h.get("r") is not None][-3:]
            if len(decisive_history) >= 3:
                rs = [abs(h["r"]) for h in decisive_history]
                if rs[0] > rs[1] > rs[2] and rs[0] - rs[2] > 0.15:
                    audit_events.append({
                        "type": "edge_decay", "key": key, "ts": now,
                        "abs_r_trend": [round(x, 3) for x in rs],
                        "cur_direction": cur_dir,
                    })
                elif rs[0] < rs[1] < rs[2] and rs[2] - rs[0] > 0.15:
                    audit_events.append({
                        "type": "edge_strengthen", "key": key, "ts": now,
                        "abs_r_trend": [round(x, 3) for x in rs],
                        "cur_direction": cur_dir,
                    })

            existing[key] = entry
    return existing, audit_events


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset", required=True)
    p.add_argument("--cb-bins", required=True)
    p.add_argument("--kr-bins", required=True)
    p.add_argument("--output-path", default="playbook_registry.json")
    p.add_argument("--audit-events-path", default=None,
                   help="if set, append audit events (direction flips, "
                        "milestones, decay/strengthen) to this JSONL file")
    p.add_argument("--no-multi-signal-pelt", dest="multi_signal_pelt",
                   action="store_false")
    p.set_defaults(multi_signal_pelt=True)
    args = p.parse_args()

    existing: dict = {}
    if os.path.exists(args.output_path):
        try:
            with open(args.output_path) as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    updated, audit_events = build_registry(
        args.asset, args.cb_bins, args.kr_bins,
        existing=existing,
        multi_signal_pelt=args.multi_signal_pelt,
    )

    with open(args.output_path, "w") as f:
        json.dump(updated, f, indent=2)

    print(f"[registry] {len(updated)} cells in registry; saved to {args.output_path}")
    for k in sorted(k for k in updated if k.startswith(f"{args.asset}/")):
        s = updated[k].get("current") or {}
        n = s.get("n", 0)
        r = s.get("r")
        p_val = s.get("p")
        d = s.get("direction", "?")
        flips = updated[k].get("lifecycle", {}).get("n_direction_flips", 0)
        flip_tag = f"  flips={flips}" if flips else ""
        if r is None:
            print(f"  {k:<28} n={n:>3}  ({d}){flip_tag}")
        else:
            print(f"  {k:<28} n={n:>3}  r={r:+.3f}  p={p_val:.3f}  -> {d}{flip_tag}")

    if audit_events:
        print(f"[audit] {len(audit_events)} event(s) generated this rebuild:")
        for ev in audit_events:
            etype = ev["type"]
            key = ev["key"]
            if etype == "direction_flip":
                print(f"  ⚠ FLIP   {key}: {ev['from']} -> {ev['to']}  "
                      f"(r {ev.get('prev_r')} -> {ev.get('cur_r')}, "
                      f"n {ev.get('prev_n')} -> {ev.get('cur_n')})")
            elif etype == "sample_milestone":
                print(f"  ✓ MILESTONE  {key}: {ev['milestone']}  "
                      f"(direction {ev.get('cur_direction')})")
            elif etype == "edge_decay":
                print(f"  ↓ DECAY  {key}: |r| trend {ev['abs_r_trend']}")
            elif etype == "edge_strengthen":
                print(f"  ↑ STRENGTHEN  {key}: |r| trend {ev['abs_r_trend']}")
            else:
                print(f"  · {etype}  {key}")
    else:
        print("[audit] no drift events this rebuild")

    if args.audit_events_path and audit_events:
        with open(args.audit_events_path, "a") as f:
            for ev in audit_events:
                f.write(json.dumps(ev) + "\n")
        print(f"[audit] {len(audit_events)} events appended to {args.audit_events_path}")


if __name__ == "__main__":
    main()
