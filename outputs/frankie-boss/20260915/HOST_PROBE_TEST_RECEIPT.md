# Actual host probe wiring verification

Host bytes after the final explanatory docstring: SHA256 `761eecae29297184b55cadb1ee5a4310ff19de9901d40e19a4f50e0d9a5a8ce0`.
Repository and external authoritative host copies match.

Executed once with `C:/Python313/python.exe`, TEMP and TMP set to this E: host-work directory and PYTHONDONTWRITEBYTECODE=1:

`python E:/Codex/Frankie-BOSS-20260915/host-work/test_actual_host_probe_wiring.py`

Observed console result:

```text
test_diagnostic_failure_does_not_replace_primary_alert ... ok
test_main_attaches_before_host_and_both_callbacks_are_wired ... ok
test_real_probe_allowlists_and_lifetime ... ok
test_waiter_observes_without_dispatch_and_retains_lock_protocol ... ok
Ran 4 tests in 0.479s
OK
```

These tests import only the host and existing progress module via importlib, exercise real probe file persistence/thread lifecycle, and use synthetic principal files. No native imports, model, source database, cloud or account actions occurred. `git diff --check` for the host passed.

After that single successful execution, the test was copied into `research/kalshi/frankie_boss/tests/test_actual_host_probe_wiring.py` with only portability substitutions: repository root derived from the test file and temporary paths using the environment default. The relocated copy was not rerun. Original E: test retained. The final host-only docstring adds no behavior and was not followed by repeated tests.

The probe attaches before ActualHost construction, observes controller/coordinator/preparation/principal/job boundaries, and remains advisory. Injected diagnostic failure preserves the exact primary exception and emits one fixed secret-free warning. Possible-stall warnings do not stop or retry work. Job transitions retain only allowlisted phases and hexadecimal identities; durable operation journals remain authoritative.
