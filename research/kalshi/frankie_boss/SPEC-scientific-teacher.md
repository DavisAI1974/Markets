# Spec: the scientific teacher (Greg, 2026-09-29)

Status: SPEC, confirmed by Greg 2026-09-29 ("I agree with everything you did"). Nothing built. Not in the Excel build plan (R3 or R4): it goes into the plan before it is built.
Greg: "Yes write scientific teacher and the rules file." The classroom rules: `knowledge/CLASSROOM_RULES_V1.json`.

## The design (Greg)
Three seats: the BOSS teacher, the scientific teacher and Frankie. The two teachers are tied together and keep their
separate roles. All three discuss findings and dipole discoveries, and Frankie gets taught.

Where the Granite confusion came from (Greg, agreed): once Frankie reported his dipole findings and learnings into the
discussion, the discussion was built "on the established model transport" (the header of `dipole_teacher_discussion.py`),
so the same Granite model spoke for the scientific teacher, the teacher-to-teacher discussion and Frankie's replies (his
engine). One model in every seat means agreement between the seats is not independent confirmation.

The fix: every seat has its own independent source, and no seat is a model (Greg: "Granite has absolutely nothing to
do with classroom anymore").

| Seat | Role (unchanged) | Source |
|---|---|---|
| Frankie | the learner; his findings are claims, never truth | his code, his calculations, his brain |
| BOSS teacher | mathematics, representation supervision, targets, masks and controls; scientific research added | code: the teacher (JournalTeacherR3 on the day's journal), the classroom package, the teacher key |
| Scientific teacher | mechanism and evidence | the experiment's search engine: every claim is tested as a hypothesis with its own chance check, reported as counts |

## What the scientific teacher does
1. Takes in, each labelled with its author: the BOSS teacher's measurements; Frankie's classroom answers, novel findings
   and analysis claims (as claims, rule R11); the retained learning history.
2. Turns every claim into a testable statement over the day's series (the raw journal, every book level, and the
   exported calculation JSON), on one causal time axis per day where every row carries only what was knowable then.
3. Runs each test with its own circular-shift chance check, per cell and per discovery day, the leakage gate on every
   target (`odcore/leakage.py`), results as counts (D37), never a coefficient or an average as the finding.
4. Hands back, per claim:
   - the test it ran (series, transform, lag, cell, condition, target) and the counts, with the days named;
   - a disposition word as orientation only (the existing DISPOSITIONS in `dipole_scientific_review.py`:
     SUPPORTED_SCOPED, PLAUSIBLE_UNRESOLVED, CONTRADICTED_SCOPED, INSUFFICIENT_EVIDENCE; rule R14);
   - a challenge where the data contradicts a subclaim, worded "the data is showing this instead" (rule R07);
   - the proposed tests it has not yet run (the untested combinations the claim implies), listed, never dropped;
   - what cannot be tested yet, and why (missing series, not yet causally available).
5. The BOSS teacher answers the scientific teacher's results within its own role (its targets, masks, controls), and
   the scientific teacher answers back; each turn builds on the other's. A new discovery from the exchange is filed as
   the teachers' own finding, scoped, with its days named. Frankie is taught from the exchange.

## Tied together, separate roles (rule R12)
- The BOSS teacher never becomes a reviewer only and never rewrites its targets from a discussion (CHAT15 handoff).
- The scientific teacher never grades Frankie: fact grading stays the deterministic classroom grade.
- Neither teacher sees Frankie's decision process or the graded outcomes (rules R09, R10).

## What is reused and what is new
Reused (not copied):
- `dipole_teacher_discussion.py`: the roles (boss_teacher_scientific, scientific_teacher), positions and schemas stay;
  only what produces a turn changes, from a model prompt to a test result.
- `dipole_scientific_review.py`: the request, exchange and disposition schemas.
- The joined-teacher builder (dfe08ca7, `frankie_box_joined_teacher.py`): its per-cell sign-step couplings and
  circular-shift null are the starting slice of the tests, pointed at the journal and the calculation JSON.
- The experiment orchestrator's search (`SPEC-experiment-orchestrator.md` steps 5-6): the scientific teacher is its
  classroom-facing side.
New:
- A box module for the scientific teacher's turn (claim -> tests -> counts -> challenges and proposed tests).
- The classroom code loading `knowledge/CLASSROOM_RULES_V1.json` and holding every seat to it.
Swapped out: `deploy/aws/box/frankie_box_scientific_dialogue.py` (it sends the teacher turns to Granite, line 25).

## Days (the experiment's walls)
The scientific teacher works on discovery days only (rule R15). Its tests run across every discovery day, so a claim
Frankie makes on one classroom day is tested on the others. Confirmation days stay untouched until the survivor list is
frozen.

## For r10
The scientific teacher needs the search, which is not built. Until it is, the tied teachers stay unwired for r10 and
the classroom runs with the BOSS teacher and Frankie's code answers only.

## Build order (each on Greg's go)
1. Greg: confirm or edit `CLASSROOM_RULES_V1.json`.
2. Add the scientific teacher and the rules file to the Excel build plan.
3. The search (experiment steps 5-6) on the discovery days.
4. The scientific teacher's turn on top of it, with the discussion schemas.
5. The classroom loads the rules file; the tied teachers switch on.

## Open for Greg
- (Resolved 2026-09-29: the pooled Pearson is out of the build; the 171 pairs carry co-movement counts.)
- Whether a model is ever given a seat. If so, one seat only, and a different model from anything else in the loop.
