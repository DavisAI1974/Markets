# Spec: the joined teachers (Greg, 2026-09-28)

Status: SPEC for Greg's go. Nothing here is built or launched until he says go.

## Why

Today the classroom teaches Frankie from 19 columns of book mechanics, built at launch. The cycle calculations, the
bedrock (dipole state, FIFO, D, families, clocks) and Frankie's own classroom findings never reach either teacher.
Greg: the teachers are there to TEACH, and to teach well they must see all the data, so that they and Frankie can find
correlations, causations, patterns and couplings between the dipole and the other data at the same time.

## The two teachers (existing roles, extended)

1. **The BOSS teacher** (`boss_teacher_scientific`, the original teacher). Duties kept: the mathematical targets, masks,
   controls and training supervision. Extended: it builds and holds the JOINED, TIME-ALIGNED data (below) and runs the
   coupling search on it. It is the data specialist.
2. **The classroom scientific teacher** (`scientific_teacher`). Duties kept: it examines mechanism, mathematics,
   assumptions and evidence, and reviews Frankie's classroom answers with him. Extended: it reads the same joined data
   and the BOSS teacher's coupling results. It is the mechanism and evidence specialist.
3. **They exchange specialties** (the existing `dipole_teacher_discussion.py` exchange, widened). The BOSS teacher hands
   over what it measured (the couplings, each with its null, cells and clocks). The scientific teacher hands back
   mechanism readings, challenges and proposed tests. Each turn may use the other's findings to look again. New
   discoveries from that exchange are recorded as the teachers' own findings, with the data that supports them.
4. **Jev** sits in on the same material the classroom teaches from, sent whole in parts (never cut).

## What the teachers see: everything, except three things

**Given to both teachers, whole (gaps listed, never dropped; nothing normalized or averaged):**
- The journal: every event, the full book at every level, orders before and after, FIFO order, fills, unknown-side
  trades (carried with count and volume).
- The whole bedrock, per group: dipole state and roll20, D-depth and lineage, families, FIFO and cohort features, the
  book path (4.2), queue features (4.6), pre-birth states, and the seven causal clocks.
- The cycle calculations: the legacy layers (price, signed flow, per-second roll20, book imbalance, structure).
- The teachers' own earlier findings and exchanges.
- Frankie's FINDINGS: the observed facts, numbers and relationships in his classroom answers and analysis, and the
  dipole research discussions (Jev's included).

**Rule 1: Frankie's decision process is withheld from both teachers (and Jev).** How he makes decisions must not
influence the teachers who are teaching him to decide better. Withheld: his forecasts and calls, locks and no-locks,
accounting and ledger choices, the reasoning that leads to a call, his play book (the brain's plays), the group-run
specialist reasoning and ledgers, and decision traces. Where a classroom answer mixes a finding with decision reasoning,
the finding passes and the decision reasoning is held back.

**Rule 2: what Frankie is graded on is kept out of the lesson material.** The teachers may use hindsight (they may see
outcomes). The material handed to Frankie before he answers never carries the outcomes he is graded on (the target
outcomes, e.g. Tuesday's; the teacher key). Otherwise the grade measures nothing.

**Rule 3: Frankie's findings are claims, never truth, and never the answer key.** They enter labelled as his claims, as
things to check. The teachers confirm or refute each one and name the data that settled it. The answer key and the
grading are built from data only, so he is never graded against his own claim.

## How relationships are found (no averages)

- Everything is joined per F_LAST group and timestamp, and each row carries only what was knowable at that moment (the
  causal clocks; the leakage gate `odcore/leakage.py` runs before any relationship is reported).
- The relationship tools are per event and per cell, never pooled: lead-lag (`odcore/leadlag.py`), the coupling
  scanner with its circular-shift null (`coupling_scanner.py`, `null_extract.py`), symbolic regression (`symbolic.py`).
- The classroom's current 171 pooled Pearson correlations are replaced: a correlation is an average (D37).
- More data yields more chance patterns, so every coupling is reported with its null result and the cells where it
  holds and where it does not ("works on {X}, not {Y}"). Nothing is dropped early (D52); trust is earned forward.
- The dipole direction question stays open research (D51, D52).

## Where it runs in the cycle

- **Launch:** the BOSS teacher reads the journal once, alongside Frankie's context (saved blocks, concurrent teacher,
  already built), joins the retained cycle calculations and bedrock, runs the coupling search, and builds the targets and
  the classroom package from the joined data (not from the 19 columns alone).
- **Principal session:** the classroom and the teacher exchange use the joined material. Jev relays it whole.
- **After the classroom:** the BOSS teacher adds this cycle's findings (as claims, rule 3) and the classroom exchange,
  re-checks them against the data, and writes the result for the correction turn and the next cycle. Today no host step
  reads the principal's classroom findings back at all; this adds that reader.

## Open points for Greg

1. **The same model plays every role.** The code says it outright: "These are roles using the established model, not
   independent experiments." When both teachers and Frankie are Granite, their agreement is not independent
   confirmation. Only the data checks are. Keep it, or give a teacher a different model (the CLM-8B / Jev idea)?
2. **Granite's read of the bedrock.** The teachers' code reads the layer files directly, with no size problem. Whether
   Frankie also reads the 18 bedrock tables (about 3.8 GB rendered) waits on a one-to-two-minute token measurement after
   the stacks.
3. **Pinned identities.** The classroom package, the teacher key and the binding hashes change. The next launch mints
   the new ones.
