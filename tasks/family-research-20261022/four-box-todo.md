# Add the two existing 32-core boxes

Authorized by the user: "get them going too". Existing A/B fits continue.
Use AWS plugin SSM only. No AI agents, monitors, chats or live orders.

1. [x] Preserve Search and boot C/D cleanly. Acceptance: stopped original Search roots
   retained without writes; same existing instances boot clean Ubuntu roots with
   one frozen-input clone each, no copied services. Verify EC2/SSM/mount receipts.
2. [x] Extend ownership and transfer to four boxes. Acceptance: exactly63 unique
   cohorts; all registered, completed, preparing and active work stays on A/B;
   only untouched work can move; C/D have32 slots each. Verify focused tests.
3. [x] Adopt A/B into the new ownership. Acceptance: all current numerical PID/start
   tokens, CPU leases and reports preserved; one coordinator per box; both ready
   before C/D dispatch. Verify fresh manifests and compact worker receipts.
4. [x] Run C/D and verify. Acceptance: no duplicate task/CPU keys; memory admission uses
   actual availability and unlimited job caps; all four owners disjoint; no raw
   input rebuild/runtime downloads. Verify runtime worker counts and ownership.
5. [ ] Preserve checkpoint and finalize after mandatory work completes. Acceptance:
   all four artifact/key sets join once, original PCA/postprocessing once, failures
   and unfavorable/reproducibility evidence retained, NOT_PASSED explicit.

Dependencies: 1 and2 precede3;3 precedes4;4 precedes5. No further machine creation
or lifecycle changes beyond these two starts and reversible boot isolation.

Activation verified20:51:34 UTC: A95/B88/C32/D25 active fit workers,240total,
760 committed, no duplicate task/CPU keys or host OOM kills. Configured capacity256.
All192 adopted jobs accounted for; no fit restart. Linux26/26 focused tests pass.
Checkpoint saved; final numerical reconciliation/PCA/postprocessing remain pending.
