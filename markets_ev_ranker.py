"""EV-ranker: offensive admission layer on top of protective.

Goal (Greg's redirect, 2026-05-23): wilson + protective stop the bleed; this
module identifies and admits best trades for positive PnL. Defensive-only is
rejected. Best output, not break-even.

Layering:
    candidate -> protective (wilson + K-NN demote)
              -> ev_ranker (this module)
                  if protective said reject/admit_bank: pass through unchanged
                  if protective said admit_shadow AND self_n >= n_min AND
                     per-identity EV_LB >= meaningful_floor_bps:
                         promote to admit_bank
                  otherwise: pass through (admit_shadow stays shadow)

EV calculation:
    EV_LB = p_win_lb_90 * avg_win_bps  -  (1 - p_win_lb_90) * avg_loss_bps  -  fees_bps

    p_win_lb_90        = Wilson lower bound on the candidate's own canonical_key
    avg_win_bps        = mean of positive net_bps over same-identity ledger entries
    avg_loss_bps       = mean of |net_bps| over same-identity negative ledger entries
    fees_bps           = 0 by default (net_bps in the ledger is already fee-inclusive)

Identity gate is the structural protection: avg_win / avg_loss come ONLY from
trades sharing (strategy, asset, side). Pooling across identities mis-prices
strategies with very different (avg_win, avg_loss) geometry.

When per-identity has fewer than IDENTITY_MIN_FOR_PAYOFF rows, falls back to
global rolling payoff (same source as wilson break-even). This is the cold-start
fallback for identity stats, not for self-evidence.

Constants are economic (round-trip fees) or statistical (Wilson z, n_min).
Nothing is tuned to a particular backtest tape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import oracle_winner_evidence as owe
from markets_evidence_knn import IDENTITY_POSITIONS, _identity_tuple, neighbor_posterior


# Identity is (strategy, asset, side) — positions 0, 1, 2 of canonical_trade_key.
# Same gate as markets_evidence_knn — re-imported for explicitness.

# Minimum same-identity ledger rows before per-identity payoff is trustworthy.
# Below this, fall back to global rolling payoff.
IDENTITY_MIN_FOR_PAYOFF = 20

# EV floor for promoting admit_shadow -> admit_bank.
# Set at ~1x typical round-trip fees: a trade with EV_LB below the fee cost
# can't be expected to clear costs in expectation. This is economic, not tuned.
# Autoresearch sweeps this knob; this default is the floor a new operator inherits.
DEFAULT_MEANINGFUL_FLOOR_BPS = owe.DEFAULT_FEES_BPS_ROUNDTRIP  # 10.0


def per_identity_payoff(
    canonical_key: str,
    path: str | Path | None = None,
    ledger_snapshot: dict[str, list[dict[str, Any]]] | None = None,
    identity_min: int = IDENTITY_MIN_FOR_PAYOFF,
) -> dict[str, Any]:
    """avg_win_bps and avg_loss_bps over ledger entries matching (strategy, asset, side).

    Falls back to global rolling payoff when same-identity has < identity_min rows.
    """
    target_identity = _identity_tuple(canonical_key)

    if ledger_snapshot is not None:
        rows: list[dict[str, Any]] = []
        for k, k_rows in ledger_snapshot.items():
            if _identity_tuple(k) == target_identity:
                rows.extend(k_rows)
    else:
        by_key = owe._load_ledger(path)
        rows = []
        for k, k_rows in by_key.items():
            if _identity_tuple(k) == target_identity:
                rows.extend(k_rows)

    if len(rows) >= identity_min:
        wins = [float(r["net_bps"]) for r in rows if float(r.get("net_bps") or 0.0) > 0]
        losses = [abs(float(r["net_bps"])) for r in rows if float(r.get("net_bps") or 0.0) <= 0]
        return {
            "n": len(rows),
            "n_wins": len(wins),
            "n_losses": len(losses),
            "avg_win_bps": (sum(wins) / len(wins)) if wins else 0.0,
            "avg_loss_bps": (sum(losses) / len(losses)) if losses else 0.0,
            "source": "identity",
            "identity": target_identity,
        }

    # Fallback to global rolling
    if ledger_snapshot is not None:
        all_rows = [r for k_rows in ledger_snapshot.values() for r in k_rows]
        all_rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
        recent = all_rows[:500]
        wins = [float(r["net_bps"]) for r in recent if float(r.get("net_bps") or 0.0) > 0]
        losses = [abs(float(r["net_bps"])) for r in recent if float(r.get("net_bps") or 0.0) <= 0]
        return {
            "n": len(recent),
            "n_wins": len(wins),
            "n_losses": len(losses),
            "avg_win_bps": (sum(wins) / len(wins)) if wins else 0.0,
            "avg_loss_bps": (sum(losses) / len(losses)) if losses else 0.0,
            "source": "global_fallback",
            "identity": target_identity,
        }

    global_ = owe.global_rolling_payoff(path)
    return {
        "n": global_["n"],
        "n_wins": -1,  # unavailable from global_rolling_payoff
        "n_losses": -1,
        "avg_win_bps": global_["avg_win_bps"],
        "avg_loss_bps": global_["avg_loss_bps"],
        "source": "global_fallback",
        "identity": target_identity,
    }


def expected_value_bps(
    p_win: float,
    avg_win_bps: float,
    avg_loss_bps: float,
    fees_bps: float = 0.0,
) -> float:
    """EV per trade in bps: p*win - (1-p)*loss - fees. Inputs already-net-of-fees by default."""
    return p_win * avg_win_bps - (1.0 - p_win) * avg_loss_bps - fees_bps


def decide_admission_ev_ranker(
    canonical_key: str,
    n_min_for_bank: int = owe.N_MIN_FOR_BANK,
    fees_bps: float = 0.0,
    meaningful_floor_bps: float = DEFAULT_MEANINGFUL_FLOOR_BPS,
    path: str | Path | None = None,
    index: dict[str, Any] | None = None,
    ledger_snapshot: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Protective + EV-ranker promotion of admit_shadow -> admit_bank.

    Promotion rule:
      - protective said admit_shadow (i.e., wilson didn't reject and K-NN didn't demote)
      - self_n >= n_min_for_bank (enough self-evidence for a trustworthy Wilson LB)
      - per-identity EV_LB >= meaningful_floor_bps (positive EV with margin)

    Wilson rejects and wilson admit_bank pass through protective and through this
    function unchanged. The only path this opens is shadow -> bank.
    """
    # Lazy import to avoid a hard dep cycle.
    from markets_evidence_knn import decide_admission_protective

    p_result = decide_admission_protective(
        canonical_key=canonical_key,
        n_min_for_bank=n_min_for_bank,
        fees_bps=fees_bps,
        path=path,
        index=index,
        ledger_snapshot=ledger_snapshot,
    )

    # Pass through reject / bank.
    if p_result["decision"] != "admit_shadow":
        p_result["ev_ranker"] = None
        return p_result

    self_n = p_result["posterior"].get("n", 0)
    payoff = per_identity_payoff(
        canonical_key,
        path=path,
        ledger_snapshot=ledger_snapshot,
    )

    # Choose which p_win_lb to use:
    #   - self LB when we have enough self-evidence
    #   - identity LB when self is cold-start but identity has rich history
    #   - skip when both are too thin
    if self_n >= n_min_for_bank:
        p_win_lb = float(p_result["posterior"].get("p_win_lb_90") or 0.0)
        p_win_mean = float(p_result["posterior"].get("p_win_mean") or 0.0)
        p_source = "self"
    elif payoff["source"] == "identity" and payoff.get("n_wins", -1) >= 0:
        identity_n = payoff["n"]
        identity_wins = payoff["n_wins"]
        p_win_lb = owe._wilson_lb(identity_wins, identity_n, owe.WILSON_Z_90)
        p_win_mean = identity_wins / identity_n if identity_n else 0.0
        p_source = "identity"
    else:
        p_result["ev_ranker"] = {
            "skipped": f"self_n_{self_n}_lt_{n_min_for_bank}_and_identity_thin",
        }
        return p_result

    ev_lb = expected_value_bps(p_win_lb, payoff["avg_win_bps"], payoff["avg_loss_bps"], fees_bps)
    ev_mean = expected_value_bps(p_win_mean, payoff["avg_win_bps"], payoff["avg_loss_bps"], fees_bps)

    if ev_lb >= meaningful_floor_bps:
        return {
            "decision": "admit_bank",
            "reason": (
                f"ev_promote:ev_lb_{ev_lb:+.2f}bps_ge_floor_{meaningful_floor_bps:.2f}bps_"
                f"p_lb_{p_win_lb:.3f}_w{payoff['avg_win_bps']:.1f}_l{payoff['avg_loss_bps']:.1f}_"
                f"p_src_{p_source}_payoff_src_{payoff['source']}_n{payoff['n']}"
            ),
            "posterior": p_result["posterior"],
            "break_even_winrate": p_result.get("break_even_winrate"),
            "global_rolling": p_result.get("global_rolling"),
            "ev_ranker": {
                "ev_mean_bps": ev_mean,
                "ev_lb_bps": ev_lb,
                "meaningful_floor_bps": meaningful_floor_bps,
                "p_source": p_source,
                "payoff": payoff,
                "promoted": True,
            },
        }

    # Not enough EV margin — honor protective's admit_shadow.
    p_result["ev_ranker"] = {
        "ev_mean_bps": ev_mean,
        "ev_lb_bps": ev_lb,
        "meaningful_floor_bps": meaningful_floor_bps,
        "p_source": p_source,
        "payoff": payoff,
        "promoted": False,
    }
    return p_result
