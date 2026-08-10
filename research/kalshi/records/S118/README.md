# S118 records - what was kept, and what was deliberately dropped

D52 requires the temp/scratch sweep to be recorded, not merely performed, and to say what was
DROPPED as well as what was kept - because a directory listing proves a sweep happened, never that
it was complete (nothing inside the repo can see a directory outside it).

## Kept, and why

| path | what | why kept |
|---|---|---|
| `FRANKIE_S118_COMPLETE_RUN.json` | all 30 forecasts with reasoning, actuals, old-blind comparison, per-event errors, emission ratios, benchmarks | the machine-readable record behind the results paper; the only place the per-event reasoning survives |
| `frankie_s118_b/`, `frankie_s118_c/` | arm A (g18, g19) and arm B (g20) posteriors + E->A->B bridges | the raw run output; a re-score must not depend on re-running the agent |
| `frankie_s118_b_scores.json`, `frankie_s118_c_scores.json` | scored per-event output | inputs to the renders and to A-83/A-85 |
| `g18_s118_curve.png`, `g19_`, `g20_` | forward-curve renders | printed to Greg; kept with the A-86 caveat attached (they are daily nets joined by interpolation, not curves) |
| `a80_a82_frankie_forecast_fixes.patch` | the A-80 / A-82 fixes against `3a72fee` | deliberately NOT pushed to ChatGPT's branch; the patch is the record of what we changed and why |

## Dropped, deliberately

- **Container-local tooling that is reproducible from git**: the `tunnel-client` binary built from
  source at `/usr/local/bin` (third-party; rebuild command is in `mcp_server/README.md`) and the
  `tunnel-client` profiles under `~/.config/tunnel-client/` (machine-specific; the `init` line that
  regenerates them is in the README). Neither belongs in the repo and neither is lost.
- **`/opt/markets-mcp/`** - the original out-of-repo MCP server. Superseded by `mcp_server/` in git;
  keeping a second copy is exactly the two-copies-of-one-thing defect (S105 root cause).
- **`/tmp/tc011/`** - the downloaded v0.0.11 release zip on the box. Re-fetchable and checksum-pinned
  in `deploy_box.sh`; the S3 mirror is the durable copy.
- **Scratch ledger worktrees** (`/tmp/led*`) - working copies only; every commit is on the remote.

## Not swept, and declared rather than discovered

The S118 half-session that produced the Frankie run predates this sweep; its outputs were committed
directly to `records/S118/` at the time rather than passing through a scratch directory. No temp
disk from that half was inspected at close, because the container had already been recycled between
halves. Stated so the gap is visible instead of implied.
