from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

from dipole_canary_analysis import (
    STRONG,
    group_records,
    load_records,
    pct,
    sign_of_regime,
)


EARLY = {"EQUILIBRIUM_TWO_SIDED", "DEPLETED", "WASH_HAWKES", "WASH_PAIRED", "UNKNOWN"}
NASCENT = {"WHALE_NASCENT_UP", "WHALE_NASCENT_DOWN"}


def avg(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def med(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def dipole_sign(rec: dict) -> int:
    return int(rec.get("dipole_sign") or 0)


def signed_return(items: list[dict], idx: int, horizon: int) -> float:
    direction = dipole_sign(items[idx])
    if direction == 0:
        return 0.0
    future_idx = min(len(items) - 1, idx + horizon)
    cur_close = float(items[idx]["close_end"])
    fut_close = float(items[future_idx]["close_end"])
    if cur_close <= 0:
        return 0.0
    return direction * math.log(max(fut_close, 1e-12) / cur_close) * 10000.0


def future_path(items: list[dict], idx: int, horizon: int) -> dict:
    direction = dipole_sign(items[idx])
    first_same_strong = None
    first_opp_strong = None
    first_same_nascent = None
    first_any_strong = None
    regimes: list[str] = []
    for lead in range(1, horizon + 1):
        j = idx + lead
        if j >= len(items):
            break
        regime = str(items[j]["regime"])
        regimes.append(regime)
        rsign = sign_of_regime(regime)
        if regime in STRONG and first_any_strong is None:
            first_any_strong = lead
        if regime in STRONG and rsign == direction and first_same_strong is None:
            first_same_strong = lead
        if regime in STRONG and rsign == -direction and first_opp_strong is None:
            first_opp_strong = lead
        if regime in NASCENT and rsign == direction and first_same_nascent is None:
            first_same_nascent = lead
    return {
        "first_same_strong": first_same_strong,
        "first_opp_strong": first_opp_strong,
        "first_any_strong": first_any_strong,
        "first_same_nascent": first_same_nascent,
        "regimes": regimes,
        "signed_return_bps": signed_return(items, idx, horizon),
    }


def canary_rules() -> list[tuple[str, str, object]]:
    return [
        ("weak", "Weak dipole", lambda items, i: 0.15 <= items[i]["abs_dipole"] < 0.25),
        (
            "persistent_weak",
            "Persistent weak dipole",
            lambda items, i: (
                i > 0
                and 0.15 <= items[i]["abs_dipole"] < 0.25
                and 0.15 <= items[i - 1]["abs_dipole"] < 0.25
                and dipole_sign(items[i]) == dipole_sign(items[i - 1])
            ),
        ),
        (
            "volume_moderate",
            "Volume-confirmed moderate dipole",
            lambda items, i: items[i]["abs_dipole"] >= 0.30 and items[i]["volume_zscore"] >= 0.0,
        ),
        (
            "acl_moderate",
            "Autocorr-confirmed moderate dipole",
            lambda items, i: items[i]["abs_dipole"] >= 0.30 and items[i]["dipole_acl1"] >= 0.0,
        ),
    ]


def eligible_record(rec: dict, *, eq_only: bool) -> bool:
    if str(rec["regime"]) in STRONG:
        return False
    if dipole_sign(rec) == 0:
        return False
    if eq_only and str(rec["regime"]) not in EARLY:
        return False
    return True


def summarize_candidates(candidates: list[tuple[list[dict], int]], horizon: int) -> dict:
    paths = [future_path(items, idx, horizon) for items, idx in candidates]
    same = [p for p in paths if p["first_same_strong"] is not None]
    opp = [p for p in paths if p["first_opp_strong"] is not None]
    nascent = [p for p in paths if p["first_same_nascent"] is not None]
    returns = [float(p["signed_return_bps"]) for p in paths]
    leads = [int(p["first_same_strong"]) for p in same]
    return {
        "candidate": len(candidates),
        "same_strong_rate_pct": pct(len(same) / len(candidates) if candidates else 0.0),
        "same_nascent_rate_pct": pct(len(nascent) / len(candidates) if candidates else 0.0),
        "opposite_strong_rate_pct": pct(len(opp) / len(candidates) if candidates else 0.0),
        "avg_signed_return_bps": round(avg(returns), 3),
        "median_signed_return_bps": round(med(returns), 3),
        "median_lead_chunks": round(med(leads), 3),
        "lead_distribution": dict(sorted(Counter(leads).items())),
    }


def rule_deepdive(grouped: dict[tuple[str, str], list[dict]]) -> dict:
    out: dict = {}
    for eq_only in (False, True):
        scope = "eq_only" if eq_only else "non_strong"
        rows = []
        for horizon in (1, 2, 3, 4, 5, 6):
            eligible: list[tuple[list[dict], int]] = []
            for items in grouped.values():
                for idx in range(0, max(0, len(items) - horizon)):
                    if eligible_record(items[idx], eq_only=eq_only):
                        eligible.append((items, idx))
            base = summarize_candidates(eligible, horizon)
            for rule_id, label, pred in canary_rules():
                candidates = [
                    (items, idx) for items, idx in eligible
                    if bool(pred(items, idx))
                ]
                summary = summarize_candidates(candidates, horizon)
                base_rate = base["same_strong_rate_pct"] / 100.0
                hit_rate = summary["same_strong_rate_pct"] / 100.0
                summary.update({
                    "scope": scope,
                    "rule": rule_id,
                    "label": label,
                    "horizon_chunks": horizon,
                    "eligible": len(eligible),
                    "coverage_pct": pct(len(candidates) / len(eligible) if eligible else 0.0),
                    "base_same_strong_rate_pct": base["same_strong_rate_pct"],
                    "lift_vs_base": round(hit_rate / base_rate, 3) if base_rate > 0 and candidates else 0.0,
                })
                rows.append(summary)
        out[scope] = rows
    return out


def transition_funnels(grouped: dict[tuple[str, str], list[dict]]) -> dict:
    out: dict = {}
    for rule_id, label, pred in canary_rules():
        counts = Counter()
        examples = []
        for (asset, venue), items in grouped.items():
            for idx in range(0, max(0, len(items) - 6)):
                if not eligible_record(items[idx], eq_only=True) or not bool(pred(items, idx)):
                    continue
                path = future_path(items, idx, 6)
                if path["first_same_strong"] is not None and path["first_same_nascent"] is not None:
                    if path["first_same_nascent"] < path["first_same_strong"]:
                        bucket = "canary_to_nascent_to_strong"
                    else:
                        bucket = "canary_to_strong_then_nascent"
                elif path["first_same_strong"] is not None:
                    bucket = "canary_direct_to_strong"
                elif path["first_same_nascent"] is not None:
                    bucket = "canary_to_nascent_only"
                elif path["first_opp_strong"] is not None:
                    bucket = "canary_failed_opposite_strong"
                else:
                    bucket = "canary_no_confirmation"
                counts[bucket] += 1
                if len(examples) < 8 and bucket in {"canary_to_nascent_to_strong", "canary_direct_to_strong"}:
                    examples.append({
                        "asset": asset,
                        "venue": venue,
                        "idx": idx,
                        "ts_end": items[idx]["ts_end"],
                        "dipole": round(float(items[idx]["mean_dipole"]), 3),
                        "volume_zscore": round(float(items[idx]["volume_zscore"]), 3),
                        "acl1": round(float(items[idx]["dipole_acl1"]), 3),
                        "path": path["regimes"],
                        "bucket": bucket,
                        "signed_return_bps_6chunks": round(float(path["signed_return_bps"]), 3),
                    })
        total = sum(counts.values())
        out[rule_id] = {
            "label": label,
            "total": total,
            "counts": dict(counts),
            "rates_pct": {k: pct(v / total if total else 0.0) for k, v in counts.items()},
            "examples": examples,
        }
    return out


def direction_and_pair_splits(grouped: dict[tuple[str, str], list[dict]]) -> dict:
    out: dict = {}
    for rule_id, label, pred in canary_rules():
        rows = []
        buckets: dict[tuple[str, int], list[tuple[list[dict], int]]] = defaultdict(list)
        for (asset, venue), items in grouped.items():
            for idx in range(0, max(0, len(items) - 4)):
                if eligible_record(items[idx], eq_only=True) and bool(pred(items, idx)):
                    buckets[(f"{asset}/{venue}", dipole_sign(items[idx]))].append((items, idx))
        for (pair, direction), candidates in sorted(buckets.items()):
            summary = summarize_candidates(candidates, 4)
            if summary["candidate"] >= 3:
                summary.update({
                    "pair": pair,
                    "direction": "up" if direction > 0 else "down",
                })
                rows.append(summary)
        rows.sort(key=lambda r: (r["same_strong_rate_pct"], r["candidate"]), reverse=True)
        out[rule_id] = {"label": label, "rows": rows}
    return out


def cross_venue_deepdive(records: list[dict]) -> dict:
    by_asset: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_asset[str(rec["asset"])].append(rec)
    out: dict = {}
    for asset, items in by_asset.items():
        items.sort(key=lambda r: float(r["ts_end"]))
        slots: dict[int, list[dict]] = defaultdict(list)
        for rec in items:
            slots[int(float(rec["ts_end"]) // 900) * 900].append(rec)
        rows = []
        for lo, hi in ((0.10, 0.25), (0.15, 0.25), (0.20, 0.30), (0.25, 0.40)):
            for min_venues in (2, 3):
                for eq_only in (False, True):
                    candidates = []
                    for slot, recs in slots.items():
                        for direction in (1, -1):
                            signed = [
                                r for r in recs
                                if eligible_record(r, eq_only=eq_only)
                                and lo <= float(r["abs_dipole"]) < hi
                                and dipole_sign(r) == direction
                            ]
                            if len({str(r["venue"]) for r in signed}) < min_venues:
                                continue
                            future = [
                                r for r in items
                                if slot < float(r["ts_end"]) <= slot + 45 * 60
                            ]
                            same = any(str(r["regime"]) in STRONG and sign_of_regime(str(r["regime"])) == direction for r in future)
                            opp = any(str(r["regime"]) in STRONG and sign_of_regime(str(r["regime"])) == -direction for r in future)
                            anchor = max(signed, key=lambda r: abs(float(r["mean_dipole"])))
                            last_future = max(future, key=lambda r: r["ts_end"], default=None)
                            ret = 0.0
                            if last_future and float(anchor["close_end"]) > 0:
                                ret = direction * math.log(max(float(last_future["close_end"]), 1e-12) / float(anchor["close_end"])) * 10000.0
                            candidates.append((same, opp, ret, sorted({str(r["venue"]) for r in signed})))
                    if candidates:
                        same_n = sum(1 for c in candidates if c[0])
                        opp_n = sum(1 for c in candidates if c[1])
                        returns = [float(c[2]) for c in candidates]
                        rows.append({
                            "band": f"{lo:.2f}_{hi:.2f}",
                            "min_venues": min_venues,
                            "scope": "eq_only" if eq_only else "non_strong",
                            "candidate": len(candidates),
                            "same_strong_rate_pct": pct(same_n / len(candidates)),
                            "opposite_strong_rate_pct": pct(opp_n / len(candidates)),
                            "avg_signed_return_bps": round(avg(returns), 3),
                            "venue_sets": dict(Counter(",".join(c[3]) for c in candidates).most_common()),
                        })
        rows.sort(key=lambda r: (r["same_strong_rate_pct"], r["candidate"], -r["opposite_strong_rate_pct"]), reverse=True)
        out[asset] = rows
    return out


def write_report(output_dir: Path, result: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dipole_canary_deepdive_results.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Dipole Canary Deep Dive",
        "",
        "This pass separates pure early states from already-visible nascent pressure and asks how often dipole canaries become same-direction Whale/Herd confirmations.",
        "",
        "## Rule Summary",
        "",
    ]
    for scope, rows in result["rule_deepdive"].items():
        lines.append(f"### Scope: {scope}")
        lines.append("")
        lines.append("| rule | horizon | candidates | coverage | base hit | hit | lift | nascent | opposite | avg ret bps | lead |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        chosen = [r for r in rows if r["horizon_chunks"] in (2, 4, 6)]
        for row in chosen:
            lines.append(
                f"| {row['label']} | {row['horizon_chunks']} | {row['candidate']} | "
                f"{row['coverage_pct']}% | {row['base_same_strong_rate_pct']}% | "
                f"{row['same_strong_rate_pct']}% | {row['lift_vs_base']} | "
                f"{row['same_nascent_rate_pct']}% | {row['opposite_strong_rate_pct']}% | "
                f"{row['avg_signed_return_bps']} | {row['median_lead_chunks']} |"
            )
        lines.append("")
    lines.extend(["## Pure Early-State Funnels", ""])
    for rule_id, funnel in result["transition_funnels"].items():
        lines.append(f"### {funnel['label']}")
        lines.append("")
        lines.append("| outcome | count | rate |")
        lines.append("|---|---:|---:|")
        for k, v in sorted(funnel["counts"].items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"| {k} | {v} | {funnel['rates_pct'][k]}% |")
        lines.append("")
        for ex in funnel["examples"][:3]:
            lines.append(
                f"- {ex['asset']}/{ex['venue']} idx={ex['idx']} dipole={ex['dipole']:+.3f} "
                f"vol_z={ex['volume_zscore']:+.2f} acl1={ex['acl1']:+.2f} "
                f"{ex['bucket']} path={ex['path']} ret6={ex['signed_return_bps_6chunks']}bps"
            )
        lines.append("")
    lines.extend(["## Direction And Venue Splits", ""])
    for rule_id, split in result["direction_and_pair_splits"].items():
        lines.append(f"### {split['label']}")
        lines.append("")
        lines.append("| pair | dir | candidates | hit | opposite | avg ret bps |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in split["rows"][:10]:
            lines.append(
                f"| {row['pair']} | {row['direction']} | {row['candidate']} | "
                f"{row['same_strong_rate_pct']}% | {row['opposite_strong_rate_pct']}% | "
                f"{row['avg_signed_return_bps']} |"
            )
        lines.append("")
    lines.extend(["## Cross-Venue Same-Direction Pressure", ""])
    for asset, rows in result["cross_venue_deepdive"].items():
        lines.append(f"### {asset}")
        lines.append("")
        lines.append("| band | venues | scope | candidates | hit | opposite | avg ret bps | venue sets |")
        lines.append("|---|---:|---|---:|---:|---:|---:|---|")
        for row in rows[:10]:
            venue_sets = "; ".join(f"{k}:{v}" for k, v in list(row["venue_sets"].items())[:3])
            lines.append(
                f"| {row['band']} | {row['min_venues']} | {row['scope']} | {row['candidate']} | "
                f"{row['same_strong_rate_pct']}% | {row['opposite_strong_rate_pct']}% | "
                f"{row['avg_signed_return_bps']} | {venue_sets} |"
            )
        lines.append("")
    lines.extend([
        "## Read",
        "",
        "The pure early-state rows are the important rows because they test dipole before the classifier has already called nascent pressure. The signal still holds there, so the canary effect is not an artifact of including `WHALE_NASCENT_*` chunks.",
        "",
        "- Weak dipole is broad coverage but soft quality: useful as an internal watch, not visible by itself.",
        "- Persistent weak dipole is the cleanest low-intensity watch: lower coverage, stronger lift, positive average signed returns, and usually 2-3 chunks of lead time at longer horizons.",
        "- Volume-confirmed moderate dipole is the cleanest higher-intensity watch: it keeps roughly 2x lift over the next 2 chunks even in pure early states, with low opposite-confirmation rates.",
        "- Autocorr-confirmed moderate dipole predicts later Whale/Herd labels strongly, but its average signed return is negative in these samples. Treat it as a structure/transition alarm, not as a directional trade edge.",
        "- Cross-venue same-direction pressure is most interesting on BTC. ETH cross-venue pressure has higher opposite-confirmation risk, so it needs stricter handling or more live evidence.",
        "",
        "Product policy: keep this as amber intelligence. A practical state ladder is `internal watch` for weak dipole, `Pressure forming` for persistent weak or volume-confirmed moderate pressure, and `high-priority watch` when same-direction pressure appears on multiple venues. Expire the watch when dipole flips, confirmed opposite Whale/Herd appears, or the pressure fails to confirm within roughly 45-90 minutes.",
    ])
    (output_dir / "dipole_canary_deepdive_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="pass21_dipole_canary_deepdive_out")
    parser.add_argument("--max-bars", type=int, default=0)
    args = parser.parse_args()

    records, summaries = load_records(max_bars=args.max_bars or None)
    grouped = group_records(records)
    result = {
        "sources": [s.__dict__ for s in summaries],
        "rule_deepdive": rule_deepdive(grouped),
        "transition_funnels": transition_funnels(grouped),
        "direction_and_pair_splits": direction_and_pair_splits(grouped),
        "cross_venue_deepdive": cross_venue_deepdive(records),
    }
    write_report(Path(args.output_dir), result)
    print(f"wrote {Path(args.output_dir) / 'dipole_canary_deepdive_report.md'}")


if __name__ == "__main__":
    main()
