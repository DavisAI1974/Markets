# HANDOFF 2026-09-30 ~04:40Z: the day workflow is built and restarted; next chat only CHECKS it is good

Branch `claude/frankie-monday-cycle-0-urozez`, tip `91f5cb1a`. Supersedes `HANDOFF_20260930_EARLY.md` (its RUN TABLE and
Greg's standing calls still hold). Session: https://claude.ai/code/session_01KPfHuN3bv1nQjW1PCo4T9y

## THE ONE JOB OF THE NEXT CHAT (Greg)
Check that the workflow stated in this chat is good. Do NOT redesign, do NOT add loops or rules, do NOT build new pieces
unless the check shows the stated workflow is broken. No reports, no tests, no validations beyond confirming it runs.

## The workflow as stated (Greg, this chat)
- The day flow = the RUN TABLE in `HANDOFF_20260930_EARLY.md` (Monday's run with fewer steps; drops confirmed; authorship
  removed). Pod days and box days have EXACTLY the same steps ("just a different name").
- Once a day enters a Pod or a box slot for its day work it does not leave until every kept step is done.
- ROOT finishing (its sheets receipted) is the key that switches on the next layer (teacher -> data export -> search ->
  lessons -> the class -> Jev), in the same slot.
- ROOT runs in parallel across slots; the one-at-a-time pieces (the class line) keep the handling built before.
- No special class of day; no hard-coded "all days ingested first" rule. Everything should already be ingested.
- Boxes full and running first, then Pods.

## What was built and pushed ([skip ci], py_compile / bash -n only)
| commit | what |
|---|---|
| dab6eb9a | A day books its 16 CPUs ONCE and holds them from ROOT to the end of its day; every step runs inside the held slot (`frankie_box_cores.py run --inside <booking>`); the class line entry carries the slot so the class runs inside it; no class-wait deadline; orchestrator with the ROOT line on only enqueues + kicks (every post-ROOT step is the slot's). Root cause fixed: last night ROOT released its CPUs and the next day took them. |
| 91f5cb1a | Pod ROOT fix: all 5 Pod ROOTs (20211020, 20221011, 20221012, 20221018, 20231004) died with "file changed while it was hashed" on the input row spool (the Pods' network volume moves mtime/ctime after close). `frankie_box_filehash.witness` re-hashes until the key is stable (max 3 passes); changing bytes still refused. |

## What is running (as dispatched, 04:28-04:35Z)
- MAIN i-035994afa8bdf66a5: ROOT-line worker handed over to dab6eb9a (run 36668992346, success; staged
  `/opt/frankie-box/code/dab6eb9a8f9ad8e426127188877c9a39b1e16a7f-36668777070-1/markets`). The old worker 86310 ends after
  its running ROOT; the new one then finishes the 8 ROOT-done days first (20211005, 20211006, 20211012, 20211013,
  20221004, 20221005, 20231003, 20221019) in held slots, then the queued days FIFO.
- MAIN conforms 20221004 and 20221005 (8 CPUs each, dispatched ~02:50Z, not stopped: never stop a running job).
- TWIN i-0d17573dbce871520: ingest 20251021 + conform 20211019 (from last night). 8-CORE i-08cee: ingest 20251007.
- POD ROOT LOOP dispatched on 91f5cb1a (staged `...91f5cb1ac8f3f2c89b1868dfadbd813e098b4114-36669219369-1/markets`,
  BUDGET_MINUTES=330) over the 4 Pods (0o3wfhj6vxvqis, kj93q89dnpuhdp, tthwp8ztjxhqcw, s8u7611dxa5i24).

## Known gaps to check against the stated workflow (Greg's call on each; do not act unasked)
1. The Pod loop runs ROOT ONLY and imports it to main; the rest of a Pod day is not built on the Pod, and dab6eb9a keeps
   Pod-ROOT days out of box slots (`_needs_finish`). So Pod days stop after ROOT. Greg wants ONE loop with the same steps
   for Pod and box; the only blocker named: the Pod loop runs on GitHub because only it holds the Runpod key and S3
   write; main has neither. Greg said NO to changing this in this chat.
2. 20211020's old Pod claim (s8u7611dxa5i24, failed attempt uploaded) is imported/released by the Pod loop.
3. Pods bill ~$1.59/h each; stop only on Greg's word.
4. Open from before: Granite Session.boss edit; DuckDB on main for the search; FIRST-RUN CHECK (ask Frankie if the day's
   step order is right: Frankie's class is code and the Granite voice is not wired, so tell Greg).
