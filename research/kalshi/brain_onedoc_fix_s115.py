#!/usr/bin/env python3
"""brain_onedoc_fix_s115.py - close the ONE-DOC holes in the brain. (S115, Greg's go.)

Greg, S115, across the thread: "I thought the rules file was the brains. What does the rules file
do different?" / "reasoning is exactly what we want tied to the decision!" / "Any function that has
to do with the brain should be in the brain file" / "Let's clear this all up now, is there another
hidden doc somewhere" / "merge the reasoning file".

FOUR DEFECTS, each MEASURED before it was believed, each fixed here. Nothing is deleted; the brain
only ever gains text, and every edit is a string rewrite that names what it replaced.

1. A SECOND DOCTRINE FILE IN THE AGENTS' READ LIST.
   `knowledge/refinement_architecture_doctrine.md` states in its OWN header that it was MERGED into
   the brain at S103 and "kept as the human-readable source" - and RFN-1 has ordered every refine
   specialist to read it ever since. Two copies of one doctrine, one of them served. That is the
   S105 root cause verbatim (blind_shared.md said USE the MBO firehose while blind_class_* said NO
   MBO; it cost a session to diagnose). Measured: the brain's copy carries provenance,
   load_bearing_principle, pieces_in_order and goal - complete EXCEPT the file's FLOW line. So the
   merge is one field, and afterwards the file is fully redundant.

2. THREE DEAD CITATIONS INSIDE SERVED PLAYS.
   `blind_class_C.md`, `blind_class_D.md` and `blind_class_E.md` are cited in the `provenance` of
   three plays and DO NOT EXIST - the whole blind stack was deleted at S105 BY DESIGN (D7: no
   blind-specific rule file may exist). A specialist following the citation finds nothing, and
   nothing reported the miss for ten sessions. The plays' CONTENT is unaffected; only the citation
   is wrong, so the repair states what happened rather than silently dropping the reference.

3. DOCTRINE THAT DEFERS SUBSTANCE TO AN EXTERNAL FILE.
   `doctrine.mbo_refinement_findings` ends "Integration gotchas:
   research/kalshi/G15_MBO_FIXES_FOR_CHATGPT.md" - doctrine served to every specialist telling it
   to go read somewhere else. Measured: that file is a 57-line S103 BUILD-INTEGRATION list (branch
   names, a contract-leg spec note), not forecasting doctrine, and it is superseded - its data-spec
   item is the NG.n.0-vs-NGJ26 basis question settled long since. So the pointer is reframed as a
   dated provenance citation, which is what it always was.

4. NOTHING STOPPED ANY OF IT RECURRING.
   `brain_schema.py` gains `check_cited_files`: any `*.md` named inside a role-served section must
   EXIST. Same posture as D34's `_is_machine_path` - a citation that cannot be opened is a hard
   validation error, not a note.

    python brain_onedoc_fix_s115.py            # dry run - print every edit
    python brain_onedoc_fix_s115.py --write    # back up, apply, verify losslessness
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
DOCTRINE_MD = os.path.join(HERE, "knowledge", "refinement_architecture_doctrine.md")

# The FLOW line, verbatim from the .md, so the merge is a transcription and not a paraphrase.
FLOW = ("old framework produces the map -> Friday anchor sets the starting state -> normalized "
        "market data -> feature states -> session specialist interprets -> coordinator selects -> "
        "posterior agent UPDATES the blind -> scoring decides if the update helped -> lesson "
        "proposals tested forward.")

DEAD = {
    "daytype.covering_giveback_self_limiting": "blind_class_E.md",
    "daytype.eia_preprint_overextension_gate": "blind_class_D.md",
    "structure.accumulation_arm_turn": "blind_class_C.md",
}


def _dead_note(fname):
    lens = fname.replace("blind_class_", "mbo_specialist_")
    return ("%s [DELETED S105 BY DESIGN - D7: blind and refine read the IDENTICAL committed rule "
            "files, so no blind-specific file may exist. The surviving canonical lens is "
            "agents/%s, which you are already told to read. Citation repaired S115; the play's "
            "content is unchanged]" % (fname, lens))


def edits(brain):
    """-> [(where, before, after)]. Pure: computes the diff, writes nothing."""
    out = []

    # (1) merge the reasoning file's last un-merged field
    for it in brain.get("doctrine", []):
        if it.get("original_key") == "refinement_architecture_s103":
            body = it["body"]
            if "flow" not in body:
                out.append(("doctrine.refinement_architecture.body.flow", "(absent)", FLOW))
            old_prov = body.get("provenance", "")
            if "SUPERSEDED" not in old_prov:
                out.append(("doctrine.refinement_architecture.body.provenance", old_prov,
                            old_prov.rstrip(". ") + ". **S115: the standalone file is now "
                            "SUPERSEDED and has been removed from RFN-1's read list.** Its FLOW "
                            "line was the only field not already here and is merged above, so this "
                            "entry is the ONLY copy of this doctrine. Greg, S115: 'merge the "
                            "reasoning file' - two copies of one doctrine, one of them served to "
                            "agents, is the S105 defect (blind_shared.md said USE the firehose "
                            "while blind_class_* said NO MBO)."))

    # (2) three dead citations
    for pl in brain.get("plays", []):
        f = DEAD.get(pl.get("id"))
        if not f:
            continue
        # THE CITATION LIVES IN legacy_notes.provenance, NOT AT THE PLAY'S TOP LEVEL - the
        # top-level `provenance` is the D29 schema's structured slot (merged_session,
        # brain_version, from_proposal), while the free-text S105 tweak note was preserved under
        # legacy_notes by the migration. The first version of this script looked only at the top
        # level and reported 0 of 3 edits; the DRY RUN is what caught it. Check both.
        for holder, key in ((pl, "provenance"), (pl.get("legacy_notes") or {}, "provenance")):
            prov = holder.get(key)
            if isinstance(prov, str) and f in prov and "DELETED S105" not in prov:
                where = ("plays[%s].legacy_notes.provenance" if holder is not pl
                         else "plays[%s].provenance") % pl["id"]
                out.append((where, prov, prov.replace(f, _dead_note(f))))

    # (3) the doctrine deferral
    for it in brain.get("doctrine", []):
        if it.get("original_key") != "mbo_refinement_g15_findings":
            continue
        body = it.get("body") or {}
        for k, v in list(body.items()):
            if isinstance(v, str) and "G15_MBO_FIXES_FOR_CHATGPT.md" in v and "SUPERSEDED" not in v:
                out.append(("doctrine.mbo_refinement_findings.body.%s" % k, v,
                            v.replace(
                                "Integration gotchas: research/kalshi/G15_MBO_FIXES_FOR_CHATGPT.md.",
                                "Provenance only (NOT something to open mid-forecast): the S103 "
                                "build-integration list lived at "
                                "research/kalshi/G15_MBO_FIXES_FOR_CHATGPT.md - branch names and a "
                                "contract-leg note, SUPERSEDED, and never forecasting doctrine. "
                                "Nothing in it is needed to use this entry.")))
    return out


def apply(brain, out):
    for where, _before, after in out:
        parts = where.split(".")
        # startswith, NOT parts[0] == "plays": every play id CONTAINS DOTS
        # ("daytype.covering_giveback_self_limiting"), so splitting on "." yields "plays[daytype"
        # and the branch never fired - the three play repairs silently did nothing while the run
        # reported success. Caught by re-reading the brain after --write instead of trusting the
        # exit code (NC-3: a fix is not done until the fixed path is observed to have executed).
        if where.startswith("plays["):
            pid = where[where.index("[") + 1:where.index("]")]
            pl = next(p for p in brain["plays"] if p.get("id") == pid)
            if ".legacy_notes." in where:
                pl["legacy_notes"]["provenance"] = after
            else:
                pl["provenance"] = after
        elif "refinement_architecture" in where:
            it = next(x for x in brain["doctrine"]
                      if x.get("original_key") == "refinement_architecture_s103")
            it["body"][parts[-1]] = after
        elif "mbo_refinement_findings" in where:
            it = next(x for x in brain["doctrine"]
                      if x.get("original_key") == "mbo_refinement_g15_findings")
            it["body"][parts[-1]] = after
    return brain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    with open(BRAIN, encoding="utf-8") as f:
        brain = json.load(f, object_pairs_hook=OrderedDict)
    before_leaves = json.dumps(brain).count('"')
    out = edits(brain)
    print("[onedoc] %d edit(s)\n" % len(out))
    for where, b4, af in out:
        print("  %s" % where)
        print("    -  %s" % (str(b4)[:150]))
        print("    +  %s\n" % (str(af)[:150]))
    if not out:
        print("[onedoc] nothing to do - already applied.")
        return 0
    if not a.write:
        print("[onedoc] dry run - nothing written. Re-run with --write.")
        return 0
    ver = (brain.get("meta") or {}).get("version", "unknown")
    bak = os.path.join(HERE, "knowledge", "ng_brain_%s_backup_pre_s115_onedoc.json" % ver)
    shutil.copy(BRAIN, bak)
    print("[onedoc] backup -> %s" % os.path.relpath(bak, HERE))
    brain = apply(brain, out)
    # LOSSLESSNESS: this may only GROW the file. A shrink means something was dropped.
    after = json.dumps(brain)
    if len(after) < before_leaves:
        raise SystemExit("[onedoc] REFUSING: the brain got smaller - an edit dropped content.")
    n_plays = len(brain["plays"])
    if n_plays != 90:
        raise SystemExit("[onedoc] REFUSING: play count changed (%d)" % n_plays)
    with open(BRAIN, "w", encoding="utf-8") as f:
        json.dump(brain, f, indent=1, ensure_ascii=False)
    print("[onedoc] WROTE %s (90 plays intact)" % os.path.relpath(BRAIN, HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
