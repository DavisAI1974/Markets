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

## 2026-08-28 corrected-work checkpoint

Published implementation checkpoint:
`405e01c2842b80b64f2c5190564f30ca18f0c195` (`feat: harden Frankie ingestion
and finish A-memory recalculation`).

The original-input A-memory member-first recalculation is complete:

- 5,667,689 / 5,667,689 native records;
- 4,256,603 / 4,256,603 F_LAST-closed groups;
- 4,758 deterministic candidate identities, including 4,628 open-world
  candidates and 19,847 exact open-world member groups;
- 3,159,886 maximal exact-family runs, including 654,478 multi-member runs;
- daily averaged companions reproduce the first replay exactly; and
- no supplemental corrected-rerun input, other arm, Step-1, reveal, scoring,
  model invocation, lock, or freeze was used.

The positive report is
`AMEMORY_MEMBER_FIRST_NATIVE_MBO_POSITIVE_FINDINGS_20260828.md`; the small
machine receipt is `AMEMORY_MEMBER_FIRST_RECALCULATION_RECEIPT_20260828.json`.
Both are hash-registered. The report's positive capsule candidates are promoted
into the always-loaded pared-down A-memory capsule.

The active ingestion contract now has 105 exact union identities, 102
applicable to A-clean and 104 to A-memory, plus a hard fail-closed minimum of
90. Count is not sufficient: the V1 exact ID-set hash is also fixed. Static
knowledge is visible pre-call; all 55 causal-stream layers remain pending until
each lawful F_LAST cutoff; all nine Step-1/answer layers stay sealed throughout
the current A scope; both S137 and HippoRAG are measurable shadow-only
components; and all 11 output classes begin pending and must become append-only
hash chains.

All old V3 result categories were removed from the active feed inventory. The
only V3-derived material permitted anywhere in the corrected input is the
correction-approved extra-agent information/gap diagnoses and four-helper
architecture, through these three exact carryforward records:

- `research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.json`;
- `research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.md`; and
- `research/NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md`.

No corrected scientific rerun has started.

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
| `research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md` | Concise, self-contained controlling RT mission | `1dde5590311ce9635a27eb6cdfa223004cf18aa99a008f98020f7ea9043f2928` |
| `research/kalshi/agents/frankie_native_raw_mbo_rt_positive_discovery_addendum_20260828.md` | Detailed positive discovery and native observation contract | `ae4209670d37c2f324c17c3fa39cce8f7b45d273773f5b9070a00831b2626f48` |
| `research/kalshi/agents/frankie_native_raw_mbo_forecaster_first_replay_review_20260828.md` | Same-arm bounded Forecaster review of first replay outputs | `b32ca5c35db11430c3bf29d8bf597c5ba0d495af499f4f680ea4c95c6c719903` |
| `research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_RT_NATIVE_MBO_POSITIVE_DERIVED_FINDINGS_20260828.md` | Mechanically reproduced exact positive family inventory | `8c67fdbf5d2995657a0020200632def3fe1b2d70f1b4573c906b3a124959f8af` |
| `research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_RT_ACTUAL_FRANKIE_INTERIM_POSITIVE_REPORT_20260828.md` | Bounded retrospective A-clean Frankie positive report | `f09c94a7453ecf1faa756d255969ad9258ec766f9115d2452caa76408bdc9987` |
| `research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_RT_ACTUAL_FRANKIE_NONAVERAGED_EXTRACTION_OPPORTUNITIES_20260828.md` | Eleven exact extraction programs with eleven coequal averaged companions | `52c17005a947586def2dea79a579e48f80524264e970a50b08fce21340eea046` |
| `research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_FORECASTER_FIRST_REPLAY_OUTPUT_POSITIVE_REVIEW_20260828.md` | Bounded A-clean Forecaster output review; no replay | `f8a092c8e32e94b1081b1a246d98a73428a8b10dc18d7adfbe86db1fffa508c2` |
| `research/kalshi/frankie_raw_mbo_benchmark/AMEMORY_RT_ACTUAL_FRANKIE_RETROSPECTIVE_POSITIVE_REPORT_20260828.md` | A-memory retrospective RT role analysis over completed native evidence and verified prior memory | `2854c9b96d759c61c4afa750e5106c824fa81462e5a5d61ff55240f9cbda9df5` |
| `research/kalshi/frankie_raw_mbo_benchmark/AMEMORY_FORECASTER_FIRST_REPLAY_OUTPUT_POSITIVE_REVIEW_20260828.md` | Bounded A-memory Forecaster output review; no replay | `b02a1a19a21a878e9d0c52294db18fd2f6810624a41a7e9a5773a01538a8d9dc` |
| `research/kalshi/frankie_raw_mbo_benchmark/FRANKIE_KNOWLEDGE_USE_AND_NONFORGETTING_REVIEW_20260828.md` | Actual Frankie audit of knowledge use and non-forgetting gates | `4e80987a3486d7bfe992192b8cf46706452d43dbeb0e30ca0721b45815669442` |
| `research/kalshi/frankie_raw_mbo_benchmark/AMEMORY_MEMBER_FIRST_NATIVE_MBO_POSITIVE_FINDINGS_20260828.md` | Completed original-input exact-member/open-world positive report | `7b9bd3f11c28780900d76cfefd273ac7e9591c8e450b9b86b06a04fb8c32cde6` |
| `research/kalshi/frankie_raw_mbo_benchmark/AMEMORY_MEMBER_FIRST_RECALCULATION_RECEIPT_20260828.json` | Hash-bound completion and artifact receipt | `094c32a4177edee9c16e92a288427d6e5d3777f23db8d2f954f0c6d5f310a7c1` |

The A-clean retrospective report is not a substitute for the later corrected
full mission-bound RT rerun. The opportunity memo proves that much richer exact
and averaged analysis can be extracted from the intact native evidence.

The A-memory retrospective is the same diagnostic role-analysis class as the
A-clean retrospective and did not make a principal Frankie model call. Its
positive, mechanically supported results are scientific findings; the absence
of a principal execution receipt limits only lock/freeze provenance. The report
independently reproduces the native family surface, confirms the authorized
41-trade memory motif directly in native MBO, and adds a mirrored-side
formation-latency relationship across five families and both held-out days.

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
- Status: positive retrospective derivation complete; corrected full
  mission-bound rerun remains pending.
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
| `research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json` | Exact 105-identity ingestion/output registry with hard floor 90 | `ac3124acd80fcf2011d89614317d965e6e579ab776a8197046130079829c26e0` |
| `research/kalshi/frankie_raw_mbo_benchmark/native_ingestion_layer_registry.py` | Registry, pre-call, and per-F_LAST causal-delivery gates | `4a8f97ddc92b1a79f2fd0e79c8bdfcc93c4487e980887206c9ddb5d84dc967ac` |
| `research/kalshi/frankie_raw_mbo_benchmark/refresh_native_frankie_knowledge.py` | Deterministic capsule/manifest refresh and unregistered-file detection | `cd86357cf9db1b56232bb4956302f5306f3da30127e99221cd2060eb684702e3` |
| `.github/workflows/frankie_native_knowledge_refresh_20260828.yml` | CI validation and reviewed refresh-PR automation | `25983bbbbea3a8bb99ff757565dea4c75a53d9ed5ef000797bfa96e3a9b15d8c` |

## Anchored knowledge base and automatic refresh

The native A-arm knowledge base is anchored at
`research/kalshi/agents/frankie_native_raw_mbo_knowledge/`.

- `KNOWLEDGE_SOURCES_20260828.json` is the reviewed editable registry.
  File SHA-256:
  `46f8fb5b59b175e4113140dbf4cb139895331a316ef4a2d0c837fb399ed44584`.
- `A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md` and
  `A_MEMORY_POSITIVE_KNOWLEDGE_20260828.md` are generated, same-arm promoted
  capsules. Their current file hashes are
  `53a42357f5dd46b553ad73f34cb2023855a742a46398e9ec55beb8e4083b0188`
  and `bc84a77d33393c7d04185fcbfa82794cef0efd45b4fd31f0b2ee245cfb8d9131`.
- `KNOWLEDGE_MANIFEST_20260828.json` content-addresses every always-loaded and
  retrieval artifact. Its canonical manifest hash is
  `435ca83925b126300dfc64ceef940bf19794c157b52b543b17fb917fe1bef9a6`.
  Its file SHA-256 is
  `d84b923a8de0e2b336dd9f907103eafe242fcd75cc1db175b048b00c8f85f571`.
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

A separately requested `gpt-5.6-sol` advisory reviewed the exact-versus-average
question and execution identity. It confirmed that exact members add substantial
value beside daily averages, including boundary-member interpretation, complete
extrema rosters, exact family/lifecycle paths, and true matched-pair work. It
also reproduced a critical gate bypass: `validate_first_lock_and_freeze()` can
currently accept a rehashed controller-only execution because it does not
consume the successful principal-execution gate receipt. The coarse execution
gate is not yet wired into either workflow or runner, requested/served model
strings remain self-asserted, provider receipt bytes are not independently
verified, and the original evidence ledger did not serialize complete
before/after FIFO state for every member.

The advisory itself exposed no provider-originated receipt, so it is design and
audit evidence rather than a scientific principal-run receipt. Do not claim its
served model, provider, invocation ID, usage, or response identity as proven.
Close the identified gaps before any corrected rerun.

## Verification completed through implementation checkpoint `405e01c2`

- A-memory resumed only after full chain, adapter, controller, source cursor,
  group count, causal watermark, memory package, and evidence-prefix audit.
- A-memory reached 100% and preserved `event_group_open=false`.
- A-clean Forecaster complete chain and every available adapter/continuation
  sibling verify through sequence 11.
- Original-input A-memory member-first derivation completed and all output
  artifact hashes were recorded in the committed machine receipt.
- Registry-focused tests: `11/11` passed.
- Complete benchmark test discovery: `60/60` passed.
- Knowledge refresh/check is current at canonical manifest hash
  `435ca83925b126300dfc64ceef940bf19794c157b52b543b17fb917fe1bef9a6`.
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

1. Read this handoff, then validate the branch tip and every current hash before
   editing.
2. Preserve the completed A-memory member-first report and receipt. Do not rerun
   that original-input calculation unless an artifact hash fails.
3. Do not resume the preserved A-clean Forecaster diagnostic replay from
   sequence 11. It is unnecessary for the A-memory output-improvement task and
   remains unauthorized.
4. Integrate `native_ingestion_layer_registry.py` into the actual packet and
   model-call seam. Pre-call must validate all 105 identities, the exact
   arm-applicable set, the hard floor of 90, static hashes, causal-stream
   readiness, nine sealed layers, shadow status, and pending append-only
   outputs. Every F_LAST group must then bind all 55 causal layers and the
   previous delivery-receipt hash.
5. Implement one real provider adapter for requested model `gpt-5.6-sol`.
   Capture provider-originated requested/served model, provider/service,
   invocation/request/response IDs, raw request/response hashes, token usage,
   timestamps, and response/output identity. Self-asserted strings or booleans
   must fail.
6. Bind actual serialized input bytes through
   `build_model_visible_context()` and `bind_principal_knowledge_use()`, the
   selected profile, current mission, calculation contract, knowledge manifest,
   ingestion registry, A-memory prior package/proof when applicable, pre-call
   receipt, and complete causal-delivery chain.
7. Close the reproduced lock bypass. Lock/freeze validation must consume a
   successful principal-execution gate receipt and validated output object,
   verify the real pre/post checkpoint chain, and atomically bind the principal
   response bytes. A controller summary can never be locked.
8. Finish the calculation implementation still absent from the initial
   member-first baseline: complete before/after FIFO and priority lifecycle;
   deterministic session/phase segmentation; true mirror matching with
   distances and unmatched rosters; all causal clocks; replenishment,
   resilience, absorption, withdrawal, and ladder topology; exhaustion
   runways; PRIOR/T0/H+N; dipole paths; D-depth lineages; open-world discovery
   fit/freeze receipts; and fixed/event-driven future-response tables with
   at-risk denominators. Preserve exact members first and averages only where
   separately valuable.
9. Run full preflight and stop on any mission, knowledge, execution identity,
   native-data, arm-isolation, or causal-delivery failure.
10. Only after all gates pass, perform each corrected arm sequentially:
    mission-bound RT -> actual model-output validation -> first lock -> freeze
    -> one-way same-arm handoff -> Forecaster -> final validation and lock.
    Never start Forecaster before its same-arm RT freeze.
11. Keep all nine Step-1/answer/reveal layers sealed throughout this A-only
    mission. Do not perform BOSS, B0/B1/B2, Granite, reconciliation, or scoring.

The exact-versus-average question and complete execution-identity audit were
asked in this chat. Their advisory answers are incorporated above. They do not
remove the need for provider-originated receipts in the corrected scientific
runs.
