# Step 4 module, API and AWS workflow review — 2026-10-07

SOURCE-REVIEWED / RUNTIME-UNVERIFIED. Initial checkout: `ccr-5fce7de3-xa4hfg`,
`439cb0bf71968f30f94b696b85acfaa00dccc3c1`; concurrent source changes preserved.
Read AGENTS, current night handoff, current CCode Step 8A assignment/returns and
Step 4 route report. Applied using-agent-skills, context-engineering, API and
Interface Design, git-workflow-and-versioning and performance-optimization.
AWS documentation search returned the exact `aws-compute` skill; read it and its
`references/systems-manager.md`. No AWS account tool or action was called.

## Actual contracts and callers

| Boundary | Actual contract | Active consumer / status |
|---|---|---|
| `Run.search_knowledge` -> `review.search_findings` | Complete owning manifest/parts, exact row provenance; uses existing `count_margins` and role classifier, retains every valid beyond-chance row separately | Writes `FRANKIE_SEARCH_FINDINGS_V1`; brain search stage; source arithmetic review is not independent scientific verification |
| `candidate_claims_doc` | Findings -> one claim per row; exact series, transform pair, cell/value, oriented lag, original day, source counts and part/row hashes | Called by accumulated teacher; exact matching prevents fuzzy name expansion; no rarity threshold or pooling |
| `load_searches` -> `test` | Full owner-local search parts, including null/contradictory rows; exact claim projection | Called by standalone scientific CLI and accumulated teacher; amended below to verify actual consumed bytes |
| `test` -> lesson result | One result per claim; scoped rows, `held`/`shown_otherwise`/`counts_only`/`unresolved`; mirror provenance retained without double counting | Scope exclusions are explicit; orientation disposition is not survivor acceptance |
| Discovery origin -> exchange | Exact part SHA, row ordinal and raw-line SHA identify the discovery row; origin rows stay outside tests/occurrence counts | `origin_evidence_accounting` calculates existing margins once; both teacher seats consume that accounting, never another observation |
| `teach_accumulated` | Frozen selection and reader witnesses; per-claim content key; own search manifest; reproduction selection; deterministic result identity | Called by exchange and non-classroom accumulated stage; publishes search lessons through existing brain writer, including origin-only lessons |
| `Run.lessons` / `frankie_lessons` | Historical/Jev/Frankie standalone batches over finished searches | Local path is called; remote owner aggregation remains absent; recovery coverage defect below |
| Survivor/acceptance | No defined writer or adopted scientific promotion rule | Existing survivor consumers do not establish a producer; step remains open |

No ID/day/weekday becomes a numeric signal through these adapters. Original day and
cell/value stay attached to the underlying market quantities. Historical bindings,
full reproduction work, nonlinear/multivariable discovery coverage and teacher
coverage remain broader open work; this review does not close them.

## Corrected source defect: exact search-part evidence binding

Previously `load_searches` copied SHA values out of the manifest; `test` read text
lines and labeled them with those values without hashing the files it consumed.
The standalone route had no part verification. Accumulated teaching separately
hashed parts before reopening them, which did not bind the subsequent read itself.
Text-mode newline normalization could also change a raw discovery-row hash.

With root's explicit disjoint ownership grant, changed ONLY `load_searches` and
`test` in `deploy/aws/box/frankie_box_scientific_teacher.py`:

- Read manifest bytes once and derive parsed manifest/hash from that same read.
- Require a part SHA and owner-local, nonrepeated resolved paths; preserve optional
  manifest byte counts. Recheck path ownership at actual consumption.
- Stream binary lines, hash/count all part bytes while parsing, and refuse a SHA
  or declared byte-count mismatch before any results are returned.
- Bind row provenance to the actual raw line, preserving newline bytes.

No formula, count, lag, condition, certainty threshold, output projection or
occurrence rule changed. Existing missing/unpinned part evidence now refuses
instead of being described as authenticated. No validator framework was added.

Source checks: AST parse without project imports and `git diff --check` passed.
No tests, imports of project modules, synthetic exercises, installations, data,
scientific, reproduction or model runs occurred. No commit/push by this agent.
The parent owns concurrent standalone freeze/write/main edits; they are not this
agent's patch.

## Caller correction completed after ownership extension

Root relayed Greg's instruction to implement the findings and granted these exact
additional functions: `Run.lessons` reuse branch, `Run.lessons_written`, and queue
`frankie_lessons`. No other runner or queue function was edited by this agent.

- Retained results must have an exact standalone scientific operation. Reuse reads
  current claims and requested manifests, invokes the existing `freeze_operation`
  compatibility check on the retained pair, then uses REVIEW's existing operation
  validation and correction-dependency guard across local/transported knowledge.
- Jev selection uses the requested stamp, not every file matching its day.
- A changed or legacy result produces an explicit waiting receipt with the pending
  claim/requested search days. Prior results stay intact; no implicit successor or
  scientific call is triggered by failed reuse admission.
- Queue reuse first checks current search completion and remote ownership and
  passes the actual requested day set. It no longer reuses before knowing which
  searches the operation must cover. A new successful call receives the same
  coverage check before completion is credited.
- Coordinated with Step 7: reused Jev results call its existing exact-byte
  `upload_jev_lessons` recovery hook before brain publication.

All three modified source modules parsed via AST without project imports; the
workspace whitespace check passed. Runtime remains unverified.

## Findings and remaining minimal follow-ups

1. **Batch reuse coverage defect — corrected in source above.**
   Previously Frankie reuse checked only its claims digest and Jev used a day glob,
   allowing an older result to stand for expanded `searched_days`. Queue reuse
   passed an empty day list. Both now bind requested operation coverage. Missing
   contributions still need explicitly scheduled owner work; source admission is
   not an implemented cross-owner scheduler or scientific successor decision.

2. **Cross-owner batch completion is genuinely absent.**
   `Run.lessons` returns waiting if any completed discovery search is remote. The
   queue helper now also refuses remote contributions explicitly. Neither is an
   owner-result aggregation protocol. Preserve the refusal. The existing compact
   contract is `(run, owner_day, search_manifest_sha256, findings_sha256)` carried
   by the search brain entry; each owner calculates on its own full parts and
   returns input/claim/search/result witnesses. A main batch must track each exact
   owner contribution and may not credit one result to another day. No giant
   evidence copy, new worker pool or replacement discovery engine is warranted.

3. **Standalone candidate interface remains intentionally narrower.**
   CLI `--search-findings` requires another day and retains search results without
   publishing; accumulated teaching permits origin-only results and publishes
   through the brain writer. The blanket messages saying no brain writer admits
   author `search` are stale: `brain.write_lessons_entry` admits the author only
   with an owner-local `knowledge_retest`. Minimal documentation fix is to state
   that precise restriction. Do not remove it just to enable standalone publication.

4. **Single-occurrence completion still needs the scientific contract.**
   No minimum occurrence/day threshold appears in the candidate or accumulated
   path. Origin evidence is taught without pretending it is a second occurrence.
   The CLI other-day requirement must not become an acceptance requirement.
   Existing same-evidence arithmetic, other-day scoped counts, and the exchange's
   second instrument are distinct checks; none presently defines survivor
   acceptance. Equal validity/certainty/acceptance/survivor/teaching treatment for
   scientifically checked single occurrences remains mandatory. The missing
   scientific decision cannot be replaced with a new threshold or fabricated
   confidence, and the old frozen-confirmation draft remains unapplied.

## AWS and processing-speed review

Documentation only; exactly three held 16-CPU lanes remain the resource boundary.
The skill supports EC2/SSM operation, stable source versions and durable storage.
It does not supply a reason to introduce AWS Batch/Auto Scaling, another instance,
new storage, a service, installation or dispatch into this existing owner model.

| Option | Source finding / disposition |
|---|---|
| Hash while parsing | Implemented for correctness above. One sequential read both authenticates and parses all rows; no extra pass in the scientific reader, no evidence reduction |
| Remove accumulated prehash pass | Parent removed `teach_accumulated`'s redundant `parts_verified` loop after the shared-reader fix. This eliminates one complete extra part read for a new operation while the scientific reader verifies its actual bytes. No measured speedup claimed |
| Scan across all documents once | Current `ST.test` scans parts per selected document. A future owner-local operation could share an exact-pin row index across claims, but full-memory amplification/restart identity require review. Not implemented or needed for the integrity fix |
| Parallelize owner contributions | Reuse the three existing lanes and their ownership; never share giant source parts. Requires the missing owner-contribution contract, not higher worker counts |
| Tune block-device read-ahead | Deferred. AWS documents 1 MiB read-ahead specifically for large sequential reads on HDD `st1`/`sc1` and warns it degrades random I/O. Current actual volume type/workload was not inspected, so no tuning, resize or recommendation is justified |

AWS source: [Amazon EBS volume performance](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-performance.html).
The AWS skill/reference were retrieved through documentation tools, not account
inspection. Performance guidance requires measurement; the user's source-only
hold supersedes measurement runs. No timing or throughput gain is asserted.

## Follow-up Step 5 interface review and assigned corrections

Root requested a fresh review of the standalone/partial-successor increment.
The review found implicit changed-search transitions, whole-document coverage
credit for unchanged old results, dropped historical collection context, missing
search-classifier reader pins, and a live-versus-frozen historical-record mismatch.
Root corrected the transition, per-claim scope/deduplication and reader-pin items;
the exchange owner is updating per-claim scope/native-reference consumers.

This agent received and completed these additional disjoint corrections:

- `scientific_teacher.freeze_operation`: choose the already frozen reproduction
  selection on resume (or capture it once on first use), then reconstruct historical
  claims/reconsideration with exactly that selection. Source bytes, stamp and legal
  claims must still equal the parser input. The operation summary and tests now
  consume the same evidence.
- `scientific_teacher.main` and the historical branch of `Run.lessons_written`:
  initial historical projection uses an empty explicit record selection, avoiding
  a live record-directory read before the operation establishes its selection.
  Main subsequently uses `frozen.selection.doc` for both test and write. Later
  reproduction records cannot mutate a pending or completed frozen operation.
- `teacher_knowledge` result identity: preserve original historical collection
  context and add `knowledge_retest.reconsideration_origin` when corrected claims
  first change its claim-source digest. This stores the original claims digest and
  original result witness; subsequent successor and ordinary teaching chains carry
  the existing origin unchanged.
- `review._validate_transition`: enforce the unchanged collection and exact origin
  binding for the accumulated successor. Coordinated exchange consumer uses that
  provenance without needing private source files on another lane. A correction
  adding origin metadata must scope the enclosing `knowledge_retest` object;
  its individual new field does not exist in the original lesson.

AST parsing without project imports and whitespace checking passed after these
changes. No scientific calculation, reproduction, test or model ran. Two final
boundary observations were sent to root for its owned correction guard and final
integration: transition admission must also consider changed search/operation
bindings when claim inputs are identical; direct standalone CLI reuse needs the
same current-correction publication guard as runner reuse.

Final assigned boundary fix completed: standalone main now checks the retained
lesson against current local/transported corrections before Jev upload or brain
publication. It hashes the same result bytes that it parsed. Retain-only reuse
still permits reading preserved work. Source readback confirmed the frozen
historical document feeds both tests and writing, exact operation validation
precedes reuse, and current-correction admission precedes external publication.
AST without project imports and whitespace checks passed after this final edit.
Root retains the changed-operation transition trigger and final integration.
