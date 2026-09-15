"""Launch a NEW actual Sunday host on a verified >=16-logical-CPU GitHub runner.

CPU budgets are explicit environment inputs chosen after benchmark. The first launch
refuses Windows-local paths and an existing run directory. Recovery of the same new
GitHub run requires FRANKIE_GITHUB_RECOVERY=1 and an identical runtime identity receipt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from research.kalshi.frankie_boss.cpu_runtime import (
    configure_cpu_runtime, policy_from_environment,
)

_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def _walk(value, location="configuration"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{location}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _walk(item, f"{location}[{index}]")
    elif isinstance(value, str):
        yield location, value


def _configuration_path(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--configuration", required=True)
    args, _ = parser.parse_known_args(argv)
    return Path(args.configuration)


def _save_identity(path, body):
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise RuntimeError("GitHub runtime identity differs from the retained run")
        return
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    temporary.rename(path)


def _guard_and_record(configuration_path, cpu_receipt):
    raw = configuration_path.read_bytes()
    configuration = json.loads(raw)
    if type(configuration) is not dict or type(configuration.get("run_id")) is not str or not configuration["run_id"]:
        raise RuntimeError("explicit new GitHub run_id required")
    for location, value in _walk(configuration):
        if _WINDOWS_ABSOLUTE.match(value):
            raise RuntimeError(f"GitHub configuration still contains local Windows path at {location}")
    run_directory = Path(configuration["run_directory"])
    recovery = os.environ.get("FRANKIE_GITHUB_RECOVERY") == "1"
    if run_directory.exists() and not recovery:
        raise RuntimeError("new GitHub run_id/run_directory already exists; refuse accidental cycle-0 reuse")
    if recovery and not run_directory.is_dir():
        raise RuntimeError("GitHub recovery requested but retained run directory is missing")
    run_directory.mkdir(parents=True, exist_ok=recovery)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    identity = dict(schema="FRANKIE_GITHUB_RUNTIME_IDENTITY_V1",
        run_id=configuration["run_id"], configuration_sha256=hashlib.sha256(raw).hexdigest(),
        code_commit=commit, cpu=cpu_receipt)
    _save_identity(run_directory / "github-runtime-identity.json", identity)
    return configuration


def main():
    configuration_path = _configuration_path(sys.argv[1:])
    policy = policy_from_environment()
    cpu_receipt = configure_cpu_runtime(policy)
    _guard_and_record(configuration_path, cpu_receipt)
    from research.kalshi.frankie_boss.operations.run_actual_sunday import main as actual_main
    return actual_main()


if __name__ == "__main__":
    raise SystemExit(main())
