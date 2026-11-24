# April 5 OD autoresearch handoff

Copies of the April 5 Operator Discovery autoresearch program and its own notes.
Source: `E:\od_autoresearch`, branch `od-autoresearch/apr5`.
Source commit: `a164b68f318c6c2dda46c95ad920b011c3ce6479`.
The originals remain in place and were not edited. This folder contains only source and notes, with no datasets, SENTINEL or crypto files, credentials, caches, or inherited Git history.

## Files

- `od_autoresearch.md`: autonomous search instructions and stop conditions; an agent-run procedure rather than a standalone search script.
- `od_engine.py`: Liouvillian recovery engine.
- `benchmark.py`: evaluation harness, including `load_dataset(path)`.
- `od_config.py`: full winning settings, unchanged.
- `SUMMARY.md`: the original April result write-up, unchanged.
- `results.tsv`: original 14-experiment log and stop row; gitignored in the source.

The five tracked files match the April branch after Git newline normalization. All six copied files are byte-identical to the originals; SHA-256 values are below.

## Complexity and penalty settings

This April branch has no explicit model-complexity, AIC, BIC, or segment-count penalty. The search instructions use simplicity as the third tiebreaker, after runtime and memory, for R-squared values within 0.0001. The experiment-loop section separately says to discard equal or worse R-squared; both original statements remain unchanged.

`ml_regularization = 0.0` and `ls_regularization = 0.0`: both Tikhonov penalties are disabled. Winning settings: `recovery_method = "least_squares"`, `ls_margin_frac = 0.01`, `ls_diff_order = 2`, `n_segments = 8`, `segment_overlap = 0`. `weight_decay = 1e-4` is in the future-engine placeholder section and is not consumed by this engine. No missing complexity-penalty setting was invented.

## Historical results and limits

The original summary reports R-squared 0.999997 and last-20-percent R-squared 1.000000 on one 401-point spin-boson trajectory. These are historical reported scores. The engine fits on the full trajectory before the benchmark scores its last 20 percent; that score is not an independent held-out fit. Piecewise reconstruction also restarts from the observed state at each segment boundary. The original summary is preserved as written.

## Running with your own data

Requires Python, NumPy, and SciPy. No datasets are shipped. The original CLI expects trusted `.npy` files in a `benchmark_data` directory beside `benchmark.py`, then runs with `python benchmark.py`. Alternatively use `benchmark.run_benchmark(path)` with an explicit path. The loader accepts dictionary-in-NPY or raw `(n_t, 5)` complex arrays (time then four density-matrix elements). It uses `allow_pickle=True`; dictionary-in-NPY files must be trusted.

## Handoff verification

The copied code was run read-only against the original local 401-point spin-boson benchmark, without copying that dataset into this folder. It reproduced R-squared `0.999996625981029` and last-20-percent R-squared `0.999999984343204` (rounded: `0.999997` and `1.000000`). Python syntax, the exact seven-file allowlist, copy hashes, and exclusion/credential-pattern checks passed.

## Source discovery

`E:\information_layer` currently contains only consciousness result artifacts; `F:\Factory\knowledge\information_layer` is absent. The exact branch was located at `E:\od_autoresearch` via its April 5 session handoff. That broader handoff is omitted because it covers unrelated projects. E: was full, so copies were placed in this single folder on F:.

## SHA-256 of original copies

| File | SHA-256 |
|---|---|
| `od_autoresearch.md` | `50b8b8c6cf80e2abeef78e4ea9d6d4acc481f645fcf21a0303c717ad6227d61f` |
| `od_engine.py` | `f5b7999b1b74671549afffc9fc45f5e6ecc29e47ce277325608c5ae334b81e67` |
| `benchmark.py` | `225ebfdfd389ccfe502fd5683063a34a5b58e7fc3a49e985a4463b9ecb83fae9` |
| `od_config.py` | `2d5a0175706f87affc5d023135cc0ddc8a9c072bc063f18b5e33a03137b69b46` |
| `SUMMARY.md` | `9434f46444b60379f3ee4d9188a5bb29820041c3675e731d3f4a9eebb9700a9c` |
| `results.tsv` | `47c2ef76461968f810ffed33c6581f1eaf71b9bff27f69262f80dbcdddaa4564` |
