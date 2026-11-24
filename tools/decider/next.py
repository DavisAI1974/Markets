"""Print the brief of the lowest-sequence question that has a brief and no decision yet.

  python3 -m tools.decider.next --mailbox <folder> [--wait-s N]
"""

import argparse
import sys
import time
from pathlib import Path

from .serve import question_folders


def waiting(mailbox):
    for box in question_folders(Path(mailbox)):
        if (box / "brief.md").exists() and not (box / "decision.json").exists() and not (box / "answer.json").exists():
            return box
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mailbox", required=True)
    ap.add_argument("--wait-s", type=float, default=0)
    a = ap.parse_args(argv)
    end = time.monotonic() + a.wait_s
    while True:
        box = waiting(a.mailbox)
        if box:
            sys.stdout.write((box / "brief.md").read_text(encoding="utf8"))
            return 0
        if time.monotonic() >= end:
            print("none is waiting")
            return 0
        time.sleep(min(0.5, max(0.0, end - time.monotonic())))


if __name__ == "__main__":
    sys.exit(main())
