# NOTE — the six deferred items, and what happened to them

Written at S115 close as "things seen and deliberately NOT edited" (Greg: *"leave any other edits
for next session. just make a note."*). Greg then said **"do the sg branch and the rest of your
plan"**, so five of the six were done in the same session. **The file is updated rather than
replaced, because the note's value is the record of what was seen and when** — a note rewritten to
look prescient is not a record.

**The andon board is ALL CLEAR for the first time.**

---

## 1. `store.py docs` crashed on an undeclared class — **DONE**

The `class_undeclared` gate added earlier at S115 lives in `docs_problems()`, so `store.py check`
and the andon did fire on it. But `cmd_docs` printed the class legend at `store.py:543` via
`store["classes"][cls]` and only called `docs_problems()` seven lines later — so the human-facing
listing died with a KeyError before the gate could explain itself. Now `.get(cls, "UNDECLARED - see
the class_undeclared gate below")`. **A crash is not a diagnosis.**

## 2. The classification gate only saw `research/kalshi/*.md` — **DONE, and it found something**

The docstring asserted the thing that was false: *"deliberately scoped to research/kalshi: repo-root
docs are covered by their own explicit entries."* **Measured: 13 tracked root-level `.md` had no
entry at all** — and one of them was **`OPEN_ITEMS.md`, a generated render the andon gates
byte-identical, absent from the very registry whose job is to know what every document is.**

Widened to walk the repo root as well; negative-tested by removing `OPEN_ITEMS.md`'s entry and
watching the gate fire, then restoring. All 13 classified: `OPEN_ITEMS.md` RENDER,
`S36_NETCOST_BACKTEST_FINDINGS.md` RECORD (CLAUDE.md's live dipole section cites it), and eleven
pre-Kalshi documents ARCHIVE with a one-line reason each.

**This was the A-24 defect one directory up.** The S115 inversion — stop asking "does the NAME match
a known pattern" (fails open) and ask "is this document CLASSIFIED" (fails closed) — was right, and
was then scoped to a single directory, which fails open on everything outside it. *A gate that fails
closed inside its box and open outside it is a gate whose box is the finding.* It also means the
three ChatGPT hand-offs arriving with the A-70 merge are now in reach of D36 on the day they land.

## 3. `station0/briefings` — **DONE. 8 of 13 unaudited -> all 13 audited, and it found four real gaps**

Not discharged by widening a glob. Every one of the eight was read and dispositioned:

| document | disposition |
|---|---|
| `G15_MBO_FIXES_FOR_CHATGPT.md` | 10 items: 7 settled and verifiable as such; **3 had no registry line -> A-73, A-75, A-76** |
| `CHATGPT_S112_SIX_WORKSTREAMS.md` | 6 tasks: 5 already covered (G-5 DONE, G-4, A-19/A-21, A-5/G-28, G-7); **Task 1 mapped onto NOTHING -> A-72** |
| `CHATGPT_S113_T1_NUCLEAR_OUTAGE_SOURCES.md` | the report's own final build decision: **A-17 split into A-17A/B/C/D**, parent stays open |
| `TURNAROUND_MEMO_S110.md` | 11 items, ten shipped at S110; **G3 collector-as-a-service was never built and never registered -> A-74** |
| `CHATGPT_BRIEF_S112.md` | outbound task packet — its recommendations live in the reply. Explicit zero, not "pending" |
| `NG_FORECASTER_PROBLEM_MEMO_S103.md` | outbound diagnostic; all four diagnoses traced to where they landed. **Nothing new to register, and that is the finding** |
| `..._ADDENDUM_FILES.md` | a file list. Explicit zero |
| `GAS_SIGNAL_BRIEFING_S111.md` | the raw body whose synthesis was audited at S112 into G-16..G-28. **Audited by structure, and the audit says so** — it does not claim the 344KB was mined |

**The four gaps are the point, and two of them touch live trading.** **A-73**: live MBO is *not
authorized* on the $179 Databento tier, the live collector *hot-loops* on the entitlement error
rather than failing loudly, and the tier that carries it is ~$1,500/mo — recorded at S103 and
unregistered for twelve sessions, against Greg's *"we need the live feeds... it's critical for live
trading."* **A-74**: collector-as-a-service, planned as half a session of work at S110, never built,
never tracked — and paper trading needs a loop that survives a session ending. **A-72**: the
order-flow direction nowcast, the highest-agreement result the desk has ever recorded, had **zero
registry lines**. **A-75/A-76** are small and real.

## 4. `records/` had no gate — **DONE, as an honest partial**

New `records` row: it proves a sweep *happened*, and its own message says it **cannot** prove the
sweep was complete, because nothing inside the repo can enumerate a directory outside it. INFO when
present, WARN when absent. A row implying completeness it does not have would be worse than no row.

## 5. `decisions` WARN on D1 / D13 / D32 — **DONE, and the gate itself was the defect**

The row's message offers two remedies — *"wire an enforcement or re-affirm"* — and only ever
accepted the first, because it read the **first** S-number in the session cell, which is the
original decision date and never moves. **A doc-only decision that was still correct could never
clear this line no matter what anyone did.** Now it reads the **max**, and re-affirmations append to
the session cell so the original date stays verbatim.

- **D1** (keys do not rotate during the walk) re-affirmed: still binding, expiry unchanged. *A
  decision not to act cannot be enforced by a gate, only re-stated on a date.*
- **D13** (gas-only scope) re-affirmed as honestly doc-only — D50 already corrected its false claim
  of enforcement.
- **D32** corrected: its `enforced_by` said *"nothing built"*, which stopped being true at S111.
  `FORECAST_ARCHITECTURE_S111.md` exists and the andon points every session at it; the curve
  scoreboard landed with A-1. **Still not built, and named so: the retrieval half (A-5, A-60/A-63).**
  Same species as D50, opposite sign — there the ledger claimed a guard that did not exist, here it
  denied work that did.

## 6. `registry_grep.py` — **DONE, promoted and improved**

Now `research/kalshi/registry_grep.py`: regex over every text field (not just the title), `--tier` /
`--status` / `--size` filters, `--full`, and — the part that earns its keep — when the match is *not*
in the title it prints **which field matched, with context**. That is what turned the briefing audit
from guesswork into measurement: `registry_grep.py 'Lee-Ready|order-flow direction nowcast'`
returning **0 of 181** is how A-72 was found.

---

## WHAT IS STILL OPEN

Unchanged and unaffected: **A-70** (review and merge `chatgpt/agent-frankie-s117` — the base branch
carries unread dashboard work) and **A-71** (move the already-paid head data out of the phantom
tree). Those two still gate A-67 arm 1, which is the frontier.

New from this pass and worth reading before the next data or live-lane work: **A-73** (the
entitlement decision — Greg's, not a build), **A-74** (collector-as-a-service), **A-72** (re-run the
direction nowcast causally against named benchmarks before anyone grants it authority).
