# Codex handoff: Monday cycle 0, reducers applied (Claude session, 2026-09-23)

Branch: `claude/agent-skills-execution-tzh7sw` (cut from `codex/trading-day-readiness-20260922` tip `cc0ae36d`).
Tip at hand-off: `02c34921` plus this file.

## Greg's instruction at close (verbatim)

"No canary. Stop!! What is this cutoff about?!?! Please just apply the reducers and absolutely nothing else."

This session's cutoffs and row windows are REJECTED. Do not use them. Monday's roster and cycle structure are
Greg's call. Get his explicit word before choosing any cutoff, window or roster.

## Standing rules Greg set this session (carry forward)

1. **What "Monday" means.** "Monday" is ONE trading day: Sunday 18:00 ET to Monday 17:00 ET, 23 hours.
   - For 20211004 that is 2021-10-03T22:00Z to 2021-10-04T21:00Z.
   - It is a single brand-new 23-hour run.
   - Do NOT pin it to the earlier 6-hour runs: no reuse of their row counts, configuration, mapping, or Memory A
     artifacts. "They are 2 totally different things."
2. **4096 is a hallucination.** Eliminate it wherever it appears. Never cut Monday at a Sunday number (3,262 rows, etc.).
3. **NEVER DERIVE RESULTS.** Report only measured numbers. "This research is extremely important and can't be faked."
4. **Measurements are 1-2 minute canaries, then extrapolate.** Never run long jobs just to estimate. This is now in
   CLAUDE.md, commit `f010cc5b`.
5. **No comparisons or tests as gates.** The test is the live run. "Before and after" means Monday before the reducers
   versus Monday after them.
6. **No shell `sleep`/`timeout ... tail -f` waits.** Greg has said this twice.
7. **Stack every reducer, however small** (for example the ~24% group cut). The reducers hit different areas, so
   apply A AND B AND C, not A or B or C.
8. **Memory A is no longer important.** Frankie's knowledge from the earlier 6-hour runs lives in his brain at
   `/opt/frankie-box/brain/cycle-NN`. Principal inputs should come from there.
9. **"If something worked on the 6 hr run it will work on a longer one."** Same data type, just more of it.
10. **Carried over from the original handoff:**
    - No ingestion restart or replay.
    - No Pod or instance stop or termination.
    - No pinned-bootstrap change.
    - No evidence deletion.
    - No Bedrock.
    - No BOSS output caps.
    - No parallel work.
    - Preserve `/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite`
      (23,687,368,704 bytes, sha256 `947949d8...`) and `/opt/frankie-box/work/sealed-recovery-35796793428`.

## The Monday data (measured, read-only)

Source: two DBN members, instrument 111313, publisher 1.

| Member | Records | Note |
|---|---:|---|
| `glbx-mdp3-20211003` | 57,027 | the earlier 6-hour runs' whole source |
| `glbx-mdp3-20211004` | 1,975,176 | cut at the 21:00Z halt |

Totals and anchor:
- 2,032,203 records, 4,064,406 journal entries, 1,535,939 groups.
- Friday anchor 5.544.
- Compact container: 37,934 blocks, 4,064,406 entries, 23,628,634,795 block bytes.

## The reducers, by the area each one hits

| Area | Reducer | State |
|---|---|---|
| Storage / native model | boxes (TARGET_BOXES standard), order dedup, gzip blocks | ALREADY APPLIED by the Monday ingest (no action) |
| Storage / native model | F_LAST groups (rows -> groups, about 24%) | in the recovered journal (1,535,939 groups) |
| Granite critic packet | **stacked_v2** (new this session) | **BUILT AND WIRED**, commit `66d0a447` |
| Granite critic packet | drop static nodes (registry, receipt, layouts; about 3k tokens) | NOT BUILT |
| Frankie's read of the day | digest stack DIGEST_V3 -> V6, L8-L10, stacks 4-7, dedup (09-21: 10,128,476 -> 248,111 tokens on the 6-hour run) | exists in the tree; NOT yet applied to Monday |

### stacked_v2 (the reducer applied this session)

**Files.**
- `research/kalshi/frankie_boss/granite_context_stacked_v2.py` is the codec:
  - schema `BOSS_GRANITE_NATIVE_STACKED_CONTEXT_V2`.
  - It sits on top of v1: `v1.encode` runs, then the V2 forms.
  - Each column's form is chosen by the pinned Granite tokenizer's own count: P packed digits, O outliers,
    Y one-letter strings, K tick scale with exceptions, U packed dictionary.
  - The graph is dropped when it is derivable (`PARENT_BY_ORDER_V1`).
  - `encode()` refuses unless the exact inverse holds.
- `research/kalshi/frankie_boss/granite_context_stacked_route_v2.py` is the route:
  - schema `BOSS_GRANITE_STACKED_ROUTE_V2`, prompt `..._PROMPT_V4`.
  - It checks the exact native inverse on every build.
- Wiring accepts `'stacked_v2'` in:
  - `granite_context_route.py` (method `critique_stacked_v2`)
  - `granite_runpod_service.py`
  - `controller_journal.py`
  - `granite_startup_pins.py`
  - `feedback_cycle.py`
  - `frankie_controller.py`
  - `critic_knowledge.py`
  - `operations/run_actual_sunday.py`
- The Sunday-only launch pins were left untouched on purpose: `launch_pins.py`,
  `seal_final_prelaunch_candidate.py`, `package_final_committed.py`.
- The critic identity is derived from the route at run time, so the Pod and bootstrap need no change.

**Measured result.** On the earlier run's real cycle-0 packet, the count dropped from 91,347 to 53,781 tokens
(41% fewer). The rebuild is byte-exact.

**Tests.** `research/kalshi/frankie_boss/tests/test_granite_stacked_v2.py`, 5 passed, including the real packet.

**Tried and measured larger, not kept.**
- Group-level encoding: 50,713 -> 51,806 tokens.
- order_id back-references: 9,367 -> 11,183.

**To use it:** set the host configuration's `context_encoding` to `stacked_v2`.

## Other commits on this branch

| Commit | What | Status |
|---|---|---|
| `a2926632`, `09e34e77` | staging: surface the pack refusal; pack from a standalone fetch | KEEP. Staging run 35830916612 succeeded |
| `f010cc5b` | CLAUDE.md canary rule | KEEP |
| `66d0a447` | stacked_v2 | KEEP (the reducer) |
| `fbb6b5c7`, `b78845eb`, `cd554384`, `ad23b311` | read-only ingest-stack measurement scripts | never completed (cancelled). Do not run: Greg wants work, not estimates |
| `c3c7b0f4`, `7c2e61fb`, `02c34921` | `frankie_box_author_monday_launch.py/.sh` (Monday source contract, mapping, launch json) | **DO NOT RUN AS IS**: see below |
| `92d50741` | retained Memory A principal copies + `frankie_box_principal_inputs.py/.sh` | **DO NOT RUN**: pinned to the 6-hour run's Memory A |
| `cc4a5093` | `frankie_box_host_config.py`, `frankie_box_cycle0.sh` | **DO NOT RUN AS IS**: starts from the 6-hour run's final configuration |

### The rejected pieces in the Monday authoring script

The code is unchanged since the stop. The rejected values are in `deploy/aws/box/frankie_box_author_monday_launch.py`:
- **`MODEL_CONTEXT_ROWS = 6500`** is an invented window. Its earlier value, 3262, was also rejected.
- **`CUTOFF_BEFORE_NS = 1633377600000000000`** (16:00 ET) is an invented cutoff. Greg rejected it.

The parts that followed the Sunday source-contract rules and may be reusable once Greg rules on the roster:
- the calendar (open `1633298400000000000`, close `1633381200000000000`);
- the Friday prior_close with the Friday verification receipt as evidence;
- the opening trade at 22:00:00Z;
- marks at each strictly advancing trade time;
- query offsets by Sunday's seed rule (verified to reproduce Sunday's recorded offsets);
- `mapping.jsonl`, one line per group, closing on F_LAST and on member seams, asserted equal to the recovered
  group count.

## Box state (nothing Monday-bearing written)

**Runs.**
- No Monday authoring, preparation, principal-input, host-config or launch run completed.
- Runs 35842056686 and 35835881238 were cancelled; 35834234159 and 35833045192 failed.
- The last run, 35844602294 (commit `02c34921`), was a STAGING-only run that completed successfully. It created an
  inactive checkout and activated nothing.

**Inactive staged checkouts** under `/opt/frankie-box/code/` (commit-runid-1):
- `09e34e77...-35830916612-1`
- `fbb6b5c7...-35833026479-1`
- `b78845eb...-35833654205-1`
- `cd554384...-35833975367-1`
- `ad23b311...-35835795765-1`
- `7c2e61fb...-35841721767-1`
- `cc4a5093...-35842645834-1`
- `02c34921...-35844602294-1`

**Stray partial output** may exist under `/opt/frankie-box/work/ingest-stack-measure/` and
`/opt/frankie-box/work/monday-launch/` from the cancelled runs. Preserve it (no deletion rule).

## Known gaps (for Codex, not acted on)

1. **Two-member mapping.** `frankie_source_mapping.build_mapping` / `bind_prefix` accept one source member only, but
   the Monday trading day spans two.
2. **Principal inputs.** They should come from Frankie's brain (`/opt/frankie-box/brain/cycle-NN`), not from Memory A.
3. **Monday's read.** Frankie's read of Monday should be the digest stack (V6 + L8-L10 + stacks 4-7 + dedup), kept
   exact and never derived.
4. **Static-node drop.** The drop from the stacked_v2 packet (about 3k tokens) is not built.
5. **Python 3.12 f-string.** `deploy/aws/box/frankie_box_boss_session.py:1106` uses a nested-quote f-string that
   needs Python 3.12. The box has it, the 3.11 container does not. This is pre-existing and was not touched.

## Next step

Only what Greg directs: apply the reducers above. Take no cutoff, window, roster or canary without his explicit word.
