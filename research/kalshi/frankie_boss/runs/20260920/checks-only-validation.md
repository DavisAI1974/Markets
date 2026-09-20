# Checks-only validation, 2026-09-20

Ordered work item 1 of `DROP_IN_CLAUDE_20260920.md`: preserve and record the final checks result.
Every figure below was read back from the GitHub Actions API and from the downloaded run log archive
for the named run. Nothing here is operator-reported and nothing here is a Frankie runtime result.

## Final run (the one to cite)

- Workflow: `.github/workflows/frankie_journal_stack.yml` (workflow id 358665467)
- Run: 35497376513, run number 23, attempt 1, event `workflow_dispatch`, actor DavisAI1974
- Ref: `codex/frankie-launch-two-cycle-20260919` at `a5ad20bcfe51d4f6478dd1632ad82ca717305f29`
- Started 2026-09-20T07:37:38Z, completed 2026-09-20T07:39:55Z
- Run conclusion: success
- https://github.com/DavisAI1974/Markets/actions/runs/35497376513

Job outcomes: `checks` success; `sources`, `journal`, `cleanup` and `host` all skipped. Only the
checks job ran a runner. The dispatch inputs are not exposed by the run API, so `day=20211003`,
`cycles=2`, `checks_only=true`, `keep_compute=true` remain operator-reported; the skip pattern above
is consistent with `checks_only=true`, and because no compute job started there is no observable
effect of `keep_compute` in this run to verify either way.

Measured step results inside the checks job:

| step | result |
|---|---|
| Complete scientific family and changed launch controls | 1101 passed, 1 skipped, 3 warnings in 79.95s |
| Validate workflow YAML | success |
| Checkout receiver | `codex/frankie-sealed-proof-producer-20260919` at `7b98617bdbbc2476666db9cf1c018c8efe6878da` |
| Verify receiver sealed proof production and rendering | 352 passed, 234 subtests passed in 3.78s |

The family step ran the twelve declared globs: `test_granite*.py`, `test_sunday*.py`,
`test_run_actual*.py`, `test_frankie_controller.py`, `test_actual_host*.py`, `test_day_pipeline.py`,
`test_classroom_recovery_reconciliation.py`, `test_stage_block_sources.py`,
`test_frankie_principal_adapter.py`, `test_launch_pins.py`, `test_git_request_archive.py`,
`test_retained_generation_publication.py`. Nothing was deselected.

The receiver step ran `test_native_sealed_absence.py`, `test_emit_frankie_spawn.py`,
`test_prepare_boss_attachment.py`, `test_native_principal_outputs.py` and `test_native_staging.py`
against the frozen receiver commit, which matches `launch_pins.py:11` `receiver_commit`.

The three warnings are a single environment `DeprecationWarning` from
`multiprocessing/popen_fork.py:73` ("this process is multi-threaded, use of fork() may lead to
deadlocks in the child"), raised under
`test_granite_runpod_cloud_control.py::test_stalled_operation_is_killed_with_wall_deadline` once and
`::test_isolated_result_larger_than_pipe_buffer_and_provider_error` twice. They are not assertion
failures and no test result depends on them.

## The preceding run named in the drop-in

`DROP_IN_CLAUDE_20260920.md` asked for run 35497249802 to be polled. It is also completed with
conclusion success, at the code tip `fbbc5ce9fbd399733059e336cced05776bb62b2b`, with the same job
skip pattern, and its logs carry the identical counts: 1101 passed, 1 skipped, 3 warnings in 83.86s,
and 352 passed with 234 subtests passed in 4.16s. That drop-in item is now closed.

Because `a5ad20bc` only adds the docs commit "docs: point Frankie Claude handoff to 20260920" on top
of `fbbc5ce9`, the identical counts across the two runs are the expected result and confirm the docs
commit changed no check.

`fbbc5ce9` fixed a checks-only fixture by populating the canonical attachment hash before the
principal adapter runs. The earlier two-failure run on `909c4683` was that fixture KeyError pair, not
a Frankie runtime failure.

The noisy `ng_exhaustion_step1_receipt_count_20260823.yml` failure is a separate workflow and is not
part of this result.

## What this result does not establish

These are green checks on an unlaunched tree. This run performed no inference, started no host and
wrote no S3 receipt. It is not evidence of an initial Frankie principal response, a classroom grade,
a correction receipt or a downstream configuration receipt; none of those is verified yet. The native
run last reached `boss_reasoning` at cursor 3261 with completed 0, and that has not advanced here.

Both EC2 hosts remain last-verified stopped, native `i-0e90ee6110ef609aa` in us-east-2 and ingest
`i-035994afa8bdf66a5` in us-east-1. Nothing in this session started, stopped or contacted either
host, or read or wrote the retained S3 prefix.

Launch remains HOLD. Ordered item 2 stays unstarted: it requires an explicit new authorization, and
a go to run on Sunday is not by itself permission to change a workflow.
