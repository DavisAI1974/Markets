# Frankie findings — frankie-a-memory-rt-33746436209-1

**This file is a RENDER of `frankie_principal_findings.json`. Do not edit it.**
Edit the findings artifact and re-render. The report is generated from the findings
so the two cannot diverge: a report authored separately from its evidence can omit
the evidence and still look complete, which is how 44 findings went unread once.

| | |
|---|---|
| run_id | `frankie-a-memory-rt-33746436209-1` |
| principal | `claude-fable-5-1` |
| arm | `A_MEMORY` |
| role | `REAL_TIME_FRANKIE` |
| source_day | `20211003` |
| evidence_result_hash | `c406eee730401de16165b46091ac3042a1ca49d9025bbaefa9aa272bf52e420b` |

## What the principal read

| exact ledger | read status |
|---|---|
| `exact_lifecycle_and_runway_ledger` | **READ** |
| `exact_member_ledger` | **READ** |
| `legacy_observable_rows` | **READ** |

Every exact ledger was declared READ.

**18 findings.** The count is stated because a reader cannot notice an
absent finding without a denominator to check it against.

## Day-over-day memory carry

These are the new findings this artifact asks the automatic A-memory carry to retain.
Their own evidence, falsifier, and confidence basis explain why each is carried;
only later stream evidence may change UNVERIFIED to VERIFIED.

#### Carry F-45

**Claim.** My own computation of the per-second aggressor substrate reproduces the runner's delivered substrate row-for-row, and my own causal detector reproduces its candidate population exactly. Over 17991 completed seconds compared as they became lawful, 17991 agree on buy volume, sell volume, own-second class, trailing-window direction and roll20 and 0 disagree. Running the same declared rules myself over the raw legacy rows, my detector promoted 91 candidates and 91 of them fall on the same event second as a delivered candidate row. This is the load-bearing check on the traversal: two independent implementations of the same contract text, one on the box and one here, over the same bytes.

**Evidence.**
```json
{
  "agree": 17991,
  "delivered_candidate_rows_seen": 91,
  "detector_counters": {
    "candidates_emitted": 91,
    "candidates_pending_in_window": 0,
    "rejected_below_threshold": 1672,
    "rejected_in_refractory": 294,
    "rejected_in_refractory_at_release": 17,
    "rejected_not_local_max": 14,
    "rejected_zero_magnitude": 338,
    "seconds_in_warmup": 11399,
    "seconds_judged": 17981,
    "seconds_observed": 17991,
    "seconds_without_finite_flow": 2103,
    "suppressed_by_prominence": 2053
  },
  "disagree": 0,
  "legacy_rows_consumed": 22380,
  "matched_on_event_second": 91,
  "my_own_bookkeeping_defect": "the reconcile block's `delivered` (182) and `delivered_only` fields double-count: matched rows were never removed from the delivered map, so `delivered` is 91 delivered rows plus 91 matches and `delivered_only` lists event seconds that were in fact matched. The load-bearing counters - own 91, matched 91, own_only empty - are unaffected, and I report the defect rather than the tidy number.",
  "own_candidates": 91,
  "own_class_census": {
    "BUY": 370,
    "EXCLUDED_AT_MID": 2,
    "NO_DIRECTION": 17246,
    "SELL": 373
  },
  "own_window_census": {
    "LONG": 2489,
    "NO_DIRECTION": 13267,
    "SHORT": 2235
  },
  "seconds_compared": 17991
}
```

**Falsifier.** A single second where the two disagree on classified volume or class, or a promoted candidate on an event second the delivered rows do not carry, falsifies the reconciliation; the counters are reported whether they are zero or not.

**Confidence basis.** Both sides were computed from the same legacy observable rows by the same declared midpoint rule, but by different code on different machines, and the comparison was made second by second as each second completed rather than on a whole-day total, so an offsetting pair of errors cannot cancel.

#### Carry F-46

**Claim.** The touch is NOT static on this instrument once the ladder is measured on the FULL book. Computing 4.9 as an exact set difference between consecutive groups' complete after-books (book_full.*_levels_full), the spread changes on 3663 COMPRESSION and 2311 EXPANSION transitions of 43569, and the best price on one side or the other moves on 6079 occasions, with per-side tick distributions that are not symmetric. A group-local view of the same day - one that can only see the levels the group's own orders touch - sees almost none of this, because most touch movement is caused by orders that the group being scored did not itself act on. The scope of the ladder measurement, not the market, decides whether the book looks frozen.

**Evidence.**
```json
{
  "dominant_stratum": {
    "key": "ow-0069e456ba86b8f3b52e|A|PRE_SETTLEMENT",
    "max_gap_ticks": {
      "max": 5820000,
      "mean": 1746958.08,
      "min": 1314,
      "n": 50,
      "p10": 1314,
      "p25": 1380,
      "p50": 1380,
      "p75": 5820000,
      "p90": 5820000,
      "p99": 5820000,
      "sum": 87347904.0
    },
    "occupied_levels": {
      "max": 259,
      "mean": 232.3,
      "min": 102,
      "n": 50,
      "p10": 219,
      "p25": 230,
      "p50": 236,
      "p75": 245,
      "p90": 251,
      "p99": 259,
      "sum": 11615.0
    }
  },
  "touch_migration_events": 6079,
  "touch_migration_ticks_ask": [
    [
      -1,
      1676
    ],
    [
      1,
      651
    ],
    [
      2,
      221
    ],
    [
      3,
      123
    ],
    [
      -2,
      96
    ],
    [
      4,
      80
    ]
  ],
  "touch_migration_ticks_bid": [
    [
      1,
      1270
    ],
    [
      -1,
      597
    ],
    [
      -2,
      158
    ],
    [
      -3,
      123
    ],
    [
      2,
      120
    ],
    [
      3,
      106
    ]
  ],
  "touch_state_census": {
    "COMPRESSION": 3663,
    "EXPANSION": 2311,
    "UNCHANGED": 37594,
    "UNDEFINED_ONE_SIDE_EMPTY": 1
  },
  "transitions": 43569
}
```

**Falsifier.** If the movement I measure were an artifact of comparing consecutive after-books across groups that arrive out of order, the receive clock would have to move backwards somewhere; the stream refuses that and delivered every group in ts_recv_ns order. A stronger falsifier: a day on which the full-book set difference and a group-local difference give the same touch-migration count.

**Confidence basis.** Every transition is an exact set difference over integer raw prices with its own before and after level set; the counts sum to the group count with no residual, and the two sides are kept apart.

#### Carry F-47

**Claim.** Under a strict one-attribution episode rule - each removal of resting quantity opens an episode at (side, price) and is closed by the FIRST later arrival at that price or one tick either side, and the modify that moved an order can never restore its own episode - the touch is still restored faster than the level behind it, and the effect survives the change of rule. 26668 episodes opened, 25974 resolved and 694 were still pending at the stream end (censored, not never-restored). The within-family, within-side AT_TOUCH versus BEHIND_TOUCH median ratios are [379.3, 405.3, 1.4, 0.3, 2.2, 2.1]. Because each arrival is credited once, my replenishment ratios are net first-arrival ratios and are NOT the arrival-density figures a many-to-one attribution produces; the two answer different questions and must not be compared.

**Evidence.**
```json
{
  "episodes": 26668,
  "pending_censored": 694,
  "price_relations": {
    "NEIGHBOUR_1_TICK": 10079,
    "SAME_PRICE": 15895
  },
  "refill_kinds": {
    "NEW_ID_ADD": 21419,
    "RESHAPED_RESIDUAL_REPRICE": 4514,
    "RESHAPED_RESIDUAL_SIZE_UP": 41
  },
  "removal_kinds": {
    "C": 19444,
    "F": 2411,
    "M_REPRICE_AWAY": 4625,
    "M_SIZE_DOWN": 188
  },
  "resolved": 25974,
  "touch_displacements": 36,
  "touch_restoration_time_ns": {
    "max": 1850097476139,
    "mean": 56193412020.76471,
    "min": 69976,
    "n": 34,
    "p10": 236184,
    "p25": 423804,
    "p50": 1639709,
    "p75": 1416822240,
    "p90": 3091801621,
    "p99": 1850097476139,
    "sum": 1910576008706.0
  },
  "within_family_within_side_pairs": [
    {
      "at_touch_median_ns": 1774647,
      "at_touch_n": 556,
      "behind_touch_median_ns": 673102126,
      "behind_touch_n": 7636,
      "family_side": "ow-40540069fe5aeddc127b|B",
      "ratio": 379.3
    },
    {
      "at_touch_median_ns": 1378939,
      "at_touch_n": 400,
      "behind_touch_median_ns": 558842876,
      "behind_touch_n": 6501,
      "family_side": "ow-59ace24da4a485c605b6|A",
      "ratio": 405.3
    },
    {
      "at_touch_median_ns": 1347065,
      "at_touch_n": 815,
      "behind_touch_median_ns": 1890331,
      "behind_touch_n": 579,
      "family_side": "ow-7b10d38a8b61511bc611|A",
      "ratio": 1.4
    },
    {
      "at_touch_median_ns": 4990034,
      "at_touch_n": 591,
      "behind_touch_median_ns": 1607344,
      "behind_touch_n": 197,
      "family_side": "ow-8c934d067bc463c01ce0|B",
      "ratio": 0.3
    },
    {
      "at_touch_median_ns": 1243382,
      "at_touch_n": 256,
      "behind_touch_median_ns": 2700538,
      "behind_touch_n": 391,
      "family_side": "ow-1fe202ccc7ea51ea8050|A",
      "ratio": 2.2
    },
    {
      "at_touch_median_ns": 321908086,
      "at_touch_n": 77,
      "behind_touch_median_ns": 670845501,
      "behind_touch_n": 68,
      "family_side": "ow-2b87a13fb17c35fb43c5|B",
      "ratio": 2.1
    }
  ]
}
```

**Falsifier.** A family and side whose AT_TOUCH median exceeds its BEHIND_TOUCH median, or an episode population where the pending count is a large share of the opened count (which would make the medians a censoring artifact rather than a restoration time).

**Confidence basis.** The comparison changes exactly one key - touch state - inside one family and one side, so it cannot be a family, side, phase or day effect; pending episodes are carried in the survival estimator's at-risk set rather than dropped.

#### Carry F-48

**Claim.** Delivered pressure looks rare or common depending entirely on how long the runway is, and I measured both. On the group-scoped runway (the F_LAST group carrying the fill) the census is {'ABSORBED_WITHOUT_PRICE_MOVE': 160, 'ACCOMPANIED_BY_WITHDRAWAL': 261, 'DELIVERED_THROUGH_PRICE': 993, 'INDETERMINATE': 157, 'INDETERMINATE_NO_CONTACT': 41998}. On the CONTACT runway - from a fill-bearing group through every following group until the next contact - the same day gives {'ABSORBED_WITHOUT_PRICE_MOVE': 75, 'ACCOMPANIED_BY_WITHDRAWAL': 453, 'DELIVERED_THROUGH_PRICE': 886} over 1414 runways spanning a median of 17 groups and 535089478 ns. Widening the window from one group to the interval between contacts moves the classification, so a disposition census is a statement about the runway definition first and about the market second.

**Evidence.**
```json
{
  "contact_runway_census": {
    "ABSORBED_WITHOUT_PRICE_MOVE": 75,
    "ACCOMPANIED_BY_WITHDRAWAL": 453,
    "DELIVERED_THROUGH_PRICE": 886
  },
  "contact_runways": 1414,
  "duration_ns": {
    "max": 235056393027,
    "mean": 5089054652.084866,
    "min": 13486,
    "n": 1414,
    "p10": 347622,
    "p25": 1739465,
    "p50": 535089478,
    "p75": 3871861339,
    "p90": 13161492080,
    "p99": 60675287441,
    "sum": 7195923278048.0
  },
  "group_scoped_census": {
    "ABSORBED_WITHOUT_PRICE_MOVE": 160,
    "ACCOMPANIED_BY_WITHDRAWAL": 261,
    "DELIVERED_THROUGH_PRICE": 993,
    "INDETERMINATE": 157,
    "INDETERMINATE_NO_CONTACT": 41998
  },
  "price_response_ticks": {
    "max": 27.5,
    "mean": 0.070014144,
    "min": -25.5,
    "n": 1414,
    "p10": -2.5,
    "p25": -1.0,
    "p50": 0.0,
    "p75": 1.0,
    "p90": 2.5,
    "p99": 9.0,
    "sum": 99.0
  },
  "span_groups": {
    "max": 555,
    "mean": 30.666195191,
    "min": 1,
    "n": 1414,
    "p10": 2,
    "p25": 5,
    "p50": 17,
    "p75": 44,
    "p90": 76,
    "p99": 165,
    "sum": 43362.0
  },
  "top_strata": {
    "ow-0069e456ba86b8f3b52e|N|PRE_SETTLEMENT|INDETERMINATE": {
      "n": 50,
      "price_response_ticks": {
        "n": 0
      },
      "traded": {
        "max": 2,
        "mean": 1.02,
        "min": 1,
        "n": 50,
        "p10": 1,
        "p25": 1,
        "p50": 1,
        "p75": 1,
        "p90": 1,
        "p99": 2,
        "sum": 51.0
      },
      "withdrawn": {
        "max": 0,
        "mean": 0.0,
        "min": 0,
        "n": 50,
        "p10": 0,
        "p25": 0,
        "p50": 0,
        "p75": 0,
        "p90": 0,
        "p99": 0,
        "sum": 0.0
      }
    },
    "ow-174847199f25c91ccb41|A|PRE_SETTLEMENT|ABSORBED_WITHOUT_PRICE_MOVE": {
      "n": 7,
      "price_response_ticks": {
        "max": 0.0,
        "mean": 0.0,
        "min": 0.0,
        "n": 7,
        "p10": 0.0,
        "p25": 0.0,
        "p50": 0.0,
        "p75": 0.0,
        "p90": 0.0,
        "p99": 0.0,
        "sum": 0.0
      },
      "traded": {
        "max": 2,
        "mean": 1.142857143,
        "min": 1,
        "n": 7,
        "p10": 1,
        "p25": 1,
        "p50": 1,
        "p75": 1,
        "p90": 1,
        "p99": 2,
        "sum": 8.0
      },
      "withdrawn": {
        "max": 0,
        "mean": 0.0,
        "min": 0,
        "n": 7,
        "p10": 0,
        "p25": 0,
        "p50": 0,
        "p75": 0,
        "p90": 0,
        "p99": 0,
        "sum": 0.0
      }
    },
    "ow-1b64a25174ce60aae233|N|PRE_SETTLEMENT|INDETERMINATE": {
      "n": 5,
      "price_response_ticks": {
        "n": 0
      },
      "traded": {
        "max": 1,
        "mean": 1.0,
        "min": 1,
        "n": 5,
        "p10": 1,
        "p25": 1,
        "p50": 1,
        "p75": 1,
        "p90": 1,
        "p99": 1,
        "sum": 5.0
      },
      "withdrawn": {
        "max": 0,
        "mean": 0.0,
        "min": 0,
        "n": 5,
        "p10": 0,
        "p25": 0,
        "p50": 0,
        "p75": 0,
        "p90": 0,
        "p99": 0,
        "sum": 0.0
      }
    },
    "ow-1f6c5bd2663dbea89be3|B|PRE_SETTLEMENT|DELIVERED_THROUGH_PRICE": {
      "n": 16,
      "price_response_ticks": {
        "max": -0.5,
        "mean": -1.625,
        "min": -5.0,
        "n": 16,
        "p10": -3.0,
        "p25": -2.0,
        "p50": -1.0,
        "p75": -1.0,
        "p90": -0.5,
        "p99": -0.5,
        "sum": -26.0
      },
      "traded": {
        "max": 6,
        "mean": 2.4375,
        "min": 2,
        "n": 16,
        "p10": 2,
        "p25": 2,
        "p50": 2,
        "p75": 2,
        "p90": 4,
        "p99": 6,
        "sum": 39.0
      },
      "withdrawn": {
        "max": 6,
        "mean": 2.4375,
        "min": 2,
        "n": 16,
        "p10": 2,
        "p25": 2,
        "p50": 2,
        "p75": 2,
        "p90": 4,
        "p99": 6,
        "sum": 39.0
      }
    }
  }
}
```

**Falsifier.** If the disposition were a property of the market rather than of the window, the two censuses would have the same shape. A day where they do would falsify this.

**Confidence basis.** Both censuses are complete partitions of their own populations (every group is classified, every contact runway closes at the next contact or the stream end) and both were computed in the same pass from the same raw actions, so the difference is the scope and nothing else.

#### Carry F-49

**Claim.** Exhaustion runways DO complete on this slice once a completion rule is actually fed. Giving each promoted candidate a runway that advances one completed second at a time - PERSISTENCE while the trailing window flow keeps the birth polarity, REVERSAL while it opposes it, QUIET_NO_DIRECTION at zero, completion when a reversal is followed by LOCAL_RADIUS consecutive seconds carrying no classified volume, extension when a later same-polarity candidate is born inside an open runway and completion-by-opposition when an opposite one is - the 91 candidates resolve as {'CENSORED_STREAM_END': 1, 'COMPLETED_BY_OPPOSITE_CANDIDATE': 22, 'COMPLETED_DECAY': 35, 'EXTENDED_BY_SUCCESSOR': 33}, with phase census {'BIRTH': 91, 'REVERSAL': 118, 'PERSISTENCE': 105, 'QUIET_NO_DIRECTION': 156}. Chain depth on this candidate lineage is {'0': 36, '1': 22, '2': 13, '3': 6, '4': 4, '5': 4, '6': 3, '7': 1, '8': 1, '9': 1}. The earlier reading that no runway ever completes was a property of a runway with no completion rule attached, not of the market.

**Evidence.**
```json
{
  "candidates": 91,
  "chain_depths": {
    "0": 36,
    "1": 22,
    "2": 13,
    "3": 6,
    "4": 4,
    "5": 4,
    "6": 3,
    "7": 1,
    "8": 1,
    "9": 1
  },
  "completed_or_extended": {
    "COMPLETED_BY_OPPOSITE_CANDIDATE": 22,
    "COMPLETED_DECAY": 35,
    "EXTENDED_BY_SUCCESSOR": 33
  },
  "orientation_counts": {
    "FLIP": 46,
    "NO_PREDECESSOR": 1,
    "SAME": 44
  },
  "phase_census": {
    "BIRTH": 91,
    "PERSISTENCE": 105,
    "QUIET_NO_DIRECTION": 156,
    "REVERSAL": 118
  },
  "phase_depletion_refill": null,
  "status_counts": {
    "CENSORED_STREAM_END": 1,
    "COMPLETED_BY_OPPOSITE_CANDIDATE": 22,
    "COMPLETED_DECAY": 35,
    "EXTENDED_BY_SUCCESSOR": 33
  }
}
```

**Falsifier.** The completion rule is mine and is stated in the 4.10 ledger; a different rule gives a different census, which is why the rule travels on every entry. It is falsified by a candidate marked COMPLETED_DECAY whose polarity side keeps trading after the quiet run, or by a successor assignment that spans a continuity boundary (there is only one segment here, so none can).

**Confidence basis.** Each transition is decided from completed-second quantities that were lawful at the second they were read; no completed duration is used at an earlier cutoff, and every runway still open at the stream end is CENSORED rather than counted as complete.

#### Carry F-50

**Claim.** A lawful pre-birth signal exists on this unit and it is weak, and both halves of that sentence are measurements. The earliest lawful precursor I can build from the same substrate is the threshold-crossing alert: the first second of the contiguous run in which |roll20| is at or above the trailing causal bar that ends at the candidate's event second, knowable one second later. It labels 35 of 91 candidates PRIOR, the rest {'H+N': 55, 'T0': 1}. But the same rule fired 160 alerts across the day, so its precision as a standalone trigger is 0.5687 - most crossings are followed by no promotion at all. A pre-birth lead measured only over the candidates that were later promoted is a survivor statistic; the denominator that matters is every alert.

**Evidence.**
```json
{
  "alert_precision": 0.5687,
  "alerts_total": 160,
  "candidates": 91,
  "detector_counters": {
    "candidates_emitted": 91,
    "candidates_pending_in_window": 0,
    "rejected_below_threshold": 1672,
    "rejected_in_refractory": 294,
    "rejected_in_refractory_at_release": 17,
    "rejected_not_local_max": 14,
    "rejected_zero_magnitude": 338,
    "seconds_in_warmup": 11399,
    "seconds_judged": 17981,
    "seconds_observed": 17991,
    "seconds_without_finite_flow": 2103,
    "suppressed_by_prominence": 2053
  },
  "precursor_labels": {
    "H+N": 55,
    "PRIOR": 35,
    "T0": 1
  },
  "promotion_lag_seconds": null
}
```

**Falsifier.** A stratum in which alert precision rises materially above the base rate would make the alert a usable pre-birth trigger; a day on which the alert never precedes a promotion at all would remove the PRIOR class entirely.

**Confidence basis.** The alert population and the promotion population are counted over the same seconds by the same bar, and the precision is a ratio of two exact counts with its denominator stated; nothing here is averaged over successful detections alone.

#### Carry F-51

**Claim.** The nineteen lawful decision points of this run were placed by a group count, not by anything the market did, and I measured what that costs. Every staged cutoff is an exact multiple of 2,281 groups, which is int(57,027 records x 0.8 groups-per-record / 20 target spawns) as the launch workflow computes it, and the launcher installs a pure count cadence (native_a_arm_launch._GroupCadence) while an event-driven cadence that triggers on a recognition or a 4.16 change point (native_replay_driver.CandidateEventCadence) exists in the driver and is not used on this path. Against my own events: 91 promotions waited a median of 381.945525951 s (p90 1040.440119355 s, max 1382.440119355 s) for the next staged cutoff at which I could speak about them, and 3 fell beyond the last staged cutoff entirely; 356 change points and 6079 touch migrations waited a median of 356.523516424 s and 47.272155612 s. 10 of the 19 staged cutoffs carried no new promotion at all, while an event-driven cadence on promotions alone would have placed 91 decision points, each one on the second the thing became knowable.

**Evidence.**
```json
{
  "cadence_arithmetic": "57,027 records x 0.8 / 20 = 2,281 groups; every staged cutoff is a multiple of 2,281",
  "event_driven_points_on_promotions": 91,
  "events": {
    "CHANGE_POINT": {
      "beyond_last_staged_cutoff": 7,
      "cutoffs_that_would_have_carried_one": 9,
      "events": 356,
      "wait_to_next_staged_cutoff_seconds": {
        "max": 1301.440119355,
        "mean": 431.692757,
        "min": 1.440119355,
        "n": 349,
        "p10": 56.945525951,
        "p50": 356.523516424,
        "p90": 978.440119355
      }
    },
    "PROMOTION": {
      "beyond_last_staged_cutoff": 3,
      "cutoffs_that_would_have_carried_one": 9,
      "events": 91,
      "wait_to_next_staged_cutoff_seconds": {
        "max": 1382.440119355,
        "mean": 470.348577,
        "min": 23.744781866,
        "n": 88,
        "p10": 85.969569876,
        "p50": 381.945525951,
        "p90": 1040.440119355
      }
    },
    "TOUCH_MIGRATION": {
      "beyond_last_staged_cutoff": 18,
      "cutoffs_that_would_have_carried_one": 19,
      "events": 6079,
      "wait_to_next_staged_cutoff_seconds": {
        "max": 1368.843351714,
        "mean": 201.017371,
        "min": 0.0,
        "n": 6061,
        "p10": 3.126303077,
        "p50": 47.272155612,
        "p90": 642.922389642
      }
    }
  },
  "staged_cutoffs": 19,
  "staged_cutoffs_with_no_new_promotion": 10,
  "staged_group_indices": [
    2281,
    4562,
    6843,
    9124,
    11405,
    13686,
    15967,
    18248,
    20529,
    22810,
    25091,
    27372,
    29653,
    31934,
    34215,
    36496,
    38777,
    41058,
    43339
  ]
}
```

**Falsifier.** If the count cadence were incidental rather than structural, the staged group indices would not all be exact multiples of one number. They are; the falsifier is a run whose cutoffs are not.

**Confidence basis.** The line of inquiry was pointed out to me by the coordinator and I verified it independently: I read the cutoff list from cutoffs.json and checked the divisibility myself, read the cadence arithmetic in the launch workflow and the two cadence classes in the repository, and every wait figure is measured from my own events against those cutoffs. Nothing here is taken on the coordinator's word.

#### Carry F-52

**Claim.** Two of the runner's own per-section row families do not exist at any decision point of this run: they are emitted only at the stream end. Across the whole traversal 21651 delivered lineage rows rode inside a group (19 of the cutoffs saw none), and the mirror rows that did arrive carried only the PENDING disposition, with the matched dispositions arriving at the close. The rows drained after exhaustion are {}. For a real-time reader that means sections 4.13 and 4.4 exist only in the post-mortem as delivered. This is an emission-cadence fact about the runner, not a limit of the evidence: my own 4.4 pairing (a partner is the most recent earlier member with the swapped side string) and my own 4.13 chain lineage (a candidate born inside an open runway is its successor) were both computable and written at every one of the twenty cutoffs, so the information needed to emit them during the stream is present in the stream.

**Evidence.**
```json
{
  "cutoffs_with_only_pending_mirror": 19,
  "cutoffs_with_zero_delivered_lineage": 19,
  "delivered_lifecycle_counts_in_stream": {
    "absorption": 43569,
    "candidate": 91,
    "detector_coverage": 1,
    "episode": 182,
    "exhaustion": 1,
    "flow_substrate": 17992,
    "ladder": 87138,
    "lineage": 21651,
    "mirror": 87138,
    "queue": 20005,
    "recurrence": 43569,
    "replenishment": 73480,
    "response": 630
  },
  "drained_at_stream_end_by_section": {},
  "own_pairs_and_nodes_at_each_cutoff": [
    {
      "cutoff_recv_ns": 1633298413318097271,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 2282
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 2235
    },
    {
      "cutoff_recv_ns": 1633298449136124134,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 4563
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 4490
    },
    {
      "cutoff_recv_ns": 1633298458819212131,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 6844
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 6751
    },
    {
      "cutoff_recv_ns": 1633298467489465095,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 9125
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 9003
    },
    {
      "cutoff_recv_ns": 1633298495252279199,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 11406
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 11272
    },
    {
      "cutoff_recv_ns": 1633298539321423187,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 13687
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 13533
    },
    {
      "cutoff_recv_ns": 1633298618241396322,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 15968
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 15805
    },
    {
      "cutoff_recv_ns": 1633298727046687558,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 18249
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 18075
    },
    {
      "cutoff_recv_ns": 1633298843554132312,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 20530
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 20349
    },
    {
      "cutoff_recv_ns": 1633298998928924813,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 22811
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 22616
    },
    {
      "cutoff_recv_ns": 1633299505523516424,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 25092
      },
      "own_lineage_nodes": 6,
      "own_mirror_pairs": 24884
    },
    {
      "cutoff_recv_ns": 1633299950655145332,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 27373
      },
      "own_lineage_nodes": 13,
      "own_mirror_pairs": 27158
    },
    {
      "cutoff_recv_ns": 1633300320102307848,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 29654
      },
      "own_lineage_nodes": 19,
      "own_mirror_pairs": 29412
    },
    {
      "cutoff_recv_ns": 1633300905784605734,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 31935
      },
      "own_lineage_nodes": 28,
      "own_mirror_pairs": 31680
    },
    {
      "cutoff_recv_ns": 1633301315945525951,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 34218
      },
      "own_lineage_nodes": 34,
      "own_mirror_pairs": 33949
    },
    {
      "cutoff_recv_ns": 1633302013969569876,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 36497
      },
      "own_lineage_nodes": 45,
      "own_mirror_pairs": 36220
    },
    {
      "cutoff_recv_ns": 1633302779744781866,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 38778
      },
      "own_lineage_nodes": 54,
      "own_mirror_pairs": 38492
    },
    {
      "cutoff_recv_ns": 1633304073331796184,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 41059
      },
      "own_lineage_nodes": 70,
      "own_mirror_pairs": 40757
    },
    {
      "cutoff_recv_ns": 1633305465440119355,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 43340
      },
      "own_lineage_nodes": 88,
      "own_mirror_pairs": 43033
    },
    {
      "cutoff_recv_ns": 1633305596372071705,
      "delivered_lineage_rows_attached": 21651,
      "delivered_mirror_rows_attached": {
        "PENDING": 43569,
        "UNMATCHED": 43569
      },
      "own_lineage_nodes": 91,
      "own_mirror_pairs": 43262
    }
  ],
  "withheld_summary": {
    "legacy": 0,
    "lifecycle": {}
  }
}
```

**Falsifier.** A lineage or matched-mirror row attached to a group before the stream end falsifies the emission claim. Separately, if my own in-stream 4.4/4.13 entries had needed any quantity that was not lawful at their cutoff, the ledger's cutoff ordering would have refused them.

**Confidence basis.** The line of inquiry was pointed out to me by the coordinator and I verified it independently: the counts come from my own stream, which tallies every attached lifecycle row by section as it rides inside a group and every withheld row by reason at the close, and from my own per-cutoff section ledgers. I did not re-use the coordinator's figures.

#### Carry F-53

**Claim.** Five retained fields are defective as carried rather than merely degenerate, and the distinction matters because a degenerate field costs nothing while a defective one can be read as a measurement. book_regime.best_bid and book_regime.best_ask are the integer 5 on every row while the real touch sits around 5.53-5.64, so book_regime.spread_raw is 0 on every row and the block's relative_imbalance is the only usable number in it; activity_since.last_trade.trade_buy_aggressor_qty and trade_sell_aggressor_qty are 0 on every row on a day carrying 2,028 trades and 2,411 fills, so the anchor window's aggressor tally is not being fed. I recommend they be REPAIRED, not dropped: each is cheap, each has an obvious correct value, and each currently reads as a real zero to anyone who does not check it against book_full.

**Evidence.**
```json
{
  "activity_since_last_trade_aggressor_qty": {
    "buy": 0,
    "day_fills": 2411,
    "day_trades": 2028,
    "sell": 0
  },
  "book_regime_best_ask_only_value": 5,
  "book_regime_best_bid_only_value": 5,
  "book_regime_spread_raw_only_value": 0,
  "true_touch_from_book_full": {
    "first_best_ask_raw": 5553000000,
    "first_best_bid_raw": 5530000000,
    "note": "book_full carries the correct integer raw prices on the same rows"
  }
}
```

**Falsifier.** A day on which book_regime.spread_raw takes a nonzero value, or on which the anchor aggressor tallies move, would show these are fed and merely quiet here.

**Confidence basis.** Each is a single-valued field in my own census over the rows I streamed, checked against a different field on the same row that carries the correct quantity, so this is a contradiction inside one row rather than an inference across rows.

#### Carry F-54

**Claim.** KEEP EVERYTHING. Having computed all eighteen contract sections from the raw member rows myself, no field group and no registry layer on this surface meets the zero-value bar, and I recommend no elimination. book_full with its per-level FIFO queues is the most load-bearing block on the surface: my queue survival, birth position, replenishment episodes, ladder topology and every state frame rest on it, and the top-N projection beside it is not a substitute because the touch moves between levels the projection does not carry. The order identities and queue-position facts are the join keys of 4.6, 4.7 and 4.14 and nothing else can supply them. The genuinely redundant material - the top-N book projection, the legacy ten-level sizes, the derived age fields - is recoverable from book_full by a stated derivation, and I still recommend keeping it: it is small, and its value is that a reader can check the derivation rather than trust it. The fields nothing read on this day (raw flags, sequence deltas, the adapter's precomputed fill-disposition and mirror blocks) are genuine spares, not defects: they would carry information on a multi-channel or out-of-order day, and this Sunday is neither. Size was never an argument in this judgement.

**Evidence.**
```json
{
  "cannot_judge": [
    "canonical_predecessor_bootstrap_objects",
    "legacy_structure_observables",
    "derived_d_family_geometry",
    "prebirth_stopped_chain_false_context_controls"
  ],
  "elimination_recommendations": 0,
  "field_paths_censused": 605,
  "most_load_bearing": "book_full.*_levels_full[].fifo_queue[] (order_id, size, volume_ahead, priority_recv_ns, priority_sequence)",
  "redundant_but_keep": [
    "book.* top-N projection",
    "legacy row bid/ask 10-level sizes",
    "front_order_age_s / priority_age_s / queue_age_*",
    "largest_order_share"
  ],
  "registry_layers_reviewed": 55,
  "repair_not_remove": [
    "book_regime.best_bid",
    "book_regime.best_ask",
    "book_regime.spread_raw",
    "activity_since.last_trade.trade_buy_aggressor_qty",
    "activity_since.last_trade.trade_sell_aggressor_qty"
  ]
}
```

**Falsifier.** An elimination recommendation would be justified by a field or layer that no section reads, that is not recoverable from another field, and that could not carry information on any future day. I found none; a single such field named with all three properties shown would falsify this verdict.

**Confidence basis.** The judgement rests on my own field census over the rows I streamed and on having actually computed every section from those fields, so 'load-bearing' means a reading I performed and not a reading I assumed. The four CANNOT_JUDGE layers are named rather than guessed at.

#### Carry F-55

**Claim.** What this run still cannot answer, marked unanswerable rather than answered thinly. (1) The mission's stream-position gradient across October 1, 3, 4 and 5 is cross-day and this run holds one day. (2) Whether the completion behaviour I measure in 4.10 is a property of the instrument or of the Sunday reopen: 43366 of 43569 groups are PRE_SETTLEMENT on one instrument in one continuity segment. (3) Whether the candidate population is representative: my detector searched 6582 of 17991 seconds after warm-up and promoted 91. (4) Any claim about the 54/55-week frozen D-family geometry: no such field is carried on the delivered rows, so the frozen vocabulary could be used as a seed for naming but never tested. (5) Whether the brain's 90 plays hold: every one of the eight that touches native MBO mechanics keys on forecaster-harness quantities (tape_conditions.*, phase flow) that this stream does not carry, so none was testable and none is reported as verified or refuted. (6) Anything about a decision clock distinct from F_LAST: the delivered rows carry decision_ts_recv_ns equal to f_last_ts_recv_ns on all 43569 of them.

**Evidence.**
```json
{
  "brain_plays_indexed": 90,
  "brain_plays_testable_on_this_stream": 0,
  "decision_delay_census": {
    "0": 43569
  },
  "detector_counters": {
    "candidates_emitted": 91,
    "candidates_pending_in_window": 0,
    "rejected_below_threshold": 1672,
    "rejected_in_refractory": 294,
    "rejected_in_refractory_at_release": 17,
    "rejected_not_local_max": 14,
    "rejected_zero_magnitude": 338,
    "seconds_in_warmup": 11399,
    "seconds_judged": 17981,
    "seconds_observed": 17991,
    "seconds_without_finite_flow": 2103,
    "suppressed_by_prominence": 2053
  },
  "groups": 43569,
  "instruments": 1,
  "phase_counts": {
    "PRE_OPEN": 203,
    "PRE_SETTLEMENT": 43366
  },
  "segments": 1,
  "source_days_in_mission": [
    "20211001",
    "20211003",
    "20211004",
    "20211005"
  ]
}
```

**Falsifier.** Each item becomes answerable when a second scored day is traversed under the same contract, or when the forecaster-harness channels the brain plays key on are delivered beside the MBO stream. None becomes answerable by re-reading this day.

**Confidence basis.** Every item is tied to a counter in this run that is structurally single-valued or structurally absent, so the limit is a property of the slice rather than of my reading of it.

#### Carry F-56

**Claim.** A fill never removes a resting order outright on this tape, and that single fact reshapes the exit census. Every one of the 2411 fill actions carries book_effect.removed = false, so under a lifecycle rule that exits an order when its fill removes it, the terminal status of all 19408 resolved lifecycles is CANCELLED and not one is FILLED. Filled orders leave by a subsequent cancel: 1815 lifecycles follow the exact path add-fill-cancel. Any statement of the form 'x% of orders end in a fill' is therefore unanswerable on this delivery, and the honest reading of a 100%-cancelled census is that the venue expresses full consumption as fill-then-cancel rather than that nothing was consumed.

**Evidence.**
```json
{
  "add_cancel_paths": 16242,
  "add_fill_cancel_paths": 1815,
  "fill_actions": 2411,
  "fills_with_book_effect_removed_true": 0,
  "resolved_lifecycles": 19408,
  "still_resting_at_stream_end": 597,
  "terminal_status_census": {
    "CANCELLED": 19408
  }
}
```

**Falsifier.** A single fill row with book_effect.removed true, or a resolved lifecycle whose last action is a fill, falsifies this.

**Confidence basis.** The count is exhaustive over every fill action in every delivered group, and it is corroborated independently by my own lifecycle census, which was built by a different rule (exit on the removing fill) and produced zero FILLED terminals as a consequence.

#### Carry F-57

**Claim.** A modify on this instrument is a priority-losing reprice, not a size trim, and that is why my replenishment layer treats it as a removal and a re-add. Of the 4913 modifies I tracked against a live order, 4625 changed price and only 288 changed size at the same price; 4640 carried book_effect.priority_lost. Modifies therefore generate 4625 of my 26668 removal episodes and 4514 of my refills - a fifth of the liquidity churn on this book is one population of orders walking their own price, not new participants arriving and leaving.

**Evidence.**
```json
{
  "modify_priority_lost": 4640,
  "modify_reprice": 4625,
  "modify_size_only": 288,
  "price_relations": {
    "NEIGHBOUR_1_TICK": 10079,
    "SAME_PRICE": 15895
  },
  "refill_kinds": {
    "NEW_ID_ADD": 21419,
    "RESHAPED_RESIDUAL_REPRICE": 4514,
    "RESHAPED_RESIDUAL_SIZE_UP": 41
  },
  "removal_kinds": {
    "C": 19444,
    "F": 2411,
    "M_REPRICE_AWAY": 4625,
    "M_SIZE_DOWN": 188
  }
}
```

**Falsifier.** A day on which same-price size changes outnumber reprices would falsify this, and it would also change what my 4.7 episodes count, which is why the removal kind travels on every episode.

**Confidence basis.** The reprice/size split is decided per row from the book_effect the row carries (old price versus new price, old size versus new size), not inferred from the action letter, and the priority-loss flag agrees with it on 4,640 of 4,913 tracked modifies.

#### Carry F-58

**Claim.** Exhaustion chains on the candidate unit run to D9 on a single Sunday. Treating a candidate born while an earlier candidate's runway is still open as that runway's qualifying successor, the depth distribution over 91 candidates is {'0': 36, '1': 22, '2': 13, '3': 6, '4': 4, '5': 4, '6': 3, '7': 1, '8': 1, '9': 1}, with 33 runways extended by a same-polarity successor and 22 completed by an opposite one. The mission's D0-D5 anchors are exercised past their top rung here, which is only visible because no maximum depth is imposed and because the successor rule is defined on the exhaustion candidate rather than on order-id succession.

**Evidence.**
```json
{
  "candidates": 91,
  "depth_distribution": {
    "0": 36,
    "1": 22,
    "2": 13,
    "3": 6,
    "4": 4,
    "5": 4,
    "6": 3,
    "7": 1,
    "8": 1,
    "9": 1
  },
  "orientation_counts": {
    "FLIP": 46,
    "NO_PREDECESSOR": 1,
    "SAME": 44
  },
  "status_counts": {
    "CENSORED_STREAM_END": 1,
    "COMPLETED_BY_OPPOSITE_CANDIDATE": 22,
    "COMPLETED_DECAY": 35,
    "EXTENDED_BY_SUCCESSOR": 33
  },
  "transition_note": "SAME extends, FLIP completes; both are recorded per node with the parent id"
}
```

**Falsifier.** A successor assignment that crosses a continuity boundary would be unlawful; there is one segment here, so none can. The claim is falsified if the depth distribution collapses to D0/D1 once the runway completion rule is tightened - which is exactly why the rule travels on every 4.10 and 4.13 entry.

**Confidence basis.** Depth is an exact integer per node with a named parent, and the chain is built forward only: a parent is known open at the moment its child is born, so no depth uses information from later than the child's own availability second.

#### Carry F-59

**Claim.** Restricted to groups where a trade actually happened, delivered pressure is the MAJORITY disposition, not the rarity a whole-day runway census makes it look. Of the 1571 groups carrying a fill, 993 moved the mid in the aggressor's direction against 261 accompanied by same-side withdrawal and 160 absorbed without a price move. The other 41998 groups of the day carry no trade at all and contribute no absorption evidence; scoring them as runways is what turns a 4:1 delivery-to-withdrawal reading into its inverse. The contact-runway scope agrees: 886 delivered against 453 withdrawal over 1414 runways.

**Evidence.**
```json
{
  "contact_census": {
    "ABSORBED_WITHOUT_PRICE_MOVE": 75,
    "ACCOMPANIED_BY_WITHDRAWAL": 453,
    "DELIVERED_THROUGH_PRICE": 886
  },
  "contact_runways": 1414,
  "group_census": {
    "ABSORBED_WITHOUT_PRICE_MOVE": 160,
    "ACCOMPANIED_BY_WITHDRAWAL": 261,
    "DELIVERED_THROUGH_PRICE": 993,
    "INDETERMINATE": 157,
    "INDETERMINATE_NO_CONTACT": 41998
  },
  "price_response_ticks": {
    "max": 27.5,
    "mean": 0.070014144,
    "min": -25.5,
    "n": 1414,
    "p10": -2.5,
    "p25": -1.0,
    "p50": 0.0,
    "p75": 1.0,
    "p90": 2.5,
    "p99": 9.0,
    "sum": 99.0
  }
}
```

**Falsifier.** If delivery were an artifact of my mid-change rule, the contact-runway census computed over a longer window would not agree with the group-scoped one. It does. A day where the two disagree in direction would falsify the reading.

**Confidence basis.** Both censuses are complete partitions of their own populations and both distinguish the no-contact population explicitly rather than folding it into a disposition, which is the difference that produces the inversion.

#### Carry F-60

**Claim.** I traversed the raw source myself and my independently reconstructed order book agrees with the delivered one on every aggregate at every group. Decoding data/sunday_source/glbx-mdp3-20211003.mbo.dbn.zst gives 57027 MBO records which I grouped on the venue's own last-message flag into 43569 F_LAST-closed groups - the same counts the delivered ledger carries - and replaying every message into full depth with per-level FIFO queues reproduces the delivered book_full's best price, full depth, order count and price-level count on BOTH sides at all 43569 groups, with zero disagreements on any of those eight comparisons. The grouping, the book and the queue are the only three things a traversal adds to the flat message stream, and two independent implementations now agree on the first two completely.

**Evidence.**
```json
{
  "action_census": {
    "A": 20249,
    "C": 19444,
    "F": 2411,
    "M": 4939,
    "N": 7955,
    "R": 1,
    "T": 2028
  },
  "agreements": {
    "best_A_agree": 43569,
    "best_B_agree": 43569,
    "depth_A_agree": 43569,
    "depth_B_agree": 43569,
    "levels_A_agree": 43569,
    "levels_B_agree": 43569,
    "orders_A_agree": 43569,
    "orders_B_agree": 43569,
    "touch_fifo_A_agree": 43493,
    "touch_fifo_B_agree": 43527
  },
  "clears": 1,
  "disagreements": {
    "touch_fifo_A_differ": 76,
    "touch_fifo_B_differ": 42
  },
  "missing_reference_in_my_replay": {
    "C": 2116,
    "F": 17,
    "M": 107
  },
  "rule": "my book: A adds to the back of its level's FIFO, C removes (partial C reduces), M keeps place only when price is unchanged and size does not increase (else it re-joins the back), F consumes from the named order, R clears; comparison is against the delivered book_full AFTER the same group's messages",
  "snapshot_adds": 244,
  "source_groups": 43569,
  "source_records": 57027
}
```

**Falsifier.** A single group where my best price, depth, order count or level count differs from the delivered book_full falsifies the reconstruction; the counters are published for all eight comparisons on all 43,569 groups whether or not they are clean.

**Confidence basis.** This is the check a single reconstruction cannot supply: a wrong book is silent, it produces a plausible book that is wrong. My replay reads only the raw DBN and the delivered book is compared afterwards, group by group, so agreement cannot be an artifact of my having read the answer first.

#### Carry F-61

**Claim.** The one place my reconstruction differs is the FIFO order after a partial fill, and it is my rule that is wrong. On 118 of 87138 touch-queue comparisons (0.135%) my queue holds the same orders in a different order, and every disagreement I captured originates at a TFM group: a trade partially fills a resting order and the venue then sends a MODIFY restating the residual size. My rule treated that modify as priority-losing, because the restated size exceeds what my book held after the fill, and re-queued the order at the back; the delivered book keeps it in place, which is the correct exchange behaviour - a residual restatement is not a new order. The consequence is confined but real: any queue-position quantity I report for an order sitting at one of those touches inherits the wrong order, which is a caveat on my 4.6 volume-ahead and queue-movement numbers at those specific levels and nowhere else.

**Evidence.**
```json
{
  "comparisons": 87138,
  "correct_rule_implied": "a modify that restates a post-fill residual keeps its place even though the stated size exceeds the post-fill remainder",
  "examples": [
    {
      "action_string": "TFM",
      "delivered": [
        786260781845,
        786260781965
      ],
      "field": "touch_fifo",
      "group_index": 2176,
      "mine": [
        786260781965,
        786260781845
      ],
      "side": "A"
    },
    {
      "action_string": "C",
      "delivered": [
        786260781845,
        786260781965
      ],
      "field": "touch_fifo",
      "group_index": 2177,
      "mine": [
        786260781965,
        786260781845
      ],
      "side": "A"
    },
    {
      "action_string": "C",
      "delivered": [
        786260781845,
        786260781965
      ],
      "field": "touch_fifo",
      "group_index": 2178,
      "mine": [
        786260781965,
        786260781845
      ],
      "side": "A"
    },
    {
      "action_string": "TFM",
      "delivered": [
        786260803522,
        786260803617,
        786260803756
      ],
      "field": "touch_fifo",
      "group_index": 19066,
      "mine": [
        786260803617,
        786260803756,
        786260803522
      ],
      "side": "B"
    }
  ],
  "fifo_disagreements": 118,
  "my_rule_as_written": "a modify keeps its place only when price is unchanged and size does not increase",
  "origin_action_string_of_captured_examples": "TFM (trade, fill, same-order modify restating the residual)",
  "share": 0.001354
}
```

**Falsifier.** If the difference were noise rather than the residual-restatement rule, the disagreements would not all begin at a TFM group and would not persist unchanged through the following groups until the level is emptied. Both are observed.

**Confidence basis.** The defect is mine and was found only by comparing two reconstructions of the same bytes; I report it against my own numbers rather than presenting the aggregate agreement alone. It is bounded by an exact count on an exact denominator.

#### Carry F-62

**Claim.** The lifecycle shape the mission names as worth recognising - AN -> TFMN -> TFCN, order birth, partial fill with resizing, then residual completion - IS observable on this day, at both grains, and the served memory records it as absent. Reading the literal action string of every delivered group, 12 groups are TFMN (trade, fill, same-order modify, neutral close); two of their families are ow-174847199f25c91ccb41 with side string BAAN and ow-d15b9631ff373f53b149 with side string NNAN. At the order grain the same shape appears as a same-order path: 17 orders follow add-fill-modify-cancel exactly, 41 follow add-fill-modify-fill-cancel and 93 add-modify-fill-cancel. The prior reading came from a family crosswalk that lists only the largest families, so a shape occurring twelve times in 43,569 groups fell below its listing threshold and was reported as a structural absence.

**Evidence.**
```json
{
  "TFCN_groups": 842,
  "TFMN_groups": 12,
  "TFM_groups": 165,
  "exemplar_groups": [
    {
      "actions": [
        [
          "T",
          "B",
          786260779687
        ],
        [
          "F",
          "A",
          786260779685
        ],
        [
          "M",
          "A",
          786260779685
        ],
        [
          "N",
          "N",
          0
        ]
      ],
      "family_id": "ow-174847199f25c91ccb41",
      "group_index": 605,
      "side_string": "BAAN"
    },
    {
      "actions": [
        [
          "T",
          "N",
          0
        ],
        [
          "F",
          "N",
          786260785693
        ],
        [
          "M",
          "A",
          786260785693
        ],
        [
          "N",
          "N",
          0
        ]
      ],
      "family_id": "ow-d15b9631ff373f53b149",
      "group_index": 4499,
      "side_string": "NNAN"
    },
    {
      "actions": [
        [
          "T",
          "B",
          786260786217
        ],
        [
          "F",
          "A",
          786260786208
        ],
        [
          "M",
          "A",
          786260786208
        ],
        [
          "N",
          "N",
          0
        ]
      ],
      "family_id": "ow-174847199f25c91ccb41",
      "group_index": 4945,
      "side_string": "BAAN"
    }
  ],
  "same_order_paths": {
    "AFC": 1815,
    "AFMC": 17,
    "AFMFC": 41,
    "AMC": 664,
    "AMFC": 93
  },
  "why_the_prior_reading_missed_it": "a crosswalk over the largest families cannot see a family with 12 members; the literal action string can"
}
```

**Falsifier.** A group whose action string is TFMN but whose modify names a different order id than the fill would not be this shape; the exemplars are given with their order ids so the same-order condition can be checked directly.

**Confidence basis.** The count is over the literal action string of every one of the 43,569 delivered groups, and it is corroborated at a different grain by my own same-order lifecycle paths, which are built from order ids across groups rather than from action strings within one.

## Findings by section

| section | findings |
|---|---:|
| 4.0 / 4.0b | 1 |
| 4.1 / 4.9 / raw traversal | 1 |
| 4.10 / 4.13 | 1 |
| 4.11 | 1 |
| 4.13 | 1 |
| 4.16 / run cadence | 1 |
| 4.3 / 4.6 | 1 |
| 4.4 / 4.13 availability | 1 |
| 4.6 | 1 |
| 4.6 / 4.7 | 1 |
| 4.6 / raw traversal | 1 |
| 4.7 | 1 |
| 4.8 | 2 |
| 4.9 | 1 |
| 9a | 2 |
| scope | 1 |

A section heading here is whatever the finding named, including a multi-section
label such as `4.3 / 4.14`. Nothing is re-filed into a tidier key, because a
finding that spans sections is evidence about the join between them.

## 4.0 / 4.0b

#### F-45
*exact_and_averaged_views_with_reconciliation_labels*

**Claim.** My own computation of the per-second aggressor substrate reproduces the runner's delivered substrate row-for-row, and my own causal detector reproduces its candidate population exactly. Over 17991 completed seconds compared as they became lawful, 17991 agree on buy volume, sell volume, own-second class, trailing-window direction and roll20 and 0 disagree. Running the same declared rules myself over the raw legacy rows, my detector promoted 91 candidates and 91 of them fall on the same event second as a delivered candidate row. This is the load-bearing check on the traversal: two independent implementations of the same contract text, one on the box and one here, over the same bytes.

**Evidence.**
```json
{
  "agree": 17991,
  "delivered_candidate_rows_seen": 91,
  "detector_counters": {
    "candidates_emitted": 91,
    "candidates_pending_in_window": 0,
    "rejected_below_threshold": 1672,
    "rejected_in_refractory": 294,
    "rejected_in_refractory_at_release": 17,
    "rejected_not_local_max": 14,
    "rejected_zero_magnitude": 338,
    "seconds_in_warmup": 11399,
    "seconds_judged": 17981,
    "seconds_observed": 17991,
    "seconds_without_finite_flow": 2103,
    "suppressed_by_prominence": 2053
  },
  "disagree": 0,
  "legacy_rows_consumed": 22380,
  "matched_on_event_second": 91,
  "my_own_bookkeeping_defect": "the reconcile block's `delivered` (182) and `delivered_only` fields double-count: matched rows were never removed from the delivered map, so `delivered` is 91 delivered rows plus 91 matches and `delivered_only` lists event seconds that were in fact matched. The load-bearing counters - own 91, matched 91, own_only empty - are unaffected, and I report the defect rather than the tidy number.",
  "own_candidates": 91,
  "own_class_census": {
    "BUY": 370,
    "EXCLUDED_AT_MID": 2,
    "NO_DIRECTION": 17246,
    "SELL": 373
  },
  "own_window_census": {
    "LONG": 2489,
    "NO_DIRECTION": 13267,
    "SHORT": 2235
  },
  "seconds_compared": 17991
}
```

**Falsifier.** A single second where the two disagree on classified volume or class, or a promoted candidate on an event second the delivered rows do not carry, falsifies the reconciliation; the counters are reported whether they are zero or not.

**Confidence basis.** Both sides were computed from the same legacy observable rows by the same declared midpoint rule, but by different code on different machines, and the comparison was made second by second as each second completed rather than on a whole-day total, so an offsetting pair of errors cannot cancel.

## 4.1 / 4.9 / raw traversal

#### F-60
*exact_evidence_and_clock_references*

**Claim.** I traversed the raw source myself and my independently reconstructed order book agrees with the delivered one on every aggregate at every group. Decoding data/sunday_source/glbx-mdp3-20211003.mbo.dbn.zst gives 57027 MBO records which I grouped on the venue's own last-message flag into 43569 F_LAST-closed groups - the same counts the delivered ledger carries - and replaying every message into full depth with per-level FIFO queues reproduces the delivered book_full's best price, full depth, order count and price-level count on BOTH sides at all 43569 groups, with zero disagreements on any of those eight comparisons. The grouping, the book and the queue are the only three things a traversal adds to the flat message stream, and two independent implementations now agree on the first two completely.

**Evidence.**
```json
{
  "action_census": {
    "A": 20249,
    "C": 19444,
    "F": 2411,
    "M": 4939,
    "N": 7955,
    "R": 1,
    "T": 2028
  },
  "agreements": {
    "best_A_agree": 43569,
    "best_B_agree": 43569,
    "depth_A_agree": 43569,
    "depth_B_agree": 43569,
    "levels_A_agree": 43569,
    "levels_B_agree": 43569,
    "orders_A_agree": 43569,
    "orders_B_agree": 43569,
    "touch_fifo_A_agree": 43493,
    "touch_fifo_B_agree": 43527
  },
  "clears": 1,
  "disagreements": {
    "touch_fifo_A_differ": 76,
    "touch_fifo_B_differ": 42
  },
  "missing_reference_in_my_replay": {
    "C": 2116,
    "F": 17,
    "M": 107
  },
  "rule": "my book: A adds to the back of its level's FIFO, C removes (partial C reduces), M keeps place only when price is unchanged and size does not increase (else it re-joins the back), F consumes from the named order, R clears; comparison is against the delivered book_full AFTER the same group's messages",
  "snapshot_adds": 244,
  "source_groups": 43569,
  "source_records": 57027
}
```

**Falsifier.** A single group where my best price, depth, order count or level count differs from the delivered book_full falsifies the reconstruction; the counters are published for all eight comparisons on all 43,569 groups whether or not they are clean.

**Confidence basis.** This is the check a single reconstruction cannot supply: a wrong book is silent, it produces a plausible book that is wrong. My replay reads only the raw DBN and the delivered book is compared afterwards, group by group, so agreement cannot be an artifact of my having read the answer first.

## 4.10 / 4.13

#### F-49
*duration_recurrence_extension_chain_and_completion_behavior*

**Claim.** Exhaustion runways DO complete on this slice once a completion rule is actually fed. Giving each promoted candidate a runway that advances one completed second at a time - PERSISTENCE while the trailing window flow keeps the birth polarity, REVERSAL while it opposes it, QUIET_NO_DIRECTION at zero, completion when a reversal is followed by LOCAL_RADIUS consecutive seconds carrying no classified volume, extension when a later same-polarity candidate is born inside an open runway and completion-by-opposition when an opposite one is - the 91 candidates resolve as {'CENSORED_STREAM_END': 1, 'COMPLETED_BY_OPPOSITE_CANDIDATE': 22, 'COMPLETED_DECAY': 35, 'EXTENDED_BY_SUCCESSOR': 33}, with phase census {'BIRTH': 91, 'REVERSAL': 118, 'PERSISTENCE': 105, 'QUIET_NO_DIRECTION': 156}. Chain depth on this candidate lineage is {'0': 36, '1': 22, '2': 13, '3': 6, '4': 4, '5': 4, '6': 3, '7': 1, '8': 1, '9': 1}. The earlier reading that no runway ever completes was a property of a runway with no completion rule attached, not of the market.

**Evidence.**
```json
{
  "candidates": 91,
  "chain_depths": {
    "0": 36,
    "1": 22,
    "2": 13,
    "3": 6,
    "4": 4,
    "5": 4,
    "6": 3,
    "7": 1,
    "8": 1,
    "9": 1
  },
  "completed_or_extended": {
    "COMPLETED_BY_OPPOSITE_CANDIDATE": 22,
    "COMPLETED_DECAY": 35,
    "EXTENDED_BY_SUCCESSOR": 33
  },
  "orientation_counts": {
    "FLIP": 46,
    "NO_PREDECESSOR": 1,
    "SAME": 44
  },
  "phase_census": {
    "BIRTH": 91,
    "PERSISTENCE": 105,
    "QUIET_NO_DIRECTION": 156,
    "REVERSAL": 118
  },
  "phase_depletion_refill": null,
  "status_counts": {
    "CENSORED_STREAM_END": 1,
    "COMPLETED_BY_OPPOSITE_CANDIDATE": 22,
    "COMPLETED_DECAY": 35,
    "EXTENDED_BY_SUCCESSOR": 33
  }
}
```

**Falsifier.** The completion rule is mine and is stated in the 4.10 ledger; a different rule gives a different census, which is why the rule travels on every entry. It is falsified by a candidate marked COMPLETED_DECAY whose polarity side keeps trading after the quiet run, or by a successor assignment that spans a continuity boundary (there is only one segment here, so none can).

**Confidence basis.** Each transition is decided from completed-second quantities that were lawful at the second they were read; no completed duration is used at an earlier cutoff, and every runway still open at the stream end is CENSORED rather than counted as complete.

## 4.11

#### F-50
*prebirth_and_early_recognition_timing*

**Claim.** A lawful pre-birth signal exists on this unit and it is weak, and both halves of that sentence are measurements. The earliest lawful precursor I can build from the same substrate is the threshold-crossing alert: the first second of the contiguous run in which |roll20| is at or above the trailing causal bar that ends at the candidate's event second, knowable one second later. It labels 35 of 91 candidates PRIOR, the rest {'H+N': 55, 'T0': 1}. But the same rule fired 160 alerts across the day, so its precision as a standalone trigger is 0.5687 - most crossings are followed by no promotion at all. A pre-birth lead measured only over the candidates that were later promoted is a survivor statistic; the denominator that matters is every alert.

**Evidence.**
```json
{
  "alert_precision": 0.5687,
  "alerts_total": 160,
  "candidates": 91,
  "detector_counters": {
    "candidates_emitted": 91,
    "candidates_pending_in_window": 0,
    "rejected_below_threshold": 1672,
    "rejected_in_refractory": 294,
    "rejected_in_refractory_at_release": 17,
    "rejected_not_local_max": 14,
    "rejected_zero_magnitude": 338,
    "seconds_in_warmup": 11399,
    "seconds_judged": 17981,
    "seconds_observed": 17991,
    "seconds_without_finite_flow": 2103,
    "suppressed_by_prominence": 2053
  },
  "precursor_labels": {
    "H+N": 55,
    "PRIOR": 35,
    "T0": 1
  },
  "promotion_lag_seconds": null
}
```

**Falsifier.** A stratum in which alert precision rises materially above the base rate would make the alert a usable pre-birth trigger; a day on which the alert never precedes a promotion at all would remove the PRIOR class entirely.

**Confidence basis.** The alert population and the promotion population are counted over the same seconds by the same bar, and the precision is a ratio of two exact counts with its denominator stated; nothing here is averaged over successful detections alone.

## 4.13

#### F-58
*duration_recurrence_extension_chain_and_completion_behavior*

**Claim.** Exhaustion chains on the candidate unit run to D9 on a single Sunday. Treating a candidate born while an earlier candidate's runway is still open as that runway's qualifying successor, the depth distribution over 91 candidates is {'0': 36, '1': 22, '2': 13, '3': 6, '4': 4, '5': 4, '6': 3, '7': 1, '8': 1, '9': 1}, with 33 runways extended by a same-polarity successor and 22 completed by an opposite one. The mission's D0-D5 anchors are exercised past their top rung here, which is only visible because no maximum depth is imposed and because the successor rule is defined on the exhaustion candidate rather than on order-id succession.

**Evidence.**
```json
{
  "candidates": 91,
  "depth_distribution": {
    "0": 36,
    "1": 22,
    "2": 13,
    "3": 6,
    "4": 4,
    "5": 4,
    "6": 3,
    "7": 1,
    "8": 1,
    "9": 1
  },
  "orientation_counts": {
    "FLIP": 46,
    "NO_PREDECESSOR": 1,
    "SAME": 44
  },
  "status_counts": {
    "CENSORED_STREAM_END": 1,
    "COMPLETED_BY_OPPOSITE_CANDIDATE": 22,
    "COMPLETED_DECAY": 35,
    "EXTENDED_BY_SUCCESSOR": 33
  },
  "transition_note": "SAME extends, FLIP completes; both are recorded per node with the parent id"
}
```

**Falsifier.** A successor assignment that crosses a continuity boundary would be unlawful; there is one segment here, so none can. The claim is falsified if the depth distribution collapses to D0/D1 once the runway completion rule is tightened - which is exactly why the rule travels on every 4.10 and 4.13 entry.

**Confidence basis.** Depth is an exact integer per node with a named parent, and the chain is built forward only: a parent is known open at the moment its child is born, so no depth uses information from later than the child's own availability second.

## 4.16 / run cadence

#### F-51
*exact_evidence_and_clock_references*

**Claim.** The nineteen lawful decision points of this run were placed by a group count, not by anything the market did, and I measured what that costs. Every staged cutoff is an exact multiple of 2,281 groups, which is int(57,027 records x 0.8 groups-per-record / 20 target spawns) as the launch workflow computes it, and the launcher installs a pure count cadence (native_a_arm_launch._GroupCadence) while an event-driven cadence that triggers on a recognition or a 4.16 change point (native_replay_driver.CandidateEventCadence) exists in the driver and is not used on this path. Against my own events: 91 promotions waited a median of 381.945525951 s (p90 1040.440119355 s, max 1382.440119355 s) for the next staged cutoff at which I could speak about them, and 3 fell beyond the last staged cutoff entirely; 356 change points and 6079 touch migrations waited a median of 356.523516424 s and 47.272155612 s. 10 of the 19 staged cutoffs carried no new promotion at all, while an event-driven cadence on promotions alone would have placed 91 decision points, each one on the second the thing became knowable.

**Evidence.**
```json
{
  "cadence_arithmetic": "57,027 records x 0.8 / 20 = 2,281 groups; every staged cutoff is a multiple of 2,281",
  "event_driven_points_on_promotions": 91,
  "events": {
    "CHANGE_POINT": {
      "beyond_last_staged_cutoff": 7,
      "cutoffs_that_would_have_carried_one": 9,
      "events": 356,
      "wait_to_next_staged_cutoff_seconds": {
        "max": 1301.440119355,
        "mean": 431.692757,
        "min": 1.440119355,
        "n": 349,
        "p10": 56.945525951,
        "p50": 356.523516424,
        "p90": 978.440119355
      }
    },
    "PROMOTION": {
      "beyond_last_staged_cutoff": 3,
      "cutoffs_that_would_have_carried_one": 9,
      "events": 91,
      "wait_to_next_staged_cutoff_seconds": {
        "max": 1382.440119355,
        "mean": 470.348577,
        "min": 23.744781866,
        "n": 88,
        "p10": 85.969569876,
        "p50": 381.945525951,
        "p90": 1040.440119355
      }
    },
    "TOUCH_MIGRATION": {
      "beyond_last_staged_cutoff": 18,
      "cutoffs_that_would_have_carried_one": 19,
      "events": 6079,
      "wait_to_next_staged_cutoff_seconds": {
        "max": 1368.843351714,
        "mean": 201.017371,
        "min": 0.0,
        "n": 6061,
        "p10": 3.126303077,
        "p50": 47.272155612,
        "p90": 642.922389642
      }
    }
  },
  "staged_cutoffs": 19,
  "staged_cutoffs_with_no_new_promotion": 10,
  "staged_group_indices": [
    2281,
    4562,
    6843,
    9124,
    11405,
    13686,
    15967,
    18248,
    20529,
    22810,
    25091,
    27372,
    29653,
    31934,
    34215,
    36496,
    38777,
    41058,
    43339
  ]
}
```

**Falsifier.** If the count cadence were incidental rather than structural, the staged group indices would not all be exact multiples of one number. They are; the falsifier is a run whose cutoffs are not.

**Confidence basis.** The line of inquiry was pointed out to me by the coordinator and I verified it independently: I read the cutoff list from cutoffs.json and checked the divisibility myself, read the cadence arithmetic in the launch workflow and the two cadence classes in the repository, and every wait figure is measured from my own events against those cutoffs. Nothing here is taken on the coordinator's word.

## 4.3 / 4.6

#### F-62
*distinct_candidate_families_and_complete_causal_runways*

**Claim.** The lifecycle shape the mission names as worth recognising - AN -> TFMN -> TFCN, order birth, partial fill with resizing, then residual completion - IS observable on this day, at both grains, and the served memory records it as absent. Reading the literal action string of every delivered group, 12 groups are TFMN (trade, fill, same-order modify, neutral close); two of their families are ow-174847199f25c91ccb41 with side string BAAN and ow-d15b9631ff373f53b149 with side string NNAN. At the order grain the same shape appears as a same-order path: 17 orders follow add-fill-modify-cancel exactly, 41 follow add-fill-modify-fill-cancel and 93 add-modify-fill-cancel. The prior reading came from a family crosswalk that lists only the largest families, so a shape occurring twelve times in 43,569 groups fell below its listing threshold and was reported as a structural absence.

**Evidence.**
```json
{
  "TFCN_groups": 842,
  "TFMN_groups": 12,
  "TFM_groups": 165,
  "exemplar_groups": [
    {
      "actions": [
        [
          "T",
          "B",
          786260779687
        ],
        [
          "F",
          "A",
          786260779685
        ],
        [
          "M",
          "A",
          786260779685
        ],
        [
          "N",
          "N",
          0
        ]
      ],
      "family_id": "ow-174847199f25c91ccb41",
      "group_index": 605,
      "side_string": "BAAN"
    },
    {
      "actions": [
        [
          "T",
          "N",
          0
        ],
        [
          "F",
          "N",
          786260785693
        ],
        [
          "M",
          "A",
          786260785693
        ],
        [
          "N",
          "N",
          0
        ]
      ],
      "family_id": "ow-d15b9631ff373f53b149",
      "group_index": 4499,
      "side_string": "NNAN"
    },
    {
      "actions": [
        [
          "T",
          "B",
          786260786217
        ],
        [
          "F",
          "A",
          786260786208
        ],
        [
          "M",
          "A",
          786260786208
        ],
        [
          "N",
          "N",
          0
        ]
      ],
      "family_id": "ow-174847199f25c91ccb41",
      "group_index": 4945,
      "side_string": "BAAN"
    }
  ],
  "same_order_paths": {
    "AFC": 1815,
    "AFMC": 17,
    "AFMFC": 41,
    "AMC": 664,
    "AMFC": 93
  },
  "why_the_prior_reading_missed_it": "a crosswalk over the largest families cannot see a family with 12 members; the literal action string can"
}
```

**Falsifier.** A group whose action string is TFMN but whose modify names a different order id than the fill would not be this shape; the exemplars are given with their order ids so the same-order condition can be checked directly.

**Confidence basis.** The count is over the literal action string of every one of the 43,569 delivered groups, and it is corroborated at a different grain by my own same-order lifecycle paths, which are built from order ids across groups rather than from action strings within one.

## 4.4 / 4.13 availability

#### F-52
*exact_and_averaged_views_with_reconciliation_labels*

**Claim.** Two of the runner's own per-section row families do not exist at any decision point of this run: they are emitted only at the stream end. Across the whole traversal 21651 delivered lineage rows rode inside a group (19 of the cutoffs saw none), and the mirror rows that did arrive carried only the PENDING disposition, with the matched dispositions arriving at the close. The rows drained after exhaustion are {}. For a real-time reader that means sections 4.13 and 4.4 exist only in the post-mortem as delivered. This is an emission-cadence fact about the runner, not a limit of the evidence: my own 4.4 pairing (a partner is the most recent earlier member with the swapped side string) and my own 4.13 chain lineage (a candidate born inside an open runway is its successor) were both computable and written at every one of the twenty cutoffs, so the information needed to emit them during the stream is present in the stream.

**Evidence.**
```json
{
  "cutoffs_with_only_pending_mirror": 19,
  "cutoffs_with_zero_delivered_lineage": 19,
  "delivered_lifecycle_counts_in_stream": {
    "absorption": 43569,
    "candidate": 91,
    "detector_coverage": 1,
    "episode": 182,
    "exhaustion": 1,
    "flow_substrate": 17992,
    "ladder": 87138,
    "lineage": 21651,
    "mirror": 87138,
    "queue": 20005,
    "recurrence": 43569,
    "replenishment": 73480,
    "response": 630
  },
  "drained_at_stream_end_by_section": {},
  "own_pairs_and_nodes_at_each_cutoff": [
    {
      "cutoff_recv_ns": 1633298413318097271,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 2282
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 2235
    },
    {
      "cutoff_recv_ns": 1633298449136124134,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 4563
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 4490
    },
    {
      "cutoff_recv_ns": 1633298458819212131,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 6844
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 6751
    },
    {
      "cutoff_recv_ns": 1633298467489465095,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 9125
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 9003
    },
    {
      "cutoff_recv_ns": 1633298495252279199,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 11406
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 11272
    },
    {
      "cutoff_recv_ns": 1633298539321423187,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 13687
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 13533
    },
    {
      "cutoff_recv_ns": 1633298618241396322,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 15968
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 15805
    },
    {
      "cutoff_recv_ns": 1633298727046687558,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 18249
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 18075
    },
    {
      "cutoff_recv_ns": 1633298843554132312,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 20530
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 20349
    },
    {
      "cutoff_recv_ns": 1633298998928924813,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 22811
      },
      "own_lineage_nodes": 0,
      "own_mirror_pairs": 22616
    },
    {
      "cutoff_recv_ns": 1633299505523516424,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 25092
      },
      "own_lineage_nodes": 6,
      "own_mirror_pairs": 24884
    },
    {
      "cutoff_recv_ns": 1633299950655145332,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 27373
      },
      "own_lineage_nodes": 13,
      "own_mirror_pairs": 27158
    },
    {
      "cutoff_recv_ns": 1633300320102307848,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 29654
      },
      "own_lineage_nodes": 19,
      "own_mirror_pairs": 29412
    },
    {
      "cutoff_recv_ns": 1633300905784605734,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 31935
      },
      "own_lineage_nodes": 28,
      "own_mirror_pairs": 31680
    },
    {
      "cutoff_recv_ns": 1633301315945525951,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 34218
      },
      "own_lineage_nodes": 34,
      "own_mirror_pairs": 33949
    },
    {
      "cutoff_recv_ns": 1633302013969569876,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 36497
      },
      "own_lineage_nodes": 45,
      "own_mirror_pairs": 36220
    },
    {
      "cutoff_recv_ns": 1633302779744781866,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 38778
      },
      "own_lineage_nodes": 54,
      "own_mirror_pairs": 38492
    },
    {
      "cutoff_recv_ns": 1633304073331796184,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 41059
      },
      "own_lineage_nodes": 70,
      "own_mirror_pairs": 40757
    },
    {
      "cutoff_recv_ns": 1633305465440119355,
      "delivered_lineage_rows_attached": 0,
      "delivered_mirror_rows_attached": {
        "PENDING": 43340
      },
      "own_lineage_nodes": 88,
      "own_mirror_pairs": 43033
    },
    {
      "cutoff_recv_ns": 1633305596372071705,
      "delivered_lineage_rows_attached": 21651,
      "delivered_mirror_rows_attached": {
        "PENDING": 43569,
        "UNMATCHED": 43569
      },
      "own_lineage_nodes": 91,
      "own_mirror_pairs": 43262
    }
  ],
  "withheld_summary": {
    "legacy": 0,
    "lifecycle": {}
  }
}
```

**Falsifier.** A lineage or matched-mirror row attached to a group before the stream end falsifies the emission claim. Separately, if my own in-stream 4.4/4.13 entries had needed any quantity that was not lawful at their cutoff, the ledger's cutoff ordering would have refused them.

**Confidence basis.** The line of inquiry was pointed out to me by the coordinator and I verified it independently: the counts come from my own stream, which tallies every attached lifecycle row by section as it rides inside a group and every withheld row by reason at the close, and from my own per-cutoff section ledgers. I did not re-use the coordinator's figures.

## 4.6

#### F-56
*novel_correlations_and_positive_hypotheses*

**Claim.** A fill never removes a resting order outright on this tape, and that single fact reshapes the exit census. Every one of the 2411 fill actions carries book_effect.removed = false, so under a lifecycle rule that exits an order when its fill removes it, the terminal status of all 19408 resolved lifecycles is CANCELLED and not one is FILLED. Filled orders leave by a subsequent cancel: 1815 lifecycles follow the exact path add-fill-cancel. Any statement of the form 'x% of orders end in a fill' is therefore unanswerable on this delivery, and the honest reading of a 100%-cancelled census is that the venue expresses full consumption as fill-then-cancel rather than that nothing was consumed.

**Evidence.**
```json
{
  "add_cancel_paths": 16242,
  "add_fill_cancel_paths": 1815,
  "fill_actions": 2411,
  "fills_with_book_effect_removed_true": 0,
  "resolved_lifecycles": 19408,
  "still_resting_at_stream_end": 597,
  "terminal_status_census": {
    "CANCELLED": 19408
  }
}
```

**Falsifier.** A single fill row with book_effect.removed true, or a resolved lifecycle whose last action is a fill, falsifies this.

**Confidence basis.** The count is exhaustive over every fill action in every delivered group, and it is corroborated independently by my own lifecycle census, which was built by a different rule (exit on the removing fill) and produced zero FILLED terminals as a consequence.

## 4.6 / 4.7

#### F-57
*duration_recurrence_extension_chain_and_completion_behavior*

**Claim.** A modify on this instrument is a priority-losing reprice, not a size trim, and that is why my replenishment layer treats it as a removal and a re-add. Of the 4913 modifies I tracked against a live order, 4625 changed price and only 288 changed size at the same price; 4640 carried book_effect.priority_lost. Modifies therefore generate 4625 of my 26668 removal episodes and 4514 of my refills - a fifth of the liquidity churn on this book is one population of orders walking their own price, not new participants arriving and leaving.

**Evidence.**
```json
{
  "modify_priority_lost": 4640,
  "modify_reprice": 4625,
  "modify_size_only": 288,
  "price_relations": {
    "NEIGHBOUR_1_TICK": 10079,
    "SAME_PRICE": 15895
  },
  "refill_kinds": {
    "NEW_ID_ADD": 21419,
    "RESHAPED_RESIDUAL_REPRICE": 4514,
    "RESHAPED_RESIDUAL_SIZE_UP": 41
  },
  "removal_kinds": {
    "C": 19444,
    "F": 2411,
    "M_REPRICE_AWAY": 4625,
    "M_SIZE_DOWN": 188
  }
}
```

**Falsifier.** A day on which same-price size changes outnumber reprices would falsify this, and it would also change what my 4.7 episodes count, which is why the removal kind travels on every episode.

**Confidence basis.** The reprice/size split is decided per row from the book_effect the row carries (old price versus new price, old size versus new size), not inferred from the action letter, and the priority-loss flag agrees with it on 4,640 of 4,913 tracked modifies.

## 4.6 / raw traversal

#### F-61
*exact_evidence_and_clock_references*

**Claim.** The one place my reconstruction differs is the FIFO order after a partial fill, and it is my rule that is wrong. On 118 of 87138 touch-queue comparisons (0.135%) my queue holds the same orders in a different order, and every disagreement I captured originates at a TFM group: a trade partially fills a resting order and the venue then sends a MODIFY restating the residual size. My rule treated that modify as priority-losing, because the restated size exceeds what my book held after the fill, and re-queued the order at the back; the delivered book keeps it in place, which is the correct exchange behaviour - a residual restatement is not a new order. The consequence is confined but real: any queue-position quantity I report for an order sitting at one of those touches inherits the wrong order, which is a caveat on my 4.6 volume-ahead and queue-movement numbers at those specific levels and nowhere else.

**Evidence.**
```json
{
  "comparisons": 87138,
  "correct_rule_implied": "a modify that restates a post-fill residual keeps its place even though the stated size exceeds the post-fill remainder",
  "examples": [
    {
      "action_string": "TFM",
      "delivered": [
        786260781845,
        786260781965
      ],
      "field": "touch_fifo",
      "group_index": 2176,
      "mine": [
        786260781965,
        786260781845
      ],
      "side": "A"
    },
    {
      "action_string": "C",
      "delivered": [
        786260781845,
        786260781965
      ],
      "field": "touch_fifo",
      "group_index": 2177,
      "mine": [
        786260781965,
        786260781845
      ],
      "side": "A"
    },
    {
      "action_string": "C",
      "delivered": [
        786260781845,
        786260781965
      ],
      "field": "touch_fifo",
      "group_index": 2178,
      "mine": [
        786260781965,
        786260781845
      ],
      "side": "A"
    },
    {
      "action_string": "TFM",
      "delivered": [
        786260803522,
        786260803617,
        786260803756
      ],
      "field": "touch_fifo",
      "group_index": 19066,
      "mine": [
        786260803617,
        786260803756,
        786260803522
      ],
      "side": "B"
    }
  ],
  "fifo_disagreements": 118,
  "my_rule_as_written": "a modify keeps its place only when price is unchanged and size does not increase",
  "origin_action_string_of_captured_examples": "TFM (trade, fill, same-order modify restating the residual)",
  "share": 0.001354
}
```

**Falsifier.** If the difference were noise rather than the residual-restatement rule, the disagreements would not all begin at a TFM group and would not persist unchanged through the following groups until the level is emptied. Both are observed.

**Confidence basis.** The defect is mine and was found only by comparing two reconstructions of the same bytes; I report it against my own numbers rather than presenting the aggregate agreement alone. It is bounded by an exact count on an exact denominator.

## 4.7

#### F-47
*duration_recurrence_extension_chain_and_completion_behavior*

**Claim.** Under a strict one-attribution episode rule - each removal of resting quantity opens an episode at (side, price) and is closed by the FIRST later arrival at that price or one tick either side, and the modify that moved an order can never restore its own episode - the touch is still restored faster than the level behind it, and the effect survives the change of rule. 26668 episodes opened, 25974 resolved and 694 were still pending at the stream end (censored, not never-restored). The within-family, within-side AT_TOUCH versus BEHIND_TOUCH median ratios are [379.3, 405.3, 1.4, 0.3, 2.2, 2.1]. Because each arrival is credited once, my replenishment ratios are net first-arrival ratios and are NOT the arrival-density figures a many-to-one attribution produces; the two answer different questions and must not be compared.

**Evidence.**
```json
{
  "episodes": 26668,
  "pending_censored": 694,
  "price_relations": {
    "NEIGHBOUR_1_TICK": 10079,
    "SAME_PRICE": 15895
  },
  "refill_kinds": {
    "NEW_ID_ADD": 21419,
    "RESHAPED_RESIDUAL_REPRICE": 4514,
    "RESHAPED_RESIDUAL_SIZE_UP": 41
  },
  "removal_kinds": {
    "C": 19444,
    "F": 2411,
    "M_REPRICE_AWAY": 4625,
    "M_SIZE_DOWN": 188
  },
  "resolved": 25974,
  "touch_displacements": 36,
  "touch_restoration_time_ns": {
    "max": 1850097476139,
    "mean": 56193412020.76471,
    "min": 69976,
    "n": 34,
    "p10": 236184,
    "p25": 423804,
    "p50": 1639709,
    "p75": 1416822240,
    "p90": 3091801621,
    "p99": 1850097476139,
    "sum": 1910576008706.0
  },
  "within_family_within_side_pairs": [
    {
      "at_touch_median_ns": 1774647,
      "at_touch_n": 556,
      "behind_touch_median_ns": 673102126,
      "behind_touch_n": 7636,
      "family_side": "ow-40540069fe5aeddc127b|B",
      "ratio": 379.3
    },
    {
      "at_touch_median_ns": 1378939,
      "at_touch_n": 400,
      "behind_touch_median_ns": 558842876,
      "behind_touch_n": 6501,
      "family_side": "ow-59ace24da4a485c605b6|A",
      "ratio": 405.3
    },
    {
      "at_touch_median_ns": 1347065,
      "at_touch_n": 815,
      "behind_touch_median_ns": 1890331,
      "behind_touch_n": 579,
      "family_side": "ow-7b10d38a8b61511bc611|A",
      "ratio": 1.4
    },
    {
      "at_touch_median_ns": 4990034,
      "at_touch_n": 591,
      "behind_touch_median_ns": 1607344,
      "behind_touch_n": 197,
      "family_side": "ow-8c934d067bc463c01ce0|B",
      "ratio": 0.3
    },
    {
      "at_touch_median_ns": 1243382,
      "at_touch_n": 256,
      "behind_touch_median_ns": 2700538,
      "behind_touch_n": 391,
      "family_side": "ow-1fe202ccc7ea51ea8050|A",
      "ratio": 2.2
    },
    {
      "at_touch_median_ns": 321908086,
      "at_touch_n": 77,
      "behind_touch_median_ns": 670845501,
      "behind_touch_n": 68,
      "family_side": "ow-2b87a13fb17c35fb43c5|B",
      "ratio": 2.1
    }
  ]
}
```

**Falsifier.** A family and side whose AT_TOUCH median exceeds its BEHIND_TOUCH median, or an episode population where the pending count is a large share of the opened count (which would make the medians a censoring artifact rather than a restoration time).

**Confidence basis.** The comparison changes exactly one key - touch state - inside one family and one side, so it cannot be a family, side, phase or day effect; pending episodes are carried in the survival estimator's at-risk set rather than dropped.

## 4.8

#### F-48
*distinct_candidate_families_and_complete_causal_runways*

**Claim.** Delivered pressure looks rare or common depending entirely on how long the runway is, and I measured both. On the group-scoped runway (the F_LAST group carrying the fill) the census is {'ABSORBED_WITHOUT_PRICE_MOVE': 160, 'ACCOMPANIED_BY_WITHDRAWAL': 261, 'DELIVERED_THROUGH_PRICE': 993, 'INDETERMINATE': 157, 'INDETERMINATE_NO_CONTACT': 41998}. On the CONTACT runway - from a fill-bearing group through every following group until the next contact - the same day gives {'ABSORBED_WITHOUT_PRICE_MOVE': 75, 'ACCOMPANIED_BY_WITHDRAWAL': 453, 'DELIVERED_THROUGH_PRICE': 886} over 1414 runways spanning a median of 17 groups and 535089478 ns. Widening the window from one group to the interval between contacts moves the classification, so a disposition census is a statement about the runway definition first and about the market second.

**Evidence.**
```json
{
  "contact_runway_census": {
    "ABSORBED_WITHOUT_PRICE_MOVE": 75,
    "ACCOMPANIED_BY_WITHDRAWAL": 453,
    "DELIVERED_THROUGH_PRICE": 886
  },
  "contact_runways": 1414,
  "duration_ns": {
    "max": 235056393027,
    "mean": 5089054652.084866,
    "min": 13486,
    "n": 1414,
    "p10": 347622,
    "p25": 1739465,
    "p50": 535089478,
    "p75": 3871861339,
    "p90": 13161492080,
    "p99": 60675287441,
    "sum": 7195923278048.0
  },
  "group_scoped_census": {
    "ABSORBED_WITHOUT_PRICE_MOVE": 160,
    "ACCOMPANIED_BY_WITHDRAWAL": 261,
    "DELIVERED_THROUGH_PRICE": 993,
    "INDETERMINATE": 157,
    "INDETERMINATE_NO_CONTACT": 41998
  },
  "price_response_ticks": {
    "max": 27.5,
    "mean": 0.070014144,
    "min": -25.5,
    "n": 1414,
    "p10": -2.5,
    "p25": -1.0,
    "p50": 0.0,
    "p75": 1.0,
    "p90": 2.5,
    "p99": 9.0,
    "sum": 99.0
  },
  "span_groups": {
    "max": 555,
    "mean": 30.666195191,
    "min": 1,
    "n": 1414,
    "p10": 2,
    "p25": 5,
    "p50": 17,
    "p75": 44,
    "p90": 76,
    "p99": 165,
    "sum": 43362.0
  },
  "top_strata": {
    "ow-0069e456ba86b8f3b52e|N|PRE_SETTLEMENT|INDETERMINATE": {
      "n": 50,
      "price_response_ticks": {
        "n": 0
      },
      "traded": {
        "max": 2,
        "mean": 1.02,
        "min": 1,
        "n": 50,
        "p10": 1,
        "p25": 1,
        "p50": 1,
        "p75": 1,
        "p90": 1,
        "p99": 2,
        "sum": 51.0
      },
      "withdrawn": {
        "max": 0,
        "mean": 0.0,
        "min": 0,
        "n": 50,
        "p10": 0,
        "p25": 0,
        "p50": 0,
        "p75": 0,
        "p90": 0,
        "p99": 0,
        "sum": 0.0
      }
    },
    "ow-174847199f25c91ccb41|A|PRE_SETTLEMENT|ABSORBED_WITHOUT_PRICE_MOVE": {
      "n": 7,
      "price_response_ticks": {
        "max": 0.0,
        "mean": 0.0,
        "min": 0.0,
        "n": 7,
        "p10": 0.0,
        "p25": 0.0,
        "p50": 0.0,
        "p75": 0.0,
        "p90": 0.0,
        "p99": 0.0,
        "sum": 0.0
      },
      "traded": {
        "max": 2,
        "mean": 1.142857143,
        "min": 1,
        "n": 7,
        "p10": 1,
        "p25": 1,
        "p50": 1,
        "p75": 1,
        "p90": 1,
        "p99": 2,
        "sum": 8.0
      },
      "withdrawn": {
        "max": 0,
        "mean": 0.0,
        "min": 0,
        "n": 7,
        "p10": 0,
        "p25": 0,
        "p50": 0,
        "p75": 0,
        "p90": 0,
        "p99": 0,
        "sum": 0.0
      }
    },
    "ow-1b64a25174ce60aae233|N|PRE_SETTLEMENT|INDETERMINATE": {
      "n": 5,
      "price_response_ticks": {
        "n": 0
      },
      "traded": {
        "max": 1,
        "mean": 1.0,
        "min": 1,
        "n": 5,
        "p10": 1,
        "p25": 1,
        "p50": 1,
        "p75": 1,
        "p90": 1,
        "p99": 1,
        "sum": 5.0
      },
      "withdrawn": {
        "max": 0,
        "mean": 0.0,
        "min": 0,
        "n": 5,
        "p10": 0,
        "p25": 0,
        "p50": 0,
        "p75": 0,
        "p90": 0,
        "p99": 0,
        "sum": 0.0
      }
    },
    "ow-1f6c5bd2663dbea89be3|B|PRE_SETTLEMENT|DELIVERED_THROUGH_PRICE": {
      "n": 16,
      "price_response_ticks": {
        "max": -0.5,
        "mean": -1.625,
        "min": -5.0,
        "n": 16,
        "p10": -3.0,
        "p25": -2.0,
        "p50": -1.0,
        "p75": -1.0,
        "p90": -0.5,
        "p99": -0.5,
        "sum": -26.0
      },
      "traded": {
        "max": 6,
        "mean": 2.4375,
        "min": 2,
        "n": 16,
        "p10": 2,
        "p25": 2,
        "p50": 2,
        "p75": 2,
        "p90": 4,
        "p99": 6,
        "sum": 39.0
      },
      "withdrawn": {
        "max": 6,
        "mean": 2.4375,
        "min": 2,
        "n": 16,
        "p10": 2,
        "p25": 2,
        "p50": 2,
        "p75": 2,
        "p90": 4,
        "p99": 6,
        "sum": 39.0
      }
    }
  }
}
```

**Falsifier.** If the disposition were a property of the market rather than of the window, the two censuses would have the same shape. A day where they do would falsify this.

**Confidence basis.** Both censuses are complete partitions of their own populations (every group is classified, every contact runway closes at the next contact or the stream end) and both were computed in the same pass from the same raw actions, so the difference is the scope and nothing else.

#### F-59
*novel_correlations_and_positive_hypotheses*

**Claim.** Restricted to groups where a trade actually happened, delivered pressure is the MAJORITY disposition, not the rarity a whole-day runway census makes it look. Of the 1571 groups carrying a fill, 993 moved the mid in the aggressor's direction against 261 accompanied by same-side withdrawal and 160 absorbed without a price move. The other 41998 groups of the day carry no trade at all and contribute no absorption evidence; scoring them as runways is what turns a 4:1 delivery-to-withdrawal reading into its inverse. The contact-runway scope agrees: 886 delivered against 453 withdrawal over 1414 runways.

**Evidence.**
```json
{
  "contact_census": {
    "ABSORBED_WITHOUT_PRICE_MOVE": 75,
    "ACCOMPANIED_BY_WITHDRAWAL": 453,
    "DELIVERED_THROUGH_PRICE": 886
  },
  "contact_runways": 1414,
  "group_census": {
    "ABSORBED_WITHOUT_PRICE_MOVE": 160,
    "ACCOMPANIED_BY_WITHDRAWAL": 261,
    "DELIVERED_THROUGH_PRICE": 993,
    "INDETERMINATE": 157,
    "INDETERMINATE_NO_CONTACT": 41998
  },
  "price_response_ticks": {
    "max": 27.5,
    "mean": 0.070014144,
    "min": -25.5,
    "n": 1414,
    "p10": -2.5,
    "p25": -1.0,
    "p50": 0.0,
    "p75": 1.0,
    "p90": 2.5,
    "p99": 9.0,
    "sum": 99.0
  }
}
```

**Falsifier.** If delivery were an artifact of my mid-change rule, the contact-runway census computed over a longer window would not agree with the group-scoped one. It does. A day where the two disagree in direction would falsify the reading.

**Confidence basis.** Both censuses are complete partitions of their own populations and both distinguish the no-contact population explicitly rather than folding it into a disposition, which is the difference that produces the inversion.

## 4.9

#### F-46
*novel_correlations_and_positive_hypotheses*

**Claim.** The touch is NOT static on this instrument once the ladder is measured on the FULL book. Computing 4.9 as an exact set difference between consecutive groups' complete after-books (book_full.*_levels_full), the spread changes on 3663 COMPRESSION and 2311 EXPANSION transitions of 43569, and the best price on one side or the other moves on 6079 occasions, with per-side tick distributions that are not symmetric. A group-local view of the same day - one that can only see the levels the group's own orders touch - sees almost none of this, because most touch movement is caused by orders that the group being scored did not itself act on. The scope of the ladder measurement, not the market, decides whether the book looks frozen.

**Evidence.**
```json
{
  "dominant_stratum": {
    "key": "ow-0069e456ba86b8f3b52e|A|PRE_SETTLEMENT",
    "max_gap_ticks": {
      "max": 5820000,
      "mean": 1746958.08,
      "min": 1314,
      "n": 50,
      "p10": 1314,
      "p25": 1380,
      "p50": 1380,
      "p75": 5820000,
      "p90": 5820000,
      "p99": 5820000,
      "sum": 87347904.0
    },
    "occupied_levels": {
      "max": 259,
      "mean": 232.3,
      "min": 102,
      "n": 50,
      "p10": 219,
      "p25": 230,
      "p50": 236,
      "p75": 245,
      "p90": 251,
      "p99": 259,
      "sum": 11615.0
    }
  },
  "touch_migration_events": 6079,
  "touch_migration_ticks_ask": [
    [
      -1,
      1676
    ],
    [
      1,
      651
    ],
    [
      2,
      221
    ],
    [
      3,
      123
    ],
    [
      -2,
      96
    ],
    [
      4,
      80
    ]
  ],
  "touch_migration_ticks_bid": [
    [
      1,
      1270
    ],
    [
      -1,
      597
    ],
    [
      -2,
      158
    ],
    [
      -3,
      123
    ],
    [
      2,
      120
    ],
    [
      3,
      106
    ]
  ],
  "touch_state_census": {
    "COMPRESSION": 3663,
    "EXPANSION": 2311,
    "UNCHANGED": 37594,
    "UNDEFINED_ONE_SIDE_EMPTY": 1
  },
  "transitions": 43569
}
```

**Falsifier.** If the movement I measure were an artifact of comparing consecutive after-books across groups that arrive out of order, the receive clock would have to move backwards somewhere; the stream refuses that and delivered every group in ts_recv_ns order. A stronger falsifier: a day on which the full-book set difference and a group-local difference give the same touch-migration count.

**Confidence basis.** Every transition is an exact set difference over integer raw prices with its own before and after level set; the counts sum to the group count with no residual, and the two sides are kept apart.

## 9a

#### F-53
*exact_evidence_and_clock_references*

**Claim.** Five retained fields are defective as carried rather than merely degenerate, and the distinction matters because a degenerate field costs nothing while a defective one can be read as a measurement. book_regime.best_bid and book_regime.best_ask are the integer 5 on every row while the real touch sits around 5.53-5.64, so book_regime.spread_raw is 0 on every row and the block's relative_imbalance is the only usable number in it; activity_since.last_trade.trade_buy_aggressor_qty and trade_sell_aggressor_qty are 0 on every row on a day carrying 2,028 trades and 2,411 fills, so the anchor window's aggressor tally is not being fed. I recommend they be REPAIRED, not dropped: each is cheap, each has an obvious correct value, and each currently reads as a real zero to anyone who does not check it against book_full.

**Evidence.**
```json
{
  "activity_since_last_trade_aggressor_qty": {
    "buy": 0,
    "day_fills": 2411,
    "day_trades": 2028,
    "sell": 0
  },
  "book_regime_best_ask_only_value": 5,
  "book_regime_best_bid_only_value": 5,
  "book_regime_spread_raw_only_value": 0,
  "true_touch_from_book_full": {
    "first_best_ask_raw": 5553000000,
    "first_best_bid_raw": 5530000000,
    "note": "book_full carries the correct integer raw prices on the same rows"
  }
}
```

**Falsifier.** A day on which book_regime.spread_raw takes a nonzero value, or on which the anchor aggressor tallies move, would show these are fed and merely quiet here.

**Confidence basis.** Each is a single-valued field in my own census over the rows I streamed, checked against a different field on the same row that carries the correct quantity, so this is a contradiction inside one row rather than an inference across rows.

#### F-54
*raw_mbo_retention_judgement*

**Claim.** KEEP EVERYTHING. Having computed all eighteen contract sections from the raw member rows myself, no field group and no registry layer on this surface meets the zero-value bar, and I recommend no elimination. book_full with its per-level FIFO queues is the most load-bearing block on the surface: my queue survival, birth position, replenishment episodes, ladder topology and every state frame rest on it, and the top-N projection beside it is not a substitute because the touch moves between levels the projection does not carry. The order identities and queue-position facts are the join keys of 4.6, 4.7 and 4.14 and nothing else can supply them. The genuinely redundant material - the top-N book projection, the legacy ten-level sizes, the derived age fields - is recoverable from book_full by a stated derivation, and I still recommend keeping it: it is small, and its value is that a reader can check the derivation rather than trust it. The fields nothing read on this day (raw flags, sequence deltas, the adapter's precomputed fill-disposition and mirror blocks) are genuine spares, not defects: they would carry information on a multi-channel or out-of-order day, and this Sunday is neither. Size was never an argument in this judgement.

**Evidence.**
```json
{
  "cannot_judge": [
    "canonical_predecessor_bootstrap_objects",
    "legacy_structure_observables",
    "derived_d_family_geometry",
    "prebirth_stopped_chain_false_context_controls"
  ],
  "elimination_recommendations": 0,
  "field_paths_censused": 605,
  "most_load_bearing": "book_full.*_levels_full[].fifo_queue[] (order_id, size, volume_ahead, priority_recv_ns, priority_sequence)",
  "redundant_but_keep": [
    "book.* top-N projection",
    "legacy row bid/ask 10-level sizes",
    "front_order_age_s / priority_age_s / queue_age_*",
    "largest_order_share"
  ],
  "registry_layers_reviewed": 55,
  "repair_not_remove": [
    "book_regime.best_bid",
    "book_regime.best_ask",
    "book_regime.spread_raw",
    "activity_since.last_trade.trade_buy_aggressor_qty",
    "activity_since.last_trade.trade_sell_aggressor_qty"
  ]
}
```

**Falsifier.** An elimination recommendation would be justified by a field or layer that no section reads, that is not recoverable from another field, and that could not carry information on any future day. I found none; a single such field named with all three properties shown would falsify this verdict.

**Confidence basis.** The judgement rests on my own field census over the rows I streamed and on having actually computed every section from those fields, so 'load-bearing' means a reading I performed and not a reading I assumed. The four CANNOT_JUDGE layers are named rather than guessed at.

## scope

#### F-55
*searched_coverage_and_current_causal_state*

**Claim.** What this run still cannot answer, marked unanswerable rather than answered thinly. (1) The mission's stream-position gradient across October 1, 3, 4 and 5 is cross-day and this run holds one day. (2) Whether the completion behaviour I measure in 4.10 is a property of the instrument or of the Sunday reopen: 43366 of 43569 groups are PRE_SETTLEMENT on one instrument in one continuity segment. (3) Whether the candidate population is representative: my detector searched 6582 of 17991 seconds after warm-up and promoted 91. (4) Any claim about the 54/55-week frozen D-family geometry: no such field is carried on the delivered rows, so the frozen vocabulary could be used as a seed for naming but never tested. (5) Whether the brain's 90 plays hold: every one of the eight that touches native MBO mechanics keys on forecaster-harness quantities (tape_conditions.*, phase flow) that this stream does not carry, so none was testable and none is reported as verified or refuted. (6) Anything about a decision clock distinct from F_LAST: the delivered rows carry decision_ts_recv_ns equal to f_last_ts_recv_ns on all 43569 of them.

**Evidence.**
```json
{
  "brain_plays_indexed": 90,
  "brain_plays_testable_on_this_stream": 0,
  "decision_delay_census": {
    "0": 43569
  },
  "detector_counters": {
    "candidates_emitted": 91,
    "candidates_pending_in_window": 0,
    "rejected_below_threshold": 1672,
    "rejected_in_refractory": 294,
    "rejected_in_refractory_at_release": 17,
    "rejected_not_local_max": 14,
    "rejected_zero_magnitude": 338,
    "seconds_in_warmup": 11399,
    "seconds_judged": 17981,
    "seconds_observed": 17991,
    "seconds_without_finite_flow": 2103,
    "suppressed_by_prominence": 2053
  },
  "groups": 43569,
  "instruments": 1,
  "phase_counts": {
    "PRE_OPEN": 203,
    "PRE_SETTLEMENT": 43366
  },
  "segments": 1,
  "source_days_in_mission": [
    "20211001",
    "20211003",
    "20211004",
    "20211005"
  ]
}
```

**Falsifier.** Each item becomes answerable when a second scored day is traversed under the same contract, or when the forecaster-harness channels the brain plays key on are delivered beside the MBO stream. None becomes answerable by re-reading this day.

**Confidence basis.** Every item is tied to a counter in this run that is structurally single-valued or structurally absent, so the limit is a property of the slice rather than of my reading of it.

