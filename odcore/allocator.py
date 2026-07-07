"""odcore/allocator.py — the shared-POOL capital allocator (S67 capital model, architect read §2.2).

WHY THIS EXISTS: the majors basket runs each cell at a FLAT $5k slice and reports the sum (the
`aggregate (sum @ $5k each)` line in basket_sim_kraken.py:203, which the code itself flags as the
wrong framing). The real platform holds ONE shared pool that is spread across coins ($2k on one,
$2k on another, $1k on a third) — capacity-capped per coin and correlation-aware — never $5k-each.
This module is the decision primitive for that spread. It is pure-numpy and imports nothing from the
live decision path, so it composes UNDER platform.run_portfolio without touching run_cell/run_stream.

GRANULARITY (Greg S67, load-bearing): capacity enters as a SWAPPABLE per-key cap. v1 keys are COINS
(a per-coin position cap) — Greg's explicit jump-off point, "ultimately the wrong strategy, adjust
later." The migration to per-LEG caps (odcore/capacity.py, the right microstructure granularity) is
a change of the `caps` dict the caller passes, NOT a rewrite of the allocator. TWO HARD RULES the
allocator obeys so the scaffold can't calcify into damage:
  1. The cap is a SIZE SCALE, never an inclusion gate. A thin-cap coin gets SMALL notional, it is
     never dropped/zeroed/excluded for having a low cap. Roster membership is decided elsewhere
     (by per-cell edge grade), never here.
  2. Weighted water-fill (not strict priority) so every positive-demand key with pool headroom gets
     a proportional share — the pool binds by MAGNITUDE, never by identity.

MECHANIC: `allocate(demands, caps, pool, weights, clusters, cluster_caps)` distributes one shared
budget across competing keys, respecting THREE caps in priority order (architect §2.2):
  1. per-key cap    — hard: allocated_i <= min(demand_i, cap_i).
  2. cluster cap    — Σ over a correlation cluster <= its budget (a correlated flush can't draw the
                      whole pool).
  3. pool cap       — Σ allocated <= pool (the ONLY place "$5k" enters; never a per-cell slice).
Within the caps, funding is proportional to `weights` (return-on-capacity = edge per $ of capacity),
so the best edge-per-$ coins fill first when the pool is tight, but nobody is excluded.
"""
from __future__ import annotations

import numpy as np

_INF = float("inf")


def allocate(demands, caps=None, pool=_INF, *, weights=None, clusters=None, cluster_caps=None,
             mode="greedy", tol=1e-9):
    """Distribute a shared POOL across competing keys under 3 caps.

    mode:
      "greedy" (DEFAULT — Greg S67 "best profit potential per hour with our $5k, fill the best first"):
        rank keys by weight (return-on-capacity = edge per $) DESCENDING and fill each to its ceiling
        before the next. A NON-POSITIVE-weight key is NOT funded (idle pool earns 0 > deploying into a
        losing trade) — but it is NOT dropped from the roster (idle costs nothing; it stays available
        for a step/regime where its edge is positive). This maximises expected pool $/hr.
      "proportional": weighted water-fill — every positive-demand key with headroom gets a share
        proportional to its weight (spreads for Sharpe/diversification). Reference mode.

    demands:      {key: desired_usd}  — what each live key wants this step (>=0).
    caps:         {key: capacity_usd} — hard per-key ceiling (the SWAPPABLE capacity; per-coin v1).
                  Missing key => uncapped. This is a SIZE cap, never an inclusion gate (rule 1).
    pool:         total shared $ available this step (default inf = unconstrained).
    weights:      {key: priority}     — funding weight = return-on-capacity (edge per $). Higher =>
                  larger proportional share when the pool binds. Missing/<=0 => funded last/equally.
    clusters:     {key: cluster_id}   — optional correlation-cluster label per key.
    cluster_caps: {cluster_id: max_usd} — optional per-cluster budget (a correlated flush cap).

    Returns {key: allocated_usd} with allocated_i <= min(demand_i, cap_i), Σ <= pool, and per-cluster
    Σ <= cluster_cap. Proportional water-fill: a positive-demand key with headroom is never zeroed
    while pool + its cluster budget remain.
    """
    keys = list(demands)
    caps = caps or {}
    weights_given = bool(weights)
    weights = weights or {}
    # effective ceiling per key = min(demand, cap); clamp negatives to 0.
    ceil = {k: max(0.0, min(float(demands[k]), float(caps.get(k, _INF)))) for k in keys}
    alloc = {k: 0.0 for k in keys}
    remaining = float(pool)
    clus_rem = dict(cluster_caps) if cluster_caps else None

    def key_weight(k):
        w = float(weights.get(k, 0.0))
        return w if w > 0 else 0.0

    # NO priority info (caller passed no weights) -> equal priority in BOTH modes (fund all, e.g. the
    # canary's pool=inf faithfulness check). When weights ARE given, respect them: greedy skips
    # non-positive edge (idle pool beats a losing trade), even to funding nothing if the whole roster
    # is negative — a coin is never DROPPED (it stays seated for a step/regime where its edge turns +).
    if not weights_given:
        def key_weight(k):  # noqa: F811 — equal-priority fallback
            return 1.0

    def cluster_room(k):
        if clus_rem is None or clusters is None or k not in clusters:
            return _INF
        return max(0.0, clus_rem.get(clusters[k], _INF))

    if mode == "greedy":
        # fill the BEST edge-per-$ coin to its ceiling first, then the next, until the pool is spent;
        # skip non-positive edge (idle beats a losing trade). Ties broken by larger ceiling first.
        order = sorted(keys, key=lambda k: (key_weight(k), ceil[k]), reverse=True)
        for k in order:
            if key_weight(k) <= 0 or remaining <= tol:
                continue
            grant = min(ceil[k] - alloc[k], cluster_room(k), remaining)
            if grant <= tol:
                continue
            alloc[k] += grant
            remaining -= grant
            if clus_rem is not None and clusters is not None and k in clusters:
                clus_rem[clusters[k]] = clus_rem.get(clusters[k], _INF) - grant
        return alloc

    active = [k for k in keys if ceil[k] - alloc[k] > tol and key_weight(k) > 0
              and cluster_room(k) > tol]
    # water-fill: each pass grants each active key its weight-proportional share of the remaining
    # pool, clipped to its own headroom and cluster headroom; keys that hit a ceiling drop out and
    # their unused share reflows to the rest on the next pass.
    guard = 0
    while active and remaining > tol and guard < 10000:
        guard += 1
        wsum = sum(key_weight(k) for k in active)
        if wsum <= 0:
            break
        # FIX the share basis at pass start (pass_pool, wsum); grants that hit a key's ceiling reflow
        # to the rest on the NEXT pass. Decrementing `remaining` mid-pass would skew funding to
        # whichever key iterates first instead of by weight (a water-fill must divide the SAME
        # pass_pool by the SAME wsum for every key in the pass).
        pass_pool = remaining
        granted_any = False
        for k in list(active):
            share = pass_pool * key_weight(k) / wsum
            room = min(ceil[k] - alloc[k], cluster_room(k))
            grant = min(share, room)
            if grant <= tol:
                if room <= tol:
                    active.remove(k)
                continue
            alloc[k] += grant
            remaining -= grant
            if clus_rem is not None and clusters is not None and k in clusters:
                clus_rem[clusters[k]] = clus_rem.get(clusters[k], _INF) - grant
            granted_any = True
            if ceil[k] - alloc[k] <= tol or cluster_room(k) <= tol:
                active.remove(k)
        if not granted_any:
            break
    return alloc


def pnl_correlation(streams):
    """Per-coin PnL-bucket correlation (promoted from basket_sim_kraken.py:192, the ad-hoc corrcoef,
    so the allocator's cluster machinery lives in odcore — architect §2.3).

    streams: {coin: 1-D array of per-bucket $ PnL}. Coins with a flat (zero-variance) stream are
    dropped from the matrix (undefined correlation). Returns (coins, corr) — coins is the retained
    order, corr an (n,n) matrix; ([], None) if fewer than 2 non-flat coins.
    """
    coins = [c for c in streams if np.asarray(streams[c], float).std() > 0]
    if len(coins) < 2:
        return coins, None
    M = np.vstack([np.asarray(streams[c], float) for c in coins])
    return coins, np.corrcoef(M)


def cluster_by_corr(coins, corr, thresh=0.5):
    """Union-find clustering: coins whose PnL correlation exceeds `thresh` share a cluster. Returns
    {coin: cluster_id}. A coin uncorrelated with all others is its own singleton cluster. Used to set
    cluster_caps so a correlated group cannot draw the whole pool (architect §1.4/§2.2 cap #2).
    Coins absent from `corr` (e.g. flat streams) each get a singleton cluster (never merged blindly).
    """
    parent = {c: c for c in coins}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    if corr is not None:
        idx = list(coins)  # `coins` here is expected to be the corr-matrix order
        for i in range(len(idx)):
            for j in range(i + 1, len(idx)):
                if abs(corr[i, j]) >= thresh:
                    union(idx[i], idx[j])
    roots = {}
    out = {}
    for c in coins:
        r = find(c)
        out[c] = roots.setdefault(r, len(roots))
    return out
