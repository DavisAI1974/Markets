# Brief for ChatGPT: new pieces of the Frankie experiment (2026-09-29)

**STATUS 2026-09-29 (later): all three pieces were built by Claude on Greg's word ("I'm going to have you do chatgpts
part") on the run branch: C transforms e7ae50ab, B historical claims e2d6bf36, A orchestrator 2ccbea3a. Do not build
them again; this brief is kept as the record of what was asked.**

Greg wants ChatGPT building new pieces of the experiment while Claude builds the teacher-only batch step. Read this
whole brief, then the files it names. Where this brief and a spec disagree, the spec wins and you say so.

## Where everything is
- Repository `DavisAI1974/Markets`, run branch `claude/frankie-monday-cycle-0-urozez`. Work on your OWN branch cut
  from its tip, one per piece: `chatgpt/experiment-orchestrator`, `chatgpt/experiment-historical-claims`,
  `chatgpt/experiment-transforms`. Claude merges them. Do not push to the run branch.
- Read first, in order:
  1. `research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md` (the whole experiment; its UPDATE block, the
     sections "Jev", "His brain" and "The teacher's Dipole rows: 1 day in 5").
  2. `research/kalshi/frankie_boss/SPEC-scientific-teacher.md` (the search IS the scientific teacher; "Data access").
  3. `.claude/skills/experiment-orchestrator/SKILL.md` (the runbook: what is built, the walls, the open items).
  4. `research/kalshi/frankie_boss/knowledge/CLASSROOM_RULES_V1.json` (rules R01-R17).

## Rules that never bend (Greg)
- No tests, no validations, no canaries. `python3.12 -m py_compile` and `bash -n` only. `[skip ci]` on every commit.
- Nothing runs. No box, Pod, model or workflow dispatch; you write code only. Every run is Greg's go, later.
- Zero data dropped: no caps, no truncation, no sampling of data, nothing normalized, smoothed or averaged. Unknown or
  incomplete data is LISTED with its reason, never filled in. A coefficient is fine only read per pair/cell/day.
- The finding is COUNTS per pair, cell, lag and day, never an average, an R2 or a pooled correlation (D37).
- Days are never pooled. Day classes never mix. Discovery = October days of 2021-2023; confirmation = October days of
  2024-2025, untouched until the survivor list is frozen (R15).
- Duplicate data declines the run, with the reason.
- No model anywhere in the experiment (R17). No Granite. No bedrock layers.
- Never edit these pinned files: `frankie_box_projection.py`, `context_session.py`, `c15_journal.py`,
  `c15_teacher_r3.py`, `c15_normalizer.py`. Call them; never modify them.
- Do not edit the files Claude is working on: `frankie_box_experiment_search.py`, `frankie_box_scientific_teacher.py`,
  `frankie_box_experiment_root.py`, `frankie_box_experiment_data.py`, `frankie_box_brain.py`,
  `frankie_box_boss_session.py`, and anything named `*teacher*` under `deploy/aws/box/`. Your pieces are NEW files.
- Keys are secrets. Box scripts live in `deploy/aws/box/`, are dispatched only through
  `.github/workflows/frankie_box_run.yml`, and follow the existing scripts' pattern (check `MARKETS_SHA` against the
  staged `CODE_ROOT`, paths only under `/opt/frankie-box/`, no quotes/apostrophes inside `${VAR:?...}` messages).

## Piece A: the orchestrator (new files `deploy/aws/box/frankie_box_experiment.py` + `.sh`)
The experiment runs as one box-side orchestrator over a list of days (spec, "How the orchestrator runs"). It CALLS the
existing steps; it re-implements none of them:
1. fetch + ingest: `frankie_box_ingest_block.sh ACTION=fetch|ingest|status` (never re-ingest Monday 20211004: gold standard);
2. ROOT: `frankie_box_experiment_root.sh` (bedrock off; DIGEST=on only on the three classroom-arm days);
3. teacher: every 5th discovery day, the teacher-only batch over the days since its last run (Claude is building this
   step; call it as `frankie_box_experiment_teacher.sh DAYS=<comma list>` and treat its interface as TBD);
4. day data: `frankie_box_experiment_data.sh ACTION=export`;
5. search: `frankie_box_experiment_search.sh DAY_ROLE=discovery`, on the same 5-day rhythm as the teacher;
6. scientific teacher: `frankie_box_scientific_teacher.sh` after each batch.
Requirements: a per-day, per-step receipt under `/opt/frankie-box/work/experiment/<run>/`; a restart skips finished
steps and resumes the rest; stop-and-save at a disk floor (measure free bytes; refuse to start a step that would cross
it, and list why); progress written for `frankie_box_progress.sh DIRECTORY=<run>`; inputs = day list, class,
discovery/confirmation assignment, stage range; confirmation days refused until a frozen survivor list exists; one
lock `box-experiment-*` (add the script to the concurrency expression in `frankie_box_run.yml` beside the other
experiment scripts). Days run in parallel where a step allows; each day's steps stay in order.

## Piece B: historical Dipole claims (new file `deploy/aws/box/frankie_box_historical_claims.py`)
An earlier agent searched the repo, the hard drive and old handoffs exhaustively for Dipole knowledge. Its output:
`research/kalshi/frankie_boss/knowledge/DIPOLE_SHARED_CATALOG_20260922.json` (127 sources, 10 review groups) and
`research/kalshi/frankie_boss/DIPOLE_KNOWLEDGE_GAP_REVIEW_20260922.md`. Turn every historical claim in it into a
testable claim for the scientific teacher, labelled with its author and source (R11: claims, never truth):
- Output `HISTORICAL_CLAIMS_V1`: `{schema, catalog_sha256, claims: [{id, author:'historical', source (file:line or
  catalog id), statement, series: [names], cells: [...], condition, lag, target, direction, evidence: [...]}],
  not_testable: [{source, statement, reason}]}` - the same claim fields as Jev's `JEV_CLAIMS_V1`
  (`research/kalshi/frankie_boss/clm_sidecar/sit_in.py`, `student_claims`).
- Series names must be the search's names where one exists (`frames.*`, `structures.*`, `prices.*`, `events.*`,
  `signed_flow.*`, `roll20.*`, and `dipole.<component>` for the 19 components in `c15_normalizer.py` COLUMNS). A claim
  whose series the search does not carry goes to `not_testable` with the reason, never dropped.
- Keep the different Dipole constructions distinct (the review's K01): a centroid-projection claim is not a C15R3
  component claim.
- Code only; no model reads the catalog to write claims. Where a claim cannot be put in testable form by code,
  list it under `not_testable` with the reason.

## Piece C: more transforms for the search (new file `deploy/aws/box/frankie_box_experiment_transforms.py`)
The search counts only the sign of each step (`frankie_box_experiment_search.py`, `couple` and `_cell_job`). Add the
transforms it lists as not yet searched, each as a function `name(values: np.ndarray) -> np.ndarray` of -1/0/1 steps
(or a documented counts shape), causal (a step at t uses only rows at or before t), no caps:
- run length (a step is +1 when a run of same-sign moves lengthens, -1 when it breaks);
- magnitude class per series (steps above / below the series' own running median of |step| so far - a running
  statistic known at t, never the whole day's);
- level crossings (the series crossing its own running median so far);
- first difference of a first difference (acceleration sign).
Export a `TRANSFORMS = {name: function}` registry and a docstring per transform saying what it counts. Claude wires
the registry into the search (so its counts stay one statistic, one chance check).

## Handing back
Push your branch, then write `research/kalshi/frankie_boss/CHATGPT_HANDBACK_<piece>_<date>.md`: what you built, file
by file, what you could not settle (listed), and anything in this brief or the specs that looked wrong.
