"""K-nearest-neighbors evidence for admission, structurally indexed by canonical_trade_key.

Where v1 (oracle_winner_evidence) gives per-canonical-key Wilson lower bound, this gives
similarity-weighted Wilson lower bound over the K nearest historical keys by structural
overlap of canonical-key tail components, gated to the same identity (strategy/asset/side).
A key with N=3 inherits weighted evidence from its same-identity neighbors instead of
being stuck in cold-start.

Same return contract as oracle_winner_evidence.decide_admission so it can drop in.

Two structural constraints, no tuned parameters:
  1. Identity gate: neighbors must match on strategy + asset + side (positions 0,1,2 of
     canonical_trade_key). Without this, a winning chop key matches losing continuation
     keys via tail overlap — caught in cross-strategy spot check.
  2. Asymmetric use: K-NN is a reject ENHANCER, not a bank promoter. Wilson keeps
     authority over bank promotion. K-NN only escalates marginal Wilson admissions to
     reject when same-identity neighbors are clearly losing.

Window-agnostic constants (statistical, not tuned):
  - K = round(sqrt(unique_keys))    statistical heuristic
  - min_similarity = 0.5            >=50% of canonical-key components must overlap
  - n_min_for_bank = 10             same as v1
  - Wilson z = 1.6449 (90%)         same as v1
  - effective N = (sum w_i)^2 / sum(w_i^2)  kernel effective sample size
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import oracle_winner_evidence as owe


MIN_SIMILARITY_DEFAULT = 0.5

# Canonical key positions 0,1,2 = strategy, asset, side. These are *identity*
# components: a trade's strategy/asset/side determines what KIND of trade it is.
# K-NN should only consider neighbors within the same identity (otherwise a
# winning mean-reversion key gets matched to losing continuation keys via
# tail-position overlap). Tail positions are contextual modifiers.
IDENTITY_POSITIONS = (0, 1, 2)

_INDEX_CACHE: dict[str, Any] = {
    "ledger_mtime_ns": 0,
    "ledger_size": 0,
    "vocab": None,
    "vectors_by_key": None,
    "outcomes_by_key": None,
}


def _key_components(canonical_key: str) -> list[tuple[int, str]]:
    if not canonical_key:
        return []
    return [(i, part) for i, part in enumerate(canonical_key.split("|"))]


def _build_vocab(unique_keys: list[str]) -> dict[tuple[int, str], int]:
    vocab: dict[tuple[int, str], int] = {}
    for key in unique_keys:
        for pos, val in _key_components(key):
            if (pos, val) not in vocab:
                vocab[(pos, val)] = len(vocab)
    return vocab


def _key_vector(canonical_key: str, vocab: dict[tuple[int, str], int]) -> dict[int, float]:
    out: dict[int, float] = {}
    for pos, val in _key_components(canonical_key):
        idx = vocab.get((pos, val))
        if idx is not None:
            out[idx] = 1.0
    return out


def _cosine_sparse(a: dict[int, float], b: dict[int, float]) -> float:
    if not a or not b:
        return 0.0
    common = a.keys() & b.keys()
    if not common:
        return 0.0
    dot = sum(a[i] * b[i] for i in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def build_index_from_ledger(ledger_by_key: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Build (vocab, vectors_by_key, outcomes_by_key) from an in-memory ledger dict.

    Use this for offline replay where you control the ledger snapshot. Returns a
    fresh, uncached index — caller is responsible for reuse.
    """
    keys = list(ledger_by_key.keys())
    vocab = _build_vocab(keys)
    vectors_by_key = {k: _key_vector(k, vocab) for k in keys}
    outcomes_by_key: dict[str, list[float]] = {
        k: [float(r.get("net_bps") or 0.0) for r in rows]
        for k, rows in ledger_by_key.items()
    }
    return {"vocab": vocab, "vectors_by_key": vectors_by_key, "outcomes_by_key": outcomes_by_key}


def _ensure_index_from_disk(path: str | Path | None = None) -> dict[str, Any]:
    """Cached disk-backed index. Rebuilds on ledger mtime/size change."""
    p = owe._ledger_path(path)
    if not p.exists():
        return {"vocab": {}, "vectors_by_key": {}, "outcomes_by_key": {}}
    stat = p.stat()
    if (
        _INDEX_CACHE.get("ledger_mtime_ns") == stat.st_mtime_ns
        and _INDEX_CACHE.get("ledger_size") == stat.st_size
        and _INDEX_CACHE.get("vocab") is not None
    ):
        return {
            "vocab": _INDEX_CACHE["vocab"],
            "vectors_by_key": _INDEX_CACHE["vectors_by_key"],
            "outcomes_by_key": _INDEX_CACHE["outcomes_by_key"],
        }
    ledger = owe._load_ledger(path)
    idx = build_index_from_ledger(ledger)
    _INDEX_CACHE["ledger_mtime_ns"] = stat.st_mtime_ns
    _INDEX_CACHE["ledger_size"] = stat.st_size
    _INDEX_CACHE["vocab"] = idx["vocab"]
    _INDEX_CACHE["vectors_by_key"] = idx["vectors_by_key"]
    _INDEX_CACHE["outcomes_by_key"] = idx["outcomes_by_key"]
    return idx


def _identity_tuple(canonical_key: str) -> tuple[str, ...]:
    parts = canonical_key.split("|")
    return tuple(parts[i] if i < len(parts) else "" for i in IDENTITY_POSITIONS)


def neighbor_posterior(
    canonical_key: str,
    k: int | None = None,
    min_similarity: float = MIN_SIMILARITY_DEFAULT,
    path: str | Path | None = None,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """K-NN-weighted posterior for a candidate key.

    Returns:
        n_neighbor_keys     : how many keys passed the similarity threshold
        n_neighbor_trades   : total observations across those neighbor keys
        effective_n         : kernel-effective sample size (sum w)^2 / sum(w^2)
        wins_weighted       : sum(w * I[outcome>0])
        p_win_mean          : weighted mean (Hájek ratio)
        p_win_lb_90         : Wilson LB at 90% on (round(p*N_eff), round(N_eff))
        avg_win_bps         : weighted mean winning bps
        avg_loss_bps        : weighted mean losing bps
        top_neighbors       : up to 5 closest neighbor keys for debug
    """
    if index is None:
        index = _ensure_index_from_disk(path)
    vocab = index["vocab"]
    vectors_by_key = index["vectors_by_key"]
    outcomes_by_key = index["outcomes_by_key"]

    empty = {
        "n_neighbor_keys": 0,
        "n_neighbor_trades": 0,
        "effective_n": 0.0,
        "wins_weighted": 0.0,
        "p_win_mean": 0.0,
        "p_win_lb_90": 0.0,
        "avg_win_bps": 0.0,
        "avg_loss_bps": 0.0,
        "top_neighbors": [],
    }
    if not vocab or not vectors_by_key:
        return empty

    query_vec = _key_vector(canonical_key, vocab)
    if not query_vec:
        return empty

    query_identity = _identity_tuple(canonical_key)
    scored: list[tuple[float, str]] = []
    for k2, vec in vectors_by_key.items():
        # Identity gate: only consider neighbors with same strategy/asset/side.
        # Without this, a winning chop key can match losing continuation keys via
        # tail-position overlap (the MEAN_REVERSION_CHOP regression seen in the
        # cross-strategy spot check).
        if _identity_tuple(k2) != query_identity:
            continue
        sim = _cosine_sparse(query_vec, vec)
        if sim >= min_similarity:
            scored.append((sim, k2))
    scored.sort(reverse=True)

    if k is None:
        k = max(5, round(math.sqrt(len(vectors_by_key))))
    top = scored[:k]

    if not top:
        return empty

    sum_w = 0.0
    sum_w_sq = 0.0
    sum_w_wins = 0.0
    sum_w_n = 0.0
    sum_w_win_bps = 0.0
    sum_w_loss_bps = 0.0
    sum_w_win_count = 0.0
    sum_w_loss_count = 0.0
    n_trades = 0

    for sim, k2 in top:
        outcomes = outcomes_by_key.get(k2, [])
        if not outcomes:
            continue
        for o in outcomes:
            n_trades += 1
            sum_w += sim
            sum_w_sq += sim * sim
            sum_w_n += sim
            if o > 0:
                sum_w_wins += sim
                sum_w_win_bps += sim * o
                sum_w_win_count += sim
            else:
                sum_w_loss_bps += sim * abs(o)
                sum_w_loss_count += sim

    if sum_w == 0:
        return empty

    p_mean = sum_w_wins / sum_w_n if sum_w_n > 0 else 0.0
    # Kernel effective sample size — accounts for weight concentration
    eff_n_float = (sum_w * sum_w) / sum_w_sq if sum_w_sq > 0 else 0.0
    eff_n = int(round(eff_n_float))
    eff_wins = int(round(p_mean * eff_n_float))
    p_lb = owe._wilson_lb(eff_wins, eff_n, owe.WILSON_Z_90)

    return {
        "n_neighbor_keys": len(top),
        "n_neighbor_trades": n_trades,
        "effective_n": eff_n,
        "wins_weighted": eff_wins,
        "p_win_mean": p_mean,
        "p_win_lb_90": p_lb,
        "avg_win_bps": (sum_w_win_bps / sum_w_win_count) if sum_w_win_count > 0 else 0.0,
        "avg_loss_bps": (sum_w_loss_bps / sum_w_loss_count) if sum_w_loss_count > 0 else 0.0,
        "top_neighbors": [(round(sim, 3), k2) for sim, k2 in top[:5]],
    }


def decide_admission_knn(
    canonical_key: str,
    n_min_for_bank: int = owe.N_MIN_FOR_BANK,
    fees_bps: float = 0.0,
    path: str | Path | None = None,
    index: dict[str, Any] | None = None,
    ledger_snapshot: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """K-NN-weighted admission. Same return contract as oracle_winner_evidence.decide_admission.

    `index` and `ledger_snapshot` are for offline replay — pass them to score against an
    in-memory ledger snapshot without touching disk.
    """
    post = neighbor_posterior(canonical_key, path=path, index=index)

    # Break-even uses the same global rolling payoff. If ledger_snapshot provided,
    # compute it from that; otherwise pull from disk.
    if ledger_snapshot is not None:
        rows = [r for k_rows in ledger_snapshot.values() for r in k_rows]
        rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
        recent = rows[:500]
        wins = [float(r["net_bps"]) for r in recent if float(r.get("net_bps") or 0.0) > 0]
        losses = [abs(float(r["net_bps"])) for r in recent if float(r.get("net_bps") or 0.0) <= 0]
        global_ = {
            "n": len(recent),
            "avg_win_bps": (sum(wins) / len(wins)) if wins else 0.0,
            "avg_loss_bps": (sum(losses) / len(losses)) if losses else 0.0,
        }
    else:
        global_ = owe.global_rolling_payoff(path)

    break_even = owe.break_even_winrate(
        global_.get("avg_win_bps", 0.0),
        global_.get("avg_loss_bps", 0.0),
        fees_bps,
    )
    eff_n = post["effective_n"]
    if eff_n == 0:
        decision = "admit_shadow"
        reason = "knn_no_neighbors"
    elif eff_n < n_min_for_bank:
        decision = "admit_shadow"
        reason = f"knn_eff_n_{eff_n}_lt_{n_min_for_bank}"
    elif post["p_win_lb_90"] >= break_even:
        decision = "admit_bank"
        reason = f"knn_lb90_{post['p_win_lb_90']:.3f}_ge_be_{break_even:.3f}_neighbors_{post['n_neighbor_keys']}"
    elif post["p_win_mean"] >= break_even:
        decision = "admit_shadow"
        reason = f"knn_mean_{post['p_win_mean']:.3f}_ge_be_{break_even:.3f}_lb_below"
    else:
        decision = "reject"
        reason = f"knn_mean_{post['p_win_mean']:.3f}_lt_be_{break_even:.3f}"

    return {
        "decision": decision,
        "reason": reason,
        "posterior": post,
        "break_even_winrate": break_even,
        "global_rolling": global_,
    }


def decide_admission_protective(
    canonical_key: str,
    n_min_for_bank: int = owe.N_MIN_FOR_BANK,
    fees_bps: float = 0.0,
    path: str | Path | None = None,
    index: dict[str, Any] | None = None,
    ledger_snapshot: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Wilson is the bank-promotion authority; K-NN is the rejection enhancer.

    Empirical finding from offline replay: K-NN bank-promotion is overconfident because
    canonical-key components are structurally correlated (neighbors are often near-duplicate
    keys, not independent draws), so kernel-effective N overstates real information.
    But K-NN reject signal is sharp — when neighbors are clearly losing, the candidate
    almost always loses too.

    Logic:
      1. Run Wilson decision (current production behavior).
      2. If Wilson says admit_bank or admit_shadow, check K-NN:
         - If K-NN has enough effective N AND K-NN LB < break_even → override to reject.
         - Otherwise honor Wilson.
      3. If Wilson says reject, stay reject. (Don't let K-NN promote rejects.)

    Net effect: same or fewer admit_bank than Wilson, more reject, more avoided losses.
    """
    if ledger_snapshot is not None:
        rows = ledger_snapshot.get(canonical_key, [])
        n = len(rows)
        wins = sum(1 for r in rows if float(r.get("net_bps") or 0.0) > 0)
        win_bps = [float(r["net_bps"]) for r in rows if float(r.get("net_bps") or 0.0) > 0]
        loss_bps = [abs(float(r["net_bps"])) for r in rows if float(r.get("net_bps") or 0.0) <= 0]
        wilson_post = {
            "n": n,
            "wins": wins,
            "losses": n - wins,
            "p_win_mean": wins / n if n else 0.0,
            "p_win_lb_90": owe._wilson_lb(wins, n, owe.WILSON_Z_90),
            "p_win_lb_95": owe._wilson_lb(wins, n, owe.WILSON_Z_95),
            "avg_win_bps": (sum(win_bps) / len(win_bps)) if win_bps else 0.0,
            "avg_loss_bps": (sum(loss_bps) / len(loss_bps)) if loss_bps else 0.0,
            "last_ts": max((float(r.get("ts") or 0.0) for r in rows), default=0.0),
        }
        all_rows = [r for k_rows in ledger_snapshot.values() for r in k_rows]
        all_rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
        recent = all_rows[:500]
        w = [float(r["net_bps"]) for r in recent if float(r.get("net_bps") or 0.0) > 0]
        l = [abs(float(r["net_bps"])) for r in recent if float(r.get("net_bps") or 0.0) <= 0]
        global_ = {
            "n": len(recent),
            "avg_win_bps": (sum(w) / len(w)) if w else 0.0,
            "avg_loss_bps": (sum(l) / len(l)) if l else 0.0,
        }
    else:
        wilson_post = owe.posterior(canonical_key, path)
        global_ = owe.global_rolling_payoff(path)

    break_even = owe.break_even_winrate(
        global_.get("avg_win_bps", 0.0),
        global_.get("avg_loss_bps", 0.0),
        fees_bps,
    )

    # Wilson decision first
    self_n = wilson_post["n"]
    if self_n == 0:
        wilson_decision = "admit_shadow"
        wilson_reason = "cold_start_no_evidence"
    elif self_n < n_min_for_bank:
        wilson_decision = "admit_shadow"
        wilson_reason = f"self_n_{self_n}_lt_{n_min_for_bank}"
    elif wilson_post["p_win_lb_90"] >= break_even:
        wilson_decision = "admit_bank"
        wilson_reason = f"wilson_lb90_{wilson_post['p_win_lb_90']:.3f}_ge_be_{break_even:.3f}"
    elif wilson_post["p_win_mean"] >= break_even:
        wilson_decision = "admit_shadow"
        wilson_reason = f"wilson_mean_{wilson_post['p_win_mean']:.3f}_ge_be_{break_even:.3f}_lb_below"
    else:
        wilson_decision = "reject"
        wilson_reason = f"wilson_mean_{wilson_post['p_win_mean']:.3f}_lt_be_{break_even:.3f}"

    # If Wilson already rejected, we're done. Don't second-guess strong negative self-evidence.
    if wilson_decision == "reject":
        return {
            "decision": "reject",
            "reason": f"wilson:{wilson_reason}",
            "posterior": wilson_post,
            "break_even_winrate": break_even,
            "global_rolling": global_,
        }

    # Wilson said bank or shadow — let K-NN argue for reject if it has strong negative signal
    knn_post = neighbor_posterior(canonical_key, path=path, index=index)
    knn_eff_n = knn_post["effective_n"]
    knn_lb = knn_post["p_win_lb_90"]
    knn_mean = knn_post["p_win_mean"]

    if knn_eff_n >= n_min_for_bank and knn_mean < break_even and knn_lb < break_even:
        return {
            "decision": "reject",
            "reason": (
                f"knn_override:knn_mean_{knn_mean:.3f}_lt_be_{break_even:.3f}_"
                f"eff_n_{knn_eff_n}_neighbors_{knn_post['n_neighbor_keys']}"
            ),
            "posterior": {**wilson_post, "knn_posterior": knn_post},
            "break_even_winrate": break_even,
            "global_rolling": global_,
        }

    # Honor Wilson
    return {
        "decision": wilson_decision,
        "reason": f"wilson:{wilson_reason}",
        "posterior": {**wilson_post, "knn_posterior": knn_post},
        "break_even_winrate": break_even,
        "global_rolling": global_,
    }


def decide_admission_hybrid(
    canonical_key: str,
    n_min_for_bank: int = owe.N_MIN_FOR_BANK,
    fees_bps: float = 0.0,
    path: str | Path | None = None,
    index: dict[str, Any] | None = None,
    ledger_snapshot: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Hybrid: per-key Wilson when key has its own n >= n_min_for_bank, else K-NN.

    Kept for replay comparison. Empirically inferior to `decide_admission_protective`
    because K-NN over-admits to bank on sparse-self-evidence keys.
    """
    if ledger_snapshot is not None:
        rows = ledger_snapshot.get(canonical_key, [])
        n_self = len(rows)
    else:
        post_self = owe.posterior(canonical_key, path)
        n_self = post_self["n"]

    if n_self >= n_min_for_bank:
        if ledger_snapshot is not None:
            # Compute self-posterior + break_even from snapshot
            rows = ledger_snapshot.get(canonical_key, [])
            n = len(rows)
            wins = sum(1 for r in rows if float(r.get("net_bps") or 0.0) > 0)
            win_bps = [float(r["net_bps"]) for r in rows if float(r.get("net_bps") or 0.0) > 0]
            loss_bps = [abs(float(r["net_bps"])) for r in rows if float(r.get("net_bps") or 0.0) <= 0]
            post = {
                "n": n,
                "wins": wins,
                "losses": n - wins,
                "p_win_mean": wins / n if n else 0.0,
                "p_win_lb_90": owe._wilson_lb(wins, n, owe.WILSON_Z_90),
                "p_win_lb_95": owe._wilson_lb(wins, n, owe.WILSON_Z_95),
                "avg_win_bps": (sum(win_bps) / len(win_bps)) if win_bps else 0.0,
                "avg_loss_bps": (sum(loss_bps) / len(loss_bps)) if loss_bps else 0.0,
                "last_ts": max((float(r.get("ts") or 0.0) for r in rows), default=0.0),
            }
            all_rows = [r for k_rows in ledger_snapshot.values() for r in k_rows]
            all_rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
            recent = all_rows[:500]
            w = [float(r["net_bps"]) for r in recent if float(r.get("net_bps") or 0.0) > 0]
            l = [abs(float(r["net_bps"])) for r in recent if float(r.get("net_bps") or 0.0) <= 0]
            global_ = {
                "n": len(recent),
                "avg_win_bps": (sum(w) / len(w)) if w else 0.0,
                "avg_loss_bps": (sum(l) / len(l)) if l else 0.0,
            }
        else:
            post = owe.posterior(canonical_key, path)
            global_ = owe.global_rolling_payoff(path)

        break_even = owe.break_even_winrate(
            global_.get("avg_win_bps", 0.0),
            global_.get("avg_loss_bps", 0.0),
            fees_bps,
        )
        if post["p_win_lb_90"] >= break_even:
            decision = "admit_bank"
            reason = f"wilson_lb90_{post['p_win_lb_90']:.3f}_ge_be_{break_even:.3f}_self_n_{n_self}"
        elif post["p_win_mean"] >= break_even:
            decision = "admit_shadow"
            reason = f"wilson_mean_{post['p_win_mean']:.3f}_ge_be_{break_even:.3f}_lb_below"
        else:
            decision = "reject"
            reason = f"wilson_mean_{post['p_win_mean']:.3f}_lt_be_{break_even:.3f}"
        return {
            "decision": decision,
            "reason": reason,
            "posterior": post,
            "break_even_winrate": break_even,
            "global_rolling": global_,
        }

    # Sparse self-evidence — fall back to K-NN
    return decide_admission_knn(
        canonical_key,
        n_min_for_bank=n_min_for_bank,
        fees_bps=fees_bps,
        path=path,
        index=index,
        ledger_snapshot=ledger_snapshot,
    )
