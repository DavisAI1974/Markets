from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from news_coupling_research import (
    VENUES,
    build_news_dipole_events,
    load_events,
    load_market,
    nearest_idx,
)


def signed_bps(entry: float, exit_: float, side: str) -> float:
    if entry <= 0 or exit_ <= 0:
        return 0.0
    sign = 1 if side == "buy" else -1 if side == "sell" else 0
    return sign * math.log(max(exit_, 1e-12) / max(entry, 1e-12)) * 10000.0


def global_market_window(market: dict[tuple[str, str], dict[str, Any]]) -> tuple[float, float]:
    starts = [pack["ts"][0] for pack in market.values() if pack.get("ts")]
    ends = [pack["ts"][-1] for pack in market.values() if pack.get("ts")]
    if not starts or not ends:
        return 0.0, 0.0
    return min(starts), max(ends)


def run_replay(
    *,
    data_dir: Path,
    events_path: Path,
    assets: list[str],
    start_hour: float,
    hours: float,
    hold_minutes: float,
    min_abs_dipole: float,
    notional: float,
    fee_bps: float,
    bucket_min: int,
) -> dict[str, Any]:
    market = load_market(data_dir, assets)
    events = load_events(events_path)
    dipoles = build_news_dipole_events(events, bucket_min)
    global_start, _global_end = global_market_window(market)
    start_ts = global_start + start_hour * 3600.0
    end_ts = start_ts + hours * 3600.0
    trades: list[dict[str, Any]] = []

    for event in dipoles:
        event_ts = float(event["published_ts"])
        if event_ts < start_ts or event_ts >= end_ts:
            continue
        dipole = float(event.get("news_dipole") or 0.0)
        if abs(dipole) < min_abs_dipole:
            continue
        side = "buy" if dipole > 0 else "sell"
        asset = str((event.get("assets") or [""])[0]).upper()
        for venue in VENUES.get(asset, {}):
            pack = market.get((asset, venue))
            if not pack:
                continue
            bars = pack["bars"]
            ts_list = pack["ts"]
            entry_idx = nearest_idx(ts_list, event_ts)
            exit_idx = nearest_idx(ts_list, event_ts + hold_minutes * 60.0)
            if entry_idx < 0 or exit_idx <= entry_idx:
                continue
            entry = float(bars[entry_idx].close)
            exit_ = float(bars[exit_idx].close)
            if entry <= 0 or exit_ <= 0:
                continue
            qty = notional / entry
            gross = (exit_ - entry) * qty if side == "buy" else (entry - exit_) * qty
            fees = notional * (fee_bps / 10000.0) + (exit_ * qty) * (fee_bps / 10000.0)
            pnl = gross - fees
            trades.append({
                "event_id": event["event_id"],
                "asset": asset,
                "venue": venue,
                "side": side,
                "news_dipole": dipole,
                "source_count": event.get("source_count", 0),
                "title": event.get("title", ""),
                "summary": event.get("summary", ""),
                "entry_ts": float(bars[entry_idx].ts),
                "exit_ts": float(bars[exit_idx].ts),
                "entry_iso": datetime.fromtimestamp(float(bars[entry_idx].ts), timezone.utc).isoformat(),
                "exit_iso": datetime.fromtimestamp(float(bars[exit_idx].ts), timezone.utc).isoformat(),
                "entry_price": entry,
                "exit_price": exit_,
                "notional": notional,
                "qty": qty,
                "fee_bps": fee_bps,
                "signed_bps": signed_bps(entry, exit_, side),
                "realized_pnl_usd": pnl,
            })

    closed = trades
    wins = sum(1 for t in closed if float(t["realized_pnl_usd"]) > 0)
    pnl = sum(float(t["realized_pnl_usd"]) for t in closed)
    by_asset = Counter(t["asset"] for t in closed)
    by_side = Counter(t["side"] for t in closed)
    by_venue = Counter(f"{t['asset']}/{t['venue']}" for t in closed)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events_path": str(events_path),
        "start_hour": start_hour,
        "hours": hours,
        "hold_minutes": hold_minutes,
        "min_abs_dipole": min_abs_dipole,
        "notional": notional,
        "fee_bps": fee_bps,
        "n_news_events": len(events),
        "n_news_dipoles": len(dipoles),
        "n_trades": len(closed),
        "wins": wins,
        "win_rate": round(wins / len(closed), 3) if closed else None,
        "realized_pnl_usd": round(pnl, 4),
        "avg_trade_pnl_usd": round(mean([float(t["realized_pnl_usd"]) for t in closed]), 4) if closed else 0.0,
        "by_asset": dict(by_asset),
        "by_side": dict(by_side),
        "by_venue": dict(by_venue),
        "trades": trades,
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    win_text = "n/a" if payload["win_rate"] is None else f"{payload['win_rate'] * 100:.1f}%"
    lines = [
        "# News Dipole Replay",
        "",
        f"Window: start hour {payload['start_hour']:g}, length {payload['hours']:g}h",
        f"Hold: {payload['hold_minutes']:g} minutes",
        f"Min abs news dipole: {payload['min_abs_dipole']}",
        "",
        f"News events: {payload['n_news_events']}",
        f"News dipole buckets: {payload['n_news_dipoles']}",
        f"Trades: {payload['n_trades']}",
        f"Win rate: {win_text}",
        f"Realized P&L: ${payload['realized_pnl_usd']:.2f}",
        "",
        "| Asset | Venue | Side | Dipole | Entry UTC | Exit UTC | Bps | P&L | Title |",
        "|---|---|---:|---:|---|---|---:|---:|---|",
    ]
    for t in payload["trades"][:80]:
        lines.append(
            f"| {t['asset']} | {t['venue']} | {t['side']} | {t['news_dipole']:.3f} | "
            f"{t['entry_iso']} | {t['exit_iso']} | {t['signed_bps']:.2f} | "
            f"${t['realized_pnl_usd']:.2f} | {str(t['title'])[:80]} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default=".")
    p.add_argument("--events", default="news_events.jsonl")
    p.add_argument("--output-dir", default="news_dipole_replay_out")
    p.add_argument("--assets", nargs="*", default=["BTC", "ETH"])
    p.add_argument("--start-hour", type=float, default=0.0)
    p.add_argument("--hours", type=float, default=24.0)
    p.add_argument("--hold-minutes", type=float, default=60.0)
    p.add_argument("--min-abs-dipole", type=float, default=0.1)
    p.add_argument("--notional", type=float, default=500.0)
    p.add_argument("--fee-bps", type=float, default=5.0)
    p.add_argument("--bucket-min", type=int, default=60)
    args = p.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = run_replay(
        data_dir=Path(args.data_dir),
        events_path=Path(args.events),
        assets=[a.upper() for a in args.assets],
        start_hour=float(args.start_hour),
        hours=float(args.hours),
        hold_minutes=float(args.hold_minutes),
        min_abs_dipole=float(args.min_abs_dipole),
        notional=float(args.notional),
        fee_bps=float(args.fee_bps),
        bucket_min=int(args.bucket_min),
    )
    json_path = output_dir / "news_dipole_replay_results.json"
    report_path = output_dir / "news_dipole_replay_report.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(report_path, payload)
    print(f"[news-dipole-replay] trades={payload['n_trades']} pnl={payload['realized_pnl_usd']}")
    print(f"[news-dipole-replay] wrote {json_path}")
    print(f"[news-dipole-replay] wrote {report_path}")


if __name__ == "__main__":
    main()
