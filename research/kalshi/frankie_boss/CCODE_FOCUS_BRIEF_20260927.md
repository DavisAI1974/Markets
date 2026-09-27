# CCode Focus Brief — Frankie/BOSS Monday Recovery

Date: 2026-09-27
Repository: DavisAI1974/Markets
Branch: claude/agent-skills-execution-tzh7sw
Latest branch tip: 2d57446eb8ce3ec477fba33bc2a9318c3bf82299
Canonical handoff: research/kalshi/frankie_boss/CODEX_HANDOFF_20260927_PROJECTION_RUNTIME.md

## Mission

Finish the already-running Monday sequence from retained evidence. The immediate operational objective is:

1. regain a command path to the existing Frankie box;
2. execute the user-approved retirement of exactly five superseded member-ledger files;
3. obtain actual deletion and reclaimed-space receipts;
4. verify the existing ROOT is inactive and the retained terminal checkpoint is valid;
5. resume the SAME calculation root on the corrected immutable runtime, reusing compressed projection ranges and all retained work;
6. retrieve projection publication, digest and calculations completion receipts;
7. continue the existing manual Monday sequence through downstream save points, principal, classroom, grading, same-session correction and retention;
8. leave Tuesday and learning outcomes pending until real evidence exists.

Do not start a new calculation, rebuild scientific records, replay ingestion, create a new orchestration layer, duplicate staging, or infer completion from counters.

## Source of truth and precedence

Read the newest section of the projection-runtime handoff first. Newer user decisions supersede every older handoff, audit and CLAUDE.md paragraph. Treat archived RUNNING/PENDING text as historical.

Required reading:

- research/kalshi/frankie_boss/CODEX_HANDOFF_20260927_PROJECTION_RUNTIME.md
- research/kalshi/frankie_boss/audits/SUPERSEDED_LEDGER_RETIREMENT_20260927.md
- research/kalshi/frankie_boss/audits/PROCESS_SAVE_POINTS_20260927.md
- research/kalshi/frankie_boss/audits/PROJECTION_ANALYSIS_IO_20260927.md
- research/kalshi/frankie_boss/CODEX_HANDOFF_20260927_CLASSROOM_QUEUED.md
- CLAUDE.md

Use the existing manual workflow. Keep the orchestrator PLAN ONLY.

## Immutable identities

Repository and branch:

- DavisAI1974/Markets
- claude/agent-skills-execution-tzh7sw

Corrected ROOT runtime:

- commit: 2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a
- ref: codex/frankie-projection-runtime-2d3e6bb
- successful staging run: 36323776583
- CODE_ROOT: /opt/frankie-box/code/2d3e6bbf61f8f7be0568107abb618ba2d3e6bb-36323776583-1/markets

Correction: the CODE_ROOT string above must use the exact staged path recorded by the successful staging receipt:
`/opt/frankie-box/code/2d3e6bbf61f8f7be0568107abb618ba2d3c62b6a-36323776583-1/markets`
Verify the actual receipt before using it. Never invent a path from memory.

Calculation root:

`/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`

Source binding SHA256:

`99440a65fe5ad6fa93fbeebdfda3391d9dfcbf58abb3251661e6f76adea2d90a`

Authorship receipt:

`/opt/frankie-box/work/monday-launch/full-20211004-20260923-r4/authorship-receipt.json`

Authorship SHA256:

`ade460dede20a4557b6369ca45f653fdae24a958fd52d1f1e449da53fe8e2ec6`

Retained complete scientific generation:

`recovery-9defa3169f7d46679491da2b1bfbbce2`

Current full terminal checkpoint:

`work/bedrock/recovery-8c03f629f01747158535f3cfa4f01f2d/checkpoints/checkpoint-000000.json`

Checkpoint SHA256:

`2d61559ca9f5c650cdb22fa9aff29b8f0a366a648983493d435c26a3387943e6`

Logical checkpoint hash:

`c3281f870a457f9ccf0827ca54a88adc99712cfb6dd3492f7a02a94019bfbecb`

Checkpoint facts: locked; 2,032,203 completed records; same adapter/source/run identity. Preserve the descriptor, driver, all current ledgers, historical sections/hashes, compressed ranges, partial publication and every receipt.

## ROOT status

ROOT workflow 36324470881 failed at 14:54:19Z during projection publication with:

`OSError: [Errno 28] No space left on device`

The failed ROOT process was PID 59092 with process token:

`099d4eb6-a46d-4b94-a888-f15e55c1ee7e:54118158`

The run had finalized all scientific records before the publication failure. Projection publication, digest and calculations-receipt.json are still pending. Verify PID59092 is inactive before resuming. Do not assume inactivity from the workflow conclusion alone.

The projection plan hash recorded before failure was:

`3ef241ac435253142680040976ab6f548b3119b1d73f26e6ca95bb9f78cb73b2`

Use the existing `.projection-v2/plan.json`, progress.json and range receipts. Completed compressed ranges are reusable only when plan, source identity, archive hash and byte coverage match. The highest range number is not an ordered frontier; use progress.json and ordered coverage receipts.

## Approved cleanup — exact scope

The user approved deletion of exactly these five files and no others:

1. work/bedrock/recovery-03a70711353a433c989b18074d7baacd/ledgers/exact_member_rows.jsonl — 312296413348 bytes
2. work/bedrock/recovery-d4b20c8f7e834d7abb1a435ff8199442/ledgers/exact_member_rows.jsonl — 231083239987 bytes
3. work/bedrock/recovery-7bd18d968a384248b02e58c74f5456c6/ledgers/exact_member_rows.jsonl — 186271626117 bytes
4. work/bedrock/ledgers/exact_member_rows.jsonl — 118280552448 bytes
5. work/bedrock/recovery-f13de5640bf549feaae493d8861bfae1/ledgers/exact_member_rows.jsonl — 97907529420 bytes

Approved logical total: 945,839,361,320 bytes.

Preserve every other file, directory and inode, including:

- current complete generation recovery-9defa3169f7d46679491da2b1bfbbce2;
- all three complete scientific ledgers;
- current and parent checkpoints and descriptors;
- driver and adapter state;
- compressed projection ranges and archives;
- partial publication evidence;
- lifecycle and legacy ledgers;
- receipts, states, historical sections and hashes;
- source journal and sealed recovery data.

Use the committed retirement script only:

`deploy/aws/box/frankie_box_retire_superseded_ledgers.sh`

Required confirmation literal:

`CONFIRM=RETIRE_SUPERSEDED_MEMBER_LEDGERS`

The script itself verifies terminal evidence hashes, exact target metadata, retained complete-ledger metadata, ROOT ownership, open descriptors and per-file receipts. It writes an intent before unlinking and emits a final receipt with allocated bytes reclaimed and available bytes.

Do not replace it with rm, find, recursive deletion, truncation, compression, move, or a hand-written command. Do not broaden the list.

## Access blocker and recovery history

Cleanup workflow 36327746090 failed. SSM command:

`00d2cb24-815f-4aeb-8d91-2048ba862098`

It returned zero stdout/stderr. Detailed control-plane inspection established:

- instance: i-035994afa8bdf66a5
- state: running
- SSM agent: Online
- volume: vol-0d36715924f03b86c, gp3, 2048 GiB, in-use
- public IPv4: 3.81.90.2
- public SSH ingress was absent; the default security group only allowed self-reference
- no EC2 Instance Connect Endpoint
- EC2 serial-console access disabled
- no other running SSM-managed peer in the VPC

The read-only observer 36327598526 failed because the SSM worker could not create:

`/var/lib/amazon/ssm/i-035994afa8bdf66a5/channels/a161e421-6163-44a9-9578-91913c94338e/tmp/master-20260927145439-000`

with `no space left on device`.

A temporary restricted-SSH recovery route was committed in the current branch, but it reached the AWS permission gate before attaching any security group:

`arn:aws:iam::568968024170:user/Claude` lacks `ec2-instance-connect:SendSSHPublicKey`.

No temporary security group was attached, no SSH command ran, and no host file was touched by that attempt.

To complete cleanup, obtain a command path with one of these explicit mechanisms:

- an authorized IAM policy granting only EC2 Instance Connect public-key push for this exact instance, followed by the existing temporary /32 route; or
- an authorized interactive AWS console/session path; or
- a functioning SSM command path after space is reclaimed by an already-running process.

Do not silently change IAM, open broad ingress, enable serial console, create a new instance, grow storage, stop/reboot the box, or bypass the retirement safeguards.

## Correct resume sequence

Only after a real cleanup receipt and capacity measurement:

1. Confirm all five target files are absent and the receipt exists.
2. Confirm the retained checkpoint SHA256 and descriptor SHA256 still match.
3. Confirm recovery-9defa3169f7d46679491da2b1bfbbce2 remains intact.
4. Confirm PID59092 and its exact process token are inactive.
5. Retrieve projection generation/range coverage and compressed receipts.
6. Resume the SAME calculation root from the verified full terminal checkpoint with:
   - corrected runtime 2d3e6bb;
   - original authorship and source binding;
   - DATA_WORKERS=48;
   - RECONSTRUCT_MISSING=0;
   - no source replay;
   - no new root;
   - no duplicate staging.
7. Preserve partial publication. Reuse valid completed ranges.
8. Read the actual projection publication receipt, digest receipt and calculations-receipt.json. Require actual hashes and status calculations_retained.
9. Use the verified downstream save-point runtime only after ROOT completion.

Do not resume merely because free space looks nonzero. Verify checkpoint, ownership, range coverage and receipt identity first.

## Downstream sequence after calculations receipt

The downstream save-point commit is:

`f98122fd71d41bc8ced7c36457b63ad91c54393d`

Ref:

`codex/frankie-downstream-savepoints-f98122f`

Staging 36326457453 failed without a source-pack/CODE_ROOT receipt. Do not claim it staged successfully and do not duplicate staging until access and capacity are restored and its failure is inspected. Use the existing inactive staging route for a genuine retry.

After successful downstream staging:

- generate principal inputs from actual calculations-receipt.json and retained knowledge;
- configure the existing Monday cycle with the prepared root;
- launch one actual host cycle and honor WAIT/ATTENTION;
- use the retained five-lesson Granite capsule in the first real request;
- verify delivery and acknowledgement from actual response evidence;
- run principal reading and mandatory classroom;
- record initial response;
- continue the same host session for grading;
- run same-session correction;
- record correction;
- run final grading;
- retain final corrected knowledge and all receipts.

Granite readiness/migration is complete by retained evidence. Actual delivery and acknowledgement are pending. Do not submit duplicate priming inference.

Tuesday and learning outcomes remain pending until actual labels/outcomes exist. Native learning must remain false in pending mode.

## Non-negotiable invariants

Preserve:

- both source members;
- all 23 trading hours;
- all 18 historical sections and hashes;
- required historical slots;
- all three repository producer groups;
- exact reducers and causal order;
- all 2,032,203 finalized scientific records;
- original authorship and source binding;
- exact checkpoint and ledger identity;
- original output semantics and no output caps.

Never:

- rebuild or replay scientific records;
- launch a duplicate calculation;
- create a new root;
- hot-patch a live interpreter;
- add tests, canaries, comparison runs or validators;
- use Amazon Bedrock;
- cap BOSS/Granite output;
- start parallel agents or new orchestration;
- write C:/ or E: artifacts;
- stop/reboot/resize/terminate infrastructure;
- delete anything outside the five approved paths;
- fabricate receipts, progress, Granite acknowledgement, learning or completion;
- interpret a stage-local counter as full-run completion;
- confuse producer scientific verdict REJECTED/cross_section_agreement with operational recovery success.

## Reporting contract

Every claim must be tied to an actual receipt, workflow, command ID, path, hash or measured status. Separate:

- observed fact;
- pending state;
- conditional plan;
- inference (label it explicitly);
- blocker.

For each destructive or resume action report:

- exact workflow/run ID;
- exact SSM command ID if applicable;
- exact commit/ref/CODE_ROOT;
- exact files affected;
- before/after hashes or byte counts;
- free-space measurement;
- process/PID/token state;
- receipt path and SHA256;
- whether source replay/model calls occurred.

If a command fails, preserve the failure and stop that branch. Do not retry the same blocked SSM command blindly. A genuine blocker is preferable to an invented completion.

## Suggested CCode turn discipline

At the start of every turn:

1. Read this brief and the newest handoff section.
2. State the active objective in one sentence.
3. List only the next three evidence checks.
4. Perform those checks.
5. Report what changed and what remains.
6. Do not broaden scope because an old handoff suggests extra work.

Before any mutation:

1. identify exact target paths and immutable identities;
2. retrieve current evidence;
3. check for conflicting live ownership;
4. execute the smallest existing committed operation;
5. retrieve the actual receipt;
6. verify postconditions;
7. update the checklist.

When uncertain, stop at the narrowest safe boundary and report the missing authority or evidence. Do not solve uncertainty by adding a new workflow, changing a policy, or inventing a fallback.

## Current checklist

- [x] Newest handoff and referenced audits read.
- [x] Corrected runtime and successful staging identified.
- [x] Full terminal checkpoint identity recorded.
- [x] Cleanup approval confirmed for exact five paths.
- [x] Cleanup failure and empty output retrieved.
- [x] SSM disk-full blocker confirmed.
- [x] Box state and access surfaces inspected.
- [x] No unauthorized deletion performed.
- [ ] Authorized command access restored.
- [ ] Exact five-file deletion receipt.
- [ ] Reclaimed-space measurement and target absence verified.
- [ ] PID59092 inactivity verified after capacity recovery.
- [ ] Projection range/coverage receipts retrieved.
- [ ] Same-root corrected resume.
- [ ] Projection publication, digest and calculations receipt.
- [ ] Downstream staging receipt.
- [ ] Principal/classroom/grading/correction/retention.
- [ ] Tuesday and learning outcomes.
