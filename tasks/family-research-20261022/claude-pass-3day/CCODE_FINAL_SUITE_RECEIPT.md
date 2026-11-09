# Claude Code final three-day suite: frozen receipt (2026-11-09)

For `agent-pass/reanalysis/SHARED_BRIEF.md at da0e2fc27350e791366eafa974e2bdb85e99460b, items 3 and 5`. Machine-readable twin: `CCODE_FINAL_SUITE_RECEIPT.json` (same folder). Written by `x20_final_suite_receipt.py` from committed files only.

## Where

- **three_day_suite**: `DavisAI1974/Markets`, branch `claude/three-day-dipole-20261108`, base `beb2104` -> head `c375c36`, folder `tasks/family-research-20261022/claude-pass-3day/`; 95 files changed or added (listed with bytes and sha256 in the JSON).
- **discovery_record**: `DavisAI1974/Markets`, branch `codex/ng-shadow-discovery-20261108`, base `de084f5` -> head `f1c7277`; 5 files changed or added (listed with bytes and sha256 in the JSON).
- **data**: `DavisAI1974/markets-data`, branch `main`, base `993cf54` -> head `c01caaf`; 10 files changed or added (listed with bytes and sha256 in the JSON).

## Populations and run receipts

| session | families in index / used / excluded | inside member with 60 s records | session groups (first to last) | censored 300 s / 600 s | 60 s lots equal to retained operands buy / sell / of |
| --- | --- | --- | --- | --- | --- |
| 20231002 | 796 / 795 / 1 | 781 | 609,611 (2023-10-01 21:01 to 2023-10-02 20:59) | 0 / 0 | 744 / 752 / 781 |
| 20231003 | 849 / 848 / 1 | 796 | 653,912 (2023-10-02 21:00 to 2023-10-03 20:59) | 2 / 2 | 749 / 742 / 796 |
| 20231017 | 824 / 823 / 1 | 809 | 638,324 (2023-10-16 21:00 to 2023-10-17 20:59) | 3 / 3 | 770 / 774 / 809 |
| 20231018 | 749 / 749 / 0 | 694 | 583,688 (2023-10-17 21:00 to 2023-10-18 20:59) | 4 / 5 | 654 / 656 / 694 |

Tier 2 grid rows after closed-market rows out: 26,980 / 26,980 / 26,979 / 26,980; 2,669 condition/outcome pairs, 49 lead-lag pairs, 42 state cells per member; full pair-coupling rows 5,406 / 5,418 / 5,166 / 5,166.

Chart reconciliation: 27 panels over 7 figures, all plotted counts equal to table rows: True.

## Oct 18 reference

- claude-pass/tables/t1_*.csv (12 files; 749 families; the matched-50 pass included); reproduced value for value by x18 on the rebuilt grids
- claude-pass/tables/t2_*.csv and tables/20231018_legacy/ (legacy mode: retained export groups, no closed-market exclusion, age_s and qage_s out of X; 2,635 pairs, 44 cells); the dense run used for the four-day comparison is tables/20231018/t2_*.csv (2,669 pairs, 42 cells); the reason is recorded in FINDINGS_TIER2_CROSSDAY_20261109.md section 1
- claude-pass/tables/crossday/t4_*.csv (c19 to c23) already covered the four days and is unchanged
- claude-pass-3day/tables/dipole/<session>/t6_* and FINDINGS_THREE_DAYS_20261108.md (Desktop's pass), unchanged

## Clocks

- **tier1_family_master**: start_recv_ns (family start receive clock, ns); cutoff_ns = start_recv_ns - 1 ns (strict decision boundary; the Oct 18 ledger's own rule, 749 of 749); ref_recv_ns (receive clock of the last group known by the cutoff: the reference midpoint and touch); start_utc (ISO); outcomes at start + h for h in 1, 5, 20, 60, 120, 300, 600 s from the last group known by then; grp_<h>s = -1 and chg NaN where the horizon passes the 21:00 UTC close; order-level windows end at cutoff (start - 1 ns) over the previous 1, 5, 20, 60 s; NaN where the window begins before the date member
- **tier1_pin_ledgers**: every record carries start, cutoff and reference-group clocks as ns and UTC; pins carry known_by_cutoff_ns, known_by_receive_ns (reference group) or outcome_window_start_plus_<h>s
- **tier2_tables**: per UTC member; decisions every 3 s with features as of the cutoff and outcomes after it (c12); one-second series by receive second (c16, c17); closed-market rows and seconds left out (odcfg.closed_mask); the cross-day tables are aggregates with no clock of their own
- **session_scope**: session groups = prior member from 21:00 UTC to the date member's 21:00 UTC close; Oct 2 and Oct 17 are partial from the UTC snapshot (their family indexes begin at 00:00 UTC), Oct 3 and Oct 18 full sessions

## Time-sensitive new files (brief item 5)

Per-event rows: the eight Tier 1 family masters (one row per family start). Pinned to the 99-layer registry as the four `ninety-nine-pins-tier1-<tag>.jsonl.gz` ledgers in markets-data (oct02: 795 rows, 135945 pins, oct03: 848 rows, 145008 pins, oct17: 823 rows, 140733 pins, oct18: 749 rows, 133322 pins); declared registry file sha256 `7ee754f1f9b080cdc5b7b68cf75829897d6216a1fadbb4b8a5ecd7b4f2133e06`. Everything else new is an aggregate over those rows or over the Tier 2 grids and carries no clock of its own.

## Limitations

- Each day is one session of one instrument; nothing is pooled across days; counts of days are counts.
- The Tier 2 cross-day reference distribution is 20 shifted-Y draws per day combined day by day; the regime comparison used the same count.
- Pair couplings beyond the line are rare by construction (family-wise line over 40 shifts on every third pair, as c15 defined it).
- Tier 1 order-level windows exist only for families inside the date member with a full window; the 60 s aggressor-lot reconciliation to the retained ROOT operands is 744/752, 749/742, 770/774, 654/656 of 781, 796, 809, 694 (the rest differ by the unknown-side lots the retained operands count differently; not examined further).
- The session groups come from the rebuilt tapes, not the retained exports; on Oct 18 they reproduce the export-based tables exactly (583,688 groups).
- Oct 2 and Oct 17 family indexes begin at the UTC snapshot; the prior evening of those sessions is in the group arrays (from the prefix members) but no family start of theirs falls in it.
- No trade cost, fee, slippage or execution assumption anywhere; these are discovery readouts on already-studied days, not out-of-sample validation.

## Not done, by direction

- agreement/disagreement pass against the Codex and Desktop passes
- the 99 and 13 crosswalk (Codex reconciles; one copy)
- detector reverse-engineering (Desktop's 3C)
- c13 and c14_deseason variants (superseded by c14 and c19)
- Desktop's 3D issue-13 follow-up (drafted, unposted)
