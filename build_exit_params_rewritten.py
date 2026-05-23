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


def build_exit_params(rows: list[dict[str, str]], min_winners: int) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        if str(row.get("status") or "") != "closed":
            continue
        if _float(row, "net_pnl_usd") <= 0:
            continue

        key = "|".join(
            [
                str(row.get("strategy_id") or "").strip().upper(),
                str(row.get("asset") or "").strip().upper(),
                str(row.get("venue") or "").strip(),
                str(row.get("bucket_session") or "").strip(),
            ]
        )
        if key.count("|") == 3 and not key.startswith("|"):
            buckets[key].append(row)

    bucket_params: dict[str, Any] = {}

    for key, bucket_rows in sorted(buckets.items()):
        if len(bucket_rows) < min_winners:
            continue

        winner_bps: list[float] = []
        hold_minutes: list[float] = []
        cf: dict[str, list[float]] = {"10m": [], "30m": [], "60m": []}

        for row in bucket_rows:
            notional = _float(row, "hypothetical_notional") or _float(row, "notional")
            pnl = _float(row, "net_pnl_usd")
            winner_bps.append(_bps_from_usd(pnl, notional))
            hold_minutes.append(_float(row, "hold_minutes_actual"))

            for horizon in ("10m", "30m", "60m"):
                extra_key = f"cf_{horizon}_best_incremental_usd"
                extra = row.get(extra_key, "")
                if extra in {"", None}:
                    continue
                cf[horizon].append(_bps_from_usd(_float(row, extra_key), notional))

        median_winner_bps = _median(winner_bps)
        p75_winner_bps = (
            sorted(winner_bps)[int(0.75 * (len(winner_bps) - 1))]
            if winner_bps
            else median_winner_bps
        )

        median_cf_30 = _median(cf["30m"], 0.0)
        cf_reference = median_cf_30 if cf["30m"] else p75_winner_bps * 0.30

        tp1_bps = _clamp(median_winner_bps * 0.60, 5.0, 50.0)
        trail_bps = _clamp(cf_reference * 0.50, 5.0, 60.0)
        scale_out_fraction = 0.33 if median_cf_30 > median_winner_bps else 0.50

        med_hold = _median(hold_minutes, 30.0)
        min_hold = int(round(_clamp(med_hold * 0.50, 15.0, 60.0)))
        max_hold = int(round(_clamp(med_hold * 2.0, 60.0, 240.0)))

        bucket_params[key] = {
            "schema": "exit_bucket_params_v1",
            "source": "trade_level_counterfactual_bucket_stats",
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
        }

    family_defaults: dict[str, Any] = {}
    family_venue_defaults: dict[str, Any] = {}

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_family_venue: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for key, params in bucket_params.items():
        strat, _asset, venue, _session = key.split("|")
        by_family[strat].append(params)
        by_family_venue[(strat, venue)].append(params)

    def _avg_param(rows_: list[dict[str, Any]], field: str, default: float) -> float:
        vals = [float(r.get(field, default)) for r in rows_ if r.get(field) is not None]
        return float(sum(vals) / len(vals)) if vals else default

    for strat, rows_list in by_family.items():
        family_defaults[strat] = {
            "schema": "exit_family_defaults_v1",
            "strategy_id": strat,
            "tp1_bps": _avg_param(rows_list, "tp1_bps", 10.0),
            "scale_out_fraction": _avg_param(rows_list, "scale_out_fraction", 0.5),
            "trail_bps": _avg_param(rows_list, "trail_bps", 10.0),
            "min_hold_minutes": int(round(_avg_param(rows_list, "min_hold_minutes", 15.0))),
            "max_hold_minutes": int(round(_avg_param(rows_list, "max_hold_minutes", 60.0))),
            "min_profit_bps_for_score_exit": _avg_param(
                rows_list, "min_profit_bps_for_score_exit", 5.0
            ),
        }

    for (strat, venue), rows_list in by_family_venue.items():
        key = f"{strat}|{venue}"
        family_venue_defaults[key] = {
            "schema": "exit_family_venue_defaults_v1",
            "strategy_id": strat,
            "venue": venue,
            "tp1_bps": _avg_param(rows_list, "tp1_bps", 10.0),
            "scale_out_fraction": _avg_param(rows_list, "scale_out_fraction", 0.5),
            "trail_bps": _avg_param(rows_list, "trail_bps", 10.0),
            "min_hold_minutes": int(round(_avg_param(rows_list, "min_hold_minutes", 15.0))),
            "max_hold_minutes": int(round(_avg_param(rows_list, "max_hold_minutes", 60.0))),
            "min_profit_bps_for_score_exit": _avg_param(
                rows_list, "min_profit_bps_for_score_exit", 5.0
            ),
        }

    return {
        "bucket_params": bucket_params,
        "family_defaults": family_defaults,
        "family_venue_defaults": family_venue_defaults,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="reports/perplexity_exit_trade_level_sheet_20260518_033642.csv",
    )
    parser.add_argument("--output", default="exit_params.json")
    parser.add_argument("--min-winners", type=int, default=5)
    args = parser.parse_args()

    input_path = Path(args.input)
    with input_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    params_payload = build_exit_params(rows, int(args.min_winners))

    payload = {
        "schema": "exit_params_map_v2",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_csv": str(input_path),
        "min_winners": int(args.min_winners),
        "bucket_count": len(params_payload["bucket_params"]),
        "bucket_params": params_payload["bucket_params"],
        "family_defaults": params_payload["family_defaults"],
        "family_venue_defaults": params_payload["family_venue_defaults"],
    }

    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"wrote {output_path} ({payload['bucket_count']} buckets)")


if __name__ == "__main__":
    main()
