from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from phase1_5_evaluator import classify_venue, load_bars
from daily_news_context import adjust_present_score_with_news, load_daily_news_context


DIRECTIONAL_REGIMES = {
    "WHALE_UP",
    "WHALE_DOWN",
    "WHALE_NASCENT_UP",
    "WHALE_NASCENT_DOWN",
    "HERD_UP",
    "HERD_DOWN",
}

STRONG_REGIMES = {"WHALE_UP", "WHALE_DOWN", "HERD_UP", "HERD_DOWN"}
NASCENT_REGIMES = {"WHALE_NASCENT_UP", "WHALE_NASCENT_DOWN"}


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


def pct(x: float) -> float:
    return round(100.0 * float(x), 2)


def avg(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def med(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def regime_side(regime: str) -> str:
    if regime.endswith("_UP"):
        return "buy"
    if regime.endswith("_DOWN"):
        return "sell"
    return ""


def dipole_side(mean_dipole: float) -> str:
    if mean_dipole > 0:
        return "buy"
    if mean_dipole < 0:
        return "sell"
    return ""


def side_sign(side: str) -> int:
    return 1 if side == "buy" else -1 if side == "sell" else 0


def chunk_close(chunk: Any) -> float:
    if not getattr(chunk, "bars", None):
        return 0.0
    return float(chunk.bars[-1].close)


def chunk_start_close(chunk: Any) -> float:
    if not getattr(chunk, "bars", None):
        return 0.0
    return float(chunk.bars[0].close)


def chunk_ts_end(chunk: Any) -> float:
    if not getattr(chunk, "bars", None):
        return 0.0
    return float(chunk.bars[-1].ts)


def signed_bps(entry: float, exit_: float, side: str) -> float:
    if entry <= 0 or exit_ <= 0 or side not in ("buy", "sell"):
        return 0.0
    return side_sign(side) * math.log(max(exit_, 1e-12) / entry) * 10000.0


def pressure_watch_state(regime: str, mean_dipole: float, volume_z: float,
                         prev_mean_dipole: float | None) -> str:
    side = dipole_side(mean_dipole)
    if not side:
        return ""
    abs_d = abs(mean_dipole)
    prev_abs = abs(prev_mean_dipole) if prev_mean_dipole is not None else 0.0
    prev_same = prev_mean_dipole is not None and dipole_side(prev_mean_dipole) == side
    if regime in STRONG_REGIMES:
        return "confirmed"
    if regime in NASCENT_REGIMES:
        return "forming"
    if abs_d >= 0.30 and volume_z >= 0.0:
        return "forming"
    if 0.15 <= abs_d < 0.25 and prev_same and prev_abs >= 0.15:
        return "persistent_weak"
    if 0.15 <= abs_d:
        return "internal_watch"
    return ""


def candidate_side(regime: str, mean_dipole: float, pressure_state: str) -> str:
    if regime in DIRECTIONAL_REGIMES:
        return regime_side(regime)
    if pressure_state:
        return dipole_side(mean_dipole)
    return ""


def stage_from_age(age_chunks: int) -> str:
    if age_chunks <= 1:
        return "onset"
    if age_chunks <= 3:
        return "early_follow"
    if age_chunks <= 8:
        return "mature"
    return "late"


def score_record(rec: dict[str, Any]) -> int:
    regime = str(rec["regime"])
    score = 0.0
    score += min(35.0, float(rec["adjusted_confidence"]) * 35.0)

    if regime in STRONG_REGIMES:
        score += 25.0
    elif regime in NASCENT_REGIMES:
        score += 18.0
    elif rec["pressure_state"] in {"forming", "persistent_weak"}:
        score += 12.0
    elif rec["pressure_state"] == "internal_watch":
        score += 6.0

    abs_d = float(rec["abs_dipole"])
    if abs_d >= 0.50:
        score += 15.0
    elif abs_d >= 0.30:
        score += 10.0
    elif abs_d >= 0.15:
        score += 5.0

    volume_z = float(rec["volume_zscore"])
    if volume_z >= 1.0:
        score += 10.0
    elif volume_z >= 0.0:
        score += 6.0

    score += min(10.0, max(-12.0, float(rec["from_onset_bps"]) / 2.5))
    score += min(8.0, max(-12.0, float(rec["current_chunk_bps"]) / 2.0))

    age = int(rec["age_chunks"])
    if age >= 9:
        score -= 14.0
    elif age >= 4:
        score -= 6.0

    if float(rec["from_onset_bps"]) > 12.0 and float(rec["recent_2chunk_bps"]) <= 0.0:
        score -= 8.0
    if float(rec["from_onset_bps"]) < -8.0:
        score -= 12.0

    return int(max(0, min(100, round(score))))


def score_band(score: int) -> str:
    if score >= 85:
        return "85_100"
    if score >= 70:
        return "70_84"
    if score >= 55:
        return "55_69"
    if score >= 40:
        return "40_54"
    return "0_39"


def build_records(asset: str, venue: str, bins_path: Path,
                  *, chunk_max: int, chunk_min: int,
                  multi_signal_pelt: bool,
                  max_bars: int = 0) -> list[dict[str, Any]]:
    bars = load_bars(str(bins_path))
    if max_bars > 0 and len(bars) > max_bars:
        bars = bars[-max_bars:]
    chunks, results, _base, _session_base, feats = classify_venue(
        bars,
        f"{venue}-{asset}",
        chunk_max=chunk_max,
        chunk_min=chunk_min,
        multi_signal_pelt=multi_signal_pelt,
        compute_hawkes=False,
        compute_hurst=False,
    )
    records: list[dict[str, Any]] = []
    active_side = ""
    onset_idx = 0
    onset_price = 0.0
    for idx, (chunk, result, feat) in enumerate(zip(chunks, results, feats)):
        regime = result.regime.value
        mean_d = float(getattr(feat, "mean_dipole", 0.0) or 0.0)
        prev_d = (
            float(getattr(feats[idx - 1], "mean_dipole", 0.0) or 0.0)
            if idx > 0 else None
        )
        volume_z = float(getattr(feat, "volume_zscore", 0.0) or 0.0)
        pressure_state = pressure_watch_state(regime, mean_d, volume_z, prev_d)
        side = candidate_side(regime, mean_d, pressure_state)
        if not side:
            active_side = ""
            continue
        if side != active_side:
            active_side = side
            onset_idx = idx
            onset_price = chunk_start_close(chunk)
        close_now = chunk_close(chunk)
        recent_start = chunk_start_close(chunks[max(0, idx - 1)])
        rec = {
            "asset": asset,
            "venue": venue,
            "idx": idx,
            "ts_end": chunk_ts_end(chunk),
            "regime": regime,
            "side": side,
            "confidence": float(result.confidence),
            "adjusted_confidence": float(result.adjusted_confidence),
            "mean_dipole": mean_d,
            "abs_dipole": abs(mean_d),
            "volume_zscore": volume_z,
            "realized_vol": float(getattr(feat, "realized_vol", 0.0) or 0.0),
            "pressure_state": pressure_state,
            "age_chunks": idx - onset_idx,
            "stage": stage_from_age(idx - onset_idx),
            "from_onset_bps": signed_bps(onset_price, close_now, side),
            "current_chunk_bps": signed_bps(chunk_start_close(chunk), close_now, side),
            "recent_2chunk_bps": signed_bps(recent_start, close_now, side),
            "close": close_now,
        }
        rec["present_score"] = score_record(rec)
        rec["score_band"] = score_band(int(rec["present_score"]))
        for horizon in (1, 2, 4, 8, 16):
            fut_idx = idx + horizon
            if fut_idx < len(chunks):
                rec[f"fwd_{horizon}chunk_bps"] = signed_bps(
                    close_now, chunk_close(chunks[fut_idx]), side)
            else:
                rec[f"fwd_{horizon}chunk_bps"] = None
        records.append(rec)
    return records


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "n": len(rows),
        "avg_present_score": round(avg([float(r["present_score"]) for r in rows]), 2),
        "median_present_score": round(med([float(r["present_score"]) for r in rows]), 2),
        "avg_from_onset_bps": round(avg([float(r["from_onset_bps"]) for r in rows]), 3),
        "avg_current_chunk_bps": round(avg([float(r["current_chunk_bps"]) for r in rows]), 3),
    }
    for horizon in (1, 2, 4, 8, 16):
        vals = [
            float(r[f"fwd_{horizon}chunk_bps"])
            for r in rows
            if r.get(f"fwd_{horizon}chunk_bps") is not None
        ]
        out[f"h{horizon}_n"] = len(vals)
        out[f"h{horizon}_hit_pct"] = pct(sum(1 for v in vals if v > 0) / len(vals)) if vals else 0.0
        out[f"h{horizon}_avg_bps"] = round(avg(vals), 3)
        out[f"h{horizon}_median_bps"] = round(med(vals), 3)
    return out


def nested_summary(records: list[dict[str, Any]], *keys: str) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        buckets[tuple(rec.get(k, "") for k in keys)].append(rec)
    rows = []
    for key, items in buckets.items():
        row = {k: v for k, v in zip(keys, key)}
        row.update(summarize_group(items))
        rows.append(row)
    rows.sort(key=lambda r: (r.get("h2_avg_bps", 0.0), r.get("n", 0)), reverse=True)
    return rows


def latest_snapshot(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in records:
        latest[(rec["asset"], rec["venue"])] = rec
    rows = []
    for rec in latest.values():
        rows.append({
            "asset": rec["asset"],
            "venue": rec["venue"],
            "regime": rec["regime"],
            "side": rec["side"],
            "stage": rec["stage"],
            "age_chunks": rec["age_chunks"],
            "present_score": rec["present_score"],
            "score_band": rec["score_band"],
            "pressure_state": rec["pressure_state"],
            "from_onset_bps": round(float(rec["from_onset_bps"]), 3),
            "current_chunk_bps": round(float(rec["current_chunk_bps"]), 3),
            "volume_zscore": round(float(rec["volume_zscore"]), 3),
            "ts_end": rec["ts_end"],
        })
    rows.sort(key=lambda r: r["present_score"], reverse=True)
    return rows


def current_gate(row: dict[str, Any]) -> str:
    news = row.get("daily_news_context") or {}
    news_status = row.get("daily_news_status") or {}
    if news_status.get("stale"):
        return "news_stale_manual_review"
    if news.get("auto_trade_mode") in {"PAUSE", "MANUAL_REVIEW", "BLOCK"}:
        return "news_manual_review"
    if float(news.get("risk_multiplier", 1.0) or 1.0) <= 0:
        return "news_blocked"
    if news.get("requires_confirmation") and news.get("market_confirmation") in {"WEAK", "LOW", "UNKNOWN"}:
        return "needs_news_confirmation"
    score = int(row["present_score"])
    if score >= 70 and row["stage"] in {"onset", "early_follow"}:
        return "actionable_now"
    if score >= 55 and row["stage"] in {"onset", "early_follow", "mature"}:
        return "probe_or_watch"
    if score >= 55:
        return "late_watch_only"
    return "no_trade"


def write_report(path: Path, payload: dict[str, Any]) -> None:
    latest = payload["latest"]
    news_context = payload.get("daily_news_context") or {}
    score_stage = payload["summaries"]["score_band_by_stage"]
    by_stage = payload["summaries"]["stage"]
    lines = [
        "# Present-Tense Signal Strength Reanalysis",
        "",
        "This pass treats history as calibration for shape and timing, not as a veto because a signal flattened later. The scoring question is: if we were standing at this chunk in real time, was the signal strong enough to trade now?",
        "",
        "## Daily News Trade Context",
        "",
    ]
    if news_context.get("status") == "missing":
        lines.append("- No `daily_news_context.json` was available, so news did not change trade criteria.")
    elif news_context.get("status") == "error":
        lines.append("- `daily_news_context.json` could not be parsed; news did not change trade criteria.")
    else:
        if news_context.get("stale"):
            lines.append("- Daily news context is stale. Auto-trade should require manual review until refreshed.")
        lines.extend([
            "| Asset | Bias | Confirmation | Crowding | Vol regime | Risk mult | Auto mode | Posture |",
            "|---|---|---|---|---|---:|---|---|",
        ])
        for asset, ctx in sorted((news_context.get("assets") or {}).items()):
            lines.append(
                f"| {asset} | {ctx.get('narrative_bias', 'UNKNOWN')} | "
                f"{ctx.get('market_confirmation', 'UNKNOWN')} | "
                f"{ctx.get('crowding_risk', 'UNKNOWN')} | "
                f"{ctx.get('volatility_regime', 'UNKNOWN')} | "
                f"{float(ctx.get('risk_multiplier', 1.0) or 0.0):.2f} | "
                f"{ctx.get('auto_trade_mode', 'ALLOW')} | "
                f"{ctx.get('trade_posture', 'NEUTRAL')} |"
            )
    lines.extend([
        "",
        "## Current Snapshot",
        "",
        "| Asset | Venue | Side | Regime | Stage | Score | Base | Gate | News risk | From onset bps | Current chunk bps |",
        "|---|---|---:|---|---|---:|---:|---|---:|---:|---:|",
    ])
    for row in latest:
        news = row.get("daily_news_context") or {}
        lines.append(
            f"| {row['asset']} | {row['venue']} | {row['side']} | {row['regime']} | "
            f"{row['stage']} | {row['present_score']} | {row.get('base_present_score', row['present_score'])} | {current_gate(row)} | "
            f"{float(news.get('risk_multiplier', 1.0) or 0.0):.2f} | "
            f"{row['from_onset_bps']:.3f} | {row['current_chunk_bps']:.3f} |"
        )
    lines.extend([
        "",
        "## Stage Calibration",
        "",
        "| Stage | N | Avg score | H1 hit | H1 avg bps | H2 hit | H2 avg bps | H4 hit | H4 avg bps |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in by_stage:
        lines.append(
            f"| {row['stage']} | {row['n']} | {row['avg_present_score']:.2f} | "
            f"{row['h1_hit_pct']:.2f}% | {row['h1_avg_bps']:.3f} | "
            f"{row['h2_hit_pct']:.2f}% | {row['h2_avg_bps']:.3f} | "
            f"{row['h4_hit_pct']:.2f}% | {row['h4_avg_bps']:.3f} |"
        )
    lines.extend([
        "",
        "## Score Band By Stage",
        "",
        "| Band | Stage | N | H1 hit | H1 avg bps | H2 hit | H2 avg bps | H8 avg bps | H16 avg bps |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in score_stage[:24]:
        lines.append(
            f"| {row['score_band']} | {row['stage']} | {row['n']} | "
            f"{row['h1_hit_pct']:.2f}% | {row['h1_avg_bps']:.3f} | "
            f"{row['h2_hit_pct']:.2f}% | {row['h2_avg_bps']:.3f} | "
            f"{row['h8_avg_bps']:.3f} | {row['h16_avg_bps']:.3f} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Use `present_score` and `stage` as the trading gate.",
        "- Use H1/H2/H4 windows as the first trading outcome lens.",
        "- Use H8/H16 as decay diagnostics, not as a reason to throw out a strong onset.",
        "- A late-stage score can still be useful, but it should be a continuation/watch decision rather than pretending it is the original day-1 entry.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default=".")
    p.add_argument("--output-dir", default="pass22_present_signal_strength_out")
    p.add_argument("--assets", nargs="*", default=["BTC", "ETH"])
    p.add_argument("--chunk-max", type=int, default=30)
    p.add_argument("--chunk-min", type=int, default=10)
    p.add_argument("--multi-signal-pelt", action="store_true")
    p.add_argument(
        "--max-bars",
        type=int,
        default=0,
        help="Use only the most recent N bars from each file. 0 means all bars.",
    )
    p.add_argument(
        "--news-context",
        default="daily_news_context.json",
        help="Daily BTC/ETH news context JSON used to annotate auto-trade criteria.",
    )
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    news_context = load_daily_news_context(str(data_dir / args.news_context))

    all_records: list[dict[str, Any]] = []
    missing: list[str] = []
    for asset in args.assets:
        for venue, filename in VENUES.get(asset, {}).items():
            path = data_dir / filename
            if not path.exists():
                missing.append(str(path))
                continue
            print(f"[present-strength] loading {asset}/{venue} {path}", flush=True)
            records = build_records(
                asset,
                venue,
                path,
                chunk_max=args.chunk_max,
                chunk_min=args.chunk_min,
                multi_signal_pelt=args.multi_signal_pelt,
                max_bars=args.max_bars,
            )
            print(f"[present-strength] {asset}/{venue}: {len(records)} candidate chunks", flush=True)
            all_records.extend(records)

    summaries = {
        "stage": nested_summary(all_records, "stage"),
        "score_band": nested_summary(all_records, "score_band"),
        "score_band_by_stage": nested_summary(all_records, "score_band", "stage"),
        "asset_venue_stage": nested_summary(all_records, "asset", "venue", "stage"),
        "regime_stage": nested_summary(all_records, "regime", "stage"),
    }
    latest = latest_snapshot(all_records)
    for row in latest:
        asset_ctx = news_context.for_asset(str(row.get("asset") or ""))
        base_score = int(row.get("present_score") or 0)
        adjusted_score = base_score
        if news_context.status == "ok" and not news_context.stale:
            adjusted_score = adjust_present_score_with_news(
                base_score,
                str(row.get("side") or ""),
                asset_ctx,
                news_dipole_value=asset_ctx.news_dipole,
            )
        row["base_present_score"] = base_score
        row["present_score"] = adjusted_score
        row["score_band"] = score_band(adjusted_score)
        row["daily_news_context"] = asset_ctx.to_dict()
        row["daily_news_status"] = {
            "status": news_context.status,
            "stale": news_context.stale,
            "generated_at": news_context.generated_at,
        }
    counts = Counter(r["stage"] for r in all_records)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": os.path.abspath(str(data_dir)),
        "daily_news_context": news_context.to_dict(),
        "n_records": len(all_records),
        "missing": missing,
        "stage_counts": dict(counts),
        "latest": latest,
        "summaries": summaries,
    }
    json_path = output_dir / "present_signal_strength_results.json"
    report_path = output_dir / "present_signal_strength_report.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(report_path, payload)
    print(f"[present-strength] wrote {json_path}", flush=True)
    print(f"[present-strength] wrote {report_path}", flush=True)


if __name__ == "__main__":
    main()
