from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


def _float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, "")
        return float(value) if value not in {"", None} else default
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _median(values: list[float], default: float = 0.0) -> float:
    clean = [float(v) for v in values if v is not None]
    return float(median(clean)) if clean else default


def _bps_from_usd(usd: float, notional: float) -> float:
    return (float(usd) / max(float(notional), 1e-12)) * 10000.0


def _derive_params(key: str, bucket_rows: list[dict[str, str]]) -> dict[str, Any]:
    winner_bps: list[float] = []
    hold_minutes: list[float] = []
    cf: dict[str, list[float]] = {"10m": [], "30m": [], "60m": []}
    for row in bucket_rows:
        notional = _float(row, "hypothetical_notional") or _float(row, "notional")
        pnl = _float(row, "net_pnl_usd")
        winner_bps.append(_bps_from_usd(pnl, notional))
        hold_minutes.append(_float(row, "hold_minutes_actual"))
        for horizon in ("10m", "30m", "60m"):
            extra = row.get(f"cf_{horizon}_best_incremental_usd", "")
            if extra in {"", None}:
                continue
            cf[horizon].append(_bps_from_usd(_float(row, f"cf_{horizon}_best_incremental_usd"), notional))

    median_winner_bps = _median(winner_bps)
    p75_winner_bps = sorted(winner_bps)[int(0.75 * (len(winner_bps) - 1))] if winner_bps else median_winner_bps
    median_cf_30 = _median(cf["30m"], 0.0)
    cf_reference = median_cf_30 if cf["30m"] else p75_winner_bps * 0.30
    tp1_bps = _clamp(median_winner_bps * 0.60, 5.0, 50.0)
    trail_bps = _clamp(cf_reference * 0.50, 5.0, 60.0)
    scale_out_fraction = 0.33 if median_cf_30 > median_winner_bps else 0.50
    med_hold = _median(hold_minutes, 30.0)
    min_hold = int(round(_clamp(med_hold * 0.50, 15.0, 60.0)))
    max_hold = int(round(_clamp(med_hold * 2.0, 60.0, 240.0)))
    return {
        "schema": "exit_bucket_params_v1",
        "source": "trade_level_counterfactual_bucket_stats",
        "key": key,
        "winner_count": len(bucket_rows),
        "median_winner_bps": round(median_winner_bps, 4),
        "p75_winner_bps": round(float(p75_winner_bps), 4),
        "median_hold_minutes": round(med_hold, 4),
        "median_cf_10m_extra_bps": round(_median(cf["10m"], 0.0), 4),
        "median_cf_30m_extra_bps": round(median_cf_30, 4),
        "median_cf_60m_extra_bps": round(_median(cf["60m"], 0.0), 4),
        "tp1_bps": round(tp1_bps, 4),
        "scale_out_fraction": round(scale_out_fraction, 4),
        "trail_bps": round(trail_bps, 4),
        "min_hold_minutes": min_hold,
        "max_hold_minutes": max_hold,
        "min_profit_bps_for_score_exit": round(max(5.0, tp1_bps * 0.50), 4),
        "allow_full_score_exit": True,
        "allow_news_full_exit": True,
        "news_can_full_flat_profitable": False,
        "under_gate_trim_fraction": 0.25,
    }


def build_exit_params(rows: list[dict[str, str]], min_winners: int) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    venues: dict[str, list[dict[str, str]]] = defaultdict(list)
    families: dict[str, list[dict[str, str]]] = defaultdict(list)
    global_winners: list[dict[str, str]] = []
    for row in rows:
        if str(row.get("status") or "") != "closed":
            continue
        if _float(row, "net_pnl_usd") <= 0:
            continue
        strategy = str(row.get("strategy_id") or "").strip().upper()
        asset = str(row.get("asset") or "").strip().upper()
        venue = str(row.get("venue") or "").strip()
        session = str(row.get("bucket_session") or "").strip()
        if not strategy:
            continue
        global_winners.append(row)
        families[strategy].append(row)
        if asset and venue:
            venues["|".join([strategy, asset, venue])].append(row)
        if asset and venue and session:
            buckets["|".join([strategy, asset, venue, session])].append(row)

    family_params = {
        key: _derive_params(key, rows_)
        for key, rows_ in sorted(families.items())
        if len(rows_) >= min_winners
    }
    defaults: dict[str, Any] = {
        "schema": "exit_defaults_v1",
        "family": family_params,
    }
    if len(global_winners) >= min_winners:
        defaults["global"] = _derive_params("GLOBAL", global_winners)
        defaults["global"]["source"] = "trade_level_counterfactual_global_default"
    return {
        "bucket_params": {
            key: _derive_params(key, rows_)
            for key, rows_ in sorted(buckets.items())
            if len(rows_) >= min_winners
        },
        "venue_params": {
            key: _derive_params(key, rows_)
            for key, rows_ in sorted(venues.items())
            if len(rows_) >= min_winners
        },
        "family_params": family_params,
        "defaults": defaults,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="reports/perplexity_exit_trade_level_sheet_20260518_033642.csv")
    parser.add_argument("--output", default="exit_params.json")
    parser.add_argument("--min-winners", type=int, default=5)
    args = parser.parse_args()

    input_path = Path(args.input)
    with input_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    params = build_exit_params(rows, int(args.min_winners))
    payload = {
        "schema": "exit_params_map_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_csv": str(input_path),
        "min_winners": int(args.min_winners),
        "bucket_count": len(params["bucket_params"]),
        "venue_count": len(params["venue_params"]),
        "family_count": len(params["family_params"]),
        "params": params["bucket_params"],
        "bucket_params": params["bucket_params"],
        "venue_params": params["venue_params"],
        "family_params": params["family_params"],
        "defaults": params["defaults"],
    }
    output_path = Path(args.output)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {output_path} ({len(params['bucket_params'])} buckets)")


if __name__ == "__main__":
    main()
