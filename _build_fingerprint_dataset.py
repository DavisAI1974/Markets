"""S35b — assemble a COMPACT, git-able fingerprint dataset in the markets repo for lightweight
coeff tests (Greg, phone-limited window). The full coeff records are ~47GB (evidence graphs);
the 128-dim vectors compact to ~40MB raw / ~5MB gzipped — that is all a fingerprint test needs.

Builds fingerprint_dataset/coeffs/coeff_index.json.gz =
  { source_id: {coef:[128], label:"win"|"lose", cell:"btc_kraken_sell", lineage:"cs2000_clean"|"cand_sp"|"onset"} }
covering the deployable lineages: cs2000_clean (win+lose), cand_sp (win), onset (win, the S35b re-anchored set).

Reuses the already-extracted E:\Markets\_cs2000_coeff_index shards for cs2000_clean (no 45GB re-read);
regex-extracts cand_sp + onset fresh (the only new domains). Data stays compact + local-derived.
"""
from __future__ import annotations

import gzip
import json
import re
import time
from pathlib import Path

STORE = Path(r"E:\refrag\discoveries\operator_discoveries")
CS2000_SHARDS = Path(r"E:\Markets\_cs2000_coeff_index")   # already extracted (24 shards)
OUT = Path(r"E:\Markets\.claude\worktrees\xenodochial-montalcini-f21fb6\fingerprint_dataset\coeffs")
PAIRS = ["btc_bybit_buy", "btc_bybit_sell", "btc_coinbase_buy", "btc_coinbase_sell",
         "btc_kraken_buy", "btc_kraken_sell", "eth_bybit_buy", "eth_bybit_sell",
         "eth_coinbase_buy", "eth_coinbase_sell", "eth_kraken_buy", "eth_kraken_sell"]

RE_COEF = re.compile(r'"operator_coefficients"\s*:\s*\[([^\]]*)\]')
RE_SID = re.compile(r'"supporting_documents"\s*:\s*\[\s*"([^"]+)"')


def parse_file(fp: Path):
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    mc = RE_COEF.search(txt); ms = RE_SID.search(txt)
    if not mc or not ms:
        return None
    try:
        coef = [float(x) for x in mc.group(1).split(",") if x.strip()]
    except ValueError:
        return None
    if len(coef) != 128:
        return None
    return ms.group(1), coef


def cell_of(bucket: str) -> str:
    b = bucket.replace("markets_", "")
    for suf in ("_win_preentry_cs2000_clean", "_lose_preentry_cs2000_clean",
                "_win_cand_sp", "_win_onset", "_win", "_lose"):
        if b.endswith(suf):
            return b[: -len(suf)]
    return b


def lineage_of(bucket: str) -> str:
    if bucket.endswith("_cand_sp"):
        return "cand_sp"
    if bucket.endswith("_win_onset"):
        return "onset"
    if "cs2000_clean" in bucket:
        return "cs2000_clean"
    return "other"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    index = {}
    t0 = time.time()

    # 1) reuse already-extracted cs2000_clean shards (win+lose)
    n_cs = 0
    for shard in sorted(CS2000_SHARDS.glob("markets_*_preentry_cs2000_clean.json")):
        d = json.loads(shard.read_text(encoding="utf-8"))
        for _uuid, rec in d.items():
            sid = rec["source_id"]
            index[sid] = {"coef": rec["coef"], "label": rec["label"],
                          "cell": cell_of(rec["bucket"]), "lineage": "cs2000_clean"}
            n_cs += 1
    print(f"cs2000_clean (reused shards): {n_cs} records  ({time.time()-t0:.0f}s)")

    # 2) extract cand_sp (win) + onset (win) fresh
    for lin, pat in (("cand_sp", "markets_{p}_win_cand_sp"), ("onset", "markets_{p}_win_onset")):
        nlin = 0
        for p in PAIRS:
            d = STORE / pat.format(p=p)
            if not d.is_dir():
                continue
            for fp in d.glob("*.json"):
                if fp.name == "index.json":
                    continue
                r = parse_file(fp)
                if r is None:
                    continue
                sid, coef = r
                index[sid] = {"coef": coef, "label": "win", "cell": p, "lineage": lin}
                nlin += 1
        print(f"{lin}: {nlin} records  ({time.time()-t0:.0f}s)")

    # 3) write compact gzipped index + a per-cell/lineage count summary
    out_gz = OUT / "coeff_index.json.gz"
    with gzip.open(str(out_gz), "wt", encoding="utf-8") as f:
        json.dump({"schema": "fingerprint_coeff_index_v1", "dim": 128,
                   "lineages": ["cs2000_clean", "cand_sp", "onset"],
                   "by_source_id": index, "n": len(index)}, f)
    from collections import Counter
    cnt = Counter((v["cell"], v["label"], v["lineage"]) for v in index.values())
    summ = {}
    for (cell, label, lin), c in sorted(cnt.items()):
        summ.setdefault(cell, {})[f"{label}_{lin}"] = c
    (OUT / "coeff_index_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(f"\nTOTAL {len(index)} distinct source_ids -> {out_gz} ({out_gz.stat().st_size/1e6:.1f}MB gz)")
    print("per-cell summary -> coeff_index_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
