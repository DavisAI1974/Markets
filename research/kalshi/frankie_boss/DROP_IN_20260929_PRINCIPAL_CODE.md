# DROP-IN: Frankie cycle 0, the principal by Frankie's code (2026-09-29)

Paste this box into the new Code session.

```
Frankie Monday cycle 0, r10 on the principal-by-code build. This is a CODE session (the chat session could not dispatch workflows).
FIRST, in this order, before anything else:
1. Run /mcp and confirm codebase-memory-mcp is connected. If it is not: install it (curl -fsSL
   https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash -s -- --skip-config), confirm
   .mcp.json and "enabledMcpjsonServers" on the branch, restart. Then index the repo (index_repository; .cbmignore
   re-includes deploy/) and use search_graph / trace_path for code questions.
2. Load the agent skills from https://github.com/addyosmani/agent-skills (clone it if it is not installed): read
   skills/using-agent-skills/SKILL.md and skills/git-workflow-and-versioning/SKILL.md and apply them. Greg's rules
   below win where they differ (no tests, [skip ci], this long-lived run branch).
3. Read the repo skills full-run-orchestrator (and experiment-orchestrator for the experiment track).
Branch: claude/frankie-monday-cycle-0-urozez. Fetch it and check it out; the tip must be this drop-in's commit or later.
READ FIRST: research/kalshi/frankie_boss/HANDOFF_20260929_PRINCIPAL_CODE.md (whole), then SPEC-decouple-granite.md
(the DECISION and BUILT blocks), then SPEC-scientific-teacher.md and knowledge/CLASSROOM_RULES_V1.json, then
GRANITE_CALL_INVENTORY_R10_20260929.md. Build plan: artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx and
_R3_20260914_Closeout.xlsx (openpyxl; Greg: R3 Granite roles on the R4 Pod).
Where things stand: Granite is ONLY the B2 shadow critic (C21-C24) on the Pod, plus one labelled self-assessment of how it
performed as the critic. Frankie's code does reading, the classroom, the correction, a small priming (no bedrock) and the
writing. The BOSS is the whole native system; Granite is a small piece of it. Nothing has run on this build yet.
Rules:
- No tests, no validations, no canaries. py_compile with python3.12 only. [skip ci] on every push.
- Launch stays on HOLD: no box run, Pod, Granite call or launch without Greg's explicit go, step by step. Read-only probes need no go.
- A probe on every long box run.
- Never edit frankie_box_projection.py or the pinned reader/teacher/normalizer/context files (swap, never edit).
- A cycle0.sh dispatch needs the staged CODE_ROOT commit == the branch tip, so restage after every push.
- Zero data dropped; no caps; no truncation; nothing flattened, smoothed, normalized or averaged (coefficients are fine,
  read per pair/cell/day). Unknown or incomplete data is listed.
- Duplicate data declines the run, with the reason.
- Keys are secrets.
Next: read Jev's reports (read-only) and show Greg what the data shows turn by turn; check what is billing; then, on
Greg's go: serverless leftover check, stage the tip, the r10 config, launch, principal, record and correction (exact
inputs in the handoff's "Next" list).
```

## Open for Greg (carried; details in the handoff)
- "Get rid of bedrock": done for the priming only; the whole run still derives it for the teachers.
- The Pearson 8-point floor.
- Whether Granite's self-assessment rates itself as the critic (built) or rates Frankie.
- Jev's reports: never read yet.
