# DROP-IN BOX — FRANKIE A-ARM, NEXT SESSION

**BRANCH: `chatgpt/frankie-raw-mbo-benchmark-20260828`**
**TIP AT HANDOFF: `81d81f9` — run `git log --oneline -1` and confirm it is that or later.**
**STATUS: NOTHING LAUNCHED. Calculation layer built and tested. Driver is a draft. Nothing wired.**

---

## 0. STOP BEFORE LAUNCH

**Do not dispatch a workflow, invoke a model, or start either arm.** Walk the whole thing
through with Greg first. Two decisions are unmade, the driver has never run, three
components are wired to nothing, and there is no end-to-end execution path. A launch from
here produces artifacts that look complete and are not.

## 1. FIRST THREE COMMANDS

```
git fetch origin chatgpt/frankie-raw-mbo-benchmark-20260828
git checkout -B chatgpt/frankie-raw-mbo-benchmark-20260828 origin/chatgpt/frankie-raw-mbo-benchmark-20260828
git log --oneline -1
```

Then read **`research/kalshi/FRANKIE_A_ARM_PRELAUNCH_STATE_20260829.md`** end to end. It is
the state record AND the file map. **Nothing in it should need searching for, and nothing in
it should be rebuilt.** If you find yourself hunting for a file, that document has a gap —
fix the document, not just your search.

## 2. TWO SANITY CHECKS BEFORE BUILDING ANYTHING

```
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests/ -q
python3 research/kalshi/frankie_raw_mbo_benchmark/refresh_native_frankie_knowledge.py \
  --spec research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_SOURCES_20260828.json \
  --repo-root . --check
```

Expect **441 passed** and **`"status": "CURRENT"`**. If the suite is not 441 green, stop and
find out why. If the refresh says `UPDATED`, someone hand-edited a generated capsule — that
needs understanding, not overwriting.

**Seven failures in the wider `research/kalshi/tests/` suite are PRE-EXISTING.** Verified by
running that suite at `d5b7b51`, the pre-session tip, where the same seven fail. Do not
treat them as regressions and do not fix them as part of this work.

## 3. THE FOUR ARCHITECTURE CORRECTIONS THAT REFRAME THE PAPERS

The A-arm papers were written against an API design that is not what you are building.

1. **The Sol run is an agent-session run**, like the group blind/refine walks — no API. The
   papers demand a "provider-originated response" in three places and
   `validate_principal_execution` demands provider, model IDs, invocation ID and token
   usage. None of that exists. The proof problem becomes the walk's file-based contract:
   read a committed staged state, emit a committed artifact, coordinator hard-fails on
   missing or malformed.
2. **Two roles only** — `REAL_TIME_FRANKIE` and `FORECASTER_FRANKIE`. The five-specialist
   structure is not used. The knowledge manifest already carries exactly these two; nothing
   needs changing there.
3. **Helpers are tools, not lanes.** RT and Forecaster may call an agent helper from their
   tools. Answers the ingestion paper's Question 3. Probable origin of the number four: a
   t3.xlarge has 4 vCPUs and there are 4 helper scouts.
4. **All four days are scored findings days**, one role `SCORED_FINDINGS_DAY`,
   `roster_position` carries stream order. This is what forced A-clean to be stripped.

## 4. WHAT IS DONE — DO NOT REBUILD

All 16 calculation-contract sections, the runner with 7 artifact layers and 8 fail-closed
gates, the periodic checkpointer, the roster migration to 97 layers, A-clean cleaned of
scored-day results, the prior-memory package hash made reproducible, the mission audited and
widened, and the vocabulary opened so families, depths, phases, states and dispositions can
all grow. **441 tests.** Full inventory with line counts in section 7 of the state doc.

## 5. WHAT IS OPEN

**Decisions (Greg's):**
- **D6 session/phase boundaries — THE BLOCKER.** Nothing defines RTH/ETH/reopen for Oct 2021
  CME. Segments decide what gets censored, where runs restart, where horizons cut. Proposal
  on the table: the 21:00 UTC anchor the data already shows.
- **D5 clustering** — in this run or not. Softer: the runner takes discovery as optional.

**Build:**
- The driver (`native_replay_driver.py` is a DRAFT — untested, feeds only clocks and
  coverage, and its invocation abstraction assumes an API call).
- Wire the checkpointer. Wire the execution gate. **Verify by search, not assumption** —
  both are currently referenced by nothing.
- Feed sections 4.6 through 4.16 from the traversal.

**Compute — unresolved:**
- **The A-arm workflows dispatch nothing.** Zero `ssm`/`ec2`/`INSTANCE_ID` references. They
  stage the packet, push to S3, and stop.
- **The recorded box is a t3.xlarge (4 vCPU / 16 GB)**, not 8 CPU / 64 GB. Unverified — no
  AWS creds this session. 5 of 16 sections previously took 2,985s and produced a 1.5 GB file.

**Parked by decision:** D3 / `ALLOWED_BOSSES`, and native-build proof modes for B0/B1/B2.

## 6. DO NOT TIDY THESE

Superseded values in the original review findings, the historical handoffs and the A-memory
prior-run reports are **deliberate** — records of what was true when written. Sweeping them
destroys the audit trail. The warmup-scoped capsule proposal is kept unregistered as the
record of an analysis the all-days-scored decision superseded; do not wire it.

## 7. THE ONE RULE THAT MATTERS MOST

**If you change any decision, update `FRANKIE_A_ARM_PRELAUNCH_STATE_20260829.md` in the same
commit.** The first version of that document went stale exactly because that did not happen,
and a stale handoff is how work gets rebuilt and findings get dropped.
