# CLM sidecar (standalone, not wired into Frankie/BOSS)

Greg, 2026-09-28: a quick version that sits by itself, learns from this Monday run and writes outputs, to see whether
a System One decision model (Stanford/NVIDIA CLM-8B on a frozen Qwen3-8B, Apache-2.0) can take Granite's decision
calls. Rough by design. Nothing in the Frankie/BOSS runtime imports it or reads its outputs.

## Where it is meant to go (D51, Greg 2026-09-28)
There is no limit on what this model is asked, direction included: its research is open. A gate or filter on
validated signals is where a System One model STARTS, never a ceiling. Only money is gated, per cell on forward
evidence: GATE, then ADVISOR (predicts beside the incumbent, scored, never acted on), then DECIDER on the cells where it
wins forward (out of sample, net of fee at maker and taker, paper then live). The same path applies to the
trade-execution layer. This sidecar's forecast questions (next move at 60 s and 300 s) are the first ADVISOR-style
scores. One run on one day is an early result: whatever it shows is a scoped finding, and no question or method is
dropped on it (D52). A path is set aside only after all research runs on the historical data.

## What it learns (both question sets, Greg's choice)
All labels are computed by code from the real day's bedrock member rows (one row per F_LAST group). There is no
synthetic data.
- **Forecast**: `next_move_60s`, `next_move_300s`. This is RISE, FALL or FLAT of the book mid, from this group's
  mid to the first group at or after +60 s or +300 s.
- **Classroom-style table reading**: every answer is readable from the state shown.
  - `fill_class` is the fill-disposition class, with the class field hidden from the state.
  - `deeper_side` is BID, ASK or EVEN.
  - `mid_vs_previous` is RISE, FALL or FLAT against the previous group's mid.

The split is by time:
- **Train**: the first 70% of the day. Rows whose forecast window reaches into the test part are purged.
- **Test**: the last 30% of the day.
- **Sample size**: 3,000 train rows and 1,500 test rows (`TRAIN` and `TEST` can change it).

A leakage check (the rule in `odcore/leakage.py`) confirms that the state at row i is unchanged when every later row
is scrambled.

## Methods (scored on the same test rows, reported per session_phase cell as counts)
- `prior`: the train-split majority choice. This is the benchmark.
- `head`: a small softmax head trained on frozen Qwen3-8B embeddings from the train rows. This is the CLM recipe
  in miniature.
- `zero_shot`: the CLM-8B System One typed answer, via `clm-serve`.
- `zero_cal`: `zero_shot` with one temperature per question, fitted on the train rows.

The report includes reliability tables (confidence against right/wrong) and "accept when confident, escalate the
rest" tables.

## How to run (two dispatches of `frankie_box_run.yml`)
1. **Box extract** (read-only on the run). Run script `deploy/aws/box/frankie_box_clm_sidecar_extract.sh`.
   - Optional variables: `STAMP`, `HORIZONS`, `TRAIN`, `TEST`.
   - It prints a manifest with the dataset's S3 key. It uses the box role's host-delivery progress prefix.
2. **GPU Pod** (Greg's go: a new small Pod, always deleted). Run script `deploy/aws/box/frankie_box_clm_sidecar_pod.sh`.
   - Variables: `DATASET_KEY=<key from step 1> STAMP=<same stamp> [MAX_MINUTES=150] [CHECKPOINT_MINUTES=30]`.
   - Every CHECKPOINT_MINUTES the Pod uploads its log, `progress.json` and any outputs so far, and the job prints a
     CHECKPOINT (Pod state, system and container log tail, progress). A Pod that has not started in 30 min is deleted.
   - The runner picks a 40 GB+ GPU in stock, creates the Pod (image `vllm/vllm-openai:latest`) and passes presigned
     URLs.
   - The Pod runs `pod_bootstrap.sh`: vLLM Qwen3-8B pooling on :8090, `clm-serve` on :8700, then `learn.py`.
   - The outputs come back to `s3://frankie-granite42-568968024170-us-east-1/clm-sidecar/<stamp>/out/` and to the run
     artifact, and `report.md` goes to the job summary. The Pod is deleted on success, failure or timeout.

## Known rough edges
- The CLM result format is parsed generically. The first five raw results are saved in
  `zero_shot_raw_examples.json`, so the parser can be fixed after the first run. If `clm-serve` does not come up,
  the run finishes head-only and says so.
- `vllm/vllm-openai:latest` is not pinned. The status marker records the vLLM version that ran.

## Sit-in with Frankie (Greg, 2026-09-28)
Jev sits in with Frankie through the principal's reading and classroom, in two roles, and they talk every few
minutes. Jev writes a report every 30 minutes, so each run leaves something to evaluate.
- **Feed out of the box:** `deploy/aws/box/frankie_box_jev_relay.sh` has its own `jev-relay` lock and runs beside the
  principal. It is read-only on the session.
  - Every `RELAY_SECONDS` (120) it bundles the session's phase, note, progress, `work/classroom/*.json` and each finished
    model call's answer text.
  - Each bundle goes to the next presigned slot, `clm-sidecar/<STAMP>/feed/NNNN.json`. The first bundle also carries the
    request's `dipole_classroom` material.
  - Dispatch with `presign="putrange:frankie-granite42-568968024170-us-east-1/clm-sidecar/<STAMP>/feed:240"`,
    `presign_hours=12`, variables `STAMP=<STAMP> REQUEST_DIRECTORY=<principal request dir>`.
- **Jev's Pod:** dispatch `frankie_box_clm_sidecar_pod.sh` with `SIT_IN_PODS=<reading Pods 2-4>` and a long
  `MAX_MINUTES`. `sit_in.py` runs after learn.py, using Qwen3-8B chat on the Pod. Each turn:
  - the **student** answers Frankie's topic from the dipole material alone;
  - the **observer** compares the two against the material (JSON: agree, disagreements, evidence, question);
  - **Frankie** (Granite on a reading Pod, never the BOSS, jobs_v1) answers the question;
  - the observer closes the turn as settled or open.
- **Reports:** `clm-sidecar/<STAMP>/sit-in/report-NNNN.md` every 30 min, listing every turn individually (never
  averaged), plus `sit-in/transcript.jsonl.gz`.
- **Isolation:** nothing Jev writes goes into Frankie's session. Frankie's replies to Jev are extra Granite calls on the
  reading Pods, which share the slots with the principal's reading.
