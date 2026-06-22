"""S35 diagnostic — settle the fingerprint reproduction gap: window/bar-source mismatch
(benign) vs LOOK-AHEAD in the stored bucket micros (serious).

Method: for a sample of clean-bucket WIN entries, find the runtime opportunity row in
`_live_mock_opportunities.jsonl` whose micros EXACTLY match the stored ones (the true
provenance of each bucket entry). Then report, for the matched row:
  - trade_age_chunks / trade_stage    (0 + ""  => onset/pre-entry;  >0 + late/mature => post-onset)
  - chunk_end_ts_utc - entry_ts_utc   (>0 => the measurement window sits AFTER the recorded entry)
  - micro_row.ts_utc - entry_ts_utc   (gap between when micros were measured and the recorded entry)

If the matched rows are systematically age>0 / late and measured well after entry_ts_utc, the
stored micros are a MID-TRADE snapshot (look-ahead), not a pre-entry fingerprint — which is why
a strictly-pre-entry recompute can't reproduce them.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

CLEAN = Path(r"E:\Markets\research\strategy_evolution\per_bucket\clean")
OPP = Path(r"E:\Markets\research\strategy_evolution\_live_mock_opportunities.jsonl")
CELLS = ["btc_kraken_sell", "btc_bybit_sell", "btc_coinbase_sell", "eth_coinbase_buy",
         "btc_kraken_buy", "eth_kraken_sell"]
N_PER_CELL = 8
MICRO_KEYS = ["trade_current_chunk_bps", "trade_recent_2chunk_bps", "trade_from_onset_bps",
              "mean_dipole", "dipole_acl1", "volume_zscore"]


def sig(row: dict) -> tuple:
    return tuple(round(float(row.get(k) or 0.0), 5) for k in MICRO_KEYS)


def main() -> int:
    # 1) collect sample clean entries
    samples = []          # (cell, entry, chunk_id, sig)
    want_cids: set[str] = set()
    for cell in CELLS:
        fp = CLEAN / f"markets_{cell}_win.clean.json"
        if not fp.exists():
            continue
        entries = json.loads(fp.read_text(encoding="utf-8")).get("entries", [])
        picked = [e for e in entries if abs(float(e.get("trade_current_chunk_bps") or 0)) > 0.01][:N_PER_CELL]
        for e in picked:
            cid = str(e.get("chunk_id") or "")
            samples.append((cell, e, cid, sig(e)))
            want_cids.add(cid)
    print(f"samples: {len(samples)}  unique chunk_ids: {len(want_cids)}")

    # 2) stream opportunity log; keep rows whose chunk_id is wanted
    by_cid: dict[str, list[dict]] = defaultdict(list)
    n = 0
    with OPP.open(encoding="utf-8", errors="replace") as f:
        for ln in f:
            if not ln.strip():
                continue
            # cheap prefilter: only json.loads lines that contain a wanted chunk_id
            if not any(cid in ln for cid in want_cids):
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            cid = str(r.get("chunk_id") or "")
            if cid in want_cids:
                by_cid[cid].append(r)
                n += 1
    print(f"matched opportunity rows pulled: {n}\n")

    # 3) for each sample, find the exact-micro match and report provenance
    hdr = f"{'cell':16s} {'cid':16s} {'age':>3s} {'stage':8s} {'micro_ts-entry(s)':>18s} {'chunkEnd-entry(s)':>18s} {'cur_bps':>9s} match"
    print(hdr)
    print("-" * len(hdr))
    ages = []
    n_lookahead = n_onset = n_nomatch = 0
    for cell, e, cid, s in samples:
        entry_ts = float(e.get("entry_ts_utc") or 0)
        cand = by_cid.get(cid, [])
        match = None
        for r in cand:
            if sig(r) == s:
                match = r
                break
        if match is None:
            n_nomatch += 1
            print(f"{cell:16s} {cid:16s}  NO EXACT MICRO MATCH among {len(cand)} rows w/ this chunk_id")
            continue
        age = int(float(match.get("trade_age_chunks") or 0))
        stage = str(match.get("trade_stage") or "")
        micro_ts = float(match.get("ts_utc") or 0)
        chunk_end = float(match.get("chunk_end_ts_utc") or 0)
        ages.append(age)
        if age > 0 or stage in ("late", "mature"):
            n_lookahead += 1
        else:
            n_onset += 1
        print(f"{cell:16s} {cid:16s} {age:>3d} {stage:8s} "
              f"{micro_ts-entry_ts:>18.0f} {chunk_end-entry_ts:>18.0f} "
              f"{float(match.get('trade_current_chunk_bps') or 0):>9.2f} OK")
    print("-" * len(hdr))
    print(f"\nmatched: {len(ages)}  no-match: {n_nomatch}")
    if ages:
        import statistics
        print(f"trade_age_chunks: min={min(ages)} max={max(ages)} median={statistics.median(ages)} mean={statistics.mean(ages):.1f}")
        print(f"age>0 or late/mature (look-ahead snapshot): {n_lookahead}/{len(ages)}")
        print(f"age==0 onset (pre-entry snapshot):          {n_onset}/{len(ages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
