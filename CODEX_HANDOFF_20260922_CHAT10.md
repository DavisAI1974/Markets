# Frankie Monday readiness handoff — 2026-09-22, chat 10

This handoff supersedes the running-ingest state in CODEX_HANDOFF_20260922.md. Read that full brief and the build plan/capability map for original requirements. GitHub is authoritative; local copies are stale.

## Non-negotiable operating rules
- DO NOT USE C: Greg says it can crash the computer. Do not use E either. No local checkout, shell, downloads, caches or filesystem skill reads. This session worked through GitHub connector APIs and GitHub-hosted CPU checks only. No local shell/CUA used during this continuation.
- Skills already read earlier: using-agent-skills, git-workflow-and-versioning and relevant review/spec/TDD/shipping skills. Greg explicitly requested the git skill and /ship. No /ship command was available; /ship review remains unfinished. Do not claim a skill was reread on C.
- Nothing deleted; every move receipted. No Pod/EC2 stop or termination without Greg. Never stop the native host runner. No keys printed. No BOSS output limits. Pinned Pod bootstrap untouched. No outside production engine. Records in Git/AWS.
- NO CANARY. NO INGEST RESTART. Greg explicitly stopped this run; fix and review first. Do not silently restart or discard its sealed container.
- The branch originally specified by Greg is stale relative to this work. Continue from the branch and commit below, not trunk. Every commit needs attribution; no model identifiers in new pushed content.

## Repository and branch
Repository: DavisAI1974/Markets.
Branch: codex/trading-day-readiness-20260922.
Latest implementation at handoff drafting: f60a89f4d9c4980a964de84e0c94cc362c32df3c.
Base was e458e5b7c7471f710c73a92969e7da58ee3f2b95 on claude/cycle-0-monday-rerun-hk2q2z.
Always read the current remote branch tip. Changes are pushed, NOT deployed to box/host/Pod. The box checkout remains the ingest-dispatched 2ae4da204b0d2a12f605e765f281b505ff51491a.

## Stop and observed ingestion state
Greg: “I knew it. Stop it and we'll fix otherwise it'll be 4 more hrs.”
Stopped only the original SSM ingest command eea87d2f-a1d7-428e-ab57-3fdab2980eb6 on i-035994afa8bdf66a5, us-east-1.
- Original GitHub run 35694087514 started 06:16:16Z; SSM command started 06:16:40Z.
- Targeted cancellation job 35704875052: AWS Cancelled confirmed 08:27:39Z. No EC2 stop, native runner stop, deletion or restart.
- Read-only audit 35705637431 at 08:35:49Z: 32 logical CPUs; no ingest PIDs and no multiprocessing helpers remaining.
- The full declared 2,032,203 INPUT records had been processed by ~07:39:50Z, about 83 minutes. Conformance was 62.7598% through at cancellation: 2,550,815 / 4,064,406 journal entries, workers 1–31, reported 446.71 source records/s.
- This is observed progress, NOT a successful ingestion receipt. No completion.json or ingestion-receipt.json exists.
- Retained sealed journal: /opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite
- Seal: C15_EXACT_ORDER_BLOCK_GZIP_V1; 4,064,406 entries; head 534f442aa0008032064c540f1c472433cb665a97bfec94399f8137ca103f207c.
- Actual packing: 37,934 boxes; 70–256 rows/box; compressed body bytes 23,628,634,795; file bytes 23,687,368,704; largest compressed body 768,823 bytes.
- So this WAS compact box packing, not one row per box. The causal parent still processes source records in order.
- First audit 35705293795 refused before status because MARKETS_SHA was absent; workflow tee masked the failure. Fixed via 503fda05; successful audit is 35705637431. One successful ACTION=status performed. Do not quote the earlier audit as evidence.
- Evidence retained in these GitHub jobs and SSM. Raw logs include all returned SSM content, but SSM itself truncated long ingest output; the separate progress-file audit supplied the final progress facts.

## Fixes committed and validation
1. a5765696 spec/tests; c3d94f2 hosted CPU check workflow; 0fb7b21 initial modules 2–4 implementation; e721598 host/contract integration; d5279ef disk-backed box row collections.
2. Trading-day schedule V1 and explicit-null MONDAY_20211004_LAUNCH.json. New schedule validator, completed compact schedule view, block scope selection, compact-only prefix snapshots, explicit prepare_trading_day.py operation, dynamic source contract and schedule gates, dynamic host cycle bounds, request carries exact pinned authored contract bytes for box verification.
3. Raw/both ingest CLI receipt regression fixed (raw journals cannot query compact blocks).
4. Box derivation now uses type-preserving RowSpool files and streaming JSON output, lazy driver stamping, constant-memory span calculation. Existing five legacy layer byte hashes and expanded cycle-zero regressions passed. Full digest path still materializes collections: remaining work, not a full 2-million-row readiness claim.
5. Verification fix at 628e3ecd64d2d7ef5e219e5f19ce8f0f68ba486f: ingestion had wrongly used full-evidence FrankieCompactReader during conformance, transferring complete book observations from workers. Switch to existing CompactConformanceReader, which verifies every canonical body/hash before sending only conformance fields. Shared worker affinity, ordering, seam validation and progress; full-evidence reader retained for model consumers.
   GitHub check 35705840996 PASSED. Tests prove raw/compact completion and state identity, and refusal when a projected-away observation body is tampered. No speedup measured on box yet.
6. Brain fix f60a89f4: preserve replaced entries in history with move receipts; capture an immutable request-specific base of all retained knowledge including prior cycle 00; verify included file hashes and load documents into the reading corpus; retain session Markdown docs; publish history/bases with response; fail on missing/changed included docs or brain write failure. GitHub readiness checks 35706533137 and box-codec checks 35706533219 PASSED on f60a89f4.
7. GitHub-hosted tests only, no model calls. .github/workflows/frankie_trading_day_checks.yml now triggers only relevant changed paths. Separate existing box-codec CI passed on d5279ef. Full /ship and launch pin review remain.
8. One legacy pipeline test expected explicit None cycle_limit to fail; new None means schedule-default. Test adjusted alongside dynamic bounds. No production count guessed.

## Brain findings and Greg’s requirement
Greg: “Each run should [be] adding onto older knowledge base, not replacing.” “We want the docs to be hitting Frankie's brain and used.”
The audit found /opt/frankie-box/brain/cycle-00/MANIFEST.json, SHA256 38291a4ae9ad2c52b1e4cd448e7814f43bf12f08abcb9243b08f649b667c737c.
Its included derivation digest, accounting/ledgers, analysis and derive receipt all exist and hash-match. derived-files.md exists/hash-matches but include=false.
Old loader only loaded lower cycle numbers: those prior Sunday cycle-00 documents were NOT automatically read by another cycle-00 run. Old writer reused cycle-00 directory. Fix above is source-only until reviewed/deployed. Verify actual reading receipts later, not merely file existence. Do not claim the new path has run on Frankie.

## Friday anchor finding
Last retained request: frankie-boss-sunday-two-cycle-20260919-cycle-00, request SHA256 1b777cf28c34415c4387119b1a42aed7dbc1f5e7b1799fdc0ed2cabd755624be; work/verify.json matches it.
It used prior_close = 5.628 with Sunday timestamps, opening=5.634. It did NOT bind the actual Friday close.
Separate receipt /opt/frankie-box/receipts/friday-anchor-1790043966.json (SHA256 7dbfe892cf9041f877ed5224b5ab624afcbc21ce53c9c63f2732b61b23df38ee) records Friday price 5.544, ts_recv=1633121996644001342.
Committed blocks/FRIDAY_ANCHOR_20211001.json still explicitly has a multi-zstd-frame/checked-bytes caveat. Corrected decoder exists, but no new confirming receipt was found. Verify before binding; don't silently turn the old caveated anchor into a proven new contract.

## Immediate next work
1. Latest brain-change readiness and codec CI passed on f60a89f4. Review changes and unresolved integration risks. Remote GitHub API only.
2. Finish conformance performance investigation. Strong candidate fixed; box speed unmeasured. Preserve existing 23.69 GB sealed container. Determine whether a verified conformance-only completion/recovery can reuse it safely. Current tool writes builder checkpoint only AFTER conformance; cancellation lost in-memory state. Do not fabricate checkpoint/receipt or weaken checks. Prefer preserving pre-conformance checkpoint in future implementation. No restart/canary without new instruction.
3. Complete brain accumulation integration and verify doc inclusion/reading receipts for next run. Source fix not deployed.
4. Verify corrected Friday anchor and attach it to actual request/contract, not just a side file.
5. Investigate Granite zero hypotheses/output and the unnamed one of four root sections with zero output. Greg asked distinguish harness failure vs genuine absent output; do not invent outputs or remove gates. Old screenshots are historical, not proof current modules are missing.
6. Finish host/pipeline adoption of prepared configuration, full compact-prefix tests, launch science-byte/code re-pins, and per-layer digest streaming. New PowerShell preparation wrapper exists; explicit prepared configuration path/hash supported in day_cycles.ps1; ensure pipeline passes it end to end.
7. Greg/receipt-dependent fields remain explicit null: row count/context window, cutoff rule and roster, mapping witness, authored source contract, ingestion receipt and publish route. Don't fill from 19/57,027/Sunday examples. Monday is Sunday 18:00 ET to Monday 17:00 ET (22:00Z to21:00Z), declared 2,032,203 records across whole20211003 plus partial20211004.
8. RunPod setup read-only inspection requested but deferred (“stick with what you were doing first”). No Pod calls made. Use available remote skill resources; don't read C skill files. Preserve pinned bootstrap.
9. Full /ship review and original rerun order including step1b. No full rerun until gates genuinely satisfied.

Greg is urgently trying to reach cycle0, says cloud time costs money. Preserve the existing root calculation optimizations; avoid repeated full replays. 1,900+ plane inputs are unavailable for this five-year-old historical run; don't fabricate them. Possible additions only after Frankie’s actual findings.

## Connector operation notes
Use functions + tools.mcp__codex_apps__github_*; discover schemas through ALL_TOOLS.
Read files via github_fetch_file at exact SHA. Read runs/jobs/logs through dedicated tools. Generic github_fetch supports GET GitHub API; no Actions cancel/dispatch tool was callable.
Remote edits: github_create_tree(base_tree_sha, changed blobs) -> github_create_commit(parent_sha, attribution) -> github_update_ref. Sequential mutations; never force over another newer tip.
The stop/read-only audit workflows were committed specifically to execute authorized actions via existing GitHub AWS secrets without local drives. Do not modify their triggering files casually: that can trigger another audit/cancellation check. Stop script only cancels the exact original command; never stops EC2 or runner.
