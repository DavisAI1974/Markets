#!/usr/bin/env python3
"""Best-effort upload of live NG DBN files left by an abrupt prior exit.

Always exits zero so an S3 outage never prevents fresh market-data collection.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

LOCAL_DIR = Path(os.getenv("NG_LIVE_LOCAL_DIR", "/var/lib/markets/ng_live"))
BUCKET = os.getenv("NG_LIVE_S3_BUCKET", "bento-568968024170-us-east-2-an")
PREFIX = os.getenv("NG_LIVE_S3_PREFIX", "nymex/live/ng").strip("/")
KEEP_LOCAL = os.getenv("NG_LIVE_KEEP_LOCAL", "0") == "1"
NAME = re.compile(r"^NG_live_(\d{8})T\d{6}Z\.dbn$")


def main() -> int:
    if not LOCAL_DIR.exists():
        return 0
    files = sorted(LOCAL_DIR.glob("NG_live_*.dbn"))
    if not files:
        return 0
    try:
        import boto3

        s3 = boto3.client("s3")
    except Exception as error:
        print(f"[ng-live-recover] S3 client unavailable: {error}", flush=True)
        return 0

    for path in files:
        match = NAME.match(path.name)
        if not match or path.stat().st_size == 0:
            continue
        try:
            day = datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
            key = f"{PREFIX}/{day:%Y/%m/%d}/{path.name}"
            s3.upload_file(str(path), BUCKET, key)
            print(f"[ng-live-recover] uploaded s3://{BUCKET}/{key}", flush=True)
            if not KEEP_LOCAL:
                path.unlink(missing_ok=True)
        except Exception as error:
            print(f"[ng-live-recover] retained {path}: {error}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
