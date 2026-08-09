import json, collections, io

P = "store/decisions.json"
d = json.load(open(P, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
ids = {e["id"] for e in d["entries"]}

D51 = collections.OrderedDict([
 ("id", "D51"),
 ("session", "S115 (integrating the external Frankie build; ChatGPT drew the distinction first and it is promoted here)"),
 ("decision",
  "**A GATE THAT EXISTS IS NOT A GATE THAT PASSED, AND AN EXTERNAL BUILD IS VERIFIED BEFORE IT IS "
  "MERGED - THE VERIFICATION NAMED, NOT ASSERTED.** Two halves, both learned the same way. "
  "(1) `FRANKIE_S115_IMPLEMENTATION.md` splits its own report into **Built** and **Not claimed as "
  "passed**, and lists six items - the M-16 physical data repair, the g6-g16 actual rebuild, A-67 "
  "arm 1, A-69, A-67 arm 2, A-42's first production run - as HARNESS PRESENT, EVIDENCE ABSENT. That "
  "split is now binding on us too: a registry item whose CODE landed does not move to DONE, because "
  "the whole point of every one of those items is a MEASUREMENT, and a green selftest measures the "
  "harness, not the market. This is the S114 'live status on dead evidence' rule pointed at build "
  "status instead of at play status - same defect, same door. (2) An external build is not merged on "
  "a description of itself. **MEASURED S115 before writing a word of this**: `git merge --no-commit "
  "--no-ff origin/chatgpt/agent-frankie-s117` merges CLEAN (0 conflicts, aborted immediately), and "
  "`python agent_frankie.py health` + `selftest` run **11/11 PASS** from a detached worktree at "
  "`48e50b9` - including the assertion that `spawn.py`'s git blob is unchanged. **The merge is still "
  "NOT taken this session**, for a reason that has nothing to do with Frankie: the branch is based on "
  "`chatgpt/novel-edge-lab-s116`, so merging it also lands ~1,500 lines of dashboard/novel-edge-lab "
  "code that no one on this side has read. **Verified is not the same as reviewed, and the merge "
  "commit spends the reviewer's credibility on both halves at once.**"),
 ("instance",
  "S115 close. Frankie: 49 files / ~7,954 insertions on `chatgpt/agent-frankie-s117` (PR #8), "
  "entry point `research/kalshi/agent_frankie.py`, conformance record "
  "`research/kalshi/FRANKIE_S115_IMPLEMENTATION.md`, built against blob "
  "6cddd0c8aad6ddf75304220250193371301bf18f of `FRANKIE_BUILD_BRIEF_S115.md`. Ran here: merge dry-run "
  "clean; health JSON reports spawn.py blob 2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e observed == "
  "expected, paper manifest READY with 9 papers; selftest 11/11 including 'Frankie can never enable "
  "execution', 'self-improvement cannot apply itself', 'self-improvement cannot touch spawn.py'. "
  "`frankie_s115_status.py` reports A-59/A-61/A-62/A-65/A-66/A-67/A-68/A-69 contracts present and "
  "A-63/A-60 explicitly DEFERRED_BY_S115_UNTIL_A-5_LIBRARY_INDEX - i.e. it did not quietly pull the "
  "fitted-sigma shortcut forward when it would have been easy to. NONE of those items moved to DONE "
  "in the registry; each gained an `external_build` note instead."),
 ("status", "DECIDED"),
 ("enforced_by",
  "half (1) is enforced by the registry: A-59/A-61/A-62/A-65/A-66/A-67/A-68/A-69/A-42/M-16 stay OPEN "
  "with an `external_build` note naming branch and commit, and the andon's open-items line keeps "
  "counting them. Half (2) is enforced by A-70, which is the merge review itself and is ESSENTIAL - "
  "the trunk cannot carry Frankie until someone has read the base branch it rides in on."),
])

if "D51" not in ids:
    d["entries"].append(D51)
    json.dump(d, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("D51 appended (%d entries)" % len(d["entries"]))
else:
    print("D51 already present")
