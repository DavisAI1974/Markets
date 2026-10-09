# Hub calc-order map (2026-10-09, session 12)

Greg's question: "We might have to rearrange some of our calc steps on the data calc parts." This document is the map
that answers it: who computes what, from what, in which order, on which clock, what is computed more than once, which
step reads something that only exists later, and what the order would be under the HUB DESIGN at the top of CLAUDE.md
(one teacher core, one ingestion stream, spokes ROOT, teacher, classroom, exchange, Jev, school, forecaster, one turn
lock, additions only, base by reference, a second lap only when a piece has something new).

Scope and method. Read-only. No code was edited, nothing was run on AWS or the box. The starting edge list is
`NATIVE_INPUTS` in `deploy/aws/box/frankie_box_hub_spokes.py` (177 native inputs over six consumers; the forecaster has
none). Every one of its anchors was located in the code it cites (`python3 frankie_box_hub_spokes.py` prints
`reads_at` for each: 177 of 177 found, 0 "anchor not found"), and the readers were then read to add the edges the
inventory does not carry (section 1.3) and to list the calc steps (section 2). Branch `ccr-d2f8f826-iefeah-frankie` at
533f42cd.

Labels used throughout:
- FINDING: read from the code, with file:line. Not checked against bytes on the box unless said so.
- PROPOSAL: a suggested order or move for Greg to decide. Nothing in this document changes the a2/20231018 day.
- [SEALED]: the step is deterministic from the sealed base plus whole-day outputs of pieces before it in the CURRENT
  order that are themselves deterministic (ROOT, the BOSS teacher walk): it could run under the hub's one-pass base.
- [ADDS:x]: the step needs piece x's additions of the same day: it must wait for x's turn.
- [CROSS-DAY]: the step needs an earlier day's additions (the classroom chain).
- [MODEL]: the step calls a model (Granite); its output is not a function of the sealed data alone.

## 0. The answer in brief

FINDING. The code's order is a DAG at step level but NOT at piece level: the "teacher" piece as the hub defines it
(the BOSS rows, the teacher key, the account, and the scientific seat's search and lessons, `publications('teacher')`
in frankie_box_hub_spokes.py:857-890) has one part that must run BEFORE the classroom (the BOSS walk, the key, the
second set) and one part that can only run AFTER it (the tests of Frankie's novel findings, which read his
`ledgers.json`). That is the one real cycle (C1, teacher <-> classroom). A second cycle (C2, exchange <-> Jev) exists in
the code's selection rules but is never satisfied on the current day (the exchange admits same-day Jev material that
the CPU Jev route only writes after the exchange). Everything else is a straight line.

FINDING. The search (data export, search, search review) has NO data dependency on the classroom: it reads the ROOT, the
sealed ingest, the day file and the BOSS teacher rows only. It runs after the classroom today by Greg's settled learning
order (frankie_box_frankie_queue.py:1236-1246), not by a data edge, and the classroom's own reader walls the same-day
search and lessons by stage (frankie_box_lane_state.py:369-385), so computing the search earlier changes nothing
Frankie sees.

FINDING. The teacher key "built three times" is built by the SAME code in the first two places: Run.teacher_knowledge
and the classroom package both call `dipole_classroom.build_teacher_key` on the snapshot made by the same
`snapshot_teacher_attachment` call with the same arguments, and both re-pin with
`dipole_classroom_integration._repin_teacher_key_correlations`. The classroom V2 does NOT use the "hardened"
correlations: `dipole_classroom_hardening._harden_teacher_key_correlations` is called only by test-path builders
(`prepare_hardened_cycle`, `prepare_final_cycle`), and its body is AST-identical to `_repin` (checked: docstrings removed,
the two function bodies parse to the same tree). Both re-pins are identities on a core-built key (the core `_pearson`
already applies the same floor of 8). The third (the exchange) recomputes the same per-pair values with the same
functions for the claimed pairs only. The expected outputs are equal; the only differences are form and scope
(section 3, D1). The "two different correlation re-pins" the drop-in names as a science question are, in the code, one.

PROPOSAL (section 6). Under the hub: ROOT, then the teacher's first turn (everything deterministic from sealed data,
the search included, plus the steps section 6 moves in from the classroom, exchange and Jev), then the classroom, then a SECOND
teacher turn inside the same lap (Frankie's findings tested, the novelty investigation), then exchange, Jev, school.
Minimum laps to the content fixed point: 2 (one working lap and the confirming lap the hub core always needs). With
today's fixed one-turn-per-piece order it is 3, and 4 if same-day Jev claims are to reach the same-day exchange.

FINDING (section 5, flow shapes). Not one size fits all: ROOT, the digest render and the teacher's pinned publication
are ONE-WAY OUT; the classroom, data, search, frankie_lessons and the school are ONE ROUND TRIP within a day; the
reports and the forecaster stub are ONE-WAY IN; the Granite meeting is ONE-WAY on the day (nothing computes on it the
same day; one cross-day path into later classrooms' knowledge check is open, section 5); ITERATING are the teacher as
the hub piece (teacher <-> classroom, one extra turn) and, latently, the exchange and Jev (exchange <-> Jev) and the
batch lessons through a plan jev_stamp.

## 1. The dependency graph

### 1.1 The pieces and the order the code runs them today

FINDING (the day's chain on the ROOT line, frankie_box_frankie_queue.py `_finish_steps` 1908 and `class_day` 1236):

1. ingest and the day file (sealed base; frankie_box_experiment.py `ingest` 1793, `external` 2225).
2. ROOT (frankie_box_experiment.py `root` 1892 -> frankie_box_experiment_root.py `_calculate_day` 506). The digest
   render runs beside the teacher in the same booking (frankie_box_render_digest.py); the class door waits for it
   (frankie_box_experiment.py `await_digest` 2772).
3. BOSS teacher (frankie_box_frankie_queue.py:1931 `run.teacher` -> frankie_box_experiment.py `teacher` 4570 ->
   frankie_box_experiment_teacher.py `_teach` 1267), then on the orchestrator `teacher_knowledge` 4930,
   `teacher_account_entry` 5054, `teacher_second_set_entry` 5014.
4. The class line in the same slot, `CLASS_STAGES` (frankie_box_frankie_queue.py:138): classroom (1286), data and search
   (1297), batch lessons (1315), frankie_lessons (1332), exchange, voice, school, reports (1338).
5. Jev after the class line (frankie_box_frankie_queue.py:2097), then a reports revision when Jev's late pieces make
   them stale (2106-2116).
6. Forecaster: no consumer (frankie_box_hub_spokes.py:442).

Outside the seven pieces but in the chain: the survivors update at a discovery batch boundary
(frankie_box_experiment.py `survivors` 5407), the accumulated lessons of non-arm days (`accumulated_lessons` 5284), the
day reports (`reports` 2951) and the one-day inspection (`inspect_day` 3137).

### 1.2 Edge table (the inventory's 177 native inputs, verified)

Columns: the producer piece, the artifact, the clock it carries (one of the seven causal clocks, a cutoff, or "sealed
base"), whether the producer COMPUTED it or it is PASSED through (a reference to a sealed base file, or an entry that
only references other files), and where the consumer reads it (found now). MECHANISM rows (claims caches, settings,
control files, model runtime) and OWN rows (the piece's own resume state) are listed, never part of the data graph.

The seven causal clocks (frankie_box_all99_coverage.py:143-149; how the classroom places them,
frankie_box_classroom_code.py:2279-2285): clock_event_time (at.ts_event_ns), clock_receive_time (at.ts_recv_ns),
clock_event_known_by (the publication frontier, a running max of the receive clock), clock_feature_availability (each
update's known_at_ns), clock_prospective_discovery_confirmation (native lifecycle recognition records),
clock_model_evaluation (the native member clock row), clock_lock_time (stamped by the consumer: its as_of and
through_cursor). Every cutoff in today's workflow is the WHOLE DAY: through_cursor = record_count - 1 everywhere; the
time cutoff (as_of) is the teacher's last row receive time (frankie_box_experiment_teacher.py:1863, and `lock` at 800),
carried unchanged by the classroom binding, the exchange and Jev. Two readers use the day's HALT instead (section 4,
W1).

#### Consumer: root (14 native inputs in the inventory)

| # | Producer | Artifact | Clock | Computed / passed | Read at |
|---|---|---|---|---|---|
| 1 | ingest (sealed base) | ingestion receipt (BOSS_BLOCK_INGESTION_RECEIPT_V1) | sealed base (record_count, journal_hash) | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_root.py:535` |
| 2 | ingest (sealed base) | sealed journal (compact) | sealed base; each record carries event / receive clocks | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_root.py:569` |
| 3 | ingest (sealed base) | opening book beside the journal (opening_book_file) | sealed base (the prior day's halt book) | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_root.py:555` |
| 4 | ingest (sealed base) | seeded opening book record (prior day's closing book, receipt.opening_book) | sealed base (the prior day's halt book) | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_root.py:562` |
| 5 | ingest (sealed base) | completion.json (sealed day completion) | sealed base | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_root.py:579` |
| 6 | day-external (sealed base) | day-external.json (the 13 historical points) | sealed base; each point event_time / known_by, read AS-OF the reader's cutoff | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_root.py:593` |
| 7 | day-external (sealed base) | day-external-receipt.json | sealed base | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_root.py:591` |
| 8 | repository (sealed base) | day source manifest (blocks/BLOCK_<day>_SOURCE_MANIFEST.json) | sealed base (repository) | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_root.py:438` |
| 9 | survivors stage | frozen survivors (a confirmation day only) | sealed (frozen list; confirmation days) | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_root.py:523` |
| 10 | ingest (sealed base) | ingest file-claims.jsonl (journal witness by claim) | - | MECHANISM | `deploy/aws/box/frankie_box_experiment_root.py:381` |
| 11 | orchestrator | run settings (day role, data workers, digest, bedrock, shared market policy) | - | MECHANISM | `deploy/aws/box/frankie_box_experiment_root.py:927` |
| 12 | orchestrator | lane stop file (FRANKIE_LANE_STOP_FILE) | - | MECHANISM | `deploy/aws/box/frankie_box_experiment_root.py:351` |
| 13 | ROOT | retained derive.json / legacy-stage.json / spools (resume) | own resume state | OWN | `deploy/aws/box/frankie_box_experiment_root.py:741` |
| 14 | ROOT | retained work/file-claims.jsonl (resume) | own resume state | OWN | `deploy/aws/box/frankie_box_experiment_root.py:749` |

#### Consumer: teacher (22 native inputs in the inventory)

| # | Producer | Artifact | Clock | Computed / passed | Read at |
|---|---|---|---|---|---|
| 15 | ingest (sealed base) | ingestion receipt | sealed base (record_count, journal_hash) | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_teacher.py:1305` |
| 16 | ingest (sealed base) | sealed journal (compact; the raw walk) | sealed base; each record carries event / receive clocks | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_teacher.py:1431` |
| 17 | day-external (sealed base) | day-external.json (resolved beside the sealed ingest) | sealed base; each point event_time / known_by, read AS-OF the reader's cutoff | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_teacher.py:1290` |
| 18 | day-external (sealed base) | day-external-receipt.json (the day file's sha256) | sealed base | PASSED (sealed) | `research/kalshi/frankie_boss/dipole_classroom_external.py:273` |
| 19 | repository (sealed base) | experiment directive (EXPERIMENT_DIRECTIVE_V1.json) | sealed base (repository) | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_teacher.py:55` |
| 20 | ROOT | ROOT source-binding.json (through SharedMarketTimeline) | whole day (through record_count-1); identity | COMPUTED (ROOT identity record) | `deploy/aws/box/frankie_box_market_timeline.py:730` |
| 21 | ROOT | ROOT calculations-receipt.json (through SharedMarketTimeline) | whole day; pins of every ROOT output | COMPUTED (ROOT) | `deploy/aws/box/frankie_box_market_timeline.py:743` |
| 22 | ROOT | ROOT derive.json (through SharedMarketTimeline) | whole day (completed derivation) | COMPUTED (ROOT) | `deploy/aws/box/frankie_box_market_timeline.py:747` |
| 23 | ROOT | ROOT frames spool (work/derived/.rows/frames.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 24 | ROOT | ROOT prices spool (work/derived/.rows/prices.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 25 | ROOT | ROOT structures spool (work/derived/.rows/structures.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 26 | ROOT | ROOT native ledger exact_member_rows.jsonl (through SharedMarketTimeline) | per row; carries clock_model_evaluation | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 27 | ROOT | ROOT native ledger exact_lifecycle_rows.jsonl (through SharedMarketTimeline) | per row; carries clock_prospective_discovery_confirmation | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 28 | ROOT | ROOT native ledger legacy_observable_rows.jsonl (through SharedMarketTimeline) | per row (event / receive) | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 29 | ROOT | ROOT native result.json (through SharedMarketTimeline) | whole day | COMPUTED (ROOT native) | `deploy/aws/box/frankie_box_experiment_native.py:316` |
| 30 | ROOT | ROOT native section bedrock_section_4_2.json.gz (through SharedMarketTimeline) | completed-only (post-stream, never backfilled into a picture) | COMPUTED (ROOT native projection) | `deploy/aws/box/frankie_box_experiment_native.py:317` |
| 31 | ROOT | ROOT native section bedrock_section_4_4.json.gz (through SharedMarketTimeline) | completed-only (post-stream, never backfilled into a picture) | COMPUTED (ROOT native projection) | `deploy/aws/box/frankie_box_experiment_native.py:317` |
| 32 | day-external (sealed base) | day file publications (the external layer) (through SharedMarketTimeline) | each publication at its known_by, in the picture of its cursor | PASSED (sealed day file, by the source-binding pin) | `deploy/aws/box/frankie_box_market_timeline.py:805` |
| 33 | ROOT | ROOT work/file-claims.jsonl (stream claims) (through SharedMarketTimeline) | - | MECHANISM | `deploy/aws/box/frankie_box_market_timeline.py:767` |
| 34 | ingest (sealed base) | ingest file-claims.jsonl (journal prefetch by claim) | - | MECHANISM | `deploy/aws/box/frankie_box_experiment_teacher.py:1286` |
| 35 | environment | native cutoff limits (FRANKIE_NATIVE_CUTOFF_*) | - | MECHANISM | `deploy/aws/box/frankie_box_experiment_teacher.py:1468` |
| 36 | teacher (BOSS) | retained teacher receipt / raw state / walk cache / carry / tracker (resume) | own resume state | OWN | `deploy/aws/box/frankie_box_experiment_teacher.py:1351` |

#### Consumer: classroom (44 native inputs in the inventory)

| # | Producer | Artifact | Clock | Computed / passed | Read at |
|---|---|---|---|---|---|
| 37 | ROOT | ROOT calculations-receipt.json | whole day; pins of every ROOT output | COMPUTED (ROOT) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:622` |
| 38 | ROOT | ROOT source-binding.json | whole day (through record_count-1); identity | COMPUTED (ROOT identity record) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:625` |
| 39 | ingest (sealed base) | sealed journal (witness: the source binding's container pin) | sealed base; each record carries event / receive clocks | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:636` |
| 40 | ROOT | Frankie's full-depth digest (work/derivation-digest-full.md; into his brain entry) | whole day (rendered from the retained layers) | COMPUTED (ROOT digest render) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:678` |
| 41 | teacher (BOSS) | teacher receipt.json | as_of = max teacher row receive time (clock_lock_time); through_cursor = record_count-1 | COMPUTED (teacher) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:686` |
| 42 | teacher (BOSS) | teacher-attachment.pkl (the classroom package source) | teacher as_of / through_cursor | COMPUTED (teacher row pass + finish) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:692` |
| 43 | teacher (BOSS) | teacher receipt shared_market_identity / shared_market_read (identity check) | identity (the ROOT the teacher read) | COMPUTED (teacher) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:736` |
| 44 | day-external (sealed base) | day-external.json | sealed base; each point event_time / known_by, read AS-OF the reader's cutoff | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:697` |
| 45 | day-external (sealed base) | day-external-receipt.json | sealed base | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:769` |
| 46 | teacher (BOSS) | teacher external section (external-section/host-dipole-external-section.json) | cutoff_ns = teacher as_of (not the halt) | COMPUTED (teacher) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:948` |
| 47 | teacher (BOSS) | teacher external section receipt (external-section/receipt.json) | cutoff_ns = teacher as_of (not the halt) | COMPUTED (teacher) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:948` |
| 48 | teacher (BOSS) | teacher classroom-carry.pkl (the walk's anchor pictures) | per picture of the teacher walk; identity | COMPUTED (Frankie's code on the teacher walk) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:305` |
| 49 | ROOT | ROOT source-binding.json (through SharedMarketTimeline) | whole day (through record_count-1); identity | COMPUTED (ROOT identity record) | `deploy/aws/box/frankie_box_market_timeline.py:730` |
| 50 | ROOT | ROOT calculations-receipt.json (through SharedMarketTimeline) | whole day; pins of every ROOT output | COMPUTED (ROOT) | `deploy/aws/box/frankie_box_market_timeline.py:743` |
| 51 | ROOT | ROOT derive.json (through SharedMarketTimeline) | whole day (completed derivation) | COMPUTED (ROOT) | `deploy/aws/box/frankie_box_market_timeline.py:747` |
| 52 | ROOT | ROOT frames spool (work/derived/.rows/frames.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 53 | ROOT | ROOT prices spool (work/derived/.rows/prices.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 54 | ROOT | ROOT structures spool (work/derived/.rows/structures.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 55 | ROOT | ROOT native ledger exact_member_rows.jsonl (through SharedMarketTimeline) | per row; carries clock_model_evaluation | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 56 | ROOT | ROOT native ledger exact_lifecycle_rows.jsonl (through SharedMarketTimeline) | per row; carries clock_prospective_discovery_confirmation | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 57 | ROOT | ROOT native ledger legacy_observable_rows.jsonl (through SharedMarketTimeline) | per row (event / receive) | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 58 | ROOT | ROOT native result.json (through SharedMarketTimeline) | whole day | COMPUTED (ROOT native) | `deploy/aws/box/frankie_box_experiment_native.py:316` |
| 59 | ROOT | ROOT native section bedrock_section_4_2.json.gz (through SharedMarketTimeline) | completed-only (post-stream, never backfilled into a picture) | COMPUTED (ROOT native projection) | `deploy/aws/box/frankie_box_experiment_native.py:317` |
| 60 | ROOT | ROOT native section bedrock_section_4_4.json.gz (through SharedMarketTimeline) | completed-only (post-stream, never backfilled into a picture) | COMPUTED (ROOT native projection) | `deploy/aws/box/frankie_box_experiment_native.py:317` |
| 61 | day-external (sealed base) | day file publications (the external layer) (through SharedMarketTimeline) | each publication at its known_by, in the picture of its cursor | PASSED (sealed day file, by the source-binding pin) | `deploy/aws/box/frankie_box_market_timeline.py:805` |
| 62 | ROOT | ROOT work/file-claims.jsonl (stream claims) (through SharedMarketTimeline) | - | MECHANISM | `deploy/aws/box/frankie_box_market_timeline.py:767` |
| 63 | teacher (BOSS) | teacher rows sidecar (the second set, row by row) | per row: key + the seven clocks matched to the picture; lock = teacher as_of | COMPUTED (teacher) | `deploy/aws/box/frankie_box_classroom_code.py:774` |
| 64 | teacher (BOSS) | teacher account (teacher-account.json) | whole day (teacher as_of) | COMPUTED (teacher findings) | `deploy/aws/box/frankie_box_classroom_code.py:835` |
| 65 | teacher (BOSS) | teacher account report (teacher-account.md) | whole day (teacher as_of) | COMPUTED (teacher findings) | `deploy/aws/box/frankie_box_classroom_code.py:835` |
| 66 | repository (sealed base) | classroom rules (CLASSROOM_RULES_V3.json) | sealed base (repository) | PASSED (sealed) | `deploy/aws/box/frankie_box_classroom_code.py:238` |
| 67 | repository (sealed base) | experiment directive | sealed base (repository) | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:206` |
| 68 | brain (every writer of entries) | brain entries (learner_knowledge, stage classroom) | day + stage wall (DAY_KINDS) | PASSED (entries by manifest pin) | `deploy/aws/box/frankie_box_lane_state.py:377` |
| 69 | school (earlier days) | brain school days (learner_school: earlier days) | day + stage wall (DAY_KINDS) | PASSED (entries by manifest pin) | `deploy/aws/box/frankie_box_lane_state.py:615` |
| 70 | school (earlier days) | brain school index (school/index.json) | append-only index of earlier days | PASSED (index) | `deploy/aws/box/frankie_box_brain.py:493` |
| 71 | review (corrections) | brain correction records (corrections/*.json) | when filed (reaches a reader at its boundary) | COMPUTED (review) | `deploy/aws/box/frankie_box_experiment_review.py:771` |
| 72 | lane state (peer versions) | knowledge versions (lane-state/knowledge/*/version.json) | peer versions at the boundary | PASSED (lane state) | `deploy/aws/box/frankie_box_lane_state.py:225` |
| 73 | brain (every writer of entries) | frozen learned structure manifest (exhaustion/D facts) | sealed (frozen) | PASSED (frozen) | `deploy/aws/box/frankie_box_classroom_code.py:2858` |
| 74 | classroom (d-1) | previous classroom day history.json (carry) | the previous classroom day's completion (cross-day) | COMPUTED (classroom d-1) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:785` |
| 75 | classroom (d-1) | previous classroom day post-grade.json (carry) | the previous classroom day's completion (cross-day) | COMPUTED (classroom d-1) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:786` |
| 76 | classroom (d-1) | previous classroom day external-history.json (carry) | the previous classroom day's completion (cross-day) | COMPUTED (classroom d-1) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:790` |
| 77 | classroom (d-1) | previous classroom day external-post-grade.json (carry) | the previous classroom day's completion (cross-day) | COMPUTED (classroom d-1) | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:791` |
| 78 | ingest (sealed base) | ingest file-claims.jsonl (journal witness by claim) | - | MECHANISM | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:648` |
| 79 | environment | native cutoff limits (FRANKIE_NATIVE_CUTOFF_*) | - | MECHANISM | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:1020` |
| 80 | classroom | retained phase state / side saves / journal-witness.json (resume) | own resume state | OWN | `deploy/aws/box/frankie_box_experiment_classroom_v2.py:681` |

#### Consumer: exchange (34 native inputs in the inventory)

| # | Producer | Artifact | Clock | Computed / passed | Read at |
|---|---|---|---|---|---|
| 81 | teacher (BOSS) | teacher rows (host-dipole-classroom-source.c15.json) | per row ts_recv_ns; snapshot as_of = teacher as_of | COMPUTED (teacher snapshot) | `deploy/aws/box/frankie_box_experiment_exchange.py:649` |
| 82 | teacher (BOSS) | teacher receipt.json (the cutoff: as_of / through_cursor, shared identity) | as_of = max teacher row receive time (clock_lock_time); through_cursor = record_count-1 | COMPUTED (teacher) | `deploy/aws/box/frankie_box_adviser_market.py:2106` |
| 83 | ingest (sealed base) | ingestion receipt (source_prefix_hash for the cutoff scope) | sealed base (record_count, journal_hash) | PASSED (sealed) | `deploy/aws/box/frankie_box_adviser_market.py:2120` |
| 84 | teacher (BOSS) | teacher-kept cutoff context (shared-market-context.json beside the teacher receipt) | scope = teacher as_of / through_cursor | COMPUTED (teacher walk: CutoffTracker) | `deploy/aws/box/frankie_box_adviser_market.py:2134` |
| 85 | ROOT | ROOT source-binding.json (through SharedMarketTimeline) | whole day (through record_count-1); identity | COMPUTED (ROOT identity record) | `deploy/aws/box/frankie_box_market_timeline.py:730` |
| 86 | ROOT | ROOT calculations-receipt.json (through SharedMarketTimeline) | whole day; pins of every ROOT output | COMPUTED (ROOT) | `deploy/aws/box/frankie_box_market_timeline.py:743` |
| 87 | ROOT | ROOT derive.json (through SharedMarketTimeline) | whole day (completed derivation) | COMPUTED (ROOT) | `deploy/aws/box/frankie_box_market_timeline.py:747` |
| 88 | ROOT | ROOT frames spool (work/derived/.rows/frames.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 89 | ROOT | ROOT prices spool (work/derived/.rows/prices.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 90 | ROOT | ROOT structures spool (work/derived/.rows/structures.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 91 | ROOT | ROOT native ledger exact_member_rows.jsonl (through SharedMarketTimeline) | per row; carries clock_model_evaluation | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 92 | ROOT | ROOT native ledger exact_lifecycle_rows.jsonl (through SharedMarketTimeline) | per row; carries clock_prospective_discovery_confirmation | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 93 | ROOT | ROOT native ledger legacy_observable_rows.jsonl (through SharedMarketTimeline) | per row (event / receive) | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 94 | ROOT | ROOT native result.json (through SharedMarketTimeline) | whole day | COMPUTED (ROOT native) | `deploy/aws/box/frankie_box_experiment_native.py:316` |
| 95 | ROOT | ROOT native section bedrock_section_4_2.json.gz (through SharedMarketTimeline) | completed-only (post-stream, never backfilled into a picture) | COMPUTED (ROOT native projection) | `deploy/aws/box/frankie_box_experiment_native.py:317` |
| 96 | ROOT | ROOT native section bedrock_section_4_4.json.gz (through SharedMarketTimeline) | completed-only (post-stream, never backfilled into a picture) | COMPUTED (ROOT native projection) | `deploy/aws/box/frankie_box_experiment_native.py:317` |
| 97 | day-external (sealed base) | day file publications (the external layer) (through SharedMarketTimeline) | each publication at its known_by, in the picture of its cursor | PASSED (sealed day file, by the source-binding pin) | `deploy/aws/box/frankie_box_market_timeline.py:805` |
| 98 | ROOT | ROOT work/file-claims.jsonl (stream claims) (through SharedMarketTimeline) | - | MECHANISM | `deploy/aws/box/frankie_box_market_timeline.py:767` |
| 99 | teacher (BOSS) | teacher rows sidecar (second set at the cutoff, leaf ledgers, the reading) | per row: key + the seven clocks matched to the picture; lock = teacher as_of | COMPUTED (teacher) | `deploy/aws/box/frankie_box_experiment_exchange.py:1719` |
| 100 | teacher (BOSS) | teacher-second-set.pkl (the reading: pinned by the receipt) | per row / per event; teacher as_of | COMPUTED (teacher) | `deploy/aws/box/frankie_box_teacher_rows.py:899` |
| 101 | teacher (BOSS) | teacher-state-split.json | per row / per event; teacher as_of | COMPUTED (teacher) | `deploy/aws/box/frankie_box_teacher_rows.py:910` |
| 102 | teacher (BOSS) | teacher-second-set-mismatches.jsonl | per row / per event; teacher as_of | COMPUTED (teacher) | `deploy/aws/box/frankie_box_teacher_rows.py:941` |
| 103 | teacher (BOSS) | teacher-book-event-differences.jsonl | per row / per event; teacher as_of | COMPUTED (teacher) | `deploy/aws/box/frankie_box_teacher_rows.py:945` |
| 104 | teacher (BOSS) | teacher-reconciliation-differences.jsonl | per row / per event; teacher as_of | COMPUTED (teacher) | `deploy/aws/box/frankie_box_teacher_rows.py:946` |
| 105 | teacher (BOSS) | teacher account (in the teacher receipt) | whole day (teacher as_of) | COMPUTED (teacher findings) | `deploy/aws/box/frankie_box_teacher_rows.py:926` |
| 106 | teacher (scientific seat) | current-day lessons (Frankie's FRANKIE_LESSONS_V1) | per discovery day tested; search F_LAST lag axis | COMPUTED (scientific teacher) | `deploy/aws/box/frankie_box_experiment_exchange.py:145` |
| 107 | teacher (scientific seat) | current-day lessons (Jev's) | per discovery day tested; search F_LAST lag axis | COMPUTED (scientific teacher) | `deploy/aws/box/frankie_box_experiment_exchange.py:145` |
| 108 | teacher (scientific seat) | the day's search (MANIFEST.json; accumulated claim tests) | per day F_LAST axis; day file read at halt_ns | COMPUTED (search) | `deploy/aws/box/frankie_box_experiment_exchange.py:2317` |
| 109 | brain (every writer of entries) | brain entries (learner_knowledge, stage exchange) | day + stage wall (DAY_KINDS) | PASSED (entries by manifest pin) | `deploy/aws/box/frankie_box_experiment_exchange.py:365` |
| 110 | school (earlier days) | brain school days (learner_school, stage exchange) | day + stage wall (DAY_KINDS) | PASSED (entries by manifest pin) | `deploy/aws/box/frankie_box_experiment_exchange.py:366` |
| 111 | review (corrections) | brain correction records | when filed (reaches a reader at its boundary) | COMPUTED (review) | `deploy/aws/box/frankie_box_experiment_review.py:771` |
| 112 | repository (sealed base) | classroom rules | sealed base (repository) | PASSED (sealed) | `deploy/aws/box/frankie_box_experiment_exchange.py:2082` |
| 113 | teacher (BOSS) | teacher rows file-claims.jsonl (rows pin by claim) | - | MECHANISM | `deploy/aws/box/frankie_box_experiment_exchange.py:621` |
| 114 | exchange | retained learner-knowledge.json / ledger save / cutoff context (resume) | own resume state | OWN | `deploy/aws/box/frankie_box_experiment_exchange.py:1653` |

#### Consumer: jev (32 native inputs in the inventory)

| # | Producer | Artifact | Clock | Computed / passed | Read at |
|---|---|---|---|---|---|
| 115 | classroom | classroom receipt (work/classroom/receipt.json) | classroom binding as_of / through_cursor (= the teacher's) | COMPUTED (classroom) | `deploy/aws/box/frankie_box_jev_cpu.py:488` |
| 116 | classroom | Jev material (jev-material/classroom-request.json) | classroom binding as_of / through_cursor | COMPUTED (classroom: the model-visible package) | `deploy/aws/box/frankie_box_jev_cpu.py:493` |
| 117 | teacher (scientific seat) | the day's search MANIFEST.json | per day F_LAST axis; day file read at halt_ns | COMPUTED (search) | `deploy/aws/box/frankie_box_jev_cpu.py:499` |
| 118 | exchange | exchange's retained cutoff context (shared-market-context.json) | scope = classroom binding as_of / through_cursor (equal to the teacher cutoff) | PASSED (the teacher-kept context, re-retained by the exchange) | `deploy/aws/box/frankie_box_jev_cpu.py:543` |
| 119 | ROOT | ROOT source-binding.json (through SharedMarketTimeline) | whole day (through record_count-1); identity | COMPUTED (ROOT identity record) | `deploy/aws/box/frankie_box_market_timeline.py:730` |
| 120 | ROOT | ROOT calculations-receipt.json (through SharedMarketTimeline) | whole day; pins of every ROOT output | COMPUTED (ROOT) | `deploy/aws/box/frankie_box_market_timeline.py:743` |
| 121 | ROOT | ROOT derive.json (through SharedMarketTimeline) | whole day (completed derivation) | COMPUTED (ROOT) | `deploy/aws/box/frankie_box_market_timeline.py:747` |
| 122 | ROOT | ROOT frames spool (work/derived/.rows/frames.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 123 | ROOT | ROOT prices spool (work/derived/.rows/prices.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 124 | ROOT | ROOT structures spool (work/derived/.rows/structures.jsonl) (through SharedMarketTimeline) | per row: event, receive, event_known_by (publication frontier), feature_availability (known_at_ns) | COMPUTED (ROOT legacy pass) | `deploy/aws/box/frankie_box_market_timeline.py:770` |
| 125 | ROOT | ROOT native ledger exact_member_rows.jsonl (through SharedMarketTimeline) | per row; carries clock_model_evaluation | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 126 | ROOT | ROOT native ledger exact_lifecycle_rows.jsonl (through SharedMarketTimeline) | per row; carries clock_prospective_discovery_confirmation | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 127 | ROOT | ROOT native ledger legacy_observable_rows.jsonl (through SharedMarketTimeline) | per row (event / receive) | COMPUTED (ROOT native traversal) | `deploy/aws/box/frankie_box_experiment_native.py:315` |
| 128 | ROOT | ROOT native result.json (through SharedMarketTimeline) | whole day | COMPUTED (ROOT native) | `deploy/aws/box/frankie_box_experiment_native.py:316` |
| 129 | ROOT | ROOT native section bedrock_section_4_2.json.gz (through SharedMarketTimeline) | completed-only (post-stream, never backfilled into a picture) | COMPUTED (ROOT native projection) | `deploy/aws/box/frankie_box_experiment_native.py:317` |
| 130 | ROOT | ROOT native section bedrock_section_4_4.json.gz (through SharedMarketTimeline) | completed-only (post-stream, never backfilled into a picture) | COMPUTED (ROOT native projection) | `deploy/aws/box/frankie_box_experiment_native.py:317` |
| 131 | day-external (sealed base) | day file publications (the external layer) (through SharedMarketTimeline) | each publication at its known_by, in the picture of its cursor | PASSED (sealed day file, by the source-binding pin) | `deploy/aws/box/frankie_box_market_timeline.py:805` |
| 132 | ROOT | ROOT work/file-claims.jsonl (stream claims) (through SharedMarketTimeline) | - | MECHANISM | `deploy/aws/box/frankie_box_market_timeline.py:767` |
| 133 | exchange | exchange.json (claim names for the second set) | teacher cutoff; no clock inside | COMPUTED (exchange) | `deploy/aws/box/frankie_box_jev_cpu.py:652` |
| 134 | exchange | exchange-frankie.json (claim names for the second set) | teacher cutoff; no clock inside | COMPUTED (exchange) | `deploy/aws/box/frankie_box_jev_cpu.py:652` |
| 135 | teacher (BOSS) | teacher rows sidecar (second set to his cutoff) | per row: key + the seven clocks matched to the picture; lock = teacher as_of | COMPUTED (teacher) | `deploy/aws/box/frankie_box_jev_cpu.py:662` |
| 136 | day-external (sealed base) | day-external.json (external.* planes at the cutoff) | sealed base; each point event_time / known_by, read AS-OF the reader's cutoff | PASSED (sealed) | `deploy/aws/box/frankie_box_jev_cpu.py:650` |
| 137 | classroom | Frankie's ledgers.json (after the blind seal) | classroom binding; read after Jev's blind seal | COMPUTED (classroom: Frankie) | `deploy/aws/box/frankie_box_jev_cpu.py:620` |
| 138 | classroom | Frankie's external-code-answers.json (after the blind seal) | classroom binding; read after Jev's blind seal | COMPUTED (classroom: Frankie) | `deploy/aws/box/frankie_box_jev_cpu.py:621` |
| 139 | classroom | Frankie's out/analysis.md (after the blind seal) | classroom binding; read after Jev's blind seal | COMPUTED (classroom: Frankie) | `deploy/aws/box/frankie_box_jev_cpu.py:622` |
| 140 | jev | Jev-only peer knowledge (brain/jev-peer/*) | Jev-only peer namespace (his earlier turns) | PASSED (entries by manifest pin) | `deploy/aws/box/frankie_box_jev_cpu.py:361` |
| 141 | jev | Jev's own brain (jev-brain/entries, jev-brain/lessons) | Jev-only peer namespace (his earlier turns) | PASSED (entries by manifest pin) | `deploy/aws/box/frankie_box_jev_cpu.py:709` |
| 142 | jev (its own scientific test, published into the brain) | brain <day>-jev-tested/stage-knowledge.json (delivery readback) | day + stage wall (DAY_KINDS) | PASSED (entries by manifest pin) | `deploy/aws/box/frankie_box_jev_cpu.py:853` |
| 143 | review (corrections) | brain correction records | when filed (reaches a reader at its boundary) | COMPUTED (review) | `deploy/aws/box/frankie_box_experiment_review.py:771` |
| 144 | orchestrator | Jev request (JEV_CPU_REQUEST_V1) | - | MECHANISM | `deploy/aws/box/frankie_box_jev_cpu.py:417` |
| 145 | setup (runtime) | model runtime config (Granite under llama.cpp) | - | MECHANISM | `deploy/aws/box/frankie_box_jev_cpu.py:475` |
| 146 | jev | retained second-set-at-cutoff.json / material.json / client-config.json / state (resume) | own resume state | OWN | `deploy/aws/box/frankie_box_jev_cpu.py:655` |

#### Consumer: school (31 native inputs in the inventory)

| # | Producer | Artifact | Clock | Computed / passed | Read at |
|---|---|---|---|---|---|
| 147 | classroom | classroom receipt | classroom binding as_of / through_cursor (= the teacher's) | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:244` |
| 148 | classroom | classroom code-answers.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 149 | classroom | classroom ledgers.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 150 | classroom | classroom external-code-answers.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 151 | classroom | classroom novel-findings.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 152 | classroom | classroom correction-response.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 153 | classroom | classroom acknowledgement.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 154 | classroom | classroom external-correction-response.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 155 | classroom | classroom external-acknowledgement.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 156 | classroom | classroom completion.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 157 | classroom | classroom external-completion.json | classroom binding | COMPUTED (classroom) | `deploy/aws/box/frankie_box_school_knowledge.py:264` |
| 158 | classroom process (teacher role: grade / correction) | classroom correction-request.json (corrections received) | teacher as_of | COMPUTED (classroom process, teacher role) | `deploy/aws/box/frankie_box_school_knowledge.py:269` |
| 159 | classroom process (teacher role: grade / correction) | classroom external-correction-request.json | teacher as_of | COMPUTED (classroom process, teacher role) | `deploy/aws/box/frankie_box_school_knowledge.py:269` |
| 160 | teacher (BOSS) | teacher rows (pointer) | per row ts_recv_ns; snapshot as_of = teacher as_of | COMPUTED (teacher snapshot) | `deploy/aws/box/frankie_box_school_knowledge.py:281` |
| 161 | teacher (BOSS) | teacher receipt.json (whole) | as_of = max teacher row receive time (clock_lock_time); through_cursor = record_count-1 | COMPUTED (teacher) | `deploy/aws/box/frankie_box_school_knowledge.py:284` |
| 162 | teacher (BOSS) | teacher rows sidecar (pointer) | per row: key + the seven clocks matched to the picture; lock = teacher as_of | COMPUTED (teacher) | `deploy/aws/box/frankie_box_school_knowledge.py:289` |
| 163 | teacher (BOSS) | BOSS teacher second-set reading (teacher-second-set-read.boss.json) | per row (the sidecar); teacher as_of | COMPUTED (a reading of the sidecar) | `deploy/aws/box/frankie_box_school_knowledge.py:292` |
| 164 | classroom | classroom package.second_set.jsonl (pointer) | per Dipole row; teacher as_of | COMPUTED (classroom second-set lesson) | `deploy/aws/box/frankie_box_school_knowledge.py:294` |
| 165 | classroom | classroom package.second_set.json | per Dipole row; teacher as_of | COMPUTED (classroom second-set lesson) | `deploy/aws/box/frankie_box_school_knowledge.py:296` |
| 166 | classroom process (package key) | classroom package.teacher_key.c15.json (identity only) | teacher as_of | COMPUTED (classroom package key) | `deploy/aws/box/frankie_box_school_knowledge.py:305` |
| 167 | classroom process (teacher role: novelty investigation) | classroom novelty-investigation.json | teacher as_of | COMPUTED (classroom process, teacher role) | `deploy/aws/box/frankie_box_school_knowledge.py:324` |
| 168 | exchange | exchange-frankie.json (the exchange view) | teacher cutoff; no clock inside | COMPUTED (exchange) | `deploy/aws/box/frankie_box_school_knowledge.py:326` |
| 169 | teacher (scientific seat) | Frankie's lessons of the day | per discovery day tested; search F_LAST lag axis | COMPUTED (scientific teacher) | `deploy/aws/box/frankie_box_school_knowledge.py:336` |
| 170 | teacher (scientific seat) | scientific teacher second-set reading (experiment-teacher/teacher-second-set/<day>.json) | per row (the sidecar); teacher as_of | COMPUTED (a reading of the sidecar) | `deploy/aws/box/frankie_box_school_knowledge.py:344` |
| 171 | exchange | the meeting record (meeting/<day>/meeting.json) | none inside (bound to the exchange sha256) | COMPUTED (voice: model) | `deploy/aws/box/frankie_box_brain.py:388` |
| 172 | exchange | the meeting receipt (meeting/<day>/receipt.json) | none inside (bound to the exchange sha256) | COMPUTED (voice: model) | `deploy/aws/box/frankie_box_brain.py:388` |
| 173 | day-external (sealed base) | day-external-receipt.json (S3 key of the day file pointer) | sealed base | PASSED (sealed) | `deploy/aws/box/frankie_box_school_knowledge.py:383` |
| 174 | day-external (sealed base) | day-external.json (pointer) | sealed base; each point event_time / known_by, read AS-OF the reader's cutoff | PASSED (sealed) | `deploy/aws/box/frankie_box_school_knowledge.py:384` |
| 175 | school (earlier days) | brain school index (school/index.json) | append-only index of earlier days | PASSED (index) | `deploy/aws/box/frankie_box_brain.py:493` |
| 176 | review (corrections) | brain correction records | when filed (reaches a reader at its boundary) | COMPUTED (review) | `deploy/aws/box/frankie_box_experiment_review.py:771` |
| 177 | each producer | pointer digests by claim (file-claims.jsonl beside each pointer) | - | MECHANISM | `deploy/aws/box/frankie_box_school_knowledge.py:101` |

### 1.3 Edges the inventory does not carry (found in the readers)

The inventory is per consumer piece and reads the teacher piece as its BOSS step only; the scientific seat (export,
search, lessons), the brain entries each piece files, the teacher-role steps run inside the classroom process, voice,
and the cross-day carry are where it is thin. Each edge below is a FINDING with file:line.

| # | Producer -> consumer | Artifact | Clock | Computed / passed | Where |
|---|---|---|---|---|---|
| M1 | ROOT -> teacher (scientific seat: data export) | the ROOT calculations directory: the five legacy layers and the row spools INCLUDED, bedrock projections/sections excluded as BEDROCK, Frankie's classroom excluded as FRANKIE_REASONING | per row (spools); whole day (layers) | PASSED (hard links, no computation) | frankie_box_experiment.py:5158 (CALCULATIONS); frankie_box_experiment_data.py:57-73 (CATALOG) |
| M2 | ingest -> data export | the sealed ingest directory (journal, receipts, completion, day-external.json) | sealed base | PASSED (hard links) | frankie_box_experiment.py:5158 (INGEST); frankie_box_experiment_data.py CATALOG `ingest` rows |
| M3 | teacher (BOSS) -> data export | the teacher rows file | teacher as_of | PASSED (hard link) | frankie_box_experiment.py:5165 (TEACHER) |
| M4 | data export -> search | the day's export (MANIFEST and every linked file) | as M1-M3 | PASSED | frankie_box_experiment_search.py:6, 3477 |
| M5 | ROOT -> search | the frames spool as the per-day causal axis (search not_run without it) | per row (frames) | COMPUTED by ROOT | frankie_box_experiment.py:5220-5232 |
| M6 | day file -> search | external series read AS-OF the day's HALT | halt_ns (not the teacher as_of) | PASSED (sealed), read at halt | frankie_box_experiment_search.py:1894 |
| M7 | teacher (BOSS rows, through the export) -> search | the Dipole rows (one source per day, duplicates refused) | teacher as_of | COMPUTED by the teacher | frankie_box_experiment_search.py:1797-1819 |
| M8 | search -> scientific teacher (batch lessons, frankie_lessons) | SEARCHES: every searched discovery day of the plan at call time | per day F_LAST axis | COMPUTED (search) | frankie_box_experiment.py:5331-5337, 5381-5382; frankie_box_frankie_queue.py:1200-1218 |
| M9 | classroom -> scientific teacher | Frankie's `ledgers.json` (dipole_novel_findings only, R09), `external-code-answers.json`, `external-novel-findings.json` | classroom binding | COMPUTED (classroom) | frankie_box_frankie_queue.py:1186-1189; frankie_box_experiment.py:5352-5358; frankie_box_scientific_teacher.py:387-400 |
| M10 | Jev -> batch lessons | Jev's sealed claims, only when the plan names a `jev_stamp` for the day | his cutoff | COMPUTED (Jev) | frankie_box_experiment.py:5348-5349; frankie_box_scientific_teacher.py:105 |
| M11 | teacher (brain `<day>-teacher` entry) -> scientific teacher | the rows path found through the entry's summary, then the whole sidecar read | teacher as_of | PASSED (entry) then COMPUTED (a reading) | frankie_box_scientific_teacher.py:2612-2630, 2703 |
| M12 | teacher (teacher-knowledge.json) -> teacher findings | the key's findings, read by the account writer | teacher as_of | COMPUTED (teacher_knowledge) | frankie_box_teacher_findings.py:53, 867 |
| M13 | classroom package key -> classroom process (teacher role) | `pkg['teacher_key']` into the grade, novelty investigation, correction request, external grade | teacher as_of | COMPUTED (classroom process) | frankie_box_experiment_classroom_v2.py:1256-1277 |
| M14 | classroom -> later classrooms | brain `<day>-cycle-00` (Frankie's entry) | day + stage wall; never his own day+cycle | COMPUTED (classroom) | frankie_box_experiment_classroom_v2.py:1325-1348; frankie_box_brain.py:1496-1512 |
| M15 | exchange -> voice | `exchange.json` (its voice_turns) | teacher cutoff | COMPUTED (exchange) | frankie_box_experiment.py:3557-3560; frankie_box_granite_meeting.py:1772 |
| M16 | exchange -> brain `<day>-exchange` -> later classrooms and exchanges | Frankie's view | day + stage 40 | COMPUTED (exchange) | frankie_box_experiment_exchange.py:2345 |
| M17 | scientific teacher -> brain `<day>-lessons` | the lessons | day + stage 20 | COMPUTED | frankie_box_brain.py:221 |
| M18 | search -> brain `<day>-search` | MANIFEST + knowledge-findings.json | day + stage 10 | COMPUTED (search review) | frankie_box_experiment.py:5277-5281 |
| M19 | teacher -> brain `<day>-teacher`, `<day>-teacher-account`, `<day>-teacher-second-set` | rows + key findings; account; the BOSS reading | day + stage -10, -10, 5 | COMPUTED | frankie_box_experiment.py:5006, 5062, 5047 |
| M20 | Jev -> brain `<day>-jev-tested`, jev-peer, jev-brain lessons | his tested claims | day + stage 30 | COMPUTED (Jev's scientific test) | frankie_box_jev_cpu.py:851-852, 861 |
| M21 | school -> later classrooms and later schools | `school/<day>.json` + index row | append-only, earlier days only | PASSED (assembly) | frankie_box_school_knowledge.py:680; frankie_box_brain.py:502 |
| M22 | ROOT (digest render) -> classroom door | `work/derivation-digest-full.md` must exist | whole day | COMPUTED (render) | frankie_box_experiment.py:2772; frankie_box_experiment_classroom_v2.py:678 |
| M23 | class line -> classroom | which previous classroom day is carried (history -> mode -> what the classroom may read) | cross-day | selection | frankie_box_frankie_queue.py:1071 `previous_for` |
| M24 | searches of the batch + brain -> survivors -> later classrooms | the frozen survivor selection | batch boundary | COMPUTED | frankie_box_experiment.py:5407-5440 |
| M25 | every piece -> reports | the day reports' 99-layer join; revised after Jev | after the class line, again after Jev | COMPUTED (render) | frankie_box_frankie_queue.py:1338, 2106-2116 |

Checked and NOT an edge: the exchange's Frankie reply (frankie_box_classroom_code.py `exchange_reply` 3909) is
Frankie's code over the lessons and the teachers' turns; it reads no classroom output file. The exchange's brain
selection never returns Frankie's own `<day>-cycle-00` (entries_before skips the own day+cycle,
frankie_box_brain.py:1507-1512).

### 1.4 Topological order and cycles

FINDING, step level (intra-day; brain and cross-day edges aside):

    sealed base (ingest, day file, manifest, directive, rules, opening book)
      -> ROOT (legacy pass, native traversal, projection, receipt; digest render)
        -> BOSS teacher walk (rows, second set, carry, cutoff context, attachment, sidecar, account, external section)
          -> teacher knowledge (key) -> teacher account (findings) -> BOSS second-set reading
            -> [classroom]                                  -> Jev material (written before any answer)
            -> data export -> search -> search review       (no edge from the classroom)
            -> batch lessons (historical)                   (no edge from the classroom)
          [classroom] -> batch lessons (frankie-<day>) and frankie_lessons
            -> exchange -> voice (meeting) -> school -> reports
          [classroom] + search + exchange -> Jev -> reports revision

FINDING, piece level (the hub's seven, with the teacher's scientific seat inside "teacher" as
`publications('teacher')` puts it): root -> teacher -> classroom -> teacher -> exchange -> jev -> school. Two cycles:

- C1 teacher <-> classroom. The classroom reads the teacher's rows, attachment, carry, sidecar, account and external
  section (inventory rows 41-48, 63-65). The teacher's scientific seat tests Frankie's novel findings from his
  `ledgers.json` (M9), and the teacher-role grade, novelty investigation and correction request are computed on his
  answers inside the classroom process (M13). In hub terms the teacher needs a turn AFTER the classroom.
- C2 exchange <-> Jev. Jev reads the exchange's claim names and retained cutoff context (inventory rows 118, 133, 134).
  The exchange reads `<lessons>/jev/<day>-*.json` (frankie_box_experiment.py:3409) and its brain selection at stage
  `exchange` (before = 40) admits a same-day `jev-tested` entry (DAY_KINDS 30, frankie_box_brain.py:39-40;
  frankie_box_lane_state.py:369-385). The CPU Jev route writes its lessons to `<jev out>/scientific` and
  `jev-brain/lessons` and files `<day>-jev-tested` (frankie_box_jev_cpu.py:826, 851-852), after the class line
  (frankie_box_frankie_queue.py:2097). So on the current day the back edge is never satisfied: the exchange always runs
  without same-day Jev material. It is a cycle in the selection rules, not in today's data.
- Cross-day chain (not a cycle within a day): classroom(d) reads classroom(d-1)'s history and grades (inventory rows
  74-77), school days of earlier days (69-70) and every earlier brain entry (68). The mode (TEACH / GUIDED / SOCRATIC /
  VERIFY) comes from that history and decides what the classroom may read (the current-day teacher entries only in
  TEACH, frankie_box_lane_state.py:381; its own learner walk in SOCRATIC / VERIFY, frankie_box_experiment_classroom_v2.py:
  993-1003). So the classroom chain is serial across days; ROOT and the BOSS teacher are not.

## 2. The calc steps of each piece, in order

Only the functions that compute (readers, witnesses and claim checks are left out unless they decide a value). Each
step: what it takes, what it writes, and its tag.

### 2.1 ROOT (frankie_box_experiment_root.py `_calculate_day` 506; frankie_box_boss_session.py `Session._derive` 2908)

| # | Step | Takes | Writes | Tag |
|---|---|---|---|---|
| R1 | the whole-day pin (`whole_day_pin_document`) | the sealed source, the pin rule | `calculation-pins.json` (root.py:685) | [SEALED] |
| R2 | the day file's computation (`computation_receipt(AsOfReader(body, body['halt_ns']))`) | day-external.json | `external-computation.json` (root.py:599, saved 707-708); clock: the HALT | [SEALED] |
| R3 | the source binding | ingestion receipt, completion, manifest pin, opening book, external pin, shared and native policies | `source-binding.json` (root.py:706) | [SEALED] |
| R4 | process 1, the legacy pass: INPUT records (`_input_records` 4054) replayed through the pinned V4 adapter onto the opening book | the sealed journal, the opening book | the five legacy layers and the row spools prices / frames / structures / failures (`work/derived/.rows/*.jsonl`); the INPUT spool | [SEALED] |
| R5 | process 2, the native traversal beside it (`_start_native_overlap` 2655, `_native_stage` 3859) | the INPUT spool, the opening adapter state | `bedrock/ledgers/` exact_member_rows, exact_lifecycle_rows, legacy_observable_rows; native result.json | [SEALED] |
| R6 | process 3, the native projection (`_native_projection` 3952, `_finalize_projection` 2874, `_write_native_layer_records` 3582) | the ledgers | layers derived_geometry, prebirth_opportunity, causal_clocks; bedrock_section_4_2 / 4_4 (completed-only); native-layer-records.json | [SEALED] |
| R7 | the derivation (`_complete_native_derivation` 3699) | R4-R6 | `work/derive.json` | [SEALED] |
| R8 | the receipt | R1-R7 pins, the spool pins as `shared_market_sources` | `calculations-receipt.json` (root.py:900-916) | [SEALED] |
| R9 | process 4, the digest: off in the experiment ROOT; rendered by frankie_box_render_digest.py beside the teacher (`write_retained_digest`; `Session._write_digest` 3753) | the retained layers and spools | `work/derivation-digest-full.md`, `work/digest-render.json` | [SEALED] |

Everything in ROOT is deterministic from the sealed base. Greg's one-pass direction excludes the derived layers
(R4-R7) from being re-sourced from an altered pass; this map leaves them where they are.

### 2.2 Teacher

The BOSS teacher child (frankie_box_experiment_teacher.py `_teach` 1267) and its orchestrator steps
(frankie_box_experiment.py), then the scientific seat (today after the classroom).

| # | Step | Takes | Writes | Tag |
|---|---|---|---|---|
| T1 | verify the ingestion receipt and the sealed journal (phases verify_ingestion_receipt / verify_sealed_journal) | ingest | (checks) | [SEALED] |
| T2 | open the shared picture (`SharedMarketTimeline`, teacher.py:1327) | the ROOT receipt, binding, derive, spools, native ledgers and sections, the day file publications | (reader) | [SEALED] |
| T3 | the walk, per picture: `CutoffTracker.see` (1475), the classroom carry `K.TeacherPassCarry.note` (1468; FRANKIE'S CODE run on the teacher's walk: the all-99 arrivals, the six native entries' online arithmetic, the anchor pictures), the second-set join of each row's picture | the journal (JournalTeacherR3) and the shared picture | in-memory; saved with the walk | [SEALED] |
| T4 | the row pass (`PT.row_pass`, 1819) with `as_of=bound`, bound = the learner binding's as_of or the WALL CLOCK (1435) | T3 | the Dipole rows (19 components per row) | [SEALED] |
| T5 | the second set (`_second_set` 744, called 1848): planes joined on every row, the book read (`TBR.assemble`), the state split (`_day_state_split` 978), clocks matched (mismatches listed) | T3, T4, a fresh reader for rows read before a resume | teacher-second-set.pkl, teacher-state-split.json, mismatches / book-event / reconciliation difference lists | [SEALED] |
| T6 | as_of = the last row's receive time (1863); `PT.finish` (1873) | T4 | the attachment | [SEALED] |
| T7 | the snapshot (`DC.snapshot_teacher_attachment`, 1944) | T6 | host-dipole-classroom-source.c15.json (rows file); teacher-attachment.pkl (body) | [SEALED] |
| T8 | the cutoff context (`_keep_cutoff_context` 330, called 1989) | T3's tracker; as_of, through_cursor | shared-market-context.json (the exchange / Jev contract) | [SEALED] |
| T9 | the rows sidecar (`_write_rows_sidecar` 1051, called 1996) | T5, T7 | the JSON-lines sidecar (key, clocks, plane references, book columns, state split per row) | [SEALED] |
| T10 | the account (`_teacher_account` 1105, called 2015) | T5, T9 | receipt.account | [SEALED] |
| T11 | the classroom carry saved with its anchors (2020-2027) | T3 | classroom-carry.pkl | [SEALED] |
| T12 | the external section (`EXT.ensure_external_section`, 2041) at cutoff = the teacher as_of | T7, the day file | external-section/ (key, receipt) | [SEALED] |
| T13 | all-99 coverage, claims, the receipt (2069-2075) | all above | receipt.json (status rows_published) | [SEALED] |
| T14 | the teacher key (`Run.teacher_knowledge` 4930: `TR.load` select 4975, `DC.build_teacher_key` + `I._repin_teacher_key_correlations` 4981) | the rows file | teacher-knowledge.json (5002), brain `<day>-teacher` (5006) | [SEALED] |
| T15 | the account report (`Run.teacher_account_entry` 5054 -> `TF.publish` 867, `TF.compute` 238: one stream of the sidecar, per state bucket) | sidecar, receipt, state split, teacher-knowledge.json | teacher-account.json / .md, teacher-findings.json, brain `<day>-teacher-account` (5062) | [SEALED] |
| T16 | the BOSS second-set reading (`Run.teacher_second_set_entry` 5014 -> `TR.second_set_reading_file` 960, reader 'boss_teacher') | sidecar, second-set file, state split, account, lists | teacher-second-set-read.boss.json, brain `<day>-teacher-second-set` (5047) | [SEALED] |
| S1 | data export (`Run.data` 5118) | ROOT, ingest, teacher rows (M1-M3) | experiment-data/<day>/cycle-00 (hard links + MANIFEST) | [SEALED] (passes through, computes nothing) |
| S2 | search (`Run.search` 5200; frankie_box_experiment_search.py) | the export, the frames axis, the day file at HALT (search.py:1894), the Dipole rows | experiment-search/<day>/cycle-00/discovery (MANIFEST, parts) | [SEALED] |
| S3 | search review (`Run.search_knowledge` 5248) | S2 | knowledge-review-*.json, knowledge-findings.json (5277), brain `<day>-search` (5278) | [SEALED] |
| S4h | batch lessons, historical claims (`Run.lessons` 5327) | the repository's historical claims, every searched discovery day at call time (M8) | HISTORICAL_LESSONS_V1, brain `<day>-lessons` | [SEALED] for a fixed set of searched days; ORDER-SENSITIVE (the set grows as days are searched) |
| S4j | batch lessons, Jev's claims (only with a plan `jev_stamp`, 5348-5349) | Jev's sealed claims | JEV_LESSONS_V1 | [ADDS:jev] |
| S4f | batch lessons, Frankie's claims (`frankie-<day>`, 5352-5358) and `frankie_lessons` (frankie_box_frankie_queue.py:1175) | his ledgers.json novel findings (M9), searches | FRANKIE_LESSONS_V1 `<lessons>/frankie/<day>-frankie.json`, brain `<day>-lessons` | [ADDS:classroom] |
| S4r | the scientific teacher's second-set reading (`teacher_second_set_reads` frankie_box_scientific_teacher.py:2597, called 2703) | the `<day>-teacher` entry, the sidecar | experiment-teacher/teacher-second-set/<day>.json | [SEALED] |
| S5 | survivors at the batch boundary (`Run.survivors` 5407) | the batch's searches, the brain | survivor selection (consumed only by later classrooms) | [ADDS: the batch's searches]; [CROSS-DAY] |
| S6 | accumulated lessons, non-arm days only (`Run.accumulated_lessons` 5284; scientific_teacher.py:2660-2672, `TK.teach_accumulated`) | the day's search, the brain | FRANKIE_ACCUMULATED_LESSONS_V1 | [SEALED] + brain (earlier days) |

### 2.3 Classroom (frankie_box_experiment_classroom_v2.py; Frankie's code frankie_box_classroom_code.py)

| # | Step | Takes | Writes | Tag |
|---|---|---|---|---|
| C1 | the package (`phase('package')` 946: `V2.prepare_cycle_v2` -> `I.prepare_integrated_cycle` -> snapshot + `build_teacher_key` + `_repin` + mode from history + pre-message + binding; the external key reused from T12) | the teacher attachment (692, read once), the previous day's history and grades (785-791), the day file | package.source / teacher_key / pre_message / binding .c15.json (954-956) | [ADDS:teacher] + [CROSS-DAY] (the mode) |
| C2 | Jev's material: the V2 model-visible request, written before any answer (963-976) | C1 | `<attempt>/jev-material/classroom-request.json` | [ADDS:teacher] |
| C3 | learner inputs (977-980): `LS.learner_knowledge(stage classroom, mode)`, `LS.learner_school` | the knowledge store (earlier days; same-day teacher entries in TEACH only) | phase save | [CROSS-DAY] |
| C4 | SOCRATIC / VERIFY: `KR.read_day` (995; his own walk, or the teacher's walk when it is the same), `K.independent_evidence` (999), `KX.independent_day_file_evidence` (1002). GUIDED: `K._evidence` (1007) | sealed journal or the teacher walk, the day file | phase saves | [SEALED] (his own reading) |
| C5 | `K.exhaustion_d_facts` (1038 side task, 1078; classroom_code.py:2797) | ROOT derive.json and bedrock layers, the frozen learned structure manifest | exhaustion-d-facts.json | [SEALED] |
| C6 | `K.market_context` (1048; classroom_code.py:512): anchors from the package (first / min / max / last PRESENT per component), the pictures at the anchors, arrivals, coverage; the native entry arithmetic (1059-1069) | the ROOT timeline, the teacher carry (to the last anchor picture; the whole source without it) | native-entry-arithmetic.json; phase save | [SEALED] + teacher carry |
| C7 | `K.knowledge_reproduction` (1088), `K.school_reproduction` (1091) | C3 | phase saves | [CROSS-DAY] |
| C8 | `K.second_set_lesson` (1101; `TR.second_set_lesson` teacher_rows.py:467): planes read by reference at each component's anchor rows | the sidecar (his own walk's in SOCRATIC / VERIFY) | package.second_set.jsonl / .json | [ADDS:teacher] |
| C9 | `K.teacher_account_context` (classroom_code.py:813) | teacher-account.json / .md, TEACH only | learner_context | [ADDS:teacher] |
| C10 | Frankie's answers: 19 component answers (`component_answers_side_by_side` 3355 / `component_answer` 3639), summary (3778), external answers (`KX.answers`), external points use (3050), all-99 coverage (2360) | C1-C9 | phase saves | his own calculation |
| C11 | assembly and validation (1208-1210) | C10 | ledgers, code-answers | his own calculation |
| C12 | TEACHER ROLE inside the classroom process: initial grade (1256; dipole_classroom_session.py:210), relationship cross-check (1257; final_review.py:214), novel findings validated (1258), novelty investigation (1259; final_review.py:151), correction request (1260); external grade / correction (1272-1277) | the package key (M13), C11 | post-grade, novelty-investigation.json, correction-request.json, external-post-grade, external-correction-request.json | [ADDS:classroom] (needs his answers) |
| C13 | Frankie's correction answers, acknowledgement, completion, transcript (1263-1268; `K.correction_answer` 3884) | C12 | correction-response, acknowledgement, completion, transcript | his own calculation |
| C14 | brain publication `<day>-cycle-00` (1325-1348) and the receipt (1451) | all | brain entry, receipt.json | [ADDS:classroom] |

### 2.4 Exchange (frankie_box_experiment_exchange.py `exchange` 1627; voice in frankie_box_experiment.py `voice` 3532)

| # | Step | Takes | Writes | Tag |
|---|---|---|---|---|
| X1 | the lessons, each through the correction route (frankie_box_experiment.py:3486-3497), `load_lessons` (137, 1658) | Frankie's lessons (S4f), Jev's lessons (S4j, empty on the CPU route), historical | (inputs) | [ADDS:teacher second part] |
| X2 | `accumulated_lessons` (322): the brain at stage exchange (365) | the knowledge store | learner-knowledge.json | brain (same-day up to stage 40) |
| X3 | `teacher_rows` (606): the 19 per-component ledgers in one pass (`_ledgers` 707 over `DC._ledger_point`) | the rows file | ledger save | [SEALED] (recomputes T14's ledgers) |
| X4 | the cutoff context `AM.from_teacher` (1689; adviser_market.py:2101): reuses T8 when its scope matches, else reads | T8 | shared-market-context.json (retained) | [SEALED] |
| X5 | the second set at the cutoff `AM.teacher_second_set_at_cutoff` (1719; teacher_rows.py:619) | the sidecar | in the exchange record | [SEALED] |
| X6 | per item: `shared_count_accounting` (1198), `origin_evidence_accounting` (1073), `boss_turn` (1272: `measure_component` 995, `measure_pair` 1007 = `DC._direction_relation`, `_pearson`, `_co_movement`), `science_turn` (1441), Frankie's reply `K.exchange_reply` (1879; classroom_code.py:3909) | X1-X5 | the turns, the teachers' own findings | [ADDS:teacher second part] |
| X7 | accumulated claim tests `TK.teach_accumulated` (2317; teacher_knowledge.py:148) | the day's search, the brain | scientific-knowledge/ | [SEALED] + brain |
| X8 | write once: exchange.json, exchange-frankie.json (2219, 2330), brain `<day>-exchange` (2345) | X6, X7 | files | - |
| X9 | voice: the meeting (`frankie_box_granite_meeting.meeting` 1772) | exchange.json | meeting/<day>/meeting.json, receipt.json | [MODEL] |

### 2.5 Jev (frankie_box_jev_cpu.py `_run` 469)

| # | Step | Takes | Writes | Tag |
|---|---|---|---|---|
| J1 | bind the shared Granite runtime and the request chain | runtime config, request | identity | mechanism |
| J2 | material: the classroom's model-visible request (493-497); the cutoff scope (533); the cutoff context reused from the exchange's retained read, else a fresh `AdviserMarketContext` walk (536-571); the second set at his cutoff with the named leaf ledgers `AM.jev_second_set` (662), names from exchange.json + exchange-frankie.json (650-654) | C2, X4, X8, the sidecar, the day file | material.json, second-set-at-cutoff.json | [ADDS:classroom, exchange] |
| J3 | the sit-in (`SI.main` with Granite chat) and the blind seal (`seal_claims` 608) | J2 | claims.json, claims-seal.json | [MODEL] |
| J4 | after the seal: Frankie's ledgers, receipt, external answers, analysis (619-625) | classroom outputs | comparison | [ADDS:classroom] |
| J5 | his scientific test: `ST.jev_claims` (824), `ST.test` (839 / 844), `ST.write` (845) | sealed claims, the day's search | `<jev out>/scientific/` | deterministic given J3 |
| J6 | deliveries: jev-brain lessons (851), Frankie's brain `<day>-jev-tested` (852), jev-peer (861); receipt | J5 | files, entries | - |

### 2.6 School (frankie_box_school_knowledge.py `build` 238)

| # | Step | Takes | Writes | Tag |
|---|---|---|---|---|
| K1 | sections: frankie_classwork (248-275), boss_teacher (279-330; the key by identity only), scientific_teacher (335-348; Jev's lessons withheld), exchange with the meeting inline (350-376), day_file (378-385); pointer digests by claim (`prefetch_pointer_digests` 113) | classroom, teacher, lessons, exchange, meeting, day file | the school document | PASSED (whole / subset / pointer; no new calculation besides subsets and hashes) |
| K2 | `BR.write_school_day` (680; brain.py:502) | K1 | school/<day>.json + the index row | - |

### 2.7 Forecaster

No consumer and no step today (frankie_box_hub_spokes.py:442-443).

## 3. Duplicates: one quantity, more than one computation from the same base

### D1. The teacher key (the known one), with what the code actually does

| Where | Function chain | Input snapshot | Re-pin | Output form |
|---|---|---|---|---|
| (a) `Run.teacher_knowledge` (frankie_box_experiment.py:4930) | `TR.load(rows, select=cursor, ts_recv_ns, target_hash, components)` (4975) -> `DC.build_teacher_key(snapshot, snapshot_hash_verified=...)` -> `I._repin_teacher_key_correlations` (4981) | the rows file the teacher wrote with `DC.snapshot_teacher_attachment(attachment, request_id='experiment-<day>-cycle-00', 0, 1, source_prefix_hash, as_of, through)` (teacher.py:1944-1945), streamed, hash checked on the stream | `_repin` (dipole_classroom_integration.py:64) | teacher-knowledge.json: per dimension the key WITHOUT `observations` and `nonpresent_explanations`, every pair whole (4984-4993); the key hash itself is not kept |
| (b) classroom V2 package (classroom_v2.py:946) | `V2.prepare_cycle_v2` -> `I.prepare_integrated_cycle` (dipole_classroom_integration.py:95-122) -> `snapshot_teacher_attachment` -> `build_teacher_key(snapshot, None)` -> `_repin` | the SAME call on the SAME body: `p = pickle.loads(attachment)` (classroom_v2.py:775) is the teacher's `body` (teacher.py:1935-1936: attachment, request_id, source_hash, as_of, through_cursor) | `_repin` | package.teacher_key.c15.json, the whole key (954-956) |
| (c) exchange (exchange.py:606, 1007) | `_ledgers` one pass over `DC._ledger_point` (694-746), then per claimed pair `DC._direction_relation`, `DC._pearson`, `DC._co_movement` (`measure_pair` 1007), per claimed component `DC._state_counts`, `DC._direction` (`measure_component` 995) | the rows file, streamed (`TR.load`) | none needed: the core `_pearson` applies the floor of 8 itself (dipole_classroom.py:61, 313-314) | the BOSS turn's measurements in exchange.json, only for the pairs and components the claims name |
| (d) V1 classroom runner (frankie_box_experiment_classroom.py:84) | `I.prepare_integrated_cycle`, as (b) | as (b) | `_repin` | as (b) (not on the V2 route) |
| (e) "hardened" | `dipole_classroom_hardening._harden_teacher_key_correlations` (82) via `prepare_hardened_cycle` and `dipole_classroom_final_review.prepare_final_cycle` (57) | - | `_harden` | NOT called by any box path; only tests (tests/test_frankie_box_classroom.py:61, research/kalshi/frankie_boss/tests/test_dipole_classroom_review_fixes.py) |

Byte identity (FINDING from the code; not checked on box bytes):
- (a) and (b) build the key from the same snapshot (same function, same arguments, previous_snapshot None in both since
  cycle_index is 0), through the same `build_teacher_key`, which reads per row only cursor, ts_recv_ns, target_hash and
  components (`_ledger_point`, dipole_classroom.py:267-272), exactly the fields (a) selects. Both re-pin with `_repin`.
  `_repin` (and the unused `_harden`, AST-identical to it) is an identity on a core-built key: the floor it applies is the
  floor `_pearson` already applied, and it recomputes `teacher_key_hash` over an equal body. So (a)'s findings are a
  projection of (b)'s key and the two should agree value for value; they differ in form (a drops the per-cursor
  observations, b keeps them) and (a) never records the key hash.
- (c) gives, for each claimed pair, the same dicts the key's `relationship_scan` holds for that pair (same three
  functions over the same ledgers), and for each claimed component the same counts and direction as the key's
  dimension. It differs in scope (claimed items only) and in what it adds beside them (masks, controls, the search's
  axis).
- So the "two different correlation re-pins" are one function body; merging the three is not a science change in the
  code. It is still Greg's call; the check that would settle it on the box is in section 6.

### D2. The walk of the shared market picture (the ROOT timeline)

| Where | What it walks | Reuse today |
|---|---|---|
| teacher (T2-T4, teacher.py:1327-1475) | the whole ordered source, every picture | - (the one full walk) |
| classroom `K.market_context` (classroom_code.py:512; classroom_v2.py:1048) | to its last anchor picture with the teacher carry; the whole source without it | the carry (T3, T11) |
| classroom SOCRATIC / VERIFY `KR.read_day` (frankie_box_classroom_reader.py:98) | the sealed day, its own learner walk | the teacher's walk when it is the same walk (`_teacher_walk` 63) |
| exchange `AM.from_teacher` (adviser_market.py:2101) | the source to the teacher cutoff (`AdviserMarketContext.read`) | the teacher-kept context (T8) when the scope matches (2134-2148) |
| Jev (jev_cpu.py:536-571) | the source to his cutoff | the exchange's retained copy, or a supplied one; else a fresh walk (561) |

Same base, same cutoff (the whole day; scope = teacher as_of / through_cursor) everywhere; four of the five reuse the
teacher's walk when their checks pass, so the remaining duplicate is the classroom's partial read to its last anchor and
any fallback walk.

### D3. The anchors

`TeacherPassCarry.note_row` (classroom_code.py:436-) keeps per component the first / running minimum / running maximum /
last PRESENT row with "the same tie rules as market_context"; `K.market_context` (classroom_code.py:543-552) derives the
same four anchors from the package's observations. Same rows, same rule, computed twice (the classroom's copy is the
check the carry must match).

### D4. Readings of the teacher's second set (the sidecar)

| Where | Function | Reader / cutoff |
|---|---|---|
| teacher account (T15) | `TF.compute` (teacher_findings.py:238): one stream, per-cell distributions per state bucket | whole day |
| BOSS reading (T16) | `TR.second_set_reading` via `second_set_reading_file` (teacher_rows.py:812, 960) | reader 'boss_teacher', whole day |
| scientific reading (S4r) | the same `TR.second_set_reading_file` (scientific_teacher.py:2629-2630) | reader 'scientific_teacher', whole day |
| classroom lesson (C8) | `TR.second_set_lesson` (teacher_rows.py:467): planes resolved at the anchor rows | Dipole rows |
| exchange (X5) | `TR.second_set_at_cutoff` (teacher_rows.py:619) | teacher through_cursor |
| Jev (J2) | `TR.second_set_at_cutoff` again (adviser_market.py:2197) + `TR.second_set_leaf_ledger` per named leaf (709) | classroom binding through_cursor = the same through_cursor |

The BOSS and scientific readings are the same function over the same files with a different reader label; the exchange's
and Jev's at-cutoff records are the same call with the same cursor (Jev additionally resolves every plane and ledgers the
named leaves). Each resolves planes by reference to the same ROOT stream rows.

### D5. The day file read as of a cutoff (different clocks, so NOT byte-identical by design)

ROOT's computation at HALT (root.py:599); the search's external series at HALT (search.py:1894); the external section at
the teacher as_of (built once by the teacher, dipole_classroom_external.py:819; the classroom reuses it); the classroom's
independent day-file evidence in SOCRATIC / VERIFY (classroom_v2.py:1002); the classroom's external points use
(classroom_code.py:3050, at the pre-message cutoff); the planes `external.*` in Jev's second set and the classroom's
second-set lesson (teacher_rows.py:467, 619, given `day_file`). Same sealed file, three different cutoffs (see W1).

### D6. Ledgers of the teacher rows

The key's `_dimension_ledger` (dipole_classroom.py:276) and the exchange's `_ledgers` (exchange.py:707) are the same
per-row step (`_ledger_point`) over the same file: computed in (a), (b) and (c) of D1. The exchange saves its ledgers for
its own resume (`_write_ledger_save` 581), the key's are not shared.

### D7. Accumulated claim tests

`TK.teach_accumulated` (teacher_knowledge.py:148) runs inside the exchange on arm days (exchange.py:2317) and as the
scientific teacher's accumulated mode on non-arm days (scientific_teacher.py:2670; `Run.accumulated_lessons` 5284).
Same function, disjoint days: a placement difference, not a same-day duplicate.

### D8. The external section key

Built by the teacher (teacher.py:2041) and, when absent, by the classroom V2 through the same
`ensure_external_section` (retained publication reused, no relationship recalculated: dipole_classroom_external.py:
819-860). Built once when the teacher built it; listed for completeness.

### D9. File hashes (mechanism, not a quantity)

The rows file and the attachment are hashed by the teacher (hash_on_thread, claims written: teacher.py:2052-2058) and
then taken by claim by `Run.teacher_rows_sha256` (frankie_box_experiment.py:5069), the exchange (`_claimed_file_pin`
487), the school (`prefetch_pointer_digests` 113) and `brain_stage`. Already deduplicated by FRANKIE_FILE_CLAIM_V2;
a re-hash happens only when a claim does not hold.

## 4. Forward reads and blind-wall concerns

### 4.1 Hidden ordering constraints (a step reads what is produced later in the hub order)

| # | Reader | Reads | Produced by | Why it matters |
|---|---|---|---|---|
| F1 | teacher scientific seat: batch lessons `frankie-<day>` (frankie_box_experiment.py:5352-5358) and `frankie_lessons` (frankie_box_frankie_queue.py:1186-1189) | Frankie's ledgers.json, external-code-answers.json, external-novel-findings.json (scientific_teacher.py:387-400) | the classroom (C11-C13) | C1: under the hub order (teacher before classroom) the teacher's lessons need a turn after the classroom |
| F2 | teacher role (grade, novelty investigation, correction request) | Frankie's answers | the classroom | computed inside the classroom process (classroom_v2.py:1256-1277) after his answers; teacher-role output placed in the classroom's turn |
| F3 | exchange | `<lessons>/jev/<day>-*.json` (frankie_box_experiment.py:3409) and the same-day `jev-tested` entry admitted at stage exchange (frankie_box_lane_state.py:369-385; DAY_KINDS frankie_box_brain.py:39-40) | Jev, after the class line (frankie_box_frankie_queue.py:2097; jev_cpu.py:851-852) | C2: always empty on the current day under the CPU Jev route; the full exchange view never carries same-day Jev items although the exchange is written to |
| F4 | Jev | claim names from exchange.json / exchange-frankie.json (jev_cpu.py:650-654) | the exchange | Jev must follow the exchange; if he ran first the names list is empty (the drop-in's note) |
| F5 | reports | Jev's lists and late pieces | Jev | rendered before Jev, then revised under the same number (frankie_box_frankie_queue.py:2106-2116; `reports_stale` 3275, `reports_school_stale` 1419) |
| F6 | classroom door | work/derivation-digest-full.md | the digest render, beside the teacher | the class door waits for it (frankie_box_experiment.py:2772); classroom_v2.py:678 refuses without it |
| F7 | batch lessons (historical, and every other claim set) | the set of searched discovery days at call time (frankie_box_experiment.py:5331-5337; frankie_box_frankie_queue.py:1200-1204) | each day's search | the lessons' CONTENT depends on how many days had been searched when the call ran; an earlier day's lessons are tested on fewer days than a later one's |

### 4.2 A value read on a later clock than the reader's own as_of, or across a wall

| # | Where | What | Concern |
|---|---|---|---|
| W1 | ROOT external computation at `body['halt_ns']` (root.py:599) and the search's external series at `body['halt_ns']` (search.py:1894) | the day file AS OF THE HALT, while the classroom, the exchange and Jev are cut at the teacher as_of = the last teacher row's receive time (teacher.py:1863; the external section's cutoff_ns = snapshot as_of, dipole_classroom_external.py:858-860) | a day-file point known in (teacher as_of, halt] can enter the search's counts, which reach the exchange and Frankie's exchange view (and his brain from the next day) at a cutoff of the teacher as_of. Whether any such point exists on a day is data, not checked here. The frames axis of the search covers the whole day too; any frame after the last teacher row is in the same window. |
| W2 | Jev's material (jev_cpu.py:646-662), built BEFORE his blind seal (`seal_claims` 608, the sit-in after the material) | the names of the dipole.second_set leaves to ledger, parsed from exchange.json and exchange-frankie.json, which carry Frankie's claims (`AM.second_set_claim_names`, adviser_market.py:2232) | names only (which leaves get ledgered); every ledgered row is at or before his cutoff (`blind_wall_audit` raises otherwise, adviser_market.py:2209-2223). Still a selection derived from Frankie's findings reaching Jev before his seal: a wall question for Greg. |
| W3 | the teacher's row pass `as_of=bound`, bound = `int(time.time() * 1e9)` without a learner binding (teacher.py:1435, 1819) | the run's wall clock as the pass's as_of | no leak (the whole sealed day precedes the wall clock); the published as_of is computed after (1863). The pass's own bound is on none of the seven clocks: recorded. |
| W4 | the classroom's brain selection walls the same-day `teacher-second-set` entry (DAY_KINDS 5 > classroom 0, frankie_box_lane_state.py:383) while `K.second_set_lesson` reads the sidecar directly (classroom_v2.py:1101-1103) | the same content by two paths | INTENTIONAL per frankie_box_brain.py:36-38 (the classroom reads the second set itself). Listed so the hub's single reveal record states it once. |

## 5. Flow shape of each piece under the hub (Greg, binding: not one size fits all)

Shapes: ONE-WAY IN (reads the hub, adds nothing a same-day calc consumes), ONE-WAY OUT (publishes base others read,
reads no other piece's additions), ONE ROUND TRIP (reads, adds once, done for the day), ITERATING (its additions depend
on other pieces' additions that in turn depend on its own: it can usefully take a second lap; the pair is named).
Determined from the steps in section 2 and the edges in section 1 (FINDING), within one day.

| # | Piece | Reads (hub) | Adds | Flow shape | Basis |
|---|---|---|---|---|---|
| 1 | ROOT | sealed base only | receipt, binding, derive, spools, ledgers, sections, external computation | ONE-WAY OUT | R1-R8; no input from any piece (inventory rows 1-14) |
| 2 | digest render | ROOT's retained layers and spools | derivation-digest-full.md | ONE-WAY OUT (ROOT's base, second producer) | R9; read by the class door and Frankie's brain entry only (M22) |
| 3 | teacher (the BOSS pinned publication, T1-T16) | sealed base + ROOT | rows, attachment, sidecar, second set, carry, cutoff context, external section, key findings, account, BOSS reading | ONE-WAY OUT | reads no classroom / exchange / Jev addition; everything after reads it |
| 3b | teacher as the hub piece (with its scientific seat) | as 3, plus the classroom's novel findings | as 3, plus Frankie's lessons, the novelty investigation (proposed) | ITERATING (exactly one extra turn) | pair teacher <-> classroom: the classroom reads the teacher rows (classroom_v2.py:686-692, 775) and the teacher's Frankie lessons read the classroom's ledgers (frankie_box_frankie_queue.py:1186-1189; frankie_box_experiment.py:5352-5358) |
| 4 | classroom | ROOT, teacher (filtered: key withheld until each lesson's discussion), knowledge store of earlier days | his answers, ledgers, the lesson discussions (grade, correction), Jev's material, brain entry | ONE ROUND TRIP (within the day) | nothing he reads on the day depends on his own additions: same-day search and lessons are walled (frankie_box_lane_state.py:369-385); across days he is the start of the next day's chain (rows 74-77) |
| 5 | data (export) | ROOT, ingest, teacher rows | the hard-linked export + MANIFEST | ONE ROUND TRIP (pass-through) | S1; computes nothing |
| 6 | search | the export, the frames axis, the day file at HALT | MANIFEST, parts, knowledge-findings, `<day>-search` | ONE ROUND TRIP | S2-S3; no classroom input (section 0) |
| 7 | batch lessons | searches, historical claims, Frankie's ledgers (frankie-<day>), Jev's claims (only with a plan jev_stamp) | lessons files, `<day>-lessons` | ONE ROUND TRIP today; ITERATING only through the jev_stamp path | latent pair batch lessons <-> Jev: Jev's claims enter by `JEV_STAMP` (frankie_box_experiment.py:5348-5349), Jev's material reads the exchange (jev_cpu.py:650-654) which reads the lessons (frankie_box_experiment.py:3409, exchange.py:1658). Also order-sensitive across days (F7) |
| 8 | frankie_lessons | Frankie's ledgers, searches | FRANKIE_LESSONS_V1, `<day>-lessons` | ONE ROUND TRIP | depends on the classroom, which does not read it on the same day |
| 9 | exchange | teacher rows + second set + cutoff context, lessons (Frankie, historical, Jev), search, brain to stage 40 | exchange.json, exchange-frankie.json, `<day>-exchange` | ITERATING (latent; empty today) | pair exchange <-> Jev: the exchange reads same-day Jev lessons and `jev-tested` (frankie_box_experiment.py:3409; frankie_box_lane_state.py:369-385 with frankie_box_brain.py:39-40) and Jev reads the exchange (jev_cpu.py:543, 650-654). Write-once today (exchange.py:56), so a second lap needs its successor route (`rebuild_successor` 2040) |
| 10 | voice (the Granite meeting) | exchange.json, the shared picture, a knowledge index from the brain (granite_meeting.py:483-506) | meeting.json + `<day>-meeting` | ONE-WAY (Greg's call), see the check below | nothing on the day computes on it; see the cross-day note |
| 11 | school | classroom, teacher, lessons, exchange, meeting, day file | school/<day>.json + index row | ONE ROUND TRIP (assembly) | K1-K2; read by the reports and by later days' classrooms only |
| 12 | reports | everything | the rendered reports | ONE-WAY IN (read twice: after the class line and again after Jev) | nothing reads the reports into a calc; the revision is a re-read (frankie_box_frankie_queue.py:2106-2116) |
| 13 | Jev | classroom material, teacher second set at cutoff, exchange names and context, search; after his seal the classroom's outputs | claims, seal, his tests, `<day>-jev-tested`, jev-peer, jev-brain | ITERATING (latent, bounded) | pair Jev <-> exchange as row 9; bounded because his material is never redone once written (jev_cpu.py:656-661) |
| 14 | forecaster (stub) | nothing today | nothing | ONE-WAY IN (go-live: the last spoke) | frankie_box_hub_spokes.py:442-443 |

The meeting check (Greg's call: ONE-WAY). FINDING, within the day: nothing reads the meeting's output into a
calculation. Its readers are the school, which carries the whole record inline as discussion with
"evidentiary_authority: none" (frankie_box_school_knowledge.py:357-376), the day reports (frankie_box_experiment_day_reports.py:
136, 1845-1850: its receipt's all-99 list, rendered), and its own brain entry (frankie_box_brain.py:429-471, kind
"post-class discussion; coordinator turns have zero evidentiary weight"). FINDING, across days, one path is open and
should be closed or confirmed by Greg: the `<day>-meeting` entry is filed with `include=True` (frankie_box_brain.py:
454-456) and every later classroom's `learner_knowledge` admits earlier days' entries of any kind
(frankie_box_lane_state.py:362-385). The classroom's `K.stage_knowledge_reproduction` (frankie_box_classroom_code.py:
4065-4123) walks every loaded document and turns every dict that carries `finding_id`, `claim_id`, or `x` and `y` into
a check against today's Dipole evidence, without a filter on the entry's kind. The meeting record keeps the exchange's
items with their `claim` objects and the seats' records (frankie_box_granite_meeting.py:497-505, record 2122), so any
such dict copied into the meeting would be re-applied on later days (a copy of what the `<day>-exchange` entry already
carries, not Granite prose). Whether the record carries such keys is not settled by the code alone; the later
meeting's own input also lists a knowledge index from the brain (granite_meeting.py:483-506), prose into prose. So: ONE-
WAY on the day, confirmed; ONE-WAY across days holds only if the reproduction skips meeting entries, which it does not
do by kind today.

## 6. The proposed order under the hub (PROPOSAL, built on the findings above)

Order: ROOT, teacher, classroom, teacher (second turn, same lap), exchange (+ voice), Jev, school, forecaster. One turn
each (the teacher two), additions only, base by reference.

| Turn | Piece | Flow shape | Reads from the hub | Adds | Moved in (deterministic from sealed data) | Must stay where it is |
|---|---|---|---|---|---|---|
| 1 | ROOT (+ digest render) | ONE-WAY OUT | pinned sources | R1-R9 | the digest render inside ROOT's turn, so the class door waits on an addition instead of a process (F6) | the derived layers (Greg: not one-pass candidates) |
| 2 | teacher, first turn | ONE-WAY OUT | base + ROOT | T1-T16, S1-S3, S4h, S4r | (i) data export, search, search review and the historical lessons, moved before the classroom: no classroom edge, and the classroom walls them by stage anyway; (ii) ONE second-set reading carrying both reader labels (D4); (iii) the second set at the cutoff once, for the exchange and Jev (D4); (iv) every dipole.second_set leaf ledgered to the cutoff once (Jev then filters by names; removes W2's Frankie-derived selection); (v) the teacher key once (D1), the classroom package and the exchange's measures reading it by reference; (vi) candidates, Greg's call whether they are ingestion or Frankie's own calculation: the exhaustion/D facts (C5) and the plane resolution at the anchors (C8) beside the carry already made on this walk | the BOSS walk itself and everything after it reads this turn |
| 3 | classroom | ONE ROUND TRIP | base + ROOT + teacher (his filter: key and answers withheld until each lesson's discussion, with the reveal record; same-day search / lessons walled) | C1-C14 (his answers, the lesson discussions, Jev's material) | - | his answers and the lesson discussions (they need his answers); the cross-day carry makes the classroom chain serial over days |
| 4 | teacher, second turn (same lap) | ITERATING (teacher <-> classroom) | the classroom's novel findings only (R09) | Frankie's lessons (S4f / frankie_lessons), the novelty investigation (moved from C12: a teacher-role response to his novel findings) | - | needs turn 3 |
| 5 | exchange (+ voice) | ITERATING (latent) / voice ONE-WAY | teacher (both turns), brain to stage 40 | X1-X9 | X3-X5 read the teacher's additions by reference instead of recomputing | needs turn 4 |
| 6 | Jev | ITERATING (latent, bounded) | classroom material, teacher second set + leaf ledgers, exchange names and context, search; after the seal the classroom | J1-J6 | J2's walk and second set read by reference | after the exchange (F4) |
| 7 | school | ONE ROUND TRIP | all | K1-K2 | - | last of the day's calc pieces |
| - | reports | ONE-WAY IN | all | renders | rendered once after Jev instead of before and again after (F5) | - |
| 8 | forecaster | ONE-WAY IN (stub) | - | - | - | go-live |

Hub-core note (FINDING from frankie_box_hub.py): the core takes each piece once per round in the workflow order when
`ordered=True` (take_turn 372) and allows a second write in the same round that EXTENDS that round's additions
(docstring line 15). A second teacher turn AFTER the classroom in the same round is therefore not expressible with
`ordered=True` alone: it needs either the teacher named twice in the round's order or an "after <piece>" condition on
the take. That is a hub-core change (PROPOSAL), not made here.

Minimum laps to the content fixed point (FINDING on the rule, PROPOSAL on the order):
- `next_lap` (frankie_box_hub.py:616) returns True while any piece added a content hash not seen in an earlier round;
  round 1 always adds, so every day takes at least a confirming lap: the floor is 2 laps.
- PROPOSED order above, same-day Jev material reaching the exchange on later days only (as today): 2 laps (one working
  lap, one confirming lap in which every piece reads and adds nothing new).
- Today's fixed order with one turn per piece per lap (teacher before classroom, nothing after): 3 laps. Lap 1: the
  teacher has no classroom input, the exchange runs without Frankie's lessons; lap 2: the teacher adds them, the
  exchange, Jev and school change; lap 3 confirms. FINDING: today's exchange and school are write-once per day
  (exchange.py:56; school_knowledge.py:30) and Jev's material is never redone (jev_cpu.py:656-661), so a lap-2 revision
  is refused by today's code except through the successor routes (exchange `rebuild_successor` 2040, school
  `rebuild_successor` 531).
- If same-day Jev claims must reach the same-day exchange (C2 honoured): 4 laps (lap 3: the exchange and school take
  `jev-tested`; lap 4 confirms), bounded only because Jev's material is frozen at its first write; without that freeze the
  names -> material -> claims -> exchange items -> names loop has no bound in the code.

30-day consequence (PROPOSAL): turns 1-2 of every day depend only on that day's sealed base (the opening book is in the
sealed ingest), so they can run ahead for all days in parallel; turns 3-7 are serial across days (the classroom carry,
the school days, earlier brain entries). One ordering choice remains Greg's: with all searches done first, every day's
batch lessons are tested on every searched day (F7), which makes the lessons deterministic but different from today's
(where an early day is tested on fewer days); CLAUDE.md's "all 30 days share completed knowledge regardless of market
date" reads as allowing it.

## 7. Checks that would turn findings into facts (read-only; not run)

1. D1: on a2/20231018 after the classroom, compare `experiment-teacher-rows/20231018/teacher-knowledge.json` findings
   with `work/classroom/package.teacher_key.c15.json` (dimensions without observations / nonpresent_explanations;
   relationship_scan) and `source.snapshot_hash` with the key's `source_snapshot_hash`. Equal = one key.
2. W1: list the day file's points with known_by in (teacher as_of, halt_ns] for 20231018 (the teacher receipt's as_of,
   the day file's halt_ns).
3. Meeting: grep the first `<day>-meeting/meeting.json` for `finding_id`, `claim_id`, or `x` and `y` keys.
4. C2: confirm `<lessons>/jev/<day>-*.json` is absent at the exchange on a CPU-Jev day (the exchange receipt's
   `lessons` list).
