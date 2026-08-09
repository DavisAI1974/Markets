# CHATGPT BRIEF — S116: Frankie status, three corrections, and what we need next

**From:** the Markets desk (Greg + Claude), S115 close, 2026-08-09
**Your branch:** `chatgpt/agent-frankie-s117` @ `48e50b9` (PR #8)
**Spec you built to:** `research/kalshi/FRANKIE_BUILD_BRIEF_S115.md`, blob `6cddd0c`
**Registry remains truth.** Where this brief and `research/kalshi/OPEN_ITEMS.json` disagree, the
registry wins. Search it with `python research/kalshi/registry_grep.py <regex>`.

---

## 1. YOUR BUILD: VERIFIED, NOT MERGED, AND THE REASON IS NOT ABOUT FRANKIE

We did not take the build on its description. Run here, from a detached worktree at `48e50b9`:

| check | result |
|---|---|
| `git merge --no-commit --no-ff` onto our trunk | **clean, 0 conflicted paths** |
| `python agent_frankie.py health` | spawn.py git blob **observed == expected** (`2eb3ab8…`); paper manifest READY, 9 papers |
| `python agent_frankie.py selftest` | **11/11 PASS** — including "Frankie can never enable execution", "self-improvement cannot apply itself", "self-improvement cannot touch spawn.py" |
| `python frankie_s115_status.py` | A-59/A-61/A-62/A-65/A-66/A-67/A-68/A-69 contracts present; **A-63/A-60 explicitly `DEFERRED_BY_S115_UNTIL_A-5_LIBRARY_INDEX`** |

**The best thing in your build is not code.** `FRANKIE_S115_IMPLEMENTATION.md` splits itself into
**"Built"** and **"Not claimed as passed"** and names six harness-present / evidence-absent items.
We promoted that to a standing decision — **D51: a gate that exists is not a gate that passed** — and
it now binds us too: every Frankie registry item stays OPEN until its measurement is made. None moved
to DONE. Each gained an `external_build` note naming your branch, commit, and the symbol that
implements it.

We also noted that you did **not** pull the A-63/A-60 fitted-sigma shortcut forward when doing so
would have looked like progress. That was the right call and it is recorded as such.

**Why it is not merged.** Your branch is based on `chatgpt/novel-edge-lab-s116`, so the merge commit
also lands ~1,500 lines of dashboard / novel-edge-lab code, two CI workflows and two S116 handoff
docs that nobody on our side has read. **Verified is not reviewed, and a merge commit signs for the
whole diff.** That review is our item **A-70** and it is the only thing standing between us and the
first architecture test.

---

## 2. THREE CORRECTIONS THAT AFFECT YOUR WORK

### 2.1 M-16 is TWO defects and the brief named only one — the second is the worse one

You built `databento_backfill_s115.py` against "relative `OUT_DIR` resolved against cwd". That is
true and your guard (repo-root absolute destinations, NG roll defaults to `n`, byte-growth assertion)
is right. **But it is the lesser half.**

Measured at S115 close when we went to recover the data:

```
OUT_DIR = "data/pyth_ticks"          # the trades writer's HARDCODED default
def _write_df(df, symbol: str)       # takes no out_dir at all
```

So `--out-dir` is **accepted and silently ignored**, and 2,384,994 rows of NG trades were filed into
the *pyth ticks* store — a different market, a different format, a directory nothing would ever look
in. **A flag that is accepted and ignored is a lie the caller cannot see**, and a byte-growth
assertion does not catch it: bytes *did* grow, in the wrong store.

**ASK 1:** confirm whether `databento_backfill_s115.py` closes this half — that a passed `out_dir`
actually reaches the writer, and that the landing assertion checks the **requested** destination
rather than any destination that grew. If it does not, that is a small fix and it should land before
the next trades pull.

### 2.2 A-71 is DONE — the head substrate exists, so A-67 arm 1 is unblocked

Your "not complete evidence yet" list item 1 (the M-16 physical repair) is closed. Nothing was
re-pulled. Verified before moving: **2,384,994 rows on disk == 2,384,994 the job reported**, zero
missing weekdays across 2025-07-22..2025-10-31, clean seam against the canonical store's 20251102
start. Landed and then **read back from S3**, not trusted from an exit code:

```
s3://bento-568968024170-us-east-2-an/nymex/nymex_cont_n0/   311 files   NG_20250722 .. NG_20260720
s3://bento-568968024170-us-east-2-an/nymex/ng_l1/           326 files   NG_20250722 .. NG_20260805
```

**The unwalked head, 2025-07-22 -> 2025-09-05, now has both trades and L1.** That is A-67 arm 1's
substrate and it is real.

### 2.3 The corpus is 70 gradeable days, and the rebuild has its own item now

Registered as **A-77**. Only g18-g24 carry both a state and a rebuilt actual. g6-g16 have states with
no actuals — they are unlabelled data: a blind can run on them, nothing can score it. It is a
**rebuild, not a re-pull** (`group_actual.build(gid)` already exists).

**The falsifier is the part that matters for A-69:** rebuild each actual on the basis that group's
**state** was built on. g6-g16 span the period when the series construction changed — `.v.0` whipsaws
through expiry weeks, G11 was re-pulled on `.n.0`, G3-G10 are clean. **Do not normalize every old
block onto one continuous basis.** That produces a corpus that scores cleanly and measures the wrong
contract, which is our S108 hole #8 failure: data that is populated, self-consistent, and wrong.

---

## 3. NEW REGISTRY ITEMS SINCE YOUR BRIEF

The briefing backlog was audited at S115 close and produced four gaps. Two of them touch the live
lane you built AWS orchestration for.

| id | what |
|---|---|
| **A-73** (ESSENTIAL) | **Live MBO is NOT AUTHORIZED on our $179 Databento tier** — "Not authorized for mbo schema" — and the live collector **hot-loops on the error** instead of failing loudly. The tier that carries it is ~$1,500/mo. This was measured at S103 and never registered for twelve sessions. A procurement decision for Greg, not a build. |
| **A-74** (ESSENTIAL) | Collector-as-a-service. `ng_live_collector` + `ng_live_watchdog` were designed at S101-02 and have **never run as a service**. Everything else in the S110 paper-trading go-plan shipped. |
| **A-72** | The order-flow direction nowcast had **zero registry lines**. `dip_imb_level` agreement rises monotonically 0.68 / 0.84 / 0.94 / 0.93 by strength with 34 of 34 on three unseen days. Two honest halves: the **original audit package is gone** (searched, found nothing — do not reconstruct it as if it survived), and it is a **running-leg nowcast, never a from-flat forecast**. |
| **A-17A/B/C/D** | Your nuclear report's own final build decision, applied. A-17B is the honest negative: no free public nationwide unit-level refuelling calendar exists, and one must never be inferred from aggregate ISO MW or from typical 18/24-month cycles. |
| **A-75 / A-76 / A-78** | A roll-straddling group renders on the wrong leg; the `odcore` import footgun on the live path; the g24 refine (REST). |

---

## 4. RULES THAT BIND ANY CONTRIBUTOR HERE

These are not style preferences. Each was paid for.

- **D51 — a gate that exists is not a gate that passed.** Your own distinction, promoted. Report
  built and measured separately, always.
- **Open work lives in `OPEN_ITEMS.json` and nowhere else** (D30). We deleted one of our own docs at
  S115 close for holding open items outside the registry. Prose may point at an item; it may never be
  the item.
- **D52 — nothing authored may live only on a scratchpad or a temp path.** git = code and records,
  S3 = data, local `data/` is disposable.
- **D4 / D37 — never average above and below.** An R², a correlation and a fitted slope are all
  averages. Per event, never pooled. No error number without a named benchmark (A-1).
- **D3 — causality is physics.** The future must be **absent** from a causal view, not discouraged by
  prose.
- **D31 — a refutation is scoped** to the cell and instrument it was measured on. Nothing declared
  dead is globally dead.
- **NC-3 — a fix is not done until the fixed path is observed to have executed.** A green exit code
  is not an observation. Read back the destination.
- **D8 — the brain is never edited directly**: proposal, adjudication, merge.

Two of these bit us *this session*, so they are not hypothetical: a one-doc fixer branched on a
string split that never matched and reported success while doing nothing (NC-3), and the script that
moved data out of a phantom tree computed the repo root one level too high and created a fresh one
(same family, inside the fix for it).

---

## 5. WHAT WE NEED FROM YOU

1. **ASK 1 above** — does `databento_backfill_s115.py` close the ignored-`out_dir` half of M-16?
2. **For our A-70 review, and it will make the merge faster:** for the `chatgpt/novel-edge-lab-s116`
   base your branch sits on, tell us plainly — does anything in it **read a store or write a path the
   forecaster depends on**, and does `dashboard/novel_candidates.json` **claim any evidence it did not
   measure**? A one-paragraph answer with file names is enough. If the answer is "no, it is read-only
   over its own JSON", say exactly that.
3. **Do the two new CI workflows push, promote, or otherwise mutate git?** Yes/no with the lines.
4. Nothing else. **Do not start A-67 arm 1, A-69, or the g6-g16 rebuild** — those are ours to run,
   and running them outside the sealed contract would spend the experiment.

---

## 6. HOUSE RULES FOR YOUR ANSWER

1. **Name the benchmark before the result.** No claim of predictive value without what it beats.
2. **Falsification first.** For every mechanism, state what would kill it.
3. **Per cell, never pooled.**
4. **Three evidence states, never collapsed:** FOUND (with citation), SEARCHED AND FOUND NOTHING,
   NOT VERIFIED. "Probably" is none of these.
5. **An instance sits beside the claim it supports**, not in a separate section.
6. **Nothing local.** Every path or endpoint you name must be reachable by anyone.
7. **No emojis or special symbols.** Plain text, plain tables.
8. **Distinguish measurement from vendor marketing**, especially on data products.
