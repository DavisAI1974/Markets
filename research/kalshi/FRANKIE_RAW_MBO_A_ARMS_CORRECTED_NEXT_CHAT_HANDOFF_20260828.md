# Frankie native raw-MBO A-arms corrected next-chat handoff

Date: 2026-08-28 UTC
Repository: `DavisAI1974/Markets`
Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`
Pre-housekeeping remote tip: `1c105b51a05d3097cc3345901a3c5c1b86929fd2`

## Read this correction first

This handoff supersedes the current-state and scientific-lock claims in
`FRANKIE_RAW_MBO_CHAT_LAUNCH_OPERATIONS_HANDOFF_20260828.md`. The older document
remains useful historical launch provenance.

Audit truth: the first A-clean RT, A-clean Forecaster, and A-memory RT Python
controllers reconstructed native MBO and wrote diagnostic summaries and
checkpoints, but did not load the scientific mission into a principal Frankie
model. Therefore their replay-completion files, first-lock labels, and freeze
labels do not prove a scientific Frankie run. Preserve their outputs as
diagnostic evidence; do not represent them as valid scientific model locks.

The mixed exploratory A-clean report was deleted and is ineligible for any
agent context or Forecaster handoff. Only the positive artifacts named below may
carry forward.

## Scope and immutable scientific input

Work only on A-clean and A-memory. Do not inspect or run BOSS, B0/B1/B2,
Granite, Step-1, reconciliation, or scoring. Keep the answer/reveal wall sealed.

- Canonical input: native Databento `.mbo.dbn.zst` for 2021-10-01, 03, 04, 05.
- Source-manifest SHA-256:
  `a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba`.
- Total native records: `5,667,689`.
- Causal order: event by event in `ts_recv_ns`, closing only on F_LAST.
- Required evidence: raw actions, full reconstructed depth, resting orders,
  FIFO/priority state, queue position, volume ahead, order age, lifecycle, and
  exact provenance/clocks.
- Forbidden: reduced seconds, `V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz`, MBP/top-10,
  Step-1-derived input, and any other arm's output.
- A-clean memory: none.
- A-memory package SHA-256:
  `0a5cddbcd971a3e6c2cad88a8e5559b0ab0529a31174c882355a61fe9c680b87`.
- A-memory package-proof receipt:
  `e7d8cbc54f354a4902ab72792e379033a25f5f28102fcf9d4bb82dda1d7e8435`.
- Repository-verification receipt:
  `9c5847e33f4014eac12e8da67c2f97e55280545f67ea0d7899fa1c914d39683b`.

## Context hierarchy for every new agent

Load focused context in this order:

1. Controlling RT mission:
   `research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md`.
2. For Forecaster output review only:
   `research/kalshi/agents/frankie_native_raw_mbo_forecaster_first_replay_review_20260828.md`.
3. Detailed positive provenance addendum:
   `research/kalshi/agents/frankie_native_raw_mbo_rt_positive_discovery_addendum_20260828.md`.
4. Only the same-arm runtime receipts, evidence, and positive reports required
   for that bounded task.

The historical reduced mission remains byte-identical at SHA-256
`442cc84c524feb6306224a6ba7e6984a21605c7a515c651b52c77bc279e2b2ef`.
It is provenance, not the controlling native mission.

## Controlling analytical rule

The daily first replay calculation stays unchanged. For each source day it
reports `first`, `last`, `min`, `max`, and arithmetic `mean` for spread,
full-depth imbalance, full bid/ask depth, full bid/ask order count, and full
bid/ask price-level count, plus action/side totals, event-group count, and
maximum group-action count.

For every additional valuable numerical extraction, produce coequal views:

1. exact member-level evidence; and
2. an arithmetic average with exact population, denominator, family/subfamily,
   side, session/phase, and clock definition.

Never average across distinct families, subfamilies, sides, sessions, phases,
or cluster identities. A valid difference caused by scope or granularity is
`COMPLEMENTARY_SCOPE_DIFFERENCE`, not a contradiction. Both views receive equal
prominence whenever each is valuable.

## What the non-averaged review added

Frankie found substantial positive information that the daily averages cannot
retain:

- October 4/5 contain 1,441/1,509 distinct action strings and 1,976/2,094
  action-plus-side strings.
- Exact members expose multi-fill cascades, mixed cancel/modify branches,
  add-interleaved groups, multi-price bursts, family recurrences/runs, session
  phases, and same-order `AN → TFMN → TFCN` depletion lifecycles.
- Full FIFO evidence adds volume ahead, priority/order age, priority loss,
  survival, replenishment, withdrawal, absorption, and lawful recognition
  clocks.
- The averaged channel adds a different valuable fact: October 5 is a stronger
  bid-heavy day regime than October 4.
- Exact decomposition explains the regime: October 4's closing bid-heaviness is
  primarily ask withdrawal; October 5's additional bid-heaviness is primarily
  bid accumulation.
- A-memory's authorized prior motif gains an arm-specific exact refinement: its
  broader negative-drift window contains a positive final 298.144-second price
  response while bid-heavy depth persists. This remains only in A-memory's
  promoted capsule and never enters A-clean.

The next chat must preserve both views. Daily averages remain equally prominent
when valuable, while exact members determine causal mechanism. Differences due
to estimand, scope, or granularity remain `COMPLEMENTARY_SCOPE_DIFFERENCE`.

## Positive repository artifacts

| Path | Role | SHA-256 |
|---|---|---|
| `research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md` | Concise, self-contained controlling RT mission | `e5bb8435387d3b73b5bca8c62f5bedc7f00425cab9d046593856d9c5271edc03` |
| `research/kalshi/agents/frankie_native_raw_mbo_rt_positive_discovery_addendum_20260828.md` | Detailed positive discovery and native observation contract | `ae4209670d37c2f324c17c3fa39cce8f7b45d273773f5b9070a00831b2626f48` |
| `research/kalshi/agents/frankie_native_raw_mbo_forecaster_first_replay_review_20260828.md` | Same-arm bounded Forecaster review of first replay outputs | `b32ca5c35db11430c3bf29d8bf597c5ba0d495af499f4f680ea4c95c6c719903` |
| `research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_RT_NATIVE_MBO_POSITIVE_DERIVED_FINDINGS_20260828.md` | Mechanically reproduced exact positive family inventory | `8c67fdbf5d2995657a0020200632def3fe1b2d70f1b4573c906b3a124959f8af` |
| `research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_RT_ACTUAL_FRANKIE_INTERIM_POSITIVE_REPORT_20260828.md` | Bounded retrospective A-clean Frankie positive report | `f09c94a7453ecf1faa756d255969ad9258ec766f9115d2452caa76408bdc9987` |
| `research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_RT_ACTUAL_FRANKIE_NONAVERAGED_EXTRACTION_OPPORTUNITIES_20260828.md` | Eleven exact extraction programs with eleven coequal averaged companions | `52c17005a947586def2dea79a579e48f80524264e970a50b08fce21340eea046` |
| `research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_FORECASTER_FIRST_REPLAY_OUTPUT_POSITIVE_REVIEW_20260828.md` | Bounded A-clean Forecaster output review; no replay | `f8a092c8e32e94b1081b1a246d98a73428a8b10dc18d7adfbe86db1fffa508c2` |
| `research/kalshi/frankie_raw_mbo_benchmark/AMEMORY_FORECASTER_FIRST_REPLAY_OUTPUT_POSITIVE_REVIEW_20260828.md` | Bounded A-memory Forecaster output review; no replay | `b02a1a19a21a878e9d0c52294db18fd2f6810624a41a7e9a5773a01538a8d9dc` |
| `research/kalshi/frankie_raw_mbo_benchmark/FRANKIE_KNOWLEDGE_USE_AND_NONFORGETTING_REVIEW_20260828.md` | Actual Frankie audit of knowledge use and non-forgetting gates | `4e80987a3486d7bfe992192b8cf46706452d43dbeb0e30ca0721b45815669442` |

The A-clean retrospective report is not a substitute for the later corrected
full mission-bound RT rerun. The opportunity memo proves that much richer exact
and averaged analysis can be extracted from the intact native evidence.

## Current runtime state

### A-clean RT diagnostic evidence

- Run: `frankie-a-clean-rt-33161766927-1`.
- Runtime: `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/`.
- Replay: `5,667,689 / 5,667,689`, `4,256,603` closed groups.
- Controller checkpoint labeled final/locked:
  `2e10b3f2534aaf697129831608a8e65fd9c4ac8ca92ec171c2a012fe8593b384`.
- Historical first-lock label:
  `ef728adf5ae2064c242f0e72acbf95f1d5b586a3f1845bed9ac9577ea998dd42`.
- Historical freeze label:
  `bc7e8ed9dbcb08177d46a48f16176afb026f5efe0c6fa49164260877fd172793`.

These three identifiers preserve controller history only. They are not valid
scientific Frankie lock/freeze proof because no principal Frankie call occurred.

### A-clean Forecaster diagnostic replay

- Run: `frankie-a-clean-forecaster-33161766927-1`.
- Runtime:
  `/workspace/scratch/da00127ac123/a-clean-forecaster-runtime-33161766927/`.
- Latest verified closed checkpoint: sequence `11`,
  `a4b03f66aa5446da2933671ae6fedaefc06dad3104812872668a02eeb20047fc`.
- Progress: `4,000,000 / 5,667,689` (`70.575502643%`).
- Groups: `3,024,930`; `event_group_open=false`; `locked=false`.
- Adapter hash:
  `e7d13b5e406a4afa4dabda00cffa0f414347c717ba5aad4e928e731f79cdef75`.
- Controller hash:
  `aef5cb1e076d322fbcb1ce88179223816c99fd0a6997792a067d1a7d4eef6ce2`.
- Complete 12-checkpoint chain and every adapter/continuation sibling verify.
- No replay process is running.

The recovery command for a later explicitly authorized diagnostic continuation
is:

```bash
cd /workspace/scratch/b2678c426534/Markets
python research/kalshi/frankie_raw_mbo_benchmark/a_clean_forecaster_resume_20260828.py
```

The helper now selects the latest valid chain tip, restores exact snapshots, and
rebuilds/audits the entire causal prefix before accepting the next record. Do not
run it merely to perform the bounded output review.

### A-memory RT diagnostic evidence

- Run: `frankie-a-memory-rt-c7da7d257fda-1`.
- Packet: `amemory-rtpkt-4eed0d33d524b7388db5`.
- Packet root: `/workspace/scratch/da00127ac123/a-memory-packet-c7da7d2/`.
- Runtime: `/workspace/scratch/da00127ac123/a-memory-runtime-c7da7d2/`.
- Replay: `5,667,689 / 5,667,689`, `4,256,603` closed groups.
- Final diagnostic checkpoint: sequence `16`,
  `07a407f5616a5a65f8345f8f44728506f1ea5c243c3114204ab1f471df92637b`.
- Phase: `RT_NATIVE_REPLAY_COMPLETE`; `event_group_open=false`; `locked=false`.
- Adapter hash:
  `8d0c9cacb7d02212e6b13198b99ea240a7d2dd42e47c7e9c2a6422d560ee603a`.
- Controller hash:
  `25aa739837aab845810b11b1f13c6012154ebd6fb5468dfb3a0817014cebab3d`.
- Evidence-bundle internal hash:
  `94a32deafdcb580868ba24df829b616edf36a80f84f80b7cd828efea24a13b36`.
- Evidence-ledger file SHA-256:
  `bc0788b51a719d39f5024f10007f4c74e96ff3361a21b66d662d9fadf1a67d8f`.
- Observation object hash:
  `dce8b9c3808cf0c5321e53879e0b4d504c267d037c9e0a276875bde6d4ff12ef`.
- Status: `READY_FOR_POSITIVE_DERIVATION`.
- `scientific_frankie_lock_created=false`;
  `scientific_rt_freeze_created=false`; `forecaster_authorized=false`.
- Complete 17-checkpoint chain and all adapter/controller siblings verify.
- No replay process is running.

Recovery from sequence 7 was independently audited against the prefix before
record 2,500,001. The receipt is
`resume-recovery-receipt-000007.json`; interrupted evidence was quarantined;
`uncheckpointed_tail_used=false`. The generalized helper then completed the
diagnostic replay without creating a scientific lock.

### A-memory Forecaster

No full A-memory Forecaster replay has started. The bounded read-only review of
the completed same-arm replay outputs does not change that state and creates no
lock or authorization.

## Repository machinery inventory

| Path | Role | SHA-256 |
|---|---|---|
| `.github/workflows/frankie_a_clean_rt_native_launch_20260828.yml` | A-clean packet staging and native hash binding; does not call Frankie | `fd9ea34473f86b93abd3cd86cd8d25db8c326fd5a1d918c6971b232249913f34` |
| `.github/workflows/frankie_a_memory_rt_native_launch_20260828.yml` | A-memory packet staging plus memory binding; does not call Frankie | `3f030e10d739a2a71fd73022a981a76d052d3fec2d7f1e949243bcf5bb509aa7` |
| `research/kalshi/frankie_raw_mbo_benchmark/chat_packet_seam.py` | Arm/input isolation and native envelope contract | `62b410cfd3a3da1ce5cb373af5b0f763bf26d271ab4cefa6bca4fe346907c274` |
| `research/kalshi/frankie_raw_mbo_benchmark/raw_mbo_source_manifest.py` | Source roster, hash, and record denominator | `7229bfc2d4befa4664aabca4b0321fd39a2c281c846022e5ec2cfdd975ae75e9` |
| `research/kalshi/frankie_raw_mbo_benchmark/mbo_resume_state.py` | Exact adapter export/restore | `e7d1dcf3a66c10bd4c2342c8e35d79ea5a58cbf44952bfbdb2b3195a7b1dd7e3` |
| `research/kalshi/frankie_raw_mbo_benchmark/benchmark_checkpoint.py` | Atomic closed-group hash chain | `06934557cf0441dac31d0abd3aafc9ae05e35a1d17a684480cf605a652e8cbf7` |
| `research/kalshi/frankie_raw_mbo_benchmark/native_evidence_bundle.py` | Exact raw-action ledger and evidence bundle | `a1d6d1e41d519a956754f6199f5a14825c243776b3c328ca9e2956ae909149ae` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_clean_rt_replay_20260828.py` | A-clean diagnostic native replay; no Frankie call | `0bb2c89ec0acb80d5725e574e521c0844962d9f66b4b60077956bb5cb1cb2c8e` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_clean_forecaster_prepare_20260828.py` | Historical controller handoff builder; labels are not scientific proof | `73d899af5a0b771497f8b25cda4e4d01320e975ea02f8afe73dc9cb61834d5fa` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_clean_forecaster_replay_20260828.py` | A-clean Forecaster diagnostic replay/controller | `44b75be9eb7fc4c00abcd287f26ec6d2ecf7b7cefb5e1eb412e3b88af97a706f` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_clean_forecaster_resume_20260828.py` | Latest-chain A-clean Forecaster recovery with sibling/prefix audit | `4af07fd03e193157dc8073697c08afb4b215700acd2c6d4a686315b0fe35ed4b` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_memory_prepare_20260828.py` | Memory-proof validation and A-memory packet builder | `0b19480edd0679be7b64f7a5dd50a66b4fa16ed8f26175ec8cf4e77d47550236` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_memory_rt_resume_20260828.py` | Historical sequence-2 A-memory recovery helper | `6406cdca918c6557b75973717b83298aaab676116511cbc64fae3194815104e9` |
| `research/kalshi/frankie_raw_mbo_benchmark/a_memory_rt_resume_latest_20260828.py` | Latest-chain A-memory recovery, prefix/tail audit, diagnostic completion | `ec27b196408635e36541b555fda85a127c1e19dd3dd5db0c790551ddcc9e12d1` |
| `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py` | Canonical full-state native replay | `838997142a543ba6c5ba6b86277c66d9465ad4e62ee85c5b1ec9ac177eaa8120` |
| `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` | Full-depth resting-order/FIFO adapter | `4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce` |
| `research/kalshi/ng_exhaustion_two_frankies_workmode_packet_2day_20260825.py` | Historical packet layout only; never reuse reduced input builder | `6170f70e5ed3f4b1c1aa99631a32514c068623711d24ffaee979c9d676459bda` |
| `research/kalshi/ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825.py` | Historical sequential lock/handoff behavior only; requires real model proof | `2c7cf46f7cdaf5784be2eaf02d941efef8ed4f0762a49933d4dad3774a9767b5` |
| `research/kalshi/frankie_raw_mbo_benchmark/native_frankie_knowledge_registry.py` | Fail-closed artifact validation, arm/role routing, deterministic bundle and receipt builder | `36c4f5d4165783819fa4fa0b63c71578aaf4879f045d4c1c0756695d38095561` |
| `research/kalshi/frankie_raw_mbo_benchmark/refresh_native_frankie_knowledge.py` | Deterministic capsule/manifest refresh and unregistered-file detection | `cd86357cf9db1b56232bb4956302f5306f3da30127e99221cd2060eb684702e3` |
| `.github/workflows/frankie_native_knowledge_refresh_20260828.yml` | CI validation and reviewed refresh-PR automation | `25983bbbbea3a8bb99ff757565dea4c75a53d9ed5ef000797bfa96e3a9b15d8c` |

## Anchored knowledge base and automatic refresh

The native A-arm knowledge base is anchored at
`research/kalshi/agents/frankie_native_raw_mbo_knowledge/`.

- `KNOWLEDGE_SOURCES_20260828.json` is the reviewed editable registry.
  File SHA-256:
  `bd9885765df225effe3039e29b3fe524e3e718e5b0ce49e99c9ad7f3afbf52d9`.
- `A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md` and
  `A_MEMORY_POSITIVE_KNOWLEDGE_20260828.md` are generated, same-arm promoted
  capsules.
- `KNOWLEDGE_MANIFEST_20260828.json` content-addresses every always-loaded and
  retrieval artifact. Its canonical manifest hash is
  `ad9787b0099a768960dd43fc29fc7ec068d938cbabe95a78a25e9376e322e16b`.
  Its file SHA-256 is
  `3d89bcf8b579f3b3225ef1af15e3aecd0be98973c3b7374d9680b55013491ec4`.
- `native_frankie_knowledge_registry.py` validates bytes, routes arm/role
  profiles, builds exact principal contexts, appends a compact hash-bound
  retrieval index, verifies external proofs, and writes context and principal
  knowledge-use receipts.
- `refresh_native_frankie_knowledge.py` regenerates promoted capsules and the
  manifest, and fails if a managed positive-knowledge file is not registered.
- `.github/workflows/frankie_native_knowledge_refresh_20260828.yml` validates
  every change and can create a reviewed refresh PR on manual dispatch. It never
  silently promotes model output or rewrites the controlling mission.

The four profiles are `RT_A_CLEAN_SECOND_PASS`, `RT_A_MEMORY_SECOND_PASS`,
`FORECASTER_A_CLEAN_REVIEW`, and `FORECASTER_A_MEMORY_REVIEW`. A principal call
is lock-ineligible unless its model-call receipt binds the profile, manifest,
exact context bundle, and context receipt; A-memory must also bind the external
prior-package proof. Full positive reports remain hash-bound in the retrieval
catalog, while the concise same-arm capsule is always loaded.

Actual Frankie audited this design and identified one call-boundary gap: the
initial registry version proved construction but not exact principal-input
consumption. That gap is now closed by `build_model_visible_context()` and
`bind_principal_knowledge_use()`. They fail on a missing byte, wrong profile or
manifest binding, incomplete retrieval disposition inventory, or external-proof
drift. Future runners must make the first-lock/freeze validator depend on the
resulting `FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_KNOWLEDGE_USE_V1` receipt hash.

## Scientific execution-proof gate for corrected reruns

No future RT or Forecaster lock/freeze is valid unless receipts prove the exact
mission bytes were loaded, the named principal model actually ran, the model's
context/usage identifies what it saw, and the validated model output—not replay
summaries—is the locked object. Checkpoint immediately before and after every
expensive model call. A path, boolean, completion counter, or lock-named file is
not proof.

For each arm preserve this order:

1. verify packet, mission, source, and—only for A-memory—memory package hashes;
2. run mission-bound RT over the lawful native causal envelope;
3. validate and first-lock the actual RT output;
4. freeze RT and create a one-way positive handoff;
5. only then run same-arm Forecaster;
6. validate and lock the actual Forecaster output; and
7. write artifact manifest and completion receipt last.

The bounded first-replay output reviews are exploratory positive research and do
not satisfy these full-run gates.

## Verification completed in this housekeeping pass

- A-memory resumed only after full chain, adapter, controller, source cursor,
  group count, causal watermark, memory package, and evidence-prefix audit.
- A-memory reached 100% and preserved `event_group_open=false`.
- A-clean Forecaster complete chain and every available adapter/continuation
  sibling verify through sequence 11.
- Focused recovery tests: `7/7` passed.
- Complete benchmark test discovery: `29/29` passed.
- Python compilation and `git diff --check` passed.

The housekeeping method used the pinned `addyosmani/agent-skills` release
`0.6.7`, commit `df1edb2e05487d0aa6d93c747141e0aed1187f25`. In particular,
`context-engineering` (SKILL SHA-256
`ff9d4e5706bdd2eb7de1bfed569f1f42d28e478979ce6fcc32e617e7861b491d`)
produced the focused hierarchy above: one concise controlling mission, a
separate Forecaster directive, detailed positive provenance outside principal
context, and task-local runtime evidence. This prevents context starvation,
stale-report leakage, cross-role mixing, and unnecessary context flooding.

## Next-chat order

1. Read this handoff and the focused context hierarchy above.
2. Review the two bounded Forecaster output-review reports; do not reinterpret
   them as full runs or locks.
3. Produce the positive-only A-memory RT retrospective research report from its
   completed same-arm diagnostic evidence and verified prior memory.
4. Decide explicitly whether to finish the preserved A-clean Forecaster
   diagnostic replay; if authorized, resume only from sequence 11 with the
   latest-chain helper.
5. Do not begin a full A-memory Forecaster replay before a valid same-arm RT
   scientific freeze and one-way handoff.
6. Plan corrected full mission-bound A-clean and A-memory reruns separately.
7. Preserve Step-1 sealing and arm isolation throughout.

Before beginning a full rerun in the next chat, ask Frankie whether additional
valuable information can be extracted from the first run's original analytical
focus when the same quantities are calculated without averaging and paired with
their averaged views. Preserve exact members and strata; do not turn this note
into a pooled or smoothing instruction.

Also ask actual Frankie to audit the full execution identity before any rerun:
exact requested/served model and provider, principal invocation evidence,
profile/manifest/context/serialized-input hashes, usage receipt, response
identity, and first-lock/freeze linkage. The knowledge-use receipt implemented
here covers the context plane; the next audit must verify the complete
end-to-end principal execution identity.
