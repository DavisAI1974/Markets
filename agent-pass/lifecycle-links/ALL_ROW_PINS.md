# Complete source-row timestamp pin index

This describes the retained-table clock attachment pass. Completion is established by the published SUMMARY.json and successful workflow, not by this document. No reverse-engineering or market reanalysis is performed.

The 553 files are a provenance inventory, not 553 independent studies or required analytical inputs. The completed lifecycle packet below is the primary entry point. This broader sidecar index checks remaining timestamped records for coverage. Historical exports and existing pin ledgers overlap; do not add their row counts as unique observations. Aggregate or unclocked tables remain supporting information rather than timed event evidence.

- Each date/cross shard has CATALOG.json, SUMMARY.json, SOURCES.json and rows/<table_id>/TABLE.json plus numbered Parquet parts.
- All 553 immutable input files have a table ID and source revision/path/blob hash/byte size/SHA256. All original rows retain their zero-based source row ordinal and stable source-record ID.
- Every extracted absolute clock retains integer nanoseconds, UTC, clock role, derivation and its own as-of external context index.
- An absent own clock is explicitly aggregate_or_unclocked_retained, or explicit_parent_context_only when an exact whole-parent reference supplies context. Parent clocks never become the observation's own clocks.
- CCode source-field relative horizons info_horizon_local_s and info_horizon_refractory_s are anchored to day0+t0+offset. Every changed stamp has an explicit correction record. Original source bytes remain available; these corrected sidecar stamps are authoritative for this packet.
- Native and CCode populations remain distinct. CCode-to-Native links require exact ID plus a matching explicit birth or recognition clock. Historical no-prefix sources remain separately labelled, not mixed into the full-session data.
- Original field-to-layer pins from CCode's existing ledgers are retained; other fields use a documented semantic field-name association. Unknown fields stay UNMAPPED_FIELD_RETAINED. All 99 registry entries are preserved; static/context layers are not falsely claimed as observed runtime measurements.
- External context indices reference the immutable 13-input/48-series publication history in the linked lifecycle packet below. Missing/invalid states remain unchanged and no future publication is selected.
- Original values are read through immutable source row coordinates; this index does not rescale, average or replace those values. Duplicate historical sources are provenance records, not independent event counts.

[Lifecycle crosswalk, sample-clock grids and informational renders](https://github.com/DavisAI1974/markets-data/tree/2f1c3c72f9e3f15916135bca37ffcad87477e1d6/tasks/family-research-20261022/lifecycle-data-links/run-42583801329-1)

External lookup: load that packet's external/external-contexts.npz and original-external-series.json.gz. For each clock's external_context_index, use previous_original_index[context,series]. -1 means no publication available. All source state codes, reasons, target dates and publication confidence are retained. Declared publication time does not prove live ingestion.

Review each shard's clock_corrections_json and aggregate/unclocked counts before consuming clocks. Duration columns are never interpreted as absolute timestamps.
