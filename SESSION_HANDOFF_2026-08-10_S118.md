# SESSION HANDOFF - S118 (2026-08-10)

**Branch `claude/kalshi-agents-coordinator-guard-sg0n15`. Brain s105.9, 90 plays - UNCHANGED, no
merge, no group run scored into the record.** Registry 192 -> 202 items (178 open: 26 ESSENTIAL,
45 BIGGEST_WIN, 108 REST); 23 DONE. Decisions 52 -> 53. Ten items raised (A-79..A-88), five closed
(A-77, A-80, A-82, A-83, A-88).

Two halves, and they are unrelated except in date: **Frankie actually ran**, and **Markets Terminal
became a durable read-only MCP service on the box.**

---

## PART ONE - FRANKIE RAN, AND THE RESULT IS NOT THE ONE THE HARNESS WAS BUILT TO PRODUCE

Full record: `research/kalshi/FRANKIE_S118_RESULTS_PAPER.md` (written for an external reader) and
`research/kalshi/records/S118/FRANKIE_S118_COMPLETE_RUN.json` (every forecast, its reasoning, its
outcome, its benchmarks).

### The corpus was rebuilt first, and its falsifier fired (A-77, DONE)

`build_legacy_actuals_a77.py` recovered the g6-g16 actuals from each `gN_score.json`. **The corpus
goes 70 -> 200 gradeable days**, which matters because S115 had asserted ~180 from narrative and the
measured number was 70. Each group carries a three-state basis verdict (`N0` / `OWN_LEG` /
`MIXED_LEG_CHANGES_INSIDE_WINDOW`) rather than an assumed one.

**The falsifier was run and it fired.** Tape reconciliation is exact on g12 12/12, g13 12/12, g16
11/11 - and **0/10 on g6, 0/11 on g10, 0/12 on g15**, with g8 7/10, g9 3/20, g14 2/12. A
single-leg rebuild would have measured **the wrong contract on 6 of 10 groups** while looking
perfectly well-formed. That is why the basis is recorded per group instead of assumed.

### Two defects had to be fixed before any number meant anything

- **A-80 (DONE) - the runner served ZERO plays on all 20 days while its preflight reported
  `PACKETS_CAUSAL`.** Three stacked shape assumptions against `brain_view`, each failing OPEN:
  `play_index` is an envelope with rows one level down; `plays` is a list keyed by `id`; the row's
  key is `play`. Fixed: **served_plays 0 -> 33.** A forecaster reasoning with no plays is not a
  degraded forecaster, it is a different experiment.
- **A-82 (DONE) - the leak guard hard-stopped on legitimate prior-group evidence.** It matched the
  TOKEN `actual_day_move_usd` wherever it appeared, including a play's evidence about g17's
  2026-04-22. Swept all 20 days: every outcome-token occurrence attached only to dates BEFORE its
  group's window, 0 reached into or past it. Rescoped to **dates, not names**; file tokens stay
  absolute; an undated realized value fails closed. **Negative-tested 7/7.**

### The run: three groups, thirty days, one variable

| arm | groups | sizing passage |
|---|---|---|
| A | g18, g19 | baseline - the shared role file's *"target honest under-100 USD error per day"* |
| B | g20 | that target withdrawn; size what the drivers support |

Everything else held: same brain, same causal slices, same contracts, same harness, same agent.

### The result, per event and never averaged (D4/D37)

Greg's correction mid-session - *"you cannot average. you have to look at every event individually"* -
**overturned my first read.** Pooled, the run looked like a wash. Per event it is not:

- **g18: improved 3/10, worsened 7/10, and worse on 6 of its 8 largest moves.** The emblem is 04-30 -
  the block's strongest coherent buy signal (only `b_share` above 0.50, `signed_flow` +7,783, big
  prints 0.621 clearing the gate) - direction called RIGHT and size **27% of the move**.
- **g19: improved 7/10, better on 5 of its 8 largest.** Best event of the run is 05-18: forecast
  `gw_cdd` tripled and the regime flipped `hard_cool`; the old harness called -550 into a +660,
  Frankie called +300, error 1,210 -> 360.
- **g20: improved 5/10, worsened 5/10.**

### The two findings that matter

**A-83 (DONE) - the under-emission is INSTRUCTIONAL.** *"Target honest under-100 USD error per day"*
on blocks whose realized moves run several hundred is **only reliably reachable by emitting near
zero**, because a small guess has a bounded error whether or not it is right. Withdraw it and the
band moves immediately: arm A `|guess|` p50 200 / MAX 330 / **0 of 20 events >= 400**; arm B p50 400 /
MAX 560 / **5 of 10 >= 400**.

**A-85 (OPEN, ESSENTIAL) - and it did not help, because SIZE CARRIES NO INFORMATION.** Sort each
arm's events by `|actual|` and read `|guess|` beside it: arm A smallest-half 100..270 vs
largest-half **90..330**; arm B 240..420 vs **250..560**. The ranges overlap almost completely in
both arms. Arm B overshot the quiet days (05-25 actual **30**, called 240; 06-02 actual **80**,
called 380) and still undershot the large ones (05-28 at 0.25x on a +2,100 day). **Under-emission
was the symptom; the disease is that magnitude is not being forecast at all** - a roughly constant
band is emitted regardless of the day, and varying the passage moved the band without touching its
discrimination. That is the direct argument for A-60/A-63: the band should be the empirical spread
of the matched cohort, not a number the agent produces.

**A-84 - a rule lost, and lost cleanly.** `selector.divergence_resolution` says default to the
tape/flow regime unless `gw_hdd >= 16.4 AND b_share >= 0.50`. Arm B applied it consistently and
**lost all three of g20's split days** (05-27, 06-04, 05-28: tape said sell, actuals +610, +1,130,
+2,100). Consistency is what made the loss legible. It may deserve DEMOTION rather than harder
enforcement, and the 200-day corpus now exists to settle it per cell.

### A-86 - THE RENDERS WERE RIGHT AND THE DATA WAS WRONG

Greg: *"these renders are completely wrong. there's only one point per day. why?"* Root cause is
mine and it is not the renderer. **`path_p50_curve` is a linear interpolation of the single net
figure already decided** - literally `[open, open+net*0.45, open+net*0.8, close]`. Four entries, no
intraday content: no ET hours, no onset, no turn, no shape. The canonical contract specifies
`[[et_hr, cum_usd], ...]` on the 2-hourly clock from the 20:00 reopen. **17 of the contract's 20
day-level fields were never emitted**, including `expected_magnitude_band_usd`, `onset_time_et`,
`turn_time_et`, `stand_down_reasons`, `evidence_used`, `evidence_rejected`. **It passed validation
anyway** because `_validate_day` checks that the curve is a list of length >= 2 - a straight line
satisfies that. D51 again: a gate that exists is not a gate that passed.

### Scope discipline on the run

This is **NOT A-67 evidence.** g18/g19/g20 are WALKED groups whose lessons are already merged. The
run validates contracts and plumbing. The architecture test still needs the unseen head, and **h1
(2025-08-04 -> 08-15) is staged but BLOCKED**: its fundamental stores are 2026-only, so 14 blocks
are empty and `state_health` correctly refuses it. Also declared, not hidden: the reasoning agent
was Claude on the runner's resume path, and **arm B's agent had already seen arm A's results.**

---

## PART TWO - MARKETS TERMINAL: A READ-ONLY MCP SERVICE, DURABLE ON THE BOX

Driven by ChatGPT through the shared ledger `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md`
(blocks C2C-004 .. C2C-007).

### What exists now

`mcp_server/` in git: a **read-only MCP server over this repository**, two tools only -
`markets_repo_status` and `markets_read_file`. Deliberately absent: command execution, writes, git
mutation, AWS/IAM surface, secret retrieval, unrestricted filesystem access, network listener.
Containment resolves `realpath` FIRST and compares on path COMPONENTS (`commonpath`), because a
`startswith` on the raw string admits both `../../etc/passwd` and a sibling `Markets-secrets/`; a
credential deny list runs after containment; binary fails closed on strict UTF-8; a 256 KB cap
REFUSES loudly rather than truncating silently.

**Running on the durable box** `i-08cee7171c0a76a04` as `markets-mcp-tunnel.service` (systemd,
enabled), from its own checkout at `/opt/markets-terminal`, on the **official checksum-verified
tunnel-client v0.0.11**. A-88 DONE. Proven by observing each thing happen: `kill -9` the main PID
(new PID, MCP child respawned, `/readyz` 200), `systemctl restart`, and a real MCP client
post-recovery passing discovery, repo status, one safe read and **9/9 containment refusals**.

**Reboot: NOT TESTED, deliberately.** The box also hosts `markets-desk.service`, Greg's live
dashboard, up 19+ days. Rebooting to prove our service returns would take his down. Isolation was
asserted at every step and re-checked after the kill tests: separate checkout, separate port
(8080 vs 8091), no systemd coupling either direction, and the desk's process uptime intact
afterwards - it never restarted.

### THREE WRONG CAUSES IN A ROW, AND THE ONE THING THAT WORKED

The tunnel returned `tunnel_use_forbidden` for hours. I proposed, in sequence:
1. **project mismatch** (`sk-proj-` keys are project-scoped) - REFUTED by the vendor's own doc,
   *"tunnel permissions are organization-level, not project-level"*, which I had not read before
   advising Greg to go check the wrong settings page;
2. **billing / missing entitlement** - argued at length, REFUTED because the fix arrived with no
   purchase ever made;
3. **key permissions** - never needed.

**The actual cause was the tunnel itself.** Greg created a NEW tunnel and it authorized on the first
attempt with the same key, org, binary and profile shape. Every theory was plausible, well-formed,
and reasoned from **how the platform should work rather than from anything measured about that
specific tunnel**. The only move that paid was ordering the cheap one-call retest first. The wrong
reasoning is left standing in the ledger with a correction appended, because the pattern is the
lesson.

### TWO DEFECTS IN MY OWN DEPLOY SCRIPT, THE SECOND WORSE THAN THE FIRST

- **`deploy_box.sh` pinned the superseded binary's hash**, so the documented update AND key-rotation
  path would have **silently reverted** the v0.0.11 upgrade. Now fetches the official release zip
  from GitHub (S3 mirror only if GitHub is unreachable) and verifies TWO hashes - the zip against
  the vendor's published `SHA256SUMS`, then the extracted binary.
- **Testing that fix exposed the real one: the script had been ABORTING BEFORE IT DEPLOYED.**
  `EXIT=2`, reproducibly. `doctor`'s `health_listener` check BINDS 127.0.0.1:8080; against a live
  service that bind fails, doctor exits non-zero, and under `set -euo pipefail` the script died
  there - before installing the unit and before restarting. **The first deploy passed only because
  the port was free on a fresh host**, so the bug was invisible exactly once and would have applied
  NOTHING on every update afterwards while printing a mostly-successful log. Fixed by stopping the
  service before the preflight, which also makes the check mean something.
  **It was hidden by my own test method**: I piped the script to `grep`, so the exit status I read
  was grep's. It surfaced the moment I captured the exit code directly.

### C2C-007 STOPPED - both plugin paths are blocked, and the reason is structural

Codex cannot consume the tunnel through a plugin package:
- `mcpServers` -> `.mcp.json` documents **local stdio `command`/`args` only**, so it can only launch
  a SECOND MCP server - forbidden by that task, and it would not use the tunnel at all;
- `apps` -> `.app.json` needs an id beginning `plugin_asdk_app...` **minted in ChatGPT developer
  mode**, i.e. the Chat seat the task existed to avoid buying.

Tested and falsified the promising third route: Codex CLI genuinely supports remote MCP
(`codex mcp add --url --bearer-token-env-var`), but `/v1/mcp/{tunnel_id}` returns **404 to the
runtime key on every method**, while `/v1/tunnels/{tunnel_id}` returns 200 on the same credential in
the same minute and a known-bad route returns the same 404.

**The structural point worth carrying forward: the tunnel publishes a LOCAL MCP server to a product
that cannot run local code. ChatGPT cannot; Codex can.** So for a Codex seat the tunnel is a detour
with no supported entrance, and the clean answer is a local stdio plugin running the same code from
the repo Codex already has - no tunnel, no connector, no Chat seat. **Not built: it needs Greg or
chat to relax the "no second MCP server" constraint**, which is theirs to relax, not mine to route
around.

### The logo

`mcp_server/logo/markets_terminal_icon.svg` - candidate A, "Forward Curve", Greg's pick. Built on
D32 (the product is a curve): anchor, week one, **the weekend GAP**, week two, the print. The gap is
the point - drawing a line through untraded hours is what our own render rule forbids. Two rejected
candidates kept beside it as the record. Known limit stated up front: A is the weakest of the three
at 32px, accepted deliberately, with the fix named if it ever bites.

### THE SHARED LEDGER WAS TRUNCATED AND RESTORED (D53)

ChatGPT's C2C-007 registration commit `4947da7` **replaced the coordination ledger rather than
appending: 637 lines -> 35.** Everything from C2C-003 through the C2C-006 addendum was removed and
stood in for by one line reading *"[CONTENT PRESERVED THROUGH C2C-006; append-only continuation]"* -
which asserted preservation while being the deletion. Restored at `ffd6556` (792 lines, all blocks
plus an integrity note and the billing correction). Nothing was permanently lost; git had it at
`cb149e1`.

**Why it mattered rather than merely annoyed:** the most useful thing in the deleted range was the
`deploy_box.sh` silent-abort defect - a bug in the deploy path ChatGPT itself depends on, which
stayed hidden for a full cycle precisely because a script reported success while doing nothing. **A
shared record that reports continuity while dropping content is that same failure shape one layer
up**, and it was found only because Greg asked whether the notes had been committed.

---

## STANDING / OUTSTANDING AT CLOSE

- **ROTATE THE OPENAI KEY.** It was pasted into chat and must be treated as compromised - the same
  exposure as the AWS pair at S99. Rotation path is now clean and idempotent: rotate ->
  `python research/kalshi/creds.py --sync-ssm` -> `bash mcp_server/deploy_box.sh` on the box. The
  key reaches the box via SSM SecureString (`/markets/OPENAI_API_KEY`) and is written to
  `/etc/markets/tunnel.env` 0600 by a script running ON the box - never as an SSM command argument,
  because RunShellScript text is retained in command history and CloudTrail.
- **A-85 (ESSENTIAL) is the next experiment, and it is NOT another forecast run.** It is A-85's
  falsifier: find any served quantity that separates large-move days from quiet ones across the
  200-day corpus (`vol_regime`, realized sigma, options-implied move, `|signed_flow|`, forecast run
  delta). If one does, this is a serving gap. If none does, the honest product is a band and
  `path_p50_curve` should be REMOVED rather than filled with decoration.
- **A-86** - the contract emits 3 of 20 fields and validation cannot see it.
- **A-87** - the always-on token budget, once the connector is actually in use. Measure first: the
  faucet is the TOOL BOUNDARY (256 KB per `markets_read_file` call), not the model. Ships through
  A-65's validated-compaction diff, not around it. Its own falsifier says close it as ceremony if a
  real day's usage turns out cheap.
- **A-70** (merge review of `chatgpt/agent-frankie-s117`) still open; **A-79** (Bedrock agreement),
  **A-81** (g11's 12 days), **h1** blocked on 2026-only fundamental stores.
- **The end-to-end ChatGPT -> tunnel -> tool call has still never been observed.** The host answers
  a real MCP client with 9/9 containment intact; that is not the same claim (D51).

---

## POST-CLOSE ADDENDUM - THE BOX NOW SERVES CHATGPT'S BRANCH, NOT OURS

After the close-out above, Greg directed the durable checkout at `/opt/markets-terminal` to
`chatgpt/agent-frankie-s117` @ **`d539c2a`** ("Fix MCP v2 ToolAnnotations field names"), and only
`markets-mcp-tunnel.service` was restarted. Verified: HEAD `d539c2a`, working tree clean, service
active on a NEW MainPID, `/readyz` ready, `/healthz` live. Nothing else on the box was touched.

**This matters for the next session and is easy to miss.** `markets_read_file` and
`markets_repo_status` serve **whatever that checkout holds**, so the repository ChatGPT reads through
Markets Terminal is now chat's Frankie branch - not `claude/kalshi-agents-coordinator-guard-sg0n15`,
where this session's work lives. Two consequences:

1. **`markets_repo_status` is the check, not an assumption.** It reports branch and HEAD; read it
   before concluding anything about what the other side can see.
2. **Work committed to the claude branch is invisible through the connector** until the box is
   pointed back or chat's branch carries it. The deploy path
   (`cd /opt/markets-terminal && git pull && bash mcp_server/deploy_box.sh`) is idempotent and will
   happily run on either branch, so the branch is a deliberate choice each time rather than a
   default.
