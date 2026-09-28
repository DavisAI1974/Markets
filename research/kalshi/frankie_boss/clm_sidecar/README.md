# CLM sidecar (standalone, not wired into Frankie/BOSS)

Greg, 2026-09-28: a quick version that sits by itself, learns from this Monday run and writes outputs, to see whether
a System One decision model (Stanford/NVIDIA CLM-8B on a frozen Qwen3-8B, Apache-2.0) can take Granite's decision
calls. Rough by design. Nothing in the Frankie/BOSS runtime imports it or reads its outputs.

## Where it is meant to go (D51, Greg 2026-09-28)
A gate or filter on validated signals is where a System One model STARTS, not where it ends. It is meant to learn and
be promoted per cell on forward evidence: GATE, then ADVISOR (predicts beside the incumbent, scored, never acted on),
then DECIDER on the cells where it wins forward (out of sample, net of fee at maker and taker, paper then live). The
same path applies to the trade-execution layer. This sidecar's forecast questions are the first ADVISOR-style scores.

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
   - Variables: `DATASET_KEY=<key from step 1> STAMP=<same stamp> [MAX_MINUTES=150]`.
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
