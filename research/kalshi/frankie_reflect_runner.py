#!/usr/bin/env python3
"""Nightly bounded reflection runner for Frankie; generates proposals, never applies them."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_backends import backend_from_name  # noqa: E402
from frankie_core import FrankieConfig, GateStop  # noqa: E402
from frankie_reflect import reflect  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--min-resolved", type=int, default=5)
    parser.add_argument("--proposer", choices=("bedrock", "openai"))
    parser.add_argument("--critic", choices=("bedrock", "openai"))
    args = parser.parse_args()
    config = FrankieConfig.from_env()
    try:
        result = reflect(
            config=config,
            proposer=backend_from_name(args.proposer or config.primary_backend, config),
            critic=backend_from_name(args.critic or config.critic_backend, config),
            limit=args.limit,
            min_resolved=args.min_resolved,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except GateStop as exc:
        print(f"STOP - {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR - {type(exc).__name__}: {str(exc)[:2000]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
