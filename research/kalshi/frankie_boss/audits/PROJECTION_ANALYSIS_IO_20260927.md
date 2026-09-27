# Projection and analysis preparation — actual observations 2026-09-27

## Scope and live identity
The user authorized checking projection/digest resource use and the remaining analysis preparation for avoidable serial work. This assessment made no ROOT transition, inference, source replay, deletion or infrastructure change. Runtime remains 01caae9d3a0e7ccdb165c734fe25ecf130c5c0f5, workflow36319242284, PID58168, token099d4eb6-a46d-4b94-a888-f15e55c1ee7e:53570313. Calculation root: /opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48.

All2032203 scientific records and finalized ledgers remain retained. The final calculations receipt is not yet published. Principal analysis, actual Granite requests, classroom, grades/corrections and retention remain pending.

## Measured CPU and I/O
Read-only workflow36321527916 sampled the same process from13:11:42.459328Z to13:12:02.461710Z:
-19.29CPU-seconds over20.002387seconds, approximately0.964core.
-Process read-character counter advanced190193664bytes (~9.51MB/s); write-character counter advanced459822782bytes (~22.99MB/s).
-Physical read_bytes advanced190316544bytes.
-RSS2006728KiB, swap0; host memory available roughly254736712KiB. No memory pressure and low I/O waiting during this interval.
-Stage root-projection, failed0.32process threads do not imply32active compute workers. The existing stage-local0/unknown counter is not useful completion progress.

This establishes CPU-limited execution for the observed interval, not a controlled speedup benchmark.

## File position and storage
Read-only workflow36321642052, using committed observere14e679ac8d97610912d90345cea4b8e73206c6f, captured at13:13:40.687399Z:
-Active input exact_member_rows.jsonl:position16787587072 of537182189410bytes (3.12512% by bytes).
-44layer pairs,88open member/lifecycle spool files; their observed total40652336829bytes. Lifecycle spools were still empty.
-Largest open spool full_bid_ask_depth-members.jsonl:24856231174bytes.
-Free filesystem space240395096064bytes.
-Original ledger remains in recovery-9defa3169f7d46679491da2b1bfbbce2; no copy was substituted.
-ROOT affinity permits32logicalCPUs, but source execution remains serial.
The verbose first observation exhausted the SSM output budget before all samples could be parsed; only this complete first file-position sample is claimed. The observer now summarizes spool totals and the five largest spools to preserve complete subsequent samples.

Conditional extrapolations, not ETAs or reserved-capacity predictions:
-At9.51MB/s, the remaining member-ledger read alone is approximately15.2hours, before lifecycle projection, final layer serialization and digest.
-At the observed spool/input ratio, complete member spools would total approximately1.30TB, requiring approximately1.26TB more, versus240.40GB free.
-At22.99MB/s output, that free space corresponds to approximately2.9hours. Record complexity and compression vary; this is not an exact exhaustion time.
Additional copies, final JSON layers and digest scratch are not included in this storage extrapolation. Current capacity cannot be assumed sufficient. Extra CPUs alone do not address expansion.

## Exact source findings
At01caae9:
1. frankie_box_bedrock.py project() parses each member row once, iterates its applicable layers serially, and appends type-preserving intermediate rows through RowSpool. Lifecycle rows and final layer publication follow serially. It has no projection helper pool or resumable projection-batch cursor.
2. RowSpool.append() recursively applies the journal pack codec then JSON-encodes it. write_json() later reads/unpacks those rows and uses Python iterencode(indent=1) to serialize the final layers, then reads each layer again for its hash.
3. frankie_box_digest_sources.py copies and independently hashes every pinned projected layer, parses rows into SQLite, and merges group/column values with per-cell SELECT/INSERT operations. These preserve conflict checks and group ordering; they are not safely removable by treating all rows as independent.
4. frankie_box_digest_document.py processes tables serially. write_table() already inverse-verifies its emitted table; document assembly then inverse-verifies it again and hashes the table before/after. Complete document bytes are hashed at result, intent and publication. Some same-file byte witnesses can potentially be shared with unchanged-file guards, as in finalization. Removing independent semantic proof requires a carefully defined replacement; this audit removes nothing.
5. Principal execution requires calculations-receipt.json and --require-retained-derivation. It reuses science, then runs reading, mandatory classroom, teaching and writing. Classroom14CPUhelpers prepare sources/tokenizers only; they do not accelerate projection, SQLite digest work or GPU generation.

## Concrete next implementation boundary
The demonstrated target is projection's serial parse/project/encode path and its expanded intermediates. A useful fix must address BOTH CPU and disk volume, preserve exact scientific values, causal row order, all required layers/reducers and historical hashes, retain partial outputs, and add durable projection progress/recovery. Bounded CPU processes are appropriate for Python-heavy work; merely adding Python threads is not evidence of parallel CPU execution. Reusing encoded rows and a verified compact or compressed transport should avoid repeated materialization, but all readers and publication receipts must agree on its contract.

Do not silently activate a new format, apply output caps, reduce records/layers, delete older ledgers, or hot-patch this runtime. Any actual transition still requires a fresh verified complete checkpoint and an explicit preserved-output/resume path; the existing terminal-finalize pause mode currently refuses root-projection. No pause was attempted by this assessment.

## Receipts and limits
-36321527916: completed success, actual20-second CPU/I/O observation.
-36321642052: completed success, complete first file-offset/space observation.
-e14e679: committed/pushed metadata-only observer; no active ROOT source mutation.
-No model calls, validators, scientific tests, benchmark/comparison runs or parallel agents.
-No new claim about classroom speedup, Granite learning or Tuesday.

## Authorized fixes — prepared after fresh checkpoint pause

User: "Proceed with fixes". Workflow36322127147 succeeded. At1790515329.6302185 the complete chain, adapter and167213056-byte driver state were freshly read and verified against checkpoint ec90d96d7114dc021cbeb129f5ab91d0756b960e6a81c126a5640f20e1234fff. PID58168 exited on SIGINT at1790515329.8960128; no child remained and no reconstruction is required. Pause receipt1693bytes SHA256239ca57cf41f3e64493f1a55d4edbf93e9714a7b0aaa1de9274a67d6d2cda4c5. Every old projection file remains in place.

The new path is confined to transport/preparation:
-CPU1 coordinator,14processes on physicalCPUs2–15, CPU0reserved. Startup barrier and process-affinity readback precede real work;28pending64MiB ledger ranges maximum. Inputs are immutable sealed ledgers, not source records or calculator replay.
-Each range uses the existing exact crosswalk/select_path and original row ordering, then emits compact JSON inside independently hashed gzip members. One archive and durable read-verified range receipt retain completed work. Adjacent byte coverage and full native ledger row counts are required at completion. Partial archives remain on failure; same-plan completed ranges can be reused.
-Final layer JSON is assembled by joining compressed members in range order. No type-tag spool expansion or serial parse/re-encode pass. New artifacts declare encoding=gzip-json and retain all values. Their byte hashes necessarily differ from old pretty JSON; no historical section or original native ledger hash changes.
-Existing legacy spools and partial original projections are preserved. New output lives under work/derived/.projection-v2. A20GiB reserve refuses additional projection work; no deletion or storage purchase is performed.
-Digest source readers verify and stream the compressed layers, retaining source-reference witnesses rather than another uncompressed copy. Independent layers parse on14CPUhelpers. The already-existing [] leaf-count reducer runs before private SQLite storage; full values remain in pinned compressed layers. Typed group conflicts, original column order and exact reducer semantics remain enforced. Per-cell SQL queries are replaced by one existing-column fetch per group and batched inserts.
-Private SQLite row payloads use lossless zlib; old plain payloads remain readable. Independent bedrock digest tables use14CPUhelpers and publish in their original order. Each table retains its actual inverse proof; file identity and copy-time hash bind that proof to publication, eliminating the duplicate inverse pass.
-The downstream comparison packet consumes current generated layer metadata; it does not load giant compressed layers into RAM. The final principal runtime MUST use this new immutable checkout, including its classroom improvements, rather than the older a80990d checkout.

Verification at preparation: Python syntax compilation in memory and static review of byte-range boundaries, gzip-member joining, resume identity, exact coverage/counts, conflict handling, ordered table joining, inverse-proof binding and cleanup. No extra scientific test, canary, comparison run, validator or model call. Deployment and measured speed/storage results remain pending until actual runtime receipts below.


## Current state — updated after 13:52Z on 2026-09-27

ROOT attempt [36322971264](https://github.com/DavisAI1974/Markets/actions/runs/36322971264) FAILED at 13:49:43Z when starting projection helpers:
`_pickle.PicklingError: Can't pickle ... _initialize ... it's not the same object as frankie_box_projection._initialize`.
The dynamically loaded worker module was not the canonical imported module object. No projection performance result is established.

The correction is committed at **2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a**, ref **codex/frankie-projection-runtime-2d3e6bb**. Both projection and digest-document entry points now use normal canonical imports. Exact GitHub source syntax compilation and import-site assertions passed; actual execution remains pending.

Corrected staging [36323776583](https://github.com/DavisAI1974/Markets/actions/runs/36323776583) SUCCEEDED at 13:52:40Z:
- CODE_ROOT=/opt/frankie-box/code/2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a-36323776583-1/markets
- Pack: 589571847 bytes, 3683 files, SHA256 73144f751c74e960264f0a20a3ad0a3f47f24133fdb9590e29374c29a823200a.
- Intent SHA256 6e1f95f4ccf78a2520fdc4cf1d8b65d5937c2dabfd9bf76cf33238a637325443.
- active_checkout_changed=false; model_calls=0; source_replays=0.
Do not duplicate staging. The corrected runtime has NOT been activated/resumed.

Immediate continuation:
1. Confirm failed PID 58711 is no longer active and inspect latest terminal checkpoint under recovery-fa8af7ed06354468bc526346f90c2291. At 13:48:21Z the generation existed but latest_checkpoint was null while writing; its final saved/read-verified receipt has NOT yet been retrieved. Obtain and freshly verify the complete checkpoint before a runtime transition. Do not infer checkpoint success from workflow failure location.
2. Resume the SAME canonical calculation root using corrected CODE_ROOT and its immutable ref, original authorship/binding, DATA_WORKERS=48, and the actual verified terminal checkpoint. No RECONSTRUCT_MISSING flag, no source replay, no duplicate calculation. The last independently verified parent checkpoint is recorded below.
3. Observe actual 14 helper PIDs/affinities, completed compressed range receipts, free disk and progress; diagnose genuine failures. .projection-v2/plan.json may already exist from the failed attempt; projection code itself is unchanged by the import correction, so valid same-plan ranges can be reused. Verify what actually exists.
4. Continue through calculations receipt and the existing Monday manual sequence. Use corrected 2d3e6bb runtime for downstream digest/principal/classroom.
5. Report actual receipts; Monday completion, actual classroom delivery/acknowledgement, Tuesday and learning outcomes remain pending.

No new resume was dispatched before handing off. This fresh chat owns the next execution.


## Corrected runtime resumed — 2026-09-27 14:09Z

The continuation owns one existing-root resume: [36324470881](https://github.com/DavisAI1974/Markets/actions/runs/36324470881), dispatched at14:02:12Z on immutable ref `codex/frankie-projection-runtime-2d3e6bb`. Runtime/CODE_ROOT are the corrected2d3e6bb package below. No duplicate staging or new calculation root was created; original authorship/binding and DATA_WORKERS=48 remain unchanged, with no reconstruction flag.

Fresh progress [36324313108](https://github.com/DavisAI1974/Markets/actions/runs/36324313108) confirmed oldPID58711/process-token53962300 inactive. Terminal checkpoint000000 in recovery-fa8af7ed06354468bc526346f90c2291 was retrieved:
- Checkpoint file712bytes SHA256a4bde7bd1fb75bb7162da4000f6f379bc97ef554aa036c42e4893533d4294bf3; checkpoint hash9c2ae2c0873e7803e09ebffbaec719cdcc2caa3502e4540136c635d5adaedba1.
- Descriptor12885bytes SHA256983e73528383a5d53eea6517cbda3a2e29ef21f18a02b1f00b32ab3a430a0a2c, independently read in36324379542.
- Full driver167213128bytes SHA2562d80a0b739983b5349a91ed077adea69f3e60d5514855958f7c974a9429b167f.
- Locked/finalized,2032203records, all three original closed/materialized ledger paths and hashes retained.
- Full producer receipt30104bytes/937lines retrieved through36324588283 plus36324690302 (SSM truncates the first read). It reports checkpoint readback_verified=true, restored_state_records=2032203, authorized_reconstruction_records=0. Its scientific verdict is REJECTED, failed_gates=[cross_section_agreement]; preserve this result for analysis, not a successful scientific verdict.

The existing resume reader freshly verifies checkpoint chain, adapter, descriptor/runtime and full driver bytes before restore_closed. Live progress36324667483 reached root-ledger-verify-member, proving those required reads passed. NewPID59092, process token099d4eb6-a46d-4b94-a888-f15e55c1ee7e:54118158, original binding99440a65fe5ad6fa93fbeebdfda3391d9dfcbf58abb3251661e6f76adea2d90a.

Resource observation36324844551 at14:09:18Z: retained member verification311905222656/537182189410bytes, failed0, coordinatorCPU1,223811674112bytes free. It is still recovering finalized state, not replaying scientific records. Checkpoints.json still names oldPID58711 until the new terminal checkpoint is saved; do not mistake that old event for a new checkpoint.

Projection observation36324486562 at14:02:53Z: preserved plan370208809bytes SHA2563ef241ac435253142680040976ab6f548b3119b1d73f26e6ca95bb9f78cb73b2; no completed ranges, archives or worker receipt yet. Actual corrected projection startup/helpers, range progress, new terminal checkpoint, digest and calculations receipt remain pending. Keep the active resume running; do not dispatch another.

All downstream Monday stages, actual Granite lesson delivery/acknowledgement, Tuesday and learning outcomes remain pending. Orchestrator stays PLAN ONLY. Existing preservation and scope restrictions below remain in force.

