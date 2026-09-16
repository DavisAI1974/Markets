# Frankie/BOSS consolidated sheet - lawful recovery state and condensation plan (2026-09-15)

This sheet collapses `CCODE_REVIEW_LAWFUL_RECOVERY_20260915.md` (first pass), the second-pass
review of the blocker ports, and `CLAUDE_TOKEN_CONDENSATION_AND_CYCLE_REUSE_ADDENDUM_20260915.md`
into one document. It is meant to open the next chat. Everything measured here was measured on
the E:/Codex/Frankie-BOSS-20260915 runtime read-only, on the E:/Markets checkout of
`chatgpt/frankie-lawful-recovery-clean-20260915` at `2c4996f4`, or on scratch clones. The
original failed run directory was hash-inventoried before and after every scratch run and is
byte-identical. Nothing was launched against Granite, Frankie, market data or the retained Pod.

## Part 1 - where the recovery stands

### 1.1 Lineage and package (settled)

- Clean branch descends from the failed run's `boss_commit 050c5056`. Compact reader, compact
  snapshot code, schedule verifier, host, checkpoint and context session are byte-identical to it.
- Restoration package grafted by object identity (trees `4a228898`, `0f6615cb`, manifest blob
  `43fba82e`). 170 small files in git; 27 bulk files (18.35 GB) hash-pinned for object storage.
- Bulk-hash gap closed: `source.sqlite` (11,700,711,424 bytes) sha256
  `181467d12a3ea289e67141be2f73e2c5ec068661c5c66c75c51eb30a2787dd6a`, addendum sha256
  `56b669aa1542fbf29fa0fd9870347a144ba589385fce0e9982487bee58580636`; audit 27/27.
- Windows RSS probe fixed (untyped pseudo-handle dropped every process field); tested.

### 1.2 Second pass: the two blocker ports

**Pod migration port (`aa12fd09` -> lawful lineage): complete and equivalent.** Mechanical
check: every added/removed line in the seven ported files is identical to the `aa12fd09` hunks,
and the file set is the same. Three of the files had other, unrelated changes on the divergent
lineage before `aa12fd09` (`be6a1fbd` capacity-retry, `45d57869` safe attribute names); those
were correctly NOT imported, and the migrated flow does not depend on them because a RUNNING
migrated Pod returns `observe_migrated_start` before any start POST. The chain is: receipt
(`granite_retained_migration_receipt.json`, source pod `jvs75m56w8f73q` -> `ycf4v6lmave6xw`,
`INFO_SHA256 0e059d18...`) -> `info_from_journal` rewrites the retained old pod-info into the
migrated identity and checks the canonical hash -> `start_once` validates a RUNNING
`-migration`-named Pod with `validate_running_migration` (status temporarily treated as
EXITED for the stable-field comparison, then restored) and never starts it -> completion and
journal generation pinned to `migration-ycf4v6lmave6xw`. Proven live in this pass: with the
reviewed `POD_ID` applied in memory, the lawful host's own `verified_service_inputs` passed
against the real readiness directory at 56 s, where the unported lineage failed at 62 s.

**Sidecar restart trap: fixed for the EC2 path, and the fix is exactly one predicate.** A
normalised diff of `source_lineage_resume.verify_closed_source_lineage` against the lawful
`ActualHost.source_lineage` shows a single differing line: `_sidecars(path)` in place of
`any(Path(str(path)+suffix).exists() ...)`. Everything else (recovery receipts, parent file
hash, parent tail, child anchor, source-origin bookkeeping, the lineage witness save) is
identical. The lawful host file is untouched; only `run_actual_sunday_ec2.py` subclasses it.

Two-invocation proof and the fail-closed proofs: see 1.4.

**Completion lineage: commit-bound, ref only selects the workflow file.** The host dispatches
`gh workflow run frankie_retained_completion.yml --ref <completion_workflow_ref>` with
`inputs.code_commit = host_runtime.boss_commit`; the workflow checks out exactly
`inputs.code_commit`; `publish_completion` refuses unless `git rev-parse HEAD` equals it. So
code drift fails closed. What the ref decides is which copy of the workflow YAML executes.
The builder now refuses the divergent branch but does not check that `boss_commit` is
reachable from the ref at generation time; add `git merge-base --is-ancestor <boss_commit>
<ref>` (via ls-remote) to the builder so the YAML that runs is the reviewed one.

### 1.3 Focused tests

Run one file at a time (the eight files run together hang at session end; see below):

| file | result |
|---|---|
| test_lawful_recovery_migration | 5 passed |
| test_native_runtime_diagnostics | 4 passed |
| test_sunday_restoration_manifest_audit | 10 passed |
| test_granite_runpod_cloud_control | 13 passed, 2 skipped |
| test_granite_cloud_resume | 22 passed |
| test_granite_retained_lifecycle | 5 passed |
| test_granite_retained_completion | 1 failed -> 3 passed after fixture fix |
| test_granite_retained_host | 1 failed, pre-existing |

The completion failure was a stale fixture still naming the retired Pod (`aa12fd09` never
updated it either); fixed on my branch. The retained-host `cleanup` test fails identically on
the untouched `050c5056` checkout (verified there), so it is not a port regression; it is a
stale test that predates the recovery work. `test_granite_retained_host.py` also leaves a
non-daemon thread alive when run without `-x`, which is why the combined run never printed a
summary; worth a `pytest-timeout` or a daemon flag, not a launch concern.

### 1.4 Disposable native-step benchmark (design resolved, invocation results below)

Mechanism chosen: Greg's option 1. The harness (`operations/benchmark_native_step_disposable.py`)
keeps `--repository` at the failed run's own `050c5056` checkout so the cloned run directory's
saved identities stay valid, and with `--reviewed-repository` applies exactly two reviewed
semantics in memory, clearly labelled benchmark-only: `granite_retained_lifecycle.POD_ID` is set
to the value read from the reviewed lineage file, and `ActualHost.source_lineage` is replaced by
the reviewed `verify_closed_source_lineage`, loaded as a submodule of the scratch package so its
`_sidecars` import resolves to the scratch checkout's identical lawful file. No check is skipped;
the same checks run with the reviewed values. (An earlier draft that stubbed the retained-service
verification was refused by the auto-mode classifier as a security weakening; that draft was
abandoned, not worked around.)

**Results on this 4-CPU / 16 GB Windows box, 4 threads, seed checkpoint kept.** Three scratch
invocations against fresh clones of the failed run directory, original directory verified
byte-identical after each (75 files):

| checkpoint in the run | invocation 1 (no residue) | invocation 2 (residue from 1 left in place) |
|---|---|---|
| reviewed `POD_ID` applied in memory | yes | yes |
| lineage verification (reviewed rule) | passed, 16 s | passed, 16 s, sidecars neither moved nor deleted |
| prefix-00 open + tail check | 1.4 s | 1.4 s |
| checkpoint restore (107 MB) | 7.7 s, peak RSS 939 MB | same |
| retained-service verification (Pod, lease, readiness files, tokenizer, runtime receipt) | passed at 56 s (unported lineage: refused at 62 s) | passed |
| coordinator: binding, chronology, Memory A, controller/export/attachment/principal stages | reached | reached |
| `principal.verify` -> `recover` -> `_request` | ValueError `principal configuration differs from retained attachment` at 377 s | same |
| native step | not reached | not reached |
| peak RSS before the step | 1.07 GB working set, 1.31 GB peak pagefile | same |

So the two reviewed semantics do exactly what they claim inside the real host: the retired
Pod pin and the sidecar trap are gone. The two-invocation proof holds (invocation 1 created
header-only `-wal`/`-shm` residue; invocation 2 passed lineage with it present). The
fail-closed side was proven on temporary files against the same `_sidecars` rule: zero-length
and 32-byte `-wal`, `-shm` alone, and the real residue pair are not hot; a `-wal` of 33 bytes or
4 KB and a `-journal` of 0 or 1 KB are hot. The unit tests in `test_lawful_recovery_migration`
cover the same table.

The step itself is still unreached, by a third identity wall that the clone approach cannot
pass: `FrankiePrincipalAdapter._request` compares the saved attachment's `config_hash` with a
hash over receiver root/commit, `sys.executable`, the preparation and render paths, the
protected files and section evidence. A clone at any other path than the original run
directory, or any other interpreter path, fails it before feedback is even reconstructed. The
exact differing field is being pinned by a third invocation that logs the hashed material
(see the appendix line at the end of this section). Consequence for the design decision: the
host-level clone (option 1) is the right tool for proving recovery semantics and measuring
everything up to the step, and it has done that; the 8-vs-16 step measurement needs option 2,
a direct learner harness: build `context`/`decoder`/`optimizer` through the host's own
`source()`, `prefix()` and `_training()` (fresh checkpoint under the requested thread count),
rebuild `sessions` exactly as `SundayExecution` does from the schedule binding, reconstruct
`FrankieFeedback` from the saved `feedback` stage (plain `asdict` payload in `cycles.sqlite`,
digest re-verified against the saved `feedback_hash`), and call `NativeForecastLearner.step`
with the learner's own diagnostic callback. That harness never touches the principal or
Granite and is the next chat's first build item; the pieces it needs are all read-only and
all present in the clone.

Appendix, pinned by invocation 3 (retained attachment hash `82873d13...` vs computed
`07333cd7...`): the differing material is `preparation.pins_path` and
`preparation.mapping_artifact`, absolute paths under `<run_directory>/execution/cycle-00/
principal/`. Everything else in the hash (receiver root and commit, interpreter path, result
and delivery paths, retained prompt and knowledge pins, Memory A witness, 18 section hashes)
matched. Two consequences: the principal attestation binds the run directory's absolute
path, so a same-run resume must keep it (one more reason the path-preserving Windows host
is right), and a fresh run at a new `run_directory` creates a fresh attestation, so this is
not a blocker for the new cycle 0.

### 1.5 Launch gate, updated

Still closed. In order: (1) confirm the retained Pod `ycf4v6lmave6xw` is RUNNING by a read-only
GET before any watchdog work; (2) add the ref-contains-commit check to the config builder;
(3) restore the Windows host (path-preserving, conditions in the first-pass sheet: `E:` drive
letter, `core.autocrlf=true`, venv at its path with 3.13.7 / 2.9.1+cpu / 2.3.5 / tokenizers
0.22.2, receiver at its `C:` path at `342f5728`); (4) run the harness there with
`--fresh-checkpoint` at 8 and 16 threads; (5) keep the instance running for all 19 cycles
(strict identity retained, per Greg); (6) Greg authorises.

## Part 2 - token condensation and cycle reuse, grounded in what the repo already has

Greg's instruction was to start from the condenser stacks already in Frankie. They are:

| stack | module | what it already does | measured |
|---|---|---|---|
| exact-order block journal | `compact_journal.py` | gzip blocks of 16 canonical bodies, chained `previous/head`, sealed | 11.70 GB -> 570 MB (20.5x) |
| block-copy prefixes | `compact_journal_snapshot.py` | copies whole blocks, re-encodes only the cutoff block | prefix-01 757 blocks / 50 MB; prefix-18 7,095 blocks / 559 MB |
| affinity reader | `frankie_journal_reader.py` | spawn workers pinned per CPU, CPU 0 reserved, two blocks in flight per worker | `data_workers=48` -> 3 here, 15 on 16 vCPU |
| compact Granite context | `granite_context_compact.py` | tree encoding of the native context | 929,730 input tokens for 3,262 rows |
| stacked Granite context | `granite_context_stacked.py` | reversible named-column grammar: columns, dictionaries (Q), runs (R/E), deltas (D), byte transposition (B), base64 hashes (G), DBN wire bytes rebuilt from typed fields (`record_recipe`), packet-hash vector reconstructed from the prefix seed (`packet_recipe`) | 92,428 input tokens for the same 3,262 rows (10.1x); request 151 KB |
| per-cycle seeds | `actual-prefixes/prefix-NN-packet-seed.json` | 4,096 context cursors, prefix seed hashes, `derivable: true`, runtime code sha | 21-26 KB per cycle, all 18 sealed |
| prepared context cache | `prepared_context_cache.py` | one preparation per process, reused under exact identity | bound to `checkpoint_hash` and `model_hash` |
| single-pass finalisation | `single_pass_finalization.py`, `journal_stack_execution.py` | one verified pass with affinity workers for the day journal | (Sunday build) |

### 2.1 Answers to the addendum's eight questions

**Q1 - What is already implemented; what remains.** Addendum items C (compact grammar), D
(columnar blocks), E (runs/dictionaries) and half of F (content-addressed packet-hash and wire
reconstruction) are the stacked codec, shipped and measured at 10.1x over compact. Item A
(static prefix) is not implemented: the system text, grammar and field dictionary are
re-sent every cycle inside the 92k. Item B (delta packets) is not implemented: cycle N+1
re-sends the whole 4,096-row window. Item G (weight-independent preparation receipt) is not
implemented: the cache still binds `checkpoint_hash`. What remains numerically: at
`context_rows = 4096` the input grows from 92k (3,262 rows) to roughly 116k tokens, and the
`remaining_context` policy then leaves Granite about 15k output tokens inside the 131,072
service context, down from 38,644 at cycle 0. That is the real pressure, not cost: the critic's
answer budget shrinks as the walk proceeds. A static prefix plus per-cycle delta would hold
input near the delta size (the window slides by a few hundred rows per cycle) and restore the
output budget.

**Q2 - Where the packet still duplicates.** Three places. (a) The grammar, system text and
column layouts (`layouts`, `layout_indexes`) are identical across cycles and re-sent. (b) The
sliding window: cycle N+1's 4,096 rows overlap cycle N's by all but the rows that entered and
left; the stacked codec has no notion of "rows the model already saw under hash H". (c)
`metadata.source_context` per row (cursor, session, member index) is derivable from the seed
plus the cursor list already in the seed file. None of these is market evidence; all are
representation. The principal (Frankie) prompt is a different animal: 28 MB for cycle 0,
dominated by the retained knowledge bundle and section evidence that `retained_knowledge`
pins by hash; that is where "static header by hash" would matter most, and it is out of scope
for the Granite packet.

**Q3 - Can a virtual prefix reader match the physical snapshot's guarantee?** Not the same
guarantee, and the difference is exactly the one this project already wrote down. The physical
snapshot makes future rows ABSENT: no code path in the process can read them, which is the
S109 hole-11 lesson (`build_causal_slices.py` exists because a prompt rule was not enough).
A virtual view makes future rows REFUSED by a reader that could, by construction, read them.
For the NATIVE consumer that distinction is acceptable: `OnlinePrefix` -> reader is the only
path, every row is hash-chained (`previous/head` per block, `previous_hash` per row) and the
cutoff receipt pins (count, head) at the cutoff, so a view that yields blocks with
`start + count <= cutoff + 1` plus the decoded, truncated crossing block, and verifies the
chain up to the receipt's head, is as verifiable as the physical copy. The invariant it cannot
give is "an agent that opens the file cannot see the future". So: virtual views for native
training reads; physical materialisation only for anything handed to a model or a human. The
existing `compact_journal_snapshot` already re-encodes only the crossing block, so its cost is
I/O and storage (5.4 GB written and hash-verified for 18 prefixes), not CPU.

**Q4 - All 19 cutoffs in one causal pass?** Yes, and the block layout makes it cheap:
cycles 1-18 differ only by which block is the crossing block. One pass over the 7,095 compact
blocks can emit 18 receipts (count, head, block range, crossing-block ordinal) and 18
re-encoded crossing blocks; with a content-addressed block store the shared blocks are stored
once. `build_remaining_sunday_prefixes.py` today loops per cycle (`for index, step in
enumerate(steps[first_cycle:])`) and copies blocks per prefix, so it does 18 passes worth of
I/O for one pass worth of information. The seeds it also emits (`prefix-NN-packet-seed.json`)
are already the single-pass product the addendum asks for.

**Q5 - Which preparation outputs are weight-independent.** From `ContextSessionRunner._prepare`:
the context selection (heap of the last `t_ctx` entity rows by receive time), the token tensors
(`encode` over the trunk registry, not weights), the packet hashes, the teacher attachment,
and the compact/stacked prompt text. None read model parameters; `model_forward_performed` is
False in every receipt. The weight-dependent products are the native forward, the decoder
outputs and the training step. So the whole Granite packet and the native input tensors are
reusable across cycles that share (source prefix hash, cutoff, entity, t_ctx, registry hash,
teacher binding, QSV identity, codec code hash), and across reruns that share those and the
scope. The existing seed files already prove this: `derivable: true` with the cursor list.

**Q6 - The cache/day-pack key.** Everything that can change the bytes: source scope genesis
hash; source journal (count, head) at the cutoff; `as_of` and `through_cursor`; entity;
`t_ctx`; trunk registry digest; teacher binding (covers the normaliser); QSV identity or its
explicit absence; codec code hash (`codec_code_hash()` already binds the stacked module, C15
packing, canonical JSON, both prefix formulas and the DBN version); grammar hash and prompt
version; `context_encoding` and its options; adapter revision. Explicitly NOT in the key:
`checkpoint_hash`, `model_hash`, thread count, host identity. Record those separately in a
model receipt at the moment of use, which is Greg's item G and the Q9 overlap enabler.

**Q7 - Irreducible work for a new day group vs orchestration rebuild.** Irreducible: ingest the
raw day once (11.7 GB -> canonical journal), source conformance, one compact conversion, one
pass to find the F_LAST cutoffs and emit the receipts and seeds, the schedule binding, and the
per-cycle Granite calls and native steps themselves. Rebuilt only by design today: 18 physical
prefix copies (5.4 GB), the per-cycle re-preparation inside `step()` (two full prefix drains
plus encoding, repeated because the cache is checkpoint-bound and the coordinator runs
`_prepare` again inside the step), the per-cycle re-send of static packet material, and the
retained-preparation recovery machinery that exists only because preparation was not sealed
ahead of time. The seed files show the project already knows what the sealed product looks
like; what is missing is treating them as the input rather than as a witness.

**Q8 - Savings and the smallest safe sequence.** Estimates from the measured numbers, not
predictions of end-to-end wall time:

| option | what it saves | estimate |
|---|---|---|
| virtual prefixes for native reads | 18 prefix writes and hash passes | 5.4 GB written -> ~0.6 GB (crossing blocks + receipts); per-cycle open cost unchanged |
| single-pass cutoff compiler | 18 block-copy passes -> 1 | I/O ~18x less for the prefix build; CPU already small |
| weight-independent preparation receipt | 2 prefix drains + encoding per cycle inside `step()`, and enables N+1 prep during N | tens of seconds per cycle here; the enabler for the Pod overlap |
| static prefix + delta packet | input tokens per cycle | 92-116k -> roughly the grammar once plus a few thousand per cycle; output budget back to ~38k |
| golden seed restore | initialisation rebuild | seconds; `_training()` with `create=True` from `manual_seed(20260915)` is already deterministic |

Sequence, smallest first and each independently reviewable: (1) the preparation/model receipt
split (item G), because it is a contract change with a one-line consumer (`prepared_input`)
and unlocks both reuse and overlap; (2) the single-pass cutoff compiler emitting receipts and
crossing blocks, keeping physical prefixes as its output until (3) a verified virtual reader
for native reads lands with the same tests as the physical one; (4) static prefix + delta for
the Granite packet, which needs a model-side confirmation that the served model honours a
prefix cache and a decoder proof that header + delta reconstructs the full packet byte-exact;
(5) `DAY_PACK_V1` as the manifest that binds all of the above by hash, which is mostly the
restoration manifest generalised. Do not start with (4): it is the largest token win but the
only one that touches what the model sees.

## Part 3 - what changed on the ccode review branch in this pass

- `tests/test_granite_retained_completion.py`: fixture pod id -> migrated Pod (3 passed).
- `operations/benchmark_native_step_disposable.py`: `--reviewed-repository` applies the two
  reviewed semantics in memory; RSS fields typed.
- This sheet. The two sheets it collapses are left in place for history.

Next chat should open from this sheet.
