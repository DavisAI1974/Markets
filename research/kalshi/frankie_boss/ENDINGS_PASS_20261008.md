# Endings pass, 2026-10-08 (session 6): CPUs and one pass in the ENDING of every workflow piece after ROOT

Owner: the ending-sequence role (parent-only session; agents do the work). Greg, 2026-10-08, verbatim: "We definitely
need CPUs in every step of this ending process of root" and "We need to check every workflow piece to see if they all
end like this. If they do, then start with CPUs on classroom while we are going through it. We'll do both in parallel."
"End like this" = what the probe measured live on a2's ROOT (scratchpad probe PROBE_20261008.md): the digest decoded the
496.7 GB frames spool five times for one table (json.loads + unpack per line at ~9.25 MB/s per core), 46 more tables
including a single-core one, a 9-minute single-CPU member-layer read while 31 CPUs idled, and two full read-backs of the
472 GB layer for hashes. ROOT itself is the ROOT-dedupe role's; this pass walked EVERY OTHER PIECE, classroom first.

Branch `ccr-d2f8f826-iefeah-frankie` (edits made on 1bf9ce0..dbda84f; the parent's WIP snapshots carry them as they land).
**SOURCE-BUILT / RUNTIME-UNVERIFIED.** py_compile + ast.parse on every edited .py, git diff --check clean, and the toy
suites below (classroom 24/24, teacher 7/7; this container: 4 CPUs, Python 3.13, torch stubbed for the research package).
Nothing ran on the box; no AWS call; no install; nothing committed by this role. The dedupe of INPUTS is the
workflow-dedupe role's (DEDUPE_PASS_20261008_WORKFLOW.md, read first, not redone); this pass is the ENDING steps and CPUs.

The rule applied to every ending step (everything after a piece's main computation up to its receipt and hand-off):
every step that can run on the lane goes through `deploy/aws/box/frankie_box_lane_pin.py` (ordered_map / placement /
executor; sized from the booked lane, never a constant); every multi-pass over the same bytes collapses to ONE pass
(decode once, hand the decoded rows to every consumer; hash on the write stream); no read-back after a write; every
output byte and receipt meaning identical (proved by toy: old vs new bytes and sha256 equal; decode/open counts before
and after). An identity-bound region is NOT edited: its function, what it needs and the saving are stated for Greg.

Rates used for the seconds column: 1.1 GB/s sequential read (the probe's measured read-back rate on the box; 1.25 GB/s
is the volume cap); ~9 MB/s per core for json decode (the probe); json.dumps(indent=1, sort_keys) MEASURED here
(toy 5): 293 MB/s on string-heavy bodies, 42 MB/s on nested small objects; sha256 397 MB/s here (one core; the box's
hashing is disk-bound). a2's sizes from the probe: frames.jsonl 496,743,568,399 B; legacy_book_imbalance.json
472,040,420,230 B; exact_member_rows 193,743,650,444; exact_lifecycle 7,560,352,552; legacy_observable 742,788,266;
structures 1,063,001,944; input spool 537,361,074; the sealed 20231018 journal ~23.7 GB; the retained teacher-rows tree
25,128,540,076 B over its days (~1.5 GB per day). The classroom and every later piece have NEVER run on a full day:
their output sizes are unmeasured; where a number depends on them the formula is given and the receipt field that will
measure it on day 1 is named.

## 0. The compact table (what changed; per-piece detail below)

| # | Piece | Ending step | CPUs before -> after | Passes before -> after | Seconds at a2 | Test |
|---|---|---|---|---|---|---|
| C1 | classroom | the 19 component answers (v2.py:1033-1066; classroom_code.py:2932-2996 `component_answers_side_by_side`) | 1 serial -> min(31, pending answers) pinned fork workers (ordered_map), values yielded in name order through the same phase() | 1 -> 1 | T_answers x (1 - 1/W); T_answers unmeasured (each answer splices the anchor picture texts: receipt `cpu_pinning.picture_texts.characters` and `phase_timings.component:*` give it on day 1) | 1a-1f |
| C2 | classroom | external answers KX.answers (v2.py:421-459 `_ThreadTask`, 1041-1070) | serial AFTER the answers -> a thread of this process started once the pool is forked (same OpenBLAS reduction setting: same bits) | 1 -> 1 | T_external hidden under C1 (`side_by_side.external_answers.thread_seconds`) | 4a-4c |
| C3 | classroom | the five answer-file groups: code-answers.json, learner-knowledge.json, ledgers.json, classroom.md, external-code-answers + external-novel-findings (v2.py:462-499 `_side_writes`/`_collect_side_writes`, 1116-1149, collected 1183) | 1 serial on the main thread BEFORE the grade chains -> 5 forked writers, one lane CPU each (placement over the off-consumer CPUs), BESIDE the V1 and external grade chains; the write-stream witness of each file remembered in the runner (frankie_box_filehash.remember) | encode+write 1 -> 1; read-back for the output pins 0 -> 0 (proved) | 3 x (P / 293 MB/s) + 2 small, hidden under the grade chains; P = bytes of picture text per file (the same texts sit in all three) | 2a-2h |
| C4 | classroom | brain publication `BR.write_entry` -> derived-files.md (brain.py:529-593 `file_claims`/`file_witnesses`, 894-904) | 1 sequential sha256 of the 472 GB layer (14-thread pool, one file = one thread) -> ROOT's FRANKIE_FILE_CLAIM_V1 claim under stat + last-64-KiB check, else hashed on lane-sized pinned threads | 1 full read of 472 GB -> one 64 KiB read (with the claim) | 429 s (472,040,420,230 B / 1.1 GB/s) -> ~0 s WITH ROOT's claim row; 0 s saved without it (request R1 below) | 3a-3g |
| C5 | classroom | `_pin_outputs` (v2.py:1272) | threads over the lane (built, session 5) | read-backs: every durable-written file is a cache hit (proved opens = 0); only the 4 SE._save'd package.*.c15.json are read once (blocked, B2) | the 4 package files: package.source ~ the rows file (GB-class on a full day, page-cache hot: ~1-2 s) | 2e |
| T1 | teacher | attachment pickle (ET.py:177-278 `_write_attachment`/`_attachment_writer_main`/`_start_attachment_writer`/`_finish_attachment_writer`; call sites 1044 and 1083-1084) | serial, GIL-bound, before the rows save -> a forked side process on one lane CPU (placement) beside the snapshot and the rows save; the digest from the write stream in a sidecar; in-order fallback | 1 -> 1 (hashed as written, as before) | pickle seconds of the attachment hidden under snapshot + SE._save: bytes / ~300 MB/s (a 0.5 GB attachment: ~2 s); `cpu_pinning.attachment_writer.side_seconds` measures it | teacher 0-4 |
| D1 | data export | MANIFEST + receipt after `_pin_all` | already pinned ordered_map (session 5); the ending is KB-MB JSON | clean: no read-back after a write; the day file is read once more for its point declarations (MB, page-cache hot) | ~0; the export's wall is `_pin_all` itself (dedupe #7: ~700 GB = 636 s until ROOT writes claims, R1) | listed |
| S1 | search | publish (search.py:3321-3400) | part pins = write-time digests (session 5); a part without one hashed on lane threads; MANIFEST.json hashed once more (KB-MB); two JSON dumps + fsync | 1 | ~0 (the three MANIFEST hashes are KB-MB; the parts are not re-read) | listed |
| R1 | reports | 16 inspection pieces (workflow_inspection.py:1091-1166 `render_pieces`) | side by side on pinned fork workers (ordered_map, one per piece, prefetch on lane threads): BUILT after the stacks pass, confirmed here | reads: `_READ_CACHE` one read per artifact | n/a (built) | listed |
| R2 | reports | the two day reports (`render_side_by_side`), the 99-layer join (`collect_all99`), receipt | reports side by side (built); the join reads ~11 KB-MB receipts once each on the coordinator; receipt dump KB-MB | 1 | ~0 (KB-MB) | listed |
| F1 | finalization | `scan` (NATIVE_VALUE_CODE, identity-bound) | 14 helpers from `placement()` (session 5) | 1 | bounded by EBS | BLOCKED B4 (stated) |
| X1 | exchange / Jev / meeting / school / survivors / scientific / lessons | endings = JSON renders (MB), brain entries (copies), receipts; witnesses after durable writes are cache hits (dedupe #5/#6/#8/#9) | serial, KB-MB | 1 | ~0-2 s each; formulas below | listed |
| I1 | ingest | checkpoint + completion + receipt + claim row (ingest_block_sources 862-903) | serial KB-MB; `_journal_sha256` beside the drain (session 5); `_boxes` = SQLite count(*) on the sealed container (leaf pages, page-cache hot) | 1 | ~0 | listed |

## 1. Classroom (`frankie_box_experiment_classroom_v2.py`, `frankie_box_classroom_code.py`, `frankie_box_brain.py`)

The ending = everything after `market_context` (v2.py:968). Walked step by step; "before" is the file at 1bf9ce0.

| Step (file:line now) | Before: CPUs / passes | After | Bytes |
|---|---|---|---|
| native-entry-arithmetic.json `_dump` + `_sha256` (v2 ~976-983) | 1 CPU json.dumps; the sha256 = the write-stream witness (durable.write_chunks + filehash.remember): no read-back (verified by reading `_bytes`/`_dump`/write_chunks and by toy 2e's mechanism) | unchanged | same |
| exhaustion/D facts, knowledge and school reproductions | side processes beside the read (session 5) | unchanged | same |
| anchor picture texts `prepare_picture_texts` | ordered_map over the lane (session 5) | unchanged | same |
| **the 19 `component_answer` calls** (old v2 949-951) | SERIAL on the main thread; each: `_exact_market_text` of the component's anchor pictures (splice of the pre-encoded texts: a string join of MB-class texts), json.dumps of the native pairs, the facts, the knowledge notes, 18 pair texts | `K.component_answers_side_by_side` (classroom_code.py:2932-2996): the pending answers on a pinned fork pool (`LP.ordered_map`, workers = min(lane, pending), gc.freeze, `_ANSWER_SHARED` inherited by fork, a dead worker's answer redone with one worker fewer), yielded in name order; v2.py:1033-1066 takes each through the SAME `phase()` (a saved phase restored as before; `received.cpu_pinning.component_answers` records placement, deaths, redone, seconds). Why the value is identical: component_answer is a pure function of its arguments and of module state that is only READ (`_EVIDENCE_CACHE` filled by the runner's guided_evidence phase before the fork; the spliced picture texts keyed by object identity, the same addresses in a forked child; TEACHER_FORM_COMPONENTS, STATES); nothing it touches is written. The pool's pickle preserves the value's object sharing, so the phase file's pickle bytes are equal (toy 1b). | same (toy 1a/1b) |
| `summary_answer` | serial, one call (`_exact_market_text(shared_market.summary())`) | unchanged (one call; depends on all 19) | same |
| **`KX.answers` (external section)** (old v2 956) | serial AFTER the 19 answers | `_ThreadTask` (v2.py:421-459) started from the pool's `on_start` (after the workers are forked, so the fork never sees the thread), joined by `phase('external_answers', external.result)` in the same place (v2.py:1070); a raised exception is re-raised as the same object (a ModeNotAnswerable still reaches the refusal path, toy 4b); when the phase is saved the thread is never started; when the pool path is serial (one answer / one CPU) `on_start` still fires at the start of the serial loop. Same process, same `blas_reduction` setting -> the same bits. | same |
| external_points_use, all99_coverage, assembly, validate, external_report | serial, small (the day file read once more: MB, page-cache hot; dedupe listed it) | unchanged | same |
| **the answer-file dumps** (old v2 1000-1018) | SERIAL json.dumps + durable write on the main thread, BEFORE the grade chains: code-answers.json (the 19 answers with their picture texts), learner-knowledge.json, ledgers.json (the same texts again), classroom.md (`C.render_markdown`: the same texts a third time), external-code-answers.json, external-novel-findings.json (+ `_sha256` of the former: a cache hit) | `_side_writes` (v2.py:462-481): five forked writers, one lane CPU each (`LP.placement(5, off-consumer CPUs)`; the external pair in one writer so the second file takes the first's write-stream sha256), running BESIDE the V1 and external grade chains (v2.py:1116-1149); `_collect_side_writes` (v2.py:483-499) joins them before the grade-chain files and hands every witness to `frankie_box_filehash.remember`, so `_pin_outputs` reads nothing back (toy 2e: opens = 0). `_bytes`/`_text`/`_dump` (v2.py:74-96) now RETURN the witness (an unchanged file is hashed from memory and remembered). No fork possible -> written in order, the same bytes (toy 2g). | same (toy 2a: byte-equal to the in-process dumps) |
| V1 grade chain (13 phases) and external grade chain (5 phases) | serial, small (host functions) | unchanged (the writers above overlap them); running the external chain on a side process was weighed: each phase is KB-class, a fork per phase costs more than the phase | same |
| the 17 grade-chain dumps, transcript.md, classroom-external.md, two histories (v2 ~1190-1200) | serial KB-MB | unchanged: a fork per KB file costs more (50-100 ms on a multi-GB parent) than its json.dumps (~1 ms) | same |
| **`publish_brain` -> `BR.write_entry`** (v2.py:1226/1228 -> brain.py:766) | copies the digest (one streamed pass, needed), derive.md (json of derive.json, MB), classroom.md (read + copy, needed for the copy), THEN `sha256_files(work/derived)`: every file directly under ROOT's work/derived hashed from byte 0 for derived-files.md. On a2: legacy_book_imbalance.json 472,040,420,230 B = ONE sequential sha256 on one thread of the 14-thread pool = 429 s at 1.1 GB/s (378 s at the 1.25 GB/s cap), a THIRD full read of the layer in the run (ROOT wrote it, ROOT read it back twice), to write a witness table Frankie never reads (include=False). NOT in any stacks-pass table. | brain.py:529-593: `file_claims(work)` reads `<work>/file-claims.jsonl` (FRANKIE_FILE_CLAIM_V1, the dedupe role's format; ROOT's rows per request R1) and `file_witnesses(paths, claims)` takes a claim only when (dev, ino, size, mtime_ns) AND the sha256 of the last 64 KiB equal the row's (the export's exact rule, `_pins_progress`); every other file is hashed from byte 0 on `sha256_files`, whose thread pool is now sized from the lane (`LP.executor('thread', min(files, lane))`, plain pool of the same width as the fallback) instead of the constant 14. derived-files.md bytes IDENTICAL (toy 3e); the manifest entry gains additive `witness_basis` per file; the receipt's `brain_entry.manifest_entries` projection (name/bytes/sha256/include) is unchanged (3f). Nothing is taken on stat alone (Greg's open call (c) untouched): a changed tail with the same size and mtime refuses and yields the NEW digest (3c); a copy on another inode never matches (3d). | same |
| `_attach_to_brain_entry`, additions loop, MANIFEST dump, fsync loop, rename | serial KB-MB; reads KB files once | unchanged | same |
| MANIFEST read-back compare (v2 ~1258) | KB | unchanged | same |
| **`_pin_outputs`** (v2.py:1272, ~25 files on lane threads) | every file written through `_dump`/`_text` in this process is a cache hit (durable's write-stream witness); the 4 `SE._save`'d package files are read once (GB-class package.source on a full day) | side-written files are hits too (remember); the 4 package files stay (B2) | same |
| receipt `_dump` (MB) | serial | unchanged (the last step) | same |

Toy suite `scratchpad/endings/selftest_classroom.py` (24/24, 9.8 s; run from the repo root with
`PYTHONPATH=deploy/aws/box:. python3 -I`): 1a pooled values == serial, in order; 1b the phase-file pickle bytes
(identity, name, value) byte-equal; 1c placement record (4 workers on this 4-CPU lane, 7 yielded, no deaths); 1d
on_start called once; 1e the serial path (one answer) equal, on_start called, reason recorded; 1f a ModeNotAnswerable in
a worker propagates. 2a side-written files byte-equal to in-process dumps; 2b ran as side processes; 2c one distinct
lane CPU each; 2d pinned; 2e `_pin_outputs` opens 0 files for them (builtins.open/io.open counted); 2f pins = sha256 of
the bytes; 2g the no-fork fallback writes the same bytes in order; 2h a rewrite of equal bytes leaves the file untouched
and returns the remembered witness. 3a the claim yields the same sha256 as hashing (basis claim vs hashed); 3b with the
claim the big file is opened once (the 64 KiB tail) vs once for the full hash; 3c a changed tail with the same size and
mtime refuses the claim (hashed, the new digest); 3d a copy on another inode is hashed; 3e derived-files.md bytes equal
with and without the claim, entry sha256 equal; 3f manifest projection unchanged, `witness_basis` present; 3g
`sha256_files` on the lane executor returns the same values in order. 4a thread value; 4b the raised exception is the
same object; 4c not started -> computed in order. 5 the rates above.

Seconds saved at a2: C4 = 429 s only when ROOT's claim row exists (R1). C1-C3 unmeasurable until the classroom runs
once; on day 1 read `phase_timings.component:*` (now the in-order wait per answer), `cpu_pinning.component_answers.
seconds` (the whole pool), `side_by_side.external_answers.thread_seconds`, `side_by_side.output_writers.tasks.*.
side_seconds`, `picture_texts.characters`. Formula for C3: the three big files each encode ~`characters` bytes of
picture text (plus escaping) at ~293 MB/s and write them at the volume's rate; 1 GB of texts = ~3.4 s + write per file,
x3, now hidden under the grade chains instead of added before them.

Blocked in the classroom (not edited, for Greg):
- B1 `frankie_box_teach.facts` / `_load` (EXHAUSTION_D_CODE): derive.json read whole + hashed by `exhaustion_d_facts`
  and again by `teach.facts._load` (dedupe pass item). An additive `derive=` parameter changes the function-level
  identity every saved classroom binds (a re-pin on Greg's go). Saving: one MB-class read.
- B2 `sunday_execution._save` (byte-pinned by the first run's identity): the 4 package.*.c15.json files are read once in
  `_pin_outputs` (package.source is GB-class on a full day: ~1-2 s page-cache hot). `_save` returning the sha256 of the
  bytes it holds would remove it; needs the prefix-batch re-pin (dedupe request R2).
- B3 the second pass over the shared read (SOCRATIC/VERIFY days) and the anchor-pictures hand-off: market_timeline
  (frozen for a2; dedupe R3).

## 2. Teacher (`frankie_box_experiment_teacher.py`; `parallel_teacher.py` finish already on the lane)

The ending = after `PT.row_pass` (ET.py ~922): `PT.finish` (chunk-start states serial, identity normalizer on a2 =
free; the chunks on 31 pinned spawn workers, in-order join while they run; per-chunk `_save_raw_state` hashed on the
write stream; the attachment hash = one in-memory sha256 of the joined fragments), then the publication tail.

| Step (ET.py now) | Before | After |
|---|---|---|
| `DC.snapshot_teacher_attachment` (1045) | serial pure Python per row (dipole_classroom, cross-owner); reads the attachment, builds NEW rows (verified: `_target_row` per row, `row['dstate'] = state` on the new row; the attachment is never mutated) | unchanged; it now runs BESIDE the attachment writer |
| **attachment pickle** (old 975-982) | serial pickle.dump through `_HashingWriter` (hashed as written, session 5), BEFORE the rows save | `_start_attachment_writer` (ET.py:205-236): when no attachment stands and this process runs one thread (`threading.active_count() == 1`; the prefetch thread joined, the spawn pools shut), a forked side process on one lane CPU (`LP.placement(1, lane)`) runs `_write_attachment` (ET.py:177-187: the same pending-write + `_HashingWriter` + fsync + replace) and leaves the digest in `<attachment>.sha256` (written whole, renamed); `_finish_attachment_writer` (ET.py:239-278) joins it after the rows save, takes the digest, unlinks the sidecar; not startable / died / no digest -> redone here in order (the same bytes). `cpu_pinning.attachment_writer` records outcome, pid, cpu, pin note, seconds. A resume with a retained attachment: no writer (it is hashed on a thread, as before). The forked child pickles the same objects at the same addresses: the same bytes (toy 1b). |
| `SE._save(out / ROWS_FILE, source)` (1080/1082) | serial canonical encoding (pure Python, GIL) of the rows + write (byte-pinned) | unchanged; runs beside the writer |
| rows-file sha256 read-back on a thread (1086) | one read of the just-written rows file on a thread beside the external section (session 5) | unchanged: BLOCKED B4 (`sunday_execution._save` holds the bytes; a returned digest needs the re-pin, dedupe R2). GB-class on a full day: ~1-2 s page-cache hot, overlapped |
| `EXT.ensure_external_section` | serial, overlapped with the hashes (session 5) | unchanged |
| `all99_field`, `workflow_report`, `_publish` (json.dump of the receipt, MB) | serial | unchanged |

Toy `scratchpad/endings/selftest_teacher.py` (7/7): 0 the reference digest = the file's sha256; 1a the writer starts
(one thread here); 1b the side-written attachment is byte-equal to the in-process write and the sidecar digest equals
it (pin note 'pinned'); 1c the sidecar and pending files are gone; 2 an existing attachment starts no writer; 3 a live
thread -> written in order, same bytes, reason recorded; 4 a writer SIGKILLed mid-write -> `redone_in_order`, exit -9
recorded, the same bytes as the reference, no pending file left. (torch stubbed: the attachment carries tensors on the
box; their pickle in a forked child is the same storage bytes, but that is RUNTIME-UNVERIFIED like everything here.)

Seconds at a2: the pickle of the attachment (~1.5 GB of teacher-rows per day in the retained tree, attachment + rows +
states; the attachment itself unmeasured) at ~300 MB/s pickle rate = a few seconds, now overlapped with the snapshot and
the rows save (each likely longer). Small by design; it is one more ending step on its own CPU.

Blocked in the teacher (for Greg): B4 above (R2); B5 the snapshot and the rows canonical encoding are per-row
independent and could be split across workers with exact concatenation, but both live in pinned/cross-owner files
(dipole_classroom.py, sunday_execution.py): a re-pin; saving = (snapshot + SE._save seconds) x (1 - 1/W), unmeasured
(`phase_timings.snapshot_rows_attachment` on day 1).

## 3. Data export + search (`frankie_box_experiment_data.py`, `frankie_box_experiment_search.py`)

Export (`_export` 588-684): the main computation IS `_pin_all` (pinned ordered_map, largest file first, claims taken
under the stat + tail rule: dedupe #7). The ending after it: the producer-pin compare (in memory), the day file read
for its point declarations (MB, page-cache hot after its hash), MANIFEST + workflow_report json.dumps (KB-MB),
`write_text`, `os.replace`. No read-back after a write; nothing to parallelize (KB-MB). Listed: the export's wall on a2
without ROOT's claim rows is ~700 GB of hashing = 636 s sequential-equivalent, ~9.4 min wall on the volume (dedupe R1).

Search (`_search` publish, 3321-3400): part pins are the jobs' write-time digests (session 5; a part without one is
hashed on `LP.executor('thread')` sized from the lane: 3329); the discovery read is cross-checked in memory; MANIFEST
.json of the export hashed once more (KB-MB, a deliberate changed-during-run check); `ALL99.search_coverage`,
`workflow_report`, `compact_report` in memory; two JSON dumps with fsync + the directory rename. No read-back; nothing
of size. The search's heavy items (S0-S2: the frames columns, build_series sources one after another, the single-core
INPUT consumer) are the main computation, not its ending, and stay with the data/search owner.

## 4. School / scientific teacher / survivors / lessons

- Scientific teacher (`main` 2484-2559, `_write_teacher_receipt` 2639-2680): per document `test()` (main computation,
  on the pinned shared pre-read), `all99_for_operation`, `write()` (durable), `witness(path)` = cache hit (durable
  remembers), `publish_lessons` (brain copy of a KB-MB file); receipt json.dumps (KB-MB) content-addressed. Serial
  KB-MB; nothing of size. The `test()` result assembly per claim (school stacks spot 4, 5-20% when claims select many
  rows) is the main computation's tail inside the owner's file: not built (unmeasured; rows would be pickled to workers).
- Accumulated lessons (`teach_accumulated` 440-551): per document `ST.test` (pre-read, session 5) then `write_json`
  (KB-MB) + `witness` (hit) + publication (KB copy); receipt. Serial KB-MB.
- School (`main` 520-609): `build` on the coordinator while the two pointer digests hash on pinned threads (session
  5), json.dumps + `write_school_day` (KB-MB), receipt. Serial KB-MB.
- Survivors (`update` 588-742): select (reads every brain document once: KB-MB each; the dedupe pass's frozen-document
  share), build, coverage per day (serial; pool-able per day, unmeasured: school stacks spot 7), json.dumps of the
  document, `write_bytes`, `write_stage_entry` (a copy), `write_json` receipt + `witness` (hit). Serial KB-MB.
No edit: every ending step here is KB-MB JSON on one CPU (ms to seconds); a fork or pool per step would cost more than
the step. Receipt witnesses after durable writes are cache hits since the dedupe pass.

## 5. Exchange / Jev / voice / meeting

- Exchange (`exchange` 1835-1870, `main` 2152-2236): after the item loop, `full` is assembled, `S.digest(finite(full))`
  and `S.digest(finite(view))` (two canonical passes over the exchange document, MB), then two json.dumps + `write_once`
  (MB), the brain entry (a copy), the receipt. Three to four passes over an MB-class document: seconds at most. The
  ledgers (19 in one pass) and the rows claim are the dedupe pass's. No edit.
- Jev (`_run` 736-856): the scientific test on the pinned pre-read (session 5), `ST.write`, the lesson retain (KB), the
  report render (KB-MB), `pin()` witnesses (filehash cache), `write_json` receipt. Serial KB-MB. The llama.cpp call
  dominates the stage (exchange stacks spot 1: Greg's call (a)).
- Meeting (`_meeting` 2032-2083, `publish_meeting_record` 1639-1683): `write_json(meeting.json)` then
  `witness_file(record_path)` (cache hit since the dedupe pass), `BR.read_meeting_record` (one parse of the MB record),
  `write_meeting_entry` (a copy), receipt. Serial KB-MB. No edit.
- Voice (`frankie_box_exchange_voice.py`): per-item validators, microseconds; not wired. N/A.

## 6. End-of-day reports / inspection / finalization

- Day reports (`_run` 2486-2677): `Day` reads ~15 classroom JSON files once; `collect_all99` reads every piece's
  recorded list once (KB-MB each, `_json_once` / `_pinned_once` with their witnesses in `d.inputs` order);
  `all99_join` in memory; the two reports rendered side by side on forked workers (`render_side_by_side`, session 5),
  written in KINDS order with a save point after each; index + receipt json.dumps (the receipt carries the full all99
  join: MB); `previous = sha256_file(receipt_path)` (KB). Serial KB-MB; reading the ~11 piece lists on threads (reports
  stacks rank 3) would save under a second of page-cache-hot KB reads: not built (the `d.inputs` order constraint is
  real and the gain is noise).
- Inspection (`render_pieces` 1126-1166): the 16 pieces ARE rendered side by side on pinned fork workers through
  `LP.ordered_map` (one worker per piece, `_prefetch` on lane threads, the read ledger merged per piece, output in
  PIECES order; in-process fallback with the reason). The reports stacks pass table said "NOT BUILT (time)"; it was
  built afterwards; confirmed here by reading the code (`_piece_job`, `_RENDER_CTX`, `FRANKIE_INSPECTION_SIDE_BY_SIDE`).
- Finalization (`scan`): identity-bound (NATIVE_VALUE_CODE); 14 helper processes from `placement()` (session 5),
  I/O-bound at the volume's rate. BLOCKED B6: `scan` re-reads the native ledgers for the finalize rows; taking ROOT's
  claim rows (R1) would save the read of exact_member_rows (193.7 GB = 176 s) + exact_lifecycle (6.9 s) per finalization,
  but `scan`'s code identity is pinned (a re-pin on Greg's go); stated, not edited.
- `frankie_box_receipts.provider_invocations`: lane-sized pinned pool (session 5). N/A.

## 7. Ingest / day file / offload

`ingest_block_sources.main` after `ingest()` returns (862-903): the builder checkpoint (canonical bytes of the state:
KB-MB, written with fsync), completion.json, `_journal_sha256` (the digest hashed BESIDE the drain, session 5; a full
read only when the file changed since), the FRANKIE_FILE_CLAIM_V1 row (one 64 KiB read, dedupe #1), the receipt
(`_boxes` = SQLite `count(*)` over the blocks table of the sealed container: leaf pages only, page-cache hot after the
drain), `write_once`. `parallel_ingest` pass 3's tail (690-770): the spools are removed after the sealed container holds
them, the conformance drain is the gold reader on the booked CPUs. Day external, offload (stat-keyed sha256 cache) and
archive (one plan pass, verify by GET) are the ingest stacks pass's. Nothing in the ingest ending runs a second pass
over the journal; the gold stack is byte-pinned (not edited). No edit.

## 8. Why bytes are unchanged

No science file's bytes change. Classroom: the 19 answers are the same values (same function, same inputs, the pool's
pickle preserves object sharing: the saved phase files are byte-equal, toy 1b); the answer files are the same
json.dumps/render written by the same durable call in another process (toy 2a); derived-files.md is the same table with
the same sha256 whether witnessed by claim or by hash (toy 3e). Teacher: the attachment pickle is the same bytes (toy
1b) with the same write-stream digest. Additive only: classroom receipt keys `received.cpu_pinning.component_answers`,
`received.side_by_side.external_answers`, `received.side_by_side.output_writers`; the brain manifest entry key
`witness_basis` on derived-files.md; the teacher receipt key `cpu_pinning.attachment_writer`. Every sha256 recorded is
the same value whichever way it was obtained.

## 9. Not done here, by reason

| Item | Why |
|---|---|
| B1 derive.json read twice (teach.facts / _load) | EXHAUSTION_D_CODE identity (re-pin on Greg's go); MB |
| B2 the 4 SE._save'd package files re-read in `_pin_outputs`; B4 the teacher rows file read-back | `sunday_execution.py` byte-pinned (dedupe R2); GB-class, page-cache hot, ~1-2 s each |
| B3 classroom second pass over the shared read; anchor-pictures hand-off | market_timeline frozen for a2 (dedupe R3) |
| B5 snapshot + rows canonical encoding across workers | dipole_classroom.py / sunday_execution.py pinned (re-pin); unmeasured |
| B6 finalization `scan` taking ROOT's claims | NATIVE_VALUE_CODE identity (re-pin); 183 s of ledger reads per finalization |
| the 17 grade-chain dumps, histories, receipts, brain copies, exchange/Jev/meeting/school/survivor/scientific endings | KB-MB JSON on one CPU: a fork or pool per step costs more than the step (fork of a multi-GB parent ~50-100 ms vs ~1 ms of json.dumps) |
| the external grade chain on a side process | 5 KB-class phases; same reason |
| `collect_all99` reads on threads | KB-MB page-cache-hot reads with an order constraint; noise |
| scientific `test()` per-claim assembly on workers | main computation, not ending; rows pickled to workers; unmeasured |
| CONTENT formats (coupling parts, lessons/survivors/school, numbered reports, Jev's material) | pinned evidence read by other owners; Greg's call (dedupe R5) |

## 10. Cross-owner requests

- R1 (ROOT role; the dedupe pass's R1, repeated because two more consumers now take it): write `<root>/work/
  file-claims.jsonl` with one FRANKIE_FILE_CLAIM_V1 row per spool, layer and native ledger ROOT witnessed whole (format
  `ingest_block_sources.file_claim`: path, bytes, sha256, stat [dev, ino, size, mtime_ns], tail_bytes, tail_sha256 of
  the last 64 KiB, claimed_by). Consumers ready: the data export (`_stage_claims`, dedupe #7: ~636 s) and now the
  classroom's brain publication (`frankie_box_brain.file_witnesses`: 429 s for the 472 GB layer). FOR a2: its ROOT
  sealed on c9bf631 and wrote no claims; writing them at the restage from derive.json's sha256 + a fresh stat and tail
  is Greg's open call (c) in another coat (a claim from the ROOT's own seal record, not from a new read): RELAY.
- R2 (Sunday identity owner): `sunday_execution._save` returning the sha256 of the bytes it holds (B2, B4).
- R3 (market_timeline owner, after a2): start-at-cursor and the anchor-pictures hand-off (B3).
- R4 (Greg): the re-pins for B1, B5, B6 and the measurement on day 1 of the classroom's `phase_timings` /
  `cpu_pinning` / `side_by_side` fields before any further ending change (performance rule: measure, then keep or revert).

## 11. Checks

py_compile + ast.parse on `frankie_box_experiment_classroom_v2.py`, `frankie_box_classroom_code.py`,
`frankie_box_brain.py`, `frankie_box_experiment_teacher.py`; `git diff --check` clean on all four; the toy suites
`scratchpad/endings/selftest_classroom.py` (24/24) and `selftest_teacher.py` (7/7). No fenced file touched
(market_timeline, frankie_queue, experiment, stage_handoff, root_validate, root_move, boss_session, experiment_root,
digest_parallel, digest_document, durable, filehash, day_external; no handoff/boundary/finish_steps function). Other
roles' concurrent edits (root_move.py, E2E doc, experiment.py) were left as found; every edit here was an exact-string
hunk on the current content, compiled after each.
