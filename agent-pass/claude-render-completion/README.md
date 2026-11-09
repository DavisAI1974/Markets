# Claude lifecycle render completion

User requested step 1 only: complete all four days and show examples before any later analysis.
Source: `claude/three-day-dipole-20261108`, commit `beb2104c079045c24832f2279eac5e8e69bc576e`.
Saved `x13_life_paths.npz` files supply individual arrays; no raw producer or market analysis is rerun.
Original Claude code and data remain intact. New outputs belong in markets-data.

The renderer preserves the six-panel structure, original array numbering, individual bar intervals, saved operands and original source bytes.
All 21 candidates absent from saved arrays remain explicit pages: 19 seam/warm-up omissions retain their original recognition clocks; two finalization-only records have no live recognition. No quote/book path is invented.
The exact prebirth cutoff is birth boundary minus 1 ns, as defined by x03. Companion ratio and markers retain their own epoch-second labels.
Recognition is read as an integer, never via floating-point CSV conversion.
Unavailable array cells remain NaN with visible bottom ticks. Zero means an observed zero.
First marker delays use timestamp differences, not row offsets. Empty windows and finite loss of one-sidedness are separate markers.
When either flip or empty is unobserved, show the saved array through +1260 and label the unresolved tail. A later observed marker is retained in metadata even when outside the displayed array.
These adjustments are documented rather than represented as byte-identical reproductions of x12 images.

Every candidate page has source row/array row coordinates, original weakening rows, clocks, a hash and per-variable finite/missing reconciliation.
All original saturated-second dispositions are retained in the source ledger, including rejected and suppressed seconds.
The audit independently reads saved arrays and checks row conservation, source identities, recognition clocks, finite/missing counts and PNG integrity.
Daily GitHub Actions artifacts provide each day's folder as a ZIP. Git contains the individual images and provenance.

Run remotely:
`python -m unittest -v test_render_core.py`
`python complete.py --day 20231002 --shard 0 --output results/20231002`
Four disjoint shards cover each day, followed by `python audit.py results`.
