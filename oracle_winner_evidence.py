"""Per-canonical-key outcome ledger and admission decision.

Structural learning loop: every closed trade (live or backtest) appends to a
single append-only jsonl ledger keyed by canonical_trade_key. Admission
decisions read the current posterior from that ledger and compare a Wilson
lower bound to a break-even win-rate derived from fees + rolling payoff stats.

No tuning to any particular window. Constants are either economic (fees) or
statistical (confidence level). Thresholds float with measured payoff.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_LEDGER_PATH = Path(__file__).parent / "research" / "strategy_evolution" / "oracle_winner_evidence_ledger.jsonl"
WILSON_Z_90 = 1.6449
WILSON_Z_95 = 1.96
N_MIN_FOR_BANK = 10
DEFAULT_FEES_BPS_ROUNDTRIP = 10.0

_CACHE: dict[str, Any] = {"path": None, "mtime_ns": 0, "size": 0, "by_key": None}

# Process-level ledger override. Set at backtest startup so record_close calls from
# deep call sites (mock_trade_replay.close_trade) honor it without plumbing scenario
# dicts through every signature. None = use DEFAULT_LEDGER_PATH.
_ACTIVE_LEDGER_PATH: Path | None = None


def set_active_ledger_path(path: str | Path | None) -> None:
    """Set the process-wide ledger override. Call once at backtest startup."""
    global _ACTIVE_LEDGER_PATH
    _ACTIVE_LEDGER_PATH = Path(path) if path else None


def _ledger_path(path: str | Path | None = None) -> Path:
    if path:
        return Path(path)
    if _ACTIVE_LEDGER_PATH is not None:
        return _ACTIVE_LEDGER_PATH
    return DEFAULT_LEDGER_PATH


def record_close(
    canonical_key: str,
    net_bps: float,
    role: str,
    source: str = "live",
    ts: float | None = None,
    path: str | Path | None = None,
) -> None:
    """Append one closed-trade outcome. role: 'bank_allocated'|'oracle_shadow'.
    source: 'live'|'backtest'|'historic_parity'."""
    if not canonical_key:
        return
    p = _ledger_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": float(ts if ts is not None else time.time()),
        "key": str(canonical_key),
        "net_bps": float(net_bps),
        "role": str(role or ""),
        "source": str(source or ""),
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    _CACHE["by_key"] = None  # invalidate


def _load_ledger(path: str | Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Returns {key: [rows...]}. Cached by mtime+size; rereads on change."""
    p = _ledger_path(path)
    if not p.exists():
        return {}
    stat = p.stat()
    if (
        _CACHE.get("path") == str(p)
        and _CACHE.get("mtime_ns") == stat.st_mtime_ns
        and _CACHE.get("size") == stat.st_size
        and _CACHE.get("by_key") is not None
    ):
        return _CACHE["by_key"]
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            k = r.get("key")
            if not k:
                continue
            by_key[k].append(r)
    _CACHE["path"] = str(p)
    _CACHE["mtime_ns"] = stat.st_mtime_ns
    _CACHE["size"] = stat.st_size
    _CACHE["by_key"] = dict(by_key)
    return _CACHE["by_key"]


def _wilson_lb(wins: int, n: int, z: float = WILSON_Z_90) -> float:
    """Wilson lower bound on P(win). Returns 0.0 for n=0."""
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1.0 + (z * z) / n
    center = p + (z * z) / (2.0 * n)
    margin = z * math.sqrt(p * (1.0 - p) / n + (z * z) / (4.0 * n * n))
    return max(0.0, (center - margin) / denom)


def posterior(canonical_key: str, path: str | Path | None = None) -> dict[str, Any]:
    """Current posterior for one key. Win = net_bps > 0."""
    rows = _load_ledger(path).get(canonical_key, [])
    n = len(rows)
    wins = sum(1 for r in rows if float(r.get("net_bps") or 0.0) > 0)
    losses = n - wins
    win_bps = [float(r["net_bps"]) for r in rows if float(r.get("net_bps") or 0.0) > 0]
    loss_bps = [abs(float(r["net_bps"])) for r in rows if float(r.get("net_bps") or 0.0) <= 0]
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "p_win_mean": (wins / n) if n else 0.0,
        "p_win_lb_90": _wilson_lb(wins, n, WILSON_Z_90),
        "p_win_lb_95": _wilson_lb(wins, n, WILSON_Z_95),
        "avg_win_bps": (sum(win_bps) / len(win_bps)) if win_bps else 0.0,
        "avg_loss_bps": (sum(loss_bps) / len(loss_bps)) if loss_bps else 0.0,
        "last_ts": max((float(r.get("ts") or 0.0) for r in rows), default=0.0),
    }


def global_rolling_payoff(path: str | Path | None = None, limit: int = 500) -> dict[str, float]:
    """Average win / loss bps across the most recent `limit` closes, across all keys."""
    by_key = _load_ledger(path)
    rows: list[dict[str, Any]] = []
    for k_rows in by_key.values():
        rows.extend(k_rows)
    rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
    recent = rows[:limit]
    wins = [float(r["net_bps"]) for r in recent if float(r.get("net_bps") or 0.0) > 0]
    losses = [abs(float(r["net_bps"])) for r in recent if float(r.get("net_bps") or 0.0) <= 0]
    return {
        "n": len(recent),
        "avg_win_bps": (sum(wins) / len(wins)) if wins else 0.0,
        "avg_loss_bps": (sum(losses) / len(losses)) if losses else 0.0,
    }


def break_even_winrate(avg_win_bps: float, avg_loss_bps: float, fees_bps: float = 0.0) -> float:
    """Win rate p such that EV = p*win - (1-p)*loss - fees = 0.
    All inputs in net bps already-fee-inclusive: pass fees_bps=0.
    Returns 0.5 if either avg is zero (insufficient data => neutral)."""
    w = float(avg_win_bps)
    l = float(avg_loss_bps)
    if w <= 0 or l <= 0:
        return 0.5
    # EV = p*w - (1-p)*l - fees > 0  =>  p > (l + fees) / (w + l)
    return max(0.0, min(1.0, (l + float(fees_bps)) / (w + l)))


def decide_admission(
    canonical_key: str,
    n_min_for_bank: int = N_MIN_FOR_BANK,
    fees_bps: float = 0.0,
    path: str | Path | None = None,
    mode: str = "wilson",
) -> dict[str, Any]:
    """Returns {decision, reason, posterior, break_even_winrate, global_rolling} where
    decision in {'admit_bank', 'admit_shadow', 'reject'}.

    Modes:
      - "wilson" (default, v1): per-canonical-key Wilson LB vs break-even.
      - "protective": Wilson is the bank-promotion authority; K-NN over structurally-
        similar keys escalates marginal admissions to reject when neighbors are losing.
        Wilson bank decisions are preserved unchanged. Validated by offline replay
        against the seed ledger (same +388 bank PnL as Wilson, drastically more rejects).

    Window-agnostic in either mode. Constants are economic (fees) or statistical (z).
    """
    if mode == "protective":
        # Lazy import — avoids a hard dep cycle if markets_evidence_knn is moved later
        from markets_evidence_knn import decide_admission_protective
        return decide_admission_protective(
            canonical_key=canonical_key,
            n_min_for_bank=n_min_for_bank,
            fees_bps=fees_bps,
            path=path,
        )

    post = posterior(canonical_key, path)
    global_ = global_rolling_payoff(path)
    break_even = break_even_winrate(
        global_.get("avg_win_bps", 0.0),
        global_.get("avg_loss_bps", 0.0),
        fees_bps,
    )
    n = post["n"]
    if n == 0:
        decision = "admit_shadow"
        reason = "cold_start_no_evidence"
    elif n < n_min_for_bank:
        decision = "admit_shadow"
        reason = f"insufficient_evidence_n_{n}_lt_{n_min_for_bank}"
    elif post["p_win_lb_90"] >= break_even:
        decision = "admit_bank"
        reason = f"wilson_lb90_{post['p_win_lb_90']:.3f}_ge_breakeven_{break_even:.3f}"
    elif post["p_win_mean"] >= break_even:
        decision = "admit_shadow"
        reason = f"mean_{post['p_win_mean']:.3f}_ge_breakeven_{break_even:.3f}_but_lb_below"
    else:
        decision = "reject"
        reason = f"mean_{post['p_win_mean']:.3f}_lt_breakeven_{break_even:.3f}"
    return {
        "decision": decision,
        "reason": reason,
        "posterior": post,
        "break_even_winrate": break_even,
        "global_rolling": global_,
    }
