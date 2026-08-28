# Frankie BOSS state serialization provenance

Date: 2026-08-28

Repository: `DavisAI1974/Markets`

Branch: `codex/frankie-boss-sol-replacement-20260824`

Module: `boss-state-serialization`

Status: **mechanical serializer GREEN in focused local execution; repository-native preservation suite not rerun in this sandbox**.

## Governing lifecycle

This tranche followed `addyosmani/agent-skills` release `0.6.7` from the brownfield path:

`using-agent-skills` -> `context-engineering` -> `spec-driven-development` -> `planning-and-task-breakdown` -> `test-driven-development` -> bounded `doubt-driven-development` / `code-review-and-quality`.

The BOSS brownfield inventory and the accepted serializer spec remain the governing context:

- `research/kalshi/frankie_boss/FRANKIE_BOSS_BROWNFIELD_ARCHITECTURE_INVENTORY_20260828.md`
- `research/kalshi/frankie_boss/SPEC-boss-state-serialization.md`

## Pre-tranche state

The proposed-spec checkpoint before human acceptance was:

`4e5a52cf18030254957624ec3de09fb38f3fac9a`

The user explicitly authorized continuation with `Proceed`. The accepted decisions were:

1. canonical JSON only for the first authority artifact,
2. `CausalPacket` identity plus separately declared typed sequence/graph/QSV state,
3. no real Step-1 sample in the mechanical tranche.

## Commit sequence

- Accepted spec: `cd29aabd17ab6a395ca82567cd7839597fe290e0`
- Plan: `35362aebd3cc8387ba25d4b90282996661c65d35`
- Task list: `8bd562a25e672e74c164866d249f05c305c1ba5a`
- Initial RED contract tests only: `2e94a45d6a3b3860bfe0d39ea3d55360359be6d4`
- Initial GREEN serializer: `9508c9e663163954a79a700572c4707bd10148af`
- Review-driven RED hardening tests: `7f20ebe43eae9fe0dd75869247afb102e1058816`
- Review-driven GREEN hardening: `186125c109133a1a6dd6ac8484c153b007d460d2`

## Files in the behavioral tranche

New executable/test files only:

- `research/kalshi/frankie_boss/state_serialization.py`
- `research/kalshi/frankie_boss/tests/test_state_serialization.py`

The accepted spec and lifecycle docs were updated. No existing BOSS executable, trunk, teacher, causal packet, Databento adapter, BLD-1 contract, Frankie core/provider file, ReFRAG registry/governance file, Step-1/V4 science file, or 1,940-path/46-block capability file was modified by this tranche.

A GitHub compare from `4e5a52cf...` through `186125c109...` showed only the accepted spec, `state_serialization.py`, its test file, and `tasks/plan.md` / `tasks/todo.md` in the tranche diff before this provenance closeout.

## RED receipt 1 — missing capability

Environment:

- Python `3.13.5`
- pytest `9.0.2`
- Linux x86_64

The RED sandbox deliberately contained the BOSS package path and a QSV registry stand-in but no serializer module.

Command shape:

```bash
python -m pytest research/kalshi/frankie_boss/tests/test_state_serialization.py -q
```

Observed intended failure:

```text
ModuleNotFoundError: No module named 'research.kalshi.frankie_boss.state_serialization'
```

This established that the new capability did not already exist and that pytest/import setup itself was working.

## Initial GREEN receipt

The focused contract suite after the minimal implementation produced:

```text
17 passed in 0.13s
```

The suite covered:

- deterministic text/hash,
- source-version mapping order neutrality,
- schema-version identity movement,
- typed round-trip,
- graph parent/root preservation,
- exact QSV name/order/state preservation,
- present-zero vs missing vs ablated distinctions,
- non-finite numeric rejection,
- malformed-parent rejection,
- QSV order/width drift rejection,
- source packet identity preservation,
- real-state identity movement,
- shape-preserving numeric/QSV ablation,
- unknown ablation-name rejection,
- no unrestricted `extra` payload on the typed snapshot.

## Review-driven RED receipt

The first bounded review found three real gaps:

1. `StateSnapshot` was frozen but retained the caller's mutable `source_versions` mapping.
2. The parser rejected unknown top-level fields but ignored unknown nested fields.
3. The parser did not reject an unsupported serializer schema version.

Regression tests were added before the fix. Against the initial GREEN implementation the focused run produced:

```text
3 failed, 17 passed
```

The three failures exactly reproduced those findings.

## Review-driven GREEN receipt

After the smallest hardening changes:

```text
20 passed in 0.05s
```

A subsequent repeat produced:

```text
20 passed in 0.06s
```

`python -m py_compile research/kalshi/frankie_boss/state_serialization.py` also passed.

The hardening changes:

- copy/freeze `source_versions` with `MappingProxyType`,
- tuple-freeze sequence/QSV collection members,
- strictly validate the complete key set at top-level and nested JSON objects,
- reject unsupported `schema_version` during parse.

## QSV test-environment qualification

This sandbox cannot clone or download the GitHub repository directly because outbound DNS/network access is unavailable. Therefore the focused local execution did **not** import the repository's live `markets_adapter.py`/`qsv_registry.py` files.

Instead it used a local registry stand-in matching the current governed default shape and order already established by repository authority:

- the 14 named prefix entries from `MARKET_FEATURE_SPEC`, followed by
- `fft_magnitude_0` through `fft_magnitude_49`,
- 64 total entries.

This is sufficient to exercise serializer logic against the current known registry shape/order, but it is not represented as a live repository import receipt. The executable serializer on GitHub imports the actual `research.refrag.qsv_registry.QSV_FEATURE_REGISTRY` and fails closed if supplied names/order differ.

## Preservation status

The existing BOSS causal/trunk/seam test files were not modified. The current environment has Torch and NumPy installed, but the repository cannot be cloned/materialized through the available sandbox network path, so the repository-native combined command covering existing causal/trunk/seam tests was **not rerun** here.

Historical `101`, `74`, and `160 passed` receipts therefore remain historical only. They are not upgraded to 2026-08-28 rerun receipts by this document.

A future repository-native environment should still execute:

```bash
python -m pytest \
  research/kalshi/frankie_boss/tests/test_causal_packet.py \
  research/kalshi/frankie_boss/tests/test_trunk.py \
  research/kalshi/frankie_boss/tests/test_seam.py \
  research/kalshi/frankie_boss/tests/test_state_serialization.py -q
```

before this tranche is treated as fully preservation-verified.

## Five-axis review

### Correctness

No remaining Critical/Required finding after the three review-driven fixes. The focused contract tests exercise the declared mechanical serializer behavior.

### Readability / simplicity

The implementation is isolated in one module and uses dataclasses/enums/pure functions. It intentionally does not introduce prompt engines, model clients, plugins, or provider abstractions.

### Architecture

No existing BOSS executable seam was modified. The serializer is additive and text-reasoner-neutral. QSV governance remains imported from ReFRAG. Graph relations are recorded/validated but graph message passing is not duplicated.

### Security / experiment integrity

The module performs no network, subprocess, provider, file-system, or dynamic-evaluation operation. Parsing is closed-schema at top-level and nested object boundaries. Non-finite present numerics and malformed graph/QSV structure fail closed.

### Performance

Serialization/parsing/ablation are bounded linear passes over the declared rows/fields/QSV vector and perform no external I/O. No performance blocker was identified for an experimental interface artifact.

## Important limitation — causal derivation is not proven here

This tranche proves a deterministic, closed, loss-auditable representation of the **declared** snapshot. It does not cryptographically prove that the separately supplied sequence/graph/QSV rows were derived from the `source_packet_hash` they accompany.

A malicious or buggy caller could still pair a valid-looking packet hash with semantically incorrect typed values while satisfying the serializer's structural schema. The serializer also cannot infer whether a correctly named numeric value was computed from future data.

That is not silently treated as solved. The later packet/ledger -> typed-state builder or semantic-validation seam must establish causal derivation and registry provenance before any Granite teacher result can be interpreted as market-valid.

This is especially important because the serializer is intended to help distinguish:

- serializer/interface failure,
- teacher/reasoner failure,
- and upstream state-derivation failure.

## Granite / Step-1 status

- Granite was not downloaded, invoked, served, or integrated.
- No provider model was called.
- No BOSS recurrent reasoning or adaptive halting was added.
- No Step-1 data was read and no Step-1 job was launched.
- No Frankie run or production launch occurred.

Granite 4.2 remains an unadopted research candidate for later teacher/control experiments only after serializer and teacher-validity gates are satisfied.

## Current interpretation

The serializer mechanical experiment is positive: the declared interface can be made deterministic, round-trippable, closed-schema, QSV-governed, graph-preserving, and ablation-aware without changing BOSS itself.

This is **not** evidence that Granite can understand the representation, improve BOSS, shorten the MBO training runway, or produce valid halt/abstain targets. Those remain separate experiments.
