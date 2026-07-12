"""
kalshi_coupling_adapter.py — feed Kalshi JSONL bins into news_coupling_research.py.

Step 4 of the S78 Kalshi build (KALSHI_BUILD_SCOPE.md): the coupling engine
(news_coupling_research.py) already measures signed edge vs a random-time placebo +
hit-rate per horizon/category. It was written for crypto bars from
phase1_5_evaluator.load_bars (objects with .ts/.close/.buy_vol/.sell_vol/.n_trades and a
market dict keyed by (asset, venue)). This adapter produces the SAME structure from Kalshi
per-series JSONL bins, so the coupling code runs UNCHANGED — only the loader is swapped.

What "price" couples to news on Kalshi: the contract's MID-PROBABILITY (cents, 0-100). A
tagged EIA/CPI/FOMC event should move its contract's probability beyond the placebo
baseline — that is the whole thesis, and this makes it testable with the existing engine.

Mapping onto (asset, venue):
  asset  = Kalshi SERIES ticker (e.g. KXFEDHIKE) — what news_ingest tags in `assets`.
  venue  = the specific MARKET ticker (strike, e.g. KXFEDHIKE-26JUL-25) — each is its own
           probability series. Macro/binary front contracts persist for weeks and accrue
           the history coupling needs; short-lived daily weather strikes naturally produce
           series too short for the horizon filter (fine — weather is the OD thread).

Trade flow: Kalshi snapshots carry the BOOK, not trades, so buy_vol/sell_vol/n_trades = 0
(flow_dipole / volume_ratio columns become N/A). The signed-bps-vs-placebo gate — the
actual decision gate — is fully intact off `mid`. (A future pass can add trade flow via the
/markets/{ticker}/trades endpoint.)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Macro/binary contracts where mid-probability is the news-coupled signal (weather excluded
# on purpose — served by the OD-weather thread). Mirrors news_ingest_rss CONTRACT_KEYWORDS.
DEFAULT_MACRO_SERIES = [
    "KXUSNFP", "KXCPIYOY", "KXCPICOREA", "PCECORE",
    "KXFEDHIKE", "RATECUTS", "KXEFFR", "KXTROPSTORM",
]


class KBar:
    """Minimal bar exposing exactly what analyze_event/window_stats read.
    close = mid-probability in cents; no trade flow in Kalshi snapshots -> zeros."""

    __slots__ = ("ts", "close", "buy_vol", "sell_vol", "n_trades")

    def __init__(self, ts: float, close: float):
        self.ts = float(ts)
        self.close = float(close)
        self.buy_vol = 0.0
        self.sell_vol = 0.0
        self.n_trades = 0


def _series_file(data_dir: Path, series: str) -> Path:
    return data_dir / f"{series}_bins.jsonl"


def load_series_bins(path: Path, two_sided_only: bool = True) -> dict[str, list[KBar]]:
    """Read one <SERIES>_bins.jsonl -> {market_ticker: [KBar,...] sorted by ts}.
    Keeps only rows with a real mid (and a two-sided book when two_sided_only)."""
    by_ticker: dict[str, list[tuple[float, float]]] = {}
    if not path.exists():
        return {}
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            mid = r.get("mid")
            ts = r.get("ts")
            tkr = r.get("ticker")
            if mid is None or ts is None or not tkr:
                continue
            if two_sided_only and not r.get("book_ok"):
                continue
            if not (0.0 < float(mid) < 100.0):     # drop degenerate 0/100 settled prints
                continue
            by_ticker.setdefault(tkr, []).append((float(ts), float(mid)))
    out: dict[str, list[KBar]] = {}
    for tkr, pts in by_ticker.items():
        pts.sort(key=lambda x: x[0])
        # collapse duplicate timestamps (keep last)
        dedup: dict[float, float] = {}
        for ts, mid in pts:
            dedup[ts] = mid
        out[tkr] = [KBar(ts, dedup[ts]) for ts in sorted(dedup)]
    return out


def load_kalshi_market(
    data_dir: Path,
    series_list: list[str],
    min_snaps: int = 20,
    two_sided_only: bool = True,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Kalshi analogue of news_coupling_research.load_market.
    Returns {(series, market_ticker): {"bars": [KBar], "ts": [float]}} for every market with
    at least `min_snaps` snapshots (enough history to fit a forward horizon)."""
    market: dict[tuple[str, str], dict[str, Any]] = {}
    for series in series_list:
        by_ticker = load_series_bins(_series_file(data_dir, series), two_sided_only)
        for tkr, bars in by_ticker.items():
            if len(bars) < min_snaps:
                continue
            market[(series, tkr)] = {"bars": bars, "ts": [b.ts for b in bars]}
    return market


def available_series(data_dir: Path) -> list[str]:
    """Series that actually have a bins file on disk (for --assets defaulting)."""
    if not data_dir.exists():
        return []
    return sorted(
        f[: -len("_bins.jsonl")]
        for f in os.listdir(data_dir)
        if f.endswith("_bins.jsonl")
    )
