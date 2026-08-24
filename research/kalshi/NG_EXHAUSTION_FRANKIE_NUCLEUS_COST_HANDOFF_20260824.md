# Frankie Nucleus cost-architecture handoff

> **Required first read:** Read and obey
> `research/kalshi/NG_EXHAUSTION_FRANKIE_MONTHLY_RUN_PROCEDURE.md` in full before this handoff.
> This handoff supplies task-specific identities and exceptions only. If it conflicts with the canonical
> procedure, stop and resolve the conflict explicitly rather than silently choosing one.

Date: 2026-08-24
Markets branch: `chatgpt/ng-exhaustion-october-sharded-20260824`
Pre-handoff remote tip: `f0b429737a7a898e817625a071c223af0be7f06e`
Nucleus candidate URL: `https://github.com/DavisAI1974/operator_hilbert_seq`

## Job 1

Establish the exact Nucleus source of truth and determine whether it can do most of the reasoning work
locally, leaving Frankie on GPT-5.6-sol as one final synthesizer per lane instead of paying for four sol
helpers plus Frankie in each lane.

Do not relaunch October, run Step-1, call a provider, modify the accepted CPU implementation, or run broad
tests while performing this review.

## Current operational truth

- October attempt 8 workflow run `32753586584` was deliberately stopped.
- Unit `ng-exhaustion-frankie-fullstack-october-1ae2d5d83906-32753586584-1` deactivated successfully at
  `2026-08-24T17:17:21Z`.
- Stop retry workflow run `32755722459` succeeded.
- Attempt 8 reached staged-data/runtime/CPU initialization but emitted no real
  `FRANKIE_PROVIDER_CALL_STARTED`, `PROVIDER_RESPONSE_ACCEPTED`, `PAIRED_PREFIX_ACCEPTED`, `PREFIX_READY`,
  or `OCTOBER_REPLAY_PROGRESS` event. It processed no D/D0 event and likely spent no OpenAI API credit.
- The accepted remote CPU path still runs recurrence=CPU0, extension=CPU1, timing=CPU2, context=CPU3
  concurrently within one lane, Frankie fifth after join, with control before combined.
- The launch marker is stopped and unauthorized. Do not change that state during the Nucleus review.

## Verified public scaffold

The visibility change initially returned 404, then propagated. The repository now resolves with:

- repository ID `1079500885`;
- default branch `main`;
- HEAD `5bc511c06d3048a510333910588b9a6305532ab2`;
- HEAD date `2025-12-28T15:43:50Z`;
- HEAD message `Add NOVA optimization to Operator Hilbert (90%+ token reduction)`; and
- tree `7b98887c05dfed324a2eb58e3968cbc6e6e960b1`.

Complete tracked source inventory at that HEAD:

| Path | Blob SHA | Finding |
|---|---|---|
| `.gitattributes` | `f5f0c27b9da1ffcfa6ef59f19300173c4b585b74` | Line-ending/binary attributes only |
| `.gitignore` | `fa3d630ba7a263f7ec46fdf48f96713a24e30143` | Ignores data and model checkpoints |
| `.github/workflows/qa-guard.yml` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` | Empty file |
| `README.md` | `99215da94fa79f04c1a68f5d2834d049a0190bef` | Describes modules not present in this tree |
| `app/main.py` | `65936f368004459f87b1f203fbf06d16dd5a3b22` | FastAPI scaffold with placeholder computations and a missing integration import |
| `app/nova_optimizer.py` | `c59424653dad5b04c0ff6f6bd7e149e90f05565e` | Local heuristic string compressor |

This is not the complete Nucleus build and is not a usable helper replacement as checked in:

- `app/main.py` returns hard-coded placeholder operator, embedding, and wavelet results.
- `app/nova_optimizer.py` is not Amazon Nova and calls no model or Amazon service. It truncates or summarizes
  dictionaries and estimates tokens as character length divided by four.
- The advertised enable key does not gate compression behavior.
- `app.integrations_foundation`/`integrations_foundation` is imported but absent.
- No requirements, project packaging, Docker file, model implementation, weights, launch wrapper, or substantive
  test exists.
- The README names FFT/DWT features, operators, models, trainers, visualization, and benchmarks that are not in
  the current tree.

The user says the full work exists in other builds and will supply those build links in the new chat. Do not
choose this scaffold as the source of truth or rebuild it before comparing those builds.

## Read-only repository inspection sequence

After the user supplies the other build link(s):

1. Record each repository owner/name, visibility, default branch, remote HEAD SHA/date, and recent history.
2. Compare each tree against the verified six-file scaffold above; identify which build contains the real
   Nucleus implementation rather than placeholder services.
3. Read repository rules and README, then inventory only dependency manifests, model/config/weight references,
   entrypoints, launch wrappers, tests/CI, and files containing Nucleus/Operator/Hilbert definitions.
4. Determine whether checkpoints/weights, data, secrets, or runtime files are missing from git or require LFS.
5. Determine whether the checked-in version is complete and runnable from a clean clone; do not assume that a
   source tree contains its weights.
6. If a desktop E: copy is later pushed or uploaded, compare `git remote -v`, branch, HEAD, recent commits,
   tracked files, and uncommitted/untracked files by hash. No committed artifact or runtime may depend on an
   E: path.
7. Produce a factual architecture packet before proposing code changes.

## Candidate cost architecture

Current paid path per paired prefix:

- control lane: four sol helpers concurrently, then Frankie;
- combined lane: four sol helpers concurrently, then Frankie;
- total: 10 logical sol invocations, with at least one tool round per invocation in the current adapter.

Candidate path:

- Nucleus locally produces four structured, source-linked sections: recurrence, extension, timing, context;
- Frankie/5.6-sol performs one final synthesis after those sections are complete;
- control lane completes before combined begins; and
- total target: 2 logical sol invocations per paired prefix, an 80% reduction in logical sol invocations.

Do not use an opaque generative summary as evidence authority. Nucleus output must bind the exact immutable
prefix, source IDs/hashes/spans, omissions, model/config/version, and deterministic output receipt. Original
evidence must remain retrievable. Nucleus cannot see target outcomes, Step-1 answers, post-cutoff rows,
cross-lane derived state, or assign final probabilities/locks.

## Smallest decision gate

Use only 1-2 already-frozen prefixes outside a live October run:

1. Existing accepted path or cached output is the comparison arm.
2. Nucleus produces the four structured sections from the identical pre-cutoff packet.
3. Frankie runs unchanged once per lane on the Nucleus receipt.
4. Compare evidence/citation retention, D/exhaustion finding, abstention/lock stability, probability delta,
   input/output tokens, provider-call count, latency, and estimated cost.
5. Fail closed on leakage, invalid citations, missing must-keep evidence, nondeterministic receipt hashes, or a
   material reasoning regression.

Only after this shadow gate passes may a separate implementation session replace the four paid helpers. That
release must remain separate from ordinary month rollover work and use no more than two focused tests.

## Subsequent monthly standardization

After the cost architecture is decided, continue the one-time monthly generalization already recorded in
`tasks/plan.md` and `tasks/todo.md`. A normal month must ingest the prior month's frozen learned knowledge and
change only its descriptor and frozen-knowledge source declaration; receipts and launch markers are generated.
Runtime, workflow, provider boundary, scientific rules, and tests remain unchanged during a normal rollover.

The canonical monthly procedure must remain the first-read block at the top of every handoff.

## Required closeout

Commit and push any accepted documentation or implementation to the Markets branch. Report exact remote SHAs,
changed files, focused verification actually run, and explicit untouched areas. Never claim a launch, provider
call, D event, or cost saving without durable receipts.
