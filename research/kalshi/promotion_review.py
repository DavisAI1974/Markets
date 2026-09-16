#!/usr/bin/env python3
"""promotion_review.py - the play promotion/retirement REVIEW (S110 memo 1.4). Reporter only.

The gap it closes: 46 PROVISIONAL plays accumulate forward evidence nobody schedules a review of
(2 of 68 STABLE at S110). This scanner reads knowledge/ng_brain.json and LISTS, per play:
status, a forward-evidence read (confirmed / mixed / none-yet / refuted-language), and whether it
is a PROMOTION or RETIREMENT candidate under the S110 cadence rule:

  promotion candidate:  forward evidence names >=3 confirming instances across >=2 groups
  retirement candidate: refuted twice in its own scope, or forward_evidence still NONE after
                        3+ groups of eligibility

IT NEVER EDITS THE BRAIN. Output feeds the merge adjudication (proposal + Greg's go), per D8.
Text-heuristic honestly labeled: forward_evidence is prose; this flags FOR HUMAN REVIEW, it does
not decide. Run at every group close-out (SOP STEP 7).
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")

CONFIRM = re.compile(r"forward[- ]confirmed|confirmed|delivered|held on g\d+|survives", re.I)
REFUTE = re.compile(r"refut|failed|false positive|did not deliver|wrong[- ]sign|retract", re.I)
NONE_YET = re.compile(r"\bnone\b|none[- ]yet|no forward", re.I)


def group_mentions(txt: str) -> set[str]:
    return set(re.findall(r"\bg(\d{1,2})\b", txt.lower())) | set(re.findall(r"\bG(\d{1,2})\b", txt))


def main() -> int:
    b = json.load(open(BRAIN, encoding="utf-8"))
    plays = b["plays"]
    promo, retire, quiet = [], [], []
    print(f"PROMOTION REVIEW - {len(plays)} plays, brain {(b.get('meta') or {}).get('version', '?')}")
    print(f"{'id':44} {'status':22} {'fwd-read':10} groups")
    for p in plays:
        pid = str(p.get("id", "?"))[:43]
        status = str(p.get("status", "?")).split(" ")[0][:21]
        fe = str(p.get("forward_evidence", ""))
        gs = group_mentions(fe)
        if REFUTE.search(fe) and len(REFUTE.findall(fe)) >= 2:
            read = "refuted-2x"
            retire.append(pid)
        elif CONFIRM.search(fe) and len(gs) >= 2:
            read = "confirmed"
            if status.startswith("PROVISIONAL") or status.startswith("PROPOSED"):
                promo.append(pid)
        elif NONE_YET.search(fe) or not fe.strip():
            read = "none-yet"
            quiet.append(pid)
        else:
            read = "mixed"
        print(f"{pid:44} {status:22} {read:10} {','.join(sorted(gs, key=int)) or '-'}")
    print("\nPROMOTION CANDIDATES (>=confirming evidence spanning >=2 groups, still PROVISIONAL/PROPOSED):")
    for x in promo:
        print("  +", x)
    print("RETIREMENT CANDIDATES (refuted-language x2 in forward evidence):")
    for x in retire or ["(none)"]:
        print("  -", x)
    print(f"QUIET ({len(quiet)} plays with no forward evidence yet) - list on request")
    print("\nReporter only - candidates go to the merge proposal for adjudication (D8). "
          "Text-heuristic: verify each candidate against its posteriors before proposing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
