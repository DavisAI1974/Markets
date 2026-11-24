"""Write decision.json for one question. `serve` does the validating.

  python3 -m tools.decider.answer --mailbox <folder> --sequence N --action take|skip --why "<one sentence>"
        --rests-on <id> [<id> ...]
"""

import argparse
import sys
from pathlib import Path

from .serve import write_json


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mailbox", required=True)
    ap.add_argument("--sequence", type=int, required=True)
    ap.add_argument("--action", required=True)
    ap.add_argument("--why", required=True)
    ap.add_argument("--rests-on", nargs="*", default=[])
    a = ap.parse_args(argv)
    box = Path(a.mailbox) / f"q-{a.sequence}"
    if not box.is_dir():
        print(f"no question {a.sequence} in {a.mailbox}", file=sys.stderr)
        return 1
    if (box / "decision.json").exists():
        print(f"q-{a.sequence} already has a decision; it is not rewritten", file=sys.stderr)
        return 1
    write_json(box / "decision.json", {"action": a.action, "why": a.why, "rests_on": a.rests_on})
    print(f"wrote {box / 'decision.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
