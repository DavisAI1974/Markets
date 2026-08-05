#!/usr/bin/env python3
"""
standdown_ledger.py - the SAVES. Every time a specialist talked itself out of firing a play, with
what the day actually did. (Greg, S112.)

WHY THIS IS THE MISSING HALF OF THE EVIDENCE BASE
-------------------------------------------------
Greg: "I also think we should have the instances where the agents talked themselves out of a bad
decision correctly in there too with past instances and the rest."

The brain records what a play does when it FIRES. It has never recorded what happened when a play
was evaluated and DECLINED - and three separate measurements say the declines are where the value is:

  - D25: "STAND DOWN produced the saves" - E-0717's counter-fade stand-down, where firing would have
    inverted a correct sign; C-0701's accumulation arm on three measured legs; D-0625's already-priced
    limb. The same decision line records that OVERRIDE produced the disasters.
  - The S112 audit, batch 0, measured on the committed record: across G22+G23 its eleven plays carry
    66 explicit invocations and 47 are STAND-DOWNS, with four plays standing down on every single
    appearance. The modern blind is running largely on these plays' ABSENCE, and none of that is
    evidence anywhere.
  - A correct decline is the FALSIFIABLE HALF of a play. It is the only direct proof the mechanism
    has a working off-switch - which is precisely what a non-falsifiable play lacks (A's S106 finding:
    covering-self-limiting pointed DOWN whether it fired or not, so it could never be wrong). The one
    play whose record already counts declines - the C1 band-break, "five fires, ONE CORRECT DECLINE,
    zero false positives" - is the strongest-evidenced gate on the desk. That is not a coincidence and
    this file generalises it.

AND IT IS THE NATURAL INPUT TO NO CALL (A-2). Greg's framing of the measurement problem was "we
didn't have a 'no call' option so we had to pick something and it would make something up to justify
its guess." True at the DAY level - the output contract forces a number. But at the PLAY level the
specialists have been declining all along, in writing, with reasons. The corpus of correct declines
is where the no-call signal already lives, and it is free.

MECHANICAL, NOT AGENTIC. `plays_stood_down`, `plays_fired`, `stand_down_reasons` and
`evidence_rejected` are structured fields in the committed per-day posteriors, so this needs no
subagents and is exactly reproducible.

HONEST ABOUT WHAT IT CANNOT DECIDE. Whether a decline was CORRECT needs a counterfactual - what the
play would have emitted had it fired - and that is not in the record for most entries. So this tool
extracts the decline, the stated reason and the realized outcome, and marks `counterfactual_stated`
only where the specialist itself wrote one ("firing it would have inverted...", "would have capped
..."). Everything else is recorded as a decline with its outcome and left for adjudication. Guessing
the counterfactual would manufacture exactly the outcome-credited evidence the audit exists to catch.

USAGE
    python standdown_ledger.py build            # -> STANDDOWN_LEDGER_S112.json + summary
    python standdown_ledger.py top              # plays ranked by decline count
    python standdown_ledger.py saves            # only the entries with a stated counterfactual
"""

import glob
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FC = os.path.join(HERE, "forecasts")
RN = os.path.join(HERE, "renders", "ng_refine_s95")
OUT = os.path.join(HERE, "STANDDOWN_LEDGER_S112.json")

PLAY_ID = re.compile(r"^\s*[\"']?([a-z_]+\.[a-z0-9_]+)")
# phrases in which a specialist states the counterfactual itself - the only basis on which this
# tool will call a decline a SAVE
CF = re.compile(r"would have|had it fired|firing it|if fired|would\s+(?:be|invert|cap|flip|"
                r"produce|emit)|inverted a correct|saved the", re.I)


def brain_ids():
    with open(os.path.join(HERE, "knowledge", "ng_brain.json"), encoding="utf-8") as f:
        return {p["id"] for p in json.load(f)["plays"]}


def actuals():
    """date -> realized day move, from the committed actual files."""
    out = {}
    for f in glob.glob(os.path.join(RN, "g*_actual.json")):
        g = re.search(r"g(\d+)_actual", f).group(1)
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        # the actual files carry days as a LIST of records keyed by a `date` FIELD, not as a
        # date-keyed dict. The first version of this walker looked for the dict shape and joined
        # ZERO of 707 entries - a silent miss that would have shipped every instance with a null
        # outcome, which is the served-but-empty defect this desk keeps finding in its own feeds.
        def walk(o):
            if isinstance(o, dict):
                dt = str(o.get("date", ""))
                if re.fullmatch(r"\d{8}", dt):
                    for cand in ("day_move_usd", "net_usd", "day_move", "actual_day_move_usd"):
                        if isinstance(o.get(cand), (int, float)):
                            out[dt] = (int(o[cand]), "g" + g)
                            break
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(d)
    return out


def _iter_entries(obj, path=""):
    """Yield (kind, text, context_date) for every stand-down / fired entry anywhere in a posterior."""
    if isinstance(obj, dict):
        date = obj.get("date") if re.fullmatch(r"\d{8}", str(obj.get("date", ""))) else None
        for k, v in obj.items():
            if k in ("plays_stood_down", "stand_down_reasons") and isinstance(v, list):
                for e in v:
                    if isinstance(e, str):
                        yield ("stood_down", e, date)
            elif k == "plays_fired" and isinstance(v, list):
                for e in v:
                    if isinstance(e, str):
                        yield ("fired", e, date)
            else:
                for r in _iter_entries(v, path):
                    yield (r[0], r[1], r[2] or date)
    elif isinstance(obj, list):
        for v in obj:
            for r in _iter_entries(v, path):
                yield r


def build():
    ids = brain_ids()
    act = actuals()
    rows = []
    for f in sorted(glob.glob(os.path.join(FC, "**", "*.json"), recursive=True)):
        rel = os.path.relpath(f, ROOT)
        base = os.path.basename(f)
        m = re.search(r"grp?(\d+)", base)
        grp = "g" + m.group(1) if m else None
        spec = None
        ms = re.search(r"_([A-E])_(\d{8})|_specialist_([A-E])|_([A-E])_r2", base)
        if ms:
            spec = ms.group(1) or ms.group(3) or ms.group(4)
        fdate = re.search(r"(\d{8})", base)
        mode = "refine" if ("refine" in rel or "_r2" in base or "refined" in base) else "blind"
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for kind, text, ctx_date in _iter_entries(d):
            pm = PLAY_ID.match(text)
            if not pm or pm.group(1) not in ids:
                continue
            date = ctx_date or (fdate.group(1) if fdate else None)
            a = act.get(date)
            rows.append({
                "play_id": pm.group(1), "action": kind, "date": date,
                "group": grp, "specialist": spec, "mode": mode,
                "source_file": rel,
                "reason": text.strip()[:900],
                "day_move_usd": a[0] if a else None,
                "counterfactual_stated": bool(CF.search(text)),
            })
    # de-duplicate: the same decline can appear in a per-day file and again in the merged file
    seen, uniq = set(), []
    for r in rows:
        k = (r["play_id"], r["date"], r["action"], r["reason"][:120])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq


def cmd_build(_):
    rows = build()
    per = defaultdict(lambda: {"stood_down": 0, "fired": 0, "cf": 0})
    for r in rows:
        per[r["play_id"]][r["action"]] += 1
        if r["counterfactual_stated"]:
            per[r["play_id"]]["cf"] += 1
    out = {
        "note": ("THE SAVES. Every recorded decline of a brain play, with the stated reason and the "
                 "day's realized move. Built mechanically from the committed posteriors - no agents, "
                 "exactly reproducible. `counterfactual_stated` is true ONLY where the specialist "
                 "itself wrote what firing would have done; correctness is NOT inferred, because "
                 "guessing the counterfactual would manufacture the outcome-credited evidence the "
                 "S112 audit exists to catch."),
        "session": "S112",
        "n_entries": len(rows),
        "entries": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    sd = sum(1 for r in rows if r["action"] == "stood_down")
    fi = len(rows) - sd
    cf = sum(1 for r in rows if r["counterfactual_stated"])
    dated = sum(1 for r in rows if r["day_move_usd"] is not None)
    print("entries %d  |  stand-downs %d  |  fires %d  |  plays covered %d"
          % (len(rows), sd, fi, len(per)))
    print("with a stated counterfactual (candidate SAVES): %d" % cf)
    print("joined to a realized day move: %d" % dated)
    print("\nwrote %s" % os.path.relpath(OUT, ROOT))
    return 0


def cmd_top(_):
    rows = build()
    per = defaultdict(lambda: {"stood_down": 0, "fired": 0, "cf": 0})
    for r in rows:
        per[r["play_id"]][r["action"]] += 1
        if r["counterfactual_stated"]:
            per[r["play_id"]]["cf"] += 1
    print("%-56s %6s %6s %6s" % ("play", "declin", "fired", "c/fact"))
    print("-" * 78)
    for pid, c in sorted(per.items(), key=lambda kv: -kv[1]["stood_down"])[:28]:
        print("%-56s %6d %6d %6d" % (pid[:56], c["stood_down"], c["fired"], c["cf"]))
    never = [p for p, c in per.items() if c["fired"] == 0 and c["stood_down"] > 0]
    print("\n  plays that have NEVER fired in the record, only declined: %d" % len(never))
    for p in sorted(never)[:12]:
        print("     %s" % p)
    return 0


def cmd_saves(_):
    rows = [r for r in build() if r["counterfactual_stated"] and r["action"] == "stood_down"]
    print("%d declines where the specialist STATED what firing would have done\n" % len(rows))
    for r in sorted(rows, key=lambda x: (x["play_id"], str(x["date"])))[:24]:
        print("  %-46s %s %s  day %s" % (r["play_id"][:46], r["date"], r["group"],
                                         r["day_move_usd"]))
        print("      %s" % r["reason"][:200].replace("\n", " "))
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    return {"build": cmd_build, "top": cmd_top, "saves": cmd_saves}.get(
        sys.argv[1], lambda _: (print(__doc__), 1)[1])(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
