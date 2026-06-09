"""
scripts/bins_integrity.py — audit and safely re-grid the per-source 1-second bins.

Motivation (the "missing or duplicated" rebuild): the durable collectors disagree
on binning policy and were corrupting data three ways:
  1. DUPLICATED volume — Kraken v2 replays a "snapshot" of recent trades on every
     (re)subscribe; the collector counted those, re-ingesting the same trades on
     each reconnect and dumping them into the reconnect wall-clock second. Footprint:
     isolated seconds with n_trades far above the local rate. (Fixed forward in the
     kraken collectors; this tool FLAGS the residue already on disk.)
  2. MISSING seconds (apparent) — inconsistent grid policy: some venues pad quiet
     seconds with zero-bins (bybit), some skip them entirely (kraken), some fill
     nearly every second (coinbase). Same reality, three on-disk shapes, which
     breaks cross-venue alignment. `--normalize` puts every source on the SAME
     regular 1-second grid (lossless: real bins are preserved verbatim, only
     explicit zero-bins are added for truly-empty seconds).
  3. MISSING seconds (real) — a crashed run force-pushing a partial file. That is a
     pipeline bug (fixed in the workflow guardrail); this tool only diagnoses it via
     the coverage/span report.

This tool NEVER mutates real trade volumes. Suspect (spike) seconds are reported and,
under --normalize, marked with "_suspect": true so a downstream consumer can mask
them — but their buy/sell/n_trades are left untouched (you can't cleanly un-sum an
already-aggregated duplicate, so the honest move is to flag, not guess).

Usage:
    python scripts/bins_integrity.py --report realbins/*.json
    python scripts/bins_integrity.py --report realbins/*.json --json out_report.json
    python scripts/bins_integrity.py --normalize realbins/btc_kraken_bins.json --out-dir realbins_norm
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
from statistics import median

# A second is a "reconnect-replay spike" suspect if its n_trades exceeds both a
# multiple of the median non-empty rate AND an absolute floor (so thin venues with
# median 1-2 aren't tripped by ordinary small bursts).
SPIKE_K = 20
SPIKE_FLOOR = 50


def _load(path: str) -> dict[int, dict]:
    with open(path) as f:
        raw = json.load(f)
    return {int(float(k)): v for k, v in raw.items()}


def audit(path: str) -> dict:
    bins = _load(path)
    ts = sorted(bins)
    n = len(ts)
    if n == 0:
        return {"file": os.path.basename(path), "bins": 0, "empty": True}
    span = ts[-1] - ts[0] + 1
    present = set(ts)
    missing = span - n

    nt = [bins[t].get("n_trades", 0) or 0 for t in ts]
    nonzero = [x for x in nt if x > 0]
    empty = n - len(nonzero)
    med = median(nonzero) if nonzero else 0.0
    thr = max(SPIKE_K * med, SPIKE_FLOOR)
    spikes = [t for t in ts if (bins[t].get("n_trades", 0) or 0) > thr]

    # consecutive identical non-zero signatures (buy,sell,mid,n_trades) — stale/dupe fills
    dup_consec = 0
    prev = None
    for t in ts:
        b = bins[t]
        if (b.get("n_trades", 0) or 0) > 0:
            sig = (b.get("mid"), b.get("buy"), b.get("sell"), b.get("n_trades"))
            if sig == prev:
                dup_consec += 1
            prev = sig
        else:
            prev = None

    gaps = [ts[i + 1] - ts[i] for i in range(n - 1)]
    max_gap = max(gaps) if gaps else 0
    big_gaps = sum(1 for g in gaps if g > 60)

    return {
        "file": os.path.basename(path),
        "bins": n,
        "span_s": span,
        "coverage_pct": round(100.0 * n / span, 1),
        "missing_s": missing,
        "empty": empty,
        "empty_pct": round(100.0 * empty / n, 1),
        "dup_consec": dup_consec,
        "median_nt": med,
        "spike_seconds": len(spikes),
        "spike_threshold": thr,
        "spike_examples": [{"ts": t, "n_trades": bins[t].get("n_trades")} for t in spikes[:5]],
        "max_gap_s": max_gap,
        "gaps_over_60s": big_gaps,
        "range_utc": [
            dt.datetime.utcfromtimestamp(ts[0]).strftime("%Y-%m-%d %H:%M:%S"),
            dt.datetime.utcfromtimestamp(ts[-1]).strftime("%Y-%m-%d %H:%M:%S"),
        ],
    }


def normalize(path: str, out_dir: str) -> dict:
    """Re-grid to a regular 1-second grid: real bins verbatim, explicit zero-bins for
    truly-empty seconds, suspect spike-seconds flagged with "_suspect": True."""
    bins = _load(path)
    ts = sorted(bins)
    if not ts:
        return {"file": os.path.basename(path), "skipped": "empty"}
    nonzero = [bins[t].get("n_trades", 0) or 0 for t in ts if (bins[t].get("n_trades", 0) or 0) > 0]
    med = median(nonzero) if nonzero else 0.0
    thr = max(SPIKE_K * med, SPIKE_FLOOR)

    out: dict[str, dict] = {}
    added_zero = 0
    flagged = 0
    last_mid = None
    for t in range(ts[0], ts[-1] + 1):
        if t in bins:
            b = dict(bins[t])
            if (b.get("n_trades", 0) or 0) > thr:
                b["_suspect"] = True
                flagged += 1
            mid = b.get("mid")
            if mid:
                last_mid = mid
            out[str(float(t))] = b
        else:
            # truly-empty second: explicit zero-bin, mid forward-filled (no fake volume)
            out[str(float(t))] = {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                  "high": 0.0, "low": 0.0, "n_trades": 0}
            added_zero += 1

    os.makedirs(out_dir, exist_ok=True)
    outp = os.path.join(out_dir, os.path.basename(path))
    with open(outp, "w") as f:
        json.dump(out, f)
    return {"file": os.path.basename(path), "out": outp, "grid_seconds": len(out),
            "zero_bins_added": added_zero, "suspect_flagged": flagged}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", nargs="+", help="bins JSON files (globs ok) to audit")
    ap.add_argument("--normalize", nargs="+", help="bins JSON files (globs ok) to re-grid")
    ap.add_argument("--out-dir", default="realbins_norm", help="output dir for --normalize")
    ap.add_argument("--json", help="write the --report rows to this JSON path")
    args = ap.parse_args()

    def expand(patterns):
        out = []
        for p in patterns:
            out.extend(sorted(glob.glob(p)) or [p])
        return out

    if args.report:
        rows = [audit(p) for p in expand(args.report)]
        hdr = f"{'file':28s}{'bins':>9s}{'cov%':>7s}{'miss_s':>8s}{'empt%':>7s}{'dupC':>6s}{'spikes':>8s}"
        print(hdr); print("-" * len(hdr))
        for r in rows:
            if r.get("bins", 0) == 0:
                print(f"{r['file']:28s}   EMPTY"); continue
            print(f"{r['file']:28s}{r['bins']:>9d}{r['coverage_pct']:>7.1f}{r['missing_s']:>8d}"
                  f"{r['empty_pct']:>7.1f}{r['dup_consec']:>6d}{r['spike_seconds']:>8d}")
        if args.json:
            with open(args.json, "w") as f:
                json.dump(rows, f, indent=2)
            print(f"\n[report] wrote {args.json}")

    if args.normalize:
        for p in expand(args.normalize):
            res = normalize(p, args.out_dir)
            print(f"[normalize] {res}")


if __name__ == "__main__":
    main()
