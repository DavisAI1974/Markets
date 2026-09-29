# DROP-IN: the Frankie experiment build (2026-09-29, after the Code session)

Paste this box into the new Code session.

```
Frankie experiment build. CODE session. Monday r10 is PARKED (do not resume it unless Greg asks).
FIRST, in this order:
1. /mcp: confirm codebase-memory-mcp is connected. Index with the CLI, not the MCP call (the call times out at 60 s and
   kills the worker): ~/.local/bin/codebase-memory-mcp cli index_repository '{"repo_path":"/home/user/Markets","mode":"moderate"}'
   Then use search_graph / trace_path for code questions.
2. Invoke the skills with the Skill tool: using-agent-skills, then experiment-orchestrator (and full-run-orchestrator
   before any box step). Greg's rules below win where they differ.
Branch: claude/frankie-monday-cycle-0-urozez. Fetch it and check it out; the tip must be this drop-in's commit or later.
READ FIRST: research/kalshi/frankie_boss/HANDOFF_20260929_EXPERIMENT_BUILD.md (whole), then SPEC-experiment-orchestrator.md
(UPDATE block, "Jev", "His brain", "The teacher's Dipole rows: 1 day in 5"), SPEC-scientific-teacher.md ("Data access"),
knowledge/CLASSROOM_RULES_V1.json, CHATGPT_BRIEF_EXPERIMENT_20260929.md.
Settled, do not re-ask: Granite is only the full run's B2 critic (+ one self-assessment); the classroom is Frankie's code;
the experiment is CPU only, no bedrock; Jev is the blind outside student with his own brain; teachers read all of
Frankie's data except his own reasoning files (R09); keys do not rotate.
Rules:
- No tests, no validations, no canaries. py_compile with python3.12 and bash -n only, EACH CHECK ON ITS OWN before a
  commit. [skip ci] on every push.
- HOLD: no box run, Pod, Granite call or launch without Greg's explicit go, step by step. Read-only probes need no go.
  Both EC2 boxes are STOPPED; starting one is a go.
- A probe on every long box run. Restage after every push before any cycle0/experiment dispatch.
- Never edit frankie_box_projection.py or the pinned reader/teacher/normalizer/context files (swap, never edit).
- Zero data dropped; no caps; no truncation; nothing flattened, smoothed, normalized or averaged (coefficients fine per
  pair/cell/day). Unknown or incomplete data is listed. Duplicate data declines the run, with the reason.
- Keys are secrets.
Next: build the teacher-only batch step (handoff "Next" 1), merge ChatGPT's pieces as they land, then on Greg's go the
box steps in the handoff's order (restage, DuckDB install, brain show, Monday day data, Monday search).
```
