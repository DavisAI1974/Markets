# Spec: decouple Granite from Frankie (Greg, 2026-09-29)

Status: SPEC, draft. **Greg: we might still tweak it in the next chat.** Nothing in it is built yet. Read it with the build
plan, `artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`.

Greg's words: "We are decoupling granite from granite. It adds nothing." Read here as **decoupling Granite from Frankie**.
Confirm that reading with Greg first thing in the next chat.

## Why
- Granite was meant to be a small reasoning boost. In practice it became the pipe for most of Frankie's work, and that work is either code-computable or copying:
  - the reading notes restate tables that code already made exactly;
  - the merges keep every line word for word;
  - the teach-back restated code facts, and a check refused any number it added;
  - the ledgers fill a fixed structure.
- Measured cost: the 131k-context read, split into parts, and the Pods (4 x A100 at about $6.36/h together in r6/r9).
- The one completed principal run (20211003 cycle 00) produced no classroom and no teach-back through it.
- The build plan already carries a no-Granite path. B1, the recurrent native BOSS, is the "required market-authoritative reasoning core and no-Granite comparison". The B1-clean and B1-memory arms have Granite = None. Decoupling runs Frankie on that path.

## What Frankie is without Granite
- The code system: ingest (the gold standard), the calculations (the derive stage, the pin producers), the native context and B1 (C19/C20), the dipole teacher (JournalTeacherR3 with the uncapped changes), the brain, and the per-cycle calculation export.
- The experiment search (`SPEC-experiment-orchestrator.md`): the systematic finder of relationships, counted against chance.

## Every Granite call today, and what replaces it
| Call (frankie_box_boss_session.py and the classroom/scientific modules) | Replacement |
|---|---|
| engine reach (Pods, serverless endpoint) | removed; no Pod |
| reading the digest in parts | removed; the digest and the calculation JSON are Frankie's own data, read by code |
| the merge levels | removed, with the reading |
| teach (exhaustion/D) | already code-only (a47ed087) |
| the classroom's 19 component answers and summary | code: the component observations transcribed from the teacher attachment; the relationship scan from the search's counts (not the 171 pooled Pearson pairs) |
| the classroom correction turn | code: each graded item resolved by the data that settles it (rule 3 of the joined-teachers spec) |
| the writing: analysis, accounting entry, ten ledgers | code fills the ledgers and the accounting; the analysis becomes a code report (per-event, never averaged; D37) |
| the B2 shadow critic (C21-C24) | off; B1 stays authoritative (the plan's rule), with no critic call |
| the scientific dialogue and the teacher discussion | already unwired (77948797) |
| the experiment's Granite pass over the survivors | removed; survivors go to symbolic regression and per-cell confirmation |
| Jev / CLM sidecar | not dispatched |

## What changes in the r10 rerun
- r10 as written in the drop-in still calls Granite for the reading, merges, classroom and writing. Hold r10 until this spec is settled.
- Then r10 runs: verify, labels, derive, the code classroom, the teach priming, the code writing, push. No engine, no reading lane, no Pods.

## Open points for the next chat (Greg may tweak)
1. Confirm the reading: Frankie decoupled from Granite, entirely.
2. The classroom without Granite has no model "student". Decide which of these it is:
   - a code teach-back and grade of what Frankie's code computed; or
   - the teacher and the search working together, with no student turn.
3. The grading key: keep the 171 pooled Pearson pairs, or move to the search's per-cell counts (re-mints the classroom identity).
4. The pinned host path expects a principal response. Choose which recorder path writes the code response, and keep the host's validators satisfied, or change them.
5. The Excel build plan: mark Granite (C21-C24, and C35's engine) as decoupled, and record the B1 no-Granite path as the operational arm.
6. Stop or delete any Pods still up from r6/r9, on Greg's word (the next session checks them first).
