# Markets bridge (Markets-owned; imports odcore)

Where the imported Adaptive Locality engine first meets Markets code, offline and read-only.

- `estimators.py`: the same RawFrames through the frozen-bin estimator (imported package) and through
  Markets' Vasicek entropy + KSG-1 mutual information (`odcore/operators.py`). Each series carries a
  calibration identity that names its estimator; the fitters refuse to mix them.
- `leakage_gate.py`: the imported fitters run through `odcore/leakage.py` (the mandatory pre-backtest gate)
  and through a native whole-frame permutation gate. A deliberately leaking signal proves the gate bites.

Not here: any real market data, any Frankie connection, any AWS call. Launch stays HOLD.

Run from the Markets root:

    PYTHONPATH=.:research/kalshi/adaptive_wavepacket_20261108/working_tree:research/kalshi/adaptive_wavepacket_20261108/working_tree/tests \
      python3 -m unittest discover -s research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tests -p 'test_*.py'
