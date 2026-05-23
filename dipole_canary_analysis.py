from __future__ import annotations

import json
import math
import os
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median

from phase1_5_evaluator import classify_venue, load_bars


DATA_SOURCES = [
    ("BTC", "Coinbase", "btc_coinbase_bins.json"),
    ("BTC", "Kraken", "btc_kraken_bins.json"),
    ("BTC", "Bybit", "btc_bybit_perp_bins.json"),
    ("ETH", "Coinbase", "eth_coinbase_bins.json"),
    ("ETH", "Kraken", "eth_kraken_bins.json"),
    ("ETH", "Bybit", "eth_bybit_perp_bins.json"),
]

STRONG_UP = {"WHALE_UP", "HERD_UP"}
STRONG_DOWN = {"WHALE_DOWN", "HERD_DOWN"}
STRONG = STRONG_UP | STRONG_DOWN
NASCENT = {"WHALE_NASCENT_UP", "WHALE_NASCENT_DOWN"}


@dataclass
class VenueSummary:
    asset: str
    venue: str
    file: str
    bars: int
    chunks: int
    regimes: dict[str, int]


def sign_of_dipole(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def sign_of_regime(regime: str) -> int:
    if regime.endswith("_UP"):
        return 1
    if regime.endswith("_DOWN"):
        return -1
    return 0


def pct(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(100.0 * value, 2)


def avg(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def med(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def load_records(max_bars: int | None = None) -> tuple[list[dict], list[VenueSummary]]:
    records: list[dict] = []
    summaries: list[VenueSummary] = []
    for asset, venue, filename in DATA_SOURCES:
        path = Path(filename)
        if not path.exists():
            continue
        bars = load_bars(str(path))
        if max_bars and len(bars) > max_bars:
            bars = bars[-max_bars:]
        chunks, results, _base, _session_base, feats = classify_venue(
            bars,
            f"{venue}-{asset}",
            chunk_max=30,
            chunk_min=10,
            multi_signal_pelt=False,
            compute_hawkes=False,
            compute_hurst=False,
        )
        summaries.append(
            VenueSummary(
                asset=asset,
                venue=venue,
                file=filename,
                bars=len(bars),
                chunks=len(chunks),
                regimes=dict(Counter(r.regime.value for r in results)),
            )
        )
        for idx, (chunk, result, feat) in enumerate(zip(chunks, results, feats)):
            close0 = float(chunk.bars[0].close) if chunk.bars else 0.0
            close1 = float(chunk.bars[-1].close) if chunk.bars else 0.0
            records.append(
                {
                    "asset": asset,
                    "venue": venue,
                    "idx": idx,
                    "ts_start": float(chunk.bars[0].ts) if chunk.bars else 0.0,
                    "ts_end": float(chunk.bars[-1].ts) if chunk.bars else 0.0,
                    "close_start": close0,
                    "close_end": close1,
                    "regime": result.regime.value,
                    "confidence": float(result.adjusted_confidence),
                    "mean_dipole": float(feat.mean_dipole),
                    "abs_dipole": abs(float(feat.mean_dipole)),
                    "dipole_sign": sign_of_dipole(float(feat.mean_dipole)),
                    "dipole_acl1": float(feat.dipole_autocorr_lag1),
                    "volume_zscore": float(feat.volume_zscore),
                    "chunk_total_volume": float(feat.chunk_total_volume),
                    "realized_vol": float(feat.realized_vol),
                }
            )
    return records, summaries


def group_records(records: list[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for rec in records:
        grouped.setdefault((rec["asset"], rec["venue"]), []).append(rec)
    for items in grouped.values():
        items.sort(key=lambda r: r["idx"])
    return grouped


def future_outcome(items: list[dict], i: int, horizon: int) -> dict:
    cur = items[i]
    s = int(cur["dipole_sign"])
    same_strong = False
    opposite_strong = False
    any_strong = False
    same_nascent = False
    lead_chunks = None
    for j in range(i + 1, min(len(items), i + horizon + 1)):
        r = str(items[j]["regime"])
        if r in NASCENT and sign_of_regime(r) == s:
            same_nascent = True
        if r in STRONG:
            any_strong = True
            if sign_of_regime(r) == s:
                same_strong = True
                if lead_chunks is None:
                    lead_chunks = j - i
            else:
                opposite_strong = True
    future_idx = min(len(items) - 1, i + horizon)
    cur_close = float(cur["close_end"])
    fut_close = float(items[future_idx]["close_end"])
    if cur_close > 0 and s != 0:
        signed_return_bps = s * math.log(max(fut_close, 1e-12) / cur_close) * 10000.0
    else:
        signed_return_bps = 0.0
    return {
        "same_strong": same_strong,
        "opposite_strong": opposite_strong,
        "any_strong": any_strong,
        "same_nascent": same_nascent,
        "lead_chunks": lead_chunks,
        "signed_return_bps": signed_return_bps,
    }


def rule_specs() -> list[tuple[str, dict]]:
    specs: list[tuple[str, dict]] = []
    for lo, hi in ((0.05, 0.15), (0.10, 0.20), (0.10, 0.25), (0.15, 0.25), (0.20, 0.30)):
        specs.append((f"weak_band_abs_dipole_{lo:.2f}_{hi:.2f}", {"threshold": lo, "max_threshold": hi}))
        specs.append((f"weak_band_vol_abs_dipole_{lo:.2f}_{hi:.2f}", {"threshold": lo, "max_threshold": hi, "volume_z_min": 0.0}))
        specs.append((f"weak_band_acl_abs_dipole_{lo:.2f}_{hi:.2f}", {"threshold": lo, "max_threshold": hi, "acl_min": 0.0}))
        specs.append((f"weak_band_persistent_abs_dipole_{lo:.2f}_{hi:.2f}", {"threshold": lo, "max_threshold": hi, "persistent": True}))
    for threshold in (0.10, 0.15, 0.20, 0.25, 0.30):
        specs.append((f"abs_dipole_ge_{threshold:.2f}", {"threshold": threshold}))
        specs.append((f"persistent_abs_dipole_ge_{threshold:.2f}", {"threshold": threshold, "persistent": True}))
        specs.append((f"vol_confirmed_abs_dipole_ge_{threshold:.2f}", {"threshold": threshold, "volume_z_min": 0.0}))
        specs.append((f"acl_confirmed_abs_dipole_ge_{threshold:.2f}", {"threshold": threshold, "acl_min": 0.0}))
    return specs


def passes_rule(items: list[dict], idx: int, spec: dict) -> bool:
    rec = items[idx]
    if str(rec["regime"]) in STRONG:
        return False
    if rec["dipole_sign"] == 0:
        return False
    if rec["abs_dipole"] < spec["threshold"]:
        return False
    if "max_threshold" in spec and rec["abs_dipole"] >= spec["max_threshold"]:
        return False
    if "volume_z_min" in spec and rec["volume_zscore"] < spec["volume_z_min"]:
        return False
    if "acl_min" in spec and rec["dipole_acl1"] < spec["acl_min"]:
        return False
    if spec.get("persistent"):
        if idx <= 0:
            return False
        prev = items[idx - 1]
        if str(prev["regime"]) in STRONG:
            return False
        if prev["dipole_sign"] != rec["dipole_sign"]:
            return False
        if prev["abs_dipole"] < spec["threshold"]:
            return False
    return True


def analyze(records: list[dict]) -> dict:
    grouped = group_records(records)
    out: dict = {
        "horizons": {},
        "best_rules_by_horizon": {},
        "per_asset_venue_best": {},
        "cross_venue_canary": {},
        "event_examples": [],
    }
    for horizon in (1, 2, 3, 4):
        horizon_rows: list[dict] = []
        for rule_name, spec in rule_specs():
            totals = {
                "eligible": 0,
                "candidate": 0,
                "base_same_strong": 0,
                "hit_same_strong": 0,
                "hit_same_nascent": 0,
                "hit_any_strong": 0,
                "hit_opposite_strong": 0,
                "candidate_returns": [],
                "eligible_returns": [],
                "lead_chunks": [],
            }
            by_pair: dict[str, dict] = {}
            for (asset, venue), items in grouped.items():
                pair_key = f"{asset}/{venue}"
                p = by_pair.setdefault(pair_key, {"eligible": 0, "candidate": 0, "base_same_strong": 0, "hit_same_strong": 0})
                for idx in range(0, max(0, len(items) - horizon)):
                    rec = items[idx]
                    if str(rec["regime"]) in STRONG:
                        continue
                    if int(rec["dipole_sign"]) == 0:
                        continue
                    outcome = future_outcome(items, idx, horizon)
                    totals["eligible"] += 1
                    p["eligible"] += 1
                    if outcome["same_strong"]:
                        totals["base_same_strong"] += 1
                        p["base_same_strong"] += 1
                    totals["eligible_returns"].append(float(outcome["signed_return_bps"]))
                    if not passes_rule(items, idx, spec):
                        continue
                    totals["candidate"] += 1
                    p["candidate"] += 1
                    if outcome["same_strong"]:
                        totals["hit_same_strong"] += 1
                        p["hit_same_strong"] += 1
                    if outcome["same_nascent"]:
                        totals["hit_same_nascent"] += 1
                    if outcome["any_strong"]:
                        totals["hit_any_strong"] += 1
                    if outcome["opposite_strong"]:
                        totals["hit_opposite_strong"] += 1
                    totals["candidate_returns"].append(float(outcome["signed_return_bps"]))
                    if outcome["lead_chunks"] is not None:
                        totals["lead_chunks"].append(int(outcome["lead_chunks"]))
            eligible = totals["eligible"]
            candidate = totals["candidate"]
            base_rate = totals["base_same_strong"] / eligible if eligible else 0.0
            hit_rate = totals["hit_same_strong"] / candidate if candidate else 0.0
            row = {
                "rule": rule_name,
                "horizon_chunks": horizon,
                "eligible": eligible,
                "candidate": candidate,
                "coverage_pct": pct(candidate / eligible if eligible else 0.0),
                "base_same_strong_rate_pct": pct(base_rate),
                "same_strong_hit_rate_pct": pct(hit_rate),
                "lift_vs_base": round(hit_rate / base_rate, 3) if base_rate > 0 and candidate else 0.0,
                "same_nascent_rate_pct": pct(totals["hit_same_nascent"] / candidate if candidate else 0.0),
                "any_strong_rate_pct": pct(totals["hit_any_strong"] / candidate if candidate else 0.0),
                "opposite_strong_rate_pct": pct(totals["hit_opposite_strong"] / candidate if candidate else 0.0),
                "avg_signed_return_bps": round(avg(totals["candidate_returns"]), 3),
                "median_signed_return_bps": round(med(totals["candidate_returns"]), 3),
                "eligible_avg_signed_return_bps": round(avg(totals["eligible_returns"]), 3),
                "median_lead_chunks": round(med(totals["lead_chunks"]), 3),
                "by_pair": by_pair,
            }
            horizon_rows.append(row)
        horizon_rows.sort(
            key=lambda r: (
                r["lift_vs_base"],
                r["same_strong_hit_rate_pct"],
                r["candidate"],
                r["avg_signed_return_bps"],
            ),
            reverse=True,
        )
        out["horizons"][str(horizon)] = horizon_rows
        out["best_rules_by_horizon"][str(horizon)] = horizon_rows[:8]
    out["per_asset_venue_best"] = per_pair_best(grouped)
    out["cross_venue_canary"] = cross_venue_slot_analysis(records)
    out["event_examples"] = collect_examples(grouped)
    return out


def cross_venue_slot_analysis(records: list[dict]) -> dict:
    by_asset: dict[str, list[dict]] = {}
    for rec in records:
        by_asset.setdefault(str(rec["asset"]), []).append(rec)
    out: dict = {}
    for asset, items in by_asset.items():
        items.sort(key=lambda r: r["ts_end"])
        rows = []
        for lo, hi in ((0.10, 0.25), (0.15, 0.25), (0.20, 0.30), (0.25, 0.40)):
            for horizon_min in (30, 45, 60):
                eligible = candidate = base_hit = hit = opposite = 0
                returns = []
                slots: dict[int, list[dict]] = {}
                for rec in items:
                    slot = int(float(rec["ts_end"]) // 900) * 900
                    slots.setdefault(slot, []).append(rec)
                for slot, slot_recs in slots.items():
                    directional: dict[int, list[dict]] = {1: [], -1: []}
                    for rec in slot_recs:
                        if str(rec["regime"]) in STRONG:
                            continue
                        if lo <= float(rec["abs_dipole"]) < hi and int(rec["dipole_sign"]) != 0:
                            directional[int(rec["dipole_sign"])].append(rec)
                    for direction, signed_recs in directional.items():
                        if not signed_recs:
                            continue
                        eligible += 1
                        future = [
                            r for r in items
                            if slot < float(r["ts_end"]) <= slot + horizon_min * 60
                        ]
                        same = any(str(r["regime"]) in STRONG and sign_of_regime(str(r["regime"])) == direction for r in future)
                        opp = any(str(r["regime"]) in STRONG and sign_of_regime(str(r["regime"])) == -direction for r in future)
                        if same:
                            base_hit += 1
                        venues = {str(r["venue"]) for r in signed_recs}
                        if len(venues) < 2:
                            continue
                        candidate += 1
                        if same:
                            hit += 1
                        if opp:
                            opposite += 1
                        anchor = max(signed_recs, key=lambda r: abs(float(r["mean_dipole"])))
                        last_future = max(future, key=lambda r: r["ts_end"], default=None)
                        if last_future and float(anchor["close_end"]) > 0:
                            ret = direction * math.log(
                                max(float(last_future["close_end"]), 1e-12) / float(anchor["close_end"])
                            ) * 10000.0
                            returns.append(ret)
                base_rate = base_hit / eligible if eligible else 0.0
                hit_rate = hit / candidate if candidate else 0.0
                if candidate:
                    rows.append({
                        "band": f"{lo:.2f}_{hi:.2f}",
                        "horizon_min": horizon_min,
                        "eligible": eligible,
                        "candidate": candidate,
                        "base_hit_rate_pct": pct(base_rate),
                        "same_strong_hit_rate_pct": pct(hit_rate),
                        "lift": round(hit_rate / base_rate, 3) if base_rate > 0 else 0.0,
                        "opposite_strong_rate_pct": pct(opposite / candidate),
                        "avg_signed_return_bps": round(avg(returns), 3),
                    })
        rows.sort(key=lambda r: (r["lift"], r["same_strong_hit_rate_pct"], r["candidate"]), reverse=True)
        out[asset] = rows[:10]
    return out


def per_pair_best(grouped: dict[tuple[str, str], list[dict]]) -> dict:
    result: dict = {}
    for pair, items in grouped.items():
        asset, venue = pair
        pair_rows = []
        for rule_name, spec in rule_specs():
            eligible = candidate = base_hit = rule_hit = 0
            returns = []
            for idx in range(0, max(0, len(items) - 3)):
                rec = items[idx]
                if str(rec["regime"]) in STRONG or int(rec["dipole_sign"]) == 0:
                    continue
                outcome = future_outcome(items, idx, 3)
                eligible += 1
                if outcome["same_strong"]:
                    base_hit += 1
                if not passes_rule(items, idx, spec):
                    continue
                candidate += 1
                if outcome["same_strong"]:
                    rule_hit += 1
                returns.append(float(outcome["signed_return_bps"]))
            base_rate = base_hit / eligible if eligible else 0.0
            hit_rate = rule_hit / candidate if candidate else 0.0
            if candidate >= 5:
                pair_rows.append(
                    {
                        "rule": rule_name,
                        "eligible": eligible,
                        "candidate": candidate,
                        "base_rate_pct": pct(base_rate),
                        "hit_rate_pct": pct(hit_rate),
                        "lift": round(hit_rate / base_rate, 3) if base_rate > 0 else 0.0,
                        "avg_signed_return_bps": round(avg(returns), 3),
                    }
                )
        pair_rows.sort(key=lambda r: (r["lift"], r["hit_rate_pct"], r["candidate"]), reverse=True)
        result[f"{asset}/{venue}"] = pair_rows[:5]
    return result


def collect_examples(grouped: dict[tuple[str, str], list[dict]]) -> list[dict]:
    examples = []
    spec = {"threshold": 0.15, "persistent": True}
    for (asset, venue), items in grouped.items():
        for idx in range(0, max(0, len(items) - 4)):
            if not passes_rule(items, idx, spec):
                continue
            outcome = future_outcome(items, idx, 4)
            if not outcome["same_strong"]:
                continue
            examples.append(
                {
                    "asset": asset,
                    "venue": venue,
                    "idx": idx,
                    "ts_end": items[idx]["ts_end"],
                    "dipole": round(items[idx]["mean_dipole"], 3),
                    "regime_now": items[idx]["regime"],
                    "lead_chunks": outcome["lead_chunks"],
                    "next_regimes": [items[j]["regime"] for j in range(idx + 1, min(len(items), idx + 5))],
                    "signed_return_bps_4chunks": round(outcome["signed_return_bps"], 3),
                }
            )
            break
    return examples[:12]


def write_report(output_dir: Path, summaries: list[VenueSummary], analysis: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "dipole_canary_results.json"
    report_path = output_dir / "dipole_canary_report.md"
    results_path.write_text(
        json.dumps(
            {
                "sources": [asdict(s) for s in summaries],
                "analysis": analysis,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lines: list[str] = []
    lines.append("# Dipole Canary Analysis")
    lines.append("")
    lines.append("Question: does weak or moderate mean_dipole act as an early warning before Whale/Herd regimes?")
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    for s in summaries:
        top = ", ".join(f"{k}={v}" for k, v in sorted(s.regimes.items(), key=lambda kv: kv[0]))
        lines.append(f"- {s.asset}/{s.venue}: {s.bars} minute bars, {s.chunks} chunks; {top}")
    lines.append("")
    lines.append("## Best Canary Rules")
    lines.append("")
    for horizon, rows in analysis["best_rules_by_horizon"].items():
        lines.append(f"### Horizon: next {horizon} chunk(s)")
        lines.append("")
        lines.append("| rule | candidates | coverage | base hit | hit | lift | avg signed ret bps | opposite hit |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for row in rows[:6]:
            lines.append(
                f"| {row['rule']} | {row['candidate']} | {row['coverage_pct']}% | "
                f"{row['base_same_strong_rate_pct']}% | {row['same_strong_hit_rate_pct']}% | "
                f"{row['lift_vs_base']} | {row['avg_signed_return_bps']} | "
                f"{row['opposite_strong_rate_pct']}% |"
            )
        lines.append("")
    lines.append("## Weak-Only Canary Rules")
    lines.append("")
    lines.append("These rows isolate weak/moderate dipole bands instead of letting high dipole values dominate.")
    lines.append("")
    for horizon, rows in analysis["horizons"].items():
        weak_rows = [
            row for row in rows
            if row["rule"].startswith("weak_band") and int(row["candidate"]) >= 50
        ]
        weak_rows.sort(
            key=lambda r: (
                r["lift_vs_base"],
                r["same_strong_hit_rate_pct"],
                r["avg_signed_return_bps"],
            ),
            reverse=True,
        )
        lines.append(f"### Horizon: next {horizon} chunk(s)")
        lines.append("")
        lines.append("| rule | candidates | base hit | hit | lift | avg signed ret bps | opposite hit |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for row in weak_rows[:6]:
            lines.append(
                f"| {row['rule']} | {row['candidate']} | {row['base_same_strong_rate_pct']}% | "
                f"{row['same_strong_hit_rate_pct']}% | {row['lift_vs_base']} | "
                f"{row['avg_signed_return_bps']} | {row['opposite_strong_rate_pct']}% |"
            )
        lines.append("")
    lines.append("## Best Per Asset/Venue, 3-Chunk Horizon")
    lines.append("")
    for pair, rows in analysis["per_asset_venue_best"].items():
        lines.append(f"### {pair}")
        lines.append("")
        lines.append("| rule | candidates | base hit | hit | lift | avg signed ret bps |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in rows[:4]:
            lines.append(
                f"| {row['rule']} | {row['candidate']} | {row['base_rate_pct']}% | "
                f"{row['hit_rate_pct']}% | {row['lift']} | {row['avg_signed_return_bps']} |"
            )
        lines.append("")
    lines.append("## Cross-Venue Canary")
    lines.append("")
    lines.append("Candidate means at least two venues show same-direction non-strong dipole pressure in the same 15-minute slot.")
    lines.append("")
    for asset, rows in analysis["cross_venue_canary"].items():
        lines.append(f"### {asset}")
        lines.append("")
        lines.append("| band | horizon min | candidates | base hit | hit | lift | avg signed ret bps | opposite hit |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for row in rows[:6]:
            lines.append(
                f"| {row['band']} | {row['horizon_min']} | {row['candidate']} | "
                f"{row['base_hit_rate_pct']}% | {row['same_strong_hit_rate_pct']}% | "
                f"{row['lift']} | {row['avg_signed_return_bps']} | "
                f"{row['opposite_strong_rate_pct']}% |"
            )
        lines.append("")
    lines.append("## Example Early Reads")
    lines.append("")
    for ex in analysis["event_examples"]:
        lines.append(
            f"- {ex['asset']}/{ex['venue']} idx={ex['idx']} dipole={ex['dipole']:+.3f} "
            f"now={ex['regime_now']} lead={ex['lead_chunks']} chunks next={ex['next_regimes']} "
            f"signed_ret_4c={ex['signed_return_bps_4chunks']} bps"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "Treat this as a canary/watch state, not a trade trigger by itself. "
        "The strongest framing is: directional pressure is forming before the classifier has enough evidence "
        "to call Whale or Herd. Product copy should stay trader-native: pressure forming, Whale/Herd watch, "
        "or equilibrium under pressure. Do not expose the internal dipole term."
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="pass20_dipole_canary_out")
    parser.add_argument("--max-bars", type=int, default=0, help="Use most recent N minute bars per venue; 0 = all.")
    args = parser.parse_args()

    records, summaries = load_records(max_bars=args.max_bars or None)
    analysis = analyze(records)
    write_report(Path(args.output_dir), summaries, analysis)
    print(f"wrote {Path(args.output_dir) / 'dipole_canary_report.md'}")
    for horizon, rows in analysis["best_rules_by_horizon"].items():
        best = rows[0] if rows else {}
        print(
            f"h={horizon}: {best.get('rule')} candidates={best.get('candidate')} "
            f"hit={best.get('same_strong_hit_rate_pct')}% lift={best.get('lift_vs_base')} "
            f"ret={best.get('avg_signed_return_bps')}bps"
        )


if __name__ == "__main__":
    main()
