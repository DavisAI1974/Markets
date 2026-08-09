# NOTE FOR S116 — things seen at S115 close and deliberately NOT edited

Greg, S115 close: *"leave any other edits for next session. just make a note."* This is the note.
Nothing below was touched. Each is small, each is real, and each is written with what I actually
measured so the next session does not have to re-find it. **None of these is a blocker — A-70 (the
merge review) and A-71 (the phantom-tree data) are still the two items that gate the frontier.**

---

## 1. `store.py docs` STILL CRASHES ON AN UNDECLARED CLASS — the new gate cannot reach it

The `class_undeclared` gate added at S115 lives in `docs_problems()`, which is what `store.py check`
and the andon's `docs` row call, so **the gate does fire and was negative-tested there.** But
`cmd_docs` prints the class legend at `store.py:543-544` — `store["classes"][cls]` — and only calls
`docs_problems()` at `:550`. So on an undeclared class the human-facing `store.py docs` listing
**still dies with a KeyError before the gate ever reports**, which is exactly the confusing failure
that hid the three invented classes in the first place.

Fix: `store["classes"].get(cls, "(UNDECLARED - see the class_undeclared gate)")` in the legend loop.
One line. The gate then explains itself instead of the traceback doing it badly.

## 2. THE CLASSIFICATION GATE ONLY SEES `research/kalshi/*.md` — ROOT-LEVEL DOCS ARE OUT OF REACH

`_unclassified_md()` walks tracked `research/kalshi/*.md`. **Every root-level document is invisible
to it** — including `CHATGPT_HANDOFF_S117_AGENT_FRANKIE.md`, `CHATGPT_HANDOFF_S116_NOVEL_EDGE_LAB.md`
and its addendum, all three of which arrive with the A-70 merge and all three of which are delivered
external hand-offs that D36 should reach.

**This is the A-24 defect one directory up.** S115 inverted the briefing gate from "does the name
match a known pattern" (fails OPEN) to "is this document classified" (fails CLOSED) — and then
scoped the inversion to one directory, which fails open on everything outside it. Widen the walk to
tracked `*.md` at the repository root as well, with the close-out trio still excluded by design.

**Do this as part of A-70, not after it** — the three ChatGPT hand-offs land in the same merge, and
classifying them on arrival is the whole point of the rule.

## 3. `station0/briefings` — 8 of 13, AND THE COUNT IS NOT THE PROBLEM

Still the single andon FAIL. Unaudited: `CHATGPT_BRIEF_S112.md`, `CHATGPT_S112_SIX_WORKSTREAMS.md`,
`CHATGPT_S113_T1_NUCLEAR_OUTAGE_SOURCES.md`, `G15_MBO_FIXES_FOR_CHATGPT.md`, and four more.

**Do not discharge this by widening a glob or by stamping audited-by-construction** — that is what
made it look green before, and the S115 widening is why the count went UP. D36 wants a real
disposition: every numbered recommendation in each document gets a registry id **including the ones
we decide against**, recorded in `store/briefing_audits.json`. `G15_MBO_FIXES_FOR_CHATGPT.md` is
already known superseded (the brain's doctrine entry that cited it was reframed this session), so
that one is a two-minute honest disposition rather than an audit.

## 4. `records/` HAS NO GATE, AND CANNOT HAVE A COMPLETE ONE

D52's sweep is a checklist line. Nothing verifies a session actually swept. The honest partial guard
available: a `plant_status` row asserting `research/kalshi/records/S<current>/` EXISTS and has a
README once the session has written a handoff. That catches "forgot entirely"; it cannot catch
"swept incompletely", because nothing inside the repo can enumerate a directory outside it. **Write
it as the partial it is, or not at all — a row that implies completeness it does not have is worse
than no row.**

## 5. `decisions` WARN — D1, D13, D32 are doc-only and older than two sessions

The andon has been asking for an enforcement or a re-affirmation on these for several sessions.
**D13's turn already came around this session and produced D50** (its `enforced_by` claimed a QC
sweep that does not exist). D1 and D32 have not been looked at. Either wire something or re-affirm
them as deliberately doc-only — but the WARN is doing its job and should not just be carried again.

## 6. `q.py` -> `registry_grep.py` DESERVES A REAL HOME

It is the only one of the three rescued scripts worth running again
(`python registry_grep.py <regex>` over id/title/why/source across the registry). It currently sits
in `records/S115/scripts/` as provenance, which is the wrong place for a live tool. Promote it to
`research/kalshi/` proper, give it `--tier`/`--status` filters, and register it in
`KALSHI_TRADING.md` — the document registry will demand that anyway.
