# Handoff 2026-09-28 ~09:3xZ: shrinking Frankie's Monday read (token stacks, passes, dedupe)

Branch `claude/frankie-monday-continuation-qlkvqr`, tip `34a9cb7a` (plus this file). Earlier record of the day:
`HANDOFF_20260928_SIDE_BUILDER_DISK.md` and `MONDAY_CHECKLIST_20260927.md`.

## Greg's standing rules for this work (2026-09-28)
- **Every token stack that works gets used**: "if they even reduce a little they're getting used ... this isn't a best
  option thing but everything that works." Ranking only orders the build.
- **Stacks are ADDITIVE. V7 does not replace V1-V6.** Each grammar version adds layers on top of the earlier ones:
  - V4: `^k`/`=k` runs, scales, `n/d` fractions, the space separator.
  - V5: tuples and signed zero.
  - V6: the bedrock tables.
  - V7: `?k` runs and wider deltas.

  Everything earlier still applies. The same goes for the existing reading-render layers (L1-L10, stacked_v1/v2,
  STACKED_TEXT): all of them get applied as well.
- **Remove every pass that is not necessary, and dedupe all repeated content.**
- **Read costs of $1k-5k are out of bounds.**
- **The principal stays HELD until the digest is shrunk.**

## The two code reviews (code-simplification and code-review-and-quality): what they said, and status
Both were report-only reviews of this session's code, and both came back before this handoff.

**Fixed in `61732105`:**
1. Staged-reading planner `plan_one` (the reviewer's R1). It still did about 11 tokenizer encodes per part. The rate now
   excludes the fixed wrapper tokens, and the search stops once a probe is within 1% of the budget. The reviewer measured
   about 2.25 encodes per part (the old search took 18.9).
2. `file_witness`. It is now keyed on fstat of the opened handle plus ctime, which removes the rename race.
   Mtime-preserving rewrites now rehash.
3. `_validate_manifest`. The memo has one slot and returns the part index. No manifest is retained per call, and the
   dead fallback is gone.
4. `frankie_box_run.yml`. The SSM Online gate no longer blocks the disk rescue or the CLM Pod step (neither uses SSM),
   and the presign put branch builds only the client it uses.
5. Composition canary. It now matches cells to kept columns with runs expanded, classifies 19-digit ints correctly, and
   tokenizes the dictionary lines.

**Still open (reviewer's required items for the digest writers):**
1. Put grammar decisions in DG/TS only. The parallel writer's code identity is only partly keyed, so a grammar change
   there might not force a rebuild.
2. Add a serial vs parallel byte-equality check on a real slice.
3. Make DISK_RESERVE a parameter, not a constant.
4. Fix the docstrings. The serial and parallel writers are NOT byte-identical for `bedrock.members`.
5. Consolidate the decoders and headers, which are triplicated across render, stream and parallel.
6. The Jev extract purge can let `j == cut` leak one row. It should be `j < cut`. Noted, not fixed.

## What landed this chat (after the reviews)
- **`8fd5a04c` DIGEST_V7.** `?k` runs of absent cells, and signed deltas on every integer column ending in
  `recv_ns` / `event_ns`, plus `group_index`.
  - Lossless. The shared `_plan_row` / `_collapse` / `_expanded` carry it into both writers.
  - Render and stream tests: 71 passed. The byte reference test is CI-only.
  - NOT yet built into a digest. Tables rebuild under the new grammar key (about 25 min with the parallel writer; a box
    action that needs Greg's go).
- **`6beac6e2`, `0537001d` stacks canary** (`deploy/aws/box/frankie_box_digest_stacks.sh`, lock `box-canary`, about
  1 min). Measured on 1,500 contiguous real rows per table.
  - **Weighted over the digest (about 2.04B tokens), V7 plus keys-once is about 26% off.** Results by table:

  | Table | V7 on top of V6 | V7 + keys-once JSON |
  |---|---|---|
  | replenishment | -34.3% | -34.3% |
  | mirror | -25.7% | -25.7% |
  | absorption | -23.6% | -23.6% |
  | lineage | -19.7% | -19.7% |
  | ladder | -12.7% | -12.7% |
  | members | -12.5% | -12.5% |
  | recurrence | -4.7% | -47.4% |
  | queue | -4.6% | -43.4% |
  | legacy tables | 0 (already delta) | 0 |

  - The v2 run (36401461809, adds example cells, same-row equal timestamps and block-absent columns) SUCCEEDED; its
    output has NOT been read yet. Read its job log first.
- **`34a9cb7a` brain dedupe.** Identical bytes are carried once.
  - `brain.load(carried=)` writes later same-sha copies as one-line references and does not re-read them.
  - The session passes the current digest's sha.
  - Test added: 19 passed.

## Where the digest goes to Granite more than once (explorer map, file:line in `frankie_box_boss_session.py`)
1. **Reading corpus (1193-1332).** It holds the head, the evidence, the brain, then the whole digest.
   - Before `34a9cb7a`, each prior brain entry added its digest twice.
2. **Part reads (1368-1407).**
   - An unusable note is retried once, then split into halves: up to 4 calls on the same bytes.
3. **Merge tree (1533-1561).**
   - Every level re-sends the previous level.
   - `keep_if_lossy` rejects any merge that drops a line, so merges barely shrink.
   - **Single-note groups are still sent to the model (1553-1556).** TODO: pass them through.
4. **Classroom staged path.** `frankie_box_classroom_staged.py:84-93` via `frankie_box_staged_session.consume_sources`
   makes a **SECOND FULL STAGED READ of the digest** plus the merged notes.
   - TODO: read the digest by reference from the reading receipts and fetch ranges on demand.
   - The legacy non-TEACH path concatenates the digest into 19 prompts and refuses at size (1688).
5. **Writing (2003-2075).** 12 calls, each with merged notes plus up to 140 KB of the digest HEAD.
   - The head goes 12 times. TODO: send it once or by reference.
6. **Chunk plan.** `_chunks` re-tokenizes the whole corpus on every start. `reading-plan.json` is written, never read,
   and moved aside. TODO: reuse it when the corpus sha matches.
7. **`reading.json` carries `at=time.time()` (1417).** That changes the classroom cache identity on every reading re-run
   and forces the second staged read again. TODO: drop `at` from identity.
8. Staged plan and part ids include the header text and binding (`frankie_box_staged_reading.py:63-67,197`).

## Next stacks (build order only; ALL get used)
1. **Keys-once JSON.** The canary proves it: queue `episodes` and recurrence `runs`/`gaps` are lists of same-keyed
   objects.
   - Declare the key order once per column in the header (planner tracks a per-column shape Counter; parallel merges
     the counts; pick the max, tie by key text).
   - Write inline cells as `R` + values (`,` between values, `;` between rows, each value compact JSON parsed with
     `raw_decode`).
   - Dictionary entries stay JSON.
   - Better still: explode single-element lists into columns / child tables, so `^`, deltas and the dictionary apply
     inside them.
2. **Same-row equal timestamps.** absorption `closed/opened/emitted_at_recv_ns` are the same value, as are ladder and
   replenishment `emitted_at_recv_ns == recv_ns`. Write them as an in-row reference or a PAIRED-style offset.
3. **Whole-table absent columns.** Add a `?col` header mark for columns absent on every row. Reorder members columns so
   absent ones group, to lengthen `?k` runs.
4. The rest, in order:
   - dictionary cutoff (inline when shorter than `@n`)
   - derived `*_count = len(list)`
   - packed digits (stacked_v2 P forms)
   - shared dictionary
   - member-ordinal joins and row refs
   - hash handles
   - the L1-L10 / stacked layers over the digest itself
5. Replenishment `price_relations` (json, not uniform) and the int lists `attributed_to_episode_ids` /
   `neighbour_offset_ticks` (about 23 items each): design from the v2 canary examples.

## Runs in flight at handoff (probe them first)
- **Launch r3.** Run 36398770889, commit 689677f3, config r3. Still in_progress at 09:1xZ: 32 spawn workers (classroom
  pool), cpu fine. Read its output: exit 3/4 with a WAIT means pending, not failure. Then run the queue in the
  scratchpad copy below.
- **Jev CLM Pod.** Run 36398106270, commit e13ea0fe, lock clm-pod. In progress. Read report.md and the artifact when
  done.
- Granite Pod fhiwwlouzyx6l2 is running ($1.09/h).

## Cycle-0 queue after the shrink (principal HELD)
Build the stacks, then stage the new commit (stage and dispatch the SAME commit), then:
config r4 -> launch r4 (+probe) -> principal (+probe) -> record initial -> resume 1 -> correction -> record correction ->
resume 2 -> retain.

Paths and variables:
- CALC = `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`
- PREPARED = `/opt/frankie-box/work/trading-day-preparation/full-20211004-20260927-r6-48/prepared-configuration.json`
- PRINCIPAL = `/opt/frankie-box/work/principal-inputs/full-20211004-20260928-r1/principal-inputs-receipt.json`
- boss_commit in the config must equal the executing checkout (agent_file_handoff.py:141), so each new code commit needs
  a new config and a new launch.

The digest re-render under V7+ is a ROOT re-run from saved sources and needs Greg's go.

## Open question for Greg
The "structure whole, rows on demand" reading model. Greg leans toward it: "shrink first."
