# Spec: bedrock-section-tables (sections 4.2 and 4.4 as V6 tables; Greg, 03:2xZ 09-22: "We are going to have to take care of that")

Greg's ask: the two pieces that "somehow got dropped" (4.2, the daily book regime companion; 4.4, the mirror matcher) must
reach Frankie as TABLES he reads, not as a document (bedrock-result.md) and a ledger reference. Both RUN in the pinned
producers (2ebb8ce8: `native_calculation_runner.sections` registers "4.2": BookRegimeCalculator and "4.4": the mirror;
the driver offers every closed group to the mirror and finalizes it at stream end; 4.2 observes every full-book snapshot).
What is missing is one projection on the BOX side: the crosswalk names no layer whose lifecycle section is `mirror` and no
layer at all for 4.2's companion rows, so `frankie_box_bedrock.project` never files them and `bedrock_tables` never renders
them. This spec adds that projection. The producers are NOT changed (the pin is the identity of the run).

## Objective
After the bedrock traversal on the box, two more files stand beside the twenty crosswalk layers in work/derived/ and the
DIGEST_V6 carries their rows as tables:
- `bedrock_section_4_2.json` -> tables `bedrock.companions.4.2` (one row per stratum per measure: measure, kind, the
  stratum fields, excluded_missing_members, the value fields; six measures: book_spread_raw, book_total_depth,
  book_order_count, book_level_count, relative_imbalance, actions_per_group), `bedrock.declarations.4.2` (one row per
  measure: numerator_formula, population, causal_cutoff, status, missingness_rule; the declaration once, not per stratum)
  and `bedrock.first_last.4.2` (one row per day-segment-phase: source_day, source_role, continuity_segment,
  session_phase, first_book.*, last_book.*).
- `bedrock_section_4_4.json` -> table `bedrock.lifecycle.mirror` (every lifecycle row whose emitting_section is `mirror`,
  whole, in ledger order: the offers at GROUP_CLOSE with disposition PENDING or PAIRED and the finalize rows at
  STREAM_END with disposition UNMATCHED and their reason) and `bedrock.matching_rule.4.4` (one row: the rule 4.4
  declares in its summary, rule_id, distance_bound, selection, attribution, lookahead, ...).
Every number comes from the traversal's own result.json (`averaged_companions.rows` filtered to section "4.2";
`exact_lifecycle_and_runway_ledger.section_summaries["4.2"]` and `["4.4"]`) and the exact lifecycle ledger
(`ledgers/exact_lifecycle_rows.jsonl`); the box computes nothing. Each file has the project() file shape (layer, kind,
producer, file, line, status, reason, count, member_rows=[], lifecycle_rows, companion_rows, section_counts, summary,
crosswalk_commit, traversal) so `bedrock.layers` indexes them like any layer and `status_of` gives a zero-row file its
measured reason, never an empty `derived`.

## Tech stack
Python 3.12 stdlib on the box (`deploy/aws/box/frankie_box_bedrock.py`, `frankie_box_digest_render.py`,
`frankie_box_boss_session.py`); the pinned producers reached through the in-repo worktree `.producers-2ebb8ce8`
(`bash deploy/aws/box/producers_checkout.sh`; tests/_producers.py) and on the box at /opt/frankie-box/producers. No torch on
this path. The DIGEST_V5 table grammar unchanged; V6 gains tables, not marks (the header sentence names the new tables).

## Commands
    bash deploy/aws/box/producers_checkout.sh
    python -m pytest -q -p no:cacheprovider tests/test_frankie_box_bedrock.py tests/test_frankie_box_digest_render.py tests/test_frankie_box_boss_session_derive.py tests/test_frankie_box_docs.py
    # the codecs CI list (.github/workflows/frankie_box_codecs_ci.yml) stays green torch present and hidden

## Project structure
    deploy/aws/box/frankie_box_bedrock.py            project_sections(result_path, ledgers_dir, out_dir, receipt): the two files (BR-9)
    deploy/aws/box/frankie_box_digest_render.py      bedrock_tables: companion_rows -> bedrock.companions.<section>, declarations, first_last, matching_rule
    deploy/aws/box/frankie_box_boss_session.py       _derive_bedrock: project_sections after project; the two entries into receipt['layers'] (bedrock=True)
    deploy/aws/box/frankie_box_docs.py               the two files referenced by name, bytes, sha256 like every bedrock layer file (no change if the loop is generic)
    tests/test_frankie_box_bedrock.py                RED first: project_sections on the fixture stream's own result.json and ledgers
    tests/test_frankie_box_digest_render.py          RED first: the four new tables render, parse back and equal the rows
    tests/test_frankie_box_boss_session_derive.py    RED first: derive.json lists bedrock_section_4_2 and bedrock_section_4_4 with bedrock=True

## Code style
The house style of frankie_box_bedrock.py: nothing computed here, the producers' own numbers copied whole; a zero-row file
says WHY (`status_of`); every file written with a witness; stdlib only; the crosswalk commit stamped on the file. Table
names follow `bedrock.<kind>.<section>`; a nested value flattens to dotted columns by the codec (the existing `_nest` /
`_flatten` pair), a mapping the table cannot spell becomes one JSON string cell (the existing rule).

## Testing strategy
- TDD: each of the three test files gains its RED test before the code. Fixtures = the existing journal-shaped fixture
  stream (`tests/test_frankie_box_bedrock.py: stream()`, three F_LAST groups) run through the PINNED driver; the 4.2 rows
  and the mirror rows asserted are whatever that traversal emits (counts read from the run, not invented). Zero synthetic
  market data.
- The render test asserts round-trip: `render_layers` -> `parse_digest` equals the tables (the codec's own self-check).
- The docs test asserts the two files are listed by name, bytes and sha256 in the bundle index.
- The codecs CI list runs torch present and hidden (the bedrock path never imports torch).

## Boundaries
- Always: the producers untouched (no file under research/kalshi/frankie_raw_mbo_benchmark at the pin changes); every
  row copied whole; `bedrock.layers` indexes the two files; a zero-row file is `could_not` with the measured reason.
- Ask first: any table beyond the six named here; any change to the V5 grammar; reading the mirror's PAIRED rows from
  `summary()` instead of the ledger (the ledger is the exact record; the summary is a count).
- Never: recompute a 4.2 statistic on the box; drop a mirror row; alias keys; change the twenty crosswalk layers; run on
  the box before Greg's word (the rerun's read is the first time these tables are read).

## Success criteria
1. On the fixture stream (MEASURED 2026-09-22 by running the pinned driver on tests/test_frankie_box_bedrock.py's stream():
   195 averaged rows of which 6 are section 4.2, one per measure, one stratum; one first_last pair; 50 lifecycle rows of
   which 6 are `mirror`: 3 PENDING offers at GROUP_CLOSE and 3 UNMATCHED at STREAM_END, reason NO_COUNTERPART_IN_SCOPE;
   4.4's summary: members_seen 3 = 2 x 0 pairs + 3 unmatched): `bedrock_section_4_2.json` status `derived` with those
   6 companion rows and 1 pair; `bedrock_section_4_4.json` status `derived` with those 6 lifecycle rows.
2. `bedrock_tables` returns `bedrock.companions.4.2`, `bedrock.declarations.4.2`, `bedrock.first_last.4.2`,
   `bedrock.lifecycle.mirror`, `bedrock.matching_rule.4.4`, all parsing back equal.
3. derive.json's layers carry the two entries with bedrock=True; the digest header names the new tables; the docs bundle
   lists the two files.
4. The four suites green; the codecs CI list green torch present and hidden; nothing under the producers pin changed
   (`git -C .producers-2ebb8ce8 status --porcelain` empty).
5. Checkpoint E (on Greg's go, box only, no model call): `ACTION=derive_only` re-measures the V6 digest with the new tables;
   the size delta reported to Greg (the reading cost is his call 2).
