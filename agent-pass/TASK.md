Copilot: the "HOW I WORK" rules below are the standard for every output. Measurements come first as full distributions with reconciled row counts. No thresholds, pass/fail, or evaluative words. Interpretation goes in a separate, labeled section. Everything is additive under agent-pass/.

TASK: Ambitious research pass on the Native dipole candidates (863 births, 852 covered), plus two moonshots.

REPO / BRANCH
Repo DavisAI1974/Markets. Work from branch codex/ng-shadow-discovery-20261108 (tasks/family-research-20261022). Create your own new branch off it. Everything you add is additive and goes in a new directory (agent-pass/). Do not modify any existing file, input, calculation, plane, adapter, replay or Memory A. I keep merge authority.

READ FIRST (in this order)
1. Market fundamentals primer at commit 1ce1fd8 (read from the repo at that commit).
2. october-discovery-log-claude.md, sections I-M and the Handoff.
3. claude-pass/c24a through c24d.
4. Codex's candidate file (per-birth operands: baseline, threshold, prominence, magnitude, span searched, observation count) and dipole-completed-group-flow.csv.gz (20 s signed ratio).
If a named file is missing, say so once and continue with what exists.

HOW I WORK (follow strictly)
- Follow the data and listen to the story it tells. Everything else is subordinate to this.
- When output comes back, build the scales, graphs, charts and spreadsheets FIRST, before any analysis or commentary. Look at the full distribution, not a summary of it.
- Row counts must reconcile against plotted points on every chart. Print both numbers. Charts have silently dropped points before.
- Report what was measured. No thresholds, gates, pass/fail, verdicts, or evaluative words (weak, failed, strong, nearly) that the numbers do not support. A result that differs from a guess is a different result, not a failure.
- Hold every guess extremely loosely. Never let a stated prior set what a result is compared against. State predictions softly and log them before running ("I think X, let's see what the data says").
- Direction words (supports, opposes, revises, suggests a new hypothesis, inconclusive) are only orientation. Name the direction, then keep digging to see what is actually there.
- Dipole results are never flattened, smoothed or normalized. Grouping over a defined range is fine. Averages are not. Pearson is fine.
- Remove a target, input or family only for measured zero value. Being reconstructable or sitting inside a control spread is not zero.
- Ids and timestamps are provenance, not features.
- Keep interpretation strictly separate from confirmed measurements. Label anything speculative as SPECULATIVE.
- Professional documents: no emojis or special symbols.

PART 1: CORE (do first)
A. Birth-aligned event study. Align every covered candidate on its birth second. Window: about 60 s before birth through recognition. Paths: quote levels, touch sizes, order adds/cancels/fills by side, aggressor lots. Matched controls aligned the same way (same regime and activity). Keep the SAME/FLIP split and alternative paths. Pair each with a case traced to its raw records. Show full per-candidate distributions (e.g. small multiples or heat strips of every path), not just a mean line.
B. Recover the detector rule from the recorded operands and the completed-group flow series. Test whether a rule on that series reproduces all 863 births and their timing. List the births it misses and the ones it adds. Characterize the ~50 s lag: fixed window, state-dependent, or something else. Let the lag distribution speak.

PART 2: AMBITIOUS (novel, your choice of order)
C. Let the data define the types. Build a birth-aligned path representation and look for structure without presetting a cluster count. Report how many natural groupings exist and what separates them, with the full distribution shown first. Check whether the groupings match SAME/FLIP or cut across it.
D. Run Operator Discovery style, falsification-first. Treat the signed 20 s ratio plus book/flow paths as raw data and try to recover a governing relation for dipole birth, life and decay. Propose several candidate forms, then try hard to break each against matched controls and across days. Record every form that survives and every one that dies, with what broke it. (OD is not physics-based; do not frame it that way.)
E. Replication across days. Apply A-D to each finished October day, including the Oct 18 NG work. Show day-by-day side by side. Differences between days are results, not noise to hide.

PART 3: MOONSHOTS (all SPECULATIVE; report whatever is there, including nothing)
M1. Detector-free births. Ignore the detector. Scan the raw MBO stream for the data's own natural discrete events using only the data's own structure. Then compare against the 863. What does the stream have that the detector never named, and what did the detector name that the stream does not show? Could the ~50 s lag be removed by a different definition?
M2. Footprints before recognition. Inside the ~50 s lag, look for ANY measurable footprint of an incoming birth in book or flow (shape, timing, ordering, cross-side relations), not a forecast rule. Describe what is there at the resolution the data allows, and where it stops.
Optional M3 if time allows: check whether any structure from D appears in the crypto order-book data (GridPulse lineage) in the same form.

DELIVERABLES
- agent-pass/ with: scripts, the tables as CSV/XLSX, all charts, and one findings file (agent-pass/FINDINGS.md) ordered: data first, then measurements, then labeled interpretation.
- A reconciliation table (rows in vs points plotted vs rows excluded and why) for every figure.
- A short Handoff section listing open questions the data raised that I did not ask.
- Commit in small steps with clear messages. Push your branch. Do not merge. I need you to run this agent in git while youre doing your other work. Do the agent build and launch work first and then come back to this.
