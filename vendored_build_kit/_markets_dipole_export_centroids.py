"""Export per-pair (c_win_centroid, c_lose_centroid) to a single JSON file
that the quote service / live wiring layer can load.

The dipole predictor uses these centroids to score every candidate trade:

    H_a = <c, c_win_centroid> / ||c_win_centroid||
    H_b = <c, c_lose_centroid> / ||c_lose_centroid||
    predict WIN iff H_a > H_b

where c is the 128-dim operator_coefficients vector produced by the
pipeline (markets_refrag_adapter --pre-entry-minutes 30 on
[entry_ts - 30m, entry_ts] bars).

Source data: pre-entry cross-section 100 sweep (2026-05-28).
- Per-trade discoveries: E:\\refrag\\discoveries\\operator_discoveries\\<pair>_<outcome>_preentry_cs100\\<uuid>.json
- Pooled CV result: 0.949 acc / 0.976 AUC / FN=0 / d_OOF=+1.98

Output schema (single JSON file):
{
    "schema_version": 1,
    "source": "preentry_cs100",
    "window": "[entry_ts - 30m, entry_ts]",
    "decision_rule": "predict WIN iff <c, c_win>/||c_win|| > <c, c_lose>/||c_lose||",
    "pairs": {
        "<pair_name>": {
            "n_win": int,
            "n_lose": int,
            "c_win_centroid": [...128 floats...],
            "c_lose_centroid": [...128 floats...],
            "c_win_norm": float,
            "c_lose_norm": float
        },
        ...
    }
}
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

DISC = Path(r"E:\refrag\discoveries\operator_discoveries")
PAIRS = [
    "markets_btc_bybit_buy", "markets_btc_bybit_sell",
    "markets_btc_coinbase_buy", "markets_btc_coinbase_sell",
    "markets_btc_kraken_buy", "markets_btc_kraken_sell",
    "markets_eth_bybit_buy", "markets_eth_bybit_sell",
    "markets_eth_coinbase_buy", "markets_eth_coinbase_sell",
    "markets_eth_kraken_buy", "markets_eth_kraken_sell",
]


def load_coefs(domain: str) -> list[list[float]]:
    d = DISC / domain
    if not d.is_dir():
        return []
    out: list[list[float]] = []
    for p in d.glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        coefs = obj.get("result", {}).get("operator_coefficients")
        if isinstance(coefs, list) and coefs:
            out.append([float(c) for c in coefs])
    return out


def vec_mean(vs: list[list[float]]) -> list[float]:
    if not vs:
        return []
    n = len(vs)
    d = len(vs[0])
    out = [0.0] * d
    for v in vs:
        for i in range(d):
            out[i] += v[i]
    return [x / n for x in out]


def norm(a: list[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain-suffix", type=str, default="preentry_cs100",
                    help="Domain folder suffix (default 'preentry_cs100'). "
                         "Used as fallback for both sides when --win-domain-suffix "
                         "and --lose-domain-suffix are not given.")
    ap.add_argument("--win-domain-suffix", type=str, default=None,
                    help="Override domain suffix for winner dirs only.")
    ap.add_argument("--lose-domain-suffix", type=str, default=None,
                    help="Override domain suffix for loser dirs only.")
    ap.add_argument("--output", type=Path,
                    default=Path(r"E:\Markets\_markets_dipole_centroids_preentry_cs100_v2.json"),
                    help="Output JSON path. Default targets the v2 (post entry-ts fix) "
                         "artifact. The original _cs100.json was renamed "
                         "_cs100.SUPERSEDED.json 2026-05-28 PM after a uniform-"
                         "timestamp bug invalidated its winner centroids.")
    args = ap.parse_args()

    win_sfx_raw = args.win_domain_suffix if args.win_domain_suffix is not None else args.domain_suffix
    lose_sfx_raw = args.lose_domain_suffix if args.lose_domain_suffix is not None else args.domain_suffix
    win_sfx = f"_{win_sfx_raw}" if win_sfx_raw else ""
    lose_sfx = f"_{lose_sfx_raw}" if lose_sfx_raw else ""
    pairs_out: dict[str, dict] = {}
    for pair in PAIRS:
        cw = load_coefs(f"{pair}_win{win_sfx}")
        cl = load_coefs(f"{pair}_lose{lose_sfx}")
        if not cw or not cl:
            print(f"  SKIP {pair}: n_win={len(cw)}  n_lose={len(cl)}", flush=True)
            continue
        cw_mean = vec_mean(cw)
        cl_mean = vec_mean(cl)
        nw = norm(cw_mean)
        nl = norm(cl_mean)
        pairs_out[pair] = {
            "n_win": len(cw),
            "n_lose": len(cl),
            "c_win_centroid": cw_mean,
            "c_lose_centroid": cl_mean,
            "c_win_norm": nw,
            "c_lose_norm": nl,
        }
        print(f"  {pair:30s}  n_win={len(cw):>4d}  n_lose={len(cl):>4d}  "
              f"||c_w||={nw:.4f}  ||c_l||={nl:.4f}", flush=True)

    src_label = win_sfx_raw if win_sfx_raw == lose_sfx_raw else f"win={win_sfx_raw};lose={lose_sfx_raw}"
    blob = {
        "schema_version": 1,
        "source": src_label or "post_hoc",
        "win_domain_suffix": win_sfx_raw,
        "lose_domain_suffix": lose_sfx_raw,
        "window": "[entry_ts - 30m, entry_ts]" if "preentry" in (win_sfx_raw or "") else "[entry_ts, exit_ts]",
        "decision_rule": "predict WIN iff <c, c_win>/||c_win|| > <c, c_lose>/||c_lose||",
        "pairs": pairs_out,
    }
    args.output.write_text(json.dumps(blob, indent=2))
    print(f"\nWrote {len(pairs_out)} pair centroids -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
