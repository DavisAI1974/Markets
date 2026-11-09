# Lifecycle data links

This packet attaches Claude's four-day lifecycle renders and timing records to the existing Native whole parents, candidate controls, detector comparisons, original figure pages, trade overlaps and pressure/family/leg links.

No new reverse-engineering or market reanalysis is performed. The user explicitly skipped the remaining reverse-engineering work. Original data is unchanged; source bytes and revisions are hashed.

## Read this first
- `YYYYMMDD/instance-pins.json.gz`: one record per archived candidate, exact identities, original render metadata, whole parent, paired controls, source table selectors and clocks.
- `YYYYMMDD/sample-clock-pins.npz`: the saved Claude array row order and -60..+1260 boundary grid. Sample-cut clocks and native-flow labels differ by one nanosecond by construction. Native completed-second known-by clocks are a separate reference, not replacements for Claude's quote/flow construction. Missing source indices/clocks are -1 sentinels.
- `YYYYMMDD/signal-links.parquet` and `trade-links.parquet`: original event rows with their clocks plus parent links, source row ordinals and external-context indices. Retrospective leg/lifetime links remain navigation, not information claimed available earlier.
- `YYYYMMDD/detector-ledger-crosswalk.json`: saved Claude approximation beside the existing exact Native-action reconstruction. No emulator is rerun.
- `YYYYMMDD/clock-differences.json`: original clock disagreements retained explicitly.
- `99-layer-attachments.json`: applicable observed-field links, with every other registry layer explicitly context-only. A layer link does not claim full book depth or completed runtime functionality.
- `external/`: all 13 original point bindings, 48 source series and their publication histories. Context indices select the last publication no later than the particular clock; ties use last original order. INVALID/MISSING stays as recorded. Target dates are not shifted to fit earlier days, and declared publication clocks are not proof of live receipt.
- `informational/`: original notes, averaged/informative CCode renders, latest Tier-2 charts and the original figure index. These support reasoning but are not relabelled time-available event measurements.

Each external context index selects a row in `external-contexts.npz/previous_original_index`; its 48 integers index the original `series[i].known` arrays in `original-external-series.json.gz`. -1 means no original publication available. The original numeric state, reason, target day and value remain authoritative.

For sample intervals, the two boundary cuts specify (left,right]; external-at-sample-cut is clock context only. The first-event aggressor marker identifies an interval's left boundary, and its right boundary is also attached. Quote/size first events are sampled boundaries; raw structural events keep their own different definition.

Every missing-array candidate still has an instance record. Do not treat missing saved paths as absent events or invent recognition for finalization-only records. Source populations remain separate; this identity join concerns the archived 741/833/741/863 candidates, not CCode's independent full-session detections.

The broader earlier 99/13 pinning backlog is not silently declared complete by this packet; this publication covers these lifecycle records, their boundary grids and the linked event records. Original unclocked summaries remain informational.

Run remotely:
`python -m unittest -v test_links.py`
`python link.py --output results`
