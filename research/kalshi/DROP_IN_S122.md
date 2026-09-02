# DROP-IN S122 - FEED HIM: THE SUNDAY RE-RUN ON THE WIRED CODE, THE SPAWN, THE REVEAL

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Check `git log --oneline -1`; the tip must be
the S121 close commit named in `SESSION_HANDOFF_2026-09-02_S121.md` section 9 or later. Read that
handoff sections 0, 4 and 9, then `FRANKIE_BUILT_NOT_WIRED_SEARCH_S121.md`, then
`FRANKIE_WIRING_TODO_S120.md`, before anything else.

## ITEM ZERO - GREG'S RULINGS ARE THE SPEC (D81-D86; verbatim in DECISIONS.md)

1. Frankie does the calcs himself from every record of every field for the day, delivered as it
   arrives in RT (F_LAST-closed groups in `ts_recv_ns` order, never ahead). The runner's result is
   not his evidence (D81).
2. A layer's evidence binds to the file that carries it, never to a document describing it (D82).
3. **Zero hardcoded time intervals for anything.** Every time is derived from the actual events on
   the clocks built for it; the seven clocks are wired into Frankie (D83).
4. A persona on a long build pushes its own branch after every commit; a save point that exists
   only in a container is not a save point (D84).
5. **One arm, and it is A_MEMORY** (D86; D85 superseded). Memory is his own day-over-day carry of
   his frozen outputs, SEEDED on day one with every committed output of the past runs, provenance
   labelled, every lesson UNVERIFIED until he verifies it against the stream; the wrong-data run
   32851909748-1 is in the seed AS the wrong-data run. A-clean is retired; its overlay, profiles and
   workflow stay as inert records until their removal is discussed (D60).
6. No historical number is a spec; derive counts from the registry and contract at validation
   time; no floor below the full count. Nothing dropped without discussion (D60); keep-everything
   is a first-class answer (D76). A helper is a tool invocation inside a role, never a lane (D63/D64).
7. **Search before building** (S116, and again S121): every "build" item of S121 turned out to be
   a wiring item. When something is still unwired after the personas, search for its producer first.

## ITEM ONE - FEED HIM (Greg's go required; the box)

1. Dispatch the A-MEMORY launch workflow (`frankie_a_memory_rt_native_launch_20260828.yml`) on the
   wired code for Sunday 2021-10-03: canary first (D79 configuration: aliasing on, change points on
   - which is now the default), then the full run.
2. Re-dispatch `frankie_ledger_delivery_20260902.yml` pinned to the new run; download the manifest
   artifact; `fetch_frankie_ledgers fetch` into `data/` (about 12.6 GB; never the scratchpad, D34).
3. `emit_frankie_spawn` against the new result and delivery receipt: it now builds the knowledge
   receipt from the manifest, runs the crosswalk and REFUSES unless every applicable input is
   DELIVERED, proves the sealed set absent, and writes the knowledge bundle, receipts and proof
   beside the prompt. A refusal names the offenders; fix the feeding, never the gate.
4. Spawn him as an agent session over committed files (D70). His artifact returns the findings, the
   output bundle directory, `outputs_receipt_sha256`, `knowledge_receipt_sha256`, `knowledge_use`.
   `native_staging read-back` validates the bundle, attaches the findings, renders the report with
   the crosswalk table, and builds the one-way handoff and first lock from the bundle.
5. STOP for the reveal (D68). Then Monday the same way, with Sunday's frozen outputs as memory.

## ITEM TWO - IF ANYTHING IS STILL UNWIRED

Section 9 of the S121 handoff lists what each wiring persona could not finish. For each: run a
read-only search for an existing producer FIRST (the S121 search agents' briefs are in the handoff's
section 4 and the search record), then a test-engineer persona wires it; `isolation: worktree` cut
by hand from the tip; commit and push per slice (D84); one arm, A_MEMORY.

## STATE (completed at the S121 close, section 9 of the handoff)

Tip, test count, the three wiring merges, the cross-persona call sites, F-22 onward.
