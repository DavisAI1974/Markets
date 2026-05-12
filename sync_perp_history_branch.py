"""sync_perp_history_branch.py — pull durable perp histories from git branch.

Copies `backend_funding_history.jsonl` and `backend_oi_history.jsonl` from the
shared `data/perp-history` branch into the local repo root (or a custom output
directory) so offline research can consume the remotely-collected history.
"""

from __future__ import annotations

import argparse
import json

from market_history_features import sync_history_from_data_branch


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", default=None)
    p.add_argument("--fetch-remote", action="store_true")
    p.add_argument("--remote", default="origin")
    p.add_argument("--output-json", default=None)
    args = p.parse_args()

    synced = sync_history_from_data_branch(
        output_dir=args.output_dir,
        fetch_remote=args.fetch_remote,
        remote=args.remote,
    )
    if args.output_json:
        with open(args.output_json, "w") as fh:
            json.dump({"synced": synced}, fh, indent=2)
    if not synced:
        print("[perp-history-sync] no newer branch files found")
        return
    for filename, meta in synced.items():
        print(
            f"[perp-history-sync] {filename} <- {meta['source_ref']} "
            f"({meta['replaced_lines']} -> {meta['lines']} lines)"
        )


if __name__ == "__main__":
    main()
