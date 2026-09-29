# HANDOFF 2026-09-29 00:1xZ ET: the principal is Frankie's code; Granite is the critic only; r10 not started

Branch `claude/frankie-monday-cycle-0-urozez`. Code tip `8e4ec92` (this handoff's commit follows it). Launch is on HOLD:
nothing was staged, dispatched, started or stopped on the box this session. Every push carried `[skip ci]`.
Previous handoff: `HANDOFF_20260928_JOINED_TEACHERS.md`. Drop-in box: `DROP_IN_20260929_PRINCIPAL_CODE.md`.

## Why this session ended
It ran as a chat session. From there, dispatching `frankie_box_run.yml` with the repo's GitHub token was refused by the
session's per-action safety check (flagged as data exfiltration for the S3-reading Jev report probe). The network was
not the cause (api.github.com answered 200). Greg is starting a Code session to do the dispatches.

## Greg's decisions this session (in order)
1. Build plan: R2 is not in the repo; R3 (2026-09-14) and R4 (2026-09-21) are, and they differ. Greg: use R3's Granite
   roles, "except for the pod use", and "Pod serves the critic only". Granite = the B2 shadow critic (C21-C24) on the R4
   Pod. C35 (Granite as Frankie's engine) is no longer a Granite role.
2. "Granite has absolutely nothing to do with classroom anymore." The classroom is answered by Frankie's code.
3. "Frankie does the analysis." Its sections (Greg, verbatim): what he learned in the classroom; what he learned from
   the cycles/calcs; new exhaustion findings; his suggestions to improve the daily runs and any additional calcs;
   things to improve him; any trade signal insight.
4. "The only analysis granite should do is to say how he feels he performed" (read as: Granite on its own performance
   as the critic; confirm with Greg if he meant Frankie's performance).
5. "The boss is much bigger than granite. He's actually a pretty small piece of it. Refer to the excel sheet." The BOSS
   is the whole native system (B0/B1/B2: trunk, B1 recurrence, ReFRAG/QSV, BLD-1, heads, teacher); Granite is its small
   C21-C24 critic. Old code calls Granite's vLLM "the BOSS"; new code never does.
6. Serverless: "Not using serverless anymore." Removed.
7. The two teachers stay tied with separate roles; the three seats (Frankie, the BOSS teacher, the scientific teacher)
   discuss findings and dipole discoveries and Frankie is taught. Greg agreed the Granite confusion came from putting
   Granite in every seat. Scientific teacher = the experiment's search (no model seat). Rules file confirmed.
8. Pearson: "We want the coefficients, just not a bunch of dipole results flattened or normalized"; "We can define a
   group them over a certain range but not an average". Coefficients kept; co-movement counts added beside them.
9. The critic's knowledge loop and priming: "fine" (kept). They are not bedrock (five legacy method statements).
10. The bedrock-built exhaustion/D priming: "Get rid of bedrock and leave something small in there ... plus he'll have
    frankie talking to him"; "We decided to put the priming in because he wasn't doing anything." Removed; a small code
    priming replaces it.

## Built (all py_compile python3.12 only; nothing run)
| Commit | What |
|---|---|
| edab906 | `.mcp.json` + `enabledMcpjsonServers` for codebase-memory-mcp on this branch (copied from the trunk) |
| 7260c6e | Granite inventory `GRANITE_CALL_INVENTORY_R10_20260929.md`; classroom and correction scientific-dialogue branches refuse; serverless lane removed (Pods only; `serverless.json` on the box refuses at preflight/run); `.cbmignore` re-includes `deploy/` |
| 694c8d1..8c27e41 | `SPEC-decouple-granite.md` DECISION block (R3 roles on the R4 Pod; decisions 1-5), R3 vs R4 cell diff in the inventory |
| 1ec9bf6 | `SPEC-scientific-teacher.md`; `knowledge/CLASSROOM_RULES_V1.json` (17 rules, each sourced; confirmed) |
| 21edfb9, 3a07433 | Pearson removed then restored (Greg corrected); each of the 171 pairs now also carries `DIPOLE_PAIR_CO_MOVEMENT_COUNTS_V1` |
| 8e4ec92 | THE PRINCIPAL BY CODE (below) |

`8e4ec92`, in `deploy/aws/box/`:
- `frankie_box_boss_session.py`: reading = the corpus recorded whole by code (no model reading or merges); classroom and
  correction answered by `frankie_box_classroom_code.py`; `teach` files a SMALL priming (`work/teach/priming.md`, no
  bedrock); writing by `frankie_box_writing_code.py`; `_granite_self_assessment` = Granite's one call, over its own
  critic output from `critic-spool/*/outcome.json`, never blocking (C24; `SoftRefusal`); the run and the correction
  need no Pod; a response written earlier by a model is rewritten by code.
- `frankie_box_classroom_code.py` (new): TEACH answered in the parsers' own shapes (counts, extremes, the teacher's
  coefficient and co-movement counts per pair, the teacher's wording quoted as the teacher's, UNKNOWN where nothing
  computes); GUIDED/SOCRATIC/VERIFY refused with the reason (never answered from the host key); novel findings only
  where a pair's first-to-last relation and its step counts disagree (filed as HYPOTHESIS); the rules file loaded and
  witnessed in the classroom receipt.
- `frankie_box_writing_code.py` (new): the analysis in Greg's six sections plus Granite's labelled section; the
  accounting entry (every required layer, status as derived, comparison "by shape only"); the ten output ledgers.
- `frankie_box_brain.py` / `frankie_box_docs.py`: the bedrock priming is never carried; `priming.md` is.
- `frankie_box_classroom_cache.py`: identity includes the code module and the rules file.
Only reachable model call in the principal now: writing -> `_granite_self_assessment` -> `boss`.

## Untouched on purpose
Pinned files (projection, context_session, c15_journal, c15_teacher_r3, normalizer); the launch critic
(`run_actual_sunday.py`) with its priming and knowledge loop; the Pearson 8-point floor; Frankie's bedrock DERIVATION
(the teachers read it); the now-unreachable `_merge`, `_read_part_guarded`, `_boss_complete`; tests for the old paths.

## Open for Greg
- "Get rid of bedrock": done for the priming only. If he meant bedrock out of the whole run, that is a bigger change.
- The Pearson 8-point floor (report every coefficient with its overlap count instead?).
- Decision 4: Granite rating itself as the critic, or rating Frankie?
- Jev: his reports were never read. Probe below; then report what the data shows, turn by turn.
- Tests for the removed Granite/serverless/dialogue paths would fail if CI ran them.
- The new code has never run; the r10 principal is its first real run.

## Next, each box step on Greg's go (all through `.github/workflows/frankie_box_run.yml` on this branch)
1. Jev (read-only, no go needed): script `deploy/aws/box/frankie_box_jev_reports.sh`, presign
   `getprefix:frankie-granite42-568968024170-us-east-1/clm-sidecar/monday-20260928-jev1/`.
2. Billing check (read-only): `frankie_pod_control.yml` action=list and `/opt/frankie-box/pods.json`; box processes
   `frankie_box_read_log.sh MODE=processes`. Never stop a Pod without Greg's word.
3. Serverless leftover (read-only): `frankie_box_serverless_config.sh ACTION=show`; if present, `ACTION=remove` on go.
4. Stage the tip: `frankie_box_stage_code.sh ACTION=stage`; note CODE_ROOT; push nothing after, or restage.
5. r10 config: `frankie_box_cycle0.sh ACTION=config CODE_ROOT=<staged> RUN_ID=monday-20211004-20260928-r10
   PREPARED=/opt/frankie-box/work/trading-day-preparation/full-20211004-20260927-r6-48/prepared-configuration.json
   PRINCIPAL=/opt/frankie-box/work/principal-inputs/full-20211004-20260928-v9-r2/principal-inputs-receipt.json
   OUTPUT_ROOT=/opt/frankie-box/work/monday-run-config/full-20211004-20260928-r10` (no JOINED). Confirm
   `classroom_scientific_dialogue: false`.
6. Launch: `ACTION=launch CODE_ROOT=<staged> CONFIGURATION=<r10 actual-host-configuration.json>`, timeout 43200,
   probe attached. The critic runs here (needs the Pod). Exit 3/4 = pending at the WAIT.
7. Principal: `ACTION=principal CODE_ROOT=<staged> CALCULATIONS=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48
   REQUEST_DIRECTORY=/opt/frankie-box/work/runs/monday-20211004-20260928-r10/execution/cycle-00/principal`, timeout 86400,
   probe attached. Stages: verify, labels, derive, compare, reading (code), classroom (code), teach (small priming),
   writing (code + Granite's self-assessment), push.
8. Record initial, correction, record correction (the drop-in and MONDAY_CHECKLIST_20260927.md differ on RESUME steps; ask).
