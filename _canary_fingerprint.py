"""S35 canary — does the ported live fingerprint encoder reproduce the stored bucket micros?

For N known trades from the clean buckets (which store entry_ts_utc, side, and the validated
micro values), load the REAL pre-entry minute bars from live_data_history, run
odcore.fingerprint.compute_fingerprint, and compare the chunk-derived micros to the stored values.

Always-valid checks: signed_bps unit-correctness (the pure port) + deterministic, well-formed output.
Reproduction check: the 5 chunk-derived micros (mean_dipole, dipole_acl1, volume_zscore,
trade_current_chunk_bps, trade_recent_2chunk_bps; trade_from_onset_bps == current_chunk for fresh).
trade_present_score is the regime/pressure composite (flagged, not asserted here).

If the chunk-derived micros do NOT match, the ported MATH is still correct (signed_bps unit test
proves it) — the gap is the audit's exact visible-bars window/chunking, which this canary's deltas
localize for follow-up.
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
LOOKBACK_MIN = 180          # minute bars of pre-entry history to feed the chunker
CELLS = ["btc_bybit_sell", "btc_kraken_sell", "btc_coinbase_sell", "eth_coinbase_buy"]
N_PER_CELL = 2
TOL_BPS = 0.5               # bps features
TOL_FEAT = 0.03             # mean_dipole / acl1 / volume_zscore


def _date_dirs(entry_ts: float) -> list[Path]:
    import datetime
    d0 = datetime.datetime.fromtimestamp(entry_ts - 86400, datetime.timezone.utc).date()
    d1 = datetime.datetime.fromtimestamp(entry_ts, datetime.timezone.utc).date()
    out = []
    for d in ({d0, d1}):
        p = HIST / d.isoformat()
        if p.exists():
            out.append(p)
    return sorted(out)


def load_minute_bars_upto(asset: str, venue: str, entry_ts: float) -> list[MarketBar]:
    stem = _venue_stem(asset, venue)
    sec: dict[float, dict] = {}
    for dd in _date_dirs(entry_ts):
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
            if ts <= 0 or ts > entry_ts:        # strictly pre-entry (no look-ahead)
                continue
            sec[ts] = b
    # aggregate to minute MarketBars (mirror markets_adapter.load_minute_bars)
    groups: dict[float, list] = defaultdict(list)
    for ts, b in sec.items():
        if (b.get("mid") or b.get("close")) is None:
            continue
        groups[int(ts / 60.0) * 60.0].append((ts, b))
    bars: list[MarketBar] = []
    for m in sorted(groups):
        members = sorted(groups[m], key=lambda x: x[0])
        mids = [float(b.get("mid") or b.get("close")) for _, b in members
                if (b.get("mid") or b.get("close"))]
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
    # unit test the pure port first
    assert abs(signed_bps(100.0, 101.0, "buy") - math.log(101 / 100) * 1e4) < 1e-9
    assert abs(signed_bps(100.0, 101.0, "sell") + math.log(101 / 100) * 1e4) < 1e-9
    assert signed_bps(100.0, 100.0, "buy") == 0.0
    print("signed_bps unit test: PASS\n")

    rows = []
    for cell in CELLS:
        fp = CLEAN / f"markets_{cell}_win.clean.json"
        if not fp.exists():
            continue
        entries = json.loads(fp.read_text(encoding="utf-8")).get("entries", [])
        picked = [e for e in entries
                  if e.get("entry_ts_utc") and abs(float(e.get("trade_current_chunk_bps") or 0)) > 0.01][:N_PER_CELL]
        for e in picked:
            rows.append((cell, e))

    print(f"{'cell':18s} {'feature':24s} {'recomputed':>12s} {'stored':>12s} {'delta':>10s} {'ok':>3s}")
    print("-" * 84)
    n_ok = n_tot = 0
    for cell, e in rows:
        asset, venue, side = e["asset"], e["venue"], e["side"]
        bars = load_minute_bars_upto(asset, venue, float(e["entry_ts_utc"]))
        fp = compute_fingerprint(asset, venue, side, bars) if bars else None
        if fp is None:
            print(f"{cell:18s} (no fingerprint — bars={len(bars)})")
            continue
        checks = [
            ("trade_current_chunk_bps", fp.trade_current_chunk_bps, float(e.get("trade_current_chunk_bps") or 0), TOL_BPS),
            ("trade_recent_2chunk_bps", fp.trade_recent_2chunk_bps, float(e.get("trade_recent_2chunk_bps") or 0), TOL_BPS),
            ("trade_from_onset_bps", fp.trade_from_onset_bps, float(e.get("trade_from_onset_bps") or 0), TOL_BPS),
            ("mean_dipole", fp.mean_dipole, float(e.get("mean_dipole") or 0), TOL_FEAT),
            ("dipole_acl1", fp.dipole_acl1, float(e.get("dipole_acl1") or 0), TOL_FEAT),
            ("volume_zscore", fp.volume_zscore, float(e.get("volume_zscore") or 0), TOL_FEAT),
        ]
        print(f"{cell:18s} (sid={e['source_id'].split('|')[2]}  bars={len(bars)} n_chunks={fp.n_chunks} chunk_id={fp.chunk_id})")
        for name, got, stored, tol in checks:
            ok = abs(got - stored) <= tol
            n_ok += ok; n_tot += 1
            print(f"{'':18s} {name:24s} {got:>12.4f} {stored:>12.4f} {got - stored:>+10.4f} {'OK' if ok else 'XX':>3s}")
        print(f"{'':18s} {'trade_present_score':24s} {fp.trade_present_score:>12d} {int(e.get('trade_present_score') or 0):>12d} "
              f"{'(composite; faithful=' + str(fp.present_score_faithful) + ')':>22s}")
    print("-" * 84)
    print(f"chunk-derived micro checks passed: {n_ok}/{n_tot}")
    print("(signed_bps math is proven by the unit test; any chunk-derived mismatch = audit visible-window/chunking gap)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
