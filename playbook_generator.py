"""
playbook_generator.py — runtime playbook string composer.

Given an (asset, venue, regime) triple, returns the actionable text the
backend embeds in SignalEvent.playbook. It reads playbook_registry.json
(written by build_playbook_registry.py) and composes text based on the
actual recovered edge per (asset, venue, regime), not a hand-coded
theory.

Falls back to per-regime DEFAULT_PLAYBOOKS when the registry has no
qualifying entry — e.g. on first boot before any registry has been
built.

The composed text intentionally INCLUDES the sample size + r-value +
p-value so users see the small-sample caveat directly in the playbook
they read. The framing updates each time the registry is rebuilt; this
is by design — see HANDOFF_PHASE1_5_RESULTS.md "second pass" for why
we don't gate on n>=10.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Optional


# ---------------------------------------------------------------------------
# Default per-regime playbooks (fallback when registry has no qualifying
# entry for this asset/venue/regime). Plain language; no math jargon.
# ---------------------------------------------------------------------------

DEFAULT_PLAYBOOKS: dict[str, str] = {
    "EQUILIBRIUM_TWO_SIDED": "Healthy two-sided market. No edge. Sit out unless flow becomes extremely one-sided.",
    "WHALE_UP": "One big buyer dominating. Piggyback if early; get out of the way if late. Watch for the buyer's order to finish.",
    "WHALE_DOWN": "One big seller dominating. Piggyback short if early; sit out if late. Watch for capitulation bottom.",
    "HERD_UP": "FOMO / panic buy — many actors aligned on the buy side. Follow with tight stops; fade after overshoot.",
    "HERD_DOWN": "Panic sell / capitulation — many actors aligned on the sell side. Fade after the worst is over; do NOT catch the falling knife.",
    "WASH_PAIRED": "Wash-trade signature: paired self-trades, no real price discovery. Do not trade.",
    "DEPLETED": "Market is asleep (lunch / off-hours). Sit out — there's no flow to ride.",
    "UNKNOWN": "Pattern doesn't match a known regime. Skip until classifier resolves.",
}


# ---------------------------------------------------------------------------
# Registry loading — process-wide cache; reloads when the file mtime changes
# so a freshly-built registry takes effect without restarting the backend.
# ---------------------------------------------------------------------------

_REGISTRY_PATH_DEFAULT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "playbook_registry.json"
)
_registry_lock = threading.Lock()
_registry_cache: dict[str, dict] = {}
_registry_mtime: float = 0.0
_registry_path: str = _REGISTRY_PATH_DEFAULT


def set_registry_path(path: str):
    """Override the registry path. Useful for tests + non-default deploys."""
    global _registry_path, _registry_cache, _registry_mtime
    with _registry_lock:
        _registry_path = path
        _registry_cache = {}
        _registry_mtime = 0.0


def _load_registry_if_stale() -> dict[str, dict]:
    global _registry_cache, _registry_mtime
    if not os.path.exists(_registry_path):
        return {}
    with _registry_lock:
        try:
            mtime = os.path.getmtime(_registry_path)
        except OSError:
            return _registry_cache
        if mtime <= _registry_mtime and _registry_cache:
            return _registry_cache
        try:
            with open(_registry_path) as f:
                _registry_cache = json.load(f) or {}
            _registry_mtime = mtime
        except Exception as e:
            print(f"[playbook_generator] registry load error: {e}", flush=True)
        return _registry_cache


# ---------------------------------------------------------------------------
# Playbook composition
# ---------------------------------------------------------------------------


def _direction_text(regime: str, direction: str, r: Optional[float]) -> str:
    """Human-readable description of the recovered edge direction. Uses the
    regime's UP/DOWN suffix to correctly orient buyer-side vs seller-side
    language."""
    is_up = regime.endswith("_UP")
    is_down = regime.endswith("_DOWN")
    if direction == "momentum":
        if is_up:
            return ("the buyer's flow is continuing — recent moves keep "
                    "pushing up after similar setups")
        if is_down:
            return ("the seller's flow is continuing — recent moves keep "
                    "pushing down after similar setups")
        return "recent moves continue in the same direction after similar setups"
    if direction == "mean_revert":
        if is_up:
            return ("the move tends to fade — recent buying surges have "
                    "been followed by retracement")
        if is_down:
            return ("the move tends to fade — recent selling capitulations "
                    "have been followed by bounce")
        return "recent moves have been followed by retracement"
    if direction == "exploring":
        return ("no clean directional edge yet — the data so far is mixed "
                "for this regime on this venue")
    return ""


def _action_text(regime: str, direction: str) -> str:
    """Suggested action given the regime + recovered direction."""
    is_up = regime.endswith("_UP")
    is_down = regime.endswith("_DOWN")

    if direction == "momentum":
        if is_up:
            return ("Action: ride the trend with a tight stop. Exit on first "
                    "sign of buying exhaustion (volume drops, dipole flips). "
                    "Don't chase late.")
        if is_down:
            return ("Action: ride the move short with a tight stop. Exit on "
                    "first sign of selling exhaustion. Don't chase late.")
    if direction == "mean_revert":
        if is_up:
            return ("Action: fade the overextension OR sit out. If fading, "
                    "small size with a tight stop above the recent high. "
                    "Don't chase the move.")
        if is_down:
            return ("Action: wait for the worst, then fade with a tight stop "
                    "below the recent low. Don't catch the falling knife.")
    if direction == "exploring":
        return ("Action: skip — wait for more data before forming a view on "
                "this venue's edge for this regime.")
    return ""


def _caveat(stats: dict) -> str:
    """Inline note showing the sample state so users see the read's
    confidence directly in the playbook."""
    n = stats.get("n", 0)
    r = stats.get("r")
    p = stats.get("p")
    if r is None or p is None:
        return f"[n={n}; sample too small to claim direction yet]"
    flag = ""
    if n < 10:
        flag = " — small sample, expect this read to shift"
    elif n < 20:
        flag = " — sample still building"
    return f"[n={n}, r={r:+.2f}, p={p:.3f}{flag}]"


def get_playbook(asset: str, venue: str, regime: str) -> str:
    """Return the actionable playbook text for an emit.

    Lookup key is "<ASSET>/<VENUE>/<REGIME>". Falls back to
    DEFAULT_PLAYBOOKS[regime] when:
      - registry file doesn't exist
      - no entry for this triple
      - entry has fewer than 3 chunks (no statistical claim possible)
    """
    registry = _load_registry_if_stale()
    venue_short = "CB" if venue.lower().startswith("c") else (
        "KR" if venue.lower().startswith("k") else venue
    )
    key = f"{asset}/{venue_short}/{regime}"
    entry = registry.get(key)
    default = DEFAULT_PLAYBOOKS.get(regime, "(no playbook configured)")

    if entry is None:
        return default

    direction = entry.get("direction") or "exploring"
    if direction == "insufficient":
        # Too few samples to fit; show the default + sample-size note so
        # users still know we're tracking this cell.
        n = entry.get("n", 0)
        return f"{default}  [n={n} on {venue_short}-{asset}; need ≥3 to compute edge]"

    description = _direction_text(regime, direction, entry.get("r"))
    action = _action_text(regime, direction)
    caveat = _caveat(entry)
    base_label = DEFAULT_PLAYBOOKS.get(regime, "")
    # Lead with the regime context, then the recovered direction, action,
    # and caveat. Plain language end-to-end.
    composed = f"{base_label.split('.')[0]}. On {venue_short}-{asset}, {description}. {action} {caveat}"
    return composed


# ---------------------------------------------------------------------------
# CLI for inspection
# ---------------------------------------------------------------------------


def _main():
    import argparse
    p = argparse.ArgumentParser(
        description="Inspect what playbook would emit for given (asset, venue, regime).")
    p.add_argument("--asset", required=True)
    p.add_argument("--venue", required=True, help="full venue name e.g. Coinbase or Kraken")
    p.add_argument("--regime", required=True)
    p.add_argument("--registry-path", default=None)
    args = p.parse_args()
    if args.registry_path:
        set_registry_path(args.registry_path)
    print(get_playbook(args.asset, args.venue, args.regime))


if __name__ == "__main__":
    _main()
