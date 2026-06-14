"""scripts/dedup_pools.py — produce CLEAN per-bucket trade pools for the discovery rerun.

Bug 2 (strategy duplication): the source CSV was built from 6 strategy passes
(basis_dislocation, liquidity_squeeze, news_breakout, relative_strength, vol_breakout,
mean_reversion_chop). Each pass re-discovered the same PHYSICAL trade under its own
strategy_id, and the pools kept every copy (canonical_trade_key LEADS with strategy_id,
so cross-strategy copies never merged). Measured inflation: lose 4.51x, win 1.97x.

Physical-trade key = (asset, venue, side, round(entry_ts_utc, 3)). Within a bucket
asset/venue/side are constant, so this dedups by real per-trade entry time. (source_id is
strategy-tagged so it can't dedup; canonical_trade_key is too coarse for lose / too fine
for win — verified S29.)

Inputs (E:\Markets\research\strategy_evolution\per_bucket):
  win  -> markets_<asset>_<venue>_<side>_win.fixed_ts.json   (Bug-1-corrected timestamps)
  lose -> markets_<asset>_<venue>_<side>_lose.json           (already real timestamps)
Output (NON-DESTRUCTIVE): per_bucket\clean\markets_..._{win,lose}.clean.json
Each kept entry gets merged_strategy_ids / merged_count / net_bps_merged for provenance.
Also reports win<->lose physical-trade label overlap per pair (a trade in BOTH pools).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

PB = Path(r"E:\Markets\research\strategy_evolution\per_bucket")
OUT = PB / "clean"
PAIRS = [
    "markets_btc_bybit_buy", "markets_btc_bybit_sell", "markets_btc_coinbase_buy", "markets_btc_coinbase_sell",
    "markets_btc_kraken_buy", "markets_btc_kraken_sell", "markets_eth_bybit_buy", "markets_eth_bybit_sell",
    "markets_eth_coinbase_buy", "markets_eth_coinbase_sell", "markets_eth_kraken_buy", "markets_eth_kraken_sell",
]


def _phys(e: dict):
    return (e.get("asset"), e.get("venue"), e.get("side"), round(float(e.get("entry_ts_utc") or 0.0), 3))


def _load(fp: Path) -> dict:
    return json.loads(fp.read_text(encoding="utf-8"))


def dedup_entries(entries: list[dict]) -> tuple[list[dict], int]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in entries:
        groups[_phys(e)].append(e)
    out = []
    for k, grp in groups.items():
        # representative: strongest |net_bps| (cosmetic for coeffs — they come from the
        # bar window at entry_ts, identical across the group — but keeps the best label)
        rep = dict(max(grp, key=lambda e: abs(float(e.get("net_bps") or 0.0))))
        rep["merged_count"] = len(grp)
        rep["merged_strategy_ids"] = sorted({str(e.get("strategy_id")) for e in grp if e.get("strategy_id")})
        rep["net_bps_merged"] = sorted({round(float(e.get("net_bps") or 0.0), 4) for e in grp})
        rep.pop("merged_duplicate_sources", None)
        out.append(rep)
    out.sort(key=lambda e: float(e.get("entry_ts_utc") or 0.0))
    return out, len(entries)


def process(pair: str) -> dict:
    res = {"pair": pair}
    OUT.mkdir(parents=True, exist_ok=True)
    win_keys, lose_keys = set(), set()
    for side, src in (("win", PB / f"{pair}_win.fixed_ts.json"), ("lose", PB / f"{pair}_lose.json")):
        if not src.exists():
            res[side] = "MISSING"; continue
        doc = _load(src)
        entries = doc.get("entries", []) or []
        clean, n_in = dedup_entries(entries)
        keys = {_phys(e) for e in clean}
        (win_keys if side == "win" else lose_keys).update(keys)
        doc["entries"] = clean
        doc["dedup"] = {"by": "asset|venue|side|entry_ts_utc", "n_in": n_in, "n_out": len(clean),
                        "ratio": round(n_in / max(1, len(clean)), 3), "tool": "dedup_pools.py"}
        outfp = OUT / f"{pair}_{side}.clean.json"
        outfp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        res[side] = {"in": n_in, "out": len(clean), "ratio": round(n_in / max(1, len(clean)), 2)}
    res["overlap"] = len(win_keys & lose_keys)  # same physical trade labeled BOTH win and lose
    return res


def main() -> None:
    rows = [process(p) for p in PAIRS]
    print(f"{'pair':28s}{'win_in':>7s}{'win_out':>8s}{'wr':>5s}{'lose_in':>8s}{'lose_out':>9s}{'lr':>5s}{'overlap':>8s}")
    print("-" * 78)
    twi = two = tli = tlo = tov = 0
    for r in rows:
        w = r.get("win"); l = r.get("lose")
        if not isinstance(w, dict) or not isinstance(l, dict):
            print(f"{r['pair']:28s}  {w} / {l}"); continue
        print(f"{r['pair']:28s}{w['in']:>7d}{w['out']:>8d}{w['ratio']:>5.1f}{l['in']:>8d}{l['out']:>9d}{l['ratio']:>5.1f}{r['overlap']:>8d}")
        twi += w['in']; two += w['out']; tli += l['in']; tlo += l['out']; tov += r['overlap']
    print("-" * 78)
    print(f"{'TOTAL':28s}{twi:>7d}{two:>8d}{'':>5s}{tli:>8d}{tlo:>9d}{'':>5s}{tov:>8d}")
    print(f"\nCLEAN POOLS -> {OUT}")
    print(f"  win:  {twi} -> {two} distinct physical trades")
    print(f"  lose: {tli} -> {tlo} distinct physical trades")
    if tov:
        print(f"  WARNING: {tov} physical trades appear in BOTH win and lose pools (label conflict) — inspect.")


if __name__ == "__main__":
    main()
