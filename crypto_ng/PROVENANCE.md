# Crypto and ng: where every file came from

Source: `DavisAI1974/Markets`, branch `claude/davisai-s71-counterparty-capacity-sf1168`, commit
`75b15fa10193fab218b6469e5e5f0f49359880e1` (2026-07-07, "S71 close").

| File here | File there | git blob id there | Same? |
|---|---|---|---|
| `program/flip_detector.py` | `odcore/flip_detector.py` | `8d0ff2f0e9c7bfda7550becf781bd6690f873eeb` | byte for byte |
| `program/swing_maker.py` | `odcore/swing_maker.py` | `3ea61f3eb3bcf0bed07e51fcc964d1040ead900d` | byte for byte |
| `program/info_dipole.py` | `odcore/info_dipole.py` | `c04751cbe5f92952e33328f6c04fcae6392e05e5` | byte for byte |
| `program/platform.py` | `odcore/platform.py` | `5b299d7b00ab5b1dacde449285e8081dc98812a4` | lines 40 to 42 only: `from odcore.` became `from crypto_ng.program.` |

`ng.py` is new. It holds the natural gas row and the few lines of the July scripts that are not part of the
program, each copied with its source named beside it:
- `rolling_imb`: `research/shape_s71/arc_gate.py` lines 39 to 44, unchanged.
- `PRE_SEC, POST_SEC, SMOOTH_SEC = 45, 60, 20` and the cut of one trade's arc: `research/shape_s71/regroup2.py`.
- `last_in` (a book figure takes the last value in each tenth of a second and is carried forward):
  `_birth_probe.py`, inside `to_grid`.
- the half spread (the middle of spread over mid, every 50th record, halved): `_liquidity_dive.py`,
  `median_spread_bps`.

The natural gas row is sol's row with the name changed (Claude's call, stated to Greg, his to change): turn amount
0.10, no early entry, no stop, a wait of 300 cells (30 seconds), first in line, the close improved by 0.5 bps. The
other four crypto rows carry numbers set on those coins' own results.
