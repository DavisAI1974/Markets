# Dedupe pass, 2026-10-08 (session 6): every workflow piece after ROOT, in run order

Owner: the workflow-dedupe role (parent-only session; agents do the work). Greg, 2026-10-08, verbatim: "Then eliminate
redundant steps" and "send dedupe agent out in the rest of the workflow process too from beginning to end." ROOT is another
role's (its item (c), `parallel_teacher._save_raw_state`, `boss_session`, `experiment_root`: not touched here). Branch
`ccr-d2f8f826-iefeah-frankie`; the edits were made on bcaf1d6..0b85c53 and the parent snapshotted them as they landed
(4433e04 granite_meeting; b474c51 adviser_market, exchange, jev_cpu, teacher_knowledge, parallel_ingest; later snapshots:
ingest_block_sources, experiment_data, exchange rows claim, joined_teacher). Greg's "start, we don't have time to waste":
tip 0b85c53 was staged on the box with the edits it held; the rest land in a later restage.

**SOURCE-BUILT / RUNTIME-UNVERIFIED.** py_compile + ast.parse on every edited .py, bash -n on the three owned .sh (unchanged),
git diff --check clean, and the toy suite below (23/23, this container, Python 3.13, torch stubbed for the research package).
Nothing ran on the box; no AWS call; no install; nothing committed by this role.

Rule applied (the brief): three kinds of dedupe, COMPUTE (the same bytes read/hashed/decoded twice in one run), PASS (a
sub-step re-walking data another walked), CONTENT (the same content rendered twice into files other stages compare). A read
is eliminated only where an EXACT cheaper check replaces it (a saved claim + stat + last line/last 64 KiB, the session-5
spool-resume pattern of `frankie_box_boss_session._resume_row_spool`), or where the same bytes are already witnessed in this
process (`frankie_box_filehash.witness`, the stat-keyed once-per-run cache; `remember` for files `frankie_box_durable`
wrote). Never by removing a verification; every skip is on the piece's receipt as `hash_basis` / `rehash_rule`; every
output byte and every existing receipt field unchanged (additive keys only). Nothing is skipped on stat alone: Greg's open
call (c) is untouched; where a claim + stat + tail check now replaces a full read, the full read still happens the first
time, by the stage that wrote the claim.

Rates for the savings column: 1.09-1.25 GB/s sequential (the probe's measured read-back rates on the box); a2's sizes from
`scratchpad/probe/PROBE_20261008.md` (frames.jsonl 496,743,568,399 B; structures.jsonl 1,063,001,944; input spool
537,361,074; exact_member_rows.jsonl 193,743,650,444; exact_lifecycle_rows.jsonl 7,560,352,552; legacy_observable_rows.jsonl
742,788,266; the sealed 20231018 journal ~23.7 GB per the export's own docstring; the Granite 4.2 3B Q4_K_M weights ~2 GB,
the pin's exact bytes are on the box). Seconds = bytes / 1.1 GB/s unless stated; sha256 CPU rides on the same pass.

## 0. The compact table (what changed; the rest of this file is the per-piece detail)

| # | Piece (run order) | Kind | Before (file:line) | After | Saved at a2's sizes | Exactness / basis | Test |
|---|---|---|---|---|---|---|---|
| 1 | ingest | COMPUTE (cross-stage, producer side) | the sealed journal's whole-file sha256 (hashed beside the drain, `_HashBeside`) reached only the receipt (ingest_block_sources ~839); every later stage re-hashed the journal from byte 0 | `file_claim` + `write_file_claims` (ingest_block_sources after `_journal_sha256`): `<ingest>/file-claims.jsonl`, one FRANKIE_FILE_CLAIM_V1 row (path, bytes, sha256, stat[dev, ino, size, mtime_ns], sha256 of the last 64 KiB, claimed_by); receipt gains `file_claims` (additive) | enables #7 (journal 23.7 GB = 21.5 s per taker); costs one 64 KiB read | a claim is a hint; refused when the bytes count differs from the measured one; a missing or unreadable file costs nothing but the taker's full hash | ingest: 3 cases |
| 2 | ingest (resume) | COMPUTE | `_sha256_file(states_path)` + `_sha256_file(pickles_path)` (parallel_ingest ~583-584) then `read_bytes()` of both again (~626-627) | one `read_bytes()` each, the sha256 from those bytes, the parse from the same bytes | 2 reads of MB-class files (resume only) | identical values; the refusal text unchanged | source pattern case |
| 3 | teacher (accumulated) | COMPUTE | `witness(manifest_path)` (durable, streamed) + `read_bytes()` + a second sha256 + a changed-between-reads guard (teacher_knowledge 165-168) | one `read_bytes()`, witness from those bytes | 1 read of the owning search MANIFEST (KB-MB) | the guard protected the window between two reads; with one read the parsed bytes ARE the witnessed bytes | source pattern + value-equality case |
| 4 | teacher (joined, Monday path) | COMPUTE | `witness(receipt)` then `read_bytes()`; `witness(derive)` then `extract()` `read_bytes()` again (joined_teacher 763-770, 264) | each read once; `extract(..., derive=None)` additive takes the parsed body | 1 read of derive.json (MB-class) + 1 of the receipt | same values; `extract`'s positional contract kept | source pattern + signature case |
| 5 | exchange (context-only -> exchange step) | COMPUTE (cross-process, claim + stat + tail) | the exchange step read and re-hashed the whole rows file before taking the context-only step's saved ledger measurement (exchange `teacher_rows` 531-535) | the ledger-save manifest records `rows_file_identity` (stat + last 64 KiB; additive); `_claimed_rows_pin` takes the rows claim only when both still match, then `_load_ledger_save` as before; notes carry `rows_claim` and `rows_hash_basis` (claim / hashed) | one full read + sha256 of the per-day rows file (`host-dipole-classroom-source.c15.json`; unmeasured here, the retained teacher-rows tree was 24.86 GB over its days) | ROOT's `_resume_row_spool` rule mirrored; a changed tail with the same size and mtime refuses the claim and reads in full; the pickle's own bytes/sha256 and the code identity are still checked | 4 cases incl. the refusal |
| 6 | exchange / adviser | COMPUTE | `sha256_bytes(path.read_bytes())` of the just-written `shared-market-context.json` in context_only (2012) and in the exchange step (2115); `retain_context` returned `durable.witness(path)` right after `write_bytes` (adviser 2086) | `_file_witness` (exchange) and `frankie_box_filehash.witness` (adviser): the write-stream witness `remember`ed by `write_bytes` serves both with no read-back | 2 reads of the context file (MB-class; it holds the picture text) | same {bytes, sha256}; the local loop is the fallback when the cache module is absent | 1 case (opens 0) |
| 7 | data export | COMPUTE (cross-stage, consumer side) | `_pin_all` hashed every linked file from byte 0 unless the export itself had saved (experiment_data `_pins_progress` 255-292) | `_stage_claims(dirs)` reads `file-claims.jsonl` / `work/file-claims.jsonl` from every stage directory; `_pins_progress(..., claims)` pins a linked file from a claim only when its (dev, ino, size, mtime_ns) AND the sha256 of its last 64 KiB equal the claim's (the same rule the export already applies to its own after-save rows); MANIFEST `hashing.claims` (files read, rows, accepted {path: hash_basis claim, claimed_by, claim_file, rehash_rule}) and `save_point.rule` name it | NOW (ingest's claim): the journal, 23.7 GB = 21.5 s. WITH ROOT's claims (request R1 below): frames 496.7 GB (452 s) + exact_member_rows 193.7 GB (176 s) + exact_lifecycle 7.6 GB (6.9 s) + structures 1.1 GB + legacy_observable 0.7 GB + input 0.5 GB = ~700 GB = ~636 s sequential, ~9.4 min wall on the 1.25 GB/s volume (the export's hashing is disk-bound) | the hard link shares the inode, so a copy never matches; a tail change with the same size and mtime refuses; no claim = byte 0 as before; `expected` (the ingestion receipt's journal pin) is still compared | 5 cases incl. 3 refusals |
| 8 | exchange / Jev / meeting | COMPUTE | the meeting hashed the GGUF weights, llama-server and every extracted runtime file FOUR times in one process with its own loop (`witness_file`: gate inside `local_runtime` 218, gate again 1813, binding 1854, record 2027) and read back every file it had just written through durable (meeting.json, receipt inputs) | `witness_file` -> `frankie_box_filehash.witness` (stat-keyed once per process; a file changed while hashed is refused); the local loop is the fallback | 3 reads of ~2 GB weights = ~6 GB = 5.5 s + 3 sha256 passes, plus 3x the binary and the extracted libraries (tens of MB) and the written-file read-backs; the second gate (session-5 "exchange spot 4") now reads 0 bytes | same bytes, same sha256, same key order (path, bytes, sha256) | 3 cases incl. "changed file re-hashed" and "ctime moved: re-hashed" |
| 9 | Jev | COMPUTE | `pinned(pin)` witnessed a file (durable, full read) and `pin(path)` witnessed it again; the own brain entry was witnessed after `write_json` (jev_cpu 260/266, 716) | `witness` -> `frankie_box_filehash.witness` (fallback: durable's) | 1 read per pinned input (lessons/entries, KB-MB) + the entry read-back | same values; a differing pin still refuses | 2 cases |

Not changed, with the reason (section 10); cross-owner requests (section 11).

## 1. Ingest / day file / offload (`operations/ingest_block_sources.py`, `parallel_ingest.py`, `ingest_cpus.py`, `compact_build_journal.py`, `frankie_box_ingest_block.sh`, `frankie_box_offload.py`, `frankie_box_archive_day.py`, `frankie_box_pull_runner_ingest.sh`)

Session-5 F rows re-read (STACKS_PASS_20261007_INGEST.md F1 a-e, spots 4/7/9, save/restore item 3): the fetch hashes
in-stream (done); the receipt hash runs beside the drain (done); a resume's `_done` takes the unchanged spool with no read
(done). Walked again:

- BUILT (#1): the journal's claim row. `file_claim(path, bytes, sha256, claimed_by)` reads the last 64 KiB only (the whole
  file was hashed by `_HashBeside` beside the drain, or by `sha256_file` when that value was stale); `write_file_claims`
  rewrites `file-claims.jsonl` whole (pending + rename, fsync) and never raises: the receipt's additive `file_claims` says
  written / not_written with the reason. The receipt's `journal_sha256` is now computed once into a local (`journal_sha256`)
  and used by both the claim and the receipt: the same value as before.
- BUILT (#2): the resume's double read of `segments/states.c15.json` and `adapters.pickle`.
- STAYS, F1 (a): `mbo_source._verified_copy` (pinned extractor, security snapshot) copies each partition while hashing and
  `_decompressed` re-reads the copy: the TOCTOU snapshot; not editable.
- STAYS, F1 (b): `fetch_sources` (`--fetch`) hashes a member already present (561) and `_verified_copy` hashes it again. Not
  a2's path: a2's wrapper fetched with ACTION=fetch (in-stream hash, its own process) and the tool ran without `--fetch`,
  so the partition was hashed exactly twice across the day (fetch stream + the pinned snapshot). The present-check's hash
  decides the receipt's `present` vs `refused` status, which `_verified_copy`'s later refusal would not report the same
  way: not an exact replacement.
- STAYS, F1 (e): the conformance drain (`compact_build_journal` 311: every block's sha256 + chain) is the gold verification
  pass and reads through SQLite, so the whole-file sha256 cannot come out of it; it runs beside it on a thread (page cache
  shares the bytes).
- STAYS: `parallel_ingest` pass 3 hashes each finished spool while it reads it (705-712): one pass.
- STAYS: `frankie_box_offload._sha256` already skips by a sidecar claim keyed on stat (`sha256_basis` hashed/cached on every
  pointer; the transport verifies the bytes it sends). `frankie_box_archive_day`: `plan` hashes whole + per-piece in one read
  (182-195); `upload`'s `present` path re-hashes a local slice only on a retry where the object already exists (a check of
  the local file against the plan); `verify` streams the objects back (that IS the verification). `pull_runner_ingest.sh`:
  the ranged download lands out of order on threads (pwrite), so an in-stream ordered hash would serialize it; the one
  read-back per landed object runs while the others download (page-cache hot). `ingest_cpus.py`: placement only, no reads.
- CONTENT: the fetch receipt repeats the transport receipt per member (session-5 F3, accepted: the shared schema). Gold
  journal bytes untouched.

## 2. Teacher (`frankie_box_experiment_teacher.py`, `parallel_teacher.py`, `frankie_box_teacher_knowledge.py`, `frankie_box_joined_teacher.py`, `frankie_box_teach.py`)

- BUILT (#3): `teach_accumulated`'s manifest read once. R3 (one shared `ST.pre_read` + `test(scanned=)` for every document
  of the accumulated step) was already built in session 5's follow-up (teacher_knowledge "Phase 1" at ~345): confirmed
  present, nothing to add. R4 (jev_cpu's native-then-test in series) is built too (jev_cpu 733-742: `ST.pre_read` when the
  scientific teacher has it, `test(scanned=)`).
- BUILT (#4): the joined teacher (the Monday path, not a2's) reads the receipt and derive.json once each.
- STAYS (teacher request 2, the rows file read-back, ET 983 `SE._save` then `hash_on_thread('rows')` 984/1017):
  `sunday_execution.py` is BYTE-PINNED by the first run's identity (`sunday_20260915_package/WORKING_TREE_IDENTITY_BYTES_20260915.json`,
  `FB/actual-feedback-run/host-identity.c15.json`, AUTHORITY_MAP): changing `_save` to return the sha256 of the bytes it
  holds changes those pins and the host refuses cycle 0 until the prefix batch is re-pinned. Computing the canonical bytes
  a second time in ET to hash them would cost more CPU (json dump of a GB-class body) than the read it removes. Today the
  read-back is page-cache hot and runs on a thread beside the external section. Request R2.
- STAYS (`parallel_teacher._save_raw_state` write-then-re-read): the ROOT-dedupe role's item (c), by the fence.
- STAYS: the resume re-read of the shared picture from instant 0 (market_timeline frozen; cross-owner, after a2).
- STAYS: ET `_sha256(receipt_path)` 497 and `_sha256(day_file)` 511 are each one read of a file this process reads once
  (the receipt's `read_bytes` at 518 is the parse of a KB file). `directive_witness()` reads the directive JSON (KB) three
  times per receipt (601, 915, 992): KB-class, listed only.

## 3. Classroom (`frankie_box_experiment_classroom_v2.py`, `classroom_reader` / `classroom_code` / `classroom_workers` / `classroom_cache`)

- Already one pass where it matters: the journal witness is measured once (filehash) and handed to the core; the attachment
  is read once, hashed in memory and unpickled from the same bytes; `_dump` -> `_text` -> `_bytes` -> `durable.write_bytes`
  remembers the write-stream witness, so `_sha256(native_path)` 896 and `_sha256(facts_path)` 916 after their `_dump` are
  cache hits (no read-back): verified by reading `_bytes`/`_dump` (v2 76-88) and `frankie_box_durable.write_chunks`.
- BLOCKED (identity-bound): derive.json read whole + hashed by `exhaustion_d_facts` (classroom_code 2402-2407) and read again
  by `frankie_box_teach.facts` -> `_load` (teach 41-42, 206). `facts` and `_load` are in `EXHAUSTION_D_CODE` (v2 99-104);
  an additive `derive=` parameter on `facts` would change the function-level identity every saved classroom binds. Not
  edited. derive.json is MB-class (listed, not measured here).
- STAYS (design): the classroom's full ordered read of the shared market repeats the teacher stage's read of the same
  source; on SOCRATIC/VERIFY days the learner walk adds a third (session-5 F2). The teacher's anchor-pictures hand-off
  (classroom request 6.1/6.2) is a market_timeline change (frozen for a2). Request R3.
- STAYS: the day file is read twice in the classroom process (v2 542 `_sha256(day_file)` streamed; classroom_code
  `external_points_use` 2646 `read_bytes` + hash for the parse). The parse needs the bytes; passing them from v2 into
  `external_points_use` (called from classroom_code ~2531) is a small plumbing edit not made here (MB-class file). Listed.
- STAYS: calculations-receipt.json / source-binding.json / teacher receipt read 2-3 times each (v2 479/639/675, classroom_code
  2402, classroom_reader 48/52): KB-class JSON; merging them means passing parsed objects across owner boundaries.
- CONTENT: Jev's material `classroom-request.json` bytes are pinned on the receipt and checked on resume; stacking belongs to
  the relay's render (already STACKED_TEXT_V1 + DIGEST_V10, parse-back proven).

## 4. Data export + search (`frankie_box_experiment_data.py`, `frankie_box_experiment_search.py`, `experiment_journal` / `dipole` / `surface` / `transforms`)

- BUILT (#7): the export takes an earlier stage's claim under the stat + tail rule. Today only the ingest writes one (the
  journal); the ROOT spools and native ledgers need ROOT's claims (R1). The `expected` journal pin from the ingestion receipt
  is still compared with the pin (claimed or hashed). The after-save path and `FRANKIE_EXPORT_REUSE_PINS` are unchanged.
- STAYS: the search re-verifies the export's pins while it decodes (`FrontierHasher` beside `spool_columns` /
  `decoded_spool` / native / journal: one disk pass shared through the page cache; the hash is CPU beside a needed read).
  MANIFEST.json hashed three times per search (1974, 3014, 3343): KB-MB, deliberate changed-during-run checks, kept.
  `_cell_job` 2594 re-hashes each coupling part right after writing it (page-cache hot; hashing as written would cost the
  same sha256 CPU; on a save the partial's hash is the saved cursor's verification): listed, not built.
- CONTENT (session-5 R4): coupling-part rows repeat day/cycle/day_role and `transform == x_transform`; a keys-once rendering
  is a format change for the scientific teacher, review and survivor readers: Greg's call, not built.

## 5. School / scientific teacher / survivors / lessons (`frankie_box_school_knowledge.py`, `frankie_box_scientific_teacher.py`, `frankie_box_survivor_update.py`)

- Session 5 built the shared pre-read (`pre_read` / `shared_scan` / `test(scanned=)`), the survivor F4 frozen-restart dedupe,
  and `_finalize_rows` hashes while it streams: confirmed.
- STAYS: a large part is read twice (`_part_tasks`: one 'hash' task + its 'range' tasks): sha256 is sequential, so the range
  scans cannot produce the whole-file digest; the page cache serves the second reader when the part fits.
- STAYS: `R.corrections(LS.knowledge_roots(a.brain))` per reused document inside the teacher loop (scientific_teacher 2510;
  session-5 spot 8): KB-MB reads; hoisting it changes nothing measurable and the loop's publication order is binding.
- STAYS: school `Section.subset` (226 + 164) reads a small file twice; `pointer` hashes big files once on the prefetch pool;
  survivor `select` reads each brain entry once and verifies in memory; the receipt witnesses after `write_json` (school 465/
  484/503, survivor 740) are durable's full reads of KB files (a filehash route would make them cache hits; not done, KB).
- CONTENT (R5): lessons / survivors / school files are pinned evidence hashed byte-for-byte by other owners: Greg's call.

## 6. Exchange / Jev / voice / meeting (`frankie_box_experiment_exchange.py`, `frankie_box_jev_cpu.py`, `clm_sidecar/sit_in.py`, `frankie_box_granite_meeting.py`, `frankie_box_exchange_voice.py`, `frankie_box_adviser_market.py`)

- BUILT (#5, #6, #8, #9) above. The meeting's double gate (session-5 exchange spot 4): the second `gate()` call stays (it
  re-checks the pins against the files at the moment the items start) but every witness in it is now a cache hit; the two
  gates read 0 bytes the second time. The exchange's `_ledgers_one_pass` (19 ledgers in one pass) is session 5's; the rows
  file itself is now read once across the two steps.
- STAYS: `sit_in.py` hashes request/response bytes in memory (no file re-reads); `frankie_box_exchange_voice.py` reads
  nothing twice. The adviser's `_PinHasher` hashes the journal and every layer spool once per process on pinned threads;
  the reader's own selected_files check hashes the native ledgers (market_timeline, frozen). Across processes (teacher,
  classroom, context-only, Jev) the sealed journal is hashed once each: 23.7 GB x 4 = ~86 s of read, 3 of them overlapped
  with other work. The ingest's claim row (#1) is the exact cheaper check each could take; whether a consumer may take a
  producer's claim for its input verification is Greg's open call (c) ("the resume witnesses"), so no consumer was changed
  except the export (#7), whose own after-save rule already accepted stat + tail claims.
- CONTENT: the system prompt (charter + whole picture) is re-sent on every coordinator call (stateless chat); llama-server's
  prompt cache reuses the KV, tokens on the wire are not deduped (session-5 F3, unchanged).

## 7. End-of-day reports / inspection / finalization (`frankie_box_experiment_day_reports.py`, `frankie_box_workflow_inspection.py`, `frankie_box_finalization.py`, `frankie_box_receipts.py`, `frankie_box_all99_coverage.py`)

- Session 5: inspection `read_object` cache (one read per artifact), `Day._read` once, receipts `_witness` through filehash.
  Confirmed. `collect_all99` reads through `Day._read` / `_step` (one read each).
- STAYS: `late_pieces_changed` re-reads the pieces by design (a separate pure call the Run makes to detect late changes);
  the reuse path re-reads each existing report to check its sha (the seal); X4 (experiment.py 2373-2377 re-reads both reports
  to log them) is a never-touch file. `sha256_file(receipt_path)` of the previous receipt (2665): KB. Finalization `scan` is
  the verify and identity-bound (NATIVE_VALUE_CODE). The numbered reports' bytes are pinned by E (no CONTENT change).

## 8. Tests run (scratchpad `workflow_dedupe/selftest_dedupe.py`, this container; `PYTHONPATH=deploy/aws/box:. python3 -I ...`)

Each case counts opens-for-reading of the file under test (builtins.open and io.open, which Path.open uses), compares the
value with a plain hashlib pass, and shows the refusals still refuse. Output (23 cases, 0 failed):

- meeting: witness_file x4 on the same model file opens it ONCE (values equal, key order path/bytes/sha256); a changed model
  file is hashed again; same size and mtime restored but ctime moved: hashed again.
- jev_cpu: pinned() then pin() reads the input once; a differing pin still refuses.
- exchange/adviser: a file written through durable.write_bytes is witnessed with no read-back (opens 0).
- ingest: file_claim + write_file_claims write one FRANKIE_FILE_CLAIM_V1 row (path, bytes, sha256, stat[4], tail); a claim
  whose bytes differ from the file is refused.
- export: _stage_claims reads the stage claims; the linked file is pinned from the claim with one 64 KiB read (basis claim);
  without a claim the same pin is hashed from byte 0; a changed tail with the same size and mtime REFUSES the claim (full
  hash, new pin); a copy (other inode) never matches a claim.
- exchange rows: _rows_file_identity = stat[4] + last-64-KiB sha256; the claim is taken on the unchanged file (one tail read);
  teacher_rows returns the saved measurement from the claim without reading the rows (basis claim); a changed tail refuses
  the claim: the rows are read in full and hashed (basis hashed).
- source patterns: parallel_ingest resume single read; teacher_knowledge single read equal to durable.witness; joined_teacher
  single reads and extract's positional contract.

Checks: py_compile + ast.parse on the 9 edited .py; bash -n on frankie_box_ingest_block.sh, frankie_box_pull_runner_ingest.sh,
frankie_box_granite_meeting.sh (unchanged); git diff --check clean.

## 9. Why bytes are unchanged

No science file's bytes change: the ingest's journal, the teacher rows and attachment, the classroom's answers, the search
parts and MANIFEST, the lessons, the meeting record are written exactly as before. Additive only: `file-claims.jsonl` (a new
file beside the ingestion receipt) and the receipt key `file_claims`; the export MANIFEST's `hashing.claims` and the
`save_point.rule` suffix; the exchange ledger-save manifest's `rows_file_identity` and the notes `rows_claim` /
`rows_hash_basis`. Every sha256 recorded is the same value whichever way it was obtained (witnessed from the write stream,
from the once-per-process cache, or from a claim whose stat and tail were checked).

## 10. Not done here, by reason

| Item | Why |
|---|---|
| teacher rows file read-back (ET 983/1017) | `sunday_execution.py` byte-pinned (R2) |
| `parallel_teacher._save_raw_state` write-then-re-read | ROOT-dedupe role's item (c) |
| derive.json read by `exhaustion_d_facts` and again by `teach.facts._load` | `facts`/`_load` in EXHAUSTION_D_CODE (identity-bound) |
| classroom's second pass over the shared read; teacher anchor-pictures hand-off | market_timeline frozen for a2 (R3) |
| consumers taking the ingest's journal claim (teacher, classroom, adviser, Jev: 4 x 21.5 s) | Greg's open call (c); the claim row now exists (R4) |
| ROOT's spools and native ledgers claimed into the export (~700 GB, ~9.4 min wall) | ROOT role writes the claims (R1) |
| day file read twice in the classroom process | MB-class; needs bytes plumbed into `external_points_use` |
| `_cell_job` part re-hash after write; large-part hash task + range scans | page-cache hot / sha256 is sequential |
| school/survivor receipt witnesses after write (durable full reads of KB files) | KB; a filehash route is a one-line change each if wanted |
| CONTENT formats (coupling parts, lessons/survivors/school, numbered reports, Jev's material) | pinned evidence read by other owners; Greg's call |

## 11. Cross-owner requests

- R1 (ROOT role, `frankie_box_boss_session` / `experiment_root`): at the seal, write `<root>/work/file-claims.jsonl` with one
  FRANKIE_FILE_CLAIM_V1 row per spool and native ledger ROOT witnessed whole (`spool_witness`, the legacy-stage artifacts):
  path, bytes, sha256, stat [dev, ino, size, mtime_ns], tail_bytes, tail_sha256 (last 64 KiB), claimed_by. The export already
  accepts them (#7); the stat and tail cost nothing beyond a 64 KiB read per file. Format: `ingest_block_sources.file_claim`.
- R2 (Sunday identity owner): `sunday_execution._save` returning the sha256 of `raw` (it holds the bytes) needs a re-pin of
  the first run's byte identity; until then the teacher's rows read-back stays (page-cache hot, on a thread).
- R3 (market_timeline owner, after a2): start-at-cursor and the anchor-pictures hand-off (the classroom's second pass).
- R4 (Greg's call (c)): whether a consumer stage may verify its sealed input by the producer's claim + stat + last 64 KiB
  (the ingest's `file-claims.jsonl` row) instead of a full re-hash: teacher, classroom, context-only, Jev would each save
  ~21.5 s on the 23.7 GB journal (3 of the 4 overlapped today).
