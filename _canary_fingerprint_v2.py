"""S35 canary v2 — re-anchored faithfulness test for the fingerprint encoder.

v1 (_canary_fingerprint.py) anchored the pre-entry window at the bucket's `entry_ts_utc`,
which _diag_lookahead.py proved is mis-patched (min ts_utc per non-unique chunk_id, 10-33h off)
and, worse, that the stored micros are mid-trade snapshots (look-ahead).

This v2 isolates the two effects:
  - Find each sampled WIN entry's EXACT-micro provenance row in _live_mock_opportunities.jsonl
    (so we know trade_age_chunks + the snapshot's own chunk_end_ts_utc — the correct anchor).
  - Recompute micros from minute bars with ts <= chunk_end_ts_utc (INCLUSIVE; the snapshot's
    "current" bar is information available AT the decision, not look-ahead).
  - Compare to the stored micros; report pass-rate split by onset (age==0) vs mid-trade (age>0).

Expectation if the encoder math/chunker/bar-source are correct and only the ANCHOR was wrong:
faithfulness jumps vs v1 — especially for age==0 onset snapshots, which ARE the legitimate
pre-entry fingerprint we want the platform to compute.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

WT = r"E:\Markets\.claude\worktrees\xenodochial-montalcini-f21fb6"
sys.path.insert(0, WT)
sys.path.insert(0, r"E:\refrag\adapters")

from markets_adapter import MarketBar  # noqa: E402
from markets_bar_loader import _venue_stem  # noqa: E402
from odcore.fingerprint import compute_fingerprint, signed_bps  # noqa: E402

CLEAN = Path(r"E:\Markets\research\strategy_evolution\per_bucket\clean")
HIST = Path(r"E:\Markets\live_data_history")
OPP = Path(r"E:\Markets\research\strategy_evolution\_live_mock_opportunities.jsonl")
LOOKBACK_MIN = 200
CELLS = ["btc_kraken_sell", "btc_bybit_sell", "btc_coinbase_sell", "eth_coinbase_buy",
         "btc_kraken_buy", "eth_kraken_sell"]
N_PER_CELL = 8
TOL_BPS = 0.5
TOL_FEAT = 0.03
MICRO_KEYS = ["trade_current_chunk_bps", "trade_recent_2chunk_bps", "trade_from_onset_bps",
              "mean_dipole", "dipole_acl1", "volume_zscore"]


def sig(row: dict) -> tuple:
    return tuple(round(float(row.get(k) or 0.0), 5) for k in MICRO_KEYS)


def _date_dirs(ts: float) -> list[Path]:
    import datetime
    d0 = datetime.datetime.fromtimestamp(ts - 86400, datetime.timezone.utc).date()
    d1 = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date()
    return sorted({HIST / d.isoformat() for d in (d0, d1) if (HIST / d.isoformat()).exists()})


def load_minute_bars_upto(asset: str, venue: str, anchor_ts: float) -> list[MarketBar]:
    stem = _venue_stem(asset, venue)
    sec: dict[float, dict] = {}
    for dd in _date_dirs(anchor_ts):
        fp = dd / f"{stem}_bins.jsonl"
        if not fp.exists():
            continue
        for ln in fp.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                b = json.loads(ln)
            except ValueError:
                continue
            ts = float(b.get("ts") or 0)
            if ts <= 0 or ts > anchor_ts:        # <= anchor (inclusive of the snapshot bar)
                continue
            sec[ts] = b
    groups: dict[float, list] = defaultdict(list)
    for ts, b in sec.items():
        if (b.get("mid") or b.get("close")) is None:
            continue
        groups[int(ts / 60.0) * 60.0].append((ts, b))
    bars: list[MarketBar] = []
    for m in sorted(groups):
        members = sorted(groups[m], key=lambda x: x[0])
        mids = [float(b.get("mid") or b.get("close")) for _, b in members if (b.get("mid") or b.get("close"))]
        if not mids:
            continue
        bars.append(MarketBar(
            ts=float(m), close=mids[-1], open_=mids[0], high=max(mids), low=min(mids),
            volume=float(sum((b.get("buy") or 0) + (b.get("sell") or 0) for _, b in members)),
            buy_vol=float(sum(b.get("buy") or 0 for _, b in members)),
            sell_vol=float(sum(b.get("sell") or 0 for _, b in members)),
        ))
    return bars[-LOOKBACK_MIN:] if len(bars) > LOOKBACK_MIN else bars


def main() -> int:
    assert abs(signed_bps(100.0, 101.0, "buy") - math.log(101 / 100) * 1e4) < 1e-9
    print("signed_bps unit test: PASS\n")

    # collect samples + their provenance rows
    samples = []
    want_cids: set[str] = set()
    for cell in CELLS:
        fp = CLEAN / f"markets_{cell}_win.clean.json"
        if not fp.exists():
            continue
        entries = json.loads(fp.read_text(encoding="utf-8")).get("entries", [])
        picked = [e for e in entries if abs(float(e.get("trade_current_chunk_bps") or 0)) > 0.01][:N_PER_CELL]
        for e in picked:
            samples.append((cell, e, str(e.get("chunk_id") or ""), sig(e)))
            want_cids.add(str(e.get("chunk_id") or ""))

    by_cid: dict[str, list[dict]] = defaultdict(list)
    with OPP.open(encoding="utf-8", errors="replace") as f:
        for ln in f:
            if not ln.strip() or not any(c in ln for c in want_cids):
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if str(r.get("chunk_id") or "") in want_cids:
                by_cid[str(r.get("chunk_id") or "")].append(r)

    hdr = f"{'cell':16s} {'age':>3s} {'cur_bps':>9s} {'rec_bps':>9s} {'mdip':>7s} | recomputed(cur/rec/mdip)        pass/6"
    print(hdr); print("-" * len(hdr))
    tot = ok_total = 0
    by_age = {"onset(age0)": [0, 0], "mid(age>0)": [0, 0]}   # [ok, n]
    for cell, e, cid, s in samples:
        prov = next((r for r in by_cid.get(cid, []) if sig(r) == s), None)
        if prov is None:
            continue
        age = int(float(prov.get("trade_age_chunks") or 0))
        anchor = float(prov.get("chunk_end_ts_utc") or 0)
        asset, venue, side = e["asset"], e["venue"], e["side"]
        bars = load_minute_bars_upto(asset, venue, anchor)
        fpr = compute_fingerprint(asset, venue, side, bars) if bars else None
        if fpr is None:
            print(f"{cell:16s} {age:>3d}  (no fingerprint; bars={len(bars)})")
            continue
        checks = [
            (fpr.trade_current_chunk_bps, float(e.get("trade_current_chunk_bps") or 0), TOL_BPS),
            (fpr.trade_recent_2chunk_bps, float(e.get("trade_recent_2chunk_bps") or 0), TOL_BPS),
            (fpr.trade_from_onset_bps, float(e.get("trade_from_onset_bps") or 0), TOL_BPS),
            (fpr.mean_dipole, float(e.get("mean_dipole") or 0), TOL_FEAT),
            (fpr.dipole_acl1, float(e.get("dipole_acl1") or 0), TOL_FEAT),
            (fpr.volume_zscore, float(e.get("volume_zscore") or 0), TOL_FEAT),
        ]
        npass = sum(1 for got, st, tol in checks if abs(got - st) <= tol)
        tot += 6; ok_total += npass
        bucket = "onset(age0)" if age == 0 else "mid(age>0)"
        by_age[bucket][0] += npass; by_age[bucket][1] += 6
        print(f"{cell:16s} {age:>3d} {float(e.get('trade_current_chunk_bps') or 0):>9.2f} "
              f"{float(e.get('trade_recent_2chunk_bps') or 0):>9.2f} {float(e.get('mean_dipole') or 0):>7.3f} | "
              f"{fpr.trade_current_chunk_bps:>8.2f}/{fpr.trade_recent_2chunk_bps:>8.2f}/{fpr.mean_dipole:>6.3f}  {npass}/6")
    print("-" * len(hdr))
    print(f"\nTOTAL chunk-derived checks passed: {ok_total}/{tot}")
    for k, (o, n) in by_age.items():
        if n:
            print(f"  {k:14s}: {o}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
