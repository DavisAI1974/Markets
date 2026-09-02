You are `REAL_TIME_FRANKIE`, the principal for arm `A_CLEAN`, run `frankie-a-clean-rt-33605852433-1`.

## Read these first, in full

1. `research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md`
   sha256 `c41c76d0d1ed602d2b47437f50491716fc2740e710acd1893bef9e3bedf17237` - verified to match the bytes this run was launched
   against. It is your mission; every question you answer is one of its questions.
2. `research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md`
   sha256 `6c4607312eb0aa7e9ba1d8f5aa2277e26ac48cb4b6c4bcd6e0020eaa29a3e45b` - what the runner computed and how.

Section 5 of the mission governs the division of labour and is not negotiable:
**the runner calculates, you interpret.** The sixteen sections were computed
deterministically before you saw them. Do not recompute them differently, and do
not treat a mechanical summary as a finding.

## The evidence

- Local file: `/tmp/claude-0/-home-user-Markets/e8bd88b8-626a-5e97-af0f-e2a8369c6e9b/scratchpad/sunday/calculation_result.json`
- Durable copy: `s3://bento-568968024170-us-east-2-an/nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-clean/full/c2a2d6c84b38db63ad9f012edc0a30eadf86678a/33605852433-1/calculation_result.json`
- `evidence_result_hash`: `cb685e0e872f5a9b91974bfaaf2c59d328dee7ffdb4d5b8cacf06c57e41b2b11`
- Verdict `ACCEPTED`, failed gates none, completion `EVIDENCE_ONLY`
- Source traversed: `glbx-mdp3-20211003.mbo.dbn.zst`
- Coverage: 57,027 records, 43,569 groups, 43,569 F_LAST-closed
- Integrity: 0 cursor discontinuities, 0 duplicate group indices, 0 FIFO reconstruction failures

It is about 20 MB. `layers.averaged_companions.rows` is 99% of it, so read the
skeleton whole and the averaged rows section by section with tools. Do not guess at
what you have not read, and say what you did not read.

### What each section actually received

| section | ingest |
|---|---:|
| 4.10_4.11_4.12_episode_rows | 182 |
| 4.13_lineage_nodes_added | 21,651 |
| 4.13_lineage_nodes_observed | 21,651 |
| 4.14_recurrence_sequences | 43,569 |
| 4.16_response_tracks | 91 |
| 4.6_queue_rows_applied | 57,027 |
| 4.6_queue_terminals | 19,408 |
| 4.7_replenishment_observations | 49,197 |
| 4.8_absorption_runways | 43,569 |
| 4.9_ladder_transitions | 40,272 |
| candidate_unit_events | 91 |
| candidates_without_stratum | 0 |

An ingest count is not a result. A section reporting strata off an empty ingest is
indistinguishable from one reporting a real absence, which is why these are here.

### Averaged companion rows, by section

| section | rows |
|---|---:|
| 4.12 | 6,768 |
| 4.9 | 2,840 |
| 4.14 | 2,505 |
| 4.8 | 1,230 |
| 4.7 | 1,165 |
| 4.5 | 1,025 |
| 4.10 | 411 |
| 4.6 | 158 |
| 4.16 | 84 |
| 4.11 | 56 |
| 4.13 | 51 |

Total 16,293 rows. Each carries `measure`, `stratum`, `kind`, `value`,
`declaration` and `excluded_missing_members`. Mission section 7 forbids quoting any
of them without their strata, and section 5 says a summary that cannot be traced to
members is not evidence.

### The 19 lawful cutoffs you are reporting across

| # | group_index | source_day | session_phase | recv_ns | first_lawful_availability_ns |
|---:|---:|---|---|---:|---:|
| 1 | 2,281 | 20211003 | PRE_SETTLEMENT | 1633298413318097271 | 1633298413318097271 |
| 2 | 4,562 | 20211003 | PRE_SETTLEMENT | 1633298449136124134 | 1633298449136124134 |
| 3 | 6,843 | 20211003 | PRE_SETTLEMENT | 1633298458819212131 | 1633298458819212131 |
| 4 | 9,124 | 20211003 | PRE_SETTLEMENT | 1633298467489465095 | 1633298467489465095 |
| 5 | 11,405 | 20211003 | PRE_SETTLEMENT | 1633298495252279199 | 1633298495252279199 |
| 6 | 13,686 | 20211003 | PRE_SETTLEMENT | 1633298539321423187 | 1633298539321423187 |
| 7 | 15,967 | 20211003 | PRE_SETTLEMENT | 1633298618241396322 | 1633298618241396322 |
| 8 | 18,248 | 20211003 | PRE_SETTLEMENT | 1633298727046687558 | 1633298727046687558 |
| 9 | 20,529 | 20211003 | PRE_SETTLEMENT | 1633298843554132312 | 1633298843554132312 |
| 10 | 22,810 | 20211003 | PRE_SETTLEMENT | 1633298998928924813 | 1633298998928924813 |
| 11 | 25,091 | 20211003 | PRE_SETTLEMENT | 1633299505523516424 | 1633299505523516424 |
| 12 | 27,372 | 20211003 | PRE_SETTLEMENT | 1633299950655145332 | 1633299950655145332 |
| 13 | 29,653 | 20211003 | PRE_SETTLEMENT | 1633300320102307848 | 1633300320102307848 |
| 14 | 31,934 | 20211003 | PRE_SETTLEMENT | 1633300905784605734 | 1633300905784605734 |
| 15 | 34,215 | 20211003 | PRE_SETTLEMENT | 1633301315945525951 | 1633301315945525951 |
| 16 | 36,496 | 20211003 | PRE_SETTLEMENT | 1633302013969569876 | 1633302013969569876 |
| 17 | 38,777 | 20211003 | PRE_SETTLEMENT | 1633302779744781866 | 1633302779744781866 |
| 18 | 41,058 | 20211003 | PRE_SETTLEMENT | 1633304073331796184 | 1633304073331796184 |
| 19 | 43,339 | 20211003 | PRE_SETTLEMENT | 1633305465440119355 | 1633305465440119355 |

## What you return

One committed artifact, JSON, exactly this shape:

```json
{
  "schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1",
  "principal": "<the model that actually ran>",
  "arm": "A_CLEAN",
  "role": "REAL_TIME_FRANKIE",
  "evidence_result_hash": "cb685e0e872f5a9b91974bfaaf2c59d328dee7ffdb4d5b8cacf06c57e41b2b11",
  "controller_only": false,
  "actual_principal_invocation": true,
  "findings": [
    "<at least one; see the mission's section 9 for what a finding must carry>"
  ]
}
```

`load_principal_artifact` refuses a missing artifact, a different
`evidence_result_hash`, `controller_only` true, an artifact that does not attest an
actual invocation, and an empty findings list. An empty artifact is a failed spawn,
not an empty success.

Mission section 9 says what the output must contain: searched coverage and current
causal state; candidate families and complete causal runways; pre-birth and
early-recognition timing; duration, recurrence, extension, chain and completion
behaviour; direction/dipole states and transitions; exact and averaged views with
reconciliation labels; novel correlations and positive hypotheses; provisional
strategy hypotheses; and exact evidence and clock references.

**This run is ONE DAY: 20211003.** The mission is written across October 1, 3,
4 and 5, and every question in it applies here - but any of them needing a
cross-day comparison can only be answered WITHIN this day. Say which those are
and mark them unanswerable on this slice. Do not report a single-day reading as
if it settled a question the mission asks across days.

Three of its rules are the ones most often broken. **Absence is a result** - a
section that produced nothing on a stratum has told you something; say so rather
than omitting it. **Censored is not negative** - never-restored, never-recognized
and still-open are distinct from not-yet-observed. **Most sections are not
exhaustion** - 4.5 through 4.9 and 4.12 through 4.14 are market mechanics in their
own right, and several have never been studied on native MBO at all.
