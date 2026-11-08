# Henry Hub NG front-month raw MBO, October 2023 re-download (2026-11-08)

Re-pull of the four Frankie test days, requested by Greg because AWS/S3 is unavailable; the
files live in git instead of the S3 `nymex/ng_mbo_5y_v0/` prefix.

- Dataset GLBX.MDP3 (CME Globex), schema `mbo` (every order message, zero reduction).
- Symbol `NG.v.0`, stype_in `continuous` = volume-rolled front-month Henry Hub natural gas
  futures (resolves to NGX3 in October 2023). The daily Kalshi NG market reprices off this.
- One file per UTC day, raw DBN zstd exactly as served (`databento` client 0.90.0,
  `timeseries.get_range` -> `DBNStore.to_file`). Read with `databento.DBNStore.from_file`.
- `MANIFEST.json` carries bytes, sha256, record count (verified equal to
  `metadata.get_record_count` for each day), first/last ts_event and per-day cost.
- The leading records of each file that pre-date the day are the resting-order snapshot
  Databento emits at range start; they are part of the raw stream and were kept.
- Total cost USD 0.31. The API key is a secret and is NOT in this repository.
