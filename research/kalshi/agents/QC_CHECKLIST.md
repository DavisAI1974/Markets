# QC_CHECKLIST.md — the conformance sweep (S110; Greg: "sonnet or haiku can easily and quickly run
# through a check list... they just make sure everything is running as it should")

**WHO RUNS THIS:** a small model (Sonnet/Haiku), once per session (SOP QA CADENCE), or any time Greg
asks "is the plant okay." **AUTHORITY: REPORT-ONLY.** You are the andon cord, not the mechanic — you
NEVER fix, edit, delete, re-run a failed step, or "clean up" anything. If an item fails, you STOP
that item, record the evidence, finish the remaining items, and deliver the report. Changing things
is a different job, done by a different session, under `agents/RUN_SOP.md`.

**HOW TO RUN:** execute each item's command from `E:\Markets\research\kalshi` (item 0 from repo
root), compare output to EXPECT, mark PASS / WARN / FAIL exactly as the rules say. No judgment
calls: if an output is not clearly the EXPECT, it is FAIL with the output quoted. Deliver the
report in the format at the bottom.

---

## ITEM 0 — the branch box
```
cd /e/Markets && git rev-parse --abbrev-ref HEAD && git log --oneline -1
```
EXPECT: branch `claude/kalshi-agents-coordinator-guard-1175nr`; tip message begins with `S1..` (a
session-numbered commit). FAIL if any other branch. STOP RULE: on FAIL do not run further git
commands; report immediately (wrong-branch sessions must not touch files).

## ITEM 1 — the andon board
```
cd /e/Markets/research/kalshi && python plant_status.py
```
EXPECT: final line `ALL CLEAR`, exit 0. Every `FAIL |` row is a FAIL for this item (quote the row).
`WARN |` rows: copy them into the report as WARN, they do not fail the item. Do not re-run on FAIL.

## ITEM 2 — the gold vault, directly (defense in depth; 10 seconds)
```
python verify_gold.py
```
EXPECT: `PASS - all frozen gold files byte-exact` AND `runtime reasoning == gold`. A TAMPERED
verdict is FAIL — quote it, do NOT touch any file in agents/. (Known benign cause on a fresh
Windows checkout: CRLF conversion — the report should note "possible CRLF class, see RUN_SOP STEP
0.4" but the verdict stays FAIL for a fixing session to confirm.)

## ITEM 3 — SOP version coherence
```
grep -n "^- v" agents/RUN_SOP.md | head -3
```
EXPECT: the top version-log line's version (e.g. `v1.2`) is mentioned in the LATEST
`SESSION_HANDOFF_*.md` or was created this session. WARN (not FAIL) if you cannot establish it —
note "SOP version unconfirmed against handoff."

## ITEM 4 — the decision ledger sweep
Covered by ITEM 1 (`decisions` row). Additionally:
```
grep -c "^| D" ../../DECISIONS.md
```
EXPECT: a count >= 20 (the ledger only grows; it is append-only). FAIL if the count SHRANK vs the
last report (deletion from an append-only ledger) — if no last report is available, record the
count for the next run.

## ITEM 5 — blind immutability spot-check
```
cd /e/Markets && git status --short research/kalshi/forecasts/ | grep -E "grp[0-9]+\.json" || echo CLEAN
```
EXPECT: `CLEAN` (no assembled blind `grp<N>.json` is locally modified — they are immutable records).
Any modified `grp<N>.json` is FAIL, quote it.

## ITEM 6 — no off-SOP artifacts in agents/
```
cd /e/Markets && git status --short research/kalshi/agents/ || echo CLEAN
```
EXPECT: empty output or `CLEAN` — the canonical rule files and SOP change only via committed,
version-logged edits. Any uncommitted modification under agents/ is FAIL.

## ITEM 7 — reasoning bound to decisions (v1.4)
```
python decision_trace.py verify g22
```
EXPECT: `0 UNRESOLVED`. Any `STALE` line is a FAIL (a ledger describes a number the system no
longer holds). An `UNBOUND ... UNDECLARED` line is a FAIL; `LEGACY-DECLARED` is a PASS (a
pre-binding ledger that says so). Substitute the group under review for g22.

---

## THE REPORT (deliver exactly this shape)

```
QC CONFORMANCE REPORT - <date>, session <S-number if known>
ITEM 0 branch:        PASS/FAIL <evidence if not PASS>
ITEM 1 andon:         PASS/FAIL - FAIL rows quoted; WARN rows listed
ITEM 2 gold:          PASS/FAIL
ITEM 3 sop-version:   PASS/WARN
ITEM 4 decisions:     PASS/FAIL (count=N)
ITEM 5 blind-immut:   PASS/FAIL
ITEM 6 agents-clean:  PASS/FAIL
ITEM 7 reasoning-tie: PASS/FAIL (N ids checked)
VERDICT: ALL CLEAR | N FAIL - LINE STOPPED, human review required
```

Rules of conduct, repeated because they are the job: report-only; never fix; never delete; never
re-run a failing command hoping it passes; never mark WARN as PASS; quote evidence verbatim. A
short honest report beats a clean-looking one.
