# HANDOFF 2026-09-28 16:1xZ -- cycle 0 launch r6 RUNNING (parallel preparation); 4 A100 Pods up (3 calls each); Jev sit-in built

Branch `claude/frankie-monday-cycle-0-urozez`, tip = this commit (code tip `8349a89e`). Previous handoff:
`HANDOFF_20260928_V9_RENDER.md`.

Standing rules:
- No tests: py_compile with python3.12 only. `[skip ci]` on every push.
- No canaries (Greg: "we'll find out when we run it").
- A probe on every long box run.
- Never edit frankie_box_projection.py.
- Keys are secrets.

## RUNNING NOW (probe first)
- **Launch r6**:
  - GitHub run 36448920615, started 16:08:57Z, `frankie_box_cycle0.sh ACTION=launch`, SSM timeout 12 h.
  - Staged code_root: `/opt/frankie-box/code/8349a89e0080ca988b3b8ed855ec7632229418c4-36447858596-1/markets`.
  - Config: `/opt/frankie-box/work/monday-run-config/full-20211004-20260928-r6/actual-host-configuration.json`, sha256
    `b9162c279711364d456ab9534f3f32313db24dd6fdd68ddbff6fdba812f26b9c`.
  - Run dir: `/opt/frankie-box/work/runs/monday-20211004-20260928-r6`.
  - Expected: it prepares the context (the parallel walk below), delivers the priming to the BOSS Pod, then stops at a
    WAIT (exit 3/4 = pending, not failure).
- **Probes** (all have their own locks):
  - `frankie_box_read_log.sh MODE=processes FILE=work/runs/monday-20211004-20260928-r6`
  - `frankie_box_read_log.sh MODE=tail FILE=work/runs/monday-20211004-20260928-r6/host-progress/progress.json`
  - `frankie_box_session_cpu.sh MODE=profile PID=<launch pid>`
- **4 A100 SXM 80GB Pods**, all in US-MD-1 at $1.59/h each (about $6.36/h together), service_ready:

  | Pod | Role | Prepare run |
  |---|---|---|
  | `kqp1qwzv6vo67a` | BOSS | 36433277296 |
  | `x2vprjb4cs2ulu` | reading | 36433876721 |
  | `mhj0jwod7yfdz5` | reading | 36433881239 |
  | `vbh922dqk8x2f9` | reading | 36433885894 |

  - Every Pod boots bundle `a9ab0b8f...` with vLLM `--max-num-seqs 3` (confirmed from each startup record).
  - `/opt/frankie-box/pods.json` = the 4 Pods with `slots: 3`, which gives 12 calls in flight. Fan-out threads are
    pinned one per CPU.
  - No serverless: `serverless.json` is absent on the box, and the canary's serverless path was deleted.

## DONE this chat (commits, in order)
- **Token canary (the last one):** the V9 read is about 55.5M tokens, 639 parts of 87k tokens, 0.564-0.594 tokens
  per byte across 8 slices.
- **/ship on the V9 render:** GO, with fixes applied.
  - render_digest names a moved-aside digest only when its bytes and sha match, and replaces the receipt atomically.
  - stop_cycle matches only a Python interpreter running the script.
- **Principal inputs** (`84b1948e`: the knowledge-base receipt is carried into a new root): output
  `/opt/frankie-box/work/principal-inputs/full-20211004-20260928-v9-r2/principal-inputs-receipt.json`, knowledge base
  57ee8388..., shared knowledge 27f7fdbd..., 0 model calls.
- **3 calls per A100 Pod** (`82883837`):
  - granite_startup.MAX_NUM_SEQS = 3, plus the matching pin in granite_runpod.
  - `pod_prepare --bundle-from-checkout` (workflow input `bundle_from_checkout=true`) stages the checkout bundle and
    sets the 5 env keys on the NEW Pod only.
  - The source Pod fhiwwlouzyx6l2 and the reviewed JSON are untouched; they are the fallback.
- **Jev (CLM sidecar):**
  - `74ab98cf`: checkpoints every 30 min (CHECKPOINT_MINUTES).
  - `45e6a16a`: diagnosis of why his Pod never started. He picked L40S LOW with no data center in stock; he now picks
    only a GPU with in-stock data centers.
  - `27a48dcd`: the sit-in with Frankie.
    - Box relay `frankie_box_jev_relay.sh` (jev-relay lock), feed every 120 s through `putrange` presign slots.
    - `sit_in.py`, two roles: the student answers from the dipole material; the observer compares and questions
      Frankie on a reading Pod (never the BOSS).
    - A report every 30 min, every turn listed individually.
- **1-CPU preparation fix** (`05939e01`, `8349a89e`, parallel_journal.py):
  - r4 spent 50+ min single-core in prime_cache -> context_session._prepare -> journal_prefix.
  - Now the compact-journal walk runs in the block workers: pairing, per-entry hash, and only the 7 fields _prepare
    reads.
  - The teacher's chained content hash uses canonical bytes the workers computed. The first 64 are checked against
    the original.
  - context_session.py, c15_journal.py and c15_teacher_r3.py are unchanged (pinned).
  - Hooked in run_actual_sunday.prime_cache.
- **Cancel fix** (`5792fed9`): a cancelled frankie_box_run.yml run now cancels its SSM command; for a cycle launch it
  also sends stop_cycle.
- **Stopped and replaced:** r4 (single core) and r5 (first parallel version). Their stop receipts are under
  `/opt/frankie-box/receipts/cycle-stop-*.json`.

## OPEN (Greg's calls in brackets)
1. **Probe r6:**
   - Workers busy? Main thread not the bottleneck?
   - Watch the phase leave `boss_reasoning`, then the priming reach the BOSS, then the WAIT.
2. **Still sequential by design:** the teacher's running normalizer and its per-instrument windows (64/1024 groups).
   Not measured. They could be split per instrument if they prove to be the long pole.
3. **Two passes:** the pinned _prepare walks for context and the teacher walks again. Merging them into one walk means
   changing _prepare (a re-pin). [Greg]
4. **At the WAIT, the principal and Jev start together** (Greg: "I'm fine if you release together"):
   - Principal: `frankie_box_cycle0.sh ACTION=principal CALCULATIONS=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48 REQUEST_DIRECTORY=<from the launch WAIT output>`.
   - Relay: `frankie_box_jev_relay.sh` with `presign="putrange:frankie-granite42-568968024170-us-east-1/clm-sidecar/<STAMP>/feed:240"`,
     `presign_hours=12`, `STAMP=<STAMP> REQUEST_DIRECTORY=<same>`.
   - Jev Pod: `frankie_box_clm_sidecar_pod.sh DATASET_KEY=clm-sidecar/monday-20260928a/dataset.jsonl.gz STAMP=<STAMP> SIT_IN_PODS=x2vprjb4cs2ulu,mhj0jwod7yfdz5,vbh922dqk8x2f9 MAX_MINUTES=600 CHECKPOINT_MINUTES=30`.
   - Probe the principal throughout.
   - Then record initial, resume 1, correction, record correction, resume 2, retain (MONDAY_CHECKLIST_20260927.md).
5. **Retained-preparation reuse:** once r6 writes its prepared request, point future cycle-0 configs'
   `retained_preparation_recovery` at it so reruns skip the walk.
6. **Review follow-ups not taken:**
   - Environment approval on frankie_box_run.yml (anyone who can push a branch can run a script on the box).
   - No tests for render, stop and canary (per Greg).
