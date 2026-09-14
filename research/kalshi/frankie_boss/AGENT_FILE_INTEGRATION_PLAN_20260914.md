# BOSS and committed-file Frankie integration audit

Read-only source audit, 2026-09-14. No provider, replay, agent launch, source edits, or output calculations were performed.

## Inspected versions

- BOSS: work/Markets-initial-build, f0127bc46231958828b442e93e7c0a44ef39c04c.
- Repaired agent: work/Markets-agent-audit, 996d121c (includes 1d43c158 chronology repair and 06118451 seed assertions).
- The BOSS checkout has no research/kalshi/frankie_raw_mbo_benchmark package. Do not assume imports from the other checkout prove a committed integrated build. Integrate the approved commits into one declared checkout or retain an explicit artifact-only boundary with both commit identities.

## Existing executable seams

BOSS research/kalshi/frankie_boss/frankie_controller.py: FrankieForecastController.refresh invokes NativeForecastRefresh, reconstructs exact context, obtains the separately bound Granite critic receipt, and records RESULT through ControllerJournal. Lines 258-273 retain per-target publication_hash, artifact_digest, record_json and record_digest plus critic_hash and native_checkpoint. ControllerJournal.state(request_id), checkpoint() and its verified reopen contract are the authoritative source, not an arbitrary caller dictionary. frankie_forecast_consumer.consume_forecast is a verified category-free data adapter, not an agent session. BOSS records must not be attributed to the human-style Frankie principal.

Agent research/kalshi/frankie_raw_mbo_benchmark/fetch_frankie_ledgers.py obtains the exact three plaintext ledgers and result metadata under a verified delivery manifest. emit_frankie_spawn.emit verifies the current ledger/result bytes and pinned knowledge bundle before writing the prompt. Native causal traversal accounts all members and sidecars and requires terminal drain_withheld. native_staging.read_back (line 725 onward) validates agent-authored findings, output bundle, delivery/stream/knowledge receipts and serialized prompt/bundle input; it attaches findings via the existing runner admission seam and creates the handoff. calculation_result.json is a runner identity/verification artifact, never substitute evidence for the three ledgers. Runner lifecycle conclusions are not principal calculations. Historical findings must retain their historical trust and provenance, not receive new current-admission claims.

## Smallest additive integration slice

Implement a committed-file BOSS attachment and combined read-back receipt, independent of all computation. Suggested new files only initially:

1. research/kalshi/frankie_boss/agent_file_handoff.py plus SPEC-agent-file-handoff.md and tests/test_agent_file_handoff.py. Export an already committed controller RESULT using independently supplied controller/native journal checkpoints and explicit request ID. Read and verify the retained request/config/source/cutoff/cursor context, original record bytes, native artifacts and critic evidence. Use the existing canonical pack/hash rules without lossy JSON conversion. Write a new directory exclusively; preserve exact payload files and deterministic manifest with relative paths, lengths, SHA256, controller/native checkpoints, both software commit identities, source prefix/cursor, arm and target identities. No implicit refresh, inference, retry, transport or agent invocation. Idle/incomplete exports remain explicitly labeled and cannot pass as complete.
2. research/kalshi/frankie_raw_mbo_benchmark/native_boss_attachment.py plus tests. Validate the physical export and independently expected manifest/checkpoints/commits against a caller-supplied explicit source identity crosswalk. Bind agent run/delivery-manifest and result identity to BOSS source cursor/cutoff/arm; source-manifest hash and BOSS source-prefix hash are different objects and must not be equated. Preserve every BOSS byte in a separate attachment with producer attribution. Default existing emitter unchanged. A later narrow emitter option can name this verified attachment and its attribution; adding it to the knowledge corpus requires the existing declared manifest/profile refresh and new knowledge identities, never bypassing corpus verification.
3. A combined committed read-back record links the existing successfully validated native_staging execution/outputs/knowledge/stream/delivery receipts to the accepted attachment manifest, including the exact principal input identity. It does not translate BOSS records into principal findings or write memory. No launcher, API or wrapper computes Frankie output. If only post-agent comparison is desired, keep the attachment out of the principal prompt and join after admission; select this explicitly in the contract because pre-agent exposure changes the agent's evidence.

No generic MBO-to-bar mapping is warranted by these files. Exact raw observation identity reconciliation must use actual source manifests/receipts. If that crosswalk cannot be independently reconstructed, refuse integration rather than inventing matches from timestamps, filenames or equal record counts.

## Synthetic acceptance cases and parallel ownership

Exporter tests can run with retained synthetic controller journals and tiny native fixtures, fake critic transport already committed by existing tests, and zero new model calls. Prove byte identity, all target roster members retained, immutable output path, wrong checkpoint/commit/request refusal, tampered record/critic rejection, incomplete status preservation and deterministic replay.

Agent attachment validator tests can independently use a frozen synthetic exporter fixture and real three-ledger delivery/knowledge witnesses. Prove wrong source/day/arm/cursor refusal, every file byte and manifest member checked, traversal/input attribution unchanged, and principal output admission still requires complete+drain and actual receipts. Combined receipt tests should fail if any retained artifact changes, and prove no principal invocation or findings generation occurs. Exporter and receiver implementations can proceed in parallel once the shared manifest/spec is frozen; reserve emitter/read_back integration to one owner. Existing fetch/knowledge/stream gates are reused, not duplicated or weakened.

## Memory A chronology provenance

Actual retained artifacts:

- principal_runs/33605852433/frankie_principal_findings.json: run frankie-a-clean-rt-33605852433-1, source_day 20211003, arm A_CLEAN, 44 historical findings. It remains historical day-one seed, not a newly executed A_MEMORY day.
- principal_runs/frankie-a-memory-rt-33746436209-1/frankie_principal_findings.json: same named run, source_day 20211003, arm A_MEMORY, 18 findings F-45 through F-62. Its retained sunday_spawn_prompt.md identifies that run and the October 3 raw source; no October 1 principal artifact exists in the inspected principal_runs directory.
- Current A_MEMORY_SEED_20260902.json records October 1 MISSING, October 3 PRESENT_WITH_FINDINGS with exactly those 18 new IDs, and October 4/5 MISSING.

build_a_memory_seed.py lines 168-202 discovers actual artifacts and retains source-day/run identity. Lines 273-365 construct explicit day status and admitted findings. Current commit 1d43c158 removed the earlier requirement that prior roster days must have artifacts; test_a_memory_findings_loop.py:125 proves a later real day is admitted without inventing an earlier run. Commit 06118451 preserves verified seed assertions as memory grows. This mismatch is resolved in the inspected HEAD; do not delete the real October 3 artifact, relabel it October 1, invent an empty earlier run, or claim historical artifacts satisfy the newly strengthened stream byte witness gates. Keep the current missing-day representation and original attribution.

## Remaining decisions requiring exact contract, not fabricated outputs

The current evidence establishes no independently verified BOSS-to-delivery source identity crosswalk and no current integrated principal-input schema for BOSS attachments. Define these before enabling agent exposure. Whether BOSS output is pre-agent attributed input or post-agent comparison must remain an explicit mode; a silent choice changes the experiment. Live readiness still depends on actual deployment/model access and agent execution evidence outside this software-only audit.
