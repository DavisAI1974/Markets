# DROP-IN: Frankie cycle 0, Granite decoupling (2026-09-28, end of chat)

Paste this box into the new chat.

```
Frankie Monday cycle 0: Granite decoupling. Run using-agent-skills before anything.
Branch: claude/frankie-monday-cycle-0-urozez. Fetch it and check it out; the tip must be this drop-in's commit or later.
READ FIRST: research/kalshi/frankie_boss/DROP_IN_20260928_GRANITE_DECOUPLE.md (this file), then
research/kalshi/frankie_boss/HANDOFF_20260928_JOINED_TEACHERS.md (every update block, in order).
Rules:
- No tests, no validations, no canaries. py_compile with python3.12 only. Put [skip ci] on every push.
- Launch stays on HOLD: no box run, Pod, Granite call or launch without Greg's explicit go.
- A probe on every long box run.
- Never edit frankie_box_projection.py or the pinned reader/teacher/normalizer/context files (swap, never edit).
- A cycle0.sh dispatch needs the staged CODE_ROOT commit == the branch tip, so restage after every push.
- Zero data dropped; no caps; no truncation; nothing normalized or averaged. Unknown or incomplete data is listed.
- Duplicate data declines the run, with the reason.
- Keys are secrets.
Next: rerun the Frankie part AND the classroom as r10 on the build-plan wiring (Greg: "Unwire everything that isn't in
the build plan and we rerun Frankie part in new chat"; "we'll have to rerun classroom too"), each step on Greg's go.
```

## UNWIRED at the end of the chat (Greg: only what is in the build plan runs)
The build plan is `research/kalshi/frankie_boss/artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`. Its Granite roles:
- C35: Frankie's engine for reading the delivered evidence and writing the four files;
- C21-C24: the shadow critic, under a closed schema;
- C14/D5: the governed 19-dimension classroom with its 171 pairs, training-only.

Unwired, because each was added after the plan (the code stays and is only disconnected):
- **The scientific-teacher dialogue and the BOSS-teacher discussion** (added 2026-09-22):
  - `run_actual_sunday_classroom` builds the classroom package WITHOUT shared knowledge unless the config says `classroom_scientific_dialogue: true`. The host config writes `false`.
  - The adapter and `make_principal_adapter` accept a plan classroom that carries none.
  - The principal still gets its shared-knowledge snapshot: in single-run mode it is Frankie's own knowledge manifest (brain entries plus the 18 preserved sections).
  - Result: the box classroom takes the plain path (19 components on the reading lane, the summary on the BOSS), and the correction is the plain classroom correction, with no scientific request.
- **The joined teacher data**: `ACTION=config JOINED=...` is refused.
- **The Granite exhaustion/D teach-back**: now code-only priming.
- **Jev's sit-in relay and the CLM sidecar**: never part of the principal; simply do not dispatch them.

The rerun therefore runs, in order: verify, labels, engine, derive, reading, merges, the governed classroom, the teach priming (code), writing, push, the correction. The Granite role table below is a later proposal and does not apply to this rerun.

## Greg's direction this chat (the load-bearing part)
- **Granite is a small piece of Frankie: a reasoning boost, nothing else.** Frankie is the system (code, calculations,
  brain). Whatever can be computed or copied is code; Granite gets a small, code-prepared question plus the exact rows
  it needs, and returns reasoning, which code checks against the data.
- **The bedrock is a logic helper, not Frankie's knowledge base.**
  - The teachers read the computed layer files in place.
  - Frankie's brain carries the derivation digest (5 legacy tables since V9), the ledgers, the analysis, layer statuses, the priming and the frozen files. It does not carry the bedrock layer contents.
- The priming for his pump must be catered to his exact role, which is to be defined next.

## DONE this chat
1. **The exhaustion/D priming is DECOUPLED from Granite** (Greg: "Decouple frankie from this part then"). This commit carries it.
   - The `teach` stage computes the facts by code and files them whole, with no model call:
     - `work/teach/exhaustion-teachback.json`, schema `FRANKIE_BOX_TEACH_PRIMING_V1`, with `model_calls: 0`;
     - `exhaustion-teachback.md`: the facts text plus the frozen files.
   - The brain entry and the docs carry that file.
   - The analysis section points at the priming file.
   - A record filed by the retired Granite teach-back still renders as it was.
   - Files: `deploy/aws/box/frankie_box_boss_session.py` (teach, _teach_section, writing prompt wording), `frankie_box_teach.py` (CODE_SCHEMA, facts_markdown), `frankie_box_brain.py` and `frankie_box_docs.py` (descriptions).
2. **Nothing needs rerunning because of it.**
   - The only completed principal run is cycle 00 of 20211003, on 2026-09-21: branches `root/cycle-00-response` 6879fb87 and d44e71ce. Its response keys are feedback, lessons, sections, session_id, request_sha256 and model identity. Its brain entry holds the digest, ledgers, analysis, derive and the derived-files listing. **No teach-back and no classroom ever ran.**
   - The Monday runs r2-r9 never reached the principal.
   - So no calculation or analysis was produced through the Granite teach-back, and the principal-inputs brain base (v9-r2) is unaffected.
3. **The joined teachers are BUILT, NOT RUN** (dfe08ca7):
   - builder: `frankie_box_joined_teacher.py`/`.sh`;
   - delivery to both teachers: `dipole_joined_teacher.py`, the scientific request, the box readings and the validators, with `ACTION=config JOINED=<MANIFEST.json>`.
   - Held until Frankie's role is defined.
4. **r9 is stopped and its data kept**, along with every fix since: the single-read walk, the concurrent teacher, the uncapped teacher, the parts-not-truncation notes, and the duplicate refusal. See the handoff.

## NEXT (in order, each on Greg's word)
0. **The r10 rerun of the Frankie part and the classroom, on the plan wiring** (step 4 below), first.
1. **Later, not for this rerun: agree the Granite role table with Greg.** It is in the handoff under "Granite is a reasoning boost". The proposal:
   - To code: the reading notes (the data is already exact), the merges (line dedupe), the classroom observation transcription, and the accounting entry plus the ten ledgers.
   - Stays Granite: novel findings, the run analysis, the correction turn, the scientific teacher, the BOSS teacher and Frankie's replies.
   - The whole-corpus staged re-reads before each role are replaced by inputs that code selects for each question.
   - Open call: the classroom grade applies only to Granite's reasoning part once code does the transcription.
2. Build the code side of the agreed table (swap modules; never edit the pinned files).
3. Define and cater the priming to that role: which facts, which frozen files, and whether the joined couplings reach him.
4. Restage the tip. Then the r10 config:
   - `PREPARED=/opt/frankie-box/work/trading-day-preparation/full-20211004-20260927-r6-48/prepared-configuration.json`
   - `PRINCIPAL=/opt/frankie-box/work/principal-inputs/full-20211004-20260928-v9-r2/principal-inputs-receipt.json`
   - `RUN_ID=monday-20211004-20260928-r10`
   - `OUTPUT_ROOT=/opt/frankie-box/work/monday-run-config/full-20211004-20260928-r10`
   Then the launch and the principal, with probes on both. No Jev relay (unwired). **Do not resend the dipole catalog.**

## Open calls for Greg (carried)
- Replacing the classroom's 171 pooled Pearson pairs in the grading key.
- The same Granite model plays every role, so agreement between roles is not independent confirmation.
- `concurrent_teacher`: when the teacher fails to pickle it falls back to in-process. Keep that fallback, or make it a hard stop?
- A full audit of anything still dropped or capped, across every process.
