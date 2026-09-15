# Durable Granite jobs v1

## Problem and contract

Runpod's HTTP proxy limits request duration, while one admitted exact Granite
prefill/decode may continue making progress longer than that limit. The explicit
`jobs_v1` transport separates short authenticated HTTP operations from backend
execution. It never falls back to a direct model POST.

`GRANITE_TRANSPORT_PROTOCOL=jobs_v1` is pinned in the launch environment, verified
in the child and parent startup receipts, and exposed as
`durable_job_protocol=jobs_v1` in the outer startup witness. The absent setting
preserves the legacy direct protocol. Bootstrap bundle and pre-import verifier
rosters include `granite_runpod_jobs.py`.

All routes require the existing bearer credential. Request ingress retains the
existing bounded framing, exact text-only model contract, and 1 MiB body cap.

| Request | Response |
| --- | --- |
| `POST /v1/jobs/{64-lowercase-hex-id}` | 202 control after durable acceptance; original exact model JSON body and `X-Granite-Request-SHA256` required |
| Same POST, same ID and bytes | 202 existing control; never duplicate a running/ambiguous/completed job |
| Same ID, different bytes | 409; no backend action |
| `GET /v1/jobs/{id}` | 200 control or 404 unknown |
| `GET /v1/jobs/{id}/result` | 200 exact raw completed outcome, 202 control while incomplete, 404 unknown |
| `GET /health` | Bounded backend health check independent of worker execution |

Control schema `GRANITE_DURABLE_JOB_V1` contains `job_id`, `request_sha256`,
`state`, `accepted_at`, `updated_at`, and (after intent) `dispatch_at`. Completed
control also contains `result_sha256`, `result_bytes`, and `result_status` (the
original backend HTTP status, including non-200 outcomes). Result size is at
most 4 MiB. Model outcome interpretation remains the client's responsibility.

## Persistence and dispatch

`/opt/ml/granite-jobs-v1/jobs.sqlite` stores original request bytes, immutable
request hash, control state, and exact raw outcome. SQLite WAL with synchronous
FULL commits acceptance before 202 or scheduling. One OS process lock excludes
another server from this spool for the whole lifetime of its workers.

1. Exact POST transaction inserts `accepted` or resumes `not_dispatched`.
2. One worker establishes a bounded loopback connection before any model POST.
3. Worker commits `running` with dispatch intent before invoking HTTP request.
4. Backend execution has no total duration or read timeout.
5. Exact raw bytes, hash, count and status commit atomically as `completed`.

Connect/thread-start failure before dispatch is `not_dispatched`; another exact
POST can safely resume it. Any exception after dispatch intent is `ambiguous`.
On process restart, retained `running` becomes `ambiguous`, and retained
`accepted` becomes `not_dispatched`. No restart, duplicate POST, polling request,
or timer can redispatch an ambiguous job. A durable intent that survived a crash
immediately before backend POST is deliberately conservative: it too requires
inspection. HTTP health responsiveness alone is not inference progress evidence.

Credentials stay outside durable request data and are stripped from backend
environment by the existing supervisor. Accidental credential text in a model
body is rejected before acceptance. Credential echoes in an outcome produce
`failed` without persisting or exposing that echo. Request/exception contents
are never logged. Explicit process termination can stop work; it does not grant
permission to execute the same ambiguous job again.

## New verification only

`test_granite_runpod_jobs.py`: atomic duplicate acceptance, exact non-200 outcome
and reopening, preconnect retry versus ambiguous dispatch, thread-start failure,
exclusive spool ownership, and restart classification. Four new tests passed.

`test_granite_jobs_integration.py`: authenticated HTTP acceptance, bounded health
and polling while a synthetic worker is blocked, no direct fallback, exact
result retrieval, protocol propagation through child/parent verification, and
server-module bootstrap roster/tamper checks. A fourth seam connects the actual
durable client to the actual store, loses the acceptance response, retrieves the
same result with one backend dispatch, then replays without credentials. Four new tests passed. These use
synthetic bytes/processes; no Granite inference, GPU or cloud action occurred.
