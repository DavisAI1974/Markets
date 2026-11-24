# OD Autoresearch

Autonomous hyperparameter optimization for Operator Discovery.
You are an autonomous researcher. You modify, run, score, keep or discard, and repeat — indefinitely until a stop condition is met.

## Setup

To set up a new experiment run, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `apr6`). The branch `od-autoresearch/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b od-autoresearch/<tag>` from current master.
3. **Read the in-scope files**:
   - `README.md` — repository context.
   - `od_engine.py` — the OD recovery engine. **READ-ONLY. Do not modify.**
   - `od_config.py` — the file you modify. All tunable hyperparameters live here.
   - `benchmark.py` — fixed benchmark evaluation. Runs OD recovery against the benchmark dataset and returns R², residuals, and runtime. **READ-ONLY. Do not modify.**
   - `benchmark_data/` — fixed benchmark datasets. **READ-ONLY.**
4. **Verify benchmark data exists**: Check that `benchmark_data/` contains at least one dataset. If not, tell the human.
5. **Initialize results.tsv**: Create `results.tsv` with just the header row. The baseline will be recorded after the first run.
6. **Confirm and go**: Confirm setup looks good. Once you get confirmation, kick off the experimentation.

## What You Modify

`od_config.py` is the ONLY file you edit. It contains all tunable parameters. Everything is fair game:

### Primary Knobs (OD Critical Path)
- `lambda_physics` — physics loss weighting (balance data fit vs. physics constraints)
- `learning_rate` — base learning rate
- `lr_schedule` — learning rate schedule type and parameters (warmup, decay, cycling)
- `attention_sparsity` — sparsity level in attention over modes
- `spectral_fft_settings` — FFT window, overlap, normalization for spectral decomposition
- `positional_encoding` — type (sinusoidal, learned, rotary) and parameters
- `latent_dim` — VAE latent space dimensionality
- `n_modes` — number of spectral modes to retain
- `residual_connections` — depth and type of residual connections
- `temperature` — softmax temperature for attention

### Secondary Knobs
- `batch_size` — samples per training step
- `n_epochs` — training iterations (within time budget)
- `optimizer` — optimizer type and parameters (Adam, AdamW, Muon, etc.)
- `weight_decay` — regularization strength
- `gradient_clip` — gradient clipping threshold
- `dropout` — dropout rate
- `activation` — activation function (ReLU, GELU, Swish, etc.)

## What You Cannot Do

- Modify `od_engine.py`. It is the core OD recovery engine. Read-only.
- Modify `benchmark.py`. It is the fixed evaluation harness. Read-only.
- Modify anything in `benchmark_data/`. The datasets are fixed.
- Install new packages or add dependencies.
- Modify the evaluation metric. R² from `benchmark.py` is ground truth.

## The Metric

**Primary: `r_squared`** — higher is better. This is the R² score of the recovered operator against ground truth on the benchmark dataset.

**Secondary (logged but not optimized against):**
- `r_squared_holdout` — R² on the 20% holdout split (falsification check)
- `residual_mean` — mean absolute residual
- `residual_max` — maximum absolute residual
- `runtime_seconds` — wall clock time for recovery
- `peak_memory_mb` — peak memory usage

**Tiebreaker:** If two configurations achieve the same R² (within 0.0001), prefer:
1. Lower runtime (faster is better)
2. Lower memory usage
3. Simpler configuration (fewer parameters changed from baseline)

## Output Format

`benchmark.py` prints a summary:

```
---
r_squared:        0.997200
r_squared_holdout: 0.995100
residual_mean:    0.001200
residual_max:     0.012300
runtime_seconds:  1.450
peak_memory_mb:   512.3
n_points:         1000
dataset:          spin_boson_001
```

Extract the key metric:
```
grep "^r_squared:" run.log
```

## Logging Results

Log every experiment to `results.tsv` (tab-separated, NOT comma-separated).

Header and columns:

```
experiment	commit	r_squared	r_squared_holdout	runtime_s	memory_mb	status	description
```

1. Experiment number (sequential, starting at 1)
2. Git commit hash (short, 7 chars)
3. `r_squared` achieved — use 0.000000 for crashes
4. `r_squared_holdout` — use 0.000000 for crashes
5. Runtime in seconds, round to .3f — use 0.0 for crashes
6. Peak memory in MB, round to .1f — use 0.0 for crashes
7. Status: `keep`, `discard`, or `crash`
8. Short text description of what this experiment tried

Example:

```
experiment	commit	r_squared	r_squared_holdout	runtime_s	memory_mb	status	description
1	a1b2c3d	0.993200	0.991000	1.850	512.3	keep	baseline
2	b2c3d4e	0.995400	0.993100	1.720	515.0	keep	increase lambda_physics to 0.8
3	c3d4e5f	0.994100	0.992000	1.900	510.1	discard	switch to GELU activation
4	d4e5f6g	0.996800	0.995200	1.650	520.0	keep	add rotary positional encoding
5	e5f6g7h	0.000000	0.000000	0.0	0.0	crash	latent_dim=256 (OOM)
```

## The Experiment Loop

LOOP:

1. Look at the git state: the current branch/commit
2. Formulate a hypothesis. Write it as a one-line comment at the top of `od_config.py`:
   `# HYPOTHESIS: Increasing lambda_physics should improve R² by strengthening physics constraints`
3. Modify `od_config.py` with the experimental change
4. `git commit -am "experiment: <short description>"`
5. Run: `python benchmark.py > run.log 2>&1`
6. Read results: `grep "^r_squared:\|^r_squared_holdout:\|^runtime_seconds:\|^peak_memory_mb:" run.log`
7. If grep output is empty → crash. Run `tail -n 50 run.log` for the stack trace. Attempt a fix (max 3 attempts), then give up and move on.
8. Record results in `results.tsv`
9. If `r_squared` improved → **KEEP**. Advance the branch.
10. If `r_squared` is equal or worse → **DISCARD**. `git reset --hard HEAD~1` to revert.
11. Check stop conditions (see below).
12. If no stop condition met → continue to next experiment.

## Time Budget

Each experiment should complete within 15 minutes (the OD incremental validation chunk size). If a run exceeds 20 minutes, kill it and treat as a crash.

Run a 2-minute canary before any experiment that changes architecture-level parameters (latent_dim, n_modes, activation). If the canary crashes or looks wrong, skip the full run.

## Experiment Strategy

Start with the highest-impact knobs first (from the OD Critical Path):

**Phase 1 — High-Impact Singles (experiments 1-15)**
Try each primary knob in isolation. Change one thing at a time. This establishes which knobs matter most for this benchmark dataset.

**Phase 2 — Combinations (experiments 16-30)**
Combine the top 3-5 knobs that produced improvements. Test pairwise and triple combinations.

**Phase 3 — Fine-Tuning (experiments 31-50)**
Narrow the search range around the best configuration. Smaller increments, fine-grained tuning.

**Phase 4 — Wild Cards (experiments 51+)**
Try more radical changes: different optimizers, unconventional learning rate schedules, aggressive spectral settings. High risk, high reward.

If you feel stuck at any phase, skip ahead to the next one. If you're stuck everywhere, re-read the in-scope files for new angles, try combining previous near-misses, or try reversing a previously discarded change in combination with a kept one.

## Stop Conditions

Unlike Karpathy's original, this loop has automatic stop conditions. **You do not need to run forever.** Stop when ANY of these are true:

1. **Convergence**: No improvement in 10 consecutive experiments. The configuration has plateaued — further random search is unlikely to help.

2. **Max experiments**: 100 experiments completed. Diminishing returns beyond this point for a single benchmark dataset.

3. **Target reached**: `r_squared >= 0.9999`. You've effectively hit the ceiling.

4. **Sustained crashes**: 5 consecutive crashes. Something is fundamentally broken — stop and report.

5. **Time limit**: 8 hours wall clock from first experiment. Safety valve for overnight runs.

When a stop condition is met:
1. Log which condition triggered the stop in `results.tsv` as a final row with status `stop`.
2. Write a `SUMMARY.md` file containing:
   - Total experiments run
   - Total kept / discarded / crashed
   - Best configuration achieved (full `od_config.py` contents)
   - Best R² and all secondary metrics
   - Top 5 most impactful changes (ranked by R² improvement)
   - Top 3 changes that surprisingly didn't help
   - Recommended next steps
3. Commit `SUMMARY.md` to the branch.
4. **STOP.**

## Post-Run

The human will review `results.tsv` and `SUMMARY.md` in the morning. The best `od_config.py` is already on the branch as the latest commit. If the results are good, the human merges the branch to master. If not, the branch is archived for reference.

## Critical Rules

- **Falsification first**: Every experiment is a falsifiable hypothesis. If the hypothesis is wrong, discard and move on. No narrative protection.
- **One change at a time** (in Phase 1): Isolate variables so you know what caused the improvement.
- **Log everything**: Every experiment gets a row in `results.tsv`, even crashes.
- **Never modify read-only files**: `od_engine.py`, `benchmark.py`, and `benchmark_data/` are sacred.
- **Git is your safety net**: Every experiment is a commit. Every discard is a reset. You can always get back to a known good state.
- **Do not ask the human**: Once the loop begins, you are autonomous. The human may be sleeping. Run until a stop condition is met.
