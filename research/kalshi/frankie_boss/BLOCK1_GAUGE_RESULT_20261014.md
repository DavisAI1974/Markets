# Block-1 updated-code gauge: passed, October 14, 2026

Greg authorized the gauge, then directed use of another existing box to avoid
the main disks' unfinished performance reductions. No saved-a2 resume was
authorized or performed. No ingestion, ROOT continuation, replacement runner,
extra test framework or 30-day work was run.

Measured source: `88d1e7b8eaa8ed9bc4b6858ec0213f87299dad36`, runtime source
equivalent to the reviewed `805a494` tree. The existing push-code staging receipt
verified all 4,175 checkout files before measurement. The existing
`frankie_box_block_gauge.py` ran the full classroom and external section with
`--day 20231018 --block 1 --evidence-encoding shadow`.

| Measurement | Result |
| --- | --- |
| Rows / original cursor range | 1,588 / [0, 1588) |
| Gauge wall seconds (includes lesson preparation) | 116.626 |
| Classroom session seconds | 90.850 |
| Previously recorded classroom session seconds | 159.0 |
| Session duration reduction versus that recorded number | 42.86% (1.75 times the throughput) |
| Classroom / external status | complete / complete |
| Second set | carried |
| Main / external shadow comparisons | 161 / 12 |
| Encoding mismatches | 0 / 0 |
| Main candidate / legacy encoding seconds | 5.191128 / 13.868717 |
| External candidate / legacy encoding seconds | 3.588250 / 40.483681 |

The 159-second number is the previous recorded session measurement, not a new
legacy rerun. Shadow computes both encoders and returns the legacy bytes; these
times include that comparison work. The candidate-only gauge has not been
measured. Main and external encoding times overlap; do not subtract their sum
from wall time to invent a fast-mode result.

The largest main-session step was external join wait (52.048 seconds).
The external child took 77.146 wall seconds: section 29.503, answers 43.751,
grade/correction 3.769, render 0.003. Main store writes took 4.795 seconds.
The existing external section reproduced the recorded section hash
`052d6fe90ba24d753b3029388105d812ea6644e307e755e0959913f310caecc7`.

## Preserved evidence and state

The original block sidecar hash remained
`40293ae593c91a5ef49c25f484733412feadd8168a25c4fff4f8625e1fc77544`.
The attached day file matched its receipt:
`d006252d605432994909a52e75fcbfe7cec3e42990a98c02e91e1f65212f0bc7`.
All five referenced plane stream files were present at their original complete
sizes. Their original paths, row keys, source pins and clocks remained intact;
no substitute or truncated plane files were created. Original work, brain,
venv and archive were mounted read-only for the gauge.

Raw measurements beside this document:
- `BLOCK1_GAUGE_20261014_88d1e7b.json`
- `BLOCK1_GAUGE_SESSION_20261014_88d1e7b.json`
- `BLOCK1_GAUGE_20261014_88d1e7b.log`

Full gauge output is retained at
`/opt/frankie-box/gauge-block1/88d1e7b-20261014T055854Z/88d1e7b8-20261014T055855Z`
on the second box's own disk (`vol-0fbf7bc0991bc8e39`). This includes the complete
block store, lesson, second-set output, classroom/external outputs and teacher
report. The CPU booking released with exit 0. The original source mounts were
cleanly unmounted afterward.

The main box's original root/archive disks are returned to their original
device mappings; both boxes are stopped and KeepRunning=false. Saved
`e2e-20231018-a2/20231018` remains untouched. Its whole-day classroom still needs
separate explicit authorization to resume. The main box's deployed checkout
was not changed during this gauge; stage the updated source before any later
saved-day execution.

This verifies this block's classroom/external run and the exercised encoder
comparisons. It does not verify ingestion/ROOT streaming, pipeline-wide exact
recovery, unfinished scientific calculations, or the rest of the saved day.
Both local deferred draft branches remain preserved and unintegrated.
