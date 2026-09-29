# Spec: Granite only in the roles the build plan gave it (Greg, 2026-09-29)

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
