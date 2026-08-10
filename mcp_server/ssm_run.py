#!/usr/bin/env python3
"""Run a shell command on the durable box over SSM and return its output.

Kept in the repo rather than a scratchpad (D34/D52): every C2C-005 deployment step runs through
this, so the deployment is reproducible from git alone.

    python mcp_server/ssm_run.py "uname -a"
"""
from __future__ import annotations

import sys, time, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "research", "kalshi"))
import creds  # noqa: E402

INSTANCE = os.environ.get("MARKETS_BOX", "i-08cee7171c0a76a04")
REGION = os.environ.get("MARKETS_BOX_REGION", "us-east-2")


def run(cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    ssm = creds.aws_client("ssm", REGION)
    r = ssm.send_command(InstanceIds=[INSTANCE], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": [cmd], "executionTimeout": [str(timeout)]})
    cid = r["Command"]["CommandId"]
    deadline = time.time() + timeout + 60
    while time.time() < deadline:
        time.sleep(3)
        try:
            inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if inv["Status"] in ("Pending", "InProgress", "Delayed"):
            continue
        return (inv.get("ResponseCode", -1), inv.get("StandardOutputContent", ""),
                inv.get("StandardErrorContent", ""))
    return (-1, "", "TIMED OUT waiting for SSM invocation %s" % cid)


if __name__ == "__main__":
    code, out, err = run(sys.argv[1])
    if out:
        print(out, end="")
    if err:
        print("--- stderr ---", file=sys.stderr)
        print(err, end="", file=sys.stderr)
    raise SystemExit(0 if code == 0 else 1)
