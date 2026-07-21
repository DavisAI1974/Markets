#!/usr/bin/env python3
"""Restart the live NG collector when its process or heartbeat becomes stale.

Designed for a systemd timer. It never interacts with historical collection jobs.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

SERVICE = os.getenv("NG_LIVE_SERVICE", "markets-ng-live.service")
HEALTH = Path(os.getenv("NG_LIVE_HEALTH_FILE", "/var/lib/markets/ng_live/health.json"))
MAX_RECORD_AGE_MS = float(os.getenv("NG_LIVE_WATCHDOG_MAX_AGE_MS", "120000"))
START_GRACE_S = float(os.getenv("NG_LIVE_WATCHDOG_START_GRACE_S", "120"))


def systemctl(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", *args],
        text=True,
        capture_output=True,
        check=check,
    )


def restart(reason: str) -> int:
    print(f"[ng-live-watchdog] restart: {reason}", flush=True)
    result = systemctl("restart", SERVICE)
    if result.returncode != 0:
        print(result.stderr.strip(), flush=True)
    return result.returncode


def main() -> int:
    if systemctl("is-active", "--quiet", SERVICE).returncode != 0:
        return restart("service is not active")

    if not HEALTH.exists():
        active = systemctl("show", SERVICE, "-p", "ActiveEnterTimestampMonotonic", "--value")
        # The service is active but has not yet produced health. Give initial auth
        # and snapshot processing a grace period before restarting.
        if active.returncode == 0 and active.stdout.strip():
            try:
                entered_us = int(active.stdout.strip())
                uptime_s = float(Path("/proc/uptime").read_text().split()[0])
                boot_us = int(uptime_s * 1_000_000)
                if boot_us - entered_us < START_GRACE_S * 1_000_000:
                    return 0
            except (OSError, ValueError, IndexError):
                pass
        return restart("health.json is missing")

    try:
        payload = json.loads(HEALTH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return restart(f"health.json unreadable: {error}")

    connection = str(payload.get("connection", "unknown"))
    if connection == "error":
        return restart(f"collector reported error: {payload.get('last_error')}")

    record_age = payload.get("record_age_ms")
    if record_age is not None:
        try:
            if float(record_age) > MAX_RECORD_AGE_MS:
                return restart(f"record heartbeat stale: {float(record_age):.0f} ms")
        except (TypeError, ValueError):
            return restart("invalid record_age_ms")

    # The health writer itself must remain alive even when the exchange is quiet.
    try:
        updated = datetime.fromisoformat(str(payload["updated_at"]))
        health_age = time.time() - updated.timestamp()
        if health_age > MAX_RECORD_AGE_MS / 1000:
            return restart(f"health writer stale: {health_age:.0f} s")
    except (KeyError, TypeError, ValueError):
        return restart("invalid updated_at")

    print(
        f"[ng-live-watchdog] ok connection={connection} "
        f"record_age_ms={record_age} bytes={payload.get('archive_bytes', 0)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
