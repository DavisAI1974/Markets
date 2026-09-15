# Retained Pod, prepared request and storage preflight

Read-only checks on 2026-09-15, approximately 09:08–09:11 UTC. No Pod
mutation, model call, tokenizer execution, active database read or storage move.

## Established

- Live Runpod GET returned retained Pod `jvs75m56w8f73q`, status `EXITED`, one
  `NVIDIA L40S`, reported cost `1.09`, and the expected pinned vLLM image digest
  `18998be4e1276d4eb6e98afe80798aa357c1cc37545150de5c210bc9111beb1d`.
- Its persistent mount remains `/opt/ml`, size `50` as reported by the API.
  No model files were opened or rehashed on the stopped Pod. Stored manifest
  environment pin remains `adf5304a845900b4395c2593c5d270ae727867cc9a164132510acb95d5a3091a`.
- The stopped Pod still carries the historical 4096 context/bootstrap settings.
  The new 131072/jobs_v1 package has deliberately not been applied yet. The
  reviewed retained prepare guard refuses this old configuration before start;
  the exact rollout remains an actual-launch step.
- Current prepared request bytes and admission receipt reconcile: SHA256
  `07cc305a5bf7aff15517122624f8337b5f2fc483ff74f74a4c50e3a7365ca770`,
  151132 bytes, retained measured input92427 and physical remaining output38645.
  Comparing complete parsed old/current requests found only `max_tokens`
  changed. No tokenization or inference was repeated.
- E: free bytes at storage check:285601693696. Current source file metadata
  reports11699789824 bytes. Eighteen copies at that full size would occupy
  210596216832 bytes, below current free space. This is a capacity comparison,
  not an exact forecast of snapshots, SQLite transient files or later checkpoints.
- C: free bytes at the same check:1259958272. New large run and snapshot outputs
  remain assigned to E:. Existing user-deferred storage work was not resumed.

## Remaining execution evidence

Final source/schedule/lineage and nineteen-prefix receipts remain pending.
The actual host must bind its exact prepared bytes, attach its live probe, and
emit admission before staging/start. The stopped Pod must receive the exact
reviewed configuration and fresh bootstrap capabilities. Live startup must
verify model/runtime identity and readiness. Local retained token admission is
not a live vLLM token-count proof. Completion, output quality, Frankie feedback,
learning and run-bound cleanup remain unexecuted and unclaimed.

Supporting receipts: FINAL_RETAINED_POD_READ.json and
FINAL_RETAINED_REQUEST_PREFLIGHT.json. Separate final-v3 package reconciliation,
source-prerequisite and GitHub workflow-readiness reports record their scopes.
