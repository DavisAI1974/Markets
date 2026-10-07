# Step 5 — owner-loop successor dispatch and recovery

SOURCE-BUILT / RUNTIME-UNVERIFIED. Greg requested this slice on 2026-10-06 at 23:49 ET,
then directed API/module and AWS workflow skills on each module. Source review, AST without
project imports and whitespace checks only. No tests, installs, model/data/scientific runs,
reproduction, AWS account inspection/actions, starts, dispatch or E2E occurred. The AWS plugin
was used only to retrieve its EC2/Systems Manager skill documentation.

## Checklist disposition

- [x] Source: explicit request and checked-decision intake on the actual scientific owner.
- [x] Source: existing ROOT/class day loops dispatch into their held CPU lane.
- [x] Source: immutable operation identity, candidate reuse, publication recovery and completion acknowledgment.
- [x] Source: cooperative successor save/resume, failure-specific retry, pending status and final day intake closure.
- [ ] Runtime verification: held-lane execution, crash recovery, mailbox sync and actual learner consumption.

This crosses off the narrow **Step 5 accumulated-successor loop dispatch/recovery source** item.
It does not complete all Step 5, the general Step 8 main/class save lifecycle, or Steps 2–7.

## Public interfaces and ownership

`frankie_box_experiment.sh` adds actions `successor-request`, `successor-decision`,
`successor-retry`, `successor-save`, and `successor-resume`. Existing plan/start/status behavior
is retained. All actions require the existing staged CODE_ROOT/MARKETS_SHA and RUN, plus
SUCCESSOR_DAY. Request/decision/retry use SUCCESSOR_FILE, an actual owner-local JSON file;
decision/retry also use SUCCESSOR_ID. These intake actions file intent only: they do not start
a worker, allocate CPUs, run the scientific teacher or call a provider. ACTION=status includes
the read-only successor inventory; the run summary cannot call pending successors complete.
No example live dispatch is authorized by this document.

The corresponding Python boundaries in `frankie_box_successor_dispatch.py` are:

| Interface | Input and result | Replay/refusal |
|---|---|---|
| `enqueue(run, day, request)` | Exact `teach_successor` request: original_inputs, original_result, reason, evidence. Returns id and operation witness. | Content-addressed id is stable across retries; same original cannot acquire a competing queued operation. Changed owner plan/search/code refuses. |
| `submit_decision(run, day, id, decision)` | receipt witness, scopes, decision, reason, evidence. Returns immutable decision witness. | Binds the exact completed candidate; applies the existing correction guard before filing. Different decision under the same id refuses. |
| `retry(run, day, id, failure)` | Exact current failure-file witness. Returns retry witness. | Grants retry only for that failure, never a later failure or another operation. Does not change original inputs/results. |
| `control(run, day, saved)` | Day-specific successor pause/resume intent. Returns control witness. | Does not pause the host or another day; actual saved acknowledgment is distinct from the requested control. |
| `drain(run, day)` | Existing active owner and its held booking. Returns checked acknowledgment witnesses. | Serializes ROOT/class consumers; resumes the same request and work directory; no new booking or scientific decision. |
| `close_day(run, day)` | Final existing day-completion boundary. Returns closed-inbox witness. | Serializes with enqueue; newly arrived accepted requests must finish before close. Closed days cannot be silently reopened. |

Artifacts live under the existing run's `successors/<day>/`: content-addressed requests,
immutable decisions, and `work/<id>/` containing frozen teaching inputs, complete candidates,
publication, acknowledgment, state/failure/retry receipts and locks. Existing durable writes
retain previous bytes. No new scheduler, AWS service, host, lane or booking is introduced.
The Linux lane uses the same owner-local code and saved plan; central intake refuses its remote
ROOT ownership. Giant evidence remains there. Remote delivery of operator files must target
that existing host; this patch does not invent a central artifact-copy or credential path.

## Module-by-module source review

| Module | Responsibility and reviewed boundary |
|---|---|
| `frankie_box_experiment.sh` | Additive, quoted-argv intake routing; same staged checkout check and existing launcher. No eval or new provider invocation. |
| `frankie_box_experiment.py` | Saved-plan intake, successor boundary before children/guarded stages, durable step receipts, pending inventory and status. Explicit successor child alone uses its newly frozen selection instead of demanding reuse of old inputs. Ordinary stale-selection guards remain. |
| `frankie_box_successor_dispatch.py` | Owner/request/decision binding, locks, intent-before-dispatch, phase receipts, failure-specific retries, sync recovery and acknowledgment. Requires actual existing run/day CPU booking. |
| `frankie_box_teacher_successor.sh` | Staged scientific child; exact operation path/phase passed as argv. Python rechecks plan, code and held owner booking. Never books a lane itself. |
| `frankie_box_teacher_knowledge.py` | Reused `teach_successor`/`publish_successor`: whole original claim set, original reproduction records and complete results preserved; checked publication only. |
| `frankie_box_experiment_review.py` | Existing same-subject/explicit-transition/scoped replacement contract remains authoritative; no metadata exemption or recency winner. |
| `frankie_box_frankie_queue.py` | ROOT/class boundaries drain pending work in their original slot; final day completion closes intake only after acknowledgments. Cached dependent teacher stages still check current selections. |
| `frankie_box_lane_state.py` / `frankie_box_cores.py` | Existing interfaces reused, not replaced: interrupted sync is recovered with its original payload; correction snapshot acknowledgment precedes completion; CPU child runs inside the held booking. |

## Recovery behavior

| Interruption or boundary | Source behavior |
|---|---|
| Duplicate intake | Same operation witness; never another id for the same intent. |
| Parent dies while child survives | Child-operation lock serializes execution; a second child reads the exact completed receipt without rewriting it. |
| Result saved before successor receipt | Existing teacher reuses the complete result under its frozen input identity and reconstructs the missing receipt. Partial deterministic local teaching resumes the same operation; it adds no independent observation. No model call exists in this path. |
| Candidate exists, no decision | Owner remains waiting with its CPU booking; no correction or ordinary candidate lesson is published. |
| Publication happened before child completion receipt | Retry calls the same guarded correction publication; its retained record and objects are reused. |
| Interrupted mailbox sync | Recover the original pending sync before constructing another snapshot payload. Other pending lane operations remain with their own recovery owner. |
| Save requested during a child | Let the child retain its current operation; the successor loop catches exit 75, records saved and waits without entering the queue's failure/release path. A successor-specific pause is acknowledged after the child returns. |
| Child returns failure | Exact failure retained; owner waits until retry intent names that failure. No automatic failure loop. |
| Crash after completion acknowledgment | Read back request -> decision -> publication -> checked brain correction; reuse acknowledgment without another scientific call. |
| Request races final completion | Intake lock distinguishes accepted pending work from a closed owner day. A late unaccepted request explicitly refuses, never disappears or silently reopens the day. |

Cooperative waiting retains the live owner's booking; this is not a claim that a killed host or
worker keeps a live process reservation. Existing host/queue/claim recovery remains its owner,
including CCode's Step 8A controller work and the still-open general main/class save lifecycle.

## Remaining scope and next review

The scientific owner must still supply the actual researched decision. Changed claim content,
changed search evidence, a smaller affected subset inside one multi-claim result, and rebuilding
dependent exchange/native requests are outside this unchanged-claim/unchanged-search operation.
Those stale dependencies refuse; they are not silently re-enabled by a successful correction.
Old completed days are not automatically reopened. Run.jev still waits; its CPU pins/count,
owner-local seal/testing/publication/completion remain open. Both teachers' historical rework
and all other held mathematical decisions remain open.

Greg also requested the same API/module and AWS workflow review for the other steps. Continue
that review after this slice, using existing inventories and per-step contracts. CCode retains
his active Step 8A files; record interface requests there rather than overlap his implementation.
