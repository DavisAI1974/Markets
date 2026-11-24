# What Granite's own code records for one call (stage 8a)

Read 2026-11-24 from Granite's writer code on the Frankie branch (`origin/frankie-tip`, tip 881377b), not from
the stopped run's notes. Paths are on that branch; line numbers are those of that tip.
`S` = `deploy/aws/box/frankie_box_boss_session.py`, `C` = `research/kalshi/frankie_boss/granite_durable_job_client.py`.

## Two writers

1. Box job (the principal engine: reading parts, merges, classroom answers, self-assessment). `Session.boss`,
   S:2459. Folder `<work>/boss-jobs/<job_id[:24]>/` (S:2146 `self.jobs`, S:2485).
2. Critic spool (the shadow critic). `_durable_transport`, C:111. Folder `<spool>/<sha256(request_id)>/` (C:123).

## Field table

| Field the plan asks for | Box job | Critic spool |
|---|---|---|
| call id | `request.json` `job_id` (S:2494; hash of attempt, request hash, config hash, body sha, S:2483) | `dispatch.json` `binding.job_id` (C:124) |
| conversation id | NOT recorded. `request.json` `attempt` = `<request_id>:<name>` (S:2482, S:2494): the request_id part is used | `binding.attempt_id` = the controller's `request.request_id` (C:124) |
| who started it (`started_by`) | NOT RECORDED | NOT RECORDED |
| purpose / role | NOT recorded as a purpose. `request.json` `name` (S:2494) and `outcome.json` `name` (S:2556): the job name | NOT RECORDED (no name; the folder is the critic spool, S:5258 `critic-spool/*/outcome.json`) |
| input (prompt) tokens | `result.json` `usage.prompt_tokens` (raw service result written at S:2530). `outcome.json` `usage` is set at S:2572-2575 (`_parse`, S:2555), after the try/except, for EVERY HTTP-200 result (normal, incomplete and unparseable alike); only the non-200 branch (S:2557-2560) returns without it. `output-incomplete.json` `usage` is also written when output ran out (S:2567). The reader still takes `result.json` first (the raw service result) and `outcome.json` second. Also `request.json` `estimated_input_tokens` (S:2495) and `outcome.json` `estimated_input_tokens` (S:2533) = an estimate, not a count | `outcome.json` `body_base64` decoded -> `usage.prompt_tokens` (written C:237-238). `dispatch.json` `admission.input_tokens` is the admission estimate (C:136, C:138) |
| output (completion) tokens | `result.json` `usage.completion_tokens` (same as above) | decoded `body_base64` -> `usage.completion_tokens` |
| wall clock | `outcome.json` `seconds` = `time.time() - started` (S:2532). Starts at THIS invocation of `boss` (S:2501), so a resumed job restarts it; a failed job (S:2537) has none | NOT RECORDED |
| start time | NOT RECORDED. Nearest: `observations.jsonl` `at` (S:2553, written by `_observe`, first line at `accepted` S:2509: after the start) | NOT RECORDED. Nearest: decoded body `created` (provider's time the response was made: the END of the call). The `observation-*.json` files (C:146) hold `binding` and `phase` only, no time |
| output text | `outcome.json` `text` (S:2562, S:2566) | decoded `body_base64` `choices[0].message.content` |
| packet / prompt | `prompt.txt` beside `request.json` (S:2497) | `request.json` `messages[0].content` (the raw request body, C:137) |
| model | `outcome.json` `model` (S:2562); `request.json` `served_model_name` (S:2496) | decoded body `model` |
| incomplete / error | `outcome.json` `incomplete` (S:2556), `error` (S:2538, S:2558, S:2571) | `finish_reason` in the decoded body; `outcome.json` `status`, `http_status` (C:237) |

The plan's five fields: input tokens and output tokens are recorded by both writers. Purpose is recorded only as a
job NAME by the box writer and not at all by the critic spool. Who or what started the call is recorded by
NEITHER. Wall clock is recorded by the box writer only (and restarts on resume). No writer records a start time.

## Consequences for the baseline reader

- `started_by`, `started_at` are `not_recorded` on every call; they are never filled.
- A call is assigned to a trade day by the nearest recorded time marker, and the line says which one:
  `first_observation_at` (box) or the provider's `created` (spool). A box marker is later than the start, a spool
  marker is the end of the call, so a call near 18:00 or 17:00 ET can land on the wrong side. This is said, not fixed. The marker places the call; it is not the call's start.
- A trade day is 18:00 ET the evening before to 17:00 ET on the date, Monday to Friday. A marker from Friday 17:00 ET to Sunday 18:00 ET is listed under `outside_any_trade_day`; 17:00 to 18:00 ET Monday to Thursday is `halt`.
- A folder whose request.json or dispatch.json cannot be read is listed under `unreadable` with its path and reason; a folder that reads but is not a Granite record is under `not_a_granite_record`.
- A call without a marker is listed apart (`no_start_time`), never dropped.

## Purposes (call names) Granite's code gives

| Name shape | Where built | Family |
|---|---|---|
| `read-NNNN` + optional pass suffix; `-retry`, `-a`, `-b` | S:4783, S:4802, S:4809 | read-part |
| `merge-<level>-final`, `merge-<level>-<gggg>` | S:4703, S:4719 | merge-notes |
| `granite-self-assessment` | S:5276 | self-assessment |
| `staged-<plan_hash[:16]>-<part_id[:24]>` | `deploy/aws/box/frankie_box_staged_session.py:117` | classroom-staged-part |
| name chosen by the caller of `_boss_complete` (`-a`/`-b` on a split) | S:5360-5375 | no call site on this tip; not in the table |
| name chosen by the scientific dialogue | `deploy/aws/box/frankie_box_scientific_dialogue.py:15,25` | refused by the 2026-09-29 unwiring per `GRANITE_CALL_INVENTORY_R10_20260929.md`; not in the table |
| (the critic spool has no name) | C:124 | shadow-critic |

## The one real per-call record found

`research/kalshi/frankie_boss/sunday_20260915_package/FB/actual-feedback-run/execution/cycle-00/critic-spool/5f6d6b901ad0177075e3f4a90bbd9c3dd9b4cd91fb49fe743730a67bbf77b359/`
on `origin/frankie-tip`: a committed critic-spool folder of the first real run. Its `outcome.json` decodes to
`usage.prompt_tokens` 92,428 and `usage.completion_tokens` 119, `created` 1789499045 (2026-09-15 15:04:05 ET, trade
day 2026-09-15), and `dispatch.json` `admission.input_tokens` 92,428. One call; it is the only one. No box-job folder
(`boss-jobs/`) is committed anywhere found, so the box reader has not been checked on a real record.
