from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from feature_store import write_onchain_features
from onchain_features import build_onchain_features
from onchain_providers import make_onchain_provider


DEFAULT_ASSETS = ["BTC", "ETH"]


def run(
    *,
    provider_name: str,
    assets: list[str],
    interval_seconds: int,
    window_minutes: int,
    once: bool = False,
) -> None:
    provider = make_onchain_provider(provider_name)
    while True:
        now = datetime.now(timezone.utc)
        for asset in assets:
            features = build_onchain_features(
                provider,
                asset,
                now=now,
                window_minutes=window_minutes,
            )
            write_onchain_features(asset, features)
        if once:
            return
        time.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="nansen", choices=["nansen", "amberdata"])
    parser.add_argument("--assets", default=",".join(DEFAULT_ASSETS))
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--window-minutes", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    assets = [a.strip().upper() for a in args.assets.split(",") if a.strip()]
    run(
        provider_name=args.provider,
        assets=assets or DEFAULT_ASSETS,
        interval_seconds=max(60, int(args.interval_seconds)),
        window_minutes=max(5, int(args.window_minutes)),
        once=bool(args.once),
    )


if __name__ == "__main__":
    main()
