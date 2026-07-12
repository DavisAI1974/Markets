from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from phase1_5_evaluator import load_bars


VENUES = {
    "BTC": {
        "Coinbase": "btc_coinbase_bins.json",
        "Kraken": "btc_kraken_bins.json",
        "Bybit": "btc_bybit_perp_bins.json",
    },
    "ETH": {
        "Coinbase": "eth_coinbase_bins.json",
        "Kraken": "eth_kraken_bins.json",
        "Bybit": "eth_bybit_perp_bins.json",
    },
}

BIAS_SIGN = {
    "BULLISH": 1,
    "BEARISH": -1,
}

SOURCE_WEIGHTS = {
    "PRIMARY": 1.0,
    "EXCHANGE_PRIMARY": 0.95,
    "PROTOCOL_PRIMARY": 0.9,
    "TRUSTED_MEDIA": 0.8,
    "AGGREGATOR": 0.6,
    "SOCIAL": 0.35,
}


def parse_ts(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).timestamp()


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def signed_bps(entry: float, exit_: float, sign: int) -> float:
    if entry <= 0 or exit_ <= 0 or sign == 0:
        return 0.0
    return sign * math.log(max(exit_, 1e-12) / max(entry, 1e-12)) * 10000.0


def raw_bps(entry: float, exit_: float) -> float:
    if entry <= 0 or exit_ <= 0:
        return 0.0
    return math.log(max(exit_, 1e-12) / max(entry, 1e-12)) * 10000.0


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            assets = [str(a).upper() for a in raw.get("assets", [])]
            if not assets:
                asset = str(raw.get("asset") or "").upper()
                assets = [asset] if asset else []
            ts = parse_ts(raw.get("published_at") or raw.get("ts") or raw.get("timestamp"))
            if ts <= 0 or not assets:
                continue
            dedupe = str(raw.get("dedupe_key") or raw.get("event_id") or f"line-{line_no}")
            key = f"{dedupe}:{','.join(sorted(assets))}"
            if key in seen:
                continue
            seen.add(key)
            raw["assets"] = assets
            raw["published_ts"] = ts
            raw["directional_bias"] = str(raw.get("directional_bias") or "UNKNOWN").upper()
            raw["source_quality"] = str(raw.get("source_quality") or "UNKNOWN").upper()
            raw["category"] = str(raw.get("category") or "UNKNOWN").upper()
            raw["confidence"] = float(raw.get("confidence") or 0.5)
            raw["impact"] = float(raw.get("impact") or 0.5)
            raw["event_id"] = str(raw.get("event_id") or hashlib.sha1(key.encode()).hexdigest()[:12])
            events.append(raw)
    events.sort(key=lambda e: e["published_ts"])
    return events


def load_market(data_dir: Path, assets: list[str]) -> dict[tuple[str, str], dict[str, Any]]:
    market: dict[tuple[str, str], dict[str, Any]] = {}
    for asset in assets:
        for venue, filename in VENUES.get(asset, {}).items():
            path = data_dir / filename
            if not path.exists():
                continue
            bars = load_bars(str(path))
            if not bars:
                continue
            ts = [float(b.ts) for b in bars]
            market[(asset, venue)] = {"bars": bars, "ts": ts}
    return market


def nearest_idx(ts_list: list[float], ts: float) -> int:
    if not ts_list:
        return -1
    i = bisect.bisect_left(ts_list, ts)
    if i <= 0:
        return 0
    if i >= len(ts_list):
        return len(ts_list) - 1
    return i if abs(ts_list[i] - ts) < abs(ts_list[i - 1] - ts) else i - 1


def window_stats(bars: list[Any], ts_list: list[float], start_ts: float, end_ts: float) -> dict[str, float]:
    lo = bisect.bisect_left(ts_list, start_ts)
    hi = bisect.bisect_right(ts_list, end_ts)
    rows = bars[lo:hi]
    if not rows:
        return {"n": 0, "volume": 0.0, "flow_dipole": 0.0, "n_trades": 0}
    buy = sum(float(b.buy_vol) for b in rows)
    sell = sum(float(b.sell_vol) for b in rows)
    vol = buy + sell
    return {
        "n": len(rows),
        "volume": vol,
        "flow_dipole": (buy - sell) / (vol + 1e-9) if vol > 0 else 0.0,
        "n_trades": sum(int(getattr(b, "n_trades", 0) or 0) for b in rows),
    }


def analyze_event(
    event: dict[str, Any],
    market: dict[tuple[str, str], dict[str, Any]],
    horizons_min: list[int],
    pre_window_min: int,
) -> list[dict[str, Any]]:
    rows = []
    sign = BIAS_SIGN.get(str(event.get("directional_bias") or "").upper(), 0)
    for asset in event["assets"]:
        for (m_asset, venue), pack in market.items():
            if m_asset != asset:
                continue
            bars = pack["bars"]
            ts_list = pack["ts"]
            idx = nearest_idx(ts_list, float(event["published_ts"]))
            if idx < 0:
                continue
            entry = float(bars[idx].close)
            pre = window_stats(
                bars, ts_list,
                float(event["published_ts"]) - pre_window_min * 60.0,
                float(event["published_ts"]),
            )
            for horizon in horizons_min:
                end_ts = float(event["published_ts"]) + horizon * 60.0
                end_idx = bisect.bisect_right(ts_list, end_ts) - 1
                if end_idx <= idx or end_idx >= len(bars):
                    continue
                post = window_stats(bars, ts_list, float(event["published_ts"]), end_ts)
                volume_ratio = (
                    post["volume"] / pre["volume"]
                    if pre["volume"] > 0 else None
                )
                rows.append({
                    "event_id": event["event_id"],
                    "asset": asset,
                    "venue": venue,
                    "published_at": iso(float(event["published_ts"])),
                    "source": event.get("source", ""),
                    "source_quality": event.get("source_quality", "UNKNOWN"),
                    "category": event.get("category", "UNKNOWN"),
                    "directional_bias": event.get("directional_bias", "UNKNOWN"),
                    "confidence": float(event.get("confidence") or 0.0),
                    "impact": float(event.get("impact") or 0.0),
                    "title": event.get("title", ""),
                    "horizon_min": horizon,
                    "entry_price": entry,
                    "exit_price": float(bars[end_idx].close),
                    "raw_bps": raw_bps(entry, float(bars[end_idx].close)),
                    "signed_news_bps": signed_bps(entry, float(bars[end_idx].close), sign),
                    "pre_flow_dipole": pre["flow_dipole"],
                    "post_flow_dipole": post["flow_dipole"],
                    "flow_dipole_delta": post["flow_dipole"] - pre["flow_dipole"],
                    "post_volume": post["volume"],
                    "pre_volume": pre["volume"],
                    "volume_ratio": volume_ratio,
                    "post_n_trades": post["n_trades"],
                    "bias_sign": sign,
                })
    return rows


def placebo_rows(
    events: list[dict[str, Any]],
    market: dict[tuple[str, str], dict[str, Any]],
    horizons_min: list[int],
    pre_window_min: int,
    n_per_event: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    out = []
    for ev in events:
        for asset in ev["assets"]:
            ranges = [
                (pack["ts"][0], pack["ts"][-1])
                for (m_asset, _venue), pack in market.items()
                if m_asset == asset and len(pack["ts"]) > 10
            ]
            if not ranges:
                continue
            lo = max(r[0] for r in ranges) + pre_window_min * 60.0
            hi = min(r[1] for r in ranges) - max(horizons_min) * 60.0
            if hi <= lo:
                continue
            for j in range(n_per_event):
                fake = dict(ev)
                fake["event_id"] = f"{ev['event_id']}__placebo_{j}"
                fake["published_ts"] = rng.uniform(lo, hi)
                fake["assets"] = [asset]
                for row in analyze_event(fake, market, horizons_min, pre_window_min):
                    row["placebo"] = True
                    out.append(row)
    return out


def build_news_dipole_events(events: list[dict[str, Any]], bucket_min: int) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, int], dict[str, Any]] = {}
    bucket_s = bucket_min * 60
    for event in events:
        bias = str(event.get("directional_bias") or "UNKNOWN").upper()
        if bias not in {"BULLISH", "BEARISH"}:
            continue
        source_quality = str(event.get("source_quality") or "UNKNOWN").upper()
        weight = SOURCE_WEIGHTS.get(source_quality, 0.5)
        pressure = float(event.get("confidence") or 0.5) * float(event.get("impact") or 0.5) * weight
        bucket_ts = int(float(event["published_ts"]) // bucket_s) * bucket_s
        for asset in event["assets"]:
            row = buckets.setdefault((asset, bucket_ts), {
                "event_id": f"news_dipole_{asset}_{bucket_ts}",
                "published_ts": float(bucket_ts),
                "published_at": iso(float(bucket_ts)),
                "source": "news_dipole",
                "source_quality": "COMPOSITE",
                "category": "NEWS_DIPOLE",
                "assets": [asset],
                "bullish_pressure": 0.0,
                "bearish_pressure": 0.0,
                "source_count": 0,
                "titles": [],
            })
            if bias == "BULLISH":
                row["bullish_pressure"] += pressure
            elif bias == "BEARISH":
                row["bearish_pressure"] += pressure
            row["source_count"] += 1
            if event.get("title"):
                row["titles"].append(str(event["title"])[:140])
    out = []
    for row in buckets.values():
        dipole = float(row["bullish_pressure"]) - float(row["bearish_pressure"])
        if abs(dipole) < 0.05:
            continue
        row["news_dipole"] = dipole
        row["directional_bias"] = "BULLISH" if dipole > 0 else "BEARISH"
        row["confidence"] = min(1.0, abs(dipole))
        row["impact"] = min(1.0, abs(dipole))
        row["title"] = f"{row['assets'][0]} news dipole {dipole:+.3f} from {row['source_count']} item(s)"
        row["summary"] = "; ".join(row["titles"][:3])
        out.append(row)
    out.sort(key=lambda r: r["published_ts"])
    return out


def summarize(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[tuple(row.get(k, "") for k in keys)].append(row)
    out = []
    for key, items in buckets.items():
        signed = [float(r["signed_news_bps"]) for r in items if int(r.get("bias_sign") or 0) != 0]
        raw = [float(r["raw_bps"]) for r in items]
        vols = [float(r["volume_ratio"]) for r in items if r.get("volume_ratio") is not None]
        flow = [float(r["flow_dipole_delta"]) for r in items]
        row = {k: v for k, v in zip(keys, key)}
        row.update({
            "n": len(items),
            "signed_avg_bps": round(mean(signed), 3) if signed else 0.0,
            "signed_median_bps": round(median(signed), 3) if signed else 0.0,
            "signed_hit_pct": round(100.0 * sum(1 for v in signed if v > 0) / len(signed), 2) if signed else 0.0,
            "raw_avg_bps": round(mean(raw), 3) if raw else 0.0,
            "volume_ratio_median": round(median(vols), 3) if vols else None,
            "flow_delta_avg": round(mean(flow), 4) if flow else 0.0,
        })
        out.append(row)
    out.sort(key=lambda r: (r.get("signed_avg_bps", 0.0), r.get("n", 0)), reverse=True)
    return out


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# News Coupling Research",
        "",
        "This pass tests whether timestamped BTC/ETH news events couple to forward price, volume, and trade-flow changes. It is research only; no event opens a trade by itself.",
        "",
        f"- Events loaded: {payload['n_events']}",
        f"- News dipole buckets: {payload['n_news_dipole_events']}",
        f"- Event observations: {payload['n_observations']}",
        f"- News dipole observations: {payload['n_news_dipole_observations']}",
        f"- Placebo observations: {payload['n_placebo_observations']}",
        "",
    ]
    if payload["n_events"] == 0:
        lines.extend([
            "## No Events",
            "",
            "No `news_events.jsonl` file was found, or it contained no usable rows. Use `news_events.example.jsonl` as the schema reference.",
            "",
        ])
    lines.extend([
        "## News Dipole",
        "",
        "| Horizon min | N | Signed avg bps | Signed hit | Raw avg bps | Median volume ratio | Flow delta avg |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in payload["summaries"]["news_dipole_by_horizon"]:
        lines.append(
            f"| {row['horizon_min']} | {row['n']} | {row['signed_avg_bps']:.3f} | "
            f"{row['signed_hit_pct']:.2f}% | {row['raw_avg_bps']:.3f} | "
            f"{row['volume_ratio_median'] if row['volume_ratio_median'] is not None else ''} | "
            f"{row['flow_delta_avg']:.4f} |"
        )
    lines.extend([
        "",
        "## By Horizon",
        "",
        "| Horizon min | N | Signed avg bps | Signed hit | Raw avg bps | Median volume ratio | Flow delta avg |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in payload["summaries"]["by_horizon"]:
        lines.append(
            f"| {row['horizon_min']} | {row['n']} | {row['signed_avg_bps']:.3f} | "
            f"{row['signed_hit_pct']:.2f}% | {row['raw_avg_bps']:.3f} | "
            f"{row['volume_ratio_median'] if row['volume_ratio_median'] is not None else ''} | "
            f"{row['flow_delta_avg']:.4f} |"
        )
    lines.extend([
        "",
        "## By Category",
        "",
        "| Category | Bias | Horizon | N | Signed avg bps | Signed hit | Median volume ratio |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for row in payload["summaries"]["by_category_bias_horizon"][:40]:
        lines.append(
            f"| {row['category']} | {row['directional_bias']} | {row['horizon_min']} | "
            f"{row['n']} | {row['signed_avg_bps']:.3f} | {row['signed_hit_pct']:.2f}% | "
            f"{row['volume_ratio_median'] if row['volume_ratio_median'] is not None else ''} |"
        )
    lines.extend([
        "",
        "## Placebo Check",
        "",
        "| Horizon min | N | Signed avg bps | Signed hit | Raw avg bps | Median volume ratio |",
        "|---:|---:|---:|---:|---:|---:|",
    ])
    for row in payload["summaries"]["placebo_by_horizon"]:
        lines.append(
            f"| {row['horizon_min']} | {row['n']} | {row['signed_avg_bps']:.3f} | "
            f"{row['signed_hit_pct']:.2f}% | {row['raw_avg_bps']:.3f} | "
            f"{row['volume_ratio_median'] if row['volume_ratio_median'] is not None else ''} |"
        )
    lines.extend([
        "",
        "## Interpretation Rules",
        "",
        "- Gold candidate: real events beat placebo on signed bps and volume/flow confirmation at the same horizon.",
        "- Absorption candidate: bearish news with non-negative raw bps and positive flow delta, or bullish news with non-positive raw bps and negative flow delta.",
        "- Crowding/noise candidate: high volume ratio but signed bps fails to beat placebo.",
        "- Require more samples before any rule changes auto-trade sizing.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default=".")
    p.add_argument("--events", default="news_events.jsonl")
    p.add_argument("--output-dir", default="pass23_news_coupling_out")
    p.add_argument("--assets", nargs="*", default=[])
    p.add_argument("--source", choices=["crypto", "kalshi"], default="crypto",
                   help="crypto = phase1_5 bars per (asset,venue); kalshi = mid-probability "
                        "per (series,market) from data/kalshi JSONL bins (S78 adapter)")
    p.add_argument("--min-snaps", type=int, default=20,
                   help="kalshi: min snapshots for a market to be included")
    p.add_argument("--horizons-min", nargs="*", type=int, default=[5, 15, 60, 240])
    p.add_argument("--pre-window-min", type=int, default=60)
    p.add_argument("--placebo-per-event", type=int, default=20)
    p.add_argument("--news-dipole-bucket-min", type=int, default=60)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    events = load_events(data_dir / args.events)
    if args.source == "kalshi":
        from research.kalshi.kalshi_coupling_adapter import (
            DEFAULT_MACRO_SERIES, available_series, load_kalshi_market,
        )
        series = [a.upper() for a in args.assets] or (
            [s for s in DEFAULT_MACRO_SERIES if s in set(available_series(data_dir))]
            or available_series(data_dir))
        market = load_kalshi_market(data_dir, series, min_snaps=args.min_snaps)
        print(f"[news-coupling] kalshi: {len(series)} series -> {len(market)} markets with "
              f">= {args.min_snaps} snaps")
    else:
        assets = [a.upper() for a in args.assets] or ["BTC", "ETH"]
        market = load_market(data_dir, assets)
    observations: list[dict[str, Any]] = []
    for event in events:
        observations.extend(analyze_event(event, market, args.horizons_min, args.pre_window_min))
    news_dipole_events = build_news_dipole_events(events, args.news_dipole_bucket_min)
    news_dipole_observations: list[dict[str, Any]] = []
    for event in news_dipole_events:
        news_dipole_observations.extend(analyze_event(event, market, args.horizons_min, args.pre_window_min))
    placebos = placebo_rows(
        events, market, args.horizons_min, args.pre_window_min,
        args.placebo_per_event, args.seed)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events_path": str(data_dir / args.events),
        "n_events": len(events),
        "n_news_dipole_events": len(news_dipole_events),
        "n_observations": len(observations),
        "n_news_dipole_observations": len(news_dipole_observations),
        "n_placebo_observations": len(placebos),
        "horizons_min": args.horizons_min,
        "pre_window_min": args.pre_window_min,
        "summaries": {
            "by_horizon": summarize(observations, ["horizon_min"]),
            "by_asset_horizon": summarize(observations, ["asset", "horizon_min"]),
            "by_category_bias_horizon": summarize(observations, ["category", "directional_bias", "horizon_min"]),
            "by_source_quality_horizon": summarize(observations, ["source_quality", "horizon_min"]),
            "news_dipole_by_horizon": summarize(news_dipole_observations, ["horizon_min"]),
            "news_dipole_by_asset_horizon": summarize(news_dipole_observations, ["asset", "horizon_min"]),
            "placebo_by_horizon": summarize(placebos, ["horizon_min"]),
        },
        "observations": observations,
        "news_dipole_events": news_dipole_events,
        "news_dipole_observations": news_dipole_observations,
        "placebo_observations": placebos,
    }
    json_path = output_dir / "news_coupling_results.json"
    report_path = output_dir / "news_coupling_report.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(report_path, payload)
    print(
        f"[news-coupling] events={len(events)} observations={len(observations)} "
        f"news_dipoles={len(news_dipole_events)} placebos={len(placebos)}")
    print(f"[news-coupling] wrote {json_path}")
    print(f"[news-coupling] wrote {report_path}")


if __name__ == "__main__":
    main()
