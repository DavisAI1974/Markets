# Ship Decision: NO-GO

Reviewed implementation: e297553a7c96dd615879e5aa8e5c5a0118aeaff2.
Branch: codex/trading-day-readiness-20260922. Date: 2026-09-22.
Review base: 7d4a593c8546b21170cd3affeb3291c214c66595.

Applied remote [using-agent-skills](https://github.com/addyosmani/agent-skills/blob/0.6.8/skills/using-agent-skills/SKILL.md), [git workflow](https://github.com/addyosmani/agent-skills/blob/0.6.8/skills/git-workflow-and-versioning/SKILL.md) and [/ship](https://github.com/addyosmani/agent-skills/blob/0.6.8/.claude/commands/ship.md), including three parallel specialist reviews. All repository work used GitHub APIs; tests used GitHub hosted runners. No local filesystem/shell/checkout/cache/download. No deployment, Monday replay, canary, ingest restart or infrastructure stop.

## Blockers

- No successful Monday ingestion receipt or builder checkpoint. The preserved container is sealed but conformance was cancelled. SPEC_SEALED_COMPACT_RECOVERY_20260922.md is a reviewed design, not a recovery result.
- Explicit null launch fields remain: model_context_rows, cutoff_rule, cutoffs, ingestion_receipt, mapping, source_contract, publish_route. Do not infer Greg's modeling choices or manufacture receipt-derived fields.
- Full digest generation/proof is not bounded in memory yet. SPEC_DIGEST_STREAMING_20260922.md describes the remaining implementation and byte-identity/resource proofs. Existing disk spools and streaming layer JSON remain intact.
- The verified Friday 5.544 anchor must be bound into the authored Monday contract's forecast_session.prior_close and into the actual independently pinned exported request. The retained Sunday request still used 5.628. Updating an anchor evidence file alone is not that binding.
- Deployment, original rerun step 1b code/science re-pins, prefix regeneration under declared values, request transport re-pin, derivation measurements, production brain restoration/reading receipts, and original rerun sequence are outstanding.
- Existing section 4.2/4.4 projection code has not been proven on Monday data. Historical 1,900+ plane inputs remain unavailable.

## Changes approved in software review

- Brain history bases independently pinned; altered or unreceipted reuse refuses. Unchanged frozen entries reuse the same manifest. Symlinks, including unlisted members, refuse before copying.
- Brain retention required before every initial/correction/retry publication.
- Preparation uses feedback_available_through and rejects a source contract for a different source manifest.
- Prepared configuration path/hash/bytes and day/schedule/count witnesses survive pipeline persistence and resume. Receipt-derived configuration overrides stale host variables. Full completion matches the declared roster.
- Raw/fallback corpus paths include the pinned prior cycle-zero history. Cached prompt and corpus bytes are verified before reuse.
- Every reading part has request/corpus/range/note witnesses and durable outcomes. Unusable coverage refuses before merge/advancement. Legacy receipts without usable coverage cannot count as current.
- Refusing, incomplete, runaway or errored merge output retains inputs, including hash-free notes. Rereading preserves old notes, attempts, merge artifacts and damaged corpus files with planned-move and completion receipts.
- Reading header names the actual trading day.

## Verification

Exact implementation commit e297553a:
- [Readiness 35710468658](https://github.com/DavisAI1974/Markets/actions/runs/35710468658): 84 readiness/preparation tests, 135 expanded regressions; compileall passed.
- [Codecs 35710468808](https://github.com/DavisAI1974/Markets/actions/runs/35710468808): 216 passed.
- Suites overlap; do not add these as unique test counts.

Behavioral regressions were observed failing before fixes:
- Brain: 5 failures at 9b5c4d1, run35708759775.
- Preparation/handoff:16 failures at2f40b413, run35708961465.
- Corpus/reading/merge:7 failures at e84f4add, run35709903776.
- Corpus damage/repeated merge preservation:2 failures at f169d50d, run35710328025.

Tests include real tiny compact source preparation, prefix/seeding witness checks, preserved parent bytes, restarted configuration handoff, missing/foreign receipt refusal, repeated frozen history, raw corpus prior-zero inclusion, failed read retry, note/corpus tampering and receipted preservation.

No production workload, host speedup, Monday section traversal, native Windows PowerShell integration, dependency/CVE audit or successful Monday model result is claimed.

## Friday verification

[Run35708373395](https://github.com/DavisAI1974/Markets/actions/runs/35708373395), implementation e545e9bc: corrected decoder consumed the pinned source bytes across all frames, verified decoded SHA, and measured ONE zstd frame. Last prehalt trade for instrument111313 is 5.544, raw5544000000, ts_event1633121996642686187, ts_recv1633121996644001342, sequence70999223.

Exact nanosecond JSON is retained in blocks/FRIDAY_ANCHOR_VERIFICATION_20260922.json. blocks/FRIDAY_ANCHOR_20211001.json retains its original measurement/caveat history and points to verification. AWS receipts: bucket frankie-granite42-568968024170-us-east-1, prefix readiness/20260922/friday-anchor/35708373395/1/. No box, host or Pod operation was performed.

## Granite and missing output findings

records/chat6_scratchpad_20260921/critic.json records HTTP200, no transport error, 124 completion tokens, stop finish, and hypotheses=[]; available output allowance was38633 tokens. The answer violated its hypothesis contract and was rejected. This does not prove genuine absence of hypotheses or output truncation.

Retained four-part reading evidence shows part4's note exists (bytes527078–532065 in the reading plan), followed by runaway merge-0-0001, refusal in merge-1-0001, and explicit group loss in merge-2-final. The files directly prove merge failure. The older handoff's reader-origin claim needs raw per-call response evidence. Do not equate this reading-part failure with calculator section4.2/4.4 absence.

## Specialist reports

### Code reviewer
APPROVE for reviewed software fixes at e297553a; no remaining Critical/Required finding in that scope. Cache integrity, movement receipts, usable coverage, retry identity, prepared configuration and declared roster gates verified. Overall launch NO-GO for blockers above. PowerShell was inspected but not executed on Windows.

### Security auditor
No new Critical/High issue or established Medium blocker in7d4a593..e297553a. Prepared config cannot be overridden by stale host variables. Friday credentials are confined to source GET/receipt PUT; decoder is credential-free, sources pinned, receipt keys unique with conditional writes and encryption. Brain/corpus/session receipt checks refuse altered evidence. Dependency/CVE audit remains unverified. Historical Sunday full-request transport pin must be replaced with independently verified Monday export pin.

### Test engineer
Baseline historical CI independently checked (readiness35706533137:68+112; codec35706533219:202 at f60a89f4). New regressions cover previously missing preparation, brain/cache/reading preservation and handoff failures. Recovery proof requires exact packed checkpoint differential tests and zero adapter/source/write calls. Streaming proof requires byte-identical digest tests plus fresh-process resource measurements. These remain unimplemented; no successful ingest/recovery is inferred.

## Code and science pins

The existing launch_pins science-byte exceptions still match the Git blobs:
- c15_journal.py: dd323e2ac423988a0b78d066071f8e8b79a30951.
- prepared_context_cache.py:8062f60200305567b1a0ef3394b7b5e58c6a5d22.

This is a source audit, not step1b deployment. The reviewed BOSS commit, source/recovery implementation identity, actual request bytes, prefix seeds and all configuration hashes must be minted together for the final launch. Never substitute current code identity for original sealed-container provenance.

## Infrastructure, documentation and access

No DB migration or infrastructure change was performed. Existing runner, Pod bootstrap and processes were untouched. Git/AWS hold new records. Accessibility is not applicable to this backend/CLI change. The capability/build-plan addenda and recovery/streaming specs distinguish built, tested, deployed and run states.

## Rollback and recovery plan

Current status is predeployment, so there is no active rollout to roll back. Do not revert or reset historical evidence, force-push, delete artifacts, stop native host, or stop/terminate Pod/EC2.

Triggers: source/hash/identity mismatch, unusable reading coverage, missing retained history, failed section traversal, allocation failure, or incomplete provider result. Refuse the next stage and preserve exact receipts/attempts. If a future deployment must be changed, leave processes untouched, audit status read-only, select the last independently verified configuration in a fresh path, re-pin request/config/code together, and rerun gates before any result-bearing action. Any service interruption needs Greg's explicit instruction.

No recovery time objective is promised before conformance and digest measurements. The cancelled Monday ingest is never marked successful by rollback or retry.
