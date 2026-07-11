from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GLOBALS = {
    "min_samples_for_policy": 50,
    "min_signed_bps_edge_vs_placebo": 3.0,
    "min_hit_rate": 55.0,
    "max_crowding_volume_ratio": 5.0,
    "shock_valid_minutes_default": 180,
}

SHOCK_CATEGORIES = {"SECURITY", "REGULATORY", "EXCHANGE", "ETF"}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _placebo_index(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        out[int(row.get("horizon_min") or 0)] = row
    return out


def derive_risk_multiplier(category: str, bias: str, edge: float, hit_rate: float) -> float:
    if category in {"SECURITY", "REGULATORY", "EXCHANGE"} and bias == "BEARISH":
        if edge >= 8.0 and hit_rate >= 60.0:
            return 0.25
        return 0.5
    if edge >= 10.0 and hit_rate >= 65.0:
        return 1.0
    if edge >= 6.0:
        return 0.75
    return 0.5


def derive_requires_confirmation(category: str, bias: str, edge: float, hit_rate: float) -> bool:
    return not (category in {"SECURITY", "REGULATORY", "EXCHANGE"} and bias == "BEARISH" and edge >= 8.0 and hit_rate >= 60.0)


def derive_shock(category: str, bias: str, horizon: int, edge: float, hit_rate: float, valid_default: int) -> dict[str, Any]:
    is_shock = category in SHOCK_CATEGORIES and edge >= 3.0 and hit_rate >= 55.0
    actions: list[str] = []
    if is_shock:
        actions.append("PAUSE_NEW_ENTRIES")
        if bias == "BEARISH":
            actions.extend(["EXIT_LONGS", "ALLOW_HEDGE_SHORT", "START_SHORT_IF_CONFIRMED"])
        elif bias == "BULLISH":
            actions.extend(["EXIT_SHORTS", "ALLOW_HEDGE_LONG", "START_LONG_IF_CONFIRMED"])
    valid_minutes = max(valid_default, int(horizon) * 2) if is_shock else 0
    return {
        "is_shock": is_shock,
        "valid_minutes": valid_minutes,
        "starter_actions": actions,
    }


def build_policy(coupling: dict[str, Any], *, source: str, globals_: dict[str, Any]) -> dict[str, Any]:
    summaries = coupling.get("summaries") or {}
    placebo = _placebo_index(list(summaries.get("placebo_by_horizon") or []))
    min_n = int(globals_["min_samples_for_policy"])
    min_edge = float(globals_["min_signed_bps_edge_vs_placebo"])
    min_hit = float(globals_["min_hit_rate"])
    max_crowding = float(globals_["max_crowding_volume_ratio"])
    valid_default = int(globals_["shock_valid_minutes_default"])

    categories: dict[str, dict[str, dict[str, Any]]] = {}
    for row in summaries.get("by_category_bias_horizon") or []:
        category = str(row.get("category") or "UNKNOWN").upper()
        bias = str(row.get("directional_bias") or "UNKNOWN").upper()
        horizon = int(row.get("horizon_min") or 0)
        n = int(row.get("n") or 0)
        signed_avg = _float(row.get("signed_avg_bps"))
        base = _float((placebo.get(horizon) or {}).get("signed_avg_bps"))
        edge = signed_avg - base
        hit_rate = _float(row.get("signed_hit_pct"))
        vol_ratio = row.get("volume_ratio_median")
        vol_value = _float(vol_ratio, 0.0) if vol_ratio is not None else None
        enabled = (
            n >= min_n
            and hit_rate >= min_hit
            and edge >= min_edge
            and (vol_value is None or vol_value <= max_crowding)
        )
        risk_multiplier = derive_risk_multiplier(category, bias, edge, hit_rate)
        entry = {
            "enabled": enabled,
            "n": n,
            "min_samples": min_n,
            "signed_avg_bps": round(signed_avg, 3),
            "placebo_signed_avg_bps": round(base, 3),
            "signed_bps_edge_vs_placebo": round(edge, 3),
            "hit_rate": round(hit_rate, 2),
            "volume_ratio_median": vol_ratio,
            "risk_multiplier": risk_multiplier,
            "requires_confirmation": derive_requires_confirmation(category, bias, edge, hit_rate),
            "shock": derive_shock(category, bias, horizon, edge, hit_rate, valid_default),
        }
        categories.setdefault(category, {}).setdefault(bias, {})[str(horizon)] = entry

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "version": 1,
        "description": "Derived mapping from news coupling research to live news-risk rules. Low-sample entries remain visible but disabled.",
        "globals": globals_,
        "categories": categories,
        "assets_overrides": {},
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--coupling-results", default="pass23_news_coupling_out/news_coupling_results.json")
    p.add_argument("--output", default="news_policy.json")
    p.add_argument("--source", default="news_coupling_research")
    p.add_argument("--min-samples-for-policy", type=int, default=DEFAULT_GLOBALS["min_samples_for_policy"])
    p.add_argument("--min-signed-bps-edge-vs-placebo", type=float, default=DEFAULT_GLOBALS["min_signed_bps_edge_vs_placebo"])
    p.add_argument("--min-hit-rate", type=float, default=DEFAULT_GLOBALS["min_hit_rate"])
    p.add_argument("--max-crowding-volume-ratio", type=float, default=DEFAULT_GLOBALS["max_crowding_volume_ratio"])
    p.add_argument("--shock-valid-minutes-default", type=int, default=DEFAULT_GLOBALS["shock_valid_minutes_default"])
    args = p.parse_args()

    path = Path(args.coupling_results)
    if path.exists():
        coupling = json.loads(path.read_text(encoding="utf-8"))
    else:
        coupling = {"summaries": {}}
    globals_ = {
        "min_samples_for_policy": args.min_samples_for_policy,
        "min_signed_bps_edge_vs_placebo": args.min_signed_bps_edge_vs_placebo,
        "min_hit_rate": args.min_hit_rate,
        "max_crowding_volume_ratio": args.max_crowding_volume_ratio,
        "shock_valid_minutes_default": args.shock_valid_minutes_default,
    }
    policy = build_policy(coupling, source=args.source, globals_=globals_)
    Path(args.output).write_text(json.dumps(policy, indent=2), encoding="utf-8")
    enabled = 0
    visible = 0
    for cat in policy["categories"].values():
        for bias in cat.values():
            for entry in bias.values():
                visible += 1
                enabled += 1 if entry.get("enabled") else 0
    print(f"[news-policy] visible_rules={visible} enabled_rules={enabled} wrote {args.output}")


if __name__ == "__main__":
    main()
