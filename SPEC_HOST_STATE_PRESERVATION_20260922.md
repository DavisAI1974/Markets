# Durable host-state preservation repair

Scope: Root/Granite continuation on codex/trading-day-readiness-20260922.
Starting revision: 45b8e90d9d5958ad9138a0e3dc753951a4ba0f44.
CHAT12, CHAT15 and SHIP_REVIEW_CLASSROOM_COMPLETE_20260922.md govern this work.

## Objective and acceptance

The host supersede script must preserve every selected code-bound artifact with a
durable pre-move intent and verifiable receipts, including after interruption.
Existing stale-identity selection and kept-artifact rules remain.

1. Validate full paths using directory boundaries and reject reparse points in
   every existing ancestor, selected item and selected directory descendant.
2. Inventory all selected files and directories before any move. Record SHA256,
   byte counts, relative paths and original root modification times. Hash files
   with bounded buffers rather than reading full SQLite databases into memory.
3. Flush a create-new intent before the first move. Serialize invocations with an
   exclusive file handle. Never replace existing intents, receipts or destinations.
4. On retry, reconcile unfinished intents before consulting identities that may
   already have moved. Verify planned bytes at source or destination; refuse
   missing, changed, duplicate or ambiguous state. Bind run, day, cycle and exact
   current commit. A pending plan for another commit or cycle must not be ignored.
5. Flush each move receipt and a final completion receipt binding the intent hash.
   A failure must leave sufficient evidence to resume or diagnose without deleting
   or relabeling historical evidence. Fresh transactions use unique destinations.
6. Preserve host-instance, native runtime, verified records, chained journals and
   other cycles. Never start/stop/dispatch a runtime from this helper.

## Structure and style

Implementation: deploy/aws/host/frankie_host_supersede_code_bound_state.ps1.
Behavioral regressions: tests/test_host_state_preservation.py.
Existing contracts: research/kalshi/frankie_boss/tests/test_host_supersede_code_bound_state.py.
CI: existing host-script workflow, isolated ubuntu runner with PowerShell and Python.

Use small named PowerShell functions, literal paths, ordered receipt maps and
explicit fail-closed checks. Retain the existing SSM variable contract and existing
FRANKIE_CODE_BOUND_STATE_SUPERSEDED_V1 receipt fields; add intent linkage and full
manifests. No configuration, mathematical targets or market records change.

## Plan and verification

- [ ] Commit isolated behavioral regressions and observe the intended failures.
- [ ] Implement path validation, full pre-move plans, interruption reconciliation,
      exclusive execution and durable receipts; update obsolete text-only assertions.
- [ ] Run behavioral tests and existing host-script contracts remotely.
- [ ] Run parallel code, security and test /ship reviews; resolve required findings.
- [ ] Record exact source revision, CI results, limitations and remaining launch gates.

Behavioral test command, from tests:
python -m pytest test_host_state_preservation.py -q --rootdir=. --confcutdir=. --noconftest -p no:cacheprovider

Existing contract command is retained in .github/workflows/frankie_host_scripts_ci.yml.
Tests exercise actual PowerShell on temporary Linux fixture files. They do not
execute on the native host, contact providers, or prove native Windows execution.
Inject interruption only through the test harness, never production switches.

## Boundaries and deployment

Remote GitHub APIs and authorized isolated Linux CI only. No local filesystem or
shell, no ingestion restart/source replay, no canary, no native runner/Pod/EC2 stop,
no pinned Pod bootstrap edits, no evidence deletion, no key exposure or output
truncation. Preserve market JSON bytes and exact integers.
Classroom remains complete; exclude this unrelated host-contract test file from
its broad push path so focused host repairs do not reopen settled Classroom tests.
Existing tasks/plan.md and tasks/todo.md contain historical unfinished work and
remain intact; this dated document follows CHAT14's instruction to preserve root
planning documents and use dated additions.

Cycle 0 and the new run remain held until the owner's final workflow task is
completed. This repair is not deployment approval for an otherwise incomplete
configuration. On failure, hold the runtime and reconcile the retained intent;
never automatically move artifacts back or revert to the unsafe helper.
