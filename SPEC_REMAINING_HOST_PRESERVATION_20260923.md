# Remaining host preservation transactions — 2026-09-23

Objective: close interruption/replay gaps in the existing principal-response and whole-cycle helpers. Retain their distinct scopes and completion receipt fields, all request-independent evidence, and their SSM interface. Cycle 0 remains held.

Capabilities: response preservation and whole-cycle preservation depend on the same filesystem transaction protocol already used by code-bound preservation. They remain self-contained script payloads because ssm_run_ps1 sends a single script verbatim. No installed host helper/module is assumed.

Scope: deploy/aws/host/frankie_host_supersede_principal_response.ps1, frankie_host_supersede_cycle.ps1, a small foreign-intent guard in frankie_host_supersede_code_bound_state.ps1, existing workflow contracts, tests/test_host_remaining_preservation.py, and existing focused host CI.

Assumptions: the operator-selected day/run configuration is retained and immutable throughout a transaction; source data is not concurrently written. Process inventory must be evaluable and show no runner. All helpers serialize via the normalized day/code-bound-state.lock. Another unfinished transaction family refuses before any move; no helper silently resolves another family's intent.

Acceptance:
1. Normalize paths; reject reparse ancestors and selected descendants. Stream hashes into complete manifests including empty/hidden directories and the response post-grade.
2. Bind intent to day, run ID/path, cycle, reason, configured boss commit, configuration SHA256, allowed source scope, exact unique destination, and full manifests. Flush a create-new pending JSON and atomically publish before any move.
3. Replay pending intent before deciding that no response/cycle remains. Preflight every source/destination and every retained move receipt, rejecting changed, missing, duplicate, ambiguous, out-of-scope, or conflicting state before further moves.
4. Verify each moved item against its original manifest; flush per-move receipts and final completion linking the intent hash. Never replace existing evidence; same-second generations are unique. Pending partial JSON remains for diagnosis.
5. Keep completed Classroom evidence and accepted principal output protected. Whole-cycle also refuses recorded responses. Evaluate these gates against retained source or already-preserved cycle during replay. Missing/malformed database or failed process enumeration refuses. Never stop a runtime.
6. Preserve workflow variables; add explicit Python input/--set to the whole-cycle workflow for its read-only principal_output gate, matching the response workflow default. Process/SQLite access uses no secrets.
7. Shared-lock foreign-intent checks validate completion schema, intent path, and hash before treating a foreign transaction as complete. The code-bound helper participates without changing its existing selection protocol.

Style: small named PowerShell functions; literal paths; ordered receipt objects; UTF8 no BOM and explicit JSON depth; no new production fault-injection switches.

Commands, from tests:
python -m pytest test_host_remaining_preservation.py test_host_state_preservation.py -q --rootdir=. --confcutdir=. --noconftest -p no:cacheprovider
Existing host-script contract command remains in .github/workflows/frankie_host_scripts_ci.yml.

Plan: land tests/spec for remote RED; implement scripts and narrowly adapt text assertions; isolated remote GREEN; independent ship review before any staging. Root owns integration/CI. Tests substitute only process inventory and interruption boundaries and use real PowerShell moves, hashes and SQLite in temporary Linux directories. They do not establish native Windows execution or actual process absence.

Always retain evidence and explicit inputs. No local/C:/E: access, live host/SSM dispatch, model calls, source replay/ingestion, runtime stop/start, bootstrap changes, or deletion. Native Windows validation and runtime admission remain gated separately.
