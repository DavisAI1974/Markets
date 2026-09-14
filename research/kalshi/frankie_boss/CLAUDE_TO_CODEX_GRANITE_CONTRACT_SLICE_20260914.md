# Claude to Codex: Granite contract slice, delivered

Date: 2026-09-14
Base: `de27bb26` on `codex/boss-full-evidence-20260907`
Branch: `claude/granite-contract-slice-20260914` (own worktree; nothing pushed to the
integration branch; Codex's checkout untouched). Commit hash and patch file are in
the chat handoff; the patch is `git format-patch de27bb26..HEAD` of this branch.

## Changed files

New
- `research/kalshi/frankie_boss/granite_contract.py`
- `research/kalshi/frankie_boss/SPEC-granite-contract.md`
- `research/kalshi/frankie_boss/tests/test_granite_contract.py`
- `research/kalshi/frankie_boss/tests/test_legacy_output_shape_conformance.py`
- `research/kalshi/frankie_boss/tests/fixtures/granite_prompts/{serialized_v2,native_v1,compact_native_v1}.txt`
- `research/kalshi/frankie_boss/tests/fixtures/granite_prompts/frozen_prompt_hashes.json`
- `research/kalshi/frankie_boss/FRANKIE_CLAUDE.md` (Greg asked for a fresh working-notes file under this name)
- this note

Modified
- `granite_output_schema.py`: constants imported from the contract; every literal cap replaced by `LIMITS.*`; public names unchanged
- `granite_prompt.py`: `SYSTEM_TEXT = render_system_text('serialized_v2')`
- `granite_context.py`: `SYSTEM_TEXT = render_system_text('native_v1')`; `granite_contract.py` added to `native_parser_code_hash` file list
- `granite_context_compact.py`: `SYSTEM_TEXT = render_system_text('compact_native_v1')`
- `granite_shadow.py`: `parser_code_hash()` bundle now includes `granite_contract`
- `.gitattributes`: fixture directory marked `-text`

Not touched: transport, controller routing, source/teacher/QSV/forecast logic,
`store/sop_templates.json`, RUN_SOP, Memory A, workbooks, OPEN_ITEMS. The de27bb26
negative-reference bounds in `score_native`/`score_compact` are unchanged.

## Frozen prompt hashes (before refactor == after refactor)

| variant | bytes | sha256 |
|---|---|---|
| serialized_v2 | 1496 | `7259a047c59e4d0b58457fe7022426e70b7116aaf0d061d12ef4da24f9d4263c` |
| native_v1 | 1014 | `a55ca0222e5e954682682df9e2cd9837dc47dc84a61d517701f8ef21526be7dd` |
| compact_native_v1 | 1746 | `f3e99a9d283c72424a22d6677c353a5ee6742632810ad6249f1e7b7c6ae18605` |

Frozen from the module `SYSTEM_TEXT` values at `de27bb26` before any edit; asserted
after the refactor against the fixture bytes, `render_system_text`, the owner
module's `SYSTEM_TEXT`, and each runtime prompt object's `system_prompt_hash`.

## Parser-identity migration

`system_prompt_hash` (all three) and `schema_version` do not move.
`parser_code_hash` (all three) moves once at this commit, for two reasons that are
both intended: the schema/context/compact/shadow module bytes changed, and
`granite_contract.py` is now an input to the bundles. Values below are computed from
git blobs (LF), independent of the Windows CRLF checkout, with a reimplementation
verified equal to the live functions on identical bytes.

| identity | de27bb26 | this commit |
|---|---|---|
| `granite_shadow.parser_code_hash()` | `4d3cce830d258432c1e78e69621e8ccfcb0dae269bd4205f7b16badd6a39e2c5` | `535ab1a2f6c8dbebaef78d945fd612b6622285f5c2462b5ad3e2e83e0073bc61` |
| `granite_context.native_parser_code_hash()` | `9b2a712ce28b8d58a2f18f8e46ca200c5f0766a040a608cfecc52adc7fc54460` | `f6b3aff443f2707d0c58345b90bf5e937d24daacf92d794592b8b30c33824652` |
| `granite_context_compact.compact_parser_code_hash()` | `6d6157834ea62ce5b07531bc1272f9f477678faa7c50469fc7322bb4ba90d441` | `c277628203d25df2c10c6f1172c85aee933233121b2f24b74255b0b295103511` |

(Computed over the committed LF blobs of `granite_parser.py`, `granite_output_schema.py`,
`granite_contract.py`, `granite_context.py`, `granite_context_compact.py`,
`context_session.py`, `native_mbo_encoder.py`, `c15_journal.py`, `causal_packet.py`
and the QSV registry names, exactly as the live functions do; a LF checkout of the
commit reproduces them by calling the functions.)

Nothing in the repository stores a parser hash as a constant: `granite_shadow`,
`granite_context`, `granite_context_compact`, `frankie_controller._configuration`
and every test compute it from source. So no in-repo pin needs editing. Any
`GraniteIdentity` pinned outside the repo (deployed SageMaker/Bedrock config, a
saved identity JSON) must be re-minted from this source; the old pin is rejected
by `serve_shadow`, `serve_native_shadow` and the controller, which is the desired
fail-closed behaviour.

Proof that a contract change cannot escape identity
(`test_granite_contract.py::test_contract_source_change_moves_every_parser_identity_without_moving_prompt_hashes`,
`::test_every_pinned_service_rejects_a_contract_change_before_transport`): an inert
comment appended to `granite_contract.py` on disk moves all three parser hashes
while the three prompt hashes stay frozen; with pins minted before the change,
`serve_shadow`, `serve_native_shadow` and `FrankieForecastController.refresh`
(built with `test_frankie_controller.build_controller`) each raise before invoking
transport. The controller needed no change: it already compares
`identity.parser_code_hash` to `native_parser_code_hash()`, which now covers the
contract.

Platform note: parser hashes read on-disk bytes. A `core.autocrlf=true` checkout
reports different values from a LF checkout. Pre-existing; not changed here.

## Legacy BLD-1 output-shape finding: resolved from code

Question: is `disposition` a deterministic post-LLM field for protected BLD-1, or is
the prompt stale?

Answer: neither a stale prompt nor a sequential transform. Two distinct interfaces.

- The protected BLD-1 template (`store/sop_templates.json`, body OUTPUT paragraph;
  RUN_SOP.md line 682 is the round-trip source) tells a walk specialist to write
  `forecasts/g{N}_perday/grp{N}_{X}_{DAY}.json` with eleven fields. Consumers of
  that file are walk tooling: `research/kalshi/path_contract.py:107,147`,
  `merge_perday.py`, `spawn.py`, `brain_audit.py`, `plant_status.py`. None imports
  `frankie_contract`. `grep -rn disposition research/kalshi --include=*.py` outside
  `frankie_boss` finds only brain-retraction and source-disposition uses; RUN_SOP's
  only `disposition` (line 375) is an audit adjudication.
- `frankie_contract.validate_bld1` (`frankie_contract.py:318`) is called only from
  `FrankieProjector.abstain` (`:477`) and `FrankieProjector.project` (`:522`), which
  set `disposition` themselves (`:465` ABSTAIN, `:520` from the `disposition`
  argument defaulting to CALL). `frankie_category_free.category_free_abstain` sets
  it at `frankie_category_free.py:103`. `forecast_bridge.py:49-50`,
  `frankie_forecast_consumer.py:67-68` and `frankie_controller.py:197-201` require
  `disposition` as CALLER-SUPPLIED metadata (`set(BLD1_FIELD_NAMES) - forecast
  fields`), never parsed from model text.
- `provenance/supplied_checkpoint/frankie_contract.py:163-176` already carries
  `disposition` as the twelfth field, so the contract did not grow a field after
  the prompt was written.
- `frankie_category_free.py:1` docstring: "Owner-approved opt-in twelve-field
  interface, separate from protected BLD-1."

So the proposed Slice-1 invariant `BLD-1 template field order == BLD1_FIELD_NAMES`
compared different interfaces. The correct, tested statements are in
`tests/test_legacy_output_shape_conformance.py`: the template emits exactly the
eleven names in order; `BLD1_FIELD_NAMES` is those eleven plus `disposition`
appended; an eleven-field payload is refused by `validate_bld1` (the shapes never
meet); the projector sets `disposition` for both CALL and ABSTAIN; and a
fail-closed static check that `validate_bld1(` has no caller in the package other
than `frankie_contract.py`, so a future module that parses a model emission into it
must record the ownership decision.

Forward note for integration (not a defect today): the bridge/consumer/controller
take `disposition` from caller metadata. If the legacy LLM walk file ever becomes
that caller's source, the caller must decide where `disposition` comes from; that is
an integration ruling, and this slice does not pre-empt it.

## Tests and commands

PYTHONPATH = `.;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests`
(`;` on Windows).

- New: `test_granite_contract.py` + `test_legacy_output_shape_conformance.py`:
  89 passed.
- Existing, unchanged: `test_granite_prompt`, `test_granite_parser`,
  `test_granite_shadow`, `test_granite_context`, `test_granite_context_compact`,
  `test_granite_native_service`, `test_granite_bedrock`, `test_granite_sagemaker`,
  `test_granite_evaluation`, `test_frankie_controller`: 382 passed before the
  refactor, 382 passed after.
- Full `research/kalshi/frankie_boss/tests` directory plus
  `research/kalshi/tests/test_frankie_boss_internal_bld1_mapping.py`, run at a
  clean `de27bb26` worktree and on this branch with identical PYTHONPATH:
  baseline 2 failed / 1380 passed / 1 skipped / 49 errors; this branch 2 failed /
  1469 passed / 1 skipped / 49 errors. The 51 failing ids are the SAME set on both
  (50 in `test_b1_reasoner.py`: a pinned checkpoint-hash mismatch and a
  "torch already imported" ordering assertion; 1 in `test_benchmark_checkpoint.py`).
  Pre-existing in this environment, none under Granite, none introduced.

## Remaining, precisely

No blocker for integrating this slice. Residuals outside its scope:

1. Sub-key names (`row`/`field`, `a`/`b`/`note`, `label`/`support`/`against`)
   remain literals in both the validator and the templates. Same orphaning class,
   not in the requested contract surface (schema version, keys, verdicts, limits).
2. The serialized V2 prose states one shared cap for contradictions and
   missing_evidence ("0 to N each"); the contract refuses to render that variant
   with unequal caps. If those caps ever diverge, the V2 prompt must change
   visibly.
3. External identity pins must be re-minted (see migration).
4. Seam 2 (`FrankieOutputContract`) and the category-free prompt render remain
   with Codex, per the assignment.
