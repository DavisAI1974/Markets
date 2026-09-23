# /ship review — chat 12, 2026-09-22 ET

Reviewed implementation: a76ec2df801cff07638ed0b40bcd7d6a70f833c0 on codex/trading-day-readiness-20260922.
Three independent reviewers completed bounded code, security and test review. No unresolved blocker in the pushed calendar/knowledge-lineage/fourth-reading-part changes. Production launch remains NO-GO until the original launch gates below are satisfied.

## Delivered changes
- Separately validated Frankie knowledge audit, exact prepared-request binding, positive model-visible projection and reply acknowledgment by hash.
- Five independently pinned successful retained calculation methods; full prior history stays intact. Free-form self-labeled helpful prose does not enter the projection.
- Market calendar preserved independently from learning availability: date/session weekday, Sunday-evening Monday convention, NewYork/Chicago/London offsets, exact nanoseconds and ambiguous-hour folds, timezone-rule hashes, DST transition context. Holiday/official exchange trade date remains explicitly unverified.
- Priming refuses on unsupported critic routes. Coordinator ownership prevents downgrade; primed training configuration binds full lineage into checkpoint identities before weights restore. Classroom currently refuses configured historical priming pending explicit support.
- Fourth reading part: exact artifact replay reproduced the old guard's failure. Every nonblank input line must now survive a merge; otherwise the original notes remain verbatim with the rejected model output retained. Nonshrinking recursion stops without truncation.

## Verification
| Implementation | Remote run | Result |
|---|---|---|
| 7a0c6ef calendar RED | [35801584732](https://github.com/DavisAI1974/Markets/actions/runs/35801584732) |5 intended missing-calendar/context failures;48 passed|
| 8e4c8de calendar/lineage | [35801849021](https://github.com/DavisAI1974/Markets/actions/runs/35801849021) |66 focused +80 preservation passed|
| 8e4c8de readiness / cycle identity | [35801849007](https://github.com/DavisAI1974/Markets/actions/runs/35801849007), [35801849029](https://github.com/DavisAI1974/Markets/actions/runs/35801849029) |passed|
| 6d48b50 training lineage | [35802300138](https://github.com/DavisAI1974/Markets/actions/runs/35802300138) |70 focused +80 preservation passed|
| 6d48b50 retained fourth-part RED | [35802300091](https://github.com/DavisAI1974/Markets/actions/runs/35802300091) |new historical regression failed;216 existing checks passed|
| fe1363e expanded fourth-part RED | [35802411841](https://github.com/DavisAI1974/Markets/actions/runs/35802411841) |historical replay +4 quiet-loss failures; one no-progress fixture setup error, corrected;217 passed|
| a76ec2d final codecs | [35802564083](https://github.com/DavisAI1974/Markets/actions/runs/35802564083) |228 passed, job106995981238|
| a76ec2d final readiness | [35802564040](https://github.com/DavisAI1974/Markets/actions/runs/35802564040) |84 boundary/ingest +147 expanded passed, job106995980765; compileall passed|

Suites overlap; do not add counts as unique coverage. Knowledge suite's latest tested code is6d48b50; later implementation changes only the separate box reading/merge path and its tests. All execution used GitHub-hosted Linux. No local filesystem, production deployment, model call, source replay or ingest restart.

Historical regression independently checks SHA256 and bytes against retained docs-index.json and replays all three original failed outputs through the guard. It proves software preservation of the complete retained fourth note, not a new production reading receipt. No hypotheses were manufactured.

## Review limits and launch gates
- No CVE audit or Windows execution performed. Pinned Pod bootstrap unchanged. Native host not stopped.
- Monday ingestion recovery is independently COMPLETE; see MONDAY_RECOVERY_COMPLETE_20260922.md. Original ingest remains cancelled. No repeated replay is required.
- Actual recovered-source integration into day preparation still needs explicit schema/provenance support.
- Remaining digest streaming and original step1b code/science/config/request re-pins remain.
- Greg-dependent model_context_rows, cutoff rule/roster and publish route remain explicit blanks.
- Verified Friday5.544 must be bound into the actual request (retained request still5.628).
- Actual brain-history/corpus reading receipts, primed Granite acknowledgment, production fourth-part preservation and completed Monday cycle0 learning remain unproven.
- Classroom is Greg's next requested review. Its priming-capable integration is deliberately not claimed by this review.

More complete notes may survive conservative merge fallback; physical context admission can refuse them and must never silently truncate. Strict feedback chronology remains enabled; explicit historical capsule priming does not grant arbitrary future learned-state replay.
