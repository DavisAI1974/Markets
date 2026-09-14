# SPEC: Granite critique contract (`granite_contract.py`)

Status: implemented on branch `claude/granite-contract-slice-20260914` from `de27bb26`.
Scope: the Granite (C23) model-completed seam only. No transport, controller routing,
source/teacher/QSV/forecast logic, legacy templates, Memory A or OPEN_ITEMS changes.

## Why

At `de27bb26` the output validator (`granite_output_schema.py`) and three system
prompts each restated the same cardinalities and limits as hand-typed literals:

| owner | what it restated |
|---|---|
| `granite_output_schema.py` | 7 required keys, 3 verdicts, refs <= 16, contradictions <= 8, missing <= 8, hypotheses 1..4, note <= 200, missing entry <= 120, label <= 40 |
| `granite_prompt.py` `SYSTEM_TEXT` (serialized V2) | all of the above as prose, schema version interpolated |
| `granite_context.py` `SYSTEM_TEXT` (native V1) | all of the above as prose, schema version hard-coded |
| `granite_context_compact.py` `SYSTEM_TEXT` (compact native V1) | all of the above as prose, schema version hard-coded |

No test derived one from another. A limit widened in the validator would leave all
three prompts under-asking and every result "valid"; a limit widened in a prompt
would have every wider reply rejected as a Granite fault. That is the orphaning the
architecture ruling (`CLAUDE_ARCH_REVIEW_NOOA_CONTEXT_RETRIEVAL_20260914.md`,
section 2a) named. The ruling predates the compact codec; this spec includes it.

## What the contract owns

`granite_contract.py` is the single source for:

- `SCHEMA_VERSION` (`BOSS_GRANITE_OUTPUT_SCHEMA_V1`)
- `REQUIRED_KEY_ORDER` (ordered tuple) and `REQUIRED_KEYS` (frozenset)
- `CONTRACT.evidence_verdicts` (ordered tuple) and `EVIDENCE_VERDICTS` (frozenset)
- `LIMITS: GraniteLimits` with fields `max_evidence_refs=16`, `max_contradictions=8`,
  `max_missing_evidence=8`, `min_hypotheses=1`, `max_hypotheses=4`, `note_chars=200`,
  `missing_evidence_chars=120`, `label_chars=40`
- `render_system_text(variant)` for `PROMPT_VARIANTS = ('serialized_v2', 'native_v1',
  'compact_native_v1')`
- `system_prompt_hash(variant)` = SHA-256 of the rendered text

Validation stays at the existing `granite_output_schema.validate_schema` entry
point, which enforces the frozen production contract. Alternate contract instances
are rendering probes only. The returned slice's unused instance `validate` method
was removed during integration because it ignored its instance and validated
against the global production limits; retaining it would falsely imply that a
custom rendered contract controls output acceptance. No dynamic validation policy
or change in accepted production output was introduced.

Consumers:

- `granite_output_schema.py` imports `SCHEMA_VERSION`, `REQUIRED_KEYS`,
  `EVIDENCE_VERDICTS`, `LIMITS` from the contract and reads every cap from `LIMITS`.
  Its public names are unchanged, so `granite_parser`, `granite_context`,
  `granite_shadow`, `frankie_controller` and the tests import exactly as before.
- `granite_prompt.SYSTEM_TEXT = render_system_text('serialized_v2')`
- `granite_context.SYSTEM_TEXT = render_system_text('native_v1')`
- `granite_context_compact.SYSTEM_TEXT = render_system_text('compact_native_v1')`

The existing `SYSTEM_TEXT` names, `PROMPT_VERSION` strings, prompt dataclasses and
`build_*_prompt` functions are untouched.

## Rendering rules

- Rendering is pure: it reads only the contract's own constants.
- Templates own layout and connective prose. Every contract value (schema version,
  each required key, each verdict, each limit) enters through a `${...}` slot; no
  contract value is a literal in a template.
- After substitution `_verify` asserts that the schema version, every required key
  and every verdict appear in the rendered text; a template that cannot carry a
  value fails closed rather than silently dropping it. A template referencing a slot
  the contract does not define also fails.
- The serialized V2 prose states one shared cap ("contradictions and missing_evidence
  contain 0 to N each"). Rendering that variant with unequal caps raises; the
  template cannot state two numbers without a prompt change.
- Line breaks inside the rendered key and verdict lists are deliberate: they
  preserve the exact byte layout frozen at `de27bb26`.

## Byte identity (A-65 proof)

The three prompts were frozen BEFORE the refactor as
`tests/fixtures/granite_prompts/{serialized_v2,native_v1,compact_native_v1}.txt`
with `frozen_prompt_hashes.json`. `.gitattributes` marks that directory `-text` so
an autocrlf checkout cannot rewrite the bytes (the gold-vault trap from S110).

| variant | bytes | sha256 |
|---|---|---|
| serialized_v2 | 1496 | `7259a047c59e4d0b58457fe7022426e70b7116aaf0d061d12ef4da24f9d4263c` |
| native_v1 | 1014 | `a55ca0222e5e954682682df9e2cd9837dc47dc84a61d517701f8ef21526be7dd` |
| compact_native_v1 | 1746 | `f3e99a9d283c72424a22d6677c353a5ee6742632810ad6249f1e7b7c6ae18605` |

`tests/test_granite_contract.py` asserts, for each variant, that the fixture bytes,
`render_system_text(variant)`, the owner module's `SYSTEM_TEXT`, and the runtime
prompt object's `system_prompt_hash` all agree with these values. The same hashes
are literals in the test so the fixture index cannot be regenerated silently.

## Identity: honest code hashes

Unchanged prompt bytes do NOT mean unchanged parser source hashes. The contract is
an input to every parser identity:

- `granite_shadow.parser_code_hash()` now digests `granite_parser`,
  `granite_output_schema` AND `granite_contract`.
- `granite_context.native_parser_code_hash()` now includes `granite_contract.py` in
  its file list.
- `granite_context_compact.compact_parser_code_hash()` = sha256(own bytes +
  `native_parser_code_hash()`), so it moves transitively with no separate list.

Consequences, proven by tests that append an inert comment to `granite_contract.py`
on disk and restore it:

- all three parser hashes move while all three prompt hashes stay frozen;
- `serve_shadow`, `serve_native_shadow`, both AWS services' `critique_compact`,
  and native/compact `FrankieForecastController.refresh` each raise before
  invoking transport when the local contract differs from the
  pinned identity (the controller route compares `identity.parser_code_hash` to
  the selected native or compact parser hash in `_configuration`, so both routes
  inherit the dependency binding).

### Migration

Because `granite_output_schema.py`, `granite_context.py`,
`granite_context_compact.py` and `granite_shadow.py` change bytes and
`granite_contract.py` joins the bundles, every `parser_code_hash` value moves once
at this commit. `system_prompt_hash` and `schema_version` do not move. No hash is
recorded as a constant anywhere in the repository (every caller and test computes
it), so no in-repo pin needs rewriting. Any identity pinned OUTSIDE the repo (a
deployed `GraniteIdentity`, a SageMaker/Bedrock config carrying
`parser_code_hash`) must be re-minted from the new source; the old pin is rejected
by design, which is the desired behaviour.

Platform note: parser hashes are computed from on-disk bytes. A Windows checkout
with `core.autocrlf=true` holds CRLF copies of these modules and therefore reports
different values than a LF checkout. This predates this change; the values handed
to Codex are computed from the git blobs (LF).

## Tests

`tests/test_granite_contract.py`: frozen bytes and hashes; contract values frozen;
schema/parser consume the contract objects; each limit accepted at its boundary and
rejected one past it; hypotheses lower bound; support/against carry no invented
cap; malformed references rejected in every location; negative row remains the
scorers' job (de27bb26); unknown variant and inconsistent V2 caps rejected; a limit
change moves the prompt hash visibly; render fails closed on an unrenderable value;
invalid limits rejected; contract mutation moves every parser identity; every
pinned service rejects a contract change before transport; compact identity is
transitive; standalone and package imports share one contract; compact AWS services
and controller reject stale contract pins before SDK construction, critic calls or
native publication; alternate render contracts expose no misleading validator API.

`tests/test_legacy_output_shape_conformance.py`: the BLD-1 output-shape finding
(see below).

Run with `PYTHONPATH` = repository root, `research/kalshi/frankie_boss`,
`research/kalshi/frankie_boss/tests` (separator `;` on Windows, `:` elsewhere).

## Legacy BLD-1 output-shape finding

The Codex preflight stopped on `store/sop_templates.json` BLD-1 naming eleven
output fields while `frankie_contract.BLD1_FIELD_NAMES` names twelve. Traced:
these are two distinct interfaces, not a stale prompt and not a sequential
transform. The legacy template instructs a walk specialist to write
`forecasts/g{N}_perday/...json`, consumed by walk tooling; nothing on that path
imports `frankie_contract`. `validate_bld1`'s only producers are the deterministic
`FrankieProjector` methods and `category_free_abstain`, which set `disposition`
themselves; and `disposition` already existed in the supplied checkpoint. The
proposed equality assertion compared different interfaces. The conformance test
freezes the actual relationship (legacy eleven == BOSS twelve minus `disposition`,
and no module feeds a model emission into `validate_bld1`).

## Residuals (not in this slice)

- Sub-key names (`row`/`field`, `a`/`b`/`note`, `label`/`support`/`against`) remain
  literals in both the validator and the templates. Same orphaning class, outside
  the requested contract surface; a follow-up could add them to the contract.
- The Frankie output contract object (Seam 2 of the ruling) is Codex's.
