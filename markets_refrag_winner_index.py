"""Layer 1 refrag pipeline applied to top winners from the 67k tape — build
the indexed winner library and analyze its structure.

Data source note: the canonical "winning json" (oracle_winner_trade_list.json)
references trades from May 23 (the live mock RT epoch), but our bin files
only cover ~May 7-13. We instead index winners from the 67k tape
(_analysis_historical_rt_trade_shapes_20260523/per_trade.csv), filtered by
net_bps > WIN_NET_BPS_THRESHOLD. These trades all sit within bin coverage by
construction. When the bin files are refreshed past May 23, the winning json
becomes usable too — the pipeline is one CSV_PATH flip away.

Composition (per `od_refrag_adapter.py` template, but for Markets):

    per_trade.csv (top winners filter)
        │
        ├─→ MarketChunker.chunk(bars)              [markets_adapter]
        ├─→ MarketChunkEncoder.encode(chunks)      [markets_adapter, 64-dim vectors]
        ├─→ refrag_core.Chunk wrapping              [stable chunk_ids]
        ├─→ refrag_core.ChunkEmbeddingCache.put()   [sqlite persistence]
        ├─→ refrag_core.VectorIndex.add()           [FAISS if installed, python fallback]
        ├─→ MarketChunkEncoder.reduce(target=12)    [PCA dim reduction]
        └─→ refrag_core.SimilaritySelector          [top-K retrieval for analysis]

The pipeline runs in-process (no MCP server required). The persistent artifacts
(index + cache) can be reused for live in-flight similarity queries later.

Outputs:
  _winner_index.json                  refrag VectorIndex (persisted)
  _winner_embeddings.cache.sqlite     refrag ChunkEmbeddingCache (per-chunk_id)
  _winner_chunks_projected.csv        12-dim PCA projection + metadata for clustering
  _winner_archetype_report.txt        intra-context similarity + cross-cluster analysis
  _winner_index_metadata.json         maps VectorIndex row → (asset, venue, source_id, chunk_idx, context_key)
"""

from __future__ import annotations

import bisect
import csv
import hashlib
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

# Import refrag_core
REFRAG_ROOT = Path(r"E:\refrag")
sys.path.insert(0, str(REFRAG_ROOT))

from refrag_core import (  # noqa: E402
    Chunk as RefragChunk,
    ChunkEmbeddingCache,
    SimilaritySelector,
    VectorIndex,
    cosine,
)

from markets_adapter import MarketBar, MarketChunker, MarketChunkEncoder  # noqa: E402
from phase1_5_evaluator import load_bars  # noqa: E402


CSV_PATH = Path(r"E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv")
WIN_NET_BPS_THRESHOLD = 30.0  # net_bps above this → "high-conviction winner" for indexing
ROOT = Path(__file__).resolve().parent

OUT_INDEX = ROOT / "_winner_index.json"
OUT_CACHE = ROOT / "_winner_embeddings.cache.sqlite"
OUT_PROJ_CSV = ROOT / "_winner_chunks_projected.csv"
OUT_META = ROOT / "_winner_index_metadata.json"
OUT_REPORT = ROOT / "_winner_archetype_report.txt"

BIN_FILES = {
    ("BTC", "Coinbase"): ROOT / "btc_coinbase_bins.json",
    ("BTC", "Kraken"): ROOT / "btc_kraken_bins.json",
    ("BTC", "Bybit"): ROOT / "btc_bybit_perp_bins.json",
    ("ETH", "Coinbase"): ROOT / "eth_coinbase_bins.json",
    ("ETH", "Kraken"): ROOT / "eth_kraken_bins.json",
    ("ETH", "Bybit"): ROOT / "eth_bybit_perp_bins.json",
}
VENUE_CANON = {"bybit": "Bybit", "coinbase": "Coinbase", "kraken": "Kraken"}

MIN_BARS = 16
D_ENC = 64
TARGET_DIM = 12


def _slice_bars_by_ts(bars, ts_start, ts_end):
    if not bars:
        return []
    ts_list = [b.ts for b in bars]
    i_start = bisect.bisect_left(ts_list, ts_start)
    i_end = bisect.bisect_right(ts_list, ts_end)
    return bars[i_start:i_end]


def _parse_float(v):
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_winning_entries() -> list[dict]:
    """Load top winners from the 67k tape (per_trade.csv).
    Filter: net_bps > WIN_NET_BPS_THRESHOLD and (asset, venue) in BIN_FILES.
    Dedupe by (asset, venue, entry_ts, exit_ts) to avoid duplicate bar-slice
    indexing — multiple family variants on the same window collapse to one
    representative."""
    if not CSV_PATH.exists():
        sys.exit(f"MISSING: {CSV_PATH}")
    records_raw: list[dict] = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            net_bps = _parse_float(r.get("net_bps"))
            entry_ts = _parse_float(r.get("entry_ts"))
            exit_ts = _parse_float(r.get("exit_ts"))
            if net_bps is None or entry_ts is None or exit_ts is None:
                continue
            if net_bps < WIN_NET_BPS_THRESHOLD:
                continue
            asset = r.get("asset") or ""
            venue = r.get("venue") or ""
            if (asset, venue) not in BIN_FILES:
                continue
            records_raw.append({
                "trade_id": r.get("id") or "",
                "asset": asset, "venue": venue,
                "side": r.get("side") or "",
                "strategy_id": r.get("strategy_id") or "",
                "entry_ts": entry_ts, "exit_ts": exit_ts,
                "net_bps": net_bps,
                "hold_min": _parse_float(r.get("hold_min")) or 0.0,
            })
    print(f"  loaded {len(records_raw)} trades with net_bps > {WIN_NET_BPS_THRESHOLD}", flush=True)

    # Dedupe by (asset, venue, entry_ts, exit_ts) — collapse family variants
    by_slice: dict = defaultdict(list)
    for r in records_raw:
        key = (r["asset"], r["venue"], r["entry_ts"], r["exit_ts"])
        by_slice[key].append(r)
    records: list[dict] = []
    for key, group in by_slice.items():
        # Take median net_bps across family variants; record n_sources
        group.sort(key=lambda x: x["strategy_id"])
        rep = group[0]
        net_bps_vals = [g["net_bps"] for g in group]
        records.append({
            "source_id": f"{rep['asset']}|{rep['venue']}|{int(rep['entry_ts'])}|{int(rep['exit_ts'])}",
            "asset": rep["asset"], "venue": rep["venue"], "side": rep["side"],
            "entry_ts": rep["entry_ts"], "exit_ts": rep["exit_ts"],
            "horizon_min": rep["hold_min"],
            # Use family as a coarse context_key; canonical is unavailable in csv schema
            "context_key": f"{rep['strategy_id']}|{rep['asset']}|{rep['venue']}|{rep['side']}",
            "entry_chunk_id": "",
            "net_bps_median": statistics.median(net_bps_vals),
            "net_bps_min": min(net_bps_vals),
            "net_bps_max": max(net_bps_vals),
            "n_sources": len(group),
        })
    print(f"  deduped to {len(records)} unique bar-slices", flush=True)
    return records


def make_chunk_id(source_id: str, chunk_idx: int) -> str:
    """Stable chunk ID. Mirrors refrag_core.chunking.make_chunk_id pattern but
    uses (source_id, chunk_idx) since we're not in token-mode."""
    raw = f"{source_id}|{chunk_idx}|marketchunk".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def main():
    print(f"Loading {CSV_PATH.name} (top winners filter) ...", flush=True)
    records = parse_winning_entries()
    print(f"  parsed {len(records)} winner records", flush=True)

    # Group by (asset, venue) for efficient bar loading
    by_av: dict = defaultdict(list)
    for r in records:
        by_av[(r["asset"], r["venue"])].append(r)
    print(f"  groups: { {f'{a}/{v}': len(rs) for (a, v), rs in by_av.items()} }",
          flush=True)

    chunker = MarketChunker(max_window_size=256, stride=128, min_segment=MIN_BARS, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=D_ENC, compute_hawkes=False, compute_hurst=False)

    # Initialize refrag primitives
    if OUT_CACHE.exists():
        OUT_CACHE.unlink()  # fresh build
    cache = ChunkEmbeddingCache(str(OUT_CACHE))
    index = VectorIndex(dim=D_ENC, backend="auto")
    print(f"  refrag VectorIndex backend: {index.backend}", flush=True)

    # Index metadata: row_idx -> {source_id, chunk_idx, ...}
    index_meta: list[dict] = []
    all_embeds: list[list[float]] = []   # for global PCA reduction
    skipped_too_short = 0
    skipped_no_bars = 0

    print("\nChunking + encoding per (asset, venue) ...", flush=True)
    t_start = time.time()
    for (asset, venue), group in by_av.items():
        bin_path = BIN_FILES.get((asset, venue))
        if bin_path is None or not bin_path.exists():
            print(f"  SKIP {asset}/{venue}: no bin file", flush=True)
            continue
        print(f"  Loading {asset}/{venue} bars from {bin_path.name} ...", flush=True)
        t0 = time.time()
        bars = load_bars(str(bin_path))
        print(f"    {len(bars)} bars loaded in {time.time()-t0:.1f}s", flush=True)

        for rec in group:
            sliced = _slice_bars_by_ts(bars, rec["entry_ts"], rec["exit_ts"])
            if len(sliced) < MIN_BARS:
                skipped_too_short += 1
                continue
            try:
                market_chunks = chunker.chunk(rec["source_id"], sliced, multi_signal=True)
            except Exception as e:
                print(f"    chunk error {rec['source_id']}: {e}", flush=True)
                continue
            if not market_chunks:
                skipped_too_short += 1
                continue
            try:
                embeds = encoder.encode(market_chunks)
            except Exception as e:
                print(f"    encode error {rec['source_id']}: {e}", flush=True)
                continue
            if not embeds:
                continue

            # Add each chunk to refrag primitives + record metadata
            for ci, emb in enumerate(embeds):
                if len(emb) != D_ENC:
                    continue
                chunk_id = make_chunk_id(rec["source_id"], ci)
                # refrag_core.ChunkEmbeddingCache: per-chunk_id sqlite store
                cache.put(chunk_id, emb)
                # refrag_core.VectorIndex: similarity index
                index.add([emb])
                # metadata for this row
                index_meta.append({
                    "row_idx": len(index_meta),
                    "chunk_id": chunk_id,
                    "source_id": rec["source_id"],
                    "asset": rec["asset"], "venue": rec["venue"], "side": rec["side"],
                    "context_key": rec["context_key"],
                    "chunk_idx": ci,
                    "n_chunks_in_trade": len(embeds),
                    "entry_ts": rec["entry_ts"], "horizon_min": rec["horizon_min"],
                    "net_bps_median": rec["net_bps_median"],
                    "n_sources": rec["n_sources"],
                })
                all_embeds.append(emb)

    print(f"\nIndexing complete in {time.time()-t_start:.1f}s", flush=True)
    print(f"  total chunks indexed: {len(all_embeds)}", flush=True)
    print(f"  skipped too short: {skipped_too_short}", flush=True)
    print(f"  unique sources: {len(set(m['source_id'] for m in index_meta))}", flush=True)

    if not all_embeds:
        sys.exit("no chunks indexed")

    # Persist refrag index + metadata
    print(f"\nSaving artifacts ...", flush=True)
    index_path = index.save(str(OUT_INDEX))
    OUT_META.write_text(json.dumps(index_meta, indent=1), encoding="utf-8")
    print(f"  VectorIndex saved: {index_path}", flush=True)
    print(f"  Cache: {OUT_CACHE}", flush=True)
    print(f"  Metadata: {OUT_META}", flush=True)

    # PCA-reduce all embeddings via MarketChunkEncoder.reduce()
    print(f"\nProjecting {len(all_embeds)} embeddings to {TARGET_DIM}-d via PCA ...", flush=True)
    t0 = time.time()
    projected = MarketChunkEncoder.reduce(all_embeds, target_dim=TARGET_DIM, method="pca")
    print(f"  PCA done in {time.time()-t0:.1f}s", flush=True)

    # Write projected CSV (PCA coords + metadata for downstream clustering/viz)
    print(f"  Writing {OUT_PROJ_CSV.name} ...", flush=True)
    with OUT_PROJ_CSV.open("w", encoding="utf-8", newline="") as f:
        pca_cols = [f"pca_{i}" for i in range(TARGET_DIM)]
        fields = ["row_idx", "chunk_id", "source_id", "asset", "venue", "side",
                  "context_key", "chunk_idx", "n_chunks_in_trade",
                  "entry_ts", "horizon_min", "net_bps_median", "n_sources"] + pca_cols
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for meta, proj in zip(index_meta, projected):
            row = {**meta}
            for i, c in enumerate(pca_cols):
                row[c] = proj[i] if i < len(proj) else 0.0
            w.writerow(row)

    # ANALYSIS
    print(f"\nRunning analysis ...", flush=True)
    selector = SimilaritySelector()
    with OUT_REPORT.open("w", encoding="utf-8") as f:
        f.write("Refrag Layer 1 winner-library analysis\n")
        f.write("=" * 100 + "\n")
        f.write(f"Source: {CSV_PATH}  (net_bps > {WIN_NET_BPS_THRESHOLD})\n")
        f.write(f"Records: {len(records)} deduped winning trades\n")
        f.write(f"Chunks indexed: {len(all_embeds)}  (skipped {skipped_too_short} too short)\n")
        f.write(f"Unique trades: {len(set(m['source_id'] for m in index_meta))}\n")
        f.write(f"Vector index backend: {index.backend}\n")
        f.write(f"Embedding dim: {D_ENC} → projected to {TARGET_DIM}-d via PCA\n\n")

        # Per-context-key density (how many chunks per context)
        by_context: dict = defaultdict(list)
        for i, m in enumerate(index_meta):
            by_context[m["context_key"]].append(i)
        f.write("PER-CONTEXT CHUNK DENSITY (top 20 by chunk count)\n")
        f.write("=" * 100 + "\n")
        f.write(f"\n  {'context_key':<60s}  {'chunks':>7s}  {'trades':>7s}  {'avg_n_chunks':>12s}\n")
        f.write("  " + "-" * 96 + "\n")
        ctx_sorted = sorted(by_context.items(), key=lambda kv: -len(kv[1]))
        for ctx, idxs in ctx_sorted[:20]:
            trades = {index_meta[i]["source_id"] for i in idxs}
            avg_n = len(idxs) / max(1, len(trades))
            ctx_short = ctx[:60]
            f.write(f"  {ctx_short:<60s}  {len(idxs):>7d}  {len(trades):>7d}  {avg_n:>12.2f}\n")

        # Per (asset, venue, side) — winner prototype = mean projected vector
        f.write(f"\n\nWINNER PROTOTYPES (per asset/venue/side, mean PCA coords)\n")
        f.write("=" * 100 + "\n")
        by_avs: dict = defaultdict(list)
        for i, m in enumerate(index_meta):
            by_avs[(m["asset"], m["venue"], m["side"])].append(projected[i])
        f.write(f"\n  {'asset/venue/side':<25s}  {'n':>5s}  {'pca_0':>8s}  {'pca_1':>8s}  {'pca_2':>8s}  {'pca_3':>8s}\n")
        f.write("  " + "-" * 75 + "\n")
        for (a, v, s), vecs in sorted(by_avs.items()):
            mean_vec = [statistics.mean(col) for col in zip(*vecs)]
            f.write(f"  {a}/{v}/{s:<8s}  {len(vecs):>5d}  "
                    f"{mean_vec[0]:>+8.4f}  {mean_vec[1]:>+8.4f}  "
                    f"{mean_vec[2]:>+8.4f}  {mean_vec[3]:>+8.4f}\n")

        # Intra-context cosine similarity (cohesion measure per context)
        f.write(f"\n\nINTRA-CONTEXT COSINE SIMILARITY (mean within-context pairwise)\n")
        f.write("=" * 100 + "\n")
        f.write("(higher = tighter cluster; ranges -1 to 1)\n\n")
        f.write(f"  {'context_key':<60s}  {'n_chunks':>9s}  {'mean_cos':>9s}  {'min_cos':>8s}  {'max_cos':>8s}\n")
        f.write("  " + "-" * 100 + "\n")
        ctx_stats = []
        for ctx, idxs in ctx_sorted[:30]:
            if len(idxs) < 4:
                continue
            # Sample up to 20 chunks for pairwise (cap O(n^2))
            sample_idxs = idxs[:20] if len(idxs) > 20 else idxs
            sims = []
            for i in range(len(sample_idxs)):
                for j in range(i + 1, len(sample_idxs)):
                    sims.append(cosine(all_embeds[sample_idxs[i]], all_embeds[sample_idxs[j]]))
            if sims:
                ctx_stats.append({
                    "ctx": ctx,
                    "n_chunks": len(idxs),
                    "mean": statistics.mean(sims),
                    "min": min(sims),
                    "max": max(sims),
                })
        ctx_stats.sort(key=lambda r: -r["mean"])
        for r in ctx_stats[:25]:
            ctx_short = r["ctx"][:60]
            f.write(f"  {ctx_short:<60s}  {r['n_chunks']:>9d}  "
                    f"{r['mean']:>+9.3f}  {r['min']:>+8.3f}  {r['max']:>+8.3f}\n")

        # Top retrieval pairs — find chunks from DIFFERENT context_keys that are very similar
        # (cross-context resonance: a single archetype that spans contexts)
        f.write(f"\n\nCROSS-CONTEXT TOP-K NEIGHBORS (top 30 cross-context similar pairs)\n")
        f.write("=" * 100 + "\n")
        f.write("(uses refrag_core.SimilaritySelector — these chunks are similar across different contexts,\n")
        f.write(" so they may represent a SHARED archetype not visible at context-key level)\n\n")
        # Sample 200 representative chunks for cross-context search
        sample_size = min(200, len(all_embeds))
        sample_idxs = list(range(0, len(all_embeds), max(1, len(all_embeds) // sample_size)))[:sample_size]
        cross_pairs = []
        for qi in sample_idxs:
            top = selector.select(all_embeds[qi], all_embeds, budget=4)
            for hit in top:
                if hit == qi:
                    continue
                if index_meta[hit]["context_key"] == index_meta[qi]["context_key"]:
                    continue
                sim = cosine(all_embeds[qi], all_embeds[hit])
                if sim > 0.95:
                    cross_pairs.append((qi, hit, sim))
        # Dedupe (smaller idx first)
        seen = set()
        unique_pairs = []
        for qi, hit, sim in cross_pairs:
            key = (min(qi, hit), max(qi, hit))
            if key in seen:
                continue
            seen.add(key)
            unique_pairs.append((qi, hit, sim))
        unique_pairs.sort(key=lambda r: -r[2])
        for qi, hit, sim in unique_pairs[:30]:
            mi = index_meta[qi]
            mj = index_meta[hit]
            f.write(f"  cos={sim:+.4f}\n")
            f.write(f"    A: {mi['asset']}/{mi['venue']}/{mi['side']:<5s}  ctx={mi['context_key'][:55]}\n")
            f.write(f"    B: {mj['asset']}/{mj['venue']}/{mj['side']:<5s}  ctx={mj['context_key'][:55]}\n")

        # Final summary
        f.write(f"\n\nSUMMARY\n")
        f.write("=" * 100 + "\n")
        n_unique_trades = len(set(m['source_id'] for m in index_meta))
        f.write(f"  total chunks indexed (refrag VectorIndex): {len(all_embeds)}\n")
        f.write(f"  unique winner trades: {n_unique_trades}\n")
        f.write(f"  context_keys: {len(by_context)}\n")
        f.write(f"  (asset, venue, side) cells: {len(by_avs)}\n")
        f.write(f"  tightest context cluster: mean_cos={ctx_stats[0]['mean']:.3f} on '{ctx_stats[0]['ctx'][:50]}'\n" if ctx_stats else "  no context clusters computed\n")
        f.write(f"  cross-context near-identical pairs (cos>0.95): {len(unique_pairs)}\n")
        f.write(f"\n  artifacts:\n")
        f.write(f"    {OUT_INDEX.name}            (refrag VectorIndex)\n")
        f.write(f"    {OUT_CACHE.name}            (refrag ChunkEmbeddingCache, sqlite)\n")
        f.write(f"    {OUT_PROJ_CSV.name}         ({TARGET_DIM}-d PCA + metadata, for clustering/viz)\n")
        f.write(f"    {OUT_META.name}             (VectorIndex row → metadata map)\n")

    print(f"\nDone.", flush=True)
    print(f"  index:    {OUT_INDEX}", flush=True)
    print(f"  cache:    {OUT_CACHE}", flush=True)
    print(f"  proj csv: {OUT_PROJ_CSV}", flush=True)
    print(f"  meta:     {OUT_META}", flush=True)
    print(f"  report:   {OUT_REPORT}", flush=True)


if __name__ == "__main__":
    main()
