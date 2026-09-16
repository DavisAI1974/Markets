# ccode review - classroom integration branch (2026-09-16), before the Codex hand-off

Reviewed: `chatgpt/frankie-dipole-classroom-integration-20260916` at `cf9e2c87` (thirteen commits on
top of my review tip `02306339`). Review branch: `ccode/frankie-dipole-classroom-integration-review-20260916`.
No Frankie, Granite, EC2, Pod, market-data or result-bearing run.

## Executed

The handoff said the new integration tests had not been run anywhere but a focused CI branch.
Run here (Python 3.13.7, torch 2.9.1+cpu, numpy 2.3.5): the handoff's eleven suites plus
`test_actual_host_probe_wiring.py`: **68 passed** as committed; **70 passed** with the two tests
added below. Science drift against the lawful `050c5056`: none (same file list as the previous
two reviews; `git diff --stat` empty).

## The fourteen review requests, answered

1. Suites run: yes, above.
2. Method rebinding on `IntegratedDipoleClassroomPrincipalAdapter`: the three reused methods call
   `FrankiePrincipalAdapter.prepare/_request/recover` by explicit class, never `super()`, so no
   zero-argument-super cell binds them to the final class. Proven by driving the integrated
   adapter through the real two-turn flow in SOCRATIC mode (the isolation test is now
   parametrised over the final and the integrated adapter; both pass with identical assertions).
3. End-to-end non-model path: `test_full_request_plan_is_saved_before_coordinator_or_critic_call`
   binds a real package and the integrated class through `SundayRuntime` into `_LazyPrincipal` and
   pins `principal_adapter_identity` in the plan; `_LazyPrincipal` passes the class to
   `make_principal_adapter`. Verified by reading and by the test.
4. Restart refusals: wrong request id and changed binding hash (unchanged checks), missing adapter
   class (`test_execution_refuses_missing_classroom_adapter_class`), changed module:qualname
   (the plan comparison), stale prior-cycle package (`runtime()` reloads from the cycle directory
   before calling the lawful runtime). Verified.
5. Filesystem isolation: unchanged from `02306339` and re-proven through the integrated adapter.
6. Correction locality and prior-summary carry: unchanged code paths; tests unchanged and green.
7. `dipole_novel_findings` mandatory, novelty non-punitive: unchanged.
8. No module or class rebinding on the classroom or EC2 path: verified by reading and by
   `test_classroom_main_has_explicit_host_class_seam_instead_of_global_rebind`.
9. Science drift: none.
10. Defects: one design risk, handled below; no behavioural defect found.

## The one thing to know about this design

The classroom host no longer rebinds `base.ActualHost`, `base.await_recorded_principal` or
`driver.SundayRuntime`; instead it carries its own copies of the lawful host's `run()` and
`main()`. Measured: the copies equal the lawful bodies modulo quote style, layout, two dropped
comments and the named seam (`host_class`, `base.incomplete_output_alert`). That is the correct
trade for a lawful file that must stay untouched, and it is exactly the shape that drifts
silently when the lawful body changes. Added
`test_classroom_run_and_main_are_the_lawful_bodies_modulo_the_named_seam`: an AST-level equality
of both copies against the lawful functions with the seam substituted, the same drift guard the
compact-source host holds over `prefix()`. If the lawful host changes, this fails and the copy is
re-synced by hand.

Also noted, not changed: `make_principal_adapter` still defaults to the base classroom adapter
when no class is supplied (construction compatibility for tests); `SundayExecution.run_cycle`
refuses a missing class before that default can matter on a real cycle.

## For Codex

Integrate from this review branch (it contains the integration tip plus the two tests). The
handoff's integration instructions stand: preserve the recovery and reduction work on
`ccode/frankie-lawful-recovery-review-20260915` (tip `030608e3`, reduction stack `848ffe0d`), keep
the classroom mandatory on every result-bearing path, keep any benchmark exemption harness-local
and fail-closed, and do not reintroduce a broad CI gate (the build dictates the flow; Greg).
