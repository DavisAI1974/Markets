# Spec: the Dipole classroom exchange in the Frankie box session (2026-09-21, chat 6, Greg: "Do option 1. Let's do it before anything else run")

## Status (18:xxZ 09-21)

BUILT, tests green, nothing run: all seven modules of the capability map landed on this branch (commits 14e3ed60,
15e58ec5, 71aef89b, 6b4a68d9, 1ce0e1d4, the host supersede, the runbook). The restart runbook (a-i) is in
`CLAUDE_HANDOFF_20260920.md` 18:xxZ; every host step waits on Greg's go.

## Objective

Cycle 0's response was recorded on the native host (run 35633661236) and the host runner stopped on it:
`validate_teachback` raised `structured Dipole classroom teach-back required` because the box session never produced
the classroom ledgers (handoff 17:5xZ). The box session must produce, in the same BOSS session that wrote the
analysis, the complete two-turn classroom exchange the host's classroom adapter grades:

- turn 1, inside `response.json`: `dipole_teachback`, `dipole_observation_review`, `dipole_relationship_scan`,
  `dipole_novel_findings`;
- turn 2, a separate response to the host's correction request: `dipole_acknowledgement` with
  `correction_resolutions`, from the same session id and model identity.

Success = the host recorder pre-grades turn 1 with the real grader and records it; the runner's classroom grade passes;
the correction turn is recorded; `finish()` produces a teacher-complete completion for cycle 0; cycle 1 launches on the
same code without a classroom-shaped stop. Nothing runs (box, Pod, endpoint, host) until this is built and Greg says go.

## The contract, read from the code (what the host grades; do not restate it elsewhere)

The cycle's classroom mode is TEACH (binding: mode TEACH, learning_measurement INSTRUCTIONAL_COMPREHENSION). In TEACH
mode the model-visible pre-message (`attachment.dipole_classroom.pre_message`, in the session request the box holds)
carries for each of the 19 components its `observations` (every retained cursor: `{cursor, ts_recv_ns, target_hash,
state, value, raw_reason}`), `state_counts`, `terminal_state`, `terminal_value`, `first_to_last_present_direction`,
`nonpresent_explanations`, `previous_cycle`, `change_from_previous`, and the full 171-pair `relationship_review`
(`{left, right, direction_relation, correlation, interpretation_limit}`). `audit_teacher_complete` asserts those
observations equal the teacher key's. So every factual field the grader checks is stated to Frankie before he answers;
the classroom measures comprehension of instruction, and Frankie's own contribution is the interpretation.

Turn 1 ledgers (grader: `dipole_classroom_session.grade_initial_response` via `dipole_classroom_final_review`):
- `dipole_teachback`: schema `DIPOLE_CLASSROOM_TEACHBACK_V1`, `teacher_message_hash` = pre-message's,
  `future_outcome_claimed` false, `relationship_pairs_considered` 171, `cycle_summary`, `correlation_review` (nonempty
  text), `unresolved_questions` (list of nonempty strings), `components`: 19 in governed order, each exactly
  `{name, state_counts{PRESENT,MISSING,INVALID,ABLATED ints}, terminal_state, direction, explanation, why,
  market_behavior, fifo_full_book_order_link, evidence, uncertainty, relationships[{with, relation, explanation}]}`.
  Graded: state_counts, terminal_state, direction against the key; each relationship's `relation` against the pair's
  `direction_relation` unless it is HYPOTHESIS (retained, but the cross-check demands the ledger mark a
  `developing_structure` for that pair, else `representation:` correction).
- `dipole_observation_review`: exactly 19 `{name, observations}` in order; every retained cursor as
  `{cursor, state, value, explanation}`; value finite number when PRESENT, null otherwise; explanation nonempty.
  Graded per cursor (state and value within 1e-6), missing/extra cursors are corrections.
- `dipole_relationship_scan`: exactly 171 canonical pairs in order, each exactly
  `{left, right, direction_relation (SAME_DIRECTION|OPPOSITE_DIRECTION|UNRESOLVED), correlation_interpretation (text),
  developing_structure (null or text)}`; direction graded against the key.
- `dipole_novel_findings`: a list (empty allowed); each `{schema FRANKIE_DIPOLE_NOVEL_FINDING_V1, finding_id, premise,
  why_novel, evidence_refs[...], future_outcome_claimed false}`; refs of kind DIPOLE_OBSERVATION
  `{component, cursor, claimed_state, claimed_value, reasoning}`, DIPOLE_RELATIONSHIP `{left, right, claimed_relation,
  reasoning}`, OTHER_CAUSAL_EVIDENCE `{evidence_pointer, description, reasoning}`. Investigated, never scored.

Turn 2 (the host writes `principal/classroom-correction-request.json`: schema
`FRANKIE_DIPOLE_CLASSROOM_CORRECTION_REQUEST_V1`, `original_request_sha256`, `session_id`,
`model_identity_as_reported_by_session`, `post_grade_hash`, `correction_ids`, `data_review_items`, `root_cause_groups`,
`novelty_investigation`, `instruction`, `request_sha256`; the runner then exits `actual_frankie_session_pending`
through PrincipalPending and must be re-dispatched once the response is recorded):
- response: `{session_id (same), model_identity_as_reported_by_session (same), request_sha256 = the request's own
  request_sha256 field, dipole_acknowledgement}`; the acknowledgement: `{schema DIPOLE_CLASSROOM_CORRECTION_ACK_V1,
  post_grade_hash, session_id, acknowledged true, what_i_will_change (text), resolved_correction_ids (= all
  correction_ids), remaining_disagreements (must be [] for teacher completion), correction_resolutions
  [{correction_id, corrected_understanding}] one per id in order, [] when none}`.
- host attestation for the turn: the same `FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1` shape with
  `request_sha256 = adapter digest of the WHOLE correction request object` (not its inner field),
  `response_sha256`, `session_id`, model identity, `host_record{path, bytes, sha256}` pinning a host record file whose
  keys match and which carries `host_authority`. The record file must be a different file from cycle 0's initial
  record (that one is retained immutable): `host-correction-record.json` beside it.

Sizes: the observation review is one object per retained cursor per component (19 x N; N is the cycle's context
cursor count, about 3,262 at the packet's T_CTX, measured on the box at run time). It cannot come out of one model
turn (38,633 output tokens on this packet), and it is a transcription of the TEACH pre-message anyway.

## Design (ASSUMPTIONS stated; Greg corrects them or they stand)

1. Facts are transcribed by the session code from the pre-message; interpretation is the BOSS's. The code fills
   state_counts, terminal_state, direction, every observation's cursor/state/value, every pair's direction_relation,
   and each component's `relationships[].relation` = the pair's direction_relation from the review (never
   HYPOTHESIS, so the cross-check is consistent by construction). The BOSS writes, per component, the six narrative
   fields, one short explanation per observation STATE (PRESENT/MISSING/INVALID/ABLATED, only the states that occur),
   and for each pair whose left is that component `correlation_interpretation` and `developing_structure` (null or an
   explicitly labeled hypothesis). Each observation's explanation = the BOSS's per-state sentence for that component
   + (non-PRESENT) `; teacher reason: <raw_reason>`. This composition is DECLARED in the host session record and the
   attestation (`classroom_composition`) and in the receipt; nothing is invented on Frankie's behalf: every sentence
   in the ledgers is either the pre-message's fact or the BOSS's text.
2. Nineteen component calls run on the reading lane (the serverless endpoint when configured, `_fan_out`), each
   prompt = the research objective + direction definition + the component's teaching (role, behavior basis, unit,
   what happened, nonpresent legend, previous-cycle change) + the compact observation series (one line per cursor:
   `cursor state value` or `cursor state - reason-id`) + that component's pairs with their direction and correlation
   + a strict JSON task. Then one summary call on the BOSS with the 19 component narratives and the fact tables:
   `cycle_summary`, `correlation_review`, `unresolved_questions`, `novel_findings`. Every call is durable (job
   outcome on disk, resumed on restart, `tolerant_json` parse; a refusal/empty/incomplete output is retried once as
   the reader guard does, then the stage refuses with a receipt: the classroom is never filed half-made).
3. Validation on the box before writing the response: the repo's own validators run against the pre-message
   (`validate_teachback`, the claim checkers, `validate_novel_findings`, the relationship cross-check) plus a
   transcription check against the pre-message facts. Novel findings that fail validation are kept in the docs
   bundle with the reason and not filed (dropping is not inventing; filing an invalid one would stop the runner).
4. Turn 2 on the box: a `correction` stage reads `request/classroom-correction-request.json` (exported by the host,
   fetched by key), builds one BOSS prompt (its own teach-back narratives + the request's data_review_items,
   root_cause_groups, novelty_investigation, instruction), parses `{what_i_will_change, remaining_disagreements,
   correction_resolutions}`, assembles the acknowledgement (schema, post_grade_hash, session_id, acknowledged true,
   resolved ids = all ids), validates with `validate_acknowledgement` + `validate_correction_resolutions` against a
   stub grade `{post_grade_hash, correction_ids}`, and writes `out/correction-response.json`,
   `out/host-correction-record.json`, `out/host-correction-attestation.json`. A non-empty
   `remaining_disagreements` is kept verbatim (Frankie's word) and noted: it blocks teacher completion by contract.
5. Host side: the recorder gains `--turn initial|correction`. Initial pre-grades the classroom with
   `grade_initial_response(classroom_package, response)` in the candidate directory and refuses a response the
   runner would stop on (printing mastered and the correction ids). Correction validates the response against the
   retained correction request and writes `classroom-correction-response.json` under the host lock, immutable, the
   host record staged at the attested path. Export, delivery (push script + fetch workflow) and record workflows gain
   a `turn` input. A new supersede workflow moves cycle 0's recorded response aside (never deletes) so the corrected
   response answers the SAME request (same request_sha256; no re-render).
6. Restart order (each a receipted host action on Greg's go): advance the host tools checkout to this branch's
   commit (imports at module top; carries the json_form root fix and the recorder) -> supersede code-bound state ->
   supersede the recorded response -> box: classroom stage + rewrite + push (turn initial) -> fetch/commit ->
   record (pre-graded) -> pipeline dispatch (runner grades, writes the correction request, pends) -> export the
   correction request -> box: correction stage + push (turn correction) -> fetch/commit -> record -> pipeline
   dispatch (runner validates, finishes, native learning, cycle 1 readiness).

## Capability map

| Module id | Responsibility | Depends on |
|---|---|---|
| box-classroom | `deploy/aws/box/frankie_box_classroom.py`: prompts, parsing, assembly, validation, acknowledgement | - |
| box-stages | `frankie_box_boss_session.py` stages `classroom` (before writing the response) and `correction`; response, record, attestation, docs, receipts | box-classroom |
| host-recorder-turns | `operations/record_actual_frankie_response.py` `--turn`, classroom pre-grade; the ps1/yml `turn` input | - |
| host-export-turn | `frankie_host_export_principal_request.{yml,ps1}` `turn` input (correction exports the correction request) | - |
| box-delivery-turn | `frankie_box_push_response.sh` `TURN`, `frankie_box_fetch_response.yml` `turn`, `frankie_box_session.sh fetch_correction` | box-stages |
| host-supersede-response | new `frankie_host_supersede_principal_response.{yml,ps1}` | - |
| restart-runbook | handoff/drop-in runbook; KALSHI_TRADING.md index | all |

Build order: box-classroom -> box-stages -> host-recorder-turns -> host-export-turn, box-delivery-turn ->
host-supersede-response -> restart-runbook.

## Commands

```
Tests (the codecs CI command, no torch): python -m pytest -q tests/test_frankie_box_classroom.py tests/test_frankie_box_boss_session_*.py tests/test_frankie_host_recorder_script.py
All Frankie box tests: python -m pytest -q tests/test_frankie_box_*.py tests/test_frankie_serverless_reading_endpoint.py tests/test_frankie_host_recorder_script.py
Shell syntax: bash -n deploy/aws/box/frankie_box_push_response.sh deploy/aws/box/frankie_box_session.sh
Workflow syntax: python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/frankie_*.yml')]"
```

## Project structure

```
deploy/aws/box/frankie_box_classroom.py        the classroom module (pure functions; validators loaded from the repo)
deploy/aws/box/frankie_box_boss_session.py     stages classroom / correction wired in
deploy/aws/box/frankie_box_push_response.sh    TURN=correction
deploy/aws/box/frankie_box_session.sh          ACTION=fetch_correction, ACTION=correction
deploy/aws/host/frankie_host_supersede_principal_response.ps1   new
deploy/aws/host/frankie_host_export_principal_request.ps1       turn
deploy/aws/host/frankie_host_record_principal_response.ps1      turn (embedded recorder source re-pinned)
research/kalshi/frankie_boss/operations/record_actual_frankie_response.py   --turn, pre-grade
.github/workflows/frankie_box_fetch_response.yml, frankie_host_export_principal_request.yml,
  frankie_host_record_principal_response.yml, frankie_host_supersede_principal_response.yml (new), frankie_box_codecs_ci.yml
tests/test_frankie_box_classroom.py (new), tests/test_frankie_box_boss_session_classroom.py (new), tests/test_frankie_host_recorder_script.py
```

## Code style

As the box modules: small pure functions, stdlib only on the box path, every output durable on disk before use,
receipts as JSON, notes through `self.note`, no emojis, no output limits on the BOSS. Fixtures build a tiny
model-visible classroom from the repo's own builders (`prepare_final_cycle` on a hand-built teacher attachment,
no market data) so the validators are the real ones.

## Testing strategy

pytest, torch-free (namespace-package loader as `tests/test_frankie_box_stacked_text.py`). Levels: (1) the classroom
module against the real validators on a synthetic 3-cursor teacher attachment (assembly passes `grade_initial_response`
with zero corrections when the BOSS text is present; every refusal path named: missing state text, wrong pair count,
invalid novel finding dropped and reported, refusal/empty output retried then refused); (2) the session stage wiring
with stubbed lanes (fan-out order, durability/resume, response keys, record/attestation composition fields);
(3) the recorder pin test (embedded source == file) and a `--turn correction` unit on a temp principal directory;
(4) shell/workflow syntax. Registered in `frankie_box_codecs_ci.yml` on push.

## Boundaries

- Always: run the tests before every commit; keep every fact in the ledgers a transcription of the pre-message or the
  BOSS's text; declare the composition in the record; receipts for every stage; nothing deleted on the host (move
  aside); keys never printed.
- Ask first (Greg): any host action (advance, supersede, record, dispatch), any box/Pod/endpoint start, any change to
  the classroom contract itself (the grader, the schemas), a response filed with `remaining_disagreements`.
- Never: fabricate Frankie's narrative text; alter the host adapter's grading; file a classroom with fewer than 19
  components or 171 pairs; run anything before Greg's go.

## Success criteria

1. `tests/test_frankie_box_classroom.py`: on the synthetic package, `assemble()` output passes the real
   `grade_initial_response` with `mastered == True` and zero corrections, `apply_relationship_view_crosscheck`
   consistent, `validate_novel_findings` on the filed list; the acknowledgement passes
   `validate_correction_resolutions` with a synthetic correction request.
2. The session's `classroom` stage is resumable: re-running with the outcomes on disk makes no model call.
3. `response.json` carries the four keys; the record and attestation carry `classroom_composition`; the docs bundle
   carries the classroom Markdown.
4. The recorder refuses (candidate, no final write) a response without a teach-back and accepts one with it,
   printing the pre-grade; `--turn correction` writes the correction response immutably.
5. All existing Frankie box tests still pass; the CI workflow lists the new tests.

## Open questions (Greg)

- The observation explanations: per-state sentence from the BOSS expanded per cursor (this spec) or one model
  sentence per cursor (about 62,000 model outputs, hours on the endpoint). Building the former; the latter is a
  switch in the classroom module if Greg wants it.
- A response.json of several MB (the review) is committed to root/cycle-NN-response by the fetch workflow; acceptable?
- Whether cycle 0's analysis text is rewritten (it says the classroom "would be written to the lessons ledger"): the
  spec re-runs only the classroom stage and the writing stage's assembly, keeping the analysis and ledgers as
  produced, and files the classroom keys beside them. The analysis prompt no longer says "no classroom lesson".
