# Handoff 2026-09-28: joined teachers built, r9 stopped, r10 not configured

Branch `claude/frankie-monday-cycle-0-urozez`. The tip is this handoff's commit; the code commit is dfe08ca7. Launch is on HOLD.
Nothing is running or billing from this session.

## State
- r9 is STOPPED and nothing is lost:
  - launch 36464699766 and principal 36464728520 were cancelled;
  - stop_cycle ran as run 36471583366;
  - Jev relays 36464345188 and 36471870371 were cancelled;
  - the run dir `/opt/frankie-box/work/runs/monday-20211004-20260928-r9` is preserved.
- The fixes since r9 are all on the branch:
  - saved walk blocks and the concurrent teacher (the journal is read once);
  - teacher changes: all levels, the whole day, unknown trades carried, D values computed instead of INVALID, and no normalizer cap (no 4096);
  - Jev and principal notes are split into parts, regenerated, and never truncated;
  - a run is refused on duplicate data.
- **The joined teachers are BUILT but NOT RUN.** The spec is `SPEC-joined-teachers.md` (status block at top). The pieces:
  - builder: `deploy/aws/box/frankie_box_joined_teacher.py` + `.sh`, on its own lock `box-joined-*`;
  - delivery: `dipole_joined_teacher.py`, the `joined_teacher` field in the scientific request, the box readings of both teachers, the host validators, and `frankie_box_cycle0.sh ACTION=config JOINED=<MANIFEST.json>`.

## Greg's decisions this session
- **Bedrock is a LOGIC HELPER for the teachers, not a Frankie knowledge base.** Nothing from it goes into Frankie's brain or his pre-message.
  - The teachers read the computed layer files in place: no copies, no recalculation.
  - The bedrock is static for this Monday and is built once.
- **What the teachers see:** all the data except how Frankie makes decisions. Three rules:
  1. The decision process is withheld.
  2. Graded outcomes are kept out of the lesson material.
  3. Frankie's findings are claims, never truth.
- **The two teachers exchange specialties** (CHAT14/CHAT15):
  - the original BOSS teacher: math and representation supervision, plus science;
  - the classroom scientific teacher: mechanism and evidence.
- Standing rules:
  - zero data dropped; unknown or incomplete data is listed, never dropped;
  - no caps, no truncation, nothing normalized or averaged (a correlation is an average, D37);
  - progress is saved on every stop; work runs in parallel;
  - duplicate data is refused, with the reason;
  - no tests or validations; py_compile only.

## Next, each step on Greg's go
1. Stage the tip on the box with `frankie_box_stage_code.sh`. A cycle0 dispatch needs the staged commit to equal the branch tip, so restage after every push.
2. Run the builder, with the probe `frankie_box_progress.sh DIRECTORY=<OUTPUT_ROOT>` attached:
   - `frankie_box_joined_teacher.sh`
   - `OUTPUT_ROOT=/opt/frankie-box/work/joined-teacher/monday-20211004-r1`
   - `CALCULATIONS_RECEIPT=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/calculations-receipt.json`
   - `CALCULATIONS_SHA256=85164f3c78f27e8d20955d0e6b2ca89d70304dcce42fe20e390ffbc14fc40432`
3. Report its sizes (series, pair-cells, bytes of `sources/couplings-beyond-null.md`) BEFORE any teacher reads it. Greg decides if the read cost is sane ($1k-5k reads are out of bounds).
4. Build the r10 config with `ACTION=config`:
   - `PREPARED=/opt/frankie-box/work/trading-day-preparation/full-20211004-20260927-r6-48/prepared-configuration.json`
   - `PRINCIPAL=/opt/frankie-box/work/principal-inputs/full-20211004-20260928-v9-r2/principal-inputs-receipt.json`
   - `RUN_ID=monday-20211004-20260928-r10`
   - `OUTPUT_ROOT=/opt/frankie-box/work/monday-run-config/full-20211004-20260928-r10`
   - `JOINED=/opt/frankie-box/work/joined-teacher/monday-20211004-r1/MANIFEST.json`
5. Launch, then the principal, with probes on both.
6. Start the Jev relay pointed at r10's request dir. **Do not resend the dipole catalog.**

## Open calls for Greg
- The classroom still grades on the 171 pooled Pearson pairs. Replacing them re-mints the grading; that is a separate call.
- The same Granite model plays every role, so agreement between roles is not independent confirmation.
- In `concurrent_teacher`, a teacher that fails to pickle falls back to in-process: keep that as a fallback, or make it a hard stop?
- An audit across every process for anything still dropped or capped was offered and not yet run.

## Answered for Greg (2026-09-28)
- **"Can Frankie not read anything over that small limit?"** He can.
  - The limit is per call: 131,072 tokens of context, about 87,000 of input per part.
  - Larger material is read whole, in consecutive parts. The Monday digest was read in 4 parts, and the shared research is read the same way.
  - What grows with size is the number of calls, which means cost and time. The bedrock's about 3.8 GB would be thousands of parts. That is why the bedrock is a teacher tool read by code, not a Frankie read.

## Update: what Frankie's knowledge base holds, and the open role question (Greg, after the handoff)
Greg: "Frankie gets all the calcs added to his knowledge base so the tables are redundant anyway. We want bedrock to
keep some priming for his pump but maybe that was the wrong direction anyway. We'll have to look at what his exact role
is and cater the prime to exactly that."

What the brain entry holds, per `frankie_box_brain.write_entry`:
- The derivation digest. Since V9 it carries the 5 legacy tables only; the bedrock tables are not rendered.
- The accounting entry and the ledgers, `analysis.md`, `derive.md` (the status, producer and hash of every layer), and the comparison packet.
- The classroom teach-back and the exhaustion/D teach-back.
- The bedrock traversal receipt.
- A listing of `work/derived` (names, bytes and sha256 only).
- The frozen learned-structure files, via the frozen entry.

So the bedrock layer CONTENTS are not in his knowledge base. What primes him from the bedrock is:
- the exhaustion/D teach-back (facts computed by code: D-depth histogram, ancestry gaps, clock order, families, candidate lane);
- the frozen learned-structure text for the four D/exhaustion layers.

Open, before the next build: define Frankie's exact role, then cater the prime to it. That covers the teach-back facts, which frozen files, and whether the joined-teacher couplings feed him at all. The joined teacher build (dfe08ca7) stays unrun until then.

## Update: Granite is a reasoning boost, not Frankie (Greg)
Greg: "granite is supposed to only be a small piece of frankie and that is reasoning boost." Asked whether the bedrock
priming must be wired to Granite: it does not. The teach stage's facts are computed by code, and Granite only restates
them, under a check that refuses any number the code did not give it.

Every Granite call in the principal today (`frankie_box_boss_session.py` and the classroom and scientific modules), with
the proposed owner:

| Call | What it does today | Proposed |
|---|---|---|
| reading (digest in parts) | writes notes that restate code-made tables | CODE (the data is already exact) |
| merge levels | "preserve every line verbatim, reorder, remove exact duplicates" | CODE (line dedupe) |
| teach (exhaustion/D) | restates code facts; foreign numbers refused | CODE |
| classroom 19 components | transcribes every observation, plus pairs, plus novel findings | transcription CODE; novel findings GRANITE |
| classroom summary | summary over the answers | GRANITE only if it reasons; otherwise CODE |
| writing: accounting + ten ledgers | structured bookkeeping | CODE fills the structure |
| writing: analysis | the narrative of the run | GRANITE (reasoning) |
| correction turn | resolves the graded corrections | GRANITE (reasoning) |
| scientific review, BOSS teacher, Frankie replies | mechanism and evidence reasoning | GRANITE (reasoning) |
| staged readings before each role | each role reads the whole corpus in parts | replace with code-selected exact inputs per question |

Principle: code does everything computable or transcribable. Granite gets a small, code-prepared question plus the exact
rows it needs, and returns reasoning (hypotheses, mechanisms, disagreements, novel findings), which code then checks
against the data. Nothing built; this is the role definition to agree first.

## Update: the exhaustion/D priming is decoupled from Granite (Greg: "Decouple frankie from this part then")
The `teach` stage is now code only: the facts are filed whole under `work/teach/` (schema FRANKIE_BOX_TEACH_PRIMING_V1,
model_calls 0), and the brain and docs carry them. Nothing needs rerunning:
- the only completed principal run (20211003 cycle 00, `root/cycle-00-response`) never ran the teach-back or the classroom;
- the Monday runs never reached the principal.

The rest of the Granite table waits on Greg. Next chat: `DROP_IN_20260928_GRANITE_DECOUPLE.md`.

## Update: the build plan is the reference; unwired what is not in it (end of chat)
**BUILD PLAN (reference for what runs): `research/kalshi/frankie_boss/artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`.**
- Sheets: Read Me, Build Plans (A, B0, B1, B2_GATED), Components C01-C35, Roadmap, Experiment Arms, Gates, Sources, Preservation Audit, Change Log R4.
- Granite in the plan:
  - C35: Frankie's engine for the reading and the writing of his four files;
  - C21-C24: the shadow critic, under a closed schema.
- The classroom in the plan: C14/D5, the governed 19-dimension classroom with its 171 pairs, training-only.

Unwired in commit 77948797, because each was added after R4:
- the classroom scientific dialogue and the teacher discussion (config `classroom_scientific_dialogue: false`);
- the joined teacher (`JOINED` refused);
- the Granite teach-back (now code priming);
- Jev and the CLM sidecar (not dispatched).

Greg: rerun the Frankie part AND the classroom as r10. The step-by-step work instructions are in `DROP_IN_20260928_GRANITE_DECOUPLE.md`.

## Update 2026-09-29: Granite ONLY in its original build-plan roles. READ `SPEC-decouple-granite.md` FIRST
Greg: "we want the roles we originally gave it, but only there."
- The kept roles, from the Excel build plan R4:
  - C35: Frankie's engine for reading the delivered evidence and writing the four files;
  - C21-C24: the B2 shadow critic under a closed schema;
  - C14: the governed classroom, answered through C35.
- Decoupled everywhere else:
  - the teach-back is code;
  - the scientific dialogue, teacher discussion and joined teacher are unwired;
  - Jev and the CLM sidecar are not dispatched;
  - the experiment's Granite pass is removed.
- r10 uses only those roles, so it is not held.
- The spec is a draft Greg may still tweak in the next chat. It supersedes the first draft of that file (full decoupling).
- Also this chat:
  - the experiment orchestrator spec (`SPEC-experiment-orchestrator.md`), with the classroom arm on the first and the last two discovery days;
  - the per-cycle calculation export (f751ccbe, `frankie_box_export_calcs.sh`).
