# Frankie native raw-MBO Chat launch operations handoff

Date: 2026-08-28 UTC  
Repository: `DavisAI1974/Markets`  
Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`  
Required starting tip: `82e140598b03bb38a7761c19d0ac47017c3908d0`

## Purpose and authority

This is the operator handoff for later Chat sessions that continue the two
ChatGPT-controlled Frankie arms. It records the exact data boundary, launch
machinery, packet identities, receipts, checkpoint rules, current status, and
restart gates used in this session.

The user's two pasted drop-ins are the scientific authority:

- `A-clean` gets the full native raw-MBO evidence and no learned memory from the
  earlier reduced/non-full-MBO run.
- `A-memory` gets the identical full native raw-MBO evidence plus one verified,
  pre-reveal package containing Frankie's learned lessons, insights, notes, and
  frozen/locked reasoning from the earlier reduced/non-full-MBO run.
- `A-memory` must never consume the old reduced market rows as live evidence or
  as the memory payload. The old run's learned knowledge is memory; the native
  DBNs remain the live scientific evidence.

Both arms keep Step-1 sealed. Do not reveal, inspect, reconcile, or score against
Step-1. Do not use BOSS, B0/B1/B2, Granite, MBP/top-10, A-clean output in
A-memory, A-memory output in A-clean, or `V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz`.

## Exact native scientific input

Source manifest schema: `FRANKIE_RAW_MBO_SOURCE_MANIFEST_V1`  
Source manifest hash:
`a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba`  
Total native MBO records: `5,667,689`  
Warmup/development records: `1,561,401`  
Held-out records: `4,106,288`

| Date | Role | Canonical object | Bytes | Native records | SHA-256 |
|---|---|---|---:|---:|---|
| 2021-10-01 | Warmup/development | `glbx-mdp3-20211001.mbo.dbn.zst` | 25,628,861 | 1,504,374 | `e6b4ec01bd9b34d57cb22c770b5d49c756e7f41a658f081823d923004a0121b2` |
| 2021-10-03 | Warmup/development | `glbx-mdp3-20211003.mbo.dbn.zst` | 973,355 | 57,027 | `4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88` |
| 2021-10-04 | Held out | `glbx-mdp3-20211004.mbo.dbn.zst` | 34,300,424 | 1,994,358 | `8ed47cc0a68cf40cae9fde45e158142978076e60d3f9fc7cf940196babfddc0a` |
| 2021-10-05 | Held out | `glbx-mdp3-20211005.mbo.dbn.zst` | 36,192,430 | 2,111,930 | `a4a12f9578da762412884e7f559a123361eaa3a153bec0db59dfb3ba6224a874` |

Canonical S3 prefix:
`s3://bento-568968024170-us-east-2-an/nymex/ng_mbo_5y_v0/native/20211001_20211101/`

The replay contract is native MBO event by event in `ts_recv_ns` causal order,
closing groups only at `F_LAST`, with full reconstructed depth, resting-order
and FIFO state, raw action groups, order identifiers, and provenance. Progress
is completed native MBO records divided by the hash-bound total above.

## Arm isolation matrix

| Input or state | A-clean | A-memory |
|---|---:|---:|
| Four canonical native DBNs | Yes | Yes |
| Native source manifest above | Yes | Yes |
| Prior reduced market rows/seconds | No | No |
| Prior Frankie lessons/insights/notes | No | Yes, after proof gate only |
| Other arm's packet/checkpoint/output | No | No |
| Step-1 or post-reveal material | No | No |

The arms may share immutable DBN bytes and source-manifest facts only. They use
different chat lanes, packet directories, checkpoint chains, artifact names,
concurrency groups, durable S3 prefixes, first locks, and Forecaster handoffs.

## Current launch workflows

### A-clean

Path: `.github/workflows/frankie_a_clean_rt_native_launch_20260828.yml`  
File SHA-256:
`fd9ea34473f86b93abd3cd86cd8d25db8c326fd5a1d918c6971b232249913f34`

Behavior:

1. Checks out the exact launch commit and proves the required starting tip is an
   ancestor.
2. Downloads only the four canonical DBNs.
3. Verifies exact object sizes and SHA-256 values.
4. Counts native MBO records with `databento==0.81.0`.
5. Builds the source manifest and an `A-clean` Chat seam contract with
   `memory_mode=CLEAN` and `memory_package=null`.
6. Creates the empty adapter snapshot and sequence-0 pre-RT checkpoint.
7. Persists the keyless packet privately to S3 and as a private GitHub artifact.

Launch commit: `abec7f831010a906dc02d482d1196675707e3470`  
Workflow run: `33161766927`  
Job: `98817666545`  
Conclusion: `success`  
Artifact: `9681937011`  
Artifact name:
`frankie-a-clean-rt-abec7f831010a906dc02d482d1196675707e3470-33161766927-1`  
Artifact ZIP SHA-256:
`5dcfe43519fc6f4a02131a7be4177b646289e5b02826428f668316b8743d7c92`  
Durable prefix:
`s3://bento-568968024170-us-east-2-an/nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-clean/abec7f831010a906dc02d482d1196675707e3470/33161766927-1`

Packet identity:

- Run: `frankie-a-clean-rt-33161766927-1`
- Packet: `aclean-rtpkt-be26a48cef30ad9abe9e`
- Contract hash:
  `be26a48cef30ad9abe9e1a0928ec284049156132f5d37a52cf9635b2460c4e82`
- Sequence-0 checkpoint:
  `e1cefd077ec2fdc1aa59ac341818cc582d1b60df295285dab19cd21fcce43bf8`
- Launch receipt:
  `ca941aa93bcdad82584707367390fadb4df6be7e6d6ea811012c2b90aa39007d`

Important status correction: the first in-agent replay reported a sequence-1
cursor but did not persist a root-visible checkpoint body. That partial attempt
was quarantined outside the active chain at
`/workspace/scratch/da00127ac123/a-clean-runtime-33161766927-attempt-prestate/`.
It is not restart authority and must never be merged into the active ledger.

A replacement A-clean replay was then started with root-visible state at
`/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/`. Its persisted
command is:

```bash
cd /workspace/scratch/da00127ac123/Markets && \
  python /workspace/scratch/da00127ac123/a_clean_rt_replay.py
```

The runtime directory contains `REPLAY_COMMAND.txt`, the exact source manifest,
launch receipt, progress receipt, active `native-evidence-groups.jsonl.gz`
ledger, and three siblings for every checkpoint: checkpoint JSON, adapter-state
body, and controller-state body. The controlling Real-Time Frankie lane was
instructed to remain open through 100% and the frozen first lock.

The current durable restart cursor is sequence 1 at
`500,001 / 5,667,689` (`8.821955474%`):

- checkpoint:
  `d2a2fb9709aee77274e99b8c207c84aff2245ba391c0ee26c28636874cd687ae`
- previous checkpoint:
  `e1cefd077ec2fdc1aa59ac341818cc582d1b60df295285dab19cd21fcce43bf8`
- adapter-state hash:
  `d60e6cb9936ff9365c61eefa2e11b6c68e319fca8be25fa6e32357cfbe626566`
- controller-state hash:
  `f6309098f0c96415441a32ae299d8340671ee7c75751472abd121af2515a63f6`

The sibling files are `checkpoint-000001.json`,
`adapter-state-000001.json.gz`, and `controller-state-000001.json`; their hashes
reconcile to the checkpoint JSON.

### A-memory

Path: `.github/workflows/frankie_a_memory_rt_native_launch_20260828.yml`  
File SHA-256:
`d061a28bbd13750550d5c14dea6386d0bcec7705a4ff74ec7c510cbc74a16c54`

This clones the A-clean checkout, native roster, manifest, adapter, checkpoint,
private persistence, and packet behavior under isolated A-memory names. Its only
scientific-arm delta is `memory_mode=MEMORY_ASSISTED` plus one verified prior
learned-knowledge package.

The memory package allowlist contains only the earlier run's learned outputs and
integrity chain:

- `RT_OUTPUT.json`
- RT context, agent receipt, first lock, frozen state, freeze completion, and
  external freeze anchor
- `ONEWAY_HANDOFF.json`
- `FORECASTER_OUTPUT.json`
- Forecaster context, agent receipt, and first lock
- execution, artifact-manifest, and completion receipts

It does not copy old seconds, source rows, scout rows, prior input packets, or
work packets. It verifies pre-benchmark mtimes, answer-wall state, principal call
order, output hashes, freeze/lock linkage, and absence of current-arm or
post-reveal lineage before creating the A-memory packet.

Launch-gate commit: `ecb57cba593ed145d454e67f3239ddb8ac662be0`  
Workflow run: `33162517524`  
Job: `98820119044`  
Conclusion: `failure` by design at the memory proof gate  
Inventory artifact: `9682229546`  
Inventory artifact ZIP SHA-256:
`6b0e888f7d517414b2cb3732c7d0cc50fb0a45e090523d4e545335285ae498e7`

The read-only inventory proved that the exact old packet S3 prefix contains only
`packet.tgz`, `packet.sha256`, `repo.tgz`, and `stage_identity.json`. The exact
old worker packet root contained none of the required learned-output filenames.
Materialization therefore failed closed before native replay or any model call.
No old reduced rows were consumed. No A-clean runtime state was exposed.

A second bounded discovery commit
`1db882d92037f9954c9a0319e3e2bfb0d0941fed` searched the entire sealed
worker `/mnt/markets` tree and Frankie S3 namespace for the exact prior run ID
and the allowlisted learned-output filenames, while excluding Step-1,
post-reveal, scoring, reconciliation, and current-arm paths. Workflow
`33163106365`, job `98822043403`, also failed closed at materialization. Its
inventory artifact `9682478127` has ZIP SHA-256
`cea2edf15319116ce49ea9e28b3e44a2c36a5ae3a83671b3e43a8a8f80615631`.
Both host and S3 inventories were empty. Therefore no authorized byte-complete
learned-knowledge package was located; A-memory cannot start until the user
provides the authoritative pre-reveal package or its exact repository/S3 path.

Authoritative A-memory status is `PRE_MEMORY_BIND`, progress
`0 / 5,667,689`. The earlier transient sequence-0 checkpoint
`b47e6ad5e04b3d00d438915fcbb08be7148bfc1857298016ad808cbd8b23d35d`
is not a launched scientific replay checkpoint until the memory package binds.

For the next attempt, search only pre-existing prior-run namespaces for the exact
learned-output filenames above and initially emit paths, bytes, mtimes, ETags,
and hashes only. Do not inspect Step-1, scoring, reconciliation, post-reveal, or
current-arm paths. Do not substitute the old packet input or a later finding.
If the byte-complete learned-output freeze/lock/receipt chain cannot be proven,
keep A-memory closed.

## Required wrappers and scientific boundary modules

| Path | Role | SHA-256 |
|---|---|---|
| `research/kalshi/frankie_raw_mbo_benchmark/chat_packet_seam.py` | Arm contract, answer wall, scientific-input seam | `62b410cfd3a3da1ce5cb373af5b0f763bf26d271ab4cefa6bca4fe346907c274` |
| `research/kalshi/frankie_raw_mbo_benchmark/raw_mbo_source_manifest.py` | Exact roster hashes, native record denominator, progress | `7229bfc2d4befa4664aabca4b0321fd39a2c281c846022e5ec2cfdd975ae75e9` |
| `research/kalshi/frankie_raw_mbo_benchmark/mbo_resume_state.py` | Exact adapter snapshot/restore at closed groups | `e7d1dcf3a66c10bd4c2342c8e35d79ea5a58cbf44952bfbdb2b3195a7b1dd7e3` |
| `research/kalshi/frankie_raw_mbo_benchmark/benchmark_checkpoint.py` | Atomic hash-chained checkpoints and progress validation | `06934557cf0441dac31d0abd3aafc9ae05e35a1d17a684480cf605a652e8cbf7` |
| `research/kalshi/frankie_raw_mbo_benchmark/native_evidence_bundle.py` | Lossless native group ledger and evidence receipts | `a1d6d1e41d519a956754f6199f5a14825c243776b3c328ca9e2956ae909149ae` |
| `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py` | Native full-state replay | `838997142a543ba6c5ba6b86277c66d9465ad4e62ee85c5b1ec9ac177eaa8120` |
| `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` | Full-depth resting-order/FIFO adapter | `4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce` |

## Older two-Frankie orchestration reused only for behavior

These files supply packet sealing and sequential orchestration behavior only.
Their older reduced-seconds scientific-input builder must not be reused:

| Path | Permitted reuse | SHA-256 |
|---|---|---|
| `research/kalshi/ng_exhaustion_two_frankies_workmode_packet_2day_20260825.py` | Keyless packet layout, answer wall, receipts | `6170f70e5ed3f4b1c1aa99631a32514c068623711d24ffaee979c9d676459bda` |
| `research/kalshi/ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825.py` | RT validation, freeze/first lock, one-way handoff, Forecaster lock, completion manifest | `2c7cf46f7cdaf5784be2eaf02d941efef8ed4f0762a49933d4dad3774a9767b5` |

The required principal order for each arm is:

1. Build and verify that arm's packet.
2. Write a pre-call checkpoint.
3. Run `REAL_TIME_FRANKIE` over every native evidence group exactly once.
4. Checkpoint at intervals, raw-file boundaries, `F_LAST`-closed boundaries,
   and immediately before and after expensive calls.
5. Validate RT output, write first lock, freeze the full RT state, and write the
   one-way handoff.
6. Only then start `FORECASTER_FRANKIE` with the frozen RT handoff for the same
   arm.
7. Validate Forecaster output, write its first lock, receipts, artifact manifest,
   and `COMPLETE.json` last.

Forecaster must never run early or mutate RT's frozen state.

## Packet contents and integrity checks

Each native arm packet must contain:

- the four exact `.mbo.dbn.zst` objects;
- `source_manifest.json`;
- `chat_packet_contract.json`;
- sequence-0 adapter state and checkpoint;
- `launch_receipt.json`;
- file SHA-256 inventory;
- for A-memory only, the independently verified lessons-only tar and its proof
  receipt.

The packet contract must say:

- evidence surface `NATIVE_RAW_DATABENTO_MBO`;
- source kind `NATIVE_DBN_MBO`;
- causal clock `ts_recv_ns`;
- native DBN replayable and canonical source not rewritten;
- event-by-event receive order, `F_LAST` group closure, raw actions, full depth,
  and FIFO order state required;
- seconds collapse, MBP substitution, and Step-1-derived input disallowed;
- Step-1, reveal, and other-arm outputs not exposed.

The generated `FILE_SHA256SUMS` currently records absolute GitHub-runner paths.
When verifying a downloaded artifact elsewhere, recompute hashes from the packet
root or normalize the recorded prefix before `sha256sum -c`; a raw `-c` call from
another filesystem will fail on missing runner paths even when the packet bytes
are correct.

## Restart and checkpoint procedure

1. Verify repository branch and prove the required starting tip is an ancestor.
2. Verify workflow/module hashes against this handoff or review and document any
   intentional later commit.
3. Re-hash all four native DBNs and rebuild/revalidate the manifest.
4. Load the last durable checkpoint and verify the complete hash chain from
   sequence 0.
5. Require `event_group_open=false`; never restart from a partial action group.
6. Restore the exact adapter snapshot and controller state named by the durable
   checkpoint.
7. Resume from `completed_mbo_records`, preserving source-file order and
   `ts_recv_ns` causal order.
8. Write checkpoints atomically at the next allowed interval, raw-file boundary,
   pre/post expensive call, or locked completion boundary.
9. Treat a locked checkpoint as terminal.

Never resume from a chat message's reported cursor alone. A restart cursor is
authoritative only when its checkpoint JSON, adapter snapshot, controller state,
ledger cursor, source manifest, and previous hash link all validate.

## Tests and launch discipline

The focused suite used for both workflows was:

```bash
python -m unittest discover \
  -s research/kalshi/frankie_raw_mbo_benchmark/tests -v
```

Result at launch preparation: `11/11` passed. Both workflow files also passed
YAML structure checks, embedded Bash syntax checks, static arm/source isolation
checks, and `git diff --check`.

Agent Skills release `0.6.7` was used for specification authority,
definition-of-done, task breakdown, incremental/TDD implementation, Git
workflow, CI, and launch verification. The Documents skill was used to structure
and audit this operator handoff. This handoff is Markdown in the Git repository,
not a separate DOCX artifact.

## Next-session acceptance checklist

- [ ] Read this handoff and the two user drop-ins before acting.
- [ ] Confirm which arm the user authorizes; do not infer a cross-arm launch.
- [ ] Keep the four native DBNs identical between arms.
- [ ] Keep learned memory absent from A-clean.
- [ ] Bind lessons/insights/notes—not reduced rows—for A-memory.
- [ ] Keep Step-1 and post-reveal state sealed.
- [ ] Recover or restart A-clean only from durable, verifiable state.
- [ ] Keep A-memory at zero until its prior learned-output proof chain binds.
- [ ] Preserve RT -> freeze/first lock -> Forecaster order independently per arm.
- [ ] Report concrete commit, workflow/job, run, packet, checkpoint, manifest,
  artifact, and record-progress identifiers.
