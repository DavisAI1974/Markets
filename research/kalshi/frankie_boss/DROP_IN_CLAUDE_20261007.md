# DROP-IN (Claude): the CCode pre-#5 queue after slices A-D (2026-10-07)

Paste this box into the new Claude Code session. It is separate from the Codex-facing `CCODE_DROP_IN_20261006_NEXT_CHAT.md`.

```
CCode pre-#5 queue, CLAUDE session, 2026-10-07. Slices A-D are RETURNED; this session reviews, fixes and hands off. HOLD stands.
FIRST, in this order:
1. /run using-agent-skills (the Skill tool). Greg's rules and the boundaries below win where they differ from a skill.
2. Branch: ccode/teacher-tasks-20261006b (the harness branch is never the work). Exactly:
     git fetch origin ccode/teacher-tasks-20261006b ccr-5fce7de3-xa4hfg
     git checkout -B ccode/teacher-tasks-20261006b origin/ccode/teacher-tasks-20261006b
     git rebase origin/ccr-5fce7de3-xa4hfg && git log --oneline -8
   The tip must be the 2026-10-07 docs commit (above a3651234, the four correction commits) on Codex's 61264cac or later.
   Expect a clean rebase; if Codex edited
   frankie_box_experiment_exchange.py / frankie_box_scientific_teacher.py / frankie_box_teacher_knowledge.py /
   frankie_box_historical_*.py / frankie_box_boss_session.py, read its diff before touching that module.
3. Memory: the MCP index_repository call times out at 60 s; run the CLI in the foreground (minutes):
     echo '{"repo_path":"/home/user/Markets","mode":"full"}' | codebase-memory-mcp cli --quiet --json index_repository
   then codebase-memory-mcp cli --quiet search_graph / get_code_snippet (project home-user-Markets).
   The session-start warning that the NG data plane is not restored is expected: nothing here needs data/ or S3.
READ, in order (research/kalshi/frankie_boss/):
   CLAUDE_HANDOFF_20261007_CCODE_SLICES_A_D.md          the Claude-side state, the map of what was built, the traps
   CCODE_NEXT_SOURCE_TASKS_20261006.md (top section)    Codex's integration review of the four returns lands HERE
   NEW_CHAT_HANDOFF_20261006_TEACHER_COVERAGE.md        newest sections only (Codex's reserved search continuation)
   CCODE_STEP4_SOURCE_ROUTE_20261006.md sections 8-9    per-slice detail, the provenance row contract (D), the closure table
DONE (source-built, runtime-unverified; nothing ran): A-D (c31cad06 7cb2ce52 11082ff8 2a05c147); Codex's correction queue
D1 f2a43e80, B7/C2 3d7f1640, B2-B5 130742ff, B1/B6/A4/C1 a3651234 (step-4 report section 8 "Corrections", section 9).
NEXT: (1) Codex's review of those four commits lands in the task doc's top section: fix every source defect it names in the
owned files, one [skip ci] commit per finding group, no reapplying what Codex integrated; (2) the exact price adapter on the
V2 price contract is Codex's: answer questions on it only; (3) nothing else is assigned: do not open or invent a slice; if the task doc assigns more, trace first, build within settled
contracts only; update step-4 report sections 8/9 + the CCODE handoff + this Claude handoff; push with [skip ci].
Boundaries: source/interface review, ast.parse without project imports, git diff --check ONLY. No tests, runs, installs,
model calls, AWS actions, dispatch, canaries or E2E. Never edit frankie_box_experiment_dipole.py or
frankie_box_experiment_search.py. Never call frankie_box_historical_reproduction.run(); never rebuild the claims file.
Granite pins/parameters settled (threads null). STOP before #5; preserved draft unapplied; never apply 9c19cc2.
Memory A retired: H06-H08 stay historical, bind nothing. Greg's decisions stay open (listed in the Claude handoff).
Commits end with the attribution lines the harness gives; no model identifiers in anything pushed. Nothing on the scratchpad.
```
