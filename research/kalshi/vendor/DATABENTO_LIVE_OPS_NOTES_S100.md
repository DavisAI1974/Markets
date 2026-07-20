# DATABENTO LIVE API - OPERATIONS NOTES (S100, from official docs; Greg screenshot capture 2026-07-20)

Source: databento.com docs, live API chapter (13 screenshots, captured while logged in).
These are THE design constraints for the M5 live collector. Vendor facts verbatim-distilled;
our conclusions marked OURS.

## Intraday replay (crash recovery)

- Live API replays within the LAST 24 HOURS: pass `start=` on subscribe (per-subscription;
  multiple subs of the same schema may carry different starts). `start=0` = full available
  replay window. Filtered on ts_event (ts_recv for BBO/CBBO only).
- GLBX.MDP3 SPECIAL CASE: MBO and definition schemas replay the ENTIRE WEEKLY SESSION
  (beyond 24h) - because they are stateful. Aids full-book recovery.
- A REPLAY_COMPLETED SystemMsg (code 3) fires per schema when replay catches up to
  real-time. Subscriptions added after session start are NOT replay-eligible.
- EXACTLY-ONCE RECIPE (verbatim doctrine): continuously store last ts_event + count of
  records at that ts_event, per schema and instrument. On reconnect, resubscribe with
  start = lowest stored ts_event across instruments for that schema; then discard records
  with lower ts_event, and discard the first N records at the stored ts_event.
- Python: client.subscribe(..., start="YYYY-MM-DDTHH:MM:SS") accepts pd.Timestamp,
  datetime, date, ISO 8601, or ns UNIX timestamp.

## Snapshot

- subscribe(..., snapshot=True) delivers current order-book state without session replay.
  MBO SCHEMA ONLY. Fastest recovery when only current state is needed; docs recommend the
  no-replay newest-messages approach for stateless schemas like MBP-10.

## System messages (SystemMsg; codes)

- 0 HEARTBEAT (sent only if no other record during interval; interval set via
  heartbeat_interval_s on Live(), default 30s; rec.is_heartbeat()).
- 1 SUBSCRIPTION_ACK, 2 SLOW_READER_WARNING, 3 REPLAY_COMPLETED, 4 END_OF_INTERVAL.

## Errors (ErrorMsg: err/code/is_last; ErrorCode)

- 1 AUTH_FAILED, 2 API_KEY_DEACTIVATED, 3 CONNECTION_LIMIT_EXCEEDED,
  4 SYMBOL_RESOLUTION_FAILED, 5 INVALID_SUBSCRIPTION, 6 INTERNAL_ERROR,
  7 SKIPPED_RECORDS_AFTER_SLOW_READING.
- Fatal errors close the session after the error record; non-fatal are informational.
- OURS: code 7 + SLOW_READER_WARNING = the backpressure signals a collector must alarm on;
  code 2 = the live-side signature of a dead key (the historical-side signature is the
  auth error we saw S100).

## Connection / rate limits (Standard plan)

- 10 simultaneous live sessions PER DATASET PER TEAM (Plus/Unlimited: 50). Extra API keys
  do NOT raise the cap.
- Gateway: max 5 incoming connections/sec per IP (excess = immediate close; wait 1s).
- Subscription requests throttled at 10/sec (excess delayed, not rejected; ack when done).

## Error detection / reconnect doctrine

- Hung connection: no data for heartbeat_interval + 10s => treat as hung, disconnect,
  reconnect (unstable links may need more than +10s).
- Disconnect without error: TCP closed; Live.block_for_close / Live.wait_for_close raise;
  wait ONE SECOND then reconnect (faster retries trip the gateway rate limiter).
- Disconnect with error: ErrorMsg precedes the close; consume it in the app.
- Logging: enable python logging for the databento module in live apps (off by default).

## Versioning / compression

- APIs + clients are semver; MAJOR 0 = API NOT YET STABLE (breaking changes possible -
  OURS: pin client versions on the live box; upgrade deliberately, not automatically).
- Live supports zstd compression option (slight CPU cost) or none.

## OURS - what the M5 collector does with this (design consequences)

1. Persist (ts_event, count) per schema+instrument continuously; on any restart,
   resubscribe with start=lowest stored ts_event and dedupe per the recipe - zero-gap
   collector without local buffering heroics.
2. MBO book collector recovers via snapshot=True when only current book needed, or full
   weekly replay when the session's book history matters.
3. Alarm on SystemMsg 2 and ErrorCode 7 (we are reading too slowly - the S90-class silent
   data-loss failure mode, now server-signaled).
4. Respect 1s reconnect backoff and the 10-session/dataset cap (the collector + smoke
   tests + ad-hoc sessions share it).
5. Latency baseline (measured S100): 6.6-23.4ms us-east-2. See LIVE_TELEMETRY_S100.md.
