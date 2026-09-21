# Spec: cycle 0's bedrock (derived geometry, pre-birth opportunity, causal clocks) and the exhaustion/D teach-back

Status: SPEC, 2026-09-21 23:xxZ, chat 6. Greg's call, verbatim: "All 3. The things you losted are sort of the bedrock
research that the rest of thebcalcs buid from and if we start with a bettwe base, everything after it improves."
The three: (1) `derived_geometry` (8 layers) added to cycle 0's pin; (2) the classroom also teaches exhaustion and D,
box-side, beside the 19-dimension Dipole classroom, host grader unchanged; (3) `prebirth_opportunity` (5) and
`causal_clocks` (7) added to cycle 0's pin too. Nothing runs on the host, the box, the Pod or the endpoint until it is
built and Greg says go. Standing rules in force (nothing deleted, every move receipted, keys never printed, no output
limits on the BOSS, 57,027 is the one measurement).

## Assumptions (correct me, or these stand)

1. Cycles 1, 2 and 3 KEEP their own pins (Greg's 2026-09-20 rule: cycle 1 repeats the second group, and so on).
   Cycle 0 gains the three groups as a BEDROCK set required in addition to its own group. The pin file's exclusivity
   (every registry layer pinned to exactly one cycle as its own) holds; the bedrock is an addition on cycle 0 only.
2. The bedrock layers are derived on the box by the PINNED producers (lineage `ccode/frankie-receiver-feed-20260916`
   at `2ebb8ce8`, the checkout the box already holds at /opt/frankie-box/producers), through the canonical traversal
   those producers define (`native_replay_driver.NativeReplayDriver`, the launch in `native_a_arm_launch.py`), not
   by new arithmetic written here. The session code projects the driver's exact ledgers into the 20 layer files by
   the producers' own crosswalk (`native_layer_crosswalk.py`), which names, for every layer, the module, symbol,
   carrier and ledger sections.
3. Changing cycle 0's pin re-renders the request on the host (the pin is rendered into the instruction; the
   request_sha256 changes; the config hash changes). That is a host step in the runbook (supersede the principal
   request, export, fetch), each on Greg's go.
4. The exhaustion/D teach-back is filed in the docs bundle and the brain entry and as a section of analysis.md, NOT as a
   new key of response.json: the host's response schema and the host classroom grader stay unchanged (Greg: "host
   grader unchanged").

## The measured constraint (arithmetic, not a choice)

Cycle 0's rows are the first `T_CTX = 3,262` INPUT records of the 20211003 prefix: ts_recv 1633298400.30 to
1633298413.31, about 13 seconds, 2,282 F_LAST groups, 91 trades, 1,482 legacy rows (cycle 0's own derivation digest).
The pinned candidate lane opens with `warmup_seconds=900` and `min_threshold_observations=600` (hardcoded in the
driver, declared in the crosswalk's HARDCODED_WINDOWS). On a 13-second slice NO candidate can be detected, so every
layer whose carrier is the `episode` or `candidate` lifecycle section will hold ZERO rows on cycle 0:
`prebirth_predecessor_at_risk_state`, `prebirth_stopped_chain_false_context_controls`, `prebirth_negative_opportunity_cases`,
`clock_prospective_discovery_confirmation`, the dipole-state half of `derived_roll20_and_dipole_state` and the
episode half of `derived_unresolved_age_chain_trajectory`. They are filed `could_not` with the MEASURED reason (slice
span vs warmup), never `derived` with an empty table. `clock_lock_time` has NO_PRODUCER_FOUND by the crosswalk's own
search (lock time is Frankie's OUTPUT, his first-locks ledger) and is filed so. `clock_model_evaluation` is a declared
CONVENTION on the row (decision_basis REPLAY_EARLIEST_LAWFUL_AVAILABILITY) and is filed derived with that note.
What a 13-second slice DOES yield: lineage (D-depth, ancestry, open lineages) on 2,282 groups, the seven clocks per
group, the per-second flow substrate, the book path per group (4.2), queue/FIFO features (4.6), family descriptors and
open-world state per group. The whole-day run (all 57,027 records, ~hours) is the only way to reach the candidate lane;
that is Greg's call, not this spec's.

## Capability map

| Module id | Responsibility | Depends on |
|---|---|---|
| pin-bedrock | cycle 0's pin carries a `bedrock` list (the three groups verbatim: layers, calculations, source receipts, producers); the loader validates it; the instruction renders it as required; the adapter tests cover it | - |
| box-bedrock-derive | the box derive stage runs the pinned driver on the cycle's rows and projects the 20 layers from its exact ledgers into `work/derived/`, each with status, producer, carrier and reason; the digest carries them; the comparison packet covers them | pin-bedrock |
| box-teach-exhaustion | one BOSS teach-back on exhaustion and D from the session's own bedrock facts and the frozen learned-structure files, transcription-checked by code, filed in docs, brain and analysis | box-bedrock-derive |

Build order: pin-bedrock -> box-bedrock-derive -> box-teach-exhaustion. The host runbook change rides pin-bedrock.

## Objective

Cycle 0's rerun derives, on the box, from the pinned producers, the 25 layers Greg calls the bedrock (5 legacy + 8
derived geometry + 5 pre-birth + 7 clocks) instead of 5, files each with an honest status, reads its own derivation,
and teaches back exhaustion and D beside the Dipole classroom, so the response, the analysis, the accounting ledger
and the brain entry rest on the base the later calculations build from.

## Tech stack and commands

Python 3.11 stdlib on the box (the producers checkout needs nothing beyond stdlib for the driver path; torch is not
imported by the driver). Tests: `python -m pytest -q -p no:cacheprovider tests/test_frankie_box_*.py
research/kalshi/frankie_boss/tests/test_frankie_principal_adapter.py research/kalshi/frankie_boss/tests/test_cycle_calculation_pin_loader.py`
from the repo root. Box suite must also pass with torch hidden (`PYTHONPATH=<dir with a raising torch.py>`).

## Design

### pin-bedrock
- `knowledge/CYCLE_CALCULATION_PINS.json`: pin 0 gains `"bedrock": [ {group, defined_on, registry_layers, calculations,
  source_receipts, crosswalk_producers} x3 ]` copied VERBATIM from pins 1-3, plus `"bedrock_rule": "Greg Davis,
  2026-09-21: ..."` at the document root. Schema stays V1 (additive field; the loader tolerates its absence on other pins).
- `load_cycle_calculation_pin`: when `bedrock` is present it must be a list of complete pin-shaped entries whose layers
  are registry layers and whose groups are pinned to some cycle of their own; malformed = refused.
- `calculation_pin_instruction`: after the pin sentence, `THIS CYCLE'S BEDROCK (Greg Davis, 2026-09-21): in addition,
  derive yourself ... <calculations>; the registry layers you must account for include <layers>; the accounting entry
  lists them beside the pinned layers, each with its own status and reason.` The sentence "layers of other cycles'
  pins are not required now" becomes "layers of other cycles' pins that are not in this cycle's bedrock are not required now".
- Sidecar `calculation-pin-witness.json` unchanged in shape (it carries the file witness; the hash moves).
- Tests: the pins test asserts bedrock groups are exactly the three, equal their own pins' layers and receipts, and the
  instruction carries every bedrock layer; the loader test refuses a malformed bedrock entry.

### box-bedrock-derive
- New module `deploy/aws/box/frankie_box_bedrock.py` (stdlib; loaded once through `_box_module`):
  - `driver_records(records, container)`: the session's INPUT observations (a mapping with ts_event, action,
    instrument_id, ...) each gain `source_dbn_object` = the prefix container path, `source_dbn_sha256` = its sha256
    and `raw_symbol` = the observation's own `raw_symbol`/`symbol` when present, else None. The driver refuses a record
    without a source object; the box's source object IS the verified prefix container.
  - `run(records, container, out_dir, producers, cycle, code_commit)`: builds `RunIdentity` (run_id
    `frankie-box-cycle-<NN>`, arm `A_MEMORY`, mission/contract sha256 from the checkout's
    `research/kalshi/agents/frankie_native_raw_mbo_{oct45_realtime_mission,calculation_contract}_20260828.md`,
    knowledge_manifest_hash from `KNOWLEDGE_MANIFEST_20260828.json`, source_manifest_hash = the container sha256,
    total_mbo_records = len(records), code_commit = the producers checkout commit), `NativeCalculationRun` with the
    launcher's canonical arguments (replenishment_horizon_ns 60e9, horizons `a-arm-h2`, the four response value names,
    alias_companion_keys False, sinks = `LedgerSinks(out_dir/'ledgers')`), `NativeReplayDriver(identity, session_rule=
    ExchangeSessionRule(), cadence=NeverInvoke(), run, sinks, emit_change_points=True)`. `NeverInvoke` is a declared
    CadencePolicy that never fires (the BOSS is invoked by the session's own stages, not inside the traversal); the
    receipt records `cadence_policy: NeverInvoke`. `consume(records)`, `finalize()`, `sinks.reconcile_all(...)`
    (a mismatch raises: a ledger that does not match its counter is not evidence). The result (minus the exact rows,
    which live in the ledgers) is written to `work/bedrock/result.json`; the ledgers stay under `work/bedrock/ledgers/`
    (`exact_member_rows.jsonl`, `exact_lifecycle_rows.jsonl`, `legacy_observable_rows.jsonl`).
  - `project(result, ledgers_dir, layers, crosswalk)`: for each of the 20 layer ids, the crosswalk record
    (`native_layer_crosswalk`'s LAYER table: module, symbol, carrier, member_paths, lifecycle_sections, notes) selects
    the rows: member rows projected to the named `member_paths` (plus the group key: `group_index`, `ts_recv_ns`,
    `f_last_ts_recv_ns`), lifecycle rows filtered to the named sections, whole. Each layer file
    `work/derived/<layer>.json` = {status, producer: `<module>.<symbol>` from the crosswalk, carrier, member_paths,
    lifecycle_sections, member_rows, lifecycle_rows, count, reason, notes}. Status: `derived` when count > 0;
    `could_not` with the MEASURED reason when count == 0 (the slice span in seconds against the candidate lane's
    warmup and minimum observations, read from the driver's own constants; or "section X emitted no rows");
    `could_not` NO_PRODUCER_FOUND for `clock_lock_time` (with the crosswalk's search note).
  - The session's `derive()` calls `run` then `project` after the legacy five (the legacy derivation stays byte-for-byte
    what it is), records `bedrock` in `derive.json` (result witness, ledger witnesses, reconciliation, span_seconds,
    warmup_seconds, sections_fed), and the layer files' witnesses under `layers` as today.
- Digest: `frankie_box_digest_render.SCHEMA` -> `DIGEST_V6`; `digest_text` gains the bedrock tables: one dense exact
  table per DERIVED bedrock layer (member_paths columns per group; lifecycle rows flattened by dotted key, nested
  values as `J...` cells), rendered by the existing `render_layers` (delta encoding, `^`, dictionary), so the reading
  corpus carries every derived bedrock fact whole. The V6 header names the new tables. The derive gate re-derives when
  the digest header is not V6 or `derive.json` does not carry `bedrock` for this pin (a pin change re-derives).
  MEASURE before any run: the token count of the V6 digest and the resulting part count (the read was 4 parts of 87k on
  V5); report it to Greg with the reading-lane cost per part before the rerun (success criterion 6).
- Comparison packet: the bedrock layers appear beside the frozen files exactly as the legacy five do (no change to
  `frankie_box_compare.py` beyond reading whatever `derive.json` lists).
- Writing: the accounting prompt already lists every layer in `derive.json`; add one sentence: a bedrock layer is
  accounted for like a pinned one, with its own status and reason.

### box-teach-exhaustion
- New stage `teach` after `classroom`, before `writing`; durable (`work/teach/`); one BOSS call on the Pod (no output
  limit), retried once like the classroom (`_classroom_call` with lane `boss`).
- Facts (pre-message, computed by code from the session's own files, small and exact): per bedrock layer its status,
  count and reason; from the lineage rows the D-depth histogram (depth -> groups), open vs closed lineages, ancestry gap
  quantiles listed per event (no average as a verdict: the largest gaps named); from the clocks rows the order check
  (event_known_by <= feature_availability <= model_evaluation) pass count; the family descriptor counts (top action
  strings); the candidate lane's measured verdict (span vs warmup); and the frozen learned-structure files' TEXT for the
  four layers that define D and exhaustion (`learned_d_structures_and_families`, `learned_dipoles_and_geometry`,
  `learned_chains_extensions_reappearances_ancestry`, `predecessor_ancestry_unresolved_chain_state`) from the brain's
  frozen entry, whole (measured: they fit the part budget; if not, the stage refuses with the sizes and Greg decides).
- Answer (one JSON object): `{"exhaustion": {"what_it_is", "how_this_cycle_shows_it", "what_this_cycle_cannot_show",
  "relation_to_dipole_state"}, "d_depth": {...same four...}, "families": {...}, "prebirth": {...}, "clocks": {...},
  "questions": [...]}`; every number the BOSS cites must exist in the facts (the classroom's transcription check,
  applied to numbers); a missing topic or a number not in the facts = unusable answer (retry, then refuse with receipt).
- Filed: `work/teach/exhaustion-teachback.json` (facts hash, answer, call witness), `.md` in the docs bundle
  (`exhaustion-teachback.md`), the brain entry (include true), and a section of analysis.md written by the writing
  stage from the file ("THE EXHAUSTION AND D TEACH-BACK"). NOT in response.json.

## Project structure

- `research/kalshi/frankie_boss/knowledge/CYCLE_CALCULATION_PINS.json`, `frankie_principal_adapter.py` (loader, instruction)
- `deploy/aws/box/frankie_box_bedrock.py` (new), `frankie_box_boss_session.py` (derive, teach, run order, writing prompt),
  `frankie_box_digest_render.py` (V6), `frankie_box_docs.py` / `frankie_box_brain.py` (the teach-back and bedrock files)
- Tests: `tests/test_frankie_box_bedrock.py` (new: driver records, projection, statuses, NeverInvoke, a real driver run on a
  synthetic 3-group stream from the checkout's own test fixtures), `tests/test_frankie_box_boss_session_teach.py` (new),
  `tests/test_frankie_box_digest_render.py` (V6), `research/kalshi/frankie_boss/tests/test_frankie_principal_adapter.py`
  and `test_cycle_calculation_pin_loader.py` (bedrock)
- Docs: this spec; `CLAUDE_HANDOFF_20260920.md` (the runbook change); `DROP_IN_CLAUDE_20260921.md`; `KALSHI_TRADING.md`

## Code style

Stdlib, pure functions with the session as the only caller, every file written whole with a witness, statuses never
inferred from absence (a zero-row layer says WHY), docstrings that name the rule and who set it. Example:

```python
def status_of(count, section_dependent, span_seconds, warmup_seconds, min_observations):
    """`derived` when rows exist; otherwise `could_not` with the measured reason, never an empty `derived`."""
    if count:
        return 'derived', None
    if section_dependent:
        return 'could_not', (f'the candidate lane needs {warmup_seconds} s of warmup and {min_observations} observations; '
                             f'this cycle\'s rows span {span_seconds:.1f} s')
    return 'could_not', 'the traversal emitted no rows for this carrier on this cycle\'s rows'
```

## Testing strategy

TDD per module. Unit: pin loader/instruction; `driver_records`; `project` on synthetic ledgers; `status_of`; the teach
facts and the number transcription check; the docs/brain inclusion. Integration: the driver run on the checkout's own
small fixture stream (the producers' tests carry one) proving `consume -> finalize -> reconcile -> project` end to end
with torch absent; the session `derive()` with a stub prefix. Text contracts for the prompts. No box, Pod or host run.

## Boundaries

- Always: run the box suite torch-present and torch-hidden; keep the legacy five byte-identical; receipts for every file.
- Ask first: any change to the host response schema or the host classroom grader (none planned); the whole-day run;
  any change to the pinned producers (none: they are pinned bytes).
- Never: derive a bedrock layer by arithmetic written here instead of the pinned producer; file an empty table as
  `derived`; run anything on the host, box, Pod or endpoint without Greg's go; print a key.

## Success criteria

1. `load_cycle_calculation_pin(0)` returns the bedrock; the instruction carries all 25 layers; adapter tests green.
2. On the checkout's fixture stream, `frankie_box_bedrock.run` completes, reconciles, and `project` writes 20 files whose
   statuses match the rules above; torch hidden.
3. Session `derive()` writes 25 layer files and a V6 digest; the derive gate re-derives on a pin change.
4. The teach stage files a validated teach-back on a stub BOSS; a number not in the facts is refused.
5. Box suite and host contract suites green; docs bundle and brain entry include the new files.
6. MEASURED before the rerun: the V6 digest's token count, the part count, and the reading-lane cost, reported to Greg.

## Open questions (for Greg)

- The whole-day run (57,027 records) is the only way the candidate lane fires on cycle 0; the 13-second slice cannot.
  Run the bedrock on the slice now (this spec) and the day later, or hold for the day?
- Reading cost: the bedrock tables enlarge the digest; the part count will be measured (criterion 6). Accept the parts,
  or cap the digest to the carrier columns only (this spec's default) and put the whole ledgers in the bundle only?
- The pin's bedrock reading (assumption 1): cycles 1-3 keep their pins. Or should cycle 1 now start at order_lifecycle?
