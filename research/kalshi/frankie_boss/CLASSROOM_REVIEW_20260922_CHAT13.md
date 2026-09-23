# Classroom review and /ship decision — 2026-09-22, chat 13

Reviewed remote tip: `3f60d47c4330f412bd94cdad23dbe6578bbf2b55` on `codex/trading-day-readiness-20260922`.
Implementation remains `a76ec2df801cff07638ed0b40bcd7d6a70f833c0`; this review changes documentation only.

## Decision: NO-GO

Classroom review is complete. Classroom repair and runtime verification are not complete.
Three independent /ship specialists reviewed correctness, security and test coverage. The main review reconciled their findings against the same pinned source. No new production run, model call, training update, deployment or ingestion work occurred.

Greg asked to review classroom next and subsequently deferred deployment discussion until classroom work is done. Keep the next work focused on classroom. Monday ingestion recovery remains COMPLETE; original ingest remains cancelled. Cycle 0 has not run under the new fixes.

## Findings

### C1 — Required: partial classroom caches can bind old interpretations to new teaching

Source: `deploy/aws/box/frankie_box_boss_session.py:1550-1553,1560-1577,2033-2036`; `deploy/aws/box/frankie_box_classroom.py:349-374`.

The work directory is selected by cycle, not request (:160). Verification updates the current request digest (:201-202). Existing component answers and summary are then reused solely by file existence. Saved prompt hashes are not compared with current prompts. With no final ledger, assembly transcribes the current teaching's facts and stamps its current teacher-message hash while keeping those cached narratives.

Concrete path: request A produces partial component/summary files; the same cycle is re-pinned to request B; the final ledger is absent. The resumed classroom combines A's interpretations with B's facts and publishes B's teacher and classroom binding hashes. Factual grading can pass because the factual fields are copied from B.

A complete old ledger preserves its old teacher hash and can be rejected downstream. That safeguard does not protect the partial-cache assembly path. This is provenance integrity failure, not evidence that an unauthenticated attacker can execute code.

Repair acceptance:
- Validate exact request, classroom binding, teacher-message, generated prompt, relevant parser/composition code and model/route identity before cache reuse.
- Bind summary to the component answers it summarizes; bind final receipt to all output witnesses.
- Preserve mismatching files with movement receipts; never silently overwrite or re-label their provenance.
- Revalidate completed artifacts before writing a response.
- Tests change request, teacher values, prompt/code and model identity after partial/full completion. Old narratives must not acquire new teaching hashes. Identical retries must make no new model calls.

### C2 — Required: the next earned curriculum mode cannot run on the box

Source: `research/kalshi/frankie_boss/dipole_classroom_integration.py:36-60,121-122`; `operations/run_actual_sunday_classroom.py:173-183`; `deploy/aws/box/frankie_box_classroom.py:144-150`.

The real curriculum advances from TEACH to GUIDED after two mastered and acknowledged TEACH completions. The box refuses all non-TEACH requests. Thus successful cycles 0 and 1 can make cycle 2 stop. This is a continuation blocker, not proof that cycle 0 itself will hit GUIDED.

Simply removing the guard is incorrect: `dipole_classroom.py:371-375,402` deliberately withholds fields and the relationship answer table outside TEACH, while the box prompts/assembly expect those taught answers. Keep the teacher key private.

Repair acceptance:
- Implement responses appropriate to each existing mode using its permitted causal evidence, preserving current grading and withholding boundaries.
- Exercise the actual host-to-box progression TEACH -> GUIDED -> SOCRATIC -> VERIFY and regression after degradation.
- Do not force every cycle to TEACH or expose the hidden key to make the tests pass. Any classroom contract change remains Greg's decision.

### C3 — Required: final-ledger existence is an unsafe completion marker

Source: `deploy/aws/box/frankie_box_boss_session.py:1583-1588,1550-1553,2033-2036,1870`.

The code writes ledgers first, Markdown next and the receipt last. A crash after ledgers but before receipt leaves a state that both resume paths treat as complete. Writing later requires the missing receipt and fails. The current partial-resume test deliberately removes the ledger, so it does not exercise this state.

Repair acceptance:
- Treat a verified final receipt plus its bound artifact witnesses as completion.
- Recover an interrupted publication from validated retained answers without unnecessary model calls, preserving old artifacts and movement receipts.
- Fault-injection tests cover every write boundary, missing/malformed receipt and mismatched ledger witness.

### C4 — Known required integration: historical positive priming still refuses on the classroom host

Source: `operations/run_actual_sunday_classroom.py:220-232`; base `operations/run_actual_sunday.py:945-959`.

The classroom host explicitly refuses configured historical priming. Its copied coordinator construction omits the capsule that the base host validates, loads, saves and supplies. This is the deliberate guard described in CHAT12, not a newly found bypass.

Repair acceptance:
- Share validated priming initialization through an explicit host seam and carry the same capsule through classroom coordinator, exact prepared critic request, runtime and training lineage.
- Preserve unsupported-route refusal, ordinary lesson chronology, positive-only public projection and truthful historical availability/calendar audit.
- Test primed classroom initialization, exact request acknowledgment, same-state restart and changed/missing lineage refusal before restoring weights.
- Never solve the gap by deleting the guard alone or by substituting the non-classroom host.
- Continue to label primed output `knowledge_primed_learning_replay`, not a blind forecast.

### C5 — Required verification repair: the classroom integration drift test is not green evidence

Source: `research/kalshi/frankie_boss/tests/test_dipole_classroom_integration.py:103-111`.

The test asserts AST equality between classroom and base run/main bodies modulo a narrow seam. The bodies now differ in historical-priming initialization/refusal and cycle-limit behavior. Inspection proves the equality assertion cannot hold; this review did not execute it and does not claim an observed failing CI run.

The test is absent from the reviewed codec, knowledge and trading-day check commands and the journal-stack fixed test list. Existing green checks therefore cannot certify this integration seam.

Replace brittle body-equivalence expectations with meaningful shared-initialization/behavior assertions as the seam is repaired, while retaining a regression that catches future host drift. Add the full classroom integration family to an isolated GitHub-hosted Linux test job with no production actions.

## Verification evidence and limits

Remote job logs inspected by the test reviewer:

| Commit / scope | Remote run | Observed result |
|---|---|---|
| a76ec2d, box codecs including pure/session classroom TEACH tests | [35802564083](https://github.com/DavisAI1974/Markets/actions/runs/35802564083), job 106995981238 | 228 passed |
| 3f60d47, trading-day checks | [35802840763](https://github.com/DavisAI1974/Markets/actions/runs/35802840763), job 106996867555 | 84 boundary/ingest +147 expanded passed |
| 6d48b50, critic knowledge/lineage and preservation | [35802300138](https://github.com/DavisAI1974/Markets/actions/runs/35802300138), job 106995161891 | 70 focused +80 preservation passed |

Suites overlap; counts are not additive unique coverage. The main review independently checked the codecs run's success and exact implementation SHA. These are existing runs, not newly executed tests. The 16 session-classroom and 7 pure-classroom tests cover TEACH assembly, same-request resume, parsing/refusals, factual validation and correction binding. They do not prove changed-request cache safety, crash-safe publication, full curriculum progression or primed classroom success.

No test execution, benchmark, dependency/CVE audit, repository-wide secret scan, IAM audit or runtime secret inspection was performed during this review. No production learning or comprehension is inferred from deterministic transcription checks.

## Specialist reports

### Code reviewer

Verdict REQUEST CHANGES / NO-GO. Required: C1 request-bound caches, C2 mode progression and C4 priming composition. Verification issue C5 must be resolved in the relevant suite. Strengths: the actual validators cover 19 components, every retained observation and 171 pairs; correction completion requires every resolution and rejects disagreements; host audit/teacher material is separated from public teaching.

### Security auditor

0 critical, 0 high, 1 medium finding: C1 provenance integrity. A request re-pin or retained-state mismatch can relabel previous narratives without a new model exchange; this is not a demonstrated unauthenticated compromise. Resolve before launch. Positive controls include host request/response/session witnesses, correction identity checks, exact knowledge acknowledgment, priming-lineage checkpoint admission and the existing unsupported-priming refusal. No output-to-shell/eval sink or hardcoded credential was identified in the scoped classroom paths. Dependency clearance is not claimed.

### Test engineer

Existing remote green evidence is limited to the suites above. Required additional coverage: C1 full/partial cache mutation, C3 interruption recovery, C2 production selector-to-box transitions, C4 real classroom-host priming and lineage, and C5 integration-family selection. Existing resume tests use the same request; the partial-resume fixture removes final ledgers, masking the receipt-publication gap. No new tests were run in this review.

## Next classroom work

1. Specify and implement request-bound, crash-safe classroom artifacts (C1+C3) with isolated RED/GREEN Linux CI.
2. Share the validated host initialization seam, integrate historical priming and repair/add behavioral integration coverage (C4+C5).
3. Implement the existing curriculum's supported response modes without weakening grader or teacher-key boundaries (C2).
4. Repeat the three /ship reviews against the final implementation and retain exact CI evidence.

The first slice can proceed without choosing Monday model_context_rows, cutoff rule or publish route. Those launch blanks remain explicit. Do not infer them from test fixtures.

## Hold / rollback posture

There is no classroom deployment to roll back from this review. Before any future GO, record an exact reviewed code/config/request identity and the established forward/rollback procedure. Wrong request/teacher/cache witnesses, lost artifacts, lineage mismatch or invalid correction completion must refuse further result publication/training. Preserve all evidence, keep the native host runner running, and use only the established receipted recovery route after the relevant gates. No recovery-time objective is claimed without a verified procedure.

The production decision remains NO-GO. Monday recovery, digest streaming, actual schedule/request/anchor bindings, brain/corpus receipts, full rerun step1b and all CHAT12 launch gates remain in force. No canary, source replay, ingestion restart, deletion, native-runner stop, Pod-bootstrap change or resource stop/termination. Deployment follow-up is deferred per Greg.

## Workflow sources

Read remotely from `addyosmani/agent-skills@0.6.8`: using-agent-skills, /ship command, shipping-and-launch, code-review-and-quality, specialist personas and their applicable skills, git-workflow-and-versioning, documentation-and-adrs, and definition-of-done. /ship's three specialist reviews ran independently in parallel. All repository access used GitHub APIs; no local filesystem or shell was used.
