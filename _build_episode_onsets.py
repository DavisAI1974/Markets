"""S35 full-anchor fix, Phase 1 — map every winning bucket entry to its TRUE per-episode onset.

The bucket micros are mid-trade snapshots and entry_ts is the chunk_id-collision min(ts).
This reconstructs episodes from _live_mock_opportunities.jsonl (per asset,venue; a new episode
starts whenever trade_age_chunks resets to 0 — gap-tolerant, since a time gap does NOT reset age),
finds each winner's exact-micro provenance row, walks back to that episode's age-0 ONSET, and emits
the corrected onset_ts + onset micros. Quantifies how many onsets MOVE materially vs the old anchor
(= the coeff re-run set).

Output: _episode_onsets_out/winner_onsets.json  + per-cell stats to stdout.
No writes to git-tracked data; pure analysis (data stays local).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

OPP = Path(r"E:\Markets\research\strategy_evolution\_live_mock_opportunities.jsonl")
CLEAN = Path(r"E:\Markets\research\strategy_evolution\per_bucket\clean")
OUT = Path(r"E:\Markets\.claude\worktrees\xenodochial-montalcini-f21fb6\_episode_onsets_out")
CELLS = ["btc_bybit_buy", "btc_bybit_sell", "btc_coinbase_buy", "btc_coinbase_sell",
         "btc_kraken_buy", "btc_kraken_sell", "eth_bybit_buy", "eth_bybit_sell",
         "eth_coinbase_buy", "eth_coinbase_sell", "eth_kraken_buy", "eth_kraken_sell"]
MICRO_KEYS = ["trade_current_chunk_bps", "trade_recent_2chunk_bps", "trade_from_onset_bps",
              "mean_dipole", "dipole_acl1", "volume_zscore"]
ONSET_MOVE_TOL_S = 90.0   # > ~1 minute bar => the 30m coeff window shifts => re-run


def micro_sig(r: dict) -> tuple:
    return tuple(round(float(r.get(k) or 0.0), 5) for k in MICRO_KEYS)


def main() -> int:
    # 1) stream opportunity log -> per (asset,venue) ordered rows (keep needed fields, dedup per ts)
    av_rows: dict[tuple, dict] = defaultdict(dict)   # (asset,venue) -> {ts: row}
    keep = ("asset", "venue", "side", "ts_utc", "chunk_end_ts_utc", "chunk_id",
            "trade_age_chunks", "trade_stage", "scenario_id", *MICRO_KEYS)
    n = 0
    with OPP.open(encoding="utf-8", errors="replace") as f:
        for ln in f:
            if '"live_mock_trade_replay"' not in ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            a, v = r.get("asset"), r.get("venue")
            if not a or not v:
                continue
            ts = round(float(r.get("ts_utc") or 0), 1)
            slot = av_rows[(a, v)]
            # prefer historic_parity_live; keep one row per ~ts (the dual buy/sell share age+micros)
            if ts not in slot or r.get("scenario_id") == "historic_parity_live":
                slot[ts] = {k: r.get(k) for k in keep}
            n += 1
    print(f"opportunity rows scanned: {n}; (asset,venue) groups: {len(av_rows)}")

    # 2) per (asset,venue): order by ts, assign episodes (new episode whenever age==0 or age drops),
    #    index each row by micro_sig -> (onset_ts, onset_micros, age, ts)
    sig_index: dict[tuple, dict] = {}     # (asset,venue,sig) -> provenance+onset
    for (a, v), slot in av_rows.items():
        rows = [slot[t] for t in sorted(slot)]
        cur_onset = None
        prev_age = None
        for r in rows:
            age = int(float(r.get("trade_age_chunks") or 0))
            if cur_onset is None or age == 0 or (prev_age is not None and age < prev_age):
                cur_onset = r            # this row starts a new episode -> it is the onset
            prev_age = age
            onset = cur_onset
            sig = (a, v, micro_sig(r))
            # keep the FIRST occurrence per sig (deterministic); winners match a unique sig anyway
            if sig not in sig_index:
                sig_index[sig] = {
                    "row_ts": float(r.get("ts_utc") or 0),
                    "row_age": age,
                    "row_stage": r.get("trade_stage") or "",
                    "onset_ts": float(onset.get("chunk_end_ts_utc") or onset.get("ts_utc") or 0),
                    "onset_market_ts": float(onset.get("chunk_end_ts_utc") or 0),
                    "onset_chunk_id": onset.get("chunk_id") or "",
                    "onset_micros": {k: float(onset.get(k) or 0.0) for k in MICRO_KEYS},
                }

    # 3) join winners -> onset
    OUT.mkdir(parents=True, exist_ok=True)
    out_rows = []
    print(f"\n{'cell':18s} {'win':>5s} {'matched':>7s} {'onset_moved':>11s} {'rerun%':>7s} {'med_age':>7s}")
    grand = defaultdict(int)
    for cell in CELLS:
        fp = CLEAN / f"markets_{cell}_win.clean.json"
        if not fp.exists():
            continue
        entries = json.loads(fp.read_text(encoding="utf-8")).get("entries", [])
        a, v = entries[0]["asset"], entries[0]["venue"] if entries else (None, None)
        matched = moved = 0
        ages = []
        for e in entries:
            a, v, side = e["asset"], e["venue"], e["side"]
            sig = (a, v, micro_sig(e))
            prov = sig_index.get(sig)
            if prov is None:
                continue
            matched += 1
            ages.append(prov["row_age"])
            old_anchor = float(e.get("entry_ts_utc") or 0)
            onset_ts = prov["onset_ts"]
            onset_moved = abs(onset_ts - old_anchor) > ONSET_MOVE_TOL_S
            if onset_moved:
                moved += 1
            out_rows.append({
                "cell": cell, "source_id": e.get("source_id"), "side": side,
                "asset": a, "venue": v,
                "old_entry_ts_utc": old_anchor,
                "true_onset_ts_utc": onset_ts,
                "onset_chunk_id": prov["onset_chunk_id"],
                "row_age_chunks": prov["row_age"], "row_stage": prov["row_stage"],
                "onset_moved": onset_moved,
                "onset_micros": prov["onset_micros"],
                "stored_micros": {k: float(e.get(k) or 0.0) for k in MICRO_KEYS},
                "net_bps": e.get("net_bps"), "horizon_minutes": e.get("horizon_minutes"),
            })
        med_age = sorted(ages)[len(ages) // 2] if ages else 0
        rerun_pct = (100.0 * moved / matched) if matched else 0.0
        print(f"{cell:18s} {len(entries):>5d} {matched:>7d} {moved:>11d} {rerun_pct:>6.1f}% {med_age:>7d}")
        grand["win"] += len(entries); grand["matched"] += matched; grand["moved"] += moved
    print("-" * 64)
    print(f"{'TOTAL':18s} {grand['win']:>5d} {grand['matched']:>7d} {grand['moved']:>11d} "
          f"{100.0*grand['moved']/max(1,grand['matched']):>6.1f}%")
    (OUT / "winner_onsets.json").write_text(json.dumps(out_rows, indent=1), encoding="utf-8")
    print(f"\nwrote {len(out_rows)} winner->onset rows to {OUT/'winner_onsets.json'}")
    print(f"COEFF RE-RUN SET (onset_moved): {grand['moved']} winners")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
