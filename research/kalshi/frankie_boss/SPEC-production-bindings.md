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

Local configuration will bind exact source scope/extractor, model and decoder
artifacts, target sessions, cadence and optional QSV/calibration. Existing runtime
objects own source verification, causal coverage, publication and confidence rules.
Source ingestion and native inference are explicit subsequent calls, not loader
side effects. All operational sources, masks, mappings, sessions, fitted weights
and empirical eligibility come from separately supplied artifacts.
