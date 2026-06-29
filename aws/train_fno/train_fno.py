"""aws/train_fno/train_fno.py — SKELETON: train the production FNO decoder (the manifest tier).

This is the GPU upgrade over the deterministic decoder (S39). The deterministic pipeline gives us, per
winning episode, a (prefill_embeds -> operator_coefficients) pair; those pairs are the FNO training set.
The FNO learns the frequency-domain map the deterministic mean-of-embeds only approximates.

Manifest training_contract (operator_decoder.v2): FNO 4 layers / 16 modes / width 64;
loss = spectral_coefficient_mse + eigenvalue_preservation; min 100 training pairs;
Bayesian ensemble 5 members, mc_dropout 0.1.

Run on a GPU (SageMaker estimator or EC2 g5). Needs torch (NOT installed in the discovery container).
This is a STUB to fill in S40+ — it wires the data path + the contract; the FNO/ensemble bodies are TODO.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

# import torch  # GPU only; install in the training image, not the discovery image


def load_training_pairs(train_pairs_gz: str):
    """(X, y, masks): X = the per-episode prefill embeds, y = the deterministic 128-dim coef.

    Reads the train-pairs artifact produced by `_run_alt_coeffs.py --save-embeds`
    (`_alt_labels/coeffs/alt_train_pairs.json.gz`, gitignored, S3-bound). The committed
    `alt_coeff_index.json.gz` is lean (coef only) and is NOT a valid training input — point this at
    the train-pairs file. The deterministic decoder computes y = L2-normalize(masked-mean(X)); the
    FNO learns a richer prefill->coef map on the SAME (X, mask) input (manifest operator_decoder.v2).
    """
    with gzip.open(train_pairs_gz, "rt") as f:
        idx = json.load(f)
    recs = list(idx["by_source_id"].values())
    ys = [v["coef"] for v in recs]
    xs = [v.get("prefill_embeds") for v in recs]
    masks = [v.get("prefill_mask") for v in recs]
    if any(x is None for x in xs):
        raise SystemExit(
            "training pairs incomplete: prefill_embeds missing. Generate them with "
            "`python _run_alt_coeffs.py --save-embeds` (writes alt_train_pairs.json.gz), and point "
            "--train-pairs at THAT file (not the lean alt_coeff_index.json.gz).")
    return xs, ys, masks


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--train-pairs", required=True,
                   help="alt_train_pairs.json.gz from `_run_alt_coeffs.py --save-embeds` (X=prefill_embeds + y=coef)")
    p.add_argument("--layers", type=int, default=4)
    p.add_argument("--modes", type=int, default=16)
    p.add_argument("--width", type=int, default=64)
    p.add_argument("--ensemble", type=int, default=5)
    p.add_argument("--mc-dropout", type=float, default=0.1)
    p.add_argument("--out", default="fno_checkpoint.pt")
    args = p.parse_args()

    X, y, masks = load_training_pairs(args.train_pairs)
    if len(X) < 100:
        raise SystemExit(f"need >=100 training pairs (manifest); have {len(X)}")
    # TODO(S40+): FNO(layers, modes, width) in frequency domain; loss = spectral_coef_mse +
    # eigenvalue_preservation; train `ensemble` members with mc_dropout for calibrated posterior;
    # save MAP estimate + posterior to args.out. Validate calibration (ECE) on held-out cells.
    print(f"[train_fno] {len(X)} pairs; FNO {args.layers}L/{args.modes}m/{args.width}w; "
          f"ensemble {args.ensemble} mc_dropout {args.mc_dropout} -> {args.out} (BODY TODO)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
