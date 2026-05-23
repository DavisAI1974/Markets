from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from daily_health_loader import report_path_for
from daily_limits import build_daily_tracker, daily_limit_health, load_daily_limits
from dipole_coupling import build_dipole_coupling
from onchain_features import classify_onchain_regime
from strategy_bucket_stats import (
    aggregate_bucket_stats,
    aggregate_venue_stats,
    bucket_health,
    load_thresholds,
    load_venue_prefs,
    normalize_family,
    profit_R_for_trade,
    venue_weight,
)


def _date_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(float(ts), timezone.utc).date().isoformat()


def _ts_from_iso(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _trade_day(trade: dict[str, Any]) -> str:
    ts = _float(trade.get("exit_ts_utc") or trade.get("ts_utc"))
    if ts <= 0:
        ts = _ts_from_iso(trade.get("close_ts"))
    if ts <= 0:
        return ""
    return _date_from_ts(ts)


def _iter_result_paths(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            paths.extend(sorted(p.glob("**/*results.json")))
        elif p.exists():
            paths.append(p)
    return paths


def _extract_trades(payload: dict[str, Any]) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    for account in (payload.get("accounts") or {}).values():
        for trade in account.get("trades") or []:
            if trade.get("status") == "closed":
                out = dict(trade)
                if out.get("profit_R") is None:
                    out["profit_R"] = profit_R_for_trade(out)
                trades.append(out)
    return trades


def _bucket_session_from_id(bucket_id: str) -> str:
    parts = str(bucket_id or "").split("|")
    return parts[4] if len(parts) >= 5 else "all"


def _normalize_flat_trade(raw: dict[str, Any], source: Path) -> dict[str, Any] | None:
    status = str(raw.get("status") or raw.get("order_state") or "").lower()
    has_close_ts = bool(raw.get("close_ts")) or _float(raw.get("exit_ts_utc")) > 0
    if status in {"open", "pending", "working"} and not has_close_ts:
        return None
    if status and status not in {"closed", "filled", "partial", "rejected", "expired"} and not has_close_ts:
        return None
    close_ts = _ts_from_iso(raw.get("close_ts"))
    if close_ts <= 0:
        close_ts = _float(raw.get("exit_ts_utc"))
    family = raw.get("family") or raw.get("trade_strategy_id") or raw.get("kind") or "unknown"
    bucket = str(raw.get("bucket_id") or "")
    side = str(raw.get("side") or "").lower()
    out = {
        **raw,
        "status": "closed",
        "trade_strategy_id": str(family),
        "asset": raw.get("asset") or "unknown",
        "venue": raw.get("venue") or "unknown",
        "side": side,
        "bucket_session": raw.get("bucket_session") or _bucket_session_from_id(bucket),
        "ts_utc": _float(raw.get("ts_utc") or raw.get("open_ts_utc") or close_ts),
        "exit_ts_utc": close_ts,
        "profit_R": _float(raw.get("pnl_R") if raw.get("pnl_R") is not None else raw.get("profit_R")),
        "realized_pnl_usd": _float(
            raw.get("realized_pnl_usd")
            if raw.get("realized_pnl_usd") is not None
            else _float(raw.get("pnl_R")) * _float(raw.get("risk_amount"), 1.0)
        ),
        "fill_price": _float(raw.get("entry_price_actual") or raw.get("fill_price") or raw.get("price")),
        "exit_price": _float(raw.get("exit_price_actual") or raw.get("exit_price")),
        "_source_result": str(source),
    }
    if bucket:
        out["bucket_id"] = bucket
    if out["exit_ts_utc"] <= 0:
        return None
    return out


def _load_flat_trades_for_date(trade_logs: Iterable[Path], day: str | None = None) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    for path in trade_logs:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                trade = _normalize_flat_trade(raw, path)
                if trade is None:
                    continue
                if day and _trade_day(trade) != day:
                    continue
                trades.append(trade)
    return trades


def collect_trades(inputs: list[str], day: str | None = None, trade_logs: list[str] | None = None) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    for path in _iter_result_paths(inputs):
        if path.suffix.lower() == ".jsonl":
            continue
        try:
            payload = _load_json(path)
        except json.JSONDecodeError:
            continue
        for trade in _extract_trades(payload):
            if day and _trade_day(trade) != day:
                continue
            trade["_source_result"] = str(path)
            trades.append(trade)
    if trade_logs:
        trades.extend(_load_flat_trades_for_date([Path(p) for p in trade_logs], day))
    return trades


def _sharpe(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    var = sum((v - avg) ** 2 for v in values) / (len(values) - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return None
    return avg / sd * math.sqrt(len(values))


def _family_stats(trades: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[normalize_family(trade.get("trade_strategy_id") or "unknown")].append(trade)
    out: dict[str, dict[str, Any]] = {}
    for family, rows in grouped.items():
        pnls = [_float(t.get("profit_R")) for t in rows]
        wins = sum(1 for t in rows if _float(t.get("profit_R")) > 0)
        n = len(rows)
        pnl_r = sum(pnls)
        sharpe = _sharpe(pnls)
        win_rate = wins / n if n else None
        status = "learning"
        if n >= 50 and win_rate is not None:
            status = "deallocated" if win_rate < 0.45 or (sharpe is not None and sharpe < 0.8) or pnl_r <= -3.0 else "ok"
        out[family] = {
            "status": status,
            "win_rate": round(win_rate, 6) if win_rate is not None else None,
            "sharpe": round(sharpe, 6) if sharpe is not None else None,
            "trades": n,
            "pnl_R": round(pnl_r, 6),
        }
    return out


def _signed_slippage_bps(expected: Any, actual: Any, side: str) -> float | None:
    expected_f = _float(expected)
    actual_f = _float(actual)
    if expected_f <= 0 or actual_f <= 0:
        return None
    signed = 1.0 if str(side or "").lower() == "buy" else -1.0
    return signed * (actual_f - expected_f) / expected_f * 10000.0


def _entry_slippage_bps(trade: dict[str, Any]) -> float | None:
    expected = trade.get("entry_price_expected") or trade.get("expected_entry_price") or trade.get("entry_price") or trade.get("fill_price")
    fill = trade.get("entry_price_actual") or trade.get("fill_price")
    return _signed_slippage_bps(expected, fill, str(trade.get("side") or ""))


def _exit_slippage_bps(trade: dict[str, Any]) -> float | None:
    expected = trade.get("exit_price_expected") or trade.get("expected_exit_price") or trade.get("exit_price")
    actual = trade.get("exit_price_actual") or trade.get("exit_price")
    side = "sell" if str(trade.get("side") or "").lower() == "buy" else "buy"
    return _signed_slippage_bps(expected, actual, side)


def _order_filled(trade: dict[str, Any]) -> bool:
    state = str(trade.get("order_state") or "filled").lower()
    return state in {"filled", "partial", "closed"}


def _order_rejected(trade: dict[str, Any]) -> bool:
    state = str(trade.get("order_state") or "").lower()
    return state in {"rejected", "expired"}


def _signal_key(trade: dict[str, Any]) -> str:
    return str(trade.get("signal_id") or trade.get("intent_id") or trade.get("id") or f"{trade.get('_source_result')}:{trade.get('ts_utc')}")


def _execution_penalty(entry_slip: float, exit_slip: float, fill_rate: float) -> float:
    return (
        max(0.0, entry_slip) * 0.1
        + max(0.0, exit_slip) * 0.1
        + max(0.0, 1.0 - fill_rate) * 10.0
    )


def _venue_status(win_rate: float | None, execution_penalty: float) -> str:
    if execution_penalty > 20.0 or (win_rate is not None and win_rate < 0.45):
        return "kill"
    if execution_penalty > 10.0 or (win_rate is not None and win_rate < 0.50):
        return "degraded"
    return "ok"


def _slippage_bps(trade: dict[str, Any]) -> float:
    slip = _entry_slippage_bps(trade)
    return float(slip) if slip is not None else 0.0


def _status_from_bucket_health(state: str) -> str:
    if state == "hard_kill":
        return "hard_kill"
    if state == "kill":
        return "kill"
    if state == "paper_only":
        return "learning"
    return "ok"


def _perf_rows(trades: list[dict[str, Any]], keys: list[str]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        parts = [str(trade.get(k) or "unknown") for k in keys]
        grouped["|".join(parts)].append(trade)
    out: dict[str, dict[str, Any]] = {}
    for key, rows in sorted(grouped.items()):
        pnls = [_float(t.get("profit_R")) for t in rows]
        wins = sum(1 for v in pnls if v > 0)
        n = len(rows)
        out[key] = {
            "trades": n,
            "win_rate": round(wins / n, 6) if n else None,
            "pnl_R": round(sum(pnls), 6),
            "avg_R": round(sum(pnls) / n, 6) if n else None,
        }
    return out


def _onchain_regime_for_trade(trade: dict[str, Any]) -> str:
    onchain = trade.get("onchain_features")
    if isinstance(onchain, dict) and onchain:
        labels = onchain.get("labels") or {}
        return str(labels.get("onchain_regime") or classify_onchain_regime(onchain))
    return str(
        trade.get("onchain_regime")
        or ((trade.get("labels") or {}).get("onchain_regime") if isinstance(trade.get("labels"), dict) else "")
        or "unknown"
    )


def _coupling_for_trade(trade: dict[str, Any]) -> dict[str, Any]:
    coupling = trade.get("dipole_coupling")
    if isinstance(coupling, dict) and coupling:
        return coupling
    return build_dipole_coupling(trade=trade).to_dict()


def _context_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        coupling = _coupling_for_trade(row)
        row["_onchain_regime"] = _onchain_regime_for_trade(row)
        row["_coupling_state"] = str(coupling.get("coupling_state") or "neutral")
        row["_family"] = normalize_family(row.get("trade_strategy_id") or "unknown")
        enriched.append(row)
    return {
        "trades_by_onchain_regime": _perf_rows(enriched, ["_onchain_regime"]),
        "trades_by_coupling_state": _perf_rows(enriched, ["_coupling_state"]),
        "trades_by_family_onchain_coupling": _perf_rows(
            enriched,
            ["_family", "_onchain_regime", "_coupling_state"],
        ),
    }


def build_report(day: str, trades: list[dict[str, Any]], *, bucket_thresholds: str, venue_prefs: str, daily_limits: str) -> dict[str, Any]:
    thresholds = load_thresholds(bucket_thresholds)
    prefs = load_venue_prefs(venue_prefs)
    limits = load_daily_limits(daily_limits)
    bucket_stats = aggregate_bucket_stats(trades)
    venue_stats = aggregate_venue_stats(trades)
    tracker = build_daily_tracker(trades)

    families = _family_stats(trades)
    buckets: dict[str, Any] = {}
    events: list[dict[str, str]] = []
    for bid, row in sorted(bucket_stats.items()):
        health = bucket_health(bid, row, thresholds)
        state = _status_from_bucket_health(str(health.get("state") or ""))
        d = row.to_dict()
        buckets[bid] = {
            "status": state,
            "trades": d["trades"],
            "win_rate": d["win_rate"],
            "pnl_R": d["pnl_R"],
        }
        if state in {"kill", "hard_kill"}:
            events.append({
                "type": "bucket_killed",
                "bucket_id": bid,
                "reason": "; ".join(health.get("reasons") or [f"status={state}"]),
            })
        elif state == "ok":
            events.append({
                "type": "bucket_ok",
                "bucket_id": bid,
                "reason": f"trades {d['trades']}, win_rate {d['win_rate']}, pnl_R {d['pnl_R']}",
            })

    venues: dict[str, Any] = {}
    for key, row in sorted(venue_stats.items()):
        d = row.to_dict()
        rows = [t for t in trades if normalize_family(t.get("trade_strategy_id") or "unknown") == row.strategy_family and str(t.get("asset") or "").upper() == row.asset and str(t.get("venue") or "").lower() == row.venue]
        entry_slips = [s for s in (_entry_slippage_bps(t) for t in rows) if s is not None]
        exit_slips = [s for s in (_exit_slippage_bps(t) for t in rows) if s is not None]
        signal_ids = {_signal_key(t) for t in rows}
        fills = sum(1 for t in rows if _order_filled(t))
        rejects = sum(1 for t in rows if _order_rejected(t))
        fill_rate = fills / max(1, len(signal_ids))
        entry_avg = sum(entry_slips) / len(entry_slips) if entry_slips else 0.0
        exit_avg = sum(exit_slips) / len(exit_slips) if exit_slips else 0.0
        penalty = _execution_penalty(entry_avg, exit_avg, fill_rate)
        status = _venue_status(d["win_rate"], penalty)
        health = venue_weight(row.strategy_family, row.asset, row.venue, row, prefs)
        if _float(health.get("weight"), 1.0) <= 0.0:
            status = "kill"
        elif status == "ok" and _float(health.get("adjustment"), 1.0) < 1.0:
            status = "degraded"
        venues[key] = {
            "status": status,
            "trades": d["trades"],
            "win_rate": d["win_rate"],
            "pnl_R": d["pnl_R"],
            "entry_slippage_bps_avg": round(entry_avg, 6),
            "exit_slippage_bps_avg": round(exit_avg, 6),
            "slippage_bps_avg": round(entry_avg + exit_avg, 6),
            "fill_rate": round(fill_rate, 6),
            "reject_count": rejects,
            "execution_penalty": round(penalty, 6),
        }

    daily_families: dict[str, Any] = {}
    for family in sorted(families):
        audit = daily_limit_health(family=family, bucket="", day=day, tracker=tracker, limits=limits)
        family_limit_reached = any("Family daily loss" in x for x in audit.get("blockers") or [])
        daily_families[family] = {
            "pnl_R_today": audit["family_pnl_R"],
            "max_loss_R": audit["family_max_loss_R"],
            "limit_reached": family_limit_reached,
        }
        if family_limit_reached:
            families[family]["status"] = "deallocated"
            events.append({
                "type": "family_deallocated",
                "family": family,
                "reason": f"daily loss {audit['family_pnl_R']:.2f}R reached {audit['family_max_loss_R']:.2f}R",
            })

    daily_buckets: dict[str, Any] = {}
    for bid in sorted(buckets):
        family = bid.split("|", 1)[0]
        audit = daily_limit_health(family=family, bucket=bid, day=day, tracker=tracker, limits=limits)
        if audit["bucket_max_loss_R"] is None:
            continue
        daily_buckets[bid] = {
            "pnl_R_today": audit["bucket_pnl_R"],
            "max_loss_R": audit["bucket_max_loss_R"],
            "limit_reached": any("Bucket daily loss" in x for x in audit.get("blockers") or []),
        }

    context = _context_stats(trades)
    return {
        "date": day,
        "summary": {"families": families},
        "buckets": buckets,
        "venues": venues,
        "context": context,
        "daily_limits_state": {
            "families": daily_families,
            "buckets": daily_buckets,
        },
        "events": events,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [f"# Daily Health {report.get('date')}", ""]
    lines.append("## Families")
    lines.append("| Family | Status | Trades | Win rate | Sharpe | PnL R |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for family, row in sorted(((report.get("summary") or {}).get("families") or {}).items()):
        win = row.get("win_rate")
        lines.append(f"| `{family}` | {row.get('status')} | {row.get('trades')} | {'' if win is None else f'{float(win)*100:.1f}%'} | {row.get('sharpe')} | {row.get('pnl_R')} |")
    lines.extend(["", "## Events"])
    for event in report.get("events") or []:
        label = event.get("bucket_id") or event.get("family") or ""
        lines.append(f"- `{event.get('type')}` {label}: {event.get('reason')}")
    context = report.get("context") or {}
    coupling = context.get("trades_by_coupling_state") or {}
    if coupling:
        lines.extend(["", "## Coupling"])
        lines.append("| State | Trades | Win rate | PnL R |")
        lines.append("|---|---:|---:|---:|")
        for state, row in sorted(coupling.items()):
            win = row.get("win_rate")
            lines.append(
                f"| `{state}` | {row.get('trades')} | "
                f"{'' if win is None else f'{float(win)*100:.1f}%'} | {row.get('pnl_R')} |"
            )
    onchain = context.get("trades_by_onchain_regime") or {}
    if onchain:
        lines.extend(["", "## On-Chain"])
        lines.append("| Regime | Trades | Win rate | PnL R |")
        lines.append("|---|---:|---:|---:|")
        for regime, row in sorted(onchain.items()):
            win = row.get("win_rate")
            lines.append(
                f"| `{regime}` | {row.get('trades')} | "
                f"{'' if win is None else f'{float(win)*100:.1f}%'} | {row.get('pnl_R')} |"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default="")
    parser.add_argument("--input", action="append", default=[], help="Replay result file or directory. Can be repeated.")
    parser.add_argument("--trade-log", action="append", default=[], help="Flat JSONL trade log. Can be repeated.")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--bucket-thresholds", default="bucket_thresholds.json")
    parser.add_argument("--venue-prefs", default="venue_prefs.json")
    parser.add_argument("--daily-limits", default="daily_limits.json")
    parser.add_argument("--write-md", action="store_true")
    args = parser.parse_args()

    inputs = args.input or ["."]
    trades = collect_trades(inputs, trade_logs=args.trade_log)
    day = args.day
    if not day:
        days = sorted({_trade_day(t) for t in trades if _trade_day(t)})
        day = days[-1] if days else datetime.now(timezone.utc).date().isoformat()
        if args.trade_log:
            trades = collect_trades(inputs, day=day, trade_logs=args.trade_log)
    else:
        trades = [t for t in trades if _trade_day(t) == day]
    report = build_report(day, trades, bucket_thresholds=args.bucket_thresholds, venue_prefs=args.venue_prefs, daily_limits=args.daily_limits)
    out = report_path_for(day, args.reports_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    if args.write_md:
        md = out.with_suffix(".md")
        write_markdown(report, md)
        print(f"wrote {md}")


if __name__ == "__main__":
    main()
