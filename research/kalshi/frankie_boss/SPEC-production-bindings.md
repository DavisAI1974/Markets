# Local production bindings

This additive capability connects externally supplied artifacts to existing source,
context and forecast implementations. It does not acquire data, train models,
derive source semantics, execute a provider request or authorize trading.

Build order: exact native model artifact -> local configuration assembly.

## Native model artifact

`NativeModelSnapshot.capture` serializes an existing finite CPU float64 eval-mode
NativeTrunk or B1Reasoner, its complete TrunkConfig, native registry, explicit QSV
ablation and complete B1Config when applicable. Existing exact tensor encoding is
used, never pickle. Runtime/source and effective module configuration are pinned.
Restoration consumes no caller RNG state and loads every tensor with exact keys,
shape, dtype and bytes; no conversion, missing-key defaults or partial loading.
Weights describe supplied state, not evidence of fitting or forecast eligibility.

Acceptance: native and B1 roundtrip with identical outputs and tensor bytes;
unknown/missing keys, dtype/shape/byte tampering, nonfinite values, incomplete
configuration, runtime changes and unsupported module overrides fail. No global
RNG or default precision/device mutation. Existing native interfaces stay intact.

## Configuration assembly

Local configuration binds exact source scope/extractor, model and decoder
artifacts, target sessions, cadence and optional QSV/calibration. Existing runtime
objects own source verification, causal coverage, publication and confidence rules.
Source ingestion and native inference are explicit subsequent calls, not loader
side effects. All operational sources, masks, mappings, sessions, fitted weights
and empirical eligibility come from separately supplied artifacts.

### Encoding and exact configuration

`load_bindings(path, expected_sha256=...)` verifies the independently supplied
SHA256 of the configuration bytes before opening referenced artifacts. All typed
files use `canonical_bytes(pack(value))` from `c15_journal`: exact bytes, tuples,
integers and IEEE-754 floats retain their existing representation. The decoder
rejects malformed/noncanonical representations. Every dataclass field must be
present, including nullable/default-valued fields; unknown fields fail. Artifact
references have exactly `path`, `bytes` and `sha256`; paths are local and resolve
relative to the configuration file. File SHA256, typed artifact digest, source
scope hash, source prefix hash and session registry hash remain separate domains.

The top-level object has exactly:

| Field | Value |
| --- | --- |
| `schema` | `BOSS_PRODUCTION_BINDINGS_V1` |
| `source` | Fields described below |
| `native` | Reference to encoded `asdict(NativeModelSnapshot)` |
| `decoder` | Reference to encoded `asdict(DecoderSnapshot)`, or null |
| `sessions` | Reference to a tuple of `(asdict(ForecastTarget), asdict(ForecastSession))`, or null |
| `expected_sessions_hash` | Independent `session_registry_hash` identity, or null |
| `cadence` | Complete `asdict(RefreshPolicy)`, or null |
| `entity` | Exact `(publisher_id, instrument_id)` tuple |
| `t_ctx` | Explicit positive native context length |
| `qsv` | Optional explicit QSV binding below, or null |
| `calibration` | Optional existing calibration binding below, or null |

`source` contains `scope` (all SourceScope dataclass fields; kind as enum value,
members as tuple of complete SourceMember dictionaries), `expected_scope_hash`,
`pin` (complete MboSourcePin), ordered local `paths`, ordered `session_ids`,
`raw_symbol` (explicit string or null) and `evidence` (nonempty referenced bytes
retaining the caller's manifest/scope mapping and authority). The mapping is a
caller assertion with pinned evidence, not a claim that arbitrary source manifests
are equivalent. Runtime is checked against the existing pinned DBN implementation.
The loader opens configuration/artifacts, not the market source files. `ingest`
subsequently delegates byte verification and all decoding to `ingest_sources`.

The native model registry must include the existing complete DBN extraction fields.
NativeTrunk may assemble a context without forecasting. B1 may also be used for
context only. Forecast configuration requires all four decoder/session/hash/cadence
fields together and B1; decoder dimensions must match the representation. Targets
must be unique and match declared session closes, with one causal source state,
certified anchors and declared cadence covering every target.

QSV has exactly `artifact` (reference to encoded complete QSVContext), `producer`
(complete ProducerConfig), `expected_artifact_hash` and `mapping_evidence`
(nonempty reference). The producer config pins its own actual bar/chunk source,
mask policy and mapping policy; its source hash is never equated to the raw MBO
scope. QSVContext.producer_id must equal ProducerConfig.digest. The existing
context attachment checks every consumed row's cursor/entity/availability/source
prefix. Unablated QSV models require an explicit artifact. No rows/masks are made
up for missing coverage.

Calibration has exactly `artifact` (reference to complete CalibrationArtifact)
and `expected_artifact_hash`. The independently trusted configuration must name an
externally accepted artifact. Its acceptance report/eligibility are not earned by
loading it. `confidence(logit=..., policy=..., context=...)` uses the unchanged
resolver's identity, support and validity checks; absence or ineligibility returns
nullable probability. It is separate from sole-candidate native publication and
does not add scoring, confidence floors or fake empirical acceptance.

### Runtime use and ownership

```python
bundle = load_bindings(config_path, expected_sha256=trusted_config_sha256)
# A separate explicitly requested local ingestion operation, if needed:
ingestion = bundle.ingest(new_source_journal_path)
# Or use an already restored C15Builder from its trusted checkpoint.
builder = C15Builder.restore(bundle.source.scope, new_source_journal_path,
    ingestion.checkpoint, expected_hash=ingestion.completion.builder_state_hash)
context = bundle.context(builder,
    expected_builder_state_hash=ingestion.completion.builder_state_hash)
# Native-only users call the existing context.run at an explicit causal cutoff.
bridge = bundle.assemble(builder, caller_owned_forecast_book,
    expected_builder_state_hash=ingestion.completion.builder_state_hash)
# B1 forecast users explicitly call bridge.update with bundle.sessions and its
# independently pinned expected_sessions_hash plus actual arm/cutoff/source pins.
```

Callers own journals/books, trusted checkpoints, lifecycle/cleanup and execution
authorization. Assembly verifies the builder's scope, checkpoint, full journal,
complete declared per-member counts, sessions, raw-symbol mapping and extraction
pins. Completeness of ingestion does not restrict earlier causal run cutoffs.
An attached QSV artifact requires the restored model's QSV input path.
Forecast sessions must bind the assembled
checkpoint's source prefix. No constructor writes output, runs a forward or fetches
anything. Artifacts and evidence bytes stay available in the returned bundle;
configuration bytes retain all supplied provenance and file identities.

Tests use synthetic actual-SDK DBN records, randomized explicitly synthetic model
artifacts and three local pathways (native, B1, B1+QSV), including an actual existing
native forecast update. They prove malformed pins/configuration fail before runtime
use, corrupted source/QSV evidence is refused, and loading performs no ingestion or
forward. They do not establish fitted performance, raw-source equivalence, empirical
calibration, provider capacity, rights, or live trading readiness. Protected prompts,
agent-lineage evidence, Memory A, workbook and Sunday artifacts are unchanged.

After independent review, three regression cases cover incomplete ingestion,
raw-symbol mismatch and an incompatible QSV model. All 131 selected production,
native-artifact, source, native-refresh, QSV-producer and confidence checks passed.
