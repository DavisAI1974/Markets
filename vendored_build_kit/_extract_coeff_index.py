"""S30 coefficient index extractor.

Reads every cs2000_clean discovery JSON and pulls out, per trade:
  - source_id  (from evidence_graph_metadata.supporting_documents / blob)
  - operator_coefficients (128-dim)
  - bucket (folder), uuid (filename stem), win/lose (from folder name)

Header/text regex (no full json.load of the multi-MB evidence graphs).
Resume-safe: writes one shard per bucket; skips buckets already done.

Outputs:
  E:\\Markets\\_cs2000_coeff_index\\<bucket>.json     (per-bucket shard)
  E:\\Markets\\_cs2000_coeff_index.json               (merged, source_id -> rec)

Double duty: this is also the compact portable coeff copy (deferred S30 TODO#1).
"""
from __future__ import annotations

import gzip
import json
import re
import time
from pathlib import Path

STORE = Path(r"E:\refrag\discoveries\operator_discoveries")
SHARD_DIR = Path(r"E:\Markets\_cs2000_coeff_index")
MERGED = Path(r"E:\Markets\_cs2000_coeff_index.json")
SUFFIX = "_preentry_cs2000_clean"

RE_COEF = re.compile(r'"operator_coefficients"\s*:\s*\[([^\]]*)\]')
# source_id lives in result.evidence_graph_metadata.supporting_documents (format-agnostic:
# win pool = "BTC|bybit|<hash>|buy"; lose pool = "BTC|bybit|h60-66|5m|slice_...|...|buy")
RE_SID = re.compile(r'"supporting_documents"\s*:\s*\[\s*"([^"]+)"')


def parse_file(fp: Path):
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    mc = RE_COEF.search(txt)
    ms = RE_SID.search(txt)
    if not mc or not ms:
        return None
    try:
        coef = [float(x) for x in mc.group(1).split(",") if x.strip()]
    except ValueError:
        return None
    if len(coef) != 128:
        return None
    return ms.group(1), coef


def main() -> int:
    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    buckets = sorted(p for p in STORE.glob(f"markets_*{SUFFIX}") if p.is_dir())
    print(f"{len(buckets)} buckets")
    t0 = time.time()
    for b in buckets:
        shard = SHARD_DIR / f"{b.name}.json"
        if shard.exists():
            print(f"  skip (done): {b.name}")
            continue
        label = "win" if "_win" + SUFFIX in b.name else "lose"
        recs = {}
        files = list(b.glob("*.json"))
        bad = 0
        for fp in files:
            r = parse_file(fp)
            if r is None:
                bad += 1
                continue
            sid, coef = r
            recs[fp.stem] = {"source_id": sid, "label": label, "bucket": b.name, "coef": coef}
        shard.write_text(json.dumps(recs), encoding="utf-8")
        print(f"  {b.name}: {len(recs)} ok, {bad} bad  ({time.time()-t0:.0f}s)")

    # merge: source_id -> rec (a trade can be in only one bucket per outcome; keep all)
    merged = {}
    by_sid = {}
    for shard in sorted(SHARD_DIR.glob("*.json")):
        d = json.loads(shard.read_text(encoding="utf-8"))
        for uuid, rec in d.items():
            merged[uuid] = rec
            by_sid[rec["source_id"]] = rec  # for join to labels
    MERGED.write_text(json.dumps({"by_uuid": merged, "by_source_id": by_sid,
                                  "n": len(merged)}), encoding="utf-8")
    with gzip.open(str(MERGED) + ".gz", "wt", encoding="utf-8") as f:
        json.dump({"by_source_id": by_sid, "n": len(by_sid)}, f)
    print(f"\nmerged: {len(merged)} coeff files, {len(by_sid)} distinct source_ids -> {MERGED}(.gz)")
    print(f"total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
