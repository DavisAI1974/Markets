# Markets bridge (Markets-owned; imports odcore)

Where the imported Adaptive Locality engine first meets Markets code, offline and read-only.

- `estimators.py`: the same RawFrames through the frozen-bin estimator (imported package) and through
  Markets' Vasicek entropy + KSG-1 mutual information (`odcore/operators.py`). Each series carries a
  calibration identity that names its estimator; the fitters refuse to mix them.
- `leakage_gate.py`: the imported fitters run through `odcore/leakage.py` (the mandatory pre-backtest gate)
  and through a native whole-frame permutation gate. A deliberately leaking signal proves the gate bites.

- `ng_runner.py`: the Henry Hub NG workflow. One NG day (`event_move_baseline.load_cont_day`, local cache or
  the repo's S3 read-time fetch) -> per-second Lee-Ready buy/sell volumes (as `month_characterize`) ->
  RawFrames -> frozen bins from the day's earliest 30 percent -> both estimators -> archive-first five-step,
  Level 2, static geometry, predictive controls and circular-shift null -> SQLite registries + `summary.json`.
  Settle exclusion 21:00 UTC +/- 1800 s by default. Computes no trade signal; trade cost appears nowhere. See
  `../CODEX_HANDOFF_NG_20261108.md` for how to run it and how to read the output.

Not here: any Frankie connection. Real NG data only through the repo's own loader; the real-day test skips
when no day is cached. Launch stays HOLD.

Run from the Markets root:

    PYTHONPATH=.:research/kalshi/adaptive_wavepacket_20261108/working_tree:research/kalshi/adaptive_wavepacket_20261108/working_tree/tests \
      python3 -m unittest discover -s research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tests -p 'test_*.py'
