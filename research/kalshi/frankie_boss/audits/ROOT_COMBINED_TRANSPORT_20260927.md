# ROOT combined transport and frozen ledger source package — 2026-09-27

Current status at 09:43Z: implemented, staged, active and verified through a post-activation full-state checkpoint. Canonical ROOT is runtime293113435a8fdf7bd5566f2652e1a1f7a1734c35, PID56833, workflow36309059667. Earlier sections retain the measured basis and ordered handoff history.

## Actual basis

Read-only progress workflow 36308440564 observed 1,166,757 / 2,032,203 records (57.41%), failed=0, alive, at 1790500144.804435 (09:09Z). Four full checkpoints saved/read_verified; latest checkpoint-000003.json. Interval since workflow 36307444156: 109.84 records/s over 1,128.63 seconds, including checkpoint overhead. The earlier short post-fix interval was 120.265 records/s versus the earlier 64.74; these are different real intervals, not a controlled comparison.

Retained post-fix profile 36306860732 and readers 36306968197 / 36306996610 identify duplicate evidence/census freezing and output receive work. Existing worker CPU time was 75.54 CPU-seconds over 30 seconds. Profile pins and phase-one receipts remain in ROOT_WORKER_TRANSPORT_ACTIVATION_20260927.md.

## Implemented changes

1. Inside the exact pinned NativeCalculationRun.note_member_row call, census freezes the member row once and evidence consumes that same immutable protocol-5 pickle. The original method is still invoked; scoped object identity, one offer/use, nonnesting and removal of the wrapper at every full-state checkpoint are enforced. Unrelated rows are frozen independently. Census reads its input without mutating it.
2. Two existing evidence encoders run the unchanged pinned RowSink.write. Encoded bytes go to producer-owned shared-memory slots. ROOT receives offsets/accounting, commits and hashes exact views in ledger order, and only then offers the next batch. The producer owns unlink, attach uses Python 3.13 track=False, and no live view crosses slot reuse. Output is not capped.
3. Full checkpoints retain immutable ordered ledger segments with explicit byte extents, logical bytes and original SHA256. Resume reads/hashes those exact bytes with bounded parallel prefetch; it does not physically rewrite old prefixes before calculation starts. A new generation appends only new bytes to new files. Original files and post-checkpoint tails remain untouched.
4. Three independent I/O workers assemble ordinary complete ledger files while calculation continues. They verify prefix and whole-file SHA256 and counts, fsync, and atomically replace only the same fresh zero-byte placeholder. Finalization waits for these actual receipts before using unchanged pinned reconciliation. Original segments remain retained. These workers are pinned to reserved CPU0; the 15 native/evidence processes remain on CPUs1–15.

The prefix still must be read to restore ordered SHA256 state. Physical whole-file copying still occurs in the background for existing downstream readers; this package removes it from the startup critical path, not from all I/O. No claim of a combined speedup has been made.

## Review and transition

The exact candidate code in 19e2da01e6b3804d29550e0aa054a2cf66ba3a94 passed Python syntax compilation without importing or running calculators. Review follow-up fdc6328f97632a27f273ce1cd82481479697ab24 retains completed ledger-transfer receipts and completes cleanup of its own I/O children. Review covered pinned member/census/RowSink methods; checkpoint external bindings and barrier order; shared-memory ownership/reuse; ordered extent restoration; append freeze and final publication; finalizer writes; closed sinks; and the existing PID-token pause route, which discovers all owned spawn children without assuming a fixed count.

Only the exact phase-one checkpoint serializer/policies are accepted as predecessors; current Python/cloudpickle and complete producer/source identity must match. New checkpoints include the ledger-storage implementation hash. Complete driver, census and book state remain checkpointed; incomplete background assemblies contain no unique state and are not checkpoint dependencies.

- [x] Implementation source and manual static review.
- [x] Candidate syntax compilation; final changed bytes also compiled successfully at fdc6328f97632a27f273ce1cd82481479697ab24.
- [x] Immutable inactive staging receipt.
- [x] Fresh read-verified full checkpoint and identified old ROOT/worker exit.
- [x] One canonical resume and restored ledger/cursor receipt.
- [x] New runtime worker receipt, forward progress and post-activation full checkpoint.
- [x] Actual combined throughput measurement.

No extra scientific test, canary, comparison calculation, model inference, ingestion replay, infrastructure stop, bootstrap change, agent delegation or orchestration was introduced. Granite's retained priming binding remains configured but actual package delivery and acknowledgement are pending in the real Monday sequence. All historical sections/hashes, slots and producer groups remain required.

## Actual checkpoint handoff — 09:20Z

- [x] Pause workflow36308640458 saved/read-verified checkpoint000004 at1,215,705records (59.82%); identified PID56172 and all14owned native workers exited. Pause receipt1270bytes SHA256208f43b0066159483c36b1a138c58e78c8679b81085f67254e4cbf4e13058150. All files/tails preserved.
- [x] Full descriptor read36308965747:10525bytes SHA256fb78159f28f2cafcb88c94276bf0f04007900789fdb3bafda4529e6adbd32a73. Driver state293255540bytes SHA256171d6984a06f5b636a0431504c8cb99e52939a2495c8885751c319ce6c5a6967; finalized=false; Python/cloudpickle and exact predecessor serializer match.
- [x] Frozen ledger prefixes: member312183215696bytes/906982rows SHA256786f05de4b8a57375e1bfc461350ca0211562587d453464d2729f33e8ae3166e; lifecycle6071380890bytes/6568550rows SHA2569f3979ee62fa0f29c71e98681a78fc98e4cf8129b741765d0cc00d597ef3218d; legacy766552961bytes/583556rows SHA2562896256c1b69d7c3cb0d524a6840071f08f85c65a1486d7c01e10bd3d1bb4ff0.
- [x] Immutable runtime293113435a8fdf7bd5566f2652e1a1f7a1734c35 staged by36308610841; source pack589523154bytes/3676files SHA25629eab7876dbc38c6db3857a02aeabbda1e0d87f564ab48f7c5a79234cbf44a80; intent85e793aba0f28c823071c93360b0ab9deec91234c959c18249eb7ec9522f51c0. CODE_ROOT=/opt/frankie-box/code/293113435a8fdf7bd5566f2652e1a1f7a1734c35-36308610841-1/markets. Existing workflow serial lock required pause before staging; staging did not overlap the active calculation.
- [x] One resume dispatched in36309059667 on codex/frankie-shared-ledger-runtime-2931134, from recovery-03a70711353a433c989b18074d7baacd/checkpoints/checkpoint-000004.json, same root/authorship/binding/48readers. No reconstruction flag.
- [x] Restored-state and activated worker receipts were subsequently verified below. First probe36309073512 read the old exited process status during startup, not a newly activated worker receipt. No second resume was dispatched.

## Activation receipts — 09:37Z

The combined package is active on PID56833, token099d4eb6-a46d-4b94-a888-f15e55c1ee7e:52429441, generation recovery-9defa3169f7d46679491da2b1bfbbce2, workflow36309059667. No duplicate resume was dispatched.

Restored checkpoint000000 at1,215,705records was read_verified at1790501391.3419423. Descriptor read36309609758:11932bytes SHA2566fea1728c85b798f2ae0422ee1416e3ae79301111b879e6d926ce35cb78a6f53; driver293274666bytes SHA256a9cf747fc1c682ea4c7fc3979b17a000a547a1c2bc408f1e4d78f83144024063. Every parent ledger attribute, logical byte count and hash matches exactly. Each ledger descriptor uses FRANKIE_LEDGER_SEGMENTS_V1 with the original frozen prefix and a new zero-byte append segment. Runtime serializer629b1355de7539e84fb8142343b182dc06cfe5033aaa3f6bf837962317a5cf76 and ledger storageb66361659495d787329a6097384df10bf4f27fc3056b511ee46f53bb7119c760 are bound.

Worker receipt read36309706680:7228bytes SHA25630f98db4106c00cbf47bf3be02dcac6afd03befc1516c6e6b22258ee9ce0c417. It records V3 evidence/auxiliary policies, exact V2 predecessor history,15native/encoding processes on CPUs1–15 and3I/Oworkers onCPU0. I/O PIDs56976(member),56980(lifecycle),56983(legacy); queue57024, replenishment57025, census57026, books57027–57035, encoders57036/57037. Worker activation1790501394.4926064 at the preserved cursor.

Observed forward rate: workflow36309607776 reported1,224,299 at1790501465.230355; workflow36309720269 reported1,248,729 at1790501645.288801, failed=0/alive,61.45%. The180.058-second interval is135.678records/s while background assembly runs. Earlier phase-one short interval120.265 and initial64.74 are different portions of real work, not a controlled comparison.

The normal-running30-second profile36309737904 is retained at work/performance/profile-1790501617950359822/profile-receipt.json,167083bytes SHA256ad0bb4c62757cb37ddf881db0239486f6f39fe9e66bfa29e35afd91e7d1ac982; compact reader36309854694. ROOT profileSHA2565de4b1c559d0253689a75c1369a56f9469476c76f6f6fb519af5bd04e564a014. Largest ROOT serialization leaf16.341% versus phase-one24.066%; auxiliary receive15.203%; pipe recv6.504%. Total101.15CPU-seconds/30seconds, of which18.77 are ledger I/Oworkers and82.38 native/encoding. ROOT24.75CPU-seconds; census12.87; encoders11.14/11.13. Sampling remains observational; no extra calculation was executed.

Restoration inspection36309226605 observed9,965,666,304read characters over10seconds with new full-ledger files at0bytes and only294912ROOTwritten bytes. Inspection36309511522 then observed verified-prefix completion, three actual I/Oworkers, fresh append files and a restored-state checkpoint being written. All previously retained file sizes remained unchanged. Prefix verification and physical background copying are distinguished; no claim that hashing or all copying disappeared.

- [x] Immutable staging and fresh checkpoint handoff.
- [x] Exact restored ledger attributes/hashes and complete-state readback.
- [x] Active V3 transport/worker receipt and forward progress/rate.
- [x] First post-activation full-state checkpoint with nonempty suffixes saved/read_verified at normal cadence; exact receipts below.
- [ ] Final whole-file materialization receipts remain pending finalization.

## Post-activation checkpoint and current progress — 09:43Z

Workflow36310178874 observed PID56833 alive, failed=0,1,303,120/2,032,203records (64.12%) at1790502112.0547266. Checkpoint000001 was saved/read_verified at1790502066.9800549. The checkpoint cursor is1,296,294records; ROOT continued normally afterward.

Descriptor read36310189787:11958bytes SHA256cf3ef0a75463556dd184c2451738d9d6ae536c22f4ba6a3fb229ad5793898ded. Complete driver state308388512bytes SHA25606f8ff56c4a1654899e34294071a49139f10f4c33f1cf1f8b1d54380d685e141. Every original prefix path/extent is unchanged, and each ordered prefix+suffix byte sum equals the logical ledger count:

- Member334215955174bytes/968411rows SHA256dbcd50439474699e93767e42b79d6e01e46bdc748aacc3fb7f11452eb593a6d6; old prefix312183215696bytes plus new suffix22032739478bytes.
- Lifecycle6479913485bytes/7010057rows SHA256afbfecbac6125e6ce2828f95a2ae202fffd03f06898d3f10109b9e61689166ee; old prefix6071380890bytes plus new suffix408532595bytes.
- Legacy824812785bytes/627902rows SHA256126178263b28c547d4a3ba08dc59958ed45f1d91689dd0ec15af631561520253; old prefix766552961bytes plus new suffix58259824bytes.

An additional normal forward interval (36309720269 to36310034380) advanced1,248,729→1,290,377 over300.088seconds:138.786records/s, failed=0. This is observed live throughput, not a same-input comparison experiment. Checkpoint pauses affect longer averages. Full-file publication/reconciliation and all remaining Monday stages are still pending. No further ROOT transition is needed for this package. Granite actual priming delivery/acknowledgement, principal/classroom/grading/corrections/retention, and Tuesday outcomes remain pending.
