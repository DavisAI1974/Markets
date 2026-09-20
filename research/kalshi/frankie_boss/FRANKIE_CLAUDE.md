# FRANKIE_CLAUDE.md - working notes for Claude on the Frankie/BOSS build

Started 2026-09-14 on the Granite contract slice. Basics only; the specs and
handoffs in this directory remain the record. This file is a new name on purpose
so nothing older is overwritten.

## Objective (read first)

The exhaustion research is Frankie's objective and the basis of the eighteen calculation sections: chains with
extensions, reappearances and ancestry; D structures and families; dipoles and geometry; pair and triplet
recurrence; pre-birth opportunity; the causal clocks; the horizon times. Mission document
`research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md` (receiver side); per-cycle
required set `knowledge/CYCLE_CALCULATION_PINS.json`; standing ledger `knowledge/RUN_FINDINGS.md`.

## Running the suites (Windows)

    PYTHONPATH=".;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests"
    python -m pytest research/kalshi/frankie_boss/tests/<file>.py -q

The separator is `;` on Windows. With `:` Python treats the whole string as one
path and `controller_journal`, `granite_context` etc. fail to import. Elsewhere
use `:`.

Checkout note: `core.autocrlf=true` here, so tracked `.py` files are CRLF on disk.
Parser code hashes read on-disk bytes; report hashes from git blobs (LF) when they
must match another machine. Byte-frozen fixtures are marked `-text` in
`.gitattributes`.

## The Granite seam in one place

Three prompt variants, one contract (`granite_contract.py`, spec in
`SPEC-granite-contract.md`):

| variant | owner module | prompt hash pinned by | parser identity |
|---|---|---|---|
| serialized V2 | `granite_prompt.SYSTEM_TEXT` | `GranitePrompt.system_prompt_hash` | `granite_shadow.parser_code_hash()` |
| native V1 | `granite_context.SYSTEM_TEXT` | `NativePrompt.system_prompt_hash` | `granite_context.native_parser_code_hash()` |
| compact native V1 | `granite_context_compact.SYSTEM_TEXT` | `CompactPrompt.system_prompt_hash` | `granite_context_compact.compact_parser_code_hash()` |

Where the pins are checked: `granite_shadow.serve_shadow` / `serve_native_shadow`
(before transport), `frankie_controller.FrankieForecastController._configuration`
(native prompt hash, native parser hash, schema version). `granite_contract.py` is
an input to all three parser hashes, so a contract edit cannot leave an old pin
valid.

Frozen prompt hashes (de27bb26, unchanged by the refactor):
`7259a047...4263c` serialized V2, `a55ca022...be7dd` native V1,
`f3e99a9d...18605` compact native V1. Full values and byte lengths in
`tests/fixtures/granite_prompts/frozen_prompt_hashes.json`.

## Legacy BLD-1 vs BOSS twelve fields

Not a stale prompt. The protected BLD-1 template (11 fields) is the walk
specialist's file-emission shape; `frankie_contract.BLD1_FIELDS` (12, with
`disposition`) is the BOSS projection target set by deterministic code. They never
meet. Locked by `tests/test_legacy_output_shape_conformance.py`.

## Parallel-build conventions

- Own worktree and branch per contributor; never edit another checkout.
- Commit locally, hand Codex the hash and patch; Codex integrates into
  `codex/boss-full-evidence-20260907`.
- Preserve de27bb26's negative-reference bounds fix in the scorers.
- Out of bounds for Claude slices unless assigned: transport, controller routing,
  source/teacher/QSV/forecast logic, protected legacy templates, Memory A,
  historical workbooks, OPEN_ITEMS terminal states, provider calls, training,
  replay, held-out reveal, trading orders.
