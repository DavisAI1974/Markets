---
description: Read-only health check of the DavisAI Markets collectors and CI on GitHub Actions
---

Read-only. Dispatch, re-run and cancel nothing.

Load the `actions-operations` skill, then for `DavisAI1974/Markets` report:

1. The most recent run of each scheduled workflow (`kalshi_collectors_durable.yml`,
   `pyth_collector_durable.yml`, `nws_hourly_collector_durable.yml`,
   `nymex_mbp10_ingest_durable.yml`, `free_ng_collectors.yml`, `aws_idle_instance_guard.yml`):
   run id, start time (UTC), status, conclusion, branch.
2. Any run that is `queued` or `in_progress` for more than an hour, and any failure in the last
   seven days with the failing step and its log lines.
3. The tip commit date of `data/kalshi-bins` and `data/pyth-ticks` - did the data actually accrue.
4. Any Frankie workflow run in the last 24 hours, listed only (id, workflow, actor, status).

Finish with one line per problem and its most likely cause from the diagnosis table. If nothing
is wrong, say exactly that.

$ARGUMENTS
