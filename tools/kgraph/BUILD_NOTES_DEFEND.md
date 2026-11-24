# Build notes: tools/kgraph/defend.py

- 2026-11-24 (ticket 02): `defend register` writes one Claim node from a proposer's claim file with the registration contract's fields, tied to what it rests on (DEPENDS_ON, SUPPORTS), and refuses a file with no mechanism, alternative, falsifier, scope, exact claim or outcome visibility, an unreal ground, or a run that is not an AgentRun.
- 2026-11-24 (ticket 03): `defend challenge-brief` writes the claim, scope, artifact and the grounds in full without the proposer's reasoning; `defend challenge` writes one Evaluation (rubric "independent challenge v1") tied to the claim, refusing the proposer's own run; `defend show` and `defend undefended` read the record back. Nothing in schema.py changed.
