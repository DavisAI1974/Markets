"""
markets_refrag_adapter.py
DavisAI - Markets bridge to refrag's runtime plane.

Runs the full 8-runtime-operator refrag pipeline (od_spectral_retrieval_pipeline)
on every winner trade in oracle_winner_trade_list.json. Per-winner outputs:
chunks -> embeddings -> query -> retrieval -> falsification -> operator
coefficients with posterior -> evidence graph -> operator validity probability.

Architecture: the 8 runtime operators and the orchestrator already exist in
refrag_discovery/runtime/. The MarketBar-flavored primitives in
E:\\Markets\\markets_adapter.py preserve microstructure features (VPIN, Hawkes,
Kyle, dipole) but are NOT in the orchestrator path for this first pass --
the orchestrator gets pure log_returns floats and runs the domain-agnostic
pipeline. Extension path (multi-channel, MarketChunker substitution) is
documented in the handoff.

Bin source: durable JSONL archive at E:\\Markets\\live_data_history\\<UTC-date>\\
via markets_bar_loader.load_closes. Replaces the original direct read of
live_data/*.json (a 6-hour LRU snapshot that was rolling old bars out from
under the pipeline, causing 68% skip rate on the first full run).

Usage:
    python E:\\refrag\\adapters\\markets_refrag_adapter.py [--smoke] [--limit N] [--out-dir PATH] [--resume]

  --resume   Skip winners whose source_id is already in summary.json, then
             append new results. Use this after the first full run to fill in
             previously-skipped winners with the new archive-backed loader.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# refrag imports
REFRAG_ROOT = Path(r"E:\refrag")
MARKETS_ROOT = Path(r"E:\Markets")
if str(REFRAG_ROOT) not in sys.path:
    sys.path.insert(0, str(REFRAG_ROOT))
ADAPTERS_DIR = REFRAG_ROOT / "adapters"
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

# Arch §8 Phase 6 / Rule 6 gate: default graph_rewriter to ENABLED in analyze
# mode for this adapter. Side-effecting modes (propose_and_simulate, execute)
# remain token-gated inside operator_graph_rewriter itself, so this default
# only unlocks the read-only structural analysis (bottlenecks, redundancies,
# friction points, health score). Explicit ENABLE_GRAPH_REWRITER=0 still wins.
os.environ.setdefault("ENABLE_GRAPH_REWRITER", "1")

from refrag_discovery.runtime.operator_orchestrator import OperatorOrchestrator  # noqa: E402
from refrag_discovery.control_plane import call_control_plane_operator  # noqa: E402
from refrag_discovery.control_plane.pipeline_performance_optimizer import (  # noqa: E402
    synthesize_retrieval_policy_control_loop,
)
from refrag_discovery.control_plane.storage import load_json, operator_state_path  # noqa: E402
from refrag_discovery.control_plane.task_meta_learner import run_task_meta_learner  # noqa: E402
from refrag_discovery.registry import trace_store  # noqa: E402
from markets_bar_loader import (  # noqa: E402
    TimedClose,
    load_closes,
    slice_closes,
    closes_to_log_returns,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WINNER_JSON = MARKETS_ROOT / "research" / "strategy_evolution" / "oracle_winner_trade_list.json"

# (asset, venue) pairs we know how to load. Loader handles the actual files.
BIN_AV = [
    ("BTC", "Bybit"),
    ("BTC", "Coinbase"),
    ("BTC", "Kraken"),
    ("ETH", "Bybit"),
    ("ETH", "Coinbase"),
    ("ETH", "Kraken"),
]

DEFAULT_OUT_DIR = MARKETS_ROOT / "_full_pipeline_winners"

# Arch §1.1: the 8 runtime operators (R-plane). The orchestrator handles
# Phase 1 (lifecycle/lineage) + Phase 2 (closed-loop falsification) for these
# per-call; the adapter handles Phase 3 (chain_builder), Phase 4 (gap_finder,
# manifest_synthesizer, cross_domain_transfer_detector), and Phase 6
# (promotion_recommender + graph_rewriter analyze) at bucket boundaries.
# ``operator_graph_rewriter`` runs in analyze mode (read-only, no approval
# token) — the side-effecting propose_and_simulate/execute modes remain
# token-gated inside the operator per arch Rule 6.
_RUNTIME_OPERATOR_IDS = [
    "spectral_chunker",
    "spectral_chunk_encode",
    "operator_query",
    "retrieval_policy_learner",
    "falsification_prioritizer",
    "operator_decoder",
    "evidence_graph_builder",
    "operator_orchestrator",
]

# Pipeline thresholds (HARD FLOORS — the meta-learner can lift these but
# never lower them. The sliding-window chunker produces ZERO chunks if
# input length < window_size, AND a single whole-segment "degenerate" chunk
# in hybrid mode when input length is exactly between window_size and the
# next stride boundary. Both modes silently destroy downstream operators:
# operator_coefficients=[0.0], empty evidence graph. Architect review
# flagged this as the #1 smoke-test failure mode.
#
# Fix C: the EFFECTIVE minimum is computed after the meta-learner call so
# we honor task_meta_learner recommendations (arch §10 — orchestrator does
# not tune; adapter pulls + passes through). A static MIN_RETURNS=32 would
# silently let a window_size=192 recommendation through and produce 1-chunk
# degenerate runs whenever a trade had between 32 and 191 log_returns.)
CHUNKER_WINDOW_SIZE = 32  # hard floor used when meta-learner is unavailable
CHUNKER_STRIDE = 16
CHUNKER_MIN_SEGMENT = 16

# Incremental flush — write summary.json every N processed records so a
# kill-mid-run loses at most N records instead of everything. Architect
# risk #3 mitigation from the prior handoff.
FLUSH_EVERY = 50


# Bar loading is provided by markets_bar_loader (JSONL archive + live snapshot).


# ---------------------------------------------------------------------------
# Per-winner pipeline runner
# ---------------------------------------------------------------------------

def winner_domain(asset: str, venue: str, side: str, outcome: str = "win",
                  domain_suffix: str = "") -> str:
    """Granular cell tag matching the migration script's inference rules.

    Format: ``markets_<asset>_<venue>_<side>_<outcome>[_<suffix>]`` (all lowercase).
    ``outcome`` is ``win`` or ``lose`` and is set from the adapter's
    ``--outcome`` flag because the input JSON is pre-split by bucket.
    ``domain_suffix`` is an optional non-cosmetic fork tag (e.g. ``preentry``)
    that keeps an experimental run's discoveries fully isolated from the
    canonical post-hoc dataset. Unlike the bucket_tag regex normalizer
    (which strips ``.eligibleN``/``.primary.*`` etc. back to canonical),
    domain_suffix lives on the domain key itself and is preserved end-to-end.
    """
    outcome = (outcome or "win").lower()
    if outcome not in ("win", "lose"):
        outcome = "win"
    base = f"markets_{asset.lower()}_{venue.lower()}_{side.lower()}_{outcome}"
    if domain_suffix:
        return f"{base}_{domain_suffix.lower()}"
    return base


def run_pipeline_on_winner(
    orch: OperatorOrchestrator,
    source_id: str,
    log_returns: list[float],
    domain: str,
    chunker_config: dict,
    query_config: dict,
) -> dict:
    """Run the full 10-stage refrag pipeline on one winner's log returns.

    ``domain`` is the granular cell tag (see ``winner_domain``) so the
    orchestrator routes the per-discovery JSON to
    ``discoveries/operator_discoveries/<domain>/<run_id>.json`` and
    accumulates per-cell evidence at
    ``discoveries/evidence_graphs/<domain>_evidence.json``.

    ``chunker_config`` and ``query_config`` carry the per-bucket recommendation
    from ``task_meta_learner`` (see main() — recommend_config call before the
    per-winner loop). Per arch §10 the orchestrator does not tune
    hyperparameters; the adapter pulls the recommendation from the control
    plane and passes it through. Hardcoded chunker constants here would
    bypass the meta-learner and lock the pipeline to a config that — at the
    32/16 default — produced bit-identical operator coefficients across all
    trades in a markets cell because 1s-bin log_returns are zero-dominated
    inside a 32-sample window.

    Returns the full orchestrator output dict, including run_id, result
    (operator_coefficients, evidence_graph, validity_posterior, etc.),
    execution_trace, and telemetry_routed.
    """
    return orch.execute(
        pipeline_id="od_spectral_retrieval_pipeline",
        data_sources={source_id: log_returns},
        query=query_config,
        task_config={
            "spectral_chunker": chunker_config,
            # NB: do NOT override evidence_graph_builder.existing_graph here.
            # The orchestrator loads the per-domain accumulated graph from
            # ``discoveries/evidence_graphs/<domain>_evidence.json`` and
            # passes it via setdefault. An explicit ``None`` here was the
            # 2026-05-25 bug that made every per-cell graph hold only the
            # last 1-2 trades instead of all N trades in the bucket — the
            # builder was building from scratch every call. Per arch §4 the
            # per-domain graph is meant to accumulate within its domain;
            # cross-domain isolation is already provided by the per-cell
            # filename scheme.
        },
        # Phase 2 (arch §8): closed-loop falsification. Per Greg's 2026-05-25
        # call: iterate until convergence, no arbitrary iteration cap.
        # Termination signal is "no new coefficients produced" — orchestrator
        # tracks max |coef[N] - coef[N-1]| and stops when below delta_threshold.
        # max_iterations is a runaway safety stop ONLY (so a broken decoder
        # can't burn forever).
        termination_config={
            "max_iterations": 100_000,
            "delta_threshold": 1e-6,
        },
        domain=domain,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _load_existing_summary(path: Path) -> dict | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _atomic_write_summary(summary_path: Path, payload: dict) -> None:
    """Write summary.json via tmp + replace so a kill never leaves a 0-byte file."""
    tmp = summary_path.with_suffix(summary_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(summary_path)


def _build_payload(
    *,
    existing: dict | None,
    new_results: list[dict],
    n_skipped_no_coverage: int,
    n_skipped_too_short: int,
    n_skipped_already_done: int,
    n_errors: int,
    t_start: float,
) -> dict:
    this_session_elapsed = round(time.time() - t_start, 2)
    common = {
        "winner_json": str(WINNER_JSON),
        "pipeline_id": "od_spectral_retrieval_pipeline",
    }
    if existing:
        prior_elapsed = float(existing.get("elapsed_s", 0))
        prior_sessions = list(existing.get("session_elapsed_s", [])) or [prior_elapsed]
        merged_results = list(existing.get("results", [])) + new_results
        return {
            **common,
            "elapsed_s": round(prior_elapsed + this_session_elapsed, 2),
            "session_elapsed_s": prior_sessions + [this_session_elapsed],
            "processed": len(merged_results),
            "processed_this_session": len(new_results),
            "skipped_no_coverage": n_skipped_no_coverage + int(existing.get("skipped_no_coverage", 0)),
            "skipped_no_coverage_this_session": n_skipped_no_coverage,
            "skipped_too_short": n_skipped_too_short + int(existing.get("skipped_too_short", 0)),
            "skipped_too_short_this_session": n_skipped_too_short,
            "skipped_already_done_this_session": n_skipped_already_done,
            "errors": n_errors + int(existing.get("errors", 0)),
            "errors_this_session": n_errors,
            "results": merged_results,
        }
    return {
        **common,
        "elapsed_s": this_session_elapsed,
        "processed": len(new_results),
        "skipped_no_coverage": n_skipped_no_coverage,
        "skipped_too_short": n_skipped_too_short,
        "errors": n_errors,
        "results": new_results,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="Process first 10 covered winners then stop (~30-60s).")
    ap.add_argument("--limit", type=int, default=0,
                    help="Cap on number of winners processed (0 = no cap).")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--resume", action="store_true",
                    help="Skip winners whose source_id is already in summary.json, "
                         "then merge new results into the same file.")
    ap.add_argument("--winner-json", type=Path, default=WINNER_JSON,
                    help="Path to a per-bucket JSON (oracle_winner_trade_v1 schema). "
                         "Default = the full oracle_winner_trade_list.json.")
    ap.add_argument("--outcome", choices=("win", "lose"), default="win",
                    help="Tag every discovery's cell with this outcome suffix. "
                         "Pair with --winner-json pointing at the matching bucket "
                         "(e.g. markets_btc_bybit_buy_lose.json + --outcome lose).")
    ap.add_argument("--no-promote-synthesized-manifests", action="store_true",
                    help="Disable manifest_synthesizer's Discovery Loop closure: "
                         "synthesized draft manifests will be returned in the Phase 4 "
                         "report but NOT persisted to registry/manifests/proposed/. "
                         "Default is to persist (arch §5 Discovery Loop closure). "
                         "Per Rule 6 spirit ('reversible graph modifications') drafts "
                         "land in a separate 'proposed/' subdir so they don't pollute "
                         "the production manifest set until manual review.")
    ap.add_argument("--domain-suffix", type=str, default="",
                    help="Optional non-cosmetic domain fork tag (e.g. 'preentry'). "
                         "Appended to the cell domain key so an experimental run's "
                         "discoveries land in markets_<asset>_<venue>_<side>_<outcome>_"
                         "<suffix>/ — fully isolated from the canonical post-hoc "
                         "dataset. Used by pre-entry validation (P1 in 2026-05-27 "
                         "handoff) so we can compare new operator_coefficients to "
                         "the post-hoc baseline without overwriting it.")
    ap.add_argument("--pre-entry-minutes", type=int, default=0,
                    help="If > 0, swap the per-trade pipeline window from the post-hoc "
                         "[entry_ts, exit_ts] to the pre-entry [entry_ts - N*60, entry_ts]. "
                         "Operator_coefficients are then computed from bars BEFORE the "
                         "trade fired (no exit data leak). Eligibility check still uses "
                         "min_returns; with 1-sec bars and N=30 the window has ~1800 bars "
                         "so the 192-bar floor is trivially met. Pair with --domain-suffix "
                         "preentry to isolate discoveries from the post-hoc baseline.")
    args = ap.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_path = out_dir / "summary.json"
    existing = _load_existing_summary(summary_path) if args.resume else None
    skip_set: set[str] = set()
    if existing:
        skip_set = {r["trade_source_id"] for r in existing.get("results", [])}
        print(f"Resume mode: {len(skip_set)} trade_source_ids already in summary.json — will skip those")

    winner_json_path = args.winner_json
    print(f"Loading winner JSON: {winner_json_path} (outcome={args.outcome})")
    with winner_json_path.open() as f:
        wj = json.load(f)
    entries = wj["entries"]
    print(f"  {len(entries)} entries")

    # Group by (asset, venue) for batched bar loading
    by_av: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for e in entries:
        by_av[(e["asset"], e["venue"])].append(e)
    print(f"  groups: {dict((f'{a}/{v}', len(es)) for (a, v), es in by_av.items())}")

    # Load bars once per (asset, venue) from the JSONL archive (durable, not
    # subject to the 6-hour rolling-window eviction of live_data/*.json).
    # Buffer the request range so per-winner [entry_ts, exit_ts] checks have margin.
    BUFFER_S = 6 * 3600
    closes_cache: dict[tuple[str, str], list[TimedClose]] = {}
    for av, winners in by_av.items():
        if av not in BIN_AV:
            print(f"  SKIP {av}: not in BIN_AV")
            continue
        t_min_ent = min(float(w["entry_ts_utc"]) for w in winners)
        if args.pre_entry_minutes > 0:
            # Pre-entry: load bars ending at entry_ts (no exit-side reach).
            t_max_exit = max(float(w["entry_ts_utc"]) for w in winners)
            t_min_ent = t_min_ent - args.pre_entry_minutes * 60
        else:
            t_max_exit = max(
                float(w["entry_ts_utc"]) + float(w.get("horizon_minutes") or 0) * 60
                for w in winners
            )
        t0 = time.time()
        closes_cache[av] = load_closes(
            av[0], av[1],
            t_min=t_min_ent - BUFFER_S,
            t_max=t_max_exit + BUFFER_S,
        )
        print(f"  {av[0]}/{av[1]}: {len(closes_cache[av])} bars in {time.time()-t0:.2f}s")

    orch = OperatorOrchestrator()

    # Per arch §10 (orchestrator does not tune): query task_meta_learner once
    # per bucket for the chunker/query config recommendation. Bucket-level
    # call uses cumulative bar count + a rough noise estimate as task_features.
    total_bars = sum(len(c) for c in closes_cache.values())
    noise_sample = []
    for c in closes_cache.values():
        for tc in c[:8]:
            noise_sample.append(abs(tc.close))
    rough_noise = round(sum(noise_sample) / max(1, len(noise_sample)), 6) if noise_sample else 0.0
    task_features = {
        "domain": "operator-discovery",
        "data_type": "spectral",
        "size": total_bars,
        "noise": rough_noise,
    }
    bucket_tag = winner_json_path.stem  # e.g. markets_eth_coinbase_sell_win
    # Reduce derived/split file names (.primary, .secondary, .first100,
    # .eligible100, etc.) back to the canonical asset_venue_side_outcome tag.
    # Any dot-suffix that appears AFTER the canonical "_win" / "_lose" token
    # is a slice/derivation marker, not part of the bucket identity. Trace
    # domain + Phase 4 cross-domain pairing must reduce to the canonical form.
    import re as _re
    _m = _re.match(r"^(.+_(?:win|lose))(?:\..+)?$", bucket_tag)
    if _m:
        bucket_tag = _m.group(1)
    meta = run_task_meta_learner(
        task_description=f"od_spectral_retrieval_pipeline:{bucket_tag}",
        task_features=task_features,
        query_mode="recommend_config",
        artifacts_dir=Path(r"E:\refrag\artifacts"),
    )
    rec = meta["recommended_configuration"]
    rec_chunker = dict(rec.get("spectral_chunker") or {})
    rec_chunker.setdefault("window_size", CHUNKER_WINDOW_SIZE)
    rec_chunker.setdefault("stride", CHUNKER_STRIDE)
    rec_chunker.setdefault("min_segment_length", CHUNKER_MIN_SEGMENT)
    # Fix C: dynamic min_returns = max(rec.window_size, hard_floor). The
    # static MIN_RETURNS=32 was a silent footgun when the meta-learner
    # bumped window_size up to 192 for "large" task families — a trade with
    # 50 log_returns passed the static guard but produced a degenerate
    # single-chunk hybrid output downstream. Per Greg: never hardcode
    # limits (feedback_no_hardcoded_limits) — derive from upstream signal.
    min_returns = max(int(rec_chunker["window_size"]), CHUNKER_WINDOW_SIZE)
    rec_query_extra = dict(rec.get("operator_query") or {})
    rec_pipeline = dict(rec.get("pipeline") or {})
    query_config = {
        "query_mode": "from_spectral_target",
        "target_frequencies": [0.1, 0.25],
        "target_energy": 1.0,
        "top_k": rec_query_extra.get("top_k", 8),
        "expand_budget": rec_pipeline.get("expand_budget", 4),
    }
    print(
        f"  meta-learner recommendation (taxonomy={meta['task_classification']['taxonomy_id']}, "
        f"confidence={rec.get('confidence')}, source={rec.get('adaptation_source')}):"
    )
    print(f"    spectral_chunker: {rec_chunker}")
    print(f"    operator_query.top_k: {query_config['top_k']}, "
          f"pipeline.expand_budget: {query_config['expand_budget']}")

    # ---- Phase 3 (arch §8): Composition Loop ----
    # Per arch §5: chain_builder → composability_scorer → validation → chain_builder.
    # ``operator_chain_builder`` internally calls ``score_operator_composability``
    # for each adjacent pair in the resolved chain, so a single chain_builder
    # call engages the full Composition Loop. Result is logged for audit; the
    # runtime ``pipeline_id`` stays "od_spectral_retrieval_pipeline" because
    # chain_builder resolves "discovery" task_objectives to the canonical
    # pipeline (which IS the arch-prescribed template).
    #
    # Rule 5 (deterministic first): ``search_mode="exhaustive"``. The arch §8
    # Phase 3 "MCTS after 200+ traces" upgrade gates the implementation's
    # search behaviour, not this caller — we surface the deterministic chain
    # in the metadata and let chain_builder's internal upgrade flip when
    # the implementation supports it.
    cp_dir = out_dir / "control_plane"
    cp_dir.mkdir(parents=True, exist_ok=True)
    # Honor arch §6 chain_builder dependencies explicitly:
    #   - lineage_tracker:  load per-operator lineage state from disk and pass it
    #                       as ``lineage_snapshot`` so chain_builder can surface
    #                       latest_version / current_best_version per chain step
    #                       (arch §2: "queries the lineage tracker for best
    #                        version per slot"). Empty on first-ever run —
    #                       chain_builder handles missing snapshots gracefully.
    #   - task_meta_learner: pass the meta-learner's return so chain_builder can
    #                        modulate chain_score by recommendation confidence
    #                        (closes the arch §6 ``task_meta_learner →
    #                        chain_builder`` feed).
    #
    # Only ``search_mode`` is set explicitly otherwise — it's the arch-required
    # knob (Rule 5: "Deterministic First, Learned Later" + arch §8 Phase 3:
    # "Exhaustive search first. MCTS after 200+ traces"). ``constraints`` and
    # ``optimization_target`` are intentionally left at their function defaults
    # so we don't invent knobs the arch doc is silent on.
    lineage_snapshot: dict[str, dict] = {}
    for _op in _RUNTIME_OPERATOR_IDS:
        _lineage_path = operator_state_path("lineage", _op, artifacts_dir=None)
        if _lineage_path.exists():
            lineage_snapshot[_op] = load_json(_lineage_path, {})

    phase3_chain = call_control_plane_operator(
        "operator_chain_builder",
        {
            "task_objective": f"od_spectral_retrieval_pipeline:discovery:{bucket_tag}",
            "available_operators": _RUNTIME_OPERATOR_IDS,
            "search_mode": "exhaustive",
            "lineage_snapshot": lineage_snapshot,
            "task_meta_learner_recommendation": meta,
        },
    )
    _lineage_sum = phase3_chain.get("lineage_summary", {})
    print(
        f"  Phase 3 chain_builder: {len(phase3_chain.get('chain', []))} stages, "
        f"chain_score={phase3_chain.get('chain_score')}, "
        f"meta_modulated_score={phase3_chain.get('task_meta_learner_modulated_score')}, "
        f"stages_with_lineage={_lineage_sum.get('stages_with_lineage', 0)}/"
        f"{_lineage_sum.get('total_stages', 0)}, "
        f"missing_capabilities={len(phase3_chain.get('missing_capabilities', []))}"
    )
    (cp_dir / "phase3_chain_builder.json").write_text(
        json.dumps(phase3_chain, indent=2), encoding="utf-8"
    )

    if args.smoke:
        max_winners = 10
    elif args.limit > 0:
        max_winners = args.limit
    else:
        max_winners = len(entries)

    n_processed = 0
    n_skipped_already_done = 0
    n_skipped_no_coverage = 0
    n_skipped_too_short = 0
    n_errors = 0
    new_results: list[dict] = []

    # Fix A: collect per-trade control-plane inputs across the bucket so the
    # post-bucket Phase 5 capstone can fire benchmark_suite / pipeline_optimizer
    # / exploration_controller ONCE on aggregated data (per arch §1.2 control
    # plane runs "between discovery runs … not latency-sensitive"). Each entry
    # is one trade's contribution: policy_feedback (operator_metrics +
    # exploration_state) plus its execution_trace for optimizer profiling.
    bucket_policy_feedbacks: list[dict] = []
    bucket_execution_traces: list[dict] = []
    bucket_query_modes: list[str] = []
    bucket_selected_modes: list[str] = []
    bucket_last_retrieval_policy: dict | None = None

    print(f"\nRunning pipeline (cap = {max_winners}, resume={args.resume}) ...")
    t_start = time.time()
    for av, winners in by_av.items():
        closes = closes_cache.get(av)
        if closes is None or not closes:
            continue
        ts_min = closes[0].ts
        ts_max = closes[-1].ts

        for w in winners:
            if n_processed >= max_winners:
                break
            source_id = w["source_id"]
            if source_id in skip_set:
                n_skipped_already_done += 1
                continue
            entry_ts = float(w["entry_ts_utc"])
            horizon_min = float(w.get("horizon_minutes") or 0)
            exit_ts = entry_ts + horizon_min * 60.0

            if args.pre_entry_minutes > 0:
                window_lo = entry_ts - args.pre_entry_minutes * 60
                window_hi = entry_ts
            else:
                window_lo = entry_ts
                window_hi = exit_ts

            if window_lo < ts_min or window_hi > ts_max:
                n_skipped_no_coverage += 1
                continue

            sliced = slice_closes(closes, window_lo, window_hi)
            log_returns = closes_to_log_returns(sliced)
            # Fix C: dynamic threshold honors the meta-learner's window_size.
            if len(log_returns) < min_returns:
                n_skipped_too_short += 1
                continue

            try:
                domain = winner_domain(w["asset"], w["venue"], w["side"], args.outcome,
                                        domain_suffix=args.domain_suffix)
                out = run_pipeline_on_winner(
                    orch, source_id, log_returns, domain,
                    chunker_config=rec_chunker,
                    query_config=query_config,
                )
                result = out["result"]
                evidence_graph = result["evidence_graph"]
                # Fix A: harvest per-trade control-plane inputs for the
                # post-bucket Phase 5 sweep. ``policy_feedback`` was computed
                # by the orchestrator's _build_policy_control_plane_feedback
                # (cheap, runtime-side) and stashed on result["retrieval_policy"]
                # ["metadata"]; the adapter aggregates across all trades and
                # feeds the bucket-level snapshot to benchmark_suite +
                # pipeline_optimizer + exploration_controller post-loop.
                _rp_meta = result["retrieval_policy"].get("metadata", {})
                _pf = _rp_meta.get("policy_feedback")
                if _pf:
                    bucket_policy_feedbacks.append(_pf)
                bucket_execution_traces.append(out["execution_trace"])
                bucket_query_modes.append(query_config["query_mode"])
                bucket_selected_modes.append(
                    str(result["retrieval_policy"].get("selected_mode", ""))
                )
                bucket_last_retrieval_policy = result["retrieval_policy"]
                # Fix K: surface evidence-graph load status. When a per-cell
                # accumulated graph file is corrupt (bad JSON, schema invalid),
                # the orchestrator quarantines it as ``<cell>_evidence.json.invalid``
                # and starts fresh — a SILENT reset of N-1 trades' accumulated
                # evidence. Until this field landed, the only way to detect a
                # quarantine was to grep the discoveries dir for ``.invalid``
                # files. Now it shows up per-trade in summary.json: "ok",
                # "quarantined", or whatever the orchestrator surfaces.
                evidence_meta = result.get("evidence_graph_metadata", {}) or {}
                existing_graph_status = str(
                    evidence_meta.get("existing_graph_status", "ok")
                )
                new_results.append({
                    "trade_source_id": source_id,
                    "canonical_trade_key": w.get("canonical_trade_key", ""),
                    "asset": w["asset"],
                    "venue": w["venue"],
                    "side": w["side"],
                    "strategy_id": w.get("strategy_id", ""),
                    "net_bps": w.get("net_bps", 0.0),
                    "horizon_minutes": horizon_min,
                    "n_bars": len(sliced),
                    "n_log_returns": len(log_returns),
                    "run_id": out["run_id"],
                    "operator_coefficients_head": [round(c, 6) for c in result["operator_coefficients"][:16]],
                    "validity_probability": result["operator_validity_posterior"]["probability_valid"],
                    "evidence_graph_n_nodes": len(evidence_graph.get("nodes", [])),
                    "evidence_graph_n_edges": len(evidence_graph.get("edges", [])),
                    "selected_retrieval_mode": result["retrieval_policy"].get("selected_mode", ""),
                    "pipeline_latency_s": result["pipeline_latency_s"],
                    "existing_graph_status": existing_graph_status,
                })
                n_processed += 1
                if n_processed % FLUSH_EVERY == 0:
                    print(f"  processed {n_processed} winners "
                          f"({time.time()-t_start:.1f}s elapsed)", flush=True)
                    payload = _build_payload(
                        existing=existing,
                        new_results=new_results,
                        n_skipped_no_coverage=n_skipped_no_coverage,
                        n_skipped_too_short=n_skipped_too_short,
                        n_skipped_already_done=n_skipped_already_done,
                        n_errors=n_errors,
                        t_start=t_start,
                    )
                    _atomic_write_summary(summary_path, payload)
            except Exception as e:
                n_errors += 1
                print(f"  ERROR on {source_id}: {type(e).__name__}: {e}", flush=True)
                continue

        if n_processed >= max_winners:
            break

    payload = _build_payload(
        existing=existing,
        new_results=new_results,
        n_skipped_no_coverage=n_skipped_no_coverage,
        n_skipped_too_short=n_skipped_too_short,
        n_skipped_already_done=n_skipped_already_done,
        n_errors=n_errors,
        t_start=t_start,
    )
    # Write the per-winner summary BEFORE Phase 4 so cross_domain_transfer_detector
    # can read the source bucket's summary.json (the detector loads per-trade
    # operator_coefficients via summary -> per-run JSON paths). Two-stage
    # write: first the per-winner results, then a final write with all
    # control_plane_phases paths attached.
    # Fix C: surface the dynamic min_returns threshold in the summary so
    # downstream consumers can audit the chunker-window/skip-floor invariant.
    payload["chunker_window_size"] = int(rec_chunker["window_size"])
    payload["min_returns_threshold"] = int(min_returns)
    payload["control_plane_phases"] = {
        "phase3_chain_builder": str(cp_dir / "phase3_chain_builder.json"),
    }
    _atomic_write_summary(summary_path, payload)

    # ---- Phase 3b (arch §5 Composition Loop closure) ----
    # Per arch §5 the Composition Loop is:
    #     chain_builder → composability_scorer → validation → chain_builder
    # The pre-bucket call above is the "plan" half; the per-winner pipeline
    # executions ARE the validation pass (they update lineage state for each
    # runtime operator via the benchmark_suite cascade). Re-firing chain_builder
    # post-bucket with the freshly-updated lineage snapshot closes the loop:
    # if a runtime operator's lineage record gained a new best version during
    # the bucket, the post-bucket chain's chain_score and per-stage
    # current_best_version reflect it. The delta vs the pre-bucket plan is
    # written to phase3b_chain_builder_post_bucket.json for audit.
    #
    # Per arch Rule 10 ("orchestrator executes, does not plan") the adapter
    # — not the orchestrator — fires this. Runtime stays on the canonical
    # od_spectral_retrieval_pipeline either way; the post-bucket call is
    # an AUDIT, not a runtime selection.
    post_bucket_lineage_snapshot: dict[str, dict] = {}
    for _op in _RUNTIME_OPERATOR_IDS:
        _lineage_path = operator_state_path("lineage", _op, artifacts_dir=None)
        if _lineage_path.exists():
            post_bucket_lineage_snapshot[_op] = load_json(_lineage_path, {})

    phase3b_chain = call_control_plane_operator(
        "operator_chain_builder",
        {
            "task_objective": f"od_spectral_retrieval_pipeline:discovery:{bucket_tag}:post_bucket",
            "available_operators": _RUNTIME_OPERATOR_IDS,
            "search_mode": "exhaustive",
            "lineage_snapshot": post_bucket_lineage_snapshot,
            "task_meta_learner_recommendation": meta,
        },
    )
    _pre_score = float(phase3_chain.get("chain_score") or 0.0)
    _post_score = float(phase3b_chain.get("chain_score") or 0.0)
    _delta = round(_post_score - _pre_score, 4)
    _pre_modulated = float(phase3_chain.get("task_meta_learner_modulated_score") or 0.0)
    _post_modulated = float(phase3b_chain.get("task_meta_learner_modulated_score") or 0.0)
    _modulated_delta = round(_post_modulated - _pre_modulated, 4)
    print(
        f"  Phase 3b chain_builder (post-bucket audit): "
        f"chain_score={_post_score} (delta={_delta:+.4f}), "
        f"meta_modulated_score={_post_modulated} (delta={_modulated_delta:+.4f}), "
        f"stages_with_lineage="
        f"{phase3b_chain.get('lineage_summary', {}).get('stages_with_lineage', 0)}/"
        f"{phase3b_chain.get('lineage_summary', {}).get('total_stages', 0)}"
    )
    phase3b_payload = {
        "post_bucket": phase3b_chain,
        "deltas_vs_pre_bucket": {
            "chain_score_delta": _delta,
            "meta_modulated_score_delta": _modulated_delta,
            "pre_bucket_chain_score": _pre_score,
            "post_bucket_chain_score": _post_score,
        },
    }
    (cp_dir / "phase3b_chain_builder_post_bucket.json").write_text(
        json.dumps(phase3b_payload, indent=2), encoding="utf-8"
    )
    payload["control_plane_phases"]["phase3b_chain_builder_post_bucket"] = str(
        cp_dir / "phase3b_chain_builder_post_bucket.json"
    )

    # ---- Phase 4 (arch §8): Discovery Loop ----
    # Per arch §5: gap_finder → manifest_synthesizer → new manifests → gap_finder.
    # Plus cross_domain_transfer_detector (Discovery layer's third operator,
    # arch §1.2). All three are control-plane, called BETWEEN runs (Rule 1).
    #
    # Canonical post-bucket ordering per arch_workflow.py header + arch spec
    # phase numbering: 3 → 4 → 5 → 6. Discovery runs first (registry coverage,
    # pattern mining, cross-domain transfer) — independent of Phase 5 capstone
    # outputs. Phase 5 then aggregates per-bucket Evaluation/Optimization
    # signals (benchmark_suite, pipeline_optimizer, exploration_controller).
    # Phase 6 (Governance closure) reads Phase 5 outputs to score promotions
    # and run graph_rewriter analyze.
    #
    # Phase 4 + Phase 6 are BUCKET-LEVEL control-plane operators that read the
    # shared trace store and discovery registry; they fire even when --resume
    # processes zero new winners in THIS bucket, because the sibling/pair
    # domain may have accumulated new traces since the last firing.

    # gap_finder: registry coverage analysis.
    # Rule 5 (deterministic first): depth="surface_type_coverage" — uses the
    # type-count heuristics the implementation actually computes; arch §8
    # Phase 4 "geometric embedding" is a later upgrade layer.
    gap_report = call_control_plane_operator(
        "operator_gap_finder",
        {
            "registry_snapshot": None,
            "target_domains": ["operator-discovery", "markets"],
            "known_tasks": [bucket_tag],
            "depth": "surface_type_coverage",
        },
    )
    print(
        f"  Phase 4 gap_finder: {len(gap_report.get('gaps', []))} gaps, "
        f"{len(gap_report.get('dead_ends', []))} dead_ends, "
        f"{len(gap_report.get('unreachable_outputs', []))} unreachable_outputs"
    )
    (cp_dir / "phase4_gap_finder.json").write_text(
        json.dumps(gap_report, indent=2), encoding="utf-8"
    )

    # manifest_synthesizer: mine successful execution patterns from traces.
    # Rule 5 (deterministic first): synthesis_mode="pattern_mining" — the
    # PrefixSpan-style frequent-sequence path. VAE generation is a later upgrade.
    # Fix C: trace store migrated from JSONL to SQLite per arch §3.2.
    # recent_traces returns newest-first dicts (drop-in for the old tail-200
    # pattern); manifest_synthesizer treats ordering as set-like.
    execution_logs = trace_store.recent_traces(limit=200)
    # Fix E / arch §5 Discovery Loop closure: ``persist_drafts=True`` is the
    # default — the synthesizer writes proposed manifests to
    # ``registry/manifests/proposed/<op>.v<ver>.json`` and the audit log
    # (Fix D) records each promotion. ``--no-promote-synthesized-manifests``
    # is the kill switch when investigating registry churn or replaying old
    # bucket runs without polluting the proposed/ subdir.
    persist_drafts = not args.no_promote_synthesized_manifests
    synth_report = call_control_plane_operator(
        "manifest_synthesizer",
        {
            "execution_logs": execution_logs,
            "min_occurrences": 5,
            "min_success_rate": 0.9,
            "synthesis_mode": "pattern_mining",
            "persist_drafts": persist_drafts,
        },
    )
    _persisted = [p for p in synth_report.get("persisted_manifest_paths", []) if p]
    print(
        f"  Phase 4 manifest_synthesizer: "
        f"{len(synth_report.get('proposed_manifests', []))} proposed manifests "
        f"from {len(execution_logs)} recent traces "
        f"(persist_drafts={persist_drafts}; "
        f"{len(_persisted)} written to registry/manifests/proposed/)"
    )
    (cp_dir / "phase4_manifest_synthesizer.json").write_text(
        json.dumps(synth_report, indent=2), encoding="utf-8"
    )

    # cross_domain_transfer_detector: intra-asset cross-outcome transfer
    # (winner vs loser within same asset/venue/side cell — the analytical
    # question per Greg's chunker-feature evidence: spectral_entropy d=+2.17
    # separates winners from losers; transfer detection asks whether the
    # decoder recovered comparable operator structure across the two
    # outcome populations of the same instrument).
    #
    # Rule 5 (deterministic first): comparison_mode="spectral_similarity"
    # — FAISS cosine over per-trade operator_coefficients (rule-7 safe; uses
    # refrag-core FaissIndex unmodified). MAML cross-domain is a later upgrade.
    opposite_outcome = "lose" if args.outcome == "win" else "win"
    if bucket_tag.endswith(("_win", "_lose")):
        opposite_bucket = bucket_tag.rsplit("_", 1)[0] + "_" + opposite_outcome
    else:
        opposite_bucket = bucket_tag + "_" + opposite_outcome
    # Fix A: detector previously hardcoded a registry of summary paths that
    # didn't match the adapter's actual ``--out-dir``. Pass an explicit map
    # from the bucket tag -> its summary.json so the detector reads OUR
    # output, not a stale default. The opposite-outcome path is inferred from
    # the conventional sibling layout (E:\Markets\per_bucket_runs\<bucket>\).
    transfer_report = call_control_plane_operator(
        "cross_domain_transfer_detector",
        {
            "source_domain": bucket_tag,
            "target_domain": opposite_bucket,
            "comparison_mode": "spectral_similarity",
            "similarity_threshold": 0.7,
            "summary_paths_by_domain": {
                bucket_tag: str(summary_path),
                opposite_bucket: str(out_dir.parent / opposite_bucket / "summary.json"),
            },
        },
    )
    print(
        f"  Phase 4 cross_domain_transfer_detector: "
        f"source={bucket_tag} -> target={opposite_bucket}, "
        f"candidates={len(transfer_report.get('transfer_candidates', []))}, "
        f"significance={transfer_report.get('publication_readiness', {}).get('significance', 'n/a')}"
    )
    (cp_dir / "phase4_cross_domain_transfer.json").write_text(
        json.dumps(transfer_report, indent=2), encoding="utf-8"
    )

    # ---- Phase 5 (arch §8): Evaluation + Optimization + Meta-Learning capstone ----
    # Fix A (deferred-bug item A, 2026-05-25): plane separation refactor.
    #
    # Per arch §1.2 the control plane runs "between discovery runs, on
    # periodic schedules, or in the background … not latency-sensitive".
    # These three control-plane operators MOVED here from inside the
    # orchestrator's per-trade execute() block (which violated Rule 1):
    #   - operator_benchmark_suite       (Evaluation [C])
    #   - pipeline_performance_optimizer (Optimization [C])
    #   - exploration_policy_controller  (Optimization [C])
    # plus the synthesised retrieval-policy control-loop state (moved out of
    # OperatorOrchestrator._persist_retrieval_policy_control_loop per Rule 10).
    #
    # task_meta_learner.update_from_outcome STAYS per-trade (arch §1 'X'
    # classification + online credit-assignment — moving it post-bucket
    # would lose the per-trial signal). Its recommend_config call is the
    # pre-bucket Phase 5 invocation already wired above.
    #
    # Aggregation strategy:
    #   - operator_benchmark_suite: passes the LATEST per-trade policy_feedback
    #     (the orchestrator stashes it on result["retrieval_policy"]["metadata"]
    #     ["policy_feedback"] for harvest). Since each per-trade benchmark
    #     reads the cumulative retrieval_policy_benchmark.json anyway, calling
    #     once with the last trade's metrics is equivalent to the prior
    #     per-trade firings — and saves N-1 calls.
    #   - pipeline_performance_optimizer: passes an AGGREGATED execution_trace
    #     (median stage timings across the bucket) so optimizer profiling
    #     reflects bucket-level behaviour rather than one stochastic trade.
    #   - exploration_policy_controller: passes the latest exploration_state
    #     (same reasoning as benchmark_suite — policy_benchmark is cumulative).
    #
    # The orchestrator's runtime-side outputs (lifecycle/lineage/task_meta_learner
    # per-trade) feed this capstone via the on-disk benchmark / history files.
    #
    # Fix I: --resume rehydration. When the per-trade loop skipped every entry
    # (resume found them all in summary.json), the in-memory bucket lists stay
    # empty and Phase 5 would otherwise be SKIPPED. Phase 5 is bucket-level,
    # not per-trade — it SHOULD fire against the FULL bucket population.
    # Rehydrate execution_traces from the SQLite trace store and synthesize
    # policy_feedback from the cumulative retrieval_policy_benchmark.json
    # (which the orchestrator keeps updated across all runs). This gives
    # Phase 5 + Phase 6 real-data inputs even when no new winners arrived.
    if args.resume and not bucket_policy_feedbacks and len(new_results) == 0:
        import sqlite3 as _sqlite3
        from refrag_discovery.paths import ARTIFACTS_DIR as _ARTIFACTS_DIR
        _trace_db = _ARTIFACTS_DIR / "execution_traces.sqlite"
        _benchmark_path = _ARTIFACTS_DIR / "retrieval_policy_benchmark.json"
        if _trace_db.exists():
            _c = _sqlite3.connect(str(_trace_db))
            _rows = _c.execute(
                "SELECT payload_json FROM traces WHERE domain = ? ORDER BY ts_ms ASC",
                (bucket_tag,),
            ).fetchall()
            _c.close()
            for _row in _rows:
                try:
                    _payload = json.loads(_row[0])
                except (json.JSONDecodeError, TypeError):
                    continue
                bucket_execution_traces.append(_payload)
            _query_mode_default = "from_spectral_target"
            _policy_benchmark = (
                json.loads(_benchmark_path.read_text(encoding="utf-8"))
                if _benchmark_path.exists() else {}
            )
            _query_mode_metrics = _policy_benchmark.get("query_mode_metrics", {})
            _selected_mode = (
                _query_mode_metrics.get(_query_mode_default, {}).get("best_mode")
                or _policy_benchmark.get("summary", {}).get("best_mode")
                or ""
            )
            _synth_rp = {
                "selected_mode": _selected_mode,
                "metadata": {"last_reward_signal": "composite"},
            }
            # Build a single representative policy_feedback from the cumulative
            # benchmark state. _build_policy_control_plane_feedback is a
            # deterministic function of (pipeline_id, query_mode, retrieval_policy,
            # policy_outcome, policy_benchmark) — using benchmark cumulative
            # state per arch §1.2 means the rehydrated feedback reflects what
            # the orchestrator would emit at the LAST trade's invocation.
            _orch_for_synth = OperatorOrchestrator()
            _synth_pf = _orch_for_synth._build_policy_control_plane_feedback(
                pipeline_id="od_spectral_retrieval_pipeline",
                query_mode=_query_mode_default,
                retrieval_policy=_synth_rp,
                policy_outcome=None,
                policy_benchmark=_policy_benchmark,
            )
            # Each rehydrated trace shares the same synthesized policy_feedback
            # because the underlying policy_benchmark IS cumulative (the
            # orchestrator updates it per-trade). The downstream
            # benchmark_suite only uses bucket_policy_feedbacks[-1] anyway.
            bucket_policy_feedbacks = [_synth_pf] * len(bucket_execution_traces)
            bucket_query_modes = [_query_mode_default] * len(bucket_execution_traces)
            bucket_selected_modes = [_selected_mode] * len(bucket_execution_traces)
            bucket_last_retrieval_policy = _synth_rp
            print(
                f"  Phase 5 REHYDRATED from trace store: "
                f"{len(bucket_execution_traces)} traces loaded for "
                f"domain={bucket_tag}, selected_mode={_selected_mode!r}"
            )

    if bucket_policy_feedbacks and bucket_last_retrieval_policy is not None:
        # Build aggregated execution_trace from collected per-trade traces.
        # Per-stage wall-time median is more representative than the last
        # trade's stochastic timing. Carry stage ordering from the first
        # trace (pipeline DAG is fixed; per-stage order is deterministic).
        _ref_trace = bucket_execution_traces[0]
        _stage_order = [s["operator_id"] for s in _ref_trace.get("stages", [])]
        _stage_walltimes_by_op: dict[str, list[float]] = {sid: [] for sid in _stage_order}
        _stage_input_by_op: dict[str, list[int]] = {sid: [] for sid in _stage_order}
        _stage_output_by_op: dict[str, list[int]] = {sid: [] for sid in _stage_order}
        for _tr in bucket_execution_traces:
            for _stg in _tr.get("stages", []):
                _op = _stg["operator_id"]
                if _op in _stage_walltimes_by_op:
                    _stage_walltimes_by_op[_op].append(float(_stg.get("wall_time_ms", 0.0)))
                    _stage_input_by_op[_op].append(int(_stg.get("input_size", 0)))
                    _stage_output_by_op[_op].append(int(_stg.get("output_size", 0)))
        def _median(xs: list[float]) -> float:
            if not xs:
                return 0.0
            ys = sorted(xs)
            n = len(ys)
            return ys[n // 2] if n % 2 == 1 else (ys[n // 2 - 1] + ys[n // 2]) / 2.0
        _aggregated_stages = []
        for _idx, _sid in enumerate(_stage_order, start=1):
            _aggregated_stages.append({
                "stage": _idx,
                "operator_id": _sid,
                "wall_time_ms": round(_median(_stage_walltimes_by_op[_sid]), 3),
                "input_size": int(_median(_stage_input_by_op[_sid])),
                "output_size": int(_median(_stage_output_by_op[_sid])),
                "status": "success",
            })
        _aggregated_total_ms = round(sum(s["wall_time_ms"] for s in _aggregated_stages), 3)
        aggregated_trace = {
            "pipeline_id": _ref_trace.get("pipeline_id", "od_spectral_retrieval_pipeline"),
            "stages": _aggregated_stages,
            "total_wall_time_ms": _aggregated_total_ms,
            "bucket_trade_count": len(bucket_execution_traces),
            "aggregation": "per-stage wall_time_ms median across bucket",
        }

        # Reload cumulative policy benchmark (the orchestrator updated it
        # on every per-trade _record_retrieval_policy_outcome). Use the
        # global artifacts dir since that's where the orchestrator's
        # production-mode writes land (the orchestrator owns this file).
        from refrag_discovery.paths import ARTIFACTS_DIR as _ARTIFACTS_DIR
        _policy_benchmark_path = _ARTIFACTS_DIR / "retrieval_policy_benchmark.json"
        bucket_policy_benchmark = (
            json.loads(_policy_benchmark_path.read_text(encoding="utf-8"))
            if _policy_benchmark_path.exists()
            else {}
        )

        # Latest per-trade policy_feedback drives the per-operator
        # external metrics; the benchmark_suite uses cumulative state
        # internally so a single bucket-end call captures everything.
        latest_policy_feedback = bucket_policy_feedbacks[-1]

        # 1) operator_benchmark_suite — Phase 5 Evaluation capstone.
        # Same args as the prior per-trade firing, just moved out of the
        # latency-sensitive path. Writes to ARTIFACTS_DIR by default.
        #
        # Per-bucket runtime_feedback (the real fix for benchmark-suite
        # cell-invariance):
        # benchmark_suite mixes external_metrics_by_operator[op] into
        # overall_score / robustness_score / efficiency_score at 0.75 weight
        # (see _operator_report in operator_benchmark_suite.py L89-103). When
        # only retrieval_policy_learner gets feedback (the previous behaviour),
        # the other 7 operators fall back to pure manifest-property scores,
        # which are bucket-invariant — that's why every bucket's score_floor
        # came out identical at 0.8085. To make scores actually vary per
        # bucket, we compute per-operator runtime feedback from THIS bucket's
        # execution traces and pass it for every runtime operator:
        #   robustness_score = success_rate  (errors → score drops)
        #   efficiency_score = 1 / (1 + avg_latency_ms / 100)
        #                      (~0.9 at 10ms, ~0.5 at 100ms, ~0.09 at 1s)
        #   overall_score    = 0.5 * robustness + 0.5 * efficiency
        # retrieval_policy_learner keeps its richer policy-feedback shape
        # (mode metrics, reward trend, benchmark labels) — those fields
        # dominate the runtime_score blend for that operator and are real
        # signal vs invented numbers.
        _trace_runtime_feedback: dict[str, dict[str, float | int]] = {}
        for _op_id in _RUNTIME_OPERATOR_IDS:
            if _op_id == "operator_orchestrator":
                # The orchestrator isn't itself a pipeline stage, so it has no
                # stage_timings entry. Its per-bucket runtime feedback comes
                # from TRACE-LEVEL metrics (total wall time, convergence
                # iterations, discovery success rate) which are the
                # orchestrator's actual job signals.
                if not bucket_execution_traces:
                    continue
                _n_traces = len(bucket_execution_traces)
                _total_walltimes = [
                    float(_tr.get("total_wall_time_ms") or 0.0)
                    for _tr in bucket_execution_traces
                ]
                _avg_total = sum(_total_walltimes) / max(1, _n_traces)
                # Discovery success rate as robustness — the orchestrator's
                # job is to produce discoveries; a bucket where every trace
                # recorded a discovery scores 1.0; one with zero scores 0.
                _discoveries = sum(
                    1 for _tr in bucket_execution_traces
                    if _tr.get("discovery_recorded")
                )
                _robustness = _discoveries / _n_traces
                # Efficiency from total wall time per trade — same 100ms
                # baseline curve but on pipeline-total, not single-stage.
                _efficiency = 1.0 / (1.0 + _avg_total / 1000.0)
                # Convergence quality: fewer closed-loop iterations is better.
                # Use 1/(1+iter/3) so 0-1 iters score ~1.0, 3 iters ~0.5,
                # 10 iters ~0.23.
                _iters = [
                    int(_tr.get("closed_loop_iterations") or 0)
                    for _tr in bucket_execution_traces
                ]
                _avg_iters = sum(_iters) / max(1, _n_traces)
                _convergence = 1.0 / (1.0 + _avg_iters / 3.0)
                _overall = (_robustness + _efficiency + _convergence) / 3.0
                _trace_runtime_feedback[_op_id] = {
                    "overall_score": round(_overall, 6),
                    "robustness_score": round(_robustness, 6),
                    "efficiency_score": round(_efficiency, 6),
                    "selection_count": _n_traces,
                }
                continue
            _walls = _stage_walltimes_by_op.get(_op_id, [])
            if not _walls:
                continue
            _total = len(_walls)
            # success_count: a stage entry in bucket_execution_traces only
            # exists if the orchestrator successfully completed it; failures
            # would short-circuit the trace. So a stricter robustness_score
            # would need access to the trace's per-stage status field. We
            # already aggregated wall_times, so use trace-level error rate
            # as a proxy: count traces where this operator appears at all,
            # vs total traces.
            _ran_in_traces = sum(
                1 for _tr in bucket_execution_traces
                if any(s["operator_id"] == _op_id for s in _tr.get("stages", []))
            )
            _robustness = (_ran_in_traces / len(bucket_execution_traces)) if bucket_execution_traces else 0.0
            _avg_latency = sum(_walls) / max(1, _total)
            _efficiency = 1.0 / (1.0 + _avg_latency / 100.0)
            _overall = 0.5 * _robustness + 0.5 * _efficiency
            _trace_runtime_feedback[_op_id] = {
                "overall_score": round(_overall, 6),
                "robustness_score": round(_robustness, 6),
                "efficiency_score": round(_efficiency, 6),
                "selection_count": _total,
            }

        # Merge: trace-derived feedback for everyone, policy_feedback for
        # retrieval_policy_learner (richer signal there — preserve it).
        _external_metrics = dict(_trace_runtime_feedback)
        _external_metrics["retrieval_policy_learner"] = {
            **_trace_runtime_feedback.get("retrieval_policy_learner", {}),
            **latest_policy_feedback["operator_metrics"],
        }

        phase5_benchmark = call_control_plane_operator(
            "operator_benchmark_suite",
            {
                "operator_ids": _RUNTIME_OPERATOR_IDS,
                "task_suite_id": "od_spectral_retrieval_pipeline_runtime_stages",
                "benchmark_mode": "full",
                "generate_adversarial_tasks": False,
                "external_metrics_by_operator": _external_metrics,
                "artifacts_dir": _ARTIFACTS_DIR,
            },
        )
        (cp_dir / "phase5_operator_benchmark_suite.json").write_text(
            json.dumps(phase5_benchmark, indent=2), encoding="utf-8"
        )
        print(
            f"  Phase 5 benchmark_suite: "
            f"{len(phase5_benchmark.get('per_operator_reports', []))} operators evaluated, "
            f"regressions={len(phase5_benchmark.get('regressions_detected', []))}"
        )

        # 2) pipeline_performance_optimizer — Phase 5 Optimization capstone.
        phase5_optimizer = call_control_plane_operator(
            "pipeline_performance_optimizer",
            {
                "pipeline_id": "od_spectral_retrieval_pipeline",
                "pipeline_trace": aggregated_trace,
                "optimization_target": "balanced",
                "benchmark_state": bucket_policy_benchmark,
                "artifacts_dir": _ARTIFACTS_DIR,
            },
        )
        (cp_dir / "phase5_pipeline_performance_optimizer.json").write_text(
            json.dumps(phase5_optimizer, indent=2), encoding="utf-8"
        )
        _opt_rec = phase5_optimizer.get("retrieval_policy_recommendations", {})
        print(
            f"  Phase 5 pipeline_optimizer: "
            f"preferred_mode={_opt_rec.get('preferred_mode', 'n/a')}, "
            f"recommended_top_k={_opt_rec.get('recommended_top_k', 'n/a')}, "
            f"bottlenecks={len(phase5_optimizer.get('profiling_report', {}).get('bottlenecks', []))}"
        )

        # 3) exploration_policy_controller — Phase 5 Optimization capstone.
        #
        # Fix B-1 / arch Rule 10: controller OWNS its policy knobs. The adapter
        # passes the real per-bucket state (system_state, plan_id,
        # artifacts_dir) and DOES NOT inject exploration_budget,
        # strategic_priorities, or time_horizon. The controller's
        # COLD_START_EXPLORATION_BUDGET (Rule 5 "deterministic first") +
        # persisted state at ``artifacts/control_plane/exploration/<plan_id>.json``
        # are the source of truth. A prior version of this adapter dictated
        # max_runs=4 / compute_fraction=0.35 / risk_tolerance=0.55 — a
        # bare-handed Rule 10 violation that defeated the entire purpose of
        # having a learning controller. Removed.
        phase5_exploration = call_control_plane_operator(
            "exploration_policy_controller",
            {
                "system_state": latest_policy_feedback["exploration_state"],
                "plan_id": "od_spectral_retrieval_pipeline_retrieval_policy",
                "artifacts_dir": _ARTIFACTS_DIR,
            },
        )
        (cp_dir / "phase5_exploration_policy_controller.json").write_text(
            json.dumps(phase5_exploration, indent=2), encoding="utf-8"
        )
        print(
            f"  Phase 5 exploration_controller: "
            f"activities={len(phase5_exploration.get('exploration_plan', {}).get('activities', []))}, "
            f"policy_gaps={phase5_exploration.get('policy_gap_analysis', {}).get('policy_gap_count', 0)}"
        )

        # 4) retrieval-policy control-loop synthesis — moved here from
        # OperatorOrchestrator._persist_retrieval_policy_control_loop per
        # Rule 10 (orchestrator does not plan). Synthesises optimizer +
        # benchmark + exploration outputs into the control_loop_state.json
        # which the retrieval_policy_learner picks up on the NEXT bucket's
        # first invocation.
        _control_loop_path = synthesize_retrieval_policy_control_loop(
            pipeline_id="od_spectral_retrieval_pipeline",
            query_mode=bucket_query_modes[-1] if bucket_query_modes else "from_spectral_target",
            retrieval_policy=bucket_last_retrieval_policy,
            policy_benchmark=bucket_policy_benchmark,
            policy_feedback=latest_policy_feedback,
            optimizer_result=phase5_optimizer,
            benchmark_result=phase5_benchmark,
            exploration_result=phase5_exploration,
            artifacts_dir=_ARTIFACTS_DIR,
        )
        print(f"  Phase 5 retrieval_policy_control_loop synthesised: {_control_loop_path}")

        payload["control_plane_phases"].update({
            "phase5_operator_benchmark_suite": str(cp_dir / "phase5_operator_benchmark_suite.json"),
            "phase5_pipeline_performance_optimizer": str(cp_dir / "phase5_pipeline_performance_optimizer.json"),
            "phase5_exploration_policy_controller": str(cp_dir / "phase5_exploration_policy_controller.json"),
            "phase5_retrieval_policy_control_loop": str(_control_loop_path),
        })
        _atomic_write_summary(summary_path, payload)
    else:
        print(
            f"  Phase 5 SKIPPED: no per-trade policy_feedback collected "
            f"(new_results={len(new_results)}, "
            f"feedbacks={len(bucket_policy_feedbacks)})"
        )

    # ---- Phase 6 (arch §8): Governance Loop closure ----
    # Per arch §5: benchmark_suite → lifecycle_tracker → lineage_tracker →
    # promotion_recommender. The first three run per-pipeline inside the
    # orchestrator (Phase 1 wiring). promotion_recommender is the closing
    # call — evaluates each runtime operator's promotion readiness given
    # the accumulated lifecycle/lineage state.
    #
    # ``operator_graph_rewriter`` (Composition capstone, depth-4 in arch §6)
    # runs in ``analyze`` mode here — read-only, no approval token, no graph
    # mutation. The side-effecting modes (``propose_and_simulate``,
    # ``execute``) remain token-gated inside the operator itself per arch
    # Rule 6 ("Reversible Graph Modifications" — max 15% disruption per pass,
    # approval tokens required). analyze mode produces bottlenecks,
    # redundancies, friction points, and a health score against the current
    # dependency graph; that's pure structural diagnostic output, no rewrite.
    # Fix B: pass artifacts_dir=None so promotion_recommender's inner
    # lifecycle + lineage calls route through the arch §3.1 registry layout
    # (registry/lineage/<op>.json) — same convention the orchestrator uses
    # for production runs. Production adapter writes to global registry.
    promotions: dict[str, dict] = {}
    for _op in _RUNTIME_OPERATOR_IDS:
        promotions[_op] = call_control_plane_operator(
            "operator_promotion_recommender",
            {
                "operator_id": _op,
                "evaluation_window": "P30D",
                "include_schema_suggestions": True,
                "run_counterfactual": True,
                "artifacts_dir": None,
            },
        )
    print(f"  Phase 6 promotion_recommender: {len(promotions)} operators evaluated")
    for _op_id, _p in promotions.items():
        print(
            f"    {_op_id}: score={_p['promotion_score']}, "
            f"recommendation={_p['recommendation']}, "
            f"blocking={len(_p.get('blocking_issues', []))}"
        )
    (cp_dir / "phase6_promotions.json").write_text(
        json.dumps(promotions, indent=2), encoding="utf-8"
    )

    # Phase 6b: operator_graph_rewriter in analyze mode. Loads the materialised
    # dependency graph at registry/dependency_graph/graph.json (arch §3.1) and
    # converts the {upstream, downstream} adjacency dict into the {nodes,
    # edges} shape the operator expects. performance_history is populated from
    # the Phase 5 outputs written earlier this run:
    #   stage_scores       <- phase5_benchmark.leaderboard.rankings[].overall_score
    #   stage_latencies_ms <- phase5_optimizer.profiling_report.stage_timings
    #                         (summed per operator across closed-loop iterations)
    # With real perf data the analyzer can surface true bottlenecks and friction
    # points instead of only structural fan-out.
    _dep_graph_path = REFRAG_ROOT / "registry" / "dependency_graph" / "graph.json"
    if _dep_graph_path.exists():
        _dep_graph = json.loads(_dep_graph_path.read_text(encoding="utf-8"))
        _ops = _dep_graph.get("operators", {})
        _nodes = [{"id": op_id} for op_id in _ops.keys()]
        _edges = [
            {"source": op_id, "target": down_id}
            for op_id, info in _ops.items()
            for down_id in info.get("downstream", [])
        ]
        _stage_scores: dict[str, float] = {}
        _bench_path = cp_dir / "phase5_operator_benchmark_suite.json"
        if _bench_path.exists():
            try:
                _bench = json.loads(_bench_path.read_text(encoding="utf-8"))
                for _row in _bench.get("leaderboard", {}).get("rankings", []):
                    _op_id = _row.get("operator_id")
                    _score = _row.get("overall_score")
                    if _op_id and _score is not None:
                        _stage_scores[_op_id] = float(_score)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        _stage_latencies_ms: dict[str, float] = {}
        _opt_path = cp_dir / "phase5_pipeline_performance_optimizer.json"
        if _opt_path.exists():
            try:
                _opt = json.loads(_opt_path.read_text(encoding="utf-8"))
                for _t in _opt.get("profiling_report", {}).get("stage_timings", []):
                    _op_id = _t.get("operator_id")
                    _wt = _t.get("wall_time_ms")
                    if _op_id and _wt is not None:
                        _stage_latencies_ms[_op_id] = (
                            _stage_latencies_ms.get(_op_id, 0.0) + float(_wt)
                        )
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        graph_analysis = call_control_plane_operator(
            "operator_graph_rewriter",
            {
                "operator_graph": {"nodes": _nodes, "edges": _edges},
                "performance_history": {
                    "stage_scores": _stage_scores,
                    "stage_latencies_ms": _stage_latencies_ms,
                },
                "rewrite_mode": "analyze",
                "rewrite_budget": 3,
            },
        )
        analysis_block = graph_analysis.get("analysis", {}) if isinstance(graph_analysis, dict) else {}
        print(
            f"  Phase 6b graph_rewriter (analyze): "
            f"health={analysis_block.get('health_score', 'n/a')}, "
            f"bottlenecks={len(analysis_block.get('bottlenecks', []))}, "
            f"redundancies={len(analysis_block.get('redundancies', []))}, "
            f"friction={len(analysis_block.get('friction_points', []))}"
        )
        (cp_dir / "phase6_graph_rewriter_analysis.json").write_text(
            json.dumps(graph_analysis, indent=2), encoding="utf-8"
        )
    else:
        print(f"  Phase 6b graph_rewriter SKIPPED: {_dep_graph_path} not found")

    # Final write with Phase 4 + Phase 6 paths attached.
    _phase_paths = {
        "phase4_gap_finder": str(cp_dir / "phase4_gap_finder.json"),
        "phase4_manifest_synthesizer": str(cp_dir / "phase4_manifest_synthesizer.json"),
        "phase4_cross_domain_transfer": str(cp_dir / "phase4_cross_domain_transfer.json"),
        "phase6_promotions": str(cp_dir / "phase6_promotions.json"),
    }
    if (cp_dir / "phase6_graph_rewriter_analysis.json").exists():
        _phase_paths["phase6_graph_rewriter_analysis"] = str(
            cp_dir / "phase6_graph_rewriter_analysis.json"
        )
    payload["control_plane_phases"].update(_phase_paths)
    _atomic_write_summary(summary_path, payload)

    print(f"\nDone in {time.time()-t_start:.1f}s")
    print(f"  processed this session : {len(new_results)}")
    if args.resume:
        print(f"  skipped (already done) : {n_skipped_already_done}")
    print(f"  skipped (no bin coverage): {n_skipped_no_coverage}")
    print(f"  skipped (too short, <{min_returns} returns; "
          f"derived from rec.window_size={rec_chunker['window_size']}): "
          f"{n_skipped_too_short}")
    print(f"  errors: {n_errors}")
    print(f"  summary (merged total = {payload['processed']}): {summary_path}")
    print(f"  per-run discoveries: {REFRAG_ROOT}\\artifacts\\discoveries\\{{run_id}}.json")


if __name__ == "__main__":
    main()
