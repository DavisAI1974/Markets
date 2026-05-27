"""Phase 2: promoted-context allowlist.

Layered on top of wilson + protective. When the entry gate says admit_shadow
AND the candidate's (asset, venue, side, session, family) matches a
high-conviction entry from research/strategy_evolution/_study_list.json,
upgrade the decision to admit_bank.

High-conviction = pnl_R >= MIN_PNL_R AND trades >= MIN_TRADES. The filter
excludes n=1 noise entries (like BTC|bybit|buy|first6h x mean_reversion_chop
with pnl_R=15.8 on 1 trade) so we only upgrade for contexts the live evolution
worker has actually validated with meaningful sample size.

Wilson's reject decisions are never overridden — this layer only upgrades
shadow -> bank, never reject -> anything. The defensive layer stays intact.

The study list is maintained by the live evolution worker (PID 76100); its
mtime drives a cached re-read so changes propagate without restart.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Path resolved at import time so the module is portable across runs.
STUDY_LIST_PATH = (
    Path(__file__).resolve().parent
    / "research" / "strategy_evolution" / "_study_list.json"
)

# Conviction filters — economic, not tape-tuned.
# pnl_R is in R-units (win/loss ratio); 100R = strong enough that small-sample noise
# is unlikely to drive it. 30 trades clears the n=20 marginal seeds.
# MAX_WR = 0.95 excludes "perfect" win-rate entries that are almost always small-sample artifacts
# (e.g. WR=1.00 on n=20 is unrealistic and historically produces losing live results).
MIN_PNL_R = 100.0
MIN_TRADES = 30
MAX_WR = 0.95

_ALLOWLIST_CACHE: dict[str, Any] = {"mtime_ns": 0, "by_key": None, "raw": None}


def _allowlist_key(asset: str, venue: str, side: str, session: str, family: str) -> str:
    """Canonical comparison key. study_list uses lowercase venue/family; trade
    dicts use various cases. Normalize to make match deterministic."""
    return (
        f"{asset.strip().upper()}|{venue.strip().lower()}|"
        f"{side.strip().lower()}|{session.strip().lower()}|"
        f"{family.strip().lower()}"
    )


def load_promoted_allowlist(
    min_pnl_r: float = MIN_PNL_R,
    min_trades: int = MIN_TRADES,
    max_wr: float = MAX_WR,
) -> dict[str, dict[str, Any]]:
    """Returns dict: normalized_key -> {context, family, pnl_R, trades, win_rate, fit_score}.

    Cached by file mtime so subsequent calls in the same process are O(1)
    unless the live worker updates the file.
    """
    try:
        stat = STUDY_LIST_PATH.stat()
    except OSError:
        return {}
    if (
        _ALLOWLIST_CACHE["mtime_ns"] == stat.st_mtime_ns
        and _ALLOWLIST_CACHE["by_key"] is not None
    ):
        return _ALLOWLIST_CACHE["by_key"]

    try:
        payload = json.loads(STUDY_LIST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    by_key: dict[str, dict[str, Any]] = {}
    for row in payload.get("promoted_contexts") or []:
        context = str(row.get("context") or "").strip()
        family = str(row.get("family") or "").strip()
        if not context or not family:
            continue
        pnl_r = float(row.get("pnl_R") or 0.0)
        trades = int(row.get("trades") or 0)
        wr = float(row.get("win_rate") or 0.0)
        # Three conviction gates: pnl_R floor, sample-size floor, WR ceiling.
        # WR > 0.95 on small n is almost always a small-sample artifact (e.g. WR=1.00 on n=20
        # in the v1 spot-check led to -$101 on 6 live trades).
        if pnl_r < min_pnl_r or trades < min_trades or wr > max_wr:
            continue
        parts = context.split("|")
        if len(parts) < 4:
            continue
        asset, venue, side, session = parts[0], parts[1], parts[2], parts[3]
        key = _allowlist_key(asset, venue, side, session, family)
        by_key[key] = {
            "context": context,
            "family": family,
            "pnl_R": pnl_r,
            "trades": trades,
            "win_rate": wr,
            "fit_score": float(row.get("fit_score") or 0.0),
        }

    _ALLOWLIST_CACHE["mtime_ns"] = stat.st_mtime_ns
    _ALLOWLIST_CACHE["by_key"] = by_key
    return by_key


def is_allowlisted(
    asset: str,
    venue: str,
    side: str,
    session: str,
    family: str,
) -> dict[str, Any] | None:
    """Returns the matching allowlist entry dict or None."""
    if not (asset and venue and side and session and family):
        return None
    return load_promoted_allowlist().get(
        _allowlist_key(asset, venue, side, session, family)
    )


def apply_allowlist_upgrade(
    decision: str,
    asset: str,
    venue: str,
    side: str,
    session: str,
    family: str,
) -> tuple[str, str | None, dict[str, Any] | None]:
    """V1 BEHAVIOR — kept for backwards compat. Upgrades admit_shadow -> admit_bank
    when allowlisted. Pre-layered (after protective). Spot-check showed this only
    fires on weak first6h seeds; strong remaining18h entries are demoted by
    protective before this layer runs. Use apply_allowlist_pre_protective for v2.
    """
    if decision != "admit_shadow":
        return decision, None, None
    entry = is_allowlisted(asset, venue, side, session, family)
    if entry is None:
        return decision, None, None
    reason = (
        f"allowlist_upgrade:context={entry['context']}_family={entry['family']}_"
        f"pnl_R={entry['pnl_R']:.1f}_n={entry['trades']}_wr={entry['win_rate']:.2f}"
    )
    return "admit_bank", reason, entry


def apply_allowlist_pre_protective(
    wilson_decision: str,
    asset: str,
    venue: str,
    side: str,
    session: str,
    family: str,
) -> tuple[str, str | None, dict[str, Any] | None]:
    """V2 BEHAVIOR — overrides BEFORE K-NN demote.

    The allowlist represents high-conviction positive-EV evidence from the live
    evolution worker. When a candidate matches a high-conviction context+family,
    we trust that signal over per-key cold-start (wilson admit_shadow) AND over
    K-NN identity-pooled negative evidence (protective demote).

    Semantics:
      - wilson admit_bank: keep (already at target)
      - wilson admit_shadow AND allowlisted: upgrade to admit_bank (bypasses K-NN demote)
      - wilson admit_shadow AND NOT allowlisted: stay shadow (protective will then
        possibly demote in its layer)
      - wilson reject: STAY REJECT — wilson rejected on n>=10 with bad self-evidence;
        that's strong per-key negative signal we don't override even if context-level
        evidence is positive.

    Returns (new_decision, upgrade_reason, allowlist_entry).
    """
    if wilson_decision == "admit_bank":
        return wilson_decision, None, None
    if wilson_decision == "reject":
        return wilson_decision, None, None
    # wilson_decision == admit_shadow
    entry = is_allowlisted(asset, venue, side, session, family)
    if entry is None:
        return wilson_decision, None, None
    reason = (
        f"allowlist_pre_protective:context={entry['context']}_family={entry['family']}_"
        f"pnl_R={entry['pnl_R']:.1f}_n={entry['trades']}_wr={entry['win_rate']:.2f}"
    )
    return "admit_bank", reason, entry


def allowlist_summary() -> dict[str, Any]:
    """One-shot summary of what's on the allowlist with current filter — useful
    for printing at backtest startup."""
    by_key = load_promoted_allowlist()
    return {
        "count": len(by_key),
        "min_pnl_r": MIN_PNL_R,
        "min_trades": MIN_TRADES,
        "entries": list(by_key.values()),
    }
