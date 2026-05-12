"""
signal_allocator.py — cohort-based signal distribution with fairness tracking.

Solves the alpha-decay-through-crowding problem: when N subscribers all act on
the same signal simultaneously, thin order books get consumed and the realized
edge degrades. Solution: rotate which subscribers receive each occurrence so
the subscriber base never acts as one cohort on a capacity-limited cell.

Public API:
    select_cohort(cell_id, capacity_class, tier, all_endpoints) -> list[str]
        Pure function. Returns the subset of endpoints that should receive
        this signal occurrence.
    record_allocation(cell_id, tier, endpoints) -> None
        Updates the persisted fairness ledger so the next call to
        select_cohort prefers subscribers who got less this round.

Design choices:
- Deterministic selection ordered by (fairness_score, last_alloc_ts,
  registered_ts). No randomness; reproducible.
- Fairness score = sum of tier weights of recently-received signals.
  Tier-1 weighted 3x tier-2 — high-conviction signals "cost" more
  fairness budget.
- "Recently" = configurable lookback (default 7 days). Older allocations
  decay so subscribers who joined long ago don't get unfair priority forever.
- Capacity classes: tiny=5, small=20, medium=50, large=∞ (broadcast),
  huge=∞ (broadcast; informational rather than tradeable).
- Ledger persisted as JSONL append-only at FAIRNESS_PATH; one line per
  allocation event for full audit.

Capacity tradeoffs:
- TINY (5)     thin venues + fade signals. KR-ETH WHALE_UP fade is the
               canonical example. Five simultaneous fills can saturate
               KR's typical depth at $1000 notional each.
- SMALL (20)   standard KR/BB cells where edge is modest and depth is
               somewhat thicker. Most directional cells live here.
- MEDIUM (50)  CB cells with deeper books, MM-passive cells whose
               capacity is bounded by spread-capture rather than depth.
- LARGE        broadcast — book is deep enough that subscriber action
               can't move the cell out of edge.
- HUGE         informational / macro alerts (regime flips, vol spikes).
               No trade implied; broadcast freely.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict, field
from typing import Iterable

# Capacity class → cohort size cap. "large" / "huge" are sentinel values
# meaning "broadcast to everyone" — no rotation.
CAPACITY_COHORT_SIZE: dict[str, int] = {
    "tiny": 5,
    "small": 20,
    "medium": 50,
    "large": 10**9,  # effectively broadcast
    "huge": 10**9,
}

# Tier weights for fairness scoring. Receiving a higher-tier signal "costs"
# the subscriber more of their fairness budget; they get fewer total
# signals over a fixed window but more high-conviction ones.
#
# Pass-18 extension: the 5-tier markets_tier_search outputs (tier_1..tier_5)
# slot in alongside the legacy "high_conviction" / "alertable" labels. Legacy
# entries in the JSONL ledger continue to score via these existing weights;
# new tier-search-emitted entries score via the tier_N weights.
TIER_WEIGHTS: dict[str, float] = {
    # Legacy labels (Pass-1..17 cells)
    "high_conviction": 3.0,
    "alertable": 1.0,
    # 5-tier markets_tier_search labels (Pass-18+)
    "tier_1": 5.0,   # 0.95-threshold: ~exceptional, costs most fairness budget
    "tier_2": 3.0,   # 0.85: strong (parity with legacy high_conviction)
    "tier_3": 2.0,   # 0.75: moderate
    "tier_4": 1.5,   # 0.65: modest
    "tier_5": 1.0,   # 0.55: parity with legacy alertable
}

# Tier ranking (highest -> lowest). Used by risk-profile filtering to test
# whether a subscriber accepts signals at a given tier level. Adding new
# tiers between the existing five is OK -- insertion order = rank order.
TIER_RANK_ORDER: list[str] = ["tier_1", "tier_2", "tier_3", "tier_4", "tier_5"]


def _tier_rank_idx(tier: str) -> int:
    """Return position in TIER_RANK_ORDER, or len(TIER_RANK_ORDER) for unknown.
    Lower index = higher quality tier."""
    try:
        return TIER_RANK_ORDER.index(tier)
    except ValueError:
        return len(TIER_RANK_ORDER)


@dataclass
class SubscriberProfile:
    """Per-subscriber risk profile. Lets subscribers pick which tier levels
    they want to receive and at what sizing.

    min_tier: tier-name threshold. The subscriber accepts signals at this
              tier and ALL HIGHER tiers (lower rank index). Default "tier_5"
              means accept everything. Set "tier_1" for the most conservative
              ("only show me near-certainty signals").

    notional_multiplier_per_tier: optional finer-grained sizing dial. If
              tier "tier_3" maps to 0.4 here, this subscriber's notional for
              tier_3 cells is base_notional * 0.4. Missing keys default to
              1.0 (use the cell's published notional verbatim).

    A subscriber with min_tier="tier_5" and an empty multiplier dict trades
    every tier at the cell's published notional -- the maximal-coverage,
    maximal-size profile. A subscriber with min_tier="tier_2" and multipliers
    {"tier_1": 1.0, "tier_2": 0.5} sees only tier_1+tier_2 and sizes tier_2
    at half. Tier-3..5 cells never reach them."""
    endpoint: str
    min_tier: str = "tier_5"
    notional_multiplier_per_tier: dict[str, float] = field(default_factory=dict)


def filter_endpoints_by_risk_profile(
    endpoints: list[str],
    tier: str,
    risk_profiles: dict[str, "SubscriberProfile"] | None,
) -> list[str]:
    """Filter endpoints down to those whose profile accepts THIS tier.
    Endpoints without a registered profile default to "accept everything"
    (backward compatibility with pre-Pass-18 subscribers)."""
    if not risk_profiles:
        return list(endpoints)
    current_rank = _tier_rank_idx(tier)
    out: list[str] = []
    for ep in endpoints:
        prof = risk_profiles.get(ep)
        if prof is None:
            out.append(ep)
            continue
        min_rank = _tier_rank_idx(prof.min_tier)
        # current_rank <= min_rank means current tier is at-or-above the
        # subscriber's floor (tier_1 = rank 0 is above tier_3 = rank 2).
        if current_rank <= min_rank:
            out.append(ep)
    return out


def notional_for_endpoint(
    endpoint: str,
    tier: str,
    base_notional: float,
    risk_profiles: dict[str, "SubscriberProfile"] | None,
) -> float:
    """Return the per-endpoint notional after applying the subscriber's
    per-tier multiplier. Falls back to base_notional if no profile or no
    tier-specific multiplier registered."""
    if not risk_profiles or endpoint not in risk_profiles:
        return base_notional
    prof = risk_profiles[endpoint]
    mult = prof.notional_multiplier_per_tier.get(tier, 1.0)
    return base_notional * float(mult)

# Fairness lookback: only allocations within this many seconds count
# toward the fairness score. Older allocations decay (don't bias the
# rotation forever).
DEFAULT_FAIRNESS_WINDOW_SEC = 7 * 24 * 3600  # 7 days


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

FAIRNESS_PATH = os.environ.get(
    "MARKETS_WATCH_FAIRNESS_LOG",
    os.path.join(os.path.dirname(__file__), "..", "signal_allocations.jsonl"),
)


@dataclass
class AllocationEvent:
    """One allocation: a cell fired and this subset of endpoints was chosen.
    Append-only log; the in-memory fairness state is derived by replaying."""
    cell_id: str
    tier: str             # "high_conviction" | "alertable"
    endpoints: list[str]  # the cohort selected for this occurrence
    ts_utc: float = 0.0


def _append_allocation(event: AllocationEvent) -> None:
    """Append-only persistence. Robust to concurrent writes via file lock?
    No — single-writer assumed (the api_server is the only emitter).
    """
    line = json.dumps(asdict(event))
    # Use append-mode write; cheaper than tmp+rename and we don't need
    # atomic-replace semantics for an append-only log.
    with open(FAIRNESS_PATH, "a") as f:
        f.write(line + "\n")


def _load_allocations(since_ts: float | None = None) -> list[AllocationEvent]:
    """Replay the allocation log. If since_ts is supplied, skip events
    older than that. Robust to missing file."""
    if not os.path.exists(FAIRNESS_PATH):
        return []
    out: list[AllocationEvent] = []
    try:
        with open(FAIRNESS_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    # Tolerate occasional bad lines (mid-write crash, etc.)
                    continue
                ts = float(d.get("ts_utc") or 0.0)
                if since_ts is not None and ts < since_ts:
                    continue
                out.append(AllocationEvent(
                    cell_id=str(d.get("cell_id", "")),
                    tier=str(d.get("tier", "")),
                    endpoints=list(d.get("endpoints", [])),
                    ts_utc=ts,
                ))
    except Exception as e:
        # Log to stderr but don't crash — caller can proceed with empty state
        print(f"[signal_allocator] could not load fairness log: {e}",
              flush=True)
    return out


# ---------------------------------------------------------------------------
# Fairness state derivation
# ---------------------------------------------------------------------------

@dataclass
class EndpointFairness:
    """Per-endpoint state derived from the allocation log."""
    endpoint: str
    weighted_count: float = 0.0   # sum of tier_weights of recent allocations
    raw_count: int = 0            # total allocations within window
    last_alloc_ts: float = 0.0    # most-recent allocation timestamp


def _compute_fairness_state(
    endpoints: Iterable[str],
    window_sec: float = DEFAULT_FAIRNESS_WINDOW_SEC,
    now_ts: float | None = None,
) -> dict[str, EndpointFairness]:
    """Replay the allocation log over the lookback window; return per-
    endpoint fairness state. Endpoints with zero allocations get
    weighted_count=0 (highest priority for the next cohort)."""
    if now_ts is None:
        now_ts = time.time()
    cutoff = now_ts - window_sec
    state: dict[str, EndpointFairness] = {
        e: EndpointFairness(endpoint=e) for e in endpoints
    }
    for event in _load_allocations(since_ts=cutoff):
        w = TIER_WEIGHTS.get(event.tier, 1.0)
        for ep in event.endpoints:
            if ep not in state:
                continue   # subscriber unsubscribed or replaced their endpoint
            f = state[ep]
            f.weighted_count += w
            f.raw_count += 1
            if event.ts_utc > f.last_alloc_ts:
                f.last_alloc_ts = event.ts_utc
    return state


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select_cohort(
    cell_id: str,
    capacity_class: str,
    tier: str,
    all_endpoints: list[str],
    registered_ts_by_endpoint: dict[str, float] | None = None,
    now_ts: float | None = None,
    window_sec: float = DEFAULT_FAIRNESS_WINDOW_SEC,
    risk_profiles: dict[str, "SubscriberProfile"] | None = None,
) -> list[str]:
    """Return the cohort of endpoints that should receive THIS occurrence
    of the signal.

    Selection rule:
      1. If risk_profiles is supplied, drop endpoints whose profile does not
         accept this tier (Pass-18: subscribers pick their own risk floor).
      2. If capacity_class is large/huge → broadcast to all remaining (no rotation).
      3. Otherwise, sort remaining endpoints by (weighted_count ASC,
         last_alloc_ts ASC, registered_ts ASC) and take the first cohort_size.

    The sort key ensures fairness over time: lowest fairness budget gets
    the next signal; ties broken by longest-waiting; final tiebreak by
    longest-subscribed (rewards loyalty when fairness is identical).

    risk_profiles is optional and backward-compatible: if None, every
    endpoint is treated as accepting all tiers (the pre-Pass-18 behavior).

    Pure function: does NOT update state. Call record_allocation() after
    delivering the signal to update the fairness ledger.
    """
    if not all_endpoints:
        return []
    eligible = filter_endpoints_by_risk_profile(all_endpoints, tier, risk_profiles)
    if not eligible:
        return []
    cohort_size = CAPACITY_COHORT_SIZE.get(capacity_class, 20)
    if cohort_size >= len(eligible):
        return list(eligible)
    state = _compute_fairness_state(eligible, window_sec=window_sec,
                                       now_ts=now_ts)
    reg_ts = registered_ts_by_endpoint or {}

    def _key(ep: str):
        f = state[ep]
        return (f.weighted_count, f.last_alloc_ts, reg_ts.get(ep, 0.0))

    ordered = sorted(eligible, key=_key)
    return ordered[:cohort_size]


def record_allocation(cell_id: str, tier: str, endpoints: list[str],
                        now_ts: float | None = None) -> None:
    """Persist an allocation event after a cohort has been notified.
    Call this AFTER push delivery (or queue) so a failed push doesn't
    inflate the cohort's fairness score erroneously."""
    if not endpoints:
        return
    event = AllocationEvent(
        cell_id=cell_id,
        tier=tier,
        endpoints=list(endpoints),
        ts_utc=now_ts if now_ts is not None else time.time(),
    )
    _append_allocation(event)


def get_fairness_summary(all_endpoints: list[str],
                            window_sec: float = DEFAULT_FAIRNESS_WINDOW_SEC,
                            now_ts: float | None = None) -> list[dict]:
    """For admin/debug UI: per-endpoint fairness state, sorted by
    weighted_count ASC (most-deserving-of-next-signal first)."""
    state = _compute_fairness_state(all_endpoints, window_sec=window_sec,
                                       now_ts=now_ts)

    def _key(ep: str):
        f = state[ep]
        return (f.weighted_count, f.last_alloc_ts)

    return [asdict(state[ep]) for ep in sorted(all_endpoints, key=_key)]
