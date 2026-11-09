# The Oct 18 dipole cohort pass, repeated on Oct 2, Oct 3 and Oct 17

Claude chat, November 8, 2026. Same code, same matched-control method, each day separate. All four dates remain discovery; Oct 2 and Oct 17 are partial. Every day is one set of dependent observations. Interpretation is in its own section at the end and is labelled.

## 1. What was run, and the replication check

The Oct 18 cohort pass (`claude-pass/c24a` to `c24d`: strict prebirth cutoff, recognition clock, oriented midpoint changes at +1, +5, +20 and +60 s, 500 matched-control draws per measure) was run unchanged in method on the other three sessions. Raw MBO tapes: `NG_v0_mbo_20231001, 02, 03, 16, 17` (sha256 checked against the manifests; Oct 18 re-decoded as the check). Candidate inputs: `replay-comparison/<day>/candidate-inputs.jsonl.gz`.

Replication: re-running Oct 18 through the same scripts reproduces the committed Oct 18 tables (cohort features 852 x 94, cells, controls, signed conditions, rank histogram, the 8 cases, the Codex comparison) with every value identical. The only differences found were blank-versus-missing text in two label columns.

Changes to the scripts, all in copies under `claude-pass-3day/`, none in existing files:
- Date and session parameters (`OD_SESS`), per-session candidate, outcome and event paths.
- Book storage cap raised from 200,001 to 5,000,001 price indices, because Oct 16 holds an order priced at index 3,257,000 (the cap only sets storage size; touch scanning is unchanged, and Oct 18 re-ran identically with the larger cap).
- The four narrated Oct 18 "log cases" are skipped on other days (they are Oct 18 events); the four rule-selected cell cases are kept.
- The candidate inputs of the other days carry no Codex label columns for orientation (SAME/FLIP), the quote-move label, the depth label or the reconstructed baseline and threshold. The SAME/FLIP cells and the two label-agreement rows are therefore absent for Oct 2, 3, 17. Codex's flow state and the outcome-file comparisons are present.

## 2. Coverage (rows in, rows covered, rows out)

| day | candidate rows | covered | not covered | covered by own-day tape | covered by prior-evening tape |
|---|---|---|---|---|---|
| Oct 2 | 741 | 741 | 0 | 741 | 0 |
| Oct 3 | 833 | 824 | 9 (1 finalize-only with no live recognition, 8 at the seam or warm-up) | 782 | 42 |
| Oct 17 | 741 | 740 | 1 (finalize-only) | 740 | 0 |
| Oct 18 | 863 | 852 | 11 (seam or warm-up) | 793 | 59 |

Birth seconds (UTC, from the epoch-second field of the candidate inputs): Oct 2 from 00:20:36 to 20:58:54 on Oct 2; Oct 3 from 22:28:02 on Oct 2 to 20:57:56 on Oct 3; Oct 17 from 00:23:33 to 20:58:14 on Oct 17; Oct 18 from 22:20:15 on Oct 17 to 20:59:24 on Oct 18. Oct 2 and Oct 17 have no births before UTC midnight of their own date.

## 3. Measurements, side by side (share of covered candidates; oriented midpoint change; ties at zero are "flat")

Cohort share moving in the birth direction / against / flat, and the share range of 500 matched-control draws (2.5 to 97.5 percent) for "in":

| measure | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| birth to recognition | 0.437 / 0.275 / 0.287 (control in 0.305-0.370) | 0.397 / 0.266 / 0.337 (0.278-0.338) | 0.442 / 0.273 / 0.285 (0.296-0.359) | 0.444 / 0.323 / 0.234 (0.316-0.379) |
| +1 s | 0.099 / 0.116 / 0.785 (0.152-0.209) | 0.095 / 0.085 / 0.820 (0.146-0.204) | 0.104 / 0.081 / 0.815 (0.149-0.201) | 0.113 / 0.110 / 0.777 (0.168-0.220) |
| +5 s | 0.163 / 0.182 / 0.655 (0.215-0.277) | 0.149 / 0.159 / 0.692 (0.210-0.266) | 0.184 / 0.166 / 0.650 (0.211-0.267) | 0.174 / 0.195 / 0.631 (0.229-0.289) |
| +20 s | 0.281 / 0.290 / 0.429 (0.307-0.374) | 0.257 / 0.266 / 0.477 (0.296-0.365) | 0.285 / 0.277 / 0.438 (0.284-0.349) | 0.302 / 0.288 / 0.411 (0.316-0.383) |
| +60 s | 0.387 / 0.355 / 0.258 (0.368-0.437) | 0.312 / 0.376 / 0.312 (0.362-0.425) | 0.357 / 0.372 / 0.272 (0.348-0.415) | 0.393 / 0.392 / 0.215 (0.374-0.438) |

n per day: 741, 824, 740, 852. Full distributions of every candidate's oriented change, by day and horizon, are in `crossday/crossday-oriented-move-distributions.png`; shares against the control ranges in `crossday/crossday-shares-vs-controls.png`. Every plotted count equals its table row (44 reconciliation rows, `crossday/crossday-chart-reconciliation.csv`).

Recognition delay (seconds from the start of the birth second to recognition), all four days:

| | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| n | 741 | 824 | 740 | 852 |
| delay 48 to under 56 s | 403 | 434 | 417 | 491 |
| delay under 40 s | 93 | 112 | 95 | 120 |
| delay 60 s or more | 150 | 145 | 137 | 102 |
| range | 7.1 to 138.8 | 7.2 to 153.4 | 8.0 to 157.8 | 7.1 to 137.4 |

The delay histogram has the same three parts on every day: a spike at 50 to 52 s, a tail to about 80 s, and a shoulder of recognitions between 8 and 40 s (`crossday/crossday-recognition-delay.png`).

Cells that hold their direction on all four days (counts in / against / flat, birth to recognition):

| Codex flow state at recognition | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| same direction | 122/43/48 | 133/59/63 | 133/48/36 | 153/65/53 |
| opposite direction | 58/95/28 | 59/102/47 | 55/73/30 | 56/126/34 |
| no classified flow | 133/60/129 | 124/51/160 | 132/77/138 | 157/71/111 |

All 19 cells per day, with the +1, +5, +20 and +60 s horizons and the nominal-clock versions, are in the workbook (`cells` sheet).

## 4. The recorded detector operands against the 20 s flow series

For each day, the recorded operands of every candidate were compared with `dipole-completed-group-flow.csv.gz` (the companion observation series; per the method file it is not the saved detector substrate).

| | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| births | 741 | 832 | 740 | 863 |
| seconds with a defined 20 s ratio / with ratio of exactly +1 or -1 | 51,198 / 14,157 | 56,176 / 16,734 | 49,554 / 13,808 | 54,335 / 16,689 |
| births on a second with |ratio| = 1 | 741 | 832 | 738 | 859 |
| polarity equals the sign of the ratio there | 741 | 832 | 738 | 859 |
| recorded magnitude equals |ratio| there (recorded magnitude is 1.0 for all) | 741 | 832 | 738 | 859 |
| prominence equals magnitude minus baseline | 741 | 832 | 740 | 863 |
| threshold values recorded | 1.0 | 1.0 | 1.0 | 1.0 |
| detection lag = 50 s / 41 to 49 s / below 41 s | 526 / 116 / 99 | 584 / 126 / 122 | 545 / 94 / 101 | 599 / 138 / 126 |
| smallest detection lag; smallest gap between births | 6 s; 45 s | 6 s; 45 s | 6 s; 45 s | 6 s; 45 s |
| gaps between births under 50 s | 140 | 159 | 137 | 155 |

Hold rules: take every second with |ratio| = 1, then keep one and skip the next h seconds. The overlap with the recorded birth seconds, by h, is in `crossday/x02_hold_rules.csv`; for example on Oct 3, h = 1 keeps all 16,734 seconds and contains all 832 births; h = 45 yields 928 births of which 530 are recorded; h = 50 yields 882 of which 451 are recorded. No h reproduces the recorded set on any day. Trailing, trailing-inclusive, centred and centred-exclusive windows of 1 to 600 s with mean, median, maximum and minimum of |ratio| matched the recorded baseline for at most 37 percent of Oct 3 births.

The six births not on a second with |ratio| = 1 (Oct 17: `dip-19647-1697525677`, `dip-19647-1697575302`; Oct 18: `dip-19648-1697581526`, `dip-19648-1697598500`, `dip-19648-1697646533`, `dip-19648-1697655970`) sit on seconds where the series window is empty (zero classified lots, ratio undefined, state 2), while their recorded operands say magnitude 1.0 with polarity +1 or -1.

## 5. Interpretation (labelled; not measurements)

SPECULATIVE readings, to be tested rather than adopted:
- The birth-to-recognition share "in the birth direction" is above its 2.5 to 97.5 percent control range on every day (rank 1.0 of 500 draws), and the +1 s and +5 s shares are below their control ranges on every day (rank 0.0). At +20 s the share is below the range on Oct 2, 3 and 18 and at its lower edge on Oct 17 (0.285 against 0.284 to 0.349); at +60 s it is inside the range on Oct 2, 17 and 18 and below it on Oct 3. The windows differ in what they measure: the first window ends when the candidate becomes visible, the others start there. One reading is that the recognition clock is late relative to the move (the spike at 50 to 52 s in the delay histogram is the same size as the recorded 50 s detection lag), so the move that precedes recognition is part of what made the candidate; a second is that the controls, built at arbitrary seconds, do not share the candidate's selection by an extreme one-sided flow window. The distributions do not separate these.
- In the Codex flow-state cells the move before recognition follows the flow sign on every day: with recent flow in the birth direction the quote more often moved in the birth direction, with opposite recent flow it more often moved against. A mechanical reading (trades that drive the touch are the same trades that make the flow window one-sided) is available and consistent with the operand table, where every recorded birth is a fully one-sided window.
- The 50 s lag is recorded in the operands as detection lag 50 for 526 to 599 births per day, with smaller values for the rest; the smaller values and the 8 to 40 s shoulder in the delay histogram may be the same candidates. This pairing was not tested here.

## 6. Open items

- Selection among the 13,808 to 16,734 fully one-sided seconds per day is not recovered by the hold rules or by the windowed baselines tried. The saved detector substrate (action-quote, per the method file) is not in this repository's flow table.
- SAME/FLIP orientation is not in the candidate inputs of Oct 2, 3, 17; it would need the episode records.
- Birth-aligned book and flow paths at one-second resolution (the full event-study form of the plan) are not built yet; the cohort tables here use the cutoffs only.
- Results here are discovery on one day each. Same model, separately fitted.

Data repository check: the sha256 of all six tapes analyzed here (Oct 1, 2, 3, 16, 17, 18) equals the corresponding tape entry in the MANIFEST.json of DavisAI1974/markets-data at commit 968fa11. The tape files were decoded from the earlier locations below; the loaders take the tape path as an argument, so a checkout at MARKETS_DATA_DIR gives the same inputs.

Provenance: tapes at data commit 1d15dc6f (Oct 2, 3, 17, 18) and the codex branch (Oct 1, 16); branch `codex/ng-shadow-discovery-20261108`; code under `claude-pass-3day/`; tables under `claude-pass-3day/tables/dipole/<day>/`; figures under `claude-pass-3day/figures/<day>/` and `claude-pass-3day/crossday/`.
