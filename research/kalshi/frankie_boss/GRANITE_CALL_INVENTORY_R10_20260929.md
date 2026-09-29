# Granite call inventory for r10, sorted against the Excel build plan R4 (2026-09-29)

Reference: research/kalshi/frankie_boss/artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx (openpyxl, data_only).
Branch claude/frankie-monday-cycle-0-urozez, tip edab9066 (250e4716 + the .mcp.json registration commit).
Method: codebase-memory-mcp graph (project home-claude-markets, deploy/ re-included via .cbmignore; 335,985 nodes /
437,312 edges) for structure and callers; grep for exact file:line. Every line below was read in the file.

## What the plan sheet says (the only Granite lines in it)

| Plan row | Cell text that names Granite's role |
|---|---|
| Build Plans r9 (B2_GATED) | "B1 remains authoritative. Granite critiques or teaches through a closed schema." / "Granite begins as a shadow teacher/critic". Since 2026-09-21 "the same BOSS vLLM is now the principal engine (Frankie's session on his box calls it over jobs_v1)". |
| Components r26 C21 | Deterministic state serializer: "Be the only answer-walled bridge from B1 state to Granite." granite_context (stacked_v1) served the critic request. |
| Components r27 C22 | Granite 4.2 8B checkpoint/runtime: "a RunPod Pod (L40S, vLLM ... served model granite42-smoke, context 131,072 ... jobs_v1)"; "Since 2026-09-21 also the principal engine". Evidence names POD_ID g7y3g2w1kor4l3. |
| Components r28 C23 | Closed Granite parser, prompt and receipt: "Approved Granite output/prompt V1 caps and nonempty hypotheses". |
| Components r29 C24 | B2 disagreement/fusion policy: "an invalid, empty or unavailable critic leaves the native result authoritative". |
| Components r40 C35 | Frankie's box harness and the BOSS engine session: "verify, timing labels by code, engine reach, derive ..., bounded reading of the delivered evidence through the BOSS, writing of the four files, push." |
| Components r19 C14 | Dipole target schema: "the governed C15 teacher classroom (dipole_classroom*.py, 171 teach-back pairs, DipoleTarget 19 dimensions) is built and its package travels with each cycle". Role column: "Training-target contract only." NO Granite named. |
| Roadmap r14 (stage 8) | "Wire Granite 4.2 8B as an independent B2 shadow lane." "Since 2026-09-21 the same service is Frankie's engine." |
| Gates G16-G19 | Granite identity frozen (G16 complete); serializer (G17); replicated inference (G18 not started); timeout/malformed/disagreement leave B1 running (G19 partial). |

Not in the sheet anywhere (searched every sheet): knowledge loop / priming / learning replay / cumulative,
scientific dialogue, teacher discussion, joined teacher, Jev sit-in, CLM sidecar, serverless reading lane.

## Every Granite (BOSS vLLM) call reachable from a cycle0.sh dispatch

The model primitive on the box is Session.boss (deploy/aws/box/frankie_box_boss_session.py:740), reached through
Session.reader (:689) and Session._boss_complete (:2299). The launch runner's critic goes through
build_runpod_service (research/kalshi/frankie_boss/operations/run_actual_sunday.py:1045).

| # | Dispatch / stage | file:line | What it asks Granite | Plan role | Gate (on/off in r10) |
|---|---|---|---|---|---|
| 1 | launch: native runtime, critic | operations/run_actual_sunday.py:968 (prepared_input -> prepare_critic_request), :1040-1048 (critic factory), :1050-1058 (SundayRuntime critic_factory) | the B2 shadow critic request (stacked_v2 context, closed schema) | C21-C24 | ON: runs inside the launch runtime before the WAIT; needs the readiness dir of the retained Pod via the FRANKIE_ACTUAL_EXECUTE_V1 trigger |
| 1a | launch: critic knowledge loop | run_actual_sunday.py:944-957, :1012, :1058 (critic_knowledge=...); critic_knowledge.py (added 2026-09-22, commit 6c3acee) | feeds prior completed-cycle lessons into the critic request ("cumulative_completed_cycles_v1") | inside C21-C24 but NOT a plan line (post-R4) | ON when context_encoding is stacked_v1/v2 (host_config.py:51 sets stacked_v2); learning_policy is not set by host_config |
| 1b | launch: critic priming | frankie_box_host_config.py:59 (critic_priming from blocks/GRANITE_PRIMING_CONFIGURATION_20260922.json: mode knowledge_primed_learning_replay, profile retained_cycle00_20260921); run_actual_sunday.py:1066-1078; feedback_cycle.py:141-221 | primes the critic with the retained cycle-00 profile | inside C21-C24 but NOT a plan line (post-R4, 2026-09-22) | ON (written into every r10 config) |
| 2 | principal: engine reach | frankie_box_boss_session.py:450 engine_reach | a reach of the Pod service (identity, no reasoning) | C35 ("engine reach") | ON |
| 3 | principal: reading parts | :1478 reading -> :1511 _read_part_guarded -> :1766 self.reader -> :694/:697 self.boss | bounded reading of the delivered evidence in parts, notes | C35 ("bounded reading of the delivered evidence through the BOSS") | ON |
| 4 | principal: merges | :1670 _merge -> :1678/:1694 self.reader | merge the reading notes level by level | C35 (the merges belong to the reading) | ON |
| 5 | principal: classroom, 19 components | :1856 classroom -> :1901 _classroom_call(..., 'reader') -> reader -> boss | answers the 19 governed components | C14 classroom answered through the C35 engine (an INFERENCE: C14 names no Granite; the spec keeps it) | ON |
| 6 | principal: classroom summary | :1911 _classroom_call('classroom-summary', ..., 'boss') | the summary over the 19 answers | C14 through C35 (same inference) | ON |
| 7 | principal: classroom staged/dialogue branch | :1875-1878 (shared_knowledge present -> frankie_box_classroom_staged.run with frankie_box_scientific_dialogue) | the scientific-teacher dialogue and teacher discussion over shared knowledge | NONE (added 2026-09-22, after R4) | OFF by config: run_actual_sunday_classroom.py:203 passes shared_knowledge only when classroom_scientific_dialogue is True; frankie_box_host_config.py:79 writes False. The code path is still reachable if a request carries shared_knowledge. |
| 8 | principal: teach | :2030 teach | none: model_calls=0, facts by code (frankie_box_teach) | code only (Greg 2026-09-28) | ON, no model call |
| 9 | principal: writing, analysis | :2145 writing -> :2204 written('write-analysis') -> :2199 _boss_complete -> :2304 self.boss | the run analysis narrative | C35 ("writing of the four files") | ON |
| 10 | principal: writing, accounting entry | :2221 written('write-accounting') | the ONE accounting entry over the pin layers | C35 writing | ON |
| 11 | principal: writing, ten output ledgers | :2246 written(f'write-{name}') for OUTPUT_LEDGERS | one ledger object each | C35 writing | ON |
| 12 | correction: plain classroom correction | :1943 correction -> :1993 _classroom_call('classroom-correction', ..., 'boss') | resolves the graded correction ids | C14 correction turn through C35 (same inference as 5/6) | ON (the plain path) |
| 12a | correction: learning_history in the request | dipole_classroom_final_review.py:344-347 (learning_history -> validate_history); dipole_classroom_learning.py (added 2026-09-22) | the retained learning history is appended to the correction prompt | inside the C14 correction but NOT a plan line (post-R4) | ON when the host passes learning_history (run_actual_sunday_classroom.prime_cache -> build_final_correction_request) |
| 13 | correction: scientific review branch | frankie_box_boss_session.py:1974-1990 (scientific_review_request present -> frankie_box_scientific_dialogue.run + classroom_staged.run_correction) | the scientific-teacher conversation about the whole run | NONE (post-R4) | OFF by the same gate: dipole_classroom_final_review.py:349-353 adds scientific_review_request only when shared_knowledge is passed, which is the classroom_scientific_dialogue config. Code path still reachable if the request carries it. |
| 14 | reading lane transport: RunPod serverless | :507 serverless_reach; :588 serverless_job; :689-692 reader; :2446/:2481/:2485 _run | the same reading/merge/classroom-component calls, over a serverless endpoint instead of the Pod | NONE: C22 names the Pod; no plan line names serverless (Greg 2026-09-28: "Not using serverless anymore") | gated on /opt/frankie-box/serverless.json existing on the box (frankie_box_serverless_config.sh); a configured lane with no healthy endpoint REFUSES, never falls back |
| 15 | record | frankie_box_cycle0.sh:43-63 -> operations/record_actual_frankie_response.py | none: grades and records; no model call | code | no model call |

Not reachable from cycle0.sh (their own dispatch scripts; not dispatched for r10): frankie_box_joined_teacher.sh
(joined teacher builder), frankie_box_jev_relay.sh (Jev sit-in), frankie_box_clm_sidecar_*.sh (CLM sidecar). The
joined manifest is refused at config (frankie_box_host_config.py:81-82).

## The NONE list (Granite reachable in a role the sheet does not give it)

- Row 7: the classroom staged/dialogue branch, frankie_box_boss_session.py:1875-1878.
- Row 13: the correction scientific-review branch, frankie_box_boss_session.py:1974-1990.
- Row 14: the serverless reading transport, frankie_box_boss_session.py:507-687 and the three _run call sites.
Rows 7 and 13 are switched off by one config gate but the code still routes to the dialogue when the request carries
the field. Row 14 is switched by a file on the box.

## Post-R4 additions INSIDE a kept role (not in the sheet; Greg's call, not touched)

- Rows 1a, 1b: the critic knowledge loop and critic priming (2026-09-22) change what the C21-C24 critic reads.
  Unwiring them makes the runner refuse retained preparations that carry a critic_knowledge_hash.
- Row 12a: learning_history in the correction request (2026-09-22).

## Open points for Greg (from the sheet itself)

1. C14 is a training-target contract and names no Granite; "the classroom answered through C35" (rows 5, 6, 12) is
   the spec's inference. Accept it, add it to the plan, or take the classroom off Granite.
2. Where the C21-C24 critic runs in r10: inside the launch runtime (run_actual_sunday.py:1040-1058), before the
   principal WAIT, against the readiness directory of the retained Pod (C22's Pod). The principal, classroom and
   correction call the same served model (granite42-smoke) over jobs_v1 through pods.json.
3. Pods: the session runs with one Pod (reader :693: pods*slots == 1 goes straight to boss); more Pods only widen the
   fan-out (reading parts, merges, 19 components). r6/r9 used 4 A100s. The critic needs the retained service the
   trigger names. POD_ID_DEFAULT fhiwwlouzyx6l2 (:67) is a stale default; pods.json is what r10 uses.

## UNWIRED in this commit (Greg 2026-09-29: "Then unwire wrong pieces"; "Not using serverless anymore")

All three NONE items, in `deploy/aws/box/frankie_box_boss_session.py` (not a pinned file) and its config script:
1. Classroom staged/dialogue branch: a classroom package carrying `shared_knowledge` is now a REFUSAL with the reason
   (was: routed to frankie_box_classroom_staged + frankie_box_scientific_dialogue).
2. Correction scientific-review branch: a correction request carrying `scientific_review_request` is now a REFUSAL
   (was: routed to frankie_box_scientific_dialogue + classroom_staged.run_correction). The correction is the plain
   C14 correction on the BOSS only; the reply no longer carries `dipole_scientific_exchange`.
3. Serverless reading lane: `serverless_reach`, `_serverless_exchange`, `_supersede_job`, `serverless_job` removed;
   `reader` and `_fan_out` are the Pods only (pods.json); `serverless_unwired()` refuses if
   `/opt/frankie-box/serverless.json` is present (preflight and the run). `frankie_box_serverless_config.sh`
   ACTION=write is refused; ACTION=remove moves a left-over file aside (nothing deleted).

The modules the branches called are kept on disk, only disconnected. Tests that exercise the removed paths
(tests/test_frankie_box_boss_session_rerun.py, tests/test_frankie_box_classroom_cache.py, the classroom-staged and
scientific-dialogue tests) were not run or edited (no tests during the build). py_compile python3.12: OK.

Not touched (inside kept roles, Greg's call): the critic knowledge loop and critic priming (rows 1a, 1b) and the
correction's learning_history (row 12a).

Before r10 on the box: `frankie_box_serverless_config.sh ACTION=show` (read-only). If the file is present, r10 refuses
at preflight until `ACTION=remove` (Greg's go).


## R3 vs R4 (Greg 2026-09-29: "If 4 is different use 2 or 3", "Except for the pod use")
R2 is not in the repo (only R3 `Frankie_BOSS_Build_Plan_R3_20260914_Closeout.xlsx` and R4). Granite-relevant cells:
| Row | R3 (2026-09-14) | R4 (2026-09-21) |
|---|---|---|
| Build Plans B2 reasoning / Granite role | "Granite critiques or teaches through a closed schema"; "Shadow-only initially" | same text, plus Current capability: "the same BOSS vLLM is now the principal engine" |
| C22 function now | "No approved model download or serving path is wired into Frankie/BOSS." | the retained RunPod Pod service (vLLM, jobs_v1); "Since 2026-09-21 also the principal engine" |
| C35 | absent | "bounded reading of the delivered evidence through the BOSS, writing of the four files" |
| C14 capability | "six unbuilt B2/C1 columns remain explicitly ABLATED" (no classroom) | the governed classroom (171 pairs, 19 dimensions) travels with each cycle; role still "Training-target contract only" |
| C21, C23, C24 | intended role, authority, never-do: identical in both | identical; capability/status updated to "built and run" |
| Roadmap stage 8 | "Pin checkpoint/runtime and wire serving ... shadow disagreement policy" | "Retained Granite service on RunPod ... Since 2026-09-21 the same service is Frankie's engine" |
| Preservation Audit | no Granite rows | adds "Principal engine": the BOSS vLLM is the engine |
Greg's decision: R3 roles (the shadow critic only) on the R4 Pod; the classroom on the critic; Frankie does the
analysis. See `SPEC-decouple-granite.md` DECISION block.
