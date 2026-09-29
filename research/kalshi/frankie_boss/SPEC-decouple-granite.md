# Spec: Granite only in the roles the build plan gave it (Greg, 2026-09-29)

## DECISION 2026-09-29 (late), supersedes the tables below: R3 roles on the R4 Pod
Greg: "Go off an earlier r like r2 or 3 and see if they match 4. If 4 is different use 2 or 3", "Except for the pod
use", and "It should just be a logic helper for frankie". R2 is not in the repo; R3 (2026-09-14 closeout) and R4
(2026-09-21) are, and they differ (full cell diff: `GRANITE_CALL_INVENTORY_R10_20260929.md`, R3 vs R4 section):
- R3: Granite has ONE role, the B2 shadow teacher/critic under a closed schema (C21-C24), B1 authoritative. C22 had
  no serving path; there is no C35; C14 has no classroom.
- R4 added on 2026-09-21: C22 as the retained RunPod Pod service; C35 (the BOSS vLLM as Frankie's principal engine:
  reading, writing); the governed classroom in C14.
Greg's answers (AskUserQuestion, 2026-09-29):
1. "Pod serves the critic only": Granite is the C21-C24 shadow critic, served from the R4 Pod. C35 is no longer a
   Granite role: the principal session makes no Granite call for reading, merges or writing.
2. The analysis: "Frankie does the analysis" (not Granite). Frankie is the system (code, calculations, brain).
3. The classroom: SUPERSEDED by Greg, 2026-09-29 23:17 ET: "Granite has absolutely nothing to do with classroom
   anymore." (His earlier answer "Keep it on the critic" is withdrawn.) The classroom (19 components, summary,
   correction) is answered by Frankie's code, with no Granite call of any kind.
4. Greg: "The only analysis granite should do is to say how he feels he performed." So the analysis is Frankie's
   (code), plus ONE Granite item: Granite's own self-assessment of how it performed as the critic, filed as
   Granite's, labelled as its own view, never as a result.
5. What Frankie's analysis covers (Greg, 2026-09-29 23:21 ET, verbatim list):
   - what he learned in the classroom;
   - what he learned from the cycles and the calculations;
   - new exhaustion findings;
   - his suggestions on how to improve the daily runs, and any additional calculations;
   - things to improve him;
   - any trade signal insight.
   Plus Granite's one labelled section: how it feels it performed as the critic.
Consequence for r10: r10 WAITS for this build (the principal's reading, merges, writing and classroom all move off
Granite; Granite is the launch's critic plus its one self-assessment). Build list and open items: the section "R3 BUILD" at the end of this file.


Status: SPEC, draft. **Greg: we might still tweak it in the next chat.** The reference is the build plan,
`artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`.

Greg: "We are decoupling granite ... It adds nothing", then: **"we want the roles we originally gave it, but only there."**
So Granite is decoupled from everything EXCEPT its original roles in the build plan. This supersedes the earlier draft of
this file, which proposed removing Granite from Frankie entirely.

## Granite's original roles (kept)
The build plan R4 (sheets Build Plans, Components, Roadmap) gives Granite these roles:
| Plan item | Role | Where it runs today |
|---|---|---|
| C35 (Frankie's box harness and the BOSS engine session) | Frankie's engine: "bounded reading of the delivered evidence through the BOSS, writing of the four files" | `frankie_box_boss_session.py`: reading (and its merges), writing |
| C21-C24 (serializer, checkpoint/runtime, closed parser, disagreement policy) | the B2 shadow teacher/critic under a closed schema; B1 stays authoritative; an empty or invalid critic leaves the native result untouched | the host's critic request (granite_context, stacked_v1) |
| C14 / D5 (the governed 19-dimension classroom, 171 pairs, training-only) | the principal session answers the classroom through the same BOSS engine | the principal's classroom stage and its correction turn |

To confirm next chat: whether the classroom answers (C14) count as an original Granite role, through the C35 engine.
This spec keeps them, because the plan's classroom is answered by the principal session.

## Everywhere else Granite is decoupled
| Was on Granite | Status |
|---|---|
| the exhaustion/D teach-back | code only (a47ed087) |
| the classroom scientific-teacher dialogue and the BOSS-teacher discussion | unwired (77948797; config `classroom_scientific_dialogue: false`) |
| the joined teacher data | unwired (`JOINED` refused) |
| Jev's sit-in / the CLM sidecar | not dispatched |
| the experiment's Granite pass over the survivors (`SPEC-experiment-orchestrator.md`) | removed: survivors go to symbolic regression and per-cell confirmation. The experiment's classroom arm (first and last two discovery days) uses the plan classroom through C35, so it stays |
| any new use | only by adding it to the build plan first |

## What this means for r10
- r10 as written in the drop-in uses only these roles: the reading and merges, the plan classroom, the writing, and the correction, all through the C35 engine; the critic under C21-C24.
- **So r10 is NOT held by this spec.** It runs on Greg's go, per the drop-in's work instructions.

## Open points for the next chat (Greg may tweak)
1. Confirm that the classroom answers (C14) count as an original role.
2. The code-first table in the handoff (moving the reading notes, merges, transcription and ledgers to code) was a proposal. Under "only the original roles" those stay on Granite, because they are C35. Keep them as they are, or revisit later.
3. Any Pods still up from r6/r9: the next session checks them first, and stops them only on Greg's word.


## R3 BUILD (on Greg's go; nothing built yet)
Principal session `deploy/aws/box/frankie_box_boss_session.py` (not pinned; swap modules where a module is replaced):
1. reading + merges: no model call. The notes the writing and the classroom read are assembled by code from the
   delivered evidence and the derivation (the data is exact already); the merge is a line-exact dedupe, nothing dropped.
2. writing: Frankie's analysis, the accounting entry and the ten output ledgers are written by Frankie's code from
   verify/labels/derive/compare/receipts and the brain (a new box module). The response keeps the shape the adapter
   and the recorder validate (lessons = [analysis, accounting entry, ten ledgers] + the four classroom ledgers).
3. classroom (19 components, summary) and the correction: answered by Frankie's code, no model call (Greg: "Granite
   has absolutely nothing to do with classroom anymore").
4. engine reach stays only as the Pod reach the critic lane needs.
Open for Greg:
- The classroom by code: the code answers what the teacher data and Frankie's calculations carry (the observations,
  the 171 pairs). A novel finding needs something to find it; by code that is only what a computation surfaces.
- Frankie's analysis sections are decision 5. For each, the build names the code source it is computed from
  (classroom ledgers; derive/compare against the frozen brain; the exhaustion/D priming facts and the exhaustion
  layers; receipts and progress timings; trade signal insight from the calculations), and lists as unknown whatever
  has no source yet, never filling it. Granite's only analysis item is its
  self-assessment (decision 4); where it sits: one closed-schema critic call after the classroom, its text appended to
  the analysis as its own labelled section (proposed; after the critic, not the classroom).
