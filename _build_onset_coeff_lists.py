"""S35 full-anchor fix, Phase 2 — build per-cell winner lists for the CORRECTED-onset coeff re-run.

Reads Phase-1 winner_onsets.json, keeps the onset_moved winners (the re-run set), and writes
arch_workflow --winner-json lists with entry_ts_utc = TRUE onset, cap 100/cell (Greg: "100 at a
time", was 150 for cand_sp), ranked by net_bps desc (strongest winners first). source_id is made
unique-per-episode (chunk_id collides) by embedding int(onset_ts) in the chunk field, keeping the
4-part ASSET|venue|chunk|side shape the downstream parser expects.

Out: _onset_coeff/lists/markets_<cell>_onset.cap100.json  (schema matches the cand_sp cap150 lists)
Coeffs will land in the ISOLATED domain markets_<cell>_win_onset/ (existing dirs untouched).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

WIN = Path(r"E:\Markets\.claude\worktrees\xenodochial-montalcini-f21fb6\_episode_onsets_out\winner_onsets.json")
OUT = Path(r"E:\Markets\_onset_coeff\lists")
CAP = 100
PAIRS = ["btc_bybit_buy", "btc_bybit_sell", "btc_coinbase_buy", "btc_coinbase_sell",
         "btc_kraken_buy", "btc_kraken_sell", "eth_bybit_buy", "eth_bybit_sell",
         "eth_coinbase_buy", "eth_coinbase_sell", "eth_kraken_buy", "eth_kraken_sell"]


def main() -> int:
    rows = json.loads(WIN.read_text(encoding="utf-8"))
    movers = [r for r in rows if r.get("onset_moved")]
    by_cell = defaultdict(list)
    for r in movers:
        by_cell[r["cell"]].append(r)

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{'cell':18s} {'movers':>6s} {'capped':>6s} {'remain':>6s}")
    tot_cap = tot_rem = 0
    for p in PAIRS:
        es = by_cell.get(p, [])
        # dedup per episode (onset_chunk_id, int(onset_ts)); rank by net_bps desc
        seen = set()
        uniq = []
        for r in sorted(es, key=lambda r: -float(r.get("net_bps") or 0)):
            key = (r["onset_chunk_id"], int(r["true_onset_ts_utc"]))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(r)
        picked = uniq[:CAP]
        remain = max(0, len(uniq) - CAP)
        entries = []
        for r in picked:
            a, v, s = r["asset"], r["venue"], r["side"]
            ots = int(r["true_onset_ts_utc"])
            sid = f"{a}|{v.lower()}|{r['onset_chunk_id']}_{ots}|{s}"
            entries.append({
                "schema": "onset_winner_v1",
                "source": "live_hindsight_winner_onset_reanchored",
                "source_id": sid,
                "asset": a, "venue": v, "side": s,
                "entry_ts_utc": float(r["true_onset_ts_utc"]),
                "horizon_minutes": float(r.get("horizon_minutes") or 240.0),
                "net_bps": float(r.get("net_bps") or 0.0),
            })
        fp = OUT / f"markets_{p}_onset.cap{CAP}.json"
        fp.write_text(json.dumps({"schema": "onset_winner_bucket_v1", "bucket": p,
                                  "entries": entries}, indent=1), encoding="utf-8")
        print(f"{p:18s} {len(uniq):>6d} {len(picked):>6d} {remain:>6d}")
        tot_cap += len(picked); tot_rem += remain
    print("-" * 40)
    print(f"{'TOTAL':18s} {'':>6s} {tot_cap:>6d} {tot_rem:>6d}")
    print(f"\nfirst pass: {tot_cap} winners -> {OUT}")
    if tot_rem:
        print(f"remaining over cap (2nd pass): {tot_rem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
