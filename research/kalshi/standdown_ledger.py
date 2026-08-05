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

# NOT A DECLINE AT ALL. The harvester matches a leading play id inside plays_stood_down, and the
# S112 decline audit found three ways that over-collects - each caught by an auditor, none by me:
#   (a) THE PLAY FIRED. A refine row reads "flow.price_free_absorption_proxy: not stood down - it
#       FIRED and it MIS-READ". Imported as a decline it would have entered the brain as a CORRECT
#       DECLINE on a day the instrument leaned the wrong way: outcome-credit manufactured by the
#       collector rather than earned by a specialist.
#   (b) THE PLAY WAS APPLIED to stand something ELSE down - "boundary.chain_staleness_gate -
#       APPLIED as a stand-down, not as a fire". That is the gate WORKING, recorded as a decline
#       OF the gate.
#   (c) THE RULE WAS OBEYED. boundary.chain_label_must_track_realized_cum says do not assert a
#       chain label without cum; "I therefore assert NO chain polarity and NO chain age" is
#       compliance, not a judgment about the market.
# These are recorded as NOT_A_DECLINE rather than dropped, because the row is real evidence about
# the play - just not evidence of an off-switch. Signatures are built from the committed text of
# the rows the auditors named, never guessed.
NOT_A_DECLINE = re.compile(
    r"not stood down|it FIRED|APPLIED as a stand-?down|applied,? not as a fire|"
    r"rungs? (?:are|is) widened, not asserted|would have been permitted", re.I)


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
                "not_a_decline": bool(NOT_A_DECLINE.search(text)),
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




# ======================================================================================
# THE DECLINE AUDIT (Greg, S112: "Did we audit the declines to make sure they are valid
# reasons?" then "do the same audit for those and fit them into the schema")
#
# THE FLAW THIS FIXES, and it was mine. The ledger above records 384 declines and every one of
# them reads as a save BY CONSTRUCTION - there is no class for a decline that was WRONG. A ledger
# that cannot return a bad verdict is non-falsifiable, which is the exact disease the 82-play audit
# spent all session finding in the plays. Backfilling it as evidence would have committed on the
# declines the same error the audit found on the fires: crediting them without checking the
# mechanism. So the declines get audited, with a rubric that can come back negative.
#
# THE VERDICT SET, and MISSED_FIRE is the one that makes it falsifiable:
#   JUSTIFIED          conditions were evaluable, were evaluated, and correctly said no. Evidence
#                      of a working off-switch - the thing that makes a play falsifiable at all.
#   OUTCOME_CREDITED   declined, the day happened to go the declining way, but the STATED REASON
#                      does not hold on the record. The decline analogue of the S108 signature.
#   MISSED_FIRE        the play should have fired. The decline COST us. Without this class the
#                      whole ledger is self-congratulation.
#   DATA_ABSENT        the play could not be evaluated - input unserved, masked, or dead. NOT
#                      judgment, and it must never be counted as one. Separately valuable: this is
#                      a worked NO CALL trigger (A-2), and the screen already finds ~90 of them.
#   SCOPE              correctly not this day's or this specialist's play. Neutral.
# ======================================================================================

BATCHES = os.path.join(HERE, "STANDDOWN_AUDIT_BATCHES_S112.json")
AUDIT_OUT = os.path.join(HERE, "forecasts", "standdown_audit")
# NOT_A_DECLINE added S112 after the first decline audit found the harvester over-collecting in
# three ways no regex catches reliably (the play FIRED; the play was APPLIED to stand another down;
# the rule was OBEYED). The signature screen in this file catches the explicit cases only - the
# semantic ones need a reader, which is what the auditors are. Same lesson as MISSED_FIRE one level
# down: a classification that cannot say "this is not what you think it is" will not say it.
VERDICTS = ["JUSTIFIED", "OUTCOME_CREDITED", "MISSED_FIRE", "DATA_ABSENT", "SCOPE", "NOT_A_DECLINE"]
REASON_CLASSES = ["MARKET_JUDGMENT", "DATA_ABSENT", "SCOPE"]


def _batch_plays(n):
    with open(BATCHES, encoding="utf-8") as f:
        b = json.load(f)["batches"]
    if not (0 <= n < len(b)):
        raise SystemExit("batch must be 0..%d" % (len(b) - 1))
    return b[n]["plays"]


def cmd_audit_prompt(a):
    n = int(sys.argv[2])
    plays = _batch_plays(n)
    rows = [r for r in json.load(open(OUT, encoding="utf-8"))["entries"]
            if r["action"] == "stood_down" and r["play_id"] in plays]
    with open(os.path.join(HERE, "knowledge", "ng_brain.json"), encoding="utf-8") as f:
        brain = {p["id"]: p for p in json.load(f)["plays"]}
    recs = [{"play": brain[p]} for p in plays if p in brain]
    print("""You are auditing DECLINES - the times a specialist evaluated a brain play and chose NOT to
fire it. Batch %d. This is the companion to the 82-play support audit; the same discipline applies.

WHY DECLINES MATTER. D25 records that STAND DOWN produced this desk's saves while OVERRIDE produced
its disasters. A correct decline is also the FALSIFIABLE HALF of a play - the only direct proof its
mechanism has a working off-switch. The strongest-evidenced gate on the desk (the C1 band-break) is
the one whose record counts "five fires, ONE CORRECT DECLINE, zero false positives".

BUT A LEDGER THAT CANNOT RETURN A BAD VERDICT IS WORTHLESS, so your job is emphatically NOT to
confirm these were good calls. Assign one verdict per decline:

  JUSTIFIED         conditions were evaluable, WERE evaluated, and correctly said no.
  OUTCOME_CREDITED  declined, the day went the declining way, but THE STATED REASON DOES NOT HOLD
                    on the record. The decline analogue of right-answer-wrong-reason.
  MISSED_FIRE       the play SHOULD have fired; the decline cost us. Hunt for these - without them
                    this ledger is self-congratulation. A decline is a MISS when the play's own
                    trigger was satisfied on the served state and the day went the play's way.
  DATA_ABSENT       the play could not be evaluated: input unserved, masked by design, or dead.
                    NOT judgment. Never score it as one.
  SCOPE             correctly not this day's or this specialist's play. Neutral.

METHOD. For each decline you are given the play's full brain record (including its trigger, its
newly-backfilled falsifier and its audited argument), the specialist's verbatim reason, the
source posterior, and the day's REALIZED move. Open the posterior and the served state where you
need them. Ask, in order: (1) was the play's trigger actually evaluable that day from the served
state? (2) if evaluable, was it satisfied? (3) does the stated reason match what the state says?
(4) what would firing have emitted, and how would that have scored against the realized move?

Answer (4) ONLY where the record supports it. If the counterfactual is not determinable, say so -
inventing it manufactures exactly the outcome-credited evidence this audit exists to catch.

OUTPUT - write research/kalshi/forecasts/standdown_audit/batch_%d.json.

THE SHAPE IS THE BRAIN'S OWN INSTANCE SHAPE, DELIBERATELY (Greg, S112): "There should be no
difference in how they are listed in the schema for the brain except one is a do and the other a
don't." So a decline is stored as an ordinary instance with `action` set to "dont" - it is NOT a
separate structure, and it sits in the same instances[] list beside the fires. The audit-only
fields (verdict, reason_class, counterfactual) ride alongside so the decline can be judged; the
instance itself reads the same as any other.

{"batch": %d,
 "declines": [
  {"play_id": "...", "date": "YYYYMMDD", "group": "gN",
   "action": "dont",
   "source_file": "<repo-relative, must exist - a desktop path is REFUSED under D34>",
   "what_the_state_said": "<what the served state said that day, and the specialist's stated
      reason for declining - this is the instance field, same as for a fire>",
   "what_the_day_did": "<the realized move and the relevant intraday shape - same field as a fire>",
   "supports_or_contradicts": "supports|contradicts|ambiguous",
   "reason_class": "MARKET_JUDGMENT|DATA_ABSENT|SCOPE",
   "verdict": "JUSTIFIED|OUTCOME_CREDITED|MISSED_FIRE|DATA_ABSENT|SCOPE",
   "why": "<the argument. Whether the trigger was evaluable and satisfied, and whether the stated
      reason holds on the record.>",
   "counterfactual": "<what firing would have emitted and how it would have scored - or the exact
      words NOT DETERMINABLE and why>",
   "confidence": "low|med|high"}
 ],
 "batch_observations": "<verdict counts, any play whose declines are systematically one class, and
   any decline that changed your view of the play itself>"}

RULES. Audit every decline listed below - all %d of them. Cite repo-relative paths only. Never
invent a source_file. You are auditing, not fixing: do not edit the brain or any posterior.

THE DECLINES IN YOUR BATCH (%d declines across %d plays), verbatim from the ledger:

%s

THE FULL BRAIN RECORD FOR EACH PLAY IN YOUR BATCH:

%s""" % (n, n, n, len(rows), len(rows), len(plays),
         json.dumps(rows, indent=1)[:190000],
         json.dumps(recs, indent=1)[:190000]))
    return 0


def cmd_audit_validate(a):
    path = sys.argv[2]
    d = json.load(open(path, encoding="utf-8"))
    errs = []
    exp = set(_batch_plays(d.get("batch", -1)))
    led = [r for r in json.load(open(OUT, encoding="utf-8"))["entries"]
           if r["action"] == "stood_down" and r["play_id"] in exp]
    want = {(r["play_id"], r["date"]) for r in led}
    got = set()
    sys.path.insert(0, HERE)
    import brain_audit as BA
    for r in d.get("declines", []):
        got.add((r.get("play_id"), r.get("date")))
        if r.get("play_id") not in exp:
            errs.append("play not in this batch: %s" % r.get("play_id"))
        if r.get("verdict") not in VERDICTS:
            errs.append("%s %s: bad verdict %r" % (r.get("play_id"), r.get("date"), r.get("verdict")))
        if r.get("reason_class") not in REASON_CLASSES:
            errs.append("%s %s: bad reason_class %r" % (r.get("play_id"), r.get("date"),
                                                        r.get("reason_class")))
        if r.get("action") != "dont":
            errs.append("%s %s: action must be 'dont' (Greg S112 - a decline is an ordinary "
                        "instance, one field marks do vs don't)" % (r.get("play_id"), r.get("date")))
        if r.get("supports_or_contradicts") not in ("supports", "contradicts", "ambiguous"):
            errs.append("%s %s: bad supports_or_contradicts" % (r.get("play_id"), r.get("date")))
        for f in ("why", "counterfactual", "what_the_day_did", "what_the_state_said",
                  "source_file", "confidence"):
            if not str(r.get(f, "")).strip():
                errs.append("%s %s: missing %s" % (r.get("play_id"), r.get("date"), f))
        sf = r.get("source_file", "")
        if sf and any(BA._is_machine_path(t) for t in BA._split_citation(sf)):
            errs.append("%s: DESKTOP PATH (D34): %s" % (r.get("play_id"), sf))
        elif sf and not BA._traces(sf):
            errs.append("%s: source_file does not resolve: %s" % (r.get("play_id"), sf))
    for miss in sorted(want - got)[:20]:
        errs.append("decline NOT audited: %s %s" % miss)
    print("%s  %d declines, %d errors" % ("FAIL" if errs else "PASS", len(d.get("declines", [])),
                                          len(errs)))
    for e in errs[:30]:
        print("   " + e)
    return 1 if errs else 0


def cmd_audit_collect(a):
    rows = []
    for f in sorted(glob.glob(os.path.join(AUDIT_OUT, "batch_*.json"))):
        rows.extend(json.load(open(f, encoding="utf-8")).get("declines", []))
    from collections import Counter
    print("collected %d audited declines from %d files\n" % (rows and len(rows) or 0,
                                                             len(glob.glob(os.path.join(AUDIT_OUT, "batch_*.json")))))
    print("VERDICT:")
    for k, v in Counter(r.get("verdict") for r in rows).most_common():
        print("   %-18s %3d  (%.0f%%)" % (k, v, 100 * v / max(1, len(rows))))
    print("\nREASON CLASS:")
    for k, v in Counter(r.get("reason_class") for r in rows).most_common():
        print("   %-18s %3d" % (k, v))
    miss = [r for r in rows if r.get("verdict") == "MISSED_FIRE"]
    print("\nMISSED_FIRE - declines that COST us: %d" % len(miss))
    for r in miss[:14]:
        print("   %-46s %s %s" % (r["play_id"][:46], r.get("date"), str(r.get("counterfactual"))[:90]))
    out = os.path.join(HERE, "STANDDOWN_AUDIT_S112.json")
    json.dump({"note": "Audited declines. Verdicts can be negative: MISSED_FIRE is a decline that "
                       "cost us, and its presence is what makes this ledger falsifiable.",
               "session": "S112", "n": len(rows), "declines": rows},
              open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("\nwrote %s" % os.path.relpath(out, ROOT))
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    return {"build": cmd_build, "top": cmd_top, "saves": cmd_saves,
            "audit-prompt": cmd_audit_prompt, "audit-validate": cmd_audit_validate,
            "audit-collect": cmd_audit_collect}.get(
        sys.argv[1], lambda _: (print(__doc__), 1)[1])(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
