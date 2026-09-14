# Governed QSV encoder producer

Additive software adapter; preserve markets_adapter.py, native mapping and
existing QSVContext attachment. No raw-MBO-to-bar transformation, resampling,
PELT segmentation, scaler fitting, feature reduction or implicit carry-forward.

An immutable complete bar observation explicitly supplies all eight MarketBar
numeric fields plus integer receive availability and independent source digest.
The source timestamp stays the original floating-point seconds accepted by the
existing encoder; availability uses explicit integer nanoseconds. Every chunk
supplies its source/chunk identities, exact window bounds, immutable bars,
availability, native cursor/entity/prefix mapping, original realized_vol and
bic_segment_score descriptors and all coordinate masks.
Nothing defaults missing OHLC/volume fields to zero. One-bar/degenerate encoder
results retain original encoder semantics; their masks are explicitly governed,
not inferred from whether the vector is zero.

Producer configuration pins source manifest, encoder code/runtime identity,
mask-policy identity and source-to-native mapping policy. `source_input_hash`
binds configuration and all original observations. `produce` requires that hash
from an independent caller source authority, checks availability before the mapped
native receive time and invokes the original complete 64-feature encoder exactly.
No model is trained. All numeric inputs/outputs must be finite; invalid data
rejects rather than being repaired. Source provenance/policy hashes are caller
assertions and do not prove the chosen real source or masks are correct.

The result is the existing immutable QSVContext with one row per declared native
cursor. Producer identity binds config; each row binds original source prefix,
entity, availability, unchanged encoder vector and supplied mask. A separate
append-only journal retains complete source observations, config and output
artifact with a production receipt hash. Restarts require an independent exact
journal count/head checkpoint; matching input retries reuse the stored output.
No deletion or result filtering. Historical reads do not rerun the encoder.

Acceptance: original encoder parity, explicit source/availability/masks, absent
field rejection, input tampering, restart/checkpoint and idempotent reuse; real
encoder output must reach actual ContextSessionRunner native/QSV tensors in a
synthetic integration test. Software checks do not accept production source
semantics, policy choices or throughput; these remain governed deployment inputs.

API: `ProducerConfig(producer_id, source_manifest_hash, mask_policy_hash,
mapping_policy_hash, encoder_hash)`; `source_input_hash(chunks, config)` computes
the identity for source authority verification. `QSVProducerStore(path,
create=True)` creates a new log; reopening requires `checkpoint=(count, head)`.
`store.produce(chunks, config, expected_input_hash=...)` returns `QSVProduction`
containing `artifact`, `input_hash`, `receipt_hash`. Pass `artifact` and its
independently retained digest to the existing ContextSessionRunner QSV interface.
Retain `store.checkpoint()` outside the database for trusted restart.
