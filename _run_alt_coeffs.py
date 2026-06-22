"""_run_alt_coeffs.py — in-container 128-dim coeff discovery for the alt cells (SOL/DOGE/XRP),
on 1-SECOND bins, using the DETERMINISTIC refrag pipeline that produced the BTC/ETH coeffs.

Why this can run here (S38 finding): the committed BTC/ETH 128-dim coeffs have unit-L2 norm and
are all non-negative — the signature of the DETERMINISTIC decoder tier (OperatorDecoder.prefill =
mean of spectral-magnitude embeds, refine = L2-normalize), NOT a trained FNO. That whole pipeline
is vendored in odcore/od_refrag_adapter.py, so no box / no torch / no checkpoint is needed.

Pipeline = the cs100_v2 config verbatim (from _markets_gate_v2):
  pre-entry 30-min window of 1-sec mid -> log-returns
  -> SpectralChunker(window=192, stride=16)
  -> SpectralChunkEncoder(d_enc=128)
  -> OperatorQuery.from_spectral_target([0.1, 0.25], energy=1.0)
  -> top_k=8 retrieval (cosine), mixed prefill (expand_budget=4 chunks expanded to raw values)
  -> OperatorDecoder.prefill -> refine(8)  => 128-dim unit-L2 operator_coefficients

PER CELL, never pooled. Winners ranked by net_bps desc, cap 100/cell (Greg: "100 at a time").
Leakage-safe: the window ends AT decision_ts (pre-entry only).

Out: _alt_labels/coeffs/alt_coeff_index.json.gz  (LEAN: coef only — the committed fingerprint;
     same schema as fingerprint_dataset coeff_index; lineage="onset_1s") + per-cell counts to stdout.
     With --save-embeds: ALSO _alt_labels/coeffs/alt_train_pairs.json.gz (gitignored) carrying the FNO
     training pairs X=prefill_embeds + prefill_mask, y=coef (for SageMaker/EC2 GPU FNO training, aws/train_fno/).

Usage:  python _run_alt_coeffs.py [--cap 100] [--cells doge_bybit_perp_buy,...] [--save-embeds]
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
from pathlib import Path

import numpy as np

from odcore.io import load_bins
from odcore.od_refrag_adapter import (SpectralChunker, SpectralChunkEncoder,
                                      OperatorQuery, OperatorDecoder)

PRE_ENTRY_S = 30 * 60
CHUNKER = dict(window_size=192, stride=16)
D_ENC = 128
TARGET_FREQS = [0.1, 0.25]
TARGET_ENERGY = 1.0
TOP_K = 8
EXPAND_BUDGET = 4
EXPAND_VALUES = 16          # raw values per expanded chunk (od_refrag e2e truncation)
REFINE_ITERS = 8
LABELS = Path("_alt_labels")
OUT = LABELS / "coeffs"

# bins file per coin/venue (1-second)
BINS = {"bybit_perp": "realbins/{coin}_bybit_perp_bins.json"}


def _cos(a, b):
    a = np.asarray(a); b = np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def coef_for_window(lr: list[float]):
    """The cs100_v2 deterministic pipeline on one pre-entry window's log-returns.

    Returns (coef, prefill, mask) or None:
      coef    = 128-dim unit-L2 operator_coefficients (the fingerprint y)
      prefill = the mixed prefill embeds the decoder ingests (the FNO training X) — list of 128-dim rows
      mask    = the prefill mask (list[int], 1 per row)
    The deterministic decoder computes coef = refine(prefill(prefill, mask)) = L2-normalize(masked-mean).
    Persisting (prefill, mask) gives the FNO the SAME input the deterministic decoder sees, so the learned
    map is a drop-in replacement for prefill->refine on identical inputs (manifest operator_decoder.v2).
    """
    if len(lr) < CHUNKER["window_size"]:
        return None
    chunker = SpectralChunker(**CHUNKER)
    encoder = SpectralChunkEncoder(d_enc=D_ENC)
    chunks = chunker.chunk("alt", lr)
    if not chunks:
        return None
    embeds = encoder.encode(chunks)
    q = OperatorQuery(d_enc=D_ENC).from_spectral_target(TARGET_FREQS, TARGET_ENERGY)
    scores = sorted(((i, _cos(q, e)) for i, e in enumerate(embeds)), key=lambda x: -x[1])
    hits = scores[:TOP_K]
    # mixed prefill: top EXPAND_BUDGET expanded to raw values, rest compressed (od_refrag e2e)
    prefill, mask = [], []
    for rank, (idx, _) in enumerate(hits):
        if rank < EXPAND_BUDGET:
            for v in chunks[idx].values[:EXPAND_VALUES]:
                prefill.append([v] + [0.0] * (D_ENC - 1)); mask.append(1)
        else:
            prefill.append([float(x) for x in embeds[idx]]); mask.append(1)
    dec = OperatorDecoder()
    coef = dec.refine(dec.prefill(prefill, mask), n_iterations=REFINE_ITERS)
    if len(coef) != D_ENC:
        return None
    return [float(x) for x in coef], prefill, mask


def run_cell(cell: str, cap: int, save_embeds: bool = False) -> dict:
    fp = LABELS / f"{cell}_winner_onsets.json"
    if not fp.exists():
        print(f"  [{cell}] no winner_onsets file", flush=True)
        return {}
    winners = json.load(open(fp))
    winners.sort(key=lambda r: -float(r.get("net_bps") or 0))   # strongest first
    coin = cell.split("_")[0]
    venue = "bybit_perp"
    bs = load_bins(BINS[venue].format(coin=coin))
    ts = bs.ts; mid = bs.mid
    out = {}
    n_done = n_skip = 0
    for w in winners:
        if n_done >= cap:
            break
        dts = float(w["decision_ts_utc"])
        i = int(np.searchsorted(ts, dts, side="right"))
        lo = int(np.searchsorted(ts, dts - PRE_ENTRY_S, side="left"))
        m = mid[lo:i]; m = m[m > 0]
        if m.size < CHUNKER["window_size"] + 1:
            n_skip += 1; continue
        lr = np.diff(np.log(m)).tolist()
        res = coef_for_window(lr)
        if res is None:
            n_skip += 1; continue
        coef, prefill, mask = res
        rec = {"coef": coef, "label": "win", "cell": cell,
               "lineage": "onset_1s", "net_bps": w.get("net_bps")}
        if save_embeds:                       # the FNO training X (separate, gitignored output)
            rec["prefill_embeds"] = prefill
            rec["prefill_mask"] = mask
        out[w["source_id"]] = rec
        n_done += 1
    print(f"  [{cell}] coeffs={n_done} skipped={n_skip} (cap {cap})", flush=True)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cap", type=int, default=100)
    p.add_argument("--cells", default="", help="comma list; default = all alt *_winner_onsets")
    p.add_argument("--save-embeds", action="store_true",
                   help="also write the FNO training pairs (X=prefill_embeds, y=coef) to "
                        "alt_train_pairs.json.gz (gitignored; for SageMaker/EC2 GPU FNO training)")
    args = p.parse_args()

    if args.cells:
        cells = [c.strip() for c in args.cells.split(",") if c.strip()]
    else:
        cells = sorted(Path(f).name.replace("_winner_onsets.json", "")
                       for f in glob.glob(str(LABELS / "*_winner_onsets.json")))
    print(f"alt coeff discovery (1-sec, deterministic cs100_v2 pipeline, d_enc={D_ENC}); cells={cells}",
          flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    index = {}
    for cell in cells:
        index.update(run_cell(cell, args.cap, save_embeds=args.save_embeds))

    pipeline = {"chunker": CHUNKER, "d_enc": D_ENC, "top_k": TOP_K,
                "expand_budget": EXPAND_BUDGET, "query": TARGET_FREQS,
                "bar_resolution": "1s", "decoder": "deterministic_stub"}

    # Lean committed index = the fingerprint (coef only). Strip any embeds so git stays small.
    lean = {sid: {k: v for k, v in rec.items() if k not in ("prefill_embeds", "prefill_mask")}
            for sid, rec in index.items()}
    blob = {"schema": "fingerprint_coeff_index_v1", "dim": D_ENC, "lineages": ["onset_1s"],
            "pipeline": pipeline, "n": len(lean), "by_source_id": lean}
    out_fp = OUT / "alt_coeff_index.json.gz"
    with gzip.open(out_fp, "wt", encoding="utf-8") as f:
        json.dump(blob, f)
    print(f"\nwrote {len(lean)} alt coeffs -> {out_fp}", flush=True)

    # Training pairs (X+y) -> separate gitignored artifact bound for S3/SageMaker (the FNO training set).
    if args.save_embeds:
        train = {"schema": "fno_training_pairs_v1", "dim": D_ENC, "lineages": ["onset_1s"],
                 "pipeline": pipeline,
                 "note": "X=prefill_embeds (decoder input rows) + prefill_mask; y=coef. "
                         "FNO learns prefill->coef, replacing the deterministic mean+L2 (manifest v2).",
                 "n": len(index), "by_source_id": index}
        train_fp = OUT / "alt_train_pairs.json.gz"
        with gzip.open(train_fp, "wt", encoding="utf-8") as f:
            json.dump(train, f)
        print(f"wrote {len(index)} FNO training pairs (X+y) -> {train_fp} "
              f"({train_fp.stat().st_size} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
