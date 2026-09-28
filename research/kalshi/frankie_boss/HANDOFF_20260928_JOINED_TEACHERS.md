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
