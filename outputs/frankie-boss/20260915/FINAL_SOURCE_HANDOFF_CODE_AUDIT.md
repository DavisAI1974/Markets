# Final source handoff code audit

Status: CODE REVIEW ONLY — final data receipts and nineteen snapshot bytes are not ready and are not approved by this report.

Reviewed commit: eb510395a8a9e3f8502017de0dd3b0c7aaca04ae. The committed operations host has no working-tree diff from this commit. No DB, model, cloud or test operation was performed by this audit.

## Exact reviewed helper bytes

| File | SHA-256 |
|---|---|
| Current task work/build_remaining_sunday_prefixes.py | 8ff0ad82d40c14f2376546ab91e51ad58325652d46aea538d52f43021031e51c |
| Current task work/finish_source_handoff.py | 20b35fec4b65f3ee8f8dc2df73e01dc4209cd7a8a6f49735895d030250b3caea |
| Committed operations/run_actual_sunday.py physical checkout | 5c2f8e200a9eb6aea09b6c801f95da57ab6fff39469bebd6c121344198b7ac72 |
| E: host-work/seal_final_prelaunch_candidate.py | 41d7020d9a35103df881d67ca1d3b064bf23a1759ea30cc142a8ed4761eeeec9 |

Current task means C:/Users/A/Documents/Codex/2026-09-15/first-run-using-agent-skills-continue. Repository means C:/Users/A/Documents/Codex/2026-09-14/latest-addendum-host-controls-completed-launch-2/work/Markets-full-frankie; operations is research/kalshi/frankie_boss/operations. E: base is E:/Codex/Frankie-BOSS-20260915.

Also read the active build_completed_schedule_once.py, sunday_schedule.py, context_session.py, journal_prefix_snapshot.py, VerifiedJournalReader constructor and stacked codec cursor reconstruction. No loaded source/reader code was edited.

## Conclusions

1. **Original nineteen cutoffs are bound by the schedule producer.** The one-shot producer pins original cutoff bytes to 4b869d1f44a97a08196cd428ac10a34f36f3f55d70f22d6e50116cc7be9f80d9 and mapping-index bytes to f62c522dcc00a4d3e1caeac7a8e1e4e534a437ef53be200e991508236c027ca6. sunday_schedule requires exactly nineteen unique ordered group indices, finds their mapped ending cursors, validates F_LAST and both supplied availability clocks, and retains every step. The prefix helper consumes that pinned schedule without generating additional cutoffs. Its own structural check (nineteen, increasing, first cursor3261) is not an independent replacement for the producer's original-cutoff hash.

2. **Final closed identity is checked before prefix work.** The helper requires pinned ingestion/schedule/lineage JSON, successful complete progress, matching completion/checkpoint/source-scope identities, and no hot sidecars. It checks the final source physical hash before and after the batch. Each copier checks the independent parent tail and copies source bytes read-only. Host source_lineage additionally walks linked recovery receipts, physical closed-parent pins and child boundary anchors.

3. **Prefix00 is preserved.** The helper verifies its existing witness and receipt against schedule step0 and closed ancestry, then starts materialization at index1. It does not overwrite prefix00. All new snapshots/receipts/witnesses are exclusive creations; ambiguous partials or a lost seed sidecar remain preserved and fail closed.

4. **No extra semantic source traversal is introduced by seed generation.** ContextSeedCollector runs inside the existing _verify_pairs iterator for the copied prefix. It consumes APPLIED records after the original pair verifier has processed them. It reconstructs every source predecessor, including other entities, and selects the same top4096 (receive-time,cursor) entries as ContextSession. Missing entity rows, noncontiguous selected source cursors or omission of the terminal cursor produce an explicit nonderivable receipt and seed=None. It never guesses contiguity or a predecessor. Stacked codec reconstructs source order separately, preserving receive-time context order.

5. **Host admission binds the seed to the actual preparation.** encoding_options checks full19 manifest, quartet/batch pins, exact source tail, scope/entity/context size, cutoff/clocks, selection/runtime code hashes, snapshot receipt and current snapshot checkpoint. It recomputes cursor coverage/derivability and checks actual cached context cursors when available. Non-derivable rows retain explicit packet hashes through the codec path; they do not invent a compact seed.

6. **No circular manifest dependency was found.** The finalizer publishes source quartet pins before starting the prefix helper. The prefix helper needs no host prefix_manifest to create full19-prefix-witnesses.json. The sealer correctly refuses missing final manifest/pins.

## Explicit finalization actions still required

- finish_source_handoff.py publishes its own complete.json containing the final manifest pin but does **not** set host_runtime.prefix_manifest. Root must independently verify the completed receipt set and publish this pin into the authoritative host configuration before sealing/launch. This is an explicit integration step, not an automatic completion.
- Include --helper C:/Users/A/Documents/Codex/2026-09-15/first-run-using-agent-skills-continue/work/finish_source_handoff.py in the seal command; the current sealer default helper roster does not include that active finalizer. Include this audit report as another --helper if it is to be snapshotted.
- Use final-v2 bootstrap explicitly with --bootstrap E:/Codex/Frankie-BOSS-20260915/bootstrap-jobs-final-v2 and commit eb510395a8a9e3f8502017de0dd3b0c7aaca04ae. The sealer's historical default still names v1 and would correctly reject its stale source commit.
- Final receipt review must verify all nineteen authored cutoff bindings, producer cutoff/index hashes, final-source success/closure and complete seed/witness bindings. A code review cannot establish those pending data facts.
- Existing C: finalizer still writes small source-handoff evidence and authoritative configuration on C:. Do not relocate its active files mid-operation; retain enough space for those already-running writes. New audit report is written only to E:.

## Read-cost accounting and limits

The existing prefix helper performs **two full physical source SHA-256 reads** (before and after the batch), plus hashing of retained prefix00. Each necessary new prefix has its original-byte copy and one full verified-copy traversal, followed by snapshot physical hashing. Seed collection adds normalized hashing within that existing traversal, not another source reader pass. Host admission also rehashes closed ancestors and current prefix snapshots. These existing explicit physical checks must not be described as zero rereads or a single total disk pass. This audit did not execute any of them.

The E: sealer reads and snapshots small code/JSON artifacts only, refuses DB file extensions and oversized artifacts, checks final commit/package consistency, and produces candidate_for_audit with approved=false. It does not independently reproduce the source verification. Snapshot safety therefore relies on reviewed final receipt producers and root's final receipt review. Local token-template parity remains source-derived; live retained vLLM parity and actual inference/training outcomes remain unestablished.

No new code correctness blocker was found in the reviewed seed selection/host binding path. The explicit finalization actions above remain mandatory before the final candidate can be sealed and reviewed. This report is an intermediate immutable audit artifact on E:; the final small report belongs in Git under the user's output policy.