"""
markets_bar_loader.py
DavisAI - Canonical bar loader for the Markets refrag adapters.

Solves the rolling-window coverage problem:
  E:\\Markets\\live_data\\*_bins.json is a fixed ~6-hour LRU snapshot. Bars
  outside that window get evicted continuously. The per-trade adapter saw
  68% skip rate on the first full run because winners spanning a 5-6h
  history were being processed while the bar window slid forward.

This loader reads from the append-only archive:
  E:\\Markets\\live_data_history\\<YYYY-MM-DD>\\<asset>_<venue>_bins.jsonl
which is partitioned by UTC date and never trimmed. Then it unions in the
current live_data snapshot for the bars that haven't been flushed yet.

That makes ANY winner whose [entry_ts, exit_ts] falls within accumulated
archive coverage processable, regardless of when the pipeline runs.

Usage:
    from markets_bar_loader import TimedClose, load_closes, slice_closes
    closes = load_closes(asset="BTC", venue="Bybit", t_min=..., t_max=...)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MARKETS_ROOT = Path(r"E:\Markets")
HISTORY_ROOT = MARKETS_ROOT / "live_data_history"
LIVE_ROOT = MARKETS_ROOT / "live_data"


@dataclass(frozen=True)
class TimedClose:
    ts: float
    close: float


def _venue_stem(asset: str, venue: str) -> str:
    v = venue.lower()
    if v == "bybit":
        return f"{asset.lower()}_bybit_perp"
    return f"{asset.lower()}_{v}"


def _bar_price(bar: dict) -> float | None:
    p = bar.get("mid") or bar.get("close") or bar.get("bid") or bar.get("ask")
    if p is None:
        return None
    try:
        f = float(p)
    except (ValueError, TypeError):
        return None
    return f if f > 0 else None


def _date_range_dirs(t_min: float, t_max: float) -> list[Path]:
    """Return existing live_data_history/<date>/ dirs covering [t_min, t_max] (UTC)."""
    if not HISTORY_ROOT.exists():
        return []
    if not math.isfinite(t_min) or not math.isfinite(t_max):
        # Fall back to scanning all available date dirs.
        return [d for d in sorted(HISTORY_ROOT.iterdir()) if d.is_dir()]
    d0 = datetime.fromtimestamp(t_min, tz=timezone.utc).date()
    d1 = datetime.fromtimestamp(t_max, tz=timezone.utc).date()
    out: list[Path] = []
    d = d0
    while d <= d1:
        p = HISTORY_ROOT / d.strftime("%Y-%m-%d")
        if p.exists() and p.is_dir():
            out.append(p)
        d += timedelta(days=1)
    return out


def _read_jsonl_closes(path: Path) -> dict[float, float]:
    """Stream a *_bins.jsonl archive file -> {ts: close} dict."""
    out: dict[float, float] = {}
    if not path.exists():
        return out
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                bar = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                ts = float(bar.get("ts"))
            except (TypeError, ValueError):
                continue
            p = _bar_price(bar)
            if p is not None:
                out[ts] = p
    return out


def _read_live_snapshot_closes(path: Path) -> dict[float, float]:
    """Read live_data/<...>_bins.json (dict keyed by ts_str) -> {ts: close}."""
    out: dict[float, float] = {}
    if not path.exists():
        return out
    try:
        raw = json.load(path.open())
    except json.JSONDecodeError:
        return out
    if not isinstance(raw, dict):
        return out
    for ts_str, bar in raw.items():
        try:
            ts = float(ts_str)
        except (TypeError, ValueError):
            continue
        if not isinstance(bar, dict):
            continue
        p = _bar_price(bar)
        if p is not None:
            out[ts] = p
    return out


def load_closes(
    asset: str,
    venue: str,
    t_min: float = 0.0,
    t_max: float = math.inf,
    use_live_snapshot: bool = True,
) -> list[TimedClose]:
    """Return time-sorted closes for (asset, venue) covering [t_min, t_max].

    Reads the append-only JSONL archive for each UTC date in the range, then
    unions in the current live_data snapshot. Dedupes by ts (later writes
    win, which means live_data overrides archive for shared timestamps - good
    because live_data is the most current rebuild). Filters to [t_min, t_max]
    inclusive.

    asset:  "BTC", "ETH", etc.
    venue:  "Bybit", "Coinbase", "Kraken" (case-insensitive)
    """
    stem = _venue_stem(asset, venue)

    combined: dict[float, float] = {}
    for d in _date_range_dirs(t_min, t_max):
        path = d / f"{stem}_bins.jsonl"
        combined.update(_read_jsonl_closes(path))

    if use_live_snapshot:
        live_path = LIVE_ROOT / f"{stem}_bins.json"
        combined.update(_read_live_snapshot_closes(live_path))

    if not combined:
        return []

    out: list[TimedClose] = []
    for ts in sorted(combined.keys()):
        if ts < t_min or ts > t_max:
            continue
        out.append(TimedClose(ts=ts, close=combined[ts]))
    return out


def slice_closes(closes: list[TimedClose], ts0: float, ts1: float) -> list[float]:
    """Inclusive slice [ts0, ts1] of a ts-sorted TimedClose list."""
    if not closes:
        return []
    import bisect
    ts_list = [c.ts for c in closes]
    i0 = bisect.bisect_left(ts_list, ts0)
    i1 = bisect.bisect_right(ts_list, ts1)
    return [c.close for c in closes[i0:i1]]


def closes_to_log_returns(closes: list[float]) -> list[float]:
    """Log returns from a close-price stream. Skips invalid pairs."""
    if len(closes) < 2:
        return []
    out: list[float] = []
    prev = closes[0]
    for c in closes[1:]:
        if prev > 0 and c > 0:
            out.append(math.log(c / prev))
        prev = c
    return out


# ---------------------------------------------------------------------------
# CLI diagnostic: report coverage per (asset, venue) for a given winner JSON.
# ---------------------------------------------------------------------------

def _diagnostic():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--winner-json",
        type=Path,
        default=MARKETS_ROOT / "research" / "strategy_evolution" / "oracle_winner_trade_list.json",
    )
    args = ap.parse_args()

    with args.winner_json.open() as f:
        entries = json.load(f)["entries"]
    print(f"{len(entries)} winners in {args.winner_json}")

    from collections import defaultdict
    by_av: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for e in entries:
        by_av[(e["asset"], e["venue"])].append(e)

    def fmt(ts: float) -> str:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    grand_total = 0
    grand_covered = 0
    grand_early = 0
    grand_late = 0
    for av in sorted(by_av):
        es = by_av[av]
        t_min_ent = min(float(e["entry_ts_utc"]) for e in es)
        t_max_ent = max(
            float(e["entry_ts_utc"]) + float(e.get("horizon_minutes") or 0) * 60
            for e in es
        )
        # Wide buffer (6 hours each side) so we surface the archive's actual
        # reach; per-winner coverage check is done by the caller.
        closes = load_closes(av[0], av[1], t_min=t_min_ent - 6 * 3600, t_max=t_max_ent + 6 * 3600)
        if not closes:
            print(f"  {av[0]}/{av[1]:<8}: NO BARS")
            continue
        fst, lst = closes[0].ts, closes[-1].ts
        n_total = len(es)
        n_early = sum(1 for e in es if float(e["entry_ts_utc"]) < fst)
        n_late = sum(
            1 for e in es
            if float(e["entry_ts_utc"]) + float(e.get("horizon_minutes") or 0) * 60 > lst
        )
        n_covered = sum(
            1 for e in es
            if float(e["entry_ts_utc"]) >= fst
            and float(e["entry_ts_utc"]) + float(e.get("horizon_minutes") or 0) * 60 <= lst
        )
        grand_total += n_total
        grand_covered += n_covered
        grand_early += n_early
        grand_late += n_late
        print(f"  {av[0]}/{av[1]:<8}  bars={len(closes):>6}  range={fmt(fst)} -> {fmt(lst)}")
        print(f"    winners total={n_total:>4}  covered={n_covered:>4}  "
              f"early_miss={n_early:>4}  late_miss={n_late:>4}")
    print()
    print(f"GRAND TOTAL: {grand_covered}/{grand_total} covered  "
          f"(early_miss={grand_early}, late_miss={grand_late})")


if __name__ == "__main__":
    _diagnostic()
