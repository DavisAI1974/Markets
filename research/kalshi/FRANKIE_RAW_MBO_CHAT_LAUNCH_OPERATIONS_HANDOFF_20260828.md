# Frankie native raw-MBO Chat launch operations handoff

> **Current-state correction:** Read
> `FRANKIE_RAW_MBO_A_ARMS_CORRECTED_NEXT_CHAT_HANDOFF_20260828.md` first. It
> supersedes the operational-status and scientific-lock claims below. This file
> remains historical provenance for the original staging and recovery work.

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

The Real-Time replay completed and froze after all `5,667,689 / 5,667,689`
native records (`100%`) and `4,256,603` F_LAST-closed groups. The final durable
chain has 18 linked checkpoints; every checkpoint's adapter and controller
sibling hash and the complete gzip ledger were revalidated.

- final locked checkpoint:
  `2e10b3f2534aaf697129831608a8e65fd9c4ac8ca92ec171c2a012fe8593b384`
- RT first lock:
  `ef728adf5ae2064c242f0e72acbf95f1d5b586a3f1845bed9ac9577ea998dd42`
- freeze receipt:
  `bc7e8ed9dbcb08177d46a48f16176afb026f5efe0c6fa49164260877fd172793`
- native evidence bundle:
  `94a32deafdcb580868ba24df829b616edf36a80f84f80b7cd828efea24a13b36`
- final checksum manifest:
  `d1994ce1449144fd48e2e87930c59727da32d85cc1c9b2cc770d77781c4c6415`

Only after that lock and freeze was the isolated A-clean Forecaster lane opened:

- run: `frankie-a-clean-forecaster-33161766927-1`
- packet: `aclean-fcpkt-281162606bbfc376537b`
- pre-call checkpoint:
  `855a2a9868b68fb90f2138f69bc3f6957d4e5f182b04546f01300879b1198266`
- frozen RT state:
  `d2f1eae14d269bf1b1b755f9502c65138164a23f3dc6a42d5c0f97e9de1c9498`

The Forecaster packet has no memory package, keeps the answer wall sealed, and
cannot modify the frozen Real-Time state.

The original Forecaster process was attached to an ephemeral Chat-agent exec
session and stopped when that session ended. A verified resume rebuilt the
controller prefix, matched the saved adapter/controller hashes, event-group
count, source cursor, and causal watermarks, then advanced through two raw-file
boundaries. The process is stopped again for handoff at this authoritative
closed checkpoint:

- sequence: `6`
- checkpoint:
  `8281459d1eaee4f060969dd457f4ba04fc156d75ff5ee88417fa46edc03fe96d`
- phase: `FORECASTER_NATIVE_REPLAY`
- progress: `2,000,000 / 5,667,689` (`35.287751322%`)
- `event_group_open=false`, `locked=false`

Ignore and quarantine any work after this checkpoint. A-memory artifacts remain
absent from the A-clean runtime.

### A-memory

Path: `.github/workflows/frankie_a_memory_rt_native_launch_20260828.yml`  
File SHA-256:
`3f030e10d739a2a71fd73022a981a76d052d3fec2d7f1e949243bcf5bb509aa7`

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
work packets. It verifies the repository recovery proof, the exact 15-file
allowlist, answer-wall state, principal call order, output hashes,
freeze/first-lock/handoff linkage, completion receipt, historical launch ancestry,
and explicit absence of Step-1, post-reveal, current-arm, or old-row content
before creating the A-memory packet.

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
Both host and S3 inventories were empty, so those attempts correctly stopped.
The blocker was later resolved by recovering and freezing the original chain in
the repository, without reconstructing Frankie findings from later material.

Authoritative repository recovery:

- recovery commit:
  `5e2927f196250fc08373b66e358bb9167af018c6`
- directory:
  `research/kalshi/frankie_raw_mbo_benchmark/prior_memory/workmode-32851909748-1/`
- historical source run: `workmode-32851909748-1`
- source surface: `PRIOR_REDUCED_NON_FULL_MBO_SURFACE`
- historical launch commit:
  `96d713cc9ed3e8ba889ae45a04e80cb4eab4fb26`, an ancestor of the required
  raw-MBO benchmark starting tip
- repository recovery proof SHA-256:
  `dc567f014d9c65fc50b179e1e2f46b8624d2d27e25eaf63a29068f6d6a4cb007`
- RT output SHA-256:
  `72a22b5ec0ee5f6ebdcf14d0ff566dd178f31ce2bd6d3f3f85cf9b49a2ac9158`
- Forecaster output SHA-256:
  `32131d948790faa56ed130f901bad71b10075919a2e23a78d1ff2c3939de25af`
- completion receipt:
  `440157fcd9d9e066e2cab0070d86d7c918f48cb024a58828f8a8cc5be5ade773`
- frozen RT state:
  `4342a36cb527d8773435f79d2adb7e35e40c24e144689b359684fde59871350e`

The proof chain passed with `answer_wall=SEALED`, Step-1 exposure false,
current raw-MBO arm content false, old reduced rows absent, RT frozen before the
Forecaster, and all available artifact-manifest bytes and hashes reconciled.
The Forecaster output is byte-identical to the historical scored-file hash; the
findings were not edited. `REPOSITORY_FREEZE.json` is verification metadata and
is not included in the learned-memory tar.

The deterministic memory tar contains exactly the 15 allowlisted artifacts and
has SHA-256
`0a5cddbcd971a3e6c2cad88a8e5559b0ab0529a31174c882355a61fe9c680b87`
(`34,009` bytes). Its generated package-proof receipt is
`e7d8cbc54f354a4902ab72792e379033a25f5f28102fcf9d4bb82dda1d7e8435`;
the repository-verification receipt is
`9c5847e33f4014eac12e8da67c2f97e55280545f67ea0d7899fa1c914d39683b`.
This hash is the identity to reuse unchanged for every memory-assisted arm.

The corrected A-memory launcher was committed through the GitHub plugin at
`c7da7d257fda2ce9ddccfaee56020ed3e7de8e50`. It uses the A-clean native
download, source manifest, replay, checkpoint, packet, and persistence behavior.
The only arm delta is `memory_mode=MEMORY_ASSISTED` and the hash-bound tar above.
The GitHub push is the private packet-staging trigger; the active Chat-controlled
Real-Time runtime is kept separately from A-clean.

Active A-memory Real-Time launch:

- run: `frankie-a-memory-rt-c7da7d257fda-1`
- packet: `amemory-rtpkt-4eed0d33d524b7388db5`
- contract:
  `4eed0d33d524b7388db56a7aebb19107c4867ed81384ec338f6cf7934d4ee499`
- durable sequence-0 checkpoint:
  `45141df6d86bde0b31cff70f1d2ba40ad5b430f3155e1f2d3142964616970fe2`
- launch receipt:
  `1bc98db77c8ba5148b1066cdf42a81256318e4b5ecbfe27b0ca7c9ac8e8b0ac0`
- packet root:
  `/workspace/scratch/da00127ac123/a-memory-packet-c7da7d2/`
- active runtime:
  `/workspace/scratch/da00127ac123/a-memory-runtime-c7da7d2/`

The original RT process was also attached to an ephemeral Chat-agent exec
session. It stopped without an exception or scientific invariant failure. Its
ledger continued beyond the last checkpoint, so the uncheckpointed tail was
quarantined and is not restart authority.

The authoritative A-memory restart boundary is:

- sequence: `2`
- checkpoint:
  `d03b863917ad250364729e976c6ba042555ffceb7b60c84ab7dfb530aeaf1757`
- phase: `RT_NATIVE_REPLAY`
- progress: `1,000,000 / 5,667,689` (`17.643875661%`)
- completed closed groups: `759,713`
- `event_group_open=false`, `locked=false`

The recovery verified the fixed memory package and complete checkpoint chain,
rebuilt a closed 1,000,000-record prefix, and quarantined the interrupted tail.
A local resume-helper naming bug surfaced only after the first independent
prefix audit passed; it changed no checkpoint or scientific state. The next
session must repeat the full adapter/controller/prefix audit from sequence 2
before accepting record 1,000,001. `FORECASTER_FRANKIE` remains sealed and must
not start until A-memory RT reaches 100%, writes its locked final checkpoint and
first lock, and freezes the one-way handoff.

## Ephemeral-process failure and recovery rule

The two incomplete processes stopped because their long-running Python children
were owned by temporary Chat-agent execution sessions. Ending or interrupting
those sessions retires their process groups. This was an orchestration failure,
not a data, model, or replay-invariant failure; neither runtime contains an
error, traceback, or failed-integrity marker.

Do not run either original start-from-zero command over an active runtime. Use
the promoted resume launchers below, verify the selected closed checkpoint and
all sibling hashes first, and discard every uncheckpointed tail. Keep the Chat
turn open through completion or move replay execution to a genuinely persistent
runner before yielding.

## Required wrappers and scientific boundary modules

| Path | Role | SHA-256 |
|---|---|---|
| `research/kalshi/frankie_raw_mbo_benchmark/chat_packet_seam.py` | Arm contract, answer wall, scientific-input seam | `62b410cfd3a3da1ce5cb373af5b0f763bf26d271ab4cefa6bca4fe346907c274` |
| `research/kalshi/frankie_raw_mbo_benchmark/raw_mbo_source_manifest.py` | Exact roster hashes, native record denominator, progress | `7229bfc2d4befa4664aabca4b0321fd39a2c281c846022e5ec2cfdd975ae75e9` |
| `research/kalshi/frankie_raw_mbo_benchmark/mbo_resume_state.py` | Exact adapter snapshot/restore at closed groups | `e7d1dcf3a66c10bd4c2342c8e35d79ea5a58cbf44952bfbdb2b3195a7b1dd7e3` |
| `research/kalshi/frankie_raw_mbo_benchmark/benchmark_checkpoint.py` | Atomic hash-chained checkpoints and progress validation | `06934557cf0441dac31d0abd3aafc9ae05e35a1d17a684480cf605a652e8cbf7` |
| `research/kalshi/frankie_raw_mbo_benchmark/native_evidence_bundle.py` | Lossless native group ledger and evidence receipts | `a1d6d1e41d519a956754f6199f5a14825c243776b3c328ca9e2956ae909149ae` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_clean_rt_replay_20260828.py` | Exact A-clean native RT replay/ledger/checkpoint launcher used for the completed frozen run | `0bb2c89ec0acb80d5725e574e521c0844962d9f66b4b60077956bb5cb1cb2c8e` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_clean_forecaster_prepare_20260828.py` | Builds and seals the A-clean frozen-RT one-way Forecaster packet and sequence-0 checkpoint | `73d899af5a0b771497f8b25cda4e4d01320e975ea02f8afe73dc9cb61834d5fa` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_clean_forecaster_replay_20260828.py` | Original A-clean Forecaster native replay and pre/post model checkpoint launcher | `44b75be9eb7fc4c00abcd287f26ec6d2ecf7b7cefb5e1eb412e3b88af97a706f` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_clean_forecaster_resume_20260828.py` | Exact A-clean Forecaster sequence-6 recovery launcher; verifies reconstructed prefix before continuation | `566f5805c4a809b44e9a1ed389e04c8013365f33ad2904b000f68e3546cd0cf3` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_memory_prepare_20260828.py` | Verifies the repository memory proof, materializes the lessons-only chain, and seals the A-memory packet | `0b19480edd0679be7b64f7a5dd50a66b4fa16ed8f26175ec8cf4e77d47550236` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_memory_rt_resume_20260828.py` | Exact A-memory RT sequence-2 recovery launcher; verifies package, chain, prefix, and quarantined tail | `6406cdca918c6557b75973717b83298aaab676116511cbc64fae3194815104e9` |
| `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py` | Native full-state replay | `838997142a543ba6c5ba6b86277c66d9465ad4e62ee85c5b1ec9ac177eaa8120` |
| `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` | Full-depth resting-order/FIFO adapter | `4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce` |

The promoted launchers are exact-run snapshots. They intentionally retain the
packet/runtime identities and absolute scratch paths used in this Work session.
On the same persistent workspace, resume with:

```bash
cd /workspace/scratch/da00127ac123/Markets-handoff
python research/kalshi/frankie_raw_mbo_benchmark/a_clean_forecaster_resume_20260828.py
python research/kalshi/frankie_raw_mbo_benchmark/a_memory_rt_resume_20260828.py
```

Run them in separate persistent processes. Do not run either command until its
named packet/runtime roots and checkpoint sibling hashes have been verified. If
the next workspace has a different absolute root, copy the sealed packet and
runtime first, then make and document a deliberate path-only launcher update;
never silently point a launcher at a newly generated or other-arm runtime.

Consolidated workflow and memory inventory:

| Path | Role | SHA-256 |
|---|---|---|
| `.github/workflows/frankie_a_clean_rt_native_launch_20260828.yml` | Exact A-clean packet staging, native source hash binding, sequence-0 checkpoint, private persistence | `fd9ea34473f86b93abd3cd86cd8d25db8c326fd5a1d918c6971b232249913f34` |
| `.github/workflows/frankie_a_memory_rt_native_launch_20260828.yml` | A-clean-equivalent native staging plus verified lessons-only memory binding | `3f030e10d739a2a71fd73022a981a76d052d3fec2d7f1e949243bcf5bb509aa7` |
| `research/kalshi/frankie_raw_mbo_benchmark/prior_memory/workmode-32851909748-1/` | Frozen 15-file prior learned-output/receipt chain plus repository recovery proof; no reduced rows | package `0a5cddbcd971a3e6c2cad88a8e5559b0ab0529a31174c882355a61fe9c680b87` |

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
- for A-memory only, the independently verified lessons-only tar, package-proof
  receipt, and repository-verification receipt.

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
