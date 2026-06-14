"""scripts/dedup_discovery_pools.py — SALVAGE step 1: inspect, then physically-dedup the
existing operator-discovery JSONs WITHOUT re-running coeff-gen.

Background (S29): the trade pools carry strategy duplication (Bug 2) — the same physical
trade was discovered by up to 6 strategy passes, each tagged with its own strategy_id, and
`oracle_winner_canonical_trade_key` LEADS with strategy_id, so the pools never deduped to
physical trades (lose pools ~4.5x inflated). The discovery JSONs were generated from those
pools, so each physical trade's coefficient vector appears ~Nx. The dipole validation
(od_larger_set_val.py) reads one vector per JSON, so the duplicates inflate the win/lose
sets and bias the centroids/counts.

Salvage premise: coefficients are extracted by chunk_id from bar chunks, NOT by timestamp,
so duplicate copies of one physical trade should have IDENTICAL coefficient vectors. If that
holds, deduping to one-per-physical-trade is LOSSLESS and no re-coeff is needed.

This tool is READ-ONLY by default (--inspect). It mutates nothing until you pass --write,
and even then it writes to a NEW directory (never touches the originals or the 3 KBs).

Run order:
  1) python scripts/dedup_discovery_pools.py --inspect          # confirm schema + dedup gate
     (paste the output back; we lock the dedup key from it)
  2) python scripts/dedup_discovery_pools.py --write --key <k>  # writes deduped copies
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

# Same root the validation harness reads. Override with --disc if it moved.
DEFAULT_DISC = Path(r"E:\refrag\discoveries\operator_discoveries")

# Identity fields we look for in each discovery JSON (top level OR under "result"/"trade"/"meta").
ID_CANDIDATES = [
    "chunk_id", "source_id", "canonical_trade_key",
    "entry_ts_utc", "entry_ts", "ts_utc",
    "asset", "venue", "side", "strategy_id", "trade_strategy_id",
]
NEST_KEYS = ("result", "trade", "meta", "entry", "row")


def _coef(obj: dict):
    c = (obj.get("result") or {}).get("operator_coefficients")
    if not isinstance(c, list) or not c:
        c = obj.get("operator_coefficients")
    return [float(x) for x in c] if isinstance(c, list) and c else None


def _coef_hash(vec, ndp: int = 6) -> str:
    s = ",".join(f"{x:.{ndp}f}" for x in vec)
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def _find_ids(obj: dict) -> dict:
    """Pull identity fields from the top level or one nested level down."""
    found = {}
    scopes = [obj] + [obj[k] for k in NEST_KEYS if isinstance(obj.get(k), dict)]
    for scope in scopes:
        for k in ID_CANDIDATES:
            if k in scope and k not in found and scope[k] not in (None, ""):
                found[k] = scope[k]
    return found


def _strip_strategy_from_canon(canon: str) -> str:
    # canonical_trade_key LEADS with strategy_id (token 0). Dropping it yields a
    # strategy-agnostic regime/trade signature. NOTE: this collapses to REGIME, which is
    # coarser than a physical trade — offered only as a diagnostic candidate, not default.
    parts = str(canon).split("|")
    return "|".join(parts[1:]) if len(parts) > 1 else str(canon)


def load_bucket(d: Path) -> list[dict]:
    rows = []
    for p in sorted(d.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        vec = _coef(obj)
        if vec is None:
            continue
        ids = _find_ids(obj)
        rows.append({"path": p, "vec": vec, "chash": _coef_hash(vec), "ids": ids})
    return rows


def candidate_keys(row: dict) -> dict:
    ids = row["ids"]
    keys = {"coef": row["chash"]}
    if "chunk_id" in ids:
        side = ids.get("side", ""); ven = ids.get("venue", ""); ast = ids.get("asset", "")
        keys["chunk"] = f"{ast}|{ven}|{side}|{ids['chunk_id']}"
    # physical trade: asset+venue+side+entry_ts (prefer real ts fields)
    ts = ids.get("ts_utc") or ids.get("entry_ts_utc") or ids.get("entry_ts")
    if ts and {"asset", "venue", "side"} <= ids.keys():
        keys["phys"] = f"{ids['asset']}|{ids['venue']}|{ids['side']}|{ts}"
    if "canonical_trade_key" in ids:
        keys["canon_nostrat"] = _strip_strategy_from_canon(ids["canonical_trade_key"])
    if "source_id" in ids:
        keys["source_id"] = str(ids["source_id"])
    return keys


def _coef_identical_within(rows: list[dict], groups: dict) -> tuple[int, float]:
    """For groups with >1 member, how many are coef-identical, and the worst max-spread."""
    import numpy as np
    multi = [g for g in groups.values() if len(g) > 1]
    if not multi:
        return 0, 0.0
    identical = 0; worst = 0.0
    for g in multi:
        hashes = {rows[i]["chash"] for i in g}
        if len(hashes) == 1:
            identical += 1
        else:
            mat = np.array([rows[i]["vec"] for i in g], float)
            spread = float(np.max(np.linalg.norm(mat - mat.mean(0), axis=1)))
            worst = max(worst, spread)
    return identical, worst


def group_by(rows: list[dict], key_name: str) -> dict:
    g = defaultdict(list)
    for i, r in enumerate(rows):
        k = candidate_keys(r).get(key_name)
        if k is None:
            k = f"__nokey__{i}"  # rows lacking this key stay unique (never silently merged)
        g[k].append(i)
    return g


def discover_buckets(disc: Path) -> list[Path]:
    return sorted([d for d in disc.glob("markets_*") if d.is_dir()])


def inspect(disc: Path) -> None:
    buckets = discover_buckets(disc)
    if not buckets:
        print(f"[inspect] NO markets_* buckets under {disc}"); return
    print(f"[inspect] {len(buckets)} buckets under {disc}\n")
    key_names = ["coef", "chunk", "phys", "canon_nostrat", "source_id"]
    grand = defaultdict(lambda: [0, 0])  # key_name -> [total, unique]
    schema_keys = defaultdict(int)
    for d in buckets:
        rows = load_bucket(d)
        n = len(rows)
        if n == 0:
            print(f"{d.name:42s}  EMPTY / no coeffs"); continue
        present = sorted({k for r in rows for k in r["ids"]})
        for k in present:
            schema_keys[k] += 1
        ratios = []
        for kn in key_names:
            if not any(kn in candidate_keys(r) for r in rows):
                ratios.append(f"{kn}=n/a"); continue
            g = group_by(rows, kn)
            u = len(g)
            grand[kn][0] += n; grand[kn][1] += u
            extra = ""
            if kn in ("coef", "chunk"):
                ident, worst = _coef_identical_within(rows, g)
                multi = sum(1 for v in g.values() if len(v) > 1)
                extra = f" [dupgrps={multi} coefIdentical={ident} worstSpread={worst:.2e}]"
            ratios.append(f"{kn}:{u}/{n}={n/u:.2f}x{extra}")
        print(f"{d.name:42s} N={n:5d}")
        print(f"    ids: {present or '(none beyond coeffs!)'}")
        for r in ratios:
            print(f"    {r}")
    print("\n=== GRAND TOTALS (all buckets) ===")
    for kn in key_names:
        tot, uniq = grand[kn]
        if tot:
            print(f"  {kn:14s} {uniq}/{tot} unique  ({tot/uniq:.2f}x inflation)")
    print("\n=== identity-field coverage (buckets containing the field) ===")
    for k, c in sorted(schema_keys.items(), key=lambda x: -x[1]):
        print(f"  {k:22s} {c}/{len(buckets)} buckets")
    print("\nNEXT: pick the dedup key from the above. Prefer the PHYSICAL-trade key that is")
    print("(a) present in all buckets and (b) shows coefIdentical==dupgrps (lossless).")
    print("Likely 'chunk' or 'coef'. Then re-run with --write --key <name>.")


def write_dedup(disc: Path, out: Path, key_name: str, rep: str) -> None:
    buckets = discover_buckets(disc)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    tot_in = tot_out = 0
    for d in buckets:
        rows = load_bucket(d)
        if not rows:
            continue
        g = group_by(rows, key_name)
        od = out / d.name
        od.mkdir(parents=True, exist_ok=True)
        kept = []
        for k, idxs in g.items():
            # representative: 'first' by filename (stable) or 'most_meta' (most id fields)
            if rep == "most_meta":
                idxs = sorted(idxs, key=lambda i: (-len(rows[i]["ids"]), str(rows[i]["path"].name)))
            else:
                idxs = sorted(idxs, key=lambda i: str(rows[i]["path"].name))
            keep = idxs[0]
            src = rows[keep]["path"]
            shutil.copy2(src, od / src.name)
            kept.append({"key": k, "kept": src.name,
                         "dropped": [rows[i]["path"].name for i in idxs[1:]],
                         "merged_strategy_ids": sorted({str(rows[i]["ids"].get("strategy_id")
                                                            or rows[i]["ids"].get("trade_strategy_id"))
                                                        for i in idxs if rows[i]["ids"].get("strategy_id")
                                                        or rows[i]["ids"].get("trade_strategy_id")})})
        manifest[d.name] = {"in": len(rows), "out": len(kept)}
        tot_in += len(rows); tot_out += len(kept)
        print(f"{d.name:42s} {len(rows):5d} -> {len(kept):5d}")
    (out / "_dedup_manifest.json").write_text(
        json.dumps({"key": key_name, "rep": rep, "buckets": manifest,
                    "total_in": tot_in, "total_out": tot_out}, indent=2), encoding="utf-8")
    print(f"\nTOTAL {tot_in} -> {tot_out}  ({tot_in/max(1,tot_out):.2f}x)  written to {out}")
    print(f"manifest: {out / '_dedup_manifest.json'}")
    print("ORIGINALS UNTOUCHED. Point od_larger_set_val.py DISC at the new dir to re-validate.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", default=str(DEFAULT_DISC), help="operator_discoveries root")
    ap.add_argument("--inspect", action="store_true", help="read-only: schema + dedup-ratio dry run")
    ap.add_argument("--write", action="store_true", help="write deduped copies to --out (non-destructive)")
    ap.add_argument("--key", default="chunk", choices=["coef", "chunk", "phys", "canon_nostrat", "source_id"])
    ap.add_argument("--rep", default="most_meta", choices=["first", "most_meta"])
    ap.add_argument("--out", default=None, help="output dir (default: <disc>_dedup)")
    args = ap.parse_args()
    disc = Path(args.disc)
    if args.write:
        out = Path(args.out) if args.out else disc.with_name(disc.name + "_dedup")
        write_dedup(disc, out, args.key, args.rep)
    else:
        inspect(disc)


if __name__ == "__main__":
    main()
