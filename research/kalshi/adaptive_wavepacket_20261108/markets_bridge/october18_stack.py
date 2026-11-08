"""Reconcile and compare four nested October 18 paper candidates on saved evidence."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPLAY = Path("artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1")
SIGNALS = REPLAY / "historical-paper-replay-v1/every-early-falling-touch-signal.jsonl.gz"
TRADES = REPLAY / "local-liquidity-v1/every-trade-local-liquidity-links.jsonl.gz"
PILOT = ("85c16576c:research/kalshi/adaptive_wavepacket_20261108/markets_bridge/"
         "october18_book_entropy_pilot/october18_book_entropy_pilot.jsonl.gz")
ARMS = ("BASELINE", "ENTROPY", "SAME_GROUP_PRINT", "ENTROPY_AND_PRINT")


def read_gzip(data):
    return [json.loads(line) for line in gzip.decompress(data).splitlines()]


def main(ledger_path):
    sources = {
        str(SIGNALS): SIGNALS.read_bytes(),
        str(TRADES): TRADES.read_bytes(),
        PILOT: subprocess.check_output(["git", "show", PILOT]),
    }
    signals, trades, pilot = (read_gzip(data) for data in sources.values())
    by_close = defaultdict(list)
    for link in trades:
        if link["window_book_line"] is not None:
            by_close[link["window_book_line"]].append(link)
    counts = defaultdict(Counter)
    support = Counter()
    dispositions = Counter()
    with ledger_path.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as out:
        for line, (signal, row) in enumerate(zip(signals, pilot, strict=True), 1):
            quote = signal["signal"]
            if row["signal_line"] != line or row["signal"] != quote or row["side"] != signal["side"]:
                raise ValueError(f"Pilot provenance mismatch on signal line {line}")
            links = by_close[quote["book_line"]]
            if sorted(link["trade_ordinal"] for link in links) != sorted(signal["original_t_ordinals_at_signal"]):
                raise ValueError(f"Print link mismatch on signal line {line}")
            for link in links:
                clocks = link["exact_clocks"]
                if (link["original_trade"]["instrument_id"] != "150611"
                        or clocks["group_close_input_cursor"] != quote["cursor"]
                        or clocks["trade_input_cursor"] > quote["cursor"]
                        or clocks["available_ns"] > quote["known_by_ns"]):
                    raise ValueError(f"Print was outside signal scope on line {line}")
            print_present = bool(links)
            has_entropy = row["overlay"] in {"TAKE", "SKIP_NO_COMPRESSION"}
            entropy = row["overlay"] == "TAKE" if has_entropy else None
            arms = dict(zip(ARMS, (True, entropy, print_present,
                                   entropy and print_present if has_entropy else None), strict=True))
            side = row["side"]
            support[side, "ALL"] += 1
            if has_entropy:
                support[side, "COMMON"] += 1
            dispositions[side, row["overlay"]] += 1
            for arm, selected in arms.items():
                if selected:
                    for horizon, outcome in row["baseline_outcomes"].items():
                        label = outcome["midpoint_result"]
                        if arm in {"BASELINE", "SAME_GROUP_PRINT"}:
                            counts[side, "ALL", arm, horizon][label] += 1
                        if has_entropy:
                            counts[side, "COMMON", arm, horizon][label] += 1
            record = {
                "signal_line": line, "side": side, "signal": quote,
                "known_print_ordinals": signal["original_t_ordinals_at_signal"],
                "entropy_disposition": row["overlay"], "arms": arms,
                "entry": row["entry"], "outcomes": row["baseline_outcomes"],
            }
            out.write((json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n").encode())
    print(json.dumps({
        "source_sha256": {path: hashlib.sha256(data).hexdigest() for path, data in sources.items()},
        "signals": len(signals), "arms": ARMS,
        "support": [[*key, count] for key, count in sorted(support.items())],
        "entropy_dispositions": [[*key, count] for key, count in sorted(dispositions.items())],
        "outcomes": [[*key, dict(counts[key])] for key in sorted(counts)],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
