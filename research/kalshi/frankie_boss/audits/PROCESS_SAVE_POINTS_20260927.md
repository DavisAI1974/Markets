# Monday process save points — 2026-09-27

User direction: principal, classroom and other processes must save completed work and ledgers so an interruption does not require rebuilding them. This is recovery work within the existing manual Monday sequence, not new orchestration.

## First implementation slice — not activated

The new `frankie_box_durable.py` writer creates a unique pending file, flushes and fsyncs it, reads back its full size/hash, preserves any previous target under a content-hash name, atomically publishes the new file, fsyncs its directory and verifies the published bytes. Failed pending writes remain available. It is used under the existing single-session writer ownership; it is not a multiwriter transaction manager.

Principal session JSON artifacts, model result bytes, prompts, notes, responses, correction records and attestations now use this writer. Existing JSON serialization and scientific content are unchanged. The existing writing receipt already pins all four output files; resume now checks those actual file witnesses before skipping writing.

Classroom answers retain request/code/prompt/payload bindings. Each save now reads back through the existing binding checks. Publication verifies both final artifacts against the final receipt before reporting completion. Preservation intents and rename receipts sync their directories. Completed part caches retain their existing resume behavior.

This slice does not alter the active ROOT process, corrected multiprocessing runtime, producer definitions, reducers, model prompts, context/output policy, source binding or authorship.

## Recovery map and remaining work

| Stage | Existing durable boundary | Recovery behavior / remaining gap |
| --- | --- | --- |
| Scientific records | Full terminal controller checkpoint, adapter/driver and closed ledger witnesses | Restore the same terminal generation; no scientific record replay. |
| Projection ranges | Compressed archive plus plan-bound range receipt with byte witness | Verify and reuse completed ranges; retain incomplete attempts. Current ROOT uses corrected runtime 2d3e6bb. |
| Projection publication | Final layer-directory receipt | Interrupted publication retains partial output but may recopy completed layer files. Per-layer publication recovery remains under review. |
| Digest | Private source/table spools, final verification and publication intent/receipt | Scratch is preserved, but current caller uses a fresh scratch directory. Intermediate resumability remains a real gap; not closed by this slice. |
| Principal reading and model answers | Deterministic BOSS job IDs, prompt/request/result/outcome files, part/merge notes | Same request and prompt reuse completed jobs. Atomic local saves added. Serverless provider-loss behavior still requires review. |
| Classroom and scientific dialogue | Identity-bound part answers, prompts, raw exchanges, final ledgers/markdown and receipt | Existing completed answers are reused; atomic saves and immediate readback added. |
| Principal writing | Four output files plus writing receipt and input identity | Resume verifies output bytes before skipping. Incomplete assembly can reuse completed model jobs. |
| Correction | Answer cache, correction response and attestation files, correction receipt | Same correction request reuses its saved answer; atomic session writes added. |
| Host grading | SQLite transactional feedback stages and immutable evidence hashes; host journal checkpoints | Continue the same run and exact WAIT receipt. No new host or scientific pass. |
| Knowledge retention | Manifest-bound brain entries with preserved historical directories | File publication and interrupted-entry recovery still under review. |
| Publication to GitHub | Retained local response artifacts and retryable push | Retry publication from existing session artifacts, without a new calculation. |

## Active ROOT evidence

ROOT 36324470881, PID 59092, corrected code root
`/opt/frankie-box/code/2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a-36323776583-1/markets`.
Calculation root remains `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`.
No duplicate resume or staging was dispatched.

Observer 36325692305 at 14:23Z reported 1,705 completed member ranges, 27,266,382,402 archive bytes (including an in-progress archive), 195,790,802,944 free bytes. The worker receipt retained all 14 actual helper PID/CPU mappings and affinity readback. These are runtime receipts, not an estimated completion.

Latest terminal checkpoint is in `recovery-8c03f629f01747158535f3cfa4f01f2d`:
file SHA256 `2d61559ca9f5c650cdb22fa9aff29b8f0a366a648983493d435c26a3387943e6`,
checkpoint hash `c3281f870a457f9ccf0827ca54a88adc99712cfb6dd3492f7a02a94019bfbecb`,
2,032,203 locked records. Projection/digest/calculations completion is still pending.

The earlier scientific producer verdict remains REJECTED with `cross_section_agreement`; recovery success must never be presented as scientific acceptance.

## Validation and activation

Only exact-source syntax compilation and source review are intended for this save-file slice before activation. No extra scientific test, validator, canary, comparison, ingestion replay or duplicate inference is authorized. Actual save/readback receipts must be collected during the existing downstream execution before claiming runtime verification. Stage a new immutable downstream package only after the remaining recovery gaps are addressed; never hotpatch the running ROOT.
