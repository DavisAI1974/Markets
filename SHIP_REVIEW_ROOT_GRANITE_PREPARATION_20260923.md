# Root/Granite preservation and preparation ship review — 2026-09-23

## Decision

GO for retaining the tested source changes on the working branch; NO-GO for live deployment or a new run. No host checkout was advanced, no preparation was run against Monday's real container, and no production request/model/cycle was dispatched.

Scope starts at 45b8e90d9d5958ad9138a0e3dc753951a4ba0f44 on codex/trading-day-readiness-20260922. Remote [using-agent-skills](https://github.com/addyosmani/agent-skills/blob/0.6.8/skills/using-agent-skills/SKILL.md) and [/ship](https://github.com/addyosmani/agent-skills/blob/0.6.8/.claude/commands/ship.md) were read at tag 0.6.8. All operations used remote GitHub APIs and isolated Linux Actions; no local filesystem, shell, C:/E: access, ingestion restart, source replay, canary, instance/Pod/native-runner stop, pinned Pod bootstrap mutation, evidence deletion or credential output.

## Implemented source

- Host code-bound state preservation: complete byte manifests; durable pre-move intent; exclusive helper lock; per-move receipts; recovery before identities; validation of every retained receipt before additional moves; UTF-8 reads; flushed pending siblings published without overwrite; normalized platform-aware path identity. Prior files, empty directories and interrupted temporary evidence remain preserved.
- Additive digest table primitive: SQLite-backed rows/plans/frequencies/dictionary/cells, exact existing table bytes, independent streamed inverse, one-pass context, exclusive fresh scratch output. It is not connected to Session.derive.
- Linux preparation adapter: exact clean reviewed checkout; explicit pinned complete Monday configuration; original recovered journal in place; new-root intent and receipts; generated artifacts only; regular no-follow archive reads with hashes of actual archived bytes; checksum-bound conditional S3 PUTs with completion receipt last. Separate prepare/publish, thin pinned launcher, no runtime controls. The archive retains Linux provenance and is not native Windows admission.

## Verification

| Component | Verified source/test revision | Remote result |
|---|---|---|
| Host preservation | c5338ac365e2d344c984e85c440d497c5325715b | [35816452957](https://github.com/DavisAI1974/Markets/actions/runs/35816452957): 97 contracts + 23 behavioral tests passed |
| Disk table codec | f5c2be88491ec88bdd782d861ecabd1537f3e389 | [35815986199](https://github.com/DavisAI1974/Markets/actions/runs/35815986199): 71 passed, including fresh-process memory measurements |
| Linux preparation/launcher/publication | bb4a7c530f89a665f9b6a530586cee30f006fa5c | [35816635892](https://github.com/DavisAI1974/Markets/actions/runs/35816635892): 36 passed using patched torch 2.10.0 |

The source changes coexist at bb4a7c530f89a665f9b6a530586cee30f006fa5c. Later rows do not alter earlier verified component source or tests. The subsequent handoff commit is documentation-only.

TDD failures were observed before implementation: host missing intent/path constraints [35814935620](https://github.com/DavisAI1974/Markets/actions/runs/35814935620); conflicting future receipts [35815767610](https://github.com/DavisAI1974/Markets/actions/runs/35815767610); path-alias retry [35816324744](https://github.com/DavisAI1974/Markets/actions/runs/35816324744); digest missing module [35815284416](https://github.com/DavisAI1974/Markets/actions/runs/35815284416); Linux missing adapter [35815712653](https://github.com/DavisAI1974/Markets/actions/runs/35815712653). The CR-byte comparison and expected-exception exit-status harness defects were corrected without weakening substantive assertions.

The disk codec's fresh processes used 4,000/40,000 rows and 2,000/20,000 distinct dictionary values. Peak RSS was 44,945,408 bytes in each; traced Python peaks 240,741/327,143 bytes; output 97,683/1,075,684 bytes. These are component regression measurements, not Monday workload capacity or whole-session proof.

Host behavior runs real PowerShell on temporary Linux fixture trees. Native Windows PowerShell semantics, physical power-loss durability and coordination with a separate running native writer are not proven. The helper lock serializes helper invocations only; verified inactivity remains a deployment prerequisite. Flushed atomic file publication does not claim a filesystem-wide transaction or directory-fsync power-loss guarantee.

Linux tests use a tiny synthetic recovered-journal fixture and fake only upload/network boundaries. The original 23,687,368,704-byte journal was not copied or replayed. Existing Classroom/readiness workflows may have run automatically under their pre-existing broad push paths; no Classroom change or manually requested retest was made.

## Parallel specialist reports and resolutions

Code reviewer: initial REQUEST CHANGES at 521e0c579711557fa8ed74de42c36f6f7f8151af because differently spelled equivalent run paths could bypass pending-intent discovery. A trailing-separator regression failed before repair. At c5338ac365e2d344c984e85c440d497c5325715b, reviewer approved normalized platform path identity across discovery and bindings; subsequent CI passed all 97 contracts and 23 behavioral checks. No other concrete component blocker found across correctness, readability, architecture, security and performance.

Security auditor: Critical 0, High 0, Medium 0, Low 0; scoped controls accepted. Targeted dependency review identified the new CI's torch 2.9.1 pin as advisory-affected by GHSA-63cw-57p8-fm3p; no malicious checkpoint reachability was established. Updated isolated preparation CI to 2.10.0 and retested. This was not an exhaustive resolved transitive dependency audit. [Official advisory](https://github.com/pytorch/pytorch/security/advisories/GHSA-63cw-57p8-fm3p).

Test engineer: broad component coverage supports source staging only after green checks. The expected-exception PowerShell harness needed explicit success exit status; content/no-overwrite assertions remain. Additional launcher success and HTTP failure checks followed. Native Windows, real transport/configuration and production Session integration remain unproven. Reviewer disclosed earlier Linux test authorship; the other two reviewers used fresh contexts. All three reports ran concurrently; tool thread limits required reusing the Linux agent for the test persona.

No UI changes; accessibility does not apply to these command-line components. No new runtime dependency was added by the table codec or adapter; deployment's existing Python environment still needs verification.

## Open launch gates

1. Owner-approved Monday model_context_rows and cutoff rule/roster remain absent. Complete mapping, source contract, actual configuration, source identity and Friday prior-close 5.544 binding must be coherent. No old 4096/19-cycle schedule is substituted.
2. Prepare the actual session from the original verified recovery on Linux; transfer only fresh outputs through the established S3 helper route. No ingestion restart/source replay.
3. Coherent native-host binding/relocation and original step 1b remain unresolved. The old whole-cycle preservation helper has no durable pre-move intent; principal-response preservation has a limited planned-name record, not the full resumable manifest protocol. Do not dispatch those helpers unchanged.
4. Native runner inactivity, native Windows behavior, live brain/history, part 4 and Granite priming acknowledgement remain unverified. Never stop an active runner to pass a gate.
5. DIGEST_V6 production write_digest integration remains incomplete: pinned incremental layer readers; exact persisted-row normalization; disk member unions and lifecycle/family ordering; whole-document orchestration; evidence-preserving publication; Session sentinels; whole-workload RSS/byte/inverse proof. project_sections, exact whole-input tokenization, reading and writing retain full-document allocations. Do not claim complete streaming or silently truncate.
6. Cycle 0/new run remains HELD until the owner's final workflow task is completed. Source staging does not release that hold.

## Rollback and failure handling

There is no live deployment to roll back. A source regression blocks dispatch and is corrected by a new reviewed forward commit. Do not restore the unsafe preservation helper as a recovery mechanism.

If a later preservation/preparation operation fails: keep Cycle 0 held; retain its complete intent, archive, partial outputs and pending files; inventory exact source/destination bytes without mutation; reconcile only under the matching reviewed intent/configuration. Never delete evidence, move it back automatically, stop a running service, or retry preparation into an existing root. Failed uploads may be republished to a fresh explicit prefix using new checksum-bound capabilities, without rerunning preparation.

Recovery completion is evidence-bound, before any Cycle 0 admission; no unmeasured wall-clock recovery guarantee is claimed. A live deployment plan still needs exact configuration/output pins and native binding verification before it can receive GO.

## Specialist reports

### Code reviewer — original verdict and follow-up

Reviewed the specs and changed tests first, then all source/workflow changes at 521e0c579711557fa8ed74de42c36f6f7f8151af against the original base. Verdict: REQUEST CHANGES.

Required: host helper line 276 skipped retained intents with case-sensitive raw path equality. Equivalent Windows case or trailing-separator spellings could evade reconciliation after identities moved; supplying OldCommit could then start a separate transaction. Normalize filesystem identity using platform-appropriate comparison throughout discovery and bindings, retaining historical evidence, and reproduce interrupted recovery under a changed spelling.

Correctness: this was the only concrete required finding. Readability: named helpers and explicit refusals make stages understandable. Architecture: additive codec and preparation delegation preserve module boundaries. Security: path/link refusal, exclusive creation, SQL binding, capability checks, redirect refusal and credential-safe errors reviewed without another required finding. Performance: SQLite avoids row-count-sized Python collections; archive/upload stream bytes; Session remains unbounded.

Positive observations: behavioral tests exercise actual interrupted moves, conflicting receipts, changed bytes, retained partial files and exclusive locking; archive tests verify bytes while reading even if a mutation is subsequently restored. Reviewer read source/tests/CI; did not execute tests or runtime actions.

Follow-up at c5338ac365e2d344c984e85c440d497c5325715b: finding closed in source; APPROVE requested fix pending CI. Normalized platform-aware equality now spans discovery and binding validation. Regression interrupts after both identities move and demands recovery under the original intent. Native Windows remains unverified and actual deployment remains NO-GO. Root subsequently verified green CI.

### Security auditor

Reviewed exact 521e0c579711557fa8ed74de42c36f6f7f8151af using the remotely pinned persona. Critical 0; High 0; Medium 0; Low 0. No concrete exploitable security defect established within stated trust boundaries. This supports inactive source eligibility only.

Informational finding: .github/workflows/frankie_linux_preparation_ci.yml line 26 introduced torch 2.9.1, affected by CVE-2026-24747 / GHSA-63cw-57p8-fm3p; fixed at 2.10.0 or later. The official advisory concerns malicious checkpoints passed to torch.load with weights_only=True. No attacker-controlled checkpoint reaching that API was established in this preparation flow or its tiny fixtures. Recommendation: upgrade to a compatible patched version and rerun. Root did so. Advisory review was targeted, not a complete transitive audit; absent published advisories on pytest, NumPy and Boto3 security pages do not prove vulnerability absence.

Positive observations: boundary-aware paths, reparse checks, complete manifests, exclusive lock and intent-linked receipt publication reduce ambiguous recovery. Archive names are explicit relative names; no-follow regular descriptors and read-time hashes reject linked or mismatching bytes. Publication requires HTTPS exact origin/key and signed conditional/checksum headers, refuses redirects, publishes receipt last and suppresses capability-bearing exceptions. SQLite values are bound parameters and dynamic identifiers internal literals. New workflows have read-only repository permissions, pinned action commits and no persisted checkout credentials.

Trust roots remain the staged checkout/interpreter, operator pins, private upload map and immutable source. The adapter's Git cleanliness check is not isolation against someone already able to replace its executable code or interpreter. The codec is not Session integration and Linux paths are not Windows bindings. No runtime/provider action, local access, edits or tests performed by this reviewer; Cycle 0 remains held.

### Test engineer

Reviewed exact 521e0c579711557fa8ed74de42c36f6f7f8151af. Disclosed prior authorship of Linux adapter/tests; independent pass across the change, but not fresh-author independence for that component. No edits/runtime/Classroom retest during review.

Host coverage: actual moves and preintent; replay after moved identities; complete manifests/empty directories; path/link refusal; conflicting receipts; changed and ambiguous bytes; real competing helper lock; pending metadata; Unicode; no-overwrite publication. The reviewed revision had 97 contract passes and 21 behavior passes plus one expected-exception harness exit failure. Explicit success exit preserves content/retention assertions; reviewed revision could not be called fully green before correction.

Digest coverage: existing-fixture byte equality; inverse corruption/truncation; one-pass context; dictionary cardinality/order; constants/tuples/floats; context fallback; scratch/write failures; wrapper sentinels; fresh-process 4k/40k resource growth. Reported 71-pass evidence establishes the table component only.

Linux coverage: independently verified run 35816112913, job 107037867437, 31 passed. Tiny recovered source exercises actual preparation, timestamp integers, unchanged source, exact archive files and source-container exclusion. Negative coverage includes launch omissions, pins/credentials, copied source, output paths, evidence retention, checkout refusal, traversal/links/ABA archive mutation, publication ordering/checksum and checked-byte map parsing.

Recommendations: (1) correct host harness and rerun before green claim; (2) native Windows/installed PowerShell isolated validation before native deployment, especially sharing/reparse/case/Unicode/atomic publication; (3) successful launcher arguments/environment, receipt-PUT failure after archive success, real 412 processing and actual redirect handling before live Linux dispatch; (4) full production Session differential/inverse and process-memory tests before streaming-completion claim. Root resolved (1), the path-alias issue from code review, and (3); final counts above. (2) and (4) remain launch gates.

Gate recommendation: source staging after green corrections; no actual deployment admission. Actual Monday rows/cutoffs, native binding/step 1b, remaining preservation helpers, production digest integration and the final owner workflow hold remain unresolved.
