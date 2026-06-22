"""S34 Direction-2: build same-period (05-23/24) CANDIDATE buckets from the audit.

The de-confound is lose-starved because only the missed-winner subset (1240) got
coeffs. The audit holds 3991 MORE same-period trades with no coeffs yet. This builds
per-cell candidate bucket files (audit unique_keys NOT already discovered) in the
schema `_eligible_cross_section.py` + the discovery adapter expect, so we can run
pre-entry discovery on them and balance the cells.

Collapses audit rows to one entry per unique_key (min ts_utc = first admission, same
policy as _patch_win_buckets_entry_ts). Writes one bucket per cell to
E:\\Markets\\_sameperiod_cand\\markets_<pair>_cand.json. Excludes keys that already
have coeffs (in _cs2000_coeff_index win shards).
"""
from __future__ import annotations

import csv, glob, json
from collections import defaultdict
from pathlib import Path

CSV = Path(r"E:\Markets\research\strategy_evolution\live_mock_replay\live_hindsight_missed_winner_audit_rows.csv")
SH = Path(r"E:\Markets\_cs2000_coeff_index")
OUT = Path(r"E:\Markets\_sameperiod_cand")
PAIRS = ["btc_bybit_buy","btc_bybit_sell","btc_coinbase_buy","btc_coinbase_sell",
         "btc_kraken_buy","btc_kraken_sell","eth_bybit_buy","eth_bybit_sell",
         "eth_coinbase_buy","eth_coinbase_sell","eth_kraken_buy","eth_kraken_sell"]


def main() -> int:
    have = set()
    for sh in glob.glob(str(SH / "*_win_preentry_cs2000_clean.json")):
        for _u, rec in json.load(open(sh)).items():
            have.add(rec["source_id"])
    print(f"already have coeffs: {len(have)}")

    # collapse audit rows -> per unique_key fields (min ts_utc)
    rows = defaultdict(lambda: {"ts": None, "a": None, "v": None, "s": None,
                                "h": None, "net": None})
    with CSV.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = r.get("unique_key")
            if not k:
                continue
            try:
                ts = float(r.get("ts_utc") or 0)
            except ValueError:
                continue
            if ts <= 0:
                continue
            d = rows[k]
            if d["ts"] is None or ts < d["ts"]:
                d["ts"] = ts
            d["a"] = r.get("asset"); d["v"] = r.get("venue"); d["s"] = r.get("side")
            try:
                d["h"] = float(r.get("oracle_horizon_minutes") or 0) or 240.0
            except ValueError:
                d["h"] = 240.0
            try:
                d["net"] = float(r.get("oracle_net_bps") or 0)
            except ValueError:
                d["net"] = 0.0

    OUT.mkdir(parents=True, exist_ok=True)
    def cell(a, v, s): return f"{a.lower()}_{v.lower()}_{s.lower()}"
    per = defaultdict(list)
    for k, d in rows.items():
        if k in have:
            continue
        c = cell(d["a"], d["v"], d["s"])
        per[c].append({
            "schema": "sameperiod_candidate_v1",
            "source": "live_hindsight_audit_sameperiod_cand",
            "source_id": k,
            "asset": d["a"], "venue": d["v"], "side": d["s"],
            "entry_ts_utc": d["ts"], "horizon_minutes": d["h"],
            "net_bps": d["net"],
        })
    print(f"\n{'cell':18s} {'cand':>5s}")
    tot = 0
    for p in PAIRS:
        es = per.get(p, [])
        es.sort(key=lambda e: e["entry_ts_utc"])
        fp = OUT / f"markets_{p}_cand.json"
        fp.write_text(json.dumps({"schema": "sameperiod_candidate_bucket_v1",
                                  "bucket": p, "entries": es}, indent=2), encoding="utf-8")
        print(f"{p:18s} {len(es):>5d}")
        tot += len(es)
    print("-" * 26)
    print(f"{'TOTAL':18s} {tot:>5d}  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
