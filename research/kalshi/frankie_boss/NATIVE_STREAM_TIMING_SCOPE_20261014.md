# Native provenance and the single small timing run

Status: source-built provenance; runtime unverified; AWS start NOT authorized.
This is the scope for Greg's next timing decision, not a launch instruction.
The operational state and saved-day paths remain in CODEX_HANDOFF_20261014_SESSION13.md.

## Recovery and joined-evidence requirement

Greg clarified on October 14 ET that ALL 99 planes and the teacher's second set
must stay pinned together as they are now: the same original event flow, row
keys, source cursors, causal clocks, plane references and book/flow values.
Earlier computation must preserve that joined picture through publication and
recovery. Pending calculations retain their pending state and actual availability.

Recovery includes a process that is one-third through its calculations or output.
Retain intermediate calculations, running totals, unfinished groups and horizons,
partial output bytes, returned worker results and exact read/write positions.
Continue the same process from its saved progress, using the existing save hooks;
neither completion of a stage nor a selected time/group cutoff is a prerequisite
for recovery. A status sentence saying outputs were saved is not a replacement
for the actual partial state. Preserve retained attempts and source data.

The current source adds partial continuation inside the second-set book-record
writer using `parallel_teacher._save_raw_state`: each produced row's joined
planes/book output and running calculation carry are saved at one matching
position. Resume reads the saved extent and continues at the next row. Complete
parts also retain their carry. Interrupted output generations are retained, and
an unacknowledged suffix is preserved when a new write generation is needed.
This saves progress within a part; it does not serialize the interpreter in the
middle of an individual row's arithmetic or pickle write.

The classroom's existing segment saves now persist each returned in-order portion
without waiting for the former 120-second interval. They remain after a sub-step
returns, covering the gap before the enclosing phase is saved. This does not yet
establish persistence inside every worker calculation or for every out-of-order
result. Legacy ROOT already saves open groups, binner, pending rows and spool
positions. New member-bound native runs now reuse the full-driver save and the
existing open-group adapter serializer, with an explicit partial checkpoint
schema. Requested saves occur after the current INPUT returns; all instruments'
unfinished groups, calculator objects, ledger extents and original input position
are retained without reading forward to a group close. Restore verifies the full
state and its adapter witness. The previous format remains readable; old
journal-stamped attempts keep their original closed-group route.

This is cooperative saved-state recovery, not a claim that every interrupted CPU
instruction or unfinished file write is restartable. Sequential ingest recovery,
temporary-EOF consumers and worker-internal/out-of-order result retention still
need their remaining gaps addressed. Do not describe recovery as pipeline-wide
complete. These changes have source/syntax review only, with no runtime claim.

## The hash dependency

New fresh sequential compact ingests with prepared INPUTs use
`FRANKIE_NATIVE_DBN_MEMBER_PROVENANCE_V1`. Each native row names
`dbn:<trading_day>:<original member_key>` and carries that physical DBN member's
already-verified SHA-256. The day prefix is necessary: the pinned native driver
reads the first date in the object name. Letting the preceding UTC partition's
filename supply that date would change the existing source-day interpretation.

The original INPUT envelope is checked while in hand against its global cursor,
member index, member name and scope genesis. Its observation is spooled unchanged.
Member selection on native recovery starts at the saved global INPUT count;
manifest counts are the selected trading-day takes, not entire UTC partitions.
The original manifest also binds the tail skips and partial-member cuts.

The prepared descriptor, ingestion receipt, ROOT policy, native continuation,
native result and teacher artifact selection carry the same policy. Full-state
recovery compares the data policy exactly, including the source order and counts.
The completed native receipt separately binds the physical journal's path,
bytes, SHA-256, entry count and chain head to the completed ROOT source.

This deliberately changes NEW native evidence identities. It is not claimed to
reproduce journal-stamped row hashes. The byte-identical faster evidence encoder
is a separate change: its hash formula still must compare exactly in shadow mode.
No market operand, reduction order, group rule or scientific producer is changed
by the provenance selection. Numerical equivalence is not established by source
inspection and remains for the authorized run.

An ingestion receipt without this policy stays journal-stamped. Existing prepared
spools, parallel ingests, old receipts and the saved a2 attempt are not migrated.
The full manifest count is never replaced by an expanding prefix denominator.

## What must exist before the combined timing run can launch

The per-record final-journal-hash dependency is removed for the new policy.
The production entry points still require whole-day completion. The following
continuation wiring remains source work, not a deployed streaming capability:

- Ingest must drain its pending encoders and commit the journal and exact INPUT
  extent before publishing a prefix. The first notification is at 30 minutes of
  receive-clock data coverage, followed by committed increments. A checkpoint
  descriptor alone is not an event notification or a conformant source.
- ROOT must hold one native/legacy state across temporary EOF, consume each new
  INPUT once, preserve all instruments' pending groups and calculator horizons,
  and save/resume at its original cursor without replaying the accumulated prefix.
  Wire the existing partial-calculation saves; do not add timed recovery gates.
  A single instrument's F_LAST cannot stand in for closure of every open group.
- The shared-picture/teacher route must read committed calculation segments with
  their actual availability, retaining pending producers as pending. Final native
  projections and day completion still require true EOF. A running native producer
  cannot be renamed absent to let a complete-picture lesson pass.

In particular, `calculate_day`, `load_prepared` and `bedrock.run` still require
the completed source; `experiment_native.selected_files` selects completed
artifacts. Do not remove those checks to manufacture a streaming demonstration.
The existing teacher-to-classroom sealed-block route does not prove raw-to-ROOT
streaming. No unused alternate frontier framework has been installed.

## Fixed timing scope

One attended AWS session on the existing main box, after the continuation wiring
above and Greg's explicit go. Two bounded legs in that same session:

| Leg | Data and work | Stop boundary | What it measures |
| --- | --- | --- | --- |
| Classroom gauge | Existing 20231018 sealed block 1, 1,588 rows, complete classroom plus external section, one lesson at a time, evidence encoding shadow | One block-1 session | Existing comparable gauge, hash-byte equality, per-step time, memory, external-key reuse and write-once store |
| Ingest/ROOT continuation | Original 20231018 opening state and contiguous first 35 receive-clock minutes, every original record/field in order, first readiness at 30 minutes | Cooperative save of actual in-progress calculations and output; no true-day EOF or native finalization | Actual new ingestion preparation, member stamping, first-frontier startup, increment consumption, partial-state save/restore and available teacher evidence |

Measure coverage from the first accepted INPUT receive clock, using the original
cursor order and its receive-clock high-water mark; late arrivals are never
sorted into an earlier prefix. The 35-minute extent is a timing boundary, not a new trading day and not a
completed-source manifest. These are readiness/measurement markers, never the
only permitted recovery positions. Preserve the next unread original cursor, pending
instrument groups and unresolved horizons at the stop. If a safe save cannot
preserve them at that exact prefix, fix that source capability before launch;
do not silently extend the slice until a convenient group closes. Request one
save during active partial work, reopen that same saved position, and continue
within the 35-minute measurement extent; no mandatory stop at exactly 30 minutes
and no recomputation of the already calculated prefix. No success claim from an empty or already-complete
resume. Existing teacher block-1 work may start earlier when its own inputs exist.

Use the full original manifest as the identity and progress denominator. Source
verification/decompression and opening-book preparation may read the required
original DBN members; report that setup separately from prefix calculation time.
It is not permission to calculate the rest of the day. In particular the existing
CLI `--canary-records` cannot substitute: it neither prepares the new spool nor
runs the continuing native/legacy path, and an arbitrary row cap can split groups.

Keep all outputs under a new owner directory beneath
`/opt/frankie-box/work/timing-native-20261014-<commit>/`. The gauge uses its own
subdirectory, never the production classroom directory. Existing teacher rows,
ingest, brain knowledge and opening state are read-only inputs. No queue resume,
whole-day teacher second set, day-end classroom, Jev, exchange, meeting, school,
full-day reports, additional day or fleet dispatch is part of this session.

Use a 30-minute wall-work budget for the combined timing work, recorded before
launch. At the budget, retain the original stop/checkpoint state and report the
unfinished measurement; do not widen the scope or keep the box running to chase
a result. The runner must have a source-reviewed cooperative stop path and
an independent box-stop safeguard before launch. Monitor throughout and stop
the box promptly on completion, failure, loss of visibility or budget exhaustion.
Boot/deploy preparation is reported separately and is attended as well.

## Measurements from that one run

- Block-1 wall and session seconds, per-step times, peak RSS, and success of the
  classroom and external section. Shadow legacy/candidate encoding times and
  comparisons remain separate from the end-to-end wall time. Do not present
  wall time minus comparison counters as a measured fast-only end-to-end result.
- Source setup, ingest, spool publication, first native/legacy work and teacher
  availability times; original cursors, journal counts/heads and spool extents
  at both committed frontiers; completed/consumed counts before and after resume.
- Original member SHA and trading-day identity before/after seek, matching market
  fields, unchanged selected policy, carried open groups/horizons, and no duplicate
  INPUT consumption. The run cannot validate a DBN member seam it never reaches;
  the small first-35-minute slice is not proof of all-day seam behavior.
- Exact encoder shadow equality on the actual processed values. Keep native
  provenance identity changes explicit; never strip arbitrary differences and
  call the complete evidence byte-identical.

This prefix leg cannot certify whole-day terminal reconciliation or performance
on all 99 planes at true EOF. Those require the later separately authorized
complete-day work. No speedup percentage or full-day cost estimate is established.

## Existing gauge command (only inside the authorized session)

The classroom leg already has an entry point. The source-continuation leg does
not yet have a runnable production command; that is a launch blocker, not grounds
to fall back to `ACTION=resume` on a2. Bind the staged checkout and fresh timing
owner first, then the existing gauge invocation is:

```bash
python3 deploy/aws/box/frankie_box_block_gauge.py \
  --rows-dir /opt/frankie-box/work/experiment-teacher-rows/20231018 \
  --ingest-dir /opt/frankie-box/work/ingest-20231018-gh-36571235912-1 \
  --day 20231018 --block 1 --evidence-encoding shadow \
  --out "$TIMING_OWNER/classroom-gauge"
```

Use the box venv, held CPU booking and SSM/systemd execution route in the handoff.
Before measuring, restore the recorded disk run settings and enable the retained
swapfile as required there. Those AWS actions and any stop safeguard are future
launch work, not performed or authorized by this source scope.
