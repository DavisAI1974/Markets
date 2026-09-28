# HANDOFF 2026-09-28 13:3xZ -- V9 render DONE (legacy-only, save points reused); Jev failed; nothing billing

Branch `claude/frankie-monday-cycle-0-k1esd8` (tip = this commit). Previous handoff: `HANDOFF_20260928_TOKEN_STACKS.md`.
Standing rules unchanged: no tests (py_compile with python3.12 only), `[skip ci]` on every push, no dispatch without
Greg's go, never edit frankie_box_projection.py, principal HELD, one step at a time, nothing on Greg's desktop, no
cutoff/window rules (the full Monday is read), every lossless stack applied, a probe on every long box run.

## What is DONE

1. **DIGEST_V9 on the retained Monday root** (run 36427973110, commit 5295f2d1, staged
   `/opt/frankie-box/code/5295f2d1e94486a67469186ce8c7d9e80ffb175a-36427648277-1/markets`), 13:21:30-13:22:07Z:
   - digest `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work/derivation-digest-full.md`
     = **94,961,846 bytes**, sha256 `6e9452cfd69e98617f1904dcc9fadd2b311cb579aab9ae1918bd8cb591b9002b`.
   - receipt `calculations-receipt.json` = 4,015 bytes, sha256 `85164f3c78f27e8d20955d0e6b2ca89d70304dcce42fe20e390ffbc14fc40432`
     (carries `digest_render`, `recalculation: false`, `model_calls: 0`, `bedrock_tables: not rendered`).
   - Contents: header, layer statuses, the 5 legacy tables in V9 (the whole Monday, no cutoff). That is exactly the
     6-hour run's read (`frankie_box_digest_read.legacy_read` stops at `## Bedrock (`; this file has no such heading,
     so the whole file is the read).
   - The 5 V9 legacy tables were REUSED from the save points of the stopped render (`derived/.digest-21f4036e...`),
     each hash-checked (legacy key code hash `0400d03d...` = the current frankie_box_digest_render.py). No table rewritten.
2. **Bedrock is no longer rebuilt by the render.** The first V9 render (run 36417977138, 8c6888e7) rebuilt the bedrock
   sources (13.7 GB sources.sqlite) and started the 18 bedrock tables Granite never reads; Greg: "stop the bedrock
   process and fix that". Stopped by run 36427074692 (`frankie_box_stop_cycle.sh TARGET=render`, receipt
   `/opt/frankie-box/receipts/render-stop-*.json`). Fix: `write_retained_digest(..., bedrock=False)` ->
   `Session._write_digest(bedrock=False)` -> `write_digest(bedrock_entries={})`. The bedrock layers stay whole in their
   layer files; the previous (V8) digest with its bedrock tables is under `superseded/digest-render-*/`. Nothing deleted.
3. `frankie_box_stop_cycle.sh` takes `TARGET=cycle|render` and now shares the `box-pause` lock (it had queued behind
   the render on `box-run`).

## What FAILED

- **Jev (CLM sidecar, run 36410448682)**: L40S Pod 65klqd6v45vwgi was created 10:35Z and reported status `None` for the
  whole 150 minutes; no outputs reached S3 (report/summary/predictions/pod.log all 404). The workflow DELETED the Pod
  (HTTP 204 at 13:04:44Z; cleanup 404 = already gone). Not diagnosed yet: next step is to read why the Pod never came
  up (image pull / no GPU host / startup script) before any re-dispatch, on Greg's go.

## Nothing is running or billing

No box process, no Pod (Jev's deleted; no Granite Pods started). `/opt/frankie-box/pods.json` untouched this chat.

## NEXT, in order, each on Greg's go

1. **Measure the V9 read in tokens** with a 1-2 minute canary (a slice, extrapolated; Greg's measurement rule). Only
   bytes are known (94.96 MB). Compare against the V8 read of the same root.
2. Further lossless stacks if the token count calls for it (Greg: every stack that works is used; $1k-5k reads out of
   bounds).
3. Principal inputs (`frankie_box_principal_inputs.sh`) from the NEW receipt (path + sha256 above).
4. Granite: 4 A100 SXM 80GB Pods (`pod_prepare.py`, min 16 vCPU / 125 GB RAM per GPU, cost ceiling 1.75), written to
   `pods.json` via `frankie_box_pods_config.sh ACTION=write PODS=... SLOTS=1`; the first Pod is the BOSS.
5. Jev diagnosis, then re-dispatch.

## Commits this chat (after 8c6888e7)

6ff3f686 render legacy-only + stop TARGET=render; 3500fccd stop on the pause lock; 5295f2d1 receipt names where an
earlier stopped render moved the previous digest; this handoff.
