#!/usr/bin/env python3
"""C2C-004 smoke test: drive the read-only server over stdio as a real MCP client.

Covers tool discovery, repo status, one safe text read, and - the part that matters - the
NEGATIVE cases. A read tool that returns the right file proves nothing on its own; what has to be
shown is that it refuses the wrong ones. Every refusal below is exercised through the live MCP
transport, not by calling the helper directly.
"""
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "markets_mcp_readonly.py")


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[SERVER])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()

            tools = await s.list_tools()
            names = sorted(t.name for t in tools.tools)
            print("TOOLS_DISCOVERED", json.dumps(names))
            assert names == ["markets_read_file", "markets_repo_status"], names

            st = await s.call_tool("markets_repo_status", {})
            status = json.loads(st.content[0].text)
            print("REPO_PATH  ", status["repo_path"])
            print("REPO_BRANCH", status["branch"])
            print("REPO_HEAD  ", status["head"])
            assert status["read_only"] is True

            ok = await s.call_tool("markets_read_file", {"path": "research/kalshi/per_event.py"})
            body = ok.content[0].text
            allowed = not body.startswith("REFUSED:")
            print("READ_ALLOWED_SAFE_FILE", allowed, "| bytes", len(body))
            assert allowed, body[:200]

            print()
            print("--- negative cases (each must REFUSE) ---")
            cases = [
                ("traversal out of repo", "../../etc/passwd"),
                ("absolute outside repo", "/etc/passwd"),
                ("home credential file", os.path.expanduser("~/.config/markets/env")),
                ("aws credentials", os.path.expanduser("~/.aws/credentials")),
                ("deny-listed name in repo", "research/kalshi/creds.py.env"),
                ("oversize file (>256KB)", "OPEN_ITEMS.md"),
                ("binary file", "research/kalshi/records/S118/g18_s118_curve.png"),
                ("sibling-prefix dir", "/home/user/Markets-secrets/x.txt"),
                ("empty path", ""),
            ]
            failures = []
            for label, path in cases:
                r = await s.call_tool("markets_read_file", {"path": path})
                txt = r.content[0].text
                refused = txt.startswith("REFUSED:")
                print("%-26s %-8s %s" % (label, "REFUSED" if refused else "*ALLOWED*",
                                         txt.split("\n")[0][:90]))
                if not refused:
                    failures.append((label, path))

            print()
            if failures:
                print("SMOKE_FAIL", json.dumps(failures))
                return 1
            print("SMOKE_PASS all negative cases refused; discovery, status and safe read OK")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
