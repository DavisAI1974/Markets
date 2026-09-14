# Claude Code: Granite contract implementation

We are continuing the final Frankie/BOSS build in parallel with Codex. Your
assignment is the narrow NOOA contract work below. Implement it and return a
reviewable commit/patch with tests; do not just write another proposal.

Repository: DavisAI1974/Markets
Integration branch: codex/boss-full-evidence-20260907
Verified starting commit: de27bb26 (2026-09-14).

Use your own isolated worktree/branch from that commit. Codex owns the shared
integration checkout and is working on compact service/controller routing,
agent-file integration, and the combined build map. Do not reset or edit Codex's
checkout, merge branches wholesale, or push to the integration branch. Commit
your completed slice locally and return its hash and patch for Codex to integrate.

Read these supplied documents as review material, with this assignment controlling
scope:
- C:/Users/A/Downloads/CODEX_HANDOFF_NOOA_SLICE1_STOP_20260914.md
- C:/Users/A/.codex/attachments/73409748-bec7-4aaa-bdbc-0d35e1a84f74/pasted-text.txt
- The current BOSS controller/compact-context specs and task maps.

1. Resolve the Slice 1 finding from actual code. Protected legacy BLD-1's prompt
   names 11 fields; BOSS's additive S120/S121 projection names 12, including
   disposition. Trace the real callers and validators. frankie_contract.py's
   opening documentation says the adapter carries disposition and the projection
   does not replace existing Frankie field population. Establish whether these
   are distinct seams or an actual sequential transform. Do not invent a
   postprocessor, add disposition to the frozen template, or weaken the final
   contract. Replace the proposed equality invariant only if source evidence
   proves it compares different interfaces, and document that correction with
   file/line citations. If ownership remains genuinely unresolved, report the
   specific missing evidence before changing that seam.

2. Implement one frozen Granite critique contract as the source for schema version,
   required keys, verdicts and output limits. Render the existing system prompts
   from it and make granite_output_schema consume the same limits. There are now
   THREE prompt variants: serialized V2, native V1, and compact native V1. Account
   for all three; the earlier ruling predates the compact codec.

3. Freeze current prompt bytes and SHA256 fixtures BEFORE refactoring. All three
   rendered prompts must remain byte-identical afterward. Keep existing public
   SYSTEM_TEXT names. Do not change output limits, add support/against caps,
   add knowledge inputs, or change valid-output acceptance.

4. Bind the new contract dependency into parser identity correctly. Unchanged
   prompt bytes do not mean unchanged parser source-code hashes. Report those
   identity changes honestly and prove that changing the contract cannot escape
   the parser/service/controller pins. Avoid import cycles in both package and
   standalone module imports used by the test suite.

Files you may change in your isolated worktree: new granite_contract.py and its
spec/tests/fixtures; granite_output_schema.py; granite_prompt.py; the prompt and
identity portions of granite_context.py and granite_context_compact.py; the
parser_code_hash helper in granite_shadow.py if needed; focused conformance tests.
Preserve de27bb26's negative-reference bounds fix. Do not change transport,
controller/journal routing, source/teacher/QSV/forecast code, legacy templates,
Memory A, workbook history, or OPEN_ITEMS terminal states in this slice.

Test with PYTHONPATH containing the repo root, research/kalshi/frankie_boss and
research/kalshi/frankie_boss/tests. Cover frozen prompt hashes, every enforced
limit at its boundary, malformed references, dependency mutation, import modes,
and existing Granite prompt/parser/shadow/native-service/SageMaker/controller
suites. Keep checkpoint dependency-isolation tests in a separate process if you
run the complete BOSS suite. No provider calls, training, replay, held-out reveal
or trading orders belong to this assignment.

Do not resurrect specialists, a native knowledge store, tree search, runtime
arbitration, a NOOA framework, or self-modifying prompts. Granite remains required
in final integrated tests; historical ShadowService names do not reduce its role.
The earlier Claude C3/C4 addendum remains with Codex's ordered remaining-build
work; do not implement it here.

Return: commit hash, changed files, test commands/results, frozen prompt hashes,
parser-identity migration explanation, legacy seam finding, and any exact blocker.
