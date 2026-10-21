# Frankie downstream classroom integration — handoff, 2026-10-21 ~16:35 UTC

Written by the Claude cloud session that continued the downstream classroom work on main over SSM.
Read this, then on the box: `/opt/frankie-box/work/handoffs/downstream-classroom-new-chat-20261021.md`
(its two appended updates) and the two new receipts named below.

## Exact resume state

- AWS account 568968024170, us-east-1. Main i-035994afa8bdf66a5 (SSM Online).
- Source `/opt/frankie-box/work/source-indexed-consumers-20261021`, branch `codex/indexed-consumers-20261021`.
- HEAD `dd5c8d0`, tree clean. History: `a7cf1df` (previous verified reproduction progress) -> `7f0dcdc`
  (answers, notes, JSON, renderer WIP committed with the review fix) -> `dd5c8d0` (streamed C15 hash module).
- Commits are `[skip ci]`, private, not pushed. Nothing deployed, no admission opened, no model or scientific
  run, no Search, BuildMap, instance, owner, booking or ingestion change. No leftover `/dev/shm` scripts or
  `/tmp/classroom-*` fixtures.
- The other window's work and the parked Search state were not touched.

## What was verified and fixed (increment 1, commit 7f0dcdc)

All seven WIP files matched the 10:19 EDT manifest (`classroom-answer-wip-20261021-101932-EDT.json`)
before one edit.

The edit: `deploy/aws/box/frankie_box_retained_classroom.py`, `Values.render_cell`. The generated version
replaced the literal two-character sequences backslash-r and backslash-n instead of CR and LF, and escaped
a pipe with two backslashes where native `_cell` uses one. It now applies the exact native rule (CR and LF
to spaces, one backslash before a pipe, three backticks to three apostrophes), lazily on a retained Text via
the store's streaming `replace`, and through `str()` for anything else.

Receipt `/opt/frankie-box/work/handoffs/indexed-classroom-render-notes-20261021.json`:

- Renderer, before the fix: retained Markdown differed from native at byte 1766 (classroom) and 267
  (external); the two empty-section cases were already identical.
- Renderer, after the fix: five cases byte-identical to native (CR, LF, CR LF, pipes, backslash-pipe,
  fences, backticks, non-ASCII, empty cells, None developing_structure, the 2000-character dropped-finding
  prefix, grade present and absent, empty sections, and a multi-piece retained Text splitting CR LF and a
  fence across pieces). Native default output of both renderers equals HEAD (the external one loaded from a
  `git archive HEAD` tree in a subprocess because of its relative imports). Reuse returns identical text.
- Notes: per-note save and resume (stop after 2 saves exits 75; resume computes only f3..f5; completed
  reuse computes nothing; result equals `K._knowledge_notes`; component, recognized and pair filters correct).
- Interrupted append (crash after two committed notes) leaves 2 rows, resume completes equal to native.
- Lost committed population under a partial index refuses with
  `partial note index lost its committed population`.
- Retained-text identity name refuses with
  `retained note identity names require native text before index admission`.
- HEAD and WIP `input_digest` and `bindings` equal on ten native inputs (old identities stay valid).
- A changed sealed dependency (one byte appended to the referenced catalog) refuses on reuse and on open
  with `immutable search catalog changed; retained`.

## New module (increment 2, commit dd5c8d0)

`deploy/aws/box/frankie_box_classroom_hash.py`: `pieces`, `evidence_bytes`, `evidence_hash`. It emits
`c15_journal.pack`'s tagged tree exactly as `json.dumps(..., separators=(',', ':'), ensure_ascii=True)`
would, piece by piece over retained Text, Sequence, note views and saved documents, and hashes with the
same C15 prefix. `c15_journal` itself is untouched.

Receipt `/opt/frankie-box/work/handoffs/indexed-classroom-c15-stream-20261021.json`:

- Native payload: bytes equal the native fast AND legacy encodings, hash equal (insertion-order dicts, big
  ints, -0.0, 1e300, 5e-324, NaN, -inf, unicode and escapes, empty containers, nesting, tuple, bytes,
  FrozenList, MappingProxyType).
- Refusals identical to `pack` (float key, set, object, numpy float64); PrePacked is refused here with its
  own message and left to the native encoder.
- Retained document: dict, joined Text, Sequence, lazy CR/LF replace, nested Sequence of joined Text, and a
  long split text all equal their native materializations field by field, as a whole SavedValue and by hash.
- Note view equals its native list (also a component selection).
- 300 random native trees equal.
- Known boundary: retained storage is JSON, so tuples read back as lists and bytes cannot be retained;
  the hash of a document read back therefore differs from a native tuple-bearing payload exactly as the
  native hashes differ.

Not wired anywhere yet.

## The next seam (read, not changed) and the design question for Greg

Where retained answers meet the native host:

- `research/kalshi/frankie_boss/dipole_classroom_external.py`: `validate_external_ledgers(ledgers, pre)`
  (~line 1086) uses `type(x) is dict/list` and `_text()`; `grade_external(key, ledgers)` (~1159) sets
  `teachback_hash=evidence_hash(ledgers)` (~1221); `finish_external` (~1256). `render_markdown` already
  takes `_values`.
- `deploy/aws/box/frankie_box_classroom.py`: `assemble(visible, outputs, summary)` (line 444) builds native
  dicts and lists and copies `out[field]` for NARRATIVE, so retained Text would sit inside native structures
  and novel findings pass `validate_novel_findings`; `validate(visible, ledgers)` (line 496) runs the repo
  validators.
- `teacher_message_hash`, `external_binding_hash`, `model_visible_hash` are pre-message bodies with no
  retained values and need nothing.

The private path can now render exact Markdown and hash ledgers identically without materializing, but
shape and text validation and grading still require native str and list. Options, neither started:
(a) a retained-aware private validator and grader applying the same rules element by element over Text and
Sequence views, proven equal to the native validator on materialized fixtures; or (b) materialize once at the
host boundary for validation only. The handoff rule stands: never weaken the native validators; ordinary
indexed admission stays closed until complete consumer integration is verified.

Also still open from the original item 5: shared-market input text (the private wrappers refuse it
explicitly), actual corpus and model evidence delivery (no model calls), the narrow nonempty measured indexed
science composition check, and the `_canon` `json.loads` round trips in the external key and grade path.
The six substantial downstream groups from the 13:08 checkpoint remain open beyond these.

## Constraints carried forward

Private source only. Explicit `git add` paths, `[skip ci]`, no public push. Reuse the receipts above and
the earlier ones; no broad reruns. Remove synthetic fixtures immediately. Preserve the original draft
(`indexed-survivor-original-20261021.draft`, sha256 4c52480d...e34c5), all saved work, all 30-day
ingestion copies including helper copies, the other window's checkouts, the parked Search state, and the
exact owner and bookings. Do not touch Search or use BuildMap. Never replace evidence or text with
descriptor metadata, silently skip values, weaken native validation, refresh frozen inputs or invent
confirmations.

## Working method that worked

AWS CLI through SSM `send-command` / `get-command-invocation` (the AWS MCP connectors were down; the
container's placeholder AWS env vars must be unset so the real pair is used). Box runtime for all checks:
`/opt/frankie-box/venv/bin/python`. Check scripts as heredocs into `/dev/shm`, run from the source root,
removed in the same command; fixtures in `tempfile.mkdtemp`, removed in `finally`. SSM output is capped at
about 24 KB per command, so large reads go in chunks.

---

# Update, 2026-10-21 ~17:45 UTC: ownership confirmed, host mirrors landed

The other window confirmed (screenshot relayed by Greg) that this window owns the classroom and
external-ledger validation, grading and streaming-hash integration; it keeps Search's calculation and
checkpoint ledger and the deployment. Two more increments landed on the box branch after `dd5c8d0`.

## Exact resume state

- Source `/opt/frankie-box/work/source-indexed-consumers-20261021`, branch `codex/indexed-consumers-20261021`,
  HEAD `caab10a`, clean. History: `a7cf1df` -> `7f0dcdc` (answers, notes, JSON, renderer) -> `dd5c8d0`
  (streamed C15 hash) -> `45dc7ff` (external host mirror) -> `caab10a` (classroom host mirror). All `[skip ci]`,
  private, not pushed.
- Receipts in `/opt/frankie-box/work/handoffs/`: `indexed-classroom-render-notes-20261021.json`,
  `indexed-classroom-c15-stream-20261021.json`, `indexed-classroom-external-host-20261021.json`,
  `indexed-classroom-host-20261021.json`. Checkpoints appended to `downstream-new-chat-20261021.md`.
- Nothing deployed, no admission opened, no model or scientific run, no Search, BuildMap, instance, owner,
  booking or ingestion change, no leftover fixtures.

## The method used for the host seam (design decision taken by this window)

The native validators and graders stay byte-identical and still refuse retained values. Each private mirror is
the native function's own text with recorded substitutions only, generated programmatically from the source,
not retyped: exact `dict`/`list` type checks become `is_dict`/`is_list` (a saved document or a retained
Sequence/Notes view beside dict/list), `_text`/`_nonempty` become a streamed nonempty check over a retained
Text's pieces, `_same`/`_canon` become a streamed canonical compare, `evidence_hash` becomes the streamed C15
encoding, `list(questions)` becomes a retained sequence under a store, and the grade body's native
`json.loads(_canon(body))` becomes an owned copy with sorted string keys that keeps retained views as
references. Every accept, every refusal message, every normalized result and every hash is proven equal to
the native function on the materialized value.

## `45dc7ff` frankie_box_retained_grading.py (external section)

`validate_external_ledgers`, `grade_external(values=)`, `correction_request`, `finish_external`, and
`retain_grade(path, key, ledgers)` which seals a retained ledgers document's post-grade as its own document
with reuse. Proven: accept counts equal; all 26 refusal messages equal across native, mirror-on-native and
mirror-on-retained (plus a whitespace-only retained Text); grade fields, both corrections, teachback and
post-grade hashes equal; correction request and completion equal including `request_sha256` and
`completion_hash`; the streamed hash of the retained grade equals the native hash; native still refuses.

## `caab10a` frankie_box_retained_host.py (classroom side)

`validate_teachback`, `_claim_components`, `_claim_relationships`, `validate_novel_findings`,
`assemble(values=)`, `validate`, with `_observation_explanation` extending a sealed Text in the writable
assembly store (the one place native code would write into a read-only source; fixed in the mirror only).
Proven on a full 19-component, 171-pair fixture in GUIDED and TEACH: assembly and dropped findings equal,
validate report equal on native and retained, C15 ledger hash equal, rendered Markdown equal, all 45 refusal
messages equal; native still refuses retained ledgers.

## What the private path can now do, end to end, without materializing retained text

Build the note index and the component, summary and external answers; assemble and validate both ledger
sets; render exact Markdown; hash with the native C15 encoding; grade, request correction and finish the
external section. Each step is proven against native.

## Still open, in order

1. Runner wiring: `frankie_box_experiment_classroom_v2` phases (`assembly`, `answer_report`,
   `external_report`, grade and `external_finish`) still call the native functions. Wiring the private path in
   behind an explicit opt-in, with ordinary admission still closed, is Greg's call.
2. Classroom-side grade, correction and transcript consumers beyond `validate`.
3. Shared-market input text (private wrappers refuse it explicitly), actual corpus and model evidence
   delivery (no model calls), the narrow nonempty measured indexed science composition check, and the
   `_canon` round trips in the external key path.
4. The six substantial downstream groups from the 13:08 checkpoint beyond these.
