import json, collections

P = "OPEN_ITEMS.json"
d = json.load(open(P, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
items = d["items"]
by = {i["id"]: i for i in items}

EXT = ("EXTERNAL BUILD LANDED S115 on `chatgpt/agent-frankie-s117` @48e50b9 (PR #8) - see "
       "`research/kalshi/FRANKIE_S115_IMPLEMENTATION.md`. **The HARNESS is built; the EVIDENCE is "
       "not collected (D51).** Verified here, not asserted: merge dry-run clean, selftest 11/11. "
       "NOT merged to trunk - blocked on A-70. Stays OPEN until the measurement it exists for has "
       "been made.")

WHERE = {
 "A-59": "frankie_render_s115.py (FrankieAgentObject, TypedPosterior, assert_byte_identical) + frankie_forecaster_s115.py",
 "A-61": "frankie_s115.pin_snapshot() / verify_snapshot()",
 "A-62": "frankie_s115.build_specialist_track_records() + frankie_effects_s115.specialist_prior_falsifier()",
 "A-65": "frankie_s115.validate_compaction() - REJECT_VIEW_CHANGE / TEST_INSENSITIVE / VALIDATED_FOR_THIS_CELL_ONLY",
 "A-66": "frankie_s115.OWNERSHIP - PART-level, six parts, same-part overlap is a hard failure",
 "A-67": "frankie_validation_s115.py seal + compare_arms() - ARM 1 HAS NOT RUN",
 "A-68": "frankie_s115 lens book (append-only JSONL, causal_lens_view serves strictly earlier days only) + frankie_effects_s115.retention_falsifier()",
 "A-69": "frankie_s115.TrainingSplit.validate() + training_release_gate() - HAS NOT TRAINED",
 "A-42": "frankie_s115.grade_fj1() against failure_localization.py's frozen table - FIRST PRODUCTION RUN NOT MADE",
 "M-16": "databento_backfill_s115.py - repo-root absolute destinations, NG roll defaults to n, asserts destination BYTE GROWTH. THE PHYSICAL REPAIR (moving/redecoding the already-paid head + L1 jobs into the canonical root) IS STILL UNDONE.",
 "A-50": "frankie_s115.assert_no_narrative_leak() - a deterministic deny gate, SUPPLEMENTS brain_view's wall, does not replace it",
 "A-64": "frankie_evolution.py - sandbox candidates only, cannot apply its own source changes",
}

for k, v in WHERE.items():
    it = by.get(k)
    if not it:
        print("MISSING", k); continue
    it["external_build"] = EXT + " Where: " + v

def add(item):
    if item["id"] in by:
        print("exists", item["id"]); return
    items.append(item); print("added", item["id"])

add(collections.OrderedDict([
 ("id", "A-70"),
 ("title", "MERGE REVIEW: chatgpt/agent-frankie-s117 carries an UNREAD base branch into the trunk"),
 ("source", "S115 close, D51"),
 ("first_raised", "S115"),
 ("status", "OPEN"),
 ("size", "M"),
 ("tier", "ESSENTIAL"),
 ("tier_why",
  "Everything downstream is blocked on it. A-67 arm 1 is the next real experiment and it cannot run "
  "until Frankie is on the trunk; but the merge commit also lands the dashboard / novel-edge-lab "
  "S116 base, and a merge commit signs for the whole diff."),
 ("why",
  "MEASURED S115: `git merge --no-commit --no-ff origin/chatgpt/agent-frankie-s117` -> 'Automatic "
  "merge went well', 0 conflicted paths (aborted). 49 files, ~7,954 insertions. The Frankie half is "
  "verified running (selftest 11/11 from a worktree; spawn.py blob unchanged; the paper manifest is "
  "READY at 9 papers). The OTHER half is not: the branch is based on `chatgpt/novel-edge-lab-s116`, "
  "which brings `dashboard/adapters/novel.py`, `dashboard/frontend/novel.{js,css}`, "
  "`dashboard/novel_candidates.json`, a `dashboard/server.py` edit, two new CI workflows and two "
  "S116 handoff docs - none of it read on this side. **Verified is not reviewed.**"),
 ("what",
  "1. Read the novel-edge-lab S116 half - `CHATGPT_HANDOFF_S116_NOVEL_EDGE_LAB.md` + its addendum, "
  "then `dashboard/adapters/novel.py` and the `dashboard/server.py` diff. The question to answer is "
  "narrow: does anything in it READ a store or WRITE a path the forecaster depends on, and does "
  "`novel_candidates.json` claim any evidence it did not measure. "
  "2. Audit the two new workflows (`.github/workflows/agent_frankie_ci.yml`, `novel_edge_lab_ci.yml`) "
  "for anything that pushes, promotes or mutates git. "
  "3. Confirm `verify_gold.py` still passes post-merge and `spawn.py`'s blob is untouched on the "
  "MERGED tree, not just on the branch. "
  "4. Then merge, run the full gate battery from `research/kalshi`, and only then start A-67 arm 1."),
 ("falsifier",
  "If the S116 dashboard half touches nothing the forecaster reads and the workflows cannot mutate "
  "git, this collapses to a 20-minute read and the merge is routine - which is the expected outcome. "
  "It is ESSENTIAL because of what it GUARDS, not because it is expected to find something."),
]))

add(collections.OrderedDict([
 ("id", "A-71"),
 ("title", "M-16's PHYSICAL repair - the guarded puller exists, the already-paid head + L1 data is still not in the canonical root"),
 ("source", "S115 close; ChatGPT's own 'not complete evidence yet' list, item 1"),
 ("first_raised", "S115"),
 ("status", "OPEN"),
 ("size", "S"),
 ("tier", "ESSENTIAL"),
 ("tier_why",
  "A-67 arm 1 needs the unwalked head (2025-07-22 -> 09-05) staged, and the head trades are the "
  "thing that landed in the phantom tree. The guard stops the NEXT pull from lying; it does not move "
  "the bytes that are already in the wrong place."),
 ("why",
  "MEASURED S115: two completed Databento jobs reported 2,384,994 and 1,386,421 rows and landed in "
  "`research/kalshi/data/` (219MB trades + 22MB L1) because `OUT_DIR`/`L1_DIR`/`MBP10_DIR` were "
  "relative and resolved against cwd. `databento_backfill_s115.py` fixes the class going forward. "
  "The data itself has not been moved or re-decoded, and it is already PAID FOR - re-pulling it "
  "spends money for nothing."),
 ("what",
  "Move (do not re-pull) the phantom tree into the canonical root destinations, then verify by "
  "READING BACK - file count and span - not by trusting the mover's exit code (S114 D47: a store "
  "rebuilt in a session is not a fix until it is on S3; same posture applies to a local move). Then "
  "run `databento_backfill_s115.py` once on a one-day window and confirm the byte-growth assertion "
  "actually fires on the canonical destination."),
 ("falsifier",
  "If a read-back of the canonical destinations shows the head span present with a plausible file "
  "count and `state_health` stages the head block clean, it is done. If the mover reports success "
  "and the read-back shows nothing, that is the SAME defect one layer up and must be reported, not "
  "retried."),
]))

d["current_session"] = "S115"
json.dump(d, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("registry now %d items" % len(items))
