# Research continuation: dipole shapes and evidence reconciliation

Updated 2026-11-08. Operational handoff, not a new findings report.

## User's current objective

Track down the historical crypto dipole-dive and direction-specific pre-onset/tail renders. Compare them against the current NG findings and other completed research, explicitly reconciling evidence instead of treating each discovery in isolation. User sees a shared concept, not transferable numerical values or identical shapes. Preserve this as a hypothesis, not an established mechanism. User still intends paper trading tonight; this handoff does not establish that a paper-trading setup is ready or authorize live trading.

User is phone-only. Continue autonomously; do not ask them to run terminal commands. No Copilot. Do not contact Claude Desktop or other people without explicit authorization.

## GitHub locations and status

Read [PUBLICATION.md](PUBLICATION.md) for verified immutable artifact links. The completed 593-file native dipole snapshot is in markets-data at 0487d83b1ddb1abe5e4cfae12e8b88797801f428. The source/hash verification included a fresh remote download. The new evidence ledger is appended to FINDINGS.md. Desktop added a chronological lean overlay at Markets commit 9622d038f; its source/denominator/control differences are now recorded. The user clarified that the 2,000-event historical image was averaged to display an observed recurring shape with modest variation; preserve that history, and recover the individual curves to measure it.

The E-drive coordinates below identify historical migration sources only; do not use them as the continuing research environment.

- Main working directory: E:/Markets. Preserve other sessions' work; do not switch/reset its branch.
- Research worktree: E:/Markets-native-dipole-agent-pass.
- Research branch: codex/native-dipole-agent-pass-20261108, based on codex/ng-shadow-discovery-20261108.
- Research agent Codex thread: 01a1be25-2ddc-7790-ade1-96d98bf4fb56, host local. Read status before assigning duplicate work.
- Issue #14 and draft PR #15 in DavisAI1974/Markets. Do not merge or mark ready. The agent uses its direct Codex thread; no issue #13 comment is needed to rerun October 18.
- Read agent-pass/PROGRESS.md and FINDINGS.md first. A-E and M1/M2 already cover October 2, 3, 17 and 18. Optional crypto M3 was not run.
- Latest PROGRESS read in this turn says shape_forms follow-up is complete: 5,085 SAME birth-definition rows, 5,079 available values; 192 fitted descriptions, 271,040 residual rows including unavailable/domain exceptions; 15,255 candidate/control/event attachment rows. Overall 337 published PNGs and 4,628 reconciliation rows. These are recorded agent results, not newly independently reverified this turn.
- Parent's proposed shape_tail_audit.py / shape-tail-* remains outstanding. Do not claim it has run.
- The corrected October 18 figures/tables are preserved in the verified markets-data snapshot. The original Markets worktree modifications remain unstaged; do not discard them.

## Storage and analysis rules

GitHub is the durable working source. Publish code, findings and handoffs to DavisAI1974/Markets; publish data, tables, renders, workbooks and provenance manifests to DavisAI1974/markets-data. Preserve existing input paths and publish corrected artifacts under new immutable paths with SHA256 and measured byte sizes. The user explicitly removed the local-only storage rule on 2026-11-08; do not reintroduce it from historical notes, memory or generated handoffs. No further desktop computation. Existing E-drive files are migration sources only. No AWS/S3. No merge.

Distributions and artifacts before interpretation; reconcile source rows, plotted points and exclusions for each figure. No smoothing, averaging or normalization of current dipole results. Preserve original time/amplitude and all exceptions. Separate SPECULATIVE interpretation. IDs/timestamps are provenance, not features. Do not transplant old thresholds, fitted constants, retrospective winner labels or normalization into new discovery. 13 external data-point relevance remains open; do not join or exclude them by assumption. Their old 749-family population differs from this dipole population.

## Current NG evidence and comparison hazards

Archived candidates per day: 741/833/741/863. Live-clock candidates: 741/832/740/863. SAME archived: 387/449/387/472, plotted live 387/448/386/472.

Parent's three shape-overlay figures use SAME only, each 1,695 rows / 1,693 points / 2 unavailable. Scripts: shape_overlays.py and clock_decomposition.py. Tables: shape-overlay-points.csv, shape-overlay-figure-reconciliation.csv, clock-decomposition-observations.csv and per-day detector-free-nearest.csv.

Definitions: quote relocation is bid/ask price change; touch-size change is either best-size change; wire aggressor run start is first raw trade at a wire B/A side change, attributed to its completed group. It is NOT first trade in the birth direction.

Sorted overlay x is ordinal rank, not elapsed time. y is recognition minus first event at/after birth. Negative values mean event AFTER recognition. Exact decomposition: recognition-event = recognition-birth minus event-birth. Shared recognition delay contributes to the plateau; resemblance does not establish a governing relation. Birth-aligned individual paths are the direct comparison to old crypto chronological curves.

## Claude Desktop evidence awaiting reconciliation

User forwarded results from claude/three-day-dipole-20261108, not merged. Desktop reports all-covered 741/824/740/852 = 3,157 candidates, 500 matched-control draws, and its own reconstructed books. Its first aggressor event is first lots in birth direction. It reports Oct 3 quote relocation separating, but not matching aggressor curves under its definitions. Its candidate omissions, lag groups, distance metric and event definitions need exact source/key reconciliation; do not assume comparability.

Desktop requests our SAME table/branch path. Provide exact source definitions and accessible handoff without pretending local CSVs are published on GitHub. Desktop also asked about October 18 via issue #13: October 18 is already done in our research. Do not rerun it solely because of that stale question.

The Desktop V plot shows shares above/below each candidate's own birth-boundary midpoint. Zero at anchor follows from its definition; off-anchor shape and control differences still require investigation. Do not dismiss the whole shape as an anchoring artifact, or equate it with old flow curves without source checks.

## Historical sources actually located

1. E:/Markets/research/ng_dipole_runway_audit.py:244-246: onset = direction * onset_raw; current = direction * current_raw; dive = onset - current. Flow source is trailing 60-second signed buy/sell volume imbalance. Positive dive is a decline in directional authority. This is older research, not the current 20-second Native detector definition.
2. E:/Markets/odcore/swing_maker.py:200: S55 round 8, THE INVERTED GRAPH. Describes flow climax and collapse through zero. Historical statements are not newly replicated measurements.
3. E:/Markets/research/shape_s71/arc_gate.py:237 and :269 produce kraken_winner_loser_arcs.png and btc_false_start_arcs.png. Second includes dip-aligned bump-pullback-relaunch panel. Original image files not found in search so far; code uses averaged curves.
4. E:/Markets/research/shape_s71/fit_shapes.py describes S74 four separate long/short, winner/loser cells and separate pre-fire/tail equations. Historical fitting uses mean arcs and normalized time. Preserve this provenance; do not import that processing into current raw-scale study.
5. Basic_equations/static_dipole_test.py contains the older algebraic dipole work, but no explicit dipole-dive match was located in Basic_equations or basic_equations_src. Not an exhaustive historical-branch search.

## User's recovered images

Directory E:/Markets/.codex-remote-attachments/01a1bcd6-f9e5-7c30-b348-cc694f25b2c9/7f6bd067-5b25-474d-ba04-8748ea86f5aa/

- 1-1000118136.jpg: title Dipole (flow) over Price - 2000 winners, aligned to the turn (x=0). Flow lean and price upside on different y axes; lower panel dipole/price rates. Need exact generating source and selection/aggregation. This is the image the user calls dipole dive.
- 2-1000123773.jpg and 3-1000123754.jpg: July 7 gallery labels, long-winner and long-loser, five coins overlaid. Pre-onset rise and post-onset tails; conspicuous common discontinuity near +20 seconds needs source/window/seam verification before interpreting.
- 4-1000123735.jpg and 5-1000123752.jpg: short-loser and short-winner, five coins; handwritten observations of below-zero pre-onset dip, earlier ascent and ascent slope. Preserve as user hypotheses rather than numerical measurements.

Desktop's newer attachments: sibling directory c26d0635-8550-404e-bd11-cc18284e8f8e, files 1-1000144716.png through 4-1000144719.png (first-event distributions, midpoint shares, aggressor lots, individual midpoint heatmaps).

## Next work

1. Find exact generators/data/provenance for recovered crypto screenshots using their titles and labels, including turn selection, sign alignment, winner/loser conditioning, rolling windows, aggregation and the +20-second seam.
2. Build an evidence ledger against current findings: observation, source, population, variable/units, anchor, direction/outcome conditioning, clock/window effects, controls, agreement/difference and unresolved question. Add to the single FINDINGS.md after artifacts, not a competing findings report.
3. Reconcile Desktop's definitions and candidate keys with ours. Then compare actual per-candidate chronological NG paths, preserving long/short or polarity and SAME/FLIP separately. Do not infer causal time-shape from sorted rank distributions.
4. Finish the outstanding parent tail/raw-record audit and review agent's shape_forms outputs. Keep fitted descriptions distinct from mechanisms.
5. Assess existing paper-trading setup independently, including current runnable path, data/clock availability and logging. Confirm actual readiness from evidence; no promise of tonight's start based on these images, and no live-money actions.

Suggested next-chat opening: Read agent-pass/NEXT_CHAT_HANDOFF.md and PUBLICATION.md on GitHub branch codex/native-dipole-agent-pass-20261108 in DavisAI1974/Markets, with artifacts in DavisAI1974/markets-data, and continue on remote compute. Track the recovered crypto dipole-dive and directional pre-onset/tail shapes back to their source, reconcile them against all four-day NG findings and Claude Desktop's results, and keep the existing paper-trading work moving. Preserve raw distributions and storage rules; no live trading or merge.
